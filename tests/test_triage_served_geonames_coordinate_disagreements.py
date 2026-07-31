import csv

from scripts.triage_served_geonames_coordinate_disagreements import (
    triage_served_geonames_coordinate_disagreements,
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
]


def write_rows(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def base_row(**overrides):
    row = {
        "event_id": "1",
        "chunk_id": "chunk_000000",
        "detail_index": "0",
        "source": "ufocat",
        "date": "2007-02-07",
        "location_raw": "SUGARLOAF MOUNTAIN, Montgomery, MD, US",
        "country": "United States of America",
        "coordinate_source": "raw_latlong",
        "location_precision": "exact_coords",
        "lat": "39.27",
        "lon": "-77.39",
        "geonames_name": "Sugarloaf Mountain",
        "geonames_id": "11205279",
        "geonames_feature_class": "T",
        "geonames_feature_code": "MT",
        "geonames_admin1": "AK",
        "geonames_lat": "53.82427",
        "geonames_lon": "-166.51505",
        "distance_km": "6539.05",
        "review_recommendation": "review_coordinate_replace_or_quarantine",
    }
    row.update(overrides)
    return row


def run_triage(tmp_path, rows):
    input_csv = tmp_path / "served.csv"
    write_rows(input_csv, rows)
    return triage_served_geonames_coordinate_disagreements(
        input_csv=input_csv,
        json_output=tmp_path / "triage.json",
        output_dir=tmp_path,
    )


def test_triage_flags_geonames_admin_conflict_as_likely_false_match(tmp_path):
    report = run_triage(tmp_path, [base_row()])

    assert report["lane_counts"] == {"geonames_admin_conflict": 1}
    example = report["lane_summaries"]["geonames_admin_conflict"]["top_examples"][0]
    assert example["admin_tokens"] == "MD"
    assert example["geonames_admin_normalized"] == "AK"
    assert example["triage_reason"] == "text_admin_token_conflicts_with_geonames_admin"


def test_triage_keeps_admin_match_in_review_lane(tmp_path):
    report = run_triage(
        tmp_path,
        [
            base_row(
                location_raw="FARGO, Cass, ND, US",
                geonames_name="Fargo",
                geonames_admin1="ND",
            )
        ],
    )

    assert report["lane_counts"] == {"admin_matched_review": 1}
    example = report["lane_summaries"]["admin_matched_review"]["top_examples"][0]
    assert example["admin_tokens"] == "ND"
    assert example["triage_reason"] == "single_text_admin_token_matches_geonames_admin"


def test_triage_routes_multi_admin_matches_to_ambiguous_lane(tmp_path):
    report = run_triage(
        tmp_path,
        [
            base_row(
                location_raw="DULUTH, MN, San Bernardino, CA, US",
                geonames_name="Duluth",
                geonames_admin1="CA",
            )
        ],
    )

    assert report["lane_counts"] == {"admin_ambiguous_review": 1}
    example = report["lane_summaries"]["admin_ambiguous_review"]["top_examples"][0]
    assert example["admin_tokens"] == "CA;MN"
    assert example["triage_reason"] == "multiple_text_admin_tokens_include_geonames_admin"


def test_triage_routes_international_rows_to_country_specific_review(tmp_path):
    report = run_triage(
        tmp_path,
        [
            base_row(
                location_raw="AZE, Loire-Cher, FRA, EU",
                country="France",
                geonames_admin1="52",
            )
        ],
    )

    assert report["lane_counts"] == {"international_or_no_admin_review": 1}
