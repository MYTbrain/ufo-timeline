import pytest

from scripts.build_entity_resolution_policy_body_preview import (
    build_entity_resolution_policy_body_preview,
)


def _merged_event_preview():
    return {
        "preview_policy": "entity_resolution_compact_merged_event_preview_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "previews": [
            {
                "patch_id": "patch_1",
                "effect_id": "effect_1",
                "review_item_id": "review_1",
                "source_event_count": 2,
                "preview_event": {
                    "canonical_event_id": "evt_a",
                    "representative_event_id": "evt_a",
                    "representative_selection": "highest_quality_preview_source_row",
                    "canonical_input_ids": ["cin_a", "cin_b"],
                    "representative_fields": {"summary": "one"},
                    "source_provenance_summary": {"source_record_count": 2},
                    "entity_resolution_preview_merged_event_ids": ["evt_a", "evt_b"],
                },
                "source_event_summaries": [
                    {"canonical_event_id": "evt_a", "summary": "one", "type_normalized": "5v"},
                    {"canonical_event_id": "evt_b", "summary": "two", "type_normalized": "5vw"},
                ],
                "field_conflicts": {"summary": ["one", "two"], "type_normalized": ["5v", "5vw"]},
            },
            {
                "patch_id": "patch_2",
                "effect_id": "effect_2",
                "review_item_id": "review_2",
                "source_event_count": 2,
                "preview_event": {"canonical_event_id": "evt_c", "canonical_input_ids": ["cin_c", "cin_d"]},
                "field_conflicts": {},
            },
        ],
    }


def _policy_proposal():
    return {
        "policy": "entity_resolution_canonical_merge_policy_proposal_v1",
        "ready_for_apply_implementation": False,
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
    }


def _override_subset():
    return {
        "effect_policy": "entity_resolution_plan_only",
        "subset_policy": "entity_resolution_shadow_preview_subset_with_analysis_overrides",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "effects": [{"effect_id": "effect_1"}],
    }


def test_policy_body_preview_builds_conflict_metadata_for_selected_effects_only():
    report = build_entity_resolution_policy_body_preview(
        merged_event_preview=_merged_event_preview(),
        policy_proposal=_policy_proposal(),
        override_subset=_override_subset(),
    )

    assert report["canonical_outputs_mutated"] is False
    assert report["policy_body_preview_count"] == 1
    assert report["skipped_preview_count"] == 1
    preview = report["previews"][0]
    assert preview["canonical_input_id_count"] == 2
    assert preview["entity_resolution_canonical_merged_event_ids"] == ["evt_a", "evt_b"]
    assert preview["entity_resolution_canonical_merge_conflicts"]["summary"]["source_values"] == [
        {"canonical_event_id": "evt_a", "value": "one"},
        {"canonical_event_id": "evt_b", "value": "two"},
    ]


def test_policy_body_preview_rejects_unsafe_policy_proposal():
    unsafe_policy = _policy_proposal()
    unsafe_policy["ready_for_apply_implementation"] = True

    with pytest.raises(ValueError, match="policy proposal is not safe"):
        build_entity_resolution_policy_body_preview(
            merged_event_preview=_merged_event_preview(),
            policy_proposal=unsafe_policy,
            override_subset=_override_subset(),
        )


def test_policy_body_preview_marks_cluster_policy_outputs():
    policy = _policy_proposal()
    policy["policy"] = "entity_resolution_cluster_canonical_merge_policy_proposal_v1"
    policy["policy_context"] = "cluster_shadow_override"

    report = build_entity_resolution_policy_body_preview(
        merged_event_preview=_merged_event_preview(),
        policy_proposal=policy,
        override_subset=_override_subset(),
    )

    assert report["preview_policy"] == "entity_resolution_cluster_canonical_merge_body_policy_preview_only"
    assert report["policy_context"] == "cluster_shadow_override"
    preview = report["previews"][0]
    assert preview["cluster_review_id"] == "review_1"
    assert preview["review_type"] == "entity_resolution_cluster_candidate"
    assert preview["entity_resolution_cluster_effect_ids"] == ["effect_1"]
