"""Review unresolved type-conflict source-identity evidence.

This classifier is conservative. It can recommend source-identity variant
candidates for later human decision staging, but it does not create decisions,
effects, preview outputs, or canonical mutations.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from pathlib import Path
from typing import Any

from parser.canonical_schema import clean_text


DEFAULT_PACKET = Path("data/reports/entity_resolution_type_conflict_source_identity_evidence_packet_worklist.json")
DEFAULT_JSON_OUTPUT = Path("data/reports/entity_resolution_type_conflict_source_identity_review_worklist.json")
DEFAULT_CSV_OUTPUT = Path("data/reports/entity_resolution_type_conflict_source_identity_review_worklist.csv")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/entity_resolution_type_conflict_source_identity_review_worklist.md")

PACKET_POLICY = "entity_resolution_type_conflict_source_identity_evidence_review_only"
REVIEW_POLICY = "entity_resolution_type_conflict_source_identity_review_only"

SAFE_RECOMMENDATION = "source_review_identity_variant_same_event_candidate"
NEEDS_MORE_EVIDENCE = "needs_more_evidence"


def review_type_conflict_source_identity_candidates(
    *,
    packet: dict[str, Any],
    packet_path: Path | None = None,
) -> dict[str, Any]:
    validate_packet_safety(packet)
    review_items = []
    for index, item in enumerate([row for row in packet.get("items") or [] if isinstance(row, dict)], start=1):
        review_items.append(review_item(item, review_rank=index))
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
        "inputs": {
            "packet": str(packet_path) if packet_path else None,
        },
        "summary": {
            "input_item_count": len(packet.get("items") or []),
            "reviewed_item_count": len(review_items),
            "review_recommendation_counts": count_by(review_items, "review_recommendation"),
            "confidence_counts": count_by(review_items, "confidence"),
            "failed_condition_counts": failed_condition_counts(review_items),
            "projected_event_reduction_by_review_recommendation": projected_reduction_by_recommendation(
                review_items
            ),
        },
        "items": review_items,
        "notes": [
            "This source review is recommendation-only.",
            "same-event recommendations still require explicit decision staging and preview/apply gates.",
            "Cross-family and coordinate-linked blockers are not processed by this classifier.",
        ],
    }


def validate_packet_safety(packet: dict[str, Any]) -> None:
    errors: list[str] = []
    if packet.get("packet_policy") != PACKET_POLICY:
        errors.append(f"packet_policy must be {PACKET_POLICY!r}")
    for flag in (
        "canonical_outputs_mutated",
        "preview_outputs_written",
        "decisions_created",
        "decision_outputs_created",
        "auto_merge_performed",
        "ready_for_canonical_apply",
    ):
        if packet.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError("source-identity evidence packet is unsafe: " + "; ".join(errors))


def review_item(item: dict[str, Any], *, review_rank: int) -> dict[str, Any]:
    conditions = condition_results(item)
    failed = sorted(name for name, ok in conditions.items() if not ok)
    is_candidate = not failed
    return {
        "review_rank": review_rank,
        "review_item_id": clean_text(item.get("review_item_id")),
        "effect_id": clean_text(item.get("effect_id")),
        "review_recommendation": SAFE_RECOMMENDATION if is_candidate else NEEDS_MORE_EVIDENCE,
        "confidence": "medium" if is_candidate else "low",
        "projected_event_reduction": int(item.get("projected_event_reduction") or 0),
        "type_conflict_classification": clean_text(item.get("type_conflict_classification")),
        "review_risk_tier": clean_text(item.get("review_risk_tier")),
        "identity_consistency": clean_text(item.get("identity_consistency")),
        "type_values": string_list(item.get("type_values")),
        "type_family_prefixes": string_list(item.get("type_family_prefixes")),
        "active_conflicts": active_conflicts(item),
        "failed_conditions": failed,
        "condition_results": conditions,
        "max_coordinate_distance_km": max_coordinate_distance_km(item),
        "summary_similarity_min": summary_similarity_min(item),
        "review_reason_codes": reason_codes(item, is_candidate=is_candidate, failed_conditions=failed),
        "source_names": string_list(source_summary(item).get("source_names")),
        "source_native_ids": string_list(source_summary(item).get("source_native_ids")),
        "dates": string_list(source_summary(item).get("date_values")),
        "times": string_list(source_summary(item).get("time_values")),
        "locations": string_list(source_summary(item).get("location_values")),
        "coordinate_values": string_list(source_summary(item).get("coordinate_values")),
        "merge_canonical_event_ids": string_list(item.get("merge_canonical_event_ids")),
        "candidate_canonical_input_ids": string_list(item.get("candidate_canonical_input_ids")),
        "notes": (
            "Source evidence is consistent with a same-event identity/location variant; still requires explicit decision and apply gates."
            if is_candidate
            else "Source evidence is not yet strict enough for same-event recommendation."
        ),
    }


def condition_results(item: dict[str, Any]) -> dict[str, bool]:
    summary = source_summary(item)
    conflicts = conflict_flags(item)
    max_distance = max_coordinate_distance_km(item)
    return {
        "no_missing_event_or_input_ids": not item.get("missing_canonical_event_ids")
        and not item.get("candidate_input_ids_missing_from_evidence"),
        "single_source": len(string_list(summary.get("source_names"))) == 1,
        "single_source_native_id": len(string_list(summary.get("source_native_ids"))) == 1,
        "single_exact_date": len(string_list(summary.get("date_values"))) == 1
        and set(string_list(summary.get("date_precision_values"))) <= {"exact_day"},
        "no_time_conflict": conflicts.get("time") is not True,
        "no_shape_conflict": conflicts.get("shape") is not True,
        "no_source_native_conflict": conflicts.get("source_native_id") is not True,
        "single_type_family": len(string_list(item.get("type_family_prefixes"))) == 1,
        "coordinate_variance_small_or_absent": max_distance is None or max_distance <= 2.0,
        "summary_text_compatible": summary_similarity_min(item) is not None
        and (summary_similarity_min(item) or 0) >= 0.65,
    }


def active_conflicts(item: dict[str, Any]) -> list[str]:
    return sorted(name for name, active in conflict_flags(item).items() if active)


def conflict_flags(item: dict[str, Any]) -> dict[str, bool]:
    conflicts = item.get("conflict_summary") if isinstance(item.get("conflict_summary"), dict) else {}
    flags = conflicts.get("conflict_flags") if isinstance(conflicts.get("conflict_flags"), dict) else {}
    return {str(key): bool(value) for key, value in flags.items()}


def source_summary(item: dict[str, Any]) -> dict[str, Any]:
    return item.get("source_summary") if isinstance(item.get("source_summary"), dict) else {}


def max_coordinate_distance_km(item: dict[str, Any]) -> float | None:
    points = []
    for row in item.get("evidence_rows") or []:
        if not isinstance(row, dict):
            continue
        lat = numeric(row.get("lat"))
        lon = numeric(row.get("lon"))
        if lat is not None and lon is not None:
            points.append((lat, lon))
    if len(points) < 2:
        return None
    max_distance = 0.0
    for index, left in enumerate(points):
        for right in points[index + 1 :]:
            max_distance = max(max_distance, haversine_km(left, right))
    return round(max_distance, 6)


def haversine_km(left: tuple[float, float], right: tuple[float, float]) -> float:
    lat1, lon1 = left
    lat2, lon2 = right
    radius_km = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def summary_similarity_min(item: dict[str, Any]) -> float | None:
    summaries = [
        normalize_text(row.get("summary"))
        for row in item.get("evidence_rows") or []
        if isinstance(row, dict) and normalize_text(row.get("summary"))
    ]
    if len(summaries) < 2:
        return None
    scores = []
    for index, left in enumerate(summaries):
        for right in summaries[index + 1 :]:
            scores.append(token_similarity(left, right))
    return round(min(scores), 6) if scores else None


def token_similarity(left: str, right: str) -> float:
    left_tokens = set(re.findall(r"[a-z0-9]+", left.lower()))
    right_tokens = set(re.findall(r"[a-z0-9]+", right.lower()))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def reason_codes(item: dict[str, Any], *, is_candidate: bool, failed_conditions: list[str]) -> list[str]:
    if not is_candidate:
        return [f"failed:{condition}" for condition in failed_conditions]
    codes = ["same_source_native_date", "compatible_summary_text", "review_only_not_decision"]
    if "location" in active_conflicts(item):
        codes.append("location_variant")
    if "type" in active_conflicts(item):
        codes.append("type_subcode_variant")
    if "coordinate" in active_conflicts(item):
        codes.append("small_coordinate_variance")
    return codes


def failed_condition_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        for condition in item.get("failed_conditions") or []:
            counts[condition] = counts.get(condition, 0) + 1
    return dict(sorted(counts.items()))


def projected_reduction_by_recommendation(items: list[dict[str, Any]]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for item in items:
        key = clean_text(item.get("review_recommendation")) or "unknown"
        totals[key] = totals.get(key, 0) + int(item.get("projected_event_reduction") or 0)
    return dict(sorted(totals.items()))


def count_by(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = clean_text(row.get(field)) or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [text for item in value if (text := clean_text(item))]
    text = clean_text(value)
    return [text] if text else []


def numeric(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "review_rank",
        "review_recommendation",
        "confidence",
        "review_item_id",
        "effect_id",
        "projected_event_reduction",
        "type_conflict_classification",
        "review_risk_tier",
        "identity_consistency",
        "type_values",
        "active_conflicts",
        "failed_conditions",
        "max_coordinate_distance_km",
        "summary_similarity_min",
        "source_names",
        "source_native_ids",
        "dates",
        "times",
        "locations",
        "coordinate_values",
        "review_reason_codes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in report.get("items") or []:
            writer.writerow({field: csv_value(item.get(field)) for field in fieldnames})


def write_markdown(path: Path, report: dict[str, Any], *, item_limit: int = 60) -> None:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    lines = [
        "# Type-Conflict Source Identity Review",
        "",
        f"- Policy: `{report.get('review_policy')}`",
        f"- Reviewed items: {summary.get('reviewed_item_count')}",
        f"- Canonical outputs mutated: `{report.get('canonical_outputs_mutated')}`",
        "",
        "## Recommendation Counts",
        "",
    ]
    for recommendation, count in sorted((summary.get("review_recommendation_counts") or {}).items()):
        lines.append(f"- `{recommendation}`: {count}")
    lines.extend(["", "## Review Rows", ""])
    for item in (report.get("items") or [])[:item_limit]:
        lines.extend(
            [
                f"### {item.get('review_rank')}. {item.get('review_recommendation')}",
                "",
                f"- Review item: `{item.get('review_item_id')}`",
                f"- Confidence: `{item.get('confidence')}`",
                f"- Type values: {', '.join(item.get('type_values') or [])}",
                f"- Active conflicts: {', '.join(item.get('active_conflicts') or []) or 'none'}",
                f"- Failed conditions: {', '.join(item.get('failed_conditions') or []) or 'none'}",
                f"- Max coordinate distance km: `{item.get('max_coordinate_distance_km')}`",
                f"- Summary similarity min: `{item.get('summary_similarity_min')}`",
                f"- Source/native/date/time: {', '.join(item.get('source_names') or [])} / {', '.join(item.get('source_native_ids') or [])} / {', '.join(item.get('dates') or [])} / {', '.join(item.get('times') or [])}",
                f"- Locations: {'; '.join(item.get('locations') or [])}",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def csv_value(value: Any) -> Any:
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument("--markdown-item-limit", type=int, default=60)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = review_type_conflict_source_identity_candidates(packet=read_json(args.packet), packet_path=args.packet)
    report["outputs"] = {
        "json": str(args.json_output),
        "csv": str(args.csv_output),
        "markdown": str(args.markdown_output),
    }
    write_json(args.json_output, report)
    write_csv(args.csv_output, report)
    write_markdown(args.markdown_output, report, item_limit=args.markdown_item_limit)
    print(
        json.dumps(
            {
                "json_output": str(args.json_output),
                "csv_output": str(args.csv_output),
                "markdown_output": str(args.markdown_output),
                "reviewed_item_count": report["summary"]["reviewed_item_count"],
                "review_recommendation_counts": report["summary"]["review_recommendation_counts"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
