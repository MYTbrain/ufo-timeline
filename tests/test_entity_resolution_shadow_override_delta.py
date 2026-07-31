import pytest

from scripts.summarize_entity_resolution_shadow_override_delta import (
    summarize_entity_resolution_shadow_override_delta,
)


def _ready_subset():
    return {
        "effect_policy": "entity_resolution_plan_only",
        "subset_policy": "entity_resolution_ready_subset_for_shadow_preview",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "selected_merge_effect_count": 33,
    }


def _override_subset():
    return {
        "effect_policy": "entity_resolution_plan_only",
        "subset_policy": "entity_resolution_shadow_preview_subset_with_analysis_overrides",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "override_decisions_created": False,
        "selected_merge_effect_count": 36,
        "override_selected_merge_effect_count": 3,
        "excluded_effects": [{"review_item_id": "review_coordinate"}],
    }


def _preview_report(reduction, rows):
    return {
        "apply_policy": "entity_resolution_stream_preview_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": True,
        "effects_blocked": 0,
        "projected_event_reduction": reduction,
        "preview_event_count": rows,
    }


def _output_check(rows):
    return {
        "check_policy": "entity_resolution_shadow_preview_output_check",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "valid": True,
        "row_count": rows,
    }


def _blocked_analysis():
    return {
        "analysis_policy": "entity_resolution_blocked_merge_analysis_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "classification_counts": {"likely_source_subtype_variant": 3},
        "suggested_action_counts": {"candidate_shadow_preview_override": 3},
    }


def test_shadow_override_delta_summary_compares_ready_and_override_previews():
    summary = summarize_entity_resolution_shadow_override_delta(
        ready_subset=_ready_subset(),
        ready_preview_report=_preview_report(33, 944545),
        ready_output_check=_output_check(944545),
        override_subset=_override_subset(),
        override_preview_report=_preview_report(36, 944542),
        override_output_check=_output_check(944542),
        blocked_analysis=_blocked_analysis(),
    )

    assert summary["canonical_outputs_mutated"] is False
    assert summary["ready_projected_event_reduction"] == 33
    assert summary["override_projected_event_reduction"] == 36
    assert summary["incremental_projected_event_reduction"] == 3
    assert summary["remaining_excluded_merge_effect_count"] == 1
    assert summary["remaining_excluded_review_item_ids"] == ["review_coordinate"]
    assert summary["ready_for_canonical_apply"] is False


def test_shadow_override_delta_summary_rejects_invalid_output_check():
    invalid_check = _output_check(944542)
    invalid_check["valid"] = False

    with pytest.raises(ValueError, match="override_output_check is not safe"):
        summarize_entity_resolution_shadow_override_delta(
            ready_subset=_ready_subset(),
            ready_preview_report=_preview_report(33, 944545),
            ready_output_check=_output_check(944545),
            override_subset=_override_subset(),
            override_preview_report=_preview_report(36, 944542),
            override_output_check=invalid_check,
            blocked_analysis=_blocked_analysis(),
        )
