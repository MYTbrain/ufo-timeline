"""Build proposed coordinate repair patches from transform-evidence candidates.

This sidecar is intentionally not an apply script. It converts the report-only
coordinate transform candidates into compact proposed patches that can be
reviewed before any preview corpus, static bundle, or deployment artifact is
rewritten.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from scripts.apply_coordinate_sanity_preview import clean_text, parse_float, write_json


DEFAULT_INPUT = Path("data/reports/coordinate_transform_repair_candidates_v109.csv")
DEFAULT_JSON = Path("data/reports/coordinate_transform_repair_sidecar_v109.json")
DEFAULT_CSV = Path("data/reports/coordinate_transform_repair_sidecar_v109.csv")


def build_coordinate_transform_repair_sidecar(
    *,
    input_csv: Path,
    json_output: Path,
    csv_output: Path,
    artifact_dir: Path | None = None,
) -> dict[str, Any]:
    rows = read_rows(input_csv)
    proposed_patches: list[dict[str, Any]] = []
    skipped_rows: list[dict[str, Any]] = []

    for row in rows:
        patch, skip = proposed_patch_from_row(row, artifact_dir=artifact_dir)
        if patch is not None:
            proposed_patches.append(patch)
        elif skip is not None:
            skipped_rows.append(skip)

    proposed_patches.sort(
        key=lambda patch: (
            clean_text(patch.get("country")),
            clean_text(patch.get("transform")),
            clean_text(patch.get("location_raw")),
            clean_text(patch.get("canonical_event_id")),
        )
    )
    write_sidecar_csv(csv_output, proposed_patches)

    report = {
        "schema_version": 1,
        "mode": "proposed_patch_sidecar",
        "sidecar_policy": "coordinate_transform_geonames_repair_proposed_patches",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "ready_for_preview_apply": True,
        "human_review_required_before_apply": True,
        "inputs": {
            "repair_candidates_csv": str(input_csv),
            "artifact_dir": str(artifact_dir) if artifact_dir is not None else None,
        },
        "outputs": {
            "json": str(json_output),
            "csv": str(csv_output),
        },
        "input_row_count": len(rows),
        "proposed_patch_count": len(proposed_patches),
        "skipped_row_count": len(skipped_rows),
        "proposed_by_country": count_by(proposed_patches, "country"),
        "proposed_by_transform": count_by(proposed_patches, "transform"),
        "skipped_reason_counts": count_by(skipped_rows, "skip_reason"),
        "proposed_patches": proposed_patches,
        "skipped_rows": skipped_rows[:200],
        "notes": [
            "This file is a review/apply sidecar only; it does not rewrite event rows.",
            "Only rows already classified as coordinate_transform_repair_candidate are eligible.",
            "Eligibility is rechecked so malformed rows cannot silently enter the apply packet.",
            "Later apply scripts should match by canonical_event_id and verify old lat/lon/source before changing coordinates.",
            "For served-payload reports without canonical_event_id, artifact_dir can be used to recover the canonical id only from an exact chunk_id/detail_index/event_id target with matching old-coordinate guards.",
        ],
    }
    write_json(json_output, report)
    return report


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def proposed_patch_from_row(
    row: dict[str, str],
    *,
    artifact_dir: Path | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if clean_text(row.get("recommended_action")) != "coordinate_transform_repair_candidate":
        return None, skip_payload(row, "not_coordinate_transform_repair_candidate")

    canonical_event_id = clean_text(row.get("canonical_event_id"))
    if not canonical_event_id:
        canonical_event_id, resolve_skip = resolve_canonical_event_id_from_chunk(row, artifact_dir)
        if not canonical_event_id:
            return None, resolve_skip or skip_payload(row, "missing_canonical_event_id")

    old_lat = parse_float(row.get("old_lat"))
    old_lon = parse_float(row.get("old_lon"))
    transformed_lat = parse_float(row.get("transformed_lat"))
    transformed_lon = parse_float(row.get("transformed_lon"))
    new_lat = parse_float(row.get("new_lat"))
    new_lon = parse_float(row.get("new_lon"))
    original_distance_km = parse_float(row.get("original_distance_km"))
    transformed_distance_km = parse_float(row.get("transformed_distance_km"))
    improvement_ratio = parse_float(row.get("distance_improvement_ratio"))
    if (
        old_lat is None
        or old_lon is None
        or transformed_lat is None
        or transformed_lon is None
        or new_lat is None
        or new_lon is None
        or original_distance_km is None
        or transformed_distance_km is None
        or improvement_ratio is None
    ):
        return None, skip_payload(row, "invalid_transform_candidate_values")

    if original_distance_km < 100 or transformed_distance_km > 50 or improvement_ratio < 3:
        return None, skip_payload(row, "transform_candidate_threshold_guard_failed")

    transform = clean_text(row.get("transform"))
    if transform not in {
        "lon_sign_flip",
        "lat_sign_flip",
        "both_sign_flip",
        "swap",
        "swap_lon_sign_flip",
        "swap_lat_sign_flip",
        "swap_both_sign_flip",
    }:
        return None, skip_payload(row, "unsupported_transform")

    feature_class = clean_text(row.get("geonames_feature_class")).upper()
    location_precision = "city" if feature_class == "P" else "mapped"
    geonames_name = clean_text(row.get("geonames_name"))
    country = clean_text(row.get("country"))
    original_source = clean_text(row.get("coordinate_source"))
    action = clean_text(row.get("suggested_preview_repair_action")) or f"replace_with_geonames_after_{transform}_evidence"

    patch = {
        "canonical_event_id": canonical_event_id,
        "event_id": clean_text(row.get("event_id")),
        "chunk_id": clean_text(row.get("chunk_id")),
        "detail_index": clean_text(row.get("detail_index")),
        "source_name": clean_text(row.get("source_name")),
        "source_row_number": clean_text(row.get("source_row_number")),
        "source_native_id": clean_text(row.get("source_native_id")),
        "date": clean_text(row.get("date")),
        "location_raw": clean_text(row.get("location_raw")),
        "country": country,
        "transform": transform,
        "old": {
            "lat": old_lat,
            "lon": old_lon,
            "coordinate_source": original_source,
            "location_precision": clean_text(row.get("location_precision")),
        },
        "transform_evidence": {
            "lat": transformed_lat,
            "lon": transformed_lon,
            "transform": transform,
            "original_distance_km": original_distance_km,
            "transformed_distance_km": transformed_distance_km,
            "distance_improvement_ratio": improvement_ratio,
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
            "geocode_query_used": display_name(geonames_name, country),
            "geocode_display_name": display_name(geonames_name, country),
            "geocode_confidence": 0.9,
            "transform_coordinate_repair_action": action,
            "transform_coordinate_repair_reason": clean_text(row.get("recommendation_reason")),
            "transform_coordinate_repair_transform": transform,
            "transform_coordinate_repair_original_lat": old_lat,
            "transform_coordinate_repair_original_lon": old_lon,
            "transform_coordinate_repair_original_source": original_source,
            "transform_coordinate_repair_transformed_lat": transformed_lat,
            "transform_coordinate_repair_transformed_lon": transformed_lon,
            "transform_coordinate_repair_original_distance_km": original_distance_km,
            "transform_coordinate_repair_transformed_distance_km": transformed_distance_km,
            "transform_coordinate_repair_improvement_ratio": improvement_ratio,
            "transform_coordinate_repair_geoname_id": clean_text(row.get("geonames_id")),
            "transform_coordinate_repair_geonames_name": geonames_name,
            "transform_coordinate_repair_geonames_admin1": clean_text(row.get("geonames_admin1")),
            "transform_coordinate_repair_geonames_feature_class": feature_class,
            "transform_coordinate_repair_geonames_feature_code": clean_text(row.get("geonames_feature_code")),
        },
        "audit": {
            "source_candidate_file_action": clean_text(row.get("recommended_action")),
            "suggested_preview_repair_action": action,
        },
    }
    return patch, None


def display_name(name: str, country: str) -> str:
    parts = [part for part in [name, country] if part]
    return ", ".join(parts)


def resolve_canonical_event_id_from_chunk(
    row: dict[str, str],
    artifact_dir: Path | None,
) -> tuple[str, dict[str, Any] | None]:
    if artifact_dir is None:
        return "", skip_payload(row, "missing_canonical_event_id")

    chunk_id = clean_text(row.get("chunk_id"))
    detail_index_raw = clean_text(row.get("detail_index"))
    event_id = clean_text(row.get("event_id"))
    if not chunk_id or not detail_index_raw or not event_id:
        return "", skip_payload(row, "missing_canonical_event_id_and_served_target")

    try:
        detail_index = int(detail_index_raw)
    except ValueError:
        return "", skip_payload(row, "invalid_served_detail_index")

    chunk_path = artifact_dir / "event_chunks" / f"{chunk_id}.json"
    if not chunk_path.exists():
        return "", skip_payload(row, "missing_served_event_chunk")

    try:
        chunk_rows = json.loads(chunk_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "", skip_payload(row, "invalid_served_event_chunk_json")
    if not isinstance(chunk_rows, list) or detail_index < 0 or detail_index >= len(chunk_rows):
        return "", skip_payload(row, "served_detail_index_out_of_range")

    target = chunk_rows[detail_index]
    if not isinstance(target, dict):
        return "", skip_payload(row, "served_target_row_not_object")
    if clean_text(target.get("event_id")) != event_id:
        return "", skip_payload(row, "served_target_event_id_mismatch")

    old_lat = parse_float(row.get("old_lat"))
    old_lon = parse_float(row.get("old_lon"))
    target_lat = parse_float(target.get("lat"))
    target_lon = parse_float(target.get("lon"))
    if old_lat is None or old_lon is None or target_lat is None or target_lon is None:
        return "", skip_payload(row, "served_target_missing_coordinate_guard")
    if abs(old_lat - target_lat) > 1e-6 or abs(old_lon - target_lon) > 1e-6:
        return "", skip_payload(row, "served_target_old_coordinate_mismatch")

    expected_source = clean_text(row.get("coordinate_source"))
    target_source = clean_text(target.get("coordinate_source"))
    if expected_source and not coordinate_source_guard_passes(expected_source, target_source):
        return "", skip_payload(row, "served_target_coordinate_source_mismatch")

    canonical_event_id = clean_text(target.get("canonical_event_id"))
    if not canonical_event_id:
        return "", skip_payload(row, "served_target_missing_canonical_event_id")
    return canonical_event_id, None


def coordinate_source_guard_passes(expected_source: str, current_source: str) -> bool:
    if expected_source == current_source:
        return True
    source_coordinate_aliases = {"source_coordinates", "raw_latlong"}
    return expected_source in source_coordinate_aliases and current_source in source_coordinate_aliases


def skip_payload(row: dict[str, str], reason: str) -> dict[str, Any]:
    return {
        "skip_reason": reason,
        "canonical_event_id": clean_text(row.get("canonical_event_id")),
        "event_id": clean_text(row.get("event_id")),
        "chunk_id": clean_text(row.get("chunk_id")),
        "detail_index": clean_text(row.get("detail_index")),
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
        "event_id",
        "chunk_id",
        "detail_index",
        "source_name",
        "source_row_number",
        "source_native_id",
        "date",
        "location_raw",
        "country",
        "transform",
        "old_lat",
        "old_lon",
        "old_coordinate_source",
        "old_location_precision",
        "transformed_lat",
        "transformed_lon",
        "original_distance_km",
        "transformed_distance_km",
        "distance_improvement_ratio",
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
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for patch in patches:
            writer.writerow(flatten_patch(patch))


def flatten_patch(patch: dict[str, Any]) -> dict[str, Any]:
    evidence = patch["transform_evidence"]
    return {
        "canonical_event_id": patch["canonical_event_id"],
        "event_id": patch.get("event_id"),
        "chunk_id": patch.get("chunk_id"),
        "detail_index": patch.get("detail_index"),
        "source_name": patch["source_name"],
        "source_row_number": patch["source_row_number"],
        "source_native_id": patch["source_native_id"],
        "date": patch["date"],
        "location_raw": patch["location_raw"],
        "country": patch["country"],
        "transform": patch["transform"],
        "old_lat": patch["old"]["lat"],
        "old_lon": patch["old"]["lon"],
        "old_coordinate_source": patch["old"]["coordinate_source"],
        "old_location_precision": patch["old"]["location_precision"],
        "transformed_lat": evidence["lat"],
        "transformed_lon": evidence["lon"],
        "original_distance_km": evidence["original_distance_km"],
        "transformed_distance_km": evidence["transformed_distance_km"],
        "distance_improvement_ratio": evidence["distance_improvement_ratio"],
        "new_lat": patch["new"]["lat"],
        "new_lon": patch["new"]["lon"],
        "new_coordinate_source": patch["new"]["coordinate_source"],
        "new_location_precision": patch["new"]["location_precision"],
        "geonames_name": patch["new"]["geonames_name"],
        "geonames_id": patch["new"]["geonames_id"],
        "geonames_feature_class": patch["new"]["geonames_feature_class"],
        "geonames_feature_code": patch["new"]["geonames_feature_code"],
        "repair_action": patch["set_fields"]["transform_coordinate_repair_action"],
        "repair_reason": patch["set_fields"]["transform_coordinate_repair_reason"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV)
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Optional canonical web artifact directory used to resolve canonical_event_id from served chunk_id/detail_index targets.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_coordinate_transform_repair_sidecar(
        input_csv=args.input_csv,
        json_output=args.json_output,
        csv_output=args.csv_output,
        artifact_dir=args.artifact_dir,
    )
    print(
        json.dumps(
            {
                "input_row_count": report["input_row_count"],
                "proposed_patch_count": report["proposed_patch_count"],
                "skipped_row_count": report["skipped_row_count"],
                "proposed_by_country": report["proposed_by_country"],
                "proposed_by_transform": report["proposed_by_transform"],
                "outputs": report["outputs"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
