"""Summarize suspicious exact/source coordinate rows after coordinate sanity fixes.

This is report-only triage. It scans a preview sidecar, finds exact/source
coordinate rows that still fall outside their declared country polygon, and
writes ranked JSON/CSV summaries for follow-up review.
"""

from __future__ import annotations

import argparse
import csv
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


DEFAULT_INPUT = Path("data/canonical_preview_mapping_enrichment_geonames_top5000_coordinate_sane/deduped_events.jsonl")
DEFAULT_COUNTRIES = Path("static_bundle/data/world_countries.geojson")
DEFAULT_JSON = Path("data/reports/coordinate_sanity_suspicious_summary.json")
DEFAULT_CSV = Path("data/reports/coordinate_sanity_suspicious_summary.csv")
DEFAULT_EXAMPLES_CSV = Path("data/reports/coordinate_sanity_suspicious_examples.csv")


def summarize_coordinate_sanity_suspicious(
    *,
    input_path: Path,
    countries_geojson: Path,
    json_output: Path,
    csv_output: Path,
    examples_output: Path,
    example_limit: int = 500,
) -> dict[str, Any]:
    country_index = load_country_index(countries_geojson)
    total_events = 0
    checked_events = 0
    suspicious_events = 0
    grouped: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    examples: list[dict[str, Any]] = []

    with input_path.open("r", encoding="utf-8") as source:
        for line in source:
            if not line.strip():
                continue
            total_events += 1
            event = json.loads(line)
            coordinate_source = clean_text(event.get("coordinate_source"))
            if coordinate_source not in EXACT_COORDINATE_SOURCES:
                continue
            lat = parse_float(event.get("lat"))
            lon = parse_float(event.get("lon"))
            if lat is None or lon is None:
                continue
            country_name = inferred_country_name(event)
            if not country_name or country_name not in country_index:
                continue
            checked_events += 1
            if point_in_feature(lat, lon, country_index[country_name]):
                continue

            suspicious_events += 1
            raw_fields = event.get("raw_fields") or {}
            source_name = clean_text(event.get("source_name")) or "unknown"
            region = clean_text(raw_fields.get("REGION") or event.get("country")) or "unknown"
            state = clean_text(raw_fields.get("STATE") or event.get("state_province")) or "unknown"
            key = (country_name, source_name, state, region)
            bucket = grouped.setdefault(
                key,
                {
                    "country": country_name,
                    "source_name": source_name,
                    "state_or_region": state,
                    "raw_region": region,
                    "count": 0,
                    "min_lat": lat,
                    "max_lat": lat,
                    "min_lon": lon,
                    "max_lon": lon,
                },
            )
            bucket["count"] += 1
            bucket["min_lat"] = min(bucket["min_lat"], lat)
            bucket["max_lat"] = max(bucket["max_lat"], lat)
            bucket["min_lon"] = min(bucket["min_lon"], lon)
            bucket["max_lon"] = max(bucket["max_lon"], lon)
            if len(examples) < example_limit:
                examples.append(example_payload(event, country_name, lat, lon))

    grouped_rows = sorted(grouped.values(), key=lambda row: (-int(row["count"]), row["country"], row["source_name"]))
    report = {
        "schema_version": 1,
        "mode": "report_only",
        "canonical_outputs_mutated": False,
        "inputs": {
            "deduped_events": str(input_path),
            "countries_geojson": str(countries_geojson),
        },
        "outputs": {
            "json": str(json_output),
            "csv": str(csv_output),
            "examples_csv": str(examples_output),
        },
        "total_events": total_events,
        "checked_exact_source_coordinate_events": checked_events,
        "suspicious_event_count": suspicious_events,
        "group_count": len(grouped_rows),
        "top_groups": grouped_rows[:50],
        "notes": [
            "Rows are exact/source coordinate events that remain outside their declared country after the coordinate sanity pass.",
            "This report does not mutate canonical data or preview sidecars.",
        ],
    }
    write_json(json_output, report)
    write_summary_csv(csv_output, grouped_rows)
    write_examples_csv(examples_output, examples)
    return report


def example_payload(event: dict[str, Any], country_name: str, lat: float, lon: float) -> dict[str, Any]:
    return {
        "canonical_event_id": event.get("canonical_event_id"),
        "source_name": event.get("source_name"),
        "source_row_number": event.get("source_row_number"),
        "source_native_id": event.get("source_native_id"),
        "date": event.get("sort_date_iso") or event.get("date_iso") or event.get("date_raw") or event.get("date"),
        "sort_date_iso": event.get("sort_date_iso"),
        "date_raw": event.get("date_raw"),
        "location_raw": event.get("location_raw"),
        "declared_country": country_name,
        "lat": lat,
        "lon": lon,
        "coordinate_source": event.get("coordinate_source"),
    }


def write_summary_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["country", "source_name", "state_or_region", "raw_region", "count", "min_lat", "max_lat", "min_lon", "max_lon"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_examples_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "canonical_event_id",
        "source_name",
        "source_row_number",
        "source_native_id",
        "date",
        "sort_date_iso",
        "date_raw",
        "location_raw",
        "declared_country",
        "lat",
        "lon",
        "coordinate_source",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--countries-geojson", type=Path, default=DEFAULT_COUNTRIES)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--examples-output", type=Path, default=DEFAULT_EXAMPLES_CSV)
    parser.add_argument("--example-limit", type=int, default=500)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = summarize_coordinate_sanity_suspicious(
        input_path=args.input,
        countries_geojson=args.countries_geojson,
        json_output=args.json_output,
        csv_output=args.csv_output,
        examples_output=args.examples_output,
        example_limit=args.example_limit,
    )
    print(json.dumps({
        "json": report["outputs"]["json"],
        "csv": report["outputs"]["csv"],
        "examples_csv": report["outputs"]["examples_csv"],
        "suspicious_event_count": report["suspicious_event_count"],
        "group_count": report["group_count"],
        "canonical_outputs_mutated": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
