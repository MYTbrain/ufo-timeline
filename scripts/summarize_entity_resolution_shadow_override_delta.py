"""Summarize the delta from readiness-only ER preview to shadow-override preview."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_READY_SUBSET = Path("data/reports/entity_resolution_ai_effects_plan_ready_subset.json")
DEFAULT_READY_PREVIEW_REPORT = Path("data/reports/entity_resolution_ai_ready_subset_preview_apply_report.json")
DEFAULT_READY_OUTPUT_CHECK = Path("data/reports/entity_resolution_ai_ready_subset_preview_output_check.json")
DEFAULT_OVERRIDE_SUBSET = Path("data/reports/entity_resolution_ai_effects_plan_shadow_override_subset.json")
DEFAULT_OVERRIDE_PREVIEW_REPORT = Path("data/reports/entity_resolution_ai_shadow_override_subset_preview_apply_report.json")
DEFAULT_OVERRIDE_OUTPUT_CHECK = Path("data/reports/entity_resolution_ai_shadow_override_subset_preview_output_check.json")
DEFAULT_BLOCKED_ANALYSIS = Path("data/reports/entity_resolution_blocked_merge_analysis.json")
DEFAULT_OUTPUT = Path("data/reports/entity_resolution_shadow_override_delta_summary.json")


def summarize_entity_resolution_shadow_override_delta(
    *,
    ready_subset: dict[str, Any],
    ready_preview_report: dict[str, Any],
    ready_output_check: dict[str, Any],
    override_subset: dict[str, Any],
    override_preview_report: dict[str, Any],
    override_output_check: dict[str, Any],
    blocked_analysis: dict[str, Any],
    paths: dict[str, Path] | None = None,
) -> dict[str, Any]:
    validate_ready_subset(ready_subset)
    validate_override_subset(override_subset)
    validate_preview_report(ready_preview_report, label="ready_preview_report")
    validate_preview_report(override_preview_report, label="override_preview_report")
    validate_output_check(ready_output_check, label="ready_output_check")
    validate_output_check(override_output_check, label="override_output_check")
    validate_blocked_analysis(blocked_analysis)

    ready_reduction = int(ready_preview_report.get("projected_event_reduction") or 0)
    override_reduction = int(override_preview_report.get("projected_event_reduction") or 0)
    excluded_effects = [
        effect for effect in override_subset.get("excluded_effects") or [] if isinstance(effect, dict)
    ]

    return {
        "schema_version": 1,
        "summary_policy": "entity_resolution_shadow_override_delta_summary",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "inputs": {key: str(path) for key, path in (paths or {}).items()},
        "ready_subset_selected_merge_effect_count": int(ready_subset.get("selected_merge_effect_count") or 0),
        "override_subset_selected_merge_effect_count": int(override_subset.get("selected_merge_effect_count") or 0),
        "override_selected_merge_effect_count": int(override_subset.get("override_selected_merge_effect_count") or 0),
        "ready_preview_event_count": int(ready_preview_report.get("preview_event_count") or 0),
        "override_preview_event_count": int(override_preview_report.get("preview_event_count") or 0),
        "ready_projected_event_reduction": ready_reduction,
        "override_projected_event_reduction": override_reduction,
        "incremental_projected_event_reduction": override_reduction - ready_reduction,
        "ready_output_valid": bool(ready_output_check.get("valid")),
        "override_output_valid": bool(override_output_check.get("valid")),
        "remaining_excluded_merge_effect_count": len(excluded_effects),
        "remaining_excluded_review_item_ids": sorted(
            str(effect.get("review_item_id")) for effect in excluded_effects if effect.get("review_item_id")
        ),
        "blocked_analysis_classification_counts": blocked_analysis.get("classification_counts") or {},
        "blocked_analysis_suggested_action_counts": blocked_analysis.get("suggested_action_counts") or {},
        "notes": [
            "This is a status summary only; it does not write or mutate preview/canonical event rows.",
            "The shadow-override lane adds high-confidence type-code variants for preview validation only.",
            "Canonical apply remains blocked until final merge-body and provenance policy is implemented.",
        ],
    }


def validate_ready_subset(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("subset_policy") != "entity_resolution_ready_subset_for_shadow_preview":
        errors.append("subset_policy must be 'entity_resolution_ready_subset_for_shadow_preview'")
    validate_plan_flags(payload, errors)
    if errors:
        raise ValueError(f"ready subset is not safe to summarize: {'; '.join(errors)}")


def validate_override_subset(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("subset_policy") != "entity_resolution_shadow_preview_subset_with_analysis_overrides":
        errors.append("subset_policy must be 'entity_resolution_shadow_preview_subset_with_analysis_overrides'")
    validate_plan_flags(payload, errors)
    if payload.get("override_decisions_created") is not False:
        errors.append("override_decisions_created must be false")
    if errors:
        raise ValueError(f"override subset is not safe to summarize: {'; '.join(errors)}")


def validate_plan_flags(payload: dict[str, Any], errors: list[str]) -> None:
    if payload.get("effect_policy") != "entity_resolution_plan_only":
        errors.append("effect_policy must be 'entity_resolution_plan_only'")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "auto_merge_performed"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")


def validate_preview_report(payload: dict[str, Any], *, label: str) -> None:
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
        raise ValueError(f"{label} is not safe to summarize: {'; '.join(errors)}")


def validate_output_check(payload: dict[str, Any], *, label: str) -> None:
    errors: list[str] = []
    if payload.get("check_policy") != "entity_resolution_shadow_preview_output_check":
        errors.append("check_policy must be 'entity_resolution_shadow_preview_output_check'")
    if payload.get("valid") is not True:
        errors.append("valid must be true")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "auto_merge_performed"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError(f"{label} is not safe to summarize: {'; '.join(errors)}")


def validate_blocked_analysis(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("analysis_policy") != "entity_resolution_blocked_merge_analysis_only":
        errors.append("analysis_policy must be 'entity_resolution_blocked_merge_analysis_only'")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "decisions_created", "auto_merge_performed"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError(f"blocked analysis is not safe to summarize: {'; '.join(errors)}")


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
    parser.add_argument("--ready-subset", type=Path, default=DEFAULT_READY_SUBSET)
    parser.add_argument("--ready-preview-report", type=Path, default=DEFAULT_READY_PREVIEW_REPORT)
    parser.add_argument("--ready-output-check", type=Path, default=DEFAULT_READY_OUTPUT_CHECK)
    parser.add_argument("--override-subset", type=Path, default=DEFAULT_OVERRIDE_SUBSET)
    parser.add_argument("--override-preview-report", type=Path, default=DEFAULT_OVERRIDE_PREVIEW_REPORT)
    parser.add_argument("--override-output-check", type=Path, default=DEFAULT_OVERRIDE_OUTPUT_CHECK)
    parser.add_argument("--blocked-analysis", type=Path, default=DEFAULT_BLOCKED_ANALYSIS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = {
        "ready_subset": args.ready_subset,
        "ready_preview_report": args.ready_preview_report,
        "ready_output_check": args.ready_output_check,
        "override_subset": args.override_subset,
        "override_preview_report": args.override_preview_report,
        "override_output_check": args.override_output_check,
        "blocked_analysis": args.blocked_analysis,
    }
    summary = summarize_entity_resolution_shadow_override_delta(
        ready_subset=read_json(args.ready_subset),
        ready_preview_report=read_json(args.ready_preview_report),
        ready_output_check=read_json(args.ready_output_check),
        override_subset=read_json(args.override_subset),
        override_preview_report=read_json(args.override_preview_report),
        override_output_check=read_json(args.override_output_check),
        blocked_analysis=read_json(args.blocked_analysis),
        paths=paths,
    )
    write_json(args.output, summary)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "summary_policy": summary["summary_policy"],
                "override_selected_merge_effect_count": summary["override_selected_merge_effect_count"],
                "incremental_projected_event_reduction": summary["incremental_projected_event_reduction"],
                "remaining_excluded_merge_effect_count": summary["remaining_excluded_merge_effect_count"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
