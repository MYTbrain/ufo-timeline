from __future__ import annotations

import json
from pathlib import Path

from scripts.apply_coordinate_admin_matched_repair_sidecar_to_canonical_web import (
    apply_sidecar_to_canonical_web,
)


def test_apply_sidecar_to_canonical_web_patches_json_and_packed_artifacts(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "canonical_web"
    (artifact_dir / "event_chunks").mkdir(parents=True)
    (artifact_dir / "summary_shards").mkdir(parents=True)
    _write_json(
        artifact_dir / "event_chunk_manifest.json",
        [{"id": "chunk_000000", "file": "chunk_000000.json", "event_count": 2}],
    )
    _write_json(
        artifact_dir / "summary_manifest.json",
        [{"id": "summary_000000", "file": "summary_000000.json", "event_count": 2}],
    )
    rows = [
        {
            "event_id": 101,
            "canonical_event_id": "evt_patch",
            "chunk_id": "chunk_000000",
            "detail_index": 0,
            "date_raw": "1976-06-14",
            "date_iso": "1976-06-14",
            "sort_date_iso": "1976-06-14",
            "date_precision": "exact_day",
            "location_raw": "ENGADINE, NSW, AU",
            "source": "ufocat",
            "type": "Unknown",
            "shape_normalized": "Unknown",
            "visual_type_group": "Other / unknown",
            "coordinate_source": "raw_latlong",
            "location_precision": "exact_coords",
            "lat": -34.75,
            "lon": 138.41,
            "has_coordinates": True,
        },
        {
            "event_id": 102,
            "canonical_event_id": "evt_keep",
            "chunk_id": "chunk_000000",
            "detail_index": 1,
            "date_raw": "1976-06-15",
            "date_iso": "1976-06-15",
            "sort_date_iso": "1976-06-15",
            "date_precision": "exact_day",
            "location_raw": "SYDNEY, NSW, AU",
            "source": "ufocat",
            "type": "Light",
            "shape_normalized": "Light",
            "visual_type_group": "UFO/UAP sighting",
            "coordinate_source": "geocoded",
            "location_precision": "city",
            "lat": -33.8688,
            "lon": 151.2093,
            "has_coordinates": True,
        },
    ]
    _write_json(artifact_dir / "event_chunks" / "chunk_000000.json", rows)
    _write_json(artifact_dir / "summary_shards" / "summary_000000.json", rows)
    _write_json(
        artifact_dir / "canonical_web_manifest.json",
        {
            "schema_version": 1,
            "source": {"input_path": "fixture"},
            "artifacts": {
                "points": "points.bin",
                "points_metadata": "points_meta.json",
                "event_chunk_manifest": "event_chunk_manifest.json",
                "event_chunks_dir": "event_chunks",
                "summary_manifest": "summary_manifest.json",
                "summary_shards_dir": "summary_shards",
                "trace_event_index": "trace_event_index.bin",
                "trace_event_index_metadata": "trace_event_index_meta.json",
                "trace_segments": "trace_segments.bin",
                "trace_segments_metadata": "trace_segments_meta.json",
                "trace_aggregate_bins": "trace_aggregate_bins.bin",
                "trace_aggregate_bins_metadata": "trace_aggregate_bins_meta.json",
            },
            "counts": {},
            "policy": {},
        },
    )
    sidecar = tmp_path / "sidecar.json"
    _write_json(
        sidecar,
        {
            "schema_version": 1,
            "proposed_patches": [
                {
                    "canonical_event_id": "evt_patch",
                    "country": "Australia",
                    "declared_admin": "02",
                    "set_fields": {
                        "lat": -34.06564,
                        "lon": 151.01266,
                        "coordinate_source": "geocoded",
                        "location_precision": "city",
                    },
                }
            ],
        },
    )

    report = apply_sidecar_to_canonical_web(
        artifact_dir=artifact_dir,
        sidecar_path=sidecar,
        report_output=tmp_path / "report.json",
        write_gzip=False,
    )

    chunk_rows = json.loads((artifact_dir / "event_chunks" / "chunk_000000.json").read_text())
    summary_rows = json.loads((artifact_dir / "summary_shards" / "summary_000000.json").read_text())
    assert chunk_rows[0]["lat"] == -34.06564
    assert chunk_rows[0]["lon"] == 151.01266
    assert summary_rows[0]["coordinate_source"] == "geocoded"
    assert report["event_chunk_patched_count"] == 1
    assert report["summary_shard_patched_count"] == 1
    assert (artifact_dir / "points.bin").exists()
    assert (artifact_dir / "trace_event_index.bin").exists()
    assert json.loads((artifact_dir / "canonical_web_manifest.json").read_text())["counts"]["mapped_events"] == 2


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
