from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from scripts import build_context_evidence_campaign as campaign


ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN_ROOT = ROOT / "campaign" / "context_evidence"
HEX = "a" * 64


def _queue_row(*, lane: str = "case_enrichment") -> dict:
    source_discovery = lane == "source_discovery"
    row = {
        "schemaId": "ufo-timeline-context-evidence-research-queue-v1.0.0",
        "queueId": "rq_aaaaaaaaaaaaaaaa",
        "caseId": None if source_discovery else "cc_aaaaaaaaaaaaaaaa",
        "candidateId": "source_candidate_example/repository" if source_discovery else None,
        "domain": "crop_circle",
        "lane": lane,
        "caseClass": "source_candidate" if source_discovery else "crop_candidate_field",
        "missingStrictGates": [] if source_discovery else ["review_quorum"],
        "priorityInputs": {
            "missingStrictGateCount": 0 if source_discovery else 1,
            "independentSourceFamilyCount": 0,
            "exactOccurrenceDay": False,
            "sourceSupportedCoordinate": False,
        },
        "priorityScore": 0,
        "rank": 1,
        "queryBudget": {
            "firstPassQueries": 2,
            "firstPassSourceOpenings": 4,
            "escalationQueries": 3,
            "escalationSourceOpenings": 4,
            "archiveFallbacks": 1,
            "escalationApproved": False,
        },
        "attempts": [],
        "blockers": [],
        "waveId": "wave-001-foundation-fixture",
        "status": "no_gain",
        "terminalDisposition": "no_gain",
        "candidateDisposition": "metadata_only" if source_discovery else None,
        "createdAt": "2026-08-10T00:00:00Z",
        "updatedAt": "2026-08-10T00:00:00Z",
    }
    row["priorityScore"] = campaign.queue_priority_score(row)
    return row


def _assertion(assertion_id: str, value: object) -> dict:
    return {
        "assertionId": assertion_id,
        "caseId": "cc_aaaaaaaaaaaaaaaa",
        "domain": "crop_circle",
        "fieldName": "formation_date",
        "value": value,
        "evidenceSha256": [HEX],
    }


def _decision(decision_id: str, assertion_id: str, reviewer_id: str) -> dict:
    return {
        "decisionId": decision_id,
        "assertionId": assertion_id,
        "caseId": "cc_aaaaaaaaaaaaaaaa",
        "domain": "crop_circle",
        "outcome": "accepted",
        "reviewer": {"reviewerId": reviewer_id, "reviewerType": "agent", "runId": f"run-{reviewer_id}"},
        "frozenEvidenceSha256": [HEX],
        "supersedesDecisionIds": [],
    }


def test_tracked_campaign_is_valid_populated_and_receipted() -> None:
    validated = campaign.validate_campaign(CAMPAIGN_ROOT)
    campaign.check_receipt(CAMPAIGN_ROOT)
    assert validated["baseline"]["baselineCommit"] == "e96acd36a6e572deb42507dd1e8be0d939f25212"
    assert validated["baseline"]["domainBaseline"]["cropCircle"]["strictReady"] == 0
    assert validated["baseline"]["domainBaseline"]["animalMutilation"]["strictReady"] == 0
    assert validated["knownSources"]["selection"]["rows"] == 2371
    assert validated["knownSources"]["noRepeatIndex"]["count"] == 2393
    rows = validated["rows"]
    assert all(rows[name] for name in ("source", "assertion", "decision", "queue"))
    assert len(validated["reviewStates"]) == len(rows["assertion"])
    review_states = set(validated["reviewStates"].values())
    assert review_states <= {"proposed", "source_reviewed", "human_reviewed"}
    assert "source_reviewed" in review_states
    assert any(row["status"] == "materially_upgraded" for row in rows["queue"])


