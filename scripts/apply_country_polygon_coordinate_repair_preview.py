"""Repair declared-country coordinates that plot outside the country polygon.

This preview lane targets the visible offshore-dot failure mode after the
broader sign and U.S.-jurisdiction repair passes. It is intentionally
conservative:

- only exact/source coordinate rows are considered;
- U.S. rows are skipped because state-level repair handles those separately;
- rows already inside their declared country polygon are untouched;
- sea/offshore/island-like rows are not moved to land automatically;
- repair uses a same-country GeoNames feature whose coordinate is inside the
  declared country polygon.

Rows that are land/city-like but still outside the polygon with no safe
GeoNames match are unmapped pending review. That removes misleading water dots
without inventing a replacement coordinate.
"""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path
from typing import Any

from scripts.apply_coordinate_sanity_preview import (
    EXACT_COORDINATE_SOURCES,
    clean_text,
    inferred_country_name,
    load_country_index,
    parse_float,
    point_in_feature,
    write_json,
)
from scripts.summarize_structured_city_alias_geonames_mapping_candidates import (
    city_alias_variants,
    city_key,
    normalized_city_keys,
)


DEFAULT_INPUT = Path("data/canonical_preview_map_enrich_v35_us_state_coordinate_repair/deduped_events.jsonl")
DEFAULT_COUNTRIES = Path("static_bundle/data/world_countries.geojson")
DEFAULT_COUNTRY_INFO = Path("cache/map_overlays/countryInfo.txt")
DEFAULT_GEONAMES_ZIP = Path("cache/map_overlays/allCountries.zip")
DEFAULT_OUTPUT_DIR = Path("data/canonical_preview_map_enrich_v36_country_polygon_coordinate_repair")
DEFAULT_REPORT = Path("data/reports/country_polygon_coordinate_repair_v36_report.json")

REPAIRABLE_FEATURE_CLASSES = {"P", "T", "S", "L"}
DEFAULT_REPAIR_COUNTRIES = {
    "Austria",
    "Belgium",
    "Denmark",
    "Finland",
    "France",
    "Germany",
    "Ireland",
    "Italy",
    "Luxembourg",
    "Netherlands",
    "Norway",
    "Portugal",
    "Spain",
    "Sweden",
    "Switzerland",
    "United Kingdom",
}
EXPLICIT_OFFSHORE_LOCATION_RE = re.compile(
    r"\b("
    r"ocean|atlantic|pacific|mediter\w*|tyrrhenian|adriatic|ligurian|"
    r"english\s+channel|irish\s+sea|sea\s+of\s+\w+|high\s+seas|bay|"
    r"offshore|\boff\b|off\s+(?:the\s+)?coast|ship|boat|aboard|at\s+sea"
    r")\b",
    re.IGNORECASE,
)
EXPLICIT_ISLAND_LOCATION_RE = re.compile(
    r"\b(island|islands|isle|channel\s+isl|channel\s+isle|channel\s+islands)\b",
    re.IGNORECASE,
)
SEA_TOWN_SUFFIX_RE = re.compile(r"\b\w+(?:-\w+)*-on-sea\b", re.IGNORECASE)
TRAILING_CITY_NOISE_RE = re.compile(
    r"\s+(?:"
    r"[NSEW]|north|south|east|west|"
    r"[NSEW]\d+(?:\.\d+)?(?:M|MI|KM)?|"
    r"\d+(?:\.\d+)?\s*(?:M|MI|KM)|"
    r"[A-Z]{0,2}[- ]?\d+[A-Z]?|"
    r"D\d+[A-Z]?|N\d+[A-Z]?|I[- ]?\d+|HWY\s*\d+|RTE\s*\d+|RT\s*\d+"
    r")$",
    re.IGNORECASE,
)


