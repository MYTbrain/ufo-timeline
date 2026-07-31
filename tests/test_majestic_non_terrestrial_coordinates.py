from parser.csv_sources.majestic import MajesticAdapter
from parser.non_terrestrial_coordinates import (
    is_non_terrestrial_placeholder_coordinate,
)


def test_lunar_zero_coordinate_is_rejected_as_a_non_earth_placeholder() -> None:
    record = _record(
        {
            "source_id": "Hatch_UDB_139",
            "date": "11/23/1887",
            "location/0": "MOON",
            "key_vals/State/Prov": "PLT",
            "key_vals/Country": "The Moon",
            "key_vals/LatLong": "0.000000 -0.000000",
        }
    )

    assert record.location_raw == "MOON, PLT, The Moon"
    assert record.lat is None
    assert record.lon is None
    assert record.coordinate_source == "unresolved"
    assert record.location_precision == "unknown"
    assert record.raw_fields["key_vals/LatLong"] == "0.000000 -0.000000"


def test_nonzero_lunar_observer_coordinate_is_preserved() -> None:
    record = _record(
        {
            "source_id": "Hatch_observer",
            "date": "9/10/1973",
            "location/0": "EMBOURG",
            "key_vals/Country": "The Moon",
            "key_vals/LatLong": "50.583336 5.583334",
        }
    )

    assert record.lat == 50.583336
    assert record.lon == 5.583334
    assert record.coordinate_source == "source_coordinates"
    assert record.location_precision == "coordinate"


def test_terrestrial_zero_coordinate_is_not_changed_by_off_world_policy() -> None:
    record = _record(
        {
            "source_id": "Hatch_earth",
            "date": "1/1/2000",
            "location/0": "GULF OF GUINEA",
            "key_vals/Country": "Atlantic Ocean",
            "key_vals/LatLong": "0.000000 0.000000",
        }
    )

    assert record.lat == 0.0
    assert record.lon == 0.0
    assert record.coordinate_source == "source_coordinates"


def test_policy_is_narrow_and_normalizes_known_source_labels() -> None:
    assert is_non_terrestrial_placeholder_coordinate(
        country="Earth Orbit or seen from space stations/capsules",
        lat=-0.0,
        lon=0,
    )
    assert not is_non_terrestrial_placeholder_coordinate(
        country="The Moon",
        lat=50.583336,
        lon=5.583334,
    )
    assert not is_non_terrestrial_placeholder_coordinate(
        country="United States",
        lat=0,
        lon=0,
    )


def _record(row: dict[str, str]):
    return MajesticAdapter().row_to_record(
        row,
        source_row_number=1461,
        source_row_hash_value="fixture-row-hash",
    )
