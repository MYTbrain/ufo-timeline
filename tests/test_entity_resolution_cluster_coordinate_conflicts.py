import pytest

from scripts.analyze_entity_resolution_cluster_coordinate_conflicts import (
    analyze_entity_resolution_cluster_coordinate_conflicts,
)


def _queue_item(review_item_id, distance_km, *, source_summary=None, bucket="coordinate_conflict_review"):
    return {
        "triage_bucket": bucket,
        "review_item_id": review_item_id,
        "effect_id": f"effect_{review_item_id}",
        "projected_event_reduction": 2,
        "blocking_fields": ["coordinate_distance_over_10km", "time_raw"],
        "field_conflict_values": {"time_raw": ["1200", "1210"], "type_normalized": []},
        "reasons": [
            "coordinate conflict lacks enough matching identity evidence for an override suggestion",
            f"max_coordinate_distance_km={distance_km}",
        ],
        "source_summary": source_summary
        or {
            "canonical_event_count": 2,
            "canonical_event_ids": [f"evt_{review_item_id}_a", f"evt_{review_item_id}_b"],
            "source_names": ["ufocat"],
            "source_native_ids": [f"native_{review_item_id}"],
            "date_values": ["1954-09-19"],
            "location_values": ["RONGERES, FRA"],
            "type_values": ["5e"],
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
            _queue_item("near", "12.5"),
            _queue_item("medium", "40.0"),
            _queue_item("wide", "100.0"),
            _queue_item("very_wide", "250.0"),
            _queue_item("ignored", "250.0", bucket="time_conflict_review"),
        ],
    }


def test_coordinate_conflict_analysis_buckets_distances_and_keeps_high_risk():
    analysis = analyze_entity_resolution_cluster_coordinate_conflicts(priority_queue=_priority_queue())

    assert analysis["analysis_policy"] == "entity_resolution_cluster_coordinate_conflict_review_only"
    assert analysis["canonical_outputs_mutated"] is False
    assert analysis["decisions_created"] is False
    assert analysis["summary"]["analyzed_item_count"] == 4
    assert analysis["summary"]["classification_counts"] == {
        "coordinate_conflict_10_to_15km": 1,
        "coordinate_conflict_15_to_50km": 1,
        "coordinate_conflict_50_to_150km": 1,
        "coordinate_conflict_over_150km": 1,
    }
    assert analysis["summary"]["review_risk_tier_counts"] == {"high": 4}
    assert analysis["summary"]["max_coordinate_distance_km"] == 250.0


def test_coordinate_conflict_analysis_rejects_unsafe_priority_queue():
    queue = _priority_queue()
    queue["preview_outputs_written"] = True

    with pytest.raises(ValueError, match="preview_outputs_written"):
        analyze_entity_resolution_cluster_coordinate_conflicts(priority_queue=queue)
