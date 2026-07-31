"""Validate compact ER policy-body preview metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_POLICY_BODY_PREVIEW = Path("data/reports/entity_resolution_policy_body_preview.json")
DEFAULT_OUTPUT = Path("data/reports/entity_resolution_policy_body_preview_check.json")

EXPECTED_PREVIEW_POLICY = "entity_resolution_canonical_merge_body_policy_preview_only"
EXPECTED_CLUSTER_PREVIEW_POLICY = "entity_resolution_cluster_canonical_merge_body_policy_preview_only"
EXPECTED_BODY_POLICY = "canonical_merge_policy_preview_not_full_event_row"
EXPECTED_POLICY = "entity_resolution_canonical_merge_policy_proposal_v1"
EXPECTED_CLUSTER_POLICY = "entity_resolution_cluster_canonical_merge_policy_proposal_v1"


def check_entity_resolution_policy_body_preview(
    *,
    policy_body_preview: dict[str, Any],
    preview_path: Path | None = None,
) -> dict[str, Any]:
    validate_preview_safety(policy_body_preview)
    previews = policy_body_preview.get("previews") if isinstance(policy_body_preview.get("previews"), list) else []
    validation_errors = []
    conflict_field_counts: dict[str, int] = {}
    seen_effect_ids: set[str] = set()
    seen_review_item_ids: set[str] = set()
    duplicate_effect_ids = 0
    duplicate_review_item_ids = 0
    invalid_conflict_metadata_count = 0
    missing_required_field_count = 0
    sample_previews = []

    expected_count = int(policy_body_preview.get("policy_body_preview_count") or 0)
    if len(previews) != expected_count:
        validation_errors.append(
            {
                "error": "policy_body_preview_count_mismatch",
                "expected": expected_count,
                "actual": len(previews),
            }
        )

    selected_effect_count = int(policy_body_preview.get("selected_effect_count") or 0)
    if selected_effect_count != expected_count:
        validation_errors.append(
            {
                "error": "selected_effect_count_mismatch",
                "selected_effect_count": selected_effect_count,
                "policy_body_preview_count": expected_count,
            }
        )

    for index, preview in enumerate(previews, start=1):
        if not isinstance(preview, dict):
            validation_errors.append({"error": "preview_not_object", "index": index})
            continue
        missing_fields = required_missing_fields(preview)
        if missing_fields:
            missing_required_field_count += len(missing_fields)
            validation_errors.append({"error": "missing_required_fields", "index": index, "fields": missing_fields})

        effect_id = clean_text(preview.get("effect_id"))
        review_item_id = clean_text(preview.get("review_item_id"))
        if effect_id:
            if effect_id in seen_effect_ids:
                duplicate_effect_ids += 1
            seen_effect_ids.add(effect_id)
        if review_item_id:
            if review_item_id in seen_review_item_ids:
                duplicate_review_item_ids += 1
            seen_review_item_ids.add(review_item_id)

        if preview.get("body_policy") != EXPECTED_BODY_POLICY:
            validation_errors.append(
                {
                    "error": "unexpected_body_policy",
                    "index": index,
                    "body_policy": preview.get("body_policy"),
                }
            )
        if preview.get("entity_resolution_canonical_merge_policy") not in {EXPECTED_POLICY, EXPECTED_CLUSTER_POLICY}:
            validation_errors.append(
                {
                    "error": "unexpected_merge_policy",
                    "index": index,
                    "policy": preview.get("entity_resolution_canonical_merge_policy"),
                }
            )

        merged_ids = string_set(preview.get("entity_resolution_canonical_merged_event_ids"))
        source_event_count = int(preview.get("source_event_count") or 0)
        if source_event_count and len(merged_ids) < source_event_count:
            validation_errors.append(
                {
                    "error": "merged_event_id_count_below_source_event_count",
                    "index": index,
                    "source_event_count": source_event_count,
                    "merged_event_id_count": len(merged_ids),
                }
            )

        canonical_input_count = int(preview.get("canonical_input_id_count") or 0)
        if source_event_count and canonical_input_count < source_event_count:
            validation_errors.append(
                {
                    "error": "canonical_input_count_below_source_event_count",
                    "index": index,
                    "source_event_count": source_event_count,
                    "canonical_input_id_count": canonical_input_count,
                }
            )

        effect_ids = string_set(preview.get("entity_resolution_canonical_effect_ids"))
        if effect_id and effect_id not in effect_ids:
            validation_errors.append(
                {
                    "error": "effect_id_missing_from_merge_audit_ids",
                    "index": index,
                    "effect_id": effect_id,
                }
            )

        conflict_errors = validate_conflicts(preview, merged_ids, index=index)
        if conflict_errors:
            invalid_conflict_metadata_count += len(conflict_errors)
            validation_errors.extend(conflict_errors)
        conflicts = preview.get("entity_resolution_canonical_merge_conflicts")
        if isinstance(conflicts, dict):
            for field in conflicts:
                field_name = str(field)
                conflict_field_counts[field_name] = conflict_field_counts.get(field_name, 0) + 1

        if len(sample_previews) < 10:
            sample_previews.append(
                {
                    "effect_id": effect_id,
                    "review_item_id": review_item_id,
                    "canonical_event_id": preview.get("canonical_event_id"),
                    "conflict_fields": sorted((conflicts or {}).keys()) if isinstance(conflicts, dict) else [],
                }
            )

    if duplicate_effect_ids:
        validation_errors.append({"error": "duplicate_effect_ids", "count": duplicate_effect_ids})
    if duplicate_review_item_ids:
        validation_errors.append({"error": "duplicate_review_item_ids", "count": duplicate_review_item_ids})

    return {
        "schema_version": 1,
        "check_policy": "entity_resolution_policy_body_preview_check",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "inputs": {
            "policy_body_preview": str(preview_path) if preview_path else None,
        },
        "policy": policy_body_preview.get("policy"),
        "policy_body_preview_count": len(previews),
        "expected_policy_body_preview_count": expected_count,
        "selected_effect_count": selected_effect_count,
        "duplicate_effect_id_count": duplicate_effect_ids,
        "duplicate_review_item_id_count": duplicate_review_item_ids,
        "missing_required_field_count": missing_required_field_count,
        "invalid_conflict_metadata_count": invalid_conflict_metadata_count,
        "conflict_field_counts": dict(sorted(conflict_field_counts.items())),
        "valid": not validation_errors,
        "validation_errors": validation_errors,
        "sample_previews": sample_previews,
    }


def required_missing_fields(preview: dict[str, Any]) -> list[str]:
    required = [
        "patch_id",
        "effect_id",
        "review_item_id",
        "body_policy",
        "canonical_event_id",
        "representative_event_id",
        "canonical_input_id_count",
        "source_event_count",
        "entity_resolution_canonical_merged_event_ids",
        "entity_resolution_canonical_effect_ids",
        "entity_resolution_canonical_merge_policy",
        "entity_resolution_canonical_merge_conflicts",
    ]
    missing = [field for field in required if preview.get(field) in (None, "", [])]
    if preview.get("entity_resolution_canonical_merge_policy") == EXPECTED_CLUSTER_POLICY:
        for field in ("cluster_review_id", "review_type", "entity_resolution_cluster_effect_ids"):
            if preview.get(field) in (None, "", []):
                missing.append(field)
    return missing


def validate_conflicts(preview: dict[str, Any], merged_ids: set[str], *, index: int) -> list[dict[str, Any]]:
    conflicts = preview.get("entity_resolution_canonical_merge_conflicts")
    if not isinstance(conflicts, dict):
        return [{"error": "merge_conflicts_not_object", "index": index}]
    errors = []
    for field, conflict in conflicts.items():
        if not isinstance(conflict, dict):
            errors.append({"error": "conflict_not_object", "index": index, "field": field})
            continue
        values = conflict.get("values")
        if not isinstance(values, list) or len(values) < 2:
            errors.append({"error": "conflict_values_invalid", "index": index, "field": field})
        source_values = conflict.get("source_values")
        if not isinstance(source_values, list):
            errors.append({"error": "conflict_source_values_not_list", "index": index, "field": field})
            continue
        for source_value in source_values:
            if not isinstance(source_value, dict):
                errors.append({"error": "conflict_source_value_not_object", "index": index, "field": field})
                continue
            event_id = clean_text(source_value.get("canonical_event_id"))
            if event_id and event_id not in merged_ids:
                errors.append(
                    {
                        "error": "conflict_source_event_id_not_in_merged_ids",
                        "index": index,
                        "field": field,
                        "canonical_event_id": event_id,
                    }
                )
    return errors


def validate_preview_safety(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("preview_policy") not in {EXPECTED_PREVIEW_POLICY, EXPECTED_CLUSTER_PREVIEW_POLICY}:
        errors.append(
            f"preview_policy must be '{EXPECTED_PREVIEW_POLICY}' or '{EXPECTED_CLUSTER_PREVIEW_POLICY}'"
        )
    if payload.get("policy") not in {EXPECTED_POLICY, EXPECTED_CLUSTER_POLICY}:
        errors.append(f"policy must be '{EXPECTED_POLICY}' or '{EXPECTED_CLUSTER_POLICY}'")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "decisions_created", "auto_merge_performed"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if payload.get("ready_for_canonical_apply") is not False:
        errors.append("ready_for_canonical_apply must be false")
    if errors:
        raise ValueError(f"policy body preview is not safe to check: {'; '.join(errors)}")


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def string_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {text for item in value if (text := clean_text(item))}


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
    parser.add_argument("--policy-body-preview", type=Path, default=DEFAULT_POLICY_BODY_PREVIEW)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    preview = read_json(args.policy_body_preview)
    report = check_entity_resolution_policy_body_preview(
        policy_body_preview=preview,
        preview_path=args.policy_body_preview,
    )
    write_json(args.output, report)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "check_policy": report["check_policy"],
                "valid": report["valid"],
                "policy_body_preview_count": report["policy_body_preview_count"],
                "invalid_conflict_metadata_count": report["invalid_conflict_metadata_count"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
