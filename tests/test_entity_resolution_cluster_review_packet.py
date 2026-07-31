from scripts.build_entity_resolution_cluster_review_packet import build_entity_resolution_cluster_review_packet


def test_build_entity_resolution_cluster_review_packet_exports_top_groups():
    opportunity_report = {
        "report_policy": "streaming_estimate_only",
        "current_canonical_counts": {"current_event_count": 100},
        "tier_union_reduction_estimates": {"conservative": {"projected_event_reduction": 10}},
        "families": [
            {
                "family_id": "same_source_native_id_strong_date",
                "tier": "conservative",
                "description": "Same source native id and date.",
                "top_cross_event_groups": [
                    {
                        "key_hash": "dgk_a",
                        "unique_current_event_count": 4,
                        "source_record_count": 5,
                        "sample_input_ids": ["cin_a", "cin_b"],
                        "source_names": ["ufocat"],
                        "first_source_file": "ufocat2023.csv",
                        "date_iso": "1954-09-19",
                        "location": "RONGERES, FRA",
                        "distinct_date_count": 1,
                        "distinct_location_count": 2,
                        "date_samples": ["1954-09-19"],
                        "location_samples": ["RONGERES, FRA"],
                        "current_event_ids": ["evt_a", "evt_b", "evt_c", "evt_d"],
                        "current_event_ids_truncated": False,
                    }
                ],
            },
            {
                "family_id": "same_source_native_id_any_date",
                "tier": "aggressive",
                "description": "Same source native id.",
                "top_cross_event_groups": [
                    {
                        "key_hash": "dgk_b",
                        "unique_current_event_count": 3,
                        "source_record_count": 3,
                        "sample_input_ids": ["cin_c"],
                        "source_names": ["ufocat"],
                    }
                ],
            },
        ],
    }

    packet = build_entity_resolution_cluster_review_packet(
        opportunity_report,
        per_family_limit=1,
        include_tiers={"conservative"},
    )

    assert packet["packet_policy"] == "entity_resolution_cluster_review_only"
    assert packet["canonical_outputs_mutated"] is False
    assert packet["decisions_created"] is False
    assert packet["export_summary"]["exported_item_count"] == 1
    assert packet["export_summary"]["tier_counts"] == {"conservative": 1}
    assert packet["export_summary"]["projected_reduction_sum_not_deduped"] == 3
    assert packet["items"][0]["family_id"] == "same_source_native_id_strong_date"
    assert packet["items"][0]["projected_event_reduction"] == 3
    assert packet["items"][0]["current_event_ids"] == ["evt_a", "evt_b", "evt_c", "evt_d"]
    assert packet["items"][0]["current_event_ids_truncated"] is False
