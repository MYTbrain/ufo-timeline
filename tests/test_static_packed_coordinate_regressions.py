import json

from parser.packed_points import export_packed_points
from scripts.check_static_packed_coordinate_regressions import check_static_packed_coordinate_regressions


def write_packed_payload(root, events):
    canonical_dir = root / "data" / "canonical_web"
    chunk_dir = canonical_dir / "event_chunks"
    chunk_dir.mkdir(parents=True)
    chunk_id = "chunk_000000"
    (chunk_dir / f"{chunk_id}.json").write_text(json.dumps({"events": events}), encoding="utf-8")
    chunk_manifest = [
        {
            "id": chunk_id,
            "start_event_id": min(int(event["event_id"]) for event in events),
            "end_event_id": max(int(event["event_id"]) for event in events),
            "details": [{"event_id": event["event_id"]} for event in events],
        }
    ]
    export_packed_points(events, canonical_dir, chunk_manifest=chunk_manifest)


def test_static_packed_coordinate_regression_check_passes_for_rendered_us_rows(tmp_path):
    root = tmp_path / "bundle"
    write_packed_payload(
        root,
        [
            {
                "event_id": 100,
                "sort_date_iso": "1954-09-20",
                "location_raw": "FARGO, Cass, ND, US",
                "source": "ufocat",
                "coordinate_source": "raw_latlong",
                "location_precision": "exact_coords",
                "lat": 46.88,
                "lon": -96.78,
            }
        ],
    )

    report = check_static_packed_coordinate_regressions(
        payload_root=root,
        named_regressions=[{"label": "FARGO, Cass, ND, US", "contains": "FARGO", "state": "ND"}],
        named_country_regressions=[],
    )

    assert report["status"] == "ready"
    assert report["counts"]["scanned_rows"] == 1
    assert report["counts"]["rows_with_full_event"] == 1
    assert report["counts"]["explicit_us_outside_bounds"] == 0
    assert report["counts"]["explicit_us_outside_state_bounds"] == 0


def test_static_packed_coordinate_regression_check_fails_for_rendered_us_row_in_asia(tmp_path):
    root = tmp_path / "bundle"
    write_packed_payload(
        root,
        [
            {
                "event_id": 100,
                "sort_date_iso": "1954-09-20",
                "location_raw": "FARGO, Cass, ND, US",
                "source": "ufocat",
                "coordinate_source": "raw_latlong",
                "location_precision": "exact_coords",
                "lat": 46.88,
                "lon": 96.78,
            }
        ],
    )

    report = check_static_packed_coordinate_regressions(
        payload_root=root,
        named_regressions=[{"label": "FARGO, Cass, ND, US", "contains": "FARGO", "state": "ND"}],
        named_country_regressions=[],
    )

    assert report["status"] == "needs_attention"
    assert report["counts"]["explicit_us_outside_bounds"] == 1
    assert report["counts"]["explicit_us_outside_state_bounds"] == 1
    assert report["counts"]["named_regression_failures"] == 1
    assert report["outside_examples"][0]["location_raw"] == "FARGO, Cass, ND, US"


def test_static_packed_coordinate_regression_check_fails_for_rendered_europe_row_in_atlantic(tmp_path):
    root = tmp_path / "bundle"
    write_packed_payload(
        root,
        [
            {
                "event_id": 200,
                "sort_date_iso": "1954-10-06",
                "location_raw": "WIEN (VIENNA), Vienna, AUT, EU",
                "source": "ufocat",
                "coordinate_source": "raw_latlong",
                "location_precision": "exact_coords",
                "lat": 48.2,
                "lon": -14.3,
            }
        ],
    )

    report = check_static_packed_coordinate_regressions(
        payload_root=root,
        named_regressions=[],
        named_country_regressions=[
            {
                "label": "WIEN (VIENNA), Vienna, AUT, EU",
                "contains": "WIEN",
                "country_tokens": {"AUT", "AUSTRIA"},
                "bounds": {"lat_min": 46.0, "lat_max": 50.0, "lon_min": 9.0, "lon_max": 18.0},
            }
        ],
    )

    assert report["status"] == "needs_attention"
    assert report["counts"]["named_country_regression_failures"] == 1
    assert report["named_country_regressions"][0]["found"] == 1
    assert report["named_country_regressions"][0]["outside_bounds"] == 1
