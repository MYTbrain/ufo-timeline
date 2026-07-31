"""Build a report-only deferred work and approval-boundary queue.

This consolidates remaining work into approval buckets so the next step is
explicit: default-runtime approval, canonical mutation/apply approval, or safe
report-only backlog. It does not perform any promotion or apply step.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_READINESS_GATE = Path("data/reports/runtime_integration_readiness_gate.json")
DEFAULT_PROMOTION_PACKET = Path("data/reports/canonical_promotion_decision_packet.json")
DEFAULT_ROLLBACK_AUDIT = Path("data/reports/canonical_promotion_rollback_gap_audit.json")
DEFAULT_REMAINING_LOWER_CHECK = Path("data/reports/entity_resolution_remaining_lower_time_format_decision_candidates_check.json")
DEFAULT_PHASE_STATUS = Path("data/canonical/reports/phase_status.json")
DEFAULT_JSON_OUTPUT = Path("data/reports/deferred_work_queue.json")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/deferred_work_queue.md")


def build_deferred_work_queue(
    *,
    readiness_gate: dict[str, Any],
    promotion_packet: dict[str, Any],
    rollback_audit: dict[str, Any],
    remaining_lower_check: dict[str, Any],
    phase_status: dict[str, Any],
) -> dict[str, Any]:
    progress = {}
    if isinstance(phase_status.get("phase_2_progress"), dict):
        progress.update(phase_status["phase_2_progress"])
    if isinstance(phase_status.get("compact_web_artifact_probe"), dict):
        progress.update(phase_status["compact_web_artifact_probe"])
    default_promoted = readiness_gate.get("status") == "default_promoted_ready"
    default_runtime_item = {
        "id": "promote_canonical_primary_catalog_trace_runtime",
        "status": "completed" if default_promoted else "blocked_pending_approval",
        "evidence": {
            "promotion_packet": "data/reports/canonical_promotion_decision_packet.json",
            "rollback_audit": "data/reports/canonical_promotion_rollback_gap_audit.json",
            "static_config_full_sidecar_smoke": get_nested(
                promotion_packet,
                "evidence",
                "static_config_full_sidecar_smoke",
            ),
            "trace_rows": get_nested(promotion_packet, "evidence", "full_sidecar_trace_rows"),
            "rendered_segments": get_nested(promotion_packet, "evidence", "full_sidecar_rendered_segments"),
        },
    }
    if default_promoted:
        default_runtime_item["completed_actions"] = [
            "static_bundle/data/app_config.json canonicalWebArtifacts flags promoted",
            "canonical primary catalog promoted as default runtime",
            "trace runtime and filtered trace aggregation promoted as default runtime",
        ]
    else:
        default_runtime_item["blocked_actions"] = [
            "change static_bundle/data/app_config.json canonicalWebArtifacts flags",
            "promote canonical primary catalog as default runtime",
            "promote trace runtime and filtered trace aggregation as default runtime",
        ]
    return {
        "schema_version": 1,
        "queue_policy": "deferred_work_queue_report_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "default_runtime_config_changed": default_promoted,
        "default_runtime_config_promoted": default_promoted,
        "current_gate_status": readiness_gate.get("status"),
        "requires_default_runtime_approval": [default_runtime_item],
        "requires_canonical_mutation_or_apply_approval": [
            {
                "id": "apply_remaining_lower_time_format_candidates",
                "status": "blocked_pending_apply_approval",
                "candidate_count": remaining_lower_check.get("decision_candidate_count"),
                "projected_event_reduction": remaining_lower_check.get("projected_event_reduction"),
                "valid_check": remaining_lower_check.get("valid"),
                "ready_for_canonical_apply": remaining_lower_check.get("ready_for_canonical_apply"),
                "blocked_actions": [
                    "accept remaining-lower candidates as canonical decisions",
                    "build/apply a sidecar from those candidates",
                    "mutate data/canonical_full/deduped_events.jsonl",
                ],
            },
            {
                "id": "manual_review_apply_or_canonical_mutation",
                "status": "blocked_pending_contract_and_approval",
                "blocker": "manual review apply remains preview-only; canonical mutation is unavailable by design",
                "blocked_actions": [
                    "promote manual-review sidecars into canonical_full",
                    "write suppressed/replacement rows into canonical_full",
                ],
            },
        ],
        "safe_report_only_backlog": [
            {
                "id": "review_high_coordinate_span_manual_queue",
                "status": report_status(get_nested(progress, "high_coordinate_span_triage_digest")),
                "item_count": get_nested(progress, "manual_review_ai_after_time_norm_high_coordinate_span_review_items"),
                "report": "data/reports/high_coordinate_span_triage_digest.json",
                "note": "Human/evidence review packet exists; no automated promotion is recommended.",
            },
            {
                "id": "review_mixed_medium_manual_queues",
                "status": report_status(get_nested(progress, "mixed_medium_review_triage_digest")),
                "item_count": sum_ints(
                    get_nested(progress, "manual_review_ai_after_time_norm_medium_identity_mixed_review_items"),
                    get_nested(progress, "manual_review_ai_after_time_norm_medium_classification_mixed_review_items"),
                    get_nested(progress, "manual_review_ai_after_time_norm_medium_body_text_mixed_review_items"),
                ),
                "report": "data/reports/mixed_medium_review_triage_digest.json",
                "note": "Mixed risk queues should stay review-only unless stronger evidence rules are added.",
            },
            {
                "id": "monitor_static_host_payload_risk",
                "status": report_status(get_nested(progress, "static_host_payload_risk_report")),
                "full_payload_gzip_mb": get_nested(
                    rollback_audit,
                    "sidecar_payloads",
                    "full_detail_primary_trace_payload",
                    "gzip_mb",
                ),
                "report": "data/reports/static_host_payload_risk_report.json",
                "note": "Deployment/storage/cache review can continue without changing runtime defaults.",
            },
        ],
        "stop_conditions": [
            "Do not make further checked-in canonical runtime default changes without explicit approval.",
            "Do not apply additional remaining-lower candidates without explicit apply approval.",
            "Do not mutate data/canonical_full/deduped_events.jsonl without a separate mutation contract.",
        ],
        "notes": [
            "This queue is advisory only.",
            "It intentionally separates runtime promotion from canonical data mutation.",
        ],
    }


def get_nested(payload: dict[str, Any], *keys: str) -> Any:
    value: Any = payload
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def sum_ints(*values: Any) -> int:
    total = 0
    for value in values:
        try:
            total += int(value)
        except (TypeError, ValueError):
            continue
    return total


def report_status(report_exists: Any) -> str:
    return "completed_report_only" if report_exists is True else "report_only_available"


def render_markdown(queue: dict[str, Any]) -> str:
    lines = [
        "# Deferred Work Queue",
        "",
        f"- Gate status: `{queue.get('current_gate_status')}`",
        f"- Default runtime config changed: `{str(queue.get('default_runtime_config_changed')).lower()}`",
        f"- Canonical outputs mutated: `{str(queue.get('canonical_outputs_mutated')).lower()}`",
        "",
        "## Requires Default Runtime Approval",
        "",
    ]
    lines.extend(f"- `{item['id']}`: {item['status']}" for item in queue["requires_default_runtime_approval"])
    lines.extend(["", "## Requires Canonical Mutation Or Apply Approval", ""])
    lines.extend(f"- `{item['id']}`: {item['status']}" for item in queue["requires_canonical_mutation_or_apply_approval"])
    lines.extend(["", "## Safe Report-Only Backlog", ""])
    lines.extend(f"- `{item['id']}`: {item['status']}" for item in queue["safe_report_only_backlog"])
    lines.extend(["", "## Stop Conditions", ""])
    lines.extend(f"- {condition}" for condition in queue["stop_conditions"])
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
    parser.add_argument("--readiness-gate", type=Path, default=DEFAULT_READINESS_GATE)
    parser.add_argument("--promotion-packet", type=Path, default=DEFAULT_PROMOTION_PACKET)
    parser.add_argument("--rollback-audit", type=Path, default=DEFAULT_ROLLBACK_AUDIT)
    parser.add_argument("--remaining-lower-check", type=Path, default=DEFAULT_REMAINING_LOWER_CHECK)
    parser.add_argument("--phase-status", type=Path, default=DEFAULT_PHASE_STATUS)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    queue = build_deferred_work_queue(
        readiness_gate=read_json(args.readiness_gate),
        promotion_packet=read_json(args.promotion_packet),
        rollback_audit=read_json(args.rollback_audit),
        remaining_lower_check=read_json(args.remaining_lower_check),
        phase_status=read_json(args.phase_status),
    )
    queue["inputs"] = {
        "readiness_gate": str(args.readiness_gate),
        "promotion_packet": str(args.promotion_packet),
        "rollback_audit": str(args.rollback_audit),
        "remaining_lower_check": str(args.remaining_lower_check),
        "phase_status": str(args.phase_status),
    }
    queue["outputs"] = {"json": str(args.json_output), "markdown": str(args.markdown_output)}
    write_json(args.json_output, queue)
    write_text(args.markdown_output, render_markdown(queue))
    print(
        json.dumps(
            {
                "json": str(args.json_output),
                "markdown": str(args.markdown_output),
                "current_gate_status": queue["current_gate_status"],
                "default_runtime_config_changed": queue["default_runtime_config_changed"],
                "default_runtime_config_promoted": queue["default_runtime_config_promoted"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
