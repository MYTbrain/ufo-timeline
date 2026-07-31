import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_json(relative_path: str) -> dict:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def test_military_membership_override_file_is_shipped_in_source_and_static_bundle():
    for static_root in ("webapp/static_public", "static_bundle"):
        override_path = ROOT / static_root / "data/map_overlays/military_base_overlay_membership_overrides.json"
        assert override_path.exists()
        payload = json.loads(override_path.read_text(encoding="utf-8"))
        assert payload["schema_version"] == 1
        assert payload["match_key"] == "source_id"
        assert len(payload["overrides"]) >= 380
        assert payload["summary"]["runtime_exclusion_count"] == len(payload["overrides"])


def test_military_membership_override_source_and_bundle_are_synced():
    source_payload = load_json("webapp/static_public/data/map_overlays/military_base_overlay_membership_overrides.json")
    bundle_payload = load_json("static_bundle/data/map_overlays/military_base_overlay_membership_overrides.json")

    assert source_payload == bundle_payload


def test_military_membership_exclusions_have_unique_ids_and_match_overlay():
    military = load_json("webapp/static_public/data/map_overlays/military_bases.geojson")
    supplemental = load_json("webapp/static_public/data/map_overlays/new_zealand_military_facilities.geojson")
    overrides = load_json("webapp/static_public/data/map_overlays/military_base_overlay_membership_overrides.json")
    overlay_source_ids = {
        str((feature.get("properties") or {}).get("source_id") or "")
        for feature in military["features"]
    }
    overlay_source_ids.update(
        str((feature.get("properties") or {}).get("source_id") or "")
        for feature in supplemental["features"]
    )
    override_ids = [
        str(entry.get("source_id") or "")
        for entry in overrides["overrides"]
    ]

    assert override_ids
    assert len(override_ids) == len(set(override_ids))
    assert set(override_ids) <= overlay_source_ids
    assert all(entry["membership_status"] == "exclude_from_military_overlay" for entry in overrides["overrides"])


def test_membership_override_keeps_mixed_buckets_in_manual_review_layer():
    overrides = load_json("webapp/static_public/data/map_overlays/military_base_overlay_membership_overrides.json")
    active_reasons = {
        str(entry.get("membership_reason") or "")
        for entry in overrides["overrides"]
    }
    manual_reasons = {
        str(entry.get("membership_reason") or "")
        for entry in overrides["manual_review_candidates"]
    }
    manual_review_buckets = {
        str(entry.get("review_reason") or "")
        for entry in overrides["manual_review_candidates"]
    }

    assert "civil_airways_business" in active_reasons
    assert "lifeguard_or_civil_safety" in active_reasons
    assert "railway_or_distance_marker_barracks" in active_reasons
    assert "worksite_or_distance_marker_barracks" in active_reasons
    assert "quarters_or_dormitory_artifact" in active_reasons
    assert "researched_civil_seaplane_site" in active_reasons
    assert "researched_no_operational_source" in active_reasons
    assert "researched_police_or_law_enforcement_barracks" in active_reasons
    assert "researched_support_housing_or_amenity" in active_reasons
    assert "unclassified_mixed_bucket" in manual_reasons
    assert "kazarma_barracks_or_railway_quarters" in manual_review_buckets
    assert "russian_barak_barracks_or_camp" in manual_review_buckets


def test_researched_non_military_seaplane_sites_are_excluded():
    overrides = load_json("webapp/static_public/data/map_overlays/military_base_overlay_membership_overrides.json")
    by_source_id = {
        entry["source_id"]: entry
        for entry in overrides["overrides"]
    }

    for source_id in ("geonames:8629648", "geonames:8643511"):
        assert by_source_id[source_id]["membership_status"] == "exclude_from_military_overlay"
        assert by_source_id[source_id]["membership_reason"] == "researched_civil_seaplane_site"

    assert by_source_id["geonames:9972485"]["membership_reason"] == "researched_police_or_law_enforcement_barracks"
    assert by_source_id["geonames:357803"]["membership_reason"] == "researched_no_operational_source"


def test_russian_distance_marker_barracks_are_excluded():
    overrides = load_json("webapp/static_public/data/map_overlays/military_base_overlay_membership_overrides.json")
    by_source_id = {
        entry["source_id"]: entry
        for entry in overrides["overrides"]
    }

    for source_id in (
        "geonames:6316261",
        "geonames:6316233",
        "geonames:6316226",
        "geonames:6316225",
        "geonames:6820035",
        "geonames:13095283",
        "geonames:13095342",
        "geonames:13559153",
        "geonames:13559159",
    ):
        assert by_source_id[source_id]["membership_status"] == "exclude_from_military_overlay"
        assert by_source_id[source_id]["membership_reason"] == "railway_or_distance_marker_barracks"


def test_guam_support_amenities_are_excluded():
    overrides = load_json("webapp/static_public/data/map_overlays/military_base_overlay_membership_overrides.json")
    by_source_id = {
        entry["source_id"]: entry
        for entry in overrides["overrides"]
    }

    for source_id in (
        "geonames:4045189",
        "geonames:7839943",
        "geonames:7874058",
        "geonames:7839974",
        "geonames:7874009",
        "geonames:7871459",
    ):
        assert by_source_id[source_id]["membership_status"] == "exclude_from_military_overlay"
        assert by_source_id[source_id]["membership_reason"] == "researched_support_housing_or_amenity"


def test_app_loads_membership_overrides_before_runtime_overlay_prep():
    app_js = (ROOT / "webapp/static_public/app.js").read_text(encoding="utf-8")
    assert "membershipOverridePath" in app_js
    assert "military_base_overlay_membership_overrides.json" in app_js
    assert "applyOverlayMembershipOverrides" in app_js
    loader_start = app_js.index("async function ensureOverlayLayer")
    loader = app_js[loader_start:]
    assert loader.index("applyOverlayMembershipOverrides(overlayId, payload, overridePayload)") < loader.index(
        "prepareOverlayPayloadForRuntime(overlayId, payload)"
    )
