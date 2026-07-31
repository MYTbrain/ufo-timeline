"""Audit and stamp summary/detail payload policy on an existing canonical web artifact."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from parser.utils import write_json
from scripts.build_canonical_web_artifacts import (
    MERGED_MEMBER_CRAFT_DETAIL_FIELDS,
    artifact_size_report,
)


SUMMARY_FORBIDDEN_PROVENANCE_FIELDS = frozenset(
    {
        "canonical_input_id",
        "canonical_input_ids",
        "raw_fields",
        "raw_source_header",
        "raw_source_row",
        "raw_source_row_values",
        "raw_source_extra_columns",
        "raw_source_missing_columns",
        "source_claims",
        "source_provenance",
        "source_provenance_count",
    }
    | set(MERGED_MEMBER_CRAFT_DETAIL_FIELDS)
)

DETAIL_RAW_EVIDENCE_FIELDS = (
    "raw_fields",
    "raw_source_header",
    "raw_source_row",
    "raw_source_row_values",
    "raw_source_extra_columns",
    "raw_source_missing_columns",
)


def stamp_canonical_web_payload_policy(artifact_dir: Path) -> dict[str, Any]:
    artifact_dir = artifact_dir.resolve()
    manifest_path = artifact_dir / "canonical_web_manifest.json"
    summary_manifest_path = artifact_dir / "summary_manifest.json"
    chunk_manifest_path = artifact_dir / "event_chunk_manifest.json"
    compression_report_path = artifact_dir / "compression_report.json"

    manifest = _read_json(manifest_path)
    summary_manifest = _read_json(summary_manifest_path)
    chunk_manifest = _read_json(chunk_manifest_path)
    compression_report = _read_json(compression_report_path)
    counts = manifest.get("counts") if isinstance(manifest, dict) else None
    if not isinstance(counts, dict):
        raise ValueError("canonical_web_manifest.json must contain counts.")
    expected_events = _as_nonnegative_int(counts.get("events"), "manifest counts.events")

    summary_declared_events = _manifest_event_total(summary_manifest, "summary_manifest.json")
    detail_declared_events = _manifest_event_total(chunk_manifest, "event_chunk_manifest.json")
    if summary_declared_events != expected_events:
        raise ValueError(
            f"Summary manifest declares {summary_declared_events:,} events; expected {expected_events:,}."
        )
    if detail_declared_events != expected_events:
        raise ValueError(
            f"Detail manifest declares {detail_declared_events:,} events; expected {expected_events:,}."
        )

    summary_events = 0
    summary_forbidden_occurrences = 0
    for entry in summary_manifest:
        path = artifact_dir / "summary_shards" / str(entry["file"])
        events = _read_json(path)
        if not isinstance(events, list):
            raise ValueError(f"{path} must contain a JSON array.")
        summary_events += len(events)
        for event in events:
            if not isinstance(event, dict):
                raise ValueError(f"{path} contains a non-object summary event.")
            summary_forbidden_occurrences += len(SUMMARY_FORBIDDEN_PROVENANCE_FIELDS.intersection(event))
    if summary_events != expected_events:
        raise ValueError(f"Summary shards contain {summary_events:,} events; expected {expected_events:,}.")
    if summary_forbidden_occurrences:
        raise ValueError(
            "Summary shards contain raw/provenance or merged-member detail fields; refusing to stamp compact policy."
        )

    detail_events = 0
    raw_evidence_events = 0
    provenance_events = 0
    merged_member_evidence_events = 0
    for entry in chunk_manifest:
        path = artifact_dir / "event_chunks" / str(entry["file"])
        events = _read_json(path)
        if not isinstance(events, list):
            raise ValueError(f"{path} must contain a JSON array.")
        detail_events += len(events)
        for event in events:
            if not isinstance(event, dict):
                raise ValueError(f"{path} contains a non-object detail event.")
            if any(field in event for field in DETAIL_RAW_EVIDENCE_FIELDS):
                raw_evidence_events += 1
            if "source_provenance" in event or "canonical_input_ids" in event:
                provenance_events += 1
            if any(field in event for field in MERGED_MEMBER_CRAFT_DETAIL_FIELDS):
                merged_member_evidence_events += 1
    if detail_events != expected_events:
        raise ValueError(f"Detail chunks contain {detail_events:,} events; expected {expected_events:,}.")
    if raw_evidence_events <= 0:
        raise ValueError("No raw source evidence was found in lazy detail chunks.")
    if provenance_events <= 0:
        raise ValueError("No source provenance was found in lazy detail chunks.")

    policy = manifest.setdefault("policy", {})
    if not isinstance(policy, dict):
        raise ValueError("canonical_web_manifest.json policy must be an object.")
    policy.update(
        {
            "raw_source_rows_included": True,
            "source_claims_included": False,
            "full_provenance_included": True,
            "detail_raw_source_rows_included": True,
            "detail_source_claims_included": False,
            "detail_full_provenance_included": True,
            "detail_chunks_are_lazy_loaded": True,
            "summary_raw_source_rows_included": False,
            "summary_source_claims_included": False,
            "summary_full_provenance_included": False,
        }
    )
    write_json(manifest_path, manifest, indent=2)
    manifest_raw = manifest_path.read_bytes()
    manifest_gzip_path = artifact_dir / "canonical_web_manifest.json.gz"
    manifest_gzip = gzip.compress(manifest_raw, compresslevel=6, mtime=0)
    manifest_gzip_path.write_bytes(manifest_gzip)

    _refresh_compression_report(
        compression_report,
        relative_path="canonical_web_manifest.json",
        raw_bytes=len(manifest_raw),
        gzip_bytes=len(manifest_gzip),
    )
    write_json(compression_report_path, compression_report, indent=2)
    write_json(artifact_dir / "artifact_size_report.json", artifact_size_report(artifact_dir), indent=2)
    gzip_verification = _verify_gzip_pairs(artifact_dir, compression_report)

    return {
        "artifact_dir": str(artifact_dir),
        "status": "passed",
        "events": expected_events,
        "summary_events": summary_events,
        "detail_events": detail_events,
        "summary_forbidden_field_occurrences": summary_forbidden_occurrences,
        "raw_evidence_events": raw_evidence_events,
        "provenance_events": provenance_events,
        "merged_member_evidence_events": merged_member_evidence_events,
        "manifest_gzip_matches_raw": gzip.decompress(manifest_gzip_path.read_bytes()) == manifest_raw,
        **gzip_verification,
    }


def _manifest_event_total(entries: Any, label: str) -> int:
    if not isinstance(entries, list):
        raise ValueError(f"{label} must contain a JSON array.")
    total = 0
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError(f"{label} contains a non-object entry.")
        total += _as_nonnegative_int(entry.get("event_count"), f"{label} event_count")
    return total


def _refresh_compression_report(
    report: Any,
    *,
    relative_path: str,
    raw_bytes: int,
    gzip_bytes: int,
) -> None:
    if not isinstance(report, dict) or not isinstance(report.get("files"), list):
        raise ValueError("compression_report.json must contain a files array.")
    match = None
    for entry in report["files"]:
        if isinstance(entry, dict) and entry.get("path") == relative_path:
            match = entry
            break
    if match is None:
        raise ValueError(f"compression_report.json is missing {relative_path}.")
    match.update(
        {
            "gzip_path": f"{relative_path}.gz",
            "bytes": raw_bytes,
            "gzip_bytes": gzip_bytes,
            "gzip_ratio": round(gzip_bytes / raw_bytes, 3) if raw_bytes else 0,
        }
    )
    total_bytes = sum(_as_nonnegative_int(entry.get("bytes"), "compression bytes") for entry in report["files"])
    total_gzip_bytes = sum(
        _as_nonnegative_int(entry.get("gzip_bytes"), "compression gzip_bytes")
        for entry in report["files"]
    )
    report.update(
        {
            "total_files": len(report["files"]),
            "total_bytes": total_bytes,
            "total_mb": round(total_bytes / (1024 * 1024), 2),
            "total_gzip_bytes": total_gzip_bytes,
            "total_gzip_mb": round(total_gzip_bytes / (1024 * 1024), 2),
            "gzip_ratio": round(total_gzip_bytes / total_bytes, 3) if total_bytes else 0,
        }
    )


def _verify_gzip_pairs(artifact_dir: Path, report: Any) -> dict[str, int]:
    if not isinstance(report, dict) or not isinstance(report.get("files"), list):
        raise ValueError("compression_report.json must contain a files array.")
    pairs_verified = 0
    decoded_bytes_verified = 0
    for entry in report["files"]:
        if not isinstance(entry, dict):
            raise ValueError("compression_report.json contains a non-object file entry.")
        raw_path = artifact_dir / str(entry.get("path", ""))
        gzip_path = artifact_dir / str(entry.get("gzip_path", ""))
        if not raw_path.is_file() or not gzip_path.is_file():
            raise ValueError(f"Missing raw/gzip pair: {raw_path} / {gzip_path}")
        expected_raw_bytes = _as_nonnegative_int(entry.get("bytes"), "compression bytes")
        expected_gzip_bytes = _as_nonnegative_int(entry.get("gzip_bytes"), "compression gzip_bytes")
        if raw_path.stat().st_size != expected_raw_bytes:
            raise ValueError(f"Raw byte count does not match compression report: {raw_path}")
        if gzip_path.stat().st_size != expected_gzip_bytes:
            raise ValueError(f"Gzip byte count does not match compression report: {gzip_path}")
        pair_bytes = 0
        with raw_path.open("rb") as raw_stream, gzip.open(gzip_path, "rb") as gzip_stream:
            while True:
                raw_chunk = raw_stream.read(1024 * 1024)
                gzip_chunk = gzip_stream.read(1024 * 1024)
                if raw_chunk != gzip_chunk:
                    raise ValueError(f"Gzip payload does not decode to its raw source: {gzip_path}")
                if not raw_chunk:
                    break
                pair_bytes += len(raw_chunk)
        if pair_bytes != expected_raw_bytes:
            raise ValueError(f"Decoded byte count does not match compression report: {gzip_path}")
        pairs_verified += 1
        decoded_bytes_verified += pair_bytes
    return {
        "gzip_pairs_verified": pairs_verified,
        "gzip_decoded_bytes_verified": decoded_bytes_verified,
    }


def _as_nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a non-negative integer.")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a non-negative integer.") from exc
    if result < 0:
        raise ValueError(f"{label} must be a non-negative integer.")
    return result


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stamp_canonical_web_payload_policy(args.artifact_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
