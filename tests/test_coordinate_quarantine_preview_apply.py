from pathlib import Path

from scripts.apply_coordinate_quarantine_preview import apply_coordinate_quarantine_preview


def test_coordinate_quarantine_preview_unmaps_quarantine_rows_only(tmp_path: Path) -> None:
    input_path = tmp_path / "deduped_events.jsonl"
    packet_csv = tmp_path / "packet.csv"
    output_dir = tmp_path / "out"
    report_output = tmp_path / "report.json"
    input_path.write_text(
        "\n".join(
            [
                '{"canonical_event_id":"bad","source_name":"ufocat","location_raw":"PALATINE, IL, US","lat":21.1,"lon":88.05,"coordinate_source":"source_coordinates","location_precision":"exact_coords"}',
                '{"canonical_event_id":"coastal","source_name":"ufocat","location_raw":"MIAMI BEACH, FL, US","lat":25.78,"lon":-80.12,"coordinate_source":"source_coordinates","location_precision":"exact_coords"}',
                '{"canonical_event_id":"unmapped","source_name":"mufon","location_raw":"Unknown","lat":null,"lon":null,"coordinate_source":"unresolved","location_precision":"unknown"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    packet_csv.write_text(
        "\n".join(
            [
                "quarantine_recommendation,quarantine_reason,canonical_event_id,declared_country",
                "quarantine_until_review,outside_country_review_bounds,bad,United States of America",
                "keep_visible_polygon_review,outside_coarse_polygon_but_inside_country_review_bounds,coastal,United States of America",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = apply_coordinate_quarantine_preview(
        input_path=input_path,
        packet_csv=packet_csv,
        output_dir=output_dir,
        report_output=report_output,
    )

    output_text = (output_dir / "deduped_events.jsonl").read_text(encoding="utf-8")
    assert report["canonical_outputs_mutated"] is False
    assert report["quarantined_event_count"] == 1
    assert report["mapped_before_count"] == 2
    assert report["mapped_after_count"] == 1
    assert '"coordinate_quarantine_status":"quarantine_until_review"' in output_text
    assert '"coordinate_quarantine_original_lat":21.1' in output_text
    assert '"canonical_event_id":"coastal","source_name":"ufocat","location_raw":"MIAMI BEACH, FL, US","lat":25.78,"lon":-80.12' in output_text
