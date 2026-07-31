import pytest

from scripts.review_likely_time_format_candidates import (
    REMAIN_DEFERRED,
    SOURCE_REVIEW_SAME_EVENT,
    build_likely_time_format_review,
    parse_time_tokens,
)


def _packet_item(review_item_id="er_cluster_a", *, time_values=None, conflict_flags=None, summaries=None):
    summaries = summaries or ["Same source text.", "Same source text."]
    return {
        "review_rank": 1,
        "review_item_id": review_item_id,
        "effect_id": f"ere_{review_item_id}",
        "projected_event_reduction": 1,
        "candidate_canonical_input_ids": ["cin_a", "cin_b"],
        "candidate_input_ids_missing_from_evidence": [],
        "merge_canonical_event_ids": ["evt_a", "evt_b"],
        "missing_canonical_event_ids": [],
        "shadow_preview_override_source": {
            "classification": "likely_time_format_variant",
            "suggested_action": "candidate_shadow_preview_override",
            "analysis_confidence": "high",
        },
        "source_summary": {
            "source_names": ["ufocat"],
            "source_native_ids": ["native_1"],
            "date_values": ["1965-11-26"],
            "date_precision_values": ["exact_day"],
            "location_values": ["ST PAUL, Ramsey, MN, US"],
            "coordinate_values": ["44.95,-93.09"],
            "type_values": ["5ew"],
            "shape_values": [""],
            "time_values": time_values or ["21", "2100"],
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
        "packet_policy": "entity_resolution_likely_time_format_source_row_evidence_review_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "auto_merge_performed": False,
        "override_decisions_created": False,
        "ready_for_canonical_apply": False,
        "items": list(items),
    }


def test_parse_time_tokens_requires_bare_hour_and_exact_clock_same_minute():
    result = parse_time_tokens(["21", "2100"])

    assert result["all_tokens_parsed"] is True
    assert result["has_bare_hour_token"] is True
    assert result["has_exact_clock_token"] is True
    assert result["parsed_minutes"] == [1260]
    assert result["distinct_minute_count"] == 1


def test_likely_time_format_review_accepts_bare_hour_exact_clock_variant():
    report = build_likely_time_format_review(_packet(_packet_item()))

    assert report["canonical_outputs_mutated"] is False
    assert report["decisions_created"] is False
    assert report["ready_for_canonical_apply"] is False
    assert report["summary"]["review_recommendation_counts"] == {SOURCE_REVIEW_SAME_EVENT: 1}
    item = report["items"][0]
    assert item["review_recommendation"] == SOURCE_REVIEW_SAME_EVENT
    assert item["failed_conditions"] == []
    assert "source_review_bare_hour_matches_exact_clock" in item["review_reason_codes"]


def test_likely_time_format_review_defer_when_exact_clock_minutes_differ():
    report = build_likely_time_format_review(_packet(_packet_item(time_values=["21", "2115"])))

    item = report["items"][0]
    assert item["review_recommendation"] == REMAIN_DEFERRED
    assert "all_tokens_parse_to_same_minute" in item["failed_conditions"]


def test_likely_time_format_review_defer_when_non_time_conflict_exists():
    conflict_flags = {
        "time": True,
        "date": False,
        "location": False,
        "coordinate": False,
        "type": False,
        "shape": True,
        "source_native_id": False,
    }

    report = build_likely_time_format_review(_packet(_packet_item(conflict_flags=conflict_flags)))

    item = report["items"][0]
    assert item["review_recommendation"] == REMAIN_DEFERRED
    assert "time_only_conflict" in item["failed_conditions"]


def test_likely_time_format_review_rejects_unsafe_packet():
    packet = _packet(_packet_item())
    packet["ready_for_canonical_apply"] = True

    with pytest.raises(ValueError, match="ready_for_canonical_apply"):
        build_likely_time_format_review(packet)
