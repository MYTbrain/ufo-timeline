"""Summarize explicit state/province location rows for low-precision mapping.

This report-only lane accepts only unambiguous admin-region strings such as
``CA, US`` or ``ON, CA``. It also accepts malformed placeholder-city rows such
as ``0, PA, US`` or ``unknown, ON, CA`` as admin-region evidence. It
intentionally avoids country-only rows and ambiguous city/country strings so
the resulting coordinates are clearly marked as state/province precision rather
than city-level evidence.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_MAPPING_CSV = Path("data/reports/mapping_coverage_opportunities.csv")
DEFAULT_OUTPUT_JSON = Path("data/reports/admin_region_mapping_candidates.json")
DEFAULT_OUTPUT_CSV = Path("data/reports/admin_region_mapping_candidates.csv")


US_STATE_CENTROIDS: dict[str, tuple[str, float, float, str]] = {
    "AL": ("Alabama", 32.806671, -86.791130, "America/Chicago"),
    "AK": ("Alaska", 61.370716, -152.404419, "America/Anchorage"),
    "AZ": ("Arizona", 33.729759, -111.431221, "America/Phoenix"),
    "AR": ("Arkansas", 34.969704, -92.373123, "America/Chicago"),
    "CA": ("California", 36.116203, -119.681564, "America/Los_Angeles"),
    "CO": ("Colorado", 39.059811, -105.311104, "America/Denver"),
    "CT": ("Connecticut", 41.597782, -72.755371, "America/New_York"),
    "DE": ("Delaware", 39.318523, -75.507141, "America/New_York"),
    "DC": ("District of Columbia", 38.897438, -77.026817, "America/New_York"),
    "FL": ("Florida", 27.766279, -81.686783, "America/New_York"),
    "GA": ("Georgia", 33.040619, -83.643074, "America/New_York"),
    "HI": ("Hawaii", 21.094318, -157.498337, "Pacific/Honolulu"),
    "ID": ("Idaho", 44.240459, -114.478828, "America/Boise"),
    "IL": ("Illinois", 40.349457, -88.986137, "America/Chicago"),
    "IN": ("Indiana", 39.849426, -86.258278, "America/Indiana/Indianapolis"),
    "IA": ("Iowa", 42.011539, -93.210526, "America/Chicago"),
    "KS": ("Kansas", 38.526600, -96.726486, "America/Chicago"),
    "KY": ("Kentucky", 37.668140, -84.670067, "America/New_York"),
    "LA": ("Louisiana", 31.169546, -91.867805, "America/Chicago"),
    "ME": ("Maine", 44.693947, -69.381927, "America/New_York"),
    "MD": ("Maryland", 39.063946, -76.802101, "America/New_York"),
    "MA": ("Massachusetts", 42.230171, -71.530106, "America/New_York"),
    "MI": ("Michigan", 43.326618, -84.536095, "America/Detroit"),
    "MN": ("Minnesota", 45.694454, -93.900192, "America/Chicago"),
    "MS": ("Mississippi", 32.741646, -89.678696, "America/Chicago"),
    "MO": ("Missouri", 38.456085, -92.288368, "America/Chicago"),
    "MT": ("Montana", 46.921925, -110.454353, "America/Denver"),
    "NE": ("Nebraska", 41.125370, -98.268082, "America/Chicago"),
    "NV": ("Nevada", 38.313515, -117.055374, "America/Los_Angeles"),
    "NH": ("New Hampshire", 43.452492, -71.563896, "America/New_York"),
    "NJ": ("New Jersey", 40.298904, -74.521011, "America/New_York"),
    "NM": ("New Mexico", 34.840515, -106.248482, "America/Denver"),
    "NY": ("New York", 42.165726, -74.948051, "America/New_York"),
    "NC": ("North Carolina", 35.630066, -79.806419, "America/New_York"),
    "ND": ("North Dakota", 47.528912, -99.784012, "America/Chicago"),
    "OH": ("Ohio", 40.388783, -82.764915, "America/New_York"),
    "OK": ("Oklahoma", 35.565342, -96.928917, "America/Chicago"),
    "OR": ("Oregon", 44.572021, -122.070938, "America/Los_Angeles"),
    "PA": ("Pennsylvania", 40.590752, -77.209755, "America/New_York"),
    "RI": ("Rhode Island", 41.680893, -71.511780, "America/New_York"),
    "SC": ("South Carolina", 33.856892, -80.945007, "America/New_York"),
    "SD": ("South Dakota", 44.299782, -99.438828, "America/Chicago"),
    "TN": ("Tennessee", 35.747845, -86.692345, "America/Chicago"),
    "TX": ("Texas", 31.054487, -97.563461, "America/Chicago"),
    "UT": ("Utah", 40.150032, -111.862434, "America/Denver"),
    "VT": ("Vermont", 44.045876, -72.710686, "America/New_York"),
    "VA": ("Virginia", 37.769337, -78.169968, "America/New_York"),
    "WA": ("Washington", 47.400902, -121.490494, "America/Los_Angeles"),
    "WV": ("West Virginia", 38.491226, -80.954453, "America/New_York"),
    "WI": ("Wisconsin", 44.268543, -89.616508, "America/Chicago"),
    "WY": ("Wyoming", 42.755966, -107.302490, "America/Denver"),
}

CA_PROVINCE_CENTROIDS: dict[str, tuple[str, float, float, str]] = {
    "AB": ("Alberta", 53.933270, -116.576504, "America/Edmonton"),
    "BC": ("British Columbia", 53.726669, -127.647621, "America/Vancouver"),
    "MB": ("Manitoba", 53.760861, -98.813876, "America/Winnipeg"),
    "NB": ("New Brunswick", 46.565316, -66.461916, "America/Moncton"),
    "NL": ("Newfoundland and Labrador", 53.135509, -57.660436, "America/St_Johns"),
    "NS": ("Nova Scotia", 44.681987, -63.744311, "America/Halifax"),
    "NT": ("Northwest Territories", 64.825544, -124.845733, "America/Yellowknife"),
    "NU": ("Nunavut", 70.299771, -83.107577, "America/Iqaluit"),
    "ON": ("Ontario", 51.253775, -85.323214, "America/Toronto"),
    "PE": ("Prince Edward Island", 46.510712, -63.416814, "America/Halifax"),
    "QC": ("Quebec", 52.939916, -73.549136, "America/Toronto"),
    "SK": ("Saskatchewan", 52.939916, -106.450864, "America/Regina"),
    "YT": ("Yukon", 64.282327, -135.000000, "America/Whitehorse"),
}

COUNTRY_ALIASES = {
    "us": "US",
    "usa": "US",
    "united states": "US",
    "ca": "CA",
    "canada": "CA",
}

PLACEHOLDER_CITY_TOKENS = {"0", "n/a", "na", "none", "unk", "unknown"}


def summarize_admin_region_mapping_candidates(*, mapping_csv: Path) -> dict[str, Any]:
    rows = load_rows(mapping_csv)
    candidates: list[dict[str, Any]] = []
    rejected: dict[str, int] = {}

    for row in rows:
        count = int(row.get("count") or 0)
        parsed = parse_admin_region_query(row.get("query") or "")
        if not parsed:
            rejected["not_explicit_admin_region"] = rejected.get("not_explicit_admin_region", 0) + count
            continue
        country_code, admin_code = parsed
        lookup = US_STATE_CENTROIDS if country_code == "US" else CA_PROVINCE_CENTROIDS
        match = lookup.get(admin_code)
        if not match:
            rejected["unsupported_admin_region"] = rejected.get("unsupported_admin_region", 0) + count
            continue
        name, lat, lon, timezone = match
        precision = "state" if country_code == "US" else "province"
        candidates.append(
            {
                "query": normalize_query(row.get("query") or ""),
                "count": count,
                "confidence": "medium",
                "candidate_count": 1,
                "name": f"{name}, {country_code}",
                "lat": lat,
                "lon": lon,
                "country_code": country_code,
                "admin1": admin_code,
                "population": 0,
                "timezone": timezone,
                "location_precision": precision,
            }
        )

    return {
        "schema_version": 1,
        "report_policy": "admin_region_mapping_candidates_report_only",
        "canonical_outputs_mutated": False,
        "geocoding_performed": False,
        "inputs": {"mapping_csv": str(mapping_csv)},
        "mapping_query_count": len(rows),
        "candidate_query_count": len(candidates),
        "candidate_event_count": sum(int(row["count"]) for row in candidates),
        "rejected_event_counts": dict(sorted(rejected.items())),
        "candidates": sorted(candidates, key=lambda item: (-int(item["count"]), item["query"])),
        "notes": [
            "Only explicit admin-region plus country rows are accepted.",
            "Placeholder city/admin/country rows such as 0, PA, US are accepted as admin-region evidence only.",
            "Country-only, city/country, and bare ambiguous two-letter rows are rejected.",
            "Coordinates are centroids and are marked with state/province precision, not city precision.",
        ],
    }


def parse_admin_region_query(value: str) -> tuple[str, str] | None:
    parts = [part.strip().lower() for part in normalize_query(value).split(",") if part.strip()]
    if len(parts) == 3 and parts[0] in PLACEHOLDER_CITY_TOKENS:
        parts = parts[1:]
    if len(parts) != 2:
        return None
    admin = parts[0].upper()
    country = COUNTRY_ALIASES.get(parts[1])
    if not country or not re.fullmatch(r"[A-Z]{2}", admin):
        return None
    return country, admin


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def normalize_query(value: str) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("\\,", ",")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*,\s*", ", ", text)
    return text.strip(" ,")


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
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = summarize_admin_region_mapping_candidates(mapping_csv=args.mapping_csv)
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
