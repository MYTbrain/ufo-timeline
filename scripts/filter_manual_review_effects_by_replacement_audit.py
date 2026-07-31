"""Filter a manual-review effects plan by replacement-audit risk level.

This is a safety lane builder. It keeps the AI/manual review plan
non-destructive, but removes merge effects whose stream replacement components
were not rated as acceptable by the conflict/body audit.
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
from pathlib import Path
from typing import Any, Iterable


DEFAULT_EFFECTS_PLAN = Path("data/reports/manual_review_ai_effects_plan.json")
DEFAULT_REPLACEMENT_AUDIT_CSV = Path("data/reports/manual_review_ai_after_time_norm_replacement_audit.csv")
DEFAULT_CANDIDATE_EVENTS = Path("data/canonical_time_norm_plus_manual_review_ai_preview/deduped_events.jsonl")
DEFAULT_OUTPUT_PLAN = Path("data/reports/manual_review_ai_after_time_norm_low_risk_effects_plan.json")
DEFAULT_OUTPUT_REPORT = Path("data/reports/manual_review_ai_after_time_norm_low_risk_effects_plan_report.json")

FILTER_POLICY = "manual_review_effects_filtered_by_replacement_audit_risk_v1"


def filter_manual_review_effects_by_replacement_audit(
    *,
    effects_plan: dict[str, Any],
    replacement_audit_csv_path: Path,
    candidate_events_path: Path,
    allowed_risk_levels: set[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    validate_effects_plan(effects_plan)
    audit_rows = read_audit_csv(replacement_audit_csv_path)
    audit_replacement_ids = {
        row["replacement_event_id"]
        for row in audit_rows
        if clean_text(row.get("replacement_event_id"))
    }
    selected_replacement_ids = {
        row["replacement_event_id"]
        for row in audit_rows
        if clean_text(row.get("replacement_event_id")) and clean_text(row.get("risk_level")) in allowed_risk_levels
    }
    excluded_replacement_ids = audit_replacement_ids - selected_replacement_ids
    selected_previews = scan_candidate_replacement_previews(candidate_events_path, selected_replacement_ids)
    excluded_previews = scan_candidate_replacement_previews(candidate_events_path, excluded_replacement_ids)
    selected_effect_ids = effect_ids_from_previews(selected_previews.values())
    excluded_effect_ids = effect_ids_from_previews(excluded_previews.values())
    selected_component_event_ids = component_event_ids_from_previews(selected_previews.values())
    excluded_component_event_ids = component_event_ids_from_previews(excluded_previews.values())
    missing_selected_replacement_ids = sorted(selected_replacement_ids - set(selected_previews))
    missing_excluded_replacement_ids = sorted(excluded_replacement_ids - set(excluded_previews))
    overlapping_effect_ids = sorted(selected_effect_ids & excluded_effect_ids)
    overlapping_component_event_ids = sorted(selected_component_event_ids & excluded_component_event_ids)

    input_effects = [effect for effect in effects_plan.get("effects") or [] if isinstance(effect, dict)]
    output_effects: list[dict[str, Any]] = []
    selected_merge_effect_count = 0
    excluded_merge_effect_count = 0
    passthrough_effect_count = 0
    for effect in input_effects:
        planned_effect = clean_text(effect.get("planned_effect"))
        effect_id = clean_text(effect.get("effect_id"))
        if planned_effect == "merge_duplicate_candidate":
            if effect_id in selected_effect_ids:
                output_effects.append(copy.deepcopy(effect))
                selected_merge_effect_count += 1
            else:
                excluded_merge_effect_count += 1
            continue
        output_effects.append(copy.deepcopy(effect))
        passthrough_effect_count += 1

    output_plan = copy.deepcopy(effects_plan)
    output_plan["filter_policy"] = FILTER_POLICY
    output_plan["source_effects_plan_policy"] = effects_plan.get("effect_policy")
    output_plan["allowed_replacement_audit_risk_levels"] = sorted(allowed_risk_levels)
    output_plan["canonical_outputs_mutated"] = False
    output_plan["canonical_outputs_mutated_by_plan"] = False
    output_plan["planned_effect_count"] = len(output_effects)
    output_plan["effects"] = output_effects

    validation_errors: list[dict[str, Any]] = []
    if missing_selected_replacement_ids:
        validation_errors.append(
            {"error": "missing_selected_replacement_rows", "event_ids": missing_selected_replacement_ids[:50]}
        )
    if overlapping_effect_ids:
        validation_errors.append({"error": "selected_excluded_effect_overlap", "effect_ids": overlapping_effect_ids[:50]})
    if overlapping_component_event_ids:
        validation_errors.append(
            {"error": "selected_excluded_component_event_overlap", "event_ids": overlapping_component_event_ids[:50]}
        )

    report = {
        "schema_version": 1,
        "filter_policy": FILTER_POLICY,
        "canonical_outputs_mutated": False,
        "source_canonical_outputs_mutated": False,
        "ready_for_runtime_promotion": False,
        "inputs": {
            "replacement_audit_csv": str(replacement_audit_csv_path),
            "candidate_events": str(candidate_events_path),
            "allowed_risk_levels": sorted(allowed_risk_levels),
        },
        "input_planned_effect_count": len(input_effects),
        "output_planned_effect_count": len(output_effects),
        "audit_rows_read": len(audit_rows),
        "audit_replacement_count": len(audit_replacement_ids),
        "selected_replacement_count": len(selected_replacement_ids),
        "excluded_replacement_count": len(excluded_replacement_ids),
        "selected_replacement_rows_found": len(selected_previews),
        "excluded_replacement_rows_found": len(excluded_previews),
        "missing_selected_replacement_count": len(missing_selected_replacement_ids),
        "missing_excluded_replacement_count": len(missing_excluded_replacement_ids),
        "selected_merge_effect_count": selected_merge_effect_count,
        "excluded_merge_effect_count": excluded_merge_effect_count,
        "passthrough_non_merge_effect_count": passthrough_effect_count,
        "selected_effect_ids_found": len(selected_effect_ids),
        "excluded_effect_ids_found": len(excluded_effect_ids),
        "selected_excluded_effect_overlap_count": len(overlapping_effect_ids),
        "selected_excluded_component_event_overlap_count": len(overlapping_component_event_ids),
        "valid": not validation_errors,
        "validation_error_count": len(validation_errors),
        "validation_errors": validation_errors,
    }
    return output_plan, report


def validate_effects_plan(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("effect_policy") != "plan_only":
        errors.append("effect_policy must be plan_only")
    if payload.get("canonical_outputs_mutated") is not False:
        errors.append("canonical_outputs_mutated must be false")
    if payload.get("canonical_outputs_mutated_by_plan") is not False:
        errors.append("canonical_outputs_mutated_by_plan must be false")
    effects = [effect for effect in payload.get("effects") or [] if isinstance(effect, dict)]
    if int(payload.get("planned_effect_count") or 0) != len(effects):
        errors.append("planned_effect_count must match effects length")
    if errors:
        raise ValueError("unsafe effects plan: " + "; ".join(errors))


def read_audit_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def scan_candidate_replacement_previews(path: Path, replacement_ids: set[str]) -> dict[str, dict[str, Any]]:
    previews: dict[str, dict[str, Any]] = {}
    if not replacement_ids:
        return previews
    for event in iter_jsonl(path):
        event_id = event_id_for(event)
        if event_id not in replacement_ids:
            continue
        preview = event.get("manual_review_preview") if isinstance(event.get("manual_review_preview"), dict) else {}
        previews[event_id] = preview
        if set(previews) == replacement_ids:
            break
    return previews


def effect_ids_from_previews(previews: Iterable[dict[str, Any]]) -> set[str]:
    return {effect_id for preview in previews for effect_id in string_list(preview.get("merged_by_effect_ids"))}


def component_event_ids_from_previews(previews: Iterable[dict[str, Any]]) -> set[str]:
    return {event_id for preview in previews for event_id in string_list(preview.get("merged_canonical_event_ids"))}


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{path} line {line_number} must be a JSON object.")
            yield payload


def event_id_for(event: dict[str, Any]) -> str:
    return clean_text(event.get("canonical_event_id")) or clean_text(event.get("event_id"))


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        text = clean_text(value)
        return [text] if text else []
    if not isinstance(value, list):
        return []
    values: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = clean_text(item)
        if text and text not in seen:
            values.append(text)
            seen.add(text)
    return values


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
    parser.add_argument("--effects-plan", type=Path, default=DEFAULT_EFFECTS_PLAN)
    parser.add_argument("--replacement-audit-csv", type=Path, default=DEFAULT_REPLACEMENT_AUDIT_CSV)
    parser.add_argument("--candidate-events", type=Path, default=DEFAULT_CANDIDATE_EVENTS)
    parser.add_argument("--output-plan", type=Path, default=DEFAULT_OUTPUT_PLAN)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    parser.add_argument("--allowed-risk-level", action="append", default=["low"])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_plan, report = filter_manual_review_effects_by_replacement_audit(
        effects_plan=read_json(args.effects_plan),
        replacement_audit_csv_path=args.replacement_audit_csv,
        candidate_events_path=args.candidate_events,
        allowed_risk_levels={clean_text(level) for level in args.allowed_risk_level if clean_text(level)},
    )
    write_json(args.output_plan, output_plan)
    write_json(args.output_report, report)
    print(
        json.dumps(
            {
                "output_plan": str(args.output_plan),
                "output_report": str(args.output_report),
                "selected_replacement_count": report["selected_replacement_count"],
                "selected_merge_effect_count": report["selected_merge_effect_count"],
                "excluded_merge_effect_count": report["excluded_merge_effect_count"],
                "valid": report["valid"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
