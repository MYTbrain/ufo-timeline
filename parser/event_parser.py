"""Event block parsing for the UFO chronology text files."""

from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
import re
from typing import Any

from .constants import (
    EVENT_HEADER_PATTERN,
    GENERIC_FIELD_PATTERN,
    KNOWN_EVENT_FIELDS,
    MULTILINE_FIELDS,
    PROMOTED_EXTRA_EVENT_FIELDS,
    YEAR_HEADER_PATTERN,
)
from .utils import collapse_whitespace, normalize_label


EVENT_HEADER_RE = re.compile(EVENT_HEADER_PATTERN, re.MULTILINE)
YEAR_HEADER_RE = re.compile(YEAR_HEADER_PATTERN, re.MULTILINE)
FIELD_RE = re.compile(GENERIC_FIELD_PATTERN)
URL_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)


def _split_semicolon_locations(value: str) -> list[str]:
    return [item.strip() for item in value.split(";") if item.strip()]


def _join_lines(lines: list[str]) -> str:
    output = "\n".join(lines)
    return output.strip("\n")


def _parse_extra_data(raw_value: str) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    if not raw_value:
        return parsed

    matches = list(
        re.finditer(r"(^|,\s)(?P<key>[A-Za-z][A-Za-z0-9/_& .-]*?):\s*", raw_value)
    )
    if not matches:
        return {"raw": raw_value}

    for index, match in enumerate(matches):
        key = match.group("key").strip()
        value_start = match.end()
        value_end = matches[index + 1].start() if index + 1 < len(matches) else len(raw_value)
        value = raw_value[value_start:value_end].strip().rstrip(",")
        if len(value) >= 2 and value[0] == value[-1] == '"':
            value = value[1:-1]
        parsed[key] = value
    return parsed


def _parse_attributes(raw_value: str) -> list[str]:
    codes: list[str] = []
    for segment in raw_value.split(","):
        match = re.match(r"\s*([A-Z0-9]{2,6})\s*:", segment)
        if match:
            code = match.group(1)
            if code not in codes:
                codes.append(code)
    return codes


def _parse_source(source_raw: str | None) -> tuple[str | None, str | None]:
    if not source_raw:
        return None, None
    match = re.match(r"^(?P<source>.+?)(?:,\s*ID:\s*(?P<source_id>.+))?$", source_raw)
    if not match:
        return source_raw, None
    source = collapse_whitespace(match.group("source"))
    source_id = collapse_whitespace(match.group("source_id")) if match.group("source_id") else None
    return source or None, source_id or None


