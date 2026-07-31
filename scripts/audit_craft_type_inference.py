"""Audit recoverable craft-type evidence in canonical UFO event rows.

This is report-only. It streams the canonical deduped-event JSONL, derives a
source-preserving craft classification proposal, and writes JSON/Markdown audit
artifacts. It does not mutate canonical rows or shipped web artifacts.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from parser.craft_types import infer_event_craft_type, is_unknownish, normalize_text


DEFAULT_INPUT = Path("data/canonical_full/deduped_events.jsonl")
DEFAULT_OUTPUT_JSON = Path("data/reports/craft_type_inference_audit.json")
DEFAULT_OUTPUT_MD = Path("data/reports/craft_type_inference_audit.md")

SAMPLE_LIMIT_PER_TYPE = 8
TOP_VALUE_LIMIT = 40


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path} line {line_number}: invalid JSON: {exc}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"{path} line {line_number}: expected object")
            yield payload


def sample_event(event: dict[str, Any], inference: dict[str, Any]) -> dict[str, Any]:
    return {
        "canonical_event_id": event.get("canonical_event_id"),
        "date_iso": event.get("date_iso"),
        "location_raw": event.get("location_raw"),
        "source_name": event.get("source_name"),
        "type_normalized": event.get("type_normalized"),
        "type_raw": event.get("type_raw"),
        "shape_normalized": event.get("shape_normalized"),
        "shape_raw": event.get("shape_raw"),
        "description_excerpt": normalize_text(event.get("description"))[:220],
        "craft_type_inferred": inference.get("craft_type_inferred"),
        "craft_type_confidence": inference.get("craft_type_confidence"),
        "craft_type_source": inference.get("craft_type_source"),
        "same_day_match_strength": inference.get("same_day_match_strength"),
        "craft_type_reason": inference.get("craft_type_reason"),
    }


def audit(input_path: Path, *, limit: int | None = None) -> dict[str, Any]:
    total = 0
    type_unknown_count = 0
    shape_unknown_count = 0
    either_unknown_count = 0
    both_unknown_count = 0
    recovered_either_unknown = 0
    recovered_both_unknown = 0

    type_counts: Counter[str] = Counter()
    shape_counts: Counter[str] = Counter()
    unknown_type_raw_counts: Counter[str] = Counter()
    unknown_shape_raw_counts: Counter[str] = Counter()
    inference_counts: Counter[str] = Counter()
    confidence_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    same_day_strength_counts: Counter[str] = Counter()
    recovered_unknown_counts: Counter[str] = Counter()
    recovered_unknown_confidence_counts: Counter[str] = Counter()
    samples: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for event in iter_jsonl(input_path):
        total += 1
        if limit is not None and total > limit:
            total -= 1
            break

        type_value = event.get("type_normalized") or event.get("type_raw") or ""
        shape_value = event.get("shape_normalized") or event.get("shape_raw") or ""
        type_key = normalize_text(type_value) or "Unknown"
        shape_key = normalize_text(shape_value) or "Unknown"
        type_counts[type_key] += 1
        shape_counts[shape_key] += 1

        type_unknown = is_unknownish(type_value)
        shape_unknown = is_unknownish(shape_value)
        if type_unknown:
            type_unknown_count += 1
            unknown_type_raw_counts[normalize_text(event.get("type_raw")) or "Unknown"] += 1
        if shape_unknown:
            shape_unknown_count += 1
            unknown_shape_raw_counts[normalize_text(event.get("shape_raw")) or "Unknown"] += 1
        if type_unknown or shape_unknown:
            either_unknown_count += 1
        if type_unknown and shape_unknown:
            both_unknown_count += 1

        inference = infer_event_craft_type(event)
        inferred = str(inference.get("craft_type_inferred") or "unknown")
        confidence = str(inference.get("craft_type_confidence") or "none")
        inference_counts[inferred] += 1
        confidence_counts[confidence] += 1
        source_counts[str(inference.get("craft_type_source") or "none")] += 1
        same_day_strength_counts[str(inference.get("same_day_match_strength") or "none")] += 1

        if (type_unknown or shape_unknown) and inferred != "unknown":
            recovered_either_unknown += 1
            recovered_unknown_counts[inferred] += 1
            recovered_unknown_confidence_counts[confidence] += 1
        if type_unknown and shape_unknown and inferred != "unknown":
            recovered_both_unknown += 1

        if inferred != "unknown" and len(samples[inferred]) < SAMPLE_LIMIT_PER_TYPE:
            samples[inferred].append(sample_event(event, inference))

    return {
        "schema_version": 1,
        "analysis_policy": "report_only_source_preserving",
        "canonical_outputs_mutated": False,
        "inputs": {"deduped_events": str(input_path), "limit": limit},
        "summary": {
            "total_events_scanned": total,
            "type_unknown_count": type_unknown_count,
            "shape_unknown_count": shape_unknown_count,
            "type_or_shape_unknown_count": either_unknown_count,
            "type_and_shape_unknown_count": both_unknown_count,
            "recoverable_type_or_shape_unknown_count": recovered_either_unknown,
            "recoverable_type_and_shape_unknown_count": recovered_both_unknown,
            "recoverable_type_or_shape_unknown_share": safe_ratio(recovered_either_unknown, either_unknown_count),
            "recoverable_type_and_shape_unknown_share": safe_ratio(recovered_both_unknown, both_unknown_count),
        },
        "craft_type_counts": dict(inference_counts.most_common()),
        "craft_type_confidence_counts": dict(confidence_counts.most_common()),
        "craft_type_source_counts": dict(source_counts.most_common()),
        "same_day_match_strength_counts": dict(same_day_strength_counts.most_common()),
        "recoverable_unknown_craft_type_counts": dict(recovered_unknown_counts.most_common()),
        "recoverable_unknown_confidence_counts": dict(recovered_unknown_confidence_counts.most_common()),
        "top_type_values": dict(type_counts.most_common(TOP_VALUE_LIMIT)),
        "top_shape_values": dict(shape_counts.most_common(TOP_VALUE_LIMIT)),
        "top_unknown_type_raw_values": dict(unknown_type_raw_counts.most_common(TOP_VALUE_LIMIT)),
        "top_unknown_shape_raw_values": dict(unknown_shape_raw_counts.most_common(TOP_VALUE_LIMIT)),
        "samples_by_inferred_type": dict(samples),
        "notes": [
            "This audit proposes derived craft-type fields only; original source type/shape/date/time text remains unchanged.",
            "Low-confidence generic light/fireball labels should not be used as strong same-day matching evidence.",
            "Use medium/high confidence and same_day_match_strength medium/strong for future trace or same-day chronology linkage.",
        ],
    }


def safe_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 6)


def write_markdown(report: dict[str, Any], output_path: Path) -> None:
    summary = report["summary"]
    lines = [
        "# Craft Type Inference Audit",
        "",
        "This is a source-preserving audit. It does not mutate canonical event data or web artifacts.",
        "",
        "## Summary",
        "",
        f"- Events scanned: `{summary['total_events_scanned']:,}`",
        f"- Type unknown: `{summary['type_unknown_count']:,}`",
        f"- Shape unknown: `{summary['shape_unknown_count']:,}`",
        f"- Type or shape unknown: `{summary['type_or_shape_unknown_count']:,}`",
        f"- Type and shape unknown: `{summary['type_and_shape_unknown_count']:,}`",
        f"- Recoverable type/shape unknown: `{summary['recoverable_type_or_shape_unknown_count']:,}` "
        f"({summary['recoverable_type_or_shape_unknown_share']:.1%})",
        f"- Recoverable both-unknown: `{summary['recoverable_type_and_shape_unknown_count']:,}` "
        f"({summary['recoverable_type_and_shape_unknown_share']:.1%})",
        "",
        "## Derived Craft Type Counts",
        "",
    ]
    for key, count in list(report["craft_type_counts"].items())[:25]:
        lines.append(f"- `{key}`: `{count:,}`")

    lines.extend(["", "## Recoverable Unknown Counts", ""])
    for key, count in list(report["recoverable_unknown_craft_type_counts"].items())[:25]:
        lines.append(f"- `{key}`: `{count:,}`")

    lines.extend(["", "## Confidence Counts", ""])
    for key, count in report["craft_type_confidence_counts"].items():
        lines.append(f"- `{key}`: `{count:,}`")

    lines.extend(["", "## Recommended Rollout", ""])
    lines.extend([
        "1. Add derived fields during canonical/web artifact generation: `craft_type_inferred`, `craft_type_confidence`, `craft_type_source`, `same_day_match_strength`.",
        "2. Preserve original `type_raw`, `type_normalized`, `shape_raw`, and `shape_normalized` display text.",
        "3. Add a craft-shape filter/color mode that uses derived fields only when confidence is not `none`.",
        "4. Use only medium/high confidence and medium/strong same-day match strength for trace/same-day sequencing support.",
        "5. Keep an `Unknown` bucket for genuinely unresolved events; do not force generic light sightings into specific craft classes.",
    ])

    lines.extend(["", "## Samples", ""])
    for craft_type, examples in report["samples_by_inferred_type"].items():
        lines.append(f"### {craft_type}")
        lines.append("")
        for item in examples[:5]:
            lines.append(
                "- "
                f"`{item.get('canonical_event_id')}` "
                f"`{item.get('date_iso')}` "
                f"{item.get('location_raw') or 'Unknown location'}; "
                f"source `{item.get('craft_type_source')}`, confidence `{item.get('craft_type_confidence')}`; "
                f"{item.get('description_excerpt') or ''}"
            )
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    report = audit(args.input, limit=args.limit)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(report, args.output_md)
    print(json.dumps({"output_json": str(args.output_json), "output_md": str(args.output_md), "summary": report["summary"]}, indent=2))


if __name__ == "__main__":
    main()
