import zipfile

from scripts.summarize_structured_city_alias_geonames_mapping_candidates import (
    summarize_structured_city_alias_geonames_mapping_candidates,
)


def test_structured_city_alias_candidates_accept_common_aliases_with_admin_country(tmp_path):
    mapping_csv = tmp_path / "mapping.csv"
    mapping_csv.write_text(
        "query,count,bucket\n"
        "\"ft. worth, tx, us\",10,city_state_country_like\n"
        "\"st petersburg, fl, us\",7,city_state_country_like\n"
        "\"mt. vernon, in, usa\",5,city_state_country_like\n"
        "\"washington, d.c., us\",3,city_state_country_like\n"
        "\"springfield, us\",99,city_region_like\n",
        encoding="utf-8",
    )
    geonames_zip = tmp_path / "allCountries.zip"
    rows = [
        "1\tFort Worth\tFort Worth\t\t32.725\t-97.320\tP\tPPLA2\tUS\t\tTX\t\t\t\t918915\t\t\tAmerica/Chicago\t2024-01-01",
        "2\tSaint Petersburg\tSaint Petersburg\tSt. Petersburg\t27.770\t-82.679\tP\tPPL\tUS\t\tFL\t\t\t\t258308\t\t\tAmerica/New_York\t2024-01-01",
        "3\tMount Vernon\tMount Vernon\tMt Vernon\t37.932\t-87.895\tP\tPPL\tUS\t\tIN\t\t\t\t6500\t\t\tAmerica/Chicago\t2024-01-01",
        "4\tWashington\tWashington\t\t38.895\t-77.036\tP\tPPLC\tUS\t\tDC\t\t\t\t689545\t\t\tAmerica/New_York\t2024-01-01",
    ]
    with zipfile.ZipFile(geonames_zip, "w") as archive:
        archive.writestr("allCountries.txt", "\n".join(rows) + "\n")

    report = summarize_structured_city_alias_geonames_mapping_candidates(
        mapping_csv=mapping_csv,
        geonames_zip=geonames_zip,
        limit=10,
    )

    assert report["canonical_outputs_mutated"] is False
    assert report["geocoding_performed"] is False
    assert report["parseable_structured_query_count"] == 4
    assert report["resolved_query_count"] == 4
    assert report["high_confidence_event_count"] == 25
    assert {row["query"] for row in report["resolved_queries"]} == {
        "ft. worth, tx, us",
        "st petersburg, fl, us",
        "mt. vernon, in, usa",
        "washington, d.c., us",
    }


def test_structured_city_alias_candidates_reject_city_country_only(tmp_path):
    mapping_csv = tmp_path / "mapping.csv"
    mapping_csv.write_text("query,count,bucket\n\"ft worth, us\",10,city_region_like\n", encoding="utf-8")
    geonames_zip = tmp_path / "allCountries.zip"
    rows = [
        "1\tFort Worth\tFort Worth\t\t32.725\t-97.320\tP\tPPLA2\tUS\t\tTX\t\t\t\t918915\t\t\tAmerica/Chicago\t2024-01-01",
    ]
    with zipfile.ZipFile(geonames_zip, "w") as archive:
        archive.writestr("allCountries.txt", "\n".join(rows) + "\n")

    report = summarize_structured_city_alias_geonames_mapping_candidates(
        mapping_csv=mapping_csv,
        geonames_zip=geonames_zip,
        limit=10,
    )

    assert report["parseable_structured_query_count"] == 0
    assert report["resolved_query_count"] == 0
