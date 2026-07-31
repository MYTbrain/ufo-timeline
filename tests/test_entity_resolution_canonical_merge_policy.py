import pytest

from scripts.propose_entity_resolution_canonical_merge_policy import (
    propose_entity_resolution_canonical_merge_policy,
)


def _merged_event_preview():
    return {
        "preview_policy": "entity_resolution_compact_merged_event_preview_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "previews": [
            {"field_conflicts": {"summary": ["a", "b"], "type_normalized": ["5v", "5vw"]}},
            {"field_conflicts": {"summary": ["c", "d"], "location_raw": ["x", "y"]}},
        ],
    }


def _shadow_override_delta():
    return {
        "summary_policy": "entity_resolution_shadow_override_delta_summary",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "override_projected_event_reduction": 36,
        "remaining_excluded_merge_effect_count": 1,
    }


def _apply_readiness():
    return {
        "apply_readiness_policy": "entity_resolution_canonical_apply_readiness_gate",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "canonical_apply_blockers": [{"blocker": "final_merge_body_policy_missing"}],
    }


def test_canonical_merge_policy_proposal_summarizes_conflicts_and_stays_report_only():
    proposal = propose_entity_resolution_canonical_merge_policy(
        merged_event_preview=_merged_event_preview(),
        shadow_override_delta=_shadow_override_delta(),
        apply_readiness=_apply_readiness(),
    )

    assert proposal["canonical_outputs_mutated"] is False
    assert proposal["ready_for_apply_implementation"] is False
    assert proposal["observed_conflict_counts"] == {
        "location_raw": 1,
        "summary": 2,
        "type_normalized": 1,
    }
    assert proposal["field_policy"]["canonical_input_ids"]["rule"] == "union_preserve_first_seen_order"
    assert proposal["field_policy"]["scalar_conflicts"]["metadata_field"] == "entity_resolution_canonical_merge_conflicts"


def test_canonical_merge_policy_proposal_rejects_apply_ready_inputs():
    readiness = _apply_readiness()
    readiness["ready_for_canonical_apply"] = True

    with pytest.raises(ValueError, match="apply readiness report is not safe"):
        propose_entity_resolution_canonical_merge_policy(
            merged_event_preview=_merged_event_preview(),
            shadow_override_delta=_shadow_override_delta(),
            apply_readiness=readiness,
        )


def test_canonical_merge_policy_proposal_accepts_cluster_impact_and_readiness_shapes():
    impact_summary = {
        "impact_policy": "entity_resolution_plan_impact_summary_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "merge_impact": {"projected_event_reduction": 61},
    }
    cluster_readiness = {
        "readiness_policy": "entity_resolution_merge_preview_readiness_gate",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "canonical_apply_blocker": "full_shadow_preview_and_final_merge_body_policy_required",
        "blocking_conflict_item_count": 538,
    }
    override_subset = {
        "subset_policy": "entity_resolution_shadow_preview_subset_with_analysis_overrides",
        "effect_policy": "entity_resolution_plan_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "excluded_merge_effect_count": 520,
    }

    proposal = propose_entity_resolution_canonical_merge_policy(
        merged_event_preview=_merged_event_preview(),
        shadow_override_delta=impact_summary,
        apply_readiness=cluster_readiness,
        override_subset=override_subset,
    )

    assert proposal["policy"] == "entity_resolution_cluster_canonical_merge_policy_proposal_v1"
    assert proposal["policy_context"] == "cluster_shadow_override"
    assert proposal["summary_source_policy"] == "entity_resolution_plan_impact_summary_only"
    assert proposal["readiness_source_policy"] == "entity_resolution_merge_preview_readiness_gate"
    assert proposal["shadow_override_projected_reduction"] == 61
    assert proposal["remaining_excluded_merge_effect_count"] == 520
    assert proposal["canonical_apply_blockers"] == [
        {
            "blocker": "full_shadow_preview_and_final_merge_body_policy_required",
            "severity": "hard",
            "reason": "Cluster merge preview readiness gate did not clear canonical apply.",
        },
        {
            "blocker": "merge_preview_blocking_conflicts_remaining",
            "severity": "hard",
            "count": 538,
            "reason": "Cluster compact merge previews still contain blocking conflicts.",
        },
    ]
