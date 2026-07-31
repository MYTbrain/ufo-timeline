from scripts.build_mixed_medium_review_triage_digest import build_mixed_medium_review_triage_digest


def test_mixed_medium_review_triage_digest_is_report_only_and_sums_lanes():
    digest = build_mixed_medium_review_triage_digest(
        review_reports={
            "medium_identity_mixed": _report("identity", 2, 3),
            "medium_classification_mixed": _report("classification", 4, 7),
            "medium_body_text_mixed": _report("body", 5, 11),
        },
        action_matrix={"report_policy": "manual_review_remaining_lane_action_matrix_v1", "ready_for_runtime_promotion": False},
    )

    assert digest["digest_policy"] == "mixed_medium_review_triage_digest_report_only"
    assert digest["canonical_outputs_mutated"] is False
    assert digest["preview_outputs_written"] is False
    assert digest["decisions_created"] is False
    assert digest["ready_for_canonical_apply"] is False
    assert digest["summary"]["reviewed_item_count"] == 11
    assert digest["summary"]["projected_event_reduction_total"] == 21
    assert digest["summary"]["lane_counts"]["medium_body_text_mixed"] == 5
    assert digest["lanes"]["medium_classification_mixed"]["top_review_items"][0]["replacement_event_id"] == "evt_classification"


def _report(label, count, projection):
    return {
        "review_policy": f"manual_review_medium_{label}_mixed_review_v1",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "ready_for_runtime_promotion": False,
        "summary": {
            "reviewed_item_count": count,
            "review_recommendation_counts": {f"needs_deeper_{label}_mixed_review": count},
            f"{label}_mixed_subcategory_counts": {f"{label}_plus_time_conflict": count},
            "confidence_counts": {"low": count},
            "projected_event_reduction_by_review_recommendation": {
                f"needs_deeper_{label}_mixed_review": projection
            },
        },
        "items": [
            {
                "review_rank": 1,
                "replacement_event_id": f"evt_{label}",
                "review_recommendation": f"needs_deeper_{label}_mixed_review",
                "projected_event_reduction": projection,
                "risk_flags": ["time_raw_conflict"],
            }
        ],
    }
