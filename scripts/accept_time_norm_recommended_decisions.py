"""Accept proven clean time-normalization decision candidates.

This script is intentionally non-destructive. It promotes only the already
previewed, low-risk recommended time-normalization candidates into a separate
accepted decision artifact. It does not apply merges or rewrite canonical
events.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from parser.canonical_schema import clean_text


DEFAULT_DECISION_CANDIDATES = Path("data/reports/entity_resolution_cluster_time_norm_recommended_decision_candidates.jsonl")
DEFAULT_DECISION_CANDIDATE_REPORT = Path(
    "data/reports/entity_resolution_cluster_time_norm_recommended_decision_candidates_report.json"
)
DEFAULT_POLICY_CONFLICT_CLASSIFICATION = Path(
    "data/reports/entity_resolution_cluster_time_norm_recommended_policy_conflict_classification.json"
)
DEFAULT_CANONICAL_APPLY_CONTRACT_CHECK = Path(
    "data/reports/entity_resolution_cluster_time_norm_recommended_canonical_apply_contract_check.json"
)
DEFAULT_CANONICAL_BODY_DRY_RUN_CHECK = Path(
    "data/reports/entity_resolution_cluster_time_norm_recommended_canonical_body_dry_run_check.json"
)
DEFAULT_ACCEPTED_DECISIONS_OUTPUT = Path(
    "data/canonical_full/entity_resolution_cluster_time_norm_recommended_accepted_decisions.jsonl"
)
DEFAULT_REPORT_OUTPUT = Path("data/reports/entity_resolution_cluster_time_norm_recommended_acceptance_report.json")

INPUT_PROMOTION_POLICY = "entity_resolution_time_norm_recommended_decision_candidates_only"
POLICY_CONFLICT_CLASSIFICATION = "entity_resolution_time_norm_recommended_policy_conflict_classification_only"
CONTRACT_POLICY = "entity_resolution_time_norm_recommended_canonical_apply_contract_check"
DRY_RUN_CHECK_POLICY = "entity_resolution_time_norm_recommended_canonical_body_dry_run_check"
ACCEPTANCE_POLICY = "entity_resolution_time_norm_recommended_policy_acceptance_v1"
DEFAULT_REVIEWER = "codex_time_norm_policy_acceptance_v1"


def accept_time_norm_recommended_decisions(
    *,
    decision_candidates: list[dict[str, Any]],
    decision_candidate_report: dict[str, Any],
    policy_conflict_classification: dict[str, Any],
    canonical_apply_contract_check: dict[str, Any],
    canonical_body_dry_run_check: dict[str, Any],
    reviewer: str = DEFAULT_REVIEWER,
    accepted_at: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    validate_candidate_report(decision_candidate_report, expected_count=len(decision_candidates))
    accepted_review_item_ids = validate_policy_conflict_classification(
        policy_conflict_classification,
        expected_count=len(decision_candidates),
    )
    validate_canonical_apply_contract(canonical_apply_contract_check, expected_count=len(decision_candidates))
    validate_canonical_body_dry_run_check(canonical_body_dry_run_check, expected_count=len(decision_candidates))

    timestamp = accepted_at or datetime.now(UTC).replace(microsecond=0).isoformat()
    accepted_decisions: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    seen_decision_ids: set[str] = set()
    seen_review_item_ids: set[str] = set()
    for decision_index, candidate in enumerate(decision_candidates, start=1):
        decision_id = clean_text(candidate.get("entity_resolution_decision_id"))
        review_item_id = clean_text(candidate.get("review_item_id"))
        if not decision_id:
            invalid.append({"decision_index": decision_index, "error": "missing_entity_resolution_decision_id"})
            continue
        if decision_id in seen_decision_ids:
            invalid.append({"decision_index": decision_index, "decision_id": decision_id, "error": "duplicate_decision_id"})
            continue
        seen_decision_ids.add(decision_id)
        if not review_item_id:
            invalid.append({"decision_index": decision_index, "decision_id": decision_id, "error": "missing_review_item_id"})
            continue
        if review_item_id in seen_review_item_ids:
            invalid.append(
                {
                    "decision_index": decision_index,
                    "review_item_id": review_item_id,
                    "error": "duplicate_review_item_id",
                }
            )
            continue
        seen_review_item_ids.add(review_item_id)
        if review_item_id not in accepted_review_item_ids:
            invalid.append(
                {
                    "decision_index": decision_index,
                    "review_item_id": review_item_id,
                    "error": "review_item_missing_from_policy_conflict_acceptance_set",
                }
            )
            continue
        candidate_error = validate_decision_candidate(candidate)
        if candidate_error:
            invalid.append({"decision_index": decision_index, "review_item_id": review_item_id, "error": candidate_error})
            continue
        accepted_decisions.append(accepted_decision_from_candidate(candidate, reviewer=reviewer, accepted_at=timestamp))

    if invalid:
        raise ValueError("decision candidates are unsafe for policy acceptance: " + json.dumps(invalid[:5], ensure_ascii=False))

    report = {
        "schema_version": 1,
        "acceptance_policy": ACCEPTANCE_POLICY,
        "input_promotion_policy": decision_candidate_report.get("promotion_policy"),
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": True,
        "accepted_canonical_decisions_created": True,
        "validated_decisions_created": True,
        "canonical_apply_performed": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "decision_candidate_count": len(decision_candidates),
        "accepted_decision_count": len(accepted_decisions),
        "skipped_decision_candidate_count": 0,
        "projected_event_reduction": int(decision_candidate_report.get("projected_event_reduction") or 0),
        "policy_conflict_apply_candidate_count": int(
            ((policy_conflict_classification.get("summary") or {}).get("apply_policy_candidate_count") or 0)
        ),
        "policy_conflict_blocking_preview_count": int(
            ((policy_conflict_classification.get("summary") or {}).get("blocking_preview_count") or 0)
        ),
        "canonical_apply_contract_valid": bool(canonical_apply_contract_check.get("contract_valid") is True),
        "canonical_body_dry_run_valid": bool(canonical_body_dry_run_check.get("valid") is True),
        "canonical_body_dry_run_row_count": int(canonical_body_dry_run_check.get("dry_run_row_count") or 0),
        "reviewer": reviewer,
        "accepted_at": timestamp,
        "notes": [
            "Accepted decisions are policy-gated from the clean time-normalization lane only.",
            "This artifact creates accepted decision records but does not apply merges or rewrite canonical events.",
            "Canonical apply remains blocked until an explicit stream-safe corpus rewrite command exists.",
        ],
    }
    return accepted_decisions, report


def accepted_decision_from_candidate(candidate: dict[str, Any], *, reviewer: str, accepted_at: str) -> dict[str, Any]:
    accepted = dict(candidate)
    accepted["effect_status"] = "accepted_not_applied"
    accepted["acceptance_policy"] = ACCEPTANCE_POLICY
    accepted["accepted_canonical_decision"] = True
    accepted["accepted_at"] = accepted_at
    accepted["accepted_by"] = reviewer
    accepted["requires_explicit_apply_step"] = True
    accepted["canonical_outputs_mutated"] = False
    accepted["decision_source"] = ACCEPTANCE_POLICY
    accepted["notes"] = append_note(
        accepted.get("notes"),
        "Policy-accepted after low-risk conflict classification, valid full-row contract check, and valid canonical-body dry-run check.",
    )
    return accepted


def validate_candidate_report(report: dict[str, Any], *, expected_count: int) -> None:
    errors: list[str] = []
    if report.get("promotion_policy") != INPUT_PROMOTION_POLICY:
        errors.append(f"promotion_policy must be {INPUT_PROMOTION_POLICY}")
    if int(report.get("decision_candidate_count") or 0) != expected_count:
        errors.append("decision_candidate_count must match the decision candidate file")
    if int(report.get("skipped_recommendation_count") or 0) != 11:
        errors.append("skipped_recommendation_count must remain 11 for the deferred source-review cases")
    for flag in (
        "canonical_outputs_mutated",
        "preview_outputs_written",
        "canonical_apply_performed",
        "auto_merge_performed",
        "accepted_canonical_decisions_created",
        "ready_for_canonical_apply",
    ):
        if report.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError("decision candidate report is unsafe for policy acceptance: " + "; ".join(errors))


def validate_policy_conflict_classification(payload: dict[str, Any], *, expected_count: int) -> set[str]:
    errors: list[str] = []
    if payload.get("classification_policy") != POLICY_CONFLICT_CLASSIFICATION:
        errors.append(f"classification_policy must be {POLICY_CONFLICT_CLASSIFICATION}")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "decisions_created", "auto_merge_performed", "ready_for_canonical_apply"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    if int(summary.get("apply_policy_candidate_count") or 0) != expected_count:
        errors.append("apply_policy_candidate_count must match decision candidates")
    if int(summary.get("blocking_preview_count") or 0) != 0:
        errors.append("blocking_preview_count must be 0")
    items = [item for item in payload.get("items") or [] if isinstance(item, dict)]
    accepted_review_item_ids: set[str] = set()
    for item in items:
        review_item_id = clean_text(item.get("review_item_id"))
        if not review_item_id:
            errors.append("policy conflict item missing review_item_id")
            continue
        if clean_text(item.get("policy_action")) != "candidate_for_final_policy_after_decision_acceptance":
            errors.append(f"{review_item_id} is not a final-policy candidate")
        if item.get("blockers"):
            errors.append(f"{review_item_id} has policy conflict blockers")
        if clean_text(item.get("risk_tier")) != "low":
            errors.append(f"{review_item_id} is not low risk")
        accepted_review_item_ids.add(review_item_id)
    if len(accepted_review_item_ids) != expected_count:
        errors.append("policy conflict accepted review-item count must match decision candidates")
    if errors:
        raise ValueError("policy conflict classification is unsafe for policy acceptance: " + "; ".join(errors))
    return accepted_review_item_ids


def validate_canonical_apply_contract(payload: dict[str, Any], *, expected_count: int) -> None:
    errors: list[str] = []
    if payload.get("contract_policy") != CONTRACT_POLICY:
        errors.append(f"contract_policy must be {CONTRACT_POLICY}")
    if payload.get("contract_valid") is not True:
        errors.append("contract_valid must be true")
    if int(payload.get("validation_error_count") or 0) != 0:
        errors.append("validation_error_count must be 0")
    if int(payload.get("effect_count") or 0) != expected_count:
        errors.append("effect_count must match decision candidates")
    if int(payload.get("merge_patch_count") or 0) != expected_count:
        errors.append("merge_patch_count must match decision candidates")
    for list_field in (
        "missing_touched_event_ids",
        "suppressed_event_ids_present_in_preview",
        "replacement_event_ids_missing_from_preview",
    ):
        if payload.get(list_field):
            errors.append(f"{list_field} must be empty")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "decisions_created", "auto_merge_performed", "ready_for_canonical_apply"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError("canonical apply contract check is unsafe for policy acceptance: " + "; ".join(errors))


def validate_canonical_body_dry_run_check(payload: dict[str, Any], *, expected_count: int) -> None:
    errors: list[str] = []
    if payload.get("check_policy") != DRY_RUN_CHECK_POLICY:
        errors.append(f"check_policy must be {DRY_RUN_CHECK_POLICY}")
    if payload.get("valid") is not True:
        errors.append("valid must be true")
    if int(payload.get("dry_run_row_count") or 0) != expected_count:
        errors.append("dry_run_row_count must match decision candidates")
    if int(payload.get("validation_error_count") or 0) != 0:
        errors.append("validation_error_count must be 0")
    if int(payload.get("incomplete_conflict_source_value_count") or 0) != 0:
        errors.append("incomplete_conflict_source_value_count must be 0")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "decisions_created", "auto_merge_performed", "ready_for_canonical_apply"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError("canonical body dry-run check is unsafe for policy acceptance: " + "; ".join(errors))


def validate_decision_candidate(candidate: dict[str, Any]) -> str | None:
    if clean_text(candidate.get("decision")) != "same_event":
        return "decision_must_be_same_event"
    if clean_text(candidate.get("effect_status")) != "recommended_candidate_not_applied":
        return "effect_status_must_be_recommended_candidate_not_applied"
    if clean_text(candidate.get("promotion_policy")) != INPUT_PROMOTION_POLICY:
        return "promotion_policy_must_match_recommended_candidate_policy"
    if candidate.get("canonical_outputs_mutated") is not False:
        return "canonical_outputs_mutated_must_be_false"
    if candidate.get("requires_explicit_apply_step") is not True:
        return "requires_explicit_apply_step_must_be_true"
    if len(string_list(candidate.get("merge_canonical_event_ids"))) < 2:
        return "merge_canonical_event_ids_must_include_at_least_two_events"
    return None


def append_note(current: Any, addition: str) -> str:
    current_text = clean_text(current)
    if not current_text:
        return addition
    return f"{current_text} {addition}"


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{path} line {line_number} must contain a JSON object.")
            records.append(payload)
    return records


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [text for item in value if (text := clean_text(item))]
    text = clean_text(value)
    return [text] if text else []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decision-candidates", type=Path, default=DEFAULT_DECISION_CANDIDATES)
    parser.add_argument("--decision-candidate-report", type=Path, default=DEFAULT_DECISION_CANDIDATE_REPORT)
    parser.add_argument("--policy-conflict-classification", type=Path, default=DEFAULT_POLICY_CONFLICT_CLASSIFICATION)
    parser.add_argument("--canonical-apply-contract-check", type=Path, default=DEFAULT_CANONICAL_APPLY_CONTRACT_CHECK)
    parser.add_argument("--canonical-body-dry-run-check", type=Path, default=DEFAULT_CANONICAL_BODY_DRY_RUN_CHECK)
    parser.add_argument("--accepted-decisions-output", type=Path, default=DEFAULT_ACCEPTED_DECISIONS_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    parser.add_argument("--reviewer", default=DEFAULT_REVIEWER)
    parser.add_argument("--accepted-at", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    accepted_decisions, report = accept_time_norm_recommended_decisions(
        decision_candidates=read_jsonl(args.decision_candidates),
        decision_candidate_report=read_json(args.decision_candidate_report),
        policy_conflict_classification=read_json(args.policy_conflict_classification),
        canonical_apply_contract_check=read_json(args.canonical_apply_contract_check),
        canonical_body_dry_run_check=read_json(args.canonical_body_dry_run_check),
        reviewer=args.reviewer,
        accepted_at=args.accepted_at,
    )
    report["inputs"] = {
        "decision_candidates": str(args.decision_candidates),
        "decision_candidate_report": str(args.decision_candidate_report),
        "policy_conflict_classification": str(args.policy_conflict_classification),
        "canonical_apply_contract_check": str(args.canonical_apply_contract_check),
        "canonical_body_dry_run_check": str(args.canonical_body_dry_run_check),
    }
    report["outputs"] = {
        "accepted_decisions": str(args.accepted_decisions_output),
        "report": str(args.report_output),
    }
    write_jsonl(args.accepted_decisions_output, accepted_decisions)
    write_json(args.report_output, report)
    print(
        json.dumps(
            {
                "accepted_decisions": str(args.accepted_decisions_output),
                "report": str(args.report_output),
                "accepted_decision_count": report["accepted_decision_count"],
                "projected_event_reduction": report["projected_event_reduction"],
                "canonical_outputs_mutated": False,
                "ready_for_canonical_apply": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
