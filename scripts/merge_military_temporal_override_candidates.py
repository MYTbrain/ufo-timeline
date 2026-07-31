from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OVERLAY = ROOT / "webapp" / "static_public" / "data" / "map_overlays" / "military_bases.geojson"
DEFAULT_OVERRIDE = ROOT / "webapp" / "static_public" / "data" / "map_overlays" / "military_base_temporal_overrides.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def has_temporal_evidence(entry: dict[str, Any]) -> bool:
    return (
        entry.get("start_year") is not None
        or entry.get("end_year") is not None
        or bool(entry.get("operational_intervals"))
    )


def candidate_entries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("overrides", "candidate_overrides", "candidates"):
        value = payload.get(key)
        if isinstance(value, list):
            return [entry for entry in value if isinstance(entry, dict)]
    return []


def source_countries_from_overlay(path: Path) -> dict[str, str]:
    payload = load_json(path)
    source_countries: dict[str, str] = {}
    for feature in payload.get("features") or []:
        properties = feature.get("properties") or {}
        source_id = str(properties.get("source_id") or "").strip()
        if source_id:
            source_countries[source_id] = str(properties.get("country_code") or "").strip()
    return source_countries


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge reviewed military-base temporal candidate overrides.")
    parser.add_argument("candidate_report", type=Path)
    parser.add_argument("--overlay", type=Path, default=DEFAULT_OVERLAY)
    parser.add_argument("--override", type=Path, default=DEFAULT_OVERRIDE)
    parser.add_argument("--temporal-source", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    candidate_payload = load_json(args.candidate_report)
    override_payload = load_json(args.override)
    overlay_source_countries = source_countries_from_overlay(args.overlay)
    overlay_source_ids = set(overlay_source_countries)
    existing_ids = {
        str(entry.get("source_id") or "").strip()
        for entry in override_payload.get("overrides") or []
        if str(entry.get("source_id") or "").strip()
    }

    added: list[str] = []
    skipped_duplicate: list[str] = []
    skipped_no_dates: list[str] = []
    skipped_missing_overlay: list[str] = []
    skipped_country_mismatch: list[str] = []
    skipped_missing_source_id = 0

    for raw_entry in candidate_entries(candidate_payload):
        entry = dict(raw_entry)
        source_id = str(entry.get("source_id") or "").strip()
        if not source_id:
            skipped_missing_source_id += 1
            continue
        if source_id in existing_ids:
            skipped_duplicate.append(source_id)
            continue
        if source_id not in overlay_source_ids:
            skipped_missing_overlay.append(source_id)
            continue
        candidate_country = str(entry.get("country_code") or "").strip()
        overlay_country = overlay_source_countries.get(source_id, "")
        if candidate_country and overlay_country and candidate_country != overlay_country:
            skipped_country_mismatch.append(source_id)
            continue
        if not has_temporal_evidence(entry):
            skipped_no_dates.append(source_id)
            continue

        if args.temporal_source and not entry.get("temporal_source"):
            entry["temporal_source"] = args.temporal_source
        entry.setdefault("date_precision_start", "year" if entry.get("start_year") is not None else "unknown")
        entry.setdefault("date_precision_end", "year" if entry.get("end_year") is not None else "open")
        entry.setdefault(
            "historical_status",
            "closed_or_transferred" if entry.get("end_year") is not None else "active_or_unknown",
        )
        override_payload.setdefault("overrides", []).append(entry)
        existing_ids.add(source_id)
        added.append(source_id)

    if not args.dry_run:
        override_payload["generated_at"] = "2026-06-04"
        args.override.write_text(json.dumps(override_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({
        "candidate_report": str(args.candidate_report),
        "dry_run": args.dry_run,
        "added": len(added),
        "total_after": len(override_payload.get("overrides") or []),
        "skipped_duplicate": len(skipped_duplicate),
        "skipped_no_dates": len(skipped_no_dates),
        "skipped_missing_overlay": len(skipped_missing_overlay),
        "skipped_country_mismatch": len(skipped_country_mismatch),
        "skipped_missing_source_id": skipped_missing_source_id,
        "added_source_ids": added,
        "skipped_no_date_source_ids": skipped_no_dates,
        "skipped_missing_overlay_source_ids": skipped_missing_overlay,
        "skipped_country_mismatch_source_ids": skipped_country_mismatch,
    }, indent=2))


if __name__ == "__main__":
    main()
