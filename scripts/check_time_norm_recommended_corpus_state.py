"""Check whether accepted time-normalization merges are already present in a corpus.

This is a read-only/idempotence diagnostic. It does not apply merges or rewrite
canonical outputs. Its main use is checking a later mapped/enriched corpus that
may already include the accepted clean time-normalization replacement rows.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from parser.canonical_schema import clean_text


DEFAULT_EFFECTS_PLAN = Path("data/reports/entity_resolution_cluster_time_norm_recommended_accepted_effects_plan.json")
DEFAULT_MERGE_PATCH = Path("data/reports/entity_resolution_cluster_time_norm_recommended_merge_preview_patch.json")
DEFAULT_DEDUPED_EVENTS = Path("data/canonical_preview_map_enrich_v29_facility_site/deduped_events.jsonl")
DEFAULT_OUTPUT = Path("data/reports/v29_time_norm_recommended_corpus_state_check.json")

CHECK_POLICY = "entity_resolution_time_norm_recommended_corpus_state_check"
APPLIED_STATE = "already_applied"
NOT_APPLIED_STATE = "not_applied"
CONFLICT_STATE = "partial_or_conflicting"


def check_time_norm_recommended_corpus_state(
    *,
    effects_plan: dict[str, Any],
    merge_patch: dict[str, Any],
    deduped_events_path: Path,
    paths: dict[str, Path] | None = None,
) -> dict[str, Any]:
    validate_effects_plan(effects_plan)
    validate_merge_patch(merge_patch)
    effects = [
        effect
        for effect in effects_plan.get("effects") or []
        if isinstance(effect, dict) and effect.get("planned_effect") == "merge_entity_resolution_candidate"
    ]
    patches_by_effect_id = {
        clean_text(patch.get("effect_id")): patch
        for patch in merge_patch.get("patches") or []
        if isinstance(patch, dict) and clean_text(patch.get("effect_id"))
    }
    expected_ids = {
        event_id
        for effect in effects
        for event_id in effect_event_ids(effect, patches_by_effect_id)
    }
    rows_by_id, scanned_event_count = collect_event_rows(deduped_events_path, expected_ids)
    effect_states = []
    state_counts: dict[str, int] = {}
    conflict_count = 0
    for effect in effects:
        effect_id = clean_text(effect.get("effect_id"))
        patch = patches_by_effect_id.get(effect_id) or {}
        merge_ids = effect_event_ids(effect, patches_by_effect_id)
        replacement_id = clean_text(patch.get("replacement_canonical_event_id")) or (sorted(merge_ids)[0] if merge_ids else "")
        suppressed_ids = sorted(event_id for event_id in merge_ids if event_id != replacement_id)
        replacement_row = rows_by_id.get(replacement_id)
        present_suppressed_ids = sorted(event_id for event_id in suppressed_ids if event_id in rows_by_id)
        missing_merge_ids = sorted(event_id for event_id in merge_ids if event_id not in rows_by_id)
        row_merged_ids = set(string_list(replacement_row.get("entity_resolution_canonical_merged_event_ids") if replacement_row else []))
        row_effect_ids = set(string_list(replacement_row.get("entity_resolution_canonical_effect_ids") if replacement_row else []))
        metadata_complete = bool(replacement_row) and set(merge_ids).issubset(row_merged_ids) and effect_id in row_effect_ids
        if replacement_row and not present_suppressed_ids and metadata_complete:
            state = APPLIED_STATE
        elif not any(event_id in rows_by_id for event_id in merge_ids):
            state = NOT_APPLIED_STATE
        else:
            state = CONFLICT_STATE
            conflict_count += 1
        state_counts[state] = state_counts.get(state, 0) + 1
        effect_states.append(
            {
                "effect_id": effect_id,
                "review_item_id": clean_text(effect.get("review_item_id")),
                "state": state,
                "replacement_canonical_event_id": replacement_id,
                "merge_canonical_event_ids": merge_ids,
                "suppressed_canonical_event_ids": suppressed_ids,
                "replacement_present": bool(replacement_row),
                "present_suppressed_ids": present_suppressed_ids,
                "missing_merge_ids": missing_merge_ids,
                "replacement_metadata_complete": metadata_complete,
                "replacement_dedupe_strategy": replacement_row.get("dedupe_strategy") if replacement_row else None,
            }
        )
    all_already_applied = len(effects) > 0 and state_counts.get(APPLIED_STATE, 0) == len(effects)
    return {
        "schema_version": 1,
        "check_policy": CHECK_POLICY,
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "ready_for_runtime_promotion": all_already_applied,
        "candidate_output_needed": not all_already_applied,
        "inputs": {key: str(path) for key, path in (paths or {}).items()},
        "effect_count": len(effects),
        "expected_event_id_count": len(expected_ids),
        "hydrated_expected_event_id_count": len(rows_by_id),
        "scanned_event_count": scanned_event_count,
        "state_counts": dict(sorted(state_counts.items())),
        "already_applied_effect_count": state_counts.get(APPLIED_STATE, 0),
        "not_applied_effect_count": state_counts.get(NOT_APPLIED_STATE, 0),
        "partial_or_conflicting_effect_count": state_counts.get(CONFLICT_STATE, 0),
        "valid": conflict_count == 0 and len(effects) > 0,
        "validation_error_count": conflict_count,
        "effect_states": effect_states,
        "notes": [
            "Read-only corpus state check; no candidate corpus is written.",
            "already_applied requires replacement row presence, suppressed row absence, merged-id metadata, and effect-id metadata.",
            "candidate_output_needed=false means the checked corpus already carries these accepted time-normalization merges.",
        ],
    }


def effect_event_ids(effect: dict[str, Any], patches_by_effect_id: dict[str, dict[str, Any]]) -> list[str]:
    patch = patches_by_effect_id.get(clean_text(effect.get("effect_id"))) or {}
    ids = string_list(patch.get("merge_canonical_event_ids"))
    return ids or string_list(effect.get("merge_canonical_event_ids"))


def collect_event_rows(path: Path, required_event_ids: set[str]) -> tuple[dict[str, dict[str, Any]], int]:
    rows: dict[str, dict[str, Any]] = {}
    scanned = 0
    if not required_event_ids:
        return rows, scanned
    for row in iter_jsonl(path):
        scanned += 1
        event_id = clean_text(row.get("canonical_event_id")) or clean_text(row.get("event_id"))
        if event_id in required_event_ids:
            rows[event_id] = row
            if len(rows) == len(required_event_ids):
                break
    return rows, scanned


def validate_effects_plan(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("effect_policy") != "entity_resolution_plan_only":
        errors.append("effect_policy must be entity_resolution_plan_only")
    for flag in ("canonical_outputs_mutated", "canonical_outputs_mutated_by_plan", "preview_outputs_written", "auto_merge_performed"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError("effects plan is unsafe for corpus-state checking: " + "; ".join(errors))


def validate_merge_patch(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("patch_policy") != "entity_resolution_merge_patch_preview_only":
        errors.append("patch_policy must be entity_resolution_merge_patch_preview_only")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "decisions_created", "auto_merge_performed"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError("merge patch is unsafe for corpus-state checking: " + "; ".join(errors))


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{path} line {line_number} must contain a JSON object.")
            yield payload


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [text for item in value if (text := clean_text(item))]
    text = clean_text(value)
    return [text] if text else []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--effects-plan", type=Path, default=DEFAULT_EFFECTS_PLAN)
    parser.add_argument("--merge-patch", type=Path, default=DEFAULT_MERGE_PATCH)
    parser.add_argument("--deduped-events", type=Path, default=DEFAULT_DEDUPED_EVENTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = {
        "effects_plan": args.effects_plan,
        "merge_patch": args.merge_patch,
        "deduped_events": args.deduped_events,
    }
    report = check_time_norm_recommended_corpus_state(
        effects_plan=read_json(args.effects_plan),
        merge_patch=read_json(args.merge_patch),
        deduped_events_path=args.deduped_events,
        paths=paths,
    )
    write_json(args.output, report)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "valid": report["valid"],
                "ready_for_runtime_promotion": report["ready_for_runtime_promotion"],
                "candidate_output_needed": report["candidate_output_needed"],
                "state_counts": report["state_counts"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
