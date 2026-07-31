import zipfile

from scripts.summarize_structured_primary_city_admin_geonames_mapping_candidates import (
    summarize_structured_primary_city_admin_geonames_mapping_candidates,
)


def write_country_info(path):
    path.write_text(
        "#ISO\tISO3\tISO-Numeric\tfips\tCountry\n"
        "US\tUSA\t840\tUS\tUnited States\n"
        "CA\tCAN\t124\tCA\tCanada\n",
        encoding="utf-8",
    )


def geonames_row(geoname_id, name, ascii_name, alternate_names, lat, lon, country, admin1, population):
    fields = [
        str(geoname_id),
        name,
        ascii_name,
        alternate_names,
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
        "America/New_York",
        "",
    ]
    return "\t".join(fields)


def write_geonames_zip(path, rows):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("allCountries.txt", "\n".join(rows) + "\n")


def test_structured_primary_city_admin_accepts_primary_name_only(tmp_path):
    mapping_csv = tmp_path / "mapping.csv"
    mapping_csv.write_text(
        "query,count,bucket\n"
        '"scarborough, on, ca",29,city_state_country_like\n'
        '"amsterdam, holland, va, us",5,city_state_country_like\n',
        encoding="utf-8",
    )
    geonames_zip = tmp_path / "allCountries.zip"
    country_info = tmp_path / "countryInfo.txt"
    write_country_info(country_info)
    write_geonames_zip(
        geonames_zip,
        [
            geonames_row(1, "Scarborough", "Scarborough", "", 43.77, -79.25, "CA", "08", 600000),
            geonames_row(2, "Daleville", "Daleville", "Amsterdam", 37.42, -79.91, "US", "VA", 2000),
        ],
    )

    report = summarize_structured_primary_city_admin_geonames_mapping_candidates(
        mapping_csv=mapping_csv,
        geonames_zip=geonames_zip,
        country_info=country_info,
        limit=100,
    )

    assert report["canonical_outputs_mutated"] is False
    assert report["geocoding_performed"] is False
    assert report["resolved_query_count"] == 1
    assert report["resolved_queries"][0]["query"] == "scarborough, on, ca"
    assert report["resolved_queries"][0]["name"] == "Scarborough"
    assert report["rejected_event_counts"]["rejected_no_primary_city_admin_match"] == 5


def test_structured_primary_city_admin_rejects_missing_admin_and_placeholder(tmp_path):
    mapping_csv = tmp_path / "mapping.csv"
    mapping_csv.write_text(
        "query,count,bucket\n"
        '"dublin, , ie",52,city_state_country_like\n'
        '"unknown, ca, us",9,city_state_country_like\n',
        encoding="utf-8",
    )
    geonames_zip = tmp_path / "allCountries.zip"
    country_info = tmp_path / "countryInfo.txt"
    write_country_info(country_info)
    write_geonames_zip(geonames_zip, [geonames_row(1, "Unknown", "Unknown", "", 1, 1, "US", "CA", 100)])

    report = summarize_structured_primary_city_admin_geonames_mapping_candidates(
        mapping_csv=mapping_csv,
        geonames_zip=geonames_zip,
        country_info=country_info,
        limit=100,
    )

    assert report["parseable_structured_query_count"] == 0
    assert report["resolved_query_count"] == 0


def test_structured_primary_city_admin_accepts_dominant_same_admin_match(tmp_path):
    mapping_csv = tmp_path / "mapping.csv"
    mapping_csv.write_text(
        "query,count,bucket\n"
        '"ames, tx, us",3,city_state_country_like\n',
        encoding="utf-8",
    )
    geonames_zip = tmp_path / "allCountries.zip"
    country_info = tmp_path / "countryInfo.txt"
    write_country_info(country_info)
    write_geonames_zip(
        geonames_zip,
        [
            geonames_row(1, "Ames", "Ames", "", 30.0, -94.0, "US", "TX", 20000),
            geonames_row(2, "Ames", "Ames", "", 31.0, -95.0, "US", "TX", 200),
        ],
    )

    report = summarize_structured_primary_city_admin_geonames_mapping_candidates(
        mapping_csv=mapping_csv,
        geonames_zip=geonames_zip,
        country_info=country_info,
        limit=100,
    )

    assert report["resolved_query_count"] == 1
    assert report["resolved_queries"][0]["confidence"] == "medium"
