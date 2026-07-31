"""Plan effects for validated entity-resolution decisions without applying them."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from parser.canonical_schema import clean_text, stable_hash


DEFAULT_VALIDATED_DECISIONS = Path("data/canonical_full/entity_resolution_validated_decisions.jsonl")
DEFAULT_OUTPUT = Path("data/reports/entity_resolution_effects_plan.json")


def build_entity_resolution_effects_plan(
    *,
    validated_decisions: list[dict[str, Any]],
    validated_decisions_path: Path | None = None,
) -> dict[str, Any]:
    effects: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    seen_decision_ids: set[str] = set()
    seen_review_item_ids: set[str] = set()

    for decision_index, decision in enumerate(validated_decisions, start=1):
        decision_id = clean_text(decision.get("entity_resolution_decision_id"))
        review_item_id = clean_text(decision.get("review_item_id"))
        if not decision_id:
            warnings.append({"decision_index": decision_index, "warning": "missing_entity_resolution_decision_id"})
            continue
        if decision_id in seen_decision_ids:
            warnings.append(
                {
                    "decision_index": decision_index,
                    "entity_resolution_decision_id": decision_id,
                    "warning": "duplicate_decision_id_skipped",
                }
            )
            continue
        seen_decision_ids.add(decision_id)
        if review_item_id in seen_review_item_ids:
            warnings.append(
                {
                    "decision_index": decision_index,
                    "review_item_id": review_item_id,
                    "warning": "duplicate_review_item_id_skipped",
                }
            )
            continue
        if review_item_id:
            seen_review_item_ids.add(review_item_id)
        effects.append(plan_effect_for_decision(decision, decision_index=decision_index))

    return {
        "schema_version": 1,
        "effect_policy": "entity_resolution_plan_only",
        "canonical_outputs_mutated": False,
        "canonical_outputs_mutated_by_plan": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "inputs": {
            "validated_decisions": str(validated_decisions_path) if validated_decisions_path else None,
        },
        "validated_decision_count": len(validated_decisions),
        "planned_effect_count": len(effects),
        "effect_counts": count_by(effects, "planned_effect"),
        "decision_counts": count_by(effects, "decision"),
        "action_class_counts": count_by(effects, "action_class"),
        "requires_explicit_apply_step_count": sum(1 for effect in effects if effect.get("requires_explicit_apply_step")),
        "warnings": warnings,
        "safety_notes": [
            "This is a plan-only artifact.",
            "No deduped events, normalized events, source records, or web runtime files are mutated.",
            "Merge effects require a separate stream-safe preview/apply implementation.",
        ],
        "effects": effects,
    }


def plan_effect_for_decision(decision: dict[str, Any], *, decision_index: int) -> dict[str, Any]:
    decision_value = clean_text(decision.get("decision"))
    canonical_input_ids = string_list(decision.get("canonical_input_ids"))
    merge_event_ids = string_list(decision.get("merge_canonical_event_ids"))
    base = {
        "effect_id": stable_hash(
            {
                "decision_id": decision.get("entity_resolution_decision_id"),
                "decision": decision_value,
                "canonical_input_ids": canonical_input_ids,
                "merge_canonical_event_ids": merge_event_ids,
            },
            prefix="ere_",
            length=20,
        ),
        "decision_index": decision_index,
        "entity_resolution_decision_id": clean_text(decision.get("entity_resolution_decision_id")),
        "review_item_id": clean_text(decision.get("review_item_id")),
        "review_type": clean_text(decision.get("review_type")) or "entity_resolution_candidate",
        "decision": decision_value,
        "effect_status": "planned_not_applied",
        "effect_policy": "entity_resolution_plan_only",
        "canonical_outputs_mutated": False,
        "review_band": clean_text(decision.get("review_band")),
        "score": decision.get("score"),
        "canonical_input_ids": canonical_input_ids,
        "merge_canonical_event_ids": merge_event_ids,
        "reviewer": clean_text(decision.get("reviewer")),
        "reviewed_at": clean_text(decision.get("reviewed_at")),
        "notes": clean_text(decision.get("notes")),
    }
    if decision_value == "same_event":
        base.update(
            {
                "planned_effect": "merge_entity_resolution_candidate",
                "effect_type": "merge_entity_resolution_candidate",
                "action_class": "merge",
                "requires_explicit_apply_step": True,
                "reason": "Reviewer validated the ER candidate as one event; merge is planned but not applied.",
            }
        )
    elif decision_value == "distinct_events":
        base.update(
            {
                "planned_effect": "preserve_distinct_events",
                "effect_type": "preserve_distinct_events",
                "action_class": "preserve",
                "requires_explicit_apply_step": False,
                "reason": "Reviewer marked the ER candidate as distinct events.",
            }
        )
    else:
        base.update(
            {
                "planned_effect": "defer_entity_resolution_candidate",
                "effect_type": "defer_entity_resolution_candidate",
                "action_class": "defer",
                "requires_explicit_apply_step": False,
                "reason": "Reviewer marked the ER candidate as needing more evidence.",
            }
        )
    return base


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
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


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [text for item in value if (text := clean_text(item))]
    text = clean_text(value)
    return [text] if text else []


def count_by(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = clean_text(row.get(field)) or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validated-decisions", type=Path, default=DEFAULT_VALIDATED_DECISIONS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    validated_decisions = read_jsonl(args.validated_decisions)
    plan = build_entity_resolution_effects_plan(
        validated_decisions=validated_decisions,
        validated_decisions_path=args.validated_decisions,
    )
    write_json(args.output, plan)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "validated_decision_count": plan["validated_decision_count"],
                "planned_effect_count": plan["planned_effect_count"],
                "effect_counts": plan["effect_counts"],
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
