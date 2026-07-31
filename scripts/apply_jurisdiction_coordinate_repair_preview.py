"""Repair or quarantine coordinates that contradict explicit location text.

This preview-only lane targets rows that have usable coordinates but clearly
fall outside an explicit jurisdiction in the rendered location text. For v1 it
handles explicit U.S. city/state rows because that is the dominant visible
failure mode: rows such as ``FARGO, Cass, ND, US`` rendered in Asia or another
U.S. state.

Policy:
- If a U.S. row is outside its declared state and GeoNames has a matching
  populated-place candidate in that same state, replace the coordinate.
- If no safe same-state candidate exists, remove the coordinate from map
  display pending review.
- Source rows are preserved; canonical source artifacts are never mutated.
"""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from typing import Any

from scripts.apply_coordinate_sanity_preview import clean_text, parse_float, write_json
from scripts.summarize_structured_city_alias_geonames_mapping_candidates import (
    city_alias_variants,
    city_key,
    normalized_city_keys,
)


DEFAULT_INPUT = Path("data/canonical_preview_map_enrich_v34_europe_residual_coordinate_sign/deduped_events.jsonl")
DEFAULT_GEONAMES_ZIP = Path("cache/map_overlays/allCountries.zip")
DEFAULT_OUTPUT_DIR = Path("data/canonical_preview_map_enrich_v35_us_state_coordinate_repair")
DEFAULT_REPORT = Path("data/reports/jurisdiction_coordinate_repair_v35_us_state_report.json")

EXACT_OR_MAPPED_COORDINATE_SOURCES = {
    "raw_latlong",
    "source_coordinates",
    "location_coordinates",
    "geocoded",
}

# Broad bounds with intentional padding. These are not precise polygons; they
# are QA gates for impossible state placements.
US_STATE_BOUNDS = {
    "AL": (30.0, 36.0, -89.0, -84.0),
    "AK": (51.0, 72.0, -180.0, -129.0),
    "AZ": (31.0, 38.0, -115.0, -108.0),
    "AR": (33.0, 37.0, -95.0, -89.0),
    "CA": (32.0, 43.0, -125.0, -114.0),
    "CO": (36.0, 42.0, -110.0, -101.0),
    "CT": (40.5, 42.5, -74.0, -71.0),
    "DC": (38.7, 39.1, -77.2, -76.8),
    "DE": (38.0, 40.0, -76.0, -74.5),
    "FL": (24.0, 31.5, -88.0, -79.0),
    "GA": (30.0, 35.5, -86.0, -80.0),
    "HI": (18.0, 23.0, -161.0, -154.0),
    "IA": (40.0, 44.0, -97.0, -90.0),
    "ID": (42.0, 50.0, -118.0, -111.0),
    "IL": (36.5, 43.0, -92.0, -86.0),
    "IN": (37.0, 42.0, -89.0, -84.0),
    "KS": (36.0, 40.5, -103.0, -94.0),
    "KY": (36.0, 40.0, -90.0, -81.0),
    "LA": (28.5, 33.5, -95.0, -88.0),
    "MA": (41.0, 43.0, -74.0, -69.0),
    "MD": (37.5, 40.0, -80.0, -75.0),
    "ME": (43.0, 48.0, -72.0, -66.0),
    "MI": (41.0, 49.0, -91.0, -82.0),
    "MN": (43.0, 50.0, -98.0, -89.0),
    "MO": (35.5, 41.0, -96.0, -89.0),
    "MS": (30.0, 35.5, -92.0, -88.0),
    "MT": (44.0, 50.0, -117.0, -103.0),
    "NC": (33.0, 37.0, -85.0, -75.0),
    "ND": (45.0, 50.0, -105.0, -96.0),
    "NE": (39.5, 43.5, -105.0, -95.0),
    "NH": (42.5, 45.5, -73.0, -70.0),
    "NJ": (38.5, 41.5, -76.0, -73.0),
    "NM": (31.0, 37.5, -110.0, -103.0),
    "NV": (35.0, 42.5, -121.0, -113.0),
    "NY": (40.0, 46.0, -80.0, -71.0),
    "OH": (38.0, 42.5, -85.0, -80.0),
    "OK": (33.5, 37.5, -104.0, -94.0),
    "OR": (41.5, 46.5, -125.0, -116.0),
    "PA": (39.5, 42.5, -81.0, -74.0),
    "RI": (41.0, 42.5, -72.0, -70.0),
    "SC": (32.0, 35.5, -84.0, -78.0),
    "SD": (42.0, 46.0, -105.0, -96.0),
    "TN": (34.5, 37.0, -91.0, -81.0),
    "TX": (25.0, 37.0, -107.0, -93.0),
    "UT": (36.5, 42.5, -115.0, -108.0),
    "VA": (36.0, 40.0, -84.0, -75.0),
    "VT": (42.5, 45.5, -74.0, -71.0),
    "WA": (45.0, 50.0, -125.0, -116.0),
    "WI": (42.0, 47.5, -93.0, -86.0),
    "WV": (37.0, 41.0, -83.0, -77.0),
    "WY": (40.5, 45.5, -112.0, -104.0),
}


