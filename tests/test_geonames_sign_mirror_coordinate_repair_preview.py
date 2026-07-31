import json
import zipfile

from scripts.apply_geonames_sign_mirror_coordinate_repair_preview import (
    apply_geonames_sign_mirror_coordinate_repair_preview,
)


def write_country_info(path):
    path.write_text(
        "\n".join(
            [
                "FR\tFRA\t250\tFR\tFrance\tParis\t547030\t66987244\tEU\t.fr\tEUR\tEuro\t33",
                "ES\tESP\t724\tSP\tSpain\tMadrid\t504782\t46505963\tEU\t.es\tEUR\tEuro\t34",
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
                    "coordinates": [[[-6, 41], [10, 41], [10, 52], [-6, 52], [-6, 41]]],
                },
            },
            {
                "type": "Feature",
                "properties": {"name": "Spain"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[-10, 35], [5, 35], [5, 44], [-10, 44], [-10, 35]]],
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
        geonames_line("2986732", "Plozevet", "Plozevet", "Plozévet", 47.98546, -4.4261, "P", "PPL", "FR", 2976),
        geonames_line("2514343", "Minorca", "Minorca", "Menorca", 39.97466, 4.07405, "T", "ISL", "ES", 0),
        geonames_line("2641598", "Newbiggin-by-the-Sea", "Newbiggin-by-the-Sea", "Newbiggin-on-Sea", 55.18532, -1.51469, "P", "PPL", "GB", 6414),
        geonames_line("2971041", "Toulouse", "Toulouse", "", 43.60426, 1.44367, "P", "PPLA", "FR", 493465),
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
    report = apply_geonames_sign_mirror_coordinate_repair_preview(
        input_path=events_path,
        countries_geojson=countries,
        country_info=country_info,
        geonames_zip=geonames,
        output_dir=tmp_path / "out",
        report_output=tmp_path / "report.json",
    )
    rows = [
        json.loads(line)
        for line in (tmp_path / "out" / "deduped_events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return report, rows


def test_repair_replaces_france_western_longitude_sign_mirror(tmp_path):
    report, rows = run_repair(
        tmp_path,
        [
            {
                "canonical_event_id": "plozevet",
                "location_raw": "PLOZEVET, Finistere, FRA, EU",
                "raw_fields": {"STATE": "FRA", "REGION": "EU"},
                "lat": 47.985,
                "lon": 4.426,
                "coordinate_source": "raw_latlong",
                "location_precision": "exact_coords",
            },
        ],
    )

    assert report["repaired_event_count"] == 1
    assert rows[0]["lat"] == 47.98546
    assert rows[0]["lon"] == -4.4261
    assert rows[0]["coordinate_source"] == "geocoded"
    assert rows[0]["location_precision"] == "city"
    assert rows[0]["geonames_sign_mirror_coordinate_original_lon"] == 4.426


def test_repair_replaces_spain_eastern_longitude_sign_mirror(tmp_path):
    report, rows = run_repair(
        tmp_path,
        [
            {
                "canonical_event_id": "menorca",
                "location_raw": "MENORCA, Baleares, ESP, EU",
                "raw_fields": {"STATE": "ESP", "REGION": "EU"},
                "lat": 40.0,
                "lon": -4.0,
                "coordinate_source": "source_coordinates",
                "location_precision": "exact_coords",
            },
        ],
    )

    assert report["repaired_event_count"] == 1
    assert rows[0]["lat"] == 39.97466
    assert rows[0]["lon"] == 4.07405
    assert rows[0]["location_precision"] == "mapped"


def test_repair_skips_explicit_offshore_rows(tmp_path):
    report, rows = run_repair(
        tmp_path,
        [
            {
                "canonical_event_id": "sea",
                "location_raw": "ATLANTIC OCEAN OFF FRANCE, FRA, EU",
                "raw_fields": {"STATE": "FRA", "REGION": "EU"},
                "lat": 47.985,
                "lon": 4.426,
                "coordinate_source": "raw_latlong",
            },
        ],
    )

    assert report["repaired_event_count"] == 0
    assert report["skipped_offshore_like_count"] == 1
    assert rows[0]["lon"] == 4.426


def test_repair_does_not_change_correct_sign_or_non_mirror_disagreements(tmp_path):
    report, rows = run_repair(
        tmp_path,
        [
            {
                "canonical_event_id": "correct",
                "location_raw": "TOULOUSE, Haute-Garonne, FRA, EU",
                "raw_fields": {"STATE": "FRA", "REGION": "EU"},
                "lat": 43.604,
                "lon": 1.443,
                "coordinate_source": "raw_latlong",
            },
            {
                "canonical_event_id": "not-close",
                "location_raw": "TOULOUSE, Haute-Garonne, FRA, EU",
                "raw_fields": {"STATE": "FRA", "REGION": "EU"},
                "lat": 48.0,
                "lon": -4.0,
                "coordinate_source": "raw_latlong",
            },
        ],
    )

    assert report["repaired_event_count"] == 0
    assert rows[0]["lat"] == 43.604
    assert rows[0]["lon"] == 1.443
    assert rows[1]["lat"] == 48.0
    assert rows[1]["lon"] == -4.0


def test_repair_handles_on_sea_town_names_as_land_places(tmp_path):
    report, rows = run_repair(
        tmp_path,
        [
            {
                "canonical_event_id": "newbiggin",
                "location_raw": "NEWBIGGIN-ON-SEA, Northumberland, GBR, EU",
                "raw_fields": {"STATE": "GBR", "REGION": "EU"},
                "lat": 55.185,
                "lon": 1.515,
                "coordinate_source": "raw_latlong",
            },
        ],
    )

    assert report["repaired_event_count"] == 1
    assert rows[0]["lat"] == 55.18532
    assert rows[0]["lon"] == -1.51469
