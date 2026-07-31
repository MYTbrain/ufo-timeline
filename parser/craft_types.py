"""Source-preserving craft type inference helpers.

These helpers derive an analysis classification from existing type, shape,
description, and raw-source fields. They do not replace source-displayed labels.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


UNKNOWN_VALUES = {
    "",
    "-",
    "--",
    "n/a",
    "na",
    "none",
    "not specified",
    "not reported",
    "not stated",
    "other",
    "other / unknown",
    "unknown",
    "unknown type",
    "unspecified",
}

GENERIC_WEAK_TYPES = {
    "light",
    "lights",
    "object",
    "objects",
    "ufo",
    "uap",
}


@dataclass(frozen=True)
class CraftPattern:
    craft_type: str
    display_label: str
    confidence: str
    same_day_match_strength: str
    pattern: re.Pattern[str]


PATTERN_GROUPS: list[CraftPattern] = [
    CraftPattern("triangle", "Triangle / delta", "high", "strong", re.compile(r"\b(triangular|triangles?|triangul\w*|tri[aá]ngulos?|dreiecks?|delta[- ]?shaped|black triangle)\b", re.I)),
    CraftPattern("chevron_boomerang", "Chevron / boomerang / V", "high", "strong", re.compile(r"\b(chevrons?|boomerangs?|vshape(?:d)?)\b", re.I)),
    CraftPattern("chevron_boomerang", "Chevron / boomerang / V", "high", "strong", re.compile(r"\b(chevron|boomerang|v[- ]?shaped|vee[- ]?shaped|arrow(?:head|s)?|fl[èe]ches?|crescent)\b", re.I)),
    CraftPattern("disc_saucer", "Disc / saucer", "high", "strong", re.compile(r"\b(dis[ck]s?|saucers?|flying saucers?|discoid(?:al)?|discos?|disques?|scheibe|lenticular|domes?|domed|saturn|ring|wheel|top[- ]?shaped|bowl[- ]?shaped)\b", re.I)),
    CraftPattern("cigar_cylinder", "Cigar / cylinder", "high", "strong", re.compile(r"\b(cigars?|cylind\w*|cilindros?|zylinders?|tube[- ]?shaped|rocket[- ]?shaped|oblong|elongat(?:e|ed)|bullet|airship|capsul(?:e|ar)?|tic[- ]?tac|tictac|tylenol[- ]?shaped)\b", re.I)),
    CraftPattern("sphere_orb", "Sphere / orb / ball", "high", "medium", re.compile(r"\b(spheres?|sph[eèé]res?|spherical|spheroid(?:al)?|esferas?|orbs?|orbes?|ball(?: of light)?|boules?|kugeln?|globes?|globular|round(?:ish| object)?|rounded object|circles?|circular)\b", re.I)),
    CraftPattern("rectangle_box", "Rectangle / box / cube", "high", "strong", re.compile(r"\b(rectang\w*|box(?:es|[- ]?shaped)?|cubes?|cubos?|cubical|square)\b", re.I)),
    CraftPattern("oval_egg", "Oval / egg", "high", "medium", re.compile(r"\b(oval\w*|egg[- ]?shape(?:d)?|eggshaped|elliptic(?:al)?|ellipse|ellipsoid|football(?:[- ]?shape(?:d)?)?|almond(?:[- ]?shaped)?)\b", re.I)),
    CraftPattern("teardrop", "Teardrop", "high", "strong", re.compile(r"\b(tear[- ]?drops?|teardrops?)\b", re.I)),
    CraftPattern("cone", "Cone", "high", "strong", re.compile(r"\b(cones?|conos?|c[oô]nes?|conical|pyramids?)\b", re.I)),
    CraftPattern("diamond", "Diamond", "high", "strong", re.compile(r"\b(diamond[- ]?shaped|diamonds?|diamantes?|losanges?)\b", re.I)),
    CraftPattern("formation", "Formation / multiple objects", "medium", "medium", re.compile(r"\b(formations?|fleet|cluster|linear|row of lights|line of lights|string of lights|multiple lights|several lights)\b", re.I)),
    CraftPattern("fireball_meteor_like", "Fireball / meteor-like", "medium", "weak", re.compile(r"\b(fireball|meteor[- ]?like|falling star|shooting star)\b", re.I)),
    CraftPattern("light", "Light / luminous object", "low", "weak", re.compile(r"\b(light|lights|luminous|lumi[eèé]res?|luces|lichter?|bright object|glowing object|flash(?:es|ing)?|star[- ]?like|dot|dots|pin[- ]?point|points? of light|spots? of light|bright spot|glowing spot|moving spot|unmoving spot)\b", re.I)),
]

LEGACY_SHAPE_VALUE_MAP: dict[str, tuple[str, str, str, str]] = {
    "arrow": ("chevron_boomerang", "Chevron / boomerang / V", "high", "strong"),
    "banana": ("cigar_cylinder", "Cigar / cylinder", "medium", "medium"),
    "barrel": ("cigar_cylinder", "Cigar / cylinder", "high", "strong"),
    "bar": ("cigar_cylinder", "Cigar / cylinder", "medium", "medium"),
    "barbell": ("dumbbell_barbell", "Dumbbell / barbell", "high", "strong"),
    "bell": ("cone", "Cone", "medium", "medium"),
    "blimp": ("cigar_cylinder", "Cigar / cylinder", "medium", "medium"),
    "comet": ("fireball_meteor_like", "Fireball / meteor-like", "medium", "weak"),
    "dirigibl": ("cigar_cylinder", "Cigar / cylinder", "medium", "medium"),
    "dumbbell": ("dumbbell_barbell", "Dumbbell / barbell", "high", "strong"),
    "fuselage": ("cigar_cylinder", "Cigar / cylinder", "medium", "medium"),
    "globe": ("sphere_orb", "Sphere / orb / ball", "high", "medium"),
    "glow": ("light", "Light / luminous object", "low", "weak"),
    "hemisphr": ("disc_saucer", "Disc / saucer", "medium", "medium"),
    "lens": ("disc_saucer", "Disc / saucer", "high", "strong"),
    "lozenge": ("cigar_cylinder", "Cigar / cylinder", "medium", "medium"),
    "mantaray": ("chevron_boomerang", "Chevron / boomerang / V", "medium", "medium"),
    "manta ray": ("chevron_boomerang", "Chevron / boomerang / V", "medium", "medium"),
    "missile": ("cigar_cylinder", "Cigar / cylinder", "medium", "medium"),
    "pear": ("oval_egg", "Oval / egg", "medium", "medium"),
    "pyramid": ("cone", "Cone", "high", "strong"),
    "rod": ("cigar_cylinder", "Cigar / cylinder", "high", "strong"),
    "rocket": ("cigar_cylinder", "Cigar / cylinder", "medium", "medium"),
    "sausage": ("cigar_cylinder", "Cigar / cylinder", "medium", "medium"),
    "spindle": ("cigar_cylinder", "Cigar / cylinder", "medium", "medium"),
    "streak": ("light", "Light / luminous object", "low", "weak"),
    "top": ("disc_saucer", "Disc / saucer", "high", "strong"),
    "torpedo": ("cigar_cylinder", "Cigar / cylinder", "high", "strong"),
    "u-shape": ("chevron_boomerang", "Chevron / boomerang / V", "medium", "medium"),
    "wedge": ("chevron_boomerang", "Chevron / boomerang / V", "high", "strong"),
    "wing": ("chevron_boomerang", "Chevron / boomerang / V", "medium", "medium"),
    "zeppelin": ("cigar_cylinder", "Cigar / cylinder", "medium", "medium"),
}

EXPLAINED_PATTERNS: list[CraftPattern] = [
    CraftPattern(
        "conventional_or_explained",
        "Conventional / explained",
        "medium",
        "none",
        re.compile(
            r"\b(result|identified|explained)\s*:\s*"
            r"(aircraft|airplane|aeroplane|balloon|meteor|satellite|star|venus|mars|moon|bird|kite|drone|reflection|lens flare|camera artifact|photo artifact)\b",
            re.I,
        ),
    ),
    CraftPattern(
        "conventional_or_explained",
        "Conventional / explained",
        "medium",
        "none",
        re.compile(
            r"\b(aircraft|airplane|aeroplane|balloon|bird|kite|drone)\s*[-/]\s*(possible|probable)\b",
            re.I,
        ),
    ),
    CraftPattern(
        "conventional_or_explained",
        "Conventional / explained",
        "medium",
        "none",
        re.compile(r"\b(conventional|prosaic)\s+explanation\b", re.I),
    ),
    CraftPattern(
        "conventional_or_explained",
        "Conventional / explained",
        "medium",
        "none",
        re.compile(r"\b(misidentification|identified as|explained as)\b", re.I),
    ),
    CraftPattern(
        "conventional_or_explained",
        "Conventional / explained",
        "medium",
        "none",
        re.compile(r"\brocket launch\b", re.I),
    ),
]

UFOCAT_MORPHOLOGY_TYPE_CODE_MAP: dict[str, tuple[str, str, str, str]] = {
    "2C": ("cigar_cylinder", "Cigar / cylinder", "medium", "medium"),
    "3C": ("cigar_cylinder", "Cigar / cylinder", "medium", "medium"),
    "4C": ("cigar_cylinder", "Cigar / cylinder", "medium", "medium"),
    "2D": ("disc_saucer", "Disc / saucer", "medium", "strong"),
    "3D": ("disc_saucer", "Disc / saucer", "medium", "strong"),
    "4D": ("disc_saucer", "Disc / saucer", "medium", "strong"),
    "5D": ("disc_saucer", "Disc / saucer", "medium", "strong"),
    "6D": ("disc_saucer", "Disc / saucer", "medium", "strong"),
    "7D": ("disc_saucer", "Disc / saucer", "medium", "strong"),
    "8D": ("disc_saucer", "Disc / saucer", "medium", "strong"),
    "2F": ("fireball_meteor_like", "Fireball / meteor-like", "medium", "weak"),
    "2G": ("fireball_meteor_like", "Fireball / meteor-like", "medium", "weak"),
    "2M": ("fireball_meteor_like", "Fireball / meteor-like", "medium", "weak"),
    "2X": ("fireball_meteor_like", "Fireball / meteor-like", "medium", "weak"),
    "2Z": ("chevron_boomerang", "Chevron / boomerang / V", "medium", "medium"),
    "3Z": ("chevron_boomerang", "Chevron / boomerang / V", "medium", "medium"),
}

UFOCAT_CONVENTIONAL_TYPE_CODES = {
    "1B",  # Balloon-like behavior.
    "1C",  # Comet.
    "1J",  # Jupiter.
    "1L",  # Moon.
    "1M",  # Mars.
    "1P",  # Sun.
    "1S",  # Star.
    "1V",  # Venus.
    "2E",  # Echo satellite.
    "2S",  # Sputnik satellite.
}


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def normalize_key(value: Any) -> str:
    return normalize_text(value).lower()


def is_unknownish(value: Any) -> bool:
    key = normalize_key(value)
    if key in UNKNOWN_VALUES:
        return True
    return key.startswith("unknown")


def stringify_raw_fields(raw_fields: Any) -> str:
    if not isinstance(raw_fields, dict):
        return ""
    parts: list[str] = []
    for key, value in raw_fields.items():
        if key and value is not None:
            text = normalize_text(value)
            if text:
                parts.append(f"{key}: {text}")
    return " | ".join(parts)


def result_from_mapping(
    craft_type: str,
    label: str,
    confidence: str,
    source: str,
    match_strength: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "craft_type_inferred": craft_type,
        "craft_type_label": label,
        "craft_type_confidence": confidence,
        "craft_type_source": source,
        "same_day_match_strength": match_strength,
        "craft_type_reason": reason,
    }


def unknown_result(
    *,
    source: str = "none",
    reason: str = "No direct craft-shape evidence found in shape/type/description fields.",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "craft_type_inferred": "unknown",
        "craft_type_label": "Unknown",
        "craft_type_confidence": "none",
        "craft_type_source": source,
        "same_day_match_strength": "none",
        "craft_type_reason": reason,
    }
    if metadata:
        result.update(metadata)
    return result


def is_ufocat_event(event: dict[str, Any]) -> bool:
    source_values = [
        event.get("source_name"),
        event.get("source"),
        event.get("collection"),
    ]
    raw_fields = event.get("raw_fields")
    if isinstance(raw_fields, dict):
        source_values.extend([
            raw_fields.get("source_name"),
            raw_fields.get("source"),
            raw_fields.get("collection"),
        ])
    return any(normalize_key(value) == "ufocat" for value in source_values)


def normalize_ufocat_code(value: Any) -> str:
    return re.sub(r"\s+", "", normalize_text(value).upper())


def ufocat_code_fields(event: dict[str, Any]) -> dict[str, str]:
    """Return explicit UFOCAT source-code fields without display fallbacks.

    ``type_raw`` is intentionally excluded. The UFOCAT CSV adapter historically
    fills ``type_raw`` from TYPE, then HYNEK, then VALLEE for display, so using it
    for source-code decoding can turn HYNEK:DD into a false TYPE:DD.
    """
    raw_fields = event.get("raw_fields")
    if not isinstance(raw_fields, dict):
        return {"TYPE": "", "SHAPE": "", "HYNEK": "", "VALLEE": ""}
    return {
        "TYPE": normalize_ufocat_code(raw_fields.get("TYPE") or raw_fields.get("type")),
        "SHAPE": normalize_text(raw_fields.get("SHAPE") or raw_fields.get("shape")),
        "HYNEK": normalize_ufocat_code(raw_fields.get("HYNEK") or raw_fields.get("hynek")),
        "VALLEE": normalize_ufocat_code(raw_fields.get("VALLEE") or raw_fields.get("vallee")),
    }


def infer_from_ufocat_shape_code(event: dict[str, Any]) -> dict[str, Any] | None:
    if not is_ufocat_event(event):
        return None
    shape = normalize_key(ufocat_code_fields(event).get("SHAPE"))
    if shape == "cloud":
        return unknown_result(
            source="ufocat_shape_code",
            reason="UFOCAT SHAPE `Cloud` is source morphology metadata, not enough to infer a craft type.",
            metadata={
                "object_morphology": "cloud_like",
                "craft_type_evidence": "UFOCAT SHAPE principal reported shape.",
                "craft_type_source_rule": "ufocat_shape_cloud_metadata",
            },
        )
    if shape == "copter":
        return unknown_result(
            source="ufocat_shape_code",
            reason="UFOCAT SHAPE `Copter` is a prosaic/conventional cue, not an anomalous craft type.",
            metadata={
                "prosaic_candidate": "helicopter_like",
                "craft_type_evidence": "UFOCAT SHAPE principal reported shape.",
                "craft_type_source_rule": "ufocat_shape_copter_prosaic",
            },
        )
    if shape == "aircraft":
        return unknown_result(
            source="ufocat_shape_code",
            reason="UFOCAT SHAPE `Aircraft` is a prosaic/conventional cue, not an anomalous craft type.",
            metadata={
                "prosaic_candidate": "aircraft_like",
                "craft_type_evidence": "UFOCAT SHAPE principal reported shape.",
                "craft_type_source_rule": "ufocat_shape_aircraft_prosaic",
            },
        )
    return None


def ufocat_has_contradictory_shape_or_prosaic_cue(event: dict[str, Any]) -> bool:
    fields = ufocat_code_fields(event)
    shape = normalize_key(fields.get("SHAPE"))
    if shape in {"aircraft", "copter", "cloud", "balloon"}:
        return True
    type_code = fields.get("TYPE")
    return bool(type_code[:2] in UFOCAT_CONVENTIONAL_TYPE_CODES)


def infer_from_ufocat_hynek_code(event: dict[str, Any]) -> dict[str, Any] | None:
    if not is_ufocat_event(event):
        return None
    fields = ufocat_code_fields(event)
    hynek = fields.get("HYNEK")
    if hynek == "DD":
        if ufocat_has_contradictory_shape_or_prosaic_cue(event):
            return unknown_result(
                source="ufocat_hynek_code",
                reason="HYNEK:DD was present but explicit UFOCAT shape/type evidence is contradictory or prosaic.",
                metadata={
                    "object_morphology": "daylight_disc_class",
                    "craft_type_evidence": "HYNEK daylight-disc classification contradicted by explicit UFOCAT shape/prosaic code.",
                    "craft_type_source_rule": "ufocat_hynek_daylight_disc_contradicted",
                    "unknown_reason": "candidate_needs_review",
                },
            )
        return result_from_mapping(
            "disc_saucer",
            "Disc / saucer",
            "medium",
            "ufocat_hynek_daylight_disc",
            "medium",
            "HYNEK:DD is the UFOCAT daylight-disc classification; applied only from raw_fields.HYNEK.",
        ) | {
            "craft_type_evidence": "HYNEK daylight-disc classification",
            "craft_type_source_rule": "ufocat_hynek_daylight_disc",
        }
    if re.fullmatch(r"CE[2345]", hynek):
        return unknown_result(
            source="ufocat_hynek_code",
            reason=f"HYNEK:{hynek} is an encounter class, not craft morphology.",
            metadata={
                "unknown_reason": "close_encounter_class_only",
                "craft_type_evidence": "HYNEK close-encounter classification.",
                "craft_type_source_rule": "ufocat_hynek_encounter_class_only",
            },
        )
    return None


def infer_from_ufocat_vallee_code(event: dict[str, Any]) -> dict[str, Any] | None:
    if not is_ufocat_event(event):
        return None
    vallee = ufocat_code_fields(event).get("VALLEE")
    if re.fullmatch(r"CE[2345]", vallee):
        return unknown_result(
            source="ufocat_vallee_code",
            reason=f"VALLEE:{vallee} is an encounter class, not craft morphology.",
            metadata={
                "unknown_reason": "close_encounter_class_only",
                "craft_type_evidence": "VALLEE close-encounter classification.",
                "craft_type_source_rule": "ufocat_vallee_encounter_class_only",
            },
        )
    return None


def infer_from_ufocat_type_code(event: dict[str, Any]) -> dict[str, Any] | None:
    if not is_ufocat_event(event):
        return None
    code = ufocat_code_fields(event).get("TYPE", "")
    if not code:
        return None
    if code.startswith("0"):
        return result_from_mapping(
            "non_ufo_context",
            "Non-UFO / contextual record",
            "high",
            "ufocat_type_code",
            "none",
            f"UFOCAT TYPE `{code}` has first digit 0, which the codebook defines as non-UFO context.",
        )
    prefix = code[:2]
    mapped = UFOCAT_MORPHOLOGY_TYPE_CODE_MAP.get(prefix)
    if mapped:
        craft_type, label, confidence, match_strength = mapped
        return result_from_mapping(
            craft_type,
            label,
            confidence,
            "ufocat_type_code",
            match_strength,
            f"UFOCAT TYPE `{code}` uses codebook morphology subcode `{prefix}`.",
        )
    if prefix in UFOCAT_CONVENTIONAL_TYPE_CODES:
        return result_from_mapping(
            "conventional_or_explained",
            "Conventional / explained",
            "medium",
            "ufocat_type_code",
            "none",
            f"UFOCAT TYPE `{code}` uses codebook conventional/astronomical subcode `{prefix}`.",
        )
    return None


def infer_from_text(text: str, *, source: str, source_confidence_cap: str | None = None) -> dict[str, Any] | None:
    cleaned = normalize_text(text)
    if not cleaned:
        return None
    for pattern in PATTERN_GROUPS:
        if pattern.pattern.search(cleaned):
            confidence = pattern.confidence
            if source_confidence_cap == "medium" and confidence == "high":
                confidence = "medium"
            if source_confidence_cap == "low":
                confidence = "low"
            return {
                "craft_type_inferred": pattern.craft_type,
                "craft_type_label": pattern.display_label,
                "craft_type_confidence": confidence,
                "craft_type_source": source,
                "same_day_match_strength": pattern.same_day_match_strength if confidence != "low" else "weak",
                "craft_type_reason": f"{source} matched /{pattern.pattern.pattern}/",
            }
    for pattern in EXPLAINED_PATTERNS:
        if pattern.pattern.search(cleaned):
            confidence = pattern.confidence
            if source_confidence_cap == "low":
                confidence = "low"
            return {
                "craft_type_inferred": pattern.craft_type,
                "craft_type_label": pattern.display_label,
                "craft_type_confidence": confidence,
                "craft_type_source": source,
                "same_day_match_strength": pattern.same_day_match_strength,
                "craft_type_reason": f"{source} matched /{pattern.pattern.pattern}/",
            }
    return None


def infer_from_legacy_shape_value(value: Any, *, source: str) -> dict[str, Any] | None:
    key = normalize_key(value)
    if not key or is_unknownish(key):
        return None
    mapped = LEGACY_SHAPE_VALUE_MAP.get(key)
    if not mapped:
        return None
    craft_type, label, confidence, match_strength = mapped
    return result_from_mapping(
        craft_type,
        label,
        confidence,
        source,
        match_strength,
        f"{source} exact legacy shape value `{key}`",
    )


def infer_event_craft_type(event: dict[str, Any]) -> dict[str, Any]:
    """Return a derived craft classification proposal for one event."""
    shape_fields = [
        ("shape_normalized", event.get("shape_normalized"), None),
        ("shape_raw", event.get("shape_raw"), None),
    ]
    for source, value, cap in shape_fields:
        if is_unknownish(value):
            continue
        result = infer_from_legacy_shape_value(value, source=source)
        if result:
            return result
        result = infer_from_text(normalize_text(value), source=source, source_confidence_cap=cap)
        if result:
            if normalize_key(value) in GENERIC_WEAK_TYPES:
                result = dict(result)
                result["craft_type_confidence"] = "low"
                result["same_day_match_strength"] = "weak"
            return result

    result = infer_from_ufocat_shape_code(event)
    if result:
        return result

    result = infer_from_ufocat_type_code(event)
    if result:
        return result

    result = infer_from_ufocat_hynek_code(event)
    if result and result.get("craft_type_inferred") != "unknown":
        return result

    source_fields = [
        ("type_normalized", event.get("type_normalized"), "medium"),
        ("type_raw", event.get("type_raw"), "medium"),
        ("description", event.get("description"), "medium"),
        ("summary", event.get("summary"), "medium"),
        ("raw_fields", stringify_raw_fields(event.get("raw_fields")), "medium"),
    ]
    for source, value, cap in source_fields:
        if source in {"type_normalized", "type_raw"} and is_unknownish(value):
            continue
        result = infer_from_text(normalize_text(value), source=source, source_confidence_cap=cap)
        if result:
            if normalize_key(value) in GENERIC_WEAK_TYPES:
                result = dict(result)
                result["craft_type_confidence"] = "low"
                result["same_day_match_strength"] = "weak"
            return result

    result = infer_from_ufocat_hynek_code(event)
    if result:
        return result
    result = infer_from_ufocat_vallee_code(event)
    if result:
        return result

    return unknown_result()
