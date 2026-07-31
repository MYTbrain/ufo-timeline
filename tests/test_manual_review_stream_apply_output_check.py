import json

from scripts.check_manual_review_stream_apply_output import check_manual_review_stream_apply_output


def test_check_manual_review_stream_apply_output_accepts_valid_candidate(tmp_path):
    events_path = tmp_path / "deduped_events.jsonl"
    _write_jsonl(events_path, [_replacement_event("evt_a", ["cin_a", "cin_b"])])

    report = check_manual_review_stream_apply_output(
        apply_report=_apply_report(row_count=1, replacements=["evt_a"], suppressed=["evt_b"]),
        apply_events_path=events_path,
    )

    assert report["valid"] is True
    assert report["row_count"] == 1
    assert report["replacement_rows_found"] == 1
    assert report["suppressed_ids_found"] == 0


def test_check_manual_review_stream_apply_output_rejects_suppressed_and_invalid_replacement(tmp_path):
    events_path = tmp_path / "deduped_events.jsonl"
    invalid = _replacement_event("evt_a", ["cin_a", "cin_b"])
    invalid["duplicate_record_count"] = 1
    _write_jsonl(events_path, [invalid, _event("evt_b", ["cin_c"])])

    report = check_manual_review_stream_apply_output(
        apply_report=_apply_report(row_count=2, replacements=["evt_a"], suppressed=["evt_b"]),
        apply_events_path=events_path,
    )

    assert report["valid"] is False
    assert {error["error"] for error in report["validation_errors"]} == {
        "suppressed_ids_still_present",
        "invalid_replacement_rows",
    }


def _apply_report(*, row_count, replacements, suppressed):
    return {
        "apply_policy": "manual_review_effects_stream_preview_v1",
        "canonical_outputs_mutated": False,
        "source_canonical_outputs_mutated": False,
        "canonical_candidate_output_written": True,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "valid": True,
        "output_event_count": row_count,
        "replacement_event_ids": replacements,
        "suppressed_event_ids": suppressed,
    }


def _replacement_event(event_id, input_ids):
    event = _event(event_id, input_ids)
    event["dedupe_strategy"] = "manual_review_stream_preview_merge"
    event["manual_review_preview"] = {
        "apply_policy": "manual_review_effects_stream_preview_v1",
        "merged_canonical_event_ids": [event_id, "evt_b"],
        "merged_by_effect_ids": ["mre_1"],
    }
    return event


def _event(event_id, input_ids):
    return {
        "canonical_event_id": event_id,
        "canonical_input_ids": input_ids,
        "duplicate_record_count": len(input_ids),
        "source_provenance": [{"canonical_input_id": input_id} for input_id in input_ids],
    }


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
