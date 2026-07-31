from scripts.accept_remaining_lower_time_format_decision_candidates import (
    accept_remaining_lower_time_format_decision_candidates,
)


def test_accept_remaining_lower_candidates_writes_accepted_records_and_effects_plan():
    accepted, effects_plan, report = accept_remaining_lower_time_format_decision_candidates(
        candidates=[
            {
                "entity_resolution_decision_id": "decision_1",
                "review_item_id": "review_1",
                "decision": "same_event",
                "merge_canonical_event_ids": ["evt_a", "evt_b", "evt_c"],
                "canonical_input_ids": ["cin_a", "cin_b"],
                "canonical_outputs_mutated": False,
            }
        ],
        check_report={
            "valid": True,
            "decision_candidate_count": 1,
            "canonical_outputs_mutated": False,
            "preview_outputs_written": False,
            "auto_merge_performed": False,
            "overlap_with_accepted_review_ids": [],
            "overlap_with_deferred_review_ids": [],
        },
        approver="test",
        accepted_at="2026-05-22T00:00:00+00:00",
    )

    assert report["acceptance_policy"] == "entity_resolution_remaining_lower_time_format_accepted_decisions_v1"
    assert report["accepted_canonical_decisions_created"] is True
    assert report["canonical_outputs_mutated"] is False
    assert report["ready_for_sidecar_apply"] is True
    assert report["projected_event_reduction"] == 2
    assert accepted[0]["effect_status"] == "accepted_for_sidecar_apply"
    assert accepted[0]["accepted_by"] == "test"
    assert effects_plan["effect_policy"] == "entity_resolution_plan_only"
    assert effects_plan["planned_effect_count"] == 1
    assert effects_plan["effects"][0]["merge_canonical_event_ids"] == ["evt_a", "evt_b", "evt_c"]
