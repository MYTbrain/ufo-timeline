"""Review small medium-risk location-text mixed manual-review components.

Targets rows whose risk flags are limited to ``location_text_conflict`` and
optionally ``time_raw_conflict``. The script classifies punctuation/spacing
location variants versus cases needing deeper location/time review. It is
review-only and never creates decisions or mutates canonical data.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import json
from pathlib import Path
from typing import Any

from scripts.analyze_entity_resolution_cluster_time_normalization import parse_time_token


DEFAULT_AUDIT_CSV = Path("data/reports/manual_review_ai_after_time_norm_replacement_audit.csv")
DEFAULT_JSON_OUTPUT = Path("data/reports/manual_review_ai_after_time_norm_medium_location_text_mixed_review.json")
DEFAULT_CSV_OUTPUT = Path("data/reports/manual_review_ai_after_time_norm_medium_location_text_mixed_review.csv")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/manual_review_ai_after_time_norm_medium_location_text_mixed_review.md")

REVIEW_POLICY = "manual_review_medium_location_text_mixed_review_v1"
LOCATION_VARIANT_REVIEW_CANDIDATE = "location_variant_review_candidate"
NEEDS_DEEPER_LOCATION_REVIEW = "needs_deeper_location_review"
MIN_LOCATION_SIMILARITY = 0.92
MAX_EXACT_SPAN_MINUTES = 15

CSV_FIELDS = (
    "review_rank",
    "replacement_event_id",
    "review_recommendation",
    "location_subcategory",
    "confidence",
    "projected_event_reduction",
    "location_similarity",
    "exact_span_minutes",
    "risk_flags",
    "location_raw_values",
    "time_raw_values",
    "failed_conditions",
    "component_event_count",
    "component_event_ids",
)


def build_medium_location_text_mixed_review(
    *,
    audit_csv_path: Path,
    min_location_similarity: float = MIN_LOCATION_SIMILARITY,
    max_exact_span_minutes: int = MAX_EXACT_SPAN_MINUTES,
) -> dict[str, Any]:
    audit_rows = read_csv(audit_csv_path)
    target_rows = [row for row in audit_rows if is_medium_location_text_mixed(row)]
    items = [
        review_row(
            row,
            min_location_similarity=min_location_similarity,
            max_exact_span_minutes=max_exact_span_minutes,
        )
        for row in target_rows
    ]
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
        "inputs": {
            "audit_csv": str(audit_csv_path),
            "min_location_similarity": min_location_similarity,
            "max_exact_span_minutes": max_exact_span_minutes,
        },
        "summary": {
            "audit_rows_read": len(audit_rows),
            "target_medium_location_text_mixed_count": len(target_rows),
            "reviewed_item_count": len(items),
            "review_recommendation_counts": count_by(items, "review_recommendation"),
            "location_subcategory_counts": count_by(items, "location_subcategory"),
            "confidence_counts": count_by(items, "confidence"),
            "projected_event_reduction_by_review_recommendation": dict(
                sorted(projected_by_recommendation.items())
            ),
            "failed_condition_counts": count_failed_conditions(items),
        },
        "items": items,
        "notes": [
            "This report is review-only; it does not create accepted decisions, apply merges, or mutate canonical outputs.",
            "Location variants require high normalized similarity and, when time conflicts exist, narrow exact-time variance.",
        ],
    }


def is_medium_location_text_mixed(row: dict[str, str]) -> bool:
    flags = set(split_pipe(row.get("risk_flags")))
    return (
        clean_text(row.get("risk_level")) == "medium"
        and "location_text_conflict" in flags
        and flags <= {"location_text_conflict", "time_raw_conflict"}
    )


def review_row(row: dict[str, str], *, min_location_similarity: float, max_exact_span_minutes: int) -> dict[str, Any]:
    flags = set(split_pipe(row.get("risk_flags")))
    location_values = split_pipe(row.get("location_raw_values"))
    similarity = min_pairwise_similarity([normalize_location(value) for value in location_values])
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
    has_time_conflict = "time_raw_conflict" in flags
    time_ok = not has_time_conflict or (
        len(exact_minutes) >= 2
        and exact_span <= max_exact_span_minutes
        and not any(token.get("kind") != "exact" or token.get("approximate") for token in parsed_tokens)
    )
    location_ok = similarity >= min_location_similarity
    subcategory = "punctuation_spacing_location_variant" if location_ok else "substantive_location_text_variance"
    conditions = {
        "audit_medium_location_text_mixed": is_medium_location_text_mixed(row),
        "location_similarity_within_threshold": location_ok,
        "time_conflict_absent_or_nearby_exact": time_ok,
    }
    failed_conditions = [key for key, passed in conditions.items() if not passed]
    review_candidate = not failed_conditions

    return {
        "review_rank": None,
        "replacement_event_id": clean_text(row.get("replacement_event_id")),
        "review_recommendation": (
            LOCATION_VARIANT_REVIEW_CANDIDATE if review_candidate else NEEDS_DEEPER_LOCATION_REVIEW
        ),
        "location_subcategory": subcategory,
        "confidence": "low",
        "projected_event_reduction": projected_event_reduction(row),
        "risk_flags": sorted(flags),
        "location_similarity": round(similarity, 4),
        "exact_span_minutes": exact_span if len(exact_minutes) >= 2 else None,
        "location_raw_values": location_values,
        "time_raw_values": time_values,
        "parsed_tokens": parsed_tokens,
        "failed_conditions": failed_conditions,
        "review_reason_codes": (
            [
                "location_text_conflict_only_or_nearby_time",
                "punctuation_spacing_location_variant",
                "manual_location_review_required",
                "review_only_not_decision",
            ]
            if review_candidate
            else ["needs_deeper_location_review", subcategory] + failed_conditions
        ),
        "component_event_count": safe_int(row.get("component_event_count")),
        "canonical_input_id_count": safe_int(row.get("canonical_input_id_count")),
        "coordinate_span_km": safe_float(row.get("coordinate_span_km")),
        "date_iso_values": split_pipe(row.get("date_iso_values")),
        "source_file_values": split_pipe(row.get("source_file_values")),
        "component_event_ids": split_pipe(row.get("component_event_ids")),
    }


def normalize_location(value: str) -> str:
    return " ".join("".join(char.lower() if char.isalnum() else " " for char in value).split())


def min_pairwise_similarity(values: list[str]) -> float:
    values = [value for value in values if value]
    if len(values) < 2:
        return 1.0
    scores = []
    for left_index, left in enumerate(values):
        for right in values[left_index + 1 :]:
            scores.append(difflib.SequenceMatcher(None, left, right).ratio())
    return min(scores) if scores else 1.0


def projected_event_reduction(row: dict[str, str]) -> int:
    return max(0, safe_int(row.get("component_event_count")) - 1)


def review_sort_key(item: dict[str, Any]) -> tuple[int, float, int, str]:
    return (
        0 if item["review_recommendation"] == LOCATION_VARIANT_REVIEW_CANDIDATE else 1,
        -float(item["location_similarity"]),
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
        "# Medium Location-Text-Mixed Review",
        "",
        "This report is review-only. It does not accept decisions or mutate canonical outputs.",
        "",
        "## Summary",
        "",
        f"- Target items: {report['summary']['target_medium_location_text_mixed_count']}",
        f"- Recommendations: {json.dumps(report['summary']['review_recommendation_counts'], sort_keys=True)}",
        f"- Subcategories: {json.dumps(report['summary']['location_subcategory_counts'], sort_keys=True)}",
        f"- Projected reduction by recommendation: {json.dumps(report['summary']['projected_event_reduction_by_review_recommendation'], sort_keys=True)}",
        "",
        "## Top Items",
        "",
        "| Recommendation | Subcategory | Replacement | Similarity | Locations | Times | Failed Conditions |",
        "| --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for item in items[:limit]:
        lines.append(
            "| "
            + " | ".join(
                [
                    escape_md(clean_text(item.get("review_recommendation"))),
                    escape_md(clean_text(item.get("location_subcategory"))),
                    f"`{escape_md(clean_text(item.get('replacement_event_id')))}`",
                    str(item.get("location_similarity")),
                    escape_md(" | ".join(item.get("location_raw_values") or [])),
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
                    "location_subcategory": item.get("location_subcategory"),
                    "confidence": item.get("confidence"),
                    "projected_event_reduction": item.get("projected_event_reduction"),
                    "location_similarity": item.get("location_similarity"),
                    "exact_span_minutes": item.get("exact_span_minutes"),
                    "risk_flags": "|".join(item.get("risk_flags") or []),
                    "location_raw_values": "|".join(item.get("location_raw_values") or []),
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
    parser.add_argument("--min-location-similarity", type=float, default=MIN_LOCATION_SIMILARITY)
    parser.add_argument("--max-exact-span-minutes", type=int, default=MAX_EXACT_SPAN_MINUTES)
    parser.add_argument("--markdown-limit", type=int, default=100)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_medium_location_text_mixed_review(
        audit_csv_path=args.audit_csv,
        min_location_similarity=args.min_location_similarity,
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
                "target_items": report["summary"]["target_medium_location_text_mixed_count"],
                "recommendations": report["summary"]["review_recommendation_counts"],
                "subcategories": report["summary"]["location_subcategory_counts"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
