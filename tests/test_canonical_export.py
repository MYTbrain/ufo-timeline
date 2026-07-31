from parser.canonical_export import (
    CANONICAL_EVENT_ID_OFFSET,
    canonical_event_to_normalized_event,
    canonical_events_to_normalized_events,
)
from parser.canonical_schema import CanonicalInputRecord
from parser.dedupe import build_deduped_events


def test_mapped_canonical_event_exports_existing_normalized_shape():
    record = CanonicalInputRecord(
        canonical_input_id="cin_roswell",
        source_name="nuforc",
        source_file="nuforcpy.csv",
        source_row_number=7,
        source_native_id="NUF-1",
        source_row_hash="rowhash-1",
        date_raw="7/8/1947",
        date_iso="1947-07-08",
        sort_date_iso="1947-07-08",
        date_precision="exact_day",
        time_raw="23:15",
        location_raw="Roswell, NM, USA",
        lat=33.3943,
        lon=-104.523,
        coordinate_source="source_coordinates",
        location_precision="coordinate",
        type_raw="Landing",
        type_normalized="landing",
        shape_raw="Disc",
        description="Witnesses saw a disc descend near the ranch.",
        summary="Disc descends near Roswell",
        source_url="https://example.test/nuforc/NUF-1",
        raw_fields={"No": "NUF-1"},
    )
    deduped_events, _ = build_deduped_events([record])

    event = canonical_event_to_normalized_event(deduped_events[0])
    again = canonical_event_to_normalized_event(deduped_events[0])

    assert event["event_id"] == again["event_id"]
    assert event["event_hash"] == again["event_hash"]
    assert event["event_id"] >= CANONICAL_EVENT_ID_OFFSET
    assert event["canonical_event_id"] == deduped_events[0]["canonical_event_id"]
    assert event["canonical_input_ids"] == ["cin_roswell"]
    assert event["source_provenance"][0]["canonical_input_id"] == "cin_roswell"
    assert event["source_file"] == "nuforcpy.csv"
    assert event["source"] == "nuforc"
    assert event["source_id"] == "NUF-1"
    assert event["date_raw"] == "7/8/1947"
    assert event["date_iso"] == "1947-07-08"
    assert event["time_raw"] == "23:15"
    assert event["location_raw"] == "Roswell, NM, USA"
    assert event["all_locations_raw"] == ["Roswell, NM, USA"]
    assert event["type"] == "Landing"
    assert event["lat"] == 33.3943
    assert event["lon"] == -104.523
    assert event["coordinate_source"] == "raw_latlong"
    assert event["location_precision"] == "exact_coords"
    assert event["primary_location_text"] == "Roswell, NM, USA"
    assert event["links"] == ["https://example.test/nuforc/NUF-1"]
    assert event["extra_data"]["canonical"]["raw_fields"] == {"No": "NUF-1"}


def test_unmapped_canonical_record_stays_unresolved_but_compatible():
    record = CanonicalInputRecord(
        canonical_input_id="cin_ottawa",
        source_name="phenomenainon_updb",
        source_file="phenomenAInon_UPDB.csv",
        source_row_number=12,
        source_native_id="5182466",
        source_row_hash="rowhash-2",
        date_raw="1993-05-20",
        date_iso="1993-05-20",
        sort_date_iso="1993-05-20",
        date_precision="day",
        time_raw="00:00:00",
        location_raw="Ottawa, CA",
        type_raw="NICAP",
        description="Airliner crew saw a triangle.",
    )

    event = canonical_event_to_normalized_event(record)

    assert isinstance(event["event_id"], int)
    assert event["event_id"] >= CANONICAL_EVENT_ID_OFFSET
    assert event["event_hash"]
    assert event["canonical_event_id"] is None
    assert event["canonical_input_ids"] == ["cin_ottawa"]
    assert event["source_provenance"] == [
        {
            "source_name": "phenomenainon_updb",
            "source_file": "phenomenAInon_UPDB.csv",
            "source_row_number": 12,
            "source_native_id": "5182466",
            "source_row_hash": "rowhash-2",
            "canonical_input_id": "cin_ottawa",
        }
    ]
    assert event["lat"] is None
    assert event["lon"] is None
    assert event["coordinate_source"] == "unresolved"
    assert event["location_precision"] == "city"
    assert event["primary_location_text"] == "Ottawa, CA"
    assert event["geocode_query_used"] == "Ottawa, CA"
    assert event["geocode_display_name"] is None
    assert event["date_precision"] == "exact_day"
    assert event["parse_warnings"] == []


def test_duplicate_provenance_is_retained_in_exported_event():
    first = CanonicalInputRecord(
        canonical_input_id="cin_a",
        source_name="alpha",
        source_file="alpha.csv",
        source_row_number=2,
        source_native_id="1",
        source_row_hash="hash_a",
        date_iso="2000-01-02",
        sort_date_iso="2000-01-02",
        time_raw="21:00",
        location_raw="Phoenix, AZ, US",
        description="Bright triangle hovered silently.",
    )
    second = CanonicalInputRecord(
        canonical_input_id="cin_b",
        source_name="beta",
        source_file="beta.csv",
        source_row_number=9,
        source_native_id="B-1",
        source_row_hash="hash_b",
        date_iso="2000-01-02",
        sort_date_iso="2000-01-02",
        time_raw="21:00",
        location_raw="Phoenix, AZ, US",
        description="Bright triangle hovered silently.",
    )
    deduped_events, duplicate_groups = build_deduped_events([first, second])

    normalized = canonical_events_to_normalized_events(deduped_events)
    normalized_again = canonical_events_to_normalized_events(deduped_events)

    assert len(duplicate_groups) == 1
    assert len(normalized) == 1
    assert normalized[0]["event_id"] == normalized_again[0]["event_id"]
    assert normalized[0]["canonical_event_id"] == deduped_events[0]["canonical_event_id"]
    assert normalized[0]["duplicate_record_count"] == 2
    assert normalized[0]["dedupe_strategy"] == "exact_canonical_fingerprint"
    assert normalized[0]["canonical_input_ids"] == ["cin_a", "cin_b"]
    assert {item["source_file"] for item in normalized[0]["source_provenance"]} == {
        "alpha.csv",
        "beta.csv",
    }
    assert normalized[0]["extra_data"]["canonical"]["source_provenance"] == normalized[0]["source_provenance"]
