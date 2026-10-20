"""Reviewed date withholding is source-specific and preserves original claims."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from parser.canonical_export import canonical_event_to_normalized_event
from parser.csv_sources.mufon import MufonPyAdapter
from parser.dedupe import SUPPORTED_DEDUPE_STRATEGIES, build_deduped_events
from parser.reviewed_event_corrections import (
    MUFON_DATE_REVIEW_FIELDS,
    MUFON_DATE_REVIEW_ID,
    MUFON_DATE_REVIEW_TARGETS,
    apply_reviewed_event_corrections,
)
from scripts.build_canonical_web_artifacts import (
    StableEventIdAllocator,
    compact_summary_event,
    compact_web_event,
)


FIXTURES = json.loads((Path(__file__).resolve().parents[1] /
                      "docs/qa/mufon-date-review-20261019/fixtures.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda item: item["source_native_id"])
def test_actual_reviewed_details_withhold_dates_and_preserve_source(fixture):
    original = deepcopy(fixture["detail"])
    before = deepcopy(original)
    corrected = apply_reviewed_event_corrections(original)
    assert original == before
    for key, expected in MUFON_DATE_REVIEW_FIELDS.items():
        assert corrected[key] == expected
    for key in ("event_id", "canonical_event_id", "canonical_input_ids", "source_provenance", "source_id",
                "date_raw", "time_raw", "reported_date_raw", "description", "raw_fields", "raw_source_row"):
        assert corrected.get(key) == before.get(key), key
    assert corrected["date_review"]["review_id"] == MUFON_DATE_REVIEW_ID
    assert apply_reviewed_event_corrections(corrected) == corrected


@pytest.mark.parametrize("strategy", sorted(SUPPORTED_DEDUPE_STRATEGIES))
def test_correction_runs_after_real_dedupe_without_changing_event_identity(strategy):
    adapter = MufonPyAdapter()
    inputs = []
    for fixture in FIXTURES:
        guard = fixture["source_guard"]
        record = adapter.row_to_record(fixture["detail"]["raw_fields"],
                                       source_row_number=guard["source_row_number"],
                                       source_row_hash_value=guard["source_row_hash"])
        assert record.canonical_input_id == guard["canonical_input_id"]
        inputs.append(record)
    events, _ = build_deduped_events(inputs, strategy=strategy)
    assert len(events) == 5
    for event in events:
        corrected = apply_reviewed_event_corrections(event)
        assert corrected["canonical_event_id"] == event["canonical_event_id"]
        assert corrected["canonical_input_ids"] == event["canonical_input_ids"]
        assert corrected["date_iso"] is None
        assert corrected["sort_date_iso"] is None
        assert corrected["date_precision"] == "unknown"
        assert corrected["date_raw"] == "1890-04-01"
        assert corrected["reported_date_raw"] == event["reported_date_raw"]


@pytest.mark.parametrize("field,value", [
    ("source_file", "different.csv"), ("source", "nuforc"), ("source_id", "wrong"),
    ("source_row_number", 1), ("source_row_hash", "0" * 40),
    ("canonical_input_id", "cin_changed"),
    ("date_raw", "1890-04-02"), ("time_raw", "1:00AM"),
    ("date_iso", "1990-04-01"), ("date_precision", "year"),
])
def test_review_fails_closed_on_changed_source_or_existing_projection(field, value):
    event = deepcopy(FIXTURES[0]["detail"])
    event[field] = value
    with pytest.raises(ValueError, match="stale-source guard"):
        apply_reviewed_event_corrections(event)


def test_review_fails_closed_on_changed_source_member_hash():
    event = deepcopy(FIXTURES[0]["detail"])
    event["source_provenance"][0]["source_row_hash"] = "0" * 40
    with pytest.raises(ValueError, match="source_row_hash"):
        apply_reviewed_event_corrections(event)


def test_review_fails_closed_on_new_primary_merge_topology():
    event = deepcopy(FIXTURES[0]["detail"])
    event["canonical_input_ids"].append("cin_other")
    event["duplicate_record_count"] = 2
    event["dedupe_strategy"] = "maximal_v3_auto_merge"
    with pytest.raises(ValueError, match="stale-source guard"):
        apply_reviewed_event_corrections(event)


def test_reviewed_input_as_non_primary_member_cannot_overwrite_representative_date():
    event = deepcopy(FIXTURES[0]["detail"])
    event.update(canonical_input_id="cin_other", source="nuforc", source_id="other",
                 canonical_input_ids=["cin_other", event["canonical_input_ids"][0]],
                 duplicate_record_count=2, dedupe_strategy="maximal_v3_auto_merge")
    corrected = apply_reviewed_event_corrections(event)
    assert corrected["date_iso"] == "1890-04-01"
    assert corrected["sort_date_iso"] == "1890-04-01"
    assert "date_review" not in corrected


def test_same_source_date_on_unreviewed_row_is_not_a_blanket_sentinel_rule():
    event = deepcopy(FIXTURES[0]["detail"])
    event["source_id"] = "unreviewed"
    event["canonical_input_ids"] = ["cin_unreviewed"]
    event["source_provenance"][0].update(canonical_input_id="cin_unreviewed", source_native_id="unreviewed")
    corrected = apply_reviewed_event_corrections(event)
    assert corrected["date_iso"] == "1890-04-01"
    assert corrected["date_precision"] == "exact_day"
    assert "date_review" not in corrected


def test_normalized_export_retains_raw_date_submission_and_review():
    fixture = FIXTURES[0]
    guard = fixture["source_guard"]
    record = MufonPyAdapter().row_to_record(fixture["detail"]["raw_fields"],
                                           source_row_number=guard["source_row_number"],
                                           source_row_hash_value=guard["source_row_hash"])
    events, _ = build_deduped_events([record])
    corrected = apply_reviewed_event_corrections(events[0])
    normalized = canonical_event_to_normalized_event(corrected)
    assert normalized["date_iso"] is None
    assert normalized["end_date_iso"] is None
    assert normalized["sort_date_iso"] is None
    assert normalized["date_precision"] == "unknown"
    assert normalized["date_raw"] == "1890-04-01"
    assert normalized["date_review"] == MUFON_DATE_REVIEW_FIELDS["date_review"]
    assert normalized["reported_date_raw"] == fixture["detail"]["reported_date_raw"]
    assert set(MUFON_DATE_REVIEW_TARGETS) == {item["source_native_id"] for item in FIXTURES}


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda item: item["source_native_id"])
def test_actual_compact_web_and_summary_exports_keep_review_and_unknown_chronology(fixture):
    original = deepcopy(fixture["detail"])
    corrected = apply_reviewed_event_corrections(original)
    compact = compact_web_event(corrected, event_id_allocator=StableEventIdAllocator())
    summary = compact_summary_event(compact)
    for event in (compact, summary):
        assert event["event_id"] == original["event_id"]
        assert event.get("date_iso") is None
        assert event.get("end_date_iso") is None
        assert event.get("sort_date_iso") is None
        assert event["date_precision"] == "unknown"
        assert event["date_raw"] == original["date_raw"]
        assert event["time_raw"] == original["time_raw"]
        assert event["date_review"] == MUFON_DATE_REVIEW_FIELDS["date_review"]
        assert event["exact_day_eligible"] is False
        assert event["time_sort_kind"] == "unknown"
        assert event["time_sort_confidence"] == "none"
        assert event["playback_sort_confidence"] == "none"
        assert event["playback_sort_key"][0] == 3
        assert event["playback_sort_key"][1:3] == [None, None]
        assert event.get("estimated_utc_timestamp_ms") is None
    assert compact["canonical_event_id"] == original["canonical_event_id"]
    assert compact["canonical_input_ids"] == original["canonical_input_ids"]
    assert original == fixture["detail"]
