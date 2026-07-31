"""Build proposed coordinate repair patches from admin-matched candidates.

This sidecar is intentionally not an apply script. It converts the reviewed
`preview_repair_candidate` rows into a compact proposed-patch packet that can
be inspected before any preview corpus, static bundle, or deployment artifact is
rewritten.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from scripts.apply_coordinate_sanity_preview import clean_text, parse_float, write_json


DEFAULT_INPUT = Path("data/reports/coordinate_admin_matched_repair_candidates_v109.csv")
DEFAULT_JSON = Path("data/reports/coordinate_admin_matched_repair_sidecar_v109.json")
DEFAULT_CSV = Path("data/reports/coordinate_admin_matched_repair_sidecar_v109.csv")


def build_coordinate_admin_matched_repair_sidecar(
    *,
    input_csv: Path,
    json_output: Path,
    csv_output: Path,
) -> dict[str, Any]:
    rows = read_rows(input_csv)
    proposed_patches: list[dict[str, Any]] = []
    skipped_rows: list[dict[str, Any]] = []

    for row in rows:
        patch, skip = proposed_patch_from_row(row)
        if patch is not None:
            proposed_patches.append(patch)
        elif skip is not None:
            skipped_rows.append(skip)

    proposed_patches.sort(
        key=lambda patch: (
            clean_text(patch.get("country")),
            clean_text(patch.get("declared_admin")),
            clean_text(patch.get("canonical_event_id")),
        )
    )
    write_sidecar_csv(csv_output, proposed_patches)

    report = {
        "schema_version": 1,
        "mode": "proposed_patch_sidecar",
        "sidecar_policy": "admin_matched_geonames_coordinate_repair_proposed_patches",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "ready_for_preview_apply": True,
        "human_review_required_before_apply": True,
        "inputs": {
            "repair_candidates_csv": str(input_csv),
        },
        "outputs": {
            "json": str(json_output),
            "csv": str(csv_output),
        },
        "input_row_count": len(rows),
        "proposed_patch_count": len(proposed_patches),
        "skipped_row_count": len(skipped_rows),
        "proposed_by_country": count_by(proposed_patches, "country"),
        "proposed_by_admin": count_by(proposed_patches, "declared_admin"),
        "skipped_reason_counts": count_by(skipped_rows, "skip_reason"),
        "proposed_patches": proposed_patches,
        "skipped_rows": skipped_rows[:200],
        "notes": [
            "This file is a review/apply sidecar only; it does not rewrite event rows.",
            "Only rows already classified as preview_repair_candidate are eligible.",
            "Eligibility is rechecked so malformed rows cannot silently enter the apply packet.",
            "Later apply scripts should match by canonical_event_id and verify old lat/lon/source before changing coordinates.",
        ],
    }
    write_json(json_output, report)
    return report


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def proposed_patch_from_row(row: dict[str, str]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if clean_text(row.get("recommended_action")) != "preview_repair_candidate":
        return None, skip_payload(row, "not_preview_repair_candidate")

    canonical_event_id = clean_text(row.get("canonical_event_id"))
    if not canonical_event_id:
        return None, skip_payload(row, "missing_canonical_event_id")

    old_lat = parse_float(row.get("old_lat"))
    old_lon = parse_float(row.get("old_lon"))
    new_lat = parse_float(row.get("new_lat"))
    new_lon = parse_float(row.get("new_lon"))
    if old_lat is None or old_lon is None or new_lat is None or new_lon is None:
        return None, skip_payload(row, "invalid_old_or_new_coordinates")

    if bool_text(row.get("current_inside_declared_admin_bounds")) is not False:
        return None, skip_payload(row, "current_coordinate_not_confirmed_outside_admin_bounds")
    if bool_text(row.get("geonames_inside_declared_admin_bounds")) is not True:
        return None, skip_payload(row, "geonames_coordinate_not_confirmed_inside_admin_bounds")

    feature_class = clean_text(row.get("geonames_feature_class")).upper()
    location_precision = "city" if feature_class == "P" else "mapped"
    geonames_name = clean_text(row.get("geonames_name"))
    declared_admin = clean_text(row.get("declared_admin"))
    country = clean_text(row.get("country"))
    original_source = clean_text(row.get("coordinate_source"))
    action = clean_text(row.get("suggested_preview_repair_action")) or "replace_with_same_admin_geonames_feature"

    patch = {
        "canonical_event_id": canonical_event_id,
        "event_id": clean_text(row.get("event_id")),
        "source_name": clean_text(row.get("source_name")),
        "source_row_number": clean_text(row.get("source_row_number")),
        "source_native_id": clean_text(row.get("source_native_id")),
        "date": clean_text(row.get("date")),
        "location_raw": clean_text(row.get("location_raw")),
        "country": country,
        "declared_admin": declared_admin,
        "old": {
            "lat": old_lat,
            "lon": old_lon,
            "coordinate_source": original_source,
            "location_precision": clean_text(row.get("location_precision")),
        },
        "new": {
            "lat": new_lat,
            "lon": new_lon,
            "coordinate_source": "geocoded",
            "location_precision": location_precision,
            "geonames_name": geonames_name,
            "geonames_id": clean_text(row.get("geonames_id")),
            "geonames_feature_class": feature_class,
            "geonames_feature_code": clean_text(row.get("geonames_feature_code")),
            "geonames_admin1": clean_text(row.get("geonames_admin1")),
        },
        "set_fields": {
            "lat": new_lat,
            "lon": new_lon,
            "coordinate_source": "geocoded",
            "location_precision": location_precision,
            "geocode_query_used": display_name(geonames_name, declared_admin, country),
            "geocode_display_name": display_name(geonames_name, declared_admin, country),
            "geocode_confidence": 0.9,
            "admin_coordinate_repair_action": action,
            "admin_coordinate_repair_reason": clean_text(row.get("recommendation_reason")),
            "admin_coordinate_repair_original_lat": old_lat,
            "admin_coordinate_repair_original_lon": old_lon,
            "admin_coordinate_repair_original_source": original_source,
            "admin_coordinate_repair_geoname_id": clean_text(row.get("geonames_id")),
            "admin_coordinate_repair_geonames_name": geonames_name,
            "admin_coordinate_repair_geonames_admin1": clean_text(row.get("geonames_admin1")),
            "admin_coordinate_repair_geonames_feature_class": feature_class,
            "admin_coordinate_repair_geonames_feature_code": clean_text(row.get("geonames_feature_code")),
        },
        "audit": {
            "distance_km": parse_float(row.get("distance_km")),
            "current_inside_declared_admin_bounds": False,
            "geonames_inside_declared_admin_bounds": True,
            "source_candidate_file_action": clean_text(row.get("recommended_action")),
        },
    }
    return patch, None


def bool_text(value: Any) -> bool | None:
    text = clean_text(value).lower()
    if text == "true":
        return True
    if text == "false":
        return False
    return None


def display_name(name: str, admin: str, country: str) -> str:
    parts = [part for part in [name, admin, country] if part]
    return ", ".join(parts)


def skip_payload(row: dict[str, str], reason: str) -> dict[str, Any]:
    return {
        "skip_reason": reason,
        "canonical_event_id": clean_text(row.get("canonical_event_id")),
        "recommended_action": clean_text(row.get("recommended_action")),
        "location_raw": clean_text(row.get("location_raw")),
    }


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = clean_text(row.get(key)) or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def write_sidecar_csv(path: Path, patches: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "canonical_event_id",
        "source_name",
        "source_row_number",
        "source_native_id",
        "date",
        "location_raw",
        "country",
        "declared_admin",
        "old_lat",
        "old_lon",
        "old_coordinate_source",
        "old_location_precision",
        "new_lat",
        "new_lon",
        "new_coordinate_source",
        "new_location_precision",
        "geonames_name",
        "geonames_id",
        "geonames_feature_class",
        "geonames_feature_code",
        "repair_action",
        "repair_reason",
        "distance_km",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for patch in patches:
            writer.writerow(flatten_patch(patch))


def flatten_patch(patch: dict[str, Any]) -> dict[str, Any]:
    return {
        "canonical_event_id": patch["canonical_event_id"],
        "source_name": patch["source_name"],
        "source_row_number": patch["source_row_number"],
        "source_native_id": patch["source_native_id"],
        "date": patch["date"],
        "location_raw": patch["location_raw"],
        "country": patch["country"],
        "declared_admin": patch["declared_admin"],
        "old_lat": patch["old"]["lat"],
        "old_lon": patch["old"]["lon"],
        "old_coordinate_source": patch["old"]["coordinate_source"],
        "old_location_precision": patch["old"]["location_precision"],
        "new_lat": patch["new"]["lat"],
        "new_lon": patch["new"]["lon"],
        "new_coordinate_source": patch["new"]["coordinate_source"],
        "new_location_precision": patch["new"]["location_precision"],
        "geonames_name": patch["new"]["geonames_name"],
        "geonames_id": patch["new"]["geonames_id"],
        "geonames_feature_class": patch["new"]["geonames_feature_class"],
        "geonames_feature_code": patch["new"]["geonames_feature_code"],
        "repair_action": patch["set_fields"]["admin_coordinate_repair_action"],
        "repair_reason": patch["set_fields"]["admin_coordinate_repair_reason"],
        "distance_km": patch["audit"]["distance_km"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_coordinate_admin_matched_repair_sidecar(
        input_csv=args.input_csv,
        json_output=args.json_output,
        csv_output=args.csv_output,
    )
    print(
        json.dumps(
            {
                "input_row_count": report["input_row_count"],
                "proposed_patch_count": report["proposed_patch_count"],
                "skipped_row_count": report["skipped_row_count"],
                "outputs": report["outputs"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
