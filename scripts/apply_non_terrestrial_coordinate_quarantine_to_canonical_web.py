"""Quarantine reviewed non-terrestrial placeholders in canonical web artifacts.

The source records remain searchable and retain their raw coordinate fields.
Only the Earth-map coordinates are removed. The patch is guarded by exact
artifact locations and expected old values, then packed point and trace
artifacts are rebuilt from the patched summary rows.
"""

from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from parser.packed_points import META_FILENAME, POINTS_FILENAME, export_packed_points
from parser.trace_segments import (
    TRACE_AGGREGATE_BINS_FILENAME,
    TRACE_AGGREGATE_BINS_META_FILENAME,
    TRACE_EVENT_INDEX_FILENAME,
    TRACE_EVENT_INDEX_META_FILENAME,
    TRACE_SEGMENTS_FILENAME,
    TRACE_SEGMENTS_META_FILENAME,
    export_trace_artifacts,
)
from parser.utils import ensure_parent_dir, write_json
from scripts.build_canonical_web_artifacts import MappedBounds


DEFAULT_ARTIFACT_DIR = Path("data/canonical_web")
DEFAULT_SIDECAR = Path("data/reports/non_terrestrial_coordinate_quarantine_sidecar_v147.json")
DEFAULT_REPORT = Path("data/reports/non_terrestrial_coordinate_quarantine_apply_v147.json")

EVENT_CHUNK_PATTERN = re.compile(r"^event_chunks/chunk_\d{6}\.json$")
SUMMARY_SHARD_PATTERN = re.compile(r"^summary_shards/summary_\d{6}\.json$")
PACKED_ARTIFACT_PATHS = (
    POINTS_FILENAME,
    META_FILENAME,
    TRACE_EVENT_INDEX_FILENAME,
    TRACE_EVENT_INDEX_META_FILENAME,
    TRACE_SEGMENTS_FILENAME,
    TRACE_SEGMENTS_META_FILENAME,
    TRACE_AGGREGATE_BINS_FILENAME,
    TRACE_AGGREGATE_BINS_META_FILENAME,
)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--sidecar", type=Path, default=DEFAULT_SIDECAR)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--no-gzip",
        action="store_true",
        help="Do not refresh gzip siblings. Intended only for small test fixtures.",
    )
    return parser


