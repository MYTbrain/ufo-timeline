"""Apply reviewed coordinate repairs to existing canonical web artifacts.

This is intentionally narrower than rebuilding canonical_web from
``data/canonical_full``. The current public app uses enriched canonical web
artifacts with many geocoded rows that are not present in the raw canonical_full
JSONL source. This script preserves that enriched artifact set, patches only
reviewed sidecar rows, and regenerates packed point/trace binaries from the
patched summary shards.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
from collections import Counter
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from parser.packed_points import export_packed_points
from parser.trace_segments import export_trace_artifacts
from parser.utils import ensure_parent_dir, write_json
from scripts.build_canonical_web_artifacts import MappedBounds, top_counts, write_gzip_artifacts
from scripts.build_coordinate_admin_matched_repair_candidates import admin_bounds, inside_bounds


DEFAULT_ARTIFACT_DIR = Path("data/canonical_web")
DEFAULT_SIDECAR = Path("data/reports/coordinate_admin_matched_repair_sidecar_current_v110.json")
DEFAULT_REPORT = Path("data/reports/coordinate_admin_matched_repair_canonical_web_apply_v110.json")


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR))
    parser.add_argument("--sidecar", default=str(DEFAULT_SIDECAR))
    parser.add_argument("--report-output", default=str(DEFAULT_REPORT))
    parser.add_argument(
        "--no-gzip",
        action="store_true",
        help="Do not refresh .gz siblings after patching artifacts.",
    )
    return parser


def apply_sidecar_to_canonical_web(
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
    patches = _sidecar_patches(sidecar)
    patch_by_canonical_id = {str(patch["canonical_event_id"]): patch for patch in patches}
    if len(patch_by_canonical_id) != len(patches):
        raise ValueError("Sidecar contains duplicate canonical_event_id values.")

    chunk_manifest = _read_json(artifact_dir / "event_chunk_manifest.json")
    summary_manifest = _read_json(artifact_dir / "summary_manifest.json")

    chunk_result = _patch_event_chunks(
        artifact_dir=artifact_dir,
        patch_by_canonical_id=patch_by_canonical_id,
    )
    event_id_to_patch = {
        item["event_id"]: patch_by_canonical_id[item["canonical_event_id"]]
        for item in chunk_result["patched_events"]
    }
    summary_result = _patch_summary_shards(
        artifact_dir=artifact_dir,
        event_id_to_patch=event_id_to_patch,
    )
    if summary_result["patched_count"] != chunk_result["patched_count"]:
        raise RuntimeError(
            "Patched event chunk count and summary shard count differ: "
            f"{chunk_result['patched_count']} vs {summary_result['patched_count']}"
        )

    summary_rows = _load_summary_rows(artifact_dir)
    points_metadata = export_packed_points(summary_rows, artifact_dir, chunk_manifest=chunk_manifest)
    trace_metadata = export_trace_artifacts(summary_rows, artifact_dir)
    manifest_result = _refresh_manifest(
        artifact_dir=artifact_dir,
        sidecar_path=sidecar_path,
        patched_events=chunk_result["patched_events"],
        summary_rows=summary_rows,
        points_metadata=points_metadata,
        trace_metadata=trace_metadata,
    )
    size_report = _write_artifact_size_report(artifact_dir)
    compression_report = None
    if write_gzip:
        compression_report = write_gzip_artifacts(artifact_dir)
        write_json(artifact_dir / "compression_report.json", compression_report, indent=2)

    report = {
        "schema_version": 1,
        "mode": "canonical_web_artifact_patch",
        "canonical_full_mutated": False,
        "canonical_web_mutated": True,
        "inputs": {
            "artifact_dir": str(artifact_dir),
            "sidecar": str(sidecar_path),
        },
        "outputs": {
            "report": str(report_output),
        },
        "sidecar_patch_count": len(patches),
        "event_chunk_patched_count": chunk_result["patched_count"],
        "summary_shard_patched_count": summary_result["patched_count"],
        "missing_patch_count": len(chunk_result["missing_patch_ids"]),
        "missing_patch_ids": chunk_result["missing_patch_ids"],
        "patched_events": chunk_result["patched_events"],
        "patched_event_chunk_files": chunk_result["patched_files"],
        "patched_summary_shard_files": summary_result["patched_files"],
        "points_row_count": points_metadata.get("row_count"),
        "trace_event_count": trace_metadata.get("trace_events", {}).get("row_count"),
        "trace_segment_count": trace_metadata.get("trace_segments", {}).get("row_count"),
        "trace_aggregate_bin_count": trace_metadata.get("trace_aggregate_bins", {}).get("row_count"),
        "manifest_counts": manifest_result["counts"],
        "artifact_size_report": size_report,
        "compression_report": {
            "total_gzip_mb": compression_report.get("total_gzip_mb"),
            "total_files": compression_report.get("total_files"),
        }
        if compression_report
        else None,
    }
    write_json(report_output, report, indent=2)
    return report


def _sidecar_patches(sidecar: Any) -> list[dict[str, Any]]:
    if not isinstance(sidecar, dict):
        raise ValueError("Sidecar must be a JSON object.")
    patches = sidecar.get("proposed_patches")
    if not isinstance(patches, list) or not patches:
        raise ValueError("Sidecar must contain a non-empty proposed_patches list.")
    for patch in patches:
        if not isinstance(patch, dict) or not patch.get("canonical_event_id"):
            raise ValueError("Each sidecar patch must contain canonical_event_id.")
        if not isinstance(patch.get("set_fields"), dict):
            raise ValueError(f"Patch {patch.get('canonical_event_id')} lacks set_fields.")
    return patches


def _patch_event_chunks(
    *,
    artifact_dir: Path,
    patch_by_canonical_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    chunks_dir = artifact_dir / "event_chunks"
    found: set[str] = set()
    patched_files: list[str] = []
    patched_events: list[dict[str, Any]] = []
    for path in sorted(chunks_dir.glob("*.json")):
        rows = _read_json(path)
        if not isinstance(rows, list):
            raise ValueError(f"Expected event chunk array: {path}")
        changed = False
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            canonical_id = str(row.get("canonical_event_id") or "")
            patch = patch_by_canonical_id.get(canonical_id)
            if patch is None:
                continue
            _validate_patch_target(row=row, patch=patch, context=f"{path.name}[{index}]")
            before = _row_coordinate_snapshot(row)
            _apply_patch_fields(row, patch)
            after = _row_coordinate_snapshot(row)
            found.add(canonical_id)
            patched_events.append(
                {
                    "canonical_event_id": canonical_id,
                    "event_id": row.get("event_id"),
                    "chunk": path.name,
                    "detail_index": index,
                    "before": before,
                    "after": after,
                }
            )
            changed = True
        if changed:
            _write_compact_json(path, rows)
            patched_files.append(str(path.relative_to(artifact_dir)).replace("\\", "/"))
    missing = sorted(set(patch_by_canonical_id) - found)
    if missing:
        raise RuntimeError(f"Missing patch targets in event chunks: {missing}")
    return {
        "patched_count": len(found),
        "patched_files": patched_files,
        "patched_events": patched_events,
        "missing_patch_ids": missing,
    }


def _patch_summary_shards(
    *,
    artifact_dir: Path,
    event_id_to_patch: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    summaries_dir = artifact_dir / "summary_shards"
    found: set[int] = set()
    patched_files: list[str] = []
    for path in sorted(summaries_dir.glob("*.json")):
        rows = _read_json(path)
        if not isinstance(rows, list):
            raise ValueError(f"Expected summary shard array: {path}")
        changed = False
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            event_id = row.get("event_id")
            patch = event_id_to_patch.get(event_id)
            if patch is None:
                continue
            _validate_patch_target(row=row, patch=patch, context=f"{path.name}[{index}]")
            _apply_patch_fields(row, patch)
            found.add(event_id)
            changed = True
        if changed:
            _write_compact_json(path, rows)
            patched_files.append(str(path.relative_to(artifact_dir)).replace("\\", "/"))
    missing = sorted(set(event_id_to_patch) - found)
    if missing:
        raise RuntimeError(f"Missing patch targets in summary shards: {missing}")
    return {
        "patched_count": len(found),
        "patched_files": patched_files,
    }


def _validate_patch_target(*, row: dict[str, Any], patch: dict[str, Any], context: str) -> None:
    current_lat = _finite_float(row.get("lat"))
    current_lon = _finite_float(row.get("lon"))
    if current_lat is None or current_lon is None:
        raise ValueError(f"{context}: target row is not currently mapped.")
    new_fields = patch.get("set_fields", {})
    new_lat = _finite_float(new_fields.get("lat"))
    new_lon = _finite_float(new_fields.get("lon"))
    if new_lat is None or new_lon is None:
        raise ValueError(f"{context}: patch has no finite replacement coordinates.")
    country = str(patch.get("country") or "")
    admin = str(patch.get("declared_admin") or "")
    bounds = admin_bounds(country=country, admin=admin)
    if bounds is not None:
        if inside_bounds(lat=current_lat, lon=current_lon, bounds=bounds):
            raise ValueError(f"{context}: current coordinate is already inside declared admin bounds.")
        if not inside_bounds(lat=new_lat, lon=new_lon, bounds=bounds):
            raise ValueError(f"{context}: replacement coordinate is outside declared admin bounds.")
    if _distance_degrees(current_lat, current_lon, new_lat, new_lon) < 0.01:
        raise ValueError(f"{context}: replacement is too close to current coordinate to be a repair.")


def _apply_patch_fields(row: dict[str, Any], patch: dict[str, Any]) -> None:
    for key, value in patch["set_fields"].items():
        row[key] = value
    row["has_coordinates"] = True


def _row_coordinate_snapshot(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "lat": row.get("lat"),
        "lon": row.get("lon"),
        "coordinate_source": row.get("coordinate_source"),
        "location_precision": row.get("location_precision"),
    }


def _load_summary_rows(artifact_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted((artifact_dir / "summary_shards").glob("*.json")):
        payload = _read_json(path)
        if not isinstance(payload, list):
            raise ValueError(f"Expected summary shard array: {path}")
        rows.extend(row for row in payload if isinstance(row, dict))
    return rows


def _refresh_manifest(
    *,
    artifact_dir: Path,
    sidecar_path: Path,
    patched_events: list[dict[str, Any]],
    summary_rows: list[dict[str, Any]],
    points_metadata: dict[str, Any],
    trace_metadata: dict[str, Any],
) -> dict[str, Any]:
    manifest_path = artifact_dir / "canonical_web_manifest.json"
    manifest = _read_json(manifest_path)
    if not isinstance(manifest, dict):
        raise ValueError("canonical_web_manifest.json must be an object.")
    source_counts: Counter[str] = Counter()
    type_counts: Counter[str] = Counter()
    shape_counts: Counter[str] = Counter()
    date_precision_counts: Counter[str] = Counter()
    location_precision_counts: Counter[str] = Counter()
    coordinate_source_counts: Counter[str] = Counter()
    mapped_bounds = MappedBounds()
    mapped_events = 0
    for row in summary_rows:
        source_counts[str(row.get("source") or "unknown")] += 1
        type_counts[str(row.get("type") or "Unknown")] += 1
        shape_counts[str(row.get("shape_normalized") or "Unknown")] += 1
        date_precision_counts[str(row.get("date_precision") or "unknown")] += 1
        location_precision_counts[str(row.get("location_precision") or "unknown")] += 1
        coordinate_source_counts[str(row.get("coordinate_source") or "unknown")] += 1
        lat = _finite_float(row.get("lat"))
        lon = _finite_float(row.get("lon"))
        if row.get("coordinate_source") != "unresolved" and lat is not None and lon is not None:
            mapped_events += 1
            mapped_bounds.add(lat, lon)
    counts = manifest.setdefault("counts", {})
    counts["events"] = len(summary_rows)
    counts["mapped_events"] = mapped_events
    counts["trace_events"] = trace_metadata["trace_events"].get("row_count")
    counts["trace_segments"] = trace_metadata["trace_segments"].get("row_count")
    counts["trace_aggregate_bins"] = trace_metadata["trace_aggregate_bins"].get("row_count")
    counts["source_counts"] = dict(sorted(source_counts.items()))
    counts["type_counts"] = top_counts(dict(type_counts), limit=200)
    counts["shape_counts"] = top_counts(dict(shape_counts), limit=200)
    counts["date_precision_counts"] = dict(sorted(date_precision_counts.items()))
    counts["location_precision_counts"] = dict(sorted(location_precision_counts.items()))
    counts["coordinate_source_counts"] = dict(sorted(coordinate_source_counts.items()))
    counts["mapped_bounds"] = mapped_bounds.to_json()
    manifest["packed_points"] = {
        "schema_version": points_metadata.get("schema_version"),
        "row_count": points_metadata.get("row_count"),
        "bytes_per_row": points_metadata.get("bytes_per_row"),
    }
    manifest["packed_trace_segments"] = {
        "schema_version": trace_metadata["trace_segments"].get("schema_version"),
        "row_count": trace_metadata["trace_segments"].get("row_count"),
        "bytes_per_row": trace_metadata["trace_segments"].get("bytes_per_row"),
        "full_window_mode": trace_metadata["trace_segments"].get("render_plan", {}).get("full_window_mode"),
    }
    manifest["packed_trace_events"] = {
        "schema_version": trace_metadata["trace_events"].get("schema_version"),
        "row_count": trace_metadata["trace_events"].get("row_count"),
        "bytes_per_row": trace_metadata["trace_events"].get("bytes_per_row"),
        "row_order": "canonical_playback_order",
        "filtered_segment_rule": "filter rows first, then connect adjacent visible rows client-side",
    }
    manifest["packed_trace_aggregate_bins"] = {
        "schema_version": trace_metadata["trace_aggregate_bins"].get("schema_version"),
        "row_count": trace_metadata["trace_aggregate_bins"].get("row_count"),
        "bytes_per_row": trace_metadata["trace_aggregate_bins"].get("bytes_per_row"),
        "runtime_warning": trace_metadata["trace_aggregate_bins"].get("render_contract", {}).get(
            "runtime_warning",
            "Use for full-universe wide-window LOD only.",
        ),
    }
    manifest.setdefault("policy", {})["admin_coordinate_repair_sidecar"] = {
        "applied": True,
        "sidecar": str(sidecar_path),
        "patched_event_count": len(patched_events),
        "canonical_full_mutated": False,
    }
    _write_compact_json(manifest_path, manifest)
    return {"counts": counts}


def _write_artifact_size_report(output_dir: Path) -> dict[str, Any]:
    files = []
    total_bytes = 0
    for path in sorted(output_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.name in {"artifact_size_report.json", "compression_probe.json", "compression_report.json"}:
            continue
        if path.suffix == ".gz":
            continue
        size_bytes = path.stat().st_size
        total_bytes += size_bytes
        files.append(
            {
                "path": str(path.relative_to(output_dir)).replace("\\", "/"),
                "bytes": size_bytes,
                "mb": round(size_bytes / (1024 * 1024), 4),
            }
        )
    report = {
        "total_files": len(files),
        "total_bytes": total_bytes,
        "total_mb": round(total_bytes / (1024 * 1024), 2),
        "files": sorted(files, key=lambda item: (-item["bytes"], item["path"])),
    }
    write_json(output_dir / "artifact_size_report.json", report, indent=2)
    return report


def _write_compact_json(path: Path, payload: Any) -> None:
    ensure_parent_dir(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _finite_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _distance_degrees(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    return math.hypot(lat_a - lat_b, lon_a - lon_b)


def main() -> int:
    args = build_argument_parser().parse_args()
    report = apply_sidecar_to_canonical_web(
        artifact_dir=Path(args.artifact_dir),
        sidecar_path=Path(args.sidecar),
        report_output=Path(args.report_output),
        write_gzip=not args.no_gzip,
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
