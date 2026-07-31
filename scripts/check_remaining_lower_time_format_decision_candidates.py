"""Check the remaining lower time-format decision-candidate gate.

This is an audit-only checker. It validates that the candidate JSONL matches
the source review/report and does not overlap already accepted combined
time-normalization decisions. It does not accept decisions or apply merges.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from parser.canonical_schema import clean_text


DEFAULT_REVIEW = Path("data/reports/entity_resolution_remaining_lower_time_format_review.json")
DEFAULT_CANDIDATES = Path("data/reports/entity_resolution_remaining_lower_time_format_decision_candidates.jsonl")
DEFAULT_CANDIDATE_REPORT = Path("data/reports/entity_resolution_remaining_lower_time_format_decision_candidates_report.json")
DEFAULT_ACCEPTED_DECISIONS = Path(
    "data/canonical_full/entity_resolution_cluster_time_norm_combined_plus_likely_plus_single_exact_context_accepted_decisions.jsonl"
)
DEFAULT_OUTPUT = Path("data/reports/entity_resolution_remaining_lower_time_format_decision_candidates_check.json")

REVIEW_POLICY = "entity_resolution_remaining_lower_time_format_source_review_only"
PROMOTION_POLICY = "entity_resolution_remaining_lower_time_format_decision_candidates_only"
SOURCE_REVIEW_SAME_EVENT = "source_review_same_event_candidate"


def check_remaining_lower_time_format_decision_candidates(
    *,
    review: dict[str, Any],
    candidates: list[dict[str, Any]],
    candidate_report: dict[str, Any],
    accepted_decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    review_items = [item for item in review.get("items") or [] if isinstance(item, dict)]
    source_candidate_items = [
        item
        for item in review_items
        if clean_text(item.get("review_recommendation")) == SOURCE_REVIEW_SAME_EVENT
        and not string_list(item.get("failed_conditions"))
    ]
    deferred_items = [
        item
        for item in review_items
        if clean_text(item.get("review_recommendation")) != SOURCE_REVIEW_SAME_EVENT
        or string_list(item.get("failed_conditions"))
    ]
    candidate_review_ids = {clean_text(item.get("review_item_id")) for item in candidates}
    expected_review_ids = {clean_text(item.get("review_item_id")) for item in source_candidate_items}
    deferred_review_ids = {clean_text(item.get("review_item_id")) for item in deferred_items}
    accepted_review_ids = {clean_text(item.get("review_item_id")) for item in accepted_decisions}
    accepted_merge_sets = {tuple(sorted(string_list(item.get("merge_canonical_event_ids")))) for item in accepted_decisions}
    candidate_merge_sets = {tuple(sorted(string_list(item.get("merge_canonical_event_ids")))) for item in candidates}

    errors: list[str] = []
    if review.get("review_policy") != REVIEW_POLICY:
        errors.append(f"review_policy must be {REVIEW_POLICY}")
    if candidate_report.get("promotion_policy") != PROMOTION_POLICY:
        errors.append(f"promotion_policy must be {PROMOTION_POLICY}")
    for label, payload in (("review", review), ("candidate_report", candidate_report)):
        for flag in (
            "canonical_outputs_mutated",
            "preview_outputs_written",
            "auto_merge_performed",
            "ready_for_canonical_apply",
        ):
            if payload.get(flag) is not False:
                errors.append(f"{label}.{flag} must be false")
    if candidate_report.get("accepted_canonical_decisions_created") is not False:
        errors.append("candidate_report.accepted_canonical_decisions_created must be false")
    if candidate_report.get("canonical_apply_performed") is not False:
        errors.append("candidate_report.canonical_apply_performed must be false")
    if int(candidate_report.get("decision_candidate_count") or 0) != len(candidates):
        errors.append("candidate report decision_candidate_count does not match candidate JSONL rows")
    if int(candidate_report.get("skipped_review_item_count") or 0) != len(deferred_items):
        errors.append("candidate report skipped_review_item_count does not match deferred review rows")
    if candidate_review_ids != expected_review_ids:
        errors.append("candidate review_item_id set does not match source-reviewed same-event rows")
    if candidate_review_ids & deferred_review_ids:
        errors.append("candidate JSONL includes deferred review rows")
    if candidate_review_ids & accepted_review_ids:
        errors.append("candidate JSONL overlaps already accepted combined decisions by review_item_id")
    if candidate_merge_sets & accepted_merge_sets:
        errors.append("candidate JSONL overlaps already accepted combined decisions by merge event set")
    if any(clean_text(candidate.get("promotion_policy")) != PROMOTION_POLICY for candidate in candidates):
        errors.append("all candidate records must use the remaining-lower promotion policy")
    if any(candidate.get("canonical_outputs_mutated") is not False for candidate in candidates):
        errors.append("all candidate records must keep canonical_outputs_mutated=false")
    projected_reduction = sum(max(0, len(string_list(candidate.get("merge_canonical_event_ids"))) - 1) for candidate in candidates)
    if int(candidate_report.get("projected_event_reduction") or 0) != projected_reduction:
        errors.append("candidate report projected_event_reduction does not match candidate merge sets")

    return {
        "schema_version": 1,
        "check_policy": "entity_resolution_remaining_lower_time_format_decision_candidate_check",
        "valid": not errors,
        "errors": errors,
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "accepted_canonical_decisions_created": False,
        "canonical_apply_performed": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "review_item_count": len(review_items),
        "expected_source_candidate_count": len(source_candidate_items),
        "deferred_review_item_count": len(deferred_items),
        "decision_candidate_count": len(candidates),
        "projected_event_reduction": projected_reduction,
        "accepted_decision_count_checked": len(accepted_decisions),
        "overlap_with_accepted_review_ids": sorted(candidate_review_ids & accepted_review_ids),
        "overlap_with_deferred_review_ids": sorted(candidate_review_ids & deferred_review_ids),
        "notes": [
            "This check validates the remaining lower time-format candidate gate only.",
            "It does not accept, apply, or stream-apply these candidates.",
            "A valid check still leaves ready_for_canonical_apply=false.",
        ],
    }


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                payload = json.loads(line)
                if isinstance(payload, dict):
                    rows.append(payload)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [text for item in value if (text := clean_text(item))]
    text = clean_text(value)
    return [text] if text else []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--candidate-report", type=Path, default=DEFAULT_CANDIDATE_REPORT)
    parser.add_argument("--accepted-decisions", type=Path, default=DEFAULT_ACCEPTED_DECISIONS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = check_remaining_lower_time_format_decision_candidates(
        review=read_json(args.review),
        candidates=read_jsonl(args.candidates),
        candidate_report=read_json(args.candidate_report),
        accepted_decisions=read_jsonl(args.accepted_decisions),
    )
    report["inputs"] = {
        "review": str(args.review),
        "candidates": str(args.candidates),
        "candidate_report": str(args.candidate_report),
        "accepted_decisions": str(args.accepted_decisions),
    }
    report["outputs"] = {"check": str(args.output)}
    write_json(args.output, report)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "valid": report["valid"],
                "decision_candidate_count": report["decision_candidate_count"],
                "projected_event_reduction": report["projected_event_reduction"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
