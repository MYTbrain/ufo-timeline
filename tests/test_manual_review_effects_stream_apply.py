import json

import pytest

from scripts.apply_manual_review_effects_stream import apply_manual_review_effects_stream


def test_stream_apply_merges_connected_components_without_mutating_source(tmp_path):
    source = tmp_path / "deduped_events.jsonl"
    output = tmp_path / "candidate" / "deduped_events.jsonl"
    events = [
        _event("evt_a", ["cin_a"], source="alpha.csv"),
        _event("evt_b", ["cin_b"], source="beta.csv"),
        _event("evt_c", ["cin_c"], source="gamma.csv"),
        _event("evt_d", ["cin_d"], source="delta.csv"),
    ]
    _write_jsonl(source, events)

    report = apply_manual_review_effects_stream(
        effects_plan=_plan(
            [
                _merge("mre_ab", "rev_ab", ["cin_a", "cin_b"]),
                _merge("mre_bc", "rev_bc", ["cin_b", "cin_c"]),
            ]
        ),
        deduped_events_path=source,
        output_events_path=output,
    )

    written = _read_jsonl(output)
    merged = next(event for event in written if event["canonical_event_id"] == "evt_a")
    assert report["valid"] is True
    assert report["actual_event_reduction"] == 2
    assert report["merge_components"] == 1
    assert report["input_event_count"] == 4
    assert report["output_event_count"] == 2
    assert [event["canonical_event_id"] for event in written] == ["evt_a", "evt_d"]
    assert merged["canonical_input_ids"] == ["cin_a", "cin_b", "cin_c"]
    assert merged["dedupe_strategy"] == "manual_review_stream_preview_merge"
    assert merged["manual_review_preview"]["merged_by_effect_ids"] == ["mre_ab", "mre_bc"]
    assert events[0]["canonical_input_ids"] == ["cin_a"]


def test_stream_apply_blocks_missing_inputs_and_keeps_source_when_invalid(tmp_path):
    source = tmp_path / "deduped_events.jsonl"
    output = tmp_path / "candidate" / "deduped_events.jsonl"
    _write_jsonl(source, [_event("evt_a", ["cin_a"], source="alpha.csv")])

    report = apply_manual_review_effects_stream(
        effects_plan=_plan([_merge("mre_missing", "rev_missing", ["cin_a", "cin_missing"])]),
        deduped_events_path=source,
        output_events_path=output,
    )

    assert report["valid"] is True
    assert report["missing_input_id_count"] == 1
    assert report["merge_effects_with_missing_inputs"] == 1
    assert report["actual_event_reduction"] == 0
    assert _read_jsonl(output)[0]["canonical_event_id"] == "evt_a"


def test_stream_apply_refuses_to_overwrite_source(tmp_path):
    source = tmp_path / "deduped_events.jsonl"
    _write_jsonl(source, [_event("evt_a", ["cin_a"], source="alpha.csv")])

    with pytest.raises(ValueError, match="output path must not be the same"):
        apply_manual_review_effects_stream(
            effects_plan=_plan([]),
            deduped_events_path=source,
            output_events_path=source,
        )


def _plan(effects):
    return {
        "schema_version": 1,
        "effect_policy": "plan_only",
        "canonical_outputs_mutated": False,
        "canonical_outputs_mutated_by_plan": False,
        "planned_effect_count": len(effects),
        "effects": effects,
    }


def _merge(effect_id, review_item_id, canonical_input_ids):
    return {
        "effect_id": effect_id,
        "review_item_id": review_item_id,
        "planned_effect": "merge_duplicate_candidate",
        "effect_policy": "plan_only",
        "effect_status": "planned_not_applied",
        "canonical_outputs_mutated": False,
        "canonical_input_ids": canonical_input_ids,
    }


def _event(event_id, canonical_input_ids, *, source):
    return {
        "canonical_event_id": event_id,
        "canonical_input_id": canonical_input_ids[0],
        "canonical_input_ids": canonical_input_ids,
        "source_name": "test",
        "source_file": source,
        "source_row_number": 1,
        "source_row_hash": event_id,
        "date_raw": "1952-07-19",
        "date_iso": "1952-07-19",
        "sort_date_iso": "1952-07-19",
        "date_precision": "exact_day",
        "location_raw": "Washington, DC",
        "description": f"Test event {event_id}",
        "duplicate_record_count": len(canonical_input_ids),
        "dedupe_strategy": "single_record",
        "source_provenance": [
            {
                "canonical_input_id": input_id,
                "source_file": source,
                "source_row_number": index + 1,
            }
            for index, input_id in enumerate(canonical_input_ids)
        ],
        "raw_source_row": {"id": json.dumps(canonical_input_ids)},
    }


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
