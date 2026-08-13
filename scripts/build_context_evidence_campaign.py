from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from jsonschema import Draft202012Validator, FormatChecker

try:
    from scripts.context_evidence_contract import REPEATABLE_CONTEXT_FIELDS
except ImportError:  # Direct script execution resolves sibling modules here.
    from context_evidence_contract import REPEATABLE_CONTEXT_FIELDS


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CAMPAIGN_ROOT = REPO_ROOT / "campaign" / "context_evidence"
CAMPAIGN_ID = "context-evidence-expansion-20260810"

CONTRACTS = {
    "source": "source_ledger.schema.json",
    "assertion": "case_enrichment.schema.json",
    "decision": "case_review_decision.schema.json",
    "queue": "research_queue.schema.json",
    "baseline": "baseline_seal.schema.json",
    "state": "campaign_state.schema.json",
    "no_gain": "no_gain_policy.schema.json",
    "known_sources": "known_source_reconciliation.schema.json",
    "receipt": "foundation_receipt.schema.json",
    "release_seal": "release_seal.schema.json",
}

LEDGERS = {
    "source": "source_ledger.jsonl",
    "assertion": "case_enrichment.jsonl",
    "decision": "case_review_decisions.jsonl",
    "queue": "research_queue.jsonl",
}

CLASS_WEIGHTS = {
    "crop_exact_coordinate": 50,
    "crop_candidate_field": 40,
    "animal_exact_day_internal_coordinate": 40,
    "accepted_new_source": 30,
    "descriptive_backlog": 10,
    "source_candidate": 0,
}

BANNED_SELECTION_KEYS = {
    "ufoneighborcount",
    "associationstrength",
    "associationscore",
    "proximitypriority",
    "ufoproximity",
    "nearbyufos",
}
BANNED_PII_KEYS = {
    "ownername",
    "personaladdress",
    "exactaddress",
    "streetaddress",
    "phonenumber",
    "emailaddress",
    "contactdetails",
    "accessinstructions",
}

CROP_ONLY_FIELDS = {"formation_date", "photography_date", "crop_type"}
ANIMAL_ONLY_FIELDS = {"death_interval", "injuries", "investigation_date", "animal_species", "victim_count"}

SEMANTIC_CHECKS = [
    "schemas_draft_2020_12_valid",
    "baseline_artifact_hashes_match",
    "ledger_ids_unique_and_references_resolve",
    "field_assertions_have_source_locators_and_frozen_hashes",
    "review_decisions_match_assertion_evidence",
    "reviewer_quorum_and_conflicts_fail_closed",
    "queue_priority_is_deterministic_and_proximity_blind",
    "attempt_fingerprints_are_unique_and_budget_bounded",
    "two_subwave_no_gain_stop_rule_enforced",
    "privacy_forbidden_keys_absent",
    "frozen_known_source_fingerprint_index_verified",
    "non_milestone_release_seal_fail_closed",
]


