import pytest

from scripts.build_coordinate_conflict_scoring_gap_report import (
    REPORT_POLICY,
    build_coordinate_conflict_scoring_gap_report,
)


def _evidence_row(
    *,
    date_iso="1954-10-03",
    date_precision="exact_day",
    location_raw="JUNGFRAU, Bern, SUI, EU",
    source_native_id="native_1",
    type_normalized="disk",
    shape_normalized="disk",
    summary="Same source text.",
):
    return {
        "source_name": "ufocat",
        "source_native_id": source_native_id,
        "date_iso": date_iso,
        "date_precision": date_precision,
        "time_raw": "2100",
        "location_raw": location_raw,
        "lat": 46.55,
        "lon": 7.98,
        "coordinate_source": "raw_latlong",
        "coordinate_precision": "exact_coords",
        "type_normalized": type_normalized,
        "shape_normalized": shape_normalized,
        "summary": summary,
        "description_excerpt": summary,
    }


def _packet_item(
    review_item_id="coord_a",
    *,
    evidence_rows=None,
    source_summary=None,
    candidate_missing=None,
    missing_events=None,
):
    evidence_rows = evidence_rows or [_evidence_row(), _evidence_row()]
    source_summary = source_summary or {
        "source_names": ["ufocat"],
        "source_native_ids": ["native_1"],
        "date_values": ["1954-10-03"],
        "date_precision_values": ["exact_day"],
        "location_values": ["JUNGFRAU, Bern, SUI, EU"],
        "coordinate_values": ["46.55,7.98", "46.62,8.08"],
        "time_values": ["2100"],
        "type_values": ["disk"],
        "shape_values": ["disk"],
    }
    return {
        "review_rank": 1,
        "review_item_id": review_item_id,
        "effect_id": f"ere_{review_item_id}",
        "projected_event_reduction": 1,
        "candidate_canonical_input_ids": ["cin_a", "cin_b"],
        "candidate_input_ids_missing_from_evidence": candidate_missing or [],
        "merge_canonical_event_ids": ["evt_a", "evt_b"],
        "missing_canonical_event_ids": missing_events or [],
        "shadow_preview_override_source": {
            "coordinate_conflict_classification": "coordinate_conflict_10_to_15km",
            "max_coordinate_distance_km": 12.5,
        },
        "source_summary": source_summary,
        "evidence_rows": evidence_rows,
    }


def _review_item(
    review_item_id="coord_a",
    *,
    recommendation="source_review_coordinate_precision_candidate",
    confidence="medium",
    time_compatibility=None,
    failed_conditions=None,
):
    return {
        "review_rank": 1,
        "review_item_id": review_item_id,
        "effect_id": f"ere_{review_item_id}",
        "review_recommendation": recommendation,
        "confidence": confidence,
        "projected_event_reduction": 1,
        "max_coordinate_distance_km": 12.5,
        "time_values": ["2100"],
        "time_compatibility": time_compatibility
        or {
            "compatible": True,
            "basis": "overlapping_time_ranges",
            "parsed": {},
        },
        "failed_conditions": failed_conditions or [],
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


def _review(*items):
    return {
        "review_policy": "entity_resolution_coordinate_conflict_source_review_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "decision_outputs_created": False,
        "validated_decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "items": list(items),
    }


def test_coordinate_conflict_scoring_gap_report_keeps_candidate_review_only():
    report = build_coordinate_conflict_scoring_gap_report(
        packet=_packet(_packet_item()),
        review=_review(_review_item()),
    )

    item = report["items"][0]
    assert report["report_policy"] == REPORT_POLICY
    assert report["canonical_outputs_mutated"] is False
    assert report["ready_for_canonical_apply"] is False
    assert item["review_next_action"] == "review_coordinate_precision_candidate_before_decision"
    assert item["missing_scoring_dimensions"] == []
    assert item["date_status"] == "single_exact_day"
    assert item["coordinate_distance_bucket"] == "10_to_15km"
    assert report["summary"]["missing_scoring_dimension_counts"] == {"none": 1}


def test_coordinate_conflict_scoring_gap_report_flags_missing_dimensions():
    mixed_source_summary = {
        "source_names": ["ufocat"],
        "source_native_ids": ["native_1", "native_2"],
        "date_values": ["1954-10-03"],
        "date_precision_values": ["month"],
        "location_values": ["JUNGFRAU, Bern, SUI, EU", "WIEN (VIENNA), Vienna, AUT, EU"],
        "type_values": ["disk", "light"],
        "shape_values": ["disk", "sphere"],
    }
    evidence_rows = [
        _evidence_row(
            date_precision="month",
            source_native_id="native_1",
            type_normalized="disk",
            shape_normalized="disk",
            summary="One account described a disk.",
        ),
        _evidence_row(
            date_precision="month",
            location_raw="WIEN (VIENNA), Vienna, AUT, EU",
            source_native_id="native_2",
            type_normalized="light",
            shape_normalized="sphere",
            summary="Different wording about a bright sphere.",
        ),
    ]
    report = build_coordinate_conflict_scoring_gap_report(
        packet=_packet(
            _packet_item(
                evidence_rows=evidence_rows,
                source_summary=mixed_source_summary,
                candidate_missing=["cin_missing"],
            )
        ),
        review=_review(
            _review_item(
                recommendation="needs_more_evidence",
                confidence="low",
                time_compatibility={
                    "compatible": False,
                    "basis": "non_overlapping_or_distant_time_values",
                    "parsed": {},
                },
                failed_conditions=["time_values_compatible"],
            )
        ),
    )

    item = report["items"][0]
    assert item["review_next_action"] == "keep_blocked_until_missing_dimensions_resolved"
    assert item["provenance_status"] == "incomplete_provenance"
    assert set(item["missing_scoring_dimensions"]) >= {
        "exact_day_date",
        "compatible_time_evidence",
        "single_location_text",
        "single_source_native_id",
        "type_consistency",
        "shape_consistency",
        "description_similarity",
        "provenance_completeness",
    }
    assert report["summary"]["missing_scoring_dimension_counts"]["provenance_completeness"] == 1


def test_coordinate_conflict_scoring_gap_report_rejects_unsafe_inputs():
    packet = _packet(_packet_item())
    packet["preview_outputs_written"] = True

    with pytest.raises(ValueError, match="preview_outputs_written"):
        build_coordinate_conflict_scoring_gap_report(packet=packet, review=_review(_review_item()))

    review = _review(_review_item())
    review["auto_merge_performed"] = True

    with pytest.raises(ValueError, match="auto_merge_performed"):
        build_coordinate_conflict_scoring_gap_report(packet=_packet(_packet_item()), review=review)
