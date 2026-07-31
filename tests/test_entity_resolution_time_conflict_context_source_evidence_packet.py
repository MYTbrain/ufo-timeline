import json

import pytest

from scripts.build_entity_resolution_time_conflict_context_source_evidence_packet import (
    PACKET_POLICY,
    build_time_conflict_context_source_evidence_packet,
)


def _analysis_item(review_item_id="er_cluster_a", *, classification="nearby_exact_conflict_15m_or_less_with_context"):
    return {
        "review_rank": 1,
        "time_conflict_classification": classification,
        "review_risk_tier": "high",
        "identity_consistency": "single_source_id_date_location",
        "recommended_review_step": "Check context tokens.",
        "review_item_id": review_item_id,
        "effect_id": f"ere_{review_item_id}",
        "projected_event_reduction": 1,
        "blocking_fields": ["time_raw"],
        "time_tokens": ["2000", "2010", "Even"],
        "parsed_minutes": [1200, 1210],
        "exact_span_minutes": 10,
        "fuzzy_labels": ["evening"],
        "approximate_tokens": [],
        "ambiguous_tokens": [],
        "unknown_tokens": [],
        "risk_flags": ["coordinates differ"],
        "has_coordinate_risk": True,
        "source_summary": {
            "canonical_event_ids": ["evt_a", "evt_b"],
            "canonical_input_ids": ["cin_a", "cin_b"],
            "source_names": ["ufocat"],
            "source_native_ids": ["native_1"],
            "date_values": ["1965-11-26"],
            "location_values": ["ST PAUL, Ramsey, MN, US"],
        },
    }


def _analysis(*items):
    return {
        "analysis_policy": "entity_resolution_cluster_time_conflict_review_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "auto_merge_performed": False,
        "override_decisions_created": False,
        "ready_for_canonical_apply": False,
        "items": list(items),
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
        "date_iso": "1965-11-26",
        "date_raw": "1965/11/26",
        "time_raw": time_raw,
        "location_raw": "ST PAUL, Ramsey, MN, US",
        "lat": 44.95,
        "lon": -93.09,
        "type_normalized": "5ew",
        "shape_normalized": "lights",
        "summary": "Same source text.",
        "description": "A description for review.",
        "raw_source_row": {"Time": time_raw, "Location": "ST PAUL"},
        "source_provenance": [{"canonical_input_id": input_id, "source_native_id": "native_1"}],
    }


def _write_events(path, rows):
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_time_conflict_context_source_evidence_packet_exports_target_classification(tmp_path):
    deduped_events = tmp_path / "deduped_events.jsonl"
    _write_events(
        deduped_events,
        [
            _event("evt_a", "cin_a", "2000"),
            _event("evt_b", "cin_b", "2010"),
            _event("evt_ignored", "cin_ignored", "2100"),
        ],
    )

    packet = build_time_conflict_context_source_evidence_packet(
        analysis=_analysis(
            _analysis_item(),
            _analysis_item("skip", classification="nearby_exact_conflict_60m_or_less"),
        ),
        deduped_events_path=deduped_events,
    )

    assert packet["packet_policy"] == PACKET_POLICY
    assert packet["canonical_outputs_mutated"] is False
    assert packet["decisions_created"] is False
    assert packet["summary"]["candidate_effect_count"] == 1
    assert packet["summary"]["requested_canonical_event_id_count"] == 2
    assert packet["summary"]["matched_canonical_event_id_count"] == 2
    item = packet["items"][0]
    assert item["review_item_id"] == "er_cluster_a"
    assert item["source_summary"]["time_values"] == ["2000", "2010"]
    assert item["conflict_summary"]["conflict_flags"]["time"] is True
    assert item["shadow_preview_override_source"]["time_conflict_classification"] == "nearby_exact_conflict_15m_or_less_with_context"


def test_time_conflict_context_source_evidence_packet_rejects_unsafe_analysis(tmp_path):
    deduped_events = tmp_path / "deduped_events.jsonl"
    _write_events(deduped_events, [])
    analysis = _analysis(_analysis_item())
    analysis["preview_outputs_written"] = True

    with pytest.raises(ValueError, match="preview_outputs_written"):
        build_time_conflict_context_source_evidence_packet(
            analysis=analysis,
            deduped_events_path=deduped_events,
        )
