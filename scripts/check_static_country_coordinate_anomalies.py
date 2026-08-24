"""Report explicit country-coded mapped rows outside broad country bounds.

This is a wider shipped-payload QA check than the named screenshot regression
check. It scans static canonical summary shards for rows whose rendered
``location_raw`` contains an explicit country token and whose mapped point is
outside broad review bounds for that country.

The script is report-only. It does not mutate canonical data, static bundles, or
preview sidecars.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable

from scripts.apply_coordinate_sanity_preview import BOUNDED_FLIP_LON_RANGES, COUNTRY_ALIASES
from scripts.apply_jurisdiction_coordinate_repair_preview import US_STATE_BOUNDS
from scripts.build_coordinate_quarantine_packet import COUNTRY_REVIEW_BOUNDS


DEFAULT_PAYLOAD_ROOT = Path("static_bundle")
DEFAULT_JSON_OUTPUT = Path("data/reports/static_country_coordinate_anomalies.json")
DEFAULT_CSV_OUTPUT = Path("data/reports/static_country_coordinate_anomalies.csv")

REGION_TOKENS = {"AF", "AS", "CA", "EU", "EUR", "NA", "OC", "SA"}
AMBIGUOUS_NONFINAL_TOKENS = {"CA", "DE", "FR", "GB", "UK", "AU"}
AUSTRALIAN_STATE_TOKENS = {"ACT", "NSW", "NT", "QLD", "QUE", "SA", "TAS", "VIC", "WA"}
CANADIAN_PROVINCE_TOKENS = {
    "AB",
    "ALBERTA",
    "BC",
    "BRITISH COLUMBIA",
    "MB",
    "MANITOBA",
    "NB",
    "NEW BRUNSWICK",
    "NL",
    "NEWFOUNDLAND",
    "NS",
    "NOVA SCOTIA",
    "NT",
    "NWT",
    "ON",
    "ONT",
    "ONTARIO",
    "PE",
    "PEI",
    "QC",
    "QUE",
    "QUEBEC",
    "SK",
    "SASKATCHEWAN",
    "YT",
    "YUKON",
}
OCEANIA_COUNTRY_TOKENS_BEFORE_REGION_AU = {
    "NZ",
    "NZL",
    "NEW ZEALAND",
    "PNG",
    "PAPUA NEW GUINEA",
    "SOL",
    "SOLOMON ISLANDS",
    "FIJI",
    "FJI",
}
EXACTISH_COORDINATE_SOURCES = {"raw_latlong", "source_coordinates", "location_coordinates", "geocoded"}
US_STATE_NAME_TO_ABBREVIATION = {
    "ALABAMA": "AL",
    "ALASKA": "AK",
    "ARIZONA": "AZ",
    "ARKANSAS": "AR",
    "CALIFORNIA": "CA",
    "COLORADO": "CO",
    "CONNECTICUT": "CT",
    "DELAWARE": "DE",
    "DISTRICT OF COLUMBIA": "DC",
    "FLORIDA": "FL",
    "GEORGIA": "GA",
    "HAWAII": "HI",
    "IDAHO": "ID",
    "ILLINOIS": "IL",
    "INDIANA": "IN",
    "IOWA": "IA",
    "KANSAS": "KS",
    "KENTUCKY": "KY",
    "LOUISIANA": "LA",
    "MAINE": "ME",
    "MARYLAND": "MD",
    "MASSACHUSETTS": "MA",
    "MICHIGAN": "MI",
    "MINNESOTA": "MN",
    "MISSISSIPPI": "MS",
    "MISSOURI": "MO",
    "MONTANA": "MT",
    "NEBRASKA": "NE",
    "NEVADA": "NV",
    "NEW HAMPSHIRE": "NH",
    "NEW JERSEY": "NJ",
    "NEW MEXICO": "NM",
    "NEW YORK": "NY",
    "NORTH CAROLINA": "NC",
    "NORTH DAKOTA": "ND",
    "OHIO": "OH",
    "OKLAHOMA": "OK",
    "OREGON": "OR",
    "PENNSYLVANIA": "PA",
    "RHODE ISLAND": "RI",
    "SOUTH CAROLINA": "SC",
    "SOUTH DAKOTA": "SD",
    "TENNESSEE": "TN",
    "TEXAS": "TX",
    "UTAH": "UT",
    "VERMONT": "VT",
    "VIRGINIA": "VA",
    "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV",
    "WISCONSIN": "WI",
    "WYOMING": "WY",
}
LOCAL_COUNTRY_ALIASES = {
    **COUNTRY_ALIASES,
    "ENG": "United Kingdom",
    "ENGL": "United Kingdom",
    "GREAT BRITAIN": "United Kingdom",
    "GREAT BRITAIN AND IRELAND": "United Kingdom",
    "BS": "Bahamas",
    "BHS": "Bahamas",
    "BAHAMAS": "Bahamas",
    "ISR": "Israel",
    "ISRAEL": "Israel",
    "MOR": "Morocco",
    "MOROCCO": "Morocco",
    "CHI": "Chile",
    "ECU": "Ecuador",
    "EGY": "Egypt",
    "NED": "Netherlands",
    "NETH": "Netherlands",
    "NETHL": "Netherlands",
    "NTHL": "Netherlands",
    "HOLLAND": "Netherlands",
    "NETHERLANDS": "Netherlands",
    "PAR": "Paraguay",
    "PARAGUAY": "Paraguay",
    "REUNION": "Reunion",
    "SAF": "South Africa",
    "SOUTH AFRICA": "South Africa",
    "SOL": "Solomon Islands",
    "SOLOMON ISLANDS": "Solomon Islands",
    "VIE": "Vietnam",
    "VIETNAM": "Vietnam",
    "CAN": "Canada",
    "CANADA": "Canada",
}
EXTRA_COUNTRY_REVIEW_BOUNDS = {
    "Bahamas": [(20.0, 28.5, -81.0, -72.0)],
    # Canary Islands plus mainland/Balearic coverage. These are valid Spain
    # coordinates and should not be treated like bad Atlantic sign errors.
    "Spain": [(27.0, 44.0, -19.0, 5.0)],
    # Mainland Portugal plus Madeira/Azores.
    "Portugal": [(30.0, 43.0, -32.0, -6.0)],
    "Ecuador": [(-6.0, 2.0, -82.0, -75.0)],
    "Egypt": [(21.0, 32.5, 24.0, 37.0)],
    "Netherlands": [(50.0, 54.0, 3.0, 8.0)],
    "Paraguay": [(-28.0, -19.0, -63.0, -54.0)],
    "Vietnam": [(8.0, 24.0, 102.0, 110.0)],
    "Solomon Islands": [(-13.0, -5.0, 155.0, 170.0)],
    "South Africa": [(-35.0, -22.0, 16.0, 33.5)],
    # Include Bornholm and nearby Danish Baltic waters used by UFOCAT/Majestic.
    "Denmark": [(54.0, 58.5, 7.0, 16.0)],
    # Include northern Scottish islands such as Shetland and Orkney.
    "United Kingdom": [(49.0, 61.5, -9.0, 3.0)],
}


def check_static_country_coordinate_anomalies(
    *,
    payload_root: Path,
    json_output: Path | None = None,
    csv_output: Path | None = None,
    max_examples: int = 500,
) -> dict[str, Any]:
    payload_root = payload_root.resolve()
    rows: list[dict[str, Any]] = []
    scanned_events = 0
    mapped_events = 0
    explicit_country_rows = 0
    checked_rows = 0
    unsupported_country_counts: dict[str, int] = {}

    for event in iter_static_summary_events(payload_root):
        scanned_events += 1
        lat = float_or_none(event.get("lat"))
        lon = float_or_none(event.get("lon"))
        if lat is None or lon is None:
            continue
        mapped_events += 1
        country = explicit_country_from_location(event.get("location_raw"))
        if not country:
            continue
        explicit_country_rows += 1
        bounds = review_bounds_for_country(country)
        if not bounds:
            unsupported_country_counts[country] = unsupported_country_counts.get(country, 0) + 1
            continue
        checked_rows += 1
        outside_declared_us_state = False
        if country == "United States of America":
            # Prefer reviewed display geography, but fall back to the raw claim
            # so an uncertainty display cannot hide a source-state conflict.
            state = explicit_us_state(
                event.get("location_display")
            ) or explicit_us_state(event.get("location_raw"))
            outside_declared_us_state = bool(
                state and not inside_us_state(state, lat, lon)
            )
        if point_in_any_bounds(lat, lon, bounds) and not outside_declared_us_state:
            continue
        rows.append(anomaly_payload(event, country, lat, lon))

    rows.sort(key=anomaly_sort_key)
    status = "ready" if not rows else "needs_attention"
    report = {
        "schema_version": 1,
        "report_policy": "static_country_coordinate_anomaly_report_only",
        "canonical_outputs_mutated": False,
        "payload_root": str(payload_root),
        "status": status,
        "counts": {
            "scanned_events": scanned_events,
            "mapped_events": mapped_events,
            "explicit_country_rows": explicit_country_rows,
            "checked_rows": checked_rows,
            "anomaly_rows": len(rows),
            "unsupported_country_rows": sum(unsupported_country_counts.values()),
        },
        "anomaly_reason_counts": count_by(rows, "reason"),
        "country_counts": count_by(rows, "country"),
        "source_counts": count_by(rows, "source"),
        "coordinate_source_counts": count_by(rows, "coordinate_source"),
        "unsupported_country_counts": dict(sorted(unsupported_country_counts.items())),
        "examples": rows[:max_examples],
        "notes": [
            "This check uses intentionally broad review bounds, not exact coastlines.",
            "Rows outside these broad bounds are high-priority coordinate QA candidates.",
            (
                "Explicit U.S. state abbreviations and full names are checked even "
                "when the point remains inside broad U.S. bounds."
            ),
            "Ambiguous non-final tokens such as CA are ignored unless a clear final country token follows.",
        ],
    }
    if json_output:
        write_json(json_output, report)
    if csv_output:
        write_csv(csv_output, rows)
    return report


def iter_static_summary_events(payload_root: Path) -> Iterable[dict[str, Any]]:
    summary_dir = payload_root / "data" / "canonical_web" / "summary_shards"
    if not summary_dir.exists():
        raise FileNotFoundError(f"Missing static summary shard directory: {summary_dir}")
    for shard_path in sorted(summary_dir.glob("summary_*.json")):
        payload = json.loads(shard_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"{shard_path} must contain a JSON array.")
        for event in payload:
            if isinstance(event, dict):
                yield event


def explicit_country_from_location(location_raw: Any) -> str | None:
    parts = [str(part).strip().upper().strip(".") for part in str(location_raw or "").split(",")]
    parts = [part for part in parts if part]
    if not parts:
        return None

    if is_baltic_sea_location(parts):
        return None
    if len(parts) <= 2 and parts[-1] == "GEORGIA":
        return None
    if parts[0] == "HOLLAND" and parts[-1] == "CA":
        return "Canada"
    if "BET. TUNIS" in " ".join(parts) and "LY" in parts:
        return None
    if "KITWE" in parts:
        return "Zambia"

    specific_country = specific_country_before_group_label(parts)
    if specific_country:
        return specific_country

    if has_country(parts, "Puerto Rico"):
        return "Puerto Rico"
    if has_country(parts, "Canada") and not has_country(parts, "United States of America"):
        return "Canada"
    if has_country(parts, "New Zealand") and any(token in {"CANTERBURY", "MARLBOROUGH"} for token in parts):
        return "New Zealand"
    if parts[-1] == "AU" and any(token in AUSTRALIAN_STATE_TOKENS for token in parts[:-1]):
        return "Australia"
    if any(token in CANADIAN_PROVINCE_TOKENS for token in parts) and parts[-1] in {"CA", "CN"}:
        return "Canada"

    for index in range(len(parts) - 1, -1, -1):
        token = parts[index]
        if token in REGION_TOKENS and index > 0:
            continue
        if token in AMBIGUOUS_NONFINAL_TOKENS and index != len(parts) - 1:
            continue
        country = LOCAL_COUNTRY_ALIASES.get(token)
        if country:
            if token == "AU" and has_more_specific_country_token_before(parts, index):
                continue
            return country
    return None


def is_baltic_sea_location(parts: list[str]) -> bool:
    return "BS" in parts and any(part in {"EU", "EUR"} for part in parts)


def specific_country_before_group_label(parts: list[str]) -> str | None:
    """Prefer a row's specific token over trailing multi-country group labels."""

    joined = " ".join(parts)
    if "NETHERLANDSAND LUXEMBOURG" in joined or ("NETHERLANDS" in parts and "BELGIUM" in parts):
        country = last_country_before(parts, {"BELGIUM", "NETHERLANDSAND LUXEMBOURG"})
        if country:
            return country
    if "LATVIA& LITHUANIA" in joined or ("ESTONIA" in parts and any(part in parts for part in {"LATVIA", "LITHUANIA"})):
        country = last_country_before(parts, {"ESTONIA", "LATVIA& LITHUANIA"})
        if country:
            return country
    if "GREAT BRITAIN AND IRELAND" in joined:
        if any(token in {"CHI", "ENGL", "ENG", "GUERNSEY", "JERSEY"} for token in parts):
            return "United Kingdom"
        country = last_country_before(parts, {"GREAT BRITAIN AND IRELAND"})
        if country:
            return country
    if "ZIMBABWE & ZAMBIA" in joined:
        if "ZIMBABWE" in parts:
            return "Zimbabwe"
        country = last_country_before(parts, {"ZIMBABWE & ZAMBIA"})
        if country:
            return country
    return None


