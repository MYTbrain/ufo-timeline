from __future__ import annotations

import json
from pathlib import Path

from scripts.rehydrate_max_dedupe_coordinates import rehydrate_max_dedupe_coordinates


def test_rehydrates_unmapped_deduped_event_from_duplicate_member_coordinate(tmp_path: Path) -> None:
    max_path = tmp_path / "max" / "deduped_events.jsonl"
    web_root = tmp_path / "web"
    output_dir = tmp_path / "out"
    max_path.parent.mkdir()
    (web_root / "event_chunks").mkdir(parents=True)

    _write_jsonl(
        max_path,
        [
            {
                "canonical_event_id": "evt_merged",
                "canonical_input_ids": ["cin_a", "cin_b"],
                "source_name": "ufocat",
                "source_file": "ufocat2023.csv",
                "source_row_number": 10,
                "source_native_id": "123",
                "location_raw": "FARGO, Cass, ND, US",
                "lat": None,
                "lon": None,
                "coordinate_source": "unresolved",
                "location_precision": "unknown",
            }
        ],
    )
    _write_json(
        web_root / "event_chunks" / "chunk_000000.json",
        [
            {
                "event_id": 101,
                "canonical_event_id": "evt_served",
                "canonical_input_ids": ["cin_b"],
                "source": "ufocat",
                "source_id": "123",
                "source_provenance": [
                    {
                        "source_name": "ufocat",
                        "source_file": "ufocat2023.csv",
                        "source_row_number": 11,
                        "source_native_id": "123",
                        "source_row_hash": "hash-b",
                        "canonical_input_id": "cin_b",
                    }
                ],
                "lat": 46.8772,
                "lon": -96.7898,
                "coordinate_source": "geocoded",
                "location_precision": "city",
                "geocode_query_used": "Fargo, ND, US",
                "geocode_confidence": 0.9,
                "city": "Fargo",
                "state_province": "ND",
                "country": "US",
            }
        ],
    )

    report = rehydrate_max_dedupe_coordinates(
        max_dedupe_path=max_path,
        served_web_dir=web_root,
        output_dir=output_dir,
        report_output=tmp_path / "report.json",
        copy_supporting_files=False,
    )

    rows = _read_jsonl(output_dir / "deduped_events.jsonl")
    assert rows[0]["lat"] == 46.8772
    assert rows[0]["lon"] == -96.7898
    assert rows[0]["coordinate_source"] == "geocoded"
    assert rows[0]["coordinate_rehydration_match_kind"] == "canonical_input_id"
    assert rows[0]["state_province"] == "ND"
    assert report["counts"]["mapped_after"] == 1
    assert report["counts"]["coordinate_changed"] == 1


def test_leaves_unmapped_event_when_no_served_coordinate_match(tmp_path: Path) -> None:
    max_path = tmp_path / "max" / "deduped_events.jsonl"
    web_root = tmp_path / "web"
    output_dir = tmp_path / "out"
    max_path.parent.mkdir()
    (web_root / "event_chunks").mkdir(parents=True)

    _write_jsonl(
        max_path,
        [
            {
                "canonical_event_id": "evt_unmapped",
                "canonical_input_ids": ["cin_missing"],
                "source_name": "nuforc",
                "lat": None,
                "lon": None,
                "coordinate_source": "unresolved",
                "location_precision": "unknown",
            }
        ],
    )
    _write_json(web_root / "event_chunks" / "chunk_000000.json", [])

    report = rehydrate_max_dedupe_coordinates(
        max_dedupe_path=max_path,
        served_web_dir=web_root,
        output_dir=output_dir,
        report_output=tmp_path / "report.json",
        copy_supporting_files=False,
    )

    rows = _read_jsonl(output_dir / "deduped_events.jsonl")
    assert rows[0]["lat"] is None
    assert rows[0]["coordinate_source"] == "unresolved"
    assert report["counts"]["mapped_after"] == 0
    assert report["unmapped_no_match_source_counts"] == {"nuforc": 1}


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
