"""Build a focused review packet from manual-review replacement audit output."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


DEFAULT_AUDIT_CSV = Path("data/reports/manual_review_ai_after_time_norm_replacement_audit.csv")
DEFAULT_OUTPUT_JSON = Path("data/reports/manual_review_ai_after_time_norm_replacement_audit_review_packet.json")
DEFAULT_OUTPUT_CSV = Path("data/reports/manual_review_ai_after_time_norm_replacement_audit_review_packet.csv")
DEFAULT_OUTPUT_MD = Path("data/reports/manual_review_ai_after_time_norm_replacement_audit_review_packet.md")

PACKET_POLICY = "manual_review_replacement_audit_review_packet_v1"
DEFAULT_REVIEW_RISK_LEVELS = ("high", "medium")


def build_manual_review_replacement_audit_packet(
    *,
    audit_csv_path: Path,
    review_risk_levels: set[str],
    markdown_limit: int = 100,
) -> tuple[dict[str, Any], list[dict[str, str]], str]:
    rows = read_csv(audit_csv_path)
    review_rows = [
        {**row, "recommended_action": recommended_action(row)}
        for row in rows
        if clean_text(row.get("risk_level")) in review_risk_levels
    ]
    review_rows.sort(key=packet_sort_key)

    risk_counts: dict[str, int] = {}
    flag_counts: dict[str, int] = {}
    for row in review_rows:
        risk = clean_text(row.get("risk_level")) or "unknown"
        risk_counts[risk] = risk_counts.get(risk, 0) + 1
        for flag in split_pipe(row.get("risk_flags")):
            flag_counts[flag] = flag_counts.get(flag, 0) + 1

    report = {
        "schema_version": 1,
        "packet_policy": PACKET_POLICY,
        "canonical_outputs_mutated": False,
        "source_canonical_outputs_mutated": False,
        "ready_for_runtime_promotion": False,
        "human_review_required": True,
        "inputs": {
            "audit_csv": str(audit_csv_path),
            "review_risk_levels": sorted(review_risk_levels),
        },
        "audit_rows_read": len(rows),
        "review_row_count": len(review_rows),
        "risk_counts": dict(sorted(risk_counts.items())),
        "flag_counts": dict(sorted(flag_counts.items())),
        "top_review_rows": review_rows[:markdown_limit],
        "valid": True,
        "validation_error_count": 0,
        "validation_errors": [],
    }
    markdown = render_markdown(report, review_rows[:markdown_limit])
    return report, review_rows, markdown


def recommended_action(row: dict[str, str]) -> str:
    flags = set(split_pipe(row.get("risk_flags")))
    if row.get("risk_level") == "high":
        return "manual_adjudication_required"
    if {"time_raw_conflict", "same_source_multiple_native_ids"} & flags:
        return "time_or_identity_review"
    if {"description_text_conflict", "summary_text_conflict"} & flags:
        return "body_variance_review"
    if {"shape_conflict", "type_conflict"} & flags:
        return "classification_review"
    return "manual_review_required"


def packet_sort_key(row: dict[str, str]) -> tuple[int, int, float, str]:
    return (
        {"high": 0, "medium": 1, "low": 2}.get(clean_text(row.get("risk_level")), 3),
        -safe_int(row.get("conflict_field_count")),
        -safe_float(row.get("coordinate_span_km")),
        clean_text(row.get("replacement_event_id")),
    )


def render_markdown(report: dict[str, Any], rows: list[dict[str, str]]) -> str:
    lines = [
        "# Manual-Review Replacement Audit Packet",
        "",
        "This packet is review-only. It does not apply merges or mutate canonical outputs.",
        "",
        "## Summary",
        "",
        f"- Audit rows read: {report['audit_rows_read']}",
        f"- Review rows: {report['review_row_count']}",
        f"- Risk counts: {json.dumps(report['risk_counts'], sort_keys=True)}",
        f"- Top flags: {json.dumps(dict(list(report['flag_counts'].items())[:12]), sort_keys=True)}",
        "",
        "## Top Components",
        "",
        "| Risk | Replacement | Flags | Conflicts | Coord km | Action | Dates | Times | Location | Components |",
        "| --- | --- | --- | ---: | ---: | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    escape_md(clean_text(row.get("risk_level"))),
                    f"`{escape_md(clean_text(row.get('replacement_event_id')))}`",
                    escape_md(clean_text(row.get("risk_flags"))),
                    str(safe_int(row.get("conflict_field_count"))),
                    f"{safe_float(row.get('coordinate_span_km')):.3f}",
                    escape_md(clean_text(row.get("recommended_action"))),
                    escape_md(clean_text(row.get("date_iso_values"))),
                    escape_md(clean_text(row.get("time_raw_values"))),
                    escape_md(truncate(clean_text(row.get("location_raw_values")), 90)),
                    str(safe_int(row.get("component_event_count"))),
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0]) if rows else [
        "replacement_event_id",
        "risk_level",
        "risk_flags",
        "recommended_action",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def split_pipe(value: Any) -> list[str]:
    return [item for item in (clean_text(part) for part in str(value or "").split("|")) if item]


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def safe_int(value: Any) -> int:
    try:
        return int(float(clean_text(value) or "0"))
    except ValueError:
        return 0


def safe_float(value: Any) -> float:
    try:
        return float(clean_text(value) or "0")
    except ValueError:
        return 0.0


def truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)] + "..."


def escape_md(value: str) -> str:
    return value.replace("|", "\\|")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-csv", type=Path, default=DEFAULT_AUDIT_CSV)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--review-risk-level", action="append", default=list(DEFAULT_REVIEW_RISK_LEVELS))
    parser.add_argument("--markdown-limit", type=int, default=100)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report, rows, markdown = build_manual_review_replacement_audit_packet(
        audit_csv_path=args.audit_csv,
        review_risk_levels={clean_text(level) for level in args.review_risk_level if clean_text(level)},
        markdown_limit=args.markdown_limit,
    )
    write_json(args.output_json, report)
    write_csv(args.output_csv, rows)
    write_text(args.output_md, markdown)
    print(
        json.dumps(
            {
                "output_json": str(args.output_json),
                "output_csv": str(args.output_csv),
                "output_md": str(args.output_md),
                "review_row_count": report["review_row_count"],
                "risk_counts": report["risk_counts"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
