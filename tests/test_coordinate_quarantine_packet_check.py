import json
from pathlib import Path

from scripts.check_coordinate_quarantine_packet import check_coordinate_quarantine_packet


def test_check_coordinate_quarantine_packet_validates_counts_and_review_gate(tmp_path: Path) -> None:
    packet_path = tmp_path / "packet.json"
    csv_path = tmp_path / "packet.csv"
    output_path = tmp_path / "readiness.json"
    packet_path.write_text(
        json.dumps(
            {
                "mode": "report_only",
                "canonical_outputs_mutated": False,
                "preview_outputs_mutated": False,
                "ready_for_apply": False,
                "human_review_required_before_hiding": True,
                "summary": {
                    "suspicious_event_count": 2,
                    "quarantine_candidate_count": 1,
                    "display_safe_review_count": 1,
                },
            }
        ),
        encoding="utf-8",
    )
    csv_path.write_text(
        "\n".join(
            [
                "quarantine_recommendation,canonical_event_id",
                "quarantine_until_review,bad",
                "keep_visible_polygon_review,coastal",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = check_coordinate_quarantine_packet(packet_path=packet_path, csv_path=csv_path, output_path=output_path)

    assert report["status"] == "ready_for_review"
    assert report["checks"]["csv_row_count_matches_suspicious"] is True
    assert output_path.exists()
