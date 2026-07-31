import json
from pathlib import Path

from scripts.apply_coordinate_residual_risk_preview import apply_coordinate_residual_risk_preview


def _write_countries(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"name": "United States of America"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[-125, 24], [-66, 24], [-66, 50], [-125, 50], [-125, 24]]],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {"name": "Brazil"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[-75, -35], [-34, -35], [-34, 6], [-75, 6], [-75, -35]]],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {"name": "Georgia"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[39, 41], [47, 41], [47, 44], [39, 44], [39, 41]]],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {"name": "Canada"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[-142, 41], [-52, 41], [-52, 84], [-142, 84], [-142, 41]]],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {"name": "Zimbabwe"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[25, -23], [34, -23], [34, -15], [25, -15], [25, -23]]],
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def test_residual_risk_preview_unmaps_wrong_hemisphere_but_keeps_valid_country_row(tmp_path: Path) -> None:
    input_path = tmp_path / "deduped_events.jsonl"
    countries_path = tmp_path / "countries.geojson"
    output_dir = tmp_path / "out"
    report_output = tmp_path / "report.json"
    _write_countries(countries_path)
    input_path.write_text(
        "\n".join(
            [
                '{"canonical_event_id":"bad","source_name":"ufocat","location_raw":"RIO, BRA, SA","lat":-22.9,"lon":43.2,"coordinate_source":"source_coordinates","location_precision":"exact_coords","raw_fields":{"REGION":"SA","STATE":"BRA"}}',
                '{"canonical_event_id":"good","source_name":"ufocat","location_raw":"RIO, BRA, SA","lat":-22.9,"lon":-43.2,"coordinate_source":"source_coordinates","location_precision":"exact_coords","raw_fields":{"REGION":"SA","STATE":"BRA"}}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = apply_coordinate_residual_risk_preview(
        input_path=input_path,
        countries_geojson=countries_path,
        output_dir=output_dir,
        report_output=report_output,
    )
    rows = [json.loads(line) for line in (output_dir / "deduped_events.jsonl").read_text(encoding="utf-8").splitlines()]

    assert report["quarantined_event_count"] == 1
    assert rows[0]["coordinate_residual_quarantine_reason"] == "positive_longitude_for_western_hemisphere_country"
    assert rows[0]["lat"] is None
    assert rows[1]["lat"] == -22.9
    assert rows[1]["lon"] == -43.2


def test_residual_risk_preview_keeps_full_us_state_name_when_country_is_usa(tmp_path: Path) -> None:
    input_path = tmp_path / "deduped_events.jsonl"
    countries_path = tmp_path / "countries.geojson"
    output_dir = tmp_path / "out"
    report_output = tmp_path / "report.json"
    _write_countries(countries_path)
    input_path.write_text(
        '{"canonical_event_id":"ga-us","source_name":"majestic","location_raw":"HOUSTON CO, GA, Georgia, USA","lat":32.43,"lon":-83.65,"coordinate_source":"source_coordinates","location_precision":"exact_coords","raw_fields":{"REGION":"USA","STATE":"Georgia"}}\n',
        encoding="utf-8",
    )

    report = apply_coordinate_residual_risk_preview(
        input_path=input_path,
        countries_geojson=countries_path,
        output_dir=output_dir,
        report_output=report_output,
    )
    rows = [json.loads(line) for line in (output_dir / "deduped_events.jsonl").read_text(encoding="utf-8").splitlines()]

    assert report["quarantined_event_count"] == 0
    assert rows[0]["lat"] == 32.43
    assert rows[0]["lon"] == -83.65


def test_residual_risk_preview_unmaps_canadian_province_mismatch(tmp_path: Path) -> None:
    input_path = tmp_path / "deduped_events.jsonl"
    countries_path = tmp_path / "countries.geojson"
    output_dir = tmp_path / "out"
    report_output = tmp_path / "report.json"
    _write_countries(countries_path)
    input_path.write_text(
        "\n".join(
            [
                '{"canonical_event_id":"bc-good","source_name":"ufocat","location_raw":"VANCOUVER, Vancouver, BC, CN","country":"CN","state_province":"BC","lat":49.27,"lon":-123.09,"coordinate_source":"source_coordinates","location_precision":"exact_coords","raw_fields":{"REGION":"CN","STATE":"BC"}}',
                '{"canonical_event_id":"bc-bad","source_name":"ufocat","location_raw":"VANCOUVER, Vancouver, BC, CN","country":"CN","state_province":"BC","lat":49.27,"lon":-63.09,"coordinate_source":"source_coordinates","location_precision":"exact_coords","raw_fields":{"REGION":"CN","STATE":"BC"}}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = apply_coordinate_residual_risk_preview(
        input_path=input_path,
        countries_geojson=countries_path,
        output_dir=output_dir,
        report_output=report_output,
    )
    rows = [json.loads(line) for line in (output_dir / "deduped_events.jsonl").read_text(encoding="utf-8").splitlines()]

    assert report["quarantined_event_count"] == 1
    assert rows[0]["lat"] == 49.27
    assert rows[0]["lon"] == -123.09
    assert rows[1]["coordinate_residual_quarantine_reason"] == "canadian_province_coordinate_outside_review_bounds"
    assert rows[1]["lat"] is None


def test_residual_risk_preview_unmaps_zimbabwe_coordinate_outside_review_bounds(tmp_path: Path) -> None:
    input_path = tmp_path / "deduped_events.jsonl"
    countries_path = tmp_path / "countries.geojson"
    output_dir = tmp_path / "out"
    report_output = tmp_path / "report.json"
    _write_countries(countries_path)
    input_path.write_text(
        "\n".join(
            [
                '{"canonical_event_id":"zimbabwe-good","source_name":"ufocat","location_raw":"MUTARE, Mashona East, ZIM, AF","country":"AF","state_province":"ZIM","lat":-18.97,"lon":32.67,"coordinate_source":"source_coordinates","location_precision":"exact_coords","raw_fields":{"REGION":"AF","STATE":"ZIM"}}',
                '{"canonical_event_id":"zimbabwe-bad","source_name":"ufocat","location_raw":"CHINHOYI E, ZIM, AF","country":"AF","state_province":"ZIM","lat":43.33,"lon":3.0,"coordinate_source":"source_coordinates","location_precision":"exact_coords","raw_fields":{"REGION":"AF","STATE":"ZIM"}}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = apply_coordinate_residual_risk_preview(
        input_path=input_path,
        countries_geojson=countries_path,
        output_dir=output_dir,
        report_output=report_output,
    )
    rows = [json.loads(line) for line in (output_dir / "deduped_events.jsonl").read_text(encoding="utf-8").splitlines()]

    assert report["quarantined_event_count"] == 1
    assert rows[0]["lat"] == -18.97
    assert rows[0]["lon"] == 32.67
    assert rows[1]["coordinate_residual_quarantine_reason"] == "zimbabwe_coordinate_outside_review_bounds"
    assert rows[1]["lat"] is None