def apply_non_terrestrial_coordinate_quarantine(
    *,
    artifact_dir: Path,
    sidecar_path: Path,
    report_output: Path,
    write_gzip: bool = True,
) -> dict[str, Any]:
    artifact_dir = artifact_dir.resolve()
    sidecar_path = sidecar_path.resolve()
    report_output = report_output.resolve()
    sidecar = _read_json(sidecar_path)
    patches = _load_patches(sidecar)
    manifest = _read_json(artifact_dir / "canonical_web_manifest.json")
    chunk_manifest = _read_json(artifact_dir / "event_chunk_manifest.json")

    detail_payloads, summary_payloads, patched_events = _preflight_patches(
        artifact_dir=artifact_dir,
        patches=patches,
    )
    summary_rows = _load_summary_rows_with_overrides(
        artifact_dir=artifact_dir,
        summary_payloads=summary_payloads,
    )
    expected_event_count = int(manifest.get("counts", {}).get("events") or len(summary_rows))
    if len(summary_rows) != expected_event_count:
        raise RuntimeError(
            f"Summary row count changed unexpectedly: {len(summary_rows)} != {expected_event_count}"
        )

    mapped_before = int(manifest.get("counts", {}).get("mapped_events") or 0)
    mapped_after = sum(1 for row in summary_rows if _is_mapped(row))
    if mapped_before - mapped_after != len(patches):
        raise RuntimeError(
            "Mapped-event reduction does not match quarantine count: "
            f"{mapped_before} -> {mapped_after}, patches={len(patches)}"
        )

    staged_relative_paths: list[str] = []
    compression_summary: dict[str, Any] | None = None
    with tempfile.TemporaryDirectory(
        prefix=".non_terrestrial_coordinate_quarantine_",
        dir=artifact_dir.parent,
    ) as temporary_dir:
        stage_root = Path(temporary_dir)
        for relative_path, payload in {**detail_payloads, **summary_payloads}.items():
            _write_compact_json(stage_root / relative_path, payload)
            staged_relative_paths.append(relative_path)

        packed_stage = stage_root / "_packed"
        points_metadata = export_packed_points(
            summary_rows,
            packed_stage,
            chunk_manifest=chunk_manifest,
        )
        trace_metadata = export_trace_artifacts(summary_rows, packed_stage)
        for name in PACKED_ARTIFACT_PATHS:
            staged_path = stage_root / name
            ensure_parent_dir(staged_path)
            os.replace(packed_stage / name, staged_path)
            staged_relative_paths.append(name)
        packed_stage.rmdir()

        refreshed_manifest = _refresh_manifest(
            manifest=manifest,
            sidecar_path=sidecar_path,
            summary_rows=summary_rows,
            points_metadata=points_metadata,
            trace_metadata=trace_metadata,
            patch_count=len(patches),
        )
        _write_compact_json(stage_root / "canonical_web_manifest.json", refreshed_manifest)
        staged_relative_paths.append("canonical_web_manifest.json")

        size_report = _build_artifact_size_report(
            artifact_dir=artifact_dir,
            stage_root=stage_root,
        )
        _write_pretty_json(stage_root / "artifact_size_report.json", size_report)
        staged_relative_paths.append("artifact_size_report.json")

        gzip_relative_paths: list[str] = []
        if write_gzip:
            compression_report = _refresh_changed_gzip_artifacts(
                artifact_dir=artifact_dir,
                stage_root=stage_root,
                changed_raw_paths=sorted(
                    set(staged_relative_paths) - {"artifact_size_report.json"}
                ),
            )
            _write_pretty_json(stage_root / "compression_report.json", compression_report)
            staged_relative_paths.append("compression_report.json")
            gzip_relative_paths = [
                f"{relative_path}.gz"
                for relative_path in sorted(
                    set(staged_relative_paths)
                    - {"artifact_size_report.json", "compression_report.json"}
                )
            ]
            compression_summary = {
                "total_files": compression_report["total_files"],
                "total_gzip_bytes": compression_report["total_gzip_bytes"],
                "total_gzip_mb": compression_report["total_gzip_mb"],
                "refreshed_file_count": len(gzip_relative_paths),
            }

        commit_paths = sorted(set(staged_relative_paths + gzip_relative_paths))
        _commit_staged_files(
            artifact_dir=artifact_dir,
            stage_root=stage_root,
            relative_paths=commit_paths,
        )

    changed_hashes = {
        relative_path: _sha256(artifact_dir / relative_path)
        for relative_path in sorted(set(staged_relative_paths))
    }
    report = {
        "schema_version": 1,
        "mode": "canonical_web_non_terrestrial_coordinate_quarantine",
        "policy": "explicit_non_terrestrial_jurisdiction_plus_exact_zero_coordinate",
        "canonical_full_mutated": False,
        "canonical_web_mutated": True,
        "event_records_preserved": True,
        "raw_source_coordinates_preserved": True,
        "inputs": {
            "artifact_dir": str(artifact_dir),
            "sidecar": str(sidecar_path),
        },
        "outputs": {
            "report": str(report_output),
        },
        "quarantined_event_count": len(patched_events),
        "mapped_before_count": mapped_before,
        "mapped_after_count": mapped_after,
        "mapped_reduction_count": mapped_before - mapped_after,
        "points_row_count": points_metadata["row_count"],
        "trace_event_count": trace_metadata["trace_events"]["row_count"],
        "trace_segment_count": trace_metadata["trace_segments"]["row_count"],
        "trace_aggregate_bin_count": trace_metadata["trace_aggregate_bins"]["row_count"],
        "patched_events": patched_events,
        "changed_raw_files": sorted(set(staged_relative_paths)),
        "changed_raw_file_sha256": changed_hashes,
        "compression": compression_summary,
    }
    write_json(report_output, report, indent=2)
    return report


