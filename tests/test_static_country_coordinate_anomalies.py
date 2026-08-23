import json

from scripts.check_static_country_coordinate_anomalies import check_static_country_coordinate_anomalies


def write_summary(root, events):
    summary_dir = root / "data" / "canonical_web" / "summary_shards"
    summary_dir.mkdir(parents=True)
    (summary_dir / "summary_000000.json").write_text(json.dumps(events), encoding="utf-8")


def test_static_country_coordinate_anomaly_check_passes_for_known_country_bounds(tmp_path):
    root = tmp_path / "bundle"
    write_summary(
        root,
        [
            {
                "event_id": "fargo",
                "location_raw": "FARGO, Cass, ND, US",
                "source": "ufocat",
                "lat": 46.88,
                "lon": -96.78,
                "coordinate_source": "raw_latlong",
            },
            {
                "event_id": "wien",
                "location_raw": "WIEN (VIENNA), Vienna, AUT, EU",
                "source": "ufocat",
                "lat": 48.22,
                "lon": 16.36,
                "coordinate_source": "raw_latlong",
            },
        ],
    )

    report = check_static_country_coordinate_anomalies(payload_root=root)

    assert report["status"] == "ready"
    assert report["counts"]["checked_rows"] == 2
    assert report["counts"]["anomaly_rows"] == 0


def test_static_country_coordinate_anomaly_check_flags_us_point_in_asia(tmp_path):
    root = tmp_path / "bundle"
    write_summary(
        root,
        [
            {
                "event_id": "fargo-asia",
                "location_raw": "FARGO, Cass, ND, US",
                "source": "ufocat",
                "lat": 46.88,
                "lon": 96.78,
                "coordinate_source": "raw_latlong",
            }
        ],
    )

    report = check_static_country_coordinate_anomalies(payload_root=root)

    assert report["status"] == "needs_attention"
    assert report["counts"]["anomaly_rows"] == 1
    assert report["examples"][0]["reason"] == "positive_longitude_for_explicit_us_row"


def test_static_country_coordinate_anomaly_check_flags_full_us_state_mismatch(tmp_path):
    root = tmp_path / "bundle"
    write_summary(
        root,
        [
            {
                "event_id": "hatch-udb-2481",
                "location_raw": "Farmlands, NAPA VALLEY, CA, Colorado, USA",
                "source": "majestic",
                "lat": 38.300002,
                "lon": -122.300006,
                "coordinate_source": "raw_latlong",
            }
        ],
    )

    report = check_static_country_coordinate_anomalies(payload_root=root)

    assert report["status"] == "needs_attention"
    assert report["counts"]["anomaly_rows"] == 1
    assert report["examples"][0]["reason"] == "outside_declared_us_state_bounds"


def test_static_country_coordinate_anomaly_check_accepts_corrected_napa_state(tmp_path):
    root = tmp_path / "bundle"
    write_summary(
        root,
        [
            {
                "event_id": "hatch-udb-2481",
                "location_raw": (
                    "Napa Valley near Napa, Napa County, California, USA"
                ),
                "source": "majestic",
                "lat": 38.300002,
                "lon": -122.300006,
                "coordinate_source": "raw_latlong",
            }
        ],
    )

    report = check_static_country_coordinate_anomalies(payload_root=root)

    assert report["status"] == "ready"
    assert report["counts"]["checked_rows"] == 1
    assert report["counts"]["anomaly_rows"] == 0


def test_static_country_coordinate_anomaly_check_flags_europe_point_in_atlantic(tmp_path):
    root = tmp_path / "bundle"
    write_summary(
        root,
        [
            {
                "event_id": "wien-atlantic",
                "location_raw": "WIEN (VIENNA), Vienna, AUT, EU",
                "source": "ufocat",
                "lat": 48.2,
                "lon": -14.3,
                "coordinate_source": "raw_latlong",
            }
        ],
    )

    report = check_static_country_coordinate_anomalies(payload_root=root)

    assert report["status"] == "needs_attention"
    assert report["counts"]["anomaly_rows"] == 1
    assert report["examples"][0]["reason"] == "far_negative_longitude_for_eastern_country"


