"""Summarize conservative mapping coverage opportunities for canonical events.

This is a report-only diagnostic. It does not geocode, mutate coordinates, or
rewrite canonical artifacts. The goal is to identify high-volume unresolved
location text buckets that are worth an offline geocoding/enrichment pass.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("data/canonical_preview_remaining_lower_time_format_apply/deduped_events.jsonl")
DEFAULT_GEOCODE_CACHE = Path("cache/geocode_cache.jsonl")
DEFAULT_OUTPUT_JSON = Path("data/reports/mapping_coverage_opportunities.json")
DEFAULT_OUTPUT_CSV = Path("data/reports/mapping_coverage_opportunities.csv")

COUNTRY_ONLY_TERMS = {
    "argentina",
    "australia",
    "brazil",
    "canada",
    "china",
    "england",
    "france",
    "germany",
    "india",
    "italy",
    "japan",
    "mexico",
    "norway",
    "russia",
    "spain",
    "sweden",
    "uk",
    "united kingdom",
    "united states",
    "us",
    "usa",
}


def summarize_mapping_coverage_opportunities(
    input_path: Path,
    geocode_cache_path: Path | None = DEFAULT_GEOCODE_CACHE,
    *,
    top_queries_limit: int = 250,
) -> dict[str, Any]:
    geocode_cache = load_geocode_cache(geocode_cache_path) if geocode_cache_path else {}
    totals = {
        "events": 0,
        "mapped": 0,
        "unresolved": 0,
        "unresolved_with_location_text": 0,
        "unresolved_without_location_text": 0,
        "unresolved_with_cached_geocode": 0,
    }
    by_source: dict[str, dict[str, int]] = {}
    by_bucket: dict[str, int] = {}
    by_query: dict[str, dict[str, Any]] = {}

    for event in iter_jsonl(input_path):
        totals["events"] += 1
        source = clean_text(event.get("source_name")) or "unknown"
        source_counts = by_source.setdefault(source, {"events": 0, "mapped": 0, "unresolved": 0, "with_location_text": 0})
        source_counts["events"] += 1

        lat = parse_float(event.get("lat"))
        lon = parse_float(event.get("lon"))
        mapped = lat is not None and lon is not None
        if mapped:
            totals["mapped"] += 1
            source_counts["mapped"] += 1
            continue

        totals["unresolved"] += 1
        source_counts["unresolved"] += 1
        location_text = best_location_text(event)
        if not location_text:
            totals["unresolved_without_location_text"] += 1
            by_bucket["missing_location_text"] = by_bucket.get("missing_location_text", 0) + 1
            continue

        totals["unresolved_with_location_text"] += 1
        source_counts["with_location_text"] += 1
        bucket = classify_location_text(location_text)
        by_bucket[bucket] = by_bucket.get(bucket, 0) + 1
        query_key = normalize_query(location_text)
        cached_geocode = geocode_cache.get(query_key)
        if cached_geocode:
            totals["unresolved_with_cached_geocode"] += 1
        entry = by_query.setdefault(
            query_key,
            {
                "query": query_key,
                "count": 0,
                "cached_geocode_count": 0,
                "bucket": bucket,
                "sources": {},
                "sample_location_raw": clean_text(event.get("location_raw")),
                "sample_event_id": clean_text(event.get("canonical_event_id")),
                "earliest_sort_date": clean_text(event.get("sort_date_iso")),
                "latest_sort_date": clean_text(event.get("sort_date_iso")),
            },
        )
        entry["count"] += 1
        if cached_geocode:
            entry["cached_geocode_count"] += 1
            entry["cached_geocode_display_name"] = cached_geocode.get("display_name")
            entry["cached_geocode_confidence"] = cached_geocode.get("confidence")
        entry["sources"][source] = entry["sources"].get(source, 0) + 1
        sort_date = clean_text(event.get("sort_date_iso"))
        if sort_date:
            if not entry["earliest_sort_date"] or sort_date < entry["earliest_sort_date"]:
                entry["earliest_sort_date"] = sort_date
            if not entry["latest_sort_date"] or sort_date > entry["latest_sort_date"]:
                entry["latest_sort_date"] = sort_date

    top_queries = sorted(by_query.values(), key=lambda item: (-int(item["count"]), item["query"]))[:top_queries_limit]
    for entry in top_queries:
        entry["source_count"] = len(entry["sources"])
        entry["sources"] = dict(sorted(entry["sources"].items()))

    return {
        "schema_version": 1,
        "report_policy": "mapping_coverage_opportunities_report_only",
        "canonical_outputs_mutated": False,
        "geocoding_performed": False,
        "input": str(input_path),
        "geocode_cache": str(geocode_cache_path) if geocode_cache_path else None,
        "totals": totals,
        "coverage": {
            "mapped_ratio": safe_ratio(totals["mapped"], totals["events"]),
            "unresolved_with_location_text_ratio": safe_ratio(totals["unresolved_with_location_text"], totals["events"]),
            "unresolved_without_location_text_ratio": safe_ratio(totals["unresolved_without_location_text"], totals["events"]),
            "unresolved_cached_geocode_ratio": safe_ratio(totals["unresolved_with_cached_geocode"], totals["unresolved"]),
        },
        "unresolved_by_source": dict(sorted(by_source.items())),
        "unresolved_location_text_buckets": dict(sorted(by_bucket.items(), key=lambda item: (-item[1], item[0]))),
        "top_unresolved_location_queries": top_queries,
        "recommended_next_steps": [
            "Fix UI counters to use canonical web manifest counts when canonical runtime is active.",
            "Build an offline geocoder cache keyed by normalized location text, not by event row.",
            "Resolve city/state/country-like buckets before country-only and vague narrative buckets.",
            "Write resolved coordinates as sidecar enrichment with coordinate_source, precision, confidence, and provenance.",
            "Use cached geocode hits first, then batch only cache misses with explicit rate limits and review thresholds.",
            "Rebuild canonical web artifacts from the enriched sidecar and rerun readiness/smoke gates.",
        ],
        "top_queries_limit": top_queries_limit,
    }


def best_location_text(event: dict[str, Any]) -> str:
    candidates = [
        event.get("location_raw"),
        event.get("primary_location_text"),
        ", ".join(str(event.get(key) or "") for key in ("city", "state_province", "country")),
    ]
    for candidate in candidates:
        text = clean_text(candidate)
        if text and re.search(r"[A-Za-z0-9]", text):
            return text
    return ""


def classify_location_text(text: str) -> str:
    normalized = normalize_query(text)
    if normalized in COUNTRY_ONLY_TERMS:
        return "country_or_region_only"
    if "no location" in normalized or "unspecified" in normalized or "unknown" in normalized:
        return "vague_or_unspecified"
    if re.search(r"\b(afb|airport|base|camp|fort|pad|proving grounds|range|station)\b", normalized):
        return "facility_or_site"
    comma_count = text.count(",")
    if comma_count >= 2:
        return "city_state_country_like"
    if comma_count == 1:
        return "city_region_like"
    if re.search(r"\b[A-Z]{2}\b", text):
        return "city_state_like"
    return "single_place_token"


def normalize_query(value: str) -> str:
    text = clean_text(value).lower()
    text = text.replace("\\,", ",")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*,\s*", ", ", text)
    return text.strip(" ,")


def load_geocode_cache(path: Path | None) -> dict[str, dict[str, Any]]:
    if not path or not path.exists():
        return {}
    cache: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            result = record.get("result")
            if not isinstance(result, dict):
                continue
            lat = parse_float(result.get("lat"))
            lon = parse_float(result.get("lon"))
            if lat is None or lon is None:
                continue
            normalized_query = normalize_query(record.get("normalized_query") or record.get("query") or "")
            if normalized_query:
                cache[normalized_query] = result
    return cache


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def parse_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result else None


def safe_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 6)


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "query",
        "count",
        "bucket",
        "source_count",
        "cached_geocode_count",
        "cached_geocode_confidence",
        "cached_geocode_display_name",
        "sample_location_raw",
        "sample_event_id",
        "earliest_sort_date",
        "latest_sort_date",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--geocode-cache", type=Path, default=DEFAULT_GEOCODE_CACHE)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--top-queries-limit", type=int, default=250)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = summarize_mapping_coverage_opportunities(
        args.input,
        args.geocode_cache,
        top_queries_limit=args.top_queries_limit,
    )
    report["outputs"] = {"json": str(args.output_json), "csv": str(args.output_csv)}
    write_json(args.output_json, report)
    write_csv(args.output_csv, report["top_unresolved_location_queries"])
    print(json.dumps({
        "json": str(args.output_json),
        "csv": str(args.output_csv),
        "events": report["totals"]["events"],
        "mapped": report["totals"]["mapped"],
        "unresolved_with_location_text": report["totals"]["unresolved_with_location_text"],
        "unresolved_with_cached_geocode": report["totals"]["unresolved_with_cached_geocode"],
        "canonical_outputs_mutated": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
