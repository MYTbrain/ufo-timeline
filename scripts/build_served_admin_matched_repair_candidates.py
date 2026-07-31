"""Build report-only repair candidates from served admin-matched disagreements.

The served GeoNames disagreement lane is still noisy: matching the same name in
the same state/province can still select the wrong duplicate feature. This
script only promotes rows where the current served coordinate contradicts broad
declared-admin bounds and the GeoNames replacement falls inside those bounds.

No canonical, static, preview, or deployment artifacts are mutated.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from scripts.apply_coordinate_residual_risk_preview import CANADIAN_PROVINCE_REVIEW_BOUNDS
from scripts.apply_coordinate_sanity_preview import clean_text, parse_float, write_json
from scripts.apply_jurisdiction_coordinate_repair_preview import US_STATE_BOUNDS
from scripts.build_coordinate_admin_matched_repair_candidates import AUSTRALIA_ADMIN_BOUNDS
from scripts.build_high_confidence_coordinate_disagreement_packet import (
    AUSTRALIA_COUNTRY_NAMES,
    CANADA_COUNTRY_NAMES,
    US_COUNTRY_NAMES,
)


DEFAULT_INPUT = Path("data/reports/served_geonames_coordinate_disagreement_admin_matched_review_v112.csv")
DEFAULT_JSON = Path("data/reports/served_admin_matched_repair_candidates_v112.json")
DEFAULT_CSV = Path("data/reports/served_admin_matched_repair_candidates_v112.csv")

SUPPORTED_FEATURE_CLASSES = {"P", "S", "T", "L"}


def build_served_admin_matched_repair_candidates(
    *,
    input_csv: Path,
    json_output: Path,
    csv_output: Path,
) -> dict[str, Any]:
    input_rows = read_rows(input_csv)
    rows = [classify_row(row) for row in input_rows]
    rows.sort(key=action_sort_key)
    write_rows(csv_output, rows)

    report = {
        "schema_version": 1,
        "mode": "report_only",
        "candidate_policy": "served_admin_matched_coordinate_repair_candidates_report_only",
        "canonical_outputs_mutated": False,
        "static_outputs_mutated": False,
        "deployment_outputs_mutated": False,
        "human_review_required_before_apply": True,
        "inputs": {
            "admin_matched_csv": str(input_csv),
        },
        "outputs": {
            "json": str(json_output),
            "csv": str(csv_output),
        },
        "input_row_count": len(input_rows),
        "candidate_count": len(rows),
        "action_counts": count_by(rows, "recommended_action"),
        "reason_counts": count_by(rows, "recommendation_reason"),
        "country_counts": count_by(rows, "country"),
        "admin_counts": count_by(rows, "declared_admin"),
        "repair_candidate_examples": [
            row for row in rows if row["recommended_action"] == "served_repair_candidate"
        ][:100],
        "quarantine_candidate_examples": [
            row for row in rows if row["recommended_action"] == "served_quarantine_candidate"
        ][:100],
        "manual_review_examples": [
            row for row in rows if row["recommended_action"] == "manual_review_only"
        ][:100],
        "notes": [
            "Report-only: no canonical, static, preview, or deployment files are mutated.",
            "Rows inside declared broad admin bounds are manual-review-only because duplicate same-name GeoNames features are common.",
            "Repair candidates require a current served coordinate outside declared admin bounds and a GeoNames coordinate inside declared admin bounds.",
            "Canada, Australia, and the United States use broad padded admin bounds as QA gates, not exact political polygons.",
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
    declared_admin = single_admin_token(row)
    bounds = admin_bounds(country, declared_admin)
    feature_class = clean_text(row.get("geonames_feature_class")).upper()
    current_inside = inside_bounds(lat, lon, bounds)
    geonames_inside = inside_bounds(geonames_lat, geonames_lon, bounds)

    if not declared_admin:
        action = "manual_review_only"
        reason = "missing_or_ambiguous_admin_token"
    elif bounds is None:
        action = "manual_review_only"
        reason = "unsupported_admin_bounds"
    elif lat is None or lon is None or geonames_lat is None or geonames_lon is None:
        action = "served_quarantine_candidate"
        reason = "invalid_current_or_geonames_coordinates"
    elif feature_class not in SUPPORTED_FEATURE_CLASSES:
        action = "served_quarantine_candidate"
        reason = "unsupported_geonames_feature_class"
    elif current_inside:
        action = "manual_review_only"
        reason = "current_coordinate_inside_declared_admin_bounds"
    elif geonames_inside:
        action = "served_repair_candidate"
        reason = "current_outside_admin_bounds_geonames_inside_admin_bounds"
    else:
        action = "served_quarantine_candidate"
        reason = "current_and_geonames_outside_declared_admin_bounds"

    return {
        "recommended_action": action,
        "recommendation_reason": reason,
        "event_id": row.get("event_id"),
        "chunk_id": row.get("chunk_id"),
        "detail_index": row.get("detail_index"),
        "source": row.get("source"),
        "date": row.get("date"),
        "location_raw": row.get("location_raw"),
        "country": country,
        "declared_admin": declared_admin,
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
        "current_inside_declared_admin_bounds": current_inside,
        "geonames_inside_declared_admin_bounds": geonames_inside,
        "served_patch_target_ready": bool(row.get("event_id") and row.get("chunk_id") and row.get("detail_index")),
    }


def single_admin_token(row: dict[str, str]) -> str:
    tokens = [token for token in clean_text(row.get("admin_tokens")).split(";") if token]
    return tokens[0] if len(tokens) == 1 else ""


def admin_bounds(country: str, admin: str) -> tuple[float, float, float, float] | None:
    if country in US_COUNTRY_NAMES:
        return US_STATE_BOUNDS.get(admin)
    if country in CANADA_COUNTRY_NAMES:
        return CANADIAN_PROVINCE_REVIEW_BOUNDS.get(admin)
    if country in AUSTRALIA_COUNTRY_NAMES:
        return AUSTRALIA_ADMIN_BOUNDS.get(admin)
    return None


def inside_bounds(
    lat: float | None,
    lon: float | None,
    bounds: tuple[float, float, float, float] | None,
) -> bool | None:
    if lat is None or lon is None or bounds is None:
        return None
    min_lat, max_lat, min_lon, max_lon = bounds
    return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon


def action_sort_key(row: dict[str, Any]) -> tuple[int, float, str, str]:
    rank = {
        "served_repair_candidate": 0,
        "served_quarantine_candidate": 1,
        "manual_review_only": 2,
    }.get(str(row.get("recommended_action")), 99)
    distance = row.get("distance_km")
    if not isinstance(distance, (int, float)):
        distance = 0
    return (
        rank,
        -float(distance),
        clean_text(row.get("country")),
        clean_text(row.get("event_id")),
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
        "event_id",
        "chunk_id",
        "detail_index",
        "source",
        "date",
        "location_raw",
        "country",
        "declared_admin",
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
        "current_inside_declared_admin_bounds",
        "geonames_inside_declared_admin_bounds",
        "served_patch_target_ready",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_served_admin_matched_repair_candidates(
        input_csv=args.input_csv,
        json_output=args.json_output,
        csv_output=args.csv_output,
    )
    print(
        json.dumps(
            {
                "json": report["outputs"]["json"],
                "csv": report["outputs"]["csv"],
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
