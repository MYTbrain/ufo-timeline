"""Build deterministic, lazy Animal Mutilation Reports web artifacts.

The source GeoJSON remains the scientific handoff. Pages receives only a small
manifest; the compact point index, searchable all-record catalog, and detail
chunks are immutable R2 payloads. The builder accepts either the handoff ZIP or
the GeoJSON directly so a corrected handoff can replace the development input
without changing the browser contract.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import shutil
import zipfile
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


SCHEMA_VERSION = 1
DEFAULT_CHUNK_SIZE = 250
MAX_CHUNK_SIZE = 250
HANDOFF_GEOJSON = "data/animal_mutilations.geojson"
HANDOFF_MANIFEST = "handoff_manifest.json"
IMPORT_MANIFEST = "manifest/animal_mutilations_import_manifest.json"
RELEASE_ID_RE = re.compile(r"^animal-mutilations-v1-\d{8}$")
DATE_PRECISION_CODES = {
    "exact_day": 0,
    "month": 1,
    "year": 2,
    "range": 3,
    "approximate": 4,
    "unknown": 5,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="Animal mutilation GeoJSON")
    source.add_argument("--handoff-zip", type=Path, help="Frozen Timeline handoff ZIP")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--asset-base-url", default="")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    return parser.parse_args()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def validate_text(value: Any, *, field: str, record_id: str) -> str:
    text = str(value or "")
    if any(ord(char) == 0 or ord(char) == 0x7F for char in text):
        raise ValueError(f"Unsafe text in {field}: {record_id}")
    # The accepted v1 handoff contains a few legacy Windows-1252 punctuation
    # code points represented as C1 controls. Normalize those for safe display
    # without changing the source artifact or its lineage hash.
    return "".join(
        bytes([ord(char)]).decode("windows-1252") if 0x80 <= ord(char) <= 0x9F else char
        for char in text
    )


def iso_ordinal(value: Any) -> int | None:
    if not value:
        return None
    try:
        parsed = date.fromisoformat(str(value))
    except ValueError as error:
        raise ValueError(f"Invalid ISO date: {value}") from error
    return (parsed - date(1970, 1, 1)).days


def safe_source_url(value: Any, *, record_id: str) -> str | None:
    if not value:
        return None
    url = str(value)
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError(f"Invalid public source URL: {record_id}")
    host = parsed.hostname.casefold().strip(".")
    if host in {"localhost", "0.0.0.0", "::1"} or host.endswith(".local") or host.startswith("127."):
        raise ValueError(f"Non-public source URL: {record_id}")
    return url


def load_source(input_path: Path | None, handoff_zip: Path | None) -> tuple[dict[str, Any], dict[str, Any]]:
    if handoff_zip:
        handoff_zip_bytes = handoff_zip.read_bytes()
        with zipfile.ZipFile(handoff_zip) as archive:
            handoff_manifest_bytes = archive.read(HANDOFF_MANIFEST)
            handoff = json.loads(handoff_manifest_bytes)
            for path, expected in handoff.get("files", {}).items():
                payload = archive.read(path)
                if len(payload) != int(expected["size_bytes"]) or sha256_bytes(payload) != expected["sha256"]:
                    raise ValueError(f"Handoff payload failed integrity validation: {path}")
            geojson_bytes = archive.read(HANDOFF_GEOJSON)
            source_meta = {
                "handoffSchema": handoff.get("schema_version"),
                "handoffZipSha256": sha256_bytes(handoff_zip_bytes),
                "handoffManifestSha256": sha256_bytes(handoff_manifest_bytes),
                "releaseCommit": handoff.get("release_commit"),
                "seedSourceCommit": handoff.get("seed_source_commit"),
                "sourceGeojsonSha256": sha256_bytes(geojson_bytes),
                "coordinateAudit": {"available": False, "requiredForRelease": True},
            }
            audit_entries = [
                (path, metadata) for path, metadata in handoff.get("files", {}).items()
                if path.startswith("data/")
                if "coordinate" in str(metadata.get("role") or "").casefold()
                and "audit" in str(metadata.get("role") or "").casefold()
            ]
            if len(audit_entries) > 1:
                raise ValueError("Handoff declares multiple coordinate-audit artifacts")
            if audit_entries:
                audit_path, audit_metadata = audit_entries[0]
                audit_bytes = archive.read(audit_path)
                if audit_path.endswith(".jsonl"):
                    rows = [json.loads(line) for line in audit_bytes.splitlines() if line.strip()]
                else:
                    audit_payload = json.loads(audit_bytes)
                    rows = audit_payload.get("records", audit_payload.get("rows", audit_payload))
                    if not isinstance(rows, list):
                        raise ValueError("Coordinate audit does not expose a deterministic record array")
                source_meta["coordinateAudit"] = {
                    "available": True,
                    "requiredForRelease": True,
                    "path": audit_path,
                    "sha256": audit_metadata["sha256"],
                    "recordCount": len(rows),
                }
            if IMPORT_MANIFEST in archive.namelist():
                import_manifest = json.loads(archive.read(IMPORT_MANIFEST))
                source_meta["adapterVersion"] = import_manifest.get("adapter_version")
                if source_meta["coordinateAudit"]["available"]:
                    coordinate_normalization = import_manifest.get("coordinate_normalization") or {}
                    coordinate_audit_identity = coordinate_normalization.get("audit") or {}
                    audit_path = str(source_meta["coordinateAudit"]["path"])
                    audit_name = Path(audit_path).name
                    output = (import_manifest.get("outputs") or {}).get(audit_name)
                    expected_records = (import_manifest.get("counts") or {}).get("coordinate_audit_records")
                    if not output or output.get("sha256") != source_meta["coordinateAudit"]["sha256"]:
                        raise ValueError("Coordinate audit identity is not reconciled in the import manifest")
                    if int(output.get("records", -1)) != int(source_meta["coordinateAudit"]["recordCount"]):
                        raise ValueError("Coordinate audit output count is inconsistent")
                    if expected_records is None or int(expected_records) != int(source_meta["coordinateAudit"]["recordCount"]):
                        raise ValueError("Coordinate audit aggregate count is inconsistent")
                    import_audit_path = str(coordinate_audit_identity.get("path") or "")
                    if not import_audit_path or Path(import_audit_path).name != audit_name:
                        raise ValueError("Coordinate audit path is not authoritative in the import manifest")
                    if coordinate_audit_identity.get("sha256") != source_meta["coordinateAudit"]["sha256"]:
                        raise ValueError("Coordinate audit hash is not authoritative in the import manifest")
                    if int(coordinate_audit_identity.get("record_count", -1)) != int(
                        source_meta["coordinateAudit"]["recordCount"]
                    ):
                        raise ValueError("Coordinate audit record count is not authoritative in the import manifest")
                    correction_count = coordinate_normalization.get("correction_count")
                    semantic_validation_passed = coordinate_normalization.get("semantic_validation_passed")
                    if int(correction_count if correction_count is not None else -1) != 479:
                        raise ValueError("Coordinate audit correction_count must be exactly 479")
                    if semantic_validation_passed is not True:
                        raise ValueError("Coordinate audit semantic validation must pass")
                    handoff_coordinate_normalization = handoff.get("coordinate_normalization") or {}
                    handoff_audit_identity = handoff_coordinate_normalization.get("audit") or {}
                    if (
                        handoff_coordinate_normalization.get("correction_count") != correction_count
                        or handoff_coordinate_normalization.get("semantic_validation_passed") is not True
                        or handoff_audit_identity.get("path") != audit_path
                        or handoff_audit_identity.get("sha256") != source_meta["coordinateAudit"]["sha256"]
                        or int(handoff_audit_identity.get("record_count", -1))
                        != int(source_meta["coordinateAudit"]["recordCount"])
                    ):
                        raise ValueError("Coordinate audit identity is not mirrored by the handoff manifest")
                    source_meta["coordinateAudit"].update({
                        "correctionCount": int(correction_count),
                        "semanticValidationPassed": True,
                        "semanticGeographyValidation": coordinate_normalization.get(
                            "semantic_geography_validation"
                        ),
                        "schemaVersion": (import_manifest.get("schema_versions") or {}).get(
                            "coordinate_normalization_audit"
                        ),
                        "schemaSha256": (import_manifest.get("schema_sha256") or {}).get(
                            "coordinate_normalization_audit"
                        ),
                        "longitudeSignCorrected": int(
                            (import_manifest.get("counts") or {}).get("longitude_sign_corrected", -1)
                        ),
                        "coordinatesUnchanged": int(
                            (import_manifest.get("counts") or {}).get("coordinates_unchanged", -1)
                        ),
                        "coordinatesSuppressedAmbiguous": int(
                            (import_manifest.get("counts") or {}).get("coordinates_suppressed_ambiguous", -1)
                        ),
                        "noPublicGeometry": int(
                            (import_manifest.get("counts") or {}).get("no_public_geometry", -1)
                        ),
                    })
                    if not source_meta["coordinateAudit"]["schemaVersion"] or not source_meta["coordinateAudit"]["schemaSha256"]:
                        raise ValueError("Coordinate audit schema identity is missing")
            return json.loads(geojson_bytes), source_meta
    assert input_path is not None
    raw = input_path.read_bytes()
    return json.loads(raw), {"sourceGeojsonSha256": sha256_bytes(raw)}


def validate_collection(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("type") != "FeatureCollection" or payload.get("name") != "Animal Mutilation Reports":
        raise ValueError("Input is not the Animal Mutilation Reports FeatureCollection")
    if payload.get("trace_eligible") is not False or payload.get("trace_role") != "context_only":
        raise ValueError("Animal records must remain context-only and trace-ineligible")
    if payload.get("causality") != "not_asserted":
        raise ValueError("Animal causality must remain not_asserted")
    if payload.get("relationships") not in (None, []):
        raise ValueError("Animal context layer must not contain relationships")
    features = payload.get("features")
    if not isinstance(features, list):
        raise ValueError("FeatureCollection.features must be an array")
    ids = [str(feature.get("id") or "") for feature in features]
    if any(not record_id.startswith("animal_mutilation:") for record_id in ids):
        raise ValueError("Every feature requires a stable animal_mutilation ID")
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate animal mutilation IDs")
    if any((feature.get("properties") or {}).get("location_precision") != "unknown" for feature in features):
        raise ValueError("Every animal report must retain location_precision=unknown")
    return sorted(features, key=lambda feature: str(feature["id"]))


def write_json_gzip(path: Path, value: Any) -> dict[str, Any]:
    raw = canonical_json_bytes(value)
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(compressed)
    return {
        "path": path.as_posix(),
        "bytes": len(compressed),
        "decodedBytes": len(raw),
        "sha256": sha256_bytes(compressed),
        "r2Only": True,
    }


def write_json(path: Path, value: Any) -> dict[str, Any]:
    raw = canonical_json_bytes(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {"bytes": len(raw), "sha256": sha256_bytes(raw)}


def compact_source_ref(ref: dict[str, Any], record_id: str) -> dict[str, Any]:
    return {
        "sourceId": validate_text(ref.get("source_id"), field="source_id", record_id=record_id),
        "sourceHash": validate_text(ref.get("source_hash"), field="source_hash", record_id=record_id),
        "locator": validate_text(ref.get("locator"), field="locator", record_id=record_id),
        "url": safe_source_url(ref.get("url"), record_id=record_id),
    }


def compact_detail(feature: dict[str, Any]) -> dict[str, Any]:
    record_id = str(feature["id"])
    props = feature.get("properties") or {}
    geometry = feature.get("geometry")
    coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
    if coordinates is not None and (
        geometry.get("type") != "Point" or len(coordinates) != 2 or
        not all(isinstance(value, (int, float)) for value in coordinates)
    ):
        raise ValueError(f"Invalid public geometry: {record_id}")
    for field, expected in {
        "status": "reported_unreviewed",
        "evidence_status": "reported_unreviewed",
        "causality": "not_asserted",
        "trace_role": "context_only",
    }.items():
        if props.get(field) != expected:
            raise ValueError(f"Invalid {field}: {record_id}")
    if props.get("trace_eligible") is not False:
        raise ValueError(f"Trace eligibility is forbidden: {record_id}")
    uncertainty = props.get("uncertainty") or {}
    if bool(uncertainty.get("coordinates_available")) != bool(coordinates is not None):
        raise ValueError(f"Coordinate uncertainty mismatch: {record_id}")
    excerpts = [
        validate_text(item, field="evidence_excerpts", record_id=record_id)
        for item in props.get("evidence_excerpts") or []
    ]
    return {
        "id": record_id,
        "title": validate_text(props.get("title"), field="title", record_id=record_id),
        "claimLabel": validate_text(props.get("claim_label"), field="claim_label", record_id=record_id),
        "summary": validate_text(props.get("summary"), field="summary", record_id=record_id),
        "contentWarning": validate_text(props.get("content_warning"), field="content_warning", record_id=record_id),
        "dateStart": props.get("date_start"),
        "dateEnd": props.get("date_end"),
        "datePrecision": props.get("date_precision"),
        "location": validate_text(props.get("location_label"), field="location_label", record_id=record_id) or None,
        "locationPrecision": props.get("location_precision"),
        "coordinates": [round(float(coordinates[0]), 6), round(float(coordinates[1]), 6)] if coordinates else None,
        "commonNames": list(props.get("normalized_common_names") or []),
        "taxonKeys": list(props.get("reported_taxon_keys") or []),
        "speciesGroups": list(props.get("species_groups") or []),
        "evidenceExcerpts": excerpts,
        "status": props.get("status"),
        "evidenceStatus": props.get("evidence_status"),
        "sourceStatus": props.get("source_status"),
        "privacyLevel": props.get("privacy_level"),
        "uncertainty": uncertainty,
        "sourceIncidentId": props.get("source_incident_id"),
        "sourceIncidentSha256": props.get("source_incident_sha256"),
        "sourceRefs": [compact_source_ref(ref, record_id) for ref in props.get("source_refs") or []],
        "causality": "not_asserted",
        "traceEligible": False,
        "traceRole": "context_only",
    }


def search_text(detail: dict[str, Any]) -> str:
    pieces: list[str] = [
        detail["id"], detail.get("title") or "", detail.get("summary") or "", detail.get("location") or "",
        detail.get("sourceIncidentId") or "",
    ]
    # The catalog is a bounded discovery index, not a second copy of full
    # report excerpts. Detailed public excerpts remain lazy in detail chunks.
    for key in ("commonNames", "taxonKeys", "speciesGroups"):
        pieces.extend(str(item) for item in detail.get(key) or [])
    pieces.extend(str(ref.get("sourceId") or "") for ref in detail.get("sourceRefs") or [])
    return normalize_text(" ".join(pieces)).casefold()


def build(
    *, input_path: Path | None, handoff_zip: Path | None, output_root: Path,
    release_id: str, asset_base_url: str, chunk_size: int,
) -> dict[str, Any]:
    if not RELEASE_ID_RE.fullmatch(release_id):
        raise ValueError("release-id must match animal-mutilations-v1-YYYYMMDD")
    if chunk_size < 1 or chunk_size > MAX_CHUNK_SIZE:
        raise ValueError("detail chunk size must be between 1 and 250")
    immutable_prefix = f"releases/{release_id}/"
    normalized_base = asset_base_url.rstrip("/") + "/" if asset_base_url else ""
    if normalized_base and not urlparse(normalized_base).scheme in {"http", "https"}:
        raise ValueError("asset-base-url must be an HTTP(S) URL")
    if normalized_base and not urlparse(normalized_base).path.endswith("/" + immutable_prefix):
        raise ValueError("asset-base-url must end with the immutable release prefix")

    payload, source_meta = load_source(input_path, handoff_zip)
    features = validate_collection(payload)
    details = [compact_detail(feature) for feature in features]
    species_groups = sorted({group for detail in details for group in detail["speciesGroups"]})
    species_codes = {name: index for index, name in enumerate(species_groups)}
    detail_chunk_by_id = {detail["id"]: index // chunk_size for index, detail in enumerate(details)}

    computed_counts = {
        "records": len(details),
        "mapped": sum(detail["coordinates"] is not None for detail in details),
        "unmapped": sum(detail["coordinates"] is None for detail in details),
        "mappedPositions": len({tuple(detail["coordinates"]) for detail in details if detail["coordinates"]}),
        "exactCoordinates": sum(detail["locationPrecision"] != "unknown" for detail in details),
        "dated": sum(detail["dateStart"] is not None for detail in details),
        "undated": sum(detail["dateStart"] is None for detail in details),
        "exactDay": sum(detail["datePrecision"] == "exact_day" for detail in details),
        "mappedExactDay": sum(
            detail["coordinates"] is not None and detail["datePrecision"] == "exact_day"
            for detail in details
        ),
        "reportedUnreviewed": sum(detail["status"] == "reported_unreviewed" for detail in details),
        "detailChunks": (len(details) + chunk_size - 1) // chunk_size,
    }
    if handoff_zip is not None:
        locked_counts = {
            "records": 1177,
            "mapped": 518,
            "unmapped": 659,
            "mappedPositions": 400,
            "exactCoordinates": 0,
            "dated": 1149,
            "undated": 28,
            "exactDay": 921,
            "mappedExactDay": 339,
            "reportedUnreviewed": 1177,
            "detailChunks": 5,
        }
        if chunk_size != 250 or computed_counts != locked_counts:
            raise ValueError(
                "Frozen Animal Mutilation Reports contract mismatch: "
                f"expected {locked_counts}, observed {computed_counts} with chunk_size={chunk_size}"
            )

    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    detail_files: list[dict[str, Any]] = []
    for start in range(0, len(details), chunk_size):
        chunk = details[start:start + chunk_size]
        relative = Path("details") / f"chunk_{start // chunk_size:03d}.json.gz"
        info = write_json_gzip(output_root / relative, {item["id"]: item for item in chunk})
        info["path"] = relative.as_posix()
        info["recordCount"] = len(chunk)
        detail_files.append(info)

    point_rows: list[list[Any]] = []
    catalog_rows: list[list[Any]] = []
    for detail in details:
        start_ordinal = iso_ordinal(detail["dateStart"])
        end_ordinal = iso_ordinal(detail["dateEnd"])
        precision_code = DATE_PRECISION_CODES.get(str(detail["datePrecision"]), DATE_PRECISION_CODES["unknown"])
        group_codes = [species_codes[name] for name in detail["speciesGroups"]]
        chunk_number = detail_chunk_by_id[detail["id"]]
        coordinates = detail["coordinates"]
        if coordinates:
            point_rows.append([
                detail["id"], coordinates[1], coordinates[0], start_ordinal, end_ordinal,
                precision_code, group_codes, chunk_number,
            ])
        catalog_rows.append([
            detail["id"], detail["title"], detail["summary"], detail["location"],
            detail["dateStart"], detail["dateEnd"], precision_code, group_codes,
            bool(coordinates), chunk_number, detail["status"], detail["commonNames"], search_text(detail),
        ])

    points_info = write_json_gzip(output_root / "points.json.gz", point_rows)
    points_info["path"] = "points.json.gz"
    points_info["recordCount"] = len(point_rows)
    points_info["rowSchema"] = [
        "id", "lat", "lon", "startOrdinal", "endOrdinal", "datePrecisionCode",
        "speciesGroupCodes", "detailChunk",
    ]
    catalog_info = write_json_gzip(output_root / "catalog.json.gz", catalog_rows)
    catalog_info["path"] = "catalog.json.gz"
    catalog_info["recordCount"] = len(catalog_rows)
    catalog_info["rowSchema"] = [
        "id", "title", "summary", "location", "dateStart", "dateEnd", "datePrecisionCode",
        "speciesGroupCodes", "mapped", "detailChunk", "status", "commonNames", "searchText",
    ]
    r2_paths = sorted([points_info["path"], catalog_info["path"], *(item["path"] for item in detail_files)])
    manifest = {
        "schemaVersion": SCHEMA_VERSION,
        "releaseId": release_id,
        "assetBaseUrl": normalized_base,
        "layerName": "Animal Mutilation Reports",
        "sourceSchema": payload.get("schema_version"),
        "source": source_meta,
        "counts": computed_counts,
        "points": points_info,
        "catalog": catalog_info,
        "details": {
            "basePath": "details/",
            "chunkPattern": "chunk_{chunk:03d}.json.gz",
            "chunkSize": chunk_size,
            "files": detail_files,
        },
        "codes": {"datePrecision": DATE_PRECISION_CODES, "speciesGroup": species_codes},
        "delivery": {
            "pagesFiles": ["manifest.json"],
            "immutablePrefix": immutable_prefix,
            "r2OnlyPaths": r2_paths,
        },
        "policy": {
            "causality": "not_asserted",
            "traceEligible": False,
            "traceRole": "context_only",
            "relationshipsEligible": False,
            "craftColorEligible": False,
            "playbackEligible": False,
            "status": "reported_unreviewed",
            "exactCoordinateEligible": False,
            "contentWarningRequired": True,
        },
    }
    write_json(output_root / "manifest.json", manifest)
    return manifest


def main() -> None:
    args = parse_args()
    manifest = build(
        input_path=args.input,
        handoff_zip=args.handoff_zip,
        output_root=args.output,
        release_id=args.release_id,
        asset_base_url=args.asset_base_url,
        chunk_size=args.chunk_size,
    )
    print(json.dumps({"output": str(args.output), "releaseId": manifest["releaseId"], "counts": manifest["counts"]}, indent=2))


if __name__ == "__main__":
    main()
