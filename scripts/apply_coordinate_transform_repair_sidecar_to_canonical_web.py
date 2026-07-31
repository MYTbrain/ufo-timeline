"""Apply reviewed transform-evidence coordinate repairs to canonical web artifacts.

This script is intentionally separate from the admin-bound repair apply path.
Transform repairs are validated by old-coordinate/source guards plus transform
distance evidence; they do not require state/province boundary checks.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from parser.packed_points import export_packed_points
from parser.trace_segments import export_trace_artifacts
from parser.utils import ensure_parent_dir, write_json
from scripts.apply_coordinate_admin_matched_repair_sidecar_to_canonical_web import (
    _load_summary_rows,
    _refresh_manifest as _refresh_base_manifest,
    _write_artifact_size_report,
)
from scripts.build_canonical_web_artifacts import write_gzip_artifacts


DEFAULT_ARTIFACT_DIR = Path("data/canonical_web")
DEFAULT_SIDECAR = Path("data/reports/coordinate_transform_repair_sidecar_v109.json")
DEFAULT_REPORT = Path("data/reports/coordinate_transform_repair_canonical_web_apply_v109.json")


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


def apply_transform_sidecar_to_canonical_web(
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
    _preflight_patch_targets(
        artifact_dir=artifact_dir,
        patch_by_canonical_id=patch_by_canonical_id,
    )
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


def _preflight_patch_targets(
    *,
    artifact_dir: Path,
    patch_by_canonical_id: dict[str, dict[str, Any]],
) -> None:
    """Validate all event chunk and summary targets before writing any file."""

    found_chunk_ids: set[str] = set()
    event_id_to_patch: dict[int, dict[str, Any]] = {}
    for path in sorted((artifact_dir / "event_chunks").glob("*.json")):
        rows = _read_json(path)
        if not isinstance(rows, list):
            raise ValueError(f"Expected event chunk array: {path}")
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            canonical_id = str(row.get("canonical_event_id") or "")
            patch = patch_by_canonical_id.get(canonical_id)
            if patch is None:
                continue
            _validate_patch_target(row=row, patch=patch, context=f"preflight:{path.name}[{index}]")
            found_chunk_ids.add(canonical_id)
            event_id = row.get("event_id")
            if not isinstance(event_id, int):
                raise ValueError(f"preflight:{path.name}[{index}]: target row lacks integer event_id.")
            event_id_to_patch[event_id] = patch

    missing_chunk_ids = sorted(set(patch_by_canonical_id) - found_chunk_ids)
    if missing_chunk_ids:
        raise RuntimeError(f"Missing patch targets in event chunks: {missing_chunk_ids}")

    found_summary_ids: set[int] = set()
    for path in sorted((artifact_dir / "summary_shards").glob("*.json")):
        rows = _read_json(path)
        if not isinstance(rows, list):
            raise ValueError(f"Expected summary shard array: {path}")
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            event_id = row.get("event_id")
            patch = event_id_to_patch.get(event_id)
            if patch is None:
                continue
            _validate_patch_target(row=row, patch=patch, context=f"preflight:{path.name}[{index}]")
            found_summary_ids.add(event_id)

    missing_summary_ids = sorted(set(event_id_to_patch) - found_summary_ids)
    if missing_summary_ids:
        raise RuntimeError(f"Missing patch targets in summary shards: {missing_summary_ids}")


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
    old = patch.get("old") or {}
    expected_lat = _finite_float(old.get("lat"))
    expected_lon = _finite_float(old.get("lon"))
    current_lat = _finite_float(row.get("lat"))
    current_lon = _finite_float(row.get("lon"))
    if expected_lat is None or expected_lon is None or current_lat is None or current_lon is None:
        raise ValueError(f"{context}: target row is not currently mapped or patch old coordinate is invalid.")
    if abs(current_lat - expected_lat) > 1e-6 or abs(current_lon - expected_lon) > 1e-6:
        raise ValueError(f"{context}: current coordinate no longer matches sidecar old-coordinate guard.")

    expected_source = str(old.get("coordinate_source") or "")
    current_source = str(row.get("coordinate_source") or "")
    if expected_source and not _coordinate_source_guard_passes(expected_source, current_source):
        raise ValueError(f"{context}: current coordinate source no longer matches sidecar source guard.")

    new_fields = patch.get("set_fields", {})
    new_lat = _finite_float(new_fields.get("lat"))
    new_lon = _finite_float(new_fields.get("lon"))
    if new_lat is None or new_lon is None:
        raise ValueError(f"{context}: patch has no finite replacement coordinates.")
    if _distance_degrees(current_lat, current_lon, new_lat, new_lon) < 0.01:
        raise ValueError(f"{context}: replacement is too close to current coordinate to be a repair.")

    evidence = patch.get("transform_evidence") or {}
    original_distance = _finite_float(evidence.get("original_distance_km"))
    transformed_distance = _finite_float(evidence.get("transformed_distance_km"))
    improvement_ratio = _finite_float(evidence.get("distance_improvement_ratio"))
    if original_distance is None or transformed_distance is None or improvement_ratio is None:
        raise ValueError(f"{context}: patch lacks finite transform evidence.")
    if original_distance < 100 or transformed_distance > 50 or improvement_ratio < 3:
        raise ValueError(f"{context}: patch transform evidence failed safety thresholds.")


def _apply_patch_fields(row: dict[str, Any], patch: dict[str, Any]) -> None:
    for key, value in patch["set_fields"].items():
        row[key] = value
    row["has_coordinates"] = True


def _coordinate_source_guard_passes(expected_source: str, current_source: str) -> bool:
    if expected_source == current_source:
        return True
    source_coordinate_aliases = {"source_coordinates", "raw_latlong"}
    if expected_source in source_coordinate_aliases and current_source in source_coordinate_aliases:
        return True
    return False


def _row_coordinate_snapshot(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "lat": row.get("lat"),
        "lon": row.get("lon"),
        "coordinate_source": row.get("coordinate_source"),
        "location_precision": row.get("location_precision"),
    }


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
    existing_manifest = _read_json(manifest_path)
    existing_admin_policy = None
    existing_transform_history: list[dict[str, Any]] = []
    if isinstance(existing_manifest, dict):
        existing_policy = existing_manifest.get("policy", {})
        if isinstance(existing_policy, dict):
            existing_admin_policy = existing_policy.get("admin_coordinate_repair_sidecar")
            existing_transform_history = _transform_repair_history(existing_policy)

    result = _refresh_base_manifest(
        artifact_dir=artifact_dir,
        sidecar_path=sidecar_path,
        patched_events=patched_events,
        summary_rows=summary_rows,
        points_metadata=points_metadata,
        trace_metadata=trace_metadata,
    )
    manifest = _read_json(manifest_path)
    policy = manifest.setdefault("policy", {})
    if existing_admin_policy is None:
        policy.pop("admin_coordinate_repair_sidecar", None)
    else:
        policy["admin_coordinate_repair_sidecar"] = existing_admin_policy
    current_transform_policy = {
        "applied": True,
        "sidecar": str(sidecar_path),
        "patched_event_count": len(patched_events),
        "canonical_full_mutated": False,
    }
    transform_history = _merge_transform_repair_history(
        existing_transform_history,
        current_transform_policy,
    )
    policy["transform_coordinate_repair_sidecar"] = current_transform_policy
    policy["transform_coordinate_repair_sidecars"] = transform_history
    policy["transform_coordinate_repair_total_patched_event_count"] = sum(
        int(item.get("patched_event_count") or 0) for item in transform_history
    )
    _write_compact_json(manifest_path, manifest)
    return result


def _transform_repair_history(policy: dict[str, Any]) -> list[dict[str, Any]]:
    history = policy.get("transform_coordinate_repair_sidecars")
    if isinstance(history, list):
        return [dict(item) for item in history if isinstance(item, dict)]
    latest = policy.get("transform_coordinate_repair_sidecar")
    if isinstance(latest, dict) and latest.get("sidecar"):
        return [dict(latest)]
    return []


def _merge_transform_repair_history(
    existing_history: list[dict[str, Any]],
    current_policy: dict[str, Any],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen_sidecars: set[str] = set()
    for item in [*existing_history, current_policy]:
        sidecar = str(item.get("sidecar") or "")
        if not sidecar:
            continue
        normalized = dict(item)
        normalized["sidecar"] = sidecar
        normalized.setdefault("applied", True)
        normalized.setdefault("canonical_full_mutated", False)
        if sidecar in seen_sidecars:
            for index, existing in enumerate(merged):
                if existing.get("sidecar") == sidecar:
                    merged[index] = normalized
                    break
            continue
        seen_sidecars.add(sidecar)
        merged.append(normalized)
    return merged


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
    report = apply_transform_sidecar_to_canonical_web(
        artifact_dir=Path(args.artifact_dir),
        sidecar_path=Path(args.sidecar),
        report_output=Path(args.report_output),
        write_gzip=not args.no_gzip,
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
