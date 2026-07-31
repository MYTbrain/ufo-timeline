"""Review low-risk type-subcode source evidence.

This consumes the type-subcode source evidence packet and produces
recommendation-only review output. It does not create decisions, preview output,
accepted records, or canonical mutations.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


DEFAULT_PACKET = Path("data/reports/entity_resolution_type_subcode_source_evidence_packet_worklist.json")
DEFAULT_JSON_OUTPUT = Path("data/reports/entity_resolution_type_subcode_source_review_worklist.json")
DEFAULT_CSV_OUTPUT = Path("data/reports/entity_resolution_type_subcode_source_review_worklist.csv")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/entity_resolution_type_subcode_source_review_worklist.md")

INPUT_PACKET_POLICY = "entity_resolution_type_subcode_source_row_evidence_review_only"
REVIEW_POLICY = "entity_resolution_type_subcode_source_review_only"
SOURCE_REVIEW_SAME_EVENT = "source_review_type_subcode_same_event_candidate"
NEEDS_MORE_EVIDENCE = "needs_more_evidence"

CSV_FIELDS = (
    "review_rank",
    "review_item_id",
    "effect_id",
    "review_recommendation",
    "confidence",
    "projected_event_reduction",
    "type_values",
    "type_family_prefixes",
    "active_conflicts",
    "failed_conditions",
    "review_reason_codes",
    "source_names",
    "source_native_ids",
    "dates",
    "locations",
    "coordinate_values",
)


def build_type_subcode_source_review(packet: dict[str, Any]) -> dict[str, Any]:
    validate_packet_safety(packet)
    items = [item for item in packet.get("items") or [] if isinstance(item, dict)]
    reviewed = [review_item(item) for item in items]
    projected_by_recommendation: dict[str, int] = {}
    for item in reviewed:
        recommendation = clean_text(item.get("review_recommendation")) or "unknown"
        projected_by_recommendation[recommendation] = projected_by_recommendation.get(recommendation, 0) + as_int(
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
            "source_review_type_subcode_same_event_candidate requires type-only conflict, one source/type family, single source-native/date/location/coordinate evidence, and no missing evidence.",
            "Review grouped artifacts before approval because overlapping effects may not reduce independently.",
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
        raise ValueError("type-subcode source packet is unsafe for review: " + "; ".join(errors))


def review_item(item: dict[str, Any]) -> dict[str, Any]:
    source_summary = item.get("source_summary") if isinstance(item.get("source_summary"), dict) else {}
    conflict_summary = item.get("conflict_summary") if isinstance(item.get("conflict_summary"), dict) else {}
    conflict_flags = conflict_summary.get("conflict_flags") if isinstance(conflict_summary.get("conflict_flags"), dict) else {}
    active_conflicts = sorted(name for name, active in conflict_flags.items() if active)
    type_values = string_list(item.get("type_values")) or string_list(source_summary.get("type_values"))
    type_family_prefixes = string_list(item.get("type_family_prefixes"))
    conditions = {
        "classification_is_low_risk_type_subcode": clean_text(item.get("type_conflict_classification"))
        == "type_only_single_family_subcode_conflict",
        "review_risk_tier_lower": clean_text(item.get("review_risk_tier")) == "lower",
        "identity_consistency_single_source_id_date_location": clean_text(item.get("identity_consistency"))
        == "single_source_id_date_location",
        "type_only_conflict": active_conflicts == ["type"],
        "single_type_family": len(type_family_prefixes) == 1,
        "multiple_type_values": len(type_values) >= 2,
        "single_source_name": len(string_list(source_summary.get("source_names"))) == 1,
        "single_source_native_id": len(string_list(source_summary.get("source_native_ids"))) == 1,
        "single_date": len(string_list(source_summary.get("date_values"))) == 1,
        "single_location": len(string_list(source_summary.get("location_values"))) == 1,
        "single_coordinate": len(string_list(source_summary.get("coordinate_values"))) == 1,
        "no_missing_candidate_input_ids": not item.get("candidate_input_ids_missing_from_evidence"),
        "no_missing_canonical_event_ids": not item.get("missing_canonical_event_ids"),
        "positive_projected_reduction": as_int(item.get("projected_event_reduction")) > 0,
    }
    failed_conditions = [key for key, passed in conditions.items() if not passed]
    same_event_candidate = not failed_conditions
    recommendation = SOURCE_REVIEW_SAME_EVENT if same_event_candidate else NEEDS_MORE_EVIDENCE
    confidence = "medium" if same_event_candidate else "low"
    reason_codes = (
        [
            "type_only_source_subcode_variant",
            "same_source_native_date_location_coordinate",
            "review_only_not_decision",
        ]
        if same_event_candidate
        else ["needs_more_evidence"] + failed_conditions
    )
    return {
        "review_rank": item.get("review_rank"),
        "review_item_id": clean_text(item.get("review_item_id")),
        "effect_id": clean_text(item.get("effect_id")),
        "review_recommendation": recommendation,
        "confidence": confidence,
        "projected_event_reduction": as_int(item.get("projected_event_reduction")),
        "type_conflict_classification": clean_text(item.get("type_conflict_classification")),
        "review_risk_tier": clean_text(item.get("review_risk_tier")),
        "identity_consistency": clean_text(item.get("identity_consistency")),
        "type_values": type_values,
        "type_family_prefixes": type_family_prefixes,
        "active_conflicts": active_conflicts,
        "failed_conditions": failed_conditions,
        "review_reason_codes": reason_codes,
        "source_names": string_list(source_summary.get("source_names")),
        "source_native_ids": string_list(source_summary.get("source_native_ids")),
        "dates": string_list(source_summary.get("date_values")),
        "locations": string_list(source_summary.get("location_values")),
        "coordinate_values": string_list(source_summary.get("coordinate_values")),
        "merge_canonical_event_ids": string_list(item.get("merge_canonical_event_ids")),
        "candidate_canonical_input_ids": string_list(item.get("candidate_canonical_input_ids")),
        "notes": (
            "Source evidence is consistent with a same-event source subtype-code variant; still requires explicit decision and apply gates."
            if same_event_candidate
            else "Deferred because one or more source-review safety conditions failed."
        ),
    }


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
            key = clean_text(condition)
            if key:
                counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, review: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for item in review.get("items") or []:
            if isinstance(item, dict):
                writer.writerow({field: csv_value(item.get(field)) for field in CSV_FIELDS})


def write_markdown(path: Path, review: dict[str, Any], *, item_limit: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = review.get("summary") if isinstance(review.get("summary"), dict) else {}
    lines = [
        "# Type-Subcode Source Review",
        "",
        "This report is review-only. It does not accept, apply, or mutate canonical merge decisions.",
        "",
        "## Summary",
        "",
        f"- Input items: `{summary.get('input_item_count', 0)}`",
        f"- Reviewed items: `{summary.get('reviewed_item_count', 0)}`",
        f"- Recommendations: `{json.dumps(summary.get('review_recommendation_counts', {}), sort_keys=True)}`",
        f"- Confidence: `{json.dumps(summary.get('confidence_counts', {}), sort_keys=True)}`",
        f"- Canonical outputs mutated: `{str(review.get('canonical_outputs_mutated')).lower()}`",
        "",
        "## Items",
        "",
    ]
    items = [item for item in review.get("items") or [] if isinstance(item, dict)]
    for item in items[: max(0, item_limit)]:
        lines.extend(
            [
                f"### #{item.get('review_rank')} {item.get('review_item_id')}",
                "",
                f"- Recommendation: `{item.get('review_recommendation')}` confidence `{item.get('confidence')}`",
                f"- Effect: `{item.get('effect_id')}`",
                f"- Type values: {', '.join(string_list(item.get('type_values'))) or 'none'}",
                f"- Source/native: {', '.join(string_list(item.get('source_names'))) or 'none'} / {', '.join(string_list(item.get('source_native_ids'))) or 'none'}",
                f"- Date/location: {', '.join(string_list(item.get('dates'))) or 'none'} / {', '.join(string_list(item.get('locations'))) or 'none'}",
                f"- Coordinates: {', '.join(string_list(item.get('coordinate_values'))) or 'none'}",
                f"- Failed conditions: {', '.join(string_list(item.get('failed_conditions'))) or 'none'}",
                "",
            ]
        )
    if len(items) > item_limit:
        lines.extend(["", f"_Markdown limited to {item_limit} of {len(items)} reviewed items._", ""])
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def csv_value(value: Any) -> Any:
    if isinstance(value, list):
        return "; ".join(clean_text(item) for item in value if clean_text(item))
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [text for item in value if (text := clean_text(item))]
    text = clean_text(value)
    return [text] if text else []


def as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument("--markdown-item-limit", type=int, default=20)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    review = build_type_subcode_source_review(read_json(args.packet))
    write_json(args.json_output, review)
    write_csv(args.csv_output, review)
    write_markdown(args.markdown_output, review, item_limit=args.markdown_item_limit)
    print(
        json.dumps(
            {
                "json_output": str(args.json_output),
                "csv_output": str(args.csv_output),
                "markdown_output": str(args.markdown_output),
                "review_policy": review["review_policy"],
                "reviewed_item_count": review["summary"]["reviewed_item_count"],
                "review_recommendation_counts": review["summary"]["review_recommendation_counts"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
