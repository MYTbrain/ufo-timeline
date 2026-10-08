"""Documented source flags must supersede unsupported inferred occurrence dates."""
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ufocat_source_timing as source


def timestamp(text):
    return int(datetime.fromisoformat(text).replace(tzinfo=timezone.utc).timestamp() * 1000)


def test_standard_daylight_and_gmt_are_distinct_and_preserve_the_coded_date():
    clock = (23 * 3600000, 23 * 3600000 + 59999)
    for flag, expected in ((".", "1952-07-20T07:00:00"), ("+", "1952-07-20T06:00:00"), ("*", "1952-07-19T23:00:00")):
        interval, _ = source.utc_interval("1952-07-19", *clock, {"TZ": flag, "TZONE": "4"})
        assert interval == (timestamp(expected), timestamp(expected) + 59999)
    assert source.timebase({"TZ": ".", "TZONE": "8.5"})[0] == -210
    assert source.timebase({"TZ": "+", "TZONE": "21.5"})[0] == 630


def test_blank_or_unlisted_code_cannot_supply_a_definite_source_offset():
    for fields in ({"TZ": "", "TZONE": "6"}, {"TZ": ".", "TZONE": "0"},
                   {"TZ": "+", "TZONE": "5.5"}, {"TZ": ".", "TZONE": "NaN"}):
        assert source.utc_interval("1994-09-16", 1000, 1999, fields)[0] is None
    assert source.timebase({"TZ": "*", "TZONE": ""})[0] == 0


def test_source_date_warnings_block_clock_and_date_only_ordering():
    for flag, reason in (("'", "source_publication_date"), ("=", "source_date_flagged_erroneous"),
                         ("-", "source_date_approximate"), ("'+", "source_publication_date"),
                         ("*-", "source_date_approximate"), ("?", "source_date_time_flag_requires_review")):
        fields = {"TZ": flag, "TZONE": "7"}
        assert source.date_exclusion(fields)["reason"] == reason
        assert source.utc_interval("1952-07-19", 1000, 1999, fields)[0] is None


def test_whole_source_day_does_not_become_midnight_or_noon():
    interval, _ = source.utc_interval("1994-09-16", 0, 86399999, {"TZ": "+", "TZONE": "4"})
    assert interval == (timestamp("1994-09-16T07:00:00"), timestamp("1994-09-17T06:59:59.999"))
