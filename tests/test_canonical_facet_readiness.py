from parser.utils import write_json
from scripts.summarize_canonical_facet_readiness import summarize_canonical_facet_readiness


def test_summarize_canonical_facet_readiness_reports_manifest_facets(tmp_path):
    manifest = tmp_path / "canonical_web_manifest.json"
    summary_manifest = tmp_path / "summary_manifest.json"
    summary_shards_dir = tmp_path / "summary_shards"
    summary_shards_dir.mkdir()

    write_json(
        manifest,
        {
            "counts": {
                "events": 100,
                "mapped_events": 40,
                "summary_shards": 1,
                "source_counts": {"ufocat": 60, "nuforc": 40},
                "type_counts": {"Unknown": 55, "Light": 25, "Disk": 20},
                "shape_counts": {"Unknown": 60, "Light": 20, "Disk": 20},
                "date_precision_counts": {"exact_day": 90, "month": 10},
                "location_precision_counts": {"exact_coords": 40, "city": 55, "unknown": 5},
                "coordinate_source_counts": {"raw_latlong": 40, "unresolved": 60},
            }
        },
    )
    write_json(summary_manifest, [{"file": "summary_000000.json", "event_count": 1}])
    write_json(
        summary_shards_dir / "summary_000000.json",
        [
            {
                "event_id": "ev_1",
                "visual_type_group": "UFO/UAP sighting",
                "time_sort_kind": "exact",
                "time_sort_confidence": "high",
                "playback_sort_confidence": "high",
                "playback_sort_reason": "exact_time_with_inferred_timezone",
            }
        ],
    )

    report = summarize_canonical_facet_readiness(
        manifest_path=manifest,
        summary_manifest_path=summary_manifest,
        summary_shards_dir=summary_shards_dir,
        scan_summary_shards=True,
    )

    assert report["status"] == "ready_with_caveats"
    assert report["policy"]["report_only"] is True
    assert report["facets"]["source"]["status"] == "ready"
    assert report["facets"]["source"]["distinct_values"] == 2
    assert report["facets"]["type"]["status"] == "ready_with_caveat"
    assert report["facets"]["type"]["unknown_share"] == 0.55
    assert report["facets"]["visual_type_group"]["status"] == "ready"
    assert report["facets"]["visual_type_group"]["top_values"][0]["label"] == "UFO/UAP sighting"
    assert report["facets"]["playback_sort_reason"]["summary_shard_counts"] is True
    assert report["facets"]["playback_sort_reason"]["top_values"][0]["label"] == "exact_time_with_inferred_timezone"
    assert report["policy"]["summary_shards_scanned"] is True
    assert "source" in report["recommended_ui_order"]


def test_summarize_canonical_facet_readiness_handles_missing_sample_shard(tmp_path):
    manifest = tmp_path / "canonical_web_manifest.json"
    summary_manifest = tmp_path / "summary_manifest.json"
    summary_shards_dir = tmp_path / "summary_shards"
    summary_shards_dir.mkdir()

    write_json(
        manifest,
        {
            "counts": {
                "events": 2,
                "mapped_events": 1,
                "source_counts": {"ufocat": 2},
            }
        },
    )
    write_json(summary_manifest, [{"file": "missing.json", "event_count": 1}])

    report = summarize_canonical_facet_readiness(
        manifest_path=manifest,
        summary_manifest_path=summary_manifest,
        summary_shards_dir=summary_shards_dir,
    )

    assert report["facets"]["source"]["status"] == "ready"
    assert report["facets"]["visual_type_group"]["status"] == "missing"
    assert report["policy"]["runtime_behavior_changed"] is False
    assert report["policy"]["required_count_facets_ready"] is False
    assert report["status"] == "blocked"


def test_summarize_canonical_facet_readiness_blocks_zero_event_manifest(tmp_path):
    manifest = tmp_path / "canonical_web_manifest.json"
    summary_manifest = tmp_path / "summary_manifest.json"
    summary_shards_dir = tmp_path / "summary_shards"
    summary_shards_dir.mkdir()

    write_json(
        manifest,
        {
            "counts": {
                "events": 0,
                "mapped_events": 0,
                "source_counts": {},
                "date_precision_counts": {},
                "location_precision_counts": {},
                "coordinate_source_counts": {},
            }
        },
    )
    write_json(summary_manifest, [])

    report = summarize_canonical_facet_readiness(
        manifest_path=manifest,
        summary_manifest_path=summary_manifest,
        summary_shards_dir=summary_shards_dir,
    )

    assert report["status"] == "blocked"
    assert report["policy"]["required_count_facets_ready"] is False
