import gzip
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from scripts import build_cloudflare_bundle, reproduction, validate_cloudflare_bundle


REPO_ROOT = Path(__file__).resolve().parents[1]


def run_python_script(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / script), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )


def write_duration_manifest_stub(root: Path) -> None:
    manifest = {
        "releaseId": "analysis-duration-test-v1",
        "assetBaseUrl": "https://assets.example.org/releases/analysis-duration-test-v1",
        "delivery": {
            "pagesFiles": ["manifest.json"],
            "immutablePrefix": "releases/analysis-duration-test-v1",
            "r2OnlyPaths": ["projection.json.gz"],
        },
        "payloads": {
            "projection": {
                "path": "projection.json.gz",
                "bytes": 2,
                "sha256": "0" * 64,
                "r2Only": True,
            }
        },
    }
    path = root / "data" / "analysis_duration_v1" / "manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest), encoding="utf-8")


def write_reporting_delay_manifest_stub(root: Path) -> None:
    manifest = {
        "releaseId": "analysis-reporting-delay-test-v1",
        "assetBaseUrl": "https://assets.example.org/releases/analysis-reporting-delay-test-v1",
        "delivery": {
            "pagesFiles": ["manifest.json"],
            "immutablePrefix": "releases/analysis-reporting-delay-test-v1",
            "r2OnlyPaths": ["projection.json.gz"],
        },
        "payloads": {
            "projection": {
                "path": "projection.json.gz",
                "bytes": 2,
                "sha256": "0" * 64,
                "r2Only": True,
            }
        },
    }
    path = root / "data" / "analysis_reporting_delay_v1" / "manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest), encoding="utf-8")


def write_coordinate_evidence_manifest_stub(root: Path) -> None:
    manifest = {
        "releaseId": "analysis-coordinate-evidence-test-v1",
        "assetBaseUrl": "https://assets.example.org/releases/analysis-coordinate-evidence-test-v1",
        "delivery": {
            "pagesFiles": ["manifest.json"],
            "immutablePrefix": "releases/analysis-coordinate-evidence-test-v1",
            "r2OnlyPaths": ["projection.json.gz"],
        },
        "payloads": {
            "projection": {
                "path": "projection.json.gz",
                "bytes": 2,
                "sha256": "0" * 64,
                "r2Only": True,
            }
        },
    }
    path = root / "data" / "analysis_coordinate_evidence_v1" / "manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest), encoding="utf-8")


def write_time_of_day_manifest_stub(root: Path) -> None:
    manifest = {
        "releaseId": "analysis-time-of-day-test-v1",
        "assetBaseUrl": "https://assets.example.org/releases/analysis-time-of-day-test-v1",
        "delivery": {
            "pagesFiles": ["manifest.json"],
            "immutablePrefix": "releases/analysis-time-of-day-test-v1",
            "r2OnlyPaths": ["projection.json.gz"],
        },
        "payloads": {"projection": {"path": "projection.json.gz", "bytes": 2, "sha256": "0" * 64, "r2Only": True}},
    }
    path = root / "data" / "analysis_time_of_day_v1" / "manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest), encoding="utf-8")


