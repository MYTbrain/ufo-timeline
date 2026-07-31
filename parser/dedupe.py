"""Canonical dedupe helpers for imported UFO source records.

The default strategy remains exact-only for compatibility with older tests and
smoke builds. Production builds can opt into ``aggressive_v1`` to auto-merge
high-volume duplicate families that are too common to leave as review-only.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
import re
from typing import Any, Iterable

from .canonical_schema import (
    CanonicalInputRecord,
    build_location_text,
    canonical_duplicate_fingerprint,
    clean_text,
    normalize_key,
    stable_hash,
)
from .merged_member_craft_evidence import build_merged_member_craft_evidence

DEFAULT_DUPLICATE_CANDIDATE_LIMIT = 5_000
MIN_DUPLICATE_CANDIDATE_SCORE = 0.82
MIN_SOURCE_TEXT_SIMILARITY = 0.62
STRONG_DATE_PRECISIONS = {"day", "exact_day"}
DEDUPE_STRATEGY_EXACT = "exact_canonical_fingerprint"
DEDUPE_STRATEGY_AGGRESSIVE_V1 = "aggressive_v1"
DEDUPE_STRATEGY_MAXIMAL_V1 = "maximal_v1"
DEDUPE_STRATEGY_MAXIMAL_V2 = "maximal_v2"
DEDUPE_STRATEGY_MAXIMAL_V3 = "maximal_v3"
SUPPORTED_DEDUPE_STRATEGIES = {
    DEDUPE_STRATEGY_EXACT,
    DEDUPE_STRATEGY_AGGRESSIVE_V1,
    DEDUPE_STRATEGY_MAXIMAL_V1,
    DEDUPE_STRATEGY_MAXIMAL_V2,
    DEDUPE_STRATEGY_MAXIMAL_V3,
}
TRUSTED_EXACT_COORDINATE_SOURCES = {
    "raw latlong",
    "raw_latlong",
    "source coordinates",
    "source_coordinates",
    "location coordinates",
    "location_coordinates",
}
GENERIC_NATIVE_IDS = {"none", "null", "unknown", "n a", "na", "000", "999"}
GENERIC_TYPE_KEYS = {"", "unknown", "other", "sighting", "ufo", "nuforc", "ufodna", "nicap", "brazilgov"}
GENERIC_LOCATION_COMPONENTS = {"", "unknown", "unresolved", "undisclosed", "undisclosed_location"}

TOKEN_RE = re.compile(r"[a-z0-9]+")
SOURCE_STOP_WORDS = {
    "a",
    "about",
    "above",
    "after",
    "again",
    "all",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "had",
    "has",
    "have",
    "in",
    "into",
    "is",
    "it",
    "near",
    "of",
    "on",
    "or",
    "over",
    "reported",
    "report",
    "saw",
    "see",
    "seen",
    "sighting",
    "the",
    "to",
    "ufo",
    "was",
    "were",
    "with",
    "witness",
    "witnesses",
}

SOURCE_TOKEN_ALIASES = {
    "cylindrical": "cylinder",
    "cylinders": "cylinder",
    "hovered": "hover",
    "hovering": "hover",
    "lights": "light",
    "silently": "silent",
    "triangular": "triangle",
    "triangles": "triangle",
}

LOCATION_TOKEN_ALIASES = {
    "al": "alabama",
    "ak": "alaska",
    "az": "arizona",
    "ar": "arkansas",
    "ca": "california",
    "co": "colorado",
    "ct": "connecticut",
    "de": "delaware",
    "fl": "florida",
    "ga": "georgia",
    "hi": "hawaii",
    "id": "idaho",
    "il": "illinois",
    "in": "indiana",
    "ia": "iowa",
    "ks": "kansas",
    "ky": "kentucky",
    "la": "louisiana",
    "me": "maine",
    "md": "maryland",
    "ma": "massachusetts",
    "mi": "michigan",
    "mn": "minnesota",
    "ms": "mississippi",
    "mo": "missouri",
    "mt": "montana",
    "ne": "nebraska",
    "nv": "nevada",
    "nh": "new_hampshire",
    "nj": "new_jersey",
    "nm": "new_mexico",
    "ny": "new_york",
    "nc": "north_carolina",
    "nd": "north_dakota",
    "oh": "ohio",
    "ok": "oklahoma",
    "or": "oregon",
    "pa": "pennsylvania",
    "ri": "rhode_island",
    "sc": "south_carolina",
    "sd": "south_dakota",
    "tn": "tennessee",
    "tx": "texas",
    "ut": "utah",
    "vt": "vermont",
    "va": "virginia",
    "wa": "washington",
    "wv": "west_virginia",
    "wi": "wisconsin",
    "wy": "wyoming",
    "usa": "usa",
    "us": "usa",
}


@dataclass(frozen=True)
class _CandidateFeatures:
    record: CanonicalInputRecord
    date_key: str | None
    location_key: str
    source_text_key: str
    source_tokens: frozenset[str]
    exact_fingerprint: str | None


class _DisjointSet:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}
        self.rank: dict[str, int] = {}

    def add(self, value: str) -> None:
        if value not in self.parent:
            self.parent[value] = value
            self.rank[value] = 0

    def find(self, value: str) -> str:
        self.add(value)
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        if self.rank[left_root] < self.rank[right_root]:
            left_root, right_root = right_root, left_root
        self.parent[right_root] = left_root
        if self.rank[left_root] == self.rank[right_root]:
            self.rank[left_root] += 1


def build_deduped_events(
    records: Iterable[CanonicalInputRecord],
    *,
    strategy: str = DEDUPE_STRATEGY_EXACT,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if strategy not in SUPPORTED_DEDUPE_STRATEGIES:
        raise ValueError(
            f"Unsupported dedupe strategy {strategy!r}; expected one of {sorted(SUPPORTED_DEDUPE_STRATEGIES)}."
        )
    if strategy in {
        DEDUPE_STRATEGY_AGGRESSIVE_V1,
        DEDUPE_STRATEGY_MAXIMAL_V1,
        DEDUPE_STRATEGY_MAXIMAL_V2,
        DEDUPE_STRATEGY_MAXIMAL_V3,
    }:
        return _build_rule_based_deduped_events(list(records), strategy=strategy)
    return _build_exact_deduped_events(records)


def _build_exact_deduped_events(
    records: Iterable[CanonicalInputRecord],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Group exact canonical duplicates while preserving every source provenance.

    This first pass intentionally avoids fuzzy auto-merging. Records only share a
    deduped event when the conservative duplicate fingerprint is identical.
    """
    groups: dict[str, list[CanonicalInputRecord]] = {}
    for record in records:
        fingerprint = canonical_duplicate_fingerprint(record)
        if fingerprint is None:
            fingerprint = f"single_{record.canonical_input_id}"
        groups.setdefault(fingerprint, []).append(record)

    deduped_events: list[dict[str, Any]] = []
    duplicate_groups: list[dict[str, Any]] = []
    for fingerprint, group_records in sorted(groups.items(), key=lambda item: item[0]):
        primary = _choose_primary_record(group_records)
        canonical_event_id = stable_hash(
            {
                "fingerprint": fingerprint,
                "primary": primary.canonical_input_id,
            },
            prefix="evt_",
            length=24,
        )
        provenance = [asdict(record.provenance()) for record in group_records]
        event = primary.to_json_dict()
        event_update = {
            "canonical_event_id": canonical_event_id,
            "duplicate_fingerprint": fingerprint if not fingerprint.startswith("single_") else None,
            "duplicate_record_count": len(group_records),
            "dedupe_strategy": "exact_canonical_fingerprint" if len(group_records) > 1 else "single_record",
            "source_provenance": provenance,
            "canonical_input_ids": [record.canonical_input_id for record in group_records],
        }
        if merged_craft_evidence := build_merged_member_craft_evidence(primary, group_records):
            event_update.update(merged_craft_evidence)
        event.update(event_update)
        deduped_events.append(event)
        if len(group_records) > 1:
            duplicate_groups.append(
                {
                    "duplicate_group_id": stable_hash(fingerprint, prefix="dupg_", length=24),
                    "canonical_event_id": canonical_event_id,
                    "duplicate_fingerprint": fingerprint,
                    "strategy": "exact_canonical_fingerprint",
                    "confidence": "high",
                    "record_count": len(group_records),
                    "canonical_input_ids": [record.canonical_input_id for record in group_records],
                    "source_provenance": provenance,
                }
            )

    return deduped_events, duplicate_groups


