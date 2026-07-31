import pytest

from scripts.summarize_entity_resolution_effect_impact import summarize_entity_resolution_effect_impact


def _safe_plan(effects):
    return {
        "effect_policy": "entity_resolution_plan_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "effects": effects,
    }


def test_entity_resolution_effect_impact_summarizes_projected_reduction():
    report = summarize_entity_resolution_effect_impact(
        effects_plan=_safe_plan(
            [
                {
                    "effect_id": "ere_a",
                    "review_item_id": "er_review_a",
                    "planned_effect": "merge_entity_resolution_candidate",
                    "merge_canonical_event_ids": ["evt_a", "evt_b"],
                    "requires_explicit_apply_step": True,
                },
                {
                    "effect_id": "ere_b",
                    "review_item_id": "er_review_b",
                    "planned_effect": "defer_entity_resolution_candidate",
                    "merge_canonical_event_ids": ["evt_c", "evt_d"],
                },
            ]
        )
    )

    assert report["canonical_outputs_mutated"] is False
    assert report["preview_outputs_written"] is False
    assert report["effect_counts"]["merge_entity_resolution_candidate"] == 1
    assert report["effect_counts"]["defer_entity_resolution_candidate"] == 1
    assert report["merge_impact"]["touched_event_count"] == 2
    assert report["merge_impact"]["projected_event_reduction"] == 1
    assert report["merge_impact"]["requires_explicit_apply_step_count"] == 1
    assert report["merge_samples"]["projected_merges"][0]["merge_canonical_event_ids"] == ["evt_a", "evt_b"]


def test_entity_resolution_effect_impact_reports_insufficient_merge_ids():
    report = summarize_entity_resolution_effect_impact(
        effects_plan=_safe_plan(
            [
                {
                    "effect_id": "ere_a",
                    "review_item_id": "er_review_a",
                    "planned_effect": "merge_entity_resolution_candidate",
                    "merge_canonical_event_ids": ["evt_a"],
                }
            ]
        )
    )

    assert report["merge_impact"]["merge_effects_with_insufficient_event_ids"] == 1
    assert report["merge_samples"]["insufficient_event_ids"][0]["projected_event_reduction"] == 0


def test_entity_resolution_effect_impact_rejects_unsafe_plan():
    unsafe_plan = _safe_plan([])
    unsafe_plan["canonical_outputs_mutated"] = True

    with pytest.raises(ValueError, match="effects plan is not safe to summarize"):
        summarize_entity_resolution_effect_impact(effects_plan=unsafe_plan)
