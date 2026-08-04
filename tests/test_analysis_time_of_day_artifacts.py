from __future__ import annotations

from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from scripts import build_cloudflare_bundle, reproduction
from scripts import publish_analysis_time_of_day_r2_release as time_release
from scripts import publish_optional_layer_r2_release as optional_r2


ROOT = Path(__file__).resolve().parents[1]
TIME_ROOT = ROOT / "webapp" / "static_public" / "data" / "analysis_time_of_day_v1"
MANIFEST_PATH = TIME_ROOT / "manifest.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_built_time_of_day_artifacts_are_integral_and_material() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    counts = manifest["counts"]
    assert counts["catalogRows"] == 702_893
    assert counts["rawTimeRows"] == 626_438
    assert counts["typedRows"] == 523_077
    assert counts["typedCatalogPct"] == 74.417728
    assert counts["sentinelAmbiguousRows"] == 70_199
    assert counts["supportedSources"] == [
        "majestic", "mufon", "nuforc", "phenomenainon_updb", "ufocat",
    ]
    assert all(manifest["readiness"]["materialGates"].values())
    assert manifest["policy"]["timezoneInferredFromLocation"] is False
    assert manifest["policy"]["utcConversionApplied"] is False
    assert manifest["policy"]["solarOrTwilightStateInferred"] is False
    assert manifest["policy"]["qualitativePeriodsAssignedMinutes"] is False
    assert manifest["policy"]["midnightOrNoonSentinelsExact"] is False

    decoded = {}
    for key, artifact in manifest["artifacts"].items():
        raw_path = TIME_ROOT / Path(artifact["file"]).name
        gzip_path = TIME_ROOT / Path(artifact["gzipFile"]).name
        assert raw_path.stat().st_size == artifact["bytes"]
        assert gzip_path.stat().st_size == artifact["gzipBytes"]
        assert gzip_path.stat().st_size <= 5_000_000
        assert sha256(raw_path) == artifact["sha256"]
        assert sha256(gzip_path) == artifact["gzipSha256"]
        assert gzip.decompress(gzip_path.read_bytes()) == raw_path.read_bytes()
        decoded[key] = json.loads(raw_path.read_text(encoding="utf-8"))
        assert len(decoded[key]) == artifact["rowCount"]

    dictionary = decoded["timeOfDayValueDictionary"]
    projection = []
    for key in manifest["artifactGroups"]["timeProjectionShards"]:
        projection.extend(decoded[key])
    assert len(projection) == 626_438
    assert all(projection[index][0] < projection[index + 1][0] for index in range(len(projection) - 1))
    assert sum(row[13] for row in dictionary) == len(projection)
    statuses = manifest["codes"]["status"]
    bins = manifest["codes"]["timeBin"]
    for row in dictionary:
        status = statuses[row[3]]
        if status in {"sentinel_ambiguous", "qualitative_period", "invalid_clock", "unparsed"}:
            assert row[5] is None and row[6] is None
            assert bins[row[7]] == bins[row[8]] == "unknown"
        if status != "exact_clock":
            assert bins[row[8]] == "unknown"


def test_time_payload_is_classified_as_immutable_r2_only() -> None:
    discovered = build_cloudflare_bundle.discover_optional_r2_paths(ROOT / "webapp" / "static_public")
    payload = "data/analysis_time_of_day_v1/time_of_day_projection_v1_000.json.gz"
    assert payload in discovered
    assert build_cloudflare_bundle.classify_file(
        Path(payload), 1, include_gzip_data=False, optional_r2_paths=discovered,
    ) == {"copy": False, "reason": "optional_layer_immutable_r2_payload"}
    contracts = reproduction.optional_layer_contracts(
        ROOT / "webapp" / "static_public", validate_local_payloads=True,
    )
    contract = next(item for item in contracts if item["name"] == "analysis_time_of_day_v1")
    assert len(contract["r2_records"]) == 10


def test_locked_time_release_validates_locally() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    payloads = optional_r2.declared_payloads(manifest, MANIFEST_PATH.resolve())
    time_release.validate_time_of_day_manifest(manifest, payloads)
    report = optional_r2.publish_release(
        manifest_path=MANIFEST_PATH,
        bucket="ufo-timeline-data",
        wrangler=Path("node_modules/.bin/wrangler"),
        timeout=1,
        validate_only=True,
        validate_manifest=time_release.validate_time_of_day_manifest,
        upload_label="analysis-time-of-day-test",
    )
    assert report == {
        "releaseId": "analysis-time-of-day-v1-20260804",
        "bucket": "ufo-timeline-data",
        "payloadCount": 10,
        "payloadBytes": 30_254_104,
        "r2Prefix": "releases/analysis-time-of-day-v1-20260804",
        "assetBaseUrl": "https://pub-e9029ab2f6b448daad03d7cde7e15e64.r2.dev/releases/analysis-time-of-day-v1-20260804",
        "validated": True,
    }


def test_time_release_rejects_timezone_inference() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    payloads = optional_r2.declared_payloads(manifest, MANIFEST_PATH.resolve())
    changed = deepcopy(manifest)
    changed["policy"]["timezoneInferredFromLocation"] = True
    with pytest.raises(optional_r2.ReleaseError, match="weakens"):
        time_release.validate_time_of_day_manifest(changed, payloads)
