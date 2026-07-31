import json
import zipfile

from scripts.summarize_structured_long_tail_geonames_mapping_candidates import (
    summarize_structured_long_tail_geonames_mapping_candidates,
)


def test_structured_long_tail_accepts_explicit_admin_country_rows(tmp_path):
    events = tmp_path / "events.jsonl"
    events.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "canonical_event_id": "evt1",
                        "source_name": "ufocat",
                        "lat": None,
                        "lon": None,
                        "location_raw": "Bangalore, , IN",
                    }
                ),
                json.dumps(
                    {
                        "canonical_event_id": "evt2",
                        "source_name": "mufon",
                        "lat": None,
                        "lon": None,
                        "location_raw": "Phoenix, AZ, US",
                    }
                ),
                json.dumps(
                    {
                        "canonical_event_id": "evt3",
                        "source_name": "nuforc",
                        "lat": None,
                        "lon": None,
                        "location_raw": "US",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    geonames_zip = tmp_path / "allCountries.zip"
    with zipfile.ZipFile(geonames_zip, "w") as archive:
        archive.writestr(
            "allCountries.txt",
            "\n".join(
                [
                    _geonames_row("1", "Bengaluru", "Bengaluru", "Bangalore", 12.97194, 77.59369, "IN", "19", 8400000),
                    _geonames_row("2", "Phoenix", "Phoenix", "Phoenix", 33.45, -112.07, "US", "AZ", 1600000),
                ]
            )
            + "\n",
        )
    country_info = tmp_path / "countryInfo.txt"
    country_info.write_text(
        "IN\tIND\t356\tIN\tIndia\n"
        "US\tUSA\t840\tUS\tUnited States\n",
        encoding="utf-8",
    )

    report = summarize_structured_long_tail_geonames_mapping_candidates(
        input_path=events,
        geonames_zip=geonames_zip,
        country_info=country_info,
        limit=0,
    )

    rows = {row["query"]: row for row in report["resolved_queries"]}
    assert rows["bangalore, , in"]["confidence"] == "high"
    assert rows["bangalore, , in"]["country_code"] == "IN"
    assert rows["phoenix, az, us"]["confidence"] == "high"
    assert rows["phoenix, az, us"]["admin1"] == "AZ"
    assert report["high_or_medium_confidence_event_count"] == 2


def test_structured_long_tail_rejects_us_without_state(tmp_path):
    events = tmp_path / "events.jsonl"
    events.write_text(
        json.dumps(
            {
                "canonical_event_id": "evt1",
                "source_name": "mufon",
                "lat": None,
                "lon": None,
                "location_raw": "Springfield, US",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    geonames_zip = tmp_path / "allCountries.zip"
    with zipfile.ZipFile(geonames_zip, "w") as archive:
        archive.writestr("allCountries.txt", "")
    country_info = tmp_path / "countryInfo.txt"
    country_info.write_text("US\tUSA\t840\tUS\tUnited States\n", encoding="utf-8")

    report = summarize_structured_long_tail_geonames_mapping_candidates(
        input_path=events,
        geonames_zip=geonames_zip,
        country_info=country_info,
        limit=0,
    )

    assert report["query_count"] == 0
    assert report["resolved_query_count"] == 0


def test_structured_long_tail_rejects_short_region_and_country_conflict(tmp_path):
    events = tmp_path / "events.jsonl"
    events.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "canonical_event_id": "evt1",
                        "source_name": "mufon",
                        "lat": None,
                        "lon": None,
                        "location_raw": "NS, CN",
                    }
                ),
                json.dumps(
                    {
                        "canonical_event_id": "evt2",
                        "source_name": "mufon",
                        "lat": None,
                        "lon": None,
                        "location_raw": "St. John's (Canada), AU",
                    }
                ),
                json.dumps(
                    {
                        "canonical_event_id": "evt3",
                        "source_name": "ufocat",
                        "lat": None,
                        "lon": None,
                        "location_raw": "Scotland, GBR, EU",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    geonames_zip = tmp_path / "allCountries.zip"
    with zipfile.ZipFile(geonames_zip, "w") as archive:
        archive.writestr("allCountries.txt", "")
    country_info = tmp_path / "countryInfo.txt"
    country_info.write_text(
        "AU\tAUS\t036\tAU\tAustralia\n"
        "CA\tCAN\t124\tCA\tCanada\n"
        "CN\tCHN\t156\tCN\tChina\n"
        "GB\tGBR\t826\tUK\tUnited Kingdom\n",
        encoding="utf-8",
    )

    report = summarize_structured_long_tail_geonames_mapping_candidates(
        input_path=events,
        geonames_zip=geonames_zip,
        country_info=country_info,
        limit=0,
    )

    assert report["query_count"] == 0
    assert report["resolved_query_count"] == 0


def test_structured_long_tail_rejects_two_part_us_state_country_ambiguity(tmp_path):
    events = tmp_path / "events.jsonl"
    events.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "canonical_event_id": "evt1",
                        "source_name": "mufon",
                        "lat": None,
                        "lon": None,
                        "location_raw": "Salem, MA",
                    }
                ),
                json.dumps(
                    {
                        "canonical_event_id": "evt2",
                        "source_name": "mufon",
                        "lat": None,
                        "lon": None,
                        "location_raw": "Haifa, IL",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    geonames_zip = tmp_path / "allCountries.zip"
    with zipfile.ZipFile(geonames_zip, "w") as archive:
        archive.writestr("allCountries.txt", "")
    country_info = tmp_path / "countryInfo.txt"
    country_info.write_text(
        "IL\tISR\t376\tIL\tIsrael\n"
        "MA\tMAR\t504\tMA\tMorocco\n",
        encoding="utf-8",
    )

    report = summarize_structured_long_tail_geonames_mapping_candidates(
        input_path=events,
        geonames_zip=geonames_zip,
        country_info=country_info,
        limit=0,
    )

    assert report["query_count"] == 0
    assert report["resolved_query_count"] == 0


def _geonames_row(
    geoname_id,
    name,
    ascii_name,
    alternates,
    lat,
    lon,
    country,
    admin1,
    population,
):
    fields = [
        geoname_id,
        name,
        ascii_name,
        alternates,
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
        "UTC",
        "2024-01-01",
    ]
    return "\t".join(fields)
