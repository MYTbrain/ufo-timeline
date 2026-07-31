import csv
import json

from scripts.review_manual_review_medium_classification_only import (
    CLASSIFICATION_VARIANT_REVIEW_CANDIDATE,
    NEEDS_DEEPER_CLASSIFICATION_REVIEW,
    build_medium_classification_only_review,
)


def test_medium_classification_review_classifies_minor_code_variant(tmp_path):
    audit_csv = tmp_path / "audit.csv"
    source_events = tmp_path / "events.jsonl"
    _write_audit_csv(audit_csv, [_row("evt_minor", "7ntts|7ntt", "evt_a|evt_b")])
    _write_jsonl(
        source_events,
        [
            _event("evt_a", "ufocat2023.csv", "100", "7ntts"),
            _event("evt_b", "ufocat2023.csv", "100", "7ntt"),
        ],
    )

    report = build_medium_classification_only_review(audit_csv_path=audit_csv, source_events_path=source_events)
    item = report["items"][0]

    assert report["summary"]["target_medium_classification_only_count"] == 1
    assert item["review_recommendation"] == CLASSIFICATION_VARIANT_REVIEW_CANDIDATE
    assert item["classification_subcategory"] == "minor_type_code_variant"
    assert report["decisions_created"] is False


def test_medium_classification_review_rejects_different_major_type(tmp_path):
    audit_csv = tmp_path / "audit.csv"
    source_events = tmp_path / "events.jsonl"
    _write_audit_csv(audit_csv, [_row("evt_substantive", "4|5", "evt_a|evt_b")])
    _write_jsonl(
        source_events,
        [
            _event("evt_a", "ufocat2023.csv", "100", "4"),
            _event("evt_b", "ufocat2023.csv", "100", "5"),
        ],
    )

    report = build_medium_classification_only_review(audit_csv_path=audit_csv, source_events_path=source_events)
    item = report["items"][0]

    assert item["review_recommendation"] == NEEDS_DEEPER_CLASSIFICATION_REVIEW
    assert item["classification_subcategory"] == "substantive_type_category_variance"
    assert "minor_type_code_variant" in item["failed_conditions"]


def test_medium_classification_review_requires_single_source_native_identity(tmp_path):
    audit_csv = tmp_path / "audit.csv"
    source_events = tmp_path / "events.jsonl"
    _write_audit_csv(audit_csv, [_row("evt_native", "7ntts|7ntt", "evt_a|evt_b")])
    _write_jsonl(
        source_events,
        [
            _event("evt_a", "ufocat2023.csv", "100", "7ntts"),
            _event("evt_b", "ufocat2023.csv", "101", "7ntt"),
        ],
    )

    report = build_medium_classification_only_review(audit_csv_path=audit_csv, source_events_path=source_events)
    item = report["items"][0]

    assert item["review_recommendation"] == NEEDS_DEEPER_CLASSIFICATION_REVIEW
    assert "single_source_native_identity" in item["failed_conditions"]


def _row(event_id, type_values, component_event_ids):
    component_count = len(component_event_ids.split("|"))
    return {
        "replacement_event_id": event_id,
        "risk_level": "medium",
        "risk_flags": "type_conflict",
        "conflict_field_count": 1,
        "component_event_count": component_count,
        "canonical_input_id_count": component_count,
        "coordinate_span_km": 0,
        "date_iso_values": "1954-09-19",
        "time_raw_values": "1600",
        "location_raw_values": "Rongeres, FRA",
        "country_values": "FRA",
        "shape_values": "disc",
        "type_values": type_values,
        "source_file_values": "ufocat2023.csv",
        "description_variant_count": 1,
        "summary_variant_count": 1,
        "component_event_ids": component_event_ids,
    }


def _event(event_id, source_file, native_id, type_normalized):
    return {
        "canonical_event_id": event_id,
        "source_file": source_file,
        "source_native_id": native_id,
        "type_normalized": type_normalized,
        "type_raw": type_normalized,
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
