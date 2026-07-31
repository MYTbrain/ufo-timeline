from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "data" / "reports"
SOURCE_MAP_OVERLAYS = ROOT / "webapp" / "static_public" / "data" / "map_overlays"
BUNDLE_MAP_OVERLAYS = ROOT / "static_bundle" / "data" / "map_overlays"
REVIEW_CSV = REPORTS / "military_base_overlay_membership_review.csv"
CLASSIFICATION_CSV = REPORTS / "military_base_overlay_membership_classification.csv"
RESEARCHED_EXCLUSIONS_JSON = REPORTS / "military_base_overlay_membership_researched_exclusions.json"
OUTPUT_NAME = "military_base_overlay_membership_overrides.json"

# Bucket-wide runtime exclusions are deliberately conservative. Mixed buckets
# such as barracks, coast guard stations, and translated military quarters stay
# in the manual-review layer until reviewed individually.
AUTO_EXCLUDE_REASONS = {
    "civil_airways_business",
    "lifeguard_or_civil_safety",
}


def load_review_rows() -> list[dict[str, str]]:
    with REVIEW_CSV.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_classification_rows() -> dict[str, dict[str, str]]:
    if not CLASSIFICATION_CSV.exists():
        return {}
    with CLASSIFICATION_CSV.open("r", encoding="utf-8", newline="") as handle:
        return {
            str(row.get("source_id") or "").strip(): row
            for row in csv.DictReader(handle)
            if str(row.get("source_id") or "").strip()
        }


