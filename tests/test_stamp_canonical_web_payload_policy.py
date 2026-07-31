import gzip
import json

import pytest

from parser.utils import write_json
from scripts.stamp_canonical_web_payload_policy import stamp_canonical_web_payload_policy


def _write_fixture(tmp_path, *, forbidden_summary=False):
    artifact_dir = tmp_path / "canonical_web"
    summary_dir = artifact_dir / "summary_shards"
    detail_dir = artifact_dir / "event_chunks"
    summary_dir.mkdir(parents=True)
    detail_dir.mkdir()
    manifest = {
        "counts": {"events": 2, "mapped_events": 1, "event_chunks": 1, "summary_shards": 1},
        "policy": {
            "raw_source_rows_included": True,
            "source_claims_included": False,
            "full_provenance_included": True,
            "detail_chunks_are_lazy_loaded": True,
        },
    }
    write_json(artifact_dir / "canonical_web_manifest.json", manifest, indent=2)
    write_json(artifact_dir / "summary_manifest.json", [{"file": "summary_000000.json", "event_count": 2}])
    write_json(artifact_dir / "event_chunk_manifest.json", [{"file": "chunk_000000.json", "event_count": 2}])
    summaries = [{"event_id": 1}, {"event_id": 2}]
    if forbidden_summary:
        summaries[0]["raw_source_row"] = {"id": 1}
    write_json(summary_dir / "summary_000000.json", summaries)
    write_json(
        detail_dir / "chunk_000000.json",
        [
            {
                "event_id": 1,
                "canonical_input_ids": ["cin_1"],
                "raw_source_row": {"id": 1},
                "source_provenance": [{"source": "fixture"}],
                "merged_member_craft_type_candidate": "disc_saucer",
            },
            {"event_id": 2},
        ],
    )
    raw = (artifact_dir / "canonical_web_manifest.json").read_bytes()
    compressed = gzip.compress(raw, compresslevel=6)
    (artifact_dir / "canonical_web_manifest.json.gz").write_bytes(compressed)
    write_json(
        artifact_dir / "compression_report.json",
        {
            "total_files": 1,
            "total_bytes": len(raw),
            "total_gzip_bytes": len(compressed),
            "files": [
                {
                    "path": "canonical_web_manifest.json",
                    "gzip_path": "canonical_web_manifest.json.gz",
                    "bytes": len(raw),
                    "gzip_bytes": len(compressed),
                    "gzip_ratio": round(len(compressed) / len(raw), 3),
                }
            ],
        },
        indent=2,
    )
    return artifact_dir


def test_stamp_preserves_details_and_certifies_compact_summaries(tmp_path):
    artifact_dir = _write_fixture(tmp_path)
    details_before = (artifact_dir / "event_chunks" / "chunk_000000.json").read_bytes()

    report = stamp_canonical_web_payload_policy(artifact_dir)

    manifest_path = artifact_dir / "canonical_web_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    compression = json.loads((artifact_dir / "compression_report.json").read_text(encoding="utf-8"))
    manifest_entry = next(entry for entry in compression["files"] if entry["path"] == "canonical_web_manifest.json")
    assert report["status"] == "passed"
    assert report["events"] == 2
    assert report["summary_forbidden_field_occurrences"] == 0
    assert report["raw_evidence_events"] == 1
    assert report["provenance_events"] == 1
    assert report["merged_member_evidence_events"] == 1
    assert report["manifest_gzip_matches_raw"] is True
    assert report["gzip_pairs_verified"] == 1
    assert report["gzip_decoded_bytes_verified"] == manifest_path.stat().st_size
    assert manifest["policy"]["detail_raw_source_rows_included"] is True
    assert manifest["policy"]["detail_full_provenance_included"] is True
    assert manifest["policy"]["summary_raw_source_rows_included"] is False
    assert manifest["policy"]["summary_full_provenance_included"] is False
    assert (artifact_dir / "event_chunks" / "chunk_000000.json").read_bytes() == details_before
    assert gzip.decompress((artifact_dir / "canonical_web_manifest.json.gz").read_bytes()) == manifest_path.read_bytes()
    assert manifest_entry["bytes"] == manifest_path.stat().st_size
    assert (artifact_dir / "artifact_size_report.json").is_file()


def test_stamp_fails_closed_when_summary_contains_raw_evidence(tmp_path):
    artifact_dir = _write_fixture(tmp_path, forbidden_summary=True)
    manifest_before = (artifact_dir / "canonical_web_manifest.json").read_bytes()

    with pytest.raises(ValueError, match="Summary shards contain raw/provenance"):
        stamp_canonical_web_payload_policy(artifact_dir)

    assert (artifact_dir / "canonical_web_manifest.json").read_bytes() == manifest_before
