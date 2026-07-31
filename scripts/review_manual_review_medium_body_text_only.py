"""Review medium-risk manual-review components with only body text conflicts.

This targets replacement-audit rows whose only risk flags are
``description_text_conflict`` and ``summary_text_conflict``. It hydrates source
component rows, computes text-similarity diagnostics, and emits review-only
outputs. It never creates decisions, applies merges, or mutates canonical data.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import json
from pathlib import Path
from typing import Any, Iterable


DEFAULT_AUDIT_CSV = Path("data/reports/manual_review_ai_after_time_norm_replacement_audit.csv")
DEFAULT_SOURCE_EVENTS = Path(
    "data/canonical_time_norm_recommended_plus_shorthand_plus_likely_plus_single_exact_context/deduped_events.jsonl"
)
DEFAULT_JSON_OUTPUT = Path("data/reports/manual_review_ai_after_time_norm_medium_body_text_only_review.json")
DEFAULT_CSV_OUTPUT = Path("data/reports/manual_review_ai_after_time_norm_medium_body_text_only_review.csv")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/manual_review_ai_after_time_norm_medium_body_text_only_review.md")

REVIEW_POLICY = "manual_review_medium_body_text_only_review_v1"
BODY_VARIANT_REVIEW_CANDIDATE = "body_variant_review_candidate"
NEEDS_DEEPER_BODY_REVIEW = "needs_deeper_body_review"
MIN_MINOR_VARIANT_SIMILARITY = 0.92

CSV_FIELDS = (
    "review_rank",
    "replacement_event_id",
    "review_recommendation",
    "body_subcategory",
    "confidence",
    "projected_event_reduction",
    "min_text_similarity",
    "source_file_values",
    "native_id_values",
    "body_snippets",
    "failed_conditions",
    "component_event_count",
    "component_event_ids",
)


def build_medium_body_text_only_review(
    *,
    audit_csv_path: Path,
    source_events_path: Path,
    min_minor_variant_similarity: float = MIN_MINOR_VARIANT_SIMILARITY,
) -> dict[str, Any]:
    audit_rows = read_csv(audit_csv_path)
    target_rows = [row for row in audit_rows if is_medium_body_text_only(row)]
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
            min_minor_variant_similarity=min_minor_variant_similarity,
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
            "min_minor_variant_similarity": min_minor_variant_similarity,
        },
        "summary": {
            "audit_rows_read": len(audit_rows),
            "target_medium_body_text_only_count": len(target_rows),
            "reviewed_item_count": len(items),
            "source_component_ids_expected": len(required_ids),
            "source_component_rows_found": len(source_rows),
            "missing_source_component_id_count": len(missing_source_ids),
            "review_recommendation_counts": count_by(items, "review_recommendation"),
            "body_subcategory_counts": count_by(items, "body_subcategory"),
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
            "Body text conflicts can preserve distinct witness details, so candidates are not promoted automatically.",
            "Minor body variants require single source/native identity and high normalized text similarity.",
        ],
    }


def is_medium_body_text_only(row: dict[str, str]) -> bool:
    return clean_text(row.get("risk_level")) == "medium" and set(split_pipe(row.get("risk_flags"))) == {
        "description_text_conflict",
        "summary_text_conflict",
    }


def review_row(
    row: dict[str, str],
    *,
    component_rows: list[dict[str, Any]],
    min_minor_variant_similarity: float,
) -> dict[str, Any]:
    body_evidence = build_body_evidence(component_rows)
    similarities = text_similarities([entry["combined_text"] for entry in body_evidence])
    min_similarity = min(similarities) if similarities else 1.0
    source_values = distinct_values(component_rows, "source_file")
    native_id_values = distinct_values(component_rows, "source_native_id")
    single_source_native = len(source_values) == 1 and len(native_id_values) == 1
    minor_variant = min_similarity >= min_minor_variant_similarity
    subcategory = "minor_body_wording_variant" if minor_variant else "substantive_body_text_variance"

    conditions = {
        "audit_medium_body_text_only": is_medium_body_text_only(row),
        "source_rows_available": len(component_rows) == len(split_pipe(row.get("component_event_ids"))),
        "single_source_native_identity": single_source_native,
        "minor_body_text_similarity": minor_variant,
    }
    failed_conditions = [key for key, passed in conditions.items() if not passed]
    review_candidate = not failed_conditions

    return {
        "review_rank": None,
        "replacement_event_id": clean_text(row.get("replacement_event_id")),
        "review_recommendation": BODY_VARIANT_REVIEW_CANDIDATE if review_candidate else NEEDS_DEEPER_BODY_REVIEW,
        "body_subcategory": subcategory,
        "confidence": "low",
        "projected_event_reduction": projected_event_reduction(row),
        "min_text_similarity": round(min_similarity, 4),
        "source_file_values": source_values,
        "native_id_values": native_id_values,
        "body_evidence": body_evidence,
        "failed_conditions": failed_conditions,
        "review_reason_codes": (
            [
                "body_text_conflict_only",
                "single_source_native_identity",
                "minor_body_wording_variant",
                "manual_body_review_required",
                "review_only_not_decision",
            ]
            if review_candidate
            else ["needs_deeper_body_review", subcategory] + failed_conditions
        ),
        "component_event_count": safe_int(row.get("component_event_count")),
        "canonical_input_id_count": safe_int(row.get("canonical_input_id_count")),
        "coordinate_span_km": safe_float(row.get("coordinate_span_km")),
        "date_iso_values": split_pipe(row.get("date_iso_values")),
        "time_raw_values": split_pipe(row.get("time_raw_values")),
        "location_raw_values": split_pipe(row.get("location_raw_values")),
        "component_event_ids": split_pipe(row.get("component_event_ids")),
    }


def build_body_evidence(component_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    evidence = []
    for row in component_rows:
        summary = clean_text(row.get("summary"))
        description = clean_text(row.get("description"))
        combined = clean_text(f"{summary} {description}")
        evidence.append(
            {
                "component_event_id": event_id_for(row),
                "source_file": clean_text(row.get("source_file")),
                "source_native_id": clean_text(row.get("source_native_id")),
                "source_row_number": clean_text(row.get("source_row_number")),
                "summary_snippet": snippet(summary),
                "description_snippet": snippet(description),
                "combined_text": combined,
            }
        )
    return evidence


def text_similarities(values: list[str]) -> list[float]:
    normalized = [normalize_text(value) for value in values if normalize_text(value)]
    similarities = []
    for left_index, left in enumerate(normalized):
        for right in normalized[left_index + 1 :]:
            similarities.append(difflib.SequenceMatcher(None, left, right).ratio())
    return similarities


def normalize_text(value: str) -> str:
    return " ".join("".join(char.lower() if char.isalnum() else " " for char in value).split())


def projected_event_reduction(row: dict[str, str]) -> int:
    return max(0, safe_int(row.get("component_event_count")) - 1)


def review_sort_key(item: dict[str, Any]) -> tuple[int, float, int, str]:
    return (
        0 if item["review_recommendation"] == BODY_VARIANT_REVIEW_CANDIDATE else 1,
        -float(item["min_text_similarity"]),
        -int(item["projected_event_reduction"]),
        item["replacement_event_id"],
    )


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
        "# Medium Body-Text-Only Review",
        "",
        "This report is review-only. It does not accept decisions or mutate canonical outputs.",
        "",
        "## Summary",
        "",
        f"- Target items: {report['summary']['target_medium_body_text_only_count']}",
        f"- Recommendations: {json.dumps(report['summary']['review_recommendation_counts'], sort_keys=True)}",
        f"- Subcategories: {json.dumps(report['summary']['body_subcategory_counts'], sort_keys=True)}",
        f"- Projected reduction by recommendation: {json.dumps(report['summary']['projected_event_reduction_by_review_recommendation'], sort_keys=True)}",
        "",
        "## Top Items",
        "",
        "| Recommendation | Subcategory | Replacement | Similarity | Reduction | Evidence | Failed Conditions |",
        "| --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    for item in items[:limit]:
        lines.append(
            "| "
            + " | ".join(
                [
                    escape_md(clean_text(item.get("review_recommendation"))),
                    escape_md(clean_text(item.get("body_subcategory"))),
                    f"`{escape_md(clean_text(item.get('replacement_event_id')))}`",
                    str(item.get("min_text_similarity")),
                    str(item.get("projected_event_reduction")),
                    escape_md(format_body_snippets(item.get("body_evidence") or [])),
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
                    "body_subcategory": item.get("body_subcategory"),
                    "confidence": item.get("confidence"),
                    "projected_event_reduction": item.get("projected_event_reduction"),
                    "min_text_similarity": item.get("min_text_similarity"),
                    "source_file_values": "|".join(item.get("source_file_values") or []),
                    "native_id_values": "|".join(item.get("native_id_values") or []),
                    "body_snippets": format_body_snippets(item.get("body_evidence") or []),
                    "failed_conditions": "|".join(item.get("failed_conditions") or []),
                    "component_event_count": item.get("component_event_count"),
                    "component_event_ids": "|".join(item.get("component_event_ids") or []),
                }
            )


def format_body_snippets(evidence: list[dict[str, str]]) -> str:
    parts = []
    for entry in evidence:
        event_id = clean_text(entry.get("component_event_id"))
        native_id = clean_text(entry.get("source_native_id"))
        text = clean_text(entry.get("description_snippet")) or clean_text(entry.get("summary_snippet"))
        parts.append(f"{event_id}/{native_id}: {text}")
    return " || ".join(parts)


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


def distinct_values(rows: list[dict[str, Any]], field: str) -> list[str]:
    seen: set[str] = set()
    values: list[str] = []
    for row in rows:
        value = clean_text(row.get(field))
        if value and value not in seen:
            values.append(value)
            seen.add(value)
    return values


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
    parser.add_argument("--min-minor-variant-similarity", type=float, default=MIN_MINOR_VARIANT_SIMILARITY)
    parser.add_argument("--markdown-limit", type=int, default=100)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_medium_body_text_only_review(
        audit_csv_path=args.audit_csv,
        source_events_path=args.source_events,
        min_minor_variant_similarity=args.min_minor_variant_similarity,
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
                "target_items": report["summary"]["target_medium_body_text_only_count"],
                "recommendations": report["summary"]["review_recommendation_counts"],
                "subcategories": report["summary"]["body_subcategory_counts"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
