"""Shared helpers for canonical CSV source adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
import csv
from pathlib import Path
from typing import Any, Iterator

from parser.canonical_schema import (
    CanonicalInputRecord,
    canonical_input_id,
    clean_text,
    coerce_coordinate,
    source_row_hash,
)
from parser.locations import extract_decimal_coordinates


class CsvSourceAdapter(ABC):
    source_name: str
    source_file: str

    def iter_records(
        self,
        path: Path,
        *,
        limit: int | None = None,
    ) -> Iterator[CanonicalInputRecord]:
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, [])
            for row_index, row_values in enumerate(reader, start=2):
                row = row_values_to_dict(header, row_values)
                row_hash = source_row_hash(header, row)
                record = self.row_to_record(
                    row,
                    source_row_number=row_index,
                    source_row_hash_value=row_hash,
                )
                attach_raw_source_row(record, header, row_values)
                yield record
                if limit is not None and row_index - 1 >= limit:
                    return

    def build_input_id(
        self,
        *,
        source_row_number: int,
        source_native_id: str | None,
        source_row_hash_value: str,
    ) -> str:
        return canonical_input_id(
            source_name=self.source_name,
            source_file=self.source_file,
            source_row_number=source_row_number,
            source_native_id=source_native_id,
            row_hash=source_row_hash_value,
        )

    @abstractmethod
    def row_to_record(
        self,
        row: dict[str, Any],
        *,
        source_row_number: int,
        source_row_hash_value: str,
    ) -> CanonicalInputRecord:
        raise NotImplementedError


def first_text(row: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = clean_text(row.get(key))
        if value:
            return value
    return None


def coordinates_from_fields(
    row: dict[str, Any],
    *,
    lat_keys: tuple[str, ...] = (),
    lon_keys: tuple[str, ...] = (),
    combined_keys: tuple[str, ...] = (),
) -> tuple[float | None, float | None, str]:
    for lat_key in lat_keys:
        lat = coerce_coordinate(row.get(lat_key))
        if lat is None:
            continue
        for lon_key in lon_keys:
            lon = coerce_coordinate(row.get(lon_key))
            if lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180:
                return lat, lon, "source_coordinates"

    for key in combined_keys:
        extracted = extract_decimal_coordinates(clean_text(row.get(key)))
        if extracted is not None:
            lat, lon = extracted
            return lat, lon, "source_coordinates"

    return None, None, "unresolved"


def compact_raw_fields(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in row.items()
        if not key.startswith("__") and clean_text(value) is not None
    }


def row_values_to_dict(header: list[str], row_values: list[str]) -> dict[str, Any]:
    row = {
        column_name: row_values[index] if index < len(row_values) else ""
        for index, column_name in enumerate(header)
    }
    extra_columns = row_values[len(header):]
    if extra_columns:
        row["__extra_columns"] = extra_columns
    return row


def attach_raw_source_row(record: CanonicalInputRecord, header: list[str], row_values: list[str]) -> None:
    raw_row = row_values_to_dict(header, row_values)
    extra_columns = list(raw_row.get("__extra_columns") or [])
    missing_columns = header[len(row_values):] if len(row_values) < len(header) else []
    anomalies = []
    if extra_columns:
        anomalies.append("extra_columns")
    if missing_columns:
        anomalies.append("missing_columns")

    record.raw_source_header = list(header)
    record.raw_source_row_values = list(row_values)
    record.raw_source_row = {
        column_name: raw_row.get(column_name, "")
        for column_name in header
    }
    record.raw_source_extra_columns = extra_columns
    record.raw_source_missing_columns = list(missing_columns)
    record.source_header_column_count = len(header)
    record.source_row_column_count = len(row_values)
    record.source_row_anomalies = anomalies
