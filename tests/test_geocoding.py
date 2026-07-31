import json
from pathlib import Path

from parser.config import GeocoderConfig
from parser.geocode_cache import GeocodeCache
from parser.geocoders.nominatim import NominatimGeocoder
from parser.locations import clean_location_text, extract_description_location
from parser.pipeline import _resolve_location, run_pipeline


class DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class DummyGeocoder:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def geocode(self, query):
        self.calls.append(query)
        return self.result


def test_cache_hit_skips_second_network_call(monkeypatch, tmp_path):
    cache = GeocodeCache(tmp_path / "geocode_cache.jsonl")
    config = GeocoderConfig(
        enabled=True,
        provider="nominatim",
        endpoint="https://example.com/search",
        user_agent="tests",
        email=None,
        language="en",
        country_codes=[],
        rate_limit_seconds=0.0,
        timeout_seconds=1.0,
        query_limit_per_run=None,
        confidence_threshold=None,
        description_fallback_enabled=True,
    )
    geocoder = NominatimGeocoder(config, cache)
    call_count = {"count": 0}

    def fake_get(*args, **kwargs):
        call_count["count"] += 1
        return DummyResponse(
            [
                {
                    "lat": "33.3943",
                    "lon": "-104.5230",
                    "display_name": "Roswell, New Mexico, USA",
                    "importance": 0.73,
                    "type": "city",
                    "address": {"city": "Roswell", "country": "USA"},
                }
            ]
        )

    monkeypatch.setattr(geocoder._session, "get", fake_get)

    first = geocoder.geocode("Roswell, New Mexico")
    second = geocoder.geocode("Roswell, New Mexico")

    assert call_count["count"] == 1
    assert first == second
    assert cache.get(geocoder.provider_id, "Roswell, New Mexico")["result"]["display_name"] == "Roswell, New Mexico, USA"


def test_manual_override_beats_other_sources():
    geocoder = DummyGeocoder(
        {
            "lat": 1.0,
            "lon": 2.0,
            "display_name": "Should not be used",
            "confidence": 0.9,
            "raw": {"type": "city"},
        }
    )
    event = {
        "event_id": 42,
        "event_hash": "AAAA",
        "source_file": "sample.txt",
        "location_raw": "Roswell, New Mexico",
        "all_locations_raw": ["Roswell, New Mexico"],
        "description": "Roswell, New Mexico. Fallback description.",
        "extra_data": {"LatLong": "33.3943 -104.5230"},
    }

    result = _resolve_location(
        event,
        geocoder=geocoder,
        geocoding_state={"enabled": True, "reason": None, "deferred_count": 0},
        manual_overrides={
            "42": {
                "lat": 10.0,
                "lon": 20.0,
                "location_precision": "approximate",
                "mapping_notes": "Manual correction",
            }
        },
        geocode_failures=[],
        geocoding_enabled=True,
        description_fallback_enabled=True,
    )

    assert result["coordinate_source"] == "manual_fallback"
    assert result["lat"] == 10.0
    assert not geocoder.calls


def test_raw_latlong_beats_geocoder():
    geocoder = DummyGeocoder(
        {
            "lat": 1.0,
            "lon": 2.0,
            "display_name": "Should not be used",
            "confidence": 0.9,
            "raw": {"type": "city"},
        }
    )
    event = {
        "event_id": 43,
        "event_hash": "BBBB",
        "source_file": "sample.txt",
        "location_raw": "Roswell, New Mexico",
        "all_locations_raw": ["Roswell, New Mexico"],
        "description": "Roswell, New Mexico.",
        "extra_data": {"LatLong": "33.3943 -104.5230"},
    }

    result = _resolve_location(
        event,
        geocoder=geocoder,
        geocoding_state={"enabled": True, "reason": None, "deferred_count": 0},
        manual_overrides={},
        geocode_failures=[],
        geocoding_enabled=True,
        description_fallback_enabled=True,
    )

    assert result["coordinate_source"] == "raw_latlong"
    assert result["location_precision"] == "exact_coords"
    assert not geocoder.calls


