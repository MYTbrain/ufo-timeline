"""Build the recommended time-normalization subset for policy-body preview."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_EFFECTS_PLAN = Path("data/reports/entity_resolution_cluster_time_norm_recommended_effects_plan.json")
DEFAULT_OUTPUT = Path("data/reports/entity_resolution_cluster_time_norm_recommended_policy_body_subset.json")


def build_time_norm_recommended_policy_body_subset(
    *,
    effects_plan: dict[str, Any],
    effects_plan_path: Path | None = None,
) -> dict[str, Any]:
    validate_effects_plan(effects_plan)
    effects = [effect for effect in effects_plan.get("effects") or [] if isinstance(effect, dict)]
    merge_effects = [
        effect for effect in effects if effect.get("planned_effect") == "merge_entity_resolution_candidate"
    ]
    return {
        "schema_version": 1,
        "effect_policy": "entity_resolution_plan_only",
        "subset_policy": "entity_resolution_shadow_preview_subset_with_analysis_overrides",
        "subset_source": "time_norm_recommended_policy_body_preview_adapter",
        "canonical_outputs_mutated": False,
        "canonical_outputs_mutated_by_plan": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "override_decisions_created": False,
        "inputs": {
            "effects_plan": str(effects_plan_path) if effects_plan_path else None,
        },
        "source_effect_count": len(effects),
        "selected_merge_effect_count": len(merge_effects),
        "excluded_merge_effect_count": len(effects) - len(merge_effects),
        "effects": merge_effects,
        "notes": [
            "Adapter subset for recommended time-normalization policy-body preview only.",
            "Canonical outputs are not mutated.",
        ],
    }


def validate_effects_plan(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("effect_policy") != "entity_resolution_plan_only":
        errors.append("effect_policy must be entity_resolution_plan_only")
    for flag in ("canonical_outputs_mutated", "canonical_outputs_mutated_by_plan", "preview_outputs_written", "auto_merge_performed"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError("effects plan is not safe for policy subset building: " + "; ".join(errors))


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
    subset = build_time_norm_recommended_policy_body_subset(
        effects_plan=read_json(args.effects_plan),
        effects_plan_path=args.effects_plan,
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
