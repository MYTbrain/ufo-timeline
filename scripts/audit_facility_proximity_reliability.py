#!/usr/bin/env python3
"""Audit how coordinate precision affects apparent facility proximity.

The audit is deliberately offline and read-only with respect to its canonical
and runtime-facility inputs.  It decodes the production ``points.bin`` schema,
assembles the same military, research, and claimed-site inputs used by the
browser, and measures point-to-facility exposure at configurable radii.

This is an exposure audit, not an assertion that a sighting occurred at the
packed coordinate or that a nearby facility is related to the sighting.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import mmap
import os
import struct
import sys
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence


SCHEMA_VERSION = "facility_proximity_reliability_audit_v2"
EARTH_RADIUS_METERS = 6_371_008.8
DEFAULT_RADII_KM = (1.0, 2.0, 3.0, 4.0, 5.0, 25.0, 100.0, 250.0, 500.0)
DEFAULT_PILE_MIN_SIZE = 10
DEFAULT_TOP_PILES = 25
DEFAULT_COORDINATE_DECIMALS = 6
GRID_CELL_DEGREES = 1.0
MISSING_LABEL = "(missing)"


RUNTIME_FACILITY_FILES = {
    "military_primary": Path("data/map_overlays/military_bases.geojson"),
    "military_supplement": Path("data/map_overlays/new_zealand_military_facilities.geojson"),
    "military_temporal_overrides": Path("data/map_overlays/military_base_temporal_overrides.json"),
    "military_membership_overrides": Path(
        "data/map_overlays/military_base_overlay_membership_overrides.json"
    ),
    "research_primary": Path("data/map_overlays/research_test_sites.geojson"),
    "research_northern_europe_supplement": Path(
        "data/map_overlays/northern_europe_research_test_sites_pass3_marker_sized_conservative.geojson"
    ),
    "research_new_zealand_supplement": Path(
        "data/map_overlays/new_zealand_research_facilities.geojson"
    ),
    "claimed_ufo_bases": Path("data/claimed_ufo_bases.json"),
}


class AuditInputError(ValueError):
    """Raised when an audit input is absent, malformed, or internally inconsistent."""


@dataclass(frozen=True)
class FacilityPoint:
    lat: float
    lon: float
    facility_source: str
    facility_key: str
    data_origin: str


@dataclass
class FeatureEntry:
    feature: dict[str, Any]
    data_origin: str


@dataclass(frozen=True)
class PackedPoint:
    lat: float
    lon: float
    event_source: str
    coordinate_source: str
    location_precision: str
    date_precision: str


@dataclass
class RuntimeFacilities:
    points: list[FacilityPoint]
    inventory: dict[str, Any]
    input_paths: list[Path]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fingerprint(path: Path, *, relative_to: Path | None = None) -> dict[str, Any]:
    label = path.relative_to(relative_to).as_posix() if relative_to else str(path)
    return {
        "path": label,
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _read_json(path: Path) -> Any:
    if not path.is_file():
        raise AuditInputError(f"Required input does not exist: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AuditInputError(f"Required input is not valid UTF-8 JSON: {path}: {exc}") from exc


def _as_feature_list(payload: Any, path: Path) -> list[dict[str, Any]]:
    if not isinstance(payload, Mapping) or not isinstance(payload.get("features"), list):
        raise AuditInputError(f"Expected a GeoJSON FeatureCollection with features: {path}")
    features: list[dict[str, Any]] = []
    for index, feature in enumerate(payload["features"]):
        if not isinstance(feature, Mapping):
            raise AuditInputError(f"Feature {index} is not an object: {path}")
        features.append(copy.deepcopy(dict(feature)))
    return features


def _source_id(feature: Mapping[str, Any]) -> str:
    properties = feature.get("properties")
    if not isinstance(properties, Mapping):
        return ""
    return str(properties.get("source_id") or "").strip()


def _replacement_source_ids(entries: Iterable[FeatureEntry]) -> set[str]:
    replacements: set[str] = set()
    for entry in entries:
        properties = entry.feature.get("properties")
        if not isinstance(properties, Mapping):
            continue
        raw = properties.get("replaces_source_id")
        values = raw if isinstance(raw, list) else [raw]
        for value in values:
            text = str(value or "").strip()
            if text:
                replacements.add(text)
    return replacements


def _merge_runtime_features(
    primary: list[FeatureEntry], supplements: list[list[FeatureEntry]]
) -> tuple[list[FeatureEntry], int, set[str]]:
    supplemental_entries = [entry for group in supplements for entry in group]
    replacement_ids = _replacement_source_ids(supplemental_entries)
    kept_primary = [
        entry for entry in primary if not (_source_id(entry.feature) in replacement_ids)
    ]
    removed = len(primary) - len(kept_primary)
    return kept_primary + supplemental_entries, removed, replacement_ids


def _override_entries(payload: Any, path: Path) -> list[dict[str, Any]]:
    if not isinstance(payload, Mapping) or not isinstance(payload.get("overrides"), list):
        raise AuditInputError(f"Expected an overrides array: {path}")
    entries: list[dict[str, Any]] = []
    for index, entry in enumerate(payload["overrides"]):
        if not isinstance(entry, Mapping):
            raise AuditInputError(f"Override {index} is not an object: {path}")
        entries.append(dict(entry))
    return entries


def _apply_temporal_overrides(
    features: list[FeatureEntry], overrides: Sequence[Mapping[str, Any]]
) -> tuple[int, int]:
    by_source_id = {
        str(entry.get("source_id") or "").strip(): entry
        for entry in overrides
        if str(entry.get("source_id") or "").strip()
    }
    applied = 0
    matched_source_ids: set[str] = set()
    for entry in features:
        source_id = _source_id(entry.feature)
        override = by_source_id.get(source_id)
        if not override:
            continue
        properties = entry.feature.setdefault("properties", {})
        if not isinstance(properties, dict):
            continue
        for key, value in override.items():
            if key != "source_id":
                properties[key] = copy.deepcopy(value)
        properties["temporal_override_applied"] = True
        applied += 1
        matched_source_ids.add(source_id)
    return applied, len(by_source_id.keys() - matched_source_ids)


def _apply_membership_exclusions(
    features: list[FeatureEntry], overrides: Sequence[Mapping[str, Any]]
) -> tuple[list[FeatureEntry], int, int, int]:
    excluded_ids = {
        str(entry.get("source_id") or "").strip()
        for entry in overrides
        if entry.get("membership_status") == "exclude_from_military_overlay"
        and str(entry.get("source_id") or "").strip()
    }
    present_ids = {_source_id(entry.feature) for entry in features}
    kept = [entry for entry in features if _source_id(entry.feature) not in excluded_ids]
    return kept, len(features) - len(kept), len(excluded_ids), len(excluded_ids - present_ids)


def _normalized_year(properties: Mapping[str, Any], field_names: Sequence[str]) -> int | None:
    for field_name in field_names:
        if field_name not in properties:
            continue
        raw_value = properties.get(field_name)
        if raw_value is None:
            continue
        text = str(raw_value).strip()
        if not text:
            continue
        if text.startswith("-"):
            digits = text[1:]
        else:
            digits = text
        if not digits.isdigit():
            continue
        return int(text)
    return None


def _has_runtime_temporal_bounds(feature: Mapping[str, Any]) -> bool:
    properties = feature.get("properties")
    if not isinstance(properties, Mapping):
        return False
    start_fields = (
        "start_year",
        "operational_start_year",
        "opened_year",
        "commissioned_year",
        "established_year",
    )
    end_fields = (
        "end_year",
        "operational_end_year",
        "closed_year",
        "decommissioned_year",
    )
    for interval_field in (
        "operational_intervals",
        "operation_intervals",
        "active_intervals",
    ):
        raw_intervals = properties.get(interval_field)
        if not isinstance(raw_intervals, list):
            continue
        for interval in raw_intervals:
            if not isinstance(interval, Mapping):
                continue
            if (
                _normalized_year(interval, start_fields) is not None
                or _normalized_year(interval, end_fields) is not None
            ):
                return True
    return (
        _normalized_year(properties, start_fields) is not None
        or _normalized_year(properties, end_fields) is not None
    )


def _normalize_longitude(lon: float) -> float:
    normalized = ((float(lon) + 180.0) % 360.0) - 180.0
    return 0.0 if normalized == -0.0 else normalized


def _coordinate_pair(value: Any) -> tuple[float, float] | None:
    if not isinstance(value, list) or len(value) < 2:
        return None
    try:
        lon = float(value[0])
        lat = float(value[1])
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(lat) and math.isfinite(lon) and -90.0 <= lat <= 90.0):
        return None
    return lat, _normalize_longitude(lon)


def _representative_points(geometry: Any) -> list[tuple[float, float]]:
    """Mirror the browser's representative-point behavior for facility geometry."""

    if not isinstance(geometry, Mapping):
        return []
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geometry_type == "Point":
        point = _coordinate_pair(coordinates)
        return [point] if point else []
    if geometry_type == "MultiPoint":
        if not isinstance(coordinates, list):
            return []
        return [point for point in map(_coordinate_pair, coordinates) if point is not None]

    points: list[tuple[float, float]] = []

    def collect(value: Any) -> None:
        point = _coordinate_pair(value)
        if point is not None and isinstance(value, list) and len(value) >= 2:
            if isinstance(value[0], (int, float)) and isinstance(value[1], (int, float)):
                points.append(point)
                return
        if isinstance(value, list):
            for child in value:
                collect(child)

    collect(coordinates)
    if not points:
        return []
    min_lat = min(point[0] for point in points)
    max_lat = max(point[0] for point in points)
    sin_sum = sum(math.sin(math.radians(point[1])) for point in points)
    cos_sum = sum(math.cos(math.radians(point[1])) for point in points)
    lon = _normalize_longitude(math.degrees(math.atan2(sin_sum / len(points), cos_sum / len(points))))
    return [((min_lat + max_lat) / 2.0, lon)]


