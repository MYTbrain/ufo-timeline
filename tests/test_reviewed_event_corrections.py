from __future__ import annotations

import json
from pathlib import Path

import pytest

from parser.canonical_export import canonical_event_to_normalized_event
from parser.reviewed_event_corrections import (
    NAPA_CANONICAL_EVENT_ID,
    NAPA_CANONICAL_INPUT_ID,
    NAPA_CORRECTION_ID,
    NAPA_EVENT_ID,
    NAPA_EXPECTED_RAW_FIELDS,
    NAPA_SOURCE_ROW_HASH,
    apply_reviewed_event_corrections,
)
from parser.utils import write_jsonl
from scripts.build_canonical_web_artifacts import build_canonical_web_artifacts


def test_napa_reviewed_correction_updates_projection_and_preserves_raw_source() -> None:
    original = _napa_event()

    corrected = apply_reviewed_event_corrections(original)

    assert corrected["canonical_event_id"] == NAPA_CANONICAL_EVENT_ID
    assert corrected["canonical_input_ids"] == [NAPA_CANONICAL_INPUT_ID]
    assert corrected["time_raw"] == "10:45"
    assert corrected["location_raw"] == (
        "Napa Valley near Napa, Napa County, California, USA"
    )
    assert corrected["city"] == "Napa"
    assert corrected["state_province"] == "California"
    assert corrected["country"] == "USA"
    assert corrected["lat"] == 38.300002
    assert corrected["lon"] == -122.300006
    assert corrected["location_precision"] == "city"
    assert corrected["duration_raw"] is None
    assert corrected["raw_fields"] == original["raw_fields"]
    assert corrected["raw_fields"]["key_vals/State/Prov"] == "Colorado"
    assert corrected["raw_fields"]["key_vals/Locale"] == "Farmlands"
    assert corrected["raw_fields"]["time"] == "10:50"
    assert corrected["raw_fields"]["key_vals/Duration"] == "1"
    assert corrected["reviewed_corrections"][0]["correction_id"] == NAPA_CORRECTION_ID


def test_napa_reviewed_correction_fails_closed_if_source_guard_changes() -> None:
    stale = _napa_event()
    stale["raw_fields"]["key_vals/State/Prov"] = "California"

    with pytest.raises(ValueError, match="stale-source guard"):
        apply_reviewed_event_corrections(stale)


def test_napa_mapping_note_and_evidence_survive_normalized_export() -> None:
    corrected = apply_reviewed_event_corrections(_napa_event())

    normalized = canonical_event_to_normalized_event(corrected)

    assert normalized["event_id"] == NAPA_EVENT_ID
    assert normalized["location_raw"] == corrected["location_raw"]
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
    assert detail["time_raw"] == "10:45"
    assert detail["parsed_time_local_minutes"] == 645.0
    assert detail["location_raw"] == (
        "Napa Valley near Napa, Napa County, California, USA"
    )
    assert detail["state_province"] == "California"
    assert detail["location_precision"] == "city"
    assert detail["lat"] == 38.300002
    assert detail["lon"] == -122.300006
    assert "duration_raw" not in detail
    assert detail["raw_fields"]["key_vals/State/Prov"] == "Colorado"
    assert detail["raw_fields"]["key_vals/Duration"] == "1"
    assert detail["reviewed_corrections"][0]["correction_id"] == NAPA_CORRECTION_ID
    assert "Original Hatch values remain preserved" in detail["mapping_notes"]
    assert "Time: 10:45" in detail["raw_event_block"]
    assert "key_vals/State/Prov: Colorado" in detail["raw_event_block"]

    assert summary["event_id"] == NAPA_EVENT_ID
    assert summary["time_raw"] == "10:45"
    assert summary["location_raw"] == detail["location_raw"]
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
        "raw_fields": dict(NAPA_EXPECTED_RAW_FIELDS),
        "raw_source_row": dict(NAPA_EXPECTED_RAW_FIELDS),
        "raw_source_row_values": list(NAPA_EXPECTED_RAW_FIELDS.values()),
        "dedupe_strategy": "single_record",
        "duplicate_record_count": 1,
    }


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))
