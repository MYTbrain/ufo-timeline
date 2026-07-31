from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct

import pytest

from parser.packed_points import ROW_STRUCT
from parser.trace_segments import TRACE_EVENT_ROW_STRUCT
from scripts.apply_non_terrestrial_coordinate_quarantine_to_canonical_web import (
    apply_non_terrestrial_coordinate_quarantine,
)


def test_quarantine_preserves_records_but_removes_placeholder_from_map_artifacts(
    tmp_path: Path,
) -> None:
    artifact_dir, sidecar = _write_fixture(tmp_path)

    report = apply_non_terrestrial_coordinate_quarantine(
        artifact_dir=artifact_dir,
        sidecar_path=sidecar,
        report_output=tmp_path / "report.json",
        write_gzip=False,
    )

    detail_rows = _read_json(artifact_dir / "event_chunks/chunk_000000.json")
    summary_rows = _read_json(artifact_dir / "summary_shards/summary_000000.json")
    target = detail_rows[0]
    assert target["event_id"] == 100
    assert target["lat"] is None
    assert target["lon"] is None
    assert target["coordinate_source"] == "unresolved"
    assert target["location_precision"] == "unknown"
    assert target["has_coordinates"] is False
    assert target["coordinate_quarantine_original_lat"] == 0.0
    assert target["raw_fields"]["key_vals/LatLong"] == "0.000000 -0.000000"
    assert summary_rows[0]["coordinate_quarantine_status"] == (
        "quarantined_non_terrestrial_placeholder"
    )

    # The rule is intentionally narrow: a terrestrial exact-zero row and a
    # non-zero lunar observer coordinate remain mapped.
    assert summary_rows[1]["has_coordinates"] is True
    assert summary_rows[1]["lat"] == 0.0
    assert summary_rows[2]["has_coordinates"] is True
    assert summary_rows[2]["lat"] == 50.583336

    points_meta = _read_json(artifact_dir / "points_meta.json")
    trace_meta = _read_json(artifact_dir / "trace_event_index_meta.json")
    assert points_meta["row_count"] == 2
    assert trace_meta["row_count"] == 2
    assert _event_ids(
        artifact_dir / "points.bin",
        row_struct=ROW_STRUCT,
        row_count=points_meta["row_count"],
    ) == [101, 102]
    assert _event_ids(
        artifact_dir / "trace_event_index.bin",
        row_struct=TRACE_EVENT_ROW_STRUCT,
        row_count=trace_meta["row_count"],
    ) == [101, 102]

    manifest = _read_json(artifact_dir / "canonical_web_manifest.json")
    assert manifest["counts"]["mapped_events"] == 2
    assert manifest["counts"]["coordinate_source_counts"] == {
        "raw_latlong": 2,
        "unresolved": 1,
    }
    policy = manifest["policy"]["non_terrestrial_coordinate_quarantine"]
    assert policy["quarantined_event_count"] == 1
    assert policy["event_records_preserved"] is True
    assert report["quarantined_event_count"] == 1
    assert report["mapped_reduction_count"] == 1


def test_stale_guard_fails_before_any_artifact_write(tmp_path: Path) -> None:
    artifact_dir, sidecar = _write_fixture(tmp_path)
    sidecar_payload = _read_json(sidecar)
    sidecar_payload["proposed_patches"][0]["expected_detail_fields"]["location_raw"] = (
        "stale value"
    )
    _write_json(sidecar, sidecar_payload)
    before = _json_hashes(artifact_dir)

    with pytest.raises(ValueError, match="stale guard"):
        apply_non_terrestrial_coordinate_quarantine(
            artifact_dir=artifact_dir,
            sidecar_path=sidecar,
            report_output=tmp_path / "report.json",
            write_gzip=False,
        )

    assert _json_hashes(artifact_dir) == before
    assert not (artifact_dir / "points.bin").exists()
    assert not (tmp_path / "report.json").exists()


