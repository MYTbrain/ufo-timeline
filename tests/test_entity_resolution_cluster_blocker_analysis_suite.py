import pytest

from scripts.summarize_entity_resolution_cluster_blocker_analysis_suite import (
    summarize_entity_resolution_cluster_blocker_analysis_suite,
)


def _priority_queue():
    return {
        "queue_policy": "entity_resolution_cluster_blocker_priority_queue_review_only",
        "canonical_outputs_mutated": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "summary": {
            "queue_item_count": 10,
            "triage_bucket_counts": {
                "time_format_review": 5,
                "time_conflict_review": 2,
                "type_conflict_review": 2,
                "coordinate_conflict_review": 1,
            },
        },
    }


def _time_norm_subset():
    return {
        "subset_policy": "entity_resolution_cluster_time_normalization_shadow_preview_subset_v2",
        "canonical_outputs_mutated": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "time_norm_override_selected_merge_effect_count": 2,
    }


def _analysis(policy, count, high):
    return {
        "analysis_policy": policy,
        "canonical_outputs_mutated": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "summary": {
            "analyzed_item_count": count,
            "review_risk_tier_counts": {"high": high},
        },
    }


def test_cluster_blocker_analysis_suite_summarizes_preview_safe_and_blocked_work():
    summary = summarize_entity_resolution_cluster_blocker_analysis_suite(
        priority_queue=_priority_queue(),
        time_norm_subset=_time_norm_subset(),
        time_conflict_analysis=_analysis("entity_resolution_cluster_time_conflict_review_only", 2, 2),
        type_conflict_analysis=_analysis("entity_resolution_cluster_type_conflict_review_only", 2, 2),
        coordinate_conflict_analysis=_analysis("entity_resolution_cluster_coordinate_conflict_review_only", 1, 1),
    )

    assert summary["summary_policy"] == "entity_resolution_cluster_blocker_analysis_suite_report_only"
    assert summary["canonical_outputs_mutated"] is False
    assert summary["decisions_created"] is False
    assert summary["summary"]["queue_item_count"] == 10
    assert summary["summary"]["strict_time_normalization_new_preview_candidates"] == 2
    assert summary["summary"]["strict_time_normalization_remaining_time_format_items"] == 3
    assert summary["summary"]["time_conflict_high_risk_items"] == 2
    assert summary["analysis_conclusion"]["preview_safe_new_candidate_class"] == "strict_time_normalization_only"


def test_cluster_blocker_analysis_suite_rejects_unsafe_inputs():
    queue = _priority_queue()
    queue["canonical_outputs_mutated"] = True

    with pytest.raises(ValueError, match="canonical_outputs_mutated"):
        summarize_entity_resolution_cluster_blocker_analysis_suite(
            priority_queue=queue,
            time_norm_subset=_time_norm_subset(),
            time_conflict_analysis=_analysis("entity_resolution_cluster_time_conflict_review_only", 2, 2),
            type_conflict_analysis=_analysis("entity_resolution_cluster_type_conflict_review_only", 2, 2),
            coordinate_conflict_analysis=_analysis("entity_resolution_cluster_coordinate_conflict_review_only", 1, 1),
        )
