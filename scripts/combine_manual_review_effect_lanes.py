"""Combine safe manual-review effect lanes into a new non-destructive plan."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable


DEFAULT_ORIGINAL_EFFECTS_PLAN = Path("data/reports/manual_review_ai_effects_plan.json")
DEFAULT_BASE_EFFECTS_PLAN = Path("data/reports/manual_review_ai_after_time_norm_low_risk_effects_plan.json")
DEFAULT_DECISION_CANDIDATES = Path("data/reports/manual_review_ai_after_time_norm_medium_time_raw_only_decision_candidates.jsonl")
DEFAULT_OUTPUT_PLAN = Path("data/reports/manual_review_ai_after_time_norm_low_risk_plus_medium_time_effects_plan.json")
DEFAULT_OUTPUT_REPORT = Path("data/reports/manual_review_ai_after_time_norm_low_risk_plus_medium_time_effects_plan_report.json")

COMBINE_POLICY = "manual_review_effect_lanes_combined_v1"
MEDIUM_TIME_PROMOTION_POLICY = "manual_review_medium_time_raw_only_decision_candidates_only"


def combine_manual_review_effect_lanes(
    *,
    original_effects_plan: dict[str, Any],
    base_effects_plan: dict[str, Any],
    decision_candidates: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    validate_effects_plan(original_effects_plan, label="original")
    validate_effects_plan(base_effects_plan, label="base")
    validate_decision_candidates(decision_candidates)

    base_effects = [effect for effect in base_effects_plan.get("effects") or [] if isinstance(effect, dict)]
    original_effects = [effect for effect in original_effects_plan.get("effects") or [] if isinstance(effect, dict)]
    base_merge_effect_ids = {
        clean_text(effect.get("effect_id"))
        for effect in base_effects
        if clean_text(effect.get("planned_effect")) == "merge_duplicate_candidate" and clean_text(effect.get("effect_id"))
    }
    passthrough_effect_ids = {
        clean_text(effect.get("effect_id"))
        for effect in original_effects
        if clean_text(effect.get("planned_effect")) != "merge_duplicate_candidate" and clean_text(effect.get("effect_id"))
    }
    medium_time_effect_ids = {
        effect_id
        for candidate in decision_candidates
        for effect_id in string_list(candidate.get("effect_ids"))
    }
    selected_merge_effect_ids = base_merge_effect_ids | medium_time_effect_ids
    output_effects = [
        effect
        for effect in original_effects
        if clean_text(effect.get("effect_id")) in selected_merge_effect_ids
        or clean_text(effect.get("effect_id")) in passthrough_effect_ids
    ]
    output_plan = {
        **original_effects_plan,
        "combine_policy": COMBINE_POLICY,
        "canonical_outputs_mutated": False,
        "canonical_outputs_mutated_by_plan": False,
        "planned_effect_count": len(output_effects),
        "effects": output_effects,
        "combined_lanes": [
            "manual_review_low_risk_replacement_audit_lane",
            "manual_review_medium_time_raw_only_parser_review_lane",
        ],
    }
    overlap_effect_ids = sorted(base_merge_effect_ids & medium_time_effect_ids)
    report = {
        "schema_version": 1,
        "combine_policy": COMBINE_POLICY,
        "canonical_outputs_mutated": False,
        "source_canonical_outputs_mutated": False,
        "ready_for_runtime_promotion": False,
        "original_effect_count": len(original_effects),
        "base_effect_count": len(base_effects),
        "base_merge_effect_count": len(base_merge_effect_ids),
        "passthrough_non_merge_effect_count": len(passthrough_effect_ids),
        "medium_time_decision_candidate_count": len(decision_candidates),
        "medium_time_merge_effect_count": len(medium_time_effect_ids),
        "base_medium_time_effect_overlap_count": len(overlap_effect_ids),
        "base_medium_time_effect_overlap_ids": overlap_effect_ids[:50],
        "selected_merge_effect_count": len(selected_merge_effect_ids),
        "output_effect_count": len(output_effects),
        "valid": True,
        "validation_error_count": 0,
        "validation_errors": [],
    }
    return output_plan, report


def validate_effects_plan(plan: dict[str, Any], *, label: str) -> None:
    errors: list[str] = []
    if plan.get("effect_policy") != "plan_only":
        errors.append(f"{label}: effect_policy must be plan_only")
    if plan.get("canonical_outputs_mutated") is not False:
        errors.append(f"{label}: canonical_outputs_mutated must be false")
    if plan.get("canonical_outputs_mutated_by_plan") is not False:
        errors.append(f"{label}: canonical_outputs_mutated_by_plan must be false")
    effects = [effect for effect in plan.get("effects") or [] if isinstance(effect, dict)]
    if int(plan.get("planned_effect_count") or 0) != len(effects):
        errors.append(f"{label}: planned_effect_count must match effects length")
    if errors:
        raise ValueError("; ".join(errors))


def validate_decision_candidates(candidates: list[dict[str, Any]]) -> None:
    errors: list[str] = []
    for index, candidate in enumerate(candidates, start=1):
        if candidate.get("promotion_policy") != MEDIUM_TIME_PROMOTION_POLICY:
            errors.append(f"candidate {index}: unexpected promotion_policy")
        if candidate.get("canonical_outputs_mutated") is not False:
            errors.append(f"candidate {index}: canonical_outputs_mutated must be false")
        if clean_text(candidate.get("decision")) != "same_event":
            errors.append(f"candidate {index}: decision must be same_event")
        if not string_list(candidate.get("effect_ids")):
            errors.append(f"candidate {index}: effect_ids required")
    if errors:
        raise ValueError("unsafe decision candidates: " + "; ".join(errors[:20]))


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{path} line {line_number} must be a JSON object.")
            yield payload


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [text for item in value if (text := clean_text(item))]
    text = clean_text(value)
    return [text] if text else []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-effects-plan", type=Path, default=DEFAULT_ORIGINAL_EFFECTS_PLAN)
    parser.add_argument("--base-effects-plan", type=Path, default=DEFAULT_BASE_EFFECTS_PLAN)
    parser.add_argument("--decision-candidates", type=Path, default=DEFAULT_DECISION_CANDIDATES)
    parser.add_argument("--output-plan", type=Path, default=DEFAULT_OUTPUT_PLAN)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_plan, report = combine_manual_review_effect_lanes(
        original_effects_plan=read_json(args.original_effects_plan),
        base_effects_plan=read_json(args.base_effects_plan),
        decision_candidates=list(iter_jsonl(args.decision_candidates)),
    )
    write_json(args.output_plan, output_plan)
    write_json(args.output_report, report)
    print(
        json.dumps(
            {
                "output_plan": str(args.output_plan),
                "output_report": str(args.output_report),
                "selected_merge_effect_count": report["selected_merge_effect_count"],
                "output_effect_count": report["output_effect_count"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
