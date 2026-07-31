import pytest

from scripts.check_entity_resolution_cluster_canonical_apply_readiness import (
    check_entity_resolution_cluster_canonical_apply_readiness,
)


def _override_subset(excluded=520):
    return {
        "effect_policy": "entity_resolution_plan_only",
        "subset_policy": "entity_resolution_shadow_preview_subset_with_analysis_overrides",
        "canonical_outputs_mutated": False,
        "canonical_outputs_mutated_by_plan": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "override_decisions_created": False,
        "selected_merge_effect_count": 34,
        "excluded_merge_effect_count": excluded,
    }


def _merge_readiness(blocking=538):
    return {
        "readiness_policy": "entity_resolution_merge_preview_readiness_gate",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "merge_preview_count": 554,
        "blocking_conflict_item_count": blocking,
        "review_conflict_item_count": 9,
    }


def _policy_body_check():
    return {
        "check_policy": "entity_resolution_policy_body_preview_check",
        "policy": "entity_resolution_cluster_canonical_merge_policy_proposal_v1",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "valid": True,
        "policy_body_preview_count": 34,
        "invalid_conflict_metadata_count": 0,
    }


def _shadow_preview_report():
    return {
        "apply_policy": "entity_resolution_stream_preview_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": True,
        "effects_requested": 34,
        "effects_applied": 34,
        "effects_blocked": 0,
        "projected_event_reduction": 61,
    }


def _shadow_output_check():
    return {
        "check_policy": "entity_resolution_shadow_preview_output_check",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "valid": True,
        "row_count": 944517,
        "preview_merge_count": 34,
    }


def test_cluster_canonical_apply_readiness_blocks_until_full_shadow_preview_exists():
    report = check_entity_resolution_cluster_canonical_apply_readiness(
        override_subset=_override_subset(),
        merge_readiness=_merge_readiness(),
        policy_body_check=_policy_body_check(),
    )

    assert report["canonical_outputs_mutated"] is False
    assert report["ready_for_canonical_apply"] is False
    assert report["selected_merge_effect_count"] == 34
    assert report["excluded_merge_effect_count"] == 520
    assert report["policy_body_preview_valid"] is True
    blockers = {item["blocker"] for item in report["canonical_apply_blockers"]}
    assert "cluster_full_shadow_preview_missing" in blockers
    assert "canonical_apply_command_not_implemented" in blockers
    assert "cluster_review_first_merge_candidates_remaining" in blockers
    assert "cluster_merge_preview_blocking_conflicts_remaining" in blockers


def test_cluster_canonical_apply_readiness_records_valid_full_shadow_preview():
    report = check_entity_resolution_cluster_canonical_apply_readiness(
        override_subset=_override_subset(),
        merge_readiness=_merge_readiness(),
        policy_body_check=_policy_body_check(),
        shadow_preview_report=_shadow_preview_report(),
        shadow_output_check=_shadow_output_check(),
    )

    assert report["ready_for_canonical_apply"] is False
    assert report["shadow_preview_available"] is True
    assert report["shadow_preview_valid"] is True
    assert report["shadow_preview_effects_applied"] == 34
    assert report["shadow_preview_event_count"] == 944517
    blockers = {item["blocker"] for item in report["canonical_apply_blockers"]}
    assert "cluster_full_shadow_preview_missing" not in blockers
    assert "canonical_apply_command_not_implemented" in blockers
    assert "cluster_review_first_merge_candidates_remaining" in blockers


def test_cluster_canonical_apply_readiness_rejects_wrong_policy_body_check():
    policy_body_check = _policy_body_check()
    policy_body_check["policy"] = "entity_resolution_canonical_merge_policy_proposal_v1"

    with pytest.raises(ValueError, match="cluster policy body check is not safe"):
        check_entity_resolution_cluster_canonical_apply_readiness(
            override_subset=_override_subset(excluded=0),
            merge_readiness=_merge_readiness(blocking=0),
            policy_body_check=policy_body_check,
        )
