"""Conservative event taxonomy helpers for UFO source catalogs.

These helpers intentionally separate source/provenance labels from user-facing
event or object labels. Raw source text should still be retained elsewhere.
"""

from __future__ import annotations

import re
from typing import Any

from .utils import collapse_whitespace


UNKNOWN_TOKENS = {"", "unknown", "unk", "n/a", "na", "none", "null", "-"}

VISUAL_TYPE_GROUPS = {
    "sighting": "UFO/UAP sighting",
    "close_encounter": "Close encounter / occupant / abduction",
    "physical_evidence": "Crash / retrieval / physical evidence",
    "military": "Military / government / intelligence / aerospace",
    "nuclear": "Nuclear / atomic / weapons test",
    "science": "Astronomical / scientific / space activity",
    "historical": "Historical / publication / media / organization",
    "unknown": "Other / unknown",
}

SOURCE_FAMILY_LABEL_KEYS = {
    "apro",
    "blue book",
    "bluebook",
    "cufos",
    "fufor",
    "hatch",
    "magonia",
    "majestic",
    "mufon",
    "narcap",
    "national ufo reporting center",
    "nicap",
    "nids",
    "nuforc",
    "project blue book",
    "ufodna",
    "ufo dna",
    "ufoinfo",
    "uktna",
    "updb",
    "vallee",
}

ATTRIBUTE_ONLY_PATTERNS = (
    r"\baircraft nearby\b",
    r"\banimal reaction\b",
    r"\baura\b",
    r"\bchanged colou?r\b",
    r"\belectrical\b",
    r"\bemitted beams?\b",
    r"\bemitted other objects?\b",
    r"\bleft a trail\b",
    r"\bmissing time\b",
    r"\bpossible abduction\b",
)

SHAPE_PATTERNS: tuple[tuple[str, str, str], ...] = (
    (r"\b(boomerang|chevron|v shape|v shaped|v form|v shaped craft)\b", "chevron", "Chevron"),
    (r"\b(triangle|triangular|delta)\b", "triangle", "Triangle"),
    (r"\b(domed? disc|dome disc|disc|disk|saucer)\b", "disk", "Disk"),
    (r"\b(sphere|spherical|orb|ball|round)\b", "sphere", "Sphere / orb"),
    (r"\b(cylinder|cylindrical)\b", "cylinder", "Cylinder"),
    (r"\b(cigar|cigar shaped)\b", "cigar", "Cigar"),
    (r"\b(fireball|meteor like)\b", "fireball", "Fireball"),
    (r"\b(light|lights|nocturnal light|nl)\b", "light", "Light"),
    (r"\b(circle|circular)\b", "circle", "Circle"),
    (r"\b(oval|ovoid|egg)\b", "oval", "Oval / egg"),
    (r"\b(rectangle|rectangular|rectangl)\b", "rectangle", "Rectangle"),
    (r"\b(formation|formatn)\b", "formation", "Formation"),
    (r"\b(diamond)\b", "diamond", "Diamond"),
    (r"\b(cone|conical)\b", "cone", "Cone"),
    (r"\b(flash)\b", "flash", "Flash"),
    (r"\b(teardrop)\b", "teardrop", "Teardrop"),
    (r"\b(cross)\b", "cross", "Cross"),
    (r"\b(star)\b", "star", "Star-like"),
    (r"\b(crescent)\b", "crescent", "Crescent"),
    (r"\b(beam)\b", "beam", "Beam"),
    (r"\b(linear|line)\b", "linear", "Linear"),
    (r"\b(changing|polymorf|polymorph|irregular|irregulr)\b", "changing", "Changing / irregular"),
    (r"\b(other)\b", "other", "Other"),
)

EVENT_TYPE_PATTERNS: tuple[tuple[str, str, str, str], ...] = (
    (r"\b(mass abduction|abduction|alien encounter|occupant|entity|creature|close encounter|ce[2345]|contact)\b", "close_encounter", "Close encounter / abduction", "close_encounter"),
    (r"\b(landing interaction|landing)\b", "landing", "Landing", "close_encounter"),
    (r"\b(crash|retrieval|recovery|physical evidence|trace|mutilation|collision|material delivery)\b", "physical_evidence", "Crash / physical evidence", "physical_evidence"),
    (r"\b(nuclear|atomic|warhead|weapon|radiological)\b", "nuclear", "Nuclear / atomic event", "nuclear"),
    (r"\b(military|air force|government|intelligence|aerospace|classified|senate|congress|policy|law|official|secret|briefing|foia|declassified|defense)\b", "military", "Military / government event", "military"),
    (r"\b(astronom|scientific|space|satellite|comet|meteor|planet|research)\b", "science", "Astronomical / scientific event", "science"),
    (r"\b(historical|article|book|movie|tv|radio|publication|documentary|conference|organization|website|presentation|lecture|interview|magazine|newspaper|history|document|recording|poll|public)\b", "historical", "Historical / publication", "historical"),
    (r"\b(mass ufo sighting|ufo sighting|uap sighting|sighting|foo fighters?|radar sighting|radar|anomalous|mystery airship|mystery plane|mystery helicopter)\b", "sighting", "Sighting", "sighting"),
)


