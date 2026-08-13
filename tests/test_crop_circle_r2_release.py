from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "publish_crop_circle_r2_release.py"
SPEC = importlib.util.spec_from_file_location("publish_crop_circle_r2_release", SCRIPT_PATH)
PUBLISH = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PUBLISH
assert SPEC.loader is not None
SPEC.loader.exec_module(PUBLISH)


def write_manifest_fixture(root: Path) -> Path:
    points = gzip.compress(b"[]", mtime=0)
    detail = gzip.compress(b"{}", mtime=0)
    (root / "details").mkdir(parents=True)
    (root / "points.json.gz").write_bytes(points)
    (root / "details" / "chunk_000.json.gz").write_bytes(detail)
    manifest = {
        "releaseId": "crop-circles-test-v1",
        "assetBaseUrl": "https://assets.example.test/releases/crop-circles-test-v1/",
        "counts": {"detailChunks": 1},
        "points": {
            "path": "points.json.gz",
            "bytes": len(points),
            "sha256": hashlib.sha256(points).hexdigest(),
        },
        "details": {"files": [{
            "path": "details/chunk_000.json.gz",
            "bytes": len(detail),
            "sha256": hashlib.sha256(detail).hexdigest(),
        }]},
    }
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_declared_payloads_validate_hashes_and_immutable_prefix(tmp_path: Path) -> None:
    manifest_path = write_manifest_fixture(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    payloads = PUBLISH.declared_payloads(manifest, manifest_path)

    assert [item["path"] for item in payloads] == ["points.json.gz", "details/chunk_000.json.gz"]
    assert payloads[0]["r2Key"] == "releases/crop-circles-test-v1/points.json.gz"


def test_declared_payloads_reject_hash_drift(tmp_path: Path) -> None:
    manifest_path = write_manifest_fixture(tmp_path)
    (tmp_path / "points.json.gz").write_bytes(b"changed")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    with pytest.raises(PUBLISH.ReleaseError, match="does not match manifest"):
        PUBLISH.declared_payloads(manifest, manifest_path)


def test_release_prefix_must_end_with_release_id() -> None:
    with pytest.raises(PUBLISH.ReleaseError, match="must end"):
        PUBLISH.release_prefix({
            "releaseId": "crop-circles-v2",
            "assetBaseUrl": "https://assets.example.test/releases/crop-circles-v1/",
        })


def test_mismatched_existing_object_is_never_overwritten(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "publicUrl": "https://assets.example.test/releases/v1/points.json.gz",
        "r2Key": "releases/v1/points.json.gz",
        "bytes": 2,
        "sha256": hashlib.sha256(b"[]").hexdigest(),
    }
    monkeypatch.setattr(PUBLISH, "request_bytes", lambda *args, **kwargs: (200, b"{}"))

    with pytest.raises(PUBLISH.ReleaseError, match="Refusing to overwrite"):
        PUBLISH.classify_remote(payload, timeout=1)


def test_windows_wrangler_launcher_uses_node_entrypoint(
    tmp_path: Path,
) -> None:
    node_modules = tmp_path / "node_modules"
    shim = node_modules / ".bin" / "wrangler"
    entrypoint = node_modules / "wrangler" / "bin" / "wrangler.js"
    node = tmp_path / "node.exe"
    shim.parent.mkdir(parents=True)
    entrypoint.parent.mkdir(parents=True)
    shim.write_text("shim", encoding="utf-8")
    entrypoint.write_text("entrypoint", encoding="utf-8")
    node.write_text("node", encoding="utf-8")
    assert PUBLISH.resolve_wrangler_command(
        shim,
        platform_name="nt",
        node_executable=node,
    ) == [str(node.resolve()), str(entrypoint.resolve())]
