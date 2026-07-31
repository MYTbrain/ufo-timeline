import pytest

from scripts.review_time_norm_deferred_shorthand_candidates import (
    REMAIN_DEFERRED,
    SOURCE_REVIEW_SAME_EVENT,
    build_deferred_shorthand_review,
    parse_time_tokens,
)


def _recommendation(review_item_id="er_cluster_a", *, blockers=None, active_conflicts=None):
    return {
        "review_rank": 1,
        "review_item_id": review_item_id,
        "cluster_review_id": review_item_id,
        "effect_id": f"ere_{review_item_id}",
        "recommendation": "needs_more_evidence",
        "projected_event_reduction": 1,
        "time_tokens": ["20+", "2000", "2015"],
        "parsed_minutes": [1200, 1215],
        "blockers": blockers or ["symbolic_or_shorthand_time_tokens"],
        "active_conflicts": active_conflicts or ["time"],
        "merge_canonical_event_ids": ["evt_a", "evt_b"],
        "candidate_canonical_input_ids": ["cin_a", "cin_b"],
    }


def _packet_item(review_item_id="er_cluster_a", *, conflict_flags=None, summaries=None, shape_values=None):
    summaries = summaries or ["Same source text.", "Same source text."]
    return {
        "review_item_id": review_item_id,
        "effect_id": f"ere_{review_item_id}",
        "projected_event_reduction": 1,
        "candidate_canonical_input_ids": ["cin_a", "cin_b"],
        "candidate_input_ids_missing_from_evidence": [],
        "merge_canonical_event_ids": ["evt_a", "evt_b"],
        "missing_canonical_event_ids": [],
        "source_summary": {
            "source_names": ["ufocat"],
            "source_native_ids": ["native_1"],
            "date_values": ["1965-11-26"],
            "date_precision_values": ["exact_day"],
            "location_values": ["ST PAUL, Ramsey, MN, US"],
            "coordinate_values": ["44.95,-93.09"],
            "type_values": ["5ew"],
            "shape_values": shape_values if shape_values is not None else ["lights"],
        },
        "conflict_summary": {
            "conflict_flags": conflict_flags
            or {
                "time": True,
                "date": False,
                "location": False,
                "coordinate": False,
                "type": False,
                "shape": False,
                "source_native_id": False,
            }
        },
        "evidence_rows": [{"summary": text} for text in summaries],
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


def _recommendations_report(*items):
    return {
        "recommendation_policy": "entity_resolution_time_norm_auto_recommendation_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "validated_decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "recommendations": list(items),
    }


def test_parse_time_tokens_handles_hour_shorthand_with_exact_clock_tokens():
    result = parse_time_tokens(["20+", "2000", "2015", "21"])

    assert result["all_tokens_parsed"] is True
    assert result["has_exact_clock_token"] is True
    assert result["has_shorthand_token"] is True
    assert result["parsed_minutes"] == [1200, 1215, 1260]
    assert result["minute_span"] == 60


def test_deferred_shorthand_review_recommends_source_review_candidate_for_time_only_rows():
    report = build_deferred_shorthand_review(
        packet=_packet(_packet_item()),
        recommendations_report=_recommendations_report(_recommendation()),
    )

    assert report["canonical_outputs_mutated"] is False
    assert report["decisions_created"] is False
    assert report["ready_for_canonical_apply"] is False
    assert report["summary"]["review_recommendation_counts"] == {SOURCE_REVIEW_SAME_EVENT: 1}
    item = report["items"][0]
    assert item["review_recommendation"] == SOURCE_REVIEW_SAME_EVENT
    assert item["failed_conditions"] == []
    assert "source_review_shorthand_time_only" in item["review_reason_codes"]


def test_deferred_shorthand_review_keeps_non_time_conflicts_deferred():
    conflict_flags = {
        "time": True,
        "date": False,
        "location": False,
        "coordinate": False,
        "type": False,
        "shape": True,
        "source_native_id": False,
    }

    report = build_deferred_shorthand_review(
        packet=_packet(_packet_item(conflict_flags=conflict_flags, shape_values=["disc", "polymorf"])),
        recommendations_report=_recommendations_report(
            _recommendation(blockers=["non_time_conflicts_present"], active_conflicts=["shape", "time"])
        ),
    )

    item = report["items"][0]
    assert item["review_recommendation"] == REMAIN_DEFERRED
    assert "time_only_conflict" in item["failed_conditions"]
    assert "single_shape_or_blank" in item["failed_conditions"]


def test_deferred_shorthand_review_keeps_insufficient_distinct_minutes_deferred():
    report = build_deferred_shorthand_review(
        packet=_packet(_packet_item()),
        recommendations_report=_recommendations_report(
            _recommendation(
                blockers=["symbolic_or_shorthand_time_tokens", "insufficient_parsed_minutes"],
            )
            | {
                "time_tokens": ["19+", "1900"],
                "parsed_minutes": [1140],
            }
        ),
    )

    item = report["items"][0]
    assert item["review_recommendation"] == REMAIN_DEFERRED
    assert "allowed_shorthand_blockers_only" in item["failed_conditions"]
    assert "at_least_two_distinct_parsed_minutes" in item["failed_conditions"]


def test_deferred_shorthand_review_rejects_unsafe_inputs():
    packet = _packet(_packet_item())
    packet["ready_for_canonical_apply"] = True

    with pytest.raises(ValueError, match="ready_for_canonical_apply"):
        build_deferred_shorthand_review(
            packet=packet,
            recommendations_report=_recommendations_report(_recommendation()),
        )
