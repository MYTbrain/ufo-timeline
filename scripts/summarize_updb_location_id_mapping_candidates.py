"""Summarize UPDB location-id mapping candidates from the local SQL archive.

This report-only lane uses the PhenomenAInon/UPDB ``api.location`` table as a
local lookup for rows whose canonical event still has no coordinates. It emits
event-specific candidates only when the event's raw numeric location id maps to
a coordinate-bearing location row and the lookup city/country agrees with the
event's canonical city/country text.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import re
from pathlib import Path
from typing import Any

from scripts.apply_mapping_enrichment_preview import best_location_text, has_usable_coordinates, normalize_query


DEFAULT_INPUT = Path("data/canonical_preview_map_enrich_v11_us_city_dominant/deduped_events.jsonl")
DEFAULT_UPDB_SQL_GZ = Path("UFO Databases/sources/phenomenon.sql.gz")
DEFAULT_GEONAMES_ZIP = Path("cache/map_overlays/allCountries.zip")
DEFAULT_OUTPUT_JSON = Path("data/reports/updb_location_id_mapping_candidates_after_us_city_dominant_v12.json")
DEFAULT_OUTPUT_CSV = Path("data/reports/updb_location_id_mapping_candidates_after_us_city_dominant_v12.csv")


def summarize_updb_location_id_mapping_candidates(
    *,
    input_path: Path,
    updb_sql_gz: Path,
) -> dict[str, Any]:
    location_ids = collect_needed_location_ids(input_path)
    location_lookup = load_updb_locations(updb_sql_gz, location_ids)

    candidates: list[dict[str, Any]] = []
    rejected: dict[str, int] = {}
    input_event_count = 0
    unmapped_updb_with_location_id_count = 0

    with input_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            event = json.loads(line)
            input_event_count += 1
            location_id = event_location_id(event)
            if not location_id or has_usable_coordinates(event):
                continue
            if clean_text(event.get("source_name")).lower() != "phenomenainon_updb":
                continue
            unmapped_updb_with_location_id_count += 1
            location = location_lookup.get(location_id)
            rejection = rejection_for_event_location(event, location)
            if rejection:
                rejected[rejection] = rejected.get(rejection, 0) + 1
                continue
            assert location is not None
            candidates.append(candidate_row(event, location))

    return {
        "schema_version": 1,
        "report_policy": "updb_location_id_mapping_candidates_report_only",
        "canonical_outputs_mutated": False,
        "geocoding_performed": False,
        "inputs": {
            "deduped_events": str(input_path),
            "updb_sql_gz": str(updb_sql_gz),
        },
        "input_event_count": input_event_count,
        "needed_location_id_count": len(location_ids),
        "lookup_location_id_count": len(location_lookup),
        "unmapped_updb_with_location_id_count": unmapped_updb_with_location_id_count,
        "candidate_event_count": len(candidates),
        "rejected_event_counts": dict(sorted(rejected.items())),
        "candidates": candidates,
        "notes": [
            "Candidates are event-specific and keyed by canonical_event_id.",
            "Only coordinate-bearing UPDB api.location rows are used.",
            "The event city and country must agree with the UPDB location lookup row.",
            "No network geocoding is performed and canonical data is not mutated.",
        ],
    }


def collect_needed_location_ids(input_path: Path) -> set[str]:
    ids: set[str] = set()
    with input_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            event = json.loads(line)
            if has_usable_coordinates(event):
                continue
            location_id = event_location_id(event)
            if location_id and clean_text(event.get("source_name")).lower() == "phenomenainon_updb":
                ids.add(location_id)
    return ids


def load_updb_locations(path: Path, wanted_ids: set[str]) -> dict[str, dict[str, Any]]:
    if not wanted_ids:
        return {}
    locations: dict[str, dict[str, Any]] = {}
    in_copy = False
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith("COPY api.location "):
                in_copy = True
                continue
            if not in_copy:
                continue
            if line.startswith("\\."):
                break
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 11 or parts[0] not in wanted_ids:
                continue
            locations[parts[0]] = {
                "location_id": parts[0],
                "city": sql_text(parts[1]),
                "district": sql_text(parts[2]),
                "country": sql_text(parts[3]),
                "water": sql_text(parts[4]),
                "other": sql_text(parts[5]),
                "lat": parse_float(sql_text(parts[6])),
                "lon": parse_float(sql_text(parts[7])),
                "geoname_id": sql_text(parts[8]),
                "population": parse_int(sql_text(parts[9])),
                "fclass": sql_text(parts[10]),
            }
    return locations


def rejection_for_event_location(event: dict[str, Any], location: dict[str, Any] | None) -> str:
    if location is None:
        return "missing_updb_location_lookup"
    if location["lat"] is None or location["lon"] is None:
        return "missing_coordinates"
    if not (-90 <= location["lat"] <= 90 and -180 <= location["lon"] <= 180):
        return "invalid_coordinates"
    event_country = normalize_place_token(event.get("country"))
    location_country = normalize_place_token(location.get("country"))
    if event_country and location_country and event_country != location_country:
        return "country_mismatch"
    event_city = normalize_place_token(event.get("city"))
    location_city = normalize_place_token(location.get("city"))
    if event_city and location_city and event_city != location_city:
        return "city_mismatch"
    if not location_city and not normalize_place_token(location.get("water")) and not normalize_place_token(location.get("other")):
        return "empty_lookup_place"
    return ""


def candidate_row(event: dict[str, Any], location: dict[str, Any]) -> dict[str, Any]:
    city = clean_text(location.get("city"))
    district = clean_text(location.get("district"))
    country = clean_text(location.get("country"))
    name = city or clean_text(location.get("water")) or clean_text(location.get("other"))
    confidence = "high" if clean_text(location.get("fclass")) == "P" and clean_text(location.get("geoname_id")) else "medium"
    return {
        "canonical_event_id": clean_text(event.get("canonical_event_id")),
        "query": normalize_query(best_location_text(event)),
        "confidence": confidence,
        "candidate_count": 1,
        "name": name,
        "lat": location["lat"],
        "lon": location["lon"],
        "country_code": country,
        "admin1": district,
        "population": location.get("population") if location.get("population") is not None else "",
        "timezone": "",
        "location_precision": "city" if city else "site",
        "updb_location_id": location["location_id"],
        "updb_geoname_id": location.get("geoname_id") or "",
        "updb_fclass": location.get("fclass") or "",
        "decision": "accepted_updb_location_id_city_country_match",
        "display_name": ", ".join(part for part in [name, district, country] if part),
    }


def event_location_id(event: dict[str, Any]) -> str:
    raw_fields = event.get("raw_fields") if isinstance(event.get("raw_fields"), dict) else {}
    raw_source_row = event.get("raw_source_row") if isinstance(event.get("raw_source_row"), dict) else {}
    for value in [raw_fields.get("location"), raw_source_row.get("location")]:
        text = clean_text(value)
        if re.fullmatch(r"\d+", text):
            return text
    return ""


def normalize_place_token(value: Any) -> str:
    text = clean_text(value).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def sql_text(value: str) -> str:
    return "" if value == "\\N" else value


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def parse_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result else None


def parse_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "canonical_event_id",
        "query",
        "confidence",
        "candidate_count",
        "name",
        "lat",
        "lon",
        "country_code",
        "admin1",
        "population",
        "timezone",
        "location_precision",
        "updb_location_id",
        "updb_geoname_id",
        "updb_fclass",
        "decision",
        "display_name",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--updb-sql-gz", type=Path, default=DEFAULT_UPDB_SQL_GZ)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = summarize_updb_location_id_mapping_candidates(
        input_path=args.input,
        updb_sql_gz=args.updb_sql_gz,
    )
    report["outputs"] = {"json": str(args.output_json), "csv": str(args.output_csv)}
    write_json(args.output_json, report)
    write_csv(args.output_csv, report["candidates"])
    print(
        json.dumps(
            {
                "json": str(args.output_json),
                "csv": str(args.output_csv),
                "candidate_event_count": report["candidate_event_count"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
