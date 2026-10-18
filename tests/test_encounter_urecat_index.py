"""Source identity and uncertainty gates for private URECAT index candidates."""
import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/encounter_urecat_index.py"
spec = importlib.util.spec_from_file_location("encounter_urecat_index", SCRIPT)
urecat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(urecat)


def fixture(*rows):
    body = "<tr><th>Date:</th><th>Place:</th><th>Names:</th></tr>"
    for when, href, place, name in rows:
        body += f'<tr><td>{when}</td><td><a href="{href}">{place}</a></td><td>{name}</td></tr>\n'
    return ("<meta charset='utf-8'><table>" + body + "</table>").encode("utf-8")


class UrecatIndexGuards(unittest.TestCase):
    def test_ambiguous_and_incomplete_dates_never_become_exact(self):
        for raw, precision in [
            ("May 21?, 2008", "approximate"), ("October 13 or 14, 2017", "range"),
            ("July 1990 ou 1992", "range"), ("Summer 1987", "season"),
            ("About 1990", "approximate"), ("August 2009", "month"),
            ("1989", "year"), ("February 30, 1954", "invalid"),
            ("1000 BC", "historical"), ("unknown", "unknown"),
            ("Before May 6, 1909", "bounded"), ("The 1960's", "decade"),
            ("July 27,30,31, 1978", "range"), ("Beg. May 1939", "approximate"),
        ]:
            with self.subTest(raw=raw):
                result = urecat.parse_date(raw)
                self.assertIsNone(result["dateIso"])
                self.assertEqual(result["datePrecision"], precision)

    def test_exact_dates_validate_calendar_and_languages(self):
        for raw in ["February 29, 2000", "29 février 2000", "2000-02-29"]:
            self.assertEqual(urecat.parse_date(raw), {"dateIso": "2000-02-29", "datePrecision": "day"})
        self.assertIsNone(urecat.parse_date("February 29, 1900")["dateIso"])

    def test_filename_does_not_override_visible_date(self):
        result = urecat.parse_index(fixture(("October 13 or 14, 2017", "2017-09-13-argentina-parquemitre.htm", "Corrientes", "")))
        self.assertIsNone(result["records"][0]["dateIso"])
        self.assertEqual(result["records"][0]["dateRaw"], "October 13 or 14, 2017")

    def test_duplicates_and_supported_bilingual_aliases_retain_all_rows(self):
        result = urecat.parse_index(fixture(
            ("4 October 1954", "1954-10-04-france-megrit.htm#summary", "M&eacute;grit, France", "URECAT-000304"),
            ("4 October 1954", "https://www.ufology.patrickgross.org/ce3/1954-10-04-france-megrit.htm", "Mégrit, France", "URECAT-000304"),
            ("4 octobre 1954", "1954-10-04-france-megritf.htm", "Mégrit, France", "URECAT-000304"),
        ))
        self.assertEqual(result["counts"]["candidateRecords"], 1)
        self.assertEqual(result["counts"]["duplicateUrlRowReferences"], 1)
        self.assertEqual(result["counts"]["bilingualAliasGroups"], 1)
        record = result["records"][0]
        self.assertEqual(len(record["rowReferences"]), 3)
        self.assertEqual(record["sourceCaseIds"], ["URECAT-000304"])
        self.assertEqual(record["dateIso"], "1954-10-04")
        self.assertFalse(record["acceptedForRuntime"])

    def test_real_place_ending_in_f_is_not_automatically_language_alias(self):
        result = urecat.parse_index(fixture(
            ("July 28, 1998", "1998-07-28-algeria-tindouf.htm", "Tindouf", ""),
            ("July 29, 1998", "1998-07-28-algeria-tindou.htm", "Tindou", ""),
        ))
        self.assertEqual(result["counts"]["candidateRecords"], 2)

    def test_same_url_date_conflict_is_held_and_not_two_events(self):
        result = urecat.parse_index(fixture(
            ("May 20, 1953", "1953-05-20-usa-brushcreek.htm", "Brush Creek", ""),
            ("May 21, 1953", "1953-05-20-usa-brushcreek.htm", "Brush Creek", ""),
        ))
        record = result["records"][0]
        self.assertEqual(result["counts"]["candidateRecords"], 1)
        self.assertIsNone(record["dateIso"])
        self.assertEqual(record["datePrecision"], "conflicting")
        self.assertIn("index_date_conflict", record["reviewFlags"])

    def test_year_only_case_link_is_retained_as_unreviewed(self):
        result = urecat.parse_index(fixture(
            ("Summer 1978", "1978.htm", "Somewhere", "Someone"),
            ("The 1960's", "1960s-denmark-aalborg.htm", "Aalborg", "A man"),
        ))
        self.assertEqual(result["counts"]["candidateRecords"], 2)
        held = next(r for r in result["records"] if r["sourceUrl"].endswith("/1978.htm"))
        self.assertIn("year_only_link_target_unreviewed", held["reviewFlags"])

    def test_language_alias_does_not_hide_multi_episode_date_conflict(self):
        result = urecat.parse_index(fixture(
            ("April 29, 1955", "1939-06-usa-california.htm", "California, USA", "Dana Howard"),
            ("June 1939", "1939-06-usa-californiaf.htm", "California, USA", "Dana Howard"),
        ))
        self.assertEqual(result["counts"]["candidateRecords"], 1)
        record = result["records"][0]
        self.assertIsNone(record["dateIso"])
        self.assertIn("bilingual_alias_unreviewed", record["reviewFlags"])
        self.assertEqual(len(record["rowReferences"]), 2)

    def test_index_navigation_and_external_links_are_not_cases(self):
        result = urecat.parse_index(fixture(
            ("1954", "_1954.htm", "1954 index", ""),
            ("1954", "https://example.com/ce3/1954-10-04-test.htm", "External", ""),
            ("1954", "1954-france-example.htm", "Real candidate", ""),
        ))
        self.assertEqual(result["counts"]["candidateRecords"], 1)
        self.assertEqual(result["records"][0]["sourceCaseIds"], [])

    def test_output_and_source_pin_are_deterministic(self):
        data = fixture(("July 22, 2018", "2018-07-22-usa-queensbury.htm", "Queensbury", "An anonymous couple"))
        self.assertEqual(urecat.parse_index(data), urecat.parse_index(data))
        self.assertEqual(urecat.parse_index(data)["sourcePin"]["bytes"], len(data))
        self.assertEqual(urecat.parse_index(data)["counts"]["runtimePromotions"], 0)


if __name__ == "__main__":
    unittest.main()
