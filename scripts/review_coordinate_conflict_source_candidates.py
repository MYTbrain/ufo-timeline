"""Review low-spread coordinate-conflict source evidence.

This consumes the coordinate-conflict source evidence packet and produces
recommendation-only review output. It does not create decisions, preview output,
accepted records, or canonical mutations.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_PACKET = Path("data/reports/entity_resolution_cluster_coordinate_conflict_source_evidence_packet.json")
DEFAULT_JSON_OUTPUT = Path("data/reports/entity_resolution_cluster_coordinate_conflict_source_review.json")
DEFAULT_CSV_OUTPUT = Path("data/reports/entity_resolution_cluster_coordinate_conflict_source_review.csv")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/entity_resolution_cluster_coordinate_conflict_source_review.md")

INPUT_PACKET_POLICY = "entity_resolution_cluster_coordinate_conflict_source_evidence_review_only"
REVIEW_POLICY = "entity_resolution_coordinate_conflict_source_review_only"
SOURCE_REVIEW_COORDINATE_PRECISION_CANDIDATE = "source_review_coordinate_precision_candidate"
NEEDS_MORE_EVIDENCE = "needs_more_evidence"

FUZZY_WINDOWS: dict[str, tuple[tuple[int, int], ...]] = {
    "before_dawn": ((210, 300),),
    "dawn": ((300, 360),),
    "sunrise": ((330, 390),),
    "early_morning": ((360, 480),),
    "morning": ((480, 660),),
    "late_morning": ((630, 720),),
    "noon": ((705, 735),),
    "day": ((360, 1080),),
    "daytime": ((360, 1080),),
    "early_afternoon": ((720, 870),),
    "afternoon": ((780, 1020),),
    "late_afternoon": ((960, 1080),),
    "sunset": ((1050, 1110),),
    "dusk": ((1020, 1260),),
    "even": ((1020, 1380),),
    "evening": ((1020, 1380),),
    "late_evening": ((1230, 1350),),
    "night": ((0, 330), (1200, 1440)),
    "midnight": ((0, 15), (1425, 1440)),
    "after_midnight": ((0, 180),),
}

CSV_FIELDS = (
    "review_rank",
    "review_item_id",
    "effect_id",
    "review_recommendation",
    "confidence",
    "projected_event_reduction",
    "max_coordinate_distance_km",
    "active_conflicts",
    "time_values",
    "time_compatibility",
    "failed_conditions",
    "review_reason_codes",
    "source_names",
    "source_native_ids",
    "dates",
    "locations",
    "coordinate_values",
    "type_values",
)


def build_coordinate_conflict_source_review(packet: dict[str, Any]) -> dict[str, Any]:
    validate_packet_safety(packet)
    items = [item for item in packet.get("items") or [] if isinstance(item, dict)]
    reviewed = [review_item(item) for item in items]
    projected_by_recommendation: dict[str, int] = {}
    for item in reviewed:
        recommendation = clean_text(item.get("review_recommendation")) or "unknown"
        projected_by_recommendation[recommendation] = projected_by_recommendation.get(recommendation, 0) + as_int(
            item.get("projected_event_reduction")
        )
    return {
        "schema_version": 1,
        "review_policy": REVIEW_POLICY,
        "input_packet_policy": packet.get("packet_policy"),
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "validated_decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "summary": {
            "input_item_count": len(items),
            "reviewed_item_count": len(reviewed),
            "review_recommendation_counts": count_by(reviewed, "review_recommendation"),
            "confidence_counts": count_by(reviewed, "confidence"),
            "projected_event_reduction_by_review_recommendation": dict(sorted(projected_by_recommendation.items())),
            "failed_condition_counts": count_failed_conditions(reviewed),
        },
        "items": reviewed,
        "notes": [
            "This report is source-review guidance only and does not accept or apply merges.",
            "source_review_coordinate_precision_candidate requires low-spread coordinates, single-source/date/location identity, and compatible time evidence.",
            "Rows with incompatible time, mixed identity, missing evidence, or non-time/coordinate conflicts remain needs_more_evidence.",
        ],
    }


def validate_packet_safety(packet: dict[str, Any]) -> None:
    errors: list[str] = []
    if packet.get("packet_policy") != INPUT_PACKET_POLICY:
        errors.append(f"packet_policy must be {INPUT_PACKET_POLICY}")
    for flag in (
        "canonical_outputs_mutated",
        "preview_outputs_written",
        "decisions_created",
        "decision_outputs_created",
        "auto_merge_performed",
        "override_decisions_created",
        "ready_for_canonical_apply",
    ):
        if packet.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError("coordinate conflict source packet is unsafe for review: " + "; ".join(errors))


def review_item(item: dict[str, Any]) -> dict[str, Any]:
    source = item.get("shadow_preview_override_source") if isinstance(item.get("shadow_preview_override_source"), dict) else {}
    source_summary = item.get("source_summary") if isinstance(item.get("source_summary"), dict) else {}
    conflict_summary = item.get("conflict_summary") if isinstance(item.get("conflict_summary"), dict) else {}
    conflict_flags = conflict_summary.get("conflict_flags") if isinstance(conflict_summary.get("conflict_flags"), dict) else {}
    active_conflicts = sorted(name for name, active in conflict_flags.items() if active)
    time_values = string_list(source_summary.get("time_values")) or string_list(source.get("time_values"))
    time_compatibility = classify_time_compatibility(time_values)
    max_distance = as_float(source.get("max_coordinate_distance_km"))
    summary_texts = normalized_summary_texts(item)
    conditions = {
        "classification_is_low_spread_coordinate_conflict": clean_text(source.get("coordinate_conflict_classification")) == "coordinate_conflict_10_to_15km",
        "coordinate_distance_positive_and_at_most_15km": 0 < max_distance <= 15,
        "identity_consistency_single_source_id_date_location": clean_text(source.get("identity_consistency")) == "single_source_id_date_location",
        "coordinate_conflict_present": "coordinate" in active_conflicts,
        "only_coordinate_or_time_conflicts": set(active_conflicts).issubset({"coordinate", "time"}),
        "single_source_name": len(string_list(source_summary.get("source_names"))) == 1,
        "single_source_native_id": len(string_list(source_summary.get("source_native_ids"))) == 1,
        "single_date": len(string_list(source_summary.get("date_values"))) == 1,
        "single_location": len(string_list(source_summary.get("location_values"))) == 1,
        "single_type": len(string_list(source_summary.get("type_values"))) <= 1,
        "time_values_compatible": time_compatibility["compatible"] is True,
        "identical_or_missing_summary_text": len(summary_texts) <= 1,
        "no_missing_candidate_input_ids": not item.get("candidate_input_ids_missing_from_evidence"),
        "no_missing_canonical_event_ids": not item.get("missing_canonical_event_ids"),
        "positive_projected_reduction": as_int(item.get("projected_event_reduction")) > 0,
    }
    failed_conditions = [key for key, passed in conditions.items() if not passed]
    candidate = not failed_conditions
    recommendation = SOURCE_REVIEW_COORDINATE_PRECISION_CANDIDATE if candidate else NEEDS_MORE_EVIDENCE
    confidence = "medium" if candidate else "low"
    reason_codes = (
        [
            "low_spread_coordinate_conflict",
            "compatible_time_evidence",
            "single_source_native_date_location",
            "review_only_not_decision",
        ]
        if candidate
        else ["needs_more_evidence"] + failed_conditions
    )
    return {
        "review_rank": item.get("review_rank"),
        "review_item_id": clean_text(item.get("review_item_id")),
        "cluster_review_id": clean_text(item.get("review_item_id")),
        "effect_id": clean_text(item.get("effect_id")),
        "review_recommendation": recommendation,
        "confidence": confidence,
        "projected_event_reduction": as_int(item.get("projected_event_reduction")),
        "coordinate_conflict_classification": clean_text(source.get("coordinate_conflict_classification")),
        "max_coordinate_distance_km": max_distance,
        "active_conflicts": active_conflicts,
        "time_values": time_values,
        "time_compatibility": time_compatibility,
        "failed_conditions": failed_conditions,
        "review_reason_codes": reason_codes,
        "source_names": string_list(source_summary.get("source_names")),
        "source_native_ids": string_list(source_summary.get("source_native_ids")),
        "dates": string_list(source_summary.get("date_values")),
        "locations": string_list(source_summary.get("location_values")),
        "coordinate_values": string_list(source_summary.get("coordinate_values")),
        "type_values": string_list(source_summary.get("type_values")),
        "shape_values": string_list(source_summary.get("shape_values")),
        "normalized_summary_text_count": len(summary_texts),
        "merge_canonical_event_ids": string_list(item.get("merge_canonical_event_ids")),
        "candidate_canonical_input_ids": string_list(item.get("candidate_canonical_input_ids")),
        "notes": (
            "Low-spread coordinate conflict looks like a coordinate precision/source review candidate; still requires explicit decision and apply gates."
            if candidate
            else "Deferred because one or more source-review safety conditions failed."
        ),
    }


def classify_time_compatibility(values: list[str]) -> dict[str, Any]:
    ranges_by_value = {value: parse_time_ranges(value) for value in values if clean_text(value)}
    if not ranges_by_value:
        return {"compatible": True, "basis": "no_time_values", "parsed": {}}
    if any(not ranges for ranges in ranges_by_value.values()):
        return {"compatible": False, "basis": "unparsed_time_value", "parsed": serializable_ranges(ranges_by_value)}
    all_ranges = list(ranges_by_value.values())
    if ranges_intersect_all(all_ranges):
        return {"compatible": True, "basis": "overlapping_time_ranges", "parsed": serializable_ranges(ranges_by_value)}
    exact_midpoints = [ranges[0][0] for ranges in all_ranges if len(ranges) == 1 and ranges[0][0] == ranges[0][1]]
    if len(exact_midpoints) == len(all_ranges) and max(exact_midpoints) - min(exact_midpoints) <= 30:
        return {"compatible": True, "basis": "nearby_exact_times_30m_or_less", "parsed": serializable_ranges(ranges_by_value)}
    return {"compatible": False, "basis": "non_overlapping_or_distant_time_values", "parsed": serializable_ranges(ranges_by_value)}


def parse_time_ranges(value: str) -> list[tuple[int, int]]:
    text = clean_text(value).casefold().replace(".", "")
    text = text.replace("early ", "early_").replace("late ", "late_").replace("after ", "after_")
    if text in FUZZY_WINDOWS:
        return [tuple(window) for window in FUZZY_WINDOWS[text]]
    if text == "ev":
        return [tuple(window) for window in FUZZY_WINDOWS["even"]]
    if match := re.fullmatch(r"(\d{1,2})(?::?(\d{2}))?\s*(am|pm)?", text):
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        meridiem = match.group(3)
        if minute > 59:
            return []
        if meridiem:
            if hour < 1 or hour > 12:
                return []
            if meridiem == "am":
                hour = 0 if hour == 12 else hour
            else:
                hour = 12 if hour == 12 else hour + 12
        elif len(match.group(1)) <= 2 and match.group(2) is None:
            if hour > 23:
                return []
        elif hour > 23:
            return []
        return [(hour * 60 + minute, hour * 60 + minute)]
    return []


def ranges_intersect_all(ranges_by_value: list[list[tuple[int, int]]]) -> bool:
    current = ranges_by_value[0]
    for ranges in ranges_by_value[1:]:
        current = intersect_range_sets(current, ranges)
        if not current:
            return False
    return True


def intersect_range_sets(left: list[tuple[int, int]], right: list[tuple[int, int]]) -> list[tuple[int, int]]:
    intersections: list[tuple[int, int]] = []
    for left_start, left_end in left:
        for right_start, right_end in right:
            start = max(left_start, right_start)
            end = min(left_end, right_end)
            if start <= end:
                intersections.append((start, end))
    return intersections


def serializable_ranges(values: dict[str, list[tuple[int, int]]]) -> dict[str, list[dict[str, int]]]:
    return {
        value: [{"start_minutes": start, "end_minutes": end} for start, end in ranges]
        for value, ranges in values.items()
    }


def normalized_summary_texts(item: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    for row in item.get("evidence_rows") or []:
        if not isinstance(row, dict):
            continue
        text = clean_text(row.get("summary")) or clean_text(row.get("description_excerpt"))
        if text:
            values.add(text.casefold())
    return values


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for item in payload.get("items") or []:
            if isinstance(item, dict):
                writer.writerow(csv_row(item))


def csv_row(item: dict[str, Any]) -> dict[str, Any]:
    time_compatibility = item.get("time_compatibility") if isinstance(item.get("time_compatibility"), dict) else {}
    return {
        "review_rank": item.get("review_rank"),
        "review_item_id": item.get("review_item_id"),
        "effect_id": item.get("effect_id"),
        "review_recommendation": item.get("review_recommendation"),
        "confidence": item.get("confidence"),
        "projected_event_reduction": item.get("projected_event_reduction"),
        "max_coordinate_distance_km": item.get("max_coordinate_distance_km"),
        "active_conflicts": "; ".join(string_list(item.get("active_conflicts"))),
        "time_values": "; ".join(string_list(item.get("time_values"))),
        "time_compatibility": clean_text(time_compatibility.get("basis")),
        "failed_conditions": "; ".join(string_list(item.get("failed_conditions"))),
        "review_reason_codes": "; ".join(string_list(item.get("review_reason_codes"))),
        "source_names": "; ".join(string_list(item.get("source_names"))),
        "source_native_ids": "; ".join(string_list(item.get("source_native_ids"))),
        "dates": "; ".join(string_list(item.get("dates"))),
        "locations": "; ".join(string_list(item.get("locations"))),
        "coordinate_values": "; ".join(string_list(item.get("coordinate_values"))),
        "type_values": "; ".join(string_list(item.get("type_values"))),
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    lines = [
        "# Coordinate Conflict Source Review",
        "",
        "This report is review-only and does not mutate canonical outputs.",
        "",
        "## Summary",
        "",
        f"- Input items reviewed: `{summary.get('reviewed_item_count', 0)}`",
        f"- Review recommendation counts: `{json.dumps(summary.get('review_recommendation_counts') or {}, sort_keys=True)}`",
        f"- Projected reduction by recommendation: `{json.dumps(summary.get('projected_event_reduction_by_review_recommendation') or {}, sort_keys=True)}`",
        f"- Canonical outputs mutated: `{str(payload.get('canonical_outputs_mutated')).lower()}`",
        "",
        "## Items",
        "",
    ]
    for item in payload.get("items") or []:
        if not isinstance(item, dict):
            continue
        time_compatibility = item.get("time_compatibility") if isinstance(item.get("time_compatibility"), dict) else {}
        lines.extend(
            [
                f"### #{item.get('review_rank')} {item.get('review_item_id')}",
                "",
                f"- Review recommendation: `{item.get('review_recommendation')}` confidence `{item.get('confidence')}`",
                f"- Effect ID: `{item.get('effect_id')}`",
                f"- Projected reduction: `{item.get('projected_event_reduction')}`",
                f"- Max coordinate distance km: `{item.get('max_coordinate_distance_km')}`",
                f"- Active conflicts: {', '.join(string_list(item.get('active_conflicts'))) or 'none'}",
                f"- Time values: {', '.join(string_list(item.get('time_values'))) or 'none'}",
                f"- Time compatibility: `{time_compatibility.get('basis')}`",
                f"- Source native IDs: {', '.join(string_list(item.get('source_native_ids'))) or 'none'}",
                f"- Dates: {', '.join(string_list(item.get('dates'))) or 'none'}",
                f"- Locations: {', '.join(string_list(item.get('locations'))) or 'none'}",
                f"- Coordinates: {', '.join(string_list(item.get('coordinate_values'))) or 'none'}",
                f"- Failed conditions: {', '.join(string_list(item.get('failed_conditions'))) or 'none'}",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = clean_text(row.get(key)) or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def count_failed_conditions(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for condition in string_list(row.get("failed_conditions")):
            counts[condition] = counts.get(condition, 0) + 1
    return dict(sorted(counts.items()))


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
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    review = build_coordinate_conflict_source_review(read_json(args.packet))
    review["inputs"] = {"packet": str(args.packet)}
    review["outputs"] = {
        "json": str(args.json_output),
        "csv": str(args.csv_output),
        "markdown": str(args.markdown_output),
    }
    write_json(args.json_output, review)
    write_csv(args.csv_output, review)
    write_markdown(args.markdown_output, review)
    print(
        json.dumps(
            {
                "json_output": str(args.json_output),
                "review_policy": review["review_policy"],
                "summary": review["summary"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
