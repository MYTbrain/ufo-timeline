import json

import pytest

from scripts.apply_time_norm_recommended_canonical_decisions import (
    apply_time_norm_recommended_canonical_decisions,
)


def _event(event_id, input_ids=None):
    input_ids = input_ids or [f"cin_{event_id}"]
    return {
        "canonical_event_id": event_id,
        "canonical_input_id": input_ids[0],
        "canonical_input_ids": input_ids,
        "dedupe_strategy": "single_record",
    }


def _write_jsonl(path, records):
    path.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records), encoding="utf-8")


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _effects_plan():
    return {
        "effect_policy": "entity_resolution_plan_only",
        "canonical_outputs_mutated": False,
        "canonical_outputs_mutated_by_plan": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "planned_effect_count": 1,
        "requires_explicit_apply_step_count": 1,
        "warnings": [],
        "effects": [
            {
                "effect_id": "ere_1",
                "planned_effect": "merge_entity_resolution_candidate",
                "requires_explicit_apply_step": True,
                "merge_canonical_event_ids": ["evt_a", "evt_b"],
            }
        ],
    }


def _dry_run_row():
    row = _event("evt_a", ["cin_a", "cin_b"])
    row.update(
        {
            "dedupe_strategy": "entity_resolution_canonical_body_dry_run_merge",
            "duplicate_record_count": 2,
            "entity_resolution_canonical_replacement_event_id": "evt_a",
            "entity_resolution_canonical_merged_event_ids": ["evt_a", "evt_b"],
            "entity_resolution_canonical_effect_ids": ["ere_1"],
            "entity_resolution_canonical_merge_conflicts": {
                "time_raw": {
                    "source_value_count": 2,
                    "source_values": [
                        {"canonical_event_id": "evt_a", "value": "1000"},
                        {"canonical_event_id": "evt_b", "value": "1005"},
                    ],
                    "values": ["1000", "1005"],
                }
            },
        }
    )
    return row


def _dry_run_check():
    return {
        "check_policy": "entity_resolution_time_norm_recommended_canonical_body_dry_run_check",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "valid": True,
        "dry_run_row_count": 1,
        "validation_error_count": 0,
        "incomplete_conflict_source_value_count": 0,
    }


def test_time_norm_recommended_canonical_apply_streams_candidate_output(tmp_path):
    source = tmp_path / "deduped_events.jsonl"
    output = tmp_path / "candidate" / "deduped_events.jsonl"
    _write_jsonl(source, [_event("evt_a"), _event("evt_b"), _event("evt_c")])

    report = apply_time_norm_recommended_canonical_decisions(
        accepted_effects_plan=_effects_plan(),
        dry_run_rows=[_dry_run_row()],
        dry_run_check=_dry_run_check(),
        deduped_events_path=source,
        output_events_path=output,
    )

    rows = _read_jsonl(output)
    assert report["apply_policy"] == "entity_resolution_time_norm_recommended_stream_apply_v1"
    assert report["canonical_outputs_mutated"] is False
    assert report["canonical_candidate_output_written"] is True
    assert report["input_event_count"] == 3
    assert report["output_event_count"] == 2
    assert report["replacement_rows_written"] == 1
    assert report["suppressed_rows_skipped"] == 1
    assert report["projected_event_reduction"] == 1
    assert [row["canonical_event_id"] for row in rows] == ["evt_a", "evt_c"]
    assert rows[0]["dedupe_strategy"] == "entity_resolution_canonical_body_dry_run_merge"
    assert rows[0]["canonical_input_ids"] == ["cin_a", "cin_b"]


def test_time_norm_recommended_canonical_apply_refuses_to_overwrite_source(tmp_path):
    source = tmp_path / "deduped_events.jsonl"
    _write_jsonl(source, [_event("evt_a")])

    with pytest.raises(ValueError, match="same as the source"):
        apply_time_norm_recommended_canonical_decisions(
            accepted_effects_plan=_effects_plan(),
            dry_run_rows=[_dry_run_row()],
            dry_run_check=_dry_run_check(),
            deduped_events_path=source,
            output_events_path=source,
        )


def test_time_norm_recommended_canonical_apply_rejects_effect_mismatch(tmp_path):
    source = tmp_path / "deduped_events.jsonl"
    output = tmp_path / "candidate" / "deduped_events.jsonl"
    _write_jsonl(source, [_event("evt_a"), _event("evt_b")])
    row = _dry_run_row()
    row["entity_resolution_canonical_effect_ids"] = ["ere_other"]

    with pytest.raises(ValueError, match="effect IDs"):
        apply_time_norm_recommended_canonical_decisions(
            accepted_effects_plan=_effects_plan(),
            dry_run_rows=[row],
            dry_run_check=_dry_run_check(),
            deduped_events_path=source,
            output_events_path=output,
        )
