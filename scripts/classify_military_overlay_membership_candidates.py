from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "data" / "reports"
MAP_OVERLAYS = ROOT / "webapp" / "static_public" / "data" / "map_overlays"
REVIEW_CSV = REPORTS / "military_base_overlay_membership_review.csv"


LIKELY_KEEP_TOKENS = (
    "air base",
    "airbase",
    "seaplane base",
    "coast guard base",
    "coast guard detachment",
    "brigade headquarters",
    "batalyon",
    "battalion",
    "infanteri",
    "komando distrik militer",
    "tentara nasional indonesia",
    "quwwāt al musalla",
)

LIKELY_EXCLUDE_TOKENS = (
    "visitors center",
    "staff quarters",
    "naval quarters",
    "residence",
    "polisi",
    "police",
    "kelas layanan khusus",
    "civil airways",
    "lifeguard",
)

HISTORICAL_TOKENS = (
    "historical",
    "ancienne",
    "ancienne caserne",
    "abandonned",
    "abandoned",
)

RAILWAY_OR_DISTANCE_PATTERNS = (
    re.compile(r"\b\d+\s+kilometr\b", re.IGNORECASE),
    re.compile(r"\bkilometr(?:a)?\b", re.IGNORECASE),
    re.compile(r"\bkm\b", re.IGNORECASE),
    re.compile(r"\bnomer\b", re.IGNORECASE),
    re.compile(r"^kazarma\s+\d+", re.IGNORECASE),
)

