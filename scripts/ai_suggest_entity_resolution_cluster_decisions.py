"""Create conservative AI-assisted suggestions for ER cluster review items.

This is a report-only triage aid. It does not create decisions, validate
decisions, plan effects, apply merges, or mutate canonical outputs.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from parser.canonical_schema import clean_text


DEFAULT_PACKET_PATH = Path("data/reports/entity_resolution_cluster_review_packet.json")
DEFAULT_SUGGESTIONS_OUTPUT = Path("data/reports/entity_resolution_cluster_review_suggestions.jsonl")
DEFAULT_REPORT_OUTPUT = Path("data/reports/entity_resolution_cluster_review_suggestions_report.json")
DEFAULT_REVIEWER = "codex_ai_entity_resolution_cluster_conservative_v1"

SAFE_SAME_EVENT_FAMILIES = {
    "same_source_native_id_strong_date",
    "same_source_url_strong_date",
    "strong_date_location_exact_text",
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


def build_entity_resolution_cluster_ai_suggestions(
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
        cluster_review_id = clean_text(item.get("cluster_review_id"))
        if not cluster_review_id:
            continue
        decision, confidence, rationale, evidence = suggest_cluster_item_decision(item)
        suggestions.append(
            {
                "cluster_review_id": cluster_review_id,
                "suggested_decision": decision,
                "tier": clean_text(item.get("tier")),
                "family_id": clean_text(item.get("family_id")),
                "confidence": confidence,
                "reviewer": reviewer,
                "reviewed_at": timestamp,
                "rationale": rationale,
                "evidence": evidence,
            }
        )
        audit_items.append(
            {
                "cluster_review_id": cluster_review_id,
                "tier": clean_text(item.get("tier")),
                "family_id": clean_text(item.get("family_id")),
                "suggested_decision": decision,
                "confidence": confidence,
                "rationale": rationale,
                "evidence": evidence,
            }
        )

    report = {
        "schema_version": 1,
        "suggestion_policy": "entity_resolution_cluster_ai_assisted_conservative_suggestions",
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
        "tier_counts": count_by(audit_items, "tier"),
        "family_counts": count_by(audit_items, "family_id"),
        "reviewer": reviewer,
        "reviewed_at": timestamp,
        "heuristics": {
            "same_event": (
                "complete non-truncated cluster in a conservative same-event family with one exact date, "
                "one normalized location, at least two current events, and no exported ID mismatch"
            ),
            "needs_more_evidence": "all clusters outside the strict conservative same-event rule",
        },
        "audit_sample": audit_items[:250],
        "audit_sample_truncated": len(audit_items) > 250,
        "notes": [
            "These are suggestions only, not validated decisions.",
            "Accepted suggestions must be converted to cluster decision records and validated before effects are planned.",
            "Do not add cluster projected reductions to pairwise ER reductions without overlap analysis.",
        ],
    }
    return suggestions, report


def validate_packet_safety(packet: dict[str, Any]) -> None:
    errors: list[str] = []
    if packet.get("packet_policy") != "entity_resolution_cluster_review_only":
        errors.append("packet_policy must be 'entity_resolution_cluster_review_only'")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "decisions_created", "auto_merge_performed"):
        if packet.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError(f"packet is not a safe ER cluster review input: {'; '.join(errors)}")


def suggest_cluster_item_decision(item: dict[str, Any]) -> tuple[str, str, str, dict[str, Any]]:
    family_id = clean_text(item.get("family_id"))
    tier = clean_text(item.get("tier"))
    current_event_ids = string_list(item.get("current_event_ids"))
    unique_count = as_int(item.get("unique_current_event_count")) or 0
    distinct_date_count = as_int(item.get("distinct_date_count")) or 0
    distinct_location_count = as_int(item.get("distinct_location_count")) or 0
    id_list_complete = bool(current_event_ids) and not bool(item.get("current_event_ids_truncated")) and len(current_event_ids) == unique_count
    same_event_safe = (
        tier == "conservative"
        and family_id in SAFE_SAME_EVENT_FAMILIES
        and unique_count >= 2
        and id_list_complete
        and distinct_date_count <= 1
        and distinct_location_count <= 1
    )
    evidence = {
        "tier": tier,
        "family_id": family_id,
        "unique_current_event_count": unique_count,
        "exported_current_event_id_count": len(current_event_ids),
        "current_event_ids_truncated": bool(item.get("current_event_ids_truncated")),
        "distinct_date_count": distinct_date_count,
        "distinct_location_count": distinct_location_count,
        "source_record_count": as_int(item.get("source_record_count")) or 0,
        "projected_event_reduction": as_int(item.get("projected_event_reduction")) or 0,
    }
    if same_event_safe:
        return (
            "same_event",
            "medium",
            "Conservative cluster suggestion: strict family, complete current-event IDs, one date, and one location.",
            evidence,
        )
    return (
        "needs_more_evidence",
        "low",
        "Cluster is outside the strict conservative same-event suggestion rule.",
        evidence,
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


def string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := clean_text(item))]


def as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = clean_text(row.get(key)) or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def main() -> int:
    args = build_argument_parser().parse_args()
    packet = read_json(args.packet)
    suggestions, report = build_entity_resolution_cluster_ai_suggestions(
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
