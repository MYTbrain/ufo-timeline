"""Build lazy, rights-safe Crop Circle Timeline runtime artifacts.

The full interoperability export is a build input only. The browser receives a
compact point index after the layer is enabled and one small detail chunk after
a marker is opened. No source photograph pixels are packaged.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
DEFAULT_CHUNK_SIZE = 250
DATE_PRECISION_CODES = {
    "exact_day": 0,
    "day": 0,
    "month": 1,
    "year": 2,
    "range": 3,
    "approximate": 4,
    "unknown": 4,
}
COORDINATE_CODES = {"exact": 0, "candidate": 1, "locality": 2}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--asset-base-url", default="")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    return parser.parse_args()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def write_json_gzip(path: Path, value: Any) -> dict[str, Any]:
    raw = canonical_json_bytes(value)
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(compressed)
    return {
        "path": path.name,
        "bytes": len(compressed),
        "decoded_bytes": len(raw),
        "sha256": hashlib.sha256(compressed).hexdigest(),
    }


def write_json(path: Path, value: Any) -> dict[str, Any]:
    raw = canonical_json_bytes(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {
        "path": path.name,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def iso_ordinal(value: str | None) -> int | None:
    if not value:
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return (parsed - date(1970, 1, 1)).days


def coordinate_code(event: dict[str, Any]) -> int:
    if event.get("exact_coordinate_eligible"):
        return COORDINATE_CODES["exact"]
    if event.get("marker_confidence") == "provisional":
        return COORDINATE_CODES["candidate"]
    return COORDINATE_CODES["locality"]


def compact_morphology(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record.get("diagram_occurrence_id"),
        "family": record.get("morphology_family"),
        "confidence": record.get("morphology_confidence"),
        "complexity": record.get("complexity_score"),
        "complexityTier": record.get("complexity_tier"),
        "components": record.get("significant_component_count"),
        "holes": record.get("hole_count"),
        "circles": record.get("circle_like_component_count"),
        "discs": record.get("filled_disc_component_count"),
        "rings": record.get("ring_component_count"),
        "concentric": record.get("concentric_components"),
        "alignment": record.get("component_alignment_score"),
        "symmetryOrder": record.get("rotational_symmetry_order"),
        "symmetryScore": record.get("rotational_symmetry_score"),
        "boundaryComplexity": record.get("boundary_complexity"),
        "straightTier": record.get("straight_component_tier"),
        "rank": record.get("diagram_rank_within_entity"),
    }


def compact_source(assertion: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": assertion.get("source_name"),
        "url": assertion.get("source_record_url") or assertion.get("source_url"),
        "page": assertion.get("source_page"),
        "notes": assertion.get("notes"),
    }


def compact_image(image: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": image.get("source_name"),
        "pageUrl": image.get("source_page_url") or image.get("source_record_url"),
        "imageUrl": image.get("image_url") if image.get("embedding_allowed") else None,
        "kind": image.get("image_kind"),
        "rights": image.get("rights_status"),
        "displayPolicy": image.get("pixel_display_policy"),
        "embeddingAllowed": bool(image.get("embedding_allowed")),
    }


def compact_detail(
    event: dict[str, Any],
    morphology: list[dict[str, Any]],
    assertions: list[dict[str, Any]],
    images: list[dict[str, Any]],
) -> dict[str, Any]:
    crop = event.get("crop_circle") or {}
    return {
        "id": event.get("event_hash") or event.get("external_id"),
        "eventId": event.get("event_id"),
        "dateRaw": event.get("date_raw"),
        "dateIso": event.get("date_iso"),
        "endDateIso": event.get("end_date_iso"),
        "datePrecision": event.get("date_precision"),
        "location": event.get("location_raw"),
        "lat": event.get("lat"),
        "lon": event.get("lon"),
        "markerConfidence": event.get("marker_confidence"),
        "exactCoordinate": bool(event.get("exact_coordinate_eligible")),
        "coordinateUncertaintyKm": event.get("coordinate_uncertainty_km"),
        "mappingNotes": event.get("mapping_notes"),
        "description": event.get("description"),
        "place": crop.get("place"),
        "region": crop.get("region"),
        "country": crop.get("country"),
        "crop": crop.get("crop") or crop.get("crop_normalized"),
        "sizeText": crop.get("size_text"),
        "reportedSizeM": crop.get("reported_size_m"),
        "classification": crop.get("classification"),
        "originStatus": crop.get("origin_status"),
        "sourceFamilies": crop.get("source_family_names") or [],
        "assertionCount": crop.get("assertion_count"),
        "multiArchive": bool(crop.get("multi_archive_coverage")),
        "multipleDiagrams": bool(crop.get("possible_multiple_formations_same_entity")) or len(morphology) > 1,
        "morphology": [compact_morphology(item) for item in morphology],
        "sources": [compact_source(item) for item in assertions],
        "images": [compact_image(item) for item in images],
        "links": list(dict.fromkeys([link for link in event.get("links", []) if link])),
        "traceEligible": False,
        "traceRole": "context_only",
    }


def build(
    input_path: Path,
    output_root: Path,
    release_id: str,
    chunk_size: int,
    asset_base_url: str = "",
) -> dict[str, Any]:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "crop-circle-timeline-export-v1.0.0":
        raise ValueError("Unsupported crop-circle export schema")
    if chunk_size < 50:
        raise ValueError("chunk-size must be at least 50")

    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    morphology_by_formation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in payload.get("morphology_occurrences", []):
        morphology_by_formation[str(record.get("formation_id"))].append(record)
    for records in morphology_by_formation.values():
        records.sort(key=lambda item: (item.get("diagram_rank_within_entity") or 999, item.get("diagram_occurrence_id") or ""))

    assertions_by_formation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in payload.get("source_assertions", []):
        assertions_by_formation[str(record.get("formation_id"))].append(record)

    images_by_formation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in payload.get("image_links", []):
        images_by_formation[str(record.get("formation_id"))].append(record)

    events = sorted(payload.get("events", []), key=lambda item: str(item.get("event_hash") or item.get("external_id")))
    detail_records: list[dict[str, Any]] = []
    detail_chunk_by_id: dict[str, int] = {}
    morphology_families = sorted({
        str(record.get("morphology_family"))
        for record in payload.get("morphology_occurrences", [])
        if record.get("morphology_family")
    })
    morphology_codes = {name: index for index, name in enumerate(morphology_families)}

    for index, event in enumerate(events):
        formation_id = str(event.get("event_hash") or event.get("external_id"))
        detail_chunk_by_id[formation_id] = index // chunk_size
        detail_records.append(compact_detail(
            event,
            morphology_by_formation.get(formation_id, []),
            assertions_by_formation.get(formation_id, []),
            images_by_formation.get(formation_id, []),
        ))

    detail_files: list[dict[str, Any]] = []
    for start in range(0, len(detail_records), chunk_size):
        chunk_number = start // chunk_size
        chunk_records = detail_records[start:start + chunk_size]
        relative = Path("details") / f"chunk_{chunk_number:03d}.json.gz"
        info = write_json_gzip(output_root / relative, {record["id"]: record for record in chunk_records})
        info["path"] = str(relative).replace("\\", "/")
        info["record_count"] = len(chunk_records)
        detail_files.append(info)

    point_rows: list[list[Any]] = []
    for event in events:
        if not event.get("has_coordinates"):
            continue
        lat = event.get("lat")
        lon = event.get("lon")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            continue
        formation_id = str(event.get("event_hash") or event.get("external_id"))
        crop = event.get("crop_circle") or {}
        primary_family = crop.get("modal_morphology_family") or "no_diagram"
        point_rows.append([
            formation_id,
            round(float(lat), 6),
            round(float(lon), 6),
            iso_ordinal(event.get("date_iso")),
            iso_ordinal(event.get("end_date_iso") or event.get("date_iso")),
            DATE_PRECISION_CODES.get(str(event.get("date_precision") or "unknown"), DATE_PRECISION_CODES["unknown"]),
            coordinate_code(event),
            morphology_codes.get(str(primary_family), morphology_codes.get("no_diagram", 0)),
            detail_chunk_by_id[formation_id],
        ])

    points_info = write_json_gzip(output_root / "points.json.gz", point_rows)
    manifest = {
        "schemaVersion": SCHEMA_VERSION,
        "releaseId": release_id,
        "assetBaseUrl": asset_base_url.rstrip("/") + "/" if asset_base_url else "",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "sourceSchema": payload.get("schema_version"),
        "sourceCommit": (payload.get("source") or {}).get("commit"),
        "counts": {
            "events": len(events),
            "mapped": len(point_rows),
            "exactCoordinates": sum(1 for row in point_rows if row[6] == COORDINATE_CODES["exact"]),
            "candidateFields": sum(1 for row in point_rows if row[6] == COORDINATE_CODES["candidate"]),
            "localityCentroids": sum(1 for row in point_rows if row[6] == COORDINATE_CODES["locality"]),
            "detailChunks": len(detail_files),
            "openLicenseImageLinks": sum(
                1 for record in payload.get("image_links", []) if record.get("embedding_allowed")
            ),
        },
        "points": {
            **points_info,
            "path": "points.json.gz",
            "rowSchema": [
                "id", "lat", "lon", "startOrdinal", "endOrdinal", "datePrecisionCode",
                "coordinateCode", "morphologyCode", "detailChunk",
            ],
        },
        "details": {
            "basePath": "details/",
            "chunkPattern": "chunk_{chunk:03d}.json.gz",
            "chunkSize": chunk_size,
            "files": detail_files,
        },
        "codes": {
            "datePrecision": DATE_PRECISION_CODES,
            "coordinate": COORDINATE_CODES,
            "morphology": morphology_codes,
        },
        "policy": {
            "traceEligible": False,
            "traceRole": "context_only",
            "photographsPreloaded": False,
            "schematicsAreApproximate": True,
        },
    }
    manifest_info = write_json(output_root / "manifest.json", manifest)
    manifest["manifestBytes"] = manifest_info["bytes"]
    return manifest


def main() -> None:
    args = parse_args()
    manifest = build(args.input, args.output, args.release_id, args.chunk_size, args.asset_base_url)
    print(json.dumps({
        "output": str(args.output),
        "releaseId": manifest["releaseId"],
        "counts": manifest["counts"],
        "pointsGzipBytes": manifest["points"]["bytes"],
        "largestDetailGzipBytes": max(item["bytes"] for item in manifest["details"]["files"]),
    }, indent=2))


if __name__ == "__main__":
    main()
