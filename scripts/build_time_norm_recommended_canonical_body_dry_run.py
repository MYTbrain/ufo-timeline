"""Build full-row canonical body dry-run rows for recommended time merges.

This hydrates full source event rows for the 33 clean recommended
time-normalization candidates and writes only dry-run merged rows. It does not
write a full canonical corpus and does not mutate canonical outputs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable


DEFAULT_EFFECTS_PLAN = Path("data/reports/entity_resolution_cluster_time_norm_recommended_effects_plan.json")
DEFAULT_MERGE_PATCH = Path("data/reports/entity_resolution_cluster_time_norm_recommended_merge_preview_patch.json")
DEFAULT_ORIGINAL_EVENTS = Path("data/canonical_full/deduped_events.jsonl")
DEFAULT_OUTPUT_JSONL = Path("data/reports/entity_resolution_cluster_time_norm_recommended_canonical_body_dry_run.jsonl")
DEFAULT_REPORT_OUTPUT = Path("data/reports/entity_resolution_cluster_time_norm_recommended_canonical_body_dry_run_report.json")

DRY_RUN_POLICY = "entity_resolution_time_norm_recommended_canonical_body_dry_run_only"
MERGE_POLICY = "entity_resolution_cluster_canonical_merge_policy_proposal_v1"
BODY_SOURCE_POLICY = "stable_replacement_id_with_highest_quality_representative_body"

CONFLICT_FIELDS = (
    "date_iso",
    "time_raw",
    "location_raw",
    "lat",
    "lon",
    "coordinate_source",
    "shape_normalized",
    "type_normalized",
    "summary",
    "description",
)


def build_time_norm_recommended_canonical_body_dry_run(
    *,
    effects_plan: dict[str, Any],
    merge_patch: dict[str, Any],
    original_events_path: Path,
    paths: dict[str, Path] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    validate_effects_plan(effects_plan)
    validate_merge_patch(merge_patch)
    effects = [
        effect
        for effect in effects_plan.get("effects") or []
        if isinstance(effect, dict) and effect.get("planned_effect") == "merge_entity_resolution_candidate"
    ]
    patch_by_effect_id = {
        clean_text(patch.get("effect_id")): patch
        for patch in merge_patch.get("patches") or []
        if isinstance(patch, dict)
    }
    required_event_ids = {
        event_id
        for effect in effects
        for event_id in string_list(effect.get("merge_canonical_event_ids"))
    }
    event_rows, scanned_event_count = collect_event_rows(original_events_path, required_event_ids)
    dry_run_rows: list[dict[str, Any]] = []
    missing_effects: list[dict[str, Any]] = []
    for effect in effects:
        event_ids = string_list(effect.get("merge_canonical_event_ids"))
        missing_event_ids = [event_id for event_id in event_ids if event_id not in event_rows]
        if missing_event_ids:
            missing_effects.append(
                {
                    "effect_id": clean_text(effect.get("effect_id")),
                    "review_item_id": clean_text(effect.get("review_item_id")),
                    "missing_event_ids": missing_event_ids,
                }
            )
            continue
        rows = [event_rows[event_id] for event_id in event_ids]
        dry_run_rows.append(build_dry_run_row(effect, rows, patch_by_effect_id=patch_by_effect_id))

    report = {
        "schema_version": 1,
        "dry_run_policy": DRY_RUN_POLICY,
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "inputs": {key: str(path) for key, path in (paths or {}).items()},
        "effect_count": len(effects),
        "required_event_id_count": len(required_event_ids),
        "hydrated_event_count": len(event_rows),
        "missing_event_id_count": len(required_event_ids - set(event_rows)),
        "missing_effect_count": len(missing_effects),
        "dry_run_row_count": len(dry_run_rows),
        "scanned_event_count": scanned_event_count,
        "body_source_policy": BODY_SOURCE_POLICY,
        "merge_policy": MERGE_POLICY,
        "conflict_field_counts": conflict_field_counts(dry_run_rows),
        "missing_effects": missing_effects,
        "notes": [
            "Dry-run rows are full merged row candidates only; no canonical corpus is rewritten.",
            "canonical_event_id follows the stable replacement event ID from the merge patch.",
            "Most body fields are copied from the highest-quality representative row, with all alternate source values preserved in conflict metadata.",
        ],
    }
    return dry_run_rows, report


def build_dry_run_row(
    effect: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    patch_by_effect_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    effect_id = clean_text(effect.get("effect_id"))
    patch = patch_by_effect_id.get(effect_id) or {}
    replacement_event_id = clean_text(patch.get("replacement_canonical_event_id")) or sorted(
        clean_text(row.get("canonical_event_id")) for row in rows
    )[0]
    representative = select_representative_row(rows)
    merged = dict(representative)
    merged_event_ids = sorted(clean_text(row.get("canonical_event_id")) for row in rows)
    input_ids = unique(
        input_id
        for row in rows
        for input_id in string_list(row.get("canonical_input_ids"))
    )
    provenance = unique_dicts(
        item
        for row in rows
        for item in row.get("source_provenance") or []
        if isinstance(item, dict)
    )
    merged["canonical_event_id"] = replacement_event_id
    merged["canonical_input_ids"] = input_ids
    merged["canonical_input_id"] = input_ids[0] if input_ids else merged.get("canonical_input_id")
    merged["duplicate_record_count"] = len(input_ids)
    merged["source_provenance"] = provenance
    merged["dedupe_strategy"] = "entity_resolution_canonical_body_dry_run_merge"
    merged["entity_resolution_canonical_merged_event_ids"] = merged_event_ids
    merged["entity_resolution_canonical_effect_ids"] = [effect_id]
    merged["entity_resolution_canonical_merge_policy"] = MERGE_POLICY
    merged["entity_resolution_canonical_merge_conflicts"] = conflict_metadata(rows)
    merged["entity_resolution_canonical_replacement_event_id"] = replacement_event_id
    merged["entity_resolution_canonical_representative_event_id"] = clean_text(representative.get("canonical_event_id"))
    merged["entity_resolution_canonical_body_source_policy"] = BODY_SOURCE_POLICY
    merged["entity_resolution_canonical_source_event_count"] = len(rows)
    return merged


def conflict_metadata(rows: list[dict[str, Any]]) -> dict[str, Any]:
    conflicts: dict[str, Any] = {}
    for field in CONFLICT_FIELDS:
        source_values = [
            {"canonical_event_id": clean_text(row.get("canonical_event_id")), "value": row.get(field)}
            for row in rows
            if field in row and row.get(field) not in (None, "")
        ]
        distinct_values = unique(source_value["value"] for source_value in source_values)
        if len(distinct_values) > 1:
            conflicts[field] = {
                "values": distinct_values,
                "source_values": source_values,
                "source_value_count": len(source_values),
            }
    return conflicts


def collect_event_rows(path: Path, required_event_ids: set[str]) -> tuple[dict[str, dict[str, Any]], int]:
    rows: dict[str, dict[str, Any]] = {}
    scanned = 0
    if not required_event_ids:
        return rows, scanned
    for row in iter_jsonl(path):
        scanned += 1
        event_id = clean_text(row.get("canonical_event_id"))
        if event_id in required_event_ids:
            rows[event_id] = row
            if len(rows) == len(required_event_ids):
                break
    return rows, scanned


def select_representative_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return max(rows, key=lambda row: (row_quality_score(row), clean_text(row.get("canonical_event_id"))))


def row_quality_score(row: dict[str, Any]) -> tuple[int, int, int, int, int]:
    has_coordinates = int(row.get("lat") is not None and row.get("lon") is not None)
    has_exact_day = int(bool(row.get("date_iso")) and row.get("date_precision") in {None, "day"})
    has_time = int(bool(clean_text(row.get("time_raw"))))
    description_len = len(str(row.get("description") or ""))
    provenance_count = len(row.get("source_provenance")) if isinstance(row.get("source_provenance"), list) else 0
    return (has_coordinates, has_exact_day, has_time, description_len, provenance_count)


def validate_effects_plan(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("effect_policy") != "entity_resolution_plan_only":
        errors.append("effect_policy must be entity_resolution_plan_only")
    for flag in ("canonical_outputs_mutated", "canonical_outputs_mutated_by_plan", "preview_outputs_written", "auto_merge_performed"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError("effects plan is not safe for dry-run building: " + "; ".join(errors))


def validate_merge_patch(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("patch_policy") != "entity_resolution_merge_patch_preview_only":
        errors.append("patch_policy must be entity_resolution_merge_patch_preview_only")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "decisions_created", "auto_merge_performed"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError("merge patch is not safe for dry-run building: " + "; ".join(errors))


def conflict_field_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        conflicts = row.get("entity_resolution_canonical_merge_conflicts")
        if not isinstance(conflicts, dict):
            continue
        for field in conflicts:
            counts[str(field)] = counts.get(str(field), 0) + 1
    return dict(sorted(counts.items()))


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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [text for item in value if (text := clean_text(item))]
    text = clean_text(value)
    return [text] if text else []


def unique(values: Iterable[Any]) -> list[Any]:
    seen: set[str] = set()
    result: list[Any] = []
    for value in values:
        key = json.dumps(value, ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        result.append(value)
        seen.add(key)
    return result


def unique_dicts(values: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(item) for item in unique(values)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--effects-plan", type=Path, default=DEFAULT_EFFECTS_PLAN)
    parser.add_argument("--merge-patch", type=Path, default=DEFAULT_MERGE_PATCH)
    parser.add_argument("--original-events", type=Path, default=DEFAULT_ORIGINAL_EVENTS)
    parser.add_argument("--jsonl-output", type=Path, default=DEFAULT_OUTPUT_JSONL)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = {
        "effects_plan": args.effects_plan,
        "merge_patch": args.merge_patch,
        "original_events": args.original_events,
    }
    rows, report = build_time_norm_recommended_canonical_body_dry_run(
        effects_plan=read_json(args.effects_plan),
        merge_patch=read_json(args.merge_patch),
        original_events_path=args.original_events,
        paths=paths,
    )
    report["outputs"] = {"jsonl": str(args.jsonl_output), "report": str(args.report_output)}
    write_jsonl(args.jsonl_output, rows)
    write_json(args.report_output, report)
    print(
        json.dumps(
            {
                "jsonl_output": str(args.jsonl_output),
                "report_output": str(args.report_output),
                "dry_run_policy": report["dry_run_policy"],
                "dry_run_row_count": report["dry_run_row_count"],
                "missing_event_id_count": report["missing_event_id_count"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
