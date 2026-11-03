import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.recover_mapping_locations import (
    compound_area_candidate, parse_location, query_id, references, run,
    scan_geonames,
)


def authority_inputs(tmp_path):
    country = tmp_path / "countries.txt"
    country.write_text("US\tUSA\t840\tUS\tUnited States\nGB\tGBR\t826\tUK\tUnited Kingdom\nAU\tAUS\t036\tAS\tAustralia\n", encoding="utf8")
    admin = tmp_path / "admin.txt"
    admin.write_text("US.HI\tHawaii\tHawaii\t5855797\nUS.WA\tWashington\tWashington\t5815135\nUS.NM\tNew Mexico\tNew Mexico\t5481136\nGB.ENG\tEngland\tEngland\t6269131\nAU.02\tNew South Wales\tNew South Wales\t2155400\n", encoding="utf8")
    return country, admin


def gazetteer_row(identity, name, lat, lon, country, admin, aliases="", feature="PPL", population=1):
    return "\t".join(map(str, [identity,name,name,aliases,lat,lon,"A" if feature in ("PCLI","PCLD","ADM1") else "P",feature,country,"",admin,"","","",population,"","","UTC","2026-01-01"]))


def archive(tmp_path, rows):
    path = tmp_path / "gazetteer.zip"
    with zipfile.ZipFile(path, "w") as sink:
        sink.writestr("allCountries.txt", "\n".join(rows) + "\n")
    return path


def prepare_queries(parsed):
    queries = {}
    parsed["queryRefs"] = []
    for query in parsed.pop("queries"):
        identity = query_id(query)
        queries[identity] = {"queryId":identity, **{k:v for k,v in query.items() if k != "scope"}}
        parsed["queryRefs"].append({"queryId":identity,"scope":query["scope"],"locality":query["locality"]})
    return queries


def test_repeated_country_city_and_admin_qualifiers_are_reversible(tmp_path):
    countries, admins = references(*authority_inputs(tmp_path))
    parsed = parse_location("Birmingham (UK/Birmingham), United Kingdom", countries, admins)
    assert parsed["queries"][0]["locality"] == "Birmingham"
    assert parsed["country"] == "GB"
    assert parsed["qualifier"] == "UK/Birmingham"
    assert not parsed["holds"]
    assert "qualified_label_resolved:repeated_country+repeated_city" in parsed["steps"]
    assert parsed["original"] == "Birmingham (UK/Birmingham), United Kingdom"
    australia = parse_location("Lennox Head (Australia), Australia", countries, admins)
    assert australia["queries"][0]["locality"] == "Lennox Head"
    assert australia["admin1"] is None
    assert "state_or_province_missing_requires_source_review" in australia["holds"]
    scoped = parse_location("Lennox Head (NSW), Australia", countries, admins)
    assert scoped["admin1"] == "02"
    assert not scoped["holds"]


def test_conflicting_or_unknown_qualifiers_are_not_discarded(tmp_path):
    countries, admins = references(*authority_inputs(tmp_path))
    conflict = parse_location("Birmingham (Australia), United Kingdom", countries, admins)
    assert conflict["queries"] == []
    assert "conflicting_qualifier_country:Australia" in conflict["holds"]
    unknown = parse_location("Birmingham (from an aircraft), United Kingdom", countries, admins)
    assert unknown["queries"][0]["locality"] == "Birmingham"
    assert "unresolved_parenthetical_role:from an aircraft" in unknown["holds"]
    wrong_admin = parse_location("Everett (New Mexico), WA, US", countries, admins)
    assert wrong_admin["queries"] == []
    assert "conflicting_explicit_admins" in wrong_admin["holds"]


def test_homonym_alternate_prevents_population_winner_and_wrong_admin_excluded(tmp_path):
    countries, admins = references(*authority_inputs(tmp_path))
    parsed = parse_location("Everett, WA, US", countries, admins)
    queries = prepare_queries(parsed)
    path = archive(tmp_path, [
        gazetteer_row(1,"Everett",47.98,-122.2,"US","WA",population=100000),
        gazetteer_row(2,"Different primary",45.5,-120.1,"US","WA",aliases="Everett",population=3),
        gazetteer_row(3,"Everett",34,-106,"US","NM"),
    ])
    scan = scan_geonames(path,queries)
    query = next(iter(queries.values()))
    assert scan["gazetteerRecordPasses"] == 1
    assert query["candidateIds"] == ["1","2"]
    assert query["screen"] == "ambiguous_separate_localities"
    assert query["accepted"] is False
    assert query["features"][1]["nameMatches"][0]["kind"] == "alternate"


