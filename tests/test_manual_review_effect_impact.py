import json

from parser.utils import write_json
from scripts.summarize_manual_review_effect_impact import summarize_effect_impact


def _write_jsonl(path, records):
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def test_summarize_effect_impact_estimates_cross_event_merges(tmp_path):
    effects_plan = tmp_path / "effects_plan.json"
    deduped_events = tmp_path / "deduped_events.jsonl"

    write_json(
        effects_plan,
        {
            "effects": [
                {
                    "review_item_id": "rev_a",
                    "effect_id": "mre_a",
                    "planned_effect": "merge_duplicate_candidate",
                    "canonical_input_ids": ["cin_a", "cin_b"],
                },
                {
                    "review_item_id": "rev_b",
                    "effect_id": "mre_b",
                    "planned_effect": "defer_duplicate_candidate",
                    "canonical_input_ids": ["cin_c", "cin_d"],
                },
                {
                    "review_item_id": "rev_c",
                    "effect_id": "mre_c",
                    "planned_effect": "preserve_source_row",
                },
            ]
        },
    )
    _write_jsonl(
        deduped_events,
        [
            {"canonical_event_id": "ev_a", "canonical_input_ids": ["cin_a"]},
            {"canonical_event_id": "ev_b", "canonical_input_ids": ["cin_b"]},
            {"canonical_event_id": "ev_c", "canonical_input_ids": ["cin_c"]},
        ],
    )

    report = summarize_effect_impact(effects_plan_path=effects_plan, deduped_events_path=deduped_events)

    assert report["canonical_outputs_mutated"] is False
    assert report["preview_outputs_written"] is False
    assert report["required_input_id_count"] == 2
    assert report["matched_input_id_count"] == 2
    assert report["effect_counts"]["merge_duplicate_candidate"] == 1
    assert report["effect_counts"]["defer_duplicate_candidate"] == 1
    assert report["merge_impact"]["merge_effects_cross_event"] == 1
    assert report["merge_impact"]["projected_event_reduction"] == 1
    assert report["merge_samples"]["cross_event"][0]["event_ids"] == ["ev_a", "ev_b"]


def test_summarize_effect_impact_reports_missing_inputs(tmp_path):
    effects_plan = tmp_path / "effects_plan.json"
    deduped_events = tmp_path / "deduped_events.jsonl"

    write_json(
        effects_plan,
        {
            "effects": [
                {
                    "review_item_id": "rev_a",
                    "effect_id": "mre_a",
                    "planned_effect": "merge_duplicate_candidate",
                    "canonical_input_ids": ["cin_a", "cin_missing"],
                }
            ]
        },
    )
    _write_jsonl(deduped_events, [{"canonical_event_id": "ev_a", "canonical_input_ids": ["cin_a"]}])

    report = summarize_effect_impact(effects_plan_path=effects_plan, deduped_events_path=deduped_events)

    assert report["missing_input_id_count"] == 1
    assert report["merge_impact"]["merge_effects_with_missing_inputs"] == 1
    assert report["merge_samples"]["missing_inputs"][0]["missing_input_ids"] == ["cin_missing"]
