"""Build source-row evidence for likely time-format cluster blockers.

This packet targets the high-confidence ``likely_time_format_variant`` items in
the time blocker action packet. It is review-only; it does not create
decisions, preview output, or canonical mutations.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.build_entity_resolution_cluster_time_norm_source_evidence_packet import (
    evidence_item_from_effect,
    load_requested_event_rows,
    write_csv,
    write_json,
    write_markdown,
)


DEFAULT_ACTION_PACKET = Path("data/reports/entity_resolution_cluster_time_blocker_action_packet.json")
DEFAULT_DEDUPED_EVENTS = Path("data/canonical_full/deduped_events.jsonl")
DEFAULT_JSON_OUTPUT = Path("data/reports/entity_resolution_cluster_likely_time_format_source_evidence_packet.json")
DEFAULT_CSV_OUTPUT = Path("data/reports/entity_resolution_cluster_likely_time_format_source_evidence_packet.csv")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/entity_resolution_cluster_likely_time_format_source_evidence_packet.md")

INPUT_PACKET_POLICY = "entity_resolution_blocked_merge_action_review_only"
PACKET_POLICY = "entity_resolution_likely_time_format_source_row_evidence_review_only"
TARGET_CLASSIFICATION = "likely_time_format_variant"
TARGET_SUGGESTED_ACTION = "candidate_shadow_preview_override"


def build_likely_time_format_source_evidence_packet(
    *,
    action_packet: dict[str, Any],
    deduped_events_path: Path,
    action_packet_path: Path | None = None,
) -> dict[str, Any]:
    validate_action_packet_safety(action_packet)
    action_items = likely_time_format_action_items(action_packet)
    effects = [effect_from_action_item(item, index=index) for index, item in enumerate(action_items, start=1)]
    requested_event_ids = sorted(
        {
            event_id
            for effect in effects
            for event_id in string_list(effect.get("merge_canonical_event_ids"))
        }
    )
    event_rows = load_requested_event_rows(deduped_events_path, requested_event_ids)
    missing_event_ids = sorted(set(requested_event_ids) - set(event_rows))
    items = [evidence_item_from_effect(effect, event_rows) for effect in effects]
    for index, item in enumerate(items, start=1):
        item["review_rank"] = index

    candidate_input_ids = sorted(
        {
            input_id
            for effect in effects
            for input_id in string_list(effect.get("canonical_input_ids"))
        }
    )
    evidence_input_ids = sorted(
        {
            input_id
            for row in event_rows.values()
            for input_id in string_list(row.get("canonical_input_ids"))
        }
    )
    missing_candidate_input_ids = sorted(set(candidate_input_ids) - set(evidence_input_ids))
    return {
        "schema_version": 1,
        "packet_policy": PACKET_POLICY,
        "input_packet_policy": action_packet.get("packet_policy"),
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "auto_merge_performed": False,
        "override_decisions_created": False,
        "ready_for_canonical_apply": False,
        "inputs": {
            "action_packet": str(action_packet_path) if action_packet_path else None,
            "deduped_events": str(deduped_events_path),
        },
        "summary": {
            "target_classification": TARGET_CLASSIFICATION,
            "target_suggested_action": TARGET_SUGGESTED_ACTION,
            "source_action_item_count": len(action_packet.get("items") or []),
            "candidate_effect_count": len(effects),
            "requested_canonical_event_id_count": len(requested_event_ids),
            "matched_canonical_event_id_count": len(event_rows),
            "missing_canonical_event_id_count": len(missing_event_ids),
            "candidate_input_id_count": len(candidate_input_ids),
            "evidence_input_id_count": len(evidence_input_ids),
            "candidate_input_ids_missing_from_evidence_count": len(missing_candidate_input_ids),
            "items_with_missing_events": sum(1 for item in items if item.get("missing_canonical_event_ids")),
            "projected_event_reduction": sum(
                max(0, len(string_list(effect.get("merge_canonical_event_ids"))) - 1) for effect in effects
            ),
        },
        "missing_canonical_event_ids": missing_event_ids,
        "candidate_input_ids": candidate_input_ids,
        "evidence_input_ids": evidence_input_ids,
        "candidate_input_ids_missing_from_evidence": missing_candidate_input_ids,
        "items": items,
        "notes": [
            "This packet is source-row evidence for review only.",
            "It targets high-confidence likely_time_format_variant blockers from the time action packet.",
            "It does not create accepted ER decisions, apply merges, or mutate canonical outputs.",
        ],
    }


def validate_action_packet_safety(packet: dict[str, Any]) -> None:
    errors: list[str] = []
    if packet.get("packet_policy") != INPUT_PACKET_POLICY:
        errors.append(f"packet_policy must be {INPUT_PACKET_POLICY}")
    for flag in (
        "canonical_outputs_mutated",
        "preview_outputs_written",
        "decisions_created",
        "auto_merge_performed",
    ):
        if packet.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError("time blocker action packet is unsafe for likely time-format evidence export: " + "; ".join(errors))


def likely_time_format_action_items(packet: dict[str, Any]) -> list[dict[str, Any]]:
    items = [
        item
        for item in packet.get("items") or []
        if isinstance(item, dict)
        and clean_text(item.get("classification")) == TARGET_CLASSIFICATION
        and clean_text(item.get("suggested_action")) == TARGET_SUGGESTED_ACTION
    ]
    return sorted(items, key=lambda item: clean_text(item.get("review_item_id")))


def effect_from_action_item(item: dict[str, Any], *, index: int) -> dict[str, Any]:
    summary = item.get("source_summary") if isinstance(item.get("source_summary"), dict) else {}
    return {
        "decision_index": index,
        "review_item_id": clean_text(item.get("review_item_id")),
        "effect_id": clean_text(item.get("effect_id")),
        "planned_effect": "merge_entity_resolution_candidate",
        "canonical_input_ids": string_list(summary.get("canonical_input_ids")),
        "merge_canonical_event_ids": string_list(summary.get("canonical_event_ids")),
        "projected_event_reduction": int(item.get("projected_event_reduction") or 0),
        "shadow_preview_override_reason": TARGET_CLASSIFICATION,
        "shadow_preview_override_source": {
            "analysis_policy": PACKET_POLICY,
            "classification": clean_text(item.get("classification")),
            "suggested_action": clean_text(item.get("suggested_action")),
            "analysis_confidence": clean_text(item.get("analysis_confidence")),
            "blocking_fields": string_list(item.get("blocking_fields")),
            "field_conflict_values": item.get("field_conflict_values") if isinstance(item.get("field_conflict_values"), dict) else {},
            "reasons": string_list(item.get("reasons")),
            "risks": string_list(item.get("risks")),
        },
    }


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [text for item in value if (text := clean_text(item))]
    text = clean_text(value)
    return [text] if text else []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action-packet", type=Path, default=DEFAULT_ACTION_PACKET)
    parser.add_argument("--deduped-events", type=Path, default=DEFAULT_DEDUPED_EVENTS)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packet = build_likely_time_format_source_evidence_packet(
        action_packet=read_json(args.action_packet),
        deduped_events_path=args.deduped_events,
        action_packet_path=args.action_packet,
    )
    packet["outputs"] = {
        "json": str(args.json_output),
        "csv": str(args.csv_output),
        "markdown": str(args.markdown_output),
    }
    write_json(args.json_output, packet)
    write_csv(args.csv_output, packet)
    write_markdown(args.markdown_output, packet, item_limit=80, row_limit_per_item=8)
    print(
        json.dumps(
            {
                "json_output": str(args.json_output),
                "packet_policy": packet["packet_policy"],
                "summary": packet["summary"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
