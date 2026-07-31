import json

from parser.utils import write_json
from scripts.stage_canonical_web_static_payload import stage_canonical_web_static_payload


def test_stage_trace_runtime_payload_copies_only_required_trace_artifacts(tmp_path):
    artifact_dir = tmp_path / "canonical_web"
    output_root = tmp_path / "static_payload"
    artifact_dir.mkdir()
    manifest = {
        "schema_version": 1,
        "artifacts": {
            "points": "points.bin",
            "points_metadata": "points_meta.json",
            "trace_event_index": "trace_event_index.bin",
            "trace_event_index_metadata": "trace_event_index_meta.json",
            "trace_segments": "trace_segments.bin",
            "trace_segments_metadata": "trace_segments_meta.json",
            "trace_aggregate_bins": "trace_aggregate_bins.bin",
            "trace_aggregate_bins_metadata": "trace_aggregate_bins_meta.json",
        },
        "counts": {
            "trace_events": 1,
            "trace_segments": 0,
            "trace_aggregate_bins": 0,
        },
    }
    write_json(artifact_dir / "canonical_web_manifest.json", manifest)
    write_json(artifact_dir / "event_chunk_manifest.json", [])
    write_json(artifact_dir / "summary_manifest.json", [])
    for file_name in (
        "points.bin",
        "points_meta.json",
        "trace_event_index.bin",
        "trace_event_index_meta.json",
        "trace_segments.bin",
        "trace_segments_meta.json",
        "trace_aggregate_bins.bin",
        "trace_aggregate_bins_meta.json",
    ):
        (artifact_dir / file_name).write_bytes(file_name.encode("utf-8"))
    (artifact_dir / "trace_event_index.bin.gz").write_bytes(b"gzipped")

    summary = stage_canonical_web_static_payload(
        artifact_dir=artifact_dir,
        output_root=output_root,
        mode="trace-runtime",
        include_gzip=True,
    )

    copied_paths = {item["path"] for item in summary["files"]}
    assert "data/canonical_web/canonical_web_manifest.json" in copied_paths
    assert "data/canonical_web/event_chunk_manifest.json" in copied_paths
    assert "data/canonical_web/summary_manifest.json" in copied_paths
    assert "data/canonical_web/trace_event_index.bin" in copied_paths
    assert "data/canonical_web/trace_event_index.bin.gz" in copied_paths
    assert "data/canonical_web/trace_aggregate_bins_meta.json" in copied_paths
    assert "data/canonical_web/points.bin" not in copied_paths
    assert (output_root / "data" / "canonical_web" / "trace_segments.bin").exists()
    assert (output_root / "canonical_web_static_payload_manifest.json").exists()

    payload_manifest = json.loads(
        (output_root / "canonical_web_static_payload_manifest.json").read_text(encoding="utf-8")
    )
    assert payload_manifest["mode"] == "trace-runtime"
    assert payload_manifest["gzip_bytes"] == len(b"gzipped")


