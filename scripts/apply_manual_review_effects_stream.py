"""Stream-apply manual-review merge effects to a sidecar candidate corpus.

This command is intentionally preview/staging only. It writes a separate
``deduped_events.jsonl`` and a report, never overwrites canonical_full, and does
not build normalized/map JSON side outputs. It is intended for large manual
review plans that are too expensive for the legacy in-memory preview writer.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any, Iterable


DEFAULT_EFFECTS_PLAN = Path("data/reports/manual_review_ai_effects_plan.json")
DEFAULT_DEDUPED_EVENTS = Path("data/canonical_full/deduped_events.jsonl")
DEFAULT_OUTPUT_EVENTS = Path("data/canonical_manual_review_ai_preview/deduped_events.jsonl")
DEFAULT_REPORT_OUTPUT = Path("data/reports/manual_review_ai_stream_apply_report.json")

APPLY_POLICY = "manual_review_effects_stream_preview_v1"


def apply_manual_review_effects_stream(
    *,
    effects_plan: dict[str, Any],
    deduped_events_path: Path,
    output_events_path: Path,
    report_output_path: Path | None = None,
    overwrite_output: bool = False,
) -> dict[str, Any]:
    validate_effects_plan(effects_plan)
    validate_output_path(deduped_events_path, output_events_path, overwrite_output=overwrite_output)

    effects = [effect for effect in effects_plan.get("effects") or [] if isinstance(effect, dict)]
    merge_effects = [effect for effect in effects if clean_text(effect.get("planned_effect")) == "merge_duplicate_candidate"]
    defer_effects = [effect for effect in effects if clean_text(effect.get("planned_effect")) == "defer_duplicate_candidate"]
    preserve_effects = [effect for effect in effects if clean_text(effect.get("planned_effect")) == "preserve_source_row"]
    exclude_effects = [effect for effect in effects if clean_text(effect.get("planned_effect")) == "exclude_source_row"]

    required_input_ids = {
        input_id
        for effect in merge_effects + exclude_effects
        for input_id in normalized_id_list(effect.get("canonical_input_ids"))
    }
    scan = scan_required_events(deduped_events_path, required_input_ids)
    merge_plan = build_merge_plan(merge_effects=merge_effects, scan=scan)

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
    output_event_ids: set[str] = set()
    duplicate_output_event_ids = 0

    with tmp_output_path.open("w", encoding="utf-8", newline="\n") as output:
        for event in iter_jsonl(deduped_events_path):
            input_event_count += 1
            event_id = clean_text(event.get("canonical_event_id")) or clean_text(event.get("event_id"))
            if event_id in merge_plan["suppressed_ids"]:
                suppressed_rows_skipped += 1
                seen_suppressed_ids.add(event_id)
                continue
            if event_id in merge_plan["replacement_rows"]:
                replacement = merge_plan["replacement_rows"][event_id]
                write_event(output, replacement)
                output_event_count += 1
                replacement_rows_written += 1
                seen_replacement_ids.add(event_id)
                duplicate_output_event_ids += track_output_event_id(replacement, output_event_ids)
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
            "effects_plan": str(effects_plan.get("inputs", {}).get("applied_decisions_path") or ""),
            "deduped_events": str(deduped_events_path),
        },
        "outputs": {
            "deduped_events": str(output_events_path),
            "report": str(report_output_path) if report_output_path else None,
        },
        "input_event_count": input_event_count,
        "output_event_count": output_event_count if not validation_errors else 0,
        "expected_output_event_count": expected_output_event_count,
        "required_input_id_count": len(required_input_ids),
        "matched_input_id_count": len(scan["input_to_event_ids"]),
        "missing_input_id_count": len(merge_plan["missing_input_ids"]),
        "missing_input_ids_sample": merge_plan["missing_input_ids"][:50],
        "merge_effect_count": len(merge_effects),
        "defer_effect_count": len(defer_effects),
        "preserve_effect_count": len(preserve_effects),
        "exclude_effect_count": len(exclude_effects),
        "merge_effects_with_missing_inputs": len(merge_plan["blocked_effects"]),
        "merge_effects_already_unified": len(merge_plan["already_unified_effects"]),
        "merge_components": len(merge_plan["replacement_rows"]),
        "replacement_event_ids": sorted(merge_plan["replacement_rows"]),
        "replacement_rows_written": replacement_rows_written,
        "suppressed_rows_expected": len(merge_plan["suppressed_ids"]),
        "suppressed_event_ids": sorted(merge_plan["suppressed_ids"]),
        "suppressed_rows_skipped": suppressed_rows_skipped,
        "untouched_rows_written": untouched_rows_written,
        "actual_event_reduction": len(merge_plan["suppressed_ids"]),
        "projected_event_reduction_from_effects": sum(
            max(0, len(item["event_ids"]) - 1) for item in merge_plan["effect_event_summaries"]
        ),
        "validation_error_count": len(validation_errors),
        "validation_errors": validation_errors,
        "valid": not validation_errors,
        "blocked_effects_sample": merge_plan["blocked_effects"][:50],
        "already_unified_effects_sample": merge_plan["already_unified_effects"][:50],
        "safety_notes": [
            "This writes a separate manual-review candidate corpus and does not overwrite canonical_full.",
            "Connected duplicate-pair effects are merged as components to avoid duplicate output rows.",
            "Runtime/static promotion remains a separate explicit step.",
        ],
    }
    return report


def validate_effects_plan(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("effect_policy") != "plan_only":
        errors.append("effect_policy must be plan_only")
    for flag in ("canonical_outputs_mutated", "canonical_outputs_mutated_by_plan"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    effects = [effect for effect in payload.get("effects") or [] if isinstance(effect, dict)]
    if len(effects) != int(payload.get("planned_effect_count") or 0):
        errors.append("effects length must match planned_effect_count")
    unsupported = sorted(
        {
            clean_text(effect.get("planned_effect"))
            for effect in effects
            if clean_text(effect.get("planned_effect"))
            not in {
                "merge_duplicate_candidate",
                "defer_duplicate_candidate",
                "preserve_source_row",
                "exclude_source_row",
            }
        }
    )
    if unsupported:
        errors.append(f"unsupported planned_effect values: {', '.join(unsupported)}")
    for effect in effects:
        if effect.get("effect_policy") != "plan_only":
            errors.append("all effects must have effect_policy=plan_only")
        if effect.get("effect_status") != "planned_not_applied":
            errors.append("all effects must have effect_status=planned_not_applied")
        if effect.get("canonical_outputs_mutated") is not False:
            errors.append("all effects must declare canonical_outputs_mutated=false")
    if errors:
        raise ValueError("manual-review effects plan is unsafe for stream apply: " + "; ".join(sorted(set(errors))))


def scan_required_events(deduped_events_path: Path, required_input_ids: set[str]) -> dict[str, Any]:
    event_rows: dict[str, dict[str, Any]] = {}
    event_order: dict[str, int] = {}
    input_to_event_ids: dict[str, set[str]] = {}
    scanned_event_count = 0
    if not required_input_ids:
        return {
            "event_rows": event_rows,
            "event_order": event_order,
            "input_to_event_ids": input_to_event_ids,
            "scanned_event_count": scanned_event_count,
        }
    for event in iter_jsonl(deduped_events_path):
        scanned_event_count += 1
        event_id = clean_text(event.get("canonical_event_id")) or clean_text(event.get("event_id"))
        if not event_id:
            continue
        matched_inputs = set(normalized_id_list(event.get("canonical_input_ids"))) & required_input_ids
        if not matched_inputs:
            continue
        event_rows[event_id] = event
        event_order[event_id] = scanned_event_count
        for input_id in matched_inputs:
            input_to_event_ids.setdefault(input_id, set()).add(event_id)
    return {
        "event_rows": event_rows,
        "event_order": event_order,
        "input_to_event_ids": input_to_event_ids,
        "scanned_event_count": scanned_event_count,
    }


def build_merge_plan(*, merge_effects: list[dict[str, Any]], scan: dict[str, Any]) -> dict[str, Any]:
    input_to_event_ids: dict[str, set[str]] = scan["input_to_event_ids"]
    event_rows: dict[str, dict[str, Any]] = scan["event_rows"]
    event_order: dict[str, int] = scan["event_order"]

    parent: dict[str, str] = {}
    component_effects: dict[str, list[dict[str, Any]]] = {}
    blocked_effects: list[dict[str, Any]] = []
    already_unified_effects: list[dict[str, Any]] = []
    effect_event_summaries: list[dict[str, Any]] = []
    missing_input_ids: set[str] = set()

    for effect in merge_effects:
        input_ids = normalized_id_list(effect.get("canonical_input_ids"))
        missing = [input_id for input_id in input_ids if input_id not in input_to_event_ids]
        event_ids = sorted({event_id for input_id in input_ids for event_id in input_to_event_ids.get(input_id, set())})
        effect_summary = {
            "effect_id": clean_text(effect.get("effect_id")),
            "review_item_id": clean_text(effect.get("review_item_id")),
            "canonical_input_ids": input_ids,
            "event_ids": event_ids,
            "missing_input_ids": missing,
        }
        effect_event_summaries.append(effect_summary)
        if missing:
            missing_input_ids.update(missing)
            blocked_effects.append({**effect_summary, "reason": "missing_canonical_input_ids"})
            continue
        if len(event_ids) <= 1:
            already_unified_effects.append({**effect_summary, "reason": "already_unified_or_no_event_rows"})
            continue
        for event_id in event_ids:
            parent.setdefault(event_id, event_id)
        first_event_id = event_ids[0]
        for event_id in event_ids[1:]:
            union(parent, first_event_id, event_id)
        root = find(parent, first_event_id)
        component_effects.setdefault(root, []).append(effect)

    # Re-bucket effects after all unions have settled.
    rebucketed_effects: dict[str, list[dict[str, Any]]] = {}
    for effects in component_effects.values():
        for effect in effects:
            input_ids = normalized_id_list(effect.get("canonical_input_ids"))
            event_ids = sorted({event_id for input_id in input_ids for event_id in input_to_event_ids.get(input_id, set())})
            if not event_ids:
                continue
            rebucketed_effects.setdefault(find(parent, event_ids[0]), []).append(effect)

    replacement_rows: dict[str, dict[str, Any]] = {}
    suppressed_ids: set[str] = set()
    for root, effects in sorted(rebucketed_effects.items()):
        component_event_ids = sorted(
            {
                event_id
                for effect in effects
                for input_id in normalized_id_list(effect.get("canonical_input_ids"))
                for event_id in input_to_event_ids.get(input_id, set())
            },
            key=lambda event_id: (event_order.get(event_id, 10**18), event_id),
        )
        if len(component_event_ids) <= 1:
            continue
        replacement_id = component_event_ids[0]
        replacement_rows[replacement_id] = build_component_replacement_row(
            replacement_id=replacement_id,
            component_event_ids=component_event_ids,
            effects=effects,
            event_rows=event_rows,
        )
        suppressed_ids.update(event_id for event_id in component_event_ids if event_id != replacement_id)

    return {
        "replacement_rows": replacement_rows,
        "suppressed_ids": suppressed_ids,
        "blocked_effects": blocked_effects,
        "already_unified_effects": already_unified_effects,
        "effect_event_summaries": effect_event_summaries,
        "missing_input_ids": sorted(missing_input_ids),
    }


def build_component_replacement_row(
    *,
    replacement_id: str,
    component_event_ids: list[str],
    effects: list[dict[str, Any]],
    event_rows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    target = copy.deepcopy(event_rows[replacement_id])
    merged_input_ids: list[str] = []
    merged_provenance: list[dict[str, Any]] = []
    seen_provenance_keys: set[str] = set()
    for event_id in component_event_ids:
        source_event = event_rows[event_id]
        for input_id in normalized_id_list(source_event.get("canonical_input_ids")):
            if input_id not in merged_input_ids:
                merged_input_ids.append(input_id)
        provenance = source_event.get("source_provenance")
        if isinstance(provenance, list):
            for item in provenance:
                if not isinstance(item, dict):
                    continue
                key = clean_text(item.get("canonical_input_id")) or json.dumps(item, sort_keys=True)
                if key not in seen_provenance_keys:
                    merged_provenance.append(copy.deepcopy(item))
                    seen_provenance_keys.add(key)
    target["canonical_input_ids"] = merged_input_ids
    target["source_provenance"] = merged_provenance
    target["duplicate_record_count"] = len(merged_input_ids)
    target["dedupe_strategy"] = "manual_review_stream_preview_merge"
    target["manual_review_preview"] = {
        "merged_by_effect_ids": [clean_text(effect.get("effect_id")) for effect in effects if clean_text(effect.get("effect_id"))],
        "review_item_ids": [
            clean_text(effect.get("review_item_id")) for effect in effects if clean_text(effect.get("review_item_id"))
        ],
        "merged_canonical_event_ids": component_event_ids,
        "apply_policy": APPLY_POLICY,
    }
    return target


def find(parent: dict[str, str], value: str) -> str:
    parent.setdefault(value, value)
    while parent[value] != value:
        parent[value] = parent[parent[value]]
        value = parent[value]
    return value


def union(parent: dict[str, str], left: str, right: str) -> None:
    left_root = find(parent, left)
    right_root = find(parent, right)
    if left_root != right_root:
        parent[right_root] = left_root


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


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{path} line {line_number} must be a JSON object.")
            yield payload


def write_event(handle: Any, event: dict[str, Any]) -> None:
    handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")


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


def normalized_id_list(value: Any) -> list[str]:
    if isinstance(value, str):
        text = clean_text(value)
        return [text] if text else []
    if not isinstance(value, list):
        return []
    ids: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = clean_text(item)
        if text and text not in seen:
            ids.append(text)
            seen.add(text)
    return ids


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--effects-plan", type=Path, default=DEFAULT_EFFECTS_PLAN)
    parser.add_argument("--deduped-events", type=Path, default=DEFAULT_DEDUPED_EVENTS)
    parser.add_argument("--output-events", type=Path, default=DEFAULT_OUTPUT_EVENTS)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    parser.add_argument("--overwrite-output", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = apply_manual_review_effects_stream(
        effects_plan=read_json(args.effects_plan),
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
                "actual_event_reduction": report["actual_event_reduction"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
