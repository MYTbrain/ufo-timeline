import pytest

from scripts.promote_entity_resolution_cluster_suggestions import (
    promote_entity_resolution_cluster_suggestions,
)


def test_promote_entity_resolution_cluster_suggestions_writes_decision_records():
    suggestions = [
        {
            "cluster_review_id": "er_cluster_a",
            "suggested_decision": "same_event",
            "confidence": "medium",
            "rationale": "strict cluster",
        },
        {
            "cluster_review_id": "er_cluster_b",
            "suggested_decision": "needs_more_evidence",
            "confidence": "low",
            "rationale": "not strict",
        },
    ]
    report_input = {
        "suggestion_policy": "entity_resolution_cluster_ai_assisted_conservative_suggestions",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
    }

    decisions, report = promote_entity_resolution_cluster_suggestions(
        suggestions,
        suggestions_report=report_input,
        reviewed_at="2026-05-22T00:00:00+00:00",
    )

    assert report["promotion_policy"] == "entity_resolution_cluster_suggestion_promotion_to_ai_accepted_decisions"
    assert report["canonical_outputs_mutated"] is False
    assert report["decisions_created"] is True
    assert report["promoted_decision_count"] == 2
    assert report["decision_counts"] == {"needs_more_evidence": 1, "same_event": 1}
    assert decisions[0]["cluster_review_id"] == "er_cluster_a"
    assert decisions[0]["decision"] == "same_event"


def test_promote_entity_resolution_cluster_suggestions_skips_invalid_rows():
    decisions, report = promote_entity_resolution_cluster_suggestions(
        [
            {"cluster_review_id": "", "suggested_decision": "same_event"},
            {"cluster_review_id": "er_cluster_a", "suggested_decision": "merge_it"},
        ],
        reviewed_at="2026-05-22T00:00:00+00:00",
    )

    assert decisions == []
    assert report["skipped_suggestion_count"] == 2
    assert [item["error"] for item in report["skipped_suggestions"]] == [
        "missing_cluster_review_id",
        "invalid_suggested_decision",
    ]


def test_promote_entity_resolution_cluster_suggestions_rejects_unsafe_report():
    with pytest.raises(ValueError, match="decisions_created"):
        promote_entity_resolution_cluster_suggestions(
            [{"cluster_review_id": "er_cluster_a", "suggested_decision": "same_event"}],
            suggestions_report={
                "suggestion_policy": "entity_resolution_cluster_ai_assisted_conservative_suggestions",
                "canonical_outputs_mutated": False,
                "preview_outputs_written": False,
                "decisions_created": True,
                "auto_merge_performed": False,
            },
        )
