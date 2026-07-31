import csv

from scripts.review_manual_review_medium_classification_mixed import (
    NEEDS_DEEPER_CLASSIFICATION_MIXED_REVIEW,
    build_medium_classification_mixed_review,
)


def test_medium_classification_mixed_targets_time_type_conflict(tmp_path):
    audit_csv = tmp_path / "audit.csv"
    _write_audit_csv(
        audit_csv,
        [
            _row("evt_mixed", "time_raw_conflict|type_conflict", "disc", "7nmd|7_md"),
            _row("evt_type_only", "type_conflict", "disc", "7nmd|7_md"),
            _row("evt_body_type", "description_text_conflict|type_conflict", "disc", "7nmd|7_md"),
        ],
    )

    report = build_medium_classification_mixed_review(audit_csv_path=audit_csv)
    item = report["items"][0]

    assert report["summary"]["target_medium_classification_mixed_count"] == 1
    assert item["review_recommendation"] == NEEDS_DEEPER_CLASSIFICATION_MIXED_REVIEW
    assert item["classification_mixed_subcategory"] == "minor_type_code_with_time_conflict"
    assert report["decisions_created"] is False


def test_medium_classification_mixed_classifies_shape_conflict(tmp_path):
    audit_csv = tmp_path / "audit.csv"
    _write_audit_csv(audit_csv, [_row("evt_shape", "time_raw_conflict|shape_conflict", "disc|sphere", "4c")])

    report = build_medium_classification_mixed_review(audit_csv_path=audit_csv)
    item = report["items"][0]

    assert item["classification_mixed_subcategory"] == "shape_with_time_conflict"


def _row(event_id, flags, shape_values, type_values):
    return {
        "replacement_event_id": event_id,
        "risk_level": "medium",
        "risk_flags": flags,
        "conflict_field_count": len(flags.split("|")),
        "component_event_count": 2,
        "canonical_input_id_count": 2,
        "coordinate_span_km": 0,
        "date_iso_values": "1954-09-19",
        "time_raw_values": "1600|1605",
        "location_raw_values": "Rongeres, FRA",
        "country_values": "FRA",
        "shape_values": shape_values,
        "type_values": type_values,
        "source_file_values": "ufocat2023.csv",
        "description_variant_count": 1,
        "summary_variant_count": 1,
        "component_event_ids": "evt_a|evt_b",
    }


def _write_audit_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
