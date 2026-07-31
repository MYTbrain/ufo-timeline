from scripts.ai_review_manual_review_queue import build_ai_assisted_decisions


def _duplicate_candidate_item(review_item_id="rev_dup", *, shared=True, similarity=1.0):
    return {
        "review_item_id": review_item_id,
        "review_type": "duplicate_candidate",
        "candidate": {
            "duplicate_candidate_id": "dupc_1",
            "score": 1.0,
            "reasons": ["same_strong_date", "same_normalized_location", "similar_source_text"],
            "blocking": {"date_iso": "1977-02-04", "location_key": "broad haven school dyfed gbr eu"},
            "signals": {
                "shared_source_identifier": shared,
                "source_text_similarity": similarity,
            },
            "canonical_input_ids": ["cin_a", "cin_b"],
            "records": [
                {"source_native_id": "94285"},
                {"source_native_id": "94285" if shared else "94286"},
            ],
        },
        "suggested_decisions": ["same_event", "distinct_events", "needs_more_evidence"],
    }


def test_ai_review_marks_strong_duplicate_candidate_same_event():
    decisions, report = build_ai_assisted_decisions([_duplicate_candidate_item()], reviewed_at="2026-05-22T00:00:00Z")

    assert decisions == [
        {
            "review_item_id": "rev_dup",
            "decision": "same_event",
            "reviewer": "codex_ai_conservative_review_v1",
            "reviewed_at": "2026-05-22T00:00:00Z",
            "notes": (
                "AI-assisted conservative review: same strong date/location with near-identical text "
                "and a strong identifier/text tie; treat as the same event."
            ),
        }
    ]
    assert report["decision_counts"] == {"same_event": 1}
    assert report["confidence_counts"] == {"high": 1}
    assert report["canonical_outputs_mutated"] is False


def test_ai_review_keeps_weaker_duplicate_candidate_for_more_evidence():
    item = _duplicate_candidate_item(shared=False, similarity=0.998)

    decisions, report = build_ai_assisted_decisions([item], reviewed_at="2026-05-22T00:00:00Z")

    assert decisions[0]["decision"] == "needs_more_evidence"
    assert report["decision_counts"] == {"needs_more_evidence": 1}
    assert report["confidence_counts"] == {"low": 1}


def test_ai_review_accepts_preserved_row_shape_anomaly_without_exclusion():
    item = {
        "review_item_id": "rev_row",
        "review_type": "row_shape_anomaly",
        "canonical_input_id": "cin_row",
        "source_file": "nuforcpy.csv",
        "source_row_number": 144555,
        "source_row_anomalies": ["extra_columns"],
        "suggested_decisions": ["accept_preserved_row", "repair_source_row", "exclude_source_row"],
    }

    decisions, report = build_ai_assisted_decisions([item], reviewed_at="2026-05-22T00:00:00Z")

    assert decisions[0]["decision"] == "accept_preserved_row"
    assert "exclude_canonical_input_ids" not in decisions[0]
    assert report["decision_counts"] == {"accept_preserved_row": 1}
