"""Validate and publish the immutable Analysis color v1 R2 release."""

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


DEFAULT_MANIFEST = Path("webapp/static_public/data/analysis_color_v1/manifest.json")
DEFAULT_BUCKET = "ufo-timeline-data"
LOCKED_RELEASE_ID = "analysis-color-v1-20260805"
LOCKED_ASSET_ORIGIN = "https://pub-e9029ab2f6b448daad03d7cde7e15e64.r2.dev"
LOCKED_COUNTS = {
    "catalogRows": 702893,
    "rawColorRows": 79215,
    "uniqueSourceRawValues": 4859,
    "normalizedRows": 70097,
    "roleSpecificRows": 1207,
    "roleUnspecifiedRows": 77994,
}
LOCKED_ARTIFACTS = {
    "colorValueDictionary": (
        "color_value_dictionary_v1", 532929,
        "22b3be93b547e41ce0c171a9ff3edaefc3c161148cbc9ca3e19c2294cf58f003",
        250452, "36a3f76a3b4d67c32aed43f3152f1b2cd6fada8f359acd558b3d0dad66ad5cba", 4859,
    ),
    "colorProjection": (
        "color_projection_v1", 2732810,
        "86210c50074fbb074a287613f71470db553090db8ff7772695ba48e00e262238",
        1070294, "e18fe47c5007c247068a938cf97d028b19ac363988d58e95454e7c817fce0057", 79215,
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
        raise ReleaseError(f"Color manifest {field} must be an integer") from exc
    if result < 0:
        raise ReleaseError(f"Color manifest {field} cannot be negative")
    return result


def validate_color_manifest(manifest: dict[str, Any], payloads: list[dict[str, Any]]) -> None:
    release_id = str(manifest.get("releaseId") or "")
    if release_id != LOCKED_RELEASE_ID or not re.fullmatch(r"analysis-color-v1-\d{8}", release_id):
        raise ReleaseError(f"Color releaseId must be the locked release {LOCKED_RELEASE_ID}")
    if optional_r2.release_prefix(manifest) != f"releases/{LOCKED_RELEASE_ID}":
        raise ReleaseError("Color R2 prefix does not match the locked immutable release prefix")
    if str(manifest.get("assetBaseUrl") or "") != f"{LOCKED_ASSET_ORIGIN}/releases/{LOCKED_RELEASE_ID}":
        raise ReleaseError("Color assetBaseUrl does not use the locked public R2 origin")
    if (
        manifest.get("schemaId") != "ufo-timeline-analysis-color-artifacts-v1.0.0"
        or manifest.get("schemaVersion") != 1
        or manifest.get("manifestVersion") != "1.0.0"
    ):
        raise ReleaseError("Color manifest schema identity is not the accepted v1 contract")

    counts = manifest.get("counts")
    if not isinstance(counts, dict):
        raise ReleaseError("Color manifest counts must be an object")
    if {key: _integer(counts.get(key), field=f"counts.{key}") for key in LOCKED_COUNTS} != LOCKED_COUNTS:
        raise ReleaseError("Color manifest counts do not match the deterministic accepted build")
    if counts.get("supportedSources") != ["nuforc", "ufocat"]:
        raise ReleaseError("Color release must retain exactly the two accepted source families")
    if counts.get("bySourceNormalized") != {"nuforc": 10165, "ufocat": 59932}:
        raise ReleaseError("Color source-specific normalized counts changed")

    readiness = manifest.get("readiness")
    gates = readiness.get("materialGates") if isinstance(readiness, dict) else None
    if (
        not isinstance(readiness, dict)
        or readiness.get("status") != "ready_descriptive_cross_source"
        or readiness.get("assessmentLane") != "cross_source_descriptive_role_preserving"
        or not isinstance(gates, dict)
        or not gates
        or any(value is not True for value in gates.values())
    ):
        raise ReleaseError("Color readiness and material gates are not release-ready")

    policy = manifest.get("policy")
    required_policy = {
        "canonicalEventsMutated": False,
        "explicitSourceFieldOnly": True,
        "narrativeDescriptionsRead": False,
        "neighboringFieldsRead": False,
        "fuzzyMatchingUsed": False,
        "missingColorIsColorlessOrZero": False,
        "sourceFieldImpliesObjectColor": False,
        "unknownRolePromoted": False,
        "descriptorsAreExactColors": False,
        "patternFinderPromotion": False,
        "incidenceAuthenticityRiskCausalOrCraftClaims": False,
        "minimumCommonSupport": 0.8,
        "minimumActiveAndReferenceCellN": 20,
    }
    if not isinstance(policy, dict) or any(policy.get(key) != value for key, value in required_policy.items()):
        raise ReleaseError("Color manifest weakens the locked scientific or nonpromotion policy")

    support = manifest.get("commonSupport")
    if (
        not isinstance(support, dict)
        or support.get("commonSupportRate") != 1.0
        or support.get("minimumRowsPerSourceCategory") != 20
        or len(support.get("commonSupportCategories") or []) != 15
    ):
        raise ReleaseError("Color common-support evidence changed")

    delivery = manifest.get("delivery")
    if not isinstance(delivery, dict) or delivery.get("pagesFiles") != ["manifest.json"]:
        raise ReleaseError("Only the color manifest may be delivered with Pages")
    if delivery.get("cacheControl") != optional_r2.DEFAULT_CACHE_CONTROL:
        raise ReleaseError("Color payloads must use immutable one-year cache control")
    expected_paths: list[str] = []
    for stem, *_unused in LOCKED_ARTIFACTS.values():
        expected_paths.extend([f"{stem}.json", f"{stem}.json.gz"])
    if delivery.get("r2OnlyPaths") != expected_paths:
        raise ReleaseError("Color delivery.r2OnlyPaths does not match the locked release order")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != set(LOCKED_ARTIFACTS):
        raise ReleaseError("Color browser artifact declarations are incomplete")
    payload_by_path = {str(payload.get("path")): payload for payload in payloads}
    if set(payload_by_path) != set(expected_paths):
        raise ReleaseError("Color R2 payload set does not match the locked release")
    for key, (stem, raw_bytes, raw_sha, gzip_bytes, gzip_sha, rows) in LOCKED_ARTIFACTS.items():
        artifact = artifacts[key]
        if (
            artifact.get("sha256") != raw_sha or artifact.get("gzipSha256") != gzip_sha
            or _integer(artifact.get("bytes"), field=f"artifacts.{key}.bytes") != raw_bytes
            or _integer(artifact.get("gzipBytes"), field=f"artifacts.{key}.gzipBytes") != gzip_bytes
            or _integer(artifact.get("rowCount"), field=f"artifacts.{key}.rowCount") != rows
        ):
            raise ReleaseError(f"Color artifact identity changed: {key}")
        if not str(artifact.get("file") or "").startswith(str(manifest["assetBaseUrl"]) + "/"):
            raise ReleaseError(f"Color artifact URL leaves the immutable release prefix: {key}")
        for path, expected_bytes, expected_sha in (
            (f"{stem}.json", raw_bytes, raw_sha),
            (f"{stem}.json.gz", gzip_bytes, gzip_sha),
        ):
            payload = payload_by_path[path]
            if _integer(payload.get("bytes"), field=f"payloads.{path}.bytes") != expected_bytes or payload.get("sha256") != expected_sha:
                raise ReleaseError(f"Color payload identity changed: {path}")
            declaration = next(
                (item for item in manifest.get("payloads", {}).values() if isinstance(item, dict) and item.get("path") == path),
                None,
            )
            if not declaration or declaration.get("r2Only") is not True or declaration.get("recordCount") != rows:
                raise ReleaseError(f"Color payload declaration is incomplete: {path}")


def main() -> None:
    args = parse_args()
    report = optional_r2.publish_release(
        manifest_path=args.manifest,
        bucket=args.bucket,
        wrangler=args.wrangler,
        timeout=args.timeout,
        validate_only=args.validate_only,
        validate_manifest=validate_color_manifest,
        upload_label="analysis-color",
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError, ReleaseError) as exc:
        print(f"Analysis color R2 release failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
