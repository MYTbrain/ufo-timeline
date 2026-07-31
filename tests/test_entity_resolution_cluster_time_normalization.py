import pytest

from scripts.analyze_entity_resolution_cluster_time_normalization import (
    analyze_entity_resolution_cluster_time_normalization,
    parse_time_token,
)


def _queue_item(review_item_id, time_values, projected_event_reduction=1):
    return {
        "triage_bucket": "time_format_review",
        "review_item_id": review_item_id,
        "effect_id": f"effect_{review_item_id}",
        "patch_id": f"patch_{review_item_id}",
        "projected_event_reduction": projected_event_reduction,
        "blocking_fields": ["time_raw"],
        "field_conflict_values": {"time_raw": time_values},
        "source_summary": {
            "canonical_event_ids": [f"evt_{review_item_id}_1", f"evt_{review_item_id}_2"],
            "canonical_input_ids": [f"cin_{review_item_id}_1", f"cin_{review_item_id}_2"],
            "canonical_event_count": 2,
            "source_names": ["ufocat"],
            "source_native_ids": ["1"],
            "date_values": ["1954-09-19"],
            "location_values": ["RONGERES, FRA"],
            "type_values": ["3l"],
        },
    }


def _priority_queue():
    return {
        "queue_policy": "entity_resolution_cluster_blocker_priority_queue_review_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "items": [
            _queue_item("single", ["1630", "16:30"], 3),
            _queue_item("context", ["1200", "Noon", "Day"], 4),
            _queue_item("near", ["0010", "0015"], 2),
            _queue_item("distinct", ["0100", "0300"], 10),
            {"triage_bucket": "coordinate_conflict_review", "review_item_id": "ignore_me"},
        ],
    }


def test_parse_time_token_handles_exact_fuzzy_and_ambiguous_tokens():
    assert parse_time_token("16:30")["minute"] == 990
    assert parse_time_token("1630")["minute"] == 990
    assert parse_time_token("Noon")["bucket_label"] == "noon"
    assert parse_time_token("Even")["bucket_label"] == "evening"
    assert parse_time_token("9")["kind"] == "ambiguous"
    assert parse_time_token("After")["kind"] == "unknown"


def test_cluster_time_normalization_analysis_classifies_time_format_review_items_only():
    analysis = analyze_entity_resolution_cluster_time_normalization(priority_queue=_priority_queue())

    assert analysis["analysis_policy"] == "entity_resolution_cluster_time_normalization_review_only"
    assert analysis["canonical_outputs_mutated"] is False
    assert analysis["decision_outputs_created"] is False
    assert analysis["summary"]["analyzed_item_count"] == 4
    assert analysis["summary"]["classification_counts"] == {
        "multiple_distinct_exact_minutes": 1,
        "nearby_exact_minutes_15m_or_less": 1,
        "single_exact_minute": 1,
        "single_exact_minute_with_context_tokens": 1,
    }
    assert analysis["items"][0]["review_item_id"] == "single"
    assert analysis["items"][0]["blocking_fields"] == ["time_raw"]
    assert analysis["items"][0]["parsed_minutes"] == [990]
    assert analysis["items"][0]["source_summary"]["canonical_event_count"] == 2
    assert analysis["items"][-1]["review_item_id"] == "distinct"


def test_cluster_time_normalization_analysis_rejects_unsafe_queue():
    queue = _priority_queue()
    queue["auto_merge_performed"] = True

    with pytest.raises(ValueError, match="auto_merge_performed"):
        analyze_entity_resolution_cluster_time_normalization(priority_queue=queue)
