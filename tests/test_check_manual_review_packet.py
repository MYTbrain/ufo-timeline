import json

from scripts.build_manual_review_packet import (
    build_manual_review_packet,
    write_csv,
    write_json,
    write_markdown,
)
from scripts.check_manual_review_packet import check_manual_review_packet


def _queue_item(review_item_id):
    return {
        "review_item_id": review_item_id,
        "review_type": "duplicate_candidate",
        "priority": "high",
        "status": "needs_review",
        "reason": "bounded fuzzy duplicate candidate; never auto-merged",
        "candidate": {
            "duplicate_candidate_id": f"dupc_{review_item_id}",
            "score": 0.95,
            "reasons": ["same_strong_date", "same_normalized_location"],
            "blocking": {
                "date_iso": "1977-02-04",
                "date_precision": "strong_day",
                "location_key": "broad haven school dyfed gbr eu",
            },
            "canonical_input_ids": [f"cin_{review_item_id}_a", f"cin_{review_item_id}_b"],
            "records": [
                {
                    "canonical_input_id": f"cin_{review_item_id}_a",
                    "source_name": "ufocat",
                    "source_file": "ufocat2023.csv",
                    "source_row_number": 281373,
                    "source_native_id": "94285",
                    "date_iso": "1977-02-04",
                    "date_precision": "exact_day",
                    "location": "BROAD HAVEN SCHOOL, Dyfed, GBR, EU",
                    "source_text": "Silver domed disc, windows, and entity.",
                }
            ],
        },
        "suggested_decisions": ["same_event", "distinct_events", "needs_more_evidence"],
    }


def _write_queue(path, items):
    path.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in items),
        encoding="utf-8",
    )


def _write_packet_files(tmp_path, items, *, markdown_item_limit=250):
    queue_path = tmp_path / "manual_review_queue.jsonl"
    packet_path = tmp_path / "manual_review_packet.json"
    csv_path = tmp_path / "manual_review_packet.csv"
    markdown_path = tmp_path / "manual_review_packet.md"
    _write_queue(queue_path, items)
    packet = build_manual_review_packet(items)
    write_json(packet_path, packet)
    write_csv(csv_path, packet["items"])
    write_markdown(markdown_path, packet, item_limit=markdown_item_limit)
    return queue_path, packet_path, csv_path, markdown_path


def test_check_manual_review_packet_accepts_review_only_packet(tmp_path):
    paths = _write_packet_files(
        tmp_path,
        [_queue_item("rev_a"), _queue_item("rev_b")],
        markdown_item_limit=1,
    )

    report = check_manual_review_packet(
        queue_path=paths[0],
        packet_path=paths[1],
        csv_path=paths[2],
        markdown_path=paths[3],
        forbidden_paths=(tmp_path / "manual_review_decisions.jsonl",),
    )

    assert report["status"] == "ready"
    assert report["checks"]["packet_contains_all_queue_ids"] is True
    assert report["checks"]["csv_json_fields_parse"] is True
    assert report["checks"]["markdown_truncation_declared_if_needed"] is True
    assert report["counts"]["queue_items"] == 2
    assert report["counts"]["markdown_items_rendered"] == 1


def test_check_manual_review_packet_blocks_generated_decisions_flag(tmp_path):
    queue_path, packet_path, csv_path, markdown_path = _write_packet_files(tmp_path, [_queue_item("rev_a")])
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    packet["decisions_created"] = True
    write_json(packet_path, packet)

    report = check_manual_review_packet(
        queue_path=queue_path,
        packet_path=packet_path,
        csv_path=csv_path,
        markdown_path=markdown_path,
        forbidden_paths=(),
    )

    assert report["status"] == "blocked"
    assert report["checks"]["decisions_not_created"] is False


def test_check_manual_review_packet_blocks_duplicate_ids_and_forbidden_outputs(tmp_path):
    queue_path, packet_path, csv_path, markdown_path = _write_packet_files(tmp_path, [_queue_item("rev_a")])
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    packet["items"].append(dict(packet["items"][0]))
    packet["exported_item_count"] = 2
    write_json(packet_path, packet)
    forbidden_path = tmp_path / "manual_review_applied_decisions.jsonl"
    forbidden_path.write_text("{}", encoding="utf-8")

    report = check_manual_review_packet(
        queue_path=queue_path,
        packet_path=packet_path,
        csv_path=csv_path,
        markdown_path=markdown_path,
        forbidden_paths=(forbidden_path,),
    )

    assert report["status"] == "blocked"
    assert report["checks"]["packet_review_ids_unique"] is False
    assert report["checks"]["csv_row_count_matches"] is False
    assert report["checks"]["no_forbidden_mutation_artifacts"] is False
    assert report["problems"]["duplicate_packet_ids"] == ["rev_a"]


def test_check_manual_review_packet_reports_missing_inputs_as_blocked(tmp_path):
    report = check_manual_review_packet(
        queue_path=tmp_path / "missing_queue.jsonl",
        packet_path=tmp_path / "missing_packet.json",
        csv_path=tmp_path / "missing_packet.csv",
        markdown_path=tmp_path / "missing_packet.md",
        forbidden_paths=(),
    )

    assert report["status"] == "blocked"
    assert report["checks"]["queue_exists"] is False
    assert report["checks"]["packet_exists"] is False
    assert report["checks"]["inputs_read_without_errors"] is False
    assert len(report["problems"]["read_errors"]) == 4
