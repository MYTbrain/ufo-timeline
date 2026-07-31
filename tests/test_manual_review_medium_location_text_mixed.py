import csv

from scripts.review_manual_review_medium_location_text_mixed import (
    LOCATION_VARIANT_REVIEW_CANDIDATE,
    NEEDS_DEEPER_LOCATION_REVIEW,
    build_medium_location_text_mixed_review,
)


def test_medium_location_text_review_classifies_punctuation_variant(tmp_path):
    audit_csv = tmp_path / "audit.csv"
    _write_audit_csv(
        audit_csv,
        [
            _row(
                "evt_location",
                "location_text_conflict",
                "ST GERVAIS SUR MARE, Herault, FRA|ST GERVAIS-SUR-MARE, Herault, FRA",
                "2145",
            )
        ],
    )

    report = build_medium_location_text_mixed_review(audit_csv_path=audit_csv)
    item = report["items"][0]

    assert report["summary"]["target_medium_location_text_mixed_count"] == 1
    assert item["review_recommendation"] == LOCATION_VARIANT_REVIEW_CANDIDATE
    assert item["location_subcategory"] == "punctuation_spacing_location_variant"
    assert report["decisions_created"] is False


def test_medium_location_text_review_allows_nearby_exact_time_conflict(tmp_path):
    audit_csv = tmp_path / "audit.csv"
    _write_audit_csv(
        audit_csv,
        [
            _row(
                "evt_time",
                "time_raw_conflict|location_text_conflict",
                "ST GERVAIS SUR MARE, Herault, FRA|ST GERVAIS-SUR-MARE, Herault, FRA",
                "2145|2150",
            )
        ],
    )

    report = build_medium_location_text_mixed_review(audit_csv_path=audit_csv)
    item = report["items"][0]

    assert item["review_recommendation"] == LOCATION_VARIANT_REVIEW_CANDIDATE
    assert item["exact_span_minutes"] == 5


def test_medium_location_text_review_rejects_substantive_location_difference(tmp_path):
    audit_csv = tmp_path / "audit.csv"
    _write_audit_csv(
        audit_csv,
        [
            _row(
                "evt_far_location",
                "location_text_conflict",
                "ST GERVAIS SUR MARE, Herault, FRA|LOS ANGELES, CA, US",
                "2145",
            )
        ],
    )

    report = build_medium_location_text_mixed_review(audit_csv_path=audit_csv)
    item = report["items"][0]

    assert item["review_recommendation"] == NEEDS_DEEPER_LOCATION_REVIEW
    assert "location_similarity_within_threshold" in item["failed_conditions"]


def _row(event_id, flags, location_values, time_values):
    return {
        "replacement_event_id": event_id,
        "risk_level": "medium",
        "risk_flags": flags,
        "conflict_field_count": len(flags.split("|")),
        "component_event_count": 2,
        "canonical_input_id_count": 2,
        "coordinate_span_km": 0,
        "date_iso_values": "1954-09-19",
        "time_raw_values": time_values,
        "location_raw_values": location_values,
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
