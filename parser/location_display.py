"""Provenance-safe location display normalization.

Canonical ``location_raw`` is a source claim and participates in identity and
deduplication.  This module only adds ``location_display`` after identity is
settled.  It removes structural presentation artifacts whose interpretation is
unambiguous while leaving contradictory or evidentially uncertain geography
for reviewed corrections.
"""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Mapping

LOCATION_DISPLAY_NORMALIZATION_POLICY = "location-label-structural-v1"

# Kept in the parser layer so runtime normalization does not depend on the
# report/preview command modules under ``scripts``.
US_STATE_NAME_TO_ABBREVIATION = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR",
    "CALIFORNIA": "CA", "COLORADO": "CO", "CONNECTICUT": "CT",
    "DELAWARE": "DE", "DISTRICT OF COLUMBIA": "DC", "FLORIDA": "FL",
    "GEORGIA": "GA", "HAWAII": "HI", "IDAHO": "ID", "ILLINOIS": "IL",
    "INDIANA": "IN", "IOWA": "IA", "KANSAS": "KS", "KENTUCKY": "KY",
    "LOUISIANA": "LA", "MAINE": "ME", "MARYLAND": "MD",
    "MASSACHUSETTS": "MA", "MICHIGAN": "MI", "MINNESOTA": "MN",
    "MISSISSIPPI": "MS", "MISSOURI": "MO", "MONTANA": "MT",
    "NEBRASKA": "NE", "NEVADA": "NV", "NEW HAMPSHIRE": "NH",
    "NEW JERSEY": "NJ", "NEW MEXICO": "NM", "NEW YORK": "NY",
    "NORTH CAROLINA": "NC", "NORTH DAKOTA": "ND", "OHIO": "OH",
    "OKLAHOMA": "OK", "OREGON": "OR", "PENNSYLVANIA": "PA",
    "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC", "SOUTH DAKOTA": "SD",
    "TENNESSEE": "TN", "TEXAS": "TX", "UTAH": "UT", "VERMONT": "VT",
    "VIRGINIA": "VA", "WASHINGTON": "WA", "WEST VIRGINIA": "WV",
    "WISCONSIN": "WI", "WYOMING": "WY",
}
US_STATE_CODES = frozenset(US_STATE_NAME_TO_ABBREVIATION.values())

MAJESTIC_ENVIRONMENT_CATEGORIES = {
    "coastlands",
    "desert",
    "farmlands",
    "forest",
    "high seas",
    "islands",
    "metropolis",
    "mountains",
    "offshore",
    "oil coal",
    "pasture",
    "rainforest",
    "residential",
    "town city",
    "tundra",
    "wetlands",
}

PLACEHOLDER_COMPONENTS = {
    "n a",
    "na",
    "none",
    "null",
    "tbd",
    "unknown",
    "unknown city",
    "unknown location",
    "unspecified",
}

US_COUNTRY_TOKENS = {"us", "usa", "united states", "united states of america"}
MARKDOWN_LINK_RE = re.compile(r"^\[([^\]]+)\]\(https?://[^)]+\)$", re.I | re.S)


