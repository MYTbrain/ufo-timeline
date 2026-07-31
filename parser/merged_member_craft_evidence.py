"""Preserve duplicate-member craft evidence without changing direct inference.

This module intentionally produces candidate metadata only. Promotion into
``craft_type_inferred`` must happen in a later, explicitly reviewed web/canonical
enrichment step.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, is_dataclass
from typing import Any, Iterable, Mapping

from .craft_types import infer_event_craft_type


NON_PROMOTABLE_CRAFT_TYPES = {
    "unknown",
    "light",
    "conventional_or_explained",
    "non_ufo_context",
}
CONFIDENCE_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3}
PROMOTABLE_STATUS = "promotable"


def build_merged_member_craft_evidence(
    primary: Any,
    group_records: Iterable[Any],
) -> dict[str, Any] | None:
    """Return compact merged-member craft evidence for a dedupe group.

    The returned payload is provenance metadata only. It never overwrites the
    primary/canonical record's direct craft inference.
    """

    records = list(group_records)
    if len(records) < 2:
        return None

    primary_dict = _record_to_dict(primary)
    primary_id = _record_id(primary_dict)
    primary_inference = infer_event_craft_type(primary_dict)
    primary_type = str(primary_inference.get("craft_type_inferred") or "unknown")

    member_evidence = [
        evidence
        for record in records
        if (evidence := _member_evidence(record, primary_id=primary_id)) is not None
    ]
    if not member_evidence:
        return None

    craft_counts = Counter(item["craft_type_inferred"] for item in member_evidence)
    high_confidence_types = {
        item["craft_type_inferred"]
        for item in member_evidence
        if item.get("craft_type_confidence") == "high"
    }
    top_type, top_count = craft_counts.most_common(1)[0]
    top_items = [item for item in member_evidence if item["craft_type_inferred"] == top_type]
    conflict = len(craft_counts) > 1
    high_confidence_conflict = len(high_confidence_types) > 1
    blocked_prosaic = top_type in {"conventional_or_explained", "non_ufo_context"}
    blocked_weak = top_type in {"unknown", "light"} or all(
        CONFIDENCE_RANK.get(str(item.get("craft_type_confidence") or "none"), 0) < CONFIDENCE_RANK["medium"]
        for item in top_items
    )

    if primary_type != "unknown":
        status = "blocked_direct_canonical_evidence_exists"
    elif high_confidence_conflict:
        status = "blocked_conflict"
    elif blocked_prosaic:
        status = "blocked_prosaic_or_conventional"
    elif blocked_weak:
        status = "blocked_weak_evidence"
    elif conflict and top_count <= 1:
        status = "blocked_conflict"
    else:
        status = PROMOTABLE_STATUS

    return {
        "merged_member_craft_type_candidate": top_type,
        "merged_member_craft_type_confidence": _candidate_confidence(top_items, conflict=conflict, status=status),
        "merged_member_craft_type_source": "duplicate_member_evidence",
        "merged_member_craft_type_evidence": _evidence_summary(top_items),
        "merged_member_craft_type_member_ids": [item["canonical_input_id"] for item in top_items],
        "merged_member_craft_type_member_sources": sorted(
            {
                str(item.get("source_name") or "unknown")
                for item in top_items
            }
        ),
        "merged_member_craft_type_conflict": conflict,
        "merged_member_craft_type_basis": {
            "member_evidence_count": len(member_evidence),
            "candidate_member_count": top_count,
            "candidate_distribution": dict(sorted(craft_counts.items())),
            "high_confidence_conflict": high_confidence_conflict,
            "primary_craft_type_inferred": primary_type,
            "primary_craft_type_confidence": primary_inference.get("craft_type_confidence") or "none",
        },
        "merged_member_craft_type_status": status,
    }


def _member_evidence(record: Any, *, primary_id: str | None) -> dict[str, Any] | None:
    record_dict = _record_to_dict(record)
    record_id = _record_id(record_dict)
    if record_id and primary_id and record_id == primary_id:
        return None

    inference = infer_event_craft_type(record_dict)
    craft_type = str(inference.get("craft_type_inferred") or "unknown")
    confidence = str(inference.get("craft_type_confidence") or "none")
    if craft_type in NON_PROMOTABLE_CRAFT_TYPES:
        if craft_type not in {"conventional_or_explained", "non_ufo_context", "light"}:
            return None
    elif CONFIDENCE_RANK.get(confidence, 0) < CONFIDENCE_RANK["medium"]:
        return None

    return {
        "canonical_input_id": record_id,
        "source_name": record_dict.get("source_name"),
        "source_file": record_dict.get("source_file"),
        "source_row_number": record_dict.get("source_row_number"),
        "source_native_id": record_dict.get("source_native_id"),
        "craft_type_inferred": craft_type,
        "craft_type_confidence": confidence,
        "craft_type_source": inference.get("craft_type_source"),
        "craft_type_source_rule": inference.get("craft_type_source_rule"),
        "craft_type_evidence": inference.get("craft_type_evidence") or inference.get("craft_type_reason"),
        "shape_raw": record_dict.get("shape_raw"),
        "shape_normalized": record_dict.get("shape_normalized"),
        "type_raw": record_dict.get("type_raw"),
        "type_normalized": record_dict.get("type_normalized"),
        "description": _sample_text(record_dict.get("description") or record_dict.get("summary")),
    }


def _candidate_confidence(items: list[dict[str, Any]], *, conflict: bool, status: str) -> str:
    best_rank = max(CONFIDENCE_RANK.get(str(item.get("craft_type_confidence") or "none"), 0) for item in items)
    if status == "blocked_conflict":
        return "none"
    if status == "blocked_prosaic_or_conventional":
        return "none"
    if status == "blocked_weak_evidence":
        return "low"
    if conflict:
        return "medium"
    if best_rank >= CONFIDENCE_RANK["high"]:
        return "high"
    if best_rank >= CONFIDENCE_RANK["medium"]:
        return "medium"
    return "low"


def _evidence_summary(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary = []
    for item in items[:5]:
        summary.append(
            {
                "canonical_input_id": item.get("canonical_input_id"),
                "source_name": item.get("source_name"),
                "source_file": item.get("source_file"),
                "source_row_number": item.get("source_row_number"),
                "source_native_id": item.get("source_native_id"),
                "craft_type_inferred": item.get("craft_type_inferred"),
                "craft_type_confidence": item.get("craft_type_confidence"),
                "craft_type_source": item.get("craft_type_source"),
                "craft_type_source_rule": item.get("craft_type_source_rule"),
                "craft_type_evidence": item.get("craft_type_evidence"),
                "shape_raw": item.get("shape_raw"),
                "shape_normalized": item.get("shape_normalized"),
                "type_raw": item.get("type_raw"),
                "type_normalized": item.get("type_normalized"),
                "description": item.get("description"),
            }
        )
    return summary


def _record_to_dict(record: Any) -> dict[str, Any]:
    if isinstance(record, Mapping):
        return dict(record)
    if hasattr(record, "to_json_dict"):
        return dict(record.to_json_dict())
    if is_dataclass(record):
        return asdict(record)
    raise TypeError(f"Unsupported record type for merged-member craft evidence: {type(record)!r}")


def _record_id(record: Mapping[str, Any]) -> str | None:
    value = record.get("canonical_input_id")
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _sample_text(value: Any, *, limit: int = 240) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    if not text:
        return None
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."
