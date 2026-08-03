"""Packed canonical trace-segment export helpers."""

from __future__ import annotations

from datetime import date
import json
import math
import struct
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .chronology import canonical_playback_sort_tuple
from .trace_scale import TRACE_GAP_BUCKETS, resolve_trace_render_mode, trace_gap_bucket_for_days
from .utils import ensure_parent_dir


SCHEMA_VERSION = 1
TRACE_EVENT_INDEX_FILENAME = "trace_event_index.bin"
TRACE_EVENT_INDEX_META_FILENAME = "trace_event_index_meta.json"
TRACE_SEGMENTS_FILENAME = "trace_segments.bin"
TRACE_SEGMENTS_META_FILENAME = "trace_segments_meta.json"
TRACE_AGGREGATE_BINS_FILENAME = "trace_aggregate_bins.bin"
TRACE_AGGREGATE_BINS_META_FILENAME = "trace_aggregate_bins_meta.json"
MISSING_DATE_KEY = 0

TRACE_AGGREGATE_LEVELS = (
    {"key": "10deg", "label": "10° grid", "cell_size_degrees": 10.0},
    {"key": "5deg", "label": "5° grid", "cell_size_degrees": 5.0},
    {"key": "2_5deg", "label": "2.5° grid", "cell_size_degrees": 2.5},
)

TRACE_EVENT_FIELD_FORMATS: list[tuple[str, str, str, str | None]] = [
    ("event_id", "uint64", "Q", None),
    ("lat", "float64", "d", None),
    ("lon", "float64", "d", None),
    ("sort_ordinal", "int32", "i", None),
    ("sort_date_key", "int32", "i", None),
    ("source_id", "lookup:uint32", "I", "sources"),
    ("chunk_id", "lookup:uint32", "I", "chunk_ids"),
    ("detail_index", "int32", "i", None),
    ("sequence_index", "uint32", "I", None),
]
TRACE_EVENT_ROW_FORMAT = "<" + "".join(field[2] for field in TRACE_EVENT_FIELD_FORMATS)
TRACE_EVENT_ROW_STRUCT = struct.Struct(TRACE_EVENT_ROW_FORMAT)

TRACE_SEGMENT_FIELD_FORMATS: list[tuple[str, str, str, str | None]] = [
    ("from_event_id", "uint64", "Q", None),
    ("to_event_id", "uint64", "Q", None),
    ("from_lat", "float64", "d", None),
    ("from_lon", "float64", "d", None),
    ("to_lat", "float64", "d", None),
    ("to_lon", "float64", "d", None),
    ("from_sort_date_key", "int32", "i", None),
    ("to_sort_date_key", "int32", "i", None),
    ("gap_days", "int32", "i", None),
    ("bucket_id", "lookup:uint32", "I", "gap_buckets"),
    ("source_pair_id", "lookup:uint32", "I", "source_pairs"),
    ("sequence_index", "uint32", "I", None),
]
TRACE_SEGMENT_ROW_FORMAT = "<" + "".join(field[2] for field in TRACE_SEGMENT_FIELD_FORMATS)
TRACE_SEGMENT_ROW_STRUCT = struct.Struct(TRACE_SEGMENT_ROW_FORMAT)

TRACE_AGGREGATE_FIELD_FORMATS: list[tuple[str, str, str, str | None]] = [
    ("level_id", "lookup:uint32", "I", "levels"),
    ("from_lon_cell", "uint16", "H", None),
    ("from_lat_cell", "uint16", "H", None),
    ("to_lon_cell", "uint16", "H", None),
    ("to_lat_cell", "uint16", "H", None),
    ("gap_bucket_id", "lookup:uint32", "I", "gap_buckets"),
    ("segment_count", "uint32", "I", None),
    ("from_lat_mean", "float32", "f", None),
    ("from_lon_mean", "float32", "f", None),
    ("to_lat_mean", "float32", "f", None),
    ("to_lon_mean", "float32", "f", None),
    ("min_sort_date_key", "int32", "i", None),
    ("max_sort_date_key", "int32", "i", None),
    ("min_sequence_index", "uint32", "I", None),
    ("max_sequence_index", "uint32", "I", None),
]
TRACE_AGGREGATE_ROW_FORMAT = "<" + "".join(field[2] for field in TRACE_AGGREGATE_FIELD_FORMATS)
TRACE_AGGREGATE_ROW_STRUCT = struct.Struct(TRACE_AGGREGATE_ROW_FORMAT)

