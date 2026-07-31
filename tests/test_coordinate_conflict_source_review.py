import pytest

from scripts.review_coordinate_conflict_source_candidates import (
    NEEDS_MORE_EVIDENCE,
    SOURCE_REVIEW_COORDINATE_PRECISION_CANDIDATE,
    build_coordinate_conflict_source_review,
)


def _item(
    review_item_id="coord_a",
    *,
    max_distance=12.5,
    time_values=None,
    conflict_flags=None,
    identity="single_source_id_date_location",
    summaries=None,
):
    time_values = time_values if time_values is not None else ["20", "2000"]
    summaries = summaries or ["Same source text.", "Same source text."]
    return {
        "review_rank": 1,
        "review_item_id": review_item_id,
        "effect_id": f"ere_{review_item_id}",
        "projected_event_reduction": 1,
        "candidate_canonical_input_ids": ["cin_a", "cin_b"],
        "candidate_input_ids_missing_from_evidence": [],
        "merge_canonical_event_ids": ["evt_a", "evt_b"],
        "missing_canonical_event_ids": [],
        "shadow_preview_override_source": {
            "coordinate_conflict_classification": "coordinate_conflict_10_to_15km",
            "review_risk_tier": "high",
            "identity_consistency": identity,
            "recommended_review_step": "Review map/source rows.",
            "blocking_fields": ["coordinate_distance_over_10km", "time_raw"],
            "max_coordinate_distance_km": max_distance,
            "time_values": time_values,
            "type_values": ["disk"],
        },
        "source_summary": {
            "source_names": ["ufocat"],
            "source_native_ids": ["native_1"],
            "date_values": ["1954-10-03"],
            "date_precision_values": ["exact_day"],
            "location_values": ["JUNGFRAU, Bern, SUI, EU"],
            "coordinate_values": ["46.55,7.98", "46.62,8.08"],
            "time_values": time_values,
            "type_values": ["disk"],
            "shape_values": ["disk"],
        },
        "conflict_summary": {
            "conflict_flags": conflict_flags
            or {
                "time": True,
                "date": False,
                "location": False,
                "coordinate": True,
                "type": False,
                "shape": False,
                "source_native_id": False,
            }
        },
        "evidence_rows": [{"summary": text} for text in summaries],
    }


def _packet(*items):
    return {
        "packet_policy": "entity_resolution_cluster_coordinate_conflict_source_evidence_review_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "auto_merge_performed": False,
        "override_decisions_created": False,
        "ready_for_canonical_apply": False,
        "items": list(items),
    }


def test_coordinate_conflict_review_accepts_shorthand_time_candidate():
    report = build_coordinate_conflict_source_review(_packet(_item()))

    item = report["items"][0]
    assert report["summary"]["review_recommendation_counts"] == {
        SOURCE_REVIEW_COORDINATE_PRECISION_CANDIDATE: 1
    }
    assert item["failed_conditions"] == []
    assert item["time_compatibility"]["basis"] == "overlapping_time_ranges"
    assert report["canonical_outputs_mutated"] is False


def test_coordinate_conflict_review_accepts_nearby_exact_times():
    report = build_coordinate_conflict_source_review(_packet(_item(time_values=["1730", "1745"])))

    item = report["items"][0]
    assert item["review_recommendation"] == SOURCE_REVIEW_COORDINATE_PRECISION_CANDIDATE
    assert item["time_compatibility"]["basis"] == "nearby_exact_times_30m_or_less"


def test_coordinate_conflict_review_rejects_distant_times():
    report = build_coordinate_conflict_source_review(_packet(_item(time_values=["2000", "2130"])))

    item = report["items"][0]
    assert item["review_recommendation"] == NEEDS_MORE_EVIDENCE
    assert "time_values_compatible" in item["failed_conditions"]


def test_coordinate_conflict_review_rejects_non_time_coordinate_conflict():
    conflict_flags = {
        "time": True,
        "date": False,
        "location": True,
        "coordinate": True,
        "type": False,
        "shape": False,
        "source_native_id": False,
    }

    report = build_coordinate_conflict_source_review(_packet(_item(conflict_flags=conflict_flags)))

    item = report["items"][0]
    assert item["review_recommendation"] == NEEDS_MORE_EVIDENCE
    assert "only_coordinate_or_time_conflicts" in item["failed_conditions"]


def test_coordinate_conflict_review_rejects_unsafe_packet():
    packet = _packet(_item())
    packet["auto_merge_performed"] = True

    with pytest.raises(ValueError, match="auto_merge_performed"):
        build_coordinate_conflict_source_review(packet)
