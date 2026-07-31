"""Score duplicate/entity-resolution candidates without applying merges.

This is a report-only ER scoring prototype. It uses bounded candidate blocks,
scores evidence dimensions independently, and writes candidate bands plus
samples. It never creates decisions or mutates canonical artifacts.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from heapq import heappop, heappush
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable

from scripts.summarize_expanded_dedupe_opportunities import (
    TRUSTED_EXACT_COORDINATE_SOURCES,
    iter_jsonl,
    normalized_id_list,
    normalized_location_key,
    normalized_source_text,
    rounded_coordinate_key,
    source_token_signature,
    source_tokens,
    specific_native_id_key,
    specific_source_url_key,
    specific_text_hash,
    specific_time_key,
)
from parser.canonical_schema import clean_text, normalize_key, stable_hash


DEFAULT_SOURCE_RECORDS_PATH = Path("data/canonical_full/source_records.jsonl")
DEFAULT_DEDUPED_EVENTS_PATH = Path("data/canonical_full/deduped_events.jsonl")
DEFAULT_INPUT_EVENT_LOOKUP_PATH = Path("data/canonical_full/input_event_lookup.jsonl")
DEFAULT_OUTPUT = Path("data/reports/entity_resolution_score_report.json")

BLOCK_FAMILY_DESCRIPTIONS = {
    "same_source_native_id": "Same source family and specific source-native identifier.",
    "strong_date_location_time": "Exact/day date, normalized location, and clock-like time.",
    "strong_date_coordinate_cell_time": "Exact/day date, trusted nearby coordinate cell, and clock-like time.",
    "strong_date_exact_text": "Exact/day date and exact normalized source text.",
    "strong_date_location_text_signature": "Exact/day date, normalized location, and significant-token text signature.",
}

BAND_THRESHOLDS = {
    "likely_same_event_review": 0.86,
    "strong_candidate_review": 0.72,
    "moderate_candidate_review": 0.58,
}

BAND_PRIORITY = {
    "likely_same_event_review": 0,
    "strong_candidate_review": 1,
    "moderate_candidate_review": 2,
    "weak_candidate": 3,
}

COUNTRY_ALIASES = {
    "us": "us",
    "usa": "us",
    "u s": "us",
    "u s a": "us",
    "united states": "us",
    "united states of america": "us",
    "canada": "ca",
    "can": "ca",
    "france": "fr",
    "fra": "fr",
    "germany": "de",
    "ger": "de",
    "deu": "de",
    "austria": "at",
    "aut": "at",
    "switzerland": "ch",
    "sui": "ch",
    "che": "ch",
    "united kingdom": "gb",
    "uk": "gb",
    "gb": "gb",
    "gbr": "gb",
}

REGIONAL_MARKER_KEYS = {"eu", "europe", "as", "asia", "na", "north america", "sa", "south america"}

US_STATE_CODES = {
    "al",
    "ak",
    "az",
    "ar",
    "ca",
    "co",
    "ct",
    "de",
    "fl",
    "ga",
    "hi",
    "id",
    "il",
    "in",
    "ia",
    "ks",
    "ky",
    "la",
    "me",
    "md",
    "ma",
    "mi",
    "mn",
    "ms",
    "mo",
    "mt",
    "ne",
    "nv",
    "nh",
    "nj",
    "nm",
    "ny",
    "nc",
    "nd",
    "oh",
    "ok",
    "or",
    "pa",
    "ri",
    "sc",
    "sd",
    "tn",
    "tx",
    "ut",
    "vt",
    "va",
    "wa",
    "wv",
    "wi",
    "wy",
    "dc",
}

CANADA_PROVINCE_CODES = {"ab", "bc", "mb", "nb", "nl", "ns", "nt", "nu", "on", "pe", "qc", "sk", "yt"}


@dataclass(frozen=True)
class CompactRecord:
    input_id: str
    event_id: str
    source_name: str
    source_file: str | None
    source_row_number: int | None
    source_native_id: str
    date_iso: str | None
    date_precision: str
    time_key: str
    location_key: str
    location_text: str | None
    location_country_key: str
    location_region_key: str
    lat: float | None
    lon: float | None
    coordinate_source: str
    text_normalized: str
    text_hash: str
    text_signature: str
    tokens: tuple[str, ...]
    type_key: str
    shape_key: str
    summary: str | None
    block_keys: tuple[tuple[str, str], ...]


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

    def projected_reduction(self) -> int:
        component_sizes: dict[str, int] = {}
        for value in self.parent:
            root = self.find(value)
            component_sizes[root] = component_sizes.get(root, 0) + 1
        return sum(size - 1 for size in component_sizes.values() if size > 1)


def score_entity_resolution_candidates(
    *,
    source_records_path: Path = DEFAULT_SOURCE_RECORDS_PATH,
    deduped_events_path: Path = DEFAULT_DEDUPED_EVENTS_PATH,
    input_event_lookup_path: Path | None = None,
    max_records_per_block: int = 80,
    max_scored_pairs: int = 500_000,
    top_pair_limit: int = 200,
    band_sample_limit: int = 50,
    candidate_worklist_per_band_limit: int = 0,
    candidate_worklist_min_band: str = "moderate_candidate_review",
    limit: int | None = None,
    offset: int = 0,
) -> dict[str, Any]:
    block_counts, required_input_ids, source_records_scanned, records_with_blocks = scan_candidate_blocks(
        source_records_path,
        limit=limit,
        offset=offset,
    )
    index_summary = build_input_to_event_index_for_ids(
        deduped_events_path,
        required_input_ids=required_input_ids,
        collect_complete_counts=limit is None,
        input_event_lookup_path=input_event_lookup_path,
    )
    input_to_event = index_summary["input_to_event"]

    selected_blocks = {key for key, count in block_counts.items() if count >= 2}
    collected_blocks: dict[tuple[str, str], list[CompactRecord]] = {key: [] for key in selected_blocks}
    oversized_blocks = {key for key in selected_blocks if block_counts[key] > max_records_per_block}
    largest_blocks = sorted(block_counts.items(), key=lambda item: (-item[1], item[0][0], item[0][1]))[:20]

    source_records_collected = 0
    for record in iter_limited_jsonl(source_records_path, limit=limit, offset=offset):
        input_id = clean_text(record.get("canonical_input_id"))
        if not input_id:
            continue
        event_id = input_to_event.get(input_id)
        if not event_id:
            continue
        keys = [key for key in candidate_block_keys(record) if key in selected_blocks]
        if not keys:
            continue
        compact = compact_record(record, event_id=event_id)
        source_records_collected += 1
        for key in keys:
            bucket = collected_blocks[key]
            if len(bucket) < max_records_per_block:
                bucket.append(compact)

    pair_seen: set[tuple[str, str]] = set()
    top_pairs: list[tuple[float, str, dict[str, Any]]] = []
    band_pair_samples: dict[str, list[tuple[float, str, dict[str, Any]]]] = {
        "likely_same_event_review": [],
        "strong_candidate_review": [],
        "moderate_candidate_review": [],
        "weak_candidate": [],
    }
    band_cross_event_pair_samples: dict[str, list[tuple[float, str, dict[str, Any]]]] = {
        "likely_same_event_review": [],
        "strong_candidate_review": [],
        "moderate_candidate_review": [],
        "weak_candidate": [],
    }
    candidate_worklist_samples: dict[str, list[tuple[float, str, dict[str, Any]]]] = {
        "likely_same_event_review": [],
        "strong_candidate_review": [],
        "moderate_candidate_review": [],
        "weak_candidate": [],
    }
    band_counts = {
        "likely_same_event_review": 0,
        "strong_candidate_review": 0,
        "moderate_candidate_review": 0,
        "weak_candidate": 0,
    }
    evidence_counts: dict[str, int] = {}
    risk_flag_counts: dict[str, int] = {}
    band_risk_flag_counts: dict[str, dict[str, int]] = {band: {} for band in band_counts}
    band_source_pair_counts: dict[str, dict[str, int]] = {band: {} for band in band_counts}
    band_unions = {
        "likely_same_event_review": DisjointSet(),
        "strong_or_better": DisjointSet(),
        "moderate_or_better": DisjointSet(),
    }
    family_pair_counts: dict[str, int] = {}
    family_scored_counts: dict[str, int] = {}
    scored_pairs = 0
    cross_event_scored_pairs = 0
    pair_scoring_truncated = False

    for block_key, records in sorted(collected_blocks.items(), key=lambda item: (item[0][0], item[0][1])):
        family_id = block_key[0]
        family_pair_counts[family_id] = family_pair_counts.get(family_id, 0) + choose2(block_counts[block_key])
        ordered = sorted(records, key=lambda item: item.input_id)
        for left_index, left in enumerate(ordered):
            for right in ordered[left_index + 1 :]:
                pair_key = ordered_pair(left.input_id, right.input_id)
                if pair_key in pair_seen:
                    continue
                pair_seen.add(pair_key)
                if scored_pairs >= max_scored_pairs:
                    pair_scoring_truncated = True
                    break
                scored_pairs += 1
                family_scored_counts[family_id] = family_scored_counts.get(family_id, 0) + 1
                score = score_pair(left, right)
                band = score_band(score["score"])
                band_counts[band] += 1
                for evidence in score["evidence"]:
                    evidence_counts[evidence] = evidence_counts.get(evidence, 0) + 1
                for risk_flag in score["risk_flags"]:
                    risk_flag_counts[risk_flag] = risk_flag_counts.get(risk_flag, 0) + 1
                    band_risk_flags = band_risk_flag_counts[band]
                    band_risk_flags[risk_flag] = band_risk_flags.get(risk_flag, 0) + 1
                source_pair_key = "|".join(sorted((left.source_name or "unknown", right.source_name or "unknown")))
                source_pair_bucket = band_source_pair_counts[band]
                source_pair_bucket[source_pair_key] = source_pair_bucket.get(source_pair_key, 0) + 1
                cross_current_event = left.event_id != right.event_id
                if cross_current_event:
                    cross_event_scored_pairs += 1
                    if score["score"] >= BAND_THRESHOLDS["likely_same_event_review"]:
                        band_unions["likely_same_event_review"].union(left.event_id, right.event_id)
                    if score["score"] >= BAND_THRESHOLDS["strong_candidate_review"]:
                        band_unions["strong_or_better"].union(left.event_id, right.event_id)
                    if score["score"] >= BAND_THRESHOLDS["moderate_candidate_review"]:
                        band_unions["moderate_or_better"].union(left.event_id, right.event_id)
                sample = sample_pair(left, right, score=score, band=band)
                sample["blocking_families"] = sorted(
                    family for family, key in candidate_pair_shared_blocks(left, right) if (family, key) in selected_blocks
                )
                keep_top_pair(top_pairs, sample, limit=top_pair_limit)
                keep_top_pair(band_pair_samples[band], sample, limit=band_sample_limit)
                if cross_current_event:
                    keep_top_pair(band_cross_event_pair_samples[band], sample, limit=band_sample_limit)
                    if should_keep_candidate_worklist_item(
                        band,
                        per_band_limit=candidate_worklist_per_band_limit,
                        min_band=candidate_worklist_min_band,
                    ):
                        keep_top_pair(
                            candidate_worklist_samples[band],
                            sample,
                            limit=candidate_worklist_per_band_limit,
                        )
            if pair_scoring_truncated:
                break
        if pair_scoring_truncated:
            break

    candidate_worklist_items = sorted_candidate_worklist_items(candidate_worklist_samples)
    candidate_worklist_summary = {
        "worklist_policy": "entity_resolution_candidate_worklist_report_only",
        "enabled": candidate_worklist_per_band_limit > 0,
        "cross_event_only": True,
        "min_band": candidate_worklist_min_band,
        "per_band_limit": candidate_worklist_per_band_limit,
        "item_count": len(candidate_worklist_items),
        "band_counts": count_samples_by_band(candidate_worklist_items),
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
    }

    report = {
        "schema_version": 1,
        "report_policy": "entity_resolution_scoring_analysis_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "inputs": {
            "source_records": str(source_records_path),
            "deduped_events": str(deduped_events_path),
            "input_event_lookup": str(input_event_lookup_path) if input_event_lookup_path else None,
            "limit": limit,
            "offset": offset,
            "max_records_per_block": max_records_per_block,
            "max_scored_pairs": max_scored_pairs,
            "top_pair_limit": top_pair_limit,
            "band_sample_limit": band_sample_limit,
            "candidate_worklist_per_band_limit": candidate_worklist_per_band_limit,
            "candidate_worklist_min_band": candidate_worklist_min_band,
        },
        "current_corpus": {
            "current_event_count": index_summary["event_count"],
            "current_source_record_count_from_events": index_summary["source_record_count_from_events"],
            "current_exact_duplicate_record_reduction": index_summary["exact_duplicate_record_reduction"],
            "event_index_source": index_summary["event_index_source"],
            "event_index_scope": index_summary["event_index_scope"],
            "event_index_complete": index_summary["event_index_complete"],
            "required_input_index_complete": index_summary["required_input_index_complete"],
            "deduped_events_scanned_for_index": index_summary["deduped_events_scanned"],
            "lookup_rows_scanned_for_index": index_summary["lookup_rows_scanned"],
            "required_input_ids_for_index": index_summary["required_input_id_count"],
            "matched_required_input_ids": index_summary["matched_required_input_id_count"],
            "missing_required_input_ids": index_summary["missing_required_input_id_count"],
        },
        "block_summary": {
            "source_records_scanned": source_records_scanned,
            "source_records_offset": offset,
            "records_with_candidate_blocks": records_with_blocks,
            "candidate_block_count": len(block_counts),
            "selected_multi_record_block_count": len(selected_blocks),
            "oversized_block_count": len(oversized_blocks),
            "source_records_collected_for_scoring": source_records_collected,
            "candidate_pair_upper_bound": sum(choose2(count) for count in block_counts.values() if count >= 2),
            "family_pair_upper_bounds": dict(sorted(family_pair_counts.items())),
            "family_scored_pair_counts": dict(sorted(family_scored_counts.items())),
            "largest_candidate_blocks": [
                {"family": family, "key": key, "record_count": count}
                for (family, key), count in largest_blocks
            ],
        },
        "score_summary": {
            "scored_pair_count": scored_pairs,
            "cross_event_scored_pair_count": cross_event_scored_pairs,
            "pair_scoring_truncated": pair_scoring_truncated,
            "band_counts": band_counts,
            "evidence_counts": dict(sorted(evidence_counts.items())),
            "risk_flag_counts": dict(sorted(risk_flag_counts.items())),
            "band_risk_flag_counts": {
                band: dict(sorted(counts.items()))
                for band, counts in sorted(band_risk_flag_counts.items())
            },
            "band_source_pair_counts": {
                band: dict(sorted(counts.items()))
                for band, counts in sorted(band_source_pair_counts.items())
            },
            "projected_cross_event_reduction": {
                "likely_same_event_review": band_unions["likely_same_event_review"].projected_reduction(),
                "strong_or_better": band_unions["strong_or_better"].projected_reduction(),
                "moderate_or_better": band_unions["moderate_or_better"].projected_reduction(),
            },
            "band_thresholds": BAND_THRESHOLDS,
        },
        "score_model": {
            "dimensions": [
                "date_precision_and_date_match",
                "specific_time_match",
                "location_text_or_trusted_coordinate_distance",
                "source_location_country_region_hint_agreement_or_conflict",
                "normalized_text_hash_or_token_overlap",
                "source_family_and_native_identifier",
                "type_shape_agreement_or_conflict",
                "structured_same_source_date_time_location_pattern",
            ],
            "date_policy": (
                "Only exact-day/day precision earns full same_exact_day evidence; matching coarser dates are "
                "downgraded and flagged."
            ),
            "band_meaning": {
                "likely_same_event_review": "High-confidence review candidate; still not auto-merged.",
                "strong_candidate_review": "Strong review candidate needing human or later policy adjudication.",
                "moderate_candidate_review": "Useful queue candidate; weaker or missing evidence remains.",
                "weak_candidate": "Scored but not prioritized for merge review.",
            },
        },
        "top_scored_pairs": [item[2] for item in sorted(top_pairs, key=lambda item: (-item[0], item[1]))],
        "band_scored_pair_samples": {
            band: [item[2] for item in sorted(samples, key=lambda item: (-item[0], item[1]))]
            for band, samples in sorted(band_pair_samples.items())
        },
        "band_cross_event_scored_pair_samples": {
            band: [item[2] for item in sorted(samples, key=lambda item: (-item[0], item[1]))]
            for band, samples in sorted(band_cross_event_pair_samples.items())
        },
        "candidate_worklist_summary": candidate_worklist_summary,
        "notes": [
            "Scores are review prioritization signals, not merge decisions.",
            "The scorer samples oversized blocks and can truncate total scored pairs to stay bounded.",
            "Only canonical apply/merge code should ever mutate outputs, and this script does not call it.",
        ],
    }
    if candidate_worklist_items:
        report["candidate_worklist_items"] = candidate_worklist_items
    return report


def scan_candidate_blocks(
    source_records_path: Path,
    *,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[dict[tuple[str, str], int], set[str], int, int]:
    block_counts: dict[tuple[str, str], int] = {}
    required_input_ids: set[str] = set()
    source_records_scanned = 0
    records_with_blocks = 0

    for record in iter_limited_jsonl(source_records_path, limit=limit, offset=offset):
        source_records_scanned += 1
        input_id = clean_text(record.get("canonical_input_id"))
        if not input_id:
            continue
        keys = candidate_block_keys(record)
        if not keys:
            continue
        records_with_blocks += 1
        required_input_ids.add(input_id)
        for key in keys:
            block_counts[key] = block_counts.get(key, 0) + 1

    return block_counts, required_input_ids, source_records_scanned, records_with_blocks


def build_input_to_event_index_for_ids(
    deduped_events_path: Path,
    *,
    required_input_ids: set[str],
    collect_complete_counts: bool,
    input_event_lookup_path: Path | None = None,
) -> dict[str, Any]:
    if input_event_lookup_path and input_event_lookup_path.exists():
        return build_input_to_event_index_for_ids_from_lookup(
            input_event_lookup_path,
            required_input_ids=required_input_ids,
            collect_complete_counts=collect_complete_counts,
        )
    return build_input_to_event_index_for_ids_from_deduped_events(
        deduped_events_path,
        required_input_ids=required_input_ids,
        collect_complete_counts=collect_complete_counts,
    )


def build_input_to_event_index_for_ids_from_lookup(
    input_event_lookup_path: Path,
    *,
    required_input_ids: set[str],
    collect_complete_counts: bool,
) -> dict[str, Any]:
    input_to_event: dict[str, str] = {}
    unmatched_input_ids = set(required_input_ids)
    lookup_rows_scanned = 0
    event_ids: set[str] = set()

    if not required_input_ids and not collect_complete_counts:
        return {
            "input_to_event": input_to_event,
            "event_count": None,
            "source_record_count_from_events": None,
            "exact_duplicate_record_reduction": None,
            "event_index_source": "input_event_lookup",
            "event_index_scope": "touched_input_ids",
            "event_index_complete": False,
            "required_input_index_complete": True,
            "deduped_events_scanned": 0,
            "lookup_rows_scanned": 0,
            "required_input_id_count": 0,
            "matched_required_input_id_count": 0,
            "missing_required_input_id_count": 0,
        }

    for row in iter_jsonl(input_event_lookup_path):
        lookup_rows_scanned += 1
        input_id = clean_text(row.get("canonical_input_id"))
        event_id = clean_text(row.get("canonical_event_id"))
        if not input_id or not event_id:
            continue
        if collect_complete_counts:
            event_ids.add(event_id)
        if input_id in unmatched_input_ids:
            input_to_event[input_id] = event_id
            unmatched_input_ids.remove(input_id)
        if not collect_complete_counts and not unmatched_input_ids:
            break

    event_count = len(event_ids) if collect_complete_counts else None
    source_record_count = lookup_rows_scanned if collect_complete_counts else None
    return {
        "input_to_event": input_to_event,
        "event_count": event_count,
        "source_record_count_from_events": source_record_count,
        "exact_duplicate_record_reduction": (
            source_record_count - event_count if source_record_count is not None and event_count is not None else None
        ),
        "event_index_source": "input_event_lookup",
        "event_index_scope": "full_corpus" if collect_complete_counts else "touched_input_ids",
        "event_index_complete": collect_complete_counts,
        "required_input_index_complete": not unmatched_input_ids,
        "deduped_events_scanned": 0,
        "lookup_rows_scanned": lookup_rows_scanned,
        "required_input_id_count": len(required_input_ids),
        "matched_required_input_id_count": len(input_to_event),
        "missing_required_input_id_count": len(unmatched_input_ids),
    }


def build_input_to_event_index_for_ids_from_deduped_events(
    deduped_events_path: Path,
    *,
    required_input_ids: set[str],
    collect_complete_counts: bool,
) -> dict[str, Any]:
    input_to_event: dict[str, str] = {}
    unmatched_input_ids = set(required_input_ids)
    event_count = 0
    source_record_count_from_events = 0
    duplicate_record_count = 0

    if not required_input_ids and not collect_complete_counts:
        return {
            "input_to_event": input_to_event,
            "event_count": None,
            "source_record_count_from_events": None,
            "exact_duplicate_record_reduction": None,
            "event_index_source": "deduped_events",
            "event_index_scope": "touched_input_ids",
            "event_index_complete": False,
            "required_input_index_complete": True,
            "deduped_events_scanned": 0,
            "lookup_rows_scanned": 0,
            "required_input_id_count": 0,
            "matched_required_input_id_count": 0,
            "missing_required_input_id_count": 0,
        }

    for event in iter_jsonl(deduped_events_path):
        event_count += 1
        event_id = clean_text(event.get("canonical_event_id")) or clean_text(event.get("event_id"))
        input_ids = normalized_id_list(event.get("canonical_input_ids"))
        source_record_count_from_events += len(input_ids)
        duplicate_record_count += max(0, len(input_ids) - 1)
        if event_id and unmatched_input_ids:
            for input_id in tuple(input_ids):
                if input_id in unmatched_input_ids:
                    input_to_event[input_id] = event_id
                    unmatched_input_ids.remove(input_id)
        if not collect_complete_counts and not unmatched_input_ids:
            break

    return {
        "input_to_event": input_to_event,
        "event_count": event_count if collect_complete_counts else None,
        "source_record_count_from_events": source_record_count_from_events if collect_complete_counts else None,
        "exact_duplicate_record_reduction": duplicate_record_count if collect_complete_counts else None,
        "event_index_source": "deduped_events",
        "event_index_scope": "full_corpus" if collect_complete_counts else "touched_input_ids",
        "event_index_complete": collect_complete_counts,
        "required_input_index_complete": not unmatched_input_ids,
        "deduped_events_scanned": event_count,
        "lookup_rows_scanned": 0,
        "required_input_id_count": len(required_input_ids),
        "matched_required_input_id_count": len(input_to_event),
        "missing_required_input_id_count": len(unmatched_input_ids),
    }


def iter_limited_jsonl(path: Path, *, limit: int | None = None, offset: int = 0) -> Iterable[dict[str, Any]]:
    emitted = 0
    for index, record in enumerate(iter_jsonl(path), start=1):
        if index <= offset:
            continue
        if limit is not None and emitted >= limit:
            break
        emitted += 1
        yield record


def candidate_block_keys(record: dict[str, Any]) -> list[tuple[str, str]]:
    source_name = normalize_key(record.get("source_name"))
    native_id = specific_native_id_key(record.get("source_native_id"))
    date_iso = clean_text(record.get("date_iso"))
    strong_date = is_strong_date_record(record)
    location_key = normalized_location_key(record)
    time_key = specific_time_key(record.get("time_raw"))
    coord_cell = nearby_coordinate_cell_key(record)
    text_hash = specific_text_hash(normalized_source_text(record))
    text_signature = source_token_signature(record)

    keys: list[tuple[str, str]] = []
    if source_name and native_id:
        keys.append(("same_source_native_id", "|".join((source_name, native_id))))
    if date_iso and strong_date and location_key and time_key:
        keys.append(("strong_date_location_time", "|".join((date_iso, location_key, time_key))))
    if date_iso and strong_date and coord_cell and time_key:
        keys.append(("strong_date_coordinate_cell_time", "|".join((date_iso, coord_cell, time_key))))
    if date_iso and strong_date and text_hash:
        keys.append(("strong_date_exact_text", "|".join((date_iso, text_hash))))
    if date_iso and strong_date and location_key and text_signature:
        keys.append(("strong_date_location_text_signature", "|".join((date_iso, location_key, text_signature))))
    return keys


def candidate_pair_shared_blocks(left: CompactRecord, right: CompactRecord) -> list[tuple[str, str]]:
    return sorted(set(left.block_keys) & set(right.block_keys))


def compact_record(record: dict[str, Any], *, event_id: str) -> CompactRecord:
    text = normalized_source_text(record)
    return CompactRecord(
        input_id=clean_text(record.get("canonical_input_id")) or "",
        event_id=event_id,
        source_name=normalize_key(record.get("source_name")),
        source_file=clean_text(record.get("source_file")),
        source_row_number=as_int(record.get("source_row_number")),
        source_native_id=specific_native_id_key(record.get("source_native_id")),
        date_iso=clean_text(record.get("date_iso")),
        date_precision=(clean_text(record.get("date_precision")) or "").strip().lower(),
        time_key=specific_time_key(record.get("time_raw")),
        location_key=normalized_location_key(record),
        location_text=record_location_text(record),
        location_country_key=location_country_key(record),
        location_region_key=location_region_key(record),
        lat=as_float(record.get("lat")),
        lon=as_float(record.get("lon")),
        coordinate_source=normalize_key(record.get("coordinate_source")),
        text_normalized=text,
        text_hash=specific_text_hash(text),
        text_signature=source_token_signature(record),
        tokens=tuple(sorted(set(source_tokens(text)))),
        type_key=normalize_key(record.get("type_normalized") or record.get("type_raw")),
        shape_key=normalize_key(record.get("shape_normalized") or record.get("shape_raw")),
        summary=snippet(record.get("summary") or record.get("description")),
        block_keys=tuple(candidate_block_keys(record)),
    )


def score_pair(left: CompactRecord, right: CompactRecord) -> dict[str, Any]:
    evidence: list[str] = []
    risks: list[str] = []
    score = 0.0

    if left.date_iso and left.date_iso == right.date_iso and is_compact_strong_date(left) and is_compact_strong_date(right):
        score += 0.20
        evidence.append("same_exact_day")
    elif left.date_iso and left.date_iso == right.date_iso:
        score += 0.08
        evidence.append("same_coarse_or_uncertain_date")
        risks.append("coarse_or_uncertain_date_precision")
    else:
        risks.append("date_mismatch_or_missing")
        score -= 0.12

    if left.time_key and left.time_key == right.time_key:
        score += 0.16
        evidence.append("same_specific_time")
    elif left.time_key or right.time_key:
        risks.append("time_mismatch_or_one_missing")
        score -= 0.04

    location_points = location_score(left, right)
    score += location_points["score"]
    evidence.extend(location_points["evidence"])
    risks.extend(location_points["risks"])

    location_text_points = location_text_hint_score(left, right)
    score += location_text_points["score"]
    evidence.extend(location_text_points["evidence"])
    risks.extend(location_text_points["risks"])

    text_points = text_score(left, right)
    score += text_points["score"]
    evidence.extend(text_points["evidence"])
    risks.extend(text_points["risks"])

    if left.source_name and left.source_name == right.source_name:
        score += 0.06
        evidence.append("same_source_family")
        if left.source_native_id and right.source_native_id and left.source_native_id == right.source_native_id:
            score += 0.18
            evidence.append("same_source_native_id")
        elif left.source_native_id or right.source_native_id:
            score -= 0.03
            risks.append("different_source_native_ids")
    elif left.source_name and right.source_name:
        score += 0.04
        evidence.append("cross_source_candidate")

    if left.type_key and left.type_key == right.type_key:
        score += 0.03
        evidence.append("same_type")
    if left.shape_key and left.shape_key == right.shape_key:
        score += 0.03
        evidence.append("same_shape")
    if left.type_key and right.type_key and left.type_key != right.type_key:
        score -= 0.03
        risks.append("type_differs")
    if left.shape_key and right.shape_key and left.shape_key != right.shape_key:
        score -= 0.03
        risks.append("shape_differs")

    distance = coordinate_distance_km(left, right)
    same_or_near_location = (
        bool(left.location_key and left.location_key == right.location_key)
        or (distance is not None and distance <= 10)
    )
    if (
        left.date_iso
        and left.date_iso == right.date_iso
        and left.source_name
        and left.source_name == right.source_name
        and left.time_key
        and left.time_key == right.time_key
        and same_or_near_location
    ):
        score += 0.04
        evidence.append("structured_same_source_date_time_location_pattern")

    normalized_score = max(0.0, min(1.0, round(score, 3)))
    return {
        "score": normalized_score,
        "evidence": sorted(set(evidence)),
        "risk_flags": sorted(set(risks)),
        "token_jaccard": round(token_jaccard(left.tokens, right.tokens), 3),
        "distance_km": coordinate_distance_km(left, right),
    }


def location_score(left: CompactRecord, right: CompactRecord) -> dict[str, Any]:
    evidence: list[str] = []
    risks: list[str] = []
    score = 0.0
    if left.location_key and left.location_key == right.location_key:
        score = max(score, 0.18)
        evidence.append("same_normalized_location")
    distance = coordinate_distance_km(left, right)
    if distance is not None:
        if distance <= 2:
            score = max(score, 0.20)
            evidence.append("trusted_coordinates_within_2km")
        elif distance <= 10:
            score = max(score, 0.16)
            evidence.append("trusted_coordinates_within_10km")
        elif distance <= 50:
            score = max(score, 0.08)
            evidence.append("trusted_coordinates_within_50km")
        else:
            risks.append("coordinates_far_apart")
            score -= 0.08
    if not evidence:
        risks.append("weak_location_evidence")
    return {"score": score, "evidence": evidence, "risks": risks}


def location_text_hint_score(left: CompactRecord, right: CompactRecord) -> dict[str, Any]:
    evidence: list[str] = []
    risks: list[str] = []
    score = 0.0
    if left.location_country_key and right.location_country_key:
        if left.location_country_key == right.location_country_key:
            score += 0.03
            evidence.append("same_source_location_country_hint")
        else:
            score -= 0.08
            risks.append("source_location_country_hint_conflict")
    if left.location_region_key and right.location_region_key:
        if left.location_region_key == right.location_region_key:
            score += 0.02
            evidence.append("same_source_location_region_hint")
        elif left.location_country_key and left.location_country_key == right.location_country_key:
            score -= 0.03
            risks.append("source_location_region_hint_conflict")
    return {"score": score, "evidence": evidence, "risks": risks}


def text_score(left: CompactRecord, right: CompactRecord) -> dict[str, Any]:
    evidence: list[str] = []
    risks: list[str] = []
    min_token_count = min(len(left.tokens), len(right.tokens))
    if (
        left.text_normalized
        and left.text_normalized == right.text_normalized
        and left.text_hash
        and left.text_hash == right.text_hash
    ):
        if min_token_count < 4:
            return {
                "score": 0.08,
                "evidence": ["same_short_normalized_text"],
                "risks": ["short_text_match_limited"],
            }
        return {"score": 0.20, "evidence": ["same_exact_normalized_text"], "risks": []}
    if left.text_normalized and left.text_normalized == right.text_normalized and min_token_count < 4:
        return {
            "score": 0.08,
            "evidence": ["same_short_normalized_text"],
            "risks": ["short_text_match_limited"],
        }
    jaccard = token_jaccard(left.tokens, right.tokens)
    if min_token_count < 4 and jaccard >= 0.65:
        return {
            "score": 0.03,
            "evidence": ["short_text_token_overlap_limited"],
            "risks": ["short_text_overlap_limited"],
        }
    if jaccard >= 0.85:
        return {"score": 0.17, "evidence": ["very_high_text_token_overlap"], "risks": []}
    if jaccard >= 0.65:
        return {"score": 0.12, "evidence": ["high_text_token_overlap"], "risks": []}
    if jaccard >= 0.45:
        return {"score": 0.06, "evidence": ["moderate_text_token_overlap"], "risks": []}
    risks.append("weak_text_overlap")
    return {"score": 0.0, "evidence": evidence, "risks": risks}


def score_band(score: float) -> str:
    if score >= BAND_THRESHOLDS["likely_same_event_review"]:
        return "likely_same_event_review"
    if score >= BAND_THRESHOLDS["strong_candidate_review"]:
        return "strong_candidate_review"
    if score >= BAND_THRESHOLDS["moderate_candidate_review"]:
        return "moderate_candidate_review"
    return "weak_candidate"


def sample_pair(left: CompactRecord, right: CompactRecord, *, score: dict[str, Any], band: str) -> dict[str, Any]:
    return {
        "pair_id": stable_hash({"left": left.input_id, "right": right.input_id}, prefix="erp_", length=20),
        "score": score["score"],
        "band": band,
        "evidence": score["evidence"],
        "risk_flags": score["risk_flags"],
        "token_jaccard": score["token_jaccard"],
        "distance_km": score["distance_km"],
        "cross_current_event": left.event_id != right.event_id,
        "left": record_sample(left),
        "right": record_sample(right),
    }


def record_sample(record: CompactRecord) -> dict[str, Any]:
    return {
        "canonical_input_id": record.input_id,
        "canonical_event_id": record.event_id,
        "source_name": record.source_name,
        "source_file": record.source_file,
        "source_row_number": record.source_row_number,
        "source_native_id": record.source_native_id,
        "date_iso": record.date_iso,
        "time_key": record.time_key,
        "location": record.location_text,
        "location_country_key": record.location_country_key,
        "location_region_key": record.location_region_key,
        "lat": record.lat,
        "lon": record.lon,
        "type_key": record.type_key,
        "shape_key": record.shape_key,
        "summary": record.summary,
    }


def keep_top_pair(heap: list[tuple[float, str, dict[str, Any]]], sample: dict[str, Any], *, limit: int) -> None:
    if limit <= 0:
        return
    item = (float(sample["score"]), str(sample["pair_id"]), sample)
    if len(heap) < limit:
        heappush(heap, item)
        return
    if item > heap[0]:
        heappop(heap)
        heappush(heap, item)


def should_keep_candidate_worklist_item(
    band: str,
    *,
    per_band_limit: int,
    min_band: str,
) -> bool:
    if per_band_limit <= 0:
        return False
    band_priority = BAND_PRIORITY.get(band)
    min_priority = BAND_PRIORITY.get(min_band)
    if band_priority is None or min_priority is None:
        return False
    return band_priority <= min_priority


def sorted_candidate_worklist_items(
    band_samples: dict[str, list[tuple[float, str, dict[str, Any]]]]
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for band, samples in sorted(band_samples.items(), key=lambda item: BAND_PRIORITY.get(item[0], 99)):
        for rank, item in enumerate(sorted(samples, key=lambda value: (-value[0], value[1])), start=1):
            sample = dict(item[2])
            sample["candidate_worklist_rank"] = rank
            sample["candidate_worklist_policy"] = "entity_resolution_candidate_worklist_report_only"
            items.append(sample)
    return items


def count_samples_by_band(samples: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for sample in samples:
        band = str(sample.get("band") or "unknown")
        counts[band] = counts.get(band, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (BAND_PRIORITY.get(item[0], 99), item[0])))


def is_strong_date_record(record: dict[str, Any]) -> bool:
    return (clean_text(record.get("date_precision")) or "").strip().lower() in {"day", "exact_day"}


def is_compact_strong_date(record: CompactRecord) -> bool:
    return record.date_precision in {"day", "exact_day"}


def nearby_coordinate_cell_key(record: dict[str, Any], *, cell_degrees: float = 0.05) -> str:
    if normalize_key(record.get("coordinate_source")) not in TRUSTED_EXACT_COORDINATE_SOURCES:
        return ""
    lat = as_float(record.get("lat"))
    lon = as_float(record.get("lon"))
    if lat is None or lon is None:
        return ""
    return f"{int(lat / cell_degrees)},{int(lon / cell_degrees)}"


def coordinate_distance_km(left: CompactRecord, right: CompactRecord) -> float | None:
    if left.coordinate_source not in TRUSTED_EXACT_COORDINATE_SOURCES:
        return None
    if right.coordinate_source not in TRUSTED_EXACT_COORDINATE_SOURCES:
        return None
    if left.lat is None or left.lon is None or right.lat is None or right.lon is None:
        return None
    distance = haversine_km(left.lat, left.lon, right.lat, right.lon)
    return round(distance, 3)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def token_jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


def ordered_pair(left: str, right: str) -> tuple[str, str]:
    return (left, right) if left <= right else (right, left)


def choose2(value: int) -> int:
    return value * (value - 1) // 2 if value > 1 else 0


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def record_location_text(record: dict[str, Any]) -> str | None:
    return clean_text(record.get("location_raw"))


def location_country_key(record: dict[str, Any]) -> str:
    explicit = country_alias_key(record.get("country"))
    if explicit:
        return explicit
    for part in reversed(location_parts(record)):
        key = normalize_key(part)
        if key in REGIONAL_MARKER_KEYS:
            continue
        alias = country_alias_key(part)
        if alias:
            return alias
    return ""


def location_region_key(record: dict[str, Any]) -> str:
    explicit = normalize_key(record.get("state_province"))
    country_key = location_country_key(record)
    if country_key == "us":
        if explicit in US_STATE_CODES:
            return f"us:{explicit}"
        for part in reversed(location_parts(record)):
            key = normalize_key(part)
            if key in US_STATE_CODES:
                return f"us:{key}"
    if country_key == "ca":
        if explicit in CANADA_PROVINCE_CODES:
            return f"ca:{explicit}"
        for part in reversed(location_parts(record)):
            key = normalize_key(part)
            if key in CANADA_PROVINCE_CODES:
                return f"ca:{key}"
    return ""


def country_alias_key(value: Any) -> str:
    key = normalize_key(value)
    return COUNTRY_ALIASES.get(key, "")


def location_parts(record: dict[str, Any]) -> list[str]:
    text = clean_text(record.get("location_raw")) or ""
    return [part.strip() for part in re.split(r"[,;/|]+", text) if part.strip()]


def snippet(value: Any, *, limit: int = 180) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip()}..."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-records", type=Path, default=DEFAULT_SOURCE_RECORDS_PATH)
    parser.add_argument("--deduped-events", type=Path, default=DEFAULT_DEDUPED_EVENTS_PATH)
    parser.add_argument(
        "--input-event-lookup",
        type=Path,
        default=DEFAULT_INPUT_EVENT_LOOKUP_PATH,
        help="Optional compact canonical_input_id to canonical_event_id lookup. Used when the file exists.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-records-per-block", type=int, default=80)
    parser.add_argument("--max-scored-pairs", type=int, default=500_000)
    parser.add_argument("--top-pair-limit", type=int, default=200)
    parser.add_argument("--band-sample-limit", type=int, default=50)
    parser.add_argument(
        "--candidate-worklist-output",
        type=Path,
        default=None,
        help="Optional JSONL output for a larger report-only cross-event candidate worklist.",
    )
    parser.add_argument(
        "--candidate-worklist-per-band-limit",
        type=int,
        default=0,
        help="Maximum retained worklist candidates per score band. Only active when greater than zero.",
    )
    parser.add_argument(
        "--candidate-worklist-min-band",
        choices=tuple(BAND_PRIORITY),
        default="moderate_candidate_review",
        help="Lowest-priority band to retain in the optional candidate worklist.",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Skip this many source records before applying --limit. Useful for report-only batch worklists.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    candidate_worklist_per_band_limit = args.candidate_worklist_per_band_limit
    if args.candidate_worklist_output and candidate_worklist_per_band_limit <= 0:
        candidate_worklist_per_band_limit = max(args.band_sample_limit, 1000)
    report = score_entity_resolution_candidates(
        source_records_path=args.source_records,
        deduped_events_path=args.deduped_events,
        input_event_lookup_path=args.input_event_lookup,
        max_records_per_block=args.max_records_per_block,
        max_scored_pairs=args.max_scored_pairs,
        top_pair_limit=args.top_pair_limit,
        band_sample_limit=args.band_sample_limit,
        candidate_worklist_per_band_limit=candidate_worklist_per_band_limit,
        candidate_worklist_min_band=args.candidate_worklist_min_band,
        limit=args.limit,
        offset=args.offset,
    )
    candidate_worklist_items = report.pop("candidate_worklist_items", [])
    if args.candidate_worklist_output:
        args.candidate_worklist_output.parent.mkdir(parents=True, exist_ok=True)
        args.candidate_worklist_output.write_text(
            "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in candidate_worklist_items),
            encoding="utf-8",
        )
        report["candidate_worklist_summary"]["output"] = str(args.candidate_worklist_output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "scored_pair_count": report["score_summary"]["scored_pair_count"],
                "likely_same_event_review": report["score_summary"]["band_counts"]["likely_same_event_review"],
                "strong_candidate_review": report["score_summary"]["band_counts"]["strong_candidate_review"],
                "moderate_candidate_review": report["score_summary"]["band_counts"]["moderate_candidate_review"],
                "candidate_worklist_items": len(candidate_worklist_items),
                "candidate_worklist_output": str(args.candidate_worklist_output) if args.candidate_worklist_output else None,
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
