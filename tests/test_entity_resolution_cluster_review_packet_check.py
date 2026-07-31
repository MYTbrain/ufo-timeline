import csv
import json

from scripts.check_entity_resolution_cluster_review_packet import check_entity_resolution_cluster_review_packet


def _write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def test_check_entity_resolution_cluster_review_packet_validates_packet_csv_and_safety_flags(tmp_path):
    packet_path = tmp_path / "packet.json"
    csv_path = tmp_path / "packet.csv"
    markdown_path = tmp_path / "packet.md"
    item = {
        "cluster_review_id": "er_cluster_a",
        "family_id": "same_source_native_id_strong_date",
        "tier": "conservative",
        "projected_event_reduction": 3,
        "unique_current_event_count": 4,
        "source_record_count": 5,
    }
    _write_json(
        packet_path,
        {
            "packet_policy": "entity_resolution_cluster_review_only",
            "canonical_outputs_mutated": False,
            "preview_outputs_written": False,
            "decisions_created": False,
            "auto_merge_performed": False,
            "export_summary": {
                "exported_item_count": 1,
                "projected_reduction_sum_not_deduped": 3,
            },
            "items": [item],
        },
    )
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["cluster_review_id"])
        writer.writeheader()
        writer.writerow({"cluster_review_id": "er_cluster_a"})
    markdown_path.write_text("# Packet\n\n## Cluster Items\n", encoding="utf-8")

    report = check_entity_resolution_cluster_review_packet(
        packet_path=packet_path,
        csv_path=csv_path,
        markdown_path=markdown_path,
    )

    assert report["valid"] is True
    assert report["item_count"] == 1
    assert report["csv_row_count"] == 1
    assert report["items_with_current_event_ids"] == 0
    assert report["canonical_outputs_mutated"] is False


def test_check_entity_resolution_cluster_review_packet_validates_current_event_id_export(tmp_path):
    packet_path = tmp_path / "packet.json"
    item = {
        "cluster_review_id": "er_cluster_a",
        "family_id": "same_source_native_id_strong_date",
        "tier": "conservative",
        "projected_event_reduction": 3,
        "unique_current_event_count": 4,
        "source_record_count": 5,
        "current_event_ids": ["evt_a", "evt_b"],
        "current_event_ids_truncated": True,
    }
    _write_json(
        packet_path,
        {
            "packet_policy": "entity_resolution_cluster_review_only",
            "canonical_outputs_mutated": False,
            "preview_outputs_written": False,
            "decisions_created": False,
            "auto_merge_performed": False,
            "export_summary": {
                "exported_item_count": 1,
                "projected_reduction_sum_not_deduped": 3,
            },
            "items": [item],
        },
    )

    report = check_entity_resolution_cluster_review_packet(
        packet_path=packet_path,
        csv_path=None,
        markdown_path=None,
    )

    assert report["valid"] is True
    assert report["items_with_current_event_ids"] == 1
    assert report["current_event_id_overflow_count"] == 0
    assert report["current_event_id_truncation_mismatch_count"] == 0


def test_check_entity_resolution_cluster_review_packet_rejects_current_event_id_mismatch(tmp_path):
    packet_path = tmp_path / "packet.json"
    item = {
        "cluster_review_id": "er_cluster_a",
        "family_id": "same_source_native_id_strong_date",
        "tier": "conservative",
        "projected_event_reduction": 1,
        "unique_current_event_count": 2,
        "source_record_count": 5,
        "current_event_ids": ["evt_a", "evt_b", "evt_c"],
        "current_event_ids_truncated": False,
    }
    _write_json(
        packet_path,
        {
            "packet_policy": "entity_resolution_cluster_review_only",
            "canonical_outputs_mutated": False,
            "preview_outputs_written": False,
            "decisions_created": False,
            "auto_merge_performed": False,
            "export_summary": {
                "exported_item_count": 1,
                "projected_reduction_sum_not_deduped": 1,
            },
            "items": [item],
        },
    )

    report = check_entity_resolution_cluster_review_packet(
        packet_path=packet_path,
        csv_path=None,
        markdown_path=None,
    )

    assert report["valid"] is False
    assert report["current_event_id_overflow_count"] == 1


def test_check_entity_resolution_cluster_review_packet_rejects_duplicate_ids(tmp_path):
    packet_path = tmp_path / "packet.json"
    item = {
        "cluster_review_id": "er_cluster_a",
        "family_id": "same_source_native_id_strong_date",
        "tier": "conservative",
        "projected_event_reduction": 3,
        "unique_current_event_count": 4,
        "source_record_count": 5,
    }
    _write_json(
        packet_path,
        {
            "packet_policy": "entity_resolution_cluster_review_only",
            "canonical_outputs_mutated": False,
            "preview_outputs_written": False,
            "decisions_created": False,
            "auto_merge_performed": False,
            "export_summary": {
                "exported_item_count": 2,
                "projected_reduction_sum_not_deduped": 6,
            },
            "items": [item, dict(item)],
        },
    )

    report = check_entity_resolution_cluster_review_packet(
        packet_path=packet_path,
        csv_path=None,
        markdown_path=None,
    )

    assert report["valid"] is False
    assert report["duplicate_cluster_review_id_count"] == 1