def last_country_before(parts: list[str], stop_tokens: set[str]) -> str | None:
    for token in reversed(parts):
        if token in stop_tokens:
            continue
        country = LOCAL_COUNTRY_ALIASES.get(token)
        if country:
            return country
    return None


def has_country(parts: list[str], expected_country: str) -> bool:
    return any(LOCAL_COUNTRY_ALIASES.get(part) == expected_country for part in parts)


def has_more_specific_country_token_before(parts: list[str], index: int) -> bool:
    for prior_token in reversed(parts[:index]):
        if prior_token in OCEANIA_COUNTRY_TOKENS_BEFORE_REGION_AU:
            return True
    return False


def review_bounds_for_country(country: str) -> list[tuple[float, float, float, float]]:
    if country in EXTRA_COUNTRY_REVIEW_BOUNDS:
        return EXTRA_COUNTRY_REVIEW_BOUNDS[country]
    if country == "United States of America":
        return [(18.0, 72.0, -180.0, -52.0)]
    review_bounds = COUNTRY_REVIEW_BOUNDS.get(country)
    if review_bounds is not None:
        min_lat, max_lat = review_bounds["lat"]
        return [
            (min_lat, max_lat, min_lon, max_lon)
            for min_lon, max_lon in review_bounds["lon_ranges"]
        ]
    fallback_bounds = BOUNDED_FLIP_LON_RANGES.get(country) or []
    return [
        (bounds["lat"][0], bounds["lat"][1], bounds["lon"][0], bounds["lon"][1])
        for bounds in fallback_bounds
    ]


