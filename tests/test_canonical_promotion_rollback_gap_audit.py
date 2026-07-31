from scripts.build_canonical_promotion_rollback_gap_audit import (
    build_canonical_promotion_rollback_gap_audit,
)


def test_canonical_promotion_rollback_gap_audit_is_report_only_and_records_deltas():
    audit = build_canonical_promotion_rollback_gap_audit(
        app_config={
            "canonicalWebArtifacts": {
                "enabled": False,
                "primaryCatalog": False,
                "traceRuntime": False,
                "filteredTraceAggregation": False,
            }
        },
        readiness_gate={
            "status": "preview_ready_default_blocked",
            "promotion_blockers": ["not promoted"],
        },
        decision_packet={
            "evidence": {
                "static_config_full_sidecar_smoke": "passed",
                "full_sidecar_trace_rows": 286582,
            }
        },
        lean_payload_readiness={
            "status": "ready",
            "mode": "primary-catalog-trace-runtime",
            "counts": {"files": 212, "summary_shards": 95, "event_chunks": 0, "gzip_bytes": 78444983},
            "checks": {"default_app_config_canonical_disabled": True},
        },
        full_payload_readiness={
            "status": "ready",
            "mode": "primary-catalog-trace-runtime-with-details",
            "counts": {"files": 968, "summary_shards": 95, "event_chunks": 378, "gzip_bytes": 425104204},
            "checks": {"default_app_config_canonical_disabled": True},
        },
    )

    assert audit["audit_policy"] == "canonical_promotion_rollback_gap_audit_report_only"
    assert audit["canonical_outputs_mutated"] is False
    assert audit["default_runtime_config_changed"] is False
    assert audit["ready_for_default_promotion"] is False
    assert audit["flag_deltas"]["enabled"] == {"current": False, "candidate": True, "would_change": True}
    assert audit["sidecar_payloads"]["lean_primary_trace_payload"]["files"] == 212
    assert audit["sidecar_payloads"]["full_detail_primary_trace_payload"]["event_chunks"] == 378
    assert audit["smoke_evidence"]["full_sidecar_trace_rows"] == 286582
    assert "static_bundle/data/app_config.json" in audit["config_only_files_that_would_change_if_approved"]


def test_canonical_promotion_rollback_gap_audit_reports_promoted_runtime():
    audit = build_canonical_promotion_rollback_gap_audit(
        app_config={
            "canonicalWebArtifacts": {
                "enabled": True,
                "primaryCatalog": True,
                "traceRuntime": True,
                "filteredTraceAggregation": True,
            }
        },
        readiness_gate={
            "status": "default_promoted_ready",
            "ready_for_default_promotion": True,
            "promotion_blockers": [],
        },
        decision_packet={"evidence": {}},
        lean_payload_readiness={"status": "ready", "counts": {}, "checks": {}},
        full_payload_readiness={"status": "ready", "counts": {}, "checks": {}},
    )

    assert audit["default_runtime_config_changed"] is True
    assert audit["default_runtime_config_promoted"] is True
    assert audit["ready_for_default_promotion"] is True
    assert audit["flag_deltas"]["enabled"] == {"current": True, "candidate": True, "would_change": False}
