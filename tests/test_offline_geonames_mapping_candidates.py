import zipfile

from scripts.summarize_offline_geonames_mapping_candidates import summarize_offline_geonames_mapping_candidates


def test_offline_geonames_mapping_candidates_matches_city_state_country(tmp_path):
    mapping_csv = tmp_path / "mapping.csv"
    mapping_csv.write_text(
        "query,count,bucket\n"
        "\"phoenix, az, us\",10,city_state_country_like\n"
        "\"springfield, us\",7,city_region_like\n",
        encoding="utf-8",
    )
    geonames_zip = tmp_path / "allCountries.zip"
    rows = [
        "1\tPhoenix\tPhoenix\t\t33.4484\t-112.074\tP\tPPLA\tUS\t\tAZ\t\t\t\t1600000\t\t\tAmerica/Phoenix\t2024-01-01",
        "2\tSpringfield\tSpringfield\t\t39.78\t-89.64\tP\tPPLA\tUS\t\tIL\t\t\t\t114000\t\t\tAmerica/Chicago\t2024-01-01",
        "3\tSpringfield\tSpringfield\t\t37.20\t-93.29\tP\tPPL\tUS\t\tMO\t\t\t\t169000\t\t\tAmerica/Chicago\t2024-01-01",
    ]
    with zipfile.ZipFile(geonames_zip, "w") as archive:
        archive.writestr("allCountries.txt", "\n".join(rows) + "\n")

    report = summarize_offline_geonames_mapping_candidates(
        mapping_csv=mapping_csv,
        geonames_zip=geonames_zip,
        limit=10,
    )

    assert report["canonical_outputs_mutated"] is False
    assert report["geocoding_performed"] is False
    assert report["resolved_query_count"] == 2
    assert report["high_or_medium_confidence_event_count"] == 10
    assert report["resolved_queries"][0]["query"] == "phoenix, az, us"
    assert report["resolved_queries"][0]["confidence"] == "high"
    assert report["resolved_queries"][1]["query"] == "springfield, us"
    assert report["resolved_queries"][1]["confidence"] == "low"


def test_offline_geonames_mapping_candidates_translates_canadian_admin_codes_and_parentheses(tmp_path):
    mapping_csv = tmp_path / "mapping.csv"
    mapping_csv.write_text(
        "query,count,bucket\n"
        "\"toronto, on, ca\",10,city_state_country_like\n"
        "\"toronto (canada), on, canada\",5,city_state_country_like\n",
        encoding="utf-8",
    )
    geonames_zip = tmp_path / "allCountries.zip"
    rows = [
        "10\tToronto\tToronto\t\t43.65348\t-79.38393\tP\tPPLA\tCA\t\t08\t\t\t\t2600000\t\t\tAmerica/Toronto\t2024-01-01",
    ]
    with zipfile.ZipFile(geonames_zip, "w") as archive:
        archive.writestr("allCountries.txt", "\n".join(rows) + "\n")

    report = summarize_offline_geonames_mapping_candidates(
        mapping_csv=mapping_csv,
        geonames_zip=geonames_zip,
        limit=10,
    )

    assert report["resolved_query_count"] == 2
    assert report["high_or_medium_confidence_event_count"] == 15
    assert [row["confidence"] for row in report["resolved_queries"]] == ["high", "high"]


def test_offline_geonames_mapping_candidates_handles_parenthetical_commas_and_country_context(tmp_path):
    mapping_csv = tmp_path / "mapping.csv"
    mapping_csv.write_text(
        "query,count,bucket\n"
        "\"melbourne (vic, australia), , australia\",7,city_state_country_like\n"
        "\"toronto (canada), ca\",5,city_region_like\n",
        encoding="utf-8",
    )
    geonames_zip = tmp_path / "allCountries.zip"
    rows = [
        "20\tMelbourne\tMelbourne\t\t-37.814\t144.96332\tP\tPPLA\tAU\t\t07\t\t\t\t5350705\t\t\tAustralia/Melbourne\t2024-01-01",
        "21\tToronto\tToronto\t\t43.65348\t-79.38393\tP\tPPLA\tCA\t\t08\t\t\t\t2794356\t\t\tAmerica/Toronto\t2024-01-01",
        "22\tToronto\tToronto\t\t46.45012\t-63.382\tP\tPPL\tCA\t\t09\t\t\t\t0\t\t\tAmerica/Halifax\t2024-01-01",
    ]
    with zipfile.ZipFile(geonames_zip, "w") as archive:
        archive.writestr("allCountries.txt", "\n".join(rows) + "\n")

    report = summarize_offline_geonames_mapping_candidates(
        mapping_csv=mapping_csv,
        geonames_zip=geonames_zip,
        limit=10,
    )

    assert report["resolved_query_count"] == 2
    assert report["high_or_medium_confidence_event_count"] == 12
    assert report["resolved_queries"][0]["confidence"] == "high"
    assert report["resolved_queries"][0]["admin1"] == "07"
    assert report["resolved_queries"][1]["confidence"] == "medium"


def test_offline_geonames_mapping_candidates_does_not_promote_zero_population_admin_match(tmp_path):
    mapping_csv = tmp_path / "mapping.csv"
    mapping_csv.write_text(
        "query,count,bucket\n"
        "\"kent (uk/england), , united kingdom\",4,city_state_country_like\n",
        encoding="utf-8",
    )
    geonames_zip = tmp_path / "allCountries.zip"
    rows = [
        "30\tKent\tKent\t\t51.25\t0.75\tP\tPPL\tGB\t\tENG\t\t\t\t0\t\t\tEurope/London\t2024-01-01",
        "31\tKent\tKent\t\t52.2\t-1.2\tP\tPPL\tGB\t\tENG\t\t\t\t0\t\t\tEurope/London\t2024-01-01",
    ]
    with zipfile.ZipFile(geonames_zip, "w") as archive:
        archive.writestr("allCountries.txt", "\n".join(rows) + "\n")

    report = summarize_offline_geonames_mapping_candidates(
        mapping_csv=mapping_csv,
        geonames_zip=geonames_zip,
        limit=10,
    )

    assert report["resolved_query_count"] == 1
    assert report["high_or_medium_confidence_event_count"] == 0
    assert report["resolved_queries"][0]["confidence"] == "low"


def test_offline_geonames_mapping_candidates_does_not_treat_descriptive_parenthetical_as_location_context(tmp_path):
    mapping_csv = tmp_path / "mapping.csv"
    mapping_csv.write_text(
        "query,count,bucket\n"
        "\"las vegas (north of), us\",6,city_region_like\n",
        encoding="utf-8",
    )
    geonames_zip = tmp_path / "allCountries.zip"
    rows = [
        "40\tLas Vegas\tLas Vegas\t\t36.17497\t-115.13722\tP\tPPL\tUS\t\tNV\t\t\t\t641903\t\t\tAmerica/Los_Angeles\t2024-01-01",
        "41\tLas Vegas\tLas Vegas\t\t35.59393\t-105.2239\tP\tPPL\tUS\t\tNM\t\t\t\t13000\t\t\tAmerica/Denver\t2024-01-01",
    ]
    with zipfile.ZipFile(geonames_zip, "w") as archive:
        archive.writestr("allCountries.txt", "\n".join(rows) + "\n")

    report = summarize_offline_geonames_mapping_candidates(
        mapping_csv=mapping_csv,
        geonames_zip=geonames_zip,
        limit=10,
    )

    assert report["resolved_query_count"] == 1
    assert report["high_or_medium_confidence_event_count"] == 0
    assert report["resolved_queries"][0]["confidence"] == "low"
