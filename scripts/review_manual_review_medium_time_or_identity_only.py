"""Review medium-risk manual-review components with source identity conflicts.

This report targets the ``medium_time_or_identity_only`` audit sublane:
components whose only medium-risk flags are ``same_source_multiple_native_ids``
and optionally ``time_raw_conflict``. Unlike the time-only lane, these rows are
not safe to promote automatically because multiple native IDs from the same
source can represent truly distinct reports. This script is therefore
review-only and never writes accepted decisions or candidate corpora.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable

from scripts.analyze_entity_resolution_cluster_time_normalization import parse_time_token


DEFAULT_AUDIT_CSV = Path("data/reports/manual_review_ai_after_time_norm_replacement_audit.csv")
DEFAULT_SOURCE_EVENTS = Path(
    "data/canonical_time_norm_recommended_plus_shorthand_plus_likely_plus_single_exact_context/deduped_events.jsonl"
)
DEFAULT_JSON_OUTPUT = Path(
    "data/reports/manual_review_ai_after_time_norm_medium_time_or_identity_only_review.json"
)
DEFAULT_CSV_OUTPUT = Path(
    "data/reports/manual_review_ai_after_time_norm_medium_time_or_identity_only_review.csv"
)
DEFAULT_MARKDOWN_OUTPUT = Path(
    "data/reports/manual_review_ai_after_time_norm_medium_time_or_identity_only_review.md"
)

REVIEW_POLICY = "manual_review_medium_time_or_identity_only_review_v1"
MANUAL_IDENTITY_REVIEW_CANDIDATE = "manual_identity_review_candidate"
NEEDS_DEEPER_IDENTITY_REVIEW = "needs_deeper_identity_review"
MAX_EXACT_SPAN_MINUTES = 15

CSV_FIELDS = (
    "review_rank",
    "replacement_event_id",
    "review_recommendation",
    "identity_subcategory",
    "confidence",
    "projected_event_reduction",
    "exact_span_minutes",
    "risk_flags",
    "time_raw_values",
    "source_file_values",
    "native_id_profile",
    "failed_conditions",
    "component_event_count",
    "component_event_ids",
)


def build_medium_time_or_identity_only_review(
    *,
    audit_csv_path: Path,
    source_events_path: Path,
    max_exact_span_minutes: int = MAX_EXACT_SPAN_MINUTES,
) -> dict[str, Any]:
    audit_rows = read_csv(audit_csv_path)
    target_rows = [row for row in audit_rows if is_medium_time_or_identity_only(row)]
    required_ids = {
        event_id
        for row in target_rows
        for event_id in split_pipe(row.get("component_event_ids"))
    }
    source_rows = scan_source_component_rows(source_events_path, required_ids)
    items = [
        review_row(
            row,
            component_rows=[source_rows[event_id] for event_id in split_pipe(row.get("component_event_ids")) if event_id in source_rows],
            max_exact_span_minutes=max_exact_span_minutes,
        )
        for row in target_rows
    ]
    items.sort(key=review_sort_key)
    for index, item in enumerate(items, start=1):
        item["review_rank"] = index

    projected_by_recommendation: dict[str, int] = {}
    for item in items:
        recommendation = item["review_recommendation"]
        projected_by_recommendation[recommendation] = projected_by_recommendation.get(recommendation, 0) + int(
            item["projected_event_reduction"]
        )

    missing_source_ids = sorted(required_ids - set(source_rows))
    return {
        "schema_version": 1,
        "review_policy": REVIEW_POLICY,
        "canonical_outputs_mutated": False,
        "source_canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_runtime_promotion": False,
        "human_review_required_before_promotion": True,
        "inputs": {
            "audit_csv": str(audit_csv_path),
            "source_events": str(source_events_path),
            "max_exact_span_minutes": max_exact_span_minutes,
        },
        "summary": {
            "audit_rows_read": len(audit_rows),
            "target_medium_time_or_identity_only_count": len(target_rows),
            "reviewed_item_count": len(items),
            "source_component_ids_expected": len(required_ids),
            "source_component_rows_found": len(source_rows),
            "missing_source_component_id_count": len(missing_source_ids),
            "review_recommendation_counts": count_by(items, "review_recommendation"),
            "identity_subcategory_counts": count_by(items, "identity_subcategory"),
            "confidence_counts": count_by(items, "confidence"),
            "projected_event_reduction_by_review_recommendation": dict(
                sorted(projected_by_recommendation.items())
            ),
            "failed_condition_counts": count_failed_conditions(items),
        },
        "items": items,
        "missing_source_component_ids": missing_source_ids[:100],
        "notes": [
            "This report is review-only; it does not create accepted decisions, apply merges, or mutate canonical outputs.",
            "Every targeted component includes same_source_multiple_native_ids, so same-source identity evidence must be reviewed before any promotion.",
            "Nearby exact time conflicts are surfaced as manual_identity_review_candidate only; they are not accepted automatically.",
        ],
    }


def is_medium_time_or_identity_only(row: dict[str, str]) -> bool:
    flags = set(split_pipe(row.get("risk_flags")))
    return (
        clean_text(row.get("risk_level")) == "medium"
        and "same_source_multiple_native_ids" in flags
        and flags <= {"same_source_multiple_native_ids", "time_raw_conflict"}
    )


def review_row(
    row: dict[str, str],
    *,
    component_rows: list[dict[str, Any]],
    max_exact_span_minutes: int,
) -> dict[str, Any]:
    flags = set(split_pipe(row.get("risk_flags")))
    time_values = split_pipe(row.get("time_raw_values"))
    parsed_tokens = [parse_time_token(value) for value in time_values]
    exact_minutes = sorted(
        {
            int(token["minute"])
            for token in parsed_tokens
            if token.get("kind") == "exact" and token.get("minute") is not None
        }
    )
    exact_span = exact_minutes[-1] - exact_minutes[0] if len(exact_minutes) >= 2 else 0
    non_exact_tokens = [token for token in parsed_tokens if token.get("kind") != "exact"]
    approximate_tokens = [token for token in parsed_tokens if token.get("approximate")]
    has_time_conflict = "time_raw_conflict" in flags
    has_body_variance = safe_int(row.get("description_variant_count")) > 1 or safe_int(row.get("summary_variant_count")) > 1
    native_profile = build_native_id_profile(component_rows)

    if not has_time_conflict:
        subcategory = "identity_only_no_time_conflict"
    elif not non_exact_tokens and not approximate_tokens and len(exact_minutes) >= 2 and exact_span <= max_exact_span_minutes:
        subcategory = "identity_plus_nearby_exact_time"
    elif not non_exact_tokens and len(exact_minutes) >= 2:
        subcategory = "identity_plus_wide_exact_time"
    else:
        subcategory = "identity_plus_fuzzy_or_unknown_time"

    candidate_conditions = {
        "audit_medium_time_or_identity_only": is_medium_time_or_identity_only(row),
        "source_rows_available": len(component_rows) == len(split_pipe(row.get("component_event_ids"))),
        "same_source_multiple_native_ids": has_same_source_multiple_native_ids(native_profile),
        "no_body_text_variance": not has_body_variance,
        "identity_conflict_only_or_nearby_exact_time": subcategory
        in {"identity_only_no_time_conflict", "identity_plus_nearby_exact_time"},
    }
    failed_conditions = [key for key, passed in candidate_conditions.items() if not passed]
    review_candidate = not failed_conditions

    return {
        "review_rank": None,
        "replacement_event_id": clean_text(row.get("replacement_event_id")),
        "review_recommendation": (
            MANUAL_IDENTITY_REVIEW_CANDIDATE if review_candidate else NEEDS_DEEPER_IDENTITY_REVIEW
        ),
        "identity_subcategory": subcategory,
        "confidence": "low",
        "projected_event_reduction": projected_event_reduction(row),
        "risk_flags": sorted(flags),
        "exact_span_minutes": exact_span if len(exact_minutes) >= 2 else None,
        "time_raw_values": time_values,
        "parsed_tokens": parsed_tokens,
        "parsed_minutes": exact_minutes,
        "non_exact_tokens": [token["raw"] for token in non_exact_tokens],
        "approximate_tokens": [token["raw"] for token in approximate_tokens],
        "has_body_variance": has_body_variance,
        "native_id_profile": native_profile,
        "failed_conditions": failed_conditions,
        "review_reason_codes": (
            [
                "same_source_multiple_native_ids_present",
                subcategory,
                "manual_identity_review_required",
                "review_only_not_decision",
            ]
            if review_candidate
            else ["needs_deeper_identity_review", subcategory] + failed_conditions
        ),
        "component_event_count": safe_int(row.get("component_event_count")),
        "canonical_input_id_count": safe_int(row.get("canonical_input_id_count")),
        "coordinate_span_km": safe_float(row.get("coordinate_span_km")),
        "date_iso_values": split_pipe(row.get("date_iso_values")),
        "location_raw_values": split_pipe(row.get("location_raw_values")),
        "source_file_values": split_pipe(row.get("source_file_values")),
        "component_event_ids": split_pipe(row.get("component_event_ids")),
    }


def build_native_id_profile(component_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_source: dict[str, dict[str, Any]] = {}
    for row in component_rows:
        source = clean_text(row.get("source_file")) or clean_text(row.get("source")) or "unknown"
        native_id = clean_text(row.get("source_native_id")) or clean_text(row.get("record_id")) or "unknown"
        entry = by_source.setdefault(source, {"source_file": source, "native_ids": set(), "event_ids": []})
        entry["native_ids"].add(native_id)
        entry["event_ids"].append(event_id_for(row))
    profile = []
    for source, entry in sorted(by_source.items()):
        native_ids = sorted(entry["native_ids"])
        profile.append(
            {
                "source_file": source,
                "native_id_count": len(native_ids),
                "native_ids": native_ids[:20],
                "component_event_ids": sorted(entry["event_ids"])[:20],
            }
        )
    return profile


def has_same_source_multiple_native_ids(native_profile: list[dict[str, Any]]) -> bool:
    return any(int(entry.get("native_id_count") or 0) > 1 for entry in native_profile)


def projected_event_reduction(row: dict[str, str]) -> int:
    return max(0, safe_int(row.get("component_event_count")) - 1)


def review_sort_key(item: dict[str, Any]) -> tuple[int, int, int, str]:
    return (
        0 if item["review_recommendation"] == MANUAL_IDENTITY_REVIEW_CANDIDATE else 1,
        subcategory_rank(item["identity_subcategory"]),
        -int(item["projected_event_reduction"]),
        item["replacement_event_id"],
    )


def subcategory_rank(value: str) -> int:
    return {
        "identity_only_no_time_conflict": 0,
        "identity_plus_nearby_exact_time": 1,
        "identity_plus_wide_exact_time": 2,
        "identity_plus_fuzzy_or_unknown_time": 3,
    }.get(value, 9)


def count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = clean_text(item.get(key)) or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def count_failed_conditions(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        for condition in item.get("failed_conditions") or []:
            condition = clean_text(condition)
            counts[condition] = counts.get(condition, 0) + 1
    return dict(sorted(counts.items()))


def render_markdown(report: dict[str, Any], *, limit: int = 100) -> str:
    items = [item for item in report.get("items") or [] if isinstance(item, dict)]
    lines = [
        "# Medium Time-Or-Identity Review",
        "",
        "This report is review-only. It does not accept decisions or mutate canonical outputs.",
        "",
        "## Summary",
        "",
        f"- Target items: {report['summary']['target_medium_time_or_identity_only_count']}",
        f"- Recommendations: {json.dumps(report['summary']['review_recommendation_counts'], sort_keys=True)}",
        f"- Subcategories: {json.dumps(report['summary']['identity_subcategory_counts'], sort_keys=True)}",
        f"- Projected reduction by recommendation: {json.dumps(report['summary']['projected_event_reduction_by_review_recommendation'], sort_keys=True)}",
        "",
        "## Top Items",
        "",
        "| Recommendation | Subcategory | Replacement | Reduction | Sources / Native IDs | Failed Conditions |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for item in items[:limit]:
        lines.append(
            "| "
            + " | ".join(
                [
                    escape_md(clean_text(item.get("review_recommendation"))),
                    escape_md(clean_text(item.get("identity_subcategory"))),
                    f"`{escape_md(clean_text(item.get('replacement_event_id')))}`",
                    str(item.get("projected_event_reduction")),
                    escape_md(format_native_profile(item.get("native_id_profile") or [])),
                    escape_md(", ".join(item.get("failed_conditions") or [])),
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def write_csv(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for item in report.get("items") or []:
            if not isinstance(item, dict):
                continue
            writer.writerow(
                {
                    "review_rank": item.get("review_rank"),
                    "replacement_event_id": item.get("replacement_event_id"),
                    "review_recommendation": item.get("review_recommendation"),
                    "identity_subcategory": item.get("identity_subcategory"),
                    "confidence": item.get("confidence"),
                    "projected_event_reduction": item.get("projected_event_reduction"),
                    "exact_span_minutes": item.get("exact_span_minutes"),
                    "risk_flags": "|".join(item.get("risk_flags") or []),
                    "time_raw_values": "|".join(item.get("time_raw_values") or []),
                    "source_file_values": "|".join(item.get("source_file_values") or []),
                    "native_id_profile": format_native_profile(item.get("native_id_profile") or []),
                    "failed_conditions": "|".join(item.get("failed_conditions") or []),
                    "component_event_count": item.get("component_event_count"),
                    "component_event_ids": "|".join(item.get("component_event_ids") or []),
                }
            )


def format_native_profile(profile: list[dict[str, Any]]) -> str:
    parts = []
    for entry in profile:
        source = clean_text(entry.get("source_file")) or "unknown"
        native_ids = [clean_text(value) for value in entry.get("native_ids") or [] if clean_text(value)]
        parts.append(f"{source}:{','.join(native_ids)}")
    return "; ".join(parts)


def scan_source_component_rows(path: Path, required_ids: set[str]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    if not required_ids:
        return rows
    for event in iter_jsonl(path):
        event_id = event_id_for(event)
        if event_id in required_ids:
            rows[event_id] = event
            if len(rows) == len(required_ids):
                break
    return rows


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{path} line {line_number} must be a JSON object.")
            yield payload


def event_id_for(event: dict[str, Any]) -> str:
    return clean_text(event.get("canonical_event_id")) or clean_text(event.get("event_id"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def split_pipe(value: Any) -> list[str]:
    return [item for item in (clean_text(part) for part in str(value or "").split("|")) if item]


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def safe_int(value: Any) -> int:
    try:
        return int(float(clean_text(value) or "0"))
    except ValueError:
        return 0


def safe_float(value: Any) -> float:
    try:
        return float(clean_text(value) or "0")
    except ValueError:
        return 0.0


def escape_md(value: str) -> str:
    return value.replace("|", "\\|")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-csv", type=Path, default=DEFAULT_AUDIT_CSV)
    parser.add_argument("--source-events", type=Path, default=DEFAULT_SOURCE_EVENTS)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument("--max-exact-span-minutes", type=int, default=MAX_EXACT_SPAN_MINUTES)
    parser.add_argument("--markdown-limit", type=int, default=100)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_medium_time_or_identity_only_review(
        audit_csv_path=args.audit_csv,
        source_events_path=args.source_events,
        max_exact_span_minutes=args.max_exact_span_minutes,
    )
    write_json(args.output_json, report)
    write_csv(args.output_csv, report)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(render_markdown(report, limit=args.markdown_limit), encoding="utf-8")
    print(
        json.dumps(
            {
                "output_json": str(args.output_json),
                "output_csv": str(args.output_csv),
                "output_md": str(args.output_md),
                "target_items": report["summary"]["target_medium_time_or_identity_only_count"],
                "recommendations": report["summary"]["review_recommendation_counts"],
                "subcategories": report["summary"]["identity_subcategory_counts"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
