"""Build a review-only packet for high-risk coordinate-span conflicts."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


DEFAULT_AUDIT_CSV = Path("data/reports/manual_review_ai_after_time_norm_replacement_audit.csv")
DEFAULT_JSON_OUTPUT = Path("data/reports/manual_review_ai_after_time_norm_high_coordinate_span_review.json")
DEFAULT_CSV_OUTPUT = Path("data/reports/manual_review_ai_after_time_norm_high_coordinate_span_review.csv")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/manual_review_ai_after_time_norm_high_coordinate_span_review.md")

REVIEW_POLICY = "manual_review_high_coordinate_span_review_v1"
NEEDS_DEEPER_HIGH_COORDINATE_REVIEW = "needs_deeper_high_coordinate_review"


def build_high_coordinate_span_review(*, audit_csv_path: Path) -> dict[str, Any]:
    audit_rows = read_csv(audit_csv_path)
    target_rows = [row for row in audit_rows if is_high_coordinate_span(row)]
    items = [review_row(row) for row in target_rows]
    items.sort(key=lambda item: (-float(item["coordinate_span_km"]), item["replacement_event_id"]))
    for index, item in enumerate(items, start=1):
        item["review_rank"] = index
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
            "target_high_coordinate_span_count": len(target_rows),
            "reviewed_item_count": len(items),
            "review_recommendation_counts": count_by(items, "review_recommendation"),
            "coordinate_subcategory_counts": count_by(items, "coordinate_subcategory"),
            "projected_event_reduction_by_review_recommendation": {
                NEEDS_DEEPER_HIGH_COORDINATE_REVIEW: sum(int(item["projected_event_reduction"]) for item in items)
            },
        },
        "items": items,
        "notes": [
            "This report is review-only; it does not create accepted decisions, apply merges, or mutate canonical outputs.",
            "All high coordinate-span components require manual geographic/source review before any decision.",
        ],
    }


def is_high_coordinate_span(row: dict[str, str]) -> bool:
    flags = set(split_pipe(row.get("risk_flags")))
    return clean_text(row.get("risk_level")) == "high" and "coordinate_span_gt_50km" in flags


def review_row(row: dict[str, str]) -> dict[str, Any]:
    span_km = safe_float(row.get("coordinate_span_km"))
    if span_km < 100:
        subcategory = "high_coordinate_variance_50_to_100km"
    elif span_km < 500:
        subcategory = "severe_coordinate_variance_100_to_500km"
    else:
        subcategory = "extreme_coordinate_variance_over_500km"
    return {
        "review_rank": None,
        "replacement_event_id": clean_text(row.get("replacement_event_id")),
        "review_recommendation": NEEDS_DEEPER_HIGH_COORDINATE_REVIEW,
        "coordinate_subcategory": subcategory,
        "confidence": "none",
        "projected_event_reduction": projected_event_reduction(row),
        "coordinate_span_km": span_km,
        "risk_flags": split_pipe(row.get("risk_flags")),
        "source_file_values": split_pipe(row.get("source_file_values")),
        "location_raw_values": split_pipe(row.get("location_raw_values")),
        "time_raw_values": split_pipe(row.get("time_raw_values")),
        "type_values": split_pipe(row.get("type_values")),
        "failed_conditions": ["high_coordinate_span_blocks_automation"],
        "component_event_count": safe_int(row.get("component_event_count")),
        "canonical_input_id_count": safe_int(row.get("canonical_input_id_count")),
        "date_iso_values": split_pipe(row.get("date_iso_values")),
        "component_event_ids": split_pipe(row.get("component_event_ids")),
    }


def projected_event_reduction(row: dict[str, str]) -> int:
    return max(0, safe_int(row.get("component_event_count")) - 1)


def count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = clean_text(item.get(key)) or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def render_markdown(report: dict[str, Any], *, limit: int = 100) -> str:
    items = [item for item in report.get("items") or [] if isinstance(item, dict)]
    lines = [
        "# High Coordinate-Span Review",
        "",
        "This report is review-only. It does not accept decisions or mutate canonical outputs.",
        "",
        "## Summary",
        "",
        f"- Target items: {report['summary']['target_high_coordinate_span_count']}",
        f"- Recommendations: {json.dumps(report['summary']['review_recommendation_counts'], sort_keys=True)}",
        f"- Subcategories: {json.dumps(report['summary']['coordinate_subcategory_counts'], sort_keys=True)}",
        "",
        "## Top Items",
        "",
        "| Recommendation | Subcategory | Replacement | Span km | Locations | Times |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for item in items[:limit]:
        lines.append(
            "| "
            + " | ".join(
                [
                    escape_md(clean_text(item.get("review_recommendation"))),
                    escape_md(clean_text(item.get("coordinate_subcategory"))),
                    f"`{escape_md(clean_text(item.get('replacement_event_id')))}`",
                    str(item.get("coordinate_span_km")),
                    escape_md("|".join(item.get("location_raw_values") or [])),
                    escape_md("|".join(item.get("time_raw_values") or [])),
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def write_csv(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = (
        "review_rank",
        "replacement_event_id",
        "review_recommendation",
        "coordinate_subcategory",
        "coordinate_span_km",
        "risk_flags",
        "location_raw_values",
        "time_raw_values",
        "component_event_count",
        "component_event_ids",
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in report.get("items") or []:
            writer.writerow(
                {
                    "review_rank": item.get("review_rank"),
                    "replacement_event_id": item.get("replacement_event_id"),
                    "review_recommendation": item.get("review_recommendation"),
                    "coordinate_subcategory": item.get("coordinate_subcategory"),
                    "coordinate_span_km": item.get("coordinate_span_km"),
                    "risk_flags": "|".join(item.get("risk_flags") or []),
                    "location_raw_values": "|".join(item.get("location_raw_values") or []),
                    "time_raw_values": "|".join(item.get("time_raw_values") or []),
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
    report = build_high_coordinate_span_review(audit_csv_path=args.audit_csv)
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
                "target_items": report["summary"]["target_high_coordinate_span_count"],
                "recommendations": report["summary"]["review_recommendation_counts"],
                "subcategories": report["summary"]["coordinate_subcategory_counts"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
