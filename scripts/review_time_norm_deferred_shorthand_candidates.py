"""Review deferred strict time-normalization shorthand candidates.

This is a non-destructive source-evidence review aid. It examines the
``needs_more_evidence`` items from the strict time-normalization recommendation
report and identifies the narrow subset where the only remaining issue is
source shorthand time notation such as ``20+`` or ``21`` alongside nearby exact
clock tokens.

The output is still review-only. It does not create accepted decisions, apply
merges, or rewrite canonical outputs.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import re
from typing import Any


DEFAULT_PACKET = Path("data/reports/entity_resolution_cluster_time_norm_source_evidence_packet.json")
DEFAULT_RECOMMENDATIONS = Path("data/reports/entity_resolution_cluster_time_norm_source_review_recommendations.json")
DEFAULT_JSON_OUTPUT = Path("data/reports/entity_resolution_cluster_time_norm_deferred_shorthand_review.json")
DEFAULT_CSV_OUTPUT = Path("data/reports/entity_resolution_cluster_time_norm_deferred_shorthand_review.csv")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/entity_resolution_cluster_time_norm_deferred_shorthand_review.md")

INPUT_PACKET_POLICY = "entity_resolution_cluster_time_normalization_source_row_evidence_review_only"
INPUT_RECOMMENDATION_POLICY = "entity_resolution_time_norm_auto_recommendation_only"
REVIEW_POLICY = "entity_resolution_time_norm_deferred_shorthand_source_review_only"
SOURCE_REVIEW_SAME_EVENT = "source_review_same_event_candidate"
REMAIN_DEFERRED = "remain_deferred"
ALLOWED_SHORTHAND_BLOCKERS = {"symbolic_or_shorthand_time_tokens"}

CSV_FIELDS = (
    "review_rank",
    "review_item_id",
    "effect_id",
    "review_recommendation",
    "confidence",
    "projected_event_reduction",
    "time_tokens",
    "parsed_token_minutes",
    "token_minute_span",
    "active_conflicts",
    "blockers",
    "review_reason_codes",
    "source_names",
    "source_native_ids",
    "dates",
    "locations",
)


def build_deferred_shorthand_review(
    *,
    packet: dict[str, Any],
    recommendations_report: dict[str, Any],
) -> dict[str, Any]:
    validate_packet_safety(packet)
    validate_recommendations_safety(recommendations_report)

    packet_items_by_id = {
        clean_text(item.get("review_item_id")): item
        for item in packet.get("items") or []
        if isinstance(item, dict) and clean_text(item.get("review_item_id"))
    }
    deferred = [
        item
        for item in recommendations_report.get("recommendations") or []
        if isinstance(item, dict) and clean_text(item.get("recommendation")) == "needs_more_evidence"
    ]
    reviewed_items: list[dict[str, Any]] = []
    for item in deferred:
        review_item_id = clean_text(item.get("review_item_id"))
        packet_item = packet_items_by_id.get(review_item_id) or {}
        reviewed_items.append(review_deferred_item(item, packet_item=packet_item))

    projected_by_recommendation: dict[str, int] = {}
    for item in reviewed_items:
        key = clean_text(item.get("review_recommendation")) or "unknown"
        projected_by_recommendation[key] = projected_by_recommendation.get(key, 0) + as_int(
            item.get("projected_event_reduction")
        )

    return {
        "schema_version": 1,
        "review_policy": REVIEW_POLICY,
        "input_packet_policy": packet.get("packet_policy"),
        "input_recommendation_policy": recommendations_report.get("recommendation_policy"),
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "validated_decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "summary": {
            "deferred_input_count": len(deferred),
            "reviewed_item_count": len(reviewed_items),
            "review_recommendation_counts": count_by(reviewed_items, "review_recommendation"),
            "confidence_counts": count_by(reviewed_items, "confidence"),
            "projected_event_reduction_by_review_recommendation": dict(sorted(projected_by_recommendation.items())),
            "blocker_counts": count_blockers(reviewed_items),
        },
        "items": reviewed_items,
        "notes": [
            "This report is source-review guidance only and does not accept or apply merges.",
            "source_review_same_event_candidate requires time-only conflicts, same source/native/date/location evidence, identical normalized summaries, and shorthand tokens within a 15-minute band of exact clock evidence.",
            "Candidates with non-time conflicts remain deferred.",
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
        raise ValueError("source evidence packet is unsafe for deferred shorthand review: " + "; ".join(errors))


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
        raise ValueError("recommendations report is unsafe for deferred shorthand review: " + "; ".join(errors))


def review_deferred_item(item: dict[str, Any], *, packet_item: dict[str, Any]) -> dict[str, Any]:
    source_summary = packet_item.get("source_summary") if isinstance(packet_item.get("source_summary"), dict) else {}
    conflict_summary = packet_item.get("conflict_summary") if isinstance(packet_item.get("conflict_summary"), dict) else {}
    conflict_flags = conflict_summary.get("conflict_flags") if isinstance(conflict_summary.get("conflict_flags"), dict) else {}
    active_conflicts = sorted(name for name, active in conflict_flags.items() if active)
    blockers = string_list(item.get("blockers"))
    time_tokens = string_list(item.get("time_tokens"))
    token_parse = parse_time_tokens(time_tokens)
    summary_texts = normalized_summary_texts(packet_item)
    conditions = {
        "packet_item_present": bool(packet_item),
        "time_only_conflict": active_conflicts == ["time"],
        "allowed_shorthand_blockers_only": set(blockers).issubset(ALLOWED_SHORTHAND_BLOCKERS),
        "has_shorthand_time_token": token_parse["has_shorthand_token"],
        "has_exact_clock_evidence": token_parse["has_exact_clock_token"],
        "all_time_tokens_parsed": token_parse["all_tokens_parsed"],
        "at_least_two_distinct_parsed_minutes": token_parse["distinct_minute_count"] >= 2,
        "token_minute_span_at_or_below_15": token_parse["minute_span"] is not None and token_parse["minute_span"] <= 15,
        "single_source_name": len(string_list(source_summary.get("source_names"))) == 1,
        "single_source_native_id": len(string_list(source_summary.get("source_native_ids"))) == 1,
        "single_date": len(string_list(source_summary.get("date_values"))) == 1,
        "exact_day_date": string_list(source_summary.get("date_precision_values")) in (["exact_day"], []),
        "single_location": len(string_list(source_summary.get("location_values"))) == 1,
        "single_coordinate": len(string_list(source_summary.get("coordinate_values"))) == 1,
        "single_type": len(string_list(source_summary.get("type_values"))) <= 1,
        "single_shape_or_blank": len(string_list(source_summary.get("shape_values"))) <= 1,
        "identical_nonempty_summary_text": len(summary_texts) == 1,
        "no_missing_candidate_input_ids": not packet_item.get("candidate_input_ids_missing_from_evidence"),
        "no_missing_canonical_event_ids": not packet_item.get("missing_canonical_event_ids"),
        "positive_projected_reduction": as_int(item.get("projected_event_reduction")) > 0,
    }
    failed_conditions = [key for key, passed in conditions.items() if not passed]
    same_event = not failed_conditions
    recommendation = SOURCE_REVIEW_SAME_EVENT if same_event else REMAIN_DEFERRED
    confidence = "medium" if same_event else "low"
    reason_codes = (
        [
            "source_review_shorthand_time_only",
            "same_source_native_date_location",
            "identical_summary_text",
            "shorthand_tokens_within_15_minutes",
            "review_only_not_decision",
        ]
        if same_event
        else ["remain_deferred"] + failed_conditions
    )
    return {
        "review_rank": item.get("review_rank"),
        "review_item_id": clean_text(item.get("review_item_id")),
        "cluster_review_id": clean_text(item.get("cluster_review_id")) or clean_text(item.get("review_item_id")),
        "effect_id": clean_text(item.get("effect_id")),
        "review_recommendation": recommendation,
        "confidence": confidence,
        "projected_event_reduction": as_int(item.get("projected_event_reduction")),
        "time_tokens": time_tokens,
        "parsed_token_minutes": token_parse["parsed_minutes"],
        "token_kinds": token_parse["token_kinds"],
        "unparsed_time_tokens": token_parse["unparsed_tokens"],
        "token_minute_span": token_parse["minute_span"],
        "active_conflicts": active_conflicts,
        "blockers": blockers,
        "failed_conditions": failed_conditions,
        "review_reason_codes": reason_codes,
        "source_names": string_list(source_summary.get("source_names")),
        "source_native_ids": string_list(source_summary.get("source_native_ids")),
        "dates": string_list(source_summary.get("date_values")),
        "date_precision_values": string_list(source_summary.get("date_precision_values")),
        "locations": string_list(source_summary.get("location_values")),
        "coordinate_values": string_list(source_summary.get("coordinate_values")),
        "type_values": string_list(source_summary.get("type_values")),
        "shape_values": string_list(source_summary.get("shape_values")),
        "normalized_summary_text_count": len(summary_texts),
        "merge_canonical_event_ids": string_list(item.get("merge_canonical_event_ids")),
        "candidate_canonical_input_ids": string_list(item.get("candidate_canonical_input_ids")),
        "notes": (
            "Source rows appear to be the same event with only shorthand/nearby time notation remaining; still requires explicit decision and apply gates."
            if same_event
            else "Deferred because one or more source-review safety conditions failed."
        ),
    }


def parse_time_tokens(tokens: list[str]) -> dict[str, Any]:
    parsed_minutes: list[int] = []
    token_kinds: dict[str, str] = {}
    unparsed_tokens: list[str] = []
    has_exact = False
    has_shorthand = False
    for token in tokens:
        parsed = parse_time_token(token)
        if parsed is None:
            unparsed_tokens.append(token)
            token_kinds[token] = "unparsed"
            continue
        minute, kind = parsed
        parsed_minutes.append(minute)
        token_kinds[token] = kind
        has_exact = has_exact or kind == "exact_clock"
        has_shorthand = has_shorthand or kind in {"hour_prefix_plus", "bare_hour"}
    distinct_minutes = sorted(set(parsed_minutes))
    minute_span = max(distinct_minutes) - min(distinct_minutes) if len(distinct_minutes) >= 2 else None
    return {
        "parsed_minutes": distinct_minutes,
        "distinct_minute_count": len(distinct_minutes),
        "token_kinds": token_kinds,
        "unparsed_tokens": unparsed_tokens,
        "has_exact_clock_token": has_exact,
        "has_shorthand_token": has_shorthand,
        "all_tokens_parsed": not unparsed_tokens and bool(tokens),
        "minute_span": minute_span,
    }


def parse_time_token(token: str) -> tuple[int, str] | None:
    value = clean_text(token)
    if re.fullmatch(r"\d{3,4}", value):
        hour = int(value[:-2])
        minute = int(value[-2:])
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return hour * 60 + minute, "exact_clock"
        return None
    plus_match = re.fullmatch(r"(\d{1,2})\+", value)
    if plus_match:
        hour = int(plus_match.group(1))
        if 0 <= hour <= 23:
            return hour * 60, "hour_prefix_plus"
        return None
    if re.fullmatch(r"\d{1,2}", value):
        hour = int(value)
        if 0 <= hour <= 23:
            return hour * 60, "bare_hour"
    return None


def normalized_summary_texts(packet_item: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    for row in packet_item.get("evidence_rows") or []:
        if not isinstance(row, dict):
            continue
        text = clean_text(row.get("summary")) or clean_text(row.get("description_excerpt"))
        if text:
            values.add(text.casefold())
    return values


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for item in payload.get("items") or []:
            if isinstance(item, dict):
                writer.writerow(csv_row(item))


def csv_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "review_rank": item.get("review_rank"),
        "review_item_id": item.get("review_item_id"),
        "effect_id": item.get("effect_id"),
        "review_recommendation": item.get("review_recommendation"),
        "confidence": item.get("confidence"),
        "projected_event_reduction": item.get("projected_event_reduction"),
        "time_tokens": "; ".join(string_list(item.get("time_tokens"))),
        "parsed_token_minutes": "; ".join(str(value) for value in int_list(item.get("parsed_token_minutes"))),
        "token_minute_span": item.get("token_minute_span"),
        "active_conflicts": "; ".join(string_list(item.get("active_conflicts"))),
        "blockers": "; ".join(string_list(item.get("blockers"))),
        "review_reason_codes": "; ".join(string_list(item.get("review_reason_codes"))),
        "source_names": "; ".join(string_list(item.get("source_names"))),
        "source_native_ids": "; ".join(string_list(item.get("source_native_ids"))),
        "dates": "; ".join(string_list(item.get("dates"))),
        "locations": "; ".join(string_list(item.get("locations"))),
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    lines = [
        "# Deferred Time-Normalization Shorthand Review",
        "",
        "This report is review-only and does not mutate canonical outputs.",
        "",
        "## Summary",
        "",
        f"- Deferred inputs reviewed: `{summary.get('reviewed_item_count', 0)}`",
        f"- Review recommendation counts: `{json.dumps(summary.get('review_recommendation_counts') or {}, sort_keys=True)}`",
        f"- Projected reduction by recommendation: `{json.dumps(summary.get('projected_event_reduction_by_review_recommendation') or {}, sort_keys=True)}`",
        f"- Canonical outputs mutated: `{str(payload.get('canonical_outputs_mutated')).lower()}`",
        "",
        "## Items",
        "",
    ]
    for item in payload.get("items") or []:
        if not isinstance(item, dict):
            continue
        lines.extend(
            [
                f"### #{item.get('review_rank')} {item.get('review_item_id')}",
                "",
                f"- Review recommendation: `{item.get('review_recommendation')}` confidence `{item.get('confidence')}`",
                f"- Effect ID: `{item.get('effect_id')}`",
                f"- Projected reduction: `{item.get('projected_event_reduction')}`",
                f"- Time tokens: {', '.join(string_list(item.get('time_tokens'))) or 'none'}",
                f"- Parsed token minutes: {', '.join(str(value) for value in int_list(item.get('parsed_token_minutes'))) or 'none'}",
                f"- Token minute span: `{item.get('token_minute_span')}`",
                f"- Active conflicts: {', '.join(string_list(item.get('active_conflicts'))) or 'none'}",
                f"- Failed conditions: {', '.join(string_list(item.get('failed_conditions'))) or 'none'}",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
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


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


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


def as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--recommendations", type=Path, default=DEFAULT_RECOMMENDATIONS)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_deferred_shorthand_review(
        packet=read_json(args.packet),
        recommendations_report=read_json(args.recommendations),
    )
    report["inputs"] = {"packet": str(args.packet), "recommendations": str(args.recommendations)}
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
                "review_policy": report["review_policy"],
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
