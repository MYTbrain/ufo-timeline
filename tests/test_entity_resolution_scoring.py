import json

from scripts.score_entity_resolution_candidates import (
    score_entity_resolution_candidates,
    score_pair,
    compact_record,
)


def _write_jsonl(path, records):
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def _source_record(
    input_id,
    *,
    source="ufocat",
    native_id="21558",
    date="1954-09-19",
    date_precision="exact_day",
    time="1630",
    location="RONGERES, Allier, FRA, EU",
    lat=46.30,
    lon=-3.47,
    text="Two witnesses observed a landed disc near Rongeres with one object reported.",
    type_raw="3L",
    shape_raw=None,
):
    return {
        "canonical_input_id": input_id,
        "source_name": source,
        "source_file": f"{source}.csv",
        "source_row_number": 1,
        "source_native_id": native_id,
        "date_iso": date,
        "date_precision": date_precision,
        "time_raw": time,
        "location_raw": location,
        "lat": lat,
        "lon": lon,
        "coordinate_source": "source_coordinates",
        "summary": text,
        "description": text,
        "type_raw": type_raw,
        "type_normalized": type_raw.lower() if type_raw else None,
        "shape_raw": shape_raw,
        "shape_normalized": shape_raw,
    }


def test_score_pair_rates_rongeres_style_duplicate_high():
    first = compact_record(_source_record("cin_a", native_id="171782", lon=-3.45), event_id="evt_a")
    second = compact_record(_source_record("cin_b", native_id="21558", lon=-3.47), event_id="evt_b")

    score = score_pair(first, second)

    assert score["score"] >= 0.86
    assert "same_exact_day" in score["evidence"]
    assert "same_specific_time" in score["evidence"]
    assert "trusted_coordinates_within_2km" in score["evidence"]
    assert "different_source_native_ids" in score["risk_flags"]


def test_score_pair_penalizes_far_location_and_weak_text():
    first = compact_record(_source_record("cin_a", native_id="171782", text="Red light moved north."), event_id="evt_a")
    second = compact_record(
        _source_record(
            "cin_b",
            native_id="999999",
            location="Denver, CO, US",
            lat=39.7392,
            lon=-104.9903,
            text="Blue triangle hovered silently.",
        ),
        event_id="evt_b",
    )

    score = score_pair(first, second)

    assert score["score"] < 0.58
    assert "coordinates_far_apart" in score["risk_flags"]
    assert "weak_text_overlap" in score["risk_flags"]
    assert "source_location_country_hint_conflict" in score["risk_flags"]


def test_score_pair_adds_source_location_country_and_region_hints():
    first = compact_record(
        _source_record(
            "cin_a",
            native_id="100",
            location="FARGO, Cass, ND, US",
            lat=46.8772,
            lon=-96.7898,
        ),
        event_id="evt_a",
    )
    second = compact_record(
        _source_record(
            "cin_b",
            native_id="101",
            location="Fargo, North Dakota, ND, US",
            lat=46.8771,
            lon=-96.7897,
        ),
        event_id="evt_b",
    )

    score = score_pair(first, second)

    assert "same_source_location_country_hint" in score["evidence"]
    assert "same_source_location_region_hint" in score["evidence"]
    assert first.location_country_key == "us"
    assert first.location_region_key == "us:nd"


def test_score_pair_flags_source_location_region_hint_conflict_within_country():
    first = compact_record(
        _source_record("cin_a", native_id="100", location="FARGO, Cass, ND, US", lat=46.8772, lon=-96.7898),
        event_id="evt_a",
    )
    second = compact_record(
        _source_record("cin_b", native_id="101", location="DENVER, CO, US", lat=39.7392, lon=-104.9903),
        event_id="evt_b",
    )

    score = score_pair(first, second)

    assert "same_source_location_country_hint" in score["evidence"]
    assert "source_location_region_hint_conflict" in score["risk_flags"]


def test_score_pair_downgrades_matching_non_exact_dates():
    first = compact_record(_source_record("cin_a", date="1954-09", date_precision="month"), event_id="evt_a")
    second = compact_record(_source_record("cin_b", date="1954-09", date_precision="month"), event_id="evt_b")

    score = score_pair(first, second)

    assert "same_exact_day" not in score["evidence"]
    assert "same_coarse_or_uncertain_date" in score["evidence"]
    assert "coarse_or_uncertain_date_precision" in score["risk_flags"]


def test_score_pair_limits_short_exact_text_credit():
    first = compact_record(_source_record("cin_a", text="Landed."), event_id="evt_a")
    second = compact_record(_source_record("cin_b", text="Landed."), event_id="evt_b")

    score = score_pair(first, second)

    assert "same_exact_normalized_text" not in score["evidence"]
    assert "same_short_normalized_text" in score["evidence"]
    assert "short_text_match_limited" in score["risk_flags"]


