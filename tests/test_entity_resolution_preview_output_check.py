import json

import pytest

from scripts.check_entity_resolution_preview_output import check_entity_resolution_preview_output


def _write_jsonl(path, records):
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def _safe_report(preview_event_count=2, effects_applied=1):
    return {
        "apply_policy": "entity_resolution_stream_preview_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": True,
        "preview_event_count": preview_event_count,
        "effects_applied": effects_applied,
    }


def test_check_entity_resolution_preview_output_validates_counts(tmp_path):
    preview_events = tmp_path / "deduped_events.jsonl"
    _write_jsonl(
        preview_events,
        [
            {
                "canonical_event_id": "evt_a",
                "dedupe_strategy": "entity_resolution_preview_merge",
                "entity_resolution_preview_merged_event_ids": ["evt_a", "evt_b"],
                "canonical_input_ids": ["cin_a", "cin_b"],
            },
            {"canonical_event_id": "evt_c", "dedupe_strategy": "single_record"},
        ],
    )

    report = check_entity_resolution_preview_output(
        preview_report=_safe_report(),
        preview_events_path=preview_events,
    )

    assert report["canonical_outputs_mutated"] is False
    assert report["valid"] is True
    assert report["row_count"] == 2
    assert report["preview_merge_count"] == 1
    assert report["validation_errors"] == []


def test_check_entity_resolution_preview_output_allows_multiple_effects_per_merged_row(tmp_path):
    preview_events = tmp_path / "deduped_events.jsonl"
    _write_jsonl(
        preview_events,
        [
            {
                "canonical_event_id": "evt_a",
                "dedupe_strategy": "entity_resolution_preview_merge",
                "entity_resolution_preview_merged_event_ids": ["evt_a", "evt_b", "evt_c"],
                "canonical_input_ids": ["cin_a", "cin_b", "cin_c"],
            },
            {"canonical_event_id": "evt_d", "dedupe_strategy": "single_record"},
        ],
    )
    report_payload = _safe_report(preview_event_count=2, effects_applied=2)
    report_payload["applied_effects"] = [
        {"effect_id": "effect_1", "preview_canonical_event_id": "evt_a"},
        {"effect_id": "effect_2", "preview_canonical_event_id": "evt_a"},
    ]

    report = check_entity_resolution_preview_output(
        preview_report=report_payload,
        preview_events_path=preview_events,
    )

    assert report["valid"] is True
    assert report["effects_applied"] == 2
    assert report["expected_preview_merge_count"] == 1
    assert report["preview_merge_count"] == 1


def test_check_entity_resolution_preview_output_reports_mismatches(tmp_path):
    preview_events = tmp_path / "deduped_events.jsonl"
    _write_jsonl(preview_events, [{"canonical_event_id": "evt_a"}, {"canonical_event_id": "evt_a"}])

    report = check_entity_resolution_preview_output(
        preview_report=_safe_report(preview_event_count=3, effects_applied=1),
        preview_events_path=preview_events,
    )

    assert report["valid"] is False
    assert {error["error"] for error in report["validation_errors"]} == {
        "preview_event_count_mismatch",
        "preview_merge_count_mismatch",
        "duplicate_canonical_event_ids",
    }


def test_check_entity_resolution_preview_output_rejects_unsafe_report(tmp_path):
    preview_events = tmp_path / "deduped_events.jsonl"
    _write_jsonl(preview_events, [])
    unsafe_report = _safe_report()
    unsafe_report["canonical_outputs_mutated"] = True

    with pytest.raises(ValueError, match="preview report is not safe"):
        check_entity_resolution_preview_output(
            preview_report=unsafe_report,
            preview_events_path=preview_events,
        )
