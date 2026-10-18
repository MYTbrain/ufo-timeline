"""Conservative source-date and identity rules for untrusted transcription."""
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location("rosales_candidates", Path(__file__).resolve().parents[1] / "scripts/encounter_rosales_candidates.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class RosalesCandidateTests(unittest.TestCase):
    def test_qualified_dates_never_become_exact(self):
        for text in ("September 16 1994?", "about September 16 1994", "Summer 1994", "September 16-17 1994", "1994 or 1995", "2357-2258 BC", "February 29 1993"):
            self.assertIsNone(M.date_fields(text)["dateIso"], text)
        self.assertEqual(M.date_fields("September 16 1994")["dateIso"], "1994-09-16")
        self.assertEqual(M.date_fields("16 September 1994")["dateIso"], "1994-09-16")
        self.assertEqual(M.date_fields("1994")["dateIso"], "1994")
        self.assertEqual(M.date_fields("September 1994")["dateIso"], "1994-09")

    def test_restarted_numbers_and_hc_collisions_keep_distinct_held_rows(self):
        base = dict(entry_number="1", year_page="1993", location="Birmingham, UK", date="1993", time="unknown", description="first", hc_number="2748", source="ref", type_code="G", strangeness_index="", reliability="", comments="")
        other = {**base, "location": "Malaysia", "date": "1995", "description": "second"}
        result = M.normalize([base, other], csv_sha="a" * 64, archives={})
        self.assertEqual(len({r["sourceEntryId"] for r in result["records"]}), 2)
        self.assertEqual(result["counts"]["acceptedIdentityLinks"], 0)
        self.assertEqual(result["counts"]["nonuniqueHcGroups"], 1)
        self.assertTrue(all("nonunique_hc_key_requires_independent_identity" in r["qualityFlags"] for r in result["records"]))
        self.assertTrue(all("abduction" not in r for r in result["records"]))

    def test_addendum_is_not_an_id_and_page_year_is_not_occurrence_date(self):
        base = dict(entry_number="1", year_page="1993", location="unknown", date="", time="", description="", hc_number="addendum", source="", type_code="", strangeness_index="", reliability="", comments="")
        row = M.normalize([base], csv_sha="b" * 64, archives={})["records"][0]
        self.assertEqual(row["sourceCaseIds"], [])
        self.assertIsNone(row["dateIso"])


if __name__ == "__main__":
    unittest.main()
