import json

from parser.trace_segments import (
    ROW_STRUCT,
    TRACE_AGGREGATE_ROW_STRUCT,
    TRACE_EVENT_ROW_STRUCT,
    export_trace_artifacts,
    export_trace_segments,
)


def test_export_trace_segments_uses_canonical_order_and_short_wrapping(tmp_path):
    events = [
        _event(30, "2001-01-03", 10.0, 20.0, source="nuforc"),
        _event(10, "2001-01-01", 0.0, 170.0, source="mufon"),
        _event(20, "2001-01-02", 0.0, -170.0, source="ufocat"),
        {**_event(40, "2001-01-04", 40.0, 40.0), "coordinate_source": "unresolved"},
    ]

    metadata = export_trace_segments(events, tmp_path)

    assert metadata["schema_version"] == 1
    assert metadata["row_count"] == 2
    assert metadata["counts"]["mapped_trace_events"] == 3
    assert metadata["counts"]["gap_bucket_counts"] == {"gap_le_1": 2}
    assert metadata["render_plan"]["row_order"] == "canonical_playback_order"
    assert (tmp_path / "trace_segments.bin").stat().st_size == 2 * metadata["bytes_per_row"]
    assert (tmp_path / "trace_segments_meta.json").exists()

    rows = _read_rows(tmp_path / "trace_segments.bin", metadata)
    first = rows[0]
    assert first["from_event_id"] == 10
    assert first["to_event_id"] == 20
    assert first["from_sort_date_key"] == 20010101
    assert first["to_sort_date_key"] == 20010102
    assert first["gap_days"] == 1
    assert first["bucket_id"] == "gap_le_1"
    assert first["source_pair_id"] == "mufon->ufocat"
    assert first["sequence_index"] == 0
    assert first["from_lon"] == 170.0
    assert first["to_lon"] == 190.0

    second = rows[1]
    assert second["from_event_id"] == 20
    assert second["to_event_id"] == 30
    assert second["source_pair_id"] == "ufocat->nuforc"
    assert {(row["from_event_id"], row["to_event_id"]) for row in rows} == {(10, 20), (20, 30)}

    persisted_metadata = json.loads((tmp_path / "trace_segments_meta.json").read_text(encoding="utf-8"))
    assert persisted_metadata["row_count"] == metadata["row_count"]


def test_export_trace_artifacts_writes_filterable_event_index_and_diagnostic_segments(tmp_path):
    events = [
        _event(30, "2001-01-01", 10.0, 20.0, source="nuforc", playback_sort_key=[1, 300, 0, 3, 0, "30"]),
        _event(10, "2001-01-01", 0.0, 170.0, source="mufon", playback_sort_key=[1, 100, 0, 3, 0, "10"]),
        _event(20, "2001-01-01", 0.0, -170.0, source="ufocat", playback_sort_key=[1, 200, 0, 3, 0, "20"]),
    ]

    metadata = export_trace_artifacts(events, tmp_path)

    assert metadata["schema_version"] == 1
    trace_events = metadata["trace_events"]
    trace_segments = metadata["trace_segments"]
    trace_aggregate_bins = metadata["trace_aggregate_bins"]
    assert trace_events["row_count"] == 3
    assert trace_events["render_contract"] == {
        "row_order": "canonical_playback_order",
        "filtered_segment_rule": "filter rows first, then connect adjacent visible rows client-side",
        "sequence_index_scope": (
            "full canonical mapped sequence; recompute visible sequence_index and sequence_ratio after filtering"
        ),
    }
    assert trace_segments["row_count"] == 2
    assert "diagnostic/convenience" in trace_segments["render_plan"]["runtime_warning"]
    assert trace_aggregate_bins["row_count"] >= 2
    assert trace_aggregate_bins["counts"]["input_segments"] == 2
    assert "full-universe wide-window LOD" in trace_aggregate_bins["render_contract"]["runtime_warning"]
    assert trace_aggregate_bins["render_contract"]["supported_filter_semantics"] == ["none/full_universe"]
    assert trace_aggregate_bins["render_contract"]["authoritative_filtered_source"] == "trace_event_index.bin"

    event_rows = _read_rows(tmp_path / "trace_event_index.bin", trace_events, TRACE_EVENT_ROW_STRUCT)
    assert [row["event_id"] for row in event_rows] == [10, 20, 30]
    assert [row["sequence_index"] for row in event_rows] == [0, 1, 2]
    assert event_rows[0]["source_id"] == "mufon"

    assert (tmp_path / "trace_event_index.bin").stat().st_size == 3 * trace_events["bytes_per_row"]
    assert (tmp_path / "trace_event_index_meta.json").exists()
    aggregate_rows = _read_rows(tmp_path / "trace_aggregate_bins.bin", trace_aggregate_bins, TRACE_AGGREGATE_ROW_STRUCT)
    assert {row["level_id"] for row in aggregate_rows} == {"10deg", "5deg", "2_5deg"}
    assert sum(row["segment_count"] for row in aggregate_rows if row["level_id"] == "10deg") == 2
    assert (tmp_path / "trace_aggregate_bins.bin").stat().st_size == (
        trace_aggregate_bins["row_count"] * trace_aggregate_bins["bytes_per_row"]
    )
    assert (tmp_path / "trace_aggregate_bins_meta.json").exists()


def test_trace_eligible_false_excludes_context_layer_events(tmp_path):
    events = [
        _event(10, "2001-01-01", 10.0, 10.0, source="ufo"),
        {
            **_event(20, "2001-01-02", 20.0, 20.0, source="Animal Mutilation Dataset v1"),
            "event_domain": "animal_mutilation",
            "trace_eligible": False,
            "trace_role": "context_only",
        },
        _event(30, "2001-01-03", 30.0, 30.0, source="ufo"),
    ]

    metadata = export_trace_artifacts(events, tmp_path)

    trace_events = _read_rows(
        tmp_path / "trace_event_index.bin",
        metadata["trace_events"],
        TRACE_EVENT_ROW_STRUCT,
    )
    trace_segments = _read_rows(
        tmp_path / "trace_segments.bin",
        metadata["trace_segments"],
    )
    assert [row["event_id"] for row in trace_events] == [10, 30]
    assert [
        (row["from_event_id"], row["to_event_id"])
        for row in trace_segments
    ] == [(10, 30)]
    assert metadata["trace_segments"]["counts"]["mapped_trace_events"] == 2


def _event(event_id, sort_date_iso, lat, lon, *, source="nuforc", playback_sort_key=None):
    return {
        "event_id": event_id,
        "sort_date_iso": sort_date_iso,
        "playback_sort_key": playback_sort_key or [3, None, None, 3, 0, str(event_id)],
        "lat": lat,
        "lon": lon,
        "coordinate_source": "raw_latlong",
        "source": source,
    }


def _read_rows(path, metadata, row_struct=ROW_STRUCT):
    rows = []
    for unpacked in row_struct.iter_unpack(path.read_bytes()):
        row = {}
        for field, value in zip(metadata["fields"], unpacked):
            lookup_table = field.get("lookup_table")
            if lookup_table:
                value = metadata["lookup_tables"][lookup_table][value]
            row[field["name"]] = value
        rows.append(row)
    return rows
