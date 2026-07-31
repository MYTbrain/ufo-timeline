import json
import zipfile

from scripts.apply_country_polygon_coordinate_repair_preview import (
    apply_country_polygon_coordinate_repair_preview,
)


def write_country_info(path):
    path.write_text(
        "\n".join(
            [
                "FR\tFRA\t250\tFR\tFrance\tParis\t547030\t66987244\tEU\t.fr\tEUR\tEuro\t33",
                "CH\tCHE\t756\tSZ\tSwitzerland\tBern\t41290\t8516543\tEU\t.ch\tCHF\tFranc\t41",
                "CA\tCAN\t124\tCA\tCanada\tOttawa\t9984670\t33679000\tNA\t.ca\tCAD\tDollar\t1",
                "GB\tGBR\t826\tUK\tUnited Kingdom\tLondon\t244820\t62348447\tEU\t.uk\tGBP\tPound\t44",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def write_countries(path):
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "France"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 41], [10, 41], [10, 52], [0, 52], [0, 41]]],
                },
            },
            {
                "type": "Feature",
                "properties": {"name": "Switzerland"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[5, 45], [11, 45], [11, 48], [5, 48], [5, 45]]],
                },
            },
            {
                "type": "Feature",
                "properties": {"name": "Canada"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[-140, 40], [-50, 40], [-50, 80], [-140, 80], [-140, 40]]],
                },
            },
            {
                "type": "Feature",
                "properties": {"name": "United Kingdom"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[-7, 49], [0, 49], [0, 59], [-7, 59], [-7, 49]]],
                },
            },
        ],
    }
    path.write_text(json.dumps(geojson), encoding="utf-8")


def geonames_line(
    geoname_id,
    name,
    ascii_name,
    alternate_names,
    lat,
    lon,
    feature_class,
    feature_code,
    country_code,
    population=0,
):
    return "\t".join(
        [
            geoname_id,
            name,
            ascii_name,
            alternate_names,
            str(lat),
            str(lon),
            feature_class,
            feature_code,
            country_code,
            "",
            "",
            "",
            "",
            "",
            str(population),
            "",
            "0",
            "Europe/Paris",
            "2025-01-01",
        ]
    )


def write_geonames(path):
    lines = [
        geonames_line("2995469", "Marseille", "Marseille", "Marselha", 43.29695, 5.38107, "P", "PPLA", "FR", 870731),
        geonames_line("2984782", "Quarouble", "Quarouble", "", 50.38634, 3.62306, "P", "PPL", "FR", 2800),
        geonames_line("2660076", "Jungfrau", "Jungfrau", "", 46.53674, 7.96234, "T", "MT", "CH", 0),
        geonames_line("6174041", "Victoria", "Victoria", "", 48.4359, -123.35155, "P", "PPLA", "CA", 289625),
        geonames_line("2641598", "Newbiggin-by-the-Sea", "Newbiggin-by-the-Sea", "Newbiggin-on-Sea", 55.18532, -1.51469, "P", "PPL", "GB", 6414),
    ]
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("allCountries.txt", "\n".join(lines) + "\n")


