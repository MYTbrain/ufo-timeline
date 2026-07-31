"""Build report-only repair/quarantine candidates from admin-matched coordinates.

This narrows the unambiguous admin-matched coordinate disagreement lane into
candidate actions without rewriting any event corpus:

- repair candidates: current coordinate is outside the declared admin bounds,
  while the matching GeoNames coordinate is inside those bounds;
- quarantine candidates: current coordinate is bad, but the replacement
  candidate still does not pass bounds checks;
- manual review only: distance alone is not enough to prove a bad coordinate.

No canonical, preview, static, or deployment artifacts are mutated.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from scripts.apply_coordinate_sanity_preview import clean_text, parse_float, write_json
from scripts.apply_jurisdiction_coordinate_repair_preview import US_STATE_BOUNDS


DEFAULT_INPUT = Path("data/reports/coordinate_disagreement_admin_matched_v109.csv")
DEFAULT_JSON = Path("data/reports/coordinate_admin_matched_repair_candidates_v109.json")
DEFAULT_CSV = Path("data/reports/coordinate_admin_matched_repair_candidates_v109.csv")

SUPPORTED_FEATURE_CLASSES = {"P", "S", "T", "L"}
US_COUNTRY_NAMES = {"United States of America", "United States", "USA", "US"}
AUSTRALIA_COUNTRY_NAMES = {"Australia"}

# Broad state/territory bounds with intentional padding. These are QA gates for
# impossible placements, not exact political polygons.
AUSTRALIA_ADMIN_BOUNDS = {
    "01": (-36.0, -35.0, 148.0, 150.0),   # ACT
    "02": (-38.5, -28.0, 140.5, 154.5),  # NSW
    "03": (-26.5, -10.0, 129.0, 139.0),  # NT
    "04": (-29.5, -9.0, 137.0, 154.5),   # QLD
    "05": (-38.5, -25.0, 129.0, 141.5),  # SA
    "06": (-44.5, -39.0, 143.0, 149.0),  # TAS
    "07": (-39.5, -33.5, 140.5, 150.5),  # VIC
    "08": (-36.5, -13.0, 112.0, 130.5),  # WA
}


def build_coordinate_admin_matched_repair_candidates(
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
        "candidate_policy": "admin_matched_coordinate_repair_candidates_report_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "ready_for_preview_apply_packet": True,
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
            row for row in rows if row["recommended_action"] == "preview_repair_candidate"
        ][:100],
        "quarantine_candidate_examples": [
            row for row in rows if row["recommended_action"] == "quarantine_candidate"
        ][:100],
        "manual_review_examples": [
            row for row in rows if row["recommended_action"] == "manual_review_only"
        ][:100],
        "notes": [
            "Report-only: no canonical, preview, static, or deployment files are mutated.",
            "Repair candidates require exactly one admin token, current coordinates outside that admin bounds, and GeoNames coordinates inside that admin bounds.",
            "Rows inside declared admin bounds are manual-review-only because same-name GeoNames distance alone can be locality ambiguity.",
            "Australia uses broad state/territory bounds added specifically for this review gate.",
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
        action = "quarantine_candidate"
        reason = "invalid_current_or_geonames_coordinates"
    elif feature_class not in SUPPORTED_FEATURE_CLASSES:
        action = "quarantine_candidate"
        reason = "unsupported_geonames_feature_class"
    elif current_inside:
        action = "manual_review_only"
        reason = "current_coordinate_inside_declared_admin_bounds"
    elif geonames_inside:
        action = "preview_repair_candidate"
        reason = "current_outside_admin_bounds_geonames_inside_admin_bounds"
    else:
        action = "quarantine_candidate"
        reason = "current_and_geonames_outside_declared_admin_bounds"

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
        "suggested_preview_repair_action": suggested_preview_repair_action(country, action),
    }


def single_admin_token(row: dict[str, str]) -> str:
    tokens = [token for token in clean_text(row.get("admin_tokens")).split(";") if token]
    return tokens[0] if len(tokens) == 1 else ""


def admin_bounds(country: str, admin: str) -> tuple[float, float, float, float] | None:
    if country in US_COUNTRY_NAMES:
        return US_STATE_BOUNDS.get(admin)
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


def suggested_preview_repair_action(country: str, action: str) -> str:
    if action != "preview_repair_candidate":
        return ""
    if country in US_COUNTRY_NAMES:
        return "replace_with_same_state_geonames_feature"
    if country in AUSTRALIA_COUNTRY_NAMES:
        return "replace_with_same_australian_admin_geonames_feature"
    return "replace_with_same_admin_geonames_feature"


def action_sort_key(row: dict[str, Any]) -> tuple[int, float, str, str]:
    rank = {
        "preview_repair_candidate": 0,
        "quarantine_candidate": 1,
        "manual_review_only": 2,
    }.get(str(row.get("recommended_action")), 99)
    distance = row.get("distance_km")
    if not isinstance(distance, (int, float)):
        distance = 0
    return (
        rank,
        -float(distance),
        clean_text(row.get("country")),
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
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_coordinate_admin_matched_repair_candidates(
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
                "preview_outputs_written": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
