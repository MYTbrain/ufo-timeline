import pytest

from scripts.review_type_subcode_source_candidates import build_type_subcode_source_review


def _packet_item(**overrides):
    item = {
        "review_rank": 1,
        "review_item_id": "review_1",
        "effect_id": "effect_1",
        "projected_event_reduction": 1,
        "type_conflict_classification": "type_only_single_family_subcode_conflict",
        "review_risk_tier": "lower",
        "identity_consistency": "single_source_id_date_location",
        "type_values": ["4", "4d"],
        "type_family_prefixes": ["4"],
        "candidate_input_ids_missing_from_evidence": [],
        "missing_canonical_event_ids": [],
        "source_summary": {
            "source_names": ["ufocat"],
            "source_native_ids": ["123"],
            "date_values": ["1952-09-30"],
            "location_values": ["EDWARDS AFB, Kern, CA, US"],
            "coordinate_values": ["34.89,-117.88"],
            "type_values": ["4", "4d"],
        },
        "conflict_summary": {"conflict_flags": {"type": True}},
        "merge_canonical_event_ids": ["evt_a", "evt_b"],
        "candidate_canonical_input_ids": ["cin_a", "cin_b"],
    }
    item.update(overrides)
    return item


def _packet(**overrides):
    packet = {
        "packet_policy": "entity_resolution_type_subcode_source_row_evidence_review_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "auto_merge_performed": False,
        "override_decisions_created": False,
        "ready_for_canonical_apply": False,
        "items": [_packet_item()],
    }
    packet.update(overrides)
    return packet


def test_type_subcode_source_review_recommends_consistent_type_only_candidate():
    review = build_type_subcode_source_review(_packet())

    assert review["review_policy"] == "entity_resolution_type_subcode_source_review_only"
    assert review["canonical_outputs_mutated"] is False
    assert review["decisions_created"] is False
    assert review["summary"]["review_recommendation_counts"] == {
        "source_review_type_subcode_same_event_candidate": 1
    }
    assert review["items"][0]["failed_conditions"] == []


def test_type_subcode_source_review_defers_non_type_conflict():
    packet = _packet(
        items=[
            _packet_item(
                conflict_summary={"conflict_flags": {"type": True, "coordinate": True}},
            )
        ]
    )

    review = build_type_subcode_source_review(packet)

    assert review["summary"]["review_recommendation_counts"] == {"needs_more_evidence": 1}
    assert "type_only_conflict" in review["items"][0]["failed_conditions"]


def test_type_subcode_source_review_rejects_unsafe_packet():
    packet = _packet(canonical_outputs_mutated=True)

    with pytest.raises(ValueError, match="unsafe"):
        build_type_subcode_source_review(packet)
