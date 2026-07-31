"""Build a strict time-normalization shadow-preview ER effects subset.

This is preview-only. It extends the current cluster shadow-override subset
with lower-risk time-normalization review cases that pass hard gates. It does
not create decisions, apply canonical changes, or relax readiness globally.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any


DEFAULT_EFFECTS_PLAN = Path("data/reports/entity_resolution_cluster_ai_effects_plan.json")
DEFAULT_BASE_SUBSET = Path("data/reports/entity_resolution_cluster_ai_effects_plan_shadow_override_subset.json")
DEFAULT_TIME_ANALYSIS = Path("data/reports/entity_resolution_cluster_time_normalization_analysis.json")
DEFAULT_OUTPUT = Path("data/reports/entity_resolution_cluster_time_norm_shadow_override_subset.json")

SUBSET_POLICY = "entity_resolution_cluster_time_normalization_shadow_preview_subset_v2"
ELIGIBLE_CLASSIFICATIONS = {
    "single_exact_minute",
    "nearby_exact_minutes_15m_or_less",
}


def build_entity_resolution_cluster_time_norm_shadow_override_subset(
    *,
    effects_plan: dict[str, Any],
    base_subset: dict[str, Any],
    time_analysis: dict[str, Any],
    effects_plan_path: Path | None = None,
    base_subset_path: Path | None = None,
    time_analysis_path: Path | None = None,
) -> dict[str, Any]:
    validate_effects_plan(effects_plan)
    validate_base_subset(base_subset)
    validate_time_analysis(time_analysis)

    source_effects = effects_plan.get("effects") if isinstance(effects_plan.get("effects"), list) else []
    source_by_review_id = {
        clean_text(effect.get("review_item_id")): effect
        for effect in source_effects
        if isinstance(effect, dict) and clean_text(effect.get("review_item_id"))
    }
    baseline_effects = [
        copy.deepcopy(effect)
        for effect in base_subset.get("effects") or []
        if isinstance(effect, dict) and effect.get("planned_effect") == "merge_entity_resolution_candidate"
    ]
    baseline_review_ids = {clean_text(effect.get("review_item_id")) for effect in baseline_effects}

    selected_effects: list[dict[str, Any]] = []
    excluded_time_candidates: list[dict[str, Any]] = []
    not_found_review_item_ids: list[str] = []
    for item in time_analysis.get("items") or []:
        if not isinstance(item, dict):
            continue
        review_item_id = clean_text(item.get("review_item_id"))
        eligible, reason = time_item_is_eligible(item)
        if not review_item_id:
            continue
        if review_item_id in baseline_review_ids:
            excluded_time_candidates.append(excluded_time_candidate(item, reason="already_selected_in_base_subset"))
            continue
        if not eligible:
            excluded_time_candidates.append(excluded_time_candidate(item, reason=reason))
            continue
        source_effect = source_by_review_id.get(review_item_id)
        if not source_effect or source_effect.get("planned_effect") != "merge_entity_resolution_candidate":
            not_found_review_item_ids.append(review_item_id)
            excluded_time_candidates.append(excluded_time_candidate(item, reason="source_merge_effect_not_found"))
            continue
        effect = copy.deepcopy(source_effect)
        effect["shadow_preview_override"] = True
        effect["shadow_preview_override_reason"] = "strict_time_normalization_candidate"
        effect["shadow_preview_override_source"] = {
            "analysis_policy": time_analysis.get("analysis_policy"),
            "time_pattern_classification": item.get("time_pattern_classification"),
            "review_risk_tier": item.get("review_risk_tier"),
            "parsed_minutes": item.get("parsed_minutes") or [],
            "time_tokens": item.get("time_tokens") or [],
            "hard_gates": {
                "eligible_classification": True,
                "lower_risk_tier": True,
                "no_fuzzy_ambiguous_or_unknown_tokens": True,
                "span_minutes_at_or_below": 15,
                "single_source_name": True,
                "single_source_native_id": True,
                "single_date": True,
                "single_location": True,
                "minimum_canonical_event_count": 2,
            },
        }
        selected_effects.append(effect)

    selected_review_ids = {clean_text(effect.get("review_item_id")) for effect in selected_effects}
    excluded_effects = [
        effect
        for effect in base_subset.get("excluded_effects") or []
        if isinstance(effect, dict) and clean_text(effect.get("review_item_id")) not in selected_review_ids
    ]
    effects = sorted(
        baseline_effects + selected_effects,
        key=lambda effect: int(effect.get("decision_index") or 0),
    )
    return {
        "schema_version": 1,
        "effect_policy": "entity_resolution_plan_only",
        "subset_policy": SUBSET_POLICY,
        "canonical_outputs_mutated": False,
        "canonical_outputs_mutated_by_plan": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "auto_merge_performed": False,
        "override_decisions_created": False,
        "ready_for_canonical_apply": False,
        "inputs": {
            "effects_plan": str(effects_plan_path) if effects_plan_path else None,
            "base_subset": str(base_subset_path) if base_subset_path else None,
            "time_normalization_analysis": str(time_analysis_path) if time_analysis_path else None,
        },
        "selection_policy": {
            "eligible_classifications": sorted(ELIGIBLE_CLASSIFICATIONS),
            "required_review_risk_tier": "lower",
            "allow_fuzzy_labels": False,
            "allow_ambiguous_tokens": False,
            "allow_unknown_tokens": False,
            "max_exact_minute_span": 15,
            "required_source_name_count": 1,
            "required_source_native_id_count": 1,
            "required_date_value_count": 1,
            "required_location_value_count": 1,
            "minimum_canonical_event_count": 2,
        },
        "source_effect_count": len(source_effects),
        "base_selected_merge_effect_count": len(baseline_effects),
        "time_analysis_item_count": len(
            [item for item in time_analysis.get("items") or [] if isinstance(item, dict)]
        ),
        "time_norm_override_selected_merge_effect_count": len(selected_effects),
        "selected_merge_effect_count": len(effects),
        "excluded_merge_effect_count": len(excluded_effects),
        "time_norm_override_review_item_ids": sorted(selected_review_ids),
        "time_norm_override_not_found_review_item_ids": sorted(not_found_review_item_ids),
        "time_norm_excluded_candidate_count": len(excluded_time_candidates),
        "time_norm_excluded_reason_counts": count_excluded_reasons(excluded_time_candidates),
        "time_norm_excluded_candidates_sample": excluded_time_candidates[:100],
        "excluded_effects": excluded_effects,
        "effects": effects,
        "safety_notes": [
            "This subset is intended for shadow preview only.",
            "Only lower-risk time-normalization cases with exact-minute evidence and no fuzzy/ambiguous/unknown tokens are included.",
            "No accepted ER decisions are created by this step.",
            "Canonical outputs are not mutated by this step.",
        ],
    }


def time_item_is_eligible(item: dict[str, Any]) -> tuple[bool, str]:
    classification = clean_text(item.get("time_pattern_classification"))
    risk_tier = clean_text(item.get("review_risk_tier"))
    parsed_minutes = numeric_list(item.get("parsed_minutes"))
    source_summary = item.get("source_summary") if isinstance(item.get("source_summary"), dict) else {}
    if classification not in ELIGIBLE_CLASSIFICATIONS:
        return False, "ineligible_time_pattern_classification"
    if risk_tier != "lower":
        return False, "not_lower_risk_tier"
    if set(string_list(item.get("blocking_fields"))) != {"time_raw"}:
        return False, "not_time_raw_only_blocker"
    if string_list(item.get("fuzzy_labels")):
        return False, "has_fuzzy_labels"
    if string_list(item.get("ambiguous_tokens")):
        return False, "has_ambiguous_tokens"
    if string_list(item.get("unknown_tokens")):
        return False, "has_unknown_tokens"
    if not parsed_minutes:
        return False, "missing_parsed_minutes"
    if max(parsed_minutes) - min(parsed_minutes) > 15:
        return False, "exact_minute_span_over_15"
    if len(string_list(source_summary.get("source_names"))) != 1:
        return False, "source_name_not_single"
    if len(string_list(source_summary.get("source_native_ids"))) != 1:
        return False, "source_native_id_not_single"
    if len(string_list(source_summary.get("date_values"))) != 1:
        return False, "date_value_not_single"
    if len(string_list(source_summary.get("location_values"))) != 1:
        return False, "location_value_not_single"
    if source_canonical_event_count(source_summary) < 2:
        return False, "insufficient_canonical_event_count"
    return True, "eligible"


def excluded_time_candidate(item: dict[str, Any], *, reason: str) -> dict[str, Any]:
    return {
        "review_item_id": clean_text(item.get("review_item_id")),
        "effect_id": clean_text(item.get("effect_id")),
        "reason": reason,
        "time_pattern_classification": clean_text(item.get("time_pattern_classification")),
        "review_risk_tier": clean_text(item.get("review_risk_tier")),
        "projected_event_reduction": as_int(item.get("projected_event_reduction")) or 0,
        "time_tokens": string_list(item.get("time_tokens")),
        "parsed_minutes": numeric_list(item.get("parsed_minutes")),
        "source_summary": item.get("source_summary") if isinstance(item.get("source_summary"), dict) else {},
    }


def validate_effects_plan(effects_plan: dict[str, Any]) -> None:
    errors: list[str] = []
    if effects_plan.get("effect_policy") != "entity_resolution_plan_only":
        errors.append("effect_policy must be 'entity_resolution_plan_only'")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "auto_merge_performed"):
        if effects_plan.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError(f"effects plan is not safe for time-normalization shadow subset: {'; '.join(errors)}")


def validate_base_subset(base_subset: dict[str, Any]) -> None:
    errors: list[str] = []
    if base_subset.get("subset_policy") != "entity_resolution_shadow_preview_subset_with_analysis_overrides":
        errors.append("base subset must use 'entity_resolution_shadow_preview_subset_with_analysis_overrides'")
    if base_subset.get("effect_policy") != "entity_resolution_plan_only":
        errors.append("effect_policy must be 'entity_resolution_plan_only'")
    for flag in (
        "canonical_outputs_mutated",
        "canonical_outputs_mutated_by_plan",
        "preview_outputs_written",
        "auto_merge_performed",
        "override_decisions_created",
    ):
        if base_subset.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError(f"base subset is not safe for time-normalization shadow subset: {'; '.join(errors)}")


def validate_time_analysis(time_analysis: dict[str, Any]) -> None:
    errors: list[str] = []
    if time_analysis.get("analysis_policy") != "entity_resolution_cluster_time_normalization_review_only":
        errors.append("analysis_policy must be 'entity_resolution_cluster_time_normalization_review_only'")
    for flag in (
        "canonical_outputs_mutated",
        "preview_outputs_written",
        "decisions_created",
        "decision_outputs_created",
        "auto_merge_performed",
        "override_decisions_created",
    ):
        if time_analysis.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if time_analysis.get("ready_for_canonical_apply") is True:
        errors.append("ready_for_canonical_apply must not be true")
    if errors:
        raise ValueError(f"time analysis is not safe for time-normalization shadow subset: {'; '.join(errors)}")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [text for item in value if (text := clean_text(item))]
    text = clean_text(value)
    return [text] if text else []


def numeric_list(value: Any) -> list[int]:
    values = value if isinstance(value, list) else []
    output = []
    for item in values:
        try:
            output.append(int(item))
        except (TypeError, ValueError):
            continue
    return sorted(set(output))


def source_canonical_event_count(source_summary: dict[str, Any]) -> int:
    explicit_count = as_int(source_summary.get("canonical_event_count"))
    if explicit_count is not None:
        return explicit_count
    return len(string_list(source_summary.get("canonical_event_ids")))


def as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def count_excluded_reasons(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        reason = clean_text(item.get("reason")) or "unknown"
        counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items()))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--effects-plan", type=Path, default=DEFAULT_EFFECTS_PLAN)
    parser.add_argument("--base-subset", type=Path, default=DEFAULT_BASE_SUBSET)
    parser.add_argument("--time-analysis", type=Path, default=DEFAULT_TIME_ANALYSIS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    subset = build_entity_resolution_cluster_time_norm_shadow_override_subset(
        effects_plan=read_json(args.effects_plan),
        base_subset=read_json(args.base_subset),
        time_analysis=read_json(args.time_analysis),
        effects_plan_path=args.effects_plan,
        base_subset_path=args.base_subset,
        time_analysis_path=args.time_analysis,
    )
    write_json(args.output, subset)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "subset_policy": subset["subset_policy"],
                "base_selected_merge_effect_count": subset["base_selected_merge_effect_count"],
                "time_norm_override_selected_merge_effect_count": subset["time_norm_override_selected_merge_effect_count"],
                "selected_merge_effect_count": subset["selected_merge_effect_count"],
                "excluded_merge_effect_count": subset["excluded_merge_effect_count"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