BARAK_ADMIN_OR_WORKSITE_PATTERNS = (
    re.compile(r"\bkvartal\b", re.IGNORECASE),
    re.compile(r"\buchastka\b", re.IGNORECASE),
    re.compile(r"\bizba\b", re.IGNORECASE),
    re.compile(r"\blesopilka\b", re.IGNORECASE),
    re.compile(r"\blesouchastka\b", re.IGNORECASE),
    re.compile(r"\bkomandirovka\b", re.IGNORECASE),
    re.compile(r"\bzimnik\b", re.IGNORECASE),
    re.compile(r"\bporog\b", re.IGNORECASE),
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_review_rows() -> list[dict[str, str]]:
    with REVIEW_CSV.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def overlay_features_by_source_id() -> dict[str, dict[str, Any]]:
    features: list[dict[str, Any]] = []
    for path in (
        MAP_OVERLAYS / "military_bases.geojson",
        MAP_OVERLAYS / "new_zealand_military_facilities.geojson",
    ):
        if not path.exists():
            continue
        payload = load_json(path)
        features.extend(payload.get("features") or [])
    return {
        str((feature.get("properties") or {}).get("source_id") or "").strip(): feature
        for feature in features
        if str((feature.get("properties") or {}).get("source_id") or "").strip()
    }


def has_any_token(text: str, tokens: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in tokens)


def matches_any_pattern(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def proposed_status(row: dict[str, str], properties: dict[str, Any]) -> tuple[str, str, str]:
    name = str(row.get("name") or "")
    lowered = name.lower()
    review_reason = str(row.get("review_reason") or "")
    feature_code = str(properties.get("feature_code") or "")

    if review_reason in {"civil_airways_business", "lifeguard_or_civil_safety"}:
        return ("exclude_runtime", "active_runtime_exclusion", "Bucket is clear civil/non-facility overlay noise.")

    if review_reason == "indonesian_asrama_quarters_or_dormitory":
        return ("candidate_exclude", "quarters_or_dormitory_artifact", "Asrama rows represent quarters/dormitory/barracks housing rather than base-level facilities.")

    if review_reason == "quarters_or_housing":
        if "headquarters" in lowered or "L.MILB" in feature_code:
            return ("candidate_keep_research_dates", "military_base_feature_code", "Headquarters or Military Base feature code should be researched before exclusion.")
        return ("candidate_exclude", "quarters_or_housing_artifact", "Name indicates housing/quarters rather than a base-level facility.")

    if review_reason == "kazarma_barracks_or_railway_quarters" and matches_any_pattern(name, RAILWAY_OR_DISTANCE_PATTERNS):
        return ("candidate_exclude", "railway_or_distance_marker_barracks", "Kazarma name looks like a distance/rail marker or numbered barracks artifact, not an operational military facility.")

    if review_reason == "nonstandard_feature_code_or_name" and matches_any_pattern(name, RAILWAY_OR_DISTANCE_PATTERNS):
        return ("candidate_exclude", "railway_or_distance_marker_barracks", "Name looks like a distance/rail marker artifact, not an operational military facility.")

    if review_reason == "russian_barak_barracks_or_camp" and (
        matches_any_pattern(name, RAILWAY_OR_DISTANCE_PATTERNS)
        or matches_any_pattern(name, BARAK_ADMIN_OR_WORKSITE_PATTERNS)
    ):
        return ("candidate_exclude", "worksite_or_distance_marker_barracks", "Barak name looks like a distance marker, administrative unit, or worksite artifact rather than an operational military facility.")

    if review_reason == "coast_guard_station":
        if "historical" in lowered or "residence" in lowered:
            return ("candidate_exclude", "historical_or_residential_coast_guard_artifact", "Historical or residential Coast Guard row should not act as an active base/facility.")
        return ("candidate_keep_research_dates", "possible_operational_security_or_air_site", "Active-looking Coast Guard station/outpost/detachment needs dates before exclusion.")

    if review_reason == "seaplane_or_civil_air_service":
        return ("candidate_keep_research_dates", "possible_operational_air_site", "Seaplane base can be an operational air site; research dates before exclusion.")

    if review_reason == "nonstandard_feature_code_or_name":
        if "ancienne" in lowered or "former" in lowered or "historical" in lowered or "masākin" in lowered or "masakin" in lowered:
            return ("candidate_exclude", "former_or_housing_barracks_artifact", "Former or housing-style barracks row should not act as an active base/facility.")
        if "caserne" in lowered:
            return ("candidate_keep_research_dates", "possible_operational_barracks", "Active-looking Caserne row needs dates before exclusion.")

    if review_reason == "barracks_or_historical_barracks":
        if "historical" in lowered or "abandonned" in lowered or "abandoned" in lowered or "visitors center" in lowered:
            return ("candidate_exclude", "historical_or_nonbase_barracks_artifact", "Historical, abandoned, or visitor-center barracks row should not act as an active base/facility.")
        return ("candidate_keep_research_dates", "possible_operational_barracks", "Named barracks without explicit historical/support signal need dates before exclusion.")

    if has_any_token(lowered, LIKELY_EXCLUDE_TOKENS):
        return ("candidate_exclude", "civil_or_non_operational_support_site", "Name indicates civil service, police, residence, visitor center, or staff housing rather than a base/facility.")

    if has_any_token(lowered, LIKELY_KEEP_TOKENS):
        return ("candidate_keep_research_dates", "military_or_security_facility_name", "Name contains military/security facility terms that should be researched before exclusion.")

    if "L.MILB" in feature_code:
        return ("candidate_keep_research_dates", "military_base_feature_code", "GeoNames feature code is Military Base; research dates before exclusion.")

    if has_any_token(lowered, HISTORICAL_TOKENS):
        return ("manual_review_historical", "historical_facility", "Historical facility needs individual decision: date and preserve if relevant, otherwise exclude.")

    if review_reason in {"coast_guard_station", "seaplane_or_civil_air_service"}:
        return ("manual_review_operational", "possible_operational_security_or_air_site", "Bucket can include operational security/air sites; do not exclude without row-level review.")

    if review_reason in {"barracks_or_historical_barracks", "nonstandard_feature_code_or_name", "indonesian_asrama_quarters_or_dormitory"}:
        return ("manual_review_mixed", "mixed_barracks_or_quarters", "Bucket is mixed; row needs evidence before keep/exclude.")

    return ("manual_review_mixed", "unclassified_mixed_bucket", "No safe automated classification rule matched.")


def main() -> None:
    features_by_id = overlay_features_by_source_id()
    rows: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    status_by_review_reason: dict[str, Counter[str]] = defaultdict(Counter)

    for row in load_review_rows():
        source_id = str(row.get("source_id") or "").strip()
        feature = features_by_id.get(source_id) or {}
        properties = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates") or []
        status, classification_reason, note = proposed_status(row, properties)
        status_counts[status] += 1
        reason_counts[classification_reason] += 1
        status_by_review_reason[str(row.get("review_reason") or "")][status] += 1
        rows.append(
            {
                "source_id": source_id,
                "name": row.get("name") or "",
                "country_code": row.get("country_code") or "",
                "review_reason": row.get("review_reason") or "",
                "feature_code": str(properties.get("feature_code") or row.get("feature_code") or ""),
                "branch": str(properties.get("branch") or row.get("branch") or ""),
                "type": str(properties.get("type") or ""),
                "longitude": coordinates[0] if isinstance(coordinates, list) and len(coordinates) >= 2 else "",
                "latitude": coordinates[1] if isinstance(coordinates, list) and len(coordinates) >= 2 else "",
                "proposed_membership_status": status,
                "classification_reason": classification_reason,
                "classification_note": note,
            }
        )

    rows.sort(
        key=lambda row: (
            row["proposed_membership_status"],
            row["classification_reason"],
            row["country_code"],
            row["name"],
            row["source_id"],
        )
    )
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input": str(REVIEW_CSV.relative_to(ROOT)).replace("\\", "/"),
        "row_count": len(rows),
        "status_counts": dict(sorted(status_counts.items())),
        "classification_reason_counts": dict(sorted(reason_counts.items())),
        "status_by_review_reason": {
            key: dict(sorted(value.items()))
            for key, value in sorted(status_by_review_reason.items())
        },
        "rows": rows,
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "military_base_overlay_membership_classification.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    with (REPORTS / "military_base_overlay_membership_classification.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)

    print(json.dumps({
        "row_count": report["row_count"],
        "status_counts": report["status_counts"],
        "classification_reason_counts": report["classification_reason_counts"],
    }, indent=2))


if __name__ == "__main__":
    main()
