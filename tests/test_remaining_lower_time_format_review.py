import pytest

from scripts.build_entity_resolution_remaining_lower_time_format_source_evidence_packet import (
    build_remaining_lower_time_format_source_evidence_packet,
)
from scripts.review_remaining_lower_time_format_candidates import (
    REMAIN_DEFERRED,
    SOURCE_REVIEW_SAME_EVENT,
    build_remaining_lower_time_format_review,
)


def _analysis_item(review_item_id="er_cluster_lower_a", *, time_tokens=None, parsed_tokens=None):
    time_tokens = time_tokens or ["0200", "0210"]
    parsed_tokens = parsed_tokens or [
        {"raw": "0200", "kind": "exact", "minute": 120, "bucket_label": None, "approximate": False, "note": None},
        {"raw": "0210", "kind": "exact", "minute": 130, "bucket_label": None, "approximate": False, "note": None},
    ]
    return {
        "review_rank": 1,
        "time_pattern_classification": "nearby_exact_minutes_15m_or_less",
        "review_risk_tier": "lower",
        "recommended_review_step": "Review as possible rounded-time duplicates.",
        "review_item_id": review_item_id,
        "effect_id": f"ere_{review_item_id}",
        "projected_event_reduction": 1,
        "blocking_fields": ["time_raw"],
        "time_tokens": time_tokens,
        "parsed_tokens": parsed_tokens,
        "parsed_minutes": sorted({token["minute"] for token in parsed_tokens if token.get("minute") is not None}),
        "fuzzy_labels": [],
        "ambiguous_tokens": [],
        "unknown_tokens": [],
        "source_summary": {
            "canonical_event_ids": ["evt_a", "evt_b"],
            "canonical_input_ids": ["cin_a", "cin_b"],
            "canonical_event_count": 2,
            "source_names": ["ufocat"],
            "source_native_ids": ["native_1"],
            "date_values": ["1965-11-26"],
            "location_values": ["ST PAUL, Ramsey, MN, US"],
            "type_values": ["5ew"],
        },
    }


def _analysis(*items):
    return {
        "analysis_policy": "entity_resolution_cluster_time_normalization_review_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "auto_merge_performed": False,
        "override_decisions_created": False,
        "ready_for_canonical_apply": False,
        "items": list(items),
    }


def _event(event_id, input_id, time_raw):
    return {
        "canonical_event_id": event_id,
        "canonical_input_id": input_id,
        "canonical_input_ids": [input_id],
        "source_name": "ufocat",
        "source_file": "ufocat2023.csv",
        "source_row_number": 1,
        "source_native_id": "native_1",
        "date_iso": "1965-11-26",
        "date_precision": "exact_day",
        "time_raw": time_raw,
        "location_raw": "ST PAUL, Ramsey, MN, US",
        "lat": 44.95,
        "lon": -93.09,
        "type_normalized": "5ew",
        "shape_normalized": "",
        "summary": "Same source text.",
    }


