"""Recommend review outcomes for strict time-normalization evidence packets.

This is a report-only adjudication aid. It consumes the source-row evidence
packet for strict time-normalization candidates and separates clean clock-token
cases from cases that still need source review. It does not create accepted
decisions, plan effects, apply merges, or mutate canonical outputs.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_PACKET = Path("data/reports/entity_resolution_cluster_time_norm_source_evidence_packet.json")
DEFAULT_JSON_OUTPUT = Path("data/reports/entity_resolution_cluster_time_norm_source_review_recommendations.json")
DEFAULT_CSV_OUTPUT = Path("data/reports/entity_resolution_cluster_time_norm_source_review_recommendations.csv")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/entity_resolution_cluster_time_norm_source_review_recommendations.md")

INPUT_PACKET_POLICY = "entity_resolution_cluster_time_normalization_source_row_evidence_review_only"
RECOMMENDATION_POLICY = "entity_resolution_time_norm_auto_recommendation_only"
RECOMMEND_SAME_EVENT = "recommend_same_event"
NEEDS_MORE_EVIDENCE = "needs_more_evidence"

CSV_FIELDS = (
    "review_rank",
    "review_item_id",
    "effect_id",
    "recommendation",
    "confidence",
    "projected_event_reduction",
    "time_pattern_classification",
    "time_tokens",
    "parsed_minutes",
    "minute_span",
    "active_conflicts",
    "blockers",
    "reason_codes",
    "source_names",
    "source_native_ids",
    "dates",
    "locations",
)


def build_time_norm_source_review_recommendations(packet: dict[str, Any]) -> dict[str, Any]:
    validate_packet_safety(packet)
    items = [item for item in packet.get("items") or [] if isinstance(item, dict)]
    recommendations = [recommend_item(item) for item in items]
    review_item_ids = [clean_text(item.get("review_item_id")) for item in recommendations if clean_text(item.get("review_item_id"))]
    effect_ids = [clean_text(item.get("effect_id")) for item in recommendations if clean_text(item.get("effect_id"))]
    projected_by_recommendation: dict[str, int] = {}
    for item in recommendations:
        key = clean_text(item.get("recommendation")) or "unknown"
        projected_by_recommendation[key] = projected_by_recommendation.get(key, 0) + as_int(
            item.get("projected_event_reduction")
        )
    return {
        "schema_version": 1,
        "recommendation_policy": RECOMMENDATION_POLICY,
        "input_packet_policy": packet.get("packet_policy"),
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "validated_decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "summary": {
            "packet_item_count": len(items),
            "reviewed_item_count": len(recommendations),
            "candidate_effect_count": len(items),
            "recommendation_counts": count_by(recommendations, "recommendation"),
            "recommended_same_event_count": sum(1 for item in recommendations if item.get("recommendation") == RECOMMEND_SAME_EVENT),
            "needs_more_evidence_count": sum(1 for item in recommendations if item.get("recommendation") == NEEDS_MORE_EVIDENCE),
            "skipped_or_invalid_count": len(items) - len(recommendations),
            "confidence_counts": count_by(recommendations, "confidence"),
            "token_class_counts": count_by(recommendations, "token_class"),
            "blocker_counts": count_blockers(recommendations),
            "projected_event_reduction_by_recommendation": dict(sorted(projected_by_recommendation.items())),
            "duplicate_review_item_id_count": duplicate_count(review_item_ids),
            "duplicate_effect_id_count": duplicate_count(effect_ids),
        },
        "recommendations": recommendations,
        "notes": [
            "Recommendations are conservative review guidance only.",
            "recommend_same_event requires clean 3-4 digit clock tokens, only time-value conflict, complete evidence coverage, and all strict hard gates.",
            "needs_more_evidence keeps symbolic or shorthand time tokens out of automated same-event recommendations.",
            "This report does not create validated decisions or mutate canonical outputs.",
        ],
    }


def validate_packet_safety(packet: dict[str, Any]) -> None:
    errors: list[str] = []
    if packet.get("packet_policy") != INPUT_PACKET_POLICY:
        errors.append(f"packet_policy must be {INPUT_PACKET_POLICY}")
    for flag in (
        "canonical_outputs_mutated",
        "preview_outputs_written",
        "decisions_created",
        "decision_outputs_created",
        "auto_merge_performed",
        "override_decisions_created",
        "ready_for_canonical_apply",
    ):
        if packet.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError("source evidence packet is unsafe for recommendations: " + "; ".join(errors))


def recommend_item(item: dict[str, Any]) -> dict[str, Any]:
    source = item.get("shadow_preview_override_source") if isinstance(item.get("shadow_preview_override_source"), dict) else {}
    hard_gates = source.get("hard_gates") if isinstance(source.get("hard_gates"), dict) else {}
    summary = item.get("source_summary") if isinstance(item.get("source_summary"), dict) else {}
    conflicts = item.get("conflict_summary") if isinstance(item.get("conflict_summary"), dict) else {}
    conflict_flags = conflicts.get("conflict_flags") if isinstance(conflicts.get("conflict_flags"), dict) else {}
    active_conflicts = sorted(name for name, active in conflict_flags.items() if active)
    time_tokens = string_list(source.get("time_tokens"))
    parsed_minutes = int_list(source.get("parsed_minutes"))
    blockers = recommendation_blockers(
        item=item,
        source=source,
        hard_gates=hard_gates,
        summary=summary,
        active_conflicts=active_conflicts,
        time_tokens=time_tokens,
        parsed_minutes=parsed_minutes,
    )
    recommendation = RECOMMEND_SAME_EVENT if not blockers else NEEDS_MORE_EVIDENCE
    minute_span = max(parsed_minutes) - min(parsed_minutes) if len(parsed_minutes) >= 2 else None
    reason_codes = recommendation_reason_codes(
        recommendation=recommendation,
        blockers=blockers,
        active_conflicts=active_conflicts,
        time_tokens=time_tokens,
    )
    return {
        "review_rank": item.get("review_rank"),
        "cluster_review_id": clean_text(item.get("review_item_id")),
        "review_item_id": clean_text(item.get("review_item_id")),
        "effect_id": clean_text(item.get("effect_id")),
        "recommendation": recommendation,
        "confidence": "medium" if recommendation == RECOMMEND_SAME_EVENT else "low",
        "projected_event_reduction": as_int(item.get("projected_event_reduction")),
        "time_pattern_classification": clean_text(source.get("time_pattern_classification")),
        "review_risk_tier": clean_text(source.get("review_risk_tier")),
        "time_tokens": time_tokens,
        "parsed_minutes": parsed_minutes,
        "minute_span": minute_span,
        "token_class": "clean_clock_tokens" if all(is_clean_clock_token(token) for token in time_tokens) else "symbolic_or_shorthand_tokens",
        "active_conflicts": active_conflicts,
        "blockers": blockers,
        "reason_codes": reason_codes,
        "blocking_reason_codes": blockers,
        "source_names": string_list(summary.get("source_names")),
        "source_name_count": len(string_list(summary.get("source_names"))),
        "source_native_ids": string_list(summary.get("source_native_ids")),
        "source_native_id_count": len(string_list(summary.get("source_native_ids"))),
        "dates": string_list(summary.get("date_values")),
        "date_count": len(string_list(summary.get("date_values"))),
        "locations": string_list(summary.get("location_values")),
        "location_count": len(string_list(summary.get("location_values"))),
        "merge_canonical_event_ids": string_list(item.get("merge_canonical_event_ids")),
        "current_event_ids": string_list(item.get("merge_canonical_event_ids")),
        "candidate_canonical_input_ids": string_list(item.get("candidate_canonical_input_ids")),
        "notes": (
            "Clean clock-token time normalization candidate; still requires explicit decision/apply flow."
            if recommendation == RECOMMEND_SAME_EVENT
            else "Deferred because one or more source-evidence gates still need review."
        ),
    }


def recommendation_blockers(
    *,
    item: dict[str, Any],
    source: dict[str, Any],
    hard_gates: dict[str, Any],
    summary: dict[str, Any],
    active_conflicts: list[str],
    time_tokens: list[str],
    parsed_minutes: list[int],
) -> list[str]:
    blockers: list[str] = []
    if item.get("missing_canonical_event_ids"):
        blockers.append("missing_canonical_event_ids")
    if item.get("candidate_input_ids_missing_from_evidence"):
        blockers.append("candidate_input_ids_missing_from_evidence")
    if as_int(item.get("projected_event_reduction")) <= 0:
        blockers.append("no_projected_event_reduction")
    if clean_text(source.get("review_risk_tier")) != "lower":
        blockers.append("review_risk_tier_not_lower")
    if clean_text(source.get("time_pattern_classification")) not in {
        "single_exact_minute",
        "nearby_exact_minutes_15m_or_less",
    }:
        blockers.append("ineligible_time_pattern_classification")
    if active_conflicts != ["time"]:
        blockers.append("non_time_conflicts_present")
    if not time_tokens:
        blockers.append("missing_time_tokens")
    elif not all(is_clean_clock_token(token) for token in time_tokens):
        blockers.append("symbolic_or_shorthand_time_tokens")
    if len(parsed_minutes) < 2:
        blockers.append("insufficient_parsed_minutes")
    elif max(parsed_minutes) - min(parsed_minutes) > 15:
        blockers.append("parsed_minute_span_over_15")
    if not hard_gate_bool(hard_gates, "eligible_classification"):
        blockers.append("hard_gate_eligible_classification_failed")
    if not hard_gate_bool(hard_gates, "lower_risk_tier"):
        blockers.append("hard_gate_lower_risk_tier_failed")
    if not hard_gate_bool(hard_gates, "no_fuzzy_ambiguous_or_unknown_tokens"):
        blockers.append("hard_gate_no_fuzzy_ambiguous_or_unknown_tokens_failed")
    if as_int(hard_gates.get("span_minutes_at_or_below")) > 15:
        blockers.append("hard_gate_span_over_15")
    for field, blocker in (
        ("source_names", "not_single_source_name"),
        ("source_native_ids", "not_single_source_native_id"),
        ("date_values", "not_single_date"),
        ("location_values", "not_single_location"),
    ):
        if len(string_list(summary.get(field))) != 1:
            blockers.append(blocker)
    return blockers


def recommendation_reason_codes(
    *,
    recommendation: str,
    blockers: list[str],
    active_conflicts: list[str],
    time_tokens: list[str],
) -> list[str]:
    if recommendation == RECOMMEND_SAME_EVENT:
        return [
            "auto_recommend_preview_candidate_numeric_time_only",
            "clean_clock_tokens",
            "time_only_conflict",
            "single_source_native_date_location",
            "report_only_not_decision",
        ]
    reason_codes = ["needs_more_evidence"]
    if "symbolic_or_shorthand_time_tokens" in blockers:
        reason_codes.append("defer_symbolic_or_short_time_token")
    if "non_time_conflicts_present" in blockers:
        reason_codes.append("defer_conflicting_source_row_evidence")
    if not time_tokens:
        reason_codes.append("defer_missing_time_tokens")
    return reason_codes + blockers


def hard_gate_bool(hard_gates: dict[str, Any], key: str) -> bool:
    return hard_gates.get(key) is True


def is_clean_clock_token(token: str) -> bool:
    if not re.fullmatch(r"\d{3,4}", clean_text(token)):
        return False
    value = clean_text(token)
    hour = int(value[:-2])
    minute = int(value[-2:])
    return 0 <= hour <= 23 and 0 <= minute <= 59


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in payload.get("recommendations") or []:
            if isinstance(row, dict):
                writer.writerow(csv_row(row))


def csv_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "review_rank": row.get("review_rank"),
        "review_item_id": row.get("review_item_id"),
        "effect_id": row.get("effect_id"),
        "recommendation": row.get("recommendation"),
        "confidence": row.get("confidence"),
        "projected_event_reduction": row.get("projected_event_reduction"),
        "time_pattern_classification": row.get("time_pattern_classification"),
        "time_tokens": "; ".join(string_list(row.get("time_tokens"))),
        "parsed_minutes": "; ".join(str(value) for value in int_list(row.get("parsed_minutes"))),
        "minute_span": row.get("minute_span"),
        "active_conflicts": "; ".join(string_list(row.get("active_conflicts"))),
        "blockers": "; ".join(string_list(row.get("blockers"))),
        "reason_codes": "; ".join(string_list(row.get("reason_codes"))),
        "source_names": "; ".join(string_list(row.get("source_names"))),
        "source_native_ids": "; ".join(string_list(row.get("source_native_ids"))),
        "dates": "; ".join(string_list(row.get("dates"))),
        "locations": "; ".join(string_list(row.get("locations"))),
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    lines = [
        "# Cluster Time-Normalization Source Review Recommendations",
        "",
        "This report is review-only. It does not create decisions or mutate canonical outputs.",
        "",
        "## Summary",
        "",
        f"- Candidate effects: `{summary.get('candidate_effect_count', 0)}`",
        f"- Reviewed items: `{summary.get('reviewed_item_count', 0)}`",
        f"- Recommendation counts: `{json.dumps(summary.get('recommendation_counts') or {}, sort_keys=True)}`",
        f"- Token class counts: `{json.dumps(summary.get('token_class_counts') or {}, sort_keys=True)}`",
        f"- Projected reduction by recommendation: `{json.dumps(summary.get('projected_event_reduction_by_recommendation') or {}, sort_keys=True)}`",
        f"- Canonical outputs mutated: `{str(payload.get('canonical_outputs_mutated')).lower()}`",
        "",
        "## Deferred Blockers",
        "",
    ]
    blocker_counts = summary.get("blocker_counts") if isinstance(summary.get("blocker_counts"), dict) else {}
    if blocker_counts:
        for key, count in blocker_counts.items():
            lines.append(f"- `{key}`: `{count}`")
    else:
        lines.append("- none")
    lines.extend(["", "## Recommendations", ""])
    for item in payload.get("recommendations") or []:
        if not isinstance(item, dict):
            continue
        lines.extend(
            [
                f"### #{item.get('review_rank')} {item.get('review_item_id')}",
                "",
                f"- Recommendation: `{item.get('recommendation')}` confidence `{item.get('confidence')}`",
                f"- Effect ID: `{item.get('effect_id')}`",
                f"- Projected reduction: `{item.get('projected_event_reduction')}`",
                f"- Time tokens: {', '.join(string_list(item.get('time_tokens'))) or 'none'}",
                f"- Parsed minutes: {', '.join(str(value) for value in int_list(item.get('parsed_minutes'))) or 'none'}",
                f"- Minute span: `{item.get('minute_span')}`",
                f"- Active conflicts: {', '.join(string_list(item.get('active_conflicts'))) or 'none'}",
                f"- Blockers: {', '.join(string_list(item.get('blockers'))) or 'none'}",
                f"- Reason codes: {', '.join(string_list(item.get('reason_codes'))) or 'none'}",
                "",
            ]
        )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = clean_text(row.get(key)) or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def count_blockers(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for blocker in string_list(row.get("blockers")):
            counts[blocker] = counts.get(blocker, 0) + 1
    return dict(sorted(counts.items()))


def duplicate_count(values: list[str]) -> int:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return len(duplicates)


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [text for item in value if (text := clean_text(item))]
    text = clean_text(value)
    return [text] if text else []


def int_list(value: Any) -> list[int]:
    result: list[int] = []
    if not isinstance(value, list):
        return result
    for item in value:
        try:
            result.append(int(item))
        except (TypeError, ValueError):
            continue
    return result


def as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_time_norm_source_review_recommendations(read_json(args.packet))
    report["inputs"] = {"packet": str(args.packet)}
    report["outputs"] = {
        "json": str(args.json_output),
        "csv": str(args.csv_output),
        "markdown": str(args.markdown_output),
    }
    write_json(args.json_output, report)
    write_csv(args.csv_output, report)
    write_markdown(args.markdown_output, report)
    print(
        json.dumps(
            {
                "json_output": str(args.json_output),
                "csv_output": str(args.csv_output),
                "markdown_output": str(args.markdown_output),
                "recommendation_policy": report["recommendation_policy"],
                "summary": report["summary"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
