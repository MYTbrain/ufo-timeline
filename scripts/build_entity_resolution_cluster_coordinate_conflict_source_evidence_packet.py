"""Build source-row evidence for low-spread coordinate-conflict clusters.

This packet targets the narrowest coordinate-conflict analysis class so that
reviewers can inspect raw/source rows before deciding whether nearby coordinate
spread is a geocode precision issue or evidence of separate events. It does not
create decisions, preview output, or canonical mutations.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from scripts.build_entity_resolution_cluster_time_norm_source_evidence_packet import (
    evidence_item_from_effect,
    load_requested_event_rows,
    write_json,
)


DEFAULT_ANALYSIS = Path("data/reports/entity_resolution_cluster_coordinate_conflict_analysis.json")
DEFAULT_DEDUPED_EVENTS = Path("data/canonical_full/deduped_events.jsonl")
DEFAULT_JSON_OUTPUT = Path("data/reports/entity_resolution_cluster_coordinate_conflict_source_evidence_packet.json")
DEFAULT_CSV_OUTPUT = Path("data/reports/entity_resolution_cluster_coordinate_conflict_source_evidence_packet.csv")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/entity_resolution_cluster_coordinate_conflict_source_evidence_packet.md")

INPUT_ANALYSIS_POLICY = "entity_resolution_cluster_coordinate_conflict_review_only"
PACKET_POLICY = "entity_resolution_cluster_coordinate_conflict_source_evidence_review_only"
TARGET_CLASSIFICATION = "coordinate_conflict_10_to_15km"

CSV_FIELDS = (
    "review_rank",
    "review_item_id",
    "effect_id",
    "coordinate_conflict_classification",
    "max_coordinate_distance_km",
    "review_risk_tier",
    "identity_consistency",
    "recommended_review_step",
    "projected_event_reduction",
    "blocking_fields",
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
    "coordinate_precision",
    "type_raw",
    "type_normalized",
    "shape_raw",
    "shape_normalized",
    "summary",
    "description_excerpt",
    "provenance_count",
    "raw_source_row",
)


def build_coordinate_conflict_source_evidence_packet(
    *,
    analysis: dict[str, Any],
    deduped_events_path: Path,
    analysis_path: Path | None = None,
    target_classification: str = TARGET_CLASSIFICATION,
) -> dict[str, Any]:
    validate_analysis_safety(analysis)
    analysis_items = coordinate_candidate_items(analysis, target_classification=target_classification)
    effects = [effect_from_analysis_item(item, index=index) for index, item in enumerate(analysis_items, start=1)]
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
        source = item.get("shadow_preview_override_source") if isinstance(item.get("shadow_preview_override_source"), dict) else {}
        item["coordinate_conflict_summary"] = {
            "coordinate_conflict_classification": clean_text(source.get("coordinate_conflict_classification")),
            "max_coordinate_distance_km": as_float(source.get("max_coordinate_distance_km")),
            "review_risk_tier": clean_text(source.get("review_risk_tier")),
            "identity_consistency": clean_text(source.get("identity_consistency")),
            "recommended_review_step": clean_text(source.get("recommended_review_step")),
            "blocking_fields": string_list(source.get("blocking_fields")),
            "time_values": string_list(source.get("time_values")),
            "type_values": string_list(source.get("type_values")),
        }
        item["reviewer_prompts"] = coordinate_reviewer_prompts()
        item["candidate_input_ids_missing_from_evidence"] = sorted(
            set(string_list(item.get("candidate_canonical_input_ids"))) - set(evidence_item_input_ids(item))
        )

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
            for input_id in raw_event_input_ids(row)
        }
    )
    missing_candidate_input_ids = sorted(set(candidate_input_ids) - set(evidence_input_ids))
    return {
        "schema_version": 1,
        "packet_policy": PACKET_POLICY,
        "input_analysis_policy": analysis.get("analysis_policy"),
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "auto_merge_performed": False,
        "override_decisions_created": False,
        "ready_for_canonical_apply": False,
        "inputs": {
            "analysis": str(analysis_path) if analysis_path else None,
            "deduped_events": str(deduped_events_path),
        },
        "summary": {
            "target_classification": target_classification,
            "source_analysis_item_count": len(analysis.get("items") or []),
            "candidate_effect_count": len(effects),
            "requested_canonical_event_id_count": len(requested_event_ids),
            "matched_canonical_event_id_count": len(event_rows),
            "missing_canonical_event_id_count": len(missing_event_ids),
            "candidate_input_id_count": len(candidate_input_ids),
            "evidence_input_id_count": len(evidence_input_ids),
            "candidate_input_ids_missing_from_evidence_count": len(missing_candidate_input_ids),
            "items_with_missing_events": sum(1 for item in items if item.get("missing_canonical_event_ids")),
            "projected_event_reduction": sum(
                max(0, len(string_list(effect.get("merge_canonical_event_ids"))) - 1) for effect in effects
            ),
        },
        "missing_canonical_event_ids": missing_event_ids,
        "candidate_input_ids": candidate_input_ids,
        "evidence_input_ids": evidence_input_ids,
        "candidate_input_ids_missing_from_evidence": missing_candidate_input_ids,
        "items": items,
        "notes": [
            "This packet is source-row evidence for review only.",
            "It targets the lowest-distance coordinate-conflict class from the coordinate-conflict analysis.",
            "Coordinate-conflict items remain high risk; this packet does not approve or apply merges.",
        ],
    }


def validate_analysis_safety(analysis: dict[str, Any]) -> None:
    errors: list[str] = []
    if analysis.get("analysis_policy") != INPUT_ANALYSIS_POLICY:
        errors.append(f"analysis_policy must be {INPUT_ANALYSIS_POLICY}")
    for flag in (
        "canonical_outputs_mutated",
        "preview_outputs_written",
        "decisions_created",
        "decision_outputs_created",
        "auto_merge_performed",
        "override_decisions_created",
        "ready_for_canonical_apply",
    ):
        if analysis.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError("coordinate-conflict analysis is unsafe for source evidence export: " + "; ".join(errors))


def coordinate_candidate_items(
    analysis: dict[str, Any],
    *,
    target_classification: str,
) -> list[dict[str, Any]]:
    items = [
        item
        for item in analysis.get("items") or []
        if isinstance(item, dict)
        and clean_text(item.get("coordinate_conflict_classification")) == target_classification
    ]
    return sorted(
        items,
        key=lambda item: (
            as_float(item.get("max_coordinate_distance_km")),
            clean_text(item.get("review_item_id")),
        ),
    )


def effect_from_analysis_item(item: dict[str, Any], *, index: int) -> dict[str, Any]:
    summary = item.get("source_summary") if isinstance(item.get("source_summary"), dict) else {}
    return {
        "decision_index": index,
        "review_item_id": clean_text(item.get("review_item_id")),
        "effect_id": clean_text(item.get("effect_id")),
        "planned_effect": "merge_entity_resolution_candidate",
        "canonical_input_ids": string_list(summary.get("canonical_input_ids")),
        "merge_canonical_event_ids": string_list(summary.get("canonical_event_ids")),
        "projected_event_reduction": as_int(item.get("projected_event_reduction")),
        "shadow_preview_override_reason": clean_text(item.get("coordinate_conflict_classification")),
        "shadow_preview_override_source": {
            "analysis_policy": PACKET_POLICY,
            "coordinate_conflict_classification": clean_text(item.get("coordinate_conflict_classification")),
            "review_risk_tier": clean_text(item.get("review_risk_tier")),
            "identity_consistency": clean_text(item.get("identity_consistency")),
            "recommended_review_step": clean_text(item.get("recommended_review_step")),
            "blocking_fields": string_list(item.get("blocking_fields")),
            "max_coordinate_distance_km": as_float(item.get("max_coordinate_distance_km")),
            "time_values": string_list(item.get("time_values")),
            "type_values": string_list(item.get("type_values")),
            "source_names": string_list(summary.get("source_names")),
            "source_native_ids": string_list(summary.get("source_native_ids")),
            "date_values": string_list(summary.get("date_values")),
            "location_values": string_list(summary.get("location_values")),
            "canonical_event_count": as_int(summary.get("canonical_event_count")),
        },
    }


def write_markdown(path: Path, packet: dict[str, Any], *, item_limit: int, row_limit_per_item: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = packet.get("summary") if isinstance(packet.get("summary"), dict) else {}
    lines = [
        "# Cluster Coordinate-Conflict Source Evidence Packet",
        "",
        "This packet is review-only. It shows source rows for low-spread coordinate-conflict candidates before any canonical decision.",
        "",
        "## Summary",
        "",
        f"- Target classification: `{summary.get('target_classification')}`",
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
    source = item.get("shadow_preview_override_source") if isinstance(item.get("shadow_preview_override_source"), dict) else {}
    return {
        "review_rank": item.get("review_rank"),
        "review_item_id": item.get("review_item_id"),
        "effect_id": item.get("effect_id"),
        "coordinate_conflict_classification": source.get("coordinate_conflict_classification"),
        "max_coordinate_distance_km": source.get("max_coordinate_distance_km"),
        "review_risk_tier": source.get("review_risk_tier"),
        "identity_consistency": source.get("identity_consistency"),
        "recommended_review_step": source.get("recommended_review_step"),
        "projected_event_reduction": item.get("projected_event_reduction"),
        "blocking_fields": "; ".join(string_list(source.get("blocking_fields"))),
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
        "coordinate_precision": row.get("coordinate_precision"),
        "type_raw": row.get("type_raw"),
        "type_normalized": row.get("type_normalized"),
        "shape_raw": row.get("shape_raw"),
        "shape_normalized": row.get("shape_normalized"),
        "summary": row.get("summary"),
        "description_excerpt": row.get("description_excerpt"),
        "provenance_count": len(row.get("source_provenance") or []),
        "raw_source_row": json.dumps(row.get("raw_source_row") or {}, ensure_ascii=False, sort_keys=True),
    }


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
        f"- Coordinate classification: `{source.get('coordinate_conflict_classification')}` risk `{source.get('review_risk_tier')}`",
        f"- Max coordinate distance km: `{source.get('max_coordinate_distance_km')}`",
        f"- Identity: `{source.get('identity_consistency')}`",
        f"- Source names: {', '.join(string_list(summary.get('source_names'))) or 'none'}",
        f"- Source native IDs: {', '.join(string_list(summary.get('source_native_ids'))) or 'none'}",
        f"- Dates: {', '.join(string_list(summary.get('date_values'))) or 'none'}",
        f"- Locations: {', '.join(string_list(summary.get('location_values'))) or 'none'}",
        f"- Coordinate values: {', '.join(string_list(summary.get('coordinate_values'))) or 'none'}",
        f"- Time values: {', '.join(string_list(source.get('time_values'))) or 'none'}",
        f"- Type values: {', '.join(string_list(source.get('type_values'))) or 'none'}",
        f"- Conflict flags: {', '.join(name for name, active in flags.items() if active) or 'none'}",
        f"- Recommended review step: {source.get('recommended_review_step') or 'none'}",
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
                f"    - Coordinates: `{row.get('lat')}`, `{row.get('lon')}` source `{row.get('coordinate_source')}` precision `{row.get('coordinate_precision')}`",
                f"    - Type/shape: `{row.get('type_normalized')}` / `{row.get('shape_normalized')}`",
                f"    - Summary: {row.get('summary') or 'none'}",
            ]
        )
    if len(rows) > row_limit_per_item:
        lines.append(f"  - _Rows limited to {row_limit_per_item} of {len(rows)}._")
    lines.append("")
    return lines


def coordinate_reviewer_prompts() -> list[str]:
    return [
        "Do the source rows describe one event with nearby coordinate precision spread, or separate nearby sightings?",
        "Do raw location text, source-native IDs, date, time, and type evidence support one canonical event?",
        "Are coordinate differences explained by geocode precision, facility/area-level wording, or source transcription?",
        "Is more source evidence needed before accepting a canonical merge?",
    ]


def raw_event_input_ids(row: dict[str, Any]) -> list[str]:
    values = string_list(row.get("canonical_input_ids"))
    direct = clean_text(row.get("canonical_input_id"))
    if direct:
        values.append(direct)
    for provenance in row.get("source_provenance") or []:
        if isinstance(provenance, dict):
            provenance_input_id = clean_text(provenance.get("canonical_input_id"))
            if provenance_input_id:
                values.append(provenance_input_id)
    return sorted(set(values))


def evidence_item_input_ids(item: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for row in item.get("evidence_rows") or []:
        if not isinstance(row, dict):
            continue
        values.extend(string_list(row.get("canonical_input_ids")))
        direct = clean_text(row.get("canonical_input_id"))
        if direct:
            values.append(direct)
        for provenance in row.get("source_provenance") or []:
            if isinstance(provenance, dict):
                provenance_input_id = clean_text(provenance.get("canonical_input_id"))
                if provenance_input_id:
                    values.append(provenance_input_id)
    return sorted(set(values))


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


def as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", type=Path, default=DEFAULT_ANALYSIS)
    parser.add_argument("--deduped-events", type=Path, default=DEFAULT_DEDUPED_EVENTS)
    parser.add_argument("--target-classification", default=TARGET_CLASSIFICATION)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument("--markdown-item-limit", type=int, default=80)
    parser.add_argument("--markdown-row-limit-per-item", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packet = build_coordinate_conflict_source_evidence_packet(
        analysis=read_json(args.analysis),
        deduped_events_path=args.deduped_events,
        analysis_path=args.analysis,
        target_classification=args.target_classification,
    )
    packet["outputs"] = {
        "json": str(args.json_output),
        "csv": str(args.csv_output),
        "markdown": str(args.markdown_output),
    }
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
                "packet_policy": packet["packet_policy"],
                "summary": packet["summary"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
