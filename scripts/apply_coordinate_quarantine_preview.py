"""Apply coordinate quarantine recommendations to a preview sidecar.

This removes only the coordinates for rows marked quarantine_until_review in a
coordinate quarantine packet. The event record is preserved, original
coordinates are copied to audit fields, and canonical source artifacts are not
mutated.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from scripts.apply_coordinate_sanity_preview import parse_float, write_json


DEFAULT_INPUT = Path("data/canonical_preview_mapping_enrichment_geonames_top5000_coordinate_sane_v3/deduped_events.jsonl")
DEFAULT_PACKET_CSV = Path("data/reports/coordinate_quarantine_packet_v3.csv")
DEFAULT_OUTPUT_DIR = Path("data/canonical_preview_mapping_enrichment_geonames_top5000_coordinate_sane_v3_quarantined")
DEFAULT_REPORT = Path("data/reports/coordinate_quarantine_preview_apply_report_v3.json")


def apply_coordinate_quarantine_preview(
    *,
    input_path: Path,
    packet_csv: Path,
    output_dir: Path,
    report_output: Path,
) -> dict[str, Any]:
    quarantine_rows = load_quarantine_rows(packet_csv)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "deduped_events.jsonl"
    tmp_output_path = output_path.with_suffix(".jsonl.tmp")
    input_event_count = 0
    output_event_count = 0
    mapped_before_count = 0
    mapped_after_count = 0
    quarantined_event_count = 0
    examples: list[dict[str, Any]] = []

    with input_path.open("r", encoding="utf-8") as source, tmp_output_path.open("w", encoding="utf-8", newline="\n") as output:
        for line in source:
            if not line.strip():
                continue
            event = json.loads(line)
            input_event_count += 1
            was_mapped = has_usable_coordinates(event)
            if was_mapped:
                mapped_before_count += 1
            event_id = str(event.get("canonical_event_id") or "")
            quarantine_row = quarantine_rows.get(event_id)
            if quarantine_row is not None:
                event = quarantine_event_coordinates(event, quarantine_row)
                quarantined_event_count += 1
                if len(examples) < 50:
                    examples.append(example_payload(event, quarantine_row))
            if has_usable_coordinates(event):
                mapped_after_count += 1
            output.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
            output_event_count += 1

    tmp_output_path.replace(output_path)
    report = {
        "schema_version": 1,
        "mode": "preview_apply",
        "apply_policy": "coordinate_quarantine_until_review_unmap_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": True,
        "inputs": {
            "deduped_events": str(input_path),
            "packet_csv": str(packet_csv),
        },
        "outputs": {
            "deduped_events": str(output_path),
            "report": str(report_output),
        },
        "input_event_count": input_event_count,
        "output_event_count": output_event_count,
        "quarantine_packet_event_count": len(quarantine_rows),
        "quarantined_event_count": quarantined_event_count,
        "mapped_before_count": mapped_before_count,
        "mapped_after_count": mapped_after_count,
        "mapped_reduction_count": mapped_before_count - mapped_after_count,
        "examples": examples,
        "notes": [
            "Only rows marked quarantine_until_review are unmapped.",
            "Event records remain in the corpus and source coordinates are preserved in coordinate_quarantine_original_lat/lon.",
            "Canonical source artifacts are not modified.",
        ],
    }
    write_json(report_output, report)
    return report


def load_quarantine_rows(path: Path) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("quarantine_recommendation") != "quarantine_until_review":
                continue
            event_id = row.get("canonical_event_id")
            if event_id:
                rows[event_id] = row
    return rows


def quarantine_event_coordinates(event: dict[str, Any], quarantine_row: dict[str, str]) -> dict[str, Any]:
    next_event = dict(event)
    lat = parse_float(next_event.get("lat"))
    lon = parse_float(next_event.get("lon"))
    next_event["coordinate_quarantine_status"] = "quarantine_until_review"
    next_event["coordinate_quarantine_reason"] = quarantine_row.get("quarantine_reason") or "coordinate_quarantine_packet"
    next_event["coordinate_quarantine_original_lat"] = lat
    next_event["coordinate_quarantine_original_lon"] = lon
    next_event["coordinate_quarantine_original_source"] = next_event.get("coordinate_source")
    next_event["coordinate_quarantine_original_precision"] = next_event.get("location_precision")
    next_event["lat"] = None
    next_event["lon"] = None
    next_event["coordinate_source"] = "unresolved"
    next_event["location_precision"] = "unknown"
    note = "Coordinate quarantine preview removed map coordinates pending review."
    existing_notes = str(next_event.get("mapping_notes") or "").strip()
    next_event["mapping_notes"] = f"{existing_notes} {note}".strip()
    return next_event


def example_payload(event: dict[str, Any], quarantine_row: dict[str, str]) -> dict[str, Any]:
    return {
        "canonical_event_id": event.get("canonical_event_id"),
        "source_name": event.get("source_name"),
        "source_row_number": event.get("source_row_number"),
        "source_native_id": event.get("source_native_id"),
        "location_raw": event.get("location_raw"),
        "declared_country": quarantine_row.get("declared_country"),
        "original_lat": event.get("coordinate_quarantine_original_lat"),
        "original_lon": event.get("coordinate_quarantine_original_lon"),
        "quarantine_reason": event.get("coordinate_quarantine_reason"),
    }


def has_usable_coordinates(event: dict[str, Any]) -> bool:
    lat = parse_float(event.get("lat"))
    lon = parse_float(event.get("lon"))
    return lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--packet-csv", type=Path, default=DEFAULT_PACKET_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = apply_coordinate_quarantine_preview(
        input_path=args.input,
        packet_csv=args.packet_csv,
        output_dir=args.output_dir,
        report_output=args.report_output,
    )
    print(json.dumps({
        "output": report["outputs"]["deduped_events"],
        "report": report["outputs"]["report"],
        "quarantined_event_count": report["quarantined_event_count"],
        "mapped_reduction_count": report["mapped_reduction_count"],
        "canonical_outputs_mutated": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
