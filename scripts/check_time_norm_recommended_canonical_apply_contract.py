"""Check the full-row canonical apply contract for the recommended time lane.

This report verifies what a canonical apply would need to preserve for the
33 clean time-normalization candidates, without writing or mutating canonical
outputs. It compares the original canonical event corpus with the preview-only
output and validates merge groups, replacement IDs, suppressed IDs, untouched
row identity, input/provenance union preservation, deferred-candidate exclusion,
and policy conflict classification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


DEFAULT_EFFECTS_PLAN = Path("data/reports/entity_resolution_cluster_time_norm_recommended_effects_plan.json")
DEFAULT_MERGE_PATCH = Path("data/reports/entity_resolution_cluster_time_norm_recommended_merge_preview_patch.json")
DEFAULT_RECOMMENDATIONS = Path("data/reports/entity_resolution_cluster_time_norm_source_review_recommendations.json")
DEFAULT_POLICY_CONFLICT_CLASSIFICATION = Path(
    "data/reports/entity_resolution_cluster_time_norm_recommended_policy_conflict_classification.json"
)
DEFAULT_ORIGINAL_EVENTS = Path("data/canonical_full/deduped_events.jsonl")
DEFAULT_PREVIEW_EVENTS = Path("data/canonical_preview_entity_resolution_cluster_time_norm_recommended/deduped_events.jsonl")
DEFAULT_PREVIEW_OUTPUT_CHECK = Path("data/reports/entity_resolution_cluster_time_norm_recommended_preview_output_check.json")
DEFAULT_OUTPUT = Path("data/reports/entity_resolution_cluster_time_norm_recommended_canonical_apply_contract_check.json")

CONTRACT_POLICY = "entity_resolution_time_norm_recommended_canonical_apply_contract_check"


def check_time_norm_recommended_canonical_apply_contract(
    *,
    effects_plan: dict[str, Any],
    merge_patch: dict[str, Any],
    recommendations: dict[str, Any],
    policy_conflict_classification: dict[str, Any],
    original_events_path: Path,
    preview_events_path: Path,
    preview_output_check: dict[str, Any],
    paths: dict[str, Path] | None = None,
) -> dict[str, Any]:
    validate_effects_plan(effects_plan)
    validate_merge_patch(merge_patch)
    validate_recommendations(recommendations)
    validate_policy_conflict_classification(policy_conflict_classification)
    validate_preview_output_check(preview_output_check)

    effects = [
        effect
        for effect in effects_plan.get("effects") or []
        if isinstance(effect, dict) and effect.get("planned_effect") == "merge_entity_resolution_candidate"
    ]
    patches = [patch for patch in merge_patch.get("patches") or [] if isinstance(patch, dict)]
    patch_by_effect_id = {clean_text(patch.get("effect_id")): patch for patch in patches}
    deferred_review_item_ids = {
        clean_text(item.get("review_item_id"))
        for item in recommendations.get("recommendations") or []
        if isinstance(item, dict) and clean_text(item.get("recommendation")) != "recommend_same_event"
    }
    classification_by_review_id = {
        clean_text(item.get("review_item_id")): item
        for item in policy_conflict_classification.get("items") or []
        if isinstance(item, dict)
    }

    validation_errors: list[dict[str, Any]] = []
    validation_errors.extend(validate_effect_groups(effects))
    validation_errors.extend(validate_patch_alignment(effects, patch_by_effect_id))
    validation_errors.extend(validate_deferred_absence(effects, deferred_review_item_ids))
    validation_errors.extend(validate_policy_classifications(effects, classification_by_review_id))

    touched_event_ids = {
        event_id
        for effect in effects
        for event_id in string_list(effect.get("merge_canonical_event_ids"))
    }
    replacement_event_ids = {
        expected_replacement_event_id(effect, patch_by_effect_id)
        for effect in effects
        if expected_replacement_event_id(effect, patch_by_effect_id)
    }
    suppressed_event_ids = touched_event_ids - replacement_event_ids

    corpus_result = compare_original_and_preview_corpus(
        original_events_path=original_events_path,
        preview_events_path=preview_events_path,
        touched_event_ids=touched_event_ids,
    )
    validation_errors.extend(corpus_result["validation_errors"])
    touched_rows = corpus_result["touched_rows"]
    preview_merge_rows = corpus_result["preview_merge_rows"]
    preview_merge_rows_by_effect = preview_rows_by_effect_id(preview_merge_rows)
    validation_errors.extend(
        validate_preview_merge_rows(
            effects=effects,
            patch_by_effect_id=patch_by_effect_id,
            touched_rows=touched_rows,
            preview_merge_rows_by_effect=preview_merge_rows_by_effect,
        )
    )

    expected_reduction = sum(max(0, len(string_list(effect.get("merge_canonical_event_ids"))) - 1) for effect in effects)
    expected_preview_rows = corpus_result["original_row_count"] - expected_reduction
    if corpus_result["preview_row_count"] != expected_preview_rows:
        validation_errors.append(
            {
                "error": "preview_row_count_contract_mismatch",
                "expected": expected_preview_rows,
                "actual": corpus_result["preview_row_count"],
            }
        )
    if corpus_result["preview_row_count"] != int(preview_output_check.get("row_count") or 0):
        validation_errors.append(
            {
                "error": "preview_output_check_row_count_mismatch",
                "output_check_row_count": int(preview_output_check.get("row_count") or 0),
                "contract_preview_row_count": corpus_result["preview_row_count"],
            }
        )
    if len(preview_merge_rows) != int(preview_output_check.get("preview_merge_count") or 0):
        validation_errors.append(
            {
                "error": "preview_output_check_merge_count_mismatch",
                "output_check_preview_merge_count": int(preview_output_check.get("preview_merge_count") or 0),
                "contract_preview_merge_count": len(preview_merge_rows),
            }
        )

    return {
        "schema_version": 1,
        "contract_policy": CONTRACT_POLICY,
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "inputs": {key: str(path) for key, path in (paths or {}).items()},
        "effect_count": len(effects),
        "merge_patch_count": len(patches),
        "touched_event_count": len(touched_event_ids),
        "replacement_event_count": len(replacement_event_ids),
        "suppressed_event_count": len(suppressed_event_ids),
        "deferred_review_item_count": len(deferred_review_item_ids),
        "original_row_count": corpus_result["original_row_count"],
        "preview_row_count": corpus_result["preview_row_count"],
        "expected_preview_row_count": expected_preview_rows,
        "preview_merge_count": len(preview_merge_rows),
        "untouched_row_count": corpus_result["untouched_row_count"],
        "untouched_hash_mismatch_count": corpus_result["untouched_hash_mismatch_count"],
        "missing_touched_event_ids": sorted(touched_event_ids - set(touched_rows)),
        "suppressed_event_ids_present_in_preview": sorted(suppressed_event_ids & corpus_result["preview_event_ids"]),
        "replacement_event_ids_missing_from_preview": sorted(replacement_event_ids - corpus_result["preview_event_ids"]),
        "contract_valid": not validation_errors,
        "validation_error_count": len(validation_errors),
        "validation_errors": validation_errors,
        "notes": [
            "This is a full-row contract check only; it does not write canonical outputs.",
            "ready_for_canonical_apply remains false because no canonical apply command has been implemented.",
        ],
    }


def validate_effects_plan(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("effect_policy") != "entity_resolution_plan_only":
        errors.append("effect_policy must be entity_resolution_plan_only")
    for flag in ("canonical_outputs_mutated", "canonical_outputs_mutated_by_plan", "preview_outputs_written", "auto_merge_performed"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError("effects plan is not safe for contract checking: " + "; ".join(errors))


def validate_merge_patch(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("patch_policy") != "entity_resolution_merge_patch_preview_only":
        errors.append("patch_policy must be entity_resolution_merge_patch_preview_only")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "decisions_created", "auto_merge_performed"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError("merge patch is not safe for contract checking: " + "; ".join(errors))


def validate_recommendations(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("recommendation_policy") != "entity_resolution_time_norm_auto_recommendation_only":
        errors.append("recommendation_policy must be entity_resolution_time_norm_auto_recommendation_only")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "decisions_created", "decision_outputs_created", "validated_decisions_created", "auto_merge_performed", "ready_for_canonical_apply"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError("recommendations report is not safe for contract checking: " + "; ".join(errors))


def validate_policy_conflict_classification(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("classification_policy") != "entity_resolution_time_norm_recommended_policy_conflict_classification_only":
        errors.append("classification_policy must be entity_resolution_time_norm_recommended_policy_conflict_classification_only")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "decisions_created", "auto_merge_performed", "ready_for_canonical_apply"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if int((payload.get("summary") or {}).get("blocking_preview_count") or 0) != 0:
        errors.append("blocking_preview_count must be 0")
    if errors:
        raise ValueError("policy conflict classification is not safe for contract checking: " + "; ".join(errors))


def validate_preview_output_check(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("check_policy") != "entity_resolution_shadow_preview_output_check":
        errors.append("check_policy must be entity_resolution_shadow_preview_output_check")
    if payload.get("valid") is not True:
        errors.append("valid must be true")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "auto_merge_performed"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError("preview output check is not safe for contract checking: " + "; ".join(errors))


def validate_effect_groups(effects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    event_to_effects: dict[str, list[str]] = {}
    for effect in effects:
        effect_id = clean_text(effect.get("effect_id"))
        event_ids = string_list(effect.get("merge_canonical_event_ids"))
        if len(event_ids) < 2:
            errors.append({"error": "effect_requires_at_least_two_merge_event_ids", "effect_id": effect_id})
        if len(event_ids) != len(set(event_ids)):
            errors.append({"error": "effect_has_duplicate_merge_event_ids", "effect_id": effect_id})
        for event_id in event_ids:
            event_to_effects.setdefault(event_id, []).append(effect_id)
    overlaps = {
        event_id: effect_ids
        for event_id, effect_ids in event_to_effects.items()
        if len(effect_ids) > 1
    }
    if overlaps:
        errors.append({"error": "canonical_event_id_appears_in_multiple_merge_groups", "overlaps": overlaps})
    return errors


def validate_patch_alignment(effects: list[dict[str, Any]], patch_by_effect_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    for effect in effects:
        effect_id = clean_text(effect.get("effect_id"))
        patch = patch_by_effect_id.get(effect_id)
        if patch is None:
            errors.append({"error": "missing_merge_patch_for_effect", "effect_id": effect_id})
            continue
        effect_ids = sorted(string_list(effect.get("merge_canonical_event_ids")))
        patch_ids = sorted(string_list(patch.get("merge_canonical_event_ids")))
        if effect_ids != patch_ids:
            errors.append({"error": "merge_patch_event_ids_mismatch", "effect_id": effect_id})
        replacement = clean_text(patch.get("replacement_canonical_event_id"))
        expected = effect_ids[0] if effect_ids else ""
        if replacement != expected:
            errors.append(
                {
                    "error": "replacement_event_id_policy_mismatch",
                    "effect_id": effect_id,
                    "expected": expected,
                    "actual": replacement,
                }
            )
    return errors


def validate_deferred_absence(effects: list[dict[str, Any]], deferred_review_item_ids: set[str]) -> list[dict[str, Any]]:
    return [
        {
            "error": "deferred_recommendation_present_in_effects_plan",
            "review_item_id": clean_text(effect.get("review_item_id")),
            "effect_id": clean_text(effect.get("effect_id")),
        }
        for effect in effects
        if clean_text(effect.get("review_item_id")) in deferred_review_item_ids
    ]


def validate_policy_classifications(
    effects: list[dict[str, Any]],
    classification_by_review_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    for effect in effects:
        review_item_id = clean_text(effect.get("review_item_id"))
        classification = classification_by_review_id.get(review_item_id)
        if classification is None:
            errors.append({"error": "missing_policy_conflict_classification", "review_item_id": review_item_id})
            continue
        if classification.get("blockers"):
            errors.append(
                {
                    "error": "policy_conflict_classification_has_blockers",
                    "review_item_id": review_item_id,
                    "blockers": classification.get("blockers"),
                }
            )
        if clean_text(classification.get("policy_action")) != "candidate_for_final_policy_after_decision_acceptance":
            errors.append(
                {
                    "error": "policy_conflict_classification_not_apply_candidate",
                    "review_item_id": review_item_id,
                    "policy_action": classification.get("policy_action"),
                }
            )
    return errors


def compare_original_and_preview_corpus(
    *,
    original_events_path: Path,
    preview_events_path: Path,
    touched_event_ids: set[str],
) -> dict[str, Any]:
    validation_errors: list[dict[str, Any]] = []
    touched_rows: dict[str, dict[str, Any]] = {}
    preview_merge_rows: list[dict[str, Any]] = []
    preview_event_ids: set[str] = set()
    duplicate_preview_event_ids: set[str] = set()
    untouched_hash_mismatch_count = 0
    untouched_row_count = 0
    original_row_count = 0
    preview_row_count = 0

    with preview_events_path.open("r", encoding="utf-8") as preview_handle:
        preview_iter = iter(preview_handle)
        for original_line in original_events_path.open("r", encoding="utf-8"):
            if not original_line.strip():
                continue
            original_row_count += 1
            original = json.loads(original_line)
            event_id = clean_text(original.get("canonical_event_id"))
            if event_id in touched_event_ids:
                touched_rows[event_id] = original
                continue
            preview_line = next_nonempty_line(preview_iter)
            if preview_line is None:
                validation_errors.append({"error": "preview_ended_before_untouched_rows_complete"})
                break
            preview_row_count += 1
            preview = json.loads(preview_line)
            preview_event_id = clean_text(preview.get("canonical_event_id"))
            if preview_event_id in preview_event_ids:
                duplicate_preview_event_ids.add(preview_event_id)
            preview_event_ids.add(preview_event_id)
            if preview.get("dedupe_strategy") == "entity_resolution_preview_merge":
                validation_errors.append(
                    {
                        "error": "preview_merge_row_appeared_before_untouched_rows_complete",
                        "preview_event_id": preview_event_id,
                    }
                )
            if preview_event_id != event_id:
                validation_errors.append(
                    {
                        "error": "untouched_row_event_id_order_mismatch",
                        "expected": event_id,
                        "actual": preview_event_id,
                    }
                )
            if stable_row_digest(original) != stable_row_digest(preview):
                untouched_hash_mismatch_count += 1
                if untouched_hash_mismatch_count <= 10:
                    validation_errors.append({"error": "untouched_row_hash_mismatch", "canonical_event_id": event_id})
            untouched_row_count += 1

        for preview_line in preview_iter:
            if not preview_line.strip():
                continue
            preview_row_count += 1
            preview = json.loads(preview_line)
            preview_event_id = clean_text(preview.get("canonical_event_id"))
            if preview_event_id in preview_event_ids:
                duplicate_preview_event_ids.add(preview_event_id)
            preview_event_ids.add(preview_event_id)
            if preview.get("dedupe_strategy") == "entity_resolution_preview_merge":
                preview_merge_rows.append(preview)
            else:
                validation_errors.append(
                    {
                        "error": "non_merge_row_after_untouched_rows_complete",
                        "canonical_event_id": preview_event_id,
                    }
                )
    if duplicate_preview_event_ids:
        validation_errors.append(
            {
                "error": "duplicate_preview_canonical_event_ids",
                "canonical_event_ids": sorted(duplicate_preview_event_ids),
            }
        )
    return {
        "original_row_count": original_row_count,
        "preview_row_count": preview_row_count,
        "untouched_row_count": untouched_row_count,
        "untouched_hash_mismatch_count": untouched_hash_mismatch_count,
        "touched_rows": touched_rows,
        "preview_merge_rows": preview_merge_rows,
        "preview_event_ids": preview_event_ids,
        "validation_errors": validation_errors,
    }


def validate_preview_merge_rows(
    *,
    effects: list[dict[str, Any]],
    patch_by_effect_id: dict[str, dict[str, Any]],
    touched_rows: dict[str, dict[str, Any]],
    preview_merge_rows_by_effect: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    for effect in effects:
        effect_id = clean_text(effect.get("effect_id"))
        event_ids = string_list(effect.get("merge_canonical_event_ids"))
        rows = [touched_rows[event_id] for event_id in event_ids if event_id in touched_rows]
        if len(rows) != len(event_ids):
            errors.append(
                {
                    "error": "missing_touched_rows_for_effect",
                    "effect_id": effect_id,
                    "missing_event_ids": sorted(set(event_ids) - set(touched_rows)),
                }
            )
            continue
        preview_row = preview_merge_rows_by_effect.get(effect_id)
        if preview_row is None:
            errors.append({"error": "missing_preview_merge_row_for_effect", "effect_id": effect_id})
            continue
        expected_replacement = expected_replacement_event_id(effect, patch_by_effect_id)
        if clean_text(preview_row.get("canonical_event_id")) != expected_replacement:
            errors.append(
                {
                    "error": "preview_merge_replacement_id_mismatch",
                    "effect_id": effect_id,
                    "expected": expected_replacement,
                    "actual": clean_text(preview_row.get("canonical_event_id")),
                }
            )
        if sorted(string_list(preview_row.get("entity_resolution_preview_merged_event_ids"))) != sorted(event_ids):
            errors.append({"error": "preview_merge_event_ids_mismatch", "effect_id": effect_id})
        expected_input_ids = sorted(
            {
                input_id
                for row in rows
                for input_id in string_list(row.get("canonical_input_ids"))
            }
        )
        if sorted(string_list(preview_row.get("canonical_input_ids"))) != expected_input_ids:
            errors.append({"error": "preview_merge_canonical_input_ids_mismatch", "effect_id": effect_id})
        expected_provenance_keys = {
            stable_row_digest(item)
            for row in rows
            for item in row.get("source_provenance") or []
            if isinstance(item, dict)
        }
        preview_provenance_keys = {
            stable_row_digest(item)
            for item in preview_row.get("source_provenance") or []
            if isinstance(item, dict)
        }
        if preview_provenance_keys != expected_provenance_keys:
            errors.append({"error": "preview_merge_source_provenance_union_mismatch", "effect_id": effect_id})
        if int(preview_row.get("duplicate_record_count") or 0) != len(expected_input_ids):
            errors.append(
                {
                    "error": "preview_merge_duplicate_record_count_mismatch",
                    "effect_id": effect_id,
                    "expected": len(expected_input_ids),
                    "actual": int(preview_row.get("duplicate_record_count") or 0),
                }
            )
    return errors


def preview_rows_by_effect_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_effect: dict[str, dict[str, Any]] = {}
    for row in rows:
        for effect_id in string_list(row.get("entity_resolution_preview_effect_ids")):
            by_effect[effect_id] = row
    return by_effect


def expected_replacement_event_id(effect: dict[str, Any], patch_by_effect_id: dict[str, dict[str, Any]]) -> str:
    effect_id = clean_text(effect.get("effect_id"))
    patch = patch_by_effect_id.get(effect_id) or {}
    replacement = clean_text(patch.get("replacement_canonical_event_id"))
    if replacement:
        return replacement
    event_ids = sorted(string_list(effect.get("merge_canonical_event_ids")))
    return event_ids[0] if event_ids else ""


def next_nonempty_line(lines: Iterable[str]) -> str | None:
    for line in lines:
        if line.strip():
            return line
    return None


def stable_row_digest(row: Any) -> str:
    return hashlib.sha256(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


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
    parser.add_argument("--effects-plan", type=Path, default=DEFAULT_EFFECTS_PLAN)
    parser.add_argument("--merge-patch", type=Path, default=DEFAULT_MERGE_PATCH)
    parser.add_argument("--recommendations", type=Path, default=DEFAULT_RECOMMENDATIONS)
    parser.add_argument("--policy-conflict-classification", type=Path, default=DEFAULT_POLICY_CONFLICT_CLASSIFICATION)
    parser.add_argument("--original-events", type=Path, default=DEFAULT_ORIGINAL_EVENTS)
    parser.add_argument("--preview-events", type=Path, default=DEFAULT_PREVIEW_EVENTS)
    parser.add_argument("--preview-output-check", type=Path, default=DEFAULT_PREVIEW_OUTPUT_CHECK)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = {
        "effects_plan": args.effects_plan,
        "merge_patch": args.merge_patch,
        "recommendations": args.recommendations,
        "policy_conflict_classification": args.policy_conflict_classification,
        "original_events": args.original_events,
        "preview_events": args.preview_events,
        "preview_output_check": args.preview_output_check,
    }
    report = check_time_norm_recommended_canonical_apply_contract(
        effects_plan=read_json(args.effects_plan),
        merge_patch=read_json(args.merge_patch),
        recommendations=read_json(args.recommendations),
        policy_conflict_classification=read_json(args.policy_conflict_classification),
        original_events_path=args.original_events,
        preview_events_path=args.preview_events,
        preview_output_check=read_json(args.preview_output_check),
        paths=paths,
    )
    write_json(args.output, report)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "contract_policy": report["contract_policy"],
                "contract_valid": report["contract_valid"],
                "validation_error_count": report["validation_error_count"],
                "preview_row_count": report["preview_row_count"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if report["contract_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
