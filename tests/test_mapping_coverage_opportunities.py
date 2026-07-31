from pathlib import Path

from scripts.summarize_mapping_coverage_opportunities import summarize_mapping_coverage_opportunities


def write_jsonl(path: Path, rows):
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def test_mapping_coverage_opportunities_summarizes_unresolved_location_text(tmp_path):
    events = tmp_path / "events.jsonl"
    cache = tmp_path / "cache.jsonl"
    write_jsonl(
        events,
        [
            '{"canonical_event_id":"evt1","source_name":"mufon","lat":1,"lon":2,"location_raw":"A"}',
            '{"canonical_event_id":"evt2","source_name":"mufon","lat":null,"lon":null,"location_raw":"Darrington, WA, US","sort_date_iso":"2011-08-17"}',
            '{"canonical_event_id":"evt3","source_name":"nuforc","lat":null,"lon":null,"location_raw":"Darrington, WA, US","sort_date_iso":"2012-01-01"}',
            '{"canonical_event_id":"evt4","source_name":"ufocat","lat":null,"lon":null,"location_raw":"United States"}',
            '{"canonical_event_id":"evt5","source_name":"ufocat","lat":null,"lon":null}',
        ],
    )
    write_jsonl(
        cache,
        [
            '{"provider_id":"nominatim:test","query":"Darrington, WA, US","normalized_query":"darrington, wa, us","result":{"lat":48.255,"lon":-121.601,"display_name":"Darrington, Washington, United States","confidence":0.8}}'
        ],
    )

    report = summarize_mapping_coverage_opportunities(events, cache)

    assert report["canonical_outputs_mutated"] is False
    assert report["geocoding_performed"] is False
    assert report["totals"]["events"] == 5
    assert report["totals"]["mapped"] == 1
    assert report["totals"]["unresolved_with_location_text"] == 3
    assert report["totals"]["unresolved_without_location_text"] == 1
    assert report["totals"]["unresolved_with_cached_geocode"] == 2
    assert report["unresolved_location_text_buckets"]["city_state_country_like"] == 2
    assert report["unresolved_location_text_buckets"]["country_or_region_only"] == 1
    assert report["top_unresolved_location_queries"][0]["query"] == "darrington, wa, us"
    assert report["top_unresolved_location_queries"][0]["count"] == 2
    assert report["top_unresolved_location_queries"][0]["cached_geocode_count"] == 2


def test_mapping_coverage_opportunities_honors_top_queries_limit(tmp_path):
    events = tmp_path / "events.jsonl"
    write_jsonl(
        events,
        [
            '{"canonical_event_id":"evt1","source_name":"mufon","lat":null,"lon":null,"location_raw":"One, WA, US"}',
            '{"canonical_event_id":"evt2","source_name":"mufon","lat":null,"lon":null,"location_raw":"One, WA, US"}',
            '{"canonical_event_id":"evt3","source_name":"mufon","lat":null,"lon":null,"location_raw":"Two, WA, US"}',
        ],
    )

    report = summarize_mapping_coverage_opportunities(events, None, top_queries_limit=1)

    assert report["top_queries_limit"] == 1
    assert len(report["top_unresolved_location_queries"]) == 1
    assert report["top_unresolved_location_queries"][0]["query"] == "one, wa, us"
