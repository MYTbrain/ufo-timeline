import json

import pytest

from scripts.build_entity_resolution_type_subcode_source_evidence_packet import (
    build_type_subcode_source_evidence_packet,
)


def test_type_subcode_source_evidence_packet_is_review_only_and_matches_rows(tmp_path):
    subset = {
        "subset_policy": "entity_resolution_type_subcode_low_risk_review_subset_report_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "auto_merge_performed": False,
        "override_decisions_created": False,
        "ready_for_canonical_apply": False,
        "selected_items": [
            {
                "review_item_id": "review_1",
                "effect_id": "effect_1",
                "patch_id": "patch_1",
                "type_conflict_classification": "type_only_single_family_subcode_conflict",
                "review_risk_tier": "lower",
                "identity_consistency": "single_source_id_date_location",
                "type_values": ["4", "4d"],
                "type_family_prefixes": ["4"],
                "blocking_fields": ["type_normalized"],
                "source_summary": {
                    "canonical_event_ids": ["evt_a", "evt_b"],
                    "canonical_input_ids": ["cin_a", "cin_b"],
                },
            }
        ],
    }
    deduped = tmp_path / "deduped_events.jsonl"
    deduped.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "canonical_event_id": "evt_a",
                        "canonical_input_id": "cin_a",
                        "canonical_input_ids": ["cin_a"],
                        "source_name": "ufocat",
                        "source_native_id": "123",
                        "date_iso": "1952-09-30",
                        "date_precision": "exact_day",
                        "location_raw": "EDWARDS AFB, Kern, CA, US",
                        "lat": 35.0,
                        "lon": -117.0,
                        "type_normalized": "4",
                        "shape_normalized": "",
                        "raw_source_row": {"TYPE": "4"},
                    }
                ),
                json.dumps(
                    {
                        "canonical_event_id": "evt_b",
                        "canonical_input_id": "cin_b",
                        "canonical_input_ids": ["cin_b"],
                        "source_name": "ufocat",
                        "source_native_id": "123",
                        "date_iso": "1952-09-30",
                        "date_precision": "exact_day",
                        "location_raw": "EDWARDS AFB, Kern, CA, US",
                        "lat": 35.0,
                        "lon": -117.0,
                        "type_normalized": "4d",
                        "shape_normalized": "",
                        "raw_source_row": {"TYPE": "4D"},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    packet = build_type_subcode_source_evidence_packet(subset=subset, deduped_events_path=deduped)

    assert packet["packet_policy"] == "entity_resolution_type_subcode_source_row_evidence_review_only"
    assert packet["canonical_outputs_mutated"] is False
    assert packet["preview_outputs_written"] is False
    assert packet["decisions_created"] is False
    assert packet["summary"]["candidate_effect_count"] == 1
    assert packet["summary"]["matched_canonical_event_id_count"] == 2
    assert packet["summary"]["missing_canonical_event_id_count"] == 0
    assert packet["summary"]["candidate_input_ids_missing_from_evidence_count"] == 0
    assert packet["items"][0]["source_summary"]["type_values"] == ["4", "4d"]
    assert len(packet["items"][0]["evidence_rows"]) == 2


def test_type_subcode_source_evidence_packet_rejects_unsafe_subset(tmp_path):
    subset = {
        "subset_policy": "entity_resolution_type_subcode_low_risk_review_subset_report_only",
        "canonical_outputs_mutated": True,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "auto_merge_performed": False,
        "override_decisions_created": False,
        "ready_for_canonical_apply": False,
        "selected_items": [],
    }
    deduped = tmp_path / "deduped_events.jsonl"
    deduped.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="unsafe"):
        build_type_subcode_source_evidence_packet(subset=subset, deduped_events_path=deduped)
