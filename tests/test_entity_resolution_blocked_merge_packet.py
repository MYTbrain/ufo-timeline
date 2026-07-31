import pytest

from scripts.build_entity_resolution_blocked_merge_packet import build_entity_resolution_blocked_merge_packet


def _readiness():
    return {
        "readiness_policy": "entity_resolution_merge_preview_readiness_gate",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "blocking_items_sample": [
            {
                "review_item_id": "review_1",
                "patch_id": "patch_1",
                "effect_id": "effect_1",
                "fields": ["type_normalized"],
                "projected_event_reduction": 1,
            }
        ],
    }


def _merged_preview():
    return {
        "preview_policy": "entity_resolution_compact_merged_event_preview_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "previews": [
            {
                "review_item_id": "review_1",
                "field_conflicts": {"type_normalized": ["disc", "sphere"]},
                "source_event_summaries": [
                    {"canonical_event_id": "evt_a", "type_normalized": "disc"},
                    {"canonical_event_id": "evt_b", "type_normalized": "sphere"},
                ],
            }
        ],
    }


def test_build_entity_resolution_blocked_merge_packet_joins_preview_details():
    packet = build_entity_resolution_blocked_merge_packet(
        readiness_report=_readiness(),
        merged_event_preview=_merged_preview(),
    )

    assert packet["canonical_outputs_mutated"] is False
    assert packet["blocked_item_count"] == 1
    assert packet["blocking_field_counts"] == {"type_normalized": 1}
    assert packet["items"][0]["field_conflicts"] == {"type_normalized": ["disc", "sphere"]}
    assert packet["items"][0]["suggested_action"] == "review_type_conflict_before_merge"


def test_build_entity_resolution_blocked_merge_packet_prefers_full_blocking_items():
    readiness = _readiness()
    readiness["blocking_items"] = [
        {
            "review_item_id": "review_1",
            "patch_id": "patch_1",
            "effect_id": "effect_1",
            "fields": ["type_normalized"],
            "projected_event_reduction": 1,
        },
        {
            "review_item_id": "review_2",
            "patch_id": "patch_2",
            "effect_id": "effect_2",
            "fields": ["coordinate_distance_over_10km"],
            "projected_event_reduction": 1,
        },
    ]

    packet = build_entity_resolution_blocked_merge_packet(
        readiness_report=readiness,
        merged_event_preview=_merged_preview(),
    )

    assert packet["blocked_item_count"] == 2
    assert packet["items"][1]["review_item_id"] == "review_2"


def test_build_entity_resolution_blocked_merge_packet_rejects_unsafe_inputs():
    unsafe_readiness = _readiness()
    unsafe_readiness["auto_merge_performed"] = True

    with pytest.raises(ValueError, match="blocked merge packet inputs are not safe"):
        build_entity_resolution_blocked_merge_packet(
            readiness_report=unsafe_readiness,
            merged_event_preview=_merged_preview(),
        )
