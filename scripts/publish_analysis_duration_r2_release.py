"""Validate and publish the immutable Analysis duration v1 R2 release."""

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
except (ModuleNotFoundError, ImportError):  # Direct script execution.
    import publish_optional_layer_r2_release as optional_r2  # type: ignore[no-redef]


DEFAULT_MANIFEST = Path("webapp/static_public/data/analysis_duration_v1/manifest.json")
DEFAULT_BUCKET = "ufo-timeline-data"
LOCKED_RELEASE_ID = "analysis-duration-v1-20260804"
LOCKED_ASSET_ORIGIN = "https://pub-e9029ab2f6b448daad03d7cde7e15e64.r2.dev"
LOCKED_COUNTS = {
    "catalogRows": 702893,
    "rawDurationRows": 290081,
    "normalizedRows": 246040,
    "descriptiveBinnedRows": 242082,
    "inferentialBinnedRows": 110089,
    "uniqueSourceRawValues": 18118,
}
LOCKED_PAYLOADS = {
    "duration_projection_v1.json": (9634161, "e0077ec47582c8f2839434c86a0da0a69316abde629786018c1ee559f4b4c1fb", 290081),
    "duration_projection_v1.json.gz": (3886442, "9a6287cbd90734d9c4af2428e4203ddc9d1ef0a7ea9b6ca44cfac6de91ef000f", 290081),
    "duration_value_dictionary_v1.json": (1973302, "bd6c59d7f9391d2e831887d480f6109f600a5da456bb29f3401810cee92a3ef0", 18118),
    "duration_value_dictionary_v1.json.gz": (907928, "c5329e0296e7425f328cd16faf15da48a0415c2d5e9a5e1dc13dd8ac15dfc2ed", 18118),
}

ReleaseError = optional_r2.ReleaseError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--wrangler", type=Path, default=Path("node_modules/.bin/wrangler"))
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate local payloads and print the immutable upload plan without network access.",
    )
    return parser.parse_args()


