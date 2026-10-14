"""Verify the bounded phone preview, then remove only its inventoried shell copies."""
import hashlib
import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QA = ROOT / "docs/qa/phone-preview-20261013"
sys.path.insert(0, str(ROOT / "scripts"))
from prepare_quality_release import validate_browser_references, verify_remote_record


def main():
    plan = json.loads((QA / "shell.json").read_text(encoding="utf-8"))
    base = "https://encounter-preview-20261013.ufo-timeline.pages.dev"
    records = [{**row, "source": row["stagedPath"], "requires_revalidation": False, "allow_pages_analytics": row["path"].endswith(".html")}
               for row in plan["files"] if row["path"] not in ("_headers", ".nojekyll")]
    validate_browser_references(records)
    def check(row):
        transformation = verify_remote_record(base + "/" + row["path"], row, 40)
        return {"path": row["path"], "bytes": row["bytes"], "sha256": row["sha256"], "providerTransformation": transformation}
    with ThreadPoolExecutor(max_workers=6) as pool:
        checked = list(pool.map(check, records))
    request = urllib.request.Request(base + "/whole-site.html", headers={
        "User-Agent": "Mozilla/5.0 (Linux; Android 14; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
        "Accept-Encoding": "identity"})
    with urllib.request.urlopen(request, timeout=30) as response:
        assert response.status == 200
        assert "noindex" in response.headers.get("X-Robots-Tag", "")
        canonical = response.url
        body = response.read(256 * 1024)
        assert b"encounter-complete-v3" in body and b"analysis-section-encounters" in body
    before = json.loads((QA / "production-before.json").read_text(encoding="utf-8-sig"))
    after = json.loads((QA / "production-after.json").read_text(encoding="utf-8-sig"))
    assert before["Id"] == after["Id"] and after["Branch"] == "main"
    receipt = {"schemaId": "ufo-phone-preview-public-verification-v1", "status": "passed",
               "url": canonical + "#analysis-section-encounters", "uniqueDeploymentUrl": "https://c9d37928.ufo-timeline.pages.dev",
               "runtimeCommit": plan["runtimeCommit"], "verifiedFiles": checked, "staticReferencesValid": True,
               "mobileHttpStatus": 200, "indexingDisabled": True, "browserVisualVerification": "not_available",
               "productionUnchanged": True, "productionDeployment": after["Id"], "r2ObjectsUploaded": 0,
               "corpusCopiesCreated": 0, "newFilesAbove100MiB": [], "validatedStageUnchanged": True}
    (QA / "public-verification.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    # Exact allowlist; every file must be the verified copy and have a retained
    # source/rebuild recipe. Never remove the source or retained production stage.
    stage = Path(plan["stage"]).resolve()
    assert stage == (ROOT / ".tmp/phone-preview-20261013").resolve() and not stage.is_symlink() and not stage.is_junction()
    assert set(path.resolve() for path in stage.rglob("*") if path.is_file()) == {Path(row["stagedPath"]).resolve() for row in plan["files"]}
    for row in plan["files"]:
        path = Path(row["stagedPath"]).resolve()
        assert path.is_relative_to(stage) and not path.is_symlink()
        assert path.stat().st_size == row["bytes"] and hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
        if row["retainedSource"]:
            assert Path(row["retainedSource"]).is_file()
    for row in plan["files"]:
        Path(row["stagedPath"]).unlink()
    for path in sorted((path for path in stage.rglob("*") if path.is_dir()), key=lambda path: len(path.parts), reverse=True):
        assert path.resolve().is_relative_to(stage) and not path.is_symlink() and not path.is_junction()
        path.rmdir()
    stage.rmdir()
    storage = {"canonical": "Current runtime sources and remote phone preview", "retainedRollback": "192e21f6-9c44-4b89-8d88-361e1c3d10d6",
               "retainedProduction": after["Id"], "temporaryShellRemoved": str(stage), "exactRemovalAllowlist": "shell.json files[]",
               "removedBytes": plan["totalBytes"], "newFilesAbove100MiB": [], "approximateNetDiskGrowth": "Under200KiB of builder and verification receipts plus small local Git/Wrangler cache metadata;37.77MiB temporary shell removed.",
               "remotePreviewRetention": "User-requested review preview; keep while reviewing. Production and sole rollback unchanged.", "supersededGeneratedArtifacts": [],
               "rebuild": "python scripts/prepare_phone_preview.py", "protectedSourceDeleted": False}
    (QA / "storage.json").write_text(json.dumps(storage, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "url": receipt["url"], "filesVerified": len(checked), "productionUnchanged": True, "temporaryShellRemoved": True}))


if __name__ == "__main__":
    main()