def test_entity_resolution_report_is_analysis_only_and_scores_pairs(tmp_path):
    deduped_events = tmp_path / "deduped_events.jsonl"
    source_records = tmp_path / "source_records.jsonl"
    _write_jsonl(
        deduped_events,
        [
            {"canonical_event_id": "evt_a", "canonical_input_ids": ["cin_a"]},
            {"canonical_event_id": "evt_b", "canonical_input_ids": ["cin_b"]},
            {"canonical_event_id": "evt_c", "canonical_input_ids": ["cin_c"]},
        ],
    )
    _write_jsonl(
        source_records,
        [
            _source_record("cin_a", native_id="171782", lon=-3.45),
            _source_record("cin_b", native_id="21558", lon=-3.47),
            _source_record("cin_c", native_id="88888", date="1954-09-20", text="Unrelated later case."),
        ],
    )

    report = score_entity_resolution_candidates(
        source_records_path=source_records,
        deduped_events_path=deduped_events,
    )

    assert report["canonical_outputs_mutated"] is False
    assert report["preview_outputs_written"] is False
    assert report["decisions_created"] is False
    assert report["auto_merge_performed"] is False
    assert report["score_summary"]["scored_pair_count"] >= 1
    assert report["score_summary"]["band_counts"]["likely_same_event_review"] >= 1
    assert report["score_summary"]["projected_cross_event_reduction"]["likely_same_event_review"] >= 1
    assert report["top_scored_pairs"][0]["band"] == "likely_same_event_review"
    assert report["band_scored_pair_samples"]["likely_same_event_review"]
    assert report["band_cross_event_scored_pair_samples"]["likely_same_event_review"]
    assert report["score_summary"]["evidence_counts"]["same_exact_day"] >= 1
    assert "ufocat|ufocat" in report["score_summary"]["band_source_pair_counts"]["likely_same_event_review"]


def test_entity_resolution_scoring_can_truncate_pair_scoring(tmp_path):
    deduped_events = tmp_path / "deduped_events.jsonl"
    source_records = tmp_path / "source_records.jsonl"
    _write_jsonl(
        deduped_events,
        [
            {"canonical_event_id": f"evt_{index}", "canonical_input_ids": [f"cin_{index}"]}
            for index in range(5)
        ],
    )
    _write_jsonl(
        source_records,
        [_source_record(f"cin_{index}", native_id=str(index)) for index in range(5)],
    )

    report = score_entity_resolution_candidates(
        source_records_path=source_records,
        deduped_events_path=deduped_events,
        max_scored_pairs=2,
    )

    assert report["score_summary"]["scored_pair_count"] == 2
    assert report["score_summary"]["pair_scoring_truncated"] is True


def test_entity_resolution_scoring_keeps_band_sample_limit(tmp_path):
    deduped_events = tmp_path / "deduped_events.jsonl"
    source_records = tmp_path / "source_records.jsonl"
    _write_jsonl(
        deduped_events,
        [
            {"canonical_event_id": f"evt_{index}", "canonical_input_ids": [f"cin_{index}"]}
            for index in range(4)
        ],
    )
    _write_jsonl(
        source_records,
        [_source_record(f"cin_{index}", native_id=str(index), lon=-3.45 + index * 0.001) for index in range(4)],
    )

    report = score_entity_resolution_candidates(
        source_records_path=source_records,
        deduped_events_path=deduped_events,
        band_sample_limit=2,
    )

    assert len(report["band_scored_pair_samples"]["likely_same_event_review"]) <= 2


def test_entity_resolution_scoring_can_build_larger_report_only_candidate_worklist(tmp_path):
    deduped_events = tmp_path / "deduped_events.jsonl"
    source_records = tmp_path / "source_records.jsonl"
    _write_jsonl(
        deduped_events,
        [
            {"canonical_event_id": f"evt_{index}", "canonical_input_ids": [f"cin_{index}"]}
            for index in range(4)
        ],
    )
    _write_jsonl(
        source_records,
        [_source_record(f"cin_{index}", native_id=str(index), lon=-3.45 + index * 0.001) for index in range(4)],
    )

    report = score_entity_resolution_candidates(
        source_records_path=source_records,
        deduped_events_path=deduped_events,
        band_sample_limit=1,
        candidate_worklist_per_band_limit=2,
        candidate_worklist_min_band="likely_same_event_review",
    )

    assert len(report["band_cross_event_scored_pair_samples"]["likely_same_event_review"]) == 1
    assert report["candidate_worklist_summary"]["enabled"] is True
    assert report["candidate_worklist_summary"]["worklist_policy"] == "entity_resolution_candidate_worklist_report_only"
    assert report["candidate_worklist_summary"]["canonical_outputs_mutated"] is False
    assert report["candidate_worklist_summary"]["decisions_created"] is False
    assert report["candidate_worklist_summary"]["band_counts"]["likely_same_event_review"] == 2
    assert len(report["candidate_worklist_items"]) == 2
    assert all(item["cross_current_event"] for item in report["candidate_worklist_items"])
    assert all(item["candidate_worklist_policy"] == "entity_resolution_candidate_worklist_report_only" for item in report["candidate_worklist_items"])


