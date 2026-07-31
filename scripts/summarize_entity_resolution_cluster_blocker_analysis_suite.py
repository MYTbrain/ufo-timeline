"""Summarize the cluster blocker analysis suite.

This report consolidates the review-only blocker queue, time-normalization
preview subset, and time/type/coordinate conflict analyses into a single
checkpoint. It does not create decisions, effects, previews, or canonical
mutations.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_PRIORITY_QUEUE = Path("data/reports/entity_resolution_cluster_blocker_priority_queue.json")
DEFAULT_TIME_NORM_SUBSET = Path("data/reports/entity_resolution_cluster_time_norm_shadow_override_subset.json")
DEFAULT_TIME_CONFLICT_ANALYSIS = Path("data/reports/entity_resolution_cluster_time_conflict_analysis.json")
DEFAULT_TYPE_CONFLICT_ANALYSIS = Path("data/reports/entity_resolution_cluster_type_conflict_analysis.json")
DEFAULT_COORDINATE_CONFLICT_ANALYSIS = Path("data/reports/entity_resolution_cluster_coordinate_conflict_analysis.json")
DEFAULT_JSON_OUTPUT = Path("data/reports/entity_resolution_cluster_blocker_analysis_suite_summary.json")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/entity_resolution_cluster_blocker_analysis_suite_summary.md")

SUMMARY_POLICY = "entity_resolution_cluster_blocker_analysis_suite_report_only"


def summarize_entity_resolution_cluster_blocker_analysis_suite(
    *,
    priority_queue: dict[str, Any],
    time_norm_subset: dict[str, Any],
    time_conflict_analysis: dict[str, Any],
    type_conflict_analysis: dict[str, Any],
    coordinate_conflict_analysis: dict[str, Any],
    inputs: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    validate_inputs(
        priority_queue=priority_queue,
        time_norm_subset=time_norm_subset,
        time_conflict_analysis=time_conflict_analysis,
        type_conflict_analysis=type_conflict_analysis,
        coordinate_conflict_analysis=coordinate_conflict_analysis,
    )
    queue_summary = priority_queue.get("summary") if isinstance(priority_queue.get("summary"), dict) else {}
    time_norm_selected = int(time_norm_subset.get("time_norm_override_selected_merge_effect_count") or 0)
    time_format_count = int((queue_summary.get("triage_bucket_counts") or {}).get("time_format_review") or 0)
    return {
        "schema_version": 1,
        "summary_policy": SUMMARY_POLICY,
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "auto_merge_performed": False,
        "override_decisions_created": False,
        "ready_for_canonical_apply": False,
        "inputs": inputs or {},
        "summary": {
            "queue_item_count": int(queue_summary.get("queue_item_count") or 0),
            "queue_triage_bucket_counts": queue_summary.get("triage_bucket_counts") or {},
            "strict_time_normalization_new_preview_candidates": time_norm_selected,
            "strict_time_normalization_remaining_time_format_items": max(0, time_format_count - time_norm_selected),
            "time_conflict_items": nested_int(time_conflict_analysis, "summary", "analyzed_item_count"),
            "time_conflict_high_risk_items": nested_int(
                time_conflict_analysis,
                "summary",
                "review_risk_tier_counts",
                "high",
            ),
            "type_conflict_items": nested_int(type_conflict_analysis, "summary", "analyzed_item_count"),
            "type_conflict_high_risk_items": nested_int(
                type_conflict_analysis,
                "summary",
                "review_risk_tier_counts",
                "high",
            ),
            "coordinate_conflict_items": nested_int(coordinate_conflict_analysis, "summary", "analyzed_item_count"),
            "coordinate_conflict_high_risk_items": nested_int(
                coordinate_conflict_analysis,
                "summary",
                "review_risk_tier_counts",
                "high",
            ),
        },
        "analysis_conclusion": {
            "preview_safe_new_candidate_class": "strict_time_normalization_only",
            "time_conflicts_preview_safe_under_current_gates": False,
            "type_conflicts_preview_safe_under_current_gates": False,
            "coordinate_conflicts_preview_safe_under_current_gates": False,
            "recommended_next_steps": [
                "Review the 44 strict time-normalization preview candidates against source rows before any canonical promotion.",
                "Do not create preview subsets from time/type/coordinate conflicts under the current evidence gates.",
                "If more reduction is needed, enrich source-row evidence for coordinate/time/type conflicts before lowering gates.",
            ],
        },
    }


def validate_inputs(
    *,
    priority_queue: dict[str, Any],
    time_norm_subset: dict[str, Any],
    time_conflict_analysis: dict[str, Any],
    type_conflict_analysis: dict[str, Any],
    coordinate_conflict_analysis: dict[str, Any],
) -> None:
    expected = [
        (priority_queue, "queue_policy", "entity_resolution_cluster_blocker_priority_queue_review_only"),
        (time_norm_subset, "subset_policy", "entity_resolution_cluster_time_normalization_shadow_preview_subset_v2"),
        (time_conflict_analysis, "analysis_policy", "entity_resolution_cluster_time_conflict_review_only"),
        (type_conflict_analysis, "analysis_policy", "entity_resolution_cluster_type_conflict_review_only"),
        (coordinate_conflict_analysis, "analysis_policy", "entity_resolution_cluster_coordinate_conflict_review_only"),
    ]
    errors = []
    for payload, key, expected_value in expected:
        if payload.get(key) != expected_value:
            errors.append(f"{key} must be {expected_value!r}")
    for name, payload in (
        ("priority_queue", priority_queue),
        ("time_norm_subset", time_norm_subset),
        ("time_conflict_analysis", time_conflict_analysis),
        ("type_conflict_analysis", type_conflict_analysis),
        ("coordinate_conflict_analysis", coordinate_conflict_analysis),
    ):
        for flag in ("canonical_outputs_mutated", "decisions_created", "auto_merge_performed"):
            if payload.get(flag) is not False:
                errors.append(f"{name}.{flag} must be false")
    if errors:
        raise ValueError("cluster blocker analysis suite inputs are unsafe: " + "; ".join(errors))


def nested_int(payload: dict[str, Any], *keys: str) -> int:
    value: Any = payload
    for key in keys:
        if not isinstance(value, dict):
            return 0
        value = value.get(key)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_markdown(path: Path, summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = summary.get("summary") if isinstance(summary.get("summary"), dict) else {}
    conclusion = summary.get("analysis_conclusion") if isinstance(summary.get("analysis_conclusion"), dict) else {}
    lines = [
        "# Cluster Blocker Analysis Suite Summary",
        "",
        "This checkpoint is report-only. It consolidates blocker triage without creating decisions or mutating canonical outputs.",
        "",
        "## Summary",
        "",
        f"- Queue items: `{data.get('queue_item_count', 0)}`",
        f"- Queue buckets: `{json.dumps(data.get('queue_triage_bucket_counts', {}), sort_keys=True)}`",
        f"- Strict time-normalization new preview candidates: `{data.get('strict_time_normalization_new_preview_candidates', 0)}`",
        f"- Remaining time-format review items after strict time-normalization candidates: `{data.get('strict_time_normalization_remaining_time_format_items', 0)}`",
        f"- Time-conflict high-risk items: `{data.get('time_conflict_high_risk_items', 0)} / {data.get('time_conflict_items', 0)}`",
        f"- Type-conflict high-risk items: `{data.get('type_conflict_high_risk_items', 0)} / {data.get('type_conflict_items', 0)}`",
        f"- Coordinate-conflict high-risk items: `{data.get('coordinate_conflict_high_risk_items', 0)} / {data.get('coordinate_conflict_items', 0)}`",
        "",
        "## Conclusion",
        "",
        f"- Preview-safe new candidate class: `{conclusion.get('preview_safe_new_candidate_class')}`",
    ]
    for step in conclusion.get("recommended_next_steps") or []:
        lines.append(f"- {step}")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--priority-queue", type=Path, default=DEFAULT_PRIORITY_QUEUE)
    parser.add_argument("--time-norm-subset", type=Path, default=DEFAULT_TIME_NORM_SUBSET)
    parser.add_argument("--time-conflict-analysis", type=Path, default=DEFAULT_TIME_CONFLICT_ANALYSIS)
    parser.add_argument("--type-conflict-analysis", type=Path, default=DEFAULT_TYPE_CONFLICT_ANALYSIS)
    parser.add_argument("--coordinate-conflict-analysis", type=Path, default=DEFAULT_COORDINATE_CONFLICT_ANALYSIS)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    inputs = {
        "priority_queue": str(args.priority_queue),
        "time_norm_subset": str(args.time_norm_subset),
        "time_conflict_analysis": str(args.time_conflict_analysis),
        "type_conflict_analysis": str(args.type_conflict_analysis),
        "coordinate_conflict_analysis": str(args.coordinate_conflict_analysis),
    }
    summary = summarize_entity_resolution_cluster_blocker_analysis_suite(
        priority_queue=read_json(args.priority_queue),
        time_norm_subset=read_json(args.time_norm_subset),
        time_conflict_analysis=read_json(args.time_conflict_analysis),
        type_conflict_analysis=read_json(args.type_conflict_analysis),
        coordinate_conflict_analysis=read_json(args.coordinate_conflict_analysis),
        inputs=inputs,
    )
    write_json(args.json_output, summary)
    write_markdown(args.markdown_output, summary)
    print(
        json.dumps(
            {
                "json_output": str(args.json_output),
                "markdown_output": str(args.markdown_output),
                "summary_policy": summary["summary_policy"],
                "queue_item_count": summary["summary"]["queue_item_count"],
                "strict_time_normalization_new_preview_candidates": summary["summary"][
                    "strict_time_normalization_new_preview_candidates"
                ],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
