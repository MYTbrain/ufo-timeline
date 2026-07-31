"""Static bundle generation for hosted static browser delivery."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import shutil
from pathlib import Path
from typing import Any

import requests

from .chronology import enrich_event_with_chronology
from .config import AppConfig
from .packed_points import export_packed_points
from .utils import ensure_parent_dir


CHUNK_SIZE = 2500
CATALOG_SHARD_SIZE = 4000


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _write_text(path: Path, content: str) -> None:
    ensure_parent_dir(path)
    path.write_text(content, encoding="utf-8")


def _copy_tree_contents(source_dir: Path, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    for source_path in source_dir.rglob("*"):
        if source_path.is_dir():
            continue
        relative_path = source_path.relative_to(source_dir)
        target_path = target_dir / relative_path
        ensure_parent_dir(target_path)
        shutil.copyfile(source_path, target_path)


VENDOR_ASSET_SOURCES = {
    "leaflet.css": "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css",
    "leaflet.js": "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js",
    "MarkerCluster.css": "https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css",
    "MarkerCluster.Default.css": "https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css",
    "leaflet.markercluster.js": "https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js",
    "images/layers.png": "https://unpkg.com/leaflet@1.9.4/dist/images/layers.png",
    "images/layers-2x.png": "https://unpkg.com/leaflet@1.9.4/dist/images/layers-2x.png",
    "images/marker-icon.png": "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
    "images/marker-icon-2x.png": "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
    "images/marker-shadow.png": "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
}


def _ensure_vendor_assets(vendor_dir: Path) -> bool:
    session = requests.Session()
    try:
        for relative_path, url in VENDOR_ASSET_SOURCES.items():
            target = vendor_dir / relative_path
            if target.exists():
                continue
            ensure_parent_dir(target)
            response = session.get(url, timeout=30)
            response.raise_for_status()
            target.write_bytes(response.content)
        return True
    except requests.RequestException:
        return False


def _browser_catalog_entry(event: dict[str, Any], chunk_id: str) -> dict[str, Any]:
    # Keep startup catalog shards to fields needed for filtering, map rendering,
    # timeline/playback ordering, and result-card summaries. Full provenance and
    # raw-detail fields remain available through lazy event_chunks.
    return {
        "event_id": event.get("event_id"),
        "chunk_id": chunk_id,
        "date_raw": event.get("date_raw"),
        "sort_date_iso": event.get("sort_date_iso"),
        "date_precision": event.get("date_precision"),
        "location_raw": event.get("location_raw"),
        "source": event.get("source"),
        "type": event.get("type"),
        "coordinate_source": event.get("coordinate_source"),
        "location_precision": event.get("location_precision"),
        "geocode_display_name": event.get("geocode_display_name"),
        "lat": event.get("lat"),
        "lon": event.get("lon"),
        "has_coordinates": event.get("lat") is not None and event.get("lon") is not None,
        "time_sort_kind": event.get("time_sort_kind"),
        "playback_sort_reason": event.get("playback_sort_reason"),
        "playback_sort_key": event.get("playback_sort_key"),
    }


def _tile_providers(config: AppConfig) -> list[dict[str, Any]]:
    providers = [
        {
            "id": "none",
            "label": "No basemap world view",
            "mode": "none",
        }
    ]
    if config.web.tile_url.strip():
        providers.append(
            {
                "id": "configured",
                "label": "Light labeled basemap (hosted tiles)",
                "mode": "tile",
                "url": config.web.tile_url,
                "attribution": config.web.tile_attribution,
            }
        )
    return providers


def build_static_bundle(
    config: AppConfig,
    *,
    normalized_events: list[dict[str, Any]],
    map_events: list[dict[str, Any]],
    unresolved_records: list[dict[str, Any]],
    ranked_unresolved_records: list[dict[str, Any]],
    summary: dict[str, Any],
) -> Path:
    project_root = _project_root()
    template_dir = project_root / "webapp" / "static_public"

    bundle_dir = config.static_bundle_dir
    data_dir = bundle_dir / "data"
    reports_dir = bundle_dir / "reports"
    vendor_dir = bundle_dir / "vendor"
    chunk_dir = data_dir / "event_chunks"
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    bundle_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    vendor_dir.mkdir(parents=True, exist_ok=True)
    chunk_dir.mkdir(parents=True, exist_ok=True)

    _copy_tree_contents(template_dir, bundle_dir)
    _ensure_vendor_assets(vendor_dir)
    _write_text(bundle_dir / ".nojekyll", "")

    prepared_events = [enrich_event_with_chronology(event) for event in normalized_events]
    catalog: list[dict[str, Any]] = []
    packed_point_rows: list[dict[str, Any]] = []
    chunk_manifest: list[dict[str, Any]] = []
    catalog_shard_manifest: list[dict[str, Any]] = []

    for index in range(0, len(prepared_events), CHUNK_SIZE):
        chunk_events = prepared_events[index:index + CHUNK_SIZE]
        chunk_id = f"chunk_{(index // CHUNK_SIZE):03d}"
        chunk_file = f"{chunk_id}.json"
        chunk_manifest.append(
            {
                "id": chunk_id,
                "file": chunk_file,
                "event_count": len(chunk_events),
                "start_event_id": chunk_events[0].get("event_id"),
                "end_event_id": chunk_events[-1].get("event_id"),
            }
        )
        for detail_index, event in enumerate(chunk_events):
            catalog.append(_browser_catalog_entry(event, chunk_id))
            packed_point_rows.append(
                {
                    **event,
                    "chunk_id": chunk_id,
                    "detail_index": detail_index,
                }
            )

        _write_text(
            chunk_dir / chunk_file,
            json.dumps(chunk_events, ensure_ascii=False, separators=(",", ":")),
        )

    catalog_shard_dir = data_dir / "catalog_shards"
    catalog_shard_dir.mkdir(parents=True, exist_ok=True)
    for index in range(0, len(catalog), CATALOG_SHARD_SIZE):
        shard_records = catalog[index:index + CATALOG_SHARD_SIZE]
        shard_id = f"catalog_{(index // CATALOG_SHARD_SIZE):03d}"
        shard_file = f"{shard_id}.json"
        catalog_shard_manifest.append(
            {
                "id": shard_id,
                "file": shard_file,
                "event_count": len(shard_records),
                "start_event_id": shard_records[0].get("event_id"),
                "end_event_id": shard_records[-1].get("event_id"),
            }
        )
        _write_text(
            catalog_shard_dir / shard_file,
            json.dumps(shard_records, ensure_ascii=False, separators=(",", ":")),
        )

    precision_breakdown: dict[str, int] = {}
    for event in prepared_events:
        precision = event.get("location_precision") or "unknown"
        precision_breakdown[precision] = precision_breakdown.get(precision, 0) + 1

    packed_points_metadata = export_packed_points(
        packed_point_rows,
        data_dir,
        chunk_manifest=chunk_manifest,
    )

    app_config_payload = {
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "initialCenter": config.web.initial_center,
        "initialZoom": config.web.initial_zoom,
        "mappedCount": summary.get("map_events", 0),
        "normalizedCount": summary.get("normalized_events", len(prepared_events)),
        "unresolvedCount": summary.get("unresolved_locations", 0),
        "liveGeocodingRan": bool(summary.get("geocoder_live_requests", 0)),
        "tileProviders": _tile_providers(config),
        "defaultTileProvider": "configured" if config.web.tile_url.strip() else "none",
        "reports": {
            "rankedUnresolvedCsv": "./reports/ranked_unresolved_locations.csv",
            "rankedUnresolvedJson": "./reports/ranked_unresolved_locations.json",
            "unresolvedCsv": "./reports/unresolved_locations.csv",
            "unresolvedJson": "./reports/unresolved_locations.json",
        },
        "precisionBreakdown": precision_breakdown,
        "packedPoints": {
            "enabled": True,
            "metadataUrl": "./data/points_meta.json",
            "binaryUrl": "./data/points.bin",
            "schemaVersion": packed_points_metadata.get("schema_version"),
            "rowCount": packed_points_metadata.get("row_count"),
            "bytesPerRow": packed_points_metadata.get("bytes_per_row"),
            "mapLayerMode": "all",
            "startupPreview": True,
            "startupPreviewMaxPoints": 80000,
        },
        "canonicalWebArtifacts": {
            "enabled": False,
            "manifestUrl": "./data/canonical_web/canonical_web_manifest.json",
            "chunkManifestUrl": "./data/canonical_web/event_chunk_manifest.json",
            "eventChunksBaseUrl": "./data/canonical_web/event_chunks/",
            "summaryManifestUrl": "./data/canonical_web/summary_manifest.json",
            "summaryShardsBaseUrl": "./data/canonical_web/summary_shards/",
            "primaryCatalog": False,
            "traceRuntime": False,
            "filteredTraceAggregation": False,
        },
    }
    _write_text(data_dir / "app_config.json", json.dumps(app_config_payload, ensure_ascii=False, separators=(",", ":")))
    _write_text(data_dir / "event_catalog_manifest.json", json.dumps(catalog_shard_manifest, ensure_ascii=False, separators=(",", ":")))
    _write_text(data_dir / "event_chunk_manifest.json", json.dumps(chunk_manifest, ensure_ascii=False, separators=(",", ":")))

    _write_text(
        reports_dir / "ranked_unresolved_locations.json",
        json.dumps(ranked_unresolved_records, ensure_ascii=False, indent=2),
    )
    _write_text(
        reports_dir / "unresolved_locations.json",
        json.dumps(unresolved_records, ensure_ascii=False, indent=2),
    )
    if config.ranked_unresolved_locations_csv_path.exists():
        shutil.copyfile(
            config.ranked_unresolved_locations_csv_path,
            reports_dir / "ranked_unresolved_locations.csv",
        )
    if config.unresolved_locations_csv_path.exists():
        shutil.copyfile(
            config.unresolved_locations_csv_path,
            reports_dir / "unresolved_locations.csv",
        )

    return bundle_dir
