from scripts.build_high_coordinate_span_triage_digest import build_high_coordinate_span_triage_digest


def test_high_coordinate_span_triage_digest_is_report_only_and_prioritizes_spans():
    digest = build_high_coordinate_span_triage_digest(
        {
            "review_policy": "manual_review_high_coordinate_span_review_v1",
            "items": [
                {
                    "review_rank": 2,
                    "replacement_event_id": "evt_small",
                    "coordinate_span_km": 70.0,
                    "coordinate_subcategory": "high_coordinate_variance_50_to_100km",
                    "projected_event_reduction": 1,
                    "risk_flags": ["coordinate_span_gt_50km"],
                    "source_file_values": ["ufocat2023.csv"],
                    "location_raw_values": ["A"],
                    "component_event_count": 2,
                },
                {
                    "review_rank": 1,
                    "replacement_event_id": "evt_extreme",
                    "coordinate_span_km": 700.0,
                    "coordinate_subcategory": "extreme_coordinate_variance_over_500km",
                    "projected_event_reduction": 2,
                    "risk_flags": ["coordinate_span_gt_50km", "time_raw_conflict"],
                    "source_file_values": ["ufocat2023.csv"],
                    "location_raw_values": ["B"],
                    "component_event_count": 3,
                },
            ],
        }
    )

    assert digest["digest_policy"] == "high_coordinate_span_triage_digest_report_only"
    assert digest["canonical_outputs_mutated"] is False
    assert digest["preview_outputs_written"] is False
    assert digest["decisions_created"] is False
    assert digest["ready_for_canonical_apply"] is False
    assert digest["summary"]["reviewed_item_count"] == 2
    assert digest["summary"]["projected_event_reduction_total"] == 3
    assert digest["summary"]["span_km_median"] == 385.0
    assert digest["summary"]["risk_flag_counts"]["time_raw_conflict"] == 1
    assert digest["top_review_items"][0]["replacement_event_id"] == "evt_extreme"
