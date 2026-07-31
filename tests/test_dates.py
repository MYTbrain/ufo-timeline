from parser.dates import normalize_event_dates


def test_normalize_exact_day():
    result = normalize_event_dates("7/8/1947", source_file="sample.txt")
    assert result["date_iso"] == "1947-07-08"
    assert result["end_date_iso"] is None
    assert result["sort_date_iso"] == "1947-07-08"
    assert result["date_precision"] == "exact_day"


def test_normalize_month_and_year_variants():
    month_result = normalize_event_dates("7/1947", source_file="sample.txt")
    assert month_result["date_iso"] == "1947-07-01"
    assert month_result["end_date_iso"] == "1947-07-31"
    assert month_result["date_precision"] == "month"

    year_result = normalize_event_dates("1947", source_file="sample.txt")
    assert year_result["date_iso"] == "1947-01-01"
    assert year_result["end_date_iso"] == "1947-12-31"
    assert year_result["date_precision"] == "year"


def test_normalize_decade_and_season_and_modifier():
    decade_result = normalize_event_dates("1980's?", source_file="sample.txt")
    assert decade_result["date_iso"] == "1980-01-01"
    assert decade_result["end_date_iso"] == "1989-12-31"
    assert decade_result["date_precision"] == "approximate"

    season_result = normalize_event_dates("Summer 1947", source_file="sample.txt")
    assert season_result["date_iso"] == "1947-06-01"
    assert season_result["end_date_iso"] == "1947-08-31"
    assert season_result["date_precision"] == "approximate"

    early_result = normalize_event_dates("Early 5/1947", source_file="sample.txt")
    assert early_result["date_iso"] == "1947-05-01"
    assert early_result["date_precision"] == "approximate"


def test_normalize_uses_context_for_short_years_and_handles_year_zero():
    short_year = normalize_event_dates("1/7/50", context_year_heading="1950", source_file="sample.txt")
    assert short_year["date_iso"] == "1950-01-07"

    year_zero = normalize_event_dates("0's", context_year_heading="0", source_file="sample.txt")
    assert year_zero["date_iso"] == "0000-01-01"
    assert year_zero["end_date_iso"] == "0009-12-31"
    assert year_zero["date_precision"] == "decade"


def test_normalize_explicit_end_date_range():
    result = normalize_event_dates("Early 5/1947", end_date_raw="5/12/1947", source_file="sample.txt")
    assert result["date_iso"] == "1947-05-01"
    assert result["end_date_iso"] == "1947-05-12"
    assert result["date_precision"] == "range"