def _origin_counts(features: Sequence[FeatureEntry]) -> list[dict[str, Any]]:
    counts = Counter(entry.data_origin for entry in features)
    return _counter_rows(counts, value_key="data_origin")


def _facility_points_from_features(
    features: Sequence[FeatureEntry], facility_source: str
) -> tuple[list[FacilityPoint], int]:
    points: list[FacilityPoint] = []
    features_without_points = 0
    for feature_index, entry in enumerate(features):
        representative_points = _representative_points(entry.feature.get("geometry"))
        if not representative_points:
            features_without_points += 1
            continue
        facility_key = f"{facility_source}:{feature_index}"
        for lat, lon in representative_points:
            points.append(
                FacilityPoint(
                    lat=lat,
                    lon=lon,
                    facility_source=facility_source,
                    facility_key=facility_key,
                    data_origin=entry.data_origin,
                )
            )
    return points, features_without_points


def load_runtime_facilities(facility_root: Path) -> RuntimeFacilities:
    """Load the proximity facility pool using the browser's static data contract."""

    root = Path(facility_root).resolve()
    paths = {name: root / relative for name, relative in RUNTIME_FACILITY_FILES.items()}
    payloads = {name: _read_json(path) for name, path in paths.items()}

    military_primary = [
        FeatureEntry(feature, RUNTIME_FACILITY_FILES["military_primary"].as_posix())
        for feature in _as_feature_list(payloads["military_primary"], paths["military_primary"])
    ]
    military_supplement = [
        FeatureEntry(feature, RUNTIME_FACILITY_FILES["military_supplement"].as_posix())
        for feature in _as_feature_list(payloads["military_supplement"], paths["military_supplement"])
    ]
    military_merged, military_replaced, replacement_ids = _merge_runtime_features(
        military_primary, [military_supplement]
    )
    temporal_overrides = _override_entries(
        payloads["military_temporal_overrides"], paths["military_temporal_overrides"]
    )
    temporal_applied, temporal_unmatched = _apply_temporal_overrides(
        military_merged, temporal_overrides
    )
    membership_overrides = _override_entries(
        payloads["military_membership_overrides"], paths["military_membership_overrides"]
    )
    (
        military_membership_filtered,
        membership_removed,
        membership_requested,
        membership_unmatched,
    ) = _apply_membership_exclusions(military_merged, membership_overrides)
    military_without_temporal_bounds = sum(
        not _has_runtime_temporal_bounds(entry.feature)
        for entry in military_membership_filtered
    )
    military_runtime = [
        entry
        for entry in military_membership_filtered
        if _has_runtime_temporal_bounds(entry.feature)
    ]
    military_points, military_without_points = _facility_points_from_features(
        military_runtime, "military"
    )

    research_groups: list[list[FeatureEntry]] = []
    for name in (
        "research_primary",
        "research_northern_europe_supplement",
        "research_new_zealand_supplement",
    ):
        research_groups.append(
            [
                FeatureEntry(feature, RUNTIME_FACILITY_FILES[name].as_posix())
                for feature in _as_feature_list(payloads[name], paths[name])
            ]
        )
    research_merged, research_replaced, research_replacement_ids = _merge_runtime_features(
        research_groups[0], research_groups[1:]
    )
    research_geometry_excluded = 0
    research_recommended_no_excluded = 0
    research_runtime: list[FeatureEntry] = []
    for entry in research_merged:
        geometry = entry.feature.get("geometry")
        geometry_type = geometry.get("type") if isinstance(geometry, Mapping) else None
        if geometry_type not in {"Point", "MultiPoint"}:
            research_geometry_excluded += 1
            continue
        properties = entry.feature.get("properties")
        recommended = (
            str(properties.get("recommended_include") or "").strip().lower()
            if isinstance(properties, Mapping)
            else ""
        )
        if recommended == "no":
            research_recommended_no_excluded += 1
            continue
        research_runtime.append(entry)
    research_points, research_without_points = _facility_points_from_features(
        research_runtime, "researchSites"
    )

    claimed_payload = payloads["claimed_ufo_bases"]
    if not isinstance(claimed_payload, Mapping) or not isinstance(claimed_payload.get("sites"), list):
        raise AuditInputError(f"Expected a sites array: {paths['claimed_ufo_bases']}")
    claimed_points: list[FacilityPoint] = []
    claimed_wrong_family = 0
    claimed_invalid_coordinates = 0
    for index, raw_site in enumerate(claimed_payload["sites"]):
        if not isinstance(raw_site, Mapping):
            claimed_invalid_coordinates += 1
            continue
        if str(raw_site.get("claim_family") or "").strip() != "claimed_ufo_bases":
            claimed_wrong_family += 1
            continue
        try:
            lat = float(raw_site.get("lat"))
            lon = float(raw_site.get("lng"))
        except (TypeError, ValueError):
            claimed_invalid_coordinates += 1
            continue
        if not (math.isfinite(lat) and math.isfinite(lon) and -90.0 <= lat <= 90.0):
            claimed_invalid_coordinates += 1
            continue
        runtime_id = str(raw_site.get("id") or f"claimed:{index}")
        claimed_points.append(
            FacilityPoint(
                lat=lat,
                lon=_normalize_longitude(lon),
                facility_source="claimedUfoBases",
                facility_key=f"claimedUfoBases:{runtime_id}",
                data_origin=RUNTIME_FACILITY_FILES["claimed_ufo_bases"].as_posix(),
            )
        )

    all_points = military_points + research_points + claimed_points
    inventory = {
        "proximity_sources": ["military", "researchSites", "claimedUfoBases"],
        "total_facility_features": len(military_runtime) + len(research_runtime) + len(claimed_points),
        "total_representative_points": len(all_points),
        "representative_points_by_facility_source": _counter_rows(
            Counter(point.facility_source for point in all_points),
            value_key="facility_source",
        ),
        "representative_points_by_data_origin": _counter_rows(
            Counter(point.data_origin for point in all_points),
            value_key="data_origin",
        ),
        "load_details": {
            "military": {
                "primary_features": len(military_primary),
                "supplemental_features": len(military_supplement),
                "replacement_source_ids": len(replacement_ids),
                "replaced_primary_features": military_replaced,
                "features_after_merge": len(military_merged),
                "temporal_override_entries": len(temporal_overrides),
                "temporal_overrides_applied": temporal_applied,
                "temporal_override_source_ids_unmatched": temporal_unmatched,
                "membership_exclusion_source_ids": membership_requested,
                "membership_features_removed": membership_removed,
                "membership_exclusion_source_ids_unmatched": membership_unmatched,
                "features_without_temporal_bounds_excluded": military_without_temporal_bounds,
                "runtime_features": len(military_runtime),
                "features_without_representative_points": military_without_points,
                "representative_points": len(military_points),
                "runtime_features_by_data_origin": _origin_counts(military_runtime),
            },
            "researchSites": {
                "primary_features": len(research_groups[0]),
                "supplemental_features": sum(len(group) for group in research_groups[1:]),
                "replacement_source_ids": len(research_replacement_ids),
                "replaced_primary_features": research_replaced,
                "features_after_merge": len(research_merged),
                "non_point_features_excluded": research_geometry_excluded,
                "recommended_include_no_excluded": research_recommended_no_excluded,
                "runtime_features": len(research_runtime),
                "features_without_representative_points": research_without_points,
                "representative_points": len(research_points),
                "runtime_features_by_data_origin": _origin_counts(research_runtime),
            },
            "claimedUfoBases": {
                "input_sites": len(claimed_payload["sites"]),
                "wrong_claim_family_excluded": claimed_wrong_family,
                "invalid_coordinate_sites_excluded": claimed_invalid_coordinates,
                "runtime_features": len(claimed_points),
                "representative_points": len(claimed_points),
            },
        },
        "not_in_proximity_index": [
            {
                "overlay": "airports",
                "reason": "The current browser proximity index only includes military, researchSites, and claimedUfoBases.",
            }
        ],
    }
    return RuntimeFacilities(
        points=all_points,
        inventory=inventory,
        input_paths=sorted(paths.values(), key=lambda path: path.as_posix()),
    )


