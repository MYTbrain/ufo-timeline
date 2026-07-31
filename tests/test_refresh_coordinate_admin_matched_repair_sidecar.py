import json

from scripts.refresh_coordinate_admin_matched_repair_sidecar import (
    refresh_coordinate_admin_matched_repair_sidecar,
)


def write_jsonl(path, rows):
    path.write_text(
        "\n".join(json.dumps(row, separators=(",", ":")) for row in rows) + "\n",
        encoding="utf-8",
    )


def write_sidecar(path, patches):
    path.write_text(
        json.dumps({"schema_version": 1, "proposed_patches": patches}),
        encoding="utf-8",
    )


def patch(canonical_event_id="evt_1"):
    return {
        "canonical_event_id": canonical_event_id,
        "source_name": "ufocat",
        "source_row_number": "230637",
        "source_native_id": "259876",
        "date": "2008-06-20",
        "location_raw": "GERALDTON, WAU, AU",
        "country": "Australia",
        "declared_admin": "08",
        "old": {
            "lat": -28.78,
            "lon": 144.6,
            "coordinate_source": "source_coordinates",
            "location_precision": "coordinate",
        },
        "new": {
            "lat": -28.77897,
            "lon": 114.61459,
            "coordinate_source": "geocoded",
            "location_precision": "city",
            "geonames_name": "Geraldton",
            "geonames_id": "2070998",
            "geonames_feature_class": "P",
            "geonames_feature_code": "PPLA2",
            "geonames_admin1": "08",
        },
        "set_fields": {
            "lat": -28.77897,
            "lon": 114.61459,
            "coordinate_source": "geocoded",
            "location_precision": "city",
            "admin_coordinate_repair_action": "replace_with_same_australian_admin_geonames_feature",
            "admin_coordinate_repair_reason": "current_outside_admin_bounds_geonames_inside_admin_bounds",
            "admin_coordinate_repair_original_lat": -28.78,
            "admin_coordinate_repair_original_lon": 144.6,
            "admin_coordinate_repair_original_source": "source_coordinates",
        },
        "audit": {
            "distance_km": 2914.494,
            "current_inside_declared_admin_bounds": False,
            "geonames_inside_declared_admin_bounds": True,
        },
    }


def run_refresh(tmp_path, events, patches):
    corpus = tmp_path / "events.jsonl"
    sidecar = tmp_path / "sidecar.json"
    json_output = tmp_path / "refreshed.json"
    csv_output = tmp_path / "refreshed.csv"
    write_jsonl(corpus, events)
    write_sidecar(sidecar, patches)
    report = refresh_coordinate_admin_matched_repair_sidecar(
        corpus_path=corpus,
        sidecar_path=sidecar,
        json_output=json_output,
        csv_output=csv_output,
    )
    refreshed = json.loads(json_output.read_text(encoding="utf-8"))
    return report, refreshed


def test_refresh_updates_old_guard_from_current_corpus_when_still_safe(tmp_path):
    report, refreshed = run_refresh(
        tmp_path,
        [
            {
                "canonical_event_id": "evt_1",
                "lat": -28.78,
                "lon": -144.6,
                "coordinate_source": "source_coordinates",
                "location_precision": "coordinate",
            }
        ],
        [patch()],
    )

    assert report["refreshed_patch_count"] == 1
    next_patch = refreshed["proposed_patches"][0]
    assert next_patch["old"]["lon"] == -144.6
    assert next_patch["set_fields"]["admin_coordinate_repair_original_lon"] == -144.6
    assert next_patch["audit"]["refreshed_from_corpus"] is True


def test_refresh_skips_when_current_coordinate_is_now_inside_declared_admin(tmp_path):
    report, refreshed = run_refresh(
        tmp_path,
        [
            {
                "canonical_event_id": "evt_1",
                "lat": -28.78,
                "lon": 114.6,
                "coordinate_source": "source_coordinates",
            }
        ],
        [patch()],
    )

    assert report["refreshed_patch_count"] == 0
    assert report["skip_reason_counts"] == {"current_coordinate_inside_declared_admin_bounds": 1}
    assert refreshed["proposed_patches"] == []


def test_refresh_skips_when_target_event_missing(tmp_path):
    report, _ = run_refresh(tmp_path, [], [patch()])

    assert report["refreshed_patch_count"] == 0
    assert report["skip_reason_counts"] == {"target_event_not_found": 1}
