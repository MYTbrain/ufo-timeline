from pathlib import Path

from scripts.apply_mapping_enrichment_preview import apply_mapping_enrichment_preview


def test_mapping_enrichment_preview_applies_high_medium_only(tmp_path):
    input_path = tmp_path / "events.jsonl"
    input_path.write_text(
        "\n".join(
            [
                '{"canonical_event_id":"evt1","source_name":"mufon","lat":null,"lon":null,"location_raw":"Seattle, WA, USA","coordinate_source":"unresolved","location_precision":"unknown"}',
                '{"canonical_event_id":"evt2","source_name":"mufon","lat":null,"lon":null,"location_raw":"Springfield, US","coordinate_source":"unresolved","location_precision":"unknown"}',
                '{"canonical_event_id":"evt3","source_name":"ufocat","lat":1.0,"lon":2.0,"location_raw":"Seattle, WA, USA","coordinate_source":"raw_latlong"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    candidates_path = tmp_path / "candidates.csv"
    candidates_path.write_text(
        "query,count,confidence,candidate_count,name,lat,lon,country_code,admin1,population,timezone\n"
        '"seattle, wa, usa",2,high,1,Seattle,47.60621,-122.33207,US,WA,780995,America/Los_Angeles\n'
        '"springfield, us",5,low,92,Springfield,37.21533,-93.29824,US,MO,170188,America/Chicago\n',
        encoding="utf-8",
    )

    report = apply_mapping_enrichment_preview(
        input_path=input_path,
        candidates_path=candidates_path,
        output_dir=tmp_path / "out",
        report_output=tmp_path / "report.json",
    )

    output_rows = (tmp_path / "out" / "deduped_events.jsonl").read_text(encoding="utf-8").splitlines()

    assert report["canonical_outputs_mutated"] is False
    assert report["input_event_count"] == 3
    assert report["mapped_before_count"] == 1
    assert report["enriched_event_count"] == 1
    assert report["projected_mapped_after_count"] == 2
    assert '"coordinate_source":"geocoded"' in output_rows[0]
    assert '"mapping_enrichment_confidence":"high"' in output_rows[0]
    assert '"coordinate_source":"unresolved"' in output_rows[1]
    assert '"coordinate_source":"raw_latlong"' in output_rows[2]


def test_mapping_enrichment_preview_accepts_numeric_cached_confidence(tmp_path):
    input_path = tmp_path / "events.jsonl"
    input_path.write_text(
        '{"canonical_event_id":"evt1","source_name":"nuforc","lat":null,"lon":null,"location_raw":"Rome, Italy","coordinate_source":"unresolved","location_precision":"unknown"}\n',
        encoding="utf-8",
    )
    candidates_path = tmp_path / "candidates.csv"
    candidates_path.write_text(
        "query,count,bucket,confidence,lat,lon,display_name,addresstype,category,osm_type,provider_id\n"
        '"rome, italy",5,city_region_like,0.88,41.8933,12.4829,"Rome, Italy",city,boundary,relation,nominatim:test\n',
        encoding="utf-8",
    )

    report = apply_mapping_enrichment_preview(
        input_path=input_path,
        candidates_path=candidates_path,
        output_dir=tmp_path / "out",
        report_output=tmp_path / "report.json",
    )

    output_text = (tmp_path / "out" / "deduped_events.jsonl").read_text(encoding="utf-8")

    assert report["enriched_event_count"] == 1
    assert '"mapping_enrichment_source":"cached_geocode"' in output_text
    assert '"mapping_enrichment_confidence":"high"' in output_text
    assert '"geocode_confidence":0.88' in output_text


def test_mapping_enrichment_preview_preserves_candidate_location_precision(tmp_path):
    input_path = tmp_path / "events.jsonl"
    input_path.write_text(
        '{"canonical_event_id":"evt1","source_name":"mufon","lat":null,"lon":null,"location_raw":"CA, US","coordinate_source":"unresolved","location_precision":"unknown"}\n',
        encoding="utf-8",
    )
    candidates_path = tmp_path / "candidates.csv"
    candidates_path.write_text(
        "query,count,confidence,candidate_count,name,lat,lon,country_code,admin1,population,timezone,location_precision\n"
        '"ca, us",10,medium,1,"California, US",36.116203,-119.681564,US,CA,0,America/Los_Angeles,state\n',
        encoding="utf-8",
    )

    report = apply_mapping_enrichment_preview(
        input_path=input_path,
        candidates_path=candidates_path,
        output_dir=tmp_path / "out",
        report_output=tmp_path / "report.json",
    )

    output_text = (tmp_path / "out" / "deduped_events.jsonl").read_text(encoding="utf-8")

    assert report["enriched_event_count"] == 1
    assert '"location_precision":"state"' in output_text


def test_mapping_enrichment_preview_can_apply_event_specific_candidates(tmp_path):
    input_path = tmp_path / "events.jsonl"
    input_path.write_text(
        "\n".join(
            [
                '{"canonical_event_id":"evt1","source_name":"nuforc","lat":null,"lon":null,"location_raw":"Columbus, US","coordinate_source":"unresolved","location_precision":"unknown"}',
                '{"canonical_event_id":"evt2","source_name":"nuforc","lat":null,"lon":null,"location_raw":"Columbus, US","coordinate_source":"unresolved","location_precision":"unknown"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    candidates_path = tmp_path / "candidates.csv"
    candidates_path.write_text(
        "canonical_event_id,query,confidence,candidate_count,name,lat,lon,country_code,admin1,population,timezone,location_precision\n"
        '"evt1","columbus, us",high,1,Columbus,39.96118,-82.99879,US,OH,913175,America/New_York,city\n',
        encoding="utf-8",
    )

    report = apply_mapping_enrichment_preview(
        input_path=input_path,
        candidates_path=candidates_path,
        output_dir=tmp_path / "out",
        report_output=tmp_path / "report.json",
    )

    output_rows = (tmp_path / "out" / "deduped_events.jsonl").read_text(encoding="utf-8").splitlines()

    assert report["enriched_event_count"] == 1
    assert '"mapping_enrichment_source":"body_text_city_state"' in output_rows[0]
    assert '"lat":39.96118' in output_rows[0]
    assert '"coordinate_source":"unresolved"' in output_rows[1]
