"""Combine accepted time-normalization decision lanes with overlap checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from parser.canonical_schema import clean_text


DEFAULT_CLEAN_ACCEPTED = Path("data/canonical_full/entity_resolution_cluster_time_norm_recommended_accepted_decisions.jsonl")
DEFAULT_SHORTHAND_ACCEPTED = Path(
    "data/canonical_full/entity_resolution_cluster_time_norm_deferred_shorthand_accepted_decisions.jsonl"
)
DEFAULT_LIKELY_TIME_FORMAT_ACCEPTED = Path(
    "data/canonical_full/entity_resolution_cluster_likely_time_format_accepted_decisions.jsonl"
)
DEFAULT_SINGLE_EXACT_CONTEXT_ACCEPTED = Path(
    "data/canonical_full/entity_resolution_single_exact_context_accepted_decisions.jsonl"
)
DEFAULT_OUTPUT = Path("data/canonical_full/entity_resolution_cluster_time_norm_combined_accepted_decisions.jsonl")
DEFAULT_REPORT_OUTPUT = Path("data/reports/entity_resolution_cluster_time_norm_combined_accepted_decisions_report.json")

COMBINE_POLICY = "entity_resolution_time_norm_combined_accepted_decisions_only"
ALLOWED_ACCEPTANCE_POLICIES = {
    "entity_resolution_time_norm_recommended_policy_acceptance_v1",
    "entity_resolution_time_norm_deferred_shorthand_policy_acceptance_v1",
    "entity_resolution_likely_time_format_policy_acceptance_v1",
    "entity_resolution_single_exact_context_policy_acceptance_v1",
}


def combine_time_norm_accepted_decisions(
    *,
    clean_decisions: list[dict[str, Any]],
    shorthand_decisions: list[dict[str, Any]],
    likely_time_format_decisions: list[dict[str, Any]] | None = None,
    single_exact_context_decisions: list[dict[str, Any]] | None = None,
    clean_path: Path | None = None,
    shorthand_path: Path | None = None,
    likely_time_format_path: Path | None = None,
    single_exact_context_path: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    lanes = [
        ("clean_recommended", clean_decisions),
        ("deferred_shorthand", shorthand_decisions),
        ("likely_time_format", likely_time_format_decisions or []),
        ("single_exact_context", single_exact_context_decisions or []),
    ]
    validation_errors: list[dict[str, Any]] = []
    seen_decision_ids: dict[str, str] = {}
    seen_review_item_ids: dict[str, str] = {}
    seen_event_ids: dict[str, str] = {}
    combined: list[dict[str, Any]] = []

    for lane_name, decisions in lanes:
        for index, decision in enumerate(decisions, start=1):
            validation_errors.extend(validate_decision(decision, lane_name=lane_name, index=index))
            decision_id = clean_text(decision.get("entity_resolution_decision_id")) or ""
            review_item_id = clean_text(decision.get("review_item_id")) or ""
            if decision_id:
                if decision_id in seen_decision_ids:
                    validation_errors.append(
                        {
                            "error": "duplicate_entity_resolution_decision_id",
                            "decision_id": decision_id,
                            "first_lane": seen_decision_ids[decision_id],
                            "second_lane": lane_name,
                        }
                    )
                seen_decision_ids[decision_id] = lane_name
            if review_item_id:
                if review_item_id in seen_review_item_ids:
                    validation_errors.append(
                        {
                            "error": "duplicate_review_item_id",
                            "review_item_id": review_item_id,
                            "first_lane": seen_review_item_ids[review_item_id],
                            "second_lane": lane_name,
                        }
                    )
                seen_review_item_ids[review_item_id] = lane_name
            for event_id in string_list(decision.get("merge_canonical_event_ids")):
                if event_id in seen_event_ids:
                    validation_errors.append(
                        {
                            "error": "canonical_event_id_in_multiple_accepted_lanes",
                            "canonical_event_id": event_id,
                            "first_lane": seen_event_ids[event_id],
                            "second_lane": lane_name,
                        }
                    )
                seen_event_ids[event_id] = lane_name
            combined.append(combined_decision(decision, lane_name=lane_name, combined_index=len(combined) + 1))

    if validation_errors:
        raise ValueError("accepted time-normalization lanes are unsafe to combine: " + json.dumps(validation_errors[:5], ensure_ascii=False))

    report = {
        "schema_version": 1,
        "combine_policy": COMBINE_POLICY,
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "canonical_apply_performed": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "inputs": {
            "clean_accepted_decisions": str(clean_path) if clean_path else None,
            "shorthand_accepted_decisions": str(shorthand_path) if shorthand_path else None,
            "likely_time_format_accepted_decisions": str(likely_time_format_path) if likely_time_format_path else None,
            "single_exact_context_accepted_decisions": str(single_exact_context_path) if single_exact_context_path else None,
        },
        "clean_decision_count": len(clean_decisions),
        "shorthand_decision_count": len(shorthand_decisions),
        "likely_time_format_decision_count": len(likely_time_format_decisions or []),
        "single_exact_context_decision_count": len(single_exact_context_decisions or []),
        "combined_decision_count": len(combined),
        "lane_decision_counts": {lane_name: len(decisions) for lane_name, decisions in lanes},
        "unique_review_item_count": len(seen_review_item_ids),
        "unique_merged_event_id_count": len(seen_event_ids),
        "projected_event_reduction": sum(
            max(0, len(string_list(decision.get("merge_canonical_event_ids"))) - 1)
            for decision in combined
        ),
        "validation_error_count": 0,
        "validation_errors": [],
        "notes": [
            "This combines accepted decision artifacts only; it does not apply merges.",
            "The combined lane is safe only if no review items or canonical event IDs overlap across input lanes.",
        ],
    }
    return combined, report


def validate_decision(decision: dict[str, Any], *, lane_name: str, index: int) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    if clean_text(decision.get("decision")) != "same_event":
        errors.append({"error": "decision_must_be_same_event", "lane": lane_name, "index": index})
    if decision.get("accepted_canonical_decision") is not True:
        errors.append({"error": "accepted_canonical_decision_must_be_true", "lane": lane_name, "index": index})
    if clean_text(decision.get("acceptance_policy")) not in ALLOWED_ACCEPTANCE_POLICIES:
        errors.append({"error": "unexpected_acceptance_policy", "lane": lane_name, "index": index})
    if decision.get("canonical_outputs_mutated") is not False:
        errors.append({"error": "canonical_outputs_mutated_must_be_false", "lane": lane_name, "index": index})
    if decision.get("requires_explicit_apply_step") is not True:
        errors.append({"error": "requires_explicit_apply_step_must_be_true", "lane": lane_name, "index": index})
    if len(string_list(decision.get("merge_canonical_event_ids"))) < 2:
        errors.append({"error": "merge_requires_at_least_two_events", "lane": lane_name, "index": index})
    return errors


def combined_decision(decision: dict[str, Any], *, lane_name: str, combined_index: int) -> dict[str, Any]:
    combined = dict(decision)
    combined["combined_decision_index"] = combined_index
    combined["combined_time_norm_lane"] = lane_name
    combined["combine_policy"] = COMBINE_POLICY
    combined["canonical_outputs_mutated"] = False
    return combined


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{path} line {line_number} must be a JSON object.")
            records.append(payload)
    return records


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [text for item in value if (text := clean_text(item))]
    text = clean_text(value)
    return [text] if text else []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean-accepted-decisions", type=Path, default=DEFAULT_CLEAN_ACCEPTED)
    parser.add_argument("--shorthand-accepted-decisions", type=Path, default=DEFAULT_SHORTHAND_ACCEPTED)
    parser.add_argument("--likely-time-format-accepted-decisions", type=Path, default=DEFAULT_LIKELY_TIME_FORMAT_ACCEPTED)
    parser.add_argument("--single-exact-context-accepted-decisions", type=Path, default=DEFAULT_SINGLE_EXACT_CONTEXT_ACCEPTED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    combined, report = combine_time_norm_accepted_decisions(
        clean_decisions=read_jsonl(args.clean_accepted_decisions),
        shorthand_decisions=read_jsonl(args.shorthand_accepted_decisions),
        likely_time_format_decisions=read_jsonl(args.likely_time_format_accepted_decisions),
        single_exact_context_decisions=read_jsonl(args.single_exact_context_accepted_decisions),
        clean_path=args.clean_accepted_decisions,
        shorthand_path=args.shorthand_accepted_decisions,
        likely_time_format_path=args.likely_time_format_accepted_decisions,
        single_exact_context_path=args.single_exact_context_accepted_decisions,
    )
    report["outputs"] = {"combined_decisions": str(args.output), "report": str(args.report_output)}
    write_jsonl(args.output, combined)
    write_json(args.report_output, report)
    print(
        json.dumps(
            {
                "combined_decisions": str(args.output),
                "report": str(args.report_output),
                "combined_decision_count": report["combined_decision_count"],
                "projected_event_reduction": report["projected_event_reduction"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
