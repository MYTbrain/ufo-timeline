"""Validate full-row canonical body dry-run rows for recommended time merges."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable


DEFAULT_DRY_RUN_JSONL = Path("data/reports/entity_resolution_cluster_time_norm_recommended_canonical_body_dry_run.jsonl")
DEFAULT_DRY_RUN_REPORT = Path("data/reports/entity_resolution_cluster_time_norm_recommended_canonical_body_dry_run_report.json")
DEFAULT_OUTPUT = Path("data/reports/entity_resolution_cluster_time_norm_recommended_canonical_body_dry_run_check.json")

EXPECTED_DRY_RUN_POLICY = "entity_resolution_time_norm_recommended_canonical_body_dry_run_only"
EXPECTED_MERGE_POLICY = "entity_resolution_cluster_canonical_merge_policy_proposal_v1"
EXPECTED_BODY_SOURCE_POLICY = "stable_replacement_id_with_highest_quality_representative_body"


def check_time_norm_recommended_canonical_body_dry_run(
    *,
    dry_run_rows: list[dict[str, Any]],
    dry_run_report: dict[str, Any],
    paths: dict[str, Path] | None = None,
) -> dict[str, Any]:
    validate_dry_run_report(dry_run_report)
    validation_errors: list[dict[str, Any]] = []
    expected_count = int(dry_run_report.get("dry_run_row_count") or 0)
    if len(dry_run_rows) != expected_count:
        validation_errors.append({"error": "dry_run_row_count_mismatch", "expected": expected_count, "actual": len(dry_run_rows)})
    seen_event_ids: set[str] = set()
    duplicate_event_ids: set[str] = set()
    conflict_field_counts: dict[str, int] = {}
    incomplete_conflict_source_values = 0
    for index, row in enumerate(dry_run_rows, start=1):
        event_id = clean_text(row.get("canonical_event_id"))
        if event_id in seen_event_ids:
            duplicate_event_ids.add(event_id)
        seen_event_ids.add(event_id)
        validation_errors.extend(validate_row(row, index=index))
        conflicts = row.get("entity_resolution_canonical_merge_conflicts")
        if isinstance(conflicts, dict):
            for field, conflict in conflicts.items():
                conflict_field_counts[str(field)] = conflict_field_counts.get(str(field), 0) + 1
                if not conflict_has_complete_source_values(conflict, row):
                    incomplete_conflict_source_values += 1
                    validation_errors.append(
                        {
                            "error": "incomplete_conflict_source_values",
                            "index": index,
                            "canonical_event_id": event_id,
                            "field": str(field),
                        }
                    )
    if duplicate_event_ids:
        validation_errors.append({"error": "duplicate_dry_run_canonical_event_ids", "canonical_event_ids": sorted(duplicate_event_ids)})
    return {
        "schema_version": 1,
        "check_policy": "entity_resolution_time_norm_recommended_canonical_body_dry_run_check",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "inputs": {key: str(path) for key, path in (paths or {}).items()},
        "dry_run_row_count": len(dry_run_rows),
        "expected_dry_run_row_count": expected_count,
        "conflict_field_counts": dict(sorted(conflict_field_counts.items())),
        "incomplete_conflict_source_value_count": incomplete_conflict_source_values,
        "valid": not validation_errors,
        "validation_error_count": len(validation_errors),
        "validation_errors": validation_errors,
    }


def validate_dry_run_report(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("dry_run_policy") != EXPECTED_DRY_RUN_POLICY:
        errors.append(f"dry_run_policy must be {EXPECTED_DRY_RUN_POLICY}")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "decisions_created", "auto_merge_performed", "ready_for_canonical_apply"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if int(payload.get("missing_event_id_count") or 0) != 0:
        errors.append("missing_event_id_count must be 0")
    if errors:
        raise ValueError("dry-run report is not safe for validation: " + "; ".join(errors))


def validate_row(row: dict[str, Any], *, index: int) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    event_id = clean_text(row.get("canonical_event_id"))
    merged_ids = string_list(row.get("entity_resolution_canonical_merged_event_ids"))
    effect_ids = string_list(row.get("entity_resolution_canonical_effect_ids"))
    input_ids = string_list(row.get("canonical_input_ids"))
    provenance = [item for item in row.get("source_provenance") or [] if isinstance(item, dict)]
    if not event_id:
        errors.append({"error": "missing_canonical_event_id", "index": index})
    if clean_text(row.get("entity_resolution_canonical_replacement_event_id")) != event_id:
        errors.append({"error": "replacement_event_id_mismatch", "index": index, "canonical_event_id": event_id})
    if clean_text(row.get("entity_resolution_canonical_representative_event_id")) not in merged_ids:
        errors.append({"error": "representative_event_id_not_in_merged_ids", "index": index, "canonical_event_id": event_id})
    if row.get("entity_resolution_canonical_merge_policy") != EXPECTED_MERGE_POLICY:
        errors.append({"error": "unexpected_merge_policy", "index": index, "canonical_event_id": event_id})
    if row.get("entity_resolution_canonical_body_source_policy") != EXPECTED_BODY_SOURCE_POLICY:
        errors.append({"error": "unexpected_body_source_policy", "index": index, "canonical_event_id": event_id})
    if len(merged_ids) < 2:
        errors.append({"error": "merged_ids_requires_two_or_more_events", "index": index, "canonical_event_id": event_id})
    if len(effect_ids) != 1:
        errors.append({"error": "expected_one_effect_id", "index": index, "canonical_event_id": event_id})
    if int(row.get("duplicate_record_count") or 0) != len(input_ids):
        errors.append({"error": "duplicate_record_count_mismatch", "index": index, "canonical_event_id": event_id})
    provenance_input_ids = {clean_text(item.get("canonical_input_id")) for item in provenance if clean_text(item.get("canonical_input_id"))}
    if not set(input_ids).issubset(provenance_input_ids):
        errors.append({"error": "canonical_input_ids_not_preserved_in_provenance", "index": index, "canonical_event_id": event_id})
    conflicts = row.get("entity_resolution_canonical_merge_conflicts")
    if not isinstance(conflicts, dict) or not conflicts:
        errors.append({"error": "missing_merge_conflicts", "index": index, "canonical_event_id": event_id})
    return errors


def conflict_has_complete_source_values(conflict: Any, row: dict[str, Any]) -> bool:
    if not isinstance(conflict, dict):
        return False
    values = conflict.get("values")
    source_values = conflict.get("source_values")
    if not isinstance(values, list) or len(values) < 2:
        return False
    if not isinstance(source_values, list) or not source_values:
        return False
    merged_ids = set(string_list(row.get("entity_resolution_canonical_merged_event_ids")))
    source_ids = {
        clean_text(item.get("canonical_event_id"))
        for item in source_values
        if isinstance(item, dict) and clean_text(item.get("canonical_event_id"))
    }
    if not source_ids.issubset(merged_ids):
        return False
    source_value_count = int(conflict.get("source_value_count") or 0)
    return source_value_count == len(source_values)


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{path} line {line_number} must contain a JSON object.")
            rows.append(payload)
    return rows


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
    parser.add_argument("--dry-run-jsonl", type=Path, default=DEFAULT_DRY_RUN_JSONL)
    parser.add_argument("--dry-run-report", type=Path, default=DEFAULT_DRY_RUN_REPORT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = {"dry_run_jsonl": args.dry_run_jsonl, "dry_run_report": args.dry_run_report}
    report = check_time_norm_recommended_canonical_body_dry_run(
        dry_run_rows=read_jsonl(args.dry_run_jsonl),
        dry_run_report=read_json(args.dry_run_report),
        paths=paths,
    )
    write_json(args.output, report)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "check_policy": report["check_policy"],
                "valid": report["valid"],
                "validation_error_count": report["validation_error_count"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
