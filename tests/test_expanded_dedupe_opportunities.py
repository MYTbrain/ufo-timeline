import json

from scripts.summarize_expanded_dedupe_opportunities import summarize_expanded_dedupe_opportunities


def _write_jsonl(path, records):
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def _source_record(input_id, *, source="nuforc", native_id=None, date="2001-01-01", location="Phoenix, AZ, US", text=None, lat=None, lon=None):
    return {
        "canonical_input_id": input_id,
        "source_name": source,
        "source_file": f"{source}.csv",
        "source_native_id": native_id,
        "date_iso": date,
        "date_precision": "exact_day",
        "location_raw": location,
        "summary": text or "Bright triangle object hovered silently over the city.",
        "description": text or "Bright triangle object hovered silently over the city.",
        "lat": lat,
        "lon": lon,
        "coordinate_source": "source_coordinates" if lat is not None and lon is not None else "unresolved",
    }


def test_expanded_dedupe_opportunities_reports_cross_event_reduction(tmp_path):
    deduped_events = tmp_path / "deduped_events.jsonl"
    source_records = tmp_path / "source_records.jsonl"
    _write_jsonl(
        deduped_events,
        [
            {"canonical_event_id": "evt_a", "canonical_input_ids": ["cin_a"]},
            {"canonical_event_id": "evt_b", "canonical_input_ids": ["cin_b"]},
            {"canonical_event_id": "evt_c", "canonical_input_ids": ["cin_c"]},
            {"canonical_event_id": "evt_d", "canonical_input_ids": ["cin_d"]},
            {"canonical_event_id": "evt_exact", "canonical_input_ids": ["cin_e", "cin_f"]},
        ],
    )
    _write_jsonl(
        source_records,
        [
            _source_record("cin_a", native_id="NUF-1"),
            _source_record("cin_b", native_id="NUF-1"),
            _source_record("cin_c", source="mufon", native_id="M-1", text="Orange sphere crossed the ridge."),
            _source_record("cin_d", source="ufocat", native_id="U-1", text="Orange sphere crossed the ridge."),
            _source_record("cin_e", native_id="EX-1", text="Already exactly deduped."),
            _source_record("cin_f", native_id="EX-1", text="Already exactly deduped."),
        ],
    )

    report = summarize_expanded_dedupe_opportunities(
        source_records_path=source_records,
        deduped_events_path=deduped_events,
    )

    assert report["canonical_outputs_mutated"] is False
    assert report["preview_outputs_written"] is False
    assert report["decisions_created"] is False
    assert report["auto_merge_performed"] is False
    assert report["current_canonical_counts"]["current_event_count"] == 5
    assert report["current_canonical_counts"]["current_exact_duplicate_record_reduction"] == 1
    assert report["scan_counts"]["source_records_with_current_event"] == 6
    assert report["tier_union_reduction_estimates"]["conservative"]["projected_event_reduction"] == 2
    assert report["benchmark_context"]["ufosint_screenshot_deduped_sightings"] == 618316

    families = {family["family_id"]: family for family in report["families"]}
    assert families["same_source_native_id_strong_date"]["projected_event_reduction_if_reviewed_same_event"] == 1
    assert families["strong_date_location_exact_text"]["projected_event_reduction_if_reviewed_same_event"] == 2
    assert families["same_source_native_id_strong_date"]["top_cross_event_groups"][0]["sample_input_ids"] == [
        "cin_a",
        "cin_b",
    ]


def test_expanded_dedupe_opportunities_can_export_top_group_current_event_ids(tmp_path):
    deduped_events = tmp_path / "deduped_events.jsonl"
    source_records = tmp_path / "source_records.jsonl"
    _write_jsonl(
        deduped_events,
        [
            {"canonical_event_id": "evt_b", "canonical_input_ids": ["cin_b"]},
            {"canonical_event_id": "evt_a", "canonical_input_ids": ["cin_a"]},
            {"canonical_event_id": "evt_c", "canonical_input_ids": ["cin_c"]},
        ],
    )
    _write_jsonl(
        source_records,
        [
            _source_record("cin_a", native_id="NUF-1"),
            _source_record("cin_b", native_id="NUF-1"),
            _source_record("cin_c", native_id="NUF-1"),
        ],
    )

    report = summarize_expanded_dedupe_opportunities(
        source_records_path=source_records,
        deduped_events_path=deduped_events,
        top_group_event_id_limit=2,
    )

    families = {family["family_id"]: family for family in report["families"]}
    top_group = families["same_source_native_id_strong_date"]["top_cross_event_groups"][0]
    assert top_group["current_event_ids"] == ["evt_a", "evt_b"]
    assert top_group["current_event_ids_truncated"] is True


