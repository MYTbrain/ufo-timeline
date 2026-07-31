from scripts.plan_entity_resolution_effects import build_entity_resolution_effects_plan


def _decision(decision_id, review_item_id, decision):
    return {
        "entity_resolution_decision_id": decision_id,
        "review_item_id": review_item_id,
        "review_type": "entity_resolution_candidate",
        "decision": decision,
        "review_band": "likely_same_event_review",
        "score": 0.98,
        "canonical_input_ids": ["cin_a", "cin_b"],
        "merge_canonical_event_ids": ["evt_a", "evt_b"],
        "reviewer": "analyst",
    }


def test_entity_resolution_effects_plan_maps_same_event_without_mutation():
    plan = build_entity_resolution_effects_plan(
        validated_decisions=[_decision("erd_1", "er_review_1", "same_event")]
    )

    assert plan["effect_policy"] == "entity_resolution_plan_only"
    assert plan["canonical_outputs_mutated"] is False
    assert plan["canonical_outputs_mutated_by_plan"] is False
    assert plan["planned_effect_count"] == 1
    assert plan["requires_explicit_apply_step_count"] == 1
    effect = plan["effects"][0]
    assert effect["effect_id"].startswith("ere_")
    assert effect["planned_effect"] == "merge_entity_resolution_candidate"
    assert effect["action_class"] == "merge"
    assert effect["requires_explicit_apply_step"] is True
    assert effect["canonical_input_ids"] == ["cin_a", "cin_b"]
    assert effect["merge_canonical_event_ids"] == ["evt_a", "evt_b"]


def test_entity_resolution_effects_plan_accepts_cluster_candidate_decisions():
    decision = _decision("erdc_1", "er_cluster_1", "same_event")
    decision["review_type"] = "entity_resolution_cluster_candidate"
    decision["merge_canonical_event_ids"] = ["evt_a", "evt_b", "evt_c"]

    plan = build_entity_resolution_effects_plan(validated_decisions=[decision])

    assert plan["planned_effect_count"] == 1
    effect = plan["effects"][0]
    assert effect["review_type"] == "entity_resolution_cluster_candidate"
    assert effect["planned_effect"] == "merge_entity_resolution_candidate"
    assert effect["merge_canonical_event_ids"] == ["evt_a", "evt_b", "evt_c"]


def test_entity_resolution_effects_plan_maps_preserve_and_defer():
    plan = build_entity_resolution_effects_plan(
        validated_decisions=[
            _decision("erd_1", "er_review_1", "distinct_events"),
            _decision("erd_2", "er_review_2", "needs_more_evidence"),
        ]
    )

    assert [effect["planned_effect"] for effect in plan["effects"]] == [
        "preserve_distinct_events",
        "defer_entity_resolution_candidate",
    ]
    assert plan["requires_explicit_apply_step_count"] == 0


def test_entity_resolution_effects_plan_skips_duplicate_decisions():
    plan = build_entity_resolution_effects_plan(
        validated_decisions=[
            _decision("erd_1", "er_review_1", "same_event"),
            _decision("erd_1", "er_review_2", "same_event"),
            _decision("erd_2", "er_review_1", "same_event"),
            {"review_item_id": "missing_decision_id", "decision": "same_event"},
        ]
    )

    assert plan["planned_effect_count"] == 1
    assert [warning["warning"] for warning in plan["warnings"]] == [
        "duplicate_decision_id_skipped",
        "duplicate_review_item_id_skipped",
        "missing_entity_resolution_decision_id",
    ]
