import csv
import json
import zipfile

from scripts.build_high_confidence_coordinate_disagreement_packet import (
    build_high_confidence_coordinate_disagreement_packet,
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
    "geonames_lat",
    "geonames_lon",
    "distance_km",
]


def geonames_line(
    geoname_id,
    name,
    lat,
    lon,
    country_code,
    admin1,
    feature_class="P",
    feature_code="PPL",
    population=0,
):
    return "\t".join(
        [
            geoname_id,
            name,
            name,
            "",
            str(lat),
            str(lon),
            feature_class,
            feature_code,
            country_code,
            "",
            admin1,
            "",
            "",
            "",
            str(population),
            "",
            "0",
            "UTC",
            "2026-01-01",
        ]
    )


def write_geonames(path):
    lines = [
        geonames_line("fargo_nd", "Fargo", 46.877, -96.789, "US", "ND", population=125990),
        geonames_line("fargo_ga", "Fargo", 30.684, -82.566, "US", "GA", population=321),
        geonames_line("hawaii_fl", "Hawaii", 25.8602, -80.1198, "US", "FL", feature_class="S", feature_code="HTL"),
        geonames_line("windward_de", "Windward", 39.775, -75.641, "US", "DE"),
        geonames_line("bruce_ms", "Bruce", 33.99206, -89.34896, "US", "MS"),
        geonames_line("plozevet", "Plozevet", 47.98546, -4.4261, "FR", "53", population=2976),
        geonames_line("woodridge_qld", "Woodridge", -27.63333, 153.1, "AU", "04", population=0),
        geonames_line("woodridge_wa", "Woodridge", -31.333, 115.6, "AU", "08", population=0),
    ]
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("allCountries.txt", "\n".join(lines) + "\n")


def base_row(**overrides):
    row = {
        "canonical_event_id": "evt",
        "event_id": "",
        "source_name": "ufocat",
        "source_row_number": "1",
        "source_native_id": "1",
        "date": "1954-09-20",
        "location_raw": "FARGO, Cass, ND, US",
        "country": "United States of America",
        "coordinate_source": "raw_latlong",
        "location_precision": "exact_coords",
        "lat": "46.88",
        "lon": "96.78",
        "geonames_name": "Fargo",
        "geonames_id": "fargo_nd",
        "geonames_feature_class": "P",
        "geonames_feature_code": "PPL",
        "geonames_lat": "46.877",
        "geonames_lon": "-96.789",
        "distance_km": "8000",
    }
    row.update(overrides)
    return row


