from scripts.validate_entity_resolution_decisions import validate_entity_resolution_decisions


def _packet_item(review_item_id="er_review_1"):
    return {
        "review_item_id": review_item_id,
        "review_band": "likely_same_event_review",
        "score": 0.98,
        "cross_current_event": True,
        "evidence": ["same_exact_day"],
        "risk_flags": [],
        "left": {
            "canonical_input_id": "cin_a",
            "canonical_event_id": "evt_a",
        },
        "right": {
            "canonical_input_id": "cin_b",
            "canonical_event_id": "evt_b",
        },
    }


def test_validate_entity_resolution_decisions_normalizes_same_event_without_mutation():
    packet = {"items": [_packet_item()]}
    decisions = [
        {
            "review_item_id": "er_review_1",
            "decision": "same_event",
            "reviewer": "analyst",
            "reviewed_at": "2026-05-22T00:00:00Z",
            "notes": "same source row duplicate",
        }
    ]

    normalized, report = validate_entity_resolution_decisions(packet=packet, decisions=decisions)

    assert report["canonical_outputs_mutated"] is False
    assert report["auto_merge_performed"] is False
    assert report["valid_decision_count"] == 1
    assert report["invalid_decision_count"] == 0
    assert report["planned_effect_counts"] == {"merge_entity_resolution_candidate": 1}
    assert normalized[0]["planned_effect"] == "merge_entity_resolution_candidate"
    assert normalized[0]["requires_explicit_apply_step"] is True
    assert normalized[0]["canonical_input_ids"] == ["cin_a", "cin_b"]
    assert normalized[0]["merge_canonical_event_ids"] == ["evt_a", "evt_b"]


def test_validate_entity_resolution_decisions_preserves_distinct_and_defer_decisions():
    packet = {"items": [_packet_item("er_review_a"), _packet_item("er_review_b")]}
    decisions = [
        {"review_item_id": "er_review_a", "decision": "distinct_events"},
        {"review_item_id": "er_review_b", "decision": "needs_more_evidence"},
    ]

    normalized, report = validate_entity_resolution_decisions(packet=packet, decisions=decisions)

    assert [record["planned_effect"] for record in normalized] == [
        "preserve_distinct_events",
        "defer_entity_resolution_candidate",
    ]
    assert report["valid_decision_count"] == 2
    assert report["invalid_decision_count"] == 0


def test_validate_entity_resolution_decisions_reports_invalid_and_duplicate_decisions():
    packet = {"items": [_packet_item()]}
    decisions = [
        {"review_item_id": "missing", "decision": "same_event"},
        {"review_item_id": "er_review_1", "decision": "merge_it"},
        {"review_item_id": "er_review_1", "decision": "same_event"},
        {"decision": "same_event"},
    ]

    normalized, report = validate_entity_resolution_decisions(packet=packet, decisions=decisions)

    assert normalized == []
    assert report["invalid_decision_count"] == 4
    assert [item["error"] for item in report["invalid_decisions"]] == [
        "review_item_id_not_in_packet",
        "invalid_decision",
        "duplicate_decision_for_review_item",
        "missing_review_item_id",
    ]


def test_validate_entity_resolution_decisions_warns_for_already_merged_same_event():
    item = _packet_item()
    item["cross_current_event"] = False
    packet = {"items": [item]}
    decisions = [{"review_item_id": "er_review_1", "decision": "same_event"}]

    normalized, report = validate_entity_resolution_decisions(packet=packet, decisions=decisions)

    assert len(normalized) == 1
    assert report["warnings"] == [
        {
            "decision_index": 1,
            "review_item_id": "er_review_1",
            "warning": "same_event_for_non_cross_current_event_pair",
        }
    ]
