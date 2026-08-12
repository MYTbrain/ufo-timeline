"""Canonical attempt-fingerprint helper for context-evidence queue writers.

Research packets may retain their own audit hashes, but queue proposals must
derive ``fingerprint`` from the campaign contract's kind, normalized target,
and optional source-version hash.  This module deliberately delegates that
derivation to the canonical campaign validator so the two cannot drift.

Library use::

    from scripts.context_evidence_attempt_fingerprint import stamp_attempt_fingerprint

    queue_attempt = stamp_attempt_fingerprint(queue_attempt)

Command-line use::

    python scripts/context_evidence_attempt_fingerprint.py \
        --kind query --target '"Mayville" crop circle report'

The helper never changes the original target, version, retry flag, or other
attempt fields.  It returns a copy with only ``fingerprint`` replaced.
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

try:
    from scripts import build_context_evidence_campaign as campaign
except ImportError:  # Direct script execution resolves sibling modules here.
    import build_context_evidence_campaign as campaign


ATTEMPT_KINDS = (
    "query",
    "source_open",
    "archive_fallback",
    "repository_sample",
    "source_version",
)
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


class AttemptFingerprintInputError(ValueError):
    """Raised when an attempt cannot be represented by the queue contract."""


def canonical_attempt_fingerprint(
    kind: str,
    target: str,
    version_sha256: str | None = None,
) -> str:
    """Return the validator's fingerprint for the exact ledger inputs."""

    if kind not in ATTEMPT_KINDS:
        raise AttemptFingerprintInputError(f"Unsupported attempt kind: {kind!r}")
    if not isinstance(target, str) or not target.strip():
        raise AttemptFingerprintInputError("Attempt target must be a non-empty string")
    if version_sha256 is not None and (
        not isinstance(version_sha256, str) or SHA256_RE.fullmatch(version_sha256) is None
    ):
        raise AttemptFingerprintInputError("versionSha256 must be null or a lowercase SHA-256 hex digest")
    return campaign.attempt_fingerprint(kind, target, version_sha256)


def stamp_attempt_fingerprint(attempt: Mapping[str, Any]) -> dict[str, Any]:
    """Copy a queue attempt and replace only its fingerprint canonically."""

    try:
        kind = attempt["kind"]
        target = attempt["target"]
        version_sha256 = attempt["versionSha256"]
    except KeyError as exc:
        raise AttemptFingerprintInputError(f"Attempt is missing required field {exc.args[0]!r}") from exc
    if not isinstance(kind, str):
        raise AttemptFingerprintInputError("Attempt kind must be a string")
    stamped = dict(attempt)
    stamped["fingerprint"] = canonical_attempt_fingerprint(kind, target, version_sha256)
    return stamped


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute a context-evidence queue attempt fingerprint from the canonical validator contract."
    )
    parser.add_argument("--kind", required=True, choices=ATTEMPT_KINDS)
    parser.add_argument("--target", required=True, help="Exact original query, URL, repository target, or source locator.")
    parser.add_argument("--version-sha256", default=None, help="Exact lowercase source-version SHA-256, when present.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the exact inputs and canonical fingerprint as compact JSON instead of only the digest.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        fingerprint = canonical_attempt_fingerprint(args.kind, args.target, args.version_sha256)
    except AttemptFingerprintInputError as exc:
        raise SystemExit(str(exc)) from exc
    if args.json:
        print(
            json.dumps(
                {
                    "kind": args.kind,
                    "target": args.target,
                    "versionSha256": args.version_sha256,
                    "fingerprint": fingerprint,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    else:
        print(fingerprint)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