def test_frozen_known_source_index_supports_clean_clone_validation(tmp_path: Path) -> None:
    reconciliation = json.loads(
        (CAMPAIGN_ROOT / "state" / "known_source_reconciliation.json").read_text(encoding="utf-8")
    )
    reconciliation["canonicalInput"]["path"] = str(tmp_path / "missing-audit.csv")
    reconciliation["existingSourceRegistry"]["path"] = str(tmp_path / "missing-registry.json")

    fingerprints = campaign.validate_known_source_reconciliation(reconciliation)

    assert len(fingerprints) == 2393
    assert len(fingerprints) == reconciliation["noRepeatIndex"]["count"]


def test_foundation_receipt_seals_git_canonical_bytes() -> None:
    receipt = json.loads(
        (CAMPAIGN_ROOT / "state" / "foundation_build_receipt.json").read_text(encoding="utf-8")
    )
    for relative, record in receipt["artifacts"].items():
        payload = campaign.git_index_bytes(ROOT, relative)
        assert len(payload) == record["bytes"]
        assert hashlib.sha256(payload).hexdigest() == record["sha256"]

    builder = receipt["builder"]
    payload = campaign.git_index_bytes(ROOT, builder["path"])
    assert hashlib.sha256(payload).hexdigest() == builder["sha256"]


def test_source_discovery_queue_has_candidate_identity_without_fake_case() -> None:
    row = _queue_row(lane="source_discovery")
    schema = json.loads(
        (CAMPAIGN_ROOT / "contracts" / "v1" / "research_queue.schema.json").read_text(encoding="utf-8")
    )
    errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(row))
    assert errors == []
    campaign.validate_queue([row])


def test_append_only_queue_ranks_each_frozen_wave_independently() -> None:
    first = _queue_row()
    second = deepcopy(first)
    second["queueId"] = "rq_bbbbbbbbbbbbbbbb"
    second["caseId"] = "cc_bbbbbbbbbbbbbbbb"
    second["waveId"] = "wave-002-foundation-fixture"
    second["rank"] = 1
    campaign.validate_queue([first, second])


def test_strict_ready_queue_closes_its_last_gate_after_approved_escalation() -> None:
    row = _queue_row()
    row["missingStrictGates"] = []
    row["priorityInputs"]["missingStrictGateCount"] = 0
    row["queryBudget"]["escalationApproved"] = True
    row["status"] = row["terminalDisposition"] = "strict_ready"
    row["priorityScore"] = campaign.queue_priority_score(row)
    schema = json.loads(
        (CAMPAIGN_ROOT / "contracts" / "v1" / "research_queue.schema.json").read_text(encoding="utf-8")
    )
    errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(row))
    assert errors == []
    campaign.validate_queue([row])


