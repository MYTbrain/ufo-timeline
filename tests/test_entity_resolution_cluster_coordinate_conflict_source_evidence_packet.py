import json

import pytest

from scripts.build_entity_resolution_cluster_coordinate_conflict_source_evidence_packet import (
    PACKET_POLICY,
    build_coordinate_conflict_source_evidence_packet,
)


def _analysis_item(review_item_id="coord_a", *, classification="coordinate_conflict_10_to_15km"):
    return {
        "review_rank": 1,
        "coordinate_conflict_classification": classification,
        "review_risk_tier": "high",
        "identity_consistency": "single_source_id_date_location",
        "recommended_review_step": "Review map/source rows for nearby geocode precision.",
        "review_item_id": review_item_id,
        "effect_id": f"ere_{review_item_id}",
        "projected_event_reduction": 1,
        "blocking_fields": ["coordinate_distance_over_10km"],
        "max_coordinate_distance_km": 12.5,
        "time_values": ["2100"],
        "type_values": ["disk"],
        "source_summary": {
            "canonical_event_count": 2,
            "canonical_event_ids": ["evt_a", "evt_b"],
            "canonical_input_ids": ["cin_a", "cin_b"],
            "source_names": ["ufocat"],
            "source_native_ids": ["native_1"],
            "date_values": ["1954-10-03"],
            "location_values": ["JUNGFRAU, Bern, SUI, EU"],
            "type_values": ["disk"],
        },
    }


def _analysis(*items):
    return {
        "analysis_policy": "entity_resolution_cluster_coordinate_conflict_review_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "auto_merge_performed": False,
        "override_decisions_created": False,
        "ready_for_canonical_apply": False,
        "items": list(items),
    }


def _event(event_id, input_id, lat, lon):
    return {
        "canonical_event_id": event_id,
        "canonical_input_id": input_id,
        "canonical_input_ids": [input_id],
        "source_name": "ufocat",
        "source_file": "ufocat2023.csv",
        "source_row_number": 123,
        "source_native_id": "native_1",
        "source_row_hash": f"hash_{event_id}",
        "date_iso": "1954-10-03",
        "date_raw": "1954/10/03",
        "time_raw": "2100",
        "location_raw": "JUNGFRAU, Bern, SUI, EU",
        "lat": lat,
        "lon": lon,
        "coordinate_source": "raw_latlong",
        "coordinate_precision": "exact_coords",
        "type_normalized": "disk",
        "shape_normalized": "disk",
        "summary": "Nearby coordinate conflict fixture.",
        "description": "A description for coordinate review.",
        "raw_source_row": {"Location": "JUNGFRAU", "Lat": str(lat), "Lon": str(lon)},
        "source_provenance": [{"canonical_input_id": input_id, "source_native_id": "native_1"}],
    }


def _write_events(path, rows):
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_coordinate_conflict_source_evidence_packet_exports_target_classification(tmp_path):
    deduped_events = tmp_path / "deduped_events.jsonl"
    _write_events(
        deduped_events,
        [
            _event("evt_a", "cin_a", 46.55, 7.98),
            _event("evt_b", "cin_b", 46.62, 8.08),
            _event("evt_ignored", "cin_ignored", 0, 0),
        ],
    )

    packet = build_coordinate_conflict_source_evidence_packet(
        analysis=_analysis(
            _analysis_item(),
            _analysis_item("skip", classification="coordinate_conflict_50_to_150km"),
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
    assert item["review_item_id"] == "coord_a"
    assert item["coordinate_conflict_summary"]["max_coordinate_distance_km"] == 12.5
    assert item["shadow_preview_override_source"]["coordinate_conflict_classification"] == "coordinate_conflict_10_to_15km"
    assert item["conflict_summary"]["conflict_flags"]["coordinate"] is True
    assert item["source_summary"]["coordinate_values"] == ["46.55,7.98", "46.62,8.08"]
    assert "coordinate precision" in item["reviewer_prompts"][0]


def test_coordinate_conflict_source_evidence_packet_rejects_unsafe_analysis(tmp_path):
    deduped_events = tmp_path / "deduped_events.jsonl"
    _write_events(deduped_events, [])
    analysis = _analysis(_analysis_item())
    analysis["preview_outputs_written"] = True

    with pytest.raises(ValueError, match="preview_outputs_written"):
        build_coordinate_conflict_source_evidence_packet(
            analysis=analysis,
            deduped_events_path=deduped_events,
        )
