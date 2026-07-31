from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.apply_coordinate_transform_repair_sidecar_to_canonical_web import (
    apply_transform_sidecar_to_canonical_web,
)


def test_apply_transform_sidecar_to_canonical_web_patches_json_and_packed_artifacts(tmp_path: Path) -> None:
    artifact_dir = _write_fixture_artifacts(tmp_path)
    sidecar = tmp_path / "sidecar.json"
    _write_json(sidecar, _sidecar_payload())

    report = apply_transform_sidecar_to_canonical_web(
        artifact_dir=artifact_dir,
        sidecar_path=sidecar,
        report_output=tmp_path / "report.json",
        write_gzip=False,
    )

    chunk_rows = json.loads((artifact_dir / "event_chunks" / "chunk_000000.json").read_text())
    summary_rows = json.loads((artifact_dir / "summary_shards" / "summary_000000.json").read_text())
    assert chunk_rows[0]["lat"] == 47.65145
    assert chunk_rows[0]["lon"] == -3.51305
    assert chunk_rows[0]["transform_coordinate_repair_transform"] == "lon_sign_flip"
    assert summary_rows[0]["coordinate_source"] == "geocoded"
    assert report["event_chunk_patched_count"] == 1
    assert report["summary_shard_patched_count"] == 1
    assert (artifact_dir / "points.bin").exists()
    assert (artifact_dir / "trace_event_index.bin").exists()
    manifest = json.loads((artifact_dir / "canonical_web_manifest.json").read_text())
    assert manifest["counts"]["mapped_events"] == 2
    assert manifest["policy"]["transform_coordinate_repair_sidecar"]["patched_event_count"] == 1
    assert len(manifest["policy"]["transform_coordinate_repair_sidecars"]) == 1
    assert manifest["policy"]["transform_coordinate_repair_total_patched_event_count"] == 1
    assert "admin_coordinate_repair_sidecar" not in manifest["policy"]


def test_apply_transform_sidecar_rejects_stale_old_coordinate_guard(tmp_path: Path) -> None:
    artifact_dir = _write_fixture_artifacts(tmp_path, old_lat=47.44)
    sidecar = tmp_path / "sidecar.json"
    _write_json(sidecar, _sidecar_payload())

    with pytest.raises(ValueError, match="old-coordinate guard"):
        apply_transform_sidecar_to_canonical_web(
            artifact_dir=artifact_dir,
            sidecar_path=sidecar,
            report_output=tmp_path / "report.json",
            write_gzip=False,
        )


def test_apply_transform_sidecar_accepts_source_coordinate_alias(tmp_path: Path) -> None:
    artifact_dir = _write_fixture_artifacts(tmp_path, coordinate_source="raw_latlong")
    sidecar = tmp_path / "sidecar.json"
    _write_json(sidecar, _sidecar_payload())

    report = apply_transform_sidecar_to_canonical_web(
        artifact_dir=artifact_dir,
        sidecar_path=sidecar,
        report_output=tmp_path / "report.json",
        write_gzip=False,
    )

    assert report["event_chunk_patched_count"] == 1


def test_apply_transform_sidecar_rejects_stale_coordinate_source_guard(tmp_path: Path) -> None:
    artifact_dir = _write_fixture_artifacts(tmp_path, coordinate_source="geocoded")
    sidecar = tmp_path / "sidecar.json"
    _write_json(sidecar, _sidecar_payload())

    with pytest.raises(ValueError, match="source guard"):
        apply_transform_sidecar_to_canonical_web(
            artifact_dir=artifact_dir,
            sidecar_path=sidecar,
            report_output=tmp_path / "report.json",
            write_gzip=False,
        )


def test_apply_transform_sidecar_rejects_weak_transform_evidence(tmp_path: Path) -> None:
    artifact_dir = _write_fixture_artifacts(tmp_path)
    sidecar = tmp_path / "sidecar.json"
    payload = _sidecar_payload()
    payload["proposed_patches"][0]["transform_evidence"]["transformed_distance_km"] = 60
    _write_json(sidecar, payload)

    with pytest.raises(ValueError, match="safety thresholds"):
        apply_transform_sidecar_to_canonical_web(
            artifact_dir=artifact_dir,
            sidecar_path=sidecar,
            report_output=tmp_path / "report.json",
            write_gzip=False,
        )


def test_apply_transform_sidecar_preserves_existing_admin_policy(tmp_path: Path) -> None:
    artifact_dir = _write_fixture_artifacts(tmp_path)
    manifest_path = artifact_dir / "canonical_web_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["policy"]["admin_coordinate_repair_sidecar"] = {
        "applied": True,
        "sidecar": "admin-sidecar.json",
        "patched_event_count": 13,
        "canonical_full_mutated": False,
    }
    _write_json(manifest_path, manifest)
    sidecar = tmp_path / "sidecar.json"
    _write_json(sidecar, _sidecar_payload())

    apply_transform_sidecar_to_canonical_web(
        artifact_dir=artifact_dir,
        sidecar_path=sidecar,
        report_output=tmp_path / "report.json",
        write_gzip=False,
    )

    updated = json.loads(manifest_path.read_text())
    assert updated["policy"]["admin_coordinate_repair_sidecar"]["sidecar"] == "admin-sidecar.json"
    assert updated["policy"]["admin_coordinate_repair_sidecar"]["patched_event_count"] == 13
    assert updated["policy"]["transform_coordinate_repair_sidecar"]["patched_event_count"] == 1


