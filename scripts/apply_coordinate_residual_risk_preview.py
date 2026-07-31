"""Unmap high-confidence residual coordinate failures in a preview sidecar.

This is a conservative event-level guard applied after the broader coordinate
repair lanes. It does not hide whole country/source buckets. It only unmaps
exact/source coordinates that still carry direct evidence of wrong hemisphere
or raw-region/country conflict.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.apply_coordinate_sanity_preview import (
    EXACT_COORDINATE_SOURCES,
    clean_text,
    inferred_country_name,
    load_country_index,
    parse_float,
    point_in_feature,
    write_json,
)
from scripts.summarize_coordinate_residual_risk import (
    EASTERN_HEMISPHERE_COUNTRIES,
    WESTERN_HEMISPHERE_COUNTRIES,
    region_conflicts_country,
    review_bounds_for_country,
)


DEFAULT_INPUT = Path("data/canonical_preview_map_enrich_v36_country_polygon_coordinate_repair/deduped_events.jsonl")
DEFAULT_COUNTRIES = Path("static_bundle/data/world_countries.geojson")
DEFAULT_OUTPUT_DIR = Path("data/canonical_preview_map_enrich_v37_residual_coordinate_quarantine")
DEFAULT_REPORT = Path("data/reports/coordinate_residual_risk_apply_v37_report.json")

CANADIAN_PROVINCE_REVIEW_BOUNDS = {
    "AB": (48.5, 60.5, -121.0, -109.0),
    "ALB": (48.5, 60.5, -121.0, -109.0),
    "BC": (48.0, 60.5, -139.5, -113.0),
    "MAN": (48.5, 60.5, -103.5, -88.5),
    "MB": (48.5, 60.5, -103.5, -88.5),
    "NB": (44.0, 48.5, -69.0, -63.0),
    "NF": (46.0, 61.0, -68.5, -51.0),
    "NFL": (46.0, 61.0, -68.5, -51.0),
    "NL": (46.0, 61.0, -68.5, -51.0),
    "NS": (43.0, 47.5, -67.5, -59.0),
    "NT": (59.0, 84.0, -136.5, -101.0),
    "NWT": (59.0, 84.0, -136.5, -101.0),
    "NU": (59.0, 84.0, -122.0, -60.0),
    "NUV": (59.0, 84.0, -122.0, -60.0),
    "ON": (41.0, 57.5, -96.5, -74.0),
    "ONT": (41.0, 57.5, -96.5, -74.0),
    "PE": (45.5, 47.5, -64.5, -61.5),
    "PEI": (45.5, 47.5, -64.5, -61.5),
    "QC": (44.0, 63.5, -80.5, -57.0),
    "QUE": (44.0, 63.5, -80.5, -57.0),
    "SK": (48.5, 60.5, -111.0, -101.0),
    "SAS": (48.5, 60.5, -111.0, -101.0),
    "YK": (59.0, 70.5, -141.5, -122.0),
    "YT": (59.0, 70.5, -141.5, -122.0),
    "YUK": (59.0, 70.5, -141.5, -122.0),
}
STRICT_REVIEW_BOUNDS_COUNTRIES = {
    "Zimbabwe",
}


def apply_coordinate_residual_risk_preview(
    *,
    input_path: Path,
    countries_geojson: Path,
    output_dir: Path,
    report_output: Path,
) -> dict[str, Any]:
    country_index = load_country_index(countries_geojson)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "deduped_events.jsonl"
    tmp_output_path = output_path.with_suffix(".jsonl.tmp")
    input_event_count = 0
    mapped_before_count = 0
    mapped_after_count = 0
    quarantined_count = 0
    quarantined_by_reason: dict[str, int] = {}
    examples: list[dict[str, Any]] = []

    with input_path.open("r", encoding="utf-8") as source, tmp_output_path.open("w", encoding="utf-8", newline="\n") as output:
        for line in source:
            if not line.strip():
                continue
            event = json.loads(line)
            input_event_count += 1
            if has_usable_coordinates(event):
                mapped_before_count += 1
            reason = residual_quarantine_reason(event, country_index)
            if reason is not None:
                event = quarantine_event(event, reason)
                quarantined_count += 1
                quarantined_by_reason[reason] = quarantined_by_reason.get(reason, 0) + 1
                if len(examples) < 80:
                    examples.append(example_payload(event))
            if has_usable_coordinates(event):
                mapped_after_count += 1
            output.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")

    tmp_output_path.replace(output_path)
    report = {
        "schema_version": 1,
        "mode": "preview_apply",
        "apply_policy": "residual_coordinate_high_confidence_wrong_hemisphere_or_region_unmap",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": True,
        "inputs": {
            "deduped_events": str(input_path),
            "countries_geojson": str(countries_geojson),
        },
        "outputs": {
            "deduped_events": str(output_path),
            "report": str(report_output),
        },
        "input_event_count": input_event_count,
        "mapped_before_count": mapped_before_count,
        "mapped_after_count": mapped_after_count,
        "quarantined_event_count": quarantined_count,
        "mapped_reduction_count": mapped_before_count - mapped_after_count,
        "quarantined_by_reason": dict(sorted(quarantined_by_reason.items())),
        "examples": examples,
        "notes": [
            "This pass does not mutate canonical_full.",
            "Whole country/source buckets are not hidden; each event must independently match a high-confidence residual failure rule.",
            "Source coordinates are preserved in coordinate_residual_quarantine_original_lat/lon for audit.",
        ],
    }
    write_json(report_output, report)
    return report


def residual_quarantine_reason(event: dict[str, Any], country_index: dict[str, dict[str, Any]]) -> str | None:
    if clean_text(event.get("coordinate_source")) not in EXACT_COORDINATE_SOURCES:
        return None
    lat = parse_float(event.get("lat"))
    lon = parse_float(event.get("lon"))
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    country_name = inferred_country_name(event)
    if not country_name:
        return None
    province_reason = canadian_province_quarantine_reason(event, country_name, lat, lon)
    if province_reason is not None:
        return province_reason
    feature = country_index.get(country_name)
    if feature and point_in_feature(lat, lon, feature):
        return None
    raw_region = clean_text((event.get("raw_fields") or {}).get("REGION") or event.get("country")).upper()
    outside_review_bounds = not point_in_review_bounds(country_name, lat, lon)
    if country_name in STRICT_REVIEW_BOUNDS_COUNTRIES and outside_review_bounds:
        return f"{country_name.lower().replace(' ', '_')}_coordinate_outside_review_bounds"
    if region_conflicts_country(raw_region, country_name) and outside_review_bounds:
        return "raw_region_conflicts_declared_country_outside_review_bounds"
    if country_name in WESTERN_HEMISPHERE_COUNTRIES and lon > 0:
        return "positive_longitude_for_western_hemisphere_country"
    if country_name in EASTERN_HEMISPHERE_COUNTRIES and lon < -20:
        return "far_negative_longitude_for_eastern_hemisphere_country"
    return None


def canadian_province_quarantine_reason(event: dict[str, Any], country_name: str, lat: float, lon: float) -> str | None:
    if country_name != "Canada":
        return None
    raw_fields = event.get("raw_fields") or {}
    province = clean_text(raw_fields.get("STATE") or event.get("state_province")).upper()
    if province not in CANADIAN_PROVINCE_REVIEW_BOUNDS:
        return None
    min_lat, max_lat, min_lon, max_lon = CANADIAN_PROVINCE_REVIEW_BOUNDS[province]
    if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
        return None
    return "canadian_province_coordinate_outside_review_bounds"


def point_in_review_bounds(country_name: str, lat: float, lon: float) -> bool:
    return any(
        min_lat <= lat <= max_lat and min_lon <= lon <= max_lon
        for min_lat, max_lat, min_lon, max_lon in review_bounds_for_country(country_name)
    )


def quarantine_event(event: dict[str, Any], reason: str) -> dict[str, Any]:
    next_event = dict(event)
    lat = parse_float(next_event.get("lat"))
    lon = parse_float(next_event.get("lon"))
    next_event["coordinate_residual_quarantine_status"] = "quarantine_until_review"
    next_event["coordinate_residual_quarantine_reason"] = reason
    next_event["coordinate_residual_quarantine_original_lat"] = lat
    next_event["coordinate_residual_quarantine_original_lon"] = lon
    next_event["coordinate_residual_quarantine_original_source"] = next_event.get("coordinate_source")
    next_event["coordinate_residual_quarantine_original_precision"] = next_event.get("location_precision")
    next_event["lat"] = None
    next_event["lon"] = None
    next_event["coordinate_source"] = "unresolved"
    next_event["location_precision"] = "unknown"
    note = f"Residual coordinate risk preview removed map coordinates pending review: {reason}."
    existing_notes = clean_text(next_event.get("mapping_notes"))
    next_event["mapping_notes"] = f"{existing_notes} {note}".strip()
    return next_event


def example_payload(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "canonical_event_id": event.get("canonical_event_id"),
        "source_name": event.get("source_name"),
        "source_row_number": event.get("source_row_number"),
        "source_native_id": event.get("source_native_id"),
        "date": event.get("date") or event.get("sort_date_iso"),
        "location_raw": event.get("location_raw"),
        "original_lat": event.get("coordinate_residual_quarantine_original_lat"),
        "original_lon": event.get("coordinate_residual_quarantine_original_lon"),
        "reason": event.get("coordinate_residual_quarantine_reason"),
    }


def has_usable_coordinates(event: dict[str, Any]) -> bool:
    lat = parse_float(event.get("lat"))
    lon = parse_float(event.get("lon"))
    return lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--countries-geojson", type=Path, default=DEFAULT_COUNTRIES)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = apply_coordinate_residual_risk_preview(
        input_path=args.input,
        countries_geojson=args.countries_geojson,
        output_dir=args.output_dir,
        report_output=args.report_output,
    )
    print(json.dumps({
        "output": report["outputs"]["deduped_events"],
        "report": report["outputs"]["report"],
        "quarantined_event_count": report["quarantined_event_count"],
        "mapped_reduction_count": report["mapped_reduction_count"],
        "quarantined_by_reason": report["quarantined_by_reason"],
        "canonical_outputs_mutated": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
