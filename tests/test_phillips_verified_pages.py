"""Reviewed source-page links, legacy display upgrades and ownership boundaries."""
import copy
import json
from pathlib import Path

from parser.ufocat_references import CATALOG_URL, reference_entries, references

FIXTURES = json.loads((Path(__file__).parent / "fixtures/ufocat_references.json").read_text(encoding="utf-8"))
PDF_SHA256 = "e824270528264c2563df17f79540171dc216fb9be85968a5eb844ecb1b2be17b"
TITLE = "Ted Phillips - Physical Traces Associated with UFO Sightings (CUFOS, 1975) [TPhillips1]"


def test_only_reviewed_direct_cases_have_fixed_source_pages():
    for fixture in FIXTURES:
        if "verifiedPages" not in fixture:
            continue
        event = copy.deepcopy(fixture["event"])
        before = copy.deepcopy(event)
        entry = next(x for x in reference_entries(event) if x.get("sourceCode"))
        pages = fixture["verifiedPages"]
        if pages:
            assert (entry["catalogPrintedPage"], entry["catalogPdfPage"]) == tuple(pages)
            assert entry["catalogPdfSha256"] == PDF_SHA256
            assert entry["url"] == f"{CATALOG_URL}#page={pages[1]}"
            assert f"printed p. {pages[0]}" in entry["text"]
            assert f"PDF page {pages[1]}" in entry["text"]
        else:
            assert "catalogPrintedPage" not in entry
            assert "catalogPdfPage" not in entry
            assert "catalogPdfSha256" not in entry
            assert entry["url"] == CATALOG_URL
            assert entry["locatorType"] == "ambiguous_catalog_case_number_or_printed_page"
        assert event == before
    for code, role in [("TPhillips", "direct"), ("TPhillips2", "direct"), ("TPhillips3", "direct"), ("TPhillips1", "indirect")]:
        for case in (253, 537, 585):
            raw = {"SOURCE": code, "PAGEVOL": str(case)} if role == "direct" else {"ISOURCE": code, "IPAGEVOL": str(case)}
            entry = reference_entries({"source": "ufocat", "raw_fields": raw})[0]
            assert "catalogPdfPage" not in entry
            assert "#page=" not in entry.get("url", "")
    unreviewed = reference_entries({"source": "ufocat", "raw_fields": {"SOURCE": "TPhillips1", "PAGEVOL": "494"}})[0]
    assert "catalogPdfPage" not in unreviewed
    assert unreviewed["url"] == CATALOG_URL


def test_exact_legacy_helper_references_upgrade_without_duplicates():
    for case in (253, 537, 585):
        event = {"source": "ufocat", "date_iso": "1972-09-14", "time_raw": "2000", "lat": 37.3, "lon": -91.9,
                 "raw_fields": {"SOURCE": "TPhillips1", "PAGEVOL": str(case)}}
        new_entry = reference_entries(event)[0]
        legacy = f"{TITLE}, case {case} (direct citation)"
        arbitrary = legacy + " - researcher note"
        for originals in ([legacy], [legacy, new_entry["text"]], [new_entry["text"], legacy],
                          ["Original source", legacy, arbitrary, legacy]):
            current = dict(event, references=originals)
            before = copy.deepcopy(current)
            entries = reference_entries(current)
            assert [x for x in entries if x.get("sourceCode")] == [new_entry]
            assert legacy not in references(current)
            assert sum(x["text"] == new_entry["text"] for x in entries) == 1
            for original in originals:
                if original not in (legacy, new_entry["text"]):
                    assert original in references(current)
            assert current == before
            assert reference_entries(dict(current, references=references(current))) == entries
        # Existing text alone does not establish raw citation ownership.
        plain = reference_entries({"source": "majestic", "references": [legacy],
                                   "raw_fields": {"SOURCE": "TPhillips1", "PAGEVOL": str(case)}})
        assert plain == [{"text": legacy, "citationRole": "existing"}]