def apply_country_polygon_coordinate_repair_preview(
    *,
    input_path: Path,
    countries_geojson: Path,
    geonames_zip: Path,
    country_info: Path,
    output_dir: Path,
    report_output: Path,
) -> dict[str, Any]:
    country_index = load_country_index(countries_geojson)
    country_codes = load_country_code_aliases(country_info)
    repair_countries = DEFAULT_REPAIR_COUNTRIES
    candidates = collect_suspicious_candidates(input_path, country_index, country_codes, repair_countries)
    needed_keys = {
        (candidate["country_code"], key)
        for candidate in candidates
        if country_codes.get(candidate["country_name"])
        for key in candidate["city_keys"]
    }
    geonames_index = load_relevant_geonames_index(geonames_zip, needed_keys, country_index, country_codes)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "deduped_events.jsonl"
    tmp_output_path = output_path.with_suffix(".jsonl.tmp")

    input_event_count = 0
    mapped_before_count = 0
    checked_outside_polygon_count = 0
    repaired_count = 0
    quarantined_count = 0
    skipped_offshore_count = 0
    offshore_sign_flip_count = 0
    declared_country_sign_flip_count = 0
    no_candidate_count = 0
    repaired_by_country: dict[str, int] = {}
    quarantined_by_country: dict[str, int] = {}
    examples: list[dict[str, Any]] = []

    with input_path.open("r", encoding="utf-8") as source, tmp_output_path.open("w", encoding="utf-8", newline="\n") as output:
        for line in source:
            if not line.strip():
                continue
            input_event_count += 1
            event = json.loads(line)
            if has_usable_coordinates(event):
                mapped_before_count += 1

            analysis = analyze_candidate_event(event, country_index, country_codes, repair_countries)
            if analysis is not None:
                checked_outside_polygon_count += 1
                if analysis["offshore_like"]:
                    flipped_event = repair_offshore_sign_flip_event(event, analysis)
                    if flipped_event is not None:
                        event = flipped_event
                        repaired_count += 1
                        offshore_sign_flip_count += 1
                        repaired_by_country[analysis["country_name"]] = repaired_by_country.get(analysis["country_name"], 0) + 1
                        action = action_payload("repaired_offshore_sign_flip", event, analysis, None)
                    else:
                        skipped_offshore_count += 1
                        action = action_payload("skipped_offshore_like", event, analysis, None)
                else:
                    candidate = best_country_candidate(analysis, geonames_index)
                    if candidate is not None:
                        event = repair_event(event, analysis, candidate)
                        repaired_count += 1
                        repaired_by_country[analysis["country_name"]] = repaired_by_country.get(analysis["country_name"], 0) + 1
                        action = action_payload("repaired", event, analysis, candidate)
                    else:
                        flipped_event = repair_declared_country_sign_flip_event(event, analysis, country_index)
                        if flipped_event is not None:
                            event = flipped_event
                            repaired_count += 1
                            declared_country_sign_flip_count += 1
                            repaired_by_country[analysis["country_name"]] = repaired_by_country.get(analysis["country_name"], 0) + 1
                            action = action_payload("repaired_declared_country_sign_flip", event, analysis, None)
                        else:
                            event = quarantine_event(event, analysis)
                            quarantined_count += 1
                            no_candidate_count += 1
                            quarantined_by_country[analysis["country_name"]] = quarantined_by_country.get(analysis["country_name"], 0) + 1
                            action = action_payload("quarantined_no_same_country_geonames_match", event, analysis, None)
                if len(examples) < 160:
                    examples.append(action)

            output.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")

    tmp_output_path.replace(output_path)
    report = {
        "schema_version": 1,
        "mode": "preview_apply",
        "apply_policy": "declared_country_polygon_city_feature_repair_or_unmap",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": True,
        "inputs": {
            "deduped_events": str(input_path),
            "countries_geojson": str(countries_geojson),
            "geonames_zip": str(geonames_zip),
            "country_info": str(country_info),
        },
        "outputs": {
            "deduped_events": str(output_path),
            "report": str(report_output),
        },
        "input_event_count": input_event_count,
        "mapped_before_count": mapped_before_count,
        "checked_outside_declared_country_polygon_count": checked_outside_polygon_count,
        "repaired_event_count": repaired_count,
        "quarantined_event_count": quarantined_count,
        "skipped_offshore_like_count": skipped_offshore_count,
        "offshore_sign_flip_count": offshore_sign_flip_count,
        "declared_country_sign_flip_count": declared_country_sign_flip_count,
        "no_candidate_count": no_candidate_count,
        "mapped_after_count": mapped_before_count - quarantined_count,
        "repaired_by_country": dict(sorted(repaired_by_country.items())),
        "quarantined_by_country": dict(sorted(quarantined_by_country.items())),
        "examples": examples,
        "notes": [
            "This lane is intentionally scoped to the Europe/near-Europe countries that produced the visible offshore map artifacts.",
            "U.S. rows are skipped; explicit U.S. state repair is handled by the jurisdiction repair lane.",
            "Rows already inside the declared country polygon are untouched.",
            "Sea/offshore/island-like rows are not moved to land automatically.",
            "A narrow Mediterranean-sign correction flips source longitudes only for France Mediterranean Sea rows that are clearly on the wrong side of the country.",
            "A generic sign correction flips longitude only when the flipped point lands inside the declared country polygon.",
            "Safe repairs require a same-country GeoNames feature inside the declared country polygon.",
            "Land-like rows outside the declared country polygon with no safe GeoNames match are unmapped pending review.",
        ],
    }
    write_json(report_output, report)
    return report


