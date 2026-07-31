from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.build_entity_resolution_review_packet import build_entity_resolution_review_packet


def test_build_entity_resolution_worklist_review_packet_tiers_and_writes_outputs(tmp_path: Path) -> None:
    input_jsonl = tmp_path / "combined.jsonl"
    json_output = tmp_path / "packet.json"
    csv_output = tmp_path / "packet.csv"
    markdown_output = tmp_path / "packet.md"
    write_jsonl(
        input_jsonl,
        [
            item("pair-risky", "likely_same_event_review", 0.99, risk_flags=["weak_location_evidence"]),
            item("pair-strong", "strong_candidate_review", 0.88),
            item("pair-likely", "likely_same_event_review", 0.96),
        ],
    )

    report = build_entity_resolution_review_packet(
        input_jsonl=input_jsonl,
        json_output=json_output,
        csv_output=csv_output,
        markdown_output=markdown_output,
        limit=10,
    )
    csv_rows = list(csv.DictReader(csv_output.open("r", encoding="utf-8")))

    assert report["mode"] == "report_only"
    assert report["canonical_outputs_mutated"] is False
    assert report["decisions_created"] is False
    assert report["auto_merge_performed"] is False
    assert report["input_item_count"] == 3
    assert report["packet_item_count"] == 3
    assert report["tier_counts"] == {
        "tier_1_likely_duplicate_review": 1,
        "tier_2_strong_duplicate_review": 1,
        "tier_3_moderate_or_risky_review": 1,
    }
    assert [row["pair_id"] for row in csv_rows] == ["pair-likely", "pair-strong", "pair-risky"]
    assert csv_rows[0]["packet_rank"] == "1"
    assert json.loads(json_output.read_text(encoding="utf-8"))["packet_item_count"] == 3
    assert "Report-only packet" in markdown_output.read_text(encoding="utf-8")


def test_build_entity_resolution_worklist_review_packet_limit_is_applied(tmp_path: Path) -> None:
    input_jsonl = tmp_path / "combined.jsonl"
    write_jsonl(
        input_jsonl,
        [
            item("pair-1", "likely_same_event_review", 0.99),
            item("pair-2", "likely_same_event_review", 0.98),
        ],
    )

    report = build_entity_resolution_review_packet(
        input_jsonl=input_jsonl,
        json_output=tmp_path / "packet.json",
        csv_output=tmp_path / "packet.csv",
        markdown_output=tmp_path / "packet.md",
        limit=1,
    )

    assert report["input_item_count"] == 2
    assert report["packet_item_count"] == 1
    assert report["top_examples"][0]["pair_id"] == "pair-1"


def item(
    pair_id: str,
    band: str,
    score: float,
    *,
    risk_flags: list[str] | None = None,
) -> dict:
    return {
        "pair_id": pair_id,
        "band": band,
        "score": score,
        "token_jaccard": 0.9,
        "risk_flags": risk_flags or ["different_source_native_ids"],
        "evidence": ["same_exact_day", "same_specific_time"],
        "left": {
            "canonical_event_id": f"{pair_id}-left-event",
            "canonical_input_id": f"{pair_id}-left-input",
            "source_name": "mufon",
            "source_native_id": "100",
            "date_iso": "1954-09-19",
            "time_key": "1630",
            "location": "RONGERES, FRA",
            "summary": "Two witnesses saw a disc.",
        },
        "right": {
            "canonical_event_id": f"{pair_id}-right-event",
            "canonical_input_id": f"{pair_id}-right-input",
            "source_name": "nuforc",
            "source_native_id": "101",
            "date_iso": "1954-09-19",
            "time_key": "1630",
            "location": "RONGERES, FRA",
            "summary": "Two witnesses saw a disc.",
        },
    }


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
