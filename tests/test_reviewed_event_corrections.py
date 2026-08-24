from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from parser.canonical_export import canonical_event_to_normalized_event
from parser.canonical_schema import CanonicalInputRecord
from parser.dedupe import (
    DEDUPE_STRATEGY_MAXIMAL_V3,
    SUPPORTED_DEDUPE_STRATEGIES,
    build_deduped_events,
)
from parser.packed_points import ROW_STRUCT as PACKED_POINT_ROW_STRUCT
from parser.reviewed_event_corrections import (
    NAPA_CANONICAL_EVENT_ID,
    NAPA_CANONICAL_INPUT_ID,
    NAPA_CORRECTION_ID,
    NAPA_EVENT_ID,
    NAPA_EXPECTED_RAW_FIELDS,
    NAPA_REVIEWED_FIELDS,
    NAPA_SINGLETON_EVENT_IDS,
    NAPA_SOURCE_ROW_HASH,
    NARRATIVE_LOCATION_CORRECTIONS,
    apply_reviewed_event_corrections,
)
from parser.trace_segments import TRACE_EVENT_ROW_STRUCT
from parser.utils import write_jsonl
from scripts.build_canonical_web_artifacts import build_canonical_web_artifacts


def test_napa_reviewed_correction_updates_projection_and_preserves_raw_source() -> None:
    original = _napa_event()

    corrected = apply_reviewed_event_corrections(original)

    assert corrected["canonical_event_id"] == NAPA_CANONICAL_EVENT_ID
    assert corrected["canonical_input_ids"] == [NAPA_CANONICAL_INPUT_ID]
    assert corrected["time_raw"] == "10:50"
    assert corrected["time_display"] == "10:45"
    assert corrected["location_raw"] == (
        "Farmlands, NAPA VALLEY, CA, Colorado, USA"
    )
    assert corrected["location_display"] == (
        "Napa Valley near Napa, Napa County, California, USA"
    )
    assert corrected["city"] == "Napa"
    assert corrected["state_province"] == "California"
    assert corrected["country"] == "USA"
    assert corrected["lat"] == 38.300002
    assert corrected["lon"] == -122.300006
    assert corrected["location_precision"] == "city"
    assert corrected["duration_raw"] == "1"
    assert corrected["duration_display"] == (
        "Not stated in the contemporary newspaper account"
    )
    assert corrected["summary"] == original["summary"]
    assert corrected["description"] == original["description"]
    assert corrected["source_url"] == original["source_url"]
    assert corrected["source_url_display"].endswith("#page=51")
    assert corrected["raw_fields"] == original["raw_fields"]
    assert corrected["raw_fields"]["key_vals/State/Prov"] == "Colorado"
    assert corrected["raw_fields"]["key_vals/Locale"] == "Farmlands"
    assert corrected["raw_fields"]["time"] == "10:50"
    assert corrected["raw_fields"]["key_vals/Duration"] == "1"
    assert corrected["reviewed_corrections"][0]["correction_id"] == NAPA_CORRECTION_ID


def test_napa_reviewed_correction_is_idempotent() -> None:
    once = apply_reviewed_event_corrections(_napa_event())

    twice = apply_reviewed_event_corrections(once)

    assert twice == once


def test_magonia_narrative_location_is_replaced_only_in_display_projection() -> None:
    original = _magonia_811_event()

    corrected = apply_reviewed_event_corrections(original)

    assert corrected["location_raw"] == original["location_raw"]
    assert corrected["raw_fields"] == original["raw_fields"]
    assert corrected["location_display"] == (
        "Interstate 64 near Dunbar, West Virginia, USA"
    )
    assert corrected["city"] == "Dunbar"
    assert corrected["state_province"] == "West Virginia"
    assert corrected["country"] == "USA"
    assert corrected["lat"] is None
    assert corrected["lon"] is None
    assert corrected["reviewed_corrections"][-1]["correction_id"] == (
        "majestic-magonia-811-dunbar-location-2026-08-24"
    )
    assert apply_reviewed_event_corrections(corrected) == corrected


def test_magonia_narrative_location_correction_fails_closed_on_source_change() -> None:
    stale = _magonia_811_event()
    stale["raw_fields"]["location/0"] += " changed"

    with pytest.raises(ValueError, match="stale-source guard"):
        apply_reviewed_event_corrections(stale)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("lat", 39.7392),
        ("lon", -104.9903),
        ("canonical_event_id", "evt_changed"),
        ("event_id", 123),
    ],
)
def test_napa_reviewed_correction_fails_closed_if_identity_or_coordinate_changes(
    field: str,
    value: object,
) -> None:
    stale = _napa_event()
    stale[field] = value

    with pytest.raises(ValueError, match="stale-source guard"):
        apply_reviewed_event_corrections(stale)


