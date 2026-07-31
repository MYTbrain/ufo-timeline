"""Build a report-only proposal for canonical ER merge body policy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_MERGED_EVENT_PREVIEW = Path("data/reports/entity_resolution_ai_merged_event_preview.json")
DEFAULT_SHADOW_OVERRIDE_DELTA = Path("data/reports/entity_resolution_shadow_override_delta_summary.json")
DEFAULT_APPLY_READINESS = Path("data/reports/entity_resolution_canonical_apply_readiness.json")
DEFAULT_OUTPUT = Path("data/reports/entity_resolution_canonical_merge_policy_proposal.json")
GENERIC_POLICY = "entity_resolution_canonical_merge_policy_proposal_v1"
CLUSTER_POLICY = "entity_resolution_cluster_canonical_merge_policy_proposal_v1"


def propose_entity_resolution_canonical_merge_policy(
    *,
    merged_event_preview: dict[str, Any],
    shadow_override_delta: dict[str, Any],
    apply_readiness: dict[str, Any],
    override_subset: dict[str, Any] | None = None,
    paths: dict[str, Path] | None = None,
) -> dict[str, Any]:
    validate_merged_event_preview(merged_event_preview)
    validate_shadow_override_delta(shadow_override_delta)
    validate_apply_readiness(apply_readiness)
    if override_subset is not None:
        validate_override_subset(override_subset)
    previews = merged_event_preview.get("previews") if isinstance(merged_event_preview.get("previews"), list) else []
    observed_conflict_counts = collect_conflict_counts(previews)
    policy = canonical_policy_name(
        shadow_override_delta=shadow_override_delta,
        apply_readiness=apply_readiness,
    )

    return {
        "schema_version": 1,
        "policy": policy,
        "policy_context": policy_context(policy),
        "policy_status": "draft_not_implemented",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "ready_for_apply_implementation": False,
        "inputs": {key: str(path) for key, path in (paths or {}).items()},
        "observed_merge_preview_count": len(previews),
        "observed_conflict_counts": observed_conflict_counts,
        "summary_source_policy": source_summary_policy(shadow_override_delta),
        "readiness_source_policy": source_readiness_policy(apply_readiness),
        "shadow_override_projected_reduction": projected_event_reduction(shadow_override_delta),
        "remaining_excluded_merge_effect_count": remaining_excluded_merge_effect_count(
            shadow_override_delta=shadow_override_delta,
            apply_readiness=apply_readiness,
            override_subset=override_subset,
        ),
        "canonical_apply_blockers": canonical_apply_blockers(apply_readiness),
        "field_policy": canonical_field_policy(),
        "implementation_requirements": [
            "Canonical apply must be a separate command from preview apply.",
            "Canonical apply must write to a new output directory or atomic temp path, never in-place over source artifacts.",
            "Every merged canonical row must preserve all merged event ids, effect ids, input ids, and source provenance.",
            "Every scalar conflict must be preserved in structured merge metadata before canonical apply can be enabled.",
            "Canonical apply must have a validation pass equivalent to the shadow preview output check.",
        ],
        "notes": [
            "This proposal is report-only and does not implement canonical apply.",
            "The current stream preview is valid for shadow inspection but not sufficient as a canonical merge-body policy.",
        ],
    }


def source_summary_policy(payload: dict[str, Any]) -> str | None:
    policy = payload.get("summary_policy") or payload.get("impact_policy")
    return str(policy) if policy else None


def source_readiness_policy(payload: dict[str, Any]) -> str | None:
    policy = payload.get("apply_readiness_policy") or payload.get("readiness_policy")
    return str(policy) if policy else None


def canonical_policy_name(*, shadow_override_delta: dict[str, Any], apply_readiness: dict[str, Any]) -> str:
    if (
        source_summary_policy(shadow_override_delta) == "entity_resolution_plan_impact_summary_only"
        and source_readiness_policy(apply_readiness) == "entity_resolution_merge_preview_readiness_gate"
    ):
        return CLUSTER_POLICY
    return GENERIC_POLICY


def policy_context(policy: str) -> str:
    if policy == CLUSTER_POLICY:
        return "cluster_shadow_override"
    return "shadow_override"


def projected_event_reduction(payload: dict[str, Any]) -> Any:
    if "override_projected_event_reduction" in payload:
        return payload.get("override_projected_event_reduction")
    merge_impact = payload.get("merge_impact")
    if isinstance(merge_impact, dict):
        return merge_impact.get("projected_event_reduction")
    return None


def remaining_excluded_merge_effect_count(
    *,
    shadow_override_delta: dict[str, Any],
    apply_readiness: dict[str, Any],
    override_subset: dict[str, Any] | None = None,
) -> Any:
    if override_subset and "excluded_merge_effect_count" in override_subset:
        return override_subset.get("excluded_merge_effect_count")
    if "remaining_excluded_merge_effect_count" in shadow_override_delta:
        return shadow_override_delta.get("remaining_excluded_merge_effect_count")
    if "blocking_conflict_item_count" in apply_readiness:
        return apply_readiness.get("blocking_conflict_item_count")
    return None


def canonical_apply_blockers(payload: dict[str, Any]) -> list[dict[str, Any]]:
    blockers = payload.get("canonical_apply_blockers")
    if isinstance(blockers, list):
        return [blocker for blocker in blockers if isinstance(blocker, dict)]
    synthesized: list[dict[str, Any]] = []
    blocker = payload.get("canonical_apply_blocker")
    if blocker:
        synthesized.append(
            {
                "blocker": str(blocker),
                "severity": "hard",
                "reason": "Cluster merge preview readiness gate did not clear canonical apply.",
            }
        )
    blocking_count = payload.get("blocking_conflict_item_count")
    if blocking_count:
        synthesized.append(
            {
                "blocker": "merge_preview_blocking_conflicts_remaining",
                "severity": "hard",
                "count": blocking_count,
                "reason": "Cluster compact merge previews still contain blocking conflicts.",
            }
        )
    return synthesized


def canonical_field_policy() -> dict[str, Any]:
    return {
        "canonical_event_id": {
            "rule": "retain_representative_event_id",
            "requirement": "Representative selection must be deterministic and recorded in merge metadata.",
        },
        "canonical_input_ids": {
            "rule": "union_preserve_first_seen_order",
            "requirement": "All source input ids from merged rows must be retained.",
        },
        "source_provenance": {
            "rule": "json_deduplicated_union",
            "requirement": "No source provenance entry may be dropped during merge.",
        },
        "duplicate_record_count": {
            "rule": "recompute_from_canonical_input_ids",
            "requirement": "Count must equal the merged canonical_input_ids length.",
        },
        "stable_same_values": {
            "rule": "retain_shared_value",
            "fields": [
                "date_iso",
                "time_raw",
                "shape_normalized",
                "type_normalized",
                "location_raw",
                "lat",
                "lon",
            ],
        },
        "scalar_conflicts": {
            "rule": "retain_representative_value_and_preserve_all_conflicting_values",
            "metadata_field": "entity_resolution_canonical_merge_conflicts",
            "requirement": "Conflicting values must include source canonical_event_id, field name, and original value.",
        },
        "summary_description": {
            "rule": "prefer_more_informative_representative_text_with_conflict_preservation",
            "requirement": "Do not concatenate long text blindly; preserve alternates in merge conflict metadata.",
        },
        "coordinates": {
            "rule": "retain_representative_coordinates_unless_explicit_coordinate_policy_accepts_a_better_value",
            "requirement": "Coordinate-distance conflicts require review or explicit source/precision policy.",
        },
        "entity_resolution_metadata": {
            "rule": "append_merge_audit_fields",
            "fields": [
                "entity_resolution_canonical_merged_event_ids",
                "entity_resolution_canonical_effect_ids",
                "entity_resolution_canonical_merge_policy",
                "entity_resolution_canonical_merge_conflicts",
            ],
        },
    }


def collect_conflict_counts(previews: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in previews:
        if not isinstance(item, dict):
            continue
        conflicts = item.get("field_conflicts") if isinstance(item.get("field_conflicts"), dict) else {}
        for field in conflicts:
            field_name = str(field)
            counts[field_name] = counts.get(field_name, 0) + 1
    return dict(sorted(counts.items()))


def validate_merged_event_preview(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("preview_policy") != "entity_resolution_compact_merged_event_preview_only":
        errors.append("preview_policy must be 'entity_resolution_compact_merged_event_preview_only'")
    for flag in (
        "canonical_outputs_mutated",
        "canonical_outputs_mutated_by_plan",
        "preview_outputs_written",
        "auto_merge_performed",
        "decisions_created",
        "override_decisions_created",
    ):
        if flag in payload and payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError(f"merged event preview is not safe for policy proposal: {'; '.join(errors)}")


def validate_shadow_override_delta(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    policy = source_summary_policy(payload)
    if policy not in {
        "entity_resolution_shadow_override_delta_summary",
        "entity_resolution_plan_impact_summary_only",
    }:
        errors.append(
            "summary_policy/impact_policy must be 'entity_resolution_shadow_override_delta_summary' "
            "or 'entity_resolution_plan_impact_summary_only'"
        )
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "decisions_created", "auto_merge_performed"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError(f"shadow override delta is not safe for policy proposal: {'; '.join(errors)}")


def validate_apply_readiness(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    policy = source_readiness_policy(payload)
    if policy not in {
        "entity_resolution_canonical_apply_readiness_gate",
        "entity_resolution_merge_preview_readiness_gate",
    }:
        errors.append(
            "apply_readiness_policy/readiness_policy must be 'entity_resolution_canonical_apply_readiness_gate' "
            "or 'entity_resolution_merge_preview_readiness_gate'"
        )
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "decisions_created", "auto_merge_performed"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if payload.get("ready_for_canonical_apply") is not False:
        errors.append("ready_for_canonical_apply must be false")
    if errors:
        raise ValueError(f"apply readiness report is not safe for policy proposal: {'; '.join(errors)}")


def validate_override_subset(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("subset_policy") != "entity_resolution_shadow_preview_subset_with_analysis_overrides":
        errors.append("subset_policy must be 'entity_resolution_shadow_preview_subset_with_analysis_overrides'")
    if payload.get("effect_policy") != "entity_resolution_plan_only":
        errors.append("effect_policy must be 'entity_resolution_plan_only'")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "auto_merge_performed"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError(f"override subset is not safe for policy proposal: {'; '.join(errors)}")


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
    parser.add_argument("--merged-event-preview", type=Path, default=DEFAULT_MERGED_EVENT_PREVIEW)
    parser.add_argument("--shadow-override-delta", type=Path, default=DEFAULT_SHADOW_OVERRIDE_DELTA)
    parser.add_argument("--apply-readiness", type=Path, default=DEFAULT_APPLY_READINESS)
    parser.add_argument("--override-subset", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = {
        "merged_event_preview": args.merged_event_preview,
        "shadow_override_delta": args.shadow_override_delta,
        "apply_readiness": args.apply_readiness,
    }
    override_subset = read_json(args.override_subset) if args.override_subset else None
    if args.override_subset:
        paths["override_subset"] = args.override_subset
    proposal = propose_entity_resolution_canonical_merge_policy(
        merged_event_preview=read_json(args.merged_event_preview),
        shadow_override_delta=read_json(args.shadow_override_delta),
        apply_readiness=read_json(args.apply_readiness),
        override_subset=override_subset,
        paths=paths,
    )
    write_json(args.output, proposal)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "policy": proposal["policy"],
                "policy_status": proposal["policy_status"],
                "observed_merge_preview_count": proposal["observed_merge_preview_count"],
                "ready_for_apply_implementation": proposal["ready_for_apply_implementation"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
