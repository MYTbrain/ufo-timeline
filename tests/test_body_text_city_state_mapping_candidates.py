import zipfile

from scripts.summarize_body_text_city_state_mapping_candidates import (
    summarize_body_text_city_state_mapping_candidates,
)


def test_body_text_city_state_candidates_are_event_level_and_require_explicit_evidence(tmp_path):
    input_path = tmp_path / "events.jsonl"
    input_path.write_text(
        "\n".join(
            [
                '{"canonical_event_id":"evt1","source_name":"nuforc","lat":null,"lon":null,"location_raw":"Columbus, US","coordinate_source":"unresolved","description":"UFOs in formation over Columbus Ohio at 8:45 pm."}',
                '{"canonical_event_id":"evt2","source_name":"nuforc","lat":null,"lon":null,"location_raw":"Columbus, US","coordinate_source":"unresolved","description":"Bright lights over Columbus with no state evidence."}',
                '{"canonical_event_id":"evt3","source_name":"nuforc","lat":null,"lon":null,"location_raw":"Springfield, US","coordinate_source":"unresolved","description":"Standing on the southwest side of Springfield IL."}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    mapping_csv = tmp_path / "coverage.csv"
    mapping_csv.write_text(
        "query,count,bucket\n"
        '"columbus, us",2,city_region_like\n'
        '"springfield, us",1,city_region_like\n',
        encoding="utf-8",
    )
    geonames_zip = tmp_path / "allCountries.zip"
    rows = [
        "1\tColumbus\tColumbus\t\t39.96118\t-82.99879\tP\tPPLA\tUS\t\tOH\t\t\t\t913175\t\t\tAmerica/New_York\t2024-01-01",
        "2\tColumbus\tColumbus\t\t32.46098\t-84.98771\tP\tPPLA2\tUS\t\tGA\t\t\t\t206922\t\t\tAmerica/New_York\t2024-01-01",
        "3\tSpringfield\tSpringfield\t\t39.80172\t-89.64371\tP\tPPLA\tUS\t\tIL\t\t\t\t114394\t\t\tAmerica/Chicago\t2024-01-01",
    ]
    with zipfile.ZipFile(geonames_zip, "w") as archive:
        archive.writestr("allCountries.txt", "\n".join(rows) + "\n")

    report = summarize_body_text_city_state_mapping_candidates(
        input_path=input_path,
        mapping_csv=mapping_csv,
        geonames_zip=geonames_zip,
    )

    assert report["canonical_outputs_mutated"] is False
    assert report["geocoding_performed"] is False
    assert report["candidate_event_count"] == 2
    assert report["resolved_event_count"] == 2
    assert [row["canonical_event_id"] for row in report["resolved_events"]] == ["evt1", "evt3"]
    assert [row["admin1"] for row in report["resolved_events"]] == ["OH", "IL"]
    assert report["rejected_event_counts"]["no_explicit_city_state_evidence"] == 1


def test_body_text_city_state_candidates_ignore_ambiguous_state_word_abbreviations(tmp_path):
    input_path = tmp_path / "events.jsonl"
    input_path.write_text(
        '{"canonical_event_id":"evt1","source_name":"nuforc","lat":null,"lon":null,"location_raw":"Salem, US","coordinate_source":"unresolved","description":"Lights over Salem or nearby."}\n',
        encoding="utf-8",
    )
    mapping_csv = tmp_path / "coverage.csv"
    mapping_csv.write_text("query,count,bucket\n\"salem, us\",1,city_region_like\n", encoding="utf-8")
    geonames_zip = tmp_path / "allCountries.zip"
    with zipfile.ZipFile(geonames_zip, "w") as archive:
        archive.writestr(
            "allCountries.txt",
            "1\tSalem\tSalem\t\t44.9429\t-123.0351\tP\tPPLA\tUS\t\tOR\t\t\t\t175535\t\t\tAmerica/Los_Angeles\t2024-01-01\n",
        )

    report = summarize_body_text_city_state_mapping_candidates(
        input_path=input_path,
        mapping_csv=mapping_csv,
        geonames_zip=geonames_zip,
    )

    assert report["candidate_event_count"] == 0
    assert report["resolved_event_count"] == 0


def test_body_text_city_state_candidates_require_primary_geonames_name_match(tmp_path):
    input_path = tmp_path / "events.jsonl"
    input_path.write_text(
        '{"canonical_event_id":"evt1","source_name":"nuforc","lat":null,"lon":null,"location_raw":"Dawsonville, US","coordinate_source":"unresolved","description":"Saw lights in Dawsonville, GA."}\n',
        encoding="utf-8",
    )
    mapping_csv = tmp_path / "coverage.csv"
    mapping_csv.write_text("query,count,bucket\n\"dawsonville, us\",1,city_region_like\n", encoding="utf-8")
    geonames_zip = tmp_path / "allCountries.zip"
    with zipfile.ZipFile(geonames_zip, "w") as archive:
        archive.writestr(
            "allCountries.txt",
            "1\tCalhoun\tCalhoun\tDawsonville\t34.50259\t-84.95105\tP\tPPL\tUS\t\tGA\t\t\t\t17000\t\t\tAmerica/New_York\t2024-01-01\n",
        )

    report = summarize_body_text_city_state_mapping_candidates(
        input_path=input_path,
        mapping_csv=mapping_csv,
        geonames_zip=geonames_zip,
    )

    assert report["candidate_event_count"] == 1
    assert report["resolved_event_count"] == 0
    assert report["rejected_event_counts"]["geonames_city_state_not_found"] == 1
