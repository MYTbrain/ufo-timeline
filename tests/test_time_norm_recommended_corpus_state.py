import json
from pathlib import Path

from scripts.check_time_norm_recommended_corpus_state import (
    APPLIED_STATE,
    CONFLICT_STATE,
    check_time_norm_recommended_corpus_state,
)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def base_effects_plan() -> dict:
    return {
        "effect_policy": "entity_resolution_plan_only",
        "canonical_outputs_mutated": False,
        "canonical_outputs_mutated_by_plan": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "effects": [
            {
                "effect_id": "effect-1",
                "review_item_id": "review-1",
                "planned_effect": "merge_entity_resolution_candidate",
                "merge_canonical_event_ids": ["evt-a", "evt-b"],
            }
        ],
    }


def base_merge_patch() -> dict:
    return {
        "patch_policy": "entity_resolution_merge_patch_preview_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "patches": [
            {
                "effect_id": "effect-1",
                "replacement_canonical_event_id": "evt-a",
                "merge_canonical_event_ids": ["evt-a", "evt-b"],
            }
        ],
    }


def test_corpus_state_detects_already_applied_merge(tmp_path):
    corpus = tmp_path / "deduped_events.jsonl"
    write_jsonl(
        corpus,
        [
            {
                "canonical_event_id": "evt-a",
                "entity_resolution_canonical_merged_event_ids": ["evt-a", "evt-b"],
                "entity_resolution_canonical_effect_ids": ["effect-1"],
                "dedupe_strategy": "entity_resolution_canonical_body_dry_run_merge",
            }
        ],
    )

    report = check_time_norm_recommended_corpus_state(
        effects_plan=base_effects_plan(),
        merge_patch=base_merge_patch(),
        deduped_events_path=corpus,
    )

    assert report["valid"] is True
    assert report["ready_for_runtime_promotion"] is True
    assert report["candidate_output_needed"] is False
    assert report["state_counts"] == {APPLIED_STATE: 1}


def test_corpus_state_flags_partial_conflict_when_suppressed_row_remains(tmp_path):
    corpus = tmp_path / "deduped_events.jsonl"
    write_jsonl(
        corpus,
        [
            {
                "canonical_event_id": "evt-a",
                "entity_resolution_canonical_merged_event_ids": ["evt-a", "evt-b"],
                "entity_resolution_canonical_effect_ids": ["effect-1"],
            },
            {"canonical_event_id": "evt-b"},
        ],
    )

    report = check_time_norm_recommended_corpus_state(
        effects_plan=base_effects_plan(),
        merge_patch=base_merge_patch(),
        deduped_events_path=corpus,
    )

    assert report["valid"] is False
    assert report["ready_for_runtime_promotion"] is False
    assert report["state_counts"] == {CONFLICT_STATE: 1}
    assert report["effect_states"][0]["present_suppressed_ids"] == ["evt-b"]
