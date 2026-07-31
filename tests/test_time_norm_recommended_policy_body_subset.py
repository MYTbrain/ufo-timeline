import pytest

from scripts.build_time_norm_recommended_policy_body_subset import (
    build_time_norm_recommended_policy_body_subset,
)


def _effects_plan():
    return {
        "effect_policy": "entity_resolution_plan_only",
        "canonical_outputs_mutated": False,
        "canonical_outputs_mutated_by_plan": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "effects": [
            {"effect_id": "merge_1", "planned_effect": "merge_entity_resolution_candidate"},
            {"effect_id": "defer_1", "planned_effect": "defer_entity_resolution_candidate"},
        ],
    }


def test_time_norm_recommended_policy_body_subset_selects_merge_effects_only():
    subset = build_time_norm_recommended_policy_body_subset(effects_plan=_effects_plan())

    assert subset["subset_policy"] == "entity_resolution_shadow_preview_subset_with_analysis_overrides"
    assert subset["effect_policy"] == "entity_resolution_plan_only"
    assert subset["canonical_outputs_mutated"] is False
    assert subset["selected_merge_effect_count"] == 1
    assert subset["excluded_merge_effect_count"] == 1
    assert [effect["effect_id"] for effect in subset["effects"]] == ["merge_1"]


def test_time_norm_recommended_policy_body_subset_rejects_unsafe_effects_plan():
    plan = _effects_plan()
    plan["canonical_outputs_mutated"] = True

    with pytest.raises(ValueError, match="canonical_outputs_mutated"):
        build_time_norm_recommended_policy_body_subset(effects_plan=plan)
