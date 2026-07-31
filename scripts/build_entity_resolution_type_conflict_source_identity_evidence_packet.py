"""Build source-row evidence for unresolved type-conflict identity reviews.

This packet targets the `source_row_identity_review` lane from the unresolved
type-conflict next queue. It is review-only and does not create ER decisions or
mutate canonical artifacts.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from scripts.build_entity_resolution_cluster_time_norm_source_evidence_packet import (
    CSV_FIELDS,
    clean_text,
    conflict_summary,
    csv_row,
    evidence_row_from_event,
    load_requested_event_rows,
    string_list,
    summarize_rows,
    write_json,
)


DEFAULT_QUEUE = Path("data/reports/entity_resolution_type_conflict_next_queue_worklist.json")
DEFAULT_DEDUPED_EVENTS = Path("data/canonical_full/deduped_events.jsonl")
DEFAULT_JSON_OUTPUT = Path("data/reports/entity_resolution_type_conflict_source_identity_evidence_packet_worklist.json")
DEFAULT_CSV_OUTPUT = Path("data/reports/entity_resolution_type_conflict_source_identity_evidence_packet_worklist.csv")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/entity_resolution_type_conflict_source_identity_evidence_packet_worklist.md")

INPUT_QUEUE_POLICY = "entity_resolution_type_conflict_next_queue_review_only"
PACKET_POLICY = "entity_resolution_type_conflict_source_identity_evidence_review_only"
TARGET_LANE = "source_row_identity_review"


def build_type_conflict_source_identity_evidence_packet(
    *,
    queue: dict[str, Any],
    deduped_events_path: Path,
    queue_path: Path | None = None,
    target_lane: str = TARGET_LANE,
    packet_policy: str = PACKET_POLICY,
) -> dict[str, Any]:
    validate_queue_safety(queue)
    candidates = [
        item
        for item in queue.get("items") or []
        if isinstance(item, dict) and clean_text(item.get("next_lane")) == target_lane
    ]
    requested_event_ids = sorted(
        {
            event_id
            for item in candidates
            for event_id in string_list(item.get("canonical_event_ids"))
        }
    )
    event_rows = load_requested_event_rows(deduped_events_path, requested_event_ids)
    missing_event_ids = sorted(set(requested_event_ids) - set(event_rows))
    items = [evidence_item_from_queue_item(candidate, event_rows) for candidate in candidates]
    for index, item in enumerate(items, start=1):
        item["review_rank"] = index

    candidate_input_ids = sorted(
        {
            input_id
            for item in candidates
            for input_id in string_list(item.get("canonical_input_ids"))
        }
    )
    evidence_input_ids = sorted(
        {
            input_id
            for row in event_rows.values()
            for input_id in string_list(row.get("canonical_input_ids")) + [clean_text(row.get("canonical_input_id"))]
            if input_id
        }
    )
    return {
        "schema_version": 1,
        "packet_policy": packet_policy,
        "input_queue_policy": queue.get("report_policy"),
        "target_lane": target_lane,
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "inputs": {
            "queue": str(queue_path) if queue_path else None,
            "deduped_events": str(deduped_events_path),
        },
        "summary": {
            "candidate_effect_count": len(candidates),
            "requested_canonical_event_id_count": len(requested_event_ids),
            "matched_canonical_event_id_count": len(event_rows),
            "missing_canonical_event_id_count": len(missing_event_ids),
            "candidate_input_id_count": len(candidate_input_ids),
            "evidence_input_id_count": len(evidence_input_ids),
            "candidate_input_ids_missing_from_evidence_count": len(
                sorted(set(candidate_input_ids) - set(evidence_input_ids))
            ),
            "items_with_missing_events": sum(1 for item in items if item.get("missing_canonical_event_ids")),
            "projected_event_reduction_sum_not_deduped": sum(
                int(candidate.get("projected_event_reduction") or 0) for candidate in candidates
            ),
        },
        "missing_canonical_event_ids": missing_event_ids,
        "candidate_input_ids": candidate_input_ids,
        "evidence_input_ids": evidence_input_ids,
        "candidate_input_ids_missing_from_evidence": sorted(set(candidate_input_ids) - set(evidence_input_ids)),
        "items": items,
        "notes": [
            "This packet is source-row evidence for review only.",
            f"It targets unresolved type conflicts in the {target_lane} lane.",
            "It does not create accepted ER decisions, apply merges, or mutate canonical outputs.",
        ],
    }


def validate_queue_safety(queue: dict[str, Any]) -> None:
    errors: list[str] = []
    if queue.get("report_policy") != INPUT_QUEUE_POLICY:
        errors.append(f"report_policy must be {INPUT_QUEUE_POLICY}")
    for flag in (
        "canonical_outputs_mutated",
        "preview_outputs_written",
        "decisions_created",
        "decision_outputs_created",
        "auto_merge_performed",
        "ready_for_canonical_apply",
    ):
        if queue.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError("type-conflict next queue is unsafe for source evidence packet: " + "; ".join(errors))


def evidence_item_from_queue_item(candidate: dict[str, Any], event_rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    event_ids = string_list(candidate.get("canonical_event_ids"))
    rows = [evidence_row_from_event(event_rows[event_id]) for event_id in event_ids if event_id in event_rows]
    candidate_input_ids = string_list(candidate.get("canonical_input_ids"))
    evidence_input_ids = sorted(
        {
            input_id
            for row in rows
            for input_id in string_list(row.get("canonical_input_ids")) + [clean_text(row.get("canonical_input_id"))]
            if input_id
        }
    )
    return {
        "review_rank": None,
        "review_item_id": clean_text(candidate.get("review_item_id")),
        "effect_id": clean_text(candidate.get("effect_id")),
        "patch_id": clean_text(candidate.get("patch_id")),
        "next_lane": clean_text(candidate.get("next_lane")),
        "next_action": clean_text(candidate.get("next_action")),
        "projected_event_reduction": int(candidate.get("projected_event_reduction") or 0),
        "type_conflict_classification": clean_text(candidate.get("type_conflict_classification")),
        "review_risk_tier": clean_text(candidate.get("review_risk_tier")),
        "identity_consistency": clean_text(candidate.get("identity_consistency")),
        "type_values": string_list(candidate.get("type_values")),
        "type_family_prefixes": string_list(candidate.get("type_family_prefixes")),
        "shape_values": string_list(candidate.get("shape_values")),
        "risk_flags": string_list(candidate.get("risk_flags")),
        "blocking_fields": string_list(candidate.get("blocking_fields")),
        "candidate_canonical_input_ids": candidate_input_ids,
        "candidate_input_ids_missing_from_evidence": sorted(set(candidate_input_ids) - set(evidence_input_ids)),
        "merge_canonical_event_ids": event_ids,
        "missing_canonical_event_ids": [event_id for event_id in event_ids if event_id not in event_rows],
        "source_summary": summarize_rows(rows),
        "conflict_summary": conflict_summary(rows),
        "reviewer_prompts": [
            "Do the source rows refer to one report or nearby/separate reports?",
            "Do the location text variants refer to the same place?",
            "Are type-family differences only source coding variants or true contradictions?",
            "Is there enough source evidence for future same-event decision staging?",
        ],
        "evidence_rows": rows,
    }


def write_csv(path: Path, packet: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for item in packet.get("items") or []:
            if not isinstance(item, dict):
                continue
            for row in item.get("evidence_rows") or []:
                if isinstance(row, dict):
                    writer.writerow(csv_row(item, row))


def write_markdown(path: Path, packet: dict[str, Any], *, item_limit: int, row_limit_per_item: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = packet.get("summary") if isinstance(packet.get("summary"), dict) else {}
    lines = [
        "# Type-Conflict Source Evidence Packet",
        "",
        "This packet is review-only. It shows source rows for a selected unresolved type-conflict lane.",
        "",
        "## Summary",
        "",
        f"- Target lane: `{packet.get('target_lane')}`",
        f"- Candidate effects: `{summary.get('candidate_effect_count', 0)}`",
        f"- Requested canonical events: `{summary.get('requested_canonical_event_id_count', 0)}`",
        f"- Matched canonical events: `{summary.get('matched_canonical_event_id_count', 0)}`",
        f"- Missing canonical events: `{summary.get('missing_canonical_event_id_count', 0)}`",
        f"- Candidate input IDs missing from evidence: `{summary.get('candidate_input_ids_missing_from_evidence_count', 0)}`",
        f"- Projected reduction, not deduped: `{summary.get('projected_event_reduction_sum_not_deduped', 0)}`",
        f"- Canonical outputs mutated: `{str(packet.get('canonical_outputs_mutated')).lower()}`",
        "",
        "## Candidate Effects",
        "",
    ]
    items = [item for item in packet.get("items") or [] if isinstance(item, dict)]
    for item in items[: max(0, item_limit)]:
        lines.extend(markdown_item_lines(item, row_limit_per_item=row_limit_per_item))
    if len(items) > item_limit:
        lines.extend(["", f"_Markdown limited to {item_limit} of {len(items)} candidate effects._", ""])
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def markdown_item_lines(item: dict[str, Any], *, row_limit_per_item: int) -> list[str]:
    summary = item.get("source_summary") if isinstance(item.get("source_summary"), dict) else {}
    conflicts = item.get("conflict_summary") if isinstance(item.get("conflict_summary"), dict) else {}
    flags = conflicts.get("conflict_flags") if isinstance(conflicts.get("conflict_flags"), dict) else {}
    lines = [
        f"### #{item.get('review_rank')} {item.get('review_item_id')}",
        "",
        f"- Effect ID: `{item.get('effect_id')}`",
        f"- Projected reduction: `{item.get('projected_event_reduction')}`",
        f"- Classification: `{item.get('type_conflict_classification')}` risk `{item.get('review_risk_tier')}`",
        f"- Identity consistency: `{item.get('identity_consistency')}`",
        f"- Type values: {', '.join(string_list(item.get('type_values'))) or 'none'}",
        f"- Source names: {', '.join(string_list(summary.get('source_names'))) or 'none'}",
        f"- Source native IDs: {', '.join(string_list(summary.get('source_native_ids'))) or 'none'}",
        f"- Dates: {', '.join(string_list(summary.get('date_values'))) or 'none'}",
        f"- Locations: {', '.join(string_list(summary.get('location_values'))) or 'none'}",
        f"- Conflict flags: {', '.join(name for name, active in flags.items() if active) or 'none'}",
        f"- Next action: {item.get('next_action')}",
        f"- Candidate input IDs missing from evidence: {', '.join(string_list(item.get('candidate_input_ids_missing_from_evidence'))) or 'none'}",
        "",
    ]
    rows = [row for row in item.get("evidence_rows") or [] if isinstance(row, dict)]
    for row in rows[: max(0, row_limit_per_item)]:
        lines.extend(
            [
                f"  - `{row.get('canonical_event_id')}` input `{'; '.join(string_list(row.get('canonical_input_ids'))) or row.get('canonical_input_id')}`",
                f"    - Source: `{row.get('source_name')}` file `{row.get('source_file')}` row `{row.get('source_row_number')}` native `{row.get('source_native_id')}`",
                f"    - Date/time/location: `{row.get('date_iso')}` / `{row.get('time_raw')}` / `{row.get('location_raw')}`",
                f"    - Type/shape: `{row.get('type_normalized')}` / `{row.get('shape_normalized')}`",
                f"    - Summary: {row.get('summary') or 'none'}",
            ]
        )
    if len(rows) > row_limit_per_item:
        lines.append(f"  - _Rows limited to {row_limit_per_item} of {len(rows)}._")
    lines.append("")
    return lines


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--deduped-events", type=Path, default=DEFAULT_DEDUPED_EVENTS)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument("--markdown-item-limit", type=int, default=40)
    parser.add_argument("--markdown-row-limit-per-item", type=int, default=8)
    parser.add_argument("--target-lane", default=TARGET_LANE)
    parser.add_argument("--packet-policy", default=PACKET_POLICY)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packet = build_type_conflict_source_identity_evidence_packet(
        queue=read_json(args.queue),
        deduped_events_path=args.deduped_events,
        queue_path=args.queue,
        target_lane=args.target_lane,
        packet_policy=args.packet_policy,
    )
    write_json(args.json_output, packet)
    write_csv(args.csv_output, packet)
    write_markdown(
        args.markdown_output,
        packet,
        item_limit=args.markdown_item_limit,
        row_limit_per_item=args.markdown_row_limit_per_item,
    )
    print(
        json.dumps(
            {
                "json_output": str(args.json_output),
                "csv_output": str(args.csv_output),
                "markdown_output": str(args.markdown_output),
                "packet_policy": packet["packet_policy"],
                "candidate_effect_count": packet["summary"]["candidate_effect_count"],
                "matched_canonical_event_id_count": packet["summary"]["matched_canonical_event_id_count"],
                "missing_canonical_event_id_count": packet["summary"]["missing_canonical_event_id_count"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
