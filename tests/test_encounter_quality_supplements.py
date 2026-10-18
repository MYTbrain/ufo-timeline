import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from encounter_quality_supplements import enrich, packed, sha


def fixture():
    prior = dict(schemaId="ufo-encounter-enrichment-v1", sources=[dict(sourceId="old")],
                 sourceEntries=[dict(entryId="old-entry", sourceId="old", caseId="case", episodeIds=["episode"])],
                 cases=[dict(caseId="case")], episodes=[dict(episodeId="episode", caseId="case", time=dict(utcStartMs=None), site=dict(lat=None))],
                 entityObservations=[], reportLinks=[dict(eventId="123", source="ufocat", caseId="case", sourceEntryIds=["old-entry"], status="candidate", acceptedForRuntime=False)])
    review = dict(schemaId="ufo-encounter-quality-review-v1", reviewer="manual source review", priorContentSha256=sha(packed(prior)),
                  sources=[dict(sourceId="new", title="Original investigator", url="https://example.org/original", kind="investigator", capture=dict(path="not-used", bytes=10, sha256="a"*64))],
                  sourceEntries=[dict(entryId="new-entry", sourceId="new", caseId="case", episodeId="episode", title="Earlier account", locator="printed page 15", evidenceSha256="a"*64, evidenceHashMeaning="captured_source_bytes")],
                  reviews=[dict(reviewId="review", subjectEntryId="old-entry", caseId="case", episodeId="episode", sourceEntryIds=["new-entry"], disposition="additional_source_context", findings=[dict(field="episode_identity", text="Original investigator and named family match the exact source page.", sourceEntryId="new-entry")], rationale="Named family and original bibliographic page resolve identity while the year remains disputed.", associationRevision=dict(eventId="123", previousStatus="candidate", status="linked", identityBasis=["named family", "exact original source page"]))])
    return prior, review


class QualitySupplementTests(unittest.TestCase):
    def test_preserved_rows_and_explicit_revision_are_separate(self):
        prior, review = fixture()
        payload, audit = enrich(prior, review, verify_captures=False)
        for table in ("sources", "sourceEntries", "cases", "episodes", "entityObservations", "reportLinks"):
            self.assertEqual(payload[table][:len(prior[table])], prior[table])
        self.assertFalse(payload["reportLinks"][0]["acceptedForRuntime"])
        self.assertEqual(audit["effectiveAcceptedLinks"], 1)
        self.assertIsNone(payload["episodes"][0]["site"]["lat"])

    def test_changed_prior_cannot_receive_old_review(self):
        prior, review = fixture()
        prior["reportLinks"][0]["status"] = "contradicted"
        with self.assertRaisesRegex(ValueError, "prior changed"):
            enrich(prior, review, verify_captures=False)

    def test_capture_and_fact_references_are_not_interchangeable(self):
        prior, review = fixture()
        review["sourceEntries"][0]["evidenceSha256"] = "b"*64
        with self.assertRaisesRegex(ValueError, "captured source bytes"):
            enrich(prior, review, verify_captures=False)
        prior, review = fixture()
        review["reviews"][0]["findings"][0]["sourceEntryId"] = "old-entry"
        with self.assertRaisesRegex(ValueError, "Fact evidence reference"):
            enrich(prior, review, verify_captures=False)

    def test_contradicted_case_cannot_be_promoted_by_candidate_revision(self):
        prior, review = fixture()
        prior["reportLinks"][0]["status"] = "contradicted"
        review["priorContentSha256"] = sha(packed(prior))
        with self.assertRaisesRegex(ValueError, "prior identity/status"):
            enrich(prior, review, verify_captures=False)

    def test_unreviewed_core_fields_are_rejected(self):
        prior, review = fixture()
        review["reviews"][0]["latitude"] = -33
        with self.assertRaisesRegex(ValueError, "core evidence"):
            enrich(prior, review, verify_captures=False)

    def test_real_capture_is_verified(self):
        prior, review = fixture()
        with self.assertRaises(FileNotFoundError):
            enrich(prior, review)


if __name__ == "__main__":
    unittest.main()
