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


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def feature_source_id(feature: dict[str, Any]) -> str:
    return str((feature.get("properties") or {}).get("source_id") or "").strip()


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


def has_temporal_metadata(properties: dict[str, Any]) -> bool:
    if properties.get("start_year") is not None or properties.get("end_year") is not None:
        return True
    intervals = properties.get("operational_intervals") or properties.get("operation_intervals") or properties.get("active_intervals")
    return isinstance(intervals, list) and bool(intervals)


def main() -> None:
    base_payload = load_json(MAP_OVERLAYS / "military_bases.geojson")
    nz_payload = load_json(MAP_OVERLAYS / "new_zealand_military_facilities.geojson")
    overrides_payload = load_json(MAP_OVERLAYS / "military_base_temporal_overrides.json")

    base_features = list(base_payload.get("features") or [])
    supplemental_features = list(nz_payload.get("features") or [])
    override_entries = list(overrides_payload.get("overrides") or [])
    override_source_ids = {
        str(entry.get("source_id") or "").strip()
        for entry in override_entries
        if str(entry.get("source_id") or "").strip()
    }
    base_source_ids = {feature_source_id(feature) for feature in base_features}

    replacement_source_ids = {
        str((feature.get("properties") or {}).get("replaces_source_id") or "").strip()
        for feature in supplemental_features
        if str((feature.get("properties") or {}).get("replaces_source_id") or "").strip()
    }
    merged_base_features = [
        feature
        for feature in base_features
        if feature_source_id(feature) not in replacement_source_ids
    ]
    merged_features = merged_base_features + supplemental_features
    membership_excluded_ids = membership_excluded_source_ids()
    merged_features = [
        feature
        for feature in merged_features
        if feature_source_id(feature) not in membership_excluded_ids
    ]

    matched_override_ids = override_source_ids & base_source_ids
    unmatched_override_ids = sorted(override_source_ids - base_source_ids)

    source_temporal_count = sum(1 for feature in merged_features if has_temporal_metadata(feature.get("properties") or {}))
    override_matched_count = sum(1 for feature in merged_features if feature_source_id(feature) in matched_override_ids)
    supplemental_temporal_count = sum(
        1 for feature in supplemental_features if has_temporal_metadata(feature.get("properties") or {})
    )

    by_country: dict[str, Counter[str]] = defaultdict(Counter)
    unknown_examples: dict[str, list[dict[str, str]]] = defaultdict(list)
    for feature in merged_features:
        properties = feature.get("properties") or {}
        country_code = str(properties.get("country_code") or properties.get("country") or "unknown").strip() or "unknown"
        source_id = feature_source_id(feature)
        is_override = source_id in matched_override_ids
        is_supplemental = source_id.startswith("nz-") or source_id in {
            feature_source_id(item) for item in supplemental_features
        }
        is_temporal = is_override or has_temporal_metadata(properties)
        by_country[country_code]["total"] += 1
        if is_temporal:
            by_country[country_code]["temporal"] += 1
        else:
            by_country[country_code]["unknown"] += 1
            if len(unknown_examples[country_code]) < 5:
                unknown_examples[country_code].append(
                    {
                        "name": str(properties.get("name") or ""),
                        "source_id": source_id,
                        "branch": str(properties.get("branch") or ""),
                    }
                )
        if is_override:
            by_country[country_code]["override"] += 1
        if is_supplemental:
            by_country[country_code]["supplemental"] += 1

    country_rows = []
    for country_code, counts in sorted(by_country.items(), key=lambda item: (-item[1]["total"], item[0])):
        country_rows.append(
            {
                "country_code": country_code,
                "total": counts["total"],
                "temporal": counts["temporal"],
                "unknown": counts["unknown"],
                "override": counts["override"],
                "supplemental": counts["supplemental"],
                "temporal_pct": round((counts["temporal"] / counts["total"]) * 100, 2) if counts["total"] else 0,
            }
        )

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_geojson_features": len(base_features),
        "supplemental_features": len(supplemental_features),
        "merged_features": len(merged_features),
        "membership_excluded_features": len(membership_excluded_ids),
        "override_entries": len(override_entries),
        "matched_override_entries": len(matched_override_ids),
        "unmatched_override_source_ids": unmatched_override_ids,
        "source_or_supplemental_temporal_features_before_override": source_temporal_count,
        "override_matched_features": override_matched_count,
        "supplemental_temporal_features": supplemental_temporal_count,
        "known_temporal_features_after_override": sum(row["temporal"] for row in country_rows),
        "unknown_temporal_features_after_override": sum(row["unknown"] for row in country_rows),
        "country_rows": country_rows,
        "unknown_examples_by_country": unknown_examples,
    }

    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "military_base_temporal_coverage.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    with (REPORTS / "military_base_temporal_coverage.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["country_code", "total", "temporal", "unknown", "override", "supplemental", "temporal_pct"],
        )
        writer.writeheader()
        writer.writerows(country_rows)

    print(json.dumps({
        "merged_features": summary["merged_features"],
        "membership_excluded_features": summary["membership_excluded_features"],
        "override_entries": summary["override_entries"],
        "matched_override_entries": summary["matched_override_entries"],
        "known_temporal_features_after_override": summary["known_temporal_features_after_override"],
        "unknown_temporal_features_after_override": summary["unknown_temporal_features_after_override"],
    }, indent=2))


if __name__ == "__main__":
    main()