def run_repair(tmp_path, events):
    events_path = tmp_path / "events.jsonl"
    events_path.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")
    countries = tmp_path / "countries.geojson"
    country_info = tmp_path / "countryInfo.txt"
    geonames = tmp_path / "allCountries.zip"
    write_countries(countries)
    write_country_info(country_info)
    write_geonames(geonames)
    report = apply_country_polygon_coordinate_repair_preview(
        input_path=events_path,
        countries_geojson=countries,
        geonames_zip=geonames,
        country_info=country_info,
        output_dir=tmp_path / "out",
        report_output=tmp_path / "report.json",
    )
    rows = [
        json.loads(line)
        for line in (tmp_path / "out" / "deduped_events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return report, rows


def test_country_polygon_repair_replaces_offshore_city_with_same_country_geonames(tmp_path):
    report, rows = run_repair(
        tmp_path,
        [
            {
                "canonical_event_id": "marseille",
                "location_raw": "MARSEILLE, Bouches-Rhon, FRA, EU",
                "raw_fields": {"STATE": "FRA", "REGION": "EU"},
                "lat": 43.27,
                "lon": -5.4,
                "coordinate_source": "raw_latlong",
                "location_precision": "exact_coords",
            },
            {
                "canonical_event_id": "quarouble",
                "location_raw": "QUAROUBLE, Nord, FRA, EU",
                "raw_fields": {"STATE": "FRA", "REGION": "EU"},
                "lat": 50.39,
                "lon": -3.615,
                "coordinate_source": "raw_latlong",
                "location_precision": "exact_coords",
            },
        ],
    )

    assert report["repaired_event_count"] == 2
    assert rows[0]["lat"] == 43.29695
    assert rows[0]["lon"] == 5.38107
    assert rows[1]["lat"] == 50.38634
    assert rows[1]["lon"] == 3.62306
    assert rows[0]["country_polygon_coordinate_repair_action"] == "replace_with_same_country_geonames_feature"


def test_country_polygon_repair_can_use_same_country_mountain_feature(tmp_path):
    report, rows = run_repair(
        tmp_path,
        [
            {
                "canonical_event_id": "jungfrau",
                "location_raw": "JUNGFRAU, Bern, SUI, EU",
                "raw_fields": {"STATE": "SUI", "REGION": "EU"},
                "lat": 46.54,
                "lon": -5.0,
                "coordinate_source": "raw_latlong",
            },
        ],
    )

    assert report["repaired_event_count"] == 1
    assert rows[0]["lat"] == 46.53674
    assert rows[0]["lon"] == 7.96234
    assert rows[0]["location_precision"] == "mapped"


def test_country_polygon_repair_skips_offshore_like_locations(tmp_path):
    report, rows = run_repair(
        tmp_path,
        [
            {
                "canonical_event_id": "sea",
                "location_raw": "MEDITERRANEAN SEA, Var, FRA, EU",
                "raw_fields": {"STATE": "FRA", "REGION": "EU"},
                "lat": 43.0,
                "lon": -4.0,
                "coordinate_source": "raw_latlong",
            },
        ],
    )

    assert report["skipped_offshore_like_count"] == 1
    assert report["repaired_event_count"] == 0
    assert report["quarantined_event_count"] == 0
    assert rows[0]["lat"] == 43.0
    assert rows[0]["lon"] == -4.0


def test_country_polygon_repair_does_not_treat_on_sea_town_names_as_offshore(tmp_path):
    report, rows = run_repair(
        tmp_path,
        [
            {
                "canonical_event_id": "newbiggin",
                "location_raw": "NEWBIGGIN-ON-SEA, Northumberland, GBR, EU",
                "raw_fields": {"STATE": "GBR", "REGION": "EU"},
                "lat": 55.18,
                "lon": -20.0,
                "coordinate_source": "raw_latlong",
            },
        ],
    )

    assert report["skipped_offshore_like_count"] == 0
    assert report["repaired_event_count"] == 1
    assert rows[0]["lat"] == 55.18532
    assert rows[0]["lon"] == -1.51469
    assert rows[0]["country_polygon_coordinate_repair_action"] == "replace_with_same_country_geonames_feature"


def test_country_polygon_repair_flips_longitude_when_declared_country_contains_flipped_point(tmp_path):
    report, rows = run_repair(
        tmp_path,
        [
            {
                "canonical_event_id": "newbiggin-sign",
                "location_raw": "NOLOCALMATCH-ON-SEA, RADAR SITE, Northumberla, GBR, EU",
                "raw_fields": {"STATE": "GBR", "REGION": "EU"},
                "lat": 55.18,
                "lon": 1.5,
                "coordinate_source": "raw_latlong",
                "location_precision": "exact_coords",
            },
        ],
    )

    assert report["declared_country_sign_flip_count"] == 1
    assert report["repaired_event_count"] == 1
    assert rows[0]["lat"] == 55.18
    assert rows[0]["lon"] == -1.5
    assert rows[0]["coordinate_source"] == "source_coordinates"
    assert rows[0]["country_polygon_coordinate_repair_action"] == "replace_with_declared_country_sign_flip"


def test_country_polygon_repair_flips_mediterranean_france_offshore_sign(tmp_path):
    report, rows = run_repair(
        tmp_path,
        [
            {
                "canonical_event_id": "med",
                "location_raw": "MEDITERANEAN SEA, Var, FRA, EU",
                "raw_fields": {"STATE": "FRA", "REGION": "EU"},
                "lat": 43.07,
                "lon": -5.77,
                "coordinate_source": "raw_latlong",
            },
        ],
    )

    assert report["offshore_sign_flip_count"] == 1
    assert report["repaired_event_count"] == 1
    assert rows[0]["lat"] == 43.07
    assert rows[0]["lon"] == 5.77
    assert rows[0]["country_polygon_coordinate_repair_action"] == "replace_with_offshore_mediterranean_sign_flip"


def test_country_polygon_repair_unmaps_land_like_row_without_safe_match(tmp_path):
    report, rows = run_repair(
        tmp_path,
        [
            {
                "canonical_event_id": "unknown",
                "location_raw": "NOTAREALPLACE, Nord, FRA, EU",
                "raw_fields": {"STATE": "FRA", "REGION": "EU"},
                "lat": 50.0,
                "lon": -4.0,
                "coordinate_source": "raw_latlong",
            },
        ],
    )

    assert report["quarantined_event_count"] == 1
    assert rows[0]["lat"] is None
    assert rows[0]["lon"] is None
    assert rows[0]["coordinate_source"] == "unresolved"


def test_country_polygon_repair_is_scoped_and_does_not_country_only_repair_canada(tmp_path):
    report, rows = run_repair(
        tmp_path,
        [
            {
                "canonical_event_id": "victoria",
                "location_raw": "VICTORIA, Capital, BC, CN",
                "raw_fields": {"STATE": "BC", "REGION": "CN"},
                "lat": 48.44,
                "lon": -10.0,
                "coordinate_source": "raw_latlong",
            },
        ],
    )

    assert report["checked_outside_declared_country_polygon_count"] == 0
    assert report["repaired_event_count"] == 0
    assert rows[0]["lat"] == 48.44
    assert rows[0]["lon"] == -10.0
    assert "country_polygon_coordinate_repair_action" not in rows[0]
