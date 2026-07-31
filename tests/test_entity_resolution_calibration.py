import pytest

from scripts.summarize_entity_resolution_calibration import summarize_entity_resolution_calibration


def _safe_score_report(score_summary):
    return {
        "report_policy": "entity_resolution_scoring_analysis_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "score_summary": score_summary,
    }


def _safe_review_packet(export_summary):
    return {
        "packet_policy": "entity_resolution_review_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "export_summary": export_summary,
    }


def test_summarize_entity_resolution_calibration_extracts_review_hotspots():
    score_report = _safe_score_report(
        {
            "scored_pair_count": 10,
            "cross_event_scored_pair_count": 8,
            "pair_scoring_truncated": False,
            "band_counts": {
                "likely_same_event_review": 4,
                "strong_candidate_review": 3,
                "moderate_candidate_review": 2,
                "weak_candidate": 1,
            },
            "band_risk_flag_counts": {
                "likely_same_event_review": {
                    "weak_text_overlap": 3,
                    "type_differs": 2,
                    "short_text_match_limited": 1,
                },
                "strong_candidate_review": {
                    "coordinates_far_apart": 2,
                    "shape_differs": 1,
                },
            },
            "band_source_pair_counts": {
                "likely_same_event_review": {
                    "ufocat|ufocat": 7,
                    "mufon|nuforc": 2,
                },
            },
            "projected_cross_event_reduction": {
                "likely_same_event_review": 3,
                "strong_or_better": 4,
            },
        }
    )
    review_packet = _safe_review_packet(
        {
            "available_sample_scope": "per_band_cross_event_scored_pair_samples",
            "exported_item_count": 2,
            "cross_event_only": True,
            "band_counts": {"likely_same_event_review": 1, "strong_candidate_review": 1},
            "risk_flag_counts": {"type_differs": 1},
        }
    )

    summary = summarize_entity_resolution_calibration(
        score_report=score_report,
        review_packet=review_packet,
    )

    assert summary["canonical_outputs_mutated"] is False
    assert summary["preview_outputs_written"] is False
    assert summary["decisions_created"] is False
    assert summary["auto_merge_performed"] is False
    assert summary["score_overview"]["scored_pair_count"] == 10
    assert summary["score_overview"]["projected_cross_event_reduction"]["strong_or_better"] == 4
    assert summary["risk_hotspots"]["likely_same_event_review"]["top_risk_flags"][0] == {
        "key": "weak_text_overlap",
        "count": 3,
    }
    assert summary["risk_hotspots"]["likely_same_event_review"]["high_attention_risk_flags"] == {
        "short_text_match_limited": 1,
        "type_differs": 2,
        "weak_text_overlap": 3,
    }
    assert summary["source_pair_hotspots"]["likely_same_event_review"][0] == {
        "key": "ufocat|ufocat",
        "count": 7,
    }
    assert summary["packet_sample_overview"]["exported_item_count"] == 2
    assert summary["workflow_readiness"] == {
        "calibration_status": "ready_for_review",
        "review_packet_available": True,
        "review_packet_cross_event_only": True,
        "ready_for_human_review": True,
        "ready_for_apply": False,
        "apply_blocker": "validated_same_event_decisions_required",
    }


def test_summarize_entity_resolution_calibration_marks_missing_packet_not_ready():
    summary = summarize_entity_resolution_calibration(
        score_report=_safe_score_report({"pair_scoring_truncated": True}),
        review_packet=None,
    )

    assert summary["inputs"]["review_packet_present"] is False
    assert summary["packet_sample_overview"]["exported_item_count"] == 0
    assert summary["workflow_readiness"]["calibration_status"] == "incomplete"
    assert summary["workflow_readiness"]["review_packet_available"] is False
    assert summary["workflow_readiness"]["ready_for_human_review"] is False
    assert summary["workflow_readiness"]["ready_for_apply"] is False
    assert summary["review_priorities"][-1]["priority"] == "generate_review_packet"


def test_summarize_entity_resolution_calibration_rejects_unsafe_inputs():
    unsafe_score_report = _safe_score_report({})
    unsafe_score_report["canonical_outputs_mutated"] = True

    with pytest.raises(ValueError, match="score_report is not a safe report-only input"):
        summarize_entity_resolution_calibration(
            score_report=unsafe_score_report,
            review_packet=None,
        )

    unsafe_review_packet = _safe_review_packet({})
    unsafe_review_packet["packet_policy"] = "unexpected"

    with pytest.raises(ValueError, match="review_packet is not a safe report-only input"):
        summarize_entity_resolution_calibration(
            score_report=_safe_score_report({}),
            review_packet=unsafe_review_packet,
        )
