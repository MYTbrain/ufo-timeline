from __future__ import annotations

import json
from pathlib import Path

from scripts.combine_entity_resolution_worklists import combine_entity_resolution_worklists


def test_combine_entity_resolution_worklists_dedupes_and_sorts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    reports_dir = tmp_path / "data" / "reports"
    reports_dir.mkdir(parents=True)
    worklist_a = reports_dir / "worklist_a.jsonl"
    worklist_b = reports_dir / "worklist_b.jsonl"
    write_jsonl(
        worklist_a,
        [
            item("pair-2", "moderate_candidate_review", 0.71, left_source="mufon", right_source="mufon"),
            item("pair-1", "strong_candidate_review", 0.82, left_source="nuforc", right_source="nuforc"),
        ],
    )
    write_jsonl(
        worklist_b,
        [
            item("pair-1", "likely_same_event_review", 0.90, left_source="nuforc", right_source="nuforc"),
            item("pair-3", "strong_candidate_review", 0.88, left_source="mufon", right_source="nuforc"),
        ],
    )
    write_report(reports_dir / "report_a.json", "data/reports/worklist_a.jsonl")
    write_report(reports_dir / "report_b.json", "data/reports/worklist_b.jsonl")

    manifest = combine_entity_resolution_worklists(
        report_glob=str(reports_dir / "report_*.json"),
        manifest_output=reports_dir / "combined.json",
        jsonl_output=reports_dir / "combined.jsonl",
    )
    combined = read_jsonl(reports_dir / "combined.jsonl")

    assert manifest["canonical_outputs_mutated"] is False
    assert manifest["decisions_created"] is False
    assert manifest["input_item_count"] == 4
    assert manifest["unique_item_count"] == 3
    assert manifest["duplicate_pair_count"] == 1
    assert manifest["band_counts"] == {
        "likely_same_event_review": 1,
        "strong_candidate_review": 1,
        "moderate_candidate_review": 1,
    }
    assert [row["pair_id"] for row in combined] == ["pair-1", "pair-3", "pair-2"]
    assert combined[0]["band"] == "likely_same_event_review"


def test_combine_entity_resolution_worklists_uses_event_ids_when_pair_id_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    reports_dir = tmp_path / "data" / "reports"
    reports_dir.mkdir(parents=True)
    worklist = reports_dir / "worklist.jsonl"
    row = item("", "strong_candidate_review", 0.8)
    row.pop("pair_id")
    write_jsonl(worklist, [row])
    write_report(reports_dir / "report.json", "data/reports/worklist.jsonl")

    manifest = combine_entity_resolution_worklists(
        report_glob=str(reports_dir / "report*.json"),
        manifest_output=reports_dir / "combined.json",
        jsonl_output=reports_dir / "combined.jsonl",
    )

    assert manifest["unique_item_count"] == 1
    assert manifest["band_counts"] == {"strong_candidate_review": 1}


def item(pair_id: str, band: str, score: float, *, left_source: str = "mufon", right_source: str = "nuforc") -> dict:
    return {
        "pair_id": pair_id,
        "band": band,
        "score": score,
        "risk_flags": ["different_source_native_ids"],
        "left": {
            "canonical_event_id": f"left-{pair_id or 'x'}",
            "source_name": left_source,
        },
        "right": {
            "canonical_event_id": f"right-{pair_id or 'x'}",
            "source_name": right_source,
        },
    }


def write_report(path: Path, worklist_output: str) -> None:
    path.write_text(
        json.dumps(
            {
                "candidate_worklist_summary": {
                    "enabled": True,
                    "output": worklist_output,
                    "canonical_outputs_mutated": False,
                    "decisions_created": False,
                }
            }
        ),
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
