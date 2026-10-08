"""Interpret only documented UFOCAT date/time flags; never infer missing flags.

CUFOS UFOCAT 2023 codebook, printed pages 18–19:
https://cufos.org/PDFs/UFOCAT%20Codebook%202023.pdf
The numbered TZONE table represents standard offsets relative to code 12/GMT.
Only listed integer and fractional codes are accepted. A blank TZ does not
establish standard time, daylight time, or GMT. Export sentinel safeguards are
applied by the caller before passing a clock here.
"""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

REFERENCE = "https://cufos.org/PDFs/UFOCAT%20Codebook%202023.pdf"
STANDARD_OFFSETS = {
    Decimal(str(code)): int((Decimal(str(code)) - 12) * 60)
    for code in (1, 2, 3, 4, 5, 6, 7, 8, 8.5, 9, 10, 11, 12, 13, 14, 15,
                 15.5, 16, 17, 17.5, 18, 18.5, 19, 20, 21, 21.5, 22, 23, 24)
}
DATE_EXCLUSIONS = {
    "'": ("source_publication_date", "UFOCAT TZ marks a publication date, not an occurrence date."),
    "=": ("source_date_flagged_erroneous", "UFOCAT TZ marks the source date as believed or known erroneous."),
    "-": ("source_date_approximate", "UFOCAT TZ marks the date as approximate by one or two days; exact occurrence ordering is withheld."),
}


def date_exclusion(fields):
    flag = str(fields.get("TZ") or "").strip()
    for glyph, (reason, basis) in DATE_EXCLUSIONS.items():
        if glyph in flag:
            return {"reason": reason, "basis": basis}
    if flag and flag not in {".", "+", "*"}:
        return {"reason": "source_date_time_flag_requires_review",
                "basis": "UFOCAT has an undocumented or combined date/time flag; occurrence ordering awaits source review."}
    return None


def timebase(fields):
    """Return (offsetMinutes, explanation), with no geography-based guess."""
    flag = str(fields.get("TZ") or "").strip()
    if date_exclusion(fields):
        return None, "source_occurrence_date_excluded"
    if not flag:
        return None, "source_timebase_unspecified"
    if flag == "*":
        return 0, "UFOCAT TZ=* explicitly codes both date and time in GMT"
    try:
        code = Decimal(str(fields.get("TZONE") or "").strip())
    except InvalidOperation:
        return None, "source_tzone_not_documented"
    if not code.is_finite() or code not in STANDARD_OFFSETS:
        return None, "source_tzone_not_documented"
    offset = STANDARD_OFFSETS[code] + (60 if flag == "+" else 0)
    mode = "standard" if flag == "." else "daylight (standard plus 60 minutes)"
    return offset, f"UFOCAT TZ={flag} explicitly codes local {mode} time; documented TZONE={code}"


def utc_interval(date_iso, start_ms, end_ms, fields):
    offset, basis = timebase(fields)
    if offset is None:
        return None, basis
    if type(start_ms) is not int or type(end_ms) is not int or not 0 <= start_ms <= end_ms < 86400000:
        return None, "invalid_source_clock_interval"
    try:
        date = datetime.strptime(date_iso, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None, "invalid_source_calendar_date"
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    base = int((date - epoch).total_seconds() * 1000) - offset * 60000
    return (base + start_ms, base + end_ms), basis
