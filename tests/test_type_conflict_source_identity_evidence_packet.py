import json

import pytest

from scripts.build_entity_resolution_type_conflict_source_identity_evidence_packet import (
    build_type_conflict_source_identity_evidence_packet,
)


def _queue_item(review_item_id, lane="source_row_identity_review"):
    return {
        "review_rank": 1,
        "review_item_id": review_item_id,
        "effect_id": f"effect_{review_item_id}",
        "patch_id": f"patch_{review_item_id}",
        "next_lane": lane,
        "next_action": "Build source-row evidence packets before any decision staging.",
        "projected_event_reduction": 1,
        "type_conflict_classification": "type_only_single_family_subcode_conflict",
        "review_risk_tier": "high",
        "identity_consistency": "mixed_or_incomplete_identity",
        "blocking_fields": ["type_normalized"],
        "type_values": ["4ctg", "4tg"],
        "type_family_prefixes": ["4"],
        "shape_values": [],
        "risk_flags": ["location text differs"],
        "canonical_event_ids": ["evt_a", "evt_b"],
        "canonical_input_ids": ["cin_a", "cin_b"],
    }


def _safe_queue():
    return {
        "report_policy": "entity_resolution_type_conflict_next_queue_review_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "items": [
            _queue_item("review_1"),
            _queue_item("review_2", lane="cross_family_human_review_only"),
        ],
    }


def _write_deduped(path):
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "canonical_event_id": "evt_a",
                        "canonical_input_id": "cin_a",
                        "canonical_input_ids": ["cin_a"],
                        "source_name": "ufocat",
                        "source_native_id": "18509",
                        "date_iso": "1952-10-17",
                        "date_precision": "exact_day",
                        "location_raw": "OLORON, Pyrenees-Atl, FRA, EU",
                        "lat": 43.19,
                        "lon": -0.61,
                        "type_normalized": "4ctg",
                        "shape_normalized": "",
                        "summary": "row a",
                    }
                ),
                json.dumps(
                    {
                        "canonical_event_id": "evt_b",
                        "canonical_input_id": "cin_b",
                        "canonical_input_ids": ["cin_b"],
                        "source_name": "ufocat",
                        "source_native_id": "18509",
                        "date_iso": "1952-10-17",
                        "date_precision": "exact_day",
                        "location_raw": "OLORON-STE-MARIE, Pyrenees-Atl, FRA, EU",
                        "lat": 43.19,
                        "lon": -0.61,
                        "type_normalized": "4tg",
                        "shape_normalized": "",
                        "summary": "row b",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_type_conflict_source_identity_evidence_packet_filters_target_lane(tmp_path):
    deduped = tmp_path / "deduped_events.jsonl"
    _write_deduped(deduped)

    packet = build_type_conflict_source_identity_evidence_packet(
        queue=_safe_queue(),
        deduped_events_path=deduped,
    )

    assert packet["packet_policy"] == "entity_resolution_type_conflict_source_identity_evidence_review_only"
    assert packet["canonical_outputs_mutated"] is False
    assert packet["decisions_created"] is False
    assert packet["summary"]["candidate_effect_count"] == 1
    assert packet["summary"]["requested_canonical_event_id_count"] == 2
    assert packet["summary"]["matched_canonical_event_id_count"] == 2
    assert packet["summary"]["candidate_input_ids_missing_from_evidence_count"] == 0
    assert packet["items"][0]["review_item_id"] == "review_1"
    assert len(packet["items"][0]["evidence_rows"]) == 2


def test_type_conflict_source_identity_evidence_packet_rejects_unsafe_queue(tmp_path):
    queue = _safe_queue()
    queue["preview_outputs_written"] = True
    deduped = tmp_path / "deduped_events.jsonl"
    deduped.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="preview_outputs_written must be false"):
        build_type_conflict_source_identity_evidence_packet(queue=queue, deduped_events_path=deduped)