def load_researched_exclusions() -> dict[str, dict[str, Any]]:
    if not RESEARCHED_EXCLUSIONS_JSON.exists():
        return {}
    try:
        payload = json.loads(RESEARCHED_EXCLUSIONS_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    exclusions: dict[str, dict[str, Any]] = {}
    for entry in payload.get("exclusions") or []:
        if not isinstance(entry, dict):
            continue
        source_id = str(entry.get("source_id") or "").strip()
        if source_id:
            exclusions[source_id] = entry
    return exclusions


def load_existing_runtime_exclusions() -> dict[str, dict[str, Any]]:
    path = SOURCE_MAP_OVERLAYS / OUTPUT_NAME
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    exclusions: dict[str, dict[str, Any]] = {}
    for entry in payload.get("overrides") or []:
        source_id = str(entry.get("source_id") or "").strip()
        if not source_id:
            continue
        if entry.get("membership_status") == "exclude_from_military_overlay":
            exclusions[source_id] = dict(entry)
    return exclusions


def load_overlay_source_ids() -> set[str]:
    payload = json.loads((SOURCE_MAP_OVERLAYS / "military_bases.geojson").read_text(encoding="utf-8"))
    source_ids = {
        str((feature.get("properties") or {}).get("source_id") or "").strip()
        for feature in payload.get("features") or []
    }
    supplemental_path = SOURCE_MAP_OVERLAYS / "new_zealand_military_facilities.geojson"
    if supplemental_path.exists():
        supplemental = json.loads(supplemental_path.read_text(encoding="utf-8"))
        source_ids.update(
            str((feature.get("properties") or {}).get("source_id") or "").strip()
            for feature in supplemental.get("features") or []
        )
    return {source_id for source_id in source_ids if source_id}


def build_override_payload(rows: list[dict[str, str]]) -> dict[str, Any]:
    overlay_source_ids = load_overlay_source_ids()
    existing_exclusions = load_existing_runtime_exclusions()
    classifications = load_classification_rows()
    researched_exclusions = load_researched_exclusions()
    seen_review_ids: set[str] = set()
    overrides: list[dict[str, Any]] = []
    review_candidates: list[dict[str, Any]] = []
    skipped_missing_ids: list[dict[str, str]] = []

    for row in rows:
        source_id = str(row.get("source_id") or "").strip()
        review_reason = str(row.get("review_reason") or "").strip()
        if not source_id:
            continue
        seen_review_ids.add(source_id)
        if source_id not in overlay_source_ids:
            skipped_missing_ids.append(
                {
                    "source_id": source_id,
                    "name": str(row.get("name") or ""),
                    "review_reason": review_reason,
                }
            )
            continue
        entry = {
            "source_id": source_id,
            "name": str(row.get("name") or ""),
            "country_code": str(row.get("country_code") or ""),
            "review_reason": review_reason,
        }
        researched_exclusion = researched_exclusions.get(source_id)
        if researched_exclusion:
            overrides.append(
                {
                    **entry,
                    "membership_status": "exclude_from_military_overlay",
                    "confidence": str(researched_exclusion.get("confidence") or "medium"),
                    "membership_reason": str(
                        researched_exclusion.get("membership_reason") or "researched_non_military_facility"
                    ),
                    "review_classification_status": "researched_exclusion",
                    "notes": str(researched_exclusion.get("notes") or ""),
                    "source_urls": list(researched_exclusion.get("source_urls") or []),
                }
            )
            continue
        classification = classifications.get(source_id) or {}
        classification_status = str(classification.get("proposed_membership_status") or "").strip()
        membership_reason = str(classification.get("classification_reason") or review_reason).strip()
        if review_reason in AUTO_EXCLUDE_REASONS or classification_status == "candidate_exclude":
            overrides.append(
                {
                    **entry,
                    "membership_status": "exclude_from_military_overlay",
                    "confidence": "high",
                    "membership_reason": membership_reason,
                    "review_classification_status": classification_status or "bucket_auto_exclude",
                    "notes": str(
                        classification.get("classification_note")
                        or "Runtime-only exclusion for a high-confidence non-facility artifact. Raw GeoJSON is unchanged."
                    ),
                }
            )
        else:
            review_candidates.append(
                {
                    **entry,
                    "membership_status": "manual_review_required",
                    "membership_reason": membership_reason,
                    "review_classification_status": classification_status or "unclassified",
                    "classification_note": str(classification.get("classification_note") or ""),
                }
            )

    emitted_override_ids = {
        str(entry.get("source_id") or "").strip()
        for entry in overrides
        if str(entry.get("source_id") or "").strip()
    }
    for source_id, researched_exclusion in researched_exclusions.items():
        if source_id in seen_review_ids or source_id not in overlay_source_ids or source_id in emitted_override_ids:
            continue
        overrides.append(
            {
                "source_id": source_id,
                "name": str(researched_exclusion.get("name") or ""),
                "country_code": str(researched_exclusion.get("country_code") or ""),
                "review_reason": "researched_row_level_exclusion",
                "membership_status": "exclude_from_military_overlay",
                "confidence": str(researched_exclusion.get("confidence") or "medium"),
                "membership_reason": str(
                    researched_exclusion.get("membership_reason") or "researched_non_military_facility"
                ),
                "review_classification_status": "researched_exclusion",
                "notes": str(researched_exclusion.get("notes") or ""),
                "source_urls": list(researched_exclusion.get("source_urls") or []),
            }
        )
        emitted_override_ids.add(source_id)

    for source_id, entry in existing_exclusions.items():
        if source_id in seen_review_ids or source_id not in overlay_source_ids or source_id in emitted_override_ids:
            continue
        overrides.append(entry)
        emitted_override_ids.add(source_id)

    overrides.sort(key=lambda entry: (entry["membership_reason"], entry["country_code"], entry["name"], entry["source_id"]))
    review_candidates.sort(key=lambda entry: (entry["membership_reason"], entry["country_code"], entry["name"], entry["source_id"]))
    counts_by_reason = Counter(str(entry["membership_reason"]) for entry in overrides)
    candidate_counts_by_reason = Counter(str(entry["membership_reason"]) for entry in review_candidates)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "description": (
            "Runtime-only military overlay membership overrides. Excluded entries are high-confidence "
            "non-facility artifacts from the overlay review layer; raw source GeoJSON remains intact."
        ),
        "match_key": "source_id",
        "auto_exclude_reasons": sorted(AUTO_EXCLUDE_REASONS),
        "overrides": overrides,
        "manual_review_candidates": review_candidates,
        "summary": {
            "runtime_exclusion_count": len(overrides),
            "manual_review_candidate_count": len(review_candidates),
            "skipped_missing_overlay_source_id_count": len(skipped_missing_ids),
            "runtime_exclusions_by_reason": dict(sorted(counts_by_reason.items())),
            "manual_review_candidates_by_reason": dict(sorted(candidate_counts_by_reason.items())),
        },
    }


def write_payload(payload: dict[str, Any], target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / OUTPUT_NAME).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    rows = load_review_rows()
    payload = build_override_payload(rows)
    write_payload(payload, SOURCE_MAP_OVERLAYS)
    write_payload(payload, BUNDLE_MAP_OVERLAYS)
    print(json.dumps(payload["summary"], indent=2))


if __name__ == "__main__":
    main()
