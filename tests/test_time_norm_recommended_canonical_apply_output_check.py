import json

import pytest

from scripts.check_time_norm_recommended_canonical_apply_output import (
    check_time_norm_recommended_canonical_apply_output,
)


def _row(event_id, input_ids=None):
    input_ids = input_ids or [f"cin_{event_id}"]
    return {
        "canonical_event_id": event_id,
        "canonical_input_ids": input_ids,
    }


def _dry_row():
    row = _row("evt_a", ["cin_a", "cin_b"])
    row["entity_resolution_canonical_merged_event_ids"] = ["evt_a", "evt_b"]
    return row


def _write_jsonl(path, records):
    path.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records), encoding="utf-8")


def _apply_report():
    return {
        "apply_policy": "entity_resolution_time_norm_recommended_stream_apply_v1",
        "canonical_outputs_mutated": False,
        "source_canonical_outputs_mutated": False,
        "canonical_candidate_output_written": True,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "ready_for_runtime_promotion": False,
        "valid": True,
        "validation_error_count": 0,
        "expected_output_event_count": 2,
    }


def test_time_norm_recommended_canonical_apply_output_check_accepts_valid_output(tmp_path):
    output = tmp_path / "deduped_events.jsonl"
    _write_jsonl(output, [_dry_row(), _row("evt_c")])

    report = check_time_norm_recommended_canonical_apply_output(
        apply_report=_apply_report(),
        apply_events_path=output,
        dry_run_rows=[_dry_row()],
        dry_run_rows_path=tmp_path / "custom_dry_run.jsonl",
    )

    assert report["check_policy"] == "entity_resolution_time_norm_recommended_canonical_apply_output_check"
    assert report["inputs"]["dry_run_rows"].endswith("custom_dry_run.jsonl")
    assert report["canonical_outputs_mutated"] is False
    assert report["valid"] is True
    assert report["row_count"] == 2
    assert report["replacement_rows_found"] == 1
    assert report["suppressed_ids_found"] == 0


def test_time_norm_recommended_canonical_apply_output_check_rejects_suppressed_id(tmp_path):
    output = tmp_path / "deduped_events.jsonl"
    _write_jsonl(output, [_dry_row(), _row("evt_b")])

    report = check_time_norm_recommended_canonical_apply_output(
        apply_report=_apply_report(),
        apply_events_path=output,
        dry_run_rows=[_dry_row()],
    )

    assert report["valid"] is False
    assert any(error["error"] == "suppressed_ids_still_present" for error in report["validation_errors"])


def test_time_norm_recommended_canonical_apply_output_check_rejects_unsafe_report(tmp_path):
    output = tmp_path / "deduped_events.jsonl"
    _write_jsonl(output, [_dry_row(), _row("evt_c")])
    apply_report = _apply_report()
    apply_report["canonical_candidate_output_written"] = False

    with pytest.raises(ValueError, match="canonical_candidate_output_written"):
        check_time_norm_recommended_canonical_apply_output(
            apply_report=apply_report,
            apply_events_path=output,
            dry_run_rows=[_dry_row()],
        )
