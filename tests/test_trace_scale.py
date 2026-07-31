import json

import pytest

from parser.trace_scale import (
    TRACE_AGGREGATE_SEGMENT_THRESHOLD,
    TRACE_BUDGETED_SEGMENT_THRESHOLD,
    TRACE_GAP_BUCKETS,
    TRACE_INDIVIDUAL_SEGMENT_THRESHOLD,
    TRACE_RENDER_MODE_AGGREGATE,
    TRACE_RENDER_MODE_BUDGETED,
    TRACE_RENDER_MODE_INDIVIDUAL,
    TRACE_RENDER_MODE_SUMMARY,
    TRACE_RENDER_MODE_THRESHOLDS,
    TRACE_SUMMARY_SEGMENT_THRESHOLD,
    chronology_legend_descriptor,
    density_legend_descriptor,
    gap_legend_descriptor,
    playback_recency_legend_descriptor,
    resolve_trace_render_mode,
    source_legend_descriptor,
    trace_gap_bucket_for_days,
)


def test_trace_render_mode_thresholds_match_scale_plan():
    assert TRACE_INDIVIDUAL_SEGMENT_THRESHOLD == 1_800
    assert TRACE_BUDGETED_SEGMENT_THRESHOLD == 6_000
    assert TRACE_AGGREGATE_SEGMENT_THRESHOLD == 28_000
    assert TRACE_SUMMARY_SEGMENT_THRESHOLD == 28_001
    assert TRACE_RENDER_MODE_THRESHOLDS == {
        TRACE_RENDER_MODE_INDIVIDUAL: TRACE_INDIVIDUAL_SEGMENT_THRESHOLD,
        TRACE_RENDER_MODE_BUDGETED: TRACE_BUDGETED_SEGMENT_THRESHOLD,
        TRACE_RENDER_MODE_AGGREGATE: TRACE_AGGREGATE_SEGMENT_THRESHOLD,
        TRACE_RENDER_MODE_SUMMARY: TRACE_SUMMARY_SEGMENT_THRESHOLD,
    }


@pytest.mark.parametrize(
    ("segment_count", "expected_mode"),
    [
        (0, TRACE_RENDER_MODE_INDIVIDUAL),
        (TRACE_INDIVIDUAL_SEGMENT_THRESHOLD, TRACE_RENDER_MODE_INDIVIDUAL),
        (TRACE_INDIVIDUAL_SEGMENT_THRESHOLD + 1, TRACE_RENDER_MODE_BUDGETED),
        (TRACE_BUDGETED_SEGMENT_THRESHOLD, TRACE_RENDER_MODE_BUDGETED),
        (TRACE_BUDGETED_SEGMENT_THRESHOLD + 1, TRACE_RENDER_MODE_AGGREGATE),
        (TRACE_AGGREGATE_SEGMENT_THRESHOLD, TRACE_RENDER_MODE_AGGREGATE),
        (TRACE_SUMMARY_SEGMENT_THRESHOLD, TRACE_RENDER_MODE_SUMMARY),
    ],
)
def test_resolve_trace_render_mode_boundary_values(segment_count, expected_mode):
    assert resolve_trace_render_mode(segment_count) == expected_mode


def test_resolve_trace_render_mode_rejects_invalid_counts():
    with pytest.raises(ValueError):
        resolve_trace_render_mode(-1)

    with pytest.raises(TypeError):
        resolve_trace_render_mode(3_000.0)

    with pytest.raises(TypeError):
        resolve_trace_render_mode(True)


def test_gradient_legend_descriptors_are_mode_specific_and_serializable():
    descriptors = (
        chronology_legend_descriptor(),
        playback_recency_legend_descriptor(),
        density_legend_descriptor(),
    )

    assert [descriptor.mode for descriptor in descriptors] == [
        "chronology",
        "playback_recency",
        "density",
    ]

    for descriptor in descriptors:
        payload = descriptor.to_json_dict()
        assert payload["kind"] == "gradient"
        json.dumps(payload)

    chronology_payload = descriptors[0].to_json_dict()
    assert [stop["value"] for stop in chronology_payload["stops"]] == [0.0, 0.16, 0.34, 0.52, 0.7, 0.86, 1.0]
    assert [stop["color"] for stop in chronology_payload["stops"]] == [
        "#2b6cb0",
        "#00a6d6",
        "#14b8a6",
        "#84cc16",
        "#facc15",
        "#f97316",
        "#e11d48",
    ]
    playback_payload = descriptors[1].to_json_dict()
    assert [stop["value"] for stop in playback_payload["stops"]] == [0.0, 0.7, 1.0]
    density_payload = descriptors[2].to_json_dict()
    assert [stop["value"] for stop in density_payload["stops"]] == [0.0, 0.5, 1.0]


def test_source_legend_descriptor_deduplicates_labels_with_stable_palette():
    descriptor = source_legend_descriptor(["NUFORC", "MUFON", "NUFORC", "", "PhenomenAInon UPDB"])
    payload = descriptor.to_json_dict()

    assert payload["mode"] == "source"
    assert payload["kind"] == "swatches"
    assert [swatch["label"] for swatch in payload["swatches"]] == ["NUFORC", "MUFON", "PhenomenAInon UPDB"]
    assert [swatch["value"] for swatch in payload["swatches"]] == ["nuforc", "mufon", "phenomenainon_updb"]
    assert payload["swatches"][0]["color"] == "#2f6bff"
    json.dumps(payload)


def test_source_legend_descriptor_honors_explicit_empty_source_list():
    payload = source_legend_descriptor([]).to_json_dict()

    assert payload["mode"] == "source"
    assert payload.get("swatches") is None
    json.dumps(payload)


def test_gap_legend_descriptor_names_current_gap_buckets():
    payload = gap_legend_descriptor().to_json_dict()

    assert payload["mode"] == "gap"
    assert payload["kind"] == "swatches"
    assert [swatch["value"] for swatch in payload["swatches"]] == [
        "current_bucket",
        "short_gap",
        "long_gap",
        "unknown_gap",
    ]
    json.dumps(payload)


def test_trace_gap_bucket_for_days_uses_export_bucket_boundaries():
    assert [bucket["key"] for bucket in TRACE_GAP_BUCKETS] == [
        "gap_le_1",
        "gap_le_2",
        "gap_le_7",
        "gap_le_30",
        "gap_gt_30",
    ]
    assert trace_gap_bucket_for_days(0) == "gap_le_1"
    assert trace_gap_bucket_for_days(1) == "gap_le_1"
    assert trace_gap_bucket_for_days(2) == "gap_le_2"
    assert trace_gap_bucket_for_days(7) == "gap_le_7"
    assert trace_gap_bucket_for_days(30) == "gap_le_30"
    assert trace_gap_bucket_for_days(31) == "gap_gt_30"

    with pytest.raises(ValueError):
        trace_gap_bucket_for_days(-1)
