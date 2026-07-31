"""Validate the coordinate quarantine packet against its CSV export."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


DEFAULT_PACKET = Path("data/reports/coordinate_quarantine_packet_v3.json")
DEFAULT_CSV = Path("data/reports/coordinate_quarantine_packet_v3.csv")
DEFAULT_OUTPUT = Path("data/reports/coordinate_quarantine_packet_v3_readiness.json")


def check_coordinate_quarantine_packet(*, packet_path: Path, csv_path: Path, output_path: Path) -> dict[str, Any]:
    packet = read_json(packet_path)
    rows = read_csv(csv_path)
    summary = packet.get("summary") or {}
    recommendation_counts = count_by(rows, "quarantine_recommendation")
    checks = {
        "packet_exists": packet_path.exists(),
        "csv_exists": csv_path.exists(),
        "report_only": packet.get("mode") == "report_only",
        "canonical_outputs_not_mutated": packet.get("canonical_outputs_mutated") is False,
        "preview_outputs_not_mutated": packet.get("preview_outputs_mutated") is False,
        "not_ready_for_apply": packet.get("ready_for_apply") is False,
        "human_review_required": packet.get("human_review_required_before_hiding") is True,
        "csv_row_count_matches_suspicious": len(rows) == int(summary.get("suspicious_event_count") or -1),
        "quarantine_count_matches": recommendation_counts.get("quarantine_until_review", 0) == int(summary.get("quarantine_candidate_count") or -1),
        "display_safe_count_matches": recommendation_counts.get("keep_visible_polygon_review", 0) == int(summary.get("display_safe_review_count") or -1),
    }
    status = "ready_for_review" if all(checks.values()) else "blocked"
    report = {
        "schema_version": 1,
        "status": status,
        "checks": checks,
        "inputs": {
            "packet": str(packet_path),
            "csv": str(csv_path),
        },
        "summary": {
            "csv_rows": len(rows),
            "recommendation_counts": recommendation_counts,
            "quarantine_candidate_count": summary.get("quarantine_candidate_count"),
            "display_safe_review_count": summary.get("display_safe_review_count"),
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def count_by(rows: list[dict[str, str]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = row.get(key) or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = check_coordinate_quarantine_packet(packet_path=args.packet, csv_path=args.csv, output_path=args.output)
    print(json.dumps({
        "output": str(args.output),
        "status": report["status"],
        "csv_rows": report["summary"]["csv_rows"],
        "recommendation_counts": report["summary"]["recommendation_counts"],
    }, indent=2))
    return 0 if report["status"] == "ready_for_review" else 1


if __name__ == "__main__":
    raise SystemExit(main())
