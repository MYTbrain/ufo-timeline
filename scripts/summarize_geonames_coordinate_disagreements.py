"""Report exact/source coordinates that disagree with same-country GeoNames.

This is a report-only QA lane for the remaining coastal/water-dot problem.
The broad country/state checks catch wrong hemispheres and country mismatches;
this pass catches rows whose source coordinate is far away from a same-country
GeoNames feature matching the primary place name.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
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
    best_country_candidate,
    cleaned_city_keys,
    is_offshore_like,
    load_country_code_aliases,
    load_relevant_geonames_index,
    primary_place_text,
)


DEFAULT_INPUT = Path("data/canonical_preview_map_enrich_v108_country_polygon_repair/deduped_events.jsonl")
DEFAULT_COUNTRIES = Path("static_bundle/data/world_countries.geojson")
DEFAULT_COUNTRY_INFO = Path("cache/map_overlays/countryInfo.txt")
DEFAULT_GEONAMES_ZIP = Path("cache/map_overlays/allCountries.zip")
DEFAULT_JSON = Path("data/reports/geonames_coordinate_disagreements.json")
DEFAULT_CSV = Path("data/reports/geonames_coordinate_disagreements.csv")


def summarize_geonames_coordinate_disagreements(
    *,
    input_path: Path,
    countries_geojson: Path,
    country_info: Path,
    geonames_zip: Path,
    json_output: Path,
    csv_output: Path,
    min_distance_km: float = 75.0,
    max_examples: int = 1000,
) -> dict[str, Any]:
    country_index = load_country_index(countries_geojson)
    country_codes = load_country_code_aliases(country_info)
    candidates = collect_candidate_events(input_path, country_codes)
    needed_keys = {
        (candidate["country_code"], key)
        for candidate in candidates
        for key in candidate["city_keys"]
    }
    geonames_index = load_relevant_geonames_index(geonames_zip, needed_keys, country_index, country_codes)

    rows: list[dict[str, Any]] = []
    matched_count = 0
    for candidate_event in candidates:
        candidate = best_country_candidate(candidate_event, geonames_index)
        if candidate is None:
            continue
        matched_count += 1
        distance_km = haversine_km(candidate_event["lat"], candidate_event["lon"], candidate["lat"], candidate["lon"])
        if distance_km < min_distance_km:
            continue
        rows.append(disagreement_payload(candidate_event, candidate, distance_km))

    rows.sort(key=lambda row: (-row["distance_km"], row["country"], row["source_name"], row["location_raw"]))
    report = {
        "schema_version": 1,
        "mode": "report_only",
        "canonical_outputs_mutated": False,
        "inputs": {
            "deduped_events": str(input_path),
            "countries_geojson": str(countries_geojson),
            "country_info": str(country_info),
            "geonames_zip": str(geonames_zip),
        },
        "outputs": {
            "json": str(json_output),
            "csv": str(csv_output),
        },
        "candidate_event_count": len(candidates),
        "same_country_geonames_match_count": matched_count,
        "min_distance_km": min_distance_km,
        "disagreement_count": len(rows),
        "source_counts": count_by(rows, "source_name"),
        "country_counts": count_by(rows, "country"),
        "coordinate_source_counts": count_by(rows, "coordinate_source"),
        "examples": rows[:max_examples],
        "notes": [
            "Report-only: no canonical, preview, or static files are mutated.",
            "Rows with explicit offshore/sea/island-like wording are excluded.",
            "Distances compare the current mapped coordinate to the best same-country GeoNames match for the primary place name.",
        ],
    }
    write_json(json_output, report)
    write_csv(csv_output, rows)
    return report


def collect_candidate_events(input_path: Path, country_codes: dict[str, str]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    with input_path.open("r", encoding="utf-8") as source:
        for line in source:
            if not line.strip():
                continue
            event = json.loads(line)
            coordinate_source = clean_text(event.get("coordinate_source"))
            if coordinate_source not in EXACT_COORDINATE_SOURCES:
                continue
            lat = parse_float(event.get("lat"))
            lon = parse_float(event.get("lon"))
            if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
                continue
            country_name = inferred_country_name(event)
            country_code = country_codes.get(country_name or "")
            if not country_name or not country_code:
                continue
            primary_text = primary_place_text(event)
            if is_offshore_like(event, primary_text):
                continue
            city_keys = cleaned_city_keys(primary_text)
            if not city_keys:
                continue
            candidates.append({
                "event": event,
                "country_name": country_name,
                "country_code": country_code,
                "lat": lat,
                "lon": lon,
                "primary_text": primary_text,
                "city_keys": city_keys,
            })
    return candidates


def disagreement_payload(candidate_event: dict[str, Any], candidate: dict[str, Any], distance_km: float) -> dict[str, Any]:
    event = candidate_event["event"]
    return {
        "canonical_event_id": event.get("canonical_event_id"),
        "event_id": event.get("event_id"),
        "source_name": event.get("source_name"),
        "source_row_number": event.get("source_row_number"),
        "source_native_id": event.get("source_native_id"),
        "date": event.get("sort_date_iso") or event.get("date") or event.get("date_raw"),
        "location_raw": event.get("location_raw"),
        "country": candidate_event["country_name"],
        "coordinate_source": event.get("coordinate_source"),
        "location_precision": event.get("location_precision"),
        "lat": candidate_event["lat"],
        "lon": candidate_event["lon"],
        "geonames_name": candidate.get("name"),
        "geonames_id": candidate.get("geoname_id"),
        "geonames_feature_class": candidate.get("feature_class"),
        "geonames_feature_code": candidate.get("feature_code"),
        "geonames_lat": candidate.get("lat"),
        "geonames_lon": candidate.get("lon"),
        "distance_km": round(distance_km, 3),
    }


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    return 2 * radius_km * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = clean_text(row.get(key)) or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "canonical_event_id",
        "event_id",
        "source_name",
        "source_row_number",
        "source_native_id",
        "date",
        "location_raw",
        "country",
        "coordinate_source",
        "location_precision",
        "lat",
        "lon",
        "geonames_name",
        "geonames_id",
        "geonames_feature_class",
        "geonames_feature_code",
        "geonames_lat",
        "geonames_lon",
        "distance_km",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--countries-geojson", type=Path, default=DEFAULT_COUNTRIES)
    parser.add_argument("--country-info", type=Path, default=DEFAULT_COUNTRY_INFO)
    parser.add_argument("--geonames-zip", type=Path, default=DEFAULT_GEONAMES_ZIP)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--min-distance-km", type=float, default=75.0)
    parser.add_argument("--max-examples", type=int, default=1000)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = summarize_geonames_coordinate_disagreements(
        input_path=args.input,
        countries_geojson=args.countries_geojson,
        country_info=args.country_info,
        geonames_zip=args.geonames_zip,
        json_output=args.json_output,
        csv_output=args.csv_output,
        min_distance_km=args.min_distance_km,
        max_examples=args.max_examples,
    )
    print(json.dumps({
        "json": report["outputs"]["json"],
        "csv": report["outputs"]["csv"],
        "candidate_event_count": report["candidate_event_count"],
        "same_country_geonames_match_count": report["same_country_geonames_match_count"],
        "disagreement_count": report["disagreement_count"],
        "canonical_outputs_mutated": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