def test_expanded_dedupe_opportunities_separates_moderate_coordinate_tier(tmp_path):
    deduped_events = tmp_path / "deduped_events.jsonl"
    source_records = tmp_path / "source_records.jsonl"
    _write_jsonl(
        deduped_events,
        [
            {"canonical_event_id": "evt_a", "canonical_input_ids": ["cin_a"]},
            {"canonical_event_id": "evt_b", "canonical_input_ids": ["cin_b"]},
        ],
    )
    _write_jsonl(
        source_records,
        [
            _source_record("cin_a", location=None, text="Silver disc near the lake.", lat=39.12345, lon=-104.98765),
            _source_record("cin_b", location=None, text="Silver disc near the lake.", lat=39.12349, lon=-104.98761),
        ],
    )

    report = summarize_expanded_dedupe_opportunities(
        source_records_path=source_records,
        deduped_events_path=deduped_events,
    )

    assert report["tier_union_reduction_estimates"]["conservative"]["projected_event_reduction"] == 0
    assert report["tier_union_reduction_estimates"]["moderate"]["projected_event_reduction"] == 1

    families = {family["family_id"]: family for family in report["families"]}
    assert families["strong_date_coordinate_exact_text"]["projected_event_reduction_if_reviewed_same_event"] == 1


def test_expanded_dedupe_opportunities_ignores_less_precise_dates(tmp_path):
    deduped_events = tmp_path / "deduped_events.jsonl"
    source_records = tmp_path / "source_records.jsonl"
    _write_jsonl(
        deduped_events,
        [
            {"canonical_event_id": "evt_a", "canonical_input_ids": ["cin_a"]},
            {"canonical_event_id": "evt_b", "canonical_input_ids": ["cin_b"]},
        ],
    )
    first = _source_record("cin_a", native_id="NUF-1")
    second = _source_record("cin_b", native_id="NUF-1")
    first["date_precision"] = "month"
    second["date_precision"] = "month"
    _write_jsonl(source_records, [first, second])

    report = summarize_expanded_dedupe_opportunities(
        source_records_path=source_records,
        deduped_events_path=deduped_events,
    )

    assert report["scan_counts"]["strong_date_records"] == 0
    assert report["tier_union_reduction_estimates"]["exploratory"]["projected_event_reduction"] == 0
    assert report["tier_union_reduction_estimates"]["aggressive"]["projected_event_reduction"] == 1


def test_expanded_dedupe_opportunities_reports_specific_time_as_aggressive_only(tmp_path):
    deduped_events = tmp_path / "deduped_events.jsonl"
    source_records = tmp_path / "source_records.jsonl"
    _write_jsonl(
        deduped_events,
        [
            {"canonical_event_id": "evt_a", "canonical_input_ids": ["cin_a"]},
            {"canonical_event_id": "evt_b", "canonical_input_ids": ["cin_b"]},
        ],
    )
    first = _source_record("cin_a", native_id=None, text="Red light.")
    second = _source_record("cin_b", native_id=None, text="Blue triangle.")
    first["time_raw"] = "21:30"
    second["time_raw"] = "21:30"
    _write_jsonl(source_records, [first, second])

    report = summarize_expanded_dedupe_opportunities(
        source_records_path=source_records,
        deduped_events_path=deduped_events,
    )

    assert report["tier_union_reduction_estimates"]["exploratory"]["projected_event_reduction"] == 0
    assert report["tier_union_reduction_estimates"]["aggressive"]["projected_event_reduction"] == 1


def test_expanded_dedupe_opportunities_rejects_vague_digit_time_strings(tmp_path):
    deduped_events = tmp_path / "deduped_events.jsonl"
    source_records = tmp_path / "source_records.jsonl"
    _write_jsonl(
        deduped_events,
        [
            {"canonical_event_id": "evt_a", "canonical_input_ids": ["cin_a"]},
            {"canonical_event_id": "evt_b", "canonical_input_ids": ["cin_b"]},
        ],
    )
    first = _source_record("cin_a", native_id=None, text="Red light.")
    second = _source_record("cin_b", native_id=None, text="Blue triangle.")
    first["time_raw"] = "about 30 minutes"
    second["time_raw"] = "about 30 minutes"
    _write_jsonl(source_records, [first, second])

    report = summarize_expanded_dedupe_opportunities(
        source_records_path=source_records,
        deduped_events_path=deduped_events,
    )

    assert report["tier_union_reduction_estimates"]["aggressive"]["projected_event_reduction"] == 0


