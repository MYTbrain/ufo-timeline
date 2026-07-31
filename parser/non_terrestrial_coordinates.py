"""Deterministic policy for non-terrestrial coordinate placeholders."""

from __future__ import annotations

import math
import re
from typing import Any


# These are explicit jurisdiction labels observed in the Majestic source. They
# describe the reported target/context, not an Earth mapping jurisdiction.
NON_TERRESTRIAL_LOCATION_KEYS = frozenset(
    {
        "earth orbit or seen from space stations capsules",
        "mars",
        "neptune",
        "pluto",
        "the moon",
    }
)


def normalize_location_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text)).strip()


def is_non_terrestrial_location(value: Any) -> bool:
    return normalize_location_key(value) in NON_TERRESTRIAL_LOCATION_KEYS


def is_non_terrestrial_placeholder_coordinate(
    *,
    country: Any,
    lat: Any,
    lon: Any,
    zero_tolerance: float = 1e-9,
) -> bool:
    """Return True only for a zero coordinate under an explicit off-world label.

    A non-zero coordinate can legitimately identify an Earth observer or a
    spacecraft ground track, so the off-world label alone is not enough to
    quarantine it.
    """

    if not is_non_terrestrial_location(country):
        return False
    latitude = _finite_float(lat)
    longitude = _finite_float(lon)
    if latitude is None or longitude is None:
        return False
    return abs(latitude) <= zero_tolerance and abs(longitude) <= zero_tolerance


def _finite_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None
