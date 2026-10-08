"""Precompute source-backed UTC intervals without modifying catalog records.

Reads the shared reviewed clock dictionary, its inherited event projection and
effective summary shards. Exact clocks retain their source resolution. Missing,
sentinel, approximate and unsupported clocks may supply only their entire stated
calendar day, never an invented clock. Partial/uncertain dates remain excluded.
Jurisdiction uncertainty retains all supported offsets instead of choosing a
zone. Longitude is a contradiction guard, never a timezone model.
The small sparse sidecar joins records by their preserved event IDs.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import gzip
import hashlib
import importlib.resources
import json
from pathlib import Path
import re
import struct
import sys
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SHARED = Path(r"C:/Users/jarod/Desktop/UFO Timeline map tool")
ROOT = Path(__file__).resolve().parents[1]
REPAIRS = SHARED / "data/research/analysis-repairs-20261007"
DEFAULT_OUTPUT = SHARED / "data/research/trace-chronology-20261008"
RELEASE = "trace-chronology-20261008"
EXPECTED_ROWS = 702893
MAX_SAFE_ID = 9007199254740991
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

# This deliberately narrower subset does not include split-zone states or
# Arizona/Nevada, whose exceptions require a locality/zone boundary lookup.
US_ZONE_STATES = {
    "AL": ("ALABAMA", "America/Chicago"),
    "AR": ("ARKANSAS", "America/Chicago"),
    "CA": ("CALIFORNIA", "America/Los_Angeles"),
    "CO": ("COLORADO", "America/Denver"),
    "CT": ("CONNECTICUT", "America/New_York"),
    "DE": ("DELAWARE", "America/New_York"),
    "DC": ("DISTRICT OF COLUMBIA", "America/New_York"),
    "GA": ("GEORGIA", "America/New_York"),
    "HI": ("HAWAII", "Pacific/Honolulu"),
    "IL": ("ILLINOIS", "America/Chicago"),
    "IA": ("IOWA", "America/Chicago"),
    "LA": ("LOUISIANA", "America/Chicago"),
    "ME": ("MAINE", "America/New_York"),
    "MD": ("MARYLAND", "America/New_York"),
    "MA": ("MASSACHUSETTS", "America/New_York"),
    "MN": ("MINNESOTA", "America/Chicago"),
    "MS": ("MISSISSIPPI", "America/Chicago"),
    "MO": ("MISSOURI", "America/Chicago"),
    "MT": ("MONTANA", "America/Denver"),
    "NH": ("NEW HAMPSHIRE", "America/New_York"),
    "NJ": ("NEW JERSEY", "America/New_York"),
    "NM": ("NEW MEXICO", "America/Denver"),
    "NY": ("NEW YORK", "America/New_York"),
    "NC": ("NORTH CAROLINA", "America/New_York"),
    "OH": ("OHIO", "America/New_York"),
    "OK": ("OKLAHOMA", "America/Chicago"),
    "PA": ("PENNSYLVANIA", "America/New_York"),
    "RI": ("RHODE ISLAND", "America/New_York"),
    "SC": ("SOUTH CAROLINA", "America/New_York"),
    "UT": ("UTAH", "America/Denver"),
    "VT": ("VERMONT", "America/New_York"),
    "VA": ("VIRGINIA", "America/New_York"),
    "WA": ("WASHINGTON", "America/Los_Angeles"),
    "WV": ("WEST VIRGINIA", "America/New_York"),
    "WI": ("WISCONSIN", "America/Chicago"),
    "WY": ("WYOMING", "America/Denver"),
}
STATE_ALIASES = {alias: (code, zone) for code, (name, zone) in US_ZONE_STATES.items()
                 for alias in (code, name)}
EXPLICIT_OFFSETS = {
    "UTC": 0, "GMT": 0, "Z": 0,
    "EST": -300, "EDT": -240, "CST": -360, "CDT": -300,
    "MST": -420, "MDT": -360, "PST": -480, "PDT": -420,
    "AKST": -540, "AKDT": -480, "HST": -600,
}
ZONE_SUFFIX = re.compile(r"\s+(UTC|GMT|Z|[ECPMA][SD]T|AK[SD]T|HST|[+-]\d{2}:?\d{2})$", re.I)
LOCAL_SUFFIX = re.compile(r"\s+(?:local(?:\s+time)?|lt)$", re.I)
CLOCK = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2})(?:\.(\d+))?)?\s*([AP])\.?M\.?$", re.I)
CLOCK24 = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2})(?:\.(\d+))?)?$")
HHMM = re.compile(r"^(\d{2})(\d{2})$")
CONTINENTS = {"AF", "AS", "EU", "NA", "SA", "OC", "AN"}
US_BOUNDS = {}
COUNTRY_BOUNDS = {}
COUNTRY_ZONES = {}
CANADIAN_PROVINCE_ALIASES = {
    "AB", "ALB", "ALBERTA", "BC", "BRITISH COLUMBIA", "LAB", "LABRADOR",
    "MAN", "MB", "MANITOBA", "NB", "NEW BRUNSWICK", "NF", "NFL", "NL",
    "NEWFOUNDLAND", "NEWFOUNDLAND AND LABRADOR", "NS", "NOVA SCOTIA", "NT",
    "NU", "NUV", "NUNAVUT", "NWT", "NORTHWEST TERRITORIES", "ON", "ONT",
    "ONTARIO", "PE", "PEI", "PRINCE EDWARD ISLAND", "QC", "QUE", "QUEBEC",
    "SK", "SAS", "SASKATCHEWAN", "YK", "YT", "YUK", "YUKON",
}
# UFOCAT REGION is a source grouping field, not uniformly ISO country codes.
# Explicit penultimate country codes may replace a grouping suffix only when
# already recognized by the pinned country dictionary and consistent with this
# narrow region allowlist. Legacy native aliases (MRT/ANT/GM etc.) are not guessed.
UFOCAT_REGIONAL_COUNTRIES = {
    "CA": {"MX", "GT", "BZ", "SV", "HN", "NI", "CR", "PA", "CU", "HT", "DO", "JM", "PR",
           "BS", "TC", "KY", "VI", "VG", "AG", "KN", "LC", "VC", "BB", "GD", "TT", "AW",
           "CW", "SX", "GP", "MQ", "DM", "MS"},
    "AU": {"NZ", "PG", "SB", "FJ", "WS", "TO", "TV", "KI", "NC", "VU", "NF", "PF",
           "GU", "MP", "PW", "FM", "MH", "AS", "CK", "NU", "TK"},
    "ME": {"TR", "IL", "IQ", "IR", "SY", "LB", "JO", "SA", "KW", "QA", "BH", "AE",
           "OM", "YE", "CY", "PS"},
}
EXTRA_US_STATE_NAMES = {
    "AK": "ALASKA", "AZ": "ARIZONA", "FL": "FLORIDA", "ID": "IDAHO",
    "IN": "INDIANA", "KS": "KANSAS", "KY": "KENTUCKY", "MI": "MICHIGAN",
    "NE": "NEBRASKA", "NV": "NEVADA", "ND": "NORTH DAKOTA", "OR": "OREGON",
    "SD": "SOUTH DAKOTA", "TN": "TENNESSEE", "TX": "TEXAS",
}
ALL_STATE_ALIASES = {alias: code for code, name in
                     {**{code: name for code, (name, _) in US_ZONE_STATES.items()},
                      **EXTRA_US_STATE_NAMES}.items() for alias in (code, name)}
DAY_MS = 86400000
# The four continental standard zones are UTC-8 through UTC-5. The envelope
# includes their one-hour civil/daylight advancements without choosing a
# municipal DST schedule, a modern boundary, or a representative city's clock.
# It is intentionally much wider than a guessed state-specific +/-1 hour.
CONTINENTAL_US_OFFSET_MINUTES = (-480, -240)
US_STANDARD_TIME_START = "1918-03-31"
US_STANDARD_TIME_REFERENCE = "https://www.govinfo.gov/content/pkg/USCODE-1997-title15/html/USCODE-1997-title15-chap6-subchapIX.htm"
US_STANDARD_TIME_ORIGINAL_REFERENCE = "https://www.govinfo.gov/content/pkg/GOVPUB-C13-8e3c5faddda4a150f64cc39be042728b/pdf/GOVPUB-C13-8e3c5faddda4a150f64cc39be042728b.pdf"
FRANCE_LEGAL_TIME_REFERENCE = "https://observatoiredeparis.psl.eu/l-heure-d-ete-fete-ses-40-ans.html"
FRANCE_1945_REFERENCE = "https://lettre-info-lte.obspm.fr/archives/232"
FRANCE_1911_REFERENCE = "https://lists.iana.org/hyperkitty/list/tz%40iana.org/message/QAB4HOEJP55OFOJQHTUBVW5AB4OOEQA6/"
UK_GMT_REFERENCE = "https://www.legislation.gov.uk/ukpga/Geo5/6-7/45/pdfs/ukpga_19160045_en.pdf"
UK_SUMMER_REFERENCE = "https://researchbriefings.files.parliament.uk/documents/SN03796/SN03796.pdf"


def load(path):
    path = Path(path)
    raw = path.read_bytes()
    if path.suffix == ".gz":
        raw = gzip.decompress(raw)
    return json.loads(raw)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(part)
    return digest.hexdigest()


def normalized(value):
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9]+", " ", str(value).upper())).strip()


def country_zone_rules():
    import tzdata
    tab = importlib.resources.files("tzdata").joinpath("zoneinfo/zone.tab")
    country_zones = defaultdict(set)
    for line in tab.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        country_zones[parts[0]].add(parts[2])
    aliases, country_names = {}, {}
    country_info = SHARED / "cache/map_overlays/countryInfo.txt"
    for line in country_info.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) >= 5:
            country_names[fields[0]] = fields[4]
            for token in (fields[0], fields[1], fields[4]):
                aliases[normalized(token)] = fields[0]
    aliases.update({"UK": "GB", "ENGLAND": "GB", "SCOTLAND": "GB", "WALES": "GB",
                    "GREAT BRITAIN": "GB", "UNITED STATES OF AMERICA": "US",
                    "ZIM": "ZW", "NED": "NL", "ITL": "IT", "GERM": "DE", "NETH": "NL"})
    COUNTRY_ZONES.clear()
    COUNTRY_ZONES.update({country: tuple(sorted(zones)) for country, zones in country_zones.items()})
    single = {country: next(iter(zones)) for country, zones in country_zones.items() if len(zones) == 1}
    state_reference = SHARED / "scripts/apply_jurisdiction_coordinate_repair_preview.py"
    for node in ast.parse(state_reference.read_text(encoding="utf-8" )).body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "US_STATE_BOUNDS" for target in node.targets):
            US_BOUNDS.update(ast.literal_eval(node.value))
    geometry_path = SHARED / "webapp/static_public/data/world_countries.geojson"
    geometry_by_name = {normalized(feature["properties"]["name"]): feature["geometry"]
                        for feature in load(geometry_path)["features"]}
    for country, name in country_names.items():
        geometry = geometry_by_name.get(normalized(name))
        if geometry is None:
            continue
        polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
        boxes = []
        for polygon in polygons:
            ring = polygon[0]
            boxes.append((min(p[1] for p in ring), max(p[1] for p in ring), min(p[0] for p in ring), max(p[0] for p in ring)))
        COUNTRY_BOUNDS[country] = boxes
    return aliases, single, {"tzdataVersion": tzdata.__version__,
                            "ianaVersion": getattr(tzdata, "IANA_VERSION", "unknown"),
                            "zoneTabSha256": hashlib.sha256(tab.read_bytes()).hexdigest(),
                            "reference": "https://www.iana.org/time-zones",
                             "historicalScopeReference": "https://data.iana.org/time-zones/tzdb/theory.html#scope",
                             "continentalUsOffsetEnvelopeReferences": [US_STANDARD_TIME_REFERENCE, US_STANDARD_TIME_ORIGINAL_REFERENCE],
                             "nationalHistoricalOffsetEnvelopeReferences": {
                                 "metropolitanFrance": [FRANCE_1911_REFERENCE, FRANCE_LEGAL_TIME_REFERENCE, FRANCE_1945_REFERENCE],
                                 "unitedKingdomHomeTerritory": [UK_GMT_REFERENCE, UK_SUMMER_REFERENCE]},
                            "countryInfo": str(country_info), "countryInfoSha256": sha(country_info),
                            "jurisdictionStateBounds": str(state_reference), "stateReferenceSha256": sha(state_reference),
                            "jurisdictionCountryGeometry": str(geometry_path), "countryGeometrySha256": sha(geometry_path),
                             "geographicGuard": "Existing padded state QA bounds and country component bounding boxes; contradiction holdout, not precise timezone polygons"}


def structured_location_parts(event, aliases):
    """Separate source-region suffixes from literal jurisdiction components.

    The UFOCAT-only exceptions correspond to preserved REGION/STATE fields:
    CN+Canadian province; CA+Central-American/Caribbean country; AU+another
    Oceanian country; ME+Middle-Eastern country. Ordinary Canada CA and China CN
    remain ISO country suffixes for other sources. A country/state coordinate
    guard still applies in the caller before any UTC interval is accepted.
    """
    parts = [normalized(part) for part in str(event.get("location_raw") or "").split(",") if normalized(part)]
    if len(parts) >= 3 and parts[-1] in CONTINENTS and parts[-2] in aliases:
        parts.pop()
    if str(event.get("source") or "").lower() != "ufocat" or len(parts) < 2:
        return parts
    region, state = parts[-1], parts[-2]
    fields = event.get("raw_fields") or event.get("raw_source_row") or {}
    if isinstance(fields, dict):
        declared_region, declared_state = normalized(fields.get("REGION") or ""), normalized(fields.get("STATE") or "")
        if (declared_region and declared_region != region) or (declared_state and declared_state != state):
            return parts
    if region == "CN" and state in CANADIAN_PROVINCE_ALIASES:
        return parts[:-1] + ["CAN"]
    allowed = UFOCAT_REGIONAL_COUNTRIES.get(region)
    # Two-letter MX and PR have unambiguous roles in the source CA group; other
    # short country/state collisions require a country ISO3 or written name.
    if allowed and len(parts) >= 3 and (len(state) >= 3 or region == "CA" and state in {"MX", "PR"}) and aliases.get(state) in allowed:
        return parts[:-1]
    return parts


def strict_zone(event, aliases, single_zones):
    """Resolve a structured jurisdiction; never scan incidental place words."""
    precision = event.get("location_precision")
    if precision not in {"city", "exact_coords", "address", "county"}:
        return None, "low_location_precision"
    if not event.get("has_coordinates"):
        return None, "unmapped"
    parts = structured_location_parts(event, aliases)
    if len(parts) < 2:
        return None, "unstructured_location"
    lat, lon = event.get("lat"), event.get("lon")
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return None, "invalid_coordinates"
    continental_us = 24 <= lat <= 50 and -126 <= lon <= -66
    hawaii = 18 <= lat <= 23 and -161 <= lon <= -154
    country = aliases.get(parts[-1])
    # Two-field domestic records use state abbreviations that collide with
    # ISO country codes. Geographic context disambiguates the field role,
    # including unsupported/split states: those must not fall through to a
    # foreign-country interpretation (PA/Panama, IN/India, etc.).
    us_state_suffix = parts[-1] in US_BOUNDS or parts[-1] in STATE_ALIASES
    domestic_suffix = len(parts) == 2 and us_state_suffix and (continental_us or hawaii)
    state_tokens = parts if domestic_suffix or country is None else parts[:-1]
    if domestic_suffix:
        country = "US"
    state = STATE_ALIASES.get(state_tokens[-1]) if state_tokens else None
    if country == "US" or (country is None and state and continental_us):
        if not state:
            return None, "split_or_missing_us_state"
        if state[0] == "HI":
            if not hawaii:
                return None, "jurisdiction_coordinate_mismatch"
        elif not continental_us:
            return None, "jurisdiction_coordinate_mismatch"
        south, north, west, east = US_BOUNDS[state[0]]
        if not (south <= lat <= north and west <= lon <= east):
            return None, "jurisdiction_coordinate_mismatch"
        return state[1], "structured_uniform_us_state"
    # CA means Canada in a country suffix; it never becomes California just
    # because an alias-scanning parser encountered those letters somewhere.
    if country in single_zones:
        boxes = COUNTRY_BOUNDS.get(country)
        if not boxes:
            return None, "missing_country_coordinate_guard"
        if not any(south - .5 <= lat <= north + .5 and west - .5 <= lon <= east + .5 for south, north, west, east in boxes):
            return None, "jurisdiction_coordinate_mismatch"
        return single_zones[country], "structured_single_iana_country"
    return None, "multi_zone_or_unknown_country"


def bounded_jurisdiction(event, aliases, single_zones):
    """Return supported zone candidates or a continental civil-offset envelope.

    A single named zone is not silently substituted for an uncertain historical
    locality. Country-wide candidates are restricted to tzdb's post-1970 scope.
    The precision, explicit jurisdiction and coordinate-contradiction gates are
    the same as strict_zone; ambiguous suffixes never fall through those gates.
    """
    zone, reason = strict_zone(event, aliases, single_zones)
    date_iso = str(event.get("sort_date_iso") or "")
    try:
        date = datetime.strptime(date_iso, "%Y-%m-%d")
    except ValueError:
        return None, "invalid_date_or_zone"
    if zone and historical_jurisdiction_supported(event, zone):
        return {"zones": (zone,), "zone": zone, "basis": reason,
                "reason": "historical_zone_interval"}, reason
    if reason in {"low_location_precision", "unmapped", "unstructured_location",
                  "invalid_coordinates", "jurisdiction_coordinate_mismatch",
                  "missing_country_coordinate_guard"}:
        return None, reason
    parts = structured_location_parts(event, aliases)
    lat, lon = event.get("lat"), event.get("lon")
    continental_us = 24 <= lat <= 50 and -126 <= lon <= -66
    hawaii = 18 <= lat <= 23 and -161 <= lon <= -154
    country = aliases.get(parts[-1])
    domestic_suffix = len(parts) == 2 and parts[-1] in ALL_STATE_ALIASES and (continental_us or hawaii)
    state_tokens = parts if domestic_suffix or country is None else parts[:-1]
    state = ALL_STATE_ALIASES.get(state_tokens[-1]) if state_tokens else None
    if domestic_suffix:
        country = "US"
    if country == "US" or (country is None and state and continental_us):
        if not state or state not in US_BOUNDS:
            return None, "split_or_missing_us_state"
        south, north, west, east = US_BOUNDS[state]
        if not (south <= lat <= north and west <= lon <= east):
            return None, "jurisdiction_coordinate_mismatch"
        if continental_us and state not in {"AK", "HI"} and date_iso >= US_STANDARD_TIME_START:
            reason = "continental_us_civil_offset_envelope"
            return {"offsetMinutes": CONTINENTAL_US_OFFSET_MINUTES, "zone": "UTC",
                    "basis": "structured US state " + state +
                    "; all continental civil offsets UTC-08:00 through UTC-04:00; municipal DST/boundary unresolved; " +
                    US_STANDARD_TIME_REFERENCE, "reason": reason}, reason
        # Alaska and Hawaii are not continental-US offset candidates.
        return None, "held_historical_locality_timezone_uncertainty" if date.year < 1970 else "unsupported_us_state_offset_envelope"
    if date.year < 1970 and country == "FR":
        if not (41.3 <= lat <= 51.2 and -5.2 <= lon <= 9.7):
            return None, "outside_supported_metropolitan_france"
        if date_iso >= "1946-01-01":
            # The national legal-time authority records the 1945 retained
            # central-European hour, with summer changes resumed only in 1976.
            # Start after the entire 1945 transition year. This is national
            # jurisdiction evidence, not an extrapolated Paris DST timetable.
            reason = "metropolitan_france_national_offset_envelope"
            return {"offsetMinutes": (60, 60), "zone": "UTC", "reason": reason,
                    "basis": "structured metropolitan France; national legal UTC+01:00 during 1946-1969; no seasonal clock assigned; " +
                             FRANCE_LEGAL_TIME_REFERENCE + "; " + FRANCE_1945_REFERENCE}, reason
        if date_iso >= "1911-03-12":
            # Retain Greenwich, summer and occupied-zone hours together. Do not
            # infer a locality's occupation line, transition day, or 1911
            # midnight broadcast convention from the Paris representative.
            reason = "metropolitan_france_historical_offset_envelope"
            return {"offsetMinutes": (0, 120), "zone": "UTC", "reason": reason,
                    "basis": "structured metropolitan France; all civil offsets UTC+00:00 through UTC+02:00 during 1911-1945; wartime/seasonal locality unresolved; " +
                             FRANCE_1911_REFERENCE + "; " + FRANCE_LEGAL_TIME_REFERENCE}, reason
        return None, "historical_france_national_time_uncertainty"
    if date.year < 1970 and country == "GB":
        if not (49.8 <= lat <= 61.1 and -8.3 <= lon <= 2.2):
            return None, "outside_supported_uk_home_territory"
        if date_iso >= "1916-10-02":
            reason = "uk_historical_civil_offset_envelope"
            return {"offsetMinutes": (0, 120), "zone": "UTC", "reason": reason,
                    "basis": "structured UK home territory; all civil offsets Greenwich through double summer UTC+02:00 after 1916 Irish-GMT unification; seasonal rule unresolved; " +
                             UK_GMT_REFERENCE + "; " + UK_SUMMER_REFERENCE}, reason
        return None, "historical_uk_national_time_uncertainty"
    if zone:
        return None, "historical_locality_timezone_uncertainty"
    if date.year < 1970:
        return None, "historical_country_offset_uncertainty"
    candidates = COUNTRY_ZONES.get(country)
    boxes = COUNTRY_BOUNDS.get(country)
    if not candidates or not boxes:
        return None, "multi_zone_or_unknown_country"
    if not any(south - .5 <= lat <= north + .5 and west - .5 <= lon <= east + .5
               for south, north, west, east in boxes):
        return None, "jurisdiction_coordinate_mismatch"
    reason = "country_iana_zone_candidate_envelope"
    return {"zones": candidates, "zone": "UTC",
            "basis": "structured country " + country + "; all post-1970 IANA zone candidates: " + ", ".join(candidates),
            "reason": reason}, reason


def source_clock(raw, lower_minute):
    text = str(raw).strip()
    explicit = ZONE_SUFFIX.search(text)
    token = explicit.group(1).upper() if explicit else ""
    if explicit:
        text = text[:explicit.start()].strip()
    text = LOCAL_SUFFIX.sub("", text).strip()
    match = CLOCK.fullmatch(text) or CLOCK24.fullmatch(text)
    if match:
        hour, minute = int(match[1]), int(match[2])
        second = int(match[3] or 0)
        fraction = match[4] or ""
        ampm = match[5].upper() if len(match.groups()) == 5 and match[5] else ""
        if ampm:
            if not 1 <= hour <= 12:
                return None
            hour = hour % 12 + (12 if ampm == "P" else 0)
        if hour > 23 or minute > 59 or second > 59 or hour * 60 + minute != lower_minute:
            return None
        fraction_ms = int((fraction + "000")[:3]) if fraction else 0
        quantum_ms = 10 ** max(0, 3 - len(fraction)) if fraction else (1000 if match[3] is not None else 60000)
        start_ms = (hour * 3600 + minute * 60 + second) * 1000 + fraction_ms
        return start_ms, start_ms + quantum_ms - 1, token
    match = HHMM.fullmatch(text)
    if match and int(match[1]) <= 23 and int(match[2]) <= 59:
        minute = int(match[1]) * 60 + int(match[2])
        if minute == lower_minute:
            return minute * 60000, minute * 60000 + 59999, token
    return None


def epoch_ms(value):
    return round((value - EPOCH).total_seconds() * 1000)


def valid_instants(wall, zone):
    candidates = set()
    for fold in (0, 1):
        utc = wall.replace(tzinfo=zone, fold=fold).astimezone(timezone.utc)
        if utc.astimezone(zone).replace(tzinfo=None) == wall:
            candidates.add(epoch_ms(utc))
    return sorted(candidates)


def utc_interval(date_iso, local_start_ms, local_end_ms, zone_name):
    try:
        date = datetime.strptime(date_iso, "%Y-%m-%d")
        zone = ZoneInfo(zone_name)
    except (ValueError, ZoneInfoNotFoundError):
        return None, "invalid_date_or_zone"
    starts = valid_instants(date + timedelta(milliseconds=local_start_ms), zone)
    ends = valid_instants(date + timedelta(milliseconds=local_end_ms), zone)
    if not starts or not ends:
        return None, "nonexistent_local_clock"
    result = min(starts), max(ends)
    return result, "historical_fold_interval" if len(starts) > 1 or len(ends) > 1 else "historical_zone_interval"


@lru_cache(maxsize=200000)
def calendar_day_utc_interval(date_iso, zone_name):
    """Whole reported civil day; a nonexistent midnight is not a missing day.

    Most dates have valid endpoints. Where a midnight transition removes one,
    preserve a conservative whole-day offset envelope from both folds of every
    quarter-hour wall sample. A fully skipped civil date remains excluded.
    These bounds express the date's uncertainty, not a recovered event clock.
    """
    interval, reason = utc_interval(date_iso, 0, DAY_MS - 1, zone_name)
    if interval is not None:
        return interval, reason
    if reason != "nonexistent_local_clock":
        return None, reason
    date = datetime.strptime(date_iso, "%Y-%m-%d")
    zone = ZoneInfo(zone_name)
    offsets = set()
    for local_ms in range(0, DAY_MS, 15 * 60000):
        wall = date + timedelta(milliseconds=local_ms)
        for instant in valid_instants(wall, zone):
            offsets.add(epoch_ms(wall.replace(tzinfo=timezone.utc)) - instant)
    if not offsets:
        return None, "nonexistent_local_calendar_day"
    anchor = epoch_ms(date.replace(tzinfo=timezone.utc))
    return (anchor - max(offsets), anchor + DAY_MS - 1 - min(offsets)), "calendar_day_transition_envelope"


def offset_utc_interval(date_iso, local_start_ms, local_end_ms, offset_minutes):
    try:
        date = datetime.strptime(date_iso, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None, "invalid_date_or_zone"
    lower, upper = min(offset_minutes), max(offset_minutes)
    anchor = epoch_ms(date)
    return (anchor + local_start_ms - upper * 60000,
            anchor + local_end_ms - lower * 60000), "offset_envelope_interval"


def jurisdiction_utc_interval(date_iso, local_start_ms, local_end_ms, jurisdiction, calendar_day=False):
    if not jurisdiction:
        return None, "unsupported_jurisdiction"
    if "offsetMinutes" in jurisdiction:
        interval, _ = offset_utc_interval(date_iso, local_start_ms, local_end_ms, jurisdiction["offsetMinutes"])
        return interval, jurisdiction["reason"]
    intervals, reasons = [], []
    for zone in jurisdiction["zones"]:
        interval, reason = (calendar_day_utc_interval(date_iso, zone) if calendar_day else
                            utc_interval(date_iso, local_start_ms, local_end_ms, zone))
        if interval is not None:
            intervals.append(interval)
            reasons.append(reason)
    if not intervals:
        return None, "nonexistent_local_calendar_day" if calendar_day else "nonexistent_local_clock"
    result = min(item[0] for item in intervals), max(item[1] for item in intervals)
    if len(jurisdiction["zones"]) > 1:
        return result, jurisdiction["reason"]
    return result, reasons[0]


def explicit_utc_interval(date_iso, local_start_ms, local_end_ms, token, location_zone):
    if token in {"UTC", "GMT", "Z"}:
        interval, reason = utc_interval(date_iso, local_start_ms, local_end_ms, "UTC")
        return (interval, "explicit_source_offset" if interval else reason), "UTC"
    if re.fullmatch(r"[+-]\d{2}:?\d{2}", token):
        hour, minute = int(token[1:3]), int(token[-2:])
        if hour > 14 or minute > 59 or (hour == 14 and minute):
            return ((None, "invalid_explicit_offset"), None)
        offset = (hour * 60 + minute) * (1 if token[0] == "+" else -1)
    else:
        # CST/IST and similar abbreviations are ambiguous globally. Require
        # the unambiguous structured US jurisdiction for American labels.
        if token not in EXPLICIT_OFFSETS or not location_zone or not location_zone.startswith(("America/", "Pacific/Honolulu")):
            return ((None, "ambiguous_explicit_timezone_label"), None)
        offset = EXPLICIT_OFFSETS[token]
        historical, historical_reason = utc_interval(date_iso, local_start_ms, local_end_ms, location_zone)
        if historical is None:
            return ((None, historical_reason), None)
    try:
        date = datetime.strptime(date_iso, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return ((None, "invalid_date_or_zone"), None)
    result = (epoch_ms(date + timedelta(milliseconds=local_start_ms, minutes=-offset)),
              epoch_ms(date + timedelta(milliseconds=local_end_ms, minutes=-offset)))
    if token in EXPLICIT_OFFSETS and not token in {"UTC", "GMT", "Z"}:
        if result[0] < historical[0] or result[1] > historical[1]:
            return ((None, "explicit_timezone_conflicts_with_jurisdiction"), None)
    # Runtime codes use IANA names. For an explicit offset without a known
    # historical jurisdiction UTC names the normalized frame; the evidence
    # code retains the fixed-offset source token/basis.
    return ((result, "explicit_source_offset"), location_zone or "UTC")


def historical_jurisdiction_supported(event, zone):
    """Pre-1970 municipal DST needs the IANA representative locality itself."""
    text = str(event.get("sort_date_iso") or "")
    try:
        year = int(text[:4])
    except ValueError:
        return False
    if year < 1900:
        return False
    if year >= 1970:
        return True
    city = normalized(str(event.get("location_raw") or "").split(",")[0])
    locality = normalized(zone.rsplit("/", 1)[-1])
    return city == locality


def validate_narrative_sources(rows, source_root=None):
    """Reopen only accepted source chunks, checking each unique chunk once.

    Groups are released after their records are verified, keeping RAM bounded
    by one existing chunk. No source or full-corpus copy is created.
    """
    source_root = Path(source_root or SHARED / "data/canonical_web/event_chunks").resolve()
    grouped = defaultdict(list)
    for row in rows:
        path = Path(row.get("sourceChunkPath") or "").resolve()
        if path.parent != source_root or path.stem != row.get("sourceChunk") or path.suffix != ".json":
            raise ValueError("Reviewed narrative source path/locator is outside the canonical detail root")
        grouped[path].append(row)
    pins = []
    for path, group in sorted(grouped.items(), key=lambda item: str(item[0])):
        raw = path.read_bytes()
        actual_hash = hashlib.sha256(raw).hexdigest()
        if any(row.get("sourceChunkSha256") != actual_hash or row.get("sourceChunkBytes") != len(raw) for row in group):
            raise ValueError("Reviewed narrative source chunk hash/size drift")
        events = json.loads(raw)
        if not isinstance(events, list):
            raise ValueError("Reviewed narrative source chunk is not an event array")
        for row in group:
            index = row.get("detailIndex")
            if type(index) is not int or not 0 <= index < len(events):
                raise ValueError("Reviewed narrative source detail locator is invalid")
            event = events[index]
            if event.get("event_id") != row["eventId"] or event.get("chunk_id") != row["sourceChunk"] or event.get("detail_index") != index:
                raise ValueError("Reviewed narrative source event identity/locator drift")
            if event.get("source") != row.get("source") or event.get("source_id") != row.get("sourceId"):
                raise ValueError("Reviewed narrative original source identity drift")
            if event.get("sort_date_iso") != row.get("date") or event.get("date_precision") != "exact_day":
                raise ValueError("Reviewed narrative original source date/precision drift")
            if str(event.get("time_raw") or "").strip() or str(row.get("rawTime") or "").strip():
                raise ValueError("Reviewed narrative does not satisfy source-clock-empty review scope")
            field = row["sourceField"]
            if field not in {"description", "summary"} or not isinstance(event.get(field), str):
                raise ValueError("Reviewed narrative original source field is unavailable")
            description = event[field]
            if hashlib.sha256(description.encode("utf-8")).hexdigest() != row.get("descriptionSha256"):
                raise ValueError("Reviewed narrative source description hash drift")
            if not isinstance(row.get("excerpt"), str) or not row["excerpt"] or not description.startswith(row["excerpt"]):
                raise ValueError("Reviewed narrative exact leading source excerpt drift")
        pins.append({"path": str(path), "bytes": len(raw), "sha256": actual_hash,
                     "role": "accepted_narrative_original_source_chunk", "reviewedRecordsVerified": len(group)})
    return pins


def build(output_dir, reviewed_path=None, recovered_path=None, release_id=RELEASE, ufocat_fields_path=None):
    aliases, single_zones, tz_metadata = country_zone_rules()
    pins = []

    def pin(path, role):
        path = Path(path)
        pins.append({"path": str(path), "bytes": path.stat().st_size, "sha256": sha(path), "role": role})

    pin(Path(__file__).resolve(), "reproducible_sparse_evidence_builder")

    time_dir = REPAIRS / "attributes/analysis_time_of_day_v1"
    manifest_path = time_dir / "manifest.json"
    clock_manifest = load(manifest_path)
    pin(manifest_path, "reviewed_time_dictionary_manifest")
    dictionary_path = time_dir / "time_of_day_value_dictionary_v1.json.gz"
    dictionary = load(dictionary_path)
    pin(dictionary_path, "reviewed_source_clock_dictionary")
    value_by_id, projected_value_counts = {}, Counter()
    for name in clock_manifest["artifactGroups"]["timeProjectionShards"]:
        artifact = clock_manifest["artifacts"][name]
        path = SHARED / "data/releases/quality-20261007/analysis_delta/analysis_time_of_day_v1" / Path(artifact["gzipFile"]).name
        pin(path, "shared_inherited_event_clock_projection")
        if sha(path) != artifact["gzipSha256"]:
            raise ValueError("Inherited projection hash mismatch: " + str(path))
        for _, event_id, value_code, _ in load(path):
            if event_id in value_by_id:
                raise ValueError("Duplicate projected clock ID")
            value_by_id[event_id] = value_code
            projected_value_counts[value_code] += 1
    full_clock_status_counts = Counter()
    for value_code, value in enumerate(dictionary):
        if projected_value_counts[value_code] != value[-1]:
            raise ValueError("Reviewed clock dictionary occurrence count drift")
        full_clock_status_counts[clock_manifest["codes"]["status"][value[3]]] += value[-1]
    reviewed = load(reviewed_path) if reviewed_path else {"rows": []}
    narrative_by_id = {}
    for row in reviewed.get("rows", []):
        if row.get("status") != "accepted":
            continue
        event_id = row.get("eventId")
        if not isinstance(event_id, int) or not 0 < event_id <= MAX_SAFE_ID or event_id in narrative_by_id:
            raise ValueError("Invalid or duplicated reviewed narrative event ID")
        lower, upper = row.get("localStartMs"), row.get("localEndMs")
        if not isinstance(lower, int) or not isinstance(upper, int) or not 0 <= lower <= upper < 86400000:
            raise ValueError("Reviewed narrative interval is outside its source calendar day")
        if not all(isinstance(row.get(key), str) and row[key].strip() for key in ("sourceField", "sourceChunk", "excerpt", "basis", "date", "zone")):
            raise ValueError("Reviewed narrative lacks a concrete provenance locator")
        narrative_by_id[event_id] = row
    if reviewed_path:
        pin(reviewed_path, "independently_reviewed_event_clock_evidence")
        pins.extend(validate_narrative_sources(narrative_by_id.values()))
    recovered_by_id = {}
    if recovered_path:
        import recover_occurrence_clock_evidence as recovery
        recovered = load(recovered_path)
        if recovered.get("schemaId") != "trace-occurrence-clock-recovery-v1" or not isinstance(recovered.get("rows"), list):
            raise ValueError("Unsupported recovered occurrence-clock evidence schema")
        pin(recovered_path, "source_pinned_corpus_occurrence_clock_recovery_ledger")
        pin(Path(recovery.__file__), "reproducible_own_occurrence_clock_recovery_rules")
        pins.extend(recovery.validate_recovered_sources(recovered["rows"], root=SHARED))
        for row in recovered["rows"]:
            if row.get("status") != "accepted_local_evidence_pending_geographic_UTC_gate":
                raise ValueError("Recovered clock has unsupported local-evidence status")
            lower, upper = row.get("localStartMs"), row.get("localEndMs")
            if type(lower) is not int or type(upper) is not int or not 0 <= lower <= upper < DAY_MS:
                raise ValueError("Recovered clock lies outside its own reported calendar day")
            recovered_by_id[row["eventId"]] = row
    source_fields_by_id = {}
    if ufocat_fields_path:
        import audit_ufocat_timezone_source_fields as source_field_audit
        import ufocat_source_timing as source_timing
        field_ledger = load(ufocat_fields_path)
        if field_ledger.get("schemaId") != "ufocat-source-time-date-fields-v1" or not isinstance(field_ledger.get("rows"), list):
            raise ValueError("Unsupported UFOCAT source date/time field ledger")
        pin(ufocat_fields_path, "hashed_original_ufocat_time_date_flags_ledger")
        pin(Path(source_field_audit.__file__), "reproducible_ufocat_source_field_join_and_verifier")
        pin(Path(source_timing.__file__), "documented_ufocat_timebase_and_occurrence_date_rules")
        pins.extend(source_field_audit.validate_source_fields(field_ledger["rows"], root=SHARED))
        source_fields_by_id = {row["eventId"]: row for row in field_ledger["rows"]}
    codes, code_by_basis, zones, zone_by_name = [], {}, [], {}
    excluded_dates = []
    rows, audit, by_source, sample = [], Counter(), defaultdict(Counter), []
    by_day_craft = defaultdict(list)
    accepted_intervals = {}
    trace_index = SHARED / "data/releases/quality-20261007/map_delta/trace_event_index.bin"
    trace_metadata = SHARED / "data/releases/quality-20261007/map_delta/trace_event_index_meta.json"
    pin(trace_index, "unchanged_existing_canonical_trace_playback_order")
    pin(trace_metadata, "canonical_trace_index_schema")
    metadata = load(trace_metadata)
    if metadata["struct_format"] != "<QddiiIIiI" or metadata["bytes_per_row"] != 48:
        raise ValueError("Unexpected canonical trace index schema")
    sequence_by_id = {}
    with trace_index.open("rb") as stream:
        for block in iter(lambda: stream.read(48 * 16384), b""):
            if len(block) % 48:
                raise ValueError("Truncated existing trace index")
            for values in struct.iter_unpack("<QddiiIIiI", block):
                sequence_by_id[values[0]] = values[-1]
    if len(sequence_by_id) != metadata["row_count"]:
        raise ValueError("Canonical trace index identity/count drift")
    summary_manifest_path = REPAIRS / "source-quality/catalog/summary_manifest.json"
    pin(summary_manifest_path, "effective_catalog_summary_manifest")
    total = 0

    def accept(event, interval, zone, kind, basis, reason, precision=None, source_field="time_raw"):
        code_key = kind, basis, reason, precision, source_field
        if code_key not in code_by_basis:
            code_by_basis[code_key] = len(codes)
            date_only = kind == "source_calendar_day_zone_bound"
            envelope = "envelope" in kind or "envelope" in reason
            jurisdiction_envelope = reason in {"continental_us_civil_offset_envelope", "country_iana_zone_candidate_envelope",
                                              "metropolitan_france_national_offset_envelope", "metropolitan_france_historical_offset_envelope",
                                              "uk_historical_civil_offset_envelope"}
            bounded_clock = precision in {"hour", "explicit_range", "explicit_ampm_half"}
            codes.append({"status": "accepted", "kind": kind,
                          "confidence": "bounded" if date_only or envelope or bounded_clock or reason == "historical_fold_interval" else "high",
                          "basis": basis, "conversion": reason,
                          "timePrecision": "whole_source_calendar_day" if date_only else precision or "source_clock_resolution",
                          "sourceField": source_field,
                          "clockEvidence": "clock_unresolved_or_withheld_entire_source_calendar_day" if date_only else "source_reported_event_occurrence_clock_resolution",
                          "timezoneEvidence": "explicit_ufocat_source_timebase" if reason == "documented_ufocat_timebase" else
                                              "explicit_source_offset" if reason == "explicit_source_offset" else
                                              "structured_jurisdiction_supported_offset_envelope_utc_frame" if jurisdiction_envelope else
                                              "structured_jurisdiction_inference_with_historical_iana_rules",
                          "interpretation": "reported_event_order_not_observed_craft_movement"})
        if zone not in zone_by_name:
            zone_by_name[zone] = len(zones)
            zones.append(zone)
        event_id = event["event_id"]
        if not isinstance(event_id, int) or not 0 < event_id <= MAX_SAFE_ID or event_id in accepted_intervals:
            raise ValueError("Invalid or repeated accepted event ID")
        rows.append([event_id, interval[0], interval[1], code_by_basis[code_key], zone_by_name[zone]])
        accepted_intervals[event_id] = interval
        audit["accepted_utc_interval"] += 1
        audit["accepted_kind_" + kind] += 1
        audit[reason] += 1
        by_source[event.get("source", "unknown")]["accepted_utc_interval"] += 1
        if len(sample) < 25 or event_id in {3972295816637808, 1880247488343365, 1548188833291382, 3448855352240391}:
            sample.append({"eventId": event_id, "source": event.get("source"), "rawTime": event.get("time_raw"),
                           "date": event.get("sort_date_iso"), "chunkId": event.get("chunk_id"),
                           "detailIndex": event.get("detail_index"), "location": event.get("location_raw"),
                           "zone": zone, "utcStartMs": interval[0], "utcEndMs": interval[1], "basis": basis})

    def accept_calendar_day(event, jurisdiction, clock_status, zone):
        # Preserve a declared source time frame even when its clock is withheld.
        # A jurisdiction/conflicting abbreviation must never be repaired into a
        # different calendar day merely by ignoring the source timezone token.
        token_match = ZONE_SUFFIX.search(str(event.get("time_raw") or "").strip())
        if token_match:
            token = token_match.group(1).upper()
            (interval, reason), frame = explicit_utc_interval(event.get("sort_date_iso"), 0, DAY_MS - 1, token, zone)
            if interval is None:
                audit["held_date_bound_" + reason] += 1
                return False
            basis = ("Entire stated source calendar day; source clock status " + clock_status +
                     "; no event clock inferred; explicit source timezone " + token)
        else:
            if not jurisdiction:
                return False
            interval, reason = jurisdiction_utc_interval(event.get("sort_date_iso"), 0, DAY_MS - 1,
                                                        jurisdiction, calendar_day=True)
            if interval is None:
                audit["held_date_bound_" + reason] += 1
                return False
            frame = jurisdiction["zone"]
            basis = ("Entire stated source calendar day; source clock status " + clock_status +
                     "; no event clock inferred; " + jurisdiction["basis"])
        accept(event, interval, frame, "source_calendar_day_zone_bound", basis, reason)
        return True

    for entry in load(summary_manifest_path):
        path = REPAIRS / "source-quality/catalog/summary_shards" / (entry["file"] + ".gz")
        if not path.exists():
            path = REPAIRS / "catalog/summary_shards" / (entry["file"] + ".gz")
        pin(path, "effective_preserved_catalog_summary_shard")
        for event in load(path):
            total += 1
            source = event.get("source", "unknown")
            by_source[source]["catalog_rows"] += 1
            event_id = event["event_id"]
            source_fields = source_fields_by_id.get(event_id)
            exclusion = None
            if source_fields:
                if (source != "ufocat" or source_fields.get("date") != (event.get("sort_date_iso") or event.get("date_iso")) or
                    source_fields.get("datePrecision") != event.get("date_precision") or
                    source_fields.get("rawTime") != str(event.get("time_raw") or "") or
                    source_fields.get("sourceChunk") != event.get("chunk_id") or
                    source_fields.get("detailIndex") != event.get("detail_index")):
                    raise ValueError("UFOCAT source-field/effective-row identity, date or time drift")
                exclusion = source_timing.date_exclusion(source_fields["fields"])
                if exclusion:
                    excluded_dates.append({"eventId": event_id, **exclusion})
                    audit["excluded_" + exclusion["reason"]] += 1
                    by_source[source]["excluded_occurrence_date"] += 1
            if event.get("date_precision") == "exact_day" and event.get("has_coordinates"):
                craft = event.get("craft_type_inferred")
                if event_id in sequence_by_id and craft not in {None, "unknown", "conventional_or_explained", "non_ufo_context"}:
                    by_day_craft[(event.get("sort_date_iso"), craft)].append(event_id)
            if exclusion:
                continue
            if event.get("date_precision") != "exact_day" or event.get("exact_day_eligible") is False:
                audit["held_partial_or_uncertain_date"] += 1
                continue
            zone, zone_reason = strict_zone(event, aliases, single_zones)
            jurisdiction, jurisdiction_reason = bounded_jurisdiction(event, aliases, single_zones)
            if source_fields:
                # These flags describe the stored date/time frame. Do not
                # reinterpret a GMT date as a local date, or substitute current
                # civil DST rules for a source explicitly coded as standard.
                value_code = value_by_id.get(event_id)
                status = clock_manifest["codes"]["status"][dictionary[value_code][3]] if value_code is not None else "empty_or_unclassified"
                if value_code is not None and dictionary[value_code][2] != event.get("time_raw"):
                    raise ValueError("Source clock projection/raw field mismatch")
                fields = source_fields["fields"]
                offset, timebase_basis = source_timing.timebase(fields)
                if offset is None:
                    audit["held_ufocat_" + timebase_basis] += 1
                    continue
                clock = source_clock(dictionary[value_code][2], dictionary[value_code][5]) if status == "exact_clock" else None
                if fields["TIME"].strip() != str(event.get("time_raw") or "").strip():
                    clock = None
                    status = "source_clock_field_mismatch"
                if clock and clock[2]:
                    (explicit, _), _ = explicit_utc_interval(event.get("sort_date_iso"), clock[0], clock[1], clock[2], zone)
                    fixed, _ = source_timing.utc_interval(event.get("sort_date_iso"), clock[0], clock[1], fields)
                    if explicit is None or explicit != fixed:
                        audit["held_ufocat_conflicting_explicit_timebases"] += 1
                        continue
                start, end = clock[:2] if clock else (0, DAY_MS - 1)
                interval, source_basis = source_timing.utc_interval(event.get("sort_date_iso"), start, end, fields)
                if interval is None:
                    audit["held_ufocat_" + source_basis] += 1
                    continue
                kind = "source_documented_timebase_clock" if clock else "source_calendar_day_zone_bound"
                basis = ("Source event clock time_raw; " if clock else
                         "Entire source calendar day; clock status " + status + "; no occurrence clock inferred; ") + source_basis + "; CUFOS UFOCAT 2023 codebook pp18–19; original fields retained in hashed source ledger"
                accept(event, interval, "UTC", kind, basis, "documented_ufocat_timebase")
                audit["documented_ufocat_timebase_accepted"] += 1
                continue
            narrative = narrative_by_id.get(event_id)
            if narrative:
                if narrative.get("date") != event.get("sort_date_iso"):
                    raise ValueError("Reviewed narrative date drift")
                if narrative.get("sourceChunk") != event.get("chunk_id") or narrative.get("detailIndex") != event.get("detail_index"):
                    raise ValueError("Reviewed narrative source locator drift")
                if narrative.get("explicitTimezoneToken"):
                    (interval, reason), resolved_zone = explicit_utc_interval(narrative["date"], narrative["localStartMs"], narrative["localEndMs"], narrative["explicitTimezoneToken"], narrative["zone"])
                else:
                    if not historical_jurisdiction_supported(event, narrative["zone"]):
                        if not jurisdiction:
                            raise ValueError("Reviewed narrative historical zone lacks supported locality or explicit offset")
                        interval, reason = jurisdiction_utc_interval(narrative["date"], narrative["localStartMs"], narrative["localEndMs"], jurisdiction)
                        resolved_zone = jurisdiction["zone"]
                    else:
                        interval, reason = utc_interval(narrative["date"], narrative["localStartMs"], narrative["localEndMs"], narrative["zone"])
                        resolved_zone = narrative["zone"]
                if interval is None:
                    raise ValueError("Reviewed narrative has invalid local interval")
                envelope = "envelope" in reason
                accept(event, interval, resolved_zone, "reviewed_event_clock_zone_envelope" if envelope else "reviewed_event_clock",
                       narrative["basis"] + ("; " + jurisdiction["basis"] if envelope else ""), reason)
                continue
            value_code = value_by_id.get(event_id)
            recovered = recovered_by_id.get(event_id)
            projected_status = clock_manifest["codes"]["status"][dictionary[value_code][3]] if value_code is not None else "empty_or_unclassified"
            if value_code is not None and dictionary[value_code][2] != event.get("time_raw"):
                raise ValueError("Source clock projection/raw field mismatch")
            if recovered and projected_status != "exact_clock":
                if recovered.get("sourceTimeStatus") != projected_status:
                    raise ValueError("Recovered clock typed source-status drift")
                if recovered.get("date") != event.get("sort_date_iso") or recovered.get("sourceTimeRaw") != str(event.get("time_raw") or ""):
                    raise ValueError("Recovered clock effective calendar date/raw time drift")
                if recovered.get("sourceChunk") != event.get("chunk_id") or recovered.get("detailIndex") != event.get("detail_index"):
                    raise ValueError("Recovered clock effective source locator drift")
                token = str(recovered.get("explicitTimezoneToken") or "").upper()
                local_only = token in {"LOCAL", "LOCAL TIME", "LT"}
                if token and not local_only:
                    (interval, reason), recovered_zone = explicit_utc_interval(recovered["date"], recovered["localStartMs"], recovered["localEndMs"], token, zone)
                    timezone_basis = "explicit own-source timezone " + token
                elif jurisdiction:
                    interval, reason = jurisdiction_utc_interval(recovered["date"], recovered["localStartMs"], recovered["localEndMs"], jurisdiction)
                    recovered_zone = jurisdiction["zone"]
                    timezone_basis = jurisdiction["basis"]
                else:
                    interval, reason, recovered_zone = None, jurisdiction_reason, None
                audit["recovered_local_clock_rows_checked"] += 1
                if interval is not None:
                    kind = "source_recovered_occurrence_clock" if recovered["sourceField"] != "time_raw" else "source_recovered_clock_field"
                    if "envelope" in reason:
                        kind += "_zone_envelope"
                    basis = ("Own source " + recovered["sourceField"] + "; rerun source-pinned rule " + recovered["ruleId"] +
                             "; stated " + recovered["precision"] + "; original clock status " + projected_status +
                             "; source excerpt retained in hashed recovery ledger; " + timezone_basis)
                    accept(event, interval, recovered_zone, kind, basis, reason,
                           precision=recovered["precision"], source_field=recovered["sourceField"])
                    audit["recovered_local_clock_utc_accepted"] += 1
                    audit["source_status_" + projected_status] += 1
                    continue
                audit["held_recovered_clock_" + reason] += 1
                if token and not local_only:
                    # Its source calendar day belongs to the rejected explicit
                    # time frame; a geographic day cannot replace that frame.
                    continue
            if value_code is None:
                audit["held_no_source_clock"] += 1
                if not accept_calendar_day(event, jurisdiction, "missing", zone):
                    audit["held_date_bound_" + jurisdiction_reason] += 1
                continue
            value = dictionary[value_code]
            status = clock_manifest["codes"]["status"][value[3]]
            audit["source_status_" + status] += 1
            if status != "exact_clock":
                audit["held_" + status] += 1
                if not accept_calendar_day(event, jurisdiction, status, zone):
                    audit["held_date_bound_" + jurisdiction_reason] += 1
                continue
            clock = source_clock(value[2], value[5])
            if not clock:
                audit["held_unsupported_exact_clock_syntax"] += 1
                accept_calendar_day(event, jurisdiction, "unsupported_exact_clock_syntax", zone)
                continue
            start, end, token = clock
            if token:
                (interval, reason), resolved_zone = explicit_utc_interval(event.get("sort_date_iso"), start, end, token, zone)
                zone = resolved_zone
                basis = "Explicit source event clock time_raw with explicit timezone " + token
            elif zone:
                if not historical_jurisdiction_supported(event, zone):
                    audit["held_historical_locality_timezone_uncertainty"] += 1
                    if not jurisdiction:
                        continue
                    interval, reason = jurisdiction_utc_interval(event.get("sort_date_iso"), start, end, jurisdiction)
                    zone = jurisdiction["zone"]
                    basis = "Explicit source event clock time_raw; " + jurisdiction["basis"]
                else:
                    interval, reason = utc_interval(event.get("sort_date_iso"), start, end, zone)
                    basis = "Explicit source event clock time_raw; " + zone_reason + "; historical IANA rules"
            elif jurisdiction:
                interval, reason = jurisdiction_utc_interval(event.get("sort_date_iso"), start, end, jurisdiction)
                zone = jurisdiction["zone"]
                basis = "Explicit source event clock time_raw; " + jurisdiction["basis"]
            else:
                audit["held_" + zone_reason] += 1
                continue
            if not interval:
                audit["held_" + reason] += 1
                continue
            accept(event, interval, zone, "source_clock_zone_envelope" if "envelope" in reason else "source_exact_clock", basis, reason)
    if total != EXPECTED_ROWS:
        raise ValueError(f"Catalog row drift {total}/{EXPECTED_ROWS}")
    pair_counts = Counter()
    for ids in by_day_craft.values():
        ids.sort(key=lambda event_id: sequence_by_id[event_id])
        # Existing packed playback order is the adjacency inventory. This
        # measures endpoint timing coverage of those exact links, not every
        # possible filtered user selection nor a physical flight sequence.
        for left, right in zip(ids, ids[1:]):
            pair_counts["same_day_craft_adjacent_links"] += 1
            a, b = accepted_intervals.get(left), accepted_intervals.get(right)
            if not a or not b:
                pair_counts["missing_endpoint_timing"] += 1
            elif a[1] < b[0] or b[1] < a[0]:
                pair_counts["utc_order_resolved_after"] += 1
            else:
                pair_counts["utc_intervals_overlap"] += 1
    rows.sort(key=lambda row: row[0])
    payload = {"schemaId": "trace-chronology-evidence-v1", "releaseId": release_id,
               "sourceContract": "source-backed-clock-and-historical-zone-v1",
               "rowSchema": ["eventId", "utcStartMs", "utcEndMs", "evidenceCode", "zoneCode"],
               "codes": {"evidence": codes, "zone": zones}, "rows": rows,
               "excludedDates": sorted(excluded_dates, key=lambda row: row["eventId"])}
    raw = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = output_dir / "evidence.json.gz"
    evidence_path.write_bytes(compressed)
    receipt = {"schemaId": "trace-chronology-evidence-build-audit-v1", "releaseId": release_id,
               "sourceRowsPreserved": total, "canonicalRecordsMutated": False,
               "completeCatalogClockStatusCounts": dict(full_clock_status_counts),
               "rowsWithoutAnyStructuredClock": total - len(value_by_id),
               "counts": dict(sorted(audit.items())), "sources": {s: dict(c) for s, c in sorted(by_source.items())},
               "countSemantics": {"accepted_kind_counters": "mutually exclusive accepted interval kinds; calendar-day bounds are not recovered clocks",
                                  "held_counters": "withheld source-clock or named-zone precision; a record may still retain a wider supported calendar-day or offset-envelope interval"},
               "sameDayCraftAdjacencyCoverage": dict(pair_counts),
               "adjacencyScope": "mapped exact-day recognized craft links in unchanged canonical packed playback order; current coverage only, compare separately with frozen previous evidence",
               "evidence": {"path": str(evidence_path), "bytes": len(compressed),
                            "sha256": hashlib.sha256(compressed).hexdigest(), "decodedBytes": len(raw),
                            "decodedSha256": hashlib.sha256(raw).hexdigest(), "rowCount": len(rows)},
               "timezoneDatabase": tz_metadata, "inputs": pins, "acceptedSamples": sample,
               "policy": {"sentinelsWithheld": True, "missingClocksAreMidnight": False,
                          "sourceClockResolutionPreserved": True, "uncertainDateMidpointsUsed": False,
                          "dstFoldCandidatesBounded": True, "nonexistentLocalClocksAccepted": False,
                          "longitudeTimezoneGuessesUsed": False, "qualitativeMidpointsUsed": False,
                          "automaticNarrativeMining": bool(recovered_path), "sourceField": "time_raw",
                          "narrativeRecoveryRequiresRerunSourcePinnedLeadingOwnOccurrenceRule": True,
                          "acceptedNarrativeOriginalChunksReopenedAndHashed": True,
                          "acceptedNarrativeSourceIdentityDateDescriptionAndExactQuoteRevalidated": True,
                          "geographicTimezoneIsInference": True,
                          "inferredZoneYearMinimum": 1900,
                          "pre1970NamedZonePrecisionRequiresIanaRepresentativeLocality": True,
                          "pre1970UnsupportedContinentalUsLocalitiesUseAllCivilOffsetsAfter": US_STANDARD_TIME_START,
                          "continentalUsCivilOffsetEnvelopeMinutes": list(CONTINENTAL_US_OFFSET_MINUTES),
                          "metropolitanFranceNationalOffsets": {"1911-03-12_through_1945-12-31": [0, 120],
                                                                "1946-01-01_through_1969-12-31": [60, 60]},
                          "ukHomeTerritoryOffsetsFrom1916October2Through1969Minutes": [0, 120],
                          "multiZoneCountriesUseAllPost1970IanaCandidates": True,
                          "sourceClockStatusAndCalendarDayBoundsRemainDistinct": True,
                          "approximateClockUncertaintyInvented": False,
                          "sourceCalendarDayBoundsRecoverEventClock": False,
                          "provenanceJoin": "eventId joins hashed effective summary row chunk_id/detail_index and hashed source-clock projection/value dictionary"},
               "storageLifecycle": {"canonicalArtifact": str(evidence_path), "rollback": "existing validated production data unchanged",
                                    "largeFilesOver100MiBCreated": [], "newBytes": len(compressed),
                                    "fullCatalogOrDetailCopiesCreated": False,
                                    "retention": "unique source-backed timing overlay and audit; retain while runtime references release"},
               "rebuildArguments": ["py", "-3", str(Path(__file__).resolve()), "--output", str(output_dir), "--release-id", release_id] +
                                   (["--reviewed-clock-evidence", str(Path(reviewed_path).resolve())] if reviewed_path else []) +
                                   (["--recovered-clock-evidence", str(Path(recovered_path).resolve())] if recovered_path else []),
               "reviewedNarrativeRowsAccepted": len(narrative_by_id),
               "recoveredClockRowsPresented": len(recovered_by_id),
               "ufocatSourceFieldRowsVerified": len(source_fields_by_id),
               "excludedOccurrenceDateCount": len(excluded_dates),
               "evidenceCodeCount": len(codes)}
    receipt["policy"].update({"documentedUfocatTimeDateFlagsUsed": bool(ufocat_fields_path),
                              "publicationApproximateErroneousDatesExcluded": bool(ufocat_fields_path),
                              "sourceDateExclusionsBlockRuntimeCalendarDateFallback": bool(ufocat_fields_path),
                              "blankUfocatFlagDoesNotAssertStandardOrDaylightTime": True,
                              "ufocatTimebaseReference": "https://cufos.org/PDFs/UFOCAT%20Codebook%202023.pdf"})
    if ufocat_fields_path:
        receipt["rebuildArguments"] += ["--ufocat-source-fields", str(Path(ufocat_fields_path).resolve())]
    audit_path = output_dir / "evidence_build_audit.json"
    audit_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"rowCount": len(rows), "gzipBytes": len(compressed), "decodedBytes": len(raw),
                      "counts": dict(audit), "sameDayLinks": dict(pair_counts), "output": str(evidence_path)}))
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--reviewed-clock-evidence", type=Path)
    parser.add_argument("--recovered-clock-evidence", type=Path)
    parser.add_argument("--ufocat-source-fields", type=Path)
    parser.add_argument("--release-id", default=RELEASE)
    args = parser.parse_args()
    # Use the project's already-installed historical timezone database; no
    # dependency installation or dataset download is performed by this build.
    if str(SHARED / ".python_packages") not in sys.path:
        sys.path.insert(0, str(SHARED / ".python_packages"))
    build(args.output, args.reviewed_clock_evidence, args.recovered_clock_evidence, args.release_id, args.ufocat_source_fields)
