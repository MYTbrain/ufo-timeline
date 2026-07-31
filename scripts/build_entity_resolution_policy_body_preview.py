"""Build compact ER merged-body previews using the proposed canonical policy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_MERGED_EVENT_PREVIEW = Path("data/reports/entity_resolution_ai_merged_event_preview.json")
DEFAULT_POLICY_PROPOSAL = Path("data/reports/entity_resolution_canonical_merge_policy_proposal.json")
DEFAULT_OVERRIDE_SUBSET = Path("data/reports/entity_resolution_ai_effects_plan_shadow_override_subset.json")
DEFAULT_OUTPUT = Path("data/reports/entity_resolution_policy_body_preview.json")
GENERIC_POLICY = "entity_resolution_canonical_merge_policy_proposal_v1"
CLUSTER_POLICY = "entity_resolution_cluster_canonical_merge_policy_proposal_v1"
GENERIC_PREVIEW_POLICY = "entity_resolution_canonical_merge_body_policy_preview_only"
CLUSTER_PREVIEW_POLICY = "entity_resolution_cluster_canonical_merge_body_policy_preview_only"


def build_entity_resolution_policy_body_preview(
    *,
    merged_event_preview: dict[str, Any],
    policy_proposal: dict[str, Any],
    override_subset: dict[str, Any],
    paths: dict[str, Path] | None = None,
) -> dict[str, Any]:
    validate_merged_event_preview(merged_event_preview)
    validate_policy_proposal(policy_proposal)
    validate_override_subset(override_subset)
    selected_effect_ids = {
        str(effect.get("effect_id"))
        for effect in override_subset.get("effects") or []
        if isinstance(effect, dict) and effect.get("effect_id")
    }
    previews = []
    skipped_preview_count = 0
    policy = str(policy_proposal.get("policy") or "")
    for item in merged_event_preview.get("previews") or []:
        if not isinstance(item, dict):
            continue
        effect_id = str(item.get("effect_id") or "")
        if effect_id not in selected_effect_ids:
            skipped_preview_count += 1
            continue
        previews.append(policy_body_preview_item(item, policy=policy))

    return {
        "schema_version": 1,
        "preview_policy": preview_policy_for_merge_policy(policy),
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "inputs": {key: str(path) for key, path in (paths or {}).items()},
        "policy": policy,
        "policy_context": policy_proposal.get("policy_context") or policy_context(policy),
        "policy_status": policy_proposal.get("policy_status"),
        "selected_effect_count": len(selected_effect_ids),
        "policy_body_preview_count": len(previews),
        "skipped_preview_count": skipped_preview_count,
        "previews": previews,
        "notes": [
            "This is a compact policy-body preview only, not a canonical event corpus.",
            "Conflict metadata is derived from compact source summaries and must be rehydrated from full rows before canonical apply.",
        ],
    }


def policy_body_preview_item(item: dict[str, Any], *, policy: Any) -> dict[str, Any]:
    preview_event = item.get("preview_event") if isinstance(item.get("preview_event"), dict) else {}
    source_summaries = [
        source for source in item.get("source_event_summaries") or [] if isinstance(source, dict)
    ]
    merged_event_ids = preview_event.get("entity_resolution_preview_merged_event_ids") or [
        source.get("canonical_event_id") for source in source_summaries if source.get("canonical_event_id")
    ]
    canonical_input_ids = preview_event.get("canonical_input_ids") or []
    preview = {
        "patch_id": item.get("patch_id"),
        "effect_id": item.get("effect_id"),
        "review_item_id": item.get("review_item_id"),
        "body_policy": "canonical_merge_policy_preview_not_full_event_row",
        "canonical_event_id": preview_event.get("canonical_event_id"),
        "representative_event_id": preview_event.get("representative_event_id"),
        "representative_selection": preview_event.get("representative_selection"),
        "canonical_input_id_count": len(canonical_input_ids),
        "source_event_count": item.get("source_event_count"),
        "entity_resolution_canonical_merged_event_ids": merged_event_ids,
        "entity_resolution_canonical_effect_ids": [item.get("effect_id")] if item.get("effect_id") else [],
        "entity_resolution_canonical_merge_policy": policy,
        "entity_resolution_canonical_merge_conflicts": conflict_metadata(item, source_summaries),
        "representative_fields": preview_event.get("representative_fields") or {},
        "source_provenance_summary": preview_event.get("source_provenance_summary") or {},
    }
    if policy == CLUSTER_POLICY:
        preview.update(
            {
                "cluster_review_id": item.get("review_item_id"),
                "review_type": "entity_resolution_cluster_candidate",
                "entity_resolution_cluster_effect_ids": [item.get("effect_id")] if item.get("effect_id") else [],
            }
        )
    return preview


def conflict_metadata(item: dict[str, Any], source_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    conflicts = item.get("field_conflicts") if isinstance(item.get("field_conflicts"), dict) else {}
    metadata: dict[str, Any] = {}
    for field, values in sorted(conflicts.items()):
        source_values = []
        for source in source_summaries:
            if field not in source:
                continue
            source_values.append(
                {
                    "canonical_event_id": source.get("canonical_event_id"),
                    "value": source.get(field),
                }
            )
        metadata[str(field)] = {
            "values": values if isinstance(values, list) else [values],
            "source_values": source_values,
        }
    return metadata


def validate_merged_event_preview(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("preview_policy") != "entity_resolution_compact_merged_event_preview_only":
        errors.append("preview_policy must be 'entity_resolution_compact_merged_event_preview_only'")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "auto_merge_performed"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError(f"merged event preview is not safe for policy body preview: {'; '.join(errors)}")


def validate_policy_proposal(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("policy") not in {GENERIC_POLICY, CLUSTER_POLICY}:
        errors.append(
            "policy must be 'entity_resolution_canonical_merge_policy_proposal_v1' "
            "or 'entity_resolution_cluster_canonical_merge_policy_proposal_v1'"
        )
    if payload.get("ready_for_apply_implementation") is not False:
        errors.append("ready_for_apply_implementation must be false")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "decisions_created", "auto_merge_performed"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError(f"policy proposal is not safe for policy body preview: {'; '.join(errors)}")


def preview_policy_for_merge_policy(policy: str) -> str:
    if policy == CLUSTER_POLICY:
        return CLUSTER_PREVIEW_POLICY
    return GENERIC_PREVIEW_POLICY


def policy_context(policy: str) -> str:
    if policy == CLUSTER_POLICY:
        return "cluster_shadow_override"
    return "shadow_override"


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
        raise ValueError(f"override subset is not safe for policy body preview: {'; '.join(errors)}")


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
    parser.add_argument("--policy-proposal", type=Path, default=DEFAULT_POLICY_PROPOSAL)
    parser.add_argument("--override-subset", type=Path, default=DEFAULT_OVERRIDE_SUBSET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = {
        "merged_event_preview": args.merged_event_preview,
        "policy_proposal": args.policy_proposal,
        "override_subset": args.override_subset,
    }
    report = build_entity_resolution_policy_body_preview(
        merged_event_preview=read_json(args.merged_event_preview),
        policy_proposal=read_json(args.policy_proposal),
        override_subset=read_json(args.override_subset),
        paths=paths,
    )
    write_json(args.output, report)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "preview_policy": report["preview_policy"],
                "policy_body_preview_count": report["policy_body_preview_count"],
                "skipped_preview_count": report["skipped_preview_count"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