def _load_patches(sidecar: Any) -> list[dict[str, Any]]:
    if not isinstance(sidecar, dict):
        raise ValueError("Sidecar must be a JSON object.")
    if sidecar.get("policy") != "explicit_non_terrestrial_jurisdiction_plus_exact_zero_coordinate":
        raise ValueError("Sidecar policy is not the reviewed non-terrestrial placeholder policy.")
    patches = sidecar.get("proposed_patches")
    if not isinstance(patches, list) or not patches:
        raise ValueError("Sidecar must contain a non-empty proposed_patches list.")

    canonical_ids: set[str] = set()
    event_ids: set[int] = set()
    for patch in patches:
        if not isinstance(patch, dict):
            raise ValueError("Each patch must be a JSON object.")
        canonical_id = str(patch.get("canonical_event_id") or "")
        event_id = _required_int(patch.get("event_id"), field="event_id")
        if not canonical_id:
            raise ValueError("Each patch must contain canonical_event_id.")
        if canonical_id in canonical_ids or event_id in event_ids:
            raise ValueError("Sidecar contains duplicate canonical_event_id or event_id values.")
        canonical_ids.add(canonical_id)
        event_ids.add(event_id)
        _validate_artifact_location(patch.get("detail_artifact"), EVENT_CHUNK_PATTERN)
        _validate_artifact_location(patch.get("summary_artifact"), SUMMARY_SHARD_PATTERN)
        if not isinstance(patch.get("expected_detail_fields"), dict):
            raise ValueError(f"{canonical_id}: expected_detail_fields must be an object.")
        if not isinstance(patch.get("expected_summary_fields"), dict):
            raise ValueError(f"{canonical_id}: expected_summary_fields must be an object.")
        if not isinstance(patch.get("expected_raw_fields"), dict):
            raise ValueError(f"{canonical_id}: expected_raw_fields must be an object.")
        set_fields = patch.get("set_fields")
        if not isinstance(set_fields, dict):
            raise ValueError(f"{canonical_id}: set_fields must be an object.")
        required_set_fields = {
            "lat": None,
            "lon": None,
            "coordinate_source": "unresolved",
            "location_precision": "unknown",
            "has_coordinates": False,
        }
        for key, expected in required_set_fields.items():
            if key not in set_fields or set_fields[key] != expected:
                raise ValueError(f"{canonical_id}: set_fields[{key!r}] must be {expected!r}.")
    return patches


def _preflight_patches(
    *,
    artifact_dir: Path,
    patches: list[dict[str, Any]],
) -> tuple[dict[str, list[Any]], dict[str, list[Any]], list[dict[str, Any]]]:
    detail_payloads = _load_target_payloads(
        artifact_dir=artifact_dir,
        locations=[patch["detail_artifact"] for patch in patches],
    )
    summary_payloads = _load_target_payloads(
        artifact_dir=artifact_dir,
        locations=[patch["summary_artifact"] for patch in patches],
    )
    patched_events: list[dict[str, Any]] = []

    for patch in patches:
        canonical_id = str(patch["canonical_event_id"])
        event_id = int(patch["event_id"])
        detail_location = patch["detail_artifact"]
        summary_location = patch["summary_artifact"]
        detail_row = _target_row(detail_payloads, detail_location)
        summary_row = _target_row(summary_payloads, summary_location)

        _validate_expected_fields(
            row=detail_row,
            expected=patch["expected_detail_fields"],
            context=f"{detail_location['path']}[{detail_location['index']}]",
        )
        _validate_expected_fields(
            row=summary_row,
            expected=patch["expected_summary_fields"],
            context=f"{summary_location['path']}[{summary_location['index']}]",
        )
        raw_fields = detail_row.get("raw_fields")
        if not isinstance(raw_fields, dict):
            raise ValueError(f"{canonical_id}: detail row has no raw_fields object.")
        _validate_expected_fields(
            row=raw_fields,
            expected=patch["expected_raw_fields"],
            context=f"{canonical_id}.raw_fields",
        )
        if str(detail_row.get("canonical_event_id") or "") != canonical_id:
            raise ValueError(f"{canonical_id}: canonical event ID guard failed.")
        if detail_row.get("event_id") != event_id or summary_row.get("event_id") != event_id:
            raise ValueError(f"{canonical_id}: numeric event ID guard failed.")
        if not _is_mapped(detail_row) or not _is_mapped(summary_row):
            raise ValueError(f"{canonical_id}: target is not currently mapped.")

        before = _coordinate_snapshot(detail_row)
        for row in (detail_row, summary_row):
            row.update(patch["set_fields"])
        after = _coordinate_snapshot(detail_row)
        patched_events.append(
            {
                "canonical_event_id": canonical_id,
                "event_id": event_id,
                "source_id": detail_row.get("source_id"),
                "sort_date_iso": detail_row.get("sort_date_iso"),
                "location_raw": detail_row.get("location_raw"),
                "detail_artifact": detail_location,
                "summary_artifact": summary_location,
                "before": before,
                "after": after,
            }
        )
    return detail_payloads, summary_payloads, patched_events