def write_disagreements(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def run_packet(tmp_path, rows):
    disagreements = tmp_path / "disagreements.csv"
    geonames = tmp_path / "allCountries.zip"
    write_disagreements(disagreements, rows)
    write_geonames(geonames)
    return build_high_confidence_coordinate_disagreement_packet(
        disagreements_csv=disagreements,
        geonames_zip=geonames,
        json_output=tmp_path / "packet.json",
        csv_output=tmp_path / "packet.csv",
        min_distance_km=150,
        max_rows=5000,
    )


def test_packet_accepts_ufocat_us_row_with_matching_state_admin(tmp_path):
    report = run_packet(tmp_path, [base_row(canonical_event_id="fargo")])

    assert report["accepted_count"] == 1
    assert report["examples"][0]["canonical_event_id"] == "fargo"
    assert report["examples"][0]["geonames_admin1"] == "ND"
    assert report["examples"][0]["admin_tokens"] == ["ND"]
    assert report["examples"][0]["admin_match_kind"] == "matched"
    assert report["canonical_outputs_mutated"] is False


def test_packet_rejects_us_same_name_wrong_state_match(tmp_path):
    report = run_packet(
        tmp_path,
        [
            base_row(
                canonical_event_id="fargo-wrong-state",
                geonames_id="fargo_ga",
                geonames_lat="30.684",
                geonames_lon="-82.566",
            )
        ],
    )

    assert report["accepted_count"] == 0
    assert report["rejected_counts"]["admin_token_mismatch"] == 1


def test_packet_does_not_extract_state_substrings_from_county_names(tmp_path):
    report = run_packet(
        tmp_path,
        [
            base_row(
                canonical_event_id="bruce-adams-wa",
                location_raw="BRUCE, Adams, WA, US",
                geonames_name="Bruce",
                geonames_id="bruce_ms",
                geonames_lat="33.99206",
                geonames_lon="-89.34896",
            )
        ],
    )

    assert report["accepted_count"] == 0
    assert report["rejected_counts"]["admin_token_mismatch"] == 1


def test_packet_rejects_generic_hawaii_and_windward_false_matches(tmp_path):
    report = run_packet(
        tmp_path,
        [
            base_row(
                canonical_event_id="hawaii",
                location_raw="HAWAII, HI, P",
                geonames_name="Hawaii",
                geonames_id="hawaii_fl",
                geonames_lat="25.8602",
                geonames_lon="-80.1198",
            ),
            base_row(
                canonical_event_id="windward",
                location_raw="WINDWARD, Honolulu, HI, P",
                geonames_name="Windward",
                geonames_id="windward_de",
                geonames_lat="39.775",
                geonames_lon="-75.641",
            ),
        ],
    )

    assert report["accepted_count"] == 0
    assert report["rejected_counts"]["generic_primary_place"] == 2


def test_packet_rejects_offshore_text_and_low_distance_rows(tmp_path):
    report = run_packet(
        tmp_path,
        [
            base_row(canonical_event_id="offshore", location_raw="ATLANTIC OCEAN OFF FRANCE, FRA, EU"),
            base_row(canonical_event_id="low-distance", distance_km="25"),
        ],
    )

    assert report["accepted_count"] == 0
    assert report["rejected_counts"]["offshore_or_maritime_text"] == 1
    assert report["rejected_counts"]["below_distance_threshold"] == 1


def test_packet_accepts_non_us_exact_primary_place_match_without_admin_requirement(tmp_path):
    report = run_packet(
        tmp_path,
        [
            base_row(
                canonical_event_id="plozevet",
                location_raw="PLOZEVET, Finistere, FRA, EU",
                country="France",
                lat="47.985",
                lon="4.426",
                geonames_name="Plozevet",
                geonames_id="plozevet",
                geonames_lat="47.98546",
                geonames_lon="-4.4261",
                distance_km="654",
            )
        ],
    )

    assert report["accepted_count"] == 1
    assert report["examples"][0]["canonical_event_id"] == "plozevet"
    assert report["examples"][0]["admin_match_kind"] == "not_required"


def test_packet_rejects_australia_same_name_wrong_state_match(tmp_path):
    report = run_packet(
        tmp_path,
        [
            base_row(
                canonical_event_id="woodridge-wrong-state",
                location_raw="WOODRIDGE, GIN GIN, Gingin, WAU, AU",
                country="Australia",
                lat="-31.33",
                lon="115.6",
                geonames_name="Woodridge",
                geonames_id="woodridge_qld",
                geonames_lat="-27.63333",
                geonames_lon="153.1",
                distance_km="3635",
            )
        ],
    )

    assert report["accepted_count"] == 0
    assert report["rejected_counts"]["admin_token_mismatch"] == 1


def test_packet_accepts_australia_row_with_matching_state_admin(tmp_path):
    report = run_packet(
        tmp_path,
        [
            base_row(
                canonical_event_id="woodridge-wa",
                location_raw="WOODRIDGE, GIN GIN, Gingin, WAU, AU",
                country="Australia",
                lat="-27.6",
                lon="153.1",
                geonames_name="Woodridge",
                geonames_id="woodridge_wa",
                geonames_lat="-31.333",
                geonames_lon="115.6",
                distance_km="3635",
            )
        ],
    )

    assert report["accepted_count"] == 1
    assert report["examples"][0]["admin_tokens"] == ["08"]
    assert report["examples"][0]["admin_match_kind"] == "matched"


def test_packet_writes_json_and_csv_outputs(tmp_path):
    report = run_packet(tmp_path, [base_row(canonical_event_id="fargo")])

    packet_json = tmp_path / "packet.json"
    packet_csv = tmp_path / "packet.csv"
    assert packet_json.exists()
    assert packet_csv.exists()
    saved = json.loads(packet_json.read_text(encoding="utf-8"))
    assert saved["accepted_count"] == report["accepted_count"]
    assert "FARGO, Cass, ND, US" in packet_csv.read_text(encoding="utf-8")
