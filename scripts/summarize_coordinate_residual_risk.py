"""Rank residual coordinate risk groups after country-polygon repair.

This is report-only triage. It consumes the suspicious-coordinate summary CSV
and separates likely benign polygon/coastal misses from high-priority groups
that still look like wrong-country, wrong-hemisphere, or sign-error failures.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from scripts.apply_coordinate_sanity_preview import BOUNDED_FLIP_LON_RANGES, write_json
from scripts.build_coordinate_quarantine_packet import COUNTRY_REVIEW_BOUNDS


DEFAULT_INPUT = Path("data/reports/coordinate_sanity_suspicious_summary_v36_country_polygon_repair.csv")
DEFAULT_JSON = Path("data/reports/coordinate_residual_risk_v37.json")
DEFAULT_CSV = Path("data/reports/coordinate_residual_risk_v37.csv")

WESTERN_HEMISPHERE_COUNTRIES = {
    "Argentina",
    "Bermuda",
    "Bolivia",
    "Brazil",
    "Canada",
    "Chile",
    "Colombia",
    "Cuba",
    "Dominican Republic",
    "Honduras",
    "Mexico",
    "Peru",
    "Puerto Rico",
    "United States of America",
    "United States Virgin Islands",
    "Uruguay",
    "Venezuela",
}

EASTERN_HEMISPHERE_COUNTRIES = {
    "Austria",
    "Belgium",
    "China",
    "Czech Republic",
    "Denmark",
    "Estonia",
    "Finland",
    "France",
    "Georgia",
    "Germany",
    "Greece",
    "Italy",
    "Japan",
    "Kazakhstan",
    "Norway",
    "Poland",
    "Romania",
    "Russia",
    "Spain",
    "Sweden",
    "Switzerland",
    "Ukraine",
}

REGION_COUNTRY_GROUPS = {
    "US": {"United States of America"},
    "USA": {"Puerto Rico", "United States of America", "United States Virgin Islands"},
    "CN": {"Canada"},
    "CA": {"Cuba", "Dominican Republic", "Honduras", "Mexico", "Puerto Rico"},
    "SA": {"Argentina", "Bolivia", "Brazil", "Chile", "Colombia", "Peru", "Uruguay", "Venezuela"},
    "EU": {
        "Austria",
        "Belgium",
        "Bosnia and Herzegovina",
        "Bulgaria",
        "Croatia",
        "Czech Republic",
        "Denmark",
        "Estonia",
        "Finland",
        "Former Yugoslavia",
        "France",
        "Germany",
        "Greece",
        "Hungary",
        "Ireland",
        "Italy",
        "Kosovo",
        "Latvia",
        "Lithuania",
        "Moldova",
        "Montenegro",
        "North Macedonia",
        "Norway",
        "Poland",
        "Portugal",
        "Romania",
        "Serbia",
        "Slovakia",
        "Slovenia",
        "Spain",
        "Sweden",
        "Switzerland",
        "United Kingdom",
        "Ukraine",
    },
    "AS": {"China", "Japan", "Kazakhstan", "Russia"},
    "AU": {"Australia", "New Zealand", "Papua New Guinea"},
}


def summarize_coordinate_residual_risk(
    *,
    input_path: Path,
    json_output: Path,
    csv_output: Path,
) -> dict[str, Any]:
    rows = [classify_row(row) for row in read_summary_rows(input_path)]
    rows.sort(key=residual_sort_key)

    report = {
        "schema_version": 1,
        "mode": "report_only",
        "canonical_outputs_mutated": False,
        "inputs": {"suspicious_summary_csv": str(input_path)},
        "outputs": {"json": str(json_output), "csv": str(csv_output)},
        "group_count": len(rows),
        "event_count": sum(int(row["count"]) for row in rows),
        "risk_counts": count_by(rows, "risk_level"),
        "reason_counts": count_reason_tokens(rows),
        "top_groups": rows[:80],
        "notes": [
            "This report does not mutate canonical data or preview sidecars.",
            "Critical/high groups are the next safest repair/quarantine targets.",
            "Low-risk groups are usually country polygon/coastal/island false positives and should not be mass-hidden.",
        ],
    }
    write_json(json_output, report)
    write_csv(csv_output, rows)
    return report


def read_summary_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [normalize_row(row) for row in reader]


def normalize_row(row: dict[str, str]) -> dict[str, Any]:
    return {
        "country": row.get("country") or "unknown",
        "source_name": row.get("source_name") or "unknown",
        "state_or_region": row.get("state_or_region") or "unknown",
        "raw_region": row.get("raw_region") or "unknown",
        "count": int(float(row.get("count") or 0)),
        "min_lat": float(row.get("min_lat") or 0),
        "max_lat": float(row.get("max_lat") or 0),
        "min_lon": float(row.get("min_lon") or 0),
        "max_lon": float(row.get("max_lon") or 0),
    }


def classify_row(row: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    country = row["country"]
    raw_region = str(row["raw_region"] or "").upper()
    lon_span = row["max_lon"] - row["min_lon"]
    lat_span = row["max_lat"] - row["min_lat"]

    if region_conflicts_country(raw_region, country):
        reasons.append("raw_region_conflicts_declared_country")
    if country in WESTERN_HEMISPHERE_COUNTRIES and row["max_lon"] > 0:
        reasons.append("positive_longitude_for_western_hemisphere_country")
    if country in EASTERN_HEMISPHERE_COUNTRIES and row["min_lon"] < -20:
        reasons.append("far_negative_longitude_for_eastern_hemisphere_country")
    if lon_span >= 60:
        reasons.append("wide_longitude_span")
    if lat_span >= 45:
        reasons.append("wide_latitude_span")
    if not bbox_inside_review_bounds(row):
        reasons.append("outside_broad_country_review_bounds")

    risk_level = risk_from_reasons(reasons, row["count"])
    recommendation = recommendation_from_risk(risk_level)
    return {
        **row,
        "lon_span": round(lon_span, 6),
        "lat_span": round(lat_span, 6),
        "risk_level": risk_level,
        "risk_reasons": ";".join(reasons) if reasons else "polygon_boundary_or_coastal_review",
        "recommendation": recommendation,
    }


def region_conflicts_country(raw_region: str, country: str) -> bool:
    if not raw_region or raw_region == "UNKNOWN":
        return False
    expected = REGION_COUNTRY_GROUPS.get(raw_region)
    if expected is None:
        return False
    return country not in expected


def bbox_inside_review_bounds(row: dict[str, Any]) -> bool:
    bounds = review_bounds_for_country(row["country"])
    if not bounds:
        return False
    return any(
        row["min_lat"] >= min_lat
        and row["max_lat"] <= max_lat
        and row["min_lon"] >= min_lon
        and row["max_lon"] <= max_lon
        for min_lat, max_lat, min_lon, max_lon in bounds
    )


def review_bounds_for_country(country: str) -> list[tuple[float, float, float, float]]:
    quarantine_bounds = COUNTRY_REVIEW_BOUNDS.get(country)
    if quarantine_bounds is not None:
        min_lat, max_lat = quarantine_bounds["lat"]
        return [(min_lat, max_lat, min_lon, max_lon) for min_lon, max_lon in quarantine_bounds["lon_ranges"]]
    fallback_bounds = BOUNDED_FLIP_LON_RANGES.get(country) or []
    return [
        (bounds["lat"][0], bounds["lat"][1], bounds["lon"][0], bounds["lon"][1])
        for bounds in fallback_bounds
    ]


def risk_from_reasons(reasons: list[str], count: int) -> str:
    reason_set = set(reasons)
    if (
        "raw_region_conflicts_declared_country" in reason_set
        and "outside_broad_country_review_bounds" in reason_set
    ):
        return "critical"
    if "positive_longitude_for_western_hemisphere_country" in reason_set:
        return "critical"
    if "far_negative_longitude_for_eastern_hemisphere_country" in reason_set:
        return "critical"
    if "wide_longitude_span" in reason_set and count >= 10 and has_direct_coordinate_failure_reason(reason_set):
        return "high"
    if "outside_broad_country_review_bounds" in reason_set and count >= 10:
        return "high"
    if "outside_broad_country_review_bounds" in reason_set:
        return "medium"
    if "wide_latitude_span" in reason_set:
        return "medium"
    return "low"


def has_direct_coordinate_failure_reason(reason_set: set[str]) -> bool:
    return bool(
        reason_set
        & {
            "outside_broad_country_review_bounds",
            "positive_longitude_for_western_hemisphere_country",
            "far_negative_longitude_for_eastern_hemisphere_country",
        }
    )


def recommendation_from_risk(risk_level: str) -> str:
    if risk_level == "critical":
        return "repair_or_quarantine_next"
    if risk_level == "high":
        return "inspect_for_batch_repair_or_quarantine"
    if risk_level == "medium":
        return "manual_review"
    return "likely_polygon_coastal_false_positive"


def residual_sort_key(row: dict[str, Any]) -> tuple[int, int, str, str, str]:
    risk_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(row["risk_level"], 9)
    return (risk_rank, -int(row["count"]), row["country"], row["source_name"], row["state_or_region"])


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def count_reason_tokens(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for reason in str(row.get("risk_reasons") or "").split(";"):
            if not reason:
                continue
            counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items()))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "risk_level",
        "recommendation",
        "risk_reasons",
        "country",
        "source_name",
        "state_or_region",
        "raw_region",
        "count",
        "min_lat",
        "max_lat",
        "min_lon",
        "max_lon",
        "lat_span",
        "lon_span",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = summarize_coordinate_residual_risk(
        input_path=args.input,
        json_output=args.json_output,
        csv_output=args.csv_output,
    )
    print(json.dumps({
        "json": report["outputs"]["json"],
        "csv": report["outputs"]["csv"],
        "group_count": report["group_count"],
        "event_count": report["event_count"],
        "risk_counts": report["risk_counts"],
        "canonical_outputs_mutated": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
