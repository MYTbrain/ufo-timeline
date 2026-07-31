"""Validate compact canonical web artifacts before frontend integration.

This is a static-host readiness check, not a browser runtime switch. It verifies
that the compact point index and lazy detail chunks are internally consistent
and records the remaining blocker for replacing eager catalog-shard startup.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from parser.packed_points import SCHEMA_VERSION as PACKED_POINTS_SCHEMA_VERSION


STARTUP_ARTIFACTS = (
    "points.bin",
    "points_meta.json",
    "event_chunk_manifest.json",
    "summary_manifest.json",
    "canonical_web_manifest.json",
)


def check_canonical_web_runtime_readiness(artifact_dir: Path, *, primary_catalog_promoted: bool = False) -> dict[str, Any]:
    manifest_path = artifact_dir / "canonical_web_manifest.json"
    points_meta_path = artifact_dir / "points_meta.json"
    points_bin_path = artifact_dir / "points.bin"
    trace_event_meta_path = artifact_dir / "trace_event_index_meta.json"
    trace_event_bin_path = artifact_dir / "trace_event_index.bin"
    trace_segment_meta_path = artifact_dir / "trace_segments_meta.json"
    trace_segment_bin_path = artifact_dir / "trace_segments.bin"
    trace_aggregate_meta_path = artifact_dir / "trace_aggregate_bins_meta.json"
    trace_aggregate_bin_path = artifact_dir / "trace_aggregate_bins.bin"
    chunk_manifest_path = artifact_dir / "event_chunk_manifest.json"
    summary_manifest_path = artifact_dir / "summary_manifest.json"
    compression_report_path = artifact_dir / "compression_report.json"
    artifact_size_report_path = artifact_dir / "artifact_size_report.json"

    manifest = _read_json(manifest_path)
    points_meta = _read_json(points_meta_path)
    trace_event_meta = _read_json(trace_event_meta_path) if trace_event_meta_path.exists() else {}
    trace_segment_meta = _read_json(trace_segment_meta_path) if trace_segment_meta_path.exists() else {}
    trace_aggregate_meta = _read_json(trace_aggregate_meta_path) if trace_aggregate_meta_path.exists() else {}
    chunk_manifest = _read_json(chunk_manifest_path)
    summary_manifest = _read_json(summary_manifest_path) if summary_manifest_path.exists() else []
    compression_report = _read_json(compression_report_path) if compression_report_path.exists() else None
    artifact_size_report = _read_json(artifact_size_report_path) if artifact_size_report_path.exists() else None

    counts = manifest.get("counts", {}) if isinstance(manifest, dict) else {}
    packed_points = manifest.get("packed_points", {}) if isinstance(manifest, dict) else {}
    packed_trace_events = manifest.get("packed_trace_events", {}) if isinstance(manifest, dict) else {}
    packed_trace_segments = manifest.get("packed_trace_segments", {}) if isinstance(manifest, dict) else {}
    packed_trace_aggregate_bins = manifest.get("packed_trace_aggregate_bins", {}) if isinstance(manifest, dict) else {}
    policy = manifest.get("policy", {}) if isinstance(manifest, dict) else {}

    row_count = int(points_meta.get("row_count", 0))
    bytes_per_row = int(points_meta.get("bytes_per_row", 0))
    expected_points_bytes = row_count * bytes_per_row
    actual_points_bytes = points_bin_path.stat().st_size if points_bin_path.exists() else 0
    trace_event_row_count = int(trace_event_meta.get("row_count", 0))
    trace_event_bytes_per_row = int(trace_event_meta.get("bytes_per_row", 0))
    expected_trace_event_bytes = trace_event_row_count * trace_event_bytes_per_row
    actual_trace_event_bytes = trace_event_bin_path.stat().st_size if trace_event_bin_path.exists() else 0
    trace_segment_row_count = int(trace_segment_meta.get("row_count", 0))
    trace_segment_bytes_per_row = int(trace_segment_meta.get("bytes_per_row", 0))
    expected_trace_segment_bytes = trace_segment_row_count * trace_segment_bytes_per_row
    actual_trace_segment_bytes = trace_segment_bin_path.stat().st_size if trace_segment_bin_path.exists() else 0
    trace_aggregate_row_count = int(trace_aggregate_meta.get("row_count", 0))
    trace_aggregate_bytes_per_row = int(trace_aggregate_meta.get("bytes_per_row", 0))
    expected_trace_aggregate_bytes = trace_aggregate_row_count * trace_aggregate_bytes_per_row
    actual_trace_aggregate_bytes = trace_aggregate_bin_path.stat().st_size if trace_aggregate_bin_path.exists() else 0
    startup_gzip_bytes = _startup_gzip_bytes(compression_report)
    total_gzip_bytes = int(compression_report.get("total_gzip_bytes", 0)) if compression_report else 0
    lazy_detail_gzip_bytes = max(0, total_gzip_bytes - startup_gzip_bytes)

    checks = {
        "manifest_exists": manifest_path.exists(),
        "points_metadata_exists": points_meta_path.exists(),
        "points_binary_exists": points_bin_path.exists(),
        "trace_event_metadata_exists": trace_event_meta_path.exists(),
        "trace_event_binary_exists": trace_event_bin_path.exists(),
        "trace_segment_metadata_exists": trace_segment_meta_path.exists(),
        "trace_segment_binary_exists": trace_segment_bin_path.exists(),
        "trace_aggregate_metadata_exists": trace_aggregate_meta_path.exists(),
        "trace_aggregate_binary_exists": trace_aggregate_bin_path.exists(),
        "event_chunk_manifest_exists": chunk_manifest_path.exists(),
        "summary_manifest_exists": summary_manifest_path.exists(),
        "compression_report_exists": compression_report_path.exists(),
        "packed_schema_version_supported": int(points_meta.get("schema_version", 0)) == PACKED_POINTS_SCHEMA_VERSION,
        "point_row_count_matches_manifest": row_count == int(counts.get("mapped_events", -1)),
        "manifest_point_row_count_matches": row_count == int(packed_points.get("row_count", -1)),
        "packed_binary_byte_length_matches": actual_points_bytes == expected_points_bytes,
        "trace_event_row_count_matches_manifest": trace_event_row_count == int(counts.get("trace_events", -1)),
        "manifest_trace_event_row_count_matches": trace_event_row_count == int(
            packed_trace_events.get("row_count", -1)
        ),
        "trace_event_binary_byte_length_matches": actual_trace_event_bytes == expected_trace_event_bytes,
        "trace_segment_row_count_matches_manifest": trace_segment_row_count == int(counts.get("trace_segments", -1)),
        "manifest_trace_segment_row_count_matches": trace_segment_row_count == int(
            packed_trace_segments.get("row_count", -1)
        ),
        "trace_segment_binary_byte_length_matches": actual_trace_segment_bytes == expected_trace_segment_bytes,
        "trace_aggregate_row_count_matches_manifest": trace_aggregate_row_count == int(
            counts.get("trace_aggregate_bins", -1)
        ),
        "manifest_trace_aggregate_row_count_matches": trace_aggregate_row_count == int(
            packed_trace_aggregate_bins.get("row_count", -1)
        ),
        "trace_aggregate_binary_byte_length_matches": actual_trace_aggregate_bytes == expected_trace_aggregate_bytes,
        "event_chunk_count_matches_manifest": len(chunk_manifest) == int(counts.get("event_chunks", -1)),
        "event_chunk_event_count_matches_manifest": _manifest_event_count(chunk_manifest)
        == int(counts.get("events", -1)),
        "summary_shard_count_matches_manifest": len(summary_manifest) == int(counts.get("summary_shards", -1)),
        "summary_shard_event_count_matches_manifest": _manifest_event_count(summary_manifest)
        == int(counts.get("events", -1)),
        "details_are_lazy": policy.get("detail_chunks_are_lazy_loaded") is True,
        "raw_source_rows_excluded": policy.get("raw_source_rows_included") is False,
        "source_claims_excluded": policy.get("source_claims_included") is False,
        "detail_raw_source_rows_preserved": policy.get("detail_raw_source_rows_included") is True,
        "detail_full_provenance_preserved": policy.get("detail_full_provenance_included") is True,
        "summary_raw_source_rows_excluded": policy.get("summary_raw_source_rows_included") is False,
        "summary_source_claims_excluded": policy.get("summary_source_claims_included") is False,
        "summary_full_provenance_excluded": policy.get("summary_full_provenance_included") is False,
        "gzip_artifacts_present": _gzip_artifacts_present(artifact_dir, compression_report),
    }

    ready_for_startup_preview = all(
        checks[name]
        for name in (
            "manifest_exists",
            "points_metadata_exists",
            "points_binary_exists",
            "packed_schema_version_supported",
            "point_row_count_matches_manifest",
            "packed_binary_byte_length_matches",
            "gzip_artifacts_present",
        )
    )
    ready_for_primary_catalog_prototype = ready_for_startup_preview and all(
        checks[name]
        for name in (
            "summary_manifest_exists",
            "summary_shard_count_matches_manifest",
            "summary_shard_event_count_matches_manifest",
            "event_chunk_event_count_matches_manifest",
            "details_are_lazy",
            "detail_raw_source_rows_preserved",
            "detail_full_provenance_preserved",
            "summary_raw_source_rows_excluded",
            "summary_source_claims_excluded",
            "summary_full_provenance_excluded",
        )
    )
    ready_for_primary_catalog = ready_for_primary_catalog_prototype and primary_catalog_promoted
    runtime_blockers = []
    if ready_for_primary_catalog:
        runtime_blockers = []
    elif ready_for_primary_catalog_prototype:
        runtime_blockers.append(
            "Summary shards are available for a guarded primary-catalog prototype, "
            "but app_config keeps canonicalWebArtifacts.primaryCatalog disabled until an explicit default-promotion decision."
        )
    elif ready_for_startup_preview:
        runtime_blockers.append(
            "Packed startup preview is ready, but summary shards are missing or invalid for primary-catalog experiments."
        )

    return {
        "artifact_dir": str(artifact_dir),
        "status": "ready_for_primary_catalog" if ready_for_primary_catalog else "ready_for_preview" if ready_for_startup_preview else "blocked",
        "checks": checks,
        "counts": {
            "events": counts.get("events", 0),
            "mapped_events": counts.get("mapped_events", 0),
            "event_chunks": counts.get("event_chunks", 0),
            "summary_shards": counts.get("summary_shards", 0),
            "point_rows": row_count,
            "points_bytes": actual_points_bytes,
            "trace_event_rows": trace_event_row_count,
            "trace_event_index_bytes": actual_trace_event_bytes,
            "trace_segment_rows": trace_segment_row_count,
            "trace_segments_bytes": actual_trace_segment_bytes,
            "trace_aggregate_rows": trace_aggregate_row_count,
            "trace_aggregate_bins_bytes": actual_trace_aggregate_bytes,
            "raw_total_mb": _bytes_to_mb(_artifact_total_bytes(artifact_dir, artifact_size_report)),
            "gzip_total_bytes": total_gzip_bytes,
            "gzip_total_mb": _bytes_to_mb(total_gzip_bytes),
            "startup_gzip_bytes": startup_gzip_bytes,
            "startup_gzip_mb": _bytes_to_mb(startup_gzip_bytes),
            "lazy_detail_gzip_bytes": lazy_detail_gzip_bytes,
            "lazy_detail_gzip_mb": _bytes_to_mb(lazy_detail_gzip_bytes),
        },
        "ready_for_startup_preview": ready_for_startup_preview,
        "ready_for_primary_catalog_prototype": ready_for_primary_catalog_prototype,
        "ready_for_primary_catalog": ready_for_primary_catalog,
        "primary_catalog_promoted": primary_catalog_promoted,
        "runtime_blockers": runtime_blockers,
    }


def _manifest_event_count(entries: Any) -> int:
    if not isinstance(entries, list):
        return -1
    total = 0
    for entry in entries:
        if not isinstance(entry, dict):
            return -1
        value = entry.get("event_count")
        if isinstance(value, bool):
            return -1
        try:
            count = int(value)
        except (TypeError, ValueError):
            return -1
        if count < 0:
            return -1
        total += count
    return total


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _gzip_artifacts_present(artifact_dir: Path, compression_report: dict[str, Any] | None) -> bool:
    if not compression_report:
        return False
    for entry in compression_report.get("files", []):
        gzip_path = entry.get("gzip_path")
        if not gzip_path or not (artifact_dir / gzip_path).exists():
            return False
    return True


def _startup_gzip_bytes(compression_report: dict[str, Any] | None) -> int:
    if not compression_report:
        return 0
    startup_paths = set(STARTUP_ARTIFACTS)
    total = 0
    for entry in compression_report.get("files", []):
        if entry.get("path") in startup_paths:
            total += int(entry.get("gzip_bytes", 0))
    return total


def _artifact_total_bytes(artifact_dir: Path, artifact_size_report: dict[str, Any] | None) -> int:
    if artifact_size_report and "total_bytes" in artifact_size_report:
        return int(artifact_size_report["total_bytes"])

    total = 0
    for path in artifact_dir.rglob("*"):
        if path.is_file() and path.suffix != ".gz":
            total += path.stat().st_size
    return total


def _bytes_to_mb(byte_count: int) -> float:
    return round(byte_count / (1024 * 1024), 2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, default=Path("data/canonical_web"))
    parser.add_argument("--output", type=Path, default=Path("data/reports/canonical_web_runtime_readiness.json"))
    parser.add_argument(
        "--primary-catalog-promoted",
        action="store_true",
        help="Mark readiness as default-promoted when primary catalog artifacts are valid.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = check_canonical_web_runtime_readiness(args.artifact_dir, primary_catalog_promoted=args.primary_catalog_promoted)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
