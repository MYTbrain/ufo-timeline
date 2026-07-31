"""Build the next review queue for ER type-conflict blockers.

This report starts from the type-conflict blocker analysis and separates
remaining blockers into bounded follow-up lanes. It does not create decisions,
effects, preview outputs, or canonical mutations.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from parser.canonical_schema import clean_text


DEFAULT_ANALYSIS = Path("data/reports/entity_resolution_type_conflict_analysis_worklist.json")
DEFAULT_ALREADY_STAGED = Path(
    "data/reports/entity_resolution_type_subcode_source_review_decision_candidates_worklist.jsonl"
)
DEFAULT_JSON_OUTPUT = Path("data/reports/entity_resolution_type_conflict_next_queue_worklist.json")
DEFAULT_CSV_OUTPUT = Path("data/reports/entity_resolution_type_conflict_next_queue_worklist.csv")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/entity_resolution_type_conflict_next_queue_worklist.md")

ANALYSIS_POLICY = "entity_resolution_cluster_type_conflict_review_only"
REPORT_POLICY = "entity_resolution_type_conflict_next_queue_review_only"


def build_entity_resolution_type_conflict_next_queue(
    *,
    analysis: dict[str, Any],
    already_staged_decisions: list[dict[str, Any]] | None = None,
    analysis_path: Path | None = None,
    already_staged_path: Path | None = None,
) -> dict[str, Any]:
    validate_analysis(analysis)
    staged_review_item_ids = staged_member_review_item_ids(already_staged_decisions or [])
    items = [item for item in analysis.get("items", []) if isinstance(item, dict)]
    remaining = [
        next_queue_item(item)
        for item in items
        if clean_text(item.get("review_item_id")) not in staged_review_item_ids
    ]
    for item in remaining:
        item["next_lane"] = classify_next_lane(item)
        item["next_action"] = next_action_for_lane(item["next_lane"])

    return {
        "schema_version": 1,
        "report_policy": REPORT_POLICY,
        "input_analysis_policy": ANALYSIS_POLICY,
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "inputs": {
            "analysis": str(analysis_path) if analysis_path else None,
            "already_staged_decisions": str(already_staged_path) if already_staged_path else None,
        },
        "summary": {
            "input_item_count": len(items),
            "already_staged_review_item_count": len(staged_review_item_ids),
            "remaining_item_count": len(remaining),
            "next_lane_counts": count_by(remaining, "next_lane"),
            "classification_counts": count_by(remaining, "type_conflict_classification"),
            "risk_tier_counts": count_by(remaining, "review_risk_tier"),
            "identity_consistency_counts": count_by(remaining, "identity_consistency"),
            "projected_reduction_sum_not_deduped": sum(
                int(item.get("projected_event_reduction") or 0) for item in remaining
            ),
        },
        "items": remaining,
        "notes": [
            "This is a review queue only; it intentionally creates no merge decisions.",
            "Staged low-risk type-subcode items are excluded so the remaining queue reflects unresolved blockers.",
            "Cross-family and coordinate-linked type conflicts remain high-risk until stronger source evidence exists.",
        ],
    }


def validate_analysis(analysis: dict[str, Any]) -> None:
    errors: list[str] = []
    if analysis.get("analysis_policy") != ANALYSIS_POLICY:
        errors.append(f"analysis_policy must be {ANALYSIS_POLICY!r}")
    for flag in (
        "canonical_outputs_mutated",
        "preview_outputs_written",
        "decisions_created",
        "decision_outputs_created",
        "auto_merge_performed",
        "ready_for_canonical_apply",
    ):
        if analysis.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError("type-conflict analysis is not safe: " + "; ".join(errors))


def staged_member_review_item_ids(decisions: list[dict[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for decision in decisions:
        source_group = decision.get("source_review_group")
        if not isinstance(source_group, dict):
            continue
        for review_item_id in string_list(source_group.get("member_review_item_ids")):
            ids.add(review_item_id)
    return ids


def next_queue_item(item: dict[str, Any]) -> dict[str, Any]:
    source_summary = item.get("source_summary") if isinstance(item.get("source_summary"), dict) else {}
    return {
        "review_rank": item.get("review_rank"),
        "review_item_id": clean_text(item.get("review_item_id")),
        "effect_id": clean_text(item.get("effect_id")),
        "patch_id": clean_text(item.get("patch_id")),
        "projected_event_reduction": int(item.get("projected_event_reduction") or 0),
        "type_conflict_classification": clean_text(item.get("type_conflict_classification")),
        "review_risk_tier": clean_text(item.get("review_risk_tier")),
        "identity_consistency": clean_text(item.get("identity_consistency")),
        "has_coordinate_risk": bool(item.get("has_coordinate_risk")),
        "blocking_fields": string_list(item.get("blocking_fields")),
        "type_values": string_list(item.get("type_values")),
        "type_family_prefixes": string_list(item.get("type_family_prefixes")),
        "shape_values": string_list(item.get("shape_values")),
        "time_values": string_list(item.get("time_values")),
        "risk_flags": string_list(item.get("risk_flags")),
        "source_names": string_list(source_summary.get("source_names")),
        "source_native_ids": string_list(source_summary.get("source_native_ids")),
        "date_values": string_list(source_summary.get("date_values")),
        "location_values": string_list(source_summary.get("location_values")),
        "canonical_event_ids": string_list(source_summary.get("canonical_event_ids")),
        "canonical_input_ids": string_list(source_summary.get("canonical_input_ids")),
        "recommended_review_step": clean_text(item.get("recommended_review_step")),
    }


def classify_next_lane(item: dict[str, Any]) -> str:
    classification = item.get("type_conflict_classification")
    identity = item.get("identity_consistency")
    risk = item.get("review_risk_tier")
    has_coordinate_risk = bool(item.get("has_coordinate_risk"))
    if classification == "type_only_single_family_subcode_conflict" and risk == "high":
        if identity == "mixed_or_incomplete_identity":
            return "source_row_identity_review"
        return "subcode_policy_review"
    if classification == "type_only_single_family_with_shape_conflict":
        return "shape_type_semantics_review"
    if classification == "type_only_cross_family_conflict":
        return "cross_family_human_review_only"
    if classification == "type_with_coordinate_conflict" or has_coordinate_risk:
        return "coordinate_plus_type_blocked"
    return "manual_triage"


def next_action_for_lane(lane: str) -> str:
    actions = {
        "source_row_identity_review": "Build source-row evidence packets before any decision staging.",
        "subcode_policy_review": "Review subtype-code policy; only stage if source/date/location identity is still strict.",
        "shape_type_semantics_review": "Inspect whether shape labels are compatible observations or true contradictions.",
        "cross_family_human_review_only": "Keep human-review-only unless descriptions/source rows prove one event.",
        "coordinate_plus_type_blocked": "Resolve coordinate conflict first; do not stage a type-only decision.",
        "manual_triage": "Inspect manually before creating any downstream artifact.",
    }
    return actions.get(lane, actions["manual_triage"])


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{path} line {line_number} must be a JSON object.")
            rows.append(payload)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, report: dict[str, Any]) -> None:
    rows = report.get("items") if isinstance(report.get("items"), list) else []
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "review_rank",
        "next_lane",
        "review_risk_tier",
        "type_conflict_classification",
        "identity_consistency",
        "review_item_id",
        "effect_id",
        "projected_event_reduction",
        "type_values",
        "type_family_prefixes",
        "shape_values",
        "risk_flags",
        "source_names",
        "source_native_ids",
        "date_values",
        "location_values",
        "next_action",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field)) for field in fieldnames})


def write_markdown(path: Path, report: dict[str, Any], *, item_limit: int = 40) -> None:
    summary = report.get("summary", {})
    rows = report.get("items") if isinstance(report.get("items"), list) else []
    lines = [
        "# ER Type-Conflict Next Queue",
        "",
        f"- Policy: `{report.get('report_policy')}`",
        f"- Remaining items: {summary.get('remaining_item_count')}",
        f"- Already staged review items excluded: {summary.get('already_staged_review_item_count')}",
        f"- Projected reduction, not deduped: {summary.get('projected_reduction_sum_not_deduped')}",
        f"- Canonical outputs mutated: `{report.get('canonical_outputs_mutated')}`",
        "",
        "## Next Lane Counts",
        "",
    ]
    for lane, count in sorted((summary.get("next_lane_counts") or {}).items()):
        lines.append(f"- `{lane}`: {count}")
    lines.extend(["", "## Review Rows", ""])
    for row in rows[:item_limit]:
        lines.extend(
            [
                f"### {row.get('review_rank')}. {row.get('next_lane')}",
                "",
                f"- Review item: `{row.get('review_item_id')}`",
                f"- Classification: `{row.get('type_conflict_classification')}`",
                f"- Risk / identity: `{row.get('review_risk_tier')}` / `{row.get('identity_consistency')}`",
                f"- Type values: {', '.join(row.get('type_values') or [])}",
                f"- Source/native: {', '.join(row.get('source_names') or [])} / {', '.join(row.get('source_native_ids') or [])}",
                f"- Date: {', '.join(row.get('date_values') or [])}",
                f"- Location: {'; '.join(row.get('location_values') or [])}",
                f"- Next action: {row.get('next_action')}",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [text for item in value if (text := clean_text(item))]
    text = clean_text(value)
    return [text] if text else []


def csv_value(value: Any) -> Any:
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return value


def count_by(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = clean_text(row.get(field)) or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", type=Path, default=DEFAULT_ANALYSIS)
    parser.add_argument("--already-staged", type=Path, default=DEFAULT_ALREADY_STAGED)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument("--markdown-item-limit", type=int, default=40)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_entity_resolution_type_conflict_next_queue(
        analysis=read_json(args.analysis),
        already_staged_decisions=read_jsonl(args.already_staged),
        analysis_path=args.analysis,
        already_staged_path=args.already_staged,
    )
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
                "remaining_item_count": report["summary"]["remaining_item_count"],
                "next_lane_counts": report["summary"]["next_lane_counts"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
