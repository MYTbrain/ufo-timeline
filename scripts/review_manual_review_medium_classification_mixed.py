"""Review medium classification-mixed manual-review replacement rows.

Targets rows whose flags are limited to time/type/shape conflicts, excluding
the classification-only lane. The packet is report-only and does not create
decisions, apply merges, or mutate canonical data.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


DEFAULT_AUDIT_CSV = Path("data/reports/manual_review_ai_after_time_norm_replacement_audit.csv")
DEFAULT_JSON_OUTPUT = Path("data/reports/manual_review_ai_after_time_norm_medium_classification_mixed_review.json")
DEFAULT_CSV_OUTPUT = Path("data/reports/manual_review_ai_after_time_norm_medium_classification_mixed_review.csv")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/manual_review_ai_after_time_norm_medium_classification_mixed_review.md")

REVIEW_POLICY = "manual_review_medium_classification_mixed_review_v1"
NEEDS_DEEPER_CLASSIFICATION_MIXED_REVIEW = "needs_deeper_classification_mixed_review"

CSV_FIELDS = (
    "review_rank",
    "replacement_event_id",
    "review_recommendation",
    "classification_mixed_subcategory",
    "confidence",
    "projected_event_reduction",
    "risk_flags",
    "shape_values",
    "type_values",
    "time_raw_values",
    "failed_conditions",
    "component_event_count",
    "component_event_ids",
)


def build_medium_classification_mixed_review(*, audit_csv_path: Path) -> dict[str, Any]:
    audit_rows = read_csv(audit_csv_path)
    target_rows = [row for row in audit_rows if is_medium_classification_mixed(row)]
    items = [review_row(row) for row in target_rows]
    items.sort(key=review_sort_key)
    for index, item in enumerate(items, start=1):
        item["review_rank"] = index

    projected_by_recommendation: dict[str, int] = {}
    for item in items:
        recommendation = item["review_recommendation"]
        projected_by_recommendation[recommendation] = projected_by_recommendation.get(recommendation, 0) + int(
            item["projected_event_reduction"]
        )

    return {
        "schema_version": 1,
        "review_policy": REVIEW_POLICY,
        "canonical_outputs_mutated": False,
        "source_canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_runtime_promotion": False,
        "human_review_required_before_promotion": True,
        "inputs": {"audit_csv": str(audit_csv_path)},
        "summary": {
            "audit_rows_read": len(audit_rows),
            "target_medium_classification_mixed_count": len(target_rows),
            "reviewed_item_count": len(items),
            "review_recommendation_counts": count_by(items, "review_recommendation"),
            "classification_mixed_subcategory_counts": count_by(items, "classification_mixed_subcategory"),
            "confidence_counts": count_by(items, "confidence"),
            "projected_event_reduction_by_review_recommendation": dict(
                sorted(projected_by_recommendation.items())
            ),
            "failed_condition_counts": count_failed_conditions(items),
        },
        "items": items,
        "notes": [
            "This report is review-only; it does not create accepted decisions, apply merges, or mutate canonical outputs.",
            "Rows mix classification and time conflicts; they require classification-code and time evidence review before decisions.",
        ],
    }


def is_medium_classification_mixed(row: dict[str, str]) -> bool:
    flags = set(split_pipe(row.get("risk_flags")))
    classification_flags = {"type_conflict", "shape_conflict"}
    return (
        clean_text(row.get("risk_level")) == "medium"
        and bool(flags & classification_flags)
        and flags <= {"time_raw_conflict", "type_conflict", "shape_conflict"}
        and flags != {"type_conflict"}
    )


def review_row(row: dict[str, str]) -> dict[str, Any]:
    flags = set(split_pipe(row.get("risk_flags")))
    shape_values = split_pipe(row.get("shape_values"))
    type_values = split_pipe(row.get("type_values"))
    type_prefixes = sorted({type_major_prefix(value) for value in type_values if type_major_prefix(value)})
    if "shape_conflict" in flags and "type_conflict" in flags:
        subcategory = "shape_and_type_with_time_conflict"
    elif "shape_conflict" in flags:
        subcategory = "shape_with_time_conflict"
    elif len(type_prefixes) == 1:
        subcategory = "minor_type_code_with_time_conflict"
    else:
        subcategory = "substantive_type_category_with_time_conflict"

    failed_conditions = ["manual_classification_time_review_required"]
    return {
        "review_rank": None,
        "replacement_event_id": clean_text(row.get("replacement_event_id")),
        "review_recommendation": NEEDS_DEEPER_CLASSIFICATION_MIXED_REVIEW,
        "classification_mixed_subcategory": subcategory,
        "confidence": "low",
        "projected_event_reduction": projected_event_reduction(row),
        "risk_flags": sorted(flags),
        "shape_values": shape_values,
        "type_values": type_values,
        "type_prefixes": type_prefixes,
        "time_raw_values": split_pipe(row.get("time_raw_values")),
        "location_raw_values": split_pipe(row.get("location_raw_values")),
        "failed_conditions": failed_conditions,
        "review_reason_codes": ["needs_deeper_classification_mixed_review", subcategory] + failed_conditions,
        "component_event_count": safe_int(row.get("component_event_count")),
        "canonical_input_id_count": safe_int(row.get("canonical_input_id_count")),
        "coordinate_span_km": safe_float(row.get("coordinate_span_km")),
        "date_iso_values": split_pipe(row.get("date_iso_values")),
        "source_file_values": split_pipe(row.get("source_file_values")),
        "component_event_ids": split_pipe(row.get("component_event_ids")),
    }


def type_major_prefix(value: str) -> str:
    value = clean_text(value).lower()
    prefix = []
    for char in value:
        if char.isdigit():
            prefix.append(char)
        else:
            break
    return "".join(prefix)


def projected_event_reduction(row: dict[str, str]) -> int:
    return max(0, safe_int(row.get("component_event_count")) - 1)


def review_sort_key(item: dict[str, Any]) -> tuple[str, int, str]:
    return (
        item["classification_mixed_subcategory"],
        -int(item["projected_event_reduction"]),
        item["replacement_event_id"],
    )


def count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = clean_text(item.get(key)) or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def count_failed_conditions(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        for condition in item.get("failed_conditions") or []:
            condition = clean_text(condition)
            counts[condition] = counts.get(condition, 0) + 1
    return dict(sorted(counts.items()))


def render_markdown(report: dict[str, Any], *, limit: int = 100) -> str:
    items = [item for item in report.get("items") or [] if isinstance(item, dict)]
    lines = [
        "# Medium Classification-Mixed Review",
        "",
        "This report is review-only. It does not accept decisions or mutate canonical outputs.",
        "",
        "## Summary",
        "",
        f"- Target items: {report['summary']['target_medium_classification_mixed_count']}",
        f"- Recommendations: {json.dumps(report['summary']['review_recommendation_counts'], sort_keys=True)}",
        f"- Subcategories: {json.dumps(report['summary']['classification_mixed_subcategory_counts'], sort_keys=True)}",
        f"- Projected reduction by recommendation: {json.dumps(report['summary']['projected_event_reduction_by_review_recommendation'], sort_keys=True)}",
        "",
        "## Top Items",
        "",
        "| Recommendation | Subcategory | Replacement | Shapes | Types | Times |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in items[:limit]:
        lines.append(
            "| "
            + " | ".join(
                [
                    escape_md(clean_text(item.get("review_recommendation"))),
                    escape_md(clean_text(item.get("classification_mixed_subcategory"))),
                    f"`{escape_md(clean_text(item.get('replacement_event_id')))}`",
                    escape_md("|".join(item.get("shape_values") or [])),
                    escape_md("|".join(item.get("type_values") or [])),
                    escape_md("|".join(item.get("time_raw_values") or [])),
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def write_csv(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for item in report.get("items") or []:
            if not isinstance(item, dict):
                continue
            writer.writerow(
                {
                    "review_rank": item.get("review_rank"),
                    "replacement_event_id": item.get("replacement_event_id"),
                    "review_recommendation": item.get("review_recommendation"),
                    "classification_mixed_subcategory": item.get("classification_mixed_subcategory"),
                    "confidence": item.get("confidence"),
                    "projected_event_reduction": item.get("projected_event_reduction"),
                    "risk_flags": "|".join(item.get("risk_flags") or []),
                    "shape_values": "|".join(item.get("shape_values") or []),
                    "type_values": "|".join(item.get("type_values") or []),
                    "time_raw_values": "|".join(item.get("time_raw_values") or []),
                    "failed_conditions": "|".join(item.get("failed_conditions") or []),
                    "component_event_count": item.get("component_event_count"),
                    "component_event_ids": "|".join(item.get("component_event_ids") or []),
                }
            )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def split_pipe(value: Any) -> list[str]:
    return [item for item in (clean_text(part) for part in str(value or "").split("|")) if item]


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def safe_int(value: Any) -> int:
    try:
        return int(float(clean_text(value) or "0"))
    except ValueError:
        return 0


def safe_float(value: Any) -> float:
    try:
        return float(clean_text(value) or "0")
    except ValueError:
        return 0.0


def escape_md(value: str) -> str:
    return value.replace("|", "\\|")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-csv", type=Path, default=DEFAULT_AUDIT_CSV)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument("--markdown-limit", type=int, default=100)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_medium_classification_mixed_review(audit_csv_path=args.audit_csv)
    write_json(args.output_json, report)
    write_csv(args.output_csv, report)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(render_markdown(report, limit=args.markdown_limit), encoding="utf-8")
    print(
        json.dumps(
            {
                "output_json": str(args.output_json),
                "output_csv": str(args.output_csv),
                "output_md": str(args.output_md),
                "target_items": report["summary"]["target_medium_classification_mixed_count"],
                "recommendations": report["summary"]["review_recommendation_counts"],
                "subcategories": report["summary"]["classification_mixed_subcategory_counts"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
