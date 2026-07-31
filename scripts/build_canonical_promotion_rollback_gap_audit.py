"""Build a report-only canonical promotion/rollback gap audit.

The audit compares checked-in runtime defaults against the candidate canonical
runtime flags and records the payload, smoke, rollback, and risk gaps that must
be handled in a future approved promotion. It does not change config or data.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_APP_CONFIG = Path("static_bundle/data/app_config.json")
DEFAULT_READINESS_GATE = Path("data/reports/runtime_integration_readiness_gate.json")
DEFAULT_DECISION_PACKET = Path("data/reports/canonical_promotion_decision_packet.json")
DEFAULT_LEAN_PAYLOAD_READINESS = Path("data/reports/canonical_web_static_payload_readiness.json")
DEFAULT_FULL_PAYLOAD_READINESS = Path("data/reports/canonical_web_static_payload_full_readiness.json")
DEFAULT_JSON_OUTPUT = Path("data/reports/canonical_promotion_rollback_gap_audit.json")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/canonical_promotion_rollback_gap_audit.md")

PROMOTED_CANONICAL_FLAGS = {
    "enabled": True,
    "primaryCatalog": True,
    "traceRuntime": True,
    "filteredTraceAggregation": True,
}


def build_canonical_promotion_rollback_gap_audit(
    *,
    app_config: dict[str, Any],
    readiness_gate: dict[str, Any],
    decision_packet: dict[str, Any],
    lean_payload_readiness: dict[str, Any],
    full_payload_readiness: dict[str, Any],
) -> dict[str, Any]:
    current_flags = extract_canonical_flags(app_config)
    default_promoted = all(current_flags.get(key) is True for key in PROMOTED_CANONICAL_FLAGS)
    ready_for_default_promotion = bool(readiness_gate.get("ready_for_default_promotion"))
    flag_deltas = {
        key: {
            "current": current_flags.get(key),
            "candidate": candidate_value,
            "would_change": current_flags.get(key) != candidate_value,
        }
        for key, candidate_value in PROMOTED_CANONICAL_FLAGS.items()
    }
    return {
        "schema_version": 1,
        "audit_policy": "canonical_promotion_rollback_gap_audit_report_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "default_runtime_config_changed": default_promoted,
        "default_runtime_config_promoted": default_promoted,
        "ready_for_default_promotion": ready_for_default_promotion,
        "current_gate_status": readiness_gate.get("status"),
        "promotion_blockers": list(readiness_gate.get("promotion_blockers") or []),
        "checked_in_default_flags": current_flags,
        "candidate_promoted_flags": PROMOTED_CANONICAL_FLAGS,
        "flag_deltas": flag_deltas,
        "config_only_files_that_would_change_if_approved": [
            "static_bundle/data/app_config.json",
            "static_bundle.zip",
        ],
        "sidecar_payloads": {
            "lean_primary_trace_payload": summarize_payload_readiness(lean_payload_readiness),
            "full_detail_primary_trace_payload": summarize_payload_readiness(full_payload_readiness),
        },
        "smoke_evidence": decision_packet.get("evidence") if isinstance(decision_packet.get("evidence"), dict) else {},
        "rollback_steps": [
            "Set canonicalWebArtifacts.enabled=false.",
            "Set canonicalWebArtifacts.primaryCatalog=false.",
            "Set canonicalWebArtifacts.traceRuntime=false.",
            "Set canonicalWebArtifacts.filteredTraceAggregation=false.",
            "Rebuild static_bundle from source.",
            "Refresh static_bundle.zip.",
            "Run full pytest.",
            "Run the guarded browser smoke in non-promoted/default-disabled mode.",
            "Regenerate runtime_integration_readiness_gate.json.",
        ],
        "unresolved_risks": [
            "Canonical mutation remains a separate contract and must not be mixed into runtime config promotion.",
            "The full-detail sidecar is large; deployment must confirm static host storage, gzip headers, and cache behavior.",
            (
                "The promoted runtime has been smoked against the actual static_bundle; future payload updates must repeat that smoke."
                if default_promoted
                else "The static-config smoke used a temporary root; an approved promotion branch must rerun smoke against the actual changed bundle."
            ),
        ],
        "notes": [
            (
                "Checked-in app_config is already promoted."
                if default_promoted
                else "This audit does not modify checked-in app_config."
            ),
            (
                "The promoted canonical web payload is staged under static_bundle/data/canonical_web."
                if default_promoted
                else "This audit does not copy sidecar payloads into the default bundle."
            ),
            "This audit does not mutate data/canonical_full/deduped_events.jsonl.",
        ],
    }


def extract_canonical_flags(app_config: dict[str, Any]) -> dict[str, bool | None]:
    config = app_config.get("canonicalWebArtifacts")
    if not isinstance(config, dict):
        config = {}
    return {key: config.get(key) if isinstance(config.get(key), bool) else None for key in PROMOTED_CANONICAL_FLAGS}


def summarize_payload_readiness(payload: dict[str, Any]) -> dict[str, Any]:
    counts = payload.get("counts") if isinstance(payload.get("counts"), dict) else {}
    checks = payload.get("checks") if isinstance(payload.get("checks"), dict) else {}
    return {
        "status": payload.get("status"),
        "mode": payload.get("mode"),
        "payload_root": payload.get("payload_root"),
        "files": counts.get("files"),
        "summary_shards": counts.get("summary_shards"),
        "event_chunks": counts.get("event_chunks"),
        "raw_mb": bytes_to_mb(counts.get("raw_bytes")),
        "gzip_mb": bytes_to_mb(counts.get("gzip_bytes")),
        "default_app_config_canonical_disabled": checks.get("default_app_config_canonical_disabled"),
    }


def bytes_to_mb(value: Any) -> float | None:
    try:
        return round(int(value) / (1024 * 1024), 2)
    except (TypeError, ValueError):
        return None


def render_markdown(audit: dict[str, Any]) -> str:
    lines = [
        "# Canonical Promotion/Rollback Gap Audit",
        "",
        f"- Gate status: `{audit.get('current_gate_status')}`",
        f"- Ready for default promotion: `{str(audit.get('ready_for_default_promotion')).lower()}`",
        f"- Default runtime config changed: `{str(audit.get('default_runtime_config_changed')).lower()}`",
        f"- Canonical outputs mutated: `{str(audit.get('canonical_outputs_mutated')).lower()}`",
        "",
        "## Candidate Flag Delta",
        "",
    ]
    for key, delta in audit["flag_deltas"].items():
        lines.append(f"- `{key}`: `{delta['current']}` -> `{delta['candidate']}`")
    lines.extend(["", "## Sidecar Payloads", ""])
    for label, payload in audit["sidecar_payloads"].items():
        lines.append(
            f"- `{label}`: status `{payload.get('status')}`, files `{payload.get('files')}`, "
            f"gzip MB `{payload.get('gzip_mb')}`, event chunks `{payload.get('event_chunks')}`"
        )
    lines.extend(["", "## Rollback Steps", ""])
    lines.extend(f"- {step}" for step in audit["rollback_steps"])
    lines.extend(["", "## Unresolved Risks", ""])
    lines.extend(f"- {risk}" for risk in audit["unresolved_risks"])
    lines.append("")
    return "\n".join(lines)


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-config", type=Path, default=DEFAULT_APP_CONFIG)
    parser.add_argument("--readiness-gate", type=Path, default=DEFAULT_READINESS_GATE)
    parser.add_argument("--decision-packet", type=Path, default=DEFAULT_DECISION_PACKET)
    parser.add_argument("--lean-payload-readiness", type=Path, default=DEFAULT_LEAN_PAYLOAD_READINESS)
    parser.add_argument("--full-payload-readiness", type=Path, default=DEFAULT_FULL_PAYLOAD_READINESS)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    audit = build_canonical_promotion_rollback_gap_audit(
        app_config=read_json(args.app_config),
        readiness_gate=read_json(args.readiness_gate),
        decision_packet=read_json(args.decision_packet),
        lean_payload_readiness=read_json(args.lean_payload_readiness),
        full_payload_readiness=read_json(args.full_payload_readiness),
    )
    audit["inputs"] = {
        "app_config": str(args.app_config),
        "readiness_gate": str(args.readiness_gate),
        "decision_packet": str(args.decision_packet),
        "lean_payload_readiness": str(args.lean_payload_readiness),
        "full_payload_readiness": str(args.full_payload_readiness),
    }
    audit["outputs"] = {"json": str(args.json_output), "markdown": str(args.markdown_output)}
    write_json(args.json_output, audit)
    write_text(args.markdown_output, render_markdown(audit))
    print(
        json.dumps(
            {
                "json": str(args.json_output),
                "markdown": str(args.markdown_output),
                "current_gate_status": audit["current_gate_status"],
                "ready_for_default_promotion": audit["ready_for_default_promotion"],
                "default_runtime_config_changed": audit["default_runtime_config_changed"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
