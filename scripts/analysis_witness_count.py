"""Strict, provenance-preserving witness-count normalization for Analysis.

Only an explicit witness-count field is classified. Narrative descriptions are
never read. Missing values, qualitative party-size language, zero/negative
source sentinels, and unsupported text are never coerced to one witness.
Credential suffixes are retained as source metadata and are not treated as
credibility evidence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any


STATUS_CODES = (
    "missing",
    "exact_count",
    "approximate_count",
    "bounded_range",
    "lower_bound",
    "qualitative_plural",
    "invalid_count",
    "unresolved_text",
)

WITNESS_COUNT_BINS = (
    "unknown",
    "one",
    "two",
    "three_to_four",
    "five_to_nine",
    "ten_to_nineteen",
    "twenty_to_forty_nine",
    "fifty_to_ninety_nine",
    "hundred_to_999",
    "thousand_plus",
)

ALLOWED_CREDENTIAL_TAGS = (
    "Pilot",
    "Military",
    "Aviation Expert",
    "Law Enforcement Officer",
)

QUALITATIVE_PARTY_TERMS = {
    "couple",
    "a couple",
    "few",
    "a few",
    "several",
    "crowd",
    "a crowd",
    "group",
    "a group",
    "family",
    "a family",
    "party",
    "a party",
    "many",
    "multiple",
}

SOURCE_NUMERIC_RE = re.compile(r"^(?P<count>[+-]?\d+)(?P<credentials>(?: - [A-Za-z ]+)*)$")
APPROXIMATE_RE = re.compile(
    r"^(?:~\s*|about\s+|around\s+|approx(?:\.|imately)?\s+|roughly\s+)(?P<count>\d+)$",
    re.IGNORECASE,
)
RANGE_RE = re.compile(r"^(?P<lower>\d+)\s*(?:-|\u2013|\u2014|to|through)\s*(?P<upper>\d+)$", re.IGNORECASE)
LOWER_BOUND_RE = re.compile(r"^(?:(?:at\s+least|minimum(?:\s+of)?|>=?)\s*(?P<prefix>\d+)|(?P<suffix>\d+)\+)$", re.IGNORECASE)


@dataclass(frozen=True)
class WitnessCountNormalization:
    status: str
    reason: str
    exact_count: int | None = None
    lower_count: int | None = None
    upper_count: int | None = None
    descriptive_bin: str = "unknown"
    precision: str = "unknown"
    credential_profile: str = ""
    extreme_audit: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def witness_count_bin(value: int | None) -> str:
    if value is None or value <= 0:
        return "unknown"
    if value == 1:
        return "one"
    if value == 2:
        return "two"
    if value <= 4:
        return "three_to_four"
    if value <= 9:
        return "five_to_nine"
    if value <= 19:
        return "ten_to_nineteen"
    if value <= 49:
        return "twenty_to_forty_nine"
    if value <= 99:
        return "fifty_to_ninety_nine"
    if value <= 999:
        return "hundred_to_999"
    return "thousand_plus"


def _result(
    status: str,
    reason: str,
    *,
    exact_count: int | None = None,
    lower_count: int | None = None,
    upper_count: int | None = None,
    precision: str = "unknown",
    credential_profile: str = "",
) -> WitnessCountNormalization:
    descriptive_bin = witness_count_bin(exact_count) if status == "exact_count" else "unknown"
    return WitnessCountNormalization(
        status=status,
        reason=reason,
        exact_count=exact_count,
        lower_count=lower_count,
        upper_count=upper_count,
        descriptive_bin=descriptive_bin,
        precision=precision,
        credential_profile=credential_profile,
        extreme_audit=bool(exact_count is not None and exact_count >= 1000),
    )


def _positive_or_invalid(
    value: int,
    *,
    status: str,
    reason: str,
    precision: str,
    credential_profile: str = "",
) -> WitnessCountNormalization:
    if value == 0:
        return _result("invalid_count", "zero_source_sentinel", precision="invalid", credential_profile=credential_profile)
    if value < 0:
        return _result("invalid_count", "negative_source_sentinel", precision="invalid", credential_profile=credential_profile)
    if status == "exact_count":
        return _result(
            status,
            reason,
            exact_count=value,
            lower_count=value,
            upper_count=value,
            precision=precision,
            credential_profile=credential_profile,
        )
    return _result(
        status,
        reason,
        lower_count=value,
        upper_count=value,
        precision=precision,
        credential_profile=credential_profile,
    )


def normalize_witness_count(source_value: str, raw_value: Any) -> WitnessCountNormalization:
    """Normalize an explicit source field without consulting narrative text."""

    source = str(source_value or "unknown").strip().lower() or "unknown"
    raw = "" if raw_value is None else re.sub(r"\s+", " ", str(raw_value)).strip()
    if not raw:
        return _result("missing", "empty")

    lowered = raw.lower().strip(" .")
    if lowered in QUALITATIVE_PARTY_TERMS:
        return _result(
            "qualitative_plural",
            "explicit_qualitative_party_size",
            precision="qualitative",
        )

    # The current immutable NUFORC field uses an integer followed by optional
    # credential labels. Keep those labels separate and never interpret them as
    # evidence of report quality or independent corroboration.
    source_match = SOURCE_NUMERIC_RE.fullmatch(raw)
    if source_match:
        credential_text = source_match.group("credentials")
        credentials = tuple(part.strip() for part in credential_text.split(" - ") if part.strip())
        if any(tag not in ALLOWED_CREDENTIAL_TAGS for tag in credentials):
            return _result("unresolved_text", "unsupported_credential_suffix")
        profile = "+".join(tag.lower().replace(" ", "_") for tag in credentials)
        return _positive_or_invalid(
            int(source_match.group("count")),
            status="exact_count",
            reason="explicit_integer_with_source_credentials" if credentials else "explicit_integer",
            precision="integer",
            credential_profile=profile,
        )

    approximate = APPROXIMATE_RE.fullmatch(raw)
    if approximate:
        return _positive_or_invalid(
            int(approximate.group("count")),
            status="approximate_count",
            reason="explicit_approximate_integer",
            precision="approximate",
        )

    bounded = RANGE_RE.fullmatch(raw)
    if bounded:
        lower = int(bounded.group("lower"))
        upper = int(bounded.group("upper"))
        if lower <= 0 or upper <= 0 or lower > upper:
            return _result("invalid_count", "invalid_or_reversed_range", precision="invalid")
        return _result(
            "bounded_range",
            "explicit_bounded_range",
            lower_count=lower,
            upper_count=upper,
            precision="range",
        )

    lower_bound = LOWER_BOUND_RE.fullmatch(raw)
    if lower_bound:
        value = int(lower_bound.group("prefix") or lower_bound.group("suffix"))
        if value <= 0:
            return _result("invalid_count", "nonpositive_lower_bound", precision="invalid")
        return _result(
            "lower_bound",
            "explicit_lower_bound",
            lower_count=value,
            precision="lower_bound",
        )

    if source != "nuforc":
        return _result("unresolved_text", "unsupported_source_field_grammar")
    return _result("unresolved_text", "unsupported_explicit_field_text")
