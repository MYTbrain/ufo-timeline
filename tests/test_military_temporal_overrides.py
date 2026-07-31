import json
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_json(relative_path: str) -> dict:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def interval_visible(interval: dict, year: int) -> bool:
    start_year = interval.get("start_year")
    end_year = interval.get("end_year")
    if start_year is not None and int(start_year) > year:
        return False
    if end_year is not None and int(end_year) < year:
        return False
    return True


def test_military_temporal_override_file_is_shipped_in_source_and_static_bundle():
    for static_root in ("webapp/static_public", "static_bundle"):
        override_path = ROOT / static_root / "data/map_overlays/military_base_temporal_overrides.json"
        assert override_path.exists()
        payload = json.loads(override_path.read_text(encoding="utf-8"))
        assert payload["schema_version"] == 1
        assert payload["match_key"] == "source_id"
        assert len(payload["overrides"]) >= 830


def test_military_temporal_override_source_and_bundle_are_synced():
    source_payload = load_json("webapp/static_public/data/map_overlays/military_base_temporal_overrides.json")
    bundle_payload = load_json("static_bundle/data/map_overlays/military_base_temporal_overrides.json")

    assert source_payload == bundle_payload


def test_military_temporal_overrides_have_unique_ids_and_dates():
    overrides = load_json("webapp/static_public/data/map_overlays/military_base_temporal_overrides.json")
    override_entries = list(overrides["overrides"])
    override_ids = [str(entry.get("source_id") or "").strip() for entry in override_entries]

    assert override_ids
    assert len(override_ids) == len(set(override_ids))
    assert all(
        entry.get("start_year") is not None
        or entry.get("end_year") is not None
        or entry.get("operational_intervals")
        for entry in override_entries
    )


def test_military_temporal_override_source_ids_match_base_overlay():
    military = load_json("webapp/static_public/data/map_overlays/military_bases.geojson")
    overrides = load_json("webapp/static_public/data/map_overlays/military_base_temporal_overrides.json")
    base_source_ids = {
        str((feature.get("properties") or {}).get("source_id") or "")
        for feature in military["features"]
    }
    override_ids = {
        str(entry.get("source_id") or "")
        for entry in overrides["overrides"]
    }

    assert override_ids
    assert override_ids <= base_source_ids


def test_military_temporal_override_countries_match_overlay_features_when_present():
    military = load_json("webapp/static_public/data/map_overlays/military_bases.geojson")
    overrides = load_json("webapp/static_public/data/map_overlays/military_base_temporal_overrides.json")
    overlay_country_by_source_id = {
        str((feature.get("properties") or {}).get("source_id") or ""): str(
            (feature.get("properties") or {}).get("country_code")
            or (feature.get("properties") or {}).get("country")
            or ""
        )
        for feature in military["features"]
    }

    for entry in overrides["overrides"]:
        entry_country = str(entry.get("country_code") or "").strip()
        if not entry_country:
            continue
        overlay_country = overlay_country_by_source_id.get(str(entry.get("source_id") or ""), "")
        assert entry_country == overlay_country


def test_military_temporal_intervals_preserve_closed_or_gap_years():
    overrides = load_json("webapp/static_public/data/map_overlays/military_base_temporal_overrides.json")
    by_source_id = {
        entry["source_id"]: entry
        for entry in overrides["overrides"]
    }

    nellis_intervals = by_source_id["geonames:8479536"]["operational_intervals"]
    assert any(interval_visible(interval, 1944) for interval in nellis_intervals)
    assert not any(interval_visible(interval, 1948) for interval in nellis_intervals)
    assert any(interval_visible(interval, 1954) for interval in nellis_intervals)

    greenham = by_source_id["geonames:6301522"]
    assert greenham["start_year"] == 1942
    assert greenham["end_year"] == 1992


