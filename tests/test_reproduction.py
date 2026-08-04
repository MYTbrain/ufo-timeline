from __future__ import annotations

from argparse import Namespace
import gzip
import hashlib
import json
from pathlib import Path
import ssl

import pytest

from scripts import reproduction


def _write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _write_duration_manifest_stub(root: Path) -> None:
    value = {
        "releaseId": "analysis-duration-test-v1",
        "assetBaseUrl": "https://assets.example.test/releases/analysis-duration-test-v1",
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
    _write(root / "data" / "analysis_duration_v1" / "manifest.json", json.dumps(value).encode("utf-8"))


def _write_reporting_delay_manifest_stub(root: Path) -> None:
    value = {
        "releaseId": "analysis-reporting-delay-test-v1",
        "assetBaseUrl": "https://assets.example.test/releases/analysis-reporting-delay-test-v1",
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
    _write(root / "data" / "analysis_reporting_delay_v1" / "manifest.json", json.dumps(value).encode("utf-8"))


def test_deterministic_pages_archive_and_tree_hash(tmp_path: Path) -> None:
    source = tmp_path / "pages"
    _write(source / "index.html", b"<h1>UFO Timeline</h1>\n")
    _write(source / "data" / "app_config.json", b'{"ok": true}\n')
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"

    first_summary = reproduction.deterministic_zip(source, first)
    second_summary = reproduction.deterministic_zip(source, second)

    assert first.read_bytes() == second.read_bytes()
    assert first_summary == second_summary
    assert first_summary["file_count"] == 2
    assert len(first_summary["tree_sha256"]) == 64


def test_safe_relative_path_rejects_escape_and_absolute_paths() -> None:
    for value in ("../escape.json", "/absolute.json", "C:/absolute.json", ""):
        with pytest.raises(reproduction.ContractError):
            reproduction.safe_relative_path(value)


def test_offline_url_localization_is_recursive() -> None:
    base = "https://example.r2.dev/releases/v1"
    value = {
        "manifest": base + "/data/manifest.json",
        "nested": [base, "https://example.com/unchanged"],
    }

    localized = reproduction.replace_url_prefix(value, base, ".")

    assert localized == {
        "manifest": "./data/manifest.json",
        "nested": [".", "https://example.com/unchanged"],
    }


def test_production_normalization_removes_only_cloudflare_pages_analytics() -> None:
    source = b"<body>tool</body>"
    injection = (
        b"<!-- Cloudflare Pages Analytics --><script defer "
        b"src='https://static.cloudflareinsights.com/beacon.min.js' "
        b"data-cf-beacon='{\"token\": \"df011473b8f34ae9a926359e4a1743e6\"}'></script>"
        b"<!-- Cloudflare Pages Analytics -->"
    )
    served = source.replace(b"</body>", injection + b"</body>")

    assert reproduction.normalize_production_source("index.html", served) == source
    assert reproduction.normalize_production_source("app.js", served) == served


def test_production_check_skips_non_public_pages_control_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    source = repo / "webapp" / "static_public"
    _write(source / "index.html", b"<body>tool</body>")
    _write(source / "_headers", b"/*\n  Cache-Control: public\n")
    source_records = [
        reproduction.file_record(path, relative_to=source)
        for path in reproduction.iter_files(source)
    ]
    r2_manifest = b'{"uploads": []}'
    manifest = {
        "release": {
            "canonical_production_url": "https://ufo-timeline.pages.dev",
            "normalized_count": 2,
            "mapped_count": 1,
        },
        "source_overlay": {
            "root": "webapp/static_public",
            "files": source_records,
        },
        "pages": {"files": source_records},
        "r2": {
            "base_url": "https://assets.example.test/releases/core-v1",
            "source_manifest_sha256": hashlib.sha256(r2_manifest).hexdigest(),
        },
    }
    requested: list[str] = []

    def fake_request(url: str, *, timeout: float) -> bytes:
        requested.append(url)
        if url.endswith("/data/app_config.json"):
            return json.dumps(
                {
                    "normalizedCount": 2,
                    "mappedCount": 1,
                    "deploymentProfile": {
                        "largeDataBaseUrl": "https://assets.example.test/releases/core-v1"
                    },
                }
            ).encode("utf-8")
        if url.endswith("/r2_upload_manifest.json"):
            return r2_manifest
        if url.endswith("/index.html"):
            return b"<body>tool</body>"
        raise AssertionError(url)

    monkeypatch.setattr(reproduction, "REPO_ROOT", repo)
    monkeypatch.setattr(reproduction, "request_bytes", fake_request)

    report = reproduction.check_production(manifest, timeout=1)

    assert not any(url.endswith("/_headers") for url in requested)
    assert report["source_file_count"] == 2
    assert report["public_source_file_count"] == 1
    assert report["non_public_pages_control_paths"] == ["_headers"]


def test_cloudflare_tls_compatibility_keeps_certificate_and_hostname_verification() -> None:
    context = reproduction.VERIFIED_SSL_CONTEXT

    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    if hasattr(ssl, "VERIFY_X509_STRICT"):
        assert not context.verify_flags & ssl.VERIFY_X509_STRICT


def test_build_manifest_pins_pages_r2_and_source_overlay(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    pages = repo / "pages"
    source = repo / "source"
    r2_asset = tmp_path / "points.bin.gz"
    _write(repo / ".python-version", b"3.14.6\n")
    _write(repo / ".nvmrc", b"24.18.0\n")
    _write(repo / "requirements.lock", b"locked\n")
    _write(repo / "package-lock.json", b"{}\n")
    monkeypatch.setattr(reproduction, "REPO_ROOT", repo)
    _write(source / "index.html", b"source shell\n")
    _write(pages / "index.html", b"source shell\n")
    _write(r2_asset, b"compressed points")
    _write(
        pages / "data" / "app_config.json",
        json.dumps(
            {
                "staticAssetVersion": "v1",
                "normalizedCount": 2,
                "mappedCount": 1,
            }
        ).encode("utf-8"),
    )
    r2_url = "https://example.r2.dev/releases/v1/data/points.bin.gz"
    r2_manifest = {
        "generated_at_utc": "2026-01-01T00:00:00+00:00",
        "r2_base_url": "https://example.r2.dev/releases/v1",
        "r2_key_prefix": "releases/v1",
        "uploads": [
            {
                "path": "data/points.bin.gz",
                "source_path": str(r2_asset),
                "bytes": r2_asset.stat().st_size,
                "url": r2_url,
                "copied_to_pages": False,
            }
        ],
    }
    _write(
        pages / "r2_upload_manifest.json",
        (json.dumps(r2_manifest, indent=2) + "\n").encode("utf-8"),
    )
    output = tmp_path / "release.json"
    archive = tmp_path / "pages.zip"
    args = Namespace(
        pages_root=pages,
        source_root=source,
        pages_base_url="https://12345678.ufo-timeline.pages.dev",
        pages_deployment_id="12345678-0000-0000-0000-000000000000",
        canonical_production_url="https://ufo-timeline.pages.dev",
        release_id="test-v1",
        archive_output=archive,
        archive_url="https://example.r2.dev/releases/reproduction/test-v1/pages.zip",
        output=output,
    )

    manifest = reproduction.build_manifest(args)

    assert output.is_file()
    assert archive.is_file()
    assert manifest["pages"]["file_count"] == 3
    assert manifest["r2"]["file_count"] == 1
    assert manifest["r2"]["files"][0]["sha256"] == reproduction.sha256_file(r2_asset)
    assert manifest["source_overlay"]["file_count"] == 1
    reproduction.validate_manifest(manifest)


def test_validate_manifest_rejects_duplicate_artifact_paths(tmp_path: Path) -> None:
    record = {"path": "index.html", "bytes": 1, "sha256": "0" * 64}
    collection = {
        "files": [record, dict(record)],
        "file_count": 2,
        "uncompressed_bytes": 2,
        "tree_sha256": reproduction.tree_sha256([record, dict(record)]),
    }
    with pytest.raises(reproduction.ContractError, match="Duplicate Pages path"):
        reproduction.validate_file_collection(
            "Pages",
            collection,
            count_key="file_count",
            bytes_key="uncompressed_bytes",
        )


def test_pages_source_policy_excludes_manifest_declared_optional_layer_payloads(tmp_path: Path) -> None:
    source = tmp_path / "static_public"
    _write(source / "index.html", b"shell\n")
    _write(source / "crop_circle_layer.js", b"runtime\n")
    for layer, release_id, payload_name in (
        ("crop_circles", "crop-v1", "points.json.gz"),
        ("animal_mutilations", "animal-v1", "catalog.json.gz"),
    ):
        payload = gzip.compress(b"[]", mtime=0)
        payload_path = source / "data" / layer / payload_name
        _write(payload_path, payload)
        manifest = {
            "releaseId": release_id,
            "assetBaseUrl": f"https://assets.example.org/releases/{release_id}/",
            "delivery": {
                "pagesFiles": ["manifest.json"],
                "immutablePrefix": f"releases/{release_id}/",
                "r2OnlyPaths": [payload_name],
            },
            "payload": {
                "path": payload_name,
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "r2Only": True,
            },
        }
        _write(
            source / "data" / layer / "manifest.json",
            json.dumps(manifest).encode("utf-8"),
        )

    records = reproduction.pages_source_records(source)
    paths = {record["path"] for record in records}

    assert "index.html" in paths
    assert "crop_circle_layer.js" in paths
    assert "data/crop_circles/manifest.json" in paths
    assert "data/animal_mutilations/manifest.json" in paths
    assert "data/crop_circles/points.json.gz" not in paths
    assert "data/animal_mutilations/catalog.json.gz" not in paths


def test_verify_baseline_uses_pages_source_policy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    source = repo / "webapp" / "static_public"
    _write(source / "index.html", b"shell\n")
    payload = gzip.compress(b"[]", mtime=0)
    _write(source / "data" / "animal_mutilations" / "catalog.json.gz", payload)
    _write(
        source / "data" / "animal_mutilations" / "manifest.json",
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
        ).encode("utf-8"),
    )
    source_records = reproduction.pages_source_records(source)
    manifest = {
        "release": {"id": "test-v1"},
        "source_overlay": {
            "root": "webapp/static_public",
            "tree_sha256": reproduction.tree_sha256(source_records),
            "files": source_records,
        },
        "pages": {"tree_sha256": "0" * 64, "files": []},
        "r2": {"tree_sha256": "1" * 64},
    }
    manifest_path = repo / "reproduction" / "release.json"
    _write(manifest_path, json.dumps(manifest).encode("utf-8"))
    monkeypatch.setattr(reproduction, "REPO_ROOT", repo)
    monkeypatch.setattr(reproduction, "validate_manifest", lambda value: None)

    report = reproduction.verify(
        Namespace(
            manifest=manifest_path,
            check_baseline_source=True,
            check_production=False,
            timeout=1,
        )
    )

    assert report["baseline_source_matches"] is True
    assert report["optional_layer_r2_file_count"] == 1


def test_optional_layer_source_rejects_review_queue_raw_cache_and_images(tmp_path: Path) -> None:
    source = tmp_path / "static_public"
    payload = gzip.compress(b"[]", mtime=0)
    _write(source / "data" / "animal_mutilations" / "catalog.json.gz", payload)
    _write(
        source / "data" / "animal_mutilations" / "manifest.json",
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
        ).encode("utf-8"),
    )
    _write(source / "data" / "animal_mutilations" / "timeline_review_queue.jsonl", b"{}\n")

    with pytest.raises(reproduction.ContractError, match="undeclared files"):
        reproduction.pages_source_records(source)


def test_exact_file_inventory_rejects_unexpected_and_changed_files(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _write(bundle / "index.html", b"known\n")
    expected = [reproduction.file_record(bundle / "index.html", relative_to=bundle)]

    report = reproduction.verify_exact_file_inventory(bundle, expected, label="test bundle")
    assert report["file_count"] == 1

    _write(bundle / "unexpected.json", b"{}\n")
    with pytest.raises(reproduction.ContractError, match="unexpected=unexpected.json"):
        reproduction.verify_exact_file_inventory(bundle, expected, label="test bundle")

    (bundle / "unexpected.json").unlink()
    _write(bundle / "index.html", b"changed\n")
    with pytest.raises(reproduction.ContractError, match="changed=index.html"):
        reproduction.verify_exact_file_inventory(bundle, expected, label="test bundle")


def test_required_pages_json_must_parse(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    for relative in reproduction.REQUIRED_PAGES_PATHS:
        _write(bundle.joinpath(*relative.parts), b"required\n")
    for relative in reproduction.REQUIRED_PAGES_JSON_PATHS:
        _write(bundle.joinpath(*relative.parts), b"{}\n")
    _write_duration_manifest_stub(bundle)
    _write_reporting_delay_manifest_stub(bundle)
    _write(bundle / "data" / "startup_profiles" / "france_1954_flap" / "manifest.json", b"{}\n")

    report = reproduction.verify_required_pages_files(bundle)
    assert "data/event_chunk_manifest.json" in report["parsed_json"]
    assert "data/startup_profiles/france_1954_flap/manifest.json" in report["parsed_json"]

    _write(bundle / "data" / "event_chunk_manifest.json", b"<!doctype html>\n")
    with pytest.raises(reproduction.ContractError, match="Required Pages JSON is invalid: data/event_chunk_manifest.json"):
        reproduction.verify_required_pages_files(bundle)


def test_current_release_pages_inventory_is_exact_baseline_plus_approved_source_assets() -> None:
    manifest = reproduction.load_json(reproduction.REPO_ROOT / "reproduction" / "release.json")
    source_root = reproduction.REPO_ROOT / manifest["source_overlay"]["root"]

    expected, source_records = reproduction.expected_pages_records(manifest, source_root)
    expected_paths = {record["path"] for record in expected}
    source_paths = {record["path"] for record in source_records}

    assert len(manifest["pages"]["files"]) == 134
    assert len(expected) == len({record["path"] for record in [*manifest["pages"]["files"], *source_records]})
    assert "404.html" in expected_paths
    assert "crop_circle_bootstrap.js" in expected_paths
    assert "crop_circle_layer.js" in expected_paths
    assert "data/crop_circles/manifest.json" in expected_paths
    assert "animal_mutilation_bootstrap.js" in expected_paths
    assert "animal_mutilation_layer.js" in expected_paths
    assert "data/animal_mutilations/manifest.json" in expected_paths
    assert "data/crop_circles/points.json.gz" not in source_paths
    assert not any(path.startswith("data/crop_circles/details/") for path in source_paths)
    assert "data/animal_mutilations/points.json.gz" not in source_paths
    assert "data/animal_mutilations/catalog.json.gz" not in source_paths
    assert not any(path.startswith("data/animal_mutilations/details/") for path in source_paths)


def test_offline_hydration_copies_and_localizes_manifest_declared_optional_payloads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    pages = repo / "pages"
    source = repo / "webapp" / "static_public"
    cache = repo / "cache"
    output = repo / "hydrated"
    _write(repo / "requirements.lock", b"locked\n")
    _write(repo / "package-lock.json", b"{}\n")

    for relative in reproduction.REQUIRED_PAGES_PATHS:
        content = b"/data/startup_profiles/*\n  Cache-Control: immutable\n" if relative.name == "_headers" else b"required\n"
        _write(pages.joinpath(*relative.parts), content)
    for relative in reproduction.REQUIRED_PAGES_JSON_PATHS:
        _write(pages.joinpath(*relative.parts), b"{}\n")
    _write_duration_manifest_stub(pages)
    _write_reporting_delay_manifest_stub(pages)
    app_config = {
        "deploymentProfile": {
            "largeDataBaseUrl": "https://assets.example.test/releases/core-v1",
            "target": "cloudflare_pages_r2",
        }
    }
    _write(pages / "data" / "app_config.json", json.dumps(app_config).encode("utf-8"))
    _write(source / "index.html", (pages / "index.html").read_bytes())

    optional_data = gzip.compress(b"[]", mtime=0)
    optional_relative = Path("data/animal_mutilations/catalog.json.gz")
    _write(source / optional_relative, optional_data)
    optional_manifest = {
        "releaseId": "animal-mutilations-test-v1",
        "assetBaseUrl": "https://assets.example.test/releases/animal-mutilations-test-v1/",
        "delivery": {
            "pagesFiles": ["manifest.json"],
            "immutablePrefix": "releases/animal-mutilations-test-v1/",
            "r2OnlyPaths": ["catalog.json.gz"],
        },
        "catalog": {
            "path": "catalog.json.gz",
            "bytes": len(optional_data),
            "sha256": hashlib.sha256(optional_data).hexdigest(),
            "r2Only": True,
        },
    }
    _write(
        source / "data" / "animal_mutilations" / "manifest.json",
        json.dumps(optional_manifest).encode("utf-8"),
    )

    canonical_data = gzip.compress(b"{}", mtime=0)
    canonical_record = {
        "path": "data/canonical_web/core.json.gz",
        "bytes": len(canonical_data),
        "sha256": hashlib.sha256(canonical_data).hexdigest(),
        "url": "https://assets.example.test/releases/core-v1/data/canonical_web/core.json.gz",
    }
    archive = repo / "pages.zip"
    archive_summary = reproduction.deterministic_zip(pages, archive)
    pages_records = [reproduction.file_record(path, relative_to=pages) for path in reproduction.iter_files(pages)]
    source_records = reproduction.pages_source_records(source)
    release = {
        "schema_version": 1,
        "release": {
            "id": "offline-test-v1",
            "canonical_production_url": "https://ufo-timeline.pages.dev",
        },
        "runtime": {
            "python_lockfile": "requirements.lock",
            "node_lockfile": "package-lock.json",
        },
        "source_overlay": {
            "root": "webapp/static_public",
            "file_count": len(source_records),
            "total_bytes": sum(record["bytes"] for record in source_records),
            "tree_sha256": reproduction.tree_sha256(source_records),
            "files": source_records,
        },
        "pages": {
            "deployment_id": "12345678-0000-0000-0000-000000000000",
            "base_url": "https://12345678.ufo-timeline.pages.dev",
            "file_count": len(pages_records),
            "uncompressed_bytes": sum(record["bytes"] for record in pages_records),
            "tree_sha256": reproduction.tree_sha256(pages_records),
            "archive": {
                "url": "https://assets.example.test/releases/reproduction/pages.zip",
                "bytes": archive.stat().st_size,
                "sha256": reproduction.sha256_file(archive),
            },
            "files": pages_records,
        },
        "r2": {
            "base_url": "https://assets.example.test/releases/core-v1",
            "key_prefix": "releases/core-v1",
            "file_count": 1,
            "total_bytes": len(canonical_data),
            "tree_sha256": reproduction.tree_sha256([canonical_record]),
            "files": [canonical_record],
        },
        "offline_localization": {
            "app_config_path": "data/app_config.json",
            "replace_url_prefix": "https://assets.example.test/releases/core-v1",
            "replacement": ".",
        },
    }
    release_path = repo / "reproduction" / "release.json"
    _write(release_path, json.dumps(release).encode("utf-8"))
    monkeypatch.setattr(reproduction, "REPO_ROOT", repo)

    def fake_download(record, target, *, timeout):
        target.parent.mkdir(parents=True, exist_ok=True)
        if record["path"] == "pages-bundle.zip":
            target.write_bytes(archive.read_bytes())
        elif record["path"] == canonical_record["path"]:
            target.write_bytes(canonical_data)
        else:  # pragma: no cover - the fixture has only the two pinned downloads
            raise AssertionError(record["path"])
        return "downloaded"

    monkeypatch.setattr(reproduction, "download_to_path", fake_download)
    report = reproduction.hydrate(
        Namespace(
            manifest=release_path,
            output=output,
            cache=cache,
            offline=True,
            expand_gzip=False,
            jobs=1,
            timeout=1,
        )
    )

    assert (output / optional_relative).read_bytes() == optional_data
    localized = json.loads(
        (output / "data" / "animal_mutilations" / "manifest.json").read_text(encoding="utf-8")
    )
    assert localized["assetBaseUrl"] == "./data/animal_mutilations/"
    assert report["optional_layer_r2"]["file_count"] == 1
    assert report["pages_validation"]["optional_layer_payloads"] == [optional_relative.as_posix()]