# Backward-compatible aliases for tests/consumers that decode full-sequence segments.
FIELD_FORMATS = TRACE_SEGMENT_FIELD_FORMATS
ROW_FORMAT = TRACE_SEGMENT_ROW_FORMAT
ROW_STRUCT = TRACE_SEGMENT_ROW_STRUCT


def export_trace_artifacts(
    events: Sequence[Mapping[str, Any]],
    output_dir: str | Path,
) -> dict[str, Any]:
    """Write trace event index plus full-sequence diagnostic trace segments."""
    output_path = Path(output_dir)
    mapped_events = sorted(
        (event for event in events if _is_traceable_event(event)),
        key=canonical_playback_sort_tuple,
    )
    segment_inputs = _segment_inputs(mapped_events)
    event_metadata = _write_trace_event_index(mapped_events, output_path)
    segment_metadata = _write_trace_segments(mapped_events, output_path, segment_inputs=segment_inputs)
    aggregate_metadata = _write_trace_aggregate_bins(segment_inputs, output_path)
    return {
        "schema_version": SCHEMA_VERSION,
        "trace_events": event_metadata,
        "trace_segments": segment_metadata,
        "trace_aggregate_bins": aggregate_metadata,
    }


def export_trace_segments(
    events: Sequence[Mapping[str, Any]],
    output_dir: str | Path,
) -> dict[str, Any]:
    """Write consecutive mapped-event trace segments in canonical playback order."""
    return export_trace_artifacts(events, output_dir)["trace_segments"]


def _write_trace_event_index(
    mapped_events: Sequence[Mapping[str, Any]],
    output_path: Path,
) -> dict[str, Any]:
    event_path = output_path / TRACE_EVENT_INDEX_FILENAME
    meta_path = output_path / TRACE_EVENT_INDEX_META_FILENAME
    source_lookup = _build_lookup(mapped_events, lambda event: _clean_text(event.get("source") or event.get("source_name")))
    chunk_lookup = _build_lookup(mapped_events, lambda event: _clean_text(event.get("chunk_id")))

    rows = bytearray()
    for sequence_index, event in enumerate(mapped_events):
        rows.extend(
            TRACE_EVENT_ROW_STRUCT.pack(
                _coerce_event_id(event.get("event_id")),
                _required_float(event.get("lat"), field_name="lat", segment=event),
                _normalize_longitude(_required_float(event.get("lon"), field_name="lon", segment=event)),
                _ordinal(event.get("sort_date_iso")) or MISSING_DATE_KEY,
                _sort_date_key(event.get("sort_date_iso")),
                source_lookup.index_by_value[_clean_text(event.get("source") or event.get("source_name"))],
                chunk_lookup.index_by_value[_clean_text(event.get("chunk_id"))],
                _coerce_int(event.get("detail_index"), default=-1),
                sequence_index,
            )
        )
    ensure_parent_dir(event_path)
    event_path.write_bytes(bytes(rows))

    metadata = {
        "schema_version": SCHEMA_VERSION,
        "row_count": len(mapped_events),
        "bytes_per_row": TRACE_EVENT_ROW_STRUCT.size,
        "endianness": "little",
        "struct_format": TRACE_EVENT_ROW_FORMAT,
        "files": {
            "trace_event_index": TRACE_EVENT_INDEX_FILENAME,
            "metadata": TRACE_EVENT_INDEX_META_FILENAME,
        },
        "fields": _field_metadata(TRACE_EVENT_FIELD_FORMATS),
        "lookup_tables": {
            "sources": source_lookup.values,
            "chunk_ids": chunk_lookup.values,
        },
        "render_contract": {
            "row_order": "canonical_playback_order",
            "filtered_segment_rule": "filter rows first, then connect adjacent visible rows client-side",
            "sequence_index_scope": "full canonical mapped sequence; recompute visible sequence_index and sequence_ratio after filtering",
        },
        "nulls": {
            "sort_date_key": MISSING_DATE_KEY,
            "sort_ordinal": MISSING_DATE_KEY,
            "detail_index": -1,
            "lookup_id": 0,
        },
    }
    _write_metadata(meta_path, metadata)
    return metadata


