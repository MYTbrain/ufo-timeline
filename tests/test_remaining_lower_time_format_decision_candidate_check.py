from scripts.check_remaining_lower_time_format_decision_candidates import (
    check_remaining_lower_time_format_decision_candidates,
)


def _review_item(review_item_id, recommendation="source_review_same_event_candidate", failed=None):
    return {
        "review_item_id": review_item_id,
        "review_recommendation": recommendation,
        "failed_conditions": failed or [],
        "merge_canonical_event_ids": [f"evt_{review_item_id}_a", f"evt_{review_item_id}_b"],
    }


def _candidate(review_item_id):
    return {
        "review_item_id": review_item_id,
        "promotion_policy": "entity_resolution_remaining_lower_time_format_decision_candidates_only",
        "canonical_outputs_mutated": False,
        "merge_canonical_event_ids": [f"evt_{review_item_id}_a", f"evt_{review_item_id}_b"],
    }


def _candidate_report(candidate_count=1, skipped_count=1, projected_reduction=1):
    return {
        "promotion_policy": "entity_resolution_remaining_lower_time_format_decision_candidates_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "canonical_apply_performed": False,
        "auto_merge_performed": False,
        "accepted_canonical_decisions_created": False,
        "ready_for_canonical_apply": False,
        "decision_candidate_count": candidate_count,
        "skipped_review_item_count": skipped_count,
        "projected_event_reduction": projected_reduction,
    }


def _review():
    return {
        "review_policy": "entity_resolution_remaining_lower_time_format_source_review_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "items": [
            _review_item("safe"),
            _review_item("defer", "remain_deferred", ["time_only_conflict"]),
        ],
    }


def test_remaining_lower_time_format_decision_candidate_check_accepts_safe_gate():
    report = check_remaining_lower_time_format_decision_candidates(
        review=_review(),
        candidates=[_candidate("safe")],
        candidate_report=_candidate_report(),
        accepted_decisions=[],
    )

    assert report["valid"] is True
    assert report["errors"] == []
    assert report["decision_candidate_count"] == 1
    assert report["deferred_review_item_count"] == 1
    assert report["ready_for_canonical_apply"] is False


def test_remaining_lower_time_format_decision_candidate_check_rejects_deferred_candidate():
    report = check_remaining_lower_time_format_decision_candidates(
        review=_review(),
        candidates=[_candidate("safe"), _candidate("defer")],
        candidate_report=_candidate_report(candidate_count=2, skipped_count=1, projected_reduction=2),
        accepted_decisions=[],
    )

    assert report["valid"] is False
    assert "candidate JSONL includes deferred review rows" in report["errors"]


def test_remaining_lower_time_format_decision_candidate_check_rejects_accepted_overlap():
    report = check_remaining_lower_time_format_decision_candidates(
        review=_review(),
        candidates=[_candidate("safe")],
        candidate_report=_candidate_report(),
        accepted_decisions=[_candidate("safe")],
    )

    assert report["valid"] is False
    assert "candidate JSONL overlaps already accepted combined decisions by review_item_id" in report["errors"]
    assert "candidate JSONL overlaps already accepted combined decisions by merge event set" in report["errors"]
