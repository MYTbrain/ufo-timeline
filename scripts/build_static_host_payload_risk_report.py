"""Build a report-only static host payload risk summary.

This report compares the lean and full-detail canonical web sidecar payloads
using the existing payload readiness checks. It is intentionally advisory: it
does not stage payload files, change app config, promote runtime defaults, or
mutate canonical outputs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_LEAN_READINESS = Path("data/reports/canonical_web_static_payload_readiness.json")
DEFAULT_FULL_READINESS = Path("data/reports/canonical_web_static_payload_full_readiness.json")
DEFAULT_ROLLBACK_AUDIT = Path("data/reports/canonical_promotion_rollback_gap_audit.json")
DEFAULT_JSON_OUTPUT = Path("data/reports/static_host_payload_risk_report.json")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/static_host_payload_risk_report.md")


def build_static_host_payload_risk_report(
    *,
    lean_payload_readiness: dict[str, Any],
    full_payload_readiness: dict[str, Any],
    rollback_audit: dict[str, Any],
) -> dict[str, Any]:
    lean = summarize_payload("lean_primary_trace_payload", lean_payload_readiness)
    full = summarize_payload("full_detail_primary_trace_payload", full_payload_readiness)
    larger_payload = "full_detail_primary_trace_payload" if (full["gzip_mb"] or 0) >= (lean["gzip_mb"] or 0) else "lean_primary_trace_payload"

    default_runtime_config_changed = bool(rollback_audit.get("default_runtime_config_changed"))
    ready_for_default_promotion = bool(rollback_audit.get("ready_for_default_promotion"))
    return {
        "schema_version": 1,
        "report_policy": "static_host_payload_risk_report_only",
        "canonical_outputs_mutated": False,
        "default_runtime_config_changed": default_runtime_config_changed,
        "payloads_staged": default_runtime_config_changed,
        "ready_for_default_promotion": ready_for_default_promotion,
        "overall_risk": classify_overall_risk(lean, full),
        "larger_payload": larger_payload,
        "payloads": {
            "lean_primary_trace_payload": lean,
            "full_detail_primary_trace_payload": full,
        },
        "promotion_context": {
            "current_gate_status": rollback_audit.get("current_gate_status"),
            "default_runtime_config_changed": rollback_audit.get("default_runtime_config_changed"),
            "canonical_outputs_mutated": rollback_audit.get("canonical_outputs_mutated"),
            "ready_for_default_promotion": rollback_audit.get("ready_for_default_promotion"),
        },
        "deployment_checks_before_promotion": [
            (
                "For future payload updates, reconfirm static host accepts the full payload file count and total object size."
                if default_runtime_config_changed
                else "Confirm static host accepts the full payload file count and total object size."
            ),
            "Confirm .gz siblings are served with Content-Encoding: gzip and correct cache headers.",
            "Confirm CDN/browser cache behavior for summary shards, event chunks, and binary trace files.",
            "Confirm upload process preserves both raw and .gz siblings without path rewriting.",
            (
                "Rerun browser smoke against the actual promoted bundle after each payload refresh."
                if default_runtime_config_changed
                else "Rerun guarded static-config browser smoke against the actual promoted bundle root."
            ),
        ],
        "notes": [
            "Lean payload is appropriate for primary catalog plus trace runtime without event detail chunks.",
            "Full-detail payload adds event chunks and should be treated as a larger deployment/storage review item.",
            (
                "This report only summarizes risk; canonicalWebArtifacts defaults are already enabled elsewhere."
                if default_runtime_config_changed
                else "This report only summarizes risk; it does not enable canonicalWebArtifacts defaults."
            ),
        ],
    }


def summarize_payload(label: str, payload: dict[str, Any]) -> dict[str, Any]:
    counts = payload.get("counts") if isinstance(payload.get("counts"), dict) else {}
    checks = payload.get("checks") if isinstance(payload.get("checks"), dict) else {}
    gzip_mb = bytes_to_mb(counts.get("gzip_bytes"))
    raw_mb = bytes_to_mb(counts.get("raw_bytes"))
    total_mb = bytes_to_mb(counts.get("total_bytes"))
    return {
        "label": label,
        "status": payload.get("status"),
        "mode": payload.get("mode"),
        "payload_root": payload.get("payload_root"),
        "files": counts.get("files"),
        "raw_files": counts.get("raw_files"),
        "gzip_files": counts.get("gzip_files"),
        "summary_shards": counts.get("summary_shards"),
        "event_chunks": counts.get("event_chunks"),
        "raw_mb": raw_mb,
        "gzip_mb": gzip_mb,
        "total_mb": total_mb,
        "size_risk": classify_size_risk(gzip_mb),
        "default_app_config_canonical_disabled": checks.get("default_app_config_canonical_disabled"),
        "checks_ready": payload.get("status") == "ready" and all(bool(value) for value in checks.values()),
    }


def classify_size_risk(gzip_mb: float | None) -> str:
    if gzip_mb is None:
        return "unknown"
    if gzip_mb >= 250:
        return "high"
    if gzip_mb >= 100:
        return "medium"
    return "moderate"


def classify_overall_risk(lean: dict[str, Any], full: dict[str, Any]) -> str:
    risks = {lean.get("size_risk"), full.get("size_risk")}
    if "high" in risks:
        return "high"
    if "medium" in risks:
        return "medium"
    if "unknown" in risks:
        return "unknown"
    return "moderate"


def bytes_to_mb(value: Any) -> float | None:
    try:
        return round(int(value) / (1024 * 1024), 2)
    except (TypeError, ValueError):
        return None


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Static Host Payload Risk Report",
        "",
        f"- Report policy: `{report.get('report_policy')}`",
        f"- Overall risk: `{report.get('overall_risk')}`",
        f"- Ready for default promotion: `{str(report.get('ready_for_default_promotion')).lower()}`",
        f"- Default runtime config changed: `{str(report.get('default_runtime_config_changed')).lower()}`",
        f"- Canonical outputs mutated: `{str(report.get('canonical_outputs_mutated')).lower()}`",
        "",
        "## Payloads",
        "",
    ]
    for key, payload in report["payloads"].items():
        lines.append(
            f"- `{key}`: status `{payload.get('status')}`, files `{payload.get('files')}`, "
            f"gzip MB `{payload.get('gzip_mb')}`, event chunks `{payload.get('event_chunks')}`, "
            f"size risk `{payload.get('size_risk')}`"
        )
    lines.extend(["", "## Deployment Checks Before Promotion", ""])
    lines.extend(f"- {item}" for item in report["deployment_checks_before_promotion"])
    lines.extend(["", "## Notes", ""])
    lines.extend(f"- {item}" for item in report["notes"])
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
    parser.add_argument("--lean-payload-readiness", type=Path, default=DEFAULT_LEAN_READINESS)
    parser.add_argument("--full-payload-readiness", type=Path, default=DEFAULT_FULL_READINESS)
    parser.add_argument("--rollback-audit", type=Path, default=DEFAULT_ROLLBACK_AUDIT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_static_host_payload_risk_report(
        lean_payload_readiness=read_json(args.lean_payload_readiness),
        full_payload_readiness=read_json(args.full_payload_readiness),
        rollback_audit=read_json(args.rollback_audit),
    )
    report["inputs"] = {
        "lean_payload_readiness": str(args.lean_payload_readiness),
        "full_payload_readiness": str(args.full_payload_readiness),
        "rollback_audit": str(args.rollback_audit),
    }
    report["outputs"] = {"json": str(args.json_output), "markdown": str(args.markdown_output)}
    write_json(args.json_output, report)
    write_text(args.markdown_output, render_markdown(report))
    print(
        json.dumps(
            {
                "json": str(args.json_output),
                "markdown": str(args.markdown_output),
                "overall_risk": report["overall_risk"],
                "ready_for_default_promotion": report["ready_for_default_promotion"],
                "canonical_outputs_mutated": report["canonical_outputs_mutated"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
