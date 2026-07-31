"""Find safe dominant-city GeoNames matches for ambiguous unresolved queries.

This is a report-only bridge for rows like ``phoenix, us`` where the standard
GeoNames pass correctly labels the query low confidence because multiple cities
share the name. A row is promoted only when the top populated-place candidate
dominates the runner-up enough to be useful as a preview mapping candidate.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import zipfile
from pathlib import Path
from typing import Any

from scripts.summarize_offline_geonames_mapping_candidates import COUNTRY_ALIASES, normalize, normalized_names


DEFAULT_MAPPING_CSV = Path("data/reports/mapping_coverage_opportunities_after_geonames_top50000_quarantine_v3.csv")
DEFAULT_GEONAMES_ZIP = Path("cache/map_overlays/allCountries.zip")
DEFAULT_OUTPUT_JSON = Path("data/reports/dominant_geonames_mapping_candidates_after_top50000.json")
DEFAULT_OUTPUT_CSV = Path("data/reports/dominant_geonames_mapping_candidates_after_top50000.csv")

MIN_TOP_POPULATION = 100_000
MIN_DOMINANCE_RATIO = 5.0
HIGH_DOMINANCE_RATIO = 10.0


def summarize_dominant_geonames_mapping_candidates(
    *,
    mapping_csv: Path,
    geonames_zip: Path,
    limit: int,
    min_top_population: int = MIN_TOP_POPULATION,
    min_dominance_ratio: float = MIN_DOMINANCE_RATIO,
) -> dict[str, Any]:
    queries = load_queries(mapping_csv, limit)
    parsed_queries = [query for query in (parse_ambiguous_city_country_query(row) for row in queries) if query]
    wanted_names = {query["city"] for query in parsed_queries}
    candidates_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {
        (query["city"], query["country_code"]): [] for query in parsed_queries
    }

    with zipfile.ZipFile(geonames_zip) as archive:
        with archive.open("allCountries.txt") as raw:
            for raw_line in raw:
                line = raw_line.decode("utf-8", errors="replace").rstrip("\n")
                parts = line.split("\t")
                if len(parts) < 19 or parts[6] != "P":
                    continue
                name_values = normalized_names(parts[1], parts[2], parts[3])
                matched_names = wanted_names.intersection(name_values)
                if not matched_names:
                    continue
                country_code = parts[8].upper()
                for city in matched_names:
                    key = (city, country_code)
                    if key not in candidates_by_key:
                        continue
                    candidates_by_key[key].append(
                        {
                            "geoname_id": parts[0],
                            "name": parts[1],
                            "lat": float(parts[4]),
                            "lon": float(parts[5]),
                            "country_code": country_code,
                            "admin1": parts[10].upper(),
                            "feature_code": parts[7],
                            "population": int(parts[14] or 0),
                            "timezone": parts[17],
                        }
                    )

    accepted_rows: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []
    accepted_event_count = 0

    for query in parsed_queries:
        candidates = sorted(
            candidates_by_key.get((query["city"], query["country_code"]), []),
            key=lambda item: (-int(item["population"]), item["name"], item["admin1"]),
        )
        if not candidates:
            continue
        top = candidates[0]
        runner_up = candidates[1] if len(candidates) > 1 else None
        runner_up_population = int(runner_up["population"]) if runner_up else 0
        dominance_ratio = dominance(top_population=int(top["population"]), runner_up_population=runner_up_population)
        accepted = int(top["population"]) >= min_top_population and dominance_ratio >= min_dominance_ratio
        base_row = {
            "query": query["query"],
            "count": int(query["count"]),
            "confidence": confidence_for(dominance_ratio),
            "candidate_count": len(candidates),
            "name": top["name"],
            "lat": top["lat"],
            "lon": top["lon"],
            "country_code": top["country_code"],
            "admin1": top["admin1"],
            "population": top["population"],
            "timezone": top["timezone"],
            "dominance_ratio": round(dominance_ratio, 3),
            "runner_up_name": runner_up["name"] if runner_up else "",
            "runner_up_admin1": runner_up["admin1"] if runner_up else "",
            "runner_up_population": runner_up_population,
            "decision": "accepted_dominant_city" if accepted else "rejected_not_dominant_enough",
        }
        if accepted:
            accepted_rows.append(base_row)
            accepted_event_count += int(query["count"])
        else:
            rejected_rows.append(base_row)

    return {
        "schema_version": 1,
        "report_policy": "dominant_geonames_mapping_candidates_report_only",
        "canonical_outputs_mutated": False,
        "geocoding_performed": False,
        "geonames_streamed": True,
        "inputs": {
            "mapping_csv": str(mapping_csv),
            "geonames_zip": str(geonames_zip),
            "limit": limit,
        },
        "thresholds": {
            "min_top_population": min_top_population,
            "min_dominance_ratio": min_dominance_ratio,
            "high_dominance_ratio": HIGH_DOMINANCE_RATIO,
        },
        "query_count": len(queries),
        "parseable_city_country_query_count": len(parsed_queries),
        "accepted_query_count": len(accepted_rows),
        "accepted_event_count": accepted_event_count,
        "rejected_query_count": len(rejected_rows),
        "accepted_queries": accepted_rows,
        "rejected_queries_sample": rejected_rows[:100],
        "notes": [
            "Only city/country unresolved queries without state/admin evidence are considered.",
            "Country-only, state-only, and already state-qualified rows are excluded.",
            "Accepted rows require a dominant most-populated GeoNames candidate, not just any match.",
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


def parse_ambiguous_city_country_query(row: dict[str, str]) -> dict[str, str] | None:
    query = normalize(row.get("query") or "")
    if not query:
        return None
    parts = [part.strip() for part in query.split(",") if part.strip()]
    if len(parts) != 2:
        return None
    country_code = COUNTRY_ALIASES.get(parts[-1])
    if not country_code:
        return None
    city = normalize(parts[0])
    if len(city) <= 2 or re.fullmatch(r"[a-z]{2,3}", city):
        return None
    return {
        "query": query,
        "city": city,
        "country_code": country_code,
        "count": str(int(row.get("count") or 0)),
    }


def dominance(*, top_population: int, runner_up_population: int) -> float:
    return top_population / max(runner_up_population, 1)


def confidence_for(dominance_ratio: float) -> str:
    if dominance_ratio >= HIGH_DOMINANCE_RATIO:
        return "high"
    if dominance_ratio >= MIN_DOMINANCE_RATIO:
        return "medium"
    return "low"


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
        "dominance_ratio",
        "runner_up_name",
        "runner_up_admin1",
        "runner_up_population",
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
    parser.add_argument("--min-top-population", type=int, default=MIN_TOP_POPULATION)
    parser.add_argument("--min-dominance-ratio", type=float, default=MIN_DOMINANCE_RATIO)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = summarize_dominant_geonames_mapping_candidates(
        mapping_csv=args.mapping_csv,
        geonames_zip=args.geonames_zip,
        limit=args.limit,
        min_top_population=args.min_top_population,
        min_dominance_ratio=args.min_dominance_ratio,
    )
    report["outputs"] = {"json": str(args.output_json), "csv": str(args.output_csv)}
    write_json(args.output_json, report)
    write_csv(args.output_csv, report["accepted_queries"])
    print(
        json.dumps(
            {
                "json": str(args.output_json),
                "csv": str(args.output_csv),
                "accepted_query_count": report["accepted_query_count"],
                "accepted_event_count": report["accepted_event_count"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
