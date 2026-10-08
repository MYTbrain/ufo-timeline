"""Time evidence regressions exercise source syntax and historical UTC rules."""
from datetime import datetime, timezone
import copy
import hashlib
import json
from pathlib import Path
import sys
import pytest

SHARED = Path(r"C:/Users/jarod/Desktop/UFO Timeline map tool")
sys.path.insert(0, str(SHARED / ".python_packages"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_trace_chronology_evidence as evidence


def ms(text):
    return evidence.epoch_ms(datetime.fromisoformat(text).replace(tzinfo=timezone.utc))


def event(location, lat=47.1, lon=-122.04, precision="city"):
    return {"location_raw": location, "has_coordinates": True,
            "location_precision": precision, "lat": lat, "lon": lon}


def test_independent_harare_and_washington_source_clocks_order_across_utc_dates():
    harare = evidence.source_clock("1018", 618)
    washington = evidence.source_clock("10:00PM", 1320)
    a, _ = evidence.utc_interval("1994-09-16", *harare[:2], "Africa/Harare")
    b, _ = evidence.utc_interval("1994-09-16", *washington[:2], "America/Los_Angeles")
    assert a == (ms("1994-09-16T08:18:00"), ms("1994-09-16T08:18:59.999"))
    assert b == (ms("1994-09-17T05:00:00"), ms("1994-09-17T05:00:59.999"))
    assert a[1] < b[0]


def test_daylight_saving_fold_preserves_both_possible_instants():
    interval, reason = evidence.utc_interval("2024-11-03", 90 * 60000, 91 * 60000 - 1, "America/New_York")
    assert reason == "historical_fold_interval"
    assert interval == (ms("2024-11-03T05:30:00"), ms("2024-11-03T06:30:59.999"))


def test_nonexistent_spring_clock_has_no_utc_evidence():
    interval, reason = evidence.utc_interval("2024-03-10", 150 * 60000, 151 * 60000 - 1, "America/New_York")
    assert interval is None
    assert reason == "nonexistent_local_clock"


def test_source_seconds_and_fractions_are_not_discarded():
    assert evidence.source_clock("06:02:59.9", 362) == (21779900, 21779999, "")
    assert evidence.source_clock("6:02:59 AM", 362) == (21779000, 21779999, "")
    assert evidence.source_clock("13:30PM", 810) is None
    assert evidence.source_clock("6:02 AM", 363) is None


def test_source_timezone_label_requires_consistent_geographic_context():
    (interval, reason), _ = evidence.explicit_utc_interval("1994-09-16", 79200000, 79259999, "PDT", None)
    assert interval is None
    assert reason == "ambiguous_explicit_timezone_label"
    (interval, _), _ = evidence.explicit_utc_interval("1994-09-16", 79200000, 79259999, "PDT", "America/Los_Angeles")
    assert interval[0] == ms("1994-09-17T05:00:00")
    (interval, reason), _ = evidence.explicit_utc_interval("1994-09-16", 79200000, 79259999, "PDT", "America/New_York")
    assert interval is None
    assert reason == "explicit_timezone_conflicts_with_jurisdiction"


def test_geographic_aliases_do_not_scan_incidental_words_or_guess_split_zones():
    aliases, single, _ = evidence.country_zone_rules()
    assert evidence.strict_zone(event("CARBONADO, Pierce, WA, US"), aliases, single)[0] == "America/Los_Angeles"
    assert evidence.strict_zone(event("HARARE RURAL AREA, Mashona East, ZIM, AF", -17.9, 31.25), aliases, single)[0] == "Africa/Harare"
    assert evidence.strict_zone(event("SIMCOE, CA", 42.83, -80.30), aliases, single)[0] is None
    assert evidence.strict_zone(event("CITY, AZ, US", 35, -111), aliases, single)[0] is None
    assert evidence.strict_zone(event("CITY, TX, US", 30, -100), aliases, single)[0] is None
    assert evidence.strict_zone(event("California, Zimbabwe", -17.9, 31.25), aliases, single)[0] == "Africa/Harare"
    assert evidence.strict_zone(event("CITY, WA, US", -17.9, 31.25), aliases, single)[0] is None
    assert evidence.strict_zone(event("CITY, WA, US", precision="country"), aliases, single)[0] is None
    assert evidence.strict_zone(event("Harrisburg, PA", 40.27, -76.89), aliases, single)[0] == "America/New_York"
    assert evidence.strict_zone(event("Richmond, VA", 37.54, -77.43), aliases, single)[0] == "America/New_York"
    assert evidence.strict_zone(event("Baltimore, MD", 39.29, -76.61), aliases, single)[0] == "America/New_York"
    assert evidence.strict_zone(event("Connersville, IN", 39.64, -85.14), aliases, single)[0] is None
    assert evidence.strict_zone(event("Oak Ridge, TN", 36.01, -84.27), aliases, single)[0] is None
    assert evidence.strict_zone(event("Tucson, AZ", 32.22, -110.97), aliases, single)[0] is None
    assert evidence.strict_zone(event("CITY, CA, US", 42, -74), aliases, single)[0] is None
    assert evidence.strict_zone(event("CITY, France", -17.9, 31.25), aliases, single)[0] is None


def test_historical_inference_needs_supported_locality_and_not_an_lmt_anchor():
    assert not evidence.historical_jurisdiction_supported({"sort_date_iso": "1899-09-16", "location_raw": "Chicago, IL"}, "America/Chicago")
    assert not evidence.historical_jurisdiction_supported({"sort_date_iso": "1952-09-16", "location_raw": "Albuquerque, NM"}, "America/Denver")
    assert evidence.historical_jurisdiction_supported({"sort_date_iso": "1952-09-16", "location_raw": "Chicago, IL"}, "America/Chicago")
    assert evidence.historical_jurisdiction_supported({"sort_date_iso": "1994-09-16", "location_raw": "Carbonado, WA"}, "America/Los_Angeles")


def dated_event(location, date, lat=47.1, lon=-122.04, precision="city"):
    return {**event(location, lat, lon, precision), "sort_date_iso": date}


def test_historical_locality_uses_entire_continental_offset_envelope_without_assigning_dst():
    aliases, single, _ = evidence.country_zone_rules()
    row = dated_event("Albuquerque, NM", "1952-09-16", 35.09, -106.65)
    assert not evidence.historical_jurisdiction_supported(row, "America/Denver")
    jurisdiction, reason = evidence.bounded_jurisdiction(row, aliases, single)
    assert reason == "continental_us_civil_offset_envelope"
    assert jurisdiction["offsetMinutes"] == (-480, -240)
    assert jurisdiction["zone"] == "UTC"
    interval, reason = evidence.jurisdiction_utc_interval("1952-09-16", 600 * 60000, 601 * 60000 - 1, jurisdiction)
    assert interval == (ms("1952-09-16T14:00:00"), ms("1952-09-16T18:00:59.999"))
    assert reason == "continental_us_civil_offset_envelope"
    # Neither a current DST rule nor an LMT representative anchor is extended
    # before the supported standardized continental civil-time regime.
    for date in ("1899-09-16", "1918-03-30"):
        jurisdiction, _ = evidence.bounded_jurisdiction({**row, "sort_date_iso": date}, aliases, single)
        assert jurisdiction is None


def test_supported_named_locality_precision_is_retained_before_1970():
    aliases, single, _ = evidence.country_zone_rules()
    row = dated_event("Chicago, IL", "1952-09-16", 41.88, -87.63)
    jurisdiction, _ = evidence.bounded_jurisdiction(row, aliases, single)
    assert jurisdiction["zones"] == ("America/Chicago",)
    assert jurisdiction["zone"] == "America/Chicago"
    assert "offsetMinutes" not in jurisdiction


def test_split_states_receive_a_broad_envelope_only_with_an_actual_guarded_jurisdiction():
    aliases, single, _ = evidence.country_zone_rules()
    for location in ("Tucson, AZ", "Tucson, Arizona, US"):
        row = dated_event(location, "1994-09-16", 32.22, -110.97)
        assert evidence.strict_zone(row, aliases, single)[0] is None
        jurisdiction, _ = evidence.bounded_jurisdiction(row, aliases, single)
        assert jurisdiction["offsetMinutes"] == (-480, -240)
    for row in (
        dated_event("Tucson, AZ", "1994-09-16", -17.9, 31.25),
        dated_event("Tucson, AZ", "1994-09-16", 32.22, -110.97, "country"),
        dated_event("City, US", "1994-09-16", 32.22, -110.97),
        dated_event("SIMCOE, CA", "1994-09-16", 42.83, -80.30),
    ):
        assert evidence.bounded_jurisdiction(row, aliases, single)[0] is None


def test_multi_zone_country_preserves_all_possible_post1970_zones():
    aliases, single, _ = evidence.country_zone_rules()
    row = dated_event("Mexico City, Mexico", "1994-09-16", 19.43, -99.13)
    jurisdiction, reason = evidence.bounded_jurisdiction(row, aliases, single)
    assert reason == "country_iana_zone_candidate_envelope"
    assert jurisdiction["zones"] == evidence.COUNTRY_ZONES["MX"]
    assert len(jurisdiction["zones"]) > 1 and jurisdiction["zone"] == "UTC"
    interval, _ = evidence.jurisdiction_utc_interval(row["sort_date_iso"], 10 * 3600000, 10 * 3600000 + 59999, jurisdiction)
    candidates = [evidence.utc_interval(row["sort_date_iso"], 10 * 3600000, 10 * 3600000 + 59999, zone)[0]
                  for zone in evidence.COUNTRY_ZONES["MX"]]
    assert interval == (min(item[0] for item in candidates), max(item[1] for item in candidates))
    assert evidence.bounded_jurisdiction({**row, "sort_date_iso": "1954-09-16"}, aliases, single)[0] is None
    assert evidence.bounded_jurisdiction({**row, "lat": -17.9, "lon": 31.25}, aliases, single)[0] is None


def test_france_national_legal_time_bounds_cover_nonparis_records_without_city_dst():
    aliases, single, _ = evidence.country_zone_rules()
    row = dated_event("Froncles, France", "1954-09-28", 48.30, 5.15)
    assert not evidence.historical_jurisdiction_supported(row, "Europe/Paris")
    jurisdiction, reason = evidence.bounded_jurisdiction(row, aliases, single)
    assert reason == "metropolitan_france_national_offset_envelope"
    assert jurisdiction["offsetMinutes"] == (60, 60)
    interval, _ = evidence.jurisdiction_utc_interval(row["sort_date_iso"], 21 * 3600000 + 30 * 60000,
                                                   21 * 3600000 + 31 * 60000 - 1, jurisdiction)
    assert interval == (ms("1954-09-28T20:30:00"), ms("1954-09-28T20:30:59.999"))
    wartime, reason = evidence.bounded_jurisdiction({**row, "sort_date_iso": "1944-09-28"}, aliases, single)
    assert reason == "metropolitan_france_historical_offset_envelope"
    assert wartime["offsetMinutes"] == (0, 120)
    assert evidence.bounded_jurisdiction({**row, "sort_date_iso": "1911-03-11"}, aliases, single)[0] is None
    assert evidence.bounded_jurisdiction({**row, "lat": 4.93, "lon": -52.33}, aliases, single)[0] is None


def test_uk_bounds_retain_double_summer_and_withhold_preunification_or_overseas():
    aliases, single, _ = evidence.country_zone_rules()
    row = dated_event("Manchester, England", "1941-07-01", 53.48, -2.24)
    jurisdiction, reason = evidence.bounded_jurisdiction(row, aliases, single)
    assert reason == "uk_historical_civil_offset_envelope"
    assert jurisdiction["offsetMinutes"] == (0, 120)
    interval, _ = evidence.jurisdiction_utc_interval(row["sort_date_iso"], 14 * 3600000, 14 * 3600000 + 59999, jurisdiction)
    assert interval == (ms("1941-07-01T12:00:00"), ms("1941-07-01T14:00:59.999"))
    assert evidence.bounded_jurisdiction({**row, "sort_date_iso": "1916-10-01"}, aliases, single)[0] is None
    assert evidence.bounded_jurisdiction({**row, "lat": -51.7, "lon": -57.85}, aliases, single)[0] is None


def test_ufocat_region_suffixes_are_separate_from_iso_countries_for_other_sources():
    aliases, single, _ = evidence.country_zone_rules()
    mexico = {**dated_event("MEXICO CITY N, Mexico, MEX, CA", "1994-09-16", 19.25, -99.6), "source": "ufocat"}
    assert evidence.structured_location_parts(mexico, aliases) == ["MEXICO CITY N", "MEXICO", "MEX"]
    jurisdiction, _ = evidence.bounded_jurisdiction(mexico, aliases, single)
    assert jurisdiction["zones"] == evidence.COUNTRY_ZONES["MX"]
    for source in ("mufon", "nuforc", "phenomenainon_updb", "majestic"):
        row = {**mexico, "source": source}
        assert evidence.structured_location_parts(row, aliases)[-1] == "CA"
        assert evidence.bounded_jurisdiction(row, aliases, single)[0] is None


def test_ufocat_canadian_region_requires_a_recognized_province_and_china_stays_literal_elsewhere():
    aliases, single, _ = evidence.country_zone_rules()
    canada = {**dated_event("OROMOCTO, NS, Sunbury, NB, CN", "2004-01-17", 45.85, -66.48), "source": "ufocat"}
    assert evidence.structured_location_parts(canada, aliases)[-1] == "CAN"
    jurisdiction, _ = evidence.bounded_jurisdiction(canada, aliases, single)
    assert jurisdiction["zones"] == evidence.COUNTRY_ZONES["CA"]
    # Actual Canadian country suffixes and California state suffixes retain
    # their established roles; no global CN/CA alias replacement is made.
    for source in ("ufocat", "mufon"):
        toronto = {**dated_event("Toronto, ON, CA", "2004-01-17", 43.65, -79.38), "source": source}
        assert evidence.structured_location_parts(toronto, aliases)[-1] == "CA"
    us_state = {**dated_event("Carbonado, WA, US", "1994-09-16"), "source": "ufocat"}
    assert evidence.strict_zone(us_state, aliases, single)[0] == "America/Los_Angeles"
    china = {**dated_event("Beijing, Hebei, CN", "2004-01-17", 39.91, 116.40), "source": "mufon"}
    assert evidence.structured_location_parts(china, aliases)[-1] == "CN"
    jurisdiction, _ = evidence.bounded_jurisdiction(china, aliases, single)
    assert jurisdiction["zones"] == evidence.COUNTRY_ZONES["CN"]
    assert evidence.bounded_jurisdiction({**canada, "lat": 39.91, "lon": 116.40}, aliases, single)[0] is None


def test_ufocat_other_oceania_and_middle_east_use_recognized_country_components():
    aliases, single, _ = evidence.country_zone_rules()
    nz = {**dated_event("QUEENSTOWN, Otago, NZL, AU", "2008-07-20", -45.05, 168.68), "source": "ufocat"}
    assert evidence.structured_location_parts(nz, aliases)[-1] == "NZL"
    jurisdiction, _ = evidence.bounded_jurisdiction(nz, aliases, single)
    assert jurisdiction["zones"] == evidence.COUNTRY_ZONES["NZ"]
    israel = {**dated_event("YAFO, Tel Aviv, ISR, ME", "1998-01-08", 32.03, 34.75), "source": "ufocat"}
    assert evidence.structured_location_parts(israel, aliases)[-1] == "ISR"
    assert evidence.strict_zone(israel, aliases, single)[0] == "Asia/Jerusalem"
    for row in (nz, israel):
        assert evidence.structured_location_parts({**row, "source": "majestic"}, aliases) == (
            [evidence.normalized(part) for part in row["location_raw"].split(",")])


def test_source_region_repair_withholds_legacy_alias_guesses_raw_field_conflicts_and_bad_coordinates():
    aliases, single, _ = evidence.country_zone_rules()
    for state in ("GM", "MRT", "ANT", "CRC"):
        row = {**dated_event("Island, " + state + ", CA", "1994-09-16", 17.0, -61.0), "source": "ufocat"}
        assert evidence.structured_location_parts(row, aliases)[-1] == "CA"
    row = {**dated_event("Mexico City, MEX, CA", "1994-09-16", 19.43, -99.13), "source": "ufocat"}
    conflicting = {**row, "raw_fields": {"REGION": "CN", "STATE": "ON"}}
    assert evidence.structured_location_parts(conflicting, aliases)[-1] == "CA"
    assert evidence.bounded_jurisdiction(conflicting, aliases, single)[0] is None
    assert evidence.bounded_jurisdiction({**row, "lat": 43.65, "lon": -79.38}, aliases, single)[0] is None
    assert evidence.bounded_jurisdiction({**row, "location_precision": "country"}, aliases, single)[0] is None


def test_calendar_day_bounds_keep_missing_clock_as_a_complete_day_and_handle_dst():
    before, _ = evidence.calendar_day_utc_interval("1994-09-16", "Africa/Harare")
    after, _ = evidence.calendar_day_utc_interval("1994-09-17", "Africa/Harare")
    assert before == (ms("1994-09-15T22:00:00"), ms("1994-09-16T21:59:59.999"))
    assert after[0] == before[1] + 1
    spring, _ = evidence.calendar_day_utc_interval("2024-03-10", "America/New_York")
    autumn, _ = evidence.calendar_day_utc_interval("2024-11-03", "America/New_York")
    assert spring[1] - spring[0] + 1 == 23 * 3600000
    assert autumn[1] - autumn[0] + 1 == 25 * 3600000


def test_midnight_gap_is_bounded_but_completely_skipped_source_date_is_withheld():
    interval, reason = evidence.calendar_day_utc_interval("2018-11-04", "America/Sao_Paulo")
    assert interval is not None and reason == "calendar_day_transition_envelope"
    actual_first_valid, _ = evidence.utc_interval("2018-11-04", 3600000, 3600000 + 59999, "America/Sao_Paulo")
    assert interval[0] <= actual_first_valid[0] <= interval[1]
    interval, reason = evidence.calendar_day_utc_interval("2011-12-30", "Pacific/Apia")
    assert interval is None and reason == "nonexistent_local_calendar_day"


def test_reviewed_narrative_reopens_original_source_and_rejects_tampering(tmp_path):
    text = "10:00 a.m. Children saw an object at their school."
    chunk = [{"event_id": 123, "chunk_id": "chunk_000000", "detail_index": 0,
              "source": "majestic", "source_id": "own-source-record",
              "sort_date_iso": "1994-09-16", "date_precision": "exact_day",
              "time_raw": "", "description": text}]
    path = tmp_path / "chunk_000000.json"
    raw = json.dumps(chunk).encode("utf-8")
    path.write_bytes(raw)
    row = {"eventId": 123, "sourceChunk": path.stem, "sourceChunkPath": str(path),
           "sourceChunkSha256": hashlib.sha256(raw).hexdigest(), "sourceChunkBytes": len(raw),
           "detailIndex": 0, "source": "majestic", "sourceId": "own-source-record",
           "date": "1994-09-16", "rawTime": "", "sourceField": "description",
           "descriptionSha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "excerpt": text[:30]}
    assert evidence.validate_narrative_sources([row], tmp_path)[0]["reviewedRecordsVerified"] == 1
    for key, value, message in [
        ("sourceChunkSha256", "0" * 64, "chunk hash"),
        ("descriptionSha256", "0" * 64, "description hash"),
        ("eventId", 456, "event identity"),
        ("detailIndex", 1, "detail locator"),
        ("excerpt", "Unrelated claimed clock", "source excerpt"),
        ("sourceChunkPath", str(tmp_path.parent / path.name), "outside"),
    ]:
        changed = copy.deepcopy(row)
        changed[key] = value
        with pytest.raises(ValueError, match=message):
            evidence.validate_narrative_sources([changed], tmp_path)
    path.write_bytes(raw.replace(b"Children", b"Students"))
    with pytest.raises(ValueError, match="chunk hash"):
        evidence.validate_narrative_sources([row], tmp_path)
