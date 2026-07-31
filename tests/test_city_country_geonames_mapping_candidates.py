import json
import zipfile

from scripts.summarize_city_country_geonames_mapping_candidates import (
    summarize_city_country_geonames_mapping_candidates,
)


def write_country_info(path):
    path.write_text(
        "#ISO\tISO3\tISO-Numeric\tfips\tCountry\n"
        "IE\tIRL\t372\tEI\tIreland\n"
        "GB\tGBR\t826\tUK\tUnited Kingdom\n"
        "NZ\tNZL\t554\tNZ\tNew Zealand\n"
        "US\tUSA\t840\tUS\tUnited States\n",
        encoding="utf-8",
    )


def geonames_row(geoname_id, name, ascii_name, lat, lon, country, admin1, population):
    fields = [
        str(geoname_id),
        name,
        ascii_name,
        "",
        str(lat),
        str(lon),
        "P",
        "PPL",
        country,
        "",
        admin1,
        "",
        "",
        "",
        str(population),
        "",
        "",
        "Europe/Dublin",
        "",
    ]
    return "\t".join(fields)


def write_geonames_zip(path, rows):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("allCountries.txt", "\n".join(rows) + "\n")


def test_city_country_candidates_accept_unique_explicit_country_match(tmp_path):
    mapping_csv = tmp_path / "mapping.csv"
    mapping_csv.write_text(
        "query,count,bucket\n"
        '"dublin, , ie",52,city_state_country_like\n'
        '"country, , ireland",10,city_state_country_like\n'
        '"springfield, , us",99,city_state_country_like\n',
        encoding="utf-8",
    )
    geonames_zip = tmp_path / "allCountries.zip"
    country_info = tmp_path / "countryInfo.txt"
    write_country_info(country_info)
    write_geonames_zip(geonames_zip, [geonames_row(1, "Dublin", "Dublin", 53.35, -6.26, "IE", "07", 1173179)])

    report = summarize_city_country_geonames_mapping_candidates(
        mapping_csv=mapping_csv,
        geonames_zip=geonames_zip,
        country_info=country_info,
        limit=100,
    )

    assert report["canonical_outputs_mutated"] is False
    assert report["geocoding_performed"] is False
    assert report["resolved_query_count"] == 1
    assert report["high_or_medium_confidence_event_count"] == 52
    assert report["resolved_queries"][0]["query"] == "dublin, , ie"
    assert report["resolved_queries"][0]["confidence"] == "high"


def test_city_country_candidates_accept_only_strongly_dominant_multiple_match(tmp_path):
    mapping_csv = tmp_path / "mapping.csv"
    mapping_csv.write_text(
        "query,count,bucket\n"
        '"auckland, , nz",78,city_state_country_like\n'
        '"duplicate, , nz",12,city_state_country_like\n',
        encoding="utf-8",
    )
    geonames_zip = tmp_path / "allCountries.zip"
    country_info = tmp_path / "countryInfo.txt"
    write_country_info(country_info)
    write_geonames_zip(
        geonames_zip,
        [
            geonames_row(1, "Auckland", "Auckland", -36.85, 174.76, "NZ", "E7", 1500000),
            geonames_row(2, "Auckland", "Auckland", -45.0, 170.0, "NZ", "F7", 1000),
            geonames_row(3, "Duplicate", "Duplicate", -41.0, 172.0, "NZ", "A", 10000),
            geonames_row(4, "Duplicate", "Duplicate", -42.0, 173.0, "NZ", "B", 9000),
        ],
    )

    report = summarize_city_country_geonames_mapping_candidates(
        mapping_csv=mapping_csv,
        geonames_zip=geonames_zip,
        country_info=country_info,
        limit=100,
    )

    assert report["resolved_query_count"] == 1
    assert report["resolved_queries"][0]["query"] == "auckland, , nz"
    assert report["resolved_queries"][0]["confidence"] == "medium"
    assert report["rejected_event_counts"]["rejected_ambiguous_city_country"] == 12


def test_city_country_candidates_ignore_admin_present_rows_and_slash_regions(tmp_path):
    mapping_csv = tmp_path / "mapping.csv"
    mapping_csv.write_text(
        "query,count,bucket\n"
        '"london, england, united kingdom",21,city_state_country_like\n'
        '"uk/england, , united kingdom",70,city_state_country_like\n',
        encoding="utf-8",
    )
    geonames_zip = tmp_path / "allCountries.zip"
    country_info = tmp_path / "countryInfo.txt"
    write_country_info(country_info)
    write_geonames_zip(geonames_zip, [geonames_row(1, "London", "London", 51.5, -0.12, "GB", "ENG", 9000000)])

    report = summarize_city_country_geonames_mapping_candidates(
        mapping_csv=mapping_csv,
        geonames_zip=geonames_zip,
        country_info=country_info,
        limit=100,
    )

    assert report["parseable_city_country_query_count"] == 0
    assert report["resolved_query_count"] == 0
