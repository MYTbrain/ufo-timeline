import json

import pytest

from scripts.apply_coordinate_admin_matched_repair_sidecar_preview import (
    apply_coordinate_admin_matched_repair_sidecar_preview,
)


def write_events(path, events):
    path.write_text(
        "\n".join(json.dumps(event, separators=(",", ":")) for event in events) + "\n",
        encoding="utf-8",
    )


def write_sidecar(path, patches):
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "mode": "proposed_patch_sidecar",
                "proposed_patches": patches,
            }
        ),
        encoding="utf-8",
    )


def patch(canonical_event_id="evt_1", old_lat=-28.78, old_lon=144.6, old_source="source_coordinates"):
    return {
        "canonical_event_id": canonical_event_id,
        "old": {
            "lat": old_lat,
            "lon": old_lon,
            "coordinate_source": old_source,
            "location_precision": "coordinate",
        },
        "new": {
            "lat": -28.77897,
            "lon": 114.61459,
        },
        "set_fields": {
            "lat": -28.77897,
            "lon": 114.61459,
            "coordinate_source": "geocoded",
            "location_precision": "city",
            "geocode_query_used": "Geraldton, 08, Australia",
            "geocode_display_name": "Geraldton, 08, Australia",
            "geocode_confidence": 0.9,
            "admin_coordinate_repair_action": "replace_with_same_australian_admin_geonames_feature",
            "admin_coordinate_repair_reason": "current_outside_admin_bounds_geonames_inside_admin_bounds",
            "admin_coordinate_repair_original_lat": old_lat,
            "admin_coordinate_repair_original_lon": old_lon,
            "admin_coordinate_repair_original_source": old_source,
            "admin_coordinate_repair_geoname_id": "2070998",
        },
    }


def run_apply(tmp_path, events, patches):
    input_path = tmp_path / "events.jsonl"
    sidecar_path = tmp_path / "sidecar.json"
    output_dir = tmp_path / "out"
    report_output = tmp_path / "report.json"
    write_events(input_path, events)
    write_sidecar(sidecar_path, patches)
    report = apply_coordinate_admin_matched_repair_sidecar_preview(
        input_path=input_path,
        sidecar_path=sidecar_path,
        output_dir=output_dir,
        report_output=report_output,
    )
    rows = [
        json.loads(line)
        for line in (output_dir / "deduped_events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return report, rows


def test_preview_apply_updates_matching_event_and_preserves_audit_metadata(tmp_path):
    report, rows = run_apply(
        tmp_path,
        [
            {
                "canonical_event_id": "evt_1",
                "lat": -28.78,
                "lon": 144.6,
                "coordinate_source": "source_coordinates",
                "location_precision": "coordinate",
            }
        ],
        [patch()],
    )

    assert report["applied_patch_count"] == 1
    assert rows[0]["lat"] == -28.77897
    assert rows[0]["lon"] == 114.61459
    assert rows[0]["coordinate_source"] == "geocoded"
    assert rows[0]["location_precision"] == "city"
    assert rows[0]["admin_coordinate_repair_original_source"] == "source_coordinates"
    assert "Admin-matched coordinate repair replaced" in rows[0]["mapping_notes"]


def test_preview_apply_skips_event_when_old_coordinate_guard_fails(tmp_path):
    report, rows = run_apply(
        tmp_path,
        [
            {
                "canonical_event_id": "evt_1",
                "lat": -28.78,
                "lon": 114.6,
                "coordinate_source": "source_coordinates",
                "location_precision": "coordinate",
            }
        ],
        [patch()],
    )

    assert report["applied_patch_count"] == 0
    assert report["skipped_patch_count"] == 1
    assert rows[0]["lon"] == 114.6
    assert report["skip_reason_counts"] == {"old_coordinate_guard_failed": 1}


def test_preview_apply_reports_unused_patches(tmp_path):
    report, rows = run_apply(
        tmp_path,
        [
            {
                "canonical_event_id": "evt_other",
                "lat": 0,
                "lon": 0,
                "coordinate_source": "source_coordinates",
            }
        ],
        [patch()],
    )

    assert report["applied_patch_count"] == 0
    assert report["unused_patch_count"] == 1
    assert rows[0]["canonical_event_id"] == "evt_other"


def test_preview_apply_rejects_duplicate_patch_ids(tmp_path):
    input_path = tmp_path / "events.jsonl"
    sidecar_path = tmp_path / "sidecar.json"
    write_events(input_path, [])
    write_sidecar(sidecar_path, [patch(), patch()])

    with pytest.raises(ValueError, match="Duplicate sidecar patch"):
        apply_coordinate_admin_matched_repair_sidecar_preview(
            input_path=input_path,
            sidecar_path=sidecar_path,
            output_dir=tmp_path / "out",
            report_output=tmp_path / "report.json",
        )
