"""Validate a manual-review stream-apply sidecar corpus."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable


DEFAULT_APPLY_REPORT = Path("data/reports/manual_review_ai_stream_apply_report.json")
DEFAULT_APPLY_EVENTS = Path("data/canonical_manual_review_ai_preview/deduped_events.jsonl")
DEFAULT_OUTPUT = Path("data/reports/manual_review_ai_stream_apply_output_check.json")

CHECK_POLICY = "manual_review_effects_stream_apply_output_check_v1"
APPLY_POLICY = "manual_review_effects_stream_preview_v1"


def check_manual_review_stream_apply_output(
    *,
    apply_report: dict[str, Any],
    apply_events_path: Path,
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    if apply_report.get("apply_policy") != APPLY_POLICY:
        errors.append({"error": "unexpected_apply_policy", "actual": apply_report.get("apply_policy")})
    if apply_report.get("valid") is not True:
        errors.append({"error": "apply_report_not_valid"})
    for flag in ("canonical_outputs_mutated", "source_canonical_outputs_mutated", "preview_outputs_written", "auto_merge_performed"):
        if apply_report.get(flag) is not False:
            errors.append({"error": "unsafe_apply_flag", "flag": flag, "actual": apply_report.get(flag)})
    if apply_report.get("canonical_candidate_output_written") is not True:
        errors.append({"error": "candidate_output_not_written"})

    replacement_ids = set(string_list(apply_report.get("replacement_event_ids")))
    suppressed_ids = set(string_list(apply_report.get("suppressed_event_ids")))
    row_count = 0
    duplicate_event_ids = 0
    output_ids: set[str] = set()
    replacement_ids_found: set[str] = set()
    suppressed_ids_found: set[str] = set()
    invalid_replacement_rows: list[dict[str, Any]] = []

    for event in iter_jsonl(apply_events_path):
        row_count += 1
        event_id = clean_text(event.get("canonical_event_id")) or clean_text(event.get("event_id"))
        if event_id in output_ids:
            duplicate_event_ids += 1
        if event_id:
            output_ids.add(event_id)
        if event_id in suppressed_ids:
            suppressed_ids_found.add(event_id)
        if event_id in replacement_ids:
            replacement_ids_found.add(event_id)
            replacement_errors = validate_replacement_row(event)
            if replacement_errors:
                invalid_replacement_rows.append({"event_id": event_id, "errors": replacement_errors})

    expected_rows = int(apply_report.get("output_event_count") or 0)
    if row_count != expected_rows:
        errors.append({"error": "row_count_mismatch", "expected": expected_rows, "actual": row_count})
    missing_replacement_ids = sorted(replacement_ids - replacement_ids_found)
    if missing_replacement_ids:
        errors.append({"error": "missing_replacement_ids", "event_ids": missing_replacement_ids[:50]})
    if suppressed_ids_found:
        errors.append({"error": "suppressed_ids_still_present", "event_ids": sorted(suppressed_ids_found)[:50]})
    if duplicate_event_ids:
        errors.append({"error": "duplicate_output_event_ids", "count": duplicate_event_ids})
    if invalid_replacement_rows:
        errors.append({"error": "invalid_replacement_rows", "rows": invalid_replacement_rows[:50]})

    return {
        "schema_version": 1,
        "check_policy": CHECK_POLICY,
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "inputs": {
            "apply_report_policy": apply_report.get("apply_policy"),
            "apply_events": str(apply_events_path),
        },
        "row_count": row_count,
        "expected_row_count": expected_rows,
        "replacement_rows_expected": len(replacement_ids),
        "replacement_rows_found": len(replacement_ids_found),
        "suppressed_ids_expected": len(suppressed_ids),
        "suppressed_ids_found": len(suppressed_ids_found),
        "duplicate_output_event_ids": duplicate_event_ids,
        "invalid_replacement_row_count": len(invalid_replacement_rows),
        "valid": not errors,
        "validation_error_count": len(errors),
        "validation_errors": errors,
    }


def validate_replacement_row(event: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    input_ids = string_list(event.get("canonical_input_ids"))
    provenance = event.get("source_provenance") if isinstance(event.get("source_provenance"), list) else []
    provenance_ids = {
        clean_text(item.get("canonical_input_id"))
        for item in provenance
        if isinstance(item, dict) and clean_text(item.get("canonical_input_id"))
    }
    preview = event.get("manual_review_preview") if isinstance(event.get("manual_review_preview"), dict) else {}
    if clean_text(event.get("dedupe_strategy")) != "manual_review_stream_preview_merge":
        errors.append("dedupe_strategy_not_manual_review_stream_preview_merge")
    if int(event.get("duplicate_record_count") or 0) != len(input_ids):
        errors.append("duplicate_record_count_mismatch")
    if set(input_ids) - provenance_ids:
        errors.append("source_provenance_missing_input_ids")
    if clean_text(preview.get("apply_policy")) != APPLY_POLICY:
        errors.append("missing_manual_review_apply_policy")
    if not string_list(preview.get("merged_canonical_event_ids")):
        errors.append("missing_merged_canonical_event_ids")
    if not string_list(preview.get("merged_by_effect_ids")):
        errors.append("missing_merged_by_effect_ids")
    return errors


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{path} line {line_number} must be a JSON object.")
            yield payload


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
    if isinstance(value, str):
        text = clean_text(value)
        return [text] if text else []
    if not isinstance(value, list):
        return []
    values: list[str] = []
    for item in value:
        text = clean_text(item)
        if text:
            values.append(text)
    return values


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply-report", type=Path, default=DEFAULT_APPLY_REPORT)
    parser.add_argument("--apply-events", type=Path, default=DEFAULT_APPLY_EVENTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = check_manual_review_stream_apply_output(
        apply_report=read_json(args.apply_report),
        apply_events_path=args.apply_events,
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
