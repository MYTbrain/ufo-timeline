"""Audit app-facing Unknown craft/type rows by source.

This report is intentionally read-only. It identifies which source catalogs and
raw fields dominate the remaining app-facing ``Unknown`` pool after derived
craft-type inference, so the next classification pass can target source-specific
decoders instead of broad risky regex.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import re
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from parser.craft_types import infer_event_craft_type, is_unknownish, normalize_text
from parser.taxonomy import display_type_for_web_event, visual_type_group_for_web_event


DEFAULT_INPUT = Path("data/canonical_full/deduped_events.jsonl")
DEFAULT_OUTPUT_JSON = Path("data/reports/unresolved_craft_type_by_source_audit.json")
DEFAULT_OUTPUT_MD = Path("data/reports/unresolved_craft_type_by_source_audit.md")
DEFAULT_OUTPUT_CSV = Path("data/reports/unresolved_craft_type_by_source_audit.csv")

TOP_VALUE_LIMIT = 25
SOURCE_SAMPLE_LIMIT = 8

RAW_EVIDENCE_KEY_RE = re.compile(
    r"(type|shape|object|class|category|hynek|vallee|form|craft|phenomen|ufo|description|summary|movement)",
    re.I,
)
PROSAIC_CUE_RE = re.compile(
    r"\b("
    r"aircraft|airplane|aeroplane|plane|helicopter|"
    r"balloon|weather balloon|kite|bird|drone|"
    r"satellite|starlink|venus|mars|moon|"
    r"meteor shower|bolide|rocket launch|flare|"
    r"hoax|misidentification|identified as|explained as|probably a"
    r")\b",
    re.I,
)


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


def source_key(event: dict[str, Any]) -> str:
    return normalize_text(event.get("source_name")).lower() or "unknown"


def is_app_facing_unknown(event: dict[str, Any]) -> bool:
    if display_type_for_web_event(event) is None:
        return True
    return visual_type_group_for_web_event(event) == "Other / unknown"


def text_has_prosaic_cue(event: dict[str, Any]) -> bool:
    parts = [
        event.get("type_raw"),
        event.get("type_normalized"),
        event.get("shape_raw"),
        event.get("shape_normalized"),
        event.get("description"),
        event.get("summary"),
    ]
    raw_fields = event.get("raw_fields")
    if isinstance(raw_fields, dict):
        parts.extend(raw_fields.values())
    haystack = " ".join(normalize_text(value) for value in parts if value is not None)
    return bool(PROSAIC_CUE_RE.search(haystack))


def raw_evidence_pairs(event: dict[str, Any]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for key in ("type_raw", "type_normalized", "shape_raw", "shape_normalized", "summary"):
        value = normalize_text(event.get(key))
        if value and not is_unknownish(value):
            pairs.append((key, value[:120]))
    raw_fields = event.get("raw_fields")
    if isinstance(raw_fields, dict):
        for key, value in raw_fields.items():
            if not key or value is None:
                continue
            key_text = normalize_text(key)
            value_text = normalize_text(value)
            if not value_text or is_unknownish(value_text):
                continue
            if RAW_EVIDENCE_KEY_RE.search(key_text):
                pairs.append((f"raw_fields.{key_text}", value_text[:120]))
    return pairs


def sample_event(event: dict[str, Any], inference: dict[str, Any]) -> dict[str, Any]:
    raw_fields = event.get("raw_fields")
    raw_excerpt: dict[str, str] = {}
    if isinstance(raw_fields, dict):
        for key, value in raw_fields.items():
            if len(raw_excerpt) >= 8:
                break
            value_text = normalize_text(value)
            if value_text:
                raw_excerpt[normalize_text(key)[:80]] = value_text[:220]
    return {
        "canonical_event_id": event.get("canonical_event_id"),
        "date_iso": event.get("date_iso"),
        "location_raw": event.get("location_raw"),
        "source_name": event.get("source_name"),
        "type_raw": event.get("type_raw"),
        "type_normalized": event.get("type_normalized"),
        "shape_raw": event.get("shape_raw"),
        "shape_normalized": event.get("shape_normalized"),
        "description_excerpt": normalize_text(event.get("description"))[:240],
        "summary": event.get("summary"),
        "craft_type_reason": inference.get("craft_type_reason"),
        "prosaic_cue_present": text_has_prosaic_cue(event),
        "raw_fields_excerpt": raw_excerpt,
    }


def new_source_bucket() -> dict[str, Any]:
    return {
        "total_events": 0,
        "app_unknown_events": 0,
        "derived_unknown_events": 0,
        "app_unknown_recovered_events": 0,
        "app_unknown_still_unresolved_events": 0,
        "prosaic_cue_events": 0,
        "no_direct_shape_evidence_events": 0,
        "recovered_type_counts": Counter(),
        "raw_type_values": Counter(),
        "raw_shape_values": Counter(),
        "raw_evidence_keys": Counter(),
        "raw_evidence_values": Counter(),
        "samples": [],
    }


def audit(input_path: Path, *, limit: int | None = None) -> dict[str, Any]:
    totals = Counter()
    source_buckets: dict[str, dict[str, Any]] = defaultdict(new_source_bucket)
    global_raw_evidence_keys: Counter[str] = Counter()
    global_raw_evidence_values: Counter[str] = Counter()
    still_unresolved_samples: list[dict[str, Any]] = []

    for index, event in enumerate(iter_jsonl(input_path), start=1):
        if limit is not None and index > limit:
            break
        totals["events_scanned"] += 1
        source = source_key(event)
        bucket = source_buckets[source]
        bucket["total_events"] += 1

        app_unknown = is_app_facing_unknown(event)
        inference = infer_event_craft_type(event)
        derived_unknown = inference.get("craft_type_inferred") == "unknown"

        if app_unknown:
            totals["app_unknown_events"] += 1
            bucket["app_unknown_events"] += 1
        if derived_unknown:
            totals["derived_unknown_events"] += 1
            bucket["derived_unknown_events"] += 1
        if app_unknown and not derived_unknown:
            totals["app_unknown_recovered_events"] += 1
            bucket["app_unknown_recovered_events"] += 1
            inferred = str(inference.get("craft_type_inferred") or "unknown")
            bucket["recovered_type_counts"][inferred] += 1
        if app_unknown and derived_unknown:
            totals["app_unknown_still_unresolved_events"] += 1
            bucket["app_unknown_still_unresolved_events"] += 1
            if len(still_unresolved_samples) < SOURCE_SAMPLE_LIMIT:
                still_unresolved_samples.append(sample_event(event, inference))

            type_value = normalize_text(event.get("type_raw") or event.get("type_normalized")) or "Unknown"
            shape_value = normalize_text(event.get("shape_raw") or event.get("shape_normalized")) or "Unknown"
            bucket["raw_type_values"][type_value] += 1
            bucket["raw_shape_values"][shape_value] += 1

            evidence_pairs = raw_evidence_pairs(event)
            if not evidence_pairs and not normalize_text(event.get("description")):
                totals["no_direct_shape_evidence_events"] += 1
                bucket["no_direct_shape_evidence_events"] += 1
            for key, value in evidence_pairs:
                bucket["raw_evidence_keys"][key] += 1
                bucket["raw_evidence_values"][f"{key}: {value}"] += 1
                global_raw_evidence_keys[key] += 1
                global_raw_evidence_values[f"{key}: {value}"] += 1

            if text_has_prosaic_cue(event):
                totals["prosaic_cue_events"] += 1
                bucket["prosaic_cue_events"] += 1

            if len(bucket["samples"]) < SOURCE_SAMPLE_LIMIT:
                bucket["samples"].append(sample_event(event, inference))

    source_rows = []
    for source, bucket in source_buckets.items():
        unresolved = int(bucket["app_unknown_still_unresolved_events"])
        if unresolved <= 0:
            continue
        source_rows.append({
            "source_name": source,
            "total_events": int(bucket["total_events"]),
            "app_unknown_events": int(bucket["app_unknown_events"]),
            "derived_unknown_events": int(bucket["derived_unknown_events"]),
            "app_unknown_recovered_events": int(bucket["app_unknown_recovered_events"]),
            "app_unknown_still_unresolved_events": unresolved,
            "app_unknown_recovery_share": safe_ratio(
                int(bucket["app_unknown_recovered_events"]),
                int(bucket["app_unknown_events"]),
            ),
            "prosaic_cue_events": int(bucket["prosaic_cue_events"]),
            "no_direct_shape_evidence_events": int(bucket["no_direct_shape_evidence_events"]),
            "top_recovered_types": dict(bucket["recovered_type_counts"].most_common(TOP_VALUE_LIMIT)),
            "top_raw_type_values": dict(bucket["raw_type_values"].most_common(TOP_VALUE_LIMIT)),
            "top_raw_shape_values": dict(bucket["raw_shape_values"].most_common(TOP_VALUE_LIMIT)),
            "top_raw_evidence_keys": dict(bucket["raw_evidence_keys"].most_common(TOP_VALUE_LIMIT)),
            "top_raw_evidence_values": dict(bucket["raw_evidence_values"].most_common(TOP_VALUE_LIMIT)),
            "samples": bucket["samples"],
        })
    source_rows.sort(key=lambda row: row["app_unknown_still_unresolved_events"], reverse=True)

    summary = {
        "events_scanned": int(totals["events_scanned"]),
        "app_unknown_events": int(totals["app_unknown_events"]),
        "derived_unknown_events": int(totals["derived_unknown_events"]),
        "app_unknown_recovered_events": int(totals["app_unknown_recovered_events"]),
        "app_unknown_still_unresolved_events": int(totals["app_unknown_still_unresolved_events"]),
        "app_unknown_recovery_share": safe_ratio(
            int(totals["app_unknown_recovered_events"]),
            int(totals["app_unknown_events"]),
        ),
        "prosaic_cue_events_in_still_unresolved": int(totals["prosaic_cue_events"]),
        "no_direct_shape_evidence_events": int(totals["no_direct_shape_evidence_events"]),
    }
    return {
        "schema_version": 1,
        "analysis_policy": "report_only_no_source_mutation",
        "canonical_outputs_mutated": False,
        "inputs": {"deduped_events": str(input_path), "limit": limit},
        "summary": summary,
        "sources_by_remaining_unknown": source_rows,
        "top_unresolved_raw_evidence_keys": dict(global_raw_evidence_keys.most_common(TOP_VALUE_LIMIT)),
        "top_unresolved_raw_evidence_values": dict(global_raw_evidence_values.most_common(TOP_VALUE_LIMIT)),
        "global_still_unresolved_samples": still_unresolved_samples,
        "recommended_next_steps": build_recommendations(source_rows, summary),
    }


def build_recommendations(source_rows: list[dict[str, Any]], summary: dict[str, Any]) -> list[str]:
    recommendations = [
        "Do not broaden generic regex until source-specific raw fields are decoded.",
        "Keep source-displayed type/shape text unchanged; add only derived craft-type fields.",
    ]
    if source_rows:
        top = source_rows[0]
        recommendations.append(
            f"Prioritize source `{top['source_name']}`; it has "
            f"{top['app_unknown_still_unresolved_events']:,} still-unresolved app-facing Unknown rows."
        )
    prosaic = int(summary.get("prosaic_cue_events_in_still_unresolved") or 0)
    if prosaic:
        recommendations.append(
            f"Consider a separate non-craft/prosaic derived bucket for {prosaic:,} unresolved rows with conventional-object cues."
        )
    return recommendations


def safe_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 6)


def write_csv(report: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "source_name",
            "total_events",
            "app_unknown_events",
            "app_unknown_recovered_events",
            "app_unknown_still_unresolved_events",
            "app_unknown_recovery_share",
            "prosaic_cue_events",
            "no_direct_shape_evidence_events",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in report["sources_by_remaining_unknown"]:
            writer.writerow({key: row.get(key) for key in fieldnames})


def write_markdown(report: dict[str, Any], output_path: Path) -> None:
    summary = report["summary"]
    lines = [
        "# Unresolved Craft Type By Source Audit",
        "",
        "This is a source-preserving report. It does not mutate canonical rows or shipped web artifacts.",
        "",
        "## Summary",
        "",
        f"- Events scanned: `{summary['events_scanned']:,}`",
        f"- App-facing Unknown events: `{summary['app_unknown_events']:,}`",
        f"- Recovered from app-facing Unknown by derived craft inference: `{summary['app_unknown_recovered_events']:,}` "
        f"({summary['app_unknown_recovery_share']:.1%})",
        f"- Still unresolved app-facing Unknown events: `{summary['app_unknown_still_unresolved_events']:,}`",
        f"- Still-unresolved rows with prosaic/conventional cues: `{summary['prosaic_cue_events_in_still_unresolved']:,}`",
        f"- Still-unresolved rows with no direct shape/type/description evidence: `{summary['no_direct_shape_evidence_events']:,}`",
        "",
        "## Source Priority",
        "",
    ]
    for row in report["sources_by_remaining_unknown"][:15]:
        lines.append(
            "- "
            f"`{row['source_name']}`: `{row['app_unknown_still_unresolved_events']:,}` still unresolved; "
            f"`{row['app_unknown_recovered_events']:,}` recovered; "
            f"`{row['app_unknown_recovery_share']:.1%}` recovery share"
        )

    lines.extend(["", "## Top Unresolved Raw Evidence Keys", ""])
    for key, count in report["top_unresolved_raw_evidence_keys"].items():
        lines.append(f"- `{key}`: `{count:,}`")

    lines.extend(["", "## Per-Source Raw Evidence Targets", ""])
    for row in report["sources_by_remaining_unknown"][:8]:
        lines.extend(["", f"### {row['source_name']}", ""])
        lines.append(f"- Still unresolved: `{row['app_unknown_still_unresolved_events']:,}`")
        lines.append(f"- Prosaic/conventional cues: `{row['prosaic_cue_events']:,}`")
        lines.append(f"- No direct shape evidence: `{row['no_direct_shape_evidence_events']:,}`")
        if row["top_raw_type_values"]:
            lines.append("- Top raw type values: " + ", ".join(
                f"`{key}` (`{value:,}`)" for key, value in list(row["top_raw_type_values"].items())[:8]
            ))
        if row["top_raw_shape_values"]:
            lines.append("- Top raw shape values: " + ", ".join(
                f"`{key}` (`{value:,}`)" for key, value in list(row["top_raw_shape_values"].items())[:8]
            ))
        if row["top_raw_evidence_keys"]:
            lines.append("- Top raw evidence keys: " + ", ".join(
                f"`{key}` (`{value:,}`)" for key, value in list(row["top_raw_evidence_keys"].items())[:8]
            ))

    lines.extend(["", "## Recommendations", ""])
    for item in report["recommended_next_steps"]:
        lines.append(f"- {item}")

    lines.extend(["", "## Still-Unresolved Samples", ""])
    for row in report["sources_by_remaining_unknown"][:5]:
        lines.extend(["", f"### {row['source_name']}", ""])
        for item in row["samples"][:5]:
            lines.append(
                "- "
                f"`{item.get('canonical_event_id')}` "
                f"`{item.get('date_iso')}` "
                f"{item.get('location_raw') or 'Unknown location'}; "
                f"type `{item.get('type_raw') or item.get('type_normalized') or 'Unknown'}`; "
                f"shape `{item.get('shape_raw') or item.get('shape_normalized') or 'Unknown'}`; "
                f"{item.get('description_excerpt') or ''}"
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    report = audit(args.input, limit=args.limit)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(report, args.output_md)
    write_csv(report, args.output_csv)
    print(json.dumps({
        "output_json": str(args.output_json),
        "output_md": str(args.output_md),
        "output_csv": str(args.output_csv),
        "summary": report["summary"],
        "top_sources": [
            {
                "source_name": row["source_name"],
                "still_unresolved": row["app_unknown_still_unresolved_events"],
                "recovered": row["app_unknown_recovered_events"],
            }
            for row in report["sources_by_remaining_unknown"][:5]
        ],
    }, indent=2))


if __name__ == "__main__":
    main()
