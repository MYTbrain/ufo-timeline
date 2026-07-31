import pytest

from scripts.check_entity_resolution_policy_body_preview import (
    check_entity_resolution_policy_body_preview,
)


def _safe_preview(previews):
    return {
        "preview_policy": "entity_resolution_canonical_merge_body_policy_preview_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "policy": "entity_resolution_canonical_merge_policy_proposal_v1",
        "selected_effect_count": len(previews),
        "policy_body_preview_count": len(previews),
        "previews": previews,
    }


def _preview():
    return {
        "patch_id": "patch_1",
        "effect_id": "effect_1",
        "review_item_id": "review_1",
        "body_policy": "canonical_merge_policy_preview_not_full_event_row",
        "canonical_event_id": "evt_a",
        "representative_event_id": "evt_a",
        "representative_selection": "highest_quality_preview_source_row",
        "canonical_input_id_count": 2,
        "source_event_count": 2,
        "entity_resolution_canonical_merged_event_ids": ["evt_a", "evt_b"],
        "entity_resolution_canonical_effect_ids": ["effect_1"],
        "entity_resolution_canonical_merge_policy": "entity_resolution_canonical_merge_policy_proposal_v1",
        "entity_resolution_canonical_merge_conflicts": {
            "summary": {
                "values": ["one", "two"],
                "source_values": [
                    {"canonical_event_id": "evt_a", "value": "one"},
                    {"canonical_event_id": "evt_b", "value": "two"},
                ],
            }
        },
    }


def test_policy_body_preview_check_accepts_valid_preview_metadata():
    report = check_entity_resolution_policy_body_preview(policy_body_preview=_safe_preview([_preview()]))

    assert report["canonical_outputs_mutated"] is False
    assert report["valid"] is True
    assert report["policy_body_preview_count"] == 1
    assert report["conflict_field_counts"] == {"summary": 1}
    assert report["validation_errors"] == []


def test_policy_body_preview_check_reports_bad_conflict_source_reference():
    preview = _preview()
    preview["entity_resolution_canonical_merge_conflicts"]["summary"]["source_values"][1][
        "canonical_event_id"
    ] = "evt_not_merged"
    report = check_entity_resolution_policy_body_preview(policy_body_preview=_safe_preview([preview]))

    assert report["valid"] is False
    assert report["invalid_conflict_metadata_count"] == 1
    assert report["validation_errors"][0]["error"] == "conflict_source_event_id_not_in_merged_ids"


def test_policy_body_preview_check_rejects_unsafe_preview():
    preview = _safe_preview([])
    preview["ready_for_canonical_apply"] = True

    with pytest.raises(ValueError, match="policy body preview is not safe"):
        check_entity_resolution_policy_body_preview(policy_body_preview=preview)


def test_policy_body_preview_check_accepts_cluster_preview_policy():
    preview = _preview()
    preview["entity_resolution_canonical_merge_policy"] = "entity_resolution_cluster_canonical_merge_policy_proposal_v1"
    preview["cluster_review_id"] = "review_1"
    preview["review_type"] = "entity_resolution_cluster_candidate"
    preview["entity_resolution_cluster_effect_ids"] = ["effect_1"]
    payload = _safe_preview([preview])
    payload["preview_policy"] = "entity_resolution_cluster_canonical_merge_body_policy_preview_only"
    payload["policy"] = "entity_resolution_cluster_canonical_merge_policy_proposal_v1"

    report = check_entity_resolution_policy_body_preview(policy_body_preview=payload)

    assert report["valid"] is True
    assert report["missing_required_field_count"] == 0