def parse_events_from_text(text: str, *, source_file: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    year_markers = [
        (match.start(), collapse_whitespace(match.group("year_heading")))
        for match in YEAR_HEADER_RE.finditer(text)
    ]
    year_positions = [item[0] for item in year_markers]
    event_headers = list(EVENT_HEADER_RE.finditer(text))

    for index, match in enumerate(event_headers):
        start = match.start()
        end = event_headers[index + 1].start() if index + 1 < len(event_headers) else len(text)
        block = text[start:end].strip()
        year_heading = None
        if year_markers:
            marker_index = bisect_right(year_positions, start) - 1
            if marker_index >= 0:
                year_heading = year_markers[marker_index][1]

        try:
            parsed = _parse_event_block(
                block,
                source_file=source_file,
                timeline_year_heading=year_heading,
            )
            events.append(parsed)
        except Exception as exc:  # pragma: no cover - exercised through pipeline guards
            failures.append(
                {
                    "source_file": source_file,
                    "event_id": match.group("event_id"),
                    "event_hash": match.group("event_hash"),
                    "error": str(exc),
                    "raw_event_block": block,
                }
            )
            events.append(
                {
                    "event_id": int(match.group("event_id")),
                    "event_hash": match.group("event_hash"),
                    "source_file": source_file,
                    "raw_event_block": block,
                    "date_raw": None,
                    "end_date_raw": None,
                    "date_iso": None,
                    "end_date_iso": None,
                    "sort_date_iso": None,
                    "date_precision": "unknown",
                    "time_raw": None,
                    "location_raw": None,
                    "location_field_name": None,
                    "all_locations_raw": [],
                    "description": None,
                    "type": None,
                    "references": [],
                    "links": [],
                    "source_raw": None,
                    "source": None,
                    "source_id": None,
                    "extra_data": {"event_fields": {}, "unparsed_lines": []},
                    "attributes_raw": None,
                    "attributes_codes": [],
                    "parse_warnings": [f"Event block parse failure: {exc}"],
                }
            )
    return events, failures


def _parse_event_block(
    block: str,
    *,
    source_file: str,
    timeline_year_heading: str | None,
) -> dict[str, Any]:
    lines = block.splitlines()
    header_match = EVENT_HEADER_RE.match(lines[0].strip())
    if not header_match:
        raise ValueError("Event block did not begin with a valid event header.")

    fields: dict[str, list[list[str]]] = defaultdict(list)
    current_label: str | None = None
    links: list[str] = []
    unparsed_lines: list[str] = []
    parse_warnings: list[str] = []

    for raw_line in lines[1:]:
        line = raw_line.rstrip()
        if URL_RE.match(line.strip()):
            links.append(line.strip())
            continue

        field_match = FIELD_RE.match(line)
        if field_match:
            normalized = normalize_label(field_match.group(1))
            if normalized in KNOWN_EVENT_FIELDS:
                current_label = KNOWN_EVENT_FIELDS[normalized]
                fields[current_label].append([field_match.group(2)])
                continue

            unparsed_lines.append(line)
            parse_warnings.append(
                f"Encountered unknown field label '{field_match.group(1)}'; preserved in unparsed_lines."
            )
            current_label = None
            continue

        if not line.strip():
            if current_label in MULTILINE_FIELDS and fields.get(current_label):
                fields[current_label][-1].append("")
            continue

        if current_label and fields.get(current_label):
            fields[current_label][-1].append(line)
            continue

        unparsed_lines.append(line)
        parse_warnings.append("Found non-empty unlabeled line outside any recognized field.")

    first_location_field = "Location" if fields.get("Location") else "Locations" if fields.get("Locations") else None
    location_raw = None
    all_locations_raw: list[str] = []
    if first_location_field:
        occurrences = [_join_lines(value) for value in fields[first_location_field]]
        location_raw = occurrences[0] if occurrences else None
        for occurrence in occurrences:
            if first_location_field == "Locations" or ";" in occurrence:
                all_locations_raw.extend(_split_semicolon_locations(occurrence))
            else:
                all_locations_raw.append(occurrence)

    references = [_join_lines(value) for value in fields.get("Reference", []) if _join_lines(value)]
    description = "\n".join(
        part for part in (_join_lines(value) for value in fields.get("Description", [])) if part
    ) or None
    source_raw = "\n".join(
        part for part in (_join_lines(value) for value in fields.get("Source", [])) if part
    ) or None
    source, source_id = _parse_source(source_raw)

    extra_data = {}
    if fields.get("Extra Data"):
        extra_data.update(_parse_extra_data(_join_lines(fields["Extra Data"][0])))

    event_fields: dict[str, Any] = {}
    for label in PROMOTED_EXTRA_EVENT_FIELDS:
        if fields.get(label):
            values = [_join_lines(value) for value in fields[label] if _join_lines(value)]
            event_fields[label] = values if len(values) > 1 else values[0]

    extra_data["event_fields"] = event_fields
    extra_data["unparsed_lines"] = unparsed_lines
    if timeline_year_heading:
        extra_data["timeline_year_heading"] = timeline_year_heading

    attributes_raw = None
    attributes_codes: list[str] = []
    if fields.get("Attributes"):
        attributes_raw = "\n".join(
            part for part in (_join_lines(value) for value in fields["Attributes"]) if part
        ) or None
        if attributes_raw:
            attributes_codes = _parse_attributes(attributes_raw)

    return {
        "event_id": int(header_match.group("event_id")),
        "event_hash": header_match.group("event_hash"),
        "source_file": source_file,
        "raw_event_block": block,
        "date_raw": _join_lines(fields["Date"][0]) if fields.get("Date") else None,
        "end_date_raw": _join_lines(fields["End date"][0]) if fields.get("End date") else None,
        "date_iso": None,
        "end_date_iso": None,
        "sort_date_iso": None,
        "date_precision": "unknown",
        "time_raw": _join_lines(fields["Time"][0]) if fields.get("Time") else None,
        "location_raw": location_raw,
        "location_field_name": first_location_field,
        "all_locations_raw": all_locations_raw,
        "description": description,
        "type": _join_lines(fields["Type"][0]) if fields.get("Type") else None,
        "references": references,
        "links": links,
        "source_raw": source_raw,
        "source": source,
        "source_id": source_id,
        "extra_data": extra_data,
        "attributes_raw": attributes_raw,
        "attributes_codes": attributes_codes,
        "parse_warnings": parse_warnings,
    }
