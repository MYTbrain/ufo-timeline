"""Build source-row evidence for strict cluster time-normalization candidates.

This packet is review-only. It extracts the current canonical rows behind the
44 strict time-normalization shadow-preview candidates so reviewers can inspect
raw/source time evidence before any canonical promotion.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


DEFAULT_SUBSET = Path("data/reports/entity_resolution_cluster_time_norm_shadow_override_subset.json")
DEFAULT_DEDUPED_EVENTS = Path("data/canonical_full/deduped_events.jsonl")
DEFAULT_JSON_OUTPUT = Path("data/reports/entity_resolution_cluster_time_norm_source_evidence_packet.json")
DEFAULT_CSV_OUTPUT = Path("data/reports/entity_resolution_cluster_time_norm_source_evidence_packet.csv")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/entity_resolution_cluster_time_norm_source_evidence_packet.md")

PACKET_POLICY = "entity_resolution_cluster_time_normalization_source_row_evidence_review_only"
TARGET_OVERRIDE_REASON = "strict_time_normalization_candidate"

CSV_FIELDS = (
    "review_rank",
    "review_item_id",
    "effect_id",
    "canonical_event_id",
    "canonical_input_ids",
    "source_name",
    "source_file",
    "source_row_number",
    "source_native_id",
    "source_url",
    "date_iso",
    "date_precision",
    "date_raw",
    "reported_date_raw",
    "time_raw",
    "location_raw",
    "lat",
    "lon",
    "coordinate_source",
    "type_raw",
    "type_normalized",
    "shape_raw",
    "shape_normalized",
    "summary",
    "description_excerpt",
    "provenance_count",
    "raw_source_row",
)


def build_entity_resolution_cluster_time_norm_source_evidence_packet(
    *,
    subset: dict[str, Any],
    deduped_events_path: Path,
    subset_path: Path | None = None,
) -> dict[str, Any]:
    validate_subset_safety(subset)
    effects = strict_time_normalization_effects(subset)
    requested_event_ids = sorted(
        {
            event_id
            for effect in effects
            for event_id in string_list(effect.get("merge_canonical_event_ids"))
        }
    )
    event_rows = load_requested_event_rows(deduped_events_path, requested_event_ids)
    missing_event_ids = sorted(set(requested_event_ids) - set(event_rows))
    items = [evidence_item_from_effect(effect, event_rows) for effect in effects]
    for index, item in enumerate(items, start=1):
        item["review_rank"] = index
    candidate_input_ids = sorted(
        {
            input_id
            for effect in effects
            for input_id in string_list(effect.get("canonical_input_ids"))
        }
    )
    evidence_input_ids = sorted(
        {
            input_id
            for row in event_rows.values()
            for input_id in string_list(row.get("canonical_input_ids"))
            + [
                clean_text(provenance.get("canonical_input_id"))
                for provenance in provenance_rows(row)
                if clean_text(provenance.get("canonical_input_id"))
            ]
        }
    )
    candidate_input_ids_missing_from_evidence = sorted(set(candidate_input_ids) - set(evidence_input_ids))
    return {
        "schema_version": 1,
        "packet_policy": PACKET_POLICY,
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "auto_merge_performed": False,
        "override_decisions_created": False,
        "ready_for_canonical_apply": False,
        "inputs": {
            "subset": str(subset_path) if subset_path else None,
            "deduped_events": str(deduped_events_path),
        },
        "summary": {
            "target_override_reason": TARGET_OVERRIDE_REASON,
            "candidate_effect_count": len(effects),
            "requested_canonical_event_id_count": len(requested_event_ids),
            "matched_canonical_event_id_count": len(event_rows),
            "missing_canonical_event_id_count": len(missing_event_ids),
            "candidate_input_id_count": len(candidate_input_ids),
            "evidence_input_id_count": len(evidence_input_ids),
            "candidate_input_ids_missing_from_evidence_count": len(candidate_input_ids_missing_from_evidence),
            "items_with_missing_events": sum(1 for item in items if item.get("missing_canonical_event_ids")),
            "projected_event_reduction": sum(max(0, len(string_list(effect.get("merge_canonical_event_ids"))) - 1) for effect in effects),
        },
        "missing_canonical_event_ids": missing_event_ids,
        "candidate_input_ids": candidate_input_ids,
        "evidence_input_ids": evidence_input_ids,
        "candidate_input_ids_missing_from_evidence": candidate_input_ids_missing_from_evidence,
        "items": items,
        "notes": [
            "This packet is source-row evidence for review only.",
            "It targets only effects whose shadow_preview_override_reason is strict_time_normalization_candidate.",
            "It does not create accepted ER decisions, apply merges, or mutate canonical outputs.",
        ],
    }


def strict_time_normalization_effects(subset: dict[str, Any]) -> list[dict[str, Any]]:
    effects = [
        effect
        for effect in subset.get("effects") or []
        if isinstance(effect, dict)
        and clean_text(effect.get("shadow_preview_override_reason")) == TARGET_OVERRIDE_REASON
        and clean_text(effect.get("planned_effect")) == "merge_entity_resolution_candidate"
    ]
    return sorted(effects, key=lambda effect: int(effect.get("decision_index") or 0))


def load_requested_event_rows(path: Path, requested_event_ids: list[str]) -> dict[str, dict[str, Any]]:
    requested = set(requested_event_ids)
    rows: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                continue
            event_id = clean_text(row.get("canonical_event_id"))
            if event_id in requested:
                rows[event_id] = row
                if len(rows) == len(requested):
                    break
    return rows


def evidence_item_from_effect(effect: dict[str, Any], event_rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    event_ids = string_list(effect.get("merge_canonical_event_ids"))
    rows = [evidence_row_from_event(event_rows[event_id]) for event_id in event_ids if event_id in event_rows]
    time_values = sorted({clean_text(row.get("time_raw")) for row in rows if clean_text(row.get("time_raw"))})
    candidate_input_ids = string_list(effect.get("canonical_input_ids"))
    evidence_input_ids = sorted(
        {
            input_id
            for row in rows
            for input_id in string_list(row.get("canonical_input_ids"))
            + [clean_text(row.get("canonical_input_id"))]
            if input_id
        }
    )
    return {
        "review_rank": None,
        "review_item_id": clean_text(effect.get("review_item_id")),
        "effect_id": clean_text(effect.get("effect_id")),
        "decision_index": int(effect.get("decision_index") or 0),
        "projected_event_reduction": max(0, len(event_ids) - 1),
        "shadow_preview_override_source": effect.get("shadow_preview_override_source") or {},
        "candidate_canonical_input_ids": candidate_input_ids,
        "candidate_input_ids_missing_from_evidence": sorted(set(candidate_input_ids) - set(evidence_input_ids)),
        "merge_canonical_event_ids": event_ids,
        "missing_canonical_event_ids": [event_id for event_id in event_ids if event_id not in event_rows],
        "source_summary": summarize_rows(rows),
        "conflict_summary": conflict_summary(rows),
        "reviewer_prompts": reviewer_prompts(),
        "time_values": time_values,
        "evidence_rows": rows,
    }


def evidence_row_from_event(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "canonical_event_id": clean_text(row.get("canonical_event_id")),
        "canonical_input_id": clean_text(row.get("canonical_input_id")),
        "canonical_input_ids": string_list(row.get("canonical_input_ids")),
        "source_name": clean_text(row.get("source_name")),
        "source_file": clean_text(row.get("source_file")),
        "source_row_number": row.get("source_row_number"),
        "source_native_id": clean_text(row.get("source_native_id")),
        "source_row_hash": clean_text(row.get("source_row_hash")),
        "source_url": clean_text(row.get("source_url")),
        "date_iso": clean_text(row.get("date_iso")),
        "date_precision": clean_text(row.get("date_precision")),
        "date_raw": clean_text(row.get("date_raw")),
        "reported_date_raw": clean_text(row.get("reported_date_raw")),
        "time_raw": clean_text(row.get("time_raw")),
        "location_raw": clean_text(row.get("location_raw")),
        "location_normalized": clean_text(row.get("location_normalized")),
        "lat": row.get("lat"),
        "lon": row.get("lon"),
        "coordinate_source": clean_text(row.get("coordinate_source")),
        "coordinate_precision": clean_text(row.get("coordinate_precision")),
        "type_raw": clean_text(row.get("type_raw")),
        "type_normalized": clean_text(row.get("type_normalized")),
        "shape_raw": clean_text(row.get("shape_raw")),
        "shape_normalized": clean_text(row.get("shape_normalized")),
        "duration_raw": clean_text(row.get("duration_raw")),
        "summary": clean_text(row.get("summary")),
        "description_excerpt": excerpt(row.get("description"), max_chars=280),
        "source_provenance": provenance_rows(row),
        "raw_fields": source_raw_fields(row),
        "raw_source_row": row.get("raw_source_row") if isinstance(row.get("raw_source_row"), dict) else {},
    }


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "canonical_event_count": len(rows),
        "canonical_input_ids": sorted(
            {
                input_id
                for row in rows
                for input_id in string_list(row.get("canonical_input_ids"))
                + [clean_text(row.get("canonical_input_id"))]
                if input_id
            }
        ),
        "source_names": unique(row.get("source_name") for row in rows),
        "source_files": unique(row.get("source_file") for row in rows),
        "source_urls": unique(row.get("source_url") for row in rows),
        "source_native_ids": unique(row.get("source_native_id") for row in rows),
        "date_values": unique(row.get("date_iso") for row in rows),
        "date_precision_values": unique(row.get("date_precision") for row in rows),
        "time_values": unique(row.get("time_raw") for row in rows),
        "location_values": unique(row.get("location_raw") for row in rows),
        "type_values": unique(row.get("type_normalized") for row in rows),
        "raw_type_values": unique(row.get("type_raw") for row in rows),
        "shape_values": unique(row.get("shape_normalized") for row in rows),
        "raw_shape_values": unique(row.get("shape_raw") for row in rows),
        "coordinate_values": unique(
            f"{row.get('lat')},{row.get('lon')}"
            for row in rows
            if row.get("lat") is not None and row.get("lon") is not None
        ),
        "provenance_row_count": sum(len(row.get("source_provenance") or []) for row in rows),
        "rows_with_raw_source_row": sum(1 for row in rows if row.get("raw_source_row")),
    }


def conflict_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize value disagreement without deciding whether a merge is valid."""

    value_groups = {
        "time": unique(row.get("time_raw") for row in rows),
        "date": unique(row.get("date_iso") for row in rows),
        "location": unique(row.get("location_raw") for row in rows),
        "coordinate": unique(
            f"{row.get('lat')},{row.get('lon')}"
            for row in rows
            if row.get("lat") is not None and row.get("lon") is not None
        ),
        "type": unique(row.get("type_normalized") for row in rows),
        "shape": unique(row.get("shape_normalized") for row in rows),
        "source_native_id": unique(row.get("source_native_id") for row in rows),
    }
    return {
        "value_groups": value_groups,
        "conflict_flags": {name: len(values) > 1 for name, values in value_groups.items()},
        "blocking_status": "review_required_not_auto_approved",
    }