class PackedPointReader:
    """Validated, repeatable reader for a canonical_web points payload."""

    REQUIRED_FIELDS = {
        "lat",
        "lon",
        "source_id",
        "location_precision_id",
        "coordinate_source_id",
        "date_precision_id",
    }

    def __init__(self, canonical_dir: Path):
        self.canonical_dir = Path(canonical_dir).resolve()
        self.meta_path = self.canonical_dir / "points_meta.json"
        self.points_path = self.canonical_dir / "points.bin"
        metadata = _read_json(self.meta_path)
        if not isinstance(metadata, Mapping):
            raise AuditInputError(f"Packed points metadata must be an object: {self.meta_path}")
        self.metadata = dict(metadata)
        try:
            self.row_count = int(metadata["row_count"])
            self.bytes_per_row = int(metadata["bytes_per_row"])
            self.row_struct = struct.Struct(str(metadata["struct_format"]))
        except (KeyError, TypeError, ValueError, struct.error) as exc:
            raise AuditInputError(f"Packed points metadata is missing a valid row schema: {exc}") from exc
        if self.row_count < 0 or self.bytes_per_row <= 0:
            raise AuditInputError(
                "Packed points row_count and bytes_per_row must be non-negative and positive, respectively."
            )
        fields = metadata.get("fields")
        if not isinstance(fields, list) or not all(isinstance(field, Mapping) for field in fields):
            raise AuditInputError("Packed points metadata fields must be an array of objects.")
        self.field_index = {str(field.get("name")): index for index, field in enumerate(fields)}
        missing_fields = self.REQUIRED_FIELDS - self.field_index.keys()
        if missing_fields:
            raise AuditInputError(f"Packed points schema is missing fields: {sorted(missing_fields)}")
        if self.row_struct.size != self.bytes_per_row:
            raise AuditInputError(
                f"Packed points row size mismatch: struct={self.row_struct.size}, metadata={self.bytes_per_row}"
            )
        unpacked_field_count = len(self.row_struct.unpack(bytes(self.row_struct.size)))
        if len(fields) != unpacked_field_count:
            raise AuditInputError(
                f"Packed points field count mismatch: struct={unpacked_field_count}, metadata={len(fields)}"
            )
        expected_offset = 0
        for field in fields:
            try:
                offset = int(field["offset"])
                size = int(field["size"])
            except (KeyError, TypeError, ValueError) as exc:
                raise AuditInputError("Packed points fields require integer offset and size values.") from exc
            if offset != expected_offset or size <= 0:
                raise AuditInputError(
                    "Packed points field layout is not contiguous at "
                    f"{field.get('name')!r}: expected offset {expected_offset}, found {offset}."
                )
            expected_offset += size
        if expected_offset != self.bytes_per_row:
            raise AuditInputError(
                f"Packed points field sizes total {expected_offset}, expected {self.bytes_per_row}."
            )
        if not self.points_path.is_file():
            raise AuditInputError(f"Required input does not exist: {self.points_path}")
        expected_bytes = self.row_count * self.bytes_per_row
        actual_bytes = self.points_path.stat().st_size
        if actual_bytes != expected_bytes:
            raise AuditInputError(
                f"Packed points byte length mismatch: expected {expected_bytes}, found {actual_bytes}"
            )
        lookup_tables = metadata.get("lookup_tables")
        if not isinstance(lookup_tables, Mapping):
            raise AuditInputError("Packed points metadata lookup_tables must be an object.")
        self.lookup_tables = dict(lookup_tables)
        for name in (
            "sources",
            "location_precisions",
            "coordinate_sources",
            "date_precisions",
        ):
            if not isinstance(self.lookup_tables.get(name), list):
                raise AuditInputError(f"Packed points lookup table is missing or invalid: {name}")

    def _lookup(self, table_name: str, raw_index: Any) -> str:
        try:
            index = int(raw_index)
        except (TypeError, ValueError) as exc:
            raise AuditInputError(f"Invalid lookup index for {table_name}: {raw_index!r}") from exc
        table = self.lookup_tables[table_name]
        if index < 0 or index >= len(table):
            raise AuditInputError(
                f"Lookup index {index} is outside {table_name} table length {len(table)}"
            )
        value = table[index]
        return str(value) if value is not None and str(value) else MISSING_LABEL

    def __iter__(self) -> Iterator[PackedPoint]:
        if self.row_count == 0:
            return
        with self.points_path.open("rb") as handle:
            with mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as mapped:
                for row_number, row in enumerate(self.row_struct.iter_unpack(mapped), start=1):
                    lat = float(row[self.field_index["lat"]])
                    lon = float(row[self.field_index["lon"]])
                    if not (
                        math.isfinite(lat)
                        and math.isfinite(lon)
                        and -90.0 <= lat <= 90.0
                    ):
                        raise AuditInputError(
                            f"Packed point row {row_number} has invalid coordinates: lat={lat}, lon={lon}"
                        )
                    yield PackedPoint(
                        lat=lat,
                        lon=_normalize_longitude(lon),
                        event_source=self._lookup(
                            "sources", row[self.field_index["source_id"]]
                        ),
                        coordinate_source=self._lookup(
                            "coordinate_sources",
                            row[self.field_index["coordinate_source_id"]],
                        ),
                        location_precision=self._lookup(
                            "location_precisions",
                            row[self.field_index["location_precision_id"]],
                        ),
                        date_precision=self._lookup(
                            "date_precisions",
                            row[self.field_index["date_precision_id"]],
                        ),
                    )


