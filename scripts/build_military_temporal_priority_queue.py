from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MAP_OVERLAYS = ROOT / "webapp" / "static_public" / "data" / "map_overlays"
REPORTS = ROOT / "data" / "reports"
BACKFILL_REPORT_GLOB = "military_base_temporal_backfill_*.json"

HIGH_VALUE_COUNTRY_ORDER = {
    "US": 100,
    "CA": 95,
    "GB": 90,
    "FR": 88,
    "DE": 86,
    "GU": 84,
    "JP": 82,
    "KR": 80,
    "NZ": 78,
    "AU": 76,
    "RU": 72,
    "CN": 70,
    "KZ": 68,
    "UA": 66,
    "BY": 64,
    "PL": 62,
    "CZ": 61,
    "RO": 60,
    "EG": 58,
    "PK": 56,
    "IN": 55,
    "IR": 54,
    "SY": 53,
    "LY": 52,
    "IQ": 51,
    "SA": 50,
}

BRANCH_WEIGHT = {
    "air": 30,
    "naval": 24,
    "army": 18,
    "base": 16,
}

NONSTANDARD_NAME_TOKENS = (
    "asrama",
    "barak",
    "barracks",
    "caserne",
    "graveyard",
    "kazarma",
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

ACTION_SORT_RANK = {
    "research_temporal_dates": 0,
    "manual_classify_then_research_or_exclude": 1,
    "review_overlay_membership_before_date_backfill": 2,
}

RESEARCH_STATUS_SORT_RANK = {
    "not_researched": 0,
    "previously_candidate": 1,
    "previously_skipped_no_safe_date": 2,
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_research_dispositions() -> dict[str, dict[str, Any]]:
    dispositions: dict[str, dict[str, Any]] = {}
    for path in sorted(REPORTS.glob(BACKFILL_REPORT_GLOB)):
        try:
            payload = load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        for entry in candidate_research_entries(payload):
            source_id = str(entry.get("source_id") or "").strip()
            if not source_id:
                continue
            disposition = dispositions.setdefault(
                source_id,
                {
                    "candidate_reports": [],
                    "skipped_reports": [],
                },
            )
            disposition["candidate_reports"].append(path.name)
        for entry in skipped_research_entries(payload):
            source_id = str(entry.get("source_id") or "").strip()
            if not source_id:
                continue
            disposition = dispositions.setdefault(
                source_id,
                {
                    "candidate_reports": [],
                    "skipped_reports": [],
                },
            )
            disposition["skipped_reports"].append(path.name)
    return dispositions


def candidate_research_entries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for key in ("candidates", "candidate_overrides", "overrides"):
        value = payload.get(key)
        if isinstance(value, list):
            entries.extend(entry for entry in value if isinstance(entry, dict))
    return entries


def skipped_research_entries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for key in ("skipped", "no_override"):
        value = payload.get(key)
        if isinstance(value, list):
            entries.extend(entry for entry in value if isinstance(entry, dict))
    for entry in candidate_research_entries(payload):
        if entry.get("no_override") is True:
            entries.append(entry)
    return entries


def feature_source_id(feature: dict[str, Any]) -> str:
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


def classify_gap(properties: dict[str, Any]) -> str:
    name = str(properties.get("name") or "").lower()
    feature_code = str(properties.get("feature_code") or "").upper()
    branch = str(properties.get("branch") or "").lower()
    if any(token in name for token in NONSTANDARD_NAME_TOKENS):
        return "nonstandard_or_possible_overlay_artifact"
    if "S.AIRB" in feature_code or branch == "air":
        return "likely_air_base_or_airfield"
    if any(token in name for token in LIKELY_BASE_TOKENS):
        return "likely_base_or_facility"
    return "needs_manual_classification"


def recommended_action(gap_class: str) -> str:
    if gap_class in {"likely_air_base_or_airfield", "likely_base_or_facility"}:
        return "research_temporal_dates"
    if gap_class == "nonstandard_or_possible_overlay_artifact":
        return "review_overlay_membership_before_date_backfill"
    return "manual_classify_then_research_or_exclude"


def merged_overlay_features() -> list[dict[str, Any]]:
    base_payload = load_json(MAP_OVERLAYS / "military_bases.geojson")
    nz_payload = load_json(MAP_OVERLAYS / "new_zealand_military_facilities.geojson")
    base_features = list(base_payload.get("features") or [])
    supplemental_features = list(nz_payload.get("features") or [])

    replacement_source_ids = {
        str((feature.get("properties") or {}).get("replaces_source_id") or "").strip()
        for feature in supplemental_features
        if str((feature.get("properties") or {}).get("replaces_source_id") or "").strip()
    }
    merged = [
        feature
        for feature in base_features
        if feature_source_id(feature) not in replacement_source_ids
    ] + supplemental_features
    excluded_ids = membership_excluded_source_ids()
    if excluded_ids:
        merged = [
            feature
            for feature in merged
            if feature_source_id(feature) not in excluded_ids
        ]
    return merged


def priority_score(properties: dict[str, Any], unknowns_by_country: Counter[str]) -> int:
    country_code = str(properties.get("country_code") or properties.get("country") or "unknown").strip() or "unknown"
    branch = str(properties.get("branch") or "").lower()
    feature_code = str(properties.get("feature_code") or "").upper()
    name = str(properties.get("name") or "").lower()

    score = HIGH_VALUE_COUNTRY_ORDER.get(country_code, 20)
    score += min(unknowns_by_country[country_code], 120) // 4
    score += BRANCH_WEIGHT.get(branch, 0)

    if "AIRB" in feature_code or "air" in name:
        score += 12
    if "naval" in name or "navy" in name or "nav" in branch:
        score += 8
    if any(token in name for token in ("base", "station", "field", "fort", "camp", "range", "airport", "airfield")):
        score += 5
    if str(properties.get("source_id") or "").startswith("geonames:"):
        score += 2
    return score


def main() -> None:
    features = merged_overlay_features()
    research_dispositions = load_research_dispositions()
    overrides_payload = load_json(MAP_OVERLAYS / "military_base_temporal_overrides.json")
    override_source_ids = {
        str(entry.get("source_id") or "").strip()
        for entry in list(overrides_payload.get("overrides") or [])
        if str(entry.get("source_id") or "").strip()
    }

    unknown_features: list[dict[str, Any]] = []
    unknowns_by_country: Counter[str] = Counter()
    for feature in features:
        properties = feature.get("properties") or {}
        source_id = feature_source_id(feature)
        if source_id in override_source_ids or has_temporal_metadata(properties):
            continue
        country_code = str(properties.get("country_code") or properties.get("country") or "unknown").strip() or "unknown"
        unknown_features.append(feature)
        unknowns_by_country[country_code] += 1

    queue_rows: list[dict[str, Any]] = []
    for feature in unknown_features:
        properties = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates") or [None, None]
        gap_class = classify_gap(properties)
        action = recommended_action(gap_class)
        research_disposition = research_dispositions.get(feature_source_id(feature), {})
        candidate_reports = list(research_disposition.get("candidate_reports") or [])
        skipped_reports = list(research_disposition.get("skipped_reports") or [])
        if skipped_reports:
            prior_research_status = "previously_skipped_no_safe_date"
        elif candidate_reports:
            prior_research_status = "previously_candidate"
        else:
            prior_research_status = "not_researched"
        row = {
            "priority_score": priority_score(properties, unknowns_by_country),
            "source_id": feature_source_id(feature),
            "name": str(properties.get("name") or ""),
            "country": str(properties.get("country") or ""),
            "country_code": str(properties.get("country_code") or properties.get("country") or "unknown").strip() or "unknown",
            "branch": str(properties.get("branch") or ""),
            "type": str(properties.get("type") or ""),
            "feature_code": str(properties.get("feature_code") or ""),
            "gap_class": gap_class,
            "recommended_action": action,
            "prior_research_status": prior_research_status,
            "prior_candidate_reports": ";".join(candidate_reports),
            "prior_skipped_reports": ";".join(skipped_reports),
            "longitude": coordinates[0] if len(coordinates) >= 1 else None,
            "latitude": coordinates[1] if len(coordinates) >= 2 else None,
            "suggested_search": " ".join(
                part
                for part in [
                    str(properties.get("name") or ""),
                    str(properties.get("country") or ""),
                    "military base history opened closed established",
                ]
                if part
            ),
        }
        queue_rows.append(row)

    queue_rows.sort(
        key=lambda row: (
            ACTION_SORT_RANK.get(str(row["recommended_action"]), 99),
            RESEARCH_STATUS_SORT_RANK.get(str(row["prior_research_status"]), 99),
            -int(row["priority_score"]),
            row["country_code"],
            row["name"],
            row["source_id"],
        )
    )

    by_country: dict[str, dict[str, Any]] = defaultdict(lambda: {"unknown_count": 0, "top_candidates": []})
    for row in queue_rows:
        country = row["country_code"]
        by_country[country]["unknown_count"] += 1
        if len(by_country[country]["top_candidates"]) < 20:
            by_country[country]["top_candidates"].append(row)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "membership_excluded_features": len(membership_excluded_source_ids()),
        "total_unknown_temporal_features": len(queue_rows),
        "research_disposition_counts": [
            {"prior_research_status": status, "count": count}
            for status, count in sorted(Counter(str(row["prior_research_status"]) for row in queue_rows).items())
        ],
        "country_unknown_counts": [
            {"country_code": country_code, "unknown_count": count}
            for country_code, count in sorted(unknowns_by_country.items(), key=lambda item: (-item[1], item[0]))
        ],
        "top_priority_queue": queue_rows[:250],
        "by_country": dict(sorted(by_country.items(), key=lambda item: (-item[1]["unknown_count"], item[0]))),
    }

    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "military_base_temporal_priority_queue.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    with (REPORTS / "military_base_temporal_priority_queue.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "priority_score",
                "source_id",
                "name",
                "country",
                "country_code",
                "branch",
                "type",
                "feature_code",
                "gap_class",
                "recommended_action",
                "prior_research_status",
                "prior_candidate_reports",
                "prior_skipped_reports",
                "longitude",
                "latitude",
                "suggested_search",
            ],
        )
        writer.writeheader()
        writer.writerows(queue_rows)

    print(json.dumps({
        "membership_excluded_features": report["membership_excluded_features"],
        "total_unknown_temporal_features": len(queue_rows),
        "top_country_gaps": report["country_unknown_counts"][:12],
        "research_disposition_counts": report["research_disposition_counts"],
        "top_priority_count": len(report["top_priority_queue"]),
    }, indent=2))


if __name__ == "__main__":
    main()
