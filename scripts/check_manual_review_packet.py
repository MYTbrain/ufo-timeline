"""Validate a generated manual-review packet without mutating canonical data."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import re
from typing import Any


DEFAULT_QUEUE_PATH = Path("data/canonical_full/manual_review_queue.jsonl")
DEFAULT_PACKET_PATH = Path("data/reports/manual_review_packet.json")
DEFAULT_CSV_PATH = Path("data/reports/manual_review_packet.csv")
DEFAULT_MARKDOWN_PATH = Path("data/reports/manual_review_packet.md")
DEFAULT_OUTPUT_PATH = Path("data/reports/manual_review_packet_readiness.json")

DEFAULT_FORBIDDEN_PATHS = (
    Path("data/canonical_full/manual_review_decisions.jsonl"),
    Path("data/canonical_full/manual_review_applied_decisions.jsonl"),
    Path("data/canonical_full/manual_review_effects_plan.json"),
    Path("data/canonical_full/manual_review_apply_preview_report.json"),
    Path("data/canonical_full/manual_review_apply_preview_report.jsonl"),
)


def check_manual_review_packet(
    *,
    queue_path: Path = DEFAULT_QUEUE_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
    csv_path: Path = DEFAULT_CSV_PATH,
    markdown_path: Path = DEFAULT_MARKDOWN_PATH,
    forbidden_paths: tuple[Path, ...] = DEFAULT_FORBIDDEN_PATHS,
) -> dict[str, Any]:
    read_errors: list[str] = []
    queue_items = safe_read_jsonl(queue_path, read_errors)
    packet = safe_read_json(packet_path, read_errors)
    csv_rows = safe_read_csv_rows(csv_path, read_errors)
    markdown = safe_read_text(markdown_path, read_errors)

    queue_ids = [str(item.get("review_item_id") or "") for item in queue_items]
    packet_items = packet.get("items") if isinstance(packet.get("items"), list) else []
    packet_ids = [str(item.get("review_item_id") or "") for item in packet_items if isinstance(item, dict)]
    csv_ids = [row.get("review_item_id", "") for row in csv_rows]
    queue_id_set = set(queue_ids)
    packet_id_set = set(packet_ids)
    csv_id_set = set(csv_ids)

    duplicate_queue_ids = sorted(id_ for id_ in queue_id_set if queue_ids.count(id_) > 1)
    duplicate_packet_ids = sorted(id_ for id_ in packet_id_set if packet_ids.count(id_) > 1)
    missing_packet_ids = sorted(queue_id_set - packet_id_set)
    extra_packet_ids = sorted(packet_id_set - queue_id_set)
    csv_missing_ids = sorted(packet_id_set - csv_id_set)
    csv_extra_ids = sorted(csv_id_set - packet_id_set)
    forbidden_existing = sorted(str(path) for path in forbidden_paths if path.exists())
    markdown_item_count = len(re.findall(r"^###\s+", markdown, flags=re.MULTILINE))
    markdown_declares_truncation = (
        len(packet_items) <= markdown_item_count
        or "Markdown view truncated" in markdown
    )

    checks = {
        "queue_exists": queue_path.exists(),
        "packet_exists": packet_path.exists(),
        "csv_exists": csv_path.exists(),
        "markdown_exists": markdown_path.exists(),
        "packet_policy_review_only": packet.get("packet_policy") == "review_only",
        "canonical_outputs_not_mutated": packet.get("canonical_outputs_mutated") is False,
        "decisions_not_created": packet.get("decisions_created") is False,
        "decision_outputs_not_created": packet.get("decision_outputs_created") is False,
        "auto_merge_not_performed": packet.get("auto_merge_performed") is False,
        "input_queue_count_matches": packet.get("input_queue_count") == len(queue_items),
        "exported_item_count_matches": packet.get("exported_item_count") == len(packet_items),
        "packet_contains_all_queue_ids": not missing_packet_ids and not extra_packet_ids,
        "queue_review_ids_present": all(queue_ids),
        "packet_review_ids_present": all(packet_ids),
        "queue_review_ids_unique": not duplicate_queue_ids,
        "packet_review_ids_unique": not duplicate_packet_ids,
        "csv_row_count_matches": len(csv_rows) == len(packet_items),
        "csv_review_ids_match_packet": not csv_missing_ids and not csv_extra_ids,
        "csv_json_fields_parse": csv_json_fields_parse(csv_rows),
        "markdown_review_only_notice_present": "review-only" in markdown.lower(),
        "markdown_safety_flags_present": "- Decisions created: false" in markdown
        and "- Canonical outputs mutated: false" in markdown
        and "- Decision outputs created: false" in markdown
        and "- Auto-merge performed: false" in markdown,
        "markdown_truncation_declared_if_needed": markdown_declares_truncation,
        "no_forbidden_mutation_artifacts": not forbidden_existing,
        "inputs_read_without_errors": not read_errors,
    }

    return {
        "schema_version": 1,
        "status": "ready" if all(checks.values()) else "blocked",
        "checks": checks,
        "counts": {
            "queue_items": len(queue_items),
            "packet_items": len(packet_items),
            "csv_rows": len(csv_rows),
            "markdown_items_rendered": markdown_item_count,
            "forbidden_paths_existing": len(forbidden_existing),
        },
        "inputs": {
            "queue": str(queue_path),
            "packet": str(packet_path),
            "csv": str(csv_path),
            "markdown": str(markdown_path),
            "forbidden_paths": [str(path) for path in forbidden_paths],
        },
        "problems": {
            "duplicate_queue_ids": duplicate_queue_ids,
            "duplicate_packet_ids": duplicate_packet_ids,
            "missing_packet_ids": missing_packet_ids[:100],
            "extra_packet_ids": extra_packet_ids[:100],
            "csv_missing_ids": csv_missing_ids[:100],
            "csv_extra_ids": csv_extra_ids[:100],
            "forbidden_existing": forbidden_existing,
            "read_errors": read_errors,
        },
    }


def safe_read_json(path: Path, read_errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        read_errors.append(f"missing JSON input: {path}")
        return {}
    try:
        return read_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        read_errors.append(f"invalid JSON input {path}: {exc}")
        return {}


def safe_read_jsonl(path: Path, read_errors: list[str]) -> list[dict[str, Any]]:
    if not path.exists():
        read_errors.append(f"missing JSONL input: {path}")
        return []
    try:
        return read_jsonl(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        read_errors.append(f"invalid JSONL input {path}: {exc}")
        return []


def safe_read_csv_rows(path: Path, read_errors: list[str]) -> list[dict[str, str]]:
    if not path.exists():
        read_errors.append(f"missing CSV input: {path}")
        return []
    try:
        return read_csv_rows(path)
    except OSError as exc:
        read_errors.append(f"invalid CSV input {path}: {exc}")
        return []


def safe_read_text(path: Path, read_errors: list[str]) -> str:
    if not path.exists():
        read_errors.append(f"missing Markdown input: {path}")
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        read_errors.append(f"invalid Markdown input {path}: {exc}")
        return ""


def csv_json_fields_parse(rows: list[dict[str, str]]) -> bool:
    json_fields = ("suggested_decisions", "candidate_reasons", "canonical_input_ids", "decision_template_json")
    for row in rows:
        for field in json_fields:
            value = row.get(field, "")
            if not value:
                continue
            try:
                json.loads(value)
            except json.JSONDecodeError:
                return False
    return True


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


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


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV_PATH)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument(
        "--forbidden-path",
        action="append",
        type=Path,
        dest="forbidden_paths",
        default=None,
        help="Additional mutation artifact path that must not exist. Repeatable.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    forbidden_paths = DEFAULT_FORBIDDEN_PATHS
    if args.forbidden_paths:
        forbidden_paths = forbidden_paths + tuple(args.forbidden_paths)
    report = check_manual_review_packet(
        queue_path=args.queue,
        packet_path=args.packet,
        csv_path=args.csv,
        markdown_path=args.markdown,
        forbidden_paths=forbidden_paths,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
