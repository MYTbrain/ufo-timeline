import csv

from scripts.summarize_manual_review_replacement_audit_sublanes import (
    summarize_manual_review_replacement_audit_sublanes,
)


def test_sublane_summary_classifies_medium_and_high_lanes(tmp_path):
    audit_csv = tmp_path / "audit.csv"
    _write_audit_csv(
        audit_csv,
        [
            _row("evt_low", "low", "", 2),
            _row("evt_time", "medium", "time_raw_conflict", 3),
            _row("evt_coord", "medium", "coordinate_span_gt_5km|time_raw_conflict", 2),
            _row("evt_high", "high", "coordinate_span_gt_50km|time_raw_conflict", 2),
        ],
    )

    report, rows = summarize_manual_review_replacement_audit_sublanes(audit_csv_path=audit_csv)
    by_lane = {row["sublane"]: row for row in rows}

    assert report["audit_rows_read"] == 4
    assert by_lane["accepted_low_risk_preview_lane"]["projected_event_reduction"] == 1
    assert by_lane["medium_time_raw_only"]["component_count"] == 1
    assert by_lane["medium_time_raw_only"]["projected_event_reduction"] == 2
    assert by_lane["medium_coordinate_span_gt_5km"]["component_count"] == 1
    assert by_lane["high_coordinate_span_gt_50km"]["component_count"] == 1


def _row(event_id, risk, flags, component_count):
    return {
        "replacement_event_id": event_id,
        "risk_level": risk,
        "risk_flags": flags,
        "conflict_field_count": 1,
        "component_event_count": component_count,
        "canonical_input_id_count": component_count,
        "coordinate_span_km": 0,
        "date_iso_values": "1954-09-19",
        "time_raw_values": "1630",
        "location_raw_values": "Rongeres, FRA",
        "country_values": "FRA",
        "shape_values": "disc",
        "type_values": "3l",
        "source_file_values": "ufocat2023.csv",
        "description_variant_count": 1,
        "summary_variant_count": 1,
        "component_event_ids": event_id,
    }


def _write_audit_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
