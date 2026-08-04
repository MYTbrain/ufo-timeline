"""Validate and publish the immutable Analysis reporting-delay v1 R2 release."""

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


DEFAULT_MANIFEST = Path("webapp/static_public/data/analysis_reporting_delay_v1/manifest.json")
DEFAULT_BUCKET = "ufo-timeline-data"
LOCKED_RELEASE_ID = "analysis-reporting-delay-v1-20260804"
LOCKED_ASSET_ORIGIN = "https://pub-e9029ab2f6b448daad03d7cde7e15e64.r2.dev"
LOCKED_MANIFEST_SHA256 = "332c2b39a17715cd255d6c3a39ac0d175db1d379b6327ddb91c2499aa6e53fd9"
LOCKED_COUNTS = {
    "catalogRows": 702893,
    "dateRoleEvidenceRows": 270461,
    "typedRows": 261331,
    "typedCatalogPct": 37.179343,
    "bySourceTyped": {"mufon": 113016, "nuforc": 148315},
    "supportedSources": ["mufon", "nuforc"],
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


def manifest_sha256(manifest: dict[str, Any]) -> str:
    encoded = (
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_reporting_delay_manifest(
    manifest: dict[str, Any],
    payloads: list[dict[str, Any]],
) -> None:
    release_id = str(manifest.get("releaseId") or "")
    if release_id != LOCKED_RELEASE_ID or not re.fullmatch(r"analysis-reporting-delay-v1-\d{8}", release_id):
        raise ReleaseError(f"Reporting-delay releaseId must be the locked release {LOCKED_RELEASE_ID}")
    if manifest_sha256(manifest) != LOCKED_MANIFEST_SHA256:
        raise ReleaseError("Reporting-delay manifest identity changed from the accepted deterministic build")
    if optional_r2.release_prefix(manifest) != f"releases/{LOCKED_RELEASE_ID}":
        raise ReleaseError("Reporting-delay R2 prefix does not match the locked immutable release prefix")
    if str(manifest.get("assetBaseUrl") or "") != f"{LOCKED_ASSET_ORIGIN}/releases/{LOCKED_RELEASE_ID}":
        raise ReleaseError("Reporting-delay assetBaseUrl does not use the locked public R2 origin")
    if (
        manifest.get("schemaId") != "ufo-timeline-analysis-reporting-delay-artifacts-v1.0.0"
        or manifest.get("schemaVersion") != 1
        or manifest.get("manifestVersion") != "1.0.0"
    ):
        raise ReleaseError("Reporting-delay manifest schema identity is not the accepted v1 contract")

    counts = manifest.get("counts")
    if not isinstance(counts, dict) or any(counts.get(key) != value for key, value in LOCKED_COUNTS.items()):
        raise ReleaseError("Reporting-delay counts do not match the deterministic accepted build")
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
        raise ReleaseError("Reporting-delay readiness and material gates are not release-ready")
    policy = manifest.get("policy")
    required_policy = {
        "canonicalEventsMutated": False,
        "narrativeDescriptionsRead": False,
        "missingDelayIsZero": False,
        "reportedRolePrecedence": "present_reported_role_never_replaced_by_posted_role",
        "postedFallbackEligibility": "reported_role_absent_only",
        "negativeDelayCoercedToZero": False,
        "patternFinderPromotion": False,
        "minimumActiveAndReferenceBinN": 20,
        "minimumCommonSupport": 0.8,
        "runtimeCovariates": ["source", "era", "macroregion"],
    }
    if not isinstance(policy, dict) or any(policy.get(key) != value for key, value in required_policy.items()):
        raise ReleaseError("Reporting-delay manifest weakens the locked scientific or nonpromotion policy")
    delivery = manifest.get("delivery")
    if not isinstance(delivery, dict) or delivery.get("pagesFiles") != ["manifest.json"]:
        raise ReleaseError("Only the reporting-delay manifest may be delivered with Pages")
    if delivery.get("cacheControl") != optional_r2.DEFAULT_CACHE_CONTROL:
        raise ReleaseError("Reporting-delay payloads must use immutable one-year cache control")
    if len(payloads) != 14 or sum(item["bytes"] for item in payloads) != 49_629_719:
        raise ReleaseError("Reporting-delay R2 payload set changed from the accepted release")
    artifacts = manifest.get("artifacts")
    shard_keys = manifest.get("artifactGroups", {}).get("roleEvidenceShards", [])
    if not isinstance(artifacts, dict) or set(shard_keys) != {
        "roleEvidenceShard000", "roleEvidenceShard001", "roleEvidenceShard002",
        "roleEvidenceShard003", "roleEvidenceShard004", "roleEvidenceShard005",
    }:
        raise ReleaseError("Reporting-delay role-evidence shard declarations are incomplete")
    if artifacts.get("reportingDelayProjection", {}).get("rowCount") != 270461:
        raise ReleaseError("Reporting-delay browser projection row count changed")


def main() -> None:
    args = parse_args()
    report = optional_r2.publish_release(
        manifest_path=args.manifest,
        bucket=args.bucket,
        wrangler=args.wrangler,
        timeout=args.timeout,
        validate_only=args.validate_only,
        validate_manifest=validate_reporting_delay_manifest,
        upload_label="analysis-reporting-delay",
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError, ReleaseError) as exc:
        print(f"Analysis reporting-delay R2 release failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
