"""Build deterministic, evidence-gated Analysis v2 spatial projections.

The browser artifacts produced here are projections of the authoritative served
catalog and context releases.  They do not consume chronology/trace segments and
they do not turn generalized context markers into exact sites.  Each potentially
inferential row carries an explicit eligibility decision and exclusion reasons.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
from copy import deepcopy
from datetime import date
from io import BytesIO
import gzip
import hashlib
import json
import math
import mmap
from pathlib import Path
import re
import struct
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DATA_ROOT = REPO_ROOT / "webapp" / "static_public" / "data"
DEFAULT_OUTPUT_ROOT = STATIC_DATA_ROOT / "analysis_v2"
DEFAULT_CANONICAL_ROOT = REPO_ROOT / "data" / "canonical_web"
DEFAULT_CANONICAL_SOURCE = (
    REPO_ROOT
    / "data"
    / "canonical_full_maximal_v3_rehydrated_jurisdiction_repair"
    / "deduped_events.jsonl"
)
DEFAULT_BROWSER_BASE_PATH = "data/analysis_v2"
DEFAULT_RELEASE_ID = "analysis-evidence-lab-v2-20260803"
SCHEMA_ID = "ufo-timeline-analysis-evidence-artifacts-v2.0.0"
RELATIONSHIP_SNAPSHOT_FILENAME = "relationship_source_snapshot.json"
RELATIONSHIP_SNAPSHOT_META_FILENAME = "relationship_source_snapshot.meta.json"
SAFE_RELEASE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
CANONICAL_EVENT_ID_RE = re.compile(br'"canonical_event_id":"(evt_[0-9a-f]+)"')
CANONICAL_INPUT_ID_RE = re.compile(br"cin_[0-9a-f]+")
SERVED_EVENT_ID_RE = re.compile(br'"coordinate_rehydration_served_event_id":(\d+)')

EARTH_RADIUS_KM = 6_371.0088
NEIGHBOR_MAX_DISTANCE_KM = 100.0
NEIGHBOR_MAX_DAY_LAG = 30
COORDINATE_PILE_DECIMALS = 6
COORDINATE_PILE_MIN_SIZE = 10
RECOGNIZED_CRAFT_CLASSES = {
    "chevron_boomerang",
    "cigar_cylinder",
    "cone",
    "diamond",
    "disc_saucer",
    "dumbbell_barbell",
    "oval_egg",
    "rectangle_box",
    "sphere_orb",
    "teardrop",
    "triangle",
}

FACILITY_FILES = {
    "militaryPrimary": "map_overlays/military_bases.geojson",
    "militarySupplement": "map_overlays/new_zealand_military_facilities.geojson",
    "militaryTemporal": "map_overlays/military_base_temporal_overrides.json",
    "militaryMembership": "map_overlays/military_base_overlay_membership_overrides.json",
    "researchPrimary": "map_overlays/research_test_sites.geojson",
    "researchNorthernEurope": (
        "map_overlays/northern_europe_research_test_sites_pass3_marker_sized_conservative.geojson"
    ),
    "researchNewZealand": "map_overlays/new_zealand_research_facilities.geojson",
    "claimedSites": "claimed_ufo_bases.json",
}

FACILITY_ROW_SCHEMA = [
    "id",
    "classCode",
    "name",
    "lat",
    "lon",
    "coordinatePrecisionCode",
    "coordinateConfidenceCode",
    "uncertaintyKm",
    "temporalConfidenceCode",
    "activeIntervals",
    "statusCode",
    "countryCode",
    "provenanceCode",
    "inferentialEligible",
    "exclusionReasonCodes",
]
CROP_CONTEXT_ROW_SCHEMA = [
    "id",
    "lat",
    "lon",
    "coordinateEvidenceCode",
    "coordinateUncertaintyKm",
    "startOrdinal",
    "endOrdinal",
    "datePrecisionCode",
    "dateRoleCode",
    "formationDateKnown",
    "reviewStateCode",
    "lineageHash",
    "sourceFamilyCount",
    "kilometerEligible",
    "exclusionReasonCodes",
]
ANIMAL_CONTEXT_ROW_SCHEMA = [
    "id",
    "lat",
    "lon",
    "coordinateEvidenceCode",
    "coordinateUncertaintyKm",
    "startOrdinal",
    "endOrdinal",
    "datePrecisionCode",
    "reviewStateCode",
    "sourceIncidentId",
    "sourceIncidentSha256",
    "lineageHash",
    "kilometerEligible",
    "exclusionReasonCodes",
]
NEIGHBOR_ROW_SCHEMA = [
    "leftEventId",
    "rightEventId",
    "distanceDecameters",
    "dayLag",
    "crossSource",
]
RELATIONSHIP_SOURCE_ROW_SCHEMA = [
    "relationshipId",
    "subjectSourceIncidentId",
    "objectDomain",
    "objectSourceId",
    "assertionMode",
    "relationshipType",
    "reviewState",
    "sourceInputIds",
]
RELATIONSHIP_ROW_SCHEMA = [
    "relationshipId",
    "subjectAnalysisId",
    "objectDomainCode",
    "objectAnalysisId",
    "assertionModeCode",
    "relationshipTypeCode",
    "reviewStateCode",
    "currentUfoEventId",
    "reconciliationStatusCode",
    "associationEligible",
    "sourceInputCount",
    "exclusionReasonCodes",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=STATIC_DATA_ROOT)
    parser.add_argument("--canonical-root", type=Path, default=DEFAULT_CANONICAL_ROOT)
    parser.add_argument("--canonical-source", type=Path, default=DEFAULT_CANONICAL_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--release-id", default=DEFAULT_RELEASE_ID)
    parser.add_argument("--browser-base-path", default=DEFAULT_BROWSER_BASE_PATH)
    parser.add_argument("--relationship-source", type=Path)
    parser.add_argument("--relationship-snapshot", type=Path)
    return parser.parse_args()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_json_document(value: Any) -> bytes:
    return canonical_json_bytes(value) + b"\n"


def deterministic_gzip(raw: bytes) -> bytes:
    output = BytesIO()
    with gzip.GzipFile(filename="", mode="wb", compresslevel=9, fileobj=output, mtime=0) as stream:
        stream.write(raw)
    return output.getvalue()


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_gzip_json(path: Path) -> Any:
    return json.loads(gzip.decompress(path.read_bytes()))


def text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def finite_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def normalize_longitude(value: float) -> float:
    result = ((float(value) + 180.0) % 360.0) - 180.0
    return 0.0 if result == -0.0 else result


def coordinate_pair(geometry: Any) -> tuple[float, float] | None:
    if not isinstance(geometry, Mapping) or geometry.get("type") != "Point":
        return None
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list) or len(coordinates) < 2:
        return None
    lon = finite_number(coordinates[0])
    lat = finite_number(coordinates[1])
    if lat is None or lon is None or not -90.0 <= lat <= 90.0:
        return None
    return lat, normalize_longitude(lon)


def year_value(value: Any) -> int | None:
    number = finite_number(value)
    if number is None or not float(number).is_integer():
        return None
    result = int(number)
    return result if -9999 <= result <= 9999 else None


def ordinal_bounds(start_value: Any, end_value: Any = None) -> tuple[int | None, int | None]:
    def bound(value: Any, *, upper: bool) -> int | None:
        raw = text(value)
        if not raw:
            return None
        parts = raw.split("-")
        try:
            year = int(parts[0])
            month = int(parts[1]) if len(parts) >= 2 else (12 if upper else 1)
            if len(parts) >= 3:
                day = int(parts[2])
            elif upper:
                if month == 12:
                    day = (date(year + 1, 1, 1) - date.resolution).day
                else:
                    day = (date(year, month + 1, 1) - date.resolution).day
            else:
                day = 1
            return date(year, month, day).toordinal()
        except (TypeError, ValueError, OverflowError):
            return None

    lower = bound(start_value, upper=False)
    upper = bound(end_value if text(end_value) else start_value, upper=True)
    if lower is None and upper is None:
        return None, None
    if lower is None:
        lower = upper
    if upper is None:
        upper = lower
    assert lower is not None and upper is not None
    return min(lower, upper), max(lower, upper)


def codebook(values: Iterable[str]) -> tuple[list[str], dict[str, int]]:
    labels = sorted({text(value) or "unknown" for value in values}, key=lambda value: (value.casefold(), value))
    return labels, {label: index for index, label in enumerate(labels)}


def encode_rows(rows: list[dict[str, Any]], schema: list[str], code_maps: Mapping[str, dict[str, int]]) -> list[list[Any]]:
    encoded: list[list[Any]] = []
    for row in rows:
        values: list[Any] = []
        for field in schema:
            value = row.get(field)
            code_map = code_maps.get(field)
            if code_map is not None:
                value = code_map[text(value) or "unknown"]
            values.append(value)
        encoded.append(values)
    return encoded


def write_projection(
    output_root: Path,
    browser_base_path: str,
    filename: str,
    rows: list[list[Any]],
    row_schema: list[str],
) -> dict[str, Any]:
    raw = canonical_json_document(rows)
    compressed = deterministic_gzip(raw)
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / filename).write_bytes(raw)
    (output_root / f"{filename}.gz").write_bytes(compressed)
    prefix = browser_base_path.strip("/")
    return {
        "bytes": len(raw),
        "file": f"{prefix}/{filename}",
        "gzipBytes": len(compressed),
        "gzipFile": f"{prefix}/{filename}.gz",
        "gzipSha256": sha256_bytes(compressed),
        "rowCount": len(rows),
        "rowSchema": row_schema,
        "sha256": sha256_bytes(raw),
    }


def write_document(
    output_root: Path,
    browser_base_path: str,
    filename: str,
    value: Any,
) -> dict[str, Any]:
    raw = canonical_json_document(value)
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / filename).write_bytes(raw)
    return {
        "bytes": len(raw),
        "file": f"{browser_base_path.strip('/')}/{filename}",
        "sha256": sha256_bytes(raw),
    }


def input_declaration(path: Path, *, label: str) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "label": label,
        "sha256": sha256_path(path),
    }


def geojson_features(path: Path) -> list[dict[str, Any]]:
    payload = load_json(path)
    if not isinstance(payload, Mapping) or not isinstance(payload.get("features"), list):
        raise ValueError(f"Expected FeatureCollection: {path}")
    return [deepcopy(dict(feature)) for feature in payload["features"] if isinstance(feature, Mapping)]


def property_id(properties: Mapping[str, Any], *names: str) -> str:
    for name in names:
        value = text(properties.get(name))
        if value:
            return value
    return ""


def active_intervals(properties: Mapping[str, Any]) -> list[list[int | None]]:
    intervals: list[list[int | None]] = []
    for name in ("operational_intervals", "operation_intervals", "active_intervals"):
        values = properties.get(name)
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, Mapping):
                continue
            start = year_value(
                value.get("start_year", value.get("operational_start_year", value.get("opened_year")))
            )
            end = year_value(
                value.get("end_year", value.get("operational_end_year", value.get("closed_year")))
            )
            if start is not None or end is not None:
                intervals.append([start, end])
    if not intervals:
        start = None
        end = None
        for name in ("start_year", "operational_start_year", "opened_year", "commissioned_year", "established_year"):
            start = year_value(properties.get(name))
            if start is not None:
                break
        for name in ("end_year", "operational_end_year", "closed_year", "decommissioned_year"):
            end = year_value(properties.get(name))
            if end is not None:
                break
        if start is not None or end is not None:
            intervals.append([start, end])
    return sorted({(item[0], item[1]) for item in intervals}, key=lambda item: (item[0] is None, item[0] or -9999, item[1] is None, item[1] or 9999))


def stable_facility_id(facility_class: str, native_id: str, lat: float, lon: float) -> str:
    identity = canonical_json_bytes([facility_class, native_id, round(lat, 7), round(lon, 7)])
    return f"facility:{hashlib.sha256(identity).hexdigest()[:20]}"


def normalize_confidence(value: Any) -> str:
    label = text(value).casefold().replace(" ", "_")
    return label if label in {"high", "medium", "low"} else "unrated"


def build_facility_projection(source_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    paths = {name: source_root / relative for name, relative in FACILITY_FILES.items()}
    military_primary = geojson_features(paths["militaryPrimary"])
    military_supplement = geojson_features(paths["militarySupplement"])
    replacement_ids = {
        text((feature.get("properties") or {}).get("replaces_source_id"))
        for feature in military_supplement
        if text((feature.get("properties") or {}).get("replaces_source_id"))
    }
    military = [
        feature
        for feature in military_primary
        if text((feature.get("properties") or {}).get("source_id")) not in replacement_ids
    ] + military_supplement
    temporal_payload = load_json(paths["militaryTemporal"])
    temporal_overrides = {
        text(item.get("source_id")): item
        for item in temporal_payload.get("overrides", [])
        if isinstance(item, Mapping) and text(item.get("source_id"))
    }
    membership_payload = load_json(paths["militaryMembership"])
    membership_excluded = {
        text(item.get("source_id"))
        for item in membership_payload.get("overrides", [])
        if isinstance(item, Mapping)
        and item.get("membership_status") == "exclude_from_military_overlay"
        and text(item.get("source_id"))
    }

    feature_entries: list[tuple[str, str, dict[str, Any], str]] = []
    for feature in military:
        properties = deepcopy(feature.get("properties") or {})
        native_id = property_id(properties, "source_id", "name")
        if native_id in temporal_overrides:
            properties.update(deepcopy(temporal_overrides[native_id]))
        feature["properties"] = properties
        origin = (
            FACILITY_FILES["militarySupplement"]
            if feature in military_supplement
            else FACILITY_FILES["militaryPrimary"]
        )
        feature_entries.append(("military", native_id, feature, origin))
    for source_name in ("researchPrimary", "researchNorthernEurope", "researchNewZealand"):
        for feature in geojson_features(paths[source_name]):
            properties = feature.get("properties") or {}
            native_id = property_id(
                properties,
                "site_id",
                "source_id",
                "facility_name",
                "display_name",
                "entity_name",
            )
            feature_entries.append(("research_test", native_id, feature, FACILITY_FILES[source_name]))

    rows: list[dict[str, Any]] = []
    for facility_class, native_id, feature, origin in feature_entries:
        properties = feature.get("properties") or {}
        pair = coordinate_pair(feature.get("geometry"))
        if pair is None:
            continue
        lat, lon = pair
        coordinate_precision = property_id(properties, "coordinate_precision", "geo_precision_target")
        if not coordinate_precision:
            coordinate_precision = "facility_marker" if origin.endswith("new_zealand_military_facilities.geojson") else "gazetteer_marker"
        coordinate_confidence = normalize_confidence(
            properties.get("coordinate_confidence", properties.get("geocode_confidence"))
        )
        evidence_status = text(properties.get("evidence_status")).casefold()
        evidence_confidence = normalize_confidence(properties.get("confidence"))
        intervals = active_intervals(properties)
        temporal_confidence = normalize_confidence(properties.get("temporal_confidence"))
        if temporal_confidence == "unrated" and intervals:
            if evidence_status == "verified" or evidence_confidence == "high":
                temporal_confidence = "high"
            elif evidence_confidence == "medium":
                temporal_confidence = "medium"
        reasons: list[str] = []
        if native_id in membership_excluded:
            reasons.append("excluded_by_reviewed_membership_policy")
        if text(properties.get("recommended_include")).casefold() == "no":
            reasons.append("recommended_include_no")
        if coordinate_confidence not in {"high", "medium"}:
            reasons.append("coordinate_confidence_below_medium")
        if temporal_confidence not in {"high", "medium"}:
            reasons.append("temporal_confidence_below_medium")
        if not intervals:
            reasons.append("no_operational_interval")
        source_urls = properties.get("source_urls")
        if not source_urls:
            reasons.append("no_pinned_source_url")
        rows.append({
            "id": stable_facility_id(facility_class, native_id, lat, lon),
            "classCode": facility_class,
            "name": property_id(properties, "display_name", "facility_name", "entity_name", "name") or native_id,
            "lat": round(lat, 7),
            "lon": round(lon, 7),
            "coordinatePrecisionCode": coordinate_precision,
            "coordinateConfidenceCode": coordinate_confidence,
            "uncertaintyKm": finite_number(properties.get("marker_radius_km")),
            "temporalConfidenceCode": temporal_confidence,
            "activeIntervals": intervals,
            "statusCode": property_id(properties, "historical_status", "status") or "unknown",
            "countryCode": property_id(properties, "country_code", "country") or "unknown",
            "provenanceCode": origin,
            "inferentialEligible": not reasons,
            "exclusionReasonCodes": sorted(set(reasons)),
        })

    claimed_payload = load_json(paths["claimedSites"])
    for index, site in enumerate(claimed_payload.get("sites", [])):
        if not isinstance(site, Mapping) or text(site.get("claim_family")) != "claimed_ufo_bases":
            continue
        lat = finite_number(site.get("lat"))
        lon = finite_number(site.get("lng"))
        if lat is None or lon is None or not -90 <= lat <= 90:
            continue
        native_id = text(site.get("id")) or f"claimed:{index}"
        rows.append({
            "id": stable_facility_id("claimed_ufo_base", native_id, lat, lon),
            "classCode": "claimed_ufo_base",
            "name": text(site.get("name")) or native_id,
            "lat": round(lat, 7),
            "lon": round(normalize_longitude(lon), 7),
            "coordinatePrecisionCode": "claim_marker",
            "coordinateConfidenceCode": "unrated",
            "uncertaintyKm": None,
            "temporalConfidenceCode": "unrated",
            "activeIntervals": [],
            "statusCode": "claim_unreviewed",
            "countryCode": text(site.get("country_code")) or "unknown",
            "provenanceCode": FACILITY_FILES["claimedSites"],
            "inferentialEligible": False,
            "exclusionReasonCodes": ["claimed_site_descriptive_only"],
        })

    rows.sort(key=lambda row: row["id"])
    source = {
        "files": {
            name: input_declaration(path, label=relative)
            for (name, relative), path in zip(FACILITY_FILES.items(), paths.values())
        },
        "policy": {
            "distanceRole": "report_marker_to_facility_marker",
            "geometryRole": "representative_point_not_site_boundary",
            "claimedSitesInferential": False,
            "requiresCoordinateConfidence": ["medium", "high"],
            "requiresTemporalConfidence": ["medium", "high"],
            "requiresOperationalInterval": True,
            "causalInfluenceAsserted": False,
        },
        "counts": {
            "rows": len(rows),
            "inferentialEligible": sum(row["inferentialEligible"] for row in rows),
            "claimedDescriptive": sum(row["classCode"] == "claimed_ufo_base" for row in rows),
            "membershipExcluded": sum(
                "excluded_by_reviewed_membership_policy" in row["exclusionReasonCodes"] for row in rows
            ),
            "militaryReplacementsApplied": len(replacement_ids),
        },
        "readiness": {
            "eligibleRecordCount": sum(row["inferentialEligible"] for row in rows),
            "minimumEligibleRecords": 25,
            "status": (
                "qualified_candidate_pool"
                if sum(row["inferentialEligible"] for row in rows) >= 25
                else "not_estimable"
            ),
            "warnings": [
                "distances_are_marker_to_marker_not_site_boundary_distances",
                "association_does_not_establish_facility_influence",
            ],
        },
    }
    return rows, source


def detail_records(layer_root: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any], bytes]:
    manifest_path = layer_root / "manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    records: dict[str, dict[str, Any]] = {}
    declarations = (manifest.get("details") or {}).get("files") or []
    for declaration in declarations:
        path = layer_root / str(declaration["path"])
        compressed = path.read_bytes()
        if sha256_bytes(compressed) != declaration.get("sha256"):
            raise ValueError(f"Context detail hash mismatch: {path}")
        payload = json.loads(gzip.decompress(compressed))
        if not isinstance(payload, Mapping):
            raise ValueError(f"Context detail chunk is not an object: {path}")
        for record_id, record in payload.items():
            if record_id in records or not isinstance(record, Mapping):
                raise ValueError(f"Invalid or duplicate context record: {record_id}")
            records[str(record_id)] = dict(record)
    return records, manifest, manifest_bytes


def lineage_hash(values: Any) -> str:
    return sha256_bytes(canonical_json_bytes(values))


def build_crop_context_projection(source_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records, manifest, manifest_bytes = detail_records(source_root / "crop_circles")
    rows: list[dict[str, Any]] = []
    for record_id in sorted(records):
        record = records[record_id]
        lat = finite_number(record.get("lat"))
        lon = finite_number(record.get("lon"))
        if lat is None or lon is None:
            coordinate_evidence = "unmapped"
        elif record.get("exactCoordinate") is True:
            coordinate_evidence = "exact_source_coordinate"
        elif text(record.get("markerConfidence")) == "provisional":
            coordinate_evidence = "candidate_field_marker"
        else:
            coordinate_evidence = "locality_centroid"
        start, end = ordinal_bounds(record.get("dateIso"), record.get("endDateIso"))
        date_precision = text(record.get("datePrecision")) or "unknown"
        date_role = text(record.get("dateRole")) or "catalog_unspecified"
        formation_known = record.get("formationDateKnown") is True
        review_state = text(record.get("classification")) or "unreviewed"
        reasons: list[str] = []
        if coordinate_evidence != "exact_source_coordinate":
            reasons.append("coordinate_not_exact_source_site")
        if not formation_known:
            reasons.append("formation_date_not_established")
        if date_precision not in {"day", "exact_day"}:
            reasons.append("date_not_exact_day")
        if date_role == "catalog_unspecified":
            reasons.append("catalog_date_role_not_formation_date")
        if review_state in {"unreviewed", "unknown"}:
            reasons.append("record_not_analyst_reviewed")
        source_lineage = [
            [text(source.get("assertionId")), text(source.get("name")), text(source.get("recordUrl"))]
            for source in (record.get("sources") or [])
            if isinstance(source, Mapping)
        ]
        rows.append({
            "id": record_id,
            "lat": round(lat, 7) if lat is not None else None,
            "lon": round(normalize_longitude(lon), 7) if lon is not None else None,
            "coordinateEvidenceCode": coordinate_evidence,
            "coordinateUncertaintyKm": finite_number(record.get("coordinateUncertaintyKm")),
            "startOrdinal": start,
            "endOrdinal": end,
            "datePrecisionCode": date_precision,
            "dateRoleCode": date_role,
            "formationDateKnown": formation_known,
            "reviewStateCode": review_state,
            "lineageHash": lineage_hash(sorted(source_lineage)),
            "sourceFamilyCount": len(set(record.get("sourceFamilies") or [])),
            "kilometerEligible": not reasons,
            "exclusionReasonCodes": sorted(set(reasons)),
        })
    source = {
        "manifestBytes": len(manifest_bytes),
        "manifestSha256": sha256_bytes(manifest_bytes),
        "releaseId": manifest.get("releaseId"),
        "rowCount": len(rows),
        "policy": {
            "localityCentroidsKilometerEligible": False,
            "candidateMarkersKilometerEligible": False,
            "catalogDatesSubstituteForFormationDates": False,
            "minimumDomainEligibleRecordsForInference": 25,
            "traceEligible": False,
        },
        "readiness": {
            "eligibleRecordCount": sum(row["kilometerEligible"] for row in rows),
            "minimumEligibleRecords": 25,
            "status": "not_estimable",
            "reasons": [
                "eligible_record_count_below_25",
                "formation_date_and_coordinate_evidence_gates_not_jointly_satisfied",
                "locality_and_candidate_markers_excluded_from_kilometer_analysis",
            ],
        },
    }
    return rows, source


def build_animal_context_projection(source_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str]]:
    records, manifest, manifest_bytes = detail_records(source_root / "animal_mutilations")
    rows: list[dict[str, Any]] = []
    incident_to_public: dict[str, str] = {}
    for record_id in sorted(records):
        record = records[record_id]
        coordinates = record.get("coordinates")
        lon = finite_number(coordinates[0]) if isinstance(coordinates, list) and len(coordinates) >= 2 else None
        lat = finite_number(coordinates[1]) if isinstance(coordinates, list) and len(coordinates) >= 2 else None
        coordinate_evidence = "generalized_public_marker" if lat is not None and lon is not None else "unmapped"
        start, end = ordinal_bounds(record.get("dateStart"), record.get("dateEnd"))
        source_incident_id = text(record.get("sourceIncidentId"))
        if source_incident_id:
            incident_to_public[source_incident_id] = record_id
        source_lineage = [
            [text(source.get("sourceId")), text(source.get("sourceHash"))]
            for source in (record.get("sourceRefs") or [])
            if isinstance(source, Mapping)
        ]
        reasons = [
            "exact_coordinate_contract_unavailable",
            "generalized_or_unmapped_location",
            "record_reported_unreviewed",
        ]
        rows.append({
            "id": record_id,
            "lat": round(lat, 7) if lat is not None else None,
            "lon": round(normalize_longitude(lon), 7) if lon is not None else None,
            "coordinateEvidenceCode": coordinate_evidence,
            "coordinateUncertaintyKm": None,
            "startOrdinal": start,
            "endOrdinal": end,
            "datePrecisionCode": text(record.get("datePrecision")) or "unknown",
            "reviewStateCode": text(record.get("status")) or "reported_unreviewed",
            "sourceIncidentId": source_incident_id or None,
            "sourceIncidentSha256": text(record.get("sourceIncidentSha256")) or None,
            "lineageHash": lineage_hash(sorted(source_lineage)),
            "kilometerEligible": False,
            "exclusionReasonCodes": reasons,
        })
    source = {
        "manifestBytes": len(manifest_bytes),
        "manifestSha256": sha256_bytes(manifest_bytes),
        "releaseId": manifest.get("releaseId"),
        "rowCount": len(rows),
        "policy": {
            "generalizedMarkersKilometerEligible": False,
            "minimumDomainEligibleRecordsForInference": 25,
            "relationshipsEligible": False,
            "traceEligible": False,
        },
        "readiness": {
            "eligibleRecordCount": 0,
            "minimumEligibleRecords": 25,
            "status": "not_estimable",
            "reasons": [
                "exact_coordinate_contract_unavailable",
                "all_records_reported_unreviewed",
                "generalized_markers_excluded_from_kilometer_analysis",
            ],
        },
    }
    return rows, source, incident_to_public


def packed_metadata(canonical_root: Path) -> tuple[dict[str, Any], Path, Path]:
    meta_path = canonical_root / "points_meta.json"
    points_path = canonical_root / "points.bin"
    metadata = load_json(meta_path)
    if int(metadata.get("schema_version", 0)) != 3:
        raise ValueError("Analysis v2 requires packed-points schema v3")
    if points_path.stat().st_size != int(metadata["row_count"]) * int(metadata["bytes_per_row"]):
        raise ValueError("Packed point byte length does not match metadata")
    return metadata, meta_path, points_path


def lookup(metadata: Mapping[str, Any], table_name: str, index: Any) -> str | None:
    table = metadata["lookup_tables"][table_name]
    value = table[int(index)]
    return str(value) if value is not None else None


def haversine_km(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    phi_a = math.radians(lat_a)
    phi_b = math.radians(lat_b)
    delta_phi = phi_b - phi_a
    delta_lon = math.radians(((lon_b - lon_a + 180.0) % 360.0) - 180.0)
    value = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi_a) * math.cos(phi_b) * math.sin(delta_lon / 2.0) ** 2
    )
    return 2.0 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(value)))


def build_neighbor_projection(canonical_root: Path) -> tuple[list[list[Any]], dict[str, Any]]:
    metadata, meta_path, points_path = packed_metadata(canonical_root)
    row_struct = struct.Struct(str(metadata["struct_format"]))
    fields = {str(field["name"]): index for index, field in enumerate(metadata["fields"])}
    required = {
        "event_id",
        "lat",
        "lon",
        "sort_date_key",
        "source_id",
        "craft_type_id",
        "craft_type_confidence_id",
        "same_day_match_strength_id",
        "date_precision_id",
        "coordinate_source_id",
    }
    if not required <= fields.keys():
        raise ValueError(f"Packed point schema lacks neighbor fields: {sorted(required - fields.keys())}")
    exclusions: Counter[str] = Counter()
    points: list[tuple[int, float, float, int, str, str]] = []
    coordinate_counts: Counter[tuple[float, float]] = Counter()
    with points_path.open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as mapped:
        for row in row_struct.iter_unpack(mapped):
            coordinate_source = lookup(metadata, "coordinate_sources", row[fields["coordinate_source_id"]])
            if coordinate_source != "raw_latlong":
                exclusions["not_source_provided_coordinate"] += 1
                continue
            date_precision = lookup(metadata, "date_precisions", row[fields["date_precision_id"]])
            if date_precision != "exact_day":
                exclusions["date_not_exact_day"] += 1
                continue
            confidence = lookup(metadata, "craft_type_confidences", row[fields["craft_type_confidence_id"]])
            if confidence not in {"high", "medium"}:
                exclusions["craft_confidence_below_medium"] += 1
                continue
            strength = lookup(metadata, "same_day_match_strengths", row[fields["same_day_match_strength_id"]])
            if strength not in {"strong", "medium"}:
                exclusions["same_day_suitability_below_medium"] += 1
                continue
            craft = lookup(metadata, "craft_types", row[fields["craft_type_id"]])
            if craft not in RECOGNIZED_CRAFT_CLASSES:
                exclusions["craft_class_not_recognized"] += 1
                continue
            raw_date = int(row[fields["sort_date_key"]])
            try:
                day = date(raw_date // 10000, (raw_date // 100) % 100, raw_date % 100).toordinal()
            except ValueError:
                exclusions["invalid_exact_day"] += 1
                continue
            event_id = int(row[fields["event_id"]])
            lat = float(row[fields["lat"]])
            lon = normalize_longitude(float(row[fields["lon"]]))
            source = lookup(metadata, "sources", row[fields["source_id"]]) or "unknown"
            point = (event_id, lat, lon, day, source, craft)
            points.append(point)
            coordinate_counts[(round(lat, COORDINATE_PILE_DECIMALS), round(lon, COORDINATE_PILE_DECIMALS))] += 1

    pre_pile_count = len(points)
    pile_keys = {key for key, count in coordinate_counts.items() if count >= COORDINATE_PILE_MIN_SIZE}
    points = [
        point
        for point in points
        if (round(point[1], COORDINATE_PILE_DECIMALS), round(point[2], COORDINATE_PILE_DECIMALS)) not in pile_keys
    ]
    exclusions["coordinate_pile"] = pre_pile_count - len(points)
    points.sort(key=lambda point: (point[3], point[0]))

    bands: dict[int, deque[int]] = defaultdict(deque)
    pairs: list[list[Any]] = []
    for index, point in enumerate(points):
        event_id, lat, lon, day, source, _craft = point
        band = math.floor(lat)
        for candidate_band in (band - 1, band, band + 1):
            candidates = bands[candidate_band]
            while candidates and day - points[candidates[0]][3] > NEIGHBOR_MAX_DAY_LAG:
                candidates.popleft()
            for candidate_index in candidates:
                other_id, other_lat, other_lon, other_day, other_source, _other_craft = points[candidate_index]
                distance = haversine_km(lat, lon, other_lat, other_lon)
                if distance > NEIGHBOR_MAX_DISTANCE_KM:
                    continue
                left, right = sorted((event_id, other_id))
                pairs.append([
                    left,
                    right,
                    int(round(distance * 100.0)),
                    day - other_day,
                    source != other_source,
                ])
        bands[band].append(index)
    pairs.sort(key=lambda row: (row[0], row[1], row[2], row[3]))
    if len({(row[0], row[1]) for row in pairs}) != len(pairs):
        raise ValueError("Neighbor artifact contains duplicate unordered pairs")
    source = {
        "pointsMetadata": input_declaration(meta_path, label="data/canonical_web/points_meta.json"),
        "pointsBinary": input_declaration(points_path, label="data/canonical_web/points.bin"),
        "policy": {
            "chronologySegmentsRead": False,
            "coordinatePileDecimals": COORDINATE_PILE_DECIMALS,
            "coordinatePileMinimumSize": COORDINATE_PILE_MIN_SIZE,
            "coordinateSource": "raw_latlong",
            "datePrecision": "exact_day",
            "craftConfidence": ["medium", "high"],
            "sameDaySuitability": ["medium", "strong"],
            "recognizedCraftClasses": sorted(RECOGNIZED_CRAFT_CLASSES),
            "maximumDistanceKm": NEIGHBOR_MAX_DISTANCE_KM,
            "maximumDayLag": NEIGHBOR_MAX_DAY_LAG,
            "pairIdentity": "unique_unordered_event_pair",
            "distanceUnit": "decameter",
        },
        "counts": {
            "packedRows": int(metadata["row_count"]),
            "eligibleBeforePileExclusion": pre_pile_count,
            "eligiblePoints": len(points),
            "coordinatePilesExcluded": len(pile_keys),
            "coordinatePileRowsExcluded": exclusions["coordinate_pile"],
            "pairs": len(pairs),
            "crossSourcePairs": sum(bool(row[4]) for row in pairs),
            "pairsWithin25Km7Days": sum(row[2] <= 2500 and row[3] <= 7 for row in pairs),
            "pairsWithin50Km7Days": sum(row[2] <= 5000 and row[3] <= 7 for row in pairs),
        },
        "exclusions": dict(sorted(exclusions.items())),
        "readiness": {
            "eligiblePointCount": len(points),
            "eligiblePointsBySource": dict(sorted(Counter(point[4] for point in points).items())),
            "status": "qualified_candidate_pool",
            "warnings": [
                "eligible_source_coordinates_are_currently_limited_to_majestic_and_ufocat",
                "source_balancing_and_leave_one_source_out_sensitivity_required",
                "point_neighborhood_association_is_not_observed_travel",
            ],
        },
    }
    return pairs, source


def discover_relationship_source() -> Path | None:
    candidates = [
        REPO_ROOT / "data" / "analysis_inputs" / "cross_domain_relationships.jsonl",
        Path.home()
        / "Documents"
        / "Cattle Mutilation Map"
        / "outputs"
        / "phase1_1"
        / "global_animal_seed_v1_1_repeat"
        / "cross_domain_relationships.jsonl",
    ]
    return next((path for path in candidates if path.is_file()), None)


def snapshot_relationship_source(path: Path) -> tuple[list[list[Any]], dict[str, Any]]:
    rows: list[list[Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            subject = record.get("subject") or {}
            object_record = record.get("object") or {}
            source_input_ids = sorted({
                text(source_ref.get("source_id"))[4:]
                for source_ref in (record.get("source_refs") or [])
                if isinstance(source_ref, Mapping) and text(source_ref.get("source_id")).startswith("ufo:cin_")
            })
            relationship_id = text(record.get("relationship_id"))
            if not relationship_id:
                raise ValueError(f"Relationship line {line_number} has no ID")
            rows.append([
                relationship_id,
                text(subject.get("native_event_id")),
                text(object_record.get("domain")) or "unknown",
                text(object_record.get("external_id", object_record.get("native_event_id"))),
                text(record.get("assertion_mode")) or "unknown",
                text(record.get("relationship_type")) or "unknown",
                text(record.get("review_state")) or "unknown",
                source_input_ids,
            ])
    rows.sort(key=lambda row: row[0])
    if len({row[0] for row in rows}) != len(rows):
        raise ValueError("Relationship source contains duplicate relationship IDs")
    return rows, {
        "bytes": path.stat().st_size,
        "label": "Cattle Mutilation Map phase1_1 global_animal_seed_v1_1_repeat relationships",
        "rowCount": len(rows),
        "sha256": sha256_path(path),
        "snapshotPolicy": "identity_and_lane_fields_only_no_narrative_or_source_locators",
    }


def load_relationship_snapshot(path: Path) -> tuple[list[list[Any]], dict[str, Any]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or any(not isinstance(row, list) or len(row) != len(RELATIONSHIP_SOURCE_ROW_SCHEMA) for row in rows):
        raise ValueError("Invalid relationship source snapshot")
    metadata_path = path.with_name(RELATIONSHIP_SNAPSHOT_META_FILENAME)
    if not metadata_path.is_file():
        raise ValueError("Relationship source snapshot has no pinned source metadata")
    metadata = load_json(metadata_path)
    if int(metadata.get("rowCount", -1)) != len(rows):
        raise ValueError("Relationship source snapshot metadata row count mismatch")
    return rows, metadata


def reconcile_input_ids(canonical_source: Path, wanted: set[str]) -> dict[str, tuple[str, int | None]]:
    found: dict[str, tuple[str, int | None]] = {}
    with canonical_source.open("rb", buffering=8 * 1024 * 1024) as stream:
        for line in stream:
            input_ids = {match.decode("ascii") for match in CANONICAL_INPUT_ID_RE.findall(line)} & wanted
            if not input_ids:
                continue
            canonical_match = CANONICAL_EVENT_ID_RE.search(line)
            if canonical_match is None:
                raise ValueError("Current canonical row with requested input lineage lacks canonical event ID")
            served_match = SERVED_EVENT_ID_RE.search(line)
            current = (
                canonical_match.group(1).decode("ascii"),
                int(served_match.group(1)) if served_match else None,
            )
            for input_id in input_ids:
                if input_id in found and found[input_id] != current:
                    raise ValueError(f"Canonical input lineage maps to multiple current events: {input_id}")
                found[input_id] = current
    return found


def build_relationship_projection(
    snapshot_rows: list[list[Any]],
    canonical_source: Path,
    animal_incident_to_public: Mapping[str, str],
    crop_ids: set[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_indices = {field: index for index, field in enumerate(RELATIONSHIP_SOURCE_ROW_SCHEMA)}
    wanted = {
        input_id
        for row in snapshot_rows
        for input_id in row[source_indices["sourceInputIds"]]
    }
    input_mapping = reconcile_input_ids(canonical_source, wanted)
    rows: list[dict[str, Any]] = []
    for source_row in snapshot_rows:
        relationship_id = source_row[source_indices["relationshipId"]]
        subject_source_id = source_row[source_indices["subjectSourceIncidentId"]]
        object_domain = source_row[source_indices["objectDomain"]]
        object_source_id = source_row[source_indices["objectSourceId"]]
        source_input_ids = source_row[source_indices["sourceInputIds"]]
        subject_public = animal_incident_to_public.get(subject_source_id)
        reasons: list[str] = []
        if subject_public is None:
            reasons.append("subject_not_in_current_animal_release")
        object_analysis_id: str | None = None
        current_ufo_event_id: int | None = None
        if object_domain == "ufo":
            current_events = {input_mapping[input_id] for input_id in source_input_ids if input_id in input_mapping}
            if len(current_events) == 1 and len(source_input_ids) == sum(input_id in input_mapping for input_id in source_input_ids):
                current_canonical_id, current_ufo_event_id = next(iter(current_events))
                object_analysis_id = current_canonical_id
                if current_ufo_event_id is None:
                    reasons.append("current_ufo_event_unmapped")
            elif not current_events:
                reasons.append("ufo_lineage_not_found_in_current_catalog")
            else:
                reasons.append("ufo_lineage_maps_to_multiple_current_events")
        elif object_domain == "crop_circle":
            if object_source_id in crop_ids:
                object_analysis_id = object_source_id
            else:
                reasons.append("crop_source_candidate_not_in_current_crop_release")
        else:
            reasons.append("unsupported_object_domain")
        reasons.extend([
            "animal_exact_coordinate_contract_unavailable",
            "relationship_not_analyst_adjudicated_for_inference",
        ])
        if subject_public is None:
            status = "quarantined_subject"
        elif object_analysis_id is None:
            status = "quarantined_object"
        elif current_ufo_event_id is None and object_domain == "ufo":
            status = "reconciled_unmapped_ufo"
        else:
            status = "reconciled_current"
        rows.append({
            "relationshipId": relationship_id,
            "subjectAnalysisId": subject_public,
            "objectDomainCode": object_domain,
            "objectAnalysisId": object_analysis_id,
            "assertionModeCode": source_row[source_indices["assertionMode"]],
            "relationshipTypeCode": source_row[source_indices["relationshipType"]],
            "reviewStateCode": source_row[source_indices["reviewState"]],
            "currentUfoEventId": current_ufo_event_id,
            "reconciliationStatusCode": status,
            "associationEligible": False,
            "sourceInputCount": len(source_input_ids),
            "exclusionReasonCodes": sorted(set(reasons)),
        })
    rows.sort(key=lambda row: row["relationshipId"])
    source = {
        "canonicalSource": input_declaration(
            canonical_source,
            label="data/canonical_full_maximal_v3_rehydrated_jurisdiction_repair/deduped_events.jsonl",
        ),
        "counts": {
            "rows": len(rows),
            "sourceInputIds": len(wanted),
            "sourceInputIdsReconciled": len(input_mapping),
            "reconciledCurrent": sum(row["reconciliationStatusCode"] == "reconciled_current" for row in rows),
            "reconciledUnmappedUfo": sum(row["reconciliationStatusCode"] == "reconciled_unmapped_ufo" for row in rows),
            "quarantinedSubject": sum(row["reconciliationStatusCode"] == "quarantined_subject" for row in rows),
            "quarantinedObject": sum(row["reconciliationStatusCode"] == "quarantined_object" for row in rows),
            "associationEligible": 0,
        },
        "policy": {
            "canonicalEventIdStringSimilarityUsed": False,
            "reconciliationKey": "canonical_input_lineage",
            "explicitSourceComputedAndReviewedLanesRemainSeparate": True,
            "unresolvedRelationshipsQuarantined": True,
            "associationInferenceEnabled": False,
        },
        "readiness": {
            "eligibleRelationshipCount": 0,
            "minimumEligibleRecords": 25,
            "status": "not_estimable",
            "reasons": [
                "animal_exact_coordinate_contract_unavailable",
                "relationships_not_analyst_adjudicated_for_inference",
                "unresolved_subjects_and_objects_remain_quarantined",
            ],
        },
    }
    return rows, source


def classify_uncertain_distance(
    marker_distance_km: float,
    subject_uncertainty_km: float,
    object_uncertainty_km: float,
    radius_km: float,
) -> str:
    uncertainty = max(0.0, float(subject_uncertainty_km)) + max(0.0, float(object_uncertainty_km))
    minimum = max(0.0, float(marker_distance_km) - uncertainty)
    maximum = float(marker_distance_km) + uncertainty
    if maximum <= radius_km:
        return "near"
    if minimum > radius_km:
        return "far"
    return "ambiguous"


def encoded_projection(rows: list[dict[str, Any]], schema: list[str]) -> tuple[list[list[Any]], dict[str, list[str]]]:
    code_fields = [field for field in schema if field.endswith("Code")]
    code_maps: dict[str, dict[str, int]] = {}
    code_tables: dict[str, list[str]] = {}
    for field in code_fields:
        labels, mapping = codebook(row.get(field) for row in rows)
        code_maps[field] = mapping
        code_tables[field.removesuffix("Code")] = labels
    reason_values = {reason for row in rows for reason in (row.get("exclusionReasonCodes") or [])}
    reason_labels, reason_map = codebook(reason_values or {"none"})
    transformed: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["exclusionReasonCodes"] = sorted(reason_map[reason] for reason in item.get("exclusionReasonCodes", []))
        transformed.append(item)
    code_tables["exclusionReason"] = reason_labels
    return encode_rows(transformed, schema, code_maps), code_tables


def build(
    *,
    source_root: Path = STATIC_DATA_ROOT,
    canonical_root: Path = DEFAULT_CANONICAL_ROOT,
    canonical_source: Path = DEFAULT_CANONICAL_SOURCE,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    release_id: str = DEFAULT_RELEASE_ID,
    browser_base_path: str = DEFAULT_BROWSER_BASE_PATH,
    relationship_source: Path | None = None,
    relationship_snapshot: Path | None = None,
) -> dict[str, Any]:
    if not SAFE_RELEASE_ID_RE.fullmatch(release_id):
        raise ValueError(f"Invalid release ID: {release_id!r}")
    if not browser_base_path.strip("/") or ".." in Path(browser_base_path).parts:
        raise ValueError("Invalid browser base path")

    facility_rows, facility_source = build_facility_projection(source_root)
    crop_rows, crop_source = build_crop_context_projection(source_root)
    animal_rows, animal_source, animal_incident_to_public = build_animal_context_projection(source_root)
    neighbor_rows, neighbor_source = build_neighbor_projection(canonical_root)

    frozen_snapshot = relationship_snapshot or (DEFAULT_OUTPUT_ROOT / RELATIONSHIP_SNAPSHOT_FILENAME)
    selected_relationship_source = relationship_source
    if selected_relationship_source is None and frozen_snapshot.is_file():
        relationship_source_rows, relationship_source_meta = load_relationship_snapshot(frozen_snapshot)
    else:
        selected_relationship_source = selected_relationship_source or discover_relationship_source()
        if selected_relationship_source is None:
            raise ValueError(
                "No relationship source or frozen minimal snapshot is available; refusing to invent reconciliation state"
            )
        relationship_source_rows, relationship_source_meta = snapshot_relationship_source(
            selected_relationship_source
        )
    relationship_rows, relationship_source = build_relationship_projection(
        relationship_source_rows,
        canonical_source,
        animal_incident_to_public,
        {row["id"] for row in crop_rows},
    )

    facility_encoded, facility_codes = encoded_projection(facility_rows, FACILITY_ROW_SCHEMA)
    crop_encoded, crop_codes = encoded_projection(crop_rows, CROP_CONTEXT_ROW_SCHEMA)
    animal_encoded, animal_codes = encoded_projection(animal_rows, ANIMAL_CONTEXT_ROW_SCHEMA)
    relationship_encoded, relationship_codes = encoded_projection(
        relationship_rows,
        RELATIONSHIP_ROW_SCHEMA,
    )
    artifacts = {
        "animalContextReadiness": write_projection(
            output_root, browser_base_path, "animal_context_readiness.json", animal_encoded, ANIMAL_CONTEXT_ROW_SCHEMA
        ),
        "cropContextReadiness": write_projection(
            output_root, browser_base_path, "crop_context_readiness.json", crop_encoded, CROP_CONTEXT_ROW_SCHEMA
        ),
        "facilityAnalysis": write_projection(
            output_root, browser_base_path, "facility_analysis_v1.json", facility_encoded, FACILITY_ROW_SCHEMA
        ),
        "relationshipReconciliation": write_projection(
            output_root,
            browser_base_path,
            "relationship_reconciliation.json",
            relationship_encoded,
            RELATIONSHIP_ROW_SCHEMA,
        ),
        "ufoPointNeighbors": write_projection(
            output_root,
            browser_base_path,
            "ufo_point_neighbors_v1.json",
            neighbor_rows,
            NEIGHBOR_ROW_SCHEMA,
        ),
    }
    snapshot_artifact = write_projection(
        output_root,
        browser_base_path,
        RELATIONSHIP_SNAPSHOT_FILENAME,
        relationship_source_rows,
        RELATIONSHIP_SOURCE_ROW_SCHEMA,
    )
    snapshot_metadata_artifact = write_document(
        output_root,
        browser_base_path,
        RELATIONSHIP_SNAPSHOT_META_FILENAME,
        relationship_source_meta,
    )

    manifest = {
        "artifacts": artifacts,
        "codes": {
            "animalContextReadiness": animal_codes,
            "cropContextReadiness": crop_codes,
            "facilityAnalysis": facility_codes,
            "relationshipReconciliation": relationship_codes,
        },
        "counts": {
            "animalContextRecords": len(animal_rows),
            "animalKilometerEligible": sum(row["kilometerEligible"] for row in animal_rows),
            "cropContextRecords": len(crop_rows),
            "cropKilometerEligible": sum(row["kilometerEligible"] for row in crop_rows),
            "facilityMarkers": len(facility_rows),
            "facilityInferentialEligible": sum(row["inferentialEligible"] for row in facility_rows),
            "relationshipRows": len(relationship_rows),
            "relationshipAssociationEligible": 0,
            "ufoNeighborEligiblePoints": neighbor_source["counts"]["eligiblePoints"],
            "ufoNeighborPairs": len(neighbor_rows),
        },
        "determinism": {
            "canonicalJson": "utf8_sorted_keys_compact_with_lf",
            "gzipMtime": 0,
            "neighborPairOrder": "left_event_id_right_event_id_distance_day_lag",
            "projectionRowOrder": "stable_id_ascending",
        },
        "policy": {
            "authenticityAssessments": False,
            "causalInferences": False,
            "chronologySegmentsRead": False,
            "contextProximityFailClosed": True,
            "generalizedCoordinatesKilometerEligible": False,
            "minimumContextEligibleRecordsForInference": 25,
            "pointNeighborhoodsOnly": True,
            "traceMetrics": False,
            "travelMetrics": False,
        },
        "releaseId": release_id,
        "schemaId": SCHEMA_ID,
        "schemaVersion": 2,
        "sources": {
            "animalContext": animal_source,
            "cropContext": crop_source,
            "facilities": facility_source,
            "relationshipPackage": relationship_source_meta,
            "relationshipReconciliation": relationship_source,
            "relationshipSourceSnapshot": snapshot_artifact,
            "relationshipSourceSnapshotMetadata": snapshot_metadata_artifact,
            "ufoPointNeighbors": neighbor_source,
        },
    }
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "manifest.json").write_bytes(canonical_json_document(manifest))
    return manifest


def main() -> int:
    args = parse_args()
    manifest = build(
        source_root=args.source_root,
        canonical_root=args.canonical_root,
        canonical_source=args.canonical_source,
        output_root=args.output,
        release_id=args.release_id,
        browser_base_path=args.browser_base_path,
        relationship_source=args.relationship_source,
        relationship_snapshot=args.relationship_snapshot,
    )
    print(json.dumps({
        "artifacts": manifest["artifacts"],
        "counts": manifest["counts"],
        "releaseId": manifest["releaseId"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
