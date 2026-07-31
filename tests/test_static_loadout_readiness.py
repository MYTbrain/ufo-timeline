import json

from scripts.check_static_loadout_readiness import check_static_loadout_readiness


def test_static_loadout_readiness_validates_canonical_packed_points(tmp_path):
    root = tmp_path / "bundle"
    canonical = root / "data" / "canonical_web"
    (canonical / "summary_shards").mkdir(parents=True)
    (root / "data").mkdir(exist_ok=True)

    (root / "data" / "app_config.json").write_text(
        json.dumps(
            {
                "normalizedCount": 5,
                "mappedCount": 3,
                "canonicalWebArtifacts": {"primaryCatalog": True},
                "packedPoints": {
                    "metadataUrl": "./data/canonical_web/points_meta.json",
                    "binaryUrl": "./data/canonical_web/points.bin",
                    "rowCount": 3,
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "canonical_web_static_payload_manifest.json").write_text(
        json.dumps({"file_count": 8, "raw_bytes": 500, "gzip_bytes": 120, "app_config_sync": {"packedPointsRowCount": 3}}),
        encoding="utf-8",
    )
    (canonical / "canonical_web_manifest.json").write_text(json.dumps({"counts": {"events": 5, "mapped_events": 3}}), encoding="utf-8")
    (canonical / "points_meta.json").write_text(json.dumps({"row_count": 3, "bytes_per_row": 4}), encoding="utf-8")
    (canonical / "points.bin").write_bytes(b"123456789012")
    (canonical / "points.bin.gz").write_bytes(b"gz")
    (canonical / "summary_manifest.json").write_text(json.dumps({"shards": [{"id": "summary_000000"}]}), encoding="utf-8")
    (canonical / "summary_shards" / "summary_000000.json.gz").write_bytes(b"gz")
    zip_path = tmp_path / "static_bundle.zip"
    zip_path.write_bytes(b"zip")

    report = check_static_loadout_readiness(payload_root=root, zip_path=zip_path)

    assert report["status"] == "ready"
    assert report["canonical_outputs_mutated"] is False
    assert report["checks"]["row_parity_ok"] is True
    assert report["checks"]["packed_points_use_canonical_paths"] is True
    assert report["counts"]["manifest_mapped_events"] == 3
    assert report["zip"]["bytes"] == 3


def test_static_loadout_readiness_detects_legacy_packed_points_path(tmp_path):
    root = tmp_path / "bundle"
    canonical = root / "data" / "canonical_web"
    (canonical / "summary_shards").mkdir(parents=True)
    (root / "data").mkdir(exist_ok=True)
    (root / "data" / "app_config.json").write_text(
        json.dumps(
            {
                "canonicalWebArtifacts": {"primaryCatalog": True},
                "packedPoints": {"metadataUrl": "./data/points_meta.json", "binaryUrl": "./data/points.bin", "rowCount": 3},
            }
        ),
        encoding="utf-8",
    )
    (root / "canonical_web_static_payload_manifest.json").write_text(
        json.dumps({"app_config_sync": {"packedPointsRowCount": 3}}),
        encoding="utf-8",
    )
    (canonical / "canonical_web_manifest.json").write_text(json.dumps({"counts": {"events": 5, "mapped_events": 3}}), encoding="utf-8")
    (canonical / "points_meta.json").write_text(json.dumps({"row_count": 3, "bytes_per_row": 4}), encoding="utf-8")
    (canonical / "points.bin").write_bytes(b"123456789012")
    (canonical / "points.bin.gz").write_bytes(b"gz")
    (canonical / "summary_manifest.json").write_text(json.dumps({"shards": []}), encoding="utf-8")
    (canonical / "summary_shards" / "summary_000000.json.gz").write_bytes(b"gz")

    report = check_static_loadout_readiness(payload_root=root, zip_path=None)

    assert report["status"] == "needs_attention"
    assert report["checks"]["packed_points_use_canonical_paths"] is False
