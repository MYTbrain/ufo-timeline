import pytest

from scripts.accept_time_norm_recommended_decisions import (
    accept_time_norm_recommended_decisions,
)


def _candidate(review_item_id="er_cluster_a", decision_id="erdtn_a"):
    return {
        "entity_resolution_decision_id": decision_id,
        "decision_index": 1,
        "review_item_id": review_item_id,
        "cluster_review_id": review_item_id,
        "review_type": "entity_resolution_cluster_time_normalization_candidate",
        "decision": "same_event",
        "effect_status": "recommended_candidate_not_applied",
        "decision_source": "entity_resolution_time_norm_auto_recommendation_only",
        "promotion_policy": "entity_resolution_time_norm_recommended_decision_candidates_only",
        "canonical_outputs_mutated": False,
        "review_band": "strict_time_normalization_clean_clock",
        "confidence": "medium",
        "canonical_input_ids": ["cin_a", "cin_b"],
        "merge_canonical_event_ids": ["evt_a", "evt_b"],
        "reviewer": "codex_time_norm_clean_clock_recommendation_v1",
        "reviewed_at": "2026-05-22T00:00:00Z",
        "notes": "candidate",
        "requires_explicit_apply_step": True,
    }


def _candidate_report(count=1):
    return {
        "promotion_policy": "entity_resolution_time_norm_recommended_decision_candidates_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "canonical_apply_performed": False,
        "auto_merge_performed": False,
        "accepted_canonical_decisions_created": False,
        "ready_for_canonical_apply": False,
        "decision_candidate_count": count,
        "skipped_recommendation_count": 11,
        "projected_event_reduction": count,
    }


def _policy_conflicts(*review_item_ids):
    items = [
        {
            "review_item_id": review_item_id,
            "policy_action": "candidate_for_final_policy_after_decision_acceptance",
            "risk_tier": "low",
            "blockers": [],
        }
        for review_item_id in review_item_ids
    ]
    return {
        "classification_policy": "entity_resolution_time_norm_recommended_policy_conflict_classification_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "summary": {
            "apply_policy_candidate_count": len(items),
            "blocking_preview_count": 0,
        },
        "items": items,
    }


def _contract(count=1):
    return {
        "contract_policy": "entity_resolution_time_norm_recommended_canonical_apply_contract_check",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "contract_valid": True,
        "validation_error_count": 0,
        "effect_count": count,
        "merge_patch_count": count,
        "missing_touched_event_ids": [],
        "suppressed_event_ids_present_in_preview": [],
        "replacement_event_ids_missing_from_preview": [],
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


def test_accept_time_norm_recommended_decisions_creates_non_mutating_accepted_artifact():
    decisions, report = accept_time_norm_recommended_decisions(
        decision_candidates=[_candidate()],
        decision_candidate_report=_candidate_report(),
        policy_conflict_classification=_policy_conflicts("er_cluster_a"),
        canonical_apply_contract_check=_contract(),
        canonical_body_dry_run_check=_dry_run_check(),
        accepted_at="2026-05-22T00:00:00Z",
    )

    assert report["acceptance_policy"] == "entity_resolution_time_norm_recommended_policy_acceptance_v1"
    assert report["canonical_outputs_mutated"] is False
    assert report["decisions_created"] is True
    assert report["accepted_canonical_decisions_created"] is True
    assert report["ready_for_canonical_apply"] is False
    assert report["accepted_decision_count"] == 1
    assert decisions[0]["effect_status"] == "accepted_not_applied"
    assert decisions[0]["accepted_canonical_decision"] is True
    assert decisions[0]["requires_explicit_apply_step"] is True


def test_accept_time_norm_recommended_decisions_rejects_policy_conflict_blockers():
    conflicts = _policy_conflicts("er_cluster_a")
    conflicts["summary"]["blocking_preview_count"] = 1

    with pytest.raises(ValueError, match="blocking_preview_count"):
        accept_time_norm_recommended_decisions(
            decision_candidates=[_candidate()],
            decision_candidate_report=_candidate_report(),
            policy_conflict_classification=conflicts,
            canonical_apply_contract_check=_contract(),
            canonical_body_dry_run_check=_dry_run_check(),
        )


def test_accept_time_norm_recommended_decisions_rejects_invalid_contract():
    contract = _contract()
    contract["contract_valid"] = False

    with pytest.raises(ValueError, match="contract_valid"):
        accept_time_norm_recommended_decisions(
            decision_candidates=[_candidate()],
            decision_candidate_report=_candidate_report(),
            policy_conflict_classification=_policy_conflicts("er_cluster_a"),
            canonical_apply_contract_check=contract,
            canonical_body_dry_run_check=_dry_run_check(),
        )
