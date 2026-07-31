"""Summarize cached geocode hits that are safe enough for mapping enrichment.

This is report-only. It cross-references a mapping coverage CSV with the local
geocode cache and keeps only coordinate-bearing cache entries whose confidence
and place type look suitable for event-level map placement.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_MAPPING_CSV = Path("data/reports/mapping_coverage_opportunities_after_top5000_geonames.csv")
DEFAULT_GEOCODE_CACHE = Path("cache/geocode_cache.jsonl")
DEFAULT_OUTPUT_JSON = Path("data/reports/cached_geocode_mapping_candidates_after_top5000.json")
DEFAULT_OUTPUT_CSV = Path("data/reports/cached_geocode_mapping_candidates_after_top5000.csv")

MIN_CONFIDENCE = 0.75
SAFE_ADDRESS_TYPES = {
    "city",
    "town",
    "village",
    "hamlet",
    "municipality",
    "suburb",
    "locality",
}
RISKY_ADDRESS_TYPES = {
    "aeroway",
    "amenity",
    "building",
    "farm",
    "house",
    "neighbourhood",
    "place_of_worship",
    "road",
    "shop",
}


def summarize_cached_geocode_mapping_candidates(
    *,
    mapping_csv: Path,
    geocode_cache: Path,
    min_confidence: float = MIN_CONFIDENCE,
) -> dict[str, Any]:
    cache = load_cache(geocode_cache)
    rows = load_mapping_rows(mapping_csv)
    candidates: list[dict[str, Any]] = []
    rejected: dict[str, int] = {}

    for row in rows:
        query = normalize_query(row.get("query") or "")
        cached = cache.get(query)
        if not cached:
            continue
        result = cached["result"]
        rejection_reason = rejection_for_result(result, min_confidence)
        if rejection_reason:
            rejected[rejection_reason] = rejected.get(rejection_reason, 0) + int(row.get("count") or 0)
            continue
        count = int(row.get("count") or 0)
        candidates.append(
            {
                "query": query,
                "count": count,
                "bucket": row.get("bucket") or "",
                "confidence": round(float(result.get("confidence") or 0), 6),
                "lat": parse_float(result.get("lat")),
                "lon": parse_float(result.get("lon")),
                "display_name": clean_text(result.get("display_name")),
                "addresstype": result_addresstype(result),
                "category": result_category(result),
                "osm_type": ((result.get("raw") or {}).get("osm_type") or ""),
                "provider_id": cached.get("provider_id") or "",
            }
        )

    candidate_event_count = sum(int(row["count"]) for row in candidates)
    return {
        "schema_version": 1,
        "report_policy": "cached_geocode_mapping_candidates_report_only",
        "canonical_outputs_mutated": False,
        "geocoding_performed": False,
        "inputs": {
            "mapping_csv": str(mapping_csv),
            "geocode_cache": str(geocode_cache),
            "min_confidence": min_confidence,
        },
        "mapping_query_count": len(rows),
        "cached_query_count": sum(1 for row in rows if normalize_query(row.get("query") or "") in cache),
        "candidate_query_count": len(candidates),
        "candidate_event_count": candidate_event_count,
        "rejected_event_counts": dict(sorted(rejected.items())),
        "candidates": sorted(candidates, key=lambda item: (-int(item["count"]), item["query"])),
        "notes": [
            "This report uses cached geocode results only; it does not call a geocoder.",
            "Candidates require numeric coordinates, confidence above threshold, and non-risky address types.",
            "Country-only centroids are intentionally excluded from the safe candidate set.",
        ],
    }


def load_cache(path: Path) -> dict[str, dict[str, Any]]:
    cache: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            result = record.get("result")
            if not isinstance(result, dict):
                continue
            query = normalize_query(record.get("normalized_query") or record.get("query") or "")
            if query:
                cache[query] = record
    return cache


def load_mapping_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def rejection_for_result(result: dict[str, Any], min_confidence: float) -> str:
    lat = parse_float(result.get("lat"))
    lon = parse_float(result.get("lon"))
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return "missing_or_invalid_coordinates"
    confidence = parse_float(result.get("confidence"))
    if confidence is None or confidence < min_confidence:
        return "low_confidence"
    addresstype = result_addresstype(result)
    category = result_category(result)
    if addresstype in {"country", "county", "state", "province", "region"}:
        return "broad_centroid"
    if addresstype in RISKY_ADDRESS_TYPES or category in RISKY_ADDRESS_TYPES:
        return "risky_place_type"
    if addresstype and addresstype not in SAFE_ADDRESS_TYPES:
        return "unsupported_place_type"
    return ""


def result_addresstype(result: dict[str, Any]) -> str:
    raw = result.get("raw") or {}
    return clean_text(raw.get("addresstype") or result.get("addresstype")).lower()


def result_category(result: dict[str, Any]) -> str:
    raw = result.get("raw") or {}
    return clean_text(raw.get("category") or result.get("category")).lower()


def normalize_query(value: str) -> str:
    text = clean_text(value).lower()
    text = text.replace("\\,", ",")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*,\s*", ", ", text)
    return text.strip(" ,")


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


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "query",
        "count",
        "bucket",
        "confidence",
        "lat",
        "lon",
        "display_name",
        "addresstype",
        "category",
        "osm_type",
        "provider_id",
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
    parser.add_argument("--geocode-cache", type=Path, default=DEFAULT_GEOCODE_CACHE)
    parser.add_argument("--min-confidence", type=float, default=MIN_CONFIDENCE)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = summarize_cached_geocode_mapping_candidates(
        mapping_csv=args.mapping_csv,
        geocode_cache=args.geocode_cache,
        min_confidence=args.min_confidence,
    )
    report["outputs"] = {"json": str(args.output_json), "csv": str(args.output_csv)}
    write_json(args.output_json, report)
    write_csv(args.output_csv, report["candidates"])
    print(json.dumps({
        "json": str(args.output_json),
        "csv": str(args.output_csv),
        "candidate_query_count": report["candidate_query_count"],
        "candidate_event_count": report["candidate_event_count"],
        "canonical_outputs_mutated": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
