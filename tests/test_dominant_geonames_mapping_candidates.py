import zipfile

from scripts.summarize_dominant_geonames_mapping_candidates import summarize_dominant_geonames_mapping_candidates


def test_dominant_geonames_mapping_candidates_accepts_dominant_city_country(tmp_path):
    mapping_csv = tmp_path / "mapping.csv"
    mapping_csv.write_text(
        "query,count,bucket\n"
        "\"phoenix, us\",10,city_region_like\n"
        "\"springfield, us\",7,city_region_like\n"
        "\"phoenix, az, us\",3,city_state_country_like\n"
        "us,99,country_or_region_only\n",
        encoding="utf-8",
    )
    geonames_zip = tmp_path / "allCountries.zip"
    rows = [
        "1\tPhoenix\tPhoenix\t\t33.4484\t-112.074\tP\tPPLA\tUS\t\tAZ\t\t\t\t1650000\t\t\tAmerica/Phoenix\t2024-01-01",
        "2\tPhoenix\tPhoenix\t\t41.611\t-87.634\tP\tPPL\tUS\t\tIL\t\t\t\t1900\t\t\tAmerica/Chicago\t2024-01-01",
        "3\tSpringfield\tSpringfield\t\t39.78\t-89.64\tP\tPPLA\tUS\t\tIL\t\t\t\t114000\t\t\tAmerica/Chicago\t2024-01-01",
        "4\tSpringfield\tSpringfield\t\t37.20\t-93.29\tP\tPPL\tUS\t\tMO\t\t\t\t169000\t\t\tAmerica/Chicago\t2024-01-01",
    ]
    with zipfile.ZipFile(geonames_zip, "w") as archive:
        archive.writestr("allCountries.txt", "\n".join(rows) + "\n")

    report = summarize_dominant_geonames_mapping_candidates(
        mapping_csv=mapping_csv,
        geonames_zip=geonames_zip,
        limit=10,
    )

    assert report["canonical_outputs_mutated"] is False
    assert report["geocoding_performed"] is False
    assert report["parseable_city_country_query_count"] == 2
    assert report["accepted_query_count"] == 1
    assert report["accepted_event_count"] == 10
    assert report["accepted_queries"][0]["query"] == "phoenix, us"
    assert report["accepted_queries"][0]["confidence"] == "high"
    assert report["accepted_queries"][0]["admin1"] == "AZ"
    assert report["rejected_queries_sample"][0]["query"] == "springfield, us"


def test_dominant_geonames_mapping_candidates_rejects_low_population_top_match(tmp_path):
    mapping_csv = tmp_path / "mapping.csv"
    mapping_csv.write_text("query,count,bucket\n\"smalltown, us\",5,city_region_like\n", encoding="utf-8")
    geonames_zip = tmp_path / "allCountries.zip"
    rows = [
        "1\tSmalltown\tSmalltown\t\t10\t20\tP\tPPL\tUS\t\tAA\t\t\t\t90000\t\t\tAmerica/New_York\t2024-01-01",
        "2\tSmalltown\tSmalltown\t\t11\t21\tP\tPPL\tUS\t\tBB\t\t\t\t1\t\t\tAmerica/New_York\t2024-01-01",
    ]
    with zipfile.ZipFile(geonames_zip, "w") as archive:
        archive.writestr("allCountries.txt", "\n".join(rows) + "\n")

    report = summarize_dominant_geonames_mapping_candidates(
        mapping_csv=mapping_csv,
        geonames_zip=geonames_zip,
        limit=10,
    )

    assert report["accepted_query_count"] == 0
    assert report["accepted_event_count"] == 0
    assert report["rejected_queries_sample"][0]["decision"] == "rejected_not_dominant_enough"
