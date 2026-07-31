import pytest

from scripts.check_entity_resolution_merge_readiness import check_entity_resolution_merge_readiness


def _safe_preview(previews):
    return {
        "preview_policy": "entity_resolution_compact_merged_event_preview_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "auto_merge_performed": False,
        "missing_event_id_count": 0,
        "previews": previews,
    }


def test_entity_resolution_merge_readiness_blocks_core_conflicts():
    report = check_entity_resolution_merge_readiness(
        merged_event_preview=_safe_preview(
            [
                {
                    "patch_id": "patch_1",
                    "review_item_id": "review_1",
                    "effect_id": "effect_1",
                    "projected_event_reduction": 1,
                    "field_conflicts": {"lat": [1, 2], "summary": ["a", "b"]},
                }
            ]
        )
    )

    assert report["canonical_outputs_mutated"] is False
    assert report["blocking_conflict_item_count"] == 1
    assert report["review_conflict_item_count"] == 0
    assert report["ready_for_full_shadow_preview"] is False
    assert report["ready_for_canonical_apply"] is False
    assert report["blocking_items"][0]["review_item_id"] == "review_1"
    assert report["conflict_counts"] == {"lat": 1, "summary": 1}


def test_entity_resolution_merge_readiness_allows_review_only_conflicts_for_shadow_preview():
    report = check_entity_resolution_merge_readiness(
        merged_event_preview=_safe_preview(
            [
                {
                    "patch_id": "patch_1",
                    "review_item_id": "review_1",
                    "field_conflicts": {"summary": ["a", "b"], "description": ["a", "b"]},
                }
            ]
        )
    )

    assert report["blocking_conflict_item_count"] == 0
    assert report["review_conflict_item_count"] == 1
    assert report["review_items"][0]["patch_id"] == "patch_1"
    assert report["ready_for_full_shadow_preview"] is True
    assert report["ready_for_canonical_apply"] is False


def test_entity_resolution_merge_readiness_treats_nearby_coordinate_variance_as_review_only():
    report = check_entity_resolution_merge_readiness(
        merged_event_preview=_safe_preview(
            [
                {
                    "patch_id": "patch_1",
                    "review_item_id": "review_1",
                    "field_conflicts": {"lat": [49.93, 49.931], "lon": [-4.62, -4.621]},
                    "source_event_summaries": [
                        {"lat": 49.93, "lon": -4.62, "location_raw": "REVIN, FRA"},
                        {"lat": 49.931, "lon": -4.621, "location_raw": "REVIN, FRA"},
                    ],
                }
            ]
        )
    )

    assert report["blocking_conflict_item_count"] == 0
    assert report["review_conflict_item_count"] == 1
    assert report["ready_for_full_shadow_preview"] is True


def test_entity_resolution_merge_readiness_rejects_unsafe_preview():
    unsafe_preview = _safe_preview([])
    unsafe_preview["preview_outputs_written"] = True

    with pytest.raises(ValueError, match="merged-event preview is not safe"):
        check_entity_resolution_merge_readiness(merged_event_preview=unsafe_preview)
