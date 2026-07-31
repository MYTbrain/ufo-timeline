from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.apply_reviewed_event_merges_to_canonical_web import (
    apply_reviewed_event_merges,
)


def test_airship_wave_review_is_bounded_disjoint_and_provenance_preserving() -> None:
    root = Path(__file__).resolve().parents[1]
    sidecar = _read_json(
        root / "data/reports/airship_wave_reviewed_event_merges_v148.json"
    )
    report = _read_json(
        root / "data/reports/airship_wave_reviewed_event_merges_apply_v148.json"
    )
    manifest = _read_json(root / "data/canonical_web/canonical_web_manifest.json")

    assert sidecar["policy"] == "reviewed_same_incident_cross_source_merge"
    assert sidecar["window"] == {
        "start": "1896-11-01",
        "end": "1897-06-30",
    }
    assert sidecar["canonical_full_mutated"] is False
    assert "month-only records" in sidecar["review_method"]

    clusters = sidecar["clusters"]
    member_ids = [
        event_id
        for cluster in clusters
        for event_id in cluster["canonical_event_ids"]
    ]
    assert len(clusters) == 52
    assert len(member_ids) == 169
    assert len(set(member_ids)) == len(member_ids)
    assert sum(len(cluster["canonical_event_ids"]) - 1 for cluster in clusters) == 117
    assert all(
        cluster["preferred_canonical_event_id"] in cluster["canonical_event_ids"]
        for cluster in clusters
    )
    assert all(cluster["match_basis"] for cluster in clusters)

    assert report["reviewed_cluster_count"] == 52
    assert report["merged_member_event_count"] == 169
    assert report["removed_duplicate_event_count"] == 117
    assert report["events_before_count"] == 703018
    assert report["events_after_count"] == 702901
    assert report["source_provenance_preserved"] is True
    assert report["removed_events_preserved_as_keeper_snapshots"] is True

    policy_runs = manifest["policy"].get("reviewed_event_merge_runs") or [
        manifest["policy"]["reviewed_event_merges"]
    ]
    airship_policy = next(
        item
        for item in policy_runs
        if item["window"] == {"start": "1896-11-01", "end": "1897-06-30"}
    )
    assert airship_policy["reviewed_cluster_count"] == 52
    assert airship_policy["removed_duplicate_event_count"] == 117
    assert airship_policy["source_provenance_preserved"] is True
    assert airship_policy["canonical_full_mutated"] is False


def test_reviewed_merge_preserves_sources_and_removes_only_reviewed_copy(
    tmp_path: Path,
) -> None:
    artifact_dir, sidecar = _write_fixture(tmp_path)

    report = apply_reviewed_event_merges(
        artifact_dir=artifact_dir,
        sidecar_path=sidecar,
        report_output=tmp_path / "report.json",
        write_gzip=False,
    )

    detail_rows = _read_json(artifact_dir / "event_chunks/chunk_000000.json")
    summary_rows = _read_json(artifact_dir / "summary_shards/summary_000000.json")
    assert [row["event_id"] for row in detail_rows] == [100, 102]
    assert [row["event_id"] for row in summary_rows] == [100, 102]

    keeper = detail_rows[0]
    assert keeper["canonical_event_id"] == "evt_keeper"
    assert keeper["lat"] == 40.0
    assert keeper["lon"] == -90.0
    assert keeper["has_coordinates"] is True
    assert keeper["description"] == (
        "Named witnesses observed the same highly distinctive incident in full detail."
    )
    assert keeper["canonical_input_ids"] == ["cin_keeper", "cin_copy"]
    assert keeper["duplicate_record_count"] == 3
    assert keeper["source_provenance_count"] == 2
    assert keeper["dedupe_strategy"] == "reviewed_same_incident_cross_source_merge"
    merge = keeper["reviewed_duplicate_merge"]
    assert merge["cluster_id"] == "fixture_cluster"
    assert merge["removed_event_ids"] == [101]
    assert len(merge["member_snapshots"]) == 2
    assert merge["member_snapshots"][1]["source_id"] == "copy_source_id"
    assert "All member snapshots and provenance remain" in keeper["raw_event_block"]

    # A same-date, same-place row is retained because it was not in the
    # explicitly reviewed cluster.
    assert detail_rows[1]["canonical_event_id"] == "evt_distinct"
    assert detail_rows[1]["detail_index"] == 1
    assert summary_rows[1]["detail_index"] == 1

    manifest = _read_json(artifact_dir / "canonical_web_manifest.json")
    assert manifest["counts"]["events"] == 2
    assert manifest["counts"]["mapped_events"] == 2
    policy = manifest["policy"]["reviewed_event_merges"]
    assert policy["reviewed_cluster_count"] == 1
    assert policy["removed_duplicate_event_count"] == 1
    assert policy["source_provenance_preserved"] is True
    assert policy["canonical_full_mutated"] is False

    assert report["events_before_count"] == 3
    assert report["events_after_count"] == 2
    assert report["removed_duplicate_event_count"] == 1
    assert report["removed_events_preserved_as_keeper_snapshots"] is True


