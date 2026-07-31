"""Review unresolved type-conflict subcode-policy evidence.

This classifier is conservative and recommendation-only. It targets subtype-code
conflicts where source/date/location identity is strict but coordinates differ.
Coordinate variance is recorded, not treated as automatic merge authority.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from parser.canonical_schema import clean_text
from scripts.review_type_conflict_source_identity_candidates import (
    active_conflicts,
    count_by,
    failed_condition_counts,
    max_coordinate_distance_km,
    projected_reduction_by_recommendation,
    source_summary,
    string_list,
    summary_similarity_min,
)


DEFAULT_PACKET = Path("data/reports/entity_resolution_type_conflict_subcode_policy_evidence_packet_worklist.json")
DEFAULT_JSON_OUTPUT = Path("data/reports/entity_resolution_type_conflict_subcode_policy_review_worklist.json")
DEFAULT_CSV_OUTPUT = Path("data/reports/entity_resolution_type_conflict_subcode_policy_review_worklist.csv")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/entity_resolution_type_conflict_subcode_policy_review_worklist.md")

PACKET_POLICY = "entity_resolution_type_conflict_subcode_policy_evidence_review_only"
REVIEW_POLICY = "entity_resolution_type_conflict_subcode_policy_review_only"

SAFE_RECOMMENDATION = "source_review_subcode_policy_same_event_candidate"
NEEDS_MORE_EVIDENCE = "needs_more_evidence"


def review_type_conflict_subcode_policy_candidates(
    *,
    packet: dict[str, Any],
    packet_path: Path | None = None,
) -> dict[str, Any]:
    validate_packet_safety(packet)
    review_items = []
    for index, item in enumerate([row for row in packet.get("items") or [] if isinstance(row, dict)], start=1):
        review_items.append(review_item(item, review_rank=index))
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
        "inputs": {
            "packet": str(packet_path) if packet_path else None,
        },
        "summary": {
            "input_item_count": len(packet.get("items") or []),
            "reviewed_item_count": len(review_items),
            "review_recommendation_counts": count_by(review_items, "review_recommendation"),
            "confidence_counts": count_by(review_items, "confidence"),
            "failed_condition_counts": failed_condition_counts(review_items),
            "projected_event_reduction_by_review_recommendation": projected_reduction_by_recommendation(
                review_items
            ),
        },
        "items": review_items,
        "notes": [
            "This subcode-policy source review is recommendation-only.",
            "Coordinate variance is allowed only when source/native/date/location text and summaries are strict.",
            "same-event recommendations still require grouping, explicit decision staging, and preview/apply gates.",
        ],
    }


def validate_packet_safety(packet: dict[str, Any]) -> None:
    errors: list[str] = []
    if packet.get("packet_policy") != PACKET_POLICY:
        errors.append(f"packet_policy must be {PACKET_POLICY!r}")
    for flag in (
        "canonical_outputs_mutated",
        "preview_outputs_written",
        "decisions_created",
        "decision_outputs_created",
        "auto_merge_performed",
        "ready_for_canonical_apply",
    ):
        if packet.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError("subcode-policy evidence packet is unsafe: " + "; ".join(errors))


def review_item(item: dict[str, Any], *, review_rank: int) -> dict[str, Any]:
    conditions = condition_results(item)
    failed = sorted(name for name, ok in conditions.items() if not ok)
    is_candidate = not failed
    return {
        "review_rank": review_rank,
        "review_item_id": clean_text(item.get("review_item_id")),
        "effect_id": clean_text(item.get("effect_id")),
        "review_recommendation": SAFE_RECOMMENDATION if is_candidate else NEEDS_MORE_EVIDENCE,
        "confidence": "medium" if is_candidate else "low",
        "projected_event_reduction": int(item.get("projected_event_reduction") or 0),
        "type_conflict_classification": clean_text(item.get("type_conflict_classification")),
        "review_risk_tier": clean_text(item.get("review_risk_tier")),
        "identity_consistency": clean_text(item.get("identity_consistency")),
        "type_values": string_list(item.get("type_values")),
        "type_family_prefixes": string_list(item.get("type_family_prefixes")),
        "active_conflicts": active_conflicts(item),
        "failed_conditions": failed,
        "condition_results": conditions,
        "max_coordinate_distance_km": max_coordinate_distance_km(item),
        "summary_similarity_min": summary_similarity_min(item),
        "review_reason_codes": reason_codes(item, is_candidate=is_candidate, failed_conditions=failed),
        "source_names": string_list(source_summary(item).get("source_names")),
        "source_native_ids": string_list(source_summary(item).get("source_native_ids")),
        "dates": string_list(source_summary(item).get("date_values")),
        "times": string_list(source_summary(item).get("time_values")),
        "locations": string_list(source_summary(item).get("location_values")),
        "coordinate_values": string_list(source_summary(item).get("coordinate_values")),
        "merge_canonical_event_ids": string_list(item.get("merge_canonical_event_ids")),
        "candidate_canonical_input_ids": string_list(item.get("candidate_canonical_input_ids")),
        "notes": (
            "Strict source/native/date/location text supports same-event subtype-code policy review; coordinate variance remains recorded."
            if is_candidate
            else "Source evidence is not strict enough for subcode-policy same-event recommendation."
        ),
    }


def condition_results(item: dict[str, Any]) -> dict[str, bool]:
    summary = source_summary(item)
    return {
        "no_missing_event_or_input_ids": not item.get("missing_canonical_event_ids")
        and not item.get("candidate_input_ids_missing_from_evidence"),
        "single_source": len(string_list(summary.get("source_names"))) == 1,
        "single_source_native_id": len(string_list(summary.get("source_native_ids"))) == 1,
        "single_exact_date": len(string_list(summary.get("date_values"))) == 1
        and set(string_list(summary.get("date_precision_values"))) <= {"exact_day"},
        "single_location_text": len(string_list(summary.get("location_values"))) == 1,
        "no_time_conflict": "time" not in active_conflicts(item),
        "no_shape_conflict": "shape" not in active_conflicts(item),
        "no_source_native_conflict": "source_native_id" not in active_conflicts(item),
        "single_type_family": len(string_list(item.get("type_family_prefixes"))) == 1,
        "summary_text_compatible": summary_similarity_min(item) is not None
        and (summary_similarity_min(item) or 0) >= 0.65,
    }


def reason_codes(item: dict[str, Any], *, is_candidate: bool, failed_conditions: list[str]) -> list[str]:
    if not is_candidate:
        return [f"failed:{condition}" for condition in failed_conditions]
    codes = ["same_source_native_date_location", "compatible_summary_text", "type_subcode_variant"]
    if "coordinate" in active_conflicts(item):
        codes.append("coordinate_variance_recorded")
    codes.append("review_only_not_decision")
    return codes


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def csv_value(value: Any) -> Any:
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return value


def write_csv(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "review_rank",
        "review_recommendation",
        "confidence",
        "review_item_id",
        "effect_id",
        "projected_event_reduction",
        "type_values",
        "active_conflicts",
        "failed_conditions",
        "max_coordinate_distance_km",
        "summary_similarity_min",
        "source_names",
        "source_native_ids",
        "dates",
        "times",
        "locations",
        "coordinate_values",
        "review_reason_codes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in report.get("items") or []:
            writer.writerow({field: csv_value(item.get(field)) for field in fieldnames})


def write_markdown(path: Path, report: dict[str, Any], *, item_limit: int) -> None:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    lines = [
        "# Type-Conflict Subcode Policy Review",
        "",
        f"- Policy: `{report.get('review_policy')}`",
        f"- Reviewed items: `{summary.get('reviewed_item_count', 0)}`",
        f"- Canonical outputs mutated: `{str(report.get('canonical_outputs_mutated')).lower()}`",
        "",
        "## Recommendation Counts",
        "",
    ]
    for recommendation, count in sorted((summary.get("review_recommendation_counts") or {}).items()):
        lines.append(f"- `{recommendation}`: {count}")
    lines.extend(["", "## Review Rows", ""])
    for item in (report.get("items") or [])[: max(0, item_limit)]:
        lines.extend(
            [
                f"### {item.get('review_rank')}. {item.get('review_recommendation')}",
                "",
                f"- Review item: `{item.get('review_item_id')}`",
                f"- Confidence: `{item.get('confidence')}`",
                f"- Type values: {', '.join(item.get('type_values') or [])}",
                f"- Active conflicts: {', '.join(item.get('active_conflicts') or []) or 'none'}",
                f"- Failed conditions: {', '.join(item.get('failed_conditions') or []) or 'none'}",
                f"- Max coordinate distance km: `{item.get('max_coordinate_distance_km')}`",
                f"- Summary similarity min: `{item.get('summary_similarity_min')}`",
                f"- Source/native/date/time: {', '.join(item.get('source_names') or [])} / {', '.join(item.get('source_native_ids') or [])} / {', '.join(item.get('dates') or [])} / {', '.join(item.get('times') or [])}",
                f"- Locations: {'; '.join(item.get('locations') or [])}",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument("--markdown-item-limit", type=int, default=40)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = review_type_conflict_subcode_policy_candidates(packet=read_json(args.packet), packet_path=args.packet)
    report["outputs"] = {
        "json": str(args.json_output),
        "csv": str(args.csv_output),
        "markdown": str(args.markdown_output),
    }
    write_json(args.json_output, report)
    write_csv(args.csv_output, report)
    write_markdown(args.markdown_output, report, item_limit=args.markdown_item_limit)
    print(
        json.dumps(
            {
                "json_output": str(args.json_output),
                "csv_output": str(args.csv_output),
                "markdown_output": str(args.markdown_output),
                "reviewed_item_count": report["summary"]["reviewed_item_count"],
                "review_recommendation_counts": report["summary"]["review_recommendation_counts"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
