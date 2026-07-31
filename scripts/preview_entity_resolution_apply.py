"""Stream a preview-only deduped_events output for ER merge effects.

This script is intentionally preview-only. It never overwrites canonical
artifacts and only buffers the event rows that participate in planned ER merge
groups.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from parser.canonical_schema import clean_text


DEFAULT_EFFECTS_PLAN = Path("data/reports/entity_resolution_effects_plan.json")
DEFAULT_DEDUPED_EVENTS = Path("data/canonical_full/deduped_events.jsonl")
DEFAULT_OUTPUT_DIR = Path("data/canonical_preview_entity_resolution")
DEFAULT_REPORT_OUTPUT = Path("data/reports/entity_resolution_preview_apply_report.json")


class DisjointSet:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}
        self.rank: dict[str, int] = {}

    def add(self, value: str) -> None:
        if value not in self.parent:
            self.parent[value] = value
            self.rank[value] = 0

    def find(self, value: str) -> str:
        self.add(value)
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        if self.rank[left_root] < self.rank[right_root]:
            left_root, right_root = right_root, left_root
        self.parent[right_root] = left_root
        if self.rank[left_root] == self.rank[right_root]:
            self.rank[left_root] += 1


def preview_entity_resolution_apply(
    *,
    effects_plan: dict[str, Any],
    deduped_events_path: Path,
    output_dir: Path,
    report_output_path: Path | None = None,
    write_noop_output: bool = False,
) -> dict[str, Any]:
    validate_effects_plan(effects_plan)
    merge_effects = [
        effect
        for effect in effects_plan.get("effects", [])
        if isinstance(effect, dict) and effect.get("planned_effect") == "merge_entity_resolution_candidate"
    ]
    if not merge_effects and not write_noop_output:
        return {
            "schema_version": 1,
            "mode": "preview",
            "apply_policy": "entity_resolution_stream_preview_only",
            "canonical_outputs_mutated": False,
            "preview_outputs_written": False,
            "input_event_count": 0,
            "preview_event_count": 0,
            "effects_requested": 0,
            "effects_applied": 0,
            "effects_blocked": 0,
            "projected_event_reduction": 0,
            "outputs": {},
            "blocked_effects": [],
            "applied_effects": [],
            "notes": ["No merge effects were present; no shadow deduped_events output was written."],
        }

    merge_plan = build_merge_plan(merge_effects)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "deduped_events.jsonl"
    tmp_output_path = output_path.with_suffix(output_path.suffix + ".tmp")

    input_event_count = 0
    passthrough_event_count = 0
    merge_rows: dict[str, list[dict[str, Any]]] = {group_id: [] for group_id in merge_plan["group_event_ids"]}
    found_event_ids: set[str] = set()

    with tmp_output_path.open("w", encoding="utf-8", newline="\n") as output:
        for event in iter_jsonl(deduped_events_path):
            input_event_count += 1
            event_id = clean_text(event.get("canonical_event_id")) or clean_text(event.get("event_id"))
            group_id = merge_plan["event_to_group"].get(event_id)
            if group_id:
                merge_rows[group_id].append(event)
                found_event_ids.add(event_id)
                continue
            output.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
            passthrough_event_count += 1

        blocked_effects = blocked_effects_for_missing_events(merge_effects, found_event_ids)
        blocked_effect_ids = {effect.get("effect_id") for effect in blocked_effects}
        applied_effects: list[dict[str, Any]] = []
        preview_event_count = passthrough_event_count
        for group_id, rows in sorted(merge_rows.items()):
            group_effects = [
                effect
                for effect in merge_plan["group_effects"][group_id]
                if effect.get("effect_id") not in blocked_effect_ids
            ]
            if not group_effects:
                for row in rows:
                    output.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
                    preview_event_count += 1
                continue
            merged_event = merge_event_rows(rows, effects=group_effects)
            output.write(json.dumps(merged_event, ensure_ascii=False, separators=(",", ":")) + "\n")
            preview_event_count += 1
            applied_effects.extend(effect_summary(effect, merged_event=merged_event) for effect in group_effects)

    tmp_output_path.replace(output_path)
    projected_reduction = input_event_count - preview_event_count
    report = {
        "schema_version": 1,
        "mode": "preview",
        "apply_policy": "entity_resolution_stream_preview_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": True,
        "inputs": {
            "deduped_events": str(deduped_events_path),
        },
        "outputs": {
            "deduped_events": str(output_path),
            "report": str(report_output_path) if report_output_path else None,
        },
        "input_event_count": input_event_count,
        "preview_event_count": preview_event_count,
        "effects_requested": len(merge_effects),
        "effects_applied": len(applied_effects),
        "effects_blocked": len(blocked_effects),
        "projected_event_reduction": projected_reduction,
        "blocked_effects": blocked_effects,
        "applied_effects": applied_effects,
        "safety_notes": [
            "Preview writes only a shadow deduped_events.jsonl under the output directory.",
            "Canonical source artifacts are not overwritten.",
            "Promotion/apply mode is intentionally not implemented.",
        ],
    }
    return report


def validate_effects_plan(effects_plan: dict[str, Any]) -> None:
    if effects_plan.get("effect_policy") != "entity_resolution_plan_only":
        raise ValueError("Effects plan must have effect_policy=entity_resolution_plan_only.")
    if effects_plan.get("canonical_outputs_mutated") is not False:
        raise ValueError("Effects plan must declare canonical_outputs_mutated=false.")


def build_merge_plan(merge_effects: list[dict[str, Any]]) -> dict[str, Any]:
    dsu = DisjointSet()
    effect_event_ids: dict[str, list[str]] = {}
    for effect in merge_effects:
        event_ids = string_list(effect.get("merge_canonical_event_ids"))
        if len(event_ids) < 2:
            continue
        first = event_ids[0]
        dsu.add(first)
        for event_id in event_ids[1:]:
            dsu.union(first, event_id)
        effect_event_ids[clean_text(effect.get("effect_id")) or ""] = event_ids

    group_event_ids: dict[str, set[str]] = {}
    event_to_group: dict[str, str] = {}
    for event_ids in effect_event_ids.values():
        for event_id in event_ids:
            group_id = dsu.find(event_id)
            group_event_ids.setdefault(group_id, set()).add(event_id)
            event_to_group[event_id] = group_id

    group_effects: dict[str, list[dict[str, Any]]] = {group_id: [] for group_id in group_event_ids}
    for effect in merge_effects:
        event_ids = string_list(effect.get("merge_canonical_event_ids"))
        if len(event_ids) < 2:
            continue
        group_effects[dsu.find(event_ids[0])].append(effect)
    return {
        "event_to_group": event_to_group,
        "group_event_ids": group_event_ids,
        "group_effects": group_effects,
    }


def blocked_effects_for_missing_events(merge_effects: list[dict[str, Any]], found_event_ids: set[str]) -> list[dict[str, Any]]:
    blocked: list[dict[str, Any]] = []
    for effect in merge_effects:
        event_ids = string_list(effect.get("merge_canonical_event_ids"))
        missing = [event_id for event_id in event_ids if event_id not in found_event_ids]
        if missing:
            blocked.append(
                {
                    "effect_id": clean_text(effect.get("effect_id")),
                    "review_item_id": clean_text(effect.get("review_item_id")),
                    "planned_effect": effect.get("planned_effect"),
                    "reason": "missing_merge_canonical_event_ids",
                    "missing_event_ids": missing,
                }
            )
    return blocked


def merge_event_rows(rows: list[dict[str, Any]], *, effects: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise ValueError("Cannot merge empty event row group.")
    rows = sorted(rows, key=lambda row: str(row.get("canonical_event_id") or ""))
    target = dict(rows[0])
    input_ids: list[str] = []
    provenance: list[dict[str, Any]] = []
    provenance_keys: set[str] = set()
    merged_event_ids: list[str] = []
    effect_ids = [clean_text(effect.get("effect_id")) for effect in effects if clean_text(effect.get("effect_id"))]

    for row in rows:
        event_id = clean_text(row.get("canonical_event_id"))
        if event_id and event_id not in merged_event_ids:
            merged_event_ids.append(event_id)
        for input_id in string_list(row.get("canonical_input_ids")):
            if input_id not in input_ids:
                input_ids.append(input_id)
        for item in row.get("source_provenance") or []:
            if not isinstance(item, dict):
                continue
            key = json.dumps(item, ensure_ascii=False, sort_keys=True)
            if key not in provenance_keys:
                provenance.append(item)
                provenance_keys.add(key)

    target["canonical_input_ids"] = input_ids
    target["canonical_input_id"] = input_ids[0] if input_ids else target.get("canonical_input_id")
    target["duplicate_record_count"] = len(input_ids)
    target["source_provenance"] = provenance
    target["dedupe_strategy"] = "entity_resolution_preview_merge"
    target["entity_resolution_preview_merged_event_ids"] = merged_event_ids
    target["entity_resolution_preview_effect_ids"] = effect_ids
    return target


def effect_summary(effect: dict[str, Any], *, merged_event: dict[str, Any]) -> dict[str, Any]:
    return {
        "effect_id": clean_text(effect.get("effect_id")),
        "review_item_id": clean_text(effect.get("review_item_id")),
        "planned_effect": effect.get("planned_effect"),
        "preview_canonical_event_id": clean_text(merged_event.get("canonical_event_id")),
        "merged_event_ids": merged_event.get("entity_resolution_preview_merged_event_ids") or [],
        "canonical_input_ids": merged_event.get("canonical_input_ids") or [],
    }


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


def string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [text for item in value if (text := clean_text(item))]
    text = clean_text(value)
    return [text] if text else []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--effects-plan", type=Path, default=DEFAULT_EFFECTS_PLAN)
    parser.add_argument("--deduped-events", type=Path, default=DEFAULT_DEDUPED_EVENTS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    parser.add_argument(
        "--write-noop-output",
        action="store_true",
        help="Copy a shadow deduped_events output even when there are no merge effects.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    effects_plan = read_json(args.effects_plan)
    report = preview_entity_resolution_apply(
        effects_plan=effects_plan,
        deduped_events_path=args.deduped_events,
        output_dir=args.output_dir,
        report_output_path=args.report_output,
        write_noop_output=args.write_noop_output,
    )
    write_json(args.report_output, report)
    print(
        json.dumps(
            {
                "report_output": str(args.report_output),
                "preview_outputs_written": report["preview_outputs_written"],
                "effects_requested": report["effects_requested"],
                "effects_applied": report["effects_applied"],
                "effects_blocked": report["effects_blocked"],
                "projected_event_reduction": report["projected_event_reduction"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
