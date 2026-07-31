import json
import struct

from parser.canonical_schema import CanonicalInputRecord
from parser.dedupe import build_deduped_events
from parser.packed_points import MISSING_DETAIL_INDEX
from parser.utils import write_jsonl
from scripts.build_canonical_web_artifacts import build_canonical_web_artifacts
from scripts.check_canonical_web_runtime_readiness import check_canonical_web_runtime_readiness


def test_build_canonical_web_artifacts_writes_compact_points_and_lazy_chunks(tmp_path):
    mapped = CanonicalInputRecord(
        canonical_input_id="cin_mapped",
        source_name="nuforc",
        source_file="nuforcpy.csv",
        source_row_number=2,
        source_native_id="42",
        source_row_hash="hash_mapped",
        date_raw="1/2/2000",
        date_iso="2000-01-02",
        sort_date_iso="2000-01-02",
        date_precision="exact_day",
        time_raw="22:00",
        location_raw="Phoenix, AZ, USA",
        lat=33.4484,
        lon=-112.074,
        coordinate_source="source_coordinates",
        location_precision="coordinate",
        shape_raw="Triangle",
        type_raw="Light",
        duration_raw="5 min",
        description="Witness saw a bright triangular light above town.",
        raw_source_row={"No": "42", "Description": "Witness saw a bright triangular light above town."},
        raw_source_row_values=["42", "Witness saw a bright triangular light above town."],
    )
    unmapped = CanonicalInputRecord(
        canonical_input_id="cin_unmapped",
        source_name="mufon",
        source_file="mufonpy.csv",
        source_row_number=3,
        source_native_id="99",
        source_row_hash="hash_unmapped",
        date_raw="2/2001",
        date_iso="2001-02-01",
        end_date_iso="2001-02-28",
        sort_date_iso="2001-02-14",
        date_precision="month",
        location_raw="Unknown",
        description="Unmapped report.",
    )
    deduped_events, _ = build_deduped_events([mapped, unmapped])
    input_path = tmp_path / "deduped_events.jsonl"
    output_dir = tmp_path / "canonical_web"
    stale_chunk_dir = output_dir / "event_chunks"
    stale_chunk_dir.mkdir(parents=True)
    (stale_chunk_dir / "chunk_999999.json").write_text("[]", encoding="utf-8")
    write_jsonl(input_path, deduped_events)

    summary = build_canonical_web_artifacts(
        input_path=input_path,
        output_dir=output_dir,
        chunk_size=1,
        write_gzip=True,
    )

    manifest = json.loads((output_dir / "canonical_web_manifest.json").read_text(encoding="utf-8"))
    chunk_manifest = json.loads((output_dir / "event_chunk_manifest.json").read_text(encoding="utf-8"))
    summary_manifest = json.loads((output_dir / "summary_manifest.json").read_text(encoding="utf-8"))
    points_meta = json.loads((output_dir / "points_meta.json").read_text(encoding="utf-8"))
    trace_event_index_meta = json.loads((output_dir / "trace_event_index_meta.json").read_text(encoding="utf-8"))
    trace_segments_meta = json.loads((output_dir / "trace_segments_meta.json").read_text(encoding="utf-8"))
    trace_aggregate_bins_meta = json.loads((output_dir / "trace_aggregate_bins_meta.json").read_text(encoding="utf-8"))
    compression_report = json.loads((output_dir / "compression_report.json").read_text(encoding="utf-8"))
    first_chunk = json.loads((output_dir / "event_chunks" / "chunk_000000.json").read_text(encoding="utf-8"))
    second_chunk = json.loads((output_dir / "event_chunks" / "chunk_000001.json").read_text(encoding="utf-8"))

    assert summary["events"] == 2
    assert summary["mapped_events"] == 1
    assert manifest["policy"]["raw_source_rows_included"] is True
    assert manifest["policy"]["source_claims_included"] is False
    assert manifest["policy"]["full_provenance_included"] is True
    assert manifest["policy"]["detail_raw_source_rows_included"] is True
    assert manifest["policy"]["detail_source_claims_included"] is False
    assert manifest["policy"]["detail_full_provenance_included"] is True
    assert manifest["policy"]["summary_raw_source_rows_included"] is False
    assert manifest["policy"]["summary_source_claims_included"] is False
    assert manifest["policy"]["summary_full_provenance_included"] is False
    assert manifest["counts"]["event_chunks"] == 2
    assert manifest["counts"]["summary_shards"] == 1
    assert manifest["counts"]["trace_events"] == 1
    assert manifest["counts"]["trace_segments"] == 0
    assert manifest["counts"]["trace_aggregate_bins"] == 0
    assert manifest["artifacts"]["trace_event_index"] == "trace_event_index.bin"
    assert manifest["artifacts"]["trace_event_index_metadata"] == "trace_event_index_meta.json"
    assert manifest["artifacts"]["trace_segments"] == "trace_segments.bin"
    assert manifest["artifacts"]["trace_segments_metadata"] == "trace_segments_meta.json"
    assert manifest["artifacts"]["trace_aggregate_bins"] == "trace_aggregate_bins.bin"
    assert manifest["artifacts"]["trace_aggregate_bins_metadata"] == "trace_aggregate_bins_meta.json"
    assert manifest["artifacts"]["summary_manifest"] == "summary_manifest.json"
    assert manifest["artifacts"]["summary_shards_dir"] == "summary_shards"
    assert manifest["counts"]["source_counts"] == {"mufon": 1, "nuforc": 1}
    assert manifest["counts"]["type_counts"]["Triangle"] == 1
    assert manifest["counts"]["shape_counts"]["Triangle"] == 1
    assert manifest["counts"]["craft_type_counts"]["triangle"] == 1
    assert manifest["counts"]["craft_type_counts"]["unknown"] == 1
    assert manifest["counts"]["craft_type_confidence_counts"]["high"] == 1
    assert manifest["counts"]["craft_type_confidence_counts"]["none"] == 1
    assert manifest["counts"]["same_day_match_strength_counts"]["strong"] == 1
    assert manifest["counts"]["same_day_match_strength_counts"]["none"] == 1
    assert manifest["counts"]["coordinate_source_counts"]["raw_latlong"] == 1
    assert manifest["counts"]["coordinate_source_counts"]["unresolved"] == 1
    assert manifest["counts"]["mapped_bounds"] == {
        "south": 33.4484,
        "north": 33.4484,
        "west": -112.074,
        "east": -112.074,
    }
    assert len(chunk_manifest) == 2
    assert len(summary_manifest) == 1
    assert summary_manifest[0]["event_count"] == 2
    summary_shard = json.loads((output_dir / "summary_shards" / summary_manifest[0]["file"]).read_text(encoding="utf-8"))
    assert len(summary_shard) == 2
    assert not (stale_chunk_dir / "chunk_999999.json").exists()
    assert (output_dir / "summary_shards" / summary_manifest[0]["file"]).exists()
    assert points_meta["row_count"] == 1
    assert (output_dir / "points.bin").stat().st_size == points_meta["bytes_per_row"]
    assert trace_event_index_meta["row_count"] == 1
    assert trace_event_index_meta["render_contract"]["filtered_segment_rule"] == (
        "filter rows first, then connect adjacent visible rows client-side"
    )
    assert trace_segments_meta["row_count"] == 0
    assert "diagnostic/convenience" in trace_segments_meta["render_plan"]["runtime_warning"]
    assert trace_aggregate_bins_meta["row_count"] == 0
    assert "full-universe wide-window LOD" in trace_aggregate_bins_meta["render_contract"]["runtime_warning"]
    assert trace_aggregate_bins_meta["render_contract"]["supported_filter_semantics"] == ["none/full_universe"]
    assert trace_aggregate_bins_meta["render_contract"]["authoritative_filtered_source"] == "trace_event_index.bin"
    assert (output_dir / "trace_event_index.bin").stat().st_size == trace_event_index_meta["bytes_per_row"]
    assert (output_dir / "trace_segments.bin").stat().st_size == 0
    assert (output_dir / "trace_aggregate_bins.bin").stat().st_size == 0
    assert (output_dir / "points.bin.gz").exists()
    assert (output_dir / "trace_event_index.bin.gz").exists()
    assert (output_dir / "trace_segments.bin.gz").exists()
    assert (output_dir / "trace_aggregate_bins.bin.gz").exists()
    assert (output_dir / "event_chunks" / "chunk_000000.json.gz").exists()
    assert (output_dir / "summary_shards" / f"{summary_manifest[0]['file']}.gz").exists()
    assert summary["gzip_total_mb"] == compression_report["total_gzip_mb"]
    assert compression_report["total_gzip_bytes"] < compression_report["total_bytes"]

    detail_events = first_chunk + second_chunk
    mapped_detail = next(event for event in detail_events if event["has_coordinates"])
    assert mapped_detail["description_short"] == "Witness saw a bright triangular light above town."
    assert mapped_detail["description"] == "Witness saw a bright triangular light above town."
    assert mapped_detail["craft_type_inferred"] == "triangle"
    assert mapped_detail["craft_type_label"] == "Triangle / delta"
    assert mapped_detail["craft_type_confidence"] == "high"
    assert mapped_detail["craft_type_source"] == "shape_normalized"
    assert mapped_detail["same_day_match_strength"] == "strong"
    assert mapped_detail["raw_source_row"] == {"No": "42", "Description": "Witness saw a bright triangular light above town."}
    assert "Description: Witness saw a bright triangular light above town." in mapped_detail["raw_event_block"]
    assert mapped_detail["time_sort_kind"] == "exact"
    assert mapped_detail["playback_sort_reason"] in {
        "exact_time_with_explicit_timezone",
        "exact_time_with_inferred_timezone",
        "local_time_only",
    }
    assert mapped_detail["playback_sort_key"]
    assert "raw_fields" in mapped_detail
    assert "source_claims" not in mapped_detail
    mapped_summary = next(event for event in summary_shard if event["has_coordinates"])
    assert mapped_summary["event_id"] == mapped_detail["event_id"]
    assert mapped_summary["chunk_id"] == mapped_detail["chunk_id"]
    assert mapped_summary["detail_index"] == mapped_detail["detail_index"]
    assert mapped_summary["time_sort_kind"] == mapped_detail["time_sort_kind"]
    assert mapped_summary["playback_sort_key"] == mapped_detail["playback_sort_key"]
    assert mapped_summary["craft_type_inferred"] == mapped_detail["craft_type_inferred"]
    assert mapped_summary["craft_type_label"] == mapped_detail["craft_type_label"]
    assert mapped_summary["craft_type_confidence"] == mapped_detail["craft_type_confidence"]
    assert mapped_summary["craft_type_source"] == mapped_detail["craft_type_source"]
    assert mapped_summary["same_day_match_strength"] == mapped_detail["same_day_match_strength"]
    assert "description_short" not in mapped_summary
    assert "description" not in mapped_summary
    assert "raw_event_block" not in mapped_summary
    assert "raw_source_row" not in mapped_summary
    assert "summary" not in mapped_summary
    assert "canonical_input_ids" not in mapped_summary
    assert "source_provenance_count" not in mapped_summary

    packed_row = _read_first_packed_row(output_dir / "points.bin", points_meta)
    assert packed_row["event_id"] == mapped_detail["event_id"]
    assert packed_row["chunk_id"] == mapped_detail["chunk_id"]
    assert packed_row["detail_index"] == mapped_detail["detail_index"]
    assert packed_row["craft_type_id"] == mapped_detail["craft_type_inferred"]
    assert packed_row["craft_type_confidence_id"] == mapped_detail["craft_type_confidence"]
    assert packed_row["craft_type_source_id"] == mapped_detail["craft_type_source"]
    assert packed_row["same_day_match_strength_id"] == mapped_detail["same_day_match_strength"]
    assert packed_row["detail_index"] != MISSING_DETAIL_INDEX

    readiness = check_canonical_web_runtime_readiness(output_dir)
    assert readiness["status"] == "ready_for_preview"
    assert readiness["ready_for_startup_preview"] is True
    assert readiness["ready_for_primary_catalog_prototype"] is True
    assert readiness["ready_for_primary_catalog"] is False
    assert readiness["checks"]["point_row_count_matches_manifest"] is True
    assert readiness["checks"]["packed_binary_byte_length_matches"] is True
    assert readiness["checks"]["trace_event_row_count_matches_manifest"] is True
    assert readiness["checks"]["trace_event_binary_byte_length_matches"] is True
    assert readiness["checks"]["trace_segment_row_count_matches_manifest"] is True
    assert readiness["checks"]["trace_segment_binary_byte_length_matches"] is True
    assert readiness["checks"]["trace_aggregate_row_count_matches_manifest"] is True
    assert readiness["checks"]["trace_aggregate_binary_byte_length_matches"] is True
    assert readiness["checks"]["summary_manifest_exists"] is True
    assert readiness["checks"]["summary_shard_count_matches_manifest"] is True
    assert readiness["checks"]["summary_shard_event_count_matches_manifest"] is True
    assert readiness["checks"]["event_chunk_event_count_matches_manifest"] is True
    assert readiness["checks"]["raw_source_rows_excluded"] is False
    assert readiness["checks"]["detail_raw_source_rows_preserved"] is True
    assert readiness["checks"]["detail_full_provenance_preserved"] is True
    assert readiness["checks"]["summary_raw_source_rows_excluded"] is True
    assert readiness["checks"]["summary_source_claims_excluded"] is True
    assert readiness["checks"]["summary_full_provenance_excluded"] is True
    assert readiness["checks"]["gzip_artifacts_present"] is True
    assert readiness["counts"]["point_rows"] == 1
    assert readiness["counts"]["trace_event_rows"] == 1
    assert readiness["counts"]["trace_segment_rows"] == 0
    assert readiness["counts"]["trace_aggregate_rows"] == 0
    assert readiness["counts"]["summary_shards"] == 1
    assert readiness["counts"]["startup_gzip_bytes"] > 0
    assert readiness["runtime_blockers"]

    promoted_readiness = check_canonical_web_runtime_readiness(
        output_dir,
        primary_catalog_promoted=True,
    )
    assert promoted_readiness["status"] == "ready_for_primary_catalog"
    assert promoted_readiness["ready_for_primary_catalog"] is True
    assert promoted_readiness["runtime_blockers"] == []

    legacy_manifest = json.loads((output_dir / "canonical_web_manifest.json").read_text(encoding="utf-8"))
    legacy_manifest["policy"].pop("summary_raw_source_rows_included")
    (output_dir / "canonical_web_manifest.json").write_text(
        json.dumps(legacy_manifest),
        encoding="utf-8",
    )
    legacy_readiness = check_canonical_web_runtime_readiness(
        output_dir,
        primary_catalog_promoted=True,
    )
    assert legacy_readiness["ready_for_primary_catalog"] is False
    assert legacy_readiness["checks"]["summary_raw_source_rows_excluded"] is False

    missing_detail_policy_manifest = json.loads(json.dumps(manifest))
    missing_detail_policy_manifest["policy"].pop("detail_raw_source_rows_included")
    (output_dir / "canonical_web_manifest.json").write_text(
        json.dumps(missing_detail_policy_manifest),
        encoding="utf-8",
    )
    missing_detail_policy_readiness = check_canonical_web_runtime_readiness(
        output_dir,
        primary_catalog_promoted=True,
    )
    assert missing_detail_policy_readiness["ready_for_primary_catalog"] is False
    assert missing_detail_policy_readiness["checks"]["detail_raw_source_rows_preserved"] is False

    (output_dir / "canonical_web_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    tampered_summary_manifest = json.loads(
        (output_dir / "summary_manifest.json").read_text(encoding="utf-8")
    )
    tampered_summary_manifest[0]["event_count"] -= 1
    (output_dir / "summary_manifest.json").write_text(
        json.dumps(tampered_summary_manifest),
        encoding="utf-8",
    )
    tampered_summary_readiness = check_canonical_web_runtime_readiness(
        output_dir,
        primary_catalog_promoted=True,
    )
    assert tampered_summary_readiness["ready_for_primary_catalog"] is False
    assert tampered_summary_readiness["checks"]["summary_shard_event_count_matches_manifest"] is False


