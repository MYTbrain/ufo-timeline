"""Find GeoNames matches for long-tail structured unresolved locations.

This report-only lane scans the actual deduped event JSONL instead of the
top-N mapping coverage CSV. It targets explicit structured rows such as
``City, Admin, US`` and ``City, Admin, FRA, EU`` that are individually rare
but numerous in aggregate.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.summarize_city_country_geonames_mapping_candidates import (
    classify_candidates,
    dedupe_candidates,
    load_country_aliases,
    normalize_query,
)
from scripts.summarize_structured_city_alias_geonames_mapping_candidates import (
    US_ADMIN1_ALIASES,
    city_alias_variants,
    city_key,
    is_placeholder_city,
    normalized_city_keys,
    parse_admin1,
)


DEFAULT_INPUT = Path("data/canonical_preview_map_enrich_v25_residual_us_city_state/deduped_events.jsonl")
DEFAULT_GEONAMES_ZIP = Path("cache/map_overlays/allCountries.zip")
DEFAULT_COUNTRY_INFO = Path("cache/map_overlays/countryInfo.txt")
DEFAULT_OUTPUT_JSON = Path("data/reports/structured_long_tail_geonames_mapping_candidates_v26.json")
DEFAULT_OUTPUT_CSV = Path("data/reports/structured_long_tail_geonames_mapping_candidates_v26.csv")

LEGACY_REGION_CODES = {
    "AF",
    "AS",
    "AU",
    "CA",
    "EU",
    "EUR",
    "NA",
    "OC",
    "P",
    "SA",
}

REGION_ONLY_CITY_KEYS = {
    "england",
    "great britain",
    "northern ireland",
    "norrland",
    "scotland",
    "united kingdom",
    "wales",
}

US_STATE_CODES = set(US_ADMIN1_ALIASES.values())


def summarize_structured_long_tail_geonames_mapping_candidates(
    *,
    input_path: Path,
    geonames_zip: Path,
    country_info: Path,
    limit: int,
) -> dict[str, Any]:
    country_aliases = load_country_aliases(country_info)
    query_counter, source_counter = load_queries(input_path, country_aliases, limit)
    parsed_queries = list(query_counter.values())
    candidates_by_query: dict[str, list[dict[str, Any]]] = {query["query"]: [] for query in parsed_queries}
    query_lookup: dict[tuple[str, str, str], list[dict[str, Any]]] = {}

    for query in parsed_queries:
      for variant in query["city_variants"]:
        query_lookup.setdefault((query["country_code"], query["admin1"], variant), []).append(query)

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
                if not name_keys:
                    continue
                matching_queries: list[dict[str, Any]] = []
                for key in name_keys:
                    matching_queries.extend(query_lookup.get((country_code, admin1, key), []))
                    matching_queries.extend(query_lookup.get((country_code, "", key), []))
                if not matching_queries:
                    continue
                candidate = {
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
                for query in matching_queries:
                    candidates_by_query[query["query"]].append(candidate)

    resolved_rows: list[dict[str, Any]] = []
    rejected_counts: Counter[str] = Counter()
    rejected_sample: list[dict[str, Any]] = []
    for query in parsed_queries:
        candidates = sorted(
            dedupe_candidates(candidates_by_query.get(query["query"], [])),
            key=lambda item: (-int(item["population"]), item["name"], item["geoname_id"]),
        )
        decision, confidence = classify_query(query, candidates)
        if not confidence:
            rejected_counts[decision] += int(query["count"])
            if len(rejected_sample) < 100:
                rejected_sample.append(
                    {
                        "query": query["query"],
                        "count": int(query["count"]),
                        "decision": decision,
                        "candidate_count": len(candidates),
                        "parse_kind": query["parse_kind"],
                    }
                )
            continue
        best = candidates[0]
        resolved_rows.append(
            {
                "query": query["query"],
                "count": int(query["count"]),
                "confidence": confidence,
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
                "parse_kind": query["parse_kind"],
            }
        )

    resolved_rows.sort(key=lambda row: (-int(row["count"]), row["query"]))
    return {
        "schema_version": 1,
        "report_policy": "structured_long_tail_geonames_mapping_candidates_report_only",
        "canonical_outputs_mutated": False,
        "geocoding_performed": False,
        "geonames_streamed": True,
        "inputs": {
            "deduped_events": str(input_path),
            "geonames_zip": str(geonames_zip),
            "country_info": str(country_info),
            "limit": limit,
        },
        "query_count": len(parsed_queries),
        "resolved_query_count": len(resolved_rows),
        "high_or_medium_confidence_event_count": sum(int(row["count"]) for row in resolved_rows),
        "resolved_by_parse_kind": dict(Counter(row["parse_kind"] for row in resolved_rows)),
        "source_counts": dict(sorted(source_counter.items())),
        "rejected_event_counts": dict(sorted(rejected_counts.items())),
        "resolved_queries": resolved_rows,
        "rejected_queries_sample": rejected_sample,
        "notes": [
            "This scans long-tail unresolved event rows directly instead of the top mapping coverage buckets.",
            "US rows require explicit state/admin evidence.",
            "Non-US city/admin/country rows require admin match when admin can be parsed.",
            "City/country rows without admin are accepted only by conservative unique/dominant GeoNames classification.",
            "Legacy trailing region tokens such as EU are used only to find the preceding country token.",
            "No canonical event coordinates are changed by this report.",
        ],
    }


def load_queries(
    input_path: Path,
    country_aliases: dict[str, str],
    limit: int,
) -> tuple[dict[str, dict[str, Any]], Counter[str]]:
    queries: dict[str, dict[str, Any]] = {}
    source_counter: Counter[str] = Counter()
    with input_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            event = json.loads(line)
            if event.get("lat") is not None and event.get("lon") is not None:
                continue
            parsed = parse_location(event.get("location_raw"), country_aliases)
            if not parsed:
                continue
            query = parsed["query"]
            if query not in queries:
                if limit and len(queries) >= limit:
                    continue
                queries[query] = parsed
                queries[query]["count"] = 0
            queries[query]["count"] += 1
            source = str(event.get("source_name") or "unknown").strip().lower() or "unknown"
            source_counter[source] += 1
    return queries, source_counter


def parse_location(raw_location: Any, country_aliases: dict[str, str]) -> dict[str, Any] | None:
    query = normalize_query(raw_location or "")
    if not query:
        return None
    raw_parts = [part.strip() for part in query.split(",")]
    if len(raw_parts) < 2:
        return None
    parts = [part for part in raw_parts if part]
    if len(parts) < 2:
        return None
    city_raw = parts[0]
    if "/" in city_raw:
        return None
    country_index, country_code = resolve_country(parts, country_aliases)
    if country_index is None or not country_code:
        return None
    if (
        len(raw_parts) == 2
        and country_code != "US"
        and raw_parts[-1].strip().upper() in US_STATE_CODES
    ):
        return None
    if country_code == "US" and country_index < 2:
        return None
    admin_raw = parts[country_index - 1] if country_index >= 2 else ""
    admin1 = parse_admin1(admin_raw, country_code) if admin_raw else ""
    if country_code == "US" and not admin1:
        return None
    if admin_raw and not admin1 and country_index >= 2:
        return None
    if parenthetical_country_conflicts(city_raw, country_code, country_aliases):
        return None
    city_variants = city_alias_variants(city_raw)
    if not city_variants:
        return None
    city_name_key = city_key(city_raw)
    if len(city_name_key.replace(" ", "")) <= 3:
        return None
    if city_name_key in REGION_ONLY_CITY_KEYS:
        return None
    if any(is_placeholder_city(variant) for variant in city_variants):
        return None
    if city_name_key in country_alias_city_keys(country_aliases, country_code):
        return None
    return {
        "query": query,
        "city_variants": sorted(city_variants),
        "admin1": admin1,
        "country_code": country_code,
        "parse_kind": "city_admin_country" if admin1 else "city_country",
    }


def resolve_country(parts: list[str], country_aliases: dict[str, str]) -> tuple[int | None, str | None]:
    last = parts[-1]
    last_key = normalize_query(last)
    if last_key.upper() in LEGACY_REGION_CODES and len(parts) >= 3:
        previous_code = country_aliases.get(normalize_query(parts[-2]))
        if previous_code:
            return len(parts) - 2, previous_code
    country_code = country_aliases.get(last_key)
    if country_code:
        return len(parts) - 1, country_code
    return None, None


def parenthetical_country_conflicts(
    city_raw: str,
    country_code: str,
    country_aliases: dict[str, str],
) -> bool:
    hints = re.findall(r"\(([^)]*)\)", city_raw)
    for hint in hints:
        hinted_country = country_aliases.get(normalize_query(hint))
        if hinted_country and hinted_country != country_code:
            return True
    return False


def country_alias_city_keys(country_aliases: dict[str, str], country_code: str) -> set[str]:
    return {city_key(alias) for alias, code in country_aliases.items() if code == country_code}


def classify_query(query: dict[str, Any], candidates: list[dict[str, Any]]) -> tuple[str, str | None]:
    if not candidates:
        return "rejected_no_geonames_match", None
    if query["admin1"]:
        return "accepted_structured_long_tail_city_admin", "high"
    decision = classify_candidates(candidates)
    if decision == "accepted_unique_city_country":
        return "accepted_structured_long_tail_unique_city_country", "high"
    if decision == "accepted_dominant_city_country":
        return "accepted_structured_long_tail_dominant_city_country", "medium"
    return decision, None


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
        "parse_kind",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--geonames-zip", type=Path, default=DEFAULT_GEONAMES_ZIP)
    parser.add_argument("--country-info", type=Path, default=DEFAULT_COUNTRY_INFO)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = summarize_structured_long_tail_geonames_mapping_candidates(
        input_path=args.input,
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
