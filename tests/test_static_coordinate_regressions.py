import json

from scripts.check_static_coordinate_regressions import check_static_coordinate_regressions


def write_summary(root, events):
    summary_dir = root / "data" / "canonical_web" / "summary_shards"
    summary_dir.mkdir(parents=True)
    (summary_dir / "summary_000000.json").write_text(json.dumps(events), encoding="utf-8")


def test_static_coordinate_regression_check_passes_for_us_rows_with_negative_longitudes(tmp_path):
    root = tmp_path / "bundle"
    write_summary(
        root,
        [
            {
                "event_id": "fargo-ok",
                "sort_date_iso": "1954-09-20",
                "location_raw": "FARGO, Cass, ND, US",
                "source": "ufocat",
                "coordinate_source": "raw_latlong",
                "location_precision": "exact_coords",
                "lat": 46.88,
                "lon": -96.78,
            },
            {
                "event_id": "butler-ok",
                "sort_date_iso": "1954-09-04",
                "location_raw": "BUTLER, Bates, MO, US",
                "source": "ufocat",
                "coordinate_source": "raw_latlong",
                "location_precision": "exact_coords",
                "lat": 38.26,
                "lon": -94.34,
            },
        ],
    )

    report = check_static_coordinate_regressions(
        payload_root=root,
        named_regressions=[
            {"label": "FARGO, Cass, ND, US", "contains": "FARGO", "state": "ND"},
            {"label": "BUTLER, Bates, MO, US", "contains": "BUTLER", "state": "MO"},
        ],
        named_country_regressions=[],
    )

    assert report["status"] == "ready"
    assert report["counts"]["explicit_us_outside_bounds"] == 0
    assert report["counts"]["explicit_us_outside_state_bounds"] == 0
    assert report["counts"]["named_regression_failures"] == 0


def test_static_coordinate_regression_check_fails_for_us_rows_with_positive_longitudes(tmp_path):
    root = tmp_path / "bundle"
    write_summary(
        root,
        [
            {
                "event_id": "fargo-bad",
                "sort_date_iso": "1954-09-20",
                "location_raw": "FARGO, Cass, ND, US",
                "source": "ufocat",
                "coordinate_source": "raw_latlong",
                "location_precision": "exact_coords",
                "lat": 46.88,
                "lon": 96.78,
            }
        ],
    )

    report = check_static_coordinate_regressions(
        payload_root=root,
        named_regressions=[{"label": "FARGO, Cass, ND, US", "contains": "FARGO", "state": "ND"}],
    )

    assert report["status"] == "needs_attention"
    assert report["counts"]["explicit_us_outside_bounds"] == 1
    assert report["counts"]["explicit_us_outside_state_bounds"] == 1
    assert report["counts"]["named_regression_failures"] == 1
    assert report["outside_examples"][0]["location_raw"] == "FARGO, Cass, ND, US"


def test_static_coordinate_regression_check_fails_for_us_rows_in_wrong_state(tmp_path):
    root = tmp_path / "bundle"
    write_summary(
        root,
        [
            {
                "event_id": "atlanta-in-texas",
                "sort_date_iso": "1954-09-20",
                "location_raw": "ATLANTA, Fulton, GA, US",
                "source": "ufocat",
                "coordinate_source": "raw_latlong",
                "location_precision": "exact_coords",
                "lat": 33.11,
                "lon": -94.16,
            }
        ],
    )

    report = check_static_coordinate_regressions(payload_root=root, named_regressions=[], named_country_regressions=[])

    assert report["status"] == "needs_attention"
    assert report["counts"]["explicit_us_outside_bounds"] == 0
    assert report["counts"]["explicit_us_outside_state_bounds"] == 1
    assert report["outside_state_examples"][0]["location_raw"] == "ATLANTA, Fulton, GA, US"


def test_static_coordinate_regression_check_does_not_treat_canada_ca_as_california(tmp_path):
    root = tmp_path / "bundle"
    write_summary(
        root,
        [
            {
                "event_id": "canada-ca",
                "location_raw": "TRAIL (CANADA), CA",
                "source": "phenomenainon_updb",
                "lat": 49.09983,
                "lon": -117.70223,
            }
        ],
    )

    report = check_static_coordinate_regressions(payload_root=root, named_regressions=[], named_country_regressions=[])

    assert report["status"] == "ready"
    assert report["counts"]["explicit_us_rows"] == 0


def test_static_coordinate_regression_check_flags_named_europe_row_in_wrong_ocean(tmp_path):
    root = tmp_path / "bundle"
    write_summary(
        root,
        [
            {
                "event_id": "wien-atlantic",
                "sort_date_iso": "1954-10-06",
                "location_raw": "WIEN (VIENNA), Vienna, AUT, EU",
                "source": "ufocat",
                "coordinate_source": "raw_latlong",
                "location_precision": "exact_coords",
                "lat": 48.2,
                "lon": -14.3,
            }
        ],
    )

    report = check_static_coordinate_regressions(
        payload_root=root,
        named_regressions=[],
        named_country_regressions=[
            {
                "label": "WIEN (VIENNA), Vienna, AUT, EU",
                "contains": "WIEN",
                "country_tokens": {"AUT", "AUSTRIA"},
                "bounds": {"lat_min": 46.0, "lat_max": 50.0, "lon_min": 9.0, "lon_max": 18.0},
            }
        ],
    )

    assert report["status"] == "needs_attention"
    assert report["counts"]["named_country_regression_failures"] >= 1
    wien = [item for item in report["named_country_regressions"] if item["label"].startswith("WIEN")][0]
    assert wien["found"] == 1
    assert wien["outside_bounds"] == 1
