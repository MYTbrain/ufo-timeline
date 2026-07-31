import pytest

from scripts.check_time_norm_recommended_apply_readiness import (
    check_time_norm_recommended_apply_readiness,
)


def _decision_report():
    return {
        "promotion_policy": "entity_resolution_time_norm_recommended_decision_candidates_only",
        "canonical_outputs_mutated": False,
        "accepted_canonical_decisions_created": False,
        "ready_for_canonical_apply": False,
        "decision_candidate_count": 33,
        "skipped_recommendation_count": 11,
    }


def _effects_plan():
    return {
        "effect_policy": "entity_resolution_plan_only",
        "canonical_outputs_mutated": False,
        "canonical_outputs_mutated_by_plan": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "planned_effect_count": 33,
    }


def _preview_report():
    return {
        "apply_policy": "entity_resolution_stream_preview_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": True,
        "effects_applied": 33,
        "effects_blocked": 0,
        "projected_event_reduction": 40,
    }


def _output_check():
    return {
        "check_policy": "entity_resolution_shadow_preview_output_check",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "valid": True,
        "row_count": 944538,
        "preview_merge_count": 33,
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
        "policy_body_preview_count": 33,
        "invalid_conflict_metadata_count": 0,
    }


def _canonical_body_dry_run_check():
    return {
        "check_policy": "entity_resolution_time_norm_recommended_canonical_body_dry_run_check",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "valid": True,
        "validation_error_count": 0,
        "dry_run_row_count": 33,
        "incomplete_conflict_source_value_count": 0,
    }


def _accepted_decision_report():
    return {
        "acceptance_policy": "entity_resolution_time_norm_recommended_policy_acceptance_v1",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": True,
        "accepted_canonical_decisions_created": True,
        "validated_decisions_created": True,
        "canonical_apply_performed": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "decision_candidate_count": 33,
        "accepted_decision_count": 33,
        "skipped_decision_candidate_count": 0,
        "policy_conflict_blocking_preview_count": 0,
        "canonical_apply_contract_valid": True,
        "canonical_body_dry_run_valid": True,
    }


def _canonical_apply_output_check():
    return {
        "check_policy": "entity_resolution_time_norm_recommended_canonical_apply_output_check",
        "canonical_outputs_mutated": False,
        "source_canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "ready_for_runtime_promotion": False,
        "valid": True,
        "validation_error_count": 0,
        "row_count": 944538,
        "replacement_rows_found": 33,
        "suppressed_ids_found": 0,
        "duplicate_event_id_count": 0,
        "malformed_row_count": 0,
        "mismatched_replacement_row_count": 0,
    }


def test_time_norm_recommended_apply_readiness_records_valid_preview_but_blocks_apply():
    report = check_time_norm_recommended_apply_readiness(
        decision_report=_decision_report(),
        effects_plan=_effects_plan(),
        preview_report=_preview_report(),
        output_check=_output_check(),
        policy_body_check=_policy_body_check(),
        canonical_body_dry_run_check=_canonical_body_dry_run_check(),
        accepted_decision_report=_accepted_decision_report(),
    )

    assert report["apply_readiness_policy"] == "entity_resolution_time_norm_recommended_apply_readiness_gate"
    assert report["canonical_outputs_mutated"] is False
    assert report["ready_for_canonical_apply"] is False
    assert report["decision_candidate_count"] == 33
    assert report["preview_effects_applied"] == 33
    assert report["preview_projected_event_reduction"] == 40
    assert report["preview_output_valid"] is True
    assert report["policy_body_preview_available"] is True
    assert report["policy_body_preview_valid"] is True
    assert report["policy_body_preview_count"] == 33
    assert report["canonical_body_dry_run_available"] is True
    assert report["canonical_body_dry_run_valid"] is True
    assert report["canonical_body_dry_run_row_count"] == 33
    assert report["canonical_body_dry_run_incomplete_conflict_source_value_count"] == 0
    assert report["accepted_decision_report_available"] is True
    assert report["accepted_canonical_decisions_created"] is True
    assert report["accepted_decision_count"] == 33
    blockers = {item["blocker"] for item in report["canonical_apply_blockers"]}
    assert "recommended_decision_candidates_not_accepted_canonical_decisions" not in blockers
    assert "canonical_apply_command_not_implemented" in blockers
    assert "canonical_body_dry_run_not_apply_implementation" in blockers
    assert "policy_body_preview_not_full_apply_policy" not in blockers
    assert "final_merge_body_policy_missing_for_recommended_lane" not in blockers
    assert report["canonical_apply_blocker_count"] == 2


def test_time_norm_recommended_apply_readiness_accepts_valid_stream_apply_output():
    report = check_time_norm_recommended_apply_readiness(
        decision_report=_decision_report(),
        effects_plan=_effects_plan(),
        preview_report=_preview_report(),
        output_check=_output_check(),
        policy_body_check=_policy_body_check(),
        canonical_body_dry_run_check=_canonical_body_dry_run_check(),
        accepted_decision_report=_accepted_decision_report(),
        canonical_apply_output_check=_canonical_apply_output_check(),
    )

    assert report["ready_for_canonical_apply"] is True
    assert report["canonical_apply_blocker_count"] == 0
    assert report["canonical_apply_output_check_available"] is True
    assert report["canonical_apply_output_valid"] is True
    assert report["canonical_apply_output_row_count"] == 944538
    assert report["canonical_apply_output_replacement_rows_found"] == 33
    assert report["canonical_apply_output_suppressed_ids_found"] == 0


def test_time_norm_recommended_apply_readiness_blocks_without_accepted_report():
    report = check_time_norm_recommended_apply_readiness(
        decision_report=_decision_report(),
        effects_plan=_effects_plan(),
        preview_report=_preview_report(),
        output_check=_output_check(),
        policy_body_check=_policy_body_check(),
        canonical_body_dry_run_check=_canonical_body_dry_run_check(),
    )

    blockers = {item["blocker"] for item in report["canonical_apply_blockers"]}
    assert "recommended_decision_candidates_not_accepted_canonical_decisions" in blockers
    assert report["accepted_decision_report_available"] is False
    assert report["accepted_canonical_decisions_created"] is False
    assert report["canonical_apply_blocker_count"] == 3


def test_time_norm_recommended_apply_readiness_rejects_unsafe_preview_report():
    preview_report = _preview_report()
    preview_report["effects_blocked"] = 1

    with pytest.raises(ValueError, match="effects_blocked"):
        check_time_norm_recommended_apply_readiness(
            decision_report=_decision_report(),
            effects_plan=_effects_plan(),
            preview_report=preview_report,
            output_check=_output_check(),
            policy_body_check=_policy_body_check(),
        )
