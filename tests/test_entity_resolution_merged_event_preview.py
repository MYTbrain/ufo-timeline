import json

import pytest

from scripts.build_entity_resolution_merged_event_preview import build_entity_resolution_merged_event_preview


def _write_jsonl(path, records):
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def _safe_patch(patches):
    return {
        "patch_policy": "entity_resolution_merge_patch_preview_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "patches": patches,
    }


def _patch(event_ids=None):
    return {
        "patch_id": "er_merge_patch_000001",
        "effect_id": "ere_1",
        "review_item_id": "er_review_1",
        "merge_canonical_event_ids": event_ids or ["evt_a", "evt_b"],
        "projected_event_reduction": 1,
    }


def _event(event_id, input_id, *, summary="same", type_normalized="light"):
    return {
        "canonical_event_id": event_id,
        "canonical_input_id": input_id,
        "canonical_input_ids": [input_id],
        "duplicate_record_count": 1,
        "dedupe_strategy": "single_record",
        "date_iso": "1995-08-18",
        "time_raw": "2300",
        "location_raw": "REVIN",
        "summary": summary,
        "type_normalized": type_normalized,
        "source_provenance": [{"canonical_input_id": input_id}],
    }


def test_build_entity_resolution_merged_event_preview_hydrates_patch_rows(tmp_path):
    deduped_events = tmp_path / "deduped_events.jsonl"
    _write_jsonl(
        deduped_events,
        [
            _event("evt_a", "cin_a", summary="Triangle"),
            _event("evt_b", "cin_b", summary="Triangle with lights"),
            _event("evt_c", "cin_c"),
        ],
    )

    report = build_entity_resolution_merged_event_preview(
        merge_patch=_safe_patch([_patch()]),
        deduped_events_path=deduped_events,
    )

    preview = report["previews"][0]
    assert report["canonical_outputs_mutated"] is False
    assert report["preview_outputs_written"] is False
    assert report["required_event_id_count"] == 2
    assert report["hydrated_event_count"] == 2
    assert report["missing_event_id_count"] == 0
    assert preview["preview_event"]["dedupe_strategy"] == "entity_resolution_preview_merge"
    assert preview["preview_event"]["canonical_input_ids"] == ["cin_a", "cin_b"]
    assert preview["preview_event"]["duplicate_record_count"] == 2
    assert preview["field_conflicts"]["summary"] == ["Triangle", "Triangle with lights"]


def test_build_entity_resolution_merged_event_preview_reports_missing_events(tmp_path):
    deduped_events = tmp_path / "deduped_events.jsonl"
    _write_jsonl(deduped_events, [_event("evt_a", "cin_a")])

    report = build_entity_resolution_merged_event_preview(
        merge_patch=_safe_patch([_patch(["evt_a", "evt_missing"])]),
        deduped_events_path=deduped_events,
    )

    assert report["missing_event_id_count"] == 1
    assert report["patches_with_missing_events"] == 1
    assert report["previews"][0]["preview_event"] is None
    assert report["previews"][0]["missing_event_ids"] == ["evt_missing"]


def test_build_entity_resolution_merged_event_preview_rejects_unsafe_patch(tmp_path):
    deduped_events = tmp_path / "deduped_events.jsonl"
    _write_jsonl(deduped_events, [])
    unsafe_patch = _safe_patch([])
    unsafe_patch["canonical_outputs_mutated"] = True

    with pytest.raises(ValueError, match="merge patch is not safe to preview"):
        build_entity_resolution_merged_event_preview(
            merge_patch=unsafe_patch,
            deduped_events_path=deduped_events,
        )
