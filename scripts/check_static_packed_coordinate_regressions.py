"""Report coordinate regressions in the packed point layer used by the map.

The summary-shard regression checks validate the catalog records. This check
validates the packed ``points.bin`` payload that the browser actually renders,
then joins each packed row back to its lazy event chunk for location labels.
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path
from typing import Any, Iterable

from scripts.check_static_coordinate_regressions import (
    NAMED_COUNTRY_REGRESSIONS,
    NAMED_US_REGRESSIONS,
    explicit_us_state,
    float_or_none,
    is_inside_named_country_bounds,
    is_inside_us_state_bounds,
    is_inside_us_wide_bounds,
    location_has_country_token,
    summarize_event,
)


DEFAULT_PAYLOAD_ROOT = Path("static_bundle")
DEFAULT_OUTPUT = Path("data/reports/static_packed_coordinate_regressions.json")


def check_static_packed_coordinate_regressions(
    *,
    payload_root: Path,
    named_regressions: list[dict[str, str]] | None = None,
    named_country_regressions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload_root = payload_root.resolve()
    if named_regressions is None:
        named_regressions = NAMED_US_REGRESSIONS
    if named_country_regressions is None:
        named_country_regressions = NAMED_COUNTRY_REGRESSIONS

    scanned_rows = 0
    rows_with_full_event = 0
    full_event_mismatches = 0
    explicit_us_rows = 0
    explicit_us_outside_bounds = 0
    explicit_us_outside_state_bounds = 0
    outside_examples: list[dict[str, Any]] = []
    outside_state_examples: list[dict[str, Any]] = []
    mismatch_examples: list[dict[str, Any]] = []
    named_results = {
        item["label"]: {"label": item["label"], "found": 0, "outside_bounds": 0, "examples": []}
        for item in named_regressions
    }
    named_country_results = {
        item["label"]: {"label": item["label"], "found": 0, "outside_bounds": 0, "examples": []}
        for item in named_country_regressions
    }

    for event in iter_static_packed_point_events(payload_root):
        scanned_rows += 1
        if event.get("_full_event_loaded"):
            rows_with_full_event += 1
        if event.get("_full_event_mismatch"):
            full_event_mismatches += 1
            if len(mismatch_examples) < 25:
                mismatch_examples.append(summarize_event(event, state=explicit_us_state(str(event.get("location_raw") or "")) or ""))

        location_raw = str(event.get("location_raw") or "")
        lat = float_or_none(event.get("lat"))
        lon = float_or_none(event.get("lon"))
        if lat is None or lon is None:
            continue

        location_upper = location_raw.upper()
        for item in named_country_regressions:
            if item["contains"].upper() not in location_upper:
                continue
            if not location_has_country_token(location_raw, item["country_tokens"]):
                continue
            named_country = named_country_results[item["label"]]
            named_country["found"] += 1
            if len(named_country["examples"]) < 5:
                named_country["examples"].append(summarize_event(event, state=explicit_us_state(location_raw) or ""))
            if not is_inside_named_country_bounds(item, lat, lon):
                named_country["outside_bounds"] += 1

        state = explicit_us_state(location_raw)
        if state is None:
            continue

        explicit_us_rows += 1
        inside = is_inside_us_wide_bounds(lat, lon)
        inside_state = is_inside_us_state_bounds(state, lat, lon)
        if not inside:
            explicit_us_outside_bounds += 1
            if len(outside_examples) < 100:
                outside_examples.append(summarize_event(event, state=state))
        if not inside_state:
            explicit_us_outside_state_bounds += 1
            if len(outside_state_examples) < 100:
                outside_state_examples.append(summarize_event(event, state=state))

        for item in named_regressions:
            if item["contains"].upper() in location_upper and state == item["state"]:
                named = named_results[item["label"]]
                named["found"] += 1
                if len(named["examples"]) < 5:
                    named["examples"].append(summarize_event(event, state=state))
                if not inside or not inside_state:
                    named["outside_bounds"] += 1

    named_failures = [
        item
        for item in named_results.values()
        if item["found"] == 0 or item["outside_bounds"] > 0
    ]
    named_country_failures = [
        item
        for item in named_country_results.values()
        if item["found"] == 0 or item["outside_bounds"] > 0
    ]
    checks = {
        "packed_rows_join_to_full_events": full_event_mismatches == 0 and rows_with_full_event == scanned_rows,
        "explicit_us_rows_inside_wide_us_bounds": explicit_us_outside_bounds == 0,
        "explicit_us_rows_inside_state_bounds": explicit_us_outside_state_bounds == 0,
        "named_regressions_found": all(item["found"] > 0 for item in named_results.values()),
        "named_regressions_inside_wide_and_state_bounds": all(item["outside_bounds"] == 0 for item in named_results.values()),
        "named_country_regressions_found": all(item["found"] > 0 for item in named_country_results.values()),
        "named_country_regressions_inside_country_bounds": all(item["outside_bounds"] == 0 for item in named_country_results.values()),
    }

    return {
        "schema_version": 1,
        "report_policy": "static_packed_coordinate_regression_report_only",
        "canonical_outputs_mutated": False,
        "payload_root": str(payload_root),
        "status": "ready" if all(checks.values()) else "needs_attention",
        "checks": checks,
        "counts": {
            "scanned_rows": scanned_rows,
            "rows_with_full_event": rows_with_full_event,
            "full_event_mismatches": full_event_mismatches,
            "explicit_us_rows": explicit_us_rows,
            "explicit_us_outside_bounds": explicit_us_outside_bounds,
            "explicit_us_outside_state_bounds": explicit_us_outside_state_bounds,
            "named_regressions_checked": len(named_regressions),
            "named_regression_failures": len(named_failures),
            "named_country_regressions_checked": len(named_country_regressions),
            "named_country_regression_failures": len(named_country_failures),
        },
        "named_regressions": list(named_results.values()),
        "named_country_regressions": list(named_country_results.values()),
        "outside_examples": outside_examples,
        "outside_state_examples": outside_state_examples,
        "full_event_mismatch_examples": mismatch_examples,
        "notes": [
            "This check validates the packed point file used by browser map rendering, not only summary shards.",
            "Packed lat/lon values are checked against the location labels loaded from lazy full-event chunks.",
        ],
    }


def iter_static_packed_point_events(payload_root: Path) -> Iterable[dict[str, Any]]:
    canonical_dir = payload_root / "data" / "canonical_web"
    meta_path = canonical_dir / "points_meta.json"
    bin_path = canonical_dir / "points.bin"
    if not meta_path.exists():
        raise FileNotFoundError(f"Missing packed points metadata: {meta_path}")
    if not bin_path.exists():
        raise FileNotFoundError(f"Missing packed points binary: {bin_path}")

    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    row_struct = struct.Struct(metadata["struct_format"])
    fields = metadata["fields"]
    lookup_tables = metadata["lookup_tables"]
    expected_bytes = int(metadata["row_count"]) * int(metadata["bytes_per_row"])
    data = bin_path.read_bytes()
    if len(data) != expected_bytes:
        raise ValueError(f"{bin_path} has {len(data)} bytes, expected {expected_bytes}.")

    chunk_cache: dict[str, list[dict[str, Any]]] = {}
    for unpacked in row_struct.iter_unpack(data):
        row = _decode_packed_row(fields, lookup_tables, unpacked)
        full_event = _full_event_for_packed_row(canonical_dir, row, chunk_cache)
        event = dict(full_event or {})
        event.update(
            {
                "event_id": row.get("event_id"),
                "lat": row.get("lat"),
                "lon": row.get("lon"),
                "sort_date_iso": _sort_date_iso_from_key(row.get("sort_date_key")),
                "source": event.get("source") or row.get("source_id"),
                "type": event.get("type") or row.get("type_id"),
                "location_precision": event.get("location_precision") or row.get("location_precision_id"),
                "coordinate_source": event.get("coordinate_source") or row.get("coordinate_source_id"),
                "_full_event_loaded": full_event is not None,
                "_full_event_mismatch": full_event is None,
            }
        )
        yield event


def _decode_packed_row(
    fields: list[dict[str, Any]],
    lookup_tables: dict[str, list[Any]],
    unpacked: tuple[Any, ...],
) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for field, value in zip(fields, unpacked):
        table_name = field.get("lookup_table")
        if table_name:
            value = lookup_tables[table_name][value]
        row[field["name"]] = value
    return row


def _full_event_for_packed_row(
    canonical_dir: Path,
    row: dict[str, Any],
    chunk_cache: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    chunk_id = row.get("chunk_id")
    detail_index = row.get("detail_index")
    if not chunk_id or not isinstance(detail_index, int) or detail_index < 0:
        return None
    if chunk_id not in chunk_cache:
        chunk_path = canonical_dir / "event_chunks" / f"{chunk_id}.json"
        payload = json.loads(chunk_path.read_text(encoding="utf-8"))
        chunk_cache[chunk_id] = payload.get("events", payload) if isinstance(payload, dict) else payload
    events = chunk_cache[chunk_id]
    if detail_index < len(events):
        candidate = events[detail_index]
        if str(candidate.get("event_id")) == str(row.get("event_id")):
            return candidate
    for candidate in events:
        if str(candidate.get("event_id")) == str(row.get("event_id")):
            return candidate
    return None


def _sort_date_iso_from_key(value: Any) -> str | None:
    try:
        key = int(value)
    except (TypeError, ValueError):
        return None
    if key <= 0:
        return None
    text = f"{key:08d}"
    return f"{text[:4]}-{text[4:6]}-{text[6:8]}"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload-root", type=Path, default=DEFAULT_PAYLOAD_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = check_static_packed_coordinate_regressions(payload_root=args.payload_root)
    report["outputs"] = {"json": str(args.output)}
    write_json(args.output, report)
    print(
        json.dumps(
            {
                "json": str(args.output),
                "status": report["status"],
                "scanned_rows": report["counts"]["scanned_rows"],
                "explicit_us_rows": report["counts"]["explicit_us_rows"],
                "explicit_us_outside_bounds": report["counts"]["explicit_us_outside_bounds"],
                "explicit_us_outside_state_bounds": report["counts"]["explicit_us_outside_state_bounds"],
                "named_regression_failures": report["counts"]["named_regression_failures"],
                "named_country_regression_failures": report["counts"]["named_country_regression_failures"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
        )
    )
    return 0 if report["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
