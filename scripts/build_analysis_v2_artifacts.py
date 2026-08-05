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

try:
    from scripts import build_analysis_geography_binary_v1 as geography_binary
except ImportError:  # Direct script execution resolves sibling modules here.
    import build_analysis_geography_binary_v1 as geography_binary


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
DEFAULT_RELEASE_ID = "analysis-evidence-lab-v2.2-20260803"
SCHEMA_ID = "ufo-timeline-analysis-evidence-artifacts-v2.2.0"
ESTIMATOR_VERSION = "ufo-analysis-evidence-lab-v2.2.0"
RELATIONSHIP_SNAPSHOT_FILENAME = "relationship_source_snapshot.json"
RELATIONSHIP_SNAPSHOT_META_FILENAME = "relationship_source_snapshot.meta.json"
SAFE_RELEASE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
CANONICAL_EVENT_ID_RE = re.compile(br'"canonical_event_id":"(evt_[0-9a-f]+)"')
CANONICAL_INPUT_ID_RE = re.compile(br"cin_[0-9a-f]+")
SERVED_EVENT_ID_RE = re.compile(br'"coordinate_rehydration_served_event_id":(\d+)')

EARTH_RADIUS_KM = 6_371.0088
NEIGHBOR_MAX_DISTANCE_KM = 100.0
NEIGHBOR_MAX_DAY_LAG = 30
CONTEXT_MAX_DISTANCE_KM = 250.0
CONTEXT_MAX_DAY_LAG = 30
CONTEXT_CONTROL_YEAR_OFFSETS = (-2, -1, 1, 2)
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
CONFIGURATION_CLASS = "formation"
WORLD_COUNTRIES_FILENAME = "world_countries.geojson"
WORLD_COUNTRY_BUCKET_DEGREES = 5
WORLD_COUNTRY_BOUNDARY_EPSILON = 1e-9
READINESS_STATUSES = {
    "ready_inferential",
    "ready_sensitivity",
    "ready_descriptive",
    "limited",
    "blocked",
    "not_applicable",
    "not_evaluated",
    "data_unavailable",
}

# Each published projection has an independently identifiable release and a
# semantic row key.  The manifest hashes the ordered key stream separately
# from the artifact bytes so consumers can distinguish row-order drift from a
# content change.  Key fields are deliberately stable identifiers, never
# presentation labels or dictionary ordinals alone.
ARTIFACT_CONTRACTS = {
    "animalContextReadiness": {
        "artifactId": "animal_context_readiness_v2",
        "orderingFields": ("id",),
        "orderingPolicyId": "animal_analysis_id_order_v1",
    },
    "cropContextReadiness": {
        "artifactId": "crop_context_readiness_v2",
        "orderingFields": ("id",),
        "orderingPolicyId": "crop_analysis_id_order_v1",
    },
    "facilityAnalysis": {
        "artifactId": "facility_analysis_v1",
        "orderingFields": ("id",),
        "orderingPolicyId": "facility_analysis_id_order_v1",
    },
    "relationshipReconciliation": {
        "artifactId": "relationship_reconciliation_v2",
        "orderingFields": ("relationshipId",),
        "orderingPolicyId": "relationship_id_order_v1",
    },
    "ufoPointNeighbors": {
        "artifactId": "ufo_point_neighbors_v1",
        "orderingFields": ("leftEventId", "rightEventId", "distanceDecameters", "dayLag"),
        "orderingPolicyId": "unordered_event_pair_order_v1",
    },
    "ufoSpatialPoints": {
        "artifactId": "ufo_spatial_points_v2",
        "orderingFields": ("eventId",),
        "orderingPolicyId": "event_id_order_v1",
    },
    "contextUfoNeighbors": {
        "artifactId": "context_ufo_neighbors_v1",
        "orderingFields": (
            "contextDomainCode", "contextLaneCode", "contextId", "dateRoleCode",
            "ufoEventId", "distanceDecameters", "dayLag",
        ),
        "orderingPolicyId": "context_role_ufo_distance_lag_order_v1",
    },
    "ufoGeography": {
        "artifactId": "ufo_geography_v1",
        "orderingFields": ("pointRowIndex", "eventId"),
        "orderingPolicyId": "packed_point_row_alignment_order_v1",
    },
    "ufoConfigurationPoints": {
        "artifactId": "ufo_configuration_points_v1",
        "orderingFields": ("eventId",),
        "orderingPolicyId": "configuration_event_id_order_v1",
    },
    "ufoConfigurationNeighbors": {
        "artifactId": "ufo_configuration_neighbors_v1",
        "orderingFields": ("leftEventId", "rightEventId", "distanceDecameters", "dayLag"),
        "orderingPolicyId": "configuration_unordered_event_pair_order_v1",
    },
}
RELATIONSHIP_SNAPSHOT_CONTRACT = {
    "artifactId": "relationship_source_snapshot_v1",
    "orderingFields": ("relationshipId",),
    "orderingPolicyId": "relationship_source_id_order_v1",
}
RELATIONSHIP_SNAPSHOT_METADATA_ARTIFACT_ID = "relationship_source_snapshot_metadata_v1"

# Broad, deterministic UN-M49-like analytical regions.  These labels are for
# source balancing and navigation, not geopolitical adjudication.  The builder
# fails if the pinned country shell contains a name that is not assigned exactly
# once, so a changed boundary release cannot silently drift the taxonomy.
MACROREGION_COUNTRIES = {
    "africa": {
        "Algeria", "Angola", "Benin", "Botswana", "Burkina Faso", "Burundi",
        "Cameroon", "Central African Republic", "Chad", "Democratic Republic of the Congo",
        "Djibouti", "Egypt", "Equatorial Guinea", "Eritrea", "Ethiopia", "Gabon",
        "Gambia", "Ghana", "Guinea", "Guinea Bissau", "Ivory Coast", "Kenya",
        "Lesotho", "Liberia", "Libya", "Madagascar", "Malawi", "Mali", "Mauritania",
        "Morocco", "Mozambique", "Namibia", "Niger", "Nigeria", "Republic of the Congo",
        "Rwanda", "Senegal", "Sierra Leone", "Somalia", "Somaliland", "South Africa",
        "South Sudan", "Sudan", "Swaziland", "Togo", "Tunisia", "Uganda",
        "United Republic of Tanzania", "Western Sahara", "Zambia", "Zimbabwe",
    },
    "asia": {
        "Afghanistan", "Armenia", "Azerbaijan", "Bangladesh", "Bhutan", "Brunei",
        "Cambodia", "China", "Cyprus", "East Timor", "Georgia", "India", "Indonesia",
        "Iran", "Iraq", "Israel", "Japan", "Jordan", "Kazakhstan", "Kuwait",
        "Kyrgyzstan", "Laos", "Lebanon", "Malaysia", "Mongolia", "Myanmar", "Nepal",
        "North Korea", "Northern Cyprus", "Oman", "Pakistan", "Philippines", "Qatar",
        "Saudi Arabia", "South Korea", "Sri Lanka", "Syria", "Taiwan", "Tajikistan",
        "Thailand", "Turkey", "Turkmenistan", "United Arab Emirates", "Uzbekistan",
        "Vietnam", "West Bank", "Yemen",
    },
    "europe": {
        "Albania", "Austria", "Belarus", "Belgium", "Bosnia and Herzegovina", "Bulgaria",
        "Croatia", "Czech Republic", "Denmark", "Estonia", "Finland", "France", "Germany",
        "Greece", "Hungary", "Iceland", "Ireland", "Italy", "Kosovo", "Latvia",
        "Lithuania", "Luxembourg", "Macedonia", "Malta", "Moldova", "Montenegro",
        "Netherlands", "Norway", "Poland", "Portugal", "Republic of Serbia", "Romania",
        "Russia", "Slovakia", "Slovenia", "Spain", "Sweden", "Switzerland", "Ukraine",
        "United Kingdom",
    },
    "latin_america_caribbean": {
        "Argentina", "Belize", "Bolivia", "Brazil", "Chile", "Colombia", "Costa Rica",
        "Cuba", "Dominican Republic", "Ecuador", "El Salvador", "Falkland Islands",
        "French Guiana", "Guatemala", "Guyana", "Haiti", "Honduras", "Jamaica", "Mexico",
        "Nicaragua", "Panama", "Paraguay", "Peru", "Puerto Rico", "Suriname", "The Bahamas",
        "Trinidad and Tobago", "Uruguay", "Venezuela",
    },
    "northern_america": {
        "Bermuda", "Canada", "Greenland", "United States of America",
    },
    "oceania": {
        "Australia", "Fiji", "New Caledonia", "New Zealand", "Papua New Guinea",
        "Solomon Islands", "Vanuatu",
    },
    "antarctica": {
        "Antarctica", "French Southern and Antarctic Lands",
    },
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
    "analysisLaneCode",
    "featureGroupCode",
    "locationDateClusterId",
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
    "analysisLaneCode",
    "featureGroupCode",
    "locationDateClusterId",
    "originInputIds",
    "originUfoEventIds",
    "originPublisherCodes",
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
UFO_SPATIAL_POINT_ROW_SCHEMA = [
    "eventId",
    "lat",
    "lon",
    "ordinal",
    "year",
    "sourceCode",
    "craftCode",
    "craftConfidenceCode",
    "sameDayMatchStrengthCode",
    "coordinateEvidenceCode",
    "coordinatePileGroup",
    "coordinatePileCount",
    "fineSpatialStratumCode",
    "coarseSpatialStratumCode",
    "fiveYearBand",
    "decade",
    "duplicateLineageCode",
]
UFO_GEOGRAPHY_ROW_SCHEMA = [
    "pointRowIndex",
    "eventId",
    "countryCode",
    "macroregionCode",
    "assignmentSourceCode",
    "assignmentConfidenceCode",
    "boundaryStatusCode",
    "coordinateEvidenceCode",
]
UFO_CONFIGURATION_POINT_ROW_SCHEMA = [
    "eventId",
    "lat",
    "lon",
    "ordinal",
    "year",
    "sourceCode",
    "configurationCode",
    "configurationConfidenceCode",
    "configurationSourceCode",
    "sameDayMatchStrengthCode",
    "coordinateEvidenceCode",
    "coordinatePileGroup",
    "coordinatePileCount",
    "fineSpatialStratumCode",
    "coarseSpatialStratumCode",
    "fiveYearBand",
    "decade",
    "duplicateLineageCode",
]
CONTEXT_UFO_NEIGHBOR_ROW_SCHEMA = [
    "contextDomainCode",
    "contextLaneCode",
    "contextId",
    "contextClusterId",
    "contextOrdinal",
    "ufoEventId",
    "distanceDecameters",
    "dayLag",
    "distanceRingCode",
    "dayLagBandCode",
    "uncertaintyClassCode",
    "contextUncertaintyKm",
    "ufoCraftCode",
    "ufoSourceCode",
    "ufoFineSpatialStratumCode",
    "ufoCoarseSpatialStratumCode",
    "featureGroupCode",
    "originUfoExcluded",
    "originPublisherExcluded",
    "independentAssociationEligible",
    "dateRoleCode",
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
    *,
    artifact_id: str,
    release_id: str,
    ordering_fields: Sequence[str],
    ordering_policy_id: str,
) -> dict[str, Any]:
    raw = canonical_json_document(rows)
    compressed = deterministic_gzip(raw)
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / filename).write_bytes(raw)
    (output_root / f"{filename}.gz").write_bytes(compressed)
    prefix = browser_base_path.strip("/")
    return {
        "artifactId": artifact_id,
        "bytes": len(raw),
        "file": f"{prefix}/{filename}",
        "gzipBytes": len(compressed),
        "gzipFile": f"{prefix}/{filename}.gz",
        "gzipSha256": sha256_bytes(compressed),
        "releaseId": artifact_release_id(release_id, artifact_id),
        "rowCount": len(rows),
        "rowOrdering": row_ordering_declaration(
            rows,
            row_schema,
            ordering_fields,
            policy_id=ordering_policy_id,
        ),
        "rowSchema": row_schema,
        "sha256": sha256_bytes(raw),
    }


