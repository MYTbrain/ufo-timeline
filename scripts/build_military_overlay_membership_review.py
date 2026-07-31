from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "data" / "reports"
GAP_CLASSES = REPORTS / "military_base_temporal_remaining_gap_classes.csv"

REVIEW_TOKEN_LABELS = (
    ("barak", "russian_barak_barracks_or_camp"),
    ("kazarma", "kazarma_barracks_or_railway_quarters"),
    ("asrama", "indonesian_asrama_quarters_or_dormitory"),
    ("barracks", "barracks_or_historical_barracks"),
    ("quarters", "quarters_or_housing"),
    ("police", "police_or_constabulary_site"),
    ("coast guard", "coast_guard_station"),
    ("lifeguard", "lifeguard_or_civil_safety"),
    ("seaplane base", "seaplane_or_civil_air_service"),
    ("airways", "civil_airways_business"),
)


def load_rows() -> list[dict[str, str]]:
    with GAP_CLASSES.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def review_reason(name: str) -> str:
    lowered = name.lower()
    for token, label in REVIEW_TOKEN_LABELS:
        if token in lowered:
            return label
    return "nonstandard_feature_code_or_name"


def main() -> None:
    rows = [
        row
        for row in load_rows()
        if row.get("recommended_action") == "review_overlay_membership_before_date_backfill"
    ]
    enriched: list[dict[str, Any]] = []
    by_country: dict[str, Counter[str]] = defaultdict(Counter)
    by_reason: Counter[str] = Counter()
    for row in rows:
        reason = review_reason(row.get("name") or "")
        by_country[row.get("country_code") or "unknown"][reason] += 1
        by_reason[reason] += 1
        enriched.append(
            {
                "source_id": row.get("source_id") or "",
                "name": row.get("name") or "",
                "country_code": row.get("country_code") or "",
                "branch": row.get("branch") or "",
                "feature_code": row.get("feature_code") or "",
                "review_reason": reason,
                "recommended_review_outcome": "review_for_overlay_exclusion_or_demotion",
            }
        )

    enriched.sort(key=lambda row: (row["review_reason"], row["country_code"], row["name"], row["source_id"]))
    summary_rows = [
        {
            "country_code": country,
            "review_reason": reason,
            "count": count,
        }
        for country, counts in sorted(by_country.items())
        for reason, count in sorted(counts.items())
    ]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input": str(GAP_CLASSES.relative_to(ROOT)).replace("\\", "/"),
        "review_count": len(enriched),
        "counts_by_review_reason": dict(by_reason),
        "counts_by_country_and_review_reason": {
            country: dict(counts)
            for country, counts in sorted(by_country.items())
        },
        "rows": enriched,
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "military_base_overlay_membership_review.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    with (REPORTS / "military_base_overlay_membership_review.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "source_id",
                "name",
                "country_code",
                "branch",
                "feature_code",
                "review_reason",
                "recommended_review_outcome",
            ],
        )
        writer.writeheader()
        writer.writerows(enriched)
    with (REPORTS / "military_base_overlay_membership_review_summary.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["country_code", "review_reason", "count"])
        writer.writeheader()
        writer.writerows(summary_rows)
    print(json.dumps({"review_count": len(enriched), "counts_by_review_reason": dict(by_reason)}, indent=2))


if __name__ == "__main__":
    main()