def test_stage_primary_catalog_trace_runtime_payload_includes_summary_shards(tmp_path):
    artifact_dir = tmp_path / "canonical_web"
    output_root = tmp_path / "payload"
    (artifact_dir / "summary_shards").mkdir(parents=True)
    (output_root / "data").mkdir(parents=True)
    write_json(
        output_root / "data" / "app_config.json",
        {
            "mappedCount": 34227,
            "normalizedCount": 54751,
            "unresolvedCount": 25270,
            "packedPoints": {"enabled": True, "metadataUrl": "./data/points_meta.json", "binaryUrl": "./data/points.bin"},
            "canonicalWebArtifacts": {"enabled": False},
        },
    )
    write_json(output_root / "data" / "points_meta.json", {"schema_version": 2, "row_count": 34227, "bytes_per_row": 72})
    (output_root / "data" / "points.bin").write_bytes(b"legacy-points")
    manifest = {
        "artifacts": {
            "points": "points.bin",
            "points_metadata": "points_meta.json",
            "trace_event_index": "trace_event_index.bin",
            "trace_event_index_metadata": "trace_event_index_meta.json",
            "trace_segments": "trace_segments.bin",
            "trace_segments_metadata": "trace_segments_meta.json",
            "trace_aggregate_bins": "trace_aggregate_bins.bin",
            "trace_aggregate_bins_metadata": "trace_aggregate_bins_meta.json",
        },
        "counts": {
            "events": 942518,
            "mapped_events": 673104,
            "location_precision_counts": {"city": 600617, "unknown": 17029},
        },
        "packed_points": {"schema_version": 2, "row_count": 673104, "bytes_per_row": 72},
    }
    write_json(artifact_dir / "canonical_web_manifest.json", manifest)
    write_json(artifact_dir / "event_chunk_manifest.json", [])
    write_json(artifact_dir / "summary_manifest.json", [{"id": "summary_000000", "file": "summary_000000.json"}])
    for file_name in (
        "points.bin",
        "trace_event_index.bin",
        "trace_event_index_meta.json",
        "trace_segments.bin",
        "trace_segments_meta.json",
        "trace_aggregate_bins.bin",
        "trace_aggregate_bins_meta.json",
        "summary_shards/summary_000000.json",
    ):
        (artifact_dir / file_name).write_bytes(b"payload")
    write_json(artifact_dir / "points_meta.json", {"schema_version": 2, "row_count": 673104, "bytes_per_row": 72})

    summary = stage_canonical_web_static_payload(
        artifact_dir=artifact_dir,
        output_root=output_root,
        mode="primary-catalog-trace-runtime",
        include_gzip=False,
    )

    copied_paths = {item["path"] for item in summary["files"]}
    assert "data/canonical_web/points.bin" in copied_paths
    assert "data/canonical_web/trace_event_index.bin" in copied_paths
    assert "data/canonical_web/summary_shards/summary_000000.json" in copied_paths
    assert summary["usage"]["primary_catalog_trace_runtime"].startswith("Mode primary-catalog-trace-runtime")
    assert summary["app_config_sync"]["updated"] is True
    synced_config = json.loads((output_root / "data" / "app_config.json").read_text(encoding="utf-8"))
    assert synced_config["mappedCount"] == 673104
    assert synced_config["normalizedCount"] == 942518
    assert synced_config["unresolvedCount"] == 269414
    assert synced_config["packedPoints"]["metadataUrl"] == "./data/canonical_web/points_meta.json"
    assert synced_config["packedPoints"]["binaryUrl"] == "./data/canonical_web/points.bin"
    assert synced_config["packedPoints"]["rowCount"] == 673104
    assert synced_config["canonicalWebArtifacts"]["primaryCatalog"] is True
    assert synced_config["canonicalWebArtifacts"]["fullDetails"] is False
    assert summary["raw_bytes"] > 0


def test_stage_primary_catalog_trace_runtime_removes_stale_detail_chunks(tmp_path):
    artifact_dir = tmp_path / "canonical_web"
    output_root = tmp_path / "payload"
    (artifact_dir / "summary_shards").mkdir(parents=True)
    stale_chunk_dir = output_root / "data" / "canonical_web" / "event_chunks"
    stale_chunk_dir.mkdir(parents=True)
    (stale_chunk_dir / "chunk_legacy.json").write_text("stale", encoding="utf-8")
    legacy_catalog_dir = output_root / "data" / "catalog_shards"
    legacy_chunk_dir = output_root / "data" / "event_chunks"
    legacy_catalog_dir.mkdir(parents=True)
    legacy_chunk_dir.mkdir(parents=True)
    (legacy_catalog_dir / "catalog_legacy.json").write_text("legacy", encoding="utf-8")
    (legacy_chunk_dir / "chunk_legacy.json").write_text("legacy", encoding="utf-8")
    write_json(
        output_root / "data" / "app_config.json",
        {
            "mappedCount": 34227,
            "normalizedCount": 54751,
            "unresolvedCount": 25270,
            "packedPoints": {"enabled": True, "metadataUrl": "./data/points_meta.json", "binaryUrl": "./data/points.bin"},
            "canonicalWebArtifacts": {"enabled": False},
        },
    )
    write_json(output_root / "data" / "points_meta.json", {"schema_version": 2, "row_count": 34227, "bytes_per_row": 72})
    (output_root / "data" / "points.bin").write_bytes(b"legacy-points")
    manifest = {
        "artifacts": {
            "points": "points.bin",
            "points_metadata": "points_meta.json",
            "trace_event_index": "trace_event_index.bin",
            "trace_event_index_metadata": "trace_event_index_meta.json",
            "trace_segments": "trace_segments.bin",
            "trace_segments_metadata": "trace_segments_meta.json",
            "trace_aggregate_bins": "trace_aggregate_bins.bin",
            "trace_aggregate_bins_metadata": "trace_aggregate_bins_meta.json",
        },
        "counts": {"events": 2, "mapped_events": 1},
        "packed_points": {"schema_version": 2, "row_count": 1, "bytes_per_row": 72},
    }
    write_json(artifact_dir / "canonical_web_manifest.json", manifest)
    write_json(artifact_dir / "event_chunk_manifest.json", [{"id": "chunk_000000", "file": "chunk_000000.json"}])
    write_json(artifact_dir / "summary_manifest.json", [{"id": "summary_000000", "file": "summary_000000.json"}])
    for file_name in (
        "points.bin",
        "trace_event_index.bin",
        "trace_event_index_meta.json",
        "trace_segments.bin",
        "trace_segments_meta.json",
        "trace_aggregate_bins.bin",
        "trace_aggregate_bins_meta.json",
        "summary_shards/summary_000000.json",
    ):
        (artifact_dir / file_name).write_bytes(b"payload")
    write_json(artifact_dir / "points_meta.json", {"schema_version": 2, "row_count": 1, "bytes_per_row": 72})

    summary = stage_canonical_web_static_payload(
        artifact_dir=artifact_dir,
        output_root=output_root,
        mode="primary-catalog-trace-runtime",
        include_gzip=False,
    )

    assert not stale_chunk_dir.exists()
    assert not legacy_catalog_dir.exists()
    assert not legacy_chunk_dir.exists()
    assert summary["legacy_payload_prune"]["removed"] is True
    assert (output_root / "data" / "canonical_web" / "summary_shards" / "summary_000000.json").exists()