def test_missing_reviewed_event_fails_before_artifact_write(tmp_path: Path) -> None:
    artifact_dir, sidecar = _write_fixture(tmp_path)
    payload = _read_json(sidecar)
    payload["clusters"][0]["canonical_event_ids"][1] = "evt_missing"
    _write_json(sidecar, payload)
    before = _artifact_hashes(artifact_dir)

    with pytest.raises(ValueError, match="missing from detail artifacts"):
        apply_reviewed_event_merges(
            artifact_dir=artifact_dir,
            sidecar_path=sidecar,
            report_output=tmp_path / "report.json",
            write_gzip=False,
        )

    assert _artifact_hashes(artifact_dir) == before
    assert not (tmp_path / "report.json").exists()


def test_overlapping_review_clusters_are_rejected(tmp_path: Path) -> None:
    artifact_dir, sidecar = _write_fixture(tmp_path)
    payload = _read_json(sidecar)
    payload["clusters"].append(
        {
            "cluster_id": "overlap",
            "preferred_canonical_event_id": "evt_copy",
            "canonical_event_ids": ["evt_copy", "evt_distinct"],
            "match_basis": ["invalid fixture overlap"],
        }
    )
    _write_json(sidecar, payload)
    before = _artifact_hashes(artifact_dir)

    with pytest.raises(ValueError, match="overlap another cluster"):
        apply_reviewed_event_merges(
            artifact_dir=artifact_dir,
            sidecar_path=sidecar,
            report_output=tmp_path / "report.json",
            write_gzip=False,
        )

    assert _artifact_hashes(artifact_dir) == before


def test_review_window_and_guarded_field_overrides_are_generalized(
    tmp_path: Path,
) -> None:
    artifact_dir, sidecar = _write_fixture(tmp_path)
    payload = _read_json(sidecar)
    payload["window"] = {"start": "1967-05-20", "end": "1967-05-20"}
    for path in (
        artifact_dir / "event_chunks/chunk_000000.json",
        artifact_dir / "summary_shards/summary_000000.json",
    ):
        rows = _read_json(path)
        for row in rows:
            row["sort_date_iso"] = "1967-05-20"
        _write_json(path, rows)
    payload["clusters"][0]["field_overrides"] = {
        "type": "Disk",
        "shape_normalized": "Disk",
        "visual_type_group": "UFO/UAP sighting",
        "craft_type_inferred": "disc_saucer",
        "craft_type_label": "Disc / saucer",
        "craft_type_confidence": "high",
        "craft_type_source": "reviewed_same_incident_evidence",
        "same_day_match_strength": "strong",
    }
    _write_json(sidecar, payload)

    apply_reviewed_event_merges(
        artifact_dir=artifact_dir,
        sidecar_path=sidecar,
        report_output=tmp_path / "report.json",
        write_gzip=False,
    )

    keeper = _read_json(artifact_dir / "event_chunks/chunk_000000.json")[0]
    summary = _read_json(artifact_dir / "summary_shards/summary_000000.json")[0]
    assert keeper["type"] == "Disk"
    assert keeper["craft_type_inferred"] == "disc_saucer"
    assert keeper["reviewed_duplicate_merge"]["field_overrides"]["type"] == "Disk"
    assert summary["type"] == "Disk"
    policy = _read_json(artifact_dir / "canonical_web_manifest.json")["policy"]
    assert policy["reviewed_event_merges"]["window"] == {
        "start": "1967-05-20",
        "end": "1967-05-20",
    }
    assert policy["reviewed_event_merge_runs"][-1]["reviewed_cluster_count"] == 1


def test_unsupported_reviewed_field_override_fails_closed(tmp_path: Path) -> None:
    artifact_dir, sidecar = _write_fixture(tmp_path)
    payload = _read_json(sidecar)
    payload["clusters"][0]["field_overrides"] = {"lat": 40.0}
    _write_json(sidecar, payload)
    before = _artifact_hashes(artifact_dir)

    with pytest.raises(ValueError, match="unsupported field_overrides"):
        apply_reviewed_event_merges(
            artifact_dir=artifact_dir,
            sidecar_path=sidecar,
            report_output=tmp_path / "report.json",
            write_gzip=False,
        )

    assert _artifact_hashes(artifact_dir) == before


