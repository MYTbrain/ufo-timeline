"""Promote medium time_raw-only review rows to decision candidates.

This is not an apply step. It turns parser-reviewed same-event candidates into
an auditable JSONL artifact with replacement/component/effect IDs attached.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Iterable

from parser.canonical_schema import clean_text, stable_hash


DEFAULT_REVIEW = Path("data/reports/manual_review_ai_after_time_norm_medium_time_raw_only_review.json")
DEFAULT_CANDIDATE_EVENTS = Path("data/canonical_time_norm_plus_manual_review_ai_preview/deduped_events.jsonl")
DEFAULT_DECISIONS_OUTPUT = Path("data/reports/manual_review_ai_after_time_norm_medium_time_raw_only_decision_candidates.jsonl")
DEFAULT_REPORT_OUTPUT = Path("data/reports/manual_review_ai_after_time_norm_medium_time_raw_only_decision_candidates_report.json")

INPUT_REVIEW_POLICY = "manual_review_medium_time_raw_only_parser_review_v1"
PROMOTION_POLICY = "manual_review_medium_time_raw_only_decision_candidates_only"
SOURCE_REVIEW_SAME_EVENT = "source_review_same_event_candidate"
DEFAULT_REVIEWER = "codex_medium_time_raw_only_parser_review_v1"


def build_medium_time_raw_only_decision_candidates(
    review_report: dict[str, Any],
    *,
    candidate_events_path: Path,
    reviewer: str = DEFAULT_REVIEWER,
    reviewed_at: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    validate_review_report_safety(review_report)
    timestamp = reviewed_at or datetime.now(UTC).replace(microsecond=0).isoformat()
    items = [item for item in review_report.get("items") or [] if isinstance(item, dict)]
    selected_items = [
        item
        for item in items
        if clean_text(item.get("review_recommendation")) == SOURCE_REVIEW_SAME_EVENT
        and not string_list(item.get("failed_conditions"))
    ]
    replacement_ids = {clean_text(item.get("replacement_event_id")) for item in selected_items if clean_text(item.get("replacement_event_id"))}
    candidate_rows = scan_candidate_rows(candidate_events_path, replacement_ids)

    decision_candidates: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for index, item in enumerate(selected_items, start=1):
        replacement_id = clean_text(item.get("replacement_event_id"))
        candidate_row = candidate_rows.get(replacement_id)
        if not candidate_row:
            skipped.append(skip_record(index, item, "missing_replacement_candidate_row"))
            continue
        preview = candidate_row.get("manual_review_preview") if isinstance(candidate_row.get("manual_review_preview"), dict) else {}
        effect_ids = string_list(preview.get("merged_by_effect_ids"))
        component_event_ids = string_list(preview.get("merged_canonical_event_ids")) or string_list(item.get("component_event_ids"))
        canonical_input_ids = string_list(candidate_row.get("canonical_input_ids"))
        if not effect_ids:
            skipped.append(skip_record(index, item, "missing_effect_ids"))
            continue
        if len(component_event_ids) < 2:
            skipped.append(skip_record(index, item, "merge_requires_at_least_two_events"))
            continue
        decision_candidates.append(
            decision_candidate_from_review_item(
                item,
                decision_index=len(decision_candidates) + 1,
                reviewer=reviewer,
                reviewed_at=timestamp,
                effect_ids=effect_ids,
                component_event_ids=component_event_ids,
                canonical_input_ids=canonical_input_ids,
            )
        )

    return decision_candidates, {
        "schema_version": 1,
        "promotion_policy": PROMOTION_POLICY,
        "input_review_policy": review_report.get("review_policy"),
        "canonical_outputs_mutated": False,
        "source_canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "canonical_apply_performed": False,
        "auto_merge_performed": False,
        "accepted_canonical_decisions_created": False,
        "recommended_decision_candidate_records_written": True,
        "ready_for_canonical_apply": False,
        "input_review_item_count": len(items),
        "selected_review_item_count": len(selected_items),
        "decision_candidate_count": len(decision_candidates),
        "skipped_selected_item_count": len(skipped),
        "skipped_reason_counts": count_by(skipped, "reason"),
        "projected_event_reduction": sum(
            max(0, len(string_list(record.get("merge_canonical_event_ids"))) - 1)
            for record in decision_candidates
        ),
        "selected_replacement_count": len(replacement_ids),
        "candidate_replacement_rows_found": len(candidate_rows),
        "reviewer": reviewer,
        "reviewed_at": timestamp,
        "skipped_selected_items": skipped,
        "notes": [
            "These are decision candidates derived from the medium time_raw-only parser review.",
            "They are not applied; a separate effects-plan filter and stream apply are required for any sidecar corpus.",
        ],
    }


def validate_review_report_safety(report: dict[str, Any]) -> None:
    errors: list[str] = []
    if report.get("review_policy") != INPUT_REVIEW_POLICY:
        errors.append(f"review_policy must be {INPUT_REVIEW_POLICY}")
    for flag in (
        "canonical_outputs_mutated",
        "source_canonical_outputs_mutated",
        "preview_outputs_written",
        "decisions_created",
        "auto_merge_performed",
        "ready_for_runtime_promotion",
    ):
        if report.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError("medium time_raw-only review report is unsafe for promotion: " + "; ".join(errors))


def decision_candidate_from_review_item(
    item: dict[str, Any],
    *,
    decision_index: int,
    reviewer: str,
    reviewed_at: str,
    effect_ids: list[str],
    component_event_ids: list[str],
    canonical_input_ids: list[str],
) -> dict[str, Any]:
    replacement_id = clean_text(item.get("replacement_event_id"))
    decision_id = stable_hash(
        {
            "replacement_event_id": replacement_id,
            "effect_ids": effect_ids,
            "decision": "same_event",
            "promotion_policy": PROMOTION_POLICY,
        },
        prefix="mrtm_",
        length=20,
    )
    return {
        "manual_review_time_decision_id": decision_id,
        "decision_index": decision_index,
        "replacement_event_id": replacement_id,
        "review_type": "manual_review_medium_time_raw_only_candidate",
        "decision": "same_event",
        "effect_status": "source_reviewed_candidate_not_applied",
        "decision_source": INPUT_REVIEW_POLICY,
        "promotion_policy": PROMOTION_POLICY,
        "canonical_outputs_mutated": False,
        "review_band": "strict_medium_time_raw_only_parser_review",
        "confidence": clean_text(item.get("confidence")),
        "canonical_input_ids": canonical_input_ids,
        "merge_canonical_event_ids": component_event_ids,
        "effect_ids": effect_ids,
        "reviewer": reviewer,
        "reviewed_at": reviewed_at,
        "requires_explicit_apply_step": True,
        "evidence": {
            "time_raw_values": string_list(item.get("time_raw_values")),
            "parsed_minutes": int_list(item.get("parsed_minutes")),
            "exact_span_minutes": item.get("exact_span_minutes"),
            "review_reason_codes": string_list(item.get("review_reason_codes")),
            "date_iso_values": string_list(item.get("date_iso_values")),
            "location_raw_values": string_list(item.get("location_raw_values")),
            "source_file_values": string_list(item.get("source_file_values")),
        },
    }


def scan_candidate_rows(path: Path, replacement_ids: set[str]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    if not replacement_ids:
        return rows
    for event in iter_jsonl(path):
        event_id = clean_text(event.get("canonical_event_id")) or clean_text(event.get("event_id"))
        if event_id in replacement_ids:
            rows[event_id] = event
            if set(rows) == replacement_ids:
                break
    return rows


def skip_record(index: int, item: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "review_index": index,
        "replacement_event_id": clean_text(item.get("replacement_event_id")),
        "review_recommendation": clean_text(item.get("review_recommendation")),
        "reason": reason,
        "failed_conditions": string_list(item.get("failed_conditions")),
    }


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{path} line {line_number} must be a JSON object.")
            yield payload


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
    parser.add_argument("--candidate-events", type=Path, default=DEFAULT_CANDIDATE_EVENTS)
    parser.add_argument("--decisions-output", type=Path, default=DEFAULT_DECISIONS_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    parser.add_argument("--reviewer", default=DEFAULT_REVIEWER)
    parser.add_argument("--reviewed-at", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    decision_candidates, report = build_medium_time_raw_only_decision_candidates(
        read_json(args.review),
        candidate_events_path=args.candidate_events,
        reviewer=args.reviewer,
        reviewed_at=args.reviewed_at,
    )
    report["inputs"] = {"review": str(args.review), "candidate_events": str(args.candidate_events)}
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
