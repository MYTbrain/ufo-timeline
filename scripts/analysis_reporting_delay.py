"""Role-preserving normalization for Analysis reporting-delay evidence.

This module deliberately treats occurrence, reported, and posted dates as
different source roles.  A present reported value is authoritative for the
selection decision: if it is invalid or precedes the occurrence date, a posted
value may not silently replace it.  Posted dates are eligible only when the
reported role is absent.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re
from typing import Any


DELAY_BINS = (
    "unknown",
    "same_day",
    "one_day",
    "two_to_three_days",
    "four_to_seven_days",
    "eight_to_thirty_days",
    "thirty_one_to_ninety_days",
    "ninety_one_to_365_days",
    "over_365_days",
)

STATUS_CODES = (
    "reported_valid",
    "posted_fallback_valid",
    "occurrence_precision_incompatible",
    "occurrence_unparseable",
    "reported_unparseable",
    "reported_negative",
    "posted_unparseable",
    "posted_negative",
    "date_role_missing",
)

ROLE_CODES = ("none", "reported", "posted")

_LEADING_ISO_DAY = re.compile(r"^\s*(\d{4})-(\d{2})-(\d{2})(?:\D|$)")


@dataclass(frozen=True)
class ReportingDelayNormalization:
    """A deterministic, source-role-aware reporting-delay normalization."""

    occurrence_date: date | None
    reported_date: date | None
    posted_date: date | None
    selected_role: str
    status: str
    reason: str
    delay_days: int | None
    delay_bin: str

    @property
    def typed(self) -> bool:
        return self.status in {"reported_valid", "posted_fallback_valid"}


def parse_explicit_day(value: Any) -> date | None:
    """Parse only an explicit leading ISO calendar day.

    Source values such as ``YYYY-MM-DD HH:MM Pacific`` remain eligible without
    interpreting the time zone.  Non-ISO, partial, impossible, and ambiguous
    values fail closed.
    """

    match = _LEADING_ISO_DAY.match(str(value or ""))
    if not match:
        return None
    try:
        return date(*(int(part) for part in match.groups()))
    except ValueError:
        return None


def reporting_delay_bin(delay_days: int | None) -> str:
    if delay_days is None or delay_days < 0:
        return "unknown"
    if delay_days == 0:
        return "same_day"
    if delay_days == 1:
        return "one_day"
    if delay_days <= 3:
        return "two_to_three_days"
    if delay_days <= 7:
        return "four_to_seven_days"
    if delay_days <= 30:
        return "eight_to_thirty_days"
    if delay_days <= 90:
        return "thirty_one_to_ninety_days"
    if delay_days <= 365:
        return "ninety_one_to_365_days"
    return "over_365_days"


def normalize_reporting_delay(
    occurrence_raw: Any,
    occurrence_precision: Any,
    reported_raw: Any,
    posted_raw: Any,
) -> ReportingDelayNormalization:
    """Normalize reporting delay while preserving date-role precedence."""

    occurrence_text = str(occurrence_raw or "").strip()
    reported_text = str(reported_raw or "").strip()
    posted_text = str(posted_raw or "").strip()
    occurrence = parse_explicit_day(occurrence_text)
    reported = parse_explicit_day(reported_text) if reported_text else None
    posted = parse_explicit_day(posted_text) if posted_text else None

    if str(occurrence_precision or "").strip().lower() != "exact_day":
        return ReportingDelayNormalization(
            occurrence, reported, posted, "none",
            "occurrence_precision_incompatible", "occurrence_not_exact_day", None, "unknown",
        )
    if occurrence is None:
        return ReportingDelayNormalization(
            None, reported, posted, "none",
            "occurrence_unparseable", "occurrence_explicit_day_unparseable", None, "unknown",
        )

    if reported_text:
        if reported is None:
            return ReportingDelayNormalization(
                occurrence, None, posted, "reported",
                "reported_unparseable", "reported_explicit_day_unparseable", None, "unknown",
            )
        delay = (reported - occurrence).days
        if delay < 0:
            return ReportingDelayNormalization(
                occurrence, reported, posted, "reported",
                "reported_negative", "reported_precedes_occurrence", None, "unknown",
            )
        return ReportingDelayNormalization(
            occurrence, reported, posted, "reported",
            "reported_valid", "reported_nonnegative_exact_day", delay, reporting_delay_bin(delay),
        )

    if posted_text:
        if posted is None:
            return ReportingDelayNormalization(
                occurrence, None, None, "posted",
                "posted_unparseable", "posted_explicit_day_unparseable", None, "unknown",
            )
        delay = (posted - occurrence).days
        if delay < 0:
            return ReportingDelayNormalization(
                occurrence, None, posted, "posted",
                "posted_negative", "posted_precedes_occurrence", None, "unknown",
            )
        return ReportingDelayNormalization(
            occurrence, None, posted, "posted",
            "posted_fallback_valid", "posted_fallback_nonnegative_exact_day", delay, reporting_delay_bin(delay),
        )

    return ReportingDelayNormalization(
        occurrence, None, None, "none",
        "date_role_missing", "reported_and_posted_missing", None, "unknown",
    )
