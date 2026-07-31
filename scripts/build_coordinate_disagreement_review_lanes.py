"""Split high-confidence coordinate disagreement packet into review lanes.

The high-confidence packet is still too broad to apply directly. This helper
creates narrower review CSVs so the next repair/quarantine decision can start
with the safest rows: US/Canada/Australia rows where the GeoNames candidate
matches the textual admin-region token.

No canonical, preview, static, or deployment artifacts are mutated.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from scripts.apply_coordinate_sanity_preview import clean_text, write_json


DEFAULT_PACKET_CSV = Path("data/reports/high_confidence_coordinate_disagreement_packet_v109.csv")
DEFAULT_JSON = Path("data/reports/coordinate_disagreement_review_lanes_v109.json")
DEFAULT_ADMIN_CSV = Path("data/reports/coordinate_disagreement_admin_matched_v109.csv")
DEFAULT_ADMIN_AMBIGUOUS_CSV = Path("data/reports/coordinate_disagreement_admin_ambiguous_v109.csv")
DEFAULT_INTERNATIONAL_CSV = Path("data/reports/coordinate_disagreement_international_review_v109.csv")


def build_coordinate_disagreement_review_lanes(
    *,
    packet_csv: Path,
    json_output: Path,
    admin_matched_csv: Path,
    admin_ambiguous_csv: Path,
    international_csv: Path,
) -> dict[str, Any]:
    rows = read_rows(packet_csv)
    admin_matched = [
        row for row in rows
        if clean_text(row.get("admin_match_kind")) == "matched"
        and len(admin_tokens(row)) == 1
    ]
    admin_ambiguous = [
        row for row in rows
        if clean_text(row.get("admin_match_kind")) == "matched"
        and len(admin_tokens(row)) != 1
    ]
    international_review = [
        row for row in rows
        if clean_text(row.get("admin_match_kind")) == "not_required"
    ]

    admin_matched.sort(key=review_sort_key)
    admin_ambiguous.sort(key=review_sort_key)
    international_review.sort(key=review_sort_key)

    write_rows(admin_matched_csv, admin_matched)
    write_rows(admin_ambiguous_csv, admin_ambiguous)
    write_rows(international_csv, international_review)

    report = {
        "schema_version": 1,
        "mode": "report_only",
        "lane_policy": "coordinate_disagreement_review_lanes_only",
        "canonical_outputs_mutated": False,
        "inputs": {
            "packet_csv": str(packet_csv),
        },
        "outputs": {
            "json": str(json_output),
            "admin_matched_csv": str(admin_matched_csv),
            "admin_ambiguous_csv": str(admin_ambiguous_csv),
            "international_csv": str(international_csv),
        },
        "input_row_count": len(rows),
        "lanes": {
            "admin_matched": lane_summary(admin_matched, "Safest first review lane: exactly one textual US/Canada/Australia admin token agrees with GeoNames admin1."),
            "admin_ambiguous": lane_summary(admin_ambiguous, "Do not auto-apply: source text contains zero or multiple admin tokens despite a GeoNames admin match."),
            "international_review": lane_summary(international_review, "Broader same-country/same-primary-name review lane without a reliable admin-token match."),
        },
        "notes": [
            "Report-only: no canonical, preview, static, or deployment files are mutated.",
            "The admin_matched lane requires exactly one admin token. Multiple-token rows are kept in admin_ambiguous.",
            "Do not automatically apply the international_review lane; split it further by country/admin evidence first.",
            "The admin_matched lane is safer but still requires a separate preview-apply script and regression checks before changing map artifacts.",
        ],
    }
    write_json(json_output, report)
    return report


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else [
        "canonical_event_id",
        "location_raw",
        "country",
        "admin_match_kind",
        "distance_km",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def admin_tokens(row: dict[str, str]) -> list[str]:
    raw_value = clean_text(row.get("admin_tokens"))
    if not raw_value:
        return []
    return [token for token in raw_value.split(";") if token]


def review_sort_key(row: dict[str, str]) -> tuple[float, str, str, str]:
    try:
        distance = float(row.get("distance_km") or 0)
    except ValueError:
        distance = 0
    return (
        -distance,
        clean_text(row.get("country")),
        clean_text(row.get("location_raw")),
        clean_text(row.get("canonical_event_id")),
    )


def lane_summary(rows: list[dict[str, str]], note: str) -> dict[str, Any]:
    return {
        "count": len(rows),
        "note": note,
        "country_counts": count_by(rows, "country"),
        "source_counts": count_by(rows, "source_name"),
        "top_examples": rows[:25],
    }


def count_by(rows: list[dict[str, str]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = clean_text(row.get(key)) or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet-csv", type=Path, default=DEFAULT_PACKET_CSV)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--admin-matched-csv", type=Path, default=DEFAULT_ADMIN_CSV)
    parser.add_argument("--admin-ambiguous-csv", type=Path, default=DEFAULT_ADMIN_AMBIGUOUS_CSV)
    parser.add_argument("--international-csv", type=Path, default=DEFAULT_INTERNATIONAL_CSV)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_coordinate_disagreement_review_lanes(
        packet_csv=args.packet_csv,
        json_output=args.json_output,
        admin_matched_csv=args.admin_matched_csv,
        admin_ambiguous_csv=args.admin_ambiguous_csv,
        international_csv=args.international_csv,
    )
    print(
        json.dumps(
            {
                "json": report["outputs"]["json"],
                "admin_matched_csv": report["outputs"]["admin_matched_csv"],
                "admin_ambiguous_csv": report["outputs"]["admin_ambiguous_csv"],
                "international_csv": report["outputs"]["international_csv"],
                "input_row_count": report["input_row_count"],
                "admin_matched_count": report["lanes"]["admin_matched"]["count"],
                "admin_ambiguous_count": report["lanes"]["admin_ambiguous"]["count"],
                "international_review_count": report["lanes"]["international_review"]["count"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
