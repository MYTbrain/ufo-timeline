import zipfile

from scripts.summarize_two_part_us_city_state_geonames_mapping_candidates import (
    summarize_two_part_us_city_state_geonames_mapping_candidates,
)


def geonames_row(geoname_id, name, ascii_name, lat, lon, admin1, population):
    fields = [
        str(geoname_id),
        name,
        ascii_name,
        "",
        str(lat),
        str(lon),
        "P",
        "PPL",
        "US",
        "",
        admin1,
        "",
        "",
        "",
        str(population),
        "",
        "",
        "America/Chicago",
        "",
    ]
    return "\t".join(fields)


def write_geonames_zip(path, rows):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("allCountries.txt", "\n".join(rows) + "\n")


def test_two_part_us_city_state_accepts_state_matched_city(tmp_path):
    mapping_csv = tmp_path / "mapping.csv"
    mapping_csv.write_text(
        "query,count,bucket\n"
        '"oak ridge, tn",21,city_region_like\n'
        '"chicago, il",16,city_region_like\n',
        encoding="utf-8",
    )
    geonames_zip = tmp_path / "allCountries.zip"
    write_geonames_zip(
        geonames_zip,
        [
            geonames_row(1, "Oak Ridge", "Oak Ridge", 36.01, -84.27, "TN", 31402),
            geonames_row(2, "Chicago", "Chicago", 41.85, -87.65, "IL", 2696555),
        ],
    )

    report = summarize_two_part_us_city_state_geonames_mapping_candidates(
        mapping_csv=mapping_csv,
        geonames_zip=geonames_zip,
        limit=100,
    )

    assert report["canonical_outputs_mutated"] is False
    assert report["resolved_query_count"] == 2
    rows = {row["query"]: row for row in report["resolved_queries"]}
    assert rows["oak ridge, tn"]["admin1"] == "TN"
    assert rows["chicago, il"]["country_code"] == "US"


def test_two_part_us_city_state_rejects_non_state_and_state_as_city(tmp_path):
    mapping_csv = tmp_path / "mapping.csv"
    mapping_csv.write_text(
        "query,count,bucket\n"
        '"colares, br",87,city_region_like\n'
        '"california, ca",52,city_region_like\n'
        '"springfield, il",9,city_region_like\n',
        encoding="utf-8",
    )
    geonames_zip = tmp_path / "allCountries.zip"
    write_geonames_zip(
        geonames_zip,
        [
            geonames_row(1, "Springfield", "Springfield", 39.8, -89.6, "IL", 114000),
            geonames_row(2, "Springfield", "Springfield", 41.3, -87.5, "IL", 12000),
        ],
    )

    report = summarize_two_part_us_city_state_geonames_mapping_candidates(
        mapping_csv=mapping_csv,
        geonames_zip=geonames_zip,
        limit=100,
    )

    assert report["parseable_two_part_us_city_state_query_count"] == 1
    assert report["resolved_query_count"] == 0
    assert report["rejected_event_counts"]["rejected_ambiguous_us_city_state"] == 9


def test_two_part_us_city_state_rejects_non_us_parenthetical_hint(tmp_path):
    mapping_csv = tmp_path / "mapping.csv"
    mapping_csv.write_text(
        "query,count,bucket\n"
        '"cornwall (canada), ca",16,city_region_like\n',
        encoding="utf-8",
    )
    geonames_zip = tmp_path / "allCountries.zip"
    write_geonames_zip(
        geonames_zip,
        [geonames_row(1, "Cornwall", "Cornwall", 38.02, -121.87, "CA", 0)],
    )

    report = summarize_two_part_us_city_state_geonames_mapping_candidates(
        mapping_csv=mapping_csv,
        geonames_zip=geonames_zip,
        limit=100,
    )

    assert report["parseable_two_part_us_city_state_query_count"] == 0
    assert report["resolved_query_count"] == 0


def test_two_part_us_city_state_accepts_washington_dc_exception(tmp_path):
    mapping_csv = tmp_path / "mapping.csv"
    mapping_csv.write_text(
        "query,count,bucket\n"
        '"washington dc",78,city_state_like\n'
        '"washington, d.c.",63,city_region_like\n',
        encoding="utf-8",
    )
    geonames_zip = tmp_path / "allCountries.zip"
    write_geonames_zip(
        geonames_zip,
        [geonames_row(1, "Washington", "Washington", 38.89511, -77.03637, "DC", 689545)],
    )

    report = summarize_two_part_us_city_state_geonames_mapping_candidates(
        mapping_csv=mapping_csv,
        geonames_zip=geonames_zip,
        limit=100,
    )

    assert report["parseable_two_part_us_city_state_query_count"] == 2
    assert report["resolved_query_count"] == 2
    assert {row["admin1"] for row in report["resolved_queries"]} == {"DC"}
