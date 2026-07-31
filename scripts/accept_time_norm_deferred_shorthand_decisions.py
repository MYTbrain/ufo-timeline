"""Accept source-reviewed deferred shorthand time-normalization candidates.

This creates accepted decision records for the narrow deferred-shorthand lane
only after preview output and canonical-body dry-run checks are valid. It does
not apply merges or rewrite canonical event outputs.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from parser.canonical_schema import clean_text


DEFAULT_DECISION_CANDIDATES = Path(
    "data/reports/entity_resolution_cluster_time_norm_deferred_shorthand_decision_candidates.jsonl"
)
DEFAULT_DECISION_CANDIDATE_REPORT = Path(
    "data/reports/entity_resolution_cluster_time_norm_deferred_shorthand_decision_candidates_report.json"
)
DEFAULT_PREVIEW_REPORT = Path("data/reports/entity_resolution_cluster_time_norm_deferred_shorthand_preview_apply_report.json")
DEFAULT_PREVIEW_OUTPUT_CHECK = Path(
    "data/reports/entity_resolution_cluster_time_norm_deferred_shorthand_preview_output_check.json"
)
DEFAULT_CANONICAL_BODY_DRY_RUN_CHECK = Path(
    "data/reports/entity_resolution_cluster_time_norm_deferred_shorthand_canonical_body_dry_run_check.json"
)
DEFAULT_ACCEPTED_DECISIONS_OUTPUT = Path(
    "data/canonical_full/entity_resolution_cluster_time_norm_deferred_shorthand_accepted_decisions.jsonl"
)
DEFAULT_REPORT_OUTPUT = Path("data/reports/entity_resolution_cluster_time_norm_deferred_shorthand_acceptance_report.json")

INPUT_PROMOTION_POLICY = "entity_resolution_time_norm_deferred_shorthand_decision_candidates_only"
PREVIEW_APPLY_POLICY = "entity_resolution_stream_preview_only"
PREVIEW_OUTPUT_CHECK_POLICY = "entity_resolution_shadow_preview_output_check"
DRY_RUN_CHECK_POLICY = "entity_resolution_time_norm_recommended_canonical_body_dry_run_check"
ACCEPTANCE_POLICY = "entity_resolution_time_norm_deferred_shorthand_policy_acceptance_v1"
DEFAULT_REVIEWER = "codex_time_norm_deferred_shorthand_policy_acceptance_v1"


def accept_time_norm_deferred_shorthand_decisions(
    *,
    decision_candidates: list[dict[str, Any]],
    decision_candidate_report: dict[str, Any],
    preview_report: dict[str, Any],
    preview_output_check: dict[str, Any],
    canonical_body_dry_run_check: dict[str, Any],
    reviewer: str = DEFAULT_REVIEWER,
    accepted_at: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    expected_count = len(decision_candidates)
    validate_candidate_report(decision_candidate_report, expected_count=expected_count)
    validate_preview_report(preview_report, expected_count=expected_count)
    validate_preview_output_check(preview_output_check, expected_count=expected_count)
    validate_canonical_body_dry_run_check(canonical_body_dry_run_check, expected_count=expected_count)

    timestamp = accepted_at or datetime.now(UTC).replace(microsecond=0).isoformat()
    accepted: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    seen_decision_ids: set[str] = set()
    seen_review_item_ids: set[str] = set()
    for index, candidate in enumerate(decision_candidates, start=1):
        decision_id = clean_text(candidate.get("entity_resolution_decision_id")) or ""
        review_item_id = clean_text(candidate.get("review_item_id")) or ""
        if not decision_id:
            invalid.append({"decision_index": index, "error": "missing_entity_resolution_decision_id"})
            continue
        if decision_id in seen_decision_ids:
            invalid.append({"decision_index": index, "decision_id": decision_id, "error": "duplicate_decision_id"})
            continue
        seen_decision_ids.add(decision_id)
        if not review_item_id:
            invalid.append({"decision_index": index, "decision_id": decision_id, "error": "missing_review_item_id"})
            continue
        if review_item_id in seen_review_item_ids:
            invalid.append({"decision_index": index, "review_item_id": review_item_id, "error": "duplicate_review_item_id"})
            continue
        seen_review_item_ids.add(review_item_id)
        candidate_error = validate_decision_candidate(candidate)
        if candidate_error:
            invalid.append({"decision_index": index, "review_item_id": review_item_id, "error": candidate_error})
            continue
        accepted.append(accepted_decision_from_candidate(candidate, reviewer=reviewer, accepted_at=timestamp))

    if invalid:
        raise ValueError("deferred shorthand decision candidates are unsafe for acceptance: " + json.dumps(invalid[:5], ensure_ascii=False))

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
        "decision_candidate_count": expected_count,
        "accepted_decision_count": len(accepted),
        "skipped_decision_candidate_count": 0,
        "projected_event_reduction": int(decision_candidate_report.get("projected_event_reduction") or 0),
        "preview_effects_applied": int(preview_report.get("effects_applied") or 0),
        "preview_output_valid": preview_output_check.get("valid") is True,
        "canonical_body_dry_run_valid": canonical_body_dry_run_check.get("valid") is True,
        "canonical_body_dry_run_row_count": int(canonical_body_dry_run_check.get("dry_run_row_count") or 0),
        "reviewer": reviewer,
        "accepted_at": timestamp,
        "notes": [
            "Accepted decisions are policy-gated from the source-reviewed deferred shorthand lane only.",
            "This artifact creates accepted decision records but does not apply merges or rewrite canonical events.",
            "A separate stream-safe candidate-corpus apply step is still required.",
        ],
    }
    return accepted, report


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
        "Policy-accepted after valid preview output and valid canonical-body dry-run checks for the source-reviewed shorthand lane.",
    )
    return accepted


def validate_candidate_report(report: dict[str, Any], *, expected_count: int) -> None:
    errors: list[str] = []
    if report.get("promotion_policy") != INPUT_PROMOTION_POLICY:
        errors.append(f"promotion_policy must be {INPUT_PROMOTION_POLICY}")
    if int(report.get("decision_candidate_count") or 0) != expected_count:
        errors.append("decision_candidate_count must match the decision candidate file")
    if int(report.get("skipped_review_item_count") or 0) != 2:
        errors.append("skipped_review_item_count must remain 2 for the deferred source-review cases")
    if int(report.get("projected_event_reduction") or 0) <= 0:
        errors.append("projected_event_reduction must be positive")
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
        raise ValueError("decision candidate report is unsafe for deferred shorthand acceptance: " + "; ".join(errors))


def validate_preview_report(payload: dict[str, Any], *, expected_count: int) -> None:
    errors: list[str] = []
    if payload.get("apply_policy") != PREVIEW_APPLY_POLICY:
        errors.append(f"apply_policy must be {PREVIEW_APPLY_POLICY}")
    if payload.get("canonical_outputs_mutated") is not False:
        errors.append("canonical_outputs_mutated must be false")
    if payload.get("preview_outputs_written") is not True:
        errors.append("preview_outputs_written must be true")
    if int(payload.get("effects_requested") or 0) != expected_count:
        errors.append("effects_requested must match decision candidates")
    if int(payload.get("effects_applied") or 0) != expected_count:
        errors.append("effects_applied must match decision candidates")
    if int(payload.get("effects_blocked") or 0) != 0:
        errors.append("effects_blocked must be 0")
    if errors:
        raise ValueError("preview report is unsafe for deferred shorthand acceptance: " + "; ".join(errors))


def validate_preview_output_check(payload: dict[str, Any], *, expected_count: int) -> None:
    errors: list[str] = []
    if payload.get("check_policy") != PREVIEW_OUTPUT_CHECK_POLICY:
        errors.append(f"check_policy must be {PREVIEW_OUTPUT_CHECK_POLICY}")
    if payload.get("valid") is not True:
        errors.append("preview output check must be valid")
    if int(payload.get("validation_errors") and len(payload.get("validation_errors")) or 0) != 0:
        errors.append("validation_errors must be empty")
    if int(payload.get("effects_applied") or 0) != expected_count:
        errors.append("effects_applied must match decision candidates")
    if int(payload.get("expected_preview_merge_count") or 0) != expected_count:
        errors.append("expected_preview_merge_count must match decision candidates")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "auto_merge_performed"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError("preview output check is unsafe for deferred shorthand acceptance: " + "; ".join(errors))


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
        raise ValueError("canonical body dry-run check is unsafe for deferred shorthand acceptance: " + "; ".join(errors))


def validate_decision_candidate(candidate: dict[str, Any]) -> str | None:
    if clean_text(candidate.get("promotion_policy")) != INPUT_PROMOTION_POLICY:
        return "unexpected_promotion_policy"
    if clean_text(candidate.get("decision")) != "same_event":
        return "decision_must_be_same_event"
    if clean_text(candidate.get("review_band")) != "strict_time_normalization_deferred_shorthand_source_review":
        return "unexpected_review_band"
    if candidate.get("canonical_outputs_mutated") is not False:
        return "canonical_outputs_mutated_must_be_false"
    if candidate.get("requires_explicit_apply_step") is not True:
        return "requires_explicit_apply_step_must_be_true"
    if len(string_list(candidate.get("merge_canonical_event_ids"))) < 2:
        return "merge_requires_at_least_two_events"
    return None


def append_note(existing: Any, note: str) -> str:
    existing_text = clean_text(existing) or ""
    return f"{existing_text} {note}".strip()


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
                raise ValueError(f"{path} line {line_number} must be a JSON object.")
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
    parser.add_argument("--preview-report", type=Path, default=DEFAULT_PREVIEW_REPORT)
    parser.add_argument("--preview-output-check", type=Path, default=DEFAULT_PREVIEW_OUTPUT_CHECK)
    parser.add_argument("--canonical-body-dry-run-check", type=Path, default=DEFAULT_CANONICAL_BODY_DRY_RUN_CHECK)
    parser.add_argument("--accepted-decisions-output", type=Path, default=DEFAULT_ACCEPTED_DECISIONS_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    parser.add_argument("--reviewer", default=DEFAULT_REVIEWER)
    parser.add_argument("--accepted-at", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    accepted, report = accept_time_norm_deferred_shorthand_decisions(
        decision_candidates=read_jsonl(args.decision_candidates),
        decision_candidate_report=read_json(args.decision_candidate_report),
        preview_report=read_json(args.preview_report),
        preview_output_check=read_json(args.preview_output_check),
        canonical_body_dry_run_check=read_json(args.canonical_body_dry_run_check),
        reviewer=args.reviewer,
        accepted_at=args.accepted_at,
    )
    report["inputs"] = {
        "decision_candidates": str(args.decision_candidates),
        "decision_candidate_report": str(args.decision_candidate_report),
        "preview_report": str(args.preview_report),
        "preview_output_check": str(args.preview_output_check),
        "canonical_body_dry_run_check": str(args.canonical_body_dry_run_check),
    }
    report["outputs"] = {
        "accepted_decisions": str(args.accepted_decisions_output),
        "report": str(args.report_output),
    }
    write_jsonl(args.accepted_decisions_output, accepted)
    write_json(args.report_output, report)
    print(
        json.dumps(
            {
                "accepted_decisions": str(args.accepted_decisions_output),
                "report": str(args.report_output),
                "accepted_decision_count": report["accepted_decision_count"],
                "projected_event_reduction": report["projected_event_reduction"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
