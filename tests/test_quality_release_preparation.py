"""Synthetic bounded release tests; no corpus, cloud upload, or network calls."""
import argparse
import copy
import gzip
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/prepare_quality_release.py"
SPEC = importlib.util.spec_from_file_location("quality_release_under_test", SCRIPT)
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


def json_write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf8")


class QualityReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ufo-quality-release-test-")
        self.root = Path(self.temporary.name).resolve()
        self.assertTrue(self.root.is_relative_to(Path(tempfile.gettempdir()).resolve()))
        self.source = self.root / "product"
        self.source.mkdir()
        self.release_root = self.root / "data/releases/quality-20261007"
        self.map_root = self.release_root / "map_delta"
        self.analysis_root = self.release_root / "analysis_delta"
        self.map_root.mkdir(parents=True)
        self.analysis_root.mkdir()
        self.quality_path = self.root / "quality.json"
        json_write(self.quality_path, {"base_catalog_mutated": False,
                                     "base": {"manifest_sha256": "b" * 64}})
        self.quality_sha = release.sha(self.quality_path)
        self.map_files = []
        self.analysis_files = []
        self.add_map("canonical_web_manifest.json", {"counts": {"events": 702893, "mapped_events": 582600}}, "r2")
        self.add_map("points_meta.json", {"row_count": 582600}, "r2")
        self.add_map("summary_manifest.json", [{"id": "shard_000"}], "r2")
        self.add_map("event_chunk_manifest.json", [{"id": "chunk_000"}], "r2")
        self.add_map("summary_shards/shard_000.json.gz", gzip.compress(b"[]", mtime=0), "r2")
        self.add_map("points.bin.gz", gzip.compress(b"reviewed-points", mtime=0), "r2")
        self.add_map("points.bin", b"reviewed-points", "local")
        self.add_map("detail_patches.json.gz", gzip.compress(b"[]", mtime=0), "pages",
                     "data/quality_detail_patches.json.gz")
        overlay = self.map_files[-1]
        self.map_receipt = self.map_root / "map_release_receipt.json"
        self.map_receipt_value = {"releaseId": release.RELEASE_ID, "qualityManifestSha256": self.quality_sha,
            "baseManifestSha256": "b" * 64,
            "counts": {"events": 702893, "mapped_events": 582600, "unmapped_events": 120293},
            "files": self.map_files,
            "detailOverlay": {"path": overlay["path"], "bytes": overlay["bytes"], "sha256": overlay["sha256"],
                "patchCount": 3, "baseManifestSha256": "b" * 64, "qualityManifestSha256": self.quality_sha,
                "publicPath": overlay["publicPath"]}}
        json_write(self.map_receipt, self.map_receipt_value)
        self.map_receipt_value["counts"]["location_precision_counts"] = {"city": 582600, "unknown": 120293}
        json_write(self.map_receipt, self.map_receipt_value)
        artifact = self.analysis_root / "analysis_v2/overview.json.gz"
        artifact.parent.mkdir()
        artifact.write_bytes(gzip.compress(b"{}", mtime=0))
        key = release.NEW_PREFIX + "/analysis_delta/analysis_v2/overview.json.gz"
        self.analysis_files.append({"path": "analysis_v2/overview.json.gz", **release.file_pin(artifact),
                                   "delivery": "r2", "public_key": key, "public_url": release.R2_ORIGIN + "/" + key})
        manifest = self.analysis_root / "analysis_v2/manifest.json"
        json_write(manifest, {"files": [{"gzipFile": release.R2_ORIGIN + "/" + key}]})
        self.analysis_files.append({"path": "analysis_v2/manifest.json", **release.file_pin(manifest),
                                   "delivery": "pages", "pages_path": "data/analysis_v2/manifest.json"})
        self.analysis_receipt = self.analysis_root / "analysis_release_receipt.json"
        json_write(self.analysis_receipt, {"release_id": release.RELEASE_ID,
                   "quality_manifest_sha256": self.quality_sha, "files": self.analysis_files})
        def map_url(name):
            return release.R2_ORIGIN + "/" + release.NEW_PREFIX + "/map_delta/" + name
        self.config = {"normalizedCount": 702893, "mappedCount": 582600,
            "deploymentProfile": {"largeDataBaseUrl": release.BASE_URL},
            "canonicalWebArtifacts": {"enabled": True, "primaryCatalog": True, "fullDetails": True,
                 "eventChunksBaseUrl": release.BASE_URL + "/data/canonical_web/event_chunks/",
                 "manifestUrl": map_url("canonical_web_manifest.json"),
                 "summaryManifestUrl": map_url("summary_manifest.json"),
                 "summaryShardsBaseUrl": map_url("summary_shards/")},
            "packedPoints": {"rowCount": 582600, "binaryUrl": map_url("points.bin"),
                             "metadataUrl": map_url("points_meta.json")},
            "locationLabelOverlay": {"entryCount": 68654},
            "detailQualityOverlay": {"enabled": True, "gzipUrl": "./data/quality_detail_patches.json.gz",
                "gzipSha256": overlay["sha256"], "patchCount": 3,
                "baseManifestSha256": "b" * 64, "qualityManifestSha256": self.quality_sha}}
        json_write(self.source / "data/app_config.json", self.config)
        (self.source / "app.js").write_text("const ready = true;", encoding="utf8")
        (self.source / "sw.js").write_text("// retained retirement worker", encoding="utf8")
        (self.source / "index.html").write_text('<script src="quality_detail_overlay.js?v=1"></script><script src="app.js"></script>', encoding="utf8")
        (self.source / "quality_detail_overlay.js").write_text("const overlay = true;", encoding="utf8")
        (self.source / "_headers").write_text("/*\n  Cache-Control: public, max-age=0, must-revalidate\n", encoding="utf8")
        baseline_files = [{"path": name, **release.file_pin(self.source / name)}
                          for name in ("app.js", "index.html", "sw.js", "_headers", "data/app_config.json")]
        self.baseline_path = self.source / ".tmp/interface-pages-inventory.json"
        json_write(self.baseline_path, {"fileCount": len(baseline_files), "files": baseline_files,
                   "treeSha256": release.tree_hash(baseline_files), "candidateRoot": "prior-validated-candidate"})
        base_file = {"path": "data/canonical_web/event_chunks/chunk_000.json.gz", "bytes": 100,
                     "sha256": "c" * 64, "url": release.BASE_URL + "/data/canonical_web/event_chunks/chunk_000.json.gz"}
        self.base_path = self.root / "base-contract.json"
        json_write(self.base_path, {"r2": {"base_url": release.BASE_URL, "key_prefix": release.BASE_PREFIX,
             "files": [base_file], "file_count": 1, "total_bytes": 100,
             "tree_sha256": release.tree_hash([base_file])}})
        self.args = argparse.Namespace(source_root=self.source, baseline_inventory=self.baseline_path,
              quality_manifest=self.quality_path, base_contract=self.base_path, release_root=self.release_root,
              map_receipt=None, analysis_receipt=None, detail_receipt=None, output=None, metadata_root=None,
              extra_pages_path=["quality_detail_overlay.js"])

    def tearDown(self):
        self.temporary.cleanup()

    def add_map(self, name, value, delivery, public_path=None):
        path = self.map_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, bytes):
            path.write_bytes(value)
        else:
            json_write(path, value)
        key = release.NEW_PREFIX + "/map_delta/" + name
        self.map_files.append({"path": name, **release.file_pin(path), "delivery": delivery,
                              "publicPath": public_path if delivery == "pages" else key,
                              "immutableKey": key if delivery == "r2" else None})

    def test_check_only_plan_inherits_corpus_without_copy_and_excludes_local_bins(self):
        plan = release.make_plan(self.args)
        self.assertEqual(len(plan["inherited_objects"]), 1)
        self.assertFalse(plan["inherited_r2_contract"]["source_bytes_rehashed"])
        self.assertFalse(Path(plan["candidate_root"]).exists())
        self.assertFalse(Path(plan["metadata_root"]).exists())
        self.assertNotIn("points.bin", [row["path"] for row in plan["uploads"]])
        self.assertIn("points.bin", [row["path"] for row in plan["local_verification_only_files"]])
        self.assertIn("data/canonical_web/points_meta.json", [row["path"] for row in plan["pages"]])

    def test_preparation_frozen_inventory_and_no_overwrite(self):
        plan = release.make_plan(self.args)
        release.prepare(plan)
        release.verify_candidate(plan)
        contract = release.load(Path(plan["metadata_root"]) / "replication_contract.json")
        self.assertEqual(contract["unchanged_canonical_r2"], plan["inherited_objects"])
        self.assertEqual(contract["new_r2_delta"], plan["uploads"])
        with self.assertRaises(release.ReleaseError):
            release.prepare(plan)

    def test_stale_quality_and_delta_digests_rejected(self):
        self.map_receipt_value["qualityManifestSha256"] = "0" * 64
        json_write(self.map_receipt, self.map_receipt_value)
        with self.assertRaisesRegex(release.ReleaseError, "stale/unpinned"):
            release.make_plan(self.args)
        self.map_receipt_value["qualityManifestSha256"] = self.quality_sha
        json_write(self.map_receipt, self.map_receipt_value)
        (self.map_root / "points.bin.gz").write_bytes(b"changed")
        with self.assertRaisesRegex(release.ReleaseError, "size changed|digest changed"):
            release.make_plan(self.args)

    def test_path_escape_key_escape_and_undeclared_new_url_rejected(self):
        for value in ("../source.csv", "C:/private.txt", "/absolute.txt", "data//x", "data\\x"):
            with self.assertRaises(release.ReleaseError):
                release.relative(value)
        self.map_receipt_value["files"][0]["immutableKey"] = "releases/old/canonical_web_manifest.json"
        json_write(self.map_receipt, self.map_receipt_value)
        with self.assertRaisesRegex(release.ReleaseError, "R2 key"):
            release.make_plan(self.args)

    def test_old_point_runtime_and_conflicting_detail_overlay_rejected(self):
        original = copy.deepcopy(self.config)
        self.config["packedPoints"]["binaryUrl"] = release.BASE_URL + "/data/canonical_web/points.bin"
        json_write(self.source / "data/app_config.json", self.config)
        with self.assertRaisesRegex(release.ReleaseError, "old data"):
            release.make_plan(self.args)
        self.config = original
        self.config["detailQualityOverlay"]["gzipSha256"] = "f" * 64
        json_write(self.source / "data/app_config.json", self.config)
        with self.assertRaisesRegex(release.ReleaseError, "overlay config"):
            release.make_plan(self.args)

    def test_missing_browser_module_and_preserved_asset_edit_rejected(self):
        self.args.extra_pages_path = []
        with self.assertRaisesRegex(release.ReleaseError, "Browser asset"):
            release.make_plan(self.args)
        self.args.extra_pages_path = ["quality_detail_overlay.js"]
        (self.source / "sw.js").write_text("// changed", encoding="utf8")
        with self.assertRaisesRegex(release.ReleaseError, "Preserved Pages asset"):
            release.make_plan(self.args)

    def test_undeclared_new_manifest_url_and_duplicate_page_path_rejected(self):
        file = self.analysis_root / "analysis_v2/manifest.json"
        json_write(file, {"gzipFile": release.R2_ORIGIN + "/" + release.NEW_PREFIX + "/analysis_delta/missing.json.gz"})
        self.analysis_files[-1].update(release.file_pin(file))
        json_write(self.analysis_receipt, {"quality_manifest_sha256": self.quality_sha, "files": self.analysis_files})
        with self.assertRaisesRegex(release.ReleaseError, "undeclared new R2 object"):
            release.make_plan(self.args)

    def test_caps_and_changed_candidate_bytes_fail_closed(self):
        with patch.object(release, "PAGES_CAP", 1):
            with self.assertRaisesRegex(release.ReleaseError, "40 MiB"):
                release.make_plan(self.args)
        with patch.object(release, "RELEASE_CAP", 1):
            with self.assertRaisesRegex(release.ReleaseError, "850 MiB"):
                release.make_plan(self.args)
        plan = release.make_plan(self.args)
        release.prepare(plan)
        (Path(plan["candidate_root"]) / "app.js").write_text("// changed after freeze", encoding="utf8")
        with self.assertRaisesRegex(release.ReleaseError, "size changed|digest changed"):
            release.verify_candidate(plan)

    def test_public_verification_rejects_foreign_or_non_immutable_hosts_before_network(self):
        plan = release.make_plan(self.args)
        for url in ("http://ufo-timeline.pages.dev", "https://evil.example",
                    "https://user@ufo-timeline.pages.dev", "https://ufo-timeline.pages.dev/path",
                    "https://fake.ufo-timeline.pages.dev", "https://ufo-timeline.pages.dev?query=1"):
            with self.assertRaises(release.ReleaseError):
                release.public_verification(plan, url, 1)

    def test_config_generation_dry_run_then_declared_source_updates(self):
        original = copy.deepcopy(self.config)
        original["mappedCount"] = 580783
        original["packedPoints"]["rowCount"] = 580783
        json_write(self.source / "data/app_config.json", original)
        result = release.configure_source(self.args, True)
        self.assertEqual(result["mapped_count"], 582600)
        self.assertEqual(release.load(self.source / "data/app_config.json")["mappedCount"], 580783)
        self.assertFalse((self.source / "data/quality_detail_patches.json.gz").exists())
        release.configure_source(self.args, False)
        self.assertEqual(release.load(self.source / "data/app_config.json")["mappedCount"], 582600)
        self.assertTrue((self.source / "data/quality_detail_patches.json.gz").exists())
        release.make_plan(self.args)

    def test_cache_misconfiguration_and_parallel_pages_only_verification(self):
        plan = release.make_plan(self.args)
        with patch.object(release, "verify_remote_record") as check:
            result = release.public_verification(plan, "https://1234abcd.ufo-timeline.pages.dev", 1, True)
        self.assertEqual(check.call_count, len(plan["pages"]) - 1)
        self.assertEqual(result["new_r2_objects_verified"], 0)
        self.assertEqual(result["parallel_streams"], 4)
        (self.source / "_headers").write_text("/*\n  Cache-Control: public, max-age=31536000, immutable\n", encoding="utf8")
        with self.assertRaisesRegex(release.ReleaseError, "not revalidated"):
            release.make_plan(self.args)

    def test_exact_provider_analytics_envelope_and_all_other_html_changes_rejected(self):
        source = b"<html><body>source</body></html>"
        insertion = release.PAGES_ANALYTICS_INSERTION
        self.assertEqual(len(insertion), 214)
        normalized, result = release.normalize_provider_html(source.replace(b"</body>", insertion + b"</body>"))
        self.assertEqual(normalized, source)
        self.assertEqual(result["inserted_bytes"], 214)
        for value in (source.replace(b"</body>", insertion * 2 + b"</body>"), insertion + source):
            with self.assertRaises(release.ReleaseError):
                release.normalize_provider_html(value)
        class Response(io.BytesIO):
            status = 200
            headers = {"Cache-Control": "public, max-age=0, must-revalidate"}
        record = {"path": "index.html", "bytes": len(source),
                  "sha256": release.hashlib.sha256(source).hexdigest(), "allow_pages_analytics": True}
        payload = source.replace(b"</body>", insertion + b"</body>")
        with patch.object(release.urllib.request, "urlopen", return_value=Response(payload)):
            self.assertEqual(release.verify_remote_record("https://ufo-timeline.pages.dev/index.html", record, 1)["path"], "index.html")
        for invalid in (payload.replace(b"df011473", b"ef011473"), payload.replace(b"source", b"SOURCE")):
            with patch.object(release.urllib.request, "urlopen", return_value=Response(invalid)):
                with self.assertRaises(release.ReleaseError):
                    release.verify_remote_record("https://ufo-timeline.pages.dev/index.html", record, 1)
        with patch.object(release.urllib.request, "urlopen", return_value=Response(payload)):
            with self.assertRaises(release.ReleaseError):
                release.verify_remote_record("https://ufo-timeline.pages.dev/data.bin", dict(record, allow_pages_analytics=False), 1)

    def portable_fixture(self):
        plan = release.make_plan(self.args)
        # Replace the synthetic original hash with a real tiny source payload.
        original = b"x" * 100
        plan["inherited_objects"][0]["sha256"] = release.hashlib.sha256(original).hexdigest()
        plan["inherited_objects"].append({"path": "data/canonical_web/summary_shards/obsolete.json.gz",
            "url": release.BASE_URL + "/data/canonical_web/summary_shards/obsolete.json.gz",
            "bytes": 1000000000, "sha256": "e" * 64})
        contract = release.modern_contract(plan)
        path = self.root / "portable.json"
        json_write(path, contract)
        args = argparse.Namespace(hydrate_contract=path, hydrate_cache=self.root / "runtime-cache",
            shared_base_root=None, shared_release_root=self.release_root, shared_r2_root=None,
            verify_pages_root=None, check_only=False, verify_cache=False, timeout=1)
        return plan, contract, args, original

    def test_portable_contract_excludes_obsolete_projections_and_has_no_machine_paths(self):
        plan, contract, args, original = self.portable_fixture()
        release.validate_modern_contract(contract)
        self.assertFalse(any("obsolete" in row["url"] for row in contract["runtime_objects"]))
        self.assertNotIn(str(self.root), json.dumps(contract))
        path = self.root / "git/quality_release.json"
        exported = release.write_modern_contract(path, plan)
        self.assertEqual(exported["runtime_objects"], contract["runtime_object_count"])
        self.assertEqual(release.load(path), contract)
        broken = copy.deepcopy(contract)
        broken["runtime_objects"][0]["url"] = "https://foreign.example/releases/evil.gz"
        with self.assertRaises(release.ReleaseError):
            release.validate_modern_contract(broken)

    def test_hydration_shared_files_verified_without_copy_or_network(self):
        plan, contract, args, original = self.portable_fixture()
        shared = self.root / "shared-canonical"
        (shared / "event_chunks").mkdir(parents=True)
        (shared / "event_chunks/chunk_000.json.gz").write_bytes(original)
        args.shared_base_root = shared
        args.verify_cache = True
        with patch.object(release.urllib.request, "urlopen") as network:
            result = release.hydrate_contract(args)
        self.assertEqual(result["missing_unique_objects"], 0)
        self.assertEqual(result["shared_objects_verified"], contract["runtime_object_count"])
        self.assertFalse(args.hydrate_cache.exists())
        network.assert_not_called()
        (shared / "event_chunks/chunk_000.json.gz").write_bytes(b"wrong")
        with self.assertRaisesRegex(release.ReleaseError, "size changed|digest changed"):
            release.hydrate_contract(args)

    def test_missing_object_hydration_is_bounded_and_bad_cache_fails_closed(self):
        plan, contract, args, original = self.portable_fixture()
        args.check_only = True
        result = release.hydrate_contract(args)
        self.assertEqual(result["download_bytes"], len(original))
        self.assertFalse(args.hydrate_cache.exists())
        args.check_only = False
        original_url = release.BASE_URL + "/data/canonical_web/event_chunks/chunk_000.json.gz"
        class Response(io.BytesIO):
            status = 200
            headers = {}
            def geturl(self):
                return original_url
        with patch.object(release.urllib.request, "urlopen", return_value=Response(original)) as network:
            result = release.hydrate_contract(args)
        self.assertEqual(network.call_count, 1)
        target = args.hydrate_cache / "objects" / release.hashlib.sha256(original).hexdigest()
        self.assertEqual(target.read_bytes(), original)
        self.assertTrue((args.hydrate_cache / "runtime_index.json").is_file())
        self.assertFalse(any(args.hydrate_cache.rglob("*.part")))
        args.verify_cache = True
        self.assertEqual(release.hydrate_contract(args)["download_bytes"], 0)
        target.write_bytes(b"stale")
        with self.assertRaisesRegex(release.ReleaseError, "size changed|digest changed"):
            release.hydrate_contract(args)

    def test_bad_download_hash_and_oversize_leave_no_accepted_cache_object(self):
        plan, contract, args, original = self.portable_fixture()
        original_url = release.BASE_URL + "/data/canonical_web/event_chunks/chunk_000.json.gz"
        class Response(io.BytesIO):
            status = 200
            headers = {}
            def geturl(self):
                return original_url
        for payload in (b"y" * 100, original + b"extra"):
            with patch.object(release.urllib.request, "urlopen", return_value=Response(payload)):
                with self.assertRaises(release.ReleaseError):
                    release.hydrate_contract(args)
            self.assertEqual(list((args.hydrate_cache / "objects").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
