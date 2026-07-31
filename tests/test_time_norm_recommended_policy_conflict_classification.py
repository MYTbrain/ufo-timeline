import pytest

from scripts.classify_time_norm_recommended_policy_body_conflicts import (
    classify_time_norm_recommended_policy_body_conflicts,
)


def _preview(review_item_id="review_1", conflicts=None):
    return {
        "review_item_id": review_item_id,
        "effect_id": f"effect_{review_item_id}",
        "canonical_event_id": "evt_a",
        "representative_event_id": "evt_a",
        "source_event_count": 2,
        "canonical_input_id_count": 2,
        "entity_resolution_canonical_merge_conflicts": conflicts
        or {
            "time_raw": {
                "values": ["1000", "1005"],
                "source_values": [
                    {"canonical_event_id": "evt_a", "value": "1000"},
                    {"canonical_event_id": "evt_b", "value": "1005"},
                ],
            }
        },
    }


def _payload(*previews):
    return {
        "preview_policy": "entity_resolution_cluster_canonical_merge_body_policy_preview_only",
        "policy": "entity_resolution_cluster_canonical_merge_policy_proposal_v1",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "previews": list(previews),
    }


def test_policy_conflict_classification_accepts_time_only_and_punctuation_text_variants():
    report = classify_time_norm_recommended_policy_body_conflicts(
        _payload(
            _preview("time_only"),
            _preview(
                "punctuation",
                conflicts={
                    "time_raw": {"values": ["1000", "1005"]},
                    "summary": {"values": ["Traces", "Traces."]},
                    "description": {"values": ["Traces", "Traces."]},
                },
            ),
        )
    )

    assert report["classification_policy"] == "entity_resolution_time_norm_recommended_policy_conflict_classification_only"
    assert report["canonical_outputs_mutated"] is False
    assert report["summary"]["classification_counts"] == {
        "time_raw_only": 1,
        "time_raw_with_punctuation_only_text_variants": 1,
    }
    assert report["summary"]["blocking_preview_count"] == 0
    assert report["summary"]["apply_policy_candidate_count"] == 2


def test_policy_conflict_classification_accepts_minor_text_typo_variants():
    report = classify_time_norm_recommended_policy_body_conflicts(
        _payload(
            _preview(
                conflicts={
                    "time_raw": {"values": ["1000", "1005"]},
                    "summary": {
                        "values": [
                            "Plane'e engine increased revolutions when UFO was sighted.",
                            "Plane's engine increased revolutions when UFO was sighted.",
                        ]
                    },
                }
            )
        )
    )

    assert report["summary"]["classification_counts"] == {"time_raw_with_minor_text_typo_variants": 1}
    assert report["summary"]["blocking_preview_count"] == 0
    assert report["items"][0]["blockers"] == []


def test_policy_conflict_classification_blocks_substantive_text_variants():
    report = classify_time_norm_recommended_policy_body_conflicts(
        _payload(
            _preview(
                conflicts={
                    "time_raw": {"values": ["1000", "1005"]},
                    "summary": {"values": ["Triangle craft", "Disc craft"]},
                }
            )
        )
    )

    assert report["summary"]["classification_counts"] == {"blocking_policy_conflict": 1}
    assert report["summary"]["blocking_preview_count"] == 1
    assert report["items"][0]["blockers"] == ["non_punctuation_text_conflict"]


def test_policy_conflict_classification_rejects_unsafe_preview():
    payload = _payload(_preview())
    payload["ready_for_canonical_apply"] = True

    with pytest.raises(ValueError, match="ready_for_canonical_apply"):
        classify_time_norm_recommended_policy_body_conflicts(payload)
