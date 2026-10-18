"""Semantic safeguards for corpus missingness units and clock/source uncertainty."""
import importlib.util
from pathlib import Path
import unittest
from copy import deepcopy

path = Path(__file__).resolve().parents[1] / "scripts/encounter_quality_corpus_audit.py"
spec = importlib.util.spec_from_file_location("encounter_quality_corpus_audit", path)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class AuditSemantics(unittest.TestCase):
    def test_missing_clock_not_zero_clock(self):
        self.assertEqual(audit.raw_clock_kind("unknown"), "missing_or_unknown")
        self.assertEqual(audit.raw_clock_kind("night"), "period_or_other_raw")
        self.assertEqual(audit.raw_clock_kind("00:00"), "clock_like_raw_unvalidated")
        self.assertEqual(audit.raw_clock_kind("9 p.m."), "clock_like_raw_unvalidated")

    def test_bare_source_name_not_report_locator(self):
        bare = audit.citation_signals("NUFORC")
        self.assertTrue(bare["citationPresent"])
        self.assertTrue(bare["bareNamedCustodian"])
        self.assertFalse(bare["pageOrIssueLocatorMentioned"])
        self.assertTrue(audit.citation_signals("LDLN No. 329 p. 14")["pageOrIssueLocatorMentioned"])

    def test_retelling_and_personal_source_are_signals_not_independence(self):
        signals = audit.citation_signals("Humcat quoting newspaper source, personal communication")
        self.assertTrue(signals["quotationOrRetellingMentioned"])
        self.assertTrue(signals["personalCommunicationMentioned"])
        self.assertNotIn("independent", signals)

    def test_calendar_day_interval_is_not_known_clock(self):
        ref = {"chunk": "chunk_1", "detailIndex": 0, "chunkSha256": "pin"}
        evidence = {"rows": [{"eventId": "1", "source": "ufocat", "sourceEventId": "one", "sourceRef": ref, "beingTypes": ["unspecified"], "abductionStatus": "", "craftAssociation": "explicit", "evidence": [{"excerpt": "CE3"}]}]}
        summaries = {"1": {"chunk_id": "chunk_1", "detail_index": 0, "source": "ufocat", "has_coordinates": True, "location_precision": "city", "date_precision": "exact_day", "date_raw": "2000-01-01", "location_raw": "Town", "time_raw": "unknown"}}
        origins = {"rows": [{"eventId": "1", "sourceRef": ref, "sourceBeingMask": 1}]}
        timing = {"rowSchema": ["eventId", "utcStartMs", "utcEndMs", "evidenceCode", "zoneCode"], "rows": [[1, 0, 86399999, 0, 0]], "codes": {"evidence": [{"kind": "source_calendar_day_zone_bound", "timePrecision": "whole_source_calendar_day"}]}}
        rows, summary = audit.native_registry(evidence, summaries, origins, {"reportLinks": []}, timing)
        self.assertFalse(rows[0]["clockSupportedRuntimeInterval"])
        self.assertEqual(summary["fieldCoverage"]["wholeCalendarDayRuntimeInterval"], 1)
        self.assertEqual(summary["fieldCoverage"]["clockSupportedRuntimeInterval"], 0)
        self.assertEqual(summary["fieldCoverage"]["acceptedReviewedSourceContext"], 0)
        self.assertEqual(summary["fieldCoverage"]["heldReviewedSourceContext"], 0)
        self.assertTrue(rows[0]["mapped"])

    def test_source_strata_are_not_drowned_out(self):
        rows = [{"priority": "p", "source": "a", "id": i} for i in range(50)] + [{"priority": "p", "source": "b", "id": "b"}]
        queue = audit.balanced_queue(rows, "source", 2)
        self.assertEqual({row["source"] for row in queue}, {"a", "b"})

    def quality_fixture(self):
        return {"sourceEntries": [{"entryId": "subject", "caseId": "case", "episodeId": "episode"}, {"entryId": "supplement", "caseId": "case", "episodeId": "episode", "sourceId": "source"}], "sources": [{"sourceId": "source"}], "episodes": [{"episodeId": "episode", "caseId": "case"}], "reportLinks": [{"eventId": "1", "caseId": "case", "sourceEntryIds": ["subject"], "status": "candidate", "acceptedForRuntime": False}], "qualityReviews": [{"reviewId": "quality1", "subjectEntryId": "subject", "caseId": "case", "episodeId": "episode", "sourceEntryIds": ["supplement"], "classificationEffect": "none", "disposition": "additional_source_context", "associationEffect": "reviewed_identity_resolution_prior_row_retained", "findings": [{"field": "episode_identity", "text": "Pinned original investigator and witness-family match.", "sourceEntryId": "supplement"}], "associationRevision": {"eventId": "1", "previousStatus": "candidate", "status": "linked", "identityBasis": ["native bibliography", "original named-family context"]}}]}

    def test_effective_identity_revision_retains_original_row(self):
        fixture = self.quality_fixture()
        before = deepcopy(fixture)
        result = audit.effective_report_links(fixture)
        self.assertEqual(result[0]["status"], "linked")
        self.assertTrue(result[0]["acceptedForRuntime"])
        self.assertEqual(result[0]["originalStatus"], "candidate")
        self.assertFalse(result[0]["originalAcceptedForRuntime"])
        self.assertEqual(fixture, before)

    def test_supplement_findings_alone_do_not_accept_identity(self):
        fixture = self.quality_fixture()
        del fixture["qualityReviews"][0]["associationRevision"]
        fixture["qualityReviews"][0]["associationEffect"] = "none_prior_status_preserved"
        result = audit.effective_report_links(fixture)
        self.assertEqual(result[0]["status"], "candidate")
        self.assertFalse(result[0]["acceptedForRuntime"])

    def test_quality_revision_with_wrong_prior_status_is_rejected(self):
        fixture = self.quality_fixture()
        fixture["reportLinks"][0]["status"] = "contradicted"
        with self.assertRaisesRegex(ValueError, "Unreviewed"):
            audit.effective_report_links(fixture)

    def test_quality_source_cross_case_cannot_promote_identity(self):
        fixture = self.quality_fixture()
        fixture["sourceEntries"][1]["caseId"] = "another_case"
        with self.assertRaisesRegex(ValueError, "source identity mismatch"):
            audit.effective_report_links(fixture)

    def test_height_guard_preserves_raw_and_classification(self):
        ref = {"chunk": "chunk_1", "detailIndex": 0, "chunkSha256": "pin"}
        evidence = {"rows": [{"eventId": "1", "source": "ufocat", "sourceEventId": "one", "sourceRef": ref, "beingTypes": ["small_humanoid"], "abductionStatus": "", "craftAssociation": "explicit", "heightFeet": 0.5, "evidence": [{"excerpt": "0.5"}]}]}
        summaries = {"1": {"chunk_id": "chunk_1", "detail_index": 0, "source": "ufocat", "has_coordinates": True, "location_precision": "city", "date_precision": "exact_day", "date_raw": "2000-01-01", "location_raw": "Town", "time_raw": "unknown"}}
        origins = {"rows": [{"eventId": "1", "sourceRef": ref, "sourceBeingMask": 1}]}
        timing = {"rowSchema": ["eventId", "utcStartMs", "utcEndMs", "evidenceCode", "zoneCode"], "rows": [], "codes": {"evidence": []}}
        guard = {"schemaId": "ufo-encounter-attribute-reviews-v1", "baseEvidenceDecodedSha256": "base", "rows": [{"eventId": "1", "source": "ufocat", "sourceEventId": "one", "sourceRef": ref, "action": "withhold_height_feet", "originalHeightFeet": 0.5, "reportedMetricText": "0.5m tall", "reason": "source_height_units_conflict"}]}
        before = deepcopy(evidence)
        rows, summary = audit.native_registry(evidence, summaries, origins, {"reportLinks": []}, timing, guard, "base")
        self.assertEqual(rows[0]["rawIndexedHeightFeet"], 0.5)
        self.assertIsNone(rows[0]["effectiveIndexedHeightFeet"])
        self.assertEqual(rows[0]["beingTypes"], ["small_humanoid"])
        self.assertEqual(summary["fieldCoverage"]["rawIndexedHeightFeetAvailable"], 1)
        self.assertEqual(summary["fieldCoverage"]["effectiveIndexedHeightFeetAvailable"], 0)
        self.assertEqual(summary["fieldCoverage"]["heightWithheldByReviewedSourceConflict"], 1)
        self.assertEqual(evidence, before)

    def test_height_guard_rejects_stale_native_value(self):
        row = {"eventId": "1", "source": "ufocat", "sourceEventId": "one", "sourceRef": {"chunk": "chunk", "detailIndex": 0, "chunkSha256": "pin"}, "heightFeet": 0.5}
        guard = {"schemaId": "ufo-encounter-attribute-reviews-v1", "baseEvidenceDecodedSha256": "base", "rows": [{"eventId": "1", "source": "ufocat", "sourceEventId": "one", "sourceRef": row["sourceRef"], "action": "withhold_height_feet", "originalHeightFeet": 0.6, "reportedMetricText": "0.5m tall", "reason": "conflict"}]}
        with self.assertRaisesRegex(ValueError, "measurement mismatch"):
            audit.height_guard_index({"rows": [row]}, guard, "base")


if __name__ == "__main__":
    unittest.main()
