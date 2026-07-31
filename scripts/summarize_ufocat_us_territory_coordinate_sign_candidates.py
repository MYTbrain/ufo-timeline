"""Report UFOCAT U.S. territory longitude-sign candidates.

This is a report-only safety lane. It flags exact/source-coordinate UFOCAT rows
where explicit territory evidence and a bounded longitude flip agree. It does
not rewrite canonical or preview corpora.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from scripts.apply_coordinate_sanity_preview import EXACT_COORDINATE_SOURCES, clean_text, parse_float, write_json


DEFAULT_INPUT = Path("data/canonical_preview_map_enrich_v29_facility_site/deduped_events.jsonl")
DEFAULT_JSON = Path("data/reports/ufocat_us_territory_coordinate_sign_candidates_after_v29.json")
DEFAULT_CSV = Path("data/reports/ufocat_us_territory_coordinate_sign_candidates_after_v29.csv")

TERRITORY_BOUNDS = {
    "us_virgin_islands": {
        "lat": (17.4, 18.8),
        "lon": (-65.3, -64.2),
        "state_codes": {"ISV", "UVI"},
        "location_phrases": {"US VIRGIN ISLANDS", "U.S. VIRGIN ISLANDS", "VIRGIN ISLANDS"},
    },
    "puerto_rico": {
        "lat": (17.5, 18.7),
        "lon": (-68.5, -65.0),
        "state_codes": {"PR", "PRI", "PUR"},
        "location_phrases": {"PUERTO RICO"},
    },
}


def summarize_ufocat_us_territory_coordinate_sign_candidates(
    *,
    input_path: Path,
    json_output: Path,
    csv_output: Path,
) -> dict[str, Any]:
    checked_rows = 0
    candidate_rows: list[dict[str, Any]] = []
    territory_counts: dict[str, int] = {}

    with input_path.open("r", encoding="utf-8") as source:
        for line in source:
            if not line.strip():
                continue
            event = json.loads(line)
            if clean_text(event.get("source_name")).lower() != "ufocat":
                continue
            if clean_text(event.get("coordinate_source")) not in EXACT_COORDINATE_SOURCES:
                continue
            lat = parse_float(event.get("lat"))
            lon = parse_float(event.get("lon"))
            if lat is None or lon is None or lon <= 0:
                continue
            checked_rows += 1
            territory, evidence = territory_match(event, lat, lon)
            if not territory:
                continue
            row = candidate_payload(event, territory, evidence, lat, lon)
            candidate_rows.append(row)
            territory_counts[territory] = territory_counts.get(territory, 0) + 1

    report = {
        "schema_version": 1,
        "mode": "report_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_mutated": False,
        "inputs": {"deduped_events": str(input_path)},
        "outputs": {"json": str(json_output), "csv": str(csv_output)},
        "checked_positive_lon_ufocat_source_coordinate_rows": checked_rows,
        "candidate_event_count": len(candidate_rows),
        "territory_counts": dict(sorted(territory_counts.items())),
        "candidates": candidate_rows[:200],
        "notes": [
            "Flags only UFOCAT exact/source-coordinate rows with positive longitude.",
            "Requires explicit U.S. territory evidence and a bounded longitude flip into that territory.",
            "Excludes incidental text matches that do not have territory code/phrase evidence and bounded coordinates.",
            "Report-only: no canonical or preview corpus is rewritten.",
        ],
    }
    write_json(json_output, report)
    write_candidates_csv(csv_output, candidate_rows)
    return report


def territory_match(event: dict[str, Any], lat: float, lon: float) -> tuple[str | None, str]:
    raw_fields = event.get("raw_fields") or {}
    state = clean_text(raw_fields.get("STATE") or event.get("state_province")).upper()
    location_values = [
        event.get("location_raw"),
        event.get("city"),
        raw_fields.get("LOCATION"),
        raw_fields.get("COUNTY"),
    ]
    location_text = " ".join(clean_text(value).upper() for value in location_values if clean_text(value))
    flipped_lon = -lon
    for territory, config in TERRITORY_BOUNDS.items():
        has_state_evidence = state in config["state_codes"]
        has_phrase_evidence = any(phrase in location_text for phrase in config["location_phrases"])
        if not (has_state_evidence or has_phrase_evidence):
            continue
        lat_min, lat_max = config["lat"]
        lon_min, lon_max = config["lon"]
        if lat_min <= lat <= lat_max and lon_min <= flipped_lon <= lon_max:
            evidence = "state_code" if has_state_evidence else "location_phrase"
            return territory, evidence
    return None, ""


def candidate_payload(event: dict[str, Any], territory: str, evidence: str, lat: float, lon: float) -> dict[str, Any]:
    raw_fields = event.get("raw_fields") or {}
    return {
        "canonical_event_id": event.get("canonical_event_id"),
        "source_row_number": event.get("source_row_number"),
        "source_native_id": event.get("source_native_id"),
        "date_iso": event.get("date_iso"),
        "location_raw": event.get("location_raw"),
        "state_province": event.get("state_province"),
        "country": event.get("country"),
        "raw_region": raw_fields.get("REGION"),
        "raw_state": raw_fields.get("STATE"),
        "territory": territory,
        "evidence": evidence,
        "lat": lat,
        "old_lon": lon,
        "candidate_lon": -lon,
        "coordinate_source": event.get("coordinate_source"),
    }


def write_candidates_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "canonical_event_id",
        "source_row_number",
        "source_native_id",
        "date_iso",
        "location_raw",
        "state_province",
        "country",
        "raw_region",
        "raw_state",
        "territory",
        "evidence",
        "lat",
        "old_lon",
        "candidate_lon",
        "coordinate_source",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = summarize_ufocat_us_territory_coordinate_sign_candidates(
        input_path=args.input,
        json_output=args.json_output,
        csv_output=args.csv_output,
    )
    print(json.dumps({
        "json": report["outputs"]["json"],
        "csv": report["outputs"]["csv"],
        "candidate_event_count": report["candidate_event_count"],
        "canonical_outputs_mutated": False,
        "preview_outputs_mutated": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