def test_napa_input_as_non_primary_merge_member_is_not_rewritten() -> None:
    merged = _napa_event()
    merged.update(
        {
            "canonical_input_id": "cin_other",
            "canonical_input_ids": ["cin_other", NAPA_CANONICAL_INPUT_ID],
            "canonical_event_id": "evt_merged",
            "event_id": 999,
            "source_name": "nuforc",
            "source_native_id": "other",
            "duplicate_record_count": 2,
            "dedupe_strategy": "maximal_v3_auto_merge",
        }
    )

    assert apply_reviewed_event_corrections(merged) == merged


def test_napa_primary_record_with_changed_merge_topology_fails_closed() -> None:
    merged = _napa_event()
    merged["canonical_input_ids"] = [NAPA_CANONICAL_INPUT_ID, "cin_other"]
    merged["duplicate_record_count"] = 2

    with pytest.raises(ValueError, match="stale-source guard"):
        apply_reviewed_event_corrections(merged)


@pytest.mark.parametrize("strategy", sorted(SUPPORTED_DEDUPE_STRATEGIES))
def test_napa_correction_runs_after_actual_supported_dedupe(strategy: str) -> None:
    deduped, duplicate_groups = build_deduped_events(
        [_napa_input_record()],
        strategy=strategy,
    )

    assert duplicate_groups == []
    assert deduped[0]["canonical_event_id"] in NAPA_SINGLETON_EVENT_IDS
    if strategy == DEDUPE_STRATEGY_MAXIMAL_V3:
        assert deduped[0]["canonical_event_id"] == NAPA_CANONICAL_EVENT_ID
    corrected = apply_reviewed_event_corrections(deduped[0])
    assert corrected["canonical_input_ids"] == [NAPA_CANONICAL_INPUT_ID]
    assert corrected["location_display"] == NAPA_REVIEWED_FIELDS["location_display"]
    assert corrected["location_raw"] == _napa_event()["location_raw"]


def test_napa_reviewed_correction_fails_closed_if_source_guard_changes() -> None:
    stale = _napa_event()
    stale["raw_fields"]["key_vals/State/Prov"] = "California"

    with pytest.raises(ValueError, match="stale-source guard"):
        apply_reviewed_event_corrections(stale)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_name", "other"),
        ("source_file", "other.csv"),
        ("source_row_number", 1),
        ("source_native_id", "other"),
        ("source_row_hash", "other"),
        ("canonical_input_id", "cin_other"),
    ],
)
def test_napa_reviewed_correction_fails_closed_if_provenance_member_changes(
    field: str,
    value: object,
) -> None:
    stale = _napa_event()
    stale["source_provenance"][0][field] = value

    with pytest.raises(ValueError, match="stale-source guard"):
        apply_reviewed_event_corrections(stale)


def test_napa_mapping_note_and_evidence_survive_normalized_export() -> None:
    corrected = apply_reviewed_event_corrections(_napa_event())

    normalized = canonical_event_to_normalized_event(corrected)

    assert normalized["event_id"] == NAPA_EVENT_ID
    assert normalized["time_raw"] == "10:50"
    assert normalized["time_display"] == "10:45"
    assert normalized["location_raw"] == corrected["location_raw"]
    assert normalized["location_display"] == corrected["location_display"]
    assert normalized["geocode_display_name"] == corrected["location_display"]
    assert normalized["location_precision"] == "city"
    assert "Corrected the normalized state" in normalized["mapping_notes"]
    assert normalized["reviewed_corrections"][0]["correction_id"] == NAPA_CORRECTION_ID
    assert (
        normalized["extra_data"]["canonical"]["reviewed_corrections"][0][
            "correction_id"
        ]
        == NAPA_CORRECTION_ID
    )
    assert normalized["extra_data"]["canonical"]["raw_fields"][
        "key_vals/State/Prov"
    ] == "Colorado"
    assert "Time: 10:50" in normalized["raw_event_block"]
    assert "Location: Farmlands, NAPA VALLEY, CA, Colorado, USA" in normalized[
        "raw_event_block"
    ]
    assert normalized["links"][0].endswith("#page=51")


