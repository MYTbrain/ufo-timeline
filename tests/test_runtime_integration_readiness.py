from parser.utils import write_json
from scripts.summarize_runtime_integration_readiness import summarize_runtime_integration_readiness


def _write_ready_inputs(tmp_path):
    phase_status = tmp_path / "phase_status.json"
    app_config = tmp_path / "app_config.json"
    runtime_readiness = tmp_path / "runtime_readiness.json"
    lean_payload = tmp_path / "lean_payload.json"
    full_payload = tmp_path / "full_payload.json"
    manual_review_packet = tmp_path / "manual_review_packet_readiness.json"
    canonical_facet_readiness = tmp_path / "canonical_facet_readiness.json"
    apply_script = tmp_path / "apply_manual_review_effects.py"

    write_json(
        phase_status,
        {
            "compact_web_artifact_probe": {
                "canonical_primary_trace_aggregation_browser_smoke": "blocked_headless_browser_exit_code_13",
                "canonical_preview_server_gzip_header_smoke": True,
                "frontend_packed_point_filter_facet_helpers": True,
                "frontend_static_trace_render_metrics": True,
            }
        },
    )
    write_json(
        app_config,
        {
            "canonicalWebArtifacts": {
                "enabled": False,
                "primaryCatalog": False,
                "traceRuntime": False,
                "filteredTraceAggregation": False,
            }
        },
    )
    write_json(
        runtime_readiness,
        {
            "ready_for_startup_preview": True,
            "ready_for_primary_catalog": False,
        },
    )
    write_json(lean_payload, {"status": "ready", "counts": {"files": 212}})
    write_json(full_payload, {"status": "ready", "counts": {"files": 968, "event_chunks": 378, "gzip_bytes": 425104204}})
    write_json(manual_review_packet, {"status": "ready", "counts": {"packet_items": 5001, "csv_rows": 5001}})
    write_json(
        canonical_facet_readiness,
        {
            "status": "ready_with_caveats",
            "facets": {"source": {}, "type": {}, "shape": {}},
            "caveats": ["type has high unknown coverage"],
        },
    )
    apply_script.write_text('parser.add_argument("--mode", choices=["preview"])\ncanonical_outputs_mutated = False\n', encoding="utf-8")
    return {
        "phase_status_path": phase_status,
        "app_config_path": app_config,
        "runtime_readiness_path": runtime_readiness,
        "lean_payload_readiness_path": lean_payload,
        "full_payload_readiness_path": full_payload,
        "manual_review_packet_readiness_path": manual_review_packet,
        "canonical_facet_readiness_path": canonical_facet_readiness,
        "manual_review_apply_script_path": apply_script,
    }


def test_runtime_integration_readiness_reports_preview_ready_but_not_promotable(tmp_path):
    paths = _write_ready_inputs(tmp_path)

    report = summarize_runtime_integration_readiness(**paths)

    assert report["status"] == "preview_ready_default_blocked"
    assert report["ready_for_preview_package"] is True
    assert report["ready_for_default_promotion"] is False
    assert report["failed_checks"] == []
    assert report["counts"]["full_payload_event_chunks"] == 378
    assert report["counts"]["manual_review_packet_items"] == 5001
    assert report["counts"]["canonical_facet_count"] == 3
    assert "browser visual/runtime smoke is still blocked, not passed" in report["promotion_blockers"]


def test_runtime_integration_readiness_accepts_passed_guarded_browser_smoke(tmp_path):
    paths = _write_ready_inputs(tmp_path)
    write_json(
        paths["phase_status_path"],
        {
            "compact_web_artifact_probe": {
                "canonical_primary_trace_aggregation_browser_smoke": "passed_guarded_full_sidecar_fresh_ports",
                "canonical_preview_server_gzip_header_smoke": True,
                "frontend_packed_point_filter_facet_helpers": True,
                "frontend_static_trace_render_metrics": True,
            }
        },
    )

    report = summarize_runtime_integration_readiness(**paths)

    assert report["status"] == "preview_ready_default_blocked"
    assert report["ready_for_preview_package"] is True
    assert report["ready_for_default_promotion"] is False
    assert report["checks"]["browser_smoke_passed_or_explicitly_blocked"] is True
    assert "browser visual/runtime smoke is still blocked, not passed" not in report["promotion_blockers"]
    assert "canonical primary catalog remains intentionally not promoted" in report["promotion_blockers"]


def test_runtime_integration_readiness_blocks_enabled_default_config(tmp_path):
    paths = _write_ready_inputs(tmp_path)
    write_json(
        paths["app_config_path"],
        {
            "canonicalWebArtifacts": {
                "enabled": True,
                "primaryCatalog": False,
                "traceRuntime": False,
                "filteredTraceAggregation": False,
            }
        },
    )

    report = summarize_runtime_integration_readiness(**paths)

    assert report["status"] == "blocked"
    assert report["checks"]["default_canonical_config_valid"] is False
    assert "default_canonical_config_valid" in report["failed_checks"]


def test_runtime_integration_readiness_reports_promoted_default_ready(tmp_path):
    paths = _write_ready_inputs(tmp_path)
    write_json(
        paths["phase_status_path"],
        {
            "compact_web_artifact_probe": {
                "canonical_primary_trace_aggregation_browser_smoke": "passed_guarded_full_sidecar_fresh_ports",
                "canonical_preview_server_gzip_header_smoke": True,
                "frontend_packed_point_filter_facet_helpers": True,
                "frontend_static_trace_render_metrics": True,
            }
        },
    )
    write_json(
        paths["app_config_path"],
        {
            "canonicalWebArtifacts": {
                "enabled": True,
                "primaryCatalog": True,
                "traceRuntime": True,
                "filteredTraceAggregation": True,
            }
        },
    )
    write_json(
        paths["runtime_readiness_path"],
        {
            "ready_for_startup_preview": True,
            "ready_for_primary_catalog": True,
        },
    )

    report = summarize_runtime_integration_readiness(**paths)

    assert report["status"] == "default_promoted_ready"
    assert report["ready_for_preview_package"] is True
    assert report["ready_for_default_promotion"] is True
    assert report["promotion_blockers"] == []


def test_runtime_integration_readiness_requires_preview_only_manual_apply(tmp_path):
    paths = _write_ready_inputs(tmp_path)
    paths["manual_review_apply_script_path"].write_text(
        'parser.add_argument("--mode", choices=["preview", "promote"])\ncanonical_outputs_mutated = True\n',
        encoding="utf-8",
    )

    report = summarize_runtime_integration_readiness(**paths)

    assert report["status"] == "blocked"
    assert report["checks"]["manual_review_mutation_unavailable"] is False
    assert "manual_review_mutation_unavailable" in report["failed_checks"]


def test_runtime_integration_readiness_requires_manual_review_packet_ready(tmp_path):
    paths = _write_ready_inputs(tmp_path)
    write_json(paths["manual_review_packet_readiness_path"], {"status": "blocked", "counts": {"packet_items": 0}})

    report = summarize_runtime_integration_readiness(**paths)

    assert report["status"] == "blocked"
    assert report["checks"]["manual_review_packet_ready"] is False
    assert "manual_review_packet_ready" in report["failed_checks"]


def test_runtime_integration_readiness_requires_facet_readiness_report(tmp_path):
    paths = _write_ready_inputs(tmp_path)
    write_json(paths["canonical_facet_readiness_path"], {"status": "blocked"})

    report = summarize_runtime_integration_readiness(**paths)

    assert report["status"] == "blocked"
    assert report["checks"]["canonical_facet_readiness_available"] is False
    assert "canonical_facet_readiness_available" in report["failed_checks"]
