"""Bounded template extraction and provenance validation regression tests."""
from copy import deepcopy
import gzip
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("recover_occurrence_clock_evidence", ROOT / "scripts/recover_occurrence_clock_evidence.py")
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)
FIXTURES = ROOT / "tests/fixtures/occurrence_clock_recovery.json"


class OccurrenceClockRecoveryTests(unittest.TestCase):
    def test_source_context_review_fixtures(self):
        fixtures = json.loads(FIXTURES.read_text(encoding="utf-8"))
        for kind, function in (("fixtures", recovery.recover_narrative), ("sourceFields", recovery.parse_source_time)):
            for row in fixtures[kind]:
                text = row.get("text", row.get("raw"))
                with self.subTest(kind=kind, text=text):
                    result = function(text)
                    accepted = bool(result and "candidateReason" not in result)
                    self.assertEqual(accepted, row["accepted"])
                    if accepted:
                        self.assertEqual(result["localStartMs"], row["start"])
                        self.assertEqual(result["localEndMs"], row["end"])
                        self.assertEqual(result["precision"], row["precision"])

    def test_reported_resolution_does_not_invent_subminute_accuracy(self):
        self.assertEqual(recovery.point_bounds("7 PM")["localEndMs"] - recovery.point_bounds("7 PM")["localStartMs"], 3_599_999)
        self.assertEqual(recovery.point_bounds("7:00 PM")["localEndMs"] - recovery.point_bounds("7:00 PM")["localStartMs"], 59_999)
        self.assertIsNone(recovery.point_bounds("24:00"))
        self.assertIsNone(recovery.point_bounds("19:60"))

    def test_source_pins_identity_quote_status_and_interval_are_fail_closed(self):
        with tempfile.TemporaryDirectory(prefix="occurrence-clock-fixture-") as folder:
            root = Path(folder)
            chunk_root = root / "data/canonical_web/event_chunks"
            chunk_root.mkdir(parents=True)
            attribute = root / "data/research/analysis-repairs-20261007/attributes/analysis_time_of_day_v1"
            attribute.mkdir(parents=True)
            (attribute / "manifest.json").write_text(json.dumps({"codes": {"source": ["majestic"], "status": ["sentinel_ambiguous", "invalid_clock"]}}))
            (attribute / "time_of_day_value_dictionary_v1.json.gz").write_bytes(gzip.compress(json.dumps([[0, "unused", "00:00", 0], [0, "unused", "5 PM", 1]]).encode()))
            event = {"event_id": 123, "source": "majestic", "source_id": "source-1", "source_row_number": 8, "sort_date_iso": "1994-09-16", "date_precision": "exact_day", "time_raw": "00:00", "description": "At 7:30 PM, I saw a bright spherical object over the field."}
            path = chunk_root / "chunk_000000.json"
            raw = json.dumps([event]).encode()
            path.write_bytes(raw)
            row = recovery.extraction_row(event, recovery.recover_narrative(event["description"]), "description", path, 0, raw, recovery.digest(raw), "sentinel_ambiguous")
            self.assertEqual(len(recovery.validate_recovered_sources([row], root)), 1)
            for key, value in (("sourceChunkSha256", "0" * 64), ("sourceId", "other"), ("date", "1994-09-17"), ("sourceTextSha256", "0" * 64), ("excerpt", "unquoted text"), ("localStartMs", 0), ("sourceTimeStatus", "invalid_clock")):
                bad = deepcopy(row)
                bad[key] = value
                with self.subTest(tampered=key), self.assertRaises(ValueError):
                    recovery.validate_recovered_sources([bad], root)
            bad = recovery.extraction_row(event, recovery.parse_source_time(event["time_raw"]), "time_raw", path, 0, raw, recovery.digest(raw), "sentinel_ambiguous")
            with self.assertRaises(ValueError):
                recovery.validate_recovered_sources([bad], root)
            with self.assertRaises(ValueError):
                recovery.validate_recovered_sources([row, row], root)


if __name__ == "__main__":
    unittest.main()
