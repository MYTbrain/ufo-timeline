from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts import apply_context_evidence_wave as writer
from scripts import build_context_evidence_campaign as campaign


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


class _NoOpValidator:
    def validate(self, _value: object) -> None:
        pass


def test_receipt_override_seals_applied_bytes_when_index_is_older(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    campaign_root = repo_root / "campaign" / "context_evidence"
    builder_relative = "scripts/build_context_evidence_campaign.py"
    ledger_relative = "campaign/context_evidence/ledgers/source_ledger.jsonl"
    index_bytes = b'{"sourceId":"src_oldoldoldoldold1"}\n'
    applied_bytes = index_bytes + b'{"sourceId":"src_newnewnewnewnew1"}\n'
    builder_bytes = b"# frozen builder\n"
    validated = {
        "schemas": {"receipt": {}},
        "baseline": {"sealedAt": "2026-08-10T00:00:00Z"},
        "knownSources": {
            "canonicalInput": {"path": "D:/input.jsonl", "bytes": 1, "sha256": "a" * 64},
            "selection": {"rows": 1},
            "existingSourceRegistry": {
                "path": "D:/sources.jsonl",
                "bytes": 1,
                "sha256": "b" * 64,
                "sourceRows": 1,
            },
        },
        "rows": {"source": [], "assertion": [], "decision": [], "queue": []},
    }

    monkeypatch.setattr(campaign, "__file__", str(repo_root / builder_relative))
    monkeypatch.setattr(campaign, "validate_campaign", lambda _root: validated)
    monkeypatch.setattr(campaign, "git_index_paths", lambda _root, _prefix: [ledger_relative])
    monkeypatch.setattr(
        campaign,
        "git_index_bytes",
        lambda _root, relative: {
            ledger_relative: index_bytes,
            builder_relative: builder_bytes,
        }[relative],
    )
    monkeypatch.setattr(campaign, "_validator", lambda _schema, _label: _NoOpValidator())

    receipt = campaign.build_receipt(
        campaign_root,
        artifact_byte_overrides={ledger_relative: applied_bytes},
    )

    assert receipt["artifacts"][ledger_relative] == {
        "bytes": len(applied_bytes),
        "sha256": hashlib.sha256(applied_bytes).hexdigest(),
    }
    assert receipt["artifacts"][ledger_relative]["sha256"] != hashlib.sha256(
        index_bytes
    ).hexdigest()


def _apply_fixture(
    tmp_path: Path,
) -> tuple[Path, dict[str, bytes], dict[str, bytes], bytes, dict[str, object]]:
    campaign_root = tmp_path / "repo" / "campaign" / "context_evidence"
    ledger_root = campaign_root / "ledgers"
    state_root = campaign_root / "state"
    ledger_root.mkdir(parents=True)
    state_root.mkdir()
    originals: dict[str, bytes] = {}
    outputs: dict[str, bytes] = {}
    for kind, filename in writer.LEDGER_FILES.items():
        originals[kind] = f'{{"kind":"{kind}-old"}}\n'.encode()
        outputs[kind] = originals[kind] + f'{{"kind":"{kind}-new"}}\n'.encode()
        (ledger_root / filename).write_bytes(originals[kind])
    original_receipt = b'{"receipt":"old"}\n'
    (state_root / "foundation_build_receipt.json").write_bytes(original_receipt)
    manifest: dict[str, object] = {
        "packageId": "cep_" + "a" * 24,
        "waveIds": ["wave-008-test"],
    }
    return campaign_root, originals, outputs, original_receipt, manifest


def test_apply_receipt_seals_exact_worktree_ledgers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    campaign_root, _originals, outputs, _receipt, manifest = _apply_fixture(tmp_path)
    appended = {kind: [{"kind": kind}] for kind in writer.LEDGER_FILES}
    monkeypatch.setattr(
        writer,
        "prepare_application",
        lambda _package, _campaign: (manifest, outputs, appended),
    )
    captured: dict[str, bytes] = {}

    def write_receipt(
        root: Path, *, artifact_byte_overrides: dict[str, bytes] | None = None
    ) -> Path:
        assert artifact_byte_overrides is not None
        captured.update(artifact_byte_overrides)
        records = {
            relative: {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
            for relative, payload in artifact_byte_overrides.items()
        }
        path = root / "state" / "foundation_build_receipt.json"
        path.write_text(json.dumps({"artifacts": records}), encoding="utf-8")
        return path

    def check_receipt(
        root: Path, *, artifact_byte_overrides: dict[str, bytes] | None = None
    ) -> None:
        assert artifact_byte_overrides == captured
        receipt = json.loads(
            (root / "state" / "foundation_build_receipt.json").read_text(encoding="utf-8")
        )
        repo_root = root.parents[1]
        for relative, payload in captured.items():
            assert (repo_root / relative).read_bytes() == payload
            assert receipt["artifacts"][relative] == {
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }

    monkeypatch.setattr(writer.campaign, "write_receipt", write_receipt)
    monkeypatch.setattr(writer.campaign, "check_receipt", check_receipt)

    result = writer.apply_package(tmp_path / "package", campaign_root)

    assert result["result"] == "applied"
    for kind, filename in writer.LEDGER_FILES.items():
        relative = f"campaign/context_evidence/ledgers/{filename}"
        assert captured[relative] == outputs[kind]


@pytest.mark.parametrize("failure_phase", ["write", "check"])
def test_apply_rolls_back_ledgers_and_receipt_after_receipt_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure_phase: str
) -> None:
    campaign_root, originals, outputs, original_receipt, manifest = _apply_fixture(tmp_path)
    appended = {kind: [{"kind": kind}] for kind in writer.LEDGER_FILES}
    monkeypatch.setattr(
        writer,
        "prepare_application",
        lambda _package, _campaign: (manifest, outputs, appended),
    )

    def write_receipt(
        root: Path, *, artifact_byte_overrides: dict[str, bytes] | None = None
    ) -> Path:
        assert artifact_byte_overrides
        path = root / "state" / "foundation_build_receipt.json"
        path.write_bytes(b'{"receipt":"new-or-partial"}\n')
        if failure_phase == "write":
            raise RuntimeError("simulated receipt write failure")
        return path

    def check_receipt(
        _root: Path, *, artifact_byte_overrides: dict[str, bytes] | None = None
    ) -> None:
        assert artifact_byte_overrides
        if failure_phase == "check":
            raise RuntimeError("simulated receipt check failure")

    monkeypatch.setattr(writer.campaign, "write_receipt", write_receipt)
    monkeypatch.setattr(writer.campaign, "check_receipt", check_receipt)

    with pytest.raises(RuntimeError, match="simulated receipt"):
        writer.apply_package(tmp_path / "package", campaign_root)

    ledger_root = campaign_root / "ledgers"
    for kind, filename in writer.LEDGER_FILES.items():
        assert (ledger_root / filename).read_bytes() == originals[kind]
    assert (
        campaign_root / "state" / "foundation_build_receipt.json"
    ).read_bytes() == original_receipt
    assert not list(ledger_root.glob(".*.pending"))
    assert not list(ledger_root.glob(".*.restore"))
