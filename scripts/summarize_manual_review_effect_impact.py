"""Stream a deduped-event corpus and summarize a manual-review effects plan.

This is a non-destructive impact estimate. It avoids loading the multi-GB
full canonical corpus into memory and does not write preview canonical outputs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_EFFECTS_PLAN = Path("data/reports/manual_review_ai_effects_plan.json")
DEFAULT_DEDUPED_EVENTS = Path("data/canonical_full/deduped_events.jsonl")
DEFAULT_OUTPUT = Path("data/reports/manual_review_ai_effect_impact_summary.json")


def summarize_effect_impact(
    *,
    effects_plan_path: Path = DEFAULT_EFFECTS_PLAN,
    deduped_events_path: Path = DEFAULT_DEDUPED_EVENTS,
) -> dict[str, Any]:
    effects_plan = read_json(effects_plan_path)
    effects = effects_plan.get("effects") if isinstance(effects_plan.get("effects"), list) else []
    merge_effects = [effect for effect in effects if isinstance(effect, dict) and effect.get("planned_effect") == "merge_duplicate_candidate"]
    exclude_effects = [effect for effect in effects if isinstance(effect, dict) and effect.get("planned_effect") == "exclude_source_row"]
    preserve_effects = [effect for effect in effects if isinstance(effect, dict) and effect.get("planned_effect") == "preserve_source_row"]
    defer_effects = [effect for effect in effects if isinstance(effect, dict) and effect.get("planned_effect") == "defer_duplicate_candidate"]

    required_input_ids = set()
    for effect in merge_effects + exclude_effects:
        required_input_ids.update(normalized_id_list(effect.get("canonical_input_ids")))

    input_to_event_ids, scanned_event_count = scan_input_event_links(deduped_events_path, required_input_ids)

    merge_summaries = []
    merge_effects_with_missing_inputs = 0
    merge_effects_already_unified = 0
    merge_effects_cross_event = 0
    projected_event_reduction = 0
    touched_event_ids: set[str] = set()

    for effect in merge_effects:
        input_ids = normalized_id_list(effect.get("canonical_input_ids"))
        missing_input_ids = [input_id for input_id in input_ids if input_id not in input_to_event_ids]
        event_ids = sorted({event_id for input_id in input_ids for event_id in input_to_event_ids.get(input_id, [])})
        touched_event_ids.update(event_ids)
        if missing_input_ids:
            merge_effects_with_missing_inputs += 1
        if len(event_ids) <= 1:
            merge_effects_already_unified += 1
        else:
            merge_effects_cross_event += 1
            projected_event_reduction += len(event_ids) - 1
        merge_summaries.append({
            "review_item_id": effect.get("review_item_id"),
            "effect_id": effect.get("effect_id"),
            "canonical_input_ids": input_ids,
            "event_ids": event_ids,
            "missing_input_ids": missing_input_ids,
            "projected_event_reduction": max(0, len(event_ids) - 1),
        })

    exclude_missing_inputs = []
    for effect in exclude_effects:
        for input_id in normalized_id_list(effect.get("canonical_input_ids")):
            if input_id not in input_to_event_ids:
                exclude_missing_inputs.append({"review_item_id": effect.get("review_item_id"), "canonical_input_id": input_id})

    return {
        "schema_version": 1,
        "impact_policy": "streaming_summary_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "inputs": {
            "effects_plan": str(effects_plan_path),
            "deduped_events": str(deduped_events_path),
        },
        "scanned_event_count": scanned_event_count,
        "required_input_id_count": len(required_input_ids),
        "matched_input_id_count": len(input_to_event_ids),
        "missing_input_id_count": len(required_input_ids - set(input_to_event_ids)),
        "effect_counts": {
            "merge_duplicate_candidate": len(merge_effects),
            "defer_duplicate_candidate": len(defer_effects),
            "preserve_source_row": len(preserve_effects),
            "exclude_source_row": len(exclude_effects),
        },
        "merge_impact": {
            "merge_effects": len(merge_effects),
            "merge_effects_cross_event": merge_effects_cross_event,
            "merge_effects_already_unified": merge_effects_already_unified,
            "merge_effects_with_missing_inputs": merge_effects_with_missing_inputs,
            "touched_event_count": len(touched_event_ids),
            "projected_event_reduction": projected_event_reduction,
        },
        "exclude_impact": {
            "exclude_effects": len(exclude_effects),
            "exclude_missing_input_count": len(exclude_missing_inputs),
            "exclude_missing_inputs_sample": exclude_missing_inputs[:50],
        },
        "merge_samples": {
            "cross_event": [item for item in merge_summaries if item["projected_event_reduction"] > 0][:25],
            "missing_inputs": [item for item in merge_summaries if item["missing_input_ids"]][:25],
            "already_unified": [item for item in merge_summaries if item["projected_event_reduction"] == 0 and not item["missing_input_ids"]][:25],
        },
    }


def scan_input_event_links(
    deduped_events_path: Path,
    required_input_ids: set[str],
) -> tuple[dict[str, list[str]], int]:
    input_to_event_ids: dict[str, list[str]] = {}
    scanned_event_count = 0
    if not required_input_ids:
        return input_to_event_ids, scanned_event_count
    with deduped_events_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ValueError(f"{deduped_events_path} line {line_number} must contain an object.")
            scanned_event_count += 1
            event_id = str(event.get("canonical_event_id") or "")
            if not event_id:
                continue
            event_input_ids = set(normalized_id_list(event.get("canonical_input_ids")))
            matched_ids = event_input_ids & required_input_ids
            for input_id in matched_ids:
                input_to_event_ids.setdefault(input_id, []).append(event_id)
            if len(input_to_event_ids) == len(required_input_ids):
                # Continue scanning would only count events; stop early for impact speed.
                break
    return input_to_event_ids, scanned_event_count


def normalized_id_list(value: Any) -> list[str]:
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if not isinstance(value, list):
        return []
    ids = []
    for item in value:
        text = str(item or "").strip()
        if text:
            ids.append(text)
    return ids


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
    parser.add_argument("--deduped-events", type=Path, default=DEFAULT_DEDUPED_EVENTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = summarize_effect_impact(
        effects_plan_path=args.effects_plan,
        deduped_events_path=args.deduped_events,
    )
    write_json(args.output, report)
    print(json.dumps({
        "output": str(args.output),
        "impact_policy": report["impact_policy"],
        "canonical_outputs_mutated": False,
        "scanned_event_count": report["scanned_event_count"],
        "required_input_id_count": report["required_input_id_count"],
        "matched_input_id_count": report["matched_input_id_count"],
        "projected_event_reduction": report["merge_impact"]["projected_event_reduction"],
        "merge_effects_cross_event": report["merge_impact"]["merge_effects_cross_event"],
        "merge_effects_with_missing_inputs": report["merge_impact"]["merge_effects_with_missing_inputs"],
    }, indent=2, ensure_ascii=False))
    return 0 if report["missing_input_id_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
