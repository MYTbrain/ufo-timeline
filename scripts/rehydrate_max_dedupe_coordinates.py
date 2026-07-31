"""Rehydrate max-deduped canonical events with served enriched coordinates.

The aggressive dedupe build intentionally works from canonical source records.
The high-mapping web payload, however, also includes later coordinate repair and
geocoding work. This script bridges those outputs by copying the best available
served coordinate for any source record that participates in a max-dedupe event.

It writes a new preview/output directory and does not mutate the promoted
``data/canonical_web`` bundle.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import shutil
from typing import Any, Iterable


DEFAULT_MAX_DEDUPE = Path("data/canonical_full_maximal_v3/deduped_events.jsonl")
DEFAULT_SERVED_WEB = Path("data/canonical_web")
DEFAULT_OUTPUT_DIR = Path("data/canonical_full_maximal_v3_rehydrated_coords")
DEFAULT_REPORT = Path("data/reports/canonical_full_maximal_v3_rehydrated_coords/rehydrate_report.json")

COORDINATE_FIELDS = (
    "lat",
    "lon",
    "coordinate_source",
    "location_precision",
    "geocode_query_used",
    "geocode_display_name",
    "geocode_confidence",
    "mapping_notes",
    "transform_coordinate_repair_action",
    "transform_coordinate_repair_geoname_id",
    "transform_coordinate_repair_geonames_admin1",
    "transform_coordinate_repair_geonames_feature_class",
    "transform_coordinate_repair_geonames_feature_code",
    "transform_coordinate_repair_geonames_name",
    "transform_coordinate_repair_improvement_ratio",
    "transform_coordinate_repair_original_distance_km",
    "transform_coordinate_repair_original_lat",
    "transform_coordinate_repair_original_lon",
    "transform_coordinate_repair_original_source",
    "transform_coordinate_repair_reason",
    "transform_coordinate_repair_transform",
    "transform_coordinate_repair_transformed_distance_km",
    "transform_coordinate_repair_transformed_lat",
    "transform_coordinate_repair_transformed_lon",
)

LOCATION_CONTEXT_FIELDS = ("city", "state_province", "country")

COORDINATE_SOURCE_SCORE = {
    "geocoded": 600,
    "mapped": 560,
    "manual": 540,
    "admin_matched": 530,
    "source_coordinates": 500,
    "raw_latlong": 500,
    "source": 480,
}

LOCATION_PRECISION_SCORE = {
    "exact_coords": 140,
    "coordinate": 140,
    "mapped": 120,
    "city": 100,
    "province": 70,
    "state": 60,
    "country": 30,
}


def rehydrate_max_dedupe_coordinates(
    *,
    max_dedupe_path: Path,
    served_web_dir: Path,
    output_dir: Path,
    report_output: Path,
    copy_supporting_files: bool = True,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_output.parent.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "deduped_events.jsonl"
    tmp_output_path = output_path.with_suffix(".jsonl.tmp")

    index, index_report = build_served_coordinate_index(served_web_dir)

    stats = Counter()
    source_counts: Counter[str] = Counter()
    replacement_source_counts: Counter[str] = Counter()
    match_kind_counts: Counter[str] = Counter()
    no_match_source_counts: Counter[str] = Counter()

    with max_dedupe_path.open("r", encoding="utf-8") as source, tmp_output_path.open(
        "w", encoding="utf-8", newline="\n"
    ) as output:
        for line in source:
            if not line.strip():
                continue
            event = json.loads(line)
            stats["input_events"] += 1
            source_name = clean_text(event.get("source_name")) or "unknown"
            source_counts[source_name] += 1
            if has_usable_coordinates(event):
                stats["mapped_before"] += 1

            candidates = collect_candidates(event, index)
            best = choose_best_candidate(candidates)

            if best is None:
                if not has_usable_coordinates(event):
                    no_match_source_counts[source_name] += 1
                else:
                    stats["mapped_after"] += 1
                output.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
                continue

            updated = apply_candidate(event, best)
            if has_usable_coordinates(updated):
                stats["mapped_after"] += 1
            if coordinate_tuple(updated) != coordinate_tuple(event):
                stats["coordinate_changed"] += 1
                replacement_source_counts[best["coordinate_source"]] += 1
                match_kind_counts[best["match_kind"]] += 1
            elif has_usable_coordinates(event):
                stats["coordinate_retained_with_match"] += 1
            output.write(json.dumps(updated, ensure_ascii=False, separators=(",", ":")) + "\n")

    tmp_output_path.replace(output_path)

    if copy_supporting_files:
        copy_existing_supporting_files(max_dedupe_path.parent, output_dir)

    for key in (
        "input_events",
        "mapped_before",
        "mapped_after",
        "coordinate_changed",
        "coordinate_retained_with_match",
    ):
        stats.setdefault(key, 0)

    report = {
        "schema_version": 1,
        "mode": "preview",
        "inputs": {
            "max_dedupe_path": str(max_dedupe_path),
            "served_web_dir": str(served_web_dir),
        },
        "outputs": {
            "deduped_events": str(output_path),
            "report": str(report_output),
        },
        "index": index_report,
        "counts": dict(stats),
        "source_counts": dict(sorted(source_counts.items())),
        "replacement_coordinate_source_counts": dict(sorted(replacement_source_counts.items())),
        "match_kind_counts": dict(sorted(match_kind_counts.items())),
        "unmapped_no_match_source_counts": dict(sorted(no_match_source_counts.items())),
        "policy": {
            "coordinate_source_score": COORDINATE_SOURCE_SCORE,
            "location_precision_score": LOCATION_PRECISION_SCORE,
            "coordinates_inherited_from_served_web_detail_chunks": True,
            "source_records_joined_by": [
                "canonical_input_id",
                "source_row_hash",
                "source_name/source_file/source_row_number",
                "source_name/source_native_id",
            ],
            "canonical_web_mutated": False,
        },
    }
    write_json(report_output, report)
    return report


def build_served_coordinate_index(served_web_dir: Path) -> tuple[dict[str, dict[Any, list[dict[str, Any]]]], dict[str, Any]]:
    index: dict[str, dict[Any, list[dict[str, Any]]]] = {
        "canonical_input_id": defaultdict(list),
        "source_row_hash": defaultdict(list),
        "source_row": defaultdict(list),
        "source_native_id": defaultdict(list),
    }
    stats = Counter()
    chunk_dir = served_web_dir / "event_chunks"
    for chunk_path in sorted(chunk_dir.glob("chunk_*.json")):
        stats["chunks"] += 1
        for event in read_json(chunk_path):
            stats["served_events"] += 1
            if not has_usable_coordinates(event):
                continue
            stats["served_mapped_events"] += 1
            candidate = coordinate_candidate_from_served_event(event)
            for input_id in canonical_input_ids(event):
                add_candidate(index["canonical_input_id"], input_id, candidate, "canonical_input_id")
            for provenance in source_provenance(event):
                input_id = clean_text(provenance.get("canonical_input_id"))
                if input_id:
                    add_candidate(index["canonical_input_id"], input_id, candidate, "canonical_input_id")
                row_hash = clean_text(provenance.get("source_row_hash"))
                if row_hash:
                    add_candidate(index["source_row_hash"], row_hash, candidate, "source_row_hash")
                row_key = source_row_key(provenance)
                if row_key:
                    add_candidate(index["source_row"], row_key, candidate, "source_row")
                native_key = source_native_key(provenance)
                if native_key:
                    add_candidate(index["source_native_id"], native_key, candidate, "source_native_id")

    return index, {
        "chunks": stats["chunks"],
        "served_events": stats["served_events"],
        "served_mapped_events": stats["served_mapped_events"],
        "index_key_counts": {name: len(bucket) for name, bucket in index.items()},
    }


def collect_candidates(event: dict[str, Any], index: dict[str, dict[Any, list[dict[str, Any]]]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()

    def add_many(items: Iterable[dict[str, Any]]) -> None:
        for item in items:
            key = (
                item.get("served_canonical_event_id"),
                item.get("lat"),
                item.get("lon"),
                item.get("coordinate_source"),
                item.get("match_kind"),
            )
            if key in seen:
                continue
            seen.add(key)
            candidates.append(item)

    for input_id in canonical_input_ids(event):
        add_many(index["canonical_input_id"].get(input_id, []))
    for provenance in source_provenance(event):
        input_id = clean_text(provenance.get("canonical_input_id"))
        if input_id:
            add_many(index["canonical_input_id"].get(input_id, []))
        row_hash = clean_text(provenance.get("source_row_hash"))
        if row_hash:
            add_many(index["source_row_hash"].get(row_hash, []))
        row_key = source_row_key(provenance)
        if row_key:
            add_many(index["source_row"].get(row_key, []))
        native_key = source_native_key(provenance)
        if native_key:
            add_many(index["source_native_id"].get(native_key, []))

    # Fallback for single-record events whose source_provenance was not expanded.
    row_hash = clean_text(event.get("source_row_hash"))
    if row_hash:
        add_many(index["source_row_hash"].get(row_hash, []))
    row_key = source_row_key(event)
    if row_key:
        add_many(index["source_row"].get(row_key, []))
    native_key = source_native_key(event)
    if native_key:
        add_many(index["source_native_id"].get(native_key, []))
    return candidates


def choose_best_candidate(candidates: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    valid = [candidate for candidate in candidates if has_usable_coordinates(candidate)]
    if not valid:
        return None
    return max(valid, key=candidate_score)


def candidate_score(candidate: dict[str, Any]) -> tuple[int, int, int, str]:
    source = clean_text(candidate.get("coordinate_source")).lower()
    precision = clean_text(candidate.get("location_precision")).lower()
    source_score = COORDINATE_SOURCE_SCORE.get(source, 100)
    precision_score = LOCATION_PRECISION_SCORE.get(precision, 0)
    confidence = candidate.get("geocode_confidence")
    confidence_score = int(float(confidence) * 100) if isinstance(confidence, (int, float)) else 0
    return (
        source_score + precision_score + confidence_score,
        1 if candidate.get("match_kind") == "canonical_input_id" else 0,
        -len(clean_text(candidate.get("served_canonical_event_id"))),
        clean_text(candidate.get("served_canonical_event_id")),
    )


def apply_candidate(event: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    if not has_usable_coordinates(candidate):
        return event

    current_score = candidate_score(
        {
            "lat": event.get("lat"),
            "lon": event.get("lon"),
            "coordinate_source": event.get("coordinate_source"),
            "location_precision": event.get("location_precision"),
            "geocode_confidence": event.get("geocode_confidence"),
            "match_kind": "current",
            "served_canonical_event_id": event.get("canonical_event_id"),
        }
    )
    replacement_score = candidate_score(candidate)
    if has_usable_coordinates(event) and current_score >= replacement_score:
        return event

    next_event = dict(event)
    for field in COORDINATE_FIELDS:
        if field in candidate and candidate[field] not in (None, "", [], {}):
            next_event[field] = candidate[field]
    for field in LOCATION_CONTEXT_FIELDS:
        if not clean_text(next_event.get(field)) and clean_text(candidate.get(field)):
            next_event[field] = candidate[field]
    next_event["coordinate_rehydration_source"] = "served_canonical_web"
    next_event["coordinate_rehydration_match_kind"] = candidate.get("match_kind")
    next_event["coordinate_rehydration_served_canonical_event_id"] = candidate.get("served_canonical_event_id")
    next_event["coordinate_rehydration_served_event_id"] = candidate.get("served_event_id")
    next_event["coordinate_rehydration_previous_coordinate_source"] = event.get("coordinate_source")
    next_event["coordinate_rehydration_previous_lat"] = event.get("lat")
    next_event["coordinate_rehydration_previous_lon"] = event.get("lon")
    return next_event


def coordinate_candidate_from_served_event(event: dict[str, Any]) -> dict[str, Any]:
    candidate = {
        field: event.get(field)
        for field in COORDINATE_FIELDS + LOCATION_CONTEXT_FIELDS
        if field in event
    }
    candidate["served_canonical_event_id"] = event.get("canonical_event_id")
    candidate["served_event_id"] = event.get("event_id")
    candidate["canonical_input_ids"] = canonical_input_ids(event)
    candidate["source_provenance"] = source_provenance(event)
    candidate["source"] = event.get("source")
    candidate["source_name"] = event.get("source_name") or event.get("source")
    candidate["source_file"] = event.get("source_file")
    candidate["source_native_id"] = event.get("source_native_id") or event.get("source_id")
    candidate["source_row_number"] = event.get("source_row_number")
    return candidate


def add_candidate(
    bucket: dict[Any, list[dict[str, Any]]],
    key: Any,
    candidate: dict[str, Any],
    match_kind: str,
) -> None:
    if not key:
        return
    item = dict(candidate)
    item["match_kind"] = match_kind
    bucket[key].append(item)


def source_provenance(event: dict[str, Any]) -> list[dict[str, Any]]:
    provenance = event.get("source_provenance")
    if isinstance(provenance, list) and provenance:
        return [item for item in provenance if isinstance(item, dict)]
    if not any(event.get(key) for key in ("source_name", "source", "source_file", "source_row_number", "source_native_id", "source_id", "source_row_hash")):
        return []
    return [
        {
            "source_name": event.get("source_name") or event.get("source"),
            "source_file": event.get("source_file"),
            "source_row_number": event.get("source_row_number"),
            "source_native_id": event.get("source_native_id") or event.get("source_id"),
            "source_row_hash": event.get("source_row_hash"),
            "canonical_input_id": event.get("canonical_input_id"),
        }
    ]


def canonical_input_ids(event: dict[str, Any]) -> list[str]:
    values: list[str] = []
    raw_values = event.get("canonical_input_ids")
    if isinstance(raw_values, list):
        values.extend(clean_text(value) for value in raw_values if clean_text(value))
    single = clean_text(event.get("canonical_input_id"))
    if single:
        values.append(single)
    return sorted(set(values))


def source_row_key(provenance: dict[str, Any]) -> tuple[str, str, int] | None:
    source_name = clean_text(provenance.get("source_name") or provenance.get("source")).lower()
    source_file = clean_text(provenance.get("source_file")).lower()
    row_number = parse_int(provenance.get("source_row_number"))
    if not source_name or not source_file or row_number is None:
        return None
    return (source_name, source_file, row_number)


def source_native_key(provenance: dict[str, Any]) -> tuple[str, str] | None:
    source_name = clean_text(provenance.get("source_name") or provenance.get("source")).lower()
    native_id = clean_text(provenance.get("source_native_id") or provenance.get("source_id"))
    if not source_name or not native_id:
        return None
    return (source_name, native_id)


def has_usable_coordinates(event: dict[str, Any]) -> bool:
    lat = parse_float(event.get("lat"))
    lon = parse_float(event.get("lon"))
    return lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180


def coordinate_tuple(event: dict[str, Any]) -> tuple[float | None, float | None, str]:
    return (
        parse_float(event.get("lat")),
        parse_float(event.get("lon")),
        clean_text(event.get("coordinate_source")).lower(),
    )


def parse_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result else None


def parse_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def copy_existing_supporting_files(source_dir: Path, output_dir: Path) -> None:
    for name in (
        "duplicate_candidates.jsonl",
        "duplicate_groups.jsonl",
        "manual_review_applied_decisions.jsonl",
        "manual_review_decision_schema.json",
        "manual_review_queue.jsonl",
        "source_claims.jsonl",
        "source_records.jsonl",
    ):
        source_path = source_dir / name
        if source_path.exists():
            shutil.copy2(source_path, output_dir / name)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-dedupe", type=Path, default=DEFAULT_MAX_DEDUPE)
    parser.add_argument("--served-web", type=Path, default=DEFAULT_SERVED_WEB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--no-copy-supporting-files", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = rehydrate_max_dedupe_coordinates(
        max_dedupe_path=args.max_dedupe,
        served_web_dir=args.served_web,
        output_dir=args.output_dir,
        report_output=args.report_output,
        copy_supporting_files=not args.no_copy_supporting_files,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
