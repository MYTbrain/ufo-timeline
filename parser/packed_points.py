"""Deterministic binary point index export for mapped UFO events."""

from __future__ import annotations

import json
import math
import re
import struct
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .utils import ensure_parent_dir


SCHEMA_VERSION = 3
POINTS_FILENAME = "points.bin"
META_FILENAME = "points_meta.json"
MISSING_INT64 = -(2**63)
MISSING_DETAIL_INDEX = -1

__all__ = [
    "META_FILENAME",
    "MISSING_DETAIL_INDEX",
    "MISSING_INT64",
    "POINTS_FILENAME",
    "SCHEMA_VERSION",
    "export_packed_points",
]

FIELD_FORMATS: list[tuple[str, str, str, str | None]] = [
    ("event_id", "uint64", "Q", None),
    ("lat", "float64", "d", None),
    ("lon", "float64", "d", None),
    ("sort_date_key", "int32", "i", None),
    ("sort_time_ms", "int64", "q", None),
    ("source_id", "lookup:uint32", "I", "sources"),
    ("type_id", "lookup:uint32", "I", "types"),
    ("shape_id", "lookup:uint32", "I", "shapes"),
    ("visual_type_group_id", "lookup:uint32", "I", "visual_type_groups"),
    ("craft_type_id", "lookup:uint32", "I", "craft_types"),
    ("craft_type_confidence_id", "lookup:uint32", "I", "craft_type_confidences"),
    ("craft_type_source_id", "lookup:uint32", "I", "craft_type_sources"),
    ("same_day_match_strength_id", "lookup:uint32", "I", "same_day_match_strengths"),
    ("date_precision_id", "lookup:uint32", "I", "date_precisions"),
    ("location_precision_id", "lookup:uint32", "I", "location_precisions"),
    ("coordinate_source_id", "lookup:uint32", "I", "coordinate_sources"),
    ("chunk_id", "lookup:uint32", "I", "chunk_ids"),
    ("detail_index", "int32", "i", None),
]
ROW_FORMAT = "<" + "".join(field[2] for field in FIELD_FORMATS)
ROW_STRUCT = struct.Struct(ROW_FORMAT)

DATE_RE = re.compile(r"^(?P<year>\d{1,4})-(?P<month>\d{2})-(?P<day>\d{2})")


