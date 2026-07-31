import csv

from scripts.review_manual_review_high_coordinate_span import (
    NEEDS_DEEPER_HIGH_COORDINATE_REVIEW,
    build_high_coordinate_span_review,
)


def test_high_coordinate_span_review_targets_high_coordinate_rows(tmp_path):
    audit_csv = tmp_path / "audit.csv"
    _write_audit_csv(
        audit_csv,
        [
            _row("evt_high", "high", "coordinate_span_gt_50km", "120"),
            _row("evt_medium", "medium", "coordinate_span_gt_5km", "12"),
        ],
    )

    report = build_high_coordinate_span_review(audit_csv_path=audit_csv)
    item = report["items"][0]

    assert report["summary"]["target_high_coordinate_span_count"] == 1
    assert item["review_recommendation"] == NEEDS_DEEPER_HIGH_COORDINATE_REVIEW
    assert item["coordinate_subcategory"] == "severe_coordinate_variance_100_to_500km"
    assert report["decisions_created"] is False


def test_high_coordinate_span_review_classifies_extreme_span(tmp_path):
    audit_csv = tmp_path / "audit.csv"
    _write_audit_csv(audit_csv, [_row("evt_extreme", "high", "coordinate_span_gt_50km", "700")])

    report = build_high_coordinate_span_review(audit_csv_path=audit_csv)
    item = report["items"][0]

    assert item["coordinate_subcategory"] == "extreme_coordinate_variance_over_500km"


def _row(event_id, risk, flags, span):
    return {
        "replacement_event_id": event_id,
        "risk_level": risk,
        "risk_flags": flags,
        "conflict_field_count": len(flags.split("|")),
        "component_event_count": 2,
        "canonical_input_id_count": 2,
        "coordinate_span_km": span,
        "date_iso_values": "1954-09-19",
        "time_raw_values": "1600|1700",
        "location_raw_values": "Rongeres, FRA",
        "country_values": "FRA",
        "shape_values": "disc",
        "type_values": "3l",
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
