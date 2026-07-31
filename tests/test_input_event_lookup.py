import json

from scripts.build_input_event_lookup import build_input_event_lookup


def _write_jsonl(path, records):
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_build_input_event_lookup_writes_compact_mapping_and_report(tmp_path):
    deduped_events = tmp_path / "deduped_events.jsonl"
    lookup = tmp_path / "input_event_lookup.jsonl"
    report_path = tmp_path / "input_event_lookup_report.json"
    _write_jsonl(
        deduped_events,
        [
            {"canonical_event_id": "evt_a", "canonical_input_ids": ["cin_a", "cin_b"]},
            {"canonical_event_id": "evt_c", "canonical_input_ids": ["cin_c"]},
        ],
    )

    report = build_input_event_lookup(
        deduped_events_path=deduped_events,
        lookup_output_path=lookup,
        report_output_path=report_path,
    )

    assert _read_jsonl(lookup) == [
        {"canonical_input_id": "cin_a", "canonical_event_id": "evt_a"},
        {"canonical_input_id": "cin_b", "canonical_event_id": "evt_a"},
        {"canonical_input_id": "cin_c", "canonical_event_id": "evt_c"},
    ]
    assert report["canonical_outputs_mutated"] is False
    assert report["summary"]["event_count"] == 2
    assert report["summary"]["source_record_count_from_events"] == 3
    assert report["summary"]["lookup_row_count"] == 3
    assert report["summary"]["exact_duplicate_record_reduction"] == 1
    assert json.loads(report_path.read_text(encoding="utf-8"))["summary"]["lookup_complete"] is True


def test_build_input_event_lookup_reports_duplicate_and_conflicting_input_ids(tmp_path):
    deduped_events = tmp_path / "deduped_events.jsonl"
    lookup = tmp_path / "input_event_lookup.jsonl"
    report_path = tmp_path / "input_event_lookup_report.json"
    _write_jsonl(
        deduped_events,
        [
            {"canonical_event_id": "evt_a", "canonical_input_ids": ["cin_a"]},
            {"canonical_event_id": "evt_b", "canonical_input_ids": ["cin_a"]},
            {"canonical_event_id": "evt_b", "canonical_input_ids": ["cin_b"]},
        ],
    )

    report = build_input_event_lookup(
        deduped_events_path=deduped_events,
        lookup_output_path=lookup,
        report_output_path=report_path,
    )

    assert _read_jsonl(lookup) == [
        {"canonical_input_id": "cin_a", "canonical_event_id": "evt_a"},
        {"canonical_input_id": "cin_b", "canonical_event_id": "evt_b"},
    ]
    assert report["summary"]["duplicate_input_id_count"] == 1
    assert report["summary"]["conflicting_input_id_count"] == 1
    assert report["samples"]["conflicting_input_ids"][0]["canonical_input_id"] == "cin_a"


def test_build_input_event_lookup_limit_marks_lookup_incomplete(tmp_path):
    deduped_events = tmp_path / "deduped_events.jsonl"
    lookup = tmp_path / "input_event_lookup.jsonl"
    report_path = tmp_path / "input_event_lookup_report.json"
    _write_jsonl(
        deduped_events,
        [
            {"canonical_event_id": "evt_a", "canonical_input_ids": ["cin_a"]},
            {"canonical_event_id": "evt_b", "canonical_input_ids": ["cin_b"]},
        ],
    )

    report = build_input_event_lookup(
        deduped_events_path=deduped_events,
        lookup_output_path=lookup,
        report_output_path=report_path,
        limit=1,
    )

    assert _read_jsonl(lookup) == [{"canonical_input_id": "cin_a", "canonical_event_id": "evt_a"}]
    assert report["summary"]["lookup_complete"] is False
