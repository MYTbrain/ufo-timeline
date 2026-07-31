"""Canonical adapter for the local phenomenAInon_UPDB.csv source."""

from __future__ import annotations

from typing import Any

from parser.canonical_schema import (
    CanonicalInputRecord,
    build_location_text,
    normalize_date_fields,
    split_date_time,
)

from .base import CsvSourceAdapter, compact_raw_fields, first_text


class PhenomenainonAdapter(CsvSourceAdapter):
    source_name = "phenomenainon_updb"
    source_file = "phenomenAInon_UPDB.csv"

    def row_to_record(
        self,
        row: dict[str, Any],
        *,
        source_row_number: int,
        source_row_hash_value: str,
    ) -> CanonicalInputRecord:
        source_native_id = first_text(row, "id", "source_id")
        date_raw, time_raw = split_date_time(first_text(row, "date"))
        date_fields = normalize_date_fields(date_raw, source_file=self.source_file)
        description = first_text(row, "description")
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
            location_raw=build_location_text(first_text(row, "city"), first_text(row, "country")),
            city=first_text(row, "city"),
            country=first_text(row, "country"),
            description=description,
            summary=description,
            raw_fields=compact_raw_fields(row),
        )
