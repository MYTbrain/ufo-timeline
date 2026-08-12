from __future__ import annotations

import hashlib

import pytest

from scripts import build_context_evidence_campaign as campaign
from scripts import context_evidence_attempt_fingerprint as helper


def _queue_row(attempt: dict) -> dict:
    row = {
        "queueId": "rq_aaaaaaaaaaaaaaaa",
        "caseId": "cc_aaaaaaaaaaaaaaaa",
        "candidateId": None,
        "domain": "crop_circle",
        "lane": "case_enrichment",
        "caseClass": "crop_candidate_field",
        "missingStrictGates": ["review_quorum"],
        "priorityInputs": {
            "missingStrictGateCount": 1,
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
            "escalationFocusGate": None,
        },
        "attempts": [attempt],
        "blockers": [],
        "waveId": "wave-008-fingerprint-fixture",
        "status": "no_gain",
        "terminalDisposition": "no_gain",
        "candidateDisposition": None,
    }
    row["priorityScore"] = campaign.queue_priority_score(row)
    return row


def test_query_uses_canonical_contract_and_preserves_original_attempt() -> None:
    target = '"Initial Field Report" "Kekoskee" filetype:pdf'
    packet_hash = hashlib.sha256(target.encode("utf-8")).hexdigest()
    attempt = {
        "kind": "query",
        "target": target,
        "versionSha256": None,
        "fingerprint": packet_hash,
        "automatic": False,
    }

    stamped = helper.stamp_attempt_fingerprint(attempt)

    assert stamped["fingerprint"] == "49881812112f497613a455ee1f3caddf787dd05b1c53f796d0b60e20933a1934"
    assert stamped["fingerprint"] != packet_hash
    assert stamped["target"] == target
    assert stamped["versionSha256"] is None
    assert stamped["automatic"] is False
    assert attempt["fingerprint"] == packet_hash


def test_source_open_url_normalization_is_stable_without_rewriting_url() -> None:
    first = "HTTPS://Example.test/path/?b=2&a=1#fragment"
    second = "https://example.test/path?a=1&b=2"

    first_attempt = helper.stamp_attempt_fingerprint(
        {"kind": "source_open", "target": first, "versionSha256": None}
    )
    second_attempt = helper.stamp_attempt_fingerprint(
        {"kind": "source_open", "target": second, "versionSha256": None}
    )

    assert first_attempt["fingerprint"] == second_attempt["fingerprint"]
    assert first_attempt["fingerprint"] == "350b98c4c33ac4f2c839dc83ee0e07a6850b30a6f2b236cb5d9d8859cf8beeb9"
    assert first_attempt["target"] == first
    assert second_attempt["target"] == second


def test_source_version_fingerprint_includes_exact_version_identity() -> None:
    target = "https://example.test/report"
    first_version = "a" * 64
    second_version = "b" * 64

    first = helper.canonical_attempt_fingerprint("source_version", target, first_version)
    repeated = helper.canonical_attempt_fingerprint("source_version", target, first_version)
    changed = helper.canonical_attempt_fingerprint("source_version", target, second_version)

    assert first == "d5e0421d5595d1538f98335f96a58916b29fc589d050b3635ae0335a21a37999"
    assert first == repeated
    assert changed == "d5e81498b66abd6ef6ff3e5c5ddaa7f103072e4868edf0a3dc4d2f8fdd0475a9"
    assert changed != first


def test_query_normalization_is_stable_for_case_and_whitespace() -> None:
    first = helper.canonical_attempt_fingerprint("query", "  Crop   Circle MAYVILLE  ")
    second = helper.canonical_attempt_fingerprint("query", "crop circle mayville")

    assert first == second
    assert first == "cb21bb5d9df7a7e5b5e9fc8b007c1c40b1fbc1cea44c05211d709a30e40b5458"


def test_validator_rejects_incompatible_research_packet_fingerprint() -> None:
    target = '"Initial Field Report" "Kekoskee" filetype:pdf'
    attempt = {
        "attemptId": "ra_aaaaaaaaaaaaaaaa",
        "kind": "query",
        "target": target,
        "versionSha256": None,
        "fingerprint": hashlib.sha256(target.encode("utf-8")).hexdigest(),
        "automatic": False,
        "phase": "first_pass",
        "result": "no_gain",
        "attemptedAt": "2026-08-11T00:00:00Z",
    }

    with pytest.raises(campaign.CampaignValidationError, match="fingerprint does not match"):
        campaign.validate_queue([_queue_row(attempt)])


def test_stamped_attempt_passes_validator_and_keeps_no_automatic_retry() -> None:
    attempt = {
        "attemptId": "ra_bbbbbbbbbbbbbbbb",
        "kind": "query",
        "target": '"Initial Field Report" "Kekoskee" filetype:pdf',
        "versionSha256": None,
        "fingerprint": "0" * 64,
        "automatic": False,
        "phase": "first_pass",
        "result": "no_gain",
        "attemptedAt": "2026-08-11T00:00:00Z",
    }

    stamped = helper.stamp_attempt_fingerprint(attempt)
    campaign.validate_queue([_queue_row(stamped)])

    assert stamped["automatic"] is False
