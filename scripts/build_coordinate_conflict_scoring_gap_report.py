"""Build a review-only scoring gap digest for coordinate-conflict candidates.

This joins the coordinate-conflict source evidence packet with the source-review
recommendations and summarizes which scoring dimensions are still missing before
any canonical entity-resolution decision can be considered.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import re
from pathlib import Path
from typing import Any

from scripts.review_coordinate_conflict_source_candidates import (
    INPUT_PACKET_POLICY,
    REVIEW_POLICY as INPUT_REVIEW_POLICY,
    SOURCE_REVIEW_COORDINATE_PRECISION_CANDIDATE,
    as_float,
    as_int,
    clean_text,
    read_json,
    string_list,
    write_json,
)


DEFAULT_PACKET = Path("data/reports/entity_resolution_cluster_coordinate_conflict_source_evidence_packet.json")
DEFAULT_REVIEW = Path("data/reports/entity_resolution_cluster_coordinate_conflict_source_review.json")
DEFAULT_JSON_OUTPUT = Path("data/reports/entity_resolution_coordinate_conflict_scoring_gap_report.json")
DEFAULT_CSV_OUTPUT = Path("data/reports/entity_resolution_coordinate_conflict_scoring_gap_report.csv")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/entity_resolution_coordinate_conflict_scoring_gap_report.md")

REPORT_POLICY = "entity_resolution_coordinate_conflict_scoring_gap_review_only"
NEEDS_MORE_EVIDENCE = "needs_more_evidence"

CSV_FIELDS = (
    "review_rank",
    "review_item_id",
    "effect_id",
    "current_review_recommendation",
    "current_confidence",
    "review_next_action",
    "projected_event_reduction",
    "max_coordinate_distance_km",
    "coordinate_distance_bucket",
    "date_status",
    "date_values",
    "date_precision_values",
    "time_status",
    "time_basis",
    "location_text_status",
    "source_family_status",
    "source_native_id_status",
    "type_status",
    "shape_status",
    "description_similarity_status",
    "description_similarity_score",
    "provenance_status",
    "missing_scoring_dimensions",
)

EXACT_DAY_PRECISIONS = {
    "day",
    "date",
    "exact",
    "exact_day",
    "full_date",
}


def build_coordinate_conflict_scoring_gap_report(
    *,
    packet: dict[str, Any],
    review: dict[str, Any],
    packet_path: Path | None = None,
    review_path: Path | None = None,
) -> dict[str, Any]:
    validate_packet_safety(packet)
    validate_review_safety(review)
    review_by_item_id = {
        item_id: item
        for item in review.get("items") or []
        if isinstance(item, dict) and (item_id := clean_text(item.get("review_item_id")))
    }
    packet_items = [item for item in packet.get("items") or [] if isinstance(item, dict)]
    gap_items = [build_gap_item(item, review_by_item_id.get(clean_text(item.get("review_item_id")))) for item in packet_items]
    summary = build_summary(gap_items, review_by_item_id, packet_items)
    return {
        "schema_version": 1,
        "report_policy": REPORT_POLICY,
        "input_packet_policy": packet.get("packet_policy"),
        "input_review_policy": review.get("review_policy"),
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "validated_decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "inputs": {
            "packet": str(packet_path) if packet_path else None,
            "review": str(review_path) if review_path else None,
        },
        "summary": summary,
        "items": gap_items,
        "notes": [
            "This digest is review-only and does not create decisions or mutate canonical data.",
            "It highlights missing scoring dimensions that should be resolved before any apply path.",
            "False merges remain higher risk than missed duplicates; coordinate conflicts require explicit review.",
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
        raise ValueError("coordinate-conflict source packet is unsafe for gap reporting: " + "; ".join(errors))


def validate_review_safety(review: dict[str, Any]) -> None:
    errors: list[str] = []
    if review.get("review_policy") != INPUT_REVIEW_POLICY:
        errors.append(f"review_policy must be {INPUT_REVIEW_POLICY}")
    for flag in (
        "canonical_outputs_mutated",
        "preview_outputs_written",
        "decisions_created",
        "decision_outputs_created",
        "validated_decisions_created",
        "auto_merge_performed",
        "ready_for_canonical_apply",
    ):
        if review.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError("coordinate-conflict source review is unsafe for gap reporting: " + "; ".join(errors))


def build_gap_item(packet_item: dict[str, Any], review_item: dict[str, Any] | None) -> dict[str, Any]:
    evidence_rows = [row for row in packet_item.get("evidence_rows") or [] if isinstance(row, dict)]
    source_summary = packet_item.get("source_summary") if isinstance(packet_item.get("source_summary"), dict) else {}
    source = (
        packet_item.get("shadow_preview_override_source")
        if isinstance(packet_item.get("shadow_preview_override_source"), dict)
        else {}
    )
    review_item = review_item or {}
    date_profile = classify_date_profile(evidence_rows, source_summary)
    time_profile = classify_time_profile(review_item)
    location_profile = classify_distinct_profile(
        values_from_summary_or_rows(source_summary, "location_values", evidence_rows, ("location_raw",)),
        "location_text",
    )
    source_family_profile = classify_distinct_profile(
        values_from_summary_or_rows(source_summary, "source_names", evidence_rows, ("source_name",)),
        "source_family",
    )
    source_native_id_profile = classify_distinct_profile(
        values_from_summary_or_rows(source_summary, "source_native_ids", evidence_rows, ("source_native_id",)),
        "source_native_id",
    )
    type_profile = classify_distinct_profile(
        values_from_summary_or_rows(source_summary, "type_values", evidence_rows, ("type_normalized", "type_raw")),
        "type",
    )
    shape_profile = classify_distinct_profile(
        values_from_summary_or_rows(source_summary, "shape_values", evidence_rows, ("shape_normalized", "shape_raw")),
        "shape",
    )
    description_profile = classify_description_similarity(evidence_rows)
    provenance_profile = classify_provenance(packet_item)
    max_distance = as_float(
        review_item.get("max_coordinate_distance_km")
        if review_item.get("max_coordinate_distance_km") is not None
        else source.get("max_coordinate_distance_km")
    )
    recommendation = clean_text(review_item.get("review_recommendation")) or "missing_review"
    confidence = clean_text(review_item.get("confidence")) or "none"
    missing_dimensions = missing_scoring_dimensions(
        date_profile=date_profile,
        time_profile=time_profile,
        location_profile=location_profile,
        source_family_profile=source_family_profile,
        source_native_id_profile=source_native_id_profile,
        type_profile=type_profile,
        shape_profile=shape_profile,
        description_profile=description_profile,
        provenance_profile=provenance_profile,
    )
    return {
        "review_rank": as_int(packet_item.get("review_rank") or review_item.get("review_rank")),
        "review_item_id": clean_text(packet_item.get("review_item_id")) or clean_text(review_item.get("review_item_id")),
        "effect_id": clean_text(packet_item.get("effect_id")) or clean_text(review_item.get("effect_id")),
        "current_review_recommendation": recommendation,
        "current_confidence": confidence,
        "review_next_action": next_action(recommendation, missing_dimensions),
        "projected_event_reduction": as_int(
            packet_item.get("projected_event_reduction") or review_item.get("projected_event_reduction")
        ),
        "max_coordinate_distance_km": max_distance,
        "coordinate_distance_bucket": coordinate_distance_bucket(max_distance),
        "date_status": date_profile["status"],
        "date_values": date_profile["values"],
        "date_precision_values": date_profile["precision_values"],
        "time_status": time_profile["status"],
        "time_basis": time_profile["basis"],
        "time_values": string_list(review_item.get("time_values")),
        "location_text_status": location_profile["status"],
        "location_values": location_profile["values"],
        "source_family_status": source_family_profile["status"],
        "source_names": source_family_profile["values"],
        "source_native_id_status": source_native_id_profile["status"],
        "source_native_ids": source_native_id_profile["values"],
        "type_status": type_profile["status"],
        "type_values": type_profile["values"],
        "shape_status": shape_profile["status"],
        "shape_values": shape_profile["values"],
        "description_similarity_status": description_profile["status"],
        "description_similarity_score": description_profile["score"],
        "provenance_status": provenance_profile["status"],
        "candidate_input_ids_missing_from_evidence": provenance_profile["missing_input_ids"],
        "missing_canonical_event_ids": provenance_profile["missing_event_ids"],
        "missing_scoring_dimensions": missing_dimensions,
        "failed_conditions": string_list(review_item.get("failed_conditions")),
    }


def classify_date_profile(evidence_rows: list[dict[str, Any]], source_summary: dict[str, Any]) -> dict[str, Any]:
    values = sorted(
        set(
            string_list(source_summary.get("date_values"))
            or [clean_text(row.get("date_iso")) for row in evidence_rows if clean_text(row.get("date_iso"))]
        )
    )
    precision_values = sorted(
        set(
            string_list(source_summary.get("date_precision_values"))
            or [clean_text(row.get("date_precision")) for row in evidence_rows if clean_text(row.get("date_precision"))]
        )
    )
    normalized_precisions = {value.casefold() for value in precision_values}
    if len(values) == 1 and normalized_precisions and normalized_precisions.issubset(EXACT_DAY_PRECISIONS):
        status = "single_exact_day"
    elif len(values) == 1:
        status = "single_non_exact_date"
    elif values:
        status = "mixed_date_values"
    else:
        status = "missing_date"
    return {"status": status, "values": values, "precision_values": precision_values}


def classify_time_profile(review_item: dict[str, Any]) -> dict[str, Any]:
    compatibility = review_item.get("time_compatibility") if isinstance(review_item.get("time_compatibility"), dict) else {}
    basis = clean_text(compatibility.get("basis"))
    compatible = compatibility.get("compatible")
    if not review_item:
        status = "missing_review_time"
    elif basis == "no_time_values":
        status = "missing_time_evidence"
    elif compatible is True:
        status = "compatible_time"
    elif compatible is False:
        status = "incompatible_time"
    else:
        status = "unknown_time_compatibility"
    return {"status": status, "basis": basis or "unknown"}


def classify_distinct_profile(values: list[str], label: str) -> dict[str, Any]:
    distinct = sorted(set(value for value in values if value))
    if len(distinct) == 1:
        status = f"single_{label}"
    elif len(distinct) > 1:
        status = f"mixed_{label}"
    else:
        status = f"missing_{label}"
    return {"status": status, "values": distinct}


def classify_description_similarity(evidence_rows: list[dict[str, Any]]) -> dict[str, Any]:
    texts = []
    for row in evidence_rows:
        text = clean_text(row.get("summary")) or clean_text(row.get("description_excerpt"))
        if text:
            texts.append(normalized_description_text(text))
    distinct = sorted(set(text for text in texts if text))
    if not distinct:
        return {"status": "missing_description_text", "score": 0.0}
    if len(distinct) == 1:
        return {"status": "identical_description_text", "score": 1.0}
    scores = [jaccard_score(left, right) for left, right in itertools.combinations(distinct, 2)]
    min_score = min(scores) if scores else 1.0
    if min_score >= 0.8:
        status = "high_description_similarity"
    elif min_score >= 0.5:
        status = "medium_description_similarity"
    else:
        status = "description_text_conflict"
    return {"status": status, "score": round(min_score, 4)}


def classify_provenance(packet_item: dict[str, Any]) -> dict[str, Any]:
    missing_input_ids = string_list(packet_item.get("candidate_input_ids_missing_from_evidence"))
    missing_event_ids = string_list(packet_item.get("missing_canonical_event_ids"))
    if missing_input_ids or missing_event_ids:
        status = "incomplete_provenance"
    else:
        status = "complete_provenance"
    return {"status": status, "missing_input_ids": missing_input_ids, "missing_event_ids": missing_event_ids}


def missing_scoring_dimensions(
    *,
    date_profile: dict[str, Any],
    time_profile: dict[str, Any],
    location_profile: dict[str, Any],
    source_family_profile: dict[str, Any],
    source_native_id_profile: dict[str, Any],
    type_profile: dict[str, Any],
    shape_profile: dict[str, Any],
    description_profile: dict[str, Any],
    provenance_profile: dict[str, Any],
) -> list[str]:
    missing: list[str] = []
    if date_profile["status"] != "single_exact_day":
        missing.append("exact_day_date")
    if time_profile["status"] not in {"compatible_time"}:
        missing.append("compatible_time_evidence")
    if location_profile["status"] != "single_location_text":
        missing.append("single_location_text")
    if source_family_profile["status"] != "single_source_family":
        missing.append("single_source_family")
    if source_native_id_profile["status"] != "single_source_native_id":
        missing.append("single_source_native_id")
    if type_profile["status"].startswith("mixed_"):
        missing.append("type_consistency")
    if shape_profile["status"].startswith("mixed_"):
        missing.append("shape_consistency")
    if description_profile["status"] in {"missing_description_text", "description_text_conflict"}:
        missing.append("description_similarity")
    if provenance_profile["status"] != "complete_provenance":
        missing.append("provenance_completeness")
    return missing


def next_action(recommendation: str, missing_dimensions: list[str]) -> str:
    if recommendation == SOURCE_REVIEW_COORDINATE_PRECISION_CANDIDATE and not missing_dimensions:
        return "review_coordinate_precision_candidate_before_decision"
    if recommendation == SOURCE_REVIEW_COORDINATE_PRECISION_CANDIDATE:
        return "resolve_scoring_gaps_before_decision"
    if recommendation == NEEDS_MORE_EVIDENCE:
        return "keep_blocked_until_missing_dimensions_resolved"
    if recommendation == "missing_review":
        return "create_source_review_before_scoring"
    return "manual_review_required"


def coordinate_distance_bucket(distance_km: float) -> str:
    if distance_km <= 0:
        return "missing_or_zero"
    if distance_km <= 10:
        return "under_10km"
    if distance_km <= 15:
        return "10_to_15km"
    if distance_km <= 50:
        return "15_to_50km"
    return "over_50km"


def values_from_summary_or_rows(
    source_summary: dict[str, Any],
    summary_key: str,
    evidence_rows: list[dict[str, Any]],
    row_keys: tuple[str, ...],
) -> list[str]:
    summary_values = string_list(source_summary.get(summary_key))
    if summary_values:
        return summary_values
    values: list[str] = []
    for row in evidence_rows:
        for key in row_keys:
            if value := clean_text(row.get(key)):
                values.append(value)
                break
    return values


def normalized_description_text(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def jaccard_score(left: str, right: str) -> float:
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens and not right_tokens:
        return 1.0
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def build_summary(
    items: list[dict[str, Any]],
    review_by_item_id: dict[str, dict[str, Any]],
    packet_items: list[dict[str, Any]],
) -> dict[str, Any]:
    packet_ids = {clean_text(item.get("review_item_id")) for item in packet_items if clean_text(item.get("review_item_id"))}
    review_ids = set(review_by_item_id)
    return {
        "input_packet_item_count": len(packet_items),
        "input_review_item_count": len(review_by_item_id),
        "reported_item_count": len(items),
        "packet_items_missing_review_count": len(packet_ids - review_ids),
        "review_items_missing_packet_count": len(review_ids - packet_ids),
        "current_review_recommendation_counts": count_by(items, "current_review_recommendation"),
        "current_confidence_counts": count_by(items, "current_confidence"),
        "coordinate_distance_bucket_counts": count_by(items, "coordinate_distance_bucket"),
        "review_next_action_counts": count_by(items, "review_next_action"),
        "missing_scoring_dimension_counts": count_nested_values(items, "missing_scoring_dimensions"),
        "projected_event_reduction_by_next_action": sum_reduction_by(items, "review_next_action"),
        "canonical_outputs_mutated": False,
        "ready_for_canonical_apply": False,
    }


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = clean_text(row.get(key)) or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def count_nested_values(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        values = string_list(row.get(key))
        if not values:
            counts["none"] = counts.get("none", 0) + 1
        for value in values:
            counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def sum_reduction_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    sums: dict[str, int] = {}
    for row in rows:
        value = clean_text(row.get(key)) or "unknown"
        sums[value] = sums.get(value, 0) + as_int(row.get("projected_event_reduction"))
    return dict(sorted(sums.items()))


def write_csv(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for item in payload.get("items") or []:
            if isinstance(item, dict):
                writer.writerow(csv_row(item))


def csv_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "review_rank": item.get("review_rank"),
        "review_item_id": item.get("review_item_id"),
        "effect_id": item.get("effect_id"),
        "current_review_recommendation": item.get("current_review_recommendation"),
        "current_confidence": item.get("current_confidence"),
        "review_next_action": item.get("review_next_action"),
        "projected_event_reduction": item.get("projected_event_reduction"),
        "max_coordinate_distance_km": item.get("max_coordinate_distance_km"),
        "coordinate_distance_bucket": item.get("coordinate_distance_bucket"),
        "date_status": item.get("date_status"),
        "date_values": "; ".join(string_list(item.get("date_values"))),
        "date_precision_values": "; ".join(string_list(item.get("date_precision_values"))),
        "time_status": item.get("time_status"),
        "time_basis": item.get("time_basis"),
        "location_text_status": item.get("location_text_status"),
        "source_family_status": item.get("source_family_status"),
        "source_native_id_status": item.get("source_native_id_status"),
        "type_status": item.get("type_status"),
        "shape_status": item.get("shape_status"),
        "description_similarity_status": item.get("description_similarity_status"),
        "description_similarity_score": item.get("description_similarity_score"),
        "provenance_status": item.get("provenance_status"),
        "missing_scoring_dimensions": "; ".join(string_list(item.get("missing_scoring_dimensions"))),
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    lines = [
        "# Coordinate Conflict Scoring Gap Report",
        "",
        "This digest is review-only. It joins source evidence with review recommendations and lists the remaining scoring gaps before any canonical entity-resolution decision.",
        "",
        "## Summary",
        "",
        f"- Reported items: `{summary.get('reported_item_count', 0)}`",
        f"- Current recommendations: `{json.dumps(summary.get('current_review_recommendation_counts') or {}, sort_keys=True)}`",
        f"- Next actions: `{json.dumps(summary.get('review_next_action_counts') or {}, sort_keys=True)}`",
        f"- Missing scoring dimensions: `{json.dumps(summary.get('missing_scoring_dimension_counts') or {}, sort_keys=True)}`",
        f"- Canonical outputs mutated: `{str(payload.get('canonical_outputs_mutated')).lower()}`",
        f"- Ready for canonical apply: `{str(payload.get('ready_for_canonical_apply')).lower()}`",
        "",
        "## Items",
        "",
    ]
    for item in payload.get("items") or []:
        if not isinstance(item, dict):
            continue
        missing = ", ".join(string_list(item.get("missing_scoring_dimensions"))) or "none"
        lines.extend(
            [
                f"### #{item.get('review_rank')} {item.get('review_item_id')}",
                "",
                f"- Current review: `{item.get('current_review_recommendation')}` confidence `{item.get('current_confidence')}`",
                f"- Next action: `{item.get('review_next_action')}`",
                f"- Coordinate distance: `{item.get('max_coordinate_distance_km')}` km (`{item.get('coordinate_distance_bucket')}`)",
                f"- Date/time: `{item.get('date_status')}` / `{item.get('time_status')}` (`{item.get('time_basis')}`)",
                f"- Location/source: `{item.get('location_text_status')}`, `{item.get('source_native_id_status')}`",
                f"- Type/shape: `{item.get('type_status')}`, `{item.get('shape_status')}`",
                f"- Description: `{item.get('description_similarity_status')}` score `{item.get('description_similarity_score')}`",
                f"- Provenance: `{item.get('provenance_status')}`",
                f"- Missing scoring dimensions: {missing}",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_coordinate_conflict_scoring_gap_report(
        packet=read_json(args.packet),
        review=read_json(args.review),
        packet_path=args.packet,
        review_path=args.review,
    )
    report["outputs"] = {
        "json": str(args.json_output),
        "csv": str(args.csv_output),
        "markdown": str(args.markdown_output),
    }
    write_json(args.json_output, report)
    write_csv(args.csv_output, report)
    write_markdown(args.markdown_output, report)
    print(
        json.dumps(
            {
                "json_output": str(args.json_output),
                "report_policy": report["report_policy"],
                "summary": report["summary"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
