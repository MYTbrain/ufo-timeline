"""Build report-only country-bound repair candidates for international rows.

This narrows the broad international coordinate-disagreement review lane into
safer action lanes. It does not mutate canonical, preview, static, or
deployment artifacts.

The strongest review lane is:
- current coordinate is outside broad country review bounds, and
- GeoNames candidate coordinate is inside broad country review bounds.

This still remains review-only because broad country bounds are a QA gate, not
proof that a source coordinate is wrong in every historical or route-based case.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from scripts.apply_coordinate_sanity_preview import clean_text, parse_float, write_json
from scripts.check_static_country_coordinate_anomalies import (
    point_in_any_bounds,
    review_bounds_for_country,
)


DEFAULT_INPUT = Path("data/reports/coordinate_disagreement_international_review_v109.csv")
DEFAULT_JSON = Path("data/reports/coordinate_international_country_repair_candidates_v109.json")
DEFAULT_REPAIR_CSV = Path("data/reports/coordinate_international_country_repair_candidates_v109.csv")
DEFAULT_QUARANTINE_CSV = Path("data/reports/coordinate_international_country_quarantine_candidates_v109.csv")
DEFAULT_MANUAL_CSV = Path("data/reports/coordinate_international_country_manual_review_v109.csv")

SUPPORTED_FEATURE_CLASSES = {"P", "S", "T", "L"}


def build_coordinate_international_country_repair_candidates(
    *,
    input_csv: Path,
    json_output: Path,
    repair_csv: Path,
    quarantine_csv: Path,
    manual_csv: Path,
) -> dict[str, Any]:
    input_rows = read_rows(input_csv)
    classified = [classify_row(row) for row in input_rows]
    classified.sort(key=action_sort_key)

    repair_rows = [row for row in classified if row["recommended_action"] == "country_repair_candidate"]
    quarantine_rows = [row for row in classified if row["recommended_action"] == "quarantine_candidate"]
    manual_rows = [row for row in classified if row["recommended_action"] == "manual_review_only"]

    write_rows(repair_csv, repair_rows)
    write_rows(quarantine_csv, quarantine_rows)
    write_rows(manual_csv, manual_rows)

    report = {
        "schema_version": 1,
        "mode": "report_only",
        "candidate_policy": "international_country_bound_coordinate_repair_candidates_report_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "human_review_required_before_apply": True,
        "inputs": {
            "international_review_csv": str(input_csv),
        },
        "outputs": {
            "json": str(json_output),
            "repair_csv": str(repair_csv),
            "quarantine_csv": str(quarantine_csv),
            "manual_csv": str(manual_csv),
        },
        "input_row_count": len(input_rows),
        "candidate_count": len(classified),
        "action_counts": count_by(classified, "recommended_action"),
        "reason_counts": count_by(classified, "recommendation_reason"),
        "country_counts": count_by(classified, "country"),
        "repair_candidate_country_counts": count_by(repair_rows, "country"),
        "quarantine_candidate_country_counts": count_by(quarantine_rows, "country"),
        "manual_review_country_counts": count_by(manual_rows, "country"),
        "repair_candidate_examples": repair_rows[:100],
        "quarantine_candidate_examples": quarantine_rows[:100],
        "manual_review_examples": manual_rows[:100],
        "notes": [
            "Report-only: no canonical, preview, static, or deployment files are mutated.",
            "Country repair candidates require current coordinates outside broad country bounds and GeoNames coordinates inside broad country bounds.",
            "Rows whose current coordinates are already inside broad country bounds remain manual-review-only because locality ambiguity is possible.",
            "Broad country bounds are intentionally padded QA gates, not exact coastlines or administrative polygons.",
            "Apply paths must still verify old lat/lon/source guards before mutating any artifact.",
        ],
    }
    write_json(json_output, report)
    return report


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def classify_row(row: dict[str, str]) -> dict[str, Any]:
    lat = parse_float(row.get("lat"))
    lon = parse_float(row.get("lon"))
    geonames_lat = parse_float(row.get("geonames_lat"))
    geonames_lon = parse_float(row.get("geonames_lon"))
    country = clean_text(row.get("country"))
    feature_class = clean_text(row.get("geonames_feature_class")).upper()
    bounds = review_bounds_for_country(country)
    current_inside = inside_country_bounds(lat, lon, bounds)
    geonames_inside = inside_country_bounds(geonames_lat, geonames_lon, bounds)

    if not bounds:
        action = "manual_review_only"
        reason = "unsupported_country_bounds"
    elif lat is None or lon is None or geonames_lat is None or geonames_lon is None:
        action = "quarantine_candidate"
        reason = "invalid_current_or_geonames_coordinates"
    elif feature_class not in SUPPORTED_FEATURE_CLASSES:
        action = "quarantine_candidate"
        reason = "unsupported_geonames_feature_class"
    elif current_inside:
        action = "manual_review_only"
        reason = "current_coordinate_inside_broad_country_bounds"
    elif geonames_inside:
        action = "country_repair_candidate"
        reason = "current_outside_country_bounds_geonames_inside_country_bounds"
    else:
        action = "quarantine_candidate"
        reason = "current_and_geonames_outside_broad_country_bounds"

    return {
        "recommended_action": action,
        "recommendation_reason": reason,
        "canonical_event_id": row.get("canonical_event_id"),
        "event_id": row.get("event_id"),
        "source_name": row.get("source_name"),
        "source_row_number": row.get("source_row_number"),
        "source_native_id": row.get("source_native_id"),
        "date": row.get("date"),
        "location_raw": row.get("location_raw"),
        "country": country,
        "coordinate_source": row.get("coordinate_source"),
        "location_precision": row.get("location_precision"),
        "old_lat": lat,
        "old_lon": lon,
        "new_lat": geonames_lat,
        "new_lon": geonames_lon,
        "geonames_name": row.get("geonames_name"),
        "geonames_id": row.get("geonames_id"),
        "geonames_feature_class": row.get("geonames_feature_class"),
        "geonames_feature_code": row.get("geonames_feature_code"),
        "geonames_admin1": row.get("geonames_admin1"),
        "distance_km": parse_float(row.get("distance_km")),
        "primary_place_key": row.get("primary_place_key"),
        "current_inside_broad_country_bounds": current_inside,
        "geonames_inside_broad_country_bounds": geonames_inside,
        "suggested_preview_repair_action": (
            "replace_with_same_country_geonames_feature"
            if action == "country_repair_candidate"
            else ""
        ),
    }


def inside_country_bounds(
    lat: float | None,
    lon: float | None,
    bounds: list[tuple[float, float, float, float]],
) -> bool | None:
    if lat is None or lon is None or not bounds:
        return None
    return point_in_any_bounds(lat, lon, bounds)


def action_sort_key(row: dict[str, Any]) -> tuple[int, str, float, str, str]:
    rank = {
        "country_repair_candidate": 0,
        "quarantine_candidate": 1,
        "manual_review_only": 2,
    }.get(str(row.get("recommended_action")), 99)
    distance = row.get("distance_km")
    if not isinstance(distance, (int, float)):
        distance = 0
    return (
        rank,
        clean_text(row.get("country")),
        -float(distance),
        clean_text(row.get("location_raw")),
        clean_text(row.get("canonical_event_id")),
    )


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = clean_text(row.get(key)) or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "recommended_action",
        "recommendation_reason",
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
        "old_lat",
        "old_lon",
        "new_lat",
        "new_lon",
        "geonames_name",
        "geonames_id",
        "geonames_feature_class",
        "geonames_feature_code",
        "geonames_admin1",
        "distance_km",
        "primary_place_key",
        "current_inside_broad_country_bounds",
        "geonames_inside_broad_country_bounds",
        "suggested_preview_repair_action",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--repair-csv", type=Path, default=DEFAULT_REPAIR_CSV)
    parser.add_argument("--quarantine-csv", type=Path, default=DEFAULT_QUARANTINE_CSV)
    parser.add_argument("--manual-csv", type=Path, default=DEFAULT_MANUAL_CSV)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_coordinate_international_country_repair_candidates(
        input_csv=args.input_csv,
        json_output=args.json_output,
        repair_csv=args.repair_csv,
        quarantine_csv=args.quarantine_csv,
        manual_csv=args.manual_csv,
    )
    print(
        json.dumps(
            {
                "json": report["outputs"]["json"],
                "repair_csv": report["outputs"]["repair_csv"],
                "quarantine_csv": report["outputs"]["quarantine_csv"],
                "manual_csv": report["outputs"]["manual_csv"],
                "input_row_count": report["input_row_count"],
                "action_counts": report["action_counts"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
