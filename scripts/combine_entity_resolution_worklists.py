"""Combine report-only entity-resolution worklist batches.

The scorer can run in bounded offset batches. This helper collects the generated
score reports and worklist JSONL files into one deduplicated review queue so the
next review/apply steps can inspect current coverage without rerunning the
expensive scorer.

No canonical, preview, static, or deployment artifacts are mutated.
"""

from __future__ import annotations

import argparse
import glob
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.apply_coordinate_sanity_preview import clean_text, write_json


DEFAULT_REPORT_GLOB = "data/reports/entity_resolution_score_report_location_hints_medium*.json"
DEFAULT_JSON = Path("data/reports/entity_resolution_candidate_worklist_location_hints_medium_combined_manifest.json")
DEFAULT_JSONL = Path("data/reports/entity_resolution_candidate_worklist_location_hints_medium_combined.jsonl")

BAND_RANK = {
    "likely_same_event_review": 0,
    "strong_candidate_review": 1,
    "moderate_candidate_review": 2,
    "weak_candidate": 3,
}


def combine_entity_resolution_worklists(
    *,
    report_glob: str,
    manifest_output: Path,
    jsonl_output: Path,
) -> dict[str, Any]:
    report_paths = [Path(path) for path in sorted(glob.glob(report_glob))]
    reports: list[dict[str, Any]] = []
    worklist_paths: list[Path] = []
    for report_path in report_paths:
        report = read_json(report_path)
        if not isinstance(report, dict):
            continue
        summary = report.get("candidate_worklist_summary")
        output = summary.get("output") if isinstance(summary, dict) else None
        if not output:
            continue
        worklist_path = Path(output)
        if not worklist_path.is_absolute():
            worklist_path = Path.cwd() / worklist_path
        if not worklist_path.exists():
            continue
        reports.append({"path": str(report_path), "report": report})
        worklist_paths.append(worklist_path)

    by_pair: dict[str, dict[str, Any]] = {}
    duplicate_count = 0
    input_item_count = 0
    for worklist_path in worklist_paths:
        for item in read_jsonl(worklist_path):
            if not isinstance(item, dict):
                continue
            input_item_count += 1
            pair_key = pair_identity(item)
            if pair_key in by_pair:
                duplicate_count += 1
                by_pair[pair_key] = better_item(by_pair[pair_key], item)
            else:
                by_pair[pair_key] = item

    items = sorted(by_pair.values(), key=sort_key)
    write_jsonl(jsonl_output, items)

    manifest = {
        "schema_version": 1,
        "mode": "report_only",
        "candidate_policy": "entity_resolution_combined_candidate_worklist_report_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "inputs": {
            "report_glob": report_glob,
            "score_reports": [entry["path"] for entry in reports],
            "worklists": [str(path) for path in worklist_paths],
        },
        "outputs": {
            "manifest": str(manifest_output),
            "jsonl": str(jsonl_output),
        },
        "report_count": len(reports),
        "worklist_count": len(worklist_paths),
        "input_item_count": input_item_count,
        "unique_item_count": len(items),
        "duplicate_pair_count": duplicate_count,
        "band_counts": count_by(items, "band"),
        "source_pair_counts": source_pair_counts(items),
        "risk_flag_counts": risk_flag_counts(items),
        "top_examples": items[:50],
        "notes": [
            "Report-only: this combines review candidates and does not create merge decisions.",
            "Pairs are deduplicated by pair_id when available, otherwise by canonical event IDs.",
            "The highest-priority version of a duplicate pair is retained.",
        ],
    }
    write_json(manifest_output, manifest)
    return manifest


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[Any]:
    rows: list[Any] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def pair_identity(item: dict[str, Any]) -> str:
    pair_id = clean_text(item.get("pair_id"))
    if pair_id:
        return f"pair:{pair_id}"
    left = item.get("left") if isinstance(item.get("left"), dict) else {}
    right = item.get("right") if isinstance(item.get("right"), dict) else {}
    event_ids = sorted(
        clean_text(value)
        for value in [left.get("canonical_event_id"), right.get("canonical_event_id")]
        if clean_text(value)
    )
    return "events:" + "|".join(event_ids)


def better_item(current: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    return min([current, candidate], key=sort_key)


def sort_key(item: dict[str, Any]) -> tuple[int, float, str]:
    band = clean_text(item.get("band"))
    score = item.get("score")
    if not isinstance(score, (int, float)):
        score = 0
    return (
        BAND_RANK.get(band, 99),
        -float(score),
        pair_identity(item),
    )


def count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for item in items:
        counts[clean_text(item.get(key)) or "unknown"] += 1
    return dict(sorted(counts.items(), key=lambda entry: (-entry[1], entry[0])))


def source_pair_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for item in items:
        left = item.get("left") if isinstance(item.get("left"), dict) else {}
        right = item.get("right") if isinstance(item.get("right"), dict) else {}
        sources = sorted([clean_text(left.get("source_name")) or "unknown", clean_text(right.get("source_name")) or "unknown"])
        counts["|".join(sources)] += 1
    return dict(sorted(counts.items(), key=lambda entry: (-entry[1], entry[0])))


def risk_flag_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for item in items:
        flags = item.get("risk_flags") if isinstance(item.get("risk_flags"), list) else []
        if not flags:
            counts["none"] += 1
            continue
        for flag in flags:
            counts[clean_text(flag) or "unknown"] += 1
    return dict(sorted(counts.items(), key=lambda entry: (-entry[1], entry[0])))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-glob", default=DEFAULT_REPORT_GLOB)
    parser.add_argument("--manifest-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--jsonl-output", type=Path, default=DEFAULT_JSONL)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = combine_entity_resolution_worklists(
        report_glob=args.report_glob,
        manifest_output=args.manifest_output,
        jsonl_output=args.jsonl_output,
    )
    print(
        json.dumps(
            {
                "manifest": manifest["outputs"]["manifest"],
                "jsonl": manifest["outputs"]["jsonl"],
                "report_count": manifest["report_count"],
                "worklist_count": manifest["worklist_count"],
                "input_item_count": manifest["input_item_count"],
                "unique_item_count": manifest["unique_item_count"],
                "band_counts": manifest["band_counts"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
