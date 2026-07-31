"""Filter an ER effects plan to only merge effects that passed readiness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_EFFECTS_PLAN = Path("data/reports/entity_resolution_ai_effects_plan.json")
DEFAULT_READINESS = Path("data/reports/entity_resolution_ai_merge_readiness.json")
DEFAULT_OUTPUT = Path("data/reports/entity_resolution_ai_effects_plan_ready_subset.json")


def filter_entity_resolution_effects_plan_by_readiness(
    *,
    effects_plan: dict[str, Any],
    readiness_report: dict[str, Any],
    effects_plan_path: Path | None = None,
    readiness_path: Path | None = None,
) -> dict[str, Any]:
    validate_effects_plan(effects_plan)
    validate_readiness_report(readiness_report)
    blocking_items = (
        readiness_report.get("blocking_items")
        if isinstance(readiness_report.get("blocking_items"), list)
        else readiness_report.get("blocking_items_sample")
    )
    blocked_review_item_ids = {
        str(item.get("review_item_id"))
        for item in blocking_items or []
        if isinstance(item, dict) and item.get("review_item_id")
    }
    source_effects = effects_plan.get("effects") if isinstance(effects_plan.get("effects"), list) else []
    selected_effects = []
    excluded_effects = []
    passthrough_non_merge_effect_count = 0

    for effect in source_effects:
        if not isinstance(effect, dict):
            continue
        if effect.get("planned_effect") != "merge_entity_resolution_candidate":
            passthrough_non_merge_effect_count += 1
            continue
        review_item_id = str(effect.get("review_item_id") or "")
        if review_item_id in blocked_review_item_ids:
            excluded_effects.append(
                {
                    "effect_id": effect.get("effect_id"),
                    "review_item_id": review_item_id,
                    "planned_effect": effect.get("planned_effect"),
                    "reason": "blocked_by_merge_readiness_gate",
                }
            )
            continue
        selected_effects.append(effect)

    return {
        "schema_version": 1,
        "effect_policy": "entity_resolution_plan_only",
        "subset_policy": "entity_resolution_ready_subset_for_shadow_preview",
        "canonical_outputs_mutated": False,
        "canonical_outputs_mutated_by_plan": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "inputs": {
            "effects_plan": str(effects_plan_path) if effects_plan_path else None,
            "readiness_report": str(readiness_path) if readiness_path else None,
        },
        "source_effect_count": len(source_effects),
        "selected_merge_effect_count": len(selected_effects),
        "excluded_merge_effect_count": len(excluded_effects),
        "passthrough_non_merge_effect_count": passthrough_non_merge_effect_count,
        "blocked_review_item_ids": sorted(blocked_review_item_ids),
        "excluded_effects": excluded_effects,
        "effects": selected_effects,
        "safety_notes": [
            "This subset is intended for shadow preview only.",
            "Blocked merge effects remain excluded until their conflicts are reviewed.",
            "Canonical outputs are not mutated by this filter step.",
        ],
    }


def validate_effects_plan(effects_plan: dict[str, Any]) -> None:
    errors: list[str] = []
    if effects_plan.get("effect_policy") != "entity_resolution_plan_only":
        errors.append("effect_policy must be 'entity_resolution_plan_only'")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "auto_merge_performed"):
        if effects_plan.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError(f"effects plan is not safe to filter: {'; '.join(errors)}")


def validate_readiness_report(readiness_report: dict[str, Any]) -> None:
    errors: list[str] = []
    if readiness_report.get("readiness_policy") != "entity_resolution_merge_preview_readiness_gate":
        errors.append("readiness_policy must be 'entity_resolution_merge_preview_readiness_gate'")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "auto_merge_performed"):
        if readiness_report.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError(f"readiness report is not safe to filter with: {'; '.join(errors)}")


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
    parser.add_argument("--readiness-report", type=Path, default=DEFAULT_READINESS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    effects_plan = read_json(args.effects_plan)
    readiness_report = read_json(args.readiness_report)
    subset = filter_entity_resolution_effects_plan_by_readiness(
        effects_plan=effects_plan,
        readiness_report=readiness_report,
        effects_plan_path=args.effects_plan,
        readiness_path=args.readiness_report,
    )
    write_json(args.output, subset)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "subset_policy": subset["subset_policy"],
                "selected_merge_effect_count": subset["selected_merge_effect_count"],
                "excluded_merge_effect_count": subset["excluded_merge_effect_count"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
