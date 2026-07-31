import pytest

from scripts.check_entity_resolution_canonical_apply_readiness import (
    check_entity_resolution_canonical_apply_readiness,
)


def _delta_summary(remaining=1):
    return {
        "summary_policy": "entity_resolution_shadow_override_delta_summary",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "remaining_excluded_merge_effect_count": remaining,
        "remaining_excluded_review_item_ids": ["review_coordinate"] if remaining else [],
    }


def _override_subset():
    return {
        "effect_policy": "entity_resolution_plan_only",
        "subset_policy": "entity_resolution_shadow_preview_subset_with_analysis_overrides",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "override_decisions_created": False,
    }


def _preview_report():
    return {
        "apply_policy": "entity_resolution_stream_preview_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": True,
        "effects_requested": 36,
        "effects_applied": 36,
        "effects_blocked": 0,
        "projected_event_reduction": 36,
    }


def _output_check():
    return {
        "check_policy": "entity_resolution_shadow_preview_output_check",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "valid": True,
    }


def test_canonical_apply_readiness_blocks_until_final_policy_and_review_are_done():
    report = check_entity_resolution_canonical_apply_readiness(
        delta_summary=_delta_summary(),
        override_subset=_override_subset(),
        override_preview_report=_preview_report(),
        override_output_check=_output_check(),
    )

    assert report["canonical_outputs_mutated"] is False
    assert report["ready_for_canonical_apply"] is False
    assert report["shadow_preview_effects_applied"] == 36
    assert report["remaining_excluded_merge_effect_count"] == 1
    blockers = {item["blocker"] for item in report["canonical_apply_blockers"]}
    assert "final_merge_body_policy_missing" in blockers
    assert "canonical_apply_command_not_implemented" in blockers
    assert "review_first_merge_candidates_remaining" in blockers


def test_canonical_apply_readiness_rejects_invalid_preview_output_check():
    invalid_check = _output_check()
    invalid_check["valid"] = False

    with pytest.raises(ValueError, match="override output check is not safe"):
        check_entity_resolution_canonical_apply_readiness(
            delta_summary=_delta_summary(remaining=0),
            override_subset=_override_subset(),
            override_preview_report=_preview_report(),
            override_output_check=invalid_check,
        )
