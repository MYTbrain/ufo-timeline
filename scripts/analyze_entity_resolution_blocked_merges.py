"""Analyze blocked ER merge candidates without creating decisions."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
from typing import Any


DEFAULT_PACKET = Path("data/reports/entity_resolution_blocked_merge_review_packet.json")
DEFAULT_OUTPUT = Path("data/reports/entity_resolution_blocked_merge_analysis.json")

EXACT_IDENTITY_FIELDS = (
    "source_name",
    "source_file",
    "source_native_id",
    "date_iso",
    "time_raw",
)
IDENTITY_FIELDS_WITHOUT_TIME = (
    "source_name",
    "source_file",
    "source_native_id",
    "date_iso",
)


def analyze_entity_resolution_blocked_merges(
    *,
    blocked_packet: dict[str, Any],
    packet_path: Path | None = None,
) -> dict[str, Any]:
    validate_packet_safety(blocked_packet)
    items = []
    for item in blocked_packet.get("items") or []:
        if not isinstance(item, dict):
            continue
        items.append(analyze_blocked_item(item))

    return {
        "schema_version": 1,
        "analysis_policy": "entity_resolution_blocked_merge_analysis_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "override_decisions_created": False,
        "ready_for_canonical_apply": False,
        "inputs": {
            "blocked_merge_packet": str(packet_path) if packet_path else None,
        },
        "blocked_item_count": len(items),
        "classification_counts": count_by(items, "classification"),
        "suggested_action_counts": count_by(items, "suggested_action"),
        "confidence_counts": count_by(items, "analysis_confidence"),
        "high_confidence_shadow_override_candidate_count": sum(
            1 for item in items if item.get("suggested_action") == "candidate_shadow_preview_override"
        ),
        "items": items,
        "notes": [
            "This analysis is suggestion-only and does not create accepted ER decisions.",
            "High-confidence subtype variants may be eligible for a separate shadow-preview override packet.",
            "Coordinate-distance blockers remain review-first unless a later explicit override policy accepts them.",
        ],
    }


def analyze_blocked_item(item: dict[str, Any]) -> dict[str, Any]:
    sources = [source for source in item.get("source_event_summaries") or [] if isinstance(source, dict)]
    blocking_fields = [str(field) for field in item.get("blocking_fields") or []]
    field_conflicts = item.get("field_conflicts") if isinstance(item.get("field_conflicts"), dict) else {}
    exact_identity_match = fields_match(sources, EXACT_IDENTITY_FIELDS)
    location_match = fields_match(sources, ("location_raw",))
    coordinate_km = coordinate_distance_km(sources)
    time_values = normalized_conflict_values(field_conflicts.get("time_raw"))
    parsed_time_minutes = parsed_time_minute_values(time_values)
    summary_similarity = text_conflict_similarity(field_conflicts.get("summary"))
    description_similarity = text_conflict_similarity(field_conflicts.get("description"))
    type_values = normalized_conflict_values(field_conflicts.get("type_normalized"))
    type_variant_score = source_subtype_variant_score(type_values)

    classification = "unclassified_blocker"
    suggested_action = "needs_human_review"
    confidence = "low"
    reasons: list[str] = []
    risks: list[str] = []

    if blocking_fields == ["time_raw"]:
        same_core_without_time = fields_match(sources, IDENTITY_FIELDS_WITHOUT_TIME)
        if same_core_without_time and location_match and coordinate_km in (None, 0):
            if parsed_time_minutes and len(parsed_time_minutes) == 1 and len(parsed_time_minutes[0][1]) == len(time_values):
                classification = "likely_time_format_variant"
                suggested_action = "candidate_shadow_preview_override"
                confidence = "high"
                reasons.extend(
                    [
                        "source/date/native_id match when time is excluded",
                        "location and coordinates do not add a separate conflict",
                        "time_raw values parse to the same minute",
                    ]
                )
            else:
                classification = "time_format_or_multiple_time_variant"
                suggested_action = "time_review_before_override"
                confidence = "medium"
                reasons.extend(
                    [
                        "source/date/native_id match when time is excluded",
                        "location and coordinates do not add a separate conflict",
                        "time_raw needs review before any override",
                    ]
                )
        else:
            classification = "time_conflict_requires_review"
            reasons.append("time conflict lacks enough matching identity evidence for an override suggestion")
            if not same_core_without_time:
                risks.append("source/date/native_id identity fields do not all match")
            if not location_match:
                risks.append("location text differs")
            if coordinate_km not in (None, 0):
                risks.append("coordinates differ")

    elif "type_normalized" in blocking_fields:
        if exact_identity_match and location_match and coordinate_km in (None, 0) and type_variant_score >= 0.6:
            classification = "likely_source_subtype_variant"
            suggested_action = "candidate_shadow_preview_override"
            confidence = "high"
            reasons.extend(
                [
                    "source/date/time/native_id match exactly",
                    "location and coordinates match exactly",
                    "type codes appear to be source subcode variants",
                ]
            )
            if summary_similarity is not None and summary_similarity < 0.5:
                risks.append("summary text overlap is low despite matching source identity")
        else:
            classification = "type_conflict_requires_review"
            reasons.append("type conflict does not meet strict subtype-variant override criteria")
            if not exact_identity_match:
                risks.append("source/date/time/native_id identity fields do not all match")
            if not location_match:
                risks.append("location text differs")
            if coordinate_km not in (None, 0):
                risks.append("coordinates differ")

    elif "coordinate_distance_over_10km" in blocking_fields:
        same_core = fields_match(sources, EXACT_IDENTITY_FIELDS + ("type_normalized",))
        location_similarity = location_token_similarity(sources)
        if same_core and location_similarity >= 0.5 and coordinate_km is not None:
            classification = "nearby_location_coordinate_variant"
            suggested_action = "coordinate_review_before_override"
            confidence = "medium"
            reasons.extend(
                [
                    "source/date/time/native_id/type match exactly",
                    "location tokens overlap but coordinates exceed readiness distance threshold",
                ]
            )
            risks.append("coordinate distance exceeded the current hard safety threshold")
        else:
            classification = "coordinate_conflict_requires_review"
            reasons.append("coordinate conflict lacks enough matching identity evidence for an override suggestion")
            confidence = "low"
    else:
        reasons.append("blocking fields are not covered by the current analyzer")

    if summary_similarity is not None:
        reasons.append(f"summary_similarity={summary_similarity:.3f}")
    if description_similarity is not None:
        reasons.append(f"description_similarity={description_similarity:.3f}")
    if coordinate_km is not None:
        reasons.append(f"max_coordinate_distance_km={coordinate_km:.3f}")

    return {
        "review_item_id": item.get("review_item_id"),
        "patch_id": item.get("patch_id"),
        "effect_id": item.get("effect_id"),
        "blocking_fields": blocking_fields,
        "classification": classification,
        "suggested_action": suggested_action,
        "analysis_confidence": confidence,
        "projected_event_reduction": item.get("projected_event_reduction"),
        "exact_identity_match": exact_identity_match,
        "location_raw_match": location_match,
        "coordinate_distance_km": coordinate_km,
        "time_values": time_values,
        "parsed_time_minutes": [minutes for minutes, _raw_values in parsed_time_minutes],
        "type_values": type_values,
        "type_variant_score": type_variant_score,
        "summary_similarity": summary_similarity,
        "description_similarity": description_similarity,
        "reasons": reasons,
        "risks": risks,
    }


def fields_match(sources: list[dict[str, Any]], fields: tuple[str, ...]) -> bool:
    if len(sources) < 2:
        return False
    for field in fields:
        values = {canonical_scalar(source.get(field)) for source in sources}
        values.discard("")
        if len(values) > 1:
            return False
    return True


def canonical_scalar(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).strip().lower())


def normalized_conflict_values(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted({canonical_scalar(item) for item in value if canonical_scalar(item)})


def source_subtype_variant_score(values: list[str]) -> float:
    if len(values) < 2:
        return 0.0
    shortest = min(values, key=len)
    longest = max(values, key=len)
    if shortest == longest:
        return 1.0
    if longest.startswith(shortest) or longest.endswith(shortest):
        return len(shortest) / len(longest)
    shared = len(set(shortest) & set(longest))
    return shared / max(1, len(set(shortest) | set(longest)))


def parsed_time_minute_values(values: list[str]) -> list[tuple[int, list[str]]]:
    by_minute: dict[int, list[str]] = {}
    for value in values:
        minute = parse_time_minutes(value)
        if minute is None:
            continue
        by_minute.setdefault(minute, []).append(value)
    return sorted((minute, sorted(raw_values)) for minute, raw_values in by_minute.items())


def parse_time_minutes(value: str) -> int | None:
    text = canonical_scalar(value)
    if not text:
        return None
    if "noon" in text:
        return 12 * 60
    if "midnight" in text:
        return 0
    am_pm_match = re.search(r"\b([1-9]|1[0-2])(?::([0-5]\d))?\s*([ap])\.?m?\.?\b", text)
    if am_pm_match:
        hour = int(am_pm_match.group(1))
        minute = int(am_pm_match.group(2) or 0)
        marker = am_pm_match.group(3)
        if marker == "a":
            hour = 0 if hour == 12 else hour
        else:
            hour = 12 if hour == 12 else hour + 12
        return hour * 60 + minute
    colon_match = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", text)
    if colon_match:
        return int(colon_match.group(1)) * 60 + int(colon_match.group(2))
    compact_match = re.search(r"\b([01]?\d|2[0-3])([0-5]\d)\b", text)
    if compact_match:
        return int(compact_match.group(1)) * 60 + int(compact_match.group(2))
    hour_match = re.fullmatch(r"(?:[01]?\d|2[0-3])", text)
    if hour_match:
        hour = int(text)
        if hour <= 12:
            return None
        return hour * 60
    return None


def text_conflict_similarity(value: Any) -> float | None:
    if not isinstance(value, list) or len(value) < 2:
        return None
    token_sets = [tokenize_text(str(item)) for item in value if str(item).strip()]
    token_sets = [tokens for tokens in token_sets if tokens]
    if len(token_sets) < 2:
        return None
    similarities = []
    for index, left in enumerate(token_sets):
        for right in token_sets[index + 1 :]:
            similarities.append(jaccard(left, right))
    if not similarities:
        return None
    return min(similarities)


def location_token_similarity(sources: list[dict[str, Any]]) -> float:
    token_sets = [tokenize_text(str(source.get("location_raw") or "")) for source in sources]
    token_sets = [tokens for tokens in token_sets if tokens]
    if len(token_sets) < 2:
        return 0.0
    return min(jaccard(left, right) for index, left in enumerate(token_sets) for right in token_sets[index + 1 :])


def tokenize_text(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.lower()))


def jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    return len(left & right) / max(1, len(left | right))


def coordinate_distance_km(sources: list[dict[str, Any]]) -> float | None:
    points = []
    for source in sources:
        lat = numeric(source.get("lat"))
        lon = numeric(source.get("lon"))
        if lat is not None and lon is not None:
            points.append((lat, lon))
    if len(points) < 2:
        return None
    return max(
        haversine_km(left, right)
        for index, left in enumerate(points)
        for right in points[index + 1 :]
    )


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


def numeric(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def validate_packet_safety(packet: dict[str, Any]) -> None:
    errors: list[str] = []
    if packet.get("packet_policy") != "entity_resolution_blocked_merge_review_only":
        errors.append("packet_policy must be 'entity_resolution_blocked_merge_review_only'")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "decisions_created", "auto_merge_performed"):
        if packet.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError(f"blocked merge packet is not safe for analysis: {'; '.join(errors)}")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blocked-packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packet = read_json(args.blocked_packet)
    report = analyze_entity_resolution_blocked_merges(blocked_packet=packet, packet_path=args.blocked_packet)
    write_json(args.output, report)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "analysis_policy": report["analysis_policy"],
                "blocked_item_count": report["blocked_item_count"],
                "classification_counts": report["classification_counts"],
                "high_confidence_shadow_override_candidate_count": report[
                    "high_confidence_shadow_override_candidate_count"
                ],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
