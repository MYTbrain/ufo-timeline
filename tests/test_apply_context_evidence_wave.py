from __future__ import annotations

from copy import deepcopy

import pytest

from scripts import apply_context_evidence_wave as writer


def test_merge_is_idempotent_and_rejects_identity_collision() -> None:
    existing = [{"sourceId": "src_aaaaaaaaaaaaaaaa", "value": 1}]
    combined, appended = writer.merge_rows(
        existing, [deepcopy(existing[0])], "sourceId"
    )
    assert combined == existing
    assert appended == []

    with pytest.raises(writer.WaveApplicationError, match="collides"):
        writer.merge_rows(
            existing,
            [{"sourceId": "src_aaaaaaaaaaaaaaaa", "value": 2}],
            "sourceId",
        )


def test_complete_adjudication_requires_two_agents_or_one_human() -> None:
    assertion = {"assertionId": "cea_aaaaaaaaaaaaaaaa"}
    base = {
        "assertionId": assertion["assertionId"],
        "decisionId": "crd_aaaaaaaaaaaaaaaa",
        "reviewer": {"reviewerId": "agent-one", "reviewerType": "agent"},
        "supersedesDecisionIds": [],
    }
    with pytest.raises(writer.WaveApplicationError, match="two independent"):
        writer.require_complete_adjudication([assertion], [base])

    second = deepcopy(base)
    second["decisionId"] = "crd_bbbbbbbbbbbbbbbb"
    second["reviewer"] = {"reviewerId": "agent-two", "reviewerType": "agent"}
    writer.require_complete_adjudication([assertion], [base, second])

    human = deepcopy(base)
    human["reviewer"] = {"reviewerId": "human-one", "reviewerType": "human"}
    writer.require_complete_adjudication([assertion], [human])


def test_append_bytes_preserves_existing_prefix() -> None:
    original = b'{"sourceId":"src_aaaaaaaaaaaaaaaa"}\n'
    output = writer.append_bytes(original, [{"sourceId": "src_bbbbbbbbbbbbbbbb"}])
    assert output.startswith(original)
    assert output.count(b"\n") == 2


def test_package_id_is_content_derived() -> None:
    manifest = {
        "campaignId": "context-evidence-expansion-20260810",
        "waveIds": ["wave-001-fixture"],
        "files": {"source_ledger.jsonl": {"rows": 0, "bytes": 0, "sha256": "a" * 64}},
    }
    first = writer.expected_package_id(manifest)
    changed = deepcopy(manifest)
    changed["files"]["source_ledger.jsonl"]["sha256"] = "b" * 64
    assert first.startswith("cep_")
    assert first != writer.expected_package_id(changed)
