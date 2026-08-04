"""Validate and publish the immutable Analysis time-of-day v1 R2 release."""

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


DEFAULT_MANIFEST = Path("webapp/static_public/data/analysis_time_of_day_v1/manifest.json")
DEFAULT_BUCKET = "ufo-timeline-data"
LOCKED_RELEASE_ID = "analysis-time-of-day-v1-20260804"
LOCKED_ASSET_ORIGIN = "https://pub-e9029ab2f6b448daad03d7cde7e15e64.r2.dev"
LOCKED_COUNTS = {
    "catalogRows": 702893,
    "rawTimeRows": 626438,
    "uniqueSourceRawValues": 8715,
    "typedRows": 523077,
    "exactInferentialRows": 511394,
    "descriptiveBinnedRows": 512354,
    "sentinelAmbiguousRows": 70199,
}
LOCKED_ARTIFACTS = {
    "timeOfDayValueDictionary": ("time_of_day_value_dictionary_v1", 966952, "7abd31656e4461eb740c27fb2bd6acb11d9644e72d88ffeda782f250bf3fe3e1", 436548, "1002cee1040008153a6c5889e12ca74b28eff8699aecd9b9ac2f0d2aaf58ad8e", 8715),
    "timeOfDayProjectionShard000": ("time_of_day_projection_v1_000", 6446948, "05c635d2490b8cabe18a7acb29358ca03386fec279d6449dec00e2063ee8e1bd", 2690356, "46fac3c4b868c8b0894dcbb32311893bc743570d93b52ea3d7b9d834d1d3aeb9", 200000),
    "timeOfDayProjectionShard001": ("time_of_day_projection_v1_001", 6547889, "2b8444de4adb63bf172db82d94b7d559c295cebbd2985654e07a0e792c915097", 2697088, "38d8681dc0fbf8fac21253616566478010087f8aff1d1d1150c464d017047c43", 200000),
    "timeOfDayProjectionShard002": ("time_of_day_projection_v1_002", 6547839, "046c127a4a85200c5dc4bb22c44a04dd3d182002c060c6e97a55a64fa2f3cc37", 2697306, "52d1900e67081ab44c967dfa74ad34babb8927ecbd4f1cd5b4562cf0be63523d", 200000),
    "timeOfDayProjectionShard003": ("time_of_day_projection_v1_003", 865730, "6237efb1cec8969d22eafbf8a884fcfa2ca5b8ed2b50e1624d0d7db96e8a26b1", 357448, "d2396d5b38cac8008c52758016e6f7350711d43cd81956470feef626319b7834", 26438),
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
        raise ReleaseError(f"Time-of-day manifest {field} must be an integer") from exc
    if result < 0:
        raise ReleaseError(f"Time-of-day manifest {field} cannot be negative")
    return result


def validate_time_of_day_manifest(manifest: dict[str, Any], payloads: list[dict[str, Any]]) -> None:
    release_id = str(manifest.get("releaseId") or "")
    if release_id != LOCKED_RELEASE_ID or not re.fullmatch(r"analysis-time-of-day-v1-\d{8}", release_id):
        raise ReleaseError(f"Time-of-day releaseId must be the locked release {LOCKED_RELEASE_ID}")
    if optional_r2.release_prefix(manifest) != f"releases/{LOCKED_RELEASE_ID}":
        raise ReleaseError("Time-of-day R2 prefix does not match the locked immutable release prefix")
    if str(manifest.get("assetBaseUrl") or "") != f"{LOCKED_ASSET_ORIGIN}/releases/{LOCKED_RELEASE_ID}":
        raise ReleaseError("Time-of-day assetBaseUrl does not use the locked public R2 origin")
    if (
        manifest.get("schemaId") != "ufo-timeline-analysis-time-of-day-artifacts-v1.0.0"
        or manifest.get("schemaVersion") != 1
        or manifest.get("manifestVersion") != "1.0.0"
    ):
        raise ReleaseError("Time-of-day manifest schema identity is not the accepted v1 contract")

    counts = manifest.get("counts")
    if not isinstance(counts, dict):
        raise ReleaseError("Time-of-day manifest counts must be an object")
    if {key: _integer(counts.get(key), field=f"counts.{key}") for key in LOCKED_COUNTS} != LOCKED_COUNTS:
        raise ReleaseError("Time-of-day manifest counts do not match the deterministic accepted build")
    if counts.get("supportedSources") != ["majestic", "mufon", "nuforc", "phenomenainon_updb", "ufocat"]:
        raise ReleaseError("Time-of-day release must retain all five accepted source families")
    if counts.get("bySourceTyped") != {
        "majestic": 14098, "mufon": 95647, "nuforc": 123468,
        "phenomenainon_updb": 121405, "ufocat": 168459,
    }:
        raise ReleaseError("Time-of-day source-specific typed counts changed")

    readiness = manifest.get("readiness")
    gates = readiness.get("materialGates") if isinstance(readiness, dict) else None
    if (
        not isinstance(readiness, dict)
        or readiness.get("status") != "ready_descriptive"
        or readiness.get("assessmentLane") != "descriptive_with_exact_clock_runtime_gated_comparisons"
        or not isinstance(gates, dict)
        or not gates
        or any(value is not True for value in gates.values())
    ):
        raise ReleaseError("Time-of-day readiness and material gates are not release-ready")

    policy = manifest.get("policy")
    required_policy = {
        "canonicalEventsMutated": False,
        "narrativeDescriptionsRead": False,
        "missingTimeIsMidnight": False,
        "midnightOrNoonSentinelsExact": False,
        "timezoneInferredFromLocation": False,
        "utcConversionApplied": False,
        "solarOrTwilightStateInferred": False,
        "qualitativePeriodsAssignedMinutes": False,
        "approximateOrRangeValuesInferentiallyEligible": False,
        "patternFinderPromotion": False,
        "runtimeCovariates": ["source", "era", "macroregion"],
        "minimumCommonSupport": 0.8,
        "minimumActiveAndReferenceBinN": 20,
    }
    if not isinstance(policy, dict) or any(policy.get(key) != value for key, value in required_policy.items()):
        raise ReleaseError("Time-of-day manifest weakens the locked scientific or nonpromotion policy")

    delivery = manifest.get("delivery")
    if not isinstance(delivery, dict) or delivery.get("pagesFiles") != ["manifest.json"]:
        raise ReleaseError("Only the time-of-day manifest may be delivered with Pages")
    if delivery.get("cacheControl") != optional_r2.DEFAULT_CACHE_CONTROL:
        raise ReleaseError("Time-of-day payloads must use immutable one-year cache control")
    expected_paths = []
    for stem, *_unused in LOCKED_ARTIFACTS.values():
        expected_paths.extend([f"{stem}.json", f"{stem}.json.gz"])
    if delivery.get("r2OnlyPaths") != expected_paths:
        raise ReleaseError("Time-of-day delivery.r2OnlyPaths does not match the locked release order")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != set(LOCKED_ARTIFACTS):
        raise ReleaseError("Time-of-day browser artifact declarations are incomplete")
    payload_by_path = {str(payload.get("path")): payload for payload in payloads}
    if set(payload_by_path) != set(expected_paths):
        raise ReleaseError("Time-of-day R2 payload set does not match the locked release")
    for key, (stem, raw_bytes, raw_sha, gzip_bytes, gzip_sha, rows) in LOCKED_ARTIFACTS.items():
        artifact = artifacts[key]
        if (
            artifact.get("sha256") != raw_sha or artifact.get("gzipSha256") != gzip_sha
            or _integer(artifact.get("bytes"), field=f"artifacts.{key}.bytes") != raw_bytes
            or _integer(artifact.get("gzipBytes"), field=f"artifacts.{key}.gzipBytes") != gzip_bytes
            or _integer(artifact.get("rowCount"), field=f"artifacts.{key}.rowCount") != rows
        ):
            raise ReleaseError(f"Time-of-day artifact identity changed: {key}")
        if not str(artifact.get("file") or "").startswith(str(manifest["assetBaseUrl"]) + "/"):
            raise ReleaseError(f"Time-of-day artifact URL leaves the immutable release prefix: {key}")
        for path, expected_bytes, expected_sha in (
            (f"{stem}.json", raw_bytes, raw_sha),
            (f"{stem}.json.gz", gzip_bytes, gzip_sha),
        ):
            payload = payload_by_path[path]
            if _integer(payload.get("bytes"), field=f"payloads.{path}.bytes") != expected_bytes or payload.get("sha256") != expected_sha:
                raise ReleaseError(f"Time-of-day payload identity changed: {path}")
            declaration = next(
                (item for item in manifest.get("payloads", {}).values() if isinstance(item, dict) and item.get("path") == path),
                None,
            )
            if not declaration or declaration.get("r2Only") is not True or declaration.get("recordCount") != rows:
                raise ReleaseError(f"Time-of-day payload declaration is incomplete: {path}")

    shard_keys = manifest.get("artifactGroups", {}).get("timeProjectionShards", [])
    if shard_keys != [f"timeOfDayProjectionShard{index:03d}" for index in range(4)]:
        raise ReleaseError("Time-of-day projection shard order changed")


def main() -> None:
    args = parse_args()
    report = optional_r2.publish_release(
        manifest_path=args.manifest,
        bucket=args.bucket,
        wrangler=args.wrangler,
        timeout=args.timeout,
        validate_only=args.validate_only,
        validate_manifest=validate_time_of_day_manifest,
        upload_label="analysis-time-of-day",
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError, ReleaseError) as exc:
        print(f"Analysis time-of-day R2 release failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
