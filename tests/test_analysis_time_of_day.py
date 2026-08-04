from __future__ import annotations

from scripts.analysis_time_of_day import normalize_time_of_day


def test_exact_source_local_clock_preserves_unknown_offset_semantics() -> None:
    value = normalize_time_of_day("nuforc", "21:40 Local")
    assert value.status == "exact_clock"
    assert value.lower_minute == value.upper_minute == 21 * 60 + 40
    assert value.descriptive_bin == value.inferential_bin == "evening_18_23"
    assert value.timezone_label == "Local"
    assert value.timezone_semantics == "local_label_without_offset"


def test_ampm_and_compact_clocks_are_strictly_typed() -> None:
    assert normalize_time_of_day("mufon", "9:07PM").lower_minute == 21 * 60 + 7
    assert normalize_time_of_day("ufocat", "0215").lower_minute == 2 * 60 + 15
    assert normalize_time_of_day("phenomenainon_updb", "05:30:00").precision == "second"


def test_approximate_clock_is_descriptive_but_not_inferential() -> None:
    value = normalize_time_of_day("majestic", "~18:00")
    assert value.status == "approximate_clock"
    assert value.descriptive_bin == "evening_18_23"
    assert value.inferential_bin == "unknown"


def test_range_remains_a_range_without_bin_promotion() -> None:
    value = normalize_time_of_day("majestic", "18:10 - 18:40")
    assert value.status == "clock_range"
    assert value.lower_minute == 1090
    assert value.upper_minute == 1120
    assert value.descriptive_bin == value.inferential_bin == "unknown"


def test_midnight_and_noon_fail_closed_as_source_sentinels() -> None:
    for raw in ("0000", "00:00 Local", "12:00AM", "12:00:00"):
        value = normalize_time_of_day("source", raw)
        assert value.status == "sentinel_ambiguous"
        assert value.lower_minute is None
        assert value.descriptive_bin == value.inferential_bin == "unknown"


def test_explicit_qualitative_period_never_receives_minutes() -> None:
    value = normalize_time_of_day("ufocat", "Night")
    assert value.status == "qualitative_period"
    assert value.qualitative_period == "night"
    assert value.lower_minute is None
    assert value.inferential_bin == "unknown"


def test_invalid_or_missing_values_never_coerce_to_midnight() -> None:
    assert normalize_time_of_day("mufon", "25:71").status == "invalid_clock"
    assert normalize_time_of_day("mufon", "").status == "unparsed"


def test_normalization_is_idempotent_and_preserves_explicit_zone_label() -> None:
    first = normalize_time_of_day("majestic", "18:20 UTC")
    second = normalize_time_of_day("majestic", "18:20 UTC")
    assert first == second
    assert first.timezone_label == "UTC"
    assert first.timezone_semantics == "explicit_label_not_converted"
    assert first.lower_minute == 1100
