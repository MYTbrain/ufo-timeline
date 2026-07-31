import pytest

from scripts.analyze_entity_resolution_cluster_time_conflicts import (
    analyze_entity_resolution_cluster_time_conflicts,
)


def _queue_item(review_item_id, times, *, source_summary=None, projected_reduction=2, bucket="time_conflict_review", risks=None):
    return {
        "triage_bucket": bucket,
        "review_item_id": review_item_id,
        "effect_id": f"effect_{review_item_id}",
        "projected_event_reduction": projected_reduction,
        "blocking_fields": ["time_raw"],
        "field_conflict_values": {"time_raw": times},
        "risks": risks or [],
        "source_summary": source_summary
        or {
            "canonical_event_count": 2,
            "canonical_event_ids": [f"evt_{review_item_id}_a", f"evt_{review_item_id}_b"],
            "source_names": ["ufocat"],
            "source_native_ids": [f"native_{review_item_id}"],
            "date_values": ["1954-09-19"],
            "location_values": ["RONGERES, FRA"],
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
            _queue_item("close_exact", ["2300", "2310"], projected_reduction=3),
            _queue_item("wide_exact", ["1800", "2100"]),
            _queue_item("fuzzy_context", ["2030", "Dusk", "Night"]),
            _queue_item("approx_context", ["2300", "23+"]),
            _queue_item("coordinate_risk", ["1100", "1110"], risks=["coordinates differ"]),
            _queue_item(
                "mixed_identity",
                ["1000", "1010"],
                source_summary={
                    "canonical_event_count": 2,
                    "canonical_event_ids": ["evt_mixed_a", "evt_mixed_b"],
                    "source_names": ["ufocat", "nuforc"],
                    "source_native_ids": ["native_mixed"],
                    "date_values": ["1954-09-19"],
                    "location_values": ["RONGERES, FRA"],
                },
            ),
            _queue_item("time_format_ignored", ["1000", "1010"], bucket="time_format_review"),
        ],
    }


def test_time_conflict_analysis_classifies_conflicts_and_identity_risk():
    analysis = analyze_entity_resolution_cluster_time_conflicts(priority_queue=_priority_queue())

    assert analysis["analysis_policy"] == "entity_resolution_cluster_time_conflict_review_only"
    assert analysis["canonical_outputs_mutated"] is False
    assert analysis["decisions_created"] is False
    assert analysis["summary"]["analyzed_item_count"] == 6
    assert analysis["summary"]["classification_counts"] == {
        "nearby_exact_conflict_15m_or_less": 3,
        "single_exact_with_approximation_context": 1,
        "single_exact_with_fuzzy_context": 1,
        "wide_exact_conflict_over_60m": 1,
    }
    assert analysis["summary"]["review_risk_tier_counts"] == {
        "high": 3,
        "lower": 1,
        "medium": 2,
    }

    by_id = {item["review_item_id"]: item for item in analysis["items"]}
    assert by_id["close_exact"]["review_risk_tier"] == "lower"
    assert by_id["close_exact"]["exact_span_minutes"] == 10
    assert by_id["approx_context"]["review_risk_tier"] == "medium"
    assert by_id["coordinate_risk"]["has_coordinate_risk"] is True
    assert by_id["coordinate_risk"]["review_risk_tier"] == "high"
    assert by_id["mixed_identity"]["identity_consistency"] == "mixed_or_incomplete_identity"
    assert by_id["mixed_identity"]["review_risk_tier"] == "high"


def test_time_conflict_analysis_rejects_unsafe_priority_queue():
    queue = _priority_queue()
    queue["canonical_outputs_mutated"] = True

    with pytest.raises(ValueError, match="canonical_outputs_mutated"):
        analyze_entity_resolution_cluster_time_conflicts(priority_queue=queue)