def _write_fixture(tmp_path: Path) -> tuple[Path, Path]:
    artifact_dir = tmp_path / "canonical_web"
    (artifact_dir / "event_chunks").mkdir(parents=True)
    (artifact_dir / "summary_shards").mkdir(parents=True)

    keeper = _event(
        event_id=100,
        canonical_event_id="evt_keeper",
        canonical_input_id="cin_keeper",
        source="source_a",
        source_id="keeper_source_id",
        description="Short account.",
        lat=None,
        lon=None,
        coordinate_source="unresolved",
        location_precision="unknown",
    )
    copy = _event(
        event_id=101,
        canonical_event_id="evt_copy",
        canonical_input_id="cin_copy",
        source="source_b",
        source_id="copy_source_id",
        description=(
            "Named witnesses observed the same highly distinctive incident in full detail."
        ),
        lat=40.0,
        lon=-90.0,
        coordinate_source="geocoded",
        location_precision="city",
    )
    copy["duplicate_record_count"] = 2
    distinct = _event(
        event_id=102,
        canonical_event_id="evt_distinct",
        canonical_input_id="cin_distinct",
        source="source_c",
        source_id="distinct_source_id",
        description="A separate report at the same date and place.",
        lat=40.0,
        lon=-90.0,
        coordinate_source="geocoded",
        location_precision="city",
    )
    detail_rows = [keeper, copy, distinct]
    for index, row in enumerate(detail_rows):
        row["chunk_id"] = "chunk_000000"
        row["detail_index"] = index
    summary_rows = [_summary(row) for row in detail_rows]

    _write_json(artifact_dir / "event_chunks/chunk_000000.json", detail_rows)
    _write_json(artifact_dir / "summary_shards/summary_000000.json", summary_rows)
    _write_json(
        artifact_dir / "event_chunk_manifest.json",
        [
            {
                "id": "chunk_000000",
                "file": "chunk_000000.json",
                "event_count": 3,
                "start_event_id": 100,
                "end_event_id": 102,
            }
        ],
    )
    _write_json(
        artifact_dir / "summary_manifest.json",
        [
            {
                "id": "summary_000000",
                "file": "summary_000000.json",
                "event_count": 3,
                "start_event_id": 100,
                "end_event_id": 102,
            }
        ],
    )
    _write_json(
        artifact_dir / "canonical_web_manifest.json",
        {
            "schema_version": 1,
            "source": {"input_path": "fixture"},
            "artifacts": {},
            "counts": {
                "events": 3,
                "mapped_events": 2,
                "event_chunks": 1,
                "summary_shards": 1,
            },
            "policy": {},
        },
    )

    sidecar = tmp_path / "sidecar.json"
    _write_json(
        sidecar,
        {
            "schema_version": 1,
            "policy": "reviewed_same_incident_cross_source_merge",
            "window": {"start": "1896-11-01", "end": "1897-06-30"},
            "clusters": [
                {
                    "cluster_id": "fixture_cluster",
                    "preferred_canonical_event_id": "evt_keeper",
                    "canonical_event_ids": ["evt_keeper", "evt_copy"],
                    "match_basis": [
                        "Same date and named witnesses",
                        "Same distinctive narrative",
                    ],
                }
            ],
        },
    )
    return artifact_dir, sidecar


def _event(
    *,
    event_id: int,
    canonical_event_id: str,
    canonical_input_id: str,
    source: str,
    source_id: str,
    description: str,
    lat: float | None,
    lon: float | None,
    coordinate_source: str,
    location_precision: str,
) -> dict:
    return {
        "event_id": event_id,
        "canonical_event_id": canonical_event_id,
        "canonical_input_ids": [canonical_input_id],
        "source": source,
        "source_file": f"{source}.csv",
        "source_id": source_id,
        "source_provenance_count": 1,
        "source_provenance": [
            {
                "source_name": source,
                "source_file": f"{source}.csv",
                "source_native_id": source_id,
                "canonical_input_id": canonical_input_id,
            }
        ],
        "duplicate_record_count": 1,
        "dedupe_strategy": "single_record",
        "date_raw": "4/15/1897",
        "sort_date_iso": "1897-04-15",
        "date_precision": "exact_day",
        "time_raw": "21:00",
        "location_raw": "Fixture City, IL, US",
        "lat": lat,
        "lon": lon,
        "has_coordinates": lat is not None and lon is not None,
        "coordinate_source": coordinate_source,
        "location_precision": location_precision,
        "type": "Light",
        "shape_normalized": "Light",
        "visual_type_group": "Light",
        "craft_type_inferred": "light",
        "craft_type_label": "Light",
        "craft_type_confidence": "low",
        "craft_type_source": "type_normalized",
        "same_day_match_strength": "medium",
        "description": description,
        "description_short": description,
        "raw_event_block": f"Source: {source}\nDescription: {description}",
        "references": [f"Reference {source}"],
        "links": [f"https://example.test/{source_id}"],
    }


def _summary(event: dict) -> dict:
    keys = (
        "event_id",
        "chunk_id",
        "detail_index",
        "date_raw",
        "sort_date_iso",
        "date_precision",
        "time_raw",
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
    return {key: event.get(key) for key in keys}


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def _artifact_hashes(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }
