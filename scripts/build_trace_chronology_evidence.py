"""Precompute source-backed UTC intervals without modifying catalog records.

Reads the shared reviewed clock dictionary, its inherited event projection and
effective summary shards. A clock must be explicitly typed exact; source noon
and midnight defaults, approximations, qualitative periods and partial dates
remain excluded. Geographic rules select existing IANA historical zones only
from explicit country/state components; longitude is never a timezone model.
The small sparse sidecar joins records by their preserved event IDs.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
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
                            "countryInfo": str(country_info), "countryInfoSha256": sha(country_info),
                            "jurisdictionStateBounds": str(state_reference), "stateReferenceSha256": sha(state_reference),
                            "jurisdictionCountryGeometry": str(geometry_path), "countryGeometrySha256": sha(geometry_path),
                            "geographicGuard": "Existing padded state QA bounds and country component bounding boxes; contradiction holdout, not precise timezone polygons"}


def strict_zone(event, aliases, single_zones):
    """Resolve a structured jurisdiction; never scan incidental place words."""
    precision = event.get("location_precision")
    if precision not in {"city", "exact_coords", "address", "county"}:
        return None, "low_location_precision"
    if not event.get("has_coordinates"):
        return None, "unmapped"
    raw = str(event.get("location_raw") or "")
    parts = [normalized(part) for part in raw.split(",") if normalized(part)]
    if len(parts) < 2:
        return None, "unstructured_location"
    # UFOCAT's final continent is a separate field, not ISO country AF/AS.
    if len(parts) >= 3 and parts[-1] in CONTINENTS and parts[-2] in aliases:
        parts.pop()
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


def explicit_utc_interval(date_iso, local_start_ms, local_end_ms, token, location_zone):
    if token in {"UTC", "GMT", "Z"}:
        return utc_interval(date_iso, local_start_ms, local_end_ms, "UTC"), "UTC"
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


def build(output_dir, reviewed_path=None):
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
    codes, code_by_basis, zones, zone_by_name = [], {}, [], {}
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

    def accept(event, interval, zone, kind, basis, reason):
        code_key = kind, basis, reason
        if code_key not in code_by_basis:
            code_by_basis[code_key] = len(codes)
            codes.append({"status": "accepted", "kind": kind,
                          "confidence": "bounded" if reason == "historical_fold_interval" else "high",
                          "basis": basis, "conversion": reason,
                          "clockEvidence": "source_reported_event_occurrence_clock_resolution",
                          "timezoneEvidence": "explicit_source_offset" if reason == "explicit_source_offset" else "structured_jurisdiction_inference_with_historical_iana_rules",
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
        audit[reason] += 1
        by_source[event.get("source", "unknown")]["accepted_utc_interval"] += 1
        if len(sample) < 25 or event_id in {3972295816637808, 1880247488343365, 1548188833291382, 3448855352240391}:
            sample.append({"eventId": event_id, "source": event.get("source"), "rawTime": event.get("time_raw"),
                           "date": event.get("sort_date_iso"), "chunkId": event.get("chunk_id"),
                           "detailIndex": event.get("detail_index"), "location": event.get("location_raw"),
                           "zone": zone, "utcStartMs": interval[0], "utcEndMs": interval[1], "basis": basis})

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
            if event.get("date_precision") == "exact_day" and event.get("has_coordinates"):
                craft = event.get("craft_type_inferred")
                if event_id in sequence_by_id and craft not in {None, "unknown", "conventional_or_explained", "non_ufo_context"}:
                    by_day_craft[(event.get("sort_date_iso"), craft)].append(event_id)
            if event.get("date_precision") != "exact_day" or event.get("exact_day_eligible") is False:
                audit["held_partial_or_uncertain_date"] += 1
                continue
            zone, zone_reason = strict_zone(event, aliases, single_zones)
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
                        raise ValueError("Reviewed narrative historical zone lacks supported locality or explicit offset")
                    interval, reason = utc_interval(narrative["date"], narrative["localStartMs"], narrative["localEndMs"], narrative["zone"])
                if interval is None:
                    raise ValueError("Reviewed narrative has invalid local interval")
                accept(event, interval, narrative["zone"], "reviewed_event_clock", narrative["basis"], reason)
                continue
            value_code = value_by_id.get(event_id)
            if value_code is None:
                audit["held_no_source_clock"] += 1
                continue
            value = dictionary[value_code]
            status = clock_manifest["codes"]["status"][value[3]]
            audit["source_status_" + status] += 1
            if status != "exact_clock":
                audit["held_" + status] += 1
                continue
            if value[2] != event.get("time_raw"):
                raise ValueError("Source clock projection/raw field mismatch")
            clock = source_clock(value[2], value[5])
            if not clock:
                audit["held_unsupported_exact_clock_syntax"] += 1
                continue
            start, end, token = clock
            if token:
                (interval, reason), resolved_zone = explicit_utc_interval(event.get("sort_date_iso"), start, end, token, zone)
                zone = resolved_zone
                basis = "Explicit source event clock time_raw with explicit timezone " + token
            elif zone:
                if not historical_jurisdiction_supported(event, zone):
                    audit["held_historical_locality_timezone_uncertainty"] += 1
                    continue
                interval, reason = utc_interval(event.get("sort_date_iso"), start, end, zone)
                basis = "Explicit source event clock time_raw; " + zone_reason + "; historical IANA rules"
            else:
                audit["held_" + zone_reason] += 1
                continue
            if not interval:
                audit["held_" + reason] += 1
                continue
            accept(event, interval, zone, "source_exact_clock", basis, reason)
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
    pair_counts["utc_order_resolved_before"] = 0
    rows.sort(key=lambda row: row[0])
    payload = {"schemaId": "trace-chronology-evidence-v1", "releaseId": RELEASE,
               "sourceContract": "source-backed-clock-and-historical-zone-v1",
               "rowSchema": ["eventId", "utcStartMs", "utcEndMs", "evidenceCode", "zoneCode"],
               "codes": {"evidence": codes, "zone": zones}, "rows": rows}
    raw = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = output_dir / "evidence.json.gz"
    evidence_path.write_bytes(compressed)
    receipt = {"schemaId": "trace-chronology-evidence-build-audit-v1", "releaseId": RELEASE,
               "sourceRowsPreserved": total, "canonicalRecordsMutated": False,
               "completeCatalogClockStatusCounts": dict(full_clock_status_counts),
               "rowsWithoutAnyStructuredClock": total - len(value_by_id),
               "counts": dict(sorted(audit.items())), "sources": {s: dict(c) for s, c in sorted(by_source.items())},
               "sameDayCraftAdjacencyCoverage": dict(pair_counts),
               "adjacencyScope": "mapped exact-day recognized craft links in unchanged canonical packed playback order; all such links formerly unresolved",
               "evidence": {"path": str(evidence_path), "bytes": len(compressed),
                            "sha256": hashlib.sha256(compressed).hexdigest(), "decodedBytes": len(raw),
                            "decodedSha256": hashlib.sha256(raw).hexdigest(), "rowCount": len(rows)},
               "timezoneDatabase": tz_metadata, "inputs": pins, "acceptedSamples": sample,
               "policy": {"sentinelsWithheld": True, "missingClocksAreMidnight": False,
                          "sourceClockResolutionPreserved": True, "uncertainDateMidpointsUsed": False,
                          "dstFoldCandidatesBounded": True, "nonexistentLocalClocksAccepted": False,
                          "longitudeTimezoneGuessesUsed": False, "qualitativeMidpointsUsed": False,
                          "automaticNarrativeMining": False, "sourceField": "time_raw",
                          "acceptedNarrativeOriginalChunksReopenedAndHashed": True,
                          "acceptedNarrativeSourceIdentityDateDescriptionAndExactQuoteRevalidated": True,
                          "geographicTimezoneIsInference": True,
                          "inferredZoneYearMinimum": 1900,
                          "pre1970InferredZonesRequireIanaRepresentativeLocality": True,
                          "provenanceJoin": "eventId joins hashed effective summary row chunk_id/detail_index and hashed source-clock projection/value dictionary"},
               "storageLifecycle": {"canonicalArtifact": str(evidence_path), "rollback": "existing validated production data unchanged",
                                    "largeFilesOver100MiBCreated": [], "newBytes": len(compressed),
                                    "fullCatalogOrDetailCopiesCreated": False,
                                    "retention": "unique source-backed timing overlay and audit; retain while runtime references release"},
               "rebuildArguments": ["py", "-3", str(Path(__file__).resolve()), "--output", str(output_dir)] +
                                   (["--reviewed-clock-evidence", str(Path(reviewed_path).resolve())] if reviewed_path else []),
               "reviewedNarrativeRowsAccepted": len(narrative_by_id)}
    audit_path = output_dir / "evidence_build_audit.json"
    audit_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"rowCount": len(rows), "gzipBytes": len(compressed), "decodedBytes": len(raw),
                      "counts": dict(audit), "sameDayLinks": dict(pair_counts), "output": str(evidence_path)}))
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--reviewed-clock-evidence", type=Path)
    args = parser.parse_args()
    # Use the project's already-installed historical timezone database; no
    # dependency installation or dataset download is performed by this build.
    if str(SHARED / ".python_packages") not in sys.path:
        sys.path.insert(0, str(SHARED / ".python_packages"))
    build(args.output, args.reviewed_clock_evidence)
