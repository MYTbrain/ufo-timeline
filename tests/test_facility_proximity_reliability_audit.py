import hashlib
import json
from pathlib import Path

import pytest

from parser.packed_points import export_packed_points
from scripts.audit_facility_proximity_reliability import (
    AuditInputError,
    FacilityGrid,
    FacilityPoint,
    audit,
    load_runtime_facilities,
    parse_radii,
    render_markdown,
    write_outputs,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _feature(source_id: str, lon: float, lat: float, **properties) -> dict:
    return {
        "type": "Feature",
        "properties": {"source_id": source_id, **properties},
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
    }


def _build_facility_fixture(root: Path) -> Path:
    static_root = root / "static"
    overlays = static_root / "data" / "map_overlays"
    _write_json(
        overlays / "military_bases.geojson",
        {
            "type": "FeatureCollection",
            "features": [
                _feature("military-keep", 0.0, 0.0),
                _feature("military-exclude", 0.01, 0.0),
                _feature("military-replaced", 10.0, 10.0),
                _feature("military-undated", 5.0, 5.0),
            ],
        },
    )
    _write_json(
        overlays / "new_zealand_military_facilities.geojson",
        {
            "type": "FeatureCollection",
            "features": [
                _feature(
                    "military-supplement",
                    20.0,
                    20.0,
                    replaces_source_id="military-replaced",
                    start_year=1970,
                )
            ],
        },
    )
    _write_json(
        overlays / "military_base_temporal_overrides.json",
        {
            "overrides": [
                {"source_id": "military-keep", "start_year": 1950},
                {"source_id": "not-present", "start_year": 2000},
            ]
        },
    )
    _write_json(
        overlays / "military_base_overlay_membership_overrides.json",
        {
            "overrides": [
                {
                    "source_id": "military-exclude",
                    "membership_status": "exclude_from_military_overlay",
                }
            ]
        },
    )
    _write_json(
        overlays / "research_test_sites.geojson",
        {
            "type": "FeatureCollection",
            "features": [_feature("research-primary", 0.0, 0.1)],
        },
    )
    _write_json(
        overlays / "northern_europe_research_test_sites_pass3_marker_sized_conservative.geojson",
        {
            "type": "FeatureCollection",
            "features": [
                _feature("research-maybe", 30.0, 30.0, recommended_include="maybe"),
                _feature("research-no", 31.0, 31.0, recommended_include="no"),
            ],
        },
    )
    _write_json(
        overlays / "new_zealand_research_facilities.geojson",
        {"type": "FeatureCollection", "features": []},
    )
    _write_json(
        static_root / "data" / "claimed_ufo_bases.json",
        {
            "sites": [
                {
                    "site_id": "claimed-one",
                    "claim_family": "claimed_ufo_bases",
                    "lat": 0.0,
                    "lng": 0.0,
                },
                {
                    "site_id": "wrong-family",
                    "claim_family": "other",
                    "lat": 0.0,
                    "lng": 0.0,
                },
            ]
        },
    )
    return static_root


def _build_points_fixture(root: Path) -> Path:
    canonical = root / "canonical_web"
    export_packed_points(
        [
            {
                "event_id": 1,
                "lat": 0.0,
                "lon": 0.0,
                "source": "alpha",
                "coordinate_source": "raw_latlong",
                "location_precision": "exact_coords",
                "date_precision": "exact_day",
            },
            {
                "event_id": 2,
                "lat": 0.0,
                "lon": 0.0,
                "source": "alpha",
                "coordinate_source": "geocoded",
                "location_precision": "city",
                "date_precision": "exact_day",
            },
            {
                "event_id": 3,
                "lat": 0.0,
                "lon": 0.0,
                "source": "beta",
                "coordinate_source": "geocoded",
                "location_precision": "city",
                "date_precision": "month",
            },
            {
                "event_id": 4,
                "lat": 0.1,
                "lon": 0.0,
                "source": "beta",
                "coordinate_source": "geocoded",
                "location_precision": "state",
                "date_precision": "exact_day",
            },
            {
                "event_id": 5,
                "lat": -20.0,
                "lon": -20.0,
                "source": "beta",
                "coordinate_source": "raw_latlong",
                "location_precision": "exact_coords",
                "date_precision": "year",
            },
        ],
        canonical,
    )
    return canonical


def _rows_by_value(rows: list[dict], key: str) -> dict[str, dict]:
    return {row[key]: row for row in rows}


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_audit_decodes_points_assembles_runtime_sources_and_reports_exposure(tmp_path: Path):
    canonical = _build_points_fixture(tmp_path)
    static_root = _build_facility_fixture(tmp_path)

    report = audit(
        canonical,
        static_root,
        radii_km=(3, 15),
        pile_min_size=2,
        top_piles=2,
    )

    assert report["canonical_points"]["mapped_event_count"] == 5
    cohorts = _rows_by_value(
        report["canonical_points"]["evidence_cohort_counts"], "evidence_cohort"
    )
    assert cohorts["source_coordinates"]["count"] == 2
    assert cohorts["generalized_city"]["count"] == 2
    assert cohorts["generalized_admin"]["count"] == 1
    strict_evidence = _rows_by_value(
        report["canonical_points"]["strict_endpoint_evidence_counts"],
        "strict_endpoint_evidence",
    )
    assert strict_evidence["eligible"]["count"] == 1
    assert strict_evidence["not_eligible"]["count"] == 4
    date_precision = _rows_by_value(
        report["canonical_points"]["date_precision_counts"], "date_precision"
    )
    assert date_precision["exact_day"]["count"] == 3
    assert date_precision["month"]["count"] == 1
    assert date_precision["year"]["count"] == 1

    piles = report["repeated_coordinate_piles"]
    assert piles["repeated_coordinate_groups"] == 1
    assert piles["events_in_repeated_coordinate_groups"] == 3
    assert piles["top_piles"][0]["lat"] == 0.0
    assert piles["top_piles"][0]["lon"] == 0.0
    assert piles["top_piles"][0]["event_count"] == 3

    details = report["runtime_facilities"]["load_details"]
    assert details["military"]["replaced_primary_features"] == 1
    assert details["military"]["membership_features_removed"] == 1
    assert details["military"]["temporal_overrides_applied"] == 1
    assert details["military"]["features_without_temporal_bounds_excluded"] == 1
    assert details["military"]["runtime_features"] == 2
    assert details["researchSites"]["recommended_include_no_excluded"] == 1
    assert details["claimedUfoBases"]["wrong_claim_family_excluded"] == 1

    radius_3, radius_15 = report["proximity_exposure"]
    assert radius_3["events_with_any_facility_match"] == 4
    radius_3_cohorts = _rows_by_value(radius_3["by_evidence_cohort"], "evidence_cohort")
    assert radius_3_cohorts["generalized_city"]["matched_events"] == 2
    assert radius_3_cohorts["generalized_admin"]["matched_events"] == 1
    assert report["reliability_summary"][0]["strict_endpoint_eligible_matched_events"] == 1
    assert (
        report["reliability_summary"][0][
            "source_coordinate_non_exact_date_matched_events"
        ]
        == 0
    )
    assert radius_15["events_with_any_facility_match"] == 4
    sources = _rows_by_value(radius_3["by_facility_source"], "facility_source")
    assert sources["military"]["matched_events"] == 3
    assert sources["claimedUfoBases"]["matched_events"] == 3
    assert sources["researchSites"]["matched_events"] == 1


def test_report_is_deterministic_and_outputs_cannot_overwrite_inputs(tmp_path: Path):
    canonical = _build_points_fixture(tmp_path)
    static_root = _build_facility_fixture(tmp_path)
    points_hash_before = _digest(canonical / "points.bin")
    meta_hash_before = _digest(canonical / "points_meta.json")

    first = audit(canonical, static_root, radii_km=(15, 3, 3), pile_min_size=2)
    second = audit(canonical, static_root, radii_km=(3, 15), pile_min_size=2)

    first_json = json.dumps(first, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    second_json = json.dumps(second, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    assert first_json == second_json
    assert render_markdown(first) == render_markdown(second)

    output_dir = tmp_path / "reports"
    written = write_outputs(
        first,
        json_output=output_dir / "audit.json",
        markdown_output=output_dir / "audit.md",
        canonical_dir=canonical,
        facility_root=static_root,
    )
    assert written == [output_dir / "audit.json", output_dir / "audit.md"]
    assert json.loads((output_dir / "audit.json").read_text(encoding="utf-8")) == first
    assert (output_dir / "audit.md").read_text(encoding="utf-8") == render_markdown(first)
    assert _digest(canonical / "points.bin") == points_hash_before
    assert _digest(canonical / "points_meta.json") == meta_hash_before

    with pytest.raises(AuditInputError, match="protected input tree"):
        write_outputs(
            first,
            json_output=canonical / "forbidden.json",
            markdown_output=None,
            canonical_dir=canonical,
            facility_root=static_root,
        )


def test_runtime_loader_and_parameter_validation_fail_closed(tmp_path: Path):
    static_root = _build_facility_fixture(tmp_path)
    runtime = load_runtime_facilities(static_root)
    assert {point.facility_source for point in runtime.points} == {
        "military",
        "researchSites",
        "claimedUfoBases",
    }
    assert parse_radii("5,1,5,3") == (1.0, 3.0, 5.0)
    with pytest.raises(AuditInputError, match="Radius must"):
        parse_radii("0,3")

    (static_root / "data" / "map_overlays" / "military_bases.geojson").unlink()
    with pytest.raises(AuditInputError, match="does not exist"):
        load_runtime_facilities(static_root)


def test_facility_grid_handles_dateline_and_polar_radius_bounds():
    dateline = FacilityPoint(0.0, -179.9, "military", "dateline", "fixture")
    polar = FacilityPoint(89.0, 120.0, "researchSites", "polar", "fixture")
    grid = FacilityGrid([dateline, polar])

    assert [item[0].facility_key for item in grid.nearby(0.0, 179.9, 30_000)] == [
        "dateline"
    ]
    assert [item[0].facility_key for item in grid.nearby(89.0, -120.0, 250_000)] == [
        "polar"
    ]
