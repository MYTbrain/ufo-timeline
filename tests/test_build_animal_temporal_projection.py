"""Bounded, synthetic country-extension tests; no private source duplication."""
from __future__ import annotations

import gzip
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/build_animal_temporal_projection.py"
SPEC = importlib.util.spec_from_file_location("animal_temporal_builder", MODULE_PATH)
Builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(Builder)


class AnimalTemporalProjectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="animal-temporal-fixture-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.frozen = self.root / "frozen"
        self.private = self.root / "private/seed.jsonl"
        self.output = self.root / "derived"
        self.private.parent.mkdir(parents=True)
        self.records = [
            {"canonical_incident_id": "seed-us", "location": {"country_code": "USA", "latitude_internal": 123.456789},
             "summary": "PRIVATE_NARRATIVE_DO_NOT_EXPORT"},
            {"canonical_incident_id": "seed-jp", "location": {"country_code": "AS"}},
            {"canonical_incident_id": "seed-conflict", "location": {"country_code": "US"}},
        ]
        self.private.write_bytes(b"\n".join(Builder.compact(value) for value in self.records) + b"\n")
        self.seed_sha = Builder.digest(self.private.read_bytes())
        self.rows = [[key, 1978, 1978, 0, [1], False, 1, 722306, 722306]
                     for key in ["public-us", "public-jp", "public-conflict", "new-case"]]
        self.details = {
            "public-us": {"id": "public-us", "sourceIncidentId": "seed-us", "location": "Place, Texas, US"},
            "public-jp": {"id": "public-jp", "sourceIncidentId": "seed-jp", "location": "Saga, JPN, AS"},
            "public-conflict": {"id": "public-conflict", "sourceIncidentId": "seed-conflict", "location": "Place, Canada"},
            "new-case": {"id": "new-case", "sourceIncidentId": "new-unjoined", "sourceIncidentSha256": None, "location": "Town, CA"},
        }
        by_id = {value["canonical_incident_id"]: value for value in self.records}
        for detail in self.details.values():
            source = by_id.get(detail["sourceIncidentId"])
            if source:
                detail["sourceIncidentSha256"] = Builder.digest(Builder.compact(source))
        self.write_fixture()

    def write_fixture(self):
        projection = Builder.compact(self.rows)
        packed = gzip.compress(projection, mtime=0)
        path = self.frozen / "projections/analysis_v1/animal_reports.json.gz"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(packed)
        manifest = {"artifacts": {"animalReports": {
            "rowSchema": Builder.ROW_SCHEMA, "gzipSha256": Builder.digest(packed), "gzipBytes": len(packed),
            "sha256": Builder.digest(projection), "bytes": len(projection), "rowCount": len(self.rows),
        }}}
        path = self.frozen / "public/data/analysis_v1/manifest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(Builder.compact(manifest))
        packed_details = gzip.compress(Builder.compact(self.details), mtime=0)
        path = self.frozen / "layers/animal_mutilations/details/chunk_000.json.gz"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(packed_details)
        manifest = {"details": {"files": [{"path": "details/chunk_000.json.gz", "sha256": Builder.digest(packed_details),
                                             "bytes": len(packed_details), "recordCount": len(self.details)}]}}
        (self.frozen / "layers/animal_mutilations/manifest.json").write_bytes(Builder.compact(manifest))

    def build(self, **overrides):
        return Builder.build_animal_temporal_projection(
            self.frozen, self.private, self.output,
            expected_seed_sha256=overrides.get("expected_seed_sha256", self.seed_sha),
            expected_record_count=4, expected_seed_matches=3,
            write_outputs=overrides.get("write_outputs", True))

    def test_preserves_fields_count_privacy_and_determinism(self):
        result = self.build()
        output_path = self.output / result["projection"]["file"]
        payload = output_path.read_bytes()
        rows = json.loads(payload)
        self.assertEqual([row[:9] for row in rows], self.rows)
        self.assertEqual([row[9] for row in rows], ["US", "JP", "unknown", "unknown"])
        self.assertEqual(result["projection"]["rowCount"], 4)
        self.assertEqual(result["projection"]["rowSchema"], Builder.ROW_SCHEMA + ["country"])
        self.assertEqual(result["counts"]["seedMatched"], 3)
        self.assertEqual(result["counts"]["seedUnmatched"], 1)
        self.assertEqual(result["counts"]["knownCountry"], 2)
        self.assertEqual(result["counts"]["countryResolution"]["continent_suffix_recovered"], 1)
        self.assertEqual(result["counts"]["countryResolution"]["country_conflict"], 1)
        provenance = (self.output / result["provenance"]["path"]).read_bytes()
        compressed = (self.output / result["projection"]["gzipFile"]).read_bytes()
        self.assertEqual(gzip.decompress(compressed), payload)
        for forbidden in [b"latitude_internal", b"PRIVATE_NARRATIVE_DO_NOT_EXPORT", str(self.private).encode(), b"123.456789"]:
            self.assertNotIn(forbidden, payload + provenance)
        public = json.loads(provenance)
        self.assertTrue(all("path" not in pin for pin in public["inputs"]))
        self.assertTrue(all("path" in pin for pin in result["inputPins"]))
        self.assertEqual(len(list((self.output / "data/analysis_v1").iterdir())), 3)
        self.assertEqual(self.build(), result)
        self.assertEqual((self.output / result["projection"]["gzipFile"]).read_bytes(), compressed)
        self.assertEqual((self.output / result["provenance"]["path"]).read_bytes(), provenance)

    def test_explicit_country_aliases_and_suffixes_only(self):
        for raw, location, expected in [
            ("France", "Locality", "FR"), ("Brazil", "Locality", "BR"),
            ("Israel", "Locality", "IL"), ("Argentina", "Locality", "AR"),
            ("SA", "Otoco, BOL, SA", "BO"), ("SA", "Calama, CHI, SA", "CL"),
            ("ME", "Porat, ISR, ME", "IL"), ("EU", "St Claude, FRA, EU", "FR"),
            ("EU", "Lake Lintel, GER, EU", "DE"), (None, "Place, CANADA", "CA"),
            (None, "Place, CA", "unknown"), (None, "Place, AR", "unknown"),
            (None, "Place, Texas", "unknown"), (None, "Kansas City", "unknown"),
            ("EU", "Place, EU", "unknown"), ("not_a_country", "Place", "unknown"),
            ("US", "Place, CAN", "unknown"), (None, "FRA, Unspecified", "unknown"),
        ]:
            with self.subTest(raw=raw, location=location):
                self.assertEqual(Builder.resolve_country(raw, location)[0], expected)

    def test_check_only_creates_nothing_and_returns_identical_metadata(self):
        checked = self.build(write_outputs=False)
        self.assertFalse(self.output.exists())
        written = self.build()
        self.assertEqual(checked, written)
        paths = list((self.output / "data/analysis_v1").iterdir())
        before = {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths}
        self.assertEqual(self.build(write_outputs=False), written)
        self.assertEqual({path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths}, before)

    def test_seed_hash_mismatch_fails_before_outputs(self):
        self.private.write_bytes(self.private.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "private_seed_country_source hash mismatch"):
            self.build()
        self.assertFalse(self.output.exists())

    def test_join_record_hash_mismatch_fails_before_outputs(self):
        self.details["public-us"]["sourceIncidentSha256"] = "0" * 64
        self.write_fixture()
        with self.assertRaisesRegex(ValueError, "canonical record hash mismatch"):
            self.build()
        self.assertFalse(self.output.exists())

    def test_projection_gzip_pin_mismatch_fails(self):
        path = self.frozen / "projections/analysis_v1/animal_reports.json.gz"
        path.write_bytes(path.read_bytes() + b"\x00")
        with self.assertRaisesRegex(ValueError, "animal_projection_gzip hash mismatch"):
            self.build()

    def test_projection_detail_identity_mismatch_fails(self):
        self.details["new-case"]["id"] = "incorrect"
        self.write_fixture()
        with self.assertRaisesRegex(ValueError, "detail ID disagreement"):
            self.build()

    def test_duplicate_projection_ids_fail(self):
        self.rows[-1][0] = self.rows[0][0]
        self.write_fixture()
        with self.assertRaisesRegex(ValueError, "Duplicate animal projection IDs"):
            self.build()

    def test_duplicate_seed_join_fails(self):
        self.details["public-jp"]["sourceIncidentId"] = "seed-us"
        self.details["public-jp"]["sourceIncidentSha256"] = self.details["public-us"]["sourceIncidentSha256"]
        self.write_fixture()
        with self.assertRaisesRegex(ValueError, "Duplicate public detail/private seed join"):
            self.build()

    def test_output_cannot_modify_frozen_release(self):
        with self.assertRaisesRegex(ValueError, "Frozen release inputs must remain immutable"):
            Builder.build_animal_temporal_projection(self.frozen, self.private, self.frozen / "derived")


if __name__ == "__main__":
    unittest.main()
