"""Build a report-only triage digest for mixed medium manual-review queues.

This digest summarizes the medium mixed-risk review packets that remain manual
review work: identity-mixed, classification-mixed, and body-text-mixed. It does
not create accepted decisions, apply merges, or mutate canonical outputs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_REVIEW_FILES = {
    "medium_identity_mixed": Path("data/reports/manual_review_ai_after_time_norm_medium_identity_mixed_review.json"),
    "medium_classification_mixed": Path("data/reports/manual_review_ai_after_time_norm_medium_classification_mixed_review.json"),
    "medium_body_text_mixed": Path("data/reports/manual_review_ai_after_time_norm_medium_body_text_mixed_review.json"),
}
DEFAULT_ACTION_MATRIX = Path("data/reports/manual_review_ai_after_time_norm_remaining_lane_actions.json")
DEFAULT_JSON_OUTPUT = Path("data/reports/mixed_medium_review_triage_digest.json")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/mixed_medium_review_triage_digest.md")


def build_mixed_medium_review_triage_digest(
    *,
    review_reports: dict[str, dict[str, Any]],
    action_matrix: dict[str, Any],
) -> dict[str, Any]:
    lanes = {name: summarize_lane(name, report) for name, report in review_reports.items()}
    total_items = sum(int(lane["reviewed_item_count"]) for lane in lanes.values())
    total_reduction = sum(int(lane["projected_event_reduction_total"]) for lane in lanes.values())
    return {
        "schema_version": 1,
        "digest_policy": "mixed_medium_review_triage_digest_report_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "ready_for_canonical_apply": False,
        "human_review_required_before_promotion": True,
        "summary": {
            "lane_count": len(lanes),
            "reviewed_item_count": total_items,
            "projected_event_reduction_total": total_reduction,
            "action_matrix_policy": action_matrix.get("report_policy"),
            "action_matrix_ready_for_runtime_promotion": action_matrix.get("ready_for_runtime_promotion"),
            "lane_counts": {name: lane["reviewed_item_count"] for name, lane in lanes.items()},
            "lane_projected_reductions": {
                name: lane["projected_event_reduction_total"] for name, lane in lanes.items()
            },
        },
        "review_guidance": [
            "Review body-text mixed rows first when descriptions or summaries may preserve distinct witness details.",
            "Review classification-mixed rows against a source-code equivalence table before considering merge decisions.",
            "Review identity-mixed rows only after confirming source-native IDs do not represent separate witness records.",
            "Do not automatically promote any mixed medium row; every lane remains manual-review only.",
        ],
        "lanes": lanes,
    }


def summarize_lane(name: str, report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    items = [item for item in report.get("items") or [] if isinstance(item, dict)]
    subcategory_counts = {
        key: value
        for key, value in summary.items()
        if key.endswith("_subcategory_counts") and isinstance(value, dict)
    }
    return {
        "lane": name,
        "review_policy": report.get("review_policy"),
        "reviewed_item_count": int(summary.get("reviewed_item_count") or len(items)),
        "projected_event_reduction_total": sum_projection(summary),
        "recommendation_counts": summary.get("review_recommendation_counts") or {},
        "subcategory_counts": subcategory_counts,
        "confidence_counts": summary.get("confidence_counts") or {},
        "failed_condition_counts": summary.get("failed_condition_counts") or {},
        "top_review_items": [summarize_item(item) for item in top_items(items)],
        "report_only_guards": {
            "canonical_outputs_mutated": report.get("canonical_outputs_mutated"),
            "preview_outputs_written": report.get("preview_outputs_written"),
            "decisions_created": report.get("decisions_created"),
            "ready_for_runtime_promotion": report.get("ready_for_runtime_promotion"),
        },
    }


def sum_projection(summary: dict[str, Any]) -> int:
    projections = summary.get("projected_event_reduction_by_review_recommendation")
    if isinstance(projections, dict):
        return sum(int(value or 0) for value in projections.values())
    return 0


def top_items(items: list[dict[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda item: (-int(item.get("projected_event_reduction") or 0), int(item.get("review_rank") or 999999)),
    )[:limit]


def summarize_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "review_rank": item.get("review_rank"),
        "replacement_event_id": item.get("replacement_event_id"),
        "review_recommendation": item.get("review_recommendation"),
        "projected_event_reduction": item.get("projected_event_reduction"),
        "risk_flags": item.get("risk_flags") or [],
        "source_file_values": item.get("source_file_values") or [],
        "location_raw_values": item.get("location_raw_values") or [],
        "time_raw_values": item.get("time_raw_values") or [],
        "type_values": item.get("type_values") or [],
        "shape_values": item.get("shape_values") or [],
    }


def render_markdown(digest: dict[str, Any]) -> str:
    summary = digest["summary"]
    lines = [
        "# Mixed Medium Review Triage Digest",
        "",
        "This digest is report-only. It does not accept decisions, apply merges, or mutate canonical outputs.",
        "",
        "## Summary",
        "",
        f"- Lanes: {summary['lane_count']}",
        f"- Reviewed items: {summary['reviewed_item_count']}",
        f"- Projected event reduction behind blocked queues: {summary['projected_event_reduction_total']}",
        f"- Lane counts: {json.dumps(summary['lane_counts'], sort_keys=True)}",
        f"- Lane projected reductions: {json.dumps(summary['lane_projected_reductions'], sort_keys=True)}",
        "",
        "## Review Guidance",
        "",
    ]
    lines.extend(f"- {item}" for item in digest["review_guidance"])
    lines.extend(["", "## Lanes", ""])
    for name, lane in digest["lanes"].items():
        lines.extend(
            [
                f"### {name}",
                "",
                f"- Policy: `{lane['review_policy']}`",
                f"- Reviewed items: {lane['reviewed_item_count']}",
                f"- Projected reduction: {lane['projected_event_reduction_total']}",
                f"- Recommendations: {json.dumps(lane['recommendation_counts'], sort_keys=True)}",
                f"- Subcategories: {json.dumps(lane['subcategory_counts'], sort_keys=True)}",
                "",
            ]
        )
    return "\n".join(lines)


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity-mixed-review", type=Path, default=DEFAULT_REVIEW_FILES["medium_identity_mixed"])
    parser.add_argument(
        "--classification-mixed-review",
        type=Path,
        default=DEFAULT_REVIEW_FILES["medium_classification_mixed"],
    )
    parser.add_argument("--body-text-mixed-review", type=Path, default=DEFAULT_REVIEW_FILES["medium_body_text_mixed"])
    parser.add_argument("--action-matrix", type=Path, default=DEFAULT_ACTION_MATRIX)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    review_reports = {
        "medium_identity_mixed": read_json(args.identity_mixed_review),
        "medium_classification_mixed": read_json(args.classification_mixed_review),
        "medium_body_text_mixed": read_json(args.body_text_mixed_review),
    }
    digest = build_mixed_medium_review_triage_digest(
        review_reports=review_reports,
        action_matrix=read_json(args.action_matrix),
    )
    digest["inputs"] = {
        "identity_mixed_review": str(args.identity_mixed_review),
        "classification_mixed_review": str(args.classification_mixed_review),
        "body_text_mixed_review": str(args.body_text_mixed_review),
        "action_matrix": str(args.action_matrix),
    }
    digest["outputs"] = {"json": str(args.json_output), "markdown": str(args.markdown_output)}
    write_json(args.json_output, digest)
    write_text(args.markdown_output, render_markdown(digest))
    print(
        json.dumps(
            {
                "json": str(args.json_output),
                "markdown": str(args.markdown_output),
                "reviewed_items": digest["summary"]["reviewed_item_count"],
                "ready_for_canonical_apply": digest["ready_for_canonical_apply"],
                "canonical_outputs_mutated": digest["canonical_outputs_mutated"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
