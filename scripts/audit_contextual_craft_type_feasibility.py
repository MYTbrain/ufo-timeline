"""Read-only feasibility audit for contextual craft-type inference.

The audit estimates whether unresolved craft-type Unknown rows could receive a
separate contextual candidate from nearby, time-related direct morphology
donors. It does not change direct craft_type_inferred values or generated web
artifacts.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
import json
import math
from pathlib import Path
import re
import sys
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from parser.craft_types import infer_event_craft_type, normalize_text
from parser.taxonomy import display_type_for_web_event, visual_type_group_for_web_event


DEFAULT_INPUT = Path("data/canonical_full_maximal_v3_rehydrated_jurisdiction_repair/deduped_events.jsonl")
DEFAULT_OUTPUT_MD = Path("data/reports/contextual_craft_type_inference_feasibility.md")
DEFAULT_OUTPUT_JSON = Path("data/reports/contextual_craft_type_inference_feasibility.json")

MAX_DONOR_DISTANCE_KM = 100.0
GRID_DEGREES = 1.0
TOP_LIMIT = 25
SAMPLE_LIMIT = 12
GENERIC_DESC_TERMS = {
    "object",
    "objects",
    "thing",
    "things",
    "light",
    "lights",
    "bright",
    "strange",
    "sky",
    "seen",
    "saw",
    "ufo",
    "uap",
    "craft",
}
DIRECT_DONOR_EXCLUDED_TYPES = {
    "unknown",
    "light",
    "fireball_meteor_like",
    "formation",
    "conventional_or_explained",
    "non_ufo_context",
}

COLOR_TERMS = {
    "red",
    "orange",
    "yellow",
    "green",
    "blue",
    "white",
    "black",
    "silver",
    "gold",
    "amber",
    "cyan",
    "purple",
    "pink",
}
BEHAVIOR_TERMS = {
    "hovering",
    "hovered",
    "silent",
    "accelerated",
    "acceleration",
    "formation",
    "pulsing",
    "pulsed",
    "zigzag",
    "zig-zag",
    "trail",
    "chasing",
    "pacing",
    "radar",
    "em",
    "electromagnetic",
    "stationary",
    "landed",
    "landing",
    "descended",
    "ascended",
}
MORPHOLOGY_TERMS = {
    "disc",
    "disk",
    "saucer",
    "triangle",
    "triangular",
    "sphere",
    "orb",
    "cigar",
    "cylinder",
    "oval",
    "egg",
    "chevron",
    "boomerang",
    "rectangle",
    "box",
    "cone",
    "diamond",
    "teardrop",
    "dumbbell",
    "barbell",
}
TOKEN_RE = re.compile(r"[a-z][a-z0-9_-]{2,}", re.I)
TIME_RE = re.compile(r"\b(?P<hour>[01]?\d|2[0-3])[:.]?(?P<minute>[0-5]\d)?\s*(?P<ampm>a\.?m\.?|p\.?m\.?|am|pm)?\b", re.I)


@dataclass(frozen=True)
class EventRecord:
    event: dict[str, Any]
    event_id: str
    source_name: str
    date_ordinal: int | None
    date_iso: str
    local_minutes: int | None
    daypart: str | None
    lat: float | None
    lon: float | None
    city: str
    state: str
    country: str
    craft_type: str
    craft_confidence: str
    craft_source: str
    direct_evidence_quality: str
    text_tokens: frozenset[str]
    color_terms: frozenset[str]
    behavior_terms: frozenset[str]
    morphology_terms: frozenset[str]
    duplicate_family: str


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path} line {line_number}: invalid JSON: {exc}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"{path} line {line_number}: expected object")
            yield payload


def is_app_facing_unknown(event: dict[str, Any]) -> bool:
    if display_type_for_web_event(event) is None:
        return True
    return visual_type_group_for_web_event(event) == "Other / unknown"


def parse_date_ordinal(value: Any) -> int | None:
    text = normalize_text(value)
    if not text or len(text) < 10:
        return None
    try:
        return date.fromisoformat(text[:10]).toordinal()
    except ValueError:
        return None


def parse_local_minutes(event: dict[str, Any]) -> int | None:
    candidates = [
        event.get("time_raw"),
        event.get("date_raw"),
        event.get("date_iso"),
        event.get("sort_date_iso"),
    ]
    raw_fields = event.get("raw_fields")
    if isinstance(raw_fields, dict):
        for key in ("TIME", "Time", "Occurred", "Occurred Date / Time", "Date / Time", "DATE"):
            candidates.append(raw_fields.get(key))
    for value in candidates:
        text = normalize_text(value)
        if not text:
            continue
        iso_match = re.search(r"T([01]\d|2[0-3]):([0-5]\d)", text)
        if iso_match:
            return int(iso_match.group(1)) * 60 + int(iso_match.group(2))
        match = TIME_RE.search(text)
        if not match:
            continue
        hour = int(match.group("hour"))
        minute = int(match.group("minute") or 0)
        ampm = normalize_text(match.group("ampm")).lower().replace(".", "")
        if ampm in {"pm", "p"} and hour != 12:
            hour += 12
        elif ampm in {"am", "a"} and hour == 12:
            hour = 0
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return hour * 60 + minute
    return None


def daypart_for_minutes(minutes: int | None) -> str | None:
    if minutes is None:
        return None
    if 300 <= minutes < 720:
        return "morning"
    if 720 <= minutes < 1020:
        return "afternoon"
    if 1020 <= minutes < 1320:
        return "evening"
    return "night"


def number_or_none(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def text_blob(event: dict[str, Any]) -> str:
    parts = [
        event.get("type_raw"),
        event.get("type_normalized"),
        event.get("shape_raw"),
        event.get("shape_normalized"),
        event.get("description"),
        event.get("summary"),
    ]
    raw = event.get("raw_fields")
    if isinstance(raw, dict):
        for key in ("Description", "description", "COMMENTS", "Comments", "Characteristics", "Color", "COLOR", "TYPE", "SHAPE", "HYNEK", "VALLEE"):
            parts.append(raw.get(key))
    return " ".join(normalize_text(value).lower() for value in parts if normalize_text(value))


def token_set(text: str) -> frozenset[str]:
    return frozenset(
        token.lower()
        for token in TOKEN_RE.findall(text)
        if token.lower() not in GENERIC_DESC_TERMS
    )


def source_key(event: dict[str, Any]) -> str:
    return normalize_text(event.get("source_name")).lower() or "unknown"


def event_id(event: dict[str, Any]) -> str:
    return normalize_text(event.get("canonical_event_id") or event.get("event_id"))


def location_key(event: dict[str, Any], key: str) -> str:
    return normalize_text(event.get(key)).lower()


def duplicate_family(event: dict[str, Any]) -> str:
    fingerprint = normalize_text(event.get("duplicate_fingerprint"))
    if fingerprint:
        return fingerprint
    ids = event.get("canonical_input_ids")
    if isinstance(ids, list) and ids:
        return "|".join(normalize_text(value) for value in ids[:3])
    return event_id(event)


def direct_evidence_quality(craft_type: str, confidence: str, source: str) -> str:
    if craft_type and craft_type not in DIRECT_DONOR_EXCLUDED_TYPES and confidence in {"high", "medium"}:
        return "direct_morphology_evidence"
    if craft_type in {"light", "fireball_meteor_like"}:
        return "weak_light_or_object_evidence"
    if craft_type in {"formation", "conventional_or_explained", "non_ufo_context"} or source.startswith("ufocat_"):
        return "metadata_or_context_only"
    return "missing_evidence"


def build_record(event: dict[str, Any]) -> EventRecord:
    inference = infer_event_craft_type(event)
    craft_type = normalize_text(inference.get("craft_type_inferred")) or "unknown"
    confidence = normalize_text(inference.get("craft_type_confidence")) or "none"
    source = normalize_text(inference.get("craft_type_source")) or "none"
    text = text_blob(event)
    tokens = token_set(text)
    return EventRecord(
        event=event,
        event_id=event_id(event),
        source_name=source_key(event),
        date_ordinal=parse_date_ordinal(event.get("sort_date_iso") or event.get("date_iso")),
        date_iso=normalize_text(event.get("date_iso")),
        local_minutes=parse_local_minutes(event),
        daypart=daypart_for_minutes(parse_local_minutes(event)),
        lat=number_or_none(event.get("lat")),
        lon=number_or_none(event.get("lon")),
        city=location_key(event, "city") or parse_location_component(event.get("location_raw"), 0),
        state=location_key(event, "state_province") or parse_location_component(event.get("location_raw"), 1),
        country=location_key(event, "country") or parse_location_component(event.get("location_raw"), -1),
        craft_type=craft_type,
        craft_confidence=confidence,
        craft_source=source,
        direct_evidence_quality=direct_evidence_quality(craft_type, confidence, source),
        text_tokens=tokens,
        color_terms=frozenset(tokens & COLOR_TERMS),
        behavior_terms=frozenset(tokens & BEHAVIOR_TERMS),
        morphology_terms=frozenset(tokens & MORPHOLOGY_TERMS),
        duplicate_family=duplicate_family(event),
    )


def parse_location_component(value: Any, index: int) -> str:
    parts = [normalize_text(part).lower() for part in normalize_text(value).split(",") if normalize_text(part)]
    if not parts:
        return ""
    try:
        return parts[index]
    except IndexError:
        return ""


def grid_cell(lat: float, lon: float) -> tuple[int, int]:
    return (math.floor(lat / GRID_DEGREES), math.floor(lon / GRID_DEGREES))


def neighboring_cells(lat: float, lon: float) -> Iterable[tuple[int, int]]:
    row, col = grid_cell(lat, lon)
    for dr in range(-2, 3):
        for dc in range(-2, 3):
            yield row + dr, col + dc


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def time_category(target: EventRecord, donor: EventRecord) -> tuple[str, int]:
    if target.date_ordinal is None or donor.date_ordinal is None:
        return "unknown_time", 0
    day_delta = abs(target.date_ordinal - donor.date_ordinal)
    if day_delta == 0 and target.local_minutes is not None and donor.local_minutes is not None:
        minute_delta = abs(target.local_minutes - donor.local_minutes)
        minute_delta = min(minute_delta, 1440 - minute_delta)
        if minute_delta <= 15:
            return "exact_near_time", 35
        if minute_delta <= 60:
            return "same_hour", 28
    if day_delta == 0 and target.daypart and target.daypart == donor.daypart:
        return "same_daypart", 18
    if day_delta == 0:
        return "same_calendar_day", 8
    if day_delta <= 2:
        return "near_day_wave", 4
    return "too_far_time", 0


def geographic_category(target: EventRecord, donor: EventRecord) -> tuple[str, int, float | None]:
    if target.lat is not None and target.lon is not None and donor.lat is not None and donor.lon is not None:
        distance = haversine_km(target.lat, target.lon, donor.lat, donor.lon)
        if distance <= 5:
            return "within_5km", 35, distance
        if distance <= 25:
            return "within_25km", 28, distance
        if distance <= 50:
            return "within_50km", 20, distance
        if distance <= MAX_DONOR_DISTANCE_KM:
            return "within_100km", 12, distance
        return "too_far_place", 0, distance
    if target.city and donor.city and target.city == donor.city and target.country == donor.country:
        return "same_city_fallback", 25, None
    if target.state and donor.state and target.state == donor.state and target.country == donor.country:
        return "same_state_fallback", 4, None
    return "unknown_place", 0, None


def plausible_speed_bonus(target: EventRecord, donor: EventRecord, distance_km: float | None) -> tuple[bool, int]:
    if distance_km is None or distance_km < 5:
        return False, 0
    if target.date_ordinal is None or donor.date_ordinal is None:
        return False, 0
    if target.local_minutes is None or donor.local_minutes is None:
        return False, 0
    delta_minutes = abs((target.date_ordinal - donor.date_ordinal) * 1440 + target.local_minutes - donor.local_minutes)
    if delta_minutes <= 0:
        return False, 0
    speed = distance_km / (delta_minutes / 60)
    if 10 <= speed <= 3000:
        return True, 8
    return False, -8


def score_pair(target: EventRecord, donor: EventRecord) -> dict[str, Any] | None:
    if target.event_id == donor.event_id:
        return None
    if target.duplicate_family and target.duplicate_family == donor.duplicate_family:
        return None
    time_label, time_score = time_category(target, donor)
    geo_label, geo_score, distance = geographic_category(target, donor)
    if time_score <= 0 or geo_score <= 0:
        return None
    if time_label == "same_calendar_day" and geo_score < 35:
        return None
    if time_label == "near_day_wave" and geo_score < 28:
        return None
    overlap = target.text_tokens & donor.text_tokens
    morphology_overlap = target.morphology_terms & donor.morphology_terms
    color_overlap = target.color_terms & donor.color_terms
    behavior_overlap = target.behavior_terms & donor.behavior_terms
    description_score = min(12, len(overlap)) + len(color_overlap) * 2 + len(behavior_overlap) * 3 + len(morphology_overlap) * 4
    quality_score = 15 if donor.craft_confidence == "high" else 8
    speed_plausible, speed_score = plausible_speed_bonus(target, donor, distance)
    total = time_score + geo_score + description_score + quality_score + speed_score
    basis = basis_for_pair(time_label, geo_label, bool(description_score), speed_plausible)
    return {
        "donor_event_id": donor.event_id,
        "donor_source_name": donor.source_name,
        "donor_craft_type": donor.craft_type,
        "donor_confidence": donor.craft_confidence,
        "donor_craft_source": donor.craft_source,
        "score": round(total, 2),
        "time_category": time_label,
        "geographic_category": geo_label,
        "distance_km": round(distance, 3) if distance is not None else None,
        "description_overlap_terms": sorted(overlap)[:12],
        "color_overlap_terms": sorted(color_overlap),
        "behavior_overlap_terms": sorted(behavior_overlap),
        "morphology_overlap_terms": sorted(morphology_overlap),
        "path_speed_plausible": speed_plausible,
        "basis": basis,
    }


def basis_for_pair(time_label: str, geo_label: str, has_description_similarity: bool, speed_plausible: bool) -> str:
    bases: list[str] = []
    if time_label in {"exact_near_time", "same_hour"} and geo_label in {"within_5km", "within_25km", "same_city_fallback"}:
        bases.append("near_time_near_place")
    if time_label in {"same_daypart", "same_calendar_day", "near_day_wave"} and geo_label in {"within_5km", "within_25km", "same_city_fallback"}:
        bases.append("same_local_wave")
    if speed_plausible:
        bases.append("path_aligned_sequence")
    if has_description_similarity:
        bases.append("description_similarity")
    if not bases:
        bases.append("near_time_near_place")
    return bases[0] if len(bases) == 1 else "mixed"


def summarize_candidate(target: EventRecord, pair_scores: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not pair_scores:
        return None
    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for pair in pair_scores:
        by_type[pair["donor_craft_type"]].append(pair)
    type_summaries: list[tuple[str, float, list[dict[str, Any]]]] = []
    for craft_type, pairs in by_type.items():
        sorted_pairs = sorted(pairs, key=lambda row: row["score"], reverse=True)
        score = min(100.0, sum(row["score"] for row in sorted_pairs[:3]) / max(1, min(3, len(sorted_pairs))) + min(18, len(sorted_pairs) * 4))
        source_count = len({row["donor_source_name"] for row in pairs})
        if source_count >= 2:
            score += 6
        type_summaries.append((craft_type, score, sorted_pairs))
    type_summaries.sort(key=lambda row: row[1], reverse=True)
    best_type, best_score, best_pairs = type_summaries[0]
    conflicting_types = [
        craft_type
        for craft_type, score, _pairs in type_summaries[1:]
        if score >= max(45, best_score - 15)
    ]
    conflict_count = len(conflicting_types)
    if conflict_count:
        best_score -= min(25, conflict_count * 10)
    if best_score < 55:
        return None
    confidence = "low"
    if best_score >= 92 and len(best_pairs) >= 2 and conflict_count == 0:
        confidence = "high"
    elif best_score >= 75 and conflict_count <= 1:
        confidence = "medium"
    bases = Counter(row["basis"] for row in best_pairs)
    basis = bases.most_common(1)[0][0] if len(bases) == 1 else "mixed"
    if conflict_count:
        basis = "mixed"
    evidence_ids = [row["donor_event_id"] for row in best_pairs[:8]]
    false_positive_risk = "low" if confidence == "high" else "medium" if confidence == "medium" else "high"
    if conflict_count:
        false_positive_risk = "high"
    return {
        "canonical_event_id": target.event_id,
        "source_name": target.source_name,
        "current_craft_type_inferred": "unknown",
        "direct_evidence_quality": target.direct_evidence_quality,
        "contextual_craft_type_candidate": best_type,
        "contextual_confidence": confidence,
        "contextual_score": round(best_score, 2),
        "contextual_basis": basis,
        "contextual_neighbor_count": len(pair_scores),
        "contextual_direct_morphology_donor_count": len(best_pairs),
        "contextual_conflicting_type_count": conflict_count,
        "contextual_conflicting_types": conflicting_types[:8],
        "contextual_evidence_event_ids": evidence_ids,
        "false_positive_risk": false_positive_risk,
        "basis_detail": {
            "top_pair_scores": best_pairs[:5],
            "candidate_type_scores": [
                {"craft_type": craft_type, "score": round(score, 2), "donor_count": len(pairs)}
                for craft_type, score, pairs in type_summaries[:8]
            ],
        },
    }


def build_indexes(records: list[EventRecord]) -> tuple[dict[tuple[int, tuple[int, int]], list[EventRecord]], dict[tuple[int, str, str, str], list[EventRecord]]]:
    spatial: dict[tuple[int, tuple[int, int]], list[EventRecord]] = defaultdict(list)
    place: dict[tuple[int, str, str, str], list[EventRecord]] = defaultdict(list)
    for record in records:
        if record.direct_evidence_quality != "direct_morphology_evidence" or record.date_ordinal is None:
            continue
        if record.lat is not None and record.lon is not None:
            spatial[(record.date_ordinal, grid_cell(record.lat, record.lon))].append(record)
        if record.city or record.state:
            place[(record.date_ordinal, record.city, record.state, record.country)].append(record)
    return spatial, place


def nearby_donors(target: EventRecord, spatial: dict[tuple[int, tuple[int, int]], list[EventRecord]], place: dict[tuple[int, str, str, str], list[EventRecord]]) -> list[EventRecord]:
    if target.date_ordinal is None:
        return []
    donors: dict[str, EventRecord] = {}
    for day in range(target.date_ordinal - 2, target.date_ordinal + 3):
        if target.lat is not None and target.lon is not None:
            for cell in neighboring_cells(target.lat, target.lon):
                for donor in spatial.get((day, cell), []):
                    donors[donor.event_id] = donor
        if target.city or target.state:
            for donor in place.get((day, target.city, target.state, target.country), []):
                donors[donor.event_id] = donor
    return list(donors.values())


def cluster_key_for_candidate(candidate: dict[str, Any], records_by_id: dict[str, EventRecord]) -> str:
    record = records_by_id.get(candidate["canonical_event_id"])
    if not record:
        return f"{candidate['contextual_craft_type_candidate']}|unknown"
    if record.lat is not None and record.lon is not None:
        cell = grid_cell(record.lat, record.lon)
        return f"{candidate['contextual_craft_type_candidate']}|{record.date_iso[:10]}|cell:{cell[0]}:{cell[1]}"
    return f"{candidate['contextual_craft_type_candidate']}|{record.date_iso[:10]}|{record.city}|{record.state}|{record.country}"


def sample_event(record: EventRecord) -> dict[str, Any]:
    return {
        "canonical_event_id": record.event_id,
        "source_name": record.source_name,
        "date_iso": record.date_iso,
        "location_raw": record.event.get("location_raw"),
        "lat": record.lat,
        "lon": record.lon,
        "type_raw": record.event.get("type_raw"),
        "shape_raw": record.event.get("shape_raw"),
        "description_excerpt": normalize_text(record.event.get("description") or record.event.get("summary"))[:260],
        "craft_type_inferred": record.craft_type,
        "craft_type_confidence": record.craft_confidence,
        "craft_type_source": record.craft_source,
        "direct_evidence_quality": record.direct_evidence_quality,
    }


def build_report(input_path: Path, *, limit: int | None = None) -> dict[str, Any]:
    totals = Counter()
    evidence_tier_counts = Counter()
    unresolved_tier_counts = Counter()
    source_unresolved_counts = Counter()
    source_candidate_counts = Counter()
    records: list[EventRecord] = []
    unresolved_unknowns: list[EventRecord] = []
    direct_donors: list[EventRecord] = []

    for index, event in enumerate(iter_jsonl(input_path), start=1):
        if limit is not None and index > limit:
            break
        record = build_record(event)
        records.append(record)
        totals["events_scanned"] += 1
        evidence_tier_counts[record.direct_evidence_quality] += 1
        if record.direct_evidence_quality == "direct_morphology_evidence":
            direct_donors.append(record)
        if is_app_facing_unknown(event) and record.craft_type == "unknown":
            unresolved_unknowns.append(record)
            source_unresolved_counts[record.source_name] += 1
            unresolved_tier_counts[record.direct_evidence_quality] += 1

    spatial, place = build_indexes(direct_donors)
    candidates: list[dict[str, Any]] = []
    no_neighbor_count = 0
    mixed_conflict_count = 0
    examples_by_confidence: dict[str, list[dict[str, Any]]] = defaultdict(list)
    false_positive_examples: list[dict[str, Any]] = []
    records_by_id = {record.event_id: record for record in records if record.event_id}

    for target in unresolved_unknowns:
        pair_scores: list[dict[str, Any]] = []
        for donor in nearby_donors(target, spatial, place):
            pair = score_pair(target, donor)
            if pair:
                pair_scores.append(pair)
        candidate = summarize_candidate(target, pair_scores)
        if not candidate:
            no_neighbor_count += 1
            continue
        candidates.append(candidate)
        source_candidate_counts[target.source_name] += 1
        if candidate["contextual_conflicting_type_count"]:
            mixed_conflict_count += 1
            if len(false_positive_examples) < SAMPLE_LIMIT:
                false_positive_examples.append(candidate)
        if len(examples_by_confidence[candidate["contextual_confidence"]]) < SAMPLE_LIMIT:
            examples_by_confidence[candidate["contextual_confidence"]].append(candidate)

    confidence_counts = Counter(candidate["contextual_confidence"] for candidate in candidates)
    candidate_type_counts = Counter(candidate["contextual_craft_type_candidate"] for candidate in candidates)
    basis_counts = Counter(candidate["contextual_basis"] for candidate in candidates)
    cluster_counter: Counter[str] = Counter()
    cluster_samples: dict[str, list[str]] = defaultdict(list)
    for candidate in candidates:
        key = cluster_key_for_candidate(candidate, records_by_id)
        cluster_counter[key] += 1
        if len(cluster_samples[key]) < 8:
            cluster_samples[key].append(candidate["canonical_event_id"])

    top_clusters = [
        {
            "cluster_key": key,
            "unknowns_contextualized": count,
            "example_contextualized_event_ids": cluster_samples[key],
        }
        for key, count in cluster_counter.most_common(TOP_LIMIT)
    ]

    safe_ceiling = int(confidence_counts["high"] + confidence_counts["medium"])
    report = {
        "schema_version": 1,
        "analysis_policy": "read_only_contextual_feasibility_no_parser_or_artifact_changes",
        "canonical_outputs_mutated": False,
        "direct_craft_type_inferred_mutated": False,
        "inputs": {
            "events_jsonl": str(input_path),
            "limit": limit,
        },
        "method": {
            "donor_rule": "Only records with direct_morphology_evidence donate. Light-only, formation-only, prosaic/context-only, and missing-evidence records cannot donate.",
            "same_day_guardrail": "Same calendar day alone is rejected unless paired with very close geography or stronger time/path/description evidence.",
            "max_donor_distance_km": MAX_DONOR_DISTANCE_KM,
            "confidence_thresholds": {
                "high": "score >= 92, at least two same-type direct donors, no conflict",
                "medium": "score >= 75, at most one near-conflicting morphology type",
                "low": "score >= 55",
            },
        },
        "summary": {
            "events_scanned": totals["events_scanned"],
            "total_unresolved_unknowns_evaluated": len(unresolved_unknowns),
            "direct_evidence_quality_counts_all_events": dict(evidence_tier_counts.most_common()),
            "direct_evidence_quality_counts_unresolved_unknowns": dict(unresolved_tier_counts.most_common()),
            "direct_morphology_donor_count": len(direct_donors),
            "high_confidence_contextual_candidate_count": int(confidence_counts["high"]),
            "medium_confidence_contextual_candidate_count": int(confidence_counts["medium"]),
            "low_confidence_contextual_candidate_count": int(confidence_counts["low"]),
            "conflicting_or_mixed_contextual_evidence_count": mixed_conflict_count,
            "no_useful_contextual_neighbors_count": no_neighbor_count,
            "counts_by_source": dict(source_unresolved_counts.most_common()),
            "contextual_candidate_counts_by_source": dict(source_candidate_counts.most_common()),
            "candidate_contextual_craft_type_distribution": dict(candidate_type_counts.most_common()),
            "contextual_basis_counts": dict(basis_counts.most_common()),
            "estimated_safe_contextual_enrichment_ceiling": safe_ceiling,
        },
        "contextual_candidates": candidates,
        "top_event_clusters_or_waves_by_unknowns_contextualized": top_clusters,
        "examples": {
            "high_confidence_clusters": examples_by_confidence.get("high", []),
            "medium_confidence_clusters": examples_by_confidence.get("medium", []),
            "low_confidence_clusters": examples_by_confidence.get("low", []),
            "false_positive_or_conflict_cases": false_positive_examples,
            "direct_donor_examples": [sample_event(record) for record in direct_donors[:SAMPLE_LIMIT]],
            "unresolved_unknown_examples": [sample_event(record) for record in unresolved_unknowns[:SAMPLE_LIMIT]],
        },
        "recommended_thresholds_for_future_implementation": [
            "Store contextual candidates in separate fields; never overwrite direct craft_type_inferred.",
            "Require at least one direct_morphology_evidence donor within 25km plus exact/near-time or same-hour evidence for medium confidence.",
            "Require at least two same-type direct donors and no conflicting direct morphology type for high confidence.",
            "Permit same-local-wave candidates only as low confidence unless there are multiple independent sources or path-aligned sequence evidence.",
            "Reject same-calendar-day-only propagation unless the points are within 5km and there is additional description or behavior similarity.",
            "Do not let light-only, formation-only, conventional/prosaic, or metadata-only records donate craft type.",
        ],
        "fields_needed_for_future_candidate_layer": [
            "contextual_craft_type_candidate",
            "contextual_craft_type_confidence",
            "contextual_craft_type_score",
            "contextual_craft_type_basis",
            "contextual_craft_type_donor_event_ids",
            "contextual_craft_type_conflict_count",
            "contextual_craft_type_false_positive_risk",
        ],
        "ui_recommendation": "Expose as a separate optional Contextual Craft Type layer or color mode, not as a replacement for direct Craft Type or raw Type filters.",
        "trace_path_reuse_note": "Existing same-day trace/path ordering can help propose path-aligned sequences later, but this audit does not reuse trace geometry directly because direct donor quality and conflict checks must remain separate from visual trace generation.",
    }
    return report


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    summary = report["summary"]
    lines: list[str] = [
        "# Contextual Craft-Type Inference Feasibility Audit",
        "",
        "Read-only audit. No parser code, canonical web artifacts, static bundles, Cloudflare/R2 artifacts, preview, deployment, or direct craft type values were changed.",
        "",
        "## Method Guardrails",
        "",
        f"- Donor rule: {report['method']['donor_rule']}",
        f"- Same-day guardrail: {report['method']['same_day_guardrail']}",
        f"- Max donor distance: `{report['method']['max_donor_distance_km']} km`",
        "",
        "## Summary",
        "",
        f"- Events scanned: `{summary['events_scanned']:,}`",
        f"- Total unresolved unknowns evaluated: `{summary['total_unresolved_unknowns_evaluated']:,}`",
        f"- Direct morphology donors available: `{summary['direct_morphology_donor_count']:,}`",
        f"- High-confidence contextual candidates: `{summary['high_confidence_contextual_candidate_count']:,}`",
        f"- Medium-confidence contextual candidates: `{summary['medium_confidence_contextual_candidate_count']:,}`",
        f"- Low-confidence contextual candidates: `{summary['low_confidence_contextual_candidate_count']:,}`",
        f"- Conflicting/mixed contextual evidence: `{summary['conflicting_or_mixed_contextual_evidence_count']:,}`",
        f"- No useful contextual neighbors: `{summary['no_useful_contextual_neighbors_count']:,}`",
        f"- Estimated safe contextual-enrichment ceiling: `{summary['estimated_safe_contextual_enrichment_ceiling']:,}`",
        "",
        "## Direct Evidence-Quality Tier Counts",
        "",
        "### All Events",
        "",
    ]
    for key, count in summary["direct_evidence_quality_counts_all_events"].items():
        lines.append(f"- `{key}`: `{count:,}`")
    lines.extend(["", "### Unresolved Unknowns", ""])
    for key, count in summary["direct_evidence_quality_counts_unresolved_unknowns"].items():
        lines.append(f"- `{key}`: `{count:,}`")

    lines.extend(["", "## Counts By Source", ""])
    for source, count in summary["counts_by_source"].items():
        candidate_count = summary["contextual_candidate_counts_by_source"].get(source, 0)
        lines.append(f"- `{source}`: `{count:,}` unresolved; `{candidate_count:,}` contextual candidates")

    lines.extend(["", "## Candidate Contextual Craft-Type Distribution", ""])
    for craft_type, count in summary["candidate_contextual_craft_type_distribution"].items():
        lines.append(f"- `{craft_type}`: `{count:,}`")

    lines.extend(["", "## Contextual Basis Counts", ""])
    for basis, count in summary["contextual_basis_counts"].items():
        lines.append(f"- `{basis}`: `{count:,}`")

    lines.extend(["", "## Top Event Clusters/Waves By Unknowns Contextualized", ""])
    lines.append("| Rank | Cluster Key | Unknowns | Example Event IDs |")
    lines.append("|---:|---|---:|---|")
    for index, cluster in enumerate(report["top_event_clusters_or_waves_by_unknowns_contextualized"][:TOP_LIMIT], start=1):
        examples = ", ".join(f"`{item}`" for item in cluster["example_contextualized_event_ids"][:5])
        lines.append(f"| {index} | `{cluster['cluster_key']}` | `{cluster['unknowns_contextualized']:,}` | {examples} |")

    for section_title, key in (
        ("High-Confidence Examples", "high_confidence_clusters"),
        ("Medium-Confidence Examples", "medium_confidence_clusters"),
        ("False-Positive / Conflict Examples", "false_positive_or_conflict_cases"),
    ):
        lines.extend(["", f"## {section_title}", ""])
        for item in report["examples"].get(key, [])[:8]:
            lines.append(
                "- "
                f"`{item['canonical_event_id']}` source `{item['source_name']}` -> "
                f"`{item['contextual_craft_type_candidate']}` `{item['contextual_confidence']}` "
                f"score `{item['contextual_score']}`; basis `{item['contextual_basis']}`; "
                f"donors `{item['contextual_direct_morphology_donor_count']}`; "
                f"conflicts `{item['contextual_conflicting_type_count']}`"
            )

    lines.extend(["", "## Recommended Thresholds For Future Implementation", ""])
    for item in report["recommended_thresholds_for_future_implementation"]:
        lines.append(f"- {item}")

    lines.extend(["", "## Recommendation", ""])
    lines.append("- Contextual craft inference is worth prototyping only as a separate candidate layer, not as a direct craft type replacement.")
    lines.append("- The safe implementation ceiling from this audit is the high+medium candidate count; low-confidence candidates should remain review/display-only.")
    lines.append("- Existing same-day traces may help future path-alignment checks, but direct donor quality and conflict checks should stay independent.")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(args.input, limit=args.limit)
    write_json(args.output_json, report)
    write_markdown(args.output_md, report)
    print(json.dumps({
        "ok": True,
        "outputs": {
            "markdown": str(args.output_md),
            "json": str(args.output_json),
        },
        "summary": report["summary"],
    }, indent=2))


if __name__ == "__main__":
    main()
