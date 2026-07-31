import pytest

from scripts.ai_suggest_entity_resolution_decisions import build_entity_resolution_ai_suggestions


def _safe_packet(items):
    return {
        "packet_policy": "entity_resolution_review_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "items": items,
    }


def _item(
    review_item_id="er_review_1",
    *,
    band="likely_same_event_review",
    score=1.0,
    evidence=None,
    risk_flags=None,
    token_jaccard=1.0,
):
    return {
        "review_item_id": review_item_id,
        "review_band": band,
        "score": score,
        "cross_current_event": True,
        "evidence": evidence
        or [
            "same_exact_day",
            "same_specific_time",
            "same_normalized_location",
            "same_source_native_id",
            "same_exact_normalized_text",
        ],
        "risk_flags": risk_flags or [],
        "token_jaccard": token_jaccard,
        "left": {
            "canonical_event_id": "evt_a",
            "canonical_input_id": "cin_a",
            "source_native_id": "159070",
        },
        "right": {
            "canonical_event_id": "evt_b",
            "canonical_input_id": "cin_b",
            "source_native_id": "159070",
        },
    }


def test_entity_resolution_ai_suggests_same_event_for_strong_clean_pair():
    suggestions, report = build_entity_resolution_ai_suggestions(
        _safe_packet([_item()]),
        reviewed_at="2026-05-22T00:00:00Z",
    )

    assert suggestions[0]["review_item_id"] == "er_review_1"
    assert suggestions[0]["suggested_decision"] == "same_event"
    assert suggestions[0]["confidence"] == "high"
    assert suggestions[0]["reviewer"] == "codex_ai_entity_resolution_conservative_v1"
    assert suggestions[0]["reviewed_at"] == "2026-05-22T00:00:00Z"
    assert suggestions[0]["evidence"]["same_native_id"] is True
    assert report["suggested_decision_counts"] == {"same_event": 1}
    assert report["confidence_counts"] == {"high": 1}
    assert report["canonical_outputs_mutated"] is False
    assert report["decisions_created"] is False
    assert report["decision_outputs_created"] is False
    assert report["validated_decisions_created"] is False
    assert report["auto_merge_performed"] is False


def test_entity_resolution_ai_defers_likely_pair_with_blocking_risk():
    item = _item(risk_flags=["type_differs"])

    suggestions, report = build_entity_resolution_ai_suggestions(_safe_packet([item]))

    assert suggestions[0]["suggested_decision"] == "needs_more_evidence"
    assert report["suggested_decision_counts"] == {"needs_more_evidence": 1}
    assert report["confidence_counts"] == {"low": 1}


def test_entity_resolution_ai_can_mark_weak_conflicting_pair_distinct():
    item = _item(
        band="weak_candidate",
        score=0.2,
        evidence=["same_exact_day"],
        risk_flags=["coordinates_far_apart"],
        token_jaccard=0.1,
    )
    item["right"]["source_native_id"] = "159071"

    suggestions, report = build_entity_resolution_ai_suggestions(_safe_packet([item]))

    assert suggestions[0]["suggested_decision"] == "distinct_events"
    assert report["suggested_decision_counts"] == {"distinct_events": 1}


def test_entity_resolution_ai_rejects_unsafe_packet():
    packet = _safe_packet([])
    packet["canonical_outputs_mutated"] = True

    with pytest.raises(ValueError, match="packet is not a safe ER review input"):
        build_entity_resolution_ai_suggestions(packet)
