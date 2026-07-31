import csv
import json

from scripts.review_manual_review_medium_body_text_only import (
    BODY_VARIANT_REVIEW_CANDIDATE,
    NEEDS_DEEPER_BODY_REVIEW,
    build_medium_body_text_only_review,
)


def test_medium_body_text_review_classifies_minor_same_native_variant(tmp_path):
    audit_csv = tmp_path / "audit.csv"
    source_events = tmp_path / "events.jsonl"
    _write_audit_csv(audit_csv, [_row("evt_minor", "evt_a|evt_b")])
    _write_jsonl(
        source_events,
        [
            _event("evt_a", "ufocat2023.csv", "100", "Objects changed colors as they moved."),
            _event("evt_b", "ufocat2023.csv", "100", "Objects changed color as they moved."),
        ],
    )

    report = build_medium_body_text_only_review(audit_csv_path=audit_csv, source_events_path=source_events)
    item = report["items"][0]

    assert report["summary"]["target_medium_body_text_only_count"] == 1
    assert item["review_recommendation"] == BODY_VARIANT_REVIEW_CANDIDATE
    assert item["body_subcategory"] == "minor_body_wording_variant"
    assert report["decisions_created"] is False
    assert report["ready_for_runtime_promotion"] is False


def test_medium_body_text_review_rejects_substantive_text_variance(tmp_path):
    audit_csv = tmp_path / "audit.csv"
    source_events = tmp_path / "events.jsonl"
    _write_audit_csv(audit_csv, [_row("evt_substantive", "evt_a|evt_b")])
    _write_jsonl(
        source_events,
        [
            _event("evt_a", "ufocat2023.csv", "100", "A bright disc hovered silently over the road."),
            _event("evt_b", "ufocat2023.csv", "100", "A triangular craft landed and occupants exited."),
        ],
    )

    report = build_medium_body_text_only_review(audit_csv_path=audit_csv, source_events_path=source_events)
    item = report["items"][0]

    assert item["review_recommendation"] == NEEDS_DEEPER_BODY_REVIEW
    assert item["body_subcategory"] == "substantive_body_text_variance"
    assert "minor_body_text_similarity" in item["failed_conditions"]


def test_medium_body_text_review_requires_single_source_native_identity(tmp_path):
    audit_csv = tmp_path / "audit.csv"
    source_events = tmp_path / "events.jsonl"
    _write_audit_csv(audit_csv, [_row("evt_native", "evt_a|evt_b")])
    _write_jsonl(
        source_events,
        [
            _event("evt_a", "ufocat2023.csv", "100", "Objects changed colors as they moved."),
            _event("evt_b", "ufocat2023.csv", "101", "Objects changed color as they moved."),
        ],
    )

    report = build_medium_body_text_only_review(audit_csv_path=audit_csv, source_events_path=source_events)
    item = report["items"][0]

    assert item["review_recommendation"] == NEEDS_DEEPER_BODY_REVIEW
    assert "single_source_native_identity" in item["failed_conditions"]


def _row(event_id, component_event_ids):
    component_count = len(component_event_ids.split("|"))
    return {
        "replacement_event_id": event_id,
        "risk_level": "medium",
        "risk_flags": "description_text_conflict|summary_text_conflict",
        "conflict_field_count": 2,
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


def _event(event_id, source_file, native_id, description):
    return {
        "canonical_event_id": event_id,
        "source_file": source_file,
        "source_native_id": native_id,
        "summary": description,
        "description": description,
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
