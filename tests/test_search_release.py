"""Search delivery guard tests; all fixtures are small and synthetic."""
import ast
import copy
import hashlib
import inspect
import json
from pathlib import Path
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import prepare_workspace_analysis_release as release


class SearchReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ufo-search-release-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "derivative"
        self.source.mkdir()
        self.manifest = {
            "schemaVersion": 1, "recordCount": 702893,
            "coverage": {"complete": True, "includesUnmapped": True,
                         "currentCatalogIdSetSha256": "a" * 64, "indexedIdSetSha256": "a" * 64},
            "ids": self.member("ids.json.gz"), "pages": self.member("pages.json.gz"),
            "lexicon": self.member("lexicon.json.gz"),
            "textPacks": [self.member("text_000.pack")],
            "postingPacks": [self.member("postings_000.pack")],
            "sourceProof": {"file": "source_pins.json", "private": "C:/private/source/path"},
        }
        (self.source / "source_pins.json").write_text("private provenance", encoding="utf-8")
        self.base_uploads = [{"key": f"existing/{n}", "source": f"protected-{n}", "sha256": f"sha-{n}"}
                             for n in range(87)]

    def member(self, filename):
        data = ("synthetic " + filename).encode()
        (self.source / filename).write_bytes(data)
        return {"file": filename, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}

    def upload_function(self, uploads):
        # Execute the actual nested production helper with its closure supplied.
        tree = ast.parse(textwrap.dedent(inspect.getsource(release.assemble)))
        helper = next(node for node in tree.body[0].body
                      if isinstance(node, ast.FunctionDef) and node.name == "upload")
        namespace = dict(vars(release), uploads=uploads)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[helper], type_ignores=[])),
                     "<actual release upload helper>", "exec"), namespace)
        return namespace["upload"]

    def prepare(self, changed=None, manifest_pin=None):
        value = copy.deepcopy(changed or self.manifest)
        data = (json.dumps(value, indent=2) + "\n").encode()
        (self.source / "manifest.json").write_bytes(data)
        pages, uploads, pins, config = {}, {}, [], {}
        # Extract only the actual search-assembly block. This keeps fixtures small
        # while testing the same guard and rewriting logic as a complete release.
        source = textwrap.dedent(inspect.getsource(release.assemble))
        start = source.index('    source_search_manifest = SEARCH_DIRECTORY / "manifest.json"')
        end = source.index('    config["staticAssetVersion"]', start)
        block = textwrap.dedent(source[start:end])
        namespace = dict(vars(release), config=config,
                         SEARCH_DIRECTORY=self.source,
                         SEARCH_SOURCE_MANIFEST_SHA256=manifest_pin or hashlib.sha256(data).hexdigest(),
                         pin=lambda file, role: pins.append((file, role)),
                         page_json=lambda logical, payload: pages.update({logical: copy.deepcopy(payload)}),
                         upload=self.upload_function(uploads))
        exec(compile(block, "<actual release search block>", "exec"), namespace)
        return pages, uploads, pins, config

    def test_search_members_are_r2_only_and_provenance_stays_local(self):
        pages, uploads, pins, config = self.prepare()
        self.assertEqual(set(pages), {release.SEARCH_MANIFEST})
        self.assertEqual(len(uploads), 5)
        public = pages[release.SEARCH_MANIFEST]
        self.assertNotIn("sourceProof", public)
        self.assertNotIn("private", json.dumps(public))
        self.assertNotIn("source_pins.json", json.dumps(uploads))
        self.assertEqual(pins[0][0], self.source / "manifest.json")
        self.assertEqual(config["searchIndex"]["expectedRecordCount"], 702893)
        self.assertEqual(config["searchIndex"]["expectedIdSetSha256"], "a" * 64)
        self.assertEqual(config["searchIndex"]["loadPolicy"], "first_keyword_search")
        public_bytes = (json.dumps(public, indent=2, ensure_ascii=False) + "\n").encode()
        self.assertEqual(config["searchIndex"]["manifestSha256"], hashlib.sha256(public_bytes).hexdigest())
        for row in uploads.values():
            self.assertTrue(row["key"].startswith(release.SEARCH_PREFIX + "/"))
            self.assertEqual(Path(row["source"]).parent, self.source)
            self.assertNotIn("content_encoding", row)
            self.assertNotIn("contentEncoding", row)
            expected_type = "application/octet-stream" if row["key"].endswith(".pack") else "application/gzip"
            self.assertEqual(row["content_type"], expected_type)

    def test_rejects_source_pin_population_or_identity_drift(self):
        with self.assertRaisesRegex(ValueError, "manifest pin drift"):
            self.prepare(manifest_pin="0" * 64)
        for mutation in [
            lambda value: value.update(recordCount=702892),
            lambda value: value["coverage"].update(complete=False),
            lambda value: value["coverage"].update(includesUnmapped=False),
            lambda value: value["coverage"].update(indexedIdSetSha256="b" * 64),
        ]:
            changed = copy.deepcopy(self.manifest)
            mutation(changed)
            with self.assertRaisesRegex(ValueError, "complete current corpus"):
                self.prepare(changed)

    def test_rejects_member_drift_and_path_escape(self):
        for mutation, message in [
            (lambda value: value["ids"].update(bytes=0), "member pin drift"),
            (lambda value: value["ids"].update(sha256="b" * 64), "member pin drift"),
            (lambda value: value["ids"].update(file="../private.json.gz"), "Unsafe search derivative"),
            (lambda value: value["ids"].update(file="source..json.gz"), "Unsafe search derivative"),
        ]:
            changed = copy.deepcopy(self.manifest)
            mutation(changed)
            with self.assertRaisesRegex(ValueError, message):
                self.prepare(changed)

    def test_refresh_preserves_every_old_pin_and_allows_only_additive_search(self):
        previous = {"uploads": self.base_uploads, "pages": [{"path": "index.html"}]}
        candidate = copy.deepcopy(previous)
        candidate["uploads"].extend({"key": release.SEARCH_PREFIX + f"/member-{n}.pack", "sha256": f"new-{n}"}
                                    for n in range(16))
        candidate["pages"].extend({"path": value} for value in [release.SEARCH_MANIFEST,
                                                                   "search_query.js", "search_catalog.js",
                                                                   "search_runtime.js", "search_worker.js",
                                                                   "search_view.js", "search_view.css"])
        release.validate_refresh(previous, candidate)
        self.assertEqual(candidate["uploads"][:87], previous["uploads"])
        for mutation in [lambda value: value["uploads"].pop(0),
                         lambda value: value["uploads"][0].update(sha256="replacement"),
                         lambda value: value["uploads"][0].update(source="different source")]:
            bad = copy.deepcopy(candidate)
            mutation(bad)
            with self.assertRaisesRegex(ValueError, "[Ii]mmutable uploads"):
                release.validate_refresh(previous, bad)
        bad = copy.deepcopy(candidate)
        bad["uploads"].append({"key": "releases/unreviewed/private"})
        with self.assertRaisesRegex(ValueError, "reviewed search index"):
            release.validate_refresh(previous, bad)
        for extra_page in ["data/search/text_000.pack", "data/search/ids.json.gz", "private/source_pins.json"]:
            bad = copy.deepcopy(candidate)
            bad["pages"].append({"path": extra_page})
            with self.assertRaisesRegex(ValueError, "file inventory"):
                release.validate_refresh(previous, bad)


if __name__ == "__main__":
    unittest.main()
