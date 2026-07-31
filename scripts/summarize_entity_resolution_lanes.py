"""Summarize report-only entity-resolution review lanes.

This compares the baseline, sampled, worklist, and cluster ER lanes without
creating decisions, applying merges, or mutating canonical outputs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_REPORTS_DIR = Path("data/reports")
DEFAULT_OUTPUT = Path("data/reports/entity_resolution_lane_comparison.json")
UFOSINT_SCREENSHOT_BENCHMARK = 618_316

LANE_SPECS = [
    {
        "lane": "baseline_200",
        "label": "Original 200-row review packet",
        "score_report": "entity_resolution_score_report.json",
        "review_packet": "entity_resolution_review_packet.json",
        "suggestions_report": "entity_resolution_review_suggestions_report.json",
        "effects_plan": "entity_resolution_ai_effects_plan.json",
        "impact_summary": "entity_resolution_ai_effect_impact_summary.json",
        "readiness": "entity_resolution_ai_merge_readiness.json",
        "ready_subset": "entity_resolution_ai_effects_plan_ready_subset.json",
        "blocked_analysis": "entity_resolution_blocked_merge_analysis.json",
        "override_subset": "entity_resolution_ai_effects_plan_shadow_override_subset.json",
        "ready_preview": "entity_resolution_ai_ready_subset_preview_apply_report.json",
        "ready_output_check": "entity_resolution_ai_ready_subset_preview_output_check.json",
        "override_preview": "entity_resolution_ai_shadow_override_subset_preview_apply_report.json",
        "override_output_check": "entity_resolution_ai_shadow_override_subset_preview_output_check.json",
        "delta_summary": "entity_resolution_shadow_override_delta_summary.json",
        "apply_readiness": "entity_resolution_canonical_apply_readiness.json",
        "policy_body_check": "entity_resolution_policy_body_preview_check.json",
        "priority_queue": None,
        "time_normalization_analysis": None,
        "time_norm_override_subset": None,
        "time_norm_override_impact_summary": None,
        "time_norm_override_preview": None,
        "time_norm_override_output_check": None,
        "time_conflict_analysis": None,
        "type_conflict_analysis": None,
        "coordinate_conflict_analysis": None,
        "time_norm_source_recommendations": None,
        "time_norm_recommended_effects_plan": None,
        "time_norm_recommended_preview": None,
        "time_norm_recommended_output_check": None,
        "time_norm_combined_accepted_report": None,
        "time_norm_combined_effects_plan": None,
        "time_norm_combined_body_check": None,
        "time_norm_combined_apply_output_check": None,
        "remaining_lower_time_format_review": None,
        "remaining_lower_time_format_decision_candidates_report": None,
    },
    {
        "lane": "samples500",
        "label": "500 retained samples per band",
        "score_report": "entity_resolution_score_report_samples500.json",
        "review_packet": "entity_resolution_review_packet_samples500.json",
        "suggestions_report": "entity_resolution_review_suggestions_samples500_report.json",
        "effects_plan": "entity_resolution_ai_effects_plan_samples500.json",
        "impact_summary": "entity_resolution_ai_effect_impact_samples500_summary.json",
        "readiness": "entity_resolution_ai_merge_readiness_samples500.json",
        "ready_subset": "entity_resolution_ai_effects_plan_ready_subset_samples500.json",
        "blocked_analysis": "entity_resolution_blocked_merge_analysis_samples500.json",
        "override_subset": "entity_resolution_ai_effects_plan_shadow_override_subset_samples500.json",
        "ready_preview": None,
        "ready_output_check": None,
        "override_preview": "entity_resolution_ai_shadow_override_subset_samples500_preview_apply_report.json",
        "override_output_check": "entity_resolution_ai_shadow_override_subset_samples500_preview_output_check.json",
        "delta_summary": None,
        "apply_readiness": None,
        "policy_body_check": None,
        "priority_queue": None,
        "time_normalization_analysis": None,
        "time_norm_override_subset": None,
        "time_norm_override_impact_summary": None,
        "time_norm_override_preview": None,
        "time_norm_override_output_check": None,
        "time_conflict_analysis": None,
        "type_conflict_analysis": None,
        "coordinate_conflict_analysis": None,
        "time_norm_source_recommendations": None,
        "time_norm_recommended_effects_plan": None,
        "time_norm_recommended_preview": None,
        "time_norm_recommended_output_check": None,
        "time_norm_combined_accepted_report": None,
        "time_norm_combined_effects_plan": None,
        "time_norm_combined_body_check": None,
        "time_norm_combined_apply_output_check": None,
        "remaining_lower_time_format_review": None,
        "remaining_lower_time_format_decision_candidates_report": None,
    },
    {
        "lane": "samples1000",
        "label": "1000 retained samples per band",
        "score_report": "entity_resolution_score_report_samples1000.json",
        "review_packet": "entity_resolution_review_packet_samples1000.json",
        "suggestions_report": "entity_resolution_review_suggestions_samples1000_report.json",
        "effects_plan": "entity_resolution_ai_effects_plan_samples1000.json",
        "impact_summary": "entity_resolution_ai_effect_impact_samples1000_summary.json",
        "readiness": "entity_resolution_ai_merge_readiness_samples1000.json",
        "ready_subset": "entity_resolution_ai_effects_plan_ready_subset_samples1000.json",
        "blocked_analysis": "entity_resolution_blocked_merge_analysis_samples1000.json",
        "override_subset": "entity_resolution_ai_effects_plan_shadow_override_subset_samples1000.json",
        "ready_preview": None,
        "ready_output_check": None,
        "override_preview": "entity_resolution_ai_shadow_override_subset_samples1000_preview_apply_report.json",
        "override_output_check": "entity_resolution_ai_shadow_override_subset_samples1000_preview_output_check.json",
        "delta_summary": None,
        "apply_readiness": None,
        "policy_body_check": None,
        "priority_queue": None,
        "time_normalization_analysis": None,
        "time_norm_override_subset": None,
        "time_norm_override_impact_summary": None,
        "time_norm_override_preview": None,
        "time_norm_override_output_check": None,
        "time_conflict_analysis": None,
        "type_conflict_analysis": None,
        "coordinate_conflict_analysis": None,
        "time_norm_source_recommendations": None,
        "time_norm_recommended_effects_plan": None,
        "time_norm_recommended_preview": None,
        "time_norm_recommended_output_check": None,
        "time_norm_combined_accepted_report": None,
        "time_norm_combined_effects_plan": None,
        "time_norm_combined_body_check": None,
        "time_norm_combined_apply_output_check": None,
        "remaining_lower_time_format_review": None,
        "remaining_lower_time_format_decision_candidates_report": None,
    },
    {
        "lane": "worklist15000",
        "label": "15000-row worklist-backed review packet",
        "score_report": "entity_resolution_score_report_with_worklist.json",
        "review_packet": "entity_resolution_review_packet_worklist.json",
        "suggestions_report": "entity_resolution_review_suggestions_worklist_report.json",
        "effects_plan": "entity_resolution_ai_effects_plan_worklist.json",
        "impact_summary": "entity_resolution_ai_effect_impact_worklist_summary.json",
        "readiness": "entity_resolution_ai_merge_readiness_worklist.json",
        "ready_subset": "entity_resolution_ai_effects_plan_ready_subset_worklist.json",
        "blocked_analysis": "entity_resolution_blocked_merge_analysis_worklist.json",
        "override_subset": "entity_resolution_ai_effects_plan_shadow_override_subset_worklist.json",
        "ready_preview": "entity_resolution_ai_ready_subset_worklist_preview_apply_report.json",
        "ready_output_check": "entity_resolution_ai_ready_subset_worklist_preview_output_check.json",
        "override_preview": "entity_resolution_ai_shadow_override_subset_worklist_preview_apply_report.json",
        "override_output_check": "entity_resolution_ai_shadow_override_subset_worklist_preview_output_check.json",
        "delta_summary": "entity_resolution_shadow_override_delta_worklist_summary.json",
        "apply_readiness": "entity_resolution_canonical_apply_readiness_worklist.json",
        "policy_body_check": "entity_resolution_policy_body_preview_worklist_check.json",
        "priority_queue": None,
        "time_normalization_analysis": None,
        "time_norm_override_subset": None,
        "time_norm_override_impact_summary": None,
        "time_norm_override_preview": None,
        "time_norm_override_output_check": None,
        "override_impact_summary": None,
        "time_conflict_analysis": None,
        "type_conflict_analysis": None,
        "coordinate_conflict_analysis": None,
        "time_norm_source_recommendations": None,
        "time_norm_recommended_effects_plan": None,
        "time_norm_recommended_preview": None,
        "time_norm_recommended_output_check": None,
        "time_norm_combined_accepted_report": None,
        "time_norm_combined_effects_plan": None,
        "time_norm_combined_body_check": None,
        "time_norm_combined_apply_output_check": None,
        "remaining_lower_time_format_review": None,
        "remaining_lower_time_format_decision_candidates_report": None,
    },
    {
        "lane": "cluster_ai_conservative",
        "label": "Conservative cluster suggestion lane",
        "score_report": None,
        "review_packet": "entity_resolution_cluster_review_packet.json",
        "suggestions_report": "entity_resolution_cluster_review_suggestions_report.json",
        "effects_plan": "entity_resolution_cluster_ai_effects_plan.json",
        "impact_summary": "entity_resolution_cluster_ai_effect_impact_summary.json",
        "readiness": "entity_resolution_cluster_ai_merge_readiness.json",
        "ready_subset": "entity_resolution_cluster_ai_effects_plan_ready_subset.json",
        "blocked_analysis": "entity_resolution_cluster_blocked_merge_analysis.json",
        "override_subset": "entity_resolution_cluster_ai_effects_plan_shadow_override_subset.json",
        "ready_preview": None,
        "ready_output_check": None,
        "override_preview": "entity_resolution_cluster_ai_shadow_override_subset_preview_apply_report.json",
        "override_output_check": "entity_resolution_cluster_ai_shadow_override_subset_preview_output_check.json",
        "delta_summary": None,
        "apply_readiness": "entity_resolution_cluster_canonical_apply_readiness.json",
        "policy_body_check": "entity_resolution_cluster_policy_body_preview_check.json",
        "priority_queue": "entity_resolution_cluster_blocker_priority_queue.json",
        "time_normalization_analysis": "entity_resolution_cluster_time_normalization_analysis.json",
        "time_norm_override_subset": "entity_resolution_cluster_time_norm_shadow_override_subset.json",
        "time_norm_override_impact_summary": "entity_resolution_cluster_time_norm_shadow_override_effect_impact_summary.json",
        "time_norm_override_preview": "entity_resolution_cluster_time_norm_shadow_override_subset_preview_apply_report.json",
        "time_norm_override_output_check": "entity_resolution_cluster_time_norm_shadow_override_subset_preview_output_check.json",
        "override_impact_summary": "entity_resolution_cluster_ai_shadow_override_effect_impact_summary.json",
        "time_conflict_analysis": "entity_resolution_cluster_time_conflict_analysis.json",
        "type_conflict_analysis": "entity_resolution_cluster_type_conflict_analysis.json",
        "coordinate_conflict_analysis": "entity_resolution_cluster_coordinate_conflict_analysis.json",
        "time_norm_source_recommendations": "entity_resolution_cluster_time_norm_source_review_recommendations.json",
        "time_norm_recommended_effects_plan": "entity_resolution_cluster_time_norm_recommended_effects_plan.json",
        "time_norm_recommended_preview": "entity_resolution_cluster_time_norm_recommended_preview_apply_report.json",
        "time_norm_recommended_output_check": "entity_resolution_cluster_time_norm_recommended_preview_output_check.json",
        "time_norm_combined_accepted_report": "entity_resolution_cluster_time_norm_combined_plus_likely_plus_single_exact_context_accepted_decisions_report.json",
        "time_norm_combined_effects_plan": "entity_resolution_cluster_time_norm_combined_plus_likely_plus_single_exact_context_effects_plan.json",
        "time_norm_combined_body_check": "entity_resolution_cluster_time_norm_combined_plus_likely_plus_single_exact_context_canonical_body_dry_run_check.json",
        "time_norm_combined_apply_output_check": "entity_resolution_cluster_time_norm_combined_plus_likely_plus_single_exact_context_canonical_apply_output_check.json",
        "remaining_lower_time_format_review": "entity_resolution_remaining_lower_time_format_review.json",
        "remaining_lower_time_format_decision_candidates_report": "entity_resolution_remaining_lower_time_format_decision_candidates_report.json",
    },
]


def summarize_entity_resolution_lanes(*, reports_dir: Path = DEFAULT_REPORTS_DIR) -> dict[str, Any]:
    lanes = [summarize_lane(spec, reports_dir=reports_dir) for spec in LANE_SPECS]
    current_event_count = first_number(lanes, "current_event_count")
    best_override_reduction = max((number(lane.get("override_projected_event_reduction")) or 0) for lane in lanes)
    best_preview_row_count = min(
        (value for lane in lanes if (value := number(lane.get("override_preview_event_count"))) is not None),
        default=None,
    )
    return {
        "schema_version": 1,
        "summary_policy": "entity_resolution_lane_comparison_report_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "reports_dir": str(reports_dir),
        "benchmark": {
            "ufosint_screenshot_sightings": UFOSINT_SCREENSHOT_BENCHMARK,
            "current_event_count": current_event_count,
            "best_override_projected_event_reduction": best_override_reduction,
            "best_override_preview_event_count": best_preview_row_count,
            "remaining_gap_after_best_override_preview": (
                best_preview_row_count - UFOSINT_SCREENSHOT_BENCHMARK
                if best_preview_row_count is not None
                else None
            ),
        },
        "lanes": lanes,
    }


def summarize_lane(spec: dict[str, Any], *, reports_dir: Path) -> dict[str, Any]:
    artifacts = {key: read_report(reports_dir, path) for key, path in spec.items() if key not in {"lane", "label"}}
    score_report = artifacts.get("score_report", {})
    review_packet = artifacts.get("review_packet", {})
    suggestions_report = artifacts.get("suggestions_report", {})
    effects_plan = artifacts.get("effects_plan", {})
    impact_summary = artifacts.get("impact_summary", {})
    readiness = artifacts.get("readiness", {})
    ready_subset = artifacts.get("ready_subset", {})
    blocked_analysis = artifacts.get("blocked_analysis", {})
    override_subset = artifacts.get("override_subset", {})
    ready_preview = artifacts.get("ready_preview", {})
    ready_output_check = artifacts.get("ready_output_check", {})
    override_preview = artifacts.get("override_preview", {})
    override_output_check = artifacts.get("override_output_check", {})
    delta_summary = artifacts.get("delta_summary", {})
    apply_readiness = artifacts.get("apply_readiness", {})
    policy_body_check = artifacts.get("policy_body_check", {})
    priority_queue = artifacts.get("priority_queue", {})
    time_normalization_analysis = artifacts.get("time_normalization_analysis", {})
    time_norm_override_subset = artifacts.get("time_norm_override_subset", {})
    time_norm_override_impact_summary = artifacts.get("time_norm_override_impact_summary", {})
    time_norm_override_preview = artifacts.get("time_norm_override_preview", {})
    time_norm_override_output_check = artifacts.get("time_norm_override_output_check", {})
    override_impact_summary = artifacts.get("override_impact_summary", {})
    time_conflict_analysis = artifacts.get("time_conflict_analysis", {})
    type_conflict_analysis = artifacts.get("type_conflict_analysis", {})
    coordinate_conflict_analysis = artifacts.get("coordinate_conflict_analysis", {})
    time_norm_source_recommendations = artifacts.get("time_norm_source_recommendations", {})
    time_norm_recommended_effects_plan = artifacts.get("time_norm_recommended_effects_plan", {})
    time_norm_recommended_preview = artifacts.get("time_norm_recommended_preview", {})
    time_norm_recommended_output_check = artifacts.get("time_norm_recommended_output_check", {})
    time_norm_combined_accepted_report = artifacts.get("time_norm_combined_accepted_report", {})
    time_norm_combined_effects_plan = artifacts.get("time_norm_combined_effects_plan", {})
    time_norm_combined_body_check = artifacts.get("time_norm_combined_body_check", {})
    time_norm_combined_apply_output_check = artifacts.get("time_norm_combined_apply_output_check", {})
    remaining_lower_time_format_review = artifacts.get("remaining_lower_time_format_review", {})
    remaining_lower_time_format_decision_candidates_report = artifacts.get(
        "remaining_lower_time_format_decision_candidates_report",
        {},
    )

    return {
        "lane": spec["lane"],
        "label": spec["label"],
        "current_event_count": get_nested(score_report, "current_corpus", "current_event_count")
        or get_nested(review_packet, "current_canonical_counts", "current_event_count"),
        "scored_pair_count": get_nested(score_report, "score_summary", "scored_pair_count"),
        "worklist_item_count": get_nested(score_report, "candidate_worklist_summary", "item_count"),
        "review_packet_items": get_nested(review_packet, "export_summary", "exported_item_count"),
        "same_event_suggestions": get_nested(suggestions_report, "suggested_decision_counts", "same_event"),
        "needs_more_evidence_suggestions": get_nested(suggestions_report, "suggested_decision_counts", "needs_more_evidence"),
        "merge_effect_count": get_nested(effects_plan, "effect_counts", "merge_entity_resolution_candidate"),
        "defer_effect_count": get_nested(effects_plan, "effect_counts", "defer_entity_resolution_candidate"),
        "impact_projected_event_reduction": get_nested(impact_summary, "merge_impact", "projected_event_reduction"),
        "readiness_selected_merge_effects": get_nested(ready_subset, "selected_merge_effect_count"),
        "readiness_blocked_merge_effects": get_nested(ready_subset, "excluded_merge_effect_count"),
        "readiness_blocking_conflicts": readiness.get("blocking_conflict_item_count"),
        "readiness_review_conflicts": readiness.get("review_conflict_item_count"),
        "blocked_classification_counts": blocked_analysis.get("classification_counts", {}),
        "shadow_override_candidates": blocked_analysis.get("high_confidence_shadow_override_candidate_count"),
        "override_selected_merge_effects": override_subset.get("selected_merge_effect_count"),
        "override_excluded_merge_effects": override_subset.get("excluded_merge_effect_count"),
        "override_subset_projected_event_reduction": get_nested(
            override_impact_summary,
            "merge_impact",
            "projected_event_reduction",
        ),
        "ready_effects_applied": ready_preview.get("effects_applied"),
        "ready_projected_event_reduction": ready_preview.get("projected_event_reduction"),
        "ready_preview_event_count": ready_output_check.get("row_count"),
        "ready_preview_valid": ready_output_check.get("valid"),
        "override_effects_applied": override_preview.get("effects_applied"),
        "override_projected_event_reduction": override_preview.get("projected_event_reduction"),
        "override_preview_event_count": override_output_check.get("row_count"),
        "override_preview_merge_rows": override_output_check.get("preview_merge_count"),
        "override_preview_valid": override_output_check.get("valid"),
        "incremental_override_reduction": delta_summary.get("incremental_projected_event_reduction"),
        "remaining_excluded_merge_effects": delta_summary.get("remaining_excluded_merge_effect_count"),
        "ready_for_canonical_apply": apply_readiness.get("ready_for_canonical_apply"),
        "canonical_apply_blocker_count": apply_readiness.get("canonical_apply_blocker_count"),
        "policy_body_preview_count": policy_body_check.get("policy_body_preview_count"),
        "policy_body_preview_valid": policy_body_check.get("valid"),
        "blocker_priority_queue_items": get_nested(priority_queue, "summary", "queue_item_count"),
        "blocker_priority_skipped_already_selected": get_nested(priority_queue, "summary", "skipped_already_selected_count"),
        "blocker_priority_bucket_counts": get_nested(priority_queue, "summary", "triage_bucket_counts") or {},
        "blocker_priority_risk_tier_counts": get_nested(priority_queue, "summary", "risk_tier_counts") or {},
        "time_normalization_analyzed_items": get_nested(time_normalization_analysis, "summary", "analyzed_item_count"),
        "time_normalization_classification_counts": get_nested(
            time_normalization_analysis,
            "summary",
            "classification_counts",
        )
        or {},
        "time_normalization_risk_tier_counts": get_nested(
            time_normalization_analysis,
            "summary",
            "review_risk_tier_counts",
        )
        or {},
        "time_norm_override_selected_merge_effects": time_norm_override_subset.get("selected_merge_effect_count"),
        "time_norm_override_new_merge_effects": time_norm_override_subset.get("time_norm_override_selected_merge_effect_count"),
        "time_norm_override_excluded_merge_effects": time_norm_override_subset.get("excluded_merge_effect_count"),
        "time_norm_override_subset_projected_reduction": get_nested(
            time_norm_override_impact_summary,
            "merge_impact",
            "projected_event_reduction",
        ),
        "time_norm_override_effects_applied": time_norm_override_preview.get("effects_applied"),
        "time_norm_override_effects_blocked": time_norm_override_preview.get("effects_blocked"),
        "time_norm_override_projected_event_reduction": time_norm_override_preview.get("projected_event_reduction"),
        "time_norm_override_preview_event_count": time_norm_override_output_check.get("row_count"),
        "time_norm_override_preview_merge_rows": time_norm_override_output_check.get("preview_merge_count"),
        "time_norm_override_preview_valid": time_norm_override_output_check.get("valid"),
        "time_norm_source_recommend_same_event": get_nested(
            time_norm_source_recommendations,
            "summary",
            "recommended_same_event_count",
        ),
        "time_norm_source_needs_more_evidence": get_nested(
            time_norm_source_recommendations,
            "summary",
            "needs_more_evidence_count",
        ),
        "time_norm_source_recommendation_counts": get_nested(
            time_norm_source_recommendations,
            "summary",
            "recommendation_counts",
        )
        or {},
        "time_norm_source_token_class_counts": get_nested(
            time_norm_source_recommendations,
            "summary",
            "token_class_counts",
        )
        or {},
        "time_norm_source_projected_reduction_by_recommendation": get_nested(
            time_norm_source_recommendations,
            "summary",
            "projected_event_reduction_by_recommendation",
        )
        or {},
        "time_norm_recommended_planned_effects": time_norm_recommended_effects_plan.get("planned_effect_count"),
        "time_norm_recommended_effects_applied": time_norm_recommended_preview.get("effects_applied"),
        "time_norm_recommended_effects_blocked": time_norm_recommended_preview.get("effects_blocked"),
        "time_norm_recommended_projected_event_reduction": time_norm_recommended_preview.get("projected_event_reduction"),
        "time_norm_recommended_preview_event_count": time_norm_recommended_output_check.get("row_count"),
        "time_norm_recommended_preview_merge_rows": time_norm_recommended_output_check.get("preview_merge_count"),
        "time_norm_recommended_preview_valid": time_norm_recommended_output_check.get("valid"),
        "time_norm_combined_clean_decision_count": time_norm_combined_accepted_report.get("clean_decision_count"),
        "time_norm_combined_shorthand_decision_count": time_norm_combined_accepted_report.get("shorthand_decision_count"),
        "time_norm_combined_likely_time_format_decision_count": time_norm_combined_accepted_report.get("likely_time_format_decision_count"),
        "time_norm_combined_single_exact_context_decision_count": time_norm_combined_accepted_report.get("single_exact_context_decision_count"),
        "time_norm_combined_decision_count": time_norm_combined_accepted_report.get("combined_decision_count"),
        "time_norm_combined_projected_event_reduction": time_norm_combined_accepted_report.get("projected_event_reduction"),
        "time_norm_combined_planned_effects": time_norm_combined_effects_plan.get("planned_effect_count"),
        "time_norm_combined_body_dry_run_rows": time_norm_combined_body_check.get("dry_run_row_count"),
        "time_norm_combined_body_dry_run_valid": time_norm_combined_body_check.get("valid"),
        "time_norm_combined_apply_output_event_count": time_norm_combined_apply_output_check.get("row_count"),
        "time_norm_combined_apply_replacement_rows": time_norm_combined_apply_output_check.get("replacement_rows_found"),
        "time_norm_combined_apply_suppressed_ids_found": time_norm_combined_apply_output_check.get("suppressed_ids_found"),
        "time_norm_combined_apply_output_valid": time_norm_combined_apply_output_check.get("valid"),
        "remaining_lower_time_format_reviewed_items": get_nested(
            remaining_lower_time_format_review,
            "summary",
            "reviewed_item_count",
        ),
        "remaining_lower_time_format_candidate_count": get_nested(
            remaining_lower_time_format_review,
            "summary",
            "review_recommendation_counts",
            "source_review_same_event_candidate",
        ),
        "remaining_lower_time_format_deferred_count": get_nested(
            remaining_lower_time_format_review,
            "summary",
            "review_recommendation_counts",
            "remain_deferred",
        ),
        "remaining_lower_time_format_projected_reduction_by_recommendation": get_nested(
            remaining_lower_time_format_review,
            "summary",
            "projected_event_reduction_by_review_recommendation",
        )
        or {},
        "remaining_lower_time_format_decision_candidate_records": remaining_lower_time_format_decision_candidates_report.get(
            "decision_candidate_count"
        ),
        "remaining_lower_time_format_decision_candidate_projected_reduction": remaining_lower_time_format_decision_candidates_report.get(
            "projected_event_reduction"
        ),
        "remaining_lower_time_format_decision_candidate_ready_for_canonical_apply": remaining_lower_time_format_decision_candidates_report.get(
            "ready_for_canonical_apply"
        ),
        "time_conflict_analyzed_items": get_nested(time_conflict_analysis, "summary", "analyzed_item_count"),
        "time_conflict_classification_counts": get_nested(
            time_conflict_analysis,
            "summary",
            "classification_counts",
        )
        or {},
        "time_conflict_risk_tier_counts": get_nested(
            time_conflict_analysis,
            "summary",
            "review_risk_tier_counts",
        )
        or {},
        "time_conflict_identity_consistency_counts": get_nested(
            time_conflict_analysis,
            "summary",
            "identity_consistency_counts",
        )
        or {},
        "type_conflict_analyzed_items": get_nested(type_conflict_analysis, "summary", "analyzed_item_count"),
        "type_conflict_classification_counts": get_nested(
            type_conflict_analysis,
            "summary",
            "classification_counts",
        )
        or {},
        "type_conflict_risk_tier_counts": get_nested(
            type_conflict_analysis,
            "summary",
            "review_risk_tier_counts",
        )
        or {},
        "type_conflict_identity_consistency_counts": get_nested(
            type_conflict_analysis,
            "summary",
            "identity_consistency_counts",
        )
        or {},
        "coordinate_conflict_analyzed_items": get_nested(
            coordinate_conflict_analysis,
            "summary",
            "analyzed_item_count",
        ),
        "coordinate_conflict_classification_counts": get_nested(
            coordinate_conflict_analysis,
            "summary",
            "classification_counts",
        )
        or {},
        "coordinate_conflict_risk_tier_counts": get_nested(
            coordinate_conflict_analysis,
            "summary",
            "review_risk_tier_counts",
        )
        or {},
        "coordinate_conflict_identity_consistency_counts": get_nested(
            coordinate_conflict_analysis,
            "summary",
            "identity_consistency_counts",
        )
        or {},
        "coordinate_conflict_max_distance_km": get_nested(
            coordinate_conflict_analysis,
            "summary",
            "max_coordinate_distance_km",
        ),
        "canonical_outputs_mutated": any(
            bool(report.get("canonical_outputs_mutated"))
            for report in artifacts.values()
            if isinstance(report, dict)
        ),
    }


def read_report(reports_dir: Path, filename: str | None) -> dict[str, Any]:
    if not filename:
        return {}
    path = reports_dir / filename
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def get_nested(payload: dict[str, Any], *keys: str) -> Any:
    value: Any = payload
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def number(value: Any) -> int | float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def first_number(items: list[dict[str, Any]], key: str) -> int | float | None:
    for item in items:
        value = number(item.get(key))
        if value is not None:
            return value
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = summarize_entity_resolution_lanes(reports_dir=args.reports_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "summary_policy": report["summary_policy"],
                "lane_count": len(report["lanes"]),
                "best_override_projected_event_reduction": report["benchmark"]["best_override_projected_event_reduction"],
                "remaining_gap_after_best_override_preview": report["benchmark"]["remaining_gap_after_best_override_preview"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
