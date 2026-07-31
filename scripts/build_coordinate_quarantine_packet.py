"""Build a report-only quarantine packet for remaining suspicious coordinates.

The coordinate sanity pass fixes safe sign errors. This packet classifies the
remaining exact/source coordinate rows that still fall outside their declared
country polygon into:

- likely polygon/coastal false positives, which should usually remain visible
- quarantine candidates, which should not be trusted for map display without
  review

No canonical data or preview sidecars are mutated.
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


DEFAULT_INPUT = Path("data/canonical_preview_mapping_enrichment_geonames_top5000_coordinate_sane_v3/deduped_events.jsonl")
DEFAULT_COUNTRIES = Path("static_bundle/data/world_countries.geojson")
DEFAULT_JSON = Path("data/reports/coordinate_quarantine_packet_v3.json")
DEFAULT_CSV = Path("data/reports/coordinate_quarantine_packet_v3.csv")

COUNTRY_REVIEW_BOUNDS = {
    "Australia": {"lat": (-45.0, -9.0), "lon_ranges": [(112.0, 154.0)]},
    "Austria": {"lat": (46.0, 50.0), "lon_ranges": [(9.0, 18.0)]},
    "Bahamas": {"lat": (20.0, 28.5), "lon_ranges": [(-81.0, -72.0)]},
    "Belgium": {"lat": (49.0, 52.0), "lon_ranges": [(2.0, 7.0)]},
    # Includes source-coded Bermuda Triangle / high-seas records near Bermuda.
    "Bermuda": {"lat": (29.0, 33.0), "lon_ranges": [(-68.0, -56.0)]},
    "Canada": {"lat": (41.0, 84.0), "lon_ranges": [(-142.0, -52.0)]},
    # Includes Chilean Antarctic station/depot records source-coded as CHL.
    "Chile": {"lat": (-67.0, -17.0), "lon_ranges": [(-77.0, -58.0)]},
    "China": {"lat": (18.0, 54.0), "lon_ranges": [(73.0, 136.0)]},
    "Cuba": {"lat": (19.0, 24.0), "lon_ranges": [(-86.0, -73.0)]},
    "Czech Republic": {"lat": (48.0, 52.0), "lon_ranges": [(12.0, 19.0)]},
    "Denmark": {"lat": (54.0, 58.0), "lon_ranges": [(8.0, 13.0)]},
    "Dominican Republic": {"lat": (17.0, 21.0), "lon_ranges": [(-73.0, -68.0)]},
    "Ecuador": {"lat": (-6.0, 2.0), "lon_ranges": [(-82.0, -75.0)]},
    "Egypt": {"lat": (21.0, 32.5), "lon_ranges": [(24.0, 37.0)]},
    "Finland": {"lat": (59.0, 71.0), "lon_ranges": [(20.0, 32.0)]},
    "France": {"lat": (41.0, 52.0), "lon_ranges": [(-6.0, 10.0)]},
    "Germany": {"lat": (47.0, 56.0), "lon_ranges": [(5.0, 16.0)]},
    "Greece": {"lat": (34.0, 42.0), "lon_ranges": [(19.0, 29.0)]},
    "Ireland": {"lat": (51.0, 56.0), "lon_ranges": [(-11.0, -5.0)]},
    "Italy": {"lat": (36.0, 48.0), "lon_ranges": [(6.0, 19.0)]},
    "Israel": {"lat": (29.0, 34.0), "lon_ranges": [(34.0, 36.5)]},
    "Japan": {"lat": (24.0, 46.0), "lon_ranges": [(122.0, 146.0)]},
    "Mexico": {"lat": (14.0, 33.0), "lon_ranges": [(-119.0, -86.0)]},
    "Morocco": {"lat": (21.0, 36.5), "lon_ranges": [(-18.0, -1.0)]},
    "Netherlands": {"lat": (50.0, 54.0), "lon_ranges": [(3.0, 8.0)]},
    "New Zealand": {"lat": (-48.0, -33.0), "lon_ranges": [(165.0, 180.0), (-180.0, -170.0)]},
    "Norway": {"lat": (57.0, 81.0), "lon_ranges": [(4.0, 32.0)]},
    "Papua New Guinea": {"lat": (-12.0, 0.0), "lon_ranges": [(140.0, 158.0)]},
    "Paraguay": {"lat": (-28.0, -19.0), "lon_ranges": [(-63.0, -54.0)]},
    "Poland": {"lat": (48.0, 56.0), "lon_ranges": [(13.0, 25.0)]},
    "Portugal": {"lat": (36.0, 43.0), "lon_ranges": [(-10.0, -6.0)]},
    "Puerto Rico": {"lat": (17.5, 18.7), "lon_ranges": [(-68.5, -65.0)]},
    "Reunion": {"lat": (-22.0, -20.5), "lon_ranges": [(55.0, 56.0)]},
    "Romania": {"lat": (43.0, 49.0), "lon_ranges": [(20.0, 30.0)]},
    "Russia": {"lat": (41.0, 82.0), "lon_ranges": [(19.0, 180.0), (-180.0, -168.0)]},
    "Saudi Arabia": {"lat": (16.0, 33.0), "lon_ranges": [(34.0, 56.0)]},
    "Solomon Islands": {"lat": (-13.0, -5.0), "lon_ranges": [(155.0, 170.0)]},
    "South Africa": {"lat": (-35.0, -22.0), "lon_ranges": [(16.0, 33.5)]},
    "Spain": {"lat": (35.0, 44.0), "lon_ranges": [(-10.0, 4.0)]},
    "Sweden": {"lat": (55.0, 70.0), "lon_ranges": [(10.0, 25.0)]},
    "Switzerland": {"lat": (45.0, 48.5), "lon_ranges": [(5.0, 11.0)]},
    "Tunisia": {"lat": (30.0, 38.5), "lon_ranges": [(7.0, 13.0)]},
    "Ukraine": {"lat": (44.0, 53.0), "lon_ranges": [(22.0, 41.0)]},
    "United Kingdom": {"lat": (49.0, 59.0), "lon_ranges": [(-8.0, 2.0)]},
    "United States of America": {"lat": (18.0, 72.0), "lon_ranges": [(-180.0, -66.0)]},
    "Vietnam": {"lat": (8.0, 24.0), "lon_ranges": [(102.0, 110.0)]},
}


def build_coordinate_quarantine_packet(
    *,
    input_path: Path,
    countries_geojson: Path,
    json_output: Path,
    csv_output: Path,
) -> dict[str, Any]:
    country_index = load_country_index(countries_geojson)
    total_events = 0
    checked_events = 0
    suspicious_events = 0
    rows: list[dict[str, Any]] = []

    with input_path.open("r", encoding="utf-8") as source:
        for line in source:
            if not line.strip():
                continue
            total_events += 1
            event = json.loads(line)
            if clean_text(event.get("coordinate_source")) not in EXACT_COORDINATE_SOURCES:
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
            rows.append(classify_event(event, country_name, lat, lon))

    rows.sort(key=lambda row: (classification_rank(row["quarantine_recommendation"]), row["declared_country"], row["source_name"], row["source_row_number"] or 0))
    summary = {
        "total_events": total_events,
        "checked_exact_source_coordinate_events": checked_events,
        "suspicious_event_count": suspicious_events,
        "quarantine_candidate_count": sum(1 for row in rows if row["quarantine_recommendation"] == "quarantine_until_review"),
        "display_safe_review_count": sum(1 for row in rows if row["quarantine_recommendation"] == "keep_visible_polygon_review"),
        "manual_review_count": sum(1 for row in rows if row["quarantine_recommendation"] == "manual_review"),
        "recommendation_counts": count_by(rows, "quarantine_recommendation"),
        "reason_counts": count_by(rows, "quarantine_reason"),
        "country_counts": count_by(rows, "declared_country"),
        "source_counts": count_by(rows, "source_name"),
    }
    report = {
        "schema_version": 1,
        "mode": "report_only",
        "policy": "coordinate_quarantine_packet_v3",
        "canonical_outputs_mutated": False,
        "preview_outputs_mutated": False,
        "ready_for_apply": False,
        "human_review_required_before_hiding": True,
        "inputs": {
            "deduped_events": str(input_path),
            "countries_geojson": str(countries_geojson),
        },
        "outputs": {
            "json": str(json_output),
            "csv": str(csv_output),
        },
        "summary": summary,
        "top_quarantine_candidates": rows[:100],
        "notes": [
            "This packet does not hide or mutate any events.",
            "quarantine_until_review means the coordinate lies outside broad country review bounds or otherwise remains implausible.",
            "keep_visible_polygon_review means the point is outside the coarse country polygon but inside broad country bounds; many coastal/island rows land here.",
        ],
    }
    write_json(json_output, report)
    write_csv(csv_output, rows)
    return report


def classify_event(event: dict[str, Any], country_name: str, lat: float, lon: float) -> dict[str, Any]:
    bounds = COUNTRY_REVIEW_BOUNDS.get(country_name)
    if bounds is None:
        recommendation = "manual_review"
        reason = "no_country_review_bounds"
    elif point_in_review_bounds(lat, lon, bounds):
        recommendation = "keep_visible_polygon_review"
        reason = "outside_coarse_polygon_but_inside_country_review_bounds"
    else:
        recommendation = "quarantine_until_review"
        reason = "outside_country_review_bounds"
    raw_fields = event.get("raw_fields") or {}
    return {
        "quarantine_recommendation": recommendation,
        "quarantine_reason": reason,
        "canonical_event_id": event.get("canonical_event_id"),
        "source_name": event.get("source_name"),
        "source_row_number": event.get("source_row_number"),
        "source_native_id": event.get("source_native_id"),
        "date": event.get("date"),
        "location_raw": event.get("location_raw"),
        "declared_country": country_name,
        "raw_region": raw_fields.get("REGION") or event.get("country"),
        "raw_state": raw_fields.get("STATE") or event.get("state_province"),
        "lat": lat,
        "lon": lon,
        "coordinate_source": event.get("coordinate_source"),
    }


def point_in_review_bounds(lat: float, lon: float, bounds: dict[str, Any]) -> bool:
    min_lat, max_lat = bounds["lat"]
    if lat < min_lat or lat > max_lat:
        return False
    return any(min_lon <= lon <= max_lon for min_lon, max_lon in bounds["lon_ranges"])


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def classification_rank(value: str) -> int:
    return {
        "quarantine_until_review": 0,
        "manual_review": 1,
        "keep_visible_polygon_review": 2,
    }.get(value, 99)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "quarantine_recommendation",
        "quarantine_reason",
        "canonical_event_id",
        "source_name",
        "source_row_number",
        "source_native_id",
        "date",
        "location_raw",
        "declared_country",
        "raw_region",
        "raw_state",
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_coordinate_quarantine_packet(
        input_path=args.input,
        countries_geojson=args.countries_geojson,
        json_output=args.json_output,
        csv_output=args.csv_output,
    )
    summary = report["summary"]
    print(json.dumps({
        "json": report["outputs"]["json"],
        "csv": report["outputs"]["csv"],
        "quarantine_candidate_count": summary["quarantine_candidate_count"],
        "display_safe_review_count": summary["display_safe_review_count"],
        "manual_review_count": summary["manual_review_count"],
        "canonical_outputs_mutated": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
