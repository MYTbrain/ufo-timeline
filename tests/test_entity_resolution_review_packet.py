import json

from scripts.build_entity_resolution_review_packet import build_entity_resolution_review_packet


def _sample(pair_id, band, score):
    return {
        "pair_id": pair_id,
        "score": score,
        "band": band,
        "cross_current_event": True,
        "blocking_families": ["strong_date_location_time"],
        "evidence": ["same_exact_day", "same_specific_time"],
        "risk_flags": ["different_source_native_ids"] if band == "moderate_candidate_review" else [],
        "token_jaccard": 0.75,
        "distance_km": 1.2,
        "left": {
            "canonical_input_id": f"{pair_id}_left",
            "canonical_event_id": f"{pair_id}_evt_left",
            "source_name": "ufocat",
            "source_file": "ufocat.csv",
            "source_row_number": 1,
            "source_native_id": "100",
            "date_iso": "1954-09-19",
            "time_key": "1630",
            "location": "RONGERES, FRA",
        },
        "right": {
            "canonical_input_id": f"{pair_id}_right",
            "canonical_event_id": f"{pair_id}_evt_right",
            "source_name": "ufocat",
            "source_file": "ufocat.csv",
            "source_row_number": 2,
            "source_native_id": "101",
            "date_iso": "1954-09-19",
            "time_key": "1630",
            "location": "RONGERES, FRA",
        },
    }


def test_build_entity_resolution_review_packet_exports_per_band_samples():
    score_report = {
        "report_policy": "entity_resolution_scoring_analysis_only",
        "inputs": {"score_report": "example"},
        "score_summary": {"scored_pair_count": 3},
        "block_summary": {"selected_multi_record_block_count": 2},
        "band_cross_event_scored_pair_samples": {
            "likely_same_event_review": [_sample("erp_likely", "likely_same_event_review", 0.98)],
            "strong_candidate_review": [_sample("erp_strong", "strong_candidate_review", 0.8)],
            "moderate_candidate_review": [_sample("erp_moderate", "moderate_candidate_review", 0.6)],
            "weak_candidate": [_sample("erp_weak", "weak_candidate", 0.2)],
        },
    }

    packet = build_entity_resolution_review_packet(score_report, per_band_limit=1)

    assert packet["canonical_outputs_mutated"] is False
    assert packet["decisions_created"] is False
    assert packet["export_summary"]["available_sample_scope"] == "per_band_cross_event_scored_pair_samples"
    assert packet["export_summary"]["cross_event_only"] is True
    assert packet["export_summary"]["exported_item_count"] == 4
    assert packet["export_summary"]["band_counts"]["likely_same_event_review"] == 1
    assert packet["export_summary"]["risk_flag_counts"]["different_source_native_ids"] == 1
    assert packet["items"][0]["review_item_id"] == "er_review_erp_likely"
    assert "same_event | distinct_events | needs_more_evidence" in packet["items"][0]["decision_template_json"]


def test_build_entity_resolution_review_packet_can_exclude_weak_samples():
    score_report = {
        "band_cross_event_scored_pair_samples": {
            "likely_same_event_review": [_sample("erp_likely", "likely_same_event_review", 0.98)],
            "weak_candidate": [_sample("erp_weak", "weak_candidate", 0.2)],
        },
    }

    packet = build_entity_resolution_review_packet(score_report, include_weak=False)

    assert packet["export_summary"]["exported_item_count"] == 1
    assert packet["items"][0]["review_band"] == "likely_same_event_review"


def test_build_entity_resolution_review_packet_falls_back_to_top_pairs():
    score_report = {
        "top_scored_pairs": [_sample("erp_top", "likely_same_event_review", 1.0)],
    }

    packet = build_entity_resolution_review_packet(score_report)

    assert packet["export_summary"]["available_sample_scope"] == "top_scored_pairs_only"
    assert packet["export_summary"]["exported_item_count"] == 1
    assert json.loads(packet["items"][0]["decision_template_json"])["pair_id"] == "erp_top"


def test_build_entity_resolution_review_packet_can_include_already_merged_samples():
    already_merged = _sample("erp_merged", "likely_same_event_review", 1.0)
    already_merged["cross_current_event"] = False
    score_report = {
        "band_cross_event_scored_pair_samples": {},
        "band_scored_pair_samples": {
            "likely_same_event_review": [already_merged],
        },
    }

    packet = build_entity_resolution_review_packet(score_report, cross_event_only=False)

    assert packet["export_summary"]["available_sample_scope"] == "per_band_scored_pair_samples"
    assert packet["export_summary"]["cross_event_only"] is False
    assert packet["export_summary"]["exported_item_count"] == 1
    assert packet["items"][0]["cross_current_event"] is False


def test_build_entity_resolution_review_packet_can_use_candidate_worklist_sidecar(tmp_path):
    score_report = {
        "report_policy": "entity_resolution_scoring_analysis_only",
        "band_cross_event_scored_pair_samples": {
            "likely_same_event_review": [_sample("erp_score_sample", "likely_same_event_review", 0.99)],
        },
    }
    worklist_path = tmp_path / "worklist.jsonl"
    worklist_samples = [
        _sample("erp_worklist_strong_a", "strong_candidate_review", 0.83),
        _sample("erp_worklist_strong_b", "strong_candidate_review", 0.82),
        _sample("erp_worklist_strong_c", "strong_candidate_review", 0.81),
        _sample("erp_worklist_moderate", "moderate_candidate_review", 0.6),
    ]

    packet = build_entity_resolution_review_packet(
        score_report,
        candidate_worklist_path=worklist_path,
        candidate_worklist_samples=worklist_samples,
        per_band_limit=2,
        include_weak=False,
    )

    assert packet["source_candidate_worklist"] == str(worklist_path)
    assert packet["export_summary"]["available_sample_scope"] == "candidate_worklist_jsonl"
    assert packet["export_summary"]["candidate_worklist_used"] is True
    assert packet["export_summary"]["exported_item_count"] == 3
    assert packet["export_summary"]["band_counts"]["strong_candidate_review"] == 2
    assert packet["export_summary"]["band_counts"]["moderate_candidate_review"] == 1
    assert {item["review_item_id"] for item in packet["items"]} == {
        "er_review_erp_worklist_strong_a",
        "er_review_erp_worklist_strong_b",
        "er_review_erp_worklist_moderate",
    }
