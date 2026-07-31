from parser.chronology import canonical_playback_sort_tuple, derive_event_chronology


def _event(**overrides):
    event = {
        "event_id": 1,
        "date_iso": "1997-03-13",
        "sort_date_iso": "1997-03-13",
        "date_precision": "exact_day",
        "time_raw": None,
        "location_raw": "New York, New York",
        "all_locations_raw": ["New York, New York"],
        "geocode_display_name": "New York, New York, United States",
        "location_precision": "city",
        "coordinate_source": "geocoded",
        "lat": 40.7128,
        "lon": -74.006,
    }
    event.update(overrides)
    return event


def test_exact_time_with_explicit_timezone_uses_utc_sorting():
    derived = derive_event_chronology(
        _event(time_raw="2:30 pm EDT")
    )

    assert derived["time_sort_kind"] == "exact"
    assert derived["time_sort_confidence"] == "high"
    assert derived["timezone_source"] == "source_explicit"
    assert derived["playback_sort_reason"] == "exact_time_with_explicit_timezone"
    assert derived["estimated_utc_timestamp_ms"] is not None


def test_exact_time_with_inferred_timezone_uses_historical_zone():
    derived = derive_event_chronology(
        _event(
            time_raw="11:15 pm",
            location_raw="Los Angeles, California",
            all_locations_raw=["Los Angeles, California"],
            geocode_display_name="Los Angeles, California, United States",
            lat=34.0522,
            lon=-118.2437,
        )
    )

    assert derived["time_sort_kind"] == "exact"
    assert derived["resolved_timezone"] == "America/Los_Angeles"
    assert derived["timezone_confidence"] in {"high", "medium"}
    assert derived["playback_sort_reason"] == "exact_time_with_inferred_timezone"
    assert derived["estimated_utc_timestamp_ms"] is not None


def test_approximate_time_uses_midpoint_and_range():
    derived = derive_event_chronology(
        _event(
            time_raw="between 9 and 10 pm",
            location_raw="Paris, France",
            all_locations_raw=["Paris, France"],
            geocode_display_name="Paris, Ile-de-France, France",
            lat=48.8566,
            lon=2.3522,
        )
    )

    assert derived["time_sort_kind"] == "approximate"
    assert derived["time_sort_confidence"] == "medium"
    assert derived["parsed_time_local_minutes"] == 21.5 * 60
    assert derived["parsed_time_local_range_start_minutes"] == 21 * 60
    assert derived["parsed_time_local_range_end_minutes"] == 22 * 60
    assert derived["playback_sort_reason"] == "approximate_time_with_inferred_timezone"


def test_bucketed_morning_and_evening_create_stable_local_order():
    morning = derive_event_chronology(_event(event_id=10, time_raw="morning"))
    evening = derive_event_chronology(_event(event_id=11, time_raw="evening"))

    first = canonical_playback_sort_tuple(_event(event_id=10, **morning))
    second = canonical_playback_sort_tuple(_event(event_id=11, **evening))

    assert morning["time_sort_kind"] == "bucketed"
    assert evening["time_sort_kind"] == "bucketed"
    assert first < second


def test_solar_sunrise_bucket_uses_coordinate_aware_estimate():
    derived = derive_event_chronology(
        _event(
            date_iso="1997-06-21",
            sort_date_iso="1997-06-21",
            time_raw="sunrise",
            location_raw="New York, New York",
            all_locations_raw=["New York, New York"],
            geocode_display_name="New York, New York, United States",
            lat=40.7128,
            lon=-74.006,
        )
    )

    assert derived["time_bucket_label"] == "sunrise"
    assert derived["parsed_time_local_minutes"] is not None
    assert abs(derived["parsed_time_local_minutes"] - 360.0) > 10.0


def test_exact_day_gating_prevents_fake_same_day_precision_for_month_records():
    derived = derive_event_chronology(
        _event(
            date_iso="1989-11-01",
            sort_date_iso="1989-11-15",
            date_precision="month",
            time_raw="morning",
        )
    )

    assert derived["time_sort_kind"] == "unknown"
    assert derived["estimated_utc_timestamp_ms"] is None
    assert derived["playback_sort_reason"] == "stable_fallback"


def test_after_midnight_phrase_is_bucketed_early_in_day():
    derived = derive_event_chronology(_event(time_raw="shortly after midnight"))

    assert derived["time_bucket_label"] == "after_midnight"
    assert derived["parsed_time_local_minutes"] == 90.0
    assert derived["parsed_time_local_range_start_minutes"] == 0.0
    assert derived["parsed_time_local_range_end_minutes"] == 180.0


def test_no_time_event_uses_stable_fallback_only():
    derived = derive_event_chronology(_event(time_raw=None))

    assert derived["time_sort_kind"] == "unknown"
    assert derived["playback_sort_confidence"] == "none"
    assert derived["playback_sort_reason"] == "stable_fallback"
    assert derived["playback_sort_key"][0] == 3


def test_low_confidence_timezone_does_not_force_utc_ordering():
    derived = derive_event_chronology(
        _event(
            time_raw="09:00",
            location_raw="North Atlantic Ocean",
            all_locations_raw=["North Atlantic Ocean"],
            geocode_display_name="North Atlantic Ocean",
            location_precision="approximate",
            coordinate_source="unresolved",
            lat=None,
            lon=None,
        )
    )

    assert derived["timezone_confidence"] == "none"
    assert derived["estimated_utc_timestamp_ms"] is None
    assert derived["playback_sort_reason"] == "local_time_only"


def test_dst_fall_back_ambiguous_time_drops_to_local_only_ordering():
    derived = derive_event_chronology(
        _event(
            date_iso="1997-10-26",
            sort_date_iso="1997-10-26",
            time_raw="1:30 am",
            location_raw="New York, New York",
            all_locations_raw=["New York, New York"],
            geocode_display_name="New York, New York, United States",
            lat=40.7128,
            lon=-74.006,
        )
    )

    assert derived["resolved_timezone"] == "America/New_York"
    assert derived["estimated_utc_timestamp_ms"] is None
    assert derived["playback_sort_reason"] == "local_time_only"
