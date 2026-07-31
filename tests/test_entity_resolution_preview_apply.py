import json

from scripts.preview_entity_resolution_apply import preview_entity_resolution_apply


def _event(event_id, input_ids):
    return {
        "canonical_event_id": event_id,
        "canonical_input_id": input_ids[0],
        "canonical_input_ids": input_ids,
        "duplicate_record_count": len(input_ids),
        "dedupe_strategy": "single_record",
        "source_provenance": [{"canonical_input_id": input_id} for input_id in input_ids],
    }


def _write_jsonl(path, records):
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _plan(effects):
    return {
        "effect_policy": "entity_resolution_plan_only",
        "canonical_outputs_mutated": False,
        "effects": effects,
    }


def _merge_effect(effect_id="ere_1", event_ids=None):
    event_ids = event_ids or ["evt_a", "evt_b"]
    return {
        "effect_id": effect_id,
        "review_item_id": f"review_{effect_id}",
        "planned_effect": "merge_entity_resolution_candidate",
        "merge_canonical_event_ids": event_ids,
        "canonical_input_ids": ["cin_a", "cin_b"],
    }


def test_preview_entity_resolution_apply_streams_shadow_merge_output(tmp_path):
    deduped_events = tmp_path / "deduped_events.jsonl"
    output_dir = tmp_path / "preview"
    _write_jsonl(
        deduped_events,
        [
            _event("evt_a", ["cin_a"]),
            _event("evt_b", ["cin_b"]),
            _event("evt_c", ["cin_c"]),
        ],
    )

    report = preview_entity_resolution_apply(
        effects_plan=_plan([_merge_effect()]),
        deduped_events_path=deduped_events,
        output_dir=output_dir,
    )

    preview_events = _read_jsonl(output_dir / "deduped_events.jsonl")
    assert report["canonical_outputs_mutated"] is False
    assert report["preview_outputs_written"] is True
    assert report["input_event_count"] == 3
    assert report["preview_event_count"] == 2
    assert report["projected_event_reduction"] == 1
    merged = [event for event in preview_events if event["dedupe_strategy"] == "entity_resolution_preview_merge"][0]
    assert merged["canonical_input_ids"] == ["cin_a", "cin_b"]
    assert merged["duplicate_record_count"] == 2
    assert merged["entity_resolution_preview_merged_event_ids"] == ["evt_a", "evt_b"]


def test_preview_entity_resolution_apply_noops_without_copying_when_no_effects(tmp_path):
    deduped_events = tmp_path / "deduped_events.jsonl"
    output_dir = tmp_path / "preview"
    _write_jsonl(deduped_events, [_event("evt_a", ["cin_a"])])

    report = preview_entity_resolution_apply(
        effects_plan=_plan([]),
        deduped_events_path=deduped_events,
        output_dir=output_dir,
    )

    assert report["preview_outputs_written"] is False
    assert not (output_dir / "deduped_events.jsonl").exists()
    assert report["effects_requested"] == 0


def test_preview_entity_resolution_apply_blocks_missing_event_ids(tmp_path):
    deduped_events = tmp_path / "deduped_events.jsonl"
    output_dir = tmp_path / "preview"
    _write_jsonl(deduped_events, [_event("evt_a", ["cin_a"])])

    report = preview_entity_resolution_apply(
        effects_plan=_plan([_merge_effect(event_ids=["evt_a", "evt_missing"])]),
        deduped_events_path=deduped_events,
        output_dir=output_dir,
    )

    preview_events = _read_jsonl(output_dir / "deduped_events.jsonl")
    assert report["effects_blocked"] == 1
    assert report["blocked_effects"][0]["missing_event_ids"] == ["evt_missing"]
    assert preview_events == [_event("evt_a", ["cin_a"])]
