"""Conservative duration normalization for the Analysis duration sidecar.

The normalizer intentionally accepts only source-documented encodings or
fully unit-bearing values.  It never reads narrative descriptions and never
assigns a unit to an undocumented bare number.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction
import math
import re
from typing import Any


DURATION_BINS = (
    "unknown",
    "under_10_seconds",
    "10_59_seconds",
    "1_4_minutes",
    "5_14_minutes",
    "15_59_minutes",
    "1_5_hours",
    "over_5_hours",
)

STATUS_CODES = (
    "unparsed",
    "exact",
    "closed_range",
    "approximate",
    "lower_censored",
    "upper_censored",
    "ambiguous",
)

UNIT_SECONDS = {
    "ms": 0.001,
    "msec": 0.001,
    "msecs": 0.001,
    "millisecond": 0.001,
    "milliseconds": 0.001,
    "s": 1.0,
    "sec": 1.0,
    "secs": 1.0,
    "second": 1.0,
    "seconds": 1.0,
    "m": 60.0,
    "min": 60.0,
    "mins": 60.0,
    "minute": 60.0,
    "minutes": 60.0,
    "h": 3600.0,
    "hr": 3600.0,
    "hrs": 3600.0,
    "hour": 3600.0,
    "hours": 3600.0,
    "d": 86400.0,
    "day": 86400.0,
    "days": 86400.0,
}

NUMBER_PATTERN = r"(?:\d+\s+\d+\s*/\s*\d+|\d+\s*/\s*\d+|\d+(?:\.\d+)?|\.\d+)"
UNIT_PATTERN = "(?:" + "|".join(sorted((re.escape(key) for key in UNIT_SECONDS), key=len, reverse=True)) + ")"
TOKEN_RE = re.compile(rf"(?P<number>{NUMBER_PATTERN})\s*(?P<unit>{UNIT_PATTERN})\b", re.IGNORECASE)
RANGE_RE = re.compile(
    rf"^(?P<lower>{NUMBER_PATTERN})\s*(?:-|to|through)\s*"
    rf"(?P<upper>{NUMBER_PATTERN})\s*(?P<unit>{UNIT_PATTERN})\.?$",
    re.IGNORECASE,
)
REPEATED_UNIT_RANGE_RE = re.compile(
    rf"^(?P<lower>{NUMBER_PATTERN})\s*(?P<lower_unit>{UNIT_PATTERN})\s*"
    rf"(?:-|to|through)\s*(?P<upper>{NUMBER_PATTERN})\s*(?P<upper_unit>{UNIT_PATTERN})\.?$",
    re.IGNORECASE,
)
CLOCK_RE = re.compile(r"^(?P<hours>\d{1,3}):(?P<minutes>[0-5]\d):(?P<seconds>[0-5]\d)$")

APPROXIMATE_RE = re.compile(
    r"(?:^|\s)(?:about|approx(?:\.|imately)?|approximately|around|circa|estimated|roughly|nearly|almost)(?:\s|$)",
    re.IGNORECASE,
)
LOWER_CENSORED_RE = re.compile(r"^(?:>|>=|more than|over|at least|minimum of)\s*", re.IGNORECASE)
UPPER_CENSORED_RE = re.compile(r"^(?:<|<=|less than|under|up to|maximum of)\s*", re.IGNORECASE)
TRAILING_APPROXIMATE_RE = re.compile(r"\s*\(?\s*(?:approx(?:\.)?|approximately|estimated)\s*\)?\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class DurationNormalization:
    status: str
    reason: str
    lower_seconds: float | None = None
    upper_seconds: float | None = None
    descriptive_bin: str = "unknown"
    inferential_bin: str = "unknown"
    source_contract: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _number(value: str) -> float:
    text = re.sub(r"\s+", " ", value.strip())
    mixed = re.fullmatch(r"(\d+)\s+(\d+)\s*/\s*(\d+)", text)
    if mixed:
        return float(int(mixed.group(1)) + Fraction(int(mixed.group(2)), int(mixed.group(3))))
    fraction = re.fullmatch(r"(\d+)\s*/\s*(\d+)", text)
    if fraction:
        return float(Fraction(int(fraction.group(1)), int(fraction.group(2))))
    return float(text)


def _clean_number(value: float | None) -> float | None:
    if value is None or not math.isfinite(value) or value < 0:
        return None
    rounded = round(value, 6)
    return int(rounded) if rounded.is_integer() else rounded


def duration_bin(seconds: float | None) -> str:
    if seconds is None or not math.isfinite(seconds) or seconds < 0:
        return "unknown"
    if seconds < 10:
        return "under_10_seconds"
    if seconds < 60:
        return "10_59_seconds"
    if seconds < 300:
        return "1_4_minutes"
    if seconds < 900:
        return "5_14_minutes"
    if seconds < 3600:
        return "15_59_minutes"
    if seconds <= 21600:
        return "1_5_hours"
    return "over_5_hours"


def _result(
    status: str,
    reason: str,
    lower: float | None = None,
    upper: float | None = None,
    *,
    source_contract: str,
) -> DurationNormalization:
    lower = _clean_number(lower)
    upper = _clean_number(upper)
    bins = {duration_bin(value) for value in (lower, upper) if value is not None}
    descriptive_bin = bins.pop() if len(bins) == 1 else "unknown"
    inferential_bin = (
        descriptive_bin
        if status in {"exact", "closed_range"} and descriptive_bin != "unknown"
        else "unknown"
    )
    return DurationNormalization(
        status=status,
        reason=reason,
        lower_seconds=lower,
        upper_seconds=upper,
        descriptive_bin=descriptive_bin,
        inferential_bin=inferential_bin,
        source_contract=source_contract,
    )


def _normalize_ufocat(raw_value: str) -> DurationNormalization:
    """Decode the pinned UFOCAT 2023 DUR contract.

    The local codebook defines bare quantities as minutes, H/D suffixes as
    hours/days, '+' as at least, and every DUR value as approximate.
    """

    contract = "ufocat_2023_codebook_dur"
    value = re.sub(r"\s+", "", raw_value).upper()
    if value in {"B", "VB", "F", "S", "H", "SH", ".F", ".S", "+H"}:
        return _result("ambiguous", "ufocat_qualitative_duration_code", source_contract=contract)
    match = re.fullmatch(r"(?P<censored>\+)?(?P<number>(?:\d+(?:\.\d+)?|\.\d+))(?P<unit>[HD])?", value)
    if not match:
        return _result("unparsed", "ufocat_code_not_recognized", source_contract=contract)
    number = float(match.group("number"))
    unit = match.group("unit") or "M"
    scale = {"M": 60.0, "H": 3600.0, "D": 86400.0}[unit]
    seconds = number * scale
    if match.group("censored"):
        return _result("lower_censored", "ufocat_at_least_code", seconds, None, source_contract=contract)
    if value.startswith(".") and unit == "M":
        # The codebook says tenths of minutes were rounded up.  Preserve the
        # documented interval, but retain approximate status as required.
        tenth = int(round(number * 10))
        lower = 0 if tenth == 0 else ((tenth * 6) - 3)
        upper = 2 if tenth == 0 else ((tenth * 6) + 2)
        return _result("approximate", "ufocat_rounded_tenth_minute", lower, upper, source_contract=contract)
    return _result("approximate", "ufocat_declared_approximate", seconds, seconds, source_contract=contract)


def _normalize_unit_text(raw_value: str) -> DurationNormalization:
    contract = "explicit_unit_text_v1"
    value = raw_value.strip().lower()
    value = value.replace("–", "-").replace("—", "-").replace("−", "-").replace("~", " about ")
    value = re.sub(r"\s+", " ", value).strip()
    if not re.search(r"\d", value):
        return _result("unparsed", "no_explicit_numeric_quantity", source_contract=contract)

    approximate = bool(APPROXIMATE_RE.search(value) or TRAILING_APPROXIMATE_RE.search(value))
    value = APPROXIMATE_RE.sub(" ", value)
    value = TRAILING_APPROXIMATE_RE.sub("", value)
    value = re.sub(r"\s+", " ", value).strip()

    censor_status = None
    if LOWER_CENSORED_RE.match(value):
        censor_status = "lower_censored"
        value = LOWER_CENSORED_RE.sub("", value, count=1).strip()
    elif UPPER_CENSORED_RE.match(value):
        censor_status = "upper_censored"
        value = UPPER_CENSORED_RE.sub("", value, count=1).strip()

    clock = CLOCK_RE.fullmatch(value)
    if clock:
        seconds = (
            int(clock.group("hours")) * 3600
            + int(clock.group("minutes")) * 60
            + int(clock.group("seconds"))
        )
        status = censor_status or ("approximate" if approximate else "exact")
        if status == "lower_censored":
            return _result(status, "explicit_clock_lower_censored", seconds, None, source_contract=contract)
        if status == "upper_censored":
            return _result(status, "explicit_clock_upper_censored", None, seconds, source_contract=contract)
        return _result(status, "explicit_clock_duration", seconds, seconds, source_contract=contract)

    repeated_range = REPEATED_UNIT_RANGE_RE.fullmatch(value)
    if repeated_range:
        lower = _number(repeated_range.group("lower")) * UNIT_SECONDS[repeated_range.group("lower_unit").lower()]
        upper = _number(repeated_range.group("upper")) * UNIT_SECONDS[repeated_range.group("upper_unit").lower()]
        if upper < lower:
            return _result("ambiguous", "descending_explicit_range", source_contract=contract)
        status = censor_status or ("approximate" if approximate else "closed_range")
        return _result(status, "explicit_repeated_unit_range", lower, upper, source_contract=contract)

    range_match = RANGE_RE.fullmatch(value)
    if range_match:
        scale = UNIT_SECONDS[range_match.group("unit").lower()]
        lower = _number(range_match.group("lower")) * scale
        upper = _number(range_match.group("upper")) * scale
        if upper < lower:
            return _result("ambiguous", "descending_explicit_range", source_contract=contract)
        status = censor_status or ("approximate" if approximate else "closed_range")
        return _result(status, "explicit_same_unit_range", lower, upper, source_contract=contract)

    matches = list(TOKEN_RE.finditer(value))
    if matches:
        residual = TOKEN_RE.sub(" ", value)
        residual = re.sub(r"[\s,;+&.]+", "", residual)
        if residual:
            return _result("unparsed", "unit_text_contains_unparsed_tokens", source_contract=contract)
        seconds = sum(
            _number(match.group("number")) * UNIT_SECONDS[match.group("unit").lower()]
            for match in matches
        )
        status = censor_status or ("approximate" if approximate else "exact")
        if status == "lower_censored":
            return _result(status, "explicit_unit_lower_censored", seconds, None, source_contract=contract)
        if status == "upper_censored":
            return _result(status, "explicit_unit_upper_censored", None, seconds, source_contract=contract)
        return _result(status, "explicit_unit_quantity", seconds, seconds, source_contract=contract)
    return _result("unparsed", "no_supported_unit_expression", source_contract=contract)


def normalize_duration(source_value: str, raw_value: Any) -> DurationNormalization:
    source = str(source_value or "").strip().lower()
    raw = "" if raw_value is None else str(raw_value).strip()
    if not raw:
        return _result("unparsed", "empty", source_contract="none")
    if source == "ufocat":
        return _normalize_ufocat(raw)
    if source == "majestic" and re.fullmatch(r"\d+(?:\.\d+)?", raw):
        return _result("unparsed", "majestic_numeric_unit_undocumented", source_contract="none")
    return _normalize_unit_text(raw)
