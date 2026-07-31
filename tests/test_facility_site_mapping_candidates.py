import json

from scripts.summarize_facility_site_mapping_candidates import summarize_facility_site_mapping_candidates


def write_geojson(path, features):
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")


def point_feature(name, lon, lat, country="US", source_id="authority:test"):
    return {
        "type": "Feature",
        "properties": {
            "name": name,
            "country": "United States" if country == "US" else country,
            "country_code": country,
            "source_id": source_id,
        },
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
    }


def test_facility_site_candidates_match_exact_authority_aliases(tmp_path):
    mapping_csv = tmp_path / "mapping.csv"
    mapping_csv.write_text(
        "query,count,bucket\n"
        '"holloman afb, us",10,facility_or_site\n'
        '"white sands pad 33, white sands proving grounds, nm",7,facility_or_site\n'
        '"camp hill, us",99,facility_or_site\n'
        '"columbus, us",50,city_region_like\n',
        encoding="utf-8",
    )
    military = tmp_path / "military.geojson"
    research = tmp_path / "research.geojson"
    write_geojson(military, [point_feature("Holloman Air Force Base", -106.1, 32.85, source_id="geonames:holloman")])
    write_geojson(
        research,
        [
            {
                "type": "Feature",
                "properties": {
                    "site_id": "white_sands",
                    "entity_name": "White Sands Missile Range",
                    "site_name": "White Sands test range",
                    "display_name": "White Sands Missile Range - White Sands test range",
                    "short_label": "White Sands Missile Range",
                    "aliases": ["White Sands Proving Ground", "White Sands Proving Grounds"],
                    "country_code": "US",
                },
                "geometry": {"type": "Point", "coordinates": [-106.5, 32.4]},
            }
        ],
    )

    report = summarize_facility_site_mapping_candidates(
        mapping_csv=mapping_csv,
        military_bases=military,
        research_sites=research,
    )

    assert report["canonical_outputs_mutated"] is False
    assert report["geocoding_performed"] is False
    assert report["candidate_query_count"] == 2
    assert report["candidate_event_count"] == 17
    assert {row["query"] for row in report["candidates"]} == {
        "holloman afb, us",
        "white sands pad 33, white sands proving grounds, nm",
    }
    assert report["rejected_event_counts"]["no_authority_match"] == 99


def test_facility_site_candidates_reject_non_facility_buckets_and_ambiguous_authority(tmp_path):
    mapping_csv = tmp_path / "mapping.csv"
    mapping_csv.write_text(
        "query,count,bucket\n"
        '"duplicate afb, us",4,facility_or_site\n'
        '"duplicate afb, ca",3,facility_or_site\n',
        encoding="utf-8",
    )
    military = tmp_path / "military.geojson"
    research = tmp_path / "research.geojson"
    write_geojson(
        military,
        [
            point_feature("Duplicate Air Force Base", -1, 1, country="US", source_id="a"),
            point_feature("Duplicate Air Force Base", -2, 2, country="US", source_id="b"),
            point_feature("Duplicate Air Force Base", -3, 3, country="CA", source_id="c"),
        ],
    )
    write_geojson(research, [])

    report = summarize_facility_site_mapping_candidates(
        mapping_csv=mapping_csv,
        military_bases=military,
        research_sites=research,
    )

    assert report["candidate_query_count"] == 1
    assert report["candidates"][0]["country_code"] == "CA"
    assert report["rejected_event_counts"]["ambiguous_authority_match"] == 4


def test_facility_site_candidates_reject_countryless_foreign_authority_match(tmp_path):
    mapping_csv = tmp_path / "mapping.csv"
    mapping_csv.write_text(
        "query,count,bucket\n"
        '"santa maria air force base",2,facility_or_site\n',
        encoding="utf-8",
    )
    military = tmp_path / "military.geojson"
    research = tmp_path / "research.geojson"
    write_geojson(military, [point_feature("Santa Maria Air Force Base", -53.6883, -29.71377, country="BR")])
    write_geojson(research, [])

    report = summarize_facility_site_mapping_candidates(
        mapping_csv=mapping_csv,
        military_bases=military,
        research_sites=research,
    )

    assert report["candidate_query_count"] == 0
    assert report["candidate_event_count"] == 0
    assert report["rejected_event_counts"]["no_authority_match"] == 2
