from scripts.plan_manual_review_effects import build_manual_review_effects_plan


def test_manual_review_effect_plan_maps_duplicate_decisions_without_mutation():
    queue = [
        {
            "review_item_id": "rev_dup",
            "review_type": "duplicate_candidate",
            "candidate": {
                "duplicate_candidate_id": "dupc_1",
                "score": 0.97,
                "reasons": ["same_strong_date", "same_normalized_location"],
                "canonical_input_ids": ["cin_a", "cin_b"],
                "blocking": {"date_iso": "1952-07-19", "location_key": "washington dc usa"},
            },
        }
    ]
    decisions = [
        {
            "review_item_id": "rev_dup",
            "review_type": "duplicate_candidate",
            "decision": "same_event",
            "replacement_canonical_event_id": "evt_primary",
            "reviewer": "analyst-a",
        }
    ]

    plan = build_manual_review_effects_plan(queue=queue, applied_decisions=decisions)

    assert plan["effect_policy"] == "plan_only"
    assert plan["canonical_outputs_mutated"] is False
    assert plan["planned_effect_count"] == 1
    effect = plan["effects"][0]
    assert effect["effect_id"].startswith("mre_")
    assert effect["effect_status"] == "planned_not_applied"
    assert effect["effect_type"] == "merge_duplicate_candidate"
    assert effect["planned_effect"] == "merge_duplicate_candidate"
    assert effect["action_class"] == "merge"
    assert effect["requires_explicit_apply_step"] is True
    assert effect["canonical_input_ids"] == ["cin_a", "cin_b"]
    assert effect["replacement_canonical_event_id"] == "evt_primary"


def test_manual_review_effect_plan_keeps_distinct_duplicate_decisions_as_noop():
    queue = [
        {
            "review_item_id": "rev_dup",
            "review_type": "duplicate_candidate",
            "candidate": {
                "duplicate_candidate_id": "dupc_1",
                "canonical_input_ids": ["cin_a", "cin_b"],
            },
        }
    ]
    decisions = [
        {
            "review_item_id": "rev_dup",
            "review_type": "duplicate_candidate",
            "decision": "distinct_events",
        }
    ]

    plan = build_manual_review_effects_plan(queue=queue, applied_decisions=decisions)

    effect = plan["effects"][0]
    assert effect["planned_effect"] == "preserve_distinct_events"
    assert effect["action_class"] == "preserve"
    assert effect["requires_explicit_apply_step"] is False
    assert effect["canonical_outputs_mutated"] is False


def test_manual_review_effect_plan_maps_row_exclusion_to_explicit_apply_step():
    queue = [
        {
            "review_item_id": "rev_row",
            "review_type": "row_shape_anomaly",
            "canonical_input_id": "cin_row",
            "source_file": "nuforcpy.csv",
            "source_row_number": 12,
            "source_row_anomalies": ["extra_columns"],
        }
    ]
    decisions = [
        {
            "review_item_id": "rev_row",
            "review_type": "row_shape_anomaly",
            "decision": "exclude_source_row",
        }
    ]

    plan = build_manual_review_effects_plan(queue=queue, applied_decisions=decisions)

    effect = plan["effects"][0]
    assert effect["planned_effect"] == "exclude_source_row"
    assert effect["action_class"] == "exclude"
    assert effect["requires_explicit_apply_step"] is True
    assert effect["canonical_input_ids"] == ["cin_row"]
    assert plan["effect_counts"] == {"exclude_source_row": 1}


def test_manual_review_effect_plan_reports_unknown_and_duplicate_applied_decisions():
    queue = [
        {
            "review_item_id": "rev_known",
            "review_type": "row_shape_anomaly",
            "canonical_input_id": "cin_row",
        }
    ]
    decisions = [
        {
            "review_item_id": "rev_missing",
            "review_type": "duplicate_candidate",
            "decision": "same_event",
        },
        {
            "review_item_id": "rev_known",
            "review_type": "row_shape_anomaly",
            "decision": "repair_source_row",
        },
        {
            "review_item_id": "rev_known",
            "review_type": "row_shape_anomaly",
            "decision": "exclude_source_row",
        },
    ]

    plan = build_manual_review_effects_plan(queue=queue, applied_decisions=decisions)

    assert [effect["planned_effect"] for effect in plan["effects"]] == [
        "blocked_unknown_review_item",
        "repair_source_row_upstream",
    ]
    assert plan["warnings"] == [
        {
            "decision_index": 1,
            "review_item_id": "rev_missing",
            "warning": "applied_decision_missing_from_queue",
        },
        {
            "decision_index": 3,
            "review_item_id": "rev_known",
            "warning": "duplicate_applied_decision_skipped",
        },
    ]
