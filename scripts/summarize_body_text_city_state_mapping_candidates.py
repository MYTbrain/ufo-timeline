"""Find event-level city/state mapping candidates from explicit body text.

This report-only lane is intentionally narrower than query-level GeoNames
mapping. Ambiguous rows such as ``Columbus, US`` are only accepted when the
individual event text explicitly repeats the city with a US state name or
postal abbreviation, for example ``Columbus Ohio`` or ``Springfield IL``.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import zipfile
from pathlib import Path
from typing import Any

from scripts.apply_mapping_enrichment_preview import best_location_text, has_usable_coordinates, normalize_query
from scripts.summarize_admin_region_mapping_candidates import US_STATE_CENTROIDS
from scripts.summarize_offline_geonames_mapping_candidates import normalize


DEFAULT_INPUT = Path("data/canonical_preview_map_enrich_v5_placeholder_admin_region/deduped_events.jsonl")
DEFAULT_MAPPING_CSV = Path("data/reports/mapping_coverage_opportunities_after_placeholder_admin_region_quarantine_v5.csv")
DEFAULT_GEONAMES_ZIP = Path("cache/map_overlays/allCountries.zip")
DEFAULT_OUTPUT_JSON = Path("data/reports/body_text_city_state_mapping_candidates.json")
DEFAULT_OUTPUT_CSV = Path("data/reports/body_text_city_state_mapping_candidates.csv")

STATE_NAME_TO_CODE = {name.lower(): code for code, (name, _lat, _lon, _timezone) in US_STATE_CENTROIDS.items()}
STATE_CODE_TO_NAME = {code: name for code, (name, _lat, _lon, _timezone) in US_STATE_CENTROIDS.items()}
AMBIGUOUS_STATE_WORDS = {"IN", "ME", "OR"}


def summarize_body_text_city_state_mapping_candidates(
    *,
    input_path: Path,
    mapping_csv: Path,
    geonames_zip: Path,
) -> dict[str, Any]:
    target_queries = load_ambiguous_city_us_queries(mapping_csv)
    event_candidates: list[dict[str, Any]] = []
    needed_pairs: set[tuple[str, str]] = set()
    scanned_events = 0
    unresolved_target_events = 0
    rejected_counts: dict[str, int] = {}

    with input_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            event = json.loads(line)
            scanned_events += 1
            if has_usable_coordinates(event):
                continue
            query = normalize_query(best_location_text(event))
            city = target_queries.get(query)
            if not city:
                continue
            unresolved_target_events += 1
            evidence = find_explicit_state_evidence(city, collect_evidence_text(event))
            if not evidence:
                rejected_counts["no_explicit_city_state_evidence"] = rejected_counts.get("no_explicit_city_state_evidence", 0) + 1
                continue
            candidate = {
                "canonical_event_id": event.get("canonical_event_id") or "",
                "query": query,
                "city": city,
                "state_code": evidence["state_code"],
                "state_name": STATE_CODE_TO_NAME[evidence["state_code"]],
                "evidence_phrase": evidence["phrase"],
                "confidence": "high",
                "location_precision": "city",
                "source_name": event.get("source_name") or "",
            }
            event_candidates.append(candidate)
            needed_pairs.add((normalize_for_geonames(city), evidence["state_code"]))

    geonames_by_pair = load_geonames_city_state_matches(geonames_zip, needed_pairs)
    resolved_rows: list[dict[str, Any]] = []
    for candidate in event_candidates:
        match = geonames_by_pair.get((normalize_for_geonames(candidate["city"]), candidate["state_code"]))
        if not match:
            rejected_counts["geonames_city_state_not_found"] = rejected_counts.get("geonames_city_state_not_found", 0) + 1
            continue
        resolved_rows.append(
            {
                **candidate,
                "name": match["name"],
                "lat": match["lat"],
                "lon": match["lon"],
                "country_code": "US",
                "admin1": candidate["state_code"],
                "population": match["population"],
                "timezone": match["timezone"],
                "candidate_count": match["candidate_count"],
            }
        )

    return {
        "schema_version": 1,
        "report_policy": "body_text_city_state_mapping_candidates_report_only",
        "canonical_outputs_mutated": False,
        "geocoding_performed": False,
        "geonames_streamed": True,
        "inputs": {
            "deduped_events": str(input_path),
            "mapping_csv": str(mapping_csv),
            "geonames_zip": str(geonames_zip),
        },
        "target_query_count": len(target_queries),
        "scanned_event_count": scanned_events,
        "unresolved_target_event_count": unresolved_target_events,
        "candidate_event_count": len(event_candidates),
        "resolved_event_count": len(resolved_rows),
        "rejected_event_counts": dict(sorted(rejected_counts.items())),
        "resolved_events": resolved_rows,
        "notes": [
            "This lane is event-level, not query-level: ambiguous City, US rows are not mapped unless the same event text contains explicit city-state evidence.",
            "State postal abbreviations IN, ME, and OR are ignored as standalone evidence because they are common English words.",
            "No canonical event coordinates are changed by this report.",
        ],
    }


def load_ambiguous_city_us_queries(path: Path) -> dict[str, str]:
    targets: dict[str, str] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            query = normalize_query(row.get("query") or "")
            parts = [part.strip() for part in query.split(",") if part.strip()]
            if len(parts) != 2 or parts[1] != "us":
                continue
            city = parts[0]
            if len(city) <= 2 or city in {"us", "unknown", "n/a", "na", "none", "0"}:
                continue
            if not re.search(r"[a-z]", city):
                continue
            targets[query] = city
    return targets


def collect_evidence_text(event: dict[str, Any]) -> str:
    values: list[str] = []
    for key in ("description", "location_raw", "primary_location_text"):
        value = event.get(key)
        if value:
            values.append(str(value))
    raw_fields = event.get("raw_fields")
    if isinstance(raw_fields, dict):
        for key in ("description", "summary", "comments", "location"):
            value = raw_fields.get(key)
            if value:
                values.append(str(value))
    return "\n".join(values)


def find_explicit_state_evidence(city: str, text: str) -> dict[str, str] | None:
    if not text:
        return None
    city_pattern = re.escape(city).replace(r"\ ", r"\s+")
    for state_name, state_code in sorted(STATE_NAME_TO_CODE.items(), key=lambda item: -len(item[0])):
        state_pattern = re.escape(state_name).replace(r"\ ", r"\s+")
        pattern = re.compile(rf"\b{city_pattern}\b[\s,()./-]{{0,20}}\b{state_pattern}\b", re.IGNORECASE)
        match = pattern.search(text)
        if match:
            return {"state_code": state_code, "phrase": compact_phrase(match.group(0))}
    for state_code in sorted(STATE_CODE_TO_NAME):
        if state_code in AMBIGUOUS_STATE_WORDS:
            continue
        pattern = re.compile(rf"\b{city_pattern}\b[\s,()./-]{{0,10}}\b{re.escape(state_code)}\b", re.IGNORECASE)
        match = pattern.search(text)
        if match:
            return {"state_code": state_code, "phrase": compact_phrase(match.group(0))}
    return None


def compact_phrase(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()[:160]


def normalize_for_geonames(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def load_geonames_city_state_matches(
    geonames_zip: Path,
    needed_pairs: set[tuple[str, str]],
) -> dict[tuple[str, str], dict[str, Any]]:
    candidates: dict[tuple[str, str], list[dict[str, Any]]] = {pair: [] for pair in needed_pairs}
    if not needed_pairs:
        return {}
    needed_names = {city for city, _state in needed_pairs}
    with zipfile.ZipFile(geonames_zip) as archive:
        with archive.open("allCountries.txt") as raw:
            for raw_line in raw:
                parts = raw_line.decode("utf-8", errors="replace").rstrip("\n").split("\t")
                if len(parts) < 19 or parts[6] != "P" or parts[8].upper() != "US":
                    continue
                names = {normalize(parts[1]), normalize(parts[2])}
                names.discard("")
                if not needed_names.intersection(names):
                    continue
                admin1 = parts[10].upper()
                for name in names.intersection(needed_names):
                    pair = (name, admin1)
                    if pair not in candidates:
                        continue
                    candidates[pair].append(
                        {
                            "name": parts[1],
                            "lat": float(parts[4]),
                            "lon": float(parts[5]),
                            "population": int(parts[14] or 0),
                            "timezone": parts[17],
                        }
                    )
    resolved: dict[tuple[str, str], dict[str, Any]] = {}
    for pair, rows in candidates.items():
        sorted_rows = sorted(rows, key=lambda row: (-row["population"], row["name"]))
        if not sorted_rows:
            continue
        resolved[pair] = {**sorted_rows[0], "candidate_count": len(sorted_rows)}
    return resolved


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "canonical_event_id",
        "query",
        "city",
        "state_code",
        "state_name",
        "evidence_phrase",
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
        "source_name",
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
    parser.add_argument("--mapping-csv", type=Path, default=DEFAULT_MAPPING_CSV)
    parser.add_argument("--geonames-zip", type=Path, default=DEFAULT_GEONAMES_ZIP)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = summarize_body_text_city_state_mapping_candidates(
        input_path=args.input,
        mapping_csv=args.mapping_csv,
        geonames_zip=args.geonames_zip,
    )
    report["outputs"] = {"json": str(args.output_json), "csv": str(args.output_csv)}
    write_json(args.output_json, report)
    write_csv(args.output_csv, report["resolved_events"])
    print(
        json.dumps(
            {
                "json": str(args.output_json),
                "csv": str(args.output_csv),
                "target_query_count": report["target_query_count"],
                "candidate_event_count": report["candidate_event_count"],
                "resolved_event_count": report["resolved_event_count"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