def point_in_any_bounds(lat: float, lon: float, bounds: list[tuple[float, float, float, float]]) -> bool:
    return any(
        min_lat <= lat <= max_lat and min_lon <= lon <= max_lon
        for min_lat, max_lat, min_lon, max_lon in bounds
    )


def country_min_review_lon(country: str) -> float:
    bounds = review_bounds_for_country(country)
    if not bounds:
        return -20.0
    return min(min_lon for _min_lat, _max_lat, min_lon, _max_lon in bounds)


def anomaly_payload(event: dict[str, Any], country: str, lat: float, lon: float) -> dict[str, Any]:
    coordinate_source = str(event.get("coordinate_source") or "")
    reason = "outside_broad_country_review_bounds"
    if country == "United States of America" and lon > 0:
        reason = "positive_longitude_for_explicit_us_row"
    elif country == "United States of America":
        state = explicit_us_state(event.get("location_raw"))
        if state and not inside_us_state(state, lat, lon):
            reason = "outside_declared_us_state_bounds"
    elif country in WESTERN_HEMISPHERE_COUNTRIES and lon > 0:
        reason = "positive_longitude_for_western_country"
    elif country in EASTERN_HEMISPHERE_COUNTRIES and lon < country_min_review_lon(country) - 2:
        reason = "far_negative_longitude_for_eastern_country"
    elif coordinate_source not in EXACTISH_COORDINATE_SOURCES:
        reason = "non_exact_coordinate_outside_broad_country_review_bounds"

    return {
        "reason": reason,
        "event_id": event.get("event_id"),
        "date": event.get("sort_date_iso") or event.get("date_raw"),
        "location_raw": event.get("location_raw"),
        "source": event.get("source"),
        "country": country,
        "lat": lat,
        "lon": lon,
        "coordinate_source": coordinate_source,
        "location_precision": event.get("location_precision"),
    }


