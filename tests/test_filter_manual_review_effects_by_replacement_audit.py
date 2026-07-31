import csv
import json

from scripts.filter_manual_review_effects_by_replacement_audit import (
    filter_manual_review_effects_by_replacement_audit,
)


def test_filters_merge_effects_to_allowed_replacement_risk_levels(tmp_path):
    audit_csv = tmp_path / "audit.csv"
    candidate = tmp_path / "candidate.jsonl"
    _write_audit_csv(
        audit_csv,
        [
            {"replacement_event_id": "evt_low", "risk_level": "low"},
            {"replacement_event_id": "evt_high", "risk_level": "high"},
        ],
    )
    _write_jsonl(
        candidate,
        [
            _candidate("evt_low", ["mre_keep"]),
            _candidate("evt_high", ["mre_drop"]),
        ],
    )

    output_plan, report = filter_manual_review_effects_by_replacement_audit(
        effects_plan=_effects_plan(),
        replacement_audit_csv_path=audit_csv,
        candidate_events_path=candidate,
        allowed_risk_levels={"low"},
    )

    output_effect_ids = [effect["effect_id"] for effect in output_plan["effects"]]
    assert output_plan["filter_policy"] == "manual_review_effects_filtered_by_replacement_audit_risk_v1"
    assert output_effect_ids == ["mre_keep", "mre_defer"]
    assert output_plan["planned_effect_count"] == 2
    assert report["selected_replacement_count"] == 1
    assert report["selected_merge_effect_count"] == 1
    assert report["excluded_merge_effect_count"] == 1
    assert report["passthrough_non_merge_effect_count"] == 1


def test_filter_can_allow_multiple_risk_levels(tmp_path):
    audit_csv = tmp_path / "audit.csv"
    candidate = tmp_path / "candidate.jsonl"
    _write_audit_csv(
        audit_csv,
        [
            {"replacement_event_id": "evt_low", "risk_level": "low"},
            {"replacement_event_id": "evt_medium", "risk_level": "medium"},
        ],
    )
    _write_jsonl(
        candidate,
        [
            _candidate("evt_low", ["mre_keep"]),
            _candidate("evt_medium", ["mre_medium"]),
        ],
    )

    output_plan, report = filter_manual_review_effects_by_replacement_audit(
        effects_plan=_effects_plan(extra_merge=("mre_medium", ["cin_c", "cin_d"])),
        replacement_audit_csv_path=audit_csv,
        candidate_events_path=candidate,
        allowed_risk_levels={"low", "medium"},
    )

    output_effect_ids = [effect["effect_id"] for effect in output_plan["effects"]]
    assert output_effect_ids == ["mre_keep", "mre_defer", "mre_medium"]
    assert report["selected_merge_effect_count"] == 2


def _effects_plan(extra_merge=None):
    effects = [
        _effect("mre_keep", "merge_duplicate_candidate", ["cin_a", "cin_b"]),
        _effect("mre_drop", "merge_duplicate_candidate", ["cin_x", "cin_y"]),
        _effect("mre_defer", "defer_duplicate_candidate", ["cin_z"]),
    ]
    if extra_merge:
        effects.append(_effect(extra_merge[0], "merge_duplicate_candidate", extra_merge[1]))
    return {
        "effect_policy": "plan_only",
        "canonical_outputs_mutated": False,
        "canonical_outputs_mutated_by_plan": False,
        "planned_effect_count": len(effects),
        "effects": effects,
    }


def _effect(effect_id, planned_effect, input_ids):
    return {
        "effect_id": effect_id,
        "planned_effect": planned_effect,
        "effect_policy": "plan_only",
        "effect_status": "planned_not_applied",
        "canonical_outputs_mutated": False,
        "canonical_input_ids": input_ids,
    }


def _candidate(event_id, effect_ids):
    return {
        "canonical_event_id": event_id,
        "manual_review_preview": {
            "merged_by_effect_ids": effect_ids,
            "merged_canonical_event_ids": [event_id, f"{event_id}_suppressed"],
        },
    }


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _write_audit_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["replacement_event_id", "risk_level"])
        writer.writeheader()
        writer.writerows(rows)
