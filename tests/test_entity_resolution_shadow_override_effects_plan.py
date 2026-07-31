import pytest

from scripts.build_entity_resolution_shadow_override_effects_plan import (
    build_entity_resolution_shadow_override_effects_plan,
)


def _effect(review_item_id, decision_index, planned_effect="merge_entity_resolution_candidate"):
    return {
        "effect_id": f"effect_{review_item_id}",
        "review_item_id": review_item_id,
        "decision_index": decision_index,
        "planned_effect": planned_effect,
        "merge_canonical_event_ids": [f"evt_{review_item_id}_a", f"evt_{review_item_id}_b"],
    }


def _safe_effects_plan(effects):
    return {
        "effect_policy": "entity_resolution_plan_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "effects": effects,
    }


def _safe_ready_subset(effects, excluded_effects):
    return {
        "effect_policy": "entity_resolution_plan_only",
        "subset_policy": "entity_resolution_ready_subset_for_shadow_preview",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "effects": effects,
        "excluded_effects": excluded_effects,
    }


def _safe_analysis(items):
    return {
        "analysis_policy": "entity_resolution_blocked_merge_analysis_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "override_decisions_created": False,
        "items": items,
    }


def test_shadow_override_effects_plan_adds_only_high_confidence_override_candidates():
    base = _effect("review_ready", 1)
    override = _effect("review_override", 2)
    coordinate_review = _effect("review_coordinate", 3)
    subset = build_entity_resolution_shadow_override_effects_plan(
        effects_plan=_safe_effects_plan([base, override, coordinate_review]),
        ready_subset=_safe_ready_subset(
            [base],
            [
                {"review_item_id": "review_override", "reason": "blocked_by_merge_readiness_gate"},
                {"review_item_id": "review_coordinate", "reason": "blocked_by_merge_readiness_gate"},
            ],
        ),
        blocked_analysis=_safe_analysis(
            [
                {
                    "review_item_id": "review_override",
                    "suggested_action": "candidate_shadow_preview_override",
                    "analysis_confidence": "high",
                    "classification": "likely_source_subtype_variant",
                    "blocking_fields": ["type_normalized"],
                },
                {
                    "review_item_id": "review_coordinate",
                    "suggested_action": "coordinate_review_before_override",
                    "analysis_confidence": "medium",
                    "classification": "nearby_location_coordinate_variant",
                    "blocking_fields": ["coordinate_distance_over_10km"],
                },
            ]
        ),
    )

    assert subset["canonical_outputs_mutated"] is False
    assert subset["override_decisions_created"] is False
    assert subset["baseline_selected_merge_effect_count"] == 1
    assert subset["override_selected_merge_effect_count"] == 1
    assert subset["selected_merge_effect_count"] == 2
    assert subset["excluded_merge_effect_count"] == 1
    assert subset["override_review_item_ids"] == ["review_override"]
    assert subset["effects"][1]["shadow_preview_override"] is True
    assert subset["excluded_effects"][0]["review_item_id"] == "review_coordinate"


def test_shadow_override_effects_plan_rejects_unsafe_analysis():
    unsafe_analysis = _safe_analysis([])
    unsafe_analysis["override_decisions_created"] = True

    with pytest.raises(ValueError, match="blocked analysis is not safe"):
        build_entity_resolution_shadow_override_effects_plan(
            effects_plan=_safe_effects_plan([]),
            ready_subset=_safe_ready_subset([], []),
            blocked_analysis=unsafe_analysis,
        )
