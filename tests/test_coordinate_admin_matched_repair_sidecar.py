import csv
import json

from scripts.build_coordinate_admin_matched_repair_sidecar import (
    build_coordinate_admin_matched_repair_sidecar,
)


def write_rows(path, rows):
    fieldnames = [
        "recommended_action",
        "recommendation_reason",
        "canonical_event_id",
        "event_id",
        "source_name",
        "source_row_number",
        "source_native_id",
        "date",
        "location_raw",
        "country",
        "declared_admin",
        "coordinate_source",
        "location_precision",
        "old_lat",
        "old_lon",
        "new_lat",
        "new_lon",
        "geonames_name",
        "geonames_id",
        "geonames_feature_class",
        "geonames_feature_code",
        "geonames_admin1",
        "distance_km",
        "current_inside_declared_admin_bounds",
        "geonames_inside_declared_admin_bounds",
        "suggested_preview_repair_action",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def repair_row(**overrides):
    row = {
        "recommended_action": "preview_repair_candidate",
        "recommendation_reason": "current_outside_admin_bounds_geonames_inside_admin_bounds",
        "canonical_event_id": "evt_au_1",
        "event_id": "",
        "source_name": "ufocat",
        "source_row_number": "230637",
        "source_native_id": "259876",
        "date": "2008-06-20",
        "location_raw": "GERALDTON, WAU, AU",
        "country": "Australia",
        "declared_admin": "08",
        "coordinate_source": "source_coordinates",
        "location_precision": "coordinate",
        "old_lat": "-28.78",
        "old_lon": "144.6",
        "new_lat": "-28.77897",
        "new_lon": "114.61459",
        "geonames_name": "Geraldton",
        "geonames_id": "2070998",
        "geonames_feature_class": "P",
        "geonames_feature_code": "PPLA2",
        "geonames_admin1": "08",
        "distance_km": "2914.494",
        "current_inside_declared_admin_bounds": "False",
        "geonames_inside_declared_admin_bounds": "True",
        "suggested_preview_repair_action": "replace_with_same_australian_admin_geonames_feature",
    }
    row.update(overrides)
    return row


def run_sidecar(tmp_path, rows):
    input_csv = tmp_path / "candidates.csv"
    json_output = tmp_path / "sidecar.json"
    csv_output = tmp_path / "sidecar.csv"
    write_rows(input_csv, rows)
    report = build_coordinate_admin_matched_repair_sidecar(
        input_csv=input_csv,
        json_output=json_output,
        csv_output=csv_output,
    )
    csv_rows = list(csv.DictReader(csv_output.open("r", encoding="utf-8", newline="")))
    json_doc = json.loads(json_output.read_text(encoding="utf-8"))
    return report, json_doc, csv_rows


def test_sidecar_emits_only_preview_repair_candidates(tmp_path):
    report, json_doc, csv_rows = run_sidecar(
        tmp_path,
        [
            repair_row(),
            repair_row(
                recommended_action="manual_review_only",
                canonical_event_id="evt_manual",
                recommendation_reason="current_coordinate_inside_declared_admin_bounds",
            ),
        ],
    )

    assert report["input_row_count"] == 2
    assert report["proposed_patch_count"] == 1
    assert json_doc["proposed_patches"][0]["canonical_event_id"] == "evt_au_1"
    assert len(csv_rows) == 1
    assert csv_rows[0]["canonical_event_id"] == "evt_au_1"


def test_sidecar_preserves_original_coordinate_metadata_and_proposes_geonames_fields(tmp_path):
    report, json_doc, _ = run_sidecar(tmp_path, [repair_row()])

    patch = json_doc["proposed_patches"][0]
    assert patch["old"]["lat"] == -28.78
    assert patch["old"]["lon"] == 144.6
    assert patch["old"]["coordinate_source"] == "source_coordinates"
    assert patch["new"]["lat"] == -28.77897
    assert patch["new"]["lon"] == 114.61459
    assert patch["set_fields"]["coordinate_source"] == "geocoded"
    assert patch["set_fields"]["location_precision"] == "city"
    assert patch["set_fields"]["admin_coordinate_repair_original_source"] == "source_coordinates"
    assert patch["set_fields"]["admin_coordinate_repair_geoname_id"] == "2070998"
    assert report["canonical_outputs_mutated"] is False
    assert report["preview_outputs_written"] is False


def test_sidecar_uses_mapped_precision_for_non_populated_feature(tmp_path):
    _, json_doc, _ = run_sidecar(
        tmp_path,
        [repair_row(geonames_feature_class="S", geonames_feature_code="HMSD")],
    )

    assert json_doc["proposed_patches"][0]["set_fields"]["location_precision"] == "mapped"


def test_sidecar_rejects_malformed_preview_rows(tmp_path):
    report, json_doc, _ = run_sidecar(
        tmp_path,
        [
            repair_row(canonical_event_id=""),
            repair_row(new_lat="", canonical_event_id="evt_bad_coords"),
            repair_row(
                current_inside_declared_admin_bounds="True",
                canonical_event_id="evt_inside_current",
            ),
        ],
    )

    assert report["proposed_patch_count"] == 0
    assert report["skipped_row_count"] == 3
    assert json_doc["proposed_patches"] == []
