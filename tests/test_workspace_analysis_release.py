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
                              {"path": "data/encounters/enrichment.json.gz"}])
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


if __name__ == "__main__":
    unittest.main()
