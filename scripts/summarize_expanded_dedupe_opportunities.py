"""Estimate expanded duplicate-reduction opportunities without mutating outputs.

This report is intentionally conservative and analysis-only. It streams compact
fields out of the current canonical source/deduped JSONL artifacts, groups
records by stronger duplicate signals, and reports possible current-event
reductions by connected component. It does not apply merges.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import Any, Iterable

from parser.canonical_schema import build_location_text, clean_text, normalize_key, stable_hash
from parser.dedupe import LOCATION_TOKEN_ALIASES, SOURCE_STOP_WORDS, TOKEN_RE, _normalize_source_token


DEFAULT_SOURCE_RECORDS_PATH = Path("data/canonical_full/source_records.jsonl")
DEFAULT_DEDUPED_EVENTS_PATH = Path("data/canonical_full/deduped_events.jsonl")
DEFAULT_OUTPUT = Path("data/reports/expanded_dedupe_opportunity_report.json")

STRONG_DATE_PRECISIONS = {"day", "exact_day"}
TEXT_SIGNATURE_MIN_TOKENS = 4
EXACT_TEXT_MIN_CHARS = 16
TRUSTED_EXACT_COORDINATE_SOURCES = {"raw latlong", "source coordinates", "location coordinates"}


@dataclass(frozen=True)
class FamilyDefinition:
    family_id: str
    tier: str
    description: str


FAMILY_DEFINITIONS = {
    "same_source_native_id_strong_date": FamilyDefinition(
        family_id="same_source_native_id_strong_date",
        tier="conservative",
        description="Same source family, same source-native identifier, and exact/day date.",
    ),
    "same_source_url_strong_date": FamilyDefinition(
        family_id="same_source_url_strong_date",
        tier="conservative",
        description="Same specific source URL, exact/day date, and normalized location.",
    ),
    "strong_date_location_exact_text": FamilyDefinition(
        family_id="strong_date_location_exact_text",
        tier="conservative",
        description="Exact/day date, normalized location, and exact normalized source text.",
    ),
    "strong_date_coordinate_exact_text": FamilyDefinition(
        family_id="strong_date_coordinate_exact_text",
        tier="moderate",
        description="Exact/day date, rounded coordinates, and exact normalized source text.",
    ),
    "strong_date_location_token_signature": FamilyDefinition(
        family_id="strong_date_location_token_signature",
        tier="exploratory",
        description=(
            "Exact/day date, normalized location, and a sorted significant-token text signature. "
            "This is for opportunity sizing, not automatic merging."
        ),
    ),
    "strong_date_exact_text_any_location": FamilyDefinition(
        family_id="strong_date_exact_text_any_location",
        tier="exploratory",
        description="Exact/day date and exact normalized source text, even when normalized location differs or is absent.",
    ),
    "strong_date_location_specific_time": FamilyDefinition(
        family_id="strong_date_location_specific_time",
        tier="aggressive",
        description="Exact/day date, normalized location, and specific time evidence, without requiring matching text.",
    ),
    "same_source_strong_date_location_specific_time": FamilyDefinition(
        family_id="same_source_strong_date_location_specific_time",
        tier="aggressive",
        description="Same source family, exact/day date, normalized location, and specific time evidence.",
    ),
    "strong_date_coordinate_specific_time": FamilyDefinition(
        family_id="strong_date_coordinate_specific_time",
        tier="aggressive",
        description="Exact/day date, rounded coordinates, and specific time evidence, without requiring matching text.",
    ),
    "same_source_strong_date_coordinate_cell_specific_time": FamilyDefinition(
        family_id="same_source_strong_date_coordinate_cell_specific_time",
        tier="aggressive",
        description=(
            "Same source family, exact/day date, specific time evidence, and nearby trusted coordinates "
            "bucketed into a coarse review-only cell."
        ),
    ),
    "same_source_native_id_any_date": FamilyDefinition(
        family_id="same_source_native_id_any_date",
        tier="aggressive",
        description="Same source family and specific source-native identifier, regardless of parsed date agreement.",
    ),
    "same_specific_source_url_any_date": FamilyDefinition(
        family_id="same_specific_source_url_any_date",
        tier="aggressive",
        description="Same specific source URL, regardless of parsed date agreement.",
    ),
}

TIER_ORDER = ("conservative", "moderate", "exploratory", "aggressive")


@dataclass
class GroupState:
    first_event_id: str
    first_input_id: str
    first_source_name: str | None
    first_source_file: str | None
    first_date_iso: str | None
    first_location: str | None
    source_record_count: int = 1
    event_ids: set[str] | None = None
    input_id_samples: list[str] = field(default_factory=list)
    source_names: set[str] = field(default_factory=set)
    date_values: set[str] | None = None
    location_values: set[str] | None = None

    def add(
        self,
        *,
        event_id: str,
        input_id: str,
        source_name: str | None,
        date_iso: str | None,
        location: str | None,
        max_samples: int,
    ) -> bool:
        """Add a record and return true when this group links distinct current events."""
        self.source_record_count += 1
        if source_name:
            self.source_names.add(source_name)
        if date_iso and date_iso != self.first_date_iso:
            if self.date_values is None:
                self.date_values = {self.first_date_iso} if self.first_date_iso else set()
            self.date_values.add(date_iso)
        if location and location != self.first_location:
            if self.location_values is None:
                self.location_values = {self.first_location} if self.first_location else set()
            self.location_values.add(location)
        if len(self.input_id_samples) < max_samples:
            self.input_id_samples.append(input_id)
        if event_id == self.first_event_id and self.event_ids is None:
            return False
        if self.event_ids is None:
            self.event_ids = {self.first_event_id}
        before_count = len(self.event_ids)
        self.event_ids.add(event_id)
        return len(self.event_ids) > before_count

    @property
    def unique_event_count(self) -> int:
        return len(self.event_ids) if self.event_ids is not None else 1

    @property
    def distinct_date_count(self) -> int:
        return len(self.date_values) if self.date_values is not None else (1 if self.first_date_iso else 0)

    @property
    def distinct_location_count(self) -> int:
        return len(self.location_values) if self.location_values is not None else (1 if self.first_location else 0)


class DisjointSet:
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

    def component_sizes(self) -> list[int]:
        components: dict[str, int] = {}
        for value in self.parent:
            root = self.find(value)
            components[root] = components.get(root, 0) + 1
        return sorted(components.values(), reverse=True)


class FamilyIndex:
    def __init__(
        self,
        definition: FamilyDefinition,
        *,
        top_group_limit: int = 20,
        sample_limit: int = 4,
        event_id_output_limit: int = 0,
    ) -> None:
        self.definition = definition
        self.top_group_limit = top_group_limit
        self.sample_limit = sample_limit
        self.event_id_output_limit = event_id_output_limit
        self.groups: dict[str, GroupState] = {}
        self.key_count = 0
        self.source_record_count = 0
        self.cross_event_key_count = 0
        self.cross_event_source_record_count = 0
        self._known_cross_event_keys: set[str] = set()

    def add(
        self,
        key: str,
        *,
        event_id: str,
        input_id: str,
        source_name: str | None,
        source_file: str | None,
        date_iso: str | None,
        location: str | None,
        tier_unions: dict[str, DisjointSet],
    ) -> None:
        self.source_record_count += 1
        group = self.groups.get(key)
        if group is None:
            self.groups[key] = GroupState(
                first_event_id=event_id,
                first_input_id=input_id,
                first_source_name=source_name,
                first_source_file=source_file,
                first_date_iso=date_iso,
                first_location=location,
                input_id_samples=[input_id],
                source_names={source_name} if source_name else set(),
            )
            self.key_count += 1
            return

        was_cross_event = group.event_ids is not None
        is_new_event = event_id != group.first_event_id and (
            group.event_ids is None or event_id not in group.event_ids
        )
        group.add(
            event_id=event_id,
            input_id=input_id,
            source_name=source_name,
            date_iso=date_iso,
            location=location,
            max_samples=self.sample_limit,
        )
        if is_new_event:
            for tier in tiers_including(self.definition.tier):
                tier_unions[tier].union(group.first_event_id, event_id)
        if not was_cross_event and group.event_ids is not None:
            self.cross_event_key_count += 1
            self._known_cross_event_keys.add(key)
        if group.event_ids is not None:
            self.cross_event_source_record_count += 1

    def summarize(self) -> dict[str, Any]:
        cross_event_groups = [
            (key, group)
            for key, group in self.groups.items()
            if group.event_ids is not None and group.unique_event_count > 1
        ]
        projected_reduction = sum(group.unique_event_count - 1 for _, group in cross_event_groups)
        cross_event_groups.sort(
            key=lambda item: (-item[1].unique_event_count, -item[1].source_record_count, item[0])
        )
        return {
            "family_id": self.definition.family_id,
            "tier": self.definition.tier,
            "description": self.definition.description,
            "key_count": self.key_count,
            "source_record_count": self.source_record_count,
            "cross_event_key_count": len(cross_event_groups),
            "cross_event_source_record_count": sum(group.source_record_count for _, group in cross_event_groups),
            "projected_event_reduction_if_reviewed_same_event": projected_reduction,
            "top_cross_event_groups": [
                self.top_group_payload(key, group)
                for key, group in cross_event_groups[: self.top_group_limit]
            ],
        }

    def top_group_payload(self, key: str, group: GroupState) -> dict[str, Any]:
        event_ids = sorted(group.event_ids or {group.first_event_id})
        payload = {
            "key_hash": stable_hash(key, prefix="dgk_", length=16),
            "unique_current_event_count": group.unique_event_count,
            "source_record_count": group.source_record_count,
            "sample_input_ids": group.input_id_samples[: self.sample_limit],
            "source_names": sorted(group.source_names),
            "first_source_file": group.first_source_file,
            "date_iso": group.first_date_iso,
            "location": group.first_location,
            "distinct_date_count": group.distinct_date_count,
            "distinct_location_count": group.distinct_location_count,
            "date_samples": sorted(group.date_values or ({group.first_date_iso} if group.first_date_iso else set()))[
                : self.sample_limit
            ],
            "location_samples": sorted(
                group.location_values or ({group.first_location} if group.first_location else set())
            )[: self.sample_limit],
        }
        if self.event_id_output_limit > 0:
            payload["current_event_ids"] = event_ids[: self.event_id_output_limit]
            payload["current_event_ids_truncated"] = len(event_ids) > self.event_id_output_limit
        return payload


def summarize_expanded_dedupe_opportunities(
    *,
    source_records_path: Path = DEFAULT_SOURCE_RECORDS_PATH,
    deduped_events_path: Path = DEFAULT_DEDUPED_EVENTS_PATH,
    top_group_limit: int = 20,
    top_group_event_id_limit: int = 0,
    limit: int | None = None,
) -> dict[str, Any]:
    input_to_event, event_count, duplicate_record_count = build_input_to_event_index(deduped_events_path)
    family_indexes = {
        family_id: FamilyIndex(
            definition,
            top_group_limit=top_group_limit,
            event_id_output_limit=top_group_event_id_limit,
        )
        for family_id, definition in FAMILY_DEFINITIONS.items()
    }
    tier_unions = {tier: DisjointSet() for tier in TIER_ORDER}

    scanned_source_records = 0
    source_records_with_current_event = 0
    source_records_without_current_event = 0
    strong_date_records = 0
    key_candidate_records = 0

    for record in iter_jsonl(source_records_path):
        scanned_source_records += 1
        if limit is not None and scanned_source_records > limit:
            scanned_source_records -= 1
            break
        input_id = clean_text(record.get("canonical_input_id"))
        if not input_id:
            continue
        event_id = input_to_event.get(input_id)
        if not event_id:
            source_records_without_current_event += 1
            continue
        source_records_with_current_event += 1
        if is_strong_date_record(record):
            strong_date_records += 1
        keys = dedupe_opportunity_keys(record)
        if keys:
            key_candidate_records += 1
        for family_id, key in keys:
            family_indexes[family_id].add(
                key,
                event_id=event_id,
                input_id=input_id,
                source_name=clean_text(record.get("source_name")),
                source_file=clean_text(record.get("source_file")),
                date_iso=clean_text(record.get("date_iso")),
                location=record_location_text(record),
                tier_unions=tier_unions,
            )

    union_summaries = {
        tier: summarize_tier_union(tier, dsu)
        for tier, dsu in tier_unions.items()
    }
    families = [family_indexes[family_id].summarize() for family_id in FAMILY_DEFINITIONS]
    return {
        "schema_version": 1,
        "report_policy": "streaming_estimate_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "inputs": {
            "source_records": str(source_records_path),
            "deduped_events": str(deduped_events_path),
            "limit": limit,
            "top_group_limit": top_group_limit,
            "top_group_event_id_limit": top_group_event_id_limit,
        },
        "current_canonical_counts": {
            "current_event_count": event_count,
            "current_source_record_count_from_events": len(input_to_event),
            "current_exact_duplicate_record_reduction": duplicate_record_count,
        },
        "scan_counts": {
            "scanned_source_records": scanned_source_records,
            "source_records_with_current_event": source_records_with_current_event,
            "source_records_without_current_event": source_records_without_current_event,
            "strong_date_records": strong_date_records,
            "records_with_any_opportunity_key": key_candidate_records,
        },
        "tier_union_reduction_estimates": union_summaries,
        "families": families,
        "benchmark_context": {
            "ufosint_screenshot_deduped_sightings": 618316,
            "gap_from_current_event_count": max(0, event_count - 618316),
            "gap_after_conservative_union_estimate": max(
                0,
                event_count - union_summaries["conservative"]["projected_event_reduction"] - 618316,
            ),
            "gap_after_conservative_plus_moderate_union_estimate": max(
                0,
                event_count - union_summaries["moderate"]["projected_event_reduction"] - 618316,
            ),
            "gap_after_all_reported_families_estimate": max(
                0,
                event_count - union_summaries["exploratory"]["projected_event_reduction"] - 618316,
            ),
            "gap_after_aggressive_union_estimate": max(
                0,
                event_count - union_summaries["aggressive"]["projected_event_reduction"] - 618316,
            ),
        },
        "notes": [
            "This report estimates review opportunity only; it does not prove all grouped records are duplicates.",
            "Conservative families still require preview/human validation before any future apply step.",
            "Exploratory token-signature families are sizing signals and should not be auto-merged.",
            "Aggressive families are for gap analysis and manual-review queue design only.",
            "The report uses current canonical event membership, so reductions count only links across existing deduped events.",
        ],
    }


def build_input_to_event_index(deduped_events_path: Path) -> tuple[dict[str, str], int, int]:
    input_to_event: dict[str, str] = {}
    event_count = 0
    duplicate_record_count = 0
    for event in iter_jsonl(deduped_events_path):
        event_count += 1
        event_id = clean_text(event.get("canonical_event_id")) or clean_text(event.get("event_id"))
        if not event_id:
            continue
        input_ids = normalized_id_list(event.get("canonical_input_ids"))
        duplicate_record_count += max(0, len(input_ids) - 1)
        for input_id in input_ids:
            input_to_event[input_id] = event_id
    return input_to_event, event_count, duplicate_record_count


def dedupe_opportunity_keys(record: dict[str, Any]) -> list[tuple[str, str]]:
    date_iso = clean_text(record.get("date_iso"))
    source_name = normalize_key(record.get("source_name"))
    native_id = normalize_key(record.get("source_native_id"))
    broad_native_id = specific_native_id_key(record.get("source_native_id"))
    source_url = specific_source_url_key(record.get("source_url"))
    location_key = normalized_location_key(record)
    exact_text = normalized_source_text(record)
    exact_text_hash = specific_text_hash(exact_text)
    text_signature = source_token_signature(record)
    coordinate_key = rounded_coordinate_key(record)
    coordinate_cell_key = nearby_coordinate_cell_key(record)
    time_key = specific_time_key(record.get("time_raw"))

    keys: list[tuple[str, str]] = []
    if source_name and broad_native_id:
        keys.append(
            (
                "same_source_native_id_any_date",
                "|".join(("same_source_native_id_any_date", source_name, broad_native_id)),
            )
        )
    if source_url:
        keys.append(("same_specific_source_url_any_date", "|".join(("same_specific_source_url_any_date", source_url))))
    if not date_iso or not is_strong_date_record(record):
        return keys

    if source_name and native_id:
        keys.append(
            (
                "same_source_native_id_strong_date",
                "|".join(("same_source_native_id_strong_date", source_name, native_id, date_iso)),
            )
        )
    if source_url and location_key:
        keys.append(
            (
                "same_source_url_strong_date",
                "|".join(("same_source_url_strong_date", source_url, date_iso, location_key)),
            )
        )
    if location_key and exact_text_hash:
        keys.append(
            (
                "strong_date_location_exact_text",
                "|".join(("strong_date_location_exact_text", date_iso, location_key, exact_text_hash)),
            )
        )
    if coordinate_key and exact_text_hash:
        keys.append(
            (
                "strong_date_coordinate_exact_text",
                "|".join(("strong_date_coordinate_exact_text", date_iso, coordinate_key, exact_text_hash)),
            )
        )
    if exact_text_hash:
        keys.append(
            (
                "strong_date_exact_text_any_location",
                "|".join(("strong_date_exact_text_any_location", date_iso, exact_text_hash)),
            )
        )
    if location_key and text_signature:
        keys.append(
            (
                "strong_date_location_token_signature",
                "|".join(("strong_date_location_token_signature", date_iso, location_key, text_signature)),
            )
        )
    if location_key and time_key:
        keys.append(
            (
                "strong_date_location_specific_time",
                "|".join(("strong_date_location_specific_time", date_iso, location_key, time_key)),
            )
        )
        if source_name:
            keys.append(
                (
                    "same_source_strong_date_location_specific_time",
                    "|".join(
                        (
                            "same_source_strong_date_location_specific_time",
                            source_name,
                            date_iso,
                            location_key,
                            time_key,
                        )
                    ),
                )
            )
    if coordinate_key and time_key:
        keys.append(
            (
                "strong_date_coordinate_specific_time",
                "|".join(("strong_date_coordinate_specific_time", date_iso, coordinate_key, time_key)),
            )
        )
    if source_name and coordinate_cell_key and time_key:
        keys.append(
            (
                "same_source_strong_date_coordinate_cell_specific_time",
                "|".join(
                    (
                        "same_source_strong_date_coordinate_cell_specific_time",
                        source_name,
                        date_iso,
                        coordinate_cell_key,
                        time_key,
                    )
                ),
            )
        )
    return keys


def summarize_tier_union(tier: str, dsu: DisjointSet) -> dict[str, Any]:
    component_sizes = dsu.component_sizes()
    linked_components = [size for size in component_sizes if size > 1]
    return {
        "included_tiers": tiers_included_by(tier),
        "linked_current_event_count": sum(linked_components),
        "linked_component_count": len(linked_components),
        "projected_event_reduction": sum(size - 1 for size in linked_components),
        "largest_components": linked_components[:25],
    }


def tiers_including(tier: str) -> tuple[str, ...]:
    start = TIER_ORDER.index(tier)
    return TIER_ORDER[start:]


def tiers_included_by(tier: str) -> list[str]:
    end = TIER_ORDER.index(tier)
    return list(TIER_ORDER[: end + 1])


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{path} line {line_number} must be a JSON object.")
            yield payload


def normalized_id_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := clean_text(item))]


def specific_source_url_key(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return ""
    key = normalize_key(text)
    if len(key) < 12:
        return ""
    lower_text = text.lower()
    has_url_signal = "http://" in lower_text or "https://" in lower_text or "#" in lower_text
    digit_count = sum(1 for char in key if char.isdigit())
    if not has_url_signal and digit_count < 4:
        return ""
    generic_keys = {
        "uforeportctr",
        "nuforc",
        "mufon",
        "ufocat",
        "personal communication",
    }
    if key in generic_keys:
        return ""
    return key


def specific_native_id_key(value: Any) -> str:
    key = normalize_key(value)
    if len(key) < 3:
        return ""
    if key in {"none", "null", "unknown", "n a", "na", "000", "999"}:
        return ""
    return key


def is_strong_date_record(record: dict[str, Any]) -> bool:
    precision = (clean_text(record.get("date_precision")) or "").strip().lower()
    return bool(clean_text(record.get("date_iso"))) and precision in STRONG_DATE_PRECISIONS


def normalized_location_key(record: dict[str, Any]) -> str:
    text = record.get("location_raw") or build_location_text(
        record.get("city"),
        record.get("state_province"),
        record.get("country"),
    )
    key = normalize_key(text)
    if not key:
        return ""
    key = re.sub(r"\bunited states(?: of america)?\b", "usa", key)
    tokens: list[str] = []
    for token in TOKEN_RE.findall(key):
        normalized = LOCATION_TOKEN_ALIASES.get(token, token)
        tokens.extend(part for part in normalized.split("_") if part)
    return " ".join(tokens)


def normalized_source_text(record: dict[str, Any]) -> str:
    raw_text = " ".join(
        part
        for part in (
            clean_text(record.get("summary")),
            clean_text(record.get("description")),
            clean_text(record.get("shape_raw")),
            clean_text(record.get("type_raw")),
            clean_text(record.get("duration_raw")),
        )
        if part
    )
    return " ".join(source_tokens(raw_text))


def specific_text_hash(value: str | None) -> str:
    text = clean_text(value)
    if not text or len(text) < EXACT_TEXT_MIN_CHARS:
        return ""
    if len(source_tokens(text)) < TEXT_SIGNATURE_MIN_TOKENS:
        return ""
    return stable_hash(text, length=20)


def source_token_signature(record: dict[str, Any]) -> str:
    tokens = sorted(set(source_tokens(normalized_source_text(record))))
    if len(tokens) < TEXT_SIGNATURE_MIN_TOKENS:
        return ""
    return stable_hash(tokens, length=20)


def specific_time_key(value: Any) -> str:
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


def source_tokens(value: str | None) -> list[str]:
    tokens = [_normalize_source_token(token) for token in TOKEN_RE.findall(normalize_key(value))]
    return [token for token in tokens if token and token not in SOURCE_STOP_WORDS and len(token) > 1]


def rounded_coordinate_key(record: dict[str, Any], *, decimals: int = 3) -> str:
    if normalize_key(record.get("coordinate_source")) not in TRUSTED_EXACT_COORDINATE_SOURCES:
        return ""
    lat = as_float(record.get("lat"))
    lon = as_float(record.get("lon"))
    if lat is None or lon is None:
        return ""
    return f"{round(lat, decimals):.{decimals}f},{round(lon, decimals):.{decimals}f}"


def nearby_coordinate_cell_key(record: dict[str, Any], *, cell_degrees: float = 0.05) -> str:
    if normalize_key(record.get("coordinate_source")) not in TRUSTED_EXACT_COORDINATE_SOURCES:
        return ""
    lat = as_float(record.get("lat"))
    lon = as_float(record.get("lon"))
    if lat is None or lon is None:
        return ""
    lat_cell = int(lat / cell_degrees)
    lon_cell = int(lon / cell_degrees)
    return f"{lat_cell},{lon_cell}"


def record_location_text(record: dict[str, Any]) -> str | None:
    return clean_text(
        record.get("location_raw")
        or build_location_text(record.get("city"), record.get("state_province"), record.get("country"))
    )


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-records", type=Path, default=DEFAULT_SOURCE_RECORDS_PATH)
    parser.add_argument("--deduped-events", type=Path, default=DEFAULT_DEDUPED_EVENTS_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--top-group-limit", type=int, default=20)
    parser.add_argument(
        "--top-group-event-id-limit",
        type=int,
        default=0,
        help=(
            "Optional max current-event IDs to export per top group. "
            "Use 0 to omit IDs and keep the report compact."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional source-record scan limit for smoke tests.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = summarize_expanded_dedupe_opportunities(
        source_records_path=args.source_records,
        deduped_events_path=args.deduped_events,
        top_group_limit=args.top_group_limit,
        top_group_event_id_limit=args.top_group_event_id_limit,
        limit=args.limit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "scanned_source_records": report["scan_counts"]["scanned_source_records"],
                "current_event_count": report["current_canonical_counts"]["current_event_count"],
                "conservative_projected_reduction": report["tier_union_reduction_estimates"]["conservative"][
                    "projected_event_reduction"
                ],
                "moderate_projected_reduction": report["tier_union_reduction_estimates"]["moderate"][
                    "projected_event_reduction"
                ],
                "exploratory_projected_reduction": report["tier_union_reduction_estimates"]["exploratory"][
                    "projected_event_reduction"
                ],
                "aggressive_projected_reduction": report["tier_union_reduction_estimates"]["aggressive"][
                    "projected_event_reduction"
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
