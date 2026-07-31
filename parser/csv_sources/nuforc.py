"""Canonical adapter for the local nuforcpy.csv source."""

from __future__ import annotations

from typing import Any

from parser.canonical_schema import (
    CanonicalInputRecord,
    normalize_date_fields,
    split_date_time,
)
from parser.taxonomy import normalize_event_type_label, normalize_shape_label

from .base import CsvSourceAdapter, compact_raw_fields, first_text


class NuforcPyAdapter(CsvSourceAdapter):
    source_name = "nuforc"
    source_file = "nuforcpy.csv"

    def row_to_record(
        self,
        row: dict[str, Any],
        *,
        source_row_number: int,
        source_row_hash_value: str,
    ) -> CanonicalInputRecord:
        source_native_id = first_text(row, "No")
        date_raw, time_raw = split_date_time(first_text(row, "Occurred"))
        date_fields = normalize_date_fields(date_raw, source_file=self.source_file)
        shape_raw = first_text(row, "Shape")
        description = first_text(row, "Description")
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
            location_raw=first_text(row, "Location", "Location details"),
            shape_raw=shape_raw,
            shape_normalized=normalize_shape_label(shape_raw),
            duration_raw=first_text(row, "Duration"),
            description=description,
            summary=description,
            reported_date_raw=first_text(row, "Reported"),
            posted_date_raw=first_text(row, "Posted"),
            type_raw=first_text(row, "Characteristics", "Explanation"),
            type_normalized=normalize_event_type_label(first_text(row, "Characteristics", "Explanation")),
            raw_fields=compact_raw_fields(row),
        )
