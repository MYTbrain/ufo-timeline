from copy import deepcopy
import csv
import gzip
import json

import pytest

from scripts.build_analysis_reviewed_year_overlay import (
    DATE_FIELDS, RAW_FIELDS, SUMMARY_FIELDS, CONTRACT, EXPECTED_REVIEW_SHA256,
    OVERLAY_ID, TARGETS, _verify_source_observations, apply_detail_patch,
    apply_summary_patch, digest, identity, load_patch_map, pin, raw_json, year_patch,
)


def example():
    event_id = "192457427678091"
    narrative = "Matched source occurrence account back in 1967 in Florida; a later follow-up took place in 1978."
    detail = {
        "event_id": int(event_id), "canonical_event_id": "evt-reviewed-fixture", "source": "phenomenainon_updb",
        "source_id": "5198825", "date_raw": "1900-01-01", "date_iso": "1900-01-01",
        "date_precision": "exact_day", "sort_date_iso": "1900-01-01", "chunk_id": "chunk_000244", "detail_index": 1910,
        "lat": 29.65, "lon": -82.32, "same_day_match_strength": "strong", "playback_sort_key": [3, None, None, 3, 0, event_id],
        "raw_source_row": {"id": "5198825", "source": "2", "source_id": "S10085", "name": "NUFORC", "date": "1900-01-01 00:00:00", "city": "GAINESVILLE", "country": "US", "description": narrative},
    }
    summary = {key: value for key, value in detail.items() if key not in {"canonical_event_id", "source_id", "raw_source_row", "date_iso"}}
    patch = {
        "eventId": event_id, "canonicalEventId": detail["canonical_event_id"], "source": detail["source"],
        "updbNativeId": detail["source_id"], "underlyingNativeId": "S10085", "rawDate": "1900-01-01",
        "rawDateSha256": digest(b"1900-01-01"), "detailDateIdentitySha256": identity(detail, DATE_FIELDS),
        "summaryDateIdentitySha256": identity(summary, SUMMARY_FIELDS), "rawSourceIdentitySha256": identity(detail["raw_source_row"], RAW_FIELDS),
        "sourceNarrativeSha256": digest(narrative.encode()), "occurrenceClause": "back in 1967 in Florida", "patch": year_patch(1967),
    }
    return detail, summary, patch


def test_calendar_year_bounds_and_sort_midpoint_do_not_assert_a_day():
    for year in (1967, 1975, 1968):
        patch = year_patch(year)
        assert patch["date_iso"] == f"{year}-01-01"
        assert patch["end_date_iso"] == f"{year}-12-31"
        assert patch["sort_date_iso"] == ("1968-07-01" if year == 1968 else f"{year}-07-02")
        assert patch["date_precision"] == "year"
        assert patch["exact_day_eligible"] is False
        assert patch["date_recovery_contract"] == CONTRACT


def test_detail_overlay_preserves_raw_and_spatial_linkage_without_mutating_input():
    detail, _, patch = example()
    before = deepcopy(detail)
    result = apply_detail_patch(detail, {patch["eventId"]: patch})
    assert detail == before
    assert result["raw_source_row"] == before["raw_source_row"]
    assert result["date_raw"] == "1900-01-01"
    for key in ("event_id", "lat", "lon", "same_day_match_strength", "playback_sort_key", "chunk_id", "detail_index"):
        assert result[key] == before[key]
    assert result["date_precision"] == "year"
    assert result["date_recovery_provenance"]["sort_midpoint_is_observed_day"] is False
    with pytest.raises(ValueError, match="normalized date"):
        apply_detail_patch(result, {patch["eventId"]: patch})


@pytest.mark.parametrize("mutation", [
    lambda row: row.update(date_raw="1967"),
    lambda row: row.update(date_iso="1900-02-01"),
    lambda row: row.update(source="nuforc"),
    lambda row: row.update(source_id="different"),
    lambda row: row.update(canonical_event_id="different"),
    lambda row: row["raw_source_row"].update(source_id="S10086"),
    lambda row: row["raw_source_row"].update(description="An unrelated event in 1967"),
])
def test_detail_guard_rejects_changed_source_native_date_and_narrative(mutation):
    detail, _, patch = example()
    mutation(detail)
    with pytest.raises(ValueError):
        apply_detail_patch(detail, {patch["eventId"]: patch})


def test_summary_overlay_keeps_locator_and_does_not_promote_match_evidence():
    _, summary, patch = example()
    before = deepcopy(summary)
    result = apply_summary_patch(summary, patch)
    assert summary == before
    assert result["detail_index"] == 1910
    assert result["same_day_match_strength"] == "strong"
    assert result["exact_day_eligible"] is False
    summary["detail_index"] += 1
    with pytest.raises(ValueError, match="locator identity"):
        apply_summary_patch(summary, patch)


def test_unrelated_rows_are_retained_and_patch_allowlist_rejects_precision_promotion(tmp_path):
    detail, _, first = example()
    unrelated = dict(detail, event_id=123)
    assert apply_detail_patch(unrelated, {first["eventId"]: first}) is unrelated
    second = deepcopy(first)
    second.update(eventId="2629924530431414", updbNativeId="5202682", underlyingNativeId="S13010", patch=year_patch(1975))
    packet = {"overlayId": OVERLAY_ID, "sourceReviewSha256": EXPECTED_REVIEW_SHA256, "patches": [first, second]}
    path = tmp_path / "patches.json.gz"
    path.write_bytes(gzip.compress(raw_json(packet)))
    assert set(load_patch_map(str(path))) == set(TARGETS)
    first["patch"]["date_precision"] = "exact_day"
    path.write_bytes(gzip.compress(raw_json(packet)))
    load_patch_map.cache_clear()
    with pytest.raises(ValueError, match="date/source contract"):
        load_patch_map(str(path))


def test_structured_occurrence_role_and_frozen_csv_identity_are_required(tmp_path):
    path = tmp_path / "nuforc.csv"
    fields = {"No": "10085", "Occurred": " 1967-05-01 20:00 Local - Approximate", "Reported": "1999-10-06", "Posted": "1999-10-19", "Description": "back in 1967 in Florida"}
    def write():
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerow(fields)
    write()
    proposal = {"eventId": "192457427678091", "sourceObservations": [{"file": str(path), "sourceRowNumber": 2, "nativeId": "10085", "fields": {key: fields[key].strip() for key in ("Occurred", "Reported", "Posted")}}], "calendarPrecisionDecision": {"occurrenceClause": "back in 1967 in Florida"}}
    review = {"inputs": [pin(path)]}
    assert len(_verify_source_observations(review, [proposal])) == 1
    fields["Occurred"] = "1999-10-06"
    write()
    with pytest.raises(ValueError, match="receipt changed"):
        _verify_source_observations(review, [proposal])
