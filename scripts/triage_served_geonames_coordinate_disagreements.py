"""Triage served GeoNames coordinate disagreements into review lanes.

The served disagreement report is intentionally broad and noisy. A same-name
GeoNames hit can be the wrong duplicate place, such as a Maryland mountain
matching an Alaska mountain. This script does not repair coordinates; it makes
the queue actionable by separating likely GeoNames false matches from rows that
may deserve deeper coordinate review.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

from scripts.apply_coordinate_sanity_preview import clean_text, write_json
from scripts.build_high_confidence_coordinate_disagreement_packet import (
    AUSTRALIA_COUNTRY_NAMES,
    CANADA_COUNTRY_NAMES,
    US_COUNTRY_NAMES,
    admin_tokens_from_location,
    normalize_admin_code,
)


DEFAULT_INPUT = Path("data/reports/served_geonames_coordinate_disagreements_v111.csv")
DEFAULT_JSON = Path("data/reports/served_geonames_coordinate_disagreement_triage_v111.json")
DEFAULT_OUTPUT_DIR = Path("data/reports")

ADMIN_COUNTRIES = US_COUNTRY_NAMES | CANADA_COUNTRY_NAMES | AUSTRALIA_COUNTRY_NAMES


def triage_served_geonames_coordinate_disagreements(
    *,
    input_csv: Path,
    json_output: Path,
    output_dir: Path,
) -> dict[str, Any]:
    rows = read_rows(input_csv)
    triaged = [triage_row(row) for row in rows]
    lanes: dict[str, list[dict[str, Any]]] = {}
    for row in triaged:
        lanes.setdefault(row["triage_lane"], []).append(row)
    for lane_rows in lanes.values():
        lane_rows.sort(key=sort_key)

    outputs: dict[str, str] = {}
    suffix = output_suffix(json_output)
    for lane, lane_rows in sorted(lanes.items()):
        path = output_dir / f"served_geonames_coordinate_disagreement_{lane}_{suffix}.csv"
        write_rows(path, lane_rows)
        outputs[lane] = str(path)

    report = {
        "schema_version": 1,
        "mode": "report_only",
        "triage_policy": "served_geonames_coordinate_disagreement_review_lanes_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "inputs": {
            "input_csv": str(input_csv),
        },
        "outputs": {
            "json": str(json_output),
            **outputs,
        },
        "input_row_count": len(rows),
        "lane_counts": {lane: len(lane_rows) for lane, lane_rows in sorted(lanes.items())},
        "lane_summaries": {
            lane: lane_summary(lane_rows)
            for lane, lane_rows in sorted(lanes.items())
        },
        "notes": [
            "Report-only: no canonical, static, preview, or deployment files are mutated.",
            "geonames_admin_conflict rows are usually wrong GeoNames duplicate-place matches, not safe coordinate repairs.",
            "admin_matched_review rows still require stronger evidence before any repair path.",
            "international_or_no_admin_review rows need country-specific logic, mechanical transform evidence, or manual review.",
        ],
    }
    write_json(json_output, report)
    return report


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def triage_row(row: dict[str, str]) -> dict[str, Any]:
    country = clean_text(row.get("country"))
    location_raw = clean_text(row.get("location_raw"))
    next_row: dict[str, Any] = dict(row)
    admin_tokens = sorted(admin_tokens_from_location(location_raw, country))
    geonames_admin = normalize_admin_code(clean_text(row.get("geonames_admin1")), country)
    next_row["admin_tokens"] = ";".join(admin_tokens)
    next_row["geonames_admin_normalized"] = geonames_admin

    if country in ADMIN_COUNTRIES:
        if not admin_tokens:
            next_row["triage_lane"] = "admin_country_missing_text_admin"
            next_row["triage_reason"] = "text_has_no_supported_admin_token"
        elif geonames_admin in admin_tokens:
            if len(admin_tokens) == 1:
                next_row["triage_lane"] = "admin_matched_review"
                next_row["triage_reason"] = "single_text_admin_token_matches_geonames_admin"
            else:
                next_row["triage_lane"] = "admin_ambiguous_review"
                next_row["triage_reason"] = "multiple_text_admin_tokens_include_geonames_admin"
        else:
            next_row["triage_lane"] = "geonames_admin_conflict"
            next_row["triage_reason"] = "text_admin_token_conflicts_with_geonames_admin"
    else:
        next_row["triage_lane"] = "international_or_no_admin_review"
        next_row["triage_reason"] = "no_supported_admin_token_policy_for_country"
    return next_row


def output_suffix(path: Path) -> str:
    match = re.search(r"(v\d+)(?:$|[^0-9])", path.stem)
    return match.group(1) if match else "current"


def sort_key(row: dict[str, Any]) -> tuple[float, str, str, str]:
    try:
        distance = float(row.get("distance_km") or 0)
    except ValueError:
        distance = 0.0
    return (
        -distance,
        clean_text(row.get("country")),
        clean_text(row.get("location_raw")),
        clean_text(row.get("event_id")),
    )


def lane_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "count": len(rows),
        "country_counts": count_by(rows, "country"),
        "source_counts": count_by(rows, "source"),
        "feature_class_counts": count_by(rows, "geonames_feature_class"),
        "top_examples": rows[:25],
    }


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = clean_text(row.get(key)) or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        fieldnames = list(rows[0].keys())
    else:
        fieldnames = ["event_id", "location_raw", "country", "triage_lane", "triage_reason"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = triage_served_geonames_coordinate_disagreements(
        input_csv=args.input_csv,
        json_output=args.json_output,
        output_dir=args.output_dir,
    )
    print(
        json.dumps(
            {
                "json": report["outputs"]["json"],
                "input_row_count": report["input_row_count"],
                "lane_counts": report["lane_counts"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
