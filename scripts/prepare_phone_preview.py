"""Build only the allowlisted public runtime shell for a phone review.

Reuses published R2 data and leaves the validated production stage untouched.
The temporary shell is removed via its exact file inventory after verification;
this script never deploys, uploads data, modifies runtime sources or deletes files.
"""
from __future__ import annotations
import ast
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / ".tmp/phone-preview-20261013"
QA = ROOT / "docs/qa/phone-preview-20261013"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert not STAGE.exists(), "Refusing to overwrite an existing preview shell"
    previous = json.loads((ROOT / "releases/workspace-analysis-20261008/delivery_plan.json").read_text(encoding="utf-8"))
    logicals = {row["path"] for row in previous["pages"]}
    tree = ast.parse((ROOT / "scripts/prepare_workspace_analysis_release.py").read_text(encoding="utf-8"))
    runtime_list = next(node.value for node in ast.walk(tree) if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "new_runtime" for target in node.targets))
    logicals.update(ast.literal_eval(runtime_list))
    logicals.update(path.relative_to(ROOT).as_posix() for path in (ROOT / "ui/accepted-workspace").iterdir() if path.suffix in (".css", ".js"))
    logicals.update(["data/encounters/manifest.json", "data/encounters/evidence.json.gz", "data/encounters/label_origins.json.gz",
                     "data/encounters/enrichment.json.gz", "data/analysis_comparisons/manifest.json", "data/analysis_comparisons/nuclear_extension_v1.json.gz"])
    originals = []
    for logical in sorted(logicals):
        assert not logical.startswith((".", "/")) or logical == ".nojekyll", logical
        assert ".." not in Path(logical).parts and not logical.startswith(("docs/", "scripts/", "node_modules/")), logical
        source = ROOT / logical
        assert source.is_file(), "Missing approved runtime source: " + logical
        assert source.stat().st_size < 25 * 1024**2, logical
        originals.append({"path": logical, "source": str(source), "bytes": source.stat().st_size, "sha256": sha(source)})
    total = sum(row["bytes"] for row in originals) + (ROOT / "index.html").stat().st_size + 512
    assert total < 50 * 1024**2, "Preview shell exceeds bounded50MiB budget"
    assert shutil.disk_usage(ROOT).free > total + 128 * 1024**2, "Insufficient disk space for bounded preview"
    config = json.loads((ROOT / "data/app_config.json").read_text(encoding="utf-8"))
    assert config["canonicalWebArtifacts"]["summaryShardsBaseUrl"].startswith("https://pub-"), "Preview must reuse public catalog"
    assert config["canonicalWebArtifacts"]["eventChunksBaseUrl"].startswith("https://pub-"), "Preview must reuse public details"
    comparisons = json.loads((ROOT / "data/analysis_comparisons/manifest.json").read_text(encoding="utf-8"))
    assert comparisons["artifacts"]["nuclearExtension"]["file"] == "./nuclear_extension_v1.json.gz", "New nuclear extension must stay in preview, not unpublished R2"
    for row in originals:
        target = STAGE / row["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(row["source"], target)
        assert sha(target) == row["sha256"]
    shutil.copyfile(ROOT / "index.html", STAGE / "whole-site.html")
    with (STAGE / "_headers").open("a", encoding="utf-8", newline="\n") as handle:
        handle.write("\n/whole-site.html\n  Cache-Control: public, max-age=0, must-revalidate\n\n/*\n  X-Robots-Tag: noindex, nofollow\n")
    (STAGE / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    records = []
    by_path = {row["path"]: row for row in originals}
    for path in sorted(STAGE.rglob("*")):
        if not path.is_file():
            continue
        logical = path.relative_to(STAGE).as_posix()
        retained = by_path.get(logical)
        records.append({"path": logical, "stagedPath": str(path.resolve()), "bytes": path.stat().st_size, "sha256": sha(path),
                        "retainedSource": retained["source"] if retained else str(ROOT / "index.html") if logical == "whole-site.html" else None,
                        "rebuild": "python scripts/prepare_phone_preview.py"})
    receipt = {"schemaId": "ufo-phone-preview-shell-v1", "branch": "encounter-preview-20261013", "productionBranch": "main",
               "runtimeCommit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(),
               "stage": str(STAGE), "files": records, "totalBytes": sum(row["bytes"] for row in records),
               "sourcePins": originals, "validatedProductionStage": str(ROOT / ".tmp/workspace-analysis-20261008-pages"),
               "corpusCopiesCreated": 0, "newFilesAbove100MiB": [], "retention": "Temporary curated preview shell only; remove exact staged files after hosted verification. Preserve this small manifest and the remote preview for user review. Production and its sole rollback remain unchanged.",
               "publicScope": "Previously allowlisted runtime assets plus current encounter metadata and nuclear patch; no workspace, scripts, source archive or scientific QA directory is served."}
    QA.mkdir(parents=True, exist_ok=True)
    (QA / "shell.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"stage": str(STAGE), "files": len(records), "bytes": receipt["totalBytes"], "expectedNetGrowthMiB": round(receipt["totalBytes"] / 1024**2, 2), "corpusCopied": False}))


if __name__ == "__main__":
    main()
