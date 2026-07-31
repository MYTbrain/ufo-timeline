import json

from scripts.summarize_entity_resolution_lanes import summarize_entity_resolution_lanes


def _write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def test_entity_resolution_lane_comparison_is_report_only_and_compares_available_lanes(tmp_path):
    _write_json(
        tmp_path / "entity_resolution_score_report.json",
        {
            "canonical_outputs_mutated": False,
            "current_corpus": {"current_event_count": 1000},
            "score_summary": {"scored_pair_count": 20},
        },
    )
    _write_json(
        tmp_path / "entity_resolution_review_packet.json",
        {"canonical_outputs_mutated": False, "export_summary": {"exported_item_count": 2}},
    )
    _write_json(
        tmp_path / "entity_resolution_review_suggestions_report.json",
        {"canonical_outputs_mutated": False, "suggested_decision_counts": {"same_event": 1, "needs_more_evidence": 1}},
    )
    _write_json(
        tmp_path / "entity_resolution_ai_effects_plan.json",
        {"canonical_outputs_mutated": False, "effect_counts": {"merge_entity_resolution_candidate": 1, "defer_entity_resolution_candidate": 1}},
    )
    _write_json(
        tmp_path / "entity_resolution_ai_effect_impact_summary.json",
        {"canonical_outputs_mutated": False, "merge_impact": {"projected_event_reduction": 1}},
    )
    _write_json(
        tmp_path / "entity_resolution_ai_shadow_override_subset_preview_apply_report.json",
        {"canonical_outputs_mutated": False, "effects_applied": 1, "projected_event_reduction": 1},
    )
    _write_json(
        tmp_path / "entity_resolution_ai_shadow_override_subset_preview_output_check.json",
        {"canonical_outputs_mutated": False, "valid": True, "row_count": 999, "preview_merge_count": 1},
    )
    _write_json(
        tmp_path / "entity_resolution_score_report_with_worklist.json",
        {
            "canonical_outputs_mutated": False,
            "current_corpus": {"current_event_count": 1000},
            "score_summary": {"scored_pair_count": 200},
            "candidate_worklist_summary": {"item_count": 150},
        },
    )
    _write_json(
        tmp_path / "entity_resolution_ai_shadow_override_subset_worklist_preview_apply_report.json",
        {"canonical_outputs_mutated": False, "effects_applied": 10, "projected_event_reduction": 6},
    )
    _write_json(
        tmp_path / "entity_resolution_ai_shadow_override_subset_worklist_preview_output_check.json",
        {"canonical_outputs_mutated": False, "valid": True, "row_count": 994, "preview_merge_count": 5},
    )
    _write_json(
        tmp_path / "entity_resolution_cluster_review_packet.json",
        {
            "canonical_outputs_mutated": False,
            "current_canonical_counts": {"current_event_count": 1000},
            "export_summary": {"exported_item_count": 12},
        },
    )
    _write_json(
        tmp_path / "entity_resolution_cluster_review_suggestions_report.json",
        {"canonical_outputs_mutated": False, "suggested_decision_counts": {"same_event": 3, "needs_more_evidence": 9}},
    )
    _write_json(
        tmp_path / "entity_resolution_cluster_ai_effects_plan.json",
        {"canonical_outputs_mutated": False, "effect_counts": {"merge_entity_resolution_candidate": 3, "defer_entity_resolution_candidate": 9}},
    )
    _write_json(
        tmp_path / "entity_resolution_cluster_ai_effect_impact_summary.json",
        {"canonical_outputs_mutated": False, "merge_impact": {"projected_event_reduction": 7}},
    )
    _write_json(
        tmp_path / "entity_resolution_cluster_ai_effects_plan_ready_subset.json",
        {"canonical_outputs_mutated": False, "selected_merge_effect_count": 2, "excluded_merge_effect_count": 1},
    )
    _write_json(
        tmp_path / "entity_resolution_cluster_ai_shadow_override_effect_impact_summary.json",
        {"canonical_outputs_mutated": False, "merge_impact": {"projected_event_reduction": 5}},
    )
    _write_json(
        tmp_path / "entity_resolution_cluster_ai_shadow_override_subset_preview_apply_report.json",
        {"canonical_outputs_mutated": False, "effects_applied": 2, "projected_event_reduction": 5},
    )
    _write_json(
        tmp_path / "entity_resolution_cluster_ai_shadow_override_subset_preview_output_check.json",
        {"canonical_outputs_mutated": False, "valid": True, "row_count": 995, "preview_merge_count": 2},
    )
    _write_json(
        tmp_path / "entity_resolution_cluster_policy_body_preview_check.json",
        {"canonical_outputs_mutated": False, "valid": True, "policy_body_preview_count": 2},
    )
    _write_json(
        tmp_path / "entity_resolution_cluster_canonical_apply_readiness.json",
        {
            "canonical_outputs_mutated": False,
            "ready_for_canonical_apply": False,
            "canonical_apply_blocker_count": 4,
        },
    )
    _write_json(
        tmp_path / "entity_resolution_cluster_blocker_priority_queue.json",
        {
            "canonical_outputs_mutated": False,
            "summary": {
                "queue_item_count": 20,
                "skipped_already_selected_count": 2,
                "triage_bucket_counts": {"time_format_review": 12, "coordinate_conflict_review": 8},
                "risk_tier_counts": {"medium": 12, "high": 8},
            },
        },
    )
    _write_json(
        tmp_path / "entity_resolution_cluster_time_normalization_analysis.json",
        {
            "canonical_outputs_mutated": False,
            "summary": {
                "analyzed_item_count": 12,
                "classification_counts": {"nearby_exact_minutes_15m_or_less": 7, "multiple_distinct_exact_minutes": 5},
                "review_risk_tier_counts": {"lower": 7, "high": 5},
            },
        },
    )
    _write_json(
        tmp_path / "entity_resolution_cluster_time_norm_shadow_override_subset.json",
        {
            "canonical_outputs_mutated": False,
            "selected_merge_effect_count": 8,
            "time_norm_override_selected_merge_effect_count": 6,
            "excluded_merge_effect_count": 4,
        },
    )
    _write_json(
        tmp_path / "entity_resolution_cluster_time_norm_shadow_override_effect_impact_summary.json",
        {"canonical_outputs_mutated": False, "merge_impact": {"projected_event_reduction": 9}},
    )
    _write_json(
        tmp_path / "entity_resolution_cluster_time_norm_shadow_override_subset_preview_apply_report.json",
        {
            "canonical_outputs_mutated": False,
            "effects_applied": 8,
            "effects_blocked": 0,
            "projected_event_reduction": 9,
        },
    )
    _write_json(
        tmp_path / "entity_resolution_cluster_time_norm_shadow_override_subset_preview_output_check.json",
        {"canonical_outputs_mutated": False, "valid": True, "row_count": 991, "preview_merge_count": 8},
    )
    _write_json(
        tmp_path / "entity_resolution_cluster_time_norm_source_review_recommendations.json",
        {
            "canonical_outputs_mutated": False,
            "summary": {
                "recommended_same_event_count": 5,
                "needs_more_evidence_count": 2,
                "recommendation_counts": {"recommend_same_event": 5, "needs_more_evidence": 2},
                "token_class_counts": {"clean_clock_tokens": 6, "symbolic_or_shorthand_tokens": 1},
                "projected_event_reduction_by_recommendation": {
                    "recommend_same_event": 8,
                    "needs_more_evidence": 3,
                },
            },
        },
    )
    _write_json(
        tmp_path / "entity_resolution_cluster_time_norm_recommended_effects_plan.json",
        {"canonical_outputs_mutated": False, "planned_effect_count": 5},
    )
    _write_json(
        tmp_path / "entity_resolution_cluster_time_norm_recommended_preview_apply_report.json",
        {
            "canonical_outputs_mutated": False,
            "effects_applied": 5,
            "effects_blocked": 0,
            "projected_event_reduction": 8,
        },
    )
    _write_json(
        tmp_path / "entity_resolution_cluster_time_norm_recommended_preview_output_check.json",
        {"canonical_outputs_mutated": False, "valid": True, "row_count": 992, "preview_merge_count": 5},
    )
    _write_json(
        tmp_path / "entity_resolution_cluster_time_norm_combined_plus_likely_plus_single_exact_context_accepted_decisions_report.json",
        {
            "canonical_outputs_mutated": False,
            "clean_decision_count": 5,
            "shorthand_decision_count": 2,
            "likely_time_format_decision_count": 3,
            "single_exact_context_decision_count": 4,
            "combined_decision_count": 14,
            "projected_event_reduction": 20,
        },
    )
    _write_json(
        tmp_path / "entity_resolution_cluster_time_norm_combined_plus_likely_plus_single_exact_context_effects_plan.json",
        {"canonical_outputs_mutated": False, "planned_effect_count": 14},
    )
    _write_json(
        tmp_path / "entity_resolution_cluster_time_norm_combined_plus_likely_plus_single_exact_context_canonical_body_dry_run_check.json",
        {"canonical_outputs_mutated": False, "valid": True, "dry_run_row_count": 14},
    )
    _write_json(
        tmp_path / "entity_resolution_cluster_time_norm_combined_plus_likely_plus_single_exact_context_canonical_apply_output_check.json",
        {
            "canonical_outputs_mutated": False,
            "valid": True,
            "row_count": 980,
            "replacement_rows_found": 14,
            "suppressed_ids_found": 0,
        },
    )
    _write_json(
        tmp_path / "entity_resolution_remaining_lower_time_format_review.json",
        {
            "canonical_outputs_mutated": False,
            "summary": {
                "reviewed_item_count": 15,
                "review_recommendation_counts": {
                    "source_review_same_event_candidate": 6,
                    "remain_deferred": 9,
                },
                "projected_event_reduction_by_review_recommendation": {
                    "source_review_same_event_candidate": 12,
                    "remain_deferred": 17,
                },
            },
        },
    )
    _write_json(
        tmp_path / "entity_resolution_remaining_lower_time_format_decision_candidates_report.json",
        {
            "canonical_outputs_mutated": False,
            "ready_for_canonical_apply": False,
            "decision_candidate_count": 6,
            "projected_event_reduction": 12,
        },
    )
    _write_json(
        tmp_path / "entity_resolution_cluster_time_conflict_analysis.json",
        {
            "canonical_outputs_mutated": False,
            "summary": {
                "analyzed_item_count": 5,
                "classification_counts": {"nearby_exact_conflict_15m_or_less": 2, "wide_exact_conflict_over_60m": 3},
                "review_risk_tier_counts": {"lower": 2, "high": 3},
                "identity_consistency_counts": {"single_source_id_date_location": 4, "mixed_or_incomplete_identity": 1},
            },
        },
    )
    _write_json(
        tmp_path / "entity_resolution_cluster_type_conflict_analysis.json",
        {
            "canonical_outputs_mutated": False,
            "summary": {
                "analyzed_item_count": 4,
                "classification_counts": {"type_with_time_conflict": 3, "type_only_cross_family_conflict": 1},
                "review_risk_tier_counts": {"high": 4},
                "identity_consistency_counts": {"single_source_id_date_location": 3, "mixed_or_incomplete_identity": 1},
            },
        },
    )
    _write_json(
        tmp_path / "entity_resolution_cluster_coordinate_conflict_analysis.json",
        {
            "canonical_outputs_mutated": False,
            "summary": {
                "analyzed_item_count": 3,
                "classification_counts": {"coordinate_conflict_10_to_15km": 1, "coordinate_conflict_over_150km": 2},
                "review_risk_tier_counts": {"high": 3},
                "identity_consistency_counts": {"single_source_id_date_location": 3},
                "max_coordinate_distance_km": 250.0,
            },
        },
    )

    report = summarize_entity_resolution_lanes(reports_dir=tmp_path)

    assert report["canonical_outputs_mutated"] is False
    assert report["decisions_created"] is False
    assert report["benchmark"]["current_event_count"] == 1000
    assert report["benchmark"]["best_override_projected_event_reduction"] == 6
    assert report["benchmark"]["best_override_preview_event_count"] == 994
    worklist_lane = next(lane for lane in report["lanes"] if lane["lane"] == "worklist15000")
    assert worklist_lane["worklist_item_count"] == 150
    assert worklist_lane["override_projected_event_reduction"] == 6
    assert worklist_lane["override_preview_valid"] is True
    cluster_lane = next(lane for lane in report["lanes"] if lane["lane"] == "cluster_ai_conservative")
    assert cluster_lane["current_event_count"] == 1000
    assert cluster_lane["review_packet_items"] == 12
    assert cluster_lane["same_event_suggestions"] == 3
    assert cluster_lane["impact_projected_event_reduction"] == 7
    assert cluster_lane["readiness_selected_merge_effects"] == 2
    assert cluster_lane["override_subset_projected_event_reduction"] == 5
    assert cluster_lane["override_projected_event_reduction"] == 5
    assert cluster_lane["override_preview_event_count"] == 995
    assert cluster_lane["override_preview_valid"] is True
    assert cluster_lane["policy_body_preview_count"] == 2
    assert cluster_lane["policy_body_preview_valid"] is True
    assert cluster_lane["ready_for_canonical_apply"] is False
    assert cluster_lane["canonical_apply_blocker_count"] == 4
    assert cluster_lane["blocker_priority_queue_items"] == 20
    assert cluster_lane["blocker_priority_skipped_already_selected"] == 2
    assert cluster_lane["blocker_priority_bucket_counts"] == {"time_format_review": 12, "coordinate_conflict_review": 8}
    assert cluster_lane["time_normalization_analyzed_items"] == 12
    assert cluster_lane["time_normalization_classification_counts"] == {
        "nearby_exact_minutes_15m_or_less": 7,
        "multiple_distinct_exact_minutes": 5,
    }
    assert cluster_lane["time_norm_override_selected_merge_effects"] == 8
    assert cluster_lane["time_norm_override_new_merge_effects"] == 6
    assert cluster_lane["time_norm_override_projected_event_reduction"] == 9
    assert cluster_lane["time_norm_override_preview_event_count"] == 991
    assert cluster_lane["time_norm_override_preview_valid"] is True
    assert cluster_lane["time_norm_source_recommend_same_event"] == 5
    assert cluster_lane["time_norm_source_needs_more_evidence"] == 2
    assert cluster_lane["time_norm_source_recommendation_counts"] == {
        "recommend_same_event": 5,
        "needs_more_evidence": 2,
    }
    assert cluster_lane["time_norm_source_token_class_counts"] == {
        "clean_clock_tokens": 6,
        "symbolic_or_shorthand_tokens": 1,
    }
    assert cluster_lane["time_norm_source_projected_reduction_by_recommendation"] == {
        "recommend_same_event": 8,
        "needs_more_evidence": 3,
    }
    assert cluster_lane["time_norm_recommended_planned_effects"] == 5
    assert cluster_lane["time_norm_recommended_effects_applied"] == 5
    assert cluster_lane["time_norm_recommended_effects_blocked"] == 0
    assert cluster_lane["time_norm_recommended_projected_event_reduction"] == 8
    assert cluster_lane["time_norm_recommended_preview_event_count"] == 992
    assert cluster_lane["time_norm_recommended_preview_merge_rows"] == 5
    assert cluster_lane["time_norm_recommended_preview_valid"] is True
    assert cluster_lane["time_norm_combined_clean_decision_count"] == 5
    assert cluster_lane["time_norm_combined_shorthand_decision_count"] == 2
    assert cluster_lane["time_norm_combined_likely_time_format_decision_count"] == 3
    assert cluster_lane["time_norm_combined_single_exact_context_decision_count"] == 4
    assert cluster_lane["time_norm_combined_decision_count"] == 14
    assert cluster_lane["time_norm_combined_projected_event_reduction"] == 20
    assert cluster_lane["time_norm_combined_planned_effects"] == 14
    assert cluster_lane["time_norm_combined_body_dry_run_rows"] == 14
    assert cluster_lane["time_norm_combined_body_dry_run_valid"] is True
    assert cluster_lane["time_norm_combined_apply_output_event_count"] == 980
    assert cluster_lane["time_norm_combined_apply_replacement_rows"] == 14
    assert cluster_lane["time_norm_combined_apply_suppressed_ids_found"] == 0
    assert cluster_lane["time_norm_combined_apply_output_valid"] is True
    assert cluster_lane["remaining_lower_time_format_reviewed_items"] == 15
    assert cluster_lane["remaining_lower_time_format_candidate_count"] == 6
    assert cluster_lane["remaining_lower_time_format_deferred_count"] == 9
    assert cluster_lane["remaining_lower_time_format_projected_reduction_by_recommendation"] == {
        "source_review_same_event_candidate": 12,
        "remain_deferred": 17,
    }
    assert cluster_lane["remaining_lower_time_format_decision_candidate_records"] == 6
    assert cluster_lane["remaining_lower_time_format_decision_candidate_projected_reduction"] == 12
    assert cluster_lane["remaining_lower_time_format_decision_candidate_ready_for_canonical_apply"] is False
    assert cluster_lane["time_conflict_analyzed_items"] == 5
    assert cluster_lane["time_conflict_classification_counts"] == {
        "nearby_exact_conflict_15m_or_less": 2,
        "wide_exact_conflict_over_60m": 3,
    }
    assert cluster_lane["time_conflict_identity_consistency_counts"] == {
        "single_source_id_date_location": 4,
        "mixed_or_incomplete_identity": 1,
    }
    assert cluster_lane["type_conflict_analyzed_items"] == 4
    assert cluster_lane["type_conflict_classification_counts"] == {
        "type_with_time_conflict": 3,
        "type_only_cross_family_conflict": 1,
    }
    assert cluster_lane["type_conflict_risk_tier_counts"] == {"high": 4}
    assert cluster_lane["coordinate_conflict_analyzed_items"] == 3
    assert cluster_lane["coordinate_conflict_classification_counts"] == {
        "coordinate_conflict_10_to_15km": 1,
        "coordinate_conflict_over_150km": 2,
    }
    assert cluster_lane["coordinate_conflict_max_distance_km"] == 250.0
