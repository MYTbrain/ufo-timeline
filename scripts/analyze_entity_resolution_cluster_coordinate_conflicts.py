"""Analyze coordinate conflicts in the cluster blocker priority queue.

This is review-only. It buckets coordinate-distance blockers by maximum spread
and preserves time/source identity context for map/source review. It does not
create decisions, override subsets, preview applies, or canonical mutations.
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
DEFAULT_JSON_OUTPUT = Path("data/reports/entity_resolution_cluster_coordinate_conflict_analysis.json")
DEFAULT_CSV_OUTPUT = Path("data/reports/entity_resolution_cluster_coordinate_conflict_analysis.csv")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/entity_resolution_cluster_coordinate_conflict_analysis.md")

ANALYSIS_POLICY = "entity_resolution_cluster_coordinate_conflict_review_only"

CSV_FIELDS = (
    "review_rank",
    "coordinate_conflict_classification",
    "review_risk_tier",
    "identity_consistency",
    "review_item_id",
    "effect_id",
    "projected_event_reduction",
    "blocking_fields",
    "max_coordinate_distance_km",
    "time_values",
    "type_values",
    "source_names",
    "source_native_ids",
    "date_values",
    "location_values",
    "canonical_event_id_count",
    "recommended_review_step",
)


def analyze_entity_resolution_cluster_coordinate_conflicts(
    *,
    priority_queue: dict[str, Any],
    priority_queue_path: Path | None = None,
) -> dict[str, Any]:
    validate_priority_queue_safety(priority_queue)
    items = []
    for queue_item in priority_queue.get("items") or []:
        if not isinstance(queue_item, dict):
            continue
        if clean_text(queue_item.get("triage_bucket")) != "coordinate_conflict_review":
            continue
        items.append(analyze_queue_item(queue_item))
    items.sort(key=coordinate_conflict_sort_key)
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
            "classification_counts": count_by(items, "coordinate_conflict_classification"),
            "review_risk_tier_counts": count_by(items, "review_risk_tier"),
            "identity_consistency_counts": count_by(items, "identity_consistency"),
            "projected_reduction_sum_not_deduped": sum(
                int(item.get("projected_event_reduction") or 0) for item in items
            ),
            "max_coordinate_distance_km": max(
                (float(item.get("max_coordinate_distance_km") or 0.0) for item in items),
                default=0.0,
            ),
        },
        "items": items,
        "notes": [
            "This analysis is review-only; it does not promote coordinate conflicts to merge decisions.",
            "All coordinate conflicts stay high risk until map/source-row review explains the spread.",
            "Projected reduction sums are not deduped across overlapping effects.",
        ],
    }


def analyze_queue_item(queue_item: dict[str, Any]) -> dict[str, Any]:
    conflicts = queue_item.get("field_conflict_values") if isinstance(queue_item.get("field_conflict_values"), dict) else {}
    source_summary = normalized_source_summary(queue_item.get("source_summary"))
    max_distance = extract_max_coordinate_distance(queue_item)
    classification = classify_coordinate_conflict(max_distance)
    return {
        "review_rank": None,
        "coordinate_conflict_classification": classification,
        "review_risk_tier": "high",
        "identity_consistency": classify_identity_consistency(source_summary),
        "recommended_review_step": recommended_review_step(classification),
        "review_item_id": clean_text(queue_item.get("review_item_id")),
        "effect_id": clean_text(queue_item.get("effect_id")),
        "patch_id": clean_text(queue_item.get("patch_id")),
        "projected_event_reduction": as_int(queue_item.get("projected_event_reduction")) or 0,
        "blocking_fields": string_list(queue_item.get("blocking_fields")),
        "max_coordinate_distance_km": max_distance,
        "time_values": sorted(set(string_list(conflicts.get("time_raw")) or string_list(source_summary.get("time_values")))),
        "type_values": sorted(set(string_list(conflicts.get("type_normalized")) or string_list(source_summary.get("type_values")))),
        "source_summary": source_summary,
    }


def extract_max_coordinate_distance(queue_item: dict[str, Any]) -> float:
    values = string_list(queue_item.get("reasons")) + string_list(queue_item.get("risks"))
    for value in values:
        match = re.search(r"max_coordinate_distance_km=([0-9]+(?:\.[0-9]+)?)", value)
        if match:
            return float(match.group(1))
    return 0.0


def classify_coordinate_conflict(max_distance_km: float) -> str:
    if max_distance_km <= 0:
        return "coordinate_conflict_distance_unknown"
    if max_distance_km <= 15:
        return "coordinate_conflict_10_to_15km"
    if max_distance_km <= 50:
        return "coordinate_conflict_15_to_50km"
    if max_distance_km <= 150:
        return "coordinate_conflict_50_to_150km"
    return "coordinate_conflict_over_150km"


def recommended_review_step(classification: str) -> str:
    if classification == "coordinate_conflict_10_to_15km":
        return "Review map/source rows for nearby geocode precision or facility-boundary spread."
    if classification == "coordinate_conflict_15_to_50km":
        return "Review map/source rows; this spread is too large for automatic merging."
    if classification == "coordinate_conflict_50_to_150km":
        return "Treat as likely separate locations unless source text proves a shared event."
    if classification == "coordinate_conflict_over_150km":
        return "Keep blocked; very large coordinate spread is incompatible with an automatic merge."
    return "Review manually; coordinate distance evidence is missing or malformed."


def coordinate_conflict_sort_key(item: dict[str, Any]) -> tuple[float, int, str]:
    return (
        float(item.get("max_coordinate_distance_km") or 0.0),
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
        "coordinate_conflict_classification": item.get("coordinate_conflict_classification"),
        "review_risk_tier": item.get("review_risk_tier"),
        "identity_consistency": item.get("identity_consistency"),
        "review_item_id": item.get("review_item_id"),
        "effect_id": item.get("effect_id"),
        "projected_event_reduction": item.get("projected_event_reduction"),
        "blocking_fields": "; ".join(string_list(item.get("blocking_fields"))),
        "max_coordinate_distance_km": item.get("max_coordinate_distance_km"),
        "time_values": "; ".join(string_list(item.get("time_values"))),
        "type_values": "; ".join(string_list(item.get("type_values"))),
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
        "# Cluster Coordinate-Conflict Analysis",
        "",
        "This analysis is review-only. It classifies coordinate conflicts but does not create merge decisions.",
        "",
        "## Summary",
        "",
        f"- Analyzed items: {summary.get('analyzed_item_count', 0)}",
        f"- Classification counts: `{json.dumps(summary.get('classification_counts', {}), sort_keys=True)}`",
        f"- Risk tier counts: `{json.dumps(summary.get('review_risk_tier_counts', {}), sort_keys=True)}`",
        f"- Identity consistency counts: `{json.dumps(summary.get('identity_consistency_counts', {}), sort_keys=True)}`",
        f"- Max coordinate distance km: `{summary.get('max_coordinate_distance_km', 0)}`",
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
        f"- Classification: `{item.get('coordinate_conflict_classification')}` risk `{item.get('review_risk_tier')}`",
        f"- Identity: `{item.get('identity_consistency')}`",
        f"- Max coordinate distance km: `{item.get('max_coordinate_distance_km')}`",
        f"- Projected reduction: `{item.get('projected_event_reduction')}`",
        f"- Blocking fields: {', '.join(string_list(item.get('blocking_fields'))) or 'none'}",
        f"- Time values: {', '.join(string_list(item.get('time_values'))) or 'none'}",
        f"- Type values: {', '.join(string_list(item.get('type_values'))) or 'none'}",
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
    analysis = analyze_entity_resolution_cluster_coordinate_conflicts(
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