def test_limited_entity_resolution_run_indexes_only_touched_inputs(tmp_path):
    deduped_events = tmp_path / "deduped_events.jsonl"
    source_records = tmp_path / "source_records.jsonl"
    _write_jsonl(
        deduped_events,
        [
            {"canonical_event_id": "evt_a", "canonical_input_ids": ["cin_a"]},
            {"canonical_event_id": "evt_b", "canonical_input_ids": ["cin_b"]},
            {"canonical_event_id": "evt_c", "canonical_input_ids": ["cin_c"]},
        ],
    )
    _write_jsonl(
        source_records,
        [
            _source_record("cin_a", native_id="171782", lon=-3.45),
            _source_record("cin_b", native_id="21558", lon=-3.47),
            _source_record("cin_c", native_id="88888", lon=-3.49),
        ],
    )

    report = score_entity_resolution_candidates(
        source_records_path=source_records,
        deduped_events_path=deduped_events,
        limit=2,
    )

    assert report["block_summary"]["source_records_scanned"] == 2
    assert report["current_corpus"]["event_index_scope"] == "touched_input_ids"
    assert report["current_corpus"]["event_index_complete"] is False
    assert report["current_corpus"]["required_input_index_complete"] is True
    assert report["current_corpus"]["deduped_events_scanned_for_index"] == 2
    assert report["current_corpus"]["matched_required_input_ids"] == 2
    assert report["score_summary"]["scored_pair_count"] == 1


def test_entity_resolution_run_can_offset_source_record_batches(tmp_path):
    deduped_events = tmp_path / "deduped_events.jsonl"
    source_records = tmp_path / "source_records.jsonl"
    _write_jsonl(
        deduped_events,
        [
            {"canonical_event_id": "evt_a", "canonical_input_ids": ["cin_a"]},
            {"canonical_event_id": "evt_b", "canonical_input_ids": ["cin_b"]},
            {"canonical_event_id": "evt_c", "canonical_input_ids": ["cin_c"]},
            {"canonical_event_id": "evt_d", "canonical_input_ids": ["cin_d"]},
        ],
    )
    _write_jsonl(
        source_records,
        [
            _source_record("cin_a", native_id="171782", lon=-3.45),
            _source_record("cin_b", native_id="21558", lon=-3.47),
            _source_record("cin_c", native_id="30000", lon=-3.49),
            _source_record("cin_d", native_id="30001", lon=-3.50),
        ],
    )

    report = score_entity_resolution_candidates(
        source_records_path=source_records,
        deduped_events_path=deduped_events,
        limit=2,
        offset=2,
    )

    assert report["inputs"]["offset"] == 2
    assert report["block_summary"]["source_records_offset"] == 2
    assert report["block_summary"]["source_records_scanned"] == 2
    assert report["score_summary"]["scored_pair_count"] == 1
    pair = report["top_scored_pairs"][0]
    assert {pair["left"]["canonical_input_id"], pair["right"]["canonical_input_id"]} == {"cin_c", "cin_d"}


def test_entity_resolution_run_can_use_input_event_lookup_without_deduped_scan(tmp_path):
    missing_deduped_events = tmp_path / "missing_deduped_events.jsonl"
    input_event_lookup = tmp_path / "input_event_lookup.jsonl"
    source_records = tmp_path / "source_records.jsonl"
    _write_jsonl(
        input_event_lookup,
        [
            {"canonical_input_id": "cin_a", "canonical_event_id": "evt_a"},
            {"canonical_input_id": "cin_b", "canonical_event_id": "evt_b"},
        ],
    )
    _write_jsonl(
        source_records,
        [
            _source_record("cin_a", native_id="171782", lon=-3.45),
            _source_record("cin_b", native_id="21558", lon=-3.47),
        ],
    )

    report = score_entity_resolution_candidates(
        source_records_path=source_records,
        deduped_events_path=missing_deduped_events,
        input_event_lookup_path=input_event_lookup,
        limit=2,
    )

    assert report["current_corpus"]["event_index_source"] == "input_event_lookup"
    assert report["current_corpus"]["deduped_events_scanned_for_index"] == 0
    assert report["current_corpus"]["lookup_rows_scanned_for_index"] == 2
    assert report["current_corpus"]["matched_required_input_ids"] == 2
    assert report["score_summary"]["scored_pair_count"] == 1
