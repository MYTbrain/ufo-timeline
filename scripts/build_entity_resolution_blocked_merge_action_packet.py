"""Build a joined action packet from blocked ER merge analysis and details.

This is review-only. It joins the compact blocker classifications back to the
blocked merge packet so analysts can work a targeted queue without weakening
readiness gates or applying merges.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from parser.canonical_schema import clean_text


DEFAULT_BLOCKED_PACKET = Path("data/reports/entity_resolution_blocked_merge_review_packet.json")
DEFAULT_BLOCKED_ANALYSIS = Path("data/reports/entity_resolution_blocked_merge_analysis.json")
DEFAULT_JSON_OUTPUT = Path("data/reports/entity_resolution_blocked_merge_action_packet.json")
DEFAULT_CSV_OUTPUT = Path("data/reports/entity_resolution_blocked_merge_action_packet.csv")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/entity_resolution_blocked_merge_action_packet.md")

CSV_FIELDS = (
    "review_item_id",
    "classification",
    "suggested_action",
    "analysis_confidence",
    "projected_event_reduction",
    "blocking_fields",
    "time_values",
    "type_values",
    "source_names",
    "source_native_ids",
    "canonical_event_ids",
    "canonical_input_ids",
    "date_values",
    "location_values",
    "reasons",
    "risks",
)


def build_entity_resolution_blocked_merge_action_packet(
    *,
    blocked_packet: dict[str, Any],
    blocked_analysis: dict[str, Any],
    blocked_packet_path: Path | None = None,
    blocked_analysis_path: Path | None = None,
    include_classifications: set[str] | None = None,
) -> dict[str, Any]:
    validate_input_safety(blocked_packet, blocked_analysis)
    details_by_id = {
        clean_text(item.get("review_item_id")): item
        for item in blocked_packet.get("items") or []
        if isinstance(item, dict) and clean_text(item.get("review_item_id"))
    }
    items: list[dict[str, Any]] = []
    missing_detail_ids: list[str] = []
    for analysis_item in blocked_analysis.get("items") or []:
        if not isinstance(analysis_item, dict):
            continue
        classification = clean_text(analysis_item.get("classification")) or "unknown"
        if include_classifications and classification not in include_classifications:
            continue
        review_item_id = clean_text(analysis_item.get("review_item_id"))
        detail_item = details_by_id.get(review_item_id)
        if detail_item is None:
            if review_item_id:
                missing_detail_ids.append(review_item_id)
            continue
        items.append(action_item_from_analysis_and_detail(analysis_item, detail_item))
    items.sort(
        key=lambda item: (
            str(item.get("classification") or ""),
            str(item.get("analysis_confidence") or ""),
            -int(item.get("projected_event_reduction") or 0),
            str(item.get("review_item_id") or ""),
        )
    )
    return {
        "schema_version": 1,
        "packet_policy": "entity_resolution_blocked_merge_action_review_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "inputs": {
            "blocked_packet": str(blocked_packet_path) if blocked_packet_path else None,
            "blocked_analysis": str(blocked_analysis_path) if blocked_analysis_path else None,
        },
        "include_classifications": sorted(include_classifications) if include_classifications else None,
        "export_summary": {
            "exported_item_count": len(items),
            "classification_counts": count_by(items, "classification"),
            "suggested_action_counts": count_by(items, "suggested_action"),
            "confidence_counts": count_by(items, "analysis_confidence"),
            "projected_reduction_sum_not_deduped": sum(int(item.get("projected_event_reduction") or 0) for item in items),
            "missing_detail_count": len(missing_detail_ids),
        },
        "missing_detail_ids": missing_detail_ids[:100],
        "missing_detail_ids_truncated": len(missing_detail_ids) > 100,
        "items": items,
    }


def action_item_from_analysis_and_detail(analysis_item: dict[str, Any], detail_item: dict[str, Any]) -> dict[str, Any]:
    field_conflicts = detail_item.get("field_conflicts") if isinstance(detail_item.get("field_conflicts"), dict) else {}
    sources = [source for source in detail_item.get("source_event_summaries") or [] if isinstance(source, dict)]
    canonical_event_ids = unique_values(source.get("canonical_event_id") for source in sources)
    canonical_input_ids = unique_values(
        input_id
        for source in sources
        for input_id in string_list(source.get("canonical_input_ids"))
    )
    return {
        "review_item_id": clean_text(analysis_item.get("review_item_id")),
        "patch_id": clean_text(analysis_item.get("patch_id")),
        "effect_id": clean_text(analysis_item.get("effect_id")),
        "classification": clean_text(analysis_item.get("classification")) or "unknown",
        "suggested_action": clean_text(analysis_item.get("suggested_action")) or "needs_human_review",
        "analysis_confidence": clean_text(analysis_item.get("analysis_confidence")) or "unknown",
        "projected_event_reduction": as_int(analysis_item.get("projected_event_reduction")) or 0,
        "blocking_fields": string_list(analysis_item.get("blocking_fields")),
        "reasons": string_list(analysis_item.get("reasons")),
        "risks": string_list(analysis_item.get("risks")),
        "field_conflict_values": {
            "time_raw": string_list(field_conflicts.get("time_raw")),
            "type_normalized": string_list(field_conflicts.get("type_normalized")),
            "shape_normalized": string_list(field_conflicts.get("shape_normalized")),
        },
        "source_summary": {
            "canonical_event_ids": canonical_event_ids,
            "canonical_input_ids": canonical_input_ids,
            "canonical_event_count": len(canonical_event_ids),
            "canonical_input_id_count": len(canonical_input_ids),
            "source_names": unique_values(source.get("source_name") for source in sources),
            "source_native_ids": unique_values(source.get("source_native_id") for source in sources),
            "date_values": unique_values(source.get("date_iso") for source in sources),
            "time_values": unique_values(source.get("time_raw") for source in sources),
            "location_values": unique_values(source.get("location_raw") for source in sources),
            "type_values": unique_values(source.get("type_normalized") for source in sources),
            "source_event_count": len(sources),
        },
    }


def validate_input_safety(blocked_packet: dict[str, Any], blocked_analysis: dict[str, Any]) -> None:
    errors: list[str] = []
    if blocked_packet.get("packet_policy") != "entity_resolution_blocked_merge_review_only":
        errors.append("blocked packet policy must be 'entity_resolution_blocked_merge_review_only'")
    if blocked_analysis.get("analysis_policy") != "entity_resolution_blocked_merge_analysis_only":
        errors.append("blocked analysis policy must be 'entity_resolution_blocked_merge_analysis_only'")
    for label, payload in (("blocked packet", blocked_packet), ("blocked analysis", blocked_analysis)):
        for flag in ("canonical_outputs_mutated", "preview_outputs_written", "decisions_created", "auto_merge_performed"):
            if payload.get(flag) is not False:
                errors.append(f"{label} {flag} must be false")
    if errors:
        raise ValueError(f"inputs are not safe for blocked action packet: {'; '.join(errors)}")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for item in items:
            writer.writerow(csv_row(item))


def csv_row(item: dict[str, Any]) -> dict[str, Any]:
    source_summary = item.get("source_summary") if isinstance(item.get("source_summary"), dict) else {}
    conflicts = item.get("field_conflict_values") if isinstance(item.get("field_conflict_values"), dict) else {}
    return {
        "review_item_id": item.get("review_item_id"),
        "classification": item.get("classification"),
        "suggested_action": item.get("suggested_action"),
        "analysis_confidence": item.get("analysis_confidence"),
        "projected_event_reduction": item.get("projected_event_reduction"),
        "blocking_fields": "; ".join(string_list(item.get("blocking_fields"))),
        "time_values": "; ".join(string_list(conflicts.get("time_raw")) or string_list(source_summary.get("time_values"))),
        "type_values": "; ".join(string_list(conflicts.get("type_normalized")) or string_list(source_summary.get("type_values"))),
        "source_names": "; ".join(string_list(source_summary.get("source_names"))),
        "source_native_ids": "; ".join(string_list(source_summary.get("source_native_ids"))),
        "canonical_event_ids": "; ".join(string_list(source_summary.get("canonical_event_ids"))),
        "canonical_input_ids": "; ".join(string_list(source_summary.get("canonical_input_ids"))),
        "date_values": "; ".join(string_list(source_summary.get("date_values"))),
        "location_values": "; ".join(string_list(source_summary.get("location_values"))),
        "reasons": "; ".join(string_list(item.get("reasons"))),
        "risks": "; ".join(string_list(item.get("risks"))),
    }


def write_markdown(path: Path, packet: dict[str, Any], *, item_limit: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    items = packet.get("items") if isinstance(packet.get("items"), list) else []
    shown = items[: max(0, item_limit)]
    summary = packet.get("export_summary") if isinstance(packet.get("export_summary"), dict) else {}
    lines = [
        "# Entity-Resolution Blocked Merge Action Packet",
        "",
        "This packet is review-only. It joins readiness blockers with blocker classifications and source details.",
        "",
        "## Summary",
        "",
        f"- Exported items: {summary.get('exported_item_count', 0)}",
        f"- Classification counts: `{json.dumps(summary.get('classification_counts', {}), sort_keys=True)}`",
        f"- Canonical outputs mutated: `{str(packet.get('canonical_outputs_mutated')).lower()}`",
        "",
        "## Items",
        "",
    ]
    for item in shown:
        lines.extend(markdown_item_lines(item))
    if len(items) > len(shown):
        lines.extend(["", f"_Markdown limited to {len(shown)} of {len(items)} exported items._", ""])
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def markdown_item_lines(item: dict[str, Any]) -> list[str]:
    source_summary = item.get("source_summary") if isinstance(item.get("source_summary"), dict) else {}
    conflicts = item.get("field_conflict_values") if isinstance(item.get("field_conflict_values"), dict) else {}
    return [
        f"### {item.get('review_item_id')}",
        "",
        f"- Classification: `{item.get('classification')}` action `{item.get('suggested_action')}` confidence `{item.get('analysis_confidence')}`",
        f"- Projected reduction: `{item.get('projected_event_reduction')}`",
        f"- Blocking fields: {', '.join(string_list(item.get('blocking_fields'))) or 'none'}",
        f"- Time values: {', '.join(string_list(conflicts.get('time_raw')) or string_list(source_summary.get('time_values'))) or 'none'}",
        f"- Type values: {', '.join(string_list(conflicts.get('type_normalized')) or string_list(source_summary.get('type_values'))) or 'none'}",
        f"- Locations: {', '.join(string_list(source_summary.get('location_values'))) or 'none'}",
        f"- Reasons: {'; '.join(string_list(item.get('reasons'))) or 'none'}",
        "",
    ]


def unique_values(values: Any) -> list[str]:
    return sorted({text for value in values if (text := clean_text(value))})


def string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [text for item in value if (text := clean_text(item))]
    text = clean_text(value)
    return [text] if text else []


def as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def count_by(items: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = clean_text(item.get(field)) or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blocked-packet", type=Path, default=DEFAULT_BLOCKED_PACKET)
    parser.add_argument("--blocked-analysis", type=Path, default=DEFAULT_BLOCKED_ANALYSIS)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument("--include-classification", action="append")
    parser.add_argument("--markdown-item-limit", type=int, default=200)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    blocked_packet = read_json(args.blocked_packet)
    blocked_analysis = read_json(args.blocked_analysis)
    packet = build_entity_resolution_blocked_merge_action_packet(
        blocked_packet=blocked_packet,
        blocked_analysis=blocked_analysis,
        blocked_packet_path=args.blocked_packet,
        blocked_analysis_path=args.blocked_analysis,
        include_classifications=set(args.include_classification) if args.include_classification else None,
    )
    write_json(args.json_output, packet)
    write_csv(args.csv_output, packet["items"])
    write_markdown(args.markdown_output, packet, item_limit=args.markdown_item_limit)
    print(
        json.dumps(
            {
                "json_output": str(args.json_output),
                "csv_output": str(args.csv_output),
                "markdown_output": str(args.markdown_output),
                "exported_item_count": packet["export_summary"]["exported_item_count"],
                "classification_counts": packet["export_summary"]["classification_counts"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
