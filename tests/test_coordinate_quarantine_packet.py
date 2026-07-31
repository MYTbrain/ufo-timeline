from pathlib import Path

from scripts.build_coordinate_quarantine_packet import build_coordinate_quarantine_packet


def test_coordinate_quarantine_packet_separates_bounds_failures_from_polygon_review(tmp_path: Path) -> None:
    input_path = tmp_path / "deduped_events.jsonl"
    countries_path = tmp_path / "countries.geojson"
    json_output = tmp_path / "packet.json"
    csv_output = tmp_path / "packet.csv"
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
        "coordinates": [[[-125, 26], [-66, 26], [-66, 50], [-125, 50], [-125, 26]]]
      }
    },
    {
      "type": "Feature",
      "properties": {"name": "Austria"},
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[10, 47], [11, 47], [11, 49], [10, 49], [10, 47]]]
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
                '{"canonical_event_id":"inside","source_name":"ufocat","source_row_number":1,"location_raw":"BROOKLYN, NY, US","country":"US","lat":40.6,"lon":-73.9,"coordinate_source":"raw_latlong","raw_fields":{"REGION":"US","STATE":"NY"}}',
                '{"canonical_event_id":"coastal","source_name":"ufocat","source_row_number":2,"location_raw":"MIAMI BEACH, FL, US","country":"US","lat":25.78,"lon":-80.12,"coordinate_source":"raw_latlong","raw_fields":{"REGION":"US","STATE":"FL"}}',
                '{"canonical_event_id":"bad","source_name":"ufocat","source_row_number":3,"location_raw":"PALATINE, IL, US","country":"US","lat":21.1,"lon":88.05,"coordinate_source":"raw_latlong","raw_fields":{"REGION":"US","STATE":"IL"}}',
                '{"canonical_event_id":"austria_review","source_name":"ufocat","source_row_number":4,"location_raw":"BRENNER PASS, Tirol, AUT, EU","country":"EU","state_province":"AUT","lat":47.0,"lon":11.52,"coordinate_source":"raw_latlong","raw_fields":{"REGION":"EU","STATE":"AUT"}}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = build_coordinate_quarantine_packet(
        input_path=input_path,
        countries_geojson=countries_path,
        json_output=json_output,
        csv_output=csv_output,
    )

    assert report["canonical_outputs_mutated"] is False
    assert report["summary"]["suspicious_event_count"] == 3
    assert report["summary"]["quarantine_candidate_count"] == 1
    assert report["summary"]["display_safe_review_count"] == 2
    assert report["summary"]["manual_review_count"] == 0
    assert report["top_quarantine_candidates"][0]["canonical_event_id"] == "bad"
    assert json_output.exists()
    assert "quarantine_until_review" in csv_output.read_text(encoding="utf-8")
