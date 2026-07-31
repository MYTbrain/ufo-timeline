"""Build a no-mutation contract for promoting a preview corpus to canonical.

The contract is deliberately report-only. It records exactly which sidecar
would become canonical, how many rows would be replaced, and which approval
evidence supports the promotion. It does not overwrite canonical outputs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_CANONICAL_EVENTS = Path("data/canonical_full/deduped_events.jsonl")
DEFAULT_PROMOTED_PREVIEW_EVENTS = Path("data/canonical_preview_remaining_lower_time_format_apply/deduped_events.jsonl")
DEFAULT_BASE_PREVIEW_EVENTS = Path("data/canonical_time_norm_plus_manual_review_ai_low_risk_plus_medium_time_preview/deduped_events.jsonl")
DEFAULT_ACCEPTANCE_REPORT = Path("data/reports/entity_resolution_remaining_lower_time_format_acceptance_report.json")
DEFAULT_PREVIEW_APPLY_REPORT = Path("data/reports/entity_resolution_remaining_lower_time_format_preview_apply_report.json")
DEFAULT_RUNTIME_READINESS = Path("data/reports/canonical_web_runtime_readiness.json")
DEFAULT_STATIC_PAYLOAD_READINESS = Path("data/reports/canonical_web_static_payload_promoted_readiness.json")
DEFAULT_OUTPUT_JSON = Path("data/reports/canonical_mutation_contract.json")
DEFAULT_OUTPUT_MD = Path("data/reports/canonical_mutation_contract.md")


def build_canonical_mutation_contract(
    *,
    canonical_events: Path,
    promoted_preview_events: Path,
    base_preview_events: Path,
    acceptance_report: dict[str, Any],
    preview_apply_report: dict[str, Any],
    runtime_readiness: dict[str, Any],
    static_payload_readiness: dict[str, Any],
    output_json: Path,
    output_md: Path,
) -> dict[str, Any]:
    canonical_count = count_lines(canonical_events)
    promoted_preview_count = count_lines(promoted_preview_events)
    base_preview_count = count_lines(base_preview_events)

    accepted_decision_count = int(acceptance_report.get("accepted_decision_count") or 0)
    applied_effect_count = int(preview_apply_report.get("effects_applied") or 0)
    latest_projected_reduction = int(preview_apply_report.get("projected_event_reduction") or 0)
    whole_chain_reduction = canonical_count - promoted_preview_count
    base_to_promoted_reduction = base_preview_count - promoted_preview_count

    validation_errors: list[str] = []
    if preview_apply_report.get("canonical_outputs_mutated") is not False:
        validation_errors.append("preview_apply_report must declare canonical_outputs_mutated=false")
    if preview_apply_report.get("effects_blocked") not in (0, "0"):
        validation_errors.append("preview apply must have zero blocked effects")
    if accepted_decision_count != applied_effect_count:
        validation_errors.append("accepted decision count must match applied effect count")
    if base_to_promoted_reduction != latest_projected_reduction:
        validation_errors.append("base preview to promoted preview reduction must match latest projected reduction")
    if runtime_readiness.get("ready_for_primary_catalog") is not True:
        validation_errors.append("runtime readiness must be ready_for_primary_catalog")
    if static_payload_readiness.get("status") != "ready":
        validation_errors.append("promoted static payload readiness must be ready")
    config_state = static_payload_readiness.get("config_state") or {}
    if config_state.get("default_app_config_canonical_promoted") is not True:
        validation_errors.append("default app config must be promoted in static payload readiness")

    report = {
        "schema_version": 1,
        "contract_policy": "canonical_full_mutation_contract_report_only",
        "canonical_outputs_mutated": False,
        "ready_for_direct_canonical_overwrite": False,
        "contract_valid": not validation_errors,
        "validation_errors": validation_errors,
        "inputs": {
            "current_canonical_events": str(canonical_events),
            "promoted_preview_events": str(promoted_preview_events),
            "base_preview_events": str(base_preview_events),
            "acceptance_report": str(DEFAULT_ACCEPTANCE_REPORT),
            "preview_apply_report": str(DEFAULT_PREVIEW_APPLY_REPORT),
            "runtime_readiness": str(DEFAULT_RUNTIME_READINESS),
            "static_payload_readiness": str(DEFAULT_STATIC_PAYLOAD_READINESS),
        },
        "counts": {
            "current_canonical_events": canonical_count,
            "base_preview_events": base_preview_count,
            "promoted_preview_events": promoted_preview_count,
            "whole_chain_event_reduction_if_promoted": whole_chain_reduction,
            "latest_remaining_lower_event_reduction": base_to_promoted_reduction,
            "accepted_remaining_lower_decisions": accepted_decision_count,
            "applied_remaining_lower_effects": applied_effect_count,
        },
        "required_promotion_steps": [
            "Create a timestamped backup of data/canonical_full/deduped_events.jsonl before any overwrite.",
            "Replace canonical_full/deduped_events.jsonl only with the exact promoted_preview_events file in this contract.",
            "Write an immutable promotion report with pre/post row counts and file hashes.",
            "Rebuild canonical web artifacts from the promoted canonical_full corpus.",
            "Restage static_bundle/data/canonical_web and refresh static_bundle.zip.",
            "Rerun pytest, runtime readiness, static payload readiness, and promoted browser smoke.",
        ],
        "rollback_steps": [
            "Restore the timestamped backup over data/canonical_full/deduped_events.jsonl.",
            "Rebuild canonical web artifacts from restored canonical_full.",
            "Restage static_bundle/data/canonical_web, refresh static_bundle.zip, and rerun smoke gates.",
        ],
        "notes": [
            "This report intentionally does not mutate canonical outputs.",
            "A direct overwrite would promote the entire sidecar chain, not only the latest six accepted remaining-lower decisions.",
            "The latest accepted remaining-lower lane accounts for 12 of the total event-row reduction from current canonical to promoted preview.",
        ],
        "outputs": {
            "json": str(output_json),
            "markdown": str(output_md),
        },
    }
    return report


def count_lines(path: Path) -> int:
    count = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            count += chunk.count(b"\n")
    return count


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    counts = report["counts"]
    lines = [
        "# Canonical Mutation Contract",
        "",
        "This is a report-only contract for a future canonical corpus promotion. It does not mutate canonical outputs.",
        "",
        "## Status",
        "",
        f"- Contract valid: `{str(report['contract_valid']).lower()}`",
        f"- Ready for direct overwrite: `{str(report['ready_for_direct_canonical_overwrite']).lower()}`",
        f"- Canonical outputs mutated: `{str(report['canonical_outputs_mutated']).lower()}`",
        "",
        "## Counts",
        "",
        f"- Current canonical events: `{counts['current_canonical_events']}`",
        f"- Base preview events: `{counts['base_preview_events']}`",
        f"- Promoted preview events: `{counts['promoted_preview_events']}`",
        f"- Whole-chain reduction if promoted: `{counts['whole_chain_event_reduction_if_promoted']}`",
        f"- Latest remaining-lower reduction: `{counts['latest_remaining_lower_event_reduction']}`",
        f"- Accepted remaining-lower decisions: `{counts['accepted_remaining_lower_decisions']}`",
        "",
        "## Required Promotion Steps",
        "",
    ]
    lines.extend(f"- {step}" for step in report["required_promotion_steps"])
    lines.extend(["", "## Rollback Steps", ""])
    lines.extend(f"- {step}" for step in report["rollback_steps"])
    lines.extend(["", "## Notes", ""])
    lines.extend(f"- {note}" for note in report["notes"])
    if report["validation_errors"]:
        lines.extend(["", "## Validation Errors", ""])
        lines.extend(f"- {error}" for error in report["validation_errors"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical-events", type=Path, default=DEFAULT_CANONICAL_EVENTS)
    parser.add_argument("--promoted-preview-events", type=Path, default=DEFAULT_PROMOTED_PREVIEW_EVENTS)
    parser.add_argument("--base-preview-events", type=Path, default=DEFAULT_BASE_PREVIEW_EVENTS)
    parser.add_argument("--acceptance-report", type=Path, default=DEFAULT_ACCEPTANCE_REPORT)
    parser.add_argument("--preview-apply-report", type=Path, default=DEFAULT_PREVIEW_APPLY_REPORT)
    parser.add_argument("--runtime-readiness", type=Path, default=DEFAULT_RUNTIME_READINESS)
    parser.add_argument("--static-payload-readiness", type=Path, default=DEFAULT_STATIC_PAYLOAD_READINESS)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    args = parser.parse_args()

    report = build_canonical_mutation_contract(
        canonical_events=args.canonical_events,
        promoted_preview_events=args.promoted_preview_events,
        base_preview_events=args.base_preview_events,
        acceptance_report=read_json(args.acceptance_report),
        preview_apply_report=read_json(args.preview_apply_report),
        runtime_readiness=read_json(args.runtime_readiness),
        static_payload_readiness=read_json(args.static_payload_readiness),
        output_json=args.output_json,
        output_md=args.output_md,
    )
    write_json(args.output_json, report)
    write_markdown(args.output_md, report)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
