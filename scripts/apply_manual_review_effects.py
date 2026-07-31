"""Apply manual-review effects to preview-only shadow outputs.

This script intentionally supports preview mode only. It reads a reviewed
effects plan plus canonical outputs, writes a separate preview directory, and
never overwrites the canonical build artifacts.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


DEFAULT_EFFECTS_PLAN_PATH = Path("data/reports/manual_review_effects_plan.json")
DEFAULT_DEDUPED_EVENTS_PATH = Path("data/canonical/deduped_events.jsonl")
DEFAULT_OUTPUT_DIR = Path("data/canonical_preview_manual_review")
DEFAULT_REPORTS_DIR = Path("data/reports")


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--effects-plan",
        default=str(DEFAULT_EFFECTS_PLAN_PATH),
        help="Path to manual_review_effects_plan.json.",
    )
    parser.add_argument(
        "--deduped-events",
        default=str(DEFAULT_DEDUPED_EVENTS_PATH),
        help="Path to source deduped_events.jsonl.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for preview-only shadow canonical outputs.",
    )
    parser.add_argument(
        "--reports-dir",
        default=str(DEFAULT_REPORTS_DIR),
        help="Directory for preview apply reports.",
    )
    parser.add_argument(
        "--mode",
        choices=["preview"],
        default="preview",
        help="Only preview mode is implemented; canonical promotion is intentionally unavailable.",
    )
    return parser


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{path} line {line_number} must be a JSON object.")
            records.append(payload)
    return records


def write_json(path: Path, payload: Any, *, indent: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=indent)


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")


def apply_manual_review_effects_preview(
    *,
    effects_plan: dict[str, Any],
    deduped_events: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if effects_plan.get("effect_policy") != "plan_only":
        raise ValueError("Effects plan must have effect_policy=plan_only.")
    if effects_plan.get("canonical_outputs_mutated") is not False:
        raise ValueError("Effects plan must declare canonical_outputs_mutated=false.")

    preview_events = copy.deepcopy(deduped_events)
    effect_records = effects_plan.get("effects")
    if not isinstance(effect_records, list):
        raise ValueError("Effects plan must include an effects array.")

    index = build_event_index(preview_events)
    applied_effects: list[dict[str, Any]] = []
    blocked_effects: list[dict[str, Any]] = []
    skipped_effects: list[dict[str, Any]] = []
    excluded_input_ids: set[str] = set()

    for effect in effect_records:
        if not isinstance(effect, dict):
            blocked_effects.append({"reason": "effect_record_must_be_object"})
            continue
        validation_error = validate_effect_header(effect)
        if validation_error:
            blocked_effects.append(blocked(effect, validation_error))
            continue
        if effect.get("planned_effect") == "exclude_source_row":
            input_ids = normalized_id_list(effect.get("canonical_input_ids"))
            missing = [input_id for input_id in input_ids if input_id not in index["input_to_event_ids"]]
            if missing:
                blocked_effects.append(blocked(effect, "missing_canonical_input_ids", missing_ids=missing))
                continue
            excluded_input_ids.update(input_ids)

    for effect in effect_records:
        if not isinstance(effect, dict) or validate_effect_header(effect):
            continue
        planned_effect = effect.get("planned_effect")
        if planned_effect == "merge_duplicate_candidate":
            input_ids = normalized_id_list(effect.get("canonical_input_ids"))
            missing = [input_id for input_id in input_ids if input_id not in index["input_to_event_ids"]]
            conflicted = [input_id for input_id in input_ids if input_id in excluded_input_ids]
            if missing:
                blocked_effects.append(blocked(effect, "missing_canonical_input_ids", missing_ids=missing))
                continue
            if conflicted:
                blocked_effects.append(
                    blocked(effect, "canonical_input_ids_also_excluded", conflicted_ids=conflicted)
                )
                continue
            merge_result = apply_merge_effect(preview_events, effect, input_ids)
            applied_effects.append(merge_result)
            index = build_event_index(preview_events)
            continue
        if planned_effect == "exclude_source_row":
            continue
        skipped_effects.append(
            {
                "effect_id": effect.get("effect_id"),
                "review_item_id": effect.get("review_item_id"),
                "planned_effect": planned_effect,
                "reason": "no_preview_output_change_for_effect_type",
            }
        )

    for input_id in sorted(excluded_input_ids):
        exclusion_result = apply_exclusion(preview_events, input_id)
        if exclusion_result["status"] == "applied":
            applied_effects.append(exclusion_result)
        else:
            blocked_effects.append(exclusion_result)

    preview_events = [event for event in preview_events if not event.get("_manual_review_preview_removed")]
    preview_events.sort(key=lambda event: str(event.get("canonical_event_id") or ""))

    report = {
        "mode": "preview",
        "canonical_outputs_mutated": False,
        "input_event_count": len(deduped_events),
        "preview_event_count": len(preview_events),
        "effects_requested": len(effect_records),
        "effects_applied": len(applied_effects),
        "effects_blocked": len(blocked_effects),
        "effects_skipped": len(skipped_effects),
        "applied_effects": applied_effects,
        "blocked_effects": blocked_effects,
        "skipped_effects": skipped_effects,
        "safety_notes": [
            "Preview mode writes only shadow outputs.",
            "Canonical source outputs are not overwritten.",
            "Promotion mode is intentionally not implemented in this pass.",
        ],
    }
    return preview_events, report


def validate_effect_header(effect: dict[str, Any]) -> str | None:
    if effect.get("effect_policy") != "plan_only":
        return "effect_policy_must_be_plan_only"
    if effect.get("effect_status") != "planned_not_applied":
        return "effect_status_must_be_planned_not_applied"
    if effect.get("canonical_outputs_mutated") is not False:
        return "effect_must_declare_no_canonical_mutation"
    if not effect.get("planned_effect"):
        return "missing_planned_effect"
    return None


def build_event_index(events: list[dict[str, Any]]) -> dict[str, Any]:
    event_by_id: dict[str, dict[str, Any]] = {}
    input_to_event_ids: dict[str, set[str]] = {}
    for event in events:
        event_id = str(event.get("canonical_event_id") or "")
        if event_id:
            event_by_id[event_id] = event
        for input_id in normalized_id_list(event.get("canonical_input_ids")):
            input_to_event_ids.setdefault(input_id, set()).add(event_id)
    return {"event_by_id": event_by_id, "input_to_event_ids": input_to_event_ids}


def apply_merge_effect(
    events: list[dict[str, Any]],
    effect: dict[str, Any],
    input_ids: list[str],
) -> dict[str, Any]:
    index = build_event_index(events)
    event_ids: list[str] = []
    for input_id in input_ids:
        for event_id in sorted(index["input_to_event_ids"].get(input_id, set())):
            if event_id and event_id not in event_ids:
                event_ids.append(event_id)

    replacement_id = effect.get("replacement_canonical_event_id")
    target_event_id = replacement_id if replacement_id in event_ids else event_ids[0]
    target = index["event_by_id"][target_event_id]
    source_events = [index["event_by_id"][event_id] for event_id in event_ids]

    merged_input_ids: list[str] = []
    merged_provenance: list[dict[str, Any]] = []
    seen_provenance_keys: set[str] = set()
    for source_event in source_events:
        for input_id in normalized_id_list(source_event.get("canonical_input_ids")):
            if input_id not in merged_input_ids:
                merged_input_ids.append(input_id)
        provenance = source_event.get("source_provenance")
        if isinstance(provenance, list):
            for item in provenance:
                if not isinstance(item, dict):
                    continue
                key = str(item.get("canonical_input_id") or json.dumps(item, sort_keys=True))
                if key not in seen_provenance_keys:
                    merged_provenance.append(copy.deepcopy(item))
                    seen_provenance_keys.add(key)

    target["canonical_input_ids"] = merged_input_ids
    target["source_provenance"] = merged_provenance
    target["duplicate_record_count"] = len(merged_input_ids)
    target["dedupe_strategy"] = "manual_review_preview_merge"
    target["manual_review_preview"] = {
        "merged_by_effect_id": effect.get("effect_id"),
        "review_item_id": effect.get("review_item_id"),
        "merged_canonical_event_ids": event_ids,
    }

    for source_event in source_events:
        if source_event is not target:
            source_event["_manual_review_preview_removed"] = True

    return {
        "status": "applied",
        "effect_id": effect.get("effect_id"),
        "planned_effect": effect.get("planned_effect"),
        "target_canonical_event_id": target_event_id,
        "merged_canonical_event_ids": event_ids,
        "canonical_input_ids": merged_input_ids,
    }


def apply_exclusion(events: list[dict[str, Any]], input_id: str) -> dict[str, Any]:
    index = build_event_index(events)
    event_ids = sorted(index["input_to_event_ids"].get(input_id, set()))
    if not event_ids:
        return {
            "status": "blocked",
            "planned_effect": "exclude_source_row",
            "reason": "missing_canonical_input_id",
            "canonical_input_id": input_id,
        }

    applied_to: list[str] = []
    removed_events: list[str] = []
    for event_id in event_ids:
        event = index["event_by_id"].get(event_id)
        if event is None:
            continue
        event["canonical_input_ids"] = [
            existing_id
            for existing_id in normalized_id_list(event.get("canonical_input_ids"))
            if existing_id != input_id
        ]
        provenance = event.get("source_provenance")
        if isinstance(provenance, list):
            event["source_provenance"] = [
                item
                for item in provenance
                if not isinstance(item, dict) or item.get("canonical_input_id") != input_id
            ]
        event["duplicate_record_count"] = len(event["canonical_input_ids"])
        event.setdefault("manual_review_preview", {})["excluded_canonical_input_ids"] = [input_id]
        applied_to.append(event_id)
        if not event["canonical_input_ids"]:
            event["_manual_review_preview_removed"] = True
            removed_events.append(event_id)

    return {
        "status": "applied",
        "planned_effect": "exclude_source_row",
        "canonical_input_id": input_id,
        "affected_canonical_event_ids": applied_to,
        "removed_canonical_event_ids": removed_events,
    }


def blocked(effect: dict[str, Any], reason: str, **extra: Any) -> dict[str, Any]:
    payload = {
        "status": "blocked",
        "effect_id": effect.get("effect_id"),
        "review_item_id": effect.get("review_item_id"),
        "planned_effect": effect.get("planned_effect"),
        "reason": reason,
    }
    payload.update(extra)
    return payload


def normalized_id_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if not isinstance(value, list):
        return []
    ids: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item).strip() if item is not None else ""
        if text and text not in seen:
            ids.append(text)
            seen.add(text)
    return ids


def write_preview_outputs(
    *,
    preview_events: list[dict[str, Any]],
    output_dir: Path,
    reports_dir: Path,
    report: dict[str, Any],
) -> dict[str, Any]:
    from parser.canonical_export import canonical_events_to_normalized_events

    normalized_events = canonical_events_to_normalized_events(preview_events)
    map_events = [
        event
        for event in normalized_events
        if event.get("lat") is not None and event.get("lon") is not None
    ]
    write_jsonl(output_dir / "deduped_events.jsonl", preview_events)
    write_json(output_dir / "normalized_events.json", normalized_events)
    write_json(output_dir / "map_events.json", map_events)
    write_json(output_dir / "manual_review_apply_preview_report.json", report, indent=2)
    write_json(reports_dir / "manual_review_apply_preview_report.json", report, indent=2)
    return {
        "deduped_events": str((output_dir / "deduped_events.jsonl").resolve()),
        "normalized_events": str((output_dir / "normalized_events.json").resolve()),
        "map_events": str((output_dir / "map_events.json").resolve()),
        "output_report": str((output_dir / "manual_review_apply_preview_report.json").resolve()),
        "reports_report": str((reports_dir / "manual_review_apply_preview_report.json").resolve()),
    }


def ensure_preview_output_dir(input_path: Path, output_dir: Path) -> None:
    input_parent = input_path.resolve().parent
    resolved_output = output_dir.resolve()
    if resolved_output == input_parent:
        raise ValueError("Preview output_dir must not be the same directory as source canonical outputs.")
    if input_parent in resolved_output.parents:
        return
    return


def main(argv: list[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    effects_plan_path = Path(args.effects_plan)
    deduped_events_path = Path(args.deduped_events)
    output_dir = Path(args.output_dir)
    reports_dir = Path(args.reports_dir)

    ensure_preview_output_dir(deduped_events_path, output_dir)
    preview_events, report = apply_manual_review_effects_preview(
        effects_plan=read_json(effects_plan_path),
        deduped_events=read_jsonl(deduped_events_path),
    )
    report["inputs"] = {
        "effects_plan": str(effects_plan_path.resolve()),
        "deduped_events": str(deduped_events_path.resolve()),
    }
    report["outputs"] = write_preview_outputs(
        preview_events=preview_events,
        output_dir=output_dir,
        reports_dir=reports_dir,
        report=report,
    )
    print(
        json.dumps(
            {
                "mode": report["mode"],
                "canonical_outputs_mutated": report["canonical_outputs_mutated"],
                "preview_event_count": report["preview_event_count"],
                "effects_applied": report["effects_applied"],
                "effects_blocked": report["effects_blocked"],
                "outputs": report["outputs"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
