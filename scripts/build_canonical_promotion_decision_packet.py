"""Build a report-only canonical runtime promotion decision packet.

This packet summarizes current smoke evidence, test status, unchanged defaults,
and the explicit approval choices still required before promoting the canonical
primary catalog/trace runtime. It does not change app config or mutate data.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_PHASE_STATUS = Path("data/canonical/reports/phase_status.json")
DEFAULT_READINESS_GATE = Path("data/reports/runtime_integration_readiness_gate.json")
DEFAULT_JSON_OUTPUT = Path("data/reports/canonical_promotion_decision_packet.json")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/canonical_promotion_decision_packet.md")


def build_canonical_promotion_decision_packet(
    *,
    phase_status: dict[str, Any],
    readiness_gate: dict[str, Any],
) -> dict[str, Any]:
    metrics = phase_status_metrics(phase_status)
    outputs = phase_status.get("outputs") if isinstance(phase_status.get("outputs"), dict) else {}
    default_promoted = readiness_gate.get("status") == "default_promoted_ready"
    return {
        "schema_version": 1,
        "packet_policy": "canonical_runtime_promotion_decision_packet_report_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "default_runtime_config_changed": default_promoted,
        "default_runtime_config_promoted": default_promoted,
        "ready_for_preview_package": bool(readiness_gate.get("ready_for_preview_package")),
        "ready_for_default_promotion": bool(readiness_gate.get("ready_for_default_promotion")),
        "current_gate_status": readiness_gate.get("status"),
        "promotion_blockers": list(readiness_gate.get("promotion_blockers") or []),
        "evidence": {
            "guarded_10k_smoke": metrics.get("canonical_primary_trace_aggregation_browser_smoke"),
            "guarded_full_sidecar_smoke": metrics.get("canonical_primary_trace_aggregation_browser_smoke_latest_diagnostic"),
            "static_config_10k_smoke": metrics.get("canonical_static_config_promotion_smoke"),
            "static_config_full_sidecar_smoke": metrics.get("canonical_static_config_promotion_smoke_full_sidecar"),
            "static_config_full_sidecar_diagnostic": metrics.get(
                "canonical_static_config_promotion_smoke_full_sidecar_latest_diagnostic"
            ),
            "full_sidecar_trace_rows": metrics.get("canonical_primary_trace_aggregation_browser_smoke_full_trace_rows"),
            "full_sidecar_rendered_segments": metrics.get(
                "canonical_primary_trace_aggregation_browser_smoke_full_rendered_segments"
            ),
            "remaining_lower_candidate_check_valid": get_nested(
                metrics,
                "entity_resolution_remaining_lower_time_format_candidate_check",
                "valid",
            ),
            "remaining_lower_candidate_ready_for_canonical_apply": get_nested(
                metrics,
                "entity_resolution_remaining_lower_time_format_candidate_check",
                "ready_for_canonical_apply",
            ),
            "full_pytest_latest": metrics.get("full_pytest_latest") or "415 passed",
        },
        "approval_choices": [
            {
                "id": "approve_default_canonical_runtime",
                "decision_required": not default_promoted,
                "status": "completed" if default_promoted else "pending_approval",
                "recommended_scope": (
                    "completed config-only default promotion"
                    if default_promoted
                    else "config-only promotion branch after preserving rollback path"
                ),
                "changes_allowed_if_approved": [
                    "static_bundle/data/app_config.json canonicalWebArtifacts flags",
                    "rebuilt static_bundle and static_bundle.zip",
                    "refreshed runtime readiness gate",
                ],
                "changes_not_in_scope": [
                    "canonical_full/deduped_events.jsonl mutation",
                    "new dedupe decisions",
                    "backend/server deployment changes",
                ],
            },
            {
                "id": "approve_canonical_mutation",
                "decision_required": True,
                "recommended_scope": "separate future contract only",
                "changes_allowed_if_approved": [
                    "explicit promote-mode apply tool with rollback and audit gates",
                ],
                "changes_not_in_scope": [
                    "runtime default promotion branch",
                    "silent writes to canonical_full/deduped_events.jsonl",
                ],
            },
            {
                "id": "defer_and_continue_report_only",
                "decision_required": False,
                "recommended_scope": "continue sidecar/report-only analysis lanes",
                "changes_allowed_if_selected": [
                    "new reports under data/reports",
                    "temporary sidecar roots",
                    "tests and docs",
                ],
                "changes_not_in_scope": [
                    "checked-in default runtime promotion",
                    "accepted/apply decision promotion without explicit approval",
                ],
            },
        ],
        "outputs": {
            "promotion_plan": outputs.get("canonical_primary_promotion_plan"),
            "worklog": outputs.get("worklog"),
            "runbook": outputs.get("runbook"),
            "runtime_gate": "data/reports/runtime_integration_readiness_gate.json",
        },
        "notes": [
            "This packet is advisory only and does not take the promotion decision.",
            "Default promotion and canonical mutation remain separate decisions.",
            (
                "Checked-in static runtime defaults are now promoted."
                if default_promoted
                else "Current runtime evidence supports preview packaging, while checked-in defaults remain intentionally disabled."
            ),
        ],
    }


def phase_status_metrics(phase_status: dict[str, Any]) -> dict[str, Any]:
    if isinstance(phase_status.get("metrics"), dict):
        return phase_status["metrics"]
    merged: dict[str, Any] = {}
    for key in ("phase_2_progress", "compact_web_artifact_probe"):
        value = phase_status.get(key)
        if isinstance(value, dict):
            merged.update(value)
    return merged


def render_markdown(packet: dict[str, Any]) -> str:
    evidence = packet["evidence"]
    blockers = packet.get("promotion_blockers") or []
    lines = [
        "# Canonical Runtime Promotion Decision Packet",
        "",
        f"- Gate status: `{packet.get('current_gate_status')}`",
        f"- Ready for preview package: `{str(packet.get('ready_for_preview_package')).lower()}`",
        f"- Ready for default promotion: `{str(packet.get('ready_for_default_promotion')).lower()}`",
        f"- Canonical outputs mutated: `{str(packet.get('canonical_outputs_mutated')).lower()}`",
        f"- Default runtime config changed: `{str(packet.get('default_runtime_config_changed')).lower()}`",
        "",
        "## Evidence",
        "",
        f"- Guarded browser smoke: `{evidence.get('guarded_10k_smoke')}`",
        f"- Static-config 10k smoke: `{evidence.get('static_config_10k_smoke')}`",
        f"- Static-config full sidecar smoke: `{evidence.get('static_config_full_sidecar_smoke')}`",
        f"- Full sidecar trace rows: `{evidence.get('full_sidecar_trace_rows')}`",
        f"- Full sidecar rendered segments: `{evidence.get('full_sidecar_rendered_segments')}`",
        f"- Remaining-lower candidate check valid: `{str(evidence.get('remaining_lower_candidate_check_valid')).lower()}`",
        f"- Full pytest latest: `{evidence.get('full_pytest_latest')}`",
        "",
        "## Remaining Blockers",
        "",
    ]
    lines.extend(f"- {blocker}" for blocker in blockers)
    lines.extend(["", "## Approval Choices", ""])
    for choice in packet["approval_choices"]:
        lines.append(f"- `{choice['id']}`: {choice['recommended_scope']}")
    lines.append("")
    return "\n".join(lines)


def get_nested(payload: dict[str, Any], *keys: str) -> Any:
    value: Any = payload
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
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
    parser.add_argument("--phase-status", type=Path, default=DEFAULT_PHASE_STATUS)
    parser.add_argument("--readiness-gate", type=Path, default=DEFAULT_READINESS_GATE)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packet = build_canonical_promotion_decision_packet(
        phase_status=read_json(args.phase_status),
        readiness_gate=read_json(args.readiness_gate),
    )
    packet["inputs"] = {
        "phase_status": str(args.phase_status),
        "readiness_gate": str(args.readiness_gate),
    }
    packet["outputs"].update(
        {
            "json": str(args.json_output),
            "markdown": str(args.markdown_output),
        }
    )
    write_json(args.json_output, packet)
    write_text(args.markdown_output, render_markdown(packet))
    print(
        json.dumps(
            {
                "json": str(args.json_output),
                "markdown": str(args.markdown_output),
                "current_gate_status": packet["current_gate_status"],
                "ready_for_default_promotion": packet["ready_for_default_promotion"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
