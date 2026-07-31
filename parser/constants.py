"""Shared constants for parser and webapp generation."""

from __future__ import annotations

EVENT_HEADER_PATTERN = r"^Event\s+(?P<event_id>\d+)\s+\((?P<event_hash>[A-F0-9]+)\)\s*$"
YEAR_HEADER_PATTERN = r"^Year:\s*(?P<year_heading>[^,]+),"
GENERIC_FIELD_PATTERN = r"^([A-Za-z][A-Za-z0-9 /_-]{0,40}):\s*(.*)$"

KNOWN_EVENT_FIELDS = {
    "date": "Date",
    "alternate date": "Alternate date",
    "end date": "End date",
    "time": "Time",
    "location": "Location",
    "locations": "Locations",
    "description": "Description",
    "type": "Type",
    "reference": "Reference",
    "source": "Source",
    "extra data": "Extra Data",
    "see also": "See also",
    "note": "Note",
    "rocket type": "Rocket type",
    "rocket altitude": "Rocket altitude",
    "atomic type": "Atomic type",
    "atomic kt": "Atomic KT",
    "atomic mt": "Atomic MT",
    "attributes": "Attributes",
}

PROMOTED_EXTRA_EVENT_FIELDS = {
    "Alternate date",
    "See also",
    "Note",
    "Rocket type",
    "Rocket altitude",
    "Atomic type",
    "Atomic KT",
    "Atomic MT",
}

MULTILINE_FIELDS = {
    "Description",
    "Note",
    "Reference",
}

RAW_COORDINATE_SOURCES = {
    "raw_latlong",
    "location_coordinates",
}

COORDINATE_SOURCES = {
    "raw_latlong",
    "location_coordinates",
    "geocoded",
    "manual_fallback",
    "unresolved",
}

LOCATION_PRECISIONS = {
    "exact_coords",
    "address",
    "city",
    "county",
    "state_province",
    "country",
    "approximate",
    "multi_location",
    "unknown",
}

DATE_PRECISIONS = {
    "exact_day",
    "month",
    "year",
    "decade",
    "range",
    "approximate",
    "unknown",
}

LOW_PRECISION_VALUES = {"country", "state_province", "approximate", "unknown"}
