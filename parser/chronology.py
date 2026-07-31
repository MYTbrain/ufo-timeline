"""Same-day chronology derivation for playback and playback traces."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
import re
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


TIME_SORT_CONFIDENCE_RANK = {
    "high": 0,
    "medium": 1,
    "low": 2,
    "none": 3,
}

TIME_BUCKETS: dict[str, tuple[float, float, float]] = {
    "before_dawn": (210.0, 300.0, 255.0),
    "dawn": (300.0, 360.0, 330.0),
    "sunrise": (330.0, 390.0, 360.0),
    "early_morning": (360.0, 480.0, 420.0),
    "morning": (480.0, 660.0, 570.0),
    "late_morning": (630.0, 720.0, 675.0),
    "noon": (705.0, 735.0, 720.0),
    "early_afternoon": (720.0, 870.0, 795.0),
    "afternoon": (780.0, 1020.0, 900.0),
    "late_afternoon": (960.0, 1080.0, 1020.0),
    "sunset": (1050.0, 1110.0, 1080.0),
    "dusk": (1080.0, 1200.0, 1140.0),
    "evening": (1110.0, 1290.0, 1200.0),
    "late_evening": (1230.0, 1350.0, 1290.0),
    "night": (1260.0, 1439.0, 1350.0),
    "midnight": (1425.0, 15.0, 0.0),
    "after_midnight": (0.0, 180.0, 90.0),
}

BUCKET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bbefore dawn\b", re.IGNORECASE), "before_dawn"),
    (re.compile(r"\bshortly after midnight\b", re.IGNORECASE), "after_midnight"),
    (re.compile(r"\bafter midnight\b", re.IGNORECASE), "after_midnight"),
    (re.compile(r"\baround noon\b", re.IGNORECASE), "noon"),
    (re.compile(r"\bearly morning\b|\bearly am\b", re.IGNORECASE), "early_morning"),
    (re.compile(r"\blate morning\b", re.IGNORECASE), "late_morning"),
    (re.compile(r"\bearly afternoon\b", re.IGNORECASE), "early_afternoon"),
    (re.compile(r"\blate afternoon\b", re.IGNORECASE), "late_afternoon"),
    (re.compile(r"\blate evening\b", re.IGNORECASE), "late_evening"),
    (re.compile(r"\bshortly after sunset\b|\bnightfall\b|\btwilight\b", re.IGNORECASE), "dusk"),
    (re.compile(r"\bsunrise\b", re.IGNORECASE), "sunrise"),
    (re.compile(r"\bsunset\b", re.IGNORECASE), "sunset"),
    (re.compile(r"\bdawn\b", re.IGNORECASE), "dawn"),
    (re.compile(r"\bdusk\b", re.IGNORECASE), "dusk"),
    (re.compile(r"\bearly morning\b", re.IGNORECASE), "early_morning"),
    (re.compile(r"\bmorning\b", re.IGNORECASE), "morning"),
    (re.compile(r"\bafternoon\b|\bdaytime\b|\bdaylight\b", re.IGNORECASE), "afternoon"),
    (re.compile(r"\bevening\b", re.IGNORECASE), "evening"),
    (re.compile(r"\bnight\b", re.IGNORECASE), "night"),
    (re.compile(r"\bnoon\b", re.IGNORECASE), "noon"),
    (re.compile(r"\bmidnight\b", re.IGNORECASE), "midnight"),
]

EXPLICIT_TIMEZONE_OFFSETS = {
    "UTC": 0,
    "GMT": 0,
    "Z": 0,
    "ZULU": 0,
    "EST": -5 * 60,
    "EDT": -4 * 60,
    "CST": -6 * 60,
    "CDT": -5 * 60,
    "MST": -7 * 60,
    "MDT": -6 * 60,
    "PST": -8 * 60,
    "PDT": -7 * 60,
    "AKST": -9 * 60,
    "AKDT": -8 * 60,
    "HST": -10 * 60,
    "CET": 1 * 60,
    "CEST": 2 * 60,
    "EET": 2 * 60,
    "EEST": 3 * 60,
    "BST": 1 * 60,
    "JST": 9 * 60,
    "AEST": 10 * 60,
    "AEDT": 11 * 60,
}

EXPLICIT_TIMEZONE_REGEX = re.compile(
    r"(?<![A-Z])(?:UTC|GMT|ZULU|Z|EST|EDT|CST|CDT|MST|MDT|PST|PDT|AKST|AKDT|HST|CET|CEST|EET|EEST|BST|JST|AEST|AEDT)(?![A-Z])",
    re.IGNORECASE,
)

SINGLE_TIMEZONE_COUNTRIES = {
    "AUSTRIA": "Europe/Vienna",
    "BELGIUM": "Europe/Brussels",
    "BULGARIA": "Europe/Sofia",
    "CHINA": "Asia/Shanghai",
    "CROATIA": "Europe/Zagreb",
    "CZECH REPUBLIC": "Europe/Prague",
    "CZECHIA": "Europe/Prague",
    "DENMARK": "Europe/Copenhagen",
    "EGYPT": "Africa/Cairo",
    "ENGLAND": "Europe/London",
    "FINLAND": "Europe/Helsinki",
    "FRANCE": "Europe/Paris",
    "GERMANY": "Europe/Berlin",
    "GREECE": "Europe/Athens",
    "HUNGARY": "Europe/Budapest",
    "ICELAND": "Atlantic/Reykjavik",
    "INDIA": "Asia/Kolkata",
    "IRELAND": "Europe/Dublin",
    "ISRAEL": "Asia/Jerusalem",
    "ITALY": "Europe/Rome",
    "JAPAN": "Asia/Tokyo",
    "NETHERLANDS": "Europe/Amsterdam",
    "NEW ZEALAND": "Pacific/Auckland",
    "NORWAY": "Europe/Oslo",
    "PALESTINE": "Asia/Hebron",
    "POLAND": "Europe/Warsaw",
    "PORTUGAL": "Europe/Lisbon",
    "ROMANIA": "Europe/Bucharest",
    "SCOTLAND": "Europe/London",
    "SOUTH AFRICA": "Africa/Johannesburg",
    "SPAIN": "Europe/Madrid",
    "SWEDEN": "Europe/Stockholm",
    "SWITZERLAND": "Europe/Zurich",
    "TAIWAN": "Asia/Taipei",
    "TURKEY": "Europe/Istanbul",
    "UNITED KINGDOM": "Europe/London",
    "WALES": "Europe/London",
}

COUNTRY_ALIASES = {
    "AUS": "AUSTRALIA",
    "AUSTRALIA": "AUSTRALIA",
    "BRITAIN": "UNITED KINGDOM",
    "ENGL": "ENGLAND",
    "ENGLAND": "ENGLAND",
    "EIRE": "IRELAND",
    "FR": "FRANCE",
    "FRANCE": "FRANCE",
    "GERM": "GERMANY",
    "GERMANY": "GERMANY",
    "GREAT BRITAIN": "UNITED KINGDOM",
    "HOLLAND": "NETHERLANDS",
    "INDIA": "INDIA",
    "IRL": "IRELAND",
    "IRELAND": "IRELAND",
    "ISRAEL": "ISRAEL",
    "ITALY": "ITALY",
    "ITL": "ITALY",
    "JAPAN": "JAPAN",
    "MEXICO": "MEXICO",
    "NEW ZEALAND": "NEW ZEALAND",
    "NETH": "NETHERLANDS",
    "PALESTINE": "PALESTINE",
    "POLAND": "POLAND",
    "PORTUGAL": "PORTUGAL",
    "SCOTLAND": "SCOTLAND",
    "SPAIN": "SPAIN",
    "SWZ": "SWITZERLAND",
    "SWITZERLAND": "SWITZERLAND",
    "TURKEY": "TURKEY",
    "UK": "UNITED KINGDOM",
    "UNITED KINGDOM": "UNITED KINGDOM",
    "USA": "UNITED STATES",
    "US": "UNITED STATES",
    "U S A": "UNITED STATES",
    "UNITED STATES": "UNITED STATES",
    "WALES": "WALES",
}

STATE_OR_PROVINCE_ZONES = {
    "ALABAMA": "America/Chicago",
    "AL": "America/Chicago",
    "ARIZONA": "America/Phoenix",
    "AZ": "America/Phoenix",
    "ARKANSAS": "America/Chicago",
    "AR": "America/Chicago",
    "CALIFORNIA": "America/Los_Angeles",
    "CA": "America/Los_Angeles",
    "COLORADO": "America/Denver",
    "CO": "America/Denver",
    "CONNECTICUT": "America/New_York",
    "CT": "America/New_York",
    "DELAWARE": "America/New_York",
    "DE": "America/New_York",
    "DISTRICT OF COLUMBIA": "America/New_York",
    "DC": "America/New_York",
    "GEORGIA": "America/New_York",
    "GA": "America/New_York",
    "HAWAII": "Pacific/Honolulu",
    "HI": "Pacific/Honolulu",
    "ILLINOIS": "America/Chicago",
    "IL": "America/Chicago",
    "IOWA": "America/Chicago",
    "IA": "America/Chicago",
    "LOUISIANA": "America/Chicago",
    "LA": "America/Chicago",
    "MAINE": "America/New_York",
    "ME": "America/New_York",
    "MARYLAND": "America/New_York",
    "MD": "America/New_York",
    "MASSACHUSETTS": "America/New_York",
    "MA": "America/New_York",
    "MINNESOTA": "America/Chicago",
    "MN": "America/Chicago",
    "MISSISSIPPI": "America/Chicago",
    "MS": "America/Chicago",
    "MISSOURI": "America/Chicago",
    "MO": "America/Chicago",
    "MONTANA": "America/Denver",
    "MT": "America/Denver",
    "NEVADA": "America/Los_Angeles",
    "NV": "America/Los_Angeles",
    "NEW HAMPSHIRE": "America/New_York",
    "NH": "America/New_York",
    "NEW JERSEY": "America/New_York",
    "NJ": "America/New_York",
    "NEW MEXICO": "America/Denver",
    "NM": "America/Denver",
    "NEW YORK": "America/New_York",
    "NY": "America/New_York",
    "NORTH CAROLINA": "America/New_York",
    "NC": "America/New_York",
    "OHIO": "America/New_York",
    "OH": "America/New_York",
    "OKLAHOMA": "America/Chicago",
    "OK": "America/Chicago",
    "PENNSYLVANIA": "America/New_York",
    "PA": "America/New_York",
    "RHODE ISLAND": "America/New_York",
    "RI": "America/New_York",
    "SOUTH CAROLINA": "America/New_York",
    "SC": "America/New_York",
    "UTAH": "America/Denver",
    "UT": "America/Denver",
    "VERMONT": "America/New_York",
    "VT": "America/New_York",
    "VIRGINIA": "America/New_York",
    "VA": "America/New_York",
    "WASHINGTON": "America/Los_Angeles",
    "WA": "America/Los_Angeles",
    "WEST VIRGINIA": "America/New_York",
    "WV": "America/New_York",
    "WISCONSIN": "America/Chicago",
    "WI": "America/Chicago",
    "WYOMING": "America/Denver",
    "WY": "America/Denver",
    "ALBERTA": "America/Edmonton",
    "AB": "America/Edmonton",
    "BRITISH COLUMBIA": "America/Vancouver",
    "BC": "America/Vancouver",
    "MANITOBA": "America/Winnipeg",
    "MB": "America/Winnipeg",
    "NEW BRUNSWICK": "America/Moncton",
    "NB": "America/Moncton",
    "NEWFOUNDLAND": "America/St_Johns",
    "NL": "America/St_Johns",
    "NOVA SCOTIA": "America/Halifax",
    "NS": "America/Halifax",
    "ONTARIO": "America/Toronto",
    "ON": "America/Toronto",
    "PRINCE EDWARD ISLAND": "America/Halifax",
    "PE": "America/Halifax",
    "QUEBEC": "America/Toronto",
    "QC": "America/Toronto",
    "SASKATCHEWAN": "America/Regina",
    "SK": "America/Regina",
    "AUSTRALIAN CAPITAL TERRITORY": "Australia/Sydney",
    "NEW SOUTH WALES": "Australia/Sydney",
    "NSW": "Australia/Sydney",
    "NORTHERN TERRITORY": "Australia/Darwin",
    "NT": "Australia/Darwin",
    "QUEENSLAND": "Australia/Brisbane",
    "QLD": "Australia/Brisbane",
    "SOUTH AUSTRALIA": "Australia/Adelaide",
    "SA": "Australia/Adelaide",
    "TASMANIA": "Australia/Hobart",
    "TAS": "Australia/Hobart",
    "VICTORIA": "Australia/Melbourne",
    "VIC": "Australia/Melbourne",
    "WESTERN AUSTRALIA": "Australia/Perth",
    "WAU": "Australia/Perth",
}

AMBIGUOUS_STATE_NAMES = {
    "ALASKA",
    "FLORIDA",
    "IDAHO",
    "INDIANA",
    "KANSAS",
    "KENTUCKY",
    "MICHIGAN",
    "NEBRASKA",
    "NORTH DAKOTA",
    "OREGON",
    "SOUTH DAKOTA",
    "TENNESSEE",
    "TEXAS",
}

PRECISION_CITY_LEVEL = {"exact_coords", "address", "city", "county"}
PRECISION_LOW_CONFIDENCE = {"country", "approximate", "multi_location", "unknown"}

APPROXIMATE_PREFIX_RE = re.compile(r"^(?:~|about|around|approx(?:\.|imately)?|ca\.?|circa)\s+", re.IGNORECASE)
APPROXIMATE_SUFFIX_RE = re.compile(r"\?$")
TIME_RANGE_RE = re.compile(r"^(?:between|from)\s+(.+?)\s+(?:and|to)\s+(.+)$", re.IGNORECASE)
TIME_TOKEN_RE = re.compile(r"^\s*(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)?\s*$", re.IGNORECASE)
HOURS_TOKEN_RE = re.compile(r"^\s*(\d{3,4})\s*hours?\s*$", re.IGNORECASE)
TWELVE_NOON_RE = re.compile(r"^\s*12\s+noon\s*$", re.IGNORECASE)
TWELVE_MIDNIGHT_RE = re.compile(r"^\s*12\s+midnight\s*$", re.IGNORECASE)
LOCAL_DATE_RE = re.compile(r"^(?P<year>-?\d{4})-(?P<month>\d{2})-(?P<day>\d{2})$")


@dataclass(slots=True)
class ParsedTimeInfo:
    sort_kind: str = "unknown"
    sort_confidence: str = "none"
    bucket_label: str | None = None
    local_minutes: float | None = None
    range_start_minutes: float | None = None
    range_end_minutes: float | None = None
    explicit_timezone_token: str | None = None


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    normalized = re.sub(r"[^A-Za-z0-9]+", " ", str(value).upper())
    return re.sub(r"\s+", " ", normalized).strip()


def _event_id_sort_value(event: dict[str, Any]) -> tuple[int, str]:
    raw_id = event.get("event_id")
    try:
        return (0, str(int(raw_id)))
    except (TypeError, ValueError):
        return (1, str(raw_id or ""))


def _coerce_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isfinite(number):
        return number
    return None


def _local_date_parts(date_iso: str | None) -> tuple[int, int, int] | None:
    if not date_iso:
        return None
    match = LOCAL_DATE_RE.match(date_iso)
    if not match:
        return None
    return (
        int(match.group("year")),
        int(match.group("month")),
        int(match.group("day")),
    )


def _sanitized_time_text(time_raw: str) -> str:
    value = str(time_raw or "").strip()
    if not value:
        return ""
    value = re.sub(r"(?<=\d)[oO](?=\d)", "0", value)
    value = re.sub(r"(?<=\d)[lI](?=\d)", "1", value)
    value = re.sub(r"(?<=\d)\.(?=\d)", ":", value)
    return re.sub(r"\s+", " ", value).strip()


def _extract_explicit_timezone_token(time_text: str) -> tuple[str, str | None]:
    if not time_text:
        return "", None
    match = EXPLICIT_TIMEZONE_REGEX.search(time_text)
    if not match:
        return time_text, None
    token = match.group(0).upper()
    stripped = (time_text[:match.start()] + " " + time_text[match.end():]).strip()
    stripped = re.sub(r"\s+", " ", stripped)
    return stripped, token


def _normalize_ampm(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.lower().replace(".", "")
    if cleaned in {"am", "pm"}:
        return cleaned
    return None


def _clock_minutes_from_parts(hours: int, minutes: int, ampm: str | None) -> float | None:
    if minutes < 0 or minutes > 59 or hours < 0:
        return None
    if ampm:
        if hours < 1 or hours > 12:
            return None
        if ampm == "am":
            hours = 0 if hours == 12 else hours
        else:
            hours = 12 if hours == 12 else hours + 12
    else:
        if hours > 23:
            return None
    return float((hours * 60) + minutes)


def _parse_clock_token(token: str, inherited_ampm: str | None = None) -> float | None:
    token = token.strip()
    if not token:
        return None

    if TWELVE_NOON_RE.match(token):
        return 720.0
    if TWELVE_MIDNIGHT_RE.match(token):
        return 0.0

    match = TIME_TOKEN_RE.match(token)
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2) or "0")
        ampm = _normalize_ampm(match.group(3)) or inherited_ampm
        return _clock_minutes_from_parts(hours, minutes, ampm)

    match = HOURS_TOKEN_RE.match(token)
    if match:
        value = match.group(1)
        if len(value) == 3:
            hours = int(value[0])
            minutes = int(value[1:])
        else:
            hours = int(value[:2])
            minutes = int(value[2:])
        return _clock_minutes_from_parts(hours, minutes, None)

    if token.lower() == "noon":
        return 720.0
    if token.lower() == "midnight":
        return 0.0
    return None


def _time_range_midpoint(start_minutes: float, end_minutes: float) -> tuple[float, float, float]:
    if end_minutes < start_minutes:
        end_minutes += 1440.0
    midpoint = start_minutes + ((end_minutes - start_minutes) / 2)
    return midpoint % 1440.0, start_minutes % 1440.0, end_minutes % 1440.0


def _normalized_range_width(
    start_minutes: float | None,
    end_minutes: float | None,
    *,
    modulo: float | None = None,
) -> float | None:
    if start_minutes is None or end_minutes is None:
        return None
    width = end_minutes - start_minutes
    if modulo and width < 0:
        width += modulo
    return abs(width)


def _expanded_local_range(start_minutes: float, end_minutes: float) -> tuple[float, float]:
    if end_minutes < start_minutes:
        end_minutes += 1440.0
    return start_minutes, end_minutes


def _parse_approximate_range(time_text: str) -> ParsedTimeInfo | None:
    match = TIME_RANGE_RE.match(time_text)
    if not match:
        return None
    left = match.group(1).strip()
    right = match.group(2).strip()
    right_ampm_match = re.search(r"\b([ap]\.?m\.?)\b", right, re.IGNORECASE)
    inherited_ampm = _normalize_ampm(right_ampm_match.group(1)) if right_ampm_match else None
    start_minutes = _parse_clock_token(left, inherited_ampm=inherited_ampm)
    end_minutes = _parse_clock_token(right)
    if start_minutes is None or end_minutes is None:
        return None
    midpoint, range_start, range_end = _time_range_midpoint(start_minutes, end_minutes)
    return ParsedTimeInfo(
        sort_kind="approximate",
        sort_confidence="medium",
        local_minutes=midpoint,
        range_start_minutes=range_start,
        range_end_minutes=range_end,
    )


def _bucket_info(label: str) -> ParsedTimeInfo:
    start_minutes, end_minutes, midpoint = TIME_BUCKETS[label]
    return ParsedTimeInfo(
        sort_kind="bucketed",
        sort_confidence="low",
        bucket_label=label,
        local_minutes=midpoint,
        range_start_minutes=start_minutes,
        range_end_minutes=end_minutes,
    )


def parse_time_for_chronology(time_raw: str | None, *, exact_day: bool) -> ParsedTimeInfo:
    if not exact_day or not time_raw:
        return ParsedTimeInfo()

    time_text = _sanitized_time_text(time_raw)
    if not time_text:
        return ParsedTimeInfo()

    without_tz, explicit_timezone_token = _extract_explicit_timezone_token(time_text)
    lowered = without_tz.lower().strip()

    for pattern, label in BUCKET_PATTERNS:
        if pattern.search(without_tz):
            parsed = _bucket_info(label)
            parsed.explicit_timezone_token = explicit_timezone_token
            if lowered == "around midnight":
                parsed.sort_kind = "approximate"
                parsed.sort_confidence = "medium"
            return parsed

    range_info = _parse_approximate_range(without_tz)
    if range_info:
        range_info.explicit_timezone_token = explicit_timezone_token
        return range_info

    approximate = False
    cleaned = without_tz.strip()
    if APPROXIMATE_PREFIX_RE.match(cleaned):
        approximate = True
        cleaned = APPROXIMATE_PREFIX_RE.sub("", cleaned, count=1).strip()
    if APPROXIMATE_SUFFIX_RE.search(cleaned):
        approximate = True
        cleaned = APPROXIMATE_SUFFIX_RE.sub("", cleaned).strip()

    if cleaned.lower() == "around midnight":
        return ParsedTimeInfo(
            sort_kind="approximate",
            sort_confidence="medium",
            local_minutes=0.0,
            range_start_minutes=1425.0,
            range_end_minutes=15.0,
            explicit_timezone_token=explicit_timezone_token,
        )

    exact_minutes = _parse_clock_token(cleaned)
    if exact_minutes is not None:
        return ParsedTimeInfo(
            sort_kind="approximate" if approximate else "exact",
            sort_confidence="medium" if approximate else "high",
            local_minutes=exact_minutes,
            range_start_minutes=exact_minutes if not approximate else max(0.0, exact_minutes - 30.0),
            range_end_minutes=exact_minutes if not approximate else min(1439.0, exact_minutes + 30.0),
            explicit_timezone_token=explicit_timezone_token,
        )

    return ParsedTimeInfo(explicit_timezone_token=explicit_timezone_token)


def _location_texts(event: dict[str, Any]) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for raw_value in (
        event.get("geocode_display_name"),
        event.get("primary_location_text"),
        event.get("location_raw"),
        *(event.get("all_locations_raw") or []),
    ):
        text = str(raw_value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        values.append(text)
    return values


def _text_contains_alias(normalized_texts: list[str], alias: str) -> bool:
    alias_normalized = _normalize_text(alias)
    if not alias_normalized:
        return False
    alias_tokens = alias_normalized.split()
    for text in normalized_texts:
        if len(alias_tokens) == 1 and len(alias_tokens[0]) <= 3:
            if alias_tokens[0] in text.split():
                return True
            continue
        if text == alias_normalized or f" {alias_normalized} " in f" {text} ":
            return True
    return False


def _matched_country_zone(event: dict[str, Any], normalized_texts: list[str]) -> tuple[str | None, str | None]:
    for alias, canonical in COUNTRY_ALIASES.items():
        if not _text_contains_alias(normalized_texts, alias):
            continue
        zone_name = SINGLE_TIMEZONE_COUNTRIES.get(canonical)
        if zone_name:
            return canonical, zone_name
    return None, None


def _matched_state_zone(normalized_texts: list[str]) -> tuple[str | None, str | None]:
    for alias, zone_name in STATE_OR_PROVINCE_ZONES.items():
        if _text_contains_alias(normalized_texts, alias):
            return alias, zone_name
    return None, None


def _exact_coordinate_source(event: dict[str, Any]) -> bool:
    return (
        event.get("location_precision") == "exact_coords"
        or event.get("coordinate_source") in {"raw_latlong", "location_coordinates"}
    )


def _mapped_coordinate_source(event: dict[str, Any]) -> bool:
    if not (event.get("lat") is not None and event.get("lon") is not None):
        return False
    if _exact_coordinate_source(event):
        return False
    return event.get("coordinate_source") not in {"unresolved", None}


def _infer_timezone(event: dict[str, Any]) -> tuple[str | None, str, str]:
    texts = _location_texts(event)
    normalized_texts = [_normalize_text(text) for text in texts if text]
    if not normalized_texts:
        return None, "unknown", "none"

    precision = str(event.get("location_precision") or "unknown")
    state_alias, state_zone = _matched_state_zone(normalized_texts)
    country_alias, country_zone = _matched_country_zone(event, normalized_texts)
    exact_coords = _exact_coordinate_source(event)
    mapped_coords = _mapped_coordinate_source(event)
    city_precision = precision in PRECISION_CITY_LEVEL

    if state_zone:
        ambiguous_state = state_alias in AMBIGUOUS_STATE_NAMES
        if exact_coords:
            return state_zone, "exact_coordinates", "medium" if ambiguous_state else "high"
        if mapped_coords:
            return state_zone, "mapped_coordinates", "medium" if ambiguous_state else "high"
        if city_precision:
            return state_zone, "city_match", "medium" if ambiguous_state else "high"
        return state_zone, "state_country_inference", "low" if ambiguous_state else "medium"

    if country_zone:
        if precision == "country":
            return country_zone, "country_only", "low"
        if exact_coords:
            return country_zone, "exact_coordinates", "high"
        if mapped_coords:
            return country_zone, "mapped_coordinates", "medium"
        if city_precision:
            return country_zone, "city_match", "medium"
        if precision == "state_province":
            return country_zone, "state_country_inference", "medium"
        return country_zone, "country_only", "low"

    return None, "unknown", "none"


def _explicit_timezone_resolution(
    event: dict[str, Any],
    token: str | None,
    parsed_time: ParsedTimeInfo,
) -> tuple[str | None, str, str, int | None]:
    if not token:
        return None, "unknown", "none", None
    token = token.upper()
    if token not in EXPLICIT_TIMEZONE_OFFSETS:
        inferred_zone, _, inferred_confidence = _infer_timezone(event)
        return inferred_zone, "source_explicit", inferred_confidence if inferred_zone else "none", None
    offset_minutes = EXPLICIT_TIMEZONE_OFFSETS[token]
    if token in {"UTC", "GMT", "Z", "ZULU"}:
        return "UTC", "source_explicit", "high", offset_minutes

    inferred_zone, _, inferred_confidence = _infer_timezone(event)
    if inferred_zone and parsed_time.local_minutes is not None:
        local_parts = _local_date_parts(event.get("date_iso"))
        if local_parts:
            year, month, day = local_parts
            if year >= 1:
                expected_offset = _zone_offset_minutes(
                    inferred_zone,
                    year,
                    month,
                    day,
                    parsed_time.local_minutes,
                )
                if expected_offset == offset_minutes:
                    return inferred_zone, "source_explicit", "high" if inferred_confidence != "low" else "medium", offset_minutes
    return None, "source_explicit", "high", offset_minutes


def _confidence_from_time_kind(time_kind: str) -> str:
    if time_kind == "exact":
        return "high"
    if time_kind == "approximate":
        return "medium"
    if time_kind == "bucketed":
        return "low"
    return "none"


def _compose_sort_key(
    event: dict[str, Any],
    *,
    group: int,
    primary_value: float | int | None,
    range_width: float | int | None,
    confidence: str,
) -> list[Any]:
    fallback_group, fallback_value = _event_id_sort_value(event)
    return [
        group,
        primary_value,
        range_width,
        TIME_SORT_CONFIDENCE_RANK.get(confidence, 3),
        fallback_group,
        fallback_value,
    ]


def _round_milliseconds(value: float) -> int:
    return int(round(value))


def _to_epoch_ms(dt_value: datetime) -> int:
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    delta = dt_value.astimezone(timezone.utc) - epoch
    return _round_milliseconds(delta.total_seconds() * 1000)


def _zone_offset_minutes(zone_name: str, year: int, month: int, day: int, local_minutes: float) -> int | None:
    try:
        zone = ZoneInfo(zone_name)
    except ZoneInfoNotFoundError:
        return None
    if year < 1:
        return None
    hour = int(local_minutes // 60)
    minute = int(round(local_minutes % 60))
    if minute >= 60:
        hour += 1
        minute -= 60
    if hour >= 24:
        hour = 23
        minute = 59
    aware = datetime(year, month, day, hour, minute, tzinfo=zone)
    offset = aware.utcoffset()
    if offset is None:
        return None
    return int(round(offset.total_seconds() / 60))


def _roundtrip_local_datetime(
    year: int,
    month: int,
    day: int,
    minutes_after_midnight: float,
    zone_name: str,
) -> tuple[str, list[datetime]]:
    try:
        zone = ZoneInfo(zone_name)
    except ZoneInfoNotFoundError:
        return "invalid_zone", []
    if year < 1:
        return "unsupported_year", []

    base_midnight = datetime(year, month, day)
    naive = base_midnight + timedelta(minutes=minutes_after_midnight)
    candidates: list[datetime] = []
    seen: set[tuple[int, int]] = set()
    for fold in (0, 1):
        aware = naive.replace(tzinfo=zone, fold=fold)
        utc_value = aware.astimezone(timezone.utc)
        roundtrip = utc_value.astimezone(zone).replace(tzinfo=None)
        if roundtrip != naive:
            continue
        marker = (utc_value.year, int(utc_value.timestamp()) if utc_value.year >= 1970 else hash((utc_value.year, utc_value.month, utc_value.day, utc_value.hour, utc_value.minute, utc_value.utcoffset())))
        if marker in seen:
            continue
        seen.add(marker)
        candidates.append(aware)

    if not candidates:
        return "nonexistent", []
    if len(candidates) > 1:
        return "ambiguous", candidates
    return "ok", candidates


def _compute_utc_range_for_zone(
    event: dict[str, Any],
    zone_name: str,
    range_start_minutes: float,
    range_end_minutes: float,
    *,
    explicit_offset_minutes: int | None = None,
) -> tuple[int | None, int | None, int | None, bool]:
    local_parts = _local_date_parts(event.get("date_iso"))
    if not local_parts:
        return None, None, None, False
    year, month, day = local_parts
    if year < 1:
        return None, None, None, False

    expanded_start_minutes, expanded_end_minutes = _expanded_local_range(range_start_minutes, range_end_minutes)

    if explicit_offset_minutes is not None:
        start_ms = _fixed_offset_utc_ms(year, month, day, expanded_start_minutes, explicit_offset_minutes)
        end_ms = _fixed_offset_utc_ms(year, month, day, expanded_end_minutes, explicit_offset_minutes)
        midpoint = _fixed_offset_utc_ms(
            year,
            month,
            day,
            expanded_start_minutes + ((expanded_end_minutes - expanded_start_minutes) / 2.0),
            explicit_offset_minutes,
        )
        return midpoint, start_ms, end_ms, False

    status_start, start_candidates = _roundtrip_local_datetime(year, month, day, expanded_start_minutes, zone_name)
    status_end, end_candidates = _roundtrip_local_datetime(year, month, day, expanded_end_minutes, zone_name)
    if status_start != "ok" or status_end != "ok" or not start_candidates or not end_candidates:
        return None, None, None, status_start == "ambiguous" or status_end == "ambiguous"

    start_utc = start_candidates[0].astimezone(timezone.utc)
    end_utc = end_candidates[0].astimezone(timezone.utc)
    midpoint_delta = end_utc - start_utc
    midpoint_utc = start_utc + (midpoint_delta / 2)
    return _to_epoch_ms(midpoint_utc), _to_epoch_ms(start_utc), _to_epoch_ms(end_utc), False


def _fixed_offset_utc_ms(year: int, month: int, day: int, local_minutes: float, offset_minutes: int) -> int:
    aware = datetime(
        year,
        month,
        day,
        tzinfo=timezone(timedelta(minutes=offset_minutes)),
    ) + timedelta(minutes=local_minutes)
    return _to_epoch_ms(aware.astimezone(timezone.utc))


def _solar_event_local_minutes(
    year: int,
    month: int,
    day: int,
    latitude: float,
    longitude: float,
    offset_minutes: int,
    *,
    event_name: str,
) -> float | None:
    try:
        day_of_year = datetime(year, month, day).timetuple().tm_yday
    except ValueError:
        return None

    zenith = {
        "sunrise": 90.833,
        "sunset": 90.833,
        "dawn": 96.0,
        "dusk": 96.0,
    }[event_name]
    lng_hour = longitude / 15.0
    approximate_time = day_of_year + (((6.0 if event_name in {"sunrise", "dawn"} else 18.0) - lng_hour) / 24.0)
    mean_anomaly = (0.9856 * approximate_time) - 3.289
    true_longitude = mean_anomaly + (1.916 * math.sin(math.radians(mean_anomaly))) + (0.020 * math.sin(math.radians(2 * mean_anomaly))) + 282.634
    true_longitude %= 360.0
    right_ascension = math.degrees(math.atan(0.91764 * math.tan(math.radians(true_longitude))))
    right_ascension %= 360.0
    l_quadrant = math.floor(true_longitude / 90.0) * 90.0
    ra_quadrant = math.floor(right_ascension / 90.0) * 90.0
    right_ascension = (right_ascension + (l_quadrant - ra_quadrant)) / 15.0
    sin_declination = 0.39782 * math.sin(math.radians(true_longitude))
    cos_declination = math.cos(math.asin(sin_declination))
    cos_hour_angle = (
        math.cos(math.radians(zenith))
        - (sin_declination * math.sin(math.radians(latitude)))
    ) / (cos_declination * math.cos(math.radians(latitude)))
    if cos_hour_angle < -1.0 or cos_hour_angle > 1.0:
        return None
    hour_angle = math.degrees(math.acos(cos_hour_angle))
    if event_name in {"sunrise", "dawn"}:
        hour_angle = 360.0 - hour_angle
    local_mean_time = (hour_angle / 15.0) + right_ascension - (0.06571 * approximate_time) - 6.622
    utc_hours = (local_mean_time - lng_hour) % 24.0
    local_hours = (utc_hours + (offset_minutes / 60.0)) % 24.0
    return local_hours * 60.0


def _apply_solar_bucket(
    event: dict[str, Any],
    parsed: ParsedTimeInfo,
    *,
    resolved_timezone: str | None,
    explicit_offset_minutes: int | None,
    timezone_confidence: str,
) -> ParsedTimeInfo:
    if parsed.bucket_label not in {"sunrise", "sunset", "dawn", "dusk"}:
        return parsed
    if timezone_confidence not in {"high", "medium"} and explicit_offset_minutes is None:
        return parsed
    date_parts = _local_date_parts(event.get("date_iso"))
    if not date_parts:
        return parsed
    lat = _coerce_float(event.get("lat"))
    lon = _coerce_float(event.get("lon"))
    if lat is None or lon is None:
        return parsed

    year, month, day = date_parts
    if year < 1:
        return parsed
    offset_minutes = explicit_offset_minutes
    if offset_minutes is None and resolved_timezone:
        offset_minutes = _zone_offset_minutes(resolved_timezone, year, month, day, 720.0)
    if offset_minutes is None:
        return parsed

    solar_minutes = _solar_event_local_minutes(
        year,
        month,
        day,
        lat,
        lon,
        offset_minutes,
        event_name=parsed.bucket_label,
    )
    if solar_minutes is None:
        return parsed

    half_window = 30.0 if parsed.bucket_label in {"sunrise", "sunset"} else 45.0
    parsed.local_minutes = solar_minutes
    parsed.range_start_minutes = max(0.0, solar_minutes - half_window)
    parsed.range_end_minutes = min(1439.0, solar_minutes + half_window)
    return parsed


def derive_event_chronology(event: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {
        "time_sort_kind": "unknown",
        "time_sort_confidence": "none",
        "time_bucket_label": None,
        "parsed_time_local_minutes": None,
        "parsed_time_local_range_start_minutes": None,
        "parsed_time_local_range_end_minutes": None,
        "resolved_timezone": None,
        "timezone_source": "unknown",
        "timezone_confidence": "none",
        "estimated_utc_timestamp_ms": None,
        "estimated_utc_range_start_ms": None,
        "estimated_utc_range_end_ms": None,
        "playback_sort_confidence": "none",
        "playback_sort_reason": "stable_fallback",
        "playback_sort_key": _compose_sort_key(event, group=3, primary_value=None, range_width=None, confidence="none"),
    }

    exact_day = event.get("date_precision") == "exact_day" and bool(event.get("date_iso"))
    parsed_time = parse_time_for_chronology(event.get("time_raw"), exact_day=exact_day)

    output["time_sort_kind"] = parsed_time.sort_kind
    output["time_sort_confidence"] = parsed_time.sort_confidence
    output["time_bucket_label"] = parsed_time.bucket_label
    output["parsed_time_local_minutes"] = parsed_time.local_minutes
    output["parsed_time_local_range_start_minutes"] = parsed_time.range_start_minutes
    output["parsed_time_local_range_end_minutes"] = parsed_time.range_end_minutes

    if not exact_day or parsed_time.sort_kind == "unknown" or parsed_time.local_minutes is None:
        return output

    resolved_timezone, timezone_source, timezone_confidence, explicit_offset_minutes = _explicit_timezone_resolution(
        event,
        parsed_time.explicit_timezone_token,
        parsed_time,
    )
    if timezone_source == "unknown":
        resolved_timezone, timezone_source, timezone_confidence = _infer_timezone(event)

    parsed_time = _apply_solar_bucket(
        event,
        parsed_time,
        resolved_timezone=resolved_timezone,
        explicit_offset_minutes=explicit_offset_minutes,
        timezone_confidence=timezone_confidence,
    )

    output["time_sort_kind"] = parsed_time.sort_kind
    output["time_sort_confidence"] = parsed_time.sort_confidence
    output["time_bucket_label"] = parsed_time.bucket_label
    output["parsed_time_local_minutes"] = parsed_time.local_minutes
    output["parsed_time_local_range_start_minutes"] = parsed_time.range_start_minutes
    output["parsed_time_local_range_end_minutes"] = parsed_time.range_end_minutes
    output["resolved_timezone"] = resolved_timezone
    output["timezone_source"] = timezone_source
    output["timezone_confidence"] = timezone_confidence

    local_range_width = _normalized_range_width(
        parsed_time.range_start_minutes,
        parsed_time.range_end_minutes,
        modulo=1440.0,
    )

    use_utc = False
    if explicit_offset_minutes is not None:
        use_utc = True
    elif resolved_timezone and timezone_confidence in {"high", "medium"}:
        use_utc = True

    if use_utc and parsed_time.range_start_minutes is not None and parsed_time.range_end_minutes is not None:
        utc_midpoint, utc_start, utc_end, utc_ambiguous = _compute_utc_range_for_zone(
            event,
            resolved_timezone or "UTC",
            parsed_time.range_start_minutes,
            parsed_time.range_end_minutes,
            explicit_offset_minutes=explicit_offset_minutes,
        )
        if utc_midpoint is not None and utc_start is not None and utc_end is not None and not utc_ambiguous:
            output["estimated_utc_timestamp_ms"] = utc_midpoint
            output["estimated_utc_range_start_ms"] = utc_start
            output["estimated_utc_range_end_ms"] = utc_end
            if parsed_time.sort_kind == "exact":
                output["playback_sort_confidence"] = "high" if explicit_offset_minutes is not None or timezone_confidence == "high" else "medium"
            elif parsed_time.sort_kind == "approximate":
                output["playback_sort_confidence"] = "medium" if timezone_confidence != "low" else "low"
            else:
                output["playback_sort_confidence"] = "low"
            output["playback_sort_reason"] = {
                ("exact", True): "exact_time_with_explicit_timezone",
                ("exact", False): "exact_time_with_inferred_timezone",
                ("approximate", True): "approximate_time_with_explicit_timezone",
                ("approximate", False): "approximate_time_with_inferred_timezone",
                ("bucketed", True): "bucketed_time_with_explicit_timezone",
                ("bucketed", False): "bucketed_time_with_inferred_timezone",
            }[(parsed_time.sort_kind, explicit_offset_minutes is not None or timezone_source == "source_explicit")]
            utc_range_width = abs(utc_end - utc_start)
            output["playback_sort_key"] = _compose_sort_key(
                event,
                group=1,
                primary_value=utc_midpoint,
                range_width=utc_range_width,
                confidence=output["playback_sort_confidence"],
            )
            return output

        if parsed_time.sort_kind == "exact":
            output["playback_sort_confidence"] = "medium"
        elif parsed_time.sort_kind == "approximate":
            output["playback_sort_confidence"] = "low"
        else:
            output["playback_sort_confidence"] = "low"

    output["playback_sort_confidence"] = _confidence_from_time_kind(parsed_time.sort_kind)
    output["playback_sort_reason"] = "local_time_only"
    output["playback_sort_key"] = _compose_sort_key(
        event,
        group=2,
        primary_value=parsed_time.local_minutes,
        range_width=local_range_width,
        confidence=output["playback_sort_confidence"],
    )
    return output


def enrich_event_with_chronology(event: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(event)
    enriched.update(derive_event_chronology(event))
    return enriched


def canonical_playback_sort_tuple(event: dict[str, Any]) -> tuple[Any, ...]:
    enriched = event if "playback_sort_key" in event else enrich_event_with_chronology(event)
    fallback_group, fallback_value = _event_id_sort_value(enriched)
    sort_date_iso = enriched.get("sort_date_iso")
    playback_sort_key = enriched.get("playback_sort_key") or _compose_sort_key(
        enriched,
        group=3,
        primary_value=None,
        range_width=None,
        confidence="none",
    )
    return (
        1 if not sort_date_iso else 0,
        sort_date_iso or "",
        *playback_sort_key,
        fallback_group,
        fallback_value,
    )
