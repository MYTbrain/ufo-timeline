import pytest

from scripts.combine_time_norm_accepted_decisions import (
    COMBINE_POLICY,
    combine_time_norm_accepted_decisions,
)


def _decision(decision_id, review_item_id, event_ids, *, acceptance_policy):
    return {
        "entity_resolution_decision_id": decision_id,
        "review_item_id": review_item_id,
        "decision": "same_event",
        "accepted_canonical_decision": True,
        "acceptance_policy": acceptance_policy,
        "canonical_outputs_mutated": False,
        "requires_explicit_apply_step": True,
        "merge_canonical_event_ids": event_ids,
    }


def _clean_decision(event_ids=None):
    return _decision(
        "erd_clean",
        "review_clean",
        event_ids or ["evt_a", "evt_b"],
        acceptance_policy="entity_resolution_time_norm_recommended_policy_acceptance_v1",
    )


def _shorthand_decision(event_ids=None):
    return _decision(
        "erd_shorthand",
        "review_shorthand",
        event_ids or ["evt_c", "evt_d", "evt_e"],
        acceptance_policy="entity_resolution_time_norm_deferred_shorthand_policy_acceptance_v1",
    )


def _likely_time_format_decision(event_ids=None):
    return _decision(
        "erd_likely",
        "review_likely",
        event_ids or ["evt_f", "evt_g"],
        acceptance_policy="entity_resolution_likely_time_format_policy_acceptance_v1",
    )


def _single_exact_context_decision(event_ids=None):
    return _decision(
        "erd_single_exact",
        "review_single_exact",
        event_ids or ["evt_h", "evt_i", "evt_j"],
        acceptance_policy="entity_resolution_single_exact_context_policy_acceptance_v1",
    )


def test_combine_time_norm_accepted_decisions_requires_non_overlapping_lanes():
    combined, report = combine_time_norm_accepted_decisions(
        clean_decisions=[_clean_decision()],
        shorthand_decisions=[_shorthand_decision()],
    )

    assert report["combine_policy"] == COMBINE_POLICY
    assert report["canonical_outputs_mutated"] is False
    assert report["combined_decision_count"] == 2
    assert report["projected_event_reduction"] == 3
    assert combined[0]["combined_time_norm_lane"] == "clean_recommended"
    assert combined[1]["combined_time_norm_lane"] == "deferred_shorthand"
    assert combined[1]["combine_policy"] == COMBINE_POLICY


def test_combine_time_norm_accepted_decisions_accepts_likely_time_format_lane():
    combined, report = combine_time_norm_accepted_decisions(
        clean_decisions=[_clean_decision()],
        shorthand_decisions=[_shorthand_decision()],
        likely_time_format_decisions=[_likely_time_format_decision()],
    )

    assert report["combined_decision_count"] == 3
    assert report["likely_time_format_decision_count"] == 1
    assert report["lane_decision_counts"]["likely_time_format"] == 1
    assert report["projected_event_reduction"] == 4
    assert combined[2]["combined_time_norm_lane"] == "likely_time_format"


def test_combine_time_norm_accepted_decisions_accepts_single_exact_context_lane():
    combined, report = combine_time_norm_accepted_decisions(
        clean_decisions=[_clean_decision()],
        shorthand_decisions=[_shorthand_decision()],
        likely_time_format_decisions=[_likely_time_format_decision()],
        single_exact_context_decisions=[_single_exact_context_decision()],
    )

    assert report["combined_decision_count"] == 4
    assert report["single_exact_context_decision_count"] == 1
    assert report["lane_decision_counts"]["single_exact_context"] == 1
    assert report["projected_event_reduction"] == 6
    assert combined[3]["combined_time_norm_lane"] == "single_exact_context"


def test_combine_time_norm_accepted_decisions_rejects_event_overlap():
    with pytest.raises(ValueError, match="canonical_event_id_in_multiple_accepted_lanes"):
        combine_time_norm_accepted_decisions(
            clean_decisions=[_clean_decision(["evt_a", "evt_b"])],
            shorthand_decisions=[_shorthand_decision(["evt_c", "evt_d"])],
            likely_time_format_decisions=[_likely_time_format_decision(["evt_b", "evt_e"])],
        )


def test_combine_time_norm_accepted_decisions_rejects_unaccepted_decision():
    decision = _clean_decision()
    decision["accepted_canonical_decision"] = False

    with pytest.raises(ValueError, match="accepted_canonical_decision_must_be_true"):
        combine_time_norm_accepted_decisions(clean_decisions=[decision], shorthand_decisions=[])
