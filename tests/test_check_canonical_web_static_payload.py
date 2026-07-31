import json

from parser.utils import write_json
from scripts.check_canonical_web_static_payload import check_canonical_web_static_payload
from scripts.stage_canonical_web_static_payload import stage_canonical_web_static_payload


def _write_artifact_fixture(artifact_dir):
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
        (artifact_dir / file_name).write_bytes(file_name.encode("utf-8"))
        (artifact_dir / f"{file_name}.gz").write_bytes(b"gz")


def _write_static_config(static_bundle_root, *, canonical_enabled=False):
    config_dir = static_bundle_root / "data"
    config_dir.mkdir(parents=True)
    write_json(
        config_dir / "app_config.json",
        {
            "canonicalWebArtifacts": {
                "enabled": canonical_enabled,
                "primaryCatalog": False,
                "traceRuntime": False,
                "filteredTraceAggregation": False,
            }
        },
    )


def test_static_payload_validator_accepts_primary_trace_payload(tmp_path):
    artifact_dir = tmp_path / "canonical_web"
    output_root = tmp_path / "payload"
    static_bundle_root = tmp_path / "static_bundle"
    _write_artifact_fixture(artifact_dir)
    _write_static_config(static_bundle_root)
    stage_canonical_web_static_payload(
        artifact_dir=artifact_dir,
        output_root=output_root,
        mode="primary-catalog-trace-runtime",
        include_gzip=True,
    )

    report = check_canonical_web_static_payload(output_root, static_bundle_root=static_bundle_root)

    assert report["status"] == "ready"
    assert report["checks"]["default_app_config_canonical_config_matches_expected"] is True
    assert report["config_state"]["default_app_config_canonical_disabled"] is True
    assert report["checks"]["primary_payload_has_summary_shards"] is True
    assert report["checks"]["lean_payload_omits_event_chunks"] is True
    assert report["checks"]["gzip_entries_have_raw_siblings"] is True
    assert report["counts"]["summary_shards"] == 1
    assert report["counts"]["event_chunks"] == 0


def test_static_payload_validator_requires_full_detail_chunks_for_full_mode(tmp_path):
    artifact_dir = tmp_path / "canonical_web"
    output_root = tmp_path / "payload"
    static_bundle_root = tmp_path / "static_bundle"
    _write_artifact_fixture(artifact_dir)
    _write_static_config(static_bundle_root)
    stage_canonical_web_static_payload(
        artifact_dir=artifact_dir,
        output_root=output_root,
        mode="primary-catalog-trace-runtime-with-details",
        include_gzip=True,
    )

    report = check_canonical_web_static_payload(output_root, static_bundle_root=static_bundle_root)

    assert report["status"] == "ready"
    assert report["checks"]["full_detail_payload_has_event_chunks"] is True
    assert report["checks"]["lean_payload_omits_event_chunks"] is True
    assert report["counts"]["event_chunks"] == 1


def test_static_payload_validator_blocks_mutated_default_app_config(tmp_path):
    artifact_dir = tmp_path / "canonical_web"
    output_root = tmp_path / "payload"
    static_bundle_root = tmp_path / "static_bundle"
    _write_artifact_fixture(artifact_dir)
    _write_static_config(static_bundle_root, canonical_enabled=True)
    stage_canonical_web_static_payload(
        artifact_dir=artifact_dir,
        output_root=output_root,
        mode="primary-catalog-trace-runtime",
        include_gzip=False,
    )

    report = check_canonical_web_static_payload(output_root, static_bundle_root=static_bundle_root)

    assert report["status"] == "blocked"
    assert report["checks"]["default_app_config_canonical_config_matches_expected"] is False
    assert report["config_state"]["default_app_config_canonical_disabled"] is False


def test_static_payload_validator_accepts_explicitly_promoted_config(tmp_path):
    artifact_dir = tmp_path / "canonical_web"
    output_root = tmp_path / "payload"
    static_bundle_root = tmp_path / "static_bundle"
    _write_artifact_fixture(artifact_dir)
    config_dir = static_bundle_root / "data"
    config_dir.mkdir(parents=True)
    write_json(
        config_dir / "app_config.json",
        {
            "canonicalWebArtifacts": {
                "enabled": True,
                "primaryCatalog": True,
                "traceRuntime": True,
                "filteredTraceAggregation": True,
            }
        },
    )
    stage_canonical_web_static_payload(
        artifact_dir=artifact_dir,
        output_root=output_root,
        mode="primary-catalog-trace-runtime-with-details",
        include_gzip=False,
    )

    report = check_canonical_web_static_payload(
        output_root,
        static_bundle_root=static_bundle_root,
        expected_canonical_config="promoted",
    )

    assert report["status"] == "ready"
    assert report["checks"]["default_app_config_canonical_config_matches_expected"] is True
    assert report["config_state"]["default_app_config_canonical_promoted"] is True


def test_static_payload_validator_reports_missing_files(tmp_path):
    artifact_dir = tmp_path / "canonical_web"
    output_root = tmp_path / "payload"
    static_bundle_root = tmp_path / "static_bundle"
    _write_artifact_fixture(artifact_dir)
    _write_static_config(static_bundle_root)
    stage_canonical_web_static_payload(
        artifact_dir=artifact_dir,
        output_root=output_root,
        mode="primary-catalog-trace-runtime",
        include_gzip=False,
    )
    manifest_path = output_root / "canonical_web_static_payload_manifest.json"
    payload_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    first_trace_file = next(
        item["path"] for item in payload_manifest["files"] if item["path"].endswith("trace_event_index.bin")
    )
    (output_root / first_trace_file).unlink()

    report = check_canonical_web_static_payload(output_root, static_bundle_root=static_bundle_root)

    assert report["status"] == "blocked"
    assert report["checks"]["copied_files_exist"] is False
    assert first_trace_file in report["problems"]["missing_files"]
