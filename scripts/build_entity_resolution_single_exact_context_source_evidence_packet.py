"""Build source evidence for single exact-time rows with context tokens.

This packet targets the medium-risk ``single_exact_minute_with_context_tokens``
time-normalization analysis items. It is review-only and does not create
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


DEFAULT_ANALYSIS = Path("data/reports/entity_resolution_cluster_time_normalization_analysis.json")
DEFAULT_DEDUPED_EVENTS = Path("data/canonical_full/deduped_events.jsonl")
DEFAULT_JSON_OUTPUT = Path("data/reports/entity_resolution_single_exact_context_source_evidence_packet.json")
DEFAULT_CSV_OUTPUT = Path("data/reports/entity_resolution_single_exact_context_source_evidence_packet.csv")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/entity_resolution_single_exact_context_source_evidence_packet.md")

INPUT_ANALYSIS_POLICY = "entity_resolution_cluster_time_normalization_review_only"
PACKET_POLICY = "entity_resolution_single_exact_context_source_evidence_review_only"
TARGET_CLASSIFICATION = "single_exact_minute_with_context_tokens"


def build_single_exact_context_source_evidence_packet(
    *,
    analysis: dict[str, Any],
    deduped_events_path: Path,
    analysis_path: Path | None = None,
) -> dict[str, Any]:
    validate_analysis_safety(analysis)
    analysis_items = target_analysis_items(analysis)
    effects = [effect_from_analysis_item(item, index=index) for index, item in enumerate(analysis_items, start=1)]
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
        "input_analysis_policy": analysis.get("analysis_policy"),
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "auto_merge_performed": False,
        "override_decisions_created": False,
        "ready_for_canonical_apply": False,
        "inputs": {
            "analysis": str(analysis_path) if analysis_path else None,
            "deduped_events": str(deduped_events_path),
        },
        "summary": {
            "target_classification": TARGET_CLASSIFICATION,
            "source_analysis_item_count": len(analysis.get("items") or []),
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
            "It targets single exact-minute time rows with fuzzy or context tokens attached.",
            "It does not create accepted ER decisions, apply merges, or mutate canonical outputs.",
        ],
    }


def validate_analysis_safety(analysis: dict[str, Any]) -> None:
    errors: list[str] = []
    if analysis.get("analysis_policy") != INPUT_ANALYSIS_POLICY:
        errors.append(f"analysis_policy must be {INPUT_ANALYSIS_POLICY}")
    for flag in (
        "canonical_outputs_mutated",
        "preview_outputs_written",
        "decisions_created",
        "decision_outputs_created",
        "auto_merge_performed",
        "override_decisions_created",
        "ready_for_canonical_apply",
    ):
        if analysis.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError("time-normalization analysis is unsafe for single-exact context export: " + "; ".join(errors))


def target_analysis_items(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    items = [
        item
        for item in analysis.get("items") or []
        if isinstance(item, dict)
        and clean_text(item.get("time_pattern_classification")) == TARGET_CLASSIFICATION
        and strict_identity_summary(item.get("source_summary"))
    ]
    return sorted(items, key=lambda item: (-as_int(item.get("projected_event_reduction")), clean_text(item.get("review_item_id"))))


def strict_identity_summary(summary_value: Any) -> bool:
    summary = summary_value if isinstance(summary_value, dict) else {}
    return (
        len(string_list(summary.get("source_names"))) == 1
        and len(string_list(summary.get("source_native_ids"))) == 1
        and len(string_list(summary.get("date_values"))) == 1
        and len(string_list(summary.get("location_values"))) == 1
        and len(string_list(summary.get("type_values"))) == 1
        and as_int(summary.get("canonical_event_count")) >= 2
    )


def effect_from_analysis_item(item: dict[str, Any], *, index: int) -> dict[str, Any]:
    summary = item.get("source_summary") if isinstance(item.get("source_summary"), dict) else {}
    return {
        "decision_index": index,
        "review_item_id": clean_text(item.get("review_item_id")),
        "effect_id": clean_text(item.get("effect_id")),
        "planned_effect": "merge_entity_resolution_candidate",
        "canonical_input_ids": string_list(summary.get("canonical_input_ids")),
        "merge_canonical_event_ids": string_list(summary.get("canonical_event_ids")),
        "projected_event_reduction": as_int(item.get("projected_event_reduction")),
        "shadow_preview_override_reason": TARGET_CLASSIFICATION,
        "shadow_preview_override_source": {
            "analysis_policy": PACKET_POLICY,
            "time_pattern_classification": clean_text(item.get("time_pattern_classification")),
            "review_risk_tier": clean_text(item.get("review_risk_tier")),
            "recommended_review_step": clean_text(item.get("recommended_review_step")),
            "blocking_fields": string_list(item.get("blocking_fields")),
            "time_tokens": string_list(item.get("time_tokens")),
            "parsed_minutes": int_list(item.get("parsed_minutes")),
            "fuzzy_labels": string_list(item.get("fuzzy_labels")),
            "ambiguous_tokens": string_list(item.get("ambiguous_tokens")),
            "unknown_tokens": string_list(item.get("unknown_tokens")),
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


def int_list(value: Any) -> list[int]:
    values: list[int] = []
    if not isinstance(value, list):
        return values
    for item in value:
        try:
            values.append(int(item))
        except (TypeError, ValueError):
            continue
    return values


def as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", type=Path, default=DEFAULT_ANALYSIS)
    parser.add_argument("--deduped-events", type=Path, default=DEFAULT_DEDUPED_EVENTS)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packet = build_single_exact_context_source_evidence_packet(
        analysis=read_json(args.analysis),
        deduped_events_path=args.deduped_events,
        analysis_path=args.analysis,
    )
    packet["outputs"] = {
        "json": str(args.json_output),
        "csv": str(args.csv_output),
        "markdown": str(args.markdown_output),
    }
    write_json(args.json_output, packet)
    write_csv(args.csv_output, packet)
    write_markdown(args.markdown_output, packet, item_limit=85, row_limit_per_item=8)
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