def write_registered_projection(
    output_root: Path,
    browser_base_path: str,
    artifact_key: str,
    filename: str,
    rows: list[list[Any]],
    row_schema: list[str],
    *,
    release_id: str,
) -> dict[str, Any]:
    contract = ARTIFACT_CONTRACTS.get(artifact_key)
    if contract is None:
        raise ValueError(f"Analysis artifact is missing a release contract: {artifact_key}")
    return write_projection(
        output_root,
        browser_base_path,
        filename,
        rows,
        row_schema,
        artifact_id=contract["artifactId"],
        release_id=release_id,
        ordering_fields=contract["orderingFields"],
        ordering_policy_id=contract["orderingPolicyId"],
    )


def write_geography_binary_projection(
    output_root: Path,
    browser_base_path: str,
    rows: list[list[Any]],
    source_declaration: Mapping[str, Any],
) -> dict[str, Any]:
    encoded = geography_binary.encode_rows(rows)
    compressed = geography_binary.deterministic_gzip(encoded)
    filename = "ufo_geography_v1.bin"
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / filename).write_bytes(encoded)
    (output_root / f"{filename}.gz").write_bytes(compressed)
    prefix = browser_base_path.strip("/")
    return {
        "bytes": len(encoded),
        "decodedCanonicalJsonSha256": sha256_bytes(canonical_json_bytes(rows)),
        "decodedJsonSha256": str(source_declaration["sha256"]),
        "file": f"{prefix}/{filename}",
        "format": "ufo_geography_columnar_v1",
        "gzipBytes": len(compressed),
        "gzipFile": f"{prefix}/{filename}.gz",
        "gzipSha256": sha256_bytes(compressed),
        "sha256": sha256_bytes(encoded),
        "version": geography_binary.VERSION,
    }


def write_document(
    output_root: Path,
    browser_base_path: str,
    filename: str,
    value: Any,
    *,
    artifact_id: str,
    release_id: str,
) -> dict[str, Any]:
    raw = canonical_json_document(value)
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / filename).write_bytes(raw)
    return {
        "artifactId": artifact_id,
        "bytes": len(raw),
        "file": f"{browser_base_path.strip('/')}/{filename}",
        "releaseId": artifact_release_id(release_id, artifact_id),
        "sha256": sha256_bytes(raw),
    }


def artifact_release_id(release_id: str, artifact_id: str) -> str:
    """Return a release-scoped identifier without conflating it with a hash."""
    if not SAFE_RELEASE_ID_RE.fullmatch(release_id):
        raise ValueError(f"Invalid release ID: {release_id!r}")
    if not SAFE_RELEASE_ID_RE.fullmatch(artifact_id):
        raise ValueError(f"Invalid artifact ID: {artifact_id!r}")
    return f"{release_id}.{artifact_id}"


def row_ordering_declaration(
    rows: Sequence[Sequence[Any]],
    row_schema: Sequence[str],
    ordering_fields: Sequence[str],
    *,
    policy_id: str,
) -> dict[str, Any]:
    """Hash the canonical ordered sequence of semantic row keys.

    This is intentionally not another whole-file digest: artifact ``sha256``
    already proves bytes.  The separate hash makes row alignment and ordering
    an explicit, independently testable part of the release contract.
    """
    fields = tuple(ordering_fields)
    if not fields:
        raise ValueError("Row-ordering fields cannot be empty")
    if len(set(fields)) != len(fields):
        raise ValueError("Row-ordering fields must be unique")
    schema_indices = {field: index for index, field in enumerate(row_schema)}
    missing = [field for field in fields if field not in schema_indices]
    if missing:
        raise ValueError(f"Row-ordering fields are absent from the row schema: {missing}")
    indices = [schema_indices[field] for field in fields]
    digest = hashlib.sha256()
    digest.update(b"[")
    for row_index, row in enumerate(rows):
        if len(row) != len(row_schema):
            raise ValueError(f"Projection row {row_index} does not match its schema")
        if row_index:
            digest.update(b",")
        digest.update(canonical_json_bytes([row[index] for index in indices]))
    digest.update(b"]")
    return {
        "canonicalization": "utf8_compact_json_array_of_key_tuples",
        "keyFields": list(fields),
        "policyId": policy_id,
        "sha256": digest.hexdigest(),
    }


def input_declaration(path: Path, *, label: str) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "label": label,
        "sha256": sha256_path(path),
    }


