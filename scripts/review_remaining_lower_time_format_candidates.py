"""Review remaining lower-risk time-format blockers.

This is a report-only classifier for the source evidence packet built from
remaining lower-risk time-normalization analysis items. It does not create
accepted decisions or apply merges.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


DEFAULT_PACKET = Path("data/reports/entity_resolution_remaining_lower_time_format_source_evidence_packet.json")
DEFAULT_JSON_OUTPUT = Path("data/reports/entity_resolution_remaining_lower_time_format_review.json")
DEFAULT_CSV_OUTPUT = Path("data/reports/entity_resolution_remaining_lower_time_format_review.csv")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/entity_resolution_remaining_lower_time_format_review.md")

INPUT_PACKET_POLICY = "entity_resolution_remaining_lower_time_format_source_row_evidence_review_only"
REVIEW_POLICY = "entity_resolution_remaining_lower_time_format_source_review_only"
SOURCE_REVIEW_SAME_EVENT = "source_review_same_event_candidate"
REMAIN_DEFERRED = "remain_deferred"

CSV_FIELDS = (
    "review_rank",
    "review_item_id",
    "effect_id",
    "review_recommendation",
    "confidence",
    "projected_event_reduction",
    "time_pattern_classification",
    "time_tokens",
    "parsed_minutes",
    "minute_span",
    "fuzzy_labels",
    "active_conflicts",
    "failed_conditions",
    "review_reason_codes",
    "source_names",
    "source_native_ids",
    "dates",
    "locations",
)

FUZZY_CONTEXT_RANGES = {
    "before_dawn": (210, 300),
    "dawn": (300, 360),
    "sunrise": (330, 390),
    "morning": (360, 720),
    "noon": (705, 735),
    "daytime": (360, 1080),
    "afternoon": (720, 1080),
    "sunset": (1050, 1110),
    "dusk": (1080, 1200),
    "evening": (1110, 1290),
    "night": (1260, 1439),
    "midnight": (0, 15),
    "after_midnight": (0, 180),
}


def build_remaining_lower_time_format_review(packet: dict[str, Any]) -> dict[str, Any]:
    validate_packet_safety(packet)
    items = [item for item in packet.get("items") or [] if isinstance(item, dict)]
    reviewed = [review_item(item) for item in items]
    projected_by_recommendation: dict[str, int] = {}
    for item in reviewed:
        key = clean_text(item.get("review_recommendation")) or "unknown"
        projected_by_recommendation[key] = projected_by_recommendation.get(key, 0) + as_int(
            item.get("projected_event_reduction")
        )
    return {
        "schema_version": 1,
        "review_policy": REVIEW_POLICY,
        "input_packet_policy": packet.get("packet_policy"),
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "validated_decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "summary": {
            "input_item_count": len(items),
            "reviewed_item_count": len(reviewed),
            "review_recommendation_counts": count_by(reviewed, "review_recommendation"),
            "confidence_counts": count_by(reviewed, "confidence"),
            "projected_event_reduction_by_review_recommendation": dict(sorted(projected_by_recommendation.items())),
            "failed_condition_counts": count_failed_conditions(reviewed),
        },
        "items": reviewed,
        "notes": [
            "This report is source-review guidance only and does not accept or apply merges.",
            "source_review_same_event_candidate requires time-only conflict, consistent source/date/location/native-id evidence, compatible time context, and no missing evidence.",
            "Rows with rollover tokens, incompatible fuzzy context, source text variance, or non-time conflicts remain deferred.",
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
        raise ValueError("remaining lower time-format source packet is unsafe for review: " + "; ".join(errors))


def review_item(item: dict[str, Any]) -> dict[str, Any]:
    source = item.get("shadow_preview_override_source") if isinstance(item.get("shadow_preview_override_source"), dict) else {}
    source_summary = item.get("source_summary") if isinstance(item.get("source_summary"), dict) else {}
    conflict_summary = item.get("conflict_summary") if isinstance(item.get("conflict_summary"), dict) else {}
    conflict_flags = conflict_summary.get("conflict_flags") if isinstance(conflict_summary.get("conflict_flags"), dict) else {}
    active_conflicts = sorted(name for name, active in conflict_flags.items() if active)
    parsed_summary = parsed_time_summary(source)
    summary_texts = normalized_summary_texts(item)
    classification = clean_text(source.get("time_pattern_classification"))
    minute_span = parsed_summary["minute_span"]
    conditions = {
        "lower_risk_tier": clean_text(source.get("review_risk_tier")) == "lower",
        "supported_time_pattern": classification in {"single_exact_minute", "nearby_exact_minutes_15m_or_less"},
        "time_only_conflict": active_conflicts == ["time"],
        "no_ambiguous_or_unknown_tokens": not string_list(source.get("ambiguous_tokens"))
        and not string_list(source.get("unknown_tokens")),
        "no_rollover_24_hour_token": not parsed_summary["has_rollover_token"],
        "sufficient_distinct_exact_minutes": (
            (classification == "single_exact_minute" and len(parsed_summary["parsed_minutes"]) == 1)
            or (
                classification == "nearby_exact_minutes_15m_or_less"
                and len(parsed_summary["parsed_minutes"]) >= 2
                and 0 < minute_span <= 15
            )
        ),
        "fuzzy_context_compatible": fuzzy_context_compatible(
            parsed_summary["parsed_minutes"],
            string_list(source.get("fuzzy_labels")),
        ),
        "single_source_name": len(string_list(source_summary.get("source_names"))) == 1,
        "single_source_native_id": len(string_list(source_summary.get("source_native_ids"))) == 1,
        "single_date": len(string_list(source_summary.get("date_values"))) == 1,
        "exact_day_date": string_list(source_summary.get("date_precision_values")) in (["exact_day"], []),
        "single_location": len(string_list(source_summary.get("location_values"))) == 1,
        "single_coordinate": len(string_list(source_summary.get("coordinate_values"))) == 1,
        "single_type": len(string_list(source_summary.get("type_values"))) <= 1,
        "single_shape_or_blank": len(string_list(source_summary.get("shape_values"))) <= 1,
        "identical_nonempty_summary_text": len(summary_texts) == 1,
        "no_missing_candidate_input_ids": not item.get("candidate_input_ids_missing_from_evidence"),
        "no_missing_canonical_event_ids": not item.get("missing_canonical_event_ids"),
        "positive_projected_reduction": as_int(item.get("projected_event_reduction")) > 0,
    }
    failed_conditions = [key for key, passed in conditions.items() if not passed]
    same_event = not failed_conditions
    recommendation = SOURCE_REVIEW_SAME_EVENT if same_event else REMAIN_DEFERRED
    confidence = "medium" if same_event else "low"
    reason_codes = (
        [
            "remaining_lower_time_format_consistent_source_evidence",
            "time_only_conflict",
            "compatible_time_context",
            "same_source_native_date_location",
            "identical_summary_text",
            "review_only_not_decision",
        ]
        if same_event
        else ["remain_deferred"] + failed_conditions
    )
    return {
        "review_rank": item.get("review_rank"),
        "review_item_id": clean_text(item.get("review_item_id")),
        "cluster_review_id": clean_text(item.get("review_item_id")),
        "effect_id": clean_text(item.get("effect_id")),
        "review_recommendation": recommendation,
        "confidence": confidence,
        "projected_event_reduction": as_int(item.get("projected_event_reduction")),
        "time_pattern_classification": classification,
        "time_tokens": string_list(source.get("time_tokens")) or string_list(source_summary.get("time_values")),
        "parsed_minutes": parsed_summary["parsed_minutes"],
        "minute_span": minute_span,
        "fuzzy_labels": string_list(source.get("fuzzy_labels")),
        "active_conflicts": active_conflicts,
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
            "Source rows appear consistent enough for a future explicit same-event decision gate; no decision is created here."
            if same_event
            else "Deferred because one or more source-review safety conditions failed."
        ),
    }


def parsed_time_summary(source: dict[str, Any]) -> dict[str, Any]:
    parsed_tokens = [token for token in source.get("parsed_tokens") or [] if isinstance(token, dict)]
    parsed_minutes = sorted(
        {
            as_int(token.get("minute"))
            for token in parsed_tokens
            if clean_text(token.get("kind")) == "exact" and token.get("minute") is not None
        }
    )
    minute_span = parsed_minutes[-1] - parsed_minutes[0] if len(parsed_minutes) >= 2 else 0
    return {
        "parsed_minutes": parsed_minutes,
        "minute_span": minute_span,
        "has_rollover_token": any(clean_text(token.get("note")) == "rollover_24_hour_token" for token in parsed_tokens),
    }


def fuzzy_context_compatible(parsed_minutes: list[int], fuzzy_labels: list[str]) -> bool:
    if not fuzzy_labels:
        return True
    if not parsed_minutes:
        return False
    for label in fuzzy_labels:
        bounds = FUZZY_CONTEXT_RANGES.get(clean_text(label).casefold())
        if not bounds:
            return False
        start, end = bounds
        if not any(start <= minute <= end for minute in parsed_minutes):
            return False
    return True


def normalized_summary_texts(item: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    for row in item.get("evidence_rows") or []:
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
        "time_pattern_classification": item.get("time_pattern_classification"),
        "time_tokens": "; ".join(string_list(item.get("time_tokens"))),
        "parsed_minutes": "; ".join(str(value) for value in int_list(item.get("parsed_minutes"))),
        "minute_span": item.get("minute_span"),
        "fuzzy_labels": "; ".join(string_list(item.get("fuzzy_labels"))),
        "active_conflicts": "; ".join(string_list(item.get("active_conflicts"))),
        "failed_conditions": "; ".join(string_list(item.get("failed_conditions"))),
        "review_reason_codes": "; ".join(string_list(item.get("review_reason_codes"))),
        "source_names": "; ".join(string_list(item.get("source_names"))),
        "source_native_ids": "; ".join(string_list(item.get("source_native_ids"))),
        "dates": "; ".join(string_list(item.get("dates"))),
        "locations": "; ".join(string_list(item.get("locations"))),
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    lines = [
        "# Remaining Lower Time-Format Source Review",
        "",
        "This report is review-only and does not mutate canonical outputs.",
        "",
        "## Summary",
        "",
        f"- Input items: `{summary.get('input_item_count', 0)}`",
        f"- Recommendation counts: `{json.dumps(summary.get('review_recommendation_counts', {}), sort_keys=True)}`",
        f"- Confidence counts: `{json.dumps(summary.get('confidence_counts', {}), sort_keys=True)}`",
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
                f"- Recommendation: `{item.get('review_recommendation')}` confidence `{item.get('confidence')}`",
                f"- Pattern: `{item.get('time_pattern_classification')}`",
                f"- Time tokens: {', '.join(string_list(item.get('time_tokens'))) or 'none'}",
                f"- Parsed minutes: {', '.join(str(value) for value in int_list(item.get('parsed_minutes'))) or 'none'}",
                f"- Fuzzy labels: {', '.join(string_list(item.get('fuzzy_labels'))) or 'none'}",
                f"- Failed conditions: {', '.join(string_list(item.get('failed_conditions'))) or 'none'}",
                f"- Source/native IDs: {', '.join(string_list(item.get('source_native_ids'))) or 'none'}",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = clean_text(item.get(key)) or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def count_failed_conditions(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        for condition in string_list(item.get("failed_conditions")):
            counts[condition] = counts.get(condition, 0) + 1
    return dict(sorted(counts.items()))


def as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def int_list(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    result: list[int] = []
    for item in value:
        try:
            result.append(int(item))
        except (TypeError, ValueError):
            continue
    return result


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [text for item in value if (text := clean_text(item))]
    text = clean_text(value)
    return [text] if text else []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_remaining_lower_time_format_review(read_json(args.packet))
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
