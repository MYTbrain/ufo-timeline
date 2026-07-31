import json

from scripts.summarize_cached_geocode_mapping_candidates import summarize_cached_geocode_mapping_candidates


def test_cached_geocode_candidates_keep_safe_places_and_reject_risky_rows(tmp_path):
    mapping_csv = tmp_path / "mapping.csv"
    mapping_csv.write_text(
        "query,count,bucket,source_count,cached_geocode_count,cached_geocode_confidence,cached_geocode_display_name,sample_location_raw,sample_event_id,earliest_sort_date,latest_sort_date\n"
        '"rome, italy",5,city_region_like,1,5,,,,,\n'
        "china,4,country_or_region_only,1,4,,,,,\n"
        '"caledonia, scotland",3,city_region_like,1,3,,,,,\n'
        "weak place,2,city_region_like,1,2,,,,,\n",
        encoding="utf-8",
    )
    cache = tmp_path / "cache.jsonl"
    rows = [
        {
            "provider_id": "nominatim:test",
            "normalized_query": "rome, italy",
            "result": {
                "lat": 41.8933,
                "lon": 12.4829,
                "display_name": "Rome, Italy",
                "confidence": 0.88,
                "raw": {"addresstype": "city", "category": "boundary"},
            },
        },
        {
            "provider_id": "nominatim:test",
            "normalized_query": "china",
            "result": {
                "lat": 35.0,
                "lon": 105.0,
                "display_name": "China",
                "confidence": 0.9,
                "raw": {"addresstype": "country", "category": "boundary"},
            },
        },
        {
            "provider_id": "nominatim:test",
            "normalized_query": "caledonia, scotland",
            "result": {
                "lat": 55.95,
                "lon": -3.18,
                "display_name": "Caledonia shop",
                "confidence": 0.9,
                "raw": {"addresstype": "shop", "category": "shop"},
            },
        },
        {
            "provider_id": "nominatim:test",
            "normalized_query": "weak place",
            "result": {
                "lat": 1,
                "lon": 2,
                "display_name": "Weak Place",
                "confidence": 0.25,
                "raw": {"addresstype": "city", "category": "boundary"},
            },
        },
    ]
    cache.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    report = summarize_cached_geocode_mapping_candidates(mapping_csv=mapping_csv, geocode_cache=cache)

    assert report["canonical_outputs_mutated"] is False
    assert report["geocoding_performed"] is False
    assert report["cached_query_count"] == 4
    assert report["candidate_query_count"] == 1
    assert report["candidate_event_count"] == 5
    assert report["candidates"][0]["query"] == "rome, italy"
    assert report["rejected_event_counts"]["broad_centroid"] == 4
    assert report["rejected_event_counts"]["risky_place_type"] == 3
    assert report["rejected_event_counts"]["low_confidence"] == 2