def _integer(value: Any, *, field: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ReleaseError(f"Duration manifest {field} must be an integer") from exc
    if result < 0:
        raise ReleaseError(f"Duration manifest {field} cannot be negative")
    return result


def validate_duration_manifest(
    manifest: dict[str, Any],
    payloads: list[dict[str, Any]],
) -> None:
    release_id = str(manifest.get("releaseId") or "")
    if release_id != LOCKED_RELEASE_ID or not re.fullmatch(r"analysis-duration-v1-\d{8}", release_id):
        raise ReleaseError(f"Duration releaseId must be the locked release {LOCKED_RELEASE_ID}")
    if optional_r2.release_prefix(manifest) != f"releases/{LOCKED_RELEASE_ID}":
        raise ReleaseError("Duration R2 prefix does not match the locked immutable release prefix")
    if str(manifest.get("assetBaseUrl") or "") != f"{LOCKED_ASSET_ORIGIN}/releases/{LOCKED_RELEASE_ID}":
        raise ReleaseError("Duration assetBaseUrl does not use the locked public R2 origin")
    if (
        manifest.get("schemaId") != "ufo-timeline-analysis-duration-artifacts-v1.0.0"
        or manifest.get("schemaVersion") != 1
        or manifest.get("manifestVersion") != "1.0.0"
    ):
        raise ReleaseError("Duration manifest schema identity is not the accepted v1 contract")

    counts = manifest.get("counts")
    if not isinstance(counts, dict):
        raise ReleaseError("Duration manifest counts must be an object")
    actual_counts = {key: _integer(counts.get(key), field=f"counts.{key}") for key in LOCKED_COUNTS}
    if actual_counts != LOCKED_COUNTS:
        raise ReleaseError("Duration manifest counts do not match the deterministic accepted build")
    if counts.get("supportedSources") != ["nuforc", "ufocat"]:
        raise ReleaseError("Duration release must retain the two accepted independent sources")
    if counts.get("bySourceNormalized") != {"majestic": 0, "nuforc": 120879, "ufocat": 125161}:
        raise ReleaseError("Duration source-specific normalized counts changed")

    readiness = manifest.get("readiness")
    gates = readiness.get("materialGates") if isinstance(readiness, dict) else None
    if (
        not isinstance(readiness, dict)
        or readiness.get("status") != "ready_descriptive"
        or readiness.get("assessmentLane") != "descriptive_with_runtime_gated_comparisons"
        or not isinstance(gates, dict)
        or not gates
        or any(value is not True for value in gates.values())
    ):
        raise ReleaseError("Duration readiness and material gates are not release-ready")

    policy = manifest.get("policy")
    required_policy = {
        "binSpanningIntervalsInferentiallyEligible": False,
        "canonicalEventsMutated": False,
        "majesticBareNumericUnitAssigned": False,
        "missingDurationIsZero": False,
        "narrativeDescriptionsRead": False,
        "patternFinderPromotion": False,
        "ufocatApproximateCodesInferentiallyEligible": False,
        "minimumActiveAndReferenceBinN": 20,
        "minimumCommonSupport": 0.8,
        "runtimeCovariates": ["source", "era", "macroregion"],
    }
    if not isinstance(policy, dict) or any(policy.get(key) != value for key, value in required_policy.items()):
        raise ReleaseError("Duration manifest weakens the locked scientific or nonpromotion policy")

    delivery = manifest.get("delivery")
    if not isinstance(delivery, dict) or delivery.get("pagesFiles") != ["manifest.json"]:
        raise ReleaseError("Only the duration manifest may be delivered with Pages")
    if delivery.get("cacheControl") != optional_r2.DEFAULT_CACHE_CONTROL:
        raise ReleaseError("Duration payloads must use immutable one-year cache control")
    payload_by_path = {str(payload.get("path")): payload for payload in payloads}
    if set(payload_by_path) != set(LOCKED_PAYLOADS):
        raise ReleaseError("Duration R2 payload set does not match the locked release")
    if delivery.get("r2OnlyPaths") != [
        "duration_value_dictionary_v1.json",
        "duration_value_dictionary_v1.json.gz",
        "duration_projection_v1.json",
        "duration_projection_v1.json.gz",
    ]:
        raise ReleaseError("Duration delivery.r2OnlyPaths does not match the locked release order")
    for path, (expected_bytes, expected_sha, expected_rows) in LOCKED_PAYLOADS.items():
        payload = payload_by_path[path]
        if (
            _integer(payload.get("bytes"), field=f"payloads.{path}.bytes") != expected_bytes
            or payload.get("sha256") != expected_sha
        ):
            raise ReleaseError(f"Duration payload identity changed: {path}")
        declaration = next(
            (item for item in manifest.get("payloads", {}).values() if isinstance(item, dict) and item.get("path") == path),
            None,
        )
        if not declaration or declaration.get("r2Only") is not True or declaration.get("recordCount") != expected_rows:
            raise ReleaseError(f"Duration payload declaration is incomplete: {path}")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != {"durationProjection", "durationValueDictionary"}:
        raise ReleaseError("Duration browser artifact declarations are incomplete")
    if artifacts["durationProjection"].get("sha256") != LOCKED_PAYLOADS["duration_projection_v1.json"][1]:
        raise ReleaseError("Duration projection browser hash does not match its payload")
    if artifacts["durationValueDictionary"].get("sha256") != LOCKED_PAYLOADS["duration_value_dictionary_v1.json"][1]:
        raise ReleaseError("Duration dictionary browser hash does not match its payload")
    for artifact in artifacts.values():
        if not str(artifact.get("file") or "").startswith(str(manifest["assetBaseUrl"]) + "/"):
            raise ReleaseError("Duration browser artifact URL leaves the immutable release prefix")
        if not str(artifact.get("gzipFile") or "").startswith(str(manifest["assetBaseUrl"]) + "/"):
            raise ReleaseError("Duration gzip artifact URL leaves the immutable release prefix")


def main() -> None:
    args = parse_args()
    report = optional_r2.publish_release(
        manifest_path=args.manifest,
        bucket=args.bucket,
        wrangler=args.wrangler,
        timeout=args.timeout,
        validate_only=args.validate_only,
        validate_manifest=validate_duration_manifest,
        upload_label="analysis-duration",
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
        ReleaseError,
    ) as exc:
        print(f"Analysis duration R2 release failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
