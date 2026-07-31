"""Analyze type conflicts in the cluster blocker priority queue.

This is review-only. It separates cleaner source subtype/code conflicts from
type conflicts that are mixed with time, coordinate, shape, or identity risks.
It does not create decisions, override subsets, preview applies, or canonical
mutations.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

from scripts.analyze_entity_resolution_cluster_time_conflicts import (
    classify_identity_consistency,
    normalized_source_summary,
)
from scripts.analyze_entity_resolution_cluster_time_normalization import (
    as_int,
    clean_text,
    count_by,
    read_json,
    string_list,
    validate_priority_queue_safety,
    write_json,
)


DEFAULT_PRIORITY_QUEUE = Path("data/reports/entity_resolution_cluster_blocker_priority_queue.json")
DEFAULT_JSON_OUTPUT = Path("data/reports/entity_resolution_cluster_type_conflict_analysis.json")
DEFAULT_CSV_OUTPUT = Path("data/reports/entity_resolution_cluster_type_conflict_analysis.csv")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/entity_resolution_cluster_type_conflict_analysis.md")

ANALYSIS_POLICY = "entity_resolution_cluster_type_conflict_review_only"

CSV_FIELDS = (
    "review_rank",
    "type_conflict_classification",
    "review_risk_tier",
    "identity_consistency",
    "review_item_id",
    "effect_id",
    "projected_event_reduction",
    "blocking_fields",
    "type_values",
    "type_family_prefixes",
    "shape_values",
    "time_values",
    "risk_flags",
    "has_coordinate_risk",
    "source_names",
    "source_native_ids",
    "date_values",
    "location_values",
    "canonical_event_id_count",
    "recommended_review_step",
)


def analyze_entity_resolution_cluster_type_conflicts(
    *,
    priority_queue: dict[str, Any],
    priority_queue_path: Path | None = None,
) -> dict[str, Any]:
    validate_priority_queue_safety(priority_queue)
    items = []
    for queue_item in priority_queue.get("items") or []:
        if not isinstance(queue_item, dict):
            continue
        if clean_text(queue_item.get("triage_bucket")) != "type_conflict_review":
            continue
        items.append(analyze_queue_item(queue_item))
    items.sort(key=type_conflict_sort_key)
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
            "classification_counts": count_by(items, "type_conflict_classification"),
            "review_risk_tier_counts": count_by(items, "review_risk_tier"),
            "identity_consistency_counts": count_by(items, "identity_consistency"),
            "projected_reduction_sum_not_deduped": sum(
                int(item.get("projected_event_reduction") or 0) for item in items
            ),
        },
        "items": items,
        "notes": [
            "This analysis is review-only; it does not promote type conflicts to merge decisions.",
            "Type-only single-family conflicts are review candidates, not approvals.",
            "Projected reduction sums are not deduped across overlapping effects.",
        ],
    }


def analyze_queue_item(queue_item: dict[str, Any]) -> dict[str, Any]:
    conflicts = queue_item.get("field_conflict_values") if isinstance(queue_item.get("field_conflict_values"), dict) else {}
    source_summary = normalized_source_summary(queue_item.get("source_summary"))
    blocking_fields = string_list(queue_item.get("blocking_fields"))
    type_values = sorted(set(string_list(conflicts.get("type_normalized")) or string_list(source_summary.get("type_values"))))
    shape_values = sorted(set(string_list(conflicts.get("shape_normalized"))))
    time_values = sorted(set(string_list(conflicts.get("time_raw"))))
    type_family_prefixes = type_prefixes(type_values)
    risk_flags = string_list(queue_item.get("risks"))
    has_coordinate_risk = any("coordinate" in risk.lower() for risk in risk_flags)
    has_identity_risk = any("identity" in risk.lower() for risk in risk_flags)
    identity_consistency = classify_identity_consistency(source_summary)
    classification = classify_type_conflict(
        blocking_fields=blocking_fields,
        type_family_prefixes=type_family_prefixes,
        shape_values=shape_values,
    )
    risk_tier = type_conflict_risk_tier(
        classification=classification,
        identity_consistency=identity_consistency,
        has_coordinate_risk=has_coordinate_risk,
        has_identity_risk=has_identity_risk,
    )
    return {
        "review_rank": None,
        "type_conflict_classification": classification,
        "review_risk_tier": risk_tier,
        "identity_consistency": identity_consistency,
        "recommended_review_step": recommended_review_step(classification, risk_tier),
        "review_item_id": clean_text(queue_item.get("review_item_id")),
        "effect_id": clean_text(queue_item.get("effect_id")),
        "patch_id": clean_text(queue_item.get("patch_id")),
        "projected_event_reduction": as_int(queue_item.get("projected_event_reduction")) or 0,
        "blocking_fields": blocking_fields,
        "type_values": type_values,
        "type_family_prefixes": type_family_prefixes,
        "shape_values": shape_values,
        "time_values": time_values,
        "risk_flags": risk_flags,
        "has_coordinate_risk": has_coordinate_risk,
        "has_identity_risk": has_identity_risk,
        "source_summary": source_summary,
    }


def type_prefixes(type_values: list[str]) -> list[str]:
    prefixes = []
    for value in type_values:
        normalized = clean_text(value).lower()
        match = re.match(r"^(\d+|[a-z]+)", normalized)
        if match:
            prefixes.append(match.group(1))
    return sorted(set(prefixes))


def classify_type_conflict(*, blocking_fields: list[str], type_family_prefixes: list[str], shape_values: list[str]) -> str:
    fields = set(blocking_fields)
    has_coordinate_blocker = "coordinate_distance_over_10km" in fields
    has_time_blocker = "time_raw" in fields
    type_only = fields == {"type_normalized"}
    single_family = len(type_family_prefixes) == 1
    has_shape_conflict = bool(shape_values)
    if has_coordinate_blocker and has_time_blocker:
        return "type_with_time_and_coordinate_conflict"
    if has_coordinate_blocker:
        return "type_with_coordinate_conflict"
    if has_time_blocker:
        return "type_with_time_conflict"
    if type_only and single_family and not has_shape_conflict:
        return "type_only_single_family_subcode_conflict"
    if type_only and single_family and has_shape_conflict:
        return "type_only_single_family_with_shape_conflict"
    if type_only:
        return "type_only_cross_family_conflict"
    return "type_conflict_mixed_blockers"


def type_conflict_risk_tier(
    *,
    classification: str,
    identity_consistency: str,
    has_coordinate_risk: bool,
    has_identity_risk: bool,
) -> str:
    if identity_consistency != "single_source_id_date_location" or has_identity_risk:
        return "high"
    if has_coordinate_risk or "coordinate" in classification:
        return "high"
    if classification == "type_only_single_family_subcode_conflict":
        return "lower"
    if classification in {"type_only_single_family_with_shape_conflict", "type_with_time_conflict"}:
        return "medium"
    return "high"


def recommended_review_step(classification: str, risk_tier: str) -> str:
    if risk_tier == "lower":
        return "Review as a same-source subtype-code variant candidate; do not auto-approve."
    if classification == "type_only_single_family_with_shape_conflict":
        return "Check whether shape labels describe one object class or conflicting reports."
    if classification == "type_with_time_conflict":
        return "Resolve time conflict before considering type-code normalization."
    if "coordinate" in classification:
        return "Keep high risk until coordinate spread is explained by source rows."
    if classification == "type_only_cross_family_conflict":
        return "Treat as high risk; type families disagree."
    return "Defer unless source-level evidence establishes one event."


def type_conflict_sort_key(item: dict[str, Any]) -> tuple[int, int, str]:
    risk_order = {"lower": 10, "medium": 20, "high": 30}
    return (
        risk_order.get(clean_text(item.get("review_risk_tier")), 90),
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
        "type_conflict_classification": item.get("type_conflict_classification"),
        "review_risk_tier": item.get("review_risk_tier"),
        "identity_consistency": item.get("identity_consistency"),
        "review_item_id": item.get("review_item_id"),
        "effect_id": item.get("effect_id"),
        "projected_event_reduction": item.get("projected_event_reduction"),
        "blocking_fields": "; ".join(string_list(item.get("blocking_fields"))),
        "type_values": "; ".join(string_list(item.get("type_values"))),
        "type_family_prefixes": "; ".join(string_list(item.get("type_family_prefixes"))),
        "shape_values": "; ".join(string_list(item.get("shape_values"))),
        "time_values": "; ".join(string_list(item.get("time_values"))),
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
        "# Cluster Type-Conflict Analysis",
        "",
        "This analysis is review-only. It classifies type conflicts but does not create merge decisions.",
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
        f"- Classification: `{item.get('type_conflict_classification')}` risk `{item.get('review_risk_tier')}`",
        f"- Identity: `{item.get('identity_consistency')}`",
        f"- Projected reduction: `{item.get('projected_event_reduction')}`",
        f"- Blocking fields: {', '.join(string_list(item.get('blocking_fields'))) or 'none'}",
        f"- Type values: {', '.join(string_list(item.get('type_values'))) or 'none'}",
        f"- Type family prefixes: {', '.join(string_list(item.get('type_family_prefixes'))) or 'none'}",
        f"- Shape values: {', '.join(string_list(item.get('shape_values'))) or 'none'}",
        f"- Time values: {', '.join(string_list(item.get('time_values'))) or 'none'}",
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
    analysis = analyze_entity_resolution_cluster_type_conflicts(
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
