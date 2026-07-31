"""Create conservative AI-assisted suggestions for ER review packet items.

This step is intentionally non-destructive. It writes separate suggestion
artifacts, but it does not create validated decisions, plan effects, apply
effects, or mutate canonical event outputs.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any


DEFAULT_PACKET_PATH = Path("data/reports/entity_resolution_review_packet.json")
DEFAULT_SUGGESTIONS_OUTPUT = Path("data/reports/entity_resolution_review_suggestions.jsonl")
DEFAULT_REPORT_OUTPUT = Path("data/reports/entity_resolution_review_suggestions_report.json")
DEFAULT_REVIEWER = "codex_ai_entity_resolution_conservative_v1"

BLOCKING_SAME_EVENT_RISKS = {
    "coarse_or_uncertain_date_precision",
    "coordinates_far_apart",
    "date_mismatch_or_missing",
    "different_source_native_ids",
    "time_mismatch_or_one_missing",
    "type_differs",
    "weak_location_evidence",
}

STRONG_LOCATION_EVIDENCE = {
    "same_normalized_location",
    "trusted_coordinates_within_2km",
}

STRONG_TEXT_EVIDENCE = {
    "same_exact_normalized_text",
    "very_high_text_token_overlap",
    "high_text_token_overlap",
}


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    parser.add_argument("--suggestions-output", type=Path, default=DEFAULT_SUGGESTIONS_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    parser.add_argument("--reviewer", default=DEFAULT_REVIEWER)
    parser.add_argument("--reviewed-at", default=None, help="Optional ISO timestamp. Defaults to current UTC time.")
    parser.add_argument("--limit", type=int, default=0, help="Optional max packet items to review. 0 means all items.")
    return parser


def build_entity_resolution_ai_suggestions(
    packet: dict[str, Any],
    *,
    reviewer: str = DEFAULT_REVIEWER,
    reviewed_at: str | None = None,
    limit: int = 0,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    validate_packet_safety(packet)
    timestamp = reviewed_at or datetime.now(UTC).replace(microsecond=0).isoformat()
    packet_items = packet.get("items") if isinstance(packet.get("items"), list) else []
    selected_items = packet_items[:limit] if limit and limit > 0 else packet_items
    suggestions: list[dict[str, Any]] = []
    audit_items: list[dict[str, Any]] = []

    for item in selected_items:
        if not isinstance(item, dict):
            continue
        decision, confidence, rationale, evidence = suggest_packet_item_decision(item)
        review_item_id = clean_text(item.get("review_item_id"))
        if not review_item_id or not decision:
            continue
        suggestions.append(
            {
                "review_item_id": review_item_id,
                "suggested_decision": decision,
                "review_band": clean_text(item.get("review_band")),
                "score": item.get("score"),
                "cross_current_event": bool(item.get("cross_current_event")),
                "confidence": confidence,
                "reviewer": reviewer,
                "reviewed_at": timestamp,
                "rationale": rationale,
                "evidence": evidence,
            }
        )
        audit_items.append(
            {
                "review_item_id": review_item_id,
                "review_band": clean_text(item.get("review_band")),
                "suggested_decision": decision,
                "confidence": confidence,
                "rationale": rationale,
                "evidence": evidence,
            }
        )

    report = {
        "schema_version": 1,
        "suggestion_policy": "entity_resolution_ai_assisted_conservative_suggestions",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "validated_decisions_created": False,
        "auto_merge_performed": False,
        "packet_item_count": len(packet_items),
        "reviewed_item_count": len(selected_items),
        "suggestion_count": len(suggestions),
        "suggested_decision_counts": count_by(suggestions, "suggested_decision"),
        "confidence_counts": count_by(audit_items, "confidence"),
        "review_band_counts": count_by(audit_items, "review_band"),
        "reviewer": reviewer,
        "reviewed_at": timestamp,
        "heuristics": {
            "same_event": (
                "cross-current-event likely-band pairs with score >= 0.98, exact day, "
                "specific time, strong location evidence, strong text or native-ID evidence, "
                "and no blocking same-event risks"
            ),
            "distinct_events": (
                "weak-band candidates with date or coordinate conflicts, no same native ID, "
                "and no exact text evidence"
            ),
            "needs_more_evidence": "all candidates that are not safe enough for same_event or distinct_events",
        },
        "audit_sample": audit_items[:250],
        "audit_sample_truncated": len(audit_items) > 250,
        "notes": [
            "These are AI-assisted suggestions, not validated decisions.",
            "Convert accepted suggestions to ER decision records, then run validate_entity_resolution_decisions.py before planning effects.",
            "No canonical event outputs are mutated by this step.",
        ],
    }
    return suggestions, report


def validate_packet_safety(packet: dict[str, Any]) -> None:
    errors: list[str] = []
    if packet.get("packet_policy") != "entity_resolution_review_only":
        errors.append("packet_policy must be 'entity_resolution_review_only'")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "auto_merge_performed"):
        if packet.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError(f"packet is not a safe ER review input: {'; '.join(errors)}")


def suggest_packet_item_decision(item: dict[str, Any]) -> tuple[str, str, str, dict[str, Any]]:
    review_band = clean_text(item.get("review_band"))
    score = numeric_score(item.get("score"))
    evidence = set(text_list(item.get("evidence")))
    risk_flags = set(text_list(item.get("risk_flags")))
    left = item.get("left") if isinstance(item.get("left"), dict) else {}
    right = item.get("right") if isinstance(item.get("right"), dict) else {}
    same_native_id = bool(clean_text(left.get("source_native_id"))) and clean_text(left.get("source_native_id")) == clean_text(
        right.get("source_native_id")
    )
    exact_text_or_high_overlap = bool(evidence & STRONG_TEXT_EVIDENCE) or numeric_score(item.get("token_jaccard")) >= 0.95
    strong_location = bool(evidence & STRONG_LOCATION_EVIDENCE)
    no_blocking_risks = not bool(risk_flags & BLOCKING_SAME_EVENT_RISKS)
    base_same_event = (
        bool(item.get("cross_current_event"))
        and review_band == "likely_same_event_review"
        and score >= 0.98
        and "same_exact_day" in evidence
        and "same_specific_time" in evidence
        and strong_location
        and no_blocking_risks
        and ("same_source_native_id" in evidence or same_native_id or exact_text_or_high_overlap)
    )
    audit_evidence = {
        "score": score,
        "review_band": review_band,
        "same_native_id": same_native_id,
        "token_jaccard": numeric_score(item.get("token_jaccard")),
        "distance_km": item.get("distance_km"),
        "evidence": sorted(evidence),
        "risk_flags": sorted(risk_flags),
    }
    if base_same_event:
        return (
            "same_event",
            "high",
            (
                "AI-assisted ER review: likely-band cross-event pair with exact date/time, "
                "strong location evidence, strong identifier/text evidence, and no blocking risk flags."
            ),
            audit_evidence,
        )
    if (
        review_band == "weak_candidate"
        and ("date_mismatch_or_missing" in risk_flags or "coordinates_far_apart" in risk_flags)
        and "same_source_native_id" not in evidence
        and not same_native_id
        and "same_exact_normalized_text" not in evidence
    ):
        return (
            "distinct_events",
            "low",
            "AI-assisted ER review: weak-band candidate with conflicting date/location evidence and no strong identity tie.",
            audit_evidence,
        )
    return (
        "needs_more_evidence",
        "low",
        "AI-assisted ER review: candidate is not safe enough for an automatic same-event or distinct-event suggestion.",
        audit_evidence,
    )


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


def text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := clean_text(item))]


def numeric_score(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def main() -> int:
    args = build_argument_parser().parse_args()
    packet = read_json(args.packet)
    suggestions, report = build_entity_resolution_ai_suggestions(
        packet,
        reviewer=args.reviewer,
        reviewed_at=args.reviewed_at,
        limit=args.limit,
    )
    report["outputs"] = {
        "suggestions": str(args.suggestions_output),
        "report": str(args.report_output),
    }
    write_jsonl(args.suggestions_output, suggestions)
    write_json(args.report_output, report)
    print(
        json.dumps(
            {
                "suggestions": str(args.suggestions_output),
                "report": str(args.report_output),
                "suggestion_count": len(suggestions),
                "suggested_decision_counts": report["suggested_decision_counts"],
                "canonical_outputs_mutated": False,
                "auto_merge_performed": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
