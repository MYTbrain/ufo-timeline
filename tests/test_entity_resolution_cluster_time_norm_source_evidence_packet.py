import json

import pytest

from scripts.build_entity_resolution_cluster_time_norm_source_evidence_packet import (
    build_entity_resolution_cluster_time_norm_source_evidence_packet,
)


def _effect(review_item_id="review_1"):
    return {
        "effect_id": f"effect_{review_item_id}",
        "review_item_id": review_item_id,
        "decision_index": 10,
        "planned_effect": "merge_entity_resolution_candidate",
        "shadow_preview_override_reason": "strict_time_normalization_candidate",
        "canonical_input_ids": ["cin_a", "cin_b"],
        "merge_canonical_event_ids": ["evt_a", "evt_b"],
        "shadow_preview_override_source": {
            "time_pattern_classification": "nearby_exact_minutes_15m_or_less",
            "review_risk_tier": "lower",
            "parsed_minutes": [600, 605],
            "time_tokens": ["1000", "1005"],
        },
    }


def _subset():
    return {
        "subset_policy": "entity_resolution_cluster_time_normalization_shadow_preview_subset_v2",
        "canonical_outputs_mutated": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "auto_merge_performed": False,
        "override_decisions_created": False,
        "ready_for_canonical_apply": False,
        "effects": [
            _effect(),
            {
                **_effect("base_override"),
                "shadow_preview_override_reason": "likely_time_format_variant",
                "merge_canonical_event_ids": ["evt_ignored"],
            },
        ],
    }


def _event(event_id, input_id, time_raw):
    return {
        "canonical_event_id": event_id,
        "canonical_input_id": input_id,
        "canonical_input_ids": [input_id],
        "source_name": "ufocat",
        "source_file": "ufocat2023.csv",
        "source_row_number": 123,
        "source_native_id": "native_1",
        "source_row_hash": f"hash_{event_id}",
        "date_iso": "1954-09-19",
        "date_raw": "1954/09/19",
        "time_raw": time_raw,
        "location_raw": "RONGERES, FRA",
        "lat": 46.3,
        "lon": 3.45,
        "type_normalized": "3l",
        "shape_normalized": "disc",
        "summary": "Test event",
        "description": "A long enough description for review.",
        "raw_source_row": {"Time": time_raw, "Location": "RONGERES"},
        "source_provenance": [{"canonical_input_id": input_id, "source_native_id": "native_1"}],
    }


def _write_events(path, rows):
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_time_norm_source_evidence_packet_extracts_only_strict_candidates(tmp_path):
    deduped_events = tmp_path / "deduped_events.jsonl"
    _write_events(
        deduped_events,
        [
            _event("evt_a", "cin_a", "1000"),
            _event("evt_b", "cin_b", "1005"),
            _event("evt_ignored", "cin_ignored", "1005"),
        ],
    )

    packet = build_entity_resolution_cluster_time_norm_source_evidence_packet(
        subset=_subset(),
        deduped_events_path=deduped_events,
    )

    assert packet["packet_policy"] == "entity_resolution_cluster_time_normalization_source_row_evidence_review_only"
    assert packet["canonical_outputs_mutated"] is False
    assert packet["summary"]["candidate_effect_count"] == 1
    assert packet["summary"]["requested_canonical_event_id_count"] == 2
    assert packet["summary"]["matched_canonical_event_id_count"] == 2
    assert packet["summary"]["missing_canonical_event_id_count"] == 0
    assert packet["summary"]["candidate_input_ids_missing_from_evidence_count"] == 0
    assert packet["summary"]["projected_event_reduction"] == 1
    item = packet["items"][0]
    assert item["review_item_id"] == "review_1"
    assert item["time_values"] == ["1000", "1005"]
    assert item["candidate_input_ids_missing_from_evidence"] == []
    assert item["conflict_summary"]["conflict_flags"]["time"] is True
    assert item["conflict_summary"]["blocking_status"] == "review_required_not_auto_approved"
    assert item["reviewer_prompts"]
    assert [row["canonical_event_id"] for row in item["evidence_rows"]] == ["evt_a", "evt_b"]
    assert item["evidence_rows"][0]["raw_source_row"] == {"Time": "1000", "Location": "RONGERES"}
    assert item["evidence_rows"][0]["raw_fields"] == {"Location": "RONGERES", "Time": "1000"}


def test_time_norm_source_evidence_packet_rejects_unsafe_subset(tmp_path):
    subset = _subset()
    subset["ready_for_canonical_apply"] = True
    deduped_events = tmp_path / "deduped_events.jsonl"
    _write_events(deduped_events, [_event("evt_a", "cin_a", "1000")])

    with pytest.raises(ValueError, match="ready_for_canonical_apply"):
        build_entity_resolution_cluster_time_norm_source_evidence_packet(
            subset=subset,
            deduped_events_path=deduped_events,
        )
