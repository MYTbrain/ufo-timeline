from __future__ import annotations

import json
from pathlib import Path

from scripts.summarize_served_geonames_coordinate_disagreements import (
    collect_candidate_rows,
    infer_country_from_location_raw,
)


def test_infer_country_from_location_raw_uses_country_code_before_region() -> None:
    assert infer_country_from_location_raw("PEN-MEN, Finistere, FRA, EU") == "France"
    assert infer_country_from_location_raw("FARGO, Cass, ND, US") == "United States of America"


def test_collect_candidate_rows_reads_served_summary_shards(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "canonical_web"
    (artifact_dir / "summary_shards").mkdir(parents=True)
    _write_json(
        artifact_dir / "summary_manifest.json",
        [{"id": "summary_000000", "file": "summary_000000.json", "event_count": 2}],
    )
    _write_json(
        artifact_dir / "summary_shards" / "summary_000000.json",
        [
            {
                "event_id": 1,
                "chunk_id": "chunk_000000",
                "detail_index": 0,
                "source": "ufocat",
                "location_raw": "PEN-MEN, Finistere, FRA, EU",
                "coordinate_source": "source_coordinates",
                "location_precision": "coordinate",
                "lat": 47.43,
                "lon": 3.82,
            },
            {
                "event_id": 2,
                "chunk_id": "chunk_000000",
                "detail_index": 1,
                "source": "ufocat",
                "location_raw": "BREST, Finistere, FRA, EU",
                "coordinate_source": "geocoded",
                "location_precision": "city",
                "lat": 48.39,
                "lon": -4.49,
            },
        ],
    )

    rows = collect_candidate_rows(artifact_dir, {"France": "FR"})

    assert len(rows) == 1
    assert rows[0]["event_id"] == 1
    assert rows[0]["chunk_id"] == "chunk_000000"
    assert rows[0]["detail_index"] == 0
    assert rows[0]["country_name"] == "France"


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
