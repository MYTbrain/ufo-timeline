"""Match top unresolved location queries against cached GeoNames data.

This is a bounded, report-only probe. It streams the local GeoNames
allCountries.zip once and resolves only the top unresolved queries from the
mapping coverage report. It does not write coordinates into canonical events.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import zipfile
from pathlib import Path
from typing import Any


DEFAULT_MAPPING_CSV = Path("data/reports/mapping_coverage_opportunities.csv")
DEFAULT_GEONAMES_ZIP = Path("cache/map_overlays/allCountries.zip")
DEFAULT_OUTPUT_JSON = Path("data/reports/offline_geonames_mapping_candidates.json")
DEFAULT_OUTPUT_CSV = Path("data/reports/offline_geonames_mapping_candidates.csv")

COUNTRY_ALIASES = {
    "argentina": "AR",
    "au": "AU",
    "australia": "AU",
    "bangladesh": "BD",
    "br": "BR",
    "brazil": "BR",
    "ca": "CA",
    "canada": "CA",
    "chile": "CL",
    "cyprus": "CY",
    "de": "DE",
    "germany": "DE",
    "egypt": "EG",
    "es": "ES",
    "spain": "ES",
    "fr": "FR",
    "france": "FR",
    "gb": "GB",
    "great britain": "GB",
    "greece": "GR",
    "hungary": "HU",
    "india": "IN",
    "iran": "IR",
    "ireland": "IE",
    "uk": "GB",
    "united kingdom": "GB",
    "it": "IT",
    "italy": "IT",
    "malaysia": "MY",
    "mx": "MX",
    "mexico": "MX",
    "new zealand": "NZ",
    "pakistan": "PK",
    "south africa": "ZA",
    "us": "US",
    "usa": "US",
    "united states": "US",
    "venezuela": "VE",
}

ADMIN1_ALIASES_BY_COUNTRY = {
    "AU": {
        "ACT": "01",
        "NEW SOUTH WALES": "02",
        "NSW": "02",
        "NORTHERN TERRITORY": "03",
        "NT": "03",
        "QUEENSLAND": "04",
        "QLD": "04",
        "SOUTH AUSTRALIA": "05",
        "SA": "05",
        "TAS": "06",
        "TASMANIA": "06",
        "VIC": "07",
        "VICTORIA": "07",
        "WA": "08",
        "WESTERN AUSTRALIA": "08",
    },
    "CA": {
        "AB": "01",
        "BC": "02",
        "MB": "03",
        "NB": "04",
        "NL": "05",
        "NS": "07",
        "ON": "08",
        "PE": "09",
        "QC": "10",
        "SK": "11",
        "YT": "12",
        "NT": "13",
        "NU": "14",
    },
    "GB": {
        "ENGLAND": "ENG",
        "ENG": "ENG",
        "NORTHERN IRELAND": "NIR",
        "NIR": "NIR",
        "SCOTLAND": "SCT",
        "SCT": "SCT",
        "WALES": "WLS",
        "WLS": "WLS",
    },
}


def summarize_offline_geonames_mapping_candidates(
    *,
    mapping_csv: Path,
    geonames_zip: Path,
    limit: int,
) -> dict[str, Any]:
    queries = load_queries(mapping_csv, limit)
    parsed_queries = [query for query in (parse_query(row) for row in queries) if query]
    wanted_names = {query["city"] for query in parsed_queries}
    candidates_by_query: dict[str, list[dict[str, Any]]] = {query["query"]: [] for query in parsed_queries}

    with zipfile.ZipFile(geonames_zip) as archive:
        with archive.open("allCountries.txt") as raw:
            for raw_line in raw:
                line = raw_line.decode("utf-8", errors="replace").rstrip("\n")
                parts = line.split("\t")
                if len(parts) < 19:
                    continue
                feature_class = parts[6]
                if feature_class != "P":
                    continue
                name_values = normalized_names(parts[1], parts[2], parts[3])
                if not wanted_names.intersection(name_values):
                    continue
                country_code = parts[8].upper()
                admin1 = parts[10].upper()
                for query in parsed_queries:
                    if query["city"] not in name_values:
                        continue
                    if query["country_code"] and query["country_code"] != country_code:
                        continue
                    if query["admin1"] and query["admin1"] != admin1:
                        continue
                    candidates_by_query[query["query"]].append(
                        {
                            "geoname_id": parts[0],
                            "name": parts[1],
                            "ascii_name": parts[2],
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
    resolved_event_count = 0
    for query in parsed_queries:
        candidates = sorted(
            candidates_by_query.get(query["query"], []),
            key=lambda item: (-int(item["population"]), item["name"]),
        )
        if not candidates:
            continue
        confidence = classify_confidence(query, candidates)
        best = candidates[0]
        count = int(query["count"])
        resolved_event_count += count if confidence in {"high", "medium"} else 0
        resolved_rows.append(
            {
                "query": query["query"],
                "count": count,
                "confidence": confidence,
                "candidate_count": len(candidates),
                "name": best["name"],
                "lat": best["lat"],
                "lon": best["lon"],
                "country_code": best["country_code"],
                "admin1": best["admin1"],
                "population": best["population"],
                "timezone": best["timezone"],
            }
        )

    return {
        "schema_version": 1,
        "report_policy": "offline_geonames_mapping_candidates_report_only",
        "canonical_outputs_mutated": False,
        "geocoding_performed": False,
        "geonames_streamed": True,
        "inputs": {
            "mapping_csv": str(mapping_csv),
            "geonames_zip": str(geonames_zip),
            "limit": limit,
        },
        "query_count": len(queries),
        "parseable_query_count": len(parsed_queries),
        "resolved_query_count": len(resolved_rows),
        "high_or_medium_confidence_event_count": resolved_event_count,
        "resolved_queries": resolved_rows,
        "notes": [
            "This report only matches top unresolved query strings to local GeoNames populated places.",
            "Rows with city plus admin1/country receive high confidence; city plus unique country match receives medium confidence.",
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


def parse_query(row: dict[str, str]) -> dict[str, str] | None:
    query = normalize(row.get("query") or "")
    if not query:
        return None
    parts = split_location_parts(query)
    if len(parts) < 2:
        return None
    country_code = COUNTRY_ALIASES.get(parts[-1])
    if not country_code:
        return None
    city = normalize_city_name(parts[0])
    if len(city) <= 2:
        return None
    admin1 = ""
    if len(parts) >= 3 and re.fullmatch(r"[a-z]{2}", parts[-2]):
        raw_admin1 = parts[-2].upper()
        admin1 = ADMIN1_ALIASES_BY_COUNTRY.get(country_code, {}).get(raw_admin1, raw_admin1)
    if not admin1:
        admin1 = parse_parenthetical_admin1(parts[0], country_code)
    return {
        "query": query,
        "city": city,
        "admin1": admin1,
        "country_code": country_code,
        "count": str(int(row.get("count") or 0)),
        "has_parenthetical_location_context": has_parenthetical_location_context(parts[0], country_code),
    }


def split_location_parts(query: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for character in query:
        if character == "(":
            depth += 1
        elif character == ")" and depth:
            depth -= 1
        if character == "," and depth == 0:
            part = "".join(current).strip()
            if part:
                parts.append(part)
            current = []
            continue
        current.append(character)
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def parse_parenthetical_admin1(city_value: str, country_code: str) -> str:
    match = re.search(r"\(([^)]*)\)\s*$", normalize(city_value))
    if not match:
        return ""
    aliases = ADMIN1_ALIASES_BY_COUNTRY.get(country_code, {})
    for token in re.split(r"[,/]", match.group(1)):
        normalized_token = normalize(token).upper()
        admin1 = aliases.get(normalized_token)
        if admin1:
            return admin1
    return ""


def has_parenthetical_location_context(city_value: str, country_code: str) -> bool:
    match = re.search(r"\(([^)]*)\)\s*$", normalize(city_value))
    if not match:
        return False
    aliases = ADMIN1_ALIASES_BY_COUNTRY.get(country_code, {})
    for token in re.split(r"[,/]", match.group(1)):
        normalized_token = normalize(token)
        if COUNTRY_ALIASES.get(normalized_token) == country_code:
            return True
        if aliases.get(normalized_token.upper()):
            return True
    return False


def normalized_names(name: str, ascii_name: str, alternate_names: str) -> set[str]:
    values = {normalize(name), normalize(ascii_name)}
    for alternate in alternate_names.split(","):
        normalized = normalize(alternate)
        if normalized:
            values.add(normalized)
    values.discard("")
    return values


def normalize(value: str) -> str:
    value = value.replace("\\,", ",")
    value = re.sub(r"\s+", " ", value.lower())
    value = re.sub(r"\s*,\s*", ", ", value)
    return value.strip(" ,")


def normalize_city_name(value: str) -> str:
    text = normalize(value)
    text = re.sub(r"\s*\([^)]*\)\s*$", "", text).strip()
    return text


def classify_confidence(query: dict[str, str], candidates: list[dict[str, Any]]) -> str:
    if int(candidates[0]["population"]) <= 0 and len(candidates) > 1:
        return "low"
    if query["admin1"]:
        return "high"
    if len(candidates) == 1:
        return "medium"
    if query.get("has_parenthetical_location_context") and has_dominant_populated_place(candidates):
        return "medium"
    return "low"


def has_dominant_populated_place(candidates: list[dict[str, Any]]) -> bool:
    if len(candidates) < 2:
        return False
    top_population = int(candidates[0]["population"])
    next_population = int(candidates[1]["population"])
    return top_population >= 100_000 and (next_population == 0 or top_population >= next_population * 20)


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
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = summarize_offline_geonames_mapping_candidates(
        mapping_csv=args.mapping_csv,
        geonames_zip=args.geonames_zip,
        limit=args.limit,
    )
    report["outputs"] = {"json": str(args.output_json), "csv": str(args.output_csv)}
    write_json(args.output_json, report)
    write_csv(args.output_csv, report["resolved_queries"])
    print(json.dumps({
        "json": str(args.output_json),
        "csv": str(args.output_csv),
        "resolved_query_count": report["resolved_query_count"],
        "high_or_medium_confidence_event_count": report["high_or_medium_confidence_event_count"],
        "canonical_outputs_mutated": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
