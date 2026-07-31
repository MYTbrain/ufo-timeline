import csv
import json

from scripts.review_manual_review_medium_identity_mixed import (
    NEEDS_DEEPER_IDENTITY_MIXED_REVIEW,
    build_medium_identity_mixed_review,
)


def test_medium_identity_mixed_review_targets_non_coordinate_mixed_identity(tmp_path):
    audit_csv = tmp_path / "audit.csv"
    source_events = tmp_path / "events.jsonl"
    _write_audit_csv(
        audit_csv,
        [
            _row(
                "evt_body",
                "description_text_conflict|summary_text_conflict|same_source_multiple_native_ids",
                "evt_a|evt_b",
            ),
            _row("evt_identity_time_only", "time_raw_conflict|same_source_multiple_native_ids", "evt_c|evt_d"),
            _row("evt_coordinate", "coordinate_span_gt_5km|same_source_multiple_native_ids", "evt_e|evt_f"),
        ],
    )
    _write_jsonl(
        source_events,
        [
            _event("evt_a", "ufocat2023.csv", "100"),
            _event("evt_b", "ufocat2023.csv", "101"),
        ],
    )

    report = build_medium_identity_mixed_review(audit_csv_path=audit_csv, source_events_path=source_events)
    item = report["items"][0]

    assert report["summary"]["target_medium_identity_mixed_count"] == 1
    assert item["review_recommendation"] == NEEDS_DEEPER_IDENTITY_MIXED_REVIEW
    assert item["identity_mixed_subcategory"] == "identity_plus_body_text_conflict"
    assert item["native_id_profile"][0]["native_id_count"] == 2
    assert report["decisions_created"] is False


def test_medium_identity_mixed_review_classifies_classification_conflict(tmp_path):
    audit_csv = tmp_path / "audit.csv"
    source_events = tmp_path / "events.jsonl"
    _write_audit_csv(
        audit_csv,
        [_row("evt_type", "time_raw_conflict|type_conflict|same_source_multiple_native_ids", "evt_a|evt_b")],
    )
    _write_jsonl(
        source_events,
        [
            _event("evt_a", "ufocat2023.csv", "100"),
            _event("evt_b", "ufocat2023.csv", "101"),
        ],
    )

    report = build_medium_identity_mixed_review(audit_csv_path=audit_csv, source_events_path=source_events)
    item = report["items"][0]

    assert item["identity_mixed_subcategory"] == "identity_plus_classification_conflict"
    assert "no_classification_or_location_conflict" in item["failed_conditions"]


def _row(event_id, flags, component_event_ids):
    component_count = len(component_event_ids.split("|"))
    return {
        "replacement_event_id": event_id,
        "risk_level": "medium",
        "risk_flags": flags,
        "conflict_field_count": len(flags.split("|")),
        "component_event_count": component_count,
        "canonical_input_id_count": component_count,
        "coordinate_span_km": 0,
        "date_iso_values": "1954-09-19",
        "time_raw_values": "1600",
        "location_raw_values": "Rongeres, FRA",
        "country_values": "FRA",
        "shape_values": "disc",
        "type_values": "3l",
        "source_file_values": "ufocat2023.csv",
        "description_variant_count": 2,
        "summary_variant_count": 2,
        "component_event_ids": component_event_ids,
    }


def _event(event_id, source_file, native_id):
    return {
        "canonical_event_id": event_id,
        "source_file": source_file,
        "source_native_id": native_id,
        "source_row_number": event_id,
        "time_raw": "1600",
        "type_normalized": "3l",
        "location_raw": "Rongeres, FRA",
        "summary": "summary",
        "description": "description",
    }


def _write_audit_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