def evidence_cohort(coordinate_source: str, location_precision: str) -> str:
    if coordinate_source == "raw_latlong":
        return "source_coordinates"
    if coordinate_source == "geocoded" and location_precision == "city":
        return "generalized_city"
    if coordinate_source == "geocoded" and location_precision in {"state", "province", "country"}:
        return "generalized_admin"
    if coordinate_source == "geocoded":
        return "other_geocoded"
    return "indeterminate"


def strict_endpoint_evidence_eligible(
    coordinate_source: str, date_precision: str
) -> bool:
    """Return whether a packed point can support strict dated proximity."""

    return coordinate_source == "raw_latlong" and date_precision == "exact_day"


def _counter_rows(
    counts: Mapping[str, int], *, value_key: str = "value", total: int | None = None
) -> list[dict[str, Any]]:
    denominator = int(total if total is not None else sum(counts.values()))
    rows = []
    for value in sorted(counts, key=str):
        count = int(counts[value])
        row: dict[str, Any] = {value_key: str(value), "count": count}
        if denominator:
            row["share_pct"] = round((count / denominator) * 100.0, 6)
        else:
            row["share_pct"] = 0.0
        rows.append(row)
    return rows


def _matched_counter_rows(
    totals: Mapping[str, int], matched: Mapping[str, int], *, value_key: str
) -> list[dict[str, Any]]:
    matched_total = sum(matched.values())
    rows = []
    for value in sorted(totals, key=str):
        total = int(totals[value])
        matched_count = int(matched.get(value, 0))
        rows.append(
            {
                value_key: str(value),
                "total_events": total,
                "matched_events": matched_count,
                "match_rate_pct": round((matched_count / total) * 100.0, 6) if total else 0.0,
                "share_of_matches_pct": (
                    round((matched_count / matched_total) * 100.0, 6) if matched_total else 0.0
                ),
            }
        )
    return rows


def _coordinate_key(lat: float, lon: float, decimals: int) -> tuple[float, float]:
    return round(lat, decimals), round(_normalize_longitude(lon), decimals)


def _haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lon = _normalize_longitude(lon2 - lon1)
    delta_lambda = math.radians(delta_lon)
    sin_phi = math.sin(delta_phi / 2.0)
    sin_lambda = math.sin(delta_lambda / 2.0)
    a = (sin_phi * sin_phi) + (math.cos(phi1) * math.cos(phi2) * sin_lambda * sin_lambda)
    a = min(1.0, max(0.0, a))
    return EARTH_RADIUS_METERS * 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))


