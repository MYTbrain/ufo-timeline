import pytest

from scripts.build_entity_resolution_blocked_merge_action_packet import (
    build_entity_resolution_blocked_merge_action_packet,
)


def _blocked_packet():
    return {
        "packet_policy": "entity_resolution_blocked_merge_review_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "items": [
            {
                "review_item_id": "review_1",
                "blocking_fields": ["time_raw"],
                "projected_event_reduction": 3,
                "field_conflicts": {"time_raw": ["1630", "16:30"]},
                "source_event_summaries": [
                    {
                        "canonical_event_id": "evt_1",
                        "canonical_input_ids": ["cin_1"],
                        "source_name": "ufocat",
                        "source_native_id": "171782",
                        "date_iso": "1954-09-19",
                        "time_raw": "1630",
                        "location_raw": "RONGERES, FRA",
                    },
                    {
                        "canonical_event_id": "evt_2",
                        "canonical_input_ids": ["cin_2"],
                        "source_name": "ufocat",
                        "source_native_id": "171782",
                        "date_iso": "1954-09-19",
                        "time_raw": "16:30",
                        "location_raw": "RONGERES, FRA",
                    },
                ],
            }
        ],
    }


def _blocked_analysis():
    return {
        "analysis_policy": "entity_resolution_blocked_merge_analysis_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "items": [
            {
                "review_item_id": "review_1",
                "classification": "time_format_or_multiple_time_variant",
                "suggested_action": "time_review_before_override",
                "analysis_confidence": "medium",
                "projected_event_reduction": 3,
                "blocking_fields": ["time_raw"],
                "reasons": ["time_raw needs review"],
                "risks": [],
            }
        ],
    }


def test_blocked_merge_action_packet_joins_analysis_and_detail_rows():
    packet = build_entity_resolution_blocked_merge_action_packet(
        blocked_packet=_blocked_packet(),
        blocked_analysis=_blocked_analysis(),
    )

    assert packet["packet_policy"] == "entity_resolution_blocked_merge_action_review_only"
    assert packet["canonical_outputs_mutated"] is False
    assert packet["export_summary"]["exported_item_count"] == 1
    assert packet["export_summary"]["classification_counts"] == {"time_format_or_multiple_time_variant": 1}
    item = packet["items"][0]
    assert item["classification"] == "time_format_or_multiple_time_variant"
    assert item["field_conflict_values"]["time_raw"] == ["1630", "16:30"]
    assert item["source_summary"]["canonical_event_ids"] == ["evt_1", "evt_2"]
    assert item["source_summary"]["canonical_input_ids"] == ["cin_1", "cin_2"]
    assert item["source_summary"]["source_native_ids"] == ["171782"]


def test_blocked_merge_action_packet_filters_classifications():
    packet = build_entity_resolution_blocked_merge_action_packet(
        blocked_packet=_blocked_packet(),
        blocked_analysis=_blocked_analysis(),
        include_classifications={"type_conflict_requires_review"},
    )

    assert packet["export_summary"]["exported_item_count"] == 0
    assert packet["items"] == []


def test_blocked_merge_action_packet_rejects_unsafe_inputs():
    blocked_packet = _blocked_packet()
    blocked_packet["canonical_outputs_mutated"] = True

    with pytest.raises(ValueError, match="canonical_outputs_mutated"):
        build_entity_resolution_blocked_merge_action_packet(
            blocked_packet=blocked_packet,
            blocked_analysis=_blocked_analysis(),
        )
