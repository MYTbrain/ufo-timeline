"""Check apply readiness for the recommended time-normalization preview lane."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_DECISION_REPORT = Path("data/reports/entity_resolution_cluster_time_norm_recommended_decision_candidates_report.json")
DEFAULT_EFFECTS_PLAN = Path("data/reports/entity_resolution_cluster_time_norm_recommended_effects_plan.json")
DEFAULT_PREVIEW_REPORT = Path("data/reports/entity_resolution_cluster_time_norm_recommended_preview_apply_report.json")
DEFAULT_OUTPUT_CHECK = Path("data/reports/entity_resolution_cluster_time_norm_recommended_preview_output_check.json")
DEFAULT_POLICY_BODY_CHECK = Path(
    "data/reports/entity_resolution_cluster_time_norm_recommended_policy_body_preview_check.json"
)
DEFAULT_CANONICAL_BODY_DRY_RUN_CHECK = Path(
    "data/reports/entity_resolution_cluster_time_norm_recommended_canonical_body_dry_run_check.json"
)
DEFAULT_ACCEPTED_DECISION_REPORT = Path("data/reports/entity_resolution_cluster_time_norm_recommended_acceptance_report.json")
DEFAULT_CANONICAL_APPLY_OUTPUT_CHECK = Path(
    "data/reports/entity_resolution_cluster_time_norm_recommended_canonical_apply_output_check.json"
)
DEFAULT_OUTPUT = Path("data/reports/entity_resolution_cluster_time_norm_recommended_apply_readiness.json")


def check_time_norm_recommended_apply_readiness(
    *,
    decision_report: dict[str, Any],
    effects_plan: dict[str, Any],
    preview_report: dict[str, Any],
    output_check: dict[str, Any],
    policy_body_check: dict[str, Any] | None = None,
    canonical_body_dry_run_check: dict[str, Any] | None = None,
    accepted_decision_report: dict[str, Any] | None = None,
    canonical_apply_output_check: dict[str, Any] | None = None,
    paths: dict[str, Path] | None = None,
) -> dict[str, Any]:
    validate_decision_report(decision_report)
    validate_effects_plan(effects_plan)
    validate_preview_report(preview_report)
    validate_output_check(output_check)
    if policy_body_check is not None:
        validate_policy_body_check(policy_body_check)
    if canonical_body_dry_run_check is not None:
        validate_canonical_body_dry_run_check(canonical_body_dry_run_check)
    if accepted_decision_report is not None:
        validate_accepted_decision_report(
            accepted_decision_report,
            expected_count=int(decision_report.get("decision_candidate_count") or 0),
        )
    if canonical_apply_output_check is not None:
        validate_canonical_apply_output_check(
            canonical_apply_output_check,
            expected_rows=int(output_check.get("row_count") or 0),
            expected_replacement_rows=int((canonical_body_dry_run_check or {}).get("dry_run_row_count") or 0),
        )
    blockers = []
    if accepted_decision_report is None:
        blockers.append(
            {
                "blocker": "recommended_decision_candidates_not_accepted_canonical_decisions",
                "severity": "hard",
                "reason": "The clean time-normalization lane uses isolated decision candidates, not accepted canonical decision records.",
            }
        )
    if canonical_apply_output_check is None:
        blockers.append(
            {
                "blocker": "canonical_apply_command_not_implemented",
                "severity": "hard",
                "reason": "No validated stream-applied canonical candidate output is available.",
            }
        )
        if canonical_body_dry_run_check is not None:
            blockers.append(
                {
                    "blocker": "canonical_body_dry_run_not_apply_implementation",
                    "severity": "hard",
                    "reason": "The full-row canonical body dry run is valid, but it is still a dry-run artifact rather than a stream-applied candidate output.",
                }
            )
        elif policy_body_check is None:
            blockers.append(
                {
                    "blocker": "final_merge_body_policy_missing_for_recommended_lane",
                    "severity": "hard",
                    "reason": "Canonical apply still needs an explicit final merge-body/provenance reconciliation policy for this lane.",
                }
            )
        else:
            blockers.append(
                {
                    "blocker": "policy_body_preview_not_full_apply_policy",
                    "severity": "hard",
                    "reason": "The merge-body metadata check is valid, but it is still a compact preview artifact and not a canonical apply implementation.",
                }
            )
    ready_for_canonical_apply = canonical_apply_output_check is not None and not blockers
    return {
        "schema_version": 1,
        "apply_readiness_policy": "entity_resolution_time_norm_recommended_apply_readiness_gate",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": ready_for_canonical_apply,
        "inputs": {key: str(path) for key, path in (paths or {}).items()},
        "decision_candidate_count": int(decision_report.get("decision_candidate_count") or 0),
        "skipped_recommendation_count": int(decision_report.get("skipped_recommendation_count") or 0),
        "planned_effect_count": int(effects_plan.get("planned_effect_count") or 0),
        "accepted_decision_report_available": accepted_decision_report is not None,
        "accepted_canonical_decisions_created": bool(
            accepted_decision_report and accepted_decision_report.get("accepted_canonical_decisions_created") is True
        ),
        "accepted_decision_count": int((accepted_decision_report or {}).get("accepted_decision_count") or 0),
        "preview_effects_applied": int(preview_report.get("effects_applied") or 0),
        "preview_effects_blocked": int(preview_report.get("effects_blocked") or 0),
        "preview_projected_event_reduction": int(preview_report.get("projected_event_reduction") or 0),
        "preview_output_valid": bool(output_check.get("valid")),
        "preview_row_count": int(output_check.get("row_count") or 0),
        "preview_merge_count": int(output_check.get("preview_merge_count") or 0),
        "policy_body_preview_available": policy_body_check is not None,
        "policy_body_preview_valid": bool(policy_body_check and policy_body_check.get("valid") is True),
        "policy_body_preview_count": int((policy_body_check or {}).get("policy_body_preview_count") or 0),
        "policy_body_invalid_conflict_metadata_count": int(
            (policy_body_check or {}).get("invalid_conflict_metadata_count") or 0
        ),
        "canonical_body_dry_run_available": canonical_body_dry_run_check is not None,
        "canonical_body_dry_run_valid": bool(canonical_body_dry_run_check and canonical_body_dry_run_check.get("valid") is True),
        "canonical_body_dry_run_row_count": int((canonical_body_dry_run_check or {}).get("dry_run_row_count") or 0),
        "canonical_body_dry_run_incomplete_conflict_source_value_count": int(
            (canonical_body_dry_run_check or {}).get("incomplete_conflict_source_value_count") or 0
        ),
        "canonical_apply_output_check_available": canonical_apply_output_check is not None,
        "canonical_apply_output_valid": bool(canonical_apply_output_check and canonical_apply_output_check.get("valid") is True),
        "canonical_apply_output_row_count": int((canonical_apply_output_check or {}).get("row_count") or 0),
        "canonical_apply_output_replacement_rows_found": int(
            (canonical_apply_output_check or {}).get("replacement_rows_found") or 0
        ),
        "canonical_apply_output_suppressed_ids_found": int(
            (canonical_apply_output_check or {}).get("suppressed_ids_found") or 0
        ),
        "canonical_apply_blocker_count": len(blockers),
        "canonical_apply_blockers": blockers,
        "next_actions": [
            "Treat the stream-applied output as a canonical candidate only until runtime/static promotion checks pass.",
            "Rebuild downstream compact web artifacts from the candidate corpus before any app integration.",
            "Keep the 11 deferred recommendations out of this lane unless a later source parser resolves their blockers.",
        ],
    }


def validate_decision_report(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("promotion_policy") != "entity_resolution_time_norm_recommended_decision_candidates_only":
        errors.append("promotion_policy must be entity_resolution_time_norm_recommended_decision_candidates_only")
    if payload.get("canonical_outputs_mutated") is not False:
        errors.append("canonical_outputs_mutated must be false")
    if payload.get("accepted_canonical_decisions_created") is not False:
        errors.append("accepted_canonical_decisions_created must be false")
    if payload.get("ready_for_canonical_apply") is not False:
        errors.append("ready_for_canonical_apply must be false")
    if errors:
        raise ValueError("decision candidate report is not safe for readiness checking: " + "; ".join(errors))


def validate_effects_plan(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("effect_policy") != "entity_resolution_plan_only":
        errors.append("effect_policy must be entity_resolution_plan_only")
    for flag in ("canonical_outputs_mutated", "canonical_outputs_mutated_by_plan", "preview_outputs_written", "auto_merge_performed"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError("effects plan is not safe for readiness checking: " + "; ".join(errors))


def validate_preview_report(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("apply_policy") != "entity_resolution_stream_preview_only":
        errors.append("apply_policy must be entity_resolution_stream_preview_only")
    if payload.get("canonical_outputs_mutated") is not False:
        errors.append("canonical_outputs_mutated must be false")
    if payload.get("preview_outputs_written") is not True:
        errors.append("preview_outputs_written must be true")
    if payload.get("effects_blocked") not in (0, "0"):
        errors.append("effects_blocked must be 0")
    if errors:
        raise ValueError("preview report is not safe for readiness checking: " + "; ".join(errors))


def validate_output_check(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("check_policy") != "entity_resolution_shadow_preview_output_check":
        errors.append("check_policy must be entity_resolution_shadow_preview_output_check")
    if payload.get("valid") is not True:
        errors.append("valid must be true")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "auto_merge_performed"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError("output check is not safe for readiness checking: " + "; ".join(errors))


def validate_policy_body_check(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("check_policy") != "entity_resolution_policy_body_preview_check":
        errors.append("check_policy must be entity_resolution_policy_body_preview_check")
    if payload.get("valid") is not True:
        errors.append("valid must be true")
    if payload.get("policy") != "entity_resolution_cluster_canonical_merge_policy_proposal_v1":
        errors.append("policy must be entity_resolution_cluster_canonical_merge_policy_proposal_v1")
    if int(payload.get("invalid_conflict_metadata_count") or 0) != 0:
        errors.append("invalid_conflict_metadata_count must be 0")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "decisions_created", "auto_merge_performed"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if payload.get("ready_for_canonical_apply") is not False:
        errors.append("ready_for_canonical_apply must be false")
    if errors:
        raise ValueError("policy body check is not safe for readiness checking: " + "; ".join(errors))


def validate_canonical_body_dry_run_check(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("check_policy") != "entity_resolution_time_norm_recommended_canonical_body_dry_run_check":
        errors.append("check_policy must be entity_resolution_time_norm_recommended_canonical_body_dry_run_check")
    if payload.get("valid") is not True:
        errors.append("valid must be true")
    if int(payload.get("validation_error_count") or 0) != 0:
        errors.append("validation_error_count must be 0")
    if int(payload.get("incomplete_conflict_source_value_count") or 0) != 0:
        errors.append("incomplete_conflict_source_value_count must be 0")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "decisions_created", "auto_merge_performed", "ready_for_canonical_apply"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError("canonical body dry-run check is not safe for readiness checking: " + "; ".join(errors))


def validate_accepted_decision_report(payload: dict[str, Any], *, expected_count: int) -> None:
    errors: list[str] = []
    if payload.get("acceptance_policy") != "entity_resolution_time_norm_recommended_policy_acceptance_v1":
        errors.append("acceptance_policy must be entity_resolution_time_norm_recommended_policy_acceptance_v1")
    if int(payload.get("decision_candidate_count") or 0) != expected_count:
        errors.append("decision_candidate_count must match the decision candidate report")
    if int(payload.get("accepted_decision_count") or 0) != expected_count:
        errors.append("accepted_decision_count must match the decision candidate report")
    if int(payload.get("skipped_decision_candidate_count") or 0) != 0:
        errors.append("skipped_decision_candidate_count must be 0")
    if int(payload.get("policy_conflict_blocking_preview_count") or 0) != 0:
        errors.append("policy_conflict_blocking_preview_count must be 0")
    if payload.get("canonical_apply_contract_valid") is not True:
        errors.append("canonical_apply_contract_valid must be true")
    if payload.get("canonical_body_dry_run_valid") is not True:
        errors.append("canonical_body_dry_run_valid must be true")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "canonical_apply_performed", "auto_merge_performed", "ready_for_canonical_apply"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    for flag in ("decisions_created", "accepted_canonical_decisions_created", "validated_decisions_created"):
        if payload.get(flag) is not True:
            errors.append(f"{flag} must be true")
    if errors:
        raise ValueError("accepted decision report is not safe for readiness checking: " + "; ".join(errors))


def validate_canonical_apply_output_check(
    payload: dict[str, Any],
    *,
    expected_rows: int,
    expected_replacement_rows: int,
) -> None:
    errors: list[str] = []
    if payload.get("check_policy") != "entity_resolution_time_norm_recommended_canonical_apply_output_check":
        errors.append("check_policy must be entity_resolution_time_norm_recommended_canonical_apply_output_check")
    if payload.get("valid") is not True:
        errors.append("valid must be true")
    if int(payload.get("validation_error_count") or 0) != 0:
        errors.append("validation_error_count must be 0")
    if int(payload.get("row_count") or 0) != expected_rows:
        errors.append("row_count must match the validated preview row count")
    if int(payload.get("replacement_rows_found") or 0) != expected_replacement_rows:
        errors.append("replacement_rows_found must match canonical body dry-run rows")
    if int(payload.get("suppressed_ids_found") or 0) != 0:
        errors.append("suppressed_ids_found must be 0")
    if int(payload.get("duplicate_event_id_count") or 0) != 0:
        errors.append("duplicate_event_id_count must be 0")
    if int(payload.get("malformed_row_count") or 0) != 0:
        errors.append("malformed_row_count must be 0")
    if int(payload.get("mismatched_replacement_row_count") or 0) != 0:
        errors.append("mismatched_replacement_row_count must be 0")
    for flag in ("canonical_outputs_mutated", "source_canonical_outputs_mutated", "preview_outputs_written", "auto_merge_performed", "ready_for_runtime_promotion"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError("canonical apply output check is not safe for readiness checking: " + "; ".join(errors))


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decision-report", type=Path, default=DEFAULT_DECISION_REPORT)
    parser.add_argument("--effects-plan", type=Path, default=DEFAULT_EFFECTS_PLAN)
    parser.add_argument("--preview-report", type=Path, default=DEFAULT_PREVIEW_REPORT)
    parser.add_argument("--output-check", type=Path, default=DEFAULT_OUTPUT_CHECK)
    parser.add_argument("--policy-body-check", type=Path, default=DEFAULT_POLICY_BODY_CHECK)
    parser.add_argument("--canonical-body-dry-run-check", type=Path, default=DEFAULT_CANONICAL_BODY_DRY_RUN_CHECK)
    parser.add_argument("--accepted-decision-report", type=Path, default=DEFAULT_ACCEPTED_DECISION_REPORT)
    parser.add_argument("--canonical-apply-output-check", type=Path, default=DEFAULT_CANONICAL_APPLY_OUTPUT_CHECK)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = {
        "decision_report": args.decision_report,
        "effects_plan": args.effects_plan,
        "preview_report": args.preview_report,
        "output_check": args.output_check,
    }
    policy_body_check = read_json(args.policy_body_check) if args.policy_body_check.exists() else None
    if policy_body_check is not None:
        paths["policy_body_check"] = args.policy_body_check
    canonical_body_dry_run_check = (
        read_json(args.canonical_body_dry_run_check) if args.canonical_body_dry_run_check.exists() else None
    )
    if canonical_body_dry_run_check is not None:
        paths["canonical_body_dry_run_check"] = args.canonical_body_dry_run_check
    accepted_decision_report = read_json(args.accepted_decision_report) if args.accepted_decision_report.exists() else None
    if accepted_decision_report is not None:
        paths["accepted_decision_report"] = args.accepted_decision_report
    canonical_apply_output_check = (
        read_json(args.canonical_apply_output_check) if args.canonical_apply_output_check.exists() else None
    )
    if canonical_apply_output_check is not None:
        paths["canonical_apply_output_check"] = args.canonical_apply_output_check
    report = check_time_norm_recommended_apply_readiness(
        decision_report=read_json(args.decision_report),
        effects_plan=read_json(args.effects_plan),
        preview_report=read_json(args.preview_report),
        output_check=read_json(args.output_check),
        policy_body_check=policy_body_check,
        canonical_body_dry_run_check=canonical_body_dry_run_check,
        accepted_decision_report=accepted_decision_report,
        canonical_apply_output_check=canonical_apply_output_check,
        paths=paths,
    )
    write_json(args.output, report)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "ready_for_canonical_apply": report["ready_for_canonical_apply"],
                "canonical_apply_blocker_count": report["canonical_apply_blocker_count"],
                "preview_output_valid": report["preview_output_valid"],
                "policy_body_preview_valid": report["policy_body_preview_valid"],
                "canonical_body_dry_run_valid": report["canonical_body_dry_run_valid"],
                "accepted_canonical_decisions_created": report["accepted_canonical_decisions_created"],
                "canonical_apply_output_valid": report["canonical_apply_output_valid"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