def test_startup_profile_builder_writes_scoped_preview_artifacts(tmp_path):
    static_root = tmp_path / "static_bundle"
    canonical_root = static_root / "data" / "canonical_web"
    summary_root = canonical_root / "summary_shards"
    summary_root.mkdir(parents=True)
    (canonical_root / "event_chunk_manifest.json").write_text("[]\n", encoding="utf-8")
    (canonical_root / "summary_manifest.json").write_text(
        json.dumps([{"id": "summary_000000", "file": "summary_000000.json", "event_count": 3}]),
        encoding="utf-8",
    )
    events = [
        {
            "event_id": 1,
            "chunk_id": "chunk_000000",
            "detail_index": 0,
            "sort_date_iso": "1954-09-02",
            "date_precision": "exact_day",
            "location_raw": "Paris, FRA, EU",
            "source": "ufocat",
            "type": "Disk",
            "coordinate_source": "geocoded",
            "location_precision": "city",
            "lat": 48.8566,
            "lon": 2.3522,
            "has_coordinates": True,
        },
        {
            "event_id": 2,
            "chunk_id": "chunk_000000",
            "detail_index": 1,
            "sort_date_iso": "1954-09-03",
            "date_precision": "exact_day",
            "location_raw": "Lyon, FRA, EU",
            "source": "ufocat",
            "type": "Light",
            "coordinate_source": "geocoded",
            "location_precision": "city",
            "lat": 45.764,
            "lon": 4.8357,
            "has_coordinates": True,
        },
        {
            "event_id": 3,
            "sort_date_iso": "1955-01-01",
            "lat": 0,
            "lon": 0,
            "has_coordinates": True,
        },
    ]
    (summary_root / "summary_000000.json").write_text(json.dumps(events), encoding="utf-8")

    run_python_script(
        "scripts/build_startup_profile_artifacts.py",
        "--static-root",
        str(static_root),
        "--profile-id",
        "france_1954_flap",
        "--label",
        "1954 France Sept-Nov",
        "--start-date",
        "1954-09-01",
        "--end-date",
        "1954-11-30",
    )

    profile_root = static_root / "data" / "startup_profiles" / "france_1954_flap"
    manifest = json.loads((profile_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["counts"]["events"] == 2
    assert manifest["counts"]["trace_preview_segments"] == 1
    assert (profile_root / "events.json.gz").exists()
    assert (profile_root / "points.bin.gz").exists()
    assert (profile_root / "trace_event_index.bin.gz").exists()


def test_startup_profile_builder_writes_default_profile_index(tmp_path):
    static_root = tmp_path / "static_bundle"
    canonical_root = static_root / "data" / "canonical_web"
    summary_root = canonical_root / "summary_shards"
    summary_root.mkdir(parents=True)
    (canonical_root / "event_chunk_manifest.json").write_text("[]\n", encoding="utf-8")
    (static_root / "data" / "app_config.json").write_text("{}\n", encoding="utf-8")
    (canonical_root / "summary_manifest.json").write_text(
        json.dumps([{"id": "summary_000000", "file": "summary_000000.json", "event_count": 5}]),
        encoding="utf-8",
    )
    events = [
        {
            "event_id": 1,
            "chunk_id": "chunk_000000",
            "detail_index": 0,
            "sort_date_iso": "1954-09-02",
            "date_precision": "exact_day",
            "source": "ufocat",
            "type": "Disk",
            "coordinate_source": "geocoded",
            "location_precision": "city",
            "lat": 48.8566,
            "lon": 2.3522,
            "has_coordinates": True,
        },
        {
            "event_id": 2,
            "chunk_id": "chunk_000000",
            "detail_index": 1,
            "sort_date_iso": "1954-09-03",
            "date_precision": "exact_day",
            "source": "ufocat",
            "type": "Light",
            "coordinate_source": "geocoded",
            "location_precision": "city",
            "lat": 45.764,
            "lon": 4.8357,
            "has_coordinates": True,
        },
        {
            "event_id": 3,
            "chunk_id": "chunk_000000",
            "detail_index": 2,
            "sort_date_iso": "1989-11-29",
            "date_precision": "exact_day",
            "source": "ufocat",
            "type": "Triangle",
            "coordinate_source": "geocoded",
            "location_precision": "city",
            "lat": 50.8503,
            "lon": 4.3517,
            "has_coordinates": True,
        },
        {
            "event_id": 4,
            "sort_date_iso": "1991-01-01",
            "lat": 0,
            "lon": 0,
            "has_coordinates": True,
        },
        {
            "event_id": 5,
            "chunk_id": "chunk_000000",
            "detail_index": 3,
            "sort_date_iso": "1897-04-15",
            "date_precision": "exact_day",
            "source": "ufocat",
            "type": "Light",
            "coordinate_source": "geocoded",
            "location_precision": "city",
            "lat": 39.0997,
            "lon": -94.5786,
            "has_coordinates": True,
        },
    ]
    (summary_root / "summary_000000.json").write_text(json.dumps(events), encoding="utf-8")

    run_python_script(
        "scripts/build_startup_profile_artifacts.py",
        "--static-root",
        str(static_root),
        "--all-default-profiles",
        "--enable-default-profile",
    )

    index = json.loads((static_root / "data" / "startup_profiles" / "manifest.json").read_text(encoding="utf-8"))
    profile_ids = {profile["id"] for profile in index["profiles"]}
    assert {
        "mystery_airship_wave_1896_1897",
        "france_1954_flap",
        "belgium_1989_1990_wave",
    }.issubset(profile_ids)
    assert (static_root / "data" / "startup_profiles" / "manifest.json.gz").exists()
    assert (static_root / "data" / "startup_profiles" / "belgium_1989_1990_wave" / "events.json.gz").exists()
    belgium_manifest = json.loads(
        (static_root / "data" / "startup_profiles" / "belgium_1989_1990_wave" / "manifest.json").read_text(encoding="utf-8")
    )
    assert belgium_manifest["counts"]["events"] == 1
    app_config = json.loads((static_root / "data" / "app_config.json").read_text(encoding="utf-8"))
    assert app_config["startupProfile"] == {
        "enabled": True,
        "id": "france_1954_flap",
        "label": "1954 France Sept-Nov",
        "baseUrl": "./data/startup_profiles/france_1954_flap/",
        "manifestUrl": "./data/startup_profiles/france_1954_flap/manifest.json",
        "renderBeforeGlobalCatalog": True,
        "tracePreview": True,
        "worker": True,
    }


def test_cloudflare_bundle_omits_oversized_raw_artifacts_and_rewrites_r2_urls(tmp_path):
    static_root = tmp_path / "static_bundle"
    canonical_root = static_root / "data" / "canonical_web"
    canonical_root.mkdir(parents=True)
    (static_root / "index.html").write_text("<!doctype html>\n", encoding="utf-8")
    (static_root / "app.js").write_text("console.log('ok');\n", encoding="utf-8")
    (static_root / "startup_profile_worker.js").write_text("self.onmessage = () => {};\n", encoding="utf-8")
    (static_root / "catalog_filter_worker.js").write_text("self.onmessage = () => {};\n", encoding="utf-8")
    (static_root / "trace_facility_worker.js").write_text("self.onmessage = () => {};\n", encoding="utf-8")
    (static_root / "data").mkdir(exist_ok=True)
    (static_root / "data" / "app_config.json").write_text(
        json.dumps({
            "packedPoints": {"metadataUrl": "./data/canonical_web/points_meta.json", "binaryUrl": "./data/canonical_web/points.bin"},
            "canonicalWebArtifacts": {
                "manifestUrl": "./data/canonical_web/canonical_web_manifest.json",
                "chunkManifestUrl": "./data/canonical_web/event_chunk_manifest.json",
                "eventChunksBaseUrl": "./data/canonical_web/event_chunks/",
                "summaryManifestUrl": "./data/canonical_web/summary_manifest.json",
                "summaryShardsBaseUrl": "./data/canonical_web/summary_shards/",
            },
        }),
        encoding="utf-8",
    )
    (canonical_root / "points.bin").write_bytes(b"x" * (26 * 1024 * 1024))
    (canonical_root / "points.bin.gz").write_bytes(b"small")
    (canonical_root / "points_meta.json").write_text("{}\n", encoding="utf-8")

    output_root = tmp_path / "cloudflare_bundle"
    run_python_script(
        "scripts/build_cloudflare_bundle.py",
        "--static-root",
        str(static_root),
        "--output-root",
        str(output_root),
        "--r2-base-url",
        "https://example.r2.dev/ufo",
        "--r2-key-prefix",
        "ufo",
        "--include-gzip-data",
    )

    report = json.loads((output_root / "cloudflare_bundle_manifest.json").read_text(encoding="utf-8"))
    r2_manifest = json.loads((output_root / "r2_upload_manifest.json").read_text(encoding="utf-8"))
    headers = (output_root / "_headers").read_text(encoding="utf-8")
    config = json.loads((output_root / "data" / "app_config.json").read_text(encoding="utf-8"))
    assert report["pages_safe"] is True
    assert not (output_root / "data" / "canonical_web" / "points.bin").exists()
    assert (output_root / "data" / "canonical_web" / "points.bin.gz").exists()
    upload_paths = {upload["path"] for upload in r2_manifest["uploads"]}
    assert r2_manifest["upload_count"] == 2
    assert r2_manifest["r2_key_prefix"] == "ufo"
    assert {
        "data/canonical_web/points.bin.gz",
        "data/canonical_web/points_meta.json",
    }.issubset(upload_paths)
    assert "data/canonical_web/points.bin" not in upload_paths
    gzip_upload = next(upload for upload in r2_manifest["uploads"] if upload["path"] == "data/canonical_web/points.bin.gz")
    assert gzip_upload["content_encoding"] == ""
    assert gzip_upload["content_type"] == "application/octet-stream"
    assert gzip_upload["cache_control"] == "public, max-age=31536000, immutable"
    assert gzip_upload["r2_key"] == "ufo/data/canonical_web/points.bin.gz"
    upload_script = (output_root / "upload_r2_assets.ps1").read_text(encoding="utf-8")
    assert "--cache-control" in upload_script
    assert (output_root / "startup_profile_worker.js").exists()
    assert (output_root / "catalog_filter_worker.js").exists()
    assert (output_root / "trace_facility_worker.js").exists()
    assert "/startup_profile_worker.js" in headers
    assert "/catalog_filter_worker.js" in headers
    assert "/trace_facility_worker.js" in headers
    assert "/data/startup_profiles/*" in headers
    assert "Cache-Control: public, max-age=31536000, immutable" in headers
    assert config["packedPoints"]["binaryUrl"] == "https://example.r2.dev/ufo/data/canonical_web/points.bin"
    assert config["canonicalWebArtifacts"]["summaryShardsBaseUrl"] == "https://example.r2.dev/ufo/data/canonical_web/summary_shards/"


def test_cloudflare_builder_omits_legacy_optional_payload_declarations(tmp_path):
    static_root = tmp_path / "static_bundle"
    crop_root = static_root / "data" / "crop_circles"
    crop_root.mkdir(parents=True)
    (static_root / "index.html").write_text("<!doctype html>\n", encoding="utf-8")
    (static_root / "data" / "app_config.json").write_text("{}\n", encoding="utf-8")
    payload = b"legacy crop payload"
    (crop_root / "points.json.gz").write_bytes(payload)
    (crop_root / "manifest.json").write_text(
        json.dumps({
            "releaseId": "crop-v1",
            "assetBaseUrl": "https://assets.example.org/releases/crop-v1",
            "points": {
                "path": "points.json.gz",
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            },
        }),
        encoding="utf-8",
    )
    output_root = tmp_path / "cloudflare_bundle"

    run_python_script(
        "scripts/build_cloudflare_bundle.py",
        "--static-root",
        str(static_root),
        "--output-root",
        str(output_root),
    )

    assert not (output_root / "data" / "crop_circles" / "points.json.gz").exists()
    report = json.loads((output_root / "cloudflare_bundle_manifest.json").read_text(encoding="utf-8"))
    omitted = {item["path"]: item["reason"] for item in report["omitted"]}
    assert omitted["data/crop_circles/points.json.gz"] == "optional_layer_immutable_r2_payload"


def test_cloudflare_bundle_validator_blocks_placeholder_r2_urls(tmp_path):
    bundle_root = tmp_path / "cloudflare_bundle_r2"
    (bundle_root / "data").mkdir(parents=True)
    (bundle_root / "cloudflare_bundle_manifest.json").write_text(
        json.dumps({"pages_safe": True}),
        encoding="utf-8",
    )
    (bundle_root / "r2_upload_manifest.json").write_text(
        json.dumps({"r2_base_url": "https://example-r2.invalid/ufo", "upload_count": 1}),
        encoding="utf-8",
    )
    (bundle_root / "data" / "app_config.json").write_text(
        json.dumps({"deploymentProfile": {"largeDataBaseUrl": "https://example-r2.invalid/ufo"}}),
        encoding="utf-8",
    )
    (bundle_root / "_headers").write_text(
        "/data/startup_profiles/*\n  Cache-Control: public, max-age=31536000, immutable\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts/validate_cloudflare_bundle.py"), "--bundle-root", str(bundle_root)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "placeholder" in result.stdout


def test_cloudflare_bundle_validator_allows_real_r2_urls(tmp_path):
    bundle_root = tmp_path / "cloudflare_bundle_r2"
    (bundle_root / "data").mkdir(parents=True)
    (bundle_root / "cloudflare_bundle_manifest.json").write_text(
        json.dumps({"pages_safe": True}),
        encoding="utf-8",
    )
    (bundle_root / "r2_upload_manifest.json").write_text(
        json.dumps({"r2_base_url": "https://assets.example.org/ufo", "upload_count": 1}),
        encoding="utf-8",
    )
    (bundle_root / "data" / "app_config.json").write_text(
        json.dumps({"deploymentProfile": {"largeDataBaseUrl": "https://assets.example.org/ufo"}}),
        encoding="utf-8",
    )
    (bundle_root / "_headers").write_text(
        "/data/startup_profiles/*\n  Cache-Control: public, max-age=31536000, immutable\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts/validate_cloudflare_bundle.py"), "--bundle-root", str(bundle_root)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0
    assert '"ok": true' in result.stdout


def test_public_cloudflare_bundle_builder_runs_profiles_bundle_and_validation(tmp_path):
    static_root = tmp_path / "static_bundle"
    canonical_root = static_root / "data" / "canonical_web"
    summary_root = canonical_root / "summary_shards"
    summary_root.mkdir(parents=True)
    (static_root / "index.html").write_text("<!doctype html>\n", encoding="utf-8")
    (static_root / "app.js").write_text("console.log('ok');\n", encoding="utf-8")
    (static_root / "styles.css").write_text("body{}\n", encoding="utf-8")
    (static_root / "startup_profile_worker.js").write_text("self.onmessage = () => {};\n", encoding="utf-8")
    (static_root / "catalog_filter_worker.js").write_text("self.onmessage = () => {};\n", encoding="utf-8")
    (static_root / "trace_facility_worker.js").write_text("self.onmessage = () => {};\n", encoding="utf-8")
    (static_root / "data").mkdir(exist_ok=True)
    (static_root / "data" / "app_config.json").write_text(
        json.dumps({
            "startupProfile": {
                "manifestUrl": "./data/startup_profiles/france_1954_flap/manifest.json",
            },
            "packedPoints": {
                "metadataUrl": "./data/canonical_web/points_meta.json",
                "binaryUrl": "./data/canonical_web/points.bin",
            },
            "canonicalWebArtifacts": {
                "manifestUrl": "./data/canonical_web/canonical_web_manifest.json",
                "chunkManifestUrl": "./data/canonical_web/event_chunk_manifest.json",
                "eventChunksBaseUrl": "./data/canonical_web/event_chunks/",
                "summaryManifestUrl": "./data/canonical_web/summary_manifest.json",
                "summaryShardsBaseUrl": "./data/canonical_web/summary_shards/",
            },
        }),
        encoding="utf-8",
    )
    (canonical_root / "event_chunk_manifest.json").write_text("[]\n", encoding="utf-8")
    (canonical_root / "points.bin").write_bytes(b"x" * (26 * 1024 * 1024))
    (canonical_root / "points.bin.gz").write_bytes(b"small")
    (canonical_root / "points_meta.json").write_text("{}\n", encoding="utf-8")
    (canonical_root / "summary_manifest.json").write_text(
        json.dumps([{"id": "summary_000000", "file": "summary_000000.json", "event_count": 3}]),
        encoding="utf-8",
    )
    summary_payload = json.dumps([
            {
                "event_id": 1,
                "sort_date_iso": "1954-09-02",
                "date_precision": "exact_day",
                "source": "ufocat",
                "type": "Disk",
                "lat": 48.8566,
                "lon": 2.3522,
                "has_coordinates": True,
            },
            {
                "event_id": 2,
                "sort_date_iso": "1989-11-29",
                "date_precision": "exact_day",
                "source": "ufocat",
                "type": "Triangle",
                "lat": 50.8503,
                "lon": 4.3517,
                "has_coordinates": True,
            },
            {
                "event_id": 3,
                "sort_date_iso": "1897-04-15",
                "date_precision": "exact_day",
                "source": "ufocat",
                "type": "Light",
                "lat": 39.0997,
                "lon": -94.5786,
                "has_coordinates": True,
            },
        ])
    (summary_root / "summary_000000.json").write_text(
        summary_payload,
        encoding="utf-8",
    )
    with gzip.open(summary_root / "summary_000000.json.gz", "wt", encoding="utf-8") as handle:
        handle.write(summary_payload)

    output_root = tmp_path / "cloudflare_bundle_r2"
    result = run_python_script(
        "scripts/build_public_cloudflare_bundle.py",
        "--static-root",
        str(static_root),
        "--output-root",
        str(output_root),
        "--r2-base-url",
        "https://assets.example.org/ufo",
        "--r2-key-prefix",
        "ufo",
    )

    assert '"ok": true' in result.stdout
    assert (output_root / "cloudflare_bundle_manifest.json").exists()
    assert (output_root / "r2_upload_manifest.json").exists()
    assert (output_root / "upload_r2_assets.ps1").exists()
    assert (output_root / "data" / "startup_profiles" / "manifest.json").exists()
    public_config = json.loads((output_root / "data" / "app_config.json").read_text(encoding="utf-8"))
    assert public_config["startupProfile"]["enabled"] is True
    assert public_config["startupProfile"]["id"] == "france_1954_flap"
    assert public_config["startupProfile"]["renderBeforeGlobalCatalog"] is True
    assert not (output_root / "data" / "canonical_web" / "points.bin").exists()
    r2_manifest = json.loads((output_root / "r2_upload_manifest.json").read_text(encoding="utf-8"))
    assert r2_manifest["r2_key_prefix"] == "ufo"
    assert all(upload["r2_key"].startswith("ufo/data/canonical_web/") for upload in r2_manifest["uploads"])
    upload_paths = {upload["path"] for upload in r2_manifest["uploads"]}
    assert "data/canonical_web/event_chunk_manifest.json" in upload_paths
    assert "data/canonical_web/summary_manifest.json" in upload_paths
    assert "data/canonical_web/points.bin.gz" in upload_paths
    assert "data/canonical_web/summary_shards/summary_000000.json.gz" in upload_paths
    assert "data/canonical_web/summary_shards/summary_000000.json" not in upload_paths


def test_cloudflare_bundle_validator_rejects_crop_r2_payloads_from_pages(tmp_path):
    bundle_root = tmp_path / "cloudflare_bundle_r2"
    crop_root = bundle_root / "data" / "crop_circles"
    crop_root.mkdir(parents=True)
    (bundle_root / "cloudflare_bundle_manifest.json").write_text(
        json.dumps({"pages_safe": True}), encoding="utf-8"
    )
    (bundle_root / "r2_upload_manifest.json").write_text(
        json.dumps(
            {
                "r2_base_url": "https://assets.example.org/releases/v1",
                "r2_key_prefix": "releases/v1",
                "upload_count": 1,
                "uploads": [{"path": "data/file.json", "r2_key": "releases/v1/data/file.json"}],
            }
        ),
        encoding="utf-8",
    )
    (bundle_root / "data" / "app_config.json").write_text(
        json.dumps({"deploymentProfile": {"largeDataBaseUrl": "https://assets.example.org/releases/v1"}}),
        encoding="utf-8",
    )
    (bundle_root / "_headers").write_text(
        "/data/startup_profiles/*\n  Cache-Control: public, max-age=31536000, immutable\n",
        encoding="utf-8",
    )
    (crop_root / "manifest.json").write_text(
        json.dumps(
            {
                "releaseId": "crop-v1",
                "assetBaseUrl": "https://assets.example.org/releases/crop-v1/",
                "points": {
                    "path": "points.json.gz",
                    "bytes": len(b"r2 only"),
                    "sha256": hashlib.sha256(b"r2 only").hexdigest(),
                },
            }
        ),
        encoding="utf-8",
    )
    (crop_root / "points.json.gz").write_bytes(b"r2 only")

    report = validate_cloudflare_bundle.validate_bundle(bundle_root)

    assert report["ok"] is False
    assert report["checks"]["optional_layer_r2_payloads_excluded"] is False
    assert report["checks"]["crop_r2_payloads_excluded"] is False
    assert report["optional_layer_r2_payloads"] == ["data/crop_circles/points.json.gz"]
    assert report["crop_r2_payloads"] == ["data/crop_circles/points.json.gz"]
    assert any("R2-only optional-layer payloads" in error for error in report["errors"])


def test_cloudflare_bundle_validator_rejects_undeclared_animal_review_queue(tmp_path):
    bundle_root = tmp_path / "cloudflare_bundle_r2"
    animal_root = bundle_root / "data" / "animal_mutilations"
    animal_root.mkdir(parents=True)
    (bundle_root / "cloudflare_bundle_manifest.json").write_text(
        json.dumps({"pages_safe": True}), encoding="utf-8"
    )
    (bundle_root / "r2_upload_manifest.json").write_text(
        json.dumps(
            {
                "r2_base_url": "https://assets.example.org/releases/v1",
                "r2_key_prefix": "releases/v1",
                "upload_count": 1,
                "uploads": [{"path": "data/file.json", "r2_key": "releases/v1/data/file.json"}],
            }
        ),
        encoding="utf-8",
    )
    (bundle_root / "data" / "app_config.json").write_text(
        json.dumps({"deploymentProfile": {"largeDataBaseUrl": "https://assets.example.org/releases/v1"}}),
        encoding="utf-8",
    )
    (bundle_root / "_headers").write_text(
        "/data/startup_profiles/*\n  Cache-Control: public, max-age=31536000, immutable\n",
        encoding="utf-8",
    )
    payload = b"r2 only"
    (animal_root / "manifest.json").write_text(
        json.dumps(
            {
                "releaseId": "animal-v1",
                "assetBaseUrl": "https://assets.example.org/releases/animal-v1/",
                "delivery": {
                    "pagesFiles": ["manifest.json"],
                    "immutablePrefix": "releases/animal-v1/",
                    "r2OnlyPaths": ["catalog.json.gz"],
                },
                "catalog": {
                    "path": "catalog.json.gz",
                    "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "r2Only": True,
                },
            }
        ),
        encoding="utf-8",
    )
    (animal_root / "timeline_review_queue.jsonl").write_text("{}\n", encoding="utf-8")

    report = validate_cloudflare_bundle.validate_bundle(bundle_root)

    assert report["ok"] is False
    assert report["undeclared_optional_layer_files"] == [
        "data/animal_mutilations/timeline_review_queue.jsonl"
    ]
    assert any("undeclared optional-layer files" in error for error in report["errors"])


def test_cloudflare_bundle_release_mode_enforces_exact_inventory(tmp_path, monkeypatch):
    bundle_root = tmp_path / "hydrated"
    source_root = tmp_path / "source"
    source_root.mkdir()
    for relative in reproduction.REQUIRED_PAGES_PATHS:
        path = bundle_root.joinpath(*relative.parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("required\n", encoding="utf-8")
    for relative in reproduction.REQUIRED_PAGES_JSON_PATHS:
        path = bundle_root.joinpath(*relative.parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
    write_duration_manifest_stub(bundle_root)
    write_reporting_delay_manifest_stub(bundle_root)
    write_coordinate_evidence_manifest_stub(bundle_root)
    write_time_of_day_manifest_stub(bundle_root)
    (bundle_root / "cloudflare_bundle_manifest.json").write_text(
        json.dumps({"pages_safe": True}), encoding="utf-8"
    )
    (bundle_root / "r2_upload_manifest.json").write_text(
        json.dumps(
            {
                "r2_base_url": "https://assets.example.org/releases/v1",
                "r2_key_prefix": "releases/v1",
                "upload_count": 1,
                "uploads": [{"path": "data/file.json", "r2_key": "releases/v1/data/file.json"}],
            }
        ),
        encoding="utf-8",
    )
    (bundle_root / "data" / "app_config.json").write_text(
        json.dumps({"deploymentProfile": {"largeDataBaseUrl": "https://assets.example.org/releases/v1"}}),
        encoding="utf-8",
    )
    (bundle_root / "_headers").write_text(
        "/data/startup_profiles/*\n  Cache-Control: public, max-age=31536000, immutable\n",
        encoding="utf-8",
    )
    records = [reproduction.file_record(path, relative_to=bundle_root) for path in reproduction.iter_files(bundle_root)]
    release_manifest_path = tmp_path / "release.json"
    release_manifest_path.write_text(
        json.dumps({"pages": {"files": records}, "source_overlay": {"files": []}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(validate_cloudflare_bundle.reproduction, "validate_manifest", lambda manifest: None)

    valid = validate_cloudflare_bundle.validate_bundle(
        bundle_root,
        release_manifest_path=release_manifest_path,
        source_root=source_root,
    )
    assert valid["ok"] is True
    assert valid["checks"]["exact_release_inventory"] is True

    (bundle_root / "unexpected.json").write_text("{}\n", encoding="utf-8")
    invalid = validate_cloudflare_bundle.validate_bundle(
        bundle_root,
        release_manifest_path=release_manifest_path,
        source_root=source_root,
    )
    assert invalid["ok"] is False
    assert invalid["checks"]["exact_release_inventory"] is False
    assert any("unexpected=unexpected.json" in error for error in invalid["errors"])


def test_optional_layer_pages_allowlist_omits_undeclared_working_files(tmp_path):
    static_root = tmp_path / "static"
    layer_root = static_root / "data" / "fixture_layer"
    layer_root.mkdir(parents=True)
    manifest = {
        "delivery": {
            "pagesFiles": ["manifest.json", "public-note.json"],
            "r2OnlyPaths": ["payload.json.gz"],
        },
        "payloads": {
            "payload": {"path": "payload.json.gz", "bytes": 2, "sha256": "0" * 64, "r2Only": True}
        },
    }
    (layer_root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    pages_paths, layer_roots = build_cloudflare_bundle.discover_optional_pages_paths(static_root)
    r2_paths = build_cloudflare_bundle.discover_optional_r2_paths(static_root)

    assert "data/fixture_layer/manifest.json" in pages_paths
    assert "data/fixture_layer/public-note.json" in pages_paths
    assert layer_roots == {"data/fixture_layer"}
    decision = build_cloudflare_bundle.classify_file(
        Path("data/fixture_layer/raw-review.json"),
        10,
        include_gzip_data=False,
        optional_r2_paths=r2_paths,
        optional_pages_paths=pages_paths,
        optional_layer_roots=layer_roots,
    )
    assert decision == {"copy": False, "reason": "optional_layer_undeclared_source_file"}


def test_pages_deploy_wrapper_validates_before_wrangler_and_rejects_raw_source() -> None:
    script = (REPO_ROOT / "scripts" / "cloudflare_deploy_pages.ps1").read_text(encoding="utf-8")

    assert "Refusing to deploy raw webapp/static_public" in script
    assert "--release-manifest" in script
    assert "[string]$Branch" in script
    assert "--branch $Branch" in script
    assert script.index("validate_cloudflare_bundle.py") < script.index("cloudflare_wrangler.ps1")


def test_public_deploy_wrapper_and_package_script_require_and_forward_explicit_branch() -> None:
    script = (REPO_ROOT / "scripts" / "cloudflare_deploy_public.ps1").read_text(encoding="utf-8")
    package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))

    branch_parameter = script.index("[string]$Branch")
    branch_forward = script.index("-Branch $Branch")
    assert "[Parameter(Mandatory = $true)]" in script[:branch_parameter]
    assert "[ValidatePattern('^[A-Za-z0-9._/-]+$')]" in script[:branch_parameter]
    assert branch_forward > branch_parameter
    assert "cloudflare_deploy_pages.ps1" in script
    deploy_command = package["scripts"]["cf:deploy"]
    assert "CLOUDFLARE_PAGES_BRANCH" in deploy_command
    assert "-Branch $env:CLOUDFLARE_PAGES_BRANCH" in deploy_command


def test_custom_pages_404_disables_index_fallback_for_missing_asset_routes() -> None:
    not_found = REPO_ROOT / "webapp" / "static_public" / "404.html"

    assert not_found.is_file()
    content = not_found.read_text(encoding="utf-8").lower()
    assert "<!doctype html>" in content
    assert "file not found" in content
    assert "noindex" in content
