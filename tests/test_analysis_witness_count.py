from __future__ import annotations

from scripts.analysis_witness_count import normalize_witness_count


def test_explicit_integer_and_source_credentials_remain_separate() -> None:
    plain = normalize_witness_count("nuforc", "3")
    tagged = normalize_witness_count("nuforc", "2 - Pilot - Military")
    assert plain.status == "exact_count"
    assert plain.exact_count == plain.lower_count == plain.upper_count == 3
    assert plain.descriptive_bin == "three_to_four"
    assert plain.credential_profile == ""
    assert tagged.status == "exact_count"
    assert tagged.exact_count == 2
    assert tagged.credential_profile == "pilot+military"


def test_approximate_range_and_lower_bound_never_become_exact() -> None:
    approximate = normalize_witness_count("nuforc", "about 5")
    bounded = normalize_witness_count("nuforc", "3-7")
    lower_bound = normalize_witness_count("nuforc", "10+")
    assert approximate.status == "approximate_count"
    assert approximate.exact_count is None
    assert approximate.lower_count == approximate.upper_count == 5
    assert approximate.descriptive_bin == "unknown"
    assert bounded.status == "bounded_range"
    assert bounded.lower_count == 3 and bounded.upper_count == 7
    assert bounded.exact_count is None
    assert lower_bound.status == "lower_bound"
    assert lower_bound.lower_count == 10 and lower_bound.upper_count is None
    assert lower_bound.exact_count is None


def test_qualitative_party_size_is_typed_but_not_coerced() -> None:
    for raw in ("couple", "few", "several", "crowd", "group", "family", "party"):
        value = normalize_witness_count("nuforc", raw)
        assert value.status == "qualitative_plural"
        assert value.exact_count is None
        assert value.lower_count is None
        assert value.descriptive_bin == "unknown"


def test_missing_zero_and_negative_source_codes_fail_closed() -> None:
    assert normalize_witness_count("nuforc", "").status == "missing"
    zero = normalize_witness_count("nuforc", "0 - Military")
    negative = normalize_witness_count("nuforc", "-2")
    assert zero.status == negative.status == "invalid_count"
    assert zero.reason == "zero_source_sentinel"
    assert negative.reason == "negative_source_sentinel"
    assert zero.exact_count is negative.exact_count is None


def test_unsupported_text_and_credentials_remain_unresolved() -> None:
    assert normalize_witness_count("nuforc", "one").status == "unresolved_text"
    assert normalize_witness_count("nuforc", "2 witnesses").status == "unresolved_text"
    assert normalize_witness_count("nuforc", "2 - Astronomer").status == "unresolved_text"


def test_extreme_count_is_retained_for_audit_without_trimming() -> None:
    value = normalize_witness_count("nuforc", "20000")
    assert value.status == "exact_count"
    assert value.exact_count == 20_000
    assert value.descriptive_bin == "thousand_plus"
    assert value.extreme_audit is True


def test_normalization_is_idempotent() -> None:
    first = normalize_witness_count("nuforc", "1 - Military - Aviation Expert")
    second = normalize_witness_count("nuforc", "1 - Military - Aviation Expert")
    assert first == second
