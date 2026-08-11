"""Validate and publish the immutable Analysis v2.3 R2 release.

Pages receives only ``manifest.json``. Every runtime projection, compressed
peer, geography binary, and frozen relationship snapshot is published beneath
one release-scoped R2 prefix. Existing keys are never overwritten unless their
public bytes already match the frozen manifest exactly.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse
import subprocess
import sys
from typing import Any, Mapping

try:
    from scripts import publish_optional_layer_r2_release as optional_r2
except (ModuleNotFoundError, ImportError):
    import publish_optional_layer_r2_release as optional_r2  # type: ignore[no-redef]


DEFAULT_MANIFEST = Path("webapp/static_public/data/analysis_v2/manifest.json")
DEFAULT_BUCKET = "ufo-timeline-data"
LOCKED_RELEASE_ID = "analysis-evidence-lab-v2.3-20260811"
LOCKED_ASSET_ORIGIN = "https://pub-e9029ab2f6b448daad03d7cde7e15e64.r2.dev"
EXPECTED_ARTIFACT_KEYS = {
    "animalContextReadiness",
    "contextUfoNeighbors",
    "cropContextReadiness",
    "facilityAnalysis",
    "relationshipReconciliation",
    "ufoConfigurationNeighbors",
    "ufoConfigurationPoints",
    "ufoGeography",
    "ufoPointNeighbors",
    "ufoSpatialPoints",
}
EXPECTED_PAYLOAD_COUNT = 25

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
        raise ReleaseError(f"Analysis v2 manifest {field} must be an integer") from exc
    if result < 0:
        raise ReleaseError(f"Analysis v2 manifest {field} cannot be negative")
    return result


def _runtime_payload(
    *,
    manifest: Mapping[str, Any],
    declaration: Mapping[str, Any],
    file_key: str,
) -> tuple[str, dict[str, Any]]:
    gzip_payload = file_key == "gzipFile"
    bytes_key = "gzipBytes" if gzip_payload else "bytes"
    sha_key = "gzipSha256" if gzip_payload else "sha256"
    url = str(declaration.get(file_key) or "")
    parsed = urlparse(url)
    base_url = str(manifest.get("assetBaseUrl") or "").rstrip("/")
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.query
        or parsed.fragment
        or "/" not in parsed.path
    ):
        raise ReleaseError(f"Analysis runtime payload URL is not immutable HTTPS: {url!r}")
    path = parsed.path.rsplit("/", 1)[-1]
    if not path or url != f"{base_url}/{path}":
        raise ReleaseError(f"Analysis runtime payload leaves assetBaseUrl: {url!r}")
    identity = {
        "bytes": _integer(declaration.get(bytes_key), field=f"{path}.{bytes_key}"),
        "sha256": str(declaration.get(sha_key) or ""),
    }
    if len(identity["sha256"]) != 64:
        raise ReleaseError(f"Analysis runtime payload has no SHA-256: {path}")
    return path, identity


def expected_runtime_payloads(manifest: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, Mapping) or set(artifacts) != EXPECTED_ARTIFACT_KEYS:
        raise ReleaseError("Analysis v2 browser artifact declarations are incomplete")
    declarations: list[Mapping[str, Any]] = []
    for key in sorted(EXPECTED_ARTIFACT_KEYS):
        declaration = artifacts.get(key)
        if not isinstance(declaration, Mapping):
            raise ReleaseError(f"Analysis v2 artifact is not an object: {key}")
        declarations.append(declaration)
        if key == "ufoGeography":
            binary = declaration.get("binary")
            if not isinstance(binary, Mapping):
                raise ReleaseError("Analysis v2 geography binary declaration is missing")
            declarations.append(binary)

    sources = manifest.get("sources")
    if not isinstance(sources, Mapping):
        raise ReleaseError("Analysis v2 source declarations are missing")
    for key in ("relationshipSourceSnapshot", "relationshipSourceSnapshotMetadata"):
        declaration = sources.get(key)
        if not isinstance(declaration, Mapping):
            raise ReleaseError(f"Analysis v2 frozen source declaration is missing: {key}")
        declarations.append(declaration)

    expected: dict[str, dict[str, Any]] = {}
    for declaration in declarations:
        for file_key in ("file", "gzipFile"):
            if file_key not in declaration:
                continue
            path, identity = _runtime_payload(
                manifest=manifest,
                declaration=declaration,
                file_key=file_key,
            )
            if path in expected:
                raise ReleaseError(f"Duplicate Analysis v2 runtime payload URL: {path}")
            expected[path] = identity
    if len(expected) != EXPECTED_PAYLOAD_COUNT:
        raise ReleaseError(
            f"Analysis v2 runtime payload count changed: {len(expected)}/{EXPECTED_PAYLOAD_COUNT}"
        )
    return expected


def validate_analysis_manifest(
    manifest: dict[str, Any], payloads: list[dict[str, Any]]
) -> None:
    release_id = str(manifest.get("releaseId") or "")
    if release_id != LOCKED_RELEASE_ID:
        raise ReleaseError(
            f"Analysis v2 releaseId must be the locked release {LOCKED_RELEASE_ID}"
        )
    asset_base_url = f"{LOCKED_ASSET_ORIGIN}/releases/{LOCKED_RELEASE_ID}"
    if str(manifest.get("assetBaseUrl") or "") != asset_base_url:
        raise ReleaseError("Analysis v2 assetBaseUrl does not use the locked public R2 release")
    if optional_r2.release_prefix(manifest) != f"releases/{LOCKED_RELEASE_ID}":
        raise ReleaseError("Analysis v2 R2 prefix does not match the locked release")
    if (
        manifest.get("schemaId") != "ufo-timeline-analysis-evidence-artifacts-v2.3.0"
        or manifest.get("schemaVersion") != 2
        or manifest.get("manifestVersion") != "2.3.0"
    ):
        raise ReleaseError("Analysis v2 manifest schema identity is not v2.3")

    required_policy = {
        "authenticityAssessments": False,
        "causalInferences": False,
        "chronologySegmentsRead": False,
        "contextProximityFailClosed": True,
        "generalizedCoordinatesKilometerEligible": False,
        "roughMarkerAssociationInferenceEligible": False,
        "roughMarkerDefiniteNearEligible": False,
        "traceMetrics": False,
        "travelMetrics": False,
    }
    policy = manifest.get("policy")
    if not isinstance(policy, Mapping) or any(
        policy.get(key) != expected for key, expected in required_policy.items()
    ):
        raise ReleaseError("Analysis v2 weakens a scientific or noncausal invariant")
    if policy.get("minimumContextEligibleRecordsForInference") != 25:
        raise ReleaseError("Analysis v2 minimum context evidence gate changed")
    counts = manifest.get("counts")
    if not isinstance(counts, Mapping):
        raise ReleaseError("Analysis v2 counts are missing")
    if _integer(
        counts.get("relationshipAssociationEligible"),
        field="counts.relationshipAssociationEligible",
    ) != 0:
        raise ReleaseError("Analysis v2 relationship associations must remain ineligible")

    delivery = manifest.get("delivery")
    if not isinstance(delivery, Mapping):
        raise ReleaseError("Analysis v2 immutable delivery contract is missing")
    if delivery.get("pagesFiles") != ["manifest.json"]:
        raise ReleaseError("Only the Analysis v2 manifest may be delivered with Pages")
    if delivery.get("cacheControl") != optional_r2.DEFAULT_CACHE_CONTROL:
        raise ReleaseError("Analysis v2 payloads must use immutable one-year cache control")
    if delivery.get("immutablePrefix") != f"releases/{LOCKED_RELEASE_ID}":
        raise ReleaseError("Analysis v2 delivery prefix changed")

    expected = expected_runtime_payloads(manifest)
    r2_paths = delivery.get("r2OnlyPaths")
    if r2_paths != sorted(expected):
        raise ReleaseError("Analysis v2 delivery.r2OnlyPaths is incomplete or unsorted")
    payload_declarations = manifest.get("payloads")
    if not isinstance(payload_declarations, list):
        raise ReleaseError("Analysis v2 payload declarations must be a list")
    declared_by_path = {
        str(item.get("path") or ""): item
        for item in payload_declarations
        if isinstance(item, Mapping)
    }
    if len(declared_by_path) != len(payload_declarations) or set(declared_by_path) != set(expected):
        raise ReleaseError("Analysis v2 payload declarations do not match runtime URLs")
    local_by_path = {str(item.get("path") or ""): item for item in payloads}
    if set(local_by_path) != set(expected):
        raise ReleaseError("Analysis v2 local payload set does not match the manifest")

    for path, identity in expected.items():
        declaration = declared_by_path[path]
        local = local_by_path[path]
        expected_content_type = (
            "application/octet-stream"
            if path.endswith(".bin") or path.endswith(".bin.gz")
            else "application/json; charset=utf-8"
        )
        if (
            declaration.get("r2Only") is not True
            or declaration.get("contentType") != expected_content_type
            or declaration.get("contentEncoding") not in {None, ""}
            or _integer(declaration.get("bytes"), field=f"payloads.{path}.bytes")
            != identity["bytes"]
            or declaration.get("sha256") != identity["sha256"]
            or local.get("bytes") != identity["bytes"]
            or local.get("sha256") != identity["sha256"]
        ):
            raise ReleaseError(f"Analysis v2 payload identity changed: {path}")


def main() -> None:
    args = parse_args()
    report = optional_r2.publish_release(
        manifest_path=args.manifest,
        bucket=args.bucket,
        wrangler=args.wrangler,
        timeout=args.timeout,
        validate_only=args.validate_only,
        validate_manifest=validate_analysis_manifest,
        upload_label="analysis-v2",
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
        print(f"Analysis v2 R2 release failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
