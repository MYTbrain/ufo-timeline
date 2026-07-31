"""Repair high-confidence longitude sign-mirror coordinate errors.

This preview lane targets rows that already pass broad country-polygon checks
but still visibly plot on the wrong side of the map because the longitude sign
is mirrored. The rule is intentionally narrow:

- only exact/source coordinate rows are considered;
- explicit offshore/sea/island rows are skipped;
- the primary place name must match a same-country GeoNames feature;
- latitude must already be close to the GeoNames feature;
- the absolute longitude magnitude must already be close, but with opposite
  sign;
- the current point must be meaningfully far from the matching GeoNames point.

This catches cases such as western France plotted east of Greenwich, or
Balearic/Spanish rows plotted west of Greenwich, without applying broad fuzzy
geocoding to every coordinate disagreement.
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
    write_json,
)
from scripts.apply_country_polygon_coordinate_repair_preview import (
    append_note,
    best_country_candidate,
    cleaned_city_keys,
    has_usable_coordinates,
    is_offshore_like,
    load_country_code_aliases,
    load_relevant_geonames_index,
    primary_place_text,
)
from scripts.summarize_geonames_coordinate_disagreements import haversine_km


DEFAULT_INPUT = Path("data/canonical_preview_map_enrich_v108_country_polygon_repair/deduped_events.jsonl")
DEFAULT_COUNTRIES = Path("static_bundle/data/world_countries.geojson")
DEFAULT_COUNTRY_INFO = Path("cache/map_overlays/countryInfo.txt")
DEFAULT_GEONAMES_ZIP = Path("cache/map_overlays/allCountries.zip")
DEFAULT_OUTPUT_DIR = Path("data/canonical_preview_map_enrich_v109_geonames_sign_mirror_repair")
DEFAULT_REPORT = Path("data/reports/geonames_sign_mirror_coordinate_repair_v109_from_v108.json")

DEFAULT_MAX_LAT_DELTA_DEGREES = 0.25
DEFAULT_MAX_ABS_LON_DELTA_DEGREES = 0.25
DEFAULT_MIN_CURRENT_DISTANCE_KM = 75.0


def apply_geonames_sign_mirror_coordinate_repair_preview(
    *,
    input_path: Path,
    countries_geojson: Path,
    country_info: Path,
    geonames_zip: Path,
    output_dir: Path,
    report_output: Path,
    max_lat_delta_degrees: float = DEFAULT_MAX_LAT_DELTA_DEGREES,
    max_abs_lon_delta_degrees: float = DEFAULT_MAX_ABS_LON_DELTA_DEGREES,
    min_current_distance_km: float = DEFAULT_MIN_CURRENT_DISTANCE_KM,
) -> dict[str, Any]:
    country_index = load_country_index(countries_geojson)
    country_codes = load_country_code_aliases(country_info)
    candidate_events = collect_candidate_events(input_path, country_codes)
    needed_keys = {
        (candidate["country_code"], key)
        for candidate in candidate_events
        for key in candidate["city_keys"]
    }
    geonames_index = load_relevant_geonames_index(geonames_zip, needed_keys, country_index, country_codes)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "deduped_events.jsonl"
    tmp_output_path = output_path.with_suffix(".jsonl.tmp")

    input_event_count = 0
    mapped_before_count = 0
    candidate_event_count = 0
    same_country_geonames_match_count = 0
    sign_mirror_candidate_count = 0
    repaired_count = 0
    skipped_offshore_count = 0
    no_match_count = 0
    rejected_not_sign_mirror_count = 0
    repaired_by_country: dict[str, int] = {}
    repaired_by_source: dict[str, int] = {}
    examples: list[dict[str, Any]] = []

    with input_path.open("r", encoding="utf-8") as source, tmp_output_path.open("w", encoding="utf-8", newline="\n") as output:
        for line in source:
            if not line.strip():
                continue
            input_event_count += 1
            event = json.loads(line)
            if has_usable_coordinates(event):
                mapped_before_count += 1

            analysis = analyze_candidate_event(event, country_codes)
            if analysis is None:
                output.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
                continue

            candidate_event_count += 1
            if analysis["offshore_like"]:
                skipped_offshore_count += 1
                output.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
                continue

            candidate = best_country_candidate(analysis, geonames_index)
            if candidate is None:
                no_match_count += 1
                output.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
                continue

            same_country_geonames_match_count += 1
            assessment = assess_sign_mirror(
                analysis,
                candidate,
                max_lat_delta_degrees=max_lat_delta_degrees,
                max_abs_lon_delta_degrees=max_abs_lon_delta_degrees,
                min_current_distance_km=min_current_distance_km,
            )
            if not assessment["repairable"]:
                rejected_not_sign_mirror_count += 1
                output.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
                continue

            sign_mirror_candidate_count += 1
            event = repair_event(event, analysis, candidate, assessment)
            repaired_count += 1
            repaired_by_country[analysis["country_name"]] = repaired_by_country.get(analysis["country_name"], 0) + 1
            source_name = clean_text(event.get("source_name")) or "unknown"
            repaired_by_source[source_name] = repaired_by_source.get(source_name, 0) + 1
            if len(examples) < 200:
                examples.append(action_payload(event, analysis, candidate, assessment))

            output.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")

    tmp_output_path.replace(output_path)
    report = {
        "schema_version": 1,
        "mode": "preview_apply",
        "apply_policy": "same_country_geonames_longitude_sign_mirror_repair",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": True,
        "inputs": {
            "deduped_events": str(input_path),
            "countries_geojson": str(countries_geojson),
            "country_info": str(country_info),
            "geonames_zip": str(geonames_zip),
        },
        "outputs": {
            "deduped_events": str(output_path),
            "report": str(report_output),
        },
        "thresholds": {
            "max_lat_delta_degrees": max_lat_delta_degrees,
            "max_abs_lon_delta_degrees": max_abs_lon_delta_degrees,
            "min_current_distance_km": min_current_distance_km,
        },
        "input_event_count": input_event_count,
        "mapped_before_count": mapped_before_count,
        "candidate_event_count": candidate_event_count,
        "same_country_geonames_match_count": same_country_geonames_match_count,
        "sign_mirror_candidate_count": sign_mirror_candidate_count,
        "repaired_event_count": repaired_count,
        "skipped_offshore_like_count": skipped_offshore_count,
        "no_same_country_geonames_match_count": no_match_count,
        "rejected_not_sign_mirror_count": rejected_not_sign_mirror_count,
        "mapped_after_count": mapped_before_count,
        "repaired_by_country": dict(sorted(repaired_by_country.items())),
        "repaired_by_source": dict(sorted(repaired_by_source.items())),
        "examples": examples,
        "notes": [
            "This lane does not broadly geocode all coordinate disagreements.",
            "Rows are repaired only when a same-country GeoNames feature matching the primary place has nearly the same latitude and opposite-signed longitude magnitude.",
            "Explicit offshore/sea/island rows are skipped to avoid moving legitimate maritime sightings to land.",
            "Repaired rows are downgraded from exact source coordinates to GeoNames-backed city/mapped coordinates.",
        ],
    }
    write_json(report_output, report)
    return report


def collect_candidate_events(input_path: Path, country_codes: dict[str, str]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    with input_path.open("r", encoding="utf-8") as source:
        for line in source:
            if not line.strip():
                continue
            event = json.loads(line)
            analysis = analyze_candidate_event(event, country_codes)
            if analysis is not None and not analysis["offshore_like"]:
                candidates.append(analysis)
    return candidates


def analyze_candidate_event(event: dict[str, Any], country_codes: dict[str, str]) -> dict[str, Any] | None:
    coordinate_source = clean_text(event.get("coordinate_source"))
    if coordinate_source not in EXACT_COORDINATE_SOURCES:
        return None
    lat = parse_float(event.get("lat"))
    lon = parse_float(event.get("lon"))
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    country_name = inferred_country_name(event)
    country_code = country_codes.get(country_name or "")
    if not country_name or not country_code:
        return None
    primary_text = primary_place_text(event)
    city_keys = cleaned_city_keys(primary_text)
    if not city_keys:
        return None
    return {
        "event": event,
        "country_name": country_name,
        "country_code": country_code,
        "lat": lat,
        "lon": lon,
        "primary_text": primary_text,
        "city_keys": city_keys,
        "coordinate_source": coordinate_source,
        "offshore_like": is_offshore_like(event, primary_text),
    }


def assess_sign_mirror(
    analysis: dict[str, Any],
    candidate: dict[str, Any],
    *,
    max_lat_delta_degrees: float,
    max_abs_lon_delta_degrees: float,
    min_current_distance_km: float,
) -> dict[str, Any]:
    lat = analysis["lat"]
    lon = analysis["lon"]
    candidate_lat = candidate["lat"]
    candidate_lon = candidate["lon"]
    lat_delta = abs(lat - candidate_lat)
    abs_lon_delta = abs(abs(lon) - abs(candidate_lon))
    opposite_sign = lon * candidate_lon < 0
    current_distance_km = haversine_km(lat, lon, candidate_lat, candidate_lon)
    mirrored_distance_km = haversine_km(lat, -lon, candidate_lat, candidate_lon)
    repairable = (
        opposite_sign
        and lat_delta <= max_lat_delta_degrees
        and abs_lon_delta <= max_abs_lon_delta_degrees
        and current_distance_km >= min_current_distance_km
    )
    return {
        "repairable": repairable,
        "lat_delta_degrees": round(lat_delta, 6),
        "abs_lon_delta_degrees": round(abs_lon_delta, 6),
        "opposite_sign": opposite_sign,
        "current_distance_km": round(current_distance_km, 3),
        "mirrored_distance_km": round(mirrored_distance_km, 3),
    }


def repair_event(
    event: dict[str, Any],
    analysis: dict[str, Any],
    candidate: dict[str, Any],
    assessment: dict[str, Any],
) -> dict[str, Any]:
    next_event = dict(event)
    next_event["geonames_sign_mirror_coordinate_repair_action"] = "replace_with_same_country_geonames_sign_mirror"
    next_event["geonames_sign_mirror_coordinate_repair_reason"] = "source_longitude_sign_mirrors_same_country_geonames_feature"
    next_event["geonames_sign_mirror_coordinate_original_lat"] = analysis["lat"]
    next_event["geonames_sign_mirror_coordinate_original_lon"] = analysis["lon"]
    next_event["geonames_sign_mirror_coordinate_original_source"] = next_event.get("coordinate_source")
    next_event["geonames_sign_mirror_coordinate_geoname_id"] = candidate["geoname_id"]
    next_event["geonames_sign_mirror_coordinate_geonames_name"] = candidate["name"]
    next_event["geonames_sign_mirror_coordinate_distance_km"] = assessment["current_distance_km"]
    next_event["geonames_sign_mirror_coordinate_mirrored_distance_km"] = assessment["mirrored_distance_km"]
    next_event["lat"] = candidate["lat"]
    next_event["lon"] = candidate["lon"]
    next_event["coordinate_source"] = "geocoded"
    next_event["location_precision"] = "city" if candidate["feature_class"] == "P" else "mapped"
    next_event["geocode_query_used"] = f"{candidate['name']}, {analysis['country_name']}"
    next_event["geocode_display_name"] = f"{candidate['name']}, {analysis['country_name']}"
    next_event["geocode_confidence"] = 0.9 if candidate["feature_class"] == "P" else 0.8
    next_event["mapping_notes"] = append_note(
        next_event,
        f"GeoNames sign-mirror coordinate repair replaced opposite-signed source longitude with same-country feature {candidate['name']}, {analysis['country_name']}.",
    )
    return next_event


def action_payload(
    event: dict[str, Any],
    analysis: dict[str, Any],
    candidate: dict[str, Any],
    assessment: dict[str, Any],
) -> dict[str, Any]:
    return {
        "canonical_event_id": event.get("canonical_event_id"),
        "event_id": event.get("event_id"),
        "source_name": event.get("source_name"),
        "source_row_number": event.get("source_row_number"),
        "date": event.get("sort_date_iso") or event.get("date") or event.get("date_raw"),
        "location_raw": event.get("location_raw"),
        "country": analysis["country_name"],
        "original_lat": analysis["lat"],
        "original_lon": analysis["lon"],
        "new_lat": candidate["lat"],
        "new_lon": candidate["lon"],
        "geonames_name": candidate["name"],
        "geonames_id": candidate["geoname_id"],
        "geonames_feature_class": candidate["feature_class"],
        "geonames_feature_code": candidate["feature_code"],
        **assessment,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--countries-geojson", type=Path, default=DEFAULT_COUNTRIES)
    parser.add_argument("--country-info", type=Path, default=DEFAULT_COUNTRY_INFO)
    parser.add_argument("--geonames-zip", type=Path, default=DEFAULT_GEONAMES_ZIP)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--max-lat-delta-degrees", type=float, default=DEFAULT_MAX_LAT_DELTA_DEGREES)
    parser.add_argument("--max-abs-lon-delta-degrees", type=float, default=DEFAULT_MAX_ABS_LON_DELTA_DEGREES)
    parser.add_argument("--min-current-distance-km", type=float, default=DEFAULT_MIN_CURRENT_DISTANCE_KM)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = apply_geonames_sign_mirror_coordinate_repair_preview(
        input_path=args.input,
        countries_geojson=args.countries_geojson,
        country_info=args.country_info,
        geonames_zip=args.geonames_zip,
        output_dir=args.output_dir,
        report_output=args.report_output,
        max_lat_delta_degrees=args.max_lat_delta_degrees,
        max_abs_lon_delta_degrees=args.max_abs_lon_delta_degrees,
        min_current_distance_km=args.min_current_distance_km,
    )
    print(json.dumps({
        "output": report["outputs"]["deduped_events"],
        "report": report["outputs"]["report"],
        "candidate_event_count": report["candidate_event_count"],
        "same_country_geonames_match_count": report["same_country_geonames_match_count"],
        "repaired_event_count": report["repaired_event_count"],
        "canonical_outputs_mutated": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
