import json

import pytest

from scripts.check_time_norm_recommended_canonical_apply_contract import (
    check_time_norm_recommended_canonical_apply_contract,
)


def _effects_plan():
    return {
        "effect_policy": "entity_resolution_plan_only",
        "canonical_outputs_mutated": False,
        "canonical_outputs_mutated_by_plan": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "effects": [
            {
                "effect_id": "effect_1",
                "review_item_id": "review_1",
                "planned_effect": "merge_entity_resolution_candidate",
                "merge_canonical_event_ids": ["evt_a", "evt_b"],
            }
        ],
    }


def _merge_patch():
    return {
        "patch_policy": "entity_resolution_merge_patch_preview_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "patches": [
            {
                "effect_id": "effect_1",
                "review_item_id": "review_1",
                "replacement_canonical_event_id": "evt_a",
                "suppressed_canonical_event_ids": ["evt_b"],
                "merge_canonical_event_ids": ["evt_a", "evt_b"],
            }
        ],
    }


def _recommendations():
    return {
        "recommendation_policy": "entity_resolution_time_norm_auto_recommendation_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "validated_decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "recommendations": [
            {"review_item_id": "review_1", "recommendation": "recommend_same_event"},
            {"review_item_id": "deferred", "recommendation": "needs_more_evidence"},
        ],
    }


def _classification():
    return {
        "classification_policy": "entity_resolution_time_norm_recommended_policy_conflict_classification_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "summary": {"blocking_preview_count": 0},
        "items": [
            {
                "review_item_id": "review_1",
                "policy_action": "candidate_for_final_policy_after_decision_acceptance",
                "blockers": [],
            }
        ],
    }


def _preview_output_check():
    return {
        "check_policy": "entity_resolution_shadow_preview_output_check",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "valid": True,
        "row_count": 2,
        "preview_merge_count": 1,
    }


def _row(event_id, input_ids, time_raw):
    return {
        "canonical_event_id": event_id,
        "canonical_input_ids": input_ids,
        "time_raw": time_raw,
        "source_provenance": [
            {"canonical_input_id": input_id, "source_name": "ufocat"} for input_id in input_ids
        ],
    }


def _write_jsonl(path, rows):
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def test_time_norm_canonical_apply_contract_validates_full_row_preview(tmp_path):
    original = tmp_path / "original.jsonl"
    preview = tmp_path / "preview.jsonl"
    untouched = _row("evt_c", ["cin_c"], "1200")
    merged = {
        **_row("evt_a", ["cin_a", "cin_b"], "1000"),
        "duplicate_record_count": 2,
        "dedupe_strategy": "entity_resolution_preview_merge",
        "entity_resolution_preview_merged_event_ids": ["evt_a", "evt_b"],
        "entity_resolution_preview_effect_ids": ["effect_1"],
        "source_provenance": [
            {"canonical_input_id": "cin_a", "source_name": "ufocat"},
            {"canonical_input_id": "cin_b", "source_name": "ufocat"},
        ],
    }
    _write_jsonl(original, [_row("evt_a", ["cin_a"], "1000"), _row("evt_b", ["cin_b"], "1005"), untouched])
    _write_jsonl(preview, [untouched, merged])

    report = check_time_norm_recommended_canonical_apply_contract(
        effects_plan=_effects_plan(),
        merge_patch=_merge_patch(),
        recommendations=_recommendations(),
        policy_conflict_classification=_classification(),
        original_events_path=original,
        preview_events_path=preview,
        preview_output_check=_preview_output_check(),
    )

    assert report["contract_policy"] == "entity_resolution_time_norm_recommended_canonical_apply_contract_check"
    assert report["canonical_outputs_mutated"] is False
    assert report["ready_for_canonical_apply"] is False
    assert report["contract_valid"] is True
    assert report["validation_error_count"] == 0
    assert report["original_row_count"] == 3
    assert report["preview_row_count"] == 2
    assert report["untouched_hash_mismatch_count"] == 0
    assert report["suppressed_event_ids_present_in_preview"] == []
    assert report["replacement_event_ids_missing_from_preview"] == []


def test_time_norm_canonical_apply_contract_rejects_deferred_effect(tmp_path):
    original = tmp_path / "original.jsonl"
    preview = tmp_path / "preview.jsonl"
    _write_jsonl(original, [_row("evt_a", ["cin_a"], "1000"), _row("evt_b", ["cin_b"], "1005")])
    _write_jsonl(
        preview,
        [
            {
                **_row("evt_a", ["cin_a", "cin_b"], "1000"),
                "duplicate_record_count": 2,
                "dedupe_strategy": "entity_resolution_preview_merge",
                "entity_resolution_preview_merged_event_ids": ["evt_a", "evt_b"],
                "entity_resolution_preview_effect_ids": ["effect_1"],
            }
        ],
    )
    recommendations = _recommendations()
    recommendations["recommendations"][0]["recommendation"] = "needs_more_evidence"

    report = check_time_norm_recommended_canonical_apply_contract(
        effects_plan=_effects_plan(),
        merge_patch=_merge_patch(),
        recommendations=recommendations,
        policy_conflict_classification=_classification(),
        original_events_path=original,
        preview_events_path=preview,
        preview_output_check={"**": None, **_preview_output_check(), "row_count": 1},
    )

    assert report["contract_valid"] is False
    assert any(error["error"] == "deferred_recommendation_present_in_effects_plan" for error in report["validation_errors"])


def test_time_norm_canonical_apply_contract_rejects_unsafe_input():
    effects_plan = _effects_plan()
    effects_plan["canonical_outputs_mutated"] = True

    with pytest.raises(ValueError, match="canonical_outputs_mutated"):
        check_time_norm_recommended_canonical_apply_contract(
            effects_plan=effects_plan,
            merge_patch=_merge_patch(),
            recommendations=_recommendations(),
            policy_conflict_classification=_classification(),
            original_events_path="unused",
            preview_events_path="unused",
            preview_output_check=_preview_output_check(),
        )
