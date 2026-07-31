import pytest

from scripts.build_entity_resolution_cluster_time_norm_shadow_override_subset import (
    build_entity_resolution_cluster_time_norm_shadow_override_subset,
)


def _effect(review_item_id, decision_index):
    return {
        "effect_id": f"effect_{review_item_id}",
        "review_item_id": review_item_id,
        "decision_index": decision_index,
        "planned_effect": "merge_entity_resolution_candidate",
        "merge_canonical_event_ids": [f"evt_{review_item_id}_a", f"evt_{review_item_id}_b"],
    }


def _effects_plan():
    return {
        "effect_policy": "entity_resolution_plan_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "effects": [
            _effect("ready", 1),
            _effect("eligible_time", 2),
            _effect("fuzzy_time", 3),
            _effect("distinct_time", 4),
            _effect("already_selected", 5),
            _effect("mixed_source_time", 6),
        ],
    }


def _base_subset():
    return {
        "effect_policy": "entity_resolution_plan_only",
        "subset_policy": "entity_resolution_shadow_preview_subset_with_analysis_overrides",
        "canonical_outputs_mutated": False,
        "canonical_outputs_mutated_by_plan": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "override_decisions_created": False,
        "effects": [_effect("ready", 1), _effect("already_selected", 5)],
        "excluded_effects": [
            {"review_item_id": "eligible_time", "reason": "blocked_by_merge_readiness_gate"},
            {"review_item_id": "fuzzy_time", "reason": "blocked_by_merge_readiness_gate"},
            {"review_item_id": "distinct_time", "reason": "blocked_by_merge_readiness_gate"},
            {"review_item_id": "mixed_source_time", "reason": "blocked_by_merge_readiness_gate"},
        ],
    }


def _time_item(
    review_item_id,
    classification,
    risk,
    minutes,
    *,
    fuzzy=None,
    ambiguous=None,
    unknown=None,
    source_names=None,
    source_native_ids=None,
    date_values=None,
    location_values=None,
):
    return {
        "review_item_id": review_item_id,
        "effect_id": f"effect_{review_item_id}",
        "time_pattern_classification": classification,
        "review_risk_tier": risk,
        "parsed_minutes": minutes,
        "blocking_fields": ["time_raw"],
        "fuzzy_labels": fuzzy or [],
        "ambiguous_tokens": ambiguous or [],
        "unknown_tokens": unknown or [],
        "time_tokens": [str(minute) for minute in minutes],
        "source_summary": {
            "canonical_event_count": 2,
            "canonical_event_ids": [f"evt_{review_item_id}_a", f"evt_{review_item_id}_b"],
            "source_names": source_names or ["ufocat"],
            "source_native_ids": source_native_ids or [f"native_{review_item_id}"],
            "date_values": date_values or ["1954-09-19"],
            "location_values": location_values or ["RONGERES, FRA"],
        },
    }


def _time_analysis():
    return {
        "analysis_policy": "entity_resolution_cluster_time_normalization_review_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "auto_merge_performed": False,
        "override_decisions_created": False,
        "items": [
            _time_item("eligible_time", "nearby_exact_minutes_15m_or_less", "lower", [600, 605]),
            _time_item("fuzzy_time", "nearby_exact_minutes_15m_or_less", "lower", [600, 605], fuzzy=["daytime"]),
            _time_item("distinct_time", "multiple_distinct_exact_minutes", "high", [600, 800]),
            _time_item("already_selected", "single_exact_minute", "lower", [600]),
            {
                **_time_item("type_blocked_time", "nearby_exact_minutes_15m_or_less", "lower", [600, 605]),
                "blocking_fields": ["time_raw", "type_normalized"],
            },
            _time_item(
                "mixed_source_time",
                "nearby_exact_minutes_15m_or_less",
                "lower",
                [600, 605],
                source_names=["ufocat", "nuforc"],
            ),
        ],
    }


def test_time_norm_shadow_override_subset_adds_only_strict_lower_risk_time_candidates():
    subset = build_entity_resolution_cluster_time_norm_shadow_override_subset(
        effects_plan=_effects_plan(),
        base_subset=_base_subset(),
        time_analysis=_time_analysis(),
    )

    assert subset["subset_policy"] == "entity_resolution_cluster_time_normalization_shadow_preview_subset_v2"
    assert subset["canonical_outputs_mutated"] is False
    assert subset["decision_outputs_created"] is False
    assert subset["base_selected_merge_effect_count"] == 2
    assert subset["time_norm_override_selected_merge_effect_count"] == 1
    assert subset["selected_merge_effect_count"] == 3
    assert subset["excluded_merge_effect_count"] == 3
    assert subset["time_norm_override_review_item_ids"] == ["eligible_time"]
    selected = [effect for effect in subset["effects"] if effect["review_item_id"] == "eligible_time"][0]
    assert selected["shadow_preview_override"] is True
    assert selected["shadow_preview_override_reason"] == "strict_time_normalization_candidate"
    assert subset["time_norm_excluded_reason_counts"] == {
        "already_selected_in_base_subset": 1,
        "has_fuzzy_labels": 1,
        "ineligible_time_pattern_classification": 1,
        "not_time_raw_only_blocker": 1,
        "source_name_not_single": 1,
    }


@pytest.mark.parametrize(
    ("source_summary_patch", "expected_reason"),
    [
        ({"source_native_ids": []}, "source_native_id_not_single"),
        ({"source_native_ids": ["native_a", "native_b"]}, "source_native_id_not_single"),
        ({"date_values": ["1954-09-19", "1954-09-20"]}, "date_value_not_single"),
        ({"location_values": ["RONGERES, FRA", "PARIS, FRA"]}, "location_value_not_single"),
        ({"canonical_event_count": 1}, "insufficient_canonical_event_count"),
    ],
)
def test_time_norm_shadow_override_subset_rejects_non_single_identity_gates(
    source_summary_patch,
    expected_reason,
):
    item = _time_item("eligible_time", "nearby_exact_minutes_15m_or_less", "lower", [600, 605])
    item["source_summary"].update(source_summary_patch)
    time_analysis = {
        "analysis_policy": "entity_resolution_cluster_time_normalization_review_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "auto_merge_performed": False,
        "override_decisions_created": False,
        "items": [item],
    }

    subset = build_entity_resolution_cluster_time_norm_shadow_override_subset(
        effects_plan=_effects_plan(),
        base_subset=_base_subset(),
        time_analysis=time_analysis,
    )

    assert subset["time_norm_override_selected_merge_effect_count"] == 0
    assert subset["time_norm_excluded_reason_counts"] == {expected_reason: 1}


def test_time_norm_shadow_override_subset_rejects_unsafe_time_analysis():
    time_analysis = _time_analysis()
    time_analysis["decisions_created"] = True

    with pytest.raises(ValueError, match="decisions_created"):
        build_entity_resolution_cluster_time_norm_shadow_override_subset(
            effects_plan=_effects_plan(),
            base_subset=_base_subset(),
            time_analysis=time_analysis,
        )


def test_time_norm_shadow_override_subset_rejects_canonical_ready_time_analysis():
    time_analysis = _time_analysis()
    time_analysis["ready_for_canonical_apply"] = True

    with pytest.raises(ValueError, match="ready_for_canonical_apply"):
        build_entity_resolution_cluster_time_norm_shadow_override_subset(
            effects_plan=_effects_plan(),
            base_subset=_base_subset(),
            time_analysis=time_analysis,
        )
