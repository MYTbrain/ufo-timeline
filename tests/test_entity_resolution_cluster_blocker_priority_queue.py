import pytest

from scripts.build_entity_resolution_cluster_blocker_priority_queue import (
    build_entity_resolution_cluster_blocker_priority_queue,
)


def _action_item(review_item_id, classification, projected_event_reduction, blocking_fields):
    return {
        "review_item_id": review_item_id,
        "patch_id": f"patch_{review_item_id}",
        "effect_id": f"effect_{review_item_id}",
        "classification": classification,
        "suggested_action": "time_review_before_override",
        "analysis_confidence": "medium",
        "projected_event_reduction": projected_event_reduction,
        "blocking_fields": blocking_fields,
        "field_conflict_values": {"time_raw": ["1630", "16:30"], "type_normalized": [], "shape_normalized": []},
        "source_summary": {
            "canonical_event_ids": [f"evt_{review_item_id}_1", f"evt_{review_item_id}_2"],
            "canonical_input_ids": [f"cin_{review_item_id}_1", f"cin_{review_item_id}_2"],
            "canonical_event_count": 2,
            "canonical_input_id_count": 2,
            "source_names": ["ufocat"],
            "source_native_ids": ["171782"],
            "date_values": ["1954-09-19"],
            "time_values": ["1630", "16:30"],
            "location_values": ["RONGERES, FRA"],
            "type_values": ["3l"],
            "source_event_count": 2,
        },
        "reasons": ["review needed"],
        "risks": [],
    }


def _action_packet():
    return {
        "packet_policy": "entity_resolution_blocked_merge_action_review_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "items": [
            _action_item("selected_1", "likely_time_format_variant", 1, ["time_raw"]),
            _action_item("time_review_1", "time_format_or_multiple_time_variant", 3, ["time_raw"]),
            _action_item("coord_review_1", "coordinate_conflict_requires_review", 8, ["coordinate_distance_over_10km"]),
        ],
    }


def _override_subset():
    return {
        "subset_policy": "entity_resolution_shadow_preview_subset_with_analysis_overrides",
        "canonical_outputs_mutated": False,
        "canonical_outputs_mutated_by_plan": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "override_decisions_created": False,
        "override_review_item_ids": ["selected_1"],
    }


def test_cluster_blocker_priority_queue_excludes_current_shadow_override_items_by_default():
    queue = build_entity_resolution_cluster_blocker_priority_queue(
        action_packet=_action_packet(),
        override_subset=_override_subset(),
    )

    assert queue["queue_policy"] == "entity_resolution_cluster_blocker_priority_queue_review_only"
    assert queue["canonical_outputs_mutated"] is False
    assert queue["decision_outputs_created"] is False
    assert queue["summary"]["source_action_item_count"] == 3
    assert queue["summary"]["skipped_already_selected_count"] == 1
    assert queue["summary"]["queue_item_count"] == 2
    assert [item["review_item_id"] for item in queue["items"]] == ["time_review_1", "coord_review_1"]
    assert queue["items"][0]["source_summary"]["canonical_event_count"] == 2
    assert queue["items"][0]["source_summary"]["canonical_event_ids"] == ["evt_time_review_1_1", "evt_time_review_1_2"]
    assert queue["summary"]["triage_bucket_counts"] == {
        "coordinate_conflict_review": 1,
        "time_format_review": 1,
    }


def test_cluster_blocker_priority_queue_can_include_already_selected_items_when_requested():
    queue = build_entity_resolution_cluster_blocker_priority_queue(
        action_packet=_action_packet(),
        override_subset=_override_subset(),
        include_already_selected=True,
    )

    assert queue["summary"]["skipped_already_selected_count"] == 0
    assert queue["summary"]["queue_item_count"] == 3
    assert queue["summary"]["triage_bucket_counts"]["already_selected_shadow_override"] == 1
    assert queue["items"][-1]["review_item_id"] == "selected_1"


def test_cluster_blocker_priority_queue_sorts_by_review_bucket_before_reduction():
    queue = build_entity_resolution_cluster_blocker_priority_queue(action_packet=_action_packet())

    assert queue["items"][0]["triage_bucket"] == "time_format_review"
    assert queue["items"][1]["triage_bucket"] == "coordinate_conflict_review"
    assert queue["items"][0]["priority_index"] == 1


def test_cluster_blocker_priority_queue_rejects_unsafe_action_packet():
    packet = _action_packet()
    packet["decisions_created"] = True

    with pytest.raises(ValueError, match="decisions_created"):
        build_entity_resolution_cluster_blocker_priority_queue(action_packet=packet)


def test_cluster_blocker_priority_queue_rejects_unsafe_override_subset():
    override_subset = _override_subset()
    override_subset["preview_outputs_written"] = True

    with pytest.raises(ValueError, match="preview_outputs_written"):
        build_entity_resolution_cluster_blocker_priority_queue(
            action_packet=_action_packet(),
            override_subset=override_subset,
        )
