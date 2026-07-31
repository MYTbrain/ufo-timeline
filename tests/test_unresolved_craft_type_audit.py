import json
from pathlib import Path

from scripts.audit_unresolved_craft_type_by_source import audit


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_unresolved_audit_separates_recovered_and_still_unknown(tmp_path: Path):
    input_path = tmp_path / "events.jsonl"
    write_jsonl(input_path, [
        {
            "canonical_event_id": "evt_recovered",
            "source_name": "ufocat",
            "date_iso": "1954-09-01",
            "location_raw": "A, US",
            "type_raw": "Unknown",
            "shape_raw": "Unknown",
            "description": "Witness described a triangular craft.",
        },
        {
            "canonical_event_id": "evt_unresolved",
            "source_name": "ufocat",
            "date_iso": "1954-09-02",
            "location_raw": "B, US",
            "type_raw": "Unknown",
            "shape_raw": "Unknown",
            "description": "Witness saw something unusual.",
        },
        {
            "canonical_event_id": "evt_prosaic",
            "source_name": "mufon",
            "date_iso": "2001-01-01",
            "location_raw": "C, US",
            "type_raw": "Unknown",
            "shape_raw": "Unknown",
            "description": "Probably a plane, but the witness filed a report.",
        },
        {
            "canonical_event_id": "evt_known",
            "source_name": "mufon",
            "date_iso": "2001-01-02",
            "location_raw": "D, US",
            "type_raw": "Disk",
            "shape_raw": "Disk",
            "description": "Disk-shaped object.",
        },
    ])

    report = audit(input_path)

    assert report["summary"]["events_scanned"] == 4
    assert report["summary"]["app_unknown_events"] == 3
    assert report["summary"]["app_unknown_recovered_events"] == 1
    assert report["summary"]["app_unknown_still_unresolved_events"] == 2
    assert report["summary"]["prosaic_cue_events_in_still_unresolved"] == 1

    by_source = {
        row["source_name"]: row
        for row in report["sources_by_remaining_unknown"]
    }
    assert by_source["ufocat"]["app_unknown_recovered_events"] == 1
    assert by_source["ufocat"]["app_unknown_still_unresolved_events"] == 1
    assert by_source["mufon"]["app_unknown_still_unresolved_events"] == 1
