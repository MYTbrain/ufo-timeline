import csv

from scripts.summarize_manual_review_remaining_lane_actions import build_remaining_lane_actions


def test_remaining_lane_actions_marks_coordinate_lane_review_only_after_packet(tmp_path):
    sublanes_csv = tmp_path / "sublanes.csv"
    _write_sublanes(
        sublanes_csv,
        [
            _row("medium_coordinate_span_gt_5km", 148, 243, {"medium": 148}, {"coordinate_span_gt_5km": 148}),
            _row("medium_body_text_only", 35, 35, {"medium": 35}, {"description_text_conflict": 35}),
        ],
    )

    report = build_remaining_lane_actions(sublanes_csv_path=sublanes_csv)
    by_lane = {item["sublane"]: item for item in report["items"]}

    assert by_lane["medium_coordinate_span_gt_5km"]["status"] == "review_only_packet_created"
    assert by_lane["medium_coordinate_span_gt_5km"]["next_action"] == (
        "manual_coordinate_review_before_any_decisions"
    )
    assert by_lane["medium_body_text_only"]["status"] == "review_only_packet_created"
    assert report["decisions_created"] is False
    assert report["auto_merge_performed"] is False


def test_remaining_lane_actions_totals_by_status(tmp_path):
    sublanes_csv = tmp_path / "sublanes.csv"
    _write_sublanes(
        sublanes_csv,
        [
            _row("accepted_low_risk_preview_lane", 10, 12, {"low": 10}, {}),
            _row("high_coordinate_span_gt_50km", 2, 3, {"high": 2}, {"coordinate_span_gt_50km": 2}),
        ],
    )

    report = build_remaining_lane_actions(sublanes_csv_path=sublanes_csv)

    assert report["summary"]["totals_by_status"]["accepted_sidecar_preview"]["component_count"] == 10
    assert report["summary"]["totals_by_status"]["high_risk_dedicated_review_packet_created"]["component_count"] == 2
    assert report["summary"]["unsafe_automation_component_count"] == 2


def _row(sublane, component_count, reduction, risk_counts, flag_counts):
    return {
        "sublane": sublane,
        "component_count": component_count,
        "projected_event_reduction": reduction,
        "risk_counts": _json(risk_counts),
        "flag_counts": _json(flag_counts),
        "top_component_ids": "evt_a",
    }


def _json(value):
    import json

    return json.dumps(value)


def _write_sublanes(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
