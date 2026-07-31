"""Location parsing, coordinate extraction, and fallback query heuristics."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from .utils import collapse_whitespace


DECIMAL_COORD_RE = re.compile(
    r"(?P<lat>[+-]?\d{1,2}(?:\.\d+)?)\s*[, ]\s*(?P<lon>[+-]?\d{1,3}(?:\.\d+)?)"
)

DIRECTIONAL_PREFIX_RE = re.compile(
    r"^(?P<prefix>NORTH|SOUTH|EAST|WEST|NORTHEAST|NORTHWEST|SOUTHEAST|SOUTHWEST|N|S|E|W|NE|NW|SE|SW)\s*/\s*(?P<rest>.+)$",
    re.IGNORECASE,
)

APPROXIMATE_PATTERNS = [
    re.compile(r"^(?:near|around|about|approx(?:\.|imately)?)\s+(?P<place>.+)$", re.IGNORECASE),
    re.compile(r"^(?:off\s+the\s+coast\s+of|off\s+coast\s+of|off)\s+(?P<place>.+)$", re.IGNORECASE),
    re.compile(
        r"^(?:north|south|east|west|northeast|northwest|southeast|southwest)\s+of\s+(?P<place>.+)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:\d+(?:\.\d+)?\s*(?:mi|miles|km|kilometers|nautical miles?)\s+(?:north|south|east|west|northeast|northwest|southeast|southwest)\s+of)\s+(?P<place>.+)$",
        re.IGNORECASE,
    ),
    re.compile(r"^between\s+(?P<place>.+?)\s+and\s+.+$", re.IGNORECASE),
]

DESCRIPTION_LOCATION_RE = re.compile(
    r"(?i:\b(?:in|near|at|over|off|above|south of|north of|east of|west of|northwest of|northeast of|southwest of|southeast of))\s+(?P<place>[A-Z][A-Za-z0-9'’().\-]+(?:\s+(?:of|the|[A-Z][A-Za-z0-9'’().\-]+))*(?:,\s*[A-Z][A-Za-z0-9'’().\- ]+)*)"
)

COUNTRY_ONLY_RE = re.compile(r"^[A-Z][A-Za-z .'-]+$")
BAD_DESCRIPTION_FALLBACK_QUERIES = {
    "New",
    "San",
    "St",
    "La",
    "Fort",
    "Mount",
    "Lake",
}

EXACT_LOCATION_ALIASES = {
    "us": "United States",
    "u.s.": "United States",
    "usa": "United States",
    "u.s.a.": "United States",
    "uk": "United Kingdom",
    "u.k.": "United Kingdom",
    "washington dc": "Washington, District of Columbia, United States",
    "washington, dc": "Washington, District of Columbia, United States",
    "washington, d.c": "Washington, District of Columbia, United States",
    "washington, d.c.": "Washington, District of Columbia, United States",
    "pentagon": "The Pentagon, Arlington, Virginia, United States",
    "the pentagon": "The Pentagon, Arlington, Virginia, United States",
    "white sands": "White Sands Missile Range, New Mexico, United States",
    "white sands, united states": "White Sands Missile Range, New Mexico, United States",
    "white sands, nm": "White Sands Missile Range, New Mexico, United States",
    "white sands pad 33, white sands proving grounds, nm": "White Sands Missile Range, New Mexico, United States",
    "holloman afb, new mexico": "Holloman Air Force Base, New Mexico, United States",
    "holloman afb, nm": "Holloman Air Force Base, New Mexico, United States",
    "goose bay afb, labrador, can": "Goose Bay, Labrador, Canada",
    "ussr": "Soviet Union",
    "u.s.s.r.": "Soviet Union",
    "france": "France",
}

US_STATE_ABBREVIATIONS = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
    "DC": "District of Columbia",
}

COUNTRY_ABBREVIATIONS = {
    "CAN": "Canada",
    "UK": "United Kingdom",
}


@dataclass(slots=True)
class LocationCandidate:
    raw_text: str
    query: str
    source_kind: str
    approximate: bool = False
    notes: list[str] | None = None


def extract_decimal_coordinates(text: str | None) -> tuple[float, float] | None:
    if not text:
        return None
    for match in DECIMAL_COORD_RE.finditer(text):
        lat = float(match.group("lat"))
        lon = float(match.group("lon"))
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon
    return None


def extract_dms_coordinates(text: str | None) -> tuple[float, float] | None:
    if not text:
        return None

    component_matches = re.findall(
        r"(\d[\d\s:°'\".,]*[NS])(?:[.,])?|(\d[\d\s:°'\".,]*[EW])(?:[.,])?",
        text,
        flags=re.IGNORECASE,
    )
    components = [part for pair in component_matches for part in pair if part]
    if len(components) < 2:
        return None

    lat_component = next((item for item in components if item[-1].upper() in {"N", "S"}), None)
    lon_component = next((item for item in components if item[-1].upper() in {"E", "W"}), None)
    if not lat_component or not lon_component:
        return None

    return _dms_to_decimal(lat_component), _dms_to_decimal(lon_component)


def _dms_to_decimal(component: str) -> float:
    hemisphere = component.strip()[-1].upper()
    numbers = [float(value) for value in re.findall(r"\d+(?:\.\d+)?", component)]
    degrees = numbers[0] if numbers else 0.0
    minutes = numbers[1] if len(numbers) > 1 else 0.0
    seconds = numbers[2] if len(numbers) > 2 else 0.0
    decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
    if hemisphere in {"S", "W"}:
        decimal *= -1
    return decimal


def clean_location_text(raw_text: str) -> tuple[str | None, bool, list[str]]:
    text = collapse_whitespace(raw_text)
    notes: list[str] = []
    approximate = False

    text = re.sub(r"\[[^\]]+\]", "", text).strip()
    text = re.sub(r"\(([^)]*[NSWE][^)]*)\)", "", text, flags=re.IGNORECASE).strip()

    directional = DIRECTIONAL_PREFIX_RE.match(text)
    if directional:
        text = directional.group("rest").strip()
        approximate = True
        notes.append("Removed directional prefix before geocoding.")

    for pattern in APPROXIMATE_PATTERNS:
        match = pattern.match(text)
        if match:
            text = match.group("place").strip()
            approximate = True
            notes.append("Converted vague location wording to best-effort place query.")
            break

    if "/" in text and not extract_decimal_coordinates(text):
        parts = [item.strip() for item in text.split("/") if item.strip()]
        if len(parts) > 1:
            text = parts[-1]
            approximate = True
            notes.append("Used the last slash-delimited location segment as the primary geocode query.")

    expanded_region = _expand_trailing_region_abbreviation(text)
    if expanded_region != text:
        text = expanded_region
        notes.append("Expanded a trailing region abbreviation before geocoding.")

    normalized_alias = _normalize_alias(text)
    if normalized_alias != text:
        text = normalized_alias
        notes.append("Normalized a common place alias before geocoding.")

    text = text.strip(" ,;.-")
    if not text:
        return None, approximate, notes
    return text, approximate, notes


def build_location_candidates(
    event: dict[str, Any],
    *,
    description_fallback_enabled: bool = True,
) -> list[LocationCandidate]:
    candidates: list[LocationCandidate] = []
    seen_queries: set[str] = set()

    explicit_locations = event.get("all_locations_raw") or []
    for raw_location in explicit_locations:
        query, approximate, notes = clean_location_text(raw_location)
        if not query:
            continue
        normalized = query.lower()
        if normalized in seen_queries:
            continue
        seen_queries.add(normalized)
        source_kind = "explicit_multi_location" if len(explicit_locations) > 1 else "explicit_location"
        candidates.append(
            LocationCandidate(
                raw_text=raw_location,
                query=query,
                source_kind=source_kind,
                approximate=approximate or len(explicit_locations) > 1,
                notes=notes,
            )
        )

    if not candidates and description_fallback_enabled:
        description_candidate = extract_description_location(event.get("description"))
        if description_candidate:
            candidates.append(description_candidate)

    return candidates


def extract_description_location(description: str | None) -> LocationCandidate | None:
    if not description:
        return None

    cleaned = re.sub(r"^\([^)]*\)\s*", "", description.strip())
    first_sentence = cleaned.split(".", 1)[0].strip()
    if first_sentence.count(",") >= 1 and len(first_sentence) <= 120:
        looks_place_like = re.match(r"^[A-Z][A-Za-z0-9'’().\- ]+(?:,\s*[A-Z][A-Za-z0-9'’().\- ]+)+$", first_sentence)
        if looks_place_like:
            return LocationCandidate(
                raw_text=first_sentence,
                query=first_sentence,
                source_kind="description_fallback",
                approximate=True,
                notes=["Used a leading place-like description fragment as a fallback geocode query."],
            )

    match = DESCRIPTION_LOCATION_RE.search(cleaned)
    if match:
        place = match.group("place").strip(" ,;.")
        if place in BAD_DESCRIPTION_FALLBACK_QUERIES:
            return None
        if " " not in place and len(place) < 4:
            return None
        place = _normalize_alias(place)
        return LocationCandidate(
            raw_text=place,
            query=place,
            source_kind="description_fallback",
            approximate=True,
            notes=["Extracted a conservative place mention from the description."],
        )
    return None


def _normalize_alias(query: str) -> str:
    lowered = query.strip().lower()
    if lowered in EXACT_LOCATION_ALIASES:
        return EXACT_LOCATION_ALIASES[lowered]

    for prefix, country in (("usa, ", "United States"), ("us, ", "United States"), ("uk, ", "United Kingdom")):
        if lowered.startswith(prefix):
            rest = query[len(prefix):].strip(" ,")
            if rest:
                return f"{rest}, {country}"
    return query


def _expand_trailing_region_abbreviation(query: str) -> str:
    parts = [item.strip() for item in query.split(",")]
    if len(parts) < 2:
        return query

    last_part = parts[-1].upper().strip(". ")
    if last_part in US_STATE_ABBREVIATIONS:
        parts[-1] = US_STATE_ABBREVIATIONS[last_part]
        if len(parts) == 2:
            parts.append("United States")
        elif parts[-1] != "United States" and parts[-2] != "United States":
            parts.append("United States")
        return ", ".join(item for item in parts if item)

    if last_part in COUNTRY_ABBREVIATIONS:
        parts[-1] = COUNTRY_ABBREVIATIONS[last_part]
        return ", ".join(item for item in parts if item)

    return query


def infer_text_precision(query: str | None, *, approximate: bool = False, multi_location: bool = False) -> str:
    if multi_location:
        return "multi_location"
    if approximate:
        return "approximate"
    if not query:
        return "unknown"
    if "," in query:
        return "city"
    if COUNTRY_ONLY_RE.match(query):
        return "country"
    return "unknown"


def classify_geocode_precision(
    result: dict[str, Any] | None,
    *,
    approximate: bool = False,
    multi_location: bool = False,
) -> str:
    if multi_location:
        return "multi_location"
    if approximate:
        return "approximate"
    if not result:
        return "unknown"

    raw = result.get("raw", {})
    addresstype = str(raw.get("addresstype") or raw.get("type") or "").lower()
    address = raw.get("address", {}) or {}

    if addresstype in {"house", "building", "amenity", "address"}:
        return "address"
    if addresstype in {"city", "town", "village", "hamlet", "municipality", "suburb"}:
        return "city"
    if addresstype in {"county", "district"} or address.get("county"):
        return "county"
    if addresstype in {"state", "province", "region"} or address.get("state"):
        return "state_province"
    if addresstype == "country" or address.get("country"):
        return "country"
    return "city" if "," in str(result.get("display_name", "")) else "unknown"
