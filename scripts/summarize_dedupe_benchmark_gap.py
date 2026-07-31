"""Consolidate canonical dedupe math against an external benchmark count.

This does not infer or apply merges. It collects existing report-only outputs
into one reproducible gap summary so benchmark discussions stay grounded in the
current corpus and current estimator limits.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_IMPORT_REPORT = Path("data/reports/canonical_full/canonical_import_report.json")
DEFAULT_CLUSTER_REPORT = Path("data/reports/duplicate_candidate_cluster_summary.json")
DEFAULT_EXPANDED_REPORT = Path("data/reports/expanded_dedupe_opportunity_report.json")
DEFAULT_AI_IMPACT_REPORT = Path("data/reports/manual_review_ai_effect_impact_summary.json")
DEFAULT_OUTPUT = Path("data/reports/dedupe_benchmark_gap_summary.json")
DEFAULT_BENCHMARK_COUNT = 618_316


def summarize_dedupe_benchmark_gap(
    *,
    import_report_path: Path = DEFAULT_IMPORT_REPORT,
    cluster_report_path: Path = DEFAULT_CLUSTER_REPORT,
    expanded_report_path: Path = DEFAULT_EXPANDED_REPORT,
    ai_impact_report_path: Path = DEFAULT_AI_IMPACT_REPORT,
    benchmark_count: int = DEFAULT_BENCHMARK_COUNT,
) -> dict[str, Any]:
    import_report = read_json(import_report_path)
    cluster_report = read_json(cluster_report_path)
    expanded_report = read_json(expanded_report_path)
    ai_impact_report = read_json(ai_impact_report_path)

    source_record_count = int_value(import_report.get("source_record_count"))
    current_event_count = int_value(import_report.get("deduped_event_count"))
    exact_reduction = max(0, source_record_count - current_event_count)
    ai_projected_reduction = int_value(
        nested_get(ai_impact_report, ("merge_impact", "projected_event_reduction"))
    )
    conservative_reduction = int_value(
        nested_get(expanded_report, ("tier_union_reduction_estimates", "conservative", "projected_event_reduction"))
    )
    moderate_reduction = int_value(
        nested_get(expanded_report, ("tier_union_reduction_estimates", "moderate", "projected_event_reduction"))
    )
    exploratory_reduction = int_value(
        nested_get(expanded_report, ("tier_union_reduction_estimates", "exploratory", "projected_event_reduction"))
    )
    aggressive_reduction = int_value(
        nested_get(expanded_report, ("tier_union_reduction_estimates", "aggressive", "projected_event_reduction"))
    )

    projections = {
        "current_gap_to_benchmark": gap(current_event_count, benchmark_count),
        "after_ai_assisted_plan_naive": {
            "projected_event_count": max(0, current_event_count - ai_projected_reduction),
            "gap_to_benchmark": gap(current_event_count - ai_projected_reduction, benchmark_count),
            "overlap_warning": "Do not add this to expanded estimator reductions without an event-level union.",
        },
        "after_expanded_conservative_estimate": {
            "projected_event_count": max(0, current_event_count - conservative_reduction),
            "gap_to_benchmark": gap(current_event_count - conservative_reduction, benchmark_count),
        },
        "after_expanded_moderate_estimate": {
            "projected_event_count": max(0, current_event_count - moderate_reduction),
            "gap_to_benchmark": gap(current_event_count - moderate_reduction, benchmark_count),
        },
        "after_expanded_exploratory_estimate": {
            "projected_event_count": max(0, current_event_count - exploratory_reduction),
            "gap_to_benchmark": gap(current_event_count - exploratory_reduction, benchmark_count),
        },
        "after_expanded_aggressive_estimate": {
            "projected_event_count": max(0, current_event_count - aggressive_reduction),
            "gap_to_benchmark": gap(current_event_count - aggressive_reduction, benchmark_count),
        },
    }

    return {
        "schema_version": 1,
        "report_policy": "consolidated_analysis_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "inputs": {
            "canonical_import_report": str(import_report_path),
            "duplicate_candidate_cluster_summary": str(cluster_report_path),
            "expanded_dedupe_opportunity_report": str(expanded_report_path),
            "manual_review_ai_effect_impact_summary": str(ai_impact_report_path),
        },
        "benchmark": {
            "label": "UFOSINT screenshot sighting count",
            "event_count": benchmark_count,
            "methodology_known": False,
        },
        "current_corpus": {
            "source_record_count": source_record_count,
            "current_deduped_event_count": current_event_count,
            "current_exact_duplicate_record_reduction": exact_reduction,
            "retained_source_files": import_report.get("retained_source_files") or [],
            "exact_subset_drop_files": import_report.get("exact_subset_drop_files") or {},
        },
        "current_candidate_queue": {
            "candidate_edge_count": int_value(cluster_report.get("candidate_edge_count")),
            "candidate_cluster_count": int_value(cluster_report.get("candidate_cluster_count")),
            "projected_cluster_reduction_if_all_edges_same_event": int_value(
                cluster_report.get("projected_cluster_reduction_if_all_edges_same_event")
            ),
            "dense_pair_capacity_waste": int_value(cluster_report.get("dense_pair_capacity_waste")),
            "candidate_limit_reached": bool(import_report.get("duplicate_candidate_limit_reached")),
        },
        "report_only_reduction_estimates": {
            "ai_assisted_plan_projected_reduction": ai_projected_reduction,
            "expanded_conservative_projected_reduction": conservative_reduction,
            "expanded_moderate_projected_reduction": moderate_reduction,
            "expanded_exploratory_projected_reduction": exploratory_reduction,
            "expanded_aggressive_projected_reduction": aggressive_reduction,
        },
        "projections": projections,
        "consistency_checks": {
            "expanded_report_source_records_match_import_report": int_value(
                nested_get(expanded_report, ("scan_counts", "scanned_source_records"))
            )
            == source_record_count,
            "expanded_report_current_events_match_import_report": int_value(
                nested_get(expanded_report, ("current_canonical_counts", "current_event_count"))
            )
            == current_event_count,
            "ai_impact_scanned_event_count_matches_import_report": int_value(
                ai_impact_report.get("scanned_event_count")
            )
            == current_event_count,
        },
        "notes": [
            "The benchmark count is external and methodology-unknown.",
            "Projected reductions are not approved merges.",
            "The AI-assisted plan and expanded estimator may overlap; do not sum them without an event-level union.",
            "Matching 618316 would require a broader validated entity-resolution pass beyond the strongest current report-only keys.",
        ],
    }


def gap(event_count: int, benchmark_count: int) -> int:
    return max(0, event_count - benchmark_count)


def nested_get(payload: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical-import-report", type=Path, default=DEFAULT_IMPORT_REPORT)
    parser.add_argument("--duplicate-cluster-report", type=Path, default=DEFAULT_CLUSTER_REPORT)
    parser.add_argument("--expanded-opportunity-report", type=Path, default=DEFAULT_EXPANDED_REPORT)
    parser.add_argument("--ai-impact-report", type=Path, default=DEFAULT_AI_IMPACT_REPORT)
    parser.add_argument("--benchmark-count", type=int, default=DEFAULT_BENCHMARK_COUNT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = summarize_dedupe_benchmark_gap(
        import_report_path=args.canonical_import_report,
        cluster_report_path=args.duplicate_cluster_report,
        expanded_report_path=args.expanded_opportunity_report,
        ai_impact_report_path=args.ai_impact_report,
        benchmark_count=args.benchmark_count,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "current_deduped_event_count": report["current_corpus"]["current_deduped_event_count"],
                "benchmark_count": report["benchmark"]["event_count"],
                "current_gap_to_benchmark": report["projections"]["current_gap_to_benchmark"],
                "gap_after_expanded_conservative_estimate": report["projections"][
                    "after_expanded_conservative_estimate"
                ]["gap_to_benchmark"],
                "gap_after_expanded_aggressive_estimate": report["projections"][
                    "after_expanded_aggressive_estimate"
                ]["gap_to_benchmark"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