def collect_suspicious_candidates(
    input_path: Path,
    country_index: dict[str, dict[str, Any]],
    country_codes: dict[str, str],
    repair_countries: set[str],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    with input_path.open("r", encoding="utf-8") as source:
        for line in source:
            if not line.strip():
                continue
            event = json.loads(line)
            analysis = analyze_candidate_event(event, country_index, country_codes, repair_countries)
            if analysis is not None:
                candidates.append(analysis)
    return candidates


def analyze_candidate_event(
    event: dict[str, Any],
    country_index: dict[str, dict[str, Any]],
    country_codes: dict[str, str],
    repair_countries: set[str],
) -> dict[str, Any] | None:
    coordinate_source = clean_text(event.get("coordinate_source"))
    if coordinate_source not in EXACT_COORDINATE_SOURCES:
        return None
    lat = parse_float(event.get("lat"))
    lon = parse_float(event.get("lon"))
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    country_name = inferred_country_name(event)
    if not country_name or country_name not in repair_countries or country_name not in country_index:
        return None
    if country_name not in country_codes:
        return None
    if point_in_feature(lat, lon, country_index[country_name]):
        return None

    primary_text = primary_place_text(event)
    city_keys = cleaned_city_keys(primary_text)
    if not city_keys:
        return None
    return {
        "country_name": country_name,
        "country_code": country_codes[country_name],
        "lat": lat,
        "lon": lon,
        "primary_text": primary_text,
        "city_keys": city_keys,
        "offshore_like": is_offshore_like(event, primary_text),
    }


def load_country_code_aliases(path: Path) -> dict[str, str]:
    aliases: dict[str, str] = {
        "United States of America": "US",
        "Czech Republic": "CZ",
        "Former Yugoslavia": "RS",
    }
    if not path.exists():
        return aliases
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 5:
                continue
            iso2, iso3, _, _, name = parts[:5]
            aliases[name] = iso2.upper()
            aliases[iso2.upper()] = iso2.upper()
            aliases[iso3.upper()] = iso2.upper()
    # Match the Natural Earth country names used by the app's GeoJSON.
    aliases.setdefault("United Kingdom", "GB")
    aliases.setdefault("Russia", "RU")
    aliases.setdefault("South Korea", "KR")
    aliases.setdefault("North Korea", "KP")
    aliases.setdefault("Vietnam", "VN")
    aliases.setdefault("Syria", "SY")
    aliases.setdefault("Moldova", "MD")
    aliases.setdefault("Laos", "LA")
    aliases.setdefault("Bolivia", "BO")
    aliases.setdefault("Venezuela", "VE")
    return aliases


def load_relevant_geonames_index(
    path: Path,
    needed_keys: set[tuple[str, str]],
    country_index: dict[str, dict[str, Any]],
    country_codes: dict[str, str],
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    code_to_country = {code: name for name, code in country_codes.items() if name in country_index}
    index: dict[tuple[str, str], list[dict[str, Any]]] = {}
    if not needed_keys:
        return index
    needed_countries = {country_code for country_code, _ in needed_keys}
    with zipfile.ZipFile(path) as archive:
        with archive.open("allCountries.txt") as raw:
            for raw_line in raw:
                line = raw_line.decode("utf-8", errors="replace").rstrip("\n")
                parts = line.split("\t")
                if len(parts) < 19:
                    continue
                feature_class = parts[6].upper()
                if feature_class not in REPAIRABLE_FEATURE_CLASSES:
                    continue
                country_code = parts[8].upper()
                if country_code not in needed_countries:
                    continue
                country_name = code_to_country.get(country_code)
                if not country_name:
                    continue
                lat = parse_float(parts[4])
                lon = parse_float(parts[5])
                if lat is None or lon is None:
                    continue
                candidate = {
                    "geoname_id": parts[0],
                    "name": parts[1],
                    "ascii_name": parts[2],
                    "primary_city_key": city_key(parts[1]),
                    "lat": lat,
                    "lon": lon,
                    "country_code": country_code,
                    "admin1": parts[10].upper(),
                    "feature_class": feature_class,
                    "feature_code": parts[7],
                    "population": int(parts[14] or 0),
                    "timezone": parts[17],
                }
                for key in normalized_city_keys(parts[1], parts[2], parts[3]):
                    index_key = (country_code, key)
                    if index_key in needed_keys:
                        index.setdefault(index_key, []).append(candidate)
    for candidates in index.values():
        candidates.sort(key=candidate_sort_key)
    return index


def best_country_candidate(
    analysis: dict[str, Any],
    geonames_index: dict[tuple[str, str], list[dict[str, Any]]],
) -> dict[str, Any] | None:
    keys = analysis["city_keys"]
    country_code = analysis["country_code"]
    for key in keys:
        candidates = geonames_index.get((country_code, key)) or []
        primary_matches = [candidate for candidate in candidates if candidate.get("primary_city_key") in keys]
        if primary_matches:
            return primary_matches[0]
    for key in keys:
        candidates = geonames_index.get((country_code, key)) or []
        if len(candidates) == 1:
            return candidates[0]
    return None


def candidate_sort_key(candidate: dict[str, Any]) -> tuple[int, int, int, str, str]:
    feature_class_rank = {"P": 0, "T": 1, "S": 2, "L": 3}.get(candidate["feature_class"], 9)
    feature_code_rank = 0 if candidate["feature_code"] in {"PPLC", "PPLA", "PPLA2", "PPLA3", "PPLA4", "PPL"} else 1
    return (
        feature_class_rank,
        feature_code_rank,
        -int(candidate["population"] or 0),
        candidate["name"],
        candidate["geoname_id"],
    )


def repair_event(event: dict[str, Any], analysis: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    next_event = dict(event)
    next_event["country_polygon_coordinate_repair_action"] = "replace_with_same_country_geonames_feature"
    next_event["country_polygon_coordinate_repair_reason"] = "outside_declared_country_polygon"
    next_event["country_polygon_coordinate_original_lat"] = analysis["lat"]
    next_event["country_polygon_coordinate_original_lon"] = analysis["lon"]
    next_event["country_polygon_coordinate_original_source"] = next_event.get("coordinate_source")
    next_event["country_polygon_coordinate_geoname_id"] = candidate["geoname_id"]
    next_event["lat"] = candidate["lat"]
    next_event["lon"] = candidate["lon"]
    next_event["coordinate_source"] = "geocoded"
    next_event["location_precision"] = "city" if candidate["feature_class"] == "P" else "mapped"
    next_event["geocode_query_used"] = f"{candidate['name']}, {analysis['country_name']}"
    next_event["geocode_display_name"] = f"{candidate['name']}, {analysis['country_name']}"
    next_event["geocode_confidence"] = 0.88 if candidate["feature_class"] == "P" else 0.78
    next_event["mapping_notes"] = append_note(
        next_event,
        f"Country-polygon coordinate repair replaced outside-country coordinate with same-country GeoNames feature {candidate['name']}, {analysis['country_name']}.",
    )
    return next_event


def quarantine_event(event: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    next_event = dict(event)
    next_event["country_polygon_coordinate_repair_action"] = "quarantine_unmapped"
    next_event["country_polygon_coordinate_repair_reason"] = "outside_declared_country_polygon_no_same_country_geonames_match"
    next_event["country_polygon_coordinate_original_lat"] = analysis["lat"]
    next_event["country_polygon_coordinate_original_lon"] = analysis["lon"]
    next_event["country_polygon_coordinate_original_source"] = next_event.get("coordinate_source")
    next_event["lat"] = None
    next_event["lon"] = None
    next_event["coordinate_source"] = "unresolved"
    next_event["location_precision"] = "unknown"
    next_event["mapping_notes"] = append_note(
        next_event,
        f"Country-polygon coordinate repair unmapped outside-country coordinate for {analysis['country_name']} pending review.",
    )
    return next_event


def repair_declared_country_sign_flip_event(
    event: dict[str, Any],
    analysis: dict[str, Any],
    country_index: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if not SEA_TOWN_SUFFIX_RE.search(analysis["primary_text"]):
        return None
    old_lon = analysis["lon"]
    new_lon = -old_lon
    if old_lon == 0 or not (-180 <= new_lon <= 180):
        return None
    country_feature = country_index.get(analysis["country_name"])
    if country_feature is None or not point_in_feature(analysis["lat"], new_lon, country_feature):
        return None
    next_event = dict(event)
    next_event["country_polygon_coordinate_repair_action"] = "replace_with_declared_country_sign_flip"
    next_event["country_polygon_coordinate_repair_reason"] = "flipped_longitude_inside_declared_country_polygon"
    next_event["country_polygon_coordinate_original_lat"] = analysis["lat"]
    next_event["country_polygon_coordinate_original_lon"] = old_lon
    next_event["country_polygon_coordinate_original_source"] = next_event.get("coordinate_source")
    next_event["lat"] = analysis["lat"]
    next_event["lon"] = new_lon
    next_event["coordinate_source"] = "source_coordinates"
    next_event["location_precision"] = next_event.get("location_precision") or "exact_coords"
    next_event["mapping_notes"] = append_note(
        next_event,
        f"Country-polygon coordinate repair flipped longitude sign because the flipped point is inside {analysis['country_name']}.",
    )
    return next_event


def repair_offshore_sign_flip_event(event: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any] | None:
    if analysis["country_name"] != "France":
        return None
    text = clean_text(event.get("location_raw")).lower()
    if "mediter" not in text or "var" not in text:
        return None
    old_lon = analysis["lon"]
    if old_lon >= 0:
        return None
    new_lon = abs(old_lon)
    if not (5.0 <= new_lon <= 7.5 and 42.0 <= analysis["lat"] <= 44.0):
        return None
    next_event = dict(event)
    next_event["country_polygon_coordinate_repair_action"] = "replace_with_offshore_mediterranean_sign_flip"
    next_event["country_polygon_coordinate_repair_reason"] = "mediterranean_france_source_longitude_wrong_sign"
    next_event["country_polygon_coordinate_original_lat"] = analysis["lat"]
    next_event["country_polygon_coordinate_original_lon"] = old_lon
    next_event["country_polygon_coordinate_original_source"] = next_event.get("coordinate_source")
    next_event["lat"] = analysis["lat"]
    next_event["lon"] = new_lon
    next_event["coordinate_source"] = "source_coordinates"
    next_event["location_precision"] = "exact_coords"
    next_event["mapping_notes"] = append_note(
        next_event,
        "Country-polygon coordinate repair flipped Mediterranean France source longitude sign.",
    )
    return next_event


def action_payload(
    action: str,
    event: dict[str, Any],
    analysis: dict[str, Any],
    candidate: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "action": action,
        "canonical_event_id": event.get("canonical_event_id"),
        "source_name": event.get("source_name"),
        "source_row_number": event.get("source_row_number"),
        "source_native_id": event.get("source_native_id"),
        "date": event.get("date") or event.get("sort_date_iso"),
        "location_raw": event.get("location_raw"),
        "country": analysis["country_name"],
        "old_lat": analysis["lat"],
        "old_lon": analysis["lon"],
        "new_lat": candidate.get("lat") if candidate else event.get("lat") if action in {"repaired_offshore_sign_flip", "repaired_declared_country_sign_flip"} else None,
        "new_lon": candidate.get("lon") if candidate else event.get("lon") if action in {"repaired_offshore_sign_flip", "repaired_declared_country_sign_flip"} else None,
        "geoname_id": candidate.get("geoname_id") if candidate else None,
        "geonames_name": candidate.get("name") if candidate else None,
        "feature_class": candidate.get("feature_class") if candidate else None,
        "feature_code": candidate.get("feature_code") if candidate else None,
    }


def primary_place_text(event: dict[str, Any]) -> str:
    return clean_text(event.get("location_raw")).split(",", 1)[0].strip()


def cleaned_city_keys(value: str) -> set[str]:
    base = clean_text(value)
    if not base:
        return set()
    variants: set[str] = set()
    queue = [base]
    stripped_parenthetical = re.sub(r"\s*\([^)]*\)\s*$", "", base).strip()
    if stripped_parenthetical and stripped_parenthetical != base:
        queue.append(stripped_parenthetical)
    compact = base
    for _ in range(3):
        next_compact = TRAILING_CITY_NOISE_RE.sub("", compact).strip(" -")
        if next_compact == compact:
            break
        compact = next_compact
        if compact:
            queue.append(compact)
    for item in queue:
        variants.update(city_alias_variants(item))
    return {variant for variant in variants if variant and not is_placeholder_city_key(variant)}


def is_placeholder_city_key(value: str) -> bool:
    return value in {"0", "unk", "unknown", "data missing", "undisclosed location"}


def is_offshore_like(event: dict[str, Any], primary_text: str) -> bool:
    raw_fields = event.get("raw_fields") or {}
    primary = clean_text(primary_text)
    full_text = " ".join(
        clean_text(value)
        for value in [
            event.get("location_raw"),
            primary_text,
            raw_fields.get("LOCATION"),
            raw_fields.get("COUNTY"),
        ]
        if clean_text(value)
    )
    if SEA_TOWN_SUFFIX_RE.search(primary):
        return False
    if EXPLICIT_OFFSHORE_LOCATION_RE.search(full_text):
        return True
    if EXPLICIT_ISLAND_LOCATION_RE.search(full_text):
        # Island and Channel Island rows often sit outside the coarse country
        # polygon because the Natural Earth country shell omits dependencies or
        # small islands. Keep those exact source coordinates unless a separate
        # island-aware boundary lane is added.
        return True
    return False


def has_usable_coordinates(event: dict[str, Any]) -> bool:
    lat = parse_float(event.get("lat"))
    lon = parse_float(event.get("lon"))
    return lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180


def append_note(event: dict[str, Any], note: str) -> str:
    existing = clean_text(event.get("mapping_notes"))
    return f"{existing} {note}".strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--countries-geojson", type=Path, default=DEFAULT_COUNTRIES)
    parser.add_argument("--geonames-zip", type=Path, default=DEFAULT_GEONAMES_ZIP)
    parser.add_argument("--country-info", type=Path, default=DEFAULT_COUNTRY_INFO)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = apply_country_polygon_coordinate_repair_preview(
        input_path=args.input,
        countries_geojson=args.countries_geojson,
        geonames_zip=args.geonames_zip,
        country_info=args.country_info,
        output_dir=args.output_dir,
        report_output=args.report_output,
    )
    print(
        json.dumps(
            {
                "output": report["outputs"]["deduped_events"],
                "report": report["outputs"]["report"],
                "checked_outside_declared_country_polygon_count": report["checked_outside_declared_country_polygon_count"],
                "repaired_event_count": report["repaired_event_count"],
                "quarantined_event_count": report["quarantined_event_count"],
                "skipped_offshore_like_count": report["skipped_offshore_like_count"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
