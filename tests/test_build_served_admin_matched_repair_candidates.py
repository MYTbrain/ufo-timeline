from __future__ import annotations

import csv

from scripts.build_served_admin_matched_repair_candidates import (
    build_served_admin_matched_repair_candidates,
)


FIELDNAMES = [
    "event_id",
    "chunk_id",
    "detail_index",
    "source",
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
    "review_recommendation",
    "admin_tokens",
    "geonames_admin_normalized",
    "triage_lane",
    "triage_reason",
]


def test_served_admin_matched_report_recommends_repair_for_bad_hemisphere_current(tmp_path):
    report = run_report(tmp_path, [base_row()])
    rows = read_rows(tmp_path / "report.csv")

    assert report["canonical_outputs_mutated"] is False
    assert report["static_outputs_mutated"] is False
    assert report["deployment_outputs_mutated"] is False
    assert report["action_counts"] == {"served_repair_candidate": 1}
    assert rows[0]["recommended_action"] == "served_repair_candidate"
    assert rows[0]["recommendation_reason"] == "current_outside_admin_bounds_geonames_inside_admin_bounds"
    assert rows[0]["served_patch_target_ready"] == "True"


def test_served_admin_matched_report_keeps_plausible_same_admin_duplicate_manual(tmp_path):
    report = run_report(
        tmp_path,
        [
            base_row(
                event_id="1991581210480900",
                location_raw="Desert, CANUTILLO, TX, Texas, USA",
                admin_tokens="TX",
                geonames_admin1="TX",
                geonames_admin_normalized="TX",
                lat="31.911113",
                lon="-106.600005",
                geonames_name="Desert",
                geonames_lat="33.38844",
                geonames_lon="-96.40193",
                distance_km="968.397",
            )
        ],
    )
    rows = read_rows(tmp_path / "report.csv")

    assert report["action_counts"] == {"manual_review_only": 1}
    assert rows[0]["recommendation_reason"] == "current_coordinate_inside_declared_admin_bounds"


def test_served_admin_matched_report_supports_canadian_province_bounds(tmp_path):
    report = run_report(
        tmp_path,
        [
            base_row(
                country="Canada",
                location_raw="PETERBOROUGH, ON, Canada",
                admin_tokens="ON",
                geonames_admin1="ON",
                geonames_admin_normalized="ON",
                lat="44.3",
                lon="78.32",
                geonames_lat="44.3",
                geonames_lon="-78.32",
                distance_km="8700",
            )
        ],
    )
    rows = read_rows(tmp_path / "report.csv")

    assert report["action_counts"] == {"served_repair_candidate": 1}
    assert rows[0]["declared_admin"] == "ON"


def test_served_admin_matched_report_quarantines_when_replacement_fails_bounds(tmp_path):
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

    assert report["action_counts"] == {"served_quarantine_candidate": 1}
    assert rows[0]["recommendation_reason"] == "current_and_geonames_outside_declared_admin_bounds"


def base_row(**overrides):
    row = {
        "event_id": "444",
        "chunk_id": "chunk_000123",
        "detail_index": "77",
        "source": "ufocat",
        "date": "1954-09-20",
        "location_raw": "FARGO, Cass, ND, US",
        "country": "United States of America",
        "coordinate_source": "raw_latlong",
        "location_precision": "exact_coords",
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
        "review_recommendation": "review_coordinate_replace_or_quarantine",
        "admin_tokens": "ND",
        "geonames_admin_normalized": "ND",
        "triage_lane": "admin_matched_review",
        "triage_reason": "single_text_admin_token_matches_geonames_admin",
    }
    row.update(overrides)
    return row


def run_report(tmp_path, rows):
    input_csv = tmp_path / "admin.csv"
    write_rows(input_csv, rows)
    return build_served_admin_matched_repair_candidates(
        input_csv=input_csv,
        json_output=tmp_path / "report.json",
        csv_output=tmp_path / "report.csv",
    )


def write_rows(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def read_rows(path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))
