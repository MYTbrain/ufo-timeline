import json

from scripts.summarize_dedupe_benchmark_gap import summarize_dedupe_benchmark_gap


def _write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_summarize_dedupe_benchmark_gap_consolidates_report_only_math(tmp_path):
    import_report = tmp_path / "canonical_import_report.json"
    cluster_report = tmp_path / "duplicate_candidate_cluster_summary.json"
    expanded_report = tmp_path / "expanded_dedupe_opportunity_report.json"
    ai_report = tmp_path / "manual_review_ai_effect_impact_summary.json"
    _write_json(
        import_report,
        {
            "source_record_count": 100,
            "deduped_event_count": 90,
            "duplicate_candidate_limit_reached": True,
            "retained_source_files": ["ufocat2023.csv"],
            "exact_subset_drop_files": {"nuforc.csv": "nuforcpy.csv"},
        },
    )
    _write_json(
        cluster_report,
        {
            "candidate_edge_count": 12,
            "candidate_cluster_count": 5,
            "projected_cluster_reduction_if_all_edges_same_event": 8,
            "dense_pair_capacity_waste": 4,
        },
    )
    _write_json(
        expanded_report,
        {
            "scan_counts": {"scanned_source_records": 100},
            "current_canonical_counts": {"current_event_count": 90},
            "tier_union_reduction_estimates": {
                "conservative": {"projected_event_reduction": 20},
                "moderate": {"projected_event_reduction": 22},
                "exploratory": {"projected_event_reduction": 25},
                "aggressive": {"projected_event_reduction": 30},
            },
        },
    )
    _write_json(
        ai_report,
        {
            "scanned_event_count": 89,
            "merge_impact": {"projected_event_reduction": 4},
        },
    )

    report = summarize_dedupe_benchmark_gap(
        import_report_path=import_report,
        cluster_report_path=cluster_report,
        expanded_report_path=expanded_report,
        ai_impact_report_path=ai_report,
        benchmark_count=60,
    )

    assert report["canonical_outputs_mutated"] is False
    assert report["preview_outputs_written"] is False
    assert report["decisions_created"] is False
    assert report["auto_merge_performed"] is False
    assert report["current_corpus"]["current_exact_duplicate_record_reduction"] == 10
    assert report["current_candidate_queue"]["candidate_limit_reached"] is True
    assert report["projections"]["current_gap_to_benchmark"] == 30
    assert report["projections"]["after_expanded_conservative_estimate"]["projected_event_count"] == 70
    assert report["projections"]["after_expanded_conservative_estimate"]["gap_to_benchmark"] == 10
    assert report["projections"]["after_expanded_aggressive_estimate"]["projected_event_count"] == 60
    assert report["projections"]["after_expanded_aggressive_estimate"]["gap_to_benchmark"] == 0
    assert report["consistency_checks"]["ai_impact_scanned_event_count_matches_import_report"] is False


def test_summarize_dedupe_benchmark_gap_does_not_sum_overlapping_estimates(tmp_path):
    import_report = tmp_path / "canonical_import_report.json"
    cluster_report = tmp_path / "duplicate_candidate_cluster_summary.json"
    expanded_report = tmp_path / "expanded_dedupe_opportunity_report.json"
    ai_report = tmp_path / "manual_review_ai_effect_impact_summary.json"
    _write_json(import_report, {"source_record_count": 10, "deduped_event_count": 8})
    _write_json(cluster_report, {})
    _write_json(
        expanded_report,
        {
            "scan_counts": {"scanned_source_records": 10},
            "current_canonical_counts": {"current_event_count": 8},
            "tier_union_reduction_estimates": {
                "conservative": {"projected_event_reduction": 2},
                "moderate": {"projected_event_reduction": 3},
                "exploratory": {"projected_event_reduction": 4},
                "aggressive": {"projected_event_reduction": 5},
            },
        },
    )
    _write_json(ai_report, {"scanned_event_count": 8, "merge_impact": {"projected_event_reduction": 2}})

    report = summarize_dedupe_benchmark_gap(
        import_report_path=import_report,
        cluster_report_path=cluster_report,
        expanded_report_path=expanded_report,
        ai_impact_report_path=ai_report,
        benchmark_count=1,
    )

    assert report["projections"]["after_ai_assisted_plan_naive"]["projected_event_count"] == 6
    assert report["projections"]["after_expanded_conservative_estimate"]["projected_event_count"] == 6
    assert "do not add" in report["projections"]["after_ai_assisted_plan_naive"]["overlap_warning"].lower()
