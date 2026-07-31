"""Validate and normalize entity-resolution review decisions.

This is intentionally non-destructive. It validates reviewer-provided
decisions against the ER review packet and writes normalized decision records,
but it does not apply merges or mutate canonical artifacts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from parser.canonical_schema import clean_text, stable_hash


DEFAULT_PACKET_PATH = Path("data/reports/entity_resolution_review_packet.json")
DEFAULT_DECISIONS_PATH = Path("data/canonical_full/entity_resolution_decisions.jsonl")
DEFAULT_NORMALIZED_OUTPUT = Path("data/canonical_full/entity_resolution_validated_decisions.jsonl")
DEFAULT_REPORT_OUTPUT = Path("data/reports/entity_resolution_decisions_report.json")

ALLOWED_DECISIONS = {"same_event", "distinct_events", "needs_more_evidence"}


def validate_entity_resolution_decisions(
    *,
    packet: dict[str, Any],
    decisions: list[dict[str, Any]],
    packet_path: Path | None = None,
    decisions_path: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    packet_items = packet.get("items") if isinstance(packet.get("items"), list) else []
    packet_by_id = {
        review_item_id: item
        for item in packet_items
        if isinstance(item, dict)
        if (review_item_id := clean_text(item.get("review_item_id")))
    }

    normalized: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    seen_review_item_ids: set[str] = set()

    for decision_index, decision in enumerate(decisions, start=1):
        review_item_id = clean_text(decision.get("review_item_id"))
        decision_value = clean_text(decision.get("decision"))
        if not review_item_id:
            invalid.append({"decision_index": decision_index, "error": "missing_review_item_id"})
            continue
        if review_item_id in seen_review_item_ids:
            invalid.append(
                {
                    "decision_index": decision_index,
                    "review_item_id": review_item_id,
                    "error": "duplicate_decision_for_review_item",
                }
            )
            continue
        seen_review_item_ids.add(review_item_id)
        packet_item = packet_by_id.get(review_item_id)
        if packet_item is None:
            invalid.append(
                {
                    "decision_index": decision_index,
                    "review_item_id": review_item_id,
                    "error": "review_item_id_not_in_packet",
                }
            )
            continue
        if decision_value not in ALLOWED_DECISIONS:
            invalid.append(
                {
                    "decision_index": decision_index,
                    "review_item_id": review_item_id,
                    "decision": decision_value,
                    "error": "invalid_decision",
                    "allowed_decisions": sorted(ALLOWED_DECISIONS),
                }
            )
            continue

        record = normalize_decision_record(
            decision,
            packet_item=packet_item,
            decision_index=decision_index,
            decision_value=decision_value,
        )
        if decision_value == "same_event" and not packet_item.get("cross_current_event"):
            warnings.append(
                {
                    "decision_index": decision_index,
                    "review_item_id": review_item_id,
                    "warning": "same_event_for_non_cross_current_event_pair",
                }
            )
        normalized.append(record)

    report = {
        "schema_version": 1,
        "decision_policy": "entity_resolution_decision_validation_only",
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
        "review_band_counts": count_by(normalized, "review_band"),
        "planned_effect_counts": count_by(normalized, "planned_effect"),
        "invalid_decisions": invalid,
        "warnings": warnings,
        "notes": [
            "Validated decisions are still not applied.",
            "same_event decisions require a separate stream-safe effect planning and apply step before canonical outputs change.",
        ],
    }
    return normalized, report


def normalize_decision_record(
    decision: dict[str, Any],
    *,
    packet_item: dict[str, Any],
    decision_index: int,
    decision_value: str,
) -> dict[str, Any]:
    left = packet_item.get("left") if isinstance(packet_item.get("left"), dict) else {}
    right = packet_item.get("right") if isinstance(packet_item.get("right"), dict) else {}
    merge_event_ids = sorted(
        {
            event_id
            for event_id in [
                clean_text(left.get("canonical_event_id")),
                clean_text(right.get("canonical_event_id")),
            ]
            if event_id
        }
    )
    input_ids = [
        input_id
        for input_id in [
            clean_text(left.get("canonical_input_id")),
            clean_text(right.get("canonical_input_id")),
        ]
        if input_id
    ]
    record = {
        "entity_resolution_decision_id": stable_hash(
            {
                "review_item_id": packet_item.get("review_item_id"),
                "decision": decision_value,
                "input_ids": input_ids,
                "event_ids": merge_event_ids,
            },
            prefix="erd_",
            length=20,
        ),
        "decision_index": decision_index,
        "review_item_id": clean_text(packet_item.get("review_item_id")),
        "review_type": "entity_resolution_candidate",
        "decision": decision_value,
        "effect_status": "validated_not_applied",
        "canonical_outputs_mutated": False,
        "review_band": clean_text(packet_item.get("review_band")),
        "score": packet_item.get("score"),
        "cross_current_event": bool(packet_item.get("cross_current_event")),
        "canonical_input_ids": input_ids,
        "merge_canonical_event_ids": merge_event_ids,
        "reviewer": clean_text(decision.get("reviewer")),
        "reviewed_at": clean_text(decision.get("reviewed_at")),
        "notes": clean_text(decision.get("notes")),
        "evidence": packet_item.get("evidence") if isinstance(packet_item.get("evidence"), list) else [],
        "risk_flags": packet_item.get("risk_flags") if isinstance(packet_item.get("risk_flags"), list) else [],
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
    normalized, report = validate_entity_resolution_decisions(
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
