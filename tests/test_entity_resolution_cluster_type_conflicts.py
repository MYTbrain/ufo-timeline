import pytest

from scripts.analyze_entity_resolution_cluster_type_conflicts import (
    analyze_entity_resolution_cluster_type_conflicts,
)


def _queue_item(
    review_item_id,
    type_values,
    *,
    blocking_fields=None,
    shape_values=None,
    time_values=None,
    source_summary=None,
    risks=None,
    projected_reduction=2,
    bucket="type_conflict_review",
):
    return {
        "triage_bucket": bucket,
        "review_item_id": review_item_id,
        "effect_id": f"effect_{review_item_id}",
        "projected_event_reduction": projected_reduction,
        "blocking_fields": blocking_fields or ["type_normalized"],
        "field_conflict_values": {
            "type_normalized": type_values,
            "shape_normalized": shape_values or [],
            "time_raw": time_values or [],
        },
        "risks": risks or [],
        "source_summary": source_summary
        or {
            "canonical_event_count": 2,
            "canonical_event_ids": [f"evt_{review_item_id}_a", f"evt_{review_item_id}_b"],
            "source_names": ["ufocat"],
            "source_native_ids": [f"native_{review_item_id}"],
            "date_values": ["1954-09-19"],
            "location_values": ["RONGERES, FRA"],
            "type_values": type_values,
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
            _queue_item("single_family", ["5e", "5em"], projected_reduction=4),
            _queue_item("shape_conflict", ["5e", "5em"], shape_values=["disc", "ball"]),
            _queue_item("cross_family", ["5e", "6t"]),
            _queue_item(
                "coordinate_conflict",
                ["5e", "5em"],
                blocking_fields=["coordinate_distance_over_10km", "type_normalized"],
                risks=["coordinates differ"],
            ),
            _queue_item(
                "mixed_identity",
                ["5e", "5em"],
                source_summary={
                    "canonical_event_count": 2,
                    "canonical_event_ids": ["evt_mixed_a", "evt_mixed_b"],
                    "source_names": ["ufocat", "nuforc"],
                    "source_native_ids": ["native_mixed"],
                    "date_values": ["1954-09-19"],
                    "location_values": ["RONGERES, FRA"],
                    "type_values": ["5e", "5em"],
                },
            ),
            _queue_item("time_conflict_ignored", ["5e", "5em"], bucket="time_conflict_review"),
        ],
    }


def test_type_conflict_analysis_classifies_type_and_identity_risk():
    analysis = analyze_entity_resolution_cluster_type_conflicts(priority_queue=_priority_queue())

    assert analysis["analysis_policy"] == "entity_resolution_cluster_type_conflict_review_only"
    assert analysis["canonical_outputs_mutated"] is False
    assert analysis["decisions_created"] is False
    assert analysis["summary"]["analyzed_item_count"] == 5
    assert analysis["summary"]["classification_counts"] == {
        "type_only_single_family_subcode_conflict": 2,
        "type_only_single_family_with_shape_conflict": 1,
        "type_only_cross_family_conflict": 1,
        "type_with_coordinate_conflict": 1,
    }
    assert analysis["summary"]["review_risk_tier_counts"] == {
        "high": 3,
        "lower": 1,
        "medium": 1,
    }

    by_id = {item["review_item_id"]: item for item in analysis["items"]}
    assert by_id["single_family"]["review_risk_tier"] == "lower"
    assert by_id["shape_conflict"]["review_risk_tier"] == "medium"
    assert by_id["coordinate_conflict"]["has_coordinate_risk"] is True
    assert by_id["coordinate_conflict"]["review_risk_tier"] == "high"
    assert by_id["mixed_identity"]["identity_consistency"] == "mixed_or_incomplete_identity"
    assert by_id["mixed_identity"]["review_risk_tier"] == "high"


def test_type_conflict_analysis_rejects_unsafe_priority_queue():
    queue = _priority_queue()
    queue["auto_merge_performed"] = True

    with pytest.raises(ValueError, match="auto_merge_performed"):
        analyze_entity_resolution_cluster_type_conflicts(priority_queue=queue)
