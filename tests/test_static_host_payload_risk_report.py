from scripts.build_static_host_payload_risk_report import build_static_host_payload_risk_report


def test_static_host_payload_risk_report_is_report_only_and_flags_full_payload_size():
    report = build_static_host_payload_risk_report(
        lean_payload_readiness={
            "status": "ready",
            "mode": "primary-catalog-trace-runtime",
            "payload_root": "lean",
            "counts": {
                "files": 212,
                "raw_files": 106,
                "gzip_files": 106,
                "summary_shards": 95,
                "event_chunks": 0,
                "raw_bytes": 619018186,
                "gzip_bytes": 78444983,
                "total_bytes": 697463169,
            },
            "checks": {"default_app_config_canonical_disabled": True, "copied_files_exist": True},
        },
        full_payload_readiness={
            "status": "ready",
            "mode": "primary-catalog-trace-runtime-with-details",
            "payload_root": "full",
            "counts": {
                "files": 968,
                "raw_files": 484,
                "gzip_files": 484,
                "summary_shards": 95,
                "event_chunks": 378,
                "raw_bytes": 2238847529,
                "gzip_bytes": 425104204,
                "total_bytes": 2663951733,
            },
            "checks": {"default_app_config_canonical_disabled": True, "copied_files_exist": True},
        },
        rollback_audit={
            "current_gate_status": "preview_ready_default_blocked",
            "default_runtime_config_changed": False,
            "canonical_outputs_mutated": False,
            "ready_for_default_promotion": False,
        },
    )

    assert report["report_policy"] == "static_host_payload_risk_report_only"
    assert report["canonical_outputs_mutated"] is False
    assert report["default_runtime_config_changed"] is False
    assert report["payloads_staged"] is False
    assert report["ready_for_default_promotion"] is False
    assert report["overall_risk"] == "high"
    assert report["larger_payload"] == "full_detail_primary_trace_payload"
    assert report["payloads"]["lean_primary_trace_payload"]["size_risk"] == "moderate"
    assert report["payloads"]["full_detail_primary_trace_payload"]["size_risk"] == "high"
    assert report["payloads"]["full_detail_primary_trace_payload"]["event_chunks"] == 378


def test_static_host_payload_risk_report_reflects_promoted_context():
    report = build_static_host_payload_risk_report(
        lean_payload_readiness={"status": "ready", "counts": {}, "checks": {}},
        full_payload_readiness={"status": "ready", "counts": {"gzip_bytes": 300 * 1024 * 1024}, "checks": {}},
        rollback_audit={
            "current_gate_status": "default_promoted_ready",
            "default_runtime_config_changed": True,
            "canonical_outputs_mutated": False,
            "ready_for_default_promotion": True,
        },
    )

    assert report["default_runtime_config_changed"] is True
    assert report["payloads_staged"] is True
    assert report["ready_for_default_promotion"] is True