def _write_trace_segments(
    mapped_events: Sequence[Mapping[str, Any]],
    output_path: Path,
    *,
    segment_inputs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    segments_path = output_path / TRACE_SEGMENTS_FILENAME
    meta_path = output_path / TRACE_SEGMENTS_META_FILENAME

    bucket_lookup = _build_lookup_from_values(bucket["key"] for bucket in TRACE_GAP_BUCKETS)
    source_pair_lookup = _build_lookup(segment_inputs, lambda segment: segment["source_pair"])

    rows = bytearray()
    for segment in segment_inputs:
        rows.extend(
            TRACE_SEGMENT_ROW_STRUCT.pack(
                _coerce_event_id(segment["from_event_id"]),
                _coerce_event_id(segment["to_event_id"]),
                _required_float(segment["from_lat"], field_name="from_lat", segment=segment),
                _required_float(segment["from_lon"], field_name="from_lon", segment=segment),
                _required_float(segment["to_lat"], field_name="to_lat", segment=segment),
                _required_float(segment["to_lon"], field_name="to_lon", segment=segment),
                int(segment["from_sort_date_key"]),
                int(segment["to_sort_date_key"]),
                int(segment["gap_days"]),
                bucket_lookup.index_by_value[segment["bucket"]],
                source_pair_lookup.index_by_value[segment["source_pair"]],
                int(segment["sequence_index"]),
            )
        )

    ensure_parent_dir(segments_path)
    segments_path.write_bytes(bytes(rows))

    bucket_counts = Counter(segment["bucket"] for segment in segment_inputs)
    source_pair_counts = Counter(segment["source_pair"] for segment in segment_inputs)
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "row_count": len(segment_inputs),
        "bytes_per_row": TRACE_SEGMENT_ROW_STRUCT.size,
        "endianness": "little",
        "struct_format": TRACE_SEGMENT_ROW_FORMAT,
        "files": {
            "trace_segments": TRACE_SEGMENTS_FILENAME,
            "metadata": TRACE_SEGMENTS_META_FILENAME,
        },
        "fields": _field_metadata(TRACE_SEGMENT_FIELD_FORMATS),
        "lookup_tables": {
            "gap_buckets": bucket_lookup.values,
            "source_pairs": source_pair_lookup.values,
        },
        "gap_bucket_definitions": list(TRACE_GAP_BUCKETS),
        "counts": {
            "mapped_trace_events": len(mapped_events),
            "trace_segments": len(segment_inputs),
            "gap_bucket_counts": dict(sorted(bucket_counts.items())),
            "source_pair_counts": dict(source_pair_counts.most_common(50)),
        },
        "render_plan": {
            "full_window_mode": resolve_trace_render_mode(len(segment_inputs)),
            "row_order": "canonical_playback_order",
            "segment_rule": "consecutive mapped events after canonical playback ordering",
            "runtime_warning": "Use trace_event_index for exact filtered static trace behavior; this full-sequence segment file is diagnostic/convenience data.",
        },
        "nulls": {
            "sort_date_key": MISSING_DATE_KEY,
        },
    }
    _write_metadata(meta_path, metadata)
    return metadata


