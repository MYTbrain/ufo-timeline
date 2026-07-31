"""Validate the report-only entity-resolution cluster review packet."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


DEFAULT_PACKET = Path("data/reports/entity_resolution_cluster_review_packet.json")
DEFAULT_CSV = Path("data/reports/entity_resolution_cluster_review_packet.csv")
DEFAULT_MARKDOWN = Path("data/reports/entity_resolution_cluster_review_packet.md")
DEFAULT_OUTPUT = Path("data/reports/entity_resolution_cluster_review_packet_check.json")


def check_entity_resolution_cluster_review_packet(
    *,
    packet_path: Path = DEFAULT_PACKET,
    csv_path: Path | None = DEFAULT_CSV,
    markdown_path: Path | None = DEFAULT_MARKDOWN,
) -> dict[str, Any]:
    packet = read_json(packet_path)
    items = packet.get("items") if isinstance(packet.get("items"), list) else []
    export_summary = packet.get("export_summary") if isinstance(packet.get("export_summary"), dict) else {}
    item_ids = [str(item.get("cluster_review_id") or "") for item in items if isinstance(item, dict)]
    duplicate_ids = sorted({item_id for item_id in item_ids if item_ids.count(item_id) > 1 and item_id})
    missing_required = [
        item.get("cluster_review_id")
        for item in items
        if isinstance(item, dict)
        and not all(item.get(field) not in (None, "") for field in required_item_fields())
    ]
    negative_reductions = [
        item.get("cluster_review_id")
        for item in items
        if isinstance(item, dict) and int(item.get("projected_event_reduction") or 0) < 0
    ]
    current_event_id_overflows = [
        item.get("cluster_review_id")
        for item in items
        if isinstance(item, dict)
        and string_list(item.get("current_event_ids"))
        and len(string_list(item.get("current_event_ids"))) > int(item.get("unique_current_event_count") or 0)
    ]
    current_event_id_truncation_mismatches = [
        item.get("cluster_review_id")
        for item in items
        if isinstance(item, dict) and has_current_event_id_truncation_mismatch(item)
    ]
    csv_row_count = count_csv_rows(csv_path) if csv_path else None
    markdown_discloses_truncation = markdown_has_truncation_note(markdown_path) if markdown_path else None
    expected_count = export_summary.get("exported_item_count")
    projected_sum = sum(int(item.get("projected_event_reduction") or 0) for item in items if isinstance(item, dict))
    expected_projected_sum = export_summary.get("projected_reduction_sum_not_deduped")

    valid = (
        packet.get("packet_policy") == "entity_resolution_cluster_review_only"
        and packet.get("canonical_outputs_mutated") is False
        and packet.get("preview_outputs_written") is False
        and packet.get("decisions_created") is False
        and packet.get("auto_merge_performed") is False
        and expected_count == len(items)
        and expected_projected_sum == projected_sum
        and not duplicate_ids
        and not missing_required
        and not negative_reductions
        and not current_event_id_overflows
        and not current_event_id_truncation_mismatches
        and (csv_row_count is None or csv_row_count == len(items))
    )
    return {
        "schema_version": 1,
        "check_policy": "entity_resolution_cluster_review_packet_check",
        "valid": valid,
        "packet": str(packet_path),
        "csv": str(csv_path) if csv_path else None,
        "markdown": str(markdown_path) if markdown_path else None,
        "packet_policy": packet.get("packet_policy"),
        "item_count": len(items),
        "expected_item_count": expected_count,
        "csv_row_count": csv_row_count,
        "projected_reduction_sum_not_deduped": projected_sum,
        "expected_projected_reduction_sum_not_deduped": expected_projected_sum,
        "duplicate_cluster_review_id_count": len(duplicate_ids),
        "missing_required_field_count": len(missing_required),
        "negative_projected_reduction_count": len(negative_reductions),
        "items_with_current_event_ids": sum(
            1 for item in items if isinstance(item, dict) and string_list(item.get("current_event_ids"))
        ),
        "current_event_id_overflow_count": len(current_event_id_overflows),
        "current_event_id_truncation_mismatch_count": len(current_event_id_truncation_mismatches),
        "markdown_discloses_truncation": markdown_discloses_truncation,
        "canonical_outputs_mutated": bool(packet.get("canonical_outputs_mutated")),
        "preview_outputs_written": bool(packet.get("preview_outputs_written")),
        "decisions_created": bool(packet.get("decisions_created")),
        "auto_merge_performed": bool(packet.get("auto_merge_performed")),
    }


def required_item_fields() -> tuple[str, ...]:
    return (
        "cluster_review_id",
        "family_id",
        "tier",
        "projected_event_reduction",
        "unique_current_event_count",
        "source_record_count",
    )


def has_current_event_id_truncation_mismatch(item: dict[str, Any]) -> bool:
    current_event_ids = string_list(item.get("current_event_ids"))
    if not current_event_ids:
        return False
    unique_count = int(item.get("unique_current_event_count") or 0)
    is_truncated = bool(item.get("current_event_ids_truncated"))
    if len(current_event_ids) < unique_count:
        return not is_truncated
    return is_truncated


def string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def count_csv_rows(path: Path | None) -> int | None:
    if path is None or not path.exists():
        return None
    with path.open("r", encoding="utf-8", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def markdown_has_truncation_note(path: Path | None) -> bool | None:
    if path is None or not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    return "Markdown limited to" in text or "Cluster Items" in text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = check_entity_resolution_cluster_review_packet(
        packet_path=args.packet,
        csv_path=args.csv,
        markdown_path=args.markdown,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "valid": report["valid"],
                "item_count": report["item_count"],
                "duplicate_cluster_review_id_count": report["duplicate_cluster_review_id_count"],
                "missing_required_field_count": report["missing_required_field_count"],
                "canonical_outputs_mutated": report["canonical_outputs_mutated"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
