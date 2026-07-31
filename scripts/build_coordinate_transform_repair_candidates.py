"""Build report-only coordinate transform repair candidates.

This identifies rows where the source coordinate appears to have a mechanical
coordinate transform error, such as longitude sign flip or latitude/longitude
swap. The output is review-only and does not mutate canonical, static, or
deployment artifacts.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

from scripts.apply_coordinate_sanity_preview import clean_text, parse_float, write_json


DEFAULT_INPUT = Path("data/reports/coordinate_disagreement_international_review_v109.csv")
DEFAULT_JSON = Path("data/reports/coordinate_transform_repair_candidates_v109.json")
DEFAULT_CSV = Path("data/reports/coordinate_transform_repair_candidates_v109.csv")

SUPPORTED_FEATURE_CLASSES = {"P", "S", "T", "L"}
TRANSFORM_NAMES = (
    "lon_sign_flip",
    "lat_sign_flip",
    "both_sign_flip",
    "swap",
    "swap_lon_sign_flip",
    "swap_lat_sign_flip",
    "swap_both_sign_flip",
)


def build_coordinate_transform_repair_candidates(
    *,
    input_csv: Path,
    json_output: Path,
    csv_output: Path,
    max_transformed_distance_km: float = 50.0,
    min_original_distance_km: float = 100.0,
    min_improvement_ratio: float = 3.0,
) -> dict[str, Any]:
    input_rows = read_rows(input_csv)
    rows = [
        candidate
        for row in input_rows
        if (
            candidate := classify_transform_candidate(
                row,
                max_transformed_distance_km=max_transformed_distance_km,
                min_original_distance_km=min_original_distance_km,
                min_improvement_ratio=min_improvement_ratio,
            )
        )
    ]
    rows.sort(key=sort_key)
    write_rows(csv_output, rows)

    report = {
        "schema_version": 1,
        "mode": "report_only",
        "candidate_policy": "coordinate_transform_repair_candidates_report_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "human_review_required_before_apply": True,
        "inputs": {
            "input_csv": str(input_csv),
        },
        "outputs": {
            "json": str(json_output),
            "csv": str(csv_output),
        },
        "thresholds": {
            "max_transformed_distance_km": max_transformed_distance_km,
            "min_original_distance_km": min_original_distance_km,
            "min_improvement_ratio": min_improvement_ratio,
        },
        "input_row_count": len(input_rows),
        "candidate_count": len(rows),
        "transform_counts": count_by(rows, "transform"),
        "country_counts": count_by(rows, "country"),
        "source_counts": count_by(rows, "source_name"),
        "examples": rows[:100],
        "notes": [
            "Report-only: no canonical, preview, static, or deployment files are mutated.",
            "Candidates require a supported GeoNames feature class, a large original disagreement, and a simple coordinate transform that lands near GeoNames.",
            "This detects mechanical coordinate-entry errors such as longitude sign flips and latitude/longitude swaps.",
            "Apply paths must still verify old lat/lon/source guards before mutating any artifact.",
        ],
    }
    write_json(json_output, report)
    return report


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def classify_transform_candidate(
    row: dict[str, str],
    *,
    max_transformed_distance_km: float,
    min_original_distance_km: float,
    min_improvement_ratio: float,
) -> dict[str, Any] | None:
    lat = parse_float(row.get("lat"))
    lon = parse_float(row.get("lon"))
    geonames_lat = parse_float(row.get("geonames_lat"))
    geonames_lon = parse_float(row.get("geonames_lon"))
    if lat is None or lon is None or geonames_lat is None or geonames_lon is None:
        return None

    feature_class = clean_text(row.get("geonames_feature_class")).upper()
    if feature_class not in SUPPORTED_FEATURE_CLASSES:
        return None

    original_distance = haversine_km(lat, lon, geonames_lat, geonames_lon)
    if original_distance < min_original_distance_km:
        return None

    best = best_transform(lat, lon, geonames_lat, geonames_lon)
    if best is None:
        return None
    transform_name, transformed_lat, transformed_lon, transformed_distance = best
    if transformed_distance > max_transformed_distance_km:
        return None
    if original_distance / max(transformed_distance, 0.001) < min_improvement_ratio:
        return None

    return {
        "recommended_action": "coordinate_transform_repair_candidate",
        "recommendation_reason": "simple_coordinate_transform_matches_geonames",
        "canonical_event_id": row.get("canonical_event_id"),
        "event_id": row.get("event_id"),
        "chunk_id": row.get("chunk_id"),
        "detail_index": row.get("detail_index"),
        "source_name": row.get("source_name") or row.get("source"),
        "source_row_number": row.get("source_row_number"),
        "source_native_id": row.get("source_native_id"),
        "date": row.get("date"),
        "location_raw": row.get("location_raw"),
        "country": clean_text(row.get("country")),
        "coordinate_source": row.get("coordinate_source"),
        "location_precision": row.get("location_precision"),
        "old_lat": lat,
        "old_lon": lon,
        "transformed_lat": transformed_lat,
        "transformed_lon": transformed_lon,
        "new_lat": geonames_lat,
        "new_lon": geonames_lon,
        "transform": transform_name,
        "original_distance_km": round(original_distance, 3),
        "transformed_distance_km": round(transformed_distance, 3),
        "distance_improvement_ratio": round(original_distance / max(transformed_distance, 0.001), 3),
        "geonames_name": row.get("geonames_name"),
        "geonames_id": row.get("geonames_id"),
        "geonames_feature_class": row.get("geonames_feature_class"),
        "geonames_feature_code": row.get("geonames_feature_code"),
        "geonames_admin1": row.get("geonames_admin1"),
        "suggested_preview_repair_action": f"replace_with_geonames_after_{transform_name}_evidence",
    }


def best_transform(
    lat: float,
    lon: float,
    target_lat: float,
    target_lon: float,
) -> tuple[str, float, float, float] | None:
    best: tuple[str, float, float, float] | None = None
    for name, transformed_lat, transformed_lon in transformed_coordinates(lat, lon):
        distance = haversine_km(transformed_lat, transformed_lon, target_lat, target_lon)
        if best is None or distance < best[3]:
            best = (name, transformed_lat, transformed_lon, distance)
    return best


def transformed_coordinates(lat: float, lon: float) -> list[tuple[str, float, float]]:
    candidates = [
        ("lon_sign_flip", lat, -lon),
        ("lat_sign_flip", -lat, lon),
        ("both_sign_flip", -lat, -lon),
        ("swap", lon, lat),
        ("swap_lon_sign_flip", lon, -lat),
        ("swap_lat_sign_flip", -lon, lat),
        ("swap_both_sign_flip", -lon, -lat),
    ]
    return [
        (name, t_lat, t_lon)
        for name, t_lat, t_lon in candidates
        if -90.0 <= t_lat <= 90.0 and -180.0 <= t_lon <= 180.0
    ]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * radius_km * math.asin(min(1.0, math.sqrt(a)))


def sort_key(row: dict[str, Any]) -> tuple[str, float, str, str]:
    return (
        clean_text(row.get("country")),
        float(row.get("transformed_distance_km") or 0),
        clean_text(row.get("transform")),
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
        "chunk_id",
        "detail_index",
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
        "transformed_lat",
        "transformed_lon",
        "new_lat",
        "new_lon",
        "transform",
        "original_distance_km",
        "transformed_distance_km",
        "distance_improvement_ratio",
        "geonames_name",
        "geonames_id",
        "geonames_feature_class",
        "geonames_feature_code",
        "geonames_admin1",
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
    parser.add_argument("--max-transformed-distance-km", type=float, default=50.0)
    parser.add_argument("--min-original-distance-km", type=float, default=100.0)
    parser.add_argument("--min-improvement-ratio", type=float, default=3.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_coordinate_transform_repair_candidates(
        input_csv=args.input_csv,
        json_output=args.json_output,
        csv_output=args.csv_output,
        max_transformed_distance_km=args.max_transformed_distance_km,
        min_original_distance_km=args.min_original_distance_km,
        min_improvement_ratio=args.min_improvement_ratio,
    )
    print(
        json.dumps(
            {
                "json": report["outputs"]["json"],
                "csv": report["outputs"]["csv"],
                "input_row_count": report["input_row_count"],
                "candidate_count": report["candidate_count"],
                "transform_counts": report["transform_counts"],
                "country_counts": report["country_counts"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
