import json
import struct
from pathlib import Path

from parser import load_config, run_pipeline


def test_pipeline_generates_outputs_without_external_geocoding(tmp_path):
    fixture = Path(__file__).parent / "fixtures" / "sample_ufo_input.txt"
    config_path = tmp_path / "config.yaml"
    data_dir = tmp_path / "data"
    reports_dir = data_dir / "reports"
    cache_dir = tmp_path / "cache"
    reports_dir.mkdir(parents=True)
    cache_dir.mkdir()
    normalized_path = str(data_dir / "normalized_events.json").replace("\\", "/")
    map_path = str(data_dir / "map_events.json").replace("\\", "/")
    unresolved_json = str(reports_dir / "unresolved_locations.json").replace("\\", "/")
    unresolved_csv = str(reports_dir / "unresolved_locations.csv").replace("\\", "/")
    parse_failures = str(reports_dir / "parse_failures.jsonl").replace("\\", "/")
    geocode_failures = str(reports_dir / "geocode_failures.jsonl").replace("\\", "/")
    overrides_path = str(data_dir / "manual_location_overrides.json").replace("\\", "/")
    cache_path = str(cache_dir / "geocode_cache.jsonl").replace("\\", "/")

    config_path.write_text(
        f"""
inputs:
  files:
    - {fixture.as_posix()}
outputs:
  normalized_events: {normalized_path}
  map_events: {map_path}
  unresolved_locations_json: {unresolved_json}
  unresolved_locations_csv: {unresolved_csv}
  parse_failures: {parse_failures}
  geocode_failures: {geocode_failures}
  manual_overrides: {overrides_path}
cache:
  geocode_cache: {cache_path}
geocoder:
  enabled: true
  provider: nominatim
  endpoint: https://example.com/search
  user_agent: tests
  rate_limit_seconds: 0.0
  timeout_seconds: 1
  description_fallback_enabled: true
web:
  host: 127.0.0.1
  port: 8000
  tile_url: https://example.com/{{z}}/{{x}}/{{y}}.png
  tile_attribution: example
  initial_center: [20, 0]
  initial_zoom: 2
""",
        encoding="utf-8",
    )

    summary = run_pipeline(load_config(config_path), disable_geocoding=True)

    normalized_path = data_dir / "normalized_events.json"
    map_path = data_dir / "map_events.json"
    unresolved_path = reports_dir / "unresolved_locations.json"
    parse_failures_path = reports_dir / "parse_failures.jsonl"
    geocode_failures_path = reports_dir / "geocode_failures.jsonl"
    static_bundle_dir = tmp_path / "static_bundle"

    assert normalized_path.exists()
    assert map_path.exists()
    assert unresolved_path.exists()
    assert parse_failures_path.exists()
    assert geocode_failures_path.exists()
    assert (static_bundle_dir / "index.html").exists()
    assert (static_bundle_dir / "data" / "app_config.json").exists()
    assert (static_bundle_dir / "data" / "event_catalog_manifest.json").exists()
    assert (static_bundle_dir / "data" / "event_chunk_manifest.json").exists()
    assert (static_bundle_dir / "data" / "points.bin").exists()
    assert (static_bundle_dir / "data" / "points_meta.json").exists()
    assert (static_bundle_dir / "data" / "catalog_shards" / "catalog_000.json").exists()
    assert (static_bundle_dir / "data" / "event_chunks" / "chunk_000.json").exists()

    normalized = json.loads(normalized_path.read_text(encoding="utf-8"))
    map_events = json.loads(map_path.read_text(encoding="utf-8"))
    unresolved = json.loads(unresolved_path.read_text(encoding="utf-8"))
    catalog_shard = json.loads((static_bundle_dir / "data" / "catalog_shards" / "catalog_000.json").read_text(encoding="utf-8"))
    chunk_events = json.loads((static_bundle_dir / "data" / "event_chunks" / "chunk_000.json").read_text(encoding="utf-8"))
    app_config = json.loads((static_bundle_dir / "data" / "app_config.json").read_text(encoding="utf-8"))
    points_meta = json.loads((static_bundle_dir / "data" / "points_meta.json").read_text(encoding="utf-8"))

    assert summary["normalized_events"] == 5
    assert summary["map_events"] == 3
    assert len(normalized) == 5
    assert len(map_events) == 3
    assert any(item["event_id"] == 101 for item in unresolved)
    assert any(item["coordinate_source"] == "raw_latlong" for item in normalized)
    assert any(item["coordinate_source"] == "location_coordinates" for item in normalized)
    assert "time_sort_kind" in catalog_shard[0]
    assert "playback_sort_reason" in catalog_shard[0]
    assert "playback_sort_key" in catalog_shard[0]
    assert "estimated_utc_timestamp_ms" not in catalog_shard[0]
    assert "parsed_time_local_minutes" not in catalog_shard[0]
    assert "timezone_confidence" not in catalog_shard[0]
    assert "raw_event_block" not in catalog_shard[0]
    assert "mapping_notes" not in catalog_shard[0]
    assert "original_entry_url" not in catalog_shard[0]
    assert "all_locations_raw" not in catalog_shard[0]
    assert "time_sort_kind" in chunk_events[0]
    assert "playback_sort_reason" in chunk_events[0]
    assert "estimated_utc_timestamp_ms" in chunk_events[0]
    assert "raw_event_block" in chunk_events[0]
    assert app_config["packedPoints"]["enabled"] is True
    assert app_config["packedPoints"]["startupPreview"] is True
    assert app_config["packedPoints"]["startupPreviewMaxPoints"] == 80000
    assert app_config["canonicalWebArtifacts"]["enabled"] is False
    assert app_config["canonicalWebArtifacts"]["primaryCatalog"] is False
    assert app_config["canonicalWebArtifacts"]["traceRuntime"] is False
    assert app_config["canonicalWebArtifacts"]["filteredTraceAggregation"] is False
    assert app_config["canonicalWebArtifacts"]["chunkManifestUrl"] == "./data/canonical_web/event_chunk_manifest.json"
    assert app_config["canonicalWebArtifacts"]["summaryManifestUrl"] == "./data/canonical_web/summary_manifest.json"
    assert app_config["canonicalWebArtifacts"]["summaryShardsBaseUrl"] == "./data/canonical_web/summary_shards/"
    assert points_meta["row_count"] == len(map_events)
    assert points_meta["bytes_per_row"] > 0
    assert (static_bundle_dir / "data" / "points.bin").stat().st_size == (
        points_meta["row_count"] * points_meta["bytes_per_row"]
    )
    packed_rows = _read_packed_rows(static_bundle_dir / "data" / "points.bin", points_meta)
    chunk_events_by_id = {
        chunk["id"]: json.loads(
            (static_bundle_dir / "data" / "event_chunks" / chunk["file"]).read_text(encoding="utf-8")
        )
        for chunk in json.loads((static_bundle_dir / "data" / "event_chunk_manifest.json").read_text(encoding="utf-8"))
    }
    for row in packed_rows:
        chunk_events = chunk_events_by_id[row["chunk_id"]]
        assert chunk_events[row["detail_index"]]["event_id"] == row["event_id"]


def _read_packed_rows(path: Path, metadata: dict):
    row_struct = struct.Struct(metadata["struct_format"])
    rows = []
    for unpacked in row_struct.iter_unpack(path.read_bytes()):
        row = {}
        for field, value in zip(metadata["fields"], unpacked):
            lookup_table = field.get("lookup_table")
            if lookup_table:
                value = metadata["lookup_tables"][lookup_table][value]
            row[field["name"]] = value
        rows.append(row)
    return rows
