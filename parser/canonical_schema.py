"""Canonical UFO CSV import records and deterministic ID helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import re
from typing import Any

from .dates import normalize_event_dates
from .taxonomy import normalize_event_type_label, normalize_shape_label
from .utils import collapse_whitespace, coerce_float


RETAINED_CSV_SOURCE_FILES = {
    "majestic.csv",
    "mufonpy.csv",
    "nuforcpy.csv",
    "phenomenAInon_UPDB.csv",
    "ufocat2023.csv",
}

EXACT_SUBSET_DROP_FILES = {
    "mufon.csv": "mufonpy.csv",
    "nuforc.csv": "nuforcpy.csv",
}

UNKNOWN_TOKENS = {"", "unknown", "unk", "n/a", "na", "none", "null", "-"}

SOURCE_CLAIM_FIELD_MAP = {
    "date_raw": "date",
    "time_raw": "time",
    "location_raw": "location",
    "shape_raw": "shape",
    "shape_normalized": "shape_normalized",
    "type_raw": "object_type",
    "type_normalized": "object_type_normalized",
    "duration_raw": "duration",
    "source_url": "source_url",
    "reported_date_raw": "reported_date",
    "posted_date_raw": "posted_date",
}


@dataclass(slots=True)
class SourceProvenance:
    source_name: str
    source_file: str
    source_row_number: int
    source_native_id: str | None
    source_row_hash: str
    canonical_input_id: str


@dataclass(slots=True)
class CanonicalInputRecord:
    canonical_input_id: str
    source_name: str
    source_file: str
    source_row_number: int
    source_native_id: str | None
    source_row_hash: str
    date_raw: str | None = None
    date_iso: str | None = None
    end_date_iso: str | None = None
    sort_date_iso: str | None = None
    date_precision: str = "unknown"
    date_warnings: list[str] = field(default_factory=list)
    time_raw: str | None = None
    location_raw: str | None = None
    city: str | None = None
    state_province: str | None = None
    country: str | None = None
    lat: float | None = None
    lon: float | None = None
    coordinate_source: str = "unresolved"
    location_precision: str = "unknown"
    shape_raw: str | None = None
    shape_normalized: str | None = None
    type_raw: str | None = None
    type_normalized: str | None = None
    duration_raw: str | None = None
    description: str | None = None
    summary: str | None = None
    reported_date_raw: str | None = None
    posted_date_raw: str | None = None
    source_url: str | None = None
    raw_fields: dict[str, Any] = field(default_factory=dict)
    raw_source_row: dict[str, Any] = field(default_factory=dict)
    raw_source_header: list[str] = field(default_factory=list)
    raw_source_row_values: list[str] = field(default_factory=list)
    raw_source_extra_columns: list[str] = field(default_factory=list)
    raw_source_missing_columns: list[str] = field(default_factory=list)
    source_header_column_count: int | None = None
    source_row_column_count: int | None = None
    source_row_anomalies: list[str] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)

    def provenance(self) -> SourceProvenance:
        return SourceProvenance(
            source_name=self.source_name,
            source_file=self.source_file,
            source_row_number=self.source_row_number,
            source_native_id=self.source_native_id,
            source_row_hash=self.source_row_hash,
            canonical_input_id=self.canonical_input_id,
        )


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = collapse_whitespace(str(value).replace("\\n", " ").replace("\\,", ","))
    if text.lower() in UNKNOWN_TOKENS:
        return None
    return text or None


def normalize_key(value: Any) -> str:
    text = clean_text(value) or ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return collapse_whitespace(text)


def normalize_type_label(value: Any) -> str | None:
    key = normalize_key(value)
    return key.replace(" ", "_") if key else None


def stable_hash(payload: Any, *, prefix: str = "", length: int = 20) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha1(serialized.encode("utf-8", "replace")).hexdigest()[:length]
    return f"{prefix}{digest}" if prefix else digest


def source_row_hash(header: list[str], row: dict[str, Any]) -> str:
    values = [str(row.get(key, "")) for key in header]
    extra_columns = row.get("__extra_columns")
    if isinstance(extra_columns, list) and extra_columns:
        values.extend(["__extra_columns__", *[str(value) for value in extra_columns]])
    return stable_hash(values, length=40)


def canonical_input_id(
    *,
    source_name: str,
    source_file: str,
    source_row_number: int,
    source_native_id: str | None,
    row_hash: str,
) -> str:
    return stable_hash(
        {
            "source_name": source_name,
            "source_file": source_file,
            "source_row_number": source_row_number,
            "source_native_id": source_native_id,
            "source_row_hash": row_hash,
        },
        prefix="cin_",
        length=24,
    )


def normalize_date_fields(
    date_raw: str | None,
    *,
    end_date_raw: str | None = None,
    alternate_date_raw: str | None = None,
    source_file: str | None = None,
) -> dict[str, Any]:
    normalized = normalize_event_dates(
        date_raw,
        end_date_raw=end_date_raw,
        alternate_date_raw=alternate_date_raw,
        source_file=source_file,
    )
    if normalized.get("date_iso") is not None:
        return normalized

    iso_like = parse_iso_like_date(date_raw)
    if iso_like is None:
        return normalized

    normalized["date_iso"] = iso_like
    normalized["sort_date_iso"] = iso_like
    normalized["date_precision"] = "day"
    return normalized


def parse_iso_like_date(value: str | None) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    match = re.match(r"^(?P<year>\d{4})[-/](?P<month>\d{1,2})[-/](?P<day>\d{1,2})", text)
    if not match:
        return None
    year = int(match.group("year"))
    month = int(match.group("month"))
    day = int(match.group("day"))
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def split_date_time(value: str | None) -> tuple[str | None, str | None]:
    text = clean_text(value)
    if not text:
        return None, None
    text = text.replace("\\n", " ")
    iso_match = re.match(
        r"^(?P<date>\d{4}-\d{1,2}-\d{1,2})(?:[ T]+(?P<time>.+))?$",
        text,
        flags=re.IGNORECASE,
    )
    if iso_match:
        return clean_text(iso_match.group("date")), clean_text(iso_match.group("time"))
    return text, None


def build_location_text(*parts: Any) -> str | None:
    cleaned = [clean_text(part) for part in parts]
    return ", ".join(part for part in cleaned if part) or None


def coerce_coordinate(value: Any) -> float | None:
    number = coerce_float(value)
    if number is None:
        return None
    return number


def canonical_duplicate_fingerprint(record: CanonicalInputRecord) -> str | None:
    """Return a conservative exact-duplicate key, or None if evidence is too weak."""
    date_key = record.date_iso
    location_key = normalize_key(record.location_raw or build_location_text(record.city, record.state_province, record.country))
    description_key = normalize_key(record.description or record.summary)
    if not date_key or not location_key or not description_key:
        return None
    return stable_hash(
        {
            "date_iso": date_key,
            "time": normalize_key(record.time_raw),
            "location": location_key,
            "description": description_key,
        },
        prefix="dup_",
        length=24,
    )


def source_claims_for_record(record: CanonicalInputRecord) -> list[dict[str, Any]]:
    claims = []
    record_dict = record.to_json_dict()
    for field_name, claim_type in SOURCE_CLAIM_FIELD_MAP.items():
        raw_value = clean_text(record_dict.get(field_name))
        if not raw_value:
            continue
        normalized_value = None
        if field_name.endswith("_normalized"):
            normalized_value = raw_value
        elif field_name == "shape_raw":
            normalized_value = normalize_shape_label(raw_value)
        elif field_name == "type_raw":
            normalized_value = normalize_event_type_label(raw_value)
        claim_payload = {
            "claim_type": claim_type,
            "canonical_input_id": record.canonical_input_id,
            "source_dataset": record.source_name,
            "source_file": record.source_file,
            "source_row_number": record.source_row_number,
            "source_native_id": record.source_native_id,
            "source_record_hash": record.source_row_hash,
            "source_field": field_name,
            "raw_value": raw_value,
            "normalized_value": normalized_value,
            "origin": "adapter_explicit_field",
            "confidence": "source_explicit",
        }
        claim_payload["source_claim_id"] = stable_hash(claim_payload, prefix="scl_", length=24)
        claims.append(claim_payload)
    return claims
