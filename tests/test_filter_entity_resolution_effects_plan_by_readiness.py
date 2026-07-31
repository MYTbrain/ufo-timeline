import pytest

from scripts.filter_entity_resolution_effects_plan_by_readiness import (
    filter_entity_resolution_effects_plan_by_readiness,
)


def _safe_plan(effects):
    return {
        "effect_policy": "entity_resolution_plan_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "effects": effects,
    }


def _safe_readiness(blocked_ids):
    return {
        "readiness_policy": "entity_resolution_merge_preview_readiness_gate",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "blocking_items_sample": [{"review_item_id": review_item_id} for review_item_id in blocked_ids],
    }


def _effect(review_item_id, planned_effect="merge_entity_resolution_candidate"):
    return {
        "effect_id": f"effect_{review_item_id}",
        "review_item_id": review_item_id,
        "planned_effect": planned_effect,
    }


def test_filter_entity_resolution_effects_plan_by_readiness_keeps_unblocked_merges_only():
    subset = filter_entity_resolution_effects_plan_by_readiness(
        effects_plan=_safe_plan(
            [
                _effect("review_a"),
                _effect("review_b"),
                _effect("review_defer", "defer_entity_resolution_candidate"),
            ]
        ),
        readiness_report=_safe_readiness(["review_b"]),
    )

    assert subset["canonical_outputs_mutated"] is False
    assert subset["selected_merge_effect_count"] == 1
    assert subset["excluded_merge_effect_count"] == 1
    assert subset["passthrough_non_merge_effect_count"] == 1
    assert subset["effects"][0]["review_item_id"] == "review_a"
    assert subset["excluded_effects"][0]["review_item_id"] == "review_b"


def test_filter_entity_resolution_effects_plan_by_readiness_uses_full_blocking_items_when_present():
    readiness = _safe_readiness(["review_sample_only"])
    readiness["blocking_items"] = [{"review_item_id": f"review_{index}"} for index in range(60)]

    subset = filter_entity_resolution_effects_plan_by_readiness(
        effects_plan=_safe_plan([_effect("review_55"), _effect("review_open")]),
        readiness_report=readiness,
    )

    assert subset["selected_merge_effect_count"] == 1
    assert subset["excluded_merge_effect_count"] == 1
    assert subset["effects"][0]["review_item_id"] == "review_open"
    assert subset["excluded_effects"][0]["review_item_id"] == "review_55"


def test_filter_entity_resolution_effects_plan_by_readiness_rejects_unsafe_inputs():
    unsafe_plan = _safe_plan([])
    unsafe_plan["auto_merge_performed"] = True

    with pytest.raises(ValueError, match="effects plan is not safe to filter"):
        filter_entity_resolution_effects_plan_by_readiness(
            effects_plan=unsafe_plan,
            readiness_report=_safe_readiness([]),
        )

    unsafe_readiness = _safe_readiness([])
    unsafe_readiness["preview_outputs_written"] = True

    with pytest.raises(ValueError, match="readiness report is not safe"):
        filter_entity_resolution_effects_plan_by_readiness(
            effects_plan=_safe_plan([]),
            readiness_report=unsafe_readiness,
        )
