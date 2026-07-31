import json
from pathlib import Path

from parser.canonical_schema import CanonicalInputRecord
from parser.dedupe import (
    DEDUPE_STRATEGY_AGGRESSIVE_V1,
    DEDUPE_STRATEGY_EXACT,
    DEDUPE_STRATEGY_MAXIMAL_V1,
    DEDUPE_STRATEGY_MAXIMAL_V2,
    DEDUPE_STRATEGY_MAXIMAL_V3,
    build_deduped_events,
    build_duplicate_candidates,
)
from scripts.build_canonical_ufo_dataset import apply_manual_review_decisions, build_canonical_dataset


def test_build_canonical_dataset_prunes_exact_subset_sources(tmp_path):
    source_dir = tmp_path / "sources"
    output_dir = tmp_path / "canonical"
    reports_dir = tmp_path / "reports"
    source_dir.mkdir()
    output_dir.mkdir()
    _write_text(output_dir / "canonical_input_events.jsonl", "stale legacy duplicate\n")

    _write_text(
        source_dir / "majestic.csv",
        "date,desc,key_vals/url,source,source_id,type/0,location/0,key_vals/Country,key_vals/LatLong,time\n"
        "5/21/1970,Many observers saw lights,,Hatch,Hatch_1,sighting,Pasture,Israel,\"31.766668 35.233335\",~18:00\n",
    )
    _write_text(
        source_dir / "mufonpy.csv",
        "No,Date Submitted,Date/Time of Event,Short Description,Location of Event,Long Description,Attachments\n"
        "2,,\"1992-08-19\\n5:45AM\",101992C FB1 MN Dark Cylinder,\"Newscandia\\, MN\\, US\",Witness saw a silent dark cylinder hovering above the farm.,\n",
    )
    _write_text(
        source_dir / "nuforcpy.csv",
        "No,Occurred,Location,Location details,Shape,Duration,Reported,Posted,Explanation,Characteristics,Color,Description,note\n"
        "111,1992-08-19 05:50 Local,\"Newscandia, MN, USA\",,Cylinder,5 min,1992-08-20,1999-11-02,,,Dark,A witness observed a dark cylindrical craft hover silently over the farm.,\n",
    )
    _write_text(
        source_dir / "phenomenAInon_UPDB.csv",
        "id,source,source_id,name,date,location,city,country,description\n"
        "5182466,3,2csohq,NICAP,1993-05-20 00:00:00,5193892,OTTAWA,CA,Airliner crew saw triangle\n",
    )
    _write_text(
        source_dir / "ufocat2023.csv",
        "PRN,YEAR,MO,DAY,TIME,LOCATION,REGION,STATE,COUNTY,LATITUDE,LONGITUDE,TYPE,SHAPE,DUR,NOTES,SOURCE,ISOURCE\n"
        "314310,1974,03,15,2200,COTTON COUNTY,US,OK,Cotton,34.35,98.32,3BR,Rectangl,5,A rectangular object,UFOReportCtr,\n",
    )
    _write_text(source_dir / "mufon.csv", "No\n2\n")
    _write_text(source_dir / "nuforc.csv", "No\n111\n")

    summary = build_canonical_dataset(
        source_dir=source_dir,
        output_dir=output_dir,
        reports_dir=reports_dir,
    )

    assert summary["source_record_count"] == 5
    assert summary["deduped_event_count"] == 5
    skipped = {(item["file"], item["reason"]) for item in summary["skipped_files"]}
    assert ("mufon.csv", "exact_subset_pruned") in skipped
    assert ("nuforc.csv", "exact_subset_pruned") in skipped

    source_records = _read_jsonl(output_dir / "source_records.jsonl")
    source_claims = _read_jsonl(output_dir / "source_claims.jsonl")
    assert {record["source_file"] for record in source_records} == {
        "majestic.csv",
        "mufonpy.csv",
        "nuforcpy.csv",
        "phenomenAInon_UPDB.csv",
        "ufocat2023.csv",
    }
    assert all(record["canonical_input_id"].startswith("cin_") for record in source_records)
    assert source_claims
    assert all(claim["source_claim_id"].startswith("scl_") for claim in source_claims)
    assert {"shape", "duration", "object_type"}.issubset({claim["claim_type"] for claim in source_claims})
    assert any(record["lat"] == 31.766668 and record["lon"] == 35.233335 for record in source_records)
    duplicate_candidates = _read_jsonl(output_dir / "duplicate_candidates.jsonl")
    manual_review_queue = _read_jsonl(output_dir / "manual_review_queue.jsonl")
    assert summary["duplicate_candidate_count"] == 1
    assert duplicate_candidates[0]["auto_merge"] is False
    assert duplicate_candidates[0]["merge_decision"] == "candidate_only"
    assert {"same_strong_date", "same_normalized_location", "similar_source_text"}.issubset(
        duplicate_candidates[0]["reasons"]
    )

    import_report = json.loads((reports_dir / "canonical_import_report.json").read_text(encoding="utf-8"))
    dedupe_report = json.loads((reports_dir / "dedupe_report.json").read_text(encoding="utf-8"))
    assert import_report["source_record_count"] == 5
    assert import_report["legacy_canonical_input_events_written"] is False
    assert import_report["source_claim_count"] == len(source_claims)
    assert import_report["normalized_event_count"] == 5
    assert import_report["map_event_count"] == 2
    assert import_report["manual_review_queue_count"] == len(manual_review_queue)
    assert any(item["review_type"] == "duplicate_candidate" for item in manual_review_queue)
    assert dedupe_report["duplicate_candidate_count"] == 1
    assert dedupe_report["duplicate_candidate_limit_reached"] is False
    assert dedupe_report["fuzzy_auto_merge_enabled"] is False
    assert dedupe_report["strategy"] == DEDUPE_STRATEGY_EXACT
    assert dedupe_report["auto_merge_policy"]["auto_merge_families"] == ["exact_canonical_fingerprint"]
    assert (output_dir / "normalized_events.json").exists()
    assert (output_dir / "map_events.json").exists()
    assert (output_dir / "manual_review_decision_schema.json").exists()
    assert not (output_dir / "canonical_input_events.jsonl").exists()


