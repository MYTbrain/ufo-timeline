"""Best-effort historical date normalization with uncertainty preserved."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
import calendar
import re

from .utils import collapse_whitespace


MONTH_NAME_TO_NUMBER = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

SEASON_MONTH_BOUNDS = {
    "spring": (3, 5),
    "summer": (6, 8),
    "autumn": (9, 11),
    "fall": (9, 11),
    "winter": (12, 2),
}


@dataclass(frozen=True, slots=True)
class HistoricalDate:
    year: int
    month: int
    day: int

    def isoformat(self) -> str:
        return f"{self.year:04d}-{self.month:02d}-{self.day:02d}"

    def to_python_date(self) -> date:
        safe_year = self.year if self.year >= 1 else 1
        safe_day = min(self.day, days_in_month(self.year, self.month))
        return date(safe_year, self.month, safe_day)


@dataclass(slots=True)
class DateParseResult:
    start: HistoricalDate | None = None
    end: HistoricalDate | None = None
    precision: str = "unknown"
    warnings: list[str] = field(default_factory=list)
    approximate: bool = False


QUESTIONABLE_MARKERS_RE = re.compile(r"[?~]")
DECADE_RE = re.compile(r"^(?P<year>\d{1,4}0)(?:'s|s)$|^(?P<short>\d{1,4})'s$")
NUMERIC_DAY_RE = re.compile(
    r"^(?P<month>\d{1,2})/(?P<day>\d{1,2})/(?P<year>\d{1,4})$"
)
NUMERIC_MONTH_RE = re.compile(r"^(?P<month>\d{1,2})/(?P<year>\d{1,4})$")
YEAR_ONLY_RE = re.compile(r"^(?P<year>\d{1,4})$")
MONTH_NAME_RE = re.compile(
    r"^(?P<month>[A-Za-z]+)\s+(?:(?P<day>\d{1,2}),\s*)?(?P<year>\d{1,4})$"
)
SEASON_RE = re.compile(
    r"^(?:(?P<modifier>early|mid|late)\s+)?(?P<season>spring|summer|autumn|fall|winter)(?:\s+(?P<year>\d{1,4}))?$",
    re.IGNORECASE,
)
APPROX_RE = re.compile(
    r"^(?P<prefix>early|mid|late|around|circa|ca\.|c\.|approx\.?|approximately)\s+(?P<rest>.+)$",
    re.IGNORECASE,
)
RANGE_RE = re.compile(r"^(?P<start>.+?)\s*(?:-|to)\s*(?P<end>.+)$", re.IGNORECASE)


def days_in_month(year: int, month: int) -> int:
    safe_year = year if year >= 1 else 1
    return calendar.monthrange(safe_year, month)[1]


def make_date(year: int, month: int, day: int) -> HistoricalDate:
    return HistoricalDate(year=year, month=month, day=min(day, days_in_month(year, month)))


def midpoint_date(start: HistoricalDate, end: HistoricalDate) -> HistoricalDate:
    start_ordinal = start.to_python_date().toordinal()
    end_ordinal = end.to_python_date().toordinal()
    midpoint = start_ordinal + ((end_ordinal - start_ordinal) // 2)
    py_midpoint = date.fromordinal(midpoint)
    year = 0 if start.year == 0 and end.year == 0 else py_midpoint.year
    return HistoricalDate(year=year, month=py_midpoint.month, day=py_midpoint.day)


def expand_year_token(
    token: str,
    *,
    context_year_heading: str | None = None,
    source_file: str | None = None,
) -> int:
    token = token.strip()
    if not token:
        raise ValueError("Empty year token")

    if len(token) >= 3:
        return int(token)

    year_value = int(token)
    if context_year_heading:
        context_digits = re.sub(r"[^\d]", "", context_year_heading)
        if context_digits:
            context_value = int(context_digits)
            if len(context_digits) == len(token):
                return context_value
            if len(token) == 2 and context_value % 100 == year_value:
                return context_value
            if len(token) == 1 and context_value % 10 == year_value:
                return context_value

    if source_file:
        lower_name = source_file.lower()
        if "1950_1959" in lower_name:
            return 1900 + year_value
        if "1960_1969" in lower_name:
            return 1900 + year_value
        if "1970_1979" in lower_name:
            return 1900 + year_value
        if "1980_present" in lower_name or "1980_present" in lower_name.replace(" ", "_"):
            if year_value >= 80:
                return 1900 + year_value
            return 2000 + year_value

    return year_value


def _season_window(year: int, season: str) -> tuple[HistoricalDate, HistoricalDate]:
    start_month, end_month = SEASON_MONTH_BOUNDS[season]
    if season == "winter":
        return make_date(year, 12, 1), make_date(year + 1, 2, days_in_month(year + 1, 2))
    return make_date(year, start_month, 1), make_date(year, end_month, days_in_month(year, end_month))


def _apply_modifier(
    base: DateParseResult,
    modifier: str,
) -> DateParseResult:
    modifier = modifier.lower()
    if not base.start or not base.end:
        base.precision = "approximate"
        base.approximate = True
        return base

    start_py = base.start.to_python_date()
    end_py = base.end.to_python_date()
    total_days = max((end_py - start_py).days + 1, 1)

    if modifier in {"around", "circa", "ca.", "c.", "approx.", "approx", "approximately"}:
        base.precision = "approximate"
        base.approximate = True
        return base

    if total_days <= 2:
        base.precision = "approximate"
        base.approximate = True
        return base

    one_third = max(total_days // 3, 1)
    if modifier == "early":
        end_py = start_py + timedelta(days=one_third - 1)
    elif modifier == "mid":
        start_py = start_py + timedelta(days=one_third)
        end_py = start_py + timedelta(days=one_third - 1)
    elif modifier == "late":
        start_py = end_py - timedelta(days=one_third - 1)

    base.start = HistoricalDate(start_py.year, start_py.month, start_py.day)
    base.end = HistoricalDate(end_py.year, end_py.month, end_py.day)
    base.precision = "approximate"
    base.approximate = True
    return base


def parse_date_expression(
    raw_value: str | None,
    *,
    context_year_heading: str | None = None,
    source_file: str | None = None,
) -> DateParseResult:
    result = DateParseResult()
    if not raw_value:
        return result

    original = collapse_whitespace(raw_value)
    if not original:
        return result

    approximate = bool(QUESTIONABLE_MARKERS_RE.search(original))
    cleaned = QUESTIONABLE_MARKERS_RE.sub("", original).strip()

    range_match = RANGE_RE.match(cleaned)
    if range_match and "/" in cleaned:
        start_part = parse_date_expression(
            range_match.group("start"),
            context_year_heading=context_year_heading,
            source_file=source_file,
        )
        end_part = parse_date_expression(
            range_match.group("end"),
            context_year_heading=context_year_heading,
            source_file=source_file,
        )
        if start_part.start and (end_part.end or end_part.start):
            result.start = start_part.start
            result.end = end_part.end or end_part.start
            result.precision = "range"
            result.approximate = approximate or start_part.approximate or end_part.approximate
            result.warnings.extend(start_part.warnings + end_part.warnings)
            return result

    approx_match = APPROX_RE.match(cleaned)
    if approx_match:
        base = parse_date_expression(
            approx_match.group("rest"),
            context_year_heading=context_year_heading,
            source_file=source_file,
        )
        base = _apply_modifier(base, approx_match.group("prefix"))
        base.approximate = True
        return base

    season_match = SEASON_RE.match(cleaned)
    if season_match:
        modifier = season_match.group("modifier")
        year_token = season_match.group("year") or context_year_heading
        if year_token:
            year = expand_year_token(
                year_token,
                context_year_heading=context_year_heading,
                source_file=source_file,
            )
            start, end = _season_window(year, season_match.group("season").lower())
            result.start = start
            result.end = end
            result.precision = "approximate"
            result.approximate = True
            if modifier:
                return _apply_modifier(result, modifier)
            return result

    month_name_match = MONTH_NAME_RE.match(cleaned)
    if month_name_match:
        month_name = month_name_match.group("month").lower()
        if month_name in MONTH_NAME_TO_NUMBER:
            month = MONTH_NAME_TO_NUMBER[month_name]
            year = expand_year_token(
                month_name_match.group("year"),
                context_year_heading=context_year_heading,
                source_file=source_file,
            )
            if month_name_match.group("day"):
                day = int(month_name_match.group("day"))
                result.start = result.end = make_date(year, month, day)
                result.precision = "exact_day"
            else:
                result.start = make_date(year, month, 1)
                result.end = make_date(year, month, days_in_month(year, month))
                result.precision = "month"
            result.approximate = approximate
            if approximate and result.precision != "unknown":
                result.precision = "approximate"
            return result

    numeric_day_match = NUMERIC_DAY_RE.match(cleaned)
    if numeric_day_match:
        year = expand_year_token(
            numeric_day_match.group("year"),
            context_year_heading=context_year_heading,
            source_file=source_file,
        )
        result.start = result.end = make_date(
            year,
            int(numeric_day_match.group("month")),
            int(numeric_day_match.group("day")),
        )
        result.precision = "exact_day" if not approximate else "approximate"
        result.approximate = approximate
        return result

    numeric_month_match = NUMERIC_MONTH_RE.match(cleaned)
    if numeric_month_match:
        year = expand_year_token(
            numeric_month_match.group("year"),
            context_year_heading=context_year_heading,
            source_file=source_file,
        )
        month = int(numeric_month_match.group("month"))
        result.start = make_date(year, month, 1)
        result.end = make_date(year, month, days_in_month(year, month))
        result.precision = "month" if not approximate else "approximate"
        result.approximate = approximate
        return result

    decade_match = DECADE_RE.match(cleaned)
    if decade_match:
        year_token = decade_match.group("year") or decade_match.group("short")
        year = expand_year_token(
            year_token,
            context_year_heading=context_year_heading,
            source_file=source_file,
        )
        if decade_match.group("short") and not decade_match.group("year") and year % 10 != 0:
            year = int(str(year)[:-1] + "0") if len(str(year)) > 1 else 0
        if str(year_token).endswith("0") is False and year % 10 != 0:
            year = year - (year % 10)
        result.start = make_date(year, 1, 1)
        result.end = make_date(year + 9, 12, 31)
        result.precision = "decade" if not approximate else "approximate"
        result.approximate = approximate
        return result

    year_match = YEAR_ONLY_RE.match(cleaned)
    if year_match:
        year = expand_year_token(
            year_match.group("year"),
            context_year_heading=context_year_heading,
            source_file=source_file,
        )
        result.start = make_date(year, 1, 1)
        result.end = make_date(year, 12, 31)
        result.precision = "year" if not approximate else "approximate"
        result.approximate = approximate
        return result

    if cleaned.lower() in {"early", "mid", "late"} and context_year_heading:
        year = expand_year_token(
            context_year_heading,
            context_year_heading=context_year_heading,
            source_file=source_file,
        )
        result.start = make_date(year, 1, 1)
        result.end = make_date(year, 12, 31)
        result.precision = "approximate"
        result.approximate = True
        return _apply_modifier(result, cleaned.lower())

    result.warnings.append(f"Could not normalize date '{raw_value}'")
    return result


def normalize_event_dates(
    date_raw: str | None,
    *,
    end_date_raw: str | None = None,
    alternate_date_raw: str | None = None,
    context_year_heading: str | None = None,
    source_file: str | None = None,
) -> dict[str, str | list[str] | None]:
    warnings: list[str] = []
    primary = parse_date_expression(
        date_raw,
        context_year_heading=context_year_heading,
        source_file=source_file,
    )
    warnings.extend(primary.warnings)

    if not primary.start and alternate_date_raw:
        alternate = parse_date_expression(
            alternate_date_raw,
            context_year_heading=context_year_heading,
            source_file=source_file,
        )
        if alternate.start:
            primary = alternate
            warnings.append(
                "Primary date could not be normalized; using alternate date as best-effort fallback."
            )
        else:
            warnings.extend(alternate.warnings)

    if end_date_raw:
        end_value = parse_date_expression(
            end_date_raw,
            context_year_heading=context_year_heading,
            source_file=source_file,
        )
        warnings.extend(end_value.warnings)
        if primary.start and (end_value.end or end_value.start):
            primary.end = end_value.end or end_value.start
            primary.precision = "range"
        elif not primary.start and (end_value.end or end_value.start):
            primary.start = end_value.start
            primary.end = end_value.end or end_value.start
            primary.precision = "range"

    if primary.start and not primary.end:
        primary.end = primary.start

    sort_date = midpoint_date(primary.start, primary.end) if primary.start and primary.end else None
    return {
        "date_iso": primary.start.isoformat() if primary.start else None,
        "end_date_iso": (
            primary.end.isoformat()
            if primary.start and primary.end and primary.end != primary.start
            else None
        ),
        "sort_date_iso": sort_date.isoformat() if sort_date else None,
        "date_precision": primary.precision,
        "date_warnings": warnings,
    }
