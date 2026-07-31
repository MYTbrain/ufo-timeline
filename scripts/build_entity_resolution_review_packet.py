"""Build a ranked review packet from a combined entity-resolution worklist.

This creates inspectable CSV/Markdown/JSON artifacts for human review. It does
not create merge decisions and does not mutate canonical outputs.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.apply_coordinate_sanity_preview import clean_text, write_json
from scripts.combine_entity_resolution_worklists import BAND_RANK


DEFAULT_INPUT = Path("data/reports/entity_resolution_candidate_worklist_location_hints_medium_combined.jsonl")
DEFAULT_JSON = Path("data/reports/entity_resolution_review_packet_location_hints_medium_combined.json")
DEFAULT_CSV = Path("data/reports/entity_resolution_review_packet_location_hints_medium_combined.csv")
DEFAULT_MD = Path("data/reports/entity_resolution_review_packet_location_hints_medium_combined.md")
DEFAULT_SCORE_REPORT = Path("data/reports/entity_resolution_score_report.json")

HIGH_RISK_FLAGS = {
    "coordinates_far_apart",
    "source_location_country_hint_conflict",
    "source_location_region_hint_conflict",
    "time_mismatch_or_one_missing",
    "weak_location_evidence",
}


def build_entity_resolution_review_packet(
    score_report: dict[str, Any] | None = None,
    *,
    per_band_limit: int = 50,
    include_weak: bool = True,
    cross_event_only: bool = True,
    candidate_worklist_path: Path | None = None,
    candidate_worklist_samples: list[dict[str, Any]] | None = None,
    input_jsonl: Path | None = None,
    json_output: Path | None = None,
    csv_output: Path | None = None,
    markdown_output: Path | None = None,
    limit: int = 200,
    markdown_item_limit: int = 200,
) -> dict[str, Any]:
    """Build an entity-resolution review packet.

    Two report-only modes are intentionally supported:
    - legacy score-report packets, used by existing ER decision/suggestion tools;
    - combined-worklist packets, used for the current batched review queue.
    """
    if score_report is not None:
        packet = build_entity_resolution_score_report_review_packet(
            score_report,
            per_band_limit=per_band_limit,
            include_weak=include_weak,
            cross_event_only=cross_event_only,
            candidate_worklist_path=candidate_worklist_path,
            candidate_worklist_samples=candidate_worklist_samples,
        )
        if json_output or csv_output or markdown_output:
            write_score_report_packet_outputs(
                packet,
                json_output=json_output,
                csv_output=csv_output,
                markdown_output=markdown_output,
                markdown_item_limit=markdown_item_limit,
            )
        return packet

    if input_jsonl is None:
        raise ValueError("input_jsonl is required when score_report is not provided")
    if json_output is None:
        json_output = DEFAULT_JSON
    if csv_output is None:
        csv_output = DEFAULT_CSV
    if markdown_output is None:
        markdown_output = DEFAULT_MD
    return build_entity_resolution_worklist_review_packet(
        input_jsonl=input_jsonl,
        json_output=json_output,
        csv_output=csv_output,
        markdown_output=markdown_output,
        limit=limit,
    )


def build_entity_resolution_score_report_review_packet(
    score_report: dict[str, Any],
    *,
    per_band_limit: int = 50,
    include_weak: bool = True,
    cross_event_only: bool = True,
    candidate_worklist_path: Path | None = None,
    candidate_worklist_samples: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    samples, sample_scope, candidate_worklist_used = score_report_samples(
        score_report,
        per_band_limit=per_band_limit,
        include_weak=include_weak,
        cross_event_only=cross_event_only,
        candidate_worklist_path=candidate_worklist_path,
        candidate_worklist_samples=candidate_worklist_samples,
    )
    items = [legacy_review_item(sample) for sample in samples]
    band_counts = count_legacy_items(items, "review_band")
    risk_flag_counts: Counter[str] = Counter()
    for item in items:
        for flag in text_list(item.get("risk_flags")):
            risk_flag_counts[flag] += 1
    return {
        "schema_version": 1,
        "packet_policy": "entity_resolution_review_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "source_candidate_worklist": str(candidate_worklist_path) if candidate_worklist_path else None,
        "inputs": score_report.get("inputs", {}),
        "score_summary": score_report.get("score_summary", {}),
        "export_summary": {
            "available_sample_scope": sample_scope,
            "candidate_worklist_used": candidate_worklist_used,
            "cross_event_only": cross_event_only,
            "per_band_limit": per_band_limit,
            "include_weak": include_weak,
            "exported_item_count": len(items),
            "band_counts": band_counts,
            "risk_flag_counts": dict(sorted(risk_flag_counts.items())),
        },
        "items": items,
        "notes": [
            "Report-only: review packet items are not merge decisions.",
            "Use validate_entity_resolution_decisions.py before any apply step.",
            "No canonical event outputs are mutated by this packet builder.",
        ],
    }


def score_report_samples(
    score_report: dict[str, Any],
    *,
    per_band_limit: int,
    include_weak: bool,
    cross_event_only: bool,
    candidate_worklist_path: Path | None,
    candidate_worklist_samples: list[dict[str, Any]] | None,
) -> tuple[list[dict[str, Any]], str, bool]:
    if candidate_worklist_samples is not None or candidate_worklist_path is not None:
        samples = list(candidate_worklist_samples or read_jsonl(candidate_worklist_path or Path()))
        return limited_band_samples(samples, per_band_limit, include_weak), "candidate_worklist_jsonl", True

    sample_key = "band_cross_event_scored_pair_samples" if cross_event_only else "band_scored_pair_samples"
    band_samples = score_report.get(sample_key)
    if isinstance(band_samples, dict) and any(isinstance(value, list) and value for value in band_samples.values()):
        samples: list[dict[str, Any]] = []
        for band in sorted(band_samples, key=lambda value: BAND_RANK.get(clean_text(value), 99)):
            if not include_weak and clean_text(band) == "weak_candidate":
                continue
            rows = [row for row in band_samples.get(band, []) if isinstance(row, dict)]
            samples.extend(rows[:per_band_limit] if per_band_limit > 0 else rows)
        return samples, f"per_band_{'cross_event_' if cross_event_only else ''}scored_pair_samples".replace("__", "_"), False

    top_pairs = score_report.get("top_scored_pairs") if isinstance(score_report.get("top_scored_pairs"), list) else []
    samples = [row for row in top_pairs if isinstance(row, dict)]
    if not include_weak:
        samples = [row for row in samples if clean_text(row.get("band")) != "weak_candidate"]
    if per_band_limit > 0:
        samples = samples[:per_band_limit]
    return samples, "top_scored_pairs_only", False


def limited_band_samples(samples: list[dict[str, Any]], per_band_limit: int, include_weak: bool) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for sample in samples:
        band = clean_text(sample.get("band")) or "unknown"
        if not include_weak and band == "weak_candidate":
            continue
        buckets.setdefault(band, []).append(sample)
    selected: list[dict[str, Any]] = []
    for band in sorted(buckets, key=lambda value: BAND_RANK.get(clean_text(value), 99)):
        rows = sorted(buckets[band], key=lambda row: -numeric_score(row.get("score")))
        selected.extend(rows[:per_band_limit] if per_band_limit > 0 else rows)
    return selected


def legacy_review_item(sample: dict[str, Any]) -> dict[str, Any]:
    pair_id = clean_text(sample.get("pair_id"))
    review_item_id = f"er_review_{pair_id}" if pair_id else f"er_review_{clean_text(sample.get('left', {}).get('canonical_event_id'))}_{clean_text(sample.get('right', {}).get('canonical_event_id'))}"
    left = sample.get("left") if isinstance(sample.get("left"), dict) else {}
    right = sample.get("right") if isinstance(sample.get("right"), dict) else {}
    item = {
        "review_item_id": review_item_id,
        "pair_id": pair_id,
        "review_band": clean_text(sample.get("band")),
        "score": sample.get("score"),
        "cross_current_event": bool(sample.get("cross_current_event", True)),
        "blocking_families": text_list(sample.get("blocking_families")),
        "evidence": text_list(sample.get("evidence")),
        "risk_flags": text_list(sample.get("risk_flags")),
        "token_jaccard": sample.get("token_jaccard"),
        "distance_km": sample.get("distance_km"),
        "left": dict(left),
        "right": dict(right),
    }
    item["decision_template_json"] = json.dumps(
        {
            "review_item_id": review_item_id,
            "pair_id": pair_id,
            "decision": "same_event | distinct_events | needs_more_evidence",
            "reviewer": "",
            "reviewed_at": "",
            "notes": "",
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return item


def text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := clean_text(item))]


def numeric_score(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) else 0.0


def count_legacy_items(items: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: Counter[str] = Counter(clean_text(item.get(field)) or "unknown" for item in items)
    return dict(sorted(counts.items(), key=lambda entry: (-entry[1], entry[0])))


def write_score_report_packet_outputs(
    packet: dict[str, Any],
    *,
    json_output: Path | None,
    csv_output: Path | None,
    markdown_output: Path | None,
    markdown_item_limit: int,
) -> None:
    if json_output is not None:
        write_json(json_output, packet)
    items = packet.get("items") if isinstance(packet.get("items"), list) else []
    if csv_output is not None:
        write_legacy_rows(csv_output, [item for item in items if isinstance(item, dict)])
    if markdown_output is not None:
        write_legacy_markdown(markdown_output, [item for item in items if isinstance(item, dict)], markdown_item_limit)


def write_legacy_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "review_item_id",
        "pair_id",
        "review_band",
        "score",
        "cross_current_event",
        "evidence",
        "risk_flags",
        "left_event_id",
        "left_input_id",
        "left_source",
        "left_native_id",
        "left_date",
        "left_time",
        "left_location",
        "right_event_id",
        "right_input_id",
        "right_source",
        "right_native_id",
        "right_date",
        "right_time",
        "right_location",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            left = row.get("left") if isinstance(row.get("left"), dict) else {}
            right = row.get("right") if isinstance(row.get("right"), dict) else {}
            writer.writerow(
                {
                    "review_item_id": row.get("review_item_id", ""),
                    "pair_id": row.get("pair_id", ""),
                    "review_band": row.get("review_band", ""),
                    "score": row.get("score", ""),
                    "cross_current_event": row.get("cross_current_event", ""),
                    "evidence": ";".join(text_list(row.get("evidence"))),
                    "risk_flags": ";".join(text_list(row.get("risk_flags"))),
                    "left_event_id": left.get("canonical_event_id", ""),
                    "left_input_id": left.get("canonical_input_id", ""),
                    "left_source": left.get("source_name", ""),
                    "left_native_id": left.get("source_native_id", ""),
                    "left_date": left.get("date_iso", ""),
                    "left_time": left.get("time_key", ""),
                    "left_location": left.get("location", ""),
                    "right_event_id": right.get("canonical_event_id", ""),
                    "right_input_id": right.get("canonical_input_id", ""),
                    "right_source": right.get("source_name", ""),
                    "right_native_id": right.get("source_native_id", ""),
                    "right_date": right.get("date_iso", ""),
                    "right_time": right.get("time_key", ""),
                    "right_location": right.get("location", ""),
                }
            )


def write_legacy_markdown(path: Path, rows: list[dict[str, Any]], markdown_item_limit: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Entity Resolution Review Packet",
        "",
        "Report-only packet. These rows are review candidates, not merge decisions.",
        "",
        f"Rows: {len(rows)}",
        "",
        "| Item | Band | Score | Left | Right |",
        "| --- | --- | --- | --- | --- |",
    ]
    limit = markdown_item_limit if markdown_item_limit > 0 else len(rows)
    for row in rows[:limit]:
        left = row.get("left") if isinstance(row.get("left"), dict) else {}
        right = row.get("right") if isinstance(row.get("right"), dict) else {}
        lines.append(
            "| {item} | {band} | {score} | {left} | {right} |".format(
                item=markdown_cell(row.get("review_item_id")),
                band=markdown_cell(row.get("review_band")),
                score=markdown_cell(row.get("score")),
                left=markdown_cell(f"{left.get('date_iso', '')} {left.get('time_key', '')} {left.get('location', '')}"),
                right=markdown_cell(f"{right.get('date_iso', '')} {right.get('time_key', '')} {right.get('location', '')}"),
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_entity_resolution_worklist_review_packet(
    *,
    input_jsonl: Path,
    json_output: Path,
    csv_output: Path,
    markdown_output: Path,
    limit: int,
) -> dict[str, Any]:
    items = [item for item in read_jsonl(input_jsonl) if isinstance(item, dict)]
    rows = [packet_row(item) for item in items]
    rows.sort(key=packet_sort_key)
    if limit > 0:
        rows = rows[:limit]
    for index, row in enumerate(rows, start=1):
        row["packet_rank"] = index

    write_rows(csv_output, rows)
    write_markdown(markdown_output, rows)
    report = {
        "schema_version": 1,
        "mode": "report_only",
        "review_policy": "entity_resolution_review_packet_report_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "inputs": {
            "worklist_jsonl": str(input_jsonl),
            "limit": limit,
        },
        "outputs": {
            "json": str(json_output),
            "csv": str(csv_output),
            "markdown": str(markdown_output),
        },
        "input_item_count": len(items),
        "packet_item_count": len(rows),
        "tier_counts": count_by(rows, "review_tier"),
        "band_counts": count_by(rows, "band"),
        "source_pair_counts": count_by(rows, "source_pair"),
        "top_examples": rows[:25],
        "notes": [
            "Report-only: review packet rows are not merge decisions.",
            "Tier 1 requires likely-same-event band with no high-risk flags.",
            "Tier 2 requires likely/strong band with no high-risk flags.",
            "All canonical mutation remains blocked until a separate reviewed decision/apply path exists.",
        ],
    }
    write_json(json_output, report)
    return report


def read_jsonl(path: Path) -> list[Any]:
    rows: list[Any] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def packet_row(item: dict[str, Any]) -> dict[str, Any]:
    left = item.get("left") if isinstance(item.get("left"), dict) else {}
    right = item.get("right") if isinstance(item.get("right"), dict) else {}
    risks = [clean_text(flag) for flag in item.get("risk_flags", []) if clean_text(flag)]
    evidence = [clean_text(flag) for flag in item.get("evidence", []) if clean_text(flag)]
    return {
        "packet_rank": "",
        "review_tier": review_tier(item, risks),
        "pair_id": item.get("pair_id", ""),
        "band": item.get("band", ""),
        "score": item.get("score", ""),
        "token_jaccard": item.get("token_jaccard", ""),
        "risk_flags": ";".join(risks),
        "evidence": ";".join(evidence),
        "source_pair": source_pair(left, right),
        "left_event_id": left.get("canonical_event_id", ""),
        "left_input_id": left.get("canonical_input_id", ""),
        "left_source": left.get("source_name", ""),
        "left_native_id": left.get("source_native_id", ""),
        "left_row_number": left.get("source_row_number", ""),
        "left_date": left.get("date_iso", ""),
        "left_time": left.get("time_key", ""),
        "left_location": left.get("location", ""),
        "left_type": left.get("type_key", ""),
        "left_shape": left.get("shape_key", ""),
        "left_summary": compact_summary(left.get("summary")),
        "right_event_id": right.get("canonical_event_id", ""),
        "right_input_id": right.get("canonical_input_id", ""),
        "right_source": right.get("source_name", ""),
        "right_native_id": right.get("source_native_id", ""),
        "right_row_number": right.get("source_row_number", ""),
        "right_date": right.get("date_iso", ""),
        "right_time": right.get("time_key", ""),
        "right_location": right.get("location", ""),
        "right_type": right.get("type_key", ""),
        "right_shape": right.get("shape_key", ""),
        "right_summary": compact_summary(right.get("summary")),
    }


def review_tier(item: dict[str, Any], risks: list[str]) -> str:
    band = clean_text(item.get("band"))
    has_high_risk = any(risk in HIGH_RISK_FLAGS for risk in risks)
    if band == "likely_same_event_review" and not has_high_risk:
        return "tier_1_likely_duplicate_review"
    if band in {"likely_same_event_review", "strong_candidate_review"} and not has_high_risk:
        return "tier_2_strong_duplicate_review"
    return "tier_3_moderate_or_risky_review"


def source_pair(left: dict[str, Any], right: dict[str, Any]) -> str:
    sources = sorted([clean_text(left.get("source_name")) or "unknown", clean_text(right.get("source_name")) or "unknown"])
    return "|".join(sources)


def compact_summary(value: Any) -> str:
    text = " ".join(clean_text(value).split())
    return text[:240]


def packet_sort_key(row: dict[str, Any]) -> tuple[int, int, float, str]:
    tier_rank = {
        "tier_1_likely_duplicate_review": 0,
        "tier_2_strong_duplicate_review": 1,
        "tier_3_moderate_or_risky_review": 2,
    }.get(str(row.get("review_tier")), 99)
    score = row.get("score")
    if not isinstance(score, (int, float)):
        score = 0
    return (
        tier_rank,
        BAND_RANK.get(clean_text(row.get("band")), 99),
        -float(score),
        clean_text(row.get("pair_id")),
    )


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: Counter[str] = Counter(clean_text(row.get(key)) or "unknown" for row in rows)
    return dict(sorted(counts.items(), key=lambda entry: (-entry[1], entry[0])))


def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "packet_rank",
        "review_tier",
        "pair_id",
        "band",
        "score",
        "token_jaccard",
        "risk_flags",
        "evidence",
        "source_pair",
        "left_event_id",
        "left_input_id",
        "left_source",
        "left_native_id",
        "left_row_number",
        "left_date",
        "left_time",
        "left_location",
        "left_type",
        "left_shape",
        "left_summary",
        "right_event_id",
        "right_input_id",
        "right_source",
        "right_native_id",
        "right_row_number",
        "right_date",
        "right_time",
        "right_location",
        "right_type",
        "right_shape",
        "right_summary",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Entity Resolution Review Packet",
        "",
        "Report-only packet. These rows are review candidates, not merge decisions.",
        "",
        f"Rows: {len(rows)}",
        "",
        "| Rank | Tier | Band | Score | Sources | Left | Right |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows[:200]:
        left = f"{row['left_date']} {row['left_time']} {row['left_location']} {row['left_native_id']}"
        right = f"{row['right_date']} {row['right_time']} {row['right_location']} {row['right_native_id']}"
        lines.append(
            "| {rank} | {tier} | {band} | {score} | {sources} | {left} | {right} |".format(
                rank=row["packet_rank"],
                tier=row["review_tier"],
                band=row["band"],
                score=row["score"],
                sources=row["source_pair"],
                left=markdown_cell(left),
                right=markdown_cell(right),
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def markdown_cell(value: Any) -> str:
    return clean_text(value).replace("|", "/")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--score-report",
        type=Path,
        default=None,
        help="Legacy score-report input. If omitted, builds from --input-jsonl combined worklist.",
    )
    parser.add_argument(
        "--candidate-worklist",
        type=Path,
        default=None,
        help="Optional legacy candidate worklist JSONL sidecar to use instead of score-report samples.",
    )
    parser.add_argument("--input-jsonl", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--per-band-limit", type=int, default=50)
    parser.add_argument("--markdown-item-limit", type=int, default=200)
    parser.add_argument("--exclude-weak", action="store_true")
    parser.add_argument(
        "--include-already-merged",
        action="store_true",
        help="Legacy mode: include non-cross-current-event samples from band_scored_pair_samples.",
    )
    parser.add_argument(
        "--decision-ready-from-worklist",
        action="store_true",
        help=(
            "Emit the legacy decision-ready packet schema from --candidate-worklist or --input-jsonl. "
            "This remains report-only and creates no decisions."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.score_report is not None or args.decision_ready_from_worklist:
        candidate_worklist_path = args.candidate_worklist
        if args.decision_ready_from_worklist and candidate_worklist_path is None:
            candidate_worklist_path = args.input_jsonl
        score_report = (
            read_json(args.score_report)
            if args.score_report is not None
            else {
                "report_policy": "entity_resolution_scoring_analysis_only",
                "inputs": {"candidate_worklist": str(candidate_worklist_path)},
                "score_summary": {},
            }
        )
        report = build_entity_resolution_review_packet(
            score_report,
            per_band_limit=args.per_band_limit,
            include_weak=not args.exclude_weak,
            cross_event_only=not args.include_already_merged,
            candidate_worklist_path=candidate_worklist_path,
            json_output=args.json_output,
            csv_output=args.csv_output,
            markdown_output=args.markdown_output,
            markdown_item_limit=args.markdown_item_limit,
        )
        print(
            json.dumps(
                {
                    "json": str(args.json_output),
                    "csv": str(args.csv_output),
                    "markdown": str(args.markdown_output),
                    "packet_item_count": report["export_summary"]["exported_item_count"],
                    "band_counts": report["export_summary"]["band_counts"],
                    "canonical_outputs_mutated": False,
                },
                indent=2,
            )
        )
        return 0

    report = build_entity_resolution_review_packet(
        input_jsonl=args.input_jsonl,
        json_output=args.json_output,
        csv_output=args.csv_output,
        markdown_output=args.markdown_output,
        limit=args.limit,
    )
    print(
        json.dumps(
            {
                "json": report["outputs"]["json"],
                "csv": report["outputs"]["csv"],
                "markdown": report["outputs"]["markdown"],
                "input_item_count": report["input_item_count"],
                "packet_item_count": report["packet_item_count"],
                "tier_counts": report["tier_counts"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
