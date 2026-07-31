"""Apply audited coordinate review actions to a preview sidecar.

Actions are intentionally explicit and small-scope:

* ``flip_lon`` keeps latitude and flips longitude sign.
* ``set_coordinates`` writes reviewed latitude/longitude.
* ``quarantine`` preserves the event but removes map coordinates pending review.

Canonical source inputs are not mutated.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from scripts.apply_coordinate_sanity_preview import parse_float, write_json


DEFAULT_INPUT = Path("data/canonical_preview_map_enrich_v52_expanded_bounds_quarantine/deduped_events.jsonl")
DEFAULT_ACTIONS = Path("data/reports/coordinate_manual_review_actions_v71.csv")
DEFAULT_OUTPUT_DIR = Path("data/canonical_preview_map_enrich_v71_manual_coordinate_review")
DEFAULT_REPORT = Path("data/reports/coordinate_manual_review_apply_v71.json")


def apply_coordinate_manual_review_actions(
    *,
    input_path: Path,
    actions_csv: Path,
    output_dir: Path,
    report_output: Path,
) -> dict[str, Any]:
    actions = load_actions(actions_csv)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "deduped_events.jsonl"
    tmp_output_path = output_path.with_suffix(".jsonl.tmp")
    action_counts: dict[str, int] = {}
    input_event_count = 0
    output_event_count = 0
    mapped_before_count = 0
    mapped_after_count = 0
    applied_examples: list[dict[str, Any]] = []
    missing_action_ids = set(actions)

    with input_path.open("r", encoding="utf-8") as source, tmp_output_path.open("w", encoding="utf-8", newline="\n") as output:
        for line in source:
            if not line.strip():
                continue
            event = json.loads(line)
            input_event_count += 1
            if has_usable_coordinates(event):
                mapped_before_count += 1
            event_id_candidates = [
                str(event.get("canonical_event_id") or ""),
                str(event.get("event_id") or ""),
            ]
            action_key = next((candidate for candidate in event_id_candidates if candidate in actions), "")
            action = actions.get(action_key)
            if action:
                missing_action_ids.discard(action_key)
                before = coordinate_payload(event)
                event = apply_action(event, action)
                action_name = action["action"]
                action_counts[action_name] = action_counts.get(action_name, 0) + 1
                if len(applied_examples) < 50:
                    applied_examples.append(
                        {
                            "action_key": action_key,
                            "canonical_event_id": event.get("canonical_event_id"),
                            "event_id": event.get("event_id"),
                            "action": action_name,
                            "reason": action.get("reason"),
                            "location_raw": event.get("location_raw"),
                            "before": before,
                            "after": coordinate_payload(event),
                        }
                    )
            if has_usable_coordinates(event):
                mapped_after_count += 1
            output.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
            output_event_count += 1

    tmp_output_path.replace(output_path)
    report = {
        "schema_version": 1,
        "mode": "preview_apply",
        "apply_policy": "manual_coordinate_review_actions",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": True,
        "inputs": {
            "deduped_events": str(input_path),
            "actions_csv": str(actions_csv),
        },
        "outputs": {
            "deduped_events": str(output_path),
            "report": str(report_output),
        },
        "input_event_count": input_event_count,
        "output_event_count": output_event_count,
        "action_row_count": len(actions),
        "applied_action_count": sum(action_counts.values()),
        "missing_action_ids": sorted(missing_action_ids),
        "action_counts": dict(sorted(action_counts.items())),
        "mapped_before_count": mapped_before_count,
        "mapped_after_count": mapped_after_count,
        "mapped_reduction_count": mapped_before_count - mapped_after_count,
        "examples": applied_examples,
        "notes": [
            "Only reviewed rows listed in the action CSV are changed.",
            "Quarantined rows remain in the corpus but are unmapped until reviewed.",
            "Manual review actions are intended for known coordinate-sign errors or high-confidence bad map placements.",
        ],
    }
    write_json(report_output, report)
    return report


def load_actions(path: Path) -> dict[str, dict[str, str]]:
    actions: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            event_id = str(row.get("canonical_event_id") or "").strip()
            action = str(row.get("action") or "").strip()
            if not event_id or action not in {"flip_lon", "set_coordinates", "quarantine"}:
                continue
            actions[event_id] = row
    return actions


def apply_action(event: dict[str, Any], action: dict[str, str]) -> dict[str, Any]:
    next_event = dict(event)
    old_lat = parse_float(next_event.get("lat"))
    old_lon = parse_float(next_event.get("lon"))
    action_name = action["action"]
    reason = action.get("reason") or "manual_coordinate_review"
    next_event["coordinate_manual_review_action"] = action_name
    next_event["coordinate_manual_review_reason"] = reason
    next_event["coordinate_manual_review_original_lat"] = old_lat
    next_event["coordinate_manual_review_original_lon"] = old_lon
    next_event["coordinate_manual_review_original_source"] = next_event.get("coordinate_source")
    next_event["coordinate_manual_review_original_precision"] = next_event.get("location_precision")

    if action_name == "flip_lon":
        if old_lon is None:
            return quarantine_event(next_event, reason)
        next_event["lat"] = old_lat
        next_event["lon"] = -old_lon
        next_event["coordinate_source"] = next_event.get("coordinate_source") or "manual_review"
        append_mapping_note(next_event, f"Manual coordinate review flipped longitude: {reason}.")
        return next_event
    if action_name == "set_coordinates":
        corrected_lat = parse_float(action.get("corrected_lat"))
        corrected_lon = parse_float(action.get("corrected_lon"))
        if corrected_lat is None or corrected_lon is None:
            return quarantine_event(next_event, reason)
        next_event["lat"] = corrected_lat
        next_event["lon"] = corrected_lon
        next_event["coordinate_source"] = "manual_review"
        next_event["location_precision"] = action.get("corrected_precision") or next_event.get("location_precision") or "city"
        append_mapping_note(next_event, f"Manual coordinate review set coordinates: {reason}.")
        return next_event
    return quarantine_event(next_event, reason)


def quarantine_event(event: dict[str, Any], reason: str) -> dict[str, Any]:
    event["coordinate_quarantine_status"] = "quarantine_until_review"
    event["coordinate_quarantine_reason"] = reason
    event["coordinate_quarantine_original_lat"] = event.get("coordinate_manual_review_original_lat")
    event["coordinate_quarantine_original_lon"] = event.get("coordinate_manual_review_original_lon")
    event["coordinate_quarantine_original_source"] = event.get("coordinate_manual_review_original_source")
    event["coordinate_quarantine_original_precision"] = event.get("coordinate_manual_review_original_precision")
    event["lat"] = None
    event["lon"] = None
    event["coordinate_source"] = "unresolved"
    event["location_precision"] = "unknown"
    append_mapping_note(event, f"Manual coordinate review quarantined coordinates: {reason}.")
    return event


def append_mapping_note(event: dict[str, Any], note: str) -> None:
    existing_notes = str(event.get("mapping_notes") or "").strip()
    event["mapping_notes"] = f"{existing_notes} {note}".strip()


def has_usable_coordinates(event: dict[str, Any]) -> bool:
    lat = parse_float(event.get("lat"))
    lon = parse_float(event.get("lon"))
    return lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180


def coordinate_payload(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "lat": event.get("lat"),
        "lon": event.get("lon"),
        "coordinate_source": event.get("coordinate_source"),
        "location_precision": event.get("location_precision"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--actions-csv", type=Path, default=DEFAULT_ACTIONS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = apply_coordinate_manual_review_actions(
        input_path=args.input,
        actions_csv=args.actions_csv,
        output_dir=args.output_dir,
        report_output=args.report_output,
    )
    print(
        json.dumps(
            {
                "output": report["outputs"]["deduped_events"],
                "report": report["outputs"]["report"],
                "applied_action_count": report["applied_action_count"],
                "action_counts": report["action_counts"],
                "mapped_reduction_count": report["mapped_reduction_count"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
