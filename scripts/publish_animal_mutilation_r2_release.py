"""Validate and publish the immutable Animal Mutilation Reports R2 release."""

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


DEFAULT_MANIFEST = Path("webapp/static_public/data/animal_mutilations/manifest.json")
DEFAULT_BUCKET = "ufo-timeline-data"
LOCKED_RELEASE_ID = "animal-mutilations-v1-20260812"
STALE_HANDOFF_ZIP_SHA256 = "caecfb0b2f94f7f361ab0782d4097fee31711073ede3b8a1b2ad071ae28f1048"
STALE_RELEASE_COMMIT = "1653e7a9cacab47603621974b7e548efaaf88c0a"

ReleaseError = optional_r2.ReleaseError
declared_payloads = optional_r2.declared_payloads
release_prefix = optional_r2.release_prefix
classify_remote = optional_r2.classify_remote
verify_remote = optional_r2.verify_remote


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--wrangler", type=Path, default=Path("node_modules/.bin/wrangler"))
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate every local payload and print the immutable upload plan without network access.",
    )
    return parser.parse_args()


def _integer(counts: dict[str, Any], key: str) -> int:
    try:
        value = int(counts[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise ReleaseError(f"Animal manifest has no valid counts.{key}") from exc
    if value < 0:
        raise ReleaseError(f"Animal manifest counts.{key} cannot be negative")
    return value


def _sha256(value: Any, *, field: str) -> str:
    digest = str(value or "")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ReleaseError(f"Animal manifest {field} must be a lowercase SHA-256")
    return digest


def validate_animal_manifest(
    manifest: dict[str, Any],
    payloads: list[dict[str, Any]],
) -> None:
    release_id = str(manifest.get("releaseId") or "")
    if release_id != LOCKED_RELEASE_ID or not re.fullmatch(r"animal-mutilations-v1-\d{8}", release_id):
        raise ReleaseError(f"Animal releaseId must be the locked release {LOCKED_RELEASE_ID}")
    if release_prefix(manifest) != f"releases/{LOCKED_RELEASE_ID}":
        raise ReleaseError("Animal R2 prefix does not match the locked immutable release prefix")

    counts = manifest.get("counts")
    if not isinstance(counts, dict):
        raise ReleaseError("Animal manifest counts must be an object")
    records = _integer(counts, "records")
    mapped = _integer(counts, "mapped")
    unmapped = _integer(counts, "unmapped")
    reported = _integer(counts, "reportedUnreviewed")
    detail_chunks = _integer(counts, "detailChunks")
    locked_counts = {
        "records": 1184,
        "sourceRecords": 1177,
        "acceptedNewCases": 7,
        "mapped": 518,
        "unmapped": 666,
        "reportedUnreviewed": 1173,
        "exactDay": 928,
        "mappedExactDay": 340,
        "undated": 28,
        "mappedPositions": 400,
        "exactCoordinates": 0,
        "detailChunks": 5,
    }
    actual_locked_counts = {key: _integer(counts, key) for key in locked_counts}
    if actual_locked_counts != locked_counts:
        raise ReleaseError("Animal manifest record counts do not match the accepted handoff")
    if mapped + unmapped != records:
        raise ReleaseError("Animal manifest mapped and unmapped counts do not sum to records")

    source = manifest.get("source")
    if not isinstance(source, dict):
        raise ReleaseError("Animal manifest source identity contract is missing")
    if source.get("adapterVersion") != "animal-mutilation-timeline-adapter-v1.1.1":
        raise ReleaseError("Animal manifest must use the corrected v1.1.1 adapter")
    if source.get("handoffSchema") != "animal-mutilation-timeline-handoff-v1.1.0":
        raise ReleaseError("Animal manifest must use the corrected v1.1.0 handoff schema")
    if manifest.get("sourceSchema") != "animal-mutilation-timeline-overlay-v1.1.0":
        raise ReleaseError("Animal manifest must use the v1.1.0 Timeline overlay schema")
    release_commit = str(source.get("releaseCommit") or "")
    if not re.fullmatch(r"[0-9a-f]{40}", release_commit) or release_commit == STALE_RELEASE_COMMIT:
        raise ReleaseError("Animal manifest must pin the corrected handoff release commit")
    handoff_zip_sha = _sha256(source.get("handoffZipSha256"), field="source.handoffZipSha256")
    if handoff_zip_sha == STALE_HANDOFF_ZIP_SHA256:
        raise ReleaseError("Animal manifest still pins the superseded v1.0 handoff ZIP")
    _sha256(source.get("handoffManifestSha256"), field="source.handoffManifestSha256")
    _sha256(source.get("sourceGeojsonSha256"), field="source.sourceGeojsonSha256")
    coordinate_audit = source.get("coordinateAudit") if isinstance(source, dict) else None
    if not isinstance(coordinate_audit, dict) or (
        coordinate_audit.get("requiredForRelease") is not True
        or coordinate_audit.get("available") is not True
        or coordinate_audit.get("semanticValidationPassed") is not True
        or coordinate_audit.get("correctionCount") != 479
    ):
        raise ReleaseError("Animal coordinate-normalization audit is required and not release-ready")
    _sha256(coordinate_audit.get("sha256"), field="source.coordinateAudit.sha256")
    if "bytes" in coordinate_audit and _integer(coordinate_audit, "bytes") <= 0:
        raise ReleaseError("Animal coordinate-normalization audit bytes must be positive")

    policy = manifest.get("policy")
    if not isinstance(policy, dict) or (
        policy.get("traceEligible") is not False
        or policy.get("traceRole") != "context_only"
        or policy.get("causality") != "not_asserted"
        or policy.get("craftColorEligible") is not False
        or policy.get("playbackEligible") is not False
        or policy.get("relationshipsEligible") is not False
        or policy.get("contentWarningRequired") is not True
    ):
        raise ReleaseError("Animal manifest violates the locked context-only trace/causality policy")

    delivery = manifest.get("delivery")
    if not isinstance(delivery, dict):
        raise ReleaseError("Animal manifest delivery contract is missing")
    if delivery.get("pagesFiles") != ["manifest.json"]:
        raise ReleaseError("Only manifest.json may be delivered with Pages for the animal layer")
    r2_paths = delivery.get("r2OnlyPaths")
    if not isinstance(r2_paths, list) or r2_paths != sorted(r2_paths):
        raise ReleaseError("Animal delivery.r2OnlyPaths must be a sorted list")
    if r2_paths != sorted(payload["path"] for payload in payloads):
        raise ReleaseError("Animal delivery.r2OnlyPaths must exactly match local R2 payloads")

    points = manifest.get("points")
    catalog = manifest.get("catalog")
    details = manifest.get("details")
    if not isinstance(points, dict) or not isinstance(catalog, dict) or not isinstance(details, dict):
        raise ReleaseError("Animal manifest must declare points, catalog, and details payloads")
    detail_files = details.get("files")
    if not isinstance(detail_files, list) or len(detail_files) != detail_chunks:
        raise ReleaseError("Animal detail chunk count does not match its declarations")
    if int(catalog.get("recordCount", -1)) != records:
        raise ReleaseError("Animal catalog must retain every supplied report")
    if int(points.get("recordCount", -1)) != mapped:
        raise ReleaseError("Animal points payload must retain every mapped report")
    if sum(int(item.get("recordCount", -1)) for item in detail_files if isinstance(item, dict)) != records:
        raise ReleaseError("Animal detail chunks must account for every supplied report")
    for declaration in [points, catalog, *detail_files]:
        if not isinstance(declaration, dict) or declaration.get("r2Only") is not True:
            raise ReleaseError("Every animal browser payload must be explicitly marked r2Only")


def main() -> None:
    args = parse_args()
    report = optional_r2.publish_release(
        manifest_path=args.manifest,
        bucket=args.bucket,
        wrangler=args.wrangler,
        timeout=args.timeout,
        validate_only=args.validate_only,
        validate_manifest=validate_animal_manifest,
        upload_label="animal-mutilation",
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
        print(f"Animal-mutilation R2 release failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