def test_ufocat_coordinate_signs_are_normalized_for_known_regions(tmp_path):
    source_dir = tmp_path / "sources"
    output_dir = tmp_path / "canonical"
    reports_dir = tmp_path / "reports"
    source_dir.mkdir()
    _write_minimum_retained_sources(source_dir)
    _write_text(
        source_dir / "ufocat2023.csv",
        "PRN,YEAR,MO,DAY,TIME,LOCATION,REGION,STATE,COUNTY,LATITUDE,LONGITUDE,TYPE,SHAPE,DUR,NOTES,SOURCE,ISOURCE\n"
        "100969,1954,05,01,1630,\"FLATBUSH, BROOKLYN\",US,NY,Kings,40.645,73.96,3L,Triangle,,Brooklyn row,UFOCAT,\n"
        "20783,1954,07,03,,\"WEST BERLIN, TEMPELHOF APT\",EU,GER,Berlin,52.47,-13.40,3L,Triangle,,Berlin row,UFOCAT,\n"
        "197154,1954,05,01,,\"HAVANA\",CA,CUB,Habana,23.12,82.42,3L,Triangle,,Cuba row,UFOCAT,\n"
        "187346,1954,05,01,,\"TAURANGA\",AU,NZL,Bay o Plenty,-37.70,-176.18,3L,Triangle,,New Zealand row,UFOCAT,\n"
        "195359,1954,05,01,,\"ADELAIDE\",AU,SAU,Adelaide,-34.93,-138.60,3L,Triangle,,South Australia row,UFOCAT,\n"
        "171782,1954,09,19,1630,\"PETERBOROUGH\",CN,ON,Peterborough,44.30,78.32,3L,Triangle,,Ontario row,UFOCAT,\n"
        "21558,1954,09,19,1630,\"AIEA\",P,HI,Honolulu,21.39,157.93,3L,Triangle,,Hawaii row,UFOCAT,\n"
        "200606,1954,05,01,,\"MADISON\",EU,WI,Dane,43.07,89.38,3L,Triangle,,Wisconsin row,UFOCAT,\n"
        "122004,1954,05,01,,\"DON MILLS\",CN,CN,Toronto,43.74,79.34,3L,Triangle,,Toronto row,UFOCAT,\n"
        "124888,1954,05,01,,\"BRIDGEND\",EU,GBR,So Glamorgan,51.52,3.35,3L,Triangle,,UK row,UFOCAT,\n"
        "124889,1954,05,01,,\"DUBLIN\",EU,IRL,Dublin,53.33,6.25,3L,Triangle,,Ireland row,UFOCAT,\n"
        "124890,1954,05,01,,\"FATIMA\",EU,POR,Santarem,39.62,8.65,3L,Triangle,,Portugal row,UFOCAT,\n"
        "124891,1954,05,01,,\"ROMA\",EU,ITA,Roma,41.88,-12.50,3L,Triangle,,Italy row,UFOCAT,\n"
        "124892,1954,05,01,,\"FUKUOKA\",AS,JPN,Fukuoka,40.27,-141.33,3L,Triangle,,Japan row,UFOCAT,\n"
        "124893,1954,05,01,,\"SHANGHAI\",AS,CHN,Shanghai,31.27,-121.42,3L,Triangle,,China row,UFOCAT,\n"
        "124894,1954,05,01,,\"ATHENS\",EU,GRE,Attica,37.98,-23.72,3L,Triangle,,Greece row,UFOCAT,\n",
    )

    build_canonical_dataset(source_dir=source_dir, output_dir=output_dir, reports_dir=reports_dir)

    ufocat_rows = [
        row for row in _read_jsonl(output_dir / "source_records.jsonl")
        if row["source_file"] == "ufocat2023.csv"
    ]

    assert ufocat_rows[0]["lat"] == 40.645
    assert ufocat_rows[0]["lon"] == -73.96
    assert ufocat_rows[1]["lat"] == 52.47
    assert ufocat_rows[1]["lon"] == 13.4
    assert ufocat_rows[2]["lat"] == 23.12
    assert ufocat_rows[2]["lon"] == -82.42
    assert ufocat_rows[3]["lat"] == -37.7
    assert ufocat_rows[3]["lon"] == -176.18
    assert ufocat_rows[4]["lat"] == -34.93
    assert ufocat_rows[4]["lon"] == 138.6
    assert ufocat_rows[5]["lat"] == 44.3
    assert ufocat_rows[5]["lon"] == -78.32
    assert ufocat_rows[6]["lat"] == 21.39
    assert ufocat_rows[6]["lon"] == -157.93
    assert ufocat_rows[7]["lat"] == 43.07
    assert ufocat_rows[7]["lon"] == -89.38
    assert ufocat_rows[8]["lat"] == 43.74
    assert ufocat_rows[8]["lon"] == -79.34
    assert ufocat_rows[9]["lat"] == 51.52
    assert ufocat_rows[9]["lon"] == -3.35
    assert ufocat_rows[10]["lat"] == 53.33
    assert ufocat_rows[10]["lon"] == -6.25
    assert ufocat_rows[11]["lat"] == 39.62
    assert ufocat_rows[11]["lon"] == -8.65
    assert ufocat_rows[12]["lat"] == 41.88
    assert ufocat_rows[12]["lon"] == 12.5
    assert ufocat_rows[13]["lat"] == 40.27
    assert ufocat_rows[13]["lon"] == 141.33
    assert ufocat_rows[14]["lat"] == 31.27
    assert ufocat_rows[14]["lon"] == 121.42
    assert ufocat_rows[15]["lat"] == 37.98
    assert ufocat_rows[15]["lon"] == 23.72


