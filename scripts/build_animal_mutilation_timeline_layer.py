#!/usr/bin/env python3
"""Build a deterministic, public-safe animal-mutilation Timeline overlay.

Without a review ledger, every eligible seed incident is emitted as clearly
labelled ``reported_unreviewed`` context and is also retained in the review
queue.  Optional review decisions remain supported for later adjudication.
The adapter never mutates the seed, canonical UFO artifacts, the frontend, or
trace data.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import unquote_plus, urlsplit


ADAPTER_VERSION = "animal-mutilation-timeline-adapter-v1.1.1"
DECISION_SCHEMA_VERSION = "animal-mutilation-timeline-review-decision-v1.0.0"
OVERLAY_SCHEMA_VERSION = "animal-mutilation-timeline-overlay-v1.1.0"
QUEUE_SCHEMA_VERSION = "animal-mutilation-timeline-review-queue-v1.1.0"
COORDINATE_AUDIT_SCHEMA_VERSION = (
    "animal-mutilation-timeline-coordinate-normalization-audit-v1.0.0"
)
MANIFEST_SCHEMA_VERSION = "animal-mutilation-timeline-import-manifest-v1.1.1"
EXPECTED_RUN_MODE = "full_global_existing_corpora"
EXPECTED_SEED_PIPELINE_VERSION = "animal-mutilation-cross-domain-seed-v1.1.12"
LAYER_NAME = "Animal Mutilation Reports"

CANONICAL_NAME = "canonical_incidents.jsonl"
SEED_MANIFEST_NAME = "run_manifest.json"
QUEUE_NAME = "timeline_review_queue.jsonl"
OVERLAY_NAME = "animal_mutilations.geojson"
COORDINATE_AUDIT_NAME = "animal_mutilation_coordinate_normalization_audit.jsonl"
IMPORT_MANIFEST_NAME = "animal_mutilations_import_manifest.json"
OUTPUT_NAMES = (
    QUEUE_NAME,
    OVERLAY_NAME,
    COORDINATE_AUDIT_NAME,
    IMPORT_MANIFEST_NAME,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CASE_SCHEMA_PATH = REPO_ROOT / "docs" / "cattle_mutilation" / "case.schema.json"
DECISION_SCHEMA_PATH = (
    REPO_ROOT / "docs" / "cattle_mutilation" / "timeline_review_decision.schema.json"
)
OVERLAY_SCHEMA_PATH = (
    REPO_ROOT / "docs" / "cattle_mutilation" / "timeline_overlay.schema.json"
)
QUEUE_SCHEMA_PATH = (
    REPO_ROOT / "docs" / "cattle_mutilation" / "timeline_review_queue.schema.json"
)
COORDINATE_AUDIT_SCHEMA_PATH = (
    REPO_ROOT
    / "docs"
    / "cattle_mutilation"
    / "timeline_coordinate_normalization_audit.schema.json"
)

CMI_RE = re.compile(r"^cmi_[0-9a-f]{24}$")
AMI_RE = re.compile(r"^ami_[0-9a-f]{24}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
VALIDATION_SCHEMA_RE = re.compile(
    r"^animal-mutilation-validation-provenance-v\d+\.\d+\.\d+$"
)

VICTIM_ROLES = frozenset({"reported_victim", "possible_victim"})
PRIVATE_PRIVACY_LEVELS = frozenset({"internal_only", "withheld"})
UFOCAT_SOURCE_PUBLISHERS = ("ufocat",)
STANDARD_SIGNED_SOURCE_PUBLISHERS = ("majestic",)
UFOCAT_LONGITUDE_RULE_ID = "ufocat_legacy_longitude_sign_v1"

# Broad semantic envelopes are validation guards, not geocoders. They reject an
# impossible source/region projection after the provenance-scoped longitude
# convention has been applied; they never select or invent a replacement point.
# Values are (minimum longitude, maximum longitude, minimum latitude, maximum latitude).
SEMANTIC_REGION_BOUNDS: Mapping[str, tuple[float, float, float, float]] = {
    "US": (-180.0, -60.0, 15.0, 72.0),
    "USA": (-180.0, -60.0, 15.0, 72.0),
    "CN": (-141.0, -52.0, 41.0, 84.0),
    "CA": (-120.0, -60.0, 5.0, 33.0),
    "SA": (-82.0, -34.0, -56.0, 13.0),
    "EU": (-25.0, 45.0, 34.0, 72.0),
    "ME": (25.0, 65.0, 12.0, 42.0),
    "AU": (110.0, 155.0, -45.0, -10.0),
    "Argentina": (-74.0, -53.0, -56.0, -21.0),
    "Brazil": (-74.0, -34.0, -34.0, 6.0),
    "France": (-6.0, 10.0, 41.0, 52.0),
    "Israel": (34.0, 36.0, 29.0, 34.0),
}
CORRUPT_TEXT_MARKERS: tuple[tuple[str, str], ...] = (
    ("unicode_replacement_character", "\N{REPLACEMENT CHARACTER}"),
    (
        "known_mojibake_sequence",
        "\N{GREEK CAPITAL LETTER GAMMA}\N{LATIN CAPITAL LETTER C WITH CEDILLA}",
    ),
)

# These patterns are deliberately conservative.  A reviewer can supply clean
# approved_public_fields, but the adapter never silently publishes a suspicious
# display string.
DISPLAY_LEAK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("embedded_url", re.compile(r"(?i)(?:https?://|www\.)")),
    (
        "email_address",
        re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"),
    ),
    (
        "telephone_number",
        re.compile(
            r"(?<!\d)(?:\+?1[-. ]?)?(?:\(\d{3}\)|\d{3})"
            r"[-. ]\d{3}[-. ]\d{4}\b"
        ),
    ),
    (
        "street_address",
        re.compile(
            r"(?i)\b\d{1,6}(?:[-\N{EN DASH}\N{EM DASH}]\d{1,6})?\s+"
            r"(?:[A-Z0-9.'-]+\s+){1,6}"
            r"(?:Road|Rd|Street|St|Avenue|Ave|Lane|Ln|Drive|Dr|Highway|Hwy|"
            r"Route|Rt|Boulevard|Blvd|Court|Ct|Way)\b"
        ),
    ),
    (
        "named_private_property",
        re.compile(
            r"\b[A-Z][A-Za-z0-9&.'\N{RIGHT SINGLE QUOTATION MARK}-]*"
            r"(?:\s+(?:and|&|[A-Z][A-Za-z0-9&.'\N{RIGHT SINGLE QUOTATION MARK}-]*)){0,3}"
            r"\s+(?:Ranch|Farm|Homestead)\b"
        ),
    ),
    (
        "lowercase_named_private_property",
        re.compile(
            r"\b[a-z][a-z0-9&.'\N{RIGHT SINGLE QUOTATION MARK}-]*"
            r"(?:\s+(?:and|&|[a-z][a-z0-9&.'\N{RIGHT SINGLE QUOTATION MARK}-]*)){0,3}"
            r"\s+(?:ranch|farm|homestead)\b"
        ),
    ),
    (
        "coordinate_pair",
        re.compile(
            r"(?<![\w.])[-+]?(?:[0-8]?\d(?:\.\d{3,})?|90(?:\.0{3,})?)"
            r"\s*[,;/]\s*[-+]?(?:1[0-7]\d(?:\.\d{3,})?|"
            r"(?:[0-9]?\d)(?:\.\d{3,})?|180(?:\.0{3,})?)(?!\d|\.\d)"
        ),
    ),
    (
        "person_attribution",
        re.compile(
            r"(?i)\b(?:reported by|owned by|owner|rancher)\s+"
            r"(?!\[(?:name|private)[^\]]*\])"
            r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b"
        ),
    ),
)


class TimelineAdapterError(RuntimeError):
    """A fail-closed Timeline projection error."""


def canonical_json_bytes(value: Any) -> bytes:
    """Return the canonical JSON representation used for lineage hashes."""

    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_json_line(value: Any) -> bytes:
    return canonical_json_bytes(value) + b"\n"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reject_json_constant(token: str) -> None:
    raise ValueError(f"non-finite JSON number {token!r} is not allowed")


def _load_json_bytes(data: bytes, *, label: str) -> Any:
    try:
        return json.loads(data.decode("utf-8"), parse_constant=_reject_json_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise TimelineAdapterError(f"invalid JSON in {label}: {exc}") from exc


def _load_schema(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise TimelineAdapterError(f"required schema is missing: {path}")
    value = _load_json_bytes(path.read_bytes(), label=str(path))
    if not isinstance(value, dict):
        raise TimelineAdapterError(f"schema must be an object: {path}")
    return value


def _jsonschema_validator(schema: Mapping[str, Any], *, label: str) -> Any:
    try:
        from jsonschema import Draft202012Validator, FormatChecker
    except ImportError as exc:  # pragma: no cover - the production lock includes it.
        raise TimelineAdapterError(
            "jsonschema is required for Timeline adapter validation"
        ) from exc
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        raise TimelineAdapterError(f"invalid {label} schema: {exc}") from exc
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _validate_instance(validator: Any, value: Any, *, label: str) -> None:
    errors = sorted(
        validator.iter_errors(value),
        key=lambda error: tuple(str(item) for item in error.absolute_path),
    )
    if not errors:
        return
    error = errors[0]
    pointer = "/" + "/".join(str(item) for item in error.absolute_path)
    if pointer == "/":
        pointer = "<root>"
    raise TimelineAdapterError(f"{label} schema validation failed at {pointer}: {error.message}")


def _read_jsonl(
    path: Path,
    *,
    label: str,
    validator: Any,
) -> list[dict[str, Any]]:
    if not path.is_file():
        raise TimelineAdapterError(f"required {label} file is missing: {path}")
    rows: list[dict[str, Any]] = []
    with path.open("rb") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            if not raw_line.strip():
                continue
            value = _load_json_bytes(raw_line, label=f"{path} line {line_number}")
            if not isinstance(value, dict):
                raise TimelineAdapterError(
                    f"{label} line {line_number} must be a JSON object"
                )
            _validate_instance(
                validator,
                value,
                label=f"{label} line {line_number}",
            )
            rows.append(value)
    return rows


def _manifest_output_claim(manifest: Mapping[str, Any]) -> Mapping[str, Any]:
    outputs = manifest.get("outputs")
    if not isinstance(outputs, Mapping):
        raise TimelineAdapterError("seed run_manifest.outputs must be an object")
    claim = outputs.get(CANONICAL_NAME)
    if not isinstance(claim, Mapping):
        raise TimelineAdapterError(
            f"seed run_manifest is missing outputs.{CANONICAL_NAME}"
        )
    expected_hash = claim.get("sha256")
    expected_size = claim.get("size_bytes")
    if not isinstance(expected_hash, str) or not SHA256_RE.fullmatch(expected_hash):
        raise TimelineAdapterError("seed canonical SHA-256 claim is invalid")
    if not isinstance(expected_size, int) or isinstance(expected_size, bool) or expected_size < 0:
        raise TimelineAdapterError("seed canonical size claim is invalid")
    return claim


def _load_and_verify_seed_manifest(seed_output_dir: Path) -> tuple[dict[str, Any], str]:
    manifest_path = seed_output_dir / SEED_MANIFEST_NAME
    if not manifest_path.is_file():
        raise TimelineAdapterError(f"seed run manifest is missing: {manifest_path}")
    manifest_bytes = manifest_path.read_bytes()
    value = _load_json_bytes(manifest_bytes, label=str(manifest_path))
    if not isinstance(value, dict):
        raise TimelineAdapterError("seed run_manifest must be a JSON object")
    if value.get("run_mode") != EXPECTED_RUN_MODE:
        raise TimelineAdapterError(
            "seed run_manifest.run_mode must be full_global_existing_corpora"
        )
    if value.get("pipeline_version") != EXPECTED_SEED_PIPELINE_VERSION:
        raise TimelineAdapterError(
            "seed run_manifest.pipeline_version must be "
            f"{EXPECTED_SEED_PIPELINE_VERSION} for the locked coordinate-normalization contract"
        )
    _manifest_output_claim(value)
    return value, sha256_bytes(manifest_bytes)


def _verify_canonical_artifact(seed_output_dir: Path, manifest: Mapping[str, Any]) -> tuple[Path, str]:
    canonical_path = seed_output_dir / CANONICAL_NAME
    if not canonical_path.is_file():
        raise TimelineAdapterError(f"seed canonical incidents are missing: {canonical_path}")
    claim = _manifest_output_claim(manifest)
    actual_size = canonical_path.stat().st_size
    if actual_size != claim["size_bytes"]:
        raise TimelineAdapterError(
            f"seed canonical size mismatch: expected {claim['size_bytes']}, got {actual_size}"
        )
    actual_hash = sha256_file(canonical_path)
    if actual_hash != claim["sha256"]:
        raise TimelineAdapterError(
            f"seed canonical SHA-256 mismatch: expected {claim['sha256']}, got {actual_hash}"
        )
    return canonical_path, actual_hash


def _incident_id(incident: Mapping[str, Any]) -> str:
    canonical_id = incident.get("canonical_incident_id")
    record_id = incident.get("record_id")
    if not isinstance(canonical_id, str) or not CMI_RE.fullmatch(canonical_id):
        raise TimelineAdapterError("canonical incident has an invalid canonical_incident_id")
    if record_id != canonical_id:
        raise TimelineAdapterError(
            f"canonical incident record_id does not match canonical_incident_id {canonical_id}"
        )
    return canonical_id


def _normalize_space(value: Any) -> str:
    return re.sub(r"\s+", " ", "" if value is None else str(value)).strip()


def _case_date_projection(incident: Mapping[str, Any]) -> dict[str, Any]:
    dates = incident.get("dates") if isinstance(incident.get("dates"), Mapping) else {}
    return {
        "event_start": dates.get("event_start"),
        "event_end": dates.get("event_end"),
        "precision": _normalize_space(dates.get("precision")) or "unknown",
    }


def _case_public_location_projection(incident: Mapping[str, Any]) -> dict[str, Any]:
    location = (
        incident.get("location")
        if isinstance(incident.get("location"), Mapping)
        else {}
    )
    return {
        "raw_text": location.get("raw_text"),
        "country_code": location.get("country_code"),
        "admin1": location.get("admin1"),
        "admin2": location.get("admin2"),
        "locality": location.get("locality"),
        "latitude_public": location.get("latitude_public"),
        "longitude_public": location.get("longitude_public"),
        "precision": _normalize_space(location.get("precision")) or "unknown",
        "privacy_level": _normalize_space(location.get("privacy_level")) or "unknown",
    }


def _expected_case_projection(incident: Mapping[str, Any]) -> dict[str, Any]:
    """Mirror the seed validator's closed public case projection."""

    animal_fields = (
        "reported_text",
        "reported_taxon_key",
        "normalized_common_name",
        "species_group",
        "domestic_context",
        "incident_role",
        "identification_basis",
        "identification_confidence",
        "source_ids",
    )

    def animal_projection(field: str) -> list[dict[str, Any]]:
        rows = incident.get(field, []) if isinstance(incident.get(field), list) else []
        return sorted(
            [
                {key: row.get(key) for key in animal_fields}
                for row in rows
                if isinstance(row, Mapping)
            ],
            key=canonical_json_bytes,
        )

    return {
        "event_domain": incident.get("event_domain"),
        "explicit_negative": bool(incident.get("explicit_negative")),
        "negative_only": bool(incident.get("negative_only")),
        "dates": _case_date_projection(incident),
        "public_location": _case_public_location_projection(incident),
        "animals": animal_projection("animals"),
        "animal_context": animal_projection("animal_context"),
    }


