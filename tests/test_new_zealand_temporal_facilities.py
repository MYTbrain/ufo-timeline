import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_json(relative_path: str) -> dict:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def visible_nz_facility_names(features: list[dict], year: int) -> set[str]:
    names: set[str] = set()
    for feature in features:
        properties = feature.get("properties") or {}
        if properties.get("country_code") != "NZ":
            continue
        start_year = properties.get("start_year")
        end_year = properties.get("end_year")
        if start_year is not None and int(start_year) > year:
            continue
        if end_year is not None and int(end_year) < year:
            continue
        names.add(properties.get("name") or properties.get("display_name"))
    return names


def merge_with_supplemental_replacements(base_features: list[dict], supplemental_features: list[dict]) -> list[dict]:
    replacement_source_ids = {
        str((feature.get("properties") or {}).get("replaces_source_id"))
        for feature in supplemental_features
        if (feature.get("properties") or {}).get("replaces_source_id")
    }
    return [
        feature
        for feature in base_features
        if str((feature.get("properties") or {}).get("source_id") or "") not in replacement_source_ids
    ] + supplemental_features


def test_new_zealand_facility_supplements_are_shipped_in_source_and_static_bundle():
    for static_root in ("webapp/static_public", "static_bundle"):
        military = load_json(f"{static_root}/data/map_overlays/new_zealand_military_facilities.geojson")
        research = load_json(f"{static_root}/data/map_overlays/new_zealand_research_facilities.geojson")

        assert len(military["features"]) == 11
        assert len(research["features"]) == 4
        assert all((feature["properties"] or {}).get("country_code") == "NZ" for feature in military["features"])
        assert all((feature["properties"] or {}).get("country_code") == "NZ" for feature in research["features"])


def test_new_zealand_facility_dates_match_representative_windows():
    base_military = load_json("webapp/static_public/data/map_overlays/military_bases.geojson")
    nz_military = load_json("webapp/static_public/data/map_overlays/new_zealand_military_facilities.geojson")
    nz_research = load_json("webapp/static_public/data/map_overlays/new_zealand_research_facilities.geojson")
    merged_military = merge_with_supplemental_replacements(base_military["features"], nz_military["features"])

    assert sum(
        1 for feature in merged_military if "Whenuapai" in ((feature.get("properties") or {}).get("name") or "")
    ) == 1

    visible_1954 = visible_nz_facility_names(merged_military, 1954)
    assert "RNZAF Base Auckland / Whenuapai" in visible_1954
    assert "RNZAF Base Ohakea" in visible_1954
    assert "RNZAF Base Wigram" in visible_1954
    assert "RNZAF Station Hobsonville" in visible_1954

    visible_2017 = visible_nz_facility_names(merged_military, 2017)
    assert "RNZAF Base Wigram" not in visible_2017
    assert "RNZAF Station Hobsonville" not in visible_2017
    assert "RNZAF Base Ohakea" in visible_2017

    visible_research_1990 = visible_nz_facility_names(nz_research["features"], 1990)
    assert "Waihopai Station" in visible_research_1990
    assert "Tangimoana Station" in visible_research_1990
    assert "Rocket Lab Launch Complex 1" not in visible_research_1990

    visible_research_2017 = visible_nz_facility_names(nz_research["features"], 2017)
    assert "Rocket Lab Launch Complex 1" in visible_research_2017
    assert "University of Canterbury Mt John Observatory" in visible_research_2017


def test_app_references_new_zealand_supplements_and_temporal_refresh():
    app_js = (ROOT / "webapp/static_public/app.js").read_text(encoding="utf-8")
    assert "new_zealand_military_facilities.geojson" in app_js
    assert "new_zealand_research_facilities.geojson" in app_js
    assert "overlayFeatureVisibleInCurrentTimeWindow" in app_js
    assert "refreshTemporalOverlayLayersForCurrentWindow" in app_js
