"""Validate reviewed entity-resolution cluster decisions without applying them.

Cluster review packets are opportunity targets, not decisions. This validator
turns explicit reviewer decisions into normalized ER decision records that can
then use the existing plan-only ER effects path. It never mutates canonical
outputs and it rejects same-event cluster decisions unless the packet carries a
complete exported current-event ID list for that cluster.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from parser.canonical_schema import clean_text, stable_hash


DEFAULT_PACKET_PATH = Path("data/reports/entity_resolution_cluster_review_packet.json")
DEFAULT_DECISIONS_PATH = Path("data/canonical_full/entity_resolution_cluster_decisions.jsonl")
DEFAULT_NORMALIZED_OUTPUT = Path("data/canonical_full/entity_resolution_validated_cluster_decisions.jsonl")
DEFAULT_REPORT_OUTPUT = Path("data/reports/entity_resolution_cluster_decisions_validation_report.json")

ALLOWED_DECISIONS = {"same_event", "distinct_events", "needs_more_evidence"}


def validate_entity_resolution_cluster_decisions(
    *,
    packet: dict[str, Any],
    decisions: list[dict[str, Any]],
    packet_path: Path | None = None,
    decisions_path: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    validate_cluster_packet_safety(packet)
    packet_items = packet.get("items") if isinstance(packet.get("items"), list) else []
    packet_by_id = {
        cluster_review_id: item
        for item in packet_items
        if isinstance(item, dict)
        if (cluster_review_id := clean_text(item.get("cluster_review_id")))
    }

    normalized: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    seen_cluster_review_ids: set[str] = set()

    for decision_index, decision in enumerate(decisions, start=1):
        cluster_review_id = clean_text(decision.get("cluster_review_id"))
        decision_value = clean_text(decision.get("decision"))
        if not cluster_review_id:
            invalid.append({"decision_index": decision_index, "error": "missing_cluster_review_id"})
            continue
        if cluster_review_id in seen_cluster_review_ids:
            invalid.append(
                {
                    "decision_index": decision_index,
                    "cluster_review_id": cluster_review_id,
                    "error": "duplicate_decision_for_cluster_review_id",
                }
            )
            continue
        seen_cluster_review_ids.add(cluster_review_id)
        packet_item = packet_by_id.get(cluster_review_id)
        if packet_item is None:
            invalid.append(
                {
                    "decision_index": decision_index,
                    "cluster_review_id": cluster_review_id,
                    "error": "cluster_review_id_not_in_packet",
                }
            )
            continue
        if decision_value not in ALLOWED_DECISIONS:
            invalid.append(
                {
                    "decision_index": decision_index,
                    "cluster_review_id": cluster_review_id,
                    "decision": decision_value,
                    "error": "invalid_decision",
                    "allowed_decisions": sorted(ALLOWED_DECISIONS),
                }
            )
            continue
        same_event_blocker = same_event_validation_blocker(packet_item, decision_value)
        if same_event_blocker:
            invalid.append(
                {
                    "decision_index": decision_index,
                    "cluster_review_id": cluster_review_id,
                    "decision": decision_value,
                    "error": same_event_blocker,
                }
            )
            continue
        normalized.append(
            normalize_cluster_decision_record(
                decision,
                packet_item=packet_item,
                decision_index=decision_index,
                decision_value=decision_value,
            )
        )

    report = {
        "schema_version": 1,
        "decision_policy": "entity_resolution_cluster_decision_validation_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "inputs": {
            "packet": str(packet_path) if packet_path else None,
            "decisions": str(decisions_path) if decisions_path else None,
        },
        "packet_item_count": len(packet_by_id),
        "input_decision_count": len(decisions),
        "valid_decision_count": len(normalized),
        "invalid_decision_count": len(invalid),
        "decision_counts": count_by(normalized, "decision"),
        "tier_counts": count_by(normalized, "review_band"),
        "planned_effect_counts": count_by(normalized, "planned_effect"),
        "invalid_decisions": invalid,
        "notes": [
            "Validated cluster decisions are still not applied.",
            "same_event cluster decisions require complete exported current_event_ids in the cluster packet.",
            "The output can be passed to plan_entity_resolution_effects.py for a plan-only effects artifact.",
        ],
    }
    return normalized, report


def validate_cluster_packet_safety(packet: dict[str, Any]) -> None:
    errors: list[str] = []
    if packet.get("packet_policy") != "entity_resolution_cluster_review_only":
        errors.append("packet_policy must be 'entity_resolution_cluster_review_only'")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "decisions_created", "auto_merge_performed"):
        if packet.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError(f"packet is not a safe ER cluster review input: {'; '.join(errors)}")


def same_event_validation_blocker(packet_item: dict[str, Any], decision_value: str | None) -> str | None:
    if decision_value != "same_event":
        return None
    current_event_ids = string_list(packet_item.get("current_event_ids"))
    unique_count = as_int(packet_item.get("unique_current_event_count")) or 0
    if len(current_event_ids) <= 1:
        return "same_event_requires_at_least_two_exported_current_event_ids"
    if bool(packet_item.get("current_event_ids_truncated")):
        return "same_event_requires_complete_current_event_ids"
    if unique_count and len(current_event_ids) != unique_count:
        return "same_event_current_event_id_count_mismatch"
    return None


def normalize_cluster_decision_record(
    decision: dict[str, Any],
    *,
    packet_item: dict[str, Any],
    decision_index: int,
    decision_value: str,
) -> dict[str, Any]:
    cluster_review_id = clean_text(packet_item.get("cluster_review_id"))
    current_event_ids = sorted(set(string_list(packet_item.get("current_event_ids"))))
    sample_input_ids = string_list(packet_item.get("sample_input_ids"))
    record = {
        "entity_resolution_decision_id": stable_hash(
            {
                "cluster_review_id": cluster_review_id,
                "decision": decision_value,
                "current_event_ids": current_event_ids,
            },
            prefix="erdc_",
            length=20,
        ),
        "decision_index": decision_index,
        "review_item_id": cluster_review_id,
        "cluster_review_id": cluster_review_id,
        "review_type": "entity_resolution_cluster_candidate",
        "decision": decision_value,
        "effect_status": "validated_not_applied",
        "canonical_outputs_mutated": False,
        "review_band": clean_text(packet_item.get("tier")),
        "family_id": clean_text(packet_item.get("family_id")),
        "family_description": clean_text(packet_item.get("family_description")),
        "key_hash": clean_text(packet_item.get("key_hash")),
        "projected_event_reduction": as_int(packet_item.get("projected_event_reduction")) or 0,
        "unique_current_event_count": as_int(packet_item.get("unique_current_event_count")) or 0,
        "source_record_count": as_int(packet_item.get("source_record_count")) or 0,
        "canonical_input_ids": sample_input_ids,
        "merge_canonical_event_ids": current_event_ids if decision_value == "same_event" else [],
        "reviewer": clean_text(decision.get("reviewer")),
        "reviewed_at": clean_text(decision.get("reviewed_at")),
        "notes": clean_text(decision.get("notes")),
        "evidence": {
            "source_names": string_list(packet_item.get("source_names")),
            "date_iso": clean_text(packet_item.get("date_iso")),
            "location": clean_text(packet_item.get("location")),
            "date_samples": string_list(packet_item.get("date_samples")),
            "location_samples": string_list(packet_item.get("location_samples")),
        },
        "risk_flags": cluster_risk_flags(packet_item),
    }
    if decision_value == "same_event":
        record["planned_effect"] = "merge_entity_resolution_candidate"
        record["requires_explicit_apply_step"] = True
    elif decision_value == "distinct_events":
        record["planned_effect"] = "preserve_distinct_events"
        record["requires_explicit_apply_step"] = False
    else:
        record["planned_effect"] = "defer_entity_resolution_candidate"
        record["requires_explicit_apply_step"] = False
    return record


def cluster_risk_flags(packet_item: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    if (as_int(packet_item.get("distinct_date_count")) or 0) > 1:
        flags.append("cluster_has_multiple_dates")
    if (as_int(packet_item.get("distinct_location_count")) or 0) > 1:
        flags.append("cluster_has_multiple_locations")
    if bool(packet_item.get("current_event_ids_truncated")):
        flags.append("cluster_current_event_ids_truncated")
    return flags


def read_decision_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict) and isinstance(payload.get("decisions"), list):
            return [item for item in payload["decisions"] if isinstance(item, dict)]
        raise ValueError(f"{path} must contain a JSON array or an object with a decisions array.")
    return read_jsonl(path)


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{path} line {line_number} must contain a JSON object.")
            records.append(payload)
    return records


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


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


def count_by(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = clean_text(row.get(field)) or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    parser.add_argument("--decisions", type=Path, default=DEFAULT_DECISIONS_PATH)
    parser.add_argument("--normalized-output", type=Path, default=DEFAULT_NORMALIZED_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packet = read_json(args.packet)
    decisions = read_decision_records(args.decisions)
    normalized, report = validate_entity_resolution_cluster_decisions(
        packet=packet,
        decisions=decisions,
        packet_path=args.packet,
        decisions_path=args.decisions,
    )
    write_jsonl(args.normalized_output, normalized)
    write_json(args.report_output, report)
    print(
        json.dumps(
            {
                "normalized_output": str(args.normalized_output),
                "report_output": str(args.report_output),
                "input_decision_count": report["input_decision_count"],
                "valid_decision_count": report["valid_decision_count"],
                "invalid_decision_count": report["invalid_decision_count"],
                "canonical_outputs_mutated": False,
                "auto_merge_performed": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
