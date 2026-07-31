"""Report source-coordinate disagreements from the served canonical web payload.

Older disagreement reports were generated from preview JSONL inputs. This
script reads the currently shipped ``data/canonical_web/summary_shards`` rows
so follow-up coordinate repair lanes start from the same payload the app
renders.

Report-only: no canonical, static, preview, or deployment artifacts are mutated.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

from scripts.apply_coordinate_sanity_preview import (
    COUNTRY_ALIASES,
    EXACT_COORDINATE_SOURCES,
    REGION_COUNTRY_ALIASES,
    clean_text,
    parse_float,
    write_json,
)
from scripts.apply_country_polygon_coordinate_repair_preview import (
    best_country_candidate,
    cleaned_city_keys,
    is_offshore_like,
    load_country_code_aliases,
    load_country_index,
    load_relevant_geonames_index,
    primary_place_text,
)


DEFAULT_ARTIFACT_DIR = Path("data/canonical_web")
DEFAULT_COUNTRIES = Path("static_bundle/data/world_countries.geojson")
DEFAULT_COUNTRY_INFO = Path("cache/map_overlays/countryInfo.txt")
DEFAULT_GEONAMES_ZIP = Path("cache/map_overlays/allCountries.zip")
DEFAULT_JSON = Path("data/reports/served_geonames_coordinate_disagreements_v111.json")
DEFAULT_CSV = Path("data/reports/served_geonames_coordinate_disagreements_v111.csv")


def summarize_served_geonames_coordinate_disagreements(
    *,
    artifact_dir: Path,
    countries_geojson: Path,
    country_info: Path,
    geonames_zip: Path,
    json_output: Path,
    csv_output: Path,
    min_distance_km: float = 75.0,
    max_examples: int = 1000,
) -> dict[str, Any]:
    country_index = load_country_index(countries_geojson)
    country_codes = load_country_code_aliases(country_info)
    candidates = collect_candidate_rows(artifact_dir, country_codes)
    needed_keys = {
        (candidate["country_code"], key)
        for candidate in candidates
        for key in candidate["city_keys"]
    }
    geonames_index = load_relevant_geonames_index(geonames_zip, needed_keys, country_index, country_codes)

    rows: list[dict[str, Any]] = []
    same_country_match_count = 0
    for candidate_row in candidates:
        geonames_candidate = best_country_candidate(candidate_row, geonames_index)
        if geonames_candidate is None:
            continue
        same_country_match_count += 1
        distance_km = haversine_km(
            candidate_row["lat"],
            candidate_row["lon"],
            geonames_candidate["lat"],
            geonames_candidate["lon"],
        )
        if distance_km < min_distance_km:
            continue
        rows.append(disagreement_payload(candidate_row, geonames_candidate, distance_km))

    rows.sort(key=lambda row: (-row["distance_km"], row["country"], row["source"], row["location_raw"]))
    write_csv(csv_output, rows)
    report = {
        "schema_version": 1,
        "mode": "report_only",
        "canonical_outputs_mutated": False,
        "inputs": {
            "artifact_dir": str(artifact_dir),
            "countries_geojson": str(countries_geojson),
            "country_info": str(country_info),
            "geonames_zip": str(geonames_zip),
        },
        "outputs": {
            "json": str(json_output),
            "csv": str(csv_output),
        },
        "candidate_row_count": len(candidates),
        "same_country_geonames_match_count": same_country_match_count,
        "min_distance_km": min_distance_km,
        "disagreement_count": len(rows),
        "source_counts": count_by(rows, "source"),
        "country_counts": count_by(rows, "country"),
        "coordinate_source_counts": count_by(rows, "coordinate_source"),
        "feature_class_counts": count_by(rows, "geonames_feature_class"),
        "examples": rows[:max_examples],
        "notes": [
            "Report-only: no canonical, preview, static, or deployment files are mutated.",
            "Rows are read from served canonical_web summary shards, not stale preview JSONL.",
            "Rows with explicit offshore/sea/island-like wording are excluded.",
            "Distances compare current mapped coordinates to a same-country GeoNames match for the primary place name.",
            "This is a mining queue, not an automatic repair list; duplicate place names can produce false positives.",
        ],
    }
    write_json(json_output, report)
    return report


def collect_candidate_rows(artifact_dir: Path, country_codes: dict[str, str]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for row in iter_summary_rows(artifact_dir):
        coordinate_source = clean_text(row.get("coordinate_source"))
        if coordinate_source not in EXACT_COORDINATE_SOURCES:
            continue
        lat = parse_float(row.get("lat"))
        lon = parse_float(row.get("lon"))
        if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        country_name = infer_country_from_location_raw(row.get("location_raw"))
        if not country_name:
            continue
        country_code = country_codes.get(country_name) or country_codes.get(country_name.upper())
        if not country_code:
            continue
        primary_text = primary_place_text(row)
        if is_offshore_like(row, primary_text):
            continue
        city_keys = cleaned_city_keys(primary_text)
        if not city_keys:
            continue
        candidates.append(
            {
                "row": row,
                "event_id": row.get("event_id"),
                "chunk_id": row.get("chunk_id"),
                "detail_index": row.get("detail_index"),
                "country_name": country_name,
                "country_code": country_code,
                "lat": lat,
                "lon": lon,
                "primary_text": primary_text,
                "city_keys": city_keys,
            }
        )
    return candidates


def iter_summary_rows(artifact_dir: Path) -> list[dict[str, Any]]:
    manifest_path = artifact_dir / "summary_manifest.json"
    if manifest_path.exists():
        entries = json.loads(manifest_path.read_text(encoding="utf-8"))
        files = [resolve_summary_shard_path(artifact_dir, str(entry["file"])) for entry in entries]
    else:
        files = sorted((artifact_dir / "summary_shards").glob("summary_*.json"))
    for path in files:
        if not path.exists() and not path.is_absolute():
            path = artifact_dir / "summary_shards" / path.name
        rows = json.loads(path.read_text(encoding="utf-8"))
        for row in rows:
            yield row


def resolve_summary_shard_path(artifact_dir: Path, file_name: str) -> Path:
    path = artifact_dir / file_name
    if path.exists():
        return path
    return artifact_dir / "summary_shards" / Path(file_name).name


def infer_country_from_location_raw(value: Any) -> str | None:
    parts = [clean_text(part).upper() for part in clean_text(value).split(",") if clean_text(part)]
    for part in reversed(parts):
        if part in REGION_COUNTRY_ALIASES:
            country = REGION_COUNTRY_ALIASES[part]
            if country:
                return country
            continue
        if part in COUNTRY_ALIASES and part not in {"CA", "AU"}:
            return COUNTRY_ALIASES[part]
    return None


def disagreement_payload(candidate_row: dict[str, Any], candidate: dict[str, Any], distance_km: float) -> dict[str, Any]:
    row = candidate_row["row"]
    return {
        "event_id": row.get("event_id"),
        "chunk_id": row.get("chunk_id"),
        "detail_index": row.get("detail_index"),
        "source": row.get("source"),
        "date": row.get("sort_date_iso") or row.get("date_raw"),
        "location_raw": row.get("location_raw"),
        "country": candidate_row["country_name"],
        "coordinate_source": row.get("coordinate_source"),
        "location_precision": row.get("location_precision"),
        "lat": candidate_row["lat"],
        "lon": candidate_row["lon"],
        "geonames_name": candidate.get("name"),
        "geonames_id": candidate.get("geoname_id"),
        "geonames_feature_class": candidate.get("feature_class"),
        "geonames_feature_code": candidate.get("feature_code"),
        "geonames_admin1": candidate.get("admin1"),
        "geonames_lat": candidate.get("lat"),
        "geonames_lon": candidate.get("lon"),
        "distance_km": round(distance_km, 3),
        "review_recommendation": "review_coordinate_replace_or_quarantine",
    }


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    return 2 * radius_km * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = clean_text(row.get(key)) or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "event_id",
        "chunk_id",
        "detail_index",
        "source",
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
        "review_recommendation",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--countries-geojson", type=Path, default=DEFAULT_COUNTRIES)
    parser.add_argument("--country-info", type=Path, default=DEFAULT_COUNTRY_INFO)
    parser.add_argument("--geonames-zip", type=Path, default=DEFAULT_GEONAMES_ZIP)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--min-distance-km", type=float, default=75.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = summarize_served_geonames_coordinate_disagreements(
        artifact_dir=args.artifact_dir,
        countries_geojson=args.countries_geojson,
        country_info=args.country_info,
        geonames_zip=args.geonames_zip,
        json_output=args.json_output,
        csv_output=args.csv_output,
        min_distance_km=args.min_distance_km,
    )
    print(
        json.dumps(
            {
                "json": report["outputs"]["json"],
                "csv": report["outputs"]["csv"],
                "candidate_row_count": report["candidate_row_count"],
                "same_country_geonames_match_count": report["same_country_geonames_match_count"],
                "disagreement_count": report["disagreement_count"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