def test_stage_primary_catalog_trace_runtime_with_details_includes_event_chunks(tmp_path):
    artifact_dir = tmp_path / "canonical_web"
    output_root = tmp_path / "payload"
    (artifact_dir / "summary_shards").mkdir(parents=True)
    (artifact_dir / "event_chunks").mkdir(parents=True)
    manifest = {
        "artifacts": {
            "points": "points.bin",
            "points_metadata": "points_meta.json",
            "trace_event_index": "trace_event_index.bin",
            "trace_event_index_metadata": "trace_event_index_meta.json",
            "trace_segments": "trace_segments.bin",
            "trace_segments_metadata": "trace_segments_meta.json",
            "trace_aggregate_bins": "trace_aggregate_bins.bin",
            "trace_aggregate_bins_metadata": "trace_aggregate_bins_meta.json",
        }
    }
    write_json(artifact_dir / "canonical_web_manifest.json", manifest)
    write_json(artifact_dir / "event_chunk_manifest.json", [{"id": "chunk_000000", "file": "chunk_000000.json"}])
    write_json(artifact_dir / "summary_manifest.json", [{"id": "summary_000000", "file": "summary_000000.json"}])
    for file_name in (
        "points.bin",
        "points_meta.json",
        "trace_event_index.bin",
        "trace_event_index_meta.json",
        "trace_segments.bin",
        "trace_segments_meta.json",
        "trace_aggregate_bins.bin",
        "trace_aggregate_bins_meta.json",
        "summary_shards/summary_000000.json",
        "event_chunks/chunk_000000.json",
    ):
        (artifact_dir / file_name).write_bytes(b"payload")
    (artifact_dir / "event_chunks" / "chunk_000000.json.gz").write_bytes(b"gz")

    summary = stage_canonical_web_static_payload(
        artifact_dir=artifact_dir,
        output_root=output_root,
        mode="primary-catalog-trace-runtime-with-details",
        include_gzip=True,
    )

    copied_paths = {item["path"] for item in summary["files"]}
    assert "data/canonical_web/summary_shards/summary_000000.json" in copied_paths
    assert "data/canonical_web/event_chunks/chunk_000000.json" in copied_paths
    assert "data/canonical_web/event_chunks/chunk_000000.json.gz" in copied_paths
    assert summary["usage"]["primary_catalog_trace_runtime_with_details"].startswith(
        "Mode primary-catalog-trace-runtime-with-details"
    )
    synced_config_path = output_root / "data" / "app_config.json"
    if synced_config_path.exists():
        synced_config = json.loads(synced_config_path.read_text(encoding="utf-8"))
        assert synced_config["canonicalWebArtifacts"]["fullDetails"] is True
