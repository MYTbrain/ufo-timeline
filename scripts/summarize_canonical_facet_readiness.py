"""Summarize browser-facing facet readiness from canonical web artifacts.

This is report-only. It does not modify app config, runtime behavior, or
canonical event data.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_MANIFEST = Path("data/canonical_web/canonical_web_manifest.json")
DEFAULT_SUMMARY_MANIFEST = Path("data/canonical_web/summary_manifest.json")
DEFAULT_SUMMARY_SHARDS_DIR = Path("data/canonical_web/summary_shards")
DEFAULT_OUTPUT = Path("data/reports/canonical_facet_readiness.json")

UNKNOWN_LABELS = {"", "unknown", "other / unknown"}
SUMMARY_COUNT_FIELDS = (
    "visual_type_group",
    "time_sort_kind",
    "time_sort_confidence",
    "playback_sort_confidence",
    "playback_sort_reason",
)
REQUIRED_COUNT_FACETS = (
    "source",
    "date_precision",
    "location_precision",
    "coordinate_source",
)


def summarize_canonical_facet_readiness(
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    summary_manifest_path: Path = DEFAULT_SUMMARY_MANIFEST,
    summary_shards_dir: Path = DEFAULT_SUMMARY_SHARDS_DIR,
    scan_summary_shards: bool = False,
) -> dict[str, Any]:
    manifest = read_json_object(manifest_path)
    counts = manifest.get("counts") if isinstance(manifest.get("counts"), dict) else {}
    event_count = int(counts.get("events") or 0)
    mapped_event_count = int(counts.get("mapped_events") or 0)
    summary_sample = read_first_summary_event(summary_manifest_path, summary_shards_dir)
    summary_counts = (
        count_summary_fields(summary_manifest_path, summary_shards_dir, SUMMARY_COUNT_FIELDS)
        if scan_summary_shards
        else {}
    )

    facets = {
        "source": summarize_count_facet("source", counts.get("source_counts"), event_count),
        "type": summarize_count_facet("type", counts.get("type_counts"), event_count),
        "shape": summarize_count_facet("shape_normalized", counts.get("shape_counts"), event_count),
        "date_precision": summarize_count_facet("date_precision", counts.get("date_precision_counts"), event_count),
        "location_precision": summarize_count_facet(
            "location_precision",
            counts.get("location_precision_counts"),
            event_count,
        ),
        "coordinate_source": summarize_count_facet(
            "coordinate_source",
            counts.get("coordinate_source_counts"),
            event_count,
        ),
        "visual_type_group": summarize_summary_field("visual_type_group", summary_sample, summary_counts, event_count),
        "time_sort_kind": summarize_summary_field("time_sort_kind", summary_sample, summary_counts, event_count),
        "time_sort_confidence": summarize_summary_field("time_sort_confidence", summary_sample, summary_counts, event_count),
        "playback_sort_confidence": summarize_summary_field(
            "playback_sort_confidence",
            summary_sample,
            summary_counts,
            event_count,
        ),
        "playback_sort_reason": summarize_summary_field("playback_sort_reason", summary_sample, summary_counts, event_count),
    }

    recommended_ui_order = [
        name
        for name in (
            "source",
            "date_precision",
            "location_precision",
            "coordinate_source",
            "visual_type_group",
            "type",
            "shape",
            "time_sort_kind",
            "playback_sort_confidence",
        )
        if facets.get(name, {}).get("status") in {"ready", "ready_with_caveat"}
    ]

    caveats = []
    for name, facet in facets.items():
        if facet.get("unknown_share", 0) >= 0.5:
            caveats.append(f"{name} has high unknown coverage; expose it as optional/advanced or pair with provenance.")
        if facet.get("status") == "sample_field_present":
            caveats.append(f"{name} is present in summary shards but does not yet have manifest-level counts.")
    required_count_facets_ready = event_count > 0 and all(
        facets.get(name, {}).get("status") in {"ready", "ready_with_caveat"}
        and facets.get(name, {}).get("counted_events", 0) > 0
        for name in REQUIRED_COUNT_FACETS
    )

    return {
        "schema_version": 1,
        "status": "ready_with_caveats" if required_count_facets_ready else "blocked",
        "inputs": {
            "manifest": str(manifest_path),
            "summary_manifest": str(summary_manifest_path),
            "summary_shards_dir": str(summary_shards_dir),
        },
        "counts": {
            "events": event_count,
            "mapped_events": mapped_event_count,
            "summary_shards": int(counts.get("summary_shards") or 0),
        },
        "facets": facets,
        "recommended_ui_order": recommended_ui_order,
        "caveats": sorted(set(caveats)),
        "policy": {
            "report_only": True,
            "runtime_behavior_changed": False,
            "canonical_outputs_mutated": False,
            "required_count_facets": list(REQUIRED_COUNT_FACETS),
            "required_count_facets_ready": required_count_facets_ready,
            "summary_shards_scanned": scan_summary_shards,
            "facet_counts_source": "canonical_web_manifest counts plus summary-shard counts"
            if scan_summary_shards
            else "canonical_web_manifest counts plus one summary-shard field-presence sample",
        },
    }


def summarize_count_facet(name: str, raw_counts: Any, event_count: int) -> dict[str, Any]:
    counts = normalize_counts(raw_counts)
    total = sum(counts.values())
    unknown_count = sum(count for label, count in counts.items() if label.strip().lower() in UNKNOWN_LABELS)
    unknown_share = (unknown_count / total) if total else 0.0
    status = "ready"
    if not counts:
        status = "missing"
    elif unknown_share >= 0.5:
        status = "ready_with_caveat"
    return {
        "field": name,
        "status": status,
        "distinct_values": len(counts),
        "counted_events": total,
        "coverage_share": round((total / event_count), 6) if event_count else 0.0,
        "unknown_count": unknown_count,
        "unknown_share": round(unknown_share, 6),
        "top_values": top_values(counts),
    }


def summarize_summary_field(
    name: str,
    sample: dict[str, Any],
    summary_counts: dict[str, dict[str, int]],
    event_count: int,
) -> dict[str, Any]:
    counts = summary_counts.get(name)
    if counts is not None:
        facet = summarize_count_facet(name, counts, event_count)
        facet["manifest_level_counts"] = False
        facet["summary_shard_counts"] = True
        return facet
    value = sample.get(name)
    return {
        "field": name,
        "status": "sample_field_present" if value is not None else "missing",
        "sample_value": value,
        "manifest_level_counts": False,
        "summary_shard_counts": False,
    }


def normalize_counts(raw_counts: Any) -> dict[str, int]:
    if not isinstance(raw_counts, dict):
        return {}
    counts: dict[str, int] = {}
    for key, value in raw_counts.items():
        label = str(key or "").strip() or "Unknown"
        counts[label] = counts.get(label, 0) + int(value or 0)
    return counts


def top_values(counts: dict[str, int], *, limit: int = 12) -> list[dict[str, Any]]:
    total = sum(counts.values())
    values = []
    for label, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]:
        values.append({
            "label": label,
            "count": count,
            "share": round((count / total), 6) if total else 0.0,
        })
    return values


def read_first_summary_event(summary_manifest_path: Path, summary_shards_dir: Path) -> dict[str, Any]:
    if not summary_manifest_path.exists():
        return {}
    summary_manifest = json.loads(summary_manifest_path.read_text(encoding="utf-8"))
    if not isinstance(summary_manifest, list) or not summary_manifest:
        return {}
    first_file = summary_manifest[0].get("file") if isinstance(summary_manifest[0], dict) else None
    if not first_file:
        return {}
    shard_path = summary_shards_dir / str(first_file)
    if not shard_path.exists():
        return {}
    shard = json.loads(shard_path.read_text(encoding="utf-8"))
    if not isinstance(shard, list) or not shard or not isinstance(shard[0], dict):
        return {}
    return shard[0]


def count_summary_fields(
    summary_manifest_path: Path,
    summary_shards_dir: Path,
    fields: tuple[str, ...],
) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {field: {} for field in fields}
    if not summary_manifest_path.exists():
        return counts
    summary_manifest = json.loads(summary_manifest_path.read_text(encoding="utf-8"))
    if not isinstance(summary_manifest, list):
        return counts
    for entry in summary_manifest:
        if not isinstance(entry, dict) or not entry.get("file"):
            continue
        shard_path = summary_shards_dir / str(entry["file"])
        if not shard_path.exists():
            continue
        shard = json.loads(shard_path.read_text(encoding="utf-8"))
        if not isinstance(shard, list):
            continue
        for event in shard:
            if not isinstance(event, dict):
                continue
            for field in fields:
                label = str(event.get(field) or "Unknown")
                field_counts = counts[field]
                field_counts[label] = field_counts.get(label, 0) + 1
    return counts


def read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--summary-manifest", type=Path, default=DEFAULT_SUMMARY_MANIFEST)
    parser.add_argument("--summary-shards-dir", type=Path, default=DEFAULT_SUMMARY_SHARDS_DIR)
    parser.add_argument("--scan-summary-shards", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = summarize_canonical_facet_readiness(
        manifest_path=args.manifest,
        summary_manifest_path=args.summary_manifest,
        summary_shards_dir=args.summary_shards_dir,
        scan_summary_shards=args.scan_summary_shards,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
