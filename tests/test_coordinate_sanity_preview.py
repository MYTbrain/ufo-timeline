import json

from scripts.apply_coordinate_sanity_preview import apply_coordinate_sanity_preview, inferred_country_name


def test_coordinate_sanity_preview_flips_longitude_when_country_polygon_matches(tmp_path):
    countries = tmp_path / "countries.geojson"
    countries.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"name": "United States of America"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[-125, 24], [-66, 24], [-66, 50], [-125, 50], [-125, 24]]],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {"name": "Germany"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[5, 47], [16, 47], [16, 56], [5, 56], [5, 47]]],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {"name": "Mexico"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[-119, 14], [-86, 14], [-86, 33], [-119, 33], [-119, 14]]],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {"name": "Canada"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[-142, 41], [-52, 41], [-52, 84], [-142, 84], [-142, 41]]],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {"name": "New Zealand"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[166, -47], [179, -47], [179, -34], [166, -34], [166, -47]]],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {"name": "Australia"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[112, -44], [154, -44], [154, -10], [112, -10], [112, -44]]],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {"name": "France"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[-4, 41], [10, 41], [10, 52], [-4, 52], [-4, 41]]],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {"name": "United Kingdom"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[-8, 49], [2, 49], [2, 59], [-8, 59], [-8, 49]]],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {"name": "Ireland"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[-11, 51], [-5, 51], [-5, 56], [-11, 56], [-11, 51]]],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {"name": "Portugal"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[-10, 36], [-6, 36], [-6, 43], [-10, 43], [-10, 36]]],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {"name": "Italy"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[6, 36], [19, 36], [19, 48], [6, 48], [6, 36]]],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {"name": "Sweden"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[10, 55], [25, 55], [25, 70], [10, 70], [10, 55]]],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {"name": "Greece"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[19, 34], [29, 34], [29, 42], [19, 42], [19, 34]]],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {"name": "Japan"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[122, 24], [146, 24], [146, 46], [122, 46], [122, 24]]],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {"name": "China"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[73, 18], [136, 18], [136, 54], [73, 54], [73, 18]]],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {"name": "Venezuela"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[-74, 0], [-59, 0], [-59, 13], [-74, 13], [-74, 0]]],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {"name": "Colombia"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[-82, -5], [-66, -5], [-66, 13], [-82, 13], [-82, -5]]],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {"name": "Honduras"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[-90, 12], [-83, 12], [-83, 17], [-90, 17], [-90, 12]]],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {"name": "Bermuda"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[-65.1, 31.8], [-64, 31.8], [-64, 32.8], [-65.1, 32.8], [-65.1, 31.8]]],
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    events = tmp_path / "events.jsonl"
    events.write_text(
        "\n".join(
            [
                '{"canonical_event_id":"ny","source_name":"ufocat","source_row_number":1,"location_raw":"FLATBUSH, BROOKLYN, NY, US","country":"US","state_province":"NY","lat":40.645,"lon":73.96,"coordinate_source":"source_coordinates"}',
                '{"canonical_event_id":"berlin","source_name":"ufocat","source_row_number":2,"location_raw":"WEST BERLIN, GER, EU","country":"EU","state_province":"GER","lat":52.47,"lon":-13.4,"coordinate_source":"source_coordinates"}',
                '{"canonical_event_id":"ok","source_name":"ufocat","source_row_number":3,"location_raw":"SEATTLE, WA, US","country":"US","state_province":"WA","lat":47.61,"lon":-122.33,"coordinate_source":"source_coordinates"}',
                '{"canonical_event_id":"geo","source_name":"mufon","source_row_number":4,"location_raw":"Seattle, WA, US","country":"US","state_province":"WA","lat":47.61,"lon":122.33,"coordinate_source":"geocoded"}',
                '{"canonical_event_id":"mex","source_name":"ufocat","source_row_number":5,"location_raw":"TEQUESQUITENGO LAKE, Morelos, MEX, CA","country":"CA","state_province":"MEX","lat":19.42,"lon":99.16,"coordinate_source":"source_coordinates"}',
                '{"canonical_event_id":"nz","source_name":"ufocat","source_row_number":6,"location_raw":"TAURANGA, Bay o Plenty, NZL, AU","country":"AU","state_province":"NZL","lat":-37.7,"lon":-176.18,"coordinate_source":"source_coordinates"}',
                '{"canonical_event_id":"south_australia","source_name":"ufocat","source_row_number":7,"location_raw":"ADELAIDE, Adelaide, SAU, AU","country":"AU","state_province":"SAU","lat":-34.93,"lon":-138.6,"coordinate_source":"source_coordinates"}',
                '{"canonical_event_id":"ontario","source_name":"ufocat","source_row_number":8,"location_raw":"PETERBOROUGH, ON, CN","country":"CN","state_province":"ON","lat":44.3,"lon":78.32,"coordinate_source":"source_coordinates","raw_fields":{"REGION":"CN","STATE":"ON"}}',
                '{"canonical_event_id":"hawaii","source_name":"ufocat","source_row_number":9,"location_raw":"AIEA, HI, P","country":"P","state_province":"HI","lat":21.39,"lon":157.93,"coordinate_source":"source_coordinates","raw_fields":{"REGION":"P","STATE":"HI"}}',
                '{"canonical_event_id":"madison","source_name":"ufocat","source_row_number":10,"location_raw":"MADISON, Dane, WI, EU","country":"EU","state_province":"WI","lat":43.07,"lon":89.38,"coordinate_source":"source_coordinates","raw_fields":{"REGION":"EU","STATE":"WI"}}',
                '{"canonical_event_id":"don_mills","source_name":"ufocat","source_row_number":11,"location_raw":"DON MILLS, Toronto, CN, CN","country":"CN","state_province":"CN","lat":43.74,"lon":79.34,"coordinate_source":"source_coordinates","raw_fields":{"REGION":"CN","STATE":"CN"}}',
                '{"canonical_event_id":"bridgend","source_name":"ufocat","source_row_number":12,"location_raw":"BRIDGEND, So Glamorgan, GBR, EU","country":"EU","state_province":"GBR","lat":51.52,"lon":3.35,"coordinate_source":"source_coordinates","raw_fields":{"REGION":"EU","STATE":"GBR"}}',
                '{"canonical_event_id":"dublin","source_name":"ufocat","source_row_number":13,"location_raw":"DUBLIN, Dublin, IRL, EU","country":"EU","state_province":"IRL","lat":53.33,"lon":6.25,"coordinate_source":"source_coordinates","raw_fields":{"REGION":"EU","STATE":"IRL"}}',
                '{"canonical_event_id":"fatima","source_name":"ufocat","source_row_number":14,"location_raw":"FATIMA, Santarem, POR, EU","country":"EU","state_province":"POR","lat":39.62,"lon":8.65,"coordinate_source":"source_coordinates","raw_fields":{"REGION":"EU","STATE":"POR"}}',
                '{"canonical_event_id":"cassis","source_name":"ufocat","source_row_number":15,"location_raw":"CASSIS, Bouches-Rhon, FRA, EU","country":"EU","state_province":"FRA","lat":43.216,"lon":-5.54,"coordinate_source":"source_coordinates","raw_fields":{"REGION":"EU","STATE":"FRA"}}',
                '{"canonical_event_id":"roma","source_name":"ufocat","source_row_number":16,"location_raw":"ROMA, Roma, ITA, EU","country":"EU","state_province":"ITA","lat":41.88,"lon":-12.5,"coordinate_source":"source_coordinates","raw_fields":{"REGION":"EU","STATE":"ITA"}}',
                '{"canonical_event_id":"sweden","source_name":"ufocat","source_row_number":17,"location_raw":"NAVSJON, Ostergotland, SWE, EU","country":"EU","state_province":"SWE","lat":58.66,"lon":-16.71,"coordinate_source":"source_coordinates","raw_fields":{"REGION":"EU","STATE":"SWE"}}',
                '{"canonical_event_id":"japan","source_name":"ufocat","source_row_number":18,"location_raw":"FUKUOKA, Fukuoka, JPN, AS","country":"AS","state_province":"JPN","lat":40.27,"lon":-141.33,"coordinate_source":"source_coordinates","raw_fields":{"REGION":"AS","STATE":"JPN"}}',
                '{"canonical_event_id":"china","source_name":"ufocat","source_row_number":19,"location_raw":"SHANGHAI, Shanghai, CHN, AS","country":"AS","state_province":"CHN","lat":31.27,"lon":-121.42,"coordinate_source":"source_coordinates","raw_fields":{"REGION":"AS","STATE":"CHN"}}',
                '{"canonical_event_id":"greece","source_name":"ufocat","source_row_number":20,"location_raw":"ATHENS, Attica, GRE, EU","country":"EU","state_province":"GRE","lat":37.98,"lon":-23.72,"coordinate_source":"source_coordinates","raw_fields":{"REGION":"EU","STATE":"GRE"}}',
                '{"canonical_event_id":"france_ok","source_name":"ufocat","source_row_number":21,"location_raw":"CANET-PLAGE, Pyrénées-Orientales, FRA, EU","country":"EU","state_province":"FRA","lat":42.70,"lon":3.03,"coordinate_source":"source_coordinates","raw_fields":{"REGION":"EU","STATE":"FRA"}}',
                '{"canonical_event_id":"usvi","source_name":"ufocat","source_row_number":22,"location_raw":"ST THOMAS, US VIRGIN ISLANDS, St Thomas, ISV, CA","country":"CA","state_province":"ISV","lat":18.33,"lon":64.92,"coordinate_source":"source_coordinates","raw_fields":{"REGION":"CA","STATE":"ISV","LOCATION":"ST THOMAS, US VIRGIN ISLANDS"}}',
                '{"canonical_event_id":"venezuela","source_name":"ufocat","source_row_number":23,"location_raw":"VALENCIA, Carabobo, VEN, SA","country":"SA","state_province":"VEN","lat":10.23,"lon":67.98,"coordinate_source":"source_coordinates","raw_fields":{"REGION":"SA","STATE":"VEN"}}',
                '{"canonical_event_id":"colombia","source_name":"ufocat","source_row_number":24,"location_raw":"MANIZALES, Caldas, COL, SA","country":"SA","state_province":"COL","lat":5.05,"lon":75.53,"coordinate_source":"source_coordinates","raw_fields":{"REGION":"SA","STATE":"COL"}}',
                '{"canonical_event_id":"honduras","source_name":"ufocat","source_row_number":25,"location_raw":"TEGUCIGALPA, HON, CA","country":"CA","state_province":"HON","lat":14.27,"lon":87.1,"coordinate_source":"source_coordinates","raw_fields":{"REGION":"CA","STATE":"HON"}}',
                '{"canonical_event_id":"bermuda","source_name":"ufocat","source_row_number":26,"location_raw":"BERMUDA, BER, A","country":"A","state_province":"BER","lat":32.38,"lon":64.67,"coordinate_source":"source_coordinates","raw_fields":{"REGION":"A","STATE":"BER"}}',
                '{"canonical_event_id":"ukraine","source_name":"ufocat","source_row_number":27,"location_raw":"KIEV, Kiev, UKR, EU","country":"EU","state_province":"UKR","lat":50.42,"lon":-30.5,"coordinate_source":"source_coordinates","raw_fields":{"REGION":"EU","STATE":"UKR"}}',
                '{"canonical_event_id":"croatia","source_name":"ufocat","source_row_number":28,"location_raw":"ZAGREB, Zagreb, CRO, EU","country":"EU","state_province":"CRO","lat":45.8,"lon":-15.97,"coordinate_source":"source_coordinates","raw_fields":{"REGION":"EU","STATE":"CRO"}}',
                '{"canonical_event_id":"bulgaria","source_name":"ufocat","source_row_number":29,"location_raw":"SOFIYA, Sofia, BUL, EU","country":"EU","state_province":"BUL","lat":42.67,"lon":-23.3,"coordinate_source":"source_coordinates","raw_fields":{"REGION":"EU","STATE":"BUL"}}',
                '{"canonical_event_id":"lithuania","source_name":"ufocat","source_row_number":30,"location_raw":"KAUNAS, Kauno, LIT, EU","country":"EU","state_province":"LIT","lat":54.7,"lon":-23.9,"coordinate_source":"source_coordinates","raw_fields":{"REGION":"EU","STATE":"LIT"}}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = apply_coordinate_sanity_preview(
        input_path=events,
        countries_geojson=countries,
        output_dir=tmp_path / "out",
        report_output=tmp_path / "report.json",
    )

    rows = [json.loads(line) for line in (tmp_path / "out" / "deduped_events.jsonl").read_text(encoding="utf-8").splitlines()]

    assert report["canonical_outputs_mutated"] is False
    assert report["corrected_event_count"] == 27
    assert rows[0]["lon"] == -73.96
    assert rows[0]["coordinate_sanity_action"] == "flip_lon"
    assert rows[1]["lon"] == 13.4
    assert rows[1]["coordinate_sanity_country"] == "Germany"
    assert rows[2]["lon"] == -122.33
    assert rows[3]["lon"] == 122.33
    assert "coordinate_sanity_action" not in rows[3]
    assert rows[4]["lon"] == -99.16
    assert rows[4]["coordinate_sanity_country"] == "Mexico"
    assert rows[5]["lon"] == 176.18
    assert rows[5]["coordinate_sanity_country"] == "New Zealand"
    assert rows[6]["lon"] == 138.6
    assert rows[6]["coordinate_sanity_country"] == "Australia"
    assert rows[7]["lon"] == -78.32
    assert rows[7]["coordinate_sanity_country"] == "Canada"
    assert rows[8]["lon"] == -157.93
    assert rows[8]["coordinate_sanity_country"] == "United States of America"
    assert rows[9]["lon"] == -89.38
    assert rows[9]["coordinate_sanity_country"] == "United States of America"
    assert rows[10]["lon"] == -79.34
    assert rows[10]["coordinate_sanity_country"] == "Canada"
    assert rows[11]["lon"] == -3.35
    assert rows[11]["coordinate_sanity_country"] == "United Kingdom"
    assert rows[12]["lon"] == -6.25
    assert rows[12]["coordinate_sanity_country"] == "Ireland"
    assert rows[13]["lon"] == -8.65
    assert rows[13]["coordinate_sanity_country"] == "Portugal"
    assert rows[14]["lon"] == 5.54
    assert rows[14]["coordinate_sanity_country"] == "France"
    assert rows[15]["lon"] == 12.5
    assert rows[15]["coordinate_sanity_country"] == "Italy"
    assert rows[16]["lon"] == 16.71
    assert rows[16]["coordinate_sanity_country"] == "Sweden"
    assert rows[17]["lon"] == 141.33
    assert rows[17]["coordinate_sanity_country"] == "Japan"
    assert rows[18]["lon"] == 121.42
    assert rows[18]["coordinate_sanity_country"] == "China"
    assert rows[19]["lon"] == 23.72
    assert rows[19]["coordinate_sanity_country"] == "Greece"
    assert rows[20]["lon"] == 3.03
    assert "coordinate_sanity_action" not in rows[20]
    assert rows[21]["lon"] == -64.92
    assert rows[21]["coordinate_sanity_country"] == "United States Virgin Islands"
    assert rows[22]["lon"] == -67.98
    assert rows[22]["coordinate_sanity_country"] == "Venezuela"
    assert rows[23]["lon"] == -75.53
    assert rows[23]["coordinate_sanity_country"] == "Colombia"
    assert rows[24]["lon"] == -87.1
    assert rows[24]["coordinate_sanity_country"] == "Honduras"
    assert rows[25]["lon"] == -64.67
    assert rows[25]["coordinate_sanity_country"] == "Bermuda"
    assert rows[26]["lon"] == 30.5
    assert rows[26]["coordinate_sanity_country"] == "Ukraine"
    assert rows[27]["lon"] == 15.97
    assert rows[27]["coordinate_sanity_country"] == "Croatia"
    assert rows[28]["lon"] == 23.3
    assert rows[28]["coordinate_sanity_country"] == "Bulgaria"
    assert rows[29]["lon"] == 23.9
    assert rows[29]["coordinate_sanity_country"] == "Lithuania"


def test_coordinate_sanity_us_bounds_include_western_aleutians():
    from scripts.apply_coordinate_sanity_preview import candidate_in_bounded_flip_lon_range

    assert candidate_in_bounded_flip_lon_range("United States of America", 51.87395, -176.63402) is True
    assert candidate_in_bounded_flip_lon_range("United States of America", 63.77921, -171.73463) is True


def test_coordinate_sanity_flips_new_zealand_mainland_even_when_antimeridian_polygon_contains_negative_copy(tmp_path):
    countries = tmp_path / "countries.geojson"
    countries.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"name": "New Zealand"},
                        "geometry": {
                            "type": "MultiPolygon",
                            "coordinates": [
                                [[[166, -48], [179, -48], [179, -33], [166, -33], [166, -48]]],
                                [[[-180, -48], [-170, -48], [-170, -33], [-180, -33], [-180, -48]]],
                            ],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    events = tmp_path / "events.jsonl"
    events.write_text(
        "\n".join(
            [
                '{"canonical_event_id":"nelson","source_name":"ufocat","location_raw":"NELSON, Nelson, NZL, AU","country":"AU","state_province":"NZL","lat":-41.3,"lon":-173.28,"coordinate_source":"source_coordinates"}',
                '{"canonical_event_id":"chatham","source_name":"ufocat","location_raw":"CHATHAM ISLANDS, NZL, AU","country":"AU","state_province":"NZL","lat":-43.9,"lon":-176.5,"coordinate_source":"source_coordinates"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = apply_coordinate_sanity_preview(
        input_path=events,
        countries_geojson=countries,
        output_dir=tmp_path / "out",
        report_output=tmp_path / "report.json",
    )
    rows = [json.loads(line) for line in (tmp_path / "out" / "deduped_events.jsonl").read_text(encoding="utf-8").splitlines()]

    assert report["corrected_event_count"] == 1
    assert rows[0]["lon"] == 173.28
    assert rows[0]["coordinate_sanity_action"] == "flip_lon_new_zealand_mainland"
    assert rows[1]["lon"] == -176.5
    assert "coordinate_sanity_action" not in rows[1]


def test_inferred_country_prefers_explicit_country_over_ambiguous_state_code():
    event = {
        "location_raw": "Metropolis, LISBON, PORTUGAL, EST, Portugal",
        "country": "Portugal",
        "state_province": "EST",
    }

    assert inferred_country_name(event) == "Portugal"


def test_inferred_country_prefers_tunisia_text_over_mon_state_code():
    event = {
        "location_raw": "Metropolis, NNW / MONASTIR, TUNISIA, MON, Tunisia",
        "country": "Tunisia",
        "state_province": "MON",
        "raw_fields": {"REGION": "Tunisia", "STATE": "MON"},
    }

    assert inferred_country_name(event) == "Tunisia"


def test_inferred_country_prefers_zimbabwe_text_over_bul_state_code():
    event = {
        "location_raw": "Town & City, BULAWAYO, ZIMBABWE, BUL, Zimbabwe & Zambia",
        "country": "Zimbabwe & Zambia",
        "state_province": "BUL",
        "raw_fields": {"REGION": "Zimbabwe & Zambia", "STATE": "BUL"},
    }

    assert inferred_country_name(event) == "Zimbabwe"


def test_inferred_country_prefers_zambia_text_over_shared_zimbabwe_zambia_region():
    event = {
        "location_raw": "Mountains, BROKEN HILL = KABWE, ZAMBIA, ZAM, Zimbabwe & Zambia",
        "country": "Zimbabwe & Zambia",
        "state_province": "ZAM",
        "raw_fields": {"REGION": "Zimbabwe & Zambia", "STATE": "ZAM"},
    }

    assert inferred_country_name(event) == "Zambia"


def test_inferred_country_uses_zambia_city_hint_when_legacy_state_code_is_wrong():
    event = {
        "location_raw": "KITWE, ZIM, AF",
        "country": "AF",
        "state_province": "ZIM",
        "raw_fields": {"REGION": "AF", "STATE": "ZIM"},
    }

    assert inferred_country_name(event) == "Zambia"


def test_inferred_country_does_not_match_zambia_hint_inside_other_city_names():
    event = {
        "location_raw": "ALMANSA, Albacete, ESP, EU",
        "country": "EU",
        "state_province": "ESP",
        "raw_fields": {"REGION": "EU", "STATE": "ESP"},
    }

    assert inferred_country_name(event) == "Spain"


def test_inferred_country_does_not_treat_australia_broken_hill_as_zambia():
    event = {
        "location_raw": "Desert, BROKEN HILL, AUSTRALIA, NSW, Australia",
        "country": "Australia",
        "state_province": "NSW",
        "raw_fields": {"REGION": "Australia", "STATE": "NSW"},
    }

    assert inferred_country_name(event) == "Australia"


def test_inferred_country_does_not_treat_salisbury_uk_as_zimbabwe():
    event = {
        "location_raw": "SALISBURY, Wiltshire, GBR, EU",
        "country": "EU",
        "state_province": "GBR",
        "raw_fields": {"REGION": "EU", "STATE": "GBR"},
    }

    assert inferred_country_name(event) == "United Kingdom"


def test_inferred_country_keeps_eu_state_country_code_when_region_is_generic():
    event = {
        "location_raw": "WIEN (VIENNA), Vienna, AUT, EU",
        "country": "EU",
        "state_province": "AUT",
        "raw_fields": {"REGION": "EU", "STATE": "AUT"},
    }

    assert inferred_country_name(event) == "Austria"


def test_inferred_country_treats_legacy_chi_as_chile():
    event = {
        "location_raw": "ANTOFAGASTA, Antofagasta, CHI, SA",
        "country": "SA",
        "state_province": "CHI",
        "raw_fields": {"REGION": "SA", "STATE": "CHI"},
    }

    assert inferred_country_name(event) == "Chile"


def test_inferred_country_treats_legacy_ned_as_netherlands():
    event = {
        "location_raw": "DRACHTEN, BEL, Friesland, NED, EU",
        "country": "EU",
        "state_province": "NED",
        "raw_fields": {"REGION": "EU", "STATE": "NED"},
    }

    assert inferred_country_name(event) == "Netherlands"


def test_inferred_country_treats_bahamas_bs_as_bahamas():
    event = {
        "location_raw": "NASSAU, BS",
        "country": "BS",
        "state_province": "",
        "raw_fields": {"REGION": "BS", "STATE": ""},
    }

    assert inferred_country_name(event) == "Bahamas"


def test_inferred_country_treats_reunion_name_as_reunion():
    event = {
        "location_raw": "Saint-Louis, , REUNION",
        "country": "REUNION",
        "state_province": "",
        "raw_fields": {"REGION": "REUNION", "STATE": ""},
    }

    assert inferred_country_name(event) == "Reunion"


def test_inferred_country_does_not_treat_italian_re_token_as_reunion():
    event = {
        "location_raw": "ROMA, Roma, ITA, RE",
        "country": "RE",
        "state_province": "ITA",
        "raw_fields": {"REGION": "RE", "STATE": "ITA"},
    }

    assert inferred_country_name(event) == "Italy"


def test_inferred_country_prefers_ireland_state_over_great_britain_region():
    event = {
        "location_raw": "Town & City, LIMERICK, IREL, Ireland, Great Britain and Ireland",
        "country": "Great Britain and Ireland",
        "state_province": "Ireland",
        "raw_fields": {"REGION": "Great Britain and Ireland", "STATE": "Ireland"},
    }

    assert inferred_country_name(event) == "Ireland"


def test_inferred_country_treats_us_puerto_rico_state_as_puerto_rico():
    event = {
        "location_raw": "Town & City, SAN JUAN, PR, Puerto Rico, USA",
        "country": "USA",
        "state_province": "Puerto Rico",
    }

    assert inferred_country_name(event) == "Puerto Rico"


def test_coordinate_sanity_flips_france_internal_admin_sign_error(tmp_path):
    countries = tmp_path / "countries.geojson"
    countries.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"name": "France"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[-6, 41], [10, 41], [10, 52], [-6, 52], [-6, 41]]],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    events = tmp_path / "events.jsonl"
    events.write_text(
        "\n".join(
            [
                '{"canonical_event_id":"orly","source_name":"ufocat","source_row_number":1,"location_raw":"PARIS ORLY APT, Val-Marne, FRA, EU","country":"EU","state_province":"FRA","lat":48.733,"lon":-2.375,"coordinate_source":"source_coordinates","raw_fields":{"REGION":"EU","STATE":"FRA"}}',
                '{"canonical_event_id":"lamballe","source_name":"ufocat","source_row_number":2,"location_raw":"LAMBALLE W, Cotes-Nord, FRA, EU","country":"EU","state_province":"FRA","lat":48.47,"lon":-2.58,"coordinate_source":"source_coordinates","raw_fields":{"REGION":"EU","STATE":"FRA"}}',
                '{"canonical_event_id":"toulouse","source_name":"ufocat","source_row_number":3,"location_raw":"TOULOUSE, Haute-Garonn, FRA, EU","country":"EU","state_province":"FRA","lat":43.61,"lon":-1.41,"coordinate_source":"source_coordinates","raw_fields":{"REGION":"EU","STATE":"FRA"}}',
                '{"canonical_event_id":"la_rochelle","source_name":"ufocat","source_row_number":4,"location_raw":"LA ROCHELLE, Charente-Mar, FRA, EU","country":"EU","state_province":"FRA","lat":46.16,"lon":1.13,"coordinate_source":"source_coordinates","raw_fields":{"REGION":"EU","STATE":"FRA"}}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = apply_coordinate_sanity_preview(
        input_path=events,
        countries_geojson=countries,
        output_dir=tmp_path / "out",
        report_output=tmp_path / "report.json",
    )

    rows = [json.loads(line) for line in (tmp_path / "out" / "deduped_events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert report["corrected_event_count"] == 3
    assert rows[0]["lon"] == 2.375
    assert rows[0]["coordinate_sanity_action"] == "flip_lon_france_admin_hint"
    assert rows[1]["lon"] == -2.58
    assert "coordinate_sanity_action" not in rows[1]
    assert rows[2]["lon"] == 1.41
    assert rows[2]["coordinate_sanity_action"] == "flip_lon_france_admin_hint"
    assert rows[3]["lon"] == -1.13
    assert rows[3]["coordinate_sanity_action"] == "flip_lon_france_admin_hint"