def test_compound_area_is_bounded_explicit_and_never_a_precise_point(tmp_path):
    countries, admins = references(*authority_inputs(tmp_path))
    parsed = parse_location("Keaau-Pahoa, HI, US", countries, admins)
    queries = prepare_queries(parsed)
    path = archive(tmp_path, [
        gazetteer_row(1,"Keaau",19.623,-155.04,"US","HI"),
        gazetteer_row(2,"Pahoa",19.497,-154.945,"US","HI"),
    ])
    scan_geonames(path, queries)
    result = compound_area_candidate(parsed, queries)
    assert result["accepted"] is False
    assert result["needsFullSourceReview"] is True
    assert result["locationPrecision"] == "approximate"
    assert result["country"] == "US" and result["admin1"] == "HI"
    assert result["radiusKm"] > result["anchorDiameterKm"] / 2
    assert {item["geonameIds"][0] for item in result["componentEvidence"]} == {"1","2"}
    assert "not an administrative boundary" in result["uncertaintyStatement"]
    assert compound_area_candidate(parsed,queries,maximum_diameter_km=1) is None
    parsed["holds"].append("route_area_facility_or_observer_role_requires_review")
    assert compound_area_candidate(parsed,queries) is None


def test_literal_hyphenated_town_is_not_reinterpreted_as_between_places(tmp_path):
    countries, admins = references(*authority_inputs(tmp_path))
    parsed = parse_location("Keaau-Pahoa, HI, US", countries, admins)
    queries = prepare_queries(parsed)
    path = archive(tmp_path,[gazetteer_row(1,"Keaau",19.623,-155.04,"US","HI"),
                             gazetteer_row(2,"Pahoa",19.497,-154.945,"US","HI"),
                             gazetteer_row(3,"Keaau-Pahoa",19.55,-155,"US","HI")])
    scan_geonames(path,queries)
    assert compound_area_candidate(parsed,queries) is None


def test_full_screen_retains_every_rejection_prior_hold_and_independent_authority(tmp_path):
    countries, admins = authority_inputs(tmp_path)
    source = tmp_path / "unmapped.jsonl.gz"
    rows = [{"event_id":1,"source":"nuforc","location_raw":"Birmingham (UK/Birmingham), United Kingdom","has_coordinates":False,"chunk_id":"chunk_1","detail_index":4},
            {"event_id":2,"source":"majestic","location_raw":"","has_coordinates":False,"chunk_id":"chunk_2","detail_index":7},
            {"event_id":3,"source":"mufon","location_raw":"Lennox Head (Australia), Australia","has_coordinates":False}]
    with gzip.open(source,"wt",encoding="utf8") as handle:
        for row in rows:
            handle.write(json.dumps(row)+"\n")
    previous = tmp_path / "previous.json"
    previous.write_text(json.dumps({"rejections":[{"event_id":1,"reason":"manual_narrative_location_conflict"}]}))
    geo = archive(tmp_path,[gazetteer_row(1,"Birmingham",52.48,-1.9,"GB","ENG"),
                           gazetteer_row(2,"Lennox Head",-28.8,153.59,"AU","02"),
                           gazetteer_row(3,"United Kingdom",54,-2,"GB","",feature="PCLI"),
                           gazetteer_row(4,"New South Wales",-32,147,"AU","02",feature="ADM1")])
    output = tmp_path / "evidence"
    receipt = run(source,output,geo,countries,admins,previous_review=previous)
    with gzip.open(output/"record-review.jsonl.gz","rt",encoding="utf8") as handle:
        evidence = [json.loads(line) for line in handle]
    assert len(evidence) == len(rows)
    assert all(not row["accepted"] and row["needsFullSourceReview"] for row in evidence)
    assert evidence[0]["previousReview"]["sourceHold"] == "manual_narrative_location_conflict"
    assert evidence[0]["reviewLane"] == "prior_source_hold_requires_new_evidence"
    assert evidence[1]["parsedLocation"]["holds"] == ["missing_location_text"]
    assert evidence[2]["reviewLane"] == "missing_admin_context_review"
    assert receipt["acceptedDecisions"] == 0
    assert receipt["mappedCopiesUsedAsEvidence"] is False
    with gzip.open(output/"area-authorities.jsonl.gz","rt",encoding="utf8") as handle:
        areas = [json.loads(line) for line in handle]
    assert {row["featureCode"] for row in areas} == {"PCLI","ADM1"}
    assert all(row["sourceLineSha256"] and row["authorityUrl"] for row in areas)
    with unittest.TestCase().assertRaisesRegex(ValueError,"overwrite"):
        run(source,output,geo,countries,admins)


def test_mapped_inputs_are_not_reused_as_geographic_evidence(tmp_path):
    countries, admins = authority_inputs(tmp_path)
    source = tmp_path/"mapped.jsonl"
    source.write_text(json.dumps({"event_id":1,"has_coordinates":True,"location_raw":"Everett, WA, USA"})+"\n")
    with unittest.TestCase().assertRaisesRegex(ValueError,"unresolved rows only"):
        run(source,tmp_path/"evidence",tmp_path/"not-read.zip",countries,admins)


def load_tests(loader, standard_tests, pattern):
    suite = unittest.TestSuite()
    for name, function in list(globals().items()):
        if name.startswith("test_") and callable(function):
            def execute(check=function):
                with tempfile.TemporaryDirectory(prefix="mapping-recovery-test-") as folder:
                    check(Path(folder))
            suite.addTest(unittest.FunctionTestCase(execute, description=name))
    return suite


if __name__ == "__main__":
    unittest.main()
