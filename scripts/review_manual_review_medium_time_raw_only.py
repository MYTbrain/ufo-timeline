"""Review medium-risk manual-review components with only time_raw conflicts.

This consumes the replacement-audit CSV and produces recommendation-only
output. It does not create accepted decisions, apply merges, or mutate any
canonical/default corpus.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from scripts.analyze_entity_resolution_cluster_time_normalization import parse_time_token


DEFAULT_AUDIT_CSV = Path("data/reports/manual_review_ai_after_time_norm_replacement_audit.csv")
DEFAULT_JSON_OUTPUT = Path("data/reports/manual_review_ai_after_time_norm_medium_time_raw_only_review.json")
DEFAULT_CSV_OUTPUT = Path("data/reports/manual_review_ai_after_time_norm_medium_time_raw_only_review.csv")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/manual_review_ai_after_time_norm_medium_time_raw_only_review.md")

REVIEW_POLICY = "manual_review_medium_time_raw_only_parser_review_v1"
SOURCE_REVIEW_SAME_EVENT = "source_review_same_event_candidate"
NEEDS_MORE_EVIDENCE = "needs_more_evidence"
MAX_EXACT_SPAN_MINUTES = 15

CSV_FIELDS = (
    "review_rank",
    "replacement_event_id",
    "review_recommendation",
    "confidence",
    "projected_event_reduction",
    "exact_span_minutes",
    "time_raw_values",
    "parsed_minutes",
    "failed_conditions",
    "component_event_count",
    "canonical_input_id_count",
    "component_event_ids",
)


def build_medium_time_raw_only_review(
    *,
    audit_csv_path: Path,
    max_exact_span_minutes: int = MAX_EXACT_SPAN_MINUTES,
) -> dict[str, Any]:
    audit_rows = read_csv(audit_csv_path)
    target_rows = [row for row in audit_rows if is_medium_time_raw_only(row)]
    items = [review_row(row, max_exact_span_minutes=max_exact_span_minutes) for row in target_rows]
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
        "inputs": {
            "audit_csv": str(audit_csv_path),
            "max_exact_span_minutes": max_exact_span_minutes,
        },
        "summary": {
            "audit_rows_read": len(audit_rows),
            "target_medium_time_raw_only_count": len(target_rows),
            "reviewed_item_count": len(items),
            "review_recommendation_counts": count_by(items, "review_recommendation"),
            "confidence_counts": count_by(items, "confidence"),
            "projected_event_reduction_by_review_recommendation": dict(
                sorted(projected_by_recommendation.items())
            ),
            "failed_condition_counts": count_failed_conditions(items),
        },
        "items": items,
        "notes": [
            "This report is source-review guidance only; it does not accept or apply merges.",
            "Candidates require exactly the audit flag time_raw_conflict, all tokens parsing as exact non-approximate times, and an exact-time span no greater than the configured threshold.",
            "Ambiguous, fuzzy, approximate, unknown, or wider-span time conflicts remain needs_more_evidence.",
        ],
    }


def is_medium_time_raw_only(row: dict[str, str]) -> bool:
    return clean_text(row.get("risk_level")) == "medium" and set(split_pipe(row.get("risk_flags"))) == {
        "time_raw_conflict"
    }


def review_row(row: dict[str, str], *, max_exact_span_minutes: int) -> dict[str, Any]:
    time_values = split_pipe(row.get("time_raw_values"))
    parsed_tokens = [parse_time_token(value) for value in time_values]
    exact_minutes = sorted(
        {
            int(token["minute"])
            for token in parsed_tokens
            if token.get("kind") == "exact" and token.get("minute") is not None
        }
    )
    exact_span = exact_minutes[-1] - exact_minutes[0] if len(exact_minutes) >= 2 else 0
    non_exact_tokens = [token for token in parsed_tokens if token.get("kind") != "exact"]
    approximate_tokens = [token for token in parsed_tokens if token.get("approximate")]
    conditions = {
        "audit_medium_time_raw_only": is_medium_time_raw_only(row),
        "two_or_more_time_values": len(time_values) >= 2,
        "all_tokens_exact": not non_exact_tokens,
        "no_approximate_tokens": not approximate_tokens,
        "two_or_more_distinct_exact_minutes": len(exact_minutes) >= 2,
        "exact_span_within_threshold": len(exact_minutes) >= 2 and exact_span <= max_exact_span_minutes,
        "positive_projected_reduction": projected_event_reduction(row) > 0,
    }
    failed_conditions = [key for key, passed in conditions.items() if not passed]
    same_event = not failed_conditions
    return {
        "review_rank": None,
        "replacement_event_id": clean_text(row.get("replacement_event_id")),
        "review_recommendation": SOURCE_REVIEW_SAME_EVENT if same_event else NEEDS_MORE_EVIDENCE,
        "confidence": "medium" if same_event else "low",
        "projected_event_reduction": projected_event_reduction(row),
        "exact_span_minutes": exact_span if len(exact_minutes) >= 2 else None,
        "time_raw_values": time_values,
        "parsed_tokens": parsed_tokens,
        "parsed_minutes": exact_minutes,
        "non_exact_tokens": [token["raw"] for token in non_exact_tokens],
        "approximate_tokens": [token["raw"] for token in approximate_tokens],
        "failed_conditions": failed_conditions,
        "review_reason_codes": (
            [
                "medium_time_raw_only",
                "nearby_exact_times",
                "no_other_audit_conflicts",
                "review_only_not_decision",
            ]
            if same_event
            else ["needs_more_evidence"] + failed_conditions
        ),
        "component_event_count": safe_int(row.get("component_event_count")),
        "canonical_input_id_count": safe_int(row.get("canonical_input_id_count")),
        "coordinate_span_km": safe_float(row.get("coordinate_span_km")),
        "location_raw_values": split_pipe(row.get("location_raw_values")),
        "date_iso_values": split_pipe(row.get("date_iso_values")),
        "source_file_values": split_pipe(row.get("source_file_values")),
        "component_event_ids": split_pipe(row.get("component_event_ids")),
    }


def projected_event_reduction(row: dict[str, str]) -> int:
    return max(0, safe_int(row.get("component_event_count")) - 1)


def review_sort_key(item: dict[str, Any]) -> tuple[int, int, int, str]:
    return (
        0 if item["review_recommendation"] == SOURCE_REVIEW_SAME_EVENT else 1,
        int(item["exact_span_minutes"] if item["exact_span_minutes"] is not None else 10**9),
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
        "# Medium Time-Raw-Only Review",
        "",
        "This report is review-only. It does not accept decisions or mutate canonical outputs.",
        "",
        "## Summary",
        "",
        f"- Target items: {report['summary']['target_medium_time_raw_only_count']}",
        f"- Recommendations: {json.dumps(report['summary']['review_recommendation_counts'], sort_keys=True)}",
        f"- Projected reduction by recommendation: {json.dumps(report['summary']['projected_event_reduction_by_review_recommendation'], sort_keys=True)}",
        "",
        "## Top Items",
        "",
        "| Recommendation | Replacement | Span min | Reduction | Times | Failed Conditions |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    for item in items[:limit]:
        span = "" if item.get("exact_span_minutes") is None else str(item.get("exact_span_minutes"))
        lines.append(
            "| "
            + " | ".join(
                [
                    escape_md(clean_text(item.get("review_recommendation"))),
                    f"`{escape_md(clean_text(item.get('replacement_event_id')))}`",
                    span,
                    str(item.get("projected_event_reduction")),
                    escape_md(" | ".join(item.get("time_raw_values") or [])),
                    escape_md(", ".join(item.get("failed_conditions") or [])),
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
                    "confidence": item.get("confidence"),
                    "projected_event_reduction": item.get("projected_event_reduction"),
                    "exact_span_minutes": item.get("exact_span_minutes"),
                    "time_raw_values": "|".join(item.get("time_raw_values") or []),
                    "parsed_minutes": "|".join(str(value) for value in item.get("parsed_minutes") or []),
                    "failed_conditions": "|".join(item.get("failed_conditions") or []),
                    "component_event_count": item.get("component_event_count"),
                    "canonical_input_id_count": item.get("canonical_input_id_count"),
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
    parser.add_argument("--max-exact-span-minutes", type=int, default=MAX_EXACT_SPAN_MINUTES)
    parser.add_argument("--markdown-limit", type=int, default=100)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_medium_time_raw_only_review(
        audit_csv_path=args.audit_csv,
        max_exact_span_minutes=args.max_exact_span_minutes,
    )
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
                "target_items": report["summary"]["target_medium_time_raw_only_count"],
                "recommendations": report["summary"]["review_recommendation_counts"],
                "projected_reduction": report["summary"]["projected_event_reduction_by_review_recommendation"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