def test_pipeline_retains_low_confidence_geocodes(tmp_path, monkeypatch):
    fixture = Path(__file__).parent / "fixtures" / "sample_ufo_input.txt"
    config_path = tmp_path / "config.yaml"
    data_dir = tmp_path / "data"
    reports_dir = data_dir / "reports"
    cache_dir = tmp_path / "cache"
    reports_dir.mkdir(parents=True)
    cache_dir.mkdir()
    normalized_path = str(data_dir / "normalized_events.json").replace("\\", "/")
    map_path = str(data_dir / "map_events.json").replace("\\", "/")
    unresolved_json = str(reports_dir / "unresolved_locations.json").replace("\\", "/")
    unresolved_csv = str(reports_dir / "unresolved_locations.csv").replace("\\", "/")
    parse_failures = str(reports_dir / "parse_failures.jsonl").replace("\\", "/")
    geocode_failures = str(reports_dir / "geocode_failures.jsonl").replace("\\", "/")
    overrides_path = str(data_dir / "manual_location_overrides.json").replace("\\", "/")
    cache_path = str(cache_dir / "geocode_cache.jsonl").replace("\\", "/")

    config_path.write_text(
        f"""
inputs:
  files:
    - {fixture.as_posix()}
outputs:
  normalized_events: {normalized_path}
  map_events: {map_path}
  unresolved_locations_json: {unresolved_json}
  unresolved_locations_csv: {unresolved_csv}
  parse_failures: {parse_failures}
  geocode_failures: {geocode_failures}
  manual_overrides: {overrides_path}
cache:
  geocode_cache: {cache_path}
geocoder:
  enabled: true
  provider: nominatim
  endpoint: https://example.com/search
  user_agent: tests
  rate_limit_seconds: 0.0
  timeout_seconds: 1
  description_fallback_enabled: true
web:
  host: 127.0.0.1
  port: 8000
  tile_url: https://example.com/{{z}}/{{x}}/{{y}}.png
  tile_attribution: example
  initial_center: [20, 0]
  initial_zoom: 2
""",
        encoding="utf-8",
    )

    class LowConfidenceGeocoder:
        def __init__(self):
            self.calls = 0

        def geocode(self, query):
            self.calls += 1
            return {
                "lat": 33.3943,
                "lon": -104.5230,
                "display_name": f"Resolved {query}",
                "confidence": 0.1,
                "raw": {"type": "city", "address": {"city": "Roswell", "country": "USA"}},
            }

    monkeypatch.setattr("parser.pipeline.create_geocoder", lambda config, cache: LowConfidenceGeocoder())

    from parser import load_config

    summary = run_pipeline(load_config(config_path))
    normalized = json.loads((data_dir / "normalized_events.json").read_text(encoding="utf-8"))
    event = next(item for item in normalized if item["event_id"] == 102)

    assert summary["normalized_events"] == 5
    assert event["coordinate_source"] == "geocoded"
    assert event["geocode_confidence"] == 0.1
    assert event["lat"] == 33.3943


def test_description_fallback_ignores_translation_prefix():
    candidate = extract_description_location("(Translated from French) In China, a bright object crossed the sky.")
    assert candidate is not None
    assert candidate.query == "China"


def test_description_fallback_prefers_complete_place_names():
    candidate = extract_description_location("Witnesses near New Mexico saw a bright object.")
    assert candidate is not None
    assert candidate.query == "New Mexico"


def test_location_aliases_are_normalized_for_geocoding():
    cleaned, approximate, notes = clean_location_text("USA, White Sands")
    assert cleaned == "White Sands, United States"
    assert not approximate
    assert any("alias" in note.lower() for note in notes)

    cleaned_dc, _, _ = clean_location_text("Washington DC")
    assert cleaned_dc == "Washington, District of Columbia, United States"


def test_state_abbreviations_expand_before_geocoding():
    cleaned, approximate, notes = clean_location_text("Los Alamos, NM")
    assert cleaned == "Los Alamos, New Mexico, United States"
    assert not approximate
    assert any("abbreviation" in note.lower() for note in notes)


def test_special_site_aliases_normalize_high_value_queries():
    cleaned, approximate, notes = clean_location_text("Pentagon")
    assert cleaned == "The Pentagon, Arlington, Virginia, United States"
    assert not approximate
    assert any("alias" in note.lower() for note in notes)
