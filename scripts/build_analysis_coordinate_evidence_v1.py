"""Build the immutable, provenance-preserving Analysis coordinate sidecar."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Iterable

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from scripts.analysis_coordinate_evidence import (
        COUNTRY_CONSISTENCY_CODES,
        QUALITY_BINS,
        STATUS_CODES,
        normalize_coordinate_evidence,
    )
    from scripts.check_static_country_coordinate_anomalies import (
        explicit_country_from_location,
        point_in_any_bounds,
        review_bounds_for_country,
    )
except ModuleNotFoundError:  # Direct script execution.
    from analysis_coordinate_evidence import (  # type: ignore[no-redef]
        COUNTRY_CONSISTENCY_CODES,
        QUALITY_BINS,
        STATUS_CODES,
        normalize_coordinate_evidence,
    )
    from check_static_country_coordinate_anomalies import (  # type: ignore[no-redef]
        explicit_country_from_location,
        point_in_any_bounds,
        review_bounds_for_country,
    )


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DETAIL_ROOT = REPO_ROOT / "static_bundle" / "data" / "canonical_web" / "event_chunks"
DEFAULT_GEOGRAPHY = REPO_ROOT / "webapp" / "static_public" / "data" / "analysis_v2" / "ufo_geography_v1.json"
DEFAULT_ANALYSIS_MANIFEST = REPO_ROOT / "webapp" / "static_public" / "data" / "analysis_v2" / "manifest.json"
DEFAULT_CONFLICT_REPORT = REPO_ROOT / "data" / "reports" / "entity_resolution_coordinate_conflict_analysis_worklist.json"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "webapp" / "static_public" / "data" / "analysis_coordinate_evidence_v1"
DEFAULT_AUDIT_PATH = REPO_ROOT / "campaign" / "analysis_improvement" / "waves" / "wave-003-coordinate-evidence-repair" / "build_audit.json"

RELEASE_ID = "analysis-coordinate-evidence-v1-20260804"
SCHEMA_ID = "ufo-timeline-analysis-coordinate-evidence-artifacts-v1.0.0"
ASSET_ORIGIN = "https://pub-e9029ab2f6b448daad03d7cde7e15e64.r2.dev"
ASSET_BASE_URL = f"{ASSET_ORIGIN}/releases/{RELEASE_ID}"
EXPECTED_CATALOG_ROWS = 702_893
MINIMUM_NORMALIZED_ROWS = 88_281
MINIMUM_NORMALIZED_CATALOG_PCT = 12.55
MINIMUM_SUPPORTED_SOURCES = 2
MINIMUM_ROWS_PER_SOURCE = 1_000
MAXIMUM_COMPRESSED_ARTIFACT_BYTES = 5_000_000
EVIDENCE_SHARD_ROWS = 25_000
REGION_OR_GROUP_COUNTRY_LABELS = {
    "", "A", "AF", "AS", "AU", "CA", "CN", "EU", "EUR", "NA", "OC", "SA", "US", "USA",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def compact_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def deterministic_gzip(raw: bytes) -> bytes:
    return gzip.compress(raw, compresslevel=9, mtime=0)


def write_raw_and_gzip(output_root: Path, stem: str, value: Any) -> dict[str, Any]:
    raw = compact_json_bytes(value)
    compressed = deterministic_gzip(raw)
    raw_path = output_root / f"{stem}.json"
    gzip_path = output_root / f"{stem}.json.gz"
    raw_path.write_bytes(raw)
    gzip_path.write_bytes(compressed)
    return {
        "rawBytes": len(raw),
        "gzipBytes": len(compressed),
        "rawSha256": sha256_bytes(raw),
        "gzipSha256": sha256_bytes(compressed),
    }


def codebook(values: Iterable[str], *, first: str | None = None) -> tuple[list[str], dict[str, int]]:
    labels = sorted(set(values))
    if first is not None:
        labels = [first] + [label for label in labels if label != first]
    return labels, {label: index for index, label in enumerate(labels)}


def era_for(value: Any) -> str:
    try:
        year = int(str(value or "")[:4])
    except ValueError:
        return "unknown"
    if year < 1945:
        return "pre_1945"
    if year < 1960:
        return "1945_1959"
    if year < 1980:
        return "1960_1979"
    if year < 2000:
        return "1980_1999"
    if year < 2020:
        return "2000_2019"
    return "2020_plus"


def load_macroregions(geography_path: Path, manifest_path: Path) -> tuple[dict[str, str], dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entry = manifest["artifacts"]["ufoGeography"]
    if sha256_file(geography_path) != entry["sha256"]:
        raise ValueError("Pinned geography artifact failed its manifest SHA-256")
    rows = json.loads(geography_path.read_text(encoding="utf-8"))
    codes = manifest["codes"]["ufoGeography"]["macroregion"]
    macroregions = {
        str(row[1]): str(codes[int(row[3])]) if 0 <= int(row[3]) < len(codes) else "unknown"
        for row in rows
    }
    if len(rows) != int(entry["rowCount"]):
        raise ValueError("Pinned geography artifact row count disagrees with its manifest")
    return macroregions, {
        "path": geography_path.relative_to(REPO_ROOT).as_posix(),
        "bytes": geography_path.stat().st_size,
        "sha256": entry["sha256"],
        "rowCount": len(rows),
        "releaseId": entry["releaseId"],
    }


def load_unresolved_conflicts(path: Path) -> tuple[set[str], dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    event_ids: set[str] = set()
    for item in payload.get("items", []):
        summary = item.get("source_summary") if isinstance(item, dict) else None
        for event_id in (summary or {}).get("canonical_event_ids", []):
            if event_id:
                event_ids.add(str(event_id))
    return event_ids, {
        "path": path.relative_to(REPO_ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "reviewItemCount": len(payload.get("items", [])),
        "canonicalEventIds": len(event_ids),
        "readyForCanonicalApply": bool(payload.get("ready_for_canonical_apply")),
        "policy": str(payload.get("analysis_policy") or ""),
    }


def raw_coordinate_values(event: dict[str, Any]) -> tuple[str, str, str, str]:
    raw = event.get("raw_source_row") if isinstance(event.get("raw_source_row"), dict) else {}

    def first(*keys: str) -> str:
        for key in keys:
            value = raw.get(key)
            if value not in (None, ""):
                return str(value)
        return ""

    return (
        first("LATITUDE", "Latitude", "latitude", "lat"),
        first("LONGITUDE", "Longitude", "longitude", "lon", "lng"),
        first("key_vals/LatLong", "LatLong", "coordinates", "Coordinates"),
        first("key_vals/LatLongDMS", "LatLongDMS"),
    )


def explicit_country_for_event(event: dict[str, Any]) -> str | None:
    """Prefer a served specific country label over legacy location tokens.

    UFOCAT commonly stores a macroregion code in ``country`` and therefore
    still requires the pinned location-token parser.  Majestic rows can carry
    a specific served country label; that label prevents an embedded token
    such as ``PNG`` in a Malaysian locality string from being promoted to the
    wrong country.
    """

    served_country = str(event.get("country") or "").strip()
    if served_country.upper() not in REGION_OR_GROUP_COUNTRY_LABELS and len(served_country) > 3:
        return served_country
    return explicit_country_from_location(event.get("location_raw"))


def stable_share_diagnostics(rows: list[tuple[str, str, str, str]], dimension_index: int) -> dict[str, Any]:
    totals = Counter(row[3] for row in rows)
    total_n = len(rows)
    groups = sorted({row[dimension_index] for row in rows if row[dimension_index] != "unknown"})
    holdouts = []
    for group in groups:
        retained = [row for row in rows if row[dimension_index] != group]
        retained_counts = Counter(row[3] for row in retained)
        maximum_shift = max(
            (
                abs(
                    (retained_counts[bin_id] / len(retained) if retained else 0) -
                    (totals[bin_id] / total_n if total_n else 0)
                )
                for bin_id in QUALITY_BINS
            ),
            default=0,
        )
        holdouts.append({
            "heldOut": group,
            "retainedRows": len(retained),
            "maximumAbsoluteShareShift": round(maximum_shift, 8),
        })
    return {"groups": groups, "holdouts": holdouts, "interpretation": "descriptive_sensitivity_not_release_gate"}


def artifact_entry(stem: str, files: dict[str, Any], row_count: int, row_schema: list[str]) -> dict[str, Any]:
    return {
        "artifactId": stem,
        "releaseId": f"{RELEASE_ID}.{stem}",
        "file": f"{ASSET_BASE_URL}/{stem}.json",
        "gzipFile": f"{ASSET_BASE_URL}/{stem}.json.gz",
        "bytes": files["rawBytes"],
        "gzipBytes": files["gzipBytes"],
        "sha256": files["rawSha256"],
        "gzipSha256": files["gzipSha256"],
        "rowCount": row_count,
        "rowSchema": row_schema,
    }


def build(args: argparse.Namespace) -> dict[str, Any]:
    detail_root = Path(args.detail_root).resolve()
    geography_path = Path(args.geography).resolve()
    analysis_manifest_path = Path(args.analysis_manifest).resolve()
    conflict_path = Path(args.conflict_report).resolve()
    output_root = Path(args.output_root).resolve()
    audit_path = Path(args.audit_path).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)

    macroregion_by_event, geography_input = load_macroregions(geography_path, analysis_manifest_path)
    conflict_event_ids, conflict_input = load_unresolved_conflicts(conflict_path)
    chunk_paths = sorted(detail_root.glob("chunk_*.json"))
    if not chunk_paths:
        raise ValueError(f"No canonical detail chunks found under {detail_root}")

    evidence_raw: list[dict[str, Any]] = []
    coordinate_origin_counts: Counter[str] = Counter()
    precision_counts: Counter[str] = Counter()
    source_evidence_counts: Counter[str] = Counter()
    source_typed_counts: Counter[str] = Counter()
    source_quality_counts: dict[str, Counter[str]] = defaultdict(Counter)
    status_counts: Counter[str] = Counter()
    consistency_counts: Counter[str] = Counter()
    quality_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    typed_diagnostics: list[tuple[str, str, str, str]] = []
    risk_counts: Counter[str] = Counter()
    raw_coordinate_text_rows = 0
    explicit_country_rows = 0
    checked_country_rows = 0
    catalog_row_index = 0

    for chunk_path in chunk_paths:
        rows = json.loads(chunk_path.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise ValueError(f"Canonical detail chunk is not an array: {chunk_path}")
        for event in rows:
            coordinate_source = str(event.get("coordinate_source") or "unresolved").strip().lower() or "unresolved"
            precision = str(event.get("location_precision") or "unknown").strip().lower() or "unknown"
            coordinate_origin_counts[coordinate_source] += 1
            precision_counts[precision] += 1
            if coordinate_source == "raw_latlong":
                event_id_value = event.get("event_id")
                event_id = event_id_value if isinstance(event_id_value, int) else str(event_id_value or "")
                canonical_event_id = str(event.get("canonical_event_id") or "")
                if event_id == "" or not canonical_event_id:
                    raise ValueError(f"Source-coordinate catalog row {catalog_row_index} has no stable event identity")
                source = str(event.get("source") or "unknown").strip().lower() or "unknown"
                era = era_for(event.get("sort_date_iso") or event.get("date_iso"))
                macroregion = macroregion_by_event.get(str(event_id), "unknown")
                country = explicit_country_for_event(event)
                bounds = review_bounds_for_country(country) if country else []
                lat = event.get("lat")
                lon = event.get("lon")
                inside_bounds = point_in_any_bounds(float(lat), float(lon), bounds) if bounds and lat is not None and lon is not None else None
                normalized = normalize_coordinate_evidence(
                    coordinate_source=coordinate_source,
                    location_precision=precision,
                    latitude=lat,
                    longitude=lon,
                    explicit_country=country,
                    country_bounds_available=bool(bounds),
                    inside_country_bounds=inside_bounds,
                    unresolved_lineage_conflict=canonical_event_id in conflict_event_ids,
                    duplicate_record_count=event.get("duplicate_record_count"),
                )
                raw_lat, raw_lon, raw_combined, raw_dms = raw_coordinate_values(event)
                if raw_lat or raw_lon or raw_combined or raw_dms:
                    raw_coordinate_text_rows += 1
                if country:
                    explicit_country_rows += 1
                if bounds:
                    checked_country_rows += 1
                if normalized.high_latitude:
                    risk_counts["highLatitude"] += 1
                if normalized.dateline:
                    risk_counts["dateline"] += 1
                if normalized.duplicate_lineage:
                    risk_counts["duplicateLineage"] += 1
                if canonical_event_id in conflict_event_ids:
                    risk_counts["unresolvedLineageConflict"] += 1
                source_evidence_counts[source] += 1
                status_counts[normalized.status] += 1
                consistency_counts[normalized.country_consistency] += 1
                quality_counts[normalized.quality_bin] += 1
                reason_counts[normalized.reason] += 1
                source_quality_counts[source][normalized.quality_bin] += 1
                if normalized.typed:
                    source_typed_counts[source] += 1
                    typed_diagnostics.append((source, era, macroregion, normalized.quality_bin))
                evidence_raw.append({
                    "catalogRowIndex": catalog_row_index,
                    "eventId": event_id,
                    "canonicalEventId": canonical_event_id,
                    "source": source,
                    "era": era,
                    "macroregion": macroregion,
                    "status": normalized.status,
                    "countryConsistency": normalized.country_consistency,
                    "qualityBin": normalized.quality_bin,
                    "reason": normalized.reason,
                    "riskFlags": normalized.risk_flags,
                    "servedLatitude": normalized.latitude,
                    "servedLongitude": normalized.longitude,
                    "coordinateSource": coordinate_source,
                    "locationPrecision": precision,
                    "explicitCountry": country or "",
                    "rawLatitude": raw_lat,
                    "rawLongitude": raw_lon,
                    "rawCoordinate": raw_combined,
                    "rawCoordinateDms": raw_dms,
                    "duplicateRecordCount": int(event.get("duplicate_record_count") or 1),
                })
            catalog_row_index += 1

    if catalog_row_index != EXPECTED_CATALOG_ROWS:
        raise ValueError(f"Served catalog row count changed: {catalog_row_index}/{EXPECTED_CATALOG_ROWS}")

    sources, source_code = codebook((row["source"] for row in evidence_raw), first="unknown")
    eras, era_code = codebook((row["era"] for row in evidence_raw), first="unknown")
    macroregions, macroregion_code = codebook((row["macroregion"] for row in evidence_raw), first="unknown")
    countries, country_code = codebook((row["explicitCountry"] for row in evidence_raw), first="")
    reasons, reason_code = codebook((row["reason"] for row in evidence_raw))
    status_code = {value: index for index, value in enumerate(STATUS_CODES)}
    consistency_code = {value: index for index, value in enumerate(COUNTRY_CONSISTENCY_CODES)}
    quality_code = {value: index for index, value in enumerate(QUALITY_BINS)}

    projection = []
    original_evidence = []
    for row in evidence_raw:
        projection.append([
            row["catalogRowIndex"], row["eventId"], source_code[row["source"]], era_code[row["era"]],
            macroregion_code[row["macroregion"]], status_code[row["status"]],
            consistency_code[row["countryConsistency"]], quality_code[row["qualityBin"]],
            row["riskFlags"], row["servedLatitude"], row["servedLongitude"],
        ])
        original_evidence.append([
            row["catalogRowIndex"], row["eventId"], row["canonicalEventId"], source_code[row["source"]],
            row["servedLatitude"], row["servedLongitude"], row["rawLatitude"], row["rawLongitude"],
            row["rawCoordinate"], row["rawCoordinateDms"], row["coordinateSource"], row["locationPrecision"],
            country_code[row["explicitCountry"]], consistency_code[row["countryConsistency"]],
            status_code[row["status"]], reason_code[row["reason"]], row["riskFlags"], row["duplicateRecordCount"],
        ])

    typed_rows = sum(source_typed_counts.values())
    typed_catalog_pct = (typed_rows / catalog_row_index * 100) if catalog_row_index else 0
    supported_sources = sorted(
        source for source, rows in source_typed_counts.items() if rows >= MINIMUM_ROWS_PER_SOURCE
    )

    artifacts: dict[str, Any] = {}
    payloads: dict[str, Any] = {}
    compressed_sizes: dict[str, int] = {}
    projection_files = write_raw_and_gzip(output_root, "coordinate_evidence_projection_v1", projection)
    artifacts["coordinateEvidenceProjection"] = artifact_entry(
        "coordinate_evidence_projection_v1", projection_files, len(projection),
        ["catalogRowIndex", "eventId", "sourceCode", "eraCode", "macroregionCode", "statusCode", "countryConsistencyCode", "qualityBinCode", "riskFlags", "servedLatitude", "servedLongitude"],
    )
    compressed_sizes["coordinateEvidenceProjection"] = projection_files["gzipBytes"]
    payloads["coordinateEvidenceProjectionRaw"] = {
        "path": "coordinate_evidence_projection_v1.json", "bytes": projection_files["rawBytes"],
        "sha256": projection_files["rawSha256"], "recordCount": len(projection), "r2Only": True,
    }
    payloads["coordinateEvidenceProjectionGzip"] = {
        "path": "coordinate_evidence_projection_v1.json.gz", "bytes": projection_files["gzipBytes"],
        "sha256": projection_files["gzipSha256"], "decodedBytes": projection_files["rawBytes"],
        "recordCount": len(projection), "r2Only": True,
    }

    evidence_keys = []
    for shard_index, start in enumerate(range(0, len(original_evidence), EVIDENCE_SHARD_ROWS)):
        shard = original_evidence[start:start + EVIDENCE_SHARD_ROWS]
        stem = f"coordinate_original_evidence_v1_{shard_index:03d}"
        key = f"originalEvidenceShard{shard_index:03d}"
        files = write_raw_and_gzip(output_root, stem, shard)
        artifacts[key] = artifact_entry(
            stem, files, len(shard),
            ["catalogRowIndex", "eventId", "canonicalEventId", "sourceCode", "servedLatitude", "servedLongitude", "rawLatitude", "rawLongitude", "rawCoordinate", "rawCoordinateDms", "coordinateSource", "locationPrecision", "explicitCountryCode", "countryConsistencyCode", "statusCode", "reasonCode", "riskFlags", "duplicateRecordCount"],
        )
        compressed_sizes[key] = files["gzipBytes"]
        evidence_keys.append(key)
        payloads[f"{key}Raw"] = {
            "path": f"{stem}.json", "bytes": files["rawBytes"], "sha256": files["rawSha256"],
            "recordCount": len(shard), "r2Only": True,
        }
        payloads[f"{key}Gzip"] = {
            "path": f"{stem}.json.gz", "bytes": files["gzipBytes"], "sha256": files["gzipSha256"],
            "decodedBytes": files["rawBytes"], "recordCount": len(shard), "r2Only": True,
        }

    compressed_budget = all(size <= MAXIMUM_COMPRESSED_ARTIFACT_BYTES for size in compressed_sizes.values())
    if not compressed_budget:
        oversized = {key: size for key, size in compressed_sizes.items() if size > MAXIMUM_COMPRESSED_ARTIFACT_BYTES}
        raise ValueError(f"Compressed coordinate artifact budget exceeded: {oversized}")

    material_gates = {
        "minimumNormalizedRows": typed_rows >= MINIMUM_NORMALIZED_ROWS,
        "minimumNormalizedCatalogPct": typed_catalog_pct >= MINIMUM_NORMALIZED_CATALOG_PCT,
        "minimumSupportedSources": len(supported_sources) >= MINIMUM_SUPPORTED_SOURCES,
        "minimumRowsPerSupportedSource": all(source_typed_counts[source] >= MINIMUM_ROWS_PER_SOURCE for source in supported_sources),
        "coordinateOriginsSeparated": coordinate_origin_counts["raw_latlong"] == len(projection),
        "generalizedMarkersRemainSeparate": coordinate_origin_counts["geocoded"] > 0,
        "unresolvedMarkersRemainSeparate": coordinate_origin_counts["unresolved"] > 0,
        "unresolvedConflictsFailClosed": status_counts["unresolved_lineage_conflict"] == risk_counts["unresolvedLineageConflict"],
        "projectionEvidenceParity": len(projection) == len(original_evidence),
        "servedCoordinatesPreserved": all(row[9] is not None and row[10] is not None for row in projection),
        "rawCoordinateTextPreservedWhenPresent": raw_coordinate_text_rows > 0,
        "compressedArtifactBudget": compressed_budget,
    }
    readiness_status = "ready_descriptive" if all(material_gates.values()) else "not_estimable"
    order_hash = sha256_bytes(compact_json_bytes([[row[0], row[1]] for row in projection]))
    manifest = {
        "schemaId": SCHEMA_ID,
        "schemaVersion": 1,
        "manifestVersion": "1.0.0",
        "releaseId": RELEASE_ID,
        "generatedAt": "2026-08-04T00:00:00Z",
        "assetBaseUrl": ASSET_BASE_URL,
        "delivery": {
            "pagesFiles": ["manifest.json"],
            "r2OnlyPaths": [item["path"] for item in payloads.values()],
            "immutablePrefix": f"releases/{RELEASE_ID}",
            "cacheControl": "public, max-age=31536000, immutable",
        },
        "artifacts": artifacts,
        "artifactGroups": {"originalEvidenceShards": evidence_keys},
        "payloads": payloads,
        "codes": {
            "source": sources,
            "era": eras,
            "macroregion": macroregions,
            "explicitCountry": countries,
            "status": list(STATUS_CODES),
            "countryConsistency": list(COUNTRY_CONSISTENCY_CODES),
            "qualityBin": list(QUALITY_BINS),
            "reason": reasons,
            "riskFlags": {"highLatitude": 1, "dateline": 2, "duplicateLineage": 4},
        },
        "rowOrdering": {
            "policyId": "served_catalog_sparse_source_coordinate_subsequence_v1",
            "keyFields": ["catalogRowIndex", "eventId"],
            "sha256": order_hash,
        },
        "inputs": {
            "canonicalManifest": {
                "path": "static_bundle/data/canonical_web/canonical_web_manifest.json",
                "sha256": sha256_file(detail_root.parent / "canonical_web_manifest.json"),
            },
            "geography": geography_input,
            "unresolvedConflictReview": conflict_input,
            "countryReviewPolicy": {
                "path": "scripts/check_static_country_coordinate_anomalies.py",
                "sha256": sha256_file(REPO_ROOT / "scripts" / "check_static_country_coordinate_anomalies.py"),
                "kind": "broad_review_bounds_not_exact_boundaries",
            },
        },
        "policy": {
            "canonicalEventsMutated": False,
            "externalGeocodingUsed": False,
            "narrativeDescriptionsRead": False,
            "coordinateRepairApplied": False,
            "precisionPromotionAllowed": False,
            "generalizedMarkersCountAsSourceCoordinates": False,
            "missingCoordinatesCountAsZero": False,
            "unresolvedConflictsExcluded": True,
            "countryBoundsAreExactBoundaries": False,
            "patternFinderPromotion": False,
            "runtimeCovariates": ["source", "era", "macroregion"],
            "minimumCommonSupport": 0.8,
            "minimumActiveAndReferenceBinN": 20,
        },
        "counts": {
            "catalogRows": catalog_row_index,
            "sourceCoordinateRows": len(projection),
            "typedRows": typed_rows,
            "typedCatalogPct": round(typed_catalog_pct, 6),
            "byCoordinateOrigin": dict(sorted(coordinate_origin_counts.items())),
            "byLocationPrecision": dict(sorted(precision_counts.items())),
            "bySourceEvidence": dict(sorted(source_evidence_counts.items())),
            "bySourceTyped": dict(sorted(source_typed_counts.items())),
            "byStatus": {status: status_counts[status] for status in STATUS_CODES if status_counts[status]},
            "byCountryConsistency": {status: consistency_counts[status] for status in COUNTRY_CONSISTENCY_CODES if consistency_counts[status]},
            "byQualityBin": {key: quality_counts[key] for key in QUALITY_BINS if quality_counts[key]},
            "bySourceQualityBin": {source: dict(sorted(counts.items())) for source, counts in sorted(source_quality_counts.items())},
            "riskFlags": dict(sorted(risk_counts.items())),
            "explicitCountryRows": explicit_country_rows,
            "checkedCountryRows": checked_country_rows,
            "rawCoordinateTextRows": raw_coordinate_text_rows,
            "supportedSources": supported_sources,
        },
        "readiness": {
            "status": readiness_status,
            "assessmentLane": "descriptive_with_runtime_gated_comparisons",
            "materialCriterion": "previously_unavailable_assessment_becomes_estimable",
            "materialGates": material_gates,
            "supportedSources": supported_sources,
            "suppressionPolicy": "Suppress inference when artifact integrity, provenance separation, typed coverage, source support, common support, bin N, or holdout stability fails.",
            "warnings": [
                "Broad country review bounds are conservative QA checks, not exact borders or reverse geocoding.",
                "Generalized public markers and unresolved rows never count as source coordinates.",
                "Coordinate evidence describes catalog provenance and quality, not authenticity, incidence, risk, travel, or causal location relationships.",
            ],
        },
        "negativeControls": {
            "leaveOneSourceOut": stable_share_diagnostics(typed_diagnostics, 0),
            "eraHoldout": stable_share_diagnostics(typed_diagnostics, 1),
            "macroregionHoldout": stable_share_diagnostics(typed_diagnostics, 2),
            "highLatitudeHoldout": {"flaggedRows": risk_counts["highLatitude"]},
            "datelineHoldout": {"flaggedRows": risk_counts["dateline"]},
            "duplicateLineageHoldout": {"flaggedRows": risk_counts["duplicateLineage"]},
            "generalizedMarkerExclusion": {"rows": coordinate_origin_counts["geocoded"]},
            "unresolvedMarkerExclusion": {"rows": coordinate_origin_counts["unresolved"]},
        },
    }
    manifest_path = output_root / "manifest.json"
    manifest_path.write_bytes(compact_json_bytes(manifest))
    audit = {
        "schemaId": "ufo-timeline-analysis-coordinate-evidence-build-audit-v1.0.0",
        "releaseId": RELEASE_ID,
        "status": readiness_status,
        "manifest": {
            "path": manifest_path.relative_to(REPO_ROOT).as_posix(),
            "bytes": manifest_path.stat().st_size,
            "sha256": sha256_file(manifest_path),
        },
        "counts": manifest["counts"],
        "materialGates": material_gates,
        "compressedArtifacts": {"byArtifact": compressed_sizes, "maximumBytesEach": MAXIMUM_COMPRESSED_ARTIFACT_BYTES},
        "topReasons": [{"reason": reason, "rows": count} for reason, count in reason_counts.most_common(20)],
        "artifactHashes": {
            key: {"sha256": value["sha256"], "gzipSha256": value["gzipSha256"]}
            for key, value in artifacts.items()
        },
    }
    audit_path.write_bytes(compact_json_bytes(audit))
    return {
        "ok": readiness_status == "ready_descriptive",
        "status": readiness_status,
        "manifest": str(manifest_path),
        "audit": str(audit_path),
        "counts": manifest["counts"],
        "compressedArtifacts": audit["compressedArtifacts"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--detail-root", default=str(DEFAULT_DETAIL_ROOT))
    parser.add_argument("--geography", default=str(DEFAULT_GEOGRAPHY))
    parser.add_argument("--analysis-manifest", default=str(DEFAULT_ANALYSIS_MANIFEST))
    parser.add_argument("--conflict-report", default=str(DEFAULT_CONFLICT_REPORT))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--audit-path", default=str(DEFAULT_AUDIT_PATH))
    return parser.parse_args()


def main() -> int:
    result = build(parse_args())
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
