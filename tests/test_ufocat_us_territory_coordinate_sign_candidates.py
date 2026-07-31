import json

from scripts.summarize_ufocat_us_territory_coordinate_sign_candidates import (
    summarize_ufocat_us_territory_coordinate_sign_candidates,
)


def test_ufocat_us_territory_report_flags_bounded_usvi_sign_candidates(tmp_path):
    input_path = tmp_path / "events.jsonl"
    input_path.write_text(
        "\n".join(
            [
                '{"canonical_event_id":"usvi","source_name":"ufocat","source_row_number":1,"source_native_id":"1","date_iso":"2020-01-01","location_raw":"ST THOMAS, US VIRGIN ISLANDS, St Thomas, ISV, CA","state_province":"ISV","country":"CA","lat":18.33,"lon":64.92,"coordinate_source":"source_coordinates","raw_fields":{"REGION":"CA","STATE":"ISV","LOCATION":"ST THOMAS, US VIRGIN ISLANDS"}}',
                '{"canonical_event_id":"jamaica","source_name":"ufocat","source_row_number":2,"source_native_id":"2","date_iso":"2020-01-01","location_raw":"CLARKS TOWN, ST THOMAS, JAM, CA","state_province":"JAM","country":"CA","lat":18.41,"lon":77.54,"coordinate_source":"source_coordinates","raw_fields":{"REGION":"CA","STATE":"JAM","LOCATION":"CLARKS TOWN"}}',
                '{"canonical_event_id":"guam","source_name":"ufocat","source_row_number":3,"source_native_id":"3","date_iso":"2020-01-01","location_raw":"GUAM, P","state_province":"GUA","country":"P","lat":13.44,"lon":144.79,"coordinate_source":"source_coordinates","raw_fields":{"REGION":"P","STATE":"GUA","LOCATION":"GUAM"}}',
                '{"canonical_event_id":"not-source","source_name":"ufocat","source_row_number":4,"source_native_id":"4","date_iso":"2020-01-01","location_raw":"ST THOMAS, US VIRGIN ISLANDS","state_province":"ISV","country":"CA","lat":18.33,"lon":64.92,"coordinate_source":"geocoded","raw_fields":{"REGION":"CA","STATE":"ISV"}}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = summarize_ufocat_us_territory_coordinate_sign_candidates(
        input_path=input_path,
        json_output=tmp_path / "report.json",
        csv_output=tmp_path / "report.csv",
    )

    assert report["canonical_outputs_mutated"] is False
    assert report["preview_outputs_mutated"] is False
    assert report["candidate_event_count"] == 1
    assert report["territory_counts"] == {"us_virgin_islands": 1}
    assert report["candidates"][0]["canonical_event_id"] == "usvi"
    assert report["candidates"][0]["candidate_lon"] == -64.92

    csv_text = (tmp_path / "report.csv").read_text(encoding="utf-8")
    assert "usvi" in csv_text
    assert "jamaica" not in csv_text
