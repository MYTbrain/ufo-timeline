"""Validate a shadow ER preview output against its preview report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable


DEFAULT_PREVIEW_REPORT = Path("data/reports/entity_resolution_ai_ready_subset_preview_apply_report.json")
DEFAULT_PREVIEW_EVENTS = Path("data/canonical_preview_entity_resolution_ai_ready_subset/deduped_events.jsonl")
DEFAULT_OUTPUT = Path("data/reports/entity_resolution_ai_ready_subset_preview_output_check.json")


def check_entity_resolution_preview_output(
    *,
    preview_report: dict[str, Any],
    preview_events_path: Path,
    preview_report_path: Path | None = None,
) -> dict[str, Any]:
    validate_preview_report(preview_report)
    row_count = 0
    preview_merge_count = 0
    malformed_rows = []
    duplicate_event_ids = 0
    seen_event_ids: set[str] = set()
    preview_merge_samples = []

    for line_number, event in iter_jsonl(preview_events_path):
        row_count += 1
        event_id = clean_text(event.get("canonical_event_id"))
        if event_id:
            if event_id in seen_event_ids:
                duplicate_event_ids += 1
            seen_event_ids.add(event_id)
        else:
            malformed_rows.append({"line_number": line_number, "error": "missing_canonical_event_id"})
        if event.get("dedupe_strategy") == "entity_resolution_preview_merge":
            preview_merge_count += 1
            if len(preview_merge_samples) < 25:
                preview_merge_samples.append(
                    {
                        "line_number": line_number,
                        "canonical_event_id": event_id,
                        "merged_event_ids": event.get("entity_resolution_preview_merged_event_ids") or [],
                        "canonical_input_id_count": len(event.get("canonical_input_ids") or []),
                    }
                )

    expected_rows = int(preview_report.get("preview_event_count") or 0)
    expected_merges = expected_preview_merge_count(preview_report)
    validation_errors = []
    if row_count != expected_rows:
        validation_errors.append(
            {
                "error": "preview_event_count_mismatch",
                "expected": expected_rows,
                "actual": row_count,
            }
        )
    if preview_merge_count != expected_merges:
        validation_errors.append(
            {
                "error": "preview_merge_count_mismatch",
                "expected": expected_merges,
                "actual": preview_merge_count,
            }
        )
    if duplicate_event_ids:
        validation_errors.append({"error": "duplicate_canonical_event_ids", "count": duplicate_event_ids})
    if malformed_rows:
        validation_errors.append({"error": "malformed_rows", "count": len(malformed_rows)})

    return {
        "schema_version": 1,
        "check_policy": "entity_resolution_shadow_preview_output_check",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "inputs": {
            "preview_report": str(preview_report_path) if preview_report_path else None,
            "preview_events": str(preview_events_path),
        },
        "row_count": row_count,
        "expected_row_count": expected_rows,
        "preview_merge_count": preview_merge_count,
        "expected_preview_merge_count": expected_merges,
        "effects_applied": int(preview_report.get("effects_applied") or 0),
        "duplicate_event_id_count": duplicate_event_ids,
        "malformed_row_count": len(malformed_rows),
        "valid": not validation_errors,
        "validation_errors": validation_errors,
        "preview_merge_samples": preview_merge_samples,
    }


def validate_preview_report(report: dict[str, Any]) -> None:
    errors: list[str] = []
    if report.get("apply_policy") != "entity_resolution_stream_preview_only":
        errors.append("apply_policy must be 'entity_resolution_stream_preview_only'")
    if report.get("canonical_outputs_mutated") is not False:
        errors.append("canonical_outputs_mutated must be false")
    if report.get("preview_outputs_written") is not True:
        errors.append("preview_outputs_written must be true")
    if errors:
        raise ValueError(f"preview report is not safe to check: {'; '.join(errors)}")


def expected_preview_merge_count(report: dict[str, Any]) -> int:
    applied_effects = report.get("applied_effects")
    if not isinstance(applied_effects, list) or not applied_effects:
        return int(report.get("effects_applied") or 0)
    preview_event_ids = {
        event_id
        for effect in applied_effects
        if isinstance(effect, dict)
        and (event_id := clean_text(effect.get("preview_canonical_event_id")))
    }
    return len(preview_event_ids) if preview_event_ids else int(report.get("effects_applied") or 0)


def iter_jsonl(path: Path) -> Iterable[tuple[int, dict[str, Any]]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{path} line {line_number} must contain a JSON object.")
            yield line_number, payload


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview-report", type=Path, default=DEFAULT_PREVIEW_REPORT)
    parser.add_argument("--preview-events", type=Path, default=DEFAULT_PREVIEW_EVENTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    preview_report = read_json(args.preview_report)
    report = check_entity_resolution_preview_output(
        preview_report=preview_report,
        preview_report_path=args.preview_report,
        preview_events_path=args.preview_events,
    )
    write_json(args.output, report)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "valid": report["valid"],
                "row_count": report["row_count"],
                "preview_merge_count": report["preview_merge_count"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
