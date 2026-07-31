"""Summarize remaining manual-review audit lanes after bounded review passes.

This report is a safety rail: it records which manual-review replacement audit
sublanes have review-only packets or accepted sidecar handling, and it assigns
the remaining mixed/high-risk lanes to explicit next actions. It does not create
decisions, apply merges, or mutate canonical corpora.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


DEFAULT_SUBLANES_CSV = Path("data/reports/manual_review_ai_after_time_norm_replacement_audit_sublanes.csv")
DEFAULT_OUTPUT = Path("data/reports/manual_review_ai_after_time_norm_remaining_lane_actions.json")
DEFAULT_CSV_OUTPUT = Path("data/reports/manual_review_ai_after_time_norm_remaining_lane_actions.csv")

REPORT_POLICY = "manual_review_remaining_lane_action_matrix_v1"

LANE_STATUS = {
    "accepted_low_risk_preview_lane": {
        "status": "accepted_sidecar_preview",
        "next_action": "keep_sidecar_only_until_runtime_promotion_review",
        "risk_position": "accepted_low_risk_components_only",
    },
    "medium_time_raw_only": {
        "status": "parser_backed_partial_sidecar_preview",
        "next_action": "keep_178_candidates_sidecar_only_and_defer_remaining_640",
        "risk_position": "only_nearby_exact_time_conflicts_promoted_to_candidate_sidecar",
    },
    "medium_time_or_identity_only": {
        "status": "review_only_packet_created",
        "next_action": "manual_identity_review_before_any_decisions",
        "risk_position": "same_source_multiple_native_ids_present_in_every_component",
    },
    "medium_body_text_only": {
        "status": "review_only_packet_created",
        "next_action": "manual_body_variant_review_before_any_decisions",
        "risk_position": "body_text_can_preserve_distinct_witness_details",
    },
    "medium_classification_only": {
        "status": "review_only_packet_created",
        "next_action": "classification_code_equivalence_table_before_any_decisions",
        "risk_position": "broad_type_code_conflicts_not_automatically_equivalent",
    },
    "medium_location_text_mixed": {
        "status": "review_only_packet_created",
        "next_action": "manual_location_time_review_before_any_decisions",
        "risk_position": "mixed_location_and_time_conflicts_require interpretation",
    },
    "medium_coordinate_span_gt_5km": {
        "status": "review_only_packet_created",
        "next_action": "manual_coordinate_review_before_any_decisions",
        "risk_position": "coordinate_span_conflicts_remain_review_only",
    },
    "medium_body_text_mixed": {
        "status": "review_only_packet_created",
        "next_action": "manual_body_mixed_review_before_any_decisions",
        "risk_position": "body_conflicts_mixed_with_location_time_or_type_conflicts",
    },
    "medium_classification_mixed": {
        "status": "review_only_packet_created",
        "next_action": "manual_classification_mixed_review_before_any_decisions",
        "risk_position": "classification_conflicts_mixed_with time_or_shape_conflicts",
    },
    "medium_identity_mixed": {
        "status": "review_only_packet_created",
        "next_action": "manual_identity_mixed_review_before_any_decisions",
        "risk_position": "same_source_identity_conflicts_mixed_with other risk flags",
    },
    "high_coordinate_span_gt_50km": {
        "status": "high_risk_dedicated_review_packet_created",
        "next_action": "manual_geographic_review_required_before_any_decisions",
        "risk_position": "high_coordinate_span_conflicts_block_automation",
    },
}


def build_remaining_lane_actions(*, sublanes_csv_path: Path) -> dict[str, Any]:
    rows = read_csv(sublanes_csv_path)
    items = []
    for row in rows:
        sublane = clean_text(row.get("sublane"))
        policy = LANE_STATUS.get(
            sublane,
            {
                "status": "unknown_lane",
                "next_action": "inspect_before_any_decision_or_apply",
                "risk_position": "not_classified_by_action_matrix",
            },
        )
        items.append(
            {
                "sublane": sublane,
                "component_count": safe_int(row.get("component_count")),
                "projected_event_reduction": safe_int(row.get("projected_event_reduction")),
                "risk_counts": parse_json_cell(row.get("risk_counts")),
                "flag_counts": parse_json_cell(row.get("flag_counts")),
                **policy,
            }
        )

    totals_by_status: dict[str, dict[str, int]] = {}
    for item in items:
        status = item["status"]
        bucket = totals_by_status.setdefault(status, {"component_count": 0, "projected_event_reduction": 0})
        bucket["component_count"] += int(item["component_count"])
        bucket["projected_event_reduction"] += int(item["projected_event_reduction"])

    unsafe_automation_components = sum(
        int(item["component_count"])
        for item in items
        if item["status"] in {"unreviewed_mixed_risk_lane", "high_risk_dedicated_review_packet_created"}
    )
    return {
        "schema_version": 1,
        "report_policy": REPORT_POLICY,
        "canonical_outputs_mutated": False,
        "source_canonical_outputs_mutated": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_runtime_promotion": False,
        "inputs": {"sublanes_csv": str(sublanes_csv_path)},
        "summary": {
            "sublane_count": len(items),
            "totals_by_status": dict(sorted(totals_by_status.items())),
            "unsafe_automation_component_count": unsafe_automation_components,
            "unreviewed_or_high_risk_component_count": unsafe_automation_components,
        },
        "items": items,
        "notes": [
            "This action matrix is report-only and does not apply any lane.",
            "Mixed coordinate/body/classification/identity lanes require evidence packets and manual review before decisions.",
            "The low-risk plus narrow exact-time sidecar remains preview-only; default runtime/static app data is not promoted.",
        ],
    }


def write_csv(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = (
        "sublane",
        "status",
        "next_action",
        "risk_position",
        "component_count",
        "projected_event_reduction",
        "flag_counts",
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in report.get("items") or []:
            writer.writerow(
                {
                    "sublane": item.get("sublane"),
                    "status": item.get("status"),
                    "next_action": item.get("next_action"),
                    "risk_position": item.get("risk_position"),
                    "component_count": item.get("component_count"),
                    "projected_event_reduction": item.get("projected_event_reduction"),
                    "flag_counts": json.dumps(item.get("flag_counts") or {}, sort_keys=True),
                }
            )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def parse_json_cell(value: Any) -> dict[str, Any]:
    text = clean_text(value)
    if not text:
        return {}
    parsed = json.loads(text)
    return parsed if isinstance(parsed, dict) else {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def safe_int(value: Any) -> int:
    try:
        return int(float(clean_text(value) or "0"))
    except ValueError:
        return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sublanes-csv", type=Path, default=DEFAULT_SUBLANES_CSV)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_remaining_lane_actions(sublanes_csv_path=args.sublanes_csv)
    write_json(args.output, report)
    write_csv(args.csv_output, report)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "csv_output": str(args.csv_output),
                "sublane_count": report["summary"]["sublane_count"],
                "totals_by_status": report["summary"]["totals_by_status"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
