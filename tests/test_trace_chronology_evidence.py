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