WESTERN_HEMISPHERE_COUNTRIES = {
    "Argentina",
    "Bermuda",
    "Bolivia",
    "Brazil",
    "Bahamas",
    "Canada",
    "Chile",
    "Colombia",
    "Cuba",
    "Dominican Republic",
    "Ecuador",
    "Honduras",
    "Mexico",
    "Paraguay",
    "Peru",
    "Puerto Rico",
    "United States of America",
    "United States Virgin Islands",
    "Uruguay",
    "Venezuela",
}

EASTERN_HEMISPHERE_COUNTRIES = {
    "Austria",
    "Belgium",
    "China",
    "Czech Republic",
    "Denmark",
    "Estonia",
    "Finland",
    "France",
    "Germany",
    "Greece",
    "Italy",
    "Japan",
    "Kazakhstan",
    "Netherlands",
    "Norway",
    "Poland",
    "Romania",
    "Russia",
    "Spain",
    "Solomon Islands",
    "South Africa",
    "Sweden",
    "Switzerland",
    "Ukraine",
}


def explicit_us_state(location_raw: Any) -> str | None:
    parts = [str(part).strip().upper().strip(".") for part in str(location_raw or "").split(",")]
    parts = [part for part in parts if part]
    if len(parts) < 2 or parts[-1] not in {"US", "USA", "UNITED STATES"}:
        return None
    state = parts[-2]
    if state in US_STATE_BOUNDS:
        return state
    return US_STATE_NAME_TO_ABBREVIATION.get(state)


