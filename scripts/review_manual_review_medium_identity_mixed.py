"""Build a review-only packet for medium identity-mixed manual-review rows.

Targets components with ``same_source_multiple_native_ids`` plus additional
non-coordinate conflicts, excluding the simpler identity/time-only lane and the
coordinate-span lane. This is evidence for manual review only: no decisions,
apply, or canonical mutation.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable


DEFAULT_AUDIT_CSV = Path("data/reports/manual_review_ai_after_time_norm_replacement_audit.csv")
DEFAULT_SOURCE_EVENTS = Path(
    "data/canonical_time_norm_recommended_plus_shorthand_plus_likely_plus_single_exact_context/deduped_events.jsonl"
)
DEFAULT_JSON_OUTPUT = Path("data/reports/manual_review_ai_after_time_norm_medium_identity_mixed_review.json")
DEFAULT_CSV_OUTPUT = Path("data/reports/manual_review_ai_after_time_norm_medium_identity_mixed_review.csv")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/manual_review_ai_after_time_norm_medium_identity_mixed_review.md")

REVIEW_POLICY = "manual_review_medium_identity_mixed_review_v1"
IDENTITY_MIXED_REVIEW_CANDIDATE = "identity_mixed_review_candidate"
NEEDS_DEEPER_IDENTITY_MIXED_REVIEW = "needs_deeper_identity_mixed_review"

CSV_FIELDS = (
    "review_rank",
    "replacement_event_id",
    "review_recommendation",
    "identity_mixed_subcategory",
    "confidence",
    "projected_event_reduction",
    "risk_flags",
    "source_file_values",
    "native_id_profile",
    "time_raw_values",
    "type_values",
    "failed_conditions",
    "component_event_count",
    "component_event_ids",
)


def build_medium_identity_mixed_review(*, audit_csv_path: Path, source_events_path: Path) -> dict[str, Any]:
    audit_rows = read_csv(audit_csv_path)
    target_rows = [row for row in audit_rows if is_medium_identity_mixed(row)]
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
        "inputs": {"audit_csv": str(audit_csv_path), "source_events": str(source_events_path)},
        "summary": {
            "audit_rows_read": len(audit_rows),
            "target_medium_identity_mixed_count": len(target_rows),
            "reviewed_item_count": len(items),
            "source_component_ids_expected": len(required_ids),
            "source_component_rows_found": len(source_rows),
            "missing_source_component_id_count": len(missing_source_ids),
            "review_recommendation_counts": count_by(items, "review_recommendation"),
            "identity_mixed_subcategory_counts": count_by(items, "identity_mixed_subcategory"),
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
            "Rows contain same-source multiple native IDs plus additional body/time/type/location conflicts.",
            "Manual source identity review is required before any decision candidate promotion.",
        ],
    }


def is_medium_identity_mixed(row: dict[str, str]) -> bool:
    flags = set(split_pipe(row.get("risk_flags")))
    return (
        clean_text(row.get("risk_level")) == "medium"
        and "same_source_multiple_native_ids" in flags
        and "coordinate_span_gt_5km" not in flags
        and not flags <= {"same_source_multiple_native_ids", "time_raw_conflict"}
    )


def review_row(row: dict[str, str], *, component_rows: list[dict[str, Any]]) -> dict[str, Any]:
    flags = set(split_pipe(row.get("risk_flags")))
    body_conflict = bool({"description_text_conflict", "summary_text_conflict"} & flags)
    classification_conflict = bool({"type_conflict", "shape_conflict"} & flags)
    location_conflict = "location_text_conflict" in flags
    time_conflict = "time_raw_conflict" in flags
    if body_conflict and not classification_conflict and not location_conflict:
        subcategory = "identity_plus_body_text_conflict"
    elif classification_conflict:
        subcategory = "identity_plus_classification_conflict"
    elif location_conflict:
        subcategory = "identity_plus_location_conflict"
    elif time_conflict:
        subcategory = "identity_plus_time_conflict"
    else:
        subcategory = "identity_mixed_other"

    native_profile = build_native_id_profile(component_rows)
    conditions = {
        "audit_medium_identity_mixed": is_medium_identity_mixed(row),
        "source_rows_available": len(component_rows) == len(split_pipe(row.get("component_event_ids"))),
        "same_source_multiple_native_ids": has_same_source_multiple_native_ids(native_profile),
        "no_classification_or_location_conflict": not classification_conflict and not location_conflict,
        "body_or_time_conflict_requires_manual_review": False,
    }
    failed_conditions = [key for key, passed in conditions.items() if not passed]

    return {
        "review_rank": None,
        "replacement_event_id": clean_text(row.get("replacement_event_id")),
        "review_recommendation": NEEDS_DEEPER_IDENTITY_MIXED_REVIEW,
        "identity_mixed_subcategory": subcategory,
        "confidence": "low",
        "projected_event_reduction": projected_event_reduction(row),
        "risk_flags": sorted(flags),
        "source_file_values": split_pipe(row.get("source_file_values")),
        "native_id_profile": native_profile,
        "time_raw_values": split_pipe(row.get("time_raw_values")),
        "type_values": split_pipe(row.get("type_values")),
        "location_raw_values": split_pipe(row.get("location_raw_values")),
        "body_variant_counts": {
            "description_variant_count": safe_int(row.get("description_variant_count")),
            "summary_variant_count": safe_int(row.get("summary_variant_count")),
        },
        "component_evidence": build_component_evidence(component_rows),
        "failed_conditions": failed_conditions,
        "review_reason_codes": ["needs_deeper_identity_mixed_review", subcategory] + failed_conditions,
        "component_event_count": safe_int(row.get("component_event_count")),
        "canonical_input_id_count": safe_int(row.get("canonical_input_id_count")),
        "coordinate_span_km": safe_float(row.get("coordinate_span_km")),
        "date_iso_values": split_pipe(row.get("date_iso_values")),
        "component_event_ids": split_pipe(row.get("component_event_ids")),
    }


def build_native_id_profile(component_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_source: dict[str, dict[str, Any]] = {}
    for row in component_rows:
        source = clean_text(row.get("source_file")) or "unknown"
        native_id = clean_text(row.get("source_native_id")) or "unknown"
        entry = by_source.setdefault(source, {"source_file": source, "native_ids": set(), "event_ids": []})
        entry["native_ids"].add(native_id)
        entry["event_ids"].append(event_id_for(row))
    return [
        {
            "source_file": source,
            "native_id_count": len(sorted(entry["native_ids"])),
            "native_ids": sorted(entry["native_ids"])[:20],
            "component_event_ids": sorted(entry["event_ids"])[:20],
        }
        for source, entry in sorted(by_source.items())
    ]


def has_same_source_multiple_native_ids(native_profile: list[dict[str, Any]]) -> bool:
    return any(int(entry.get("native_id_count") or 0) > 1 for entry in native_profile)


def build_component_evidence(component_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    evidence = []
    for row in component_rows:
        evidence.append(
            {
                "component_event_id": event_id_for(row),
                "source_file": clean_text(row.get("source_file")),
                "source_native_id": clean_text(row.get("source_native_id")),
                "source_row_number": clean_text(row.get("source_row_number")),
                "time_raw": clean_text(row.get("time_raw")),
                "type_normalized": clean_text(row.get("type_normalized")),
                "location_raw": clean_text(row.get("location_raw")),
                "summary_snippet": snippet(clean_text(row.get("summary"))),
                "description_snippet": snippet(clean_text(row.get("description"))),
            }
        )
    return evidence


def projected_event_reduction(row: dict[str, str]) -> int:
    return max(0, safe_int(row.get("component_event_count")) - 1)


def review_sort_key(item: dict[str, Any]) -> tuple[str, int, str]:
    return (item["identity_mixed_subcategory"], -int(item["projected_event_reduction"]), item["replacement_event_id"])


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
        "# Medium Identity-Mixed Review",
        "",
        "This report is review-only. It does not accept decisions or mutate canonical outputs.",
        "",
        "## Summary",
        "",
        f"- Target items: {report['summary']['target_medium_identity_mixed_count']}",
        f"- Recommendations: {json.dumps(report['summary']['review_recommendation_counts'], sort_keys=True)}",
        f"- Subcategories: {json.dumps(report['summary']['identity_mixed_subcategory_counts'], sort_keys=True)}",
        f"- Projected reduction by recommendation: {json.dumps(report['summary']['projected_event_reduction_by_review_recommendation'], sort_keys=True)}",
        "",
        "## Top Items",
        "",
        "| Recommendation | Subcategory | Replacement | Flags | Native IDs | Failed Conditions |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in items[:limit]:
        lines.append(
            "| "
            + " | ".join(
                [
                    escape_md(clean_text(item.get("review_recommendation"))),
                    escape_md(clean_text(item.get("identity_mixed_subcategory"))),
                    f"`{escape_md(clean_text(item.get('replacement_event_id')))}`",
                    escape_md("|".join(item.get("risk_flags") or [])),
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
                    "identity_mixed_subcategory": item.get("identity_mixed_subcategory"),
                    "confidence": item.get("confidence"),
                    "projected_event_reduction": item.get("projected_event_reduction"),
                    "risk_flags": "|".join(item.get("risk_flags") or []),
                    "source_file_values": "|".join(item.get("source_file_values") or []),
                    "native_id_profile": format_native_profile(item.get("native_id_profile") or []),
                    "time_raw_values": "|".join(item.get("time_raw_values") or []),
                    "type_values": "|".join(item.get("type_values") or []),
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


def snippet(value: str, limit: int = 160) -> str:
    value = clean_text(value)
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "..."


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
    parser.add_argument("--markdown-limit", type=int, default=100)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_medium_identity_mixed_review(audit_csv_path=args.audit_csv, source_events_path=args.source_events)
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
                "target_items": report["summary"]["target_medium_identity_mixed_count"],
                "recommendations": report["summary"]["review_recommendation_counts"],
                "subcategories": report["summary"]["identity_mixed_subcategory_counts"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
