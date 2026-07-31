"""Build a shadow-preview ER effects subset with explicit blocked-merge overrides."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any


DEFAULT_EFFECTS_PLAN = Path("data/reports/entity_resolution_ai_effects_plan.json")
DEFAULT_READY_SUBSET = Path("data/reports/entity_resolution_ai_effects_plan_ready_subset.json")
DEFAULT_BLOCKED_ANALYSIS = Path("data/reports/entity_resolution_blocked_merge_analysis.json")
DEFAULT_OUTPUT = Path("data/reports/entity_resolution_ai_effects_plan_shadow_override_subset.json")


def build_entity_resolution_shadow_override_effects_plan(
    *,
    effects_plan: dict[str, Any],
    ready_subset: dict[str, Any],
    blocked_analysis: dict[str, Any],
    effects_plan_path: Path | None = None,
    ready_subset_path: Path | None = None,
    blocked_analysis_path: Path | None = None,
) -> dict[str, Any]:
    validate_effects_plan(effects_plan)
    validate_ready_subset(ready_subset)
    validate_blocked_analysis(blocked_analysis)

    source_effects = effects_plan.get("effects") if isinstance(effects_plan.get("effects"), list) else []
    source_by_review_id = {
        str(effect.get("review_item_id")): effect
        for effect in source_effects
        if isinstance(effect, dict) and effect.get("review_item_id")
    }
    baseline_effects = [
        copy.deepcopy(effect)
        for effect in ready_subset.get("effects") or []
        if isinstance(effect, dict) and effect.get("planned_effect") == "merge_entity_resolution_candidate"
    ]
    baseline_review_ids = {str(effect.get("review_item_id")) for effect in baseline_effects}

    override_candidates = [
        item
        for item in blocked_analysis.get("items") or []
        if isinstance(item, dict)
        and item.get("suggested_action") == "candidate_shadow_preview_override"
        and item.get("analysis_confidence") == "high"
    ]

    override_effects = []
    override_not_found = []
    for candidate in override_candidates:
        review_item_id = str(candidate.get("review_item_id") or "")
        if not review_item_id or review_item_id in baseline_review_ids:
            continue
        source_effect = source_by_review_id.get(review_item_id)
        if not source_effect or source_effect.get("planned_effect") != "merge_entity_resolution_candidate":
            override_not_found.append(review_item_id)
            continue
        effect = copy.deepcopy(source_effect)
        effect["shadow_preview_override"] = True
        effect["shadow_preview_override_reason"] = candidate.get("classification")
        effect["shadow_preview_override_source"] = {
            "analysis_policy": blocked_analysis.get("analysis_policy"),
            "analysis_confidence": candidate.get("analysis_confidence"),
            "blocking_fields": candidate.get("blocking_fields") or [],
        }
        override_effects.append(effect)

    effects = sorted(
        baseline_effects + override_effects,
        key=lambda effect: int(effect.get("decision_index") or 0),
    )
    excluded_after_override = [
        effect
        for effect in ready_subset.get("excluded_effects") or []
        if isinstance(effect, dict) and str(effect.get("review_item_id") or "") not in {item.get("review_item_id") for item in override_effects}
    ]

    return {
        "schema_version": 1,
        "effect_policy": "entity_resolution_plan_only",
        "subset_policy": "entity_resolution_shadow_preview_subset_with_analysis_overrides",
        "canonical_outputs_mutated": False,
        "canonical_outputs_mutated_by_plan": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "override_decisions_created": False,
        "ready_for_canonical_apply": False,
        "inputs": {
            "effects_plan": str(effects_plan_path) if effects_plan_path else None,
            "ready_subset": str(ready_subset_path) if ready_subset_path else None,
            "blocked_merge_analysis": str(blocked_analysis_path) if blocked_analysis_path else None,
        },
        "source_effect_count": len(source_effects),
        "baseline_selected_merge_effect_count": len(baseline_effects),
        "override_selected_merge_effect_count": len(override_effects),
        "selected_merge_effect_count": len(effects),
        "excluded_merge_effect_count": len(excluded_after_override),
        "override_not_found_review_item_ids": sorted(override_not_found),
        "override_review_item_ids": sorted(str(effect.get("review_item_id")) for effect in override_effects),
        "excluded_effects": excluded_after_override,
        "effects": effects,
        "safety_notes": [
            "This subset is intended for shadow preview only.",
            "Only high-confidence blocked-merge analysis candidates are included as overrides.",
            "No accepted ER decisions are created by this step.",
            "Canonical outputs are not mutated by this step.",
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
        raise ValueError(f"effects plan is not safe for shadow override filtering: {'; '.join(errors)}")


def validate_ready_subset(ready_subset: dict[str, Any]) -> None:
    errors: list[str] = []
    if ready_subset.get("subset_policy") != "entity_resolution_ready_subset_for_shadow_preview":
        errors.append("subset_policy must be 'entity_resolution_ready_subset_for_shadow_preview'")
    if ready_subset.get("effect_policy") != "entity_resolution_plan_only":
        errors.append("effect_policy must be 'entity_resolution_plan_only'")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "auto_merge_performed"):
        if ready_subset.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError(f"ready subset is not safe for shadow override filtering: {'; '.join(errors)}")


def validate_blocked_analysis(blocked_analysis: dict[str, Any]) -> None:
    errors: list[str] = []
    if blocked_analysis.get("analysis_policy") != "entity_resolution_blocked_merge_analysis_only":
        errors.append("analysis_policy must be 'entity_resolution_blocked_merge_analysis_only'")
    for flag in (
        "canonical_outputs_mutated",
        "preview_outputs_written",
        "decisions_created",
        "auto_merge_performed",
        "override_decisions_created",
    ):
        if blocked_analysis.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError(f"blocked analysis is not safe for shadow override filtering: {'; '.join(errors)}")


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
    parser.add_argument("--ready-subset", type=Path, default=DEFAULT_READY_SUBSET)
    parser.add_argument("--blocked-analysis", type=Path, default=DEFAULT_BLOCKED_ANALYSIS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    effects_plan = read_json(args.effects_plan)
    ready_subset = read_json(args.ready_subset)
    blocked_analysis = read_json(args.blocked_analysis)
    subset = build_entity_resolution_shadow_override_effects_plan(
        effects_plan=effects_plan,
        ready_subset=ready_subset,
        blocked_analysis=blocked_analysis,
        effects_plan_path=args.effects_plan,
        ready_subset_path=args.ready_subset,
        blocked_analysis_path=args.blocked_analysis,
    )
    write_json(args.output, subset)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "subset_policy": subset["subset_policy"],
                "baseline_selected_merge_effect_count": subset["baseline_selected_merge_effect_count"],
                "override_selected_merge_effect_count": subset["override_selected_merge_effect_count"],
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