def _validate_manifest_coverage(
    manifest: Mapping[str, Any],
    incidents: Mapping[str, Mapping[str, Any]],
) -> None:
    incident_ids = list(incidents)
    counts = manifest.get("counts")
    expected_count = counts.get("canonical_incidents") if isinstance(counts, Mapping) else None
    if not isinstance(expected_count, int) or isinstance(expected_count, bool):
        raise TimelineAdapterError("seed run_manifest canonical_incidents count is invalid")
    if expected_count != len(incident_ids):
        raise TimelineAdapterError(
            f"canonical row count mismatch: manifest={expected_count}, rows={len(incident_ids)}"
        )

    provenance = manifest.get("validation_provenance")
    if not isinstance(provenance, Mapping):
        raise TimelineAdapterError("seed validation_provenance is required")
    schema_version = provenance.get("schema_version")
    if not isinstance(schema_version, str) or not VALIDATION_SCHEMA_RE.fullmatch(schema_version):
        raise TimelineAdapterError(
            "seed validation_provenance schema is missing or unrecognized"
        )
    registry_hash = provenance.get("registry_sha256")
    if not isinstance(registry_hash, str) or not SHA256_RE.fullmatch(registry_hash):
        raise TimelineAdapterError("seed validation_provenance registry_sha256 is invalid")
    registry_payload = dict(provenance)
    registry_payload.pop("registry_sha256", None)
    recomputed_registry_hash = sha256_bytes(canonical_json_bytes(registry_payload))
    if registry_hash != recomputed_registry_hash:
        raise TimelineAdapterError(
            "seed validation_provenance registry SHA-256 mismatch"
        )
    case_decisions = provenance.get("case_decisions")
    if not isinstance(case_decisions, list):
        raise TimelineAdapterError("seed validation_provenance.case_decisions must be an array")
    decisions_by_id: dict[str, Mapping[str, Any]] = {}
    for index, decision in enumerate(case_decisions):
        if not isinstance(decision, Mapping):
            raise TimelineAdapterError(
                f"seed validation case decision {index} is malformed"
            )
        record_id = _normalize_space(decision.get("record_id"))
        if not record_id:
            raise TimelineAdapterError(
                f"seed validation case decision {index} has no record_id"
            )
        if record_id in decisions_by_id:
            raise TimelineAdapterError(
                f"seed validation provenance has duplicate case decision: {record_id}"
            )
        decisions_by_id[record_id] = decision

    missing = sorted(set(incident_ids) - set(decisions_by_id))
    if missing:
        sample = ", ".join(missing[:3])
        raise TimelineAdapterError(
            f"seed validation provenance does not resolve {len(missing)} canonical incidents: {sample}"
        )
    for record_id in sorted(incident_ids):
        decision = decisions_by_id[record_id]
        expected = decision.get("expected")
        if not isinstance(expected, Mapping):
            raise TimelineAdapterError(
                f"seed validation decision is incomplete for {record_id}"
            )
        expected_hash = decision.get("expected_projection_sha256")
        if not isinstance(expected_hash, str) or not SHA256_RE.fullmatch(expected_hash):
            raise TimelineAdapterError(
                f"seed validation decision hash is malformed for {record_id}"
            )
        recomputed_expected_hash = sha256_bytes(canonical_json_bytes(dict(expected)))
        if expected_hash != recomputed_expected_hash:
            raise TimelineAdapterError(
                f"seed validation decision hash mismatch for {record_id}"
            )
        actual_projection = _expected_case_projection(incidents[record_id])
        if dict(expected) != actual_projection:
            raise TimelineAdapterError(
                f"seed validation decision projection mismatch for {record_id}"
            )


