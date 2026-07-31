import json

import pytest

from scripts.build_time_norm_recommended_canonical_body_dry_run import (
    build_time_norm_recommended_canonical_body_dry_run,
)
from scripts.check_time_norm_recommended_canonical_body_dry_run import (
    check_time_norm_recommended_canonical_body_dry_run,
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
                "replacement_canonical_event_id": "evt_a",
                "merge_canonical_event_ids": ["evt_a", "evt_b"],
            }
        ],
    }


def _row(event_id, input_id, time_raw, summary):
    return {
        "canonical_event_id": event_id,
        "canonical_input_ids": [input_id],
        "canonical_input_id": input_id,
        "date_iso": "1954-09-19",
        "date_precision": "day",
        "time_raw": time_raw,
        "summary": summary,
        "description": summary,
        "lat": 1.0,
        "lon": 2.0,
        "source_provenance": [{"canonical_input_id": input_id, "source_name": "ufocat"}],
    }


def _write_jsonl(path, rows):
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_canonical_body_dry_run_builds_full_rows_and_check_accepts(tmp_path):
    events = tmp_path / "events.jsonl"
    _write_jsonl(
        events,
        [
            _row("evt_a", "cin_a", "1000", "Traces"),
            _row("evt_b", "cin_b", "1005", "Traces."),
        ],
    )

    rows, report = build_time_norm_recommended_canonical_body_dry_run(
        effects_plan=_effects_plan(),
        merge_patch=_merge_patch(),
        original_events_path=events,
    )

    assert report["dry_run_policy"] == "entity_resolution_time_norm_recommended_canonical_body_dry_run_only"
    assert report["canonical_outputs_mutated"] is False
    assert report["dry_run_row_count"] == 1
    assert report["conflict_field_counts"] == {"description": 1, "summary": 1, "time_raw": 1}
    row = rows[0]
    assert row["canonical_event_id"] == "evt_a"
    assert row["entity_resolution_canonical_replacement_event_id"] == "evt_a"
    assert row["entity_resolution_canonical_representative_event_id"] == "evt_b"
    assert row["canonical_input_ids"] == ["cin_a", "cin_b"]
    assert row["duplicate_record_count"] == 2
    assert row["entity_resolution_canonical_merge_conflicts"]["description"]["source_values"]

    check = check_time_norm_recommended_canonical_body_dry_run(
        dry_run_rows=rows,
        dry_run_report=report,
    )

    assert check["valid"] is True
    assert check["validation_error_count"] == 0
    assert check["incomplete_conflict_source_value_count"] == 0


def test_canonical_body_dry_run_check_rejects_empty_conflict_source_values():
    rows = [
        {
            "canonical_event_id": "evt_a",
            "canonical_input_ids": ["cin_a", "cin_b"],
            "duplicate_record_count": 2,
            "source_provenance": [
                {"canonical_input_id": "cin_a"},
                {"canonical_input_id": "cin_b"},
            ],
            "entity_resolution_canonical_merged_event_ids": ["evt_a", "evt_b"],
            "entity_resolution_canonical_effect_ids": ["effect_1"],
            "entity_resolution_canonical_merge_policy": "entity_resolution_cluster_canonical_merge_policy_proposal_v1",
            "entity_resolution_canonical_body_source_policy": "stable_replacement_id_with_highest_quality_representative_body",
            "entity_resolution_canonical_replacement_event_id": "evt_a",
            "entity_resolution_canonical_representative_event_id": "evt_a",
            "entity_resolution_canonical_merge_conflicts": {
                "description": {"values": ["one", "two"], "source_values": [], "source_value_count": 0}
            },
        }
    ]
    report = {
        "dry_run_policy": "entity_resolution_time_norm_recommended_canonical_body_dry_run_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "missing_event_id_count": 0,
        "dry_run_row_count": 1,
    }

    check = check_time_norm_recommended_canonical_body_dry_run(dry_run_rows=rows, dry_run_report=report)

    assert check["valid"] is False
    assert check["validation_errors"][0]["error"] == "incomplete_conflict_source_values"


def test_canonical_body_dry_run_rejects_unsafe_effects_plan(tmp_path):
    plan = _effects_plan()
    plan["canonical_outputs_mutated"] = True

    with pytest.raises(ValueError, match="canonical_outputs_mutated"):
        build_time_norm_recommended_canonical_body_dry_run(
            effects_plan=plan,
            merge_patch=_merge_patch(),
            original_events_path=tmp_path / "missing.jsonl",
        )
