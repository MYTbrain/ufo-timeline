import pytest

from scripts.review_type_conflict_source_identity_candidates import (
    review_type_conflict_source_identity_candidates,
)


def _packet(summary_b="same bright disc over town"):
    return {
        "packet_policy": "entity_resolution_type_conflict_source_identity_evidence_review_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "items": [
            {
                "review_item_id": "review_1",
                "effect_id": "effect_1",
                "projected_event_reduction": 1,
                "type_conflict_classification": "type_only_single_family_subcode_conflict",
                "review_risk_tier": "high",
                "identity_consistency": "mixed_or_incomplete_identity",
                "type_values": ["4ctg", "4tg"],
                "type_family_prefixes": ["4"],
                "candidate_canonical_input_ids": ["cin_a", "cin_b"],
                "merge_canonical_event_ids": ["evt_a", "evt_b"],
                "missing_canonical_event_ids": [],
                "candidate_input_ids_missing_from_evidence": [],
                "source_summary": {
                    "source_names": ["ufocat"],
                    "source_native_ids": ["18509"],
                    "date_values": ["1952-10-17"],
                    "date_precision_values": ["exact_day"],
                    "time_values": ["1250"],
                    "shape_values": ["disc"],
                    "coordinate_values": ["43.187,0.609"],
                    "location_values": [
                        "OLORON, Pyrenees-Atl, FRA, EU",
                        "OLORON-STE-MARIE, Pyrenees-Atl, FRA, EU",
                    ],
                },
                "conflict_summary": {
                    "conflict_flags": {
                        "time": False,
                        "date": False,
                        "location": True,
                        "coordinate": False,
                        "type": True,
                        "shape": False,
                        "source_native_id": False,
                    }
                },
                "evidence_rows": [
                    {
                        "lat": 43.187,
                        "lon": 0.609,
                        "summary": "same bright disc over town",
                    },
                    {
                        "lat": 43.187,
                        "lon": 0.609,
                        "summary": summary_b,
                    },
                ],
            }
        ],
    }


def test_type_conflict_source_identity_review_recommends_strict_identity_variant():
    report = review_type_conflict_source_identity_candidates(packet=_packet())

    assert report["canonical_outputs_mutated"] is False
    assert report["decisions_created"] is False
    assert report["summary"]["review_recommendation_counts"] == {
        "source_review_identity_variant_same_event_candidate": 1
    }
    item = report["items"][0]
    assert item["confidence"] == "medium"
    assert item["failed_conditions"] == []
    assert item["review_reason_codes"] == [
        "same_source_native_date",
        "compatible_summary_text",
        "review_only_not_decision",
        "location_variant",
        "type_subcode_variant",
    ]


def test_type_conflict_source_identity_review_blocks_incompatible_summary_text():
    report = review_type_conflict_source_identity_candidates(packet=_packet(summary_b="different witness at airport"))

    assert report["summary"]["review_recommendation_counts"] == {"needs_more_evidence": 1}
    assert "summary_text_compatible" in report["items"][0]["failed_conditions"]


def test_type_conflict_source_identity_review_rejects_unsafe_packet():
    packet = _packet()
    packet["canonical_outputs_mutated"] = True

    with pytest.raises(ValueError, match="canonical_outputs_mutated must be false"):
        review_type_conflict_source_identity_candidates(packet=packet)
