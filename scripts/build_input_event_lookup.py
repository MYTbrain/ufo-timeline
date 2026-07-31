"""Build a compact canonical-input to canonical-event lookup artifact.

The lookup is a derived acceleration artifact for analysis/review tools. It
does not make merge decisions or mutate the canonical deduped-event source.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from parser.canonical_schema import clean_text
from parser.utils import ensure_parent_dir


DEFAULT_DEDUPED_EVENTS_PATH = Path("data/canonical_full/deduped_events.jsonl")
DEFAULT_LOOKUP_OUTPUT_PATH = Path("data/canonical_full/input_event_lookup.jsonl")
DEFAULT_REPORT_OUTPUT_PATH = Path("data/reports/input_event_lookup_report.json")
LOOKUP_SCHEMA_VERSION = 1


def build_input_event_lookup(
    *,
    deduped_events_path: Path = DEFAULT_DEDUPED_EVENTS_PATH,
    lookup_output_path: Path = DEFAULT_LOOKUP_OUTPUT_PATH,
    report_output_path: Path = DEFAULT_REPORT_OUTPUT_PATH,
    limit: int | None = None,
) -> dict[str, Any]:
    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative")

    ensure_parent_dir(lookup_output_path)
    ensure_parent_dir(report_output_path)
    tmp_lookup_path = lookup_output_path.with_suffix(lookup_output_path.suffix + ".tmp")

    event_count = 0
    source_record_count_from_events = 0
    lookup_row_count = 0
    duplicate_input_id_count = 0
    conflicting_input_id_count = 0
    missing_event_id_count = 0
    missing_input_id_count = 0
    seen_input_to_event: dict[str, str] = {}
    event_ids_with_multiple_inputs = 0
    duplicate_input_samples: list[dict[str, str]] = []
    conflict_samples: list[dict[str, str]] = []

    with tmp_lookup_path.open("w", encoding="utf-8", newline="\n") as output:
        for event in iter_jsonl(deduped_events_path, limit=limit):
            event_count += 1
            event_id = clean_text(event.get("canonical_event_id")) or clean_text(event.get("event_id"))
            if not event_id:
                missing_event_id_count += 1
                continue
            input_ids = normalized_id_list(event.get("canonical_input_ids"))
            if not input_ids:
                missing_input_id_count += 1
                continue
            source_record_count_from_events += len(input_ids)
            if len(input_ids) > 1:
                event_ids_with_multiple_inputs += 1
            for input_id in input_ids:
                prior_event_id = seen_input_to_event.get(input_id)
                if prior_event_id:
                    duplicate_input_id_count += 1
                    if len(duplicate_input_samples) < 20:
                        duplicate_input_samples.append(
                            {
                                "canonical_input_id": input_id,
                                "first_canonical_event_id": prior_event_id,
                                "duplicate_canonical_event_id": event_id,
                            }
                        )
                    if prior_event_id != event_id:
                        conflicting_input_id_count += 1
                        if len(conflict_samples) < 20:
                            conflict_samples.append(
                                {
                                    "canonical_input_id": input_id,
                                    "first_canonical_event_id": prior_event_id,
                                    "conflicting_canonical_event_id": event_id,
                                }
                            )
                    continue
                seen_input_to_event[input_id] = event_id
                output.write(
                    json.dumps(
                        {
                            "canonical_input_id": input_id,
                            "canonical_event_id": event_id,
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    + "\n"
                )
                lookup_row_count += 1

    tmp_lookup_path.replace(lookup_output_path)
    report = {
        "schema_version": 1,
        "lookup_schema_version": LOOKUP_SCHEMA_VERSION,
        "report_policy": "input_event_lookup_build_report",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "inputs": {
            "deduped_events": str(deduped_events_path),
            "limit": limit,
        },
        "outputs": {
            "input_event_lookup": str(lookup_output_path),
            "report": str(report_output_path),
        },
        "summary": {
            "event_count": event_count,
            "source_record_count_from_events": source_record_count_from_events,
            "lookup_row_count": lookup_row_count,
            "exact_duplicate_record_reduction": source_record_count_from_events - event_count,
            "event_ids_with_multiple_inputs": event_ids_with_multiple_inputs,
            "duplicate_input_id_count": duplicate_input_id_count,
            "conflicting_input_id_count": conflicting_input_id_count,
            "missing_event_id_count": missing_event_id_count,
            "missing_input_id_count": missing_input_id_count,
            "lookup_complete": limit is None,
        },
        "samples": {
            "duplicate_input_ids": duplicate_input_samples,
            "conflicting_input_ids": conflict_samples,
        },
        "notes": [
            "This lookup is a derived acceleration artifact for review/analysis tools.",
            "It maps each canonical_input_id to its current canonical_event_id from deduped_events.jsonl.",
            "It does not apply merges, create decisions, or replace deduped_events.jsonl as the authoritative source.",
        ],
    }
    report_output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def iter_jsonl(path: Path, *, limit: int | None = None) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if limit is not None and line_number > limit:
                break
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{path} line {line_number} must be a JSON object.")
            yield payload


def normalized_id_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := clean_text(item))]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deduped-events", type=Path, default=DEFAULT_DEDUPED_EVENTS_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_LOOKUP_OUTPUT_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_OUTPUT_PATH)
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_input_event_lookup(
        deduped_events_path=args.deduped_events,
        lookup_output_path=args.output,
        report_output_path=args.report,
        limit=args.limit,
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "report": str(args.report),
                "event_count": report["summary"]["event_count"],
                "lookup_row_count": report["summary"]["lookup_row_count"],
                "duplicate_input_id_count": report["summary"]["duplicate_input_id_count"],
                "conflicting_input_id_count": report["summary"]["conflicting_input_id_count"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