def test_audit_report_drives_exact_subset_pruning(tmp_path):
    source_dir = tmp_path / "sources"
    output_dir = tmp_path / "canonical"
    reports_dir = tmp_path / "reports"
    source_dir.mkdir()
    _write_text(
        source_dir / "nuforc.csv",
        "No,Occurred,Location,Location details,Shape,Duration,Reported,Posted,Explanation,Characteristics,Color,Description,note\n"
        "111,1995-02-02 23:00 Local,\"Shady Grove, OR, USA\",,Cone,15 min,1995-02-03,1999-11-02,,,Red,Subset row,\n",
    )
    _write_text(
        source_dir / "nuforcpy.csv",
        "No,Occurred,Location,Location details,Shape,Duration,Reported,Posted,Explanation,Characteristics,Color,Description,note\n"
        "111,1995-02-02 23:00 Local,\"Shady Grove, OR, USA\",,Cone,15 min,1995-02-03,1999-11-02,,,Red,Retained superset row,\n",
    )
    audit_report_path = tmp_path / "ufo_csv_audit.json"
    audit_report_path.write_text(
        json.dumps(
            {
                "recommended_keep_files_after_exact_subset_pruning": ["nuforcpy.csv"],
                "exact_overlap_pairs": [
                    {
                        "left": "nuforc.csv",
                        "right": "nuforcpy.csv",
                        "exact_overlap": 1,
                        "left_only": 0,
                        "right_only": 1,
                        "relationship": "left_subset_of_right",
                        "recommended_keep": "nuforcpy.csv",
                        "recommended_drop": "nuforc.csv",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    summary = build_canonical_dataset(
        source_dir=source_dir,
        output_dir=output_dir,
        reports_dir=reports_dir,
        audit_report_path=audit_report_path,
    )

    assert summary["source_file_plan"]["source"] == "ufo_csv_audit"
    assert summary["retained_source_files"] == ["nuforcpy.csv"]
    assert summary["source_record_count"] == 1
    skipped = [item for item in summary["skipped_files"] if item["file"] == "nuforc.csv"]
    assert skipped == [
        {
            "file": "nuforc.csv",
            "reason": "exact_subset_pruned",
            "retained_file": "nuforcpy.csv",
            "evidence_source": "ufo_csv_audit",
            "relationship": "left_subset_of_right",
            "exact_overlap": 1,
            "left_only": 0,
            "right_only": 1,
        }
    ]


def test_manual_review_decisions_are_recorded_without_mutating_canonical_outputs(tmp_path):
    source_dir = tmp_path / "sources"
    initial_output_dir = tmp_path / "initial" / "canonical"
    initial_reports_dir = tmp_path / "initial" / "reports"
    decided_output_dir = tmp_path / "decided" / "canonical"
    decided_reports_dir = tmp_path / "decided" / "reports"
    source_dir.mkdir()
    _write_text(
        source_dir / "nuforcpy.csv",
        "No,Occurred,Location,Location details,Shape,Duration,Reported,Posted,Explanation,Characteristics,Color,Description,note\n"
        "111,1992-08-19 05:50 Local,\"Newscandia, MN, USA\",,Cylinder,5 min,1992-08-20,1999-11-02,,,Dark,A witness observed a craft.,,overflow-one\n",
    )

    initial_summary = build_canonical_dataset(
        source_dir=source_dir,
        output_dir=initial_output_dir,
        reports_dir=initial_reports_dir,
    )
    initial_queue = _read_jsonl(initial_output_dir / "manual_review_queue.jsonl")
    review_item_id = next(
        item["review_item_id"]
        for item in initial_queue
        if item["review_type"] == "row_shape_anomaly"
    )

    decisions_path = tmp_path / "manual_review_decisions.jsonl"
    decisions_path.write_text(
        json.dumps(
            {
                "review_item_id": review_item_id,
                "decision": "repair_source_row",
                "reviewer": "analyst-a",
                "reviewed_at": "2026-05-21T12:00:00Z",
                "notes": "Overflow column should be repaired upstream.",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    decided_summary = build_canonical_dataset(
        source_dir=source_dir,
        output_dir=decided_output_dir,
        reports_dir=decided_reports_dir,
        manual_review_decisions_path=decisions_path,
    )

    decided_queue = _read_jsonl(decided_output_dir / "manual_review_queue.jsonl")
    reviewed_item = next(item for item in decided_queue if item["review_item_id"] == review_item_id)
    applied_decisions = _read_jsonl(decided_output_dir / "manual_review_applied_decisions.jsonl")
    decision_report = json.loads(
        (decided_reports_dir / "manual_review_decisions_report.json").read_text(encoding="utf-8")
    )

    assert initial_summary["deduped_event_count"] == decided_summary["deduped_event_count"]
    assert reviewed_item["status"] == "reviewed"
    assert reviewed_item["decision_effect"] == "record_only"
    assert reviewed_item["manual_decision"]["decision"] == "repair_source_row"
    assert reviewed_item["manual_decision"]["reviewer"] == "analyst-a"
    assert applied_decisions == [reviewed_item["manual_decision"]]
    assert decision_report["provided_decision_count"] == 1
    assert decision_report["applied_decision_count"] == 1
    assert decision_report["effect_policy"] == "record_only"
    assert decision_report["canonical_outputs_mutated"] is False
    assert decided_summary["manual_review_decisions"]["applied_decision_count"] == 1


def test_manual_review_decision_ingestion_reports_unknown_invalid_and_duplicate_decisions():
    queue = [
        {
            "review_item_id": "rev_known",
            "review_type": "duplicate_candidate",
            "status": "needs_review",
            "suggested_decisions": ["same_event", "distinct_events", "needs_more_evidence"],
        },
        {
            "review_item_id": "rev_other",
            "review_type": "row_shape_anomaly",
            "status": "needs_review",
            "suggested_decisions": ["accept_preserved_row", "repair_source_row", "exclude_source_row"],
        },
    ]
    decisions = [
        {"review_item_id": "rev_known", "decision": "same_event", "reviewer": "analyst-a"},
        {"review_item_id": "rev_known", "decision": "distinct_events", "reviewer": "analyst-b"},
        {"review_item_id": "rev_missing", "decision": "same_event"},
        {"review_item_id": "rev_other", "decision": "merge_anyway"},
        {"decision": "same_event"},
    ]

    updated_queue, applied_decisions, report = apply_manual_review_decisions(queue, decisions)

    assert updated_queue[0]["status"] == "reviewed"
    assert updated_queue[1]["status"] == "needs_review"
    assert updated_queue[0]["decision_effect"] == "record_only"
    assert applied_decisions[0]["decision"] == "same_event"
    assert report["provided_decision_count"] == 5
    assert report["applied_decision_count"] == 1
    assert report["unknown_review_item_ids"] == [
        {
            "decision_index": 3,
            "review_item_id": "rev_missing",
            "decision": "same_event",
        }
    ]
    assert {item["reason"] for item in report["invalid_decisions"]} == {
        "duplicate_decision_for_review_item",
        "decision_not_allowed_for_review_type",
        "missing_review_item_id",
    }


def test_canonical_ids_are_stable_for_same_source_rows(tmp_path):
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    _write_minimum_retained_sources(source_dir)

    first = build_canonical_dataset(
        source_dir=source_dir,
        output_dir=tmp_path / "first" / "canonical",
        reports_dir=tmp_path / "first" / "reports",
    )
    second = build_canonical_dataset(
        source_dir=source_dir,
        output_dir=tmp_path / "second" / "canonical",
        reports_dir=tmp_path / "second" / "reports",
    )

    assert first["source_record_count"] == second["source_record_count"]
    first_records = _read_jsonl(tmp_path / "first" / "canonical" / "source_records.jsonl")
    second_records = _read_jsonl(tmp_path / "second" / "canonical" / "source_records.jsonl")
    assert [record["canonical_input_id"] for record in first_records] == [
        record["canonical_input_id"] for record in second_records
    ]


def test_source_records_preserve_complete_raw_rows_and_shape_anomalies(tmp_path):
    source_dir = tmp_path / "sources"
    output_dir = tmp_path / "canonical"
    reports_dir = tmp_path / "reports"
    source_dir.mkdir()
    _write_text(
        source_dir / "nuforcpy.csv",
        "No,Occurred,Location,Location details,Shape,Duration,Reported,Posted,Explanation,Characteristics,Color,Description,note\n"
        "111,1992-08-19 05:50 Local,\"Newscandia, MN, USA\",,Cylinder,5 min,1992-08-20,1999-11-02,,,Dark,A witness observed a craft.,,overflow-one,overflow-two\n"
        "222\n",
    )

    summary = build_canonical_dataset(
        source_dir=source_dir,
        output_dir=output_dir,
        reports_dir=reports_dir,
    )

    assert summary["source_record_count"] == 2
    records = _read_jsonl(output_dir / "source_records.jsonl")
    overflow_record = records[0]
    missing_record = records[1]
    assert overflow_record["raw_source_row"]["Location details"] == ""
    assert overflow_record["raw_source_extra_columns"] == ["overflow-one", "overflow-two"]
    assert overflow_record["source_row_anomalies"] == ["extra_columns"]
    assert "__extra_columns" not in overflow_record["raw_fields"]
    assert missing_record["raw_source_missing_columns"]
    assert "missing_columns" in missing_record["source_row_anomalies"]
    assert missing_record["source_row_column_count"] == 1
    column_accounting = json.loads((reports_dir / "canonical_column_accounting.json").read_text(encoding="utf-8"))
    manual_review_queue = _read_jsonl(output_dir / "manual_review_queue.jsonl")
    assert column_accounting["summary"]["row_shape_anomaly_count"] == 2
    assert column_accounting["sources"]["nuforcpy.csv"]["row_shape_anomaly_counts"] == {
        "extra_columns": 1,
        "missing_columns": 1,
    }
    assert sum(1 for item in manual_review_queue if item["review_type"] == "row_shape_anomaly") == 2


def test_source_column_mapping_emits_raw_source_claims(tmp_path):
    source_dir = tmp_path / "sources"
    output_dir = tmp_path / "canonical"
    reports_dir = tmp_path / "reports"
    source_dir.mkdir()
    _write_text(
        source_dir / "nuforcpy.csv",
        "No,Occurred,Location,Location details,Shape,Duration,Reported,Posted,Explanation,Characteristics,Color,Description,note\n"
        "111,1995-02-02 23:00 Local,\"Shady Grove, OR, USA\",,Cone,15 min,1995-02-03,1999-11-02,,,Blue-white,A blue-white cone crossed the sky.,case-note\n",
    )
    mapping_path = tmp_path / "source_column_mapping.json"
    mapping_path.write_text(
        json.dumps(
            {
                "sources": {
                    "nuforcpy.csv": {
                        "Shape": {
                            "mapping_action": "source_claim",
                            "suspected_semantic_role": "object_shape_claim",
                            "inferred_type": "text",
                        },
                        "Color": {
                            "mapping_action": "source_claim",
                            "suspected_semantic_role": "color_light_claim",
                            "inferred_type": "text",
                        },
                        "Description": {
                            "mapping_action": "canonical",
                            "suspected_semantic_role": "description",
                            "inferred_type": "long_text",
                        },
                        "note": {
                            "mapping_action": "source_specific",
                            "suspected_semantic_role": "source_specific",
                            "inferred_type": "long_text",
                        },
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    summary = build_canonical_dataset(
        source_dir=source_dir,
        output_dir=output_dir,
        reports_dir=reports_dir,
        source_column_mapping_path=mapping_path,
    )

    source_claims = _read_jsonl(output_dir / "source_claims.jsonl")
    mapped_claims = [claim for claim in source_claims if claim["origin"] == "source_column_mapping"]
    assert summary["source_claims"]["origin_counts"]["source_column_mapping"] == 2
    assert {claim["source_field"] for claim in mapped_claims} == {"Shape", "Color"}
    assert any(
        claim["claim_type"] == "color_light"
        and claim["raw_value"] == "Blue-white"
        and claim["normalized_value"] == "blue_white"
        and claim["mapping_role"] == "color_light_claim"
        for claim in mapped_claims
    )
    assert any(
        claim["claim_type"] == "object_shape"
        and claim["raw_value"] == "Cone"
        and claim["normalized_value"] == "cone"
        for claim in mapped_claims
    )
    import_report = json.loads((reports_dir / "canonical_import_report.json").read_text(encoding="utf-8"))
    column_accounting = json.loads((reports_dir / "canonical_column_accounting.json").read_text(encoding="utf-8"))
    import_failures = json.loads((reports_dir / "canonical_import_failures.json").read_text(encoding="utf-8"))
    assert import_report["source_column_mapping_path"] == str(mapping_path.resolve())
    assert import_report["source_claim_count"] == len(source_claims)
    assert import_report["column_accounting"]["source_specific_non_empty_value_count"] == 1
    assert import_report["import_failures"]["count"] == 0
    assert import_failures == []
    assert column_accounting["sources"]["nuforcpy.csv"]["source_specific_columns"] == ["note"]
    assert column_accounting["sources"]["nuforcpy.csv"]["source_specific_non_empty_value_count"] == 1
    assert column_accounting["sources"]["nuforcpy.csv"]["source_claim_non_empty_value_count"] == 2


def test_ufocat_zero_day_falls_back_to_month_precision(tmp_path):
    source_dir = tmp_path / "sources"
    output_dir = tmp_path / "canonical"
    reports_dir = tmp_path / "reports"
    source_dir.mkdir()
    _write_text(
        source_dir / "ufocat2023.csv",
        "PRN,YEAR,MO,DAY,TIME,LOCATION,REGION,STATE,COUNTY,LATITUDE,LONGITUDE,TYPE,SHAPE,DUR,NOTES,SOURCE,ISOURCE\n"
        "290383,2018,04,0,2200,SAN ANTONIO,US,TX,Bexar,29.42,98.49,3BR,Light,5,Day unknown in source,UFOReportCtr,\n",
    )

    summary = build_canonical_dataset(
        source_dir=source_dir,
        output_dir=output_dir,
        reports_dir=reports_dir,
    )

    records = _read_jsonl(output_dir / "source_records.jsonl")
    assert summary["source_record_count"] == 1
    assert summary["import_failures"]["count"] == 0
    assert records[0]["date_raw"] == "4/2018"
    assert records[0]["date_precision"] == "month"
    assert records[0]["date_iso"] == "2018-04-01"
    assert records[0]["end_date_iso"] == "2018-04-30"


def test_ufocat_blank_region_state_does_not_abort_import(tmp_path):
    source_dir = tmp_path / "sources"
    output_dir = tmp_path / "canonical"
    reports_dir = tmp_path / "reports"
    source_dir.mkdir()
    _write_text(
        source_dir / "ufocat2023.csv",
        "PRN,YEAR,MO,DAY,TIME,LOCATION,REGION,STATE,COUNTY,LATITUDE,LONGITUDE,TYPE,SHAPE,DUR,NOTES,SOURCE,ISOURCE\n"
        "400001,1954,09,24,2100,HOBBS,,,Lea,32.7026,103.1360,3L,Light,,Blank admin cells,UFOCAT,\n",
    )

    summary = build_canonical_dataset(
        source_dir=source_dir,
        output_dir=output_dir,
        reports_dir=reports_dir,
    )

    records = _read_jsonl(output_dir / "source_records.jsonl")
    assert summary["source_record_count"] == 1
    assert summary["import_failures"]["count"] == 0
    assert records[0]["location_raw"] == "HOBBS, Lea"
    assert records[0]["lat"] == 32.7026
    assert records[0]["lon"] == 103.136


def test_exact_duplicate_grouping_preserves_provenance():
    first = CanonicalInputRecord(
        canonical_input_id="cin_a",
        source_name="alpha",
        source_file="alpha.csv",
        source_row_number=2,
        source_native_id="1",
        source_row_hash="hash_a",
        date_raw="1/2/2000",
        date_iso="2000-01-02",
        time_raw="21:00",
        location_raw="Phoenix, AZ, US",
        description="Bright triangle hovered silently.",
    )
    second = CanonicalInputRecord(
        canonical_input_id="cin_b",
        source_name="beta",
        source_file="beta.csv",
        source_row_number=9,
        source_native_id="B-1",
        source_row_hash="hash_b",
        date_raw="2000-01-02",
        date_iso="2000-01-02",
        time_raw="21:00",
        location_raw="Phoenix, AZ, US",
        description="Bright triangle hovered silently.",
    )

    deduped_events, duplicate_groups = build_deduped_events([first, second])

    assert len(deduped_events) == 1
    assert len(duplicate_groups) == 1
    assert deduped_events[0]["duplicate_record_count"] == 2
    assert {item["source_file"] for item in deduped_events[0]["source_provenance"]} == {
        "alpha.csv",
        "beta.csv",
    }


def test_near_miss_records_are_not_auto_merged():
    first = CanonicalInputRecord(
        canonical_input_id="cin_a",
        source_name="alpha",
        source_file="alpha.csv",
        source_row_number=2,
        source_native_id="1",
        source_row_hash="hash_a",
        date_iso="2000-01-02",
        time_raw="21:00",
        location_raw="Phoenix, AZ, US",
        description="Bright triangle hovered silently.",
    )
    second = CanonicalInputRecord(
        canonical_input_id="cin_b",
        source_name="beta",
        source_file="beta.csv",
        source_row_number=9,
        source_native_id="B-1",
        source_row_hash="hash_b",
        date_iso="2000-01-02",
        time_raw="21:00",
        location_raw="Phoenix, AZ, US",
        description="Bright oval hovered silently.",
    )

    deduped_events, duplicate_groups = build_deduped_events([first, second])

    assert len(deduped_events) == 2
    assert duplicate_groups == []


def test_aggressive_v1_merges_same_source_exact_day_location_rows_with_type_disagreement():
    first = _canonical_record(
        canonical_input_id="cin_hobbs_a",
        source_name="ufocat",
        source_file="ufocat2023.csv",
        source_row_number=10,
        source_native_id="171782",
        source_row_hash="hash_hobbs_a",
        date_iso="1954-09-24",
        sort_date_iso="1954-09-24",
        date_precision="exact_day",
        location_raw="HOBBS, Lea, NM, US",
        type_raw="Light",
        description="First sparse source row.",
    )
    second = _canonical_record(
        canonical_input_id="cin_hobbs_b",
        source_name="ufocat",
        source_file="ufocat2023.csv",
        source_row_number=11,
        source_native_id="171783",
        source_row_hash="hash_hobbs_b",
        date_iso="1954-09-24",
        sort_date_iso="1954-09-24",
        date_precision="exact_day",
        location_raw="HOBBS, Lea, NM, US",
        type_raw="Crescent",
        description="Second sparse source row from the same incident.",
    )

    exact_events, exact_groups = build_deduped_events([first, second], strategy=DEDUPE_STRATEGY_EXACT)
    aggressive_events, aggressive_groups = build_deduped_events(
        [first, second],
        strategy=DEDUPE_STRATEGY_AGGRESSIVE_V1,
    )

    assert len(exact_events) == 2
    assert exact_groups == []
    assert len(aggressive_events) == 1
    assert len(aggressive_groups) == 1
    assert aggressive_events[0]["duplicate_record_count"] == 2
    assert aggressive_events[0]["dedupe_strategy"] == "aggressive_v1_auto_merge"
    assert "same_source_strong_date_location" in aggressive_events[0]["dedupe_evidence_families"]


def test_aggressive_v1_does_not_merge_same_source_location_type_without_exact_day():
    first = _canonical_record(
        canonical_input_id="cin_month_a",
        source_name="ufocat",
        source_file="ufocat2023.csv",
        source_row_number=10,
        source_native_id="171782",
        source_row_hash="hash_month_a",
        date_iso="1954-09-01",
        sort_date_iso="1954-09-01",
        date_precision="month",
        location_raw="HOBBS, Lea, NM, US",
        type_raw="Light",
    )
    second = _canonical_record(
        canonical_input_id="cin_month_b",
        source_name="ufocat",
        source_file="ufocat2023.csv",
        source_row_number=11,
        source_native_id="171783",
        source_row_hash="hash_month_b",
        date_iso="1954-09-01",
        sort_date_iso="1954-09-01",
        date_precision="month",
        location_raw="HOBBS, Lea, NM, US",
        type_raw="Light",
    )

    deduped_events, duplicate_groups = build_deduped_events(
        [first, second],
        strategy=DEDUPE_STRATEGY_AGGRESSIVE_V1,
    )

    assert len(deduped_events) == 2
    assert duplicate_groups == []


def test_maximal_v1_merges_cross_source_exact_day_location_type_rows():
    first = _canonical_record(
        canonical_input_id="cin_cross_a",
        source_name="ufocat",
        source_file="ufocat2023.csv",
        source_row_number=10,
        source_native_id="171782",
        source_row_hash="hash_cross_a",
        date_iso="1954-09-24",
        sort_date_iso="1954-09-24",
        date_precision="exact_day",
        location_raw="HOBBS, Lea, NM, US",
        type_raw="Light",
    )
    second = _canonical_record(
        canonical_input_id="cin_cross_b",
        source_name="nuforc",
        source_file="nuforcpy.csv",
        source_row_number=11,
        source_native_id="case-b",
        source_row_hash="hash_cross_b",
        date_iso="1954-09-24",
        sort_date_iso="1954-09-24",
        date_precision="exact_day",
        location_raw="HOBBS, Lea, NM, US",
        type_raw="Light",
    )

    aggressive_events, aggressive_groups = build_deduped_events(
        [first, second],
        strategy=DEDUPE_STRATEGY_AGGRESSIVE_V1,
    )
    maximal_events, maximal_groups = build_deduped_events(
        [first, second],
        strategy=DEDUPE_STRATEGY_MAXIMAL_V1,
    )

    assert len(aggressive_events) == 2
    assert aggressive_groups == []
    assert len(maximal_events) == 1
    assert len(maximal_groups) == 1
    assert maximal_events[0]["dedupe_strategy"] == "maximal_v1_auto_merge"
    assert "strong_date_location_type" in maximal_events[0]["dedupe_evidence_families"]


def test_maximal_v2_merges_cross_source_county_and_no_county_location_variants():
    first = _canonical_record(
        canonical_input_id="cin_structured_a",
        source_name="ufocat",
        source_file="ufocat2023.csv",
        source_row_number=10,
        source_native_id="171782",
        source_row_hash="hash_structured_a",
        date_iso="1954-09-24",
        sort_date_iso="1954-09-24",
        date_precision="exact_day",
        location_raw="HOBBS, Lea, NM, US",
        city="HOBBS",
        state_province="NM",
        country="US",
        type_raw="Light",
    )
    second = _canonical_record(
        canonical_input_id="cin_structured_b",
        source_name="phenomenainon_updb",
        source_file="phenomenAInon_UPDB.csv",
        source_row_number=11,
        source_native_id="case-b",
        source_row_hash="hash_structured_b",
        date_iso="1954-09-24",
        sort_date_iso="1954-09-24",
        date_precision="exact_day",
        location_raw="HOBBS, NM, US",
        city="HOBBS",
        state_province="NM",
        country="US",
        type_raw="Light",
    )

    maximal_v1_events, maximal_v1_groups = build_deduped_events(
        [first, second],
        strategy=DEDUPE_STRATEGY_MAXIMAL_V1,
    )
    maximal_v2_events, maximal_v2_groups = build_deduped_events(
        [first, second],
        strategy=DEDUPE_STRATEGY_MAXIMAL_V2,
    )

    assert len(maximal_v1_events) == 2
    assert maximal_v1_groups == []
    assert len(maximal_v2_events) == 1
    assert len(maximal_v2_groups) == 1
    assert maximal_v2_events[0]["dedupe_strategy"] == "maximal_v2_auto_merge"
    assert "strong_date_structured_city_state_country" in maximal_v2_events[0]["dedupe_evidence_families"]


def test_maximal_v2_does_not_merge_city_country_only_without_specific_type():
    first = _canonical_record(
        canonical_input_id="cin_city_country_a",
        source_name="ufocat",
        source_file="ufocat2023.csv",
        source_row_number=10,
        source_native_id="171782",
        source_row_hash="hash_city_country_a",
        date_iso="1954-09-24",
        sort_date_iso="1954-09-24",
        date_precision="exact_day",
        location_raw="SPRINGFIELD, Greene County, US",
        city="SPRINGFIELD",
        country="US",
        type_raw="Unknown",
    )
    second = _canonical_record(
        canonical_input_id="cin_city_country_b",
        source_name="nuforc",
        source_file="nuforcpy.csv",
        source_row_number=11,
        source_native_id="case-b",
        source_row_hash="hash_city_country_b",
        date_iso="1954-09-24",
        sort_date_iso="1954-09-24",
        date_precision="exact_day",
        location_raw="SPRINGFIELD, Hampden County, US",
        city="SPRINGFIELD",
        country="US",
        type_raw="Unknown",
    )

    deduped_events, duplicate_groups = build_deduped_events(
        [first, second],
        strategy=DEDUPE_STRATEGY_MAXIMAL_V2,
    )

    assert len(deduped_events) == 2
    assert duplicate_groups == []


def test_maximal_v3_merges_state_present_and_state_missing_exact_day_city_country_rows():
    state_present = _canonical_record(
        canonical_input_id="cin_hobbs_state",
        source_name="ufocat",
        source_file="ufocat2023.csv",
        source_row_number=10,
        date_raw="1954-09-24",
        date_iso="1954-09-24",
        sort_date_iso="1954-09-24",
        date_precision="day",
        location_raw="HOBBS, Lea, NM, US",
        city="HOBBS",
        state_province="NM",
        country="US",
        type_raw="Light",
    )
    state_missing = _canonical_record(
        canonical_input_id="cin_hobbs_no_state",
        source_name="nuforc",
        source_file="nuforcpy.csv",
        source_row_number=11,
        date_raw="1954-09-24",
        date_iso="1954-09-24",
        sort_date_iso="1954-09-24",
        date_precision="day",
        location_raw="Hobbs, US",
        city="Hobbs",
        state_province=None,
        country="USA",
        type_raw="Unknown",
    )

    maximal_v2_events, maximal_v2_groups = build_deduped_events(
        [state_present, state_missing],
        strategy=DEDUPE_STRATEGY_MAXIMAL_V2,
    )
    maximal_v3_events, maximal_v3_groups = build_deduped_events(
        [state_present, state_missing],
        strategy=DEDUPE_STRATEGY_MAXIMAL_V3,
    )

    assert len(maximal_v2_events) == 2
    assert maximal_v2_groups == []
    assert len(maximal_v3_events) == 1
    assert len(maximal_v3_groups) == 1
    assert maximal_v3_events[0]["dedupe_strategy"] == "maximal_v3_auto_merge"
    assert (
        "strong_date_structured_city_country_no_state_conflict"
        in maximal_v3_events[0]["dedupe_evidence_families"]
    )


def test_maximal_v3_does_not_merge_city_country_rows_when_known_states_conflict():
    illinois = _canonical_record(
        canonical_input_id="cin_springfield_il",
        source_name="ufocat",
        source_file="ufocat2023.csv",
        source_row_number=10,
        date_raw="1954-09-24",
        date_iso="1954-09-24",
        sort_date_iso="1954-09-24",
        date_precision="day",
        location_raw="SPRINGFIELD, IL, US",
        city="SPRINGFIELD",
        state_province="IL",
        country="US",
        type_raw="Light",
    )
    missouri = _canonical_record(
        canonical_input_id="cin_springfield_mo",
        source_name="nuforc",
        source_file="nuforcpy.csv",
        source_row_number=11,
        date_raw="1954-09-24",
        date_iso="1954-09-24",
        sort_date_iso="1954-09-24",
        date_precision="day",
        location_raw="SPRINGFIELD, MO, US",
        city="SPRINGFIELD",
        state_province="MO",
        country="USA",
        type_raw="Light",
    )
    state_missing = _canonical_record(
        canonical_input_id="cin_springfield_no_state",
        source_name="phenomenainon_updb",
        source_file="phenomenAInon_UPDB.csv",
        source_row_number=12,
        date_raw="1954-09-24",
        date_iso="1954-09-24",
        sort_date_iso="1954-09-24",
        date_precision="day",
        location_raw="Springfield, US",
        city="Springfield",
        state_province=None,
        country="US",
        type_raw="Light",
    )

    deduped_events, duplicate_groups = build_deduped_events(
        [illinois, missouri, state_missing],
        strategy=DEDUPE_STRATEGY_MAXIMAL_V3,
    )

    assert len(deduped_events) == 3
    assert duplicate_groups == []


def test_obvious_fuzzy_duplicate_candidate_is_queued_without_auto_merge():
    first = _canonical_record(
        canonical_input_id="cin_a",
        source_name="alpha",
        source_file="alpha.csv",
        source_row_number=2,
        source_native_id="1",
        source_row_hash="hash_a",
        date_iso="2000-01-02",
        sort_date_iso="2000-01-02",
        date_precision="exact_day",
        location_raw="Phoenix, AZ, US",
        description="Bright triangle hovered silently over downtown.",
    )
    second = _canonical_record(
        canonical_input_id="cin_b",
        source_name="beta",
        source_file="beta.csv",
        source_row_number=9,
        source_native_id="B-1",
        source_row_hash="hash_b",
        date_iso="2000-01-02",
        sort_date_iso="2000-01-02",
        date_precision="exact_day",
        location_raw="Phoenix, Arizona, USA",
        description="A silent bright triangular craft was hovering above downtown.",
    )

    deduped_events, duplicate_groups = build_deduped_events([first, second])
    candidates = build_duplicate_candidates([first, second])

    assert len(deduped_events) == 2
    assert duplicate_groups == []
    assert len(candidates) == 1
    assert candidates[0]["auto_merge"] is False
    assert candidates[0]["score"] >= 0.82
    assert candidates[0]["canonical_input_ids"] == ["cin_a", "cin_b"]
    assert {"same_strong_date", "same_normalized_location", "similar_source_text"}.issubset(
        candidates[0]["reasons"]
    )


def test_near_noncandidate_is_not_queued_on_date_and_location_alone():
    first = _canonical_record(
        canonical_input_id="cin_a",
        source_name="alpha",
        source_file="alpha.csv",
        source_row_number=2,
        source_native_id="1",
        source_row_hash="hash_a",
        date_iso="2000-01-02",
        sort_date_iso="2000-01-02",
        date_precision="exact_day",
        location_raw="Phoenix, AZ, US",
        description="Bright triangle hovered silently over downtown.",
    )
    second = _canonical_record(
        canonical_input_id="cin_b",
        source_name="beta",
        source_file="beta.csv",
        source_row_number=9,
        source_native_id="B-1",
        source_row_hash="hash_b",
        date_iso="2000-01-02",
        sort_date_iso="2000-01-02",
        date_precision="exact_day",
        location_raw="Phoenix, Arizona, USA",
        description="Airport officials launched a weather balloon for a festival.",
    )

    assert build_duplicate_candidates([first, second]) == []


def test_weak_date_records_are_not_queued_even_with_matching_text():
    first = _canonical_record(
        canonical_input_id="cin_a",
        source_name="alpha",
        source_file="alpha.csv",
        source_row_number=2,
        source_native_id="1",
        source_row_hash="hash_a",
        date_iso="1947-07-01",
        end_date_iso="1947-07-31",
        sort_date_iso="1947-07-16",
        date_precision="month",
        location_raw="Roswell, NM, US",
        description="Bright disc hovered above the ranch.",
    )
    second = _canonical_record(
        canonical_input_id="cin_b",
        source_name="beta",
        source_file="beta.csv",
        source_row_number=9,
        source_native_id="B-1",
        source_row_hash="hash_b",
        date_iso="1947-07-01",
        end_date_iso="1947-07-31",
        sort_date_iso="1947-07-16",
        date_precision="month",
        location_raw="Roswell, New Mexico, USA",
        description="A bright disc was hovering above the ranch.",
    )

    assert build_duplicate_candidates([first, second]) == []


def _canonical_record(**overrides) -> CanonicalInputRecord:
    data = {
        "canonical_input_id": "cin_default",
        "source_name": "test",
        "source_file": "test.csv",
        "source_row_number": 1,
        "source_native_id": None,
        "source_row_hash": "hash_default",
    }
    data.update(overrides)
    return CanonicalInputRecord(**data)


def _write_minimum_retained_sources(source_dir: Path) -> None:
    _write_text(
        source_dir / "majestic.csv",
        "date,desc,key_vals/url,source,source_id,type/0,location/0,key_vals/Country,key_vals/LatLong,time\n"
        "5/21/1970,Many observers saw lights,,Hatch,Hatch_1,sighting,Pasture,Israel,\"31.766668 35.233335\",~18:00\n",
    )
    _write_text(
        source_dir / "mufonpy.csv",
        "No,Date Submitted,Date/Time of Event,Short Description,Location of Event,Long Description,Attachments\n"
        "2,,\"1992-08-19\\n5:45AM\",101992C FB1 MN Dark Cyl,\"Newscandia\\, MN\\, US\",Witness narrative,\n",
    )
    _write_text(
        source_dir / "nuforcpy.csv",
        "No,Occurred,Location,Location details,Shape,Duration,Reported,Posted,Explanation,Characteristics,Color,Description,note\n"
        "111,1995-02-02 23:00 Local,\"Shady Grove, OR, USA\",,Cone,15 min,1995-02-03,1999-11-02,,,Red,NUFORC UFO Sighting 111,\n",
    )
    _write_text(
        source_dir / "phenomenAInon_UPDB.csv",
        "id,source,source_id,name,date,location,city,country,description\n"
        "5182466,3,2csohq,NICAP,1993-05-20 00:00:00,5193892,OTTAWA,CA,Airliner crew saw triangle\n",
    )
    _write_text(
        source_dir / "ufocat2023.csv",
        "PRN,YEAR,MO,DAY,TIME,LOCATION,REGION,STATE,COUNTY,LATITUDE,LONGITUDE,TYPE,SHAPE,DUR,NOTES,SOURCE,ISOURCE\n"
        "314310,1974,03,15,2200,COTTON COUNTY,US,OK,Cotton,34.35,98.32,3BR,Rectangl,5,A rectangular object,UFOReportCtr,\n",
    )


def _write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="")


def _read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
