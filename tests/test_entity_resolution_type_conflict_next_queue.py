from scripts.build_entity_resolution_type_conflict_next_queue import (
    build_entity_resolution_type_conflict_next_queue,
)


def _analysis_item(review_item_id, classification, risk="high", identity="mixed_or_incomplete_identity"):
    return {
        "review_rank": 1,
        "review_item_id": review_item_id,
        "effect_id": f"effect_{review_item_id}",
        "patch_id": f"patch_{review_item_id}",
        "projected_event_reduction": 1,
        "type_conflict_classification": classification,
        "review_risk_tier": risk,
        "identity_consistency": identity,
        "blocking_fields": ["type_normalized"],
        "type_values": ["4a", "5c"],
        "type_family_prefixes": ["4", "5"],
        "shape_values": [],
        "time_values": [],
        "risk_flags": [],
        "has_coordinate_risk": classification == "type_with_coordinate_conflict",
        "source_summary": {
            "canonical_event_ids": ["evt_a", "evt_b"],
            "canonical_input_ids": ["cin_a", "cin_b"],
            "source_names": ["ufocat"],
            "source_native_ids": ["native_1"],
            "date_values": ["1954-10-01"],
            "location_values": ["PARIS, FRA, EU"],
        },
        "recommended_review_step": "Review.",
    }


def _analysis():
    return {
        "analysis_policy": "entity_resolution_cluster_type_conflict_review_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "items": [
            _analysis_item(
                "already_staged",
                "type_only_single_family_subcode_conflict",
                risk="lower",
                identity="single_source_id_date_location",
            ),
            _analysis_item("single_family_high", "type_only_single_family_subcode_conflict"),
            _analysis_item("cross_family", "type_only_cross_family_conflict"),
            _analysis_item("shape_conflict", "type_only_single_family_with_shape_conflict"),
            _analysis_item("coordinate_type", "type_with_coordinate_conflict"),
        ],
    }


def test_type_conflict_next_queue_excludes_staged_review_members_and_counts_lanes():
    report = build_entity_resolution_type_conflict_next_queue(
        analysis=_analysis(),
        already_staged_decisions=[
            {
                "source_review_group": {
                    "member_review_item_ids": ["already_staged"],
                }
            }
        ],
    )

    assert report["canonical_outputs_mutated"] is False
    assert report["decisions_created"] is False
    assert report["summary"]["already_staged_review_item_count"] == 1
    assert report["summary"]["remaining_item_count"] == 4
    assert report["summary"]["next_lane_counts"] == {
        "coordinate_plus_type_blocked": 1,
        "cross_family_human_review_only": 1,
        "shape_type_semantics_review": 1,
        "source_row_identity_review": 1,
    }


def test_type_conflict_next_queue_rejects_unsafe_analysis():
    analysis = _analysis()
    analysis["canonical_outputs_mutated"] = True

    try:
        build_entity_resolution_type_conflict_next_queue(analysis=analysis)
    except ValueError as error:
        assert "canonical_outputs_mutated must be false" in str(error)
    else:
        raise AssertionError("Expected unsafe analysis to be rejected")
