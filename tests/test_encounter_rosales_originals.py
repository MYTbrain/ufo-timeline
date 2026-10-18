import hashlib
import importlib.util
from pathlib import Path
import unittest
import tempfile
from unittest.mock import Mock, patch

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "encounter_rosales_originals.py"
spec = importlib.util.spec_from_file_location("rosales_originals", MODULE_PATH)
parser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parser)


def parse(body):
    payload = body.encode("utf-8")
    return parser.extract_rows(payload, {
        "sourceId": "fixture", "url": "https://example.test/humanoid1993.shtml",
        "sha256": hashlib.sha256(payload).hexdigest(), "path": "fixture.html"})


class OriginalParserTests(unittest.TestCase):
    def test_preserves_compound_and_uncertain_classification(self):
        rows, audit = parse("<p>1.<br>Location. Example<br>Date: January 12 1993<br>Time: evening<br>Reported account.</p><p>HC addition # 3870<br>Source: A source<br>Type: E? Or F</p><p>Total Cases: 1</p>")
        row = rows[0]
        self.assertEqual(row["sourceClassificationRaw"], "E? Or F")
        self.assertEqual(row["sourceClassificationCodes"], ["E", "F"])
        self.assertIn("uncertain_source_classification", row["reviewFlags"])
        self.assertEqual(row["dateIso"], "1993-01-12")
        self.assertEqual(row["sourceCaseIds"], [{"scheme": "rosales_hc", "value": "3870"}])
        self.assertEqual(row["narrativeSha256"], parser.sha("Reported account."))
        self.assertNotIn("narrativePrivate", row)
        self.assertEqual(audit["declaredTotals"], [1])

    def test_does_not_invent_dates_times_coordinates_or_identity(self):
        rows, audit = parse("<p>1.<br>Location Not given<br>Date: Spring 1993<br>Time: morning<br>One account.<br>HC addition, addendum<br>Source: A<br>Type: G?</p><p>1.<br>Location. Elsewhere<br>Date: 1993<br>Time: night<br>Another account.<br>HC addition # Source:<br>Source: B<br>Type: A/B</p>")
        self.assertEqual(len(rows), 2)
        self.assertEqual(len({r["sourceEntryId"] for r in rows}), 2)
        self.assertIsNone(rows[0]["dateIso"])
        self.assertEqual(rows[0]["datePrecision"], "approximate")
        self.assertIsNone(rows[0]["latitude"])
        self.assertIsNone(rows[0]["utcTime"])
        self.assertEqual(rows[1]["sourceCaseIds"], [])
        self.assertEqual(rows[1]["sourceClassificationCodes"], ["A", "B"])

    def test_invalid_calendar_and_inline_time(self):
        rows, _ = parse("<p>1.<br>Location. Example<br>Date: September 31 1993 Time: 0110A<br>Account.<br>Source: A<br>Type: G</p>")
        self.assertIsNone(rows[0]["dateIso"])
        self.assertEqual(rows[0]["datePrecision"], "invalid")
        self.assertEqual(rows[0]["timeRaw"], "0110A")
        self.assertIn("invalid_calendar_date", rows[0]["reviewFlags"])

    def test_header_type_typo_is_not_footer_classification_or_time(self):
        rows, _ = parse("<p>1.<br>Location. Example<br>Date: mid April 1993<br>Type: 1900<br>Account.<br>HC addition # 3402<br>Source: A<br>Type: E</p>")
        self.assertEqual(rows[0]["headerClassificationRaw"], "1900")
        self.assertIsNone(rows[0]["timeRaw"])
        self.assertEqual(rows[0]["sourceClassificationRaw"], "E")
        self.assertEqual(rows[0]["narrativeSha256"], parser.sha("Account."))

    def test_missing_labels_are_held_and_corrupt_capture_rejected(self):
        rows, audit = parse("<script>9. Location. Fake Date: 1993</script><p>1.<br>Location. Example<br>No date label.</p>")
        self.assertEqual(rows, [])
        self.assertEqual(len(audit["heldBlocks"]), 1)
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            parser.extract_rows(b"<p>1.</p>", {"sha256": "wrong"})

    def test_decode_preserves_legacy_smart_quotes(self):
        text, encoding = parser.decode_html(b"witness\x92s account")
        self.assertEqual(text, "witness’s account")
        self.assertEqual(encoding, "utf8_with_legacy_bytes")
        mixed, _ = parser.decode_html("quoted “word” ".encode("utf-8") + b"witness\x92s")
        self.assertEqual(mixed, "quoted “word” witness’s")

    def test_prose_does_not_create_classification_codes(self):
        rows, _ = parse("<p>1.<br>Location. Example<br>Date: 1993<br>Time: night<br>Account.<br>Source: A<br>Type: C Direct interaction with a being.</p>")
        self.assertEqual(rows[0]["sourceClassificationCodes"], ["C"])

    def test_recovers_literal_header_typos_and_preserves_partial_date(self):
        rows, _ = parse('<p>1.<br>Location. ExampleDate: September 1993<br>Time: night<br>Account.<br>Source: A<br>Type: E</p><p>2.<br>Location. Elsewhere<br>Date” August 23 1993<br>Time: midnight<br>Account.<br>Source: B<br>Type: A</p><p>3.<br>Location. Lourdes<br>April 14 1858<br>Time: afternoon<br>Account.<br>Source: C<br>Type: E</p>')
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["dateStartIso"], "1993-09")
        self.assertIsNone(rows[0]["dateIso"])
        self.assertEqual(rows[1]["dateIso"], "1993-08-23")
        self.assertIn("malformed_date_label", rows[1]["reviewFlags"])
        self.assertEqual(rows[2]["dateIso"], "1858-04-14")
        self.assertIn("unlabelled_date_header", rows[2]["reviewFlags"])

    def test_inline_source_and_type_footer(self):
        rows, _ = parse('<p>1.<br>Location. Example<br>Date: 1993<br>Time: night<br>Account.<br>Source: Journal Type: A & C?</p>')
        self.assertEqual(rows[0]["sourceCitationRaw"], "Journal")
        self.assertEqual(rows[0]["sourceClassificationRaw"], "A & C?")
        self.assertEqual(rows[0]["sourceClassificationCodes"], ["A", "C"])

    def test_pdf_native_text_page_pins_and_range(self):
        page1 = Mock()
        page1.extract_text.return_value = '1\n1900 - 1909 HUMANOID SIGHTING REPORTS\n1.\nLocation. Example\nDate: 1900 Time: unknown\nAccount starts'
        page2 = Mock()
        page2.extract_text.return_value = '2\nand ends.\nHC addition # 407\nSource: Journal T ype: E\nTotal cases: 1'
        reader = Mock(pages=[page1, page2])
        with patch('pypdf.PdfReader', return_value=reader):
            rows, audit = parser.extract_rows(b'%PDF synthetic fixture', {'sourceId': 'pdf', 'url': 'https://example.test/humanoid-1909.pdf'})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['sourcePageStart'], 1)
        self.assertEqual(rows[0]['sourcePageEnd'], 2)
        self.assertEqual(rows[0]['sourceDeclaredYearRange'], [1900, 1909])
        self.assertEqual(rows[0]['sourceCitationRaw'], 'Journal')
        self.assertEqual(rows[0]['sourceClassificationRaw'], 'E')
        self.assertEqual(rows[0]['narrativeSha256'], parser.sha('Account starts and ends.'))
        self.assertNotIn('occurrence_year_differs_from_page', rows[0]['reviewFlags'])
        self.assertEqual(audit['pdfPages'], 2)

    def test_missing_period_numbers_and_mislabelled_date(self):
        rows, _ = parse('<p>10<br>Location. First<br>Date: 1993<br>Time: night<br>Account.<br>Source: A<br>Type: E</p><p>11,<br>Location. Guamo, Italy<br>Location. June/July 1993 (1994?) Time: 1530<br>Account.<br>Source: B<br>Type: E</p>')
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['nativeEntryNumber'], '10')
        self.assertEqual(rows[1]['dateRaw'], 'June/July 1993 (1994?)')
        self.assertEqual(rows[1]['timeRaw'], '1530')
        self.assertIn('date_mislabelled_location', rows[1]['reviewFlags'])

    def test_comparison_comment_does_not_overwrite_primary_type(self):
        rows, _ = parse('<p>1.<br>Location. First<br>Date: 1993<br>Time: night<br>Account.<br>Source: A<br>Type: E<br>Comments: Compare this other report.<br>Location. Elsewhere<br>Date: 1975<br>Time: 2200<br>Other account.<br>Source: B<br>Type: G</p>')
        self.assertEqual(rows[0]['sourceClassificationRaw'], 'E')

    def test_existing_output_is_never_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'validated.json.gz'
            output.write_bytes(b'preserve')
            with self.assertRaises(FileExistsError):
                parser.build(Path(directory) / 'not-read.json', output, Path(directory) / 'audit.json')
            self.assertEqual(output.read_bytes(), b'preserve')


if __name__ == "__main__":
    unittest.main()
