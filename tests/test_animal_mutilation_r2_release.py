from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "publish_animal_mutilation_r2_release.py"
SPEC = importlib.util.spec_from_file_location("publish_animal_mutilation_r2_release", SCRIPT_PATH)
PUBLISH = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PUBLISH
assert SPEC.loader is not None
SPEC.loader.exec_module(PUBLISH)
OPTIONAL = PUBLISH.optional_r2


def _payload(root: Path, name: str, value: object) -> dict[str, object]:
    encoded = json.dumps(value, separators=(",", ":")).encode("utf-8")
    compressed = gzip.compress(encoded, mtime=0)
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(compressed)
    return {
        "path": name,
        "bytes": len(compressed),
        "decodedBytes": len(encoded),
        "sha256": hashlib.sha256(compressed).hexdigest(),
        "recordCount": len(value),
        "r2Only": True,
    }


def write_manifest_fixture(root: Path, *, audit_available: bool = True) -> Path:
    points = _payload(root, "points.json.gz", [[index] for index in range(518)])
    catalog = _payload(root, "catalog.json.gz", [[index] for index in range(1177)])
    detail_files = []
    for chunk, (start, end) in enumerate(((0, 250), (250, 500), (500, 750), (750, 1000), (1000, 1177))):
        detail_files.append(
            _payload(
                root,
                f"details/chunk_{chunk:03d}.json.gz",
                {str(index): {"id": index} for index in range(start, end)},
            )
        )
    paths = sorted(
        [str(points["path"]), str(catalog["path"]), *(str(detail["path"]) for detail in detail_files)]
    )
    manifest = {
        "releaseId": PUBLISH.LOCKED_RELEASE_ID,
        "assetBaseUrl": (
            "https://assets.example.test/releases/" + PUBLISH.LOCKED_RELEASE_ID + "/"
        ),
        "counts": {
            "records": 1177,
            "mapped": 518,
            "unmapped": 659,
            "reportedUnreviewed": 1177,
            "exactDay": 921,
            "mappedExactDay": 339,
            "undated": 28,
            "mappedPositions": 400,
            "exactCoordinates": 0,
            "detailChunks": 5,
        },
        "source": {
            "adapterVersion": "animal-mutilation-timeline-adapter-v1.1.1",
            "handoffSchema": "animal-mutilation-timeline-handoff-v1.1.0",
            "releaseCommit": "2" * 40,
            "handoffZipSha256": "3" * 64,
            "handoffManifestSha256": "4" * 64,
            "sourceGeojsonSha256": "5" * 64,
            "coordinateAudit": {
                "available": audit_available,
                "requiredForRelease": True,
                "semanticValidationPassed": True,
                "correctionCount": 479,
                "sha256": "6" * 64,
                "bytes": 1024,
            }
        },
        "policy": {
            "traceEligible": False,
            "traceRole": "context_only",
            "causality": "not_asserted",
            "craftColorEligible": False,
            "playbackEligible": False,
            "relationshipsEligible": False,
            "contentWarningRequired": True,
        },
        "delivery": {
            "pagesFiles": ["manifest.json"],
            "immutablePrefix": "releases/" + PUBLISH.LOCKED_RELEASE_ID + "/",
            "r2OnlyPaths": paths,
        },
        "points": points,
        "catalog": catalog,
        "details": {"files": detail_files},
        "sourceSchema": "animal-mutilation-timeline-overlay-v1.1.0",
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def test_local_payload_hash_size_json_and_counts_are_validated(tmp_path: Path) -> None:
    manifest_path = write_manifest_fixture(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    payloads = PUBLISH.declared_payloads(manifest, manifest_path)
    PUBLISH.validate_animal_manifest(manifest, payloads)

    assert [payload["path"] for payload in payloads] == manifest["delivery"]["r2OnlyPaths"]
    assert all(payload["r2Key"].startswith("releases/animal-mutilations-v1-20260802/") for payload in payloads)


def test_release_fails_closed_without_coordinate_audit(tmp_path: Path) -> None:
    manifest_path = write_manifest_fixture(tmp_path, audit_available=False)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payloads = PUBLISH.declared_payloads(manifest, manifest_path)

    with pytest.raises(PUBLISH.ReleaseError, match="coordinate-normalization audit"):
        PUBLISH.validate_animal_manifest(manifest, payloads)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda manifest: manifest["counts"].__setitem__("mappedPositions", 399), "record counts"),
        (lambda manifest: manifest["policy"].__setitem__("playbackEligible", True), "trace/causality policy"),
        (
            lambda manifest: manifest["source"].__setitem__(
                "releaseCommit", PUBLISH.STALE_RELEASE_COMMIT
            ),
            "corrected handoff release commit",
        ),
        (
            lambda manifest: manifest["source"]["coordinateAudit"].__setitem__(
                "correctionCount", 478
            ),
            "coordinate-normalization audit",
        ),
    ],
)
def test_release_identity_policy_and_scientific_counts_fail_closed(
    tmp_path: Path,
    mutation,
    message: str,
) -> None:
    manifest_path = write_manifest_fixture(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payloads = PUBLISH.declared_payloads(manifest, manifest_path)
    mutation(manifest)

    with pytest.raises(PUBLISH.ReleaseError, match=message):
        PUBLISH.validate_animal_manifest(manifest, payloads)


def test_release_directory_rejects_review_queue_or_other_undeclared_file(tmp_path: Path) -> None:
    manifest_path = write_manifest_fixture(tmp_path)
    (tmp_path / "timeline_review_queue.jsonl").write_text("{}\n", encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    with pytest.raises(PUBLISH.ReleaseError, match="review queues"):
        PUBLISH.declared_payloads(manifest, manifest_path)


def test_remote_preflight_uses_head_then_hash_readback(monkeypatch: pytest.MonkeyPatch) -> None:
    body = b"payload"
    payload = {
        "publicUrl": "https://assets.example.test/releases/v1/payload.json.gz",
        "r2Key": "releases/v1/payload.json.gz",
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
    }
    calls: list[str] = []

    def request(url: str, *, method: str, timeout: float):
        calls.append(method)
        if method == "HEAD":
            return 200, {"Content-Length": str(len(body))}, b""
        return 200, {}, body

    monkeypatch.setattr(OPTIONAL, "request_http", request)

    assert PUBLISH.classify_remote(payload, timeout=1) == "matching"
    assert calls == ["HEAD", "GET"]


def test_remote_preflight_refuses_mismatched_immutable_object(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "publicUrl": "https://assets.example.test/releases/v1/payload.json.gz",
        "r2Key": "releases/v1/payload.json.gz",
        "bytes": 2,
        "sha256": hashlib.sha256(b"[]").hexdigest(),
    }

    def request(url: str, *, method: str, timeout: float):
        if method == "HEAD":
            return 200, {"Content-Length": "2"}, b""
        return 200, {}, b"{}"

    monkeypatch.setattr(OPTIONAL, "request_http", request)

    with pytest.raises(PUBLISH.ReleaseError, match="Refusing to overwrite"):
        PUBLISH.classify_remote(payload, timeout=1)


def test_windows_wrangler_launcher_uses_node_and_pinned_javascript_entrypoint(tmp_path: Path) -> None:
    shim = tmp_path / "node_modules" / ".bin" / "wrangler"
    entrypoint = tmp_path / "node_modules" / "wrangler" / "bin" / "wrangler.js"
    node = tmp_path / "nodejs" / "node.exe"
    for path in (shim, entrypoint, node):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("pinned", encoding="utf-8")

    command = OPTIONAL.resolve_wrangler_command(
        shim,
        platform_name="nt",
        node_executable=node,
    )

    assert command == [str(node.resolve()), str(entrypoint.resolve())]


def test_publish_skips_matching_objects_uploads_only_missing_then_reads_back_all(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = write_manifest_fixture(tmp_path / "layer")
    wrangler = tmp_path / "bin" / "wrangler"
    wrangler.parent.mkdir()
    wrangler.write_text("pinned", encoding="utf-8")
    uploaded: list[str] = []
    verified: list[str] = []
    payload_paths = json.loads(manifest_path.read_text(encoding="utf-8"))["delivery"]["r2OnlyPaths"]
    matching = payload_paths[0]

    monkeypatch.setattr(
        OPTIONAL,
        "classify_remote",
        lambda payload, *, timeout: "matching" if payload["path"] == matching else "missing",
    )
    monkeypatch.setattr(
        OPTIONAL,
        "upload_payload",
        lambda wrangler, bucket, payload: uploaded.append(payload["path"]),
    )
    monkeypatch.setattr(
        OPTIONAL,
        "verify_remote",
        lambda payload, *, timeout: verified.append(payload["path"]),
    )

    report = OPTIONAL.publish_release(
        manifest_path=manifest_path,
        bucket="ufo-timeline-data",
        wrangler=wrangler,
        timeout=1,
        validate_only=False,
        validate_manifest=PUBLISH.validate_animal_manifest,
        upload_label="animal-mutilation",
    )

    assert report["alreadyPresent"] == 1
    assert report["uploaded"] == len(payload_paths) - 1
    assert uploaded == [path for path in payload_paths if path != matching]
    assert verified == payload_paths
