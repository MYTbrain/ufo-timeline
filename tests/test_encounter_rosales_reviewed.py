"""Focused refusal and preservation checks for reviewed Rosales annotations."""
import contextlib
import copy
import gzip
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("rosales_reviewed", ROOT / "scripts/encounter_rosales_build_reviewed.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class ReviewedSourceGuards(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)
        source = self.path / "original.html"
        source.write_text("<p>1.<br>Location. Example, Country<br>Date: January 12 1993<br>Time: evening<br>An account of reported contact.<br>HC addition # 1234<br>Source: Historical reference<br>Type: G</p>", encoding="utf-8")
        raw = source.read_bytes()
        self.account = builder.extract_rows(raw, dict(path=str(source), sourceId="fixture", sourceUrl="https://example.test/humanoid1993.shtml", sha256=builder.sha(raw)))[0][0]
        self.entry_id = self.account["sourceEntryId"]
        chunk = self.path / "chunks"
        chunk.mkdir()
        native_bytes = json.dumps([dict(event_id=123456, source="ufocat", source_id="321", date_raw="1/12/1993", location_raw="EXAMPLE, COUNTRY", time_raw="0000")]).encode()
        (chunk / "chunk_000001.json").write_bytes(native_bytes)
        self.candidate = dict(eventId="123456", source="ufocat", sourceEventId="321", dateRaw="1/12/1993", locationRaw="EXAMPLE, COUNTRY", dateAgreement="overlap", sourceRef=dict(chunk="chunk_000001", detailIndex=0, chunkSha256=builder.sha(native_bytes)))
        self.queue = {self.entry_id: dict(sourceEntryId=self.entry_id, nativeCitationLinks=[self.candidate])}
        self.accounts = {self.entry_id: self.account}
        self.review = dict(schemaId="ufo-reviewed-rosales-decisions-v1", reviewer="manual-fixture-review", rows=[dict(sourceEntryId=self.entry_id, eventId="123456", status="linked", rationale="Reviewed native citation and source locality agree.", identityBasis=["Native HC citation", "Source date and locality"], reviewFlags=[], visibleBeingStatus="uncertain", contactKind="unclear", onboardStatus="not_described", recallMethod="unknown", scope="source_account_unsplit", craftAssociation="not_established", entityGroups=[])])
        evidence = builder.packed(dict(fixture="base evidence unchanged"))
        (self.path / "evidence.json.gz").write_bytes(gzip.compress(evidence, mtime=0))
        self.prior = dict(schemaId=builder.SCHEMA, releaseId="prior", catalogCount=702893, baseEvidenceDecodedSha256=builder.sha(evidence), taxonomyKeys=["humanoid", "human_like"], policy=dict(additiveOnly=True), **{key: [] for key in builder.TABLES})
        # A retained source row detects unintentional replacement of the pilot.
        self.prior["sources"] = [dict(sourceId="prior-source", title="Preserved pilot source")]
        self.write_inputs()

    def write_inputs(self):
        for name, value in (("review.json", self.review), ("originals.json", dict(records=list(self.accounts.values()))), ("queue.json", dict(records=list(self.queue.values())))):
            (self.path / name).write_text(json.dumps(value), encoding="utf-8")
        (self.path / "prior.json.gz").write_bytes(gzip.compress(builder.packed(self.prior), mtime=0))

    def run_build(self):
        self.write_inputs()
        with contextlib.redirect_stdout(io.StringIO()):
            return builder.build(self.path / "review.json", self.path / "validated", originals=self.path / "originals.json", queue_path=self.path / "queue.json", prior_path=self.path / "prior.json.gz", evidence_path=self.path / "evidence.json.gz", chunks=self.path / "chunks")

    def test_success_preserves_originals_type_g_is_not_abduction_and_unknowns_stay_null(self):
        inputs = {p: p.read_bytes() for p in self.path.rglob("*") if p.is_file()}
        payload, manifest, audit = self.run_build()
        self.assertEqual(audit["status"], "passed")
        self.assertTrue(builder.validate_payload(payload, self.prior))
        self.assertEqual(payload["sources"][0], self.prior["sources"][0])
        self.assertEqual(payload["entityObservations"], [])
        episode = payload["episodes"][0]
        self.assertEqual(episode["contactKind"], "unclear")
        self.assertFalse(episode["time"]["utcVerified"])
        self.assertIsNone(episode["time"]["utcStartMs"])
        self.assertIsNone(episode["site"]["lat"])
        self.assertIsNone(episode["date"]["startIso"])
        self.assertEqual(episode["date"]["raw"], "January 12 1993")
        self.assertEqual(payload["sourceEntries"][0]["sourceClassificationRaw"], "G")
        self.assertEqual(payload["sourceEntries"][0]["shortExcerpt"], "")
        self.assertNotIn("An account of reported contact", builder.packed(payload).decode())
        self.assertTrue(payload["reportLinks"][0]["acceptedForRuntime"])
        self.assertEqual(manifest["counts"]["changedEncounterClassifications"], 0)
        for path, raw in inputs.items():
            self.assertEqual(path.read_bytes(), raw)

    def test_capture_change_refused(self):
        Path(self.account["capture"]["path"]).write_text("Changed source", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "capture hash mismatch"):
            self.run_build()
        self.assertFalse((self.path / "validated").exists())

    def test_parsed_block_change_refused(self):
        self.account["sourceBlockSha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source pin mismatch"):
            self.run_build()

    def test_native_source_id_mismatch_refused(self):
        self.candidate["sourceEventId"] = "other"
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            self.run_build()

    def test_native_hash_change_refused(self):
        self.candidate["sourceRef"]["chunkSha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "chunk hash mismatch"):
            self.run_build()

    def test_missing_manual_decision_refused(self):
        self.review["rows"][0]["status"] = "held_not_admitted"
        with self.assertRaisesRegex(ValueError, "Decision must be explicit"):
            self.run_build()

    def test_duplicate_review_pair_refused(self):
        self.review["rows"].append(copy.deepcopy(self.review["rows"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate reviewed"):
            self.run_build()

    def test_held_link_is_not_accepted(self):
        self.review["rows"][0]["status"] = "candidate"
        payload, _, _ = self.run_build()
        self.assertFalse(payload["reportLinks"][0]["acceptedForRuntime"])

    def test_output_replacement_refused(self):
        (self.path / "validated").mkdir()
        with self.assertRaisesRegex(ValueError, "new directory"):
            self.run_build()

    def test_nonvisual_account_cannot_create_entity_observation(self):
        self.review["rows"][0].update(visibleBeingStatus="reported_nonvisual", entityGroups=[dict(reportedTypes=["humanoid"], count=None, attributes=[])])
        with self.assertRaisesRegex(ValueError, "Nonvisual/uncertain"):
            self.run_build()

    def test_reviewed_group_annotation_has_source_attribution(self):
        self.review["rows"][0].update(visibleBeingStatus="reported_visible", scope="dated_episode", craftAssociation="co_reported", entityGroups=[dict(reportedTypes=["human_like"], count=1, attributes=[dict(field="clothing", value="dark suit", attribution="explicit_individual")])])
        payload, _, _ = self.run_build()
        entity = payload["entityObservations"][0]
        self.assertEqual(entity["reportedTypes"], ["human_like"])
        self.assertEqual(entity["craftAssociation"], "co_reported")
        self.assertEqual(entity["attributes"][0]["entryId"], payload["sourceEntries"][0]["entryId"])
        self.assertEqual(entity["attributes"][0]["attribution"], "explicit_individual")
        self.assertEqual(payload["reportLinks"][0]["entityObservationIds"], [entity["entityObservationId"]])

    def test_individual_attribute_with_group_preserves_unresolved_member_scope(self):
        self.review["rows"][0].update(visibleBeingStatus="reported_visible", entityGroups=[dict(reportedTypes=["humanoid"], count=2, attributes=[dict(field="height", value="short", attribution="explicit_individual")])])
        payload, _, _ = self.run_build()
        entity = payload["entityObservations"][0]
        attribute = entity["attributes"][0]
        self.assertEqual(entity["count"], 2)
        self.assertEqual(attribute["value"], "short")
        self.assertEqual(attribute["attribution"], "explicit_individual")
        self.assertEqual(attribute["subjectScope"], "one_unresolved_member")
        self.assertIn("individual_attribute_target_not_separately_identified", entity["reviewFlags"])
        del attribute["subjectScope"]
        with self.assertRaisesRegex(ValueError, "membership uncertainty"):
            builder.validate_payload(payload, self.prior)

    def test_taxonomy_invention_refused(self):
        self.review["rows"][0].update(visibleBeingStatus="reported_visible", entityGroups=[dict(reportedTypes=["verified_species"], count=None, attributes=[])])
        with self.assertRaisesRegex(ValueError, "outside established taxonomy"):
            self.run_build()

    def test_entity_count_zero_is_not_unknown(self):
        self.review["rows"][0].update(visibleBeingStatus="reported_visible", entityGroups=[dict(reportedTypes=["humanoid"], count=0, attributes=[])])
        with self.assertRaisesRegex(ValueError, "positive integer or unknown"):
            self.run_build()

    def test_unverified_utc_replacement_refused(self):
        payload, _, _ = self.run_build()
        payload["episodes"][0]["time"]["utcVerified"] = True
        with self.assertRaisesRegex(ValueError, "verified UTC"):
            builder.validate_payload(payload, self.prior)

    def test_prior_pilot_modification_refused(self):
        payload, _, _ = self.run_build()
        payload["sources"][0]["title"] = "Changed"
        with self.assertRaisesRegex(ValueError, "Prior pilot table changed"):
            builder.validate_payload(payload, self.prior)


if __name__ == "__main__":
    unittest.main()
