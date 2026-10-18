"""Regression checks for preserving shared captures without duplicate downloads."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("expansion_capture", Path(__file__).resolve().parents[1] / "scripts/encounter_expansion_capture.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class CaptureReuseTests(unittest.TestCase):
    def test_reused_source_is_referenced_again_without_download_or_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            canonical = root / "retained.pdf"
            canonical.write_bytes(b"%PDF-1.5\nretained")
            url = "https://example.org/retained.pdf"
            manifest = root / "reuse.json"
            manifest.write_text(json.dumps({"sources": [{"status": "reused", "path": str(canonical), "url": url, "bytes": canonical.stat().st_size, "sha256": hashlib.sha256(canonical.read_bytes()).hexdigest()}]}))
            output = root / "new"
            with patch.object(M, "SOURCES", [("test", url, "copy.pdf", 100, "test")]), patch("sys.argv", ["capture", "--reuse-manifest", str(manifest), "--output", str(output)]), patch.object(M.urllib.request, "urlopen", side_effect=AssertionError("Reused input must not be downloaded")):
                M.main()
            rows = json.loads((output / "capture_manifest.json").read_text())
            self.assertEqual(rows["totalBytes"], 0)
            self.assertEqual(rows["sources"][0]["status"], "reused")
            self.assertEqual(rows["sources"][0]["path"], str(canonical))
            self.assertEqual(list((output / "captures").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
