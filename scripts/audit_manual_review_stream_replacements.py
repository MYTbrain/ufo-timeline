"""Audit manual-review stream replacement rows for hidden merge conflicts.

The stream apply writer intentionally keeps one representative event body and
adds merged provenance. This report-only audit compares each replacement row
against the source component rows so a candidate sidecar cannot be promoted
without seeing date, time, location, coordinate, classification, and body
variance risks.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable


DEFAULT_APPLY_REPORT = Path("data/reports/manual_review_ai_after_time_norm_stream_apply_report.json")
DEFAULT_SOURCE_EVENTS = Path("data/canonical_time_norm_recommended_plus_shorthand_plus_likely_plus_single_exact_context/deduped_events.jsonl")
DEFAULT_CANDIDATE_EVENTS = Path("data/canonical_time_norm_plus_manual_review_ai_preview/deduped_events.jsonl")
DEFAULT_OUTPUT = Path("data/reports/manual_review_ai_after_time_norm_replacement_audit.json")
DEFAULT_CSV_OUTPUT = Path("data/reports/manual_review_ai_after_time_norm_replacement_audit.csv")

AUDIT_POLICY = "manual_review_stream_replacement_conflict_audit_v1"
APPLY_POLICY = "manual_review_effects_stream_preview_v1"
EARTH_RADIUS_KM = 6371.0088

TEXT_FIELDS = (
    "date_iso",
    "sort_date_iso",
    "end_date_iso",
    "date_precision",
    "time_raw",
    "location_raw",
    "city",
    "state_province",
    "country",
    "coordinate_source",
    "location_precision",
    "shape_normalized",
    "type_normalized",
    "source_file",
    "source_native_id",
)


def audit_manual_review_stream_replacements(
    *,
    apply_report: dict[str, Any],
    source_events_path: Path,
    candidate_events_path: Path,
    csv_output_path: Path | None = None,
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    if apply_report.get("apply_policy") != APPLY_POLICY:
        errors.append({"error": "unexpected_apply_policy", "actual": apply_report.get("apply_policy")})
    if apply_report.get("valid") is not True:
        errors.append({"error": "apply_report_not_valid"})
    if apply_report.get("canonical_outputs_mutated") is not False:
        errors.append({"error": "unsafe_apply_report_flag", "flag": "canonical_outputs_mutated"})

    replacement_ids = set(string_list(apply_report.get("replacement_event_ids")))
    candidate_replacements = scan_candidate_replacements(candidate_events_path, replacement_ids)
    missing_candidate_replacements = sorted(replacement_ids - set(candidate_replacements))
    if missing_candidate_replacements:
        errors.append(
            {"error": "missing_candidate_replacement_rows", "event_ids": missing_candidate_replacements[:50]}
        )

    required_source_ids = {
        event_id
        for replacement in candidate_replacements.values()
        for event_id in string_list(replacement.get("manual_review_preview", {}).get("merged_canonical_event_ids"))
    }
    source_rows = scan_source_component_rows(source_events_path, required_source_ids)
    missing_source_rows = sorted(required_source_ids - set(source_rows))
    if missing_source_rows:
        errors.append({"error": "missing_source_component_rows", "event_ids": missing_source_rows[:50]})

    component_audits: list[dict[str, Any]] = []
    csv_rows: list[dict[str, Any]] = []
    for replacement_id in sorted(candidate_replacements):
        candidate = candidate_replacements[replacement_id]
        component_ids = string_list(candidate.get("manual_review_preview", {}).get("merged_canonical_event_ids"))
        component_rows = [source_rows[event_id] for event_id in component_ids if event_id in source_rows]
        audit = audit_component(
            replacement_id=replacement_id,
            component_ids=component_ids,
            candidate=candidate,
            component_rows=component_rows,
        )
        component_audits.append(audit)
        csv_rows.append(flatten_component_audit(audit))

    risk_counts: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
    flag_counts: dict[str, int] = {}
    for audit in component_audits:
        risk_counts[audit["risk_level"]] = risk_counts.get(audit["risk_level"], 0) + 1
        for flag in audit["risk_flags"]:
            flag_counts[flag] = flag_counts.get(flag, 0) + 1

    top_risk_components = sorted(
        component_audits,
        key=lambda item: (
            risk_rank(item["risk_level"]),
            -int(item["conflict_field_count"]),
            -float(item["coordinate_span_km"] or 0),
            item["replacement_event_id"],
        ),
    )[:100]

    if csv_output_path is not None:
        write_csv(csv_output_path, csv_rows)

    return {
        "schema_version": 1,
        "audit_policy": AUDIT_POLICY,
        "canonical_outputs_mutated": False,
        "source_canonical_outputs_mutated": False,
        "ready_for_runtime_promotion": False,
        "human_review_required_before_promotion": True,
        "inputs": {
            "apply_report_policy": apply_report.get("apply_policy"),
            "source_events": str(source_events_path),
            "candidate_events": str(candidate_events_path),
        },
        "outputs": {
            "csv": str(csv_output_path) if csv_output_path else None,
        },
        "replacement_rows_expected": len(replacement_ids),
        "replacement_rows_audited": len(component_audits),
        "source_component_ids_expected": len(required_source_ids),
        "source_component_rows_found": len(source_rows),
        "risk_counts": risk_counts,
        "flag_counts": dict(sorted(flag_counts.items())),
        "high_risk_component_count": risk_counts.get("high", 0),
        "medium_risk_component_count": risk_counts.get("medium", 0),
        "low_risk_component_count": risk_counts.get("low", 0),
        "top_risk_components": top_risk_components,
        "valid": not errors,
        "validation_error_count": len(errors),
        "validation_errors": errors,
        "audit_notes": [
            "This is a report-only audit; it does not mutate canonical or candidate corpora.",
            "Replacement rows preserve one representative event body, so conflicts here must be reviewed before promotion.",
            "High/medium risk is not a script failure; it is promotion-blocking evidence for human review.",
        ],
    }


def scan_candidate_replacements(path: Path, replacement_ids: set[str]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    if not replacement_ids:
        return rows
    for event in iter_jsonl(path):
        event_id = event_id_for(event)
        if event_id in replacement_ids:
            rows[event_id] = event
            if len(rows) == len(replacement_ids):
                break
    return rows


def scan_source_component_rows(path: Path, required_ids: set[str]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    if not required_ids:
        return rows
    for event in iter_jsonl(path):
        event_id = event_id_for(event)
        if event_id in required_ids:
            rows[event_id] = event
            if len(rows) == len(required_ids):
                break
    return rows


def audit_component(
    *,
    replacement_id: str,
    component_ids: list[str],
    candidate: dict[str, Any],
    component_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    field_values = {field: distinct_values(component_rows, field) for field in TEXT_FIELDS}
    description_variants = distinct_text_hashes(component_rows, "description")
    summary_variants = distinct_text_hashes(component_rows, "summary")
    coordinate_summary = summarize_coordinates(component_rows)

    risk_flags: list[str] = []
    if len(field_values["date_iso"]) > 1:
        risk_flags.append("date_iso_conflict")
    if len(field_values["sort_date_iso"]) > 1:
        risk_flags.append("sort_date_iso_conflict")
    if len(field_values["time_raw"]) > 1:
        risk_flags.append("time_raw_conflict")
    if len(field_values["country"]) > 1:
        risk_flags.append("country_conflict")
    if len(field_values["state_province"]) > 1:
        risk_flags.append("state_province_conflict")
    if len(field_values["location_raw"]) > 1:
        risk_flags.append("location_text_conflict")
    if coordinate_summary["coordinate_span_km"] > 50:
        risk_flags.append("coordinate_span_gt_50km")
    elif coordinate_summary["coordinate_span_km"] > 5:
        risk_flags.append("coordinate_span_gt_5km")
    if len(field_values["shape_normalized"]) > 1:
        risk_flags.append("shape_conflict")
    if len(field_values["type_normalized"]) > 1:
        risk_flags.append("type_conflict")
    if len(description_variants) > 1:
        risk_flags.append("description_text_conflict")
    if len(summary_variants) > 1:
        risk_flags.append("summary_text_conflict")
    if same_source_multiple_native_ids(component_rows):
        risk_flags.append("same_source_multiple_native_ids")

    risk_level = classify_risk(risk_flags)
    conflict_fields = [
        field
        for field, values in field_values.items()
        if len(values) > 1
    ]
    if len(description_variants) > 1:
        conflict_fields.append("description")
    if len(summary_variants) > 1:
        conflict_fields.append("summary")
    if coordinate_summary["coordinate_span_km"] > 5:
        conflict_fields.append("lat_lon")

    return {
        "replacement_event_id": replacement_id,
        "component_event_ids": component_ids,
        "component_event_count": len(component_ids),
        "source_component_rows_found": len(component_rows),
        "canonical_input_id_count": len(string_list(candidate.get("canonical_input_ids"))),
        "risk_level": risk_level,
        "risk_flags": risk_flags,
        "conflict_field_count": len(set(conflict_fields)),
        "conflict_fields": sorted(set(conflict_fields)),
        "coordinate_span_km": round(coordinate_summary["coordinate_span_km"], 3),
        "coordinate_count": coordinate_summary["coordinate_count"],
        "field_values": {
            "date_iso": field_values["date_iso"],
            "time_raw": field_values["time_raw"],
            "location_raw": field_values["location_raw"][:10],
            "city": field_values["city"],
            "state_province": field_values["state_province"],
            "country": field_values["country"],
            "shape_normalized": field_values["shape_normalized"],
            "type_normalized": field_values["type_normalized"],
            "source_file": field_values["source_file"],
            "source_native_id": field_values["source_native_id"][:10],
        },
        "body_variance": {
            "description_variant_count": len(description_variants),
            "description_hashes": description_variants[:10],
            "summary_variant_count": len(summary_variants),
            "summary_hashes": summary_variants[:10],
        },
    }


def classify_risk(flags: list[str]) -> str:
    high_flags = {"date_iso_conflict", "sort_date_iso_conflict", "country_conflict", "coordinate_span_gt_50km"}
    medium_flags = {
        "time_raw_conflict",
        "state_province_conflict",
        "coordinate_span_gt_5km",
        "location_text_conflict",
        "shape_conflict",
        "type_conflict",
        "description_text_conflict",
        "summary_text_conflict",
        "same_source_multiple_native_ids",
    }
    if any(flag in high_flags for flag in flags):
        return "high"
    if any(flag in medium_flags for flag in flags):
        return "medium"
    return "low"


def flatten_component_audit(audit: dict[str, Any]) -> dict[str, Any]:
    values = audit["field_values"]
    return {
        "replacement_event_id": audit["replacement_event_id"],
        "risk_level": audit["risk_level"],
        "risk_flags": "|".join(audit["risk_flags"]),
        "conflict_field_count": audit["conflict_field_count"],
        "component_event_count": audit["component_event_count"],
        "canonical_input_id_count": audit["canonical_input_id_count"],
        "coordinate_span_km": audit["coordinate_span_km"],
        "date_iso_values": "|".join(values["date_iso"]),
        "time_raw_values": "|".join(values["time_raw"]),
        "location_raw_values": "|".join(values["location_raw"]),
        "country_values": "|".join(values["country"]),
        "shape_values": "|".join(values["shape_normalized"]),
        "type_values": "|".join(values["type_normalized"]),
        "source_file_values": "|".join(values["source_file"]),
        "description_variant_count": audit["body_variance"]["description_variant_count"],
        "summary_variant_count": audit["body_variance"]["summary_variant_count"],
        "component_event_ids": "|".join(audit["component_event_ids"]),
    }


def risk_rank(value: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(value, 3)


def distinct_values(rows: list[dict[str, Any]], field: str) -> list[str]:
    seen: set[str] = set()
    values: list[str] = []
    for row in rows:
        value = clean_text(row.get(field))
        if value and value not in seen:
            values.append(value)
            seen.add(value)
    return values


def distinct_text_hashes(rows: list[dict[str, Any]], field: str) -> list[str]:
    seen: set[str] = set()
    values: list[str] = []
    for row in rows:
        text = clean_body_text(row.get(field))
        if not text:
            continue
        digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
        if digest not in seen:
            seen.add(digest)
            values.append(digest)
    return values


def summarize_coordinates(rows: list[dict[str, Any]]) -> dict[str, Any]:
    coords: list[tuple[float, float]] = []
    for row in rows:
        lat = parse_float(row.get("lat"))
        lon = parse_float(row.get("lon"))
        if lat is None or lon is None:
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        coords.append((lat, lon))
    max_distance = 0.0
    for index, left in enumerate(coords):
        for right in coords[index + 1 :]:
            max_distance = max(max_distance, haversine_km(left, right))
    return {"coordinate_count": len(coords), "coordinate_span_km": max_distance}


def same_source_multiple_native_ids(rows: list[dict[str, Any]]) -> bool:
    by_source: dict[str, set[str]] = {}
    for row in rows:
        source = clean_text(row.get("source_file")) or clean_text(row.get("source_name"))
        native_id = clean_text(row.get("source_native_id"))
        if not source or not native_id:
            continue
        by_source.setdefault(source, set()).add(native_id)
    return any(len(native_ids) > 1 for native_ids in by_source.values())


def haversine_km(left: tuple[float, float], right: tuple[float, float]) -> float:
    lat1, lon1 = left
    lat2, lon2 = right
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def parse_float(value: Any) -> float | None:
    try:
        if value is None or clean_text(value) == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def event_id_for(event: dict[str, Any]) -> str:
    return clean_text(event.get("canonical_event_id")) or clean_text(event.get("event_id"))


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


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0]) if rows else [
        "replacement_event_id",
        "risk_level",
        "risk_flags",
        "conflict_field_count",
        "component_event_count",
        "canonical_input_id_count",
        "coordinate_span_km",
        "date_iso_values",
        "time_raw_values",
        "location_raw_values",
        "country_values",
        "shape_values",
        "type_values",
        "source_file_values",
        "description_variant_count",
        "summary_variant_count",
        "component_event_ids",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def clean_body_text(value: Any) -> str:
    return clean_text(value).lower()


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply-report", type=Path, default=DEFAULT_APPLY_REPORT)
    parser.add_argument("--source-events", type=Path, default=DEFAULT_SOURCE_EVENTS)
    parser.add_argument("--candidate-events", type=Path, default=DEFAULT_CANDIDATE_EVENTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = audit_manual_review_stream_replacements(
        apply_report=read_json(args.apply_report),
        source_events_path=args.source_events,
        candidate_events_path=args.candidate_events,
        csv_output_path=args.csv_output,
    )
    write_json(args.output, report)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "csv": str(args.csv_output),
                "valid": report["valid"],
                "replacement_rows_audited": report["replacement_rows_audited"],
                "risk_counts": report["risk_counts"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