def clean_taxonomy_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).replace("\\n", " ").replace("\\,", ",")
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)
    text = collapse_whitespace(text)
    if text.lower() in UNKNOWN_TOKENS:
        return None
    return text or None


def taxonomy_key(value: Any) -> str:
    text = clean_taxonomy_text(value) or ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return collapse_whitespace(text)


def normalize_shape_label(value: Any) -> str | None:
    match = _match_shape(value)
    return match[0] if match else None


def display_shape_label(value: Any) -> str | None:
    match = _match_shape(value)
    return match[1] if match else None


def normalize_event_type_label(value: Any) -> str | None:
    match = _match_event_type(value)
    return match[0] if match else None


def display_event_type_label(value: Any) -> str | None:
    match = _match_event_type(value)
    return match[1] if match else None


def display_type_for_web_event(record: dict[str, Any]) -> str | None:
    """Return a compact browser-facing type label for filters and legends."""
    type_values = _candidate_values(record, "type", "type_normalized", "type_raw")
    shape_values = _candidate_values(record, "shape_normalized", "shape_raw", "shape")

    event_match = _first_event_type_match(type_values)
    shape_label = _first_shape_display(shape_values)
    shape_from_type = _first_shape_display(type_values)

    if event_match and event_match[2] not in {"sighting"}:
        return event_match[1]
    if shape_label:
        return shape_label
    if shape_from_type:
        return shape_from_type
    if event_match:
        return event_match[1]
    return None


def display_shape_for_web_event(record: dict[str, Any]) -> str | None:
    return _first_shape_display(_candidate_values(record, "shape_normalized", "shape_raw", "shape"))


def visual_type_group_for_web_event(record: dict[str, Any]) -> str:
    type_values = _candidate_values(record, "type", "type_normalized", "type_raw")
    event_match = _first_event_type_match(type_values)
    if event_match:
        return VISUAL_TYPE_GROUPS.get(event_match[2], VISUAL_TYPE_GROUPS["unknown"])
    if display_shape_for_web_event(record) or _first_shape_display(type_values):
        return VISUAL_TYPE_GROUPS["sighting"]
    return VISUAL_TYPE_GROUPS["unknown"]


def is_source_family_label(value: Any) -> bool:
    key = taxonomy_key(value)
    return key in SOURCE_FAMILY_LABEL_KEYS


def _candidate_values(record: dict[str, Any], *keys: str) -> list[Any]:
    return [record.get(key) for key in keys if record.get(key) not in (None, "")]


def _first_shape_display(values: list[Any]) -> str | None:
    for value in values:
        label = display_shape_label(value)
        if label:
            return label
    return None


def _first_event_type_match(values: list[Any]) -> tuple[str, str, str] | None:
    for value in values:
        match = _match_event_type(value)
        if match:
            return match
    return None


def _match_shape(value: Any) -> tuple[str, str] | None:
    key = taxonomy_key(value)
    if not key or is_source_family_label(key) or _is_code_only(key):
        return None
    for pattern, normalized, display in SHAPE_PATTERNS:
        if re.search(pattern, key):
            return normalized, display
    return None


def _match_event_type(value: Any) -> tuple[str, str, str] | None:
    key = taxonomy_key(value)
    if not key or is_source_family_label(key) or _is_code_only(key):
        return None
    if any(re.search(pattern, key) for pattern in ATTRIBUTE_ONLY_PATTERNS):
        return None
    for pattern, normalized, display, group_key in EVENT_TYPE_PATTERNS:
        if re.search(pattern, key):
            return normalized, display, group_key
    return None


def _is_code_only(key: str) -> bool:
    if re.fullmatch(r"\d+[a-z^]*", key):
        return True
    if re.fullmatch(r"[a-z]{1,4}\d*[a-z^]*", key) and key.upper() == key:
        return True
    return False