def test_inaccessible_lead_allows_null_hash_but_retrieved_source_does_not() -> None:
    schema = json.loads(
        (CAMPAIGN_ROOT / "contracts" / "v1" / "source_ledger.schema.json").read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    source = {
        "schemaId": "ufo-timeline-context-evidence-source-v1.0.0",
        "sourceId": "src_aaaaaaaaaaaaaaaa",
        "sourceFamilyId": "sf_aaaaaaaaaaaaaaaa",
        "title": "Unavailable lead",
        "publisher": "Example",
        "publicationDate": None,
        "authors": [],
        "locator": {"kind": "url", "value": "https://example.test/lead", "accessedAt": "2026-08-10", "pageOrSection": None},
        "accessStatus": "inaccessible",
        "contentSha256": None,
        "sourceTier": "lead_only",
        "rights": {"status": "rights_unknown", "redistributionAllowed": False, "license": None, "notes": None},
        "retention": {"class": "link_only", "storageLocation": None, "decision": "Retain metadata and URL only."},
        "derivation": {"derivedFromSourceIds": [], "relation": "original"},
        "independenceStatus": "lead_only",
        "registeredAt": "2026-08-10T00:00:00Z",
    }
    assert list(validator.iter_errors(source)) == []
    retrieved = deepcopy(source)
    retrieved["accessStatus"] = "retrieved"
    assert list(validator.iter_errors(retrieved))


def test_reviewer_quorum_is_deterministic_and_conflicts_fail_closed() -> None:
    first = _assertion("cea_aaaaaaaaaaaaaaaa", "1977-07-01")
    assertions = {first["assertionId"]: first}
    decisions = [
        _decision("crd_aaaaaaaaaaaaaaaa", first["assertionId"], "agent-one"),
        _decision("crd_bbbbbbbbbbbbbbbb", first["assertionId"], "agent-two"),
    ]
    states = campaign.validate_decisions(decisions, assertions)
    assert states[first["assertionId"]] == "source_reviewed"

    dissent = _decision("crd_eeeeeeeeeeeeeeee", first["assertionId"], "agent-three")
    dissent["outcome"] = "rejected"
    states = campaign.validate_decisions([*decisions, dissent], assertions)
    assert states[first["assertionId"]] == "proposed"

    repeated_reviewer = _decision("crd_ffffffffffffffff", first["assertionId"], "agent-one")
    with pytest.raises(campaign.CampaignValidationError, match="multiple active decisions"):
        campaign.validate_decisions([*decisions, repeated_reviewer], assertions)

    second = _assertion("cea_bbbbbbbbbbbbbbbb", "1977-07-02")
    assertions[second["assertionId"]] = second
    decisions.extend(
        [
            _decision("crd_cccccccccccccccc", second["assertionId"], "agent-one"),
            _decision("crd_dddddddddddddddd", second["assertionId"], "agent-two"),
        ]
    )
    with pytest.raises(campaign.CampaignValidationError, match="Conflicting reviewed assertions"):
        campaign.validate_decisions(decisions, assertions)


def test_wave4_associated_claims_are_additive_after_independent_quorum() -> None:
    claims = [
        {"claimType": "campaign_identity", "value": "Bacardi Seven Tiki"},
        {
            "claimType": "source_lineage_or_scope_decision",
            "status": "count_as_one_family_pending_separate_evidence",
        },
    ]
    assertions: dict[str, dict] = {}
    decisions: list[dict] = []
    for index, claim in enumerate(claims):
        assertion_id = f"cea_{'b' if index else 'a'}" + "1" * 15
        assertion = _assertion(assertion_id, claim)
        assertion["fieldName"] = "associated_claim"
        assertions[assertion_id] = assertion
        decisions.extend([
            _decision(f"crd_{index}aaaaaaaaaaaaaaa", assertion_id, "wave4-agent-a"),
            _decision(f"crd_{index}bbbbbbbbbbbbbbb", assertion_id, "wave4-agent-b"),
        ])

    states = campaign.validate_decisions(decisions, assertions)

    assert set(states) == set(assertions)
    assert set(states.values()) == {"source_reviewed"}


def test_attempt_fingerprints_block_normalized_repeats() -> None:
    row = _queue_row()
    target_one = "HTTPS://Example.test/path/?b=2&a=1#fragment"
    target_two = "https://example.test/path?a=1&b=2"
    fingerprint = campaign.attempt_fingerprint("source_open", target_one)
    assert fingerprint == campaign.attempt_fingerprint("source_open", target_two)
    row["attempts"] = [
        {
            "attemptId": "ra_aaaaaaaaaaaaaaaa",
            "kind": "source_open",
            "target": target_one,
            "versionSha256": None,
            "fingerprint": fingerprint,
            "automatic": True,
            "phase": "first_pass",
            "result": "failed",
            "attemptedAt": "2026-08-10T00:00:00Z",
        },
        {
            "attemptId": "ra_bbbbbbbbbbbbbbbb",
            "kind": "source_open",
            "target": target_two,
            "versionSha256": None,
            "fingerprint": fingerprint,
            "automatic": True,
            "phase": "first_pass",
            "result": "failed",
            "attemptedAt": "2026-08-10T00:01:00Z",
        },
    ]
    with pytest.raises(campaign.CampaignValidationError, match="Repeated query, URL"):
        campaign.validate_queue([row])
