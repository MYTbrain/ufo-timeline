"""Promote ER suggestion rows into separate AI-accepted decision records.

This does not validate or apply decisions. It creates a separate decision JSONL
that can be passed through validate_entity_resolution_decisions.py and then the
plan-only effects step.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any


DEFAULT_SUGGESTIONS = Path("data/reports/entity_resolution_review_suggestions.jsonl")
DEFAULT_SUGGESTIONS_REPORT = Path("data/reports/entity_resolution_review_suggestions_report.json")
DEFAULT_DECISIONS_OUTPUT = Path("data/canonical_full/entity_resolution_decisions_ai_accepted.jsonl")
DEFAULT_REPORT_OUTPUT = Path("data/reports/entity_resolution_suggestion_promotion_report.json")
DEFAULT_REVIEWER = "codex_ai_entity_resolution_accepted_v1"
ALLOWED_DECISIONS = {"same_event", "distinct_events", "needs_more_evidence"}


def promote_entity_resolution_suggestions(
    suggestions: list[dict[str, Any]],
    *,
    suggestions_report: dict[str, Any] | None = None,
    reviewer: str = DEFAULT_REVIEWER,
    reviewed_at: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if suggestions_report is not None:
        validate_suggestions_report(suggestions_report)
    timestamp = reviewed_at or datetime.now(UTC).replace(microsecond=0).isoformat()
    decisions: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for index, suggestion in enumerate(suggestions, start=1):
        review_item_id = clean_text(suggestion.get("review_item_id"))
        suggested_decision = clean_text(suggestion.get("suggested_decision"))
        confidence = clean_text(suggestion.get("confidence")) or "unknown"
        if not review_item_id:
            skipped.append({"suggestion_index": index, "error": "missing_review_item_id"})
            continue
        if suggested_decision not in ALLOWED_DECISIONS:
            skipped.append(
                {
                    "suggestion_index": index,
                    "review_item_id": review_item_id,
                    "suggested_decision": suggested_decision,
                    "error": "invalid_suggested_decision",
                }
            )
            continue
        rationale = clean_text(suggestion.get("rationale")) or "No rationale supplied."
        decisions.append(
            {
                "review_item_id": review_item_id,
                "decision": suggested_decision,
                "reviewer": reviewer,
                "reviewed_at": timestamp,
                "notes": f"Promoted AI-assisted ER suggestion ({confidence} confidence): {rationale}",
            }
        )

    report = {
        "schema_version": 1,
        "promotion_policy": "entity_resolution_suggestion_promotion_to_ai_accepted_decisions",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": True,
        "validated_decisions_created": False,
        "auto_merge_performed": False,
        "suggestion_count": len(suggestions),
        "promoted_decision_count": len(decisions),
        "skipped_suggestion_count": len(skipped),
        "decision_counts": count_by(decisions, "decision"),
        "source_confidence_counts": count_by(suggestions, "confidence"),
        "reviewer": reviewer,
        "reviewed_at": timestamp,
        "skipped_suggestions": skipped,
        "notes": [
            "Promoted decisions are not validated and not applied.",
            "Run validate_entity_resolution_decisions.py before planning effects.",
            "Only a separate AI-accepted decision file is written; canonical event outputs are unchanged.",
        ],
    }
    return decisions, report


def validate_suggestions_report(report: dict[str, Any]) -> None:
    errors: list[str] = []
    if report.get("suggestion_policy") != "entity_resolution_ai_assisted_conservative_suggestions":
        errors.append("suggestion_policy must be 'entity_resolution_ai_assisted_conservative_suggestions'")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "auto_merge_performed"):
        if report.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if report.get("decisions_created") is not False:
        errors.append("decisions_created must be false")
    if errors:
        raise ValueError(f"suggestions report is not safe to promote: {'; '.join(errors)}")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{path} line {line_number} must contain a JSON object.")
            rows.append(payload)
    return rows


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


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suggestions", type=Path, default=DEFAULT_SUGGESTIONS)
    parser.add_argument("--suggestions-report", type=Path, default=DEFAULT_SUGGESTIONS_REPORT)
    parser.add_argument("--decisions-output", type=Path, default=DEFAULT_DECISIONS_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    parser.add_argument("--reviewer", default=DEFAULT_REVIEWER)
    parser.add_argument("--reviewed-at", default=None, help="Optional ISO timestamp. Defaults to current UTC time.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    suggestions = read_jsonl(args.suggestions)
    suggestions_report = read_json(args.suggestions_report) if args.suggestions_report.exists() else None
    decisions, report = promote_entity_resolution_suggestions(
        suggestions,
        suggestions_report=suggestions_report,
        reviewer=args.reviewer,
        reviewed_at=args.reviewed_at,
    )
    report["outputs"] = {
        "decisions": str(args.decisions_output),
        "report": str(args.report_output),
    }
    write_jsonl(args.decisions_output, decisions)
    write_json(args.report_output, report)
    print(
        json.dumps(
            {
                "decisions": str(args.decisions_output),
                "report": str(args.report_output),
                "promoted_decision_count": len(decisions),
                "decision_counts": report["decision_counts"],
                "canonical_outputs_mutated": False,
                "auto_merge_performed": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if not report["skipped_suggestion_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
