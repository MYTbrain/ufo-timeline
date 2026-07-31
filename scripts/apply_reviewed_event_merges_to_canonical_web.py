"""Consolidate reviewed same-incident copies in canonical web artifacts.

This is intentionally a current-artifact repair. The authoritative canonical
full JSONL remains untouched. Every removed web event is preserved as a source
snapshot and as merged provenance on the surviving event.
"""

from __future__ import annotations

import argparse
from collections import Counter
import copy
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Iterable, Mapping

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
DEFAULT_SIDECAR = Path("data/reports/airship_wave_reviewed_event_merges_v148.json")
DEFAULT_REPORT = Path("data/reports/airship_wave_reviewed_event_merges_apply_v148.json")

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
SUMMARY_SYNC_FIELDS = (
    "date_raw",
    "sort_date_iso",
    "date_precision",
    "time_raw",
    "time_sort_kind",
    "time_sort_confidence",
    "playback_sort_confidence",
    "playback_sort_reason",
    "playback_sort_key",
    "location_raw",
    "source",
    "type",
    "coordinate_source",
    "location_precision",
    "lat",
    "lon",
    "has_coordinates",
    "shape_normalized",
    "visual_type_group",
    "craft_type_inferred",
    "craft_type_label",
    "craft_type_confidence",
    "craft_type_source",
    "same_day_match_strength",
)
MAPPING_FIELDS = (
    "location_raw",
    "lat",
    "lon",
    "has_coordinates",
    "coordinate_source",
    "location_precision",
    "city",
    "state_province",
    "country",
    "geocode_display_name",
)
CRAFT_FIELDS = (
    "type",
    "type_raw",
    "type_normalized",
    "shape_raw",
    "shape_normalized",
    "visual_type_group",
    "craft_type_inferred",
    "craft_type_label",
    "craft_type_confidence",
    "craft_type_source",
    "craft_type_reason",
    "same_day_match_strength",
)
REVIEWED_OVERRIDE_FIELDS = frozenset(CRAFT_FIELDS)


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


