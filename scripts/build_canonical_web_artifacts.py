"""Build compact static web artifacts from canonical deduped events."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import sys
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from parser.canonical_export import CANONICAL_EVENT_ID_OFFSET
from parser.chronology import enrich_event_with_chronology
from parser.canonical_schema import build_location_text, clean_text, stable_hash
from parser.craft_types import infer_event_craft_type
from parser.locations import infer_text_precision
from parser.packed_points import export_packed_points
from parser.reviewed_event_corrections import apply_reviewed_event_corrections
from parser.taxonomy import (
    display_shape_for_web_event,
    display_type_for_web_event,
    visual_type_group_for_web_event,
)
from parser.trace_segments import export_trace_artifacts
from parser.utils import ensure_parent_dir, write_json


DEFAULT_INPUT = Path("data/canonical_full/deduped_events.jsonl")
DEFAULT_OUTPUT_DIR = Path("data/canonical_web")
DEFAULT_CHUNK_SIZE = 2500
DEFAULT_SUMMARY_SHARD_SIZE = 10000
MERGED_MEMBER_CRAFT_DETAIL_FIELDS = (
    "merged_member_craft_type_candidate",
    "merged_member_craft_type_confidence",
    "merged_member_craft_type_source",
    "merged_member_craft_type_evidence",
    "merged_member_craft_type_member_ids",
    "merged_member_craft_type_member_sources",
    "merged_member_craft_type_conflict",
    "merged_member_craft_type_basis",
    "merged_member_craft_type_status",
)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT),
        help="Canonical deduped_events.jsonl input path.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Output directory for compact web artifacts.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help="Number of compact event details per lazy detail chunk.",
    )
    parser.add_argument(
        "--summary-shard-size",
        type=int,
        default=DEFAULT_SUMMARY_SHARD_SIZE,
        help="Number of compact browser-summary events per optional summary shard.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional input record limit for smoke tests.",
    )
    parser.add_argument(
        "--write-gzip",
        action="store_true",
        help="Write .gz siblings for compact web artifacts and emit compression_report.json.",
    )
    return parser


def build_canonical_web_artifacts(
    *,
    input_path: Path,
    output_dir: Path,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    summary_shard_size: int = DEFAULT_SUMMARY_SHARD_SIZE,
    limit: int | None = None,
    write_gzip: bool = False,
) -> dict[str, Any]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if summary_shard_size <= 0:
        raise ValueError("summary_shard_size must be positive")

    input_path = input_path.resolve()
    output_dir = output_dir.resolve()
    prepare_output_dir(output_dir)
    details_dir = output_dir / "event_chunks"
    summaries_dir = output_dir / "summary_shards"
    details_dir.mkdir(parents=True, exist_ok=True)
    summaries_dir.mkdir(parents=True, exist_ok=True)

    event_id_allocator = StableEventIdAllocator()
    chunk_manifest: list[dict[str, Any]] = []
    summary_manifest: list[dict[str, Any]] = []
    current_chunk: list[dict[str, Any]] = []
    current_point_chunk: list[dict[str, Any]] = []
    current_summary_shard: list[dict[str, Any]] = []
    point_rows: list[dict[str, Any]] = []
    total_events = 0
    mapped_events = 0
    source_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    shape_counts: dict[str, int] = {}
    craft_type_counts: dict[str, int] = {}
    craft_type_confidence_counts: dict[str, int] = {}
    craft_type_source_counts: dict[str, int] = {}
    same_day_match_strength_counts: dict[str, int] = {}
    date_precision_counts: dict[str, int] = {}
    location_precision_counts: dict[str, int] = {}
    coordinate_source_counts: dict[str, int] = {}
    mapped_bounds = MappedBounds()

    reviewed_correction_counts: dict[str, int] = {}
    reviewed_corrected_event_ids: set[str] = set()

    for record in iter_jsonl(input_path, limit=limit):
        record = apply_reviewed_event_corrections(record)
        record_has_reviewed_correction = False
        for correction in record.get("reviewed_corrections") or []:
            if not isinstance(correction, dict):
                continue
            correction_id = clean_text(correction.get("correction_id"))
            if correction_id:
                reviewed_correction_counts[correction_id] = reviewed_correction_counts.get(correction_id, 0) + 1
                record_has_reviewed_correction = True
        if record_has_reviewed_correction:
            reviewed_corrected_event_ids.add(
                first_clean(record, "canonical_event_id", "canonical_input_id")
                or json.dumps(canonical_identity(record), sort_keys=True, separators=(",", ":"))
            )
        total_events += 1
        compact_event = prune_compact_event(
            compact_web_event(record, event_id_allocator=event_id_allocator)
        )
        detail_event = prune_compact_event(detail_web_event(record, compact_event))
        source = compact_event.get("source") or "unknown"
        source_counts[source] = source_counts.get(source, 0) + 1
        event_type = compact_event.get("type") or "Unknown"
        type_counts[event_type] = type_counts.get(event_type, 0) + 1
        shape = compact_event.get("shape_normalized") or "Unknown"
        shape_counts[shape] = shape_counts.get(shape, 0) + 1
        craft_type = compact_event.get("craft_type_inferred") or "unknown"
        craft_type_counts[craft_type] = craft_type_counts.get(craft_type, 0) + 1
        craft_type_confidence = compact_event.get("craft_type_confidence") or "none"
        craft_type_confidence_counts[craft_type_confidence] = craft_type_confidence_counts.get(craft_type_confidence, 0) + 1
        craft_type_source = compact_event.get("craft_type_source") or "none"
        craft_type_source_counts[craft_type_source] = craft_type_source_counts.get(craft_type_source, 0) + 1
        same_day_strength = compact_event.get("same_day_match_strength") or "none"
        same_day_match_strength_counts[same_day_strength] = same_day_match_strength_counts.get(same_day_strength, 0) + 1
        date_precision = compact_event.get("date_precision") or "unknown"
        date_precision_counts[date_precision] = date_precision_counts.get(date_precision, 0) + 1
        location_precision = compact_event.get("location_precision") or "unknown"
        location_precision_counts[location_precision] = location_precision_counts.get(location_precision, 0) + 1
        coordinate_source = compact_event.get("coordinate_source") or "unknown"
        coordinate_source_counts[coordinate_source] = coordinate_source_counts.get(coordinate_source, 0) + 1

        current_chunk.append(detail_event)
        current_point_chunk.append(compact_event)
        if is_mapped_event(compact_event):
            mapped_events += 1
            mapped_bounds.add(compact_event["lat"], compact_event["lon"])

        if len(current_chunk) >= chunk_size:
            flush_detail_chunk(details_dir, chunk_manifest, current_chunk)
            sync_detail_indexes(current_point_chunk, current_chunk)
            point_rows.extend(event for event in current_point_chunk if is_mapped_event(event))
            current_summary_shard = append_summary_events(
                summaries_dir,
                summary_manifest,
                current_summary_shard,
                current_point_chunk,
                summary_shard_size,
            )
            current_chunk = []
            current_point_chunk = []

    if current_chunk:
        flush_detail_chunk(details_dir, chunk_manifest, current_chunk)
        sync_detail_indexes(current_point_chunk, current_chunk)
        point_rows.extend(event for event in current_point_chunk if is_mapped_event(event))
        current_summary_shard = append_summary_events(
            summaries_dir,
            summary_manifest,
            current_summary_shard,
            current_point_chunk,
            summary_shard_size,
        )
    if current_summary_shard:
        flush_summary_shard(summaries_dir, summary_manifest, current_summary_shard)

    points_metadata = export_packed_points(
        point_rows,
        output_dir,
        chunk_manifest=chunk_manifest,
    )
    trace_artifacts_metadata = export_trace_artifacts(point_rows, output_dir)
    trace_events_metadata = trace_artifacts_metadata["trace_events"]
    trace_segments_metadata = trace_artifacts_metadata["trace_segments"]
    trace_aggregate_metadata = trace_artifacts_metadata["trace_aggregate_bins"]
    manifest = {
        "schema_version": 1,
        "source": {
            "input_path": str(input_path),
            "input_limit": limit,
        },
        "artifacts": {
            "points": "points.bin",
            "points_metadata": "points_meta.json",
            "event_chunk_manifest": "event_chunk_manifest.json",
            "event_chunks_dir": "event_chunks",
            "summary_manifest": "summary_manifest.json",
            "summary_shards_dir": "summary_shards",
            "trace_event_index": "trace_event_index.bin",
            "trace_event_index_metadata": "trace_event_index_meta.json",
            "trace_segments": "trace_segments.bin",
            "trace_segments_metadata": "trace_segments_meta.json",
            "trace_aggregate_bins": "trace_aggregate_bins.bin",
            "trace_aggregate_bins_metadata": "trace_aggregate_bins_meta.json",
        },
        "counts": {
            "events": total_events,
            "mapped_events": mapped_events,
            "trace_events": trace_events_metadata.get("row_count"),
            "trace_segments": trace_segments_metadata.get("row_count"),
            "trace_aggregate_bins": trace_aggregate_metadata.get("row_count"),
            "event_chunks": len(chunk_manifest),
            "summary_shards": len(summary_manifest),
            "source_counts": dict(sorted(source_counts.items())),
            "type_counts": top_counts(type_counts, limit=200),
            "shape_counts": top_counts(shape_counts, limit=200),
            "craft_type_counts": top_counts(craft_type_counts, limit=200),
            "craft_type_confidence_counts": dict(sorted(craft_type_confidence_counts.items())),
            "craft_type_source_counts": dict(sorted(craft_type_source_counts.items())),
            "same_day_match_strength_counts": dict(sorted(same_day_match_strength_counts.items())),
            "date_precision_counts": dict(sorted(date_precision_counts.items())),
            "location_precision_counts": dict(sorted(location_precision_counts.items())),
            "coordinate_source_counts": dict(sorted(coordinate_source_counts.items())),
            "mapped_bounds": mapped_bounds.to_json(),
        },
        "packed_points": {
            "schema_version": points_metadata.get("schema_version"),
            "row_count": points_metadata.get("row_count"),
            "bytes_per_row": points_metadata.get("bytes_per_row"),
        },
        "packed_trace_segments": {
            "schema_version": trace_segments_metadata.get("schema_version"),
            "row_count": trace_segments_metadata.get("row_count"),
            "bytes_per_row": trace_segments_metadata.get("bytes_per_row"),
            "full_window_mode": trace_segments_metadata.get("render_plan", {}).get("full_window_mode"),
        },
        "packed_trace_events": {
            "schema_version": trace_events_metadata.get("schema_version"),
            "row_count": trace_events_metadata.get("row_count"),
            "bytes_per_row": trace_events_metadata.get("bytes_per_row"),
            "row_order": trace_events_metadata.get("render_contract", {}).get("row_order"),
            "filtered_segment_rule": trace_events_metadata.get("render_contract", {}).get("filtered_segment_rule"),
        },
        "packed_trace_aggregate_bins": {
            "schema_version": trace_aggregate_metadata.get("schema_version"),
            "row_count": trace_aggregate_metadata.get("row_count"),
            "bytes_per_row": trace_aggregate_metadata.get("bytes_per_row"),
            "runtime_warning": trace_aggregate_metadata.get("render_contract", {}).get("runtime_warning"),
        },
        "policy": {
            "raw_source_rows_included": True,
            "source_claims_included": False,
            "full_provenance_included": True,
            "detail_raw_source_rows_included": True,
            "detail_source_claims_included": False,
            "detail_full_provenance_included": True,
            "detail_chunks_are_lazy_loaded": True,
            "summary_raw_source_rows_included": False,
            "summary_source_claims_included": False,
            "summary_full_provenance_included": False,
            "reviewed_event_corrections": {
                "applied": bool(reviewed_correction_counts),
                "event_count": len(reviewed_corrected_event_ids),
                "correction_counts": dict(sorted(reviewed_correction_counts.items())),
                "raw_source_fields_preserved": True,
            },
        },
    }
    write_json(output_dir / "event_chunk_manifest.json", chunk_manifest, indent=2)
    write_json(output_dir / "summary_manifest.json", summary_manifest, indent=2)
    write_json(output_dir / "canonical_web_manifest.json", manifest, indent=2)
    size_report = artifact_size_report(output_dir)
    write_json(output_dir / "artifact_size_report.json", size_report, indent=2)
    compression_report = None
    if write_gzip:
        compression_report = write_gzip_artifacts(output_dir)
        write_json(output_dir / "compression_report.json", compression_report, indent=2)
    return {
        **manifest["counts"],
        "output_dir": str(output_dir),
        "points_bytes": (output_dir / "points.bin").stat().st_size,
        "trace_event_index_bytes": (output_dir / "trace_event_index.bin").stat().st_size,
        "trace_segments_bytes": (output_dir / "trace_segments.bin").stat().st_size,
        "trace_aggregate_bins_bytes": (output_dir / "trace_aggregate_bins.bin").stat().st_size,
        "total_artifact_bytes": size_report["total_bytes"],
        "total_artifact_mb": size_report["total_mb"],
        "gzip_total_mb": compression_report["total_gzip_mb"] if compression_report else None,
    }


class StableEventIdAllocator:
    def __init__(self) -> None:
        self.used_event_ids: set[int] = set()

    def event_id_for(self, record: dict[str, Any]) -> int:
        identity = canonical_identity(record)
        salt = 0
        while True:
            payload = identity if salt == 0 else {"identity": identity, "collision_salt": salt}
            event_id = CANONICAL_EVENT_ID_OFFSET + int(stable_hash(payload, length=13), 16)
            if event_id not in self.used_event_ids:
                self.used_event_ids.add(event_id)
                return event_id
            salt += 1


class MappedBounds:
    def __init__(self) -> None:
        self.min_lat: float | None = None
        self.max_lat: float | None = None
        self.min_lon: float | None = None
        self.max_lon: float | None = None

    def add(self, lat: float, lon: float) -> None:
        self.min_lat = lat if self.min_lat is None else min(self.min_lat, lat)
        self.max_lat = lat if self.max_lat is None else max(self.max_lat, lat)
        self.min_lon = lon if self.min_lon is None else min(self.min_lon, lon)
        self.max_lon = lon if self.max_lon is None else max(self.max_lon, lon)

    def to_json(self) -> dict[str, float] | None:
        if self.min_lat is None or self.max_lat is None or self.min_lon is None or self.max_lon is None:
            return None
        return {
            "south": self.min_lat,
            "north": self.max_lat,
            "west": self.min_lon,
            "east": self.max_lon,
        }


def iter_jsonl(path: Path, *, limit: int | None = None) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle):
            if limit is not None and index >= limit:
                return
            if not line.strip():
                continue
            yield json.loads(line)


def prepare_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for file_name in (
        "points.bin",
        "points_meta.json",
        "event_chunk_manifest.json",
        "summary_manifest.json",
        "canonical_web_manifest.json",
        "artifact_size_report.json",
        "compression_probe.json",
        "compression_report.json",
        "trace_event_index.bin",
        "trace_event_index_meta.json",
        "trace_segments.bin",
        "trace_segments_meta.json",
        "trace_aggregate_bins.bin",
        "trace_aggregate_bins_meta.json",
    ):
        path = output_dir / file_name
        if path.exists() and path.is_file():
            path.unlink()
        gzip_path = output_dir / f"{file_name}.gz"
        if gzip_path.exists() and gzip_path.is_file():
            gzip_path.unlink()
    chunk_dir = output_dir / "event_chunks"
    if chunk_dir.exists():
        for path in list(chunk_dir.glob("*.json")) + list(chunk_dir.glob("*.json.gz")):
            if path.is_file():
                path.unlink()
    summary_dir = output_dir / "summary_shards"
    if summary_dir.exists():
        for path in list(summary_dir.glob("*.json")) + list(summary_dir.glob("*.json.gz")):
            if path.is_file():
                path.unlink()


def compact_web_event(
    record: dict[str, Any],
    *,
    event_id_allocator: StableEventIdAllocator,
) -> dict[str, Any]:
    location_raw = first_clean(record, "location_raw") or build_location_text(
        record.get("city"),
        record.get("state_province"),
        record.get("country"),
    )
    location_display = first_clean(record, "location_display")
    lat, lon = usable_coordinates(record)
    mapped = lat is not None and lon is not None
    location_precision = normalized_location_precision(
        record.get("location_precision"),
        location_raw=location_raw,
        mapped=mapped,
    )
    source_url = first_clean(record, "source_url_display", "source_url")
    description = first_clean(record, "description_display", "description", "summary")
    source_provenance = record.get("source_provenance") if isinstance(record.get("source_provenance"), list) else []
    canonical_input_ids = record.get("canonical_input_ids") if isinstance(record.get("canonical_input_ids"), list) else []
    if not canonical_input_ids:
        canonical_input_id = first_clean(record, "canonical_input_id")
        canonical_input_ids = [canonical_input_id] if canonical_input_id else []

    projected_type = display_type_for_web_event(record) or "Unknown"
    projected_shape = display_shape_for_web_event(record)
    projected_group = visual_type_group_for_web_event(record)
    craft_input = dict(record)
    craft_input["type_normalized"] = projected_type
    craft_input["shape_normalized"] = projected_shape
    craft_inference = infer_event_craft_type(craft_input)

    return enrich_event_with_chronology(
        {
            "event_id": event_id_allocator.event_id_for(record),
            "canonical_event_id": first_clean(record, "canonical_event_id"),
            "canonical_input_ids": canonical_input_ids,
            "source": first_clean(record, "source_name", "source"),
            "source_file": first_clean(record, "source_file"),
            "source_id": first_clean(record, "source_native_id", "source_id"),
            "source_provenance_count": len(source_provenance) or len(canonical_input_ids),
            "duplicate_record_count": coerce_int(record.get("duplicate_record_count")) or 1,
            "dedupe_strategy": first_clean(record, "dedupe_strategy"),
            "date_raw": first_clean(record, "date_raw"),
            "date_iso": first_clean(record, "date_iso"),
            "end_date_iso": first_clean(record, "end_date_iso"),
            "sort_date_iso": first_clean(record, "sort_date_iso", "date_iso"),
            "date_precision": normalized_date_precision(record.get("date_precision")),
            "time_raw": first_clean(record, "time_raw"),
            "time_display": first_clean(record, "time_display"),
            "location_raw": location_raw,
            "location_display": location_display,
            "lat": lat,
            "lon": lon,
            "has_coordinates": mapped,
            "coordinate_source": normalized_coordinate_source(record.get("coordinate_source"), mapped=mapped),
            "location_precision": location_precision,
            "type": projected_type,
            "type_raw": first_clean(record, "type_raw"),
            "type_normalized": first_clean(record, "type_normalized"),
            "shape_raw": first_clean(record, "shape_raw"),
            "shape_normalized": projected_shape,
            "visual_type_group": first_clean(record, "visual_type_group") or projected_group,
            "craft_type_inferred": craft_inference.get("craft_type_inferred"),
            "craft_type_label": craft_inference.get("craft_type_label"),
            "craft_type_confidence": craft_inference.get("craft_type_confidence"),
            "craft_type_source": craft_inference.get("craft_type_source"),
            "craft_type_reason": craft_inference.get("craft_type_reason"),
            "same_day_match_strength": craft_inference.get("same_day_match_strength"),
            "duration_raw": first_clean(record, "duration_raw"),
            "duration_display": first_clean(record, "duration_display"),
            "summary": first_clean(record, "summary_display", "summary"),
            "description_short": snippet(description, limit=240),
            "links": [source_url] if source_url and source_url.lower().startswith(("http://", "https://")) else [],
        }
    )


def detail_web_event(record: dict[str, Any], compact_event: dict[str, Any]) -> dict[str, Any]:
    """Build the lazy full-detail payload while keeping startup summaries compact."""
    detail = dict(compact_event)
    description = first_clean(record, "description_display", "description", "summary")
    source_url = first_clean(record, "source_url")
    source_url_display = first_clean(record, "source_url_display")
    linked_source_url = source_url_display or source_url
    raw_fields = record.get("raw_fields") if isinstance(record.get("raw_fields"), dict) else None
    source_provenance = record.get("source_provenance") if isinstance(record.get("source_provenance"), list) else None

    detail.update(
        {
            "description": description,
            "description_short": snippet(description, limit=360),
            "source_url": source_url,
            "source_url_display": source_url_display,
            "links": [linked_source_url]
            if linked_source_url and linked_source_url.lower().startswith(("http://", "https://"))
            else [],
            "source_row_number": record.get("source_row_number"),
            "posted_date_raw": first_clean(record, "posted_date_raw"),
            "reported_date_raw": first_clean(record, "reported_date_raw"),
            "city": first_clean(record, "city"),
            "state_province": first_clean(record, "state_province"),
            "country": first_clean(record, "country"),
            "raw_fields": raw_fields,
            "raw_source_header": record.get("raw_source_header"),
            "raw_source_row": record.get("raw_source_row"),
            "raw_source_row_values": record.get("raw_source_row_values"),
            "raw_source_extra_columns": record.get("raw_source_extra_columns"),
            "raw_source_missing_columns": record.get("raw_source_missing_columns"),
            "source_row_anomalies": record.get("source_row_anomalies"),
            "source_provenance": source_provenance,
            "mapping_notes": first_clean(record, "mapping_notes"),
            "reviewed_corrections": record.get("reviewed_corrections"),
        }
    )
    # Merged-member evidence is review/provenance metadata. Preserve it in the
    # lazy full-detail record without allowing it to overwrite the canonical
    # representative's direct craft inference in startup summaries or points.
    detail.update(
        {
            field: record.get(field)
            for field in MERGED_MEMBER_CRAFT_DETAIL_FIELDS
            if field in record
        }
    )
    detail["raw_event_block"] = build_raw_event_block(record, detail)
    return detail


def compact_summary_event(event: dict[str, Any]) -> dict[str, Any]:
    # Browser-summary shards contain only the fields needed for filters,
    # timeline/playback ordering, map rendering, and result-card shells.
    # Full narrative text stays in lazy detail chunks.
    return prune_compact_event(
        {
            "event_id": event.get("event_id"),
            "chunk_id": event.get("chunk_id"),
            "detail_index": event.get("detail_index"),
            "date_raw": event.get("date_raw"),
            "sort_date_iso": event.get("sort_date_iso") or event.get("date_iso"),
            "date_precision": event.get("date_precision"),
            "time_raw": event.get("time_raw"),
            "time_display": event.get("time_display"),
            "time_sort_kind": event.get("time_sort_kind"),
            "time_sort_confidence": event.get("time_sort_confidence"),
            "playback_sort_confidence": event.get("playback_sort_confidence"),
            "playback_sort_reason": event.get("playback_sort_reason"),
            "playback_sort_key": event.get("playback_sort_key"),
            "location_raw": event.get("location_raw"),
            "location_display": event.get("location_display"),
            "source": event.get("source"),
            "type": event.get("type"),
            "coordinate_source": event.get("coordinate_source"),
            "location_precision": event.get("location_precision"),
            "lat": event.get("lat"),
            "lon": event.get("lon"),
            "has_coordinates": event.get("has_coordinates"),
            "shape_normalized": event.get("shape_normalized"),
            "visual_type_group": event.get("visual_type_group"),
            "craft_type_inferred": event.get("craft_type_inferred"),
            "craft_type_label": event.get("craft_type_label"),
            "craft_type_confidence": event.get("craft_type_confidence"),
            "craft_type_source": event.get("craft_type_source"),
            "same_day_match_strength": event.get("same_day_match_strength"),
        }
    )


def append_summary_events(
    summaries_dir: Path,
    summary_manifest: list[dict[str, Any]],
    current_summary_shard: list[dict[str, Any]],
    events: list[dict[str, Any]],
    summary_shard_size: int,
) -> list[dict[str, Any]]:
    for event in events:
        current_summary_shard.append(compact_summary_event(event))
        if len(current_summary_shard) >= summary_shard_size:
            flush_summary_shard(summaries_dir, summary_manifest, current_summary_shard)
            current_summary_shard = []
    return current_summary_shard


def sync_detail_indexes(compact_events: list[dict[str, Any]], detail_events: list[dict[str, Any]]) -> None:
    if len(compact_events) != len(detail_events):
        raise ValueError("compact/detail event chunk length mismatch")
    for compact_event, detail_event in zip(compact_events, detail_events):
        compact_event["chunk_id"] = detail_event.get("chunk_id")
        compact_event["detail_index"] = detail_event.get("detail_index")


def canonical_identity(record: dict[str, Any]) -> dict[str, Any]:
    canonical_event_id = first_clean(record, "canonical_event_id")
    if canonical_event_id:
        return {"canonical_event_id": canonical_event_id}
    canonical_input_ids = record.get("canonical_input_ids")
    if isinstance(canonical_input_ids, list) and canonical_input_ids:
        return {"canonical_input_ids": canonical_input_ids}
    canonical_input_id = first_clean(record, "canonical_input_id")
    if canonical_input_id:
        return {"canonical_input_id": canonical_input_id}
    return {
        key: record.get(key)
        for key in ("source_name", "source_file", "source_row_number", "source_native_id", "source_row_hash")
        if record.get(key) not in (None, "")
    }


def flush_detail_chunk(
    details_dir: Path,
    chunk_manifest: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> None:
    chunk_index = len(chunk_manifest)
    chunk_id = f"chunk_{chunk_index:06d}"
    chunk_file = f"{chunk_id}.json"
    for detail_index, event in enumerate(events):
        event["chunk_id"] = chunk_id
        event["detail_index"] = detail_index
    write_compact_json(details_dir / chunk_file, events)
    chunk_manifest.append(
        {
            "id": chunk_id,
            "file": chunk_file,
            "event_count": len(events),
            "start_event_id": events[0].get("event_id"),
            "end_event_id": events[-1].get("event_id"),
        }
    )


def flush_summary_shard(
    summaries_dir: Path,
    summary_manifest: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> None:
    shard_index = len(summary_manifest)
    shard_id = f"summary_{shard_index:06d}"
    shard_file = f"{shard_id}.json"
    write_compact_json(summaries_dir / shard_file, events)
    summary_manifest.append(
        {
            "id": shard_id,
            "file": shard_file,
            "event_count": len(events),
            "start_event_id": events[0].get("event_id"),
            "end_event_id": events[-1].get("event_id"),
        }
    )


def build_raw_event_block(record: dict[str, Any], detail: dict[str, Any]) -> str | None:
    lines = []
    pairs = [
        ("Source", detail.get("source")),
        ("Source file", detail.get("source_file")),
        ("Source ID", detail.get("source_id")),
        ("Source row", detail.get("source_row_number")),
        ("Date", record.get("date_raw") or record.get("sort_date_iso")),
        ("Time", record.get("time_raw")),
        ("Location", record.get("location_raw")),
        ("Type", detail.get("type")),
        ("Shape", detail.get("shape_raw") or detail.get("shape_normalized")),
        ("Duration", record.get("duration_raw")),
        ("Description", first_clean(record, "description", "summary")),
    ]
    for label, value in pairs:
        text = clean_text(value)
        if text:
            lines.append(f"{label}: {text}")

    raw_fields = record.get("raw_fields")
    if isinstance(raw_fields, dict) and raw_fields:
        lines.append("")
        lines.append("Raw source fields:")
        for key in sorted(raw_fields):
            value = clean_text(raw_fields.get(key))
            if value:
                lines.append(f"{key}: {value}")

    return "\n".join(lines).strip() or None


def artifact_size_report(output_dir: Path) -> dict[str, Any]:
    files = []
    for path in sorted(output_dir.rglob("*")):
        if (
            not path.is_file()
            or path.name in {"artifact_size_report.json", "compression_probe.json", "compression_report.json"}
            or path.suffix == ".gz"
        ):
            continue
        size_bytes = path.stat().st_size
        files.append(
            {
                "path": str(path.relative_to(output_dir)).replace("\\", "/"),
                "bytes": size_bytes,
                "mb": round(size_bytes / (1024 * 1024), 2),
            }
        )
    files.sort(key=lambda item: (-item["bytes"], item["path"]))
    total_bytes = sum(item["bytes"] for item in files)
    return {
        "total_files": len(files),
        "total_bytes": total_bytes,
        "total_mb": round(total_bytes / (1024 * 1024), 2),
        "files": files,
    }


def top_counts(counts: dict[str, int], *, limit: int) -> dict[str, int]:
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0].casefold()))
    return dict(ordered[:limit])


def write_compact_json(path: Path, payload: Any) -> None:
    ensure_parent_dir(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def write_gzip_artifacts(output_dir: Path) -> dict[str, Any]:
    files = []
    for path in sorted(output_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.name in {"artifact_size_report.json", "compression_probe.json", "compression_report.json"}:
            continue
        if path.suffix == ".gz":
            continue
        raw_bytes = path.read_bytes()
        gzip_path = path.with_name(f"{path.name}.gz")
        gzip_bytes = gzip.compress(raw_bytes, compresslevel=6)
        gzip_path.write_bytes(gzip_bytes)
        relative_path = str(path.relative_to(output_dir)).replace("\\", "/")
        files.append(
            {
                "path": relative_path,
                "gzip_path": str(gzip_path.relative_to(output_dir)).replace("\\", "/"),
                "bytes": len(raw_bytes),
                "gzip_bytes": len(gzip_bytes),
                "gzip_ratio": round(len(gzip_bytes) / len(raw_bytes), 3) if raw_bytes else 0,
            }
        )
    total_bytes = sum(item["bytes"] for item in files)
    total_gzip_bytes = sum(item["gzip_bytes"] for item in files)
    return {
        "total_files": len(files),
        "total_bytes": total_bytes,
        "total_mb": round(total_bytes / (1024 * 1024), 2),
        "total_gzip_bytes": total_gzip_bytes,
        "total_gzip_mb": round(total_gzip_bytes / (1024 * 1024), 2),
        "gzip_ratio": round(total_gzip_bytes / total_bytes, 3) if total_bytes else 0,
        "files": sorted(files, key=lambda item: (-item["bytes"], item["path"])),
    }


def prune_compact_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in event.items()
        if value is not None and value != [] and value != ""
    }


def is_mapped_event(event: dict[str, Any]) -> bool:
    return event.get("lat") is not None and event.get("lon") is not None and event.get("coordinate_source") != "unresolved"


def usable_coordinates(record: dict[str, Any]) -> tuple[float | None, float | None]:
    lat = finite_float(record.get("lat"))
    lon = finite_float(record.get("lon"))
    if lat is None or lon is None:
        return None, None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None, None
    return lat, lon


def finite_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def normalized_coordinate_source(value: Any, *, mapped: bool) -> str:
    if not mapped:
        return "unresolved"
    text = clean_string(value)
    if text in {"raw_latlong", "location_coordinates", "geocoded", "manual_fallback"}:
        return text
    return "raw_latlong"


def normalized_location_precision(value: Any, *, location_raw: str | None, mapped: bool) -> str:
    text = clean_string(value)
    if mapped and text in {"coordinate", "coordinates", "exact", "exact_coords", "source_coordinates"}:
        return "exact_coords"
    if text in {"exact_coords", "city", "state", "province", "region", "country", "approximate", "unknown"}:
        return text
    if location_raw:
        return infer_text_precision(location_raw)
    return "unknown"


def normalized_date_precision(value: Any) -> str:
    text = clean_string(value)
    if text == "day":
        return "exact_day"
    return text or "unknown"


def first_clean(record: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = clean_string(record.get(key))
        if value:
            return value
    return None


def clean_string(value: Any) -> str | None:
    return clean_text(value)


def coerce_int(value: Any) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def snippet(value: str | None, *, limit: int) -> str | None:
    text = clean_string(value)
    if text is None or len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip()}..."


def main() -> int:
    args = build_argument_parser().parse_args()
    summary = build_canonical_web_artifacts(
        input_path=Path(args.input),
        output_dir=Path(args.output_dir),
        chunk_size=args.chunk_size,
        limit=args.limit,
        write_gzip=args.write_gzip,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
