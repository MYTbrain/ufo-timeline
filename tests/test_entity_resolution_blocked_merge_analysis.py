import pytest

from scripts.analyze_entity_resolution_blocked_merges import analyze_entity_resolution_blocked_merges


def _safe_packet(items):
    return {
        "packet_policy": "entity_resolution_blocked_merge_review_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "items": items,
    }


def test_blocked_merge_analysis_marks_strict_subtype_variants_as_shadow_override_candidates():
    report = analyze_entity_resolution_blocked_merges(
        blocked_packet=_safe_packet(
            [
                {
                    "review_item_id": "review_1",
                    "patch_id": "patch_1",
                    "effect_id": "effect_1",
                    "blocking_fields": ["type_normalized"],
                    "projected_event_reduction": 1,
                    "field_conflicts": {
                        "type_normalized": ["6p", "6ph"],
                        "summary": ["same source event with beam", "same source event with beam detail"],
                    },
                    "source_event_summaries": [
                        {
                            "source_name": "ufocat",
                            "source_file": "ufocat2023.csv",
                            "source_native_id": "78248",
                            "date_iso": "1968-08-28",
                            "time_raw": "1930",
                            "location_raw": "UCERO, Soria, ESP, EU",
                            "lat": 41.7,
                            "lon": 3.05,
                            "type_normalized": "6p",
                        },
                        {
                            "source_name": "ufocat",
                            "source_file": "ufocat2023.csv",
                            "source_native_id": "78248",
                            "date_iso": "1968-08-28",
                            "time_raw": "1930",
                            "location_raw": "UCERO, Soria, ESP, EU",
                            "lat": 41.7,
                            "lon": 3.05,
                            "type_normalized": "6ph",
                        },
                    ],
                }
            ]
        )
    )

    item = report["items"][0]
    assert report["canonical_outputs_mutated"] is False
    assert report["decisions_created"] is False
    assert report["high_confidence_shadow_override_candidate_count"] == 1
    assert item["classification"] == "likely_source_subtype_variant"
    assert item["suggested_action"] == "candidate_shadow_preview_override"
    assert item["analysis_confidence"] == "high"


def test_blocked_merge_analysis_keeps_coordinate_distance_as_review_first():
    report = analyze_entity_resolution_blocked_merges(
        blocked_packet=_safe_packet(
            [
                {
                    "review_item_id": "review_2",
                    "blocking_fields": ["coordinate_distance_over_10km"],
                    "field_conflicts": {"lat": [-24.77, -24.85], "lon": [65.47, 65.42]},
                    "source_event_summaries": [
                        {
                            "source_name": "ufocat",
                            "source_file": "ufocat2023.csv",
                            "source_native_id": "32227",
                            "date_iso": "1959-06-22",
                            "time_raw": "2000",
                            "location_raw": "SALTA=SAN BERNARDO, Salta, ARG, SA",
                            "lat": -24.77,
                            "lon": 65.47,
                            "type_normalized": "5e",
                        },
                        {
                            "source_name": "ufocat",
                            "source_file": "ufocat2023.csv",
                            "source_native_id": "32227",
                            "date_iso": "1959-06-22",
                            "time_raw": "2000",
                            "location_raw": "SALTA, Salta, ARG, SA",
                            "lat": -24.85,
                            "lon": 65.42,
                            "type_normalized": "5e",
                        },
                    ],
                }
            ]
        )
    )

    item = report["items"][0]
    assert item["classification"] == "nearby_location_coordinate_variant"
    assert item["suggested_action"] == "coordinate_review_before_override"
    assert item["analysis_confidence"] == "medium"
    assert report["high_confidence_shadow_override_candidate_count"] == 0


def test_blocked_merge_analysis_marks_true_time_format_variants_as_shadow_override_candidates():
    report = analyze_entity_resolution_blocked_merges(
        blocked_packet=_safe_packet(
            [
                {
                    "review_item_id": "review_3",
                    "blocking_fields": ["time_raw"],
                    "field_conflicts": {"time_raw": ["1630", "16:30"]},
                    "source_event_summaries": [
                        {
                            "source_name": "ufocat",
                            "source_file": "ufocat2023.csv",
                            "source_native_id": "171782",
                            "date_iso": "1954-09-19",
                            "time_raw": "1630",
                            "location_raw": "RONGERES, FRA",
                            "lat": 46.3,
                            "lon": 3.45,
                        },
                        {
                            "source_name": "ufocat",
                            "source_file": "ufocat2023.csv",
                            "source_native_id": "171782",
                            "date_iso": "1954-09-19",
                            "time_raw": "16:30",
                            "location_raw": "RONGERES, FRA",
                            "lat": 46.3,
                            "lon": 3.45,
                        },
                    ],
                }
            ]
        )
    )

    item = report["items"][0]
    assert item["classification"] == "likely_time_format_variant"
    assert item["suggested_action"] == "candidate_shadow_preview_override"
    assert item["analysis_confidence"] == "high"
    assert item["parsed_time_minutes"] == [990]
    assert report["high_confidence_shadow_override_candidate_count"] == 1


def test_blocked_merge_analysis_keeps_different_times_review_first():
    report = analyze_entity_resolution_blocked_merges(
        blocked_packet=_safe_packet(
            [
                {
                    "review_item_id": "review_4",
                    "blocking_fields": ["time_raw"],
                    "field_conflicts": {"time_raw": ["1630", "1730"]},
                    "source_event_summaries": [
                        {
                            "source_name": "ufocat",
                            "source_file": "ufocat2023.csv",
                            "source_native_id": "171782",
                            "date_iso": "1954-09-19",
                            "time_raw": "1630",
                            "location_raw": "RONGERES, FRA",
                            "lat": 46.3,
                            "lon": 3.45,
                        },
                        {
                            "source_name": "ufocat",
                            "source_file": "ufocat2023.csv",
                            "source_native_id": "171782",
                            "date_iso": "1954-09-19",
                            "time_raw": "1730",
                            "location_raw": "RONGERES, FRA",
                            "lat": 46.3,
                            "lon": 3.45,
                        },
                    ],
                }
            ]
        )
    )

    item = report["items"][0]
    assert item["classification"] == "time_format_or_multiple_time_variant"
    assert item["suggested_action"] == "time_review_before_override"
    assert item["analysis_confidence"] == "medium"
    assert item["parsed_time_minutes"] == [990, 1050]
    assert report["high_confidence_shadow_override_candidate_count"] == 0


def test_blocked_merge_analysis_rejects_unsafe_packet():
    packet = _safe_packet([])
    packet["decisions_created"] = True

    with pytest.raises(ValueError, match="blocked merge packet is not safe"):
        analyze_entity_resolution_blocked_merges(blocked_packet=packet)
