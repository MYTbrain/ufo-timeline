#!/usr/bin/env python3
"""Enrich canonical web event chunks with lazy full-detail fields.

This keeps the target artifact set's coordinates, filters, chunk ids, and
render fields intact while copying narrative/source-detail fields from a detail
artifact set keyed by canonical_event_id.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sqlite3
from pathlib import Path
from typing import Any


DETAIL_FIELDS = (
    "description",
    "source_url",
    "links",
    "source_row_number",
    "posted_date_raw",
    "reported_date_raw",
    "city",
    "state_province",
    "country",
    "raw_fields",
    "raw_source_header",
    "raw_source_row",
    "raw_source_row_values",
    "raw_source_extra_columns",
    "raw_source_missing_columns",
    "source_row_anomalies",
    "source_provenance",
    "raw_event_block",
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> int:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    path.write_bytes(data)
    return len(data)


def write_gzip_json(path: Path, payload: Any) -> int:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with gzip.open(path, "wb", compresslevel=9) as handle:
        handle.write(data)
    return path.stat().st_size


def iter_chunk_paths(root: Path):
    chunk_dir = root / "event_chunks"
    yield from sorted(chunk_dir.glob("chunk_*.json"))


def build_detail_index(detail_root: Path, sqlite_path: Path) -> int:
    if sqlite_path.exists():
        sqlite_path.unlink()
    conn = sqlite3.connect(sqlite_path)
    try:
        conn.execute("CREATE TABLE details (canonical_event_id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        count = 0
        for chunk_path in iter_chunk_paths(detail_root):
            for event in read_json(chunk_path):
                event_id = event.get("canonical_event_id")
                if not event_id:
                    continue
                detail = {field: event[field] for field in DETAIL_FIELDS if field in event}
                description_short = event.get("description_short")
                if description_short:
                    detail["description_short"] = description_short
                if not detail:
                    continue
                conn.execute(
                    "INSERT OR REPLACE INTO details(canonical_event_id, payload) VALUES (?, ?)",
                    (event_id, json.dumps(detail, ensure_ascii=False, separators=(",", ":"))),
                )
                count += 1
            conn.commit()
        return count
    finally:
        conn.close()


def enrich_target(target_root: Path, sqlite_path: Path, write_gzip: bool) -> dict[str, Any]:
    conn = sqlite3.connect(sqlite_path)
    stats = {
        "target": str(target_root),
        "chunks": 0,
        "events": 0,
        "matched": 0,
        "description_added": 0,
        "raw_event_block_added": 0,
    }
    try:
        for chunk_path in iter_chunk_paths(target_root):
            events = read_json(chunk_path)
            changed = False
            for event in events:
                stats["events"] += 1
                event_id = event.get("canonical_event_id")
                if not event_id:
                    continue
                row = conn.execute("SELECT payload FROM details WHERE canonical_event_id = ?", (event_id,)).fetchone()
                if not row:
                    continue
                stats["matched"] += 1
                detail = json.loads(row[0])
                for key, value in detail.items():
                    if key == "description_short" and event.get("description_short"):
                        continue
                    if value in (None, "", [], {}):
                        continue
                    if key == "description" and not event.get("description"):
                        stats["description_added"] += 1
                    if key == "raw_event_block" and not event.get("raw_event_block"):
                        stats["raw_event_block_added"] += 1
                    event[key] = value
                    changed = True
            if changed:
                write_json(chunk_path, events)
                if write_gzip:
                    write_gzip_json(chunk_path.with_suffix(".json.gz"), events)
            stats["chunks"] += 1
        manifest_path = target_root / "canonical_web_manifest.json"
        manifest = read_json(manifest_path)
        policy = manifest.setdefault("policy", {})
        policy["raw_source_rows_included"] = True
        policy["source_claims_included"] = False
        policy["full_provenance_included"] = True
        policy["detail_raw_source_rows_included"] = True
        policy["detail_source_claims_included"] = False
        policy["detail_full_provenance_included"] = True
        policy["detail_chunks_are_lazy_loaded"] = True
        policy.setdefault("summary_raw_source_rows_included", False)
        policy.setdefault("summary_source_claims_included", False)
        policy.setdefault("summary_full_provenance_included", False)
        write_json(manifest_path, manifest)
        if write_gzip:
            write_gzip_json(manifest_path.with_suffix(".json.gz"), manifest)
        return stats
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--detail-root", required=True, type=Path)
    parser.add_argument("--target-root", required=True, action="append", type=Path)
    parser.add_argument("--sqlite-path", default=Path(".tmp/detail_chunk_lookup.sqlite"), type=Path)
    parser.add_argument("--write-gzip", action="store_true")
    args = parser.parse_args()

    args.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    indexed = build_detail_index(args.detail_root, args.sqlite_path)
    results = []
    for target_root in args.target_root:
        results.append(enrich_target(target_root, args.sqlite_path, args.write_gzip))
    print(json.dumps({"indexed": indexed, "targets": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
