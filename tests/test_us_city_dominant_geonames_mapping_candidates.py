import zipfile

from scripts.summarize_us_city_dominant_geonames_mapping_candidates import (
    summarize_us_city_dominant_geonames_mapping_candidates,
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
        "America/New_York",
        "",
    ]
    return "\t".join(fields)


def write_geonames_zip(path, rows):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("allCountries.txt", "\n".join(rows) + "\n")


def test_us_city_dominant_accepts_unique_and_dominant_city(tmp_path):
    mapping_csv = tmp_path / "mapping.csv"
    mapping_csv.write_text(
        "query,count,bucket\n"
        '"el paso, us",10,city_region_like\n'
        '"uniqueville, us",4,city_region_like\n',
        encoding="utf-8",
    )
    geonames_zip = tmp_path / "allCountries.zip"
    write_geonames_zip(
        geonames_zip,
        [
            geonames_row(1, "El Paso", "El Paso", 31.76, -106.49, "TX", 678000),
            geonames_row(2, "El Paso", "El Paso", 40.74, -89.02, "IL", 2800),
            geonames_row(3, "Uniqueville", "Uniqueville", 35.0, -90.0, "AR", 2500),
        ],
    )

    report = summarize_us_city_dominant_geonames_mapping_candidates(
        mapping_csv=mapping_csv,
        geonames_zip=geonames_zip,
        limit=100,
    )

    assert report["canonical_outputs_mutated"] is False
    assert report["resolved_query_count"] == 2
    rows = {row["query"]: row for row in report["resolved_queries"]}
    assert rows["el paso, us"]["decision"] == "accepted_dominant_us_city"
    assert rows["el paso, us"]["admin1"] == "TX"
    assert rows["uniqueville, us"]["decision"] == "accepted_unique_us_city"


def test_us_city_dominant_rejects_ambiguous_and_non_us_shapes(tmp_path):
    mapping_csv = tmp_path / "mapping.csv"
    mapping_csv.write_text(
        "query,count,bucket\n"
        '"springfield, us",9,city_region_like\n'
        '"dublin, ie",5,city_region_like\n'
        '"us, us",3,city_region_like\n',
        encoding="utf-8",
    )
    geonames_zip = tmp_path / "allCountries.zip"
    write_geonames_zip(
        geonames_zip,
        [
            geonames_row(1, "Springfield", "Springfield", 39.8, -89.6, "IL", 114000),
            geonames_row(2, "Springfield", "Springfield", 42.1, -72.6, "MA", 155000),
        ],
    )

    report = summarize_us_city_dominant_geonames_mapping_candidates(
        mapping_csv=mapping_csv,
        geonames_zip=geonames_zip,
        limit=100,
    )

    assert report["parseable_us_city_query_count"] == 1
    assert report["resolved_query_count"] == 0
    assert report["rejected_event_counts"]["rejected_ambiguous_us_city"] == 9


def test_us_city_dominant_rejects_unsafe_city_only_tokens(tmp_path):
    mapping_csv = tmp_path / "mapping.csv"
    mapping_csv.write_text(
        "query,count,bucket\n"
        '"n, us",2,city_region_like\n'
        '"new mexico, us",3,city_region_like\n'
        '"yosemite, us",4,city_region_like\n'
        '"tinyville, us",5,city_region_like\n',
        encoding="utf-8",
    )
    geonames_zip = tmp_path / "allCountries.zip"
    write_geonames_zip(
        geonames_zip,
        [
            geonames_row(1, "North", "North", 33.6, -81.1, "SC", 700),
            geonames_row(2, "New Mexico", "New Mexico", 39.4, -76.5, "MD", 1200),
            geonames_row(3, "Yosemite", "Yosemite", 37.3, -84.8, "KY", 500),
            geonames_row(4, "Tinyville", "Tinyville", 35.0, -90.0, "AR", 999),
        ],
    )

    report = summarize_us_city_dominant_geonames_mapping_candidates(
        mapping_csv=mapping_csv,
        geonames_zip=geonames_zip,
        limit=100,
    )

    assert report["parseable_us_city_query_count"] == 1
    assert report["resolved_query_count"] == 0
    assert report["rejected_event_counts"]["rejected_low_population_unique_us_city"] == 5
