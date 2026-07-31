"""Group source-identity same-event review recommendations.

This is a review-only grouping layer. It consumes the conservative
source-identity review report and groups overlapping same-event recommendations
by shared canonical event IDs. It does not create decisions, effects, previews,
or canonical mutations.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any, Iterable

from parser.canonical_schema import clean_text, stable_hash


DEFAULT_REVIEW = Path("data/reports/entity_resolution_type_conflict_source_identity_review_worklist.json")
DEFAULT_JSON_OUTPUT = Path("data/reports/entity_resolution_type_conflict_source_identity_review_groups_worklist.json")
DEFAULT_CSV_OUTPUT = Path("data/reports/entity_resolution_type_conflict_source_identity_review_groups_worklist.csv")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/entity_resolution_type_conflict_source_identity_review_groups_worklist.md")

INPUT_REVIEW_POLICY = "entity_resolution_type_conflict_source_identity_review_only"
GROUPING_POLICY = "entity_resolution_type_conflict_source_identity_review_groups_report_only"
SAFE_RECOMMENDATION = "source_review_identity_variant_same_event_candidate"
GROUP_RECOMMENDATION = "source_identity_review_group_same_event_candidate"
NEEDS_MORE_EVIDENCE = "needs_more_evidence"


def group_type_conflict_source_identity_review_candidates(
    *,
    review: dict[str, Any],
    review_path: Path | None = None,
) -> dict[str, Any]:
    validate_review_safety(review)
    items = [item for item in review.get("items") or [] if isinstance(item, dict)]
    safe_items = [item for item in items if clean_text(item.get("review_recommendation")) == SAFE_RECOMMENDATION]
    blocked_items = [blocked_review_item(item) for item in items if item not in safe_items]
    groups = build_groups(safe_items)
    for index, group in enumerate(groups, start=1):
        group["group_rank"] = index

    projected_reduction = sum(int(group.get("projected_event_reduction") or 0) for group in groups)
    return {
        "schema_version": 1,
        "grouping_policy": GROUPING_POLICY,
        "input_review_policy": review.get("review_policy"),
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "validated_decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "inputs": {
            "review": str(review_path) if review_path else None,
        },
        "summary": {
            "input_review_item_count": len(items),
            "safe_recommendation_item_count": len(safe_items),
            "blocked_or_needs_more_evidence_item_count": len(blocked_items),
            "group_count": len(groups),
            "ready_group_count": sum(1 for group in groups if group.get("ready_for_decision_staging") is True),
            "group_recommendation_counts": count_by(groups, "group_recommendation"),
            "projected_event_reduction": projected_reduction,
            "blocked_item_recommendation_counts": count_by(blocked_items, "review_recommendation"),
        },
        "groups": groups,
        "blocked_or_needs_more_evidence_items": blocked_items,
        "notes": [
            "This grouping report is review-only.",
            "It groups only already-recommended source-identity same-event candidates.",
            "Connected groups are formed by overlapping merge_canonical_event_ids.",
            "No canonical event corpus is mutated by this script.",
        ],
    }


def validate_review_safety(review: dict[str, Any]) -> None:
    errors: list[str] = []
    if review.get("review_policy") != INPUT_REVIEW_POLICY:
        errors.append(f"review_policy must be {INPUT_REVIEW_POLICY!r}")
    for flag in (
        "canonical_outputs_mutated",
        "preview_outputs_written",
        "decisions_created",
        "decision_outputs_created",
        "validated_decisions_created",
        "auto_merge_performed",
        "ready_for_canonical_apply",
    ):
        if review.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError("source-identity review report is unsafe for grouping: " + "; ".join(errors))


def build_groups(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    parent: dict[str, str] = {}
    event_to_indices: dict[str, set[int]] = {}

    for index, item in enumerate(items):
        event_ids = string_list(item.get("merge_canonical_event_ids"))
        for event_id in event_ids:
            parent.setdefault(event_id, event_id)
            event_to_indices.setdefault(event_id, set()).add(index)
        for event_id in event_ids[1:]:
            union(parent, event_ids[0], event_id)

    root_to_indices: dict[str, set[int]] = {}
    for event_id, indices in event_to_indices.items():
        root_to_indices.setdefault(find(parent, event_id), set()).update(indices)

    groups = [group_from_items([items[index] for index in sorted(indices)]) for indices in root_to_indices.values()]
    return sorted(
        groups,
        key=lambda group: (
            min(int(rank) for rank in numeric_values(group.get("member_review_ranks"))) if group.get("member_review_ranks") else 0,
            string_list(group.get("source_names")),
            string_list(group.get("dates")),
            string_list(group.get("source_native_ids")),
        ),
    )


def group_from_items(items: list[dict[str, Any]]) -> dict[str, Any]:
    review_item_ids = unique_ordered(item.get("review_item_id") for item in items)
    merge_event_ids = unique_ordered(
        event_id for item in items for event_id in string_list(item.get("merge_canonical_event_ids"))
    )
    input_ids = unique_ordered(
        input_id for item in items for input_id in string_list(item.get("candidate_canonical_input_ids"))
    )
    blockers = group_blockers(items, merge_event_ids)
    group_id = stable_hash(
        {
            "review_item_ids": review_item_ids,
            "merge_canonical_event_ids": merge_event_ids,
            "policy": GROUPING_POLICY,
        },
        prefix="er_src_identity_group_",
        length=20,
    )
    location_values = unique_ordered(location for item in items for location in string_list(item.get("locations")))
    return {
        "group_rank": None,
        "group_id": group_id,
        "group_recommendation": GROUP_RECOMMENDATION if not blockers else NEEDS_MORE_EVIDENCE,
        "ready_for_decision_staging": not blockers,
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "member_count": len(items),
        "member_review_ranks": [item.get("review_rank") for item in items],
        "review_item_ids": review_item_ids,
        "effect_ids": unique_ordered(item.get("effect_id") for item in items),
        "review_recommendations": unique_ordered(item.get("review_recommendation") for item in items),
        "confidence_values": unique_ordered(item.get("confidence") for item in items),
        "source_names": unique_ordered(source for item in items for source in string_list(item.get("source_names"))),
        "source_native_ids": unique_ordered(
            source_id for item in items for source_id in string_list(item.get("source_native_ids"))
        ),
        "dates": unique_ordered(date for item in items for date in string_list(item.get("dates"))),
        "times": unique_ordered(time for item in items for time in string_list(item.get("times"))),
        "locations": location_values,
        "location_family_values": unique_ordered(normalize_location_family(value) for value in location_values),
        "coordinate_values": unique_ordered(
            coordinate for item in items for coordinate in string_list(item.get("coordinate_values"))
        ),
        "type_values": unique_ordered(type_value for item in items for type_value in string_list(item.get("type_values"))),
        "type_family_prefixes": unique_ordered(
            family for item in items for family in string_list(item.get("type_family_prefixes"))
        ),
        "active_conflicts": unique_ordered(
            conflict for item in items for conflict in string_list(item.get("active_conflicts"))
        ),
        "failed_conditions": unique_ordered(
            condition for item in items for condition in string_list(item.get("failed_conditions"))
        ),
        "review_reason_codes": unique_ordered(
            reason for item in items for reason in string_list(item.get("review_reason_codes"))
        ),
        "merge_canonical_event_ids": merge_event_ids,
        "canonical_input_ids": input_ids,
        "projected_event_reduction": max(0, len(merge_event_ids) - 1),
        "group_blockers": blockers,
        "notes": (
            "Connected source-identity review recommendations are consistent enough for later decision staging."
            if not blockers
            else "Connected review recommendations need additional evidence before decision staging."
        ),
    }


def group_blockers(items: list[dict[str, Any]], merge_event_ids: list[str]) -> list[str]:
    blockers: list[str] = []
    if len(merge_event_ids) < 2:
        blockers.append("too_few_merge_event_ids")
    if any(clean_text(item.get("review_recommendation")) != SAFE_RECOMMENDATION for item in items):
        blockers.append("contains_non_same_event_recommendation")
    if any(string_list(item.get("failed_conditions")) for item in items):
        blockers.append("member_failed_conditions_present")
    if len(unique_ordered(source for item in items for source in string_list(item.get("source_names")))) != 1:
        blockers.append("requires_single_source")
    if len(unique_ordered(source_id for item in items for source_id in string_list(item.get("source_native_ids")))) != 1:
        blockers.append("requires_single_source_native_id")
    if len(unique_ordered(date for item in items for date in string_list(item.get("dates")))) != 1:
        blockers.append("requires_single_exact_date")
    if len(unique_ordered(family for item in items for family in string_list(item.get("type_family_prefixes")))) != 1:
        blockers.append("requires_single_type_family")
    return sorted(set(blockers))


def blocked_review_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "review_rank": item.get("review_rank"),
        "review_item_id": clean_text(item.get("review_item_id")),
        "effect_id": clean_text(item.get("effect_id")),
        "review_recommendation": clean_text(item.get("review_recommendation")),
        "confidence": clean_text(item.get("confidence")),
        "failed_conditions": string_list(item.get("failed_conditions")),
        "source_names": string_list(item.get("source_names")),
        "source_native_ids": string_list(item.get("source_native_ids")),
        "dates": string_list(item.get("dates")),
        "locations": string_list(item.get("locations")),
        "merge_canonical_event_ids": string_list(item.get("merge_canonical_event_ids")),
        "reason": "not_grouped_because_not_safe_same_event_recommendation",
    }


def find(parent: dict[str, str], node: str) -> str:
    parent.setdefault(node, node)
    if parent[node] != node:
        parent[node] = find(parent, parent[node])
    return parent[node]


def union(parent: dict[str, str], left: str, right: str) -> None:
    left_root = find(parent, left)
    right_root = find(parent, right)
    if left_root != right_root:
        parent[right_root] = left_root


def normalize_location_family(value: Any) -> str:
    text = clean_text(value).lower()
    if not text:
        return ""
    primary = text.split(",", 1)[0]
    primary = re.sub(r"[^a-z0-9]+", " ", primary)
    return re.sub(r"\s+", " ", primary).strip()


def unique_ordered(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = clean_text(value)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [text for item in value if (text := clean_text(item))]
    text = clean_text(value)
    return [text] if text else []


def numeric_values(value: Any) -> list[int]:
    result = []
    for item in value or []:
        try:
            result.append(int(item))
        except (TypeError, ValueError):
            continue
    return result


def count_by(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = clean_text(row.get(field)) or "unknown"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


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
        "group_rank",
        "group_recommendation",
        "ready_for_decision_staging",
        "group_id",
        "member_count",
        "projected_event_reduction",
        "review_item_ids",
        "effect_ids",
        "source_names",
        "source_native_ids",
        "dates",
        "times",
        "location_family_values",
        "locations",
        "type_values",
        "type_family_prefixes",
        "active_conflicts",
        "group_blockers",
        "merge_canonical_event_ids",
        "canonical_input_ids",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for group in report.get("groups") or []:
            writer.writerow({field: csv_value(group.get(field)) for field in fieldnames})


def write_markdown(path: Path, report: dict[str, Any], *, group_limit: int) -> None:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    lines = [
        "# Type-Conflict Source Identity Review Groups",
        "",
        "This report is review-only. It groups source-identity same-event recommendations by overlapping canonical event IDs.",
        "",
        "## Summary",
        "",
        f"- Input review items: `{summary.get('input_review_item_count', 0)}`",
        f"- Safe recommendation items: `{summary.get('safe_recommendation_item_count', 0)}`",
        f"- Blocked / needs-more-evidence items: `{summary.get('blocked_or_needs_more_evidence_item_count', 0)}`",
        f"- Groups: `{summary.get('group_count', 0)}`",
        f"- Ready groups: `{summary.get('ready_group_count', 0)}`",
        f"- Projected event reduction: `{summary.get('projected_event_reduction', 0)}`",
        f"- Canonical outputs mutated: `{str(report.get('canonical_outputs_mutated')).lower()}`",
        "",
        "## Groups",
        "",
    ]
    groups = [group for group in report.get("groups") or [] if isinstance(group, dict)]
    for group in groups[: max(0, group_limit)]:
        lines.extend(markdown_group_lines(group))
    if len(groups) > group_limit:
        lines.extend(["", f"_Markdown limited to {group_limit} of {len(groups)} groups._", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def markdown_group_lines(group: dict[str, Any]) -> list[str]:
    return [
        f"### {group.get('group_rank')}. {group.get('group_recommendation')}",
        "",
        f"- Group ID: `{group.get('group_id')}`",
        f"- Ready for decision staging: `{str(group.get('ready_for_decision_staging')).lower()}`",
        f"- Member review items: {', '.join(string_list(group.get('review_item_ids')))}",
        f"- Projected reduction: `{group.get('projected_event_reduction')}`",
        f"- Source/native/date/time: {', '.join(string_list(group.get('source_names')))} / {', '.join(string_list(group.get('source_native_ids')))} / {', '.join(string_list(group.get('dates')))} / {', '.join(string_list(group.get('times'))) or 'none'}",
        f"- Location families: {', '.join(string_list(group.get('location_family_values'))) or 'none'}",
        f"- Locations: {'; '.join(string_list(group.get('locations'))) or 'none'}",
        f"- Type values: {', '.join(string_list(group.get('type_values'))) or 'none'}",
        f"- Active conflicts: {', '.join(string_list(group.get('active_conflicts'))) or 'none'}",
        f"- Group blockers: {', '.join(string_list(group.get('group_blockers'))) or 'none'}",
        f"- Merge canonical events: {', '.join(string_list(group.get('merge_canonical_event_ids')))}",
        "",
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument("--markdown-group-limit", type=int, default=80)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = group_type_conflict_source_identity_review_candidates(
        review=read_json(args.review),
        review_path=args.review,
    )
    report["outputs"] = {
        "json": str(args.json_output),
        "csv": str(args.csv_output),
        "markdown": str(args.markdown_output),
    }
    write_json(args.json_output, report)
    write_csv(args.csv_output, report)
    write_markdown(args.markdown_output, report, group_limit=args.markdown_group_limit)
    print(
        json.dumps(
            {
                "json_output": str(args.json_output),
                "csv_output": str(args.csv_output),
                "markdown_output": str(args.markdown_output),
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
