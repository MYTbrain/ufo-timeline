import pytest

from scripts.promote_time_norm_deferred_shorthand_review_to_decision_candidates import (
    PROMOTION_POLICY,
    build_deferred_shorthand_decision_candidates,
)


def _review_item(review_item_id="er_cluster_a", *, recommendation="source_review_same_event_candidate", failed=None):
    return {
        "review_rank": 1,
        "review_item_id": review_item_id,
        "cluster_review_id": review_item_id,
        "effect_id": f"ere_{review_item_id}",
        "review_recommendation": recommendation,
        "confidence": "medium",
        "projected_event_reduction": 1,
        "time_tokens": ["20+", "2000", "2015"],
        "parsed_token_minutes": [1200, 1215],
        "token_minute_span": 15,
        "active_conflicts": ["time"],
        "review_reason_codes": ["source_review_shorthand_time_only"],
        "source_names": ["ufocat"],
        "source_native_ids": ["native_1"],
        "dates": ["1965-11-26"],
        "locations": ["ST PAUL, Ramsey, MN, US"],
        "failed_conditions": failed or [],
        "merge_canonical_event_ids": ["evt_a", "evt_b"],
        "candidate_canonical_input_ids": ["cin_a", "cin_b"],
        "notes": "reviewed",
    }


def _report(*items):
    return {
        "review_policy": "entity_resolution_time_norm_deferred_shorthand_source_review_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "validated_decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "items": list(items),
    }


def test_promote_deferred_shorthand_review_writes_only_same_event_candidates():
    candidates, report = build_deferred_shorthand_decision_candidates(
        _report(
            _review_item("safe"),
            _review_item("defer", recommendation="remain_deferred", failed=["time_only_conflict"]),
        ),
        reviewed_at="2026-05-22T00:00:00Z",
    )

    assert report["promotion_policy"] == PROMOTION_POLICY
    assert report["canonical_outputs_mutated"] is False
    assert report["ready_for_canonical_apply"] is False
    assert report["decision_candidate_count"] == 1
    assert report["skipped_review_item_count"] == 1
    assert report["projected_event_reduction"] == 1
    candidate = candidates[0]
    assert candidate["decision"] == "same_event"
    assert candidate["effect_status"] == "source_reviewed_candidate_not_applied"
    assert candidate["promotion_policy"] == PROMOTION_POLICY
    assert candidate["review_band"] == "strict_time_normalization_deferred_shorthand_source_review"
    assert candidate["requires_explicit_apply_step"] is True


def test_promote_deferred_shorthand_review_skips_failed_same_event_item():
    candidates, report = build_deferred_shorthand_decision_candidates(
        _report(_review_item("failed", failed=["identical_nonempty_summary_text"])),
    )

    assert candidates == []
    assert report["skipped_reason_counts"] == {"source_review_has_failed_conditions": 1}


def test_promote_deferred_shorthand_review_rejects_unsafe_report():
    report = _report(_review_item())
    report["auto_merge_performed"] = True

    with pytest.raises(ValueError, match="auto_merge_performed"):
        build_deferred_shorthand_decision_candidates(report)