def reviewer_prompts() -> list[str]:
    return [
        "Are these source rows the same sighting/event, or separate reports in the same wave?",
        "Is the only meaningful disagreement rounded/nearby time notation?",
        "Do location, coordinate, source-native ID, and date evidence stay consistent?",
        "Is more source evidence needed before accepting a canonical merge?",
    ]


def provenance_rows(row: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in row.get("source_provenance") or [] if isinstance(item, dict)]


def source_raw_fields(row: dict[str, Any]) -> dict[str, str]:
    raw = row.get("raw_source_row") if isinstance(row.get("raw_source_row"), dict) else {}
    wanted_tokens = (
        "date",
        "time",
        "hour",
        "location",
        "city",
        "state",
        "country",
        "lat",
        "lon",
        "source",
        "record",
        "id",
    )
    fields: dict[str, str] = {}
    for key, value in raw.items():
        key_text = clean_text(key)
        if not key_text:
            continue
        key_lower = key_text.lower()
        if any(token in key_lower for token in wanted_tokens):
            fields[key_text] = clean_text(value)
    return fields


def validate_subset_safety(subset: dict[str, Any]) -> None:
    errors: list[str] = []
    if subset.get("subset_policy") != "entity_resolution_cluster_time_normalization_shadow_preview_subset_v2":
        errors.append("subset_policy must be entity_resolution_cluster_time_normalization_shadow_preview_subset_v2")
    for flag in (
        "canonical_outputs_mutated",
        "decisions_created",
        "decision_outputs_created",
        "auto_merge_performed",
        "override_decisions_created",
        "ready_for_canonical_apply",
    ):
        if subset.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError("time-normalization subset is unsafe for source evidence packet: " + "; ".join(errors))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


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


