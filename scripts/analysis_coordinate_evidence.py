"""Fail-closed coordinate-evidence classification for Analysis Wave 3.

The classifier never geocodes, repairs, swaps, or upgrades coordinates.  It
only records whether an already-served source coordinate is numerically valid,
compatible with its declared precision, consistent with a pinned broad country
review bound when one is available, and clear of an unresolved lineage review.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any


SOURCE_COORDINATE_VALUES = {
    "raw_latlong",
    "location_coordinates",
    "source_coordinates",
    "source-provided",
    "source_provided",
}

SOURCE_PRECISION_VALUES = {"exact_coords", "coordinate", "source_coordinate"}

STATUS_CODES = (
    "typed_country_consistent",
    "typed_country_unchecked",
    "unresolved_lineage_conflict",
    "country_inconsistent",
    "invalid_zero_sentinel",
    "invalid_out_of_range",
    "invalid_non_numeric",
    "precision_incompatible",
    "origin_incompatible",
)

COUNTRY_CONSISTENCY_CODES = (
    "consistent",
    "inconsistent",
    "unchecked_no_explicit_country",
    "unchecked_no_pinned_bounds",
    "not_applicable_invalid",
)

QUALITY_BINS = (
    "country_consistent",
    "country_unchecked",
    "lineage_conflict",
    "country_inconsistent",
    "invalid_or_incompatible",
)

RISK_FLAG_HIGH_LATITUDE = 1
RISK_FLAG_DATELINE = 2
RISK_FLAG_DUPLICATE_LINEAGE = 4


@dataclass(frozen=True)
class CoordinateEvidenceNormalization:
    status: str
    reason: str
    country_consistency: str
    quality_bin: str
    typed: bool
    latitude: float | None
    longitude: float | None
    risk_flags: int

    @property
    def high_latitude(self) -> bool:
        return bool(self.risk_flags & RISK_FLAG_HIGH_LATITUDE)

    @property
    def dateline(self) -> bool:
        return bool(self.risk_flags & RISK_FLAG_DATELINE)

    @property
    def duplicate_lineage(self) -> bool:
        return bool(self.risk_flags & RISK_FLAG_DUPLICATE_LINEAGE)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def normalize_coordinate_evidence(
    *,
    coordinate_source: Any,
    location_precision: Any,
    latitude: Any,
    longitude: Any,
    explicit_country: str | None,
    country_bounds_available: bool,
    inside_country_bounds: bool | None,
    unresolved_lineage_conflict: bool,
    duplicate_record_count: Any = 1,
) -> CoordinateEvidenceNormalization:
    """Classify an existing source coordinate without altering it."""

    source = str(coordinate_source or "").strip().lower()
    precision = str(location_precision or "").strip().lower()
    lat = _finite_number(latitude)
    lon = _finite_number(longitude)
    try:
        duplicate_count = max(1, int(duplicate_record_count or 1))
    except (TypeError, ValueError):
        duplicate_count = 1

    risk_flags = 0
    if lat is not None and abs(lat) >= 66.5:
        risk_flags |= RISK_FLAG_HIGH_LATITUDE
    if lon is not None and abs(lon) >= 170.0:
        risk_flags |= RISK_FLAG_DATELINE
    if duplicate_count > 1:
        risk_flags |= RISK_FLAG_DUPLICATE_LINEAGE

    def result(
        status: str,
        reason: str,
        country_consistency: str,
        quality_bin: str,
        typed: bool,
    ) -> CoordinateEvidenceNormalization:
        return CoordinateEvidenceNormalization(
            status=status,
            reason=reason,
            country_consistency=country_consistency,
            quality_bin=quality_bin,
            typed=typed,
            latitude=lat,
            longitude=lon,
            risk_flags=risk_flags,
        )

    if source not in SOURCE_COORDINATE_VALUES:
        return result(
            "origin_incompatible",
            "coordinate_origin_is_not_source_provided",
            "not_applicable_invalid",
            "invalid_or_incompatible",
            False,
        )
    if precision not in SOURCE_PRECISION_VALUES:
        return result(
            "precision_incompatible",
            "source_coordinate_precision_is_not_explicit",
            "not_applicable_invalid",
            "invalid_or_incompatible",
            False,
        )
    if lat is None or lon is None:
        return result(
            "invalid_non_numeric",
            "latitude_or_longitude_is_not_finite",
            "not_applicable_invalid",
            "invalid_or_incompatible",
            False,
        )
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return result(
            "invalid_out_of_range",
            "latitude_or_longitude_out_of_range",
            "not_applicable_invalid",
            "invalid_or_incompatible",
            False,
        )
    if lat == 0.0 and lon == 0.0:
        return result(
            "invalid_zero_sentinel",
            "exact_zero_pair_is_not_treated_as_a_terrestrial_site",
            "not_applicable_invalid",
            "invalid_or_incompatible",
            False,
        )
    if unresolved_lineage_conflict:
        country_consistency = (
            "consistent"
            if explicit_country and country_bounds_available and inside_country_bounds is True
            else (
                "inconsistent"
                if explicit_country and country_bounds_available and inside_country_bounds is False
                else (
                    "unchecked_no_pinned_bounds"
                    if explicit_country
                    else "unchecked_no_explicit_country"
                )
            )
        )
        return result(
            "unresolved_lineage_conflict",
            "coordinate_lineage_requires_review",
            country_consistency,
            "lineage_conflict",
            False,
        )
    if explicit_country and country_bounds_available:
        if inside_country_bounds is not True:
            return result(
                "country_inconsistent",
                "source_coordinate_outside_pinned_broad_country_review_bounds",
                "inconsistent",
                "country_inconsistent",
                False,
            )
        return result(
            "typed_country_consistent",
            "source_coordinate_inside_pinned_broad_country_review_bounds",
            "consistent",
            "country_consistent",
            True,
        )
    if explicit_country:
        return result(
            "typed_country_unchecked",
            "explicit_country_has_no_pinned_review_bounds",
            "unchecked_no_pinned_bounds",
            "country_unchecked",
            True,
        )
    return result(
        "typed_country_unchecked",
        "no_unambiguous_explicit_country_token",
        "unchecked_no_explicit_country",
        "country_unchecked",
        True,
    )
