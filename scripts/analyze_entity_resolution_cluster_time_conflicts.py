"""Analyze time conflicts in the cluster blocker priority queue.

This is review-only. It classifies the remaining time-conflict blockers so the
next review pass can separate close rounded-time conflicts from broad or risky
same-day disagreements. It does not create decisions, override subsets, preview
applies, or canonical mutations.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from scripts.analyze_entity_resolution_cluster_time_normalization import (
    as_int,
    clean_text,
    count_by,
    parse_time_token,
    read_json,
    string_list,
    time_tokens,
    validate_priority_queue_safety,
    write_json,
)


DEFAULT_PRIORITY_QUEUE = Path("data/reports/entity_resolution_cluster_blocker_priority_queue.json")
DEFAULT_JSON_OUTPUT = Path("data/reports/entity_resolution_cluster_time_conflict_analysis.json")
DEFAULT_CSV_OUTPUT = Path("data/reports/entity_resolution_cluster_time_conflict_analysis.csv")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/entity_resolution_cluster_time_conflict_analysis.md")

ANALYSIS_POLICY = "entity_resolution_cluster_time_conflict_review_only"

CSV_FIELDS = (
    "review_rank",
    "time_conflict_classification",
    "review_risk_tier",
    "identity_consistency",
    "review_item_id",
    "effect_id",
    "projected_event_reduction",
    "blocking_fields",
    "time_tokens",
    "parsed_minutes",
    "exact_span_minutes",
    "fuzzy_labels",
    "approximate_tokens",
    "ambiguous_tokens",
    "unknown_tokens",
    "risk_flags",
    "has_coordinate_risk",
    "source_names",
    "source_native_ids",
    "date_values",
    "location_values",
    "canonical_event_id_count",
    "recommended_review_step",
)


def analyze_entity_resolution_cluster_time_conflicts(
    *,
    priority_queue: dict[str, Any],
    priority_queue_path: Path | None = None,
) -> dict[str, Any]:
    validate_priority_queue_safety(priority_queue)
    items = []
    for queue_item in priority_queue.get("items") or []:
        if not isinstance(queue_item, dict):
            continue
        if clean_text(queue_item.get("triage_bucket")) != "time_conflict_review":
            continue
        items.append(analyze_queue_item(queue_item))
    items.sort(key=time_conflict_sort_key)
    for index, item in enumerate(items, start=1):
        item["review_rank"] = index
    return {
        "schema_version": 1,
        "analysis_policy": ANALYSIS_POLICY,
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "auto_merge_performed": False,
        "override_decisions_created": False,
        "ready_for_canonical_apply": False,
        "inputs": {
            "priority_queue": str(priority_queue_path) if priority_queue_path else None,
        },
        "summary": {
            "analyzed_item_count": len(items),
            "classification_counts": count_by(items, "time_conflict_classification"),
            "review_risk_tier_counts": count_by(items, "review_risk_tier"),
            "identity_consistency_counts": count_by(items, "identity_consistency"),
            "projected_reduction_sum_not_deduped": sum(
                int(item.get("projected_event_reduction") or 0) for item in items
            ),
        },
        "items": items,
        "notes": [
            "This analysis is review-only; it does not promote time conflicts to merge decisions.",
            "Close exact-time conflicts are still review candidates, not approvals.",
            "Projected reduction sums are not deduped across overlapping effects.",
        ],
    }


def analyze_queue_item(queue_item: dict[str, Any]) -> dict[str, Any]:
    tokens = time_tokens(queue_item)
    parsed_tokens = [parse_time_token(token) for token in tokens]
    exact_minutes = sorted(
        {token["minute"] for token in parsed_tokens if token["kind"] == "exact" and token["minute"] is not None}
    )
    fuzzy_labels = sorted({token["bucket_label"] for token in parsed_tokens if token["kind"] == "fuzzy" and token["bucket_label"]})
    ambiguous_tokens = [token["raw"] for token in parsed_tokens if token["kind"] == "ambiguous"]
    unknown_tokens = [token["raw"] for token in parsed_tokens if token["kind"] == "unknown"]
    approximate_tokens = [token["raw"] for token in parsed_tokens if token.get("approximate")]
    exact_span_minutes = exact_minutes[-1] - exact_minutes[0] if len(exact_minutes) >= 2 else 0
    source_summary = normalized_source_summary(queue_item.get("source_summary"))
    identity_consistency = classify_identity_consistency(source_summary)
    classification = classify_time_conflict(
        exact_minutes=exact_minutes,
        exact_span_minutes=exact_span_minutes,
        fuzzy_labels=fuzzy_labels,
        approximate_tokens=approximate_tokens,
        ambiguous_tokens=ambiguous_tokens,
        unknown_tokens=unknown_tokens,
    )
    risk_flags = string_list(queue_item.get("risks"))
    has_coordinate_risk = any("coordinate" in risk.lower() for risk in risk_flags)
    risk_tier = time_conflict_risk_tier(
        classification=classification,
        identity_consistency=identity_consistency,
        has_coordinate_risk=has_coordinate_risk,
    )
    return {
        "review_rank": None,
        "time_conflict_classification": classification,
        "review_risk_tier": risk_tier,
        "identity_consistency": identity_consistency,
        "recommended_review_step": recommended_review_step(classification, risk_tier),
        "review_item_id": clean_text(queue_item.get("review_item_id")),
        "effect_id": clean_text(queue_item.get("effect_id")),
        "patch_id": clean_text(queue_item.get("patch_id")),
        "projected_event_reduction": as_int(queue_item.get("projected_event_reduction")) or 0,
        "blocking_fields": string_list(queue_item.get("blocking_fields")),
        "time_tokens": tokens,
        "parsed_tokens": parsed_tokens,
        "parsed_minutes": exact_minutes,
        "exact_span_minutes": exact_span_minutes,
        "fuzzy_labels": fuzzy_labels,
        "approximate_tokens": approximate_tokens,
        "ambiguous_tokens": ambiguous_tokens,
        "unknown_tokens": unknown_tokens,
        "risk_flags": risk_flags,
        "has_coordinate_risk": has_coordinate_risk,
        "source_summary": source_summary,
    }


def normalized_source_summary(value: Any) -> dict[str, Any]:
    source_summary = value if isinstance(value, dict) else {}
    canonical_event_ids = string_list(source_summary.get("canonical_event_ids"))
    return {
        "canonical_event_ids": canonical_event_ids,
        "canonical_input_ids": string_list(source_summary.get("canonical_input_ids")),
        "canonical_event_count": as_int(source_summary.get("canonical_event_count")) or len(canonical_event_ids),
        "source_names": string_list(source_summary.get("source_names")),
        "source_native_ids": string_list(source_summary.get("source_native_ids")),
        "date_values": string_list(source_summary.get("date_values")),
        "location_values": string_list(source_summary.get("location_values")),
        "type_values": string_list(source_summary.get("type_values")),
    }


def classify_identity_consistency(source_summary: dict[str, Any]) -> str:
    if (
        len(string_list(source_summary.get("source_names"))) == 1
        and len(string_list(source_summary.get("source_native_ids"))) == 1
        and len(string_list(source_summary.get("date_values"))) == 1
        and len(string_list(source_summary.get("location_values"))) == 1
        and int(source_summary.get("canonical_event_count") or 0) >= 2
    ):
        return "single_source_id_date_location"
    return "mixed_or_incomplete_identity"


def classify_time_conflict(
    *,
    exact_minutes: list[int],
    exact_span_minutes: int,
    fuzzy_labels: list[str],
    approximate_tokens: list[str],
    ambiguous_tokens: list[str],
    unknown_tokens: list[str],
) -> str:
    has_context_tokens = bool(fuzzy_labels or approximate_tokens or ambiguous_tokens or unknown_tokens)
    if len(exact_minutes) >= 2 and exact_span_minutes <= 5 and not has_context_tokens:
        return "nearby_exact_conflict_5m_or_less"
    if len(exact_minutes) >= 2 and exact_span_minutes <= 15 and not has_context_tokens:
        return "nearby_exact_conflict_15m_or_less"
    if len(exact_minutes) >= 2 and exact_span_minutes <= 15 and approximate_tokens:
        return "nearby_exact_conflict_15m_or_less_with_approximation"
    if len(exact_minutes) >= 2 and exact_span_minutes <= 15:
        return "nearby_exact_conflict_15m_or_less_with_context"
    if len(exact_minutes) >= 2 and exact_span_minutes <= 60 and not (ambiguous_tokens or unknown_tokens):
        return "nearby_exact_conflict_60m_or_less"
    if len(exact_minutes) >= 2 and exact_span_minutes > 60:
        return "wide_exact_conflict_over_60m"
    if len(exact_minutes) == 1 and approximate_tokens and not (fuzzy_labels or ambiguous_tokens or unknown_tokens):
        return "single_exact_with_approximation_context"
    if len(exact_minutes) == 1 and fuzzy_labels and not (ambiguous_tokens or unknown_tokens):
        return "single_exact_with_fuzzy_context"
    if not exact_minutes and fuzzy_labels and not (ambiguous_tokens or unknown_tokens):
        return "fuzzy_bucket_conflict_only"
    if ambiguous_tokens or unknown_tokens:
        return "ambiguous_or_unknown_conflict"
    return "single_exact_or_unclassified_conflict"


def time_conflict_risk_tier(*, classification: str, identity_consistency: str, has_coordinate_risk: bool) -> str:
    if identity_consistency != "single_source_id_date_location":
        return "high"
    if has_coordinate_risk:
        return "high"
    if classification in {"nearby_exact_conflict_5m_or_less", "nearby_exact_conflict_15m_or_less"}:
        return "lower"
    if classification in {
        "nearby_exact_conflict_15m_or_less_with_approximation",
        "nearby_exact_conflict_15m_or_less_with_context",
        "nearby_exact_conflict_60m_or_less",
        "single_exact_with_approximation_context",
        "single_exact_with_fuzzy_context",
        "fuzzy_bucket_conflict_only",
    }:
        return "medium"
    return "high"


def recommended_review_step(classification: str, risk_tier: str) -> str:
    if risk_tier == "lower":
        return "Review source text as a rounded-time duplicate candidate; do not auto-approve."
    if classification == "nearby_exact_conflict_15m_or_less_with_approximation":
        return "Check approximate time markers before treating close exact times as one observation."
    if classification == "single_exact_with_approximation_context":
        return "Review whether approximate marks are shorthand for the same exact minute."
    if classification == "nearby_exact_conflict_15m_or_less_with_context":
        return "Check whether context tokens are broad descriptors attached to close exact times."
    if classification == "nearby_exact_conflict_60m_or_less":
        return "Review manually; close times may be duplicate reports or sequential observations."
    if classification == "single_exact_with_fuzzy_context":
        return "Review whether broad fuzzy labels describe the same exact-timed observation."
    if classification == "fuzzy_bucket_conflict_only":
        return "Keep as weak evidence; broad time buckets are not enough for precise same-day merging."
    if classification == "wide_exact_conflict_over_60m":
        return "Treat as high risk; wide same-day time gaps may be separate events."
    if classification == "ambiguous_or_unknown_conflict":
        return "Resolve ambiguous/unknown tokens before considering any merge override."
    return "Defer unless source-level evidence establishes one event."


def time_conflict_sort_key(item: dict[str, Any]) -> tuple[int, int, int, str]:
    risk_order = {"lower": 10, "medium": 20, "high": 30}
    return (
        risk_order.get(clean_text(item.get("review_risk_tier")), 90),
        int(item.get("exact_span_minutes") or 0),
        -int(item.get("projected_event_reduction") or 0),
        str(item.get("review_item_id") or ""),
    )


def write_csv(path: Path, items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for item in items:
            writer.writerow(csv_row(item))


def csv_row(item: dict[str, Any]) -> dict[str, Any]:
    source_summary = item.get("source_summary") if isinstance(item.get("source_summary"), dict) else {}
    return {
        "review_rank": item.get("review_rank"),
        "time_conflict_classification": item.get("time_conflict_classification"),
        "review_risk_tier": item.get("review_risk_tier"),
        "identity_consistency": item.get("identity_consistency"),
        "review_item_id": item.get("review_item_id"),
        "effect_id": item.get("effect_id"),
        "projected_event_reduction": item.get("projected_event_reduction"),
        "blocking_fields": "; ".join(string_list(item.get("blocking_fields"))),
        "time_tokens": "; ".join(string_list(item.get("time_tokens"))),
        "parsed_minutes": "; ".join(str(value) for value in item.get("parsed_minutes") or []),
        "exact_span_minutes": item.get("exact_span_minutes"),
        "fuzzy_labels": "; ".join(string_list(item.get("fuzzy_labels"))),
        "approximate_tokens": "; ".join(string_list(item.get("approximate_tokens"))),
        "ambiguous_tokens": "; ".join(string_list(item.get("ambiguous_tokens"))),
        "unknown_tokens": "; ".join(string_list(item.get("unknown_tokens"))),
        "risk_flags": "; ".join(string_list(item.get("risk_flags"))),
        "has_coordinate_risk": item.get("has_coordinate_risk"),
        "source_names": "; ".join(string_list(source_summary.get("source_names"))),
        "source_native_ids": "; ".join(string_list(source_summary.get("source_native_ids"))),
        "date_values": "; ".join(string_list(source_summary.get("date_values"))),
        "location_values": "; ".join(string_list(source_summary.get("location_values"))),
        "canonical_event_id_count": source_summary.get("canonical_event_count") or 0,
        "recommended_review_step": item.get("recommended_review_step"),
    }


def write_markdown(path: Path, analysis: dict[str, Any], *, item_limit: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = analysis.get("summary") if isinstance(analysis.get("summary"), dict) else {}
    lines = [
        "# Cluster Time-Conflict Analysis",
        "",
        "This analysis is review-only. It classifies time conflicts but does not create merge decisions.",
        "",
        "## Summary",
        "",
        f"- Analyzed items: {summary.get('analyzed_item_count', 0)}",
        f"- Classification counts: `{json.dumps(summary.get('classification_counts', {}), sort_keys=True)}`",
        f"- Risk tier counts: `{json.dumps(summary.get('review_risk_tier_counts', {}), sort_keys=True)}`",
        f"- Identity consistency counts: `{json.dumps(summary.get('identity_consistency_counts', {}), sort_keys=True)}`",
        f"- Canonical outputs mutated: `{str(analysis.get('canonical_outputs_mutated')).lower()}`",
        "",
        "## Top Review Items",
        "",
    ]
    for item in (analysis.get("items") or [])[: max(0, item_limit)]:
        if not isinstance(item, dict):
            continue
        lines.extend(markdown_item_lines(item))
    if len(analysis.get("items") or []) > item_limit:
        lines.extend(["", f"_Markdown limited to {item_limit} of {len(analysis.get('items') or [])} analyzed items._", ""])
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def markdown_item_lines(item: dict[str, Any]) -> list[str]:
    source_summary = item.get("source_summary") if isinstance(item.get("source_summary"), dict) else {}
    return [
        f"### #{item.get('review_rank')} {item.get('review_item_id')}",
        "",
        f"- Classification: `{item.get('time_conflict_classification')}` risk `{item.get('review_risk_tier')}`",
        f"- Identity: `{item.get('identity_consistency')}`",
        f"- Projected reduction: `{item.get('projected_event_reduction')}`",
        f"- Blocking fields: {', '.join(string_list(item.get('blocking_fields'))) or 'none'}",
        f"- Time tokens: {', '.join(string_list(item.get('time_tokens'))) or 'none'}",
        f"- Parsed minutes: {', '.join(str(value) for value in item.get('parsed_minutes') or []) or 'none'}",
        f"- Exact span minutes: `{item.get('exact_span_minutes')}`",
        f"- Fuzzy labels: {', '.join(string_list(item.get('fuzzy_labels'))) or 'none'}",
        f"- Approximate tokens: {', '.join(string_list(item.get('approximate_tokens'))) or 'none'}",
        f"- Ambiguous tokens: {', '.join(string_list(item.get('ambiguous_tokens'))) or 'none'}",
        f"- Unknown tokens: {', '.join(string_list(item.get('unknown_tokens'))) or 'none'}",
        f"- Risk flags: {', '.join(string_list(item.get('risk_flags'))) or 'none'}",
        f"- Source names: {', '.join(string_list(source_summary.get('source_names'))) or 'none'}",
        f"- Source native IDs: {', '.join(string_list(source_summary.get('source_native_ids'))) or 'none'}",
        f"- Dates: {', '.join(string_list(source_summary.get('date_values'))) or 'none'}",
        f"- Locations: {', '.join(string_list(source_summary.get('location_values'))) or 'none'}",
        f"- Recommended review step: {item.get('recommended_review_step') or 'none'}",
        "",
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--priority-queue", type=Path, default=DEFAULT_PRIORITY_QUEUE)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument("--markdown-item-limit", type=int, default=120)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    priority_queue = read_json(args.priority_queue)
    analysis = analyze_entity_resolution_cluster_time_conflicts(
        priority_queue=priority_queue,
        priority_queue_path=args.priority_queue,
    )
    write_json(args.json_output, analysis)
    write_csv(args.csv_output, analysis["items"])
    write_markdown(args.markdown_output, analysis, item_limit=args.markdown_item_limit)
    print(
        json.dumps(
            {
                "json_output": str(args.json_output),
                "csv_output": str(args.csv_output),
                "markdown_output": str(args.markdown_output),
                "analyzed_item_count": analysis["summary"]["analyzed_item_count"],
                "classification_counts": analysis["summary"]["classification_counts"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