def _write_trace_aggregate_bins(
    segment_inputs: Sequence[Mapping[str, Any]],
    output_path: Path,
) -> dict[str, Any]:
    aggregate_path = output_path / TRACE_AGGREGATE_BINS_FILENAME
    meta_path = output_path / TRACE_AGGREGATE_BINS_META_FILENAME

    level_lookup = _lookup_preserve_order(level["key"] for level in TRACE_AGGREGATE_LEVELS)
    bucket_lookup = _lookup_preserve_order(bucket["key"] for bucket in TRACE_GAP_BUCKETS)
    aggregates: dict[tuple[str, int, int, int, int, str], dict[str, Any]] = {}
    for segment in segment_inputs:
        for level in TRACE_AGGREGATE_LEVELS:
            level_key = str(level["key"])
            cell_size = float(level["cell_size_degrees"])
            from_lon_cell, from_lat_cell = _cell_for_point(segment["from_lat"], segment["from_lon"], cell_size)
            to_lon_cell, to_lat_cell = _cell_for_point(segment["to_lat"], segment["to_lon"], cell_size)
            key = (level_key, from_lon_cell, from_lat_cell, to_lon_cell, to_lat_cell, str(segment["bucket"]))
            aggregate = aggregates.setdefault(
                key,
                {
                    "level": level_key,
                    "from_lon_cell": from_lon_cell,
                    "from_lat_cell": from_lat_cell,
                    "to_lon_cell": to_lon_cell,
                    "to_lat_cell": to_lat_cell,
                    "bucket": str(segment["bucket"]),
                    "segment_count": 0,
                    "from_lat_sum": 0.0,
                    "from_lon_sum": 0.0,
                    "to_lat_sum": 0.0,
                    "to_lon_sum": 0.0,
                    "min_sort_date_key": MISSING_DATE_KEY,
                    "max_sort_date_key": MISSING_DATE_KEY,
                    "min_sequence_index": int(segment["sequence_index"]),
                    "max_sequence_index": int(segment["sequence_index"]),
                },
            )
            _add_segment_to_aggregate(aggregate, segment)

    rows = bytearray()
    for aggregate in sorted(
        aggregates.values(),
        key=lambda item: (
            level_lookup.index_by_value[item["level"]],
            item["from_lat_cell"],
            item["from_lon_cell"],
            item["to_lat_cell"],
            item["to_lon_cell"],
            bucket_lookup.index_by_value[item["bucket"]],
        ),
    ):
        count = int(aggregate["segment_count"])
        rows.extend(
            TRACE_AGGREGATE_ROW_STRUCT.pack(
                level_lookup.index_by_value[aggregate["level"]],
                int(aggregate["from_lon_cell"]),
                int(aggregate["from_lat_cell"]),
                int(aggregate["to_lon_cell"]),
                int(aggregate["to_lat_cell"]),
                bucket_lookup.index_by_value[aggregate["bucket"]],
                count,
                float(aggregate["from_lat_sum"]) / count,
                float(aggregate["from_lon_sum"]) / count,
                float(aggregate["to_lat_sum"]) / count,
                float(aggregate["to_lon_sum"]) / count,
                int(aggregate["min_sort_date_key"]),
                int(aggregate["max_sort_date_key"]),
                int(aggregate["min_sequence_index"]),
                int(aggregate["max_sequence_index"]),
            )
        )

    ensure_parent_dir(aggregate_path)
    aggregate_path.write_bytes(bytes(rows))

    level_counts = Counter(aggregate["level"] for aggregate in aggregates.values())
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "row_count": len(aggregates),
        "bytes_per_row": TRACE_AGGREGATE_ROW_STRUCT.size,
        "endianness": "little",
        "struct_format": TRACE_AGGREGATE_ROW_FORMAT,
        "files": {
            "trace_aggregate_bins": TRACE_AGGREGATE_BINS_FILENAME,
            "metadata": TRACE_AGGREGATE_BINS_META_FILENAME,
        },
        "fields": _field_metadata(TRACE_AGGREGATE_FIELD_FORMATS),
        "lookup_tables": {
            "levels": level_lookup.values,
            "gap_buckets": bucket_lookup.values,
        },
        "levels": list(TRACE_AGGREGATE_LEVELS),
        "counts": {
            "input_segments": len(segment_inputs),
            "aggregate_bins": len(aggregates),
            "aggregate_bins_by_level": dict(sorted(level_counts.items())),
        },
        "render_contract": {
            "row_order": "level_then_origin_then_destination_then_gap_bucket",
            "grouping": "level + from cell + to cell + gap bucket",
            "input": "full canonical adjacent trace segments",
            "supported_filter_semantics": ["none/full_universe"],
            "authoritative_filtered_source": TRACE_EVENT_INDEX_FILENAME,
            "runtime_warning": (
                "Use for full-universe wide-window LOD only. For arbitrary filtered traces, filter "
                "trace_event_index rows first and aggregate/connect adjacent visible rows client-side."
            ),
        },
        "cell_indexing": {
            "longitude_origin_degrees": -180.0,
            "latitude_origin_degrees": -90.0,
            "longitude_wrap": "normalize to [-180, 180] before assigning cells",
        },
        "nulls": {
            "sort_date_key": MISSING_DATE_KEY,
        },
    }
    _write_metadata(meta_path, metadata)
    return metadata


