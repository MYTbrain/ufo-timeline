"""Build a review-only packet from expanded ER cluster opportunity groups."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from parser.canonical_schema import clean_text, stable_hash


DEFAULT_OPPORTUNITY_REPORT = Path("data/reports/expanded_dedupe_opportunity_report_top500.json")
DEFAULT_JSON_OUTPUT = Path("data/reports/entity_resolution_cluster_review_packet.json")
DEFAULT_CSV_OUTPUT = Path("data/reports/entity_resolution_cluster_review_packet.csv")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/entity_resolution_cluster_review_packet.md")

TIER_PRIORITY = {
    "conservative": 0,
    "moderate": 1,
    "exploratory": 2,
    "aggressive": 3,
}

CSV_FIELDS = (
    "cluster_review_id",
    "family_id",
    "tier",
    "projected_event_reduction",
    "unique_current_event_count",
    "source_record_count",
    "source_names",
    "first_source_file",
    "date_iso",
    "distinct_date_count",
    "location",
    "distinct_location_count",
    "sample_input_ids",
    "current_event_id_count_exported",
    "current_event_ids_truncated",
)


def build_entity_resolution_cluster_review_packet(
    opportunity_report: dict[str, Any],
    *,
    source_report_path: Path | None = None,
    per_family_limit: int = 500,
    include_tiers: set[str] | None = None,
) -> dict[str, Any]:
    include_tiers = include_tiers or set(TIER_PRIORITY)
    items: list[dict[str, Any]] = []
    for family in opportunity_report.get("families") or []:
        if not isinstance(family, dict):
            continue
        family_id = clean_text(family.get("family_id")) or "unknown"
        tier = clean_text(family.get("tier")) or "unknown"
        if tier not in include_tiers:
            continue
        groups = family.get("top_cross_event_groups")
        if not isinstance(groups, list):
            continue
        for group in groups[: max(0, per_family_limit)]:
            if isinstance(group, dict):
                items.append(cluster_item_from_group(family, group))
    items.sort(key=cluster_item_sort_key)
    return {
        "schema_version": 1,
        "packet_policy": "entity_resolution_cluster_review_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "auto_merge_performed": False,
        "source_report": str(source_report_path) if source_report_path else None,
        "source_report_policy": opportunity_report.get("report_policy"),
        "current_canonical_counts": opportunity_report.get("current_canonical_counts", {}),
        "tier_union_reduction_estimates": opportunity_report.get("tier_union_reduction_estimates", {}),
        "export_summary": {
            "per_family_limit": per_family_limit,
            "include_tiers": sorted(include_tiers, key=lambda tier: TIER_PRIORITY.get(tier, 99)),
            "exported_item_count": len(items),
            "tier_counts": count_by(items, "tier"),
            "family_counts": count_by(items, "family_id"),
            "projected_reduction_sum_not_deduped": sum(int(item.get("projected_event_reduction") or 0) for item in items),
        },
        "decision_guidance": {
            "important_policy": "Cluster rows are review targets only. Do not auto-merge a cluster from this packet without a later cluster decision/apply policy.",
            "review_focus": "Prioritize conservative and moderate clusters first, then inspect exploratory/aggressive clusters for systematic source-specific duplication patterns.",
        },
        "items": items,
    }


def cluster_item_from_group(family: dict[str, Any], group: dict[str, Any]) -> dict[str, Any]:
    unique_count = as_int(group.get("unique_current_event_count")) or 0
    family_id = clean_text(family.get("family_id")) or "unknown"
    key_hash = clean_text(group.get("key_hash")) or stable_hash(group, prefix="dgk_", length=16)
    return {
        "cluster_review_id": f"er_cluster_{stable_hash({'family_id': family_id, 'key_hash': key_hash}, length=18)}",
        "family_id": family_id,
        "tier": clean_text(family.get("tier")) or "unknown",
        "family_description": clean_text(family.get("description")),
        "key_hash": key_hash,
        "projected_event_reduction": max(0, unique_count - 1),
        "unique_current_event_count": unique_count,
        "source_record_count": as_int(group.get("source_record_count")) or 0,
        "sample_input_ids": string_list(group.get("sample_input_ids")),
        "current_event_ids": string_list(group.get("current_event_ids")),
        "current_event_ids_truncated": bool(group.get("current_event_ids_truncated")),
        "source_names": string_list(group.get("source_names")),
        "first_source_file": clean_text(group.get("first_source_file")),
        "date_iso": clean_text(group.get("date_iso")),
        "distinct_date_count": as_int(group.get("distinct_date_count")),
        "location": clean_text(group.get("location")),
        "distinct_location_count": as_int(group.get("distinct_location_count")),
        "date_samples": string_list(group.get("date_samples")),
        "location_samples": string_list(group.get("location_samples")),
    }


def cluster_item_sort_key(item: dict[str, Any]) -> tuple[int, int, str]:
    return (
        TIER_PRIORITY.get(str(item.get("tier") or ""), 99),
        -int(item.get("projected_event_reduction") or 0),
        str(item.get("cluster_review_id") or ""),
    )


def count_by(items: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = clean_text(item.get(field)) or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := clean_text(item))]


def as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for item in items:
            writer.writerow(csv_row(item))


def csv_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "cluster_review_id": item.get("cluster_review_id"),
        "family_id": item.get("family_id"),
        "tier": item.get("tier"),
        "projected_event_reduction": item.get("projected_event_reduction"),
        "unique_current_event_count": item.get("unique_current_event_count"),
        "source_record_count": item.get("source_record_count"),
        "source_names": "; ".join(string_list(item.get("source_names"))),
        "first_source_file": item.get("first_source_file"),
        "date_iso": item.get("date_iso"),
        "distinct_date_count": item.get("distinct_date_count"),
        "location": item.get("location"),
        "distinct_location_count": item.get("distinct_location_count"),
        "sample_input_ids": "; ".join(string_list(item.get("sample_input_ids"))),
        "current_event_id_count_exported": len(string_list(item.get("current_event_ids"))),
        "current_event_ids_truncated": str(bool(item.get("current_event_ids_truncated"))).lower(),
    }


def write_markdown(path: Path, packet: dict[str, Any], *, item_limit: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    items = packet.get("items") if isinstance(packet.get("items"), list) else []
    shown = items[: max(0, item_limit)]
    export_summary = packet.get("export_summary") if isinstance(packet.get("export_summary"), dict) else {}
    lines = [
        "# Entity-Resolution Cluster Review Packet",
        "",
        "This packet is review-only. It does not create decisions, perform merges, or mutate canonical outputs.",
        "",
        "## Summary",
        "",
        f"- Source report: `{packet.get('source_report')}`",
        f"- Exported cluster items: {export_summary.get('exported_item_count', 0)}",
        f"- Projected reduction sum, not deduped: {export_summary.get('projected_reduction_sum_not_deduped', 0)}",
        f"- Canonical outputs mutated: {str(packet.get('canonical_outputs_mutated')).lower()}",
        "",
        "## Cluster Items",
        "",
    ]
    for item in shown:
        lines.extend(markdown_item_lines(item))
    if len(items) > len(shown):
        lines.extend(["", f"_Markdown limited to {len(shown)} of {len(items)} exported items._", ""])
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def markdown_item_lines(item: dict[str, Any]) -> list[str]:
    return [
        f"### {item.get('cluster_review_id')}",
        "",
        f"- Tier / family: `{item.get('tier')}` / `{item.get('family_id')}`",
        f"- Projected reduction: `{item.get('projected_event_reduction')}` from `{item.get('unique_current_event_count')}` current events",
        f"- Source records: `{item.get('source_record_count')}`",
        f"- Source names: {', '.join(string_list(item.get('source_names'))) or 'unknown'}",
        f"- Date: `{item.get('date_iso')}` distinct date count `{item.get('distinct_date_count')}`",
        f"- Location: {item.get('location') or 'unknown'} distinct location count `{item.get('distinct_location_count')}`",
        f"- Sample input IDs: {', '.join(string_list(item.get('sample_input_ids'))) or 'none'}",
        f"- Current event IDs exported: `{len(string_list(item.get('current_event_ids')))}` truncated `{str(bool(item.get('current_event_ids_truncated'))).lower()}`",
        "",
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--opportunity-report", type=Path, default=DEFAULT_OPPORTUNITY_REPORT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument("--per-family-limit", type=int, default=500)
    parser.add_argument("--markdown-item-limit", type=int, default=200)
    parser.add_argument("--include-tier", action="append", choices=tuple(TIER_PRIORITY))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    opportunity_report = read_json(args.opportunity_report)
    packet = build_entity_resolution_cluster_review_packet(
        opportunity_report,
        source_report_path=args.opportunity_report,
        per_family_limit=args.per_family_limit,
        include_tiers=set(args.include_tier) if args.include_tier else None,
    )
    write_json(args.json_output, packet)
    write_csv(args.csv_output, packet["items"])
    write_markdown(args.markdown_output, packet, item_limit=args.markdown_item_limit)
    print(
        json.dumps(
            {
                "json_output": str(args.json_output),
                "csv_output": str(args.csv_output),
                "markdown_output": str(args.markdown_output),
                "exported_item_count": packet["export_summary"]["exported_item_count"],
                "projected_reduction_sum_not_deduped": packet["export_summary"]["projected_reduction_sum_not_deduped"],
                "canonical_outputs_mutated": False,
                "decisions_created": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
