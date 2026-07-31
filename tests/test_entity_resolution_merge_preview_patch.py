import pytest

from scripts.build_entity_resolution_merge_preview_patch import build_entity_resolution_merge_preview_patch


def _safe_plan(effects):
    return {
        "effect_policy": "entity_resolution_plan_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "effects": effects,
    }


def test_build_entity_resolution_merge_preview_patch_creates_compact_patch():
    patch = build_entity_resolution_merge_preview_patch(
        effects_plan=_safe_plan(
            [
                {
                    "effect_id": "ere_a",
                    "review_item_id": "er_review_a",
                    "planned_effect": "merge_entity_resolution_candidate",
                    "merge_canonical_event_ids": ["evt_b", "evt_a"],
                    "canonical_input_ids": ["cin_b", "cin_a"],
                    "requires_explicit_apply_step": True,
                },
                {
                    "effect_id": "ere_b",
                    "planned_effect": "defer_entity_resolution_candidate",
                    "merge_canonical_event_ids": ["evt_c", "evt_d"],
                },
            ]
        )
    )

    assert patch["canonical_outputs_mutated"] is False
    assert patch["preview_outputs_written"] is False
    assert patch["merge_patch_count"] == 1
    assert patch["projected_event_reduction"] == 1
    assert patch["patches"][0]["replacement_canonical_event_id"] == "evt_a"
    assert patch["patches"][0]["suppressed_canonical_event_ids"] == ["evt_b"]
    assert patch["patches"][0]["requires_explicit_apply_step"] is True


def test_build_entity_resolution_merge_preview_patch_skips_insufficient_merge_ids():
    patch = build_entity_resolution_merge_preview_patch(
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

    assert patch["merge_patch_count"] == 0
    assert patch["skipped_merge_effect_count"] == 1
    assert patch["skipped_merge_effects"][0]["reason"] == "insufficient_merge_event_ids"


def test_build_entity_resolution_merge_preview_patch_rejects_unsafe_plan():
    unsafe_plan = _safe_plan([])
    unsafe_plan["auto_merge_performed"] = True

    with pytest.raises(ValueError, match="effects plan is not safe for preview patching"):
        build_entity_resolution_merge_preview_patch(effects_plan=unsafe_plan)
