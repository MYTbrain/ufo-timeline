from scripts.build_deferred_work_queue import build_deferred_work_queue


def test_deferred_work_queue_keeps_approval_boundaries_explicit():
    queue = build_deferred_work_queue(
        readiness_gate={"status": "preview_ready_default_blocked"},
        promotion_packet={
            "evidence": {
                "static_config_full_sidecar_smoke": "passed",
                "full_sidecar_trace_rows": 286582,
                "full_sidecar_rendered_segments": 11135,
            }
        },
        rollback_audit={
            "sidecar_payloads": {
                "full_detail_primary_trace_payload": {"gzip_mb": 405.41},
            }
        },
        remaining_lower_check={
            "valid": True,
            "decision_candidate_count": 6,
            "projected_event_reduction": 12,
            "ready_for_canonical_apply": False,
        },
        phase_status={
            "phase_2_progress": {
                "manual_review_ai_after_time_norm_high_coordinate_span_review_items": 37,
                "manual_review_ai_after_time_norm_medium_identity_mixed_review_items": 22,
                "manual_review_ai_after_time_norm_medium_classification_mixed_review_items": 68,
                "manual_review_ai_after_time_norm_medium_body_text_mixed_review_items": 85,
                "high_coordinate_span_triage_digest": True,
                "mixed_medium_review_triage_digest": True,
                "static_host_payload_risk_report": True,
            }
        },
    )

    assert queue["queue_policy"] == "deferred_work_queue_report_only"
    assert queue["canonical_outputs_mutated"] is False
    assert queue["default_runtime_config_changed"] is False
    assert queue["requires_default_runtime_approval"][0]["id"] == "promote_canonical_primary_catalog_trace_runtime"
    assert queue["requires_default_runtime_approval"][0]["evidence"]["trace_rows"] == 286582
    assert queue["requires_canonical_mutation_or_apply_approval"][0]["candidate_count"] == 6
    assert queue["requires_canonical_mutation_or_apply_approval"][0]["ready_for_canonical_apply"] is False
    assert queue["safe_report_only_backlog"][0]["item_count"] == 37
    assert queue["safe_report_only_backlog"][0]["status"] == "completed_report_only"
    assert queue["safe_report_only_backlog"][1]["item_count"] == 175
    assert queue["safe_report_only_backlog"][1]["status"] == "completed_report_only"
    assert queue["safe_report_only_backlog"][2]["status"] == "completed_report_only"


def test_deferred_work_queue_marks_runtime_promotion_complete():
    queue = build_deferred_work_queue(
        readiness_gate={"status": "default_promoted_ready"},
        promotion_packet={"evidence": {}},
        rollback_audit={"sidecar_payloads": {"full_detail_primary_trace_payload": {}}},
        remaining_lower_check={},
        phase_status={},
    )

    assert queue["default_runtime_config_changed"] is True
    assert queue["default_runtime_config_promoted"] is True
    assert queue["requires_default_runtime_approval"][0]["status"] == "completed"
    assert "completed_actions" in queue["requires_default_runtime_approval"][0]
    assert "blocked_actions" not in queue["requires_default_runtime_approval"][0]