class CampaignValidationError(ValueError):
    pass


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_index_bytes(repo_root: Path, relative: str) -> bytes:
    process = subprocess.run(
        ["git", "cat-file", "blob", f":{relative}"],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if process.returncode != 0:
        detail = process.stderr.decode("utf-8", errors="replace").strip()
        raise CampaignValidationError(f"Tracked receipt input is unavailable: {relative}: {detail}")
    return process.stdout


def git_commit_blob_bytes(repo_root: Path, commit: str, relative: str) -> bytes:
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise CampaignValidationError("Released source commit must be a full lowercase Git object ID")
    relative_path = PurePosixPath(relative)
    if (
        not relative_path.parts
        or relative_path.is_absolute()
        or relative != relative_path.as_posix()
        or any(part in {"", ".", ".."} for part in relative_path.parts)
        or ":" in relative
    ):
        raise CampaignValidationError(f"Unsafe released Git blob path: {relative!r}")
    try:
        process = subprocess.run(
            ["git", "cat-file", "blob", f"{commit}:{relative}"],
            cwd=repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise CampaignValidationError(
            f"Unable to read released Git blob at {commit}:{relative}"
        ) from exc
    if process.returncode != 0:
        detail = process.stderr.decode("utf-8", errors="replace").strip()
        raise CampaignValidationError(
            f"Released Git blob is unavailable at {commit}:{relative}: {detail}"
        )
    return process.stdout


def git_index_paths(repo_root: Path, prefix: str) -> list[str]:
    process = subprocess.run(
        ["git", "ls-files", "--cached", "--", prefix],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if process.returncode != 0:
        detail = process.stderr.decode("utf-8", errors="replace").strip()
        raise CampaignValidationError(f"Cannot enumerate tracked receipt inputs: {detail}")
    return sorted(line for line in process.stdout.decode("utf-8").splitlines() if line)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CampaignValidationError(f"Cannot load JSON {path}: {exc}") from exc


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise CampaignValidationError(f"Cannot load JSONL {path}: {exc}") from exc
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            raise CampaignValidationError(f"Blank JSONL line is not allowed: {path}:{line_number}")
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CampaignValidationError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
        if not isinstance(value, dict):
            raise CampaignValidationError(f"JSONL row must be an object: {path}:{line_number}")
        rows.append(value)
    return rows


def load_jsonl_bytes(payload: bytes, label: str) -> list[dict[str, Any]]:
    try:
        lines = payload.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise CampaignValidationError(f"Cannot decode JSONL {label}: {exc}") from exc
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            raise CampaignValidationError(f"Blank JSONL line is not allowed: {label}:{line_number}")
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CampaignValidationError(f"Invalid JSONL at {label}:{line_number}: {exc}") from exc
        if not isinstance(value, dict):
            raise CampaignValidationError(f"JSONL row must be an object: {label}:{line_number}")
        rows.append(value)
    return rows


def _validator(schema: Mapping[str, Any], label: str) -> Draft202012Validator:
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:  # jsonschema exposes several schema-error subclasses.
        raise CampaignValidationError(f"Invalid {label} schema: {exc}") from exc
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _validate_rows(rows: Iterable[dict[str, Any]], validator: Draft202012Validator, label: str) -> None:
    for row_number, row in enumerate(rows, start=1):
        errors = sorted(validator.iter_errors(row), key=lambda item: tuple(str(part) for part in item.path))
        if errors:
            path = ".".join(str(part) for part in errors[0].path) or "<root>"
            raise CampaignValidationError(f"{label} row {row_number} fails schema at {path}: {errors[0].message}")


def _validate_document(value: Mapping[str, Any], validator: Draft202012Validator, label: str) -> None:
    errors = sorted(validator.iter_errors(value), key=lambda item: tuple(str(part) for part in item.path))
    if errors:
        path = ".".join(str(part) for part in errors[0].path) or "<root>"
        raise CampaignValidationError(f"{label} fails schema at {path}: {errors[0].message}")


def _unique_map(rows: Iterable[dict[str, Any]], key: str, label: str) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = str(row[key])
        if value in output:
            raise CampaignValidationError(f"Duplicate {label} {value}")
        output[value] = row
    return output


def _normalized_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def _walk_keys(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child)


def reject_forbidden_keys(value: Any, label: str) -> None:
    for key in _walk_keys(value):
        normalized = _normalized_key(key)
        if normalized in BANNED_SELECTION_KEYS:
            raise CampaignValidationError(f"{label} contains proximity-based selection key {key!r}")
        if normalized in BANNED_PII_KEYS:
            raise CampaignValidationError(f"{label} contains forbidden personal-data key {key!r}")


def normalize_attempt_target(kind: str, target: str) -> str:
    compact = " ".join(target.strip().split())
    if kind in {"source_open", "archive_fallback"} and compact.lower().startswith(("http://", "https://")):
        parsed = urlsplit(compact)
        query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
        path = parsed.path or "/"
        if path != "/":
            path = path.rstrip("/")
        return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, query, ""))
    return compact.casefold()


def attempt_fingerprint(kind: str, target: str, version_sha256: str | None = None) -> str:
    normalized = normalize_attempt_target(kind, target)
    payload = f"{kind}\0{normalized}\0{version_sha256 or ''}".encode("utf-8")
    return sha256_bytes(payload)


def queue_priority_score(row: Mapping[str, Any]) -> int:
    inputs = row["priorityInputs"]
    missing = int(inputs["missingStrictGateCount"])
    return (
        (10 - missing) * 100
        + CLASS_WEIGHTS[str(row["caseClass"])]
        + min(int(inputs["independentSourceFamilyCount"]), 5) * 5
        + (10 if inputs["exactOccurrenceDay"] else 0)
        + (10 if inputs["sourceSupportedCoordinate"] else 0)
    )


def _case_domain_matches(case_id: str, domain: str) -> bool:
    return (domain == "crop_circle" and case_id.startswith("cc_")) or (
        domain == "animal_mutilation" and case_id.startswith("ami_")
    )


def validate_sources(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    sources = _unique_map(rows, "sourceId", "sourceId")
    for row in rows:
        source_id = row["sourceId"]
        derived = row["derivation"]["derivedFromSourceIds"]
        relation = row["derivation"]["relation"]
        if relation == "original" and derived:
            raise CampaignValidationError(f"Original source {source_id} cannot derive from another source")
        if relation != "original" and not derived:
            raise CampaignValidationError(f"Derived source {source_id} must name its upstream source")
        for upstream_id in derived:
            if upstream_id not in sources:
                raise CampaignValidationError(f"Source {source_id} references missing upstream source {upstream_id}")
            if sources[upstream_id]["sourceFamilyId"] != row["sourceFamilyId"]:
                raise CampaignValidationError(f"Derived source {source_id} must retain the upstream source family")
        is_lead = row["sourceTier"] == "lead_only"
        if is_lead != (row["independenceStatus"] == "lead_only"):
            raise CampaignValidationError(f"Source {source_id} must align lead-only tier and independence")
        if row["accessStatus"] == "retrieved" and row["contentSha256"] is None:
            raise CampaignValidationError(f"Retrieved source {source_id} requires a content hash")
        if row["accessStatus"] == "inaccessible" and row["contentSha256"] is not None:
            raise CampaignValidationError(f"Inaccessible source {source_id} cannot claim a content hash")
        if row["rights"]["redistributionAllowed"] and row["rights"]["status"] not in {
            "public_domain", "open_license", "permission_granted"
        }:
            raise CampaignValidationError(f"Source {source_id} cannot authorize redistribution under its rights status")
        reject_forbidden_keys(row, f"source {source_id}")
    return sources


def validate_assertions(
    rows: list[dict[str, Any]], sources: Mapping[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    assertions = _unique_map(rows, "assertionId", "assertionId")
    for row in rows:
        assertion_id = row["assertionId"]
        if not _case_domain_matches(row["caseId"], row["domain"]):
            raise CampaignValidationError(f"Assertion {assertion_id} case/domain mismatch")
        if row["domain"] == "crop_circle" and row["fieldName"] in ANIMAL_ONLY_FIELDS:
            raise CampaignValidationError(f"Assertion {assertion_id} uses an animal-only field")
        if row["domain"] == "animal_mutilation" and row["fieldName"] in CROP_ONLY_FIELDS:
            raise CampaignValidationError(f"Assertion {assertion_id} uses a crop-only field")
        cited = set(row["sourceIds"])
        located = {item["sourceId"] for item in row["sourceLocators"]}
        if cited != located:
            raise CampaignValidationError(f"Assertion {assertion_id} must provide exactly one or more locators per cited source set")
        for source_id in cited:
            if source_id not in sources:
                raise CampaignValidationError(f"Assertion {assertion_id} references missing source {source_id}")
        if row["evidenceSha256"] != sorted(row["evidenceSha256"]):
            raise CampaignValidationError(f"Assertion {assertion_id} evidence hashes must be sorted")
        field = row["fieldName"]
        value = row["value"]
        if field == "latitude" and (not isinstance(value, (int, float)) or isinstance(value, bool) or not -90 <= value <= 90):
            raise CampaignValidationError(f"Assertion {assertion_id} latitude is invalid")
        if field == "longitude" and (not isinstance(value, (int, float)) or isinstance(value, bool) or not -180 <= value <= 180):
            raise CampaignValidationError(f"Assertion {assertion_id} longitude is invalid")
        if field == "coordinate_uncertainty_m" and (
            not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0
        ):
            raise CampaignValidationError(f"Assertion {assertion_id} coordinate uncertainty is invalid")
        if field == "duplicate_of_case_id" and (not isinstance(value, str) or not re.fullmatch(r"(?:cc|ami)_[a-f0-9]+", value)):
            raise CampaignValidationError(f"Assertion {assertion_id} duplicate target is invalid")
        reject_forbidden_keys(row, f"assertion {assertion_id}")
    return assertions


def active_review_decisions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    superseded = {decision_id for row in rows for decision_id in row["supersedesDecisionIds"]}
    return [row for row in rows if row["decisionId"] not in superseded]


def review_state_by_assertion(rows: list[dict[str, Any]]) -> dict[str, str]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in active_review_decisions(rows):
        grouped[row["assertionId"]].append(row)
    states: dict[str, str] = {}
    for assertion_id, decisions in grouped.items():
        positive_outcomes = {"accepted", "duplicate"}
        human = [row for row in decisions if row["reviewer"]["reviewerType"] == "human"]
        if human:
            human_outcomes = {row["outcome"] for row in human}
            duplicate_targets = {
                row["duplicateOfCaseId"] for row in human if row["outcome"] == "duplicate"
            }
            states[assertion_id] = (
                "human_reviewed"
                if len(human_outcomes) == 1
                and human_outcomes.issubset(positive_outcomes)
                and len(duplicate_targets) <= 1
                else "proposed"
            )
            continue
        agent_ids = {row["reviewer"]["reviewerId"] for row in decisions}
        agent_outcomes = {row["outcome"] for row in decisions}
        duplicate_targets = {
            row["duplicateOfCaseId"] for row in decisions if row["outcome"] == "duplicate"
        }
        unanimous_positive = (
            len(agent_outcomes) == 1
            and agent_outcomes.issubset(positive_outcomes)
            and len(duplicate_targets) <= 1
        )
        states[assertion_id] = (
            "source_reviewed" if len(agent_ids) >= 2 and unanimous_positive else "proposed"
        )
    return states


def validate_decisions(
    rows: list[dict[str, Any]], assertions: Mapping[str, dict[str, Any]]
) -> dict[str, str]:
    decisions = _unique_map(rows, "decisionId", "decisionId")
    for row in rows:
        decision_id = row["decisionId"]
        assertion_id = row["assertionId"]
        assertion = assertions.get(assertion_id)
        if assertion is None:
            raise CampaignValidationError(f"Decision {decision_id} references missing assertion {assertion_id}")
        if row["caseId"] != assertion["caseId"] or row["domain"] != assertion["domain"]:
            raise CampaignValidationError(f"Decision {decision_id} case/domain does not match its assertion")
        if row["frozenEvidenceSha256"] != assertion["evidenceSha256"]:
            raise CampaignValidationError(f"Decision {decision_id} does not use the assertion's exact frozen evidence")
        if row["reviewer"]["reviewerType"] == "agent" and row["reviewer"]["runId"] is None:
            raise CampaignValidationError(f"Agent decision {decision_id} requires a runId")
        if row["outcome"] == "duplicate":
            if assertion["fieldName"] != "duplicate_of_case_id":
                raise CampaignValidationError(
                    f"Duplicate decision {decision_id} must review duplicate_of_case_id"
                )
            if assertion["value"] != row["duplicateOfCaseId"]:
                raise CampaignValidationError(
                    f"Duplicate decision {decision_id} does not match the asserted duplicate target"
                )
        for prior_id in row["supersedesDecisionIds"]:
            if prior_id not in decisions:
                raise CampaignValidationError(f"Decision {decision_id} supersedes missing decision {prior_id}")
            prior = decisions[prior_id]
            if prior["assertionId"] != assertion_id or prior["reviewer"]["reviewerId"] != row["reviewer"]["reviewerId"]:
                raise CampaignValidationError(f"Decision {decision_id} may supersede only the same reviewer's decision")
        reject_forbidden_keys(row, f"decision {decision_id}")

    active = active_review_decisions(rows)
    active_reviewer_keys: set[tuple[str, str]] = set()
    for row in active:
        key = (row["assertionId"], row["reviewer"]["reviewerId"])
        if key in active_reviewer_keys:
            raise CampaignValidationError(
                f"Reviewer {key[1]} has multiple active decisions for assertion {key[0]}"
            )
        active_reviewer_keys.add(key)

    states = review_state_by_assertion(rows)
    accepted_by_field: dict[tuple[str, str], list[Any]] = defaultdict(list)
    for assertion_id, state in states.items():
        if state not in {"human_reviewed", "source_reviewed"}:
            continue
        assertion = assertions[assertion_id]
        accepted_by_field[(assertion["caseId"], assertion["fieldName"])].append(assertion["value"])
    for key, values in accepted_by_field.items():
        if key[1] in REPEATABLE_CONTEXT_FIELDS:
            continue
        canonical = {canonical_json_bytes(value) for value in values}
        if len(canonical) > 1:
            raise CampaignValidationError(f"Conflicting reviewed assertions remain unresolved for {key[0]} {key[1]}")
    return states


def validate_queue(rows: list[dict[str, Any]], known_attempt_fingerprints: set[str] | None = None) -> None:
    known_attempt_fingerprints = known_attempt_fingerprints or set()
    _unique_map(rows, "queueId", "queueId")
    attempt_ids: set[str] = set()
    fingerprints: set[str] = set()
    for row in rows:
        queue_id = row["queueId"]
        if row["lane"] == "case_enrichment":
            if not _case_domain_matches(row["caseId"], row["domain"]):
                raise CampaignValidationError(f"Queue item {queue_id} case/domain mismatch")
            subject_id = row["caseId"]
        else:
            if row["caseId"] is not None or not row["candidateId"]:
                raise CampaignValidationError(f"Source-discovery queue item {queue_id} requires only candidateId")
            subject_id = row["candidateId"]
        inputs = row["priorityInputs"]
        if inputs["missingStrictGateCount"] != len(row["missingStrictGates"]):
            raise CampaignValidationError(f"Queue item {queue_id} missing-gate count mismatch")
        expected_score = queue_priority_score(row)
        if row["priorityScore"] != expected_score:
            raise CampaignValidationError(f"Queue item {queue_id} priority score must be {expected_score}")
        budget = row["queryBudget"]
        if budget["escalationApproved"]:
            focus_gate = budget.get("escalationFocusGate")
            missing_gates = row["missingStrictGates"]
            if inputs["missingStrictGateCount"] > 1:
                if focus_gate is None:
                    raise CampaignValidationError(
                        f"Queue item {queue_id} multi-gate escalation requires one explicit focus gate"
                    )
                if focus_gate not in missing_gates:
                    raise CampaignValidationError(
                        f"Queue item {queue_id} escalation focus gate must be unresolved"
                    )
            elif (
                focus_gate is not None
                and row["status"] != "strict_ready"
                and focus_gate not in missing_gates
            ):
                raise CampaignValidationError(
                    f"Queue item {queue_id} escalation focus gate must be unresolved"
                )
        if row["status"] == "strict_ready" and row["missingStrictGates"]:
            raise CampaignValidationError(f"Queue item {queue_id} cannot be strict-ready with missing gates")
        if row["status"] != "strict_ready" and row["lane"] == "case_enrichment" and not row["missingStrictGates"]:
            raise CampaignValidationError(
                f"Queue item {queue_id} must record unresolved gates unless it is strict-ready"
            )
        counts: Counter[tuple[str, str]] = Counter()
        for attempt in row["attempts"]:
            attempt_id = attempt["attemptId"]
            if attempt_id in attempt_ids:
                raise CampaignValidationError(f"Repeated attemptId {attempt_id}")
            attempt_ids.add(attempt_id)
            expected_fingerprint = attempt_fingerprint(attempt["kind"], attempt["target"], attempt["versionSha256"])
            if attempt["fingerprint"] != expected_fingerprint:
                raise CampaignValidationError(f"Attempt {attempt_id} fingerprint does not match its unchanged target/version")
            if expected_fingerprint in fingerprints:
                raise CampaignValidationError(f"Repeated query, URL, sample, or source version fingerprint {expected_fingerprint}")
            if expected_fingerprint in known_attempt_fingerprints:
                raise CampaignValidationError(f"Attempt {attempt_id} repeats a reconciled pre-campaign target")
            fingerprints.add(expected_fingerprint)
            counts[(attempt["phase"], attempt["kind"])] += 1
            if attempt["phase"] == "escalation" and not row["queryBudget"]["escalationApproved"]:
                raise CampaignValidationError(f"Attempt {attempt_id} uses unapproved escalation")
        first_openings = counts[("first_pass", "source_open")] + counts[("first_pass", "repository_sample")] + counts[("first_pass", "source_version")]
        escalation_openings = counts[("escalation", "source_open")] + counts[("escalation", "repository_sample")] + counts[("escalation", "source_version")]
        if counts[("first_pass", "query")] > 2 or first_openings > 4:
            raise CampaignValidationError(f"Queue item {queue_id} exceeds first-pass budget")
        if counts[("escalation", "query")] > 3 or escalation_openings > 4 or counts[("escalation", "archive_fallback")] > 1:
            raise CampaignValidationError(f"Queue item {queue_id} exceeds escalation budget")
        if row["terminalDisposition"] != row["status"]:
            raise CampaignValidationError(f"Queue item {queue_id} terminal disposition must equal status")
        if row["status"] in {"blocked", "quarantined", "parked"} and not row["blockers"]:
            raise CampaignValidationError(f"Queue item {queue_id} requires an explicit blocker")
        if row["lane"] == "source_discovery":
            if row["candidateDisposition"] is None:
                raise CampaignValidationError(
                    f"Source-discovery queue item {queue_id} must classify its terminal candidate disposition"
                )
        elif row["candidateDisposition"] is not None:
            raise CampaignValidationError(f"Case-enrichment queue item {queue_id} cannot have a source disposition")
        reject_forbidden_keys(row, f"queue item {queue_id}")

    by_wave: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_wave[row["waveId"]].append(row)
    for wave_id, wave_rows in by_wave.items():
        ordered = sorted(
            wave_rows,
            key=lambda row: (-row["priorityScore"], row["caseId"] or row["candidateId"], row["queueId"]),
        )
        if [row["queueId"] for row in wave_rows] != [row["queueId"] for row in ordered]:
            raise CampaignValidationError(
                f"Research queue wave {wave_id} must be stored in deterministic priority order"
            )
        if [row["rank"] for row in wave_rows] != list(range(1, len(wave_rows) + 1)):
            raise CampaignValidationError(
                f"Research queue wave {wave_id} ranks must be contiguous and start at 1"
            )


def validate_new_case_bootstraps(
    queue_rows: list[dict[str, Any]],
    assertions: Mapping[str, dict[str, Any]],
    review_states: Mapping[str, str],
) -> None:
    reviewed_fields: dict[str, set[str]] = defaultdict(set)
    for assertion_id, state in review_states.items():
        if state in {"human_reviewed", "source_reviewed"}:
            assertion = assertions[assertion_id]
            reviewed_fields[assertion["caseId"]].add(assertion["fieldName"])
    date_fields = {
        "occurrence_date", "formation_date", "discovery_date", "death_interval",
        "report_date", "catalog_date", "publication_date",
    }
    location_fields = {"location_label", "latitude", "longitude"}
    for row in queue_rows:
        if row["caseClass"] != "accepted_new_source" or row["status"] not in {
            "materially_upgraded", "strict_ready"
        }:
            continue
        fields = reviewed_fields[row["caseId"]]
        missing: list[str] = []
        if "source_case_identifier" not in fields:
            missing.append("source_case_identifier")
        if not fields.intersection({"public_title", "public_summary"}):
            missing.append("public_title_or_summary")
        if "primary_classification" not in fields:
            missing.append("primary_classification")
        if not fields.intersection(date_fields):
            missing.append("date_role")
        if not fields.intersection(location_fields):
            missing.append("location_role")
        if row["domain"] == "animal_mutilation" and not fields.intersection({"animal_species", "victim_count"}):
            missing.append("animal_species_or_victim_count")
        if row["domain"] == "crop_circle" and "crop_type" not in fields:
            missing.append("crop_type")
        if missing:
            raise CampaignValidationError(
                f"New case {row['caseId']} cannot reach terminal acceptance without reviewed bootstrap fields: {', '.join(missing)}"
            )


def _validate_baseline_artifacts(baseline: Mapping[str, Any], repo_root: Path) -> None:
    baseline_commit = str(baseline.get("baselineCommit") or "")
    if not re.fullmatch(r"[0-9a-f]{40}", baseline_commit):
        raise CampaignValidationError("Baseline commit must be a full lowercase Git object ID")

    for artifact in baseline["artifacts"]:
        path_text = str(artifact.get("path") or "")
        relative = PurePosixPath(path_text)
        if (
            not relative.parts
            or relative.is_absolute()
            or path_text != relative.as_posix()
            or any(part in {"", ".", ".."} for part in relative.parts)
            or ":" in path_text
        ):
            raise CampaignValidationError(f"Unsafe baseline artifact path: {path_text!r}")

        object_spec = f"{baseline_commit}:{path_text}"
        try:
            result = subprocess.run(
                ["git", "cat-file", "blob", object_spec],
                cwd=repo_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        except OSError as exc:
            raise CampaignValidationError(
                f"Unable to read sealed baseline Git object: {path_text}"
            ) from exc
        if result.returncode != 0:
            raise CampaignValidationError(
                f"Baseline artifact is missing from sealed commit {baseline_commit}: {path_text}"
            )

        artifact_bytes = result.stdout
        if len(artifact_bytes) != artifact["bytes"]:
            raise CampaignValidationError(f"Baseline artifact byte count changed: {artifact['path']}")
        if hashlib.sha256(artifact_bytes).hexdigest() != artifact["sha256"]:
            raise CampaignValidationError(f"Baseline artifact hash changed: {artifact['path']}")


def _validate_lane_stop_state(state: Mapping[str, Any]) -> None:
    for lane_name, lane in state["laneState"].items():
        if lane["consecutiveNoGainSubwaves"] == 2 and lane["status"] != "parked":
            raise CampaignValidationError(f"Lane {lane_name} must be parked after two no-gain subwaves")
        if lane["status"] == "parked" and lane["consecutiveNoGainSubwaves"] < 2:
            raise CampaignValidationError(f"Lane {lane_name} cannot be parked before two no-gain subwaves")


def _validate_release_seal(
    seal: Mapping[str, Any],
    *,
    campaign_root: Path,
    baseline: Mapping[str, Any],
    queue_rows: list[dict[str, Any]],
) -> None:
    repo_root = campaign_root.parents[1]
    released = seal["releaseStatus"] == "released"
    source_commit = seal["sourceCommit"]
    if released and not isinstance(source_commit, str):
        raise CampaignValidationError("Released source commit must be a full lowercase Git object ID")
    ledger_paths = {
        "source": campaign_root / "ledgers" / LEDGERS["source"],
        "enrichment": campaign_root / "ledgers" / LEDGERS["assertion"],
        "review": campaign_root / "ledgers" / LEDGERS["decision"],
        "queue": campaign_root / "ledgers" / LEDGERS["queue"],
    }
    frozen_ledger_bytes: dict[str, bytes] = {}
    for name, path in ledger_paths.items():
        record = seal["frozenLedgers"][name]
        expected_relative = path.relative_to(repo_root).as_posix()
        if record["path"] != expected_relative:
            raise CampaignValidationError(f"Release seal {name} ledger path must be {expected_relative}")
        if released:
            payload = git_commit_blob_bytes(repo_root, source_commit, expected_relative)
            frozen_ledger_bytes[name] = payload
            identity_matches = len(payload) == record["bytes"] and sha256_bytes(payload) == record["sha256"]
        else:
            identity_matches = path.stat().st_size == record["bytes"] and sha256_file(path) == record["sha256"]
        if not identity_matches:
            raise CampaignValidationError(f"Release seal {name} ledger identity is stale")

    summary_queue_rows = queue_rows
    if released:
        summary_queue_rows = load_jsonl_bytes(
            frozen_ledger_bytes["queue"],
            f"release seal queue at {source_commit}",
        )
    terminal_material_statuses = {"materially_upgraded", "strict_ready"}
    material_case_ids = {
        row["caseId"]
        for row in summary_queue_rows
        if row["lane"] == "case_enrichment"
        and row["caseId"]
        and row["status"] in terminal_material_statuses
    }
    strict_by_domain = {
        domain: {
            row["caseId"]
            for row in summary_queue_rows
            if row["lane"] == "case_enrichment"
            and row["domain"] == domain
            and row["caseId"]
            and row["status"] == "strict_ready"
        }
        for domain in ("crop_circle", "animal_mutilation")
    }
    summary = seal["dataSummary"]
    if summary["materiallyUpgradedOverall"] != len(material_case_ids):
        raise CampaignValidationError("Release seal materially-upgraded count does not match the frozen queue")
    strict_counts = {
        "cropCircle": len(strict_by_domain["crop_circle"]),
        "animalMutilation": len(strict_by_domain["animal_mutilation"]),
    }
    for domain, strict_count in strict_counts.items():
        if summary["domains"][domain]["strictReady"] != strict_count:
            raise CampaignValidationError(
                f"Release seal {domain} strict-ready count does not match the frozen queue"
            )
    first_milestone_met = (
        len(material_case_ids) >= 100
        and strict_counts["cropCircle"] >= 25
        and strict_counts["animalMutilation"] >= 25
    )
    if summary["firstMilestoneMet"] != first_milestone_met:
        raise CampaignValidationError("Release seal first-milestone result is inconsistent with frozen counts")
    scope = seal["authorizedScope"]
    if first_milestone_met or scope["milestoneClaimed"] or scope["strictReadinessClaimed"]:
        raise CampaignValidationError(
            "This release seal is restricted to an explicit non-milestone release with no strict claim"
        )

    rollback = seal["rollback"]
    if rollback["deploymentId"] != baseline["production"]["deploymentId"]:
        raise CampaignValidationError("Release rollback must retain the sealed pre-release production deployment")
    if rollback["sourceCommit"] != baseline["production"]["sourceCommit"]:
        raise CampaignValidationError("Release rollback source commit must match the sealed baseline production")

    if not released:
        if seal["sourceCommit"] is not None or seal["finalizedAt"] is not None:
            raise CampaignValidationError("Pre-release seal cannot claim a finalized source commit or time")
        if seal["artifactManifests"] or seal["r2Releases"] or seal["reproduction"] is not None:
            raise CampaignValidationError("Pre-release seal cannot contain published artifact evidence")
        pages = seal["pages"]
        if any(value is not None for value in pages.values()):
            raise CampaignValidationError("Pre-release seal cannot contain Pages deployment evidence")
        for gate_name, gate in seal["acceptance"].items():
            if gate != {"status": "pending", "runCount": 0, "evidenceLocator": None}:
                raise CampaignValidationError(f"Pre-release {gate_name} gate must remain pending and unused")
        return

    for artifact in seal["artifactManifests"]:
        relative = Path(artifact["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise CampaignValidationError(f"Unsafe release artifact path: {artifact['path']}")
        payload = git_commit_blob_bytes(repo_root, source_commit, relative.as_posix())
        if len(payload) != artifact["bytes"] or sha256_bytes(payload) != artifact["sha256"]:
            raise CampaignValidationError(f"Released artifact manifest identity changed: {artifact['path']}")
    artifact_domains = [record["domain"] for record in seal["artifactManifests"]]
    if sorted(artifact_domains) != ["analysis", "animal_mutilation", "crop_circle"]:
        raise CampaignValidationError("Released seal must record exactly crop, animal, and Analysis manifests")

    r2_domains = [record["domain"] for record in seal["r2Releases"]]
    if sorted(r2_domains) != ["analysis", "animal_mutilation", "crop_circle"]:
        raise CampaignValidationError("Released seal must record exactly crop, animal, and Analysis R2 releases")
    if any(not record["readbackVerified"] for record in seal["r2Releases"]):
        raise CampaignValidationError("Every released R2 object set must pass immutable readback")

    pages = seal["pages"]
    preview = pages["preview"]
    production = pages["production"]
    if not pages["identicalPreviewProductionArtifact"]:
        raise CampaignValidationError("Preview and production must use the identical frozen Pages artifact")
    if preview["sourceCommit"] != source_commit or production["sourceCommit"] != source_commit:
        raise CampaignValidationError("Preview and production must pin the released source commit")
    for label, deployment in (("preview", preview), ("production", production)):
        expected_host = deployment["deploymentId"].split("-", 1)[0]
        if f"https://{expected_host}." not in deployment["immutableUrl"]:
            raise CampaignValidationError(f"{label} immutable URL does not match its deployment ID")
    if production["branch"] != "main":
        raise CampaignValidationError("Production Pages deployment must use branch main")

    for gate_name, gate in seal["acceptance"].items():
        if gate["status"] != "passed" or gate["runCount"] != 1 or not gate["evidenceLocator"]:
            raise CampaignValidationError(
                f"Released seal requires exactly one passed {gate_name} gate with evidence"
            )


def validate_frozen_known_source_index(reconciliation: Mapping[str, Any]) -> set[str]:
    index = reconciliation["noRepeatIndex"]
    raw_fingerprints = index.get("fingerprints")
    if not isinstance(raw_fingerprints, list) or any(
        not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value)
        for value in raw_fingerprints
    ):
        raise CampaignValidationError("Frozen known-source fingerprint index is malformed")
    fingerprints = list(raw_fingerprints)
    if fingerprints != sorted(set(fingerprints)):
        raise CampaignValidationError("Frozen known-source fingerprint index must be sorted and unique")
    if index.get("count") != len(fingerprints):
        raise CampaignValidationError("Frozen known-source fingerprint count changed")
    if index.get("sha256") != sha256_bytes(canonical_json_bytes(fingerprints)):
        raise CampaignValidationError("Frozen known-source fingerprint index hash changed")
    return set(fingerprints)


def derive_external_known_source_fingerprints(reconciliation: Mapping[str, Any]) -> set[str]:
    canonical = reconciliation["canonicalInput"]
    path = Path(canonical["path"])
    if not path.is_file():
        raise CampaignValidationError(f"Canonical known-source audit is missing: {path}")
    if path.stat().st_size != canonical["bytes"]:
        raise CampaignValidationError("Canonical known-source audit byte count changed")
    if sha256_file(path) != canonical["sha256"]:
        raise CampaignValidationError("Canonical known-source audit hash changed")

    total_rows = 0
    selected_rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "item_kind", "item_id", "parent_event_id", "source_record_url", "disposition",
            "coverage_status", "http_status", "content_sha256", "archive_snapshot_url",
            "rights_status", "notes",
        }
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise CampaignValidationError("Canonical known-source audit columns changed")
        for row in reader:
            total_rows += 1
            if row["item_kind"] == reconciliation["selection"]["value"]:
                selected_rows.append(row)
    if total_rows != canonical["totalRows"]:
        raise CampaignValidationError("Canonical known-source audit row count changed")
    if len(selected_rows) != reconciliation["selection"]["rows"]:
        raise CampaignValidationError("Known crop-source URL selection count changed")
    if len({row["item_id"] for row in selected_rows}) != len(selected_rows):
        raise CampaignValidationError("Known crop-source audit item IDs are not unique")
    disposition_counts = dict(sorted(Counter(row["disposition"] for row in selected_rows).items()))
    coverage_counts = dict(sorted(Counter(row["coverage_status"] for row in selected_rows).items()))
    if disposition_counts != reconciliation["dispositionCounts"]:
        raise CampaignValidationError("Known-source disposition counts changed")
    if coverage_counts != reconciliation["coverageCounts"]:
        raise CampaignValidationError("Known-source coverage counts changed")

    fingerprints: set[str] = set()
    for row in selected_rows:
        url = row["source_record_url"].strip()
        if not url:
            raise CampaignValidationError(f"Known-source item {row['item_id']} has no URL")
        fingerprints.add(attempt_fingerprint("source_open", url))
        archive_url = row["archive_snapshot_url"].strip()
        if archive_url:
            fingerprints.add(attempt_fingerprint("archive_fallback", archive_url))
    for candidate in reconciliation["externalDiscoveryProvenance"]["candidateRepositories"]:
        fingerprints.add(attempt_fingerprint("repository_sample", candidate))

    registry_pin = reconciliation["existingSourceRegistry"]
    registry_path = Path(registry_pin["path"])
    if not registry_path.is_file():
        raise CampaignValidationError(f"Existing source registry is missing: {registry_path}")
    if registry_path.stat().st_size != registry_pin["bytes"] or sha256_file(registry_path) != registry_pin["sha256"]:
        raise CampaignValidationError("Existing source registry identity changed")
    registry = load_json(registry_path)
    registry_sources = registry.get("sources")
    if not isinstance(registry_sources, list) or len(registry_sources) != registry_pin["sourceRows"]:
        raise CampaignValidationError("Existing source registry row count changed")
    source_ids = [row.get("source_id") for row in registry_sources]
    if any(not source_id for source_id in source_ids) or len(set(source_ids)) != len(source_ids):
        raise CampaignValidationError("Existing source registry IDs are missing or duplicated")
    registry_urls = [str(row["url"]).strip() for row in registry_sources if row.get("url")]
    if len(registry_urls) != registry_pin["urlRows"]:
        raise CampaignValidationError("Existing source registry URL count changed")
    fingerprints.update(attempt_fingerprint("source_open", url) for url in registry_urls)
    return fingerprints


def validate_known_source_reconciliation(reconciliation: Mapping[str, Any]) -> set[str]:
    frozen_fingerprints = validate_frozen_known_source_index(reconciliation)
    canonical_path = Path(reconciliation["canonicalInput"]["path"])
    registry_path = Path(reconciliation["existingSourceRegistry"]["path"])
    available = (canonical_path.is_file(), registry_path.is_file())
    if available == (False, False):
        return frozen_fingerprints
    if available != (True, True):
        raise CampaignValidationError(
            "Known-source external inputs must either both be available or both be absent"
        )
    derived_fingerprints = derive_external_known_source_fingerprints(reconciliation)
    if derived_fingerprints != frozen_fingerprints:
        raise CampaignValidationError("Frozen known-source fingerprint index does not match canonical inputs")
    return frozen_fingerprints


def write_known_source_index(campaign_root: Path = DEFAULT_CAMPAIGN_ROOT) -> Path:
    path = campaign_root / "state" / "known_source_reconciliation.json"
    reconciliation = load_json(path)
    fingerprints = sorted(derive_external_known_source_fingerprints(reconciliation))
    reconciliation["noRepeatIndex"] = {
        "targetColumn": "source_record_url",
        "fingerprintAlgorithm": "sha256_attempt_kind_normalized_target_version_v1",
        "storage": "frozen_sorted_index_recomputed_when_canonical_inputs_available",
        "exactMatchRequired": True,
        "count": len(fingerprints),
        "sha256": sha256_bytes(canonical_json_bytes(fingerprints)),
        "fingerprints": fingerprints,
    }
    path.write_bytes(canonical_json_bytes(reconciliation))
    return path


def validate_campaign(campaign_root: Path = DEFAULT_CAMPAIGN_ROOT) -> dict[str, Any]:
    campaign_root = campaign_root.resolve()
    repo_root = campaign_root.parents[1]
    contract_root = campaign_root / "contracts" / "v1"
    ledger_root = campaign_root / "ledgers"
    schemas = {name: load_json(contract_root / filename) for name, filename in CONTRACTS.items()}
    validators = {name: _validator(schema, name) for name, schema in schemas.items()}

    baseline = load_json(campaign_root / "state" / "baseline_seal.json")
    state = load_json(campaign_root / "state" / "current.json")
    no_gain = load_json(campaign_root / "state" / "no_gain_policy.json")
    reconciliation = load_json(campaign_root / "state" / "known_source_reconciliation.json")
    release_seal = load_json(campaign_root / "state" / "release_seal.json")
    validators["baseline"].validate(baseline)
    validators["state"].validate(state)
    validators["no_gain"].validate(no_gain)
    validators["known_sources"].validate(reconciliation)
    _validate_document(release_seal, validators["release_seal"], "release seal")
    if baseline["baselineCommit"] != baseline["production"]["sourceCommit"]:
        raise CampaignValidationError("Baseline commit and production source commit must match")
    _validate_baseline_artifacts(baseline, repo_root)
    _validate_lane_stop_state(state)
    known_attempt_fingerprints = validate_known_source_reconciliation(reconciliation)
    reject_forbidden_keys(state, "campaign state")

    rows = {name: load_jsonl(ledger_root / filename) for name, filename in LEDGERS.items()}
    for name in LEDGERS:
        _validate_rows(rows[name], validators[name], name)
    sources = validate_sources(rows["source"])
    assertions = validate_assertions(rows["assertion"], sources)
    review_states = validate_decisions(rows["decision"], assertions)
    validate_queue(rows["queue"], known_attempt_fingerprints)
    validate_new_case_bootstraps(rows["queue"], assertions, review_states)
    _validate_release_seal(
        release_seal,
        campaign_root=campaign_root,
        baseline=baseline,
        queue_rows=rows["queue"],
    )
    return {
        "schemas": schemas,
        "baseline": baseline,
        "state": state,
        "noGain": no_gain,
        "knownSources": reconciliation,
        "releaseSeal": release_seal,
        "rows": rows,
        "reviewStates": review_states,
    }


def build_receipt(
    campaign_root: Path = DEFAULT_CAMPAIGN_ROOT,
    *,
    artifact_byte_overrides: Mapping[str, bytes] | None = None,
) -> dict[str, Any]:
    validated = validate_campaign(campaign_root)
    campaign_root = campaign_root.resolve()
    repo_root = campaign_root.parents[1]
    receipt_path = campaign_root / "state" / "foundation_build_receipt.json"
    artifacts: dict[str, dict[str, Any]] = {}
    mutable_release_seal_path = campaign_root / "state" / "release_seal.json"
    excluded = {
        receipt_path.relative_to(repo_root).as_posix(),
        mutable_release_seal_path.relative_to(repo_root).as_posix(),
    }
    campaign_prefix = campaign_root.relative_to(repo_root).as_posix()
    artifact_paths = [
        relative
        for relative in git_index_paths(repo_root, campaign_prefix)
        if relative not in excluded
    ]
    overrides = dict(artifact_byte_overrides or {})
    invalid_overrides = sorted(set(overrides) - set(artifact_paths))
    if invalid_overrides:
        raise CampaignValidationError(
            "Receipt byte override is not a tracked campaign artifact: "
            + ", ".join(invalid_overrides)
        )
    if any(not isinstance(payload, bytes) for payload in overrides.values()):
        raise CampaignValidationError("Receipt artifact byte overrides must be bytes")
    for relative in artifact_paths:
        payload = overrides.get(relative)
        if payload is None:
            payload = git_index_bytes(repo_root, relative)
        artifacts[relative] = {"bytes": len(payload), "sha256": sha256_bytes(payload)}
    builder_path = Path(__file__).resolve()
    builder_relative = builder_path.relative_to(repo_root).as_posix()
    builder_payload = git_index_bytes(repo_root, builder_relative)
    builder_hash = sha256_bytes(builder_payload)
    tree_lines = [f"{path}\0{record['bytes']}\0{record['sha256']}" for path, record in artifacts.items()]
    tree_lines.append(f"{builder_relative}\0{len(builder_payload)}\0{builder_hash}")
    tree_hash = sha256_bytes(("\n".join(tree_lines) + "\n").encode("utf-8"))
    rows = validated["rows"]
    receipt = {
        "schemaId": "ufo-timeline-context-evidence-foundation-receipt-v1.0.0",
        "campaignId": CAMPAIGN_ID,
        "validationEpoch": validated["baseline"]["sealedAt"],
        "builder": {"path": builder_relative, "sha256": builder_hash},
        "packageTreeSha256": tree_hash,
        "artifacts": artifacts,
        "externalInputs": {
            validated["knownSources"]["canonicalInput"]["path"]: {
                "bytes": validated["knownSources"]["canonicalInput"]["bytes"],
                "sha256": validated["knownSources"]["canonicalInput"]["sha256"],
                "selectedRows": validated["knownSources"]["selection"]["rows"],
            },
            validated["knownSources"]["existingSourceRegistry"]["path"]: {
                "bytes": validated["knownSources"]["existingSourceRegistry"]["bytes"],
                "sha256": validated["knownSources"]["existingSourceRegistry"]["sha256"],
                "selectedRows": validated["knownSources"]["existingSourceRegistry"]["sourceRows"],
            },
        },
        "ledgerCounts": {
            "sources": len(rows["source"]),
            "assertions": len(rows["assertion"]),
            "reviewDecisions": len(rows["decision"]),
            "queueItems": len(rows["queue"]),
        },
        "semanticChecks": SEMANTIC_CHECKS,
        "result": "valid",
    }
    _validator(validated["schemas"]["receipt"], "receipt").validate(receipt)
    return receipt


def write_receipt(
    campaign_root: Path = DEFAULT_CAMPAIGN_ROOT,
    *,
    artifact_byte_overrides: Mapping[str, bytes] | None = None,
) -> Path:
    path = campaign_root / "state" / "foundation_build_receipt.json"
    path.write_bytes(
        canonical_json_bytes(
            build_receipt(
                campaign_root,
                artifact_byte_overrides=artifact_byte_overrides,
            )
        )
    )
    return path


def check_receipt(
    campaign_root: Path = DEFAULT_CAMPAIGN_ROOT,
    *,
    artifact_byte_overrides: Mapping[str, bytes] | None = None,
) -> None:
    path = campaign_root / "state" / "foundation_build_receipt.json"
    expected = canonical_json_bytes(
        build_receipt(
            campaign_root,
            artifact_byte_overrides=artifact_byte_overrides,
        )
    )
    try:
        actual = path.read_bytes()
    except OSError as exc:
        raise CampaignValidationError(f"Foundation receipt is missing: {path}") from exc
    if actual != expected:
        raise CampaignValidationError(
            "Foundation receipt is stale; run --write-receipt once after intentional contract or ledger changes"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate and receipt the bounded context-evidence campaign foundation.")
    parser.add_argument("--campaign-root", type=Path, default=DEFAULT_CAMPAIGN_ROOT)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--check", action="store_true", help="Require the tracked receipt to match (default).")
    action.add_argument("--write-receipt", action="store_true", help="Write the deterministic candidate receipt.")
    action.add_argument(
        "--write-known-source-index",
        action="store_true",
        help="Freeze the no-repeat fingerprint index from both content-addressed external inputs.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.write_known_source_index:
            path = write_known_source_index(args.campaign_root)
            print(f"wrote {path}")
        elif args.write_receipt:
            path = write_receipt(args.campaign_root)
            print(f"wrote {path}")
        else:
            check_receipt(args.campaign_root)
            print("context evidence campaign foundation: valid")
    except CampaignValidationError as exc:
        print(f"context evidence campaign foundation: invalid: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
