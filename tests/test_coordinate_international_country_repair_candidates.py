import csv

from scripts.build_coordinate_international_country_repair_candidates import (
    build_coordinate_international_country_repair_candidates,
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
        "canonical_event_id": "evt-france-atlantic",
        "event_id": "",
        "source_name": "ufocat",
        "source_row_number": "1",
        "source_native_id": "native-1",
        "date": "1954-10-03",
        "location_raw": "PLOZEVET, Finistere, FRA, EU",
        "country": "France",
        "coordinate_source": "source_coordinates",
        "location_precision": "coordinate",
        "lat": "47.98",
        "lon": "-47.99",
        "geonames_name": "Plozevet",
        "geonames_id": "2986860",
        "geonames_feature_class": "P",
        "geonames_feature_code": "PPL",
        "geonames_admin1": "53",
        "geonames_lat": "47.9833",
        "geonames_lon": "-4.4167",
        "distance_km": "3194.4",
        "primary_place_key": "plozevet",
        "admin_tokens": "",
        "admin_match_kind": "not_required",
        "review_recommendation": "review_coordinate_replace_or_quarantine",
    }
    row.update(overrides)
    return row


def run_candidates(tmp_path, rows):
    input_csv = tmp_path / "international.csv"
    write_rows(input_csv, rows)
    return build_coordinate_international_country_repair_candidates(
        input_csv=input_csv,
        json_output=tmp_path / "report.json",
        repair_csv=tmp_path / "repair.csv",
        quarantine_csv=tmp_path / "quarantine.csv",
        manual_csv=tmp_path / "manual.csv",
    )


def test_international_country_repair_candidate_requires_current_outside_and_geonames_inside(tmp_path):
    report = run_candidates(tmp_path, [base_row()])

    repair_rows = read_rows(tmp_path / "repair.csv")
    quarantine_rows = read_rows(tmp_path / "quarantine.csv")
    manual_rows = read_rows(tmp_path / "manual.csv")

    assert report["canonical_outputs_mutated"] is False
    assert report["preview_outputs_written"] is False
    assert report["action_counts"] == {"country_repair_candidate": 1}
    assert [row["canonical_event_id"] for row in repair_rows] == ["evt-france-atlantic"]
    assert repair_rows[0]["suggested_preview_repair_action"] == "replace_with_same_country_geonames_feature"
    assert quarantine_rows == []
    assert manual_rows == []


def test_international_country_candidate_keeps_current_inside_country_as_manual_review(tmp_path):
    report = run_candidates(
        tmp_path,
        [
            base_row(
                canonical_event_id="evt-france-locality-ambiguity",
                lat="48.5",
                lon="2.1",
                geonames_lat="43.7",
                geonames_lon="7.2",
                distance_km="700",
            )
        ],
    )

    manual_rows = read_rows(tmp_path / "manual.csv")

    assert report["action_counts"] == {"manual_review_only": 1}
    assert manual_rows[0]["recommendation_reason"] == "current_coordinate_inside_broad_country_bounds"


def test_international_country_candidate_quarantines_when_geonames_is_also_outside_country(tmp_path):
    report = run_candidates(
        tmp_path,
        [
            base_row(
                canonical_event_id="evt-geonames-mismatch",
                lat="47.98",
                lon="-47.99",
                geonames_lat="40.0",
                geonames_lon="-74.0",
                distance_km="5000",
            )
        ],
    )

    quarantine_rows = read_rows(tmp_path / "quarantine.csv")

    assert report["action_counts"] == {"quarantine_candidate": 1}
    assert quarantine_rows[0]["recommendation_reason"] == "current_and_geonames_outside_broad_country_bounds"


def test_international_country_candidate_keeps_unsupported_country_manual(tmp_path):
    report = run_candidates(
        tmp_path,
        [
            base_row(
                canonical_event_id="evt-unsupported",
                country="Atlantis",
                location_raw="FICTIONAL, ATLANTIS",
                lat="0",
                lon="0",
                geonames_lat="1",
                geonames_lon="1",
            )
        ],
    )

    manual_rows = read_rows(tmp_path / "manual.csv")

    assert report["action_counts"] == {"manual_review_only": 1}
    assert manual_rows[0]["recommendation_reason"] == "unsupported_country_bounds"
