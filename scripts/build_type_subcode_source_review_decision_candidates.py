"""Build preview-only ER decision candidates for safe type-subcode groups.

This is a staging adapter, not an apply step. It consumes the source-review
group report for type-subcode-only conflicts and emits normalized decision
records that can be passed through the existing plan-only ER effects path.
Canonical event artifacts are not mutated by this script.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from parser.canonical_schema import clean_text, stable_hash


DEFAULT_GROUPS = Path("data/reports/entity_resolution_type_subcode_source_review_groups_worklist.json")
DEFAULT_SOURCE_REVIEW = Path("data/reports/entity_resolution_type_subcode_source_review_worklist.json")
DEFAULT_DECISIONS_OUTPUT = Path(
    "data/reports/entity_resolution_type_subcode_source_review_decision_candidates_worklist.jsonl"
)
DEFAULT_CHECK_OUTPUT = Path(
    "data/reports/entity_resolution_type_subcode_source_review_decision_candidates_check_worklist.json"
)

GROUPING_POLICY = "entity_resolution_type_subcode_source_review_groups_report_only"
SOURCE_REVIEW_POLICY = "entity_resolution_type_subcode_source_review_only"
CHECK_POLICY = "entity_resolution_type_subcode_source_review_decision_candidates_preview_only_v1"


def build_type_subcode_source_review_decision_candidates(
    *,
    groups_report: dict[str, Any],
    source_review: dict[str, Any],
    groups_path: Path | None = None,
    source_review_path: Path | None = None,
    generated_at: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    validate_safe_input_reports(groups_report=groups_report, source_review=source_review)
    review_items = {
        review_item_id: item
        for item in source_review.get("items", [])
        if isinstance(item, dict)
        if (review_item_id := clean_text(item.get("review_item_id")))
    }
    timestamp = generated_at or datetime.now(UTC).replace(microsecond=0).isoformat()
    decisions: list[dict[str, Any]] = []
    invalid_groups: list[dict[str, Any]] = []

    for group in groups_report.get("groups", []):
        if not isinstance(group, dict):
            continue
        blockers = group_blockers(group, review_items)
        if blockers:
            invalid_groups.append(
                {
                    "group_rank": group.get("group_rank"),
                    "review_item_ids": string_list(group.get("review_item_ids")),
                    "blockers": blockers,
                }
            )
            continue
        decision = build_decision_for_group(group, review_items, generated_at=timestamp)
        decisions.append(decision)

    duplicate_decision_ids = duplicates([row["entity_resolution_decision_id"] for row in decisions])
    duplicate_group_ids = duplicates([row["review_item_id"] for row in decisions])
    validation_errors = []
    if invalid_groups:
        validation_errors.append({"error": "invalid_groups", "count": len(invalid_groups)})
    if duplicate_decision_ids:
        validation_errors.append({"error": "duplicate_decision_ids", "values": duplicate_decision_ids})
    if duplicate_group_ids:
        validation_errors.append({"error": "duplicate_group_review_ids", "values": duplicate_group_ids})

    check = {
        "schema_version": 1,
        "check_policy": CHECK_POLICY,
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "canonical_apply_performed": False,
        "decision_candidates_created": True,
        "ready_for_effects_plan": not validation_errors,
        "valid": not validation_errors,
        "inputs": {
            "groups": str(groups_path) if groups_path else None,
            "source_review": str(source_review_path) if source_review_path else None,
        },
        "source_group_count": len([item for item in groups_report.get("groups", []) if isinstance(item, dict)]),
        "source_review_item_count": len(review_items),
        "decision_candidate_count": len(decisions),
        "projected_event_reduction": sum(int(row.get("projected_event_reduction") or 0) for row in decisions),
        "decision_counts": count_by(decisions, "decision"),
        "review_type_counts": count_by(decisions, "review_type"),
        "invalid_groups": invalid_groups,
        "validation_errors": validation_errors,
        "notes": [
            "Decision candidates are preview-only staging records.",
            "They are derived only from source-reviewed lower-risk type-subcode groups.",
            "No canonical event corpus is mutated by this script.",
        ],
    }
    return decisions, check


def validate_safe_input_reports(*, groups_report: dict[str, Any], source_review: dict[str, Any]) -> None:
    errors: list[str] = []
    if groups_report.get("grouping_policy") != GROUPING_POLICY:
        errors.append(f"groups grouping_policy must be {GROUPING_POLICY!r}")
    if source_review.get("review_policy") != SOURCE_REVIEW_POLICY:
        errors.append(f"source_review review_policy must be {SOURCE_REVIEW_POLICY!r}")
    for name, report in (("groups", groups_report), ("source_review", source_review)):
        for flag in (
            "canonical_outputs_mutated",
            "preview_outputs_written",
            "decisions_created",
            "decision_outputs_created",
            "auto_merge_performed",
        ):
            if report.get(flag) is not False:
                errors.append(f"{name}.{flag} must be false")
    if source_review.get("ready_for_canonical_apply") is not False:
        errors.append("source_review.ready_for_canonical_apply must be false")
    if errors:
        raise ValueError("type-subcode source-review inputs are not safe: " + "; ".join(errors))


def group_blockers(group: dict[str, Any], review_items: dict[str, dict[str, Any]]) -> list[str]:
    blockers: list[str] = []
    review_item_ids = string_list(group.get("review_item_ids"))
    if not review_item_ids:
        blockers.append("missing_review_item_ids")
    if group.get("group_recommendation") != "source_review_group_same_event_candidate":
        blockers.append("group_not_same_event_candidate")
    if group.get("failed_conditions"):
        blockers.append("group_failed_conditions_present")
    if len(string_list(group.get("source_names"))) != 1:
        blockers.append("group_requires_single_source")
    if len(string_list(group.get("source_native_ids"))) != 1:
        blockers.append("group_requires_single_source_native_id")
    if len(string_list(group.get("date_values"))) != 1:
        blockers.append("group_requires_single_date")
    if len(string_list(group.get("location_values"))) != 1:
        blockers.append("group_requires_single_location")

    for review_item_id in review_item_ids:
        item = review_items.get(review_item_id)
        if item is None:
            blockers.append(f"missing_source_review_item:{review_item_id}")
            continue
        if item.get("review_recommendation") != "source_review_type_subcode_same_event_candidate":
            blockers.append(f"review_not_same_event_candidate:{review_item_id}")
        if item.get("failed_conditions"):
            blockers.append(f"review_failed_conditions_present:{review_item_id}")
        if item.get("type_conflict_classification") != "type_only_single_family_subcode_conflict":
            blockers.append(f"review_not_type_subcode_only:{review_item_id}")
        if item.get("review_risk_tier") != "lower":
            blockers.append(f"review_not_lower_risk:{review_item_id}")
        if item.get("identity_consistency") != "single_source_id_date_location":
            blockers.append(f"review_not_single_source_id_date_location:{review_item_id}")
        if set(string_list(item.get("active_conflicts"))) != {"type"}:
            blockers.append(f"review_has_non_type_conflicts:{review_item_id}")
        if len(string_list(item.get("merge_canonical_event_ids"))) < 2:
            blockers.append(f"review_has_too_few_merge_event_ids:{review_item_id}")
    return sorted(set(blockers))


def build_decision_for_group(
    group: dict[str, Any],
    review_items: dict[str, dict[str, Any]],
    *,
    generated_at: str,
) -> dict[str, Any]:
    review_item_ids = string_list(group.get("review_item_ids"))
    member_items = [review_items[review_item_id] for review_item_id in review_item_ids]
    merge_event_ids = unique_ordered(
        event_id
        for item in member_items
        for event_id in string_list(item.get("merge_canonical_event_ids"))
    )
    canonical_input_ids = unique_ordered(
        input_id
        for item in member_items
        for input_id in string_list(item.get("candidate_canonical_input_ids"))
    )
    group_review_id = stable_hash(
        {
            "review_item_ids": review_item_ids,
            "merge_canonical_event_ids": merge_event_ids,
            "source_names": string_list(group.get("source_names")),
            "source_native_ids": string_list(group.get("source_native_ids")),
            "date_values": string_list(group.get("date_values")),
            "location_values": string_list(group.get("location_values")),
        },
        prefix="er_type_subcode_group_",
        length=20,
    )
    decision_id = stable_hash(
        {
            "group_review_id": group_review_id,
            "decision": "same_event",
            "merge_canonical_event_ids": merge_event_ids,
            "policy": CHECK_POLICY,
        },
        prefix="erdts_",
        length=20,
    )
    return {
        "entity_resolution_decision_id": decision_id,
        "review_item_id": group_review_id,
        "review_type": "entity_resolution_type_subcode_source_review_group_candidate",
        "decision": "same_event",
        "effect_status": "preview_candidate_not_applied",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "requires_explicit_apply_step": True,
        "planned_effect": "merge_entity_resolution_candidate",
        "review_band": "lower_type_subcode_source_review",
        "score": None,
        "confidence": min_confidence(string_list(group.get("confidence_values"))),
        "projected_event_reduction": max(0, len(merge_event_ids) - 1),
        "canonical_input_ids": canonical_input_ids,
        "merge_canonical_event_ids": merge_event_ids,
        "reviewer": "source_review_policy_preview_staging",
        "reviewed_at": generated_at,
        "notes": "Preview-only decision candidate from source-reviewed type-subcode variant group.",
        "source_review_group": {
            "group_rank": group.get("group_rank"),
            "member_count": group.get("member_count"),
            "member_review_item_ids": review_item_ids,
            "member_effect_ids": string_list(group.get("effect_ids")),
            "source_names": string_list(group.get("source_names")),
            "source_native_ids": string_list(group.get("source_native_ids")),
            "date_values": string_list(group.get("date_values")),
            "location_values": string_list(group.get("location_values")),
            "type_values_union": string_list(group.get("type_values_union")),
            "review_recommendations": string_list(group.get("review_recommendations")),
        },
    }


def min_confidence(values: list[str]) -> str | None:
    if not values:
        return None
    order = {"none": 0, "low": 1, "medium": 2, "high": 3}
    return min(values, key=lambda value: order.get(value, 99))


def unique_ordered(values: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = clean_text(value)
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result


def string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [text for item in value if (text := clean_text(item))]
    text = clean_text(value)
    return [text] if text else []


def duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicate_values: set[str] = set()
    for value in values:
        if value in seen:
            duplicate_values.add(value)
        seen.add(value)
    return sorted(duplicate_values)


def count_by(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = clean_text(row.get(field)) or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--groups", type=Path, default=DEFAULT_GROUPS)
    parser.add_argument("--source-review", type=Path, default=DEFAULT_SOURCE_REVIEW)
    parser.add_argument("--decisions-output", type=Path, default=DEFAULT_DECISIONS_OUTPUT)
    parser.add_argument("--check-output", type=Path, default=DEFAULT_CHECK_OUTPUT)
    parser.add_argument("--generated-at", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    decisions, check = build_type_subcode_source_review_decision_candidates(
        groups_report=read_json(args.groups),
        source_review=read_json(args.source_review),
        groups_path=args.groups,
        source_review_path=args.source_review,
        generated_at=args.generated_at,
    )
    check["outputs"] = {
        "decisions": str(args.decisions_output),
        "check": str(args.check_output),
    }
    write_jsonl(args.decisions_output, decisions)
    write_json(args.check_output, check)
    print(
        json.dumps(
            {
                "decisions_output": str(args.decisions_output),
                "check_output": str(args.check_output),
                "valid": check["valid"],
                "decision_candidate_count": check["decision_candidate_count"],
                "projected_event_reduction": check["projected_event_reduction"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if check["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
