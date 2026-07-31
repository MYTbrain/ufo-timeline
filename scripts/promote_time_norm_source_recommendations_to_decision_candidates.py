"""Promote clean time-normalization recommendations to decision candidates.

This creates an isolated JSONL of same-event decision candidates from the
report-only source recommendation artifact. It is intentionally not a canonical
apply step: it does not mutate canonical outputs and the resulting records still
require the existing explicit effects-plan/preview/apply workflow.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from parser.canonical_schema import clean_text, stable_hash


DEFAULT_RECOMMENDATIONS = Path("data/reports/entity_resolution_cluster_time_norm_source_review_recommendations.json")
DEFAULT_DECISIONS_OUTPUT = Path("data/reports/entity_resolution_cluster_time_norm_recommended_decision_candidates.jsonl")
DEFAULT_REPORT_OUTPUT = Path("data/reports/entity_resolution_cluster_time_norm_recommended_decision_candidates_report.json")

INPUT_RECOMMENDATION_POLICY = "entity_resolution_time_norm_auto_recommendation_only"
PROMOTION_POLICY = "entity_resolution_time_norm_recommended_decision_candidates_only"
DEFAULT_REVIEWER = "codex_time_norm_clean_clock_recommendation_v1"


def build_time_norm_recommended_decision_candidates(
    recommendations_report: dict[str, Any],
    *,
    reviewer: str = DEFAULT_REVIEWER,
    reviewed_at: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    validate_recommendations_safety(recommendations_report)
    timestamp = reviewed_at or datetime.now(UTC).replace(microsecond=0).isoformat()
    recommendations = [
        item for item in recommendations_report.get("recommendations") or [] if isinstance(item, dict)
    ]
    decision_candidates: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for index, recommendation in enumerate(recommendations, start=1):
        if clean_text(recommendation.get("recommendation")) != "recommend_same_event":
            skipped.append(skip_record(index, recommendation, "recommendation_not_same_event"))
            continue
        blockers = string_list(recommendation.get("blockers"))
        if blockers:
            skipped.append(skip_record(index, recommendation, "recommendation_has_blockers", blockers=blockers))
            continue
        merge_event_ids = string_list(recommendation.get("merge_canonical_event_ids"))
        if len(merge_event_ids) < 2:
            skipped.append(skip_record(index, recommendation, "merge_requires_at_least_two_events"))
            continue
        decision_candidates.append(
            decision_candidate_from_recommendation(
                recommendation,
                decision_index=len(decision_candidates) + 1,
                reviewer=reviewer,
                reviewed_at=timestamp,
            )
        )
    report = {
        "schema_version": 1,
        "promotion_policy": PROMOTION_POLICY,
        "input_recommendation_policy": recommendations_report.get("recommendation_policy"),
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "canonical_apply_performed": False,
        "auto_merge_performed": False,
        "accepted_canonical_decisions_created": False,
        "recommended_decision_candidate_records_written": True,
        "ready_for_canonical_apply": False,
        "input_recommendation_count": len(recommendations),
        "decision_candidate_count": len(decision_candidates),
        "skipped_recommendation_count": len(skipped),
        "skipped_reason_counts": count_by(skipped, "reason"),
        "projected_event_reduction": sum(
            max(0, len(string_list(record.get("merge_canonical_event_ids"))) - 1)
            for record in decision_candidates
        ),
        "reviewer": reviewer,
        "reviewed_at": timestamp,
        "skipped_recommendations": skipped,
        "notes": [
            "These are decision candidates derived from clean time-normalization recommendations.",
            "They are not canonical apply; use the explicit effects-plan and preview-only apply path before any promotion.",
            "Deferred symbolic/shorthand-token and non-time-conflict recommendations are intentionally skipped.",
        ],
    }
    return decision_candidates, report


def validate_recommendations_safety(report: dict[str, Any]) -> None:
    errors: list[str] = []
    if report.get("recommendation_policy") != INPUT_RECOMMENDATION_POLICY:
        errors.append(f"recommendation_policy must be {INPUT_RECOMMENDATION_POLICY}")
    for flag in (
        "canonical_outputs_mutated",
        "preview_outputs_written",
        "decisions_created",
        "decision_outputs_created",
        "validated_decisions_created",
        "auto_merge_performed",
        "ready_for_canonical_apply",
    ):
        if report.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError("recommendations report is unsafe for promotion: " + "; ".join(errors))


def decision_candidate_from_recommendation(
    recommendation: dict[str, Any],
    *,
    decision_index: int,
    reviewer: str,
    reviewed_at: str,
) -> dict[str, Any]:
    review_item_id = clean_text(recommendation.get("review_item_id"))
    merge_event_ids = string_list(recommendation.get("merge_canonical_event_ids"))
    canonical_input_ids = string_list(recommendation.get("candidate_canonical_input_ids"))
    decision_id = stable_hash(
        {
            "review_item_id": review_item_id,
            "effect_id": recommendation.get("effect_id"),
            "decision": "same_event",
            "merge_canonical_event_ids": merge_event_ids,
            "promotion_policy": PROMOTION_POLICY,
        },
        prefix="erdtn_",
        length=20,
    )
    return {
        "entity_resolution_decision_id": decision_id,
        "decision_index": decision_index,
        "review_item_id": review_item_id,
        "cluster_review_id": clean_text(recommendation.get("cluster_review_id")) or review_item_id,
        "review_type": "entity_resolution_cluster_time_normalization_candidate",
        "decision": "same_event",
        "effect_status": "recommended_candidate_not_applied",
        "decision_source": INPUT_RECOMMENDATION_POLICY,
        "promotion_policy": PROMOTION_POLICY,
        "canonical_outputs_mutated": False,
        "review_band": "strict_time_normalization_clean_clock",
        "confidence": clean_text(recommendation.get("confidence")),
        "canonical_input_ids": canonical_input_ids,
        "merge_canonical_event_ids": merge_event_ids,
        "reviewer": reviewer,
        "reviewed_at": reviewed_at,
        "notes": clean_text(recommendation.get("notes")),
        "requires_explicit_apply_step": True,
        "evidence": {
            "effect_id": clean_text(recommendation.get("effect_id")),
            "time_tokens": string_list(recommendation.get("time_tokens")),
            "parsed_minutes": int_list(recommendation.get("parsed_minutes")),
            "minute_span": recommendation.get("minute_span"),
            "active_conflicts": string_list(recommendation.get("active_conflicts")),
            "reason_codes": string_list(recommendation.get("reason_codes")),
            "source_names": string_list(recommendation.get("source_names")),
            "source_native_ids": string_list(recommendation.get("source_native_ids")),
            "dates": string_list(recommendation.get("dates")),
            "locations": string_list(recommendation.get("locations")),
        },
    }


def skip_record(
    index: int,
    recommendation: dict[str, Any],
    reason: str,
    *,
    blockers: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "recommendation_index": index,
        "review_item_id": clean_text(recommendation.get("review_item_id")),
        "effect_id": clean_text(recommendation.get("effect_id")),
        "recommendation": clean_text(recommendation.get("recommendation")),
        "reason": reason,
        "blockers": blockers or string_list(recommendation.get("blockers")),
    }


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = clean_text(row.get(key)) or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [text for item in value if (text := clean_text(item))]
    text = clean_text(value)
    return [text] if text else []


def int_list(value: Any) -> list[int]:
    values: list[int] = []
    if not isinstance(value, list):
        return values
    for item in value:
        try:
            values.append(int(item))
        except (TypeError, ValueError):
            continue
    return values


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recommendations", type=Path, default=DEFAULT_RECOMMENDATIONS)
    parser.add_argument("--decisions-output", type=Path, default=DEFAULT_DECISIONS_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    parser.add_argument("--reviewer", default=DEFAULT_REVIEWER)
    parser.add_argument("--reviewed-at", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    decision_candidates, report = build_time_norm_recommended_decision_candidates(
        read_json(args.recommendations),
        reviewer=args.reviewer,
        reviewed_at=args.reviewed_at,
    )
    report["inputs"] = {"recommendations": str(args.recommendations)}
    report["outputs"] = {
        "decision_candidates": str(args.decisions_output),
        "report": str(args.report_output),
    }
    write_jsonl(args.decisions_output, decision_candidates)
    write_json(args.report_output, report)
    print(
        json.dumps(
            {
                "decision_candidates": str(args.decisions_output),
                "report": str(args.report_output),
                "decision_candidate_count": report["decision_candidate_count"],
                "skipped_recommendation_count": report["skipped_recommendation_count"],
                "projected_event_reduction": report["projected_event_reduction"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