def csv_row(item: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    return {
        "review_rank": item.get("review_rank"),
        "review_item_id": item.get("review_item_id"),
        "effect_id": item.get("effect_id"),
        "canonical_event_id": row.get("canonical_event_id"),
        "canonical_input_ids": "; ".join(string_list(row.get("canonical_input_ids"))),
        "source_name": row.get("source_name"),
        "source_file": row.get("source_file"),
        "source_row_number": row.get("source_row_number"),
        "source_native_id": row.get("source_native_id"),
        "source_url": row.get("source_url"),
        "date_iso": row.get("date_iso"),
        "date_precision": row.get("date_precision"),
        "date_raw": row.get("date_raw"),
        "reported_date_raw": row.get("reported_date_raw"),
        "time_raw": row.get("time_raw"),
        "location_raw": row.get("location_raw"),
        "lat": row.get("lat"),
        "lon": row.get("lon"),
        "coordinate_source": row.get("coordinate_source"),
        "type_raw": row.get("type_raw"),
        "type_normalized": row.get("type_normalized"),
        "shape_raw": row.get("shape_raw"),
        "shape_normalized": row.get("shape_normalized"),
        "summary": row.get("summary"),
        "description_excerpt": row.get("description_excerpt"),
        "provenance_count": len(row.get("source_provenance") or []),
        "raw_source_row": json.dumps(row.get("raw_source_row") or {}, ensure_ascii=False, sort_keys=True),
    }


def write_markdown(path: Path, packet: dict[str, Any], *, item_limit: int, row_limit_per_item: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = packet.get("summary") if isinstance(packet.get("summary"), dict) else {}
    lines = [
        "# Cluster Time-Normalization Source Evidence Packet",
        "",
        "This packet is review-only. It shows source rows for strict time-normalization candidates before canonical promotion.",
        "",
        "## Summary",
        "",
        f"- Candidate effects: `{summary.get('candidate_effect_count', 0)}`",
        f"- Requested canonical events: `{summary.get('requested_canonical_event_id_count', 0)}`",
        f"- Matched canonical events: `{summary.get('matched_canonical_event_id_count', 0)}`",
        f"- Missing canonical events: `{summary.get('missing_canonical_event_id_count', 0)}`",
        f"- Candidate input IDs missing from evidence: `{summary.get('candidate_input_ids_missing_from_evidence_count', 0)}`",
        f"- Projected event reduction: `{summary.get('projected_event_reduction', 0)}`",
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
    source = item.get("shadow_preview_override_source") if isinstance(item.get("shadow_preview_override_source"), dict) else {}
    summary = item.get("source_summary") if isinstance(item.get("source_summary"), dict) else {}
    conflicts = item.get("conflict_summary") if isinstance(item.get("conflict_summary"), dict) else {}
    flags = conflicts.get("conflict_flags") if isinstance(conflicts.get("conflict_flags"), dict) else {}
    lines = [
        f"### #{item.get('review_rank')} {item.get('review_item_id')}",
        "",
        f"- Effect ID: `{item.get('effect_id')}`",
        f"- Projected reduction: `{item.get('projected_event_reduction')}`",
        f"- Time pattern: `{source.get('time_pattern_classification')}` risk `{source.get('review_risk_tier')}`",
        f"- Parsed minutes: {', '.join(str(value) for value in source.get('parsed_minutes') or []) or 'none'}",
        f"- Time tokens: {', '.join(string_list(source.get('time_tokens'))) or 'none'}",
        f"- Source names: {', '.join(string_list(summary.get('source_names'))) or 'none'}",
        f"- Source native IDs: {', '.join(string_list(summary.get('source_native_ids'))) or 'none'}",
        f"- Dates: {', '.join(string_list(summary.get('date_values'))) or 'none'}",
        f"- Locations: {', '.join(string_list(summary.get('location_values'))) or 'none'}",
        f"- Times: {', '.join(string_list(summary.get('time_values'))) or 'none'}",
        f"- Conflict flags: {', '.join(name for name, active in flags.items() if active) or 'none'}",
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
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [text for item in value if (text := clean_text(item))]
    text = clean_text(value)
    return [text] if text else []


def unique(values: Any) -> list[str]:
    return sorted({text for value in values if (text := clean_text(value))})


def excerpt(value: Any, *, max_chars: int) -> str:
    text = clean_text(value)
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 3)].rstrip() + "..."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subset", type=Path, default=DEFAULT_SUBSET)
    parser.add_argument("--deduped-events", type=Path, default=DEFAULT_DEDUPED_EVENTS)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument("--markdown-item-limit", type=int, default=44)
    parser.add_argument("--markdown-row-limit-per-item", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packet = build_entity_resolution_cluster_time_norm_source_evidence_packet(
        subset=read_json(args.subset),
        deduped_events_path=args.deduped_events,
        subset_path=args.subset,
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
