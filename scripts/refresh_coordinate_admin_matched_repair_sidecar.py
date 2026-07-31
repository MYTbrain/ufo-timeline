"""Refresh admin-matched coordinate repair sidecar guards from a current corpus.

The coordinate-review sidecar can become stale if another preview pass changes
coordinates after the candidate report was generated. This script rebuilds the
sidecar's old-coordinate guards from the current event corpus, but only when
the same safety condition still holds:

- target event is found by canonical_event_id;
- current coordinate is outside the declared admin bounds;
- proposed GeoNames coordinate is inside the declared admin bounds.

It writes a refreshed proposed-patch sidecar only. It does not rewrite corpus,
static, canonical, or deployment artifacts.
"""

from __future__ import annotations

import argparse
import csv
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from scripts.apply_coordinate_sanity_preview import clean_text, parse_float, write_json
from scripts.build_coordinate_admin_matched_repair_candidates import admin_bounds, inside_bounds
from scripts.build_coordinate_admin_matched_repair_sidecar import flatten_patch


DEFAULT_CORPUS = Path("data/canonical_full/deduped_events.jsonl")
DEFAULT_SIDECAR = Path("data/reports/coordinate_admin_matched_repair_sidecar_v109.json")
DEFAULT_JSON = Path("data/reports/coordinate_admin_matched_repair_sidecar_current_v110.json")
DEFAULT_CSV = Path("data/reports/coordinate_admin_matched_repair_sidecar_current_v110.csv")


def refresh_coordinate_admin_matched_repair_sidecar(
    *,
    corpus_path: Path,
    sidecar_path: Path,
    json_output: Path,
    csv_output: Path,
) -> dict[str, Any]:
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    original_patches = sidecar.get("proposed_patches", [])
    patches_by_id = {
        clean_text(patch.get("canonical_event_id")): patch
        for patch in original_patches
        if clean_text(patch.get("canonical_event_id"))
    }
    event_rows = load_target_events(corpus_path, set(patches_by_id))

    refreshed_patches: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for canonical_event_id, patch in patches_by_id.items():
        event = event_rows.get(canonical_event_id)
        if event is None:
            skipped.append(skip_payload("target_event_not_found", patch, None))
            continue
        refreshed, reason = refresh_patch_if_safe(patch, event)
        if refreshed is None:
            skipped.append(skip_payload(reason, patch, event))
            continue
        refreshed_patches.append(refreshed)

    refreshed_patches.sort(
        key=lambda patch: (
            clean_text(patch.get("country")),
            clean_text(patch.get("declared_admin")),
            clean_text(patch.get("canonical_event_id")),
        )
    )
    write_sidecar_csv(csv_output, refreshed_patches)

    report = {
        "schema_version": 1,
        "mode": "refreshed_proposed_patch_sidecar",
        "sidecar_policy": "admin_matched_geonames_coordinate_repair_current_guard_refresh",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "inputs": {
            "corpus": str(corpus_path),
            "sidecar": str(sidecar_path),
        },
        "outputs": {
            "json": str(json_output),
            "csv": str(csv_output),
        },
        "input_patch_count": len(original_patches),
        "target_event_count": len(event_rows),
        "refreshed_patch_count": len(refreshed_patches),
        "skipped_patch_count": len(skipped),
        "refreshed_by_country": count_by(refreshed_patches, "country"),
        "refreshed_by_admin": count_by(refreshed_patches, "declared_admin"),
        "skip_reason_counts": count_by(skipped, "skip_reason"),
        "proposed_patches": refreshed_patches,
        "skipped_patches": skipped[:200],
        "notes": [
            "Report-only sidecar refresh; no event corpus is rewritten.",
            "Current event coordinates replace stale old-coordinate guards only when the current point is still outside the declared admin bounds.",
            "The proposed GeoNames coordinate must remain inside the declared admin bounds.",
        ],
    }
    write_json(json_output, report)
    return report


def load_target_events(corpus_path: Path, target_ids: set[str]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    with corpus_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            event = json.loads(line)
            canonical_event_id = clean_text(event.get("canonical_event_id"))
            if canonical_event_id in target_ids:
                rows[canonical_event_id] = event
                if len(rows) == len(target_ids):
                    break
    return rows


def refresh_patch_if_safe(patch: dict[str, Any], event: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    country = clean_text(patch.get("country"))
    admin = clean_text(patch.get("declared_admin"))
    bounds = admin_bounds(country, admin)
    if bounds is None:
        return None, "unsupported_admin_bounds"

    current_lat = parse_float(event.get("lat"))
    current_lon = parse_float(event.get("lon"))
    new_lat = parse_float((patch.get("new") or {}).get("lat"))
    new_lon = parse_float((patch.get("new") or {}).get("lon"))
    if current_lat is None or current_lon is None or new_lat is None or new_lon is None:
        return None, "invalid_current_or_new_coordinates"

    current_inside = inside_bounds(current_lat, current_lon, bounds)
    new_inside = inside_bounds(new_lat, new_lon, bounds)
    if current_inside:
        return None, "current_coordinate_inside_declared_admin_bounds"
    if not new_inside:
        return None, "new_coordinate_outside_declared_admin_bounds"

    refreshed = deepcopy(patch)
    current_source = clean_text(event.get("coordinate_source"))
    current_precision = clean_text(event.get("location_precision"))
    refreshed["old"] = {
        "lat": current_lat,
        "lon": current_lon,
        "coordinate_source": current_source,
        "location_precision": current_precision,
    }
    set_fields = dict(refreshed.get("set_fields") or {})
    set_fields["admin_coordinate_repair_original_lat"] = current_lat
    set_fields["admin_coordinate_repair_original_lon"] = current_lon
    set_fields["admin_coordinate_repair_original_source"] = current_source
    refreshed["set_fields"] = set_fields
    audit = dict(refreshed.get("audit") or {})
    audit["refreshed_from_corpus"] = True
    audit["current_inside_declared_admin_bounds"] = False
    audit["geonames_inside_declared_admin_bounds"] = True
    refreshed["audit"] = audit
    return refreshed, ""


def skip_payload(reason: str, patch: dict[str, Any], event: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "skip_reason": reason,
        "canonical_event_id": clean_text(patch.get("canonical_event_id")),
        "location_raw": clean_text(patch.get("location_raw")) or clean_text((event or {}).get("location_raw")),
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--sidecar", type=Path, default=DEFAULT_SIDECAR)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = refresh_coordinate_admin_matched_repair_sidecar(
        corpus_path=args.corpus,
        sidecar_path=args.sidecar,
        json_output=args.json_output,
        csv_output=args.csv_output,
    )
    print(
        json.dumps(
            {
                "input_patch_count": report["input_patch_count"],
                "refreshed_patch_count": report["refreshed_patch_count"],
                "skipped_patch_count": report["skipped_patch_count"],
                "outputs": report["outputs"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
