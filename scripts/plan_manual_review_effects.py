"""Plan explicit effects for already-ingested manual review decisions.

This is intentionally non-destructive. It converts record-only decisions from
manual_review_applied_decisions.jsonl into a reviewable effect plan without
rewriting canonical event, normalized event, or web runtime artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


DEFAULT_QUEUE_PATH = Path("data/canonical/manual_review_queue.jsonl")
DEFAULT_APPLIED_DECISIONS_PATH = Path("data/canonical/manual_review_applied_decisions.jsonl")
DEFAULT_OUTPUT_PATH = Path("data/reports/manual_review_effects_plan.json")
UNKNOWN_TOKENS = {"", "unknown", "unk", "n/a", "na", "none", "null", "-"}
WHITESPACE_RE = re.compile(r"\s+")


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--queue",
        default=str(DEFAULT_QUEUE_PATH),
        help="Path to manual_review_queue.jsonl.",
    )
    parser.add_argument(
        "--applied-decisions",
        default=str(DEFAULT_APPLIED_DECISIONS_PATH),
        help="Path to manual_review_applied_decisions.jsonl.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help="Path for the plan-only manual review effects report.",
    )
    return parser


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"JSONL input not found: {path.resolve()}")

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


def write_json(path: Path, payload: Any, *, indent: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=indent)


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = WHITESPACE_RE.sub(" ", str(value).replace("\\n", " ").replace("\\,", ",")).strip()
    if text.lower() in UNKNOWN_TOKENS:
        return None
    return text or None


def stable_hash(payload: Any, *, prefix: str = "", length: int = 20) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha1(serialized.encode("utf-8", "replace")).hexdigest()[:length]
    return f"{prefix}{digest}" if prefix else digest


def build_manual_review_effects_plan(
    *,
    queue: list[dict[str, Any]],
    applied_decisions: list[dict[str, Any]],
    queue_path: Path | None = None,
    applied_decisions_path: Path | None = None,
) -> dict[str, Any]:
    queue_by_id = {
        clean_text(item.get("review_item_id")): item
        for item in queue
        if clean_text(item.get("review_item_id"))
    }

    effects: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    seen_review_item_ids: set[str] = set()

    for decision_index, applied_decision in enumerate(applied_decisions, start=1):
        review_item_id = clean_text(applied_decision.get("review_item_id"))
        if not review_item_id:
            warnings.append(
                {
                    "decision_index": decision_index,
                    "warning": "missing_review_item_id",
                }
            )
            continue

        if review_item_id in seen_review_item_ids:
            warnings.append(
                {
                    "decision_index": decision_index,
                    "review_item_id": review_item_id,
                    "warning": "duplicate_applied_decision_skipped",
                }
            )
            continue
        seen_review_item_ids.add(review_item_id)

        queue_item = queue_by_id.get(review_item_id)
        if queue_item is None:
            warnings.append(
                {
                    "decision_index": decision_index,
                    "review_item_id": review_item_id,
                    "warning": "applied_decision_missing_from_queue",
                }
            )
            effects.append(finalize_effect(plan_unknown_queue_effect(applied_decision, decision_index=decision_index)))
            continue

        effects.append(
            finalize_effect(
                plan_effect_for_applied_decision(
                    applied_decision,
                    queue_item=queue_item,
                    decision_index=decision_index,
                )
            )
        )

    return {
        "schema_version": 1,
        "effect_policy": "plan_only",
        "canonical_outputs_mutated": False,
        "canonical_outputs_mutated_by_plan": False,
        "inputs": {
            "queue_path": str(queue_path.resolve()) if queue_path is not None else None,
            "applied_decisions_path": str(applied_decisions_path.resolve())
            if applied_decisions_path is not None
            else None,
        },
        "queue_item_count": len(queue),
        "applied_decision_count": len(applied_decisions),
        "planned_effect_count": len(effects),
        "effect_counts": count_by(effects, "planned_effect"),
        "decision_counts": count_by(effects, "decision"),
        "review_type_counts": count_by(effects, "review_type"),
        "action_class_counts": count_by(effects, "action_class"),
        "warnings": warnings,
        "safety_notes": [
            "This report is a plan-only artifact.",
            "No canonical event, normalized event, source row, or web runtime output is mutated.",
            "Merge and exclusion effects require a separate explicit apply step with dedicated tests.",
        ],
        "effects": effects,
    }


def plan_unknown_queue_effect(applied_decision: dict[str, Any], *, decision_index: int) -> dict[str, Any]:
    return {
        **base_effect(applied_decision, queue_item={}, decision_index=decision_index),
        "review_type": clean_text(applied_decision.get("review_type")) or "unknown",
        "planned_effect": "blocked_unknown_review_item",
        "action_class": "blocked",
        "requires_explicit_apply_step": False,
        "reason": "Applied decision could not be matched back to manual_review_queue.jsonl.",
    }


def plan_effect_for_applied_decision(
    applied_decision: dict[str, Any],
    *,
    queue_item: dict[str, Any],
    decision_index: int,
) -> dict[str, Any]:
    review_type = clean_text(queue_item.get("review_type"))
    decision = clean_text(applied_decision.get("decision"))
    effect = base_effect(applied_decision, queue_item=queue_item, decision_index=decision_index)

    if review_type == "duplicate_candidate":
        return plan_duplicate_candidate_effect(effect, applied_decision, queue_item, decision)
    if review_type == "row_shape_anomaly":
        return plan_row_shape_anomaly_effect(effect, applied_decision, queue_item, decision)
    if review_type == "unmapped_headers":
        return plan_unmapped_headers_effect(effect, queue_item, decision)
    if review_type == "import_failure":
        return plan_import_failure_effect(effect, queue_item, decision)

    effect.update(
        {
            "planned_effect": "manual_review_decision_unmapped",
            "action_class": "unknown",
            "requires_explicit_apply_step": False,
            "reason": "No planner mapping exists for this review_type.",
        }
    )
    return effect


def base_effect(
    applied_decision: dict[str, Any],
    *,
    queue_item: dict[str, Any],
    decision_index: int,
) -> dict[str, Any]:
    review_item_id = clean_text(applied_decision.get("review_item_id")) or clean_text(
        queue_item.get("review_item_id")
    )
    review_type = clean_text(queue_item.get("review_type")) or clean_text(applied_decision.get("review_type"))
    decision = clean_text(applied_decision.get("decision"))
    effect: dict[str, Any] = {
        "decision_index": decision_index,
        "review_item_id": review_item_id,
        "review_type": review_type,
        "decision": decision,
        "effect_status": "planned_not_applied",
        "effect_policy": "plan_only",
        "canonical_outputs_mutated": False,
    }
    for optional_field in ("reviewer", "reviewed_at", "notes"):
        value = clean_text(applied_decision.get(optional_field))
        if value:
            effect[optional_field] = value
    return effect


def plan_duplicate_candidate_effect(
    effect: dict[str, Any],
    applied_decision: dict[str, Any],
    queue_item: dict[str, Any],
    decision: str,
) -> dict[str, Any]:
    candidate = queue_item.get("candidate") if isinstance(queue_item.get("candidate"), dict) else {}
    effect.update(candidate_summary(candidate))

    if decision == "same_event":
        replacement_id = clean_text(applied_decision.get("replacement_canonical_event_id"))
        effect.update(
            {
                "planned_effect": "merge_duplicate_candidate",
                "action_class": "merge",
                "requires_explicit_apply_step": True,
                "reason": "Reviewer marked a bounded fuzzy duplicate candidate as the same event.",
            }
        )
        if replacement_id:
            effect["replacement_canonical_event_id"] = replacement_id
        return effect

    if decision == "distinct_events":
        effect.update(
            {
                "planned_effect": "preserve_distinct_events",
                "action_class": "preserve",
                "requires_explicit_apply_step": False,
                "reason": "Reviewer marked the candidate records as distinct; no merge should be applied.",
            }
        )
        return effect

    if decision == "needs_more_evidence":
        effect.update(
            {
                "planned_effect": "defer_duplicate_candidate",
                "action_class": "defer",
                "requires_explicit_apply_step": False,
                "reason": "Reviewer deferred the candidate pending stronger evidence.",
            }
        )
        return effect

    effect.update(unknown_decision_payload(decision))
    return effect


def plan_row_shape_anomaly_effect(
    effect: dict[str, Any],
    applied_decision: dict[str, Any],
    queue_item: dict[str, Any],
    decision: str,
) -> dict[str, Any]:
    canonical_input_id = clean_text(queue_item.get("canonical_input_id"))
    if canonical_input_id:
        effect["canonical_input_ids"] = [canonical_input_id]
    effect["source_file"] = clean_text(queue_item.get("source_file"))
    effect["source_row_number"] = queue_item.get("source_row_number")
    anomalies = queue_item.get("source_row_anomalies")
    if isinstance(anomalies, list):
        effect["source_row_anomalies"] = [clean_text(item) for item in anomalies if clean_text(item)]

    if decision == "accept_preserved_row":
        effect.update(
            {
                "planned_effect": "preserve_source_row",
                "action_class": "preserve",
                "requires_explicit_apply_step": False,
                "reason": "Reviewer accepted the preserved row as imported.",
            }
        )
        return effect

    if decision == "repair_source_row":
        effect.update(
            {
                "planned_effect": "repair_source_row_upstream",
                "action_class": "repair",
                "requires_explicit_apply_step": False,
                "reason": "Reviewer requested source-row repair before any canonical rebuild.",
            }
        )
        return effect

    if decision == "exclude_source_row":
        excluded_ids = normalized_id_list(applied_decision.get("exclude_canonical_input_ids"))
        if not excluded_ids and canonical_input_id:
            excluded_ids = [canonical_input_id]
        effect.update(
            {
                "planned_effect": "exclude_source_row",
                "action_class": "exclude",
                "canonical_input_ids": excluded_ids,
                "requires_explicit_apply_step": True,
                "reason": "Reviewer requested explicit source-row exclusion from future canonical outputs.",
            }
        )
        return effect

    effect.update(unknown_decision_payload(decision))
    return effect


def plan_unmapped_headers_effect(
    effect: dict[str, Any],
    queue_item: dict[str, Any],
    decision: str,
) -> dict[str, Any]:
    effect["source_file"] = clean_text(queue_item.get("source_file"))
    headers = queue_item.get("unmapped_headers")
    if isinstance(headers, list):
        effect["unmapped_headers"] = [clean_text(item) for item in headers if clean_text(item)]

    mapping = {
        "map_columns": (
            "update_source_column_mapping",
            "mapping",
            "Reviewer requested column mapping updates before rebuild.",
        ),
        "mark_source_specific": (
            "mark_headers_source_specific",
            "mapping",
            "Reviewer classified headers as source-specific provenance.",
        ),
        "ignore_if_empty": (
            "document_ignored_headers",
            "mapping",
            "Reviewer accepted ignoring these headers when empty.",
        ),
    }
    if decision in mapping:
        planned_effect, action_class, reason = mapping[decision]
        effect.update(
            {
                "planned_effect": planned_effect,
                "action_class": action_class,
                "requires_explicit_apply_step": False,
                "reason": reason,
            }
        )
        return effect

    effect.update(unknown_decision_payload(decision))
    return effect


def plan_import_failure_effect(
    effect: dict[str, Any],
    queue_item: dict[str, Any],
    decision: str,
) -> dict[str, Any]:
    failure = queue_item.get("failure") if isinstance(queue_item.get("failure"), dict) else {}
    effect["source_file"] = clean_text(failure.get("file")) or clean_text(queue_item.get("source_file"))
    effect["error_type"] = clean_text(failure.get("error_type"))

    mapping = {
        "fix_adapter": (
            "fix_source_adapter",
            "repair",
            "Reviewer requested source adapter repair before rebuild.",
            False,
        ),
        "fix_source_file": (
            "fix_source_file_upstream",
            "repair",
            "Reviewer requested source file repair before rebuild.",
            False,
        ),
        "exclude_source_file": (
            "exclude_source_file",
            "exclude",
            "Reviewer requested excluding this source file in a future explicit apply step.",
            True,
        ),
    }
    if decision in mapping:
        planned_effect, action_class, reason, requires_apply = mapping[decision]
        effect.update(
            {
                "planned_effect": planned_effect,
                "action_class": action_class,
                "requires_explicit_apply_step": requires_apply,
                "reason": reason,
            }
        )
        return effect

    effect.update(unknown_decision_payload(decision))
    return effect


def candidate_summary(candidate: dict[str, Any]) -> dict[str, Any]:
    ids = normalized_id_list(candidate.get("canonical_input_ids"))
    reasons = candidate.get("reasons")
    summary: dict[str, Any] = {
        "duplicate_candidate_id": clean_text(candidate.get("duplicate_candidate_id")),
        "canonical_input_ids": ids,
        "candidate_score": candidate.get("score"),
        "record_count": len(ids),
    }
    if isinstance(reasons, list):
        summary["candidate_reasons"] = [clean_text(item) for item in reasons if clean_text(item)]
    blocking = candidate.get("blocking")
    if isinstance(blocking, dict):
        summary["blocking"] = {
            key: value
            for key, value in blocking.items()
            if value is not None and clean_text(value) != ""
        }
    return summary


def unknown_decision_payload(decision: str) -> dict[str, Any]:
    return {
        "planned_effect": "manual_review_decision_unmapped",
        "action_class": "unknown",
        "requires_explicit_apply_step": False,
        "reason": f"No planner mapping exists for decision: {decision or 'missing'}",
    }


def finalize_effect(effect: dict[str, Any]) -> dict[str, Any]:
    planned_effect = clean_text(effect.get("planned_effect")) or "unknown"
    effect["effect_type"] = planned_effect
    effect["effect_id"] = stable_hash(
        {
            "review_item_id": clean_text(effect.get("review_item_id")),
            "decision": clean_text(effect.get("decision")),
            "planned_effect": planned_effect,
            "canonical_input_ids": effect.get("canonical_input_ids") or [],
            "source_file": clean_text(effect.get("source_file")),
        },
        prefix="mre_",
        length=24,
    )
    return effect


def normalized_id_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = clean_text(value)
        return [text] if text else []
    if not isinstance(value, list):
        return []
    ids: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = clean_text(item)
        if text and text not in seen:
            ids.append(text)
            seen.add(text)
    return ids


def count_by(records: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        value = clean_text(record.get(key)) or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def main(argv: list[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    queue_path = Path(args.queue)
    applied_decisions_path = Path(args.applied_decisions)
    output_path = Path(args.output)

    plan = build_manual_review_effects_plan(
        queue=read_jsonl(queue_path),
        applied_decisions=read_jsonl(applied_decisions_path),
        queue_path=queue_path,
        applied_decisions_path=applied_decisions_path,
    )
    write_json(output_path, plan, indent=2)
    print(
        json.dumps(
            {
                "output": str(output_path.resolve()),
                "effect_policy": plan["effect_policy"],
                "planned_effect_count": plan["planned_effect_count"],
                "warnings": len(plan["warnings"]),
                "canonical_outputs_mutated": plan["canonical_outputs_mutated"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
