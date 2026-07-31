from scripts.build_canonical_promotion_decision_packet import build_canonical_promotion_decision_packet


def test_canonical_promotion_decision_packet_keeps_decisions_explicit():
    packet = build_canonical_promotion_decision_packet(
        phase_status={
            "phase_2_progress": {
                "entity_resolution_remaining_lower_time_format_candidate_check": {
                    "valid": True,
                    "ready_for_canonical_apply": False,
                },
            },
            "compact_web_artifact_probe": {
                "canonical_static_config_promotion_smoke_full_sidecar": "passed",
                "canonical_primary_trace_aggregation_browser_smoke_full_trace_rows": 286582,
                "canonical_primary_trace_aggregation_browser_smoke_full_rendered_segments": 11135,
            },
            "outputs": {"canonical_primary_promotion_plan": "docs/CANONICAL_PRIMARY_PROMOTION_PLAN.md"},
        },
        readiness_gate={
            "status": "preview_ready_default_blocked",
            "ready_for_preview_package": True,
            "ready_for_default_promotion": False,
            "promotion_blockers": ["canonical primary catalog remains intentionally not promoted"],
        },
    )

    assert packet["packet_policy"] == "canonical_runtime_promotion_decision_packet_report_only"
    assert packet["canonical_outputs_mutated"] is False
    assert packet["default_runtime_config_changed"] is False
    assert packet["ready_for_preview_package"] is True
    assert packet["ready_for_default_promotion"] is False
    assert packet["evidence"]["full_sidecar_trace_rows"] == 286582
    assert packet["evidence"]["remaining_lower_candidate_ready_for_canonical_apply"] is False
    assert [choice["id"] for choice in packet["approval_choices"]] == [
        "approve_default_canonical_runtime",
        "approve_canonical_mutation",
        "defer_and_continue_report_only",
    ]


def test_canonical_promotion_decision_packet_marks_default_promotion_completed():
    packet = build_canonical_promotion_decision_packet(
        phase_status={},
        readiness_gate={
            "status": "default_promoted_ready",
            "ready_for_preview_package": True,
            "ready_for_default_promotion": True,
            "promotion_blockers": [],
        },
    )

    assert packet["default_runtime_config_changed"] is True
    assert packet["default_runtime_config_promoted"] is True
    assert packet["ready_for_default_promotion"] is True
    assert packet["approval_choices"][0]["decision_required"] is False
    assert packet["approval_choices"][0]["status"] == "completed"