def test_canonical_web_build_applies_napa_correction_to_all_map_surfaces(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "deduped_events.jsonl"
    output_dir = tmp_path / "canonical_web"
    write_jsonl(input_path, [_napa_event()])

    build_canonical_web_artifacts(
        input_path=input_path,
        output_dir=output_dir,
        chunk_size=1,
        summary_shard_size=1,
    )

    detail = _read_json(output_dir / "event_chunks/chunk_000000.json")[0]
    summary = _read_json(output_dir / "summary_shards/summary_000000.json")[0]
    manifest = _read_json(output_dir / "canonical_web_manifest.json")
    points_meta = _read_json(output_dir / "points_meta.json")

    assert detail["event_id"] == NAPA_EVENT_ID
    assert detail["time_raw"] == "10:50"
    assert detail["time_display"] == "10:45"
    assert detail["parsed_time_local_minutes"] == 645.0
    assert detail["location_raw"] == (
        "Farmlands, NAPA VALLEY, CA, Colorado, USA"
    )
    assert detail["location_display"] == (
        "Napa Valley near Napa, Napa County, California, USA"
    )
    assert detail["state_province"] == "California"
    assert detail["location_precision"] == "city"
    assert detail["lat"] == 38.300002
    assert detail["lon"] == -122.300006
    assert detail["duration_raw"] == "1"
    assert detail["duration_display"] == (
        "Not stated in the contemporary newspaper account"
    )
    assert detail["raw_fields"]["key_vals/State/Prov"] == "Colorado"
    assert detail["raw_fields"]["key_vals/Duration"] == "1"
    assert detail["reviewed_corrections"][0]["correction_id"] == NAPA_CORRECTION_ID
    assert "Original Hatch values remain preserved" in detail["mapping_notes"]
    assert "Time: 10:50" in detail["raw_event_block"]
    assert "Location: Farmlands, NAPA VALLEY, CA, Colorado, USA" in detail[
        "raw_event_block"
    ]
    assert "Duration: 1" in detail["raw_event_block"]
    assert "Time: 10:45" not in detail["raw_event_block"]
    assert "key_vals/State/Prov: Colorado" in detail["raw_event_block"]

    assert summary["event_id"] == NAPA_EVENT_ID
    assert summary["time_raw"] == "10:50"
    assert summary["time_display"] == "10:45"
    assert summary["location_raw"] == detail["location_raw"]
    assert summary["location_display"] == detail["location_display"]
    assert summary["location_precision"] == "city"
    assert summary["lat"] == detail["lat"]
    assert summary["lon"] == detail["lon"]

    policy = manifest["policy"]["reviewed_event_corrections"]
    assert policy == {
        "applied": True,
        "event_count": 1,
        "correction_counts": {NAPA_CORRECTION_ID: 1},
        "raw_source_fields_preserved": True,
    }
    assert manifest["counts"]["location_precision_counts"] == {"city": 1}
    assert points_meta["lookup_tables"]["location_precisions"] == [None, "city"]

    packed_row = _read_binary_rows(
        output_dir / "points.bin",
        points_meta,
        PACKED_POINT_ROW_STRUCT,
    )[0]
    assert packed_row["event_id"] == NAPA_EVENT_ID
    assert packed_row["lat"] == pytest.approx(38.300002)
    assert packed_row["lon"] == pytest.approx(-122.300006)
    assert packed_row["location_precision_id"] == "city"
    assert packed_row["sort_time_ms"] == detail["estimated_utc_timestamp_ms"]
    assert packed_row["chunk_id"] == detail["chunk_id"]
    assert packed_row["detail_index"] == detail["detail_index"]

    trace_meta = _read_json(output_dir / "trace_event_index_meta.json")
    trace_row = _read_binary_rows(
        output_dir / "trace_event_index.bin",
        trace_meta,
        TRACE_EVENT_ROW_STRUCT,
    )[0]
    assert trace_row["event_id"] == NAPA_EVENT_ID
    assert trace_row["lat"] == pytest.approx(38.300002)
    assert trace_row["lon"] == pytest.approx(-122.300006)
    assert trace_row["sequence_index"] == 0


def _magonia_811_event() -> dict[str, object]:
    correction = NARRATIVE_LOCATION_CORRECTIONS[
        "evt_c20894010b97e5adf60162c6"
    ]
    target = correction["target"]
    location = (
        "Charleston (West Virginia) Tad Jones, 38, was driving near Charleston "
        "when he saw a large, metal sphere, about 6 m in diameter, having four "
        "legs equipped with wheels and a very small propeller underneath"
    )
    description = "Two min later it flew away."
    return {
        "canonical_input_id": target["canonical_input_id"],
        "canonical_input_ids": [target["canonical_input_id"]],
        "canonical_event_id": target["canonical_event_id"],
        "event_id": target["event_id"],
        "source_name": "majestic",
        "source_file": "majestic.csv",
        "source_row_number": target["source_row_number"],
        "source_native_id": target["source_native_id"],
        "source_row_hash": target["source_row_hash"],
        "source_provenance": [
            {
                "source_name": "majestic",
                "source_file": "majestic.csv",
                "source_row_number": target["source_row_number"],
                "source_native_id": target["source_native_id"],
                "source_row_hash": target["source_row_hash"],
                "canonical_input_id": target["canonical_input_id"],
            }
        ],
        "location_raw": location,
        "city": location,
        "state_province": None,
        "country": None,
        "lat": None,
        "lon": None,
        "coordinate_source": "unresolved",
        "location_precision": "city",
        "description": description,
        "summary": description,
        "raw_fields": {"location/0": location, "desc": description},
        "dedupe_strategy": "single_record",
        "duplicate_record_count": 1,
    }


def _napa_event() -> dict[str, object]:
    return {
        "canonical_input_id": NAPA_CANONICAL_INPUT_ID,
        "canonical_input_ids": [NAPA_CANONICAL_INPUT_ID],
        "canonical_event_id": NAPA_CANONICAL_EVENT_ID,
        "source_name": "majestic",
        "source_file": "majestic.csv",
        "source_row_number": 11264,
        "source_native_id": "Hatch_UDB_2481",
        "source_row_hash": NAPA_SOURCE_ROW_HASH,
        "source_provenance": [
            {
                "source_name": "majestic",
                "source_file": "majestic.csv",
                "source_row_number": 11264,
                "source_native_id": "Hatch_UDB_2481",
                "source_row_hash": NAPA_SOURCE_ROW_HASH,
                "canonical_input_id": NAPA_CANONICAL_INPUT_ID,
            }
        ],
        "date_raw": "7/27/1952",
        "date_iso": "1952-07-27",
        "sort_date_iso": "1952-07-27",
        "date_precision": "exact_day",
        "time_raw": "10:50",
        "location_raw": "Farmlands, NAPA VALLEY, CA, Colorado, USA",
        "city": "NAPA VALLEY, CA",
        "state_province": "Colorado",
        "country": "USA",
        "lat": 38.300002,
        "lon": -122.300006,
        "coordinate_source": "source_coordinates",
        "location_precision": "coordinate",
        "type_raw": "sighting",
        "type_normalized": "sighting",
        "shape_raw": (
            "NAPA Vly,CA:John Foraythe:MTLC DISK >>W/20K'alt:"
            "TILTS:LOST IN HAZE:NFD"
        ),
        "shape_normalized": "Disk",
        "duration_raw": "1",
        "summary": (
            "John Foraythe. Metallic disk going quickly west / 20K' altitude. "
            "Tilts. Lost in haze. No further details."
        ),
        "description": (
            "John Foraythe. Metallic disk going quickly west / 20K' altitude. "
            "Tilts. Lost in haze. No further details."
        ),
        "source_url": '<a href="timeline_part2.html#00388FC9">7/27/1952 #11262</a>',
        "raw_fields": dict(NAPA_EXPECTED_RAW_FIELDS),
        "raw_source_row": dict(NAPA_EXPECTED_RAW_FIELDS),
        "raw_source_row_values": list(NAPA_EXPECTED_RAW_FIELDS.values()),
        "dedupe_strategy": "single_record",
        "duplicate_record_count": 1,
    }


def _napa_input_record() -> CanonicalInputRecord:
    event = _napa_event()
    return CanonicalInputRecord(
        canonical_input_id=NAPA_CANONICAL_INPUT_ID,
        source_name="majestic",
        source_file="majestic.csv",
        source_row_number=11264,
        source_native_id="Hatch_UDB_2481",
        source_row_hash=NAPA_SOURCE_ROW_HASH,
        date_raw="7/27/1952",
        date_iso="1952-07-27",
        sort_date_iso="1952-07-27",
        date_precision="exact_day",
        time_raw="10:50",
        location_raw=str(event["location_raw"]),
        city="NAPA VALLEY, CA",
        state_province="Colorado",
        country="USA",
        lat=38.300002,
        lon=-122.300006,
        coordinate_source="source_coordinates",
        location_precision="coordinate",
        shape_raw=str(event["shape_raw"]),
        shape_normalized="Disk",
        type_raw="sighting",
        type_normalized="sighting",
        duration_raw="1",
        description=str(event["description"]),
        summary=str(event["summary"]),
        source_url=str(event["source_url"]),
        raw_fields=dict(NAPA_EXPECTED_RAW_FIELDS),
        raw_source_row=dict(NAPA_EXPECTED_RAW_FIELDS),
        raw_source_row_values=list(NAPA_EXPECTED_RAW_FIELDS.values()),
    )


def _read_binary_rows(path: Path, metadata: dict, row_struct: struct.Struct):
    rows = []
    for unpacked in row_struct.iter_unpack(path.read_bytes()):
        row = {}
        for field, value in zip(metadata["fields"], unpacked):
            lookup_table = field.get("lookup_table")
            if lookup_table:
                value = metadata["lookup_tables"][lookup_table][value]
            row[field["name"]] = value
        rows.append(row)
    return rows


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))
