from __future__ import annotations

import json
from pathlib import Path

from parser.packed_points import ROW_STRUCT
from parser.trace_segments import TRACE_EVENT_ROW_STRUCT


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_ROOT = PROJECT_ROOT / "static_bundle" / "data" / "canonical_web"
QUARANTINED = (
    ("chunk_000087.json", 862, 31235763669570, "Hatch_UDB_139"),
    ("chunk_000192.json", 949, 132294255236761, "Hatch_UDB_17715"),
    ("chunk_000201.json", 1848, 4114331960007368, "Hatch_UDB_3756"),
)
PRESERVED_LUNAR_OBSERVER_EVENT_ID = 1769977787353407
REVIEWED_RELEASE_EVENTS = 702893
REVIEWED_RELEASE_MAPPED_EVENTS = 580783
REVIEWED_RELEASE_TRACE_EVENTS = 574943
REVIEWED_RELEASE_UNRESOLVED_EVENTS = 122110


def test_known_lunar_zero_placeholders_are_unmapped_but_auditable() -> None:
    for chunk_name, detail_index, event_id, source_id in QUARANTINED:
        rows = _read_json(ARTIFACT_ROOT / "event_chunks" / chunk_name)
        event = rows[detail_index]
        assert event["event_id"] == event_id
        assert event["source_id"] == source_id
        assert event["lat"] is None
        assert event["lon"] is None
        assert event["coordinate_source"] == "unresolved"
        assert event["has_coordinates"] is False
        assert event["coordinate_quarantine_status"] == (
            "quarantined_non_terrestrial_placeholder"
        )
        assert event["coordinate_quarantine_original_lat"] == 0.0
        assert event["raw_fields"]["key_vals/Country"] == "The Moon"
        assert event["raw_fields"]["key_vals/LatLong"] == "0.000000 -0.000000"


def test_quarantined_ids_are_absent_from_points_and_traces_without_blanket_lunar_removal() -> None:
    quarantined_ids = {event_id for _, _, event_id, _ in QUARANTINED}
    point_ids = _packed_event_ids(
        ARTIFACT_ROOT / "points.bin",
        ARTIFACT_ROOT / "points_meta.json",
        ROW_STRUCT,
    )
    trace_ids = _packed_event_ids(
        ARTIFACT_ROOT / "trace_event_index.bin",
        ARTIFACT_ROOT / "trace_event_index_meta.json",
        TRACE_EVENT_ROW_STRUCT,
    )

    assert quarantined_ids.isdisjoint(point_ids)
    assert quarantined_ids.isdisjoint(trace_ids)
    assert PRESERVED_LUNAR_OBSERVER_EVENT_ID in point_ids
    assert PRESERVED_LUNAR_OBSERVER_EVENT_ID in trace_ids

    manifest = _read_json(ARTIFACT_ROOT / "canonical_web_manifest.json")
    assert manifest["counts"]["mapped_events"] == REVIEWED_RELEASE_MAPPED_EVENTS
    assert manifest["counts"]["trace_events"] == REVIEWED_RELEASE_TRACE_EVENTS
    policy = manifest["policy"]["non_terrestrial_coordinate_quarantine"]
    assert policy["quarantined_event_count"] == 3
    assert policy["event_records_preserved"] is True


def test_quarantined_ids_are_absent_from_startup_profile_events_and_trace_preview() -> None:
    quarantined_ids = {event_id for _, _, event_id, _ in QUARANTINED}
    profiles_root = ARTIFACT_ROOT.parent / "startup_profiles"
    profile_index = _read_json(profiles_root / "manifest.json")
    for profile in profile_index["profiles"]:
        profile_root = profiles_root / profile["id"]
        events = _read_json(profile_root / "events.json")
        event_ids = {event["event_id"] for event in events}
        assert quarantined_ids.isdisjoint(event_ids)
        preview_segments = _read_json(profile_root / "trace_preview_segments.json")
        preview_ids = {
            event_id
            for segment in preview_segments
            for event_id in (segment["from_event_id"], segment["to_event_id"])
        }
        assert quarantined_ids.isdisjoint(preview_ids)


def test_public_app_config_matches_quarantined_catalog_counts() -> None:
    app_config = _read_json(ARTIFACT_ROOT.parent / "app_config.json")
    manifest = _read_json(ARTIFACT_ROOT / "canonical_web_manifest.json")

    assert (
        app_config["normalizedCount"]
        == manifest["counts"]["events"]
        == REVIEWED_RELEASE_EVENTS
    )
    assert (
        app_config["mappedCount"]
        == manifest["counts"]["mapped_events"]
        == REVIEWED_RELEASE_MAPPED_EVENTS
    )
    assert app_config["unresolvedCount"] == REVIEWED_RELEASE_UNRESOLVED_EVENTS
    assert (
        app_config["packedPoints"]["rowCount"]
        == manifest["packed_points"]["row_count"]
        == REVIEWED_RELEASE_MAPPED_EVENTS
    )
    assert app_config["precisionBreakdown"] == manifest["counts"]["location_precision_counts"]


def _packed_event_ids(path: Path, metadata_path: Path, row_struct) -> set[int]:
    metadata = _read_json(metadata_path)
    data = path.read_bytes()
    assert len(data) == metadata["row_count"] * row_struct.size
    return {values[0] for values in row_struct.iter_unpack(data)}


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))
