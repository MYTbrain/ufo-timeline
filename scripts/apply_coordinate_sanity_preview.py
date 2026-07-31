"""Apply conservative coordinate sign fixes to a preview corpus sidecar.

This script corrects mapped source coordinates only when the event declares a
country/region and flipping longitude moves the point from outside that country
polygon to inside it. It writes a sidecar JSONL and an audit report; canonical
source artifacts are never overwritten.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("data/canonical_preview_mapping_enrichment_geonames_top5000_high_medium/deduped_events.jsonl")
DEFAULT_COUNTRIES = Path("static_bundle/data/world_countries.geojson")
DEFAULT_OUTPUT_DIR = Path("data/canonical_preview_mapping_enrichment_geonames_top5000_coordinate_sane")
DEFAULT_REPORT = Path("data/reports/coordinate_sanity_top5000_preview_apply_report.json")
EXACT_COORDINATE_SOURCES = {"source_coordinates", "raw_latlong", "location_coordinates"}

COUNTRY_ALIASES = {
    "GER": "Germany",
    "DE": "Germany",
    "DEU": "Germany",
    "GERMANY": "Germany",
    "ES": "Spain",
    "ESP": "Spain",
    "SPAIN": "Spain",
    "FR": "France",
    "FRA": "France",
    "FRANCE": "France",
    "GR": "Greece",
    "GRE": "Greece",
    "GREECE": "Greece",
    "GB": "United Kingdom",
    "GBR": "United Kingdom",
    "UK": "United Kingdom",
    "UNITED KINGDOM": "United Kingdom",
    "GREAT BRITAIN": "United Kingdom",
    "GREAT BRITAIN AND IRELAND": "United Kingdom",
    "ENGL": "United Kingdom",
    "ENG": "United Kingdom",
    "IE": "Ireland",
    "IRL": "Ireland",
    "IREL": "Ireland",
    "EIRE": "Ireland",
    "IRELAND": "Ireland",
    "ITA": "Italy",
    "ITALY": "Italy",
    "JAPAN": "Japan",
    "JPN": "Japan",
    "AU": "Australia",
    "AUS": "Australia",
    "AUSTRALIA": "Australia",
    "AUT": "Austria",
    "AUSTRIA": "Austria",
    "ALB": "Albania",
    "ALBANIA": "Albania",
    "BE": "Belgium",
    "BEL": "Belgium",
    "BELGIUM": "Belgium",
    "BS": "Bahamas",
    "BHS": "Bahamas",
    "BAHAMAS": "Bahamas",
    "BALTIC SEA": "Baltic Sea",
    "BLR": "Belarus",
    "BELARUS": "Belarus",
    "BOS": "Bosnia and Herzegovina",
    "BOSNIA": "Bosnia and Herzegovina",
    "BOSNIA AND HERZEGOVINA": "Bosnia and Herzegovina",
    "BUL": "Bulgaria",
    "BULGARIA": "Bulgaria",
    "CAN": "Canada",
    "CANADA": "Canada",
    "CHINA": "China",
    "CHN": "China",
    "CUB": "Cuba",
    "CUBA": "Cuba",
    "CRO": "Croatia",
    "CROATIA": "Croatia",
    "CYP": "Cyprus",
    "CYPRUS": "Cyprus",
    "ARG": "Argentina",
    "ARGENTINA": "Argentina",
    "BER": "Bermuda",
    "BERMUDA": "Bermuda",
    "BOL": "Bolivia",
    "BOLIVIA": "Bolivia",
    "BRA": "Brazil",
    "BRAZIL": "Brazil",
    "CHL": "Chile",
    "CHI": "Chile",
    "CHILE": "Chile",
    "COL": "Colombia",
    "COLOMBIA": "Colombia",
    "CZ": "Czech Republic",
    "CZE": "Czech Republic",
    "CZECH REPUBLIC": "Czech Republic",
    "ECU": "Ecuador",
    "ECUADOR": "Ecuador",
    "EGY": "Egypt",
    "EGYPT": "Egypt",
    "DEN": "Denmark",
    "DENMARK": "Denmark",
    "DK": "Denmark",
    "DOM": "Dominican Republic",
    "DOMINICAN REPUBLIC": "Dominican Republic",
    "EST": "Estonia",
    "ESTONIA": "Estonia",
    "FIN": "Finland",
    "FINLAND": "Finland",
    "GEO": "Georgia",
    "GEORGIA": "Georgia",
    "HON": "Honduras",
    "HONDURAS": "Honduras",
    "HUN": "Hungary",
    "HUNGARY": "Hungary",
    "MEX": "Mexico",
    "MEXICO": "Mexico",
    "NED": "Netherlands",
    "NETH": "Netherlands",
    "NETHL": "Netherlands",
    "NTHL": "Netherlands",
    "HOLLAND": "Netherlands",
    "NETHERLANDS": "Netherlands",
    "MX": "Mexico",
    "KAZ": "Kazakhstan",
    "KAZAKHSTAN": "Kazakhstan",
    "KOS": "Kosovo",
    "KOSOVO": "Kosovo",
    "LAT": "Latvia",
    "LATVIA": "Latvia",
    "LIT": "Lithuania",
    "LITHUANIA": "Lithuania",
    "MAC": "North Macedonia",
    "MACEDONIA": "North Macedonia",
    "MOL": "Moldova",
    "MOLDOVA": "Moldova",
    "MON": "Montenegro",
    "MONTENEGRO": "Montenegro",
    "NZ": "New Zealand",
    "NZL": "New Zealand",
    "NEW ZEALAND": "New Zealand",
    "NOR": "Norway",
    "NORWAY": "Norway",
    "PNG": "Papua New Guinea",
    "PAPUA NEW GUINEA": "Papua New Guinea",
    "PER": "Peru",
    "PERU": "Peru",
    "POL": "Poland",
    "POLAND": "Poland",
    "POR": "Portugal",
    "PORTUGAL": "Portugal",
    "PT": "Portugal",
    "PR": "Puerto Rico",
    "PRI": "Puerto Rico",
    "PUERTO RICO": "Puerto Rico",
    "PAR": "Paraguay",
    "PARAGUAY": "Paraguay",
    "SAF": "South Africa",
    "SOUTH AFRICA": "South Africa",
    "SOL": "Solomon Islands",
    "SOLOMON ISLANDS": "Solomon Islands",
    "ROM": "Romania",
    "ROMANIA": "Romania",
    "ISR": "Israel",
    "ISRAEL": "Israel",
    "MOR": "Morocco",
    "MOROCCO": "Morocco",
    "REUNION": "Reunion",
    "RUS": "Russia",
    "RUSSIA": "Russia",
    "SAUDI ARABIA": "Saudi Arabia",
    "SER": "Serbia",
    "SERBIA": "Serbia",
    "SLK": "Slovakia",
    "SLOVAKIA": "Slovakia",
    "SLO": "Slovenia",
    "SLOVENIA": "Slovenia",
    "SUI": "Switzerland",
    "SWE": "Sweden",
    "SWEDEN": "Sweden",
    "SWITZERLAND": "Switzerland",
    "TUN": "Tunisia",
    "TUNISIA": "Tunisia",
    "UKR": "Ukraine",
    "UKRAINE": "Ukraine",
    "YUG": "Former Yugoslavia",
    "YUGOSLAVIA": "Former Yugoslavia",
    "US": "United States of America",
    "USA": "United States of America",
    "UNITED STATES": "United States of America",
    "URU": "Uruguay",
    "URUGUAY": "Uruguay",
    "VEN": "Venezuela",
    "VENEZUELA": "Venezuela",
    "VIE": "Vietnam",
    "VIETNAM": "Vietnam",
    "ZM": "Zambia",
    "ZAM": "Zambia",
    "ZAMBIA": "Zambia",
    "NORTH RHODESIA": "Zambia",
    "ZIM": "Zimbabwe",
    "ZIMBABWE": "Zimbabwe",
    "ISV": "United States Virgin Islands",
    "UVI": "United States Virgin Islands",
}
REGION_COUNTRY_ALIASES = {
    "EU": None,
    "EUR": None,
    "US": "United States of America",
    "USA": "United States of America",
    "CAN": "Canada",
    "MX": "Mexico",
    "MEX": "Mexico",
}
STATE_COUNTRY_ALIASES = {
    key: value
    for key, value in COUNTRY_ALIASES.items()
    if key
    not in {
        "AU",
        "CA",
        "DE",
        "FR",
        "GB",
        "UK",
    }
}
BOUNDED_FLIP_LON_RANGES = {
    "Argentina": [{"lat": (-56.0, -21.0), "lon": (-74.0, -53.0)}],
    "Austria": [{"lat": (46.0, 50.0), "lon": (9.0, 18.0)}],
    "Albania": [{"lat": (39.0, 43.0), "lon": (19.0, 22.0)}],
    "Bahamas": [{"lat": (20.0, 28.5), "lon": (-81.0, -72.0)}],
    "Belgium": [{"lat": (49.0, 52.0), "lon": (2.0, 7.0)}],
    "Baltic Sea": [{"lat": (53.0, 66.0), "lon": (9.0, 31.0)}],
    "Belarus": [{"lat": (51.0, 57.0), "lon": (23.0, 33.0)}],
    "Bermuda": [{"lat": (31.8, 32.8), "lon": (-65.1, -64.0)}],
    "Bolivia": [{"lat": (-23.5, -9.0), "lon": (-70.0, -57.0)}],
    "Bosnia and Herzegovina": [{"lat": (42.0, 46.0), "lon": (15.0, 20.0)}],
    "Brazil": [{"lat": (-34.5, 6.0), "lon": (-74.5, -34.0)}],
    "Bulgaria": [{"lat": (41.0, 45.0), "lon": (22.0, 29.0)}],
    "Canada": [{"lat": (41.0, 84.0), "lon": (-142.0, -52.0)}],
    "Chile": [{"lat": (-56.0, -17.0), "lon": (-76.0, -66.0)}],
    "China": [{"lat": (18.0, 54.0), "lon": (73.0, 136.0)}],
    "Colombia": [{"lat": (-5.0, 13.0), "lon": (-82.0, -66.0)}],
    "Croatia": [{"lat": (42.0, 47.0), "lon": (13.0, 20.0)}],
    "Cuba": [{"lat": (19.0, 24.0), "lon": (-86.0, -73.0)}],
    "Cyprus": [{"lat": (34.0, 36.0), "lon": (32.0, 35.0)}],
    "Czech Republic": [{"lat": (48.0, 52.0), "lon": (12.0, 19.0)}],
    "Denmark": [{"lat": (54.0, 58.0), "lon": (8.0, 13.0)}],
    "Dominican Republic": [{"lat": (17.0, 21.0), "lon": (-73.0, -68.0)}],
    "Estonia": [{"lat": (57.0, 60.5), "lon": (21.0, 29.0)}],
    "Finland": [{"lat": (59.0, 71.0), "lon": (20.0, 32.0)}],
    "Former Yugoslavia": [{"lat": (41.0, 47.0), "lon": (13.0, 23.0)}],
    "France": [{"lat": (41.0, 52.0), "lon": (-6.0, 10.0)}],
    "Georgia": [{"lat": (41.0, 44.0), "lon": (39.0, 47.0)}],
    "Germany": [{"lat": (47.0, 56.0), "lon": (5.0, 16.0)}],
    "Greece": [{"lat": (34.0, 42.0), "lon": (19.0, 29.0)}],
    "Honduras": [{"lat": (12.5, 16.8), "lon": (-90.0, -83.0)}],
    "Hungary": [{"lat": (45.0, 49.0), "lon": (16.0, 23.0)}],
    "Ireland": [{"lat": (51.0, 56.0), "lon": (-11.0, -5.0)}],
    "Italy": [{"lat": (36.0, 48.0), "lon": (6.0, 19.0)}],
    "Israel": [{"lat": (29.0, 34.0), "lon": (34.0, 36.5)}],
    "Japan": [{"lat": (24.0, 46.0), "lon": (122.0, 146.0)}],
    "Kazakhstan": [{"lat": (40.0, 56.0), "lon": (46.0, 88.0)}],
    "Kosovo": [{"lat": (41.5, 43.5), "lon": (20.0, 22.5)}],
    "Latvia": [{"lat": (55.0, 59.0), "lon": (20.0, 29.0)}],
    "Lithuania": [{"lat": (53.0, 57.0), "lon": (20.0, 28.0)}],
    "Mexico": [{"lat": (14.0, 33.0), "lon": (-119.0, -86.0)}],
    "Moldova": [{"lat": (45.0, 49.0), "lon": (26.0, 31.0)}],
    "Montenegro": [{"lat": (41.5, 43.8), "lon": (18.0, 21.0)}],
    "Morocco": [{"lat": (21.0, 36.5), "lon": (-18.0, -1.0)}],
    "New Zealand": [{"lat": (-48.0, -33.0), "lon": (165.0, 180.0)}, {"lat": (-48.0, -33.0), "lon": (-180.0, -170.0)}],
    "North Macedonia": [{"lat": (40.5, 42.5), "lon": (20.0, 23.5)}],
    "Norway": [{"lat": (57.0, 81.0), "lon": (4.0, 32.0)}],
    "Papua New Guinea": [{"lat": (-12.0, 0.0), "lon": (140.0, 158.0)}],
    "Peru": [{"lat": (-19.0, 1.0), "lon": (-82.5, -68.0)}],
    "Poland": [{"lat": (48.0, 56.0), "lon": (13.0, 25.0)}],
    "Portugal": [{"lat": (36.0, 43.0), "lon": (-10.0, -6.0)}],
    "Puerto Rico": [{"lat": (17.5, 18.7), "lon": (-68.5, -65.0)}],
    "Romania": [{"lat": (43.0, 49.0), "lon": (20.0, 30.0)}],
    "Reunion": [{"lat": (-22.0, -20.5), "lon": (55.0, 56.0)}],
    "Russia": [{"lat": (41.0, 82.0), "lon": (19.0, 180.0)}, {"lat": (41.0, 82.0), "lon": (-180.0, -168.0)}],
    "Saudi Arabia": [{"lat": (16.0, 33.0), "lon": (34.0, 56.0)}],
    "Serbia": [{"lat": (42.0, 47.0), "lon": (18.0, 23.0)}],
    "Slovakia": [{"lat": (47.0, 50.5), "lon": (16.0, 23.0)}],
    "Slovenia": [{"lat": (45.0, 47.0), "lon": (13.0, 17.0)}],
    "Solomon Islands": [{"lat": (-13.0, -5.0), "lon": (155.0, 170.0)}],
    "South Africa": [{"lat": (-35.0, -22.0), "lon": (16.0, 33.5)}],
    "Spain": [{"lat": (35.0, 44.0), "lon": (-10.0, 4.0)}],
    "Sweden": [{"lat": (55.0, 70.0), "lon": (10.0, 25.0)}],
    "Switzerland": [{"lat": (45.0, 48.5), "lon": (5.0, 11.0)}],
    "Tunisia": [{"lat": (30.0, 38.5), "lon": (7.0, 13.0)}],
    "Ukraine": [{"lat": (44.0, 53.0), "lon": (22.0, 41.0)}],
    "United Kingdom": [{"lat": (49.0, 59.0), "lon": (-8.0, 2.0)}],
    "Uruguay": [{"lat": (-36.0, -30.0), "lon": (-59.0, -53.0)}],
    "United States of America": [
        {"lat": (24.0, 50.0), "lon": (-125.0, -66.0)},
        {"lat": (51.0, 72.0), "lon": (-180.0, -130.0)},
        {"lat": (18.0, 23.0), "lon": (-161.0, -154.0)},
        {"lat": (20.0, 31.0), "lon": (-86.0, -73.0)},
    ],
    "United States Virgin Islands": [{"lat": (17.4, 18.8), "lon": (-65.3, -64.2)}],
    "Venezuela": [{"lat": (0.0, 13.5), "lon": (-74.5, -59.0)}],
    "Zambia": [{"lat": (-19.0, -8.0), "lon": (21.0, 34.0)}],
    "Zimbabwe": [{"lat": (-23.0, -15.0), "lon": (25.0, 34.0)}],
}
ZAMBIA_STRONG_LOCATION_HINTS = {
    "NORTH RHODESIA",
    "ZAMBIA",
}
ZAMBIA_CITY_HINTS = {
    "CHINGOLA",
    "CHISAMBA",
    "KABWE",
    "KASAMA",
    "KITWE",
    "LUSAKA",
    "MANSA",
    "NDOLA",
}
ZIMBABWE_LOCATION_HINTS = {
    "BULAWAYO",
    "CHEGUTU",
    "CHIMANIMANI",
    "CHINHOYI",
    "CHIRUNDU",
    "INYANGANI",
    "MAZOWE",
    "MUTARE",
    "NYANGA",
    "RHODESIA",
    "SALISBURY",
    "SINOIA",
    "UMVUMA",
    "VUMBA",
}
ZAMBIA_CONTEXT_REGIONS = {"", "AF", "ZM", "ZAMBIA", "ZIMBABWE & ZAMBIA"}
ZAMBIA_CONTEXT_STATES = {"ZAM", "NRH"}
ZIMBABWE_CONTEXT_REGIONS = {"AF", "ZIMBABWE & ZAMBIA"}
ZIMBABWE_CONTEXT_STATES = {"BLW", "HRR", "MSH", "MUT", "RHD", "ZIM"}
FRANCE_EAST_OF_GREENWICH_ADMIN_HINTS = {
    "AISNE",
    "ALPES-DE-HAUTE",
    "ALPES-MARITI",
    "ARDECHE",
    "ARDENNES",
    "ARIEGE",
    "AUBE",
    "AUDE",
    "AVEYRON",
    "BAS-RHIN",
    "BOUCHES-RHON",
    "CANTAL",
    "CHER",
    "CORREZE",
    "COTE-D'OR",
    "COTE D'OR",
    "DOUBS",
    "DORDOGNE",
    "DROME",
    "ESSONE",
    "ESSONNE",
    "EURE",
    "EURE-LOIR",
    "GARD",
    "GERS",
    "HAUT-RHIN",
    "HAUTE-GARON",
    "HAUTE-GARONN",
    "HAUTE-GARRON",
    "HAUTE-LOIRE",
    "HAUTE-MARNE",
    "HAUTE-SAONE",
    "HAUTE-SAVOIE",
    "HAUTE-VIENNE",
    "HAUTES-ALPES",
    "HAUTES-PYREN",
    "HAUTS-SEINE",
    "HERAULT",
    "ILE-DE-FRANCE",
    "ILE-FRANCE",
    "INDRE",
    "INDRE LOIRE",
    "INDRE-LOIRE",
    "ISERE",
    "JURA",
    "LOIR-CHER",
    "LOIR-ET-CHER",
    "LOIRE",
    "LOIRET",
    "LOT",
    "LOT GARONNE",
    "LOT-GARONNE",
    "MARNE",
    "MAYENNE",
    "MEURTHE",
    "MEUSE",
    "MOSELLE",
    "NIEVRE",
    "NORD",
    "OISE",
    "ORLY",
    "PARIS",
    "PAS-CALAIS",
    "PUY-DE-DOME",
    "PYRENEES-ORIENT",
    "RHONE",
    "SAONE-LOIRE",
    "SARTHE",
    "SAVOIE",
    "SEINE MARNE",
    "SEINE-MARITI",
    "SEINE-MARNE",
    "SEINEMARNE",
    "TARN",
    "TARN-GARONNE",
    "TERRITOIRE-DE-BELFORT",
    "VAL-DE-MARNE",
    "VAL-MARNE",
    "VAL-D'OISE",
    "VAR",
    "VAUCLUSE",
    "VIENNE",
    "VOSGES",
    "YONNE",
    "YVELINES",
}
FRANCE_WEST_OF_GREENWICH_ADMIN_HINTS = {
    "CALVADOS",
    "CHARENTE",
    "CHARENTE-MAR",
    "CHARENTE MAR",
    "COTES-NORD",
    "COTES NORD",
    "COTES-D'ARMOR",
    "COTES D'ARMOR",
    "FINISTERE",
    "GIRONDE",
    "ILLE-ET-VILAINE",
    "ILLE VILAINE",
    "LANDES",
    "LOIRE-ATLANT",
    "LOIRE-ATLANTIQUE",
    "LOIRE ATLANT",
    "LOIRE ATLANTIQUE",
    "MAINE-ET-LOIRE",
    "MAINE ET LOIRE",
    "MANCHE",
    "MORBIHAN",
    "PYA",
    "PYRENEES-ATL",
    "PYRENEES ATL",
    "VENDEE",
}
AUSTRALIAN_STATE_CODES = {"ACT", "NSW", "NT", "NTA", "QLD", "SA", "SAU", "TAS", "TSM", "VIC", "WAU"}
CANADIAN_PROVINCE_CODES = {"AB", "ALB", "BC", "LAB", "MAN", "MB", "NB", "NF", "NFL", "NL", "NS", "NT", "NU", "NUV", "NWT", "ON", "ONT", "PE", "PEI", "QC", "QUE", "SK", "SAS", "YK", "YT", "YUK"}
CENTRAL_AMERICA_REGION_COUNTRY_CODES = {"CUB", "DOM", "HON", "MEX", "MX", "PR", "PRI"}
SOUTH_AMERICA_REGION_COUNTRY_CODES = {"ARG", "BOL", "BRA", "CHI", "CHL", "COL", "ECU", "PAR", "PER", "URU", "VEN"}
LEGACY_US_REGION_CODES = {"US", "USA", "UA", "UE", "P", "AS"}
US_STATE_CODES = {
    "AK", "AL", "AR", "AZ", "CA", "CO", "CT", "DC", "DE", "FL", "GA", "HI", "IA", "ID", "IL",
    "IN", "KS", "KY", "LA", "MA", "MD", "ME", "MI", "MN", "MO", "MS", "MT", "NC", "ND", "NE",
    "NH", "NJ", "NM", "NV", "NY", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT",
    "VA", "VT", "WA", "WI", "WV", "WY",
}
US_STATE_NAMES = {
    "ALABAMA", "ALASKA", "ARIZONA", "ARKANSAS", "CALIFORNIA", "COLORADO", "CONNECTICUT", "DELAWARE",
    "DISTRICT OF COLUMBIA", "FLORIDA", "GEORGIA", "HAWAII", "IDAHO", "ILLINOIS", "INDIANA", "IOWA",
    "KANSAS", "KENTUCKY", "LOUISIANA", "MAINE", "MARYLAND", "MASSACHUSETTS", "MICHIGAN", "MINNESOTA",
    "MISSISSIPPI", "MISSOURI", "MONTANA", "NEBRASKA", "NEVADA", "NEW HAMPSHIRE", "NEW JERSEY",
    "NEW MEXICO", "NEW YORK", "NORTH CAROLINA", "NORTH DAKOTA", "OHIO", "OKLAHOMA", "OREGON",
    "PENNSYLVANIA", "RHODE ISLAND", "SOUTH CAROLINA", "SOUTH DAKOTA", "TENNESSEE", "TEXAS",
    "UTAH", "VERMONT", "VIRGINIA", "WASHINGTON", "WEST VIRGINIA", "WISCONSIN", "WYOMING",
}


def apply_coordinate_sanity_preview(
    *,
    input_path: Path,
    countries_geojson: Path,
    output_dir: Path,
    report_output: Path,
) -> dict[str, Any]:
    country_index = load_country_index(countries_geojson)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "deduped_events.jsonl"
    tmp_output_path = output_path.with_suffix(".jsonl.tmp")

    input_event_count = 0
    mapped_before_count = 0
    corrected_event_count = 0
    suspicious_event_count = 0
    corrected_by_country: dict[str, int] = {}
    suspicious_examples: list[dict[str, Any]] = []
    corrected_examples: list[dict[str, Any]] = []

    with input_path.open("r", encoding="utf-8") as source, tmp_output_path.open("w", encoding="utf-8", newline="\n") as output:
        for line in source:
            if not line.strip():
                continue
            event = json.loads(line)
            input_event_count += 1
            if has_usable_coordinates(event):
                mapped_before_count += 1
            country_name = inferred_country_name(event)
            corrected_event, action = maybe_correct_event(event, country_name, country_index)
            if action["kind"] == "corrected":
                corrected_event_count += 1
                corrected_by_country[country_name or "unknown"] = corrected_by_country.get(country_name or "unknown", 0) + 1
                if len(corrected_examples) < 50:
                    corrected_examples.append(action)
            elif action["kind"] == "suspicious":
                suspicious_event_count += 1
                if len(suspicious_examples) < 50:
                    suspicious_examples.append(action)
            output.write(json.dumps(corrected_event, ensure_ascii=False, separators=(",", ":")) + "\n")

    tmp_output_path.replace(output_path)
    report = {
        "schema_version": 1,
        "mode": "preview",
        "apply_policy": "coordinate_sanity_longitude_flip_if_country_polygon_matches",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": True,
        "inputs": {
            "deduped_events": str(input_path),
            "countries_geojson": str(countries_geojson),
        },
        "outputs": {
            "deduped_events": str(output_path),
            "report": str(report_output),
        },
        "input_event_count": input_event_count,
        "preview_event_count": input_event_count,
        "mapped_before_count": mapped_before_count,
        "mapped_after_count": mapped_before_count,
        "corrected_event_count": corrected_event_count,
        "suspicious_event_count": suspicious_event_count,
        "corrected_by_country": dict(sorted(corrected_by_country.items())),
        "corrected_examples": corrected_examples,
        "suspicious_examples": suspicious_examples,
        "notes": [
            "Only exact/source coordinate rows are considered.",
            "A longitude sign flip is applied only when current point is outside the declared country and flipped point is inside.",
            "Rows still outside the declared country after tested flips are reported but not automatically changed.",
        ],
    }
    write_json(report_output, report)
    return report


def maybe_correct_event(
    event: dict[str, Any],
    country_name: str | None,
    country_index: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    lat = parse_float(event.get("lat"))
    lon = parse_float(event.get("lon"))
    if lat is None or lon is None:
        return event, {"kind": "none"}
    if clean_text(event.get("coordinate_source")) not in EXACT_COORDINATE_SOURCES:
        return event, {"kind": "none"}
    if not country_name:
        return event, {"kind": "none"}
    feature = country_index.get(country_name)
    internal_admin_correction = maybe_correct_internal_admin_sign_error(event, country_name, feature, lat, lon)
    if internal_admin_correction is not None:
        next_event, correction = internal_admin_correction
        return next_event, action_payload("corrected", event, country_name, correction, lat, lon, next_event["lat"], next_event["lon"])
    nz_mainland_correction = maybe_correct_new_zealand_mainland_sign_error(event, country_name, feature, lat, lon)
    if nz_mainland_correction is not None:
        next_event, correction = nz_mainland_correction
        return next_event, action_payload("corrected", event, country_name, correction, lat, lon, next_event["lat"], next_event["lon"])
    if feature and point_in_feature(lat, lon, feature):
        return event, {"kind": "none"}
    if not feature and candidate_in_bounded_flip_lon_range(country_name, lat, lon):
        return event, {"kind": "none"}

    candidates = [
        ("flip_lon", lat, -lon),
        ("flip_lat", -lat, lon),
        ("flip_both", -lat, -lon),
    ]
    if feature:
        for correction, candidate_lat, candidate_lon in candidates:
            if point_in_feature(candidate_lat, candidate_lon, feature):
                next_event = dict(event)
                next_event["lat"] = candidate_lat
                next_event["lon"] = candidate_lon
                next_event["coordinate_sanity_action"] = correction
                next_event["coordinate_sanity_country"] = country_name
                next_event["coordinate_sanity_original_lat"] = lat
                next_event["coordinate_sanity_original_lon"] = lon
                existing_notes = clean_text(next_event.get("mapping_notes"))
                note = f"Coordinate sanity preview applied {correction} against declared country {country_name}."
                next_event["mapping_notes"] = f"{existing_notes} {note}".strip()
                return next_event, action_payload("corrected", event, country_name, correction, lat, lon, candidate_lat, candidate_lon)

    current_in_bounded_range = candidate_in_bounded_flip_lon_range(country_name, lat, lon)
    flipped_in_bounded_range = candidate_in_bounded_flip_lon_range(country_name, lat, -lon)
    if not current_in_bounded_range and flipped_in_bounded_range:
        next_event = dict(event)
        next_event["lat"] = lat
        next_event["lon"] = -lon
        next_event["coordinate_sanity_action"] = "flip_lon_bounded"
        next_event["coordinate_sanity_country"] = country_name
        next_event["coordinate_sanity_original_lat"] = lat
        next_event["coordinate_sanity_original_lon"] = lon
        existing_notes = clean_text(next_event.get("mapping_notes"))
        note = f"Coordinate sanity preview applied bounded flip_lon against declared country {country_name}."
        next_event["mapping_notes"] = f"{existing_notes} {note}".strip()
        return next_event, action_payload("corrected", event, country_name, "flip_lon_bounded", lat, lon, lat, -lon)

    return event, action_payload("suspicious", event, country_name, "outside_declared_country", lat, lon, None, None)


def maybe_correct_internal_admin_sign_error(
    event: dict[str, Any],
    country_name: str,
    feature: dict[str, Any] | None,
    lat: float,
    lon: float,
) -> tuple[dict[str, Any], str] | None:
    if country_name != "France" or feature is None:
        return None
    east_hint = france_location_has_east_of_greenwich_hint(event)
    west_hint = france_location_has_west_of_greenwich_hint(event)
    if lon < -0.2 and not east_hint:
        return None
    if lon > 0.2 and not west_hint:
        return None
    if -0.2 <= lon <= 0.2:
        return None
    flipped_lon = -lon
    if not point_in_feature(lat, flipped_lon, feature):
        return None
    next_event = dict(event)
    next_event["lat"] = lat
    next_event["lon"] = flipped_lon
    next_event["coordinate_sanity_action"] = "flip_lon_france_admin_hint"
    next_event["coordinate_sanity_country"] = country_name
    next_event["coordinate_sanity_original_lat"] = lat
    next_event["coordinate_sanity_original_lon"] = lon
    existing_notes = clean_text(next_event.get("mapping_notes"))
    note = "Coordinate sanity preview applied France admin-level longitude sign correction."
    next_event["mapping_notes"] = f"{existing_notes} {note}".strip()
    return next_event, "flip_lon_france_admin_hint"


def maybe_correct_new_zealand_mainland_sign_error(
    event: dict[str, Any],
    country_name: str,
    feature: dict[str, Any] | None,
    lat: float,
    lon: float,
) -> tuple[dict[str, Any], str] | None:
    if country_name != "New Zealand" or feature is None:
        return None
    if lon >= 0:
        return None
    if not (-48.5 <= lat <= -33.0 and 165.0 <= abs(lon) <= 179.9):
        return None
    if new_zealand_location_can_legitimately_use_west_longitude(event):
        return None
    flipped_lon = abs(lon)
    if not candidate_in_bounded_flip_lon_range(country_name, lat, flipped_lon):
        return None
    next_event = dict(event)
    next_event["lat"] = lat
    next_event["lon"] = flipped_lon
    next_event["coordinate_sanity_action"] = "flip_lon_new_zealand_mainland"
    next_event["coordinate_sanity_country"] = country_name
    next_event["coordinate_sanity_original_lat"] = lat
    next_event["coordinate_sanity_original_lon"] = lon
    existing_notes = clean_text(next_event.get("mapping_notes"))
    note = "Coordinate sanity preview flipped New Zealand mainland longitude sign."
    next_event["mapping_notes"] = f"{existing_notes} {note}".strip()
    return next_event, "flip_lon_new_zealand_mainland"


def new_zealand_location_can_legitimately_use_west_longitude(event: dict[str, Any]) -> bool:
    text = " ".join(
        clean_text(value).upper()
        for value in [
            event.get("location_raw"),
            event.get("location"),
            event.get("location_text"),
            (event.get("raw_fields") or {}).get("LOCATION"),
            (event.get("raw_fields") or {}).get("COUNTY"),
        ]
        if clean_text(value)
    )
    return any(
        token in text
        for token in (
            "CHATHAM",
            "KERMADEC",
            "RAOUL",
            "CAMPBELL ISLAND",
            "AUCKLAND ISLAND",
            "ANTIPODES",
            "BOUNTY ISLAND",
            "SNARES",
        )
    )


def france_location_has_east_of_greenwich_hint(event: dict[str, Any]) -> bool:
    location_text = france_lookup_text(event)
    if any(lookup_text_has_hint(location_text, hint) for hint in FRANCE_WEST_OF_GREENWICH_ADMIN_HINTS):
        return False
    return any(lookup_text_has_hint(location_text, hint) for hint in FRANCE_EAST_OF_GREENWICH_ADMIN_HINTS)


def france_location_has_west_of_greenwich_hint(event: dict[str, Any]) -> bool:
    location_text = france_lookup_text(event)
    if any(lookup_text_has_hint(location_text, hint) for hint in FRANCE_EAST_OF_GREENWICH_ADMIN_HINTS):
        return False
    return any(lookup_text_has_hint(location_text, hint) for hint in FRANCE_WEST_OF_GREENWICH_ADMIN_HINTS)


def france_lookup_text(event: dict[str, Any]) -> str:
    raw_fields = event.get("raw_fields") or {}
    return normalized_lookup_text(
        " ".join(
            clean_text(value)
            for value in [
                event.get("location_raw"),
                event.get("city"),
                event.get("state_province"),
                raw_fields.get("LOCATION"),
                raw_fields.get("CITY"),
                raw_fields.get("COUNTY"),
            ]
            if clean_text(value)
        )
    )


def lookup_text_has_hint(location_text: str, hint: str) -> bool:
    return re.search(rf"(?<![A-Z0-9]){re.escape(hint)}(?![A-Z0-9])", location_text) is not None


def action_payload(
    kind: str,
    event: dict[str, Any],
    country_name: str,
    correction: str,
    old_lat: float,
    old_lon: float,
    new_lat: float | None,
    new_lon: float | None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "canonical_event_id": event.get("canonical_event_id"),
        "source_name": event.get("source_name"),
        "source_row_number": event.get("source_row_number"),
        "source_native_id": event.get("source_native_id"),
        "location_raw": event.get("location_raw"),
        "country": country_name,
        "correction": correction,
        "old_lat": old_lat,
        "old_lon": old_lon,
        "new_lat": new_lat,
        "new_lon": new_lon,
    }


def inferred_country_name(event: dict[str, Any]) -> str | None:
    raw_fields = event.get("raw_fields") or {}
    state_values = [
        clean_text(raw_fields.get("STATE")).upper(),
        clean_text(event.get("state_province")).upper(),
    ]
    region_values = [
        clean_text(raw_fields.get("REGION")).upper(),
        clean_text(event.get("country")).upper(),
    ]
    raw_state = next((value for value in state_values if value), "")
    raw_region = next((value for value in region_values if value), "")
    if raw_region == "AU":
        if raw_state in {"NZ", "NZL"}:
            return "New Zealand"
        if raw_state == "PNG":
            return "Papua New Guinea"
        if raw_state in AUSTRALIAN_STATE_CODES:
            return "Australia"
    if raw_region in {"US", "USA", "UNITED STATES"} and raw_state in US_STATE_NAMES:
        return "United States of America"
    if raw_region in {"US", "USA", "UNITED STATES"} and raw_state in {"PR", "PRI", "PUERTO RICO"}:
        return "Puerto Rico"
    if raw_state in US_STATE_CODES and raw_region != "AU":
        return "United States of America"
    if raw_region == "CA":
        if raw_state in CENTRAL_AMERICA_REGION_COUNTRY_CODES:
            return STATE_COUNTRY_ALIASES.get(raw_state)
        if raw_state in CANADIAN_PROVINCE_CODES:
            return "Canada"
    if raw_region == "SA" and raw_state in SOUTH_AMERICA_REGION_COUNTRY_CODES:
        return STATE_COUNTRY_ALIASES.get(raw_state)
    if raw_region == "CN":
        return "Canada"
    if raw_region == "A" and raw_state in CANADIAN_PROVINCE_CODES:
        return "Canada"
    if raw_state in {"ISV", "UVI"}:
        return "United States Virgin Islands"
    location_text = " ".join(
        clean_text(value).upper()
        for value in [
            event.get("location_raw"),
            event.get("city"),
            raw_fields.get("LOCATION"),
            raw_fields.get("COUNTY"),
        ]
        if clean_text(value)
    )
    if "US VIRGIN ISLANDS" in location_text or "U.S. VIRGIN ISLANDS" in location_text:
        return "United States Virgin Islands"
    if "VIRGIN ISLANDS" in location_text and raw_region == "A":
        return "United States Virgin Islands"
    if raw_state in {"EIRE", "IREL", "IRELAND"}:
        return "Ireland"
    if raw_state in {"SOL"}:
        return "Solomon Islands"
    if raw_state in {"SAF", "SOUTH AFRICA"}:
        return "South Africa"
    if "TUNISIA" in location_text:
        return "Tunisia"
    if text_has_location_hint(location_text, "NORTH RHODESIA"):
        return "Zambia"
    if text_has_location_hint(location_text, "ZAMBIA") and raw_region != "ZIMBABWE & ZAMBIA":
        return "Zambia"
    if (
        (raw_region in ZAMBIA_CONTEXT_REGIONS or raw_state in ZAMBIA_CONTEXT_STATES)
        and any(text_has_location_hint(location_text, hint) for hint in ZAMBIA_CITY_HINTS)
    ):
        return "Zambia"
    if (
        (raw_region in ZIMBABWE_CONTEXT_REGIONS or raw_state in ZIMBABWE_CONTEXT_STATES)
        and any(text_has_location_hint(location_text, hint) for hint in ZIMBABWE_LOCATION_HINTS)
    ):
        return "Zimbabwe"
    if "ZIMBABWE" in location_text:
        return "Zimbabwe"
    for value in region_values:
        if value in REGION_COUNTRY_ALIASES:
            country = REGION_COUNTRY_ALIASES[value]
            if country is not None:
                return country
            continue
        if value in COUNTRY_ALIASES and value not in {"CA", "AU"}:
            return COUNTRY_ALIASES[value]
    for value in state_values:
        if value in STATE_COUNTRY_ALIASES:
            return STATE_COUNTRY_ALIASES[value]
    return None


def text_has_location_hint(text: str, hint: str) -> bool:
    pattern = rf"(?<![A-Z0-9]){re.escape(hint)}(?![A-Z0-9])"
    return re.search(pattern, text) is not None


def candidate_in_bounded_flip_lon_range(country_name: str, lat: float, lon: float) -> bool:
    ranges = BOUNDED_FLIP_LON_RANGES.get(country_name)
    if not ranges:
        return False
    return any(
        bounds["lat"][0] <= lat <= bounds["lat"][1] and bounds["lon"][0] <= lon <= bounds["lon"][1]
        for bounds in ranges
    )


def load_country_index(path: Path) -> dict[str, dict[str, Any]]:
    geojson = json.loads(path.read_text(encoding="utf-8"))
    index: dict[str, dict[str, Any]] = {}
    for feature in geojson.get("features", []):
        name = (feature.get("properties") or {}).get("name")
        if not name:
            continue
        geometry = feature.get("geometry") or {}
        bbox = geometry_bbox(geometry)
        index[name] = {"geometry": geometry, "bbox": bbox}
    return index


def point_in_feature(lat: float, lon: float, feature: dict[str, Any]) -> bool:
    bbox = feature.get("bbox")
    if bbox:
        min_lon, min_lat, max_lon, max_lat = bbox
        if lon < min_lon or lon > max_lon or lat < min_lat or lat > max_lat:
            return False
    return point_in_geometry(lat, lon, feature["geometry"])


def point_in_geometry(lat: float, lon: float, geometry: dict[str, Any]) -> bool:
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates") or []
    if geometry_type == "Polygon":
        return any(point_in_polygon(lat, lon, polygon) for polygon in [coordinates])
    if geometry_type == "MultiPolygon":
        return any(point_in_polygon(lat, lon, polygon) for polygon in coordinates)
    return False


def point_in_polygon(lat: float, lon: float, polygon: list[Any]) -> bool:
    if not polygon:
        return False
    outer = polygon[0]
    if not point_in_ring(lat, lon, outer):
        return False
    holes = polygon[1:]
    return not any(point_in_ring(lat, lon, hole) for hole in holes)


def point_in_ring(lat: float, lon: float, ring: list[list[float]]) -> bool:
    inside = False
    j = len(ring) - 1
    for i, point in enumerate(ring):
        xi, yi = point[0], point[1]
        xj, yj = ring[j][0], ring[j][1]
        intersects = ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def geometry_bbox(geometry: dict[str, Any]) -> tuple[float, float, float, float] | None:
    points: list[tuple[float, float]] = []
    collect_points(geometry.get("coordinates") or [], points)
    if not points:
        return None
    lons = [point[0] for point in points]
    lats = [point[1] for point in points]
    return min(lons), min(lats), max(lons), max(lats)


def collect_points(value: Any, points: list[tuple[float, float]]) -> None:
    if isinstance(value, list) and len(value) >= 2 and all(isinstance(item, (int, float)) for item in value[:2]):
        points.append((float(value[0]), float(value[1])))
        return
    if isinstance(value, list):
        for item in value:
            collect_points(item, points)


def has_usable_coordinates(event: dict[str, Any]) -> bool:
    lat = parse_float(event.get("lat"))
    lon = parse_float(event.get("lon"))
    return lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalized_lookup_text(value: Any) -> str:
    decomposed = unicodedata.normalize("NFKD", clean_text(value))
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", ascii_text.upper()).strip()


def parse_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result else None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--countries-geojson", type=Path, default=DEFAULT_COUNTRIES)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = apply_coordinate_sanity_preview(
        input_path=args.input,
        countries_geojson=args.countries_geojson,
        output_dir=args.output_dir,
        report_output=args.report_output,
    )
    print(json.dumps({
        "output": report["outputs"]["deduped_events"],
        "report": report["outputs"]["report"],
        "corrected_event_count": report["corrected_event_count"],
        "suspicious_event_count": report["suspicious_event_count"],
        "canonical_outputs_mutated": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
