"""Validate and atomically append one adjudicated context-evidence wave package.

The research package stays on D:. This canonical writer is the only supported
path from a frozen package into the four compact Git-tracked ledgers. It never
retrieves sources, changes research decisions, or upgrades a review outcome.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import build_context_evidence_campaign as campaign


DEFAULT_CAMPAIGN_ROOT = REPO_ROOT / "campaign" / "context_evidence"
MANIFEST_NAME = "package_manifest.json"
LEDGER_FILES = {
    "source": "source_ledger.jsonl",
    "assertion": "case_enrichment.jsonl",
    "decision": "case_review_decisions.jsonl",
    "queue": "research_queue.jsonl",
}
ID_FIELDS = {
    "source": "sourceId",
    "assertion": "assertionId",
    "decision": "decisionId",
    "queue": "queueId",
}


class WaveApplicationError(ValueError):
    pass


def canonical_line(row: dict[str, Any]) -> bytes:
    return campaign.canonical_json_bytes(row)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def expected_package_id(manifest: dict[str, Any]) -> str:
    identity = {
        "campaignId": manifest["campaignId"],
        "files": manifest["files"],
        "waveIds": manifest["waveIds"],
    }
    return "cep_" + hashlib.sha256(campaign.canonical_json_bytes(identity)).hexdigest()[:24]


def load_package(package_root: Path, campaign_root: Path) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    package_root = package_root.resolve()
    manifest_path = package_root / MANIFEST_NAME
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WaveApplicationError(f"Cannot read frozen package manifest: {manifest_path}") from exc
    schema_path = campaign_root / "contracts" / "v1" / "wave_package.schema.json"
    campaign._validator(campaign.load_json(schema_path), "wave package").validate(manifest)
    expected_id = expected_package_id(manifest)
    if manifest["packageId"] != expected_id:
        raise WaveApplicationError(f"Frozen package ID must be {expected_id}")

    rows: dict[str, list[dict[str, Any]]] = {}
    for kind, filename in LEDGER_FILES.items():
        path = package_root / filename
        identity = manifest["files"][filename]
        if not path.is_file():
            raise WaveApplicationError(f"Frozen package file is missing: {path}")
        if path.stat().st_size != identity["bytes"] or file_sha256(path) != identity["sha256"]:
            raise WaveApplicationError(f"Frozen package identity mismatch: {filename}")
        rows[kind] = campaign.load_jsonl(path)
        if len(rows[kind]) != identity["rows"]:
            raise WaveApplicationError(f"Frozen package row-count mismatch: {filename}")
    return manifest, rows


def merge_rows(
    existing: list[dict[str, Any]], incoming: list[dict[str, Any]], id_field: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_id = {str(row[id_field]): row for row in existing}
    if len(by_id) != len(existing):
        raise WaveApplicationError(f"Canonical ledger has duplicate {id_field} values")
    appended: list[dict[str, Any]] = []
    for row in incoming:
        row_id = str(row[id_field])
        prior = by_id.get(row_id)
        if prior is not None:
            if canonical_line(prior) != canonical_line(row):
                raise WaveApplicationError(f"Frozen package collides with canonical {id_field} {row_id}")
            continue
        by_id[row_id] = row
        appended.append(row)
    return existing + appended, appended


def _active_decisions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    superseded = {
        decision_id
        for row in rows
        for decision_id in row.get("supersedesDecisionIds", [])
    }
    return [row for row in rows if row["decisionId"] not in superseded]


def require_complete_adjudication(
    incoming_assertions: list[dict[str, Any]], combined_decisions: list[dict[str, Any]]
) -> None:
    by_assertion: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in _active_decisions(combined_decisions):
        by_assertion[row["assertionId"]].append(row)
    for assertion in incoming_assertions:
        assertion_id = assertion["assertionId"]
        decisions = by_assertion.get(assertion_id, [])
        human_ids = {
            row["reviewer"]["reviewerId"]
            for row in decisions
            if row["reviewer"]["reviewerType"] == "human"
        }
        agent_ids = {
            row["reviewer"]["reviewerId"]
            for row in decisions
            if row["reviewer"]["reviewerType"] == "agent"
        }
        if not human_ids and len(agent_ids) < 2:
            raise WaveApplicationError(
                f"Assertion {assertion_id} lacks one human or two independent active agent decisions"
            )


def validate_combined(
    campaign_root: Path,
    manifest: dict[str, Any],
    existing: dict[str, list[dict[str, Any]]],
    incoming: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    contract_root = campaign_root / "contracts" / "v1"
    validators = {
        kind: campaign._validator(campaign.load_json(contract_root / campaign.CONTRACTS[kind]), kind)
        for kind in LEDGER_FILES
    }
    for kind, kind_rows in incoming.items():
        campaign._validate_rows(kind_rows, validators[kind], f"wave package {kind}")

    package_reviewer_ids = {row["reviewerId"] for row in manifest["adjudicators"]}
    decision_reviewer_ids = {
        row["reviewer"]["reviewerId"] for row in incoming["decision"]
    }
    if decision_reviewer_ids - package_reviewer_ids:
        raise WaveApplicationError("Decision reviewer is absent from the frozen package adjudicator list")

    wave_ids = set(manifest["waveIds"])
    if any(row["waveId"] not in wave_ids for row in incoming["assertion"]):
        raise WaveApplicationError("Assertion waveId is absent from package waveIds")
    if any(row["waveId"] not in wave_ids for row in incoming["queue"]):
        raise WaveApplicationError("Queue waveId is absent from package waveIds")
    existing_wave_ids = {row["waveId"] for row in existing["queue"]}
    incoming_queue_ids = {row["queueId"] for row in incoming["queue"]}
    if existing_wave_ids.intersection(wave_ids) and not incoming_queue_ids.issubset(
        {row["queueId"] for row in existing["queue"]}
    ):
        raise WaveApplicationError("A canonical queue wave cannot be partially extended")

    combined: dict[str, list[dict[str, Any]]] = {}
    appended: dict[str, list[dict[str, Any]]] = {}
    for kind in LEDGER_FILES:
        combined[kind], appended[kind] = merge_rows(
            existing[kind], incoming[kind], ID_FIELDS[kind]
        )

    reconciliation = campaign.load_json(campaign_root / "state" / "known_source_reconciliation.json")
    known_fingerprints = campaign.validate_known_source_reconciliation(reconciliation)
    sources = campaign.validate_sources(combined["source"])
    assertions = campaign.validate_assertions(combined["assertion"], sources)
    review_states = campaign.validate_decisions(combined["decision"], assertions)
    campaign.validate_queue(combined["queue"], known_fingerprints)
    campaign.validate_new_case_bootstraps(combined["queue"], assertions, review_states)
    require_complete_adjudication(appended["assertion"], combined["decision"])
    return combined, appended


def append_bytes(original: bytes, rows: list[dict[str, Any]]) -> bytes:
    if not rows:
        return original
    separator = b"" if not original or original.endswith(b"\n") else b"\n"
    return original + separator + b"".join(canonical_line(row) for row in rows)


def prepare_application(
    package_root: Path, campaign_root: Path
) -> tuple[dict[str, Any], dict[str, bytes], dict[str, list[dict[str, Any]]]]:
    manifest, incoming = load_package(package_root, campaign_root)
    ledger_root = campaign_root / "ledgers"
    originals = {kind: (ledger_root / filename).read_bytes() for kind, filename in LEDGER_FILES.items()}
    existing = {
        kind: campaign.load_jsonl(ledger_root / filename)
        for kind, filename in LEDGER_FILES.items()
    }
    _combined, appended = validate_combined(campaign_root, manifest, existing, incoming)
    outputs = {kind: append_bytes(originals[kind], appended[kind]) for kind in LEDGER_FILES}
    for kind in LEDGER_FILES:
        if not outputs[kind].startswith(originals[kind]):
            raise WaveApplicationError(f"Append-only prefix check failed for {LEDGER_FILES[kind]}")
    return manifest, outputs, appended


def apply_package(package_root: Path, campaign_root: Path) -> dict[str, Any]:
    manifest, outputs, appended = prepare_application(package_root, campaign_root)
    ledger_root = campaign_root / "ledgers"
    receipt_path = campaign_root / "state" / "foundation_build_receipt.json"
    originals = {
        kind: (ledger_root / filename).read_bytes() for kind, filename in LEDGER_FILES.items()
    }
    original_receipt = receipt_path.read_bytes()
    pending: list[Path] = []
    replaced: list[str] = []
    try:
        for kind, filename in LEDGER_FILES.items():
            path = ledger_root / filename
            candidate = path.with_name(f".{filename}.{manifest['packageId']}.pending")
            candidate.write_bytes(outputs[kind])
            pending.append(candidate)
        for kind, filename in LEDGER_FILES.items():
            os.replace(ledger_root / f".{filename}.{manifest['packageId']}.pending", ledger_root / filename)
            replaced.append(kind)
        repo_root = campaign_root.resolve().parents[1]
        ledger_receipt_bytes: dict[str, bytes] = {}
        for kind, filename in LEDGER_FILES.items():
            path = ledger_root / filename
            payload = path.read_bytes()
            if payload != outputs[kind]:
                raise WaveApplicationError(
                    f"Applied ledger bytes differ from prepared output: {filename}"
                )
            relative = path.resolve().relative_to(repo_root).as_posix()
            ledger_receipt_bytes[relative] = payload
        campaign.write_receipt(
            campaign_root,
            artifact_byte_overrides=ledger_receipt_bytes,
        )
        campaign.check_receipt(
            campaign_root,
            artifact_byte_overrides=ledger_receipt_bytes,
        )
    except Exception:
        for kind in replaced:
            filename = LEDGER_FILES[kind]
            restore = ledger_root / f".{filename}.{manifest['packageId']}.restore"
            restore.write_bytes(originals[kind])
            os.replace(restore, ledger_root / filename)
        receipt_restore = receipt_path.with_name(
            f".{receipt_path.name}.{manifest['packageId']}.restore"
        )
        receipt_restore.write_bytes(original_receipt)
        os.replace(receipt_restore, receipt_path)
        raise
    finally:
        for path in pending:
            path.unlink(missing_ok=True)
    return {
        "packageId": manifest["packageId"],
        "waveIds": manifest["waveIds"],
        "appended": {kind: len(rows) for kind, rows in appended.items()},
        "ledgerSha256": {
            kind: file_sha256(ledger_root / filename) for kind, filename in LEDGER_FILES.items()
        },
        "result": "applied" if any(appended.values()) else "already_applied",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--campaign-root", type=Path, default=DEFAULT_CAMPAIGN_ROOT)
    parser.add_argument("--apply", action="store_true", help="Append after all fail-closed checks pass")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.apply:
            result = apply_package(args.package_root, args.campaign_root)
        else:
            manifest, _outputs, appended = prepare_application(args.package_root, args.campaign_root)
            result = {
                "packageId": manifest["packageId"],
                "waveIds": manifest["waveIds"],
                "wouldAppend": {kind: len(rows) for kind, rows in appended.items()},
                "result": "valid_dry_run",
            }
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    except (WaveApplicationError, campaign.CampaignValidationError, OSError, ValueError) as exc:
        print(f"context evidence wave package: invalid: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
