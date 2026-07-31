import pytest

from scripts.build_type_subcode_source_review_decision_candidates import (
    build_type_subcode_source_review_decision_candidates,
)


def _review_item(review_item_id, event_ids=None, input_ids=None):
    return {
        "review_item_id": review_item_id,
        "review_recommendation": "source_review_type_subcode_same_event_candidate",
        "confidence": "medium",
        "projected_event_reduction": 1,
        "type_conflict_classification": "type_only_single_family_subcode_conflict",
        "review_risk_tier": "lower",
        "identity_consistency": "single_source_id_date_location",
        "type_values": ["5smd", "5smzzx"],
        "type_family_prefixes": ["5"],
        "active_conflicts": ["type"],
        "failed_conditions": [],
        "source_names": ["ufocat"],
        "source_native_ids": ["32884"],
        "dates": ["1960-03-04"],
        "locations": ["DUBUQUE, Dubuque, IA, US"],
        "merge_canonical_event_ids": event_ids or ["evt_a", "evt_b"],
        "candidate_canonical_input_ids": input_ids or ["cin_a", "cin_b"],
    }


def _reports():
    return (
        {
            "grouping_policy": "entity_resolution_type_subcode_source_review_groups_report_only",
            "canonical_outputs_mutated": False,
            "preview_outputs_written": False,
            "decisions_created": False,
            "decision_outputs_created": False,
            "auto_merge_performed": False,
            "groups": [
                {
                    "group_rank": 1,
                    "member_count": 2,
                    "review_item_ids": ["review_a", "review_b"],
                    "effect_ids": ["effect_a", "effect_b"],
                    "source_names": ["ufocat"],
                    "source_native_ids": ["32884"],
                    "date_values": ["1960-03-04"],
                    "location_values": ["DUBUQUE, Dubuque, IA, US"],
                    "type_values_union": ["5smd", "5smzzx"],
                    "review_recommendations": ["source_review_type_subcode_same_event_candidate"],
                    "confidence_values": ["medium"],
                    "failed_conditions": [],
                    "group_recommendation": "source_review_group_same_event_candidate",
                }
            ],
        },
        {
            "review_policy": "entity_resolution_type_subcode_source_review_only",
            "canonical_outputs_mutated": False,
            "preview_outputs_written": False,
            "decisions_created": False,
            "decision_outputs_created": False,
            "auto_merge_performed": False,
            "ready_for_canonical_apply": False,
            "items": [
                _review_item("review_a", event_ids=["evt_a", "evt_b"], input_ids=["cin_a", "cin_b"]),
                _review_item("review_b", event_ids=["evt_b", "evt_c"], input_ids=["cin_b", "cin_c"]),
            ],
        },
    )


def test_type_subcode_source_review_decision_candidates_group_overlapping_effects_without_mutation():
    groups_report, source_review = _reports()

    decisions, check = build_type_subcode_source_review_decision_candidates(
        groups_report=groups_report,
        source_review=source_review,
        generated_at="2026-01-01T00:00:00+00:00",
    )

    assert check["valid"] is True
    assert check["canonical_outputs_mutated"] is False
    assert check["preview_outputs_written"] is False
    assert check["auto_merge_performed"] is False
    assert check["decision_candidate_count"] == 1
    assert check["projected_event_reduction"] == 2
    decision = decisions[0]
    assert decision["decision"] == "same_event"
    assert decision["review_type"] == "entity_resolution_type_subcode_source_review_group_candidate"
    assert decision["requires_explicit_apply_step"] is True
    assert decision["merge_canonical_event_ids"] == ["evt_a", "evt_b", "evt_c"]
    assert decision["canonical_input_ids"] == ["cin_a", "cin_b", "cin_c"]


def test_type_subcode_source_review_decision_candidates_rejects_unsafe_source_review_flags():
    groups_report, source_review = _reports()
    source_review["canonical_outputs_mutated"] = True

    with pytest.raises(ValueError, match="source_review.canonical_outputs_mutated must be false"):
        build_type_subcode_source_review_decision_candidates(
            groups_report=groups_report,
            source_review=source_review,
        )


def test_type_subcode_source_review_decision_candidates_blocks_non_single_source_groups():
    groups_report, source_review = _reports()
    groups_report["groups"][0]["source_names"] = ["ufocat", "nuforc"]

    decisions, check = build_type_subcode_source_review_decision_candidates(
        groups_report=groups_report,
        source_review=source_review,
    )

    assert decisions == []
    assert check["valid"] is False
    assert check["invalid_groups"][0]["blockers"] == ["group_requires_single_source"]
