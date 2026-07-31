"""Find GeoNames matches for two-part US city/state rows.

This report-only lane targets residual rows shaped like ``Chicago, IL`` or
``Oak Ridge, TN``. It requires explicit US state evidence and matches only
GeoNames populated-place primary/ascii names in that state.
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
    clean_city,
    dedupe_candidates,
    normalize_query,
    primary_city_keys,
)
from scripts.summarize_structured_city_alias_geonames_mapping_candidates import (
    US_ADMIN1_ALIASES,
    city_alias_variants,
    is_placeholder_city,
)


DEFAULT_MAPPING_CSV = Path("data/reports/mapping_coverage_opportunities_after_updb_location_id_v12.csv")
DEFAULT_GEONAMES_ZIP = Path("cache/map_overlays/allCountries.zip")
DEFAULT_OUTPUT_JSON = Path("data/reports/two_part_us_city_state_geonames_mapping_candidates_after_updb_location_id_v14.json")
DEFAULT_OUTPUT_CSV = Path("data/reports/two_part_us_city_state_geonames_mapping_candidates_after_updb_location_id_v14.csv")

STATE_ALIASES = {**US_ADMIN1_ALIASES, **{code: code for code in US_ADMIN1_ALIASES.values()}}
STATE_NAMES = {normalize_query(name) for name in US_ADMIN1_ALIASES if len(name) > 2}


def summarize_two_part_us_city_state_geonames_mapping_candidates(
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
                admin1 = parts[10].upper()
                name_keys = primary_city_keys(parts[1], parts[2])
                if not wanted_keys.intersection(name_keys):
                    continue
                for query in parsed_queries:
                    if query["admin1"] != admin1:
                        continue
                    if not set(query["city_variants"]).intersection(name_keys):
                        continue
                    candidates_by_query[query["query"]].append(
                        {
                            "geoname_id": parts[0],
                            "name": parts[1],
                            "lat": float(parts[4]),
                            "lon": float(parts[5]),
                            "country_code": "US",
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
        if decision not in {"accepted_unique_us_city_state", "accepted_dominant_us_city_state"}:
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
                "confidence": "high" if decision == "accepted_unique_us_city_state" else "medium",
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
        "report_policy": "two_part_us_city_state_geonames_mapping_candidates_report_only",
        "canonical_outputs_mutated": False,
        "geocoding_performed": False,
        "geonames_streamed": True,
        "inputs": {
            "mapping_csv": str(mapping_csv),
            "geonames_zip": str(geonames_zip),
            "limit": limit,
        },
        "query_count": len(queries),
        "parseable_two_part_us_city_state_query_count": len(parsed_queries),
        "resolved_query_count": len(resolved_rows),
        "high_or_medium_confidence_event_count": sum(int(row["count"]) for row in resolved_rows),
        "rejected_event_counts": dict(sorted(rejected.items())),
        "resolved_queries": sorted(resolved_rows, key=lambda item: (-int(item["count"]), item["query"])),
        "rejected_queries_sample": rejected_sample,
        "notes": [
            "Only two-part US city/state residual rows are considered.",
            "City text that is itself a US state name, placeholder text, or slash-composite text is ignored.",
            "Matching uses GeoNames primary/ascii populated-place names only, not alternate names.",
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
    bucket = row.get("bucket") or ""
    if bucket not in {"city_region_like", "city_state_like"}:
        return None
    query = normalize_query(row.get("query") or "")
    if not query:
        return None
    parts = [part.strip() for part in query.split(",") if part.strip()]
    if len(parts) == 1 and bucket == "city_state_like":
        parts = parse_compact_city_state(parts[0])
    if len(parts) != 2:
        return None
    city_raw, state_raw = parts
    if "/" in city_raw or "/" in state_raw:
        return None
    if has_non_us_parenthetical_hint(city_raw):
        return None
    admin1 = parse_state(state_raw)
    if not admin1:
        return None
    city = clean_city(city_raw)
    if city in STATE_NAMES and not (admin1 == "DC" and city == "washington"):
        return None
    city_variants = city_alias_variants(city)
    if not city_variants:
        return None
    if any(is_placeholder_city(variant) for variant in city_variants):
        return None
    if re.fullmatch(r"[a-z]{1,3}", city):
        return None
    return {
        "query": query,
        "city_variants": sorted(city_variants),
        "admin1": admin1,
        "count": str(int(row.get("count") or 0)),
    }


def parse_compact_city_state(value: str) -> list[str]:
    match = re.fullmatch(r"(.+?)\s+(d\.?c\.?|dc)", value)
    if not match:
        return [value]
    return [match.group(1), match.group(2)]


def has_non_us_parenthetical_hint(value: str) -> bool:
    hints = re.findall(r"\(([^)]*)\)", value)
    if not hints:
        return False
    allowed = {"us", "usa", "u.s.", "u.s.a.", "united states", "united states of america"}
    return any(normalize_query(hint) not in allowed for hint in hints)


def parse_state(value: str) -> str:
    normalized = normalize_query(value).upper()
    normalized_no_period = normalized.replace(".", "")
    return STATE_ALIASES.get(normalized) or STATE_ALIASES.get(normalized_no_period) or ""


def classify_candidates(candidates: list[dict[str, Any]]) -> str:
    if not candidates:
        return "rejected_no_primary_us_city_state_match"
    if len(candidates) == 1:
        return "accepted_unique_us_city_state"
    top_population = int(candidates[0]["population"])
    next_population = int(candidates[1]["population"])
    if top_population >= 10_000 and (next_population == 0 or top_population >= next_population * 20):
        return "accepted_dominant_us_city_state"
    return "rejected_ambiguous_us_city_state"


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
    report = summarize_two_part_us_city_state_geonames_mapping_candidates(
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
