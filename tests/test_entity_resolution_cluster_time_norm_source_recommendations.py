import pytest

from scripts.recommend_entity_resolution_cluster_time_norm_source_decisions import (
    NEEDS_MORE_EVIDENCE,
    RECOMMEND_SAME_EVENT,
    build_time_norm_source_review_recommendations,
)


def _item(review_item_id="er_cluster_a", *, time_tokens=None, parsed_minutes=None, blockers=None):
    return {
        "review_rank": 1,
        "review_item_id": review_item_id,
        "effect_id": f"ere_{review_item_id}",
        "projected_event_reduction": 1,
        "shadow_preview_override_source": {
            "time_pattern_classification": "nearby_exact_minutes_15m_or_less",
            "review_risk_tier": "lower",
            "parsed_minutes": parsed_minutes or [600, 605],
            "time_tokens": time_tokens or ["1000", "1005"],
            "hard_gates": {
                "eligible_classification": True,
                "lower_risk_tier": True,
                "no_fuzzy_ambiguous_or_unknown_tokens": True,
                "span_minutes_at_or_below": 15,
            },
        },
        "candidate_canonical_input_ids": ["cin_a", "cin_b"],
        "candidate_input_ids_missing_from_evidence": blockers or [],
        "merge_canonical_event_ids": ["evt_a", "evt_b"],
        "missing_canonical_event_ids": [],
        "source_summary": {
            "source_names": ["ufocat"],
            "source_native_ids": ["native_1"],
            "date_values": ["1954-09-19"],
            "location_values": ["RONGERES, FRA"],
        },
        "conflict_summary": {
            "conflict_flags": {
                "time": True,
                "date": False,
                "location": False,
                "coordinate": False,
                "type": False,
                "shape": False,
                "source_native_id": False,
            }
        },
    }


def _packet(*items):
    return {
        "packet_policy": "entity_resolution_cluster_time_normalization_source_row_evidence_review_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "auto_merge_performed": False,
        "override_decisions_created": False,
        "ready_for_canonical_apply": False,
        "items": list(items),
    }


def test_time_norm_source_recommendations_accept_clean_clock_tokens_only():
    report = build_time_norm_source_review_recommendations(
        _packet(
            _item("clean", time_tokens=["1000", "1005"], parsed_minutes=[600, 605]),
            _item("symbolic", time_tokens=["10+", "1000"], parsed_minutes=[600]),
        )
    )

    assert report["recommendation_policy"] == "entity_resolution_time_norm_auto_recommendation_only"
    assert report["canonical_outputs_mutated"] is False
    assert report["decisions_created"] is False
    assert report["ready_for_canonical_apply"] is False
    assert report["summary"]["reviewed_item_count"] == 2
    assert report["summary"]["duplicate_review_item_id_count"] == 0
    assert report["summary"]["duplicate_effect_id_count"] == 0
    assert report["summary"]["recommendation_counts"] == {
        NEEDS_MORE_EVIDENCE: 1,
        RECOMMEND_SAME_EVENT: 1,
    }
    assert report["summary"]["token_class_counts"] == {
        "clean_clock_tokens": 1,
        "symbolic_or_shorthand_tokens": 1,
    }
    clean, symbolic = report["recommendations"]
    assert clean["recommendation"] == RECOMMEND_SAME_EVENT
    assert clean["blockers"] == []
    assert clean["minute_span"] == 5
    assert "auto_recommend_preview_candidate_numeric_time_only" in clean["reason_codes"]
    assert symbolic["recommendation"] == NEEDS_MORE_EVIDENCE
    assert "symbolic_or_shorthand_time_tokens" in symbolic["blockers"]
    assert "insufficient_parsed_minutes" in symbolic["blockers"]
    assert "defer_symbolic_or_short_time_token" in symbolic["reason_codes"]


def test_time_norm_source_recommendations_block_non_time_conflicts():
    item = _item()
    item["conflict_summary"]["conflict_flags"]["location"] = True

    report = build_time_norm_source_review_recommendations(_packet(item))

    assert report["summary"]["recommendation_counts"] == {NEEDS_MORE_EVIDENCE: 1}
    assert report["recommendations"][0]["blockers"] == ["non_time_conflicts_present"]


def test_time_norm_source_recommendations_reject_unsafe_packet():
    packet = _packet(_item())
    packet["ready_for_canonical_apply"] = True

    with pytest.raises(ValueError, match="ready_for_canonical_apply"):
        build_time_norm_source_review_recommendations(packet)
