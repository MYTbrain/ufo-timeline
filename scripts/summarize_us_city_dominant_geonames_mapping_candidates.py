"""Find strict GeoNames matches for ambiguous ``City, US`` residual rows.

This report-only lane is intentionally conservative. It considers only residual
rows shaped like ``city, us`` and accepts a match only when the city is unique
among U.S. GeoNames populated places or the largest populated place is strongly
dominant. It does not use alternate names and does not mutate canonical data.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import zipfile
from pathlib import Path
from typing import Any

from scripts.summarize_city_country_geonames_mapping_candidates import (
    dedupe_candidates,
    primary_city_keys,
    normalize_query,
)
from scripts.summarize_structured_city_alias_geonames_mapping_candidates import (
    city_alias_variants,
    is_placeholder_city,
)


DEFAULT_MAPPING_CSV = Path("data/reports/mapping_coverage_opportunities_after_structured_primary_city_admin_quarantine_v10.csv")
DEFAULT_GEONAMES_ZIP = Path("cache/map_overlays/allCountries.zip")
DEFAULT_OUTPUT_JSON = Path("data/reports/us_city_dominant_geonames_mapping_candidates_after_structured_primary_city_admin_v11.json")
DEFAULT_OUTPUT_CSV = Path("data/reports/us_city_dominant_geonames_mapping_candidates_after_structured_primary_city_admin_v11.csv")

MIN_UNIQUE_CITY_POPULATION = 1_000
MIN_DOMINANT_CITY_POPULATION = 150_000
DOMINANT_CITY_POPULATION_RATIO = 10

US_STATE_NAME_TOKENS = {
    "alabama",
    "alaska",
    "arizona",
    "arkansas",
    "california",
    "colorado",
    "connecticut",
    "delaware",
    "florida",
    "georgia",
    "hawaii",
    "idaho",
    "illinois",
    "indiana",
    "iowa",
    "kansas",
    "kentucky",
    "louisiana",
    "maine",
    "maryland",
    "massachusetts",
    "michigan",
    "minnesota",
    "mississippi",
    "missouri",
    "montana",
    "nebraska",
    "nevada",
    "new hampshire",
    "new jersey",
    "new mexico",
    "new york",
    "north carolina",
    "north dakota",
    "ohio",
    "oklahoma",
    "oregon",
    "pennsylvania",
    "rhode island",
    "south carolina",
    "south dakota",
    "tennessee",
    "texas",
    "utah",
    "vermont",
    "virginia",
    "washington",
    "west virginia",
    "wisconsin",
    "wyoming",
}

DIRECTIONAL_PLACEHOLDER_TOKENS = {"n", "s", "e", "w", "north", "south", "east", "west"}

# These are common non-city references in UFO location text where a unique
# low-population GeoNames populated-place row is more likely to be misleading
# than useful without additional admin/location evidence.
UNSAFE_CITY_ONLY_TOKENS = {
    "lake tahoe",
    "yosemite",
}


def summarize_us_city_dominant_geonames_mapping_candidates(
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
                if len(parts) < 19 or parts[6] != "P" or parts[8].upper() != "US":
                    continue
                name_keys = primary_city_keys(parts[1], parts[2])
                if not wanted_keys.intersection(name_keys):
                    continue
                candidate = {
                    "geoname_id": parts[0],
                    "name": parts[1],
                    "lat": float(parts[4]),
                    "lon": float(parts[5]),
                    "country_code": "US",
                    "admin1": parts[10].upper(),
                    "feature_code": parts[7],
                    "population": int(parts[14] or 0),
                    "timezone": parts[17],
                }
                for query in parsed_queries:
                    if set(query["city_variants"]).intersection(name_keys):
                        candidates_by_query[query["query"]].append(candidate)

    resolved_rows: list[dict[str, Any]] = []
    rejected: dict[str, int] = {}
    rejected_sample: list[dict[str, Any]] = []
    for query in parsed_queries:
        count = int(query["count"])
        candidates = sorted(
            dedupe_candidates(candidates_by_query.get(query["query"], [])),
            key=lambda item: (-int(item["population"]), item["name"], item["geoname_id"]),
        )
        decision = classify_candidates(candidates)
        if decision not in {"accepted_unique_us_city", "accepted_dominant_us_city"}:
            rejected[decision] = rejected.get(decision, 0) + count
            if len(rejected_sample) < 100:
                rejected_sample.append(
                    {
                        "query": query["query"],
                        "count": count,
                        "decision": decision,
                        "candidate_count": len(candidates),
                        "top_candidates": "|".join(format_candidate(candidate) for candidate in candidates[:5]),
                    }
                )
            continue
        best = candidates[0]
        resolved_rows.append(
            {
                "query": query["query"],
                "count": count,
                "confidence": "high" if decision == "accepted_unique_us_city" else "medium",
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
                "decision": decision,
                "top_candidates": "|".join(format_candidate(candidate) for candidate in candidates[:5]),
            }
        )

    return {
        "schema_version": 1,
        "report_policy": "us_city_dominant_geonames_mapping_candidates_report_only",
        "canonical_outputs_mutated": False,
        "geocoding_performed": False,
        "geonames_streamed": True,
        "inputs": {
            "mapping_csv": str(mapping_csv),
            "geonames_zip": str(geonames_zip),
            "limit": limit,
        },
        "query_count": len(queries),
        "parseable_us_city_query_count": len(parsed_queries),
        "resolved_query_count": len(resolved_rows),
        "high_or_medium_confidence_event_count": sum(int(row["count"]) for row in resolved_rows),
        "rejected_event_counts": dict(sorted(rejected.items())),
        "resolved_queries": sorted(resolved_rows, key=lambda item: (-int(item["count"]), item["query"])),
        "rejected_queries_sample": rejected_sample,
        "notes": [
            "Only residual rows shaped exactly like City, US are considered.",
            "Matching uses GeoNames primary/ascii populated-place names only, not alternate names.",
            "Ambiguous U.S. city names are rejected unless the top populated place is at least 150k population and 10x the next candidate.",
            "This report does not mutate canonical data or preview sidecars.",
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
    if (row.get("bucket") or "") != "city_region_like":
        return None
    query = normalize_query(row.get("query") or "")
    parts = [part.strip() for part in query.split(",") if part.strip()]
    if len(parts) != 2 or parts[1] != "us":
        return None
    city_raw = clean_city(parts[0])
    if not city_raw or "/" in city_raw:
        return None
    city_variants = city_alias_variants(city_raw)
    if not city_variants or any(is_placeholder_city(variant) for variant in city_variants):
        return None
    if city_raw in {"us", "usa", "united states"}:
        return None
    if city_raw in DIRECTIONAL_PLACEHOLDER_TOKENS:
        return None
    if city_raw in US_STATE_NAME_TOKENS:
        return None
    if city_raw in UNSAFE_CITY_ONLY_TOKENS:
        return None
    return {
        "query": query,
        "city_variants": sorted(city_variants),
        "count": str(int(row.get("count") or 0)),
    }


def clean_city(value: str) -> str:
    text = normalize_query(value)
    text = re.sub(r"\s*\([^)]*\)\s*$", "", text).strip()
    text = re.sub(r"\?.*$", "", text).strip()
    return text


def classify_candidates(candidates: list[dict[str, Any]]) -> str:
    if not candidates:
        return "rejected_no_primary_us_city_match"
    if len(candidates) == 1:
        if int(candidates[0]["population"]) < MIN_UNIQUE_CITY_POPULATION:
            return "rejected_low_population_unique_us_city"
        return "accepted_unique_us_city"
    top_population = int(candidates[0]["population"])
    next_population = int(candidates[1]["population"])
    if top_population >= MIN_DOMINANT_CITY_POPULATION and (
        next_population == 0 or top_population >= next_population * DOMINANT_CITY_POPULATION_RATIO
    ):
        return "accepted_dominant_us_city"
    return "rejected_ambiguous_us_city"


def format_candidate(candidate: dict[str, Any]) -> str:
    return f"{candidate['name']} {candidate['admin1']} pop={candidate['population']}"


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
        "top_candidates",
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
    report = summarize_us_city_dominant_geonames_mapping_candidates(
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
                "high_or_medium_confidence_event_count": report["high_or_medium_confidence_event_count"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