def test_static_country_coordinate_anomaly_check_ignores_ambiguous_middle_ca(tmp_path):
    root = tmp_path / "bundle"
    write_summary(
        root,
        [
            {
                "event_id": "trail-ca",
                "location_raw": "TRAIL (CANADA), CA",
                "source": "phenomenainon_updb",
                "lat": 49.09983,
                "lon": -117.70223,
                "coordinate_source": "geocoded",
            }
        ],
    )

    report = check_static_country_coordinate_anomalies(payload_root=root)

    assert report["status"] == "ready"
    assert report["counts"]["explicit_country_rows"] == 0


def test_static_country_coordinate_anomaly_check_treats_final_au_as_australia(tmp_path):
    root = tmp_path / "bundle"
    write_summary(
        root,
        [
            {
                "event_id": "bowral",
                "location_raw": "BOWRAL, US, AU",
                "source": "phenomenainon_updb",
                "lat": -33.0,
                "lon": 146.0,
                "coordinate_source": "geocoded",
            }
        ],
    )

    report = check_static_country_coordinate_anomalies(payload_root=root)

    assert report["status"] == "ready"
    assert report["counts"]["checked_rows"] == 1


def test_static_country_coordinate_anomaly_check_prefers_nzl_before_oceania_region(tmp_path):
    root = tmp_path / "bundle"
    write_summary(
        root,
        [
            {
                "event_id": "auckland",
                "location_raw": "AUCKLAND, Auckland, NZL, AU",
                "source": "ufocat",
                "lat": -36.92,
                "lon": 174.78,
                "coordinate_source": "raw_latlong",
            }
        ],
    )

    report = check_static_country_coordinate_anomalies(payload_root=root)

    assert report["status"] == "ready"
    assert report["counts"]["checked_rows"] == 1


def test_static_country_coordinate_anomaly_check_uses_later_specific_country_token(tmp_path):
    root = tmp_path / "bundle"
    write_summary(
        root,
        [
            {
                "event_id": "drachten",
                "location_raw": "DRACHTEN, BEL, Friesland, NED, EU",
                "source": "ufocat",
                "lat": 53.12,
                "lon": 6.1,
                "coordinate_source": "raw_latlong",
            }
        ],
    )

    report = check_static_country_coordinate_anomalies(payload_root=root)

    assert report["status"] == "ready"
    assert report["counts"]["checked_rows"] == 1


def test_static_country_coordinate_anomaly_check_does_not_treat_baltic_sea_bs_as_bahamas(tmp_path):
    root = tmp_path / "bundle"
    write_summary(
        root,
        [
            {
                "event_id": "baltic",
                "location_raw": "BALTIC SEA 40NM OFF CAPE HEL, BS, EU",
                "source": "ufocat",
                "lat": 54.83,
                "lon": 19.0,
                "coordinate_source": "raw_latlong",
            }
        ],
    )

    report = check_static_country_coordinate_anomalies(payload_root=root)

    assert report["status"] == "ready"
    assert report["counts"]["explicit_country_rows"] == 0


def test_static_country_coordinate_anomaly_check_treats_bs_eu_as_baltic_context(tmp_path):
    root = tmp_path / "bundle"
    write_summary(
        root,
        [
            {
                "event_id": "leba",
                "location_raw": "LEBA, Slupsk, BS, EU",
                "source": "ufocat",
                "lat": 54.75,
                "lon": 17.53,
                "coordinate_source": "raw_latlong",
            }
        ],
    )

    report = check_static_country_coordinate_anomalies(payload_root=root)

    assert report["status"] == "ready"
    assert report["counts"]["explicit_country_rows"] == 0


def test_static_country_coordinate_anomaly_check_prefers_specific_country_over_group_label(tmp_path):
    root = tmp_path / "bundle"
    write_summary(
        root,
        [
            {
                "event_id": "haarlem",
                "location_raw": "Coastlands, HAARLEM, NETH, Netherlands, Belgium, Netherlandsand Luxembourg",
                "source": "majestic",
                "lat": 52.366669,
                "lon": 4.616667,
                "coordinate_source": "raw_latlong",
            },
            {
                "event_id": "ireland",
                "location_raw": "Town & City, LIMERICK, IREL, Ireland, Great Britain and Ireland",
                "source": "majestic",
                "lat": 52.650003,
                "lon": -8.616667,
                "coordinate_source": "raw_latlong",
            },
        ],
    )

    report = check_static_country_coordinate_anomalies(payload_root=root)

    assert report["status"] == "ready"
    assert report["counts"]["checked_rows"] == 2