class FacilityGrid:
    def __init__(self, facilities: Sequence[FacilityPoint], cell_degrees: float = GRID_CELL_DEGREES):
        self.cell_degrees = float(cell_degrees)
        self.lon_cells = math.ceil(360.0 / self.cell_degrees)
        self.lat_cells = math.ceil(180.0 / self.cell_degrees)
        self.grid: dict[tuple[int, int], list[FacilityPoint]] = defaultdict(list)
        for facility in facilities:
            self.grid[self._cell(facility.lat, facility.lon)].append(facility)
        for bucket in self.grid.values():
            bucket.sort(key=lambda point: (point.facility_source, point.facility_key, point.lat, point.lon))

    def _cell(self, lat: float, lon: float) -> tuple[int, int]:
        lat_cell = math.floor((min(max(lat, -90.0), 89.999999) + 90.0) / self.cell_degrees)
        lon_cell = math.floor((_normalize_longitude(lon) + 180.0) / self.cell_degrees)
        return lat_cell, lon_cell % self.lon_cells

    def nearby(
        self, lat: float, lon: float, radius_meters: float
    ) -> list[tuple[FacilityPoint, float]]:
        angular_radius = radius_meters / EARTH_RADIUS_METERS
        latitude_span = math.degrees(angular_radius)
        if latitude_span >= (90.0 - abs(lat)):
            longitude_span = 180.0
        else:
            cosine = max(abs(math.cos(math.radians(lat))), 1e-12)
            longitude_span = math.degrees(
                math.asin(min(1.0, math.sin(angular_radius) / cosine))
            )
        min_lat_cell = math.floor(
            (min(max(lat - latitude_span, -90.0), 89.999999) + 90.0) / self.cell_degrees
        )
        max_lat_cell = math.floor(
            (min(max(lat + latitude_span, -90.0), 89.999999) + 90.0) / self.cell_degrees
        )
        lon_center_cell = self._cell(lat, lon)[1]
        lon_cell_span = min(
            self.lon_cells,
            math.ceil(longitude_span / self.cell_degrees) + 1,
        )
        lon_cells = {
            (lon_center_cell + offset) % self.lon_cells
            for offset in range(-lon_cell_span, lon_cell_span + 1)
        }
        candidates: dict[tuple[str, str], tuple[FacilityPoint, float]] = {}
        for lat_cell in range(min_lat_cell, max_lat_cell + 1):
            if lat_cell < 0 or lat_cell >= self.lat_cells:
                continue
            for lon_cell in lon_cells:
                for facility in self.grid.get((lat_cell, lon_cell), []):
                    distance = _haversine_meters(lat, lon, facility.lat, facility.lon)
                    if distance > radius_meters:
                        continue
                    key = (facility.facility_source, facility.facility_key)
                    prior = candidates.get(key)
                    if prior is None or distance < prior[1]:
                        candidates[key] = (facility, distance)
        return sorted(
            candidates.values(),
            key=lambda item: (
                item[1],
                item[0].facility_source,
                item[0].facility_key,
            ),
        )


def parse_radii(value: str | Iterable[float]) -> tuple[float, ...]:
    raw_values: Iterable[Any] = value.split(",") if isinstance(value, str) else value
    radii: set[float] = set()
    for raw in raw_values:
        try:
            radius = float(str(raw).strip())
        except (TypeError, ValueError) as exc:
            raise AuditInputError(f"Invalid radius: {raw!r}") from exc
        if not math.isfinite(radius) or radius <= 0.0 or radius > 2_000.0:
            raise AuditInputError(f"Radius must be > 0 and <= 2000 km: {raw!r}")
        radii.add(radius)
    if not radii:
        raise AuditInputError("At least one radius is required.")
    if len(radii) > 32:
        raise AuditInputError("At most 32 distinct radii may be audited at once.")
    return tuple(sorted(radii))


def _validate_parameters(
    pile_min_size: int, top_piles: int, coordinate_decimals: int
) -> None:
    if pile_min_size < 2:
        raise AuditInputError("pile_min_size must be at least 2.")
    if top_piles < 0 or top_piles > 1_000:
        raise AuditInputError("top_piles must be between 0 and 1000.")
    if coordinate_decimals < 0 or coordinate_decimals > 9:
        raise AuditInputError("coordinate_decimals must be between 0 and 9.")


