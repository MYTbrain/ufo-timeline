"""Build a compact human-review packet from manual_review_queue.jsonl.

The packet is non-destructive. It summarizes queue items into CSV/JSON so a
reviewer can make decisions later using manual_review_decision_schema.json.
It does not fabricate decisions and does not mutate canonical outputs.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import re
from typing import Any


DEFAULT_QUEUE_PATH = Path("data/canonical_full/manual_review_queue.jsonl")
DEFAULT_JSON_OUTPUT = Path("data/reports/manual_review_packet.json")
DEFAULT_CSV_OUTPUT = Path("data/reports/manual_review_packet.csv")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/manual_review_packet.md")

CSV_FIELDS = (
    "review_item_id",
    "review_type",
    "priority",
    "status",
    "reason",
    "suggested_decisions",
    "candidate_id",
    "candidate_score",
    "candidate_reasons",
    "date_iso",
    "date_precision",
    "location_key",
    "canonical_input_ids",
    "record_count",
    "records_summary",
    "decision_template_json",
)

WHITESPACE_RE = re.compile(r"\s+")


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE_PATH)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument("--limit", type=int, default=0, help="Optional max items to export. 0 means all items.")
    parser.add_argument(
        "--markdown-item-limit",
        type=int,
        default=250,
        help="Max items to include in the Markdown triage view. CSV/JSON export still honors --limit.",
    )
    return parser


def build_manual_review_packet(queue: list[dict[str, Any]], *, limit: int = 0) -> dict[str, Any]:
    rows = []
    for item in queue:
        rows.append(summarize_review_item(item))

    rows.sort(key=review_packet_sort_key)
    if limit and limit > 0:
        rows = rows[:limit]

    return {
        "schema_version": 1,
        "packet_policy": "review_only",
        "canonical_outputs_mutated": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "auto_merge_performed": False,
        "input_queue_count": len(queue),
        "exported_item_count": len(rows),
        "type_counts": count_by(rows, "review_type"),
        "priority_counts": count_by(rows, "priority"),
        "status_counts": count_by(rows, "status"),
        "decision_guidance": {
            "decision_file_format": "JSONL or JSON array accepted by scripts/build_canonical_ufo_dataset.py --manual-review-decisions.",
            "required_field": "review_item_id",
            "important_policy": "Fuzzy duplicate candidates must not be merged unless a reviewer explicitly chooses same_event.",
        },
        "items": rows,
    }


def summarize_review_item(item: dict[str, Any]) -> dict[str, Any]:
    candidate = item.get("candidate") if isinstance(item.get("candidate"), dict) else {}
    blocking = candidate.get("blocking") if isinstance(candidate.get("blocking"), dict) else {}
    records = candidate.get("records") if isinstance(candidate.get("records"), list) else []
    canonical_input_ids = _string_list(candidate.get("canonical_input_ids"))
    if not canonical_input_ids:
        canonical_input_ids = _string_list(item.get("canonical_input_ids"))

    row = {
        "review_item_id": clean_text(item.get("review_item_id")),
        "review_type": clean_text(item.get("review_type")) or "unknown",
        "priority": clean_text(item.get("priority")) or "normal",
        "status": clean_text(item.get("status")) or "needs_review",
        "reason": clean_text(item.get("reason")),
        "suggested_decisions": _string_list(item.get("suggested_decisions")),
        "candidate_id": clean_text(candidate.get("duplicate_candidate_id") or candidate.get("candidate_id")),
        "candidate_score": candidate.get("score"),
        "candidate_reasons": _string_list(candidate.get("reasons")),
        "date_iso": clean_text(blocking.get("date_iso") or item.get("date_iso")),
        "date_precision": clean_text(blocking.get("date_precision") or item.get("date_precision")),
        "location_key": clean_text(blocking.get("location_key") or item.get("location_key")),
        "canonical_input_ids": canonical_input_ids,
        "record_count": len(records),
        "records": [summarize_candidate_record(record) for record in records if isinstance(record, dict)],
    }
    row["records_summary"] = summarize_records_for_csv(row["records"])
    row["decision_template"] = decision_template_for_row(row)
    row["decision_template_json"] = json.dumps(row["decision_template"], ensure_ascii=False, sort_keys=True)
    return row


def summarize_candidate_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "canonical_input_id": clean_text(record.get("canonical_input_id")),
        "source_name": clean_text(record.get("source_name")),
        "source_file": clean_text(record.get("source_file")),
        "source_row_number": record.get("source_row_number"),
        "source_native_id": clean_text(record.get("source_native_id")),
        "date_iso": clean_text(record.get("date_iso")),
        "date_precision": clean_text(record.get("date_precision")),
        "location": clean_text(record.get("location")),
        "source_text": truncate_text(record.get("source_text"), 220),
    }


def summarize_records_for_csv(records: list[dict[str, Any]]) -> str:
    parts = []
    for record in records:
        source = record.get("source_name") or "source"
        row_number = record.get("source_row_number")
        native_id = record.get("source_native_id") or ""
        location = record.get("location") or ""
        text = record.get("source_text") or ""
        parts.append(
            clean_text(
                f"{source} row {row_number or '?'} native {native_id}: {location} :: {text}"
            )
        )
    return " | ".join(part for part in parts if part)


def decision_template_for_row(row: dict[str, Any]) -> dict[str, Any]:
    template = {
        "review_item_id": row.get("review_item_id"),
        "decision": "",
        "reviewer": "",
        "reviewed_at": "",
        "notes": "",
    }
    if row.get("review_type") == "duplicate_candidate":
        template["decision"] = "same_event | distinct_events | needs_more_evidence"
        template["replacement_canonical_event_id"] = ""
        template["exclude_canonical_input_ids"] = []
    return template


def review_packet_sort_key(row: dict[str, Any]) -> tuple[int, str, str]:
    priority_rank = {
        "urgent": 0,
        "high": 1,
        "normal": 2,
        "medium": 2,
        "low": 3,
    }
    return (
        priority_rank.get(str(row.get("priority") or "").lower(), 4),
        str(row.get("review_type") or ""),
        str(row.get("review_item_id") or ""),
    )


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{path} line {line_number} must contain a JSON object.")
            records.append(payload)
    return records


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                field: csv_value(row.get(field))
                for field in CSV_FIELDS
            })


def write_markdown(path: Path, packet: dict[str, Any], *, item_limit: int = 250) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    items = packet.get("items") if isinstance(packet.get("items"), list) else []
    visible_items = items[: max(0, item_limit)]
    lines = [
        "# Manual Review Packet",
        "",
        "This packet is review-only. It does not create decisions, perform merges, or mutate canonical outputs.",
        "",
        "## Summary",
        "",
        f"- Input queue items: {packet.get('input_queue_count', 0)}",
        f"- Exported items: {packet.get('exported_item_count', 0)}",
        f"- Canonical outputs mutated: {str(packet.get('canonical_outputs_mutated')).lower()}",
        f"- Decisions created: {str(packet.get('decisions_created')).lower()}",
        f"- Decision outputs created: {str(packet.get('decision_outputs_created')).lower()}",
        f"- Auto-merge performed: {str(packet.get('auto_merge_performed')).lower()}",
        f"- Markdown items shown: {len(visible_items)}",
        "",
        "## Type Counts",
        "",
    ]
    for key, count in sorted((packet.get("type_counts") or {}).items()):
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## Review Items", ""])
    for item in visible_items:
        lines.extend(markdown_lines_for_item(item))
    if len(items) > len(visible_items):
        lines.extend([
            "",
            f"_Markdown view truncated at {len(visible_items)} items. Use the CSV/JSON packet for all {len(items)} exported items._",
            "",
        ])
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def markdown_lines_for_item(item: dict[str, Any]) -> list[str]:
    records = item.get("records") if isinstance(item.get("records"), list) else []
    lines = [
        f"### {item.get('review_item_id') or 'unknown'}",
        "",
        f"- Type: {item.get('review_type') or 'unknown'}",
        f"- Priority: {item.get('priority') or 'normal'}",
        f"- Status: {item.get('status') or 'needs_review'}",
        f"- Reason: {item.get('reason') or ''}",
        f"- Suggested decisions: {', '.join(item.get('suggested_decisions') or [])}",
        f"- Candidate ID: {item.get('candidate_id') or ''}",
        f"- Score: {item.get('candidate_score') if item.get('candidate_score') is not None else ''}",
        f"- Date/location: {item.get('date_iso') or ''} - {item.get('location_key') or ''}",
        f"- Canonical input IDs: {', '.join(item.get('canonical_input_ids') or [])}",
        "",
    ]
    for record in records[:4]:
        source = record.get("source_name") or "source"
        row_number = record.get("source_row_number") or "?"
        native_id = record.get("source_native_id") or ""
        location = record.get("location") or ""
        text = record.get("source_text") or ""
        lines.append(f"- {source} row {row_number} native {native_id}: {location} :: {text}")
    lines.append("")
    return lines


def csv_value(value: Any) -> str:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if value is None:
        return ""
    return str(value)


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [text for item in value if (text := clean_text(item))]
    text = clean_text(value)
    return [text] if text else []


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = WHITESPACE_RE.sub(" ", str(value).replace("\n", " ")).strip()
    return text or None


def truncate_text(value: Any, limit: int) -> str | None:
    text = clean_text(value)
    if not text or len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def main() -> int:
    args = build_argument_parser().parse_args()
    queue = read_jsonl(args.queue)
    packet = build_manual_review_packet(queue, limit=args.limit)
    write_json(args.json_output, packet)
    write_csv(args.csv_output, packet["items"])
    write_markdown(args.markdown_output, packet, item_limit=args.markdown_item_limit)
    print(json.dumps({
        "queue": str(args.queue),
        "json_output": str(args.json_output),
        "csv_output": str(args.csv_output),
        "markdown_output": str(args.markdown_output),
        "input_queue_count": packet["input_queue_count"],
        "exported_item_count": packet["exported_item_count"],
        "canonical_outputs_mutated": False,
        "decisions_created": False,
        "auto_merge_performed": False,
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
