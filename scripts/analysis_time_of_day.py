"""Strict, provenance-preserving time-of-day normalization for Analysis.

The classifier reads only the explicit source clock field.  It never uses a
location, coordinate, date, narrative, or inferred timezone.  Exact-looking
midnight and noon values are deliberately held in a sentinel lane because
several source exports use them as defaults for unknown time.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any


STATUS_CODES = (
    "unparsed",
    "exact_clock",
    "approximate_clock",
    "clock_range",
    "qualitative_period",
    "sentinel_ambiguous",
    "invalid_clock",
)

TIME_BINS = (
    "unknown",
    "night_00_05",
    "morning_06_11",
    "afternoon_12_17",
    "evening_18_23",
)

QUALITATIVE_PERIODS = {
    "dawn": "dawn",
    "day": "daytime",
    "daylight": "daytime",
    "daytime": "daytime",
    "dusk": "dusk",
    "even": "evening",
    "evening": "evening",
    "morning": "morning",
    "night": "night",
    "nighttime": "night",
    "noon": "noon_qualitative",
    "midday": "noon_qualitative",
    "midnight": "midnight_qualitative",
}

APPROXIMATE_RE = re.compile(
    r"(?:^|\s|[-–—])(?:approx(?:\.|imately)?|about|around|circa|estimated|roughly|near|~)(?:\s|$)",
    re.IGNORECASE,
)
TRAILING_LOCAL_RE = re.compile(r"\s+(?P<label>local(?:\s+time)?|lt)$", re.IGNORECASE)
TRAILING_ZONE_RE = re.compile(
    r"\s+(?P<label>Z|UTC|GMT|[ECMPAHY][SD]T|AK[SD]T|HST|[+-]\d{2}:?\d{2})$",
    re.IGNORECASE,
)
AMPM_RE = re.compile(
    r"^(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))(?::(?P<second>\d{2})(?:\.\d+)?)?\s*(?P<ampm>[AP])\.?M\.?$",
    re.IGNORECASE,
)
COLON_RE = re.compile(r"^(?P<hour>\d{1,2}):(?P<minute>\d{2})(?::(?P<second>\d{2})(?:\.\d+)?)?$")
COMPACT_RE = re.compile(r"^(?P<hour>\d{2})(?P<minute>\d{2})$")
RANGE_SEPARATOR_RE = re.compile(r"\s*(?:-|–|—|to|through)\s*", re.IGNORECASE)


@dataclass(frozen=True)
class TimeOfDayNormalization:
    status: str
    reason: str
    lower_minute: int | None = None
    upper_minute: int | None = None
    descriptive_bin: str = "unknown"
    inferential_bin: str = "unknown"
    precision: str = "unknown"
    qualitative_period: str = ""
    timezone_label: str = ""
    timezone_semantics: str = "unknown"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def time_bin(minute: int | None) -> str:
    if minute is None or minute < 0 or minute >= 24 * 60:
        return "unknown"
    if minute < 6 * 60:
        return "night_00_05"
    if minute < 12 * 60:
        return "morning_06_11"
    if minute < 18 * 60:
        return "afternoon_12_17"
    return "evening_18_23"


def _result(
    status: str,
    reason: str,
    lower: int | None = None,
    upper: int | None = None,
    *,
    precision: str = "unknown",
    qualitative_period: str = "",
    timezone_label: str = "",
    timezone_semantics: str = "unknown",
) -> TimeOfDayNormalization:
    descriptive = time_bin(lower) if lower is not None and lower == upper else "unknown"
    inferential = descriptive if status == "exact_clock" else "unknown"
    return TimeOfDayNormalization(
        status=status,
        reason=reason,
        lower_minute=lower,
        upper_minute=upper,
        descriptive_bin=descriptive,
        inferential_bin=inferential,
        precision=precision,
        qualitative_period=qualitative_period,
        timezone_label=timezone_label,
        timezone_semantics=timezone_semantics,
    )


def _parse_clock(value: str) -> tuple[int, str] | None:
    match = AMPM_RE.fullmatch(value)
    if match:
        hour = int(match.group("hour"))
        minute = int(match.group("minute"))
        second = int(match.group("second") or 0)
        if not (1 <= hour <= 12 and minute <= 59 and second <= 59):
            return None
        if hour == 12:
            hour = 0
        if match.group("ampm").upper() == "P":
            hour += 12
        precision = "second" if match.group("second") is not None else "minute"
        return hour * 60 + minute, precision
    match = COLON_RE.fullmatch(value) or COMPACT_RE.fullmatch(value)
    if not match:
        return None
    hour = int(match.group("hour"))
    minute = int(match.group("minute"))
    second_text = match.groupdict().get("second")
    second = int(second_text or 0)
    if hour > 23 or minute > 59 or second > 59:
        return None
    precision = "second" if second_text is not None else "minute"
    return hour * 60 + minute, precision


def _strip_timezone(value: str) -> tuple[str, str, str]:
    local = TRAILING_LOCAL_RE.search(value)
    if local:
        return value[: local.start()].strip(), local.group("label"), "local_label_without_offset"
    zone = TRAILING_ZONE_RE.search(value)
    if zone:
        return value[: zone.start()].strip(), zone.group("label"), "explicit_label_not_converted"
    return value, "", "unknown"


def normalize_time_of_day(source_value: str, raw_value: Any) -> TimeOfDayNormalization:
    source = str(source_value or "unknown").strip().lower() or "unknown"
    raw = "" if raw_value is None else str(raw_value).strip()
    if not raw:
        return _result("unparsed", "empty")
    value = re.sub(r"\s+", " ", raw.replace("â€“", "–").replace("â€”", "—")).strip()
    lowered = value.lower().strip(" .")
    if lowered in QUALITATIVE_PERIODS:
        return _result(
            "qualitative_period",
            "explicit_qualitative_period",
            precision="qualitative",
            qualitative_period=QUALITATIVE_PERIODS[lowered],
        )

    value, timezone_label, timezone_semantics = _strip_timezone(value)
    approximate = value.lstrip().startswith("~") or bool(APPROXIMATE_RE.search(value))
    value = APPROXIMATE_RE.sub(" ", value).replace("~", " ")
    value = re.sub(r"\s+", " ", value).strip(" .")

    parts = RANGE_SEPARATOR_RE.split(value)
    if len(parts) == 2 and all(parts):
        lower = _parse_clock(parts[0])
        upper = _parse_clock(parts[1])
        if lower is None or upper is None:
            return _result("invalid_clock", "invalid_clock_range", timezone_label=timezone_label, timezone_semantics=timezone_semantics)
        if lower[0] in {0, 720} or upper[0] in {0, 720}:
            return _result("sentinel_ambiguous", "midnight_or_noon_range_endpoint", precision="range", timezone_label=timezone_label, timezone_semantics=timezone_semantics)
        return _result(
            "clock_range",
            "explicit_clock_range",
            lower[0],
            upper[0],
            precision="range",
            timezone_label=timezone_label,
            timezone_semantics=timezone_semantics,
        )
    if len(parts) > 2:
        return _result("invalid_clock", "multiple_range_separators", timezone_label=timezone_label, timezone_semantics=timezone_semantics)

    parsed = _parse_clock(value)
    if parsed is None:
        return _result("invalid_clock", "unsupported_or_invalid_clock", timezone_label=timezone_label, timezone_semantics=timezone_semantics)
    minute, precision = parsed
    if minute in {0, 720}:
        return _result(
            "sentinel_ambiguous",
            "midnight_or_noon_source_sentinel",
            precision=precision,
            timezone_label=timezone_label,
            timezone_semantics=timezone_semantics,
        )
    return _result(
        "approximate_clock" if approximate else "exact_clock",
        "explicit_approximate_clock" if approximate else "explicit_clock",
        minute,
        minute,
        precision=precision,
        timezone_label=timezone_label,
        timezone_semantics=timezone_semantics,
    )