def _canonical_incident_sha256(incident: Mapping[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes(incident))


def _index_incidents(
    incidents: Sequence[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    by_id: dict[str, dict[str, Any]] = {}
    hashes: dict[str, str] = {}
    for incident in incidents:
        source_id = _incident_id(incident)
        if source_id in by_id:
            raise TimelineAdapterError(f"duplicate canonical incident ID: {source_id}")
        by_id[source_id] = incident
        hashes[source_id] = _canonical_incident_sha256(incident)
    return by_id, hashes


def _load_decisions(
    review_decisions: Path | None,
    *,
    validator: Any,
) -> tuple[list[dict[str, Any]], bytes]:
    if review_decisions is None:
        return [], b""
    if not review_decisions.is_file():
        raise TimelineAdapterError(f"review decision ledger is missing: {review_decisions}")
    ledger_bytes = review_decisions.read_bytes()
    rows = _read_jsonl(
        review_decisions,
        label="review decision",
        validator=validator,
    )
    return rows, ledger_bytes


def _index_and_verify_decisions(
    decisions: Sequence[dict[str, Any]],
    incidents: Mapping[str, dict[str, Any]],
    incident_hashes: Mapping[str, str],
) -> dict[str, dict[str, Any]]:
    by_source: dict[str, dict[str, Any]] = {}
    decision_ids: set[str] = set()
    ami_ids: set[str] = set()
    superseded_ids: set[str] = set()
    for decision in decisions:
        decision_id = decision["review_decision_id"]
        source_id = decision["source_incident_id"]
        if decision_id in decision_ids:
            raise TimelineAdapterError(f"duplicate review_decision_id: {decision_id}")
        decision_ids.add(decision_id)
        if source_id in by_source:
            raise TimelineAdapterError(f"duplicate review decision for source incident: {source_id}")
        if source_id not in incidents:
            raise TimelineAdapterError(f"review decision references unknown incident: {source_id}")
        expected_hash = incident_hashes[source_id]
        if decision["source_incident_sha256"] != expected_hash:
            raise TimelineAdapterError(
                f"stale review decision for {source_id}: canonical JSON SHA-256 changed"
            )
        supersedes = decision.get("supersedes_source_incident_ids", [])
        if source_id in supersedes:
            raise TimelineAdapterError(
                f"review decision {decision_id} cannot supersede its own source incident"
            )
        for superseded_id in supersedes:
            if superseded_id in incidents:
                raise TimelineAdapterError(
                    f"review decision {decision_id} supersedes current incident {superseded_id}"
                )
            if superseded_id in superseded_ids:
                raise TimelineAdapterError(
                    f"historical source incident is claimed by multiple decisions: {superseded_id}"
                )
            superseded_ids.add(superseded_id)
        if decision["disposition"] == "accepted":
            ami_id = decision["animal_mutilation_event_id"]
            if not isinstance(ami_id, str) or not AMI_RE.fullmatch(ami_id):
                raise TimelineAdapterError(f"accepted decision {decision_id} has an invalid AMI")
            if ami_id in ami_ids:
                raise TimelineAdapterError(f"persistent AMI is reused in the ledger: {ami_id}")
            ami_ids.add(ami_id)
        by_source[source_id] = decision
    return by_source


def _victim_rows(incident: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    animals = incident.get("animals")
    if not isinstance(animals, list):
        return []
    return [
        animal
        for animal in animals
        if isinstance(animal, Mapping) and animal.get("incident_role") in VICTIM_ROLES
    ]


def _require_eligible_incident(
    incident: Mapping[str, Any], source_id: str
) -> list[Mapping[str, Any]]:
    if incident.get("event_domain") != "animal_mutilation":
        raise TimelineAdapterError(f"{source_id} is not in the animal_mutilation domain")
    if incident.get("record_type") != "mutilation_case":
        raise TimelineAdapterError(f"{source_id} is not a mutilation_case")
    if incident.get("negative_only") is not False:
        raise TimelineAdapterError(f"{source_id} is negative-only")
    provenance = incident.get("provenance")
    if isinstance(provenance, Mapping) and provenance.get("review_state") == "rejected_as_noise":
        raise TimelineAdapterError(f"{source_id} was rejected as extraction noise")
    victims = _victim_rows(incident)
    if not victims:
        raise TimelineAdapterError(f"{source_id} has no victim animal assertion")
    return victims


def _clean_text(value: Any, *, field: str, max_length: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TimelineAdapterError(f"public field {field} must be a string or null")
    text = " ".join(value.split())
    if not text:
        return None
    if len(text) > max_length:
        raise TimelineAdapterError(
            f"public field {field} exceeds its {max_length}-character bound; reviewer override required"
        )
    return text


def _display_leak_reason(text: str) -> str | None:
    for reason, pattern in DISPLAY_LEAK_PATTERNS:
        if pattern.search(text):
            return reason
    return None


def _text_corruption_reason(text: str) -> str | None:
    for reason, marker in CORRUPT_TEXT_MARKERS:
        if marker in text:
            return reason
    return None


def _assert_display_text_safe(text: str, *, field: str) -> None:
    corruption_reason = _text_corruption_reason(text)
    if corruption_reason:
        raise TimelineAdapterError(
            f"public field {field} contains disallowed {corruption_reason}"
        )
    reason = _display_leak_reason(text)
    if reason:
        raise TimelineAdapterError(f"public field {field} contains disallowed {reason}")


def _valid_public_url(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise TimelineAdapterError(f"{field} must be a non-empty URL string")
    if any(character.isspace() for character in value):
        raise TimelineAdapterError(f"{field} contains whitespace")
    try:
        parsed = urlsplit(value)
        _ = parsed.port
    except ValueError as exc:
        raise TimelineAdapterError(f"{field} is malformed: {exc}") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise TimelineAdapterError(f"{field} must use http or https and include a host")
    if parsed.username is not None or parsed.password is not None:
        raise TimelineAdapterError(f"{field} must not contain URL credentials")
    return value


def _decoded_url_privacy_reason(value: str) -> str | None:
    """Inspect decoded path/query/fragment text before publishing a source URL."""

    parsed = urlsplit(value)
    locator_text = " ".join((parsed.path, parsed.query, parsed.fragment))
    for _ in range(3):
        decoded = unquote_plus(locator_text)
        if decoded == locator_text:
            break
        locator_text = decoded
    normalized = re.sub(r"[/\\?&#=._+%:-]+", " ", locator_text)
    corruption_reason = _text_corruption_reason(normalized)
    if corruption_reason:
        return corruption_reason
    return _display_leak_reason(normalized)


def _iter_strings(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], str]]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, Mapping):
        for key, child in value.items():
            yield from _iter_strings(child, path + (str(key),))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _iter_strings(child, path + (str(index),))


def _scan_emitted_strings(value: Any, *, artifact: str) -> None:
    for path, text in _iter_strings(value):
        dotted = ".".join(path)
        # A URL is allowed only in the dedicated typed source_refs[].url field.
        if path and path[-1] == "url" and "source_refs" in path:
            url = _valid_public_url(text, field=f"{artifact}:{dotted}")
            reason = _decoded_url_privacy_reason(url)
            if reason:
                raise TimelineAdapterError(
                    f"public field {artifact}:{dotted} contains disallowed decoded URL {reason}"
                )
            continue
        _assert_display_text_safe(text, field=f"{artifact}:{dotted}")


def _coordinate(value: Any, *, field: str, minimum: float, maximum: float) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TimelineAdapterError(f"{field} must be numeric or null")
    coordinate = float(value)
    if not math.isfinite(coordinate) or not minimum <= coordinate <= maximum:
        raise TimelineAdapterError(f"{field} is outside its valid finite range")
    return coordinate


def _public_geometry(location: Mapping[str, Any], source_id: str) -> dict[str, Any] | None:
    longitude = _coordinate(
        location.get("longitude_public"),
        field=f"{source_id}.location.longitude_public",
        minimum=-180,
        maximum=180,
    )
    latitude = _coordinate(
        location.get("latitude_public"),
        field=f"{source_id}.location.latitude_public",
        minimum=-90,
        maximum=90,
    )
    privacy_level = location.get("privacy_level")
    if privacy_level in PRIVATE_PRIVACY_LEVELS:
        if longitude is not None or latitude is not None:
            raise TimelineAdapterError(
                f"accepted {source_id} exposes public coordinates at a private privacy level"
            )
        return None
    if (longitude is None) != (latitude is None):
        raise TimelineAdapterError(
            f"accepted {source_id} has a one-sided public coordinate pair"
        )
    if longitude is None or latitude is None:
        return None
    return {"type": "Point", "coordinates": [longitude, latitude]}


def _source_publishers(incident: Mapping[str, Any]) -> list[str]:
    sources = incident.get("sources")
    if not isinstance(sources, list):
        return []
    return sorted(
        {
            publisher.lower()
            for source in sources
            if isinstance(source, Mapping)
            and (publisher := _normalize_space(source.get("agency_or_publisher")))
        }
    )


def _geometry_in_semantic_region(
    geometry: Mapping[str, Any], country_code: str | None
) -> bool:
    bounds = SEMANTIC_REGION_BOUNDS.get(country_code or "")
    if bounds is None:
        return False
    longitude, latitude = geometry["coordinates"]
    minimum_longitude, maximum_longitude, minimum_latitude, maximum_latitude = bounds
    return (
        minimum_longitude <= longitude <= maximum_longitude
        and minimum_latitude <= latitude <= maximum_latitude
    )


def _normalized_public_geometry_with_audit(
    incident: Mapping[str, Any],
    source_hash: str,
    animal_mutilation_event_id: str,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Project public geometry under a frozen, provenance-scoped longitude policy.

    The frozen UFOCAT source encodes west longitude as positive and east longitude
    as negative. Majestic records already use GeoJSON signed longitude. Any other
    provenance or any post-transform region mismatch is retained as an auditable
    report with null geometry rather than being guessed into a map position.
    """

    source_id = _incident_id(incident)
    location = incident.get("location")
    if not isinstance(location, Mapping):
        raise TimelineAdapterError(f"{source_id} has no location object")
    original_geometry = _public_geometry(location, source_id)
    source_publishers = _source_publishers(incident)
    country_code = _normalize_space(location.get("country_code")) or None
    admin1 = _normalize_space(location.get("admin1")) or None
    coordinate_source = _normalize_space(location.get("coordinate_source")) or None
    privacy_level = location.get("privacy_level")
    audit = {
        "schema_version": COORDINATE_AUDIT_SCHEMA_VERSION,
        "source_incident_id": source_id,
        "source_incident_sha256": source_hash,
        "animal_mutilation_event_id": animal_mutilation_event_id,
        "coordinate_source": coordinate_source,
        "source_publishers": source_publishers,
        "country_code": country_code,
        "admin1": admin1,
        "privacy_level": privacy_level,
        "original_geometry": original_geometry,
        "output_geometry": None,
        "action": "no_public_geometry",
        "rule_id": "no_public_geometry_v1",
        "source_longitude_convention": None,
        "transformation": None,
        "semantic_region": None,
        "semantic_validation": "not_applicable_no_public_geometry",
    }
    if original_geometry is None:
        return None, audit

    if tuple(source_publishers) == UFOCAT_SOURCE_PUBLISHERS:
        longitude, latitude = original_geometry["coordinates"]
        candidate_geometry = {
            "type": "Point",
            "coordinates": [-longitude, latitude],
        }
        action = "longitude_sign_corrected"
        rule_id = UFOCAT_LONGITUDE_RULE_ID
        source_convention = "west_positive_east_negative"
        transformation = "longitude_out=-longitude_in"
    elif tuple(source_publishers) == STANDARD_SIGNED_SOURCE_PUBLISHERS:
        candidate_geometry = {
            "type": "Point",
            "coordinates": list(original_geometry["coordinates"]),
        }
        action = "unchanged_standard_signed"
        rule_id = "standard_signed_longitude_v1"
        source_convention = "geojson_signed_longitude"
        transformation = "identity"
    else:
        audit.update(
            {
                "action": "geometry_suppressed_ambiguous_provenance",
                "rule_id": "fail_closed_ambiguous_provenance_v1",
                "semantic_region": country_code,
                "semantic_validation": "failed_closed",
            }
        )
        return None, audit

    audit.update(
        {
            "source_longitude_convention": source_convention,
            "transformation": transformation,
            "semantic_region": country_code,
        }
    )
    if not _geometry_in_semantic_region(candidate_geometry, country_code):
        audit.update(
            {
                "action": "geometry_suppressed_ambiguous_geography",
                "rule_id": "fail_closed_semantic_geography_v1",
                "semantic_validation": "failed_closed",
            }
        )
        return None, audit

    audit.update(
        {
            "output_geometry": candidate_geometry,
            "action": action,
            "rule_id": rule_id,
            "semantic_validation": "passed",
        }
    )
    return candidate_geometry, audit


MIRRORED_PAIR_IGNORED_LOCATION_TOKENS = frozenset(
    {"US", "USA", "CN", "CA", "SA", "EU", "ME", "AU", "ARG", "BRA", "FRA", "ISR"}
)


def _location_tokens(value: Any) -> set[str]:
    return {
        token
        for raw_token in _normalize_space(value).upper().split(",")
        if len(token := raw_token.strip()) >= 3
        and token not in MIRRORED_PAIR_IGNORED_LOCATION_TOKENS
    }


def _opposite_sign_near_duplicate_pair_count(
    features: Sequence[Mapping[str, Any]],
    coordinate_audit: Sequence[Mapping[str, Any]],
    *,
    use_original_geometry: bool,
) -> int:
    audit_by_source = {
        entry["source_incident_id"]: entry for entry in coordinate_audit
    }
    points: list[tuple[float, float, set[str]]] = []
    for feature in features:
        properties = feature["properties"]
        if use_original_geometry:
            geometry = audit_by_source[properties["source_incident_id"]]["original_geometry"]
        else:
            geometry = feature["geometry"]
        if geometry is None:
            continue
        longitude, latitude = geometry["coordinates"]
        points.append(
            (
                longitude,
                latitude,
                _location_tokens(properties.get("location_label")),
            )
        )

    pair_count = 0
    for index, left in enumerate(points):
        for right in points[index + 1 :]:
            if left[0] * right[0] >= 0:
                continue
            if abs(abs(left[0]) - abs(right[0])) > 0.02:
                continue
            if abs(left[1] - right[1]) > 0.1:
                continue
            if left[2] & right[2]:
                pair_count += 1
    return pair_count


def _sorted_unique_strings(values: Iterable[Any]) -> list[str]:
    return sorted({value for value in values if isinstance(value, str) and value})


def _default_summary(normalized_names: Sequence[str]) -> str:
    if not normalized_names or normalized_names == ["unknown_animal"]:
        return "The cited source reports an animal mutilation incident."
    display = ", ".join(name.replace("_", " ") for name in normalized_names)
    return f"The cited source reports an animal mutilation incident involving {display}."


def _stable_reported_event_id(source_id: str) -> str:
    """Derive the stable public identity from the extraction-lineage identity."""

    if not CMI_RE.fullmatch(source_id):
        raise TimelineAdapterError(f"invalid source incident identity: {source_id}")
    digest = sha256_bytes(
        b"animal-mutilation-reported-unreviewed-v1\0" + source_id.encode("ascii")
    )
    return f"ami_{digest[:24]}"


def _public_location_label(location: Mapping[str, Any]) -> str | None:
    """Build a display label only from structured, already-generalized fields."""

    if location.get("privacy_level") in PRIVATE_PRIVACY_LEVELS:
        return None
    parts: list[str] = []
    seen: set[str] = set()
    for key in ("locality", "admin2", "admin1", "country_code"):
        try:
            value = _clean_text(location.get(key), field=f"location.{key}", max_length=150)
        except TimelineAdapterError:
            continue
        if value is None or _display_leak_reason(value):
            continue
        normalized = value.casefold()
        if normalized not in seen:
            parts.append(value)
            seen.add(normalized)
    while parts:
        label = ", ".join(parts)
        if len(label) <= 300 and _display_leak_reason(label) is None:
            return label
        parts.pop()
    return None


def _safe_unreviewed_evidence(victims: Sequence[Mapping[str, Any]]) -> list[str]:
    """Retain only bounded extracts that pass the public display scan."""

    evidence: set[str] = set()
    for victim in victims:
        try:
            value = _clean_text(
                victim.get("evidence_excerpt"),
                field="evidence excerpt",
                max_length=500,
            )
        except TimelineAdapterError:
            continue
        if (
            value is not None
            and _text_corruption_reason(value) is None
            and _display_leak_reason(value) is None
        ):
            evidence.add(value)
    return sorted(evidence)[:8]


def _uncertainty(
    dates: Mapping[str, Any],
    location: Mapping[str, Any],
    geometry: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return {
        "date_precision": dates.get("precision"),
        "location_precision": location.get("precision"),
        "privacy_generalized": location.get("privacy_level") != "public_exact",
        "coordinates_available": geometry is not None,
    }


def _source_refs(
    incident: Mapping[str, Any],
    victims: Sequence[Mapping[str, Any]],
    source_id: str,
) -> list[dict[str, Any]]:
    supported_source_ids = {
        item
        for victim in victims
        for item in victim.get("source_ids", [])
        if isinstance(item, str)
    }
    sources = incident.get("sources")
    if not isinstance(sources, list):
        raise TimelineAdapterError(f"accepted {source_id} has no source array")
    source_index: dict[str, Mapping[str, Any]] = {}
    for source in sources:
        if not isinstance(source, Mapping) or not isinstance(source.get("source_id"), str):
            continue
        candidate_id = source["source_id"]
        if candidate_id in source_index:
            raise TimelineAdapterError(f"accepted {source_id} has duplicate source_id {candidate_id}")
        source_index[candidate_id] = source
    missing = sorted(supported_source_ids - set(source_index))
    if missing:
        raise TimelineAdapterError(
            f"accepted {source_id} has unresolved victim source IDs: {', '.join(missing)}"
        )
    refs: list[dict[str, Any]] = []
    for supported_id in sorted(supported_source_ids):
        source = source_index[supported_id]
        source_hash = source.get("source_hash")
        if not isinstance(source_hash, str) or not SHA256_RE.fullmatch(source_hash.lower()):
            raise TimelineAdapterError(
                f"accepted {source_id} source {supported_id} lacks a valid source_hash"
            )
        locator_value = source.get("page_or_container") or source.get("archival_citation")
        locator = _clean_text(locator_value, field="source locator", max_length=300)
        if locator is None or _display_leak_reason(locator):
            locator = supported_id
        ref: dict[str, Any] = {
            "source_id": supported_id,
            "locator": locator,
            "source_hash": source_hash.lower(),
        }
        url = source.get("url")
        if url is not None:
            public_url = _valid_public_url(url, field=f"{source_id}.{supported_id}.url")
            if _decoded_url_privacy_reason(public_url) is None:
                ref["url"] = public_url
        refs.append(ref)
    if not refs:
        raise TimelineAdapterError(f"accepted {source_id} has no resolved supporting sources")
    return refs


def _approved_field(decision: Mapping[str, Any], key: str, default: Any) -> Any:
    approved = decision.get("approved_public_fields")
    if isinstance(approved, Mapping) and key in approved:
        return approved[key]
    return default


def _feature_for_accepted(
    incident: Mapping[str, Any],
    source_hash: str,
    decision: Mapping[str, Any],
    *,
    geometry: Mapping[str, Any] | None,
) -> dict[str, Any]:
    source_id = _incident_id(incident)
    victims = _require_eligible_incident(incident, source_id)
    normalized_names = _sorted_unique_strings(
        victim.get("normalized_common_name") for victim in victims
    )
    taxon_keys = _sorted_unique_strings(victim.get("reported_taxon_key") for victim in victims)
    species_groups = _sorted_unique_strings(victim.get("species_group") for victim in victims)

    evidence_default = _sorted_unique_strings(
        _clean_text(victim.get("evidence_excerpt"), field="evidence excerpt", max_length=500)
        for victim in victims
    )[:8]
    evidence_value = _approved_field(decision, "evidence_excerpts", evidence_default)
    if not isinstance(evidence_value, list):
        raise TimelineAdapterError(f"accepted {source_id} evidence_excerpts must be an array")
    evidence = []
    for index, value in enumerate(evidence_value):
        cleaned = _clean_text(value, field=f"evidence_excerpts[{index}]", max_length=500)
        if cleaned is not None:
            evidence.append(cleaned)
    evidence = sorted(set(evidence))
    if not evidence:
        raise TimelineAdapterError(
            f"accepted {source_id} has no bounded public evidence excerpt; reviewer override required"
        )
    if len(evidence) > 8:
        raise TimelineAdapterError(f"accepted {source_id} has more than 8 evidence excerpts")

    location = incident.get("location")
    if not isinstance(location, Mapping):
        raise TimelineAdapterError(f"accepted {source_id} has no location object")
    privacy_level = location.get("privacy_level")
    default_location_label = _public_location_label(location)
    location_label_value = _approved_field(
        decision, "location_label", default_location_label
    )
    location_label = _clean_text(
        location_label_value,
        field="location_label",
        max_length=300,
    )
    if privacy_level in PRIVATE_PRIVACY_LEVELS and location_label is not None:
        raise TimelineAdapterError(
            f"accepted {source_id} cannot publish a location label at privacy level {privacy_level}"
        )

    summary_value = _approved_field(decision, "summary", _default_summary(normalized_names))
    summary = _clean_text(summary_value, field="summary", max_length=1000)
    warning_value = _approved_field(
        decision,
        "content_warning",
        "Animal-death and anatomical descriptions may be disturbing.",
    )
    content_warning = _clean_text(
        warning_value,
        field="content_warning",
        max_length=300,
    )

    dates = incident.get("dates")
    if not isinstance(dates, Mapping):
        raise TimelineAdapterError(f"accepted {source_id} has no dates object")
    reviewed_at = decision["reviewed_at"]
    reviewed_on = reviewed_at[:10]
    ami_id = decision["animal_mutilation_event_id"]
    properties = {
        "animal_mutilation_event_id": ami_id,
        "source_incident_id": source_id,
        "source_incident_sha256": source_hash,
        "review_decision_id": decision["review_decision_id"],
        "reviewed_on": reviewed_on,
        "event_domain": "animal_mutilation",
        "record_type": "mutilation_case",
        "claim_label": "Reported animal mutilation",
        "status": incident["status"],
        "evidence_status": "reviewed",
        "source_status": incident["status"],
        "title": "Reported animal mutilation",
        "summary": summary,
        "date_start": dates.get("event_start"),
        "date_end": dates.get("event_end"),
        "date_precision": dates["precision"],
        "location_label": location_label,
        "location_precision": location["precision"],
        "privacy_level": privacy_level,
        "uncertainty": _uncertainty(dates, location, geometry),
        "normalized_common_names": normalized_names,
        "reported_taxon_keys": taxon_keys,
        "species_groups": species_groups,
        "evidence_excerpts": evidence,
        "source_refs": _source_refs(incident, victims, source_id),
        "content_warning": content_warning,
        "trace_eligible": False,
        "trace_role": "context_only",
        "causality": "not_asserted",
    }
    feature = {
        "type": "Feature",
        "id": f"animal_mutilation:{ami_id}",
        "geometry": geometry,
        "properties": properties,
    }
    _scan_emitted_strings(feature, artifact=OVERLAY_NAME)
    return feature


def _feature_for_reported_unreviewed(
    incident: Mapping[str, Any],
    source_hash: str,
    *,
    geometry: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Project an eligible canonical report without asserting analyst review."""

    source_id = _incident_id(incident)
    victims = _require_eligible_incident(incident, source_id)
    location = incident.get("location")
    if not isinstance(location, Mapping):
        raise TimelineAdapterError(f"{source_id} has no location object")
    dates = incident.get("dates")
    if not isinstance(dates, Mapping):
        raise TimelineAdapterError(f"{source_id} has no dates object")

    normalized_names = _sorted_unique_strings(
        victim.get("normalized_common_name") for victim in victims
    )
    taxon_keys = _sorted_unique_strings(
        victim.get("reported_taxon_key") for victim in victims
    )
    species_groups = _sorted_unique_strings(
        victim.get("species_group") for victim in victims
    )
    ami_id = _stable_reported_event_id(source_id)
    source_status = incident.get("status")
    properties = {
        "animal_mutilation_event_id": ami_id,
        "source_incident_id": source_id,
        "source_incident_sha256": source_hash,
        "event_domain": "animal_mutilation",
        "record_type": "mutilation_case",
        "claim_label": "Reported animal mutilation",
        "status": "reported_unreviewed",
        "evidence_status": "reported_unreviewed",
        "source_status": source_status,
        "title": "Reported animal mutilation",
        "summary": _default_summary(normalized_names),
        "date_start": dates.get("event_start"),
        "date_end": dates.get("event_end"),
        "date_precision": dates.get("precision"),
        "location_label": _public_location_label(location),
        "location_precision": location.get("precision"),
        "privacy_level": location.get("privacy_level"),
        "uncertainty": _uncertainty(dates, location, geometry),
        "normalized_common_names": normalized_names,
        "reported_taxon_keys": taxon_keys,
        "species_groups": species_groups,
        "evidence_excerpts": _safe_unreviewed_evidence(victims),
        "source_refs": _source_refs(incident, victims, source_id),
        "content_warning": "Animal-death and anatomical descriptions may be disturbing.",
        "trace_eligible": False,
        "trace_role": "context_only",
        "causality": "not_asserted",
    }
    feature = {
        "type": "Feature",
        "id": f"animal_mutilation:{ami_id}",
        "geometry": geometry,
        "properties": properties,
    }
    _scan_emitted_strings(feature, artifact=OVERLAY_NAME)
    return feature


def _queue_entry(
    incident: Mapping[str, Any],
    source_hash: str,
    decision: Mapping[str, Any] | None,
    *,
    published_unreviewed: bool = False,
) -> dict[str, Any]:
    source_id = _incident_id(incident)
    victims = _victim_rows(incident)
    dates = incident.get("dates") if isinstance(incident.get("dates"), Mapping) else {}
    location = (
        incident.get("location") if isinstance(incident.get("location"), Mapping) else {}
    )
    provenance = (
        incident.get("provenance")
        if isinstance(incident.get("provenance"), Mapping)
        else {}
    )
    if published_unreviewed:
        queue_state = "reported_unreviewed"
    elif decision is None:
        queue_state = "missing_review_decision"
    else:
        queue_state = "review_unresolved"
    entry = {
        "schema_version": QUEUE_SCHEMA_VERSION,
        "animal_mutilation_event_id": _stable_reported_event_id(source_id)
        if published_unreviewed
        else None,
        "source_incident_id": source_id,
        "source_incident_sha256": source_hash,
        "queue_state": queue_state,
        "evidence_status": queue_state,
        "review_decision_id": None if decision is None else decision["review_decision_id"],
        "record_type": incident.get("record_type"),
        "status": incident.get("status"),
        "negative_only": incident.get("negative_only"),
        "provenance_review_state": provenance.get("review_state"),
        "victim_assertion_count": len(victims),
        "normalized_common_names": _sorted_unique_strings(
            victim.get("normalized_common_name") for victim in victims
        ),
        "reported_taxon_keys": _sorted_unique_strings(
            victim.get("reported_taxon_key") for victim in victims
        ),
        "species_groups": _sorted_unique_strings(
            victim.get("species_group") for victim in victims
        ),
        "date_start": dates.get("event_start"),
        "date_end": dates.get("event_end"),
        "date_precision": dates.get("precision"),
        "location_precision": location.get("precision"),
        "privacy_level": location.get("privacy_level"),
        "source_count": len(incident.get("sources", []))
        if isinstance(incident.get("sources"), list)
        else 0,
        "requested_action": (
            "Optional analyst review may record accepted, rejected, or unresolved disposition; "
            "publication as reported_unreviewed is not blocked."
            if published_unreviewed
            else "Resolve the ambiguous review disposition when evidence permits."
            if decision is not None
            else "Record an analyst disposition before using the review-ledger release mode."
        ),
    }
    _scan_emitted_strings(entry, artifact=QUEUE_NAME)
    return entry


def _relationship_counts(seed_manifest: Mapping[str, Any]) -> dict[str, Any]:
    counts = seed_manifest.get("counts")
    counts = counts if isinstance(counts, Mapping) else {}

    def nonnegative_count(name: str) -> int:
        value = counts.get(name, 0)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise TimelineAdapterError(f"seed run_manifest count {name} is invalid")
        return value

    explicit = nonnegative_count("explicit_source_relationships")
    computed = nonnegative_count("computed_relationships")
    total = nonnegative_count("cross_domain_relationships")
    if total != explicit + computed:
        raise TimelineAdapterError(
            "seed relationship counts do not reconcile explicit plus computed relationships"
        )
    return {
        "scope": "seed_run_global",
        "explicit_source_pending": explicit,
        "computed_pending": computed,
        "total_pending": total,
        "emitted": 0,
        "policy": "No relationship is emitted without an independently reviewed stable-link decision.",
    }


def _jsonl_bytes(rows: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(canonical_json_line(row) for row in rows)


def _atomic_write(path: Path, data: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _safe_resolved_paths(
    seed_output_dir: Path,
    review_decisions: Path | None,
    output_dir: Path,
) -> tuple[Path, Path | None, Path]:
    seed = seed_output_dir.resolve()
    output = output_dir.resolve()
    decisions = review_decisions.resolve() if review_decisions is not None else None
    if output == seed or seed in output.parents:
        raise TimelineAdapterError(
            "output-dir must be separate from, and not nested inside, seed-output-dir"
        )
    if decisions is not None and decisions.parent == output and decisions.name in OUTPUT_NAMES:
        raise TimelineAdapterError("review decision input would be overwritten by adapter output")
    return seed, decisions, output


def build_timeline_layer(
    *,
    seed_output_dir: Path,
    review_decisions: Path | None,
    output_dir: Path,
) -> dict[str, Any]:
    """Validate inputs and write the four deterministic bridge artifacts."""

    seed_dir, decision_path, target_dir = _safe_resolved_paths(
        Path(seed_output_dir),
        Path(review_decisions) if review_decisions is not None else None,
        Path(output_dir),
    )
    seed_manifest, seed_manifest_hash = _load_and_verify_seed_manifest(seed_dir)
    canonical_path, canonical_file_hash = _verify_canonical_artifact(seed_dir, seed_manifest)

    case_validator = _jsonschema_validator(
        _load_schema(CASE_SCHEMA_PATH), label="animal mutilation case"
    )
    decision_schema = _load_schema(DECISION_SCHEMA_PATH)
    decision_validator = _jsonschema_validator(
        decision_schema, label="Timeline review decision"
    )
    overlay_schema = _load_schema(OVERLAY_SCHEMA_PATH)
    overlay_validator = _jsonschema_validator(overlay_schema, label="Timeline overlay")
    queue_schema = _load_schema(QUEUE_SCHEMA_PATH)
    queue_validator = _jsonschema_validator(queue_schema, label="Timeline review queue")
    coordinate_audit_schema = _load_schema(COORDINATE_AUDIT_SCHEMA_PATH)
    coordinate_audit_validator = _jsonschema_validator(
        coordinate_audit_schema,
        label="Timeline coordinate normalization audit",
    )

    incidents = _read_jsonl(
        canonical_path,
        label="canonical incident",
        validator=case_validator,
    )
    incident_index, incident_hashes = _index_incidents(incidents)
    _validate_manifest_coverage(seed_manifest, incident_index)

    decisions, ledger_bytes = _load_decisions(decision_path, validator=decision_validator)
    decisions_by_source = _index_and_verify_decisions(
        decisions,
        incident_index,
        incident_hashes,
    )

    features: list[dict[str, Any]] = []
    queue: list[dict[str, Any]] = []
    coordinate_audit: list[dict[str, Any]] = []
    accepted_count = rejected_count = unresolved_count = missing_count = 0
    reported_unreviewed_count = 0
    release_mode = "reported_unreviewed" if decision_path is None else "review_ledger"
    for source_id in sorted(incident_index):
        incident = incident_index[source_id]
        decision = decisions_by_source.get(source_id)
        if release_mode == "reported_unreviewed":
            missing_count += 1
            reported_unreviewed_count += 1
            ami_id = _stable_reported_event_id(source_id)
            geometry, audit_row = _normalized_public_geometry_with_audit(
                incident,
                incident_hashes[source_id],
                ami_id,
            )
            features.append(
                _feature_for_reported_unreviewed(
                    incident,
                    incident_hashes[source_id],
                    geometry=geometry,
                )
            )
            coordinate_audit.append(audit_row)
            queue.append(
                _queue_entry(
                    incident,
                    incident_hashes[source_id],
                    None,
                    published_unreviewed=True,
                )
            )
            continue
        if decision is None:
            missing_count += 1
            queue.append(_queue_entry(incident, incident_hashes[source_id], None))
            continue
        disposition = decision["disposition"]
        if disposition == "accepted":
            accepted_count += 1
            geometry, audit_row = _normalized_public_geometry_with_audit(
                incident,
                incident_hashes[source_id],
                decision["animal_mutilation_event_id"],
            )
            features.append(
                _feature_for_accepted(
                    incident,
                    incident_hashes[source_id],
                    decision,
                    geometry=geometry,
                )
            )
            coordinate_audit.append(audit_row)
        elif disposition == "rejected":
            rejected_count += 1
        else:
            unresolved_count += 1
            queue.append(_queue_entry(incident, incident_hashes[source_id], decision))

    features.sort(key=lambda feature: feature["properties"]["animal_mutilation_event_id"])
    queue.sort(key=lambda entry: entry["source_incident_id"])
    coordinate_audit.sort(key=lambda entry: entry["source_incident_id"])
    for index, entry in enumerate(queue):
        _validate_instance(
            queue_validator,
            entry,
            label=f"generated Timeline review queue row {index}",
        )
    for index, entry in enumerate(coordinate_audit):
        _validate_instance(
            coordinate_audit_validator,
            entry,
            label=f"generated coordinate normalization audit row {index}",
        )
    overlay = {
        "type": "FeatureCollection",
        "name": LAYER_NAME,
        "schema_version": OVERLAY_SCHEMA_VERSION,
        "event_domain": "animal_mutilation",
        "release_mode": release_mode,
        "trace_eligible": False,
        "trace_role": "context_only",
        "causality": "not_asserted",
        "features": features,
    }
    _validate_instance(overlay_validator, overlay, label="generated Timeline overlay")
    _scan_emitted_strings(overlay, artifact=OVERLAY_NAME)

    queue_bytes = _jsonl_bytes(queue)
    coordinate_audit_bytes = _jsonl_bytes(coordinate_audit)
    overlay_bytes = canonical_json_line(overlay)
    geometry_count = sum(feature["geometry"] is not None for feature in features)
    audit_actions = Counter(entry["action"] for entry in coordinate_audit)
    coordinate_correction_count = audit_actions["longitude_sign_corrected"]
    coordinate_unchanged_count = audit_actions["unchanged_standard_signed"]
    coordinate_suppression_count = (
        audit_actions["geometry_suppressed_ambiguous_provenance"]
        + audit_actions["geometry_suppressed_ambiguous_geography"]
    )
    semantic_validated_geometry_count = (
        coordinate_correction_count + coordinate_unchanged_count
    )
    semantic_validation_passed = (
        coordinate_suppression_count == 0
        and semantic_validated_geometry_count == geometry_count
    )
    exact_day_count = sum(
        feature["properties"]["date_precision"] == "exact_day" for feature in features
    )
    mapped_exact_day_count = sum(
        feature["geometry"] is not None
        and feature["properties"]["date_precision"] == "exact_day"
        for feature in features
    )
    undated_count = sum(
        feature["properties"]["date_start"] is None
        and feature["properties"]["date_end"] is None
        for feature in features
    )
    original_opposite_sign_pair_count = _opposite_sign_near_duplicate_pair_count(
        features,
        coordinate_audit,
        use_original_geometry=True,
    )
    output_opposite_sign_pair_count = _opposite_sign_near_duplicate_pair_count(
        features,
        coordinate_audit,
        use_original_geometry=False,
    )
    total_count = len(incidents)
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "adapter_version": ADAPTER_VERSION,
        "layer_name": LAYER_NAME,
        "event_domain": "animal_mutilation",
        "release_mode": release_mode,
        "source_commit": seed_manifest.get("base_commit"),
        "seed_pipeline_version": seed_manifest.get("pipeline_version"),
        "source_trust": {
            "required_run_mode": EXPECTED_RUN_MODE,
            "validation_provenance_schema": seed_manifest["validation_provenance"][
                "schema_version"
            ],
            "canonical_hash_claim_verified": True,
            "canonical_row_count_reconciled": True,
            "coordinate_normalization_input_immutable": True,
        },
        "coordinate_normalization": {
            "policy_version": "animal-mutilation-timeline-coordinate-normalization-v1.0.0",
            "locked_seed_pipeline_version": EXPECTED_SEED_PIPELINE_VERSION,
            "source_scope": "sources[].agency_or_publisher=ufocat",
            "source_longitude_convention": "west_positive_east_negative",
            "transformation": "longitude_out=-longitude_in",
            "semantic_geography_policy": (
                "validate against the declared source region after normalization; "
                "retain the report with null geometry when provenance or geography is ambiguous"
            ),
            "semantic_geography_validation": {
                "status": "passed" if semantic_validation_passed else "failed_closed",
                "validated_output_geometries": semantic_validated_geometry_count,
                "failed_closed_geometries": coordinate_suppression_count,
                "unvalidated_output_geometries": 0,
            },
            "correction_count": coordinate_correction_count,
            "semantic_validation_passed": semantic_validation_passed,
            "audit_artifact": COORDINATE_AUDIT_NAME,
            "audit": {
                "path": COORDINATE_AUDIT_NAME,
                "schema_version": COORDINATE_AUDIT_SCHEMA_VERSION,
                "schema_sha256": sha256_file(COORDINATE_AUDIT_SCHEMA_PATH),
                "sha256": sha256_bytes(coordinate_audit_bytes),
                "size_bytes": len(coordinate_audit_bytes),
                "record_count": len(coordinate_audit),
            },
        },
        "inputs": {
            "seed_run_manifest": {
                "sha256": seed_manifest_hash,
                "size_bytes": (seed_dir / SEED_MANIFEST_NAME).stat().st_size,
            },
            "canonical_incidents": {
                "sha256": canonical_file_hash,
                "size_bytes": canonical_path.stat().st_size,
            },
            "review_decision_ledger": {
                "provided": decision_path is not None,
                "sha256": sha256_bytes(ledger_bytes),
                "size_bytes": len(ledger_bytes),
            },
        },
        "schema_versions": {
            "review_decision": DECISION_SCHEMA_VERSION,
            "overlay": OVERLAY_SCHEMA_VERSION,
            "review_queue": QUEUE_SCHEMA_VERSION,
            "coordinate_normalization_audit": COORDINATE_AUDIT_SCHEMA_VERSION,
        },
        "schema_sha256": {
            "review_decision": sha256_file(DECISION_SCHEMA_PATH),
            "overlay": sha256_file(OVERLAY_SCHEMA_PATH),
            "review_queue": sha256_file(QUEUE_SCHEMA_PATH),
            "coordinate_normalization_audit": sha256_file(
                COORDINATE_AUDIT_SCHEMA_PATH
            ),
            "source_case": sha256_file(CASE_SCHEMA_PATH),
        },
        "counts": {
            "total_source_incidents": total_count,
            "decision_ledger_rows": len(decisions),
            "accepted": accepted_count,
            "reported_unreviewed": reported_unreviewed_count,
            "rejected": rejected_count,
            "unresolved": unresolved_count,
            "missing_decision": missing_count,
            "mapped_incidents": geometry_count,
            "unmapped_incidents": len(features) - geometry_count,
            "queued_for_review": len(queue),
            "features_with_geometry": geometry_count,
            "features_without_geometry": len(features) - geometry_count,
            "exact_day_features": exact_day_count,
            "mapped_exact_day_features": mapped_exact_day_count,
            "undated_features": undated_count,
            "coordinate_audit_records": len(coordinate_audit),
            "longitude_sign_corrected": coordinate_correction_count,
            "coordinates_unchanged": coordinate_unchanged_count,
            "coordinates_suppressed_ambiguous": coordinate_suppression_count,
            "no_public_geometry": audit_actions["no_public_geometry"],
            "semantic_geography_passed": semantic_validated_geometry_count,
            "semantic_geography_failed_closed": coordinate_suppression_count,
            "original_opposite_sign_near_duplicate_pairs": (
                original_opposite_sign_pair_count
            ),
            "output_opposite_sign_near_duplicate_pairs": output_opposite_sign_pair_count,
            "generated_artifacts": 4,
        },
        "pending_relationships": _relationship_counts(seed_manifest),
        "outputs": {
            QUEUE_NAME: {
                "sha256": sha256_bytes(queue_bytes),
                "size_bytes": len(queue_bytes),
                "records": len(queue),
            },
            OVERLAY_NAME: {
                "sha256": sha256_bytes(overlay_bytes),
                "size_bytes": len(overlay_bytes),
                "features": len(features),
            },
            COORDINATE_AUDIT_NAME: {
                "sha256": sha256_bytes(coordinate_audit_bytes),
                "size_bytes": len(coordinate_audit_bytes),
                "records": len(coordinate_audit),
                "longitude_sign_corrected": coordinate_correction_count,
                "coordinates_suppressed_ambiguous": coordinate_suppression_count,
            },
        },
        "manifest_self_hash_policy": "not_embedded_to_avoid_recursion",
        "relationship_export_policy": "no_cross_domain_relationships_emitted_in_this_context_layer",
        "trace_policy": {
            "trace_eligible": False,
            "trace_role": "context_only",
            "causality": "not_asserted",
        },
        "mutation_guards": {
            "canonical_ufo_outputs_mutated": False,
            "frontend_outputs_mutated": False,
            "seed_outputs_mutated": False,
            "canonical_coordinates_mutated": False,
            "normalization_applied_only_to_timeline_projection": True,
        },
        "timestamp_policy": "no_wall_clock_timestamp_in_deterministic_outputs",
    }
    _scan_emitted_strings(queue, artifact=QUEUE_NAME)
    _scan_emitted_strings(coordinate_audit, artifact=COORDINATE_AUDIT_NAME)
    _scan_emitted_strings(manifest, artifact=IMPORT_MANIFEST_NAME)
    manifest_bytes = canonical_json_line(manifest)

    target_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write(target_dir / QUEUE_NAME, queue_bytes)
    _atomic_write(target_dir / OVERLAY_NAME, overlay_bytes)
    _atomic_write(target_dir / COORDINATE_AUDIT_NAME, coordinate_audit_bytes)
    _atomic_write(target_dir / IMPORT_MANIFEST_NAME, manifest_bytes)
    return manifest


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build the public-safe Animal Mutilation Reports layer for UFO Timeline integration."
        )
    )
    parser.add_argument(
        "--seed-output-dir",
        type=Path,
        required=True,
        help="Validated seed extraction output containing run_manifest.json and canonical_incidents.jsonl.",
    )
    parser.add_argument(
        "--review-decisions",
        type=Path,
        default=None,
        help=(
            "Optional JSONL ledger conforming to timeline_review_decision.schema.json. "
            "When omitted, all eligible incidents are emitted as reported_unreviewed."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Separate target directory for the three bridge artifacts.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        manifest = build_timeline_layer(
            seed_output_dir=args.seed_output_dir,
            review_decisions=args.review_decisions,
            output_dir=args.output_dir,
        )
    except TimelineAdapterError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    counts = manifest["counts"]
    print(
        "Built animal-mutilation Timeline bridge: "
        f"mapped={counts['mapped_incidents']} "
        f"reported_unreviewed={counts['reported_unreviewed']} "
        f"queued={counts['queued_for_review']} "
        f"rejected={counts['rejected']} "
        f"longitude_sign_corrected={counts['longitude_sign_corrected']} "
        f"coordinate_ambiguities_suppressed={counts['coordinates_suppressed_ambiguous']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
