import csv

from scripts.build_coordinate_disagreement_review_lanes import (
    build_coordinate_disagreement_review_lanes,
)


FIELDNAMES = [
    "canonical_event_id",
    "source_name",
    "location_raw",
    "country",
    "admin_tokens",
    "admin_match_kind",
    "distance_km",
    "geonames_name",
    "geonames_id",
]


def write_packet(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def read_rows(path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def base_row(**overrides):
    row = {
        "canonical_event_id": "evt-1",
        "source_name": "ufocat",
        "location_raw": "FARGO, Cass, ND, US",
        "country": "United States of America",
        "admin_tokens": "ND",
        "admin_match_kind": "matched",
        "distance_km": "8000",
        "geonames_name": "Fargo",
        "geonames_id": "fargo_nd",
    }
    row.update(overrides)
    return row


def run_lanes(tmp_path, rows):
    packet = tmp_path / "packet.csv"
    write_packet(packet, rows)
    return build_coordinate_disagreement_review_lanes(
        packet_csv=packet,
        json_output=tmp_path / "lanes.json",
        admin_matched_csv=tmp_path / "admin.csv",
        admin_ambiguous_csv=tmp_path / "admin_ambiguous.csv",
        international_csv=tmp_path / "international.csv",
    )


def test_review_lanes_split_admin_matched_and_international_rows(tmp_path):
    report = run_lanes(
        tmp_path,
        [
            base_row(canonical_event_id="fargo"),
            base_row(
                canonical_event_id="plozevet",
                location_raw="PLOZEVET, Finistere, FRA, EU",
                country="France",
                admin_match_kind="not_required",
                distance_km="650",
                geonames_name="Plozevet",
                geonames_id="plozevet",
            ),
            base_row(
                canonical_event_id="woodridge",
                location_raw="WOODRIDGE, GIN GIN, WAU, AU",
                country="Australia",
                admin_tokens="08",
                distance_km="3600",
                geonames_name="Woodridge",
                geonames_id="woodridge_wa",
            ),
        ],
    )

    assert report["canonical_outputs_mutated"] is False
    assert report["input_row_count"] == 3
    assert report["lanes"]["admin_matched"]["count"] == 2
    assert report["lanes"]["admin_ambiguous"]["count"] == 0
    assert report["lanes"]["international_review"]["count"] == 1
    assert report["lanes"]["admin_matched"]["country_counts"] == {
        "Australia": 1,
        "United States of America": 1,
    }
    assert report["lanes"]["international_review"]["country_counts"] == {"France": 1}


def test_review_lanes_split_multiple_admin_tokens_into_ambiguous_lane(tmp_path):
    report = run_lanes(
        tmp_path,
        [
            base_row(
                canonical_event_id="multi-state",
                location_raw="DULUTH, MN, San Bernardi, CA, US",
                admin_tokens="CA;MN",
                distance_km="2300",
            ),
            base_row(canonical_event_id="single-state", admin_tokens="ND", distance_km="900"),
        ],
    )

    admin_rows = read_rows(tmp_path / "admin.csv")
    ambiguous_rows = read_rows(tmp_path / "admin_ambiguous.csv")

    assert report["lanes"]["admin_matched"]["count"] == 1
    assert report["lanes"]["admin_ambiguous"]["count"] == 1
    assert [row["canonical_event_id"] for row in admin_rows] == ["single-state"]
    assert [row["canonical_event_id"] for row in ambiguous_rows] == ["multi-state"]


def test_review_lanes_sort_each_output_by_largest_distance_first(tmp_path):
    report = run_lanes(
        tmp_path,
        [
            base_row(canonical_event_id="near", distance_km="200"),
            base_row(canonical_event_id="far", distance_km="9000"),
            base_row(
                canonical_event_id="international-near",
                country="France",
                admin_match_kind="not_required",
                distance_km="300",
            ),
            base_row(
                canonical_event_id="international-far",
                country="France",
                admin_match_kind="not_required",
                distance_km="1200",
            ),
        ],
    )

    admin_rows = read_rows(tmp_path / "admin.csv")
    international_rows = read_rows(tmp_path / "international.csv")

    assert [row["canonical_event_id"] for row in admin_rows] == ["far", "near"]
    assert [row["canonical_event_id"] for row in international_rows] == [
        "international-far",
        "international-near",
    ]
    assert report["lanes"]["admin_matched"]["top_examples"][0]["canonical_event_id"] == "far"
    assert (
        report["lanes"]["international_review"]["top_examples"][0]["canonical_event_id"]
        == "international-far"
    )


def test_review_lanes_write_headers_for_empty_lanes(tmp_path):
    run_lanes(
        tmp_path,
        [
            base_row(
                canonical_event_id="ignored",
                admin_tokens="",
                admin_match_kind="missing_admin_token",
                distance_km="7000",
            )
        ],
    )

    admin_rows = read_rows(tmp_path / "admin.csv")
    ambiguous_rows = read_rows(tmp_path / "admin_ambiguous.csv")
    international_rows = read_rows(tmp_path / "international.csv")

    assert admin_rows == []
    assert ambiguous_rows == []
    assert international_rows == []
