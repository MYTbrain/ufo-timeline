"""Summarize ER scoring calibration and review-priority risks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_SCORE_REPORT = Path("data/reports/entity_resolution_score_report.json")
DEFAULT_REVIEW_PACKET = Path("data/reports/entity_resolution_review_packet.json")
DEFAULT_OUTPUT = Path("data/reports/entity_resolution_calibration_summary.json")

HIGH_ATTENTION_RISK_FLAGS = {
    "coarse_or_uncertain_date_precision",
    "coordinates_far_apart",
    "date_mismatch_or_missing",
    "different_source_native_ids",
    "shape_differs",
    "short_text_match_limited",
    "short_text_overlap_limited",
    "time_mismatch_or_one_missing",
    "type_differs",
    "weak_location_evidence",
    "weak_text_overlap",
}

REPORT_ONLY_FALSE_FLAGS = (
    "canonical_outputs_mutated",
    "preview_outputs_written",
    "decisions_created",
    "auto_merge_performed",
)


def summarize_entity_resolution_calibration(
    *,
    score_report: dict[str, Any],
    review_packet: dict[str, Any] | None = None,
    score_report_path: Path | None = None,
    review_packet_path: Path | None = None,
) -> dict[str, Any]:
    validate_report_only_payload(
        "score_report",
        score_report,
        expected_policy_key="report_policy",
        expected_policy_value="entity_resolution_scoring_analysis_only",
    )
    if review_packet is not None:
        validate_report_only_payload(
            "review_packet",
            review_packet,
            expected_policy_key="packet_policy",
            expected_policy_value="entity_resolution_review_only",
        )

    score_summary = dict_or_empty(score_report.get("score_summary"))
    band_counts = dict_or_empty(score_summary.get("band_counts"))
    band_risk_flag_counts = dict_or_empty(score_summary.get("band_risk_flag_counts"))
    band_source_pair_counts = dict_or_empty(score_summary.get("band_source_pair_counts"))
    projected_reduction = dict_or_empty(score_summary.get("projected_cross_event_reduction"))

    packet_summary = dict_or_empty(review_packet.get("export_summary")) if review_packet else {}
    return {
        "schema_version": 1,
        "report_policy": "entity_resolution_calibration_summary",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "inputs": {
            "score_report": str(score_report_path) if score_report_path else None,
            "review_packet": str(review_packet_path) if review_packet_path else None,
            "review_packet_present": review_packet is not None,
        },
        "score_overview": {
            "scored_pair_count": score_summary.get("scored_pair_count", 0),
            "cross_event_scored_pair_count": score_summary.get("cross_event_scored_pair_count", 0),
            "pair_scoring_truncated": bool(score_summary.get("pair_scoring_truncated")),
            "band_counts": band_counts,
            "projected_cross_event_reduction": projected_reduction,
        },
        "risk_hotspots": {
            "likely_same_event_review": risk_hotspots_for_band("likely_same_event_review", band_risk_flag_counts),
            "strong_candidate_review": risk_hotspots_for_band("strong_candidate_review", band_risk_flag_counts),
            "moderate_candidate_review": risk_hotspots_for_band("moderate_candidate_review", band_risk_flag_counts),
        },
        "source_pair_hotspots": {
            band: top_counts(counts, limit=12)
            for band, counts in sorted(band_source_pair_counts.items())
            if isinstance(counts, dict)
        },
        "packet_sample_overview": {
            "sample_scope": packet_summary.get("available_sample_scope"),
            "exported_item_count": packet_summary.get("exported_item_count", 0),
            "cross_event_only": packet_summary.get("cross_event_only"),
            "band_counts": packet_summary.get("band_counts", {}),
            "risk_flag_counts": packet_summary.get("risk_flag_counts", {}),
        },
        "workflow_readiness": {
            "calibration_status": "ready_for_review" if packet_summary.get("exported_item_count", 0) > 0 else "incomplete",
            "review_packet_available": packet_summary.get("exported_item_count", 0) > 0,
            "review_packet_cross_event_only": packet_summary.get("cross_event_only") is True,
            "ready_for_human_review": packet_summary.get("exported_item_count", 0) > 0,
            "ready_for_apply": False,
            "apply_blocker": "validated_same_event_decisions_required",
        },
        "review_priorities": review_priorities(score_summary, packet_summary),
        "notes": [
            "This is a calibration report, not a merge plan.",
            "Risk flags inside high-score bands are intentional review prompts, not automatic rejection.",
            "Use the ER review packet for item-level adjudication and validated decisions for workflow state.",
        ],
    }


def risk_hotspots_for_band(band: str, band_risk_flag_counts: dict[str, Any]) -> dict[str, Any]:
    counts = dict_or_empty(band_risk_flag_counts.get(band))
    high_attention = {
        key: value
        for key, value in sorted(counts.items())
        if key in HIGH_ATTENTION_RISK_FLAGS and isinstance(value, int) and value > 0
    }
    return {
        "top_risk_flags": top_counts(counts, limit=12),
        "high_attention_risk_flags": high_attention,
    }


def validate_report_only_payload(
    label: str,
    payload: dict[str, Any],
    *,
    expected_policy_key: str,
    expected_policy_value: str,
) -> None:
    errors: list[str] = []
    if payload.get(expected_policy_key) != expected_policy_value:
        errors.append(f"{expected_policy_key} must be {expected_policy_value!r}")
    for flag in REPORT_ONLY_FALSE_FLAGS:
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError(f"{label} is not a safe report-only input: {'; '.join(errors)}")


def review_priorities(score_summary: dict[str, Any], packet_summary: dict[str, Any]) -> list[dict[str, str]]:
    priorities = [
        {
            "priority": "review_likely_same_event_cross_event_samples_first",
            "reason": "These are the highest-scored cross-current-event candidates and produce the cleanest early validation signal.",
        },
        {
            "priority": "audit_high_score_pairs_with_risk_flags",
            "reason": "Likely/strong candidates can still carry type, text, coordinate, or native-ID conflicts that should calibrate thresholds.",
        },
        {
            "priority": "do_not_apply_until_decisions_exist",
            "reason": "All current ER outputs are reports, packets, validation scaffolds, or preview seams; no same_event decisions have been supplied.",
        },
    ]
    if score_summary.get("pair_scoring_truncated"):
        priorities.append(
            {
                "priority": "increase_pair_cap_or_partition_scoring",
                "reason": "The score report was truncated, so aggregate counts are incomplete.",
            }
        )
    if packet_summary.get("exported_item_count", 0) == 0:
        priorities.append(
            {
                "priority": "generate_review_packet",
                "reason": "No item-level packet exists for adjudication.",
            }
        )
    return priorities


def top_counts(counts: dict[str, Any], *, limit: int) -> list[dict[str, Any]]:
    numeric_items = [(key, value) for key, value in counts.items() if isinstance(value, int)]
    return [
        {"key": key, "count": value}
        for key, value in sorted(numeric_items, key=lambda item: (-item[1], item[0]))[:limit]
    ]


def dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--score-report", type=Path, default=DEFAULT_SCORE_REPORT)
    parser.add_argument("--review-packet", type=Path, default=DEFAULT_REVIEW_PACKET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    score_report = read_json(args.score_report)
    review_packet = read_json(args.review_packet) if args.review_packet.exists() else None
    summary = summarize_entity_resolution_calibration(
        score_report=score_report,
        review_packet=review_packet,
        score_report_path=args.score_report,
        review_packet_path=args.review_packet if review_packet else None,
    )
    write_json(args.output, summary)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "scored_pair_count": summary["score_overview"]["scored_pair_count"],
                "exported_review_items": summary["packet_sample_overview"]["exported_item_count"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