def test_apply_transform_sidecar_preserves_existing_transform_policy_history(tmp_path: Path) -> None:
    artifact_dir = _write_fixture_artifacts(tmp_path)
    manifest_path = artifact_dir / "canonical_web_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["policy"]["transform_coordinate_repair_sidecar"] = {
        "applied": True,
        "sidecar": "previous-transform-sidecar.json",
        "patched_event_count": 47,
        "canonical_full_mutated": False,
    }
    _write_json(manifest_path, manifest)
    sidecar = tmp_path / "sidecar.json"
    _write_json(sidecar, _sidecar_payload())

    apply_transform_sidecar_to_canonical_web(
        artifact_dir=artifact_dir,
        sidecar_path=sidecar,
        report_output=tmp_path / "report.json",
        write_gzip=False,
    )

    updated = json.loads(manifest_path.read_text())
    policy = updated["policy"]
    assert policy["transform_coordinate_repair_sidecar"]["sidecar"] == str(sidecar.resolve())
    assert policy["transform_coordinate_repair_sidecar"]["patched_event_count"] == 1
    assert policy["transform_coordinate_repair_sidecars"] == [
        {
            "applied": True,
            "sidecar": "previous-transform-sidecar.json",
            "patched_event_count": 47,
            "canonical_full_mutated": False,
        },
        {
            "applied": True,
            "sidecar": str(sidecar.resolve()),
            "patched_event_count": 1,
            "canonical_full_mutated": False,
        },
    ]
    assert policy["transform_coordinate_repair_total_patched_event_count"] == 48


def test_apply_transform_sidecar_preserves_existing_transform_history_list(tmp_path: Path) -> None:
    artifact_dir = _write_fixture_artifacts(tmp_path)
    manifest_path = artifact_dir / "canonical_web_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["policy"]["transform_coordinate_repair_sidecars"] = [
        {
            "applied": True,
            "sidecar": "transform-v109.json",
            "patched_event_count": 47,
            "canonical_full_mutated": False,
        },
        {
            "applied": True,
            "sidecar": "transform-v111.json",
            "patched_event_count": 18,
            "canonical_full_mutated": False,
        },
    ]
    _write_json(manifest_path, manifest)
    sidecar = tmp_path / "sidecar.json"
    _write_json(sidecar, _sidecar_payload())

    apply_transform_sidecar_to_canonical_web(
        artifact_dir=artifact_dir,
        sidecar_path=sidecar,
        report_output=tmp_path / "report.json",
        write_gzip=False,
    )

    updated = json.loads(manifest_path.read_text())
    history = updated["policy"]["transform_coordinate_repair_sidecars"]
    assert [item["sidecar"] for item in history] == [
        "transform-v109.json",
        "transform-v111.json",
        str(sidecar.resolve()),
    ]
    assert updated["policy"]["transform_coordinate_repair_total_patched_event_count"] == 66


def _write_fixture_artifacts(
    tmp_path: Path,
    *,
    old_lat: float = 47.43,
    coordinate_source: str = "source_coordinates",
) -> Path:
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
            "canonical_event_id": "evt_fr_1",
            "chunk_id": "chunk_000000",
            "detail_index": 0,
            "date_raw": "1990-11-05",
            "date_iso": "1990-11-05",
            "sort_date_iso": "1990-11-05",
            "date_precision": "exact_day",
            "location_raw": "PEN-MEN, Finistere, FRA, EU",
            "source": "ufocat",
            "type": "Unknown",
            "shape_normalized": "Unknown",
            "visual_type_group": "Other / unknown",
            "coordinate_source": coordinate_source,
            "location_precision": "coordinate",
            "lat": old_lat,
            "lon": 3.82,
            "has_coordinates": True,
        },
        {
            "event_id": 102,
            "canonical_event_id": "evt_keep",
            "chunk_id": "chunk_000000",
            "detail_index": 1,
            "date_raw": "1990-11-06",
            "date_iso": "1990-11-06",
            "sort_date_iso": "1990-11-06",
            "date_precision": "exact_day",
            "location_raw": "BREST, Finistere, FRA, EU",
            "source": "ufocat",
            "type": "Light",
            "shape_normalized": "Light",
            "visual_type_group": "UFO/UAP sighting",
            "coordinate_source": "geocoded",
            "location_precision": "city",
            "lat": 48.3904,
            "lon": -4.4861,
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
    return artifact_dir


def _sidecar_payload() -> dict:
    return {
        "schema_version": 1,
        "proposed_patches": [
            {
                "canonical_event_id": "evt_fr_1",
                "country": "France",
                "transform": "lon_sign_flip",
                "old": {
                    "lat": 47.43,
                    "lon": 3.82,
                    "coordinate_source": "source_coordinates",
                    "location_precision": "coordinate",
                },
                "transform_evidence": {
                    "lat": 47.43,
                    "lon": -3.82,
                    "transform": "lon_sign_flip",
                    "original_distance_km": 550.793,
                    "transformed_distance_km": 33.723,
                    "distance_improvement_ratio": 16.333,
                },
                "set_fields": {
                    "lat": 47.65145,
                    "lon": -3.51305,
                    "coordinate_source": "geocoded",
                    "location_precision": "mapped",
                    "transform_coordinate_repair_transform": "lon_sign_flip",
                },
            }
        ],
    }


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
