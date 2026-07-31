"""Canonical adapter for the local majestic.csv source."""

from __future__ import annotations

from typing import Any

from parser.canonical_schema import (
    CanonicalInputRecord,
    build_location_text,
    clean_text,
    normalize_date_fields,
)
from parser.non_terrestrial_coordinates import is_non_terrestrial_placeholder_coordinate
from parser.taxonomy import normalize_event_type_label, normalize_shape_label

from .base import CsvSourceAdapter, compact_raw_fields, coordinates_from_fields, first_text


class MajesticAdapter(CsvSourceAdapter):
    source_name = "majestic"
    source_file = "majestic.csv"

    def row_to_record(
        self,
        row: dict[str, Any],
        *,
        source_row_number: int,
        source_row_hash_value: str,
    ) -> CanonicalInputRecord:
        source_native_id = first_text(row, "source_id", "key_vals/url")
        date_raw = first_text(row, "date")
        date_fields = normalize_date_fields(
            date_raw,
            end_date_raw=first_text(row, "end_date"),
            alternate_date_raw=first_text(row, "alt_date"),
            source_file=self.source_file,
        )
        lat, lon, coordinate_source = coordinates_from_fields(
            row,
            combined_keys=("key_vals/LatLong", "key_vals/LatLongDMS"),
        )
        city = first_text(row, "location/0", "location/1")
        state = first_text(row, "key_vals/State/Prov")
        country = first_text(row, "key_vals/Country")
        if is_non_terrestrial_placeholder_coordinate(country=country, lat=lat, lon=lon):
            lat = None
            lon = None
            coordinate_source = "unresolved"
        location_raw = build_location_text(
            first_text(row, "key_vals/Locale"),
            city,
            state,
            country,
        )
        type_raw = first_text(row, "type/0", "type/1", "type/2")
        description = first_text(row, "desc")
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
            time_raw=first_text(row, "time"),
            location_raw=location_raw,
            city=city,
            state_province=state,
            country=country,
            lat=lat,
            lon=lon,
            coordinate_source=coordinate_source,
            location_precision="coordinate" if lat is not None and lon is not None else "unknown",
            shape_raw=first_text(row, "key_vals/HatchDesc"),
            shape_normalized=normalize_shape_label(first_text(row, "key_vals/HatchDesc")),
            type_raw=type_raw,
            type_normalized=normalize_event_type_label(type_raw),
            duration_raw=first_text(row, "key_vals/Duration"),
            description=description,
            summary=description,
            source_url=first_text(row, "key_vals/url"),
            raw_fields=compact_raw_fields(row),
        )