def test_expanded_dedupe_opportunities_ignores_untrusted_coordinate_time_groups(tmp_path):
    deduped_events = tmp_path / "deduped_events.jsonl"
    source_records = tmp_path / "source_records.jsonl"
    _write_jsonl(
        deduped_events,
        [
            {"canonical_event_id": "evt_a", "canonical_input_ids": ["cin_a"]},
            {"canonical_event_id": "evt_b", "canonical_input_ids": ["cin_b"]},
        ],
    )
    first = _source_record("cin_a", native_id=None, location=None, text="Red light.", lat=40.0, lon=-75.0)
    second = _source_record("cin_b", native_id=None, location=None, text="Blue triangle.", lat=40.0, lon=-75.0)
    first["coordinate_source"] = "city_geocode"
    second["coordinate_source"] = "city_geocode"
    first["time_raw"] = "21:30"
    second["time_raw"] = "21:30"
    _write_jsonl(source_records, [first, second])

    report = summarize_expanded_dedupe_opportunities(
        source_records_path=source_records,
        deduped_events_path=deduped_events,
    )

    families = {family["family_id"]: family for family in report["families"]}
    assert families["strong_date_coordinate_specific_time"]["projected_event_reduction_if_reviewed_same_event"] == 0


def test_expanded_dedupe_opportunities_catches_same_source_nearby_coordinate_time_pattern(tmp_path):
    deduped_events = tmp_path / "deduped_events.jsonl"
    source_records = tmp_path / "source_records.jsonl"
    _write_jsonl(
        deduped_events,
        [
            {"canonical_event_id": "evt_a", "canonical_input_ids": ["cin_a"]},
            {"canonical_event_id": "evt_b", "canonical_input_ids": ["cin_b"]},
        ],
    )
    first = _source_record(
        "cin_a",
        source="ufocat",
        native_id="171782",
        date="1954-09-19",
        location="RONGERES, FRA",
        text="Witnesses 2 objects 1 landed disc.",
        lat=46.3000,
        lon=3.4500,
    )
    second = _source_record(
        "cin_b",
        source="ufocat",
        native_id="21558",
        date="1954-09-19",
        location="RONGERES, FRA",
        text="Witnesses 2 objects 1 landed disc.",
        lat=46.3000,
        lon=3.4700,
    )
    first["time_raw"] = "1630"
    second["time_raw"] = "1630"
    _write_jsonl(source_records, [first, second])

    report = summarize_expanded_dedupe_opportunities(
        source_records_path=source_records,
        deduped_events_path=deduped_events,
    )

    families = {family["family_id"]: family for family in report["families"]}
    assert families["same_source_strong_date_location_specific_time"][
        "projected_event_reduction_if_reviewed_same_event"
    ] == 1
    assert families["same_source_strong_date_coordinate_cell_specific_time"][
        "projected_event_reduction_if_reviewed_same_event"
    ] == 1


def test_expanded_dedupe_opportunities_ignores_generic_source_url_labels(tmp_path):
    deduped_events = tmp_path / "deduped_events.jsonl"
    source_records = tmp_path / "source_records.jsonl"
    _write_jsonl(
        deduped_events,
        [
            {"canonical_event_id": "evt_a", "canonical_input_ids": ["cin_a"]},
            {"canonical_event_id": "evt_b", "canonical_input_ids": ["cin_b"]},
        ],
    )
    first = _source_record("cin_a", native_id=None, text="A red light moved north.")
    second = _source_record("cin_b", native_id=None, text="A blue triangle hovered.")
    first["source_url"] = "UFOReportCtr"
    second["source_url"] = "UFOReportCtr"
    _write_jsonl(source_records, [first, second])

    report = summarize_expanded_dedupe_opportunities(
        source_records_path=source_records,
        deduped_events_path=deduped_events,
    )

    families = {family["family_id"]: family for family in report["families"]}
    assert families["same_source_url_strong_date"]["projected_event_reduction_if_reviewed_same_event"] == 0
