import csv

from scripts.build_coordinate_transform_repair_candidates import (
    build_coordinate_transform_repair_candidates,
)


FIELDNAMES = [
    "canonical_event_id",
    "event_id",
    "chunk_id",
    "detail_index",
    "source_name",
    "source",
    "source_row_number",
    "source_native_id",
    "date",
    "location_raw",
    "country",
    "coordinate_source",
    "location_precision",
    "lat",
    "lon",
    "geonames_name",
    "geonames_id",
    "geonames_feature_class",
    "geonames_feature_code",
    "geonames_admin1",
    "geonames_lat",
    "geonames_lon",
    "distance_km",
    "primary_place_key",
    "admin_tokens",
    "admin_match_kind",
    "review_recommendation",
]


def write_rows(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def read_rows(path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def base_row(**overrides):
    row = {
        "canonical_event_id": "evt-lon-flip",
        "event_id": "",
        "chunk_id": "",
        "detail_index": "",
        "source_name": "ufocat",
        "source": "",
        "source_row_number": "1",
        "source_native_id": "native-1",
        "date": "1954-10-03",
        "location_raw": "NORFOLK, Norfolk, GBR, EU",
        "country": "United Kingdom",
        "coordinate_source": "source_coordinates",
        "location_precision": "coordinate",
        "lat": "52.67",
        "lon": "-1.33",
        "geonames_name": "Norfolk",
        "geonames_id": "2641454",
        "geonames_feature_class": "P",
        "geonames_feature_code": "PPL",
        "geonames_admin1": "ENG",
        "geonames_lat": "52.67543",
        "geonames_lon": "0.94571",
        "distance_km": "153.4",
        "primary_place_key": "norfolk",
        "admin_tokens": "",
        "admin_match_kind": "not_required",
        "review_recommendation": "review_coordinate_replace_or_quarantine",
    }
    row.update(overrides)
    return row


def run_candidates(tmp_path, rows):
    input_csv = tmp_path / "input.csv"
    write_rows(input_csv, rows)
    return build_coordinate_transform_repair_candidates(
        input_csv=input_csv,
        json_output=tmp_path / "report.json",
        csv_output=tmp_path / "candidates.csv",
    )


def test_transform_candidate_detects_longitude_sign_flip(tmp_path):
    report = run_candidates(tmp_path, [base_row()])
    rows = read_rows(tmp_path / "candidates.csv")

    assert report["canonical_outputs_mutated"] is False
    assert report["preview_outputs_written"] is False
    assert report["candidate_count"] == 1
    assert rows[0]["transform"] == "lon_sign_flip"
    assert rows[0]["recommended_action"] == "coordinate_transform_repair_candidate"


def test_transform_candidate_detects_lat_lon_swap(tmp_path):
    report = run_candidates(
        tmp_path,
        [
            base_row(
                canonical_event_id="evt-swap",
                location_raw="KAZAN', Tatar, RUS, EU",
                country="Russia",
                lat="49.3",
                lon="55.83",
                geonames_lat="55.78874",
                geonames_lon="49.12214",
                geonames_name="Kazan",
                geonames_admin1="73",
                distance_km="851",
            )
        ],
    )
    rows = read_rows(tmp_path / "candidates.csv")

    assert report["candidate_count"] == 1
    assert rows[0]["transform"] == "swap"


def test_transform_candidate_rejects_small_original_disagreement(tmp_path):
    report = run_candidates(
        tmp_path,
        [
            base_row(
                canonical_event_id="evt-near",
                lat="52.67",
                lon="0.93",
                geonames_lat="52.67543",
                geonames_lon="0.94571",
                distance_km="1",
            )
        ],
    )

    assert report["candidate_count"] == 0
    assert read_rows(tmp_path / "candidates.csv") == []


def test_transform_candidate_rejects_unsupported_geonames_feature_class(tmp_path):
    report = run_candidates(
        tmp_path,
        [
            base_row(
                canonical_event_id="evt-unsupported-feature",
                geonames_feature_class="V",
            )
        ],
    )

    assert report["candidate_count"] == 0


def test_transform_candidate_preserves_served_payload_identifiers(tmp_path):
    report = run_candidates(
        tmp_path,
        [
            base_row(
                canonical_event_id="",
                event_id="served-event-1",
                chunk_id="chunk_000123",
                detail_index="17",
                source_name="",
                source="ufocat",
            )
        ],
    )
    rows = read_rows(tmp_path / "candidates.csv")

    assert report["candidate_count"] == 1
    assert report["source_counts"] == {"ufocat": 1}
    assert rows[0]["event_id"] == "served-event-1"
    assert rows[0]["chunk_id"] == "chunk_000123"
    assert rows[0]["detail_index"] == "17"
    assert rows[0]["source_name"] == "ufocat"
