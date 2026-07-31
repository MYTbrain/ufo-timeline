import pytest

from scripts.promote_entity_resolution_suggestions import promote_entity_resolution_suggestions


def _safe_report():
    return {
        "suggestion_policy": "entity_resolution_ai_assisted_conservative_suggestions",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
    }


def test_promote_entity_resolution_suggestions_creates_separate_decisions():
    suggestions = [
        {
            "review_item_id": "er_review_1",
            "suggested_decision": "same_event",
            "confidence": "high",
            "rationale": "Exact date, time, place, and native ID.",
        },
        {
            "review_item_id": "er_review_2",
            "suggested_decision": "needs_more_evidence",
            "confidence": "low",
            "rationale": "Risk flags remain.",
        },
    ]

    decisions, report = promote_entity_resolution_suggestions(
        suggestions,
        suggestions_report=_safe_report(),
        reviewed_at="2026-05-22T00:00:00Z",
    )

    assert [decision["decision"] for decision in decisions] == ["same_event", "needs_more_evidence"]
    assert decisions[0]["notes"] == (
        "Promoted AI-assisted ER suggestion (high confidence): Exact date, time, place, and native ID."
    )
    assert report["decisions_created"] is True
    assert report["validated_decisions_created"] is False
    assert report["canonical_outputs_mutated"] is False
    assert report["decision_counts"] == {"needs_more_evidence": 1, "same_event": 1}
    assert report["skipped_suggestion_count"] == 0


def test_promote_entity_resolution_suggestions_skips_invalid_rows():
    suggestions = [
        {"suggested_decision": "same_event"},
        {"review_item_id": "er_review_bad", "suggested_decision": "merge_now"},
    ]

    decisions, report = promote_entity_resolution_suggestions(suggestions, suggestions_report=_safe_report())

    assert decisions == []
    assert report["skipped_suggestion_count"] == 2
    assert report["skipped_suggestions"][0]["error"] == "missing_review_item_id"
    assert report["skipped_suggestions"][1]["error"] == "invalid_suggested_decision"


def test_promote_entity_resolution_suggestions_rejects_unsafe_report():
    unsafe_report = _safe_report()
    unsafe_report["decisions_created"] = True

    with pytest.raises(ValueError, match="suggestions report is not safe to promote"):
        promote_entity_resolution_suggestions([], suggestions_report=unsafe_report)
