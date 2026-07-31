import json
from pathlib import Path

import pytest

from scripts.serve_static_bundle_with_canonical_web import (
    CanonicalPreviewHandler,
    CanonicalPreviewServer,
    DEFAULT_CANONICAL_WEB_DIR,
    DEFAULT_STATIC_ROOT,
    build_preview_app_config,
    load_json_with_optional_bom,
    safe_resolve_under,
    select_served_file,
)


def test_preview_app_config_can_enable_guarded_canonical_trace_runtime():
    base_config = {
        "canonicalWebArtifacts": {
            "enabled": False,
            "manifestUrl": "./data/canonical_web/canonical_web_manifest.json",
            "primaryCatalog": False,
            "traceRuntime": False,
        }
    }

    config = build_preview_app_config(
        base_config,
        enable_canonical_web=True,
        enable_primary_catalog=True,
        enable_trace_runtime=True,
        enable_filtered_trace_aggregation=True,
    )

    canonical_config = config["canonicalWebArtifacts"]
    assert canonical_config["enabled"] is True
    assert canonical_config["primaryCatalog"] is True
    assert canonical_config["traceRuntime"] is True
    assert canonical_config["filteredTraceAggregation"] is True
    assert canonical_config["manifestUrl"] == "/data/canonical_web/canonical_web_manifest.json"
    assert canonical_config["summaryShardsBaseUrl"] == "/data/canonical_web/summary_shards/"
    assert config["packedPoints"]["metadataUrl"] == "/data/canonical_web/points_meta.json"
    assert config["packedPoints"]["binaryUrl"] == "/data/canonical_web/points.bin"


def test_preview_app_config_preserves_disabled_default_without_flags():
    base_config = {
        "mappedCount": 10,
        "canonicalWebArtifacts": {
            "enabled": False,
            "primaryCatalog": False,
            "traceRuntime": False,
        },
    }

    config = build_preview_app_config(base_config)

    assert config["mappedCount"] == 10
    assert config["canonicalWebArtifacts"]["enabled"] is False
    assert config["canonicalWebArtifacts"]["primaryCatalog"] is False
    assert config["canonicalWebArtifacts"]["traceRuntime"] is False
    assert config["canonicalWebArtifacts"]["filteredTraceAggregation"] is False


def test_preview_app_config_can_opt_into_canonical_packed_points_without_primary_catalog():
    config = build_preview_app_config(
        {
            "packedPoints": {
                "enabled": True,
                "metadataUrl": "./data/points_meta.json",
                "binaryUrl": "./data/points.bin",
            },
            "canonicalWebArtifacts": {
                "enabled": False,
                "primaryCatalog": False,
                "traceRuntime": False,
            },
        },
        use_canonical_packed_points=True,
    )

    assert config["packedPoints"]["metadataUrl"] == "/data/canonical_web/points_meta.json"
    assert config["packedPoints"]["binaryUrl"] == "/data/canonical_web/points.bin"
    assert config["canonicalWebArtifacts"]["primaryCatalog"] is False


def test_gzip_variant_is_selected_only_when_supported(tmp_path):
    raw_path = tmp_path / "trace_event_index.bin"
    raw_path.write_bytes(b"raw")
    raw_path.with_name("trace_event_index.bin.gz").write_bytes(b"gzip")

    served_path, encoding = select_served_file(raw_path, "br, gzip")
    assert served_path.name == "trace_event_index.bin.gz"
    assert encoding == "gzip"

    served_path, encoding = select_served_file(raw_path, "identity")
    assert served_path.name == "trace_event_index.bin"
    assert encoding is None


def test_safe_resolve_under_blocks_directory_traversal(tmp_path):
    root = tmp_path / "static"
    root.mkdir()
    (root / "index.html").write_text("ok", encoding="utf-8")

    assert safe_resolve_under(root, "/index.html") == (root / "index.html").resolve()
    with pytest.raises(ValueError):
        safe_resolve_under(root, "/../secret.txt")


def test_preview_app_config_json_round_trips():
    config = build_preview_app_config(
        {"canonicalWebArtifacts": {}},
        enable_trace_runtime=True,
    )
    payload = json.dumps(config, separators=(",", ":"), ensure_ascii=False)
    assert json.loads(payload)["canonicalWebArtifacts"]["traceRuntime"] is True


def test_preview_app_config_loader_accepts_windows_bom(tmp_path):
    config_path = tmp_path / "app_config.json"
    config_path.write_text('\ufeff{"canonicalWebArtifacts":{"enabled":true}}', encoding="utf-8")

    config = load_json_with_optional_bom(config_path)

    assert config["canonicalWebArtifacts"]["enabled"] is True


def test_preview_server_uses_browser_safe_connection_settings():
    source = Path("scripts/serve_static_bundle_with_canonical_web.py").read_text(encoding="utf-8")

    assert CanonicalPreviewHandler.protocol_version == "HTTP/1.1"
    assert CanonicalPreviewServer.daemon_threads is True
    assert CanonicalPreviewServer.allow_reuse_address is True
    assert "def log_message(self, format: str, *args: Any) -> None:" in source
    assert "if self.quiet:" in source
    assert 'send_header("Connection", "close")' not in source
    assert 'send_header("Cache-Control", "no-store")' in source


def test_preview_server_defaults_to_shipped_static_bundle_payload():
    assert DEFAULT_STATIC_ROOT == Path("static_bundle")
    assert DEFAULT_CANONICAL_WEB_DIR == Path("static_bundle") / "data" / "canonical_web"
