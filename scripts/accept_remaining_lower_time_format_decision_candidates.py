"""Accept checked remaining-lower time-format decision candidates.

This script is the explicit approval boundary for the remaining-lower
time-format lane. It consumes the candidate JSONL and its valid check report,
writes accepted decision records, and writes an effects plan that can be used
by the existing preview/apply machinery. It does not mutate canonical_full.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from parser.canonical_schema import clean_text, stable_hash


DEFAULT_CANDIDATES = Path("data/reports/entity_resolution_remaining_lower_time_format_decision_candidates.jsonl")
DEFAULT_CHECK = Path("data/reports/entity_resolution_remaining_lower_time_format_decision_candidates_check.json")
DEFAULT_ACCEPTED_OUTPUT = Path("data/canonical_full/entity_resolution_remaining_lower_time_format_accepted_decisions.jsonl")
DEFAULT_EFFECTS_PLAN_OUTPUT = Path("data/reports/entity_resolution_remaining_lower_time_format_effects_plan.json")
DEFAULT_REPORT_OUTPUT = Path("data/reports/entity_resolution_remaining_lower_time_format_acceptance_report.json")

ACCEPTANCE_POLICY = "entity_resolution_remaining_lower_time_format_accepted_decisions_v1"
EFFECT_POLICY = "entity_resolution_plan_only"


def accept_remaining_lower_time_format_decision_candidates(
    *,
    candidates: list[dict[str, Any]],
    check_report: dict[str, Any],
    approver: str = "user_approved_everything",
    accepted_at: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    validate_check_report(check_report, expected_candidate_count=len(candidates))
    timestamp = accepted_at or datetime.now(UTC).replace(microsecond=0).isoformat()
    accepted: list[dict[str, Any]] = []
    effects: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates, start=1):
        merge_event_ids = string_list(candidate.get("merge_canonical_event_ids"))
        if len(merge_event_ids) < 2:
            raise ValueError(f"candidate row {index} must contain at least two merge_canonical_event_ids")
        decision_id = clean_text(candidate.get("entity_resolution_decision_id")) or stable_hash(
            {"candidate": candidate, "acceptance_policy": ACCEPTANCE_POLICY},
            prefix="errltfa_",
            length=20,
        )
        accepted_record = dict(candidate)
        accepted_record.update(
            {
                "entity_resolution_decision_id": decision_id,
                "accepted_decision_index": index,
                "acceptance_policy": ACCEPTANCE_POLICY,
                "decision": "same_event",
                "effect_status": "accepted_for_sidecar_apply",
                "accepted_by": approver,
                "accepted_at": timestamp,
                "canonical_outputs_mutated": False,
                "requires_explicit_apply_step": True,
            }
        )
        accepted.append(accepted_record)
        effect_id = stable_hash(
            {
                "decision_id": decision_id,
                "merge_canonical_event_ids": merge_event_ids,
                "acceptance_policy": ACCEPTANCE_POLICY,
            },
            prefix="errltf_effect_",
            length=20,
        )
        effects.append(
            {
                "effect_id": effect_id,
                "review_item_id": clean_text(candidate.get("review_item_id")),
                "decision_id": decision_id,
                "planned_effect": "merge_entity_resolution_candidate",
                "requires_explicit_apply_step": True,
                "merge_canonical_event_ids": merge_event_ids,
                "canonical_input_ids": string_list(candidate.get("canonical_input_ids")),
                "source_policy": ACCEPTANCE_POLICY,
                "projected_event_reduction": max(0, len(merge_event_ids) - 1),
            }
        )

    effects_plan = {
        "schema_version": 1,
        "effect_policy": EFFECT_POLICY,
        "source_acceptance_policy": ACCEPTANCE_POLICY,
        "canonical_outputs_mutated": False,
        "canonical_outputs_mutated_by_plan": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "planned_effect_count": len(effects),
        "requires_explicit_apply_step_count": len(effects),
        "projected_event_reduction": sum(int(effect["projected_event_reduction"]) for effect in effects),
        "warnings": [],
        "effects": effects,
    }
    report = {
        "schema_version": 1,
        "acceptance_policy": ACCEPTANCE_POLICY,
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "accepted_canonical_decisions_created": True,
        "canonical_apply_performed": False,
        "auto_merge_performed": False,
        "ready_for_sidecar_apply": True,
        "accepted_decision_count": len(accepted),
        "planned_effect_count": len(effects),
        "projected_event_reduction": effects_plan["projected_event_reduction"],
        "approver": approver,
        "accepted_at": timestamp,
        "check_policy": check_report.get("check_policy"),
        "notes": [
            "Approval was explicit in-chat: user said 'i approve everything'.",
            "Accepted decisions are written as a decision artifact; canonical_full/deduped_events.jsonl is not mutated by this script.",
            "Use the effects plan with preview/apply machinery to produce a validated sidecar corpus.",
        ],
    }
    return accepted, effects_plan, report


def validate_check_report(check_report: dict[str, Any], *, expected_candidate_count: int) -> None:
    errors: list[str] = []
    if check_report.get("valid") is not True:
        errors.append("candidate check must be valid")
    if int(check_report.get("decision_candidate_count") or 0) != expected_candidate_count:
        errors.append("candidate check count must match candidate rows")
    if check_report.get("canonical_outputs_mutated") is not False:
        errors.append("candidate check canonical_outputs_mutated must be false")
    if check_report.get("preview_outputs_written") is not False:
        errors.append("candidate check preview_outputs_written must be false")
    if check_report.get("auto_merge_performed") is not False:
        errors.append("candidate check auto_merge_performed must be false")
    if check_report.get("overlap_with_accepted_review_ids"):
        errors.append("candidate check overlaps already accepted review IDs")
    if check_report.get("overlap_with_deferred_review_ids"):
        errors.append("candidate check overlaps deferred review IDs")
    if errors:
        raise ValueError("remaining lower candidate check is unsafe for acceptance: " + "; ".join(errors))


def string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [text for item in value if (text := clean_text(item))]
    text = clean_text(value)
    return [text] if text else []


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                payload = json.loads(line)
                if not isinstance(payload, dict):
                    raise ValueError(f"{path} contains a non-object JSONL row.")
                rows.append(payload)
    return rows


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
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--check", type=Path, default=DEFAULT_CHECK)
    parser.add_argument("--accepted-output", type=Path, default=DEFAULT_ACCEPTED_OUTPUT)
    parser.add_argument("--effects-plan-output", type=Path, default=DEFAULT_EFFECTS_PLAN_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    parser.add_argument("--approver", default="user_approved_everything")
    parser.add_argument("--accepted-at", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    accepted, effects_plan, report = accept_remaining_lower_time_format_decision_candidates(
        candidates=read_jsonl(args.candidates),
        check_report=read_json(args.check),
        approver=args.approver,
        accepted_at=args.accepted_at,
    )
    report["inputs"] = {"candidates": str(args.candidates), "check": str(args.check)}
    report["outputs"] = {
        "accepted_decisions": str(args.accepted_output),
        "effects_plan": str(args.effects_plan_output),
        "report": str(args.report_output),
    }
    effects_plan["inputs"] = {"accepted_decisions": str(args.accepted_output)}
    effects_plan["outputs"] = {"effects_plan": str(args.effects_plan_output)}
    write_jsonl(args.accepted_output, accepted)
    write_json(args.effects_plan_output, effects_plan)
    write_json(args.report_output, report)
    print(
        json.dumps(
            {
                "accepted_decisions": str(args.accepted_output),
                "effects_plan": str(args.effects_plan_output),
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
