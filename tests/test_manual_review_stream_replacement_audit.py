import json

from scripts.audit_manual_review_stream_replacements import audit_manual_review_stream_replacements


def test_replacement_audit_flags_high_risk_component_conflicts(tmp_path):
    source = tmp_path / "source.jsonl"
    candidate = tmp_path / "candidate.jsonl"
    csv_output = tmp_path / "audit.csv"
    _write_jsonl(
        source,
        [
            _event("evt_a", date_iso="1954-09-19", time_raw="1630", lat=46.3, lon=3.45, description="One"),
            _event("evt_b", date_iso="1954-09-20", time_raw="night", lat=47.3, lon=4.45, description="Two"),
        ],
    )
    _write_jsonl(
        candidate,
        [
            {
                **_event("evt_a", date_iso="1954-09-19", time_raw="1630", lat=46.3, lon=3.45),
                "canonical_input_ids": ["cin_evt_a", "cin_evt_b"],
                "dedupe_strategy": "manual_review_stream_preview_merge",
                "manual_review_preview": {
                    "merged_canonical_event_ids": ["evt_a", "evt_b"],
                    "merged_by_effect_ids": ["mre_1"],
                    "apply_policy": "manual_review_effects_stream_preview_v1",
                },
            }
        ],
    )

    report = audit_manual_review_stream_replacements(
        apply_report=_apply_report(["evt_a"]),
        source_events_path=source,
        candidate_events_path=candidate,
        csv_output_path=csv_output,
    )

    component = report["top_risk_components"][0]
    assert report["valid"] is True
    assert report["replacement_rows_audited"] == 1
    assert report["risk_counts"]["high"] == 1
    assert component["risk_level"] == "high"
    assert "date_iso_conflict" in component["risk_flags"]
    assert "coordinate_span_gt_50km" in component["risk_flags"]
    assert component["body_variance"]["description_variant_count"] == 2
    assert csv_output.read_text(encoding="utf-8").splitlines()[0].startswith("replacement_event_id,risk_level")


def test_replacement_audit_reports_missing_candidate_rows(tmp_path):
    source = tmp_path / "source.jsonl"
    candidate = tmp_path / "candidate.jsonl"
    _write_jsonl(source, [_event("evt_a")])
    _write_jsonl(candidate, [])

    report = audit_manual_review_stream_replacements(
        apply_report=_apply_report(["evt_a"]),
        source_events_path=source,
        candidate_events_path=candidate,
    )

    assert report["valid"] is False
    assert report["validation_errors"][0]["error"] == "missing_candidate_replacement_rows"


def _apply_report(replacement_ids):
    return {
        "apply_policy": "manual_review_effects_stream_preview_v1",
        "valid": True,
        "canonical_outputs_mutated": False,
        "replacement_event_ids": replacement_ids,
    }


def _event(
    event_id,
    *,
    date_iso="1954-09-19",
    time_raw="1630",
    lat=46.3,
    lon=3.45,
    description="Same",
):
    return {
        "canonical_event_id": event_id,
        "canonical_input_ids": [f"cin_{event_id}"],
        "source_file": "ufocat2023.csv",
        "source_native_id": event_id,
        "date_iso": date_iso,
        "sort_date_iso": date_iso,
        "date_precision": "exact_day",
        "time_raw": time_raw,
        "location_raw": "Rongeres, FRA",
        "city": "Rongeres",
        "state_province": "",
        "country": "FRA",
        "lat": lat,
        "lon": lon,
        "coordinate_source": "source_coordinates",
        "shape_normalized": "disc",
        "type_normalized": "3l",
        "description": description,
        "summary": description,
    }


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