def readiness_gate(
    gate_id: str,
    label: str,
    denominator_label: str,
    *,
    applicability: str,
    status: str,
    input_n: int | None,
    passed_n: int | None,
    unknown_n: int = 0,
    reason_codes: Sequence[str] = (),
    policy_id: str,
) -> dict[str, Any]:
    """Return a typed, independently hashable readiness decision.

    Readiness is deliberately separate from artifact-row eligibility.  A gate
    can therefore report a limited or descriptive lane without erasing the
    underlying counts that remain useful to the Evidence Lab.
    """
    if status not in READINESS_STATUSES:
        raise ValueError(f"Unsupported readiness status: {status}")
    if input_n is not None and input_n < 0:
        raise ValueError("Readiness input count cannot be negative")
    if passed_n is not None and passed_n < 0:
        raise ValueError("Readiness passed count cannot be negative")
    if unknown_n < 0:
        raise ValueError("Readiness unknown count cannot be negative")
    failed_n = None
    if input_n is not None and passed_n is not None:
        failed_n = input_n - passed_n - unknown_n
        if failed_n < 0:
            raise ValueError(f"Readiness counts are inconsistent for {gate_id}")
    gate = {
        "gateId": gate_id,
        "label": label,
        "denominatorLabel": denominator_label,
        "applicability": applicability,
        "status": status,
        "inputN": input_n,
        "passedN": passed_n,
        "failedN": failed_n,
        "unknownN": unknown_n,
        "reasonCodes": sorted({text(reason) for reason in reason_codes if text(reason)}),
        "policyId": policy_id,
    }
    gate["evidenceHash"] = sha256_bytes(canonical_json_bytes(gate))
    return gate


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
            "coverageLimitations": [
                "research_test_supplement_is_concentrated_in_northern_europe_and_new_zealand",
            ],
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
            "gates": [
                readiness_gate(
                    "facility_descriptive_inventory",
                    "Facility markers available for descriptive context",
                    "facility markers",
                    applicability="descriptive_facility_context",
                    status="ready_descriptive" if rows else "data_unavailable",
                    input_n=len(rows),
                    passed_n=len(rows),
                    policy_id="facility_marker_inventory_v1",
                ),
                readiness_gate(
                    "facility_inferential_markers",
                    "Coordinate- and time-qualified facility markers",
                    "facility markers",
                    applicability="facility_composition_inference",
                    status=(
                        "ready_inferential"
                        if sum(row["inferentialEligible"] for row in rows) >= 25
                        else "blocked"
                    ),
                    input_n=len(rows),
                    passed_n=sum(row["inferentialEligible"] for row in rows),
                    reason_codes=(
                        "claimed_sites_descriptive_only",
                        "coverage_concentrated_in_northern_europe_and_new_zealand",
                    ),
                    policy_id="facility_inferential_marker_gate_v1",
                ),
            ],
            "warnings": [
                "distances_are_marker_to_marker_not_site_boundary_distances",
                "association_does_not_establish_facility_influence",
                "research_test_coverage_is_strongly_limited_to_northern_europe_and_new_zealand_supplements",
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


def location_date_cluster_id(domain: str, lat: float | None, lon: float | None, ordinal: int | None) -> str | None:
    """Return a stable location-date unit without implying exact-site identity."""
    if lat is None or lon is None or ordinal is None:
        return None
    key = [domain, round(float(lat), 4), round(normalize_longitude(float(lon)), 4), int(ordinal)]
    return f"ctx_{sha256_bytes(canonical_json_bytes(key))[:20]}"


def crop_feature_group(record: Mapping[str, Any]) -> str:
    morphology = [row for row in (record.get("morphology") or []) if isinstance(row, Mapping)]
    morphology.sort(key=lambda row: (finite_number(row.get("rank")) or 1_000_000, text(row.get("family"))))
    return text(morphology[0].get("family")) if morphology else "unknown"


def animal_feature_group(record: Mapping[str, Any]) -> str:
    groups = sorted({text(value).lower() for value in (record.get("speciesGroups") or []) if text(value)})
    return groups[0] if groups else "unknown"


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
        analysis_lane = "excluded"
        if date_precision in {"day", "exact_day"} and coordinate_evidence in {
            "exact_source_coordinate", "candidate_field_marker"
        }:
            analysis_lane = "crop_bounded"
        elif date_precision in {"day", "exact_day"} and coordinate_evidence == "locality_centroid":
            analysis_lane = "crop_locality"
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
            "analysisLaneCode": analysis_lane,
            "featureGroupCode": crop_feature_group(record),
            "locationDateClusterId": location_date_cluster_id("crop", lat, lon, start),
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
            "candidateMarkersBoundedAnalysisEligible": True,
            "localityCentroidsRoughMarkerAnalysisEligible": True,
            "catalogDatesSubstituteForFormationDates": False,
            "minimumDomainEligibleRecordsForInference": 25,
            "traceEligible": False,
        },
        "readiness": {
            "eligibleRecordCount": sum(row["kilometerEligible"] for row in rows),
            "minimumEligibleRecords": 25,
            "status": "strict_not_estimable_exploratory_lanes_ready",
            "reasons": [
                "eligible_record_count_below_25",
                "formation_date_and_coordinate_evidence_gates_not_jointly_satisfied",
                "locality_and_candidate_markers_excluded_from_kilometer_analysis",
            ],
            "analysisLanes": {
                "cropBoundedExactDay": sum(row["analysisLaneCode"] == "crop_bounded" for row in rows),
                "cropLocalityExactDay": sum(row["analysisLaneCode"] == "crop_locality" for row in rows),
            },
            "gates": [
                readiness_gate(
                    "crop_exact_site_formation_date",
                    "Exact-site reviewed formation-date evidence",
                    "crop-circle catalog records",
                    applicability="strict_kilometer_inference",
                    status="blocked",
                    input_n=len(rows),
                    passed_n=sum(row["kilometerEligible"] for row in rows),
                    reason_codes=(
                        "formation_date_and_coordinate_evidence_gates_not_jointly_satisfied",
                        "catalog_dates_cannot_substitute_for_formation_dates",
                    ),
                    policy_id="crop_strict_site_date_gate_v2",
                ),
                readiness_gate(
                    "crop_bounded_marker_lane",
                    "Exact-day bounded crop markers",
                    "crop-circle catalog records",
                    applicability="bounded_marker_sensitivity_analysis",
                    status="ready_sensitivity",
                    input_n=len(rows),
                    passed_n=sum(row["analysisLaneCode"] == "crop_bounded" for row in rows),
                    reason_codes=("time_role_is_catalog_date_not_formation_date",),
                    policy_id="crop_bounded_marker_lane_v1",
                ),
                readiness_gate(
                    "crop_locality_marker_lane",
                    "Exact-day crop locality markers",
                    "crop-circle catalog records",
                    applicability="rough_marker_sensitivity_analysis",
                    status="ready_sensitivity",
                    input_n=len(rows),
                    passed_n=sum(row["analysisLaneCode"] == "crop_locality" for row in rows),
                    reason_codes=(
                        "locality_centroids_are_not_exact_sites",
                        "time_role_is_catalog_date_not_formation_date",
                    ),
                    policy_id="crop_locality_marker_lane_v1",
                ),
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
        origin_input_ids = sorted({
            text(source.get("sourceId"))[4:]
            for source in (record.get("sourceRefs") or [])
            if isinstance(source, Mapping) and text(source.get("sourceId")).startswith("ufo:cin_")
        })
        analysis_lane = (
            "animal_public_marker"
            if coordinate_evidence == "generalized_public_marker" and text(record.get("datePrecision")) == "exact_day"
            else "excluded"
        )
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
            "analysisLaneCode": analysis_lane,
            "featureGroupCode": animal_feature_group(record),
            "locationDateClusterId": location_date_cluster_id("animal", lat, lon, start),
            "originInputIds": origin_input_ids,
            "originUfoEventIds": [],
            "originPublisherCodes": [],
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
            "generalizedPublicMarkersRoughAnalysisEligible": True,
            "generalizedPublicMarkersDefiniteNearEligible": False,
            "minimumDomainEligibleRecordsForInference": 25,
            "relationshipsEligible": False,
            "traceEligible": False,
        },
        "readiness": {
            "eligibleRecordCount": 0,
            "minimumEligibleRecords": 25,
            "status": "strict_not_estimable_exploratory_lane_ready",
            "reasons": [
                "exact_coordinate_contract_unavailable",
                "all_records_reported_unreviewed",
                "generalized_markers_excluded_from_kilometer_analysis",
            ],
            "analysisLanes": {
                "animalPublicMarkerExactDay": sum(
                    row["analysisLaneCode"] == "animal_public_marker" for row in rows
                ),
            },
            "gates": [
                readiness_gate(
                    "animal_exact_site_reviewed",
                    "Reviewed exact-site animal evidence",
                    "animal-report catalog records",
                    applicability="strict_kilometer_inference",
                    status="blocked",
                    input_n=len(rows),
                    passed_n=0,
                    reason_codes=(
                        "exact_coordinate_contract_unavailable",
                        "all_records_reported_unreviewed",
                    ),
                    policy_id="animal_strict_site_review_gate_v2",
                ),
                readiness_gate(
                    "animal_public_marker_lane",
                    "Exact-day generalized public markers",
                    "animal-report catalog records",
                    applicability="rough_marker_sensitivity_analysis",
                    status="ready_sensitivity",
                    input_n=len(rows),
                    passed_n=sum(row["analysisLaneCode"] == "animal_public_marker" for row in rows),
                    reason_codes=(
                        "public_markers_are_not_exact_sites",
                        "definite_near_classification_prohibited",
                    ),
                    policy_id="animal_public_marker_lane_v1",
                ),
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


def macroregion_country_map(country_names: Iterable[str]) -> dict[str, str]:
    mapped: dict[str, str] = {}
    duplicates: set[str] = set()
    for macroregion, names in MACROREGION_COUNTRIES.items():
        for name in names:
            if name in mapped:
                duplicates.add(name)
            mapped[name] = macroregion
    expected = {text(name) for name in country_names if text(name)}
    missing = expected - mapped.keys()
    extra = mapped.keys() - expected
    if duplicates or missing or extra:
        raise ValueError(
            "Macroregion taxonomy does not exactly cover the pinned country release: "
            f"duplicates={sorted(duplicates)}, missing={sorted(missing)}, extra={sorted(extra)}"
        )
    return mapped


def geometry_polygon_parts(geometry: Any) -> list[list[list[list[float]]]]:
    if not isinstance(geometry, Mapping):
        return []
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geometry_type == "Polygon" and isinstance(coordinates, list):
        return [coordinates]
    if geometry_type == "MultiPolygon" and isinstance(coordinates, list):
        return [polygon for polygon in coordinates if isinstance(polygon, list)]
    return []


def ring_longitudes_unwrapped(
    ring: Sequence[Sequence[Any]],
) -> tuple[list[tuple[float, float]], float] | None:
    result: list[tuple[float, float]] = []
    previous: float | None = None
    for coordinate in ring:
        if not isinstance(coordinate, Sequence) or len(coordinate) < 2:
            continue
        lon = finite_number(coordinate[0])
        lat = finite_number(coordinate[1])
        if lon is None or lat is None:
            continue
        if previous is not None:
            while lon - previous > 180.0:
                lon -= 360.0
            while lon - previous < -180.0:
                lon += 360.0
        result.append((lon, lat))
        previous = lon
    if len(result) < 3:
        return None
    return result, sum(point[0] for point in result) / len(result)


def point_on_segment(
    x: float,
    y: float,
    x_a: float,
    y_a: float,
    x_b: float,
    y_b: float,
    epsilon: float = WORLD_COUNTRY_BOUNDARY_EPSILON,
) -> bool:
    cross = (x - x_a) * (y_b - y_a) - (y - y_a) * (x_b - x_a)
    scale = max(1.0, abs(x_a), abs(y_a), abs(x_b), abs(y_b))
    if abs(cross) > epsilon * scale:
        return False
    return (
        min(x_a, x_b) - epsilon <= x <= max(x_a, x_b) + epsilon
        and min(y_a, y_b) - epsilon <= y <= max(y_a, y_b) + epsilon
    )


def point_in_ring_status(lon: float, lat: float, ring: Sequence[Sequence[Any]]) -> str:
    unwrapped = ring_longitudes_unwrapped(ring)
    if unwrapped is None:
        return "outside"
    points, average_lon = unwrapped
    point_lon = normalize_longitude(lon)
    point_lon += round((average_lon - point_lon) / 360.0) * 360.0
    inside = False
    previous = points[-1]
    for current in points:
        x_a, y_a = previous
        x_b, y_b = current
        if point_on_segment(point_lon, lat, x_a, y_a, x_b, y_b):
            return "boundary"
        if (y_a > lat) != (y_b > lat):
            intersection = x_a + (lat - y_a) * (x_b - x_a) / (y_b - y_a)
            if point_lon < intersection:
                inside = not inside
        previous = current
    return "inside" if inside else "outside"


def point_in_polygon_status(lon: float, lat: float, polygon: Sequence[Any]) -> str:
    if not polygon:
        return "outside"
    exterior = point_in_ring_status(lon, lat, polygon[0])
    if exterior != "inside":
        return exterior
    for hole in polygon[1:]:
        status = point_in_ring_status(lon, lat, hole)
        if status == "boundary":
            return "boundary"
        if status == "inside":
            return "outside"
    return "inside"


def polygon_bbox(polygon: Sequence[Any]) -> tuple[float, float, float, float] | None:
    if not polygon:
        return None
    coordinates = [
        (finite_number(point[0]), finite_number(point[1]))
        for ring in polygon
        if isinstance(ring, Sequence)
        for point in ring
        if isinstance(point, Sequence) and len(point) >= 2
    ]
    valid = [(lon, lat) for lon, lat in coordinates if lon is not None and lat is not None]
    if not valid:
        return None
    return (
        min(float(lon) for lon, _lat in valid),
        min(float(lat) for _lon, lat in valid),
        max(float(lon) for lon, _lat in valid),
        max(float(lat) for _lon, lat in valid),
    )


def world_country_index(
    path: Path,
) -> tuple[list[dict[str, Any]], dict[tuple[int, int], tuple[int, ...]], dict[str, str], dict[str, Any]]:
    features = geojson_features(path)
    country_names = [text((feature.get("properties") or {}).get("name")) for feature in features]
    if any(not name for name in country_names) or len(set(country_names)) != len(country_names):
        raise ValueError("Pinned world country shell requires unique non-empty feature names")
    macroregions = macroregion_country_map(country_names)
    parts: list[dict[str, Any]] = []
    buckets: dict[tuple[int, int], set[int]] = defaultdict(set)
    geometry_counts: Counter[str] = Counter()
    for feature in features:
        country = text((feature.get("properties") or {}).get("name"))
        geometry = feature.get("geometry") or {}
        geometry_counts[text(geometry.get("type")) or "unknown"] += 1
        for polygon in geometry_polygon_parts(geometry):
            bbox = polygon_bbox(polygon)
            if bbox is None:
                continue
            part_index = len(parts)
            parts.append({"country": country, "polygon": polygon})
            min_lon, min_lat, max_lon, max_lat = bbox
            min_lat_bucket = max(0, min(35, math.floor((min_lat + 90.0) / WORLD_COUNTRY_BUCKET_DEGREES)))
            max_lat_bucket = max(0, min(35, math.floor((max_lat + 90.0) / WORLD_COUNTRY_BUCKET_DEGREES)))
            for shift in (-360.0, 0.0, 360.0):
                shifted_min = min_lon + shift
                shifted_max = max_lon + shift
                if shifted_max < -180.0 or shifted_min > 180.0:
                    continue
                min_lon_bucket = max(
                    0,
                    min(71, math.floor((max(-180.0, shifted_min) + 180.0) / WORLD_COUNTRY_BUCKET_DEGREES)),
                )
                max_lon_bucket = max(
                    0,
                    min(71, math.floor((min(180.0, shifted_max) + 180.0) / WORLD_COUNTRY_BUCKET_DEGREES)),
                )
                for lat_bucket in range(min_lat_bucket, max_lat_bucket + 1):
                    for lon_bucket in range(min_lon_bucket, max_lon_bucket + 1):
                        buckets[(lat_bucket, lon_bucket)].add(part_index)
    frozen_buckets = {key: tuple(sorted(value)) for key, value in buckets.items()}
    path_hash = sha256_path(path)
    source = {
        **input_declaration(path, label=f"data/{WORLD_COUNTRIES_FILENAME}"),
        "releaseId": f"world-countries-geojson-sha256-{path_hash[:16]}",
        "releasePolicy": "content_addressed_local_country_shell_no_external_release_invented",
        "featureCount": len(features),
        "polygonPartCount": len(parts),
        "geometryCounts": dict(sorted(geometry_counts.items())),
        "countryProperty": "name",
    }
    return parts, frozen_buckets, macroregions, source


def assign_world_country(
    lat: float,
    lon: float,
    parts: Sequence[Mapping[str, Any]],
    buckets: Mapping[tuple[int, int], Sequence[int]],
    macroregions: Mapping[str, str],
) -> tuple[str, str, str, str, str]:
    if not math.isfinite(lat) or not math.isfinite(lon) or not -90.0 <= lat <= 90.0:
        return "unknown", "unknown", "invalid_coordinate", "none", "invalid_coordinate"
    normalized_lon = normalize_longitude(lon)
    lat_bucket = max(0, min(35, math.floor((lat + 90.0) / WORLD_COUNTRY_BUCKET_DEGREES)))
    lon_bucket = max(0, min(71, math.floor((normalized_lon + 180.0) / WORLD_COUNTRY_BUCKET_DEGREES)))
    inside: set[str] = set()
    boundary: set[str] = set()
    for part_index in buckets.get((lat_bucket, lon_bucket), ()):
        part = parts[part_index]
        status = point_in_polygon_status(normalized_lon, lat, part["polygon"])
        country = str(part["country"])
        if status == "inside":
            inside.add(country)
        elif status == "boundary":
            boundary.add(country)
    if len(inside) == 1 and not (boundary - inside):
        country = next(iter(inside))
        return country, macroregions[country], "world_country_polygon", "high", "inside_country"
    if not inside and len(boundary) == 1:
        country = next(iter(boundary))
        return country, macroregions[country], "world_country_polygon", "medium", "on_boundary"
    if inside or boundary:
        return "unknown", "unknown", "world_country_boundary_ambiguous", "none", "overlapping_boundaries"
    return "unknown", "unknown", "unassigned_ocean_or_boundary_gap", "none", "outside_country_boundaries"


def build_ufo_geography_projection(
    canonical_root: Path,
    source_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    metadata, meta_path, points_path = packed_metadata(canonical_root)
    if (metadata.get("input") or {}).get("row_order") != "input_order":
        raise ValueError("Geography projection requires packed-points input-order metadata")
    row_struct = struct.Struct(str(metadata["struct_format"]))
    fields = {str(field["name"]): index for index, field in enumerate(metadata["fields"])}
    required = {"event_id", "lat", "lon", "coordinate_source_id"}
    if not required <= fields.keys():
        raise ValueError(f"Packed point schema lacks geography fields: {sorted(required - fields.keys())}")
    world_path = source_root / WORLD_COUNTRIES_FILENAME
    parts, buckets, macroregions, world_source = world_country_index(world_path)
    taxonomy_hash = sha256_bytes(canonical_json_bytes({
        key: sorted(values) for key, values in sorted(MACROREGION_COUNTRIES.items())
    }))
    rows: list[dict[str, Any]] = []
    assignment_cache: dict[tuple[float, float], tuple[str, str, str, str, str]] = {}
    status_counts: Counter[str] = Counter()
    country_counts: Counter[str] = Counter()
    macroregion_counts: Counter[str] = Counter()
    with points_path.open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as mapped:
        for point_row_index, packed in enumerate(row_struct.iter_unpack(mapped)):
            lat = float(packed[fields["lat"]])
            lon = normalize_longitude(float(packed[fields["lon"]]))
            coordinate_source = lookup(
                metadata,
                "coordinate_sources",
                packed[fields["coordinate_source_id"]],
            )
            coordinate_evidence = (
                "source_coordinates" if coordinate_source == "raw_latlong"
                else "generalized_coordinates" if coordinate_source == "geocoded"
                else "unknown"
            )
            coordinate_key = (round(lat, 7), round(lon, 7))
            assignment = assignment_cache.get(coordinate_key)
            if assignment is None:
                assignment = assign_world_country(lat, lon, parts, buckets, macroregions)
                assignment_cache[coordinate_key] = assignment
            country, macroregion, assignment_source, confidence, boundary_status = assignment
            rows.append({
                "pointRowIndex": point_row_index,
                "eventId": int(packed[fields["event_id"]]),
                "countryCode": country,
                "macroregionCode": macroregion,
                "assignmentSourceCode": assignment_source,
                "assignmentConfidenceCode": confidence,
                "boundaryStatusCode": boundary_status,
                "coordinateEvidenceCode": coordinate_evidence,
            })
            status_counts[boundary_status] += 1
            country_counts[country] += 1
            macroregion_counts[macroregion] += 1
    packed_rows = int(metadata["row_count"])
    if len(rows) != packed_rows or any(row["pointRowIndex"] != index for index, row in enumerate(rows)):
        raise ValueError("Geography projection is not aligned to packed-points input order")
    assigned = packed_rows - country_counts["unknown"]
    source = {
        "pointsMetadata": input_declaration(meta_path, label="data/canonical_web/points_meta.json"),
        "pointsBinary": input_declaration(points_path, label="data/canonical_web/points.bin"),
        "worldCountries": world_source,
        "macroregionTaxonomy": {
            "releaseId": "ufo-analysis-macroregion-v1",
            "sha256": taxonomy_hash,
            "countryCount": len(macroregions),
            "labels": sorted(MACROREGION_COUNTRIES),
            "policy": "broad_un_m49_like_source_balancing_regions_not_geopolitical_adjudication",
        },
        "policy": {
            "rowOrder": "packed_points_input_order_mapped_catalog_subsequence",
            "runtimeVerification": "contiguous_point_row_index_and_event_id_fail_closed",
            "assignmentMethod": "point_in_pinned_country_polygon_with_boundary_fail_closed",
            "coordinateClassesSeparated": True,
            "oceanAndBoundaryGaps": "unknown",
            "countryDensityIsIncidence": False,
            "chronologySegmentsRead": False,
        },
        "counts": {
            "rows": len(rows),
            "uniqueCoordinateMarkers": len(assignment_cache),
            "countryAssigned": assigned,
            "countryUnknown": country_counts["unknown"],
            "byBoundaryStatus": dict(sorted(status_counts.items())),
            "byMacroregion": dict(sorted(macroregion_counts.items())),
        },
        "readiness": {
            "status": "ready_descriptive",
            "gates": [
                readiness_gate(
                    "geography_row_alignment",
                    "Mapped point rows align with the served catalog",
                    "mapped packed-point rows",
                    applicability="all_geography_outputs",
                    status="ready_descriptive",
                    input_n=packed_rows,
                    passed_n=len(rows),
                    policy_id="packed_points_input_order_mapped_catalog_subsequence_v1",
                ),
                readiness_gate(
                    "country_polygon_assignment",
                    "Country polygon assignment is available",
                    "mapped packed-point rows",
                    applicability="country_and_macroregion_descriptive_outputs",
                    status="ready_descriptive" if assigned else "data_unavailable",
                    input_n=packed_rows,
                    passed_n=assigned,
                    reason_codes=("ocean_or_boundary_gap_rows_remain_unknown",),
                    policy_id="world_country_point_assignment_v1",
                ),
                readiness_gate(
                    "macroregion_assignment",
                    "Assigned countries map to a pinned macroregion",
                    "country-assigned rows",
                    applicability="source_balanced_geography",
                    status="ready_descriptive" if assigned else "data_unavailable",
                    input_n=assigned,
                    passed_n=assigned,
                    policy_id="ufo_analysis_macroregion_v1",
                ),
            ],
            "warnings": [
                "country_shell_is_content_addressed_but_has_no_claimed_external_release_identity",
                "boundary_and_ocean_rows_fail_closed_to_unknown",
                "generalized_markers_are_not_exact_sites",
            ],
        },
    }
    return rows, source


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


def equal_area_strata(lat: float, lon: float) -> tuple[str, str]:
    normalized_lon = normalize_longitude(lon)
    lat_index = min(11, max(0, math.floor(((math.sin(math.radians(lat)) + 1.0) / 2.0) * 12)))
    lon_index = min(23, max(0, math.floor(((normalized_lon + 180.0) / 360.0) * 24)))
    return (
        f"ea12x24:{lat_index}:{lon_index}",
        f"ea6x12:{lat_index // 2}:{lon_index // 2}",
    )


def build_ufo_spatial_projections(
    canonical_root: Path,
) -> tuple[list[dict[str, Any]], list[list[Any]], dict[str, Any]]:
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
    points: list[dict[str, Any]] = []
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
            fine_stratum, coarse_stratum = equal_area_strata(lat, lon)
            point = {
                "eventId": event_id,
                "lat": round(lat, 7),
                "lon": round(lon, 7),
                "ordinal": day,
                "year": date.fromordinal(day).year,
                "sourceCode": source,
                "craftCode": craft,
                "craftConfidenceCode": confidence,
                "sameDayMatchStrengthCode": strength,
                "coordinateEvidenceCode": "source_coordinates",
                "fineSpatialStratumCode": fine_stratum,
                "coarseSpatialStratumCode": coarse_stratum,
                "duplicateLineageCode": "canonical_deduped_event",
            }
            points.append(point)
            coordinate_counts[(round(lat, COORDINATE_PILE_DECIMALS), round(lon, COORDINATE_PILE_DECIMALS))] += 1

    pre_pile_count = len(points)
    pile_keys = {key for key, count in coordinate_counts.items() if count >= COORDINATE_PILE_MIN_SIZE}
    points = [
        point
        for point in points
        if (round(point["lat"], COORDINATE_PILE_DECIMALS), round(point["lon"], COORDINATE_PILE_DECIMALS)) not in pile_keys
    ]
    exclusions["coordinate_pile"] = pre_pile_count - len(points)
    for point in points:
        pile_key = (round(point["lat"], COORDINATE_PILE_DECIMALS), round(point["lon"], COORDINATE_PILE_DECIMALS))
        point["coordinatePileGroup"] = "pile_" + sha256_bytes(canonical_json_bytes(pile_key))[:16]
        point["coordinatePileCount"] = coordinate_counts[pile_key]
        point["fiveYearBand"] = math.floor(point["year"] / 5) * 5
        point["decade"] = math.floor(point["year"] / 10) * 10
    chronological_points = sorted(points, key=lambda point: (point["ordinal"], point["eventId"]))

    bands: dict[int, deque[int]] = defaultdict(deque)
    pairs: list[list[Any]] = []
    for index, point in enumerate(chronological_points):
        event_id = point["eventId"]
        lat = point["lat"]
        lon = point["lon"]
        day = point["ordinal"]
        source = point["sourceCode"]
        band = math.floor(lat)
        for candidate_band in (band - 1, band, band + 1):
            candidates = bands[candidate_band]
            while candidates and day - chronological_points[candidates[0]]["ordinal"] > NEIGHBOR_MAX_DAY_LAG:
                candidates.popleft()
            for candidate_index in candidates:
                other = chronological_points[candidate_index]
                other_id = other["eventId"]
                other_lat = other["lat"]
                other_lon = other["lon"]
                other_day = other["ordinal"]
                other_source = other["sourceCode"]
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
    packed_count = int(metadata["row_count"])
    source_coordinate_count = packed_count - exclusions["not_source_provided_coordinate"]
    exact_day_count = source_coordinate_count - exclusions["date_not_exact_day"]
    confidence_count = exact_day_count - exclusions["craft_confidence_below_medium"]
    suitability_count = confidence_count - exclusions["same_day_suitability_below_medium"]
    recognized_count = suitability_count - exclusions["craft_class_not_recognized"]
    valid_day_count = recognized_count - exclusions["invalid_exact_day"]
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
            "packedRows": packed_count,
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
            "eligiblePointsBySource": dict(sorted(Counter(point["sourceCode"] for point in points).items())),
            "status": "qualified_candidate_pool",
            "gates": [
                readiness_gate(
                    "ufo_neighbor_source_coordinates",
                    "Source-provided report coordinates",
                    "mapped packed-point rows",
                    applicability="point_neighborhood_inference",
                    status="ready_inferential",
                    input_n=packed_count,
                    passed_n=source_coordinate_count,
                    reason_codes=("generalized_coordinates_excluded",),
                    policy_id="ufo_point_neighbor_eligibility_v2",
                ),
                readiness_gate(
                    "ufo_neighbor_exact_day",
                    "Exact-day report dates",
                    "source-coordinate rows",
                    applicability="point_neighborhood_inference",
                    status="ready_inferential",
                    input_n=source_coordinate_count,
                    passed_n=exact_day_count,
                    reason_codes=("non_exact_dates_excluded",),
                    policy_id="ufo_point_neighbor_eligibility_v2",
                ),
                readiness_gate(
                    "ufo_neighbor_craft_confidence",
                    "Medium/high craft confidence",
                    "source-coordinate exact-day rows",
                    applicability="point_neighborhood_inference",
                    status="ready_inferential",
                    input_n=exact_day_count,
                    passed_n=confidence_count,
                    reason_codes=("craft_confidence_below_medium_excluded",),
                    policy_id="ufo_point_neighbor_eligibility_v2",
                ),
                readiness_gate(
                    "ufo_neighbor_same_day_suitability",
                    "Medium/strong same-day suitability",
                    "coordinate-date-confidence qualified rows",
                    applicability="point_neighborhood_inference",
                    status="ready_inferential",
                    input_n=confidence_count,
                    passed_n=suitability_count,
                    reason_codes=("same_day_suitability_below_medium_excluded",),
                    policy_id="ufo_point_neighbor_eligibility_v2",
                ),
                readiness_gate(
                    "ufo_neighbor_recognized_craft",
                    "Recognized single-craft classes",
                    "coordinate-date-confidence-suitability qualified rows",
                    applicability="point_neighborhood_inference",
                    status="ready_inferential",
                    input_n=suitability_count,
                    passed_n=valid_day_count,
                    reason_codes=("configuration_and_noncraft_classes_excluded",),
                    policy_id="ufo_point_neighbor_craft_classes_v1",
                ),
                readiness_gate(
                    "ufo_neighbor_coordinate_piles",
                    "Coordinate pile exclusion",
                    "fully qualified pre-pile rows",
                    applicability="point_neighborhood_inference",
                    status="ready_inferential" if points else "data_unavailable",
                    input_n=valid_day_count,
                    passed_n=len(points),
                    reason_codes=("coordinate_piles_excluded",),
                    policy_id="coordinate_pile_exclusion_v1",
                ),
            ],
            "warnings": [
                "eligible_source_coordinates_are_currently_limited_to_majestic_and_ufocat",
                "source_balancing_and_leave_one_source_out_sensitivity_required",
                "point_neighborhood_association_is_not_observed_travel",
            ],
        },
    }
    points.sort(key=lambda point: point["eventId"])
    return points, pairs, source


def build_neighbor_projection(canonical_root: Path) -> tuple[list[list[Any]], dict[str, Any]]:
    """Compatibility wrapper retained for focused neighbor-builder tests."""
    _points, pairs, source = build_ufo_spatial_projections(canonical_root)
    return pairs, source


def build_required_neighbor_pairs(
    points: Sequence[Mapping[str, Any]],
    required_event_ids: set[int],
) -> list[list[Any]]:
    """Build bounded unordered pairs with at least one required endpoint."""
    event_ids = [int(point["eventId"]) for point in points]
    if len(set(event_ids)) != len(event_ids):
        raise ValueError("Configuration-neighbor endpoint pool contains duplicate event IDs")
    chronological = sorted(points, key=lambda point: (int(point["ordinal"]), int(point["eventId"])))
    bands: dict[int, deque[int]] = defaultdict(deque)
    pairs: list[list[Any]] = []
    for index, point in enumerate(chronological):
        event_id = int(point["eventId"])
        lat = float(point["lat"])
        lon = float(point["lon"])
        day = int(point["ordinal"])
        source = text(point.get("sourceCode")) or "unknown"
        band = math.floor(lat)
        for candidate_band in (band - 1, band, band + 1):
            candidates = bands[candidate_band]
            while candidates and day - int(chronological[candidates[0]]["ordinal"]) > NEIGHBOR_MAX_DAY_LAG:
                candidates.popleft()
            for candidate_index in candidates:
                other = chronological[candidate_index]
                other_id = int(other["eventId"])
                if event_id not in required_event_ids and other_id not in required_event_ids:
                    continue
                distance = haversine_km(lat, lon, float(other["lat"]), float(other["lon"]))
                if distance > NEIGHBOR_MAX_DISTANCE_KM:
                    continue
                left, right = sorted((event_id, other_id))
                pairs.append([
                    left,
                    right,
                    int(round(distance * 100.0)),
                    day - int(other["ordinal"]),
                    source != (text(other.get("sourceCode")) or "unknown"),
                ])
        bands[band].append(index)
    pairs.sort(key=lambda row: (row[0], row[1], row[2], row[3]))
    if len({(row[0], row[1]) for row in pairs}) != len(pairs):
        raise ValueError("Configuration-neighbor artifact contains duplicate unordered pairs")
    if any(row[0] not in required_event_ids and row[1] not in required_event_ids for row in pairs):
        raise ValueError("Configuration-neighbor artifact contains a pair without a configuration endpoint")
    return pairs


def build_ufo_configuration_projections(
    canonical_root: Path,
    craft_points: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[list[Any]], dict[str, Any], dict[str, Any]]:
    metadata, meta_path, points_path = packed_metadata(canonical_root)
    row_struct = struct.Struct(str(metadata["struct_format"]))
    fields = {str(field["name"]): index for index, field in enumerate(metadata["fields"])}
    required = {
        "event_id", "lat", "lon", "sort_date_key", "source_id", "craft_type_id",
        "craft_type_confidence_id", "craft_type_source_id", "same_day_match_strength_id",
        "date_precision_id", "coordinate_source_id",
    }
    if not required <= fields.keys():
        raise ValueError(
            f"Packed point schema lacks configuration fields: {sorted(required - fields.keys())}"
        )
    stages: Counter[str] = Counter()
    exclusions: Counter[str] = Counter()
    candidates: list[dict[str, Any]] = []
    with points_path.open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as mapped:
        for packed in row_struct.iter_unpack(mapped):
            configuration = lookup(metadata, "craft_types", packed[fields["craft_type_id"]])
            if configuration != CONFIGURATION_CLASS:
                exclusions["not_formation_configuration"] += 1
                continue
            stages["formationRows"] += 1
            coordinate_source = lookup(
                metadata,
                "coordinate_sources",
                packed[fields["coordinate_source_id"]],
            )
            if coordinate_source != "raw_latlong":
                exclusions["not_source_provided_coordinate"] += 1
                continue
            stages["sourceCoordinateRows"] += 1
            date_precision = lookup(metadata, "date_precisions", packed[fields["date_precision_id"]])
            if date_precision != "exact_day":
                exclusions["date_not_exact_day"] += 1
                continue
            stages["exactDayRows"] += 1
            confidence = lookup(
                metadata,
                "craft_type_confidences",
                packed[fields["craft_type_confidence_id"]],
            )
            if confidence not in {"high", "medium"}:
                exclusions["configuration_confidence_below_medium"] += 1
                continue
            stages["confidenceRows"] += 1
            strength = lookup(
                metadata,
                "same_day_match_strengths",
                packed[fields["same_day_match_strength_id"]],
            )
            if strength not in {"strong", "medium"}:
                exclusions["same_day_suitability_below_medium"] += 1
                continue
            stages["suitabilityRows"] += 1
            raw_date = int(packed[fields["sort_date_key"]])
            try:
                day_value = date(
                    raw_date // 10000,
                    (raw_date // 100) % 100,
                    raw_date % 100,
                )
            except ValueError:
                exclusions["invalid_exact_day"] += 1
                continue
            stages["validDateRows"] += 1
            lat = float(packed[fields["lat"]])
            lon = normalize_longitude(float(packed[fields["lon"]]))
            fine_stratum, coarse_stratum = equal_area_strata(lat, lon)
            candidates.append({
                "eventId": int(packed[fields["event_id"]]),
                "lat": round(lat, 7),
                "lon": round(lon, 7),
                "ordinal": day_value.toordinal(),
                "year": day_value.year,
                "sourceCode": lookup(metadata, "sources", packed[fields["source_id"]]) or "unknown",
                "configurationCode": CONFIGURATION_CLASS,
                "configurationConfidenceCode": confidence,
                "configurationSourceCode": (
                    lookup(metadata, "craft_type_sources", packed[fields["craft_type_source_id"]])
                    or "unknown"
                ),
                "sameDayMatchStrengthCode": strength,
                "coordinateEvidenceCode": "source_coordinates",
                "fineSpatialStratumCode": fine_stratum,
                "coarseSpatialStratumCode": coarse_stratum,
                "fiveYearBand": math.floor(day_value.year / 5) * 5,
                "decade": math.floor(day_value.year / 10) * 10,
                "duplicateLineageCode": "canonical_deduped_event",
            })
    craft_event_ids = {int(point["eventId"]) for point in craft_points}
    configuration_event_ids = {int(point["eventId"]) for point in candidates}
    if craft_event_ids & configuration_event_ids:
        raise ValueError("Formation/configuration rows must remain separate from recognized craft rows")
    endpoint_pool = [dict(point) for point in craft_points] + candidates
    coordinate_counts: Counter[tuple[float, float]] = Counter(
        (
            round(float(point["lat"]), COORDINATE_PILE_DECIMALS),
            round(float(point["lon"]), COORDINATE_PILE_DECIMALS),
        )
        for point in endpoint_pool
    )
    pile_keys = {
        key for key, count in coordinate_counts.items() if count >= COORDINATE_PILE_MIN_SIZE
    }
    final_endpoints = [
        point for point in endpoint_pool
        if (
            round(float(point["lat"]), COORDINATE_PILE_DECIMALS),
            round(float(point["lon"]), COORDINATE_PILE_DECIMALS),
        ) not in pile_keys
    ]
    final_configuration_ids = {
        int(point["eventId"])
        for point in final_endpoints
        if int(point["eventId"]) in configuration_event_ids
    }
    final_configuration_points = [
        point for point in candidates if int(point["eventId"]) in final_configuration_ids
    ]
    exclusions["coordinate_pile"] = len(candidates) - len(final_configuration_points)
    for point in final_configuration_points:
        pile_key = (
            round(float(point["lat"]), COORDINATE_PILE_DECIMALS),
            round(float(point["lon"]), COORDINATE_PILE_DECIMALS),
        )
        point["coordinatePileGroup"] = "pile_" + sha256_bytes(canonical_json_bytes(pile_key))[:16]
        point["coordinatePileCount"] = coordinate_counts[pile_key]
    final_configuration_points.sort(key=lambda point: int(point["eventId"]))
    pairs = build_required_neighbor_pairs(final_endpoints, final_configuration_ids)
    config_pair_count = sum(
        row[0] in final_configuration_ids and row[1] in final_configuration_ids for row in pairs
    )
    paired_configuration_ids = {
        event_id
        for row in pairs
        for event_id in (row[0], row[1])
        if event_id in final_configuration_ids
    }
    packed_rows = int(metadata["row_count"])
    point_source = {
        "pointsMetadata": input_declaration(meta_path, label="data/canonical_web/points_meta.json"),
        "pointsBinary": input_declaration(points_path, label="data/canonical_web/points.bin"),
        "policy": {
            "configurationClass": CONFIGURATION_CLASS,
            "semanticRole": "configuration_or_multiple_objects_not_single_craft_shape",
            "dumbbellBarbellAlias": False,
            "coordinateSource": "raw_latlong",
            "datePrecision": "exact_day",
            "configurationConfidence": ["medium", "high"],
            "sameDaySuitability": ["medium", "strong"],
            "coordinatePilePool": "qualified_recognized_craft_plus_formation_configuration_endpoints",
            "coordinatePileDecimals": COORDINATE_PILE_DECIMALS,
            "coordinatePileMinimumSize": COORDINATE_PILE_MIN_SIZE,
            "duplicateRole": "canonical_deduped_event",
            "chronologySegmentsRead": False,
        },
        "counts": {
            "packedRows": packed_rows,
            **dict(sorted(stages.items())),
            "eligibleBeforePileExclusion": len(candidates),
            "eligiblePoints": len(final_configuration_points),
            "coordinatePilesExcluded": len(pile_keys),
            "coordinatePileRowsExcluded": exclusions["coordinate_pile"],
            "eligiblePointsBySource": dict(sorted(Counter(
                point["sourceCode"] for point in final_configuration_points
            ).items())),
        },
        "exclusions": dict(sorted(exclusions.items())),
        "readiness": {
            "status": "ready_sensitivity" if final_configuration_points else "data_unavailable",
            "gates": [
                readiness_gate(
                    "configuration_classification",
                    "Formation/configuration classification",
                    "mapped packed-point rows",
                    applicability="configuration_neighborhood_analysis",
                    status="ready_sensitivity" if stages["formationRows"] else "data_unavailable",
                    input_n=packed_rows,
                    passed_n=stages["formationRows"],
                    reason_codes=("formation_is_configuration_not_dumbbell_craft",),
                    policy_id="formation_configuration_semantics_v1",
                ),
                readiness_gate(
                    "configuration_source_coordinates",
                    "Source-provided configuration coordinates",
                    "formation/configuration rows",
                    applicability="configuration_neighborhood_analysis",
                    status="ready_sensitivity" if stages["sourceCoordinateRows"] else "data_unavailable",
                    input_n=stages["formationRows"],
                    passed_n=stages["sourceCoordinateRows"],
                    reason_codes=("generalized_coordinates_excluded",),
                    policy_id="configuration_point_eligibility_v1",
                ),
                readiness_gate(
                    "configuration_exact_day",
                    "Exact-day configuration dates",
                    "source-coordinate configuration rows",
                    applicability="configuration_neighborhood_analysis",
                    status="ready_sensitivity" if stages["exactDayRows"] else "data_unavailable",
                    input_n=stages["sourceCoordinateRows"],
                    passed_n=stages["exactDayRows"],
                    reason_codes=("non_exact_dates_excluded",),
                    policy_id="configuration_point_eligibility_v1",
                ),
                readiness_gate(
                    "configuration_confidence",
                    "Medium/high configuration confidence",
                    "source-coordinate exact-day configuration rows",
                    applicability="configuration_neighborhood_analysis",
                    status="ready_sensitivity" if stages["confidenceRows"] else "data_unavailable",
                    input_n=stages["exactDayRows"],
                    passed_n=stages["confidenceRows"],
                    reason_codes=("configuration_confidence_below_medium_excluded",),
                    policy_id="configuration_point_eligibility_v1",
                ),
                readiness_gate(
                    "configuration_same_day_suitability",
                    "Medium/strong same-day suitability",
                    "coordinate-date-confidence qualified configuration rows",
                    applicability="configuration_neighborhood_analysis",
                    status="ready_sensitivity" if stages["validDateRows"] else "data_unavailable",
                    input_n=stages["confidenceRows"],
                    passed_n=stages["validDateRows"],
                    reason_codes=("same_day_suitability_below_medium_excluded",),
                    policy_id="configuration_point_eligibility_v1",
                ),
                readiness_gate(
                    "configuration_coordinate_piles",
                    "Configuration coordinate pile exclusion",
                    "fully qualified pre-pile configuration rows",
                    applicability="configuration_neighborhood_analysis",
                    status="ready_sensitivity" if final_configuration_points else "data_unavailable",
                    input_n=len(candidates),
                    passed_n=len(final_configuration_points),
                    reason_codes=("coordinate_piles_excluded",),
                    policy_id="configuration_union_coordinate_pile_exclusion_v1",
                ),
            ],
            "warnings": [
                "formation_describes_a_configuration_or_multiple_objects_not_a_dumbbell_craft",
                "configuration_neighborhoods_are_report_point_associations_not_observed_travel",
            ],
        },
    }
    neighbor_source = {
        "policy": {
            "maximumDistanceKm": NEIGHBOR_MAX_DISTANCE_KM,
            "maximumDayLag": NEIGHBOR_MAX_DAY_LAG,
            "pairIdentity": "unique_unordered_event_pair",
            "requiredEndpoint": "formation_configuration",
            "distanceUnit": "decameter",
            "chronologySegmentsRead": False,
        },
        "counts": {
            "eligibleUnionEndpoints": len(final_endpoints),
            "eligibleCraftEndpoints": len(final_endpoints) - len(final_configuration_points),
            "eligibleConfigurationEndpoints": len(final_configuration_points),
            "pairedConfigurationEndpoints": len(paired_configuration_ids),
            "pairs": len(pairs),
            "configurationConfigurationPairs": config_pair_count,
            "configurationCraftPairs": len(pairs) - config_pair_count,
            "crossSourcePairs": sum(bool(row[4]) for row in pairs),
            "pairsWithin25Km7Days": sum(row[2] <= 2500 and row[3] <= 7 for row in pairs),
            "pairsWithin50Km7Days": sum(row[2] <= 5000 and row[3] <= 7 for row in pairs),
            "pairsWithin100Km30Days": len(pairs),
        },
        "readiness": {
            "status": "ready_sensitivity" if pairs else "data_unavailable",
            "gates": [
                readiness_gate(
                    "configuration_neighbor_support",
                    "Configuration endpoints with at least one bounded neighbor",
                    "eligible configuration endpoints",
                    applicability="configuration_neighborhood_analysis",
                    status="ready_sensitivity" if pairs else "data_unavailable",
                    input_n=len(final_configuration_points),
                    passed_n=len(paired_configuration_ids),
                    reason_codes=("unpaired_configuration_endpoints_remain_visible_in_point_artifact",),
                    policy_id="configuration_neighbor_pairs_v1",
                ),
            ],
            "warnings": [
                "pair_artifact_is_unordered_but_runtime_focal_neighbor_estimates_are_directed",
                "chronology_connectors_are_prohibited_inputs",
            ],
        },
    }
    return final_configuration_points, pairs, point_source, neighbor_source


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


def reconcile_input_details(
    canonical_source: Path,
    wanted: set[str],
) -> dict[str, tuple[str, int | None, str]]:
    found: dict[str, tuple[str, int | None, str]] = {}
    with canonical_source.open("rb", buffering=8 * 1024 * 1024) as stream:
        for line in stream:
            input_ids = {match.decode("ascii") for match in CANONICAL_INPUT_ID_RE.findall(line)} & wanted
            if not input_ids:
                continue
            canonical_match = CANONICAL_EVENT_ID_RE.search(line)
            if canonical_match is None:
                raise ValueError("Current canonical row with requested input lineage lacks canonical event ID")
            served_match = SERVED_EVENT_ID_RE.search(line)
            record = json.loads(line)
            source_by_input = {
                text(item.get("canonical_input_id")): text(item.get("source_name")) or "unknown"
                for item in (record.get("source_provenance") or [])
                if isinstance(item, Mapping)
            }
            for input_id in input_ids:
                current = (
                    canonical_match.group(1).decode("ascii"),
                    int(served_match.group(1)) if served_match else None,
                    source_by_input.get(input_id, text(record.get("source_name")) or "unknown"),
                )
                if input_id in found and found[input_id] != current:
                    raise ValueError(f"Canonical input lineage maps to multiple current events: {input_id}")
                found[input_id] = current
    return found


def reconcile_input_ids(canonical_source: Path, wanted: set[str]) -> dict[str, tuple[str, int | None]]:
    return {
        input_id: (details[0], details[1])
        for input_id, details in reconcile_input_details(canonical_source, wanted).items()
    }


def apply_animal_origin_reconciliation(
    rows: list[dict[str, Any]],
    input_mapping: Mapping[str, tuple[str, int | None, str]],
) -> dict[str, int]:
    mapped_inputs = 0
    mapped_records = 0
    for row in rows:
        details = [input_mapping[input_id] for input_id in row.get("originInputIds", []) if input_id in input_mapping]
        row["originUfoEventIds"] = sorted({detail[1] for detail in details if detail[1] is not None})
        row["originPublisherCodes"] = sorted({detail[2] for detail in details if detail[2]})
        mapped_inputs += len(details)
        mapped_records += bool(details)
    return {"mappedInputIds": mapped_inputs, "mappedRecords": mapped_records}


def build_relationship_projection(
    snapshot_rows: list[list[Any]],
    canonical_source: Path,
    animal_incident_to_public: Mapping[str, str],
    crop_ids: set[str],
    input_mapping: Mapping[str, tuple[str, int | None, str]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_indices = {field: index for index, field in enumerate(RELATIONSHIP_SOURCE_ROW_SCHEMA)}
    wanted = {
        input_id
        for row in snapshot_rows
        for input_id in row[source_indices["sourceInputIds"]]
    }
    detailed_mapping = input_mapping or reconcile_input_details(canonical_source, wanted)
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
            current_events = {
                detailed_mapping[input_id][:2]
                for input_id in source_input_ids
                if input_id in detailed_mapping
            }
            if len(current_events) == 1 and len(source_input_ids) == sum(
                input_id in detailed_mapping for input_id in source_input_ids
            ):
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
            "sourceInputIdsReconciled": sum(input_id in detailed_mapping for input_id in wanted),
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
            "gates": [
                readiness_gate(
                    "relationship_descriptive_records",
                    "Explicit and deterministic relationship records",
                    "relationship package rows",
                    applicability="descriptive_relationship_heatmap",
                    status="ready_descriptive" if rows else "data_unavailable",
                    input_n=len(rows),
                    passed_n=len(rows),
                    policy_id="relationship_lane_description_v1",
                ),
                readiness_gate(
                    "relationship_reconciliation",
                    "Relationships reconciled to current records",
                    "relationship package rows",
                    applicability="relationship_reconciliation_heatmap",
                    status="limited",
                    input_n=len(rows),
                    passed_n=sum(
                        row["reconciliationStatusCode"] in {
                            "reconciled_current", "reconciled_unmapped_ufo"
                        }
                        for row in rows
                    ),
                    reason_codes=("unresolved_subjects_and_objects_quarantined",),
                    policy_id="canonical_input_lineage_reconciliation_v1",
                ),
                readiness_gate(
                    "relationship_inference",
                    "Analyst-adjudicated independent relationships",
                    "relationship package rows",
                    applicability="relationship_association_inference",
                    status="blocked",
                    input_n=len(rows),
                    passed_n=0,
                    reason_codes=(
                        "animal_exact_coordinate_contract_unavailable",
                        "relationships_not_analyst_adjudicated_for_inference",
                    ),
                    policy_id="relationship_inference_gate_v2",
                ),
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


def shifted_year_ordinal(ordinal: int, year_offset: int) -> int:
    value = date.fromordinal(int(ordinal))
    target_year = value.year + int(year_offset)
    try:
        shifted = value.replace(year=target_year)
    except ValueError:
        # February 29 controls use the last valid February day, preserving
        # season without silently dropping leap-day context records.
        shifted = value.replace(year=target_year, day=28)
    return shifted.toordinal()


def distance_ring(distance_km: float) -> str:
    if distance_km <= 25.0:
        return "0_25_km"
    if distance_km <= 50.0:
        return "25_50_km"
    if distance_km <= 100.0:
        return "50_100_km"
    return "100_250_km"


def day_lag_band(day_lag: int) -> str:
    absolute = abs(int(day_lag))
    if absolute == 0:
        return "same_day"
    if absolute <= 3:
        return "1_3_days"
    if absolute <= 7:
        return "4_7_days"
    return "8_30_days"


def build_context_ufo_neighbor_projection(
    ufo_points: Sequence[Mapping[str, Any]],
    crop_rows: Sequence[Mapping[str, Any]],
    animal_rows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build actual and same-season control point neighborhoods.

    The four control anchors are persisted with the observed candidates so the
    browser can run matched-label permutations and cluster bootstraps without
    repeating a global spatial search.  Chronology connectors are not inputs.
    """
    points_by_day: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for point in ufo_points:
        points_by_day[int(point["ordinal"])].append(point)
    for values in points_by_day.values():
        values.sort(key=lambda point: int(point["eventId"]))

    contexts: list[tuple[str, Mapping[str, Any]]] = []
    contexts.extend(("crop", row) for row in crop_rows if row.get("analysisLaneCode") in {
        "crop_bounded", "crop_locality"
    })
    contexts.extend(("animal", row) for row in animal_rows if row.get("analysisLaneCode") == "animal_public_marker")
    contexts.sort(key=lambda item: (item[0], text(item[1].get("id"))))

    rows: list[dict[str, Any]] = []
    candidate_counts: Counter[str] = Counter()
    excluded_counts: Counter[str] = Counter()
    observed_excluded_counts: Counter[str] = Counter()
    observed_clusters: set[str] = set()
    for domain, context in contexts:
        context_id = text(context.get("id"))
        cluster_id = text(context.get("locationDateClusterId"))
        context_ordinal = int(context["startOrdinal"])
        lat = float(context["lat"])
        lon = float(context["lon"])
        lane = text(context.get("analysisLaneCode"))
        feature = text(context.get("featureGroupCode")) or "unknown"
        uncertainty_km = finite_number(context.get("coordinateUncertaintyKm"))
        origin_event_ids = {int(value) for value in (context.get("originUfoEventIds") or [])}
        origin_publishers = {text(value).lower() for value in (context.get("originPublisherCodes") or [])}
        observed_role = "observed_catalog_date" if domain == "crop" else "observed_reported_date"
        anchors = [(observed_role, context_ordinal)] + [
            (
                f"matched_control_{'plus' if offset > 0 else 'minus'}_{abs(offset)}y",
                shifted_year_ordinal(context_ordinal, offset),
            )
            for offset in CONTEXT_CONTROL_YEAR_OFFSETS
        ]
        for role, anchor_ordinal in anchors:
            rows_before_role = len(rows)
            for ufo_ordinal in range(
                anchor_ordinal - CONTEXT_MAX_DAY_LAG,
                anchor_ordinal + CONTEXT_MAX_DAY_LAG + 1,
            ):
                for point in points_by_day.get(ufo_ordinal, []):
                    # A latitude bound rejects most candidates cheaply and is
                    # safe at the dateline and poles; exact distance follows.
                    if abs(float(point["lat"]) - lat) > CONTEXT_MAX_DISTANCE_KM / 110.5:
                        continue
                    marker_distance = haversine_km(lat, lon, float(point["lat"]), float(point["lon"]))
                    if marker_distance > CONTEXT_MAX_DISTANCE_KM:
                        continue
                    candidate_counts[f"{lane}:{role}"] += 1
                    event_id = int(point["eventId"])
                    origin_ufo_excluded = event_id in origin_event_ids
                    origin_publisher_excluded = domain == "animal" and text(point["sourceCode"]).lower() in origin_publishers
                    if origin_ufo_excluded:
                        excluded_counts["origin_ufo_event"] += 1
                        if role == observed_role:
                            observed_excluded_counts["origin_ufo_event"] += 1
                    if origin_publisher_excluded:
                        excluded_counts["origin_publisher"] += 1
                        if role == observed_role:
                            observed_excluded_counts["origin_publisher"] += 1
                    independent = not origin_ufo_excluded and not origin_publisher_excluded
                    if domain == "animal":
                        uncertainty_class = "public_marker_ambiguous"
                    elif uncertainty_km is None:
                        uncertainty_class = "uncertainty_unavailable"
                    else:
                        at_maximum = classify_uncertain_distance(
                            marker_distance,
                            uncertainty_km,
                            0.0,
                            CONTEXT_MAX_DISTANCE_KM,
                        )
                        uncertainty_class = f"{at_maximum}_at_250km"
                    signed_lag = int(point["ordinal"]) - anchor_ordinal
                    rows.append({
                        "contextDomainCode": domain,
                        "contextLaneCode": lane,
                        "contextId": context_id,
                        "contextClusterId": cluster_id,
                        "contextOrdinal": context_ordinal,
                        "ufoEventId": event_id,
                        "distanceDecameters": int(round(marker_distance * 100.0)),
                        "dayLag": signed_lag,
                        "distanceRingCode": distance_ring(marker_distance),
                        "dayLagBandCode": day_lag_band(signed_lag),
                        "uncertaintyClassCode": uncertainty_class,
                        "contextUncertaintyKm": round(uncertainty_km, 6) if uncertainty_km is not None else None,
                        "ufoCraftCode": point["craftCode"],
                        "ufoSourceCode": point["sourceCode"],
                        "ufoFineSpatialStratumCode": point["fineSpatialStratumCode"],
                        "ufoCoarseSpatialStratumCode": point["coarseSpatialStratumCode"],
                        "featureGroupCode": feature,
                        "originUfoExcluded": origin_ufo_excluded,
                        "originPublisherExcluded": origin_publisher_excluded,
                        "independentAssociationEligible": independent,
                        "dateRoleCode": role,
                    })
                    if role == observed_role and independent:
                        observed_clusters.add(cluster_id)
            if len(rows) == rows_before_role:
                rows.append({
                    "contextDomainCode": domain,
                    "contextLaneCode": lane,
                    "contextId": context_id,
                    "contextClusterId": cluster_id,
                    "contextOrdinal": context_ordinal,
                    "ufoEventId": None,
                    "distanceDecameters": None,
                    "dayLag": None,
                    "distanceRingCode": "none",
                    "dayLagBandCode": "none",
                    "uncertaintyClassCode": (
                        "public_marker_ambiguous" if domain == "animal" else "no_neighbor_in_window"
                    ),
                    "contextUncertaintyKm": round(uncertainty_km, 6) if uncertainty_km is not None else None,
                    "ufoCraftCode": "none",
                    "ufoSourceCode": "none",
                    "ufoFineSpatialStratumCode": "none",
                    "ufoCoarseSpatialStratumCode": "none",
                    "featureGroupCode": feature,
                    "originUfoExcluded": False,
                    "originPublisherExcluded": False,
                    "independentAssociationEligible": True,
                    "dateRoleCode": role,
                })
    rows.sort(key=lambda row: (
        row["contextDomainCode"],
        row["contextLaneCode"],
        row["contextId"],
        row["dateRoleCode"],
        -1 if row["ufoEventId"] is None else row["ufoEventId"],
        -1 if row["distanceDecameters"] is None else row["distanceDecameters"],
        -99 if row["dayLag"] is None else row["dayLag"],
    ))
    lane_context_counts = Counter(text(row.get("analysisLaneCode")) for _domain, row in contexts)
    all_context_clusters = {
        text(row.get("locationDateClusterId"))
        for _domain, row in contexts
        if text(row.get("locationDateClusterId"))
    }
    observed_rows = [
        row for row in rows
        if row["dateRoleCode"].startswith("observed_") and row["ufoEventId"] is not None
    ]
    independent_observed = [row for row in observed_rows if row["independentAssociationEligible"]]
    source = {
        "counts": {
            "contextRecords": len(contexts),
            "locationDateClusters": len(all_context_clusters),
            "contextRecordsByLane": dict(sorted(lane_context_counts.items())),
            "rows": len(rows),
            "zeroNeighborSentinelRows": sum(row["ufoEventId"] is None for row in rows),
            "observedRows": len(observed_rows),
            "independentObservedRows": len(independent_observed),
            "independentObservedClusters": len(observed_clusters),
            "rowsByLane": dict(sorted(Counter(row["contextLaneCode"] for row in rows).items())),
            "originExclusions": dict(sorted(excluded_counts.items())),
            "observedOriginExclusions": dict(sorted(observed_excluded_counts.items())),
        },
        "candidateCounts": dict(sorted(candidate_counts.items())),
        "policy": {
            "chronologySegmentsRead": False,
            "maximumDistanceKm": CONTEXT_MAX_DISTANCE_KM,
            "maximumAbsoluteDayLag": CONTEXT_MAX_DAY_LAG,
            "observedUnits": "unique_context_location_date_cluster",
            "controlMethod": "same_location_same_season_year_offsets",
            "controlYearOffsets": list(CONTEXT_CONTROL_YEAR_OFFSETS),
            "matchedPermutationReplicates": 499,
            "clusterBootstrapReplicates": 199,
            "animalMarkersNeverDefiniteNear": True,
            "cropCatalogDatesAreNotFormationDates": True,
            "originatingUfoAndPublisherExcludedFromIndependentLane": True,
        },
        "readiness": {
            "status": "exploratory_candidate_pool",
            "gates": [
                readiness_gate(
                    "context_observed_neighbors",
                    "Observed context-to-UFO marker neighborhoods",
                    "context location-date clusters",
                    applicability="rough_marker_association_analysis",
                    status="ready_sensitivity" if observed_rows else "data_unavailable",
                    input_n=len(all_context_clusters),
                    passed_n=len(observed_clusters),
                    reason_codes=("zero_neighbor_clusters_remain_in_sentinel_rows",),
                    policy_id="context_ufo_marker_neighbors_v1",
                ),
                readiness_gate(
                    "context_independent_neighbors",
                    "Origin- and publisher-independent observed pairs",
                    "observed context-UFO neighbor rows",
                    applicability="independent_rough_marker_association_analysis",
                    status="ready_sensitivity" if independent_observed else "data_unavailable",
                    input_n=len(observed_rows),
                    passed_n=len(independent_observed),
                    reason_codes=("origin_and_publisher_contamination_excluded",),
                    policy_id="context_origin_exclusion_v1",
                ),
            ],
            "warnings": [
                "associations_are_report_marker_to_context_marker_not_site_to_site",
                "crop_time_is_catalog_date_not_established_formation_time",
                "animal_time_and_location_are_public_report_markers",
                "context_association_is_not_causal_and_does_not_establish_authenticity",
            ],
        },
    }
    return rows, source


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
    ufo_spatial_rows, neighbor_rows, neighbor_source = build_ufo_spatial_projections(canonical_root)
    geography_rows, geography_source = build_ufo_geography_projection(canonical_root, source_root)
    (
        configuration_rows,
        configuration_neighbor_rows,
        configuration_source,
        configuration_neighbor_source,
    ) = build_ufo_configuration_projections(canonical_root, ufo_spatial_rows)

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
    relationship_source_indices = {field: index for index, field in enumerate(RELATIONSHIP_SOURCE_ROW_SCHEMA)}
    relationship_input_ids = {
        input_id
        for row in relationship_source_rows
        for input_id in row[relationship_source_indices["sourceInputIds"]]
    }
    animal_input_ids = {
        input_id
        for row in animal_rows
        for input_id in row.get("originInputIds", [])
    }
    input_mapping = reconcile_input_details(canonical_source, relationship_input_ids | animal_input_ids)
    animal_origin_counts = apply_animal_origin_reconciliation(animal_rows, input_mapping)
    animal_source["originReconciliation"] = {
        **animal_origin_counts,
        "inputIds": len(animal_input_ids),
        "unresolvedInputIds": sum(input_id not in input_mapping for input_id in animal_input_ids),
        "policy": "canonical_input_lineage_only_no_string_similarity",
    }
    relationship_rows, relationship_source = build_relationship_projection(
        relationship_source_rows,
        canonical_source,
        animal_incident_to_public,
        {row["id"] for row in crop_rows},
        input_mapping,
    )
    context_neighbor_rows, context_neighbor_source = build_context_ufo_neighbor_projection(
        ufo_spatial_rows,
        crop_rows,
        animal_rows,
    )

    facility_encoded, facility_codes = encoded_projection(facility_rows, FACILITY_ROW_SCHEMA)
    crop_encoded, crop_codes = encoded_projection(crop_rows, CROP_CONTEXT_ROW_SCHEMA)
    animal_encoded, animal_codes = encoded_projection(animal_rows, ANIMAL_CONTEXT_ROW_SCHEMA)
    relationship_encoded, relationship_codes = encoded_projection(
        relationship_rows,
        RELATIONSHIP_ROW_SCHEMA,
    )
    ufo_spatial_encoded, ufo_spatial_codes = encoded_projection(
        ufo_spatial_rows,
        UFO_SPATIAL_POINT_ROW_SCHEMA,
    )
    context_neighbor_encoded, context_neighbor_codes = encoded_projection(
        context_neighbor_rows,
        CONTEXT_UFO_NEIGHBOR_ROW_SCHEMA,
    )
    geography_row_count = len(geography_rows)
    geography_encoded, geography_codes = encoded_projection(
        geography_rows,
        UFO_GEOGRAPHY_ROW_SCHEMA,
    )
    del geography_rows
    configuration_encoded, configuration_codes = encoded_projection(
        configuration_rows,
        UFO_CONFIGURATION_POINT_ROW_SCHEMA,
    )
    artifacts = {
        "animalContextReadiness": write_registered_projection(
            output_root, browser_base_path, "animalContextReadiness",
            "animal_context_readiness.json", animal_encoded, ANIMAL_CONTEXT_ROW_SCHEMA,
            release_id=release_id,
        ),
        "cropContextReadiness": write_registered_projection(
            output_root, browser_base_path, "cropContextReadiness",
            "crop_context_readiness.json", crop_encoded, CROP_CONTEXT_ROW_SCHEMA,
            release_id=release_id,
        ),
        "facilityAnalysis": write_registered_projection(
            output_root, browser_base_path, "facilityAnalysis",
            "facility_analysis_v1.json", facility_encoded, FACILITY_ROW_SCHEMA,
            release_id=release_id,
        ),
        "relationshipReconciliation": write_registered_projection(
            output_root,
            browser_base_path,
            "relationshipReconciliation",
            "relationship_reconciliation.json",
            relationship_encoded,
            RELATIONSHIP_ROW_SCHEMA,
            release_id=release_id,
        ),
        "ufoPointNeighbors": write_registered_projection(
            output_root,
            browser_base_path,
            "ufoPointNeighbors",
            "ufo_point_neighbors_v1.json",
            neighbor_rows,
            NEIGHBOR_ROW_SCHEMA,
            release_id=release_id,
        ),
        "ufoSpatialPoints": write_registered_projection(
            output_root,
            browser_base_path,
            "ufoSpatialPoints",
            "ufo_spatial_points_v2.json",
            ufo_spatial_encoded,
            UFO_SPATIAL_POINT_ROW_SCHEMA,
            release_id=release_id,
        ),
        "contextUfoNeighbors": write_registered_projection(
            output_root,
            browser_base_path,
            "contextUfoNeighbors",
            "context_ufo_neighbors_v1.json",
            context_neighbor_encoded,
            CONTEXT_UFO_NEIGHBOR_ROW_SCHEMA,
            release_id=release_id,
        ),
        "ufoGeography": write_registered_projection(
            output_root,
            browser_base_path,
            "ufoGeography",
            "ufo_geography_v1.json",
            geography_encoded,
            UFO_GEOGRAPHY_ROW_SCHEMA,
            release_id=release_id,
        ),
        "ufoConfigurationPoints": write_registered_projection(
            output_root,
            browser_base_path,
            "ufoConfigurationPoints",
            "ufo_configuration_points_v1.json",
            configuration_encoded,
            UFO_CONFIGURATION_POINT_ROW_SCHEMA,
            release_id=release_id,
        ),
        "ufoConfigurationNeighbors": write_registered_projection(
            output_root,
            browser_base_path,
            "ufoConfigurationNeighbors",
            "ufo_configuration_neighbors_v1.json",
            configuration_neighbor_rows,
            NEIGHBOR_ROW_SCHEMA,
            release_id=release_id,
        ),
    }
    artifacts["ufoGeography"]["binary"] = write_geography_binary_projection(
        output_root,
        browser_base_path,
        geography_encoded,
        artifacts["ufoGeography"],
    )
    snapshot_artifact = write_projection(
        output_root,
        browser_base_path,
        RELATIONSHIP_SNAPSHOT_FILENAME,
        relationship_source_rows,
        RELATIONSHIP_SOURCE_ROW_SCHEMA,
        artifact_id=RELATIONSHIP_SNAPSHOT_CONTRACT["artifactId"],
        release_id=release_id,
        ordering_fields=RELATIONSHIP_SNAPSHOT_CONTRACT["orderingFields"],
        ordering_policy_id=RELATIONSHIP_SNAPSHOT_CONTRACT["orderingPolicyId"],
    )
    snapshot_metadata_artifact = write_document(
        output_root,
        browser_base_path,
        RELATIONSHIP_SNAPSHOT_META_FILENAME,
        relationship_source_meta,
        artifact_id=RELATIONSHIP_SNAPSHOT_METADATA_ARTIFACT_ID,
        release_id=release_id,
    )

    codebooks = {
        "animalContextReadiness": animal_codes,
        "cropContextReadiness": crop_codes,
        "facilityAnalysis": facility_codes,
        "relationshipReconciliation": relationship_codes,
        "ufoSpatialPoints": ufo_spatial_codes,
        "contextUfoNeighbors": context_neighbor_codes,
        "ufoGeography": geography_codes,
        "ufoConfigurationPoints": configuration_codes,
    }
    root_policy = {
        "authenticityAssessments": False,
        "causalInferences": False,
        "chronologySegmentsRead": False,
        "contextProximityFailClosed": True,
        "generalizedCoordinatesKilometerEligible": False,
        "roughMarkerAnalysisEnabled": True,
        "roughMarkerAssociationInferenceEligible": True,
        "roughMarkerDefiniteNearEligible": False,
        "minimumContextEligibleRecordsForInference": 25,
        "pointNeighborhoodsOnly": True,
        "traceMetrics": False,
        "travelMetrics": False,
    }
    dictionary_artifact_hashes = {
        artifact_key: sha256_bytes(canonical_json_bytes(codebook))
        for artifact_key, codebook in sorted(codebooks.items())
    }
    dictionaries = {
        "artifactSha256": dictionary_artifact_hashes,
        "codebooksPath": "#/codes",
        "encoding": "zero_based_integer_index_into_manifest_codebook",
        "sha256": sha256_bytes(canonical_json_bytes(codebooks)),
    }
    artifact_releases = {
        artifact_key: declaration["releaseId"]
        for artifact_key, declaration in sorted(artifacts.items())
    }
    row_ordering_hashes = {
        artifact_key: declaration["rowOrdering"]["sha256"]
        for artifact_key, declaration in sorted(artifacts.items())
    }
    contract_hashes = {
        "artifactDeclarationsSha256": sha256_bytes(canonical_json_bytes(artifacts)),
        "dictionaryCodebooksSha256": dictionaries["sha256"],
        "rootPolicySha256": sha256_bytes(canonical_json_bytes(root_policy)),
    }

    manifest = {
        "artifacts": artifacts,
        "artifactReleases": artifact_releases,
        "codes": codebooks,
        "contractHashes": contract_hashes,
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
            "ufoSpatialPoints": len(ufo_spatial_rows),
            "ufoGeographyRows": geography_row_count,
            "ufoGeographyCountryAssigned": geography_source["counts"]["countryAssigned"],
            "ufoConfigurationPoints": len(configuration_rows),
            "ufoConfigurationNeighborPairs": len(configuration_neighbor_rows),
            "contextUfoNeighborRows": len(context_neighbor_rows),
            "contextObservedNeighborRows": context_neighbor_source["counts"]["observedRows"],
            "contextIndependentObservedRows": context_neighbor_source["counts"]["independentObservedRows"],
            "contextLocationDateClusters": context_neighbor_source["counts"]["locationDateClusters"],
            "cropBoundedAnalysisRecords": sum(row["analysisLaneCode"] == "crop_bounded" for row in crop_rows),
            "cropLocalityAnalysisRecords": sum(row["analysisLaneCode"] == "crop_locality" for row in crop_rows),
            "animalPublicMarkerAnalysisRecords": sum(
                row["analysisLaneCode"] == "animal_public_marker" for row in animal_rows
            ),
        },
        "determinism": {
            "canonicalJson": "utf8_sorted_keys_compact_with_lf",
            "gzipMtime": 0,
            "neighborPairOrder": "left_event_id_right_event_id_distance_day_lag",
            "projectionRowOrder": "stable_id_ascending",
            "contextNeighborOrder": "domain_lane_context_role_ufo_distance_day_lag",
            "contextControlOffsetsYears": list(CONTEXT_CONTROL_YEAR_OFFSETS),
            "geographyRowOrder": "packed_points_input_order_mapped_catalog_subsequence",
            "configurationPointOrder": "event_id_ascending",
            "configurationNeighborOrder": "left_event_id_right_event_id_distance_day_lag",
        },
        "dictionaries": dictionaries,
        "estimatorVersion": ESTIMATOR_VERSION,
        "policy": root_policy,
        "releaseId": release_id,
        "rowOrderingHashes": row_ordering_hashes,
        "manifestVersion": "2.2.0",
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
            "ufoSpatialPoints": {
                "counts": {"rows": len(ufo_spatial_rows)},
                "policy": {
                    "chronologySegmentsRead": False,
                    "endpointFieldsPinned": True,
                    "coordinatePileRowsExcluded": True,
                    "duplicateRole": "canonical_deduped_event",
                },
                "readiness": neighbor_source["readiness"],
            },
            "contextUfoNeighbors": context_neighbor_source,
            "ufoGeography": geography_source,
            "ufoConfigurationPoints": configuration_source,
            "ufoConfigurationNeighbors": configuration_neighbor_source,
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
