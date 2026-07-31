"""Check whether cluster ER policy artifacts are ready for canonical apply."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_OVERRIDE_SUBSET = Path("data/reports/entity_resolution_cluster_ai_effects_plan_shadow_override_subset.json")
DEFAULT_MERGE_READINESS = Path("data/reports/entity_resolution_cluster_ai_merge_readiness.json")
DEFAULT_POLICY_BODY_CHECK = Path("data/reports/entity_resolution_cluster_policy_body_preview_check.json")
DEFAULT_SHADOW_PREVIEW_REPORT = Path(
    "data/reports/entity_resolution_cluster_ai_shadow_override_subset_preview_apply_report.json"
)
DEFAULT_SHADOW_OUTPUT_CHECK = Path(
    "data/reports/entity_resolution_cluster_ai_shadow_override_subset_preview_output_check.json"
)
DEFAULT_OUTPUT = Path("data/reports/entity_resolution_cluster_canonical_apply_readiness.json")


def check_entity_resolution_cluster_canonical_apply_readiness(
    *,
    override_subset: dict[str, Any],
    merge_readiness: dict[str, Any],
    policy_body_check: dict[str, Any],
    shadow_preview_report: dict[str, Any] | None = None,
    shadow_output_check: dict[str, Any] | None = None,
    paths: dict[str, Path] | None = None,
) -> dict[str, Any]:
    validate_override_subset(override_subset)
    validate_merge_readiness(merge_readiness)
    validate_policy_body_check(policy_body_check)
    if shadow_preview_report is not None:
        validate_shadow_preview_report(shadow_preview_report)
    if shadow_output_check is not None:
        validate_shadow_output_check(shadow_output_check)

    remaining_excluded = int(override_subset.get("excluded_merge_effect_count") or 0)
    blocking_conflicts = int(merge_readiness.get("blocking_conflict_item_count") or 0)
    selected_effects = int(override_subset.get("selected_merge_effect_count") or 0)
    policy_body_preview_count = int(policy_body_check.get("policy_body_preview_count") or 0)
    shadow_preview_valid = bool(shadow_output_check and shadow_output_check.get("valid") is True)

    blockers = [
        {
            "blocker": "canonical_apply_command_not_implemented",
            "severity": "hard",
            "reason": "The current apply scripts intentionally support preview/report flows only.",
        },
    ]
    if not (shadow_preview_report and shadow_output_check and shadow_preview_valid):
        blockers.insert(
            0,
            {
                "blocker": "cluster_full_shadow_preview_missing",
                "severity": "hard",
                "reason": "The cluster lane has compact policy-body validation but no valid full shadow preview output.",
            },
        )
    if remaining_excluded:
        blockers.append(
            {
                "blocker": "cluster_review_first_merge_candidates_remaining",
                "severity": "hard",
                "count": remaining_excluded,
                "reason": "Cluster merge effects remain excluded from the shadow-override subset.",
            }
        )
    if blocking_conflicts:
        blockers.append(
            {
                "blocker": "cluster_merge_preview_blocking_conflicts_remaining",
                "severity": "hard",
                "count": blocking_conflicts,
                "reason": "The full cluster compact merge preview still contains blocking conflicts.",
            }
        )

    return {
        "schema_version": 1,
        "apply_readiness_policy": "entity_resolution_cluster_canonical_apply_readiness_gate",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "inputs": {key: str(path) for key, path in (paths or {}).items()},
        "selected_merge_effect_count": selected_effects,
        "excluded_merge_effect_count": remaining_excluded,
        "merge_readiness_preview_count": int(merge_readiness.get("merge_preview_count") or 0),
        "merge_readiness_blocking_conflicts": blocking_conflicts,
        "merge_readiness_review_conflicts": int(merge_readiness.get("review_conflict_item_count") or 0),
        "policy_body_preview_valid": bool(policy_body_check.get("valid")),
        "policy_body_preview_count": policy_body_preview_count,
        "policy_body_invalid_conflict_metadata_count": int(
            policy_body_check.get("invalid_conflict_metadata_count") or 0
        ),
        "shadow_preview_available": shadow_preview_report is not None and shadow_output_check is not None,
        "shadow_preview_valid": shadow_preview_valid,
        "shadow_preview_effects_requested": int((shadow_preview_report or {}).get("effects_requested") or 0),
        "shadow_preview_effects_applied": int((shadow_preview_report or {}).get("effects_applied") or 0),
        "shadow_preview_effects_blocked": int((shadow_preview_report or {}).get("effects_blocked") or 0),
        "shadow_preview_projected_event_reduction": int(
            (shadow_preview_report or {}).get("projected_event_reduction") or 0
        ),
        "shadow_preview_event_count": int((shadow_output_check or {}).get("row_count") or 0),
        "shadow_preview_merge_count": int((shadow_output_check or {}).get("preview_merge_count") or 0),
        "canonical_apply_blocker_count": len(blockers),
        "canonical_apply_blockers": blockers,
        "next_actions": [
            "Resolve or explicitly defer remaining cluster readiness blockers.",
            "Run a full cluster shadow preview only after the selected subset is intentionally approved for that heavier check.",
            "Implement a separate canonical apply command only after full shadow preview and final merge-body policy are available.",
        ],
    }


def validate_override_subset(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("subset_policy") != "entity_resolution_shadow_preview_subset_with_analysis_overrides":
        errors.append("subset_policy must be 'entity_resolution_shadow_preview_subset_with_analysis_overrides'")
    if payload.get("effect_policy") != "entity_resolution_plan_only":
        errors.append("effect_policy must be 'entity_resolution_plan_only'")
    for flag in (
        "canonical_outputs_mutated",
        "canonical_outputs_mutated_by_plan",
        "preview_outputs_written",
        "auto_merge_performed",
        "override_decisions_created",
    ):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError(f"cluster override subset is not safe for canonical apply checking: {'; '.join(errors)}")


def validate_merge_readiness(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("readiness_policy") != "entity_resolution_merge_preview_readiness_gate":
        errors.append("readiness_policy must be 'entity_resolution_merge_preview_readiness_gate'")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "decisions_created", "auto_merge_performed"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if payload.get("ready_for_canonical_apply") is not False:
        errors.append("ready_for_canonical_apply must be false")
    if errors:
        raise ValueError(f"cluster merge readiness is not safe for canonical apply checking: {'; '.join(errors)}")


def validate_policy_body_check(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("check_policy") != "entity_resolution_policy_body_preview_check":
        errors.append("check_policy must be 'entity_resolution_policy_body_preview_check'")
    if payload.get("policy") != "entity_resolution_cluster_canonical_merge_policy_proposal_v1":
        errors.append("policy must be 'entity_resolution_cluster_canonical_merge_policy_proposal_v1'")
    if payload.get("valid") is not True:
        errors.append("valid must be true")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "decisions_created", "auto_merge_performed"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if payload.get("ready_for_canonical_apply") is not False:
        errors.append("ready_for_canonical_apply must be false")
    if errors:
        raise ValueError(f"cluster policy body check is not safe for canonical apply checking: {'; '.join(errors)}")


def validate_shadow_preview_report(payload: dict[str, Any]) -> None:
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
        raise ValueError(f"cluster shadow preview report is not safe for canonical apply checking: {'; '.join(errors)}")


def validate_shadow_output_check(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("check_policy") != "entity_resolution_shadow_preview_output_check":
        errors.append("check_policy must be 'entity_resolution_shadow_preview_output_check'")
    if payload.get("valid") is not True:
        errors.append("valid must be true")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "auto_merge_performed"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError(f"cluster shadow output check is not safe for canonical apply checking: {'; '.join(errors)}")


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
    parser.add_argument("--override-subset", type=Path, default=DEFAULT_OVERRIDE_SUBSET)
    parser.add_argument("--merge-readiness", type=Path, default=DEFAULT_MERGE_READINESS)
    parser.add_argument("--policy-body-check", type=Path, default=DEFAULT_POLICY_BODY_CHECK)
    parser.add_argument("--shadow-preview-report", type=Path, default=DEFAULT_SHADOW_PREVIEW_REPORT)
    parser.add_argument("--shadow-output-check", type=Path, default=DEFAULT_SHADOW_OUTPUT_CHECK)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = {
        "override_subset": args.override_subset,
        "merge_readiness": args.merge_readiness,
        "policy_body_check": args.policy_body_check,
    }
    shadow_preview_report = read_json(args.shadow_preview_report) if args.shadow_preview_report.exists() else None
    shadow_output_check = read_json(args.shadow_output_check) if args.shadow_output_check.exists() else None
    if shadow_preview_report is not None:
        paths["shadow_preview_report"] = args.shadow_preview_report
    if shadow_output_check is not None:
        paths["shadow_output_check"] = args.shadow_output_check
    report = check_entity_resolution_cluster_canonical_apply_readiness(
        override_subset=read_json(args.override_subset),
        merge_readiness=read_json(args.merge_readiness),
        policy_body_check=read_json(args.policy_body_check),
        shadow_preview_report=shadow_preview_report,
        shadow_output_check=shadow_output_check,
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
