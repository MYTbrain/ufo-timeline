"""Check ER merge preview readiness before any full shadow-corpus apply."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
from typing import Any


DEFAULT_PREVIEW = Path("data/reports/entity_resolution_ai_merged_event_preview.json")
DEFAULT_OUTPUT = Path("data/reports/entity_resolution_ai_merge_readiness.json")

BLOCKING_CONFLICT_FIELDS = {
    "date_iso",
    "time_raw",
    "type_normalized",
}
REVIEW_CONFLICT_FIELDS = {
    "coordinate_source",
    "shape_normalized",
    "summary",
    "description",
}


def check_entity_resolution_merge_readiness(
    *,
    merged_event_preview: dict[str, Any],
    preview_path: Path | None = None,
) -> dict[str, Any]:
    validate_preview_safety(merged_event_preview)
    previews = merged_event_preview.get("previews") if isinstance(merged_event_preview.get("previews"), list) else []
    conflict_counts: dict[str, int] = {}
    blocking_items = []
    review_items = []

    for item in previews:
        if not isinstance(item, dict):
            continue
        field_conflicts = item.get("field_conflicts") if isinstance(item.get("field_conflicts"), dict) else {}
        for field in sorted(field_conflicts):
            conflict_counts[field] = conflict_counts.get(field, 0) + 1
        blocking_fields = material_blocking_fields(item, field_conflicts)
        review_fields = sorted(field for field in field_conflicts if field in REVIEW_CONFLICT_FIELDS)
        if coordinate_distance_km(item) is not None and coordinate_distance_km(item) <= 2:
            review_fields.extend(field for field in ["lat", "lon"] if field in field_conflicts)
        elif any(field in field_conflicts for field in ["lat", "lon"]):
            review_fields.append("coordinate_variance")
        if "location_raw" in field_conflicts and "location_raw" not in blocking_fields:
            review_fields.append("location_raw")
        if item.get("missing_event_ids"):
            blocking_fields.append("missing_event_ids")
        if blocking_fields:
            blocking_items.append(readiness_item(item, blocking_fields, "blocking_conflict"))
        elif review_fields:
            review_items.append(readiness_item(item, review_fields, "review_conflict"))

    ready_for_full_shadow_preview = not blocking_items
    return {
        "schema_version": 1,
        "readiness_policy": "entity_resolution_merge_preview_readiness_gate",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "inputs": {
            "merged_event_preview": str(preview_path) if preview_path else None,
        },
        "merge_preview_count": len(previews),
        "missing_event_id_count": merged_event_preview.get("missing_event_id_count", 0),
        "conflict_counts": dict(sorted(conflict_counts.items())),
        "blocking_conflict_item_count": len(blocking_items),
        "review_conflict_item_count": len(review_items),
        "ready_for_full_shadow_preview": ready_for_full_shadow_preview,
        "ready_for_canonical_apply": False,
        "canonical_apply_blocker": "full_shadow_preview_and_final_merge_body_policy_required",
        "blocking_items": blocking_items,
        "review_items": review_items,
        "blocking_items_sample": blocking_items[:50],
        "review_items_sample": review_items[:50],
        "notes": [
            "This gate only decides whether a full shadow-corpus preview is low-risk enough to run.",
            "Canonical apply remains blocked until final merge-body/provenance policy exists.",
            "Coordinate/text conflicts may be acceptable duplicates but should remain visible for review.",
        ],
    }


def material_blocking_fields(item: dict[str, Any], field_conflicts: dict[str, Any]) -> list[str]:
    fields = sorted(field for field in field_conflicts if field in BLOCKING_CONFLICT_FIELDS)
    coordinate_km = coordinate_distance_km(item)
    if any(field in field_conflicts for field in ["lat", "lon"]) and (coordinate_km is None or coordinate_km > 10):
        fields.append("coordinate_distance_over_10km" if coordinate_km is not None else "coordinate_conflict_without_distance")
    if "location_raw" in field_conflicts and not location_conflict_is_minor(item, coordinate_km):
        fields.append("location_raw")
    return sorted(set(fields))


def location_conflict_is_minor(item: dict[str, Any], coordinate_km: float | None) -> bool:
    if coordinate_km is not None and coordinate_km <= 10:
        return True
    locations = [
        str(event.get("location_raw") or "")
        for event in item.get("source_event_summaries") or []
        if isinstance(event, dict) and event.get("location_raw")
    ]
    if len(locations) < 2:
        return True
    token_sets = [set(re.findall(r"[a-z0-9]+", value.lower())) for value in locations]
    token_sets = [tokens for tokens in token_sets if tokens]
    if len(token_sets) < 2:
        return True
    base = token_sets[0]
    for tokens in token_sets[1:]:
        overlap = len(base & tokens) / max(1, len(base | tokens))
        if overlap < 0.6:
            return False
    return True


def coordinate_distance_km(item: dict[str, Any]) -> float | None:
    points = []
    for event in item.get("source_event_summaries") or []:
        if not isinstance(event, dict):
            continue
        lat = numeric(event.get("lat"))
        lon = numeric(event.get("lon"))
        if lat is not None and lon is not None:
            points.append((lat, lon))
    if len(points) < 2:
        return None
    max_distance = 0.0
    for index, left in enumerate(points):
        for right in points[index + 1 :]:
            max_distance = max(max_distance, haversine_km(left, right))
    return max_distance


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


def readiness_item(item: dict[str, Any], fields: list[str], reason: str) -> dict[str, Any]:
    return {
        "patch_id": item.get("patch_id"),
        "review_item_id": item.get("review_item_id"),
        "effect_id": item.get("effect_id"),
        "reason": reason,
        "fields": fields,
        "projected_event_reduction": item.get("projected_event_reduction"),
    }


def validate_preview_safety(preview: dict[str, Any]) -> None:
    errors: list[str] = []
    if preview.get("preview_policy") != "entity_resolution_compact_merged_event_preview_only":
        errors.append("preview_policy must be 'entity_resolution_compact_merged_event_preview_only'")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "auto_merge_performed"):
        if preview.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError(f"merged-event preview is not safe for readiness checking: {'; '.join(errors)}")


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
    parser.add_argument("--merged-event-preview", type=Path, default=DEFAULT_PREVIEW)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    preview = read_json(args.merged_event_preview)
    report = check_entity_resolution_merge_readiness(merged_event_preview=preview, preview_path=args.merged_event_preview)
    write_json(args.output, report)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "readiness_policy": report["readiness_policy"],
                "merge_preview_count": report["merge_preview_count"],
                "blocking_conflict_item_count": report["blocking_conflict_item_count"],
                "review_conflict_item_count": report["review_conflict_item_count"],
                "ready_for_full_shadow_preview": report["ready_for_full_shadow_preview"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
