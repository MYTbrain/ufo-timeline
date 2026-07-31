"""Validate the stream-applied time-normalization canonical candidate corpus."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from parser.canonical_schema import clean_text


DEFAULT_APPLY_REPORT = Path("data/reports/entity_resolution_cluster_time_norm_recommended_canonical_apply_report.json")
DEFAULT_APPLY_EVENTS = Path("data/canonical_time_norm_recommended/deduped_events.jsonl")
DEFAULT_DRY_RUN_ROWS = Path("data/reports/entity_resolution_cluster_time_norm_recommended_canonical_body_dry_run.jsonl")
DEFAULT_OUTPUT = Path("data/reports/entity_resolution_cluster_time_norm_recommended_canonical_apply_output_check.json")

APPLY_POLICY = "entity_resolution_time_norm_recommended_stream_apply_v1"
CHECK_POLICY = "entity_resolution_time_norm_recommended_canonical_apply_output_check"


def check_time_norm_recommended_canonical_apply_output(
    *,
    apply_report: dict[str, Any],
    apply_events_path: Path,
    dry_run_rows: list[dict[str, Any]],
    apply_report_path: Path | None = None,
    dry_run_rows_path: Path | None = None,
) -> dict[str, Any]:
    validate_apply_report(apply_report)
    expected_replacement_rows = {
        clean_text(row.get("canonical_event_id")): row
        for row in dry_run_rows
        if isinstance(row, dict) and clean_text(row.get("canonical_event_id"))
    }
    expected_suppressed_ids = {
        event_id
        for row in dry_run_rows
        if isinstance(row, dict)
        for event_id in string_list(row.get("entity_resolution_canonical_merged_event_ids"))
        if event_id != clean_text(row.get("canonical_event_id"))
    }
    row_count = 0
    duplicate_event_id_count = 0
    malformed_row_count = 0
    seen_event_ids: set[str] = set()
    replacement_rows_found: set[str] = set()
    suppressed_ids_found: set[str] = set()
    mismatched_replacement_rows: list[dict[str, Any]] = []

    for line_number, event in iter_jsonl(apply_events_path):
        row_count += 1
        event_id = clean_text(event.get("canonical_event_id")) or clean_text(event.get("event_id"))
        if not event_id:
            malformed_row_count += 1
            continue
        if event_id in seen_event_ids:
            duplicate_event_id_count += 1
        seen_event_ids.add(event_id)
        if event_id in expected_suppressed_ids:
            suppressed_ids_found.add(event_id)
        expected_row = expected_replacement_rows.get(event_id)
        if expected_row is not None:
            replacement_rows_found.add(event_id)
            if canonical_json(event) != canonical_json(expected_row):
                mismatched_replacement_rows.append({"line_number": line_number, "canonical_event_id": event_id})

    validation_errors: list[dict[str, Any]] = []
    expected_rows = int(apply_report.get("expected_output_event_count") or 0)
    if row_count != expected_rows:
        validation_errors.append({"error": "row_count_mismatch", "expected": expected_rows, "actual": row_count})
    if duplicate_event_id_count:
        validation_errors.append({"error": "duplicate_event_id_count", "count": duplicate_event_id_count})
    if malformed_row_count:
        validation_errors.append({"error": "malformed_row_count", "count": malformed_row_count})
    missing_replacement_rows = sorted(set(expected_replacement_rows) - replacement_rows_found)
    if missing_replacement_rows:
        validation_errors.append({"error": "missing_replacement_rows", "event_ids": missing_replacement_rows})
    if suppressed_ids_found:
        validation_errors.append({"error": "suppressed_ids_still_present", "event_ids": sorted(suppressed_ids_found)})
    if mismatched_replacement_rows:
        validation_errors.append(
            {
                "error": "replacement_rows_do_not_match_dry_run_rows",
                "count": len(mismatched_replacement_rows),
                "samples": mismatched_replacement_rows[:10],
            }
        )

    return {
        "schema_version": 1,
        "check_policy": CHECK_POLICY,
        "canonical_outputs_mutated": False,
        "source_canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "ready_for_runtime_promotion": False,
        "inputs": {
            "apply_report": str(apply_report_path) if apply_report_path else None,
            "apply_events": str(apply_events_path),
            "dry_run_rows": str(dry_run_rows_path) if dry_run_rows_path else str(DEFAULT_DRY_RUN_ROWS),
        },
        "row_count": row_count,
        "expected_row_count": expected_rows,
        "replacement_rows_found": len(replacement_rows_found),
        "expected_replacement_rows": len(expected_replacement_rows),
        "suppressed_ids_found": len(suppressed_ids_found),
        "expected_suppressed_ids": len(expected_suppressed_ids),
        "duplicate_event_id_count": duplicate_event_id_count,
        "malformed_row_count": malformed_row_count,
        "mismatched_replacement_row_count": len(mismatched_replacement_rows),
        "valid": not validation_errors,
        "validation_error_count": len(validation_errors),
        "validation_errors": validation_errors,
    }


def validate_apply_report(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("apply_policy") != APPLY_POLICY:
        errors.append(f"apply_policy must be {APPLY_POLICY}")
    if payload.get("valid") is not True:
        errors.append("valid must be true")
    if payload.get("canonical_candidate_output_written") is not True:
        errors.append("canonical_candidate_output_written must be true")
    if int(payload.get("validation_error_count") or 0) != 0:
        errors.append("validation_error_count must be 0")
    for flag in ("canonical_outputs_mutated", "source_canonical_outputs_mutated", "preview_outputs_written", "auto_merge_performed", "ready_for_runtime_promotion"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError("canonical apply report is not safe to check: " + "; ".join(errors))


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def iter_jsonl(path: Path) -> Iterable[tuple[int, dict[str, Any]]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{path} line {line_number} must be a JSON object.")
            yield line_number, payload


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [payload for _, payload in iter_jsonl(path)]


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
    parser.add_argument("--apply-report", type=Path, default=DEFAULT_APPLY_REPORT)
    parser.add_argument("--apply-events", type=Path, default=DEFAULT_APPLY_EVENTS)
    parser.add_argument("--dry-run-rows", type=Path, default=DEFAULT_DRY_RUN_ROWS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = check_time_norm_recommended_canonical_apply_output(
        apply_report=read_json(args.apply_report),
        apply_events_path=args.apply_events,
        dry_run_rows=read_jsonl(args.dry_run_rows),
        apply_report_path=args.apply_report,
        dry_run_rows_path=args.dry_run_rows,
    )
    write_json(args.output, report)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "valid": report["valid"],
                "row_count": report["row_count"],
                "replacement_rows_found": report["replacement_rows_found"],
                "suppressed_ids_found": report["suppressed_ids_found"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
