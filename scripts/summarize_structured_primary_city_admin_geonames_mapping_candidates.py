"""Find strict GeoNames matches for explicit city/admin/country rows.

This report-only lane is intentionally stricter than the broad offline
GeoNames probe: it requires explicit admin/state evidence and matches only
GeoNames primary/ascii populated-place names, not alternate names.
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
    load_country_aliases,
    normalize_query,
    primary_city_keys,
)
from scripts.summarize_structured_city_alias_geonames_mapping_candidates import (
    ADMIN1_ALIASES,
    US_ADMIN1_ALIASES,
    city_alias_variants,
    is_placeholder_city,
)


DEFAULT_MAPPING_CSV = Path("data/reports/mapping_coverage_opportunities_after_city_country_quarantine_v9.csv")
DEFAULT_GEONAMES_ZIP = Path("cache/map_overlays/allCountries.zip")
DEFAULT_COUNTRY_INFO = Path("cache/map_overlays/countryInfo.txt")
DEFAULT_OUTPUT_JSON = Path("data/reports/structured_primary_city_admin_geonames_mapping_candidates_after_city_country_v10.json")
DEFAULT_OUTPUT_CSV = Path("data/reports/structured_primary_city_admin_geonames_mapping_candidates_after_city_country_v10.csv")

ADMIN_ALIASES = {
    **ADMIN1_ALIASES,
    "US": {**US_ADMIN1_ALIASES, **{code: code for code in US_ADMIN1_ALIASES.values()}},
}


def summarize_structured_primary_city_admin_geonames_mapping_candidates(
    *,
    mapping_csv: Path,
    geonames_zip: Path,
    country_info: Path,
    limit: int,
) -> dict[str, Any]:
    country_aliases = load_country_aliases(country_info)
    queries = load_queries(mapping_csv, limit)
    parsed_queries = [query for query in (parse_query(row, country_aliases) for row in queries) if query]
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
                name_keys = primary_city_keys(parts[1], parts[2])
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
    rejected: dict[str, int] = {}
    rejected_sample: list[dict[str, Any]] = []
    for query in parsed_queries:
        count = int(query["count"])
        candidates = sorted(
            dedupe_candidates(candidates_by_query.get(query["query"], [])),
            key=lambda item: (-int(item["population"]), item["name"], item["geoname_id"]),
        )
        decision = classify_candidates(candidates)
        if decision not in {"accepted_unique_primary_city_admin", "accepted_dominant_primary_city_admin"}:
            rejected[decision] = rejected.get(decision, 0) + count
            if len(rejected_sample) < 100:
                rejected_sample.append(
                    {
                        "query": query["query"],
                        "count": count,
                        "decision": decision,
                        "candidate_count": len(candidates),
                        "city_variants": "|".join(query["city_variants"]),
                    }
                )
            continue
        best = candidates[0]
        resolved_rows.append(
            {
                "query": query["query"],
                "count": count,
                "confidence": "high" if decision == "accepted_unique_primary_city_admin" else "medium",
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
            }
        )

    return {
        "schema_version": 1,
        "report_policy": "structured_primary_city_admin_geonames_mapping_candidates_report_only",
        "canonical_outputs_mutated": False,
        "geocoding_performed": False,
        "geonames_streamed": True,
        "inputs": {
            "mapping_csv": str(mapping_csv),
            "geonames_zip": str(geonames_zip),
            "country_info": str(country_info),
            "limit": limit,
        },
        "query_count": len(queries),
        "parseable_structured_query_count": len(parsed_queries),
        "resolved_query_count": len(resolved_rows),
        "high_or_medium_confidence_event_count": sum(int(row["count"]) for row in resolved_rows),
        "rejected_event_counts": dict(sorted(rejected.items())),
        "resolved_queries": sorted(resolved_rows, key=lambda item: (-int(item["count"]), item["query"])),
        "rejected_queries_sample": rejected_sample,
        "notes": [
            "Only explicit city/admin/country residual rows are considered.",
            "Admin evidence must resolve through known state/province aliases.",
            "Matching uses GeoNames primary/ascii populated-place names only, not alternate names.",
            "Country-only, region-only, placeholder, and missing-admin rows are ignored.",
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


def parse_query(row: dict[str, str], country_aliases: dict[str, str]) -> dict[str, Any] | None:
    if (row.get("bucket") or "") != "city_state_country_like":
        return None
    query = normalize_query(row.get("query") or "")
    if not query:
        return None
    parts = [part.strip() for part in query.split(",") if part.strip()]
    if len(parts) < 3:
        return None
    country_code = country_aliases.get(parts[-1])
    if not country_code:
        return None
    admin1 = parse_admin1(parts[-2], country_code)
    if not admin1:
        return None
    city_variants = city_alias_variants(clean_city(parts[0]))
    if not city_variants:
        return None
    if any(is_placeholder_city(variant) for variant in city_variants):
        return None
    if "/" in parts[0]:
        return None
    return {
        "query": query,
        "city_variants": sorted(city_variants),
        "admin1": admin1,
        "country_code": country_code,
        "count": str(int(row.get("count") or 0)),
    }


def parse_admin1(value: str, country_code: str) -> str:
    normalized = normalize_query(value).upper()
    normalized_no_period = normalized.replace(".", "")
    aliases = ADMIN_ALIASES.get(country_code, {})
    return aliases.get(normalized) or aliases.get(normalized_no_period) or ""


def clean_city(value: str) -> str:
    text = normalize_query(value)
    text = re.sub(r"\s*\([^)]*\)\s*$", "", text).strip()
    text = re.sub(r"\?.*$", "", text).strip()
    return text


def dedupe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        geoname_id = str(candidate["geoname_id"])
        if geoname_id in seen:
            continue
        seen.add(geoname_id)
        deduped.append(candidate)
    return deduped


def classify_candidates(candidates: list[dict[str, Any]]) -> str:
    if not candidates:
        return "rejected_no_primary_city_admin_match"
    if len(candidates) == 1:
        return "accepted_unique_primary_city_admin"
    top_population = int(candidates[0]["population"])
    next_population = int(candidates[1]["population"])
    if top_population >= 10_000 and (next_population == 0 or top_population >= next_population * 20):
        return "accepted_dominant_primary_city_admin"
    return "rejected_ambiguous_primary_city_admin"


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
    parser.add_argument("--country-info", type=Path, default=DEFAULT_COUNTRY_INFO)
    parser.add_argument("--limit", type=int, default=20000)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = summarize_structured_primary_city_admin_geonames_mapping_candidates(
        mapping_csv=args.mapping_csv,
        geonames_zip=args.geonames_zip,
        country_info=args.country_info,
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
