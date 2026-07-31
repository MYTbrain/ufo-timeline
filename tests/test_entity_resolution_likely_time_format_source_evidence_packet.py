import json

import pytest

from scripts.build_entity_resolution_likely_time_format_source_evidence_packet import (
    PACKET_POLICY,
    build_likely_time_format_source_evidence_packet,
)


def _event(event_id, input_id, *, time_raw):
    return {
        "canonical_event_id": event_id,
        "canonical_input_id": input_id,
        "canonical_input_ids": [input_id],
        "source_name": "ufocat",
        "source_file": "ufocat2023.csv",
        "source_row_number": 1,
        "source_native_id": "native_1",
        "source_row_hash": f"hash_{input_id}",
        "date_iso": "1909-05-18",
        "date_precision": "exact_day",
        "time_raw": time_raw,
        "location_raw": "CAERPHILLY, So Glamorgan, GBR, EU",
        "lat": 51.58,
        "lon": -3.22,
        "coordinate_source": "source_coordinates",
        "type_normalized": "7ltj",
        "summary": "Same source text.",
        "source_provenance": [
            {
                "source_name": "ufocat",
                "source_file": "ufocat2023.csv",
                "source_row_number": 1,
                "source_native_id": "native_1",
                "source_row_hash": f"hash_{input_id}",
                "canonical_input_id": input_id,
            }
        ],
    }


def _action_packet(*items):
    return {
        "packet_policy": "entity_resolution_blocked_merge_action_review_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "items": list(items),
    }


def _action_item(review_item_id="er_cluster_a", *, classification="likely_time_format_variant"):
    return {
        "review_item_id": review_item_id,
        "effect_id": f"ere_{review_item_id}",
        "classification": classification,
        "suggested_action": "candidate_shadow_preview_override",
        "analysis_confidence": "high",
        "projected_event_reduction": 1,
        "blocking_fields": ["time_raw"],
        "field_conflict_values": {"time_raw": ["23", "2300"]},
        "reasons": ["time_raw values parse to the same minute"],
        "risks": [],
        "source_summary": {
            "canonical_event_ids": ["evt_a", "evt_b"],
            "canonical_input_ids": ["cin_a", "cin_b"],
        },
    }


def _write_jsonl(path, rows):
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def test_likely_time_format_source_evidence_packet_exports_target_items(tmp_path):
    deduped = tmp_path / "deduped_events.jsonl"
    _write_jsonl(deduped, [_event("evt_a", "cin_a", time_raw="23"), _event("evt_b", "cin_b", time_raw="2300")])

    packet = build_likely_time_format_source_evidence_packet(
        action_packet=_action_packet(_action_item(), _action_item("skip", classification="time_conflict_requires_review")),
        deduped_events_path=deduped,
    )

    assert packet["packet_policy"] == PACKET_POLICY
    assert packet["canonical_outputs_mutated"] is False
    assert packet["decisions_created"] is False
    assert packet["summary"]["candidate_effect_count"] == 1
    assert packet["summary"]["matched_canonical_event_id_count"] == 2
    assert packet["summary"]["projected_event_reduction"] == 1
    item = packet["items"][0]
    assert item["review_item_id"] == "er_cluster_a"
    assert item["source_summary"]["time_values"] == ["23", "2300"]
    assert item["conflict_summary"]["conflict_flags"]["time"] is True


def test_likely_time_format_source_evidence_packet_rejects_unsafe_action_packet(tmp_path):
    deduped = tmp_path / "deduped_events.jsonl"
    _write_jsonl(deduped, [])
    packet = _action_packet(_action_item())
    packet["preview_outputs_written"] = True

    with pytest.raises(ValueError, match="preview_outputs_written"):
        build_likely_time_format_source_evidence_packet(
            action_packet=packet,
            deduped_events_path=deduped,
        )
