import csv
import json

from scripts.build_manual_review_packet import build_manual_review_packet, main


def _duplicate_item(review_item_id="rev_duplicate"):
    return {
        "review_item_id": review_item_id,
        "review_type": "duplicate_candidate",
        "priority": "high",
        "status": "needs_review",
        "reason": "bounded fuzzy duplicate candidate; never auto-merged",
        "candidate": {
            "duplicate_candidate_id": "dupc_123",
            "score": 1.0,
            "reasons": ["same_strong_date", "same_normalized_location"],
            "blocking": {
                "date_iso": "1977-02-04",
                "date_precision": "strong_day",
                "location_key": "broad haven school dyfed gbr eu",
            },
            "canonical_input_ids": ["cin_a", "cin_b"],
            "records": [
                {
                    "canonical_input_id": "cin_a",
                    "source_name": "ufocat",
                    "source_file": "ufocat2023.csv",
                    "source_row_number": 281373,
                    "source_native_id": "94285",
                    "date_iso": "1977-02-04",
                    "date_precision": "exact_day",
                    "location": "BROAD HAVEN SCHOOL, Dyfed, GBR, EU",
                    "source_text": "Silver domed disc with windows.",
                },
                {
                    "canonical_input_id": "cin_b",
                    "source_name": "ufocat",
                    "source_file": "ufocat2023.csv",
                    "source_row_number": 282176,
                    "source_native_id": "94285",
                    "date_iso": "1977-02-04",
                    "date_precision": "exact_day",
                    "location": "BROAD HAVEN SCHOOL, Dyfed, GBR, EU",
                    "source_text": "Silver domed disc with windows.",
                },
            ],
        },
        "suggested_decisions": ["same_event", "distinct_events", "needs_more_evidence"],
    }


def _non_duplicate_item():
    return {
        "review_item_id": "rev_low_precision",
        "review_type": "low_precision_location",
        "priority": "normal",
        "status": "needs_review",
        "reason": "location needs reviewer confirmation",
        "date_iso": "1952-07-01",
        "date_precision": "month",
        "location_key": "washington dc usa na",
        "canonical_input_ids": ["cin_c"],
        "suggested_decisions": ["accept_low_precision", "exclude_from_map"],
    }


def test_build_manual_review_packet_summarizes_duplicate_candidates():
    packet = build_manual_review_packet([_duplicate_item()])

    assert packet["packet_policy"] == "review_only"
    assert packet["canonical_outputs_mutated"] is False
    assert packet["decisions_created"] is False
    assert packet["decision_outputs_created"] is False
    assert packet["auto_merge_performed"] is False
    assert packet["type_counts"] == {"duplicate_candidate": 1}
    item = packet["items"][0]
    assert item["review_item_id"] == "rev_duplicate"
    assert item["candidate_id"] == "dupc_123"
    assert item["canonical_input_ids"] == ["cin_a", "cin_b"]
    assert item["record_count"] == 2
    assert "ufocat row 281373" in item["records_summary"]
    assert item["decision_template"]["decision"] == "same_event | distinct_events | needs_more_evidence"
    assert json.loads(item["decision_template_json"])["review_item_id"] == "rev_duplicate"


def test_build_manual_review_packet_preserves_non_duplicate_review_items():
    packet = build_manual_review_packet([_non_duplicate_item()])

    item = packet["items"][0]
    assert item["review_item_id"] == "rev_low_precision"
    assert item["review_type"] == "low_precision_location"
    assert item["candidate_id"] is None
    assert item["canonical_input_ids"] == ["cin_c"]
    assert item["date_iso"] == "1952-07-01"
    assert item["location_key"] == "washington dc usa na"
    assert item["suggested_decisions"] == ["accept_low_precision", "exclude_from_map"]
    assert item["decision_template"] == {
        "review_item_id": "rev_low_precision",
        "decision": "",
        "reviewer": "",
        "reviewed_at": "",
        "notes": "",
    }


def test_build_manual_review_packet_sorts_high_priority_first_and_limits():
    low = _duplicate_item("rev_low")
    low["priority"] = "low"
    high = _duplicate_item("rev_high")
    high["priority"] = "high"

    packet = build_manual_review_packet([low, high], limit=1)

    assert packet["input_queue_count"] == 2
    assert packet["exported_item_count"] == 1
    assert packet["items"][0]["review_item_id"] == "rev_high"


def test_manual_review_packet_cli_writes_json_csv_and_markdown(tmp_path, monkeypatch):
    queue_path = tmp_path / "manual_review_queue.jsonl"
    json_output = tmp_path / "manual_review_packet.json"
    csv_output = tmp_path / "manual_review_packet.csv"
    markdown_output = tmp_path / "manual_review_packet.md"
    queue_path.write_text(json.dumps(_duplicate_item()) + "\n", encoding="utf-8")

    monkeypatch.setattr(
        "sys.argv",
        [
            "build_manual_review_packet.py",
            "--queue",
            str(queue_path),
            "--json-output",
            str(json_output),
            "--csv-output",
            str(csv_output),
            "--markdown-output",
            str(markdown_output),
        ],
    )

    assert main() == 0
    payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert payload["exported_item_count"] == 1
    assert payload["decisions_created"] is False
    assert payload["auto_merge_performed"] is False
    with csv_output.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["review_item_id"] == "rev_duplicate"
    assert rows[0]["canonical_input_ids"] == '["cin_a", "cin_b"]'
    markdown = markdown_output.read_text(encoding="utf-8")
    assert "This packet is review-only." in markdown
    assert "- Decisions created: false" in markdown
    assert "- Decision outputs created: false" in markdown
    assert "- Auto-merge performed: false" in markdown
    assert "### rev_duplicate" in markdown
