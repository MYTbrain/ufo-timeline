import gzip
import json
from pathlib import Path

import math
import tempfile
import unittest
from contextlib import contextmanager


@contextmanager
def raises(error):
    try:
        yield
    except error:
        return
    raise AssertionError(f"Expected {error.__name__}")

from scripts.audit_unmapped_source_coordinates import audit, parse_component, screen_record


def row(raw=None, **detail_overrides):
    detail = {"event_id": 1, "raw_fields": raw or {}, "source_provenance_count": 1, "duplicate_record_count": 1,
              **detail_overrides}
    return {"summary": {"event_id": 1, "has_coordinates": False, "source": "nuforc", "location_raw": "Everett, WA, USA", "coordinate_source": "unresolved"},
            "source_detail": detail, "provenance": {"sha256": "test-pinned-source"}}


def test_decimal_dms_and_zero_axes_are_conservative():
    assert parse_component("47.5 N", "lat")[0] == 47.5
    assert parse_component("122° 20′ 30″ W", "lon")[0] == -122.34166666666667
    assert parse_component(0, "lat")[0] == 0
    for value in (True, "nan", "infinity", "4730", "47° 60′ N", "47.5° 3′ N", "+47 S", "-47 N"):
        assert parse_component(value, "lat")[0] is None
    assert parse_component("47 E", "lat")[0] is None


def test_original_axis_fields_are_review_only_not_approved():
    result = screen_record(row({"Latitude": "47.5", "Longitude": "-122.3"}))
    assert result["disposition"] == "review_candidate"
    assert result["accepted"] is False
    finding = result["coordinate_findings"][0]
    assert finding["field_paths"] == ["raw_fields.Latitude", "raw_fields.Longitude"]
    assert finding["parsed_lon"] == -122.3
    assert "verify_observer_role" in finding["required_review"]


def test_derived_coordinates_are_not_original_evidence():
    result = screen_record(row({}, lat=47, lon=-122, has_coordinates=True,
                               source_provenance=[{"lat": 48, "lon": -123}]))
    assert result["disposition"] == "no_explicit_source_coordinates"
    assert result["coordinate_findings"] == []


def test_no_accidental_dates_or_aircraft_numbers_as_coordinates():
    result = screen_record(row({"Description": "In 2014, 12 people saw 2 objects on 47, 122 Road near I-5."}))
    assert result["coordinate_findings"] == []
    assert screen_record(row({"search": "normalized index 19 N 172 E"}))["coordinate_findings"] == []


def test_explicit_narrative_coordinate_with_original_context():
    result = screen_record(row({"Description": "Our ship position was latitude 47.25 longitude -122.1 at the observation."}))
    finding = result["coordinate_findings"][0]
    assert finding["kind"] == "labelled_text"
    assert finding["parsed_lat"] == 47.25
    assert "ship position" in finding["excerpt"]


def test_hemisphere_pair_does_not_confuse_axis_order():
    result = screen_record(row({"Location": "122.5 W, 47.5 N"}))
    assert result["coordinate_findings"][0]["parsed_lon"] == -122.5
    assert result["coordinate_findings"][0]["parsed_lat"] == 47.5


def test_majestic_combined_fields_and_non_terrestrial_context():
    result = screen_record(row({"key_vals/LatLong": "47.5 -122.3"}))
    assert result["coordinate_findings"][0]["parsed_lon"] == -122.3
    result = screen_record(row({"key_vals/LatLong": "0.0000 -0.0000", "key_vals/Country": "The Moon"}))
    assert result["disposition"] == "hold"
    assert "non_terrestrial_context" in result["record_flags"]


def test_gps_coordinate_text_requires_explicit_label():
    result = screen_record(row({"Description": "GPS coordinates are 47.25, -122.3 at our position."}))
    assert result["coordinate_findings"][0]["kind"] == "gps_labelled_text"
    assert result["coordinate_findings"][0]["parsed_lat"] == 47.25


UNSAFE_CASES = [
    ({"lat": 0, "lon": 0}, {}, {}, "zero_pair_requires_independent_evidence"),
    ({"lat": 47}, {}, {}, "incomplete_or_unparsed_coordinate_pair"),
    ({"lat": 47, "lon": 122}, {}, {"source": "ufocat"}, "ufocat_codebook_sign_datum_and_grid_review"),
    ({"lat": 47, "lon": -122}, {"duplicate_record_count": 2}, {}, "composite_requires_member_review"),
    ({"object_latitude": 47, "object_longitude": -122}, {}, {}, "non_observer_coordinate_role"),
    ({"home_address_latitude": 47, "home_address_longitude": -122}, {}, {}, "non_observer_coordinate_role"),
    ({"lat": 47, "lon": -122}, {"description": "I watched an ISS live feed."}, {}, "remote_media_role_requires_review"),
    ({"lat": 47, "lon": -122}, {}, {"coordinate_source": "coordinate_quarantine"}, "existing_coordinate_review_or_quarantine"),
    ({"lat": 47, "lon": -122}, {"country": "Mars"}, {}, "non_terrestrial_context"),
]
def unsafe_candidate_stays_held(raw, extra, summary, reasons):
    record = row(raw, **extra)
    record["summary"].update(summary)
    result = screen_record(record)
    assert result["disposition"] == "hold"
    assert reasons in result["coordinate_findings"][0]["hold_reasons"]
    assert result["accepted"] is False


def test_summary_detail_guards_fail_closed():
    record = row()
    record["source_detail"]["event_id"] = 2
    with raises(ValueError):
        screen_record(record)
    record = row()
    record["summary"]["has_coordinates"] = True
    with raises(ValueError):
        screen_record(record)


def test_streaming_census_accounts_for_every_record_and_refuses_overwrite(tmp_path: Path):
    input_path = tmp_path / "input.jsonl.gz"
    records = [row({"lat": 47, "lon": -122}), row({"lat": 0, "lon": 0}), row()]
    with gzip.open(input_path, "wt", encoding="utf8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")
    result = audit(input_path, tmp_path / "audit")
    assert result["counts"] == {"records_scanned": 3, "review_candidate": 1, "hold": 1, "no_explicit_source_coordinates": 1}
    assert result["accepted_coordinates"] == 0
    assert all(output["sha256"] for output in result["outputs"])
    with raises(FileExistsError):
        audit(input_path, tmp_path / "audit")


class SourceCoordinateAuditTests(unittest.TestCase):
    pass


for test_name, test_function in list(globals().items()):
    if test_name.startswith("test_") and callable(test_function) and test_name != "test_streaming_census_accounts_for_every_record_and_refuses_overwrite":
        setattr(SourceCoordinateAuditTests, test_name, lambda self, test=test_function: test())
del test_name, test_function


def unsafe_test(self):
    for case in UNSAFE_CASES:
        with self.subTest(reason=case[-1]):
            unsafe_candidate_stays_held(*case)


def streaming_test(self):
    with tempfile.TemporaryDirectory() as directory:
        test_streaming_census_accounts_for_every_record_and_refuses_overwrite(Path(directory))


SourceCoordinateAuditTests.test_unsafe_candidates_stay_held = unsafe_test
SourceCoordinateAuditTests.test_streaming_census = streaming_test

if __name__ == "__main__":
    unittest.main()
