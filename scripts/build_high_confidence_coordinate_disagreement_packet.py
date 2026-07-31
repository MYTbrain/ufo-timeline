"""Build a high-confidence coordinate disagreement review packet.

This report-only lane filters the broad GeoNames coordinate disagreement
queue down to candidates that are safer for human review before any repair
or quarantine action. The broad queue is intentionally noisy: generic names
such as "Hawaii" or "Windward" can match unrelated same-country GeoNames
features. This packet keeps only exact/source-coordinate rows with strong
primary-name evidence and, for US/Canada rows, matching admin-region evidence.

No canonical, preview, static, or deployment artifacts are mutated.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import zipfile
from pathlib import Path
from typing import Any

from scripts.apply_coordinate_sanity_preview import (
    CANADIAN_PROVINCE_CODES,
    EXACT_COORDINATE_SOURCES,
    US_STATE_CODES,
    clean_text,
    parse_float,
    write_json,
)
from scripts.apply_country_polygon_coordinate_repair_preview import (
    EXPLICIT_OFFSHORE_LOCATION_RE,
    SEA_TOWN_SUFFIX_RE,
)
from scripts.summarize_structured_city_alias_geonames_mapping_candidates import city_key


DEFAULT_DISAGREEMENTS_CSV = Path("data/reports/geonames_coordinate_disagreements_v109.csv")
DEFAULT_GEONAMES_ZIP = Path("cache/map_overlays/allCountries.zip")
DEFAULT_JSON = Path("data/reports/high_confidence_coordinate_disagreement_packet.json")
DEFAULT_CSV = Path("data/reports/high_confidence_coordinate_disagreement_packet.csv")

DEFAULT_MIN_DISTANCE_KM = 150.0
DEFAULT_MAX_ROWS = 5000

US_COUNTRY_NAMES = {"United States of America", "United States", "USA", "US"}
CANADA_COUNTRY_NAMES = {"Canada"}
AUSTRALIA_COUNTRY_NAMES = {"Australia"}
CANADIAN_PROVINCE_NORMALIZATION = {
    "ALB": "AB",
    "LAB": "NL",
    "MAN": "MB",
    "NF": "NL",
    "NFL": "NL",
    "NUV": "NU",
    "NWT": "NT",
    "ONT": "ON",
    "PEI": "PE",
    "QUE": "QC",
    "SAS": "SK",
    "YUK": "YT",
}
AUSTRALIAN_STATE_TO_GEONAMES_ADMIN1 = {
    "ACT": "01",
    "NSW": "02",
    "NT": "03",
    "NTE": "03",
    "QLD": "04",
    "SA": "05",
    "SAU": "05",
    "TAS": "06",
    "VIC": "07",
    "WA": "08",
    "WAU": "08",
}

GENERIC_PRIMARY_KEYS = {
    "america",
    "atlantic",
    "bay",
    "central",
    "channel",
    "coast",
    "east",
    "eastern",
    "gulf",
    "hawaii",
    "island",
    "islands",
    "lake",
    "north",
    "northern",
    "ocean",
    "pacific",
    "river",
    "sea",
    "shore",
    "south",
    "southern",
    "unknown",
    "west",
    "western",
    "windward",
}

LOCATION_TOKEN_RE = re.compile(r"\b[A-Za-z]{2,3}\b")


def build_high_confidence_coordinate_disagreement_packet(
    *,
    disagreements_csv: Path,
    geonames_zip: Path,
    json_output: Path,
    csv_output: Path,
    min_distance_km: float = DEFAULT_MIN_DISTANCE_KM,
    max_rows: int = DEFAULT_MAX_ROWS,
) -> dict[str, Any]:
    rows = load_disagreement_rows(disagreements_csv)
    geoname_ids = {clean_text(row.get("geonames_id")) for row in rows if clean_text(row.get("geonames_id"))}
    geonames_by_id = load_geonames_by_id(geonames_zip, geoname_ids)

    accepted: list[dict[str, Any]] = []
    rejected_counts: dict[str, int] = {}
    for row in rows:
        accepted_row, reason = maybe_accept_row(row, geonames_by_id, min_distance_km=min_distance_km)
        if accepted_row is None:
            rejected_counts[reason] = rejected_counts.get(reason, 0) + 1
            continue
        accepted.append(accepted_row)

    accepted.sort(
        key=lambda row: (
            -float(row["distance_km"]),
            clean_text(row.get("country")),
            clean_text(row.get("source_name")),
            clean_text(row.get("location_raw")),
            clean_text(row.get("canonical_event_id")),
        )
    )
    if max_rows > 0:
        accepted = accepted[:max_rows]

    report = {
        "schema_version": 1,
        "mode": "report_only",
        "packet_policy": "high_confidence_coordinate_disagreement_review_only",
        "canonical_outputs_mutated": False,
        "inputs": {
            "disagreements_csv": str(disagreements_csv),
            "geonames_zip": str(geonames_zip),
        },
        "outputs": {
            "json": str(json_output),
            "csv": str(csv_output),
        },
        "thresholds": {
            "min_distance_km": min_distance_km,
            "max_rows": max_rows,
        },
        "input_row_count": len(rows),
        "accepted_count": len(accepted),
        "rejected_counts": dict(sorted(rejected_counts.items())),
        "source_counts": count_by(accepted, "source_name"),
        "country_counts": count_by(accepted, "country"),
        "admin_match_counts": count_by(accepted, "admin_match_kind"),
        "examples": accepted[:200],
        "notes": [
            "Report-only: no canonical, preview, static, or deployment files are mutated.",
            "US and Canada rows require a matching GeoNames admin1 code when a state/province token is present.",
            "Generic primary names such as Hawaii, Windward, Shore, Ocean, and region-only labels are rejected.",
            "This packet is intended as the next human-review input, not an automatic correction list.",
        ],
    }
    write_json(json_output, report)
    write_packet_csv(csv_output, accepted)
    return report


def load_disagreement_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_geonames_by_id(path: Path, needed_ids: set[str]) -> dict[str, dict[str, Any]]:
    if not needed_ids:
        return {}
    result: dict[str, dict[str, Any]] = {}
    with zipfile.ZipFile(path) as archive:
        with archive.open("allCountries.txt") as raw:
            for raw_line in raw:
                line = raw_line.decode("utf-8", errors="replace").rstrip("\n")
                parts = line.split("\t")
                if len(parts) < 19:
                    continue
                geoname_id = parts[0]
                if geoname_id not in needed_ids:
                    continue
                result[geoname_id] = {
                    "geoname_id": geoname_id,
                    "name": parts[1],
                    "ascii_name": parts[2],
                    "lat": parse_float(parts[4]),
                    "lon": parse_float(parts[5]),
                    "feature_class": parts[6].upper(),
                    "feature_code": parts[7],
                    "country_code": parts[8].upper(),
                    "admin1": parts[10].upper(),
                    "population": parse_int(parts[14]),
                    "timezone": parts[17],
                }
    return result


def maybe_accept_row(
    row: dict[str, str],
    geonames_by_id: dict[str, dict[str, Any]],
    *,
    min_distance_km: float,
) -> tuple[dict[str, Any] | None, str]:
    if clean_text(row.get("source_name")).lower() != "ufocat":
        return None, "non_ufocat_source"
    if clean_text(row.get("coordinate_source")) not in EXACT_COORDINATE_SOURCES:
        return None, "not_exact_source_coordinate"
    distance_km = parse_float(row.get("distance_km"))
    if distance_km is None or distance_km < min_distance_km:
        return None, "below_distance_threshold"
    geoname_id = clean_text(row.get("geonames_id"))
    candidate = geonames_by_id.get(geoname_id)
    if candidate is None:
        return None, "missing_geonames_metadata"
    if candidate.get("feature_class") not in {"P", "T", "S", "L"}:
        return None, "unsupported_feature_class"

    location_raw = clean_text(row.get("location_raw"))
    if is_explicit_offshore_text(location_raw):
        return None, "offshore_or_maritime_text"
    primary_text = primary_place(location_raw)
    primary_key = city_key(primary_text)
    geonames_key = city_key(candidate.get("ascii_name") or candidate.get("name"))
    if not primary_key:
        return None, "missing_primary_place"
    if primary_key in GENERIC_PRIMARY_KEYS:
        return None, "generic_primary_place"
    if primary_key != geonames_key:
        return None, "primary_name_mismatch"

    country = clean_text(row.get("country"))
    admin_tokens = admin_tokens_from_location(location_raw, country)
    admin_match_kind = "not_required"
    if country in US_COUNTRY_NAMES or country in CANADA_COUNTRY_NAMES or country in AUSTRALIA_COUNTRY_NAMES:
        if not admin_tokens:
            return None, "missing_admin_token"
        candidate_admin = normalize_admin_code(candidate.get("admin1"), country)
        if candidate_admin not in admin_tokens:
            return None, "admin_token_mismatch"
        admin_match_kind = "matched"

    accepted = {
        "canonical_event_id": row.get("canonical_event_id"),
        "event_id": row.get("event_id"),
        "source_name": row.get("source_name"),
        "source_row_number": row.get("source_row_number"),
        "source_native_id": row.get("source_native_id"),
        "date": row.get("date"),
        "location_raw": row.get("location_raw"),
        "country": country,
        "coordinate_source": row.get("coordinate_source"),
        "location_precision": row.get("location_precision"),
        "lat": parse_float(row.get("lat")),
        "lon": parse_float(row.get("lon")),
        "geonames_name": row.get("geonames_name"),
        "geonames_id": geoname_id,
        "geonames_feature_class": candidate.get("feature_class"),
        "geonames_feature_code": candidate.get("feature_code"),
        "geonames_admin1": candidate.get("admin1"),
        "geonames_lat": parse_float(row.get("geonames_lat")),
        "geonames_lon": parse_float(row.get("geonames_lon")),
        "distance_km": round(float(distance_km), 3),
        "primary_place_key": primary_key,
        "admin_tokens": sorted(admin_tokens),
        "admin_match_kind": admin_match_kind,
        "review_recommendation": "review_coordinate_replace_or_quarantine",
    }
    return accepted, "accepted"


def is_explicit_offshore_text(value: str) -> bool:
    if SEA_TOWN_SUFFIX_RE.search(value):
        return False
    return bool(EXPLICIT_OFFSHORE_LOCATION_RE.search(value))


def primary_place(location_raw: str) -> str:
    return clean_text(location_raw).split(",", 1)[0].strip()


def admin_tokens_from_location(location_raw: str, country: str) -> set[str]:
    parts = [clean_text(part).upper() for part in location_raw.split(",")[1:]]
    tokens = {match.group(0).upper() for part in parts for match in LOCATION_TOKEN_RE.finditer(part)}
    if country in US_COUNTRY_NAMES:
        return {token for token in tokens if token in US_STATE_CODES}
    if country in CANADA_COUNTRY_NAMES:
        return {normalize_admin_code(token, country) for token in tokens if token in CANADIAN_PROVINCE_CODES}
    if country in AUSTRALIA_COUNTRY_NAMES:
        return {
            normalize_admin_code(token, country)
            for token in tokens
            if token in AUSTRALIAN_STATE_TO_GEONAMES_ADMIN1
        }
    return set()


def normalize_admin_code(value: Any, country: str) -> str:
    token = clean_text(value).upper()
    if country in CANADA_COUNTRY_NAMES:
        return CANADIAN_PROVINCE_NORMALIZATION.get(token, token)
    if country in AUSTRALIA_COUNTRY_NAMES:
        return AUSTRALIAN_STATE_TO_GEONAMES_ADMIN1.get(token, token)
    return token


def parse_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = clean_text(row.get(key)) or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def write_packet_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "canonical_event_id",
        "event_id",
        "source_name",
        "source_row_number",
        "source_native_id",
        "date",
        "location_raw",
        "country",
        "coordinate_source",
        "location_precision",
        "lat",
        "lon",
        "geonames_name",
        "geonames_id",
        "geonames_feature_class",
        "geonames_feature_code",
        "geonames_admin1",
        "geonames_lat",
        "geonames_lon",
        "distance_km",
        "primary_place_key",
        "admin_tokens",
        "admin_match_kind",
        "review_recommendation",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            next_row = dict(row)
            next_row["admin_tokens"] = ";".join(row.get("admin_tokens") or [])
            writer.writerow(next_row)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--disagreements-csv", type=Path, default=DEFAULT_DISAGREEMENTS_CSV)
    parser.add_argument("--geonames-zip", type=Path, default=DEFAULT_GEONAMES_ZIP)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--min-distance-km", type=float, default=DEFAULT_MIN_DISTANCE_KM)
    parser.add_argument("--max-rows", type=int, default=DEFAULT_MAX_ROWS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_high_confidence_coordinate_disagreement_packet(
        disagreements_csv=args.disagreements_csv,
        geonames_zip=args.geonames_zip,
        json_output=args.json_output,
        csv_output=args.csv_output,
        min_distance_km=args.min_distance_km,
        max_rows=args.max_rows,
    )
    print(
        json.dumps(
            {
                "json": report["outputs"]["json"],
                "csv": report["outputs"]["csv"],
                "input_row_count": report["input_row_count"],
                "accepted_count": report["accepted_count"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
