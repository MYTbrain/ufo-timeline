"""Analyze time-token patterns in the cluster blocker priority queue.

This is review-only. It does not create merge decisions or override subsets;
it narrows the remaining time-format review work into safer review buckets.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_PRIORITY_QUEUE = Path("data/reports/entity_resolution_cluster_blocker_priority_queue.json")
DEFAULT_JSON_OUTPUT = Path("data/reports/entity_resolution_cluster_time_normalization_analysis.json")
DEFAULT_CSV_OUTPUT = Path("data/reports/entity_resolution_cluster_time_normalization_analysis.csv")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/entity_resolution_cluster_time_normalization_analysis.md")

ANALYSIS_POLICY = "entity_resolution_cluster_time_normalization_review_only"

CSV_FIELDS = (
    "review_rank",
    "time_pattern_classification",
    "review_risk_tier",
    "review_item_id",
    "effect_id",
    "projected_event_reduction",
    "blocking_fields",
    "time_tokens",
    "parsed_minutes",
    "fuzzy_labels",
    "ambiguous_tokens",
    "unknown_tokens",
    "canonical_event_id_count",
    "canonical_event_ids",
    "location_values",
    "recommended_review_step",
)

FUZZY_TIME_BUCKETS: dict[str, tuple[str, int | None]] = {
    "before dawn": ("before_dawn", 255),
    "predawn": ("before_dawn", 255),
    "pdawn": ("before_dawn", 255),
    "dawn": ("dawn", 330),
    "sunrise": ("sunrise", 360),
    "morning": ("morning", 570),
    "noon": ("noon", 720),
    "day": ("daytime", None),
    "afternoon": ("afternoon", 900),
    "sunset": ("sunset", 1080),
    "dusk": ("dusk", 1140),
    "even": ("evening", 1200),
    "eve": ("evening", 1200),
    "evening": ("evening", 1200),
    "night": ("night", 1350),
    "midnight": ("midnight", 0),
    "after midnight": ("after_midnight", 90),
}


def analyze_entity_resolution_cluster_time_normalization(
    *,
    priority_queue: dict[str, Any],
    priority_queue_path: Path | None = None,
) -> dict[str, Any]:
    validate_priority_queue_safety(priority_queue)
    items = []
    for queue_item in priority_queue.get("items") or []:
        if not isinstance(queue_item, dict):
            continue
        if clean_text(queue_item.get("triage_bucket")) != "time_format_review":
            continue
        items.append(analyze_queue_item(queue_item))
    items.sort(key=time_review_sort_key)
    for index, item in enumerate(items, start=1):
        item["review_rank"] = index
    return {
        "schema_version": 1,
        "analysis_policy": ANALYSIS_POLICY,
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "auto_merge_performed": False,
        "override_decisions_created": False,
        "ready_for_canonical_apply": False,
        "inputs": {
            "priority_queue": str(priority_queue_path) if priority_queue_path else None,
        },
        "summary": {
            "analyzed_item_count": len(items),
            "classification_counts": count_by(items, "time_pattern_classification"),
            "review_risk_tier_counts": count_by(items, "review_risk_tier"),
            "projected_reduction_sum_not_deduped": sum(
                int(item.get("projected_event_reduction") or 0) for item in items
            ),
        },
        "items": items,
        "notes": [
            "This analysis is review-only; it does not promote time blockers to merge decisions.",
            "Ambiguous one- or two-digit times are flagged instead of being treated as exact evidence.",
            "Projected reduction sums are not deduped across overlapping effects.",
        ],
    }


def analyze_queue_item(queue_item: dict[str, Any]) -> dict[str, Any]:
    tokens = time_tokens(queue_item)
    parsed_tokens = [parse_time_token(token) for token in tokens]
    exact_minutes = sorted({token["minute"] for token in parsed_tokens if token["kind"] == "exact" and token["minute"] is not None})
    fuzzy_labels = sorted({token["bucket_label"] for token in parsed_tokens if token["kind"] == "fuzzy" and token["bucket_label"]})
    ambiguous_tokens = [token["raw"] for token in parsed_tokens if token["kind"] == "ambiguous"]
    unknown_tokens = [token["raw"] for token in parsed_tokens if token["kind"] == "unknown"]
    classification = classify_time_pattern(
        exact_minutes=exact_minutes,
        fuzzy_labels=fuzzy_labels,
        ambiguous_tokens=ambiguous_tokens,
        unknown_tokens=unknown_tokens,
    )
    source_summary = queue_item.get("source_summary") if isinstance(queue_item.get("source_summary"), dict) else {}
    return {
        "review_rank": None,
        "time_pattern_classification": classification,
        "review_risk_tier": time_pattern_risk_tier(classification),
        "recommended_review_step": recommended_review_step(classification),
        "review_item_id": clean_text(queue_item.get("review_item_id")),
        "effect_id": clean_text(queue_item.get("effect_id")),
        "patch_id": clean_text(queue_item.get("patch_id")),
        "projected_event_reduction": as_int(queue_item.get("projected_event_reduction")) or 0,
        "blocking_fields": string_list(queue_item.get("blocking_fields")),
        "time_tokens": tokens,
        "parsed_tokens": parsed_tokens,
        "parsed_minutes": exact_minutes,
        "fuzzy_labels": fuzzy_labels,
        "ambiguous_tokens": ambiguous_tokens,
        "unknown_tokens": unknown_tokens,
        "source_summary": {
            "canonical_event_ids": string_list(source_summary.get("canonical_event_ids")),
            "canonical_input_ids": string_list(source_summary.get("canonical_input_ids")),
            "canonical_event_count": as_int(source_summary.get("canonical_event_count"))
            or len(string_list(source_summary.get("canonical_event_ids"))),
            "source_names": string_list(source_summary.get("source_names")),
            "source_native_ids": string_list(source_summary.get("source_native_ids")),
            "date_values": string_list(source_summary.get("date_values")),
            "location_values": string_list(source_summary.get("location_values")),
            "type_values": string_list(source_summary.get("type_values")),
        },
    }


def time_tokens(queue_item: dict[str, Any]) -> list[str]:
    conflicts = queue_item.get("field_conflict_values") if isinstance(queue_item.get("field_conflict_values"), dict) else {}
    source_summary = queue_item.get("source_summary") if isinstance(queue_item.get("source_summary"), dict) else {}
    values = string_list(conflicts.get("time_raw")) or string_list(source_summary.get("time_values"))
    return sorted(set(values), key=lambda value: (canonical_time_text(value), value))


def parse_time_token(raw: str) -> dict[str, Any]:
    text = canonical_time_text(raw)
    if not text:
        return parsed_token(raw, "unknown")
    fuzzy_match = FUZZY_TIME_BUCKETS.get(text)
    if fuzzy_match:
        label, minute = fuzzy_match
        return parsed_token(raw, "fuzzy", minute=minute, bucket_label=label)
    if text in {"after", "before", "approx", "unknown", "unk", "?"}:
        return parsed_token(raw, "unknown")
    suffix_approx = text.endswith("+") or text.endswith("?")
    trimmed = text.rstrip("+?")
    colon_match = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", trimmed)
    if colon_match:
        return parsed_token(
            raw,
            "exact",
            minute=int(colon_match.group(1)) * 60 + int(colon_match.group(2)),
            approximate=suffix_approx,
        )
    compact_match = re.fullmatch(r"([01]\d|2[0-3])([0-5]\d)", trimmed)
    if compact_match:
        return parsed_token(
            raw,
            "exact",
            minute=int(compact_match.group(1)) * 60 + int(compact_match.group(2)),
            approximate=suffix_approx,
        )
    if trimmed == "2400" or trimmed == "24":
        return parsed_token(raw, "exact", minute=0, approximate=True, note="rollover_24_hour_token")
    hour_match = re.fullmatch(r"\d{1,2}", trimmed)
    if hour_match:
        hour = int(trimmed)
        if hour == 0:
            return parsed_token(raw, "exact", minute=0, approximate=suffix_approx)
        if 13 <= hour <= 23:
            return parsed_token(raw, "exact", minute=hour * 60, approximate=suffix_approx)
        return parsed_token(raw, "ambiguous", note="one_or_two_digit_hour_without_meridiem")
    am_pm_match = re.fullmatch(r"([1-9]|1[0-2])(?::([0-5]\d))?\s*([ap])m?", text)
    if am_pm_match:
        hour = int(am_pm_match.group(1))
        minute = int(am_pm_match.group(2) or 0)
        marker = am_pm_match.group(3)
        if marker == "a":
            hour = 0 if hour == 12 else hour
        else:
            hour = 12 if hour == 12 else hour + 12
        return parsed_token(raw, "exact", minute=hour * 60 + minute)
    return parsed_token(raw, "unknown")


def parsed_token(
    raw: str,
    kind: str,
    *,
    minute: int | None = None,
    bucket_label: str | None = None,
    approximate: bool = False,
    note: str | None = None,
) -> dict[str, Any]:
    return {
        "raw": raw,
        "kind": kind,
        "minute": minute,
        "bucket_label": bucket_label,
        "approximate": approximate,
        "note": note,
    }


def classify_time_pattern(
    *,
    exact_minutes: list[int],
    fuzzy_labels: list[str],
    ambiguous_tokens: list[str],
    unknown_tokens: list[str],
) -> str:
    span = exact_minutes[-1] - exact_minutes[0] if len(exact_minutes) >= 2 else 0
    has_context_tokens = bool(fuzzy_labels or ambiguous_tokens or unknown_tokens)
    if len(exact_minutes) == 1 and not has_context_tokens:
        return "single_exact_minute"
    if len(exact_minutes) == 1 and has_context_tokens:
        return "single_exact_minute_with_context_tokens"
    if len(exact_minutes) > 1 and span <= 15:
        return "nearby_exact_minutes_15m_or_less"
    if len(exact_minutes) > 1 and span <= 60:
        return "nearby_exact_minutes_60m_or_less"
    if len(exact_minutes) > 1:
        return "multiple_distinct_exact_minutes"
    if fuzzy_labels and not ambiguous_tokens and not unknown_tokens:
        return "fuzzy_bucket_only"
    if fuzzy_labels or ambiguous_tokens:
        return "fuzzy_or_ambiguous_only"
    return "unknown_time_tokens_only"


def time_pattern_risk_tier(classification: str) -> str:
    if classification in {"single_exact_minute", "nearby_exact_minutes_15m_or_less"}:
        return "lower"
    if classification in {
        "single_exact_minute_with_context_tokens",
        "nearby_exact_minutes_60m_or_less",
        "fuzzy_bucket_only",
        "fuzzy_or_ambiguous_only",
    }:
        return "medium"
    return "high"


def recommended_review_step(classification: str) -> str:
    if classification == "single_exact_minute":
        return "Check source identity; this is the strongest time-normalization review case but still not auto-approved."
    if classification == "single_exact_minute_with_context_tokens":
        return "Check whether context tokens are non-time descriptors or broad time words attached to one exact time."
    if classification == "nearby_exact_minutes_15m_or_less":
        return "Review as possible rounded-time duplicates; preserve if source implies separate observations."
    if classification == "nearby_exact_minutes_60m_or_less":
        return "Review manually; close times may be duplicates or sequential observations."
    if classification == "multiple_distinct_exact_minutes":
        return "Treat as high-risk; likely separate same-day observations unless source evidence says otherwise."
    if classification == "fuzzy_bucket_only":
        return "Review broad time bucket language; do not create precise chronology or merge confidence from this alone."
    if classification == "fuzzy_or_ambiguous_only":
        return "Resolve ambiguous tokens before considering any override; do not infer exact time."
    return "Defer unless source text provides additional identity evidence."


def time_review_sort_key(item: dict[str, Any]) -> tuple[int, int, str]:
    risk_order = {"lower": 10, "medium": 20, "high": 30}
    return (
        risk_order.get(clean_text(item.get("review_risk_tier")), 90),
        -int(item.get("projected_event_reduction") or 0),
        str(item.get("review_item_id") or ""),
    )


def validate_priority_queue_safety(queue: dict[str, Any]) -> None:
    errors: list[str] = []
    if queue.get("queue_policy") != "entity_resolution_cluster_blocker_priority_queue_review_only":
        errors.append("priority queue policy must be 'entity_resolution_cluster_blocker_priority_queue_review_only'")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "decisions_created", "auto_merge_performed"):
        if queue.get(flag) is not False:
            errors.append(f"priority queue {flag} must be false")
    if errors:
        raise ValueError(f"input is not safe for time-normalization analysis: {'; '.join(errors)}")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for item in items:
            writer.writerow(csv_row(item))


def csv_row(item: dict[str, Any]) -> dict[str, Any]:
    source_summary = item.get("source_summary") if isinstance(item.get("source_summary"), dict) else {}
    return {
        "review_rank": item.get("review_rank"),
        "time_pattern_classification": item.get("time_pattern_classification"),
        "review_risk_tier": item.get("review_risk_tier"),
        "review_item_id": item.get("review_item_id"),
        "effect_id": item.get("effect_id"),
        "projected_event_reduction": item.get("projected_event_reduction"),
        "blocking_fields": "; ".join(string_list(item.get("blocking_fields"))),
        "time_tokens": "; ".join(string_list(item.get("time_tokens"))),
        "parsed_minutes": "; ".join(str(value) for value in item.get("parsed_minutes") or []),
        "fuzzy_labels": "; ".join(string_list(item.get("fuzzy_labels"))),
        "ambiguous_tokens": "; ".join(string_list(item.get("ambiguous_tokens"))),
        "unknown_tokens": "; ".join(string_list(item.get("unknown_tokens"))),
        "canonical_event_id_count": source_summary.get("canonical_event_count") or 0,
        "canonical_event_ids": "; ".join(string_list(source_summary.get("canonical_event_ids"))[:20]),
        "location_values": "; ".join(string_list(source_summary.get("location_values"))),
        "recommended_review_step": item.get("recommended_review_step"),
    }


def write_markdown(path: Path, analysis: dict[str, Any], *, item_limit: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = analysis.get("summary") if isinstance(analysis.get("summary"), dict) else {}
    lines = [
        "# Cluster Time-Normalization Analysis",
        "",
        "This analysis is review-only. It classifies time-token patterns but does not create merge decisions.",
        "",
        "## Summary",
        "",
        f"- Analyzed items: {summary.get('analyzed_item_count', 0)}",
        f"- Classification counts: `{json.dumps(summary.get('classification_counts', {}), sort_keys=True)}`",
        f"- Risk tier counts: `{json.dumps(summary.get('review_risk_tier_counts', {}), sort_keys=True)}`",
        f"- Canonical outputs mutated: `{str(analysis.get('canonical_outputs_mutated')).lower()}`",
        "",
        "## Top Review Items",
        "",
    ]
    for item in (analysis.get("items") or [])[: max(0, item_limit)]:
        if not isinstance(item, dict):
            continue
        lines.extend(markdown_item_lines(item))
    if len(analysis.get("items") or []) > item_limit:
        lines.extend(["", f"_Markdown limited to {item_limit} of {len(analysis.get('items') or [])} analyzed items._", ""])
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def markdown_item_lines(item: dict[str, Any]) -> list[str]:
    source_summary = item.get("source_summary") if isinstance(item.get("source_summary"), dict) else {}
    return [
        f"### #{item.get('review_rank')} {item.get('review_item_id')}",
        "",
        f"- Pattern: `{item.get('time_pattern_classification')}` risk `{item.get('review_risk_tier')}`",
        f"- Projected reduction: `{item.get('projected_event_reduction')}`",
        f"- Blocking fields: {', '.join(string_list(item.get('blocking_fields'))) or 'none'}",
        f"- Time tokens: {', '.join(string_list(item.get('time_tokens'))) or 'none'}",
        f"- Parsed minutes: {', '.join(str(value) for value in item.get('parsed_minutes') or []) or 'none'}",
        f"- Fuzzy labels: {', '.join(string_list(item.get('fuzzy_labels'))) or 'none'}",
        f"- Ambiguous tokens: {', '.join(string_list(item.get('ambiguous_tokens'))) or 'none'}",
        f"- Unknown tokens: {', '.join(string_list(item.get('unknown_tokens'))) or 'none'}",
        f"- Canonical event IDs: `{source_summary.get('canonical_event_count') or 0}`",
        f"- Locations: {', '.join(string_list(source_summary.get('location_values'))) or 'none'}",
        f"- Recommended review step: {item.get('recommended_review_step') or 'none'}",
        "",
    ]


def canonical_time_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [text for item in value if (text := clean_text(item))]
    text = clean_text(value)
    return [text] if text else []


def as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def count_by(items: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = clean_text(item.get(field)) or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--priority-queue", type=Path, default=DEFAULT_PRIORITY_QUEUE)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument("--markdown-item-limit", type=int, default=120)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    priority_queue = read_json(args.priority_queue)
    analysis = analyze_entity_resolution_cluster_time_normalization(
        priority_queue=priority_queue,
        priority_queue_path=args.priority_queue,
    )
    write_json(args.json_output, analysis)
    write_csv(args.csv_output, analysis["items"])
    write_markdown(args.markdown_output, analysis, item_limit=args.markdown_item_limit)
    print(
        json.dumps(
            {
                "json_output": str(args.json_output),
                "csv_output": str(args.csv_output),
                "markdown_output": str(args.markdown_output),
                "analyzed_item_count": analysis["summary"]["analyzed_item_count"],
                "classification_counts": analysis["summary"]["classification_counts"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
