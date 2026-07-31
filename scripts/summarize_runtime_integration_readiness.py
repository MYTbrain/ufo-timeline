"""Summarize compact runtime integration readiness into one gated report.

This report is intentionally conservative. It can mark the canonical static
payload path as preview-ready, but it must not mark it default-promotable while
browser smoke is blocked, canonical primary catalog remains gated, or manual
review mutation is unavailable by design.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_PHASE_STATUS = Path("data/canonical/reports/phase_status.json")
DEFAULT_APP_CONFIG = Path("static_bundle/data/app_config.json")
DEFAULT_RUNTIME_READINESS = Path("data/reports/canonical_web_runtime_readiness.json")
DEFAULT_LEAN_PAYLOAD_READINESS = Path("data/reports/canonical_web_static_payload_readiness.json")
DEFAULT_FULL_PAYLOAD_READINESS = Path("data/reports/canonical_web_static_payload_full_readiness.json")
DEFAULT_MANUAL_REVIEW_PACKET_READINESS = Path("data/reports/manual_review_packet_readiness.json")
DEFAULT_CANONICAL_FACET_READINESS = Path("data/reports/canonical_facet_readiness.json")
DEFAULT_MANUAL_REVIEW_APPLY_SCRIPT = Path("scripts/apply_manual_review_effects.py")
DEFAULT_OUTPUT = Path("data/reports/runtime_integration_readiness_gate.json")

CANONICAL_FLAGS = (
    "enabled",
    "primaryCatalog",
    "traceRuntime",
    "filteredTraceAggregation",
)


def summarize_runtime_integration_readiness(
    *,
    phase_status_path: Path = DEFAULT_PHASE_STATUS,
    app_config_path: Path = DEFAULT_APP_CONFIG,
    runtime_readiness_path: Path = DEFAULT_RUNTIME_READINESS,
    lean_payload_readiness_path: Path = DEFAULT_LEAN_PAYLOAD_READINESS,
    full_payload_readiness_path: Path = DEFAULT_FULL_PAYLOAD_READINESS,
    manual_review_packet_readiness_path: Path = DEFAULT_MANUAL_REVIEW_PACKET_READINESS,
    canonical_facet_readiness_path: Path = DEFAULT_CANONICAL_FACET_READINESS,
    manual_review_apply_script_path: Path = DEFAULT_MANUAL_REVIEW_APPLY_SCRIPT,
) -> dict[str, Any]:
    phase_status = _read_json_if_exists(phase_status_path)
    app_config = _read_json_if_exists(app_config_path)
    runtime_readiness = _read_json_if_exists(runtime_readiness_path)
    lean_payload_readiness = _read_json_if_exists(lean_payload_readiness_path)
    full_payload_readiness = _read_json_if_exists(full_payload_readiness_path)
    manual_review_packet_readiness = _read_json_if_exists(manual_review_packet_readiness_path)
    canonical_facet_readiness = _read_json_if_exists(canonical_facet_readiness_path)
    manual_review_apply_script = (
        manual_review_apply_script_path.read_text(encoding="utf-8")
        if manual_review_apply_script_path.exists()
        else ""
    )

    compact_probe = phase_status.get("compact_web_artifact_probe", {}) if isinstance(phase_status, dict) else {}
    browser_smoke_status = compact_probe.get("canonical_primary_trace_aggregation_browser_smoke")

    browser_smoke_passed = _browser_smoke_passed(browser_smoke_status)
    browser_smoke_explicitly_blocked = _browser_smoke_explicitly_blocked(browser_smoke_status)

    default_canonical_flags_disabled = _canonical_flags_disabled(app_config)
    default_canonical_flags_promoted = _canonical_flags_promoted(app_config)
    runtime_primary_catalog_ready = runtime_readiness.get("ready_for_primary_catalog") is True
    checks = {
        "default_canonical_flags_disabled": _canonical_flags_disabled(app_config),
        "default_canonical_flags_promoted": default_canonical_flags_promoted,
        "default_canonical_config_valid": default_canonical_flags_disabled or default_canonical_flags_promoted,
        "runtime_ready_for_preview": runtime_readiness.get("ready_for_startup_preview") is True,
        "runtime_primary_catalog_not_promoted": runtime_readiness.get("ready_for_primary_catalog") is False,
        "runtime_primary_catalog_ready": runtime_primary_catalog_ready,
        "lean_payload_ready": lean_payload_readiness.get("status") == "ready",
        "full_detail_payload_ready": full_payload_readiness.get("status") == "ready",
        "gzip_header_smoke_recorded": compact_probe.get("canonical_preview_server_gzip_header_smoke") is True,
        "packed_point_filter_helpers_recorded": compact_probe.get("frontend_packed_point_filter_facet_helpers") is True,
        "trace_render_metrics_recorded": compact_probe.get("frontend_static_trace_render_metrics") is True,
        "manual_review_packet_ready": manual_review_packet_readiness.get("status") == "ready",
        "canonical_facet_readiness_available": canonical_facet_readiness.get("status") in {"ready", "ready_with_caveats"},
        "manual_review_mutation_unavailable": _manual_review_apply_is_preview_only(manual_review_apply_script),
        "browser_smoke_passed_or_explicitly_blocked": browser_smoke_passed or browser_smoke_explicitly_blocked,
    }

    preview_required = (
        "default_canonical_config_valid",
        "runtime_ready_for_preview",
        "lean_payload_ready",
        "full_detail_payload_ready",
        "gzip_header_smoke_recorded",
        "packed_point_filter_helpers_recorded",
        "trace_render_metrics_recorded",
        "manual_review_packet_ready",
        "canonical_facet_readiness_available",
        "manual_review_mutation_unavailable",
        "browser_smoke_passed_or_explicitly_blocked",
    )
    preview_ready = all(checks[name] for name in preview_required)
    default_promoted_ready = all(
        checks[name]
        for name in (
            "default_canonical_flags_promoted",
            "runtime_ready_for_preview",
            "runtime_primary_catalog_ready",
            "full_detail_payload_ready",
            "gzip_header_smoke_recorded",
            "packed_point_filter_helpers_recorded",
            "trace_render_metrics_recorded",
            "canonical_facet_readiness_available",
            "browser_smoke_passed_or_explicitly_blocked",
        )
    ) and browser_smoke_passed
    promotion_blockers = []
    if default_promoted_ready:
        promotion_blockers = []
    elif browser_smoke_explicitly_blocked:
        promotion_blockers.append("browser visual/runtime smoke is still blocked, not passed")
    elif not browser_smoke_passed:
        promotion_blockers.append("browser_smoke_status_not_passed_or_explicitly_blocked")
    if runtime_readiness.get("ready_for_primary_catalog") is not True:
        promotion_blockers.append("canonical primary catalog remains intentionally not promoted")
    if checks["manual_review_mutation_unavailable"] and not default_promoted_ready:
        promotion_blockers.append("manual review apply remains preview-only; canonical mutation is unavailable by design")

    failed_checks = sorted(
        name
        for name, passed in checks.items()
        if not passed and name not in {"default_canonical_flags_disabled", "default_canonical_flags_promoted", "runtime_primary_catalog_not_promoted", "runtime_primary_catalog_ready"}
    )
    return {
        "schema_version": 1,
        "status": "default_promoted_ready" if default_promoted_ready else "preview_ready_default_blocked" if preview_ready else "blocked",
        "ready_for_preview_package": preview_ready,
        "ready_for_default_promotion": default_promoted_ready,
        "checks": checks,
        "failed_checks": failed_checks,
        "promotion_blockers": promotion_blockers,
        "inputs": {
            "phase_status": str(phase_status_path),
            "app_config": str(app_config_path),
            "runtime_readiness": str(runtime_readiness_path),
            "lean_payload_readiness": str(lean_payload_readiness_path),
            "full_payload_readiness": str(full_payload_readiness_path),
            "manual_review_packet_readiness": str(manual_review_packet_readiness_path),
            "canonical_facet_readiness": str(canonical_facet_readiness_path),
            "manual_review_apply_script": str(manual_review_apply_script_path),
        },
        "counts": {
            "lean_payload_files": _nested_int(lean_payload_readiness, "counts", "files"),
            "full_payload_files": _nested_int(full_payload_readiness, "counts", "files"),
            "full_payload_event_chunks": _nested_int(full_payload_readiness, "counts", "event_chunks"),
            "full_payload_gzip_bytes": _nested_int(full_payload_readiness, "counts", "gzip_bytes"),
            "manual_review_packet_items": _nested_int(manual_review_packet_readiness, "counts", "packet_items"),
            "manual_review_packet_csv_rows": _nested_int(manual_review_packet_readiness, "counts", "csv_rows"),
            "canonical_facet_count": len(canonical_facet_readiness.get("facets", {}))
            if isinstance(canonical_facet_readiness.get("facets"), dict)
            else 0,
            "canonical_facet_caveats": len(canonical_facet_readiness.get("caveats", []))
            if isinstance(canonical_facet_readiness.get("caveats"), list)
            else 0,
        },
    }


def _read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _canonical_flags_disabled(config: dict[str, Any]) -> bool:
    canonical_config = config.get("canonicalWebArtifacts") if isinstance(config, dict) else None
    if not isinstance(canonical_config, dict):
        return False
    return all(canonical_config.get(flag) is False for flag in CANONICAL_FLAGS)


def _canonical_flags_promoted(config: dict[str, Any]) -> bool:
    canonical_config = config.get("canonicalWebArtifacts") if isinstance(config, dict) else None
    if not isinstance(canonical_config, dict):
        return False
    return all(canonical_config.get(flag) is True for flag in CANONICAL_FLAGS)


def _browser_smoke_passed(status: Any) -> bool:
    return isinstance(status, str) and status.startswith("passed_")


def _browser_smoke_explicitly_blocked(status: Any) -> bool:
    return isinstance(status, str) and status.startswith("blocked_")


def _manual_review_apply_is_preview_only(script_text: str) -> bool:
    normalized = script_text.replace(" ", "")
    return 'choices=["preview"]' in normalized and "--mode" in script_text and "canonical_outputs_mutated" in script_text


def _nested_int(payload: dict[str, Any], *keys: str) -> int:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return 0
        current = current.get(key)
    return int(current or 0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase-status", type=Path, default=DEFAULT_PHASE_STATUS)
    parser.add_argument("--app-config", type=Path, default=DEFAULT_APP_CONFIG)
    parser.add_argument("--runtime-readiness", type=Path, default=DEFAULT_RUNTIME_READINESS)
    parser.add_argument("--lean-payload-readiness", type=Path, default=DEFAULT_LEAN_PAYLOAD_READINESS)
    parser.add_argument("--full-payload-readiness", type=Path, default=DEFAULT_FULL_PAYLOAD_READINESS)
    parser.add_argument("--manual-review-packet-readiness", type=Path, default=DEFAULT_MANUAL_REVIEW_PACKET_READINESS)
    parser.add_argument("--canonical-facet-readiness", type=Path, default=DEFAULT_CANONICAL_FACET_READINESS)
    parser.add_argument("--manual-review-apply-script", type=Path, default=DEFAULT_MANUAL_REVIEW_APPLY_SCRIPT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = summarize_runtime_integration_readiness(
        phase_status_path=args.phase_status,
        app_config_path=args.app_config,
        runtime_readiness_path=args.runtime_readiness,
        lean_payload_readiness_path=args.lean_payload_readiness,
        full_payload_readiness_path=args.full_payload_readiness,
        manual_review_packet_readiness_path=args.manual_review_packet_readiness,
        canonical_facet_readiness_path=args.canonical_facet_readiness,
        manual_review_apply_script_path=args.manual_review_apply_script,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
