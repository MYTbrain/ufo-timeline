from scripts.validate_entity_resolution_cluster_decisions import validate_entity_resolution_cluster_decisions


def _packet_item(**overrides):
    item = {
        "cluster_review_id": "er_cluster_a",
        "family_id": "same_source_native_id_strong_date",
        "family_description": "Same native ID and exact date.",
        "tier": "conservative",
        "key_hash": "dgk_a",
        "projected_event_reduction": 2,
        "unique_current_event_count": 3,
        "source_record_count": 4,
        "sample_input_ids": ["cin_a", "cin_b"],
        "current_event_ids": ["evt_c", "evt_a", "evt_b"],
        "current_event_ids_truncated": False,
        "source_names": ["ufocat"],
        "date_iso": "1954-09-19",
        "distinct_date_count": 1,
        "location": "RONGERES, FRA",
        "distinct_location_count": 1,
    }
    item.update(overrides)
    return item


def _packet(*items):
    return {
        "packet_policy": "entity_resolution_cluster_review_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "items": list(items),
    }


def test_validate_entity_resolution_cluster_decisions_normalizes_same_event_without_mutation():
    packet = _packet(_packet_item())
    decisions = [
        {
            "cluster_review_id": "er_cluster_a",
            "decision": "same_event",
            "reviewer": "analyst",
            "reviewed_at": "2026-05-22T00:00:00Z",
            "notes": "same source cluster",
        }
    ]

    normalized, report = validate_entity_resolution_cluster_decisions(packet=packet, decisions=decisions)

    assert report["decision_policy"] == "entity_resolution_cluster_decision_validation_only"
    assert report["canonical_outputs_mutated"] is False
    assert report["valid_decision_count"] == 1
    assert report["invalid_decision_count"] == 0
    assert report["planned_effect_counts"] == {"merge_entity_resolution_candidate": 1}
    assert normalized[0]["review_type"] == "entity_resolution_cluster_candidate"
    assert normalized[0]["planned_effect"] == "merge_entity_resolution_candidate"
    assert normalized[0]["requires_explicit_apply_step"] is True
    assert normalized[0]["merge_canonical_event_ids"] == ["evt_a", "evt_b", "evt_c"]
    assert normalized[0]["canonical_input_ids"] == ["cin_a", "cin_b"]


def test_validate_entity_resolution_cluster_decisions_rejects_truncated_same_event_cluster():
    packet = _packet(_packet_item(current_event_ids=["evt_a", "evt_b"], current_event_ids_truncated=True))
    decisions = [{"cluster_review_id": "er_cluster_a", "decision": "same_event"}]

    normalized, report = validate_entity_resolution_cluster_decisions(packet=packet, decisions=decisions)

    assert normalized == []
    assert report["valid_decision_count"] == 0
    assert report["invalid_decision_count"] == 1
    assert report["invalid_decisions"][0]["error"] == "same_event_requires_complete_current_event_ids"


def test_validate_entity_resolution_cluster_decisions_preserves_distinct_and_defer():
    packet = _packet(_packet_item(cluster_review_id="er_cluster_a"), _packet_item(cluster_review_id="er_cluster_b"))
    decisions = [
        {"cluster_review_id": "er_cluster_a", "decision": "distinct_events"},
        {"cluster_review_id": "er_cluster_b", "decision": "needs_more_evidence"},
    ]

    normalized, report = validate_entity_resolution_cluster_decisions(packet=packet, decisions=decisions)

    assert report["valid_decision_count"] == 2
    assert [record["planned_effect"] for record in normalized] == [
        "preserve_distinct_events",
        "defer_entity_resolution_candidate",
    ]
    assert all(record["merge_canonical_event_ids"] == [] for record in normalized)


def test_validate_entity_resolution_cluster_decisions_reports_invalid_and_duplicate_decisions():
    packet = _packet(_packet_item())
    decisions = [
        {"cluster_review_id": "missing", "decision": "same_event"},
        {"cluster_review_id": "er_cluster_a", "decision": "merge_it"},
        {"cluster_review_id": "er_cluster_a", "decision": "same_event"},
        {"decision": "same_event"},
    ]

    normalized, report = validate_entity_resolution_cluster_decisions(packet=packet, decisions=decisions)

    assert normalized == []
    assert report["invalid_decision_count"] == 4
    assert [item["error"] for item in report["invalid_decisions"]] == [
        "cluster_review_id_not_in_packet",
        "invalid_decision",
        "duplicate_decision_for_cluster_review_id",
        "missing_cluster_review_id",
    ]
