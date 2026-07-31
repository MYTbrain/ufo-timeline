import pytest

from scripts.review_time_conflict_context_candidates import (
    NEEDS_MORE_EVIDENCE,
    SOURCE_REVIEW_SAME_EVENT,
    build_time_conflict_context_review,
)


def _item(
    review_item_id="er_cluster_a",
    *,
    conflict_flags=None,
    coord_risk=False,
    risk_flags=None,
    unknown=None,
    ambiguous=None,
    summaries=None,
    parsed_minutes=None,
    labels=None,
):
    parsed_minutes = parsed_minutes or [1200, 1210]
    labels = labels if labels is not None else ["evening"]
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
            "time_conflict_classification": "nearby_exact_conflict_15m_or_less_with_context",
            "review_risk_tier": "high",
            "identity_consistency": "single_source_id_date_location",
            "time_tokens": ["2000", "2010", *(label.title() for label in labels), *(unknown or []), *(ambiguous or [])],
            "parsed_minutes": parsed_minutes,
            "exact_span_minutes": max(parsed_minutes) - min(parsed_minutes),
            "fuzzy_labels": labels,
            "approximate_tokens": [],
            "ambiguous_tokens": ambiguous or [],
            "unknown_tokens": unknown or [],
            "risk_flags": risk_flags or [],
            "has_coordinate_risk": coord_risk,
        },
        "source_summary": {
            "source_names": ["ufocat"],
            "source_native_ids": ["native_1"],
            "date_values": ["1965-11-26"],
            "date_precision_values": ["exact_day"],
            "location_values": ["ST PAUL, Ramsey, MN, US"],
            "coordinate_values": ["44.95,-93.09"],
            "type_values": ["5ew"],
            "shape_values": ["lights"],
        },
        "conflict_summary": {
            "conflict_flags": conflict_flags
            or {
                "time": True,
                "date": False,
                "location": False,
                "coordinate": False,
                "type": False,
                "shape": False,
                "source_native_id": False,
            }
        },
        "evidence_rows": [{"summary": text} for text in summaries],
    }


def _packet(*items):
    return {
        "packet_policy": "entity_resolution_time_conflict_context_source_evidence_review_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "auto_merge_performed": False,
        "override_decisions_created": False,
        "ready_for_canonical_apply": False,
        "items": list(items),
    }


def test_time_conflict_context_review_accepts_strict_time_only_case():
    report = build_time_conflict_context_review(_packet(_item()))

    item = report["items"][0]
    assert report["summary"]["review_recommendation_counts"] == {SOURCE_REVIEW_SAME_EVENT: 1}
    assert item["failed_conditions"] == []
    assert "source_review_nearby_exact_times_with_context" in item["review_reason_codes"]
    assert report["canonical_outputs_mutated"] is False


def test_time_conflict_context_review_rejects_coordinate_conflict():
    conflict_flags = {
        "time": True,
        "date": False,
        "location": False,
        "coordinate": True,
        "type": False,
        "shape": False,
        "source_native_id": False,
    }

    report = build_time_conflict_context_review(_packet(_item(conflict_flags=conflict_flags, coord_risk=True)))

    item = report["items"][0]
    assert item["review_recommendation"] == NEEDS_MORE_EVIDENCE
    assert "time_only_conflict" in item["failed_conditions"]
    assert "no_coordinate_risk" in item["failed_conditions"]


def test_time_conflict_context_review_rejects_unknown_tokens():
    report = build_time_conflict_context_review(_packet(_item(unknown=["After"])))

    item = report["items"][0]
    assert item["review_recommendation"] == NEEDS_MORE_EVIDENCE
    assert "no_unknown_tokens" in item["failed_conditions"]


def test_time_conflict_context_review_rejects_mixed_identity():
    item = _item()
    item["shadow_preview_override_source"]["identity_consistency"] = "mixed_or_incomplete_identity"

    report = build_time_conflict_context_review(_packet(item))

    reviewed = report["items"][0]
    assert reviewed["review_recommendation"] == NEEDS_MORE_EVIDENCE
    assert "identity_consistency_single_source_id_date_location" in reviewed["failed_conditions"]


def test_time_conflict_context_review_rejects_incompatible_fuzzy_label():
    report = build_time_conflict_context_review(_packet(_item(labels=["dawn"])))

    item = report["items"][0]
    assert item["review_recommendation"] == NEEDS_MORE_EVIDENCE
    assert "all_fuzzy_labels_compatible" in item["failed_conditions"]


def test_time_conflict_context_review_rejects_non_identical_summary_text():
    report = build_time_conflict_context_review(
        _packet(_item(summaries=["First source summary.", "Different source summary."]))
    )

    item = report["items"][0]
    assert item["review_recommendation"] == NEEDS_MORE_EVIDENCE
    assert "identical_nonempty_summary_text" in item["failed_conditions"]


def test_time_conflict_context_review_rejects_unsafe_packet():
    packet = _packet(_item())
    packet["auto_merge_performed"] = True

    with pytest.raises(ValueError, match="auto_merge_performed"):
        build_time_conflict_context_review(packet)
