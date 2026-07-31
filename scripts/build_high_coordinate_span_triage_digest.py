"""Build a report-only triage digest for high coordinate-span review items.

The source high-coordinate review packet is intentionally conservative and
keeps every item blocked. This digest summarizes the manual review order and
the evidence fields reviewers should inspect first. It does not create
decisions, apply merges, or mutate canonical outputs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import median
from typing import Any


DEFAULT_REVIEW_JSON = Path("data/reports/manual_review_ai_after_time_norm_high_coordinate_span_review.json")
DEFAULT_JSON_OUTPUT = Path("data/reports/high_coordinate_span_triage_digest.json")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/high_coordinate_span_triage_digest.md")


def build_high_coordinate_span_triage_digest(review_report: dict[str, Any]) -> dict[str, Any]:
    items = [item for item in review_report.get("items") or [] if isinstance(item, dict)]
    spans = [float(item.get("coordinate_span_km") or 0) for item in items]
    top_items = sorted(items, key=lambda item: (-float(item.get("coordinate_span_km") or 0), str(item.get("replacement_event_id"))))[:10]
    return {
        "schema_version": 1,
        "digest_policy": "high_coordinate_span_triage_digest_report_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "ready_for_canonical_apply": False,
        "human_review_required_before_promotion": True,
        "source_review_policy": review_report.get("review_policy"),
        "summary": {
            "reviewed_item_count": len(items),
            "projected_event_reduction_total": sum(int(item.get("projected_event_reduction") or 0) for item in items),
            "coordinate_subcategory_counts": count_by(items, "coordinate_subcategory"),
            "risk_flag_counts": count_list_values(items, "risk_flags"),
            "source_file_counts": count_list_values(items, "source_file_values"),
            "component_event_count_buckets": component_event_count_buckets(items),
            "span_km_min": round(min(spans), 3) if spans else None,
            "span_km_median": round(median(spans), 3) if spans else None,
            "span_km_max": round(max(spans), 3) if spans else None,
        },
        "review_guidance": [
            "Start with extreme and severe coordinate spans before 50-100km cases.",
            "Verify whether component rows are duplicate records with bad geocodes or genuinely separate locations.",
            "Treat vague locations such as P, P, ships, airports, and region-only records as source/geocode review blockers.",
            "Do not accept a same-event merge unless source rows support one location interpretation.",
            "Do not use this digest as an apply file; it is a manual review triage surface only.",
        ],
        "top_review_items": [summarize_item(item) for item in top_items],
    }


def count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def count_list_values(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        values = item.get(key)
        if not isinstance(values, list) or not values:
            values = ["unknown"]
        for value in values:
            text = str(value or "unknown")
            counts[text] = counts.get(text, 0) + 1
    return dict(sorted(counts.items()))


def component_event_count_buckets(items: list[dict[str, Any]]) -> dict[str, int]:
    buckets = {"2_events": 0, "3_to_4_events": 0, "5_plus_events": 0}
    for item in items:
        count = int(item.get("component_event_count") or 0)
        if count <= 2:
            buckets["2_events"] += 1
        elif count <= 4:
            buckets["3_to_4_events"] += 1
        else:
            buckets["5_plus_events"] += 1
    return buckets


def summarize_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "review_rank": item.get("review_rank"),
        "replacement_event_id": item.get("replacement_event_id"),
        "coordinate_span_km": item.get("coordinate_span_km"),
        "coordinate_subcategory": item.get("coordinate_subcategory"),
        "projected_event_reduction": item.get("projected_event_reduction"),
        "source_file_values": item.get("source_file_values") or [],
        "location_raw_values": item.get("location_raw_values") or [],
        "date_iso_values": item.get("date_iso_values") or [],
        "time_raw_values": item.get("time_raw_values") or [],
        "risk_flags": item.get("risk_flags") or [],
        "component_event_count": item.get("component_event_count"),
        "component_event_ids": item.get("component_event_ids") or [],
    }


def render_markdown(digest: dict[str, Any]) -> str:
    summary = digest["summary"]
    lines = [
        "# High Coordinate-Span Triage Digest",
        "",
        "This digest is report-only. It does not accept decisions, apply merges, or mutate canonical outputs.",
        "",
        "## Summary",
        "",
        f"- Reviewed items: {summary['reviewed_item_count']}",
        f"- Projected event reduction behind the blocked queue: {summary['projected_event_reduction_total']}",
        f"- Span km min/median/max: {summary['span_km_min']} / {summary['span_km_median']} / {summary['span_km_max']}",
        f"- Subcategories: {json.dumps(summary['coordinate_subcategory_counts'], sort_keys=True)}",
        f"- Component event buckets: {json.dumps(summary['component_event_count_buckets'], sort_keys=True)}",
        "",
        "## Review Guidance",
        "",
    ]
    lines.extend(f"- {item}" for item in digest["review_guidance"])
    lines.extend(
        [
            "",
            "## Top Review Items",
            "",
            "| Rank | Replacement | Span km | Subcategory | Locations | Times |",
            "| ---: | --- | ---: | --- | --- | --- |",
        ]
    )
    for item in digest["top_review_items"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(item.get("review_rank")),
                    f"`{escape_md(str(item.get('replacement_event_id') or ''))}`",
                    str(item.get("coordinate_span_km")),
                    escape_md(str(item.get("coordinate_subcategory") or "")),
                    escape_md("|".join(item.get("location_raw_values") or [])),
                    escape_md("|".join(item.get("time_raw_values") or [])),
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def escape_md(value: str) -> str:
    return value.replace("|", "\\|")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-json", type=Path, default=DEFAULT_REVIEW_JSON)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    digest = build_high_coordinate_span_triage_digest(read_json(args.review_json))
    digest["inputs"] = {"review_json": str(args.review_json)}
    digest["outputs"] = {"json": str(args.json_output), "markdown": str(args.markdown_output)}
    write_json(args.json_output, digest)
    write_text(args.markdown_output, render_markdown(digest))
    print(
        json.dumps(
            {
                "json": str(args.json_output),
                "markdown": str(args.markdown_output),
                "reviewed_items": digest["summary"]["reviewed_item_count"],
                "ready_for_canonical_apply": digest["ready_for_canonical_apply"],
                "canonical_outputs_mutated": digest["canonical_outputs_mutated"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
