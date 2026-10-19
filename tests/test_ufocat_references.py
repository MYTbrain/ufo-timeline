"""Citation provenance and exporter regression checks; no corpus build required."""
import copy
import json
from pathlib import Path

from parser.canonical_export import canonical_event_to_normalized_event
from parser.ufocat_references import CATALOG_URL, FAMILY_ID, reference_entries, references

FIXTURES = json.loads((Path(__file__).parent / "fixtures/ufocat_references.json").read_text(encoding="utf-8"))


def test_source_code_ownership_and_existing_references():
    for fixture in FIXTURES:
        event = copy.deepcopy(fixture["event"])
        before = copy.deepcopy(event)
        entries = reference_entries(event)
        assert [entry["sourceCode"] for entry in entries if "sourceCode" in entry] == fixture["expectedCodes"], fixture["name"]
        assert references(event) == [entry["text"] for entry in entries]
        assert event == before
    assert references(FIXTURES[8]["event"])[0] == "Original source"
    assert len(reference_entries(FIXTURES[8]["event"])) == 2


def test_direct_and_indirect_catalog_locators_are_distinct():
    direct = reference_entries(FIXTURES[0]["event"])[0]
    indirect = reference_entries(FIXTURES[1]["event"])[1]
    assert direct["catalogCaseNumber"] == 293
    assert direct["locatorType"] == "catalog_case_number"
    assert "case 293" in direct["text"]
    assert "page 293" not in direct["text"]
    assert indirect["catalogCaseNumber"] is None
    assert indirect["locatorRaw"] == "079"
    assert indirect["locatorType"] == "ambiguous_catalog_case_number_or_printed_page"
    assert direct["familyId"] == indirect["familyId"] == FAMILY_ID
    assert direct["url"] == indirect["url"] == CATALOG_URL
    invalid = reference_entries(FIXTURES[7]["event"])
    assert invalid[0]["catalogCaseNumber"] is None
    assert invalid[0]["flags"] == ["missing_or_invalid_catalog_case_number"]
    assert "unverified locator 999" in invalid[0]["text"]
    assert invalid[1]["catalogCaseNumber"] is None


def test_export_preserves_original_references_and_core_data():
    source = {"source_name":"ufocat", "source_file":"ufocat2023.csv", "source_native_id":"53369",
        "canonical_input_id":"cin_phillips_fixture", "source_row_number":19, "source_row_hash":"pinned",
        "date_iso":"1967-09-07", "date_precision":"exact_day", "lat":37.47, "lon":-105.87,
        "coordinate_source":"source_coordinates", "raw_fields":{"SOURCE":"TPhillips1", "PAGEVOL":"293"},
        "source_url":"TPhillips1", "references":["Original primary citation"]}
    before = copy.deepcopy(source)
    event = canonical_event_to_normalized_event(source)
    assert source == before
    assert event["references"][0] == "Original primary citation"
    assert "case 293" in event["references"][1]
    assert event["date_iso"] == source["date_iso"]
    assert (event["lat"], event["lon"]) == (source["lat"], source["lon"])
    assert event["canonical_input_ids"] == [source["canonical_input_id"]]
    assert event["extra_data"]["canonical"]["raw_fields"] == source["raw_fields"]
    assert event["links"] == [], "A code is not a source URL; helper supplies the verified catalog link separately"


def test_no_phillips_promotion_from_author_or_missing_source_identity():
    for event in [None, {}, {"raw_fields":{"SOURCE":"TPhillips1", "PAGEVOL":"494"}},
                  {"source":"nuforc","raw_fields":{"AUTHOR":"Ted Phillips", "SOURCE":"TPhillips1"}}]:
        assert reference_entries(event) == []


def test_reexported_reference_recovers_typed_metadata_without_duplication():
    event = copy.deepcopy(FIXTURES[0]["event"])
    expected = reference_entries(event)
    event["references"] = references(event)
    assert reference_entries(event) == expected
