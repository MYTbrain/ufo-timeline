import pytest

from scripts.promote_time_norm_source_recommendations_to_decision_candidates import (
    build_time_norm_recommended_decision_candidates,
)


def _recommendation(review_item_id="er_cluster_a", *, recommendation="recommend_same_event", blockers=None):
    return {
        "review_item_id": review_item_id,
        "cluster_review_id": review_item_id,
        "effect_id": f"ere_{review_item_id}",
        "recommendation": recommendation,
        "confidence": "medium",
        "blockers": blockers or [],
        "candidate_canonical_input_ids": ["cin_a", "cin_b"],
        "merge_canonical_event_ids": ["evt_a", "evt_b"],
        "time_tokens": ["1000", "1005"],
        "parsed_minutes": [600, 605],
        "minute_span": 5,
        "active_conflicts": ["time"],
        "reason_codes": ["auto_recommend_preview_candidate_numeric_time_only"],
        "source_names": ["ufocat"],
        "source_native_ids": ["native_1"],
        "dates": ["1954-09-19"],
        "locations": ["RONGERES, FRA"],
        "notes": "candidate",
    }


def _report(*recommendations):
    return {
        "recommendation_policy": "entity_resolution_time_norm_auto_recommendation_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "validated_decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "recommendations": list(recommendations),
    }


def test_time_norm_recommended_decision_candidates_promotes_only_same_event_recommendations():
    decisions, report = build_time_norm_recommended_decision_candidates(
        _report(
            _recommendation("accept"),
            _recommendation("defer", recommendation="needs_more_evidence", blockers=["symbolic_or_shorthand_time_tokens"]),
        ),
        reviewed_at="2026-05-22T00:00:00Z",
    )

    assert report["promotion_policy"] == "entity_resolution_time_norm_recommended_decision_candidates_only"
    assert report["canonical_outputs_mutated"] is False
    assert report["ready_for_canonical_apply"] is False
    assert report["accepted_canonical_decisions_created"] is False
    assert report["recommended_decision_candidate_records_written"] is True
    assert report["decision_candidate_count"] == 1
    assert report["skipped_recommendation_count"] == 1
    assert report["skipped_reason_counts"] == {"recommendation_not_same_event": 1}
    assert report["projected_event_reduction"] == 1
    assert len(decisions) == 1
    decision = decisions[0]
    assert decision["entity_resolution_decision_id"].startswith("erdtn_")
    assert decision["review_item_id"] == "accept"
    assert decision["decision"] == "same_event"
    assert decision["effect_status"] == "recommended_candidate_not_applied"
    assert decision["merge_canonical_event_ids"] == ["evt_a", "evt_b"]
    assert decision["requires_explicit_apply_step"] is True
    assert decision["evidence"]["time_tokens"] == ["1000", "1005"]


def test_time_norm_recommended_decision_candidates_rejects_unsafe_input():
    report = _report(_recommendation())
    report["ready_for_canonical_apply"] = True

    with pytest.raises(ValueError, match="ready_for_canonical_apply"):
        build_time_norm_recommended_decision_candidates(report)