def _segment_inputs(mapped_events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        _segment_input(previous, current, sequence_index=index)
        for index, (previous, current) in enumerate(zip(mapped_events, mapped_events[1:]))
    ]


def _field_metadata(field_formats: Sequence[tuple[str, str, str, str | None]]) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    offset = 0
    for name, field_type, fmt, lookup_table in field_formats:
        size = struct.calcsize("<" + fmt)
        field = {
            "name": name,
            "offset": offset,
            "type": field_type,
            "size": size,
        }
        if lookup_table is not None:
            field["lookup_table"] = lookup_table
        fields.append(field)
        offset += size
    return fields


def _write_metadata(path: Path, metadata: Mapping[str, Any]) -> None:
    ensure_parent_dir(path)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _segment_input(previous: Mapping[str, Any], current: Mapping[str, Any], *, sequence_index: int) -> dict[str, Any]:
    from_lon = _normalize_longitude(_required_float(previous.get("lon"), field_name="lon", segment=previous))
    to_lon_raw = _normalize_longitude(_required_float(current.get("lon"), field_name="lon", segment=current))
    to_lon = from_lon + _shortest_longitude_delta(from_lon, to_lon_raw)
    from_ordinal = _ordinal(previous.get("sort_date_iso"))
    to_ordinal = _ordinal(current.get("sort_date_iso"))
    gap_days = abs(to_ordinal - from_ordinal) if from_ordinal is not None and to_ordinal is not None else 0
    return {
        "from_event_id": previous.get("event_id"),
        "to_event_id": current.get("event_id"),
        "from_lat": previous.get("lat"),
        "from_lon": from_lon,
        "to_lat": current.get("lat"),
        "to_lon": to_lon,
        "from_sort_date_key": _sort_date_key(previous.get("sort_date_iso")),
        "to_sort_date_key": _sort_date_key(current.get("sort_date_iso")),
        "gap_days": gap_days,
        "bucket": trace_gap_bucket_for_days(gap_days),
        "source_pair": _source_pair(previous, current),
        "sequence_index": sequence_index,
    }


def _add_segment_to_aggregate(aggregate: dict[str, Any], segment: Mapping[str, Any]) -> None:
    aggregate["segment_count"] += 1
    aggregate["from_lat_sum"] += float(segment["from_lat"])
    aggregate["from_lon_sum"] += float(segment["from_lon"])
    aggregate["to_lat_sum"] += float(segment["to_lat"])
    aggregate["to_lon_sum"] += float(segment["to_lon"])
    from_key = int(segment["from_sort_date_key"])
    to_key = int(segment["to_sort_date_key"])
    if aggregate["min_sort_date_key"] == MISSING_DATE_KEY:
        aggregate["min_sort_date_key"] = min(from_key, to_key)
    else:
        aggregate["min_sort_date_key"] = min(int(aggregate["min_sort_date_key"]), from_key, to_key)
    aggregate["max_sort_date_key"] = max(int(aggregate["max_sort_date_key"]), from_key, to_key)
    sequence_index = int(segment["sequence_index"])
    aggregate["min_sequence_index"] = min(int(aggregate["min_sequence_index"]), sequence_index)
    aggregate["max_sequence_index"] = max(int(aggregate["max_sequence_index"]), sequence_index)


def _cell_for_point(lat: Any, lon: Any, cell_size_degrees: float) -> tuple[int, int]:
    latitude = max(-90.0, min(89.999999, _required_float(lat, field_name="lat", segment={"lat": lat, "lon": lon})))
    longitude = _normalize_longitude(_required_float(lon, field_name="lon", segment={"lat": lat, "lon": lon}))
    longitude = max(-180.0, min(179.999999, longitude))
    lon_cell = int(math.floor((longitude + 180.0) / cell_size_degrees))
    lat_cell = int(math.floor((latitude + 90.0) / cell_size_degrees))
    return lon_cell, lat_cell


