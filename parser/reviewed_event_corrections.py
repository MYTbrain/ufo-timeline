"""Fail-closed, source-reviewed corrections applied after event identity is set.

These corrections intentionally run after deduplication.  That keeps stable
canonical event identities tied to the imported source row while allowing the
map projection to use better evidence than a known-bad normalized source field.
Source-claim fields ending in ``_raw`` and the original row remain unchanged;
reviewed values use distinct display fields.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
from typing import Any, Iterable, Mapping

from .location_display import apply_location_display_normalization


NAPA_CORRECTION_ID = "majestic-hatch-udb-2481-napa-2026-08-23"
NAPA_CANONICAL_INPUT_ID = "cin_2117d48199668f694e7c1a29"
NAPA_CANONICAL_EVENT_ID = "evt_49c65297c6a08bd6ff910e2d"
NAPA_EVENT_ID = 3483027136344169
NAPA_SOURCE_ROW_HASH = "fc1a2224bc69a9810773e1034a2e0d8ae5a4de36"

# A singleton receives a deterministic event ID for each supported dedupe mode.
# Enumerating those IDs keeps all build modes usable while still failing closed
# on any new merge topology or identity algorithm.
NAPA_SINGLETON_EVENT_IDS = {
    "evt_4fbb948a14778d333a893f61": 4255985604229664,  # exact
    "evt_bb376e27bb52fbb0a13851cc": 3381470316185291,  # aggressive_v1
    "evt_01dce5938a5e27b9e3b135d5": 2813087785304214,  # maximal_v1
    "evt_0fe9f1746177762265fb0cf7": 1556825630784813,  # maximal_v2
    NAPA_CANONICAL_EVENT_ID: NAPA_EVENT_ID,  # maximal_v3 / production v152
}

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

NAPA_ORIGINAL_PROJECTION = {
    "time_raw": "10:50",
    "location_raw": "Farmlands, NAPA VALLEY, CA, Colorado, USA",
    "city": "NAPA VALLEY, CA",
    "state_province": "Colorado",
    "country": "USA",
    "duration_raw": "1",
}

NAPA_REVIEWED_FIELDS = {
    "time_display": "10:45",
    "location_display": "Napa Valley near Napa, Napa County, California, USA",
    "city": "Napa",
    "state_province": "California",
    "country": "USA",
    "location_precision": "city",
    "duration_display": "Not stated in the contemporary newspaper account",
    "summary_display": (
        "John Foraythe reported a metallic disc moving west at great speed over "
        "Napa Valley at an estimated 20,000 feet; it tilted edge-on and vanished "
        "in haze."
    ),
    "description_display": (
        "On Sunday, July 27, 1952 at 10:45 a.m., John Foraythe of 1512 A Street "
        "in Napa reported a metallic, disc-shaped object at an estimated altitude "
        "of 20,000 feet moving west at great speed over Napa Valley. It tilted "
        "until its thin edge faced him, then disappeared in haze. His report to "
        "the local sheriff's office was forwarded to Hamilton Field airbase."
    ),
    "source_url_display": (
        "https://sohp.us/collections/ufos-a-history/pdf/"
        "GROSS-1952-July-21-31-SN.pdf#page=51"
    ),
    "mapping_notes": (
        "Reviewed 2026-08-23. Retained the Hatch coordinate as an approximate "
        "Napa-area marker; the report does not establish an exact observer or "
        "airborne-object position. Corrected the normalized state from Colorado "
        "to California and removed Hatch's 'Farmlands' environment category from "
        "the display place. The contemporary newspaper account gives 10:45 a.m. "
        "and states no duration. Original Hatch values remain preserved in the "
        "raw source-claim fields and raw source row."
    ),
}

NAPA_REVIEWED_CORRECTION = {
    "correction_id": NAPA_CORRECTION_ID,
    "reviewed_at": "2026-08-23",
    "target": {
        "canonical_input_id": NAPA_CANONICAL_INPUT_ID,
        "canonical_event_id": NAPA_CANONICAL_EVENT_ID,
        "supported_singleton_canonical_event_ids": sorted(NAPA_SINGLETON_EVENT_IDS),
        "event_id": NAPA_EVENT_ID,
        "source_name": "majestic",
        "source_file": "majestic.csv",
        "source_native_id": "Hatch_UDB_2481",
        "source_row_number": 11264,
        "source_row_hash": NAPA_SOURCE_ROW_HASH,
    },
    "set_fields": NAPA_REVIEWED_FIELDS,
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
        "Reviewed display fields affect the normalized/map projection only; imported "
        "source-claim fields, raw source rows, and stable source identity are not rewritten."
    ),
}


NARRATIVE_LOCATION_CORRECTIONS = {
    "evt_11849f13c62eec6fb0aa6fc1": {
        "correction_id": "majestic-overmeire-1022-oslofjord-location-2026-08-24",
        "target": {
            "canonical_event_id": "evt_11849f13c62eec6fb0aa6fc1",
            "event_id": 1843028587236113,
            "canonical_input_id": "cin_4e1d1f8341be28025601f2a9",
            "source_native_id": "Overmeire_1022",
            "source_row_number": 3844,
            "source_row_hash": "56902aff2095bffeeb27eb9ee882b4d61f8aaeab",
            "location_sha256": (
                "b9b329f69f0025483c7a1a1818c459fe78b47691f62e58da272f328842ef5e40"
            ),
            "description_sha256": (
                "e123fc5f323e954d8fd296b0e87e8b9969baf5a81881fb0da65b7da91bc3b52e"
            ),
        },
        "set_fields": {
            "location_display": "Oslofjord, about 30 km from Oslo, Norway",
            "city": "Oslo",
            "state_province": None,
            "country": "Norway",
            "location_precision": "region",
            "mapping_notes": (
                "Reviewed 2026-08-24. The imported location/0 cell contains a "
                "narrative rather than a place. The source description identifies "
                "Oslofjord; a James McDonald interview index describes the site as "
                "about 30 km from Oslo. No point coordinate is asserted. The full "
                "source narrative remains preserved in location_raw and raw_fields."
            ),
            "source_url_display": (
                "https://github.com/bbauska/UFO-Dr-James-McDonald/blob/main/"
                "james-mcdonald-australia.md"
            ),
        },
        "evidence": [
            {
                "kind": "source_description",
                "title": "Overmeire_1022 imported description",
                "locator": "December 1943; Norway, Oslo (Oslofjorden)",
            },
            {
                "kind": "interview_index",
                "title": "James McDonald interview with Mrs I Palmer",
                "url": (
                    "https://github.com/bbauska/UFO-Dr-James-McDonald/blob/"
                    "main/james-mcdonald-australia.md"
                ),
            },
        ],
    },
    "evt_c20894010b97e5adf60162c6": {
        "correction_id": "majestic-magonia-811-dunbar-location-2026-08-24",
        "target": {
            "canonical_event_id": "evt_c20894010b97e5adf60162c6",
            "event_id": 3021254738232912,
            "canonical_input_id": "cin_73e900923672d187cf01462e",
            "source_native_id": "Magonia_811",
            "source_row_number": 27609,
            "source_row_hash": "50c0818284ee4f038eaec15d201f2c29169edb7f",
            "location_sha256": (
                "27d61cc9fe4429d566b2e51aa3e97e5526352bcb905c92dbc755e541d17e44ca"
            ),
            "description_sha256": (
                "bac229b51d21263fd5dee7cd9d94659c0f12e81bc405dc8e12ae2128984314e2"
            ),
        },
        "set_fields": {
            "location_display": (
                "Interstate 64 near Dunbar, West Virginia, USA"
            ),
            "city": "Dunbar",
            "state_province": "West Virginia",
            "country": "USA",
            "location_precision": "city",
            "mapping_notes": (
                "Reviewed 2026-08-24. Magonia row 811 shifted the sighting narrative "
                "into location/0. The Magonia text says Charleston, West Virginia; "
                "NICAP's chronology places the report on Interstate 64 near Dunbar. "
                "No exact point coordinate is asserted. The original narrative remains "
                "preserved in location_raw and raw_fields."
            ),
            "source_url_display": "https://www.nicap.org/chronos/1967fullrep.htm",
        },
        "evidence": [
            {
                "kind": "source_catalog",
                "title": "Magonia database, entry 811",
                "url": "https://www.nicap.org/magonia.htm",
            },
            {
                "kind": "case_chronology",
                "title": "NICAP 1967 chronology",
                "url": "https://www.nicap.org/chronos/1967fullrep.htm",
            },
        ],
    },
    "evt_ef86a4241215f54588bb629b": {
        "correction_id": "majestic-overmeire-2808-hebrides-location-2026-08-24",
        "target": {
            "canonical_event_id": "evt_ef86a4241215f54588bb629b",
            "event_id": 2487272255366338,
            "canonical_input_id": "cin_fce75f3625e03ebfce6f3b8e",
            "source_native_id": "Overmeire_2808",
            "source_row_number": 36623,
            "source_row_hash": "ffa8d1f3dd5f2ccf51fc0e069402fbf4d4b74a02",
            "location_sha256": (
                "bdb88eebb1824ea65341a7edce1993784814736dfc6e027a2ced3fb90b6e2839"
            ),
            "description_sha256": (
                "3f78e71174dacbb2e9726f35ea744fe131bfe904f7931c168015324f17323f4f"
            ),
        },
        "set_fields": {
            "location_display": (
                "At sea between St Kilda and Barra, Outer Hebrides, Scotland, UK"
            ),
            "city": None,
            "state_province": "Scotland",
            "country": "United Kingdom",
            "location_precision": "region",
            "mapping_notes": (
                "Reviewed 2026-08-24. Overmeire_2808 shifted a long narrative into "
                "location/0. The account places the trawler between St Kilda and "
                "Barra off northern Scotland. No exact vessel position is supplied, "
                "so the event remains unmapped at regional precision. The complete "
                "source narrative remains preserved in location_raw and raw_fields."
            ),
        },
        "evidence": [
            {
                "kind": "source_description",
                "title": "Overmeire_2808 imported account",
                "locator": "trawler Avel-Mad, between St Kilda and Barra",
            },
            {
                "kind": "bibliographic_source",
                "title": "Jean Francois Boedec, Les OVNI en Bretagne",
                "locator": "1978, pages 57-58",
            },
        ],
    },
}


def apply_reviewed_event_corrections(event: Mapping[str, Any]) -> dict[str, Any]:
    """Return a corrected copy of one event, or an unchanged copy when untargeted.

    A target match with stale or incomplete source evidence raises ``ValueError``.
    This prevents a future source refresh from silently receiving an obsolete
    correction.
    """

    if _is_napa_non_primary_merge_member(event):
        return deepcopy(dict(event))

    next_event = apply_location_display_normalization(event)
    if not _targets_napa_event(next_event):
        return _apply_narrative_location_correction(next_event)

    already_applied = _has_napa_correction(next_event)
    _validate_napa_source_guard(next_event, already_applied=already_applied)
    next_event.update(deepcopy(NAPA_REVIEWED_CORRECTION["set_fields"]))
    # The evidence-reviewed Napa projection supersedes the conservative generic
    # label formatter that would otherwise omit both contradictory raw states.
    next_event.pop("location_display_normalizations", None)

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
    correction_record = deepcopy(NAPA_REVIEWED_CORRECTION)
    correction_record["applied_target"] = {
        "canonical_input_id": next_event.get("canonical_input_id")
        or NAPA_CANONICAL_INPUT_ID,
        "canonical_event_id": next_event.get("canonical_event_id"),
        "event_id": next_event.get("event_id"),
    }
    corrections.append(correction_record)
    next_event["reviewed_corrections"] = corrections
    return next_event


def _apply_narrative_location_correction(
    event: Mapping[str, Any],
) -> dict[str, Any]:
    canonical_event_id = event.get("canonical_event_id")
    correction = NARRATIVE_LOCATION_CORRECTIONS.get(str(canonical_event_id or ""))
    if not correction:
        return deepcopy(dict(event))

    next_event = deepcopy(dict(event))
    target = correction["target"]
    errors: list[str] = []
    _expect(errors, "canonical_event_id", canonical_event_id, target["canonical_event_id"])
    _expect(errors, "event_id", event.get("event_id"), target["event_id"])
    if event.get("canonical_input_id") is not None:
        _expect(
            errors,
            "canonical_input_id",
            event.get("canonical_input_id"),
            target["canonical_input_id"],
        )
    _expect(
        errors,
        "canonical_input_ids",
        event.get("canonical_input_ids"),
        [target["canonical_input_id"]],
    )
    _expect(errors, "duplicate_record_count", event.get("duplicate_record_count"), 1)
    _expect(errors, "dedupe_strategy", event.get("dedupe_strategy"), "single_record")
    _expect(errors, "source_name", _first(event, "source_name", "source"), "majestic")
    _expect(errors, "source_file", event.get("source_file"), "majestic.csv")
    _expect(
        errors,
        "source_native_id",
        _first(event, "source_native_id", "source_id"),
        target["source_native_id"],
    )
    _expect(errors, "lat", event.get("lat"), None)
    _expect(errors, "lon", event.get("lon"), None)
    _expect(errors, "coordinate_source", event.get("coordinate_source"), "unresolved")

    provenance = _source_provenance(event)
    _expect(errors, "source_provenance.count", len(provenance), 1)
    if provenance:
        for key, expected in (
            ("source_name", "majestic"),
            ("source_file", "majestic.csv"),
            ("source_row_number", target["source_row_number"]),
            ("source_native_id", target["source_native_id"]),
            ("source_row_hash", target["source_row_hash"]),
            ("canonical_input_id", target["canonical_input_id"]),
        ):
            _expect(errors, f"source_provenance[0].{key}", provenance[0].get(key), expected)
    source_row_number = event.get("source_row_number")
    source_row_hash = event.get("source_row_hash")
    if provenance:
        source_row_number = source_row_number or provenance[0].get("source_row_number")
        source_row_hash = source_row_hash or provenance[0].get("source_row_hash")
    _expect(errors, "source_row_number", source_row_number, target["source_row_number"])
    _expect(errors, "source_row_hash", source_row_hash, target["source_row_hash"])

    raw_fields = event.get("raw_fields")
    if not isinstance(raw_fields, Mapping):
        errors.append("raw_fields: expected preserved source mapping")
    else:
        _expect(
            errors,
            "raw_fields.location/0.sha256",
            _sha256_text(raw_fields.get("location/0")),
            target["location_sha256"],
        )
        _expect(
            errors,
            "raw_fields.desc.sha256",
            _sha256_text(raw_fields.get("desc")),
            target["description_sha256"],
        )
    _expect(
        errors,
        "location_raw.sha256",
        _sha256_text(event.get("location_raw")),
        target["location_sha256"],
    )
    _expect(
        errors,
        "description.sha256",
        _sha256_text(event.get("description")),
        target["description_sha256"],
    )
    if errors:
        raise ValueError(
            f"Reviewed correction {correction['correction_id']} failed its stale-source guard: "
            + "; ".join(errors)
        )

    next_event.update(deepcopy(correction["set_fields"]))
    next_event.pop("location_display_normalizations", None)
    corrections = [
        item
        for item in next_event.get("reviewed_corrections") or []
        if isinstance(item, dict)
        and item.get("correction_id") != correction["correction_id"]
    ]
    corrections.append(
        {
            "correction_id": correction["correction_id"],
            "reviewed_at": "2026-08-24",
            "target": deepcopy(target),
            "set_fields": deepcopy(correction["set_fields"]),
            "evidence": deepcopy(correction["evidence"]),
            "provenance_policy": (
                "Reviewed display fields affect only the normalized/map projection; "
                "location_raw, raw source rows, and source identity remain unchanged."
            ),
        }
    )
    next_event["reviewed_corrections"] = corrections
    return next_event


def apply_reviewed_event_corrections_many(
    events: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [apply_reviewed_event_corrections(event) for event in events]


def _targets_napa_event(event: Mapping[str, Any]) -> bool:
    # Membership alone is intentionally insufficient: a later merge may retain
    # the Hatch input as a non-primary member under a different representative.
    if event.get("canonical_input_id") == NAPA_CANONICAL_INPUT_ID:
        return True
    if event.get("canonical_event_id") == NAPA_CANONICAL_EVENT_ID:
        return True
    if event.get("event_id") == NAPA_EVENT_ID:
        return True
    return (
        _first(event, "source_name", "source") == "majestic"
        and _first(event, "source_native_id", "source_id") == "Hatch_UDB_2481"
    )


def _is_napa_non_primary_merge_member(event: Mapping[str, Any]) -> bool:
    canonical_input_ids = event.get("canonical_input_ids")
    canonical_input_id = event.get("canonical_input_id")
    return bool(
        isinstance(canonical_input_ids, list)
        and NAPA_CANONICAL_INPUT_ID in canonical_input_ids
        # Exported singleton detail records intentionally omit the singular
        # canonical_input_id while retaining the complete one-item membership
        # list.  Only an explicit different representative identifies a true
        # non-primary merge member.
        and canonical_input_id is not None
        and canonical_input_id != NAPA_CANONICAL_INPUT_ID
    )


def _validate_napa_source_guard(
    event: Mapping[str, Any],
    *,
    already_applied: bool,
) -> None:
    errors: list[str] = []
    canonical_event_id = event.get("canonical_event_id")
    if canonical_event_id not in NAPA_SINGLETON_EVENT_IDS:
        errors.append(
            "canonical_event_id: expected a reviewed singleton ID, "
            f"found {canonical_event_id!r}"
        )
    if event.get("event_id") is not None:
        _expect(
            errors,
            "event_id",
            event.get("event_id"),
            NAPA_SINGLETON_EVENT_IDS.get(canonical_event_id),
        )
    if event.get("canonical_input_id") is not None:
        _expect(
            errors,
            "canonical_input_id",
            event.get("canonical_input_id"),
            NAPA_CANONICAL_INPUT_ID,
        )
    _expect(
        errors,
        "canonical_input_ids",
        event.get("canonical_input_ids"),
        [NAPA_CANONICAL_INPUT_ID],
    )
    _expect(errors, "duplicate_record_count", event.get("duplicate_record_count"), 1)
    _expect(errors, "dedupe_strategy", event.get("dedupe_strategy"), "single_record")
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
    _expect_float(errors, "lat", event.get("lat"), 38.300002)
    _expect_float(errors, "lon", event.get("lon"), -122.300006)
    if event.get("coordinate_source") not in {"source_coordinates", "raw_latlong"}:
        errors.append(
            "coordinate_source: expected 'source_coordinates' or 'raw_latlong', "
            f"found {event.get('coordinate_source')!r}"
        )

    provenance = _source_provenance(event)
    if not provenance:
        errors.append("source_provenance: expected one preserved source member")
    else:
        _expect(errors, "source_provenance.count", len(provenance), 1)
        target_provenance = provenance[0]
        _expect(
            errors,
            "source_provenance[0].source_name",
            target_provenance.get("source_name"),
            "majestic",
        )
        _expect(
            errors,
            "source_provenance[0].source_file",
            target_provenance.get("source_file"),
            "majestic.csv",
        )
        _expect(
            errors,
            "source_provenance[0].source_row_number",
            target_provenance.get("source_row_number"),
            11264,
        )
        _expect(
            errors,
            "source_provenance[0].canonical_input_id",
            target_provenance.get("canonical_input_id"),
            NAPA_CANONICAL_INPUT_ID,
        )
        _expect(
            errors,
            "source_provenance[0].source_native_id",
            target_provenance.get("source_native_id"),
            "Hatch_UDB_2481",
        )
        _expect(
            errors,
            "source_provenance[0].source_row_hash",
            target_provenance.get("source_row_hash"),
            NAPA_SOURCE_ROW_HASH,
        )

    raw_fields = event.get("raw_fields")
    if not isinstance(raw_fields, Mapping):
        errors.append("raw_fields: expected preserved source mapping")
    else:
        for key, expected in NAPA_EXPECTED_RAW_FIELDS.items():
            _expect(errors, f"raw_fields.{key}", raw_fields.get(key), expected)

    expected_projection = (
        NAPA_REVIEWED_FIELDS if already_applied else NAPA_ORIGINAL_PROJECTION
    )
    for key, expected in expected_projection.items():
        _expect(errors, key, event.get(key), expected)
    if not already_applied and event.get("location_precision") not in {
        "coordinate",
        "exact_coords",
    }:
        errors.append(
            "location_precision: expected 'coordinate' or 'exact_coords', "
            f"found {event.get('location_precision')!r}"
        )

    if errors:
        raise ValueError(
            f"Reviewed correction {NAPA_CORRECTION_ID} failed its stale-source guard: "
            + "; ".join(errors)
        )


def _has_napa_correction(event: Mapping[str, Any]) -> bool:
    corrections = event.get("reviewed_corrections")
    return bool(
        isinstance(corrections, list)
        and any(
            isinstance(item, Mapping)
            and item.get("correction_id") == NAPA_CORRECTION_ID
            for item in corrections
        )
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


def _sha256_text(value: Any) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _first(event: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = event.get(key)
        if value not in (None, ""):
            return value
    return None


def _expect(errors: list[str], field: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        errors.append(f"{field}: expected {expected!r}, found {actual!r}")


def _expect_float(
    errors: list[str],
    field: str,
    actual: Any,
    expected: float,
) -> None:
    try:
        number = float(actual)
    except (TypeError, ValueError):
        errors.append(f"{field}: expected {expected!r}, found {actual!r}")
        return
    if abs(number - expected) > 1e-9:
        errors.append(f"{field}: expected {expected!r}, found {actual!r}")
