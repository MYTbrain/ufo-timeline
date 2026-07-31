"""Summarize replacement-audit components into bounded review sublanes."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


DEFAULT_AUDIT_CSV = Path("data/reports/manual_review_ai_after_time_norm_replacement_audit.csv")
DEFAULT_OUTPUT_JSON = Path("data/reports/manual_review_ai_after_time_norm_replacement_audit_sublanes.json")
DEFAULT_OUTPUT_CSV = Path("data/reports/manual_review_ai_after_time_norm_replacement_audit_sublanes.csv")

REPORT_POLICY = "manual_review_replacement_audit_sublane_summary_v1"


def summarize_manual_review_replacement_audit_sublanes(
    *,
    audit_csv_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = read_csv(audit_csv_path)
    sublanes: dict[str, dict[str, Any]] = {}
    for row in rows:
        sublane = classify_sublane(row)
        summary = sublanes.setdefault(
            sublane,
            {
                "sublane": sublane,
                "component_count": 0,
                "projected_event_reduction": 0,
                "risk_counts": {},
                "flag_counts": {},
                "top_component_ids": [],
            },
        )
        summary["component_count"] += 1
        summary["projected_event_reduction"] += max(0, safe_int(row.get("component_event_count")) - 1)
        risk = clean_text(row.get("risk_level")) or "unknown"
        summary["risk_counts"][risk] = summary["risk_counts"].get(risk, 0) + 1
        for flag in split_pipe(row.get("risk_flags")):
            summary["flag_counts"][flag] = summary["flag_counts"].get(flag, 0) + 1
        if len(summary["top_component_ids"]) < 20:
            summary["top_component_ids"].append(clean_text(row.get("replacement_event_id")))

    rows_out = sorted(
        sublanes.values(),
        key=lambda item: (
            sublane_rank(item["sublane"]),
            -int(item["component_count"]),
            item["sublane"],
        ),
    )
    report = {
        "schema_version": 1,
        "report_policy": REPORT_POLICY,
        "canonical_outputs_mutated": False,
        "source_canonical_outputs_mutated": False,
        "ready_for_runtime_promotion": False,
        "inputs": {
            "audit_csv": str(audit_csv_path),
        },
        "audit_rows_read": len(rows),
        "sublane_count": len(rows_out),
        "sublanes": rows_out,
        "valid": True,
        "validation_error_count": 0,
        "validation_errors": [],
    }
    return report, rows_out


def classify_sublane(row: dict[str, str]) -> str:
    risk = clean_text(row.get("risk_level"))
    flags = set(split_pipe(row.get("risk_flags")))
    if risk == "low":
        return "accepted_low_risk_preview_lane"
    if "coordinate_span_gt_50km" in flags:
        return "high_coordinate_span_gt_50km"
    if "coordinate_span_gt_5km" in flags:
        return "medium_coordinate_span_gt_5km"
    if flags == {"time_raw_conflict"}:
        return "medium_time_raw_only"
    if flags <= {"time_raw_conflict", "same_source_multiple_native_ids"}:
        return "medium_time_or_identity_only"
    if flags <= {"description_text_conflict", "summary_text_conflict"}:
        return "medium_body_text_only"
    if flags <= {"shape_conflict", "type_conflict"}:
        return "medium_classification_only"
    if "same_source_multiple_native_ids" in flags:
        return "medium_identity_mixed"
    if {"description_text_conflict", "summary_text_conflict"} & flags:
        return "medium_body_text_mixed"
    if {"shape_conflict", "type_conflict"} & flags:
        return "medium_classification_mixed"
    if "location_text_conflict" in flags:
        return "medium_location_text_mixed"
    return f"{risk or 'unknown'}_other"


def sublane_rank(value: str) -> int:
    order = {
        "accepted_low_risk_preview_lane": 0,
        "medium_time_raw_only": 1,
        "medium_time_or_identity_only": 2,
        "medium_body_text_only": 3,
        "medium_classification_only": 4,
        "medium_coordinate_span_gt_5km": 8,
        "high_coordinate_span_gt_50km": 20,
    }
    return order.get(value, 10)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "sublane",
                "component_count",
                "projected_event_reduction",
                "risk_counts",
                "flag_counts",
                "top_component_ids",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **row,
                    "risk_counts": json.dumps(row["risk_counts"], sort_keys=True),
                    "flag_counts": json.dumps(row["flag_counts"], sort_keys=True),
                    "top_component_ids": "|".join(row["top_component_ids"]),
                }
            )


def split_pipe(value: Any) -> list[str]:
    return [item for item in (clean_text(part) for part in str(value or "").split("|")) if item]


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def safe_int(value: Any) -> int:
    try:
        return int(float(clean_text(value) or "0"))
    except ValueError:
        return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-csv", type=Path, default=DEFAULT_AUDIT_CSV)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report, rows = summarize_manual_review_replacement_audit_sublanes(audit_csv_path=args.audit_csv)
    write_json(args.output_json, report)
    write_csv(args.output_csv, rows)
    print(
        json.dumps(
            {
                "output_json": str(args.output_json),
                "output_csv": str(args.output_csv),
                "sublane_count": report["sublane_count"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
