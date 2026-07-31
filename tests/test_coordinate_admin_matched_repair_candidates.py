import csv

from scripts.build_coordinate_admin_matched_repair_candidates import (
    build_coordinate_admin_matched_repair_candidates,
)


FIELDNAMES = [
    "canonical_event_id",
    "event_id",
    "source_name",
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
        "canonical_event_id": "evt-fargo",
        "event_id": "",
        "source_name": "ufocat",
        "source_row_number": "1",
        "source_native_id": "1",
        "date": "1954-09-20",
        "location_raw": "FARGO, Cass, ND, US",
        "country": "United States of America",
        "coordinate_source": "source_coordinates",
        "location_precision": "coordinate",
        "lat": "46.88",
        "lon": "96.78",
        "geonames_name": "Fargo",
        "geonames_id": "5059163",
        "geonames_feature_class": "P",
        "geonames_feature_code": "PPL",
        "geonames_admin1": "ND",
        "geonames_lat": "46.87719",
        "geonames_lon": "-96.7898",
        "distance_km": "8000",
        "primary_place_key": "fargo",
        "admin_tokens": "ND",
        "admin_match_kind": "matched",
        "review_recommendation": "review_coordinate_replace_or_quarantine",
    }
    row.update(overrides)
    return row


def run_report(tmp_path, rows):
    input_csv = tmp_path / "admin.csv"
    write_rows(input_csv, rows)
    return build_coordinate_admin_matched_repair_candidates(
        input_csv=input_csv,
        json_output=tmp_path / "report.json",
        csv_output=tmp_path / "report.csv",
    )


def test_admin_matched_report_recommends_repair_when_current_outside_and_geonames_inside(tmp_path):
    report = run_report(tmp_path, [base_row()])
    rows = read_rows(tmp_path / "report.csv")

    assert report["canonical_outputs_mutated"] is False
    assert report["preview_outputs_written"] is False
    assert report["action_counts"] == {"preview_repair_candidate": 1}
    assert rows[0]["recommended_action"] == "preview_repair_candidate"
    assert rows[0]["recommendation_reason"] == "current_outside_admin_bounds_geonames_inside_admin_bounds"
    assert rows[0]["suggested_preview_repair_action"] == "replace_with_same_state_geonames_feature"


def test_admin_matched_report_does_not_repair_when_current_point_is_plausible(tmp_path):
    report = run_report(
        tmp_path,
        [
            base_row(
                canonical_event_id="evt-fargo-good",
                lon="-96.78",
                distance_km="2",
            )
        ],
    )
    rows = read_rows(tmp_path / "report.csv")

    assert report["action_counts"] == {"manual_review_only": 1}
    assert rows[0]["recommendation_reason"] == "current_coordinate_inside_declared_admin_bounds"


def test_admin_matched_report_quarantines_when_replacement_candidate_fails_bounds(tmp_path):
    report = run_report(
        tmp_path,
        [
            base_row(
                geonames_lat="40.0",
                geonames_lon="-80.0",
                distance_km="2000",
            )
        ],
    )
    rows = read_rows(tmp_path / "report.csv")

    assert report["action_counts"] == {"quarantine_candidate": 1}
    assert rows[0]["recommendation_reason"] == "current_and_geonames_outside_declared_admin_bounds"


def test_admin_matched_report_handles_australia_admin_bounds(tmp_path):
    report = run_report(
        tmp_path,
        [
            base_row(
                canonical_event_id="evt-geraldton",
                location_raw="GERALDTON, WAU, AU",
                country="Australia",
                lat="-28.78",
                lon="144.6",
                geonames_name="Geraldton",
                geonames_id="2070998",
                geonames_admin1="08",
                geonames_lat="-28.77897",
                geonames_lon="114.61459",
                distance_km="2914",
                primary_place_key="geraldton",
                admin_tokens="08",
            )
        ],
    )
    rows = read_rows(tmp_path / "report.csv")

    assert report["action_counts"] == {"preview_repair_candidate": 1}
    assert rows[0]["suggested_preview_repair_action"] == "replace_with_same_australian_admin_geonames_feature"


def test_admin_matched_report_keeps_ambiguous_admin_tokens_out_of_repair_lane(tmp_path):
    report = run_report(
        tmp_path,
        [
            base_row(
                canonical_event_id="evt-ambiguous",
                location_raw="DULUTH, MN, San Bernardi, CA, US",
                admin_tokens="CA;MN",
                geonames_admin1="MN",
            )
        ],
    )
    rows = read_rows(tmp_path / "report.csv")

    assert report["action_counts"] == {"manual_review_only": 1}
    assert rows[0]["recommendation_reason"] == "missing_or_ambiguous_admin_token"
