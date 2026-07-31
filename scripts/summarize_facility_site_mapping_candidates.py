"""Find authority-backed facility/site mapping candidates.

This report-only lane resolves unresolved rows such as ``Holloman AFB, US`` or
``White Sands Pad 33, White Sands Proving Grounds, NM`` against local curated
map overlays. It does not call a geocoder and it deliberately avoids generic
city/country or country-centroid matching.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from pathlib import Path
from typing import Any


DEFAULT_MAPPING_CSV = Path("data/reports/mapping_coverage_opportunities_after_structured_city_alias_quarantine_v7.csv")
DEFAULT_MILITARY_BASES = Path("webapp/static_public/data/map_overlays/military_bases.geojson")
DEFAULT_RESEARCH_SITES = Path("webapp/static_public/data/map_overlays/research_test_sites.geojson")
DEFAULT_OUTPUT_JSON = Path("data/reports/facility_site_mapping_candidates_after_structured_city_alias_v8.json")
DEFAULT_OUTPUT_CSV = Path("data/reports/facility_site_mapping_candidates_after_structured_city_alias_v8.csv")

COUNTRY_ALIASES = {
    "us": "US",
    "usa": "US",
    "united states": "US",
    "can": "CA",
    "ca": "CA",
    "cn": "CA",
    "canada": "CA",
    "gb": "GB",
    "gbr": "GB",
    "uk": "GB",
    "united kingdom": "GB",
    "as": "",
    "eu": "",
}

US_ADMIN_CODES = {
    "ak",
    "al",
    "ar",
    "az",
    "ca",
    "co",
    "ct",
    "dc",
    "de",
    "fl",
    "ga",
    "hi",
    "ia",
    "id",
    "il",
    "in",
    "ks",
    "ky",
    "la",
    "ma",
    "md",
    "me",
    "mi",
    "mn",
    "mo",
    "ms",
    "mt",
    "nc",
    "nd",
    "ne",
    "nh",
    "nj",
    "nm",
    "nv",
    "ny",
    "oh",
    "ok",
    "or",
    "pa",
    "ri",
    "sc",
    "sd",
    "tn",
    "tx",
    "ut",
    "va",
    "vt",
    "wa",
    "wi",
    "wv",
    "wy",
}

FACILITY_HINTS = {
    "afb",
    "air base",
    "air force base",
    "airfield",
    "army airfield",
    "base",
    "camp",
    "fort",
    "missile range",
    "proving ground",
    "proving grounds",
    "range",
}


def summarize_facility_site_mapping_candidates(
    *,
    mapping_csv: Path,
    military_bases: Path,
    research_sites: Path,
) -> dict[str, Any]:
    authority = load_authority_index(military_bases=military_bases, research_sites=research_sites)
    rows = load_mapping_rows(mapping_csv)
    accepted: list[dict[str, Any]] = []
    rejected: dict[str, int] = {}

    for row in rows:
        if (row.get("bucket") or "") != "facility_or_site":
            continue
        count = int(row.get("count") or 0)
        parsed = parse_facility_query(row.get("query") or "")
        if not parsed:
            rejected["not_parseable_facility_query"] = rejected.get("not_parseable_facility_query", 0) + count
            continue
        matches = find_authority_matches(parsed, authority)
        if not matches:
            rejected["no_authority_match"] = rejected.get("no_authority_match", 0) + count
            continue
        if len(matches) > 1:
            rejected["ambiguous_authority_match"] = rejected.get("ambiguous_authority_match", 0) + count
            continue
        match = matches[0]
        accepted.append(
            {
                "query": normalize_query(row.get("query") or ""),
                "count": count,
                "confidence": "high",
                "candidate_count": 1,
                "name": match["name"],
                "lat": match["lat"],
                "lon": match["lon"],
                "country_code": match["country_code"],
                "admin1": match.get("admin1", ""),
                "timezone": "",
                "location_precision": "facility",
                "authority_source": match["source"],
                "authority_source_id": match.get("source_id", ""),
                "matched_alias": match["matched_alias"],
                "decision": "accepted_authority_facility_exact_alias",
            }
        )

    return {
        "schema_version": 1,
        "report_policy": "facility_site_mapping_candidates_report_only",
        "canonical_outputs_mutated": False,
        "geocoding_performed": False,
        "inputs": {
            "mapping_csv": str(mapping_csv),
            "military_bases": str(military_bases),
            "research_sites": str(research_sites),
        },
        "candidate_query_count": len(accepted),
        "candidate_event_count": sum(int(row["count"]) for row in accepted),
        "rejected_event_counts": dict(sorted(rejected.items())),
        "candidates": sorted(accepted, key=lambda item: (-int(item["count"]), item["query"])),
        "notes": [
            "Only facility_or_site residual rows are considered.",
            "Candidates require an exact normalized alias match against local authority overlays.",
            "Country/admin hints may constrain matches, but broad country or state centroids are never emitted.",
            "No canonical event coordinates are changed by this report.",
        ],
    }


def load_authority_index(*, military_bases: Path, research_sites: Path) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    for feature in load_geojson_features(military_bases):
        props = feature.get("properties") or {}
        coords = ((feature.get("geometry") or {}).get("coordinates") or [])
        if len(coords) < 2:
            continue
        names = authority_names_from_military(props)
        add_authority_record(
            index,
            names=names,
            record={
                "source": "military_bases",
                "source_id": clean_text(props.get("source_id")),
                "name": clean_text(props.get("name")),
                "country_code": clean_text(props.get("country_code")).upper(),
                "admin1": "",
                "lat": float(coords[1]),
                "lon": float(coords[0]),
            },
        )
    for feature in load_geojson_features(research_sites):
        props = feature.get("properties") or {}
        coords = ((feature.get("geometry") or {}).get("coordinates") or [])
        if len(coords) < 2:
            continue
        names = authority_names_from_research(props)
        add_authority_record(
            index,
            names=names,
            record={
                "source": "research_test_sites",
                "source_id": clean_text(props.get("site_id") or props.get("entity_id")),
                "name": clean_text(props.get("display_name") or props.get("entity_name") or props.get("site_name")),
                "country_code": clean_text(props.get("country_code")).upper(),
                "admin1": "",
                "lat": float(coords[1]),
                "lon": float(coords[0]),
            },
        )
    return index


def load_geojson_features(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    features = payload.get("features") or []
    return [feature for feature in features if isinstance(feature, dict)]


def authority_names_from_military(props: dict[str, Any]) -> set[str]:
    raw_names = {clean_text(props.get("name"))}
    return expand_authority_aliases(raw_names)


def authority_names_from_research(props: dict[str, Any]) -> set[str]:
    raw_names = {
        clean_text(props.get("entity_name")),
        clean_text(props.get("site_name")),
        clean_text(props.get("display_name")),
        clean_text(props.get("short_label")),
    }
    for alias in props.get("aliases") or []:
        raw_names.add(clean_text(alias))
    return expand_authority_aliases(raw_names)


def add_authority_record(index: dict[str, list[dict[str, Any]]], *, names: set[str], record: dict[str, Any]) -> None:
    for name in names:
        key = facility_key(name)
        if not key:
            continue
        item = dict(record)
        item["matched_alias"] = name
        index.setdefault(key, []).append(item)


def expand_authority_aliases(names: set[str]) -> set[str]:
    aliases: set[str] = set()
    for raw in names:
        name = clean_text(raw)
        if not name:
            continue
        aliases.add(name)
        stripped = re.sub(r"\s*\([^)]*\)", "", name).strip()
        if stripped:
            aliases.add(stripped)
        aliases.add(re.sub(r"\bAir Force Base\b", "AFB", stripped or name, flags=re.IGNORECASE))
        aliases.add(re.sub(r"\bAir Reserve Base\b", "ARB", stripped or name, flags=re.IGNORECASE))
        aliases.add(re.sub(r"\bAir National Guard Base\b", "ANGB", stripped or name, flags=re.IGNORECASE))
        aliases.add(re.sub(r"\bArmy Airfield\b", "AAF", stripped or name, flags=re.IGNORECASE))
        aliases.add(re.sub(r"\bNaval Air Station\b", "NAS", stripped or name, flags=re.IGNORECASE))
        aliases.add(re.sub(r"\bMissile Range\b", "Proving Grounds", stripped or name, flags=re.IGNORECASE))
        aliases.add(re.sub(r"\bMissile Range\b", "Proving Ground", stripped or name, flags=re.IGNORECASE))
        if " / " in name:
            aliases.update(part.strip() for part in name.split(" / ") if part.strip())
        if " — " in name:
            aliases.update(part.strip() for part in name.split(" — ") if part.strip())
    return {alias for alias in aliases if alias}


def parse_facility_query(value: str) -> dict[str, Any] | None:
    query = normalize_query(value)
    if not query:
        return None
    parts = [part.strip() for part in query.split(",") if part.strip()]
    if not parts:
        return None
    country_code = ""
    admin_hint = ""
    if len(parts) >= 2:
        trailing_country = COUNTRY_ALIASES.get(parts[-1])
        if trailing_country:
            country_code = trailing_country
            parts = parts[:-1]
        elif parts[-1] in US_ADMIN_CODES:
            admin_hint = parts[-1].upper()
            country_code = "US"
            parts = parts[:-1]
    if parts and parts[-1] in US_ADMIN_CODES:
        admin_hint = parts[-1].upper()
        if not country_code:
            country_code = "US"
        parts = parts[:-1]
    core_parts = [strip_non_name_context(part) for part in parts]
    core_parts = [part for part in core_parts if part]
    if not core_parts:
        return None
    candidates = []
    candidates.append(core_parts[0])
    if len(core_parts) > 1:
        candidates.append(core_parts[-1])
        candidates.append(" ".join(core_parts))
    names = {facility_key(candidate) for candidate in candidates if has_facility_hint(candidate)}
    names.discard("")
    if not names:
        return None
    return {"query": query, "name_keys": names, "country_code": country_code, "admin_hint": admin_hint}


def strip_non_name_context(value: str) -> str:
    text = re.sub(r"\b(now|formerly|near|nr|in|at)\b.*$", "", value).strip()
    return text.strip(" []")


def has_facility_hint(value: str) -> bool:
    key = facility_key(value)
    return any(hint in key for hint in FACILITY_HINTS)


def find_authority_matches(parsed: dict[str, Any], authority: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    seen: set[tuple[str, float, float]] = set()
    for name_key in parsed["name_keys"]:
        for record in authority.get(name_key, []):
            if parsed["country_code"] and record["country_code"] and parsed["country_code"] != record["country_code"]:
                continue
            if not parsed["country_code"] and record["country_code"] and record["country_code"] != "US":
                continue
            key = (record.get("source_id") or record["name"], record["lat"], record["lon"])
            if key in seen:
                continue
            seen.add(key)
            matches.append(record)
    return matches


def load_mapping_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def normalize_query(value: str) -> str:
    text = clean_text(value).lower()
    text = text.replace("\\,", ",")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*,\s*", ", ", text)
    return text.strip(" ,")


def facility_key(value: str) -> str:
    text = unicodedata.normalize("NFKD", clean_text(value))
    text = "".join(character for character in text if not unicodedata.combining(character))
    text = text.lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[.'`´’]", "", text)
    text = re.sub(r"\bairforce\b", "air force", text)
    text = re.sub(r"\bafb\b", "air force base", text)
    text = re.sub(r"\barb\b", "air reserve base", text)
    text = re.sub(r"\bangb\b", "air national guard base", text)
    text = re.sub(r"\baaf\b", "army airfield", text)
    text = re.sub(r"\bnas\b", "naval air station", text)
    text = re.sub(r"\s*/\s*", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "query",
        "count",
        "confidence",
        "candidate_count",
        "name",
        "lat",
        "lon",
        "country_code",
        "admin1",
        "timezone",
        "location_precision",
        "authority_source",
        "authority_source_id",
        "matched_alias",
        "decision",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mapping-csv", type=Path, default=DEFAULT_MAPPING_CSV)
    parser.add_argument("--military-bases", type=Path, default=DEFAULT_MILITARY_BASES)
    parser.add_argument("--research-sites", type=Path, default=DEFAULT_RESEARCH_SITES)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = summarize_facility_site_mapping_candidates(
        mapping_csv=args.mapping_csv,
        military_bases=args.military_bases,
        research_sites=args.research_sites,
    )
    report["outputs"] = {"json": str(args.output_json), "csv": str(args.output_csv)}
    write_json(args.output_json, report)
    write_csv(args.output_csv, report["candidates"])
    print(
        json.dumps(
            {
                "json": str(args.output_json),
                "csv": str(args.output_csv),
                "candidate_query_count": report["candidate_query_count"],
                "candidate_event_count": report["candidate_event_count"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