def apply_jurisdiction_coordinate_repair_preview(
    *,
    input_path: Path,
    geonames_zip: Path,
    output_dir: Path,
    report_output: Path,
) -> dict[str, Any]:
    geonames_index = load_us_geonames_index(geonames_zip)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "deduped_events.jsonl"
    tmp_output_path = output_path.with_suffix(".jsonl.tmp")

    input_event_count = 0
    mapped_before_count = 0
    checked_us_state_count = 0
    outside_state_count = 0
    repaired_count = 0
    quarantined_count = 0
    repaired_by_state: dict[str, int] = {}
    quarantined_by_state: dict[str, int] = {}
    examples: list[dict[str, Any]] = []

    with input_path.open("r", encoding="utf-8") as source, tmp_output_path.open("w", encoding="utf-8", newline="\n") as output:
        for line in source:
            if not line.strip():
                continue
            event = json.loads(line)
            input_event_count += 1
            if has_usable_coordinates(event):
                mapped_before_count += 1

            state = explicit_us_state(event.get("location_raw"))
            if state and clean_text(event.get("coordinate_source")) in EXACT_OR_MAPPED_COORDINATE_SOURCES:
                lat = parse_float(event.get("lat"))
                lon = parse_float(event.get("lon"))
                if lat is not None and lon is not None:
                    checked_us_state_count += 1
                    if not is_inside_state_bounds(state, lat, lon):
                        outside_state_count += 1
                        next_event, action = repair_or_quarantine_us_state_event(event, state, lat, lon, geonames_index)
                        event = next_event
                        if action["action"] == "repaired":
                            repaired_count += 1
                            repaired_by_state[state] = repaired_by_state.get(state, 0) + 1
                        elif action["action"] == "quarantined":
                            quarantined_count += 1
                            quarantined_by_state[state] = quarantined_by_state.get(state, 0) + 1
                        if len(examples) < 100:
                            examples.append(action)

            output.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")

    tmp_output_path.replace(output_path)
    report = {
        "schema_version": 1,
        "mode": "preview_apply",
        "apply_policy": "explicit_us_state_coordinate_repair_or_unmap",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": True,
        "inputs": {
            "deduped_events": str(input_path),
            "geonames_zip": str(geonames_zip),
        },
        "outputs": {
            "deduped_events": str(output_path),
            "report": str(report_output),
        },
        "input_event_count": input_event_count,
        "mapped_before_count": mapped_before_count,
        "checked_us_state_count": checked_us_state_count,
        "outside_state_count": outside_state_count,
        "repaired_event_count": repaired_count,
        "quarantined_event_count": quarantined_count,
        "mapped_after_count": mapped_before_count - quarantined_count,
        "repaired_by_state": dict(sorted(repaired_by_state.items())),
        "quarantined_by_state": dict(sorted(quarantined_by_state.items())),
        "examples": examples,
        "notes": [
            "Only rows with explicit trailing U.S. state plus US/USA are considered.",
            "Outside-state rows are repaired only with a same-state GeoNames populated-place match.",
            "Rows without a same-state city match are unmapped pending review to avoid false dots.",
            "This is preview-only and does not mutate canonical source artifacts.",
        ],
    }
    write_json(report_output, report)
    return report


