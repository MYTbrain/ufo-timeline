"""Bounded Pages extension pins and guarded release refresh checks."""
import copy
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import prepare_workspace_analysis_release as release


class WorkspaceAnalysisReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ufo-release-extension-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / release.NUCLEAR_EXTENSION
        self.source.parent.mkdir(parents=True)
        self.payload = {"schemaId": "ufo-nuclear-context-extension-v1",
                        "releaseId": "synthetic-reviewed-extension", "tests": []}
        decoded = json.dumps(self.payload).encode()
        compressed = gzip.compress(decoded, mtime=0)
        self.source.write_bytes(compressed)
        self.artifact = {"schemaId": self.payload["schemaId"], "releaseId": self.payload["releaseId"],
                         "file": "./nuclear_extension_v1.json.gz", "url": "./" + release.NUCLEAR_EXTENSION,
                         "gzipBytes": len(compressed), "gzipSha256": hashlib.sha256(compressed).hexdigest(),
                         "bytes": len(decoded), "sha256": hashlib.sha256(decoded).hexdigest()}
        self.comparisons = {"artifacts": {"nuclearExtension": self.artifact}}
        self.previous = {"uploads": [{"key": "immutable-existing", "sha256": "a" * 64}],
                         "pages": [{"path": "index.html"}]}

    def prepare_extension(self, comparisons=None):
        pages, pins = {}, []
        with patch.object(release, "ROOT", self.root):
            release.add_nuclear_extension_pages(comparisons or self.comparisons, pages,
                                                lambda path, role: pins.append((path, role)))
        return pages, pins

    def test_extension_is_pinned_pages_asset_with_relative_manifest_paths(self):
        pages, pins = self.prepare_extension()
        self.assertEqual(pages, {release.NUCLEAR_EXTENSION: self.source})
        self.assertEqual(pins[0][0], self.source)
        self.assertEqual(self.artifact["file"], "./nuclear_extension_v1.json.gz")
        self.assertEqual(self.artifact["url"], "./" + release.NUCLEAR_EXTENSION)
        self.assertNotIn("https://", self.artifact["file"])

    def test_rejects_physical_decoded_and_identity_drift(self):
        for field, value, message in [
            ("gzipBytes", 0, "gzip pin"), ("gzipSha256", "0" * 64, "gzip pin"),
            ("bytes", 0, "decoded pin"), ("sha256", "0" * 64, "decoded pin"),
            ("schemaId", "different-schema", "identity"),
            ("releaseId", "different-release", "identity"),
            ("file", "./unreviewed.json.gz", "filename")
        ]:
            with self.subTest(field=field):
                comparisons = copy.deepcopy(self.comparisons)
                comparisons["artifacts"]["nuclearExtension"][field] = value
                with self.assertRaisesRegex(ValueError, message):
                    self.prepare_extension(comparisons)

    def test_absent_extension_does_not_add_pages_or_pins(self):
        self.assertEqual(self.prepare_extension({"artifacts": {}}), ({}, []))

    def test_refresh_allows_only_reviewed_additions_with_identical_uploads(self):
        plan = copy.deepcopy(self.previous)
        plan["pages"].extend([{"path": release.NUCLEAR_EXTENSION},
                              {"path": "data/encounters/enrichment.json.gz"},
                              {"path": "analysis_overview_visuals.js"}])
        plan["pages"].extend({"path": path} for path in (
            "analysis_readiness_model.js", "analysis_readiness_view.js", "analysis_readiness.css"))
        release.validate_refresh(self.previous, plan)
        for mutation, message in [
            (lambda p: p["uploads"][0].update(sha256="b" * 64), "Immutable uploads"),
            (lambda p: p["uploads"].append({"key": "new-unapproved"}), "Immutable uploads"),
            (lambda p: p["pages"].append({"path": "private/source.pdf"}), "file inventory"),
            (lambda p: p["pages"].pop(0), "file inventory")
        ]:
            with self.subTest(message=message):
                changed = copy.deepcopy(plan)
                mutation(changed)
                with self.assertRaisesRegex(ValueError, message):
                    release.validate_refresh(self.previous, changed)

    def test_collection_study_pins_population_policy_and_reviewed_joins(self):
        payload = {"schemaId": "ufo-collection-evidence-v1", "schemaVersion": 1,
                   "reports": [{"eventId": "11", "canonicalJoinStatus": "validated_id_source_chunk_index"}],
                   "cases": [{"caseId": "unjoined-control"}],
                   "policy": {"canonicalDataMutated": False, "keywordCandidatesPromoted": False,
                              "casesExcludedFromReportMatrices": True}}

        def prepare(value, manifest_change=None):
            decoded = json.dumps(value).encode()
            compressed = gzip.compress(decoded, mtime=0)
            source = self.root / release.COLLECTION_EVIDENCE
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(compressed)
            manifest = {"schemaId": payload["schemaId"], "schemaVersion": 1, "artifact": {
                "file": "evidence.json.gz", "url": "./" + release.COLLECTION_EVIDENCE,
                "gzipBytes": len(compressed), "gzipSha256": hashlib.sha256(compressed).hexdigest(),
                "decodedBytes": len(decoded), "decodedSha256": hashlib.sha256(decoded).hexdigest(),
                "reportCount": len(value["reports"]), "caseCount": len(value["cases"])}}
            if manifest_change:
                manifest_change(manifest)
            (self.root / release.COLLECTION_MANIFEST).write_text(json.dumps(manifest))
            pages, pins = {}, []
            with patch.object(release, "ROOT", self.root):
                release.add_collection_study_pages(pages, lambda path, role: pins.append(path))
            return pages, pins

        pages, pins = prepare(payload)
        self.assertEqual(set(pages), {release.COLLECTION_MANIFEST, release.COLLECTION_EVIDENCE})
        self.assertEqual(len(pins), 2)
        for change, message in [
            (lambda p: p["policy"].update(keywordCandidatesPromoted=True), "source policy"),
            (lambda p: p["policy"].update(casesExcludedFromReportMatrices=False), "source policy"),
            (lambda p: p["reports"].append(copy.deepcopy(p["reports"][0])), "report join"),
            (lambda p: p["reports"][0].update(canonicalJoinStatus="candidate"), "report join"),
        ]:
            value = copy.deepcopy(payload)
            change(value)
            with self.assertRaisesRegex(ValueError, message):
                prepare(value)
        with self.assertRaisesRegex(ValueError, "population identity"):
            prepare(payload, lambda m: m["artifact"].update(reportCount=2))
        with self.assertRaisesRegex(ValueError, "gzip pin"):
            prepare(payload, lambda m: m["artifact"].update(gzipSha256="0" * 64))


if __name__ == "__main__":
    unittest.main()
