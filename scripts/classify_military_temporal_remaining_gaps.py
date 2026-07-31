from __future__ import annotations

import json
import csv
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MAP_OVERLAYS = ROOT / "webapp" / "static_public" / "data" / "map_overlays"
REPORTS = ROOT / "data" / "reports"

NONSTANDARD_NAME_TOKENS = (
    "asrama",
    "barak",
    "barracks",
    "caserne",
    "graveyard",
    "kazarma",
    "kazarmy",
    "lifeguard",
    "masākin",
    "police",
    "quarters",
    "cvn-",
    "uss ",
    "coast guard",
    "seaplane base",
    "airways",
)

DISTANCE_MARKER_PATTERNS = (
    re.compile(r"^\s*\d+\s*km\s*$", re.IGNORECASE),
    re.compile(r"\b\d+\s+kilometr\b", re.IGNORECASE),
    re.compile(r"\bkilometr(?:a)?\b", re.IGNORECASE),
)

LIKELY_BASE_TOKENS = (
    "air base",
    "airbase",
    "air force base",
    "naval air station",
    "army airfield",
    "air national guard",
    "cfb",
    "cfs",
    "base",
    "station",
    "camp",
    "fort",
    "range",
    "aerodrom",
    "airport",
    "airfield",
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def source_id(feature: dict[str, Any]) -> str:
    return str((feature.get("properties") or {}).get("source_id") or "").strip()


def has_temporal_metadata(properties: dict[str, Any]) -> bool:
    if properties.get("start_year") is not None or properties.get("end_year") is not None:
        return True
    intervals = properties.get("operational_intervals") or properties.get("operation_intervals") or properties.get("active_intervals")
    return isinstance(intervals, list) and bool(intervals)


def membership_excluded_source_ids() -> set[str]:
    path = MAP_OVERLAYS / "military_base_overlay_membership_overrides.json"
    if not path.exists():
        return set()
    payload = load_json(path)
    return {
        str(entry.get("source_id") or "").strip()
        for entry in payload.get("overrides") or []
        if entry.get("membership_status") == "exclude_from_military_overlay"
        and str(entry.get("source_id") or "").strip()
    }


def merged_features() -> list[dict[str, Any]]:
    base_payload = load_json(MAP_OVERLAYS / "military_bases.geojson")
    nz_payload = load_json(MAP_OVERLAYS / "new_zealand_military_facilities.geojson")
    base_features = list(base_payload.get("features") or [])
    supplemental_features = list(nz_payload.get("features") or [])
    replacements = {
        str((feature.get("properties") or {}).get("replaces_source_id") or "").strip()
        for feature in supplemental_features
        if str((feature.get("properties") or {}).get("replaces_source_id") or "").strip()
    }
    merged = [feature for feature in base_features if source_id(feature) not in replacements] + supplemental_features
    excluded_ids = membership_excluded_source_ids()
    if excluded_ids:
        merged = [
            feature
            for feature in merged
            if source_id(feature) not in excluded_ids
        ]
    return merged


def classify(properties: dict[str, Any]) -> str:
    name = str(properties.get("name") or "").lower()
    feature_code = str(properties.get("feature_code") or "").upper()
    branch = str(properties.get("branch") or "").lower()
    if any(pattern.search(name) for pattern in DISTANCE_MARKER_PATTERNS):
        return "nonstandard_or_possible_overlay_artifact"
    if any(token in name for token in NONSTANDARD_NAME_TOKENS):
        return "nonstandard_or_possible_overlay_artifact"
    if "S.AIRB" in feature_code or branch == "air":
        return "likely_air_base_or_airfield"
    if any(token in name for token in LIKELY_BASE_TOKENS):
        return "likely_base_or_facility"
    return "needs_manual_classification"


def recommended_action(category: str) -> str:
    if category in {"likely_air_base_or_airfield", "likely_base_or_facility"}:
        return "research_temporal_dates"
    if category == "nonstandard_or_possible_overlay_artifact":
        return "review_overlay_membership_before_date_backfill"
    return "manual_classify_then_research_or_exclude"


def main() -> None:
    override_payload = load_json(MAP_OVERLAYS / "military_base_temporal_overrides.json")
    override_ids = {
        str(entry.get("source_id") or "").strip()
        for entry in override_payload.get("overrides") or []
        if str(entry.get("source_id") or "").strip()
    }
    rows: list[dict[str, Any]] = []
    counts_by_country_and_class: dict[str, Counter[str]] = defaultdict(Counter)
    for feature in merged_features():
        properties = feature.get("properties") or {}
        sid = source_id(feature)
        if sid in override_ids or has_temporal_metadata(properties):
            continue
        country = str(properties.get("country_code") or properties.get("country") or "unknown").strip() or "unknown"
        category = classify(properties)
        counts_by_country_and_class[country][category] += 1
        rows.append({
            "source_id": sid,
            "name": str(properties.get("name") or ""),
            "country_code": country,
            "branch": str(properties.get("branch") or ""),
            "feature_code": str(properties.get("feature_code") or ""),
            "gap_class": category,
            "recommended_action": recommended_action(category),
        })

    rows.sort(key=lambda row: (row["gap_class"], row["country_code"], row["name"], row["source_id"]))
    action_counts = Counter(row["recommended_action"] for row in rows)
    country_class_rows = [
        {
            "country_code": country,
            "gap_class": category,
            "count": count,
        }
        for country, counts in sorted(counts_by_country_and_class.items())
        for category, count in sorted(counts.items())
    ]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "membership_excluded_features": len(membership_excluded_source_ids()),
        "undated_count": len(rows),
        "counts_by_class": dict(Counter(row["gap_class"] for row in rows)),
        "counts_by_recommended_action": dict(action_counts),
        "counts_by_country_and_class": {
            country: dict(counts)
            for country, counts in sorted(counts_by_country_and_class.items())
        },
        "rows": rows,
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "military_base_temporal_remaining_gap_classes.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    with (REPORTS / "military_base_temporal_remaining_gap_classes.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "source_id",
                "name",
                "country_code",
                "branch",
                "feature_code",
                "gap_class",
                "recommended_action",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    with (REPORTS / "military_base_temporal_remaining_gap_class_summary.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["country_code", "gap_class", "count"])
        writer.writeheader()
        writer.writerows(country_class_rows)
    print(json.dumps({
        "membership_excluded_features": report["membership_excluded_features"],
        "undated_count": report["undated_count"],
        "counts_by_class": report["counts_by_class"],
        "counts_by_recommended_action": report["counts_by_recommended_action"],
    }, indent=2))


if __name__ == "__main__":
    main()
