"""Validate and publish the immutable Analysis coordinate-evidence v1 release."""

from __future__ import annotations

import argparse
import hashlib
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


DEFAULT_MANIFEST = Path("webapp/static_public/data/analysis_coordinate_evidence_v1/manifest.json")
DEFAULT_BUCKET = "ufo-timeline-data"
LOCKED_RELEASE_ID = "analysis-coordinate-evidence-v1-20260804"
LOCKED_ASSET_ORIGIN = "https://pub-e9029ab2f6b448daad03d7cde7e15e64.r2.dev"
LOCKED_MANIFEST_SHA256 = "2d1c70e0b90a5a7f4d8f519f36dff07bf370c86a6381229f0d255309c033a4d8"
LOCKED_COUNTS = {
    "catalogRows": 702893,
    "sourceCoordinateRows": 110352,
    "typedRows": 110055,
    "typedCatalogPct": 15.657433,
    "bySourceTyped": {"majestic": 14510, "phenomenainon_updb": 1, "ufocat": 95544},
    "supportedSources": ["majestic", "ufocat"],
}
LOCKED_PAYLOAD_COUNT = 12
LOCKED_PAYLOAD_BYTES = 29_127_049

ReleaseError = optional_r2.ReleaseError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--wrangler", type=Path, default=Path("node_modules/.bin/wrangler"))
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def manifest_sha256(manifest: dict[str, Any]) -> str:
    encoded = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_coordinate_evidence_manifest(
    manifest: dict[str, Any],
    payloads: list[dict[str, Any]],
) -> None:
    release_id = str(manifest.get("releaseId") or "")
    if release_id != LOCKED_RELEASE_ID or not re.fullmatch(r"analysis-coordinate-evidence-v1-\d{8}", release_id):
        raise ReleaseError(f"Coordinate-evidence releaseId must be the locked release {LOCKED_RELEASE_ID}")
    if manifest_sha256(manifest) != LOCKED_MANIFEST_SHA256:
        raise ReleaseError("Coordinate-evidence manifest identity changed from the accepted deterministic build")
    if optional_r2.release_prefix(manifest) != f"releases/{LOCKED_RELEASE_ID}":
        raise ReleaseError("Coordinate-evidence R2 prefix does not match the locked immutable release prefix")
    if str(manifest.get("assetBaseUrl") or "") != f"{LOCKED_ASSET_ORIGIN}/releases/{LOCKED_RELEASE_ID}":
        raise ReleaseError("Coordinate-evidence assetBaseUrl does not use the locked public R2 origin")
    if (
        manifest.get("schemaId") != "ufo-timeline-analysis-coordinate-evidence-artifacts-v1.0.0"
        or manifest.get("schemaVersion") != 1
        or manifest.get("manifestVersion") != "1.0.0"
    ):
        raise ReleaseError("Coordinate-evidence manifest schema identity is not the accepted v1 contract")

    counts = manifest.get("counts")
    if not isinstance(counts, dict) or any(counts.get(key) != value for key, value in LOCKED_COUNTS.items()):
        raise ReleaseError("Coordinate-evidence counts do not match the deterministic accepted build")
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
        raise ReleaseError("Coordinate-evidence readiness and material gates are not release-ready")

    policy = manifest.get("policy")
    required_policy = {
        "canonicalEventsMutated": False,
        "externalGeocodingUsed": False,
        "narrativeDescriptionsRead": False,
        "coordinateRepairApplied": False,
        "precisionPromotionAllowed": False,
        "generalizedMarkersCountAsSourceCoordinates": False,
        "missingCoordinatesCountAsZero": False,
        "unresolvedConflictsExcluded": True,
        "countryBoundsAreExactBoundaries": False,
        "patternFinderPromotion": False,
        "runtimeCovariates": ["source", "era", "macroregion"],
        "minimumCommonSupport": 0.8,
        "minimumActiveAndReferenceBinN": 20,
    }
    if not isinstance(policy, dict) or any(policy.get(key) != value for key, value in required_policy.items()):
        raise ReleaseError("Coordinate-evidence manifest weakens the locked scientific or nonpromotion policy")
    delivery = manifest.get("delivery")
    if not isinstance(delivery, dict) or delivery.get("pagesFiles") != ["manifest.json"]:
        raise ReleaseError("Only the coordinate-evidence manifest may be delivered with Pages")
    if delivery.get("cacheControl") != optional_r2.DEFAULT_CACHE_CONTROL:
        raise ReleaseError("Coordinate-evidence payloads must use immutable one-year cache control")
    if len(payloads) != LOCKED_PAYLOAD_COUNT or sum(item["bytes"] for item in payloads) != LOCKED_PAYLOAD_BYTES:
        raise ReleaseError("Coordinate-evidence R2 payload set changed from the accepted release")

    artifacts = manifest.get("artifacts")
    shard_keys = manifest.get("artifactGroups", {}).get("originalEvidenceShards", [])
    if not isinstance(artifacts, dict) or set(shard_keys) != {
        "originalEvidenceShard000", "originalEvidenceShard001", "originalEvidenceShard002",
        "originalEvidenceShard003", "originalEvidenceShard004",
    }:
        raise ReleaseError("Coordinate original-evidence shard declarations are incomplete")
    if artifacts.get("coordinateEvidenceProjection", {}).get("rowCount") != 110352:
        raise ReleaseError("Coordinate-evidence browser projection row count changed")


def main() -> None:
    args = parse_args()
    report = optional_r2.publish_release(
        manifest_path=args.manifest,
        bucket=args.bucket,
        wrangler=args.wrangler,
        timeout=args.timeout,
        validate_only=args.validate_only,
        validate_manifest=validate_coordinate_evidence_manifest,
        upload_label="analysis-coordinate-evidence",
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError, ReleaseError) as exc:
        print(f"Analysis coordinate-evidence R2 release failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
