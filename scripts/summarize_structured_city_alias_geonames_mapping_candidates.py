"""Find GeoNames matches for structured city/admin/country rows with common aliases.

This report-only lane targets rows that already contain explicit admin-region
and country evidence, but missed earlier GeoNames passes because the city text
uses common abbreviations or punctuation such as ``Ft.``, ``St.``, ``Mt.``, or
``D.C.``. It deliberately ignores city/country-only rows.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
import zipfile
from pathlib import Path
from typing import Any

from scripts.summarize_offline_geonames_mapping_candidates import (
    ADMIN1_ALIASES_BY_COUNTRY,
    COUNTRY_ALIASES,
    normalize,
    split_location_parts,
)


DEFAULT_MAPPING_CSV = Path("data/reports/mapping_coverage_opportunities_after_body_city_state_quarantine_v6.csv")
DEFAULT_GEONAMES_ZIP = Path("cache/map_overlays/allCountries.zip")
DEFAULT_OUTPUT_JSON = Path("data/reports/structured_city_alias_geonames_mapping_candidates_after_body_city_state_v7.json")
DEFAULT_OUTPUT_CSV = Path("data/reports/structured_city_alias_geonames_mapping_candidates_after_body_city_state_v7.csv")

US_ADMIN1_ALIASES = {
    "ALABAMA": "AL",
    "ALASKA": "AK",
    "ARIZONA": "AZ",
    "ARKANSAS": "AR",
    "CALIFORNIA": "CA",
    "COLORADO": "CO",
    "CONNECTICUT": "CT",
    "DELAWARE": "DE",
    "DISTRICT OF COLUMBIA": "DC",
    "D C": "DC",
    "D.C.": "DC",
    "DC": "DC",
    "FLORIDA": "FL",
    "GEORGIA": "GA",
    "HAWAII": "HI",
    "IDAHO": "ID",
    "ILLINOIS": "IL",
    "INDIANA": "IN",
    "IOWA": "IA",
    "KANSAS": "KS",
    "KENTUCKY": "KY",
    "LOUISIANA": "LA",
    "MAINE": "ME",
    "MARYLAND": "MD",
    "MASSACHUSETTS": "MA",
    "MICHIGAN": "MI",
    "MINNESOTA": "MN",
    "MISSISSIPPI": "MS",
    "MISSOURI": "MO",
    "MONTANA": "MT",
    "NEBRASKA": "NE",
    "NEVADA": "NV",
    "NEW HAMPSHIRE": "NH",
    "NEW JERSEY": "NJ",
    "NEW MEXICO": "NM",
    "NEW YORK": "NY",
    "NORTH CAROLINA": "NC",
    "NORTH DAKOTA": "ND",
    "OHIO": "OH",
    "OKLAHOMA": "OK",
    "OREGON": "OR",
    "PENNSYLVANIA": "PA",
    "RHODE ISLAND": "RI",
    "SOUTH CAROLINA": "SC",
    "SOUTH DAKOTA": "SD",
    "TENNESSEE": "TN",
    "TEXAS": "TX",
    "UTAH": "UT",
    "VERMONT": "VT",
    "VIRGINIA": "VA",
    "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV",
    "WISCONSIN": "WI",
    "WYOMING": "WY",
}

ADMIN1_ALIASES = {
    **ADMIN1_ALIASES_BY_COUNTRY,
    "US": {**US_ADMIN1_ALIASES, **{code: code for code in US_ADMIN1_ALIASES.values()}},
}


def summarize_structured_city_alias_geonames_mapping_candidates(
    *,
    mapping_csv: Path,
    geonames_zip: Path,
    limit: int,
) -> dict[str, Any]:
    queries = load_queries(mapping_csv, limit)
    parsed_queries = [query for query in (parse_query(row) for row in queries) if query]
    wanted_keys = {variant for query in parsed_queries for variant in query["city_variants"]}
    candidates_by_query: dict[str, list[dict[str, Any]]] = {query["query"]: [] for query in parsed_queries}

    with zipfile.ZipFile(geonames_zip) as archive:
        with archive.open("allCountries.txt") as raw:
            for raw_line in raw:
                line = raw_line.decode("utf-8", errors="replace").rstrip("\n")
                parts = line.split("\t")
                if len(parts) < 19 or parts[6] != "P":
                    continue
                country_code = parts[8].upper()
                admin1 = parts[10].upper()
                name_keys = normalized_city_keys(parts[1], parts[2], parts[3])
                if not wanted_keys.intersection(name_keys):
                    continue
                for query in parsed_queries:
                    if query["country_code"] != country_code or query["admin1"] != admin1:
                        continue
                    if not set(query["city_variants"]).intersection(name_keys):
                        continue
                    candidates_by_query[query["query"]].append(
                        {
                            "geoname_id": parts[0],
                            "name": parts[1],
                            "lat": float(parts[4]),
                            "lon": float(parts[5]),
                            "country_code": country_code,
                            "admin1": admin1,
                            "feature_code": parts[7],
                            "population": int(parts[14] or 0),
                            "timezone": parts[17],
                        }
                    )

    resolved_rows: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []
    resolved_event_count = 0
    for query in parsed_queries:
        candidates = sorted(
            candidates_by_query.get(query["query"], []),
            key=lambda item: (-int(item["population"]), item["name"], item["geoname_id"]),
        )
        if not candidates:
            rejected_rows.append(
                {
                    "query": query["query"],
                    "count": int(query["count"]),
                    "decision": "rejected_no_alias_match",
                    "city_variants": "|".join(query["city_variants"]),
                }
            )
            continue
        best = candidates[0]
        row = {
            "query": query["query"],
            "count": int(query["count"]),
            "confidence": "high",
            "candidate_count": len(candidates),
            "name": best["name"],
            "lat": best["lat"],
            "lon": best["lon"],
            "country_code": best["country_code"],
            "admin1": best["admin1"],
            "population": best["population"],
            "timezone": best["timezone"],
            "location_precision": "city",
            "matched_city_variants": "|".join(query["city_variants"]),
            "decision": "accepted_structured_city_alias",
        }
        resolved_rows.append(row)
        resolved_event_count += int(query["count"])

    return {
        "schema_version": 1,
        "report_policy": "structured_city_alias_geonames_mapping_candidates_report_only",
        "canonical_outputs_mutated": False,
        "geocoding_performed": False,
        "geonames_streamed": True,
        "inputs": {
            "mapping_csv": str(mapping_csv),
            "geonames_zip": str(geonames_zip),
            "limit": limit,
        },
        "query_count": len(queries),
        "parseable_structured_query_count": len(parsed_queries),
        "resolved_query_count": len(resolved_rows),
        "high_confidence_event_count": resolved_event_count,
        "resolved_queries": resolved_rows,
        "rejected_queries_sample": rejected_rows[:100],
        "notes": [
            "Only rows with explicit city, admin-region, and country evidence are considered.",
            "Common city aliases are normalized for matching, but country/admin-region still must match exactly.",
            "No city/country-only or country-only rows are considered.",
            "No canonical event coordinates are changed by this report.",
        ],
    }


def load_queries(path: Path, limit: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if len(rows) >= limit:
                break
            rows.append(row)
    return rows


def parse_query(row: dict[str, str]) -> dict[str, Any] | None:
    query = normalize(row.get("query") or "")
    if not query:
        return None
    parts = split_location_parts(query)
    if len(parts) < 3:
        return None
    country_code = COUNTRY_ALIASES.get(parts[-1])
    if not country_code:
        return None
    admin1 = parse_admin1(parts[-2], country_code)
    if not admin1:
        return None
    city_variants = city_alias_variants(parts[0])
    if not city_variants:
        return None
    if any(is_placeholder_city(variant) for variant in city_variants):
        return None
    return {
        "query": query,
        "city_variants": sorted(city_variants),
        "admin1": admin1,
        "country_code": country_code,
        "count": str(int(row.get("count") or 0)),
    }


def parse_admin1(value: str, country_code: str) -> str:
    normalized = normalize(value).upper()
    normalized_no_period = normalized.replace(".", "")
    aliases = ADMIN1_ALIASES.get(country_code, {})
    return aliases.get(normalized) or aliases.get(normalized_no_period) or ""


def city_alias_variants(value: str) -> set[str]:
    text = normalize(value)
    text = re.sub(r"\s*\([^)]*\)\s*$", "", text).strip()
    if not text:
        return set()
    variants = {city_key(text)}
    expanded = city_key(text.replace(".", " "))
    variants.add(expanded)
    variants.add(expand_directional_abbreviations(expanded))
    variants.add(expand_place_abbreviations(expanded))
    variants.add(expand_place_abbreviations(expand_directional_abbreviations(expanded)))
    return {variant for variant in variants if variant}


def normalized_city_keys(name: str, ascii_name: str, alternate_names: str) -> set[str]:
    keys = set()
    for value in [name, ascii_name, *alternate_names.split(",")]:
        key = city_key(value)
        if key:
            keys.add(key)
            keys.add(expand_place_abbreviations(key))
    keys.discard("")
    return keys


def city_key(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = "".join(character for character in text if not unicodedata.combining(character))
    text = text.lower().replace("\\,", ",")
    text = text.replace("&", " and ")
    text = re.sub(r"[.'`´’]", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def expand_place_abbreviations(value: str) -> str:
    replacements = {
        "ft": "fort",
        "mt": "mount",
        "st": "saint",
        "ste": "sainte",
    }
    parts = [replacements.get(part, part) for part in value.split()]
    return " ".join(parts)


def expand_directional_abbreviations(value: str) -> str:
    replacements = {
        "n": "north",
        "s": "south",
        "e": "east",
        "w": "west",
    }
    parts = [replacements.get(part, part) for part in value.split()]
    return " ".join(parts)


def is_placeholder_city(value: str) -> bool:
    return value in {"0", "-", "unk", "unknown", "data missing", "undisclosed location"}


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
        "population",
        "timezone",
        "location_precision",
        "matched_city_variants",
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
    parser.add_argument("--geonames-zip", type=Path, default=DEFAULT_GEONAMES_ZIP)
    parser.add_argument("--limit", type=int, default=20000)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = summarize_structured_city_alias_geonames_mapping_candidates(
        mapping_csv=args.mapping_csv,
        geonames_zip=args.geonames_zip,
        limit=args.limit,
    )
    report["outputs"] = {"json": str(args.output_json), "csv": str(args.output_csv)}
    write_json(args.output_json, report)
    write_csv(args.output_csv, report["resolved_queries"])
    print(
        json.dumps(
            {
                "json": str(args.output_json),
                "csv": str(args.output_csv),
                "resolved_query_count": report["resolved_query_count"],
                "high_confidence_event_count": report["high_confidence_event_count"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
