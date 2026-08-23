"""Fail-closed, source-reviewed corrections applied after event identity is set.

These corrections intentionally run after deduplication.  That keeps stable
canonical event identities tied to the imported source row while allowing the
map projection to use better evidence than a known-bad normalized source field.
The original row remains unchanged in ``raw_fields`` and ``raw_source_row``.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping


NAPA_CORRECTION_ID = "majestic-hatch-udb-2481-napa-2026-08-23"
NAPA_CANONICAL_INPUT_ID = "cin_2117d48199668f694e7c1a29"
NAPA_CANONICAL_EVENT_ID = "evt_49c65297c6a08bd6ff910e2d"
NAPA_EVENT_ID = 3483027136344169
NAPA_SOURCE_ROW_HASH = "fc1a2224bc69a9810773e1034a2e0d8ae5a4de36"

NAPA_EXPECTED_RAW_FIELDS = {
    "date": "7/27/1952",
    "time": "10:50",
    "location/0": "NAPA VALLEY, CA",
    "key_vals/State/Prov": "Colorado",
    "key_vals/Country": "USA",
    "key_vals/LatLong": "38.300002 -122.300006",
    "key_vals/LatLongDMS": "38:18:00 N 122:18:00 W",
    "key_vals/Locale": "Farmlands",
    "key_vals/Duration": "1",
}

NAPA_REVIEWED_CORRECTION = {
    "correction_id": NAPA_CORRECTION_ID,
    "reviewed_at": "2026-08-23",
    "target": {
        "canonical_input_id": NAPA_CANONICAL_INPUT_ID,
        "canonical_event_id": NAPA_CANONICAL_EVENT_ID,
        "event_id": NAPA_EVENT_ID,
        "source_name": "majestic",
        "source_file": "majestic.csv",
        "source_native_id": "Hatch_UDB_2481",
        "source_row_number": 11264,
        "source_row_hash": NAPA_SOURCE_ROW_HASH,
    },
    "set_fields": {
        "time_raw": "10:45",
        "location_raw": "Napa Valley near Napa, Napa County, California, USA",
        "city": "Napa",
        "state_province": "California",
        "country": "USA",
        "location_precision": "city",
        "duration_raw": None,
        "summary": (
            "John Foraythe reported a metallic disc moving west at great speed over "
            "Napa Valley at an estimated 20,000 feet; it tilted edge-on and vanished "
            "in haze."
        ),
        "description": (
            "On Sunday, July 27, 1952 at 10:45 a.m., John Foraythe of 1512 A Street "
            "in Napa reported a metallic, disc-shaped object at an estimated altitude "
            "of 20,000 feet moving west at great speed over Napa Valley. It tilted "
            "until its thin edge faced him, then disappeared in haze. His report to "
            "the local sheriff's office was forwarded to Hamilton Field airbase."
        ),
        "source_url": (
            "https://sohp.us/collections/ufos-a-history/pdf/"
            "GROSS-1952-July-21-31-SN.pdf#page=51"
        ),
        "mapping_notes": (
            "Reviewed 2026-08-23. Retained the Hatch coordinate as an approximate "
            "Napa-area marker; the report does not establish an exact observer or "
            "airborne-object position. Corrected the normalized state from Colorado "
            "to California and removed Hatch's 'Farmlands' environment category from "
            "the place label. The contemporary newspaper account gives 10:45 a.m. "
            "and states no duration. Original Hatch values remain preserved in the "
            "raw source fields."
        ),
    },
    "evidence": [
        {
            "kind": "contemporary_newspaper",
            "title": "Napa Register",
            "publication_date": "1952-07-29",
            "url": "https://cdnc.ucr.edu/?a=d&d=NVR19520729",
        },
        {
            "kind": "source_transcription",
            "title": (
                "Loren E. Gross, UFOs: A History, Supplemental Notes—"
                "1952 July 21–31"
            ),
            "locator": "printed page 50; PDF page 51",
            "url": (
                "https://sohp.us/collections/ufos-a-history/pdf/"
                "GROSS-1952-July-21-31-SN.pdf#page=51"
            ),
        },
        {
            "kind": "official_geography",
            "title": "U.S. Census Geocoder reverse geography for the Hatch coordinate",
            "url": (
                "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
                "?x=-122.300006&y=38.300002&benchmark=Public_AR_Current"
                "&vintage=Current_Current&format=json"
            ),
        },
    ],
    "provenance_policy": (
        "Reviewed fields affect the normalized/map projection only; imported raw source "
        "fields and the stable source-row identity are not rewritten."
    ),
}


def apply_reviewed_event_corrections(event: Mapping[str, Any]) -> dict[str, Any]:
    """Return a corrected copy of one event, or an unchanged copy when untargeted.

    A target match with stale or incomplete source evidence raises ``ValueError``.
    This prevents a future source refresh from silently receiving an obsolete
    correction.
    """

    next_event = deepcopy(dict(event))
    if not _targets_napa_event(next_event):
        return next_event

    _validate_napa_source_guard(next_event)
    next_event.update(deepcopy(NAPA_REVIEWED_CORRECTION["set_fields"]))

    existing = next_event.get("reviewed_corrections")
    corrections = (
        [item for item in existing if isinstance(item, dict)]
        if isinstance(existing, list)
        else []
    )
    corrections = [
        item
        for item in corrections
        if item.get("correction_id") != NAPA_CORRECTION_ID
    ]
    corrections.append(deepcopy(NAPA_REVIEWED_CORRECTION))
    next_event["reviewed_corrections"] = corrections
    return next_event


def apply_reviewed_event_corrections_many(
    events: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [apply_reviewed_event_corrections(event) for event in events]


def _targets_napa_event(event: Mapping[str, Any]) -> bool:
    input_ids = event.get("canonical_input_ids")
    if isinstance(input_ids, list) and NAPA_CANONICAL_INPUT_ID in input_ids:
        return True
    if event.get("canonical_input_id") == NAPA_CANONICAL_INPUT_ID:
        return True
    if event.get("canonical_event_id") == NAPA_CANONICAL_EVENT_ID:
        return True
    if event.get("event_id") == NAPA_EVENT_ID:
        return True
    return _first(event, "source_native_id", "source_id") == "Hatch_UDB_2481"


def _validate_napa_source_guard(event: Mapping[str, Any]) -> None:
    errors: list[str] = []
    _expect(errors, "source_name", _first(event, "source_name", "source"), "majestic")
    _expect(errors, "source_file", event.get("source_file"), "majestic.csv")
    _expect(
        errors,
        "source_native_id",
        _first(event, "source_native_id", "source_id"),
        "Hatch_UDB_2481",
    )
    _expect(errors, "source_row_number", _source_row_number(event), 11264)
    _expect(errors, "source_row_hash", _source_row_hash(event), NAPA_SOURCE_ROW_HASH)

    raw_fields = event.get("raw_fields")
    if not isinstance(raw_fields, Mapping):
        errors.append("raw_fields: expected preserved source mapping")
    else:
        for key, expected in NAPA_EXPECTED_RAW_FIELDS.items():
            _expect(errors, f"raw_fields.{key}", raw_fields.get(key), expected)

    if errors:
        raise ValueError(
            f"Reviewed correction {NAPA_CORRECTION_ID} failed its stale-source guard: "
            + "; ".join(errors)
        )


def _source_row_number(event: Mapping[str, Any]) -> Any:
    if event.get("source_row_number") is not None:
        return event.get("source_row_number")
    for item in _source_provenance(event):
        if item.get("canonical_input_id") == NAPA_CANONICAL_INPUT_ID:
            return item.get("source_row_number")
    return None


def _source_row_hash(event: Mapping[str, Any]) -> Any:
    if event.get("source_row_hash"):
        return event.get("source_row_hash")
    for item in _source_provenance(event):
        if item.get("canonical_input_id") == NAPA_CANONICAL_INPUT_ID:
            return item.get("source_row_hash")
    return None


def _source_provenance(event: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    value = event.get("source_provenance")
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _first(event: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = event.get(key)
        if value not in (None, ""):
            return value
    return None


def _expect(errors: list[str], field: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        errors.append(f"{field}: expected {expected!r}, found {actual!r}")
