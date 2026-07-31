"""Check whether ER shadow previews are ready for canonical apply."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_DELTA_SUMMARY = Path("data/reports/entity_resolution_shadow_override_delta_summary.json")
DEFAULT_OVERRIDE_SUBSET = Path("data/reports/entity_resolution_ai_effects_plan_shadow_override_subset.json")
DEFAULT_OVERRIDE_PREVIEW_REPORT = Path("data/reports/entity_resolution_ai_shadow_override_subset_preview_apply_report.json")
DEFAULT_OVERRIDE_OUTPUT_CHECK = Path("data/reports/entity_resolution_ai_shadow_override_subset_preview_output_check.json")
DEFAULT_OUTPUT = Path("data/reports/entity_resolution_canonical_apply_readiness.json")


def check_entity_resolution_canonical_apply_readiness(
    *,
    delta_summary: dict[str, Any],
    override_subset: dict[str, Any],
    override_preview_report: dict[str, Any],
    override_output_check: dict[str, Any],
    paths: dict[str, Path] | None = None,
) -> dict[str, Any]:
    validate_delta_summary(delta_summary)
    validate_override_subset(override_subset)
    validate_override_preview_report(override_preview_report)
    validate_override_output_check(override_output_check)

    blockers = [
        {
            "blocker": "final_merge_body_policy_missing",
            "severity": "hard",
            "reason": "The current stream preview merges by retaining a representative row plus aggregated provenance fields; canonical apply needs an explicit final field/provenance reconciliation policy.",
        },
        {
            "blocker": "canonical_apply_command_not_implemented",
            "severity": "hard",
            "reason": "The current apply script intentionally supports preview mode only.",
        },
    ]
    remaining_excluded = int(delta_summary.get("remaining_excluded_merge_effect_count") or 0)
    if remaining_excluded:
        blockers.append(
            {
                "blocker": "review_first_merge_candidates_remaining",
                "severity": "hard",
                "count": remaining_excluded,
                "review_item_ids": delta_summary.get("remaining_excluded_review_item_ids") or [],
                "reason": "At least one ER merge candidate remains excluded from the shadow-override lane.",
            }
        )

    return {
        "schema_version": 1,
        "apply_readiness_policy": "entity_resolution_canonical_apply_readiness_gate",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "inputs": {key: str(path) for key, path in (paths or {}).items()},
        "shadow_preview_valid": bool(override_output_check.get("valid")),
        "shadow_preview_effects_requested": int(override_preview_report.get("effects_requested") or 0),
        "shadow_preview_effects_applied": int(override_preview_report.get("effects_applied") or 0),
        "shadow_preview_effects_blocked": int(override_preview_report.get("effects_blocked") or 0),
        "shadow_preview_projected_event_reduction": int(override_preview_report.get("projected_event_reduction") or 0),
        "remaining_excluded_merge_effect_count": remaining_excluded,
        "canonical_apply_blocker_count": len(blockers),
        "canonical_apply_blockers": blockers,
        "next_actions": [
            "Define final canonical merge-body/provenance reconciliation policy.",
            "Implement a separate canonical apply command only after the final merge policy exists.",
            "Resolve or explicitly defer the remaining coordinate-distance blocker.",
        ],
    }


def validate_delta_summary(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("summary_policy") != "entity_resolution_shadow_override_delta_summary":
        errors.append("summary_policy must be 'entity_resolution_shadow_override_delta_summary'")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "decisions_created", "auto_merge_performed"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError(f"delta summary is not safe for canonical apply checking: {'; '.join(errors)}")


def validate_override_subset(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("subset_policy") != "entity_resolution_shadow_preview_subset_with_analysis_overrides":
        errors.append("subset_policy must be 'entity_resolution_shadow_preview_subset_with_analysis_overrides'")
    if payload.get("effect_policy") != "entity_resolution_plan_only":
        errors.append("effect_policy must be 'entity_resolution_plan_only'")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "auto_merge_performed"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if payload.get("override_decisions_created") is not False:
        errors.append("override_decisions_created must be false")
    if errors:
        raise ValueError(f"override subset is not safe for canonical apply checking: {'; '.join(errors)}")


def validate_override_preview_report(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("apply_policy") != "entity_resolution_stream_preview_only":
        errors.append("apply_policy must be 'entity_resolution_stream_preview_only'")
    if payload.get("canonical_outputs_mutated") is not False:
        errors.append("canonical_outputs_mutated must be false")
    if payload.get("preview_outputs_written") is not True:
        errors.append("preview_outputs_written must be true")
    if payload.get("effects_blocked") not in (0, "0"):
        errors.append("effects_blocked must be 0")
    if errors:
        raise ValueError(f"override preview report is not safe for canonical apply checking: {'; '.join(errors)}")


def validate_override_output_check(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("check_policy") != "entity_resolution_shadow_preview_output_check":
        errors.append("check_policy must be 'entity_resolution_shadow_preview_output_check'")
    if payload.get("valid") is not True:
        errors.append("valid must be true")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "auto_merge_performed"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError(f"override output check is not safe for canonical apply checking: {'; '.join(errors)}")


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
    parser.add_argument("--delta-summary", type=Path, default=DEFAULT_DELTA_SUMMARY)
    parser.add_argument("--override-subset", type=Path, default=DEFAULT_OVERRIDE_SUBSET)
    parser.add_argument("--override-preview-report", type=Path, default=DEFAULT_OVERRIDE_PREVIEW_REPORT)
    parser.add_argument("--override-output-check", type=Path, default=DEFAULT_OVERRIDE_OUTPUT_CHECK)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = {
        "delta_summary": args.delta_summary,
        "override_subset": args.override_subset,
        "override_preview_report": args.override_preview_report,
        "override_output_check": args.override_output_check,
    }
    report = check_entity_resolution_canonical_apply_readiness(
        delta_summary=read_json(args.delta_summary),
        override_subset=read_json(args.override_subset),
        override_preview_report=read_json(args.override_preview_report),
        override_output_check=read_json(args.override_output_check),
        paths=paths,
    )
    write_json(args.output, report)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "apply_readiness_policy": report["apply_readiness_policy"],
                "ready_for_canonical_apply": report["ready_for_canonical_apply"],
                "canonical_apply_blocker_count": report["canonical_apply_blocker_count"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
