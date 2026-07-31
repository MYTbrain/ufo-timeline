"""Build a compact review packet for ER merge effects blocked by readiness."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


DEFAULT_READINESS = Path("data/reports/entity_resolution_ai_merge_readiness.json")
DEFAULT_MERGED_PREVIEW = Path("data/reports/entity_resolution_ai_merged_event_preview.json")
DEFAULT_JSON_OUTPUT = Path("data/reports/entity_resolution_blocked_merge_review_packet.json")
DEFAULT_CSV_OUTPUT = Path("data/reports/entity_resolution_blocked_merge_review_packet.csv")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/entity_resolution_blocked_merge_review_packet.md")


def build_entity_resolution_blocked_merge_packet(
    *,
    readiness_report: dict[str, Any],
    merged_event_preview: dict[str, Any],
    readiness_path: Path | None = None,
    merged_preview_path: Path | None = None,
) -> dict[str, Any]:
    validate_inputs(readiness_report, merged_event_preview)
    preview_by_review_id = {
        str(item.get("review_item_id")): item
        for item in merged_event_preview.get("previews") or []
        if isinstance(item, dict) and item.get("review_item_id")
    }
    blocking_items = (
        readiness_report.get("blocking_items")
        if isinstance(readiness_report.get("blocking_items"), list)
        else readiness_report.get("blocking_items_sample")
    )
    items = []
    for blocked in blocking_items or []:
        if not isinstance(blocked, dict):
            continue
        review_item_id = str(blocked.get("review_item_id") or "")
        preview = preview_by_review_id.get(review_item_id, {})
        items.append(
            {
                "review_item_id": review_item_id,
                "patch_id": blocked.get("patch_id"),
                "effect_id": blocked.get("effect_id"),
                "blocking_fields": blocked.get("fields") or [],
                "projected_event_reduction": blocked.get("projected_event_reduction"),
                "field_conflicts": preview.get("field_conflicts") if isinstance(preview.get("field_conflicts"), dict) else {},
                "source_event_summaries": preview.get("source_event_summaries") or [],
                "suggested_action": suggested_action(blocked.get("fields") or []),
            }
        )

    return {
        "schema_version": 1,
        "packet_policy": "entity_resolution_blocked_merge_review_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "inputs": {
            "readiness_report": str(readiness_path) if readiness_path else None,
            "merged_event_preview": str(merged_preview_path) if merged_preview_path else None,
        },
        "blocked_item_count": len(items),
        "blocking_field_counts": count_blocking_fields(items),
        "items": items,
        "notes": [
            "This packet is for blocked ER merge review only.",
            "No decisions are created and no canonical outputs are mutated.",
            "Use it to decide whether each blocked merge should become same_event, distinct_events, or needs_more_evidence.",
        ],
    }


def suggested_action(fields: list[str]) -> str:
    field_set = set(fields)
    if "type_normalized" in field_set:
        return "review_type_conflict_before_merge"
    if "coordinate_distance_over_10km" in field_set:
        return "review_coordinate_distance_before_merge"
    return "review_blocking_conflict_before_merge"


def count_blocking_fields(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        for field in item.get("blocking_fields") or []:
            field_name = str(field)
            counts[field_name] = counts.get(field_name, 0) + 1
    return dict(sorted(counts.items()))


def validate_inputs(readiness_report: dict[str, Any], merged_event_preview: dict[str, Any]) -> None:
    errors = []
    if readiness_report.get("readiness_policy") != "entity_resolution_merge_preview_readiness_gate":
        errors.append("readiness_policy must be 'entity_resolution_merge_preview_readiness_gate'")
    if merged_event_preview.get("preview_policy") != "entity_resolution_compact_merged_event_preview_only":
        errors.append("preview_policy must be 'entity_resolution_compact_merged_event_preview_only'")
    for label, payload in [("readiness", readiness_report), ("merged_event_preview", merged_event_preview)]:
        for flag in ("canonical_outputs_mutated", "preview_outputs_written", "auto_merge_performed"):
            if payload.get(flag) is not False:
                errors.append(f"{label}.{flag} must be false")
    if errors:
        raise ValueError(f"blocked merge packet inputs are not safe: {'; '.join(errors)}")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, packet: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "review_item_id",
                "patch_id",
                "effect_id",
                "blocking_fields",
                "projected_event_reduction",
                "suggested_action",
            ],
        )
        writer.writeheader()
        for item in packet.get("items") or []:
            writer.writerow(
                {
                    "review_item_id": item.get("review_item_id"),
                    "patch_id": item.get("patch_id"),
                    "effect_id": item.get("effect_id"),
                    "blocking_fields": ";".join(str(field) for field in item.get("blocking_fields") or []),
                    "projected_event_reduction": item.get("projected_event_reduction"),
                    "suggested_action": item.get("suggested_action"),
                }
            )


def write_markdown(path: Path, packet: dict[str, Any]) -> None:
    lines = [
        "# Entity Resolution Blocked Merge Review Packet",
        "",
        f"- Blocked items: {packet.get('blocked_item_count')}",
        f"- Blocking field counts: `{json.dumps(packet.get('blocking_field_counts') or {}, sort_keys=True)}`",
        "- Canonical outputs mutated: false",
        "",
    ]
    for index, item in enumerate(packet.get("items") or [], start=1):
        lines.extend(
            [
                f"## {index}. {item.get('review_item_id')}",
                "",
                f"- Patch: `{item.get('patch_id')}`",
                f"- Effect: `{item.get('effect_id')}`",
                f"- Blocking fields: `{', '.join(str(field) for field in item.get('blocking_fields') or [])}`",
                f"- Suggested action: `{item.get('suggested_action')}`",
                "",
                "Source events:",
            ]
        )
        for source in item.get("source_event_summaries") or []:
            if not isinstance(source, dict):
                continue
            lines.append(
                "- "
                f"`{source.get('canonical_event_id')}` "
                f"{source.get('date_iso') or ''} {source.get('time_raw') or ''} "
                f"{source.get('location_raw') or ''} "
                f"type={source.get('type_normalized') or ''} "
                f"summary={source.get('summary') or ''}"
            )
        lines.extend(["", "Field conflicts:", ""])
        for field, values in sorted((item.get("field_conflicts") or {}).items()):
            lines.append(f"- `{field}`: `{json.dumps(values, ensure_ascii=False)}`")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readiness-report", type=Path, default=DEFAULT_READINESS)
    parser.add_argument("--merged-event-preview", type=Path, default=DEFAULT_MERGED_PREVIEW)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    readiness_report = read_json(args.readiness_report)
    merged_event_preview = read_json(args.merged_event_preview)
    packet = build_entity_resolution_blocked_merge_packet(
        readiness_report=readiness_report,
        merged_event_preview=merged_event_preview,
        readiness_path=args.readiness_report,
        merged_preview_path=args.merged_event_preview,
    )
    write_json(args.json_output, packet)
    write_csv(args.csv_output, packet)
    write_markdown(args.markdown_output, packet)
    print(
        json.dumps(
            {
                "json_output": str(args.json_output),
                "csv_output": str(args.csv_output),
                "markdown_output": str(args.markdown_output),
                "blocked_item_count": packet["blocked_item_count"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
