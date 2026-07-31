import csv

from scripts.review_manual_review_medium_body_text_mixed import (
    NEEDS_DEEPER_BODY_MIXED_REVIEW,
    build_medium_body_text_mixed_review,
)


def test_medium_body_text_mixed_targets_body_plus_location_or_type(tmp_path):
    audit_csv = tmp_path / "audit.csv"
    _write_audit_csv(
        audit_csv,
        [
            _row("evt_body_location", "description_text_conflict|summary_text_conflict|location_text_conflict"),
            _row("evt_body_only", "description_text_conflict|summary_text_conflict"),
            _row("evt_identity", "description_text_conflict|same_source_multiple_native_ids"),
            _row("evt_coordinate", "description_text_conflict|coordinate_span_gt_5km"),
        ],
    )

    report = build_medium_body_text_mixed_review(audit_csv_path=audit_csv)
    item = report["items"][0]

    assert report["summary"]["target_medium_body_text_mixed_count"] == 1
    assert item["review_recommendation"] == NEEDS_DEEPER_BODY_MIXED_REVIEW
    assert item["body_mixed_subcategory"] == "body_location_time_mixed"
    assert report["decisions_created"] is False


def test_medium_body_text_mixed_classifies_location_classification_mix(tmp_path):
    audit_csv = tmp_path / "audit.csv"
    _write_audit_csv(
        audit_csv,
        [
            _row(
                "evt_full",
                "time_raw_conflict|location_text_conflict|type_conflict|description_text_conflict|summary_text_conflict",
            )
        ],
    )

    report = build_medium_body_text_mixed_review(audit_csv_path=audit_csv)
    item = report["items"][0]

    assert item["body_mixed_subcategory"] == "body_location_classification_time_mixed"


def _row(event_id, flags):
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
        "location_raw_values": "Rongeres, FRA|Rongeres France",
        "country_values": "FRA",
        "shape_values": "disc",
        "type_values": "3l|4",
        "source_file_values": "ufocat2023.csv|mufonpy.csv",
        "description_variant_count": 2,
        "summary_variant_count": 2,
        "component_event_ids": "evt_a|evt_b",
    }


def _write_audit_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
