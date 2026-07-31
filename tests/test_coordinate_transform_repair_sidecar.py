import csv
import json

from scripts.build_coordinate_transform_repair_sidecar import (
    build_coordinate_transform_repair_sidecar,
)


def write_rows(path, rows):
    fieldnames = [
        "recommended_action",
        "recommendation_reason",
        "canonical_event_id",
        "event_id",
        "chunk_id",
        "detail_index",
        "source_name",
        "source_row_number",
        "source_native_id",
        "date",
        "location_raw",
        "country",
        "coordinate_source",
        "location_precision",
        "old_lat",
        "old_lon",
        "transformed_lat",
        "transformed_lon",
        "new_lat",
        "new_lon",
        "transform",
        "original_distance_km",
        "transformed_distance_km",
        "distance_improvement_ratio",
        "geonames_name",
        "geonames_id",
        "geonames_feature_class",
        "geonames_feature_code",
        "geonames_admin1",
        "suggested_preview_repair_action",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def repair_row(**overrides):
    row = {
        "recommended_action": "coordinate_transform_repair_candidate",
        "recommendation_reason": "simple_coordinate_transform_matches_geonames",
        "canonical_event_id": "evt_fr_1",
        "event_id": "",
        "chunk_id": "",
        "detail_index": "",
        "source_name": "ufocat",
        "source_row_number": "156916",
        "source_native_id": "173505",
        "date": "1990-11-05",
        "location_raw": "PEN-MEN, Finistere, FRA, EU",
        "country": "France",
        "coordinate_source": "source_coordinates",
        "location_precision": "coordinate",
        "old_lat": "47.43",
        "old_lon": "3.82",
        "transformed_lat": "47.43",
        "transformed_lon": "-3.82",
        "new_lat": "47.65145",
        "new_lon": "-3.51305",
        "transform": "lon_sign_flip",
        "original_distance_km": "550.793",
        "transformed_distance_km": "33.723",
        "distance_improvement_ratio": "16.333",
        "geonames_name": "Pen Men",
        "geonames_id": "2988085",
        "geonames_feature_class": "T",
        "geonames_feature_code": "PT",
        "geonames_admin1": "53",
        "suggested_preview_repair_action": "replace_with_geonames_after_lon_sign_flip_evidence",
    }
    row.update(overrides)
    return row


def run_sidecar(tmp_path, rows):
    input_csv = tmp_path / "candidates.csv"
    json_output = tmp_path / "sidecar.json"
    csv_output = tmp_path / "sidecar.csv"
    write_rows(input_csv, rows)
    report = build_coordinate_transform_repair_sidecar(
        input_csv=input_csv,
        json_output=json_output,
        csv_output=csv_output,
    )
    csv_rows = list(csv.DictReader(csv_output.open("r", encoding="utf-8", newline="")))
    json_doc = json.loads(json_output.read_text(encoding="utf-8"))
    return report, json_doc, csv_rows


def run_sidecar_with_artifacts(tmp_path, rows, artifact_dir):
    input_csv = tmp_path / "candidates.csv"
    json_output = tmp_path / "sidecar.json"
    csv_output = tmp_path / "sidecar.csv"
    write_rows(input_csv, rows)
    report = build_coordinate_transform_repair_sidecar(
        input_csv=input_csv,
        json_output=json_output,
        csv_output=csv_output,
        artifact_dir=artifact_dir,
    )
    csv_rows = list(csv.DictReader(csv_output.open("r", encoding="utf-8", newline="")))
    json_doc = json.loads(json_output.read_text(encoding="utf-8"))
    return report, json_doc, csv_rows


def test_sidecar_emits_only_transform_repair_candidates(tmp_path):
    report, json_doc, csv_rows = run_sidecar(
        tmp_path,
        [
            repair_row(),
            repair_row(
                recommended_action="manual_review_only",
                canonical_event_id="evt_manual",
            ),
        ],
    )

    assert report["input_row_count"] == 2
    assert report["proposed_patch_count"] == 1
    assert json_doc["proposed_patches"][0]["canonical_event_id"] == "evt_fr_1"
    assert len(csv_rows) == 1
    assert csv_rows[0]["canonical_event_id"] == "evt_fr_1"


def test_sidecar_preserves_original_metadata_and_transform_evidence(tmp_path):
    report, json_doc, _ = run_sidecar(tmp_path, [repair_row()])

    patch = json_doc["proposed_patches"][0]
    assert patch["old"]["lat"] == 47.43
    assert patch["old"]["lon"] == 3.82
    assert patch["old"]["coordinate_source"] == "source_coordinates"
    assert patch["transform_evidence"]["transform"] == "lon_sign_flip"
    assert patch["transform_evidence"]["transformed_distance_km"] == 33.723
    assert patch["new"]["lat"] == 47.65145
    assert patch["new"]["lon"] == -3.51305
    assert patch["set_fields"]["coordinate_source"] == "geocoded"
    assert patch["set_fields"]["location_precision"] == "mapped"
    assert patch["set_fields"]["transform_coordinate_repair_transform"] == "lon_sign_flip"
    assert patch["set_fields"]["transform_coordinate_repair_geoname_id"] == "2988085"
    assert report["canonical_outputs_mutated"] is False
    assert report["preview_outputs_written"] is False


def test_sidecar_uses_city_precision_for_populated_feature(tmp_path):
    _, json_doc, _ = run_sidecar(
        tmp_path,
        [repair_row(geonames_feature_class="P", geonames_feature_code="PPL")],
    )

    assert json_doc["proposed_patches"][0]["set_fields"]["location_precision"] == "city"


def test_sidecar_rejects_malformed_or_weak_transform_rows(tmp_path):
    report, json_doc, _ = run_sidecar(
        tmp_path,
        [
            repair_row(canonical_event_id=""),
            repair_row(new_lat="", canonical_event_id="evt_bad_coords"),
            repair_row(original_distance_km="80", canonical_event_id="evt_too_close"),
            repair_row(transformed_distance_km="60", canonical_event_id="evt_transform_too_far"),
            repair_row(distance_improvement_ratio="2.5", canonical_event_id="evt_low_improvement"),
            repair_row(transform="unsupported", canonical_event_id="evt_bad_transform"),
        ],
    )

    assert report["proposed_patch_count"] == 0
    assert report["skipped_row_count"] == 6
    assert json_doc["proposed_patches"] == []


def test_sidecar_resolves_missing_canonical_id_from_served_chunk_target(tmp_path):
    artifact_dir = write_fixture_artifacts(tmp_path)
    report, json_doc, csv_rows = run_sidecar_with_artifacts(
        tmp_path,
        [
            repair_row(
                canonical_event_id="",
                event_id="101",
                chunk_id="chunk_000000",
                detail_index="0",
                coordinate_source="raw_latlong",
            )
        ],
        artifact_dir,
    )

    assert report["proposed_patch_count"] == 1
    patch = json_doc["proposed_patches"][0]
    assert patch["canonical_event_id"] == "evt_fr_1"
    assert patch["event_id"] == "101"
    assert patch["chunk_id"] == "chunk_000000"
    assert patch["detail_index"] == "0"
    assert csv_rows[0]["canonical_event_id"] == "evt_fr_1"
    assert csv_rows[0]["chunk_id"] == "chunk_000000"


def test_sidecar_rejects_served_chunk_target_when_old_coordinate_guard_is_stale(tmp_path):
    artifact_dir = write_fixture_artifacts(tmp_path, old_lat=47.44)
    report, json_doc, _ = run_sidecar_with_artifacts(
        tmp_path,
        [
            repair_row(
                canonical_event_id="",
                event_id="101",
                chunk_id="chunk_000000",
                detail_index="0",
            )
        ],
        artifact_dir,
    )

    assert report["proposed_patch_count"] == 0
    assert report["skipped_row_count"] == 1
    assert json_doc["skipped_rows"][0]["skip_reason"] == "served_target_old_coordinate_mismatch"


def write_fixture_artifacts(tmp_path, *, old_lat=47.43):
    artifact_dir = tmp_path / "canonical_web"
    (artifact_dir / "event_chunks").mkdir(parents=True)
    rows = [
        {
            "event_id": 101,
            "canonical_event_id": "evt_fr_1",
            "lat": old_lat,
            "lon": 3.82,
            "coordinate_source": "source_coordinates",
        }
    ]
    (artifact_dir / "event_chunks" / "chunk_000000.json").write_text(
        json.dumps(rows),
        encoding="utf-8",
    )
    return artifact_dir
