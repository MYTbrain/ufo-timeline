"""Compatibility export from canonical UFO records to normalized events."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import asdict, is_dataclass
import math
import re
from typing import Any

from .canonical_schema import build_location_text, clean_text, stable_hash
from .locations import infer_text_precision


CANONICAL_EVENT_ID_OFFSET = 1_000_000_000_000
EVENT_ID_HASH_HEX_LENGTH = 13
URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def canonical_events_to_normalized_events(records: Iterable[Any]) -> list[dict[str, Any]]:
    """Convert canonical/deduped records into the existing normalized shape."""
    normalized_events: list[dict[str, Any]] = []
    used_event_ids: set[int] = set()

    for record in records:
        data = _record_to_dict(record)
        identity = _identity_payload(data)
        event_id = _stable_numeric_event_id(identity, used_event_ids=used_event_ids)
        normalized_events.append(canonical_event_to_normalized_event(data, event_id=event_id))

    return normalized_events


def canonical_event_to_normalized_event(record: Any, *, event_id: int | None = None) -> dict[str, Any]:
    """Convert one canonical/deduped record into a parser-compatible event dict."""
    data = _record_to_dict(record)
    identity = _identity_payload(data)
    numeric_event_id = event_id if event_id is not None else _existing_or_stable_event_id(data, identity)
    event_hash = _first_clean(data, "event_hash") or stable_hash(identity, length=16).upper()

    location_raw = _location_text(data)
    all_locations_raw = _all_locations(data, location_raw)
    description = _first_clean(data, "description", "summary")
    type_label = _first_clean(data, "type_raw", "type", "type_normalized", "shape_raw", "shape_normalized")
    source_name = _first_clean(data, "source_name", "source")
    source_native_id = _first_clean(data, "source_native_id", "source_id")
    source_file = _first_clean(data, "source_file") or "canonical"
    source_raw = _source_raw(source_name, source_native_id)
    source_url = _first_clean(data, "source_url")
    provenance = _source_provenance(data)
    canonical_input_ids = _canonical_input_ids(data)
    parse_warnings = list(data.get("date_warnings") or [])

    lat, lon, coordinate_warning = _coordinates(data)
    if coordinate_warning:
        parse_warnings.append(coordinate_warning)

    primary_location_text = location_raw
    if lat is not None and lon is not None:
        coordinate_source = _normalized_coordinate_source(data.get("coordinate_source"))
        location_precision = _normalized_location_precision(data.get("location_precision"), mapped=True)
        geocode_display_name = primary_location_text
        geocode_query_used = None
        geocode_confidence = 1.0
        mapping_notes = "Used coordinates carried by the canonical source record."
    else:
        coordinate_source = "unresolved"
        location_precision = _normalized_location_precision(data.get("location_precision"), mapped=False)
        if location_precision == "unknown" and primary_location_text:
            location_precision = infer_text_precision(primary_location_text)
        geocode_display_name = None
        geocode_query_used = primary_location_text
        geocode_confidence = None
        mapping_notes = "Canonical source record did not include usable coordinates."

    extra_data = _extra_data(data, provenance, canonical_input_ids)
    normalized = {
        "event_id": numeric_event_id,
        "event_hash": event_hash,
        "canonical_event_id": _first_clean(data, "canonical_event_id"),
        "canonical_input_id": _first_clean(data, "canonical_input_id"),
        "canonical_input_ids": canonical_input_ids,
        "source_provenance": provenance,
        "duplicate_fingerprint": data.get("duplicate_fingerprint"),
        "duplicate_record_count": data.get("duplicate_record_count", 1),
        "dedupe_strategy": data.get("dedupe_strategy"),
        "source_file": source_file,
        "source_name": source_name,
        "source_native_id": source_native_id,
        "raw_event_block": _raw_event_block(
            event_id=numeric_event_id,
            event_hash=event_hash,
            data=data,
            location_raw=location_raw,
            type_label=type_label,
            source_raw=source_raw,
            description=description,
        ),
        "date_raw": _first_clean(data, "date_raw"),
        "end_date_raw": _first_clean(data, "end_date_raw"),
        "date_iso": _first_clean(data, "date_iso"),
        "end_date_iso": _first_clean(data, "end_date_iso"),
        "sort_date_iso": _first_clean(data, "sort_date_iso", "date_iso"),
        "date_precision": _normalized_date_precision(data.get("date_precision")),
        "time_raw": _first_clean(data, "time_raw"),
        "location_raw": location_raw,
        "location_field_name": "Location" if location_raw else None,
        "all_locations_raw": all_locations_raw,
        "description": description,
        "summary": _first_clean(data, "summary"),
        "type": type_label,
        "type_raw": _first_clean(data, "type_raw"),
        "type_normalized": _first_clean(data, "type_normalized"),
        "shape_raw": _first_clean(data, "shape_raw"),
        "shape_normalized": _first_clean(data, "shape_normalized"),
        "duration_raw": _first_clean(data, "duration_raw"),
        "references": [],
        "links": [source_url] if source_url and URL_RE.match(source_url) else [],
        "source_raw": source_raw,
        "source": source_name,
        "source_id": source_native_id,
        "extra_data": extra_data,
        "attributes_raw": None,
        "attributes_codes": [],
        "parse_warnings": parse_warnings,
        "original_entry_url": None,
        "lat": lat,
        "lon": lon,
        "primary_location_text": primary_location_text,
        "coordinate_source": coordinate_source,
        "location_precision": location_precision,
        "geocode_query_used": geocode_query_used,
        "geocode_display_name": geocode_display_name,
        "geocode_confidence": geocode_confidence,
        "mapping_notes": mapping_notes,
    }

    return normalized


def _record_to_dict(record: Any) -> dict[str, Any]:
    if isinstance(record, Mapping):
        return dict(record)
    if hasattr(record, "to_json_dict"):
        return dict(record.to_json_dict())
    if is_dataclass(record):
        return asdict(record)
    raise TypeError(f"Unsupported canonical record type: {type(record)!r}")


def _identity_payload(data: Mapping[str, Any]) -> dict[str, Any]:
    canonical_event_id = _first_clean(data, "canonical_event_id")
    if canonical_event_id:
        return {"canonical_event_id": canonical_event_id}

    canonical_input_ids = _canonical_input_ids(data)
    if canonical_input_ids:
        return {"canonical_input_ids": canonical_input_ids}

    canonical_input_id = _first_clean(data, "canonical_input_id")
    if canonical_input_id:
        return {"canonical_input_id": canonical_input_id}

    fallback = {
        key: data.get(key)
        for key in (
            "source_name",
            "source_file",
            "source_row_number",
            "source_native_id",
            "source_row_hash",
        )
        if data.get(key) not in (None, "")
    }
    return fallback or {"record": dict(data)}


def _existing_or_stable_event_id(data: Mapping[str, Any], identity: Mapping[str, Any]) -> int:
    existing_event_id = _coerce_int(data.get("event_id"))
    if existing_event_id is not None and existing_event_id >= 0:
        return existing_event_id
    return _stable_numeric_event_id(identity)


def _stable_numeric_event_id(
    identity: Mapping[str, Any],
    *,
    used_event_ids: set[int] | None = None,
) -> int:
    salt = 0
    while True:
        payload: Mapping[str, Any] | dict[str, Any]
        payload = identity if salt == 0 else {"identity": identity, "collision_salt": salt}
        event_id = CANONICAL_EVENT_ID_OFFSET + int(stable_hash(payload, length=EVENT_ID_HASH_HEX_LENGTH), 16)
        if used_event_ids is None or event_id not in used_event_ids:
            if used_event_ids is not None:
                used_event_ids.add(event_id)
            return event_id
        salt += 1


def _source_provenance(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    provided = data.get("source_provenance")
    if isinstance(provided, list):
        return [_provenance_item(item) for item in provided]

    source_name = _first_clean(data, "source_name", "source")
    source_file = _first_clean(data, "source_file")
    source_row_number = _coerce_int(data.get("source_row_number"))
    source_row_hash = _first_clean(data, "source_row_hash")
    canonical_input_id = _first_clean(data, "canonical_input_id")
    if not any((source_name, source_file, source_row_number, source_row_hash, canonical_input_id)):
        return []

    return [
        {
            "source_name": source_name,
            "source_file": source_file,
            "source_row_number": source_row_number,
            "source_native_id": _first_clean(data, "source_native_id", "source_id"),
            "source_row_hash": source_row_hash,
            "canonical_input_id": canonical_input_id,
        }
    ]


def _provenance_item(item: Any) -> dict[str, Any]:
    if isinstance(item, Mapping):
        return dict(item)
    if is_dataclass(item):
        return asdict(item)
    return {"value": item}


def _canonical_input_ids(data: Mapping[str, Any]) -> list[str]:
    raw_ids = data.get("canonical_input_ids")
    if isinstance(raw_ids, list):
        return [item for item in (_clean_string(value) for value in raw_ids) if item]

    single_id = _first_clean(data, "canonical_input_id")
    return [single_id] if single_id else []


def _location_text(data: Mapping[str, Any]) -> str | None:
    return _first_clean(data, "location_raw") or build_location_text(
        data.get("city"),
        data.get("state_province"),
        data.get("country"),
    )


def _all_locations(data: Mapping[str, Any], location_raw: str | None) -> list[str]:
    existing = data.get("all_locations_raw")
    if isinstance(existing, list):
        locations = [_clean_string(item) for item in existing]
        return [item for item in locations if item]

    if not location_raw:
        return []
    return [item.strip() for item in location_raw.split(";") if item.strip()]


def _coordinates(data: Mapping[str, Any]) -> tuple[float | None, float | None, str | None]:
    lat_present = data.get("lat") not in (None, "")
    lon_present = data.get("lon") not in (None, "")
    lat = _finite_float(data.get("lat"))
    lon = _finite_float(data.get("lon"))
    if lat is None and lon is None:
        return None, None, None
    if lat is None or lon is None:
        return None, None, "Canonical record had incomplete coordinates; omitted from mapped output."
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None, None, "Canonical record had out-of-range coordinates; omitted from mapped output."
    if not lat_present or not lon_present:
        return None, None, None
    return lat, lon, None


def _finite_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _normalized_coordinate_source(value: Any) -> str:
    text = _clean_string(value)
    if text in {"raw_latlong", "location_coordinates", "geocoded", "manual_fallback"}:
        return text
    return "raw_latlong"


def _normalized_location_precision(value: Any, *, mapped: bool) -> str:
    text = _clean_string(value)
    if mapped and text in {"coordinate", "coordinates", "exact", "exact_coords", "source_coordinates"}:
        return "exact_coords"
    if text in {
        "exact_coords",
        "address",
        "city",
        "county",
        "state_province",
        "country",
        "approximate",
        "multi_location",
        "unknown",
    }:
        return text
    return "exact_coords" if mapped else "unknown"


def _normalized_date_precision(value: Any) -> str:
    text = _clean_string(value)
    if text == "day":
        return "exact_day"
    if text in {"exact_day", "month", "year", "decade", "range", "approximate", "unknown"}:
        return text
    return "unknown"


def _source_raw(source_name: str | None, source_native_id: str | None) -> str | None:
    if source_name and source_native_id:
        return f"{source_name}, ID: {source_native_id}"
    return source_name


def _extra_data(
    data: Mapping[str, Any],
    provenance: list[dict[str, Any]],
    canonical_input_ids: list[str],
) -> dict[str, Any]:
    event_fields = {
        label: value
        for label, value in (
            ("Duration", _first_clean(data, "duration_raw")),
            ("Reported date", _first_clean(data, "reported_date_raw")),
            ("Posted date", _first_clean(data, "posted_date_raw")),
            ("Source URL", _first_clean(data, "source_url")),
        )
        if value
    }
    return {
        "event_fields": event_fields,
        "unparsed_lines": [],
        "canonical": {
            "canonical_event_id": _first_clean(data, "canonical_event_id"),
            "canonical_input_id": _first_clean(data, "canonical_input_id"),
            "canonical_input_ids": canonical_input_ids,
            "duplicate_fingerprint": data.get("duplicate_fingerprint"),
            "duplicate_record_count": data.get("duplicate_record_count", 1),
            "dedupe_strategy": data.get("dedupe_strategy"),
            "source_provenance": provenance,
            "raw_fields": data.get("raw_fields") or {},
            "shape_raw": _first_clean(data, "shape_raw"),
            "shape_normalized": _first_clean(data, "shape_normalized"),
            "type_raw": _first_clean(data, "type_raw"),
            "type_normalized": _first_clean(data, "type_normalized"),
        },
    }


def _raw_event_block(
    *,
    event_id: int,
    event_hash: str,
    data: Mapping[str, Any],
    location_raw: str | None,
    type_label: str | None,
    source_raw: str | None,
    description: str | None,
) -> str:
    lines = [f"Event {event_id} ({event_hash})"]
    for label, value in (
        ("Date", _first_clean(data, "date_raw")),
        ("End date", _first_clean(data, "end_date_raw")),
        ("Time", _first_clean(data, "time_raw")),
        ("Location", location_raw),
        ("Type", type_label),
        ("Source", source_raw),
    ):
        if value:
            lines.append(f"{label}: {value}")
    if description:
        lines.append("Description:")
        lines.append(description)
    return "\n".join(lines)


def _first_clean(data: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = _clean_string(data.get(key))
        if value:
            return value
    return None


def _clean_string(value: Any) -> str | None:
    return clean_text(value)


def _coerce_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None
