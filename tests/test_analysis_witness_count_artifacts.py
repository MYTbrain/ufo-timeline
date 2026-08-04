from __future__ import annotations

from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from scripts import build_cloudflare_bundle, reproduction
from scripts import publish_analysis_witness_count_r2_release as witness_release
from scripts import publish_optional_layer_r2_release as optional_r2


ROOT = Path(__file__).resolve().parents[1]
WITNESS_ROOT = ROOT / "webapp" / "static_public" / "data" / "analysis_witness_count_v1"
MANIFEST_PATH = WITNESS_ROOT / "manifest.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_built_witness_count_artifacts_are_integral_and_material() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    counts = manifest["counts"]
    assert counts["catalogRows"] == 702_893
    assert counts["rawWitnessCountRows"] == 145_289
    assert counts["typedRows"] == counts["exactCountRows"] == 135_868
    assert counts["typedCatalogPct"] == 19.329827
    assert counts["zeroSentinelRows"] == 9_332
    assert counts["negativeSentinelRows"] == 89
    assert counts["extremeCountRows1000Plus"] == 84
    assert counts["maximumExactCount"] == 20_000
    assert counts["supportedSources"] == ["nuforc"]
    assert all(manifest["readiness"]["materialGates"].values())
    assert manifest["readiness"]["assessmentLane"] == "single_source_descriptive_only"
    assert manifest["policy"]["narrativeDescriptionsRead"] is False
    assert manifest["policy"]["missingCountIsZeroOrOne"] is False
    assert manifest["policy"]["qualitativePartySizeIsExact"] is False
    assert manifest["policy"]["crossSourceComparison"] is False
    assert manifest["policy"]["activeReferenceInference"] is False
    assert manifest["policy"]["patternFinderPromotion"] is False
    assert manifest["policy"]["credentialMetadataIsCredibilityEvidence"] is False

    decoded = {}
    for key, artifact in manifest["artifacts"].items():
        raw_path = WITNESS_ROOT / Path(artifact["file"]).name
        gzip_path = WITNESS_ROOT / Path(artifact["gzipFile"]).name
        assert raw_path.stat().st_size == artifact["bytes"]
        assert gzip_path.stat().st_size == artifact["gzipBytes"]
        assert gzip_path.stat().st_size <= 5_000_000
        assert sha256(raw_path) == artifact["sha256"]
        assert sha256(gzip_path) == artifact["gzipSha256"]
        assert gzip.decompress(gzip_path.read_bytes()) == raw_path.read_bytes()
        decoded[key] = json.loads(raw_path.read_text(encoding="utf-8"))
        assert len(decoded[key]) == artifact["rowCount"]

    dictionary = decoded["witnessCountValueDictionary"]
    projection = []
    for key in manifest["artifactGroups"]["witnessCountProjectionShards"]:
        projection.extend(decoded[key])
    assert len(projection) == 145_289
    assert all(projection[index][0] < projection[index + 1][0] for index in range(len(projection) - 1))
    assert sum(row[12] for row in dictionary) == len(projection)
    statuses = manifest["codes"]["status"]
    bins = manifest["codes"]["witnessCountBin"]
    for row in dictionary:
        assert hashlib.sha256(row[2].encode("utf-8")).hexdigest() == row[1]
        status = statuses[row[3]]
        if status == "exact_count":
            assert row[5] == row[6] == row[7]
            assert row[5] > 0
            assert bins[row[8]] != "unknown"
        else:
            assert row[5] is None
            assert bins[row[8]] == "unknown"


def test_witness_payload_is_classified_as_immutable_r2_only() -> None:
    discovered = build_cloudflare_bundle.discover_optional_r2_paths(ROOT / "webapp" / "static_public")
    payload = "data/analysis_witness_count_v1/witness_count_projection_v1_000.json.gz"
    assert payload in discovered
    assert build_cloudflare_bundle.classify_file(
        Path(payload), 1, include_gzip_data=False, optional_r2_paths=discovered,
    ) == {"copy": False, "reason": "optional_layer_immutable_r2_payload"}
    contracts = reproduction.optional_layer_contracts(
        ROOT / "webapp" / "static_public", validate_local_payloads=True,
    )
    contract = next(item for item in contracts if item["name"] == "analysis_witness_count_v1")
    assert len(contract["r2_records"]) == 4


def test_locked_witness_release_validates_locally() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    payloads = optional_r2.declared_payloads(manifest, MANIFEST_PATH.resolve())
    witness_release.validate_witness_count_manifest(manifest, payloads)
    report = optional_r2.publish_release(
        manifest_path=MANIFEST_PATH,
        bucket="ufo-timeline-data",
        wrangler=Path("node_modules/.bin/wrangler"),
        timeout=1,
        validate_only=True,
        validate_manifest=witness_release.validate_witness_count_manifest,
        upload_label="analysis-witness-count-test",
    )
    assert report == {
        "releaseId": "analysis-witness-count-v1-20260804",
        "bucket": "ufo-timeline-data",
        "payloadCount": 4,
        "payloadBytes": 6_358_272,
        "r2Prefix": "releases/analysis-witness-count-v1-20260804",
        "assetBaseUrl": "https://pub-e9029ab2f6b448daad03d7cde7e15e64.r2.dev/releases/analysis-witness-count-v1-20260804",
        "validated": True,
    }


def test_witness_release_rejects_cross_source_or_credibility_promotion() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    payloads = optional_r2.declared_payloads(manifest, MANIFEST_PATH.resolve())
    for key in ("crossSourceComparison", "activeReferenceInference", "patternFinderPromotion", "credentialMetadataIsCredibilityEvidence"):
        changed = deepcopy(manifest)
        changed["policy"][key] = True
        with pytest.raises(optional_r2.ReleaseError, match="weakens"):
            witness_release.validate_witness_count_manifest(changed, payloads)
