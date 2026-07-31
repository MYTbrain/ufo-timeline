import json

from scripts.apply_manual_review_effects import apply_manual_review_effects_preview, write_preview_outputs


def test_apply_preview_merges_reviewed_duplicate_without_mutating_input():
    original_events = [
        _event("evt_a", ["cin_a"], source="alpha.csv"),
        _event("evt_b", ["cin_b"], source="beta.csv"),
    ]
    plan = _plan(
        [
            {
                "effect_id": "mre_merge",
                "review_item_id": "rev_dup",
                "planned_effect": "merge_duplicate_candidate",
                "effect_policy": "plan_only",
                "effect_status": "planned_not_applied",
                "canonical_outputs_mutated": False,
                "canonical_input_ids": ["cin_a", "cin_b"],
            }
        ]
    )

    preview_events, report = apply_manual_review_effects_preview(
        effects_plan=plan,
        deduped_events=original_events,
    )

    assert len(preview_events) == 1
    assert preview_events[0]["canonical_input_ids"] == ["cin_a", "cin_b"]
    assert preview_events[0]["dedupe_strategy"] == "manual_review_preview_merge"
    assert report["canonical_outputs_mutated"] is False
    assert report["effects_applied"] == 1
    assert original_events[0]["canonical_input_ids"] == ["cin_a"]


def test_apply_preview_excludes_reviewed_source_row():
    events = [_event("evt_a", ["cin_a", "cin_b"], source="alpha.csv")]
    plan = _plan(
        [
            {
                "effect_id": "mre_exclude",
                "review_item_id": "rev_row",
                "planned_effect": "exclude_source_row",
                "effect_policy": "plan_only",
                "effect_status": "planned_not_applied",
                "canonical_outputs_mutated": False,
                "canonical_input_ids": ["cin_b"],
            }
        ]
    )

    preview_events, report = apply_manual_review_effects_preview(effects_plan=plan, deduped_events=events)

    assert preview_events[0]["canonical_input_ids"] == ["cin_a"]
    assert preview_events[0]["duplicate_record_count"] == 1
    assert report["effects_applied"] == 1
    assert report["applied_effects"][0]["planned_effect"] == "exclude_source_row"


def test_apply_preview_blocks_merge_when_input_is_also_excluded():
    events = [_event("evt_a", ["cin_a"], source="alpha.csv"), _event("evt_b", ["cin_b"], source="beta.csv")]
    plan = _plan(
        [
            {
                "effect_id": "mre_exclude",
                "review_item_id": "rev_row",
                "planned_effect": "exclude_source_row",
                "effect_policy": "plan_only",
                "effect_status": "planned_not_applied",
                "canonical_outputs_mutated": False,
                "canonical_input_ids": ["cin_b"],
            },
            {
                "effect_id": "mre_merge",
                "review_item_id": "rev_dup",
                "planned_effect": "merge_duplicate_candidate",
                "effect_policy": "plan_only",
                "effect_status": "planned_not_applied",
                "canonical_outputs_mutated": False,
                "canonical_input_ids": ["cin_a", "cin_b"],
            },
        ]
    )

    preview_events, report = apply_manual_review_effects_preview(effects_plan=plan, deduped_events=events)

    assert len(preview_events) == 1
    assert preview_events[0]["canonical_event_id"] == "evt_a"
    assert report["effects_blocked"] == 1
    assert report["blocked_effects"][0]["reason"] == "canonical_input_ids_also_excluded"


def test_write_preview_outputs_writes_shadow_files(tmp_path):
    output_dir = tmp_path / "preview"
    reports_dir = tmp_path / "reports"
    report = {
        "mode": "preview",
        "canonical_outputs_mutated": False,
        "preview_event_count": 1,
    }

    paths = write_preview_outputs(
        preview_events=[_event("evt_a", ["cin_a"], source="alpha.csv")],
        output_dir=output_dir,
        reports_dir=reports_dir,
        report=report,
    )

    assert (output_dir / "deduped_events.jsonl").exists()
    assert (output_dir / "normalized_events.json").exists()
    assert (output_dir / "map_events.json").exists()
    assert (output_dir / "manual_review_apply_preview_report.json").exists()
    assert (reports_dir / "manual_review_apply_preview_report.json").exists()
    assert paths["deduped_events"].endswith("deduped_events.jsonl")
    written_report = json.loads((reports_dir / "manual_review_apply_preview_report.json").read_text())
    assert written_report["canonical_outputs_mutated"] is False


def _plan(effects):
    return {
        "effect_policy": "plan_only",
        "canonical_outputs_mutated": False,
        "effects": effects,
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
