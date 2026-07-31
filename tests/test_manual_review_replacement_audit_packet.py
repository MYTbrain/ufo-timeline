import csv

from scripts.build_manual_review_replacement_audit_packet import (
    build_manual_review_replacement_audit_packet,
)


def test_replacement_audit_packet_filters_and_sorts_review_rows(tmp_path):
    audit_csv = tmp_path / "audit.csv"
    _write_audit_csv(
        audit_csv,
        [
            _row("evt_low", "low", "", 0, 0),
            _row("evt_medium", "medium", "time_raw_conflict", 1, 0),
            _row("evt_high", "high", "coordinate_span_gt_50km", 2, 150),
        ],
    )

    report, rows, markdown = build_manual_review_replacement_audit_packet(
        audit_csv_path=audit_csv,
        review_risk_levels={"high", "medium"},
        markdown_limit=10,
    )

    assert report["review_row_count"] == 2
    assert report["risk_counts"] == {"high": 1, "medium": 1}
    assert [row["replacement_event_id"] for row in rows] == ["evt_high", "evt_medium"]
    assert rows[0]["recommended_action"] == "manual_adjudication_required"
    assert rows[1]["recommended_action"] == "time_or_identity_review"
    assert "`evt_high`" in markdown
    assert "evt_low" not in markdown


def _row(event_id, risk, flags, conflicts, coordinate_span):
    return {
        "replacement_event_id": event_id,
        "risk_level": risk,
        "risk_flags": flags,
        "conflict_field_count": conflicts,
        "component_event_count": 2,
        "canonical_input_id_count": 2,
        "coordinate_span_km": coordinate_span,
        "date_iso_values": "1954-09-19",
        "time_raw_values": "1630|night",
        "location_raw_values": "Rongeres, FRA",
        "country_values": "FRA",
        "shape_values": "disc",
        "type_values": "3l",
        "source_file_values": "ufocat2023.csv",
        "description_variant_count": 1,
        "summary_variant_count": 1,
        "component_event_ids": f"{event_id}|{event_id}_b",
    }


def _write_audit_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
