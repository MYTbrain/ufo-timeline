"""Create conservative AI-assisted decisions for manual-review queue items.

This script is intentionally non-destructive. It writes a separate AI-assisted
decisions JSONL plus applied-decision/report artifacts, but it does not mutate
canonical events or runtime outputs.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_canonical_ufo_dataset import apply_manual_review_decisions


DEFAULT_QUEUE_PATH = Path("data/canonical_full/manual_review_queue.jsonl")
DEFAULT_DECISIONS_OUTPUT = Path("data/canonical_full/manual_review_decisions_ai_assisted.jsonl")
DEFAULT_APPLIED_OUTPUT = Path("data/canonical_full/manual_review_applied_decisions_ai_assisted.jsonl")
DEFAULT_REPORT_OUTPUT = Path("data/reports/manual_review_ai_decisions_report.json")
DEFAULT_REVIEWER = "codex_ai_conservative_review_v1"


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE_PATH)
    parser.add_argument("--decisions-output", type=Path, default=DEFAULT_DECISIONS_OUTPUT)
    parser.add_argument("--applied-output", type=Path, default=DEFAULT_APPLIED_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    parser.add_argument("--reviewer", default=DEFAULT_REVIEWER)
    parser.add_argument("--reviewed-at", default=None, help="Optional ISO timestamp. Defaults to current UTC time.")
    parser.add_argument("--limit", type=int, default=0, help="Optional max queue items to review. 0 means all items.")
    return parser


def build_ai_assisted_decisions(
    queue: list[dict[str, Any]],
    *,
    reviewer: str = DEFAULT_REVIEWER,
    reviewed_at: str | None = None,
    limit: int = 0,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    timestamp = reviewed_at or datetime.now(UTC).replace(microsecond=0).isoformat()
    selected_queue = queue[:limit] if limit and limit > 0 else queue
    decisions: list[dict[str, Any]] = []
    audit_items: list[dict[str, Any]] = []

    for item in selected_queue:
        decision, confidence, rationale, evidence = review_queue_item(item)
        review_item_id = clean_text(item.get("review_item_id"))
        if not review_item_id or not decision:
            continue
        record = {
            "review_item_id": review_item_id,
            "decision": decision,
            "reviewer": reviewer,
            "reviewed_at": timestamp,
            "notes": rationale,
        }
        if decision == "exclude_source_row":
            input_id = clean_text(item.get("canonical_input_id"))
            if input_id:
                record["exclude_canonical_input_ids"] = [input_id]
        decisions.append(record)
        audit_items.append({
            "review_item_id": review_item_id,
            "review_type": clean_text(item.get("review_type")),
            "decision": decision,
            "confidence": confidence,
            "rationale": rationale,
            "evidence": evidence,
        })

    return decisions, {
        "schema_version": 1,
        "review_policy": "ai_assisted_conservative",
        "canonical_outputs_mutated": False,
        "queue_item_count": len(queue),
        "reviewed_item_count": len(selected_queue),
        "decision_count": len(decisions),
        "decision_counts": count_by(decisions, "decision"),
        "confidence_counts": count_by(audit_items, "confidence"),
        "reviewer": reviewer,
        "reviewed_at": timestamp,
        "heuristics": {
            "duplicate_candidate_same_event": (
                "score=1.0, same strong date, same normalized location, similar source text, "
                "and shared source id, same native id, or source text similarity >= 0.999"
            ),
            "duplicate_candidate_needs_more_evidence": "candidate lacks the strongest duplicate tie-breakers",
            "row_shape_anomaly_accept_preserved_row": "row is already preserved; no exclusion or repair is inferred",
        },
        "audit_sample": audit_items[:250],
        "audit_sample_truncated": len(audit_items) > 250,
    }


def review_queue_item(item: dict[str, Any]) -> tuple[str | None, str, str, dict[str, Any]]:
    review_type = clean_text(item.get("review_type"))
    if review_type == "duplicate_candidate":
        return review_duplicate_candidate(item)
    if review_type == "row_shape_anomaly":
        return (
            "accept_preserved_row",
            "medium",
            "AI-assisted conservative review: accept the preserved malformed row as imported; no exclusion or repair is inferred.",
            {
                "source_file": clean_text(item.get("source_file")),
                "source_row_number": item.get("source_row_number"),
                "source_row_anomalies": item.get("source_row_anomalies") or [],
            },
        )
    return (
        None,
        "none",
        "No conservative AI-assisted heuristic exists for this review type.",
        {"review_type": review_type},
    )


def review_duplicate_candidate(item: dict[str, Any]) -> tuple[str, str, str, dict[str, Any]]:
    candidate = item.get("candidate") if isinstance(item.get("candidate"), dict) else {}
    reasons = set(candidate.get("reasons") or [])
    signals = candidate.get("signals") if isinstance(candidate.get("signals"), dict) else {}
    records = candidate.get("records") if isinstance(candidate.get("records"), list) else []
    source_text_similarity = float(signals.get("source_text_similarity") or 0.0)
    shared_source_identifier = bool(signals.get("shared_source_identifier"))
    native_ids = {
        text
        for record in records
        if isinstance(record, dict)
        if (text := clean_text(record.get("source_native_id")))
    }
    same_native_id = len(native_ids) == 1 and bool(native_ids)
    base_exact_match = (
        candidate.get("score") == 1.0
        and {"same_strong_date", "same_normalized_location", "similar_source_text"}.issubset(reasons)
        and bool(candidate.get("blocking", {}).get("date_iso") if isinstance(candidate.get("blocking"), dict) else None)
        and bool(candidate.get("blocking", {}).get("location_key") if isinstance(candidate.get("blocking"), dict) else None)
    )
    strongest_tie = shared_source_identifier or same_native_id or source_text_similarity >= 0.999
    evidence = {
        "candidate_id": clean_text(candidate.get("duplicate_candidate_id") or candidate.get("candidate_id")),
        "score": candidate.get("score"),
        "reasons": sorted(reasons),
        "source_text_similarity": source_text_similarity,
        "shared_source_identifier": shared_source_identifier,
        "same_native_id": same_native_id,
        "record_count": len(records),
        "canonical_input_ids": candidate.get("canonical_input_ids") or [],
    }
    if base_exact_match and strongest_tie:
        return (
            "same_event",
            "high",
            (
                "AI-assisted conservative review: same strong date/location with near-identical text "
                "and a strong identifier/text tie; treat as the same event."
            ),
            evidence,
        )
    return (
        "needs_more_evidence",
        "low",
        (
            "AI-assisted conservative review: candidate has same date/location and similar text, "
            "but lacks the strongest identifier/text tie-breaker for an automatic same-event decision."
        ),
        evidence,
    )


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{path} line {line_number} must be a JSON object.")
            records.append(payload)
    return records


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def main() -> int:
    args = build_argument_parser().parse_args()
    queue = read_jsonl(args.queue)
    decisions, report = build_ai_assisted_decisions(
        queue,
        reviewer=args.reviewer,
        reviewed_at=args.reviewed_at,
        limit=args.limit,
    )
    _updated_queue, applied_decisions, decision_report = apply_manual_review_decisions(
        queue,
        decisions,
        decisions_path=args.decisions_output,
    )
    report["decision_ingestion_report"] = decision_report
    report["applied_decision_count"] = len(applied_decisions)
    report["invalid_decision_count"] = len(decision_report.get("invalid_decisions", []))
    report["unknown_review_item_id_count"] = len(decision_report.get("unknown_review_item_ids", []))
    report["outputs"] = {
        "decisions": str(args.decisions_output),
        "applied_decisions": str(args.applied_output),
        "report": str(args.report_output),
    }
    write_jsonl(args.decisions_output, decisions)
    write_jsonl(args.applied_output, applied_decisions)
    write_json(args.report_output, report)
    print(json.dumps({
        "decisions": str(args.decisions_output),
        "applied_decisions": str(args.applied_output),
        "report": str(args.report_output),
        "decision_count": len(decisions),
        "applied_decision_count": len(applied_decisions),
        "decision_counts": report["decision_counts"],
        "canonical_outputs_mutated": False,
    }, indent=2, ensure_ascii=False))
    return 0 if not report["invalid_decision_count"] and not report["unknown_review_item_id_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
