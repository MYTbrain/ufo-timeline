from scripts.summarize_admin_region_mapping_candidates import summarize_admin_region_mapping_candidates


def test_admin_region_candidates_accept_explicit_state_and_province_only(tmp_path):
    mapping_csv = tmp_path / "coverage.csv"
    mapping_csv.write_text(
        "query,count,bucket,source_count,cached_geocode_count,sample_location_raw\n"
        '"ca, us",10,city_region_like,2,0,"CA, US"\n'
        '"on, ca",7,city_region_like,1,0,"ON, CA"\n'
        '"ca",5,city_state_like,3,0,"CA"\n'
        '"springfield, us",4,city_region_like,1,0,"SPRINGFIELD, US"\n'
        '"gb",3,city_state_like,1,0,"GB"\n',
        encoding="utf-8",
    )

    report = summarize_admin_region_mapping_candidates(mapping_csv=mapping_csv)

    assert report["canonical_outputs_mutated"] is False
    assert report["geocoding_performed"] is False
    assert report["candidate_query_count"] == 2
    assert report["candidate_event_count"] == 17
    assert report["candidates"][0]["query"] == "ca, us"
    assert report["candidates"][0]["location_precision"] == "state"
    assert report["candidates"][1]["query"] == "on, ca"
    assert report["candidates"][1]["location_precision"] == "province"
    assert report["rejected_event_counts"]["not_explicit_admin_region"] == 12


def test_admin_region_candidates_accept_placeholder_city_admin_region_rows(tmp_path):
    mapping_csv = tmp_path / "coverage.csv"
    mapping_csv.write_text(
        "query,count,bucket,source_count,cached_geocode_count,sample_location_raw\n"
        '"0, pa, us",10,city_state_country_like,1,0,"0, PA, US"\n'
        '"unknown, on, ca",7,vague_or_unspecified,1,0,"Unknown, ON, CA"\n'
        '"springfield, il, us",4,city_state_country_like,1,0,"SPRINGFIELD, IL, US"\n',
        encoding="utf-8",
    )

    report = summarize_admin_region_mapping_candidates(mapping_csv=mapping_csv)

    assert report["candidate_query_count"] == 2
    assert report["candidate_event_count"] == 17
    assert [candidate["query"] for candidate in report["candidates"]] == ["0, pa, us", "unknown, on, ca"]
    assert report["candidates"][0]["location_precision"] == "state"
    assert report["candidates"][1]["location_precision"] == "province"
    assert report["rejected_event_counts"]["not_explicit_admin_region"] == 4
