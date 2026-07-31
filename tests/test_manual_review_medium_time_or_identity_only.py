import csv
import json

from scripts.review_manual_review_medium_time_or_identity_only import (
    MANUAL_IDENTITY_REVIEW_CANDIDATE,
    NEEDS_DEEPER_IDENTITY_REVIEW,
    build_medium_time_or_identity_only_review,
)


def test_medium_time_or_identity_review_classifies_identity_only_candidate(tmp_path):
    audit_csv = tmp_path / "audit.csv"
    source_events = tmp_path / "events.jsonl"
    _write_audit_csv(
        audit_csv,
        [
            _row(
                "evt_identity",
                "same_source_multiple_native_ids",
                "1600",
                "evt_a|evt_b",
                description_variant_count=1,
                summary_variant_count=1,
            )
        ],
    )
    _write_jsonl(
        source_events,
        [
            _event("evt_a", "ufocat2023.csv", "100"),
            _event("evt_b", "ufocat2023.csv", "101"),
        ],
    )

    report = build_medium_time_or_identity_only_review(
        audit_csv_path=audit_csv,
        source_events_path=source_events,
    )
    item = report["items"][0]

    assert report["summary"]["target_medium_time_or_identity_only_count"] == 1
    assert item["identity_subcategory"] == "identity_only_no_time_conflict"
    assert item["review_recommendation"] == MANUAL_IDENTITY_REVIEW_CANDIDATE
    assert item["native_id_profile"][0]["native_id_count"] == 2
    assert report["decisions_created"] is False
    assert report["ready_for_runtime_promotion"] is False


def test_medium_time_or_identity_review_keeps_wide_time_conflict_deeper_review(tmp_path):
    audit_csv = tmp_path / "audit.csv"
    source_events = tmp_path / "events.jsonl"
    _write_audit_csv(
        audit_csv,
        [
            _row(
                "evt_wide",
                "same_source_multiple_native_ids|time_raw_conflict",
                "1200|1800",
                "evt_a|evt_b",
                description_variant_count=1,
                summary_variant_count=1,
            )
        ],
    )
    _write_jsonl(
        source_events,
        [
            _event("evt_a", "ufocat2023.csv", "100"),
            _event("evt_b", "ufocat2023.csv", "101"),
        ],
    )

    report = build_medium_time_or_identity_only_review(
        audit_csv_path=audit_csv,
        source_events_path=source_events,
    )
    item = report["items"][0]

    assert item["identity_subcategory"] == "identity_plus_wide_exact_time"
    assert item["review_recommendation"] == NEEDS_DEEPER_IDENTITY_REVIEW
    assert "identity_conflict_only_or_nearby_exact_time" in item["failed_conditions"]


def test_medium_time_or_identity_review_rejects_body_variance_candidate(tmp_path):
    audit_csv = tmp_path / "audit.csv"
    source_events = tmp_path / "events.jsonl"
    _write_audit_csv(
        audit_csv,
        [
            _row(
                "evt_body",
                "same_source_multiple_native_ids",
                "1600",
                "evt_a|evt_b",
                description_variant_count=2,
                summary_variant_count=1,
            )
        ],
    )
    _write_jsonl(
        source_events,
        [
            _event("evt_a", "ufocat2023.csv", "100"),
            _event("evt_b", "ufocat2023.csv", "101"),
        ],
    )

    report = build_medium_time_or_identity_only_review(
        audit_csv_path=audit_csv,
        source_events_path=source_events,
    )
    item = report["items"][0]

    assert item["review_recommendation"] == NEEDS_DEEPER_IDENTITY_REVIEW
    assert "no_body_text_variance" in item["failed_conditions"]


def _row(
    event_id,
    flags,
    time_values,
    component_event_ids,
    *,
    description_variant_count,
    summary_variant_count,
):
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
        "time_raw_values": time_values,
        "location_raw_values": "Rongeres, FRA",
        "country_values": "FRA",
        "shape_values": "disc",
        "type_values": "3l",
        "source_file_values": "ufocat2023.csv",
        "description_variant_count": description_variant_count,
        "summary_variant_count": summary_variant_count,
        "component_event_ids": component_event_ids,
    }


def _event(event_id, source_file, native_id):
    return {
        "canonical_event_id": event_id,
        "source_file": source_file,
        "source_native_id": native_id,
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