def _is_traceable_event(event: Mapping[str, Any]) -> bool:
    return (
        event.get("trace_eligible") is not False
        and event.get("coordinate_source") != "unresolved"
        and _finite_float(event.get("lat")) is not None
        and _finite_float(event.get("lon")) is not None
        and _ordinal(event.get("sort_date_iso")) is not None
    )


def _source_pair(previous: Mapping[str, Any], current: Mapping[str, Any]) -> str:
    previous_source = _clean_text(previous.get("source") or previous.get("source_name")) or "unknown"
    current_source = _clean_text(current.get("source") or current.get("source_name")) or "unknown"
    return f"{previous_source}->{current_source}"


def _sort_date_key(value: Any) -> int:
    text = _clean_text(value)
    if not text:
        return MISSING_DATE_KEY
    try:
        year, month, day = date.fromisoformat(text[:10]).timetuple()[:3]
    except ValueError:
        return MISSING_DATE_KEY
    return (year * 10000) + (month * 100) + day


def _ordinal(value: Any) -> int | None:
    text = _clean_text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10]).toordinal()
    except ValueError:
        return None


def _shortest_longitude_delta(from_lon: float, to_lon: float) -> float:
    delta = to_lon - from_lon
    if delta > 180:
        delta -= 360
    if delta < -180:
        delta += 360
    return delta


def _normalize_longitude(longitude: float) -> float:
    normalized = longitude
    while normalized > 180:
        normalized -= 360
    while normalized < -180:
        normalized += 360
    return normalized


def _finite_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _required_float(value: Any, *, field_name: str, segment: Mapping[str, Any]) -> float:
    number = _finite_float(value)
    if number is None:
        raise ValueError(f"Trace segment has no finite {field_name}: {segment!r}")
    return number


def _coerce_event_id(raw_id: Any) -> int:
    try:
        event_id = int(str(raw_id))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Trace segment has non-integer event_id: {raw_id!r}") from exc
    if event_id < 0 or event_id > 2**64 - 1:
        raise ValueError(f"Trace segment event_id is outside uint64 range: {raw_id!r}")
    return event_id


def _coerce_int(value: Any, *, default: int) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


class _Lookup:
    def __init__(self, values: list[str | None]) -> None:
        self.values = values
        self.index_by_value = {value: index for index, value in enumerate(values)}


def _build_lookup(
    rows: Iterable[Mapping[str, Any]],
    label_func: Callable[[Mapping[str, Any]], str | None],
) -> _Lookup:
    return _build_lookup_from_values(label_func(row) for row in rows)


def _build_lookup_from_values(values: Iterable[str | None]) -> _Lookup:
    labels = sorted(
        {value for value in values if value is not None},
        key=lambda value: (value.casefold(), value),
    )
    return _Lookup([None, *labels])


def _lookup_preserve_order(values: Iterable[str | None]) -> _Lookup:
    labels: list[str | None] = [None]
    seen: set[str | None] = {None}
    for value in values:
        if value is None or value in seen:
            continue
        labels.append(value)
        seen.add(value)
    return _Lookup(labels)


__all__ = [
    "FIELD_FORMATS",
    "MISSING_DATE_KEY",
    "ROW_FORMAT",
    "ROW_STRUCT",
    "SCHEMA_VERSION",
    "TRACE_AGGREGATE_BINS_FILENAME",
    "TRACE_AGGREGATE_BINS_META_FILENAME",
    "TRACE_AGGREGATE_FIELD_FORMATS",
    "TRACE_AGGREGATE_LEVELS",
    "TRACE_AGGREGATE_ROW_FORMAT",
    "TRACE_AGGREGATE_ROW_STRUCT",
    "TRACE_EVENT_FIELD_FORMATS",
    "TRACE_EVENT_INDEX_FILENAME",
    "TRACE_EVENT_INDEX_META_FILENAME",
    "TRACE_EVENT_ROW_FORMAT",
    "TRACE_EVENT_ROW_STRUCT",
    "TRACE_SEGMENT_FIELD_FORMATS",
    "TRACE_SEGMENTS_FILENAME",
    "TRACE_SEGMENTS_META_FILENAME",
    "TRACE_SEGMENT_ROW_FORMAT",
    "TRACE_SEGMENT_ROW_STRUCT",
    "export_trace_artifacts",
    "export_trace_segments",
]