def test_build_canonical_web_artifacts_preserves_admin_region_precision(tmp_path):
    input_path = tmp_path / "deduped_events.jsonl"
    input_path.write_text(
        '{"canonical_event_id":"evt_state","canonical_input_ids":["cin_state"],"source_name":"mufon","date_raw":"2020-01-01","date_iso":"2020-01-01","sort_date_iso":"2020-01-01","date_precision":"exact_day","location_raw":"CA, US","lat":36.116203,"lon":-119.681564,"coordinate_source":"geocoded","location_precision":"state"}\n'
        '{"canonical_event_id":"evt_province","canonical_input_ids":["cin_province"],"source_name":"mufon","date_raw":"2020-01-02","date_iso":"2020-01-02","sort_date_iso":"2020-01-02","date_precision":"exact_day","location_raw":"ON, CA","lat":51.253775,"lon":-85.323214,"coordinate_source":"geocoded","location_precision":"province"}\n',
        encoding="utf-8",
    )
    output_dir = tmp_path / "canonical_web"

    summary = build_canonical_web_artifacts(input_path=input_path, output_dir=output_dir)

    manifest = json.loads((output_dir / "canonical_web_manifest.json").read_text(encoding="utf-8"))
    summary_manifest = json.loads((output_dir / "summary_manifest.json").read_text(encoding="utf-8"))
    summary_shard = json.loads((output_dir / "summary_shards" / summary_manifest[0]["file"]).read_text(encoding="utf-8"))

    assert summary["location_precision_counts"]["state"] == 1
    assert summary["location_precision_counts"]["province"] == 1
    assert manifest["counts"]["location_precision_counts"]["state"] == 1
    assert manifest["counts"]["location_precision_counts"]["province"] == 1
    assert {event["location_precision"] for event in summary_shard} == {"state", "province"}


def _read_first_packed_row(path, metadata):
    row_struct = struct.Struct(metadata["struct_format"])
    unpacked = next(row_struct.iter_unpack(path.read_bytes()))
    row = {}
    for field, value in zip(metadata["fields"], unpacked):
        lookup_table = field.get("lookup_table")
        if lookup_table:
            value = metadata["lookup_tables"][lookup_table][value]
        row[field["name"]] = value
    return row
