"""Freeze the accepted workspace UI and changed-only analysis/data release.

Shared protected datasets are referenced in place. Only the small Pages shell is
copied; gzip deltas are uploaded directly from their canonical locations. This
builder does not upload, overwrite immutable cloud objects, or delete anything.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sys

from prepare_quality_release import validate_browser_references, verify_remote_record, tree_hash
from concurrent.futures import ThreadPoolExecutor

RELEASE = "workspace-analysis-20261008"
ORIGIN = "https://pub-e9029ab2f6b448daad03d7cde7e15e64.r2.dev"
PREFIX = "releases/" + RELEASE
BASE_DEPLOYMENT = "dc834bac-2108-4de3-baad-47044e2ec51c"
RUNTIME_REVISION = "trace-chronology-20261008"
RETAINED_ROLLBACK = "a70bc14c-550c-4057-b461-bca4fd7aba27"
ROOT = Path(__file__).resolve().parent.parent
SHARED = Path(r"C:/Users/jarod/Desktop/UFO Timeline map tool")
REPAIRS = SHARED / "data/research/analysis-repairs-20261007"
PAGES = ROOT / ".tmp" / (RELEASE + "-pages")
META = ROOT / "releases" / RELEASE
OLD_MAP = ORIGIN + "/releases/quality-20261007/map_delta/"
OLD_ANIMALS = ORIGIN + "/releases/animal-mutilations-v1-20260812/"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def release_url(logical):
    return ORIGIN + "/" + PREFIX + "/" + logical


def assemble(check_only=False):
    base = load(ROOT / "reproduction/quality_release.json")
    base_pages = {row["path"]: row for row in base["pages"]}
    pages = {row["path"]: ROOT / row["path"] for row in base["pages"]}
    uploads = {}
    derived = {}
    input_pins = []

    def pin(path, role):
        require(path.is_file(), "Missing protected input: " + str(path))
        input_pins.append({"path": str(path), "bytes": path.stat().st_size, "sha256": sha(path), "role": role})

    def upload(path, logical):
        require(path.is_file(), "Missing changed asset: " + str(path))
        require(".." not in logical.split("/") and not logical.startswith("/"), "Unsafe logical path")
        key = PREFIX + "/" + logical
        uploads[key] = {"key": key, "url": ORIGIN + "/" + key, "source": str(path.resolve()),
                        "bytes": path.stat().st_size, "sha256": sha(path),
                        "content_type": "application/gzip" if logical.endswith(".gz") else "application/json"}
        return ORIGIN + "/" + key

    def page_json(logical, value):
        derived[logical] = value
        pages[logical] = ROOT / logical

    # Accepted runtime assets only; research reports/QA/private source archives
    # never become Pages assets merely because they live alongside runtime data.
    new_runtime = ["analysis_astronomy_engine.js", "analysis_comparisons.css", "analysis_comparisons_view.js",
                   "analysis_cross_context.js", "analysis_lunar.js", "analysis_nuclear.js", "analysis_planetary.js",
                   "analysis_repair_detail_overlay.js", "trace_chronology.js",
                   "guided_tour.css", "guided_tour.js", "guided_tour_content.js", "guided_tour_state.js", "help_panel.js"]
    for name in new_runtime:
        pages[name] = ROOT / name
    for path in (ROOT / "ui/accepted-workspace").iterdir():
        if path.suffix in (".css", ".js"):
            pages[path.relative_to(ROOT).as_posix()] = path

    config = copy.deepcopy(load(ROOT / "data/app_config.json"))
    config["staticAssetVersion"] = RELEASE
    config["analysisWorkspaceRelease"] = {"id": RELEASE, "baseDeployment": BASE_DEPLOYMENT,
                                         "sourceRowsPreserved": 702893, "mappedRowsPreserved": 582877}

    # Small, precomputed source-clock sidecar; no canonical corpus copies or R2
    # replacement. Its hash contract is checked by the main thread and worker.
    timing = load(ROOT / "data/trace_chronology/manifest.json")
    timing_file = ROOT / "data/trace_chronology/evidence.json.gz"
    require(timing_file.is_file() and sha(timing_file) == timing["gzipSha256"], "Timing sidecar hash drift")
    pages["data/trace_chronology/evidence.json.gz"] = timing_file
    pages["data/trace_chronology/manifest.json"] = ROOT / "data/trace_chronology/manifest.json"
    config["traceChronologyEvidenceUrl"] = "./data/trace_chronology/evidence.json.gz"
    config["traceChronologyEvidenceGzipSha256"] = timing["gzipSha256"]
    config["traceChronologyEvidenceSha256"] = timing["decodedSha256"]
    config["traceChronologyEvidenceRowCount"] = timing["rowCount"]
    pin(timing_file, "precomputed guarded source-clock UTC evidence")

    # All 71 changed summary gzip shards; the two reviewed year corrections win.
    catalog = REPAIRS / "catalog"
    reviewed = REPAIRS / "source-quality/catalog"
    manifest = load(reviewed / "canonical_web_manifest.json")
    summary = load(reviewed / "summary_manifest.json")
    require(manifest["counts"]["events"] == 702893 and manifest["counts"]["mapped_events"] == 582877,
            "Catalog identity/count drift")
    for row in summary:
        relative = "summary_shards/" + row["file"] + ".gz"
        source = reviewed / relative
        if not source.exists():
            source = catalog / relative
        upload(source, "data/canonical_web/" + relative)
    pin(catalog / "catalog_overlay_receipt.json", "MUFON date-overlay receipt")
    pin(reviewed / "catalog_overlay_receipt.json", "reviewed-year overlay receipt")
    for name in manifest["artifacts"]:
        if name == "summary_manifest":
            manifest["artifacts"][name] = release_url("data/canonical_web/summary_manifest.json")
        elif name == "summary_shards_dir":
            manifest["artifacts"][name] = release_url("data/canonical_web/summary_shards/")
        elif name == "event_chunks_dir":
            manifest["artifacts"][name] = config["canonicalWebArtifacts"]["eventChunksBaseUrl"]
        else:
            manifest["artifacts"][name] = OLD_MAP + manifest["artifacts"][name]
    for field in ("repairOverlay", "reviewedYearOverlay"):
        manifest[field]["status"] = "published_reviewed_overlay"
    page_json("data/canonical_web/canonical_web_manifest.json", manifest)
    page_json("data/canonical_web/summary_manifest.json", summary)
    config["canonicalWebArtifacts"]["manifestUrl"] = release_url("data/canonical_web/canonical_web_manifest.json")
    config["canonicalWebArtifacts"]["summaryManifestUrl"] = release_url("data/canonical_web/summary_manifest.json")
    config["canonicalWebArtifacts"]["summaryShardsBaseUrl"] = release_url("data/canonical_web/summary_shards/")

    # Attribute dictionaries and witness projection. Existing unchanged geometry,
    # clock and duration projection objects retain their immutable URLs and pins.
    for directory in (REPAIRS / "attributes").iterdir():
        if not directory.is_dir() or not (directory / "manifest.json").exists():
            continue
        name = directory.name
        value = load(directory / "manifest.json")
        pin(directory / "manifest.json", "reviewed attribute manifest")
        for path in directory.glob("*.gz"):
            upload(path, "data/" + name + "/" + path.name)
        for artifact in value["artifacts"].values():
            for field in ("file", "gzipFile"):
                filename = artifact.get(field, "")
                if filename and not filename.startswith("https://"):
                    artifact[field] = release_url("data/" + name + "/" + filename)
        value["assetBaseUrl"] = release_url("data/" + name + "/")
        value["delivery"].update(mode="published_reviewed_overlay", productionPublished=True,
                                 immutablePrefix=PREFIX + "/data/" + name + "/")
        page_json("data/" + name + "/manifest.json", value)

    # Crop analysis projection and reviewed animal detail evidence.
    context = REPAIRS / "context"
    for path in context.rglob("*.gz"):
        upload(path, "data/" + path.relative_to(context).as_posix())
    analysis = load(context / "analysis_v1/manifest.json")
    for artifact in analysis["artifacts"].values():
        for field in ("file", "gzipFile"):
            logical = artifact[field]
            if (context / logical.removeprefix("data/")).exists() or (context / (logical.removeprefix("data/") + ".gz")).exists():
                artifact[field] = release_url(logical)
    page_json("data/analysis_v1/manifest.json", analysis)
    analysis["delivery"]["immutablePrefix"] = PREFIX + "/data/analysis_v1/"
    animal = load(context / "animal_mutilations/manifest.json")
    animal["assetBaseUrl"] = release_url("data/animal_mutilations/")
    for item in [animal["catalog"], animal["points"], *animal["details"]["files"]]:
        local = context / "animal_mutilations" / item["path"]
        if not local.exists():
            item["path"] = OLD_ANIMALS + item["path"]
    animal["delivery"]["immutablePrefix"] = PREFIX + "/data/animal_mutilations/"
    animal["delivery"]["r2OnlyPaths"] = [item["path"] for item in
        [animal["catalog"], animal["points"], *animal["details"]["files"]]]
    page_json("data/animal_mutilations/manifest.json", animal)

    # Lunar/nuclear/cross-context and the physical planetary atlas. The atlas is
    # never copied into Pages. QA/source-reference files are deliberately omitted.
    comparisons = load(ROOT / "data/analysis_comparisons/manifest.json")
    for name in ("context_rows.json.gz", "nuclear_context_v1.json.gz", "ephemeris_atlas_v1.bin.gz"):
        upload(ROOT / "data/analysis_comparisons" / name, "data/analysis_comparisons/" + name)
    for name in ("context", "nuclear"):
        artifact = comparisons["artifacts"][name]
        artifact["file"] = release_url("data/analysis_comparisons/" + Path(artifact["file"]).name)
    facility = comparisons["artifacts"]["facilities"]
    facility["file"] = facility["sourceFile"]
    comparisons["ephemerisAtlas"]["file"] = release_url("data/analysis_comparisons/ephemeris_atlas_v1.bin.gz")
    page_json("data/analysis_comparisons/manifest.json", comparisons)

    # Sparse original-detail corrections apply after the retained quality overlay.
    repair_contract = load(ROOT / "data/analysis_repair_detail/manifest.json")
    detail_file = ROOT / "data/analysis_repair_detail" / repair_contract["file"]
    detail_url = upload(detail_file, "data/analysis_repair_detail/" + detail_file.name)
    config["analysisRepairDetailOverlay"] = dict(repair_contract, enabled=True, gzipUrl=detail_url)
    config["analysisRepairDetailOverlay"].pop("file", None)
    page_json("data/app_config.json", config)

    # A frozen manifest can be published both at its Pages lookup location and
    # at the immutable delivery prefix used by its explicit URLs.
    if not check_only:
        for logical, value in derived.items():
            write(ROOT / logical, value)
        for logical in ("data/canonical_web/canonical_web_manifest.json", "data/canonical_web/summary_manifest.json"):
            upload(ROOT / logical, logical)

    records = []
    for logical, path in sorted(pages.items()):
        require(path.is_file() or logical in derived, "Missing Pages runtime asset: " + logical)
        if logical in derived and check_only:
            blob = (json.dumps(derived[logical], indent=2, ensure_ascii=False) + "\n").encode()
            size, digest = len(blob), hashlib.sha256(blob).hexdigest()
        else:
            size, digest = path.stat().st_size, sha(path)
        require(size < 25 * 1024 * 1024, "Pages file cap: " + logical)
        records.append({"path": logical, "source": str(path.resolve()), "bytes": size, "sha256": digest,
                        "requires_revalidation": (logical not in base_pages or base_pages[logical]["sha256"] != digest)
                            and logical.endswith((".js", ".css", ".html", ".json")),
                        "allow_pages_analytics": logical.endswith(".html")})
    total = sum(r["bytes"] for r in records)
    require(total < 40 * 1024 * 1024, "Bounded Pages candidate exceeds40MiB")
    require(shutil.disk_usage(ROOT).free - total > 100 * 1024**3, "C reserve would fall below100GiB")
    plan = {"schema": "ufo-workspace-analysis-release-v1", "release_id": RELEASE,
            "base_deployment": BASE_DEPLOYMENT, "runtime_revision": RUNTIME_REVISION,
            "retained_rollback": RETAINED_ROLLBACK,
            "counts": {"events": 702893, "mapped": 582877}, "pages": records,
            "pages_tree_sha256": tree_hash(records), "pages_total_bytes": total,
            "bucket": "ufo-timeline-data", "key_prefix": PREFIX,
            "uploads": sorted(uploads.values(), key=lambda r:r["key"]),
            "upload_total_bytes": sum(r["bytes"] for r in uploads.values()),
            "inherited_runtime_objects": base["runtime_objects"], "input_pins": input_pins,
            "storage": {"corpus_copied": False, "new_files_above_100MiB": [],
                        "approximate_net_local_growth_bytes": total,
                        "canonical_candidate": str(PAGES), "shared_inputs": str(REPAIRS),
                        "rollback": RETAINED_ROLLBACK, "superseded_staging": [],
                        "cleanup": "No data deletion. Earlier rollback designation is superseded; shared source assets remain protected."}}
    if not check_only:
        validate_browser_references(records)
        write(META / "delivery_plan.json", plan)
        write(META / "upload_manifest.json", {k:plan[k] for k in ("release_id", "bucket", "key_prefix", "uploads", "upload_total_bytes")})
    return plan


def verify(plan):
    expected = {row["path"] for row in plan["pages"]}
    require({p.relative_to(PAGES).as_posix() for p in PAGES.rglob("*") if p.is_file()} == expected, "Pages inventory drift")
    for row in plan["pages"]:
        p = PAGES / row["path"]
        require(p.stat().st_size == row["bytes"] and sha(p) == row["sha256"], "Frozen Pages bytes changed:" + row["path"])
    for row in plan["uploads"]:
        p = Path(row["source"])
        require(p.stat().st_size == row["bytes"] and sha(p) == row["sha256"], "Frozen delta changed:" + row["key"])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--check-only", action="store_true")
    p.add_argument("--stage", action="store_true")
    p.add_argument("--refresh-stage", action="store_true", help="Verify and update the single existing candidate; immutable uploads must stay identical")
    p.add_argument("--verify-existing", action="store_true")
    p.add_argument("--verify-public")
    p.add_argument("--pages-only", action="store_true")
    args = p.parse_args()
    if args.verify_existing or args.verify_public:
        plan = load(META / "delivery_plan.json")
        verify(plan)
        if args.verify_public:
            checks = [(args.verify_public.rstrip("/") + "/" + r["path"], r) for r in plan["pages"] if r["path"] not in ("_headers", ".nojekyll")]
            if not args.pages_only:
                checks += [(r["url"],dict(r,requires_revalidation=False)) for r in plan["uploads"]]
            with ThreadPoolExecutor(max_workers=4) as executor:
                transformations = list(executor.map(lambda x:verify_remote_record(x[0],x[1],90), checks))
            result = {"passed": True,"url":args.verify_public,"verified_objects":len(checks),
                      "pages_only":args.pages_only,"provider_transformations":[x for x in transformations if x]}
            write(META / ("production_verification.json" if args.pages_only else "preview_verification.json"),result)
            print(json.dumps(result));return
    else:
        previous = None
        if args.refresh_stage:
            previous = load(META / "delivery_plan.json")
            verify(previous)
        plan = assemble(check_only=args.check_only)
        if args.stage or args.refresh_stage:
            require(not args.check_only, "Cannot stage a check-only plan")
            if args.refresh_stage:
                require(previous["uploads"] == plan["uploads"], "Immutable uploads changed during candidate refresh")
                old_paths = {r["path"] for r in previous["pages"]}
                new_paths = {r["path"] for r in plan["pages"]}
                require(old_paths <= new_paths and new_paths - old_paths <= {
                    "trace_chronology.js", "data/trace_chronology/evidence.json.gz", "data/trace_chronology/manifest.json"
                }, "Candidate file inventory changed beyond the reviewed timing sidecar")
            else:
                require(not PAGES.exists(), "Refusing extra/overwritten Pages candidate")
            for row in plan["pages"]:
                target = PAGES / row["path"]
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(row["source"],target)
            verify(plan)
    print(json.dumps({"passed":True,"release_id":RELEASE,"pages_files":len(plan["pages"]),
                      "pages_bytes":plan["pages_total_bytes"],"upload_objects":len(plan["uploads"]),
                      "upload_bytes":plan["upload_total_bytes"],"pages_tree_sha256":plan["pages_tree_sha256"]}))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("Release refused: " + str(error),file=sys.stderr);raise SystemExit(1)
