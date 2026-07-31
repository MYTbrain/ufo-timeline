import pytest

from scripts.accept_likely_time_format_decisions import (
    ACCEPTANCE_POLICY,
    accept_likely_time_format_decisions,
)


def _candidate(decision_id="erltf_1", review_item_id="review_1"):
    return {
        "entity_resolution_decision_id": decision_id,
        "review_item_id": review_item_id,
        "review_type": "entity_resolution_cluster_likely_time_format_candidate",
        "decision": "same_event",
        "promotion_policy": "entity_resolution_likely_time_format_decision_candidates_only",
        "canonical_outputs_mutated": False,
        "review_band": "strict_likely_time_format_source_review",
        "canonical_input_ids": ["cin_a", "cin_b"],
        "merge_canonical_event_ids": ["evt_a", "evt_b"],
        "requires_explicit_apply_step": True,
        "notes": "reviewed",
    }


def _candidate_report(count=1):
    return {
        "promotion_policy": "entity_resolution_likely_time_format_decision_candidates_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "canonical_apply_performed": False,
        "auto_merge_performed": False,
        "accepted_canonical_decisions_created": False,
        "ready_for_canonical_apply": False,
        "decision_candidate_count": count,
        "skipped_review_item_count": 0,
        "projected_event_reduction": count,
    }


def _preview_report(count=1):
    return {
        "apply_policy": "entity_resolution_stream_preview_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": True,
        "effects_requested": count,
        "effects_applied": count,
        "effects_blocked": 0,
    }


def _preview_output_check(count=1):
    return {
        "check_policy": "entity_resolution_shadow_preview_output_check",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "valid": True,
        "validation_errors": [],
        "effects_applied": count,
        "expected_preview_merge_count": count,
    }


def _dry_run_check(count=1):
    return {
        "check_policy": "entity_resolution_time_norm_recommended_canonical_body_dry_run_check",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "valid": True,
        "dry_run_row_count": count,
        "validation_error_count": 0,
        "incomplete_conflict_source_value_count": 0,
    }


def test_accept_likely_time_format_decisions_requires_preview_and_dry_run_gates():
    accepted, report = accept_likely_time_format_decisions(
        decision_candidates=[_candidate()],
        decision_candidate_report=_candidate_report(),
        preview_report=_preview_report(),
        preview_output_check=_preview_output_check(),
        canonical_body_dry_run_check=_dry_run_check(),
        accepted_at="2026-05-22T00:00:00Z",
    )

    assert report["acceptance_policy"] == ACCEPTANCE_POLICY
    assert report["accepted_decision_count"] == 1
    assert report["canonical_outputs_mutated"] is False
    assert report["canonical_apply_performed"] is False
    assert report["ready_for_canonical_apply"] is False
    assert accepted[0]["effect_status"] == "accepted_not_applied"
    assert accepted[0]["accepted_canonical_decision"] is True
    assert accepted[0]["acceptance_policy"] == ACCEPTANCE_POLICY


def test_accept_likely_time_format_decisions_rejects_invalid_preview_output():
    preview_output = _preview_output_check()
    preview_output["valid"] = False

    with pytest.raises(ValueError, match="preview output check must be valid"):
        accept_likely_time_format_decisions(
            decision_candidates=[_candidate()],
            decision_candidate_report=_candidate_report(),
            preview_report=_preview_report(),
            preview_output_check=preview_output,
            canonical_body_dry_run_check=_dry_run_check(),
        )


def test_accept_likely_time_format_decisions_rejects_duplicate_review_items():
    with pytest.raises(ValueError, match="duplicate_review_item"):
        accept_likely_time_format_decisions(
            decision_candidates=[_candidate("erltf_1", "review_1"), _candidate("erltf_2", "review_1")],
            decision_candidate_report=_candidate_report(count=2),
            preview_report=_preview_report(count=2),
            preview_output_check=_preview_output_check(count=2),
            canonical_body_dry_run_check=_dry_run_check(count=2),
        )
