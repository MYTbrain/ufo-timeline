import pytest

from scripts.review_type_conflict_subcode_policy_candidates import (
    review_type_conflict_subcode_policy_candidates,
)


def _packet(summary_b="silver object landed on sandbar and took off"):
    return {
        "packet_policy": "entity_resolution_type_conflict_subcode_policy_evidence_review_only",
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
                "identity_consistency": "single_source_id_date_location",
                "type_values": ["7nt", "7t"],
                "type_family_prefixes": ["7"],
                "candidate_canonical_input_ids": ["cin_a", "cin_b"],
                "merge_canonical_event_ids": ["evt_a", "evt_b"],
                "missing_canonical_event_ids": [],
                "candidate_input_ids_missing_from_evidence": [],
                "source_summary": {
                    "source_names": ["ufocat"],
                    "source_native_ids": ["60842"],
                    "date_values": ["1953-05-20"],
                    "date_precision_values": ["exact_day"],
                    "time_values": ["1830"],
                    "location_values": ["BRUSH CREEK, Butte, CA, US"],
                    "coordinate_values": ["39.7,-121.4", "39.8,-121.5"],
                },
                "conflict_summary": {
                    "conflict_flags": {
                        "coordinate": True,
                        "type": True,
                        "time": False,
                        "shape": False,
                        "source_native_id": False,
                    }
                },
                "evidence_rows": [
                    {
                        "lat": 39.7,
                        "lon": -121.4,
                        "summary": "silver object landed on sandbar and took off",
                    },
                    {
                        "lat": 39.8,
                        "lon": -121.5,
                        "summary": summary_b,
                    },
                ],
            }
        ],
    }


def test_subcode_policy_review_recommends_strict_identity_despite_coordinate_variance():
    report = review_type_conflict_subcode_policy_candidates(packet=_packet())

    assert report["canonical_outputs_mutated"] is False
    assert report["decisions_created"] is False
    assert report["summary"]["review_recommendation_counts"] == {
        "source_review_subcode_policy_same_event_candidate": 1
    }
    item = report["items"][0]
    assert item["failed_conditions"] == []
    assert item["review_reason_codes"] == [
        "same_source_native_date_location",
        "compatible_summary_text",
        "type_subcode_variant",
        "coordinate_variance_recorded",
        "review_only_not_decision",
    ]


def test_subcode_policy_review_blocks_incompatible_summary_text():
    report = review_type_conflict_subcode_policy_candidates(packet=_packet(summary_b="unrelated airport light"))

    assert report["summary"]["review_recommendation_counts"] == {"needs_more_evidence": 1}
    assert "summary_text_compatible" in report["items"][0]["failed_conditions"]


def test_subcode_policy_review_rejects_unsafe_packet():
    packet = _packet()
    packet["canonical_outputs_mutated"] = True

    with pytest.raises(ValueError, match="canonical_outputs_mutated must be false"):
        review_type_conflict_subcode_policy_candidates(packet=packet)
