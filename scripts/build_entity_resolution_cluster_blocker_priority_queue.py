"""Build a prioritized review queue for remaining cluster ER blockers.

This artifact is review-only. It ranks blocked cluster merge candidates for
the next triage pass without creating decisions, override approvals, previews,
or canonical mutations.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from parser.canonical_schema import clean_text


DEFAULT_ACTION_PACKET = Path("data/reports/entity_resolution_cluster_blocked_merge_action_packet.json")
DEFAULT_OVERRIDE_SUBSET = Path("data/reports/entity_resolution_cluster_ai_effects_plan_shadow_override_subset.json")
DEFAULT_JSON_OUTPUT = Path("data/reports/entity_resolution_cluster_blocker_priority_queue.json")
DEFAULT_CSV_OUTPUT = Path("data/reports/entity_resolution_cluster_blocker_priority_queue.csv")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/entity_resolution_cluster_blocker_priority_queue.md")

QUEUE_POLICY = "entity_resolution_cluster_blocker_priority_queue_review_only"

CSV_FIELDS = (
    "priority_index",
    "triage_bucket",
    "risk_tier",
    "review_item_id",
    "effect_id",
    "classification",
    "suggested_action",
    "analysis_confidence",
    "projected_event_reduction",
    "blocking_fields",
    "time_values",
    "type_values",
    "source_names",
    "source_native_ids",
    "canonical_event_id_count",
    "canonical_event_ids",
    "canonical_input_ids",
    "date_values",
    "location_values",
    "review_rationale",
)


TRIAGE_BUCKETS: dict[str, dict[str, Any]] = {
    "time_format_review": {
        "order": 10,
        "risk_tier": "medium",
        "next_action": "Review normalized time variants; promote only rows that are true time-format duplicates.",
    },
    "time_conflict_review": {
        "order": 20,
        "risk_tier": "medium_high",
        "next_action": "Review time conflicts against source rows before any override; many may represent separate sightings.",
    },
    "type_conflict_review": {
        "order": 30,
        "risk_tier": "medium_high",
        "next_action": "Review source subtype/type conflicts; only same-source subcode variants should graduate.",
    },
    "coordinate_conflict_review": {
        "order": 40,
        "risk_tier": "high",
        "next_action": "Review manually with map/source context; coordinate conflicts stay conservative.",
    },
    "already_selected_shadow_override": {
        "order": 90,
        "risk_tier": "handled",
        "next_action": "Already covered by the current shadow-override subset; do not re-triage unless policy changes.",
    },
    "other_review": {
        "order": 80,
        "risk_tier": "unknown",
        "next_action": "Review manually; no narrower queue rule matched.",
    },
}


def build_entity_resolution_cluster_blocker_priority_queue(
    *,
    action_packet: dict[str, Any],
    action_packet_path: Path | None = None,
    override_subset: dict[str, Any] | None = None,
    override_subset_path: Path | None = None,
    include_already_selected: bool = False,
) -> dict[str, Any]:
    validate_action_packet_safety(action_packet)
    selected_review_item_ids = extract_override_review_item_ids(override_subset)
    items: list[dict[str, Any]] = []
    skipped_already_selected_count = 0
    for raw_item in action_packet.get("items") or []:
        if not isinstance(raw_item, dict):
            continue
        review_item_id = clean_text(raw_item.get("review_item_id"))
        already_selected = bool(review_item_id and review_item_id in selected_review_item_ids)
        if already_selected and not include_already_selected:
            skipped_already_selected_count += 1
            continue
        items.append(priority_queue_item(raw_item, already_selected=already_selected))

    items.sort(key=priority_sort_key)
    for index, item in enumerate(items, start=1):
        item["priority_index"] = index

    bucket_summaries = summarize_buckets(items)
    return {
        "schema_version": 1,
        "queue_policy": QUEUE_POLICY,
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "auto_merge_performed": False,
        "inputs": {
            "action_packet": str(action_packet_path) if action_packet_path else None,
            "override_subset": str(override_subset_path) if override_subset_path else None,
        },
        "queue_scope": (
            "remaining_cluster_blockers_excluding_current_shadow_override_subset"
            if selected_review_item_ids and not include_already_selected
            else "all_cluster_blockers"
        ),
        "include_already_selected": include_already_selected,
        "summary": {
            "source_action_item_count": len([item for item in action_packet.get("items") or [] if isinstance(item, dict)]),
            "override_subset_review_item_count": len(selected_review_item_ids),
            "skipped_already_selected_count": skipped_already_selected_count,
            "queue_item_count": len(items),
            "classification_counts": count_by(items, "classification"),
            "triage_bucket_counts": count_by(items, "triage_bucket"),
            "risk_tier_counts": count_by(items, "risk_tier"),
            "projected_reduction_sum_not_deduped": sum(
                int(item.get("projected_event_reduction") or 0) for item in items
            ),
        },
        "bucket_summaries": bucket_summaries,
        "items": items,
        "notes": [
            "This queue is review-only and does not create accepted ER decisions.",
            "Projected reduction sums are not deduped across overlapping effects.",
            "Items already selected by the current shadow override subset are excluded by default.",
        ],
    }


def priority_queue_item(raw_item: dict[str, Any], *, already_selected: bool) -> dict[str, Any]:
    triage_bucket = "already_selected_shadow_override" if already_selected else classify_triage_bucket(raw_item)
    bucket_meta = TRIAGE_BUCKETS.get(triage_bucket, TRIAGE_BUCKETS["other_review"])
    source_summary = raw_item.get("source_summary") if isinstance(raw_item.get("source_summary"), dict) else {}
    conflict_values = raw_item.get("field_conflict_values") if isinstance(raw_item.get("field_conflict_values"), dict) else {}
    return {
        "priority_index": None,
        "triage_bucket": triage_bucket,
        "risk_tier": bucket_meta["risk_tier"],
        "review_rationale": build_review_rationale(raw_item, triage_bucket),
        "review_item_id": clean_text(raw_item.get("review_item_id")),
        "patch_id": clean_text(raw_item.get("patch_id")),
        "effect_id": clean_text(raw_item.get("effect_id")),
        "classification": clean_text(raw_item.get("classification")) or "unknown",
        "suggested_action": clean_text(raw_item.get("suggested_action")) or "needs_human_review",
        "analysis_confidence": clean_text(raw_item.get("analysis_confidence")) or "unknown",
        "projected_event_reduction": as_int(raw_item.get("projected_event_reduction")) or 0,
        "blocking_fields": string_list(raw_item.get("blocking_fields")),
        "field_conflict_values": {
            "time_raw": string_list(conflict_values.get("time_raw")),
            "type_normalized": string_list(conflict_values.get("type_normalized")),
            "shape_normalized": string_list(conflict_values.get("shape_normalized")),
        },
        "source_summary": {
            "canonical_event_ids": string_list(source_summary.get("canonical_event_ids")),
            "canonical_input_ids": string_list(source_summary.get("canonical_input_ids")),
            "canonical_event_count": as_int(source_summary.get("canonical_event_count"))
            or len(string_list(source_summary.get("canonical_event_ids"))),
            "canonical_input_id_count": as_int(source_summary.get("canonical_input_id_count"))
            or len(string_list(source_summary.get("canonical_input_ids"))),
            "source_names": string_list(source_summary.get("source_names")),
            "source_native_ids": string_list(source_summary.get("source_native_ids")),
            "date_values": string_list(source_summary.get("date_values")),
            "time_values": string_list(source_summary.get("time_values")),
            "location_values": string_list(source_summary.get("location_values")),
            "type_values": string_list(source_summary.get("type_values")),
            "source_event_count": as_int(source_summary.get("source_event_count")) or 0,
        },
        "reasons": string_list(raw_item.get("reasons")),
        "risks": string_list(raw_item.get("risks")),
    }


def classify_triage_bucket(item: dict[str, Any]) -> str:
    classification = clean_text(item.get("classification"))
    blocking_fields = set(string_list(item.get("blocking_fields")))
    if classification == "time_format_or_multiple_time_variant":
        return "time_format_review"
    if classification == "time_conflict_requires_review":
        return "time_conflict_review"
    if classification == "type_conflict_requires_review" or "type_normalized" in blocking_fields:
        return "type_conflict_review"
    if classification == "coordinate_conflict_requires_review" or "coordinate_distance_over_10km" in blocking_fields:
        return "coordinate_conflict_review"
    return "other_review"


def build_review_rationale(item: dict[str, Any], triage_bucket: str) -> str:
    bucket_action = TRIAGE_BUCKETS.get(triage_bucket, TRIAGE_BUCKETS["other_review"])["next_action"]
    projected_reduction = as_int(item.get("projected_event_reduction")) or 0
    blocking_fields = ", ".join(string_list(item.get("blocking_fields"))) or "none"
    return f"{bucket_action} Blocking fields: {blocking_fields}. Projected reduction: {projected_reduction}."


def priority_sort_key(item: dict[str, Any]) -> tuple[int, int, int, str, str]:
    bucket = clean_text(item.get("triage_bucket")) or "other_review"
    bucket_order = int(TRIAGE_BUCKETS.get(bucket, TRIAGE_BUCKETS["other_review"])["order"])
    return (
        bucket_order,
        -int(item.get("projected_event_reduction") or 0),
        len(string_list(item.get("blocking_fields"))),
        str(item.get("classification") or ""),
        str(item.get("review_item_id") or ""),
    )


def summarize_buckets(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_bucket: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        bucket = clean_text(item.get("triage_bucket")) or "other_review"
        by_bucket.setdefault(bucket, []).append(item)
    summaries = []
    for bucket, bucket_items in by_bucket.items():
        meta = TRIAGE_BUCKETS.get(bucket, TRIAGE_BUCKETS["other_review"])
        summaries.append(
            {
                "triage_bucket": bucket,
                "risk_tier": meta["risk_tier"],
                "item_count": len(bucket_items),
                "projected_reduction_sum_not_deduped": sum(
                    int(item.get("projected_event_reduction") or 0) for item in bucket_items
                ),
                "suggested_next_action": meta["next_action"],
                "top_review_item_ids": [item.get("review_item_id") for item in bucket_items[:10]],
            }
        )
    summaries.sort(key=lambda summary: int(TRIAGE_BUCKETS.get(summary["triage_bucket"], TRIAGE_BUCKETS["other_review"])["order"]))
    return summaries


def validate_action_packet_safety(packet: dict[str, Any]) -> None:
    errors: list[str] = []
    if packet.get("packet_policy") != "entity_resolution_blocked_merge_action_review_only":
        errors.append("action packet policy must be 'entity_resolution_blocked_merge_action_review_only'")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "decisions_created", "auto_merge_performed"):
        if packet.get(flag) is not False:
            errors.append(f"action packet {flag} must be false")
    if errors:
        raise ValueError(f"input is not safe for cluster blocker priority queue: {'; '.join(errors)}")


def extract_override_review_item_ids(override_subset: dict[str, Any] | None) -> set[str]:
    if not override_subset:
        return set()
    errors: list[str] = []
    if override_subset.get("subset_policy") != "entity_resolution_shadow_preview_subset_with_analysis_overrides":
        errors.append("override subset policy must be 'entity_resolution_shadow_preview_subset_with_analysis_overrides'")
    for flag in (
        "canonical_outputs_mutated",
        "canonical_outputs_mutated_by_plan",
        "preview_outputs_written",
        "auto_merge_performed",
        "override_decisions_created",
    ):
        if override_subset.get(flag) is not False:
            errors.append(f"override subset {flag} must be false")
    if errors:
        raise ValueError(f"override subset is not safe for cluster blocker priority queue: {'; '.join(errors)}")
    return {text for value in override_subset.get("override_review_item_ids") or [] if (text := clean_text(value))}


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for item in items:
            writer.writerow(csv_row(item))


def csv_row(item: dict[str, Any]) -> dict[str, Any]:
    source_summary = item.get("source_summary") if isinstance(item.get("source_summary"), dict) else {}
    conflicts = item.get("field_conflict_values") if isinstance(item.get("field_conflict_values"), dict) else {}
    return {
        "priority_index": item.get("priority_index"),
        "triage_bucket": item.get("triage_bucket"),
        "risk_tier": item.get("risk_tier"),
        "review_item_id": item.get("review_item_id"),
        "effect_id": item.get("effect_id"),
        "classification": item.get("classification"),
        "suggested_action": item.get("suggested_action"),
        "analysis_confidence": item.get("analysis_confidence"),
        "projected_event_reduction": item.get("projected_event_reduction"),
        "blocking_fields": "; ".join(string_list(item.get("blocking_fields"))),
        "time_values": "; ".join(string_list(conflicts.get("time_raw")) or string_list(source_summary.get("time_values"))),
        "type_values": "; ".join(string_list(conflicts.get("type_normalized")) or string_list(source_summary.get("type_values"))),
        "source_names": "; ".join(string_list(source_summary.get("source_names"))),
        "source_native_ids": "; ".join(string_list(source_summary.get("source_native_ids"))),
        "canonical_event_id_count": source_summary.get("canonical_event_count") or len(string_list(source_summary.get("canonical_event_ids"))),
        "canonical_event_ids": "; ".join(string_list(source_summary.get("canonical_event_ids"))[:20]),
        "canonical_input_ids": "; ".join(string_list(source_summary.get("canonical_input_ids"))[:20]),
        "date_values": "; ".join(string_list(source_summary.get("date_values"))),
        "location_values": "; ".join(string_list(source_summary.get("location_values"))),
        "review_rationale": item.get("review_rationale"),
    }


def write_markdown(path: Path, queue: dict[str, Any], *, item_limit: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = queue.get("summary") if isinstance(queue.get("summary"), dict) else {}
    lines = [
        "# Cluster Blocker Priority Queue",
        "",
        "This queue is review-only. It ranks remaining cluster merge blockers for triage and does not apply decisions.",
        "",
        "## Summary",
        "",
        f"- Queue items: {summary.get('queue_item_count', 0)}",
        f"- Skipped already-selected shadow overrides: {summary.get('skipped_already_selected_count', 0)}",
        f"- Triage bucket counts: `{json.dumps(summary.get('triage_bucket_counts', {}), sort_keys=True)}`",
        f"- Canonical outputs mutated: `{str(queue.get('canonical_outputs_mutated')).lower()}`",
        "",
        "## Buckets",
        "",
    ]
    for bucket in queue.get("bucket_summaries") or []:
        if not isinstance(bucket, dict):
            continue
        lines.extend(
            [
                f"### {bucket.get('triage_bucket')}",
                "",
                f"- Items: `{bucket.get('item_count', 0)}`",
                f"- Risk tier: `{bucket.get('risk_tier')}`",
                f"- Suggested next action: {bucket.get('suggested_next_action')}",
                f"- Top review IDs: {', '.join(string_list(bucket.get('top_review_item_ids'))) or 'none'}",
                "",
            ]
        )
    lines.extend(["## Top Items", ""])
    for item in (queue.get("items") or [])[: max(0, item_limit)]:
        if not isinstance(item, dict):
            continue
        lines.extend(markdown_item_lines(item))
    if len(queue.get("items") or []) > item_limit:
        lines.extend(["", f"_Markdown limited to {item_limit} of {len(queue.get('items') or [])} queue items._", ""])
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def markdown_item_lines(item: dict[str, Any]) -> list[str]:
    source_summary = item.get("source_summary") if isinstance(item.get("source_summary"), dict) else {}
    conflicts = item.get("field_conflict_values") if isinstance(item.get("field_conflict_values"), dict) else {}
    return [
        f"### #{item.get('priority_index')} {item.get('review_item_id')}",
        "",
        f"- Bucket: `{item.get('triage_bucket')}` risk `{item.get('risk_tier')}`",
        f"- Classification: `{item.get('classification')}` action `{item.get('suggested_action')}` confidence `{item.get('analysis_confidence')}`",
        f"- Projected reduction: `{item.get('projected_event_reduction')}`",
        f"- Canonical event IDs: `{source_summary.get('canonical_event_count') or 0}`",
        f"- Blocking fields: {', '.join(string_list(item.get('blocking_fields'))) or 'none'}",
        f"- Time values: {', '.join(string_list(conflicts.get('time_raw')) or string_list(source_summary.get('time_values'))) or 'none'}",
        f"- Type values: {', '.join(string_list(conflicts.get('type_normalized')) or string_list(source_summary.get('type_values'))) or 'none'}",
        f"- Locations: {', '.join(string_list(source_summary.get('location_values'))) or 'none'}",
        f"- Review rationale: {item.get('review_rationale') or 'none'}",
        "",
    ]


def string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [text for item in value if (text := clean_text(item))]
    text = clean_text(value)
    return [text] if text else []


def as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def count_by(items: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = clean_text(item.get(field)) or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action-packet", type=Path, default=DEFAULT_ACTION_PACKET)
    parser.add_argument("--override-subset", type=Path, default=DEFAULT_OVERRIDE_SUBSET)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument("--include-already-selected", action="store_true")
    parser.add_argument("--markdown-item-limit", type=int, default=100)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    action_packet = read_json(args.action_packet)
    override_subset = read_json(args.override_subset) if args.override_subset.exists() else None
    queue = build_entity_resolution_cluster_blocker_priority_queue(
        action_packet=action_packet,
        action_packet_path=args.action_packet,
        override_subset=override_subset,
        override_subset_path=args.override_subset if override_subset else None,
        include_already_selected=args.include_already_selected,
    )
    write_json(args.json_output, queue)
    write_csv(args.csv_output, queue["items"])
    write_markdown(args.markdown_output, queue, item_limit=args.markdown_item_limit)
    print(
        json.dumps(
            {
                "json_output": str(args.json_output),
                "csv_output": str(args.csv_output),
                "markdown_output": str(args.markdown_output),
                "queue_item_count": queue["summary"]["queue_item_count"],
                "skipped_already_selected_count": queue["summary"]["skipped_already_selected_count"],
                "triage_bucket_counts": queue["summary"]["triage_bucket_counts"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
