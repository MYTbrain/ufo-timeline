"""Validate and publish the immutable Analysis witness-count v1 R2 release."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

try:
    from scripts import publish_optional_layer_r2_release as optional_r2
except (ModuleNotFoundError, ImportError):
    import publish_optional_layer_r2_release as optional_r2  # type: ignore


DEFAULT_MANIFEST = Path("webapp/static_public/data/analysis_witness_count_v1/manifest.json")
DEFAULT_BUCKET = "ufo-timeline-data"
LOCKED_RELEASE_ID = "analysis-witness-count-v1-20260804"
LOCKED_ASSET_ORIGIN = "https://pub-e9029ab2f6b448daad03d7cde7e15e64.r2.dev"
LOCKED_COUNTS = {
    "catalogRows": 702893,
    "rawWitnessCountRows": 145289,
    "uniqueSourceRawValues": 229,
    "typedRows": 135868,
    "exactCountRows": 135868,
    "descriptiveBinnedRows": 135868,
    "zeroSentinelRows": 9332,
    "negativeSentinelRows": 89,
    "highCountRows100Plus": 446,
    "extremeCountRows1000Plus": 84,
    "credentialTaggedRows": 1710,
    "maximumExactCount": 20000,
}
LOCKED_ARTIFACTS = {
    "witnessCountValueDictionary": (
        "witness_count_value_dictionary_v1", 24785,
        "9408347c1c23214b68656ca8cdbb724b34e7e510835be5688f82c431f9dcaf5d",
        11687, "a95a626353da9a563bd4c0b7c416eefd9b4fe35559d23667349f4b31133edd61", 229,
    ),
    "witnessCountProjectionShard000": (
        "witness_count_projection_v1_000", 4561476,
        "ec9803433314193014c078ecb17e3b18c760ed9218c5ca31ccf78306f52e64b7",
        1760324, "351ddf61ba6d56d54349e82edf88be8283c1d53523d75558d2f44a5ecaa6370e", 145289,
    ),
}

ReleaseError = optional_r2.ReleaseError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--wrangler", type=Path, default=Path("node_modules/.bin/wrangler"))
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def _integer(value: Any, *, field: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ReleaseError(f"Witness-count manifest {field} must be an integer") from exc
    if result < 0:
        raise ReleaseError(f"Witness-count manifest {field} cannot be negative")
    return result


def validate_witness_count_manifest(manifest: dict[str, Any], payloads: list[dict[str, Any]]) -> None:
    release_id = str(manifest.get("releaseId") or "")
    if release_id != LOCKED_RELEASE_ID or not re.fullmatch(r"analysis-witness-count-v1-\d{8}", release_id):
        raise ReleaseError(f"Witness-count releaseId must be the locked release {LOCKED_RELEASE_ID}")
    if optional_r2.release_prefix(manifest) != f"releases/{LOCKED_RELEASE_ID}":
        raise ReleaseError("Witness-count R2 prefix does not match the locked immutable release prefix")
    if str(manifest.get("assetBaseUrl") or "") != f"{LOCKED_ASSET_ORIGIN}/releases/{LOCKED_RELEASE_ID}":
        raise ReleaseError("Witness-count assetBaseUrl does not use the locked public R2 origin")
    if (
        manifest.get("schemaId") != "ufo-timeline-analysis-witness-count-artifacts-v1.0.0"
        or manifest.get("schemaVersion") != 1
        or manifest.get("manifestVersion") != "1.0.0"
    ):
        raise ReleaseError("Witness-count manifest schema identity is not the accepted v1 contract")

    counts = manifest.get("counts")
    if not isinstance(counts, dict):
        raise ReleaseError("Witness-count manifest counts must be an object")
    if {key: _integer(counts.get(key), field=f"counts.{key}") for key in LOCKED_COUNTS} != LOCKED_COUNTS:
        raise ReleaseError("Witness-count manifest counts do not match the deterministic accepted build")
    if counts.get("supportedSources") != ["nuforc"] or counts.get("bySourceTyped") != {"nuforc": 135868}:
        raise ReleaseError("Witness-count release must retain exactly the accepted one-source NUFORC lane")

    readiness = manifest.get("readiness")
    gates = readiness.get("materialGates") if isinstance(readiness, dict) else None
    if (
        not isinstance(readiness, dict)
        or readiness.get("status") != "ready_descriptive"
        or readiness.get("assessmentLane") != "single_source_descriptive_only"
        or not isinstance(gates, dict)
        or not gates
        or any(value is not True for value in gates.values())
    ):
        raise ReleaseError("Witness-count readiness and material gates are not release-ready")

    policy = manifest.get("policy")
    required_policy = {
        "canonicalEventsMutated": False,
        "explicitSourceFieldOnly": True,
        "sourceFieldName": "No of observers",
        "narrativeDescriptionsRead": False,
        "missingCountIsZeroOrOne": False,
        "qualitativePartySizeIsExact": False,
        "approximateRangeOrLowerBoundIsExact": False,
        "credentialMetadataIsCredibilityEvidence": False,
        "extremeCountsDiscarded": False,
        "crossSourceComparison": False,
        "activeReferenceInference": False,
        "patternFinderPromotion": False,
        "credibilityIncidenceAuthenticityRiskOrCausalClaims": False,
    }
    if not isinstance(policy, dict) or any(policy.get(key) != value for key, value in required_policy.items()):
        raise ReleaseError("Witness-count manifest weakens the locked scientific or nonpromotion policy")

    delivery = manifest.get("delivery")
    if not isinstance(delivery, dict) or delivery.get("pagesFiles") != ["manifest.json"]:
        raise ReleaseError("Only the witness-count manifest may be delivered with Pages")
    if delivery.get("cacheControl") != optional_r2.DEFAULT_CACHE_CONTROL:
        raise ReleaseError("Witness-count payloads must use immutable one-year cache control")
    expected_paths: list[str] = []
    for stem, *_unused in LOCKED_ARTIFACTS.values():
        expected_paths.extend([f"{stem}.json", f"{stem}.json.gz"])
    if delivery.get("r2OnlyPaths") != expected_paths:
        raise ReleaseError("Witness-count delivery.r2OnlyPaths does not match the locked release order")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != set(LOCKED_ARTIFACTS):
        raise ReleaseError("Witness-count browser artifact declarations are incomplete")
    payload_by_path = {str(payload.get("path")): payload for payload in payloads}
    if set(payload_by_path) != set(expected_paths):
        raise ReleaseError("Witness-count R2 payload set does not match the locked release")
    for key, (stem, raw_bytes, raw_sha, gzip_bytes, gzip_sha, rows) in LOCKED_ARTIFACTS.items():
        artifact = artifacts[key]
        if (
            artifact.get("sha256") != raw_sha or artifact.get("gzipSha256") != gzip_sha
            or _integer(artifact.get("bytes"), field=f"artifacts.{key}.bytes") != raw_bytes
            or _integer(artifact.get("gzipBytes"), field=f"artifacts.{key}.gzipBytes") != gzip_bytes
            or _integer(artifact.get("rowCount"), field=f"artifacts.{key}.rowCount") != rows
        ):
            raise ReleaseError(f"Witness-count artifact identity changed: {key}")
        if not str(artifact.get("file") or "").startswith(str(manifest["assetBaseUrl"]) + "/"):
            raise ReleaseError(f"Witness-count artifact URL leaves the immutable release prefix: {key}")
        for path, expected_bytes, expected_sha in (
            (f"{stem}.json", raw_bytes, raw_sha),
            (f"{stem}.json.gz", gzip_bytes, gzip_sha),
        ):
            payload = payload_by_path[path]
            if _integer(payload.get("bytes"), field=f"payloads.{path}.bytes") != expected_bytes or payload.get("sha256") != expected_sha:
                raise ReleaseError(f"Witness-count payload identity changed: {path}")
            declaration = next(
                (item for item in manifest.get("payloads", {}).values() if isinstance(item, dict) and item.get("path") == path),
                None,
            )
            if not declaration or declaration.get("r2Only") is not True or declaration.get("recordCount") != rows:
                raise ReleaseError(f"Witness-count payload declaration is incomplete: {path}")
    if manifest.get("artifactGroups", {}).get("witnessCountProjectionShards") != ["witnessCountProjectionShard000"]:
        raise ReleaseError("Witness-count projection shard order changed")


def main() -> None:
    args = parse_args()
    report = optional_r2.publish_release(
        manifest_path=args.manifest,
        bucket=args.bucket,
        wrangler=args.wrangler,
        timeout=args.timeout,
        validate_only=args.validate_only,
        validate_manifest=validate_witness_count_manifest,
        upload_label="analysis-witness-count",
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError, ReleaseError) as exc:
        print(f"Analysis witness-count R2 release failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