def inside_us_state(state: str, lat: float, lon: float) -> bool:
    min_lat, max_lat, min_lon, max_lon = US_STATE_BOUNDS[state]
    return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon


def anomaly_sort_key(row: dict[str, Any]) -> tuple[int, str, str, str]:
    reason_rank = {
        "positive_longitude_for_explicit_us_row": 0,
        "outside_declared_us_state_bounds": 1,
        "positive_longitude_for_western_country": 2,
        "far_negative_longitude_for_eastern_country": 3,
        "outside_broad_country_review_bounds": 4,
        "non_exact_coordinate_outside_broad_country_review_bounds": 5,
    }
    return (
        reason_rank.get(str(row.get("reason")), 99),
        str(row.get("country") or ""),
        str(row.get("source") or ""),
        str(row.get("location_raw") or ""),
    )


def float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def count_by(rows: Iterable[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "reason",
        "event_id",
        "date",
        "source",
        "country",
        "location_raw",
        "lat",
        "lon",
        "coordinate_source",
        "location_precision",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload-root", type=Path, default=DEFAULT_PAYLOAD_ROOT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--max-examples", type=int, default=500)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = check_static_country_coordinate_anomalies(
        payload_root=args.payload_root,
        json_output=args.json_output,
        csv_output=args.csv_output,
        max_examples=args.max_examples,
    )
    print(
        json.dumps(
            {
                "json": str(args.json_output),
                "csv": str(args.csv_output),
                "status": report["status"],
                "checked_rows": report["counts"]["checked_rows"],
                "anomaly_rows": report["counts"]["anomaly_rows"],
                "canonical_outputs_mutated": report["canonical_outputs_mutated"],
            },
            indent=2,
        )
    )
    return 0 if report["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
