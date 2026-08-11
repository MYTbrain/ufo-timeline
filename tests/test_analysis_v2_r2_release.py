from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from scripts import build_analysis_v2_artifacts as builder
from scripts import publish_analysis_v2_r2_release as publisher


ARTIFACT_FILES = {
    "animalContextReadiness": "animal_context_readiness.json",
    "contextUfoNeighbors": "context_ufo_neighbors_v1.json",
    "cropContextReadiness": "crop_context_readiness.json",
    "facilityAnalysis": "facility_analysis_v1.json",
    "relationshipReconciliation": "relationship_reconciliation.json",
    "ufoConfigurationNeighbors": "ufo_configuration_neighbors_v1.json",
    "ufoConfigurationPoints": "ufo_configuration_points_v1.json",
    "ufoGeography": "ufo_geography_v1.json",
    "ufoPointNeighbors": "ufo_point_neighbors_v1.json",
    "ufoSpatialPoints": "ufo_spatial_points_v2.json",
}


def _json_pair(root: Path, filename: str, value: object) -> dict[str, object]:
    raw = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8") + b"\n"
    compressed = gzip.compress(raw, mtime=0)
    (root / filename).write_bytes(raw)
    (root / f"{filename}.gz").write_bytes(compressed)
    return {
        "bytes": len(raw),
        "file": f"data/analysis_v2/{filename}",
        "gzipBytes": len(compressed),
        "gzipFile": f"data/analysis_v2/{filename}.gz",
        "gzipSha256": hashlib.sha256(compressed).hexdigest(),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _binary_pair(root: Path, filename: str) -> dict[str, object]:
    raw = b"analysis-binary-fixture\x00\x01"
    compressed = gzip.compress(raw, mtime=0)
    (root / filename).write_bytes(raw)
    (root / f"{filename}.gz").write_bytes(compressed)
    return {
        "bytes": len(raw),
        "file": f"data/analysis_v2/{filename}",
        "gzipBytes": len(compressed),
        "gzipFile": f"data/analysis_v2/{filename}.gz",
        "gzipSha256": hashlib.sha256(compressed).hexdigest(),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _manifest_fixture(root: Path) -> Path:
    root.mkdir(parents=True)
    artifacts = {
        key: _json_pair(root, filename, [[key]])
        for key, filename in ARTIFACT_FILES.items()
    }
    artifacts["ufoGeography"]["binary"] = _binary_pair(root, "ufo_geography_v1.bin")
    snapshot = _json_pair(root, "relationship_source_snapshot.json", [["snapshot"]])
    metadata_raw = b'{"frozen":true}\n'
    metadata_name = "relationship_source_snapshot.meta.json"
    (root / metadata_name).write_bytes(metadata_raw)
    snapshot_metadata = {
        "bytes": len(metadata_raw),
        "file": f"data/analysis_v2/{metadata_name}",
        "sha256": hashlib.sha256(metadata_raw).hexdigest(),
    }
    base_url, delivery, payloads = builder.build_analysis_r2_delivery(
        output_root=root,
        release_id=publisher.LOCKED_RELEASE_ID,
        asset_base_url=(
            f"{publisher.LOCKED_ASSET_ORIGIN}/releases/{publisher.LOCKED_RELEASE_ID}"
        ),
        declaration_roots=[artifacts, snapshot, snapshot_metadata],
    )
    manifest = {
        "artifacts": artifacts,
        "assetBaseUrl": base_url,
        "counts": {"relationshipAssociationEligible": 0},
        "delivery": delivery,
        "manifestVersion": "2.3.0",
        "payloads": payloads,
        "policy": {
            "authenticityAssessments": False,
            "causalInferences": False,
            "chronologySegmentsRead": False,
            "contextProximityFailClosed": True,
            "generalizedCoordinatesKilometerEligible": False,
            "minimumContextEligibleRecordsForInference": 25,
            "roughMarkerAssociationInferenceEligible": False,
            "roughMarkerDefiniteNearEligible": False,
            "traceMetrics": False,
            "travelMetrics": False,
        },
        "releaseId": publisher.LOCKED_RELEASE_ID,
        "schemaId": "ufo-timeline-analysis-evidence-artifacts-v2.3.0",
        "schemaVersion": 2,
        "sources": {
            "relationshipSourceSnapshot": snapshot,
            "relationshipSourceSnapshotMetadata": snapshot_metadata,
            "repeatedProvenanceInputs": [
                {"bytes": 1, "path": "canonical/input.json", "sha256": "0" * 64},
                {"bytes": 1, "path": "canonical/input.json", "sha256": "0" * 64},
            ],
        },
    }
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_analysis_v2_manifest_and_local_payloads_pass_locked_publish_contract(
    tmp_path: Path,
) -> None:
    manifest_path = _manifest_fixture(tmp_path / "analysis_v2")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payloads = publisher.optional_r2.declared_payloads(manifest, manifest_path)

    publisher.validate_analysis_manifest(manifest, payloads)

    assert len(payloads) == publisher.EXPECTED_PAYLOAD_COUNT == 25
    assert [payload["path"] for payload in payloads] == manifest["delivery"]["r2OnlyPaths"]
    assert all(
        payload["r2Key"].startswith(f"releases/{publisher.LOCKED_RELEASE_ID}/")
        for payload in payloads
    )


def test_analysis_v2_publisher_rejects_weakened_noncausal_policy(tmp_path: Path) -> None:
    manifest_path = _manifest_fixture(tmp_path / "analysis_v2")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payloads = publisher.optional_r2.declared_payloads(manifest, manifest_path)
    manifest["policy"]["causalInferences"] = True

    with pytest.raises(publisher.ReleaseError, match="scientific or noncausal"):
        publisher.validate_analysis_manifest(manifest, payloads)


def test_analysis_asset_base_rejects_localhost_and_mutable_paths() -> None:
    with pytest.raises(ValueError, match="absolute HTTPS"):
        builder.analysis_asset_base_url(
            publisher.LOCKED_RELEASE_ID,
            f"http://127.0.0.1/releases/{publisher.LOCKED_RELEASE_ID}",
        )
    with pytest.raises(ValueError, match="absolute HTTPS"):
        builder.analysis_asset_base_url(
            publisher.LOCKED_RELEASE_ID,
            f"https://assets.example.test/current/{publisher.LOCKED_RELEASE_ID}",
        )
