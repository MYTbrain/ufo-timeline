from __future__ import annotations

from argparse import Namespace
import json
from pathlib import Path

import pytest

from scripts import reproduction


def _write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


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


def test_pages_source_policy_excludes_manifest_declared_and_known_crop_r2_payloads(tmp_path: Path) -> None:
    source = tmp_path / "static_public"
    _write(source / "index.html", b"shell\n")
    _write(source / "crop_circle_layer.js", b"runtime\n")
    _write(source / "data" / "crop_circles" / "points.json.gz", b"known points")
    _write(source / "data" / "crop_circles" / "future_points.bin.gz", b"future points")
    _write(source / "data" / "crop_circles" / "details" / "chunk_000.json.gz", b"details")
    _write(
        source / "data" / "crop_circles" / "manifest.json",
        json.dumps(
            {
                "assetBaseUrl": "https://assets.example.org/releases/crop-v1/",
                "points": {"path": "future_points.bin.gz"},
                "details": {"files": [{"path": "details/chunk_000.json.gz"}]},
            }
        ).encode("utf-8"),
    )

    records = reproduction.pages_source_records(source)
    paths = {record["path"] for record in records}

    assert "index.html" in paths
    assert "crop_circle_layer.js" in paths
    assert "data/crop_circles/manifest.json" in paths
    assert "data/crop_circles/points.json.gz" not in paths
    assert "data/crop_circles/future_points.bin.gz" not in paths
    assert "data/crop_circles/details/chunk_000.json.gz" not in paths


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
    _write(bundle / "data" / "startup_profiles" / "france_1954_flap" / "manifest.json", b"{}\n")

    report = reproduction.verify_required_pages_files(bundle)
    assert "data/event_chunk_manifest.json" in report["parsed_json"]
    assert "data/startup_profiles/france_1954_flap/manifest.json" in report["parsed_json"]

    _write(bundle / "data" / "event_chunk_manifest.json", b"<!doctype html>\n")
    with pytest.raises(reproduction.ContractError, match="Required Pages JSON is invalid: data/event_chunk_manifest.json"):
        reproduction.verify_required_pages_files(bundle)


def test_current_release_pages_inventory_is_baseline_plus_four_source_assets() -> None:
    manifest = reproduction.load_json(reproduction.REPO_ROOT / "reproduction" / "release.json")
    source_root = reproduction.REPO_ROOT / manifest["source_overlay"]["root"]

    expected, source_records = reproduction.expected_pages_records(manifest, source_root)
    expected_paths = {record["path"] for record in expected}
    source_paths = {record["path"] for record in source_records}

    assert len(manifest["pages"]["files"]) == 127
    assert len(expected) == 131
    assert "404.html" in expected_paths
    assert "crop_circle_bootstrap.js" in expected_paths
    assert "crop_circle_layer.js" in expected_paths
    assert "data/crop_circles/manifest.json" in expected_paths
    assert "data/crop_circles/points.json.gz" not in source_paths
    assert not any(path.startswith("data/crop_circles/details/") for path in source_paths)
