#!/usr/bin/env python3
"""Validate and package the deterministic UFO Timeline animal-report handoff.

This command consumes an already-built Timeline adapter directory. It never
runs extraction, classification, review, or frontend code, and it includes
only a fixed public-safe allowlist in the resulting ZIP.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import unquote_plus, urlsplit


HANDOFF_VERSION = "animal-mutilation-timeline-handoff-v1.0.0"
LAYER_NAME = "Animal Mutilation Reports"
REPORTED_UNREVIEWED = "reported_unreviewed"
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)

OVERLAY_NAME = "animal_mutilations.geojson"
QUEUE_NAME = "timeline_review_queue.jsonl"
IMPORT_MANIFEST_NAME = "animal_mutilations_import_manifest.json"

REPO_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_PAYLOADS: tuple[tuple[str, Path, str], ...] = (
    (
        "adapter/build_animal_mutilation_timeline_layer.py",
        REPO_ROOT / "scripts" / "build_animal_mutilation_timeline_layer.py",
        "deterministic_adapter_source",
    ),
    (
        "schemas/timeline_overlay.schema.json",
        REPO_ROOT / "docs" / "cattle_mutilation" / "timeline_overlay.schema.json",
        "overlay_schema",
    ),
    (
        "schemas/timeline_review_decision.schema.json",
        REPO_ROOT
        / "docs"
        / "cattle_mutilation"
        / "timeline_review_decision.schema.json",
        "optional_review_decision_schema",
    ),
    (
        "schemas/case.schema.json",
        REPO_ROOT / "docs" / "cattle_mutilation" / "case.schema.json",
        "seed_case_schema",
    ),
)
ADAPTER_PAYLOADS: tuple[tuple[str, str, str], ...] = (
    (f"data/{OVERLAY_NAME}", OVERLAY_NAME, "timeline_context_layer"),
    (f"data/{QUEUE_NAME}", QUEUE_NAME, "optional_review_queue"),
    (
        f"manifest/{IMPORT_MANIFEST_NAME}",
        IMPORT_MANIFEST_NAME,
        "adapter_import_manifest",
    ),
)

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
AMI_RE = re.compile(r"^ami_[0-9a-f]{24}$")
CMI_RE = re.compile(r"^cmi_[0-9a-f]{24}$")
FEATURE_ID_RE = re.compile(r"^animal_mutilation:ami_[0-9a-f]{24}$")
PIPELINE_VERSION_RE = re.compile(
    r"^animal-mutilation-cross-domain-seed-v\d+\.\d+\.\d+$"
)
ADAPTER_VERSION_RE = re.compile(
    r"^animal-mutilation-timeline-adapter-v\d+\.\d+\.\d+$"
)
CORRUPT_TEXT_MARKERS = (
    "\N{REPLACEMENT CHARACTER}",
    "\N{GREEK CAPITAL LETTER GAMMA}\N{LATIN CAPITAL LETTER C WITH CEDILLA}",
)
URL_LOCATOR_PRIVACY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)(?:https?://|www\.)"),
    re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"),
    re.compile(
        r"(?<!\d)(?:\+?1[-. ]?)?(?:\(\d{3}\)|\d{3})"
        r"[-. ]\d{3}[-. ]\d{4}\b"
    ),
    re.compile(
        r"(?i)\b\d{1,6}(?:[-\N{EN DASH}\N{EM DASH}]\d{1,6})?\s+"
        r"(?:[A-Z0-9.'-]+\s+){1,6}"
        r"(?:Road|Rd|Street|St|Avenue|Ave|Lane|Ln|Drive|Dr|Highway|Hwy|"
        r"Route|Rt|Boulevard|Blvd|Court|Ct|Way)\b"
    ),
    re.compile(
        r"\b[A-Z][A-Za-z0-9&.'\N{RIGHT SINGLE QUOTATION MARK}-]*"
        r"(?:\s+(?:and|&|[A-Z][A-Za-z0-9&.'\N{RIGHT SINGLE QUOTATION MARK}-]*)){0,3}"
        r"\s+(?:Ranch|Farm|Homestead)\b"
    ),
    re.compile(
        r"\b[a-z][a-z0-9&.'\N{RIGHT SINGLE QUOTATION MARK}-]*"
        r"(?:\s+(?:and|&|[a-z][a-z0-9&.'\N{RIGHT SINGLE QUOTATION MARK}-]*)){0,3}"
        r"\s+(?:ranch|farm|homestead)\b"
    ),
    re.compile(
        r"(?<![\w.])[-+]?(?:[0-8]?\d(?:\.\d{3,})?|90(?:\.0{3,})?)"
        r"\s*[,;/]\s*[-+]?(?:1[0-7]\d(?:\.\d{3,})?|"
        r"(?:[0-9]?\d)(?:\.\d{3,})?|180(?:\.0{3,})?)(?!\d|\.\d)"
    ),
    re.compile(
        r"(?i)\b(?:reported by|owned by|owner|rancher)\s+"
        r"(?!\[(?:name|private)[^\]]*\])"
        r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b"
    ),
)


class HandoffPackagingError(RuntimeError):
    """The adapter output is not safe or internally consistent for handoff."""


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _reject_json_constant(token: str) -> None:
    raise ValueError(f"non-finite JSON number {token!r} is not allowed")


def _load_json(data: bytes, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            data.decode("utf-8"),
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise HandoffPackagingError(f"invalid JSON in {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise HandoffPackagingError(f"{label} must contain a JSON object")
    return value


def _load_jsonl(data: bytes, *, label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(data.splitlines(), start=1):
        if not raw_line.strip():
            continue
        row = _load_json(raw_line, label=f"{label} line {line_number}")
        rows.append(row)
    return rows


def _required_nonnegative_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise HandoffPackagingError(f"{label} must be a non-negative integer")
    return value


def _corrupt_text_path(value: Any, path: tuple[str, ...] = ()) -> str | None:
    if isinstance(value, str):
        if any(marker in value for marker in CORRUPT_TEXT_MARKERS):
            return ".".join(path) or "<root>"
    elif isinstance(value, Mapping):
        for key, child in value.items():
            found = _corrupt_text_path(child, path + (str(key),))
            if found is not None:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = _corrupt_text_path(child, path + (str(index),))
            if found is not None:
                return found
    return None


def _decoded_url_privacy_reason(value: str) -> str | None:
    if any(character.isspace() for character in value):
        return "whitespace"
    try:
        parsed = urlsplit(value)
        _ = parsed.port
    except ValueError:
        return "malformed_url"
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return "invalid_public_url"
    if parsed.username is not None or parsed.password is not None:
        return "url_credentials"
    locator_text = " ".join((parsed.path, parsed.query, parsed.fragment))
    for _ in range(3):
        decoded = unquote_plus(locator_text)
        if decoded == locator_text:
            break
        locator_text = decoded
    normalized = re.sub(r"[/\\?&#=._+%:-]+", " ", locator_text)
    if any(marker in normalized for marker in CORRUPT_TEXT_MARKERS):
        return "corrupt_text"
    for pattern in URL_LOCATOR_PRIVACY_PATTERNS:
        if pattern.search(normalized):
            return "private_locator"
    return None


def _assert_safety_contract(value: Mapping[str, Any], *, label: str) -> None:
    expected = {
        "trace_eligible": False,
        "trace_role": "context_only",
        "causality": "not_asserted",
    }
    for key, expected_value in expected.items():
        if value.get(key) != expected_value:
            raise HandoffPackagingError(
                f"{label}.{key} must be {expected_value!r}"
            )


def _contains_forbidden_review_key(value: Any) -> str | None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in {"review_decision_id", "reviewed_on"}:
                return str(key)
            nested = _contains_forbidden_review_key(child)
            if nested is not None:
                return nested
    elif isinstance(value, list):
        for child in value:
            nested = _contains_forbidden_review_key(child)
            if nested is not None:
                return nested
    return None


def _validate_source_refs(
    source_refs: Any,
    *,
    source_incident_id: str,
) -> int:
    if not isinstance(source_refs, list) or not source_refs:
        raise HandoffPackagingError(
            f"feature {source_incident_id} must retain at least one source reference"
        )
    identities: set[tuple[str, str, str]] = set()
    for index, source_ref in enumerate(source_refs):
        if not isinstance(source_ref, Mapping):
            raise HandoffPackagingError(
                f"feature {source_incident_id} source_refs[{index}] must be an object"
            )
        source_id = source_ref.get("source_id")
        locator = source_ref.get("locator")
        source_hash = source_ref.get("source_hash")
        if not isinstance(source_id, str) or not source_id.strip():
            raise HandoffPackagingError(
                f"feature {source_incident_id} source_refs[{index}] has no source_id"
            )
        if not isinstance(locator, str) or not locator.strip():
            raise HandoffPackagingError(
                f"feature {source_incident_id} source_refs[{index}] has no locator"
            )
        if not isinstance(source_hash, str) or not SHA256_RE.fullmatch(source_hash):
            raise HandoffPackagingError(
                f"feature {source_incident_id} source_refs[{index}] has an invalid source_hash"
            )
        url = source_ref.get("url")
        if url is not None:
            if not isinstance(url, str):
                raise HandoffPackagingError(
                    f"feature {source_incident_id} source_refs[{index}].url is not a string"
                )
            privacy_reason = _decoded_url_privacy_reason(url)
            if privacy_reason is not None:
                raise HandoffPackagingError(
                    f"feature {source_incident_id} source_refs[{index}].url contains "
                    f"disallowed {privacy_reason}"
                )
        identity = (source_id, locator, source_hash)
        if identity in identities:
            raise HandoffPackagingError(
                f"feature {source_incident_id} repeats a source lineage identity"
            )
        identities.add(identity)
    return len(identities)


def _validate_overlay(overlay: Mapping[str, Any]) -> dict[str, Any]:
    corrupt_path = _corrupt_text_path(overlay)
    if corrupt_path is not None:
        raise HandoffPackagingError(
            f"overlay contains corrupt public text at {corrupt_path}"
        )
    if overlay.get("type") != "FeatureCollection":
        raise HandoffPackagingError("overlay.type must be FeatureCollection")
    if overlay.get("name") != LAYER_NAME:
        raise HandoffPackagingError(
            f"overlay.name must be exactly {LAYER_NAME!r}"
        )
    if overlay.get("release_mode") != REPORTED_UNREVIEWED:
        raise HandoffPackagingError(
            "overlay.release_mode must be reported_unreviewed"
        )
    _assert_safety_contract(overlay, label="overlay")
    features = overlay.get("features")
    if not isinstance(features, list) or not features:
        raise HandoffPackagingError("overlay.features must be a non-empty array")

    feature_ids: set[str] = set()
    event_ids: set[str] = set()
    source_ids: set[str] = set()
    incident_hashes: set[str] = set()
    source_ref_count = 0
    geometry_count = 0
    lineage: dict[str, str] = {}
    for index, feature in enumerate(features):
        if not isinstance(feature, Mapping) or feature.get("type") != "Feature":
            raise HandoffPackagingError(f"overlay feature {index} is not a Feature")
        feature_id = feature.get("id")
        if not isinstance(feature_id, str) or not FEATURE_ID_RE.fullmatch(feature_id):
            raise HandoffPackagingError(f"overlay feature {index} has an invalid id")
        if feature_id in feature_ids:
            raise HandoffPackagingError(f"duplicate feature id: {feature_id}")
        feature_ids.add(feature_id)

        properties = feature.get("properties")
        if not isinstance(properties, Mapping):
            raise HandoffPackagingError(f"{feature_id} has no properties object")
        if properties.get("status") != REPORTED_UNREVIEWED:
            raise HandoffPackagingError(
                f"{feature_id}.properties.status must be reported_unreviewed"
            )
        if properties.get("evidence_status") != REPORTED_UNREVIEWED:
            raise HandoffPackagingError(
                f"{feature_id}.properties.evidence_status must be reported_unreviewed"
            )
        forbidden_key = _contains_forbidden_review_key(feature)
        if forbidden_key is not None:
            raise HandoffPackagingError(
                f"unreviewed feature {feature_id} contains forbidden {forbidden_key}"
            )
        _assert_safety_contract(properties, label=f"{feature_id}.properties")

        event_id = properties.get("animal_mutilation_event_id")
        source_id = properties.get("source_incident_id")
        incident_hash = properties.get("source_incident_sha256")
        if not isinstance(event_id, str) or not AMI_RE.fullmatch(event_id):
            raise HandoffPackagingError(f"{feature_id} has an invalid event lineage id")
        if feature_id != f"animal_mutilation:{event_id}":
            raise HandoffPackagingError(
                f"{feature_id} does not reconcile animal_mutilation_event_id"
            )
        if not isinstance(source_id, str) or not CMI_RE.fullmatch(source_id):
            raise HandoffPackagingError(f"{feature_id} has an invalid source_incident_id")
        if not isinstance(incident_hash, str) or not SHA256_RE.fullmatch(incident_hash):
            raise HandoffPackagingError(
                f"{feature_id} has an invalid source_incident_sha256"
            )
        if event_id in event_ids:
            raise HandoffPackagingError(f"duplicate event lineage id: {event_id}")
        if source_id in source_ids:
            raise HandoffPackagingError(f"duplicate source incident lineage: {source_id}")
        if incident_hash in incident_hashes:
            raise HandoffPackagingError(
                f"duplicate source incident content hash: {incident_hash}"
            )
        event_ids.add(event_id)
        source_ids.add(source_id)
        incident_hashes.add(incident_hash)
        lineage[source_id] = incident_hash
        source_ref_count += _validate_source_refs(
            properties.get("source_refs"),
            source_incident_id=source_id,
        )
        if feature.get("geometry") is not None:
            geometry_count += 1

    return {
        "features": len(features),
        "features_with_geometry": geometry_count,
        "features_without_geometry": len(features) - geometry_count,
        "source_refs": source_ref_count,
        "lineage": lineage,
    }


def _validate_queue(
    queue: Sequence[Mapping[str, Any]],
    *,
    feature_lineage: Mapping[str, str],
) -> None:
    if len(queue) != len(feature_lineage):
        raise HandoffPackagingError(
            "review queue row count must equal reported_unreviewed feature count"
        )
    queue_lineage: dict[str, str] = {}
    for index, row in enumerate(queue):
        corrupt_path = _corrupt_text_path(row)
        if corrupt_path is not None:
            raise HandoffPackagingError(
                f"review queue row {index} contains corrupt public text at {corrupt_path}"
            )
        source_id = row.get("source_incident_id")
        source_hash = row.get("source_incident_sha256")
        if not isinstance(source_id, str) or not CMI_RE.fullmatch(source_id):
            raise HandoffPackagingError(f"review queue row {index} has an invalid source id")
        if not isinstance(source_hash, str) or not SHA256_RE.fullmatch(source_hash):
            raise HandoffPackagingError(
                f"review queue row {index} has an invalid source hash"
            )
        if source_id in queue_lineage:
            raise HandoffPackagingError(f"duplicate review queue source id: {source_id}")
        if row.get("queue_state") != REPORTED_UNREVIEWED:
            raise HandoffPackagingError(
                f"review queue row {source_id} is not reported_unreviewed"
            )
        if row.get("evidence_status") != REPORTED_UNREVIEWED:
            raise HandoffPackagingError(
                f"review queue row {source_id} has the wrong evidence_status"
            )
        queue_lineage[source_id] = source_hash
    if queue_lineage != dict(feature_lineage):
        raise HandoffPackagingError(
            "review queue lineage/hash pairs do not match overlay features"
        )


def _output_claim(
    adapter_manifest: Mapping[str, Any],
    *,
    name: str,
) -> Mapping[str, Any]:
    outputs = adapter_manifest.get("outputs")
    if not isinstance(outputs, Mapping) or not isinstance(outputs.get(name), Mapping):
        raise HandoffPackagingError(f"adapter manifest is missing outputs.{name}")
    return outputs[name]


def _verify_output_claim(
    adapter_manifest: Mapping[str, Any],
    *,
    name: str,
    data: bytes,
    count_key: str,
    expected_count: int,
) -> None:
    claim = _output_claim(adapter_manifest, name=name)
    if claim.get("sha256") != sha256_bytes(data):
        raise HandoffPackagingError(f"adapter manifest hash mismatch for {name}")
    if claim.get("size_bytes") != len(data):
        raise HandoffPackagingError(f"adapter manifest size mismatch for {name}")
    if claim.get(count_key) != expected_count:
        raise HandoffPackagingError(f"adapter manifest count mismatch for {name}")


def _validate_adapter_manifest(
    adapter_manifest: Mapping[str, Any],
    *,
    overlay_bytes: bytes,
    queue_bytes: bytes,
    overlay_summary: Mapping[str, Any],
    queue_count: int,
    repository_payloads: Mapping[str, bytes],
) -> dict[str, str]:
    corrupt_path = _corrupt_text_path(adapter_manifest)
    if corrupt_path is not None:
        raise HandoffPackagingError(
            f"adapter manifest contains corrupt public text at {corrupt_path}"
        )
    if adapter_manifest.get("layer_name") != LAYER_NAME:
        raise HandoffPackagingError(
            f"adapter manifest layer_name must be exactly {LAYER_NAME!r}"
        )
    if adapter_manifest.get("release_mode") != REPORTED_UNREVIEWED:
        raise HandoffPackagingError(
            "adapter manifest release_mode must be reported_unreviewed"
        )
    trace_policy = adapter_manifest.get("trace_policy")
    if not isinstance(trace_policy, Mapping):
        raise HandoffPackagingError("adapter manifest has no trace_policy")
    _assert_safety_contract(trace_policy, label="adapter manifest trace_policy")

    feature_count = int(overlay_summary["features"])
    _verify_output_claim(
        adapter_manifest,
        name=OVERLAY_NAME,
        data=overlay_bytes,
        count_key="features",
        expected_count=feature_count,
    )
    _verify_output_claim(
        adapter_manifest,
        name=QUEUE_NAME,
        data=queue_bytes,
        count_key="records",
        expected_count=queue_count,
    )

    counts = adapter_manifest.get("counts")
    if not isinstance(counts, Mapping):
        raise HandoffPackagingError("adapter manifest counts must be an object")
    exact_counts = {
        "total_source_incidents": feature_count,
        "decision_ledger_rows": 0,
        "accepted": 0,
        "reported_unreviewed": feature_count,
        "rejected": 0,
        "unresolved": 0,
        "missing_decision": queue_count,
        "mapped_incidents": overlay_summary["features_with_geometry"],
        "unmapped_incidents": overlay_summary["features_without_geometry"],
        "queued_for_review": queue_count,
        "features_with_geometry": overlay_summary["features_with_geometry"],
        "features_without_geometry": overlay_summary["features_without_geometry"],
        "generated_artifacts": 3,
    }
    for name, expected in exact_counts.items():
        actual = _required_nonnegative_int(
            counts.get(name),
            label=f"adapter manifest counts.{name}",
        )
        if actual != expected:
            raise HandoffPackagingError(
                f"adapter manifest counts.{name}={actual} does not reconcile {expected}"
            )

    pending_relationships = adapter_manifest.get("pending_relationships")
    if not isinstance(pending_relationships, Mapping) or pending_relationships.get(
        "emitted"
    ) != 0:
        raise HandoffPackagingError(
            "adapter manifest must emit zero cross-domain relationships"
        )

    schema_claims = adapter_manifest.get("schema_sha256")
    if not isinstance(schema_claims, Mapping):
        raise HandoffPackagingError("adapter manifest schema_sha256 must be an object")
    schema_paths = {
        "overlay": "schemas/timeline_overlay.schema.json",
        "review_decision": "schemas/timeline_review_decision.schema.json",
        "source_case": "schemas/case.schema.json",
    }
    for claim_name, archive_path in schema_paths.items():
        if schema_claims.get(claim_name) != sha256_bytes(
            repository_payloads[archive_path]
        ):
            raise HandoffPackagingError(
                f"adapter manifest schema hash mismatch for {claim_name}"
            )

    adapter_version = adapter_manifest.get("adapter_version")
    source_commit = adapter_manifest.get("source_commit")
    seed_pipeline_version = adapter_manifest.get("seed_pipeline_version")
    if not isinstance(adapter_version, str) or not ADAPTER_VERSION_RE.fullmatch(
        adapter_version
    ):
        raise HandoffPackagingError("adapter manifest adapter_version is invalid")
    if not isinstance(source_commit, str) or not GIT_COMMIT_RE.fullmatch(source_commit):
        raise HandoffPackagingError("adapter manifest source_commit is invalid")
    if not isinstance(seed_pipeline_version, str) or not PIPELINE_VERSION_RE.fullmatch(
        seed_pipeline_version
    ):
        raise HandoffPackagingError("adapter manifest seed_pipeline_version is invalid")

    adapter_source = repository_payloads[
        "adapter/build_animal_mutilation_timeline_layer.py"
    ]
    version_match = re.search(
        rb'^ADAPTER_VERSION\s*=\s*"([^"]+)"',
        adapter_source,
        flags=re.MULTILINE,
    )
    if version_match is None or version_match.group(1).decode("ascii") != adapter_version:
        raise HandoffPackagingError(
            "included adapter source does not match adapter manifest version"
        )
    return {
        "adapter_version": adapter_version,
        "seed_source_commit": source_commit,
        "seed_pipeline_version": seed_pipeline_version,
    }


def _handoff_markdown(
    *,
    release_commit: str,
    identities: Mapping[str, str],
    overlay_summary: Mapping[str, Any],
) -> bytes:
    return (
        "# Animal Mutilation Reports - UFO Timeline Handoff\n\n"
        "This package contains a deterministic, public-safe context layer named "
        f"`{LAYER_NAME}`. It is ready for product integration without reopening "
        "the extraction or classifier research campaign.\n\n"
        "## Release identity\n\n"
        f"- Release commit: `{release_commit}`\n"
        f"- Seed source commit: `{identities['seed_source_commit']}`\n"
        f"- Seed pipeline: `{identities['seed_pipeline_version']}`\n"
        f"- Timeline adapter: `{identities['adapter_version']}`\n"
        f"- Report features: {overlay_summary['features']}\n"
        f"- Features with public geometry: {overlay_summary['features_with_geometry']}\n"
        f"- Features without public geometry: {overlay_summary['features_without_geometry']}\n\n"
        "## Custody and privacy\n\n"
        "The ZIP contains only bounded public evidence, deterministic lineage, "
        "schemas, adapter source, and the review queue. Raw third-party pages, "
        "images, private caches, internal coordinates, and private-property "
        "locators are not included. Continue to honor each feature's privacy and "
        "uncertainty fields; never infer a more precise place or date.\n\n"
        "## Scientific limitations\n\n"
        "Every feature is a `reported_unreviewed` source report, not a verified "
        "scientific finding. The layer asserts no cause, does not authenticate UFO "
        "or crop-circle claims, and is never a craft trace endpoint. Source-access "
        "gaps are unknown coverage, not negative evidence. Cross-domain candidates "
        "remain separate from this context overlay. Evidence may describe animal "
        "death or injury and should retain the supplied content warning.\n\n"
        "## Verification\n\n"
        "Validate every payload against `handoff_manifest.json` before import. The "
        "manifest intentionally excludes its own digest from its file table because "
        "a file cannot contain its final SHA-256 without a recursive identity. ZIP "
        "entry names, timestamps, permissions, and order are fixed for reproducible "
        "builds.\n"
    ).encode("utf-8")


def _import_prompt(*, release_commit: str) -> bytes:
    return (
        "Integrate the supplied GeoJSON into the UFO Timeline as a distinct layer "
        f"named exactly `{LAYER_NAME}`. Use the supplied adapter output and schemas; "
        "do not reopen or rerun extraction, classifier, crop-circle, or source "
        "research. Do not gate display on analyst verification: every supplied "
        "feature is intentionally publishable as `reported_unreviewed`, while the "
        "review queue supports later adjudication. Preserve `status`, "
        "`evidence_status`, lineage IDs, source hashes, privacy, uncertainty, content "
        "warnings, and null geometry exactly. Keep this layer separate from UFO/UAP "
        "craft sightings and trace segments. Enforce `trace_eligible=false`, "
        "`trace_role=context_only`, and `causality=not_asserted`; never infer or "
        "display causation. Verify all payload hashes and counts in "
        "`handoff_manifest.json` before making product changes. Do not mutate the "
        "seed outputs. The handoff release commit is "
        f"`{release_commit}`.\n"
    ).encode("utf-8")


def _file_identity(data: bytes, *, role: str) -> dict[str, Any]:
    return {
        "role": role,
        "sha256": sha256_bytes(data),
        "size_bytes": len(data),
    }


def _zip_info(path: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(path, date_time=ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    info.internal_attr = 0
    info.extra = b""
    info.comment = b""
    return info


def _write_deterministic_zip(path: Path, payloads: Mapping[str, bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    try:
        with zipfile.ZipFile(
            temporary_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
            strict_timestamps=True,
        ) as archive:
            for archive_path in sorted(payloads):
                archive.writestr(
                    _zip_info(archive_path),
                    payloads[archive_path],
                    compress_type=zipfile.ZIP_DEFLATED,
                    compresslevel=9,
                )
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def package_handoff(
    *,
    adapter_output_dir: Path,
    output_zip: Path,
    release_commit: str,
) -> dict[str, Any]:
    """Validate adapter output and write the fixed-content handoff ZIP."""

    if not GIT_COMMIT_RE.fullmatch(release_commit):
        raise HandoffPackagingError("release_commit must be a lowercase 40-character Git SHA")
    adapter_dir = Path(adapter_output_dir).resolve()
    target_zip = Path(output_zip).resolve()
    if not adapter_dir.is_dir():
        raise HandoffPackagingError(f"adapter output directory is missing: {adapter_dir}")
    if target_zip == adapter_dir or adapter_dir in target_zip.parents:
        raise HandoffPackagingError(
            "output ZIP must be outside the adapter output directory"
        )

    payloads: dict[str, bytes] = {}
    roles: dict[str, str] = {}
    for archive_path, source_path, role in REPOSITORY_PAYLOADS:
        if not source_path.is_file():
            raise HandoffPackagingError(f"required repository file is missing: {source_path}")
        payloads[archive_path] = source_path.read_bytes()
        roles[archive_path] = role
    for archive_path, source_name, role in ADAPTER_PAYLOADS:
        source_path = adapter_dir / source_name
        if not source_path.is_file():
            raise HandoffPackagingError(f"required adapter output is missing: {source_path}")
        payloads[archive_path] = source_path.read_bytes()
        roles[archive_path] = role

    overlay_bytes = payloads[f"data/{OVERLAY_NAME}"]
    queue_bytes = payloads[f"data/{QUEUE_NAME}"]
    adapter_manifest_bytes = payloads[f"manifest/{IMPORT_MANIFEST_NAME}"]
    overlay = _load_json(overlay_bytes, label=OVERLAY_NAME)
    queue = _load_jsonl(queue_bytes, label=QUEUE_NAME)
    adapter_manifest = _load_json(
        adapter_manifest_bytes,
        label=IMPORT_MANIFEST_NAME,
    )
    overlay_summary = _validate_overlay(overlay)
    _validate_queue(queue, feature_lineage=overlay_summary["lineage"])
    identities = _validate_adapter_manifest(
        adapter_manifest,
        overlay_bytes=overlay_bytes,
        queue_bytes=queue_bytes,
        overlay_summary=overlay_summary,
        queue_count=len(queue),
        repository_payloads=payloads,
    )

    payloads["HANDOFF.md"] = _handoff_markdown(
        release_commit=release_commit,
        identities=identities,
        overlay_summary=overlay_summary,
    )
    roles["HANDOFF.md"] = "custody_and_limitations_handoff"
    payloads["IMPORT_PROMPT.md"] = _import_prompt(release_commit=release_commit)
    roles["IMPORT_PROMPT.md"] = "bounded_ufo_timeline_import_instruction"

    file_inventory = {
        archive_path: _file_identity(data, role=roles[archive_path])
        for archive_path, data in sorted(payloads.items())
    }
    archive_paths = sorted([*payloads, "handoff_manifest.json"])
    handoff_manifest = {
        "schema_version": HANDOFF_VERSION,
        "layer_name": LAYER_NAME,
        "release_mode": REPORTED_UNREVIEWED,
        "release_commit": release_commit,
        "seed_source_commit": identities["seed_source_commit"],
        "seed_pipeline_version": identities["seed_pipeline_version"],
        "adapter_version": identities["adapter_version"],
        "record_counts": {
            "reported_unreviewed_features": overlay_summary["features"],
            "review_queue_records": len(queue),
            "features_with_geometry": overlay_summary["features_with_geometry"],
            "features_without_geometry": overlay_summary["features_without_geometry"],
            "source_references": overlay_summary["source_refs"],
        },
        "trace_policy": {
            "trace_eligible": False,
            "trace_role": "context_only",
            "causality": "not_asserted",
        },
        "files": file_inventory,
        "archive_paths": archive_paths,
        "archive_entry_count": len(archive_paths),
        "manifest_self_hash_policy": (
            "handoff_manifest.json is listed as an archive path but excluded from "
            "files because embedding its final SHA-256 would be recursive"
        ),
        "zip_policy": {
            "entry_order": "lexicographic_path",
            "entry_timestamp": "1980-01-01T00:00:00Z",
            "compression": "deflate_level_9",
            "unix_mode": "0100644",
        },
    }
    payloads["handoff_manifest.json"] = canonical_json_bytes(handoff_manifest)
    _write_deterministic_zip(target_zip, payloads)
    return handoff_manifest


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate and package an already-built Animal Mutilation Reports "
            "adapter output for UFO Timeline integration."
        )
    )
    parser.add_argument(
        "--adapter-output-dir",
        type=Path,
        required=True,
        help="Directory containing the three deterministic Timeline adapter outputs.",
    )
    parser.add_argument(
        "--output-zip",
        type=Path,
        required=True,
        help="Target handoff ZIP path outside the adapter output directory.",
    )
    parser.add_argument(
        "--release-commit",
        required=True,
        help="Lowercase 40-character Git commit for the handoff release.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        manifest = package_handoff(
            adapter_output_dir=args.adapter_output_dir,
            output_zip=args.output_zip,
            release_commit=args.release_commit,
        )
    except HandoffPackagingError as exc:
        print(f"ERROR: {exc}", file=os.sys.stderr)
        return 2
    print(
        "Packaged Animal Mutilation Reports handoff: "
        f"features={manifest['record_counts']['reported_unreviewed_features']} "
        f"queue={manifest['record_counts']['review_queue_records']} "
        f"zip={Path(args.output_zip).resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
