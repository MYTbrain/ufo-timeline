from __future__ import annotations

import json
from pathlib import Path

from scripts.audit_canonical_pipeline_completeness import (
    audit_canonical_pipeline_completeness,
    render_markdown,
)


def test_completeness_audit_reconciles_reviewed_merges_and_coordinates(
    tmp_path: Path,
) -> None:
    canonical_full = tmp_path / "canonical_full"
    canonical_web = tmp_path / "canonical_web"
    (canonical_web / "event_chunks").mkdir(parents=True)
    (canonical_web / "summary_shards").mkdir(parents=True)
    canonical_full.mkdir()

    _write_jsonl(
        canonical_full / "input_event_lookup.jsonl",
        [
            {"canonical_input_id": "cin_a", "canonical_event_id": "evt_keep"},
            {"canonical_input_id": "cin_b", "canonical_event_id": "evt_removed"},
            {"canonical_input_id": "cin_c", "canonical_event_id": "evt_unmapped"},
        ],
    )
    _write_jsonl(
        canonical_full / "deduped_events.jsonl",
        [
            {"canonical_event_id": "evt_keep"},
            {"canonical_event_id": "evt_removed"},
            {"canonical_event_id": "evt_unmapped"},
        ],
    )
    _write_json(
        canonical_web / "event_chunks/chunk_000000.json",
        [
            {
                "event_id": 100,
                "canonical_event_id": "evt_keep",
                "canonical_input_ids": ["cin_a", "cin_b"],
                "reviewed_duplicate_merge": {
                    "preferred_canonical_event_id": "evt_keep",
                    "merged_canonical_event_ids": ["evt_keep", "evt_removed"],
                    "preserved_source_record_count": 2,
                },
            },
            {
                "event_id": 101,
                "canonical_event_id": "evt_unmapped",
                "canonical_input_ids": ["cin_c"],
            },
        ],
    )
    _write_json(
        canonical_web / "summary_shards/summary_000000.json",
        [
            {
                "event_id": 100,
                "has_coordinates": True,
                "lat": 49.7,
                "lon": -95.32,
                "coordinate_source": "raw_latlong",
                "location_precision": "exact_coords",
            },
            {
                "event_id": 101,
                "has_coordinates": False,
                "lat": None,
                "lon": None,
                "coordinate_source": "unresolved",
                "location_precision": "city",
            },
        ],
    )
    _write_json(
        canonical_web / "canonical_web_manifest.json",
        {"counts": {"events": 2, "mapped_events": 1}},
    )
    import_report = tmp_path / "canonical_import_report.json"
    import_failures = tmp_path / "canonical_import_failures.json"
    app_config = tmp_path / "app_config.json"
    _write_json(
        import_report,
        {
            "source_record_count": 3,
            "normalized_event_count": 3,
            "retained_source_files": ["fixture.csv"],
            "skipped_files": [],
        },
    )
    _write_json(import_failures, [])
    _write_json(app_config, {"normalizedCount": 2, "mappedCount": 1})

    report = audit_canonical_pipeline_completeness(
        canonical_full_dir=canonical_full,
        canonical_web_dir=canonical_web,
        expected_events_path=canonical_full / "deduped_events.jsonl",
        import_report_path=import_report,
        import_failures_path=import_failures,
        app_config_path=app_config,
    )

    assert report["status"] == "passed"
    assert report["source_import"]["source_record_count"] == 3
    assert report["normalization_and_deduplication"][
        "reviewed_web_removed_event_shell_count"
    ] == 1
    assert report["canonical_web"]["without_coordinates_count"] == 1
    assert report["identity_reconciliation"][
        "undocumented_expected_not_current_web_count"
    ] == 0
    assert "Status: **PASSED**" in render_markdown(report)


def test_completeness_audit_fails_for_undocumented_missing_identity(
    tmp_path: Path,
) -> None:
    canonical_full = tmp_path / "canonical_full"
    canonical_web = tmp_path / "canonical_web"
    (canonical_web / "event_chunks").mkdir(parents=True)
    (canonical_web / "summary_shards").mkdir(parents=True)
    canonical_full.mkdir()
    _write_jsonl(
        canonical_full / "input_event_lookup.jsonl",
        [{"canonical_input_id": "cin_missing", "canonical_event_id": "evt_missing"}],
    )
    _write_jsonl(
        canonical_full / "deduped_events.jsonl",
        [{"canonical_event_id": "evt_missing"}],
    )
    _write_json(canonical_web / "event_chunks/chunk_000000.json", [])
    _write_json(canonical_web / "summary_shards/summary_000000.json", [])
    _write_json(
        canonical_web / "canonical_web_manifest.json",
        {"counts": {"events": 0, "mapped_events": 0}},
    )
    import_report = tmp_path / "canonical_import_report.json"
    import_failures = tmp_path / "canonical_import_failures.json"
    _write_json(
        import_report,
        {"source_record_count": 1, "normalized_event_count": 1},
    )
    _write_json(import_failures, [])

    report = audit_canonical_pipeline_completeness(
        canonical_full_dir=canonical_full,
        canonical_web_dir=canonical_web,
        expected_events_path=canonical_full / "deduped_events.jsonl",
        import_report_path=import_report,
        import_failures_path=import_failures,
        app_config_path=None,
    )

    assert report["status"] == "failed"
    assert report["identity_reconciliation"][
        "undocumented_expected_not_current_web_count"
    ] == 1
    assert report["checks"][
        "all_missing_canonical_shells_are_documented_reviewed_merges"
    ] is False


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )
