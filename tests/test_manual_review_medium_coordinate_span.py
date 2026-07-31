import csv
import json

from scripts.review_manual_review_medium_coordinate_span import (
    COORDINATE_REVIEW_CANDIDATE,
    NEEDS_DEEPER_COORDINATE_REVIEW,
    build_medium_coordinate_span_review,
)


def test_medium_coordinate_span_review_classifies_local_single_native_candidate(tmp_path):
    audit_csv = tmp_path / "audit.csv"
    source_events = tmp_path / "events.jsonl"
    _write_audit_csv(audit_csv, [_row("evt_local", "coordinate_span_gt_5km", "6.5", "evt_a|evt_b")])
    _write_jsonl(
        source_events,
        [
            _event("evt_a", "ufocat2023.csv", "100", 46.0, 3.0),
            _event("evt_b", "ufocat2023.csv", "100", 46.05, 3.0),
        ],
    )

    report = build_medium_coordinate_span_review(audit_csv_path=audit_csv, source_events_path=source_events)
    item = report["items"][0]

    assert report["summary"]["target_medium_coordinate_span_count"] == 1
    assert item["review_recommendation"] == COORDINATE_REVIEW_CANDIDATE
    assert item["coordinate_subcategory"] == "local_coordinate_variance_5_to_10km"
    assert report["decisions_created"] is False


def test_medium_coordinate_span_review_rejects_broad_span(tmp_path):
    audit_csv = tmp_path / "audit.csv"
    source_events = tmp_path / "events.jsonl"
    _write_audit_csv(audit_csv, [_row("evt_broad", "coordinate_span_gt_5km", "44.0", "evt_a|evt_b")])
    _write_jsonl(
        source_events,
        [
            _event("evt_a", "ufocat2023.csv", "100", 46.0, 3.0),
            _event("evt_b", "ufocat2023.csv", "100", 46.4, 3.0),
        ],
    )

    report = build_medium_coordinate_span_review(audit_csv_path=audit_csv, source_events_path=source_events)
    item = report["items"][0]

    assert item["review_recommendation"] == NEEDS_DEEPER_COORDINATE_REVIEW
    assert item["coordinate_subcategory"] == "broad_coordinate_variance_25_to_50km"
    assert "local_coordinate_span_under_10km" in item["failed_conditions"]


def test_medium_coordinate_span_review_rejects_secondary_conflicts(tmp_path):
    audit_csv = tmp_path / "audit.csv"
    source_events = tmp_path / "events.jsonl"
    _write_audit_csv(
        audit_csv,
        [_row("evt_secondary", "coordinate_span_gt_5km|description_text_conflict", "6.5", "evt_a|evt_b")],
    )
    _write_jsonl(
        source_events,
        [
            _event("evt_a", "ufocat2023.csv", "100", 46.0, 3.0),
            _event("evt_b", "ufocat2023.csv", "100", 46.05, 3.0),
        ],
    )

    report = build_medium_coordinate_span_review(audit_csv_path=audit_csv, source_events_path=source_events)
    item = report["items"][0]

    assert item["review_recommendation"] == NEEDS_DEEPER_COORDINATE_REVIEW
    assert "no_secondary_non_time_conflicts" in item["failed_conditions"]


def _row(event_id, flags, span, component_event_ids):
    component_count = len(component_event_ids.split("|"))
    return {
        "replacement_event_id": event_id,
        "risk_level": "medium",
        "risk_flags": flags,
        "conflict_field_count": len(flags.split("|")),
        "component_event_count": component_count,
        "canonical_input_id_count": component_count,
        "coordinate_span_km": span,
        "date_iso_values": "1954-09-19",
        "time_raw_values": "1600",
        "location_raw_values": "Rongeres, FRA",
        "country_values": "FRA",
        "shape_values": "disc",
        "type_values": "3l",
        "source_file_values": "ufocat2023.csv",
        "description_variant_count": 1,
        "summary_variant_count": 1,
        "component_event_ids": component_event_ids,
    }


def _event(event_id, source_file, native_id, lat, lon):
    return {
        "canonical_event_id": event_id,
        "source_file": source_file,
        "source_native_id": native_id,
        "source_row_number": event_id,
        "lat": lat,
        "lon": lon,
        "coordinate_source": "source_coordinates",
        "location_raw": "Rongeres, FRA",
        "time_raw": "1600",
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
