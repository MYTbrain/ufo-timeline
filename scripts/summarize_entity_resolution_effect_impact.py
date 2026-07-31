"""Summarize an entity-resolution effects plan without applying it.

Unlike manual-review duplicate effects, ER effects already carry the current
canonical event IDs they would merge, so this impact estimate does not need to
stream the multi-GB deduped-event corpus.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_EFFECTS_PLAN = Path("data/reports/entity_resolution_ai_effects_plan.json")
DEFAULT_OUTPUT = Path("data/reports/entity_resolution_ai_effect_impact_summary.json")


def summarize_entity_resolution_effect_impact(*, effects_plan: dict[str, Any], effects_plan_path: Path | None = None) -> dict[str, Any]:
    validate_plan_safety(effects_plan)
    effects = effects_plan.get("effects") if isinstance(effects_plan.get("effects"), list) else []
    merge_effects = [
        effect
        for effect in effects
        if isinstance(effect, dict) and effect.get("planned_effect") == "merge_entity_resolution_candidate"
    ]
    defer_effects = [
        effect
        for effect in effects
        if isinstance(effect, dict) and effect.get("planned_effect") == "defer_entity_resolution_candidate"
    ]
    preserve_effects = [
        effect
        for effect in effects
        if isinstance(effect, dict) and effect.get("planned_effect") == "preserve_distinct_events"
    ]

    merge_summaries = []
    touched_event_ids: set[str] = set()
    projected_event_reduction = 0
    merge_effects_with_insufficient_event_ids = 0

    for effect in merge_effects:
        event_ids = sorted(set(normalized_id_list(effect.get("merge_canonical_event_ids"))))
        touched_event_ids.update(event_ids)
        reduction = max(0, len(event_ids) - 1)
        projected_event_reduction += reduction
        if len(event_ids) <= 1:
            merge_effects_with_insufficient_event_ids += 1
        merge_summaries.append(
            {
                "effect_id": effect.get("effect_id"),
                "review_item_id": effect.get("review_item_id"),
                "review_band": effect.get("review_band"),
                "score": effect.get("score"),
                "merge_canonical_event_ids": event_ids,
                "projected_event_reduction": reduction,
                "requires_explicit_apply_step": bool(effect.get("requires_explicit_apply_step")),
            }
        )

    return {
        "schema_version": 1,
        "impact_policy": "entity_resolution_plan_impact_summary_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "inputs": {
            "effects_plan": str(effects_plan_path) if effects_plan_path else None,
        },
        "effect_counts": {
            "merge_entity_resolution_candidate": len(merge_effects),
            "defer_entity_resolution_candidate": len(defer_effects),
            "preserve_distinct_events": len(preserve_effects),
        },
        "merge_impact": {
            "merge_effects": len(merge_effects),
            "merge_effects_with_insufficient_event_ids": merge_effects_with_insufficient_event_ids,
            "touched_event_count": len(touched_event_ids),
            "projected_event_reduction": projected_event_reduction,
            "requires_explicit_apply_step_count": sum(
                1 for effect in merge_effects if bool(effect.get("requires_explicit_apply_step"))
            ),
        },
        "merge_samples": {
            "projected_merges": [item for item in merge_summaries if item["projected_event_reduction"] > 0][:25],
            "insufficient_event_ids": [
                item for item in merge_summaries if item["projected_event_reduction"] == 0
            ][:25],
        },
        "notes": [
            "This is an impact summary, not a preview apply.",
            "Projected reduction is computed from event IDs already present in the ER effects plan.",
            "No full deduped-event corpus is copied or mutated.",
        ],
    }


def validate_plan_safety(effects_plan: dict[str, Any]) -> None:
    errors: list[str] = []
    if effects_plan.get("effect_policy") != "entity_resolution_plan_only":
        errors.append("effect_policy must be 'entity_resolution_plan_only'")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "auto_merge_performed"):
        if effects_plan.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError(f"effects plan is not safe to summarize: {'; '.join(errors)}")


def normalized_id_list(value: Any) -> list[str]:
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if not isinstance(value, list):
        return []
    ids = []
    for item in value:
        text = str(item or "").strip()
        if text:
            ids.append(text)
    return ids


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--effects-plan", type=Path, default=DEFAULT_EFFECTS_PLAN)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    effects_plan = read_json(args.effects_plan)
    report = summarize_entity_resolution_effect_impact(effects_plan=effects_plan, effects_plan_path=args.effects_plan)
    write_json(args.output, report)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "impact_policy": report["impact_policy"],
                "merge_effects": report["merge_impact"]["merge_effects"],
                "projected_event_reduction": report["merge_impact"]["projected_event_reduction"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
