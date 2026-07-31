"""Promote reviewed deferred shorthand time candidates to decision candidates.

This consumes the source-review-only deferred shorthand report and writes a
separate JSONL of same-event decision candidates for the items that passed that
review. It is intentionally not an apply step.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from parser.canonical_schema import clean_text, stable_hash


DEFAULT_REVIEW = Path("data/reports/entity_resolution_cluster_time_norm_deferred_shorthand_review.json")
DEFAULT_DECISIONS_OUTPUT = Path(
    "data/reports/entity_resolution_cluster_time_norm_deferred_shorthand_decision_candidates.jsonl"
)
DEFAULT_REPORT_OUTPUT = Path(
    "data/reports/entity_resolution_cluster_time_norm_deferred_shorthand_decision_candidates_report.json"
)

INPUT_REVIEW_POLICY = "entity_resolution_time_norm_deferred_shorthand_source_review_only"
PROMOTION_POLICY = "entity_resolution_time_norm_deferred_shorthand_decision_candidates_only"
DEFAULT_REVIEWER = "codex_time_norm_deferred_shorthand_source_review_v1"
SOURCE_REVIEW_SAME_EVENT = "source_review_same_event_candidate"


def build_deferred_shorthand_decision_candidates(
    review_report: dict[str, Any],
    *,
    reviewer: str = DEFAULT_REVIEWER,
    reviewed_at: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    validate_review_report_safety(review_report)
    timestamp = reviewed_at or datetime.now(UTC).replace(microsecond=0).isoformat()
    items = [item for item in review_report.get("items") or [] if isinstance(item, dict)]
    decision_candidates: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        if clean_text(item.get("review_recommendation")) != SOURCE_REVIEW_SAME_EVENT:
            skipped.append(skip_record(index, item, "review_recommendation_not_same_event_candidate"))
            continue
        failed_conditions = string_list(item.get("failed_conditions"))
        if failed_conditions:
            skipped.append(skip_record(index, item, "source_review_has_failed_conditions", failed_conditions=failed_conditions))
            continue
        merge_event_ids = string_list(item.get("merge_canonical_event_ids"))
        if len(merge_event_ids) < 2:
            skipped.append(skip_record(index, item, "merge_requires_at_least_two_events"))
            continue
        decision_candidates.append(
            decision_candidate_from_review_item(
                item,
                decision_index=len(decision_candidates) + 1,
                reviewer=reviewer,
                reviewed_at=timestamp,
            )
        )
    report = {
        "schema_version": 1,
        "promotion_policy": PROMOTION_POLICY,
        "input_review_policy": review_report.get("review_policy"),
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "canonical_apply_performed": False,
        "auto_merge_performed": False,
        "accepted_canonical_decisions_created": False,
        "recommended_decision_candidate_records_written": True,
        "ready_for_canonical_apply": False,
        "input_review_item_count": len(items),
        "decision_candidate_count": len(decision_candidates),
        "skipped_review_item_count": len(skipped),
        "skipped_reason_counts": count_by(skipped, "reason"),
        "projected_event_reduction": sum(
            max(0, len(string_list(record.get("merge_canonical_event_ids"))) - 1)
            for record in decision_candidates
        ),
        "reviewer": reviewer,
        "reviewed_at": timestamp,
        "skipped_review_items": skipped,
        "notes": [
            "These are decision candidates derived from the deferred shorthand source-review report.",
            "They are not canonical apply; use effects-plan and dry-run gates before any candidate corpus rewrite.",
            "Items with non-time conflicts remain intentionally skipped.",
        ],
    }
    return decision_candidates, report


def validate_review_report_safety(report: dict[str, Any]) -> None:
    errors: list[str] = []
    if report.get("review_policy") != INPUT_REVIEW_POLICY:
        errors.append(f"review_policy must be {INPUT_REVIEW_POLICY}")
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
        raise ValueError("deferred shorthand review report is unsafe for promotion: " + "; ".join(errors))


def decision_candidate_from_review_item(
    item: dict[str, Any],
    *,
    decision_index: int,
    reviewer: str,
    reviewed_at: str,
) -> dict[str, Any]:
    review_item_id = clean_text(item.get("review_item_id")) or ""
    merge_event_ids = string_list(item.get("merge_canonical_event_ids"))
    canonical_input_ids = string_list(item.get("candidate_canonical_input_ids"))
    decision_id = stable_hash(
        {
            "review_item_id": review_item_id,
            "effect_id": item.get("effect_id"),
            "decision": "same_event",
            "merge_canonical_event_ids": merge_event_ids,
            "promotion_policy": PROMOTION_POLICY,
        },
        prefix="erdtns_",
        length=20,
    )
    return {
        "entity_resolution_decision_id": decision_id,
        "decision_index": decision_index,
        "review_item_id": review_item_id,
        "cluster_review_id": clean_text(item.get("cluster_review_id")) or review_item_id,
        "review_type": "entity_resolution_cluster_time_normalization_candidate",
        "decision": "same_event",
        "effect_status": "source_reviewed_candidate_not_applied",
        "decision_source": INPUT_REVIEW_POLICY,
        "promotion_policy": PROMOTION_POLICY,
        "canonical_outputs_mutated": False,
        "review_band": "strict_time_normalization_deferred_shorthand_source_review",
        "confidence": clean_text(item.get("confidence")),
        "canonical_input_ids": canonical_input_ids,
        "merge_canonical_event_ids": merge_event_ids,
        "reviewer": reviewer,
        "reviewed_at": reviewed_at,
        "notes": clean_text(item.get("notes")),
        "requires_explicit_apply_step": True,
        "evidence": {
            "effect_id": clean_text(item.get("effect_id")),
            "time_tokens": string_list(item.get("time_tokens")),
            "parsed_token_minutes": int_list(item.get("parsed_token_minutes")),
            "token_minute_span": item.get("token_minute_span"),
            "active_conflicts": string_list(item.get("active_conflicts")),
            "review_reason_codes": string_list(item.get("review_reason_codes")),
            "source_names": string_list(item.get("source_names")),
            "source_native_ids": string_list(item.get("source_native_ids")),
            "dates": string_list(item.get("dates")),
            "locations": string_list(item.get("locations")),
        },
    }


def skip_record(
    index: int,
    item: dict[str, Any],
    reason: str,
    *,
    failed_conditions: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "review_index": index,
        "review_item_id": clean_text(item.get("review_item_id")),
        "effect_id": clean_text(item.get("effect_id")),
        "review_recommendation": clean_text(item.get("review_recommendation")),
        "reason": reason,
        "failed_conditions": failed_conditions or string_list(item.get("failed_conditions")),
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
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--decisions-output", type=Path, default=DEFAULT_DECISIONS_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    parser.add_argument("--reviewer", default=DEFAULT_REVIEWER)
    parser.add_argument("--reviewed-at", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    decision_candidates, report = build_deferred_shorthand_decision_candidates(
        read_json(args.review),
        reviewer=args.reviewer,
        reviewed_at=args.reviewed_at,
    )
    report["inputs"] = {"review": str(args.review)}
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
                "skipped_review_item_count": report["skipped_review_item_count"],
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