def repair_or_quarantine_us_state_event(
    event: dict[str, Any],
    state: str,
    lat: float,
    lon: float,
    geonames_index: dict[tuple[str, str], list[dict[str, Any]]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    city = primary_city_text(event.get("location_raw"))
    candidate = best_us_city_candidate(city, state, geonames_index)
    if candidate is None:
        next_event = dict(event)
        next_event["jurisdiction_coordinate_repair_action"] = "quarantine_unmapped"
        next_event["jurisdiction_coordinate_repair_reason"] = "outside_declared_us_state_no_same_state_geonames_city"
        next_event["jurisdiction_coordinate_original_lat"] = lat
        next_event["jurisdiction_coordinate_original_lon"] = lon
        next_event["jurisdiction_coordinate_original_source"] = next_event.get("coordinate_source")
        next_event["lat"] = None
        next_event["lon"] = None
        next_event["coordinate_source"] = "unresolved"
        next_event["location_precision"] = "unknown"
        next_event["mapping_notes"] = append_note(
            next_event,
            f"Jurisdiction coordinate repair unmapped outside-state coordinate for {state} pending review.",
        )
        return next_event, action_payload("quarantined", event, state, lat, lon, None, None, None)

    next_event = dict(event)
    next_event["lat"] = candidate["lat"]
    next_event["lon"] = candidate["lon"]
    next_event["coordinate_source"] = "geocoded"
    next_event["location_precision"] = "city"
    next_event["geocode_query_used"] = f"{candidate['name']}, {state}, US"
    next_event["geocode_display_name"] = f"{candidate['name']}, {state}, US"
    next_event["geocode_confidence"] = 0.9
    next_event["jurisdiction_coordinate_repair_action"] = "replace_with_same_state_geonames_city"
    next_event["jurisdiction_coordinate_repair_reason"] = "outside_declared_us_state"
    next_event["jurisdiction_coordinate_original_lat"] = lat
    next_event["jurisdiction_coordinate_original_lon"] = lon
    next_event["jurisdiction_coordinate_original_source"] = next_event.get("coordinate_source")
    next_event["jurisdiction_coordinate_geoname_id"] = candidate["geoname_id"]
    next_event["mapping_notes"] = append_note(
        next_event,
        f"Jurisdiction coordinate repair replaced outside-state coordinate with same-state GeoNames city {candidate['name']}, {state}.",
    )
    return next_event, action_payload("repaired", event, state, lat, lon, candidate["lat"], candidate["lon"], candidate)


def load_us_geonames_index(path: Path) -> dict[tuple[str, str], list[dict[str, Any]]]:
    index: dict[tuple[str, str], list[dict[str, Any]]] = {}
    with zipfile.ZipFile(path) as archive:
        with archive.open("allCountries.txt") as raw:
            for raw_line in raw:
                line = raw_line.decode("utf-8", errors="replace").rstrip("\n")
                parts = line.split("\t")
                if len(parts) < 19 or parts[6] != "P" or parts[8].upper() != "US":
                    continue
                admin1 = parts[10].upper()
                if admin1 not in US_STATE_BOUNDS:
                    continue
                candidate = {
                    "geoname_id": parts[0],
                    "name": parts[1],
                    "primary_city_key": city_key(parts[1]),
                    "lat": float(parts[4]),
                    "lon": float(parts[5]),
                    "admin1": admin1,
                    "feature_code": parts[7],
                    "population": int(parts[14] or 0),
                    "timezone": parts[17],
                }
                for key in normalized_city_keys(parts[1], parts[2], parts[3]):
                    index.setdefault((admin1, key), []).append(candidate)
    for key, candidates in index.items():
        candidates.sort(key=lambda item: (-int(item["population"]), item["feature_code"], item["name"], item["geoname_id"]))
    return index


def best_us_city_candidate(
    city: str,
    state: str,
    geonames_index: dict[tuple[str, str], list[dict[str, Any]]],
) -> dict[str, Any] | None:
    variants = city_alias_variants(city)
    for variant in variants:
        candidates = geonames_index.get((state, variant))
        primary_matches = [candidate for candidate in candidates or [] if candidate.get("primary_city_key") in variants]
        if primary_matches:
            return primary_matches[0]
    for variant in variants:
        candidates = geonames_index.get((state, variant))
        if candidates and len(candidates) == 1:
            return candidates[0]
    return None


def explicit_us_state(location_raw: Any) -> str | None:
    parts = [part.strip().upper().strip(".") for part in clean_text(location_raw).split(",")]
    parts = [part for part in parts if part]
    if len(parts) < 2 or parts[-1] not in {"US", "USA", "UNITED STATES"}:
        return None
    state = parts[-2]
    return state if state in US_STATE_BOUNDS else None


def primary_city_text(location_raw: Any) -> str:
    return clean_text(location_raw).split(",", 1)[0].strip()


def is_inside_state_bounds(state: str, lat: float, lon: float) -> bool:
    min_lat, max_lat, min_lon, max_lon = US_STATE_BOUNDS[state]
    return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon


def has_usable_coordinates(event: dict[str, Any]) -> bool:
    lat = parse_float(event.get("lat"))
    lon = parse_float(event.get("lon"))
    return lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180


def append_note(event: dict[str, Any], note: str) -> str:
    existing = clean_text(event.get("mapping_notes"))
    return f"{existing} {note}".strip()


def action_payload(
    action: str,
    event: dict[str, Any],
    state: str,
    old_lat: float,
    old_lon: float,
    new_lat: float | None,
    new_lon: float | None,
    candidate: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "action": action,
        "canonical_event_id": event.get("canonical_event_id"),
        "source_name": event.get("source_name"),
        "source_row_number": event.get("source_row_number"),
        "source_native_id": event.get("source_native_id"),
        "date": event.get("date") or event.get("sort_date_iso"),
        "location_raw": event.get("location_raw"),
        "state": state,
        "old_lat": old_lat,
        "old_lon": old_lon,
        "new_lat": new_lat,
        "new_lon": new_lon,
        "geoname_id": candidate.get("geoname_id") if candidate else None,
        "geonames_name": candidate.get("name") if candidate else None,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--geonames-zip", type=Path, default=DEFAULT_GEONAMES_ZIP)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = apply_jurisdiction_coordinate_repair_preview(
        input_path=args.input,
        geonames_zip=args.geonames_zip,
        output_dir=args.output_dir,
        report_output=args.report_output,
    )
    print(
        json.dumps(
            {
                "output": report["outputs"]["deduped_events"],
                "report": report["outputs"]["report"],
                "outside_state_count": report["outside_state_count"],
                "repaired_event_count": report["repaired_event_count"],
                "quarantined_event_count": report["quarantined_event_count"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
