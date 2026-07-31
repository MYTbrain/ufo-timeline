from pathlib import Path

from parser.event_parser import parse_events_from_text


FIXTURE = Path(__file__).parent / "fixtures" / "sample_ufo_input.txt"


def test_event_parser_preserves_multiline_content_and_unknown_lines():
    events, failures = parse_events_from_text(FIXTURE.read_text(encoding="utf-8"), source_file="sample_ufo_input.txt")

    assert not failures
    assert len(events) == 5

    first = events[0]
    assert first["event_id"] == 100
    assert "Second paragraph preserves line breaks" in first["description"]
    assert first["references"] == ["Sample Ref 1", "Sample Ref 2"]
    assert first["source"] == "SampleSource"
    assert first["source_id"] == "Sample_1"
    assert first["attributes_codes"] == ["GND", "NLT"]
    assert first["extra_data"]["LatLong"] == "33.3943 -104.5230"

    second = events[1]
    assert second["location_field_name"] == "Locations"
    assert second["all_locations_raw"] == ["Holloman AFB", "Corona, New Mexico"]
    assert second["links"] == ["https://example.com/holloman"]
    assert second["extra_data"]["event_fields"]["Alternate date"] == "Late 7/1947"
    assert second["extra_data"]["event_fields"]["Note"] == "Multi-location case."
    assert "Mystery Label: Keep this line for review." in second["extra_data"]["unparsed_lines"]
    assert any("unknown field label" in warning.lower() for warning in second["parse_warnings"])

    fifth = events[4]
    assert fifth["source"] is None
    assert fifth["references"] == ["Embedded DMS"]


def test_event_parser_tracks_timeline_year_heading_for_ambiguous_dates():
    events, _ = parse_events_from_text(FIXTURE.read_text(encoding="utf-8"), source_file="sample_ufo_input.txt")
    assert events[0]["extra_data"]["timeline_year_heading"] == "1947"
    assert events[3]["extra_data"]["timeline_year_heading"] == "1980"