def _write_fixture(tmp_path: Path) -> tuple[Path, Path]:
    artifact_dir = tmp_path / "canonical_web"
    (artifact_dir / "event_chunks").mkdir(parents=True)
    (artifact_dir / "summary_shards").mkdir(parents=True)
    rows = [
        {
            "event_id": 100,
            "canonical_event_id": "evt_lunar_zero",
            "chunk_id": "chunk_000000",
            "detail_index": 0,
            "source": "majestic",
            "source_file": "majestic.csv",
            "source_id": "Hatch_fixture",
            "sort_date_iso": "1887-11-23",
            "date_precision": "exact_day",
            "location_raw": "Residential, MOON, PLT, The Moon",
            "lat": 0.0,
            "lon": -0.0,
            "coordinate_source": "raw_latlong",
            "location_precision": "exact_coords",
            "has_coordinates": True,
            "type": "Triangle",
            "shape_normalized": "Triangle",
            "raw_fields": {
                "source_id": "Hatch_fixture",
                "key_vals/Country": "The Moon",
                "key_vals/LatLong": "0.000000 -0.000000",
            },
        },
        {
            "event_id": 101,
            "canonical_event_id": "evt_earth_zero",
            "chunk_id": "chunk_000000",
            "detail_index": 1,
            "source": "majestic",
            "source_file": "majestic.csv",
            "source_id": "Hatch_earth",
            "sort_date_iso": "1900-01-01",
            "date_precision": "exact_day",
            "location_raw": "Gulf of Guinea, Atlantic Ocean",
            "lat": 0.0,
            "lon": 0.0,
            "coordinate_source": "raw_latlong",
            "location_precision": "exact_coords",
            "has_coordinates": True,
            "type": "Light",
            "shape_normalized": "Light",
            "raw_fields": {
                "source_id": "Hatch_earth",
                "key_vals/Country": "Atlantic Ocean",
                "key_vals/LatLong": "0.000000 0.000000",
            },
        },
        {
            "event_id": 102,
            "canonical_event_id": "evt_lunar_observer",
            "chunk_id": "chunk_000000",
            "detail_index": 2,
            "source": "majestic",
            "source_file": "majestic.csv",
            "source_id": "Hatch_observer",
            "sort_date_iso": "1973-09-10",
            "date_precision": "exact_day",
            "location_raw": "EMBOURG, The Moon",
            "lat": 50.583336,
            "lon": 5.583334,
            "coordinate_source": "raw_latlong",
            "location_precision": "exact_coords",
            "has_coordinates": True,
            "type": "Light",
            "shape_normalized": "Light",
            "raw_fields": {
                "source_id": "Hatch_observer",
                "key_vals/Country": "The Moon",
                "key_vals/LatLong": "50.583336 5.583334",
            },
        },
    ]
    _write_json(artifact_dir / "event_chunks/chunk_000000.json", rows)
    _write_json(artifact_dir / "summary_shards/summary_000000.json", rows)
    _write_json(
        artifact_dir / "event_chunk_manifest.json",
        [{"id": "chunk_000000", "file": "chunk_000000.json", "event_count": 3}],
    )
    _write_json(
        artifact_dir / "summary_manifest.json",
        [{"id": "summary_000000", "file": "summary_000000.json", "event_count": 3}],
    )
    _write_json(
        artifact_dir / "canonical_web_manifest.json",
        {
            "schema_version": 1,
            "source": {"input_path": "fixture"},
            "artifacts": {},
            "counts": {
                "events": 3,
                "mapped_events": 3,
                "location_precision_counts": {"exact_coords": 3},
                "coordinate_source_counts": {"raw_latlong": 3},
            },
            "policy": {},
        },
    )
    sidecar = tmp_path / "sidecar.json"
    _write_json(
        sidecar,
        {
            "schema_version": 1,
            "policy": "explicit_non_terrestrial_jurisdiction_plus_exact_zero_coordinate",
            "proposed_patches": [
                {
                    "canonical_event_id": "evt_lunar_zero",
                    "event_id": 100,
                    "detail_artifact": {
                        "path": "event_chunks/chunk_000000.json",
                        "index": 0,
                    },
                    "summary_artifact": {
                        "path": "summary_shards/summary_000000.json",
                        "index": 0,
                    },
                    "expected_detail_fields": {
                        "event_id": 100,
                        "canonical_event_id": "evt_lunar_zero",
                        "source": "majestic",
                        "source_file": "majestic.csv",
                        "source_id": "Hatch_fixture",
                        "sort_date_iso": "1887-11-23",
                        "location_raw": "Residential, MOON, PLT, The Moon",
                        "lat": 0.0,
                        "lon": -0.0,
                        "coordinate_source": "raw_latlong",
                        "location_precision": "exact_coords",
                        "has_coordinates": True,
                    },
                    "expected_summary_fields": {
                        "event_id": 100,
                        "source": "majestic",
                        "sort_date_iso": "1887-11-23",
                        "location_raw": "Residential, MOON, PLT, The Moon",
                        "lat": 0.0,
                        "lon": -0.0,
                        "coordinate_source": "raw_latlong",
                        "location_precision": "exact_coords",
                        "has_coordinates": True,
                    },
                    "expected_raw_fields": {
                        "source_id": "Hatch_fixture",
                        "key_vals/Country": "The Moon",
                        "key_vals/LatLong": "0.000000 -0.000000",
                    },
                    "set_fields": {
                        "lat": None,
                        "lon": None,
                        "coordinate_source": "unresolved",
                        "location_precision": "unknown",
                        "has_coordinates": False,
                        "coordinate_quarantine_status": (
                            "quarantined_non_terrestrial_placeholder"
                        ),
                        "coordinate_quarantine_reason": (
                            "non_terrestrial_location_with_exact_zero_coordinate"
                        ),
                        "coordinate_quarantine_original_lat": 0.0,
                        "coordinate_quarantine_original_lon": -0.0,
                        "coordinate_quarantine_original_source": "raw_latlong",
                        "coordinate_quarantine_original_precision": "exact_coords",
                        "non_terrestrial_location": "The Moon",
                        "mapping_notes": "Earth-map coordinates omitted.",
                    },
                }
            ],
        },
    )
    return artifact_dir, sidecar


def _event_ids(path: Path, *, row_struct: struct.Struct, row_count: int) -> list[int]:
    data = path.read_bytes()
    assert len(data) == row_count * row_struct.size
    return [values[0] for values in row_struct.iter_unpack(data)]


def _json_hashes(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*.json"))
    }


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
