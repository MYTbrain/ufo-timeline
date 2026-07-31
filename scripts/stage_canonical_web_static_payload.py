"""Stage selected canonical web artifacts under a static app root.

The normal static bundle intentionally does not include the full canonical web
directory. This helper creates an opt-in payload rooted at ``data/canonical_web``
so guarded browser experiments can load canonical manifests and packed trace
artifacts without copying the full multi-GB detail corpus by default. A separate
full-detail mode is available when production-like event-detail browsing needs
to be staged explicitly.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from parser.utils import ensure_parent_dir, write_json


DEFAULT_ARTIFACT_DIR = Path("data/canonical_web")
DEFAULT_OUTPUT_ROOT = Path("data/canonical_web_static_trace_payload")

BASE_MANIFEST_FILES = (
    "canonical_web_manifest.json",
    "event_chunk_manifest.json",
    "summary_manifest.json",
)

OPTIONAL_REPORT_FILES = (
    "artifact_size_report.json",
    "compression_report.json",
)

ARTIFACT_KEYS_BY_MODE = {
    "trace-runtime": (
        "trace_event_index",
        "trace_event_index_metadata",
        "trace_segments",
        "trace_segments_metadata",
        "trace_aggregate_bins",
        "trace_aggregate_bins_metadata",
    ),
    "startup-preview": (
        "points",
        "points_metadata",
        "trace_event_index",
        "trace_event_index_metadata",
        "trace_segments",
        "trace_segments_metadata",
        "trace_aggregate_bins",
        "trace_aggregate_bins_metadata",
    ),
    "primary-catalog-trace-runtime": (
        "points",
        "points_metadata",
        "trace_event_index",
        "trace_event_index_metadata",
        "trace_segments",
        "trace_segments_metadata",
        "trace_aggregate_bins",
        "trace_aggregate_bins_metadata",
    ),
    "primary-catalog-trace-runtime-with-details": (
        "points",
        "points_metadata",
        "trace_event_index",
        "trace_event_index_metadata",
        "trace_segments",
        "trace_segments_metadata",
        "trace_aggregate_bins",
        "trace_aggregate_bins_metadata",
    ),
}

SUMMARY_SHARD_MODES = {
    "primary-catalog-trace-runtime",
    "primary-catalog-trace-runtime-with-details",
}

DETAIL_CHUNK_MODES = {
    "primary-catalog-trace-runtime-with-details",
}


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=DEFAULT_ARTIFACT_DIR,
        help="Source data/canonical_web artifact directory.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Static root to stage into. Files are copied under output-root/data/canonical_web.",
    )
    parser.add_argument(
        "--mode",
        choices=sorted(ARTIFACT_KEYS_BY_MODE),
        default="trace-runtime",
        help="Artifact subset to stage.",
    )
    parser.add_argument(
        "--no-gzip",
        action="store_true",
        help="Do not copy .gz siblings.",
    )
    return parser


def stage_canonical_web_static_payload(
    *,
    artifact_dir: Path,
    output_root: Path,
    mode: str = "trace-runtime",
    include_gzip: bool = True,
) -> dict[str, Any]:
    artifact_dir = artifact_dir.resolve()
    output_root = output_root.resolve()
    target_dir = output_root / "data" / "canonical_web"
    manifest = _read_json(artifact_dir / "canonical_web_manifest.json")
    artifact_map = manifest.get("artifacts", {}) if isinstance(manifest, dict) else {}
    if mode not in ARTIFACT_KEYS_BY_MODE:
        raise ValueError(f"Unsupported canonical web payload mode: {mode}")

    # Staging modes copy different subsets. Clear the prior payload first so a
    # lighter mode cannot accidentally ship stale full-detail chunks.
    if target_dir.exists():
        shutil.rmtree(target_dir)

    files_to_copy = list(BASE_MANIFEST_FILES)
    for optional_file in OPTIONAL_REPORT_FILES:
        if (artifact_dir / optional_file).exists():
            files_to_copy.append(optional_file)
    for artifact_key in ARTIFACT_KEYS_BY_MODE[mode]:
        artifact_path = artifact_map.get(artifact_key)
        if not isinstance(artifact_path, str) or not artifact_path.strip():
            raise ValueError(f"Canonical web manifest is missing artifact key: {artifact_key}")
        files_to_copy.append(artifact_path.strip())
    if mode in SUMMARY_SHARD_MODES:
        summary_manifest = _read_json(artifact_dir / "summary_manifest.json")
        if not isinstance(summary_manifest, list):
            raise ValueError("summary_manifest.json must be a list for primary-catalog staging.")
        for entry in summary_manifest:
            shard_file = entry.get("file") if isinstance(entry, dict) else None
            if not isinstance(shard_file, str) or not shard_file.strip():
                raise ValueError("summary_manifest.json contains an entry without a file value.")
            files_to_copy.append(str(Path("summary_shards") / shard_file.strip()).replace("\\", "/"))
    if mode in DETAIL_CHUNK_MODES:
        chunk_manifest = _read_json(artifact_dir / "event_chunk_manifest.json")
        if not isinstance(chunk_manifest, list):
            raise ValueError("event_chunk_manifest.json must be a list for full-detail primary-catalog staging.")
        for entry in chunk_manifest:
            chunk_file = entry.get("file") if isinstance(entry, dict) else None
            if not isinstance(chunk_file, str) or not chunk_file.strip():
                raise ValueError("event_chunk_manifest.json contains an entry without a file value.")
            files_to_copy.append(str(Path("event_chunks") / chunk_file.strip()).replace("\\", "/"))

    copied: list[dict[str, Any]] = []
    seen: set[str] = set()
    for relative_file in files_to_copy:
        _copy_artifact_file(
            artifact_dir=artifact_dir,
            target_dir=target_dir,
            relative_file=relative_file,
            copied=copied,
            seen=seen,
        )
        if include_gzip:
            gzip_relative = f"{relative_file}.gz"
            if (artifact_dir / gzip_relative).exists():
                _copy_artifact_file(
                    artifact_dir=artifact_dir,
                    target_dir=target_dir,
                    relative_file=gzip_relative,
                    copied=copied,
                    seen=seen,
                )

    app_config_sync = sync_static_app_config_with_canonical_manifest(
        output_root=output_root,
        manifest=manifest,
        mode=mode,
    )
    legacy_payload_prune = prune_legacy_catalog_payload(output_root=output_root, mode=mode)
    payload_manifest = {
        "schema_version": 1,
        "mode": mode,
        "source_artifact_dir": str(artifact_dir),
        "output_root": str(output_root),
        "target_artifact_dir": str(target_dir),
        "include_gzip": include_gzip,
        "files": copied,
        "file_count": len(copied),
        "total_bytes": sum(item["bytes"] for item in copied),
        "raw_bytes": sum(item["bytes"] for item in copied if not item["path"].endswith(".gz")),
        "gzip_bytes": sum(item["bytes"] for item in copied if item["path"].endswith(".gz")),
        "app_config_sync": app_config_sync,
        "legacy_payload_prune": legacy_payload_prune,
        "usage": {
            "static_path": "data/canonical_web",
            "default_safe": "This payload is opt-in and is not part of the normal static_bundle.zip.",
            "trace_runtime": "Enable canonicalWebArtifacts in a local/test app_config, then use the debug trace artifact helpers.",
            "primary_catalog_trace_runtime": (
                "Mode primary-catalog-trace-runtime includes canonical packed points, summary shards, and trace artifacts "
                "for guarded primaryCatalog + traceRuntime previews, but still omits lazy full-detail event chunks."
            ),
            "primary_catalog_trace_runtime_with_details": (
                "Mode primary-catalog-trace-runtime-with-details includes summary shards, trace artifacts, and lazy "
                "event_chunks for complete event-detail browsing. It is substantially larger and remains opt-in."
            ),
        },
    }
    write_json(output_root / "canonical_web_static_payload_manifest.json", payload_manifest, indent=2)
    return payload_manifest


def prune_legacy_catalog_payload(*, output_root: Path, mode: str) -> dict[str, Any]:
    if mode not in SUMMARY_SHARD_MODES:
        return {"removed": False, "reason": "mode_keeps_legacy_catalog_payload"}
    removed: list[dict[str, Any]] = []
    for relative_dir in (Path("data") / "catalog_shards", Path("data") / "event_chunks"):
        target = output_root / relative_dir
        if not target.exists():
            continue
        file_count = sum(1 for path in target.rglob("*") if path.is_file())
        byte_count = sum(path.stat().st_size for path in target.rglob("*") if path.is_file())
        shutil.rmtree(target)
        removed.append(
            {
                "path": str(relative_dir).replace("\\", "/"),
                "files": file_count,
                "bytes": byte_count,
            }
        )
    return {
        "removed": bool(removed),
        "reason": "canonical_primary_catalog_uses_canonical_summary_shards",
        "directories": removed,
    }


def sync_static_app_config_with_canonical_manifest(
    *,
    output_root: Path,
    manifest: dict[str, Any],
    mode: str,
) -> dict[str, Any]:
    config_path = output_root / "data" / "app_config.json"
    if mode not in SUMMARY_SHARD_MODES or not config_path.exists():
        return {
            "updated": False,
            "reason": "app_config_missing_or_mode_not_primary_catalog",
            "path": str(config_path),
        }
    config = _read_json(config_path)
    if not isinstance(config, dict):
        return {
            "updated": False,
            "reason": "app_config_not_object",
            "path": str(config_path),
        }

    counts = manifest.get("counts") if isinstance(manifest.get("counts"), dict) else {}
    mapped_events = _as_int(counts.get("mapped_events"))
    total_events = _as_int(counts.get("events"))
    if mapped_events is None or total_events is None:
        return {
            "updated": False,
            "reason": "canonical_manifest_missing_counts",
            "path": str(config_path),
        }

    generated_at_utc = datetime.now(timezone.utc).isoformat()
    config["generatedAtUtc"] = generated_at_utc
    config["staticAssetVersion"] = generated_at_utc
    config["mappedCount"] = mapped_events
    config["normalizedCount"] = total_events
    config["unresolvedCount"] = max(0, total_events - mapped_events)
    if isinstance(counts.get("location_precision_counts"), dict):
        config["precisionBreakdown"] = dict(counts["location_precision_counts"])

    packed_points_config = sync_static_startup_packed_points(output_root=output_root, config=config)
    if packed_points_config:
        config["packedPoints"] = packed_points_config

    canonical_config = dict(config.get("canonicalWebArtifacts") or {})
    canonical_config.update(
        {
            "enabled": True,
            "manifestUrl": "./data/canonical_web/canonical_web_manifest.json",
            "chunkManifestUrl": "./data/canonical_web/event_chunk_manifest.json",
            "eventChunksBaseUrl": "./data/canonical_web/event_chunks/",
            "summaryManifestUrl": "./data/canonical_web/summary_manifest.json",
            "summaryShardsBaseUrl": "./data/canonical_web/summary_shards/",
            "primaryCatalog": True,
            "traceRuntime": True,
            "filteredTraceAggregation": True,
            "fullDetails": mode in DETAIL_CHUNK_MODES,
        }
    )
    config["canonicalWebArtifacts"] = canonical_config
    write_json(config_path, config, indent=2)
    return {
        "updated": True,
        "path": str(config_path),
        "mappedCount": mapped_events,
        "normalizedCount": total_events,
        "unresolvedCount": max(0, total_events - mapped_events),
        "packedPointsRowCount": packed_points_config.get("rowCount") if packed_points_config else None,
        "packedPointsSource": packed_points_config.get("metadataUrl") if packed_points_config else None,
    }


def sync_static_startup_packed_points(*, output_root: Path, config: dict[str, Any]) -> dict[str, Any]:
    """Point startup preview at canonical packed points when they are staged."""
    packed_points_config = dict(config.get("packedPoints") or {})
    canonical_meta_path = output_root / "data" / "canonical_web" / "points_meta.json"
    canonical_bin_path = output_root / "data" / "canonical_web" / "points.bin"
    legacy_meta_path = output_root / "data" / "points_meta.json"
    legacy_bin_path = output_root / "data" / "points.bin"
    if canonical_meta_path.exists() and canonical_bin_path.exists():
        metadata_path = canonical_meta_path
        metadata_url = "./data/canonical_web/points_meta.json"
        binary_url = "./data/canonical_web/points.bin"
    elif legacy_meta_path.exists() and legacy_bin_path.exists():
        metadata_path = legacy_meta_path
        metadata_url = "./data/points_meta.json"
        binary_url = "./data/points.bin"
    else:
        return packed_points_config
    metadata = _read_json(metadata_path)
    row_count = _as_int(metadata.get("row_count")) if isinstance(metadata, dict) else None
    bytes_per_row = _as_int(metadata.get("bytes_per_row")) if isinstance(metadata, dict) else None
    schema_version = _as_int(metadata.get("schema_version")) if isinstance(metadata, dict) else None
    packed_points_config.update(
        {
            "enabled": True,
            "metadataUrl": metadata_url,
            "binaryUrl": binary_url,
            "schemaVersion": schema_version or packed_points_config.get("schemaVersion", 2),
            "rowCount": row_count or packed_points_config.get("rowCount"),
            "bytesPerRow": bytes_per_row or packed_points_config.get("bytesPerRow", 72),
            "mapLayerMode": packed_points_config.get("mapLayerMode", "all"),
            "startupPreview": packed_points_config.get("startupPreview", True),
        }
    )
    return packed_points_config


def _copy_artifact_file(
    *,
    artifact_dir: Path,
    target_dir: Path,
    relative_file: str,
    copied: list[dict[str, Any]],
    seen: set[str],
) -> None:
    normalized = relative_file.replace("\\", "/").lstrip("/")
    if normalized in seen:
        return
    source_path = artifact_dir / normalized
    if not source_path.exists() or not source_path.is_file():
        raise FileNotFoundError(f"Canonical web artifact file is missing: {source_path}")
    target_path = target_dir / normalized
    ensure_parent_dir(target_path)
    shutil.copy2(source_path, target_path)
    seen.add(normalized)
    copied.append(
        {
            "path": str(Path("data") / "canonical_web" / normalized).replace("\\", "/"),
            "bytes": target_path.stat().st_size,
        }
    )


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def main() -> int:
    args = build_argument_parser().parse_args()
    summary = stage_canonical_web_static_payload(
        artifact_dir=args.artifact_dir,
        output_root=args.output_root,
        mode=args.mode,
        include_gzip=not args.no_gzip,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