def apply_reviewed_event_merges(
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
    review_window = _load_review_window(sidecar)
    clusters = _load_clusters(sidecar)
    target_canonical_ids = {
        canonical_id
        for cluster in clusters
        for canonical_id in cluster["canonical_event_ids"]
    }

    manifest = _read_json(artifact_dir / "canonical_web_manifest.json")
    chunk_manifest = _read_json(artifact_dir / "event_chunk_manifest.json")
    summary_manifest = _read_json(artifact_dir / "summary_manifest.json")
    detail_payloads, detail_locations = _load_target_detail_chunks(
        artifact_dir=artifact_dir,
        canonical_ids=target_canonical_ids,
    )
    summary_payloads, summary_locations, summary_rows_before = _load_all_summary_rows(
        artifact_dir=artifact_dir,
        summary_manifest=summary_manifest,
    )
    _preflight_locations(
        target_canonical_ids=target_canonical_ids,
        detail_locations=detail_locations,
        summary_locations=summary_locations,
        manifest=manifest,
        summary_rows=summary_rows_before,
        review_window=review_window,
    )

    removed_event_ids: set[int] = set()
    affected_chunk_paths: set[str] = set()
    affected_summary_paths: set[str] = set()
    merged_cluster_reports: list[dict[str, Any]] = []

    for cluster in clusters:
        cluster_report = _merge_cluster(
            cluster=cluster,
            detail_locations=detail_locations,
            summary_locations=summary_locations,
        )
        removed_event_ids.update(cluster_report["removed_event_ids"])
        affected_chunk_paths.update(cluster_report["affected_detail_paths"])
        affected_summary_paths.update(cluster_report["affected_summary_paths"])
        merged_cluster_reports.append(cluster_report)

    detail_index_by_event_id: dict[int, int] = {}
    for relative_path in sorted(affected_chunk_paths):
        rows = detail_payloads[relative_path]
        retained_rows = [
            row for row in rows if _required_int(row.get("event_id"), field="event_id")
            not in removed_event_ids
        ]
        for detail_index, row in enumerate(retained_rows):
            row["detail_index"] = detail_index
            detail_index_by_event_id[_required_int(row.get("event_id"), field="event_id")] = (
                detail_index
            )
        detail_payloads[relative_path] = retained_rows

    for relative_path, rows in summary_payloads.items():
        retained_rows = [
            row for row in rows if _required_int(row.get("event_id"), field="event_id")
            not in removed_event_ids
        ]
        changed = len(retained_rows) != len(rows)
        for row in retained_rows:
            event_id = _required_int(row.get("event_id"), field="event_id")
            if event_id in detail_index_by_event_id:
                row["detail_index"] = detail_index_by_event_id[event_id]
                changed = True
        if changed:
            affected_summary_paths.add(relative_path)
        summary_payloads[relative_path] = retained_rows

    summary_rows = [
        row
        for entry in summary_manifest
        for row in summary_payloads[_summary_relative_path(entry)]
    ]
    events_before = len(summary_rows_before)
    events_after = len(summary_rows)
    expected_reduction = sum(len(cluster["canonical_event_ids"]) - 1 for cluster in clusters)
    if events_before - events_after != expected_reduction:
        raise RuntimeError(
            "Reviewed merge reduction mismatch: "
            f"{events_before} -> {events_after}, expected={expected_reduction}"
        )

    refreshed_chunk_manifest = _refresh_partition_manifest(
        manifest_rows=chunk_manifest,
        payloads=detail_payloads,
        relative_path_resolver=_chunk_relative_path,
    )
    refreshed_summary_manifest = _refresh_partition_manifest(
        manifest_rows=summary_manifest,
        payloads=summary_payloads,
        relative_path_resolver=_summary_relative_path,
    )

    staged_raw_paths: list[str] = []
    compression_summary: dict[str, Any] | None = None
    with tempfile.TemporaryDirectory(
        prefix=".reviewed_event_merges_",
        dir=artifact_dir.parent,
    ) as temporary_dir:
        stage_root = Path(temporary_dir)

        for relative_path in sorted(affected_chunk_paths):
            _write_compact_json(stage_root / relative_path, detail_payloads[relative_path])
            staged_raw_paths.append(relative_path)
        for relative_path in sorted(affected_summary_paths):
            _write_compact_json(stage_root / relative_path, summary_payloads[relative_path])
            staged_raw_paths.append(relative_path)

        _write_pretty_json(stage_root / "event_chunk_manifest.json", refreshed_chunk_manifest)
        _write_pretty_json(stage_root / "summary_manifest.json", refreshed_summary_manifest)
        staged_raw_paths.extend(["event_chunk_manifest.json", "summary_manifest.json"])

        packed_stage = stage_root / "_packed"
        points_metadata = export_packed_points(
            summary_rows,
            packed_stage,
            chunk_manifest=refreshed_chunk_manifest,
        )
        trace_metadata = export_trace_artifacts(summary_rows, packed_stage)
        for name in PACKED_ARTIFACT_PATHS:
            staged_path = stage_root / name
            ensure_parent_dir(staged_path)
            os.replace(packed_stage / name, staged_path)
            staged_raw_paths.append(name)
        packed_stage.rmdir()

        refreshed_manifest = _refresh_manifest(
            manifest=manifest,
            sidecar_path=sidecar_path,
            summary_rows=summary_rows,
            chunk_manifest=refreshed_chunk_manifest,
            summary_manifest=refreshed_summary_manifest,
            points_metadata=points_metadata,
            trace_metadata=trace_metadata,
            cluster_count=len(clusters),
        removed_event_count=len(removed_event_ids),
        review_window=review_window,
        )
        _write_pretty_json(stage_root / "canonical_web_manifest.json", refreshed_manifest)
        staged_raw_paths.append("canonical_web_manifest.json")

        size_report = _build_artifact_size_report(
            artifact_dir=artifact_dir,
            stage_root=stage_root,
        )
        _write_pretty_json(stage_root / "artifact_size_report.json", size_report)
        staged_raw_paths.append("artifact_size_report.json")

        gzip_relative_paths: list[str] = []
        if write_gzip:
            compression_report = _refresh_changed_gzip_artifacts(
                artifact_dir=artifact_dir,
                stage_root=stage_root,
                changed_raw_paths=sorted(
                    set(staged_raw_paths)
                    - {"artifact_size_report.json", "compression_report.json"}
                ),
            )
            _write_pretty_json(stage_root / "compression_report.json", compression_report)
            staged_raw_paths.append("compression_report.json")
            gzip_relative_paths = [
                f"{relative_path}.gz"
                for relative_path in sorted(
                    set(staged_raw_paths)
                    - {"artifact_size_report.json", "compression_report.json"}
                )
            ]
            compression_summary = {
                "total_files": compression_report["total_files"],
                "total_gzip_bytes": compression_report["total_gzip_bytes"],
                "total_gzip_mb": compression_report["total_gzip_mb"],
                "refreshed_file_count": len(gzip_relative_paths),
            }

        commit_paths = sorted(set(staged_raw_paths + gzip_relative_paths))
        _commit_staged_files(
            artifact_dir=artifact_dir,
            stage_root=stage_root,
            relative_paths=commit_paths,
        )

    changed_hashes = {
        relative_path: _sha256(artifact_dir / relative_path)
        for relative_path in sorted(set(staged_raw_paths))
    }
    report = {
        "schema_version": 1,
        "mode": "canonical_web_reviewed_same_incident_merge",
        "policy": "reviewed_same_incident_cross_source_merge",
        "canonical_full_mutated": False,
        "canonical_web_mutated": True,
        "removed_events_preserved_as_keeper_snapshots": True,
        "source_provenance_preserved": True,
        "inputs": {
            "artifact_dir": str(artifact_dir),
            "sidecar": str(sidecar_path),
        },
        "outputs": {"report": str(report_output)},
        "window": sidecar.get("window"),
        "reviewed_cluster_count": len(clusters),
        "merged_member_event_count": sum(
            len(cluster["canonical_event_ids"]) for cluster in clusters
        ),
        "removed_duplicate_event_count": len(removed_event_ids),
        "events_before_count": events_before,
        "events_after_count": events_after,
        "mapped_after_count": sum(1 for row in summary_rows if _is_mapped(row)),
        "points_row_count": points_metadata["row_count"],
        "trace_event_count": trace_metadata["trace_events"]["row_count"],
        "trace_segment_count": trace_metadata["trace_segments"]["row_count"],
        "trace_aggregate_bin_count": trace_metadata["trace_aggregate_bins"]["row_count"],
        "clusters": merged_cluster_reports,
        "changed_raw_files": sorted(set(staged_raw_paths)),
        "changed_raw_file_sha256": changed_hashes,
        "compression": compression_summary,
    }
    write_json(report_output, report, indent=2)
    return report


def _load_clusters(sidecar: Any) -> list[dict[str, Any]]:
    if not isinstance(sidecar, dict):
        raise ValueError("Sidecar must be a JSON object.")
    if sidecar.get("policy") != "reviewed_same_incident_cross_source_merge":
        raise ValueError("Sidecar policy is not the reviewed same-incident merge policy.")
    _load_review_window(sidecar)
    clusters = sidecar.get("clusters")
    if not isinstance(clusters, list) or not clusters:
        raise ValueError("Sidecar must contain a non-empty clusters list.")

    seen_cluster_ids: set[str] = set()
    seen_canonical_ids: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for value in clusters:
        if not isinstance(value, dict):
            raise ValueError("Each reviewed cluster must be an object.")
        cluster_id = str(value.get("cluster_id") or "").strip()
        preferred = str(value.get("preferred_canonical_event_id") or "").strip()
        canonical_ids = [
            str(item).strip()
            for item in value.get("canonical_event_ids", [])
            if str(item).strip()
        ]
        match_basis = [
            str(item).strip()
            for item in value.get("match_basis", [])
            if str(item).strip()
        ]
        field_overrides = value.get("field_overrides") or {}
        if not cluster_id or cluster_id in seen_cluster_ids:
            raise ValueError(f"Missing or duplicate cluster_id: {cluster_id!r}")
        if len(canonical_ids) < 2 or len(set(canonical_ids)) != len(canonical_ids):
            raise ValueError(f"{cluster_id}: canonical_event_ids must be unique and contain 2+ IDs.")
        if preferred not in canonical_ids:
            raise ValueError(f"{cluster_id}: preferred_canonical_event_id is not a member.")
        if not match_basis:
            raise ValueError(f"{cluster_id}: match_basis is required.")
        if not isinstance(field_overrides, dict):
            raise ValueError(f"{cluster_id}: field_overrides must be an object.")
        unsupported_overrides = set(field_overrides).difference(REVIEWED_OVERRIDE_FIELDS)
        if unsupported_overrides:
            raise ValueError(
                f"{cluster_id}: unsupported field_overrides: {sorted(unsupported_overrides)}"
            )
        if any(value is None for value in field_overrides.values()):
            raise ValueError(f"{cluster_id}: field_overrides cannot contain null values.")
        overlap = seen_canonical_ids.intersection(canonical_ids)
        if overlap:
            raise ValueError(f"{cluster_id}: canonical IDs overlap another cluster: {sorted(overlap)}")
        seen_cluster_ids.add(cluster_id)
        seen_canonical_ids.update(canonical_ids)
        normalized.append(
            {
                "cluster_id": cluster_id,
                "preferred_canonical_event_id": preferred,
                "canonical_event_ids": canonical_ids,
                "match_basis": match_basis,
                "date_review": value.get("date_review"),
                "field_overrides": copy.deepcopy(field_overrides),
            }
        )
    return normalized


def _load_review_window(sidecar: Mapping[str, Any]) -> dict[str, str]:
    window = sidecar.get("window")
    if not isinstance(window, dict):
        raise ValueError("Sidecar must declare a reviewed date window.")
    start = str(window.get("start") or "").strip()
    end = str(window.get("end") or "").strip()
    iso_day_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    if not iso_day_pattern.fullmatch(start) or not iso_day_pattern.fullmatch(end):
        raise ValueError("Sidecar review window boundaries must use YYYY-MM-DD.")
    if start > end:
        raise ValueError("Sidecar review window start must be on or before its end.")
    return {"start": start, "end": end}


def _load_target_detail_chunks(
    *,
    artifact_dir: Path,
    canonical_ids: set[str],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    pattern = re.compile(
        rb'"canonical_event_id":"('
        + b"|".join(re.escape(item.encode("utf-8")) for item in sorted(canonical_ids))
        + rb')"'
    )
    payloads: dict[str, list[dict[str, Any]]] = {}
    locations: dict[str, dict[str, Any]] = {}
    for path in sorted((artifact_dir / "event_chunks").glob("chunk_*.json")):
        raw = path.read_bytes()
        if not pattern.search(raw):
            continue
        relative_path = str(path.relative_to(artifact_dir)).replace("\\", "/")
        rows = json.loads(raw)
        payloads[relative_path] = rows
        for index, row in enumerate(rows):
            canonical_id = str(row.get("canonical_event_id") or "")
            if canonical_id not in canonical_ids:
                continue
            if canonical_id in locations:
                raise ValueError(f"Duplicate detail canonical_event_id: {canonical_id}")
            locations[canonical_id] = {
                "path": relative_path,
                "index": index,
                "row": row,
            }
    return payloads, locations


def _load_all_summary_rows(
    *,
    artifact_dir: Path,
    summary_manifest: list[dict[str, Any]],
) -> tuple[
    dict[str, list[dict[str, Any]]],
    dict[int, dict[str, Any]],
    list[dict[str, Any]],
]:
    payloads: dict[str, list[dict[str, Any]]] = {}
    locations: dict[int, dict[str, Any]] = {}
    flat_rows: list[dict[str, Any]] = []
    for entry in summary_manifest:
        relative_path = _summary_relative_path(entry)
        rows = _read_json(artifact_dir / relative_path)
        if not isinstance(rows, list):
            raise ValueError(f"Summary shard is not a list: {relative_path}")
        payloads[relative_path] = rows
        for index, row in enumerate(rows):
            event_id = _required_int(row.get("event_id"), field=f"{relative_path}.event_id")
            if event_id in locations:
                raise ValueError(f"Duplicate summary event_id: {event_id}")
            locations[event_id] = {
                "path": relative_path,
                "index": index,
                "row": row,
            }
            flat_rows.append(row)
    return payloads, locations, flat_rows


def _preflight_locations(
    *,
    target_canonical_ids: set[str],
    detail_locations: Mapping[str, Mapping[str, Any]],
    summary_locations: Mapping[int, Mapping[str, Any]],
    manifest: Mapping[str, Any],
    summary_rows: list[dict[str, Any]],
    review_window: Mapping[str, str],
) -> None:
    missing = target_canonical_ids.difference(detail_locations)
    if missing:
        raise ValueError(f"Reviewed canonical_event_ids are missing from detail artifacts: {sorted(missing)}")
    missing_summary: list[int] = []
    for canonical_id in sorted(target_canonical_ids):
        row = detail_locations[canonical_id]["row"]
        event_id = _required_int(row.get("event_id"), field=f"{canonical_id}.event_id")
        if event_id not in summary_locations:
            missing_summary.append(event_id)
        sort_date = str(row.get("sort_date_iso") or "")
        if not review_window["start"] <= sort_date <= review_window["end"]:
            raise ValueError(f"{canonical_id}: sort_date_iso is outside the reviewed window.")
    if missing_summary:
        raise ValueError(f"Reviewed detail events are missing summary rows: {missing_summary}")
    expected_count = int(manifest.get("counts", {}).get("events") or len(summary_rows))
    if len(summary_rows) != expected_count:
        raise RuntimeError(
            f"Summary row count is stale before merge: {len(summary_rows)} != {expected_count}"
        )


def _merge_cluster(
    *,
    cluster: Mapping[str, Any],
    detail_locations: Mapping[str, Mapping[str, Any]],
    summary_locations: Mapping[int, Mapping[str, Any]],
) -> dict[str, Any]:
    canonical_ids = list(cluster["canonical_event_ids"])
    preferred_id = str(cluster["preferred_canonical_event_id"])
    detail_rows = [detail_locations[canonical_id]["row"] for canonical_id in canonical_ids]
    summary_rows = [
        summary_locations[_required_int(row.get("event_id"), field="event_id")]["row"]
        for row in detail_rows
    ]
    keeper_detail = detail_locations[preferred_id]["row"]
    keeper_event_id = _required_int(keeper_detail.get("event_id"), field="keeper.event_id")
    keeper_summary = summary_locations[keeper_event_id]["row"]

    best_mapping = max(detail_rows, key=_mapping_score)
    best_description = max(detail_rows, key=_description_score)
    best_craft = max(detail_rows, key=_craft_score)
    original_keeper = copy.deepcopy(keeper_detail)

    if _mapping_score(best_mapping) > _mapping_score(keeper_detail):
        _copy_present_fields(best_mapping, keeper_detail, MAPPING_FIELDS)
    if _description_score(best_description) > _description_score(keeper_detail):
        keeper_detail["description"] = best_description.get("description")
        keeper_detail["summary"] = best_description.get("summary")
        keeper_detail["description_short"] = _snippet(
            best_description.get("description") or best_description.get("summary"),
            limit=360,
        )
    if _craft_score(best_craft) > _craft_score(keeper_detail):
        _copy_present_fields(best_craft, keeper_detail, CRAFT_FIELDS)
    field_overrides = dict(cluster.get("field_overrides") or {})
    if field_overrides:
        _copy_present_fields(field_overrides, keeper_detail, REVIEWED_OVERRIDE_FIELDS)
    if not keeper_detail.get("time_raw"):
        timed = max(detail_rows, key=lambda row: bool(row.get("time_raw")))
        if timed.get("time_raw"):
            keeper_detail["time_raw"] = timed.get("time_raw")

    keeper_detail["canonical_input_ids"] = _unique_values(
        item
        for row in detail_rows
        for item in _list_value(row.get("canonical_input_ids"))
    )
    keeper_detail["source_provenance"] = _unique_mappings(
        item
        for row in detail_rows
        for item in _list_value(row.get("source_provenance"))
        if isinstance(item, dict)
    )
    keeper_detail["duplicate_record_count"] = sum(
        max(1, int(row.get("duplicate_record_count") or 1)) for row in detail_rows
    )
    keeper_detail["source_provenance_count"] = max(
        len(keeper_detail["canonical_input_ids"]),
        len(keeper_detail["source_provenance"]),
    )
    keeper_detail["dedupe_strategy"] = "reviewed_same_incident_cross_source_merge"
    keeper_detail["links"] = _unique_values(
        item for row in detail_rows for item in _list_value(row.get("links"))
    )
    keeper_detail["references"] = _unique_values(
        item for row in detail_rows for item in _list_value(row.get("references"))
    )

    member_snapshots = [_member_snapshot(row) for row in detail_rows]
    removed_detail_rows = [
        row for row in detail_rows if row is not keeper_detail
    ]
    removed_event_ids = [
        _required_int(row.get("event_id"), field="removed.event_id")
        for row in removed_detail_rows
    ]
    keeper_detail["reviewed_duplicate_merge"] = {
        "schema_version": 1,
        "policy": "reviewed_same_incident_cross_source_merge",
        "cluster_id": cluster["cluster_id"],
        "match_basis": list(cluster["match_basis"]),
        "date_review": cluster.get("date_review"),
        "preferred_canonical_event_id": preferred_id,
        "merged_canonical_event_ids": canonical_ids,
        "removed_event_ids": removed_event_ids,
        "preserved_source_record_count": keeper_detail["duplicate_record_count"],
        "mapping_source_canonical_event_id": best_mapping.get("canonical_event_id"),
        "description_source_canonical_event_id": best_description.get("canonical_event_id"),
        "craft_source_canonical_event_id": best_craft.get("canonical_event_id"),
        "original_keeper_snapshot": _member_snapshot(original_keeper),
        "member_snapshots": member_snapshots,
        "field_overrides": copy.deepcopy(field_overrides),
    }
    keeper_detail["raw_event_block"] = _append_merge_note(
        keeper_detail.get("raw_event_block"),
        cluster_id=str(cluster["cluster_id"]),
        merged_event_count=len(detail_rows),
        source_record_count=keeper_detail["duplicate_record_count"],
        member_snapshots=member_snapshots,
    )

    for field in SUMMARY_SYNC_FIELDS:
        if field in keeper_detail:
            keeper_summary[field] = keeper_detail.get(field)

    return {
        "cluster_id": cluster["cluster_id"],
        "preferred_canonical_event_id": preferred_id,
        "keeper_event_id": keeper_event_id,
        "member_canonical_event_ids": canonical_ids,
        "removed_event_ids": removed_event_ids,
        "source_record_count": keeper_detail["duplicate_record_count"],
        "date_values": sorted(
            {
                str(row.get("sort_date_iso"))
                for row in detail_rows
                if row.get("sort_date_iso")
            }
        ),
        "mapping_source_canonical_event_id": best_mapping.get("canonical_event_id"),
        "description_source_canonical_event_id": best_description.get("canonical_event_id"),
        "field_overrides": copy.deepcopy(field_overrides),
        "affected_detail_paths": sorted(
            {str(detail_locations[canonical_id]["path"]) for canonical_id in canonical_ids}
        ),
        "affected_summary_paths": sorted(
            {
                str(
                    summary_locations[
                        _required_int(
                            detail_locations[canonical_id]["row"].get("event_id"),
                            field="event_id",
                        )
                    ]["path"]
                )
                for canonical_id in canonical_ids
            }
        ),
    }


def _member_snapshot(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "canonical_event_id": row.get("canonical_event_id"),
        "event_id": row.get("event_id"),
        "source": row.get("source"),
        "source_file": row.get("source_file"),
        "source_id": row.get("source_id"),
        "date_raw": row.get("date_raw"),
        "sort_date_iso": row.get("sort_date_iso"),
        "date_precision": row.get("date_precision"),
        "time_raw": row.get("time_raw"),
        "location_raw": row.get("location_raw"),
        "lat": row.get("lat"),
        "lon": row.get("lon"),
        "coordinate_source": row.get("coordinate_source"),
        "location_precision": row.get("location_precision"),
        "type": row.get("type"),
        "shape_normalized": row.get("shape_normalized"),
        "description": row.get("description"),
        "links": row.get("links"),
        "references": row.get("references"),
        "canonical_input_ids": row.get("canonical_input_ids"),
        "source_provenance": row.get("source_provenance"),
        "duplicate_record_count": row.get("duplicate_record_count"),
        "dedupe_strategy": row.get("dedupe_strategy"),
    }


def _mapping_score(row: Mapping[str, Any]) -> tuple[int, int, int, str]:
    precision_rank = {
        "exact_coords": 6,
        "mapped": 5,
        "city": 4,
        "state": 3,
        "province": 3,
        "country": 2,
        "unknown": 0,
    }
    mapped = int(_is_mapped(row))
    location_text = str(row.get("location_raw") or "")
    return (
        mapped,
        precision_rank.get(str(row.get("location_precision") or "unknown"), 1),
        len(location_text),
        str(row.get("canonical_event_id") or ""),
    )


def _description_score(row: Mapping[str, Any]) -> tuple[int, int, str]:
    description = str(row.get("description") or row.get("summary") or "").strip()
    return (
        int(bool(description)),
        len(description),
        str(row.get("canonical_event_id") or ""),
    )


def _craft_score(row: Mapping[str, Any]) -> tuple[int, int, int, str]:
    confidence_rank = {"high": 3, "medium": 2, "low": 1, "none": 0}
    craft = str(row.get("craft_type_inferred") or "unknown")
    event_type = str(row.get("type") or "Unknown")
    return (
        confidence_rank.get(str(row.get("craft_type_confidence") or "none"), 0),
        int(craft != "unknown"),
        int(event_type.lower() != "unknown"),
        str(row.get("canonical_event_id") or ""),
    )


def _copy_present_fields(
    source: Mapping[str, Any],
    destination: dict[str, Any],
    fields: Iterable[str],
) -> None:
    for field in fields:
        if field in source:
            destination[field] = source.get(field)


def _refresh_partition_manifest(
    *,
    manifest_rows: list[dict[str, Any]],
    payloads: Mapping[str, list[dict[str, Any]]],
    relative_path_resolver: Any,
) -> list[dict[str, Any]]:
    refreshed = copy.deepcopy(manifest_rows)
    for entry in refreshed:
        relative_path = relative_path_resolver(entry)
        rows = payloads.get(relative_path)
        if rows is None:
            continue
        entry["event_count"] = len(rows)
        entry["start_event_id"] = rows[0].get("event_id") if rows else None
        entry["end_event_id"] = rows[-1].get("event_id") if rows else None
    return refreshed


def _refresh_manifest(
    *,
    manifest: Mapping[str, Any],
    sidecar_path: Path,
    summary_rows: list[dict[str, Any]],
    chunk_manifest: list[dict[str, Any]],
    summary_manifest: list[dict[str, Any]],
    points_metadata: Mapping[str, Any],
    trace_metadata: Mapping[str, Any],
    cluster_count: int,
    removed_event_count: int,
    review_window: Mapping[str, str],
) -> dict[str, Any]:
    refreshed = copy.deepcopy(manifest)
    mapped_bounds = MappedBounds()
    counters = {
        "source_counts": Counter(),
        "type_counts": Counter(),
        "shape_counts": Counter(),
        "craft_type_counts": Counter(),
        "craft_type_confidence_counts": Counter(),
        "craft_type_source_counts": Counter(),
        "same_day_match_strength_counts": Counter(),
        "date_precision_counts": Counter(),
        "location_precision_counts": Counter(),
        "coordinate_source_counts": Counter(),
    }
    mapped_count = 0
    for row in summary_rows:
        counters["source_counts"][str(row.get("source") or "unknown")] += 1
        counters["type_counts"][str(row.get("type") or "Unknown")] += 1
        counters["shape_counts"][str(row.get("shape_normalized") or "Unknown")] += 1
        counters["craft_type_counts"][str(row.get("craft_type_inferred") or "unknown")] += 1
        counters["craft_type_confidence_counts"][
            str(row.get("craft_type_confidence") or "none")
        ] += 1
        counters["craft_type_source_counts"][str(row.get("craft_type_source") or "none")] += 1
        counters["same_day_match_strength_counts"][
            str(row.get("same_day_match_strength") or "none")
        ] += 1
        counters["date_precision_counts"][str(row.get("date_precision") or "unknown")] += 1
        counters["location_precision_counts"][
            str(row.get("location_precision") or "unknown")
        ] += 1
        counters["coordinate_source_counts"][
            str(row.get("coordinate_source") or "unknown")
        ] += 1
        if _is_mapped(row):
            mapped_count += 1
            mapped_bounds.add(float(row["lat"]), float(row["lon"]))

    trace_events = trace_metadata["trace_events"]
    trace_segments = trace_metadata["trace_segments"]
    trace_aggregate_bins = trace_metadata["trace_aggregate_bins"]
    counts = refreshed.setdefault("counts", {})
    counts.update(
        {
            "events": len(summary_rows),
            "mapped_events": mapped_count,
            "trace_events": trace_events.get("row_count"),
            "trace_segments": trace_segments.get("row_count"),
            "trace_aggregate_bins": trace_aggregate_bins.get("row_count"),
            "event_chunks": len(chunk_manifest),
            "summary_shards": len(summary_manifest),
            "mapped_bounds": mapped_bounds.to_json(),
        }
    )
    for key, counter in counters.items():
        counts[key] = dict(sorted(counter.items(), key=lambda item: (-item[1], item[0])))

    refreshed["packed_points"] = {
        "schema_version": points_metadata.get("schema_version"),
        "row_count": points_metadata.get("row_count"),
        "bytes_per_row": points_metadata.get("bytes_per_row"),
    }
    refreshed["packed_trace_segments"] = {
        "schema_version": trace_segments.get("schema_version"),
        "row_count": trace_segments.get("row_count"),
        "bytes_per_row": trace_segments.get("bytes_per_row"),
        "full_window_mode": trace_segments.get("render_plan", {}).get("full_window_mode"),
    }
    refreshed["packed_trace_events"] = {
        "schema_version": trace_events.get("schema_version"),
        "row_count": trace_events.get("row_count"),
        "bytes_per_row": trace_events.get("bytes_per_row"),
        "row_order": trace_events.get("render_contract", {}).get("row_order"),
        "filtered_segment_rule": trace_events.get("render_contract", {}).get(
            "filtered_segment_rule"
        ),
    }
    refreshed["packed_trace_aggregate_bins"] = {
        "schema_version": trace_aggregate_bins.get("schema_version"),
        "row_count": trace_aggregate_bins.get("row_count"),
        "bytes_per_row": trace_aggregate_bins.get("bytes_per_row"),
        "runtime_warning": trace_aggregate_bins.get("render_contract", {}).get(
            "runtime_warning"
        ),
    }
    policy = refreshed.setdefault("policy", {})
    run_record = {
        "applied": True,
        "sidecar": str(sidecar_path),
        "policy": "reviewed_same_incident_cross_source_merge",
        "window": dict(review_window),
        "reviewed_cluster_count": cluster_count,
        "removed_duplicate_event_count": removed_event_count,
        "removed_events_preserved_as_keeper_snapshots": True,
        "source_provenance_preserved": True,
        "canonical_full_mutated": False,
    }
    history = copy.deepcopy(policy.get("reviewed_event_merge_runs") or [])
    previous = copy.deepcopy(policy.get("reviewed_event_merges"))
    if previous and not history:
        history.append(previous)
    run_identity = (
        str(run_record["sidecar"]),
        run_record["window"]["start"],
        run_record["window"]["end"],
    )
    history = [
        entry
        for entry in history
        if (
            str(entry.get("sidecar")),
            str((entry.get("window") or {}).get("start")),
            str((entry.get("window") or {}).get("end")),
        )
        != run_identity
    ]
    history.append(copy.deepcopy(run_record))
    policy["reviewed_event_merge_runs"] = history
    policy["reviewed_event_merges"] = run_record
    return refreshed


def _append_merge_note(
    raw_event_block: Any,
    *,
    cluster_id: str,
    merged_event_count: int,
    source_record_count: int,
    member_snapshots: list[dict[str, Any]],
) -> str:
    original = str(raw_event_block or "").strip()
    source_labels = _unique_values(
        f"{item.get('source') or 'unknown'}:{item.get('source_id') or 'unknown'}"
        for item in member_snapshots
    )
    note = "\n".join(
        [
            "Reviewed duplicate consolidation:",
            f"Cluster: {cluster_id}",
            f"Normalized event copies consolidated: {merged_event_count}",
            f"Preserved source records: {source_record_count}",
            f"Member sources: {' | '.join(source_labels)}",
            "All member snapshots and provenance remain in reviewed_duplicate_merge.",
        ]
    )
    return "\n\n".join(part for part in (original, note) if part)


def _summary_relative_path(entry: Mapping[str, Any]) -> str:
    file_name = str(entry.get("file") or "")
    relative_path = f"summary_shards/{file_name}"
    if not SUMMARY_SHARD_PATTERN.fullmatch(relative_path):
        raise ValueError(f"Invalid summary manifest file: {file_name!r}")
    return relative_path


def _chunk_relative_path(entry: Mapping[str, Any]) -> str:
    file_name = str(entry.get("file") or "")
    relative_path = f"event_chunks/{file_name}"
    if not EVENT_CHUNK_PATTERN.fullmatch(relative_path):
        raise ValueError(f"Invalid chunk manifest file: {file_name!r}")
    return relative_path


def _list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _unique_values(values: Iterable[Any]) -> list[Any]:
    output: list[Any] = []
    seen: set[str] = set()
    for value in values:
        if value in (None, ""):
            continue
        key = json.dumps(value, ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        output.append(value)
    return output


def _unique_mappings(values: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [dict(value) for value in _unique_values(values)]


def _snippet(value: Any, *, limit: int) -> str | None:
    text = " ".join(str(value or "").split()).strip()
    if not text:
        return None
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)].rstrip() + "…"


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
        current = artifact_dir / relative_path
        staged = stage_root / relative_path
        effective = staged if staged.exists() else current
        if effective.suffix == ".gz":
            continue
        if effective.name in {
            "artifact_size_report.json",
            "compression_probe.json",
            "compression_report.json",
        }:
            continue
        size_bytes = effective.stat().st_size
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
    report = _read_json(artifact_dir / "compression_report.json")
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


def main() -> int:
    args = build_argument_parser().parse_args()
    report = apply_reviewed_event_merges(
        artifact_dir=args.artifact_dir,
        sidecar_path=args.sidecar,
        report_output=args.report_output,
        write_gzip=not args.no_gzip,
    )
    print(
        json.dumps(
            {
                "reviewed_cluster_count": report["reviewed_cluster_count"],
                "removed_duplicate_event_count": report["removed_duplicate_event_count"],
                "events_after_count": report["events_after_count"],
                "mapped_after_count": report["mapped_after_count"],
                "report": report["outputs"]["report"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
