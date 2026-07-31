import zipfile

from scripts.summarize_two_part_city_country_geonames_mapping_candidates import (
    summarize_two_part_city_country_geonames_mapping_candidates,
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
        "CA\tCAN\t124\tCA\tCanada\n"
        "US\tUSA\t840\tUS\tUnited States\n",
        encoding="utf-8",
    )


def test_two_part_city_country_accepts_non_us_unique_city(tmp_path):
    mapping_csv = tmp_path / "mapping.csv"
    mapping_csv.write_text(
        "query,count,bucket\n"
        '"colares, br",87,city_region_like\n',
        encoding="utf-8",
    )
    country_info = tmp_path / "countryInfo.txt"
    write_country_info(country_info)
    geonames_zip = tmp_path / "allCountries.zip"
    write_geonames_zip(
        geonames_zip,
        [geonames_row(1, "Colares", "Colares", -0.936, -48.281, "BR", "16", 11971)],
    )

    report = summarize_two_part_city_country_geonames_mapping_candidates(
        mapping_csv=mapping_csv,
        geonames_zip=geonames_zip,
        country_info=country_info,
        limit=100,
    )

    assert report["canonical_outputs_mutated"] is False
    assert report["resolved_query_count"] == 1
    assert report["high_or_medium_confidence_event_count"] == 87
    assert report["resolved_queries"][0]["country_code"] == "BR"


def test_two_part_city_country_rejects_us_country_only_and_ambiguous(tmp_path):
    mapping_csv = tmp_path / "mapping.csv"
    mapping_csv.write_text(
        "query,count,bucket\n"
        '"springfield, us",9,city_region_like\n'
        '"br, br",8,city_region_like\n'
        '"victoria, ca",7,city_region_like\n',
        encoding="utf-8",
    )
    country_info = tmp_path / "countryInfo.txt"
    write_country_info(country_info)
    geonames_zip = tmp_path / "allCountries.zip"
    write_geonames_zip(
        geonames_zip,
        [
            geonames_row(1, "Victoria", "Victoria", 48.43, -123.36, "CA", "BC", 289625),
            geonames_row(2, "Victoria", "Victoria", 44.86, -65.35, "CA", "07", 100000),
        ],
    )

    report = summarize_two_part_city_country_geonames_mapping_candidates(
        mapping_csv=mapping_csv,
        geonames_zip=geonames_zip,
        country_info=country_info,
        limit=100,
    )

    assert report["parseable_two_part_city_country_query_count"] == 1
    assert report["resolved_query_count"] == 0
    assert report["rejected_event_counts"]["rejected_ambiguous_city_country"] == 7
