import pytest

from scripts.build_type_conflict_source_identity_review_decision_candidates import (
    build_type_conflict_source_identity_review_decision_candidates,
)


def _review_item(review_item_id, event_ids=None, input_ids=None):
    return {
        "review_item_id": review_item_id,
        "effect_id": f"effect_{review_item_id}",
        "review_recommendation": "source_review_identity_variant_same_event_candidate",
        "confidence": "medium",
        "failed_conditions": [],
        "merge_canonical_event_ids": event_ids or ["evt_a", "evt_b"],
        "candidate_canonical_input_ids": input_ids or ["cin_a", "cin_b"],
    }


def _reports():
    return (
        {
            "grouping_policy": "entity_resolution_type_conflict_source_identity_review_groups_report_only",
            "canonical_outputs_mutated": False,
            "preview_outputs_written": False,
            "decisions_created": False,
            "decision_outputs_created": False,
            "validated_decisions_created": False,
            "auto_merge_performed": False,
            "ready_for_canonical_apply": False,
            "groups": [
                {
                    "group_rank": 1,
                    "group_id": "group_1",
                    "group_recommendation": "source_identity_review_group_same_event_candidate",
                    "ready_for_decision_staging": True,
                    "group_blockers": [],
                    "member_count": 2,
                    "review_item_ids": ["review_a", "review_b"],
                    "effect_ids": ["effect_a", "effect_b"],
                    "source_names": ["ufocat"],
                    "source_native_ids": ["18509"],
                    "dates": ["1952-10-17"],
                    "times": ["1250"],
                    "locations": ["OLORON, Pyrenees-Atl, FRA, EU", "OLORON-STE-MARIE, Pyrenees-Atl, FRA, EU"],
                    "location_family_values": ["oloron", "oloron ste marie"],
                    "type_values": ["4ctg", "4tg"],
                    "type_family_prefixes": ["4"],
                    "active_conflicts": ["location", "type"],
                    "confidence_values": ["medium"],
                    "merge_canonical_event_ids": ["evt_a", "evt_b", "evt_c"],
                    "canonical_input_ids": ["cin_a", "cin_b", "cin_c"],
                }
            ],
        },
        {
            "review_policy": "entity_resolution_type_conflict_source_identity_review_only",
            "canonical_outputs_mutated": False,
            "preview_outputs_written": False,
            "decisions_created": False,
            "decision_outputs_created": False,
            "validated_decisions_created": False,
            "auto_merge_performed": False,
            "ready_for_canonical_apply": False,
            "items": [
                _review_item("review_a", event_ids=["evt_a", "evt_b"], input_ids=["cin_a", "cin_b"]),
                _review_item("review_b", event_ids=["evt_b", "evt_c"], input_ids=["cin_b", "cin_c"]),
            ],
        },
    )


def test_source_identity_group_decision_candidates_stage_ready_groups_without_mutation():
    groups_report, source_review = _reports()

    decisions, check = build_type_conflict_source_identity_review_decision_candidates(
        groups_report=groups_report,
        source_review=source_review,
        generated_at="2026-01-01T00:00:00+00:00",
    )

    assert check["valid"] is True
    assert check["canonical_outputs_mutated"] is False
    assert check["preview_outputs_written"] is False
    assert check["decision_candidate_count"] == 1
    assert check["projected_event_reduction"] == 2
    decision = decisions[0]
    assert decision["decision"] == "same_event"
    assert decision["review_type"] == "entity_resolution_type_conflict_source_identity_review_group_candidate"
    assert decision["requires_explicit_apply_step"] is True
    assert decision["merge_canonical_event_ids"] == ["evt_a", "evt_b", "evt_c"]
    assert decision["canonical_input_ids"] == ["cin_a", "cin_b", "cin_c"]


def test_source_identity_group_decision_candidates_rejects_unsafe_group_flags():
    groups_report, source_review = _reports()
    groups_report["validated_decisions_created"] = True

    with pytest.raises(ValueError, match="groups.validated_decisions_created must be false"):
        build_type_conflict_source_identity_review_decision_candidates(
            groups_report=groups_report,
            source_review=source_review,
        )


def test_source_identity_group_decision_candidates_blocks_unready_group():
    groups_report, source_review = _reports()
    groups_report["groups"][0]["ready_for_decision_staging"] = False
    groups_report["groups"][0]["group_blockers"] = ["requires_single_source"]

    decisions, check = build_type_conflict_source_identity_review_decision_candidates(
        groups_report=groups_report,
        source_review=source_review,
    )

    assert decisions == []
    assert check["valid"] is False
    assert check["invalid_groups"][0]["blockers"] == [
        "group_blockers_present",
        "group_not_ready_for_decision_staging",
    ]
