"""Apply reviewed admin-matched coordinate repair sidecar to a preview corpus.

This is a preview-only apply lane. It reads proposed patches from
`coordinate_admin_matched_repair_sidecar_v109.json`, verifies that each target
event still has the expected old lat/lon/source, and writes a new preview
`deduped_events.jsonl`. Canonical/source artifacts are never mutated.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.apply_coordinate_sanity_preview import clean_text, parse_float, write_json


DEFAULT_INPUT = Path("data/canonical_preview_map_enrich_v109_geonames_sign_mirror_repair/deduped_events.jsonl")
DEFAULT_SIDECAR = Path("data/reports/coordinate_admin_matched_repair_sidecar_v109.json")
DEFAULT_OUTPUT_DIR = Path("data/canonical_preview_map_enrich_v110_admin_matched_repair")
DEFAULT_REPORT = Path("data/reports/coordinate_admin_matched_repair_preview_v110_from_v109.json")


def apply_coordinate_admin_matched_repair_sidecar_preview(
    *,
    input_path: Path,
    sidecar_path: Path,
    output_dir: Path,
    report_output: Path,
) -> dict[str, Any]:
    patches_by_id = load_patches(sidecar_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "deduped_events.jsonl"
    tmp_output_path = output_path.with_suffix(".jsonl.tmp")

    input_event_count = 0
    applied_patch_count = 0
    skipped_patches: list[dict[str, Any]] = []
    applied_examples: list[dict[str, Any]] = []
    seen_patch_ids: set[str] = set()

    with input_path.open("r", encoding="utf-8") as source, tmp_output_path.open("w", encoding="utf-8", newline="\n") as output:
        for line in source:
            if not line.strip():
                continue
            input_event_count += 1
            event = json.loads(line)
            canonical_event_id = clean_text(event.get("canonical_event_id"))
            patch = patches_by_id.get(canonical_event_id)
            if patch is None:
                output.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
                continue

            seen_patch_ids.add(canonical_event_id)
            if not old_coordinate_guard_passes(event, patch):
                skipped_patches.append(skip_payload("old_coordinate_guard_failed", event, patch))
                output.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
                continue

            event = apply_patch_to_event(event, patch)
            applied_patch_count += 1
            if len(applied_examples) < 100:
                applied_examples.append(example_payload(event, patch))
            output.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")

    tmp_output_path.replace(output_path)

    unused_patches = [
        skip_payload("target_event_not_found", {"canonical_event_id": patch_id}, patch)
        for patch_id, patch in patches_by_id.items()
        if patch_id not in seen_patch_ids
    ]
    all_skips = skipped_patches + unused_patches
    report = {
        "schema_version": 1,
        "mode": "preview_apply",
        "apply_policy": "admin_matched_geonames_coordinate_repair_sidecar",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": True,
        "inputs": {
            "deduped_events": str(input_path),
            "sidecar": str(sidecar_path),
        },
        "outputs": {
            "deduped_events": str(output_path),
            "report": str(report_output),
        },
        "input_event_count": input_event_count,
        "sidecar_patch_count": len(patches_by_id),
        "applied_patch_count": applied_patch_count,
        "skipped_patch_count": len(skipped_patches),
        "unused_patch_count": len(unused_patches),
        "skip_reason_counts": count_by(all_skips, "skip_reason"),
        "applied_examples": applied_examples,
        "skipped_examples": all_skips[:100],
        "notes": [
            "Preview-only: canonical/source artifacts are not mutated.",
            "Each patch is guarded by canonical_event_id plus old lat/lon/source verification.",
            "Rows with changed old coordinates are left unchanged and reported as skips.",
        ],
    }
    write_json(report_output, report)
    return report


def load_patches(path: Path) -> dict[str, dict[str, Any]]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    patches: dict[str, dict[str, Any]] = {}
    for patch in doc.get("proposed_patches", []):
        canonical_event_id = clean_text(patch.get("canonical_event_id"))
        if not canonical_event_id:
            continue
        if canonical_event_id in patches:
            raise ValueError(f"Duplicate sidecar patch for {canonical_event_id}")
        patches[canonical_event_id] = patch
    return patches


def old_coordinate_guard_passes(event: dict[str, Any], patch: dict[str, Any]) -> bool:
    old = patch.get("old") or {}
    expected_lat = parse_float(old.get("lat"))
    expected_lon = parse_float(old.get("lon"))
    actual_lat = parse_float(event.get("lat"))
    actual_lon = parse_float(event.get("lon"))
    expected_source = clean_text(old.get("coordinate_source"))
    actual_source = clean_text(event.get("coordinate_source"))
    if expected_lat is None or expected_lon is None or actual_lat is None or actual_lon is None:
        return False
    if abs(actual_lat - expected_lat) > 1e-6 or abs(actual_lon - expected_lon) > 1e-6:
        return False
    return not expected_source or actual_source == expected_source


def apply_patch_to_event(event: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    next_event = dict(event)
    for key, value in (patch.get("set_fields") or {}).items():
        next_event[key] = value
    next_event["mapping_notes"] = append_note(
        next_event,
        "Admin-matched coordinate repair replaced outside-admin coordinate with same-admin GeoNames coordinate.",
    )
    return next_event


def append_note(event: dict[str, Any], note: str) -> str:
    existing = clean_text(event.get("mapping_notes"))
    return f"{existing} {note}".strip()


def skip_payload(reason: str, event: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    return {
        "skip_reason": reason,
        "canonical_event_id": clean_text(patch.get("canonical_event_id")) or clean_text(event.get("canonical_event_id")),
        "location_raw": clean_text(patch.get("location_raw")) or clean_text(event.get("location_raw")),
    }


def example_payload(event: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    return {
        "canonical_event_id": clean_text(event.get("canonical_event_id")),
        "location_raw": clean_text(event.get("location_raw")),
        "old": patch.get("old"),
        "new": patch.get("new"),
    }


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = clean_text(row.get(key)) or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--sidecar", type=Path, default=DEFAULT_SIDECAR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = apply_coordinate_admin_matched_repair_sidecar_preview(
        input_path=args.input,
        sidecar_path=args.sidecar,
        output_dir=args.output_dir,
        report_output=args.report_output,
    )
    print(
        json.dumps(
            {
                "input_event_count": report["input_event_count"],
                "sidecar_patch_count": report["sidecar_patch_count"],
                "applied_patch_count": report["applied_patch_count"],
                "skipped_patch_count": report["skipped_patch_count"],
                "unused_patch_count": report["unused_patch_count"],
                "outputs": report["outputs"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