def test_static_country_coordinate_anomaly_check_prefers_puerto_rico_over_usa_group(tmp_path):
    root = tmp_path / "bundle"
    write_summary(
        root,
        [
            {
                "event_id": "guanica",
                "location_raw": "Town & City, GUANICA, PR, Puerto Rico, USA",
                "source": "majestic",
                "lat": 17.977779,
                "lon": -66.911114,
                "coordinate_source": "raw_latlong",
            }
        ],
    )

    report = check_static_country_coordinate_anomalies(payload_root=root)

    assert report["status"] == "ready"
    assert report["counts"]["checked_rows"] == 1


def test_static_country_coordinate_anomaly_check_supports_reunion_israel_morocco_and_saudi_arabia(tmp_path):
    root = tmp_path / "bundle"
    write_summary(
        root,
        [
            {
                "event_id": "reunion",
                "location_raw": "Saint-Louis, , REUNION",
                "source": "mufon",
                "lat": -21.28585,
                "lon": 55.41124,
                "coordinate_source": "geocoded",
            },
            {
                "event_id": "israel",
                "location_raw": "HAIFA, ISR, ME",
                "source": "ufocat",
                "lat": 32.82,
                "lon": 34.98,
                "coordinate_source": "raw_latlong",
            },
            {
                "event_id": "morocco",
                "location_raw": "CASABLANCA, MOR, AF",
                "source": "ufocat",
                "lat": 33.65,
                "lon": -7.58,
                "coordinate_source": "raw_latlong",
            },
            {
                "event_id": "saudi",
                "location_raw": "RIYADH, SAUDI ARABIA",
                "source": "ufocat",
                "lat": 24.71,
                "lon": 46.67,
                "coordinate_source": "raw_latlong",
            },
        ],
    )

    report = check_static_country_coordinate_anomalies(payload_root=root)

    assert report["status"] == "ready"
    assert report["counts"]["checked_rows"] == 4


def test_static_country_coordinate_anomaly_check_does_not_treat_italian_re_as_reunion(tmp_path):
    root = tmp_path / "bundle"
    write_summary(
        root,
        [
            {
                "event_id": "rome",
                "location_raw": "ROMA, Roma, ITA, RE",
                "source": "ufocat",
                "lat": 41.88,
                "lon": 12.5,
                "coordinate_source": "raw_latlong",
            }
        ],
    )

    report = check_static_country_coordinate_anomalies(payload_root=root)

    assert report["status"] == "ready"
    assert report["counts"]["checked_rows"] == 1


def test_static_country_coordinate_anomaly_check_does_not_prefer_canada_word_over_us_token(tmp_path):
    root = tmp_path / "bundle"
    write_summary(
        root,
        [
            {
                "event_id": "canada-ky",
                "location_raw": "canada, KY, US",
                "source": "mufon",
                "lat": 37.6,
                "lon": -82.7,
                "coordinate_source": "geocoded",
            }
        ],
    )

    report = check_static_country_coordinate_anomalies(payload_root=root)

    assert report["status"] == "ready"
    assert report["counts"]["checked_rows"] == 1


def test_static_country_coordinate_anomaly_check_treats_chi_great_britain_group_as_channel_islands(tmp_path):
    root = tmp_path / "bundle"
    write_summary(
        root,
        [
            {
                "event_id": "guernsey",
                "location_raw": "Islands, GRANDES ROCQUES, GUERNSEY, CHI, Great Britain and Ireland",
                "source": "majestic",
                "lat": 49.47,
                "lon": -2.58,
                "coordinate_source": "raw_latlong",
            }
        ],
    )

    report = check_static_country_coordinate_anomalies(payload_root=root)

    assert report["status"] == "ready"
    assert report["counts"]["checked_rows"] == 1
