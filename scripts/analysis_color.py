"""Conservative value-only color normalization for Analysis Wave 7."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Iterable


STATUS_CODES = (
    "missing",
    "source_sentinel",
    "exact_single",
    "explicit_compound",
    "multicolor_unspecified",
    "changing_known",
    "changing_unspecified",
    "non_color_descriptor",
    "unparsed",
)
ROLE_CODES = (
    "role_unspecified",
    "emitted_light_explicit",
    "object_surface_explicit",
    "both_role_cues_ambiguous",
)
CATEGORY_CODES = (
    "white",
    "black",
    "gray",
    "red",
    "orange",
    "yellow",
    "amber",
    "green",
    "blue",
    "purple",
    "pink",
    "brown",
    "gold",
    "silver",
    "copper_bronze",
)
NORMALIZED_STATUSES = {
    "exact_single",
    "explicit_compound",
    "multicolor_unspecified",
    "changing_known",
    "changing_unspecified",
}
SOURCE_SENTINELS = {"unknown", "unk", "n/a", "na", "none", "null"}

WORD_CATEGORY_ALIASES = {
    "white": "white",
    "whitish": "white",
    "ivory": "white",
    "cream": "white",
    "black": "black",
    "blackish": "black",
    "charcoal": "black",
    "gray": "gray",
    "grey": "gray",
    "grayish": "gray",
    "greyish": "gray",
    "red": "red",
    "reddish": "red",
    "crimson": "red",
    "scarlet": "red",
    "maroon": "red",
    "burgundy": "red",
    "orange": "orange",
    "orangish": "orange",
    "yellow": "yellow",
    "yellowish": "yellow",
    "amber": "amber",
    "green": "green",
    "greenish": "green",
    "blue": "blue",
    "bluish": "blue",
    "aqua": "blue",
    "cyan": "blue",
    "teal": "blue",
    "purple": "purple",
    "violet": "purple",
    "magenta": "purple",
    "indigo": "purple",
    "lavender": "purple",
    "pink": "pink",
    "brown": "brown",
    "brownish": "brown",
    "tan": "brown",
    "beige": "brown",
    "gold": "gold",
    "golden": "gold",
    "silver": "silver",
    "copper": "copper_bronze",
    "bronze": "copper_bronze",
}
PACKED_COLOR_ALIASES = {
    "blu": "blue",
    "blue": "blue",
    "brown": "brown",
    "brwn": "brown",
    "gold": "gold",
    "gray": "gray",
    "gree": "green",
    "green": "green",
    "grey": "gray",
    "oran": "orange",
    "orang": "orange",
    "orange": "orange",
    "pink": "pink",
    "purpl": "purple",
    "red": "red",
    "silvr": "silver",
    "silver": "silver",
    "viole": "purple",
    "white": "white",
    "yel": "yellow",
    "yell": "yellow",
    "yello": "yellow",
    "yellow": "yellow",
}
PACKED_MODIFIERS = {"bright", "dark", "neon", "pale"}
ROLE_LIGHT_WORDS = {"light", "lights", "glow", "glowing", "illumination", "illuminated"}
ROLE_OBJECT_WORDS = {"object", "craft", "body", "hull", "surface", "exterior", "fuselage"}
CHANGING_WORDS = {"change", "changed", "changing", "flashing", "flashes", "pulsing", "cycling", "alternating"}
DESCRIPTOR_WORDS = {
    "luminous", "metallic", "shiny", "bright", "fiery", "transparent", "translucent", "reflective", "clear", "dark",
}
MULTICOLOR_RE = re.compile(
    r"\b(?:multi(?:[ -]?colou?red)?|multiple|various|rainbow|different[ -]+colou?rs?)\b",
    re.I,
)
WORD_RE = re.compile(r"[a-z]+", re.I)
ALNUM_RE = re.compile(r"[^a-z]+", re.I)


@dataclass(frozen=True)
class ColorNormalization:
    source: str
    raw_value: str
    raw_value_sha256: str
    status: str
    role: str
    categories: tuple[str, ...]
    changing: bool
    multicolor: bool
    compound: bool
    reason: str

    @property
    def normalized(self) -> bool:
        return self.status in NORMALIZED_STATUSES


def _ordered_categories(values: Iterable[str]) -> tuple[str, ...]:
    present = set(values)
    return tuple(category for category in CATEGORY_CODES if category in present)


def _role_for(words: set[str]) -> str:
    light = bool(words & ROLE_LIGHT_WORDS)
    object_ = bool(words & ROLE_OBJECT_WORDS)
    if light and object_:
        return "both_role_cues_ambiguous"
    if light:
        return "emitted_light_explicit"
    if object_:
        return "object_surface_explicit"
    return "role_unspecified"


def _segment_packed_ufocat(value: str) -> tuple[str, ...]:
    packed = ALNUM_RE.sub("", value.lower())
    if not packed:
        return ()
    tokens = sorted(
        [(token, category) for token, category in PACKED_COLOR_ALIASES.items()] +
        [(token, None) for token in PACKED_MODIFIERS],
        key=lambda item: (-len(item[0]), item[0]),
    )
    memo: dict[int, tuple[str, ...] | None] = {}

    def walk(offset: int) -> tuple[str, ...] | None:
        if offset == len(packed):
            return ()
        if offset in memo:
            return memo[offset]
        for token, category in tokens:
            if not packed.startswith(token, offset):
                continue
            tail = walk(offset + len(token))
            if tail is not None:
                memo[offset] = ((category,) if category else ()) + tail
                return memo[offset]
        memo[offset] = None
        return None

    parsed = walk(0)
    return _ordered_categories(parsed or ())


def normalize_color(source: str, raw_value: str | None) -> ColorNormalization:
    canonical_source = str(source or "unknown").strip().lower() or "unknown"
    raw = "" if raw_value is None else str(raw_value)
    raw_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    text = raw.strip()
    if not text:
        return ColorNormalization(canonical_source, raw, raw_hash, "missing", "role_unspecified", (), False, False, False, "empty")
    if text.lower() in SOURCE_SENTINELS:
        return ColorNormalization(
            canonical_source, raw, raw_hash, "source_sentinel", "role_unspecified", (), False, False, False,
            "explicit_source_sentinel",
        )

    words_in_order = [word.lower() for word in WORD_RE.findall(text)]
    words = set(words_in_order)
    categories = _ordered_categories(WORD_CATEGORY_ALIASES[word] for word in words_in_order if word in WORD_CATEGORY_ALIASES)
    packed = False
    if not categories and canonical_source == "ufocat" and len(words_in_order) == 1:
        categories = _segment_packed_ufocat(text)
        packed = bool(categories)
    role = _role_for(words)
    changing = bool(words & CHANGING_WORDS)
    multicolor_marker = bool(MULTICOLOR_RE.search(text))
    descriptor = bool(words & DESCRIPTOR_WORDS)

    if changing:
        status = "changing_known" if categories else "changing_unspecified"
        reason = "changing_marker_with_categories" if categories else "changing_marker_without_categories"
    elif multicolor_marker and len(categories) < 2:
        status = "multicolor_unspecified"
        reason = "multicolor_marker_without_two_explicit_categories"
    elif len(categories) >= 2:
        status = "explicit_compound"
        reason = "complete_packed_controlled_categories" if packed else "multiple_whole_token_categories"
    elif len(categories) == 1:
        status = "exact_single"
        reason = "complete_packed_controlled_category" if packed else "whole_token_category"
    elif descriptor:
        status = "non_color_descriptor"
        reason = "appearance_or_luminosity_descriptor_without_color_category"
    else:
        status = "unparsed"
        reason = "no_registered_whole_token_or_complete_packed_category"

    compound = len(categories) >= 2
    multicolor = compound or multicolor_marker
    return ColorNormalization(
        canonical_source,
        raw,
        raw_hash,
        status,
        role,
        categories,
        changing,
        multicolor,
        compound,
        reason,
    )
