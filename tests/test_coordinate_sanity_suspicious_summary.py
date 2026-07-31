from pathlib import Path

from scripts.summarize_coordinate_sanity_suspicious import summarize_coordinate_sanity_suspicious


def test_summarize_coordinate_sanity_suspicious_reports_remaining_out_of_country_rows(tmp_path: Path) -> None:
    input_path = tmp_path / "deduped_events.jsonl"
    countries_path = tmp_path / "countries.geojson"
    json_output = tmp_path / "summary.json"
    csv_output = tmp_path / "summary.csv"
    examples_output = tmp_path / "examples.csv"
    countries_path.write_text(
        """
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {"name": "United States of America"},
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[-125, 24], [-66, 24], [-66, 50], [-125, 50], [-125, 24]]]
      }
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )
    input_path.write_text(
        "\n".join(
            [
                '{"canonical_event_id":"inside","source_name":"ufocat","source_row_number":1,"source_native_id":"1","location_raw":"BROOKLYN, NY, US","date":"1954-05-01","country":"US","lat":40.6,"lon":-73.9,"coordinate_source":"raw_latlong","raw_fields":{"REGION":"US","STATE":"NY"}}',
                '{"canonical_event_id":"outside","source_name":"ufocat","source_row_number":2,"source_native_id":"2","location_raw":"BROOKLYN, NY, US","date":"1954-05-01","country":"US","lat":40.6,"lon":73.9,"coordinate_source":"raw_latlong","raw_fields":{"REGION":"US","STATE":"NY"}}',
                '{"canonical_event_id":"geocoded","source_name":"ufocat","country":"US","lat":40.6,"lon":73.9,"coordinate_source":"geocoded","raw_fields":{"REGION":"US","STATE":"NY"}}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = summarize_coordinate_sanity_suspicious(
        input_path=input_path,
        countries_geojson=countries_path,
        json_output=json_output,
        csv_output=csv_output,
        examples_output=examples_output,
    )

    assert report["canonical_outputs_mutated"] is False
    assert report["checked_exact_source_coordinate_events"] == 2
    assert report["suspicious_event_count"] == 1
    assert report["top_groups"][0]["country"] == "United States of America"
    assert report["top_groups"][0]["state_or_region"] == "NY"
    assert json_output.exists()
    assert csv_output.exists()
    assert "outside" in examples_output.read_text(encoding="utf-8")


def test_summarize_coordinate_sanity_suspicious_keeps_raw_regions_separate(tmp_path: Path) -> None:
    input_path = tmp_path / "deduped_events.jsonl"
    countries_path = tmp_path / "countries.geojson"
    json_output = tmp_path / "summary.json"
    csv_output = tmp_path / "summary.csv"
    examples_output = tmp_path / "examples.csv"
    countries_path.write_text(
        """
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {"name": "Russia"},
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[30, 40], [40, 40], [40, 50], [30, 50], [30, 40]]]
      }
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )
    input_path.write_text(
        "\n".join(
            [
                '{"canonical_event_id":"rus-eu","source_name":"ufocat","country":"EU","lat":60,"lon":60,"coordinate_source":"raw_latlong","raw_fields":{"REGION":"EU","STATE":"RUS"}}',
                '{"canonical_event_id":"rus-as","source_name":"ufocat","country":"AS","lat":61,"lon":120,"coordinate_source":"raw_latlong","raw_fields":{"REGION":"AS","STATE":"RUS"}}',
                '{"canonical_event_id":"rus-p","source_name":"ufocat","country":"P","lat":55,"lon":150,"coordinate_source":"raw_latlong","raw_fields":{"REGION":"P","STATE":"RUS"}}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = summarize_coordinate_sanity_suspicious(
        input_path=input_path,
        countries_geojson=countries_path,
        json_output=json_output,
        csv_output=csv_output,
        examples_output=examples_output,
    )

    regions = {row["raw_region"] for row in report["top_groups"]}
    assert report["suspicious_event_count"] == 3
    assert report["group_count"] == 3
    assert regions == {"EU", "AS", "P"}
