import pytest

from scripts.review_single_exact_context_candidates import (
    NEEDS_MORE_EVIDENCE,
    SOURCE_REVIEW_SAME_EVENT,
    build_single_exact_context_review,
)


def _item(review_item_id="er_cluster_a", *, labels=None, unknown=None, conflict_flags=None, summaries=None, minute=1200):
    labels = labels if labels is not None else ["evening"]
    summaries = summaries or ["Same source text.", "Same source text."]
    token = f"{minute // 60:02d}{minute % 60:02d}"
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
            "time_pattern_classification": "single_exact_minute_with_context_tokens",
            "review_risk_tier": "medium",
            "time_tokens": [token, *(label.title() for label in labels), *(unknown or [])],
            "parsed_minutes": [minute],
            "fuzzy_labels": labels,
            "ambiguous_tokens": [],
            "unknown_tokens": unknown or [],
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
        "packet_policy": "entity_resolution_single_exact_context_source_evidence_review_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "auto_merge_performed": False,
        "override_decisions_created": False,
        "ready_for_canonical_apply": False,
        "items": list(items),
    }


def test_single_exact_context_review_accepts_compatible_fuzzy_label():
    report = build_single_exact_context_review(_packet(_item(labels=["evening"], minute=1200)))

    item = report["items"][0]
    assert report["summary"]["review_recommendation_counts"] == {SOURCE_REVIEW_SAME_EVENT: 1}
    assert item["failed_conditions"] == []
    assert "source_review_exact_time_with_compatible_context" in item["review_reason_codes"]
    assert report["canonical_outputs_mutated"] is False


def test_single_exact_context_review_rejects_unknown_context_tokens():
    report = build_single_exact_context_review(_packet(_item(labels=["daytime"], unknown=["After"], minute=630)))

    item = report["items"][0]
    assert item["review_recommendation"] == NEEDS_MORE_EVIDENCE
    assert "no_unknown_tokens" in item["failed_conditions"]


def test_single_exact_context_review_does_not_treat_approximate_token_as_exact():
    item = _item(labels=["night"], minute=1200)
    item["shadow_preview_override_source"]["time_tokens"] = ["2000?", "night"]

    report = build_single_exact_context_review(_packet(item))

    reviewed = report["items"][0]
    assert reviewed["review_recommendation"] == NEEDS_MORE_EVIDENCE
    assert "has_exact_clock_token_for_minute" in reviewed["failed_conditions"]


def test_single_exact_context_review_rejects_incompatible_fuzzy_label():
    report = build_single_exact_context_review(_packet(_item(labels=["dawn"], minute=1200)))

    item = report["items"][0]
    assert item["review_recommendation"] == NEEDS_MORE_EVIDENCE
    assert "all_fuzzy_labels_compatible" in item["failed_conditions"]


def test_single_exact_context_review_rejects_non_time_conflict():
    conflict_flags = {
        "time": True,
        "date": False,
        "location": False,
        "coordinate": False,
        "type": False,
        "shape": True,
        "source_native_id": False,
    }

    report = build_single_exact_context_review(_packet(_item(conflict_flags=conflict_flags)))

    item = report["items"][0]
    assert item["review_recommendation"] == NEEDS_MORE_EVIDENCE
    assert "time_only_conflict" in item["failed_conditions"]


def test_single_exact_context_review_rejects_non_identical_summary_text():
    report = build_single_exact_context_review(
        _packet(_item(summaries=["First source summary.", "Different source summary."]))
    )

    item = report["items"][0]
    assert item["review_recommendation"] == NEEDS_MORE_EVIDENCE
    assert "identical_nonempty_summary_text" in item["failed_conditions"]


def test_single_exact_context_review_rejects_unsafe_packet():
    packet = _packet(_item())
    packet["auto_merge_performed"] = True

    with pytest.raises(ValueError, match="auto_merge_performed"):
        build_single_exact_context_review(packet)