def _load_target_payloads(
    *,
    artifact_dir: Path,
    locations: list[dict[str, Any]],
) -> dict[str, list[Any]]:
    payloads: dict[str, list[Any]] = {}
    for location in locations:
        relative_path = str(location["path"])
        if relative_path in payloads:
            continue
        payload = _read_json(artifact_dir / relative_path)
        if not isinstance(payload, list):
            raise ValueError(f"Expected a JSON array: {relative_path}")
        payloads[relative_path] = payload
    return payloads


def _target_row(
    payloads: dict[str, list[Any]],
    location: dict[str, Any],
) -> dict[str, Any]:
    relative_path = str(location["path"])
    index = int(location["index"])
    payload = payloads[relative_path]
    if index < 0 or index >= len(payload):
        raise IndexError(f"{relative_path}[{index}] is outside the artifact array.")
    row = payload[index]
    if not isinstance(row, dict):
        raise ValueError(f"{relative_path}[{index}] is not an object.")
    return row


def _load_summary_rows_with_overrides(
    *,
    artifact_dir: Path,
    summary_payloads: dict[str, list[Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted((artifact_dir / "summary_shards").glob("*.json")):
        relative_path = str(path.relative_to(artifact_dir)).replace("\\", "/")
        payload = summary_payloads.get(relative_path)
        if payload is None:
            payload = _read_json(path)
        if not isinstance(payload, list):
            raise ValueError(f"Expected summary shard array: {relative_path}")
        rows.extend(row for row in payload if isinstance(row, dict))
    return rows


def _refresh_manifest(
    *,
    manifest: dict[str, Any],
    sidecar_path: Path,
    summary_rows: list[dict[str, Any]],
    points_metadata: dict[str, Any],
    trace_metadata: dict[str, Any],
    patch_count: int,
) -> dict[str, Any]:
    refreshed = json.loads(json.dumps(manifest))
    location_precision_counts: Counter[str] = Counter()
    coordinate_source_counts: Counter[str] = Counter()
    mapped_bounds = MappedBounds()
    mapped_events = 0
    for row in summary_rows:
        location_precision_counts[str(row.get("location_precision") or "unknown")] += 1
        coordinate_source_counts[str(row.get("coordinate_source") or "unknown")] += 1
        if _is_mapped(row):
            mapped_events += 1
            mapped_bounds.add(float(row["lat"]), float(row["lon"]))

    counts = refreshed.setdefault("counts", {})
    counts["events"] = len(summary_rows)
    counts["mapped_events"] = mapped_events
    counts["trace_events"] = trace_metadata["trace_events"]["row_count"]
    counts["trace_segments"] = trace_metadata["trace_segments"]["row_count"]
    counts["trace_aggregate_bins"] = trace_metadata["trace_aggregate_bins"]["row_count"]
    counts["location_precision_counts"] = dict(sorted(location_precision_counts.items()))
    counts["coordinate_source_counts"] = dict(sorted(coordinate_source_counts.items()))
    counts["mapped_bounds"] = mapped_bounds.to_json()
    refreshed["packed_points"] = {
        "schema_version": points_metadata.get("schema_version"),
        "row_count": points_metadata.get("row_count"),
        "bytes_per_row": points_metadata.get("bytes_per_row"),
    }
    refreshed["packed_trace_segments"] = {
        "schema_version": trace_metadata["trace_segments"].get("schema_version"),
        "row_count": trace_metadata["trace_segments"].get("row_count"),
        "bytes_per_row": trace_metadata["trace_segments"].get("bytes_per_row"),
        "full_window_mode": trace_metadata["trace_segments"]
        .get("render_plan", {})
        .get("full_window_mode"),
    }
    refreshed["packed_trace_events"] = {
        "schema_version": trace_metadata["trace_events"].get("schema_version"),
        "row_count": trace_metadata["trace_events"].get("row_count"),
        "bytes_per_row": trace_metadata["trace_events"].get("bytes_per_row"),
        "row_order": "canonical_playback_order",
        "filtered_segment_rule": "filter rows first, then connect adjacent visible rows client-side",
    }
    refreshed["packed_trace_aggregate_bins"] = {
        "schema_version": trace_metadata["trace_aggregate_bins"].get("schema_version"),
        "row_count": trace_metadata["trace_aggregate_bins"].get("row_count"),
        "bytes_per_row": trace_metadata["trace_aggregate_bins"].get("bytes_per_row"),
        "runtime_warning": trace_metadata["trace_aggregate_bins"]
        .get("render_contract", {})
        .get("runtime_warning", "Use for full-universe wide-window LOD only."),
    }
    refreshed.setdefault("policy", {})["non_terrestrial_coordinate_quarantine"] = {
        "applied": True,
        "sidecar": str(sidecar_path),
        "policy": "explicit_non_terrestrial_jurisdiction_plus_exact_zero_coordinate",
        "quarantined_event_count": patch_count,
        "event_records_preserved": True,
        "raw_source_coordinates_preserved": True,
        "canonical_full_mutated": False,
    }
    return refreshed


def _build_artifact_size_report(
    *,
    artifact_dir: Path,
    stage_root: Path,
) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    total_bytes = 0
    relative_paths = {
        str(path.relative_to(artifact_dir)).replace("\\", "/")
        for path in artifact_dir.rglob("*")
        if path.is_file()
    }
    relative_paths.update(
        str(path.relative_to(stage_root)).replace("\\", "/")
        for path in stage_root.rglob("*")
        if path.is_file()
    )
    for relative_path in sorted(relative_paths):
        path = artifact_dir / relative_path
        staged_path = stage_root / relative_path
        effective_path = staged_path if staged_path.exists() else path
        if effective_path.suffix == ".gz":
            continue
        if effective_path.name in {
            "artifact_size_report.json",
            "compression_probe.json",
            "compression_report.json",
        }:
            continue
        size_bytes = effective_path.stat().st_size
        total_bytes += size_bytes
        files.append(
            {
                "path": relative_path,
                "bytes": size_bytes,
                "mb": round(size_bytes / (1024 * 1024), 4),
            }
        )
    return {
        "total_files": len(files),
        "total_bytes": total_bytes,
        "total_mb": round(total_bytes / (1024 * 1024), 2),
        "files": sorted(files, key=lambda item: (-item["bytes"], item["path"])),
    }


def _refresh_changed_gzip_artifacts(
    *,
    artifact_dir: Path,
    stage_root: Path,
    changed_raw_paths: list[str],
) -> dict[str, Any]:
    report_path = artifact_dir / "compression_report.json"
    report = _read_json(report_path)
    entries = {
        str(entry["path"]): dict(entry)
        for entry in report.get("files", [])
        if isinstance(entry, dict) and entry.get("path")
    }
    for relative_path in changed_raw_paths:
        raw_path = stage_root / relative_path
        if not raw_path.is_file():
            raise FileNotFoundError(f"Changed raw artifact was not staged: {relative_path}")
        raw_bytes = raw_path.read_bytes()
        gzip_bytes = gzip.compress(raw_bytes, compresslevel=6, mtime=0)
        gzip_relative_path = f"{relative_path}.gz"
        gzip_path = stage_root / gzip_relative_path
        ensure_parent_dir(gzip_path)
        gzip_path.write_bytes(gzip_bytes)
        entries[relative_path] = {
            "path": relative_path,
            "gzip_path": gzip_relative_path,
            "bytes": len(raw_bytes),
            "gzip_bytes": len(gzip_bytes),
            "gzip_ratio": round(len(gzip_bytes) / len(raw_bytes), 3) if raw_bytes else 0,
        }
    sorted_entries = sorted(entries.values(), key=lambda item: (-item["bytes"], item["path"]))
    total_bytes = sum(int(entry["bytes"]) for entry in sorted_entries)
    total_gzip_bytes = sum(int(entry["gzip_bytes"]) for entry in sorted_entries)
    return {
        "total_files": len(sorted_entries),
        "total_bytes": total_bytes,
        "total_mb": round(total_bytes / (1024 * 1024), 2),
        "total_gzip_bytes": total_gzip_bytes,
        "total_gzip_mb": round(total_gzip_bytes / (1024 * 1024), 2),
        "gzip_ratio": round(total_gzip_bytes / total_bytes, 3) if total_bytes else 0,
        "files": sorted_entries,
    }


def _commit_staged_files(
    *,
    artifact_dir: Path,
    stage_root: Path,
    relative_paths: list[str],
) -> None:
    for relative_path in relative_paths:
        source = stage_root / relative_path
        destination = artifact_dir / relative_path
        if not source.is_file():
            raise FileNotFoundError(f"Staged artifact is missing: {relative_path}")
        ensure_parent_dir(destination)
    for relative_path in relative_paths:
        os.replace(stage_root / relative_path, artifact_dir / relative_path)


def _validate_artifact_location(value: Any, pattern: re.Pattern[str]) -> None:
    if not isinstance(value, dict):
        raise ValueError("Artifact location must be an object.")
    relative_path = str(value.get("path") or "").replace("\\", "/")
    if not pattern.fullmatch(relative_path):
        raise ValueError(f"Invalid guarded artifact path: {relative_path!r}")
    _required_int(value.get("index"), field=f"{relative_path}.index")


def _validate_expected_fields(
    *,
    row: Mapping[str, Any],
    expected: Mapping[str, Any],
    context: str,
) -> None:
    for key, expected_value in expected.items():
        if key not in row:
            raise ValueError(f"{context}: expected field {key!r} is missing.")
        if row.get(key) != expected_value:
            raise ValueError(
                f"{context}: stale guard for {key!r}: "
                f"expected {expected_value!r}, found {row.get(key)!r}."
            )


def _coordinate_snapshot(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "lat": row.get("lat"),
        "lon": row.get("lon"),
        "coordinate_source": row.get("coordinate_source"),
        "location_precision": row.get("location_precision"),
        "has_coordinates": row.get("has_coordinates"),
    }


def _is_mapped(row: Mapping[str, Any]) -> bool:
    return (
        row.get("coordinate_source") != "unresolved"
        and _finite_float(row.get("lat")) is not None
        and _finite_float(row.get("lon")) is not None
    )


def _finite_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _required_int(value: Any, *, field: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer.") from exc


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_compact_json(path: Path, payload: Any) -> None:
    ensure_parent_dir(path)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def _write_pretty_json(path: Path, payload: Any) -> None:
    ensure_parent_dir(path)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    args = build_argument_parser().parse_args()
    report = apply_non_terrestrial_coordinate_quarantine(
        artifact_dir=args.artifact_dir,
        sidecar_path=args.sidecar,
        report_output=args.report_output,
        write_gzip=not args.no_gzip,
    )
    print(
        json.dumps(
            {
                "quarantined_event_count": report["quarantined_event_count"],
                "mapped_reduction_count": report["mapped_reduction_count"],
                "points_row_count": report["points_row_count"],
                "trace_event_count": report["trace_event_count"],
                "report": report["outputs"]["report"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