def _packet_item(*, parsed_tokens=None, fuzzy_labels=None, conflict_flags=None, summaries=None):
    summaries = summaries or ["Same source text.", "Same source text."]
    return {
        "review_rank": 1,
        "review_item_id": "er_cluster_lower_a",
        "effect_id": "ere_lower_a",
        "projected_event_reduction": 1,
        "candidate_canonical_input_ids": ["cin_a", "cin_b"],
        "candidate_input_ids_missing_from_evidence": [],
        "merge_canonical_event_ids": ["evt_a", "evt_b"],
        "missing_canonical_event_ids": [],
        "shadow_preview_override_source": {
            "time_pattern_classification": "nearby_exact_minutes_15m_or_less",
            "review_risk_tier": "lower",
            "time_tokens": ["0200", "0210"],
            "parsed_tokens": parsed_tokens
            or [
                {"raw": "0200", "kind": "exact", "minute": 120, "note": None},
                {"raw": "0210", "kind": "exact", "minute": 130, "note": None},
            ],
            "fuzzy_labels": fuzzy_labels or [],
            "ambiguous_tokens": [],
            "unknown_tokens": [],
        },
        "source_summary": {
            "source_names": ["ufocat"],
            "source_native_ids": ["native_1"],
            "date_values": ["1965-11-26"],
            "date_precision_values": ["exact_day"],
            "location_values": ["ST PAUL, Ramsey, MN, US"],
            "coordinate_values": ["44.95,-93.09"],
            "type_values": ["5ew"],
            "shape_values": [""],
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
        "packet_policy": "entity_resolution_remaining_lower_time_format_source_row_evidence_review_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "auto_merge_performed": False,
        "override_decisions_created": False,
        "ready_for_canonical_apply": False,
        "items": list(items),
    }


def test_remaining_lower_packet_excludes_accepted_review_items(tmp_path):
    deduped = tmp_path / "deduped_events.jsonl"
    deduped.write_text(
        "\n".join(
            [
                '{"canonical_event_id":"evt_a","canonical_input_id":"cin_a","canonical_input_ids":["cin_a"],"time_raw":"0200"}',
                '{"canonical_event_id":"evt_b","canonical_input_id":"cin_b","canonical_input_ids":["cin_b"],"time_raw":"0210"}',
                "",
            ]
        ),
        encoding="utf-8",
    )
    packet = build_remaining_lower_time_format_source_evidence_packet(
        analysis=_analysis(_analysis_item("er_cluster_lower_a"), _analysis_item("er_cluster_accepted")),
        accepted_decisions=[{"review_item_id": "er_cluster_accepted"}],
        deduped_events_path=deduped,
    )

    assert packet["canonical_outputs_mutated"] is False
    assert packet["decisions_created"] is False
    assert packet["summary"]["candidate_effect_count"] == 1
    assert packet["items"][0]["review_item_id"] == "er_cluster_lower_a"


def test_remaining_lower_review_accepts_consistent_nearby_time_only_candidate():
    report = build_remaining_lower_time_format_review(_packet(_packet_item()))

    assert report["canonical_outputs_mutated"] is False
    assert report["decisions_created"] is False
    assert report["ready_for_canonical_apply"] is False
    item = report["items"][0]
    assert item["review_recommendation"] == SOURCE_REVIEW_SAME_EVENT
    assert item["failed_conditions"] == []


def test_remaining_lower_review_defers_rollover_token():
    parsed_tokens = [
        {"raw": "00+", "kind": "exact", "minute": 0, "note": None},
        {"raw": "0015", "kind": "exact", "minute": 15, "note": None},
        {"raw": "2445", "kind": "exact", "minute": 0, "note": "rollover_24_hour_token"},
    ]

    report = build_remaining_lower_time_format_review(_packet(_packet_item(parsed_tokens=parsed_tokens)))

    item = report["items"][0]
    assert item["review_recommendation"] == REMAIN_DEFERRED
    assert "no_rollover_24_hour_token" in item["failed_conditions"]


def test_remaining_lower_review_defers_incompatible_fuzzy_context():
    parsed_tokens = [
        {"raw": "0828", "kind": "exact", "minute": 508, "note": None},
        {"raw": "0836", "kind": "exact", "minute": 516, "note": None},
        {"raw": "PDawn", "kind": "fuzzy", "minute": 255, "bucket_label": "before_dawn", "note": None},
    ]

    report = build_remaining_lower_time_format_review(
        _packet(_packet_item(parsed_tokens=parsed_tokens, fuzzy_labels=["before_dawn"]))
    )

    item = report["items"][0]
    assert item["review_recommendation"] == REMAIN_DEFERRED
    assert "fuzzy_context_compatible" in item["failed_conditions"]


def test_remaining_lower_review_rejects_unsafe_packet():
    packet = _packet(_packet_item())
    packet["ready_for_canonical_apply"] = True

    with pytest.raises(ValueError, match="ready_for_canonical_apply"):
        build_remaining_lower_time_format_review(packet)