def export_packed_points(
    events: Sequence[Mapping[str, Any]],
    output_dir: str | Path,
    *,
    chunk_manifest: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Write mapped point rows to ``points.bin`` and ``points_meta.json``.

    The exporter accepts either normalized events or already-filtered map events.
    Rows are emitted in input order after filtering out records without usable
    coordinates or with ``coordinate_source == "unresolved"``. Chunk manifest
    ranges identify chunks; detail indexes come from event fields or ordered
    manifest details, not from event-id arithmetic.
    """
    output_path = Path(output_dir)
    points_path = output_path / POINTS_FILENAME
    meta_path = output_path / META_FILENAME

    mapped_events = [event for event in events if _is_mapped_event(event)]
    chunk_reference = _build_chunk_reference(chunk_manifest or [])
    chunk_details = [_chunk_detail_for_event(event, chunk_reference) for event in mapped_events]

    source_lookup = _build_lookup(mapped_events, _source_label)
    type_lookup = _build_lookup(mapped_events, _type_label)
    shape_lookup = _build_lookup(mapped_events, _shape_label)
    visual_type_group_lookup = _build_lookup(mapped_events, _visual_type_group_label)
    craft_type_lookup = _build_lookup(mapped_events, _craft_type_label)
    craft_type_confidence_lookup = _build_lookup(mapped_events, _craft_type_confidence_label)
    craft_type_source_lookup = _build_lookup(mapped_events, _craft_type_source_label)
    same_day_match_strength_lookup = _build_lookup(mapped_events, _same_day_match_strength_label)
    date_precision_lookup = _build_lookup(mapped_events, _date_precision_label)
    location_precision_lookup = _build_lookup(mapped_events, _location_precision_label)
    coordinate_source_lookup = _build_lookup(mapped_events, _coordinate_source_label)
    chunk_lookup = _build_lookup_from_values(chunk_id for chunk_id, _ in chunk_details)

    rows = bytearray()
    for event, (chunk_id, detail_index) in zip(mapped_events, chunk_details):
        rows.extend(
            ROW_STRUCT.pack(
                _coerce_event_id(event),
                _required_float(event.get("lat"), field_name="lat", event=event),
                _required_float(event.get("lon"), field_name="lon", event=event),
                _sort_date_key(event),
                _sort_time_ms(event),
                source_lookup.index_by_value[_source_label(event)],
                type_lookup.index_by_value[_type_label(event)],
                shape_lookup.index_by_value[_shape_label(event)],
                visual_type_group_lookup.index_by_value[_visual_type_group_label(event)],
                craft_type_lookup.index_by_value[_craft_type_label(event)],
                craft_type_confidence_lookup.index_by_value[_craft_type_confidence_label(event)],
                craft_type_source_lookup.index_by_value[_craft_type_source_label(event)],
                same_day_match_strength_lookup.index_by_value[_same_day_match_strength_label(event)],
                date_precision_lookup.index_by_value[_date_precision_label(event)],
                location_precision_lookup.index_by_value[_location_precision_label(event)],
                coordinate_source_lookup.index_by_value[_coordinate_source_label(event)],
                chunk_lookup.index_by_value[chunk_id],
                detail_index,
            )
        )

    ensure_parent_dir(points_path)
    points_path.write_bytes(bytes(rows))

    metadata = {
        "schema_version": SCHEMA_VERSION,
        "row_count": len(mapped_events),
        "bytes_per_row": ROW_STRUCT.size,
        "endianness": "little",
        "struct_format": ROW_FORMAT,
        "files": {
            "points": POINTS_FILENAME,
            "metadata": META_FILENAME,
        },
        "fields": _field_metadata(),
        "lookup_tables": {
            "sources": source_lookup.values,
            "types": type_lookup.values,
            "shapes": shape_lookup.values,
            "visual_type_groups": visual_type_group_lookup.values,
            "craft_types": craft_type_lookup.values,
            "craft_type_confidences": craft_type_confidence_lookup.values,
            "craft_type_sources": craft_type_source_lookup.values,
            "same_day_match_strengths": same_day_match_strength_lookup.values,
            "date_precisions": date_precision_lookup.values,
            "location_precisions": location_precision_lookup.values,
            "coordinate_sources": coordinate_source_lookup.values,
            "chunk_ids": chunk_lookup.values,
        },
        "detail_lookup": {
            "chunk_field": "chunk_id",
            "chunk_lookup_table": "chunk_ids",
            "detail_index_field": "detail_index",
            "missing_detail_index": MISSING_DETAIL_INDEX,
        },
        "nulls": {
            "lookup_id": 0,
            "sort_date_key": 0,
            "sort_time_ms": MISSING_INT64,
        },
        "input": {
            "event_count": len(events),
            "mapped_event_count": len(mapped_events),
            "skipped_event_count": len(events) - len(mapped_events),
            "row_order": "input_order",
        },
    }
    ensure_parent_dir(meta_path)
    with meta_path.open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")

    return metadata


class _Lookup:
    def __init__(self, values: list[str | None]) -> None:
        self.values = values
        self.index_by_value = {value: index for index, value in enumerate(values)}


def _field_metadata() -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    offset = 0
    for name, field_type, fmt, lookup_table in FIELD_FORMATS:
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


def _is_mapped_event(event: Mapping[str, Any]) -> bool:
    if event.get("coordinate_source") == "unresolved":
        return False
    return _finite_float(event.get("lat")) is not None and _finite_float(event.get("lon")) is not None


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


def _required_float(value: Any, *, field_name: str, event: Mapping[str, Any]) -> float:
    number = _finite_float(value)
    if number is None:
        raise ValueError(f"Event {event.get('event_id')!r} has no finite {field_name}.")
    return number


def _coerce_event_id(event: Mapping[str, Any]) -> int:
    return _coerce_event_id_value(event.get("event_id"))


def _coerce_event_id_value(raw_id: Any) -> int:
    try:
        event_id = int(str(raw_id))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Mapped event has non-integer event_id: {raw_id!r}") from exc
    if event_id < 0 or event_id > 2**64 - 1:
        raise ValueError(f"Mapped event_id is outside uint64 range: {raw_id!r}")
    return event_id


def _sort_date_key(event: Mapping[str, Any]) -> int:
    for key in ("sort_date_iso", "date_iso"):
        raw_value = event.get(key)
        if not raw_value:
            continue
        match = DATE_RE.match(str(raw_value))
        if not match:
            continue
        year = int(match.group("year"))
        month = int(match.group("month"))
        day = int(match.group("day"))
        if 1 <= month <= 12 and 1 <= day <= 31:
            return (year * 10000) + (month * 100) + day
    return 0


def _sort_time_ms(event: Mapping[str, Any]) -> int:
    for key in ("estimated_utc_timestamp_ms", "sort_time_ms"):
        raw_value = event.get(key)
        if raw_value is None or raw_value == "":
            continue
        try:
            number = int(round(float(raw_value)))
        except (TypeError, ValueError):
            continue
        if MISSING_INT64 < number < 2**63:
            return number
    return MISSING_INT64


def _source_label(event: Mapping[str, Any]) -> str | None:
    return _first_text(event, "source", "source_name")


def _type_label(event: Mapping[str, Any]) -> str | None:
    return _first_text(event, "type", "type_normalized", "type_raw")


def _shape_label(event: Mapping[str, Any]) -> str | None:
    extra_data = event.get("extra_data")
    extra_shape = extra_data.get("shape") if isinstance(extra_data, Mapping) else None
    return _first_text(event, "shape_normalized", "shape") or _clean_text(extra_shape)


def _visual_type_group_label(event: Mapping[str, Any]) -> str | None:
    return _first_text(event, "visual_type_group")


def _craft_type_label(event: Mapping[str, Any]) -> str | None:
    return _first_text(event, "craft_type_inferred")


def _craft_type_confidence_label(event: Mapping[str, Any]) -> str | None:
    return _first_text(event, "craft_type_confidence")


def _craft_type_source_label(event: Mapping[str, Any]) -> str | None:
    return _first_text(event, "craft_type_source")


def _same_day_match_strength_label(event: Mapping[str, Any]) -> str | None:
    return _first_text(event, "same_day_match_strength")


def _date_precision_label(event: Mapping[str, Any]) -> str | None:
    return _first_text(event, "date_precision")


def _location_precision_label(event: Mapping[str, Any]) -> str | None:
    return _first_text(event, "location_precision")


def _coordinate_source_label(event: Mapping[str, Any]) -> str | None:
    return _first_text(event, "coordinate_source")


def _first_text(event: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = _clean_text(event.get(key))
        if value is not None:
            return value
    return None


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def _build_lookup(
    events: Iterable[Mapping[str, Any]],
    label_func: Callable[[Mapping[str, Any]], str | None],
) -> _Lookup:
    return _build_lookup_from_values(label_func(event) for event in events)


def _build_lookup_from_values(values: Iterable[str | None]) -> _Lookup:
    labels = sorted(
        {value for value in values if value is not None},
        key=lambda value: (value.casefold(), value),
    )
    return _Lookup([None, *labels])


class _ChunkReference:
    def __init__(
        self,
        ranges: list[tuple[int, int, str]],
        detail_indexes_by_event_id: dict[int, tuple[str, int]],
    ) -> None:
        self.ranges = ranges
        self.detail_indexes_by_event_id = detail_indexes_by_event_id


def _build_chunk_reference(manifest: Sequence[Mapping[str, Any]]) -> _ChunkReference:
    ranges: list[tuple[int, int, str]] = []
    detail_indexes_by_event_id: dict[int, tuple[str, int]] = {}
    for item in manifest:
        chunk_id = _clean_text(item.get("id") or item.get("chunk_id"))
        if chunk_id is None:
            continue
        try:
            start = int(str(item.get("start_event_id")))
            end = int(str(item.get("end_event_id")))
        except (TypeError, ValueError):
            pass
        else:
            ranges.append((start, end, chunk_id))
        for event_id, detail_index in _iter_manifest_detail_indexes(item):
            detail_indexes_by_event_id.setdefault(event_id, (chunk_id, detail_index))
    ranges.sort(key=lambda item: (item[0], item[1], item[2]))
    return _ChunkReference(ranges=ranges, detail_indexes_by_event_id=detail_indexes_by_event_id)


def _iter_manifest_detail_indexes(item: Mapping[str, Any]) -> Iterable[tuple[int, int]]:
    for field_name in ("details", "events", "event_ids"):
        raw_details = item.get(field_name)
        if not _is_list_like(raw_details):
            continue
        for fallback_index, raw_detail in enumerate(raw_details):
            event_id, detail_index = _manifest_detail_index(raw_detail, fallback_index)
            if event_id is not None and detail_index != MISSING_DETAIL_INDEX:
                yield event_id, detail_index


def _manifest_detail_index(raw_detail: Any, fallback_index: int) -> tuple[int | None, int]:
    if isinstance(raw_detail, Mapping):
        raw_event_id = raw_detail.get("event_id")
        detail_index = _coerce_detail_index(
            raw_detail.get("detail_index")
            if "detail_index" in raw_detail
            else raw_detail.get("chunk_event_index", raw_detail.get("detail_row_index"))
        )
    else:
        raw_event_id = raw_detail
        detail_index = MISSING_DETAIL_INDEX
    if detail_index == MISSING_DETAIL_INDEX:
        detail_index = fallback_index

    try:
        return _coerce_event_id_value(raw_event_id), detail_index
    except ValueError:
        return None, MISSING_DETAIL_INDEX


def _is_list_like(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def _chunk_detail_for_event(
    event: Mapping[str, Any],
    chunk_reference: _ChunkReference,
) -> tuple[str | None, int]:
    chunk_id = _clean_text(event.get("chunk_id"))
    if "detail_index" in event:
        detail_index_value = event.get("detail_index")
    elif "chunk_event_index" in event:
        detail_index_value = event.get("chunk_event_index")
    else:
        detail_index_value = event.get("detail_row_index")
    detail_index = _coerce_detail_index(detail_index_value)

    try:
        event_id = _coerce_event_id(event)
    except ValueError:
        event_id = None

    if chunk_id is not None:
        if event_id is not None and detail_index == MISSING_DETAIL_INDEX:
            manifest_detail = chunk_reference.detail_indexes_by_event_id.get(event_id)
            if manifest_detail is not None and manifest_detail[0] == chunk_id:
                detail_index = manifest_detail[1]
        return chunk_id, detail_index

    if event_id is None:
        return None, detail_index

    manifest_detail = chunk_reference.detail_indexes_by_event_id.get(event_id)
    if manifest_detail is not None:
        return manifest_detail

    for start, end, manifest_chunk_id in chunk_reference.ranges:
        if start <= event_id <= end:
            return manifest_chunk_id, detail_index
    return None, detail_index


def _coerce_detail_index(value: Any) -> int:
    if value is None or value == "":
        return MISSING_DETAIL_INDEX
    try:
        detail_index = int(str(value))
    except (TypeError, ValueError):
        return MISSING_DETAIL_INDEX
    if detail_index < 0 or detail_index > 2**31 - 1:
        return MISSING_DETAIL_INDEX
    return detail_index
