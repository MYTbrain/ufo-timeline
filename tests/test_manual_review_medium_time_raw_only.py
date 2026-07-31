import csv

from scripts.review_manual_review_medium_time_raw_only import (
    NEEDS_MORE_EVIDENCE,
    SOURCE_REVIEW_SAME_EVENT,
    build_medium_time_raw_only_review,
)


def test_medium_time_raw_only_review_recommends_nearby_exact_times(tmp_path):
    audit_csv = tmp_path / "audit.csv"
    _write_audit_csv(
        audit_csv,
        [
            _row("evt_near", "medium", "time_raw_conflict", "2015|2020", 2),
            _row("evt_far", "medium", "time_raw_conflict", "1200|1400", 2),
            _row("evt_low", "low", "", "1200", 2),
            _row("evt_context", "medium", "time_raw_conflict", "Even|2020", 2),
        ],
    )

    report = build_medium_time_raw_only_review(audit_csv_path=audit_csv)
    by_id = {item["replacement_event_id"]: item for item in report["items"]}

    assert report["summary"]["target_medium_time_raw_only_count"] == 3
    assert by_id["evt_near"]["review_recommendation"] == SOURCE_REVIEW_SAME_EVENT
    assert by_id["evt_near"]["exact_span_minutes"] == 5
    assert by_id["evt_far"]["review_recommendation"] == NEEDS_MORE_EVIDENCE
    assert "exact_span_within_threshold" in by_id["evt_far"]["failed_conditions"]
    assert by_id["evt_context"]["review_recommendation"] == NEEDS_MORE_EVIDENCE
    assert "all_tokens_exact" in by_id["evt_context"]["failed_conditions"]


def test_medium_time_raw_only_review_rejects_approximate_suffix(tmp_path):
    audit_csv = tmp_path / "audit.csv"
    _write_audit_csv(audit_csv, [_row("evt_approx", "medium", "time_raw_conflict", "2015?|2020", 2)])

    report = build_medium_time_raw_only_review(audit_csv_path=audit_csv)
    item = report["items"][0]

    assert item["review_recommendation"] == NEEDS_MORE_EVIDENCE
    assert "no_approximate_tokens" in item["failed_conditions"]


def _row(event_id, risk, flags, time_values, component_count):
    return {
        "replacement_event_id": event_id,
        "risk_level": risk,
        "risk_flags": flags,
        "conflict_field_count": 1,
        "component_event_count": component_count,
        "canonical_input_id_count": component_count,
        "coordinate_span_km": 0,
        "date_iso_values": "1954-09-19",
        "time_raw_values": time_values,
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
