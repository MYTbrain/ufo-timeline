"""Canonical adapter for the local ufocat2023.csv source."""

from __future__ import annotations

import calendar
from typing import Any

from parser.canonical_schema import (
    CanonicalInputRecord,
    build_location_text,
    clean_text,
    normalize_date_fields,
)
from parser.taxonomy import normalize_event_type_label, normalize_shape_label

from .base import CsvSourceAdapter, compact_raw_fields, coordinates_from_fields, first_text


class UfocatAdapter(CsvSourceAdapter):
    source_name = "ufocat"
    source_file = "ufocat2023.csv"

    def row_to_record(
        self,
        row: dict[str, Any],
        *,
        source_row_number: int,
        source_row_hash_value: str,
    ) -> CanonicalInputRecord:
        source_native_id = first_text(row, "PRN", "URN", "IRN")
        date_raw = _build_ufocat_date(row)
        date_fields = normalize_date_fields(date_raw, source_file=self.source_file)
        lat, lon, coordinate_source = coordinates_from_fields(
            row,
            lat_keys=("LATITUDE",),
            lon_keys=("LONGITUDE",),
        )
        lat, lon = _normalize_ufocat_coordinate_signs(
            lat=lat,
            lon=lon,
            region=first_text(row, "REGION"),
            state=first_text(row, "STATE"),
        )
        shape_raw = first_text(row, "SHAPE")
        type_raw = first_text(row, "TYPE", "HYNEK", "VALLEE")
        description = first_text(row, "NOTES")
        return CanonicalInputRecord(
            canonical_input_id=self.build_input_id(
                source_row_number=source_row_number,
                source_native_id=source_native_id,
                source_row_hash_value=source_row_hash_value,
            ),
            source_name=self.source_name,
            source_file=self.source_file,
            source_row_number=source_row_number,
            source_native_id=source_native_id,
            source_row_hash=source_row_hash_value,
            date_raw=date_raw,
            date_iso=date_fields.get("date_iso"),
            end_date_iso=date_fields.get("end_date_iso"),
            sort_date_iso=date_fields.get("sort_date_iso"),
            date_precision=str(date_fields.get("date_precision") or "unknown"),
            date_warnings=list(date_fields.get("date_warnings") or []),
            time_raw=first_text(row, "TIME"),
            location_raw=build_location_text(
                first_text(row, "LOCATION"),
                first_text(row, "COUNTY"),
                first_text(row, "STATE"),
                first_text(row, "REGION"),
            ),
            city=first_text(row, "LOCATION"),
            state_province=first_text(row, "STATE"),
            country=first_text(row, "REGION"),
            lat=lat,
            lon=lon,
            coordinate_source=coordinate_source,
            location_precision="coordinate" if lat is not None and lon is not None else "unknown",
            shape_raw=shape_raw,
            shape_normalized=normalize_shape_label(shape_raw),
            type_raw=type_raw,
            type_normalized=normalize_event_type_label(type_raw),
            duration_raw=first_text(row, "DUR"),
            description=description,
            summary=description,
            source_url=first_text(row, "SOURCE", "ISOURCE"),
            raw_fields=compact_raw_fields(row),
        )


def _build_ufocat_date(row: dict[str, Any]) -> str | None:
    year = clean_text(row.get("YEAR"))
    month = clean_text(row.get("MO"))
    day = clean_text(row.get("DAY"))
    if not year:
        return None
    if month and month.isdigit():
        month_value = int(month)
        if not 1 <= month_value <= 12:
            return year
        if day and day.isdigit():
            day_value = int(day)
            year_value = int(year) if year.isdigit() else 1
            max_day = calendar.monthrange(max(year_value, 1), month_value)[1]
            if 1 <= day_value <= max_day:
                return f"{month_value}/{day_value}/{year}"
        return f"{month_value}/{year}"
    return year


def _normalize_ufocat_coordinate_signs(
    *,
    lat: float | None,
    lon: float | None,
    region: str | None,
    state: str | None,
) -> tuple[float | None, float | None]:
    """Normalize common UFOCAT longitude hemisphere omissions.

    UFOCAT often stores western-hemisphere longitudes as positive numbers
    (for example Brooklyn as 73.96 instead of -73.96). A smaller set of
    European rows show the inverse problem. This intentionally uses only
    conservative country/state cues so valid source coordinates are not broadly
    reinterpreted.
    """
    if lat is None or lon is None:
        return lat, lon
    region_key = (clean_text(region) or "").upper()
    state_key = (clean_text(state) or "").upper()
    western_country_or_region_codes = {"US", "USA", "CAN", "MX", "MEX", "CUB", "DOM", "PR", "PRI"}
    us_state_codes = {
        "AK", "AL", "AR", "AZ", "CA", "CO", "CT", "DC", "DE", "FL", "GA", "HI", "IA", "ID", "IL",
        "IN", "KS", "KY", "LA", "MA", "MD", "ME", "MI", "MN", "MO", "MS", "MT", "NC", "ND", "NE",
        "NH", "NJ", "NM", "NV", "NY", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT",
        "VA", "VT", "WA", "WI", "WV", "WY",
    }
    canadian_province_codes = {
        "AB", "ALB", "BC", "LAB", "MAN", "MB", "NB", "NF", "NFL", "NL", "NS", "NT", "NU", "NUV",
        "NWT", "ON", "ONT", "PE", "PEI", "QC", "QUE", "SK", "SAS", "YK", "YT", "YUK",
    }
    australian_state_codes = {"ACT", "NSW", "NT", "NTA", "QLD", "SA", "SAU", "TAS", "TSM", "VIC", "WAU"}
    eastern_country_codes = {
        "AUT", "BEL", "CHN", "CZE", "DEN", "FIN", "GRE", "ITA", "JPN", "NOR", "POL", "ROM", "RUS",
        "SUI", "SWE",
    }
    if region_key in western_country_or_region_codes and lon > 0:
        return lat, -lon
    if state_key in western_country_or_region_codes and lon > 0:
        return lat, -lon
    if state_key in us_state_codes and region_key != "AU" and lon > 0:
        return lat, -lon
    if region_key == "CN" and lon > 0:
        return lat, -lon
    if region_key in {"CA", "A"} and state_key in canadian_province_codes and lon > 0:
        return lat, -lon
    if region_key == "AU" and state_key in australian_state_codes and lon < 0:
        return lat, abs(lon)
    if (region_key in {"EU", "EUR"} or state_key in {"GER", "DE", "DEU"}) and state_key in {"GER", "DE", "DEU"} and lon < 0:
        return lat, abs(lon)
    if state_key in eastern_country_codes and lon < 0:
        return lat, abs(lon)
    if region_key in {"EU", "EUR"} and state_key in {"GBR", "IRL", "POR"} and lon > 0:
        return lat, -lon
    return lat, lon
