import zipfile

from scripts.summarize_legacy_continent_city_country_geonames_mapping_candidates import (
    summarize_legacy_continent_city_country_geonames_mapping_candidates,
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
        "America/Belem",
        "",
    ]
    return "\t".join(fields)


def write_geonames_zip(path, rows):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("allCountries.txt", "\n".join(rows) + "\n")


def write_country_info(path):
    path.write_text(
        "#ISO\tISO3\tISO-Numeric\tfips\tCountry\n"
        "BR\tBRA\t076\tBR\tBrazil\n"
        "GB\tGBR\t826\tUK\tUnited Kingdom\n",
        encoding="utf-8",
    )


def test_legacy_continent_city_country_accepts_city_iso3_continent(tmp_path):
    mapping_csv = tmp_path / "mapping.csv"
    mapping_csv.write_text(
        "query,count,bucket\n"
        '"benevides, para, bra, sa",35,city_state_country_like\n',
        encoding="utf-8",
    )
    country_info = tmp_path / "countryInfo.txt"
    write_country_info(country_info)
    geonames_zip = tmp_path / "allCountries.zip"
    write_geonames_zip(
        geonames_zip,
        [geonames_row(1, "Benevides", "Benevides", -1.36, -48.24, "BR", "16", 49794)],
    )

    report = summarize_legacy_continent_city_country_geonames_mapping_candidates(
        mapping_csv=mapping_csv,
        geonames_zip=geonames_zip,
        country_info=country_info,
        limit=100,
    )

    assert report["canonical_outputs_mutated"] is False
    assert report["resolved_query_count"] == 1
    assert report["resolved_queries"][0]["country_code"] == "BR"


def test_legacy_continent_city_country_rejects_broad_place_token(tmp_path):
    mapping_csv = tmp_path / "mapping.csv"
    mapping_csv.write_text(
        "query,count,bucket\n"
        '"england, gbr, eu",49,city_state_country_like\n',
        encoding="utf-8",
    )
    country_info = tmp_path / "countryInfo.txt"
    write_country_info(country_info)
    geonames_zip = tmp_path / "allCountries.zip"
    write_geonames_zip(
        geonames_zip,
        [geonames_row(1, "England", "England", 52.16, -0.7, "GB", "ENG", 0)],
    )

    report = summarize_legacy_continent_city_country_geonames_mapping_candidates(
        mapping_csv=mapping_csv,
        geonames_zip=geonames_zip,
        country_info=country_info,
        limit=100,
    )

    assert report["parseable_legacy_continent_city_country_query_count"] == 0
    assert report["resolved_query_count"] == 0