def audit(
    canonical_dir: Path,
    facility_root: Path,
    *,
    radii_km: Iterable[float] = DEFAULT_RADII_KM,
    pile_min_size: int = DEFAULT_PILE_MIN_SIZE,
    top_piles: int = DEFAULT_TOP_PILES,
    coordinate_decimals: int = DEFAULT_COORDINATE_DECIMALS,
) -> dict[str, Any]:
    """Build a deterministic facility-proximity reliability report."""

    radii = parse_radii(radii_km)
    _validate_parameters(pile_min_size, top_piles, coordinate_decimals)
    canonical_path = Path(canonical_dir).resolve()
    facility_path = Path(facility_root).resolve()
    reader = PackedPointReader(canonical_path)
    runtime = load_runtime_facilities(facility_path)

    event_source_totals: Counter[str] = Counter()
    coordinate_source_totals: Counter[str] = Counter()
    location_precision_totals: Counter[str] = Counter()
    date_precision_totals: Counter[str] = Counter()
    cohort_totals: Counter[str] = Counter()
    strict_endpoint_evidence_totals: Counter[str] = Counter()
    precision_coordinate_cross: Counter[tuple[str, str]] = Counter()
    coordinate_counts: Counter[tuple[float, float]] = Counter()
    min_lat = 90.0
    max_lat = -90.0
    min_lon = 180.0
    max_lon = -180.0

    for point in reader:
        key = _coordinate_key(point.lat, point.lon, coordinate_decimals)
        coordinate_counts[key] += 1
        event_source_totals[point.event_source] += 1
        coordinate_source_totals[point.coordinate_source] += 1
        location_precision_totals[point.location_precision] += 1
        date_precision_totals[point.date_precision] += 1
        cohort_totals[evidence_cohort(point.coordinate_source, point.location_precision)] += 1
        strict_endpoint_evidence_totals[
            "eligible"
            if strict_endpoint_evidence_eligible(
                point.coordinate_source, point.date_precision
            )
            else "not_eligible"
        ] += 1
        precision_coordinate_cross[(point.coordinate_source, point.location_precision)] += 1
        min_lat = min(min_lat, point.lat)
        max_lat = max(max_lat, point.lat)
        min_lon = min(min_lon, point.lon)
        max_lon = max(max_lon, point.lon)

    if sum(coordinate_counts.values()) != reader.row_count:
        raise AuditInputError("Decoded row count did not match points metadata row_count.")

    sorted_piles = sorted(
        coordinate_counts.items(),
        key=lambda item: (-item[1], item[0][0], item[0][1]),
    )
    top_keys = {key for key, _ in sorted_piles[:top_piles]}
    repeated_keys = {key for key, count in coordinate_counts.items() if count >= 2}
    threshold_keys = {key for key, count in coordinate_counts.items() if count >= pile_min_size}

    grid = FacilityGrid(runtime.points)
    max_radius_meters = radii[-1] * 1_000.0
    coordinate_exposure: dict[
        tuple[float, float], tuple[tuple[bool, frozenset[str]], ...]
    ] = {}
    matched_event_totals = [0 for _ in radii]
    event_facility_source_totals = [Counter() for _ in radii]
    pair_totals = [Counter() for _ in radii]
    matched_facility_keys = [defaultdict(set) for _ in radii]

    for (lat, lon), coordinate_event_count in sorted(
        coordinate_counts.items(), key=lambda item: item[0]
    ):
        nearby = grid.nearby(lat, lon, max_radius_meters)
        per_radius: list[tuple[bool, frozenset[str]]] = []
        for radius_index, radius in enumerate(radii):
            within = [item for item in nearby if item[1] <= (radius * 1_000.0)]
            sources = frozenset(item[0].facility_source for item in within)
            matched = bool(within)
            per_radius.append((matched, sources))
            if matched:
                matched_event_totals[radius_index] += coordinate_event_count
            for source in sources:
                event_facility_source_totals[radius_index][source] += coordinate_event_count
            for facility, _distance in within:
                pair_totals[radius_index][facility.facility_source] += coordinate_event_count
                matched_facility_keys[radius_index][facility.facility_source].add(
                    facility.facility_key
                )
        coordinate_exposure[(lat, lon)] = tuple(per_radius)

    matched_event_sources = [Counter() for _ in radii]
    matched_coordinate_sources = [Counter() for _ in radii]
    matched_location_precisions = [Counter() for _ in radii]
    matched_date_precisions = [Counter() for _ in radii]
    matched_cohorts = [Counter() for _ in radii]
    matched_strict_endpoint_evidence = [Counter() for _ in radii]
    top_breakdowns: dict[tuple[float, float], dict[str, Counter[str]]] = {
        key: {
            "event_source": Counter(),
            "coordinate_source": Counter(),
            "location_precision": Counter(),
            "date_precision": Counter(),
            "evidence_cohort": Counter(),
        }
        for key in top_keys
    }
    repeated_cohorts: Counter[str] = Counter()
    threshold_cohorts: Counter[str] = Counter()

    for point in reader:
        key = _coordinate_key(point.lat, point.lon, coordinate_decimals)
        cohort = evidence_cohort(point.coordinate_source, point.location_precision)
        if key in repeated_keys:
            repeated_cohorts[cohort] += 1
        if key in threshold_keys:
            threshold_cohorts[cohort] += 1
        if key in top_breakdowns:
            breakdown = top_breakdowns[key]
            breakdown["event_source"][point.event_source] += 1
            breakdown["coordinate_source"][point.coordinate_source] += 1
            breakdown["location_precision"][point.location_precision] += 1
            breakdown["date_precision"][point.date_precision] += 1
            breakdown["evidence_cohort"][cohort] += 1
        for radius_index, (matched, _sources) in enumerate(coordinate_exposure[key]):
            if not matched:
                continue
            matched_event_sources[radius_index][point.event_source] += 1
            matched_coordinate_sources[radius_index][point.coordinate_source] += 1
            matched_location_precisions[radius_index][point.location_precision] += 1
            matched_date_precisions[radius_index][point.date_precision] += 1
            matched_cohorts[radius_index][cohort] += 1
            matched_strict_endpoint_evidence[radius_index][
                "eligible"
                if strict_endpoint_evidence_eligible(
                    point.coordinate_source, point.date_precision
                )
                else "not_eligible"
            ] += 1

    proximity_rows: list[dict[str, Any]] = []
    reliability_summary: list[dict[str, Any]] = []
    for radius_index, radius in enumerate(radii):
        matched_count = matched_event_totals[radius_index]
        facility_source_rows = []
        all_facility_sources = sorted(
            set(point.facility_source for point in runtime.points)
        )
        for source in all_facility_sources:
            source_matched_events = int(event_facility_source_totals[radius_index][source])
            facility_source_rows.append(
                {
                    "facility_source": source,
                    "matched_events": source_matched_events,
                    "share_of_all_mapped_events_pct": round(
                        (source_matched_events / reader.row_count) * 100.0, 6
                    )
                    if reader.row_count
                    else 0.0,
                    "event_facility_pairs": int(pair_totals[radius_index][source]),
                    "facilities_with_one_or_more_matches": len(
                        matched_facility_keys[radius_index][source]
                    ),
                }
            )
        proximity_rows.append(
            {
                "radius_km": radius,
                "events_with_any_facility_match": matched_count,
                "share_of_all_mapped_events_pct": round(
                    (matched_count / reader.row_count) * 100.0, 6
                )
                if reader.row_count
                else 0.0,
                "by_event_source": _matched_counter_rows(
                    event_source_totals,
                    matched_event_sources[radius_index],
                    value_key="event_source",
                ),
                "by_coordinate_source": _matched_counter_rows(
                    coordinate_source_totals,
                    matched_coordinate_sources[radius_index],
                    value_key="coordinate_source",
                ),
                "by_location_precision": _matched_counter_rows(
                    location_precision_totals,
                    matched_location_precisions[radius_index],
                    value_key="location_precision",
                ),
                "by_date_precision": _matched_counter_rows(
                    date_precision_totals,
                    matched_date_precisions[radius_index],
                    value_key="date_precision",
                ),
                "by_strict_endpoint_evidence": _matched_counter_rows(
                    strict_endpoint_evidence_totals,
                    matched_strict_endpoint_evidence[radius_index],
                    value_key="strict_endpoint_evidence",
                ),
                "by_evidence_cohort": _matched_counter_rows(
                    cohort_totals,
                    matched_cohorts[radius_index],
                    value_key="evidence_cohort",
                ),
                "by_facility_source": facility_source_rows,
            }
        )
        generalized = (
            matched_cohorts[radius_index]["generalized_city"]
            + matched_cohorts[radius_index]["generalized_admin"]
            + matched_cohorts[radius_index]["other_geocoded"]
        )
        source_coordinates = matched_cohorts[radius_index]["source_coordinates"]
        strict_eligible = matched_strict_endpoint_evidence[radius_index]["eligible"]
        source_coordinate_non_exact_date = max(0, source_coordinates - strict_eligible)
        reliability_summary.append(
            {
                "radius_km": radius,
                "all_matched_events": matched_count,
                "source_coordinate_matched_events": int(source_coordinates),
                "strict_endpoint_eligible_matched_events": int(strict_eligible),
                "source_coordinate_non_exact_date_matched_events": int(
                    source_coordinate_non_exact_date
                ),
                "generalized_location_matched_events": int(generalized),
                "generalized_city_matched_events": int(
                    matched_cohorts[radius_index]["generalized_city"]
                ),
                "generalized_share_of_matches_pct": round(
                    (generalized / matched_count) * 100.0, 6
                )
                if matched_count
                else 0.0,
            }
        )

    top_pile_rows = []
    for rank, (key, count) in enumerate(sorted_piles[:top_piles], start=1):
        breakdown = top_breakdowns[key]
        nearby_sources_by_radius = []
        for radius_index, radius in enumerate(radii):
            matched, sources = coordinate_exposure[key][radius_index]
            nearby_sources_by_radius.append(
                {
                    "radius_km": radius,
                    "has_any_facility_match": matched,
                    "facility_sources": sorted(sources),
                }
            )
        top_pile_rows.append(
            {
                "rank": rank,
                "lat": key[0],
                "lon": key[1],
                "event_count": count,
                "event_sources": _counter_rows(
                    breakdown["event_source"], value_key="event_source", total=count
                ),
                "coordinate_sources": _counter_rows(
                    breakdown["coordinate_source"],
                    value_key="coordinate_source",
                    total=count,
                ),
                "location_precisions": _counter_rows(
                    breakdown["location_precision"],
                    value_key="location_precision",
                    total=count,
                ),
                "date_precisions": _counter_rows(
                    breakdown["date_precision"],
                    value_key="date_precision",
                    total=count,
                ),
                "evidence_cohorts": _counter_rows(
                    breakdown["evidence_cohort"],
                    value_key="evidence_cohort",
                    total=count,
                ),
                "nearby_facility_sources_by_radius": nearby_sources_by_radius,
            }
        )

    canonical_fingerprints = [
        _fingerprint(reader.meta_path, relative_to=canonical_path),
        _fingerprint(reader.points_path, relative_to=canonical_path),
    ]
    facility_fingerprints = [
        _fingerprint(path, relative_to=facility_path) for path in runtime.input_paths
    ]
    cross_rows = [
        {
            "coordinate_source": coordinate_source,
            "location_precision": location_precision,
            "count": count,
            "share_pct": round((count / reader.row_count) * 100.0, 6)
            if reader.row_count
            else 0.0,
        }
        for (coordinate_source, location_precision), count in sorted(
            precision_coordinate_cross.items(), key=lambda item: item[0]
        )
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "parameters": {
            "radii_km": list(radii),
            "pile_min_size": pile_min_size,
            "top_piles": top_piles,
            "coordinate_group_rounding_decimals": coordinate_decimals,
            "temporal_mode": "all_time_facility_pool",
            "facility_source_mode": "all_runtime_sources",
            "military_branch_mode": "all_runtime_branches",
        },
        "input_integrity": {
            "canonical_files": canonical_fingerprints,
            "runtime_facility_files": facility_fingerprints,
        },
        "canonical_points": {
            "mapped_event_count": reader.row_count,
            "coordinate_bounds": {
                "min_lat": min_lat if reader.row_count else None,
                "max_lat": max_lat if reader.row_count else None,
                "min_lon": min_lon if reader.row_count else None,
                "max_lon": max_lon if reader.row_count else None,
            },
            "event_source_counts": _counter_rows(
                event_source_totals, value_key="event_source", total=reader.row_count
            ),
            "coordinate_source_counts": _counter_rows(
                coordinate_source_totals,
                value_key="coordinate_source",
                total=reader.row_count,
            ),
            "location_precision_counts": _counter_rows(
                location_precision_totals,
                value_key="location_precision",
                total=reader.row_count,
            ),
            "date_precision_counts": _counter_rows(
                date_precision_totals,
                value_key="date_precision",
                total=reader.row_count,
            ),
            "strict_endpoint_evidence_counts": _counter_rows(
                strict_endpoint_evidence_totals,
                value_key="strict_endpoint_evidence",
                total=reader.row_count,
            ),
            "evidence_cohort_counts": _counter_rows(
                cohort_totals, value_key="evidence_cohort", total=reader.row_count
            ),
            "coordinate_source_by_location_precision": cross_rows,
        },
        "repeated_coordinate_piles": {
            "coordinate_group_rounding_decimals": coordinate_decimals,
            "total_coordinate_groups": len(coordinate_counts),
            "repeated_coordinate_groups": len(repeated_keys),
            "events_in_repeated_coordinate_groups": sum(
                coordinate_counts[key] for key in repeated_keys
            ),
            "events_in_repeated_groups_by_evidence_cohort": _counter_rows(
                repeated_cohorts,
                value_key="evidence_cohort",
                total=sum(repeated_cohorts.values()),
            ),
            "pile_min_size": pile_min_size,
            "coordinate_groups_at_or_above_pile_min_size": len(threshold_keys),
            "events_at_or_above_pile_min_size": sum(
                coordinate_counts[key] for key in threshold_keys
            ),
            "events_at_or_above_pile_min_size_by_evidence_cohort": _counter_rows(
                threshold_cohorts,
                value_key="evidence_cohort",
                total=sum(threshold_cohorts.values()),
            ),
            "top_piles": top_pile_rows,
        },
        "runtime_facilities": runtime.inventory,
        "proximity_exposure": proximity_rows,
        "reliability_summary": reliability_summary,
        "interpretation": {
            "source_coordinates": "Coordinate supplied by the source dataset; this supports a coordinate-based proximity calculation, not a causal claim.",
            "strict_endpoint_evidence": "Strict proximity requires both a source-provided coordinate and an exact-day event date; other date precision is exploratory.",
            "generalized_city": "A geocoded city representative point; proximity describes that representative point, not the unknown sighting location within the city.",
            "generalized_admin": "A geocoded state, province, or country representative point; strict facility proximity is not supported.",
        },
        "limitations": [
            "This audit measures endpoint-to-facility exposure only; it does not establish that a sighting occurred at the packed coordinate or that a facility is related.",
            "Facility operating dates are inventoried through the runtime override inputs but are not paired to each event date in this all-time baseline.",
            "Year-only facility start and end bounds cannot establish activity on a particular day within either boundary year.",
            "Chronological connector lines and pass-near segment intersections are intentionally outside this endpoint audit.",
            "Non-point facility geometry is reduced using the same representative-point rule as the current browser.",
            "Claimed UFO base sites are reported as a separate unverified facility source.",
            "Exposure totals include all runtime facility sources and military branches; current UI source and branch selections can produce a smaller subset.",
        ],
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    points = report["canonical_points"]
    piles = report["repeated_coordinate_piles"]
    facilities = report["runtime_facilities"]
    lines = [
        "# Facility Proximity Reliability Audit",
        "",
        "This report measures how often packed map coordinates fall within each configured radius of the runtime facility pool. It is an exposure audit, not evidence that a sighting occurred at the packed coordinate or was related to a facility.",
        "",
        "## Canonical coordinate evidence",
        "",
        f"Mapped events decoded: **{points['mapped_event_count']:,}**.",
        "",
        "| Evidence cohort | Events | Share |",
        "|---|---:|---:|",
    ]
    for row in points["evidence_cohort_counts"]:
        lines.append(
            f"| {row['evidence_cohort']} | {row['count']:,} | {row['share_pct']:.3f}% |"
        )
    strict_counts = {
        row["strict_endpoint_evidence"]: row
        for row in points["strict_endpoint_evidence_counts"]
    }
    strict_eligible = strict_counts.get("eligible", {"count": 0})["count"]
    lines.extend(
        [
            "",
            f"Strict endpoint evidence (source-provided coordinate plus exact-day date): **{strict_eligible:,}** events.",
        ]
    )
    lines.extend(
        [
            "",
            "## Repeated coordinate piles",
            "",
            f"Coordinates are grouped after rounding to {piles['coordinate_group_rounding_decimals']} decimal places.",
            "",
            f"- Repeated groups: **{piles['repeated_coordinate_groups']:,}**",
            f"- Events in repeated groups: **{piles['events_in_repeated_coordinate_groups']:,}**",
            f"- Groups with at least {piles['pile_min_size']:,} events: **{piles['coordinate_groups_at_or_above_pile_min_size']:,}**",
            f"- Events in those large piles: **{piles['events_at_or_above_pile_min_size']:,}**",
            "",
            "## Runtime facility assembly",
            "",
            f"Runtime facility features: **{facilities['total_facility_features']:,}**; representative points: **{facilities['total_representative_points']:,}**.",
            "",
            "| Facility source | Representative points |",
            "|---|---:|",
        ]
    )
    for row in facilities["representative_points_by_facility_source"]:
        lines.append(f"| {row['facility_source']} | {row['count']:,} |")
    lines.extend(
        [
            "",
            "## Proximity reliability summary",
            "",
            "| Radius | All matched | Source-coordinate matches | Strict-eligible matches | Source coordinates with non-exact dates | Generalized-location matches | Generalized share |",
            "|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in report["reliability_summary"]:
        lines.append(
            "| {radius:g} km | {all_matches:,} | {source_matches:,} | {strict_eligible:,} | {source_non_exact:,} | {generalized:,} | {share:.3f}% |".format(
                radius=row["radius_km"],
                all_matches=row["all_matched_events"],
                source_matches=row["source_coordinate_matched_events"],
                strict_eligible=row["strict_endpoint_eligible_matched_events"],
                source_non_exact=row[
                    "source_coordinate_non_exact_date_matched_events"
                ],
                generalized=row["generalized_location_matched_events"],
                share=row["generalized_share_of_matches_pct"],
            )
        )
    lines.extend(["", "## Interpretation limits", ""])
    lines.extend(f"- {item}" for item in report["limitations"])
    return "\n".join(lines) + "\n"


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _validate_output_path(output: Path, protected_roots: Sequence[Path]) -> Path:
    resolved = output.resolve()
    for protected in protected_roots:
        if _is_relative_to(resolved, protected.resolve()):
            raise AuditInputError(
                f"Refusing to write an audit output inside a protected input tree: {resolved}"
            )
    return resolved


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def write_outputs(
    report: Mapping[str, Any],
    *,
    json_output: Path | None,
    markdown_output: Path | None,
    canonical_dir: Path,
    facility_root: Path,
) -> list[Path]:
    protected = [Path(canonical_dir).resolve(), Path(facility_root).resolve()]
    json_path = (
        _validate_output_path(Path(json_output), protected)
        if json_output is not None
        else None
    )
    markdown_path = (
        _validate_output_path(Path(markdown_output), protected)
        if markdown_output is not None
        else None
    )
    if json_path is not None and markdown_path is not None and json_path == markdown_path:
        raise AuditInputError("JSON and Markdown outputs must use different paths.")
    written: list[Path] = []
    if json_path is not None:
        _atomic_write_text(
            json_path,
            json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        )
        written.append(json_path)
    if markdown_path is not None:
        _atomic_write_text(markdown_path, render_markdown(report))
        written.append(markdown_path)
    return written


def build_parser() -> argparse.ArgumentParser:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Audit coordinate reliability in apparent facility proximity without network access."
    )
    parser.add_argument(
        "--canonical-dir",
        type=Path,
        default=project_root / "data" / "canonical_web",
        help="Directory containing points.bin and points_meta.json.",
    )
    parser.add_argument(
        "--facility-root",
        type=Path,
        default=project_root / "webapp" / "static_public",
        help="Static root containing the runtime facility datasets.",
    )
    parser.add_argument(
        "--radii-km",
        default=",".join(f"{radius:g}" for radius in DEFAULT_RADII_KM),
        help="Comma-separated positive radii in kilometres (maximum 2000).",
    )
    parser.add_argument("--pile-min-size", type=int, default=DEFAULT_PILE_MIN_SIZE)
    parser.add_argument("--top-piles", type=int, default=DEFAULT_TOP_PILES)
    parser.add_argument(
        "--coordinate-decimals", type=int, default=DEFAULT_COORDINATE_DECIMALS
    )
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        radii = parse_radii(args.radii_km)
        report = audit(
            args.canonical_dir,
            args.facility_root,
            radii_km=radii,
            pile_min_size=args.pile_min_size,
            top_piles=args.top_piles,
            coordinate_decimals=args.coordinate_decimals,
        )
        written = write_outputs(
            report,
            json_output=args.json_output,
            markdown_output=args.markdown_output,
            canonical_dir=args.canonical_dir,
            facility_root=args.facility_root,
        )
    except (AuditInputError, OSError) as exc:
        parser.error(str(exc))
    if not written:
        json.dump(report, sys.stdout, indent=2, sort_keys=True, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        for path in written:
            print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
