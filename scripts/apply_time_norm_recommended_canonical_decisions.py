"""Stream-apply accepted clean time-normalization decisions to a new corpus.

This command writes a separate canonical-candidate ``deduped_events.jsonl``.
It refuses to overwrite the source corpus by default and never mutates the
existing canonical_full outputs in place.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from parser.canonical_schema import clean_text


DEFAULT_ACCEPTED_EFFECTS_PLAN = Path("data/reports/entity_resolution_cluster_time_norm_recommended_accepted_effects_plan.json")
DEFAULT_DRY_RUN_ROWS = Path("data/reports/entity_resolution_cluster_time_norm_recommended_canonical_body_dry_run.jsonl")
DEFAULT_DRY_RUN_CHECK = Path("data/reports/entity_resolution_cluster_time_norm_recommended_canonical_body_dry_run_check.json")
DEFAULT_DEDUPED_EVENTS = Path("data/canonical_full/deduped_events.jsonl")
DEFAULT_OUTPUT_EVENTS = Path("data/canonical_time_norm_recommended/deduped_events.jsonl")
DEFAULT_REPORT_OUTPUT = Path("data/reports/entity_resolution_cluster_time_norm_recommended_canonical_apply_report.json")

APPLY_POLICY = "entity_resolution_time_norm_recommended_stream_apply_v1"
DRY_RUN_CHECK_POLICY = "entity_resolution_time_norm_recommended_canonical_body_dry_run_check"


def apply_time_norm_recommended_canonical_decisions(
    *,
    accepted_effects_plan: dict[str, Any],
    dry_run_rows: list[dict[str, Any]],
    dry_run_check: dict[str, Any],
    deduped_events_path: Path,
    output_events_path: Path,
    report_output_path: Path | None = None,
    overwrite_output: bool = False,
) -> dict[str, Any]:
    validate_accepted_effects_plan(accepted_effects_plan)
    validate_dry_run_check(dry_run_check, expected_count=int(accepted_effects_plan.get("planned_effect_count") or 0))
    merge_plan = build_apply_plan(accepted_effects_plan=accepted_effects_plan, dry_run_rows=dry_run_rows)
    validate_output_path(deduped_events_path, output_events_path, overwrite_output=overwrite_output)

    output_events_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_output_path = output_events_path.with_suffix(output_events_path.suffix + ".tmp")
    if tmp_output_path.exists():
        tmp_output_path.unlink()

    input_event_count = 0
    output_event_count = 0
    replacement_rows_written = 0
    suppressed_rows_skipped = 0
    untouched_rows_written = 0
    seen_replacement_ids: set[str] = set()
    seen_suppressed_ids: set[str] = set()
    duplicate_output_event_ids = 0
    output_event_ids: set[str] = set()

    with tmp_output_path.open("w", encoding="utf-8", newline="\n") as output:
        for event in iter_jsonl(deduped_events_path):
            input_event_count += 1
            event_id = clean_text(event.get("canonical_event_id")) or clean_text(event.get("event_id"))
            if event_id in merge_plan["suppressed_ids"]:
                suppressed_rows_skipped += 1
                seen_suppressed_ids.add(event_id)
                continue
            if event_id in merge_plan["replacement_rows"]:
                row = merge_plan["replacement_rows"][event_id]
                write_event(output, row)
                output_event_count += 1
                replacement_rows_written += 1
                seen_replacement_ids.add(event_id)
                duplicate_output_event_ids += track_output_event_id(row, output_event_ids)
                continue
            write_event(output, event)
            output_event_count += 1
            untouched_rows_written += 1
            duplicate_output_event_ids += track_output_event_id(event, output_event_ids)

    validation_errors: list[dict[str, Any]] = []
    missing_replacement_ids = sorted(set(merge_plan["replacement_rows"]) - seen_replacement_ids)
    missing_suppressed_ids = sorted(merge_plan["suppressed_ids"] - seen_suppressed_ids)
    expected_output_event_count = input_event_count - len(merge_plan["suppressed_ids"])
    if missing_replacement_ids:
        validation_errors.append({"error": "missing_replacement_ids", "event_ids": missing_replacement_ids})
    if missing_suppressed_ids:
        validation_errors.append({"error": "missing_suppressed_ids", "event_ids": missing_suppressed_ids})
    if output_event_count != expected_output_event_count:
        validation_errors.append(
            {
                "error": "output_event_count_mismatch",
                "expected": expected_output_event_count,
                "actual": output_event_count,
            }
        )
    if duplicate_output_event_ids:
        validation_errors.append({"error": "duplicate_output_event_ids", "count": duplicate_output_event_ids})

    if validation_errors:
        tmp_output_path.unlink(missing_ok=True)
    else:
        if output_events_path.exists() and overwrite_output:
            output_events_path.unlink()
        tmp_output_path.replace(output_events_path)

    report = {
        "schema_version": 1,
        "apply_policy": APPLY_POLICY,
        "canonical_outputs_mutated": False,
        "source_canonical_outputs_mutated": False,
        "canonical_candidate_output_written": not validation_errors,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "ready_for_runtime_promotion": False,
        "inputs": {
            "accepted_effects_plan": str(accepted_effects_plan.get("inputs", {}).get("validated_decisions") or ""),
            "deduped_events": str(deduped_events_path),
            "dry_run_check_policy": dry_run_check.get("check_policy"),
        },
        "outputs": {
            "deduped_events": str(output_events_path),
            "report": str(report_output_path) if report_output_path else None,
        },
        "input_event_count": input_event_count,
        "output_event_count": output_event_count if not validation_errors else 0,
        "expected_output_event_count": expected_output_event_count,
        "replacement_rows_expected": len(merge_plan["replacement_rows"]),
        "replacement_rows_written": replacement_rows_written,
        "suppressed_rows_expected": len(merge_plan["suppressed_ids"]),
        "suppressed_rows_skipped": suppressed_rows_skipped,
        "untouched_rows_written": untouched_rows_written,
        "planned_effect_count": int(accepted_effects_plan.get("planned_effect_count") or 0),
        "projected_event_reduction": len(merge_plan["suppressed_ids"]),
        "valid": not validation_errors,
        "validation_error_count": len(validation_errors),
        "validation_errors": validation_errors,
        "safety_notes": [
            "This writes a separate canonical-candidate corpus and does not overwrite canonical_full.",
            "Runtime/static promotion remains a separate explicit step.",
            "The original source corpus is left unchanged.",
        ],
    }
    return report


def validate_accepted_effects_plan(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("effect_policy") != "entity_resolution_plan_only":
        errors.append("effect_policy must be entity_resolution_plan_only")
    if int(payload.get("planned_effect_count") or 0) <= 0:
        errors.append("planned_effect_count must be positive")
    if int(payload.get("requires_explicit_apply_step_count") or 0) != int(payload.get("planned_effect_count") or 0):
        errors.append("requires_explicit_apply_step_count must match planned_effect_count")
    for flag in ("canonical_outputs_mutated", "canonical_outputs_mutated_by_plan", "preview_outputs_written", "auto_merge_performed"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    effects = [effect for effect in payload.get("effects") or [] if isinstance(effect, dict)]
    if len(effects) != int(payload.get("planned_effect_count") or 0):
        errors.append("effects length must match planned_effect_count")
    for effect in effects:
        if clean_text(effect.get("planned_effect")) != "merge_entity_resolution_candidate":
            errors.append("all accepted effects must be merge_entity_resolution_candidate")
        if effect.get("requires_explicit_apply_step") is not True:
            errors.append("all accepted effects must require explicit apply")
    if payload.get("warnings"):
        errors.append("accepted effects plan must not contain warnings")
    if errors:
        raise ValueError("accepted effects plan is unsafe for stream apply: " + "; ".join(errors))


def validate_dry_run_check(payload: dict[str, Any], *, expected_count: int) -> None:
    errors: list[str] = []
    if payload.get("check_policy") != DRY_RUN_CHECK_POLICY:
        errors.append(f"check_policy must be {DRY_RUN_CHECK_POLICY}")
    if payload.get("valid") is not True:
        errors.append("valid must be true")
    if int(payload.get("dry_run_row_count") or 0) != expected_count:
        errors.append("dry_run_row_count must match accepted effect count")
    if int(payload.get("validation_error_count") or 0) != 0:
        errors.append("validation_error_count must be 0")
    if int(payload.get("incomplete_conflict_source_value_count") or 0) != 0:
        errors.append("incomplete_conflict_source_value_count must be 0")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "decisions_created", "auto_merge_performed", "ready_for_canonical_apply"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError("canonical body dry-run check is unsafe for stream apply: " + "; ".join(errors))


def build_apply_plan(
    *,
    accepted_effects_plan: dict[str, Any],
    dry_run_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    expected_effect_ids = {
        effect_id
        for effect in accepted_effects_plan.get("effects") or []
        if isinstance(effect, dict)
        if (effect_id := clean_text(effect.get("effect_id")))
    }
    replacement_rows: dict[str, dict[str, Any]] = {}
    suppressed_ids: set[str] = set()
    seen_merged_ids: set[str] = set()
    dry_run_effect_ids: set[str] = set()
    errors: list[str] = []
    for row in dry_run_rows:
        replacement_id = clean_text(row.get("entity_resolution_canonical_replacement_event_id")) or clean_text(
            row.get("canonical_event_id")
        )
        if not replacement_id:
            errors.append("dry-run row missing replacement event id")
            continue
        if clean_text(row.get("canonical_event_id")) != replacement_id:
            errors.append(f"dry-run row {replacement_id} canonical_event_id must equal replacement id")
        if replacement_id in replacement_rows:
            errors.append(f"duplicate replacement id: {replacement_id}")
        replacement_rows[replacement_id] = row
        row_effect_ids = string_list(row.get("entity_resolution_canonical_effect_ids"))
        dry_run_effect_ids.update(row_effect_ids)
        merged_ids = string_list(row.get("entity_resolution_canonical_merged_event_ids"))
        if replacement_id not in merged_ids:
            errors.append(f"replacement id {replacement_id} is missing from merged event ids")
        for event_id in merged_ids:
            if event_id in seen_merged_ids:
                errors.append(f"event id appears in more than one dry-run merge row: {event_id}")
            seen_merged_ids.add(event_id)
            if event_id != replacement_id:
                suppressed_ids.add(event_id)
    if dry_run_effect_ids != expected_effect_ids:
        errors.append("dry-run effect IDs must match accepted effects plan effect IDs")
    if len(replacement_rows) != len(expected_effect_ids):
        errors.append("replacement row count must match accepted effects count")
    if errors:
        raise ValueError("dry-run rows are unsafe for stream apply: " + "; ".join(errors))
    return {
        "replacement_rows": replacement_rows,
        "suppressed_ids": suppressed_ids,
    }


def validate_output_path(source_path: Path, output_path: Path, *, overwrite_output: bool) -> None:
    if source_path.resolve() == output_path.resolve():
        raise ValueError("output path must not be the same as the source deduped_events path")
    if output_path.exists() and not overwrite_output:
        raise FileExistsError(f"{output_path} already exists; pass --overwrite-output to replace that output path")


def track_output_event_id(event: dict[str, Any], seen: set[str]) -> int:
    event_id = clean_text(event.get("canonical_event_id")) or clean_text(event.get("event_id"))
    if not event_id:
        return 0
    if event_id in seen:
        return 1
    seen.add(event_id)
    return 0


def write_event(handle: Any, event: dict[str, Any]) -> None:
    handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")


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


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return list(iter_jsonl(path))


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
    parser.add_argument("--accepted-effects-plan", type=Path, default=DEFAULT_ACCEPTED_EFFECTS_PLAN)
    parser.add_argument("--dry-run-rows", type=Path, default=DEFAULT_DRY_RUN_ROWS)
    parser.add_argument("--dry-run-check", type=Path, default=DEFAULT_DRY_RUN_CHECK)
    parser.add_argument("--deduped-events", type=Path, default=DEFAULT_DEDUPED_EVENTS)
    parser.add_argument("--output-events", type=Path, default=DEFAULT_OUTPUT_EVENTS)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    parser.add_argument("--overwrite-output", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = apply_time_norm_recommended_canonical_decisions(
        accepted_effects_plan=read_json(args.accepted_effects_plan),
        dry_run_rows=read_jsonl(args.dry_run_rows),
        dry_run_check=read_json(args.dry_run_check),
        deduped_events_path=args.deduped_events,
        output_events_path=args.output_events,
        report_output_path=args.report_output,
        overwrite_output=args.overwrite_output,
    )
    write_json(args.report_output, report)
    print(
        json.dumps(
            {
                "report": str(args.report_output),
                "deduped_events": str(args.output_events),
                "valid": report["valid"],
                "input_event_count": report["input_event_count"],
                "output_event_count": report["output_event_count"],
                "projected_event_reduction": report["projected_event_reduction"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