def apply_location_display_normalization(
    event: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a copy with a clean display label when the changes are certain.

    Existing displays are used as the input when present, so already-reviewed
    wording is retained while harmless comma/duplication artifacts can still be
    removed.  A clean existing display is returned unchanged.
    """

    normalized_event = deepcopy(dict(event))
    existing_display = _clean_text(normalized_event.get("location_display"))
    location_raw = _clean_text(normalized_event.get("location_raw"))
    if not location_raw and not existing_display:
        return normalized_event

    source_label = existing_display or location_raw or ""
    input_label = source_label
    markdown_match = MARKDOWN_LINK_RE.match(input_label)
    if markdown_match:
        input_label = markdown_match.group(1).strip()
        transformations: list[str] = ["unwrap_markdown_location_link"]
    else:
        transformations = []

    # Narrative-in-location defects require evidence-backed extraction.  The
    # known production cases are handled by reviewed event corrections below
    # this generic layer; never tokenize arbitrary prose as comma geography.
    if len(input_label) > 180 and not transformations:
        return normalized_event

    original_parts = input_label.split(",")
    parts = [part.strip() for part in original_parts if part.strip()]
    if len(parts) != len(original_parts):
        transformations.append("remove_empty_components")

    source = _normalize_component(
        normalized_event.get("source_name") or normalized_event.get("source")
    )
    if (
        source == "majestic"
        and parts
        and _normalize_component(parts[0]) in MAJESTIC_ENVIRONMENT_CATEGORIES
    ):
        parts.pop(0)
        transformations.append("remove_majestic_environment_category")

    parts, removed_placeholders = _remove_placeholder_components(parts)
    if removed_placeholders:
        transformations.append("remove_placeholder_components")

    parts, removed_adjacent_duplicates = _remove_adjacent_duplicates(parts)
    if removed_adjacent_duplicates:
        transformations.append("remove_adjacent_duplicate_components")

    parts, removed_repeated_components = _remove_repeated_components(parts)
    if removed_repeated_components:
        transformations.append("remove_repeated_components")

    parts, state_transformation = _normalize_us_state_components(parts)
    if state_transformation:
        transformations.append(state_transformation)

    # Administrative removal can expose a new exact adjacency.
    parts, removed_post_state_duplicates = _remove_adjacent_duplicates(parts)
    if (
        removed_post_state_duplicates
        and "remove_adjacent_duplicate_components" not in transformations
    ):
        transformations.append("remove_adjacent_duplicate_components")

    parts, removed_redundant_state = _remove_redundant_us_state_components(parts)
    if removed_redundant_state:
        transformations.append("remove_redundant_us_state_components")

    location_display = ", ".join(parts).strip()
    if not location_display or location_display == source_label:
        return normalized_event

    normalized_event["location_display"] = location_display
    existing_normalizations = normalized_event.get("location_display_normalizations")
    normalizations = (
        [item for item in existing_normalizations if isinstance(item, dict)]
        if isinstance(existing_normalizations, list)
        else []
    )
    normalizations = [
        item
        for item in normalizations
        if item.get("policy_id") != LOCATION_DISPLAY_NORMALIZATION_POLICY
    ]
    normalizations.append(
        {
            "policy_id": LOCATION_DISPLAY_NORMALIZATION_POLICY,
            "transformations": transformations,
            "raw_location_preserved": bool(location_raw),
        }
    )
    normalized_event["location_display_normalizations"] = normalizations
    return normalized_event


def _remove_placeholder_components(parts: list[str]) -> tuple[list[str], bool]:
    if len(parts) <= 1:
        return parts, False
    kept = [
        part
        for part in parts
        if _normalize_component(part) not in PLACEHOLDER_COMPONENTS
    ]
    if not kept:
        return parts, False
    return kept, len(kept) != len(parts)


def _remove_adjacent_duplicates(parts: list[str]) -> tuple[list[str], bool]:
    kept: list[str] = []
    removed = False
    for part in parts:
        if kept and _normalize_component(kept[-1]) == _normalize_component(part):
            removed = True
            continue
        kept.append(part)
    return kept, removed


def _remove_repeated_components(parts: list[str]) -> tuple[list[str], bool]:
    kept: list[str] = []
    seen: set[str] = set()
    removed = False
    for part in parts:
        normalized = _normalize_component(part)
        if normalized in seen:
            removed = True
            continue
        seen.add(normalized)
        kept.append(part)
    return kept, removed


def _normalize_us_state_components(parts: list[str]) -> tuple[list[str], str | None]:
    if len(parts) < 4 or _normalize_component(parts[-1]) not in US_COUNTRY_TOKENS:
        return parts, None
    admin_indexes = [
        (index, state)
        for index in range(1, len(parts) - 1)
        if (state := _us_state_code(parts[index]))
    ]
    states = {state for _index, state in admin_indexes}
    if len(states) <= 1:
        return parts, None

    conflict_indexes = {index for index, _state in admin_indexes}
    return (
        [part for index, part in enumerate(parts) if index not in conflict_indexes],
        "omit_conflicting_us_state_components",
    )


def _remove_redundant_us_state_components(
    parts: list[str],
) -> tuple[list[str], bool]:
    if len(parts) < 4 or _normalize_component(parts[-1]) not in US_COUNTRY_TOKENS:
        return parts, False

    # The first component is the place; only later components may be treated as
    # administrative fields.  Distinct states are an evidence conflict and are
    # intentionally left untouched for review.
    admin_indexes: list[tuple[int, str]] = []
    for index in range(1, len(parts) - 1):
        state = _us_state_code(parts[index])
        if state:
            admin_indexes.append((index, state))
    states = {state for _index, state in admin_indexes}
    if len(states) != 1 or len(admin_indexes) < 2:
        return parts, False

    keep_index = admin_indexes[0][0]
    redundant_indexes = {index for index, _state in admin_indexes[1:]}
    return [
        part
        for index, part in enumerate(parts)
        if index == keep_index or index not in redundant_indexes
    ], True


def _us_state_code(value: Any) -> str | None:
    text = str(value or "").strip().upper().strip(".")
    if text in US_STATE_CODES:
        return text
    return US_STATE_NAME_TO_ABBREVIATION.get(text)


def _normalize_component(value: Any) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").lower()))


def _clean_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None
