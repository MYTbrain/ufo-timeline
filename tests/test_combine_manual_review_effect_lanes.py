import pytest

from scripts.combine_manual_review_effect_lanes import combine_manual_review_effect_lanes


def test_combines_low_risk_base_and_medium_time_effect_lanes():
    output_plan, report = combine_manual_review_effect_lanes(
        original_effects_plan=_plan(
            [
                _effect("mre_low", "merge_duplicate_candidate"),
                _effect("mre_medium", "merge_duplicate_candidate"),
                _effect("mre_drop", "merge_duplicate_candidate"),
                _effect("mre_defer", "defer_duplicate_candidate"),
            ]
        ),
        base_effects_plan=_plan([_effect("mre_low", "merge_duplicate_candidate"), _effect("mre_defer", "defer_duplicate_candidate")]),
        decision_candidates=[_candidate(["mre_medium"])],
    )

    assert [effect["effect_id"] for effect in output_plan["effects"]] == ["mre_low", "mre_medium", "mre_defer"]
    assert output_plan["combine_policy"] == "manual_review_effect_lanes_combined_v1"
    assert output_plan["planned_effect_count"] == 3
    assert report["selected_merge_effect_count"] == 2
    assert report["base_medium_time_effect_overlap_count"] == 0


def test_combined_effect_lanes_rejects_unsafe_candidate():
    with pytest.raises(ValueError, match="promotion_policy"):
        combine_manual_review_effect_lanes(
            original_effects_plan=_plan([_effect("mre_a", "merge_duplicate_candidate")]),
            base_effects_plan=_plan([]),
            decision_candidates=[{"promotion_policy": "wrong", "canonical_outputs_mutated": False, "decision": "same_event", "effect_ids": ["mre_a"]}],
        )


def _plan(effects):
    return {
        "effect_policy": "plan_only",
        "canonical_outputs_mutated": False,
        "canonical_outputs_mutated_by_plan": False,
        "planned_effect_count": len(effects),
        "effects": effects,
    }


def _effect(effect_id, planned_effect):
    return {
        "effect_id": effect_id,
        "planned_effect": planned_effect,
        "effect_policy": "plan_only",
        "effect_status": "planned_not_applied",
        "canonical_outputs_mutated": False,
    }


def _candidate(effect_ids):
    return {
        "promotion_policy": "manual_review_medium_time_raw_only_decision_candidates_only",
        "canonical_outputs_mutated": False,
        "decision": "same_event",
        "effect_ids": effect_ids,
    }
