import pytest

from scripts.group_type_conflict_source_identity_review_candidates import (
    group_type_conflict_source_identity_review_candidates,
)


SAFE_RECOMMENDATION = "source_review_identity_variant_same_event_candidate"


def _review_item(review_item_id, event_ids, input_ids=None, recommendation=SAFE_RECOMMENDATION):
    return {
        "review_rank": len(review_item_id),
        "review_item_id": review_item_id,
        "effect_id": f"effect_{review_item_id}",
        "review_recommendation": recommendation,
        "confidence": "medium" if recommendation == SAFE_RECOMMENDATION else "low",
        "projected_event_reduction": 1,
        "type_conflict_classification": "type_only_single_family_subcode_conflict",
        "review_risk_tier": "high",
        "identity_consistency": "mixed_or_incomplete_identity",
        "type_values": ["4ctg", "4tg"],
        "type_family_prefixes": ["4"],
        "active_conflicts": ["location", "type"],
        "failed_conditions": [] if recommendation == SAFE_RECOMMENDATION else ["summary_text_compatible"],
        "source_names": ["ufocat"],
        "source_native_ids": ["18509"],
        "dates": ["1952-10-17"],
        "times": ["1250"],
        "locations": ["OLORON, Pyrenees-Atl, FRA, EU", "OLORON-STE-MARIE, Pyrenees-Atl, FRA, EU"],
        "coordinate_values": ["43.187,0.609"],
        "review_reason_codes": ["same_source_native_date", "compatible_summary_text", "review_only_not_decision"],
        "merge_canonical_event_ids": event_ids,
        "candidate_canonical_input_ids": input_ids or [f"input_{event_id}" for event_id in event_ids],
    }


def _review():
    return {
        "review_policy": "entity_resolution_type_conflict_source_identity_review_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "validated_decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "items": [
            _review_item("review_a", ["evt_a", "evt_b"], ["in_a", "in_b"]),
            _review_item("review_b", ["evt_b", "evt_c"], ["in_b", "in_c"]),
            _review_item("review_c", ["evt_x", "evt_y"], recommendation="needs_more_evidence"),
        ],
    }


def test_source_identity_review_groups_connected_candidates_without_mutation():
    report = group_type_conflict_source_identity_review_candidates(review=_review())

    assert report["canonical_outputs_mutated"] is False
    assert report["decisions_created"] is False
    assert report["summary"]["safe_recommendation_item_count"] == 2
    assert report["summary"]["blocked_or_needs_more_evidence_item_count"] == 1
    assert report["summary"]["group_count"] == 1
    assert report["summary"]["ready_group_count"] == 1
    assert report["summary"]["projected_event_reduction"] == 2

    group = report["groups"][0]
    assert group["group_recommendation"] == "source_identity_review_group_same_event_candidate"
    assert group["ready_for_decision_staging"] is True
    assert group["review_item_ids"] == ["review_a", "review_b"]
    assert group["merge_canonical_event_ids"] == ["evt_a", "evt_b", "evt_c"]
    assert group["canonical_input_ids"] == ["in_a", "in_b", "in_c"]
    assert group["group_blockers"] == []


def test_source_identity_review_groups_blocks_cross_source_connected_group():
    review = _review()
    review["items"][1]["source_names"] = ["ufocat", "nuforc"]

    report = group_type_conflict_source_identity_review_candidates(review=review)

    group = report["groups"][0]
    assert group["group_recommendation"] == "needs_more_evidence"
    assert group["ready_for_decision_staging"] is False
    assert "requires_single_source" in group["group_blockers"]


def test_source_identity_review_groups_rejects_unsafe_review_report():
    review = _review()
    review["preview_outputs_written"] = True

    with pytest.raises(ValueError, match="preview_outputs_written must be false"):
        group_type_conflict_source_identity_review_candidates(review=review)
