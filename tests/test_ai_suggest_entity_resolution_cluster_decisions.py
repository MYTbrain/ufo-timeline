import pytest

from scripts.ai_suggest_entity_resolution_cluster_decisions import (
    build_entity_resolution_cluster_ai_suggestions,
)


def _packet_item(**overrides):
    item = {
        "cluster_review_id": "er_cluster_a",
        "family_id": "same_source_native_id_strong_date",
        "tier": "conservative",
        "projected_event_reduction": 2,
        "unique_current_event_count": 3,
        "source_record_count": 4,
        "current_event_ids": ["evt_a", "evt_b", "evt_c"],
        "current_event_ids_truncated": False,
        "distinct_date_count": 1,
        "distinct_location_count": 1,
    }
    item.update(overrides)
    return item


def _packet(*items):
    return {
        "packet_policy": "entity_resolution_cluster_review_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "items": list(items),
    }


def test_cluster_ai_suggestions_marks_strict_conservative_complete_cluster_same_event():
    suggestions, report = build_entity_resolution_cluster_ai_suggestions(
        _packet(_packet_item()),
        reviewed_at="2026-05-22T00:00:00+00:00",
    )

    assert report["canonical_outputs_mutated"] is False
    assert report["decisions_created"] is False
    assert report["suggested_decision_counts"] == {"same_event": 1}
    assert suggestions[0]["cluster_review_id"] == "er_cluster_a"
    assert suggestions[0]["suggested_decision"] == "same_event"
    assert suggestions[0]["confidence"] == "medium"


def test_cluster_ai_suggestions_defers_truncated_or_nonconservative_clusters():
    packet = _packet(
        _packet_item(cluster_review_id="er_cluster_a", current_event_ids=["evt_a", "evt_b"], current_event_ids_truncated=True),
        _packet_item(cluster_review_id="er_cluster_b", tier="aggressive"),
    )

    suggestions, report = build_entity_resolution_cluster_ai_suggestions(packet)

    assert report["suggested_decision_counts"] == {"needs_more_evidence": 2}
    assert [item["suggested_decision"] for item in suggestions] == ["needs_more_evidence", "needs_more_evidence"]


def test_cluster_ai_suggestions_rejects_unsafe_packet():
    packet = _packet(_packet_item())
    packet["canonical_outputs_mutated"] = True

    with pytest.raises(ValueError, match="canonical_outputs_mutated"):
        build_entity_resolution_cluster_ai_suggestions(packet)