def test_researched_facility_candidates_have_temporal_bounds():
    overrides = load_json("webapp/static_public/data/map_overlays/military_base_temporal_overrides.json")
    by_source_id = {
        entry["source_id"]: entry
        for entry in overrides["overrides"]
    }

    pollenca = by_source_id["geonames:11995822"]
    assert pollenca["start_year"] == 1937
    assert pollenca["end_year"] is None

    dumont = by_source_id["geonames:12501143"]
    assert dumont["start_year"] == 1895
    assert dumont["end_year"] == 1946

    kisarazu = by_source_id["geonames:12953987"]
    assert kisarazu["start_year"] == 1969
    assert kisarazu["end_year"] is None

    sarba = by_source_id["geonames:268151"]
    assert sarba["start_year"] == 1994
    assert sarba["end_year"] is None

    wavell = by_source_id["geonames:80813"]
    assert wavell["start_year"] == 1955
    assert wavell["end_year"] == 1968

    pomona = by_source_id["geonames:1106440"]
    assert pomona["start_year"] == 1999
    assert pomona["end_year"] is None

    guozhuang = by_source_id["geonames:11493886"]
    assert guozhuang["start_year"] == 1950
    assert guozhuang["end_year"] is None

    karankut = by_source_id["geonames:11749495"]
    assert karankut["start_year"] == 1940
    assert karankut["end_year"] == 1995

    cedar_springs_alias = by_source_id["geonames:5919633"]
    assert cedar_springs_alias["start_year"] == 1912
    assert cedar_springs_alias["copy_from_source_id"] == "geonames:5918916"

    mount_mckay_alias = by_source_id["geonames:5919653"]
    assert mount_mckay_alias["start_year"] == 1907
    assert mount_mckay_alias["copy_from_source_id"] == "geonames:6081841"

    saint_bruno_alias = by_source_id["geonames:5919644"]
    assert saint_bruno_alias["start_year"] == 1938
    assert saint_bruno_alias["end_year"] == 2017
    assert saint_bruno_alias["copy_from_source_id"] == "geonames:6083456"

    chezzetcook_alias = by_source_id["geonames:5919627"]
    assert chezzetcook_alias["start_year"] is None
    assert chezzetcook_alias["end_year"] == 1984
    assert chezzetcook_alias["copy_from_source_id"] == "geonames:5921136"

    abashiri = by_source_id["geonames:11717277"]
    assert abashiri["start_year"] == 1950
    assert abashiri["end_year"] is None

    sodegaura = by_source_id["geonames:11077475"]
    assert sodegaura["start_year"] == 1972
    assert sodegaura["end_year"] == 2010

    chilcotin = by_source_id["geonames:5921322"]
    assert chilcotin["start_year"] == 1923
    assert chilcotin["end_year"] is None

    sussex = by_source_id["geonames:6159986"]
    assert sussex["start_year"] == 1885
    assert sussex["end_year"] is None

    boreel = by_source_id["geonames:6950892"]
    assert boreel["start_year"] == 1849
    assert boreel["end_year"] == 1997

    oberfeld = by_source_id["geonames:2605387"]
    assert oberfeld["start_year"] == 1930
    assert oberfeld["end_year"] == 2009

    setermoen = by_source_id["geonames:6545376"]
    assert setermoen["start_year"] == 1897
    assert setermoen["end_year"] is None

    al_qusayr = by_source_id["geonames:11749483"]
    assert al_qusayr["start_year"] == 1987
    assert al_qusayr["end_year"] is None

    meiktila = by_source_id["geonames:11749514"]
    assert meiktila["start_year"] == 1942
    assert meiktila["end_year"] is None


def test_temporal_priority_queue_recognizes_new_candidate_and_no_override_keys():
    script_path = ROOT / "scripts/build_military_temporal_priority_queue.py"
    spec = importlib.util.spec_from_file_location("build_military_temporal_priority_queue", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    dispositions = module.load_research_dispositions()

    assert "military_base_temporal_backfill_researched_candidates_2026-06-05-batch4.json" in dispositions[
        "geonames:11493886"
    ]["candidate_reports"]
    assert "military_base_temporal_backfill_researched_candidates_2026-06-05-batch4.json" in dispositions[
        "geonames:11493835"
    ]["skipped_reports"]


def test_app_loads_temporal_overrides_before_runtime_overlay_prep():
    app_js = (ROOT / "webapp/static_public/app.js").read_text(encoding="utf-8")
    assert "temporalOverridePath" in app_js
    assert "military_base_temporal_overrides.json" in app_js
    assert "applyOverlayTemporalOverrides" in app_js
    loader_start = app_js.index("async function ensureOverlayLayer")
    loader = app_js[loader_start:]
    assert loader.index("applyOverlayTemporalOverrides(overlayId, payload, overridePayload)") < loader.index(
        "prepareOverlayPayloadForRuntime(overlayId, payload)"
    )
    assert "overlayOperationIntervals" in app_js
    assert "Operational dates unknown" in app_js


def test_military_overlay_does_not_treat_unknown_dates_as_always_visible():
    app_js = (ROOT / "webapp/static_public/app.js").read_text(encoding="utf-8")
    function_start = app_js.index("function militaryFeatureVisible")
    function_body = app_js[function_start:app_js.index("function isFocusMapActive", function_start)]

    assert "feature.__overlayHasTemporalBounds" in function_body
    assert "overlayFeatureVisibleInCurrentTimeWindow(feature)" in function_body
