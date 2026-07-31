import json

import pytest

from scripts.promote_manual_review_medium_time_raw_only_review_to_decision_candidates import (
    PROMOTION_POLICY,
    build_medium_time_raw_only_decision_candidates,
)


def test_promotes_medium_time_raw_only_same_event_candidates(tmp_path):
    candidate_events = tmp_path / "candidate.jsonl"
    _write_jsonl(
        candidate_events,
        [
            {
                "canonical_event_id": "evt_a",
                "canonical_input_ids": ["cin_a", "cin_b"],
                "manual_review_preview": {
                    "merged_by_effect_ids": ["mre_a"],
                    "merged_canonical_event_ids": ["evt_a", "evt_b"],
                },
            }
        ],
    )

    candidates, report = build_medium_time_raw_only_decision_candidates(
        _review_report(_review_item("evt_a"), _review_item("evt_skip", recommendation="needs_more_evidence")),
        candidate_events_path=candidate_events,
        reviewed_at="2026-05-22T00:00:00Z",
    )

    assert report["promotion_policy"] == PROMOTION_POLICY
    assert report["decision_candidate_count"] == 1
    assert report["projected_event_reduction"] == 1
    candidate = candidates[0]
    assert candidate["decision"] == "same_event"
    assert candidate["effect_ids"] == ["mre_a"]
    assert candidate["merge_canonical_event_ids"] == ["evt_a", "evt_b"]
    assert candidate["canonical_input_ids"] == ["cin_a", "cin_b"]
    assert candidate["requires_explicit_apply_step"] is True


def test_promote_medium_time_raw_only_skips_missing_candidate_row(tmp_path):
    candidate_events = tmp_path / "candidate.jsonl"
    _write_jsonl(candidate_events, [])

    candidates, report = build_medium_time_raw_only_decision_candidates(
        _review_report(_review_item("evt_missing")),
        candidate_events_path=candidate_events,
    )

    assert candidates == []
    assert report["skipped_reason_counts"] == {"missing_replacement_candidate_row": 1}


def test_promote_medium_time_raw_only_rejects_unsafe_review_report(tmp_path):
    candidate_events = tmp_path / "candidate.jsonl"
    _write_jsonl(candidate_events, [])
    report = _review_report(_review_item("evt_a"))
    report["auto_merge_performed"] = True

    with pytest.raises(ValueError, match="auto_merge_performed"):
        build_medium_time_raw_only_decision_candidates(report, candidate_events_path=candidate_events)


def _review_report(*items):
    return {
        "review_policy": "manual_review_medium_time_raw_only_parser_review_v1",
        "canonical_outputs_mutated": False,
        "source_canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_runtime_promotion": False,
        "items": list(items),
    }


def _review_item(replacement_id, *, recommendation="source_review_same_event_candidate"):
    return {
        "replacement_event_id": replacement_id,
        "review_recommendation": recommendation,
        "confidence": "medium",
        "failed_conditions": [],
        "time_raw_values": ["2015", "2020"],
        "parsed_minutes": [1215, 1220],
        "exact_span_minutes": 5,
        "review_reason_codes": ["nearby_exact_times"],
        "date_iso_values": ["1983-03-24"],
        "location_raw_values": ["Yorktown, NY"],
        "source_file_values": ["ufocat2023.csv"],
        "component_event_ids": [replacement_id, "evt_b"],
    }


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
