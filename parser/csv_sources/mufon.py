"""Canonical adapter for the local mufonpy.csv source."""

from __future__ import annotations

from typing import Any

from parser.canonical_schema import (
    CanonicalInputRecord,
    normalize_date_fields,
    split_date_time,
)
from parser.taxonomy import display_shape_label, normalize_shape_label

from .base import CsvSourceAdapter, compact_raw_fields, first_text


class MufonPyAdapter(CsvSourceAdapter):
    source_name = "mufon"
    source_file = "mufonpy.csv"

    def row_to_record(
        self,
        row: dict[str, Any],
        *,
        source_row_number: int,
        source_row_hash_value: str,
    ) -> CanonicalInputRecord:
        source_native_id = first_text(row, "No")
        date_raw, time_raw = split_date_time(first_text(row, "Date/Time of Event"))
        date_fields = normalize_date_fields(date_raw, source_file=self.source_file)
        short_description = first_text(row, "Short Description")
        long_description = first_text(row, "Long Description")
        location_raw = first_text(row, "Location of Event")
        inferred_shape = display_shape_label(short_description)
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
            time_raw=time_raw,
            location_raw=location_raw,
            shape_normalized=normalize_shape_label(inferred_shape),
            description=long_description,
            summary=short_description or long_description,
            reported_date_raw=first_text(row, "Date Submitted"),
            raw_fields=compact_raw_fields(row),
        )
