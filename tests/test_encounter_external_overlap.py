"""Semantic guards for external encounter discovery, not identity acceptance."""
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("external_overlap", Path(__file__).resolve().parents[1] / "scripts/encounter_external_overlap.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ExternalOverlapTests(unittest.TestCase):
    def test_year_and_month_are_intervals_not_midpoints(self):
        year = MODULE.date_interval({"dateIso": "1993-07-01", "datePrecision": "year"})
        day = MODULE.date_interval({"dateIso": "1993-01-02", "datePrecision": "exact_day"})
        month = MODULE.date_interval({"dateIso": "1993-02-15", "datePrecision": "month"})
        self.assertLess(year[0], day[0])
        self.assertGreater(year[1], month[1])
        self.assertEqual(month[1] - month[0], 27)
        self.assertIsNone(MODULE.date_interval({"dateIso": "1993-07-01", "datePrecision": "unknown"}))

    def test_bce_and_invalid_ranges_do_not_become_modern_dates(self):
        self.assertIsNone(MODULE.date_interval({"dateRaw": "2357 BC", "dateIso": "2357-01-01", "datePrecision": "year"}))
        self.assertIsNone(MODULE.date_interval({"dateIso": "1993-02-29", "datePrecision": "exact_day"}))
        self.assertIsNone(MODULE.date_interval({"dateIso": "1993-03-02", "dateEndIso": "1993-03-01", "datePrecision": "date_range"}))

    def test_locality_requires_phrase_boundary_and_excludes_country_only(self):
        self.assertTrue(MODULE.location_matches({"locationRaw": "Near Mégrit, France"}, {"location_raw": "MEGRIT, Bretagne, FR"}))
        self.assertFalse(MODULE.location_matches({"locationRaw": "Eagle, USA"}, {"location_raw": "EAGLETON, TX, US"}))
        self.assertFalse(MODULE.location_matches({"locationRaw": "France"}, {"location_raw": "France"}))

    def test_native_rosales_website_ids_are_not_book_page_numbers(self):
        web = {"source": "ufocat", "raw_fields": {"SOURCE": "ARosales01", "PAGEVOL": " 2803", "URN": "160500", "PRN": "124097"}}
        book = {"source": "ufocat", "raw_fields": {"SOURCE": "ARosales14", "PAGEVOL": "287"}}
        self.assertIn(("rosales_hc", "", "2803"), MODULE.normalized_ids(MODULE.native_ids(web)))
        self.assertNotIn(("rosales_hc", "", "287"), MODULE.normalized_ids(MODULE.native_ids(book)))
        self.assertNotIn(("ufocat_urn", "", "124097"), MODULE.normalized_ids(MODULE.native_ids(web)))
        secondary = {"source": "ufocat", "raw_fields": {"SOURCE": "FSR", "PAGEVOL": "2803", "ISOURCE": "ARosales01", "IPAGEVOL": "3654"}}
        secondary_keys = MODULE.normalized_ids(MODULE.native_ids(secondary))
        self.assertIn(("rosales_hc", "", "3654"), secondary_keys)
        self.assertNotIn(("rosales_hc", "", "2803"), secondary_keys)

    def test_full_native_scan_retains_conflicting_dates_and_pins(self):
        candidate = {"sourceEntryId": "ext:hc2803", "dateIso": "1994-05-20", "datePrecision": "exact_day", "locationRaw": "Northford, Connecticut", "sourceCaseIds": [{"scheme": "rosales_hc", "value": "2803"}]}
        collision = {"sourceEntryId": "ext:hc2803:other-edition", "dateIso": "1995-09-12", "datePrecision": "exact_day", "locationRaw": "Othercity, Spain", "sourceCaseIds": [{"scheme": "rosales_hc", "value": "2803"}]}
        row = {"event_id": 123, "source": "ufocat", "source_id": "124097", "date_iso": "1995-09-12", "date_raw": "9/12/1995", "date_precision": "exact_day", "location_raw": "NORTHFORD, New Haven, CT, US", "raw_fields": {"SOURCE": "ARosales01", "PAGEVOL": "2803"}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data/canonical_web/event_chunks/chunk_000000.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps([row]))
            result = MODULE.overlap([candidate, collision], [], {"123"}, shared=directory, native_citations_all=True)
        link = result["entries"][0]["nativeCitationLinks"][0]
        self.assertEqual(link["dateAgreement"], "conflict")
        self.assertEqual(link["locationAgreement"], "explicit_locality_phrase")
        self.assertEqual(link["status"], "held_native_citation_review")
        self.assertEqual(result["counts"]["acceptedIdentityLinks"], 0)
        self.assertEqual(len(result["detailPins"]), 1)
        self.assertEqual(result["counts"]["entriesWithNativeCitationCandidates"], 2)
        self.assertEqual(result["counts"]["uniqueNativeCitationReports"], 1)
        collision_link = result["entries"][1]["nativeCitationLinks"][0]
        self.assertEqual(collision_link["dateAgreement"], "overlap")
        self.assertEqual(collision_link["locationAgreement"], "not_established")
        self.assertEqual(collision_link["status"], "held_native_citation_review")

    def test_held_candidates_include_reports_outside_existing_encounter_index(self):
        candidates = [{"sourceEntryId": "ext:one", "sourceUrl": "https://example.org/1", "dateIso": "1993-05-20", "datePrecision": "exact_day", "locationRaw": "Torphins, Scotland"},
                      {"sourceEntryId": "ext:two", "dateIso": "1993-05-20", "datePrecision": "exact_day", "locationRaw": "Otherplace"}]
        rows = [{"event_id": 1, "source": "ufocat", "chunk_id": "chunk_000000", "detail_index": 0, "sort_date_iso": "1993-05-20", "date_raw": "5/20/1993", "date_precision": "exact_day", "location_raw": "TORPHINS, SCT, EU"},
                {"event_id": 2, "source": "majestic", "chunk_id": "chunk_000000", "detail_index": 1, "sort_date_iso": "1993-05-20", "date_precision": "exact_day", "location_raw": "TORPHINS, Aberdeenshire"}]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "summary.json.gz"
            raw = gzip.compress(json.dumps(rows).encode())
            path.write_bytes(raw)
            shard = {"key": "test/summary_shards/summary_000000.json.gz", "source": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            result = MODULE.overlap(candidates, [shard], {"1"}, expected_count=2)
        counts = result["counts"]
        self.assertEqual(counts["acceptedIdentityLinks"], 0)
        self.assertEqual(counts["entriesWithExistingEncounterCandidates"], 1)
        self.assertEqual(counts["entriesWithOutsideEncounterIndexCandidates"], 1)
        self.assertEqual(counts["entriesWithoutSummaryCandidate"], 1)
        self.assertEqual(counts["ambiguousEntries"], 1)
        self.assertTrue(all(r["status"] == "held_discovery_only" for r in result["entries"]))


if __name__ == "__main__":
    unittest.main()