def _build_rule_based_deduped_events(
    records: list[CanonicalInputRecord],
    *,
    strategy: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Apply production rule-based dedupe families with explicit evidence tags.

    This is not a fuzzy text scorer. It only unions records connected by stable
    blocking keys that have strong operational value:
    exact canonical fingerprints, same source/native ID, same exact
    day/location/time, trusted coordinate/time, and same source exact
    day/location/type. The broader same-source day/location family is the
    intentional high-yield step that catches repeated source rows with sparse
    descriptions and inconsistent object classification.
    """
    dsu = _DisjointSet()
    record_by_id = {record.canonical_input_id: record for record in records}
    evidence_by_input_id: dict[str, set[str]] = {record.canonical_input_id: set() for record in records}

    for record in records:
        dsu.add(record.canonical_input_id)

    key_buckets: dict[tuple[str, str], list[str]] = {}
    for record in records:
        for family, key in _rule_based_auto_merge_keys(record, strategy=strategy):
            key_buckets.setdefault((family, key), []).append(record.canonical_input_id)

    if strategy == DEDUPE_STRATEGY_MAXIMAL_V3:
        _add_maximal_v3_group_aware_keys(records, key_buckets)

    for (family, _key), input_ids in sorted(key_buckets.items(), key=lambda item: item[0]):
        if len(input_ids) < 2:
            continue
        ordered_ids = sorted(set(input_ids))
        first_id = ordered_ids[0]
        for input_id in ordered_ids[1:]:
            dsu.union(first_id, input_id)
        for input_id in ordered_ids:
            evidence_by_input_id[input_id].add(family)

    groups: dict[str, list[CanonicalInputRecord]] = {}
    for record in records:
        groups.setdefault(dsu.find(record.canonical_input_id), []).append(record)

    deduped_events: list[dict[str, Any]] = []
    duplicate_groups: list[dict[str, Any]] = []
    for _root, group_records in sorted(groups.items(), key=lambda item: min(record.canonical_input_id for record in item[1])):
        group_records = sorted(group_records, key=lambda record: record.canonical_input_id)
        primary = _choose_primary_record(group_records)
        input_ids = [record.canonical_input_id for record in group_records]
        families = sorted(
            {
                family
                for input_id in input_ids
                for family in evidence_by_input_id.get(input_id, set())
            }
        )
        if len(group_records) == 1:
            dedupe_strategy = "single_record"
            duplicate_fingerprint = None
            confidence = "none"
        elif families == ["exact_canonical_fingerprint"]:
            dedupe_strategy = "exact_canonical_fingerprint"
            duplicate_fingerprint = canonical_duplicate_fingerprint(primary)
            confidence = "high"
        else:
            dedupe_strategy = f"{strategy}_auto_merge"
            duplicate_fingerprint = stable_hash(
                {
                    "strategy": strategy,
                    "families": families,
                    "canonical_input_ids": input_ids,
                },
                prefix="dup_",
                length=24,
            )
            confidence = _aggressive_group_confidence(families)

        canonical_event_id = stable_hash(
            {
                "strategy": strategy,
                "primary": primary.canonical_input_id,
                "canonical_input_ids": input_ids,
            },
            prefix="evt_",
            length=24,
        )
        provenance = [asdict(record.provenance()) for record in group_records]
        event = primary.to_json_dict()
        event_update = {
            "canonical_event_id": canonical_event_id,
            "duplicate_fingerprint": duplicate_fingerprint,
            "duplicate_record_count": len(group_records),
            "dedupe_strategy": dedupe_strategy,
            "dedupe_evidence_families": families,
            "dedupe_confidence": confidence,
            "source_provenance": provenance,
            "canonical_input_ids": input_ids,
        }
        if merged_craft_evidence := build_merged_member_craft_evidence(primary, group_records):
            event_update.update(merged_craft_evidence)
        event.update(event_update)
        deduped_events.append(event)
        if len(group_records) > 1:
            duplicate_groups.append(
                {
                    "duplicate_group_id": stable_hash(
                        {
                            "strategy": strategy,
                            "canonical_input_ids": input_ids,
                        },
                        prefix="dupg_",
                        length=24,
                    ),
                    "canonical_event_id": canonical_event_id,
                    "duplicate_fingerprint": duplicate_fingerprint,
                    "strategy": dedupe_strategy,
                    "confidence": confidence,
                    "record_count": len(group_records),
                    "canonical_input_ids": input_ids,
                    "dedupe_evidence_families": families,
                    "source_provenance": provenance,
                }
            )

    return deduped_events, duplicate_groups


def build_duplicate_candidates(
    records: Iterable[CanonicalInputRecord],
    *,
    limit: int = DEFAULT_DUPLICATE_CANDIDATE_LIMIT,
) -> list[dict[str, Any]]:
    """Return a bounded queue of fuzzy duplicate candidates without merging.

    Candidate generation is intentionally narrower than exact grouping. A pair
    must share the same strong day-level date, a normalized location block, and
    corroborating source text or source identifier evidence before it is emitted.
    """
    if limit <= 0:
        return []

    features = [_candidate_features(record) for record in records]
    blocks: dict[tuple[str, str], list[_CandidateFeatures]] = {}
    for feature in features:
        if feature.date_key is None or not feature.location_key:
            continue
        blocks.setdefault((feature.date_key, feature.location_key), []).append(feature)

    candidates_by_pair: dict[tuple[str, str], dict[str, Any]] = {}
    for (date_key, location_key), block in sorted(blocks.items(), key=lambda item: item[0]):
        if len(block) < 2:
            continue
        ordered_block = sorted(block, key=lambda item: item.record.canonical_input_id)
        for left_index, left in enumerate(ordered_block):
            for right in ordered_block[left_index + 1 :]:
                pair_key = _candidate_pair_key(left.record, right.record)
                if pair_key in candidates_by_pair:
                    continue
                candidate = _score_candidate_pair(left, right, date_key=date_key, location_key=location_key)
                if candidate is not None:
                    candidates_by_pair[pair_key] = candidate

    candidates = sorted(
        candidates_by_pair.values(),
        key=lambda candidate: (
            -candidate["score"],
            candidate["canonical_input_ids"],
            candidate["duplicate_candidate_id"],
        ),
    )
    return candidates[:limit]


def _choose_primary_record(records: list[CanonicalInputRecord]) -> CanonicalInputRecord:
    def score(record: CanonicalInputRecord) -> tuple[int, int, int, str]:
        mapped = 1 if record.lat is not None and record.lon is not None else 0
        description_len = len(record.description or "")
        source_count = 1 if record.source_native_id else 0
        return mapped, description_len, source_count, record.canonical_input_id

    return sorted(records, key=score, reverse=True)[0]


def _rule_based_auto_merge_keys(
    record: CanonicalInputRecord,
    *,
    strategy: str,
) -> list[tuple[str, str]]:
    source_key = normalize_key(record.source_name)
    native_id = _specific_native_id_key(record.source_native_id)
    date_key = _strong_date_key(record)
    location_key = _normalized_location_key(record)
    time_key = _specific_time_key(record.time_raw)
    type_key = _type_shape_key(record)
    specific_type_key = _specific_type_shape_key(record)
    coordinate_key = _trusted_rounded_coordinate_key(record)
    coordinate_cell_key = _trusted_nearby_coordinate_cell_key(record)
    structured_city_state_country_key = _structured_location_key(record, include_state=True, include_country=True)
    structured_city_state_key = _structured_location_key(record, include_state=True, include_country=False)
    structured_city_country_key = _structured_location_key(record, include_state=False, include_country=True)
    exact_fingerprint = canonical_duplicate_fingerprint(record)

    keys: list[tuple[str, str]] = []
    if exact_fingerprint:
        keys.append(("exact_canonical_fingerprint", exact_fingerprint))
    if source_key and native_id:
        keys.append(("same_source_native_id_any_date", "|".join((source_key, native_id))))
        if date_key:
            keys.append(("same_source_native_id_strong_date", "|".join((source_key, native_id, date_key))))
    if not date_key:
        return keys
    if location_key and time_key:
        keys.append(("strong_date_location_specific_time", "|".join((date_key, location_key, time_key))))
        if source_key:
            keys.append(
                (
                    "same_source_strong_date_location_specific_time",
                    "|".join((source_key, date_key, location_key, time_key)),
                )
            )
    if coordinate_key and time_key:
        keys.append(("strong_date_coordinate_specific_time", "|".join((date_key, coordinate_key, time_key))))
    if source_key and coordinate_cell_key and time_key:
        keys.append(
            (
                "same_source_strong_date_coordinate_cell_specific_time",
                "|".join((source_key, date_key, coordinate_cell_key, time_key)),
            )
        )
    if source_key and location_key and type_key:
        keys.append(
            (
                "same_source_strong_date_location_type",
                "|".join((source_key, date_key, location_key, type_key)),
            )
        )
    if source_key and location_key:
        keys.append(
            (
                "same_source_strong_date_location",
                "|".join((source_key, date_key, location_key)),
            )
        )
    if source_key and coordinate_key and type_key:
        keys.append(
            (
                "same_source_strong_date_coordinate_type",
                "|".join((source_key, date_key, coordinate_key, type_key)),
            )
        )
    if source_key and coordinate_cell_key:
        keys.append(
            (
                "same_source_strong_date_coordinate_cell",
                "|".join((source_key, date_key, coordinate_cell_key)),
            )
        )
    if strategy in {DEDUPE_STRATEGY_MAXIMAL_V1, DEDUPE_STRATEGY_MAXIMAL_V2, DEDUPE_STRATEGY_MAXIMAL_V3}:
        if location_key and type_key:
            keys.append(("strong_date_location_type", "|".join((date_key, location_key, type_key))))
        if coordinate_key and type_key:
            keys.append(("strong_date_coordinate_type", "|".join((date_key, coordinate_key, type_key))))
        if location_key:
            keys.append(("strong_date_location", "|".join((date_key, location_key))))
        if coordinate_cell_key:
            keys.append(("strong_date_coordinate_cell", "|".join((date_key, coordinate_cell_key))))
    if strategy in {DEDUPE_STRATEGY_MAXIMAL_V2, DEDUPE_STRATEGY_MAXIMAL_V3}:
        if source_key and structured_city_state_country_key:
            keys.append(
                (
                    "same_source_strong_date_structured_city_state_country",
                    "|".join((source_key, date_key, structured_city_state_country_key)),
                )
            )
        if source_key and structured_city_state_key:
            keys.append(
                (
                    "same_source_strong_date_structured_city_state",
                    "|".join((source_key, date_key, structured_city_state_key)),
                )
            )
        if strategy == DEDUPE_STRATEGY_MAXIMAL_V2 and source_key and structured_city_country_key and specific_type_key:
            keys.append(
                (
                    "same_source_strong_date_structured_city_country_type",
                    "|".join((source_key, date_key, structured_city_country_key, specific_type_key)),
                )
            )
        if structured_city_state_country_key:
            keys.append(
                (
                    "strong_date_structured_city_state_country",
                    "|".join((date_key, structured_city_state_country_key)),
                )
            )
        if structured_city_state_key:
            keys.append(("strong_date_structured_city_state", "|".join((date_key, structured_city_state_key))))
        if strategy == DEDUPE_STRATEGY_MAXIMAL_V2 and structured_city_country_key and specific_type_key:
            keys.append(
                (
                    "strong_date_structured_city_country_type",
                    "|".join((date_key, structured_city_country_key, specific_type_key)),
                )
            )
    return keys


def _add_maximal_v3_group_aware_keys(
    records: list[CanonicalInputRecord],
    key_buckets: dict[tuple[str, str], list[str]],
) -> None:
    """Add high-yield exact-day joins across state-present/state-missing rows.

    Many source files describe the same event as ``Hobbs, NM, US`` in one row
    and ``Hobbs, US`` or ``Hobbs`` in another. Per-record keys cannot safely
    merge those variants because dropping state can conflate cities with the
    same name. This pass builds whole city/country/day blocks, then allows the
    merge only when every known state/province inside the block agrees.
    """

    blocks: dict[str, list[CanonicalInputRecord]] = {}
    for record in records:
        date_key = _strong_date_key(record)
        city = _normalized_location_component(record.city)
        country = _normalized_location_component(record.country)
        if (
            not date_key
            or not city
            or not country
            or city in GENERIC_LOCATION_COMPONENTS
            or country in GENERIC_LOCATION_COMPONENTS
        ):
            continue
        key = "|".join((date_key, city, country))
        blocks.setdefault(key, []).append(record)

    family = "strong_date_structured_city_country_no_state_conflict"
    for key, block_records in blocks.items():
        if len(block_records) < 2:
            continue
        known_states = {
            state
            for state in (_normalized_location_component(record.state_province) for record in block_records)
            if state and state not in GENERIC_LOCATION_COMPONENTS
        }
        if len(known_states) > 1:
            continue
        key_buckets.setdefault((family, key), []).extend(
            record.canonical_input_id for record in block_records
        )


def _aggressive_group_confidence(families: list[str]) -> str:
    high_confidence = {
        "exact_canonical_fingerprint",
        "same_source_native_id_any_date",
        "same_source_native_id_strong_date",
        "same_source_strong_date_location",
        "same_source_strong_date_location_specific_time",
        "same_source_strong_date_coordinate_cell",
        "same_source_strong_date_coordinate_cell_specific_time",
        "same_source_strong_date_structured_city_state_country",
        "same_source_strong_date_structured_city_state",
    }
    medium_confidence = {
        "strong_date_location_specific_time",
        "strong_date_coordinate_specific_time",
        "same_source_strong_date_location_type",
        "same_source_strong_date_coordinate_type",
        "same_source_strong_date_structured_city_country_type",
        "strong_date_location_type",
        "strong_date_coordinate_type",
        "strong_date_structured_city_state_country",
        "strong_date_structured_city_state",
        "strong_date_structured_city_country_type",
    }
    low_confidence = {
        "strong_date_location",
        "strong_date_coordinate_cell",
        "strong_date_structured_city_country_no_state_conflict",
    }
    if any(family in high_confidence for family in families):
        return "high"
    if any(family in medium_confidence for family in families):
        return "medium"
    if any(family in low_confidence for family in families):
        return "low"
    return "low"


def _specific_native_id_key(value: str | None) -> str:
    key = normalize_key(value)
    if len(key) < 3:
        return ""
    if key in GENERIC_NATIVE_IDS:
        return ""
    return key


def _specific_time_key(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return ""
    lowered = text.lower()
    if "noon" in lowered:
        return "noon"
    if "midnight" in lowered:
        return "midnight"
    clock_match = re.search(
        r"\b(?:(?:[01]?\d|2[0-3])(?::[0-5]\d){1,2}|(?:[01]?\d|2[0-3])[0-5]\d)\s*(?:a\.?m\.?|p\.?m\.?)?\b",
        lowered,
    )
    if clock_match:
        return normalize_key(clock_match.group(0))
    am_pm_match = re.search(r"\b(?:[1-9]|1[0-2])\s*(?:a\.?m\.?|p\.?m\.?)\b", lowered)
    if am_pm_match:
        return normalize_key(am_pm_match.group(0))
    return ""


def _type_shape_key(record: CanonicalInputRecord) -> str:
    return normalize_key(
        record.type_normalized
        or record.type_raw
        or record.shape_normalized
        or record.shape_raw
    )


def _specific_type_shape_key(record: CanonicalInputRecord) -> str:
    key = _type_shape_key(record)
    if key in GENERIC_TYPE_KEYS:
        return ""
    return key


def _structured_location_key(
    record: CanonicalInputRecord,
    *,
    include_state: bool,
    include_country: bool,
) -> str:
    city = _normalized_location_component(record.city)
    if not city:
        return ""
    parts = [city]
    if include_state:
        state = _normalized_location_component(record.state_province)
        if not state:
            return ""
        parts.append(state)
    if include_country:
        country = _normalized_location_component(record.country)
        if not country:
            return ""
        parts.append(country)
    return "|".join(parts)


def _normalized_location_component(value: Any) -> str:
    key = normalize_key(value)
    if not key:
        return ""
    tokens: list[str] = []
    for token in TOKEN_RE.findall(key):
        normalized = LOCATION_TOKEN_ALIASES.get(token, token)
        tokens.extend(part for part in normalized.split("_") if part)
    return " ".join(tokens)


def _trusted_rounded_coordinate_key(record: CanonicalInputRecord, *, decimals: int = 3) -> str:
    if normalize_key(record.coordinate_source) not in TRUSTED_EXACT_COORDINATE_SOURCES:
        return ""
    if record.lat is None or record.lon is None:
        return ""
    return f"{round(float(record.lat), decimals):.{decimals}f},{round(float(record.lon), decimals):.{decimals}f}"


def _trusted_nearby_coordinate_cell_key(record: CanonicalInputRecord, *, cell_degrees: float = 0.05) -> str:
    if normalize_key(record.coordinate_source) not in TRUSTED_EXACT_COORDINATE_SOURCES:
        return ""
    if record.lat is None or record.lon is None:
        return ""
    lat_cell = int(float(record.lat) / cell_degrees)
    lon_cell = int(float(record.lon) / cell_degrees)
    return f"{lat_cell},{lon_cell}"


def _candidate_features(record: CanonicalInputRecord) -> _CandidateFeatures:
    source_text_key, source_tokens = _normalized_source_text(record)
    return _CandidateFeatures(
        record=record,
        date_key=_strong_date_key(record),
        location_key=_normalized_location_key(record),
        source_text_key=source_text_key,
        source_tokens=frozenset(source_tokens),
        exact_fingerprint=canonical_duplicate_fingerprint(record),
    )


def _strong_date_key(record: CanonicalInputRecord) -> str | None:
    if not record.date_iso:
        return None
    if (record.date_precision or "").lower() not in STRONG_DATE_PRECISIONS:
        return None
    return record.date_iso


def _normalized_location_key(record: CanonicalInputRecord) -> str:
    text = record.location_raw or build_location_text(record.city, record.state_province, record.country)
    key = normalize_key(text)
    if not key:
        return ""
    key = re.sub(r"\bunited states(?: of america)?\b", "usa", key)
    tokens: list[str] = []
    for token in TOKEN_RE.findall(key):
        normalized = LOCATION_TOKEN_ALIASES.get(token, token)
        tokens.extend(part for part in normalized.split("_") if part)
    return " ".join(tokens)


def _normalized_source_text(record: CanonicalInputRecord) -> tuple[str, set[str]]:
    raw_text = " ".join(
        part
        for part in (
            clean_text(record.summary),
            clean_text(record.description),
            clean_text(record.shape_raw),
            clean_text(record.type_raw),
            clean_text(record.duration_raw),
        )
        if part
    )
    tokens = [_normalize_source_token(token) for token in TOKEN_RE.findall(normalize_key(raw_text))]
    significant_ordered = [
        token for token in tokens if token and token not in SOURCE_STOP_WORDS and len(token) > 1
    ]
    return " ".join(significant_ordered), set(significant_ordered)


def _normalize_source_token(token: str) -> str:
    token = SOURCE_TOKEN_ALIASES.get(token, token)
    if token in SOURCE_TOKEN_ALIASES.values():
        return token
    if len(token) > 5 and token.endswith("ing"):
        return token[:-3]
    if len(token) > 4 and token.endswith("ed"):
        return token[:-2]
    if len(token) > 4 and token.endswith("ly"):
        return token[:-2]
    if len(token) > 3 and token.endswith("s"):
        return token[:-1]
    return token


def _candidate_pair_key(left: CanonicalInputRecord, right: CanonicalInputRecord) -> tuple[str, str]:
    ordered = sorted((left.canonical_input_id, right.canonical_input_id))
    return ordered[0], ordered[1]


def _score_candidate_pair(
    left: _CandidateFeatures,
    right: _CandidateFeatures,
    *,
    date_key: str,
    location_key: str,
) -> dict[str, Any] | None:
    if left.exact_fingerprint and left.exact_fingerprint == right.exact_fingerprint:
        return None

    text_similarity = _source_text_similarity(left, right)
    shared_identifier = _shared_source_identifier(left.record, right.record)
    if text_similarity < MIN_SOURCE_TEXT_SIMILARITY and not shared_identifier:
        return None

    reasons = ["same_strong_date", "same_normalized_location"]
    source_signal_score = text_similarity
    if text_similarity >= MIN_SOURCE_TEXT_SIMILARITY:
        reasons.append("similar_source_text")
    if shared_identifier:
        reasons.append("shared_source_identifier")
        source_signal_score = max(source_signal_score, 0.72)

    score = min(1.0, round((0.38 + 0.34 + (0.28 * source_signal_score)), 3))
    if score < MIN_DUPLICATE_CANDIDATE_SCORE:
        return None

    ids = list(_candidate_pair_key(left.record, right.record))
    return {
        "duplicate_candidate_id": stable_hash(
            {"canonical_input_ids": ids},
            prefix="dupc_",
            length=24,
        ),
        "strategy": "bounded_fuzzy_candidate",
        "auto_merge": False,
        "merge_decision": "candidate_only",
        "score": score,
        "reasons": reasons,
        "blocking": {
            "date_iso": date_key,
            "date_precision": "strong_day",
            "location_key": location_key,
        },
        "signals": {
            "source_text_similarity": round(text_similarity, 3),
            "shared_source_identifier": shared_identifier,
        },
        "canonical_input_ids": ids,
        "records": [
            _candidate_record_summary(left.record),
            _candidate_record_summary(right.record),
        ],
    }


def _source_text_similarity(left: _CandidateFeatures, right: _CandidateFeatures) -> float:
    token_similarity = _token_cosine(left.source_tokens, right.source_tokens)
    sequence_similarity = 0.0
    if left.source_text_key and right.source_text_key:
        sequence_similarity = SequenceMatcher(None, left.source_text_key, right.source_text_key).ratio()
    return max(token_similarity, sequence_similarity)


def _token_cosine(left_tokens: frozenset[str], right_tokens: frozenset[str]) -> float:
    if not left_tokens or not right_tokens:
        return 0.0
    intersection_count = len(left_tokens & right_tokens)
    return intersection_count / ((len(left_tokens) * len(right_tokens)) ** 0.5)


def _shared_source_identifier(left: CanonicalInputRecord, right: CanonicalInputRecord) -> bool:
    left_id = normalize_key(left.source_native_id)
    right_id = normalize_key(right.source_native_id)
    if left_id and left_id == right_id:
        return True
    left_url = normalize_key(left.source_url)
    right_url = normalize_key(right.source_url)
    return bool(left_url and left_url == right_url)


def _candidate_record_summary(record: CanonicalInputRecord) -> dict[str, Any]:
    return {
        "canonical_input_id": record.canonical_input_id,
        "source_name": record.source_name,
        "source_file": record.source_file,
        "source_row_number": record.source_row_number,
        "source_native_id": record.source_native_id,
        "date_iso": record.date_iso,
        "date_precision": record.date_precision,
        "location": record.location_raw or build_location_text(record.city, record.state_province, record.country),
        "source_text": _snippet(record.summary or record.description),
    }


def _snippet(value: str | None, *, limit: int = 180) -> str | None:
    text = clean_text(value)
    if text is None or len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip()}..."
