"""Prepare the small, explicitly allowed Pages interface release without R2 copies.

Run --check-only first. Staging requires a fresh .tmp output directory and writes
its hash inventory beside, never inside, that public directory. The existing
production data/configuration and retirement worker are pinned to the confirmed
production Git revision. This script does not build data, upload, delete, or alter
the checkout. Re-run --verify-existing immediately before publishing.
"""

from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import shutil
import subprocess
import sys
from urllib.parse import unquote, urlsplit


BASELINE_COMMIT = "6fb09834ec028b48e4d201a1ee632206d5c38404"
BASELINE_DEPLOYMENT = "ca73305a-aff6-4466-8d9a-83c9416f4cfe"
R2_BASE = "https://pub-e9029ab2f6b448daad03d7cde7e15e64.r2.dev/releases/coordinated-reliability-v152-20260731"
MAX_TOTAL_BYTES = 35 * 1024 * 1024
MAX_FILE_BYTES = 8 * 1024 * 1024
BASELINE_SHELL = frozenset("""
.nojekyll 404.html _headers index.html styles.css sw.js
analysis_spatial.js analysis_spatial_worker.js analysis_stats.js analysis_view.js
animal_mutilation_bootstrap.js animal_mutilation_layer.js app.js
catalog_filter_worker.js crop_circle_bootstrap.js crop_circle_layer.js
flap_preset_labels.js legend_controls.js playback_performance.js
startup_profile_worker.js trace_facility_worker.js trace_neighborhood.js
""".split())
MUTABLE_SHELL = frozenset("""
app.js index.html styles.css legend_controls.js trace_neighborhood.js
animal_mutilation_bootstrap.js animal_mutilation_layer.js
crop_circle_bootstrap.js crop_circle_layer.js
""".split())
NEW_INTERFACE_PATHS = frozenset("""
famous_case_presets.js trace_direction_summary.js trace_intersection_layer.js
trace_intersection_feasibility.html trace_intersection_feasibility.js
trace_intersection_feasibility.css
data/trace_intersection_feasibility_v1/manifest.json
data/trace_intersection_feasibility_v1/strict_25km_7d_buffer1.json
data/trace_intersection_feasibility_v1/strict_25km_7d_buffer5.json
""".split())
BASELINE_DATA = frozenset("""
data/analysis_color_v1/manifest.json
data/analysis_coordinate_evidence_v1/manifest.json
data/analysis_duration_v1/manifest.json
data/analysis_reporting_delay_v1/manifest.json
data/analysis_time_of_day_v1/manifest.json
data/analysis_v1/animal_reports.json data/analysis_v1/animal_reports.json.gz
data/analysis_v1/crop_circles.json data/analysis_v1/crop_circles.json.gz
data/analysis_v1/manifest.json data/analysis_v2/manifest.json
data/analysis_witness_count_v1/manifest.json
data/animal_mutilations/manifest.json data/app_config.json
data/canonical_web/artifact_size_report.json
data/canonical_web/canonical_web_manifest.json
data/canonical_web/compression_report.json
data/canonical_web/event_chunk_manifest.json
data/canonical_web/points_meta.json data/canonical_web/summary_manifest.json
data/canonical_web/trace_aggregate_bins_meta.json
data/canonical_web/trace_event_index_meta.json
data/canonical_web/trace_segments_meta.json
data/claimed_ufo_bases.json data/crop_circles/manifest.json
data/event_catalog_manifest.json data/event_chunk_manifest.json
data/location_label_overlay.json.gz
data/map_overlays/airports.geojson data/map_overlays/highways.geojson
data/map_overlays/military_base_overlay_membership_overrides.json
data/map_overlays/military_base_temporal_overrides.json
data/map_overlays/military_bases.geojson
data/map_overlays/new_zealand_military_facilities.geojson
data/map_overlays/new_zealand_research_facilities.geojson
data/map_overlays/northern_europe_research_test_sites_pass3_marker_sized_conservative.geojson
data/map_overlays/overlay_sources.json data/map_overlays/research_test_sites.geojson
data/map_overlays/research_test_sites_config.json
data/points.bin data/points_meta.json data/world_countries.geojson
data/startup_profiles/manifest.json data/startup_profiles/manifest.json.gz
""".split())
PROFILE_IDS = (
    "france_1954_flap", "belgium_1989_1990_wave", "mystery_airship_wave_1896_1897",
)
PROFILE_FILES = """
events.json manifest.json points.bin points_meta.json trace_aggregate_bins.bin
trace_aggregate_bins_meta.json trace_event_index.bin trace_event_index_meta.json
trace_preview_segments.json trace_segments.bin trace_segments_meta.json
""".split()
PROFILE_PATHS = frozenset(
    f"data/startup_profiles/{profile}/{name}{suffix}"
    for profile in PROFILE_IDS for name in PROFILE_FILES for suffix in ("", ".gz")
)
VENDOR_PATHS = frozenset("""
vendor/MarkerCluster.Default.css vendor/MarkerCluster.css vendor/leaflet.css
vendor/leaflet.js vendor/leaflet.markercluster.js vendor/images/layers-2x.png
vendor/images/layers.png vendor/images/marker-icon-2x.png
vendor/images/marker-icon.png vendor/images/marker-shadow.png
""".split())
PUBLIC_PATHS = BASELINE_SHELL | BASELINE_DATA | PROFILE_PATHS | VENDOR_PATHS | NEW_INTERFACE_PATHS
PRESERVED_PATHS = PUBLIC_PATHS - MUTABLE_SHELL - NEW_INTERFACE_PATHS
NON_RUNTIME_SOURCE_PATHS = frozenset({"data/map_overlays/README.txt"})


class ReleaseError(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReleaseError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git(source: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(source), *args], capture_output=True, check=False)
    require(result.returncode == 0, "Git baseline could not be read; no files were staged.")
    return result.stdout


def safe_asset(root: Path, relative: str) -> Path:
    path = root.joinpath(*PurePosixPath(relative).parts)
    require(path.resolve().is_relative_to(root), f"Asset escapes the source root: {relative}")
    for part in (path, *path.parents):
        if part == root:
            break
        require(not part.is_symlink() and not (hasattr(part, "is_junction") and part.is_junction()),
                f"Runtime asset uses a link/junction: {relative}")
    require(path.is_file(), f"Missing required Pages asset: {relative}")
    require(path.stat().st_size <= MAX_FILE_BYTES, f"Unexpected large Pages asset: {relative}")
    return path


def reject_undeclared_runtime_files(source: Path) -> None:
    for path in source.iterdir():
        if path.is_file() and path.suffix.lower() in {".js", ".css", ".html"}:
            require(path.name in PUBLIC_PATHS, f"Undeclared root browser asset: {path.name}")
    allowed_dirs = {
        parent.as_posix() for relative in PUBLIC_PATHS
        for parent in PurePosixPath(relative).parents if parent.as_posix() != "."
    }
    for top in ("data", "vendor"):
        for directory, dirs, files in os.walk(source / top, followlinks=False):
            base = Path(directory)
            for name in dirs:
                relative = (base / name).relative_to(source).as_posix()
                require(relative in allowed_dirs, f"Undeclared runtime directory: {relative}")
            for name in files:
                relative = (base / name).relative_to(source).as_posix()
                require(relative in PUBLIC_PATHS or relative in NON_RUNTIME_SOURCE_PATHS,
                        f"Undeclared runtime payload: {relative}")


def require_local_reference(url: str, owner: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return
    path = unquote(parsed.path)
    relative = posixpath.normpath(path.lstrip("/")) if path.startswith("/") else posixpath.normpath(
        posixpath.join(posixpath.dirname(owner), path)
    )
    if path.endswith("/"):
        relative = posixpath.join(relative, "index.html").removeprefix("./")
    require(relative in PUBLIC_PATHS, f"Browser reference has no Pages asset: {owner} -> {url}")


class AssetParser(HTMLParser):
    def __init__(self, owner: str):
        super().__init__()
        self.owner = owner

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if value and name in {"src", "href"}:
                require_local_reference(value, self.owner)


def validate_browser_references(source: Path) -> None:
    js_asset = re.compile(r'''["']((?:\./|/)?[A-Za-z0-9_./-]+\.(?:js|css)(?:\?[^"'\s]*)?)["']''')
    css_asset = re.compile(r'''url\(\s*["']?([^\s"')]+)["']?\s*\)''')
    for relative in sorted(PUBLIC_PATHS):
        path = source / relative
        if path.suffix == ".html":
            AssetParser(relative).feed(path.read_text(encoding="utf-8-sig"))
        elif path.suffix == ".js":
            for match in js_asset.finditer(path.read_text(encoding="utf-8-sig")):
                require_local_reference(match.group(1), relative)
        elif path.suffix == ".css":
            for match in css_asset.finditer(path.read_text(encoding="utf-8-sig")):
                require_local_reference(match.group(1), relative)


def read_json(source: Path, relative: str):
    return json.loads((source / relative).read_text(encoding="utf-8-sig"))


def validate_runtime_contract(source: Path) -> None:
    for relative in sorted(PUBLIC_PATHS):
        if relative.endswith((".json", ".geojson")):
            read_json(source, relative)
    config = read_json(source, "data/app_config.json")
    require(config["deploymentProfile"]["largeDataBaseUrl"] == R2_BASE, "Canonical R2 release changed.")
    require(config["normalizedCount"] == 702893 and config["mappedCount"] == 580783,
            "Production catalog counts changed.")
    canonical = config["canonicalWebArtifacts"]
    require(all(canonical.get(key) is True for key in ("enabled", "primaryCatalog", "traceRuntime", "fullDetails")),
            "Canonical runtime features were disabled.")
    for key, value in canonical.items():
        if key.endswith("Url"):
            require(value.startswith(R2_BASE + "/"), f"Unexpected canonical runtime URL: {key}")
    require(config["packedPoints"]["binaryUrl"].startswith(R2_BASE + "/"), "Packed points lost their R2 URL.")
    overlay = config["locationLabelOverlay"]
    require(overlay["enabled"] is True and overlay["entryCount"] == 68654 and overlay["reviewedCount"] == 4,
            "Reviewed location-label overlay was lost.")
    require_local_reference(overlay["gzipUrl"], "index.html")
    overlay_path = source / "data/location_label_overlay.json.gz"
    require(overlay_path.stat().st_size == overlay["gzipBytes"] and sha256_file(overlay_path) == overlay["gzipSha256"],
            "Location-label overlay differs from its integrity declaration.")
    for url in config["reports"].values():
        require(url.startswith("https://b0f0a0de.ufo-timeline.pages.dev/reports/"),
                "Immutable report pointer changed.")
    startup = config["startupProfile"]
    require(startup["enabled"] is True, "Production startup preview was disabled.")
    require_local_reference(startup["manifestUrl"], "index.html")
    for profile in read_json(source, "data/startup_profiles/manifest.json")["profiles"]:
        require_local_reference(profile["manifestUrl"], "index.html")
        manifest_path = f"data/startup_profiles/{profile['id']}/manifest.json"
        for name in read_json(source, manifest_path)["files"].values():
            require_local_reference(name, manifest_path)
    convergence_path = "data/trace_intersection_feasibility_v1/manifest.json"
    convergence = read_json(source, convergence_path)
    require(convergence["claimBoundary"]["observedTravelPaths"] is False,
            "Convergence artifacts lost their report-association claim boundary.")
    for artifact in convergence["artifacts"].values():
        require_local_reference(artifact["file"], convergence_path)
        path = source / PurePosixPath(convergence_path).parent / artifact["file"]
        require(path.stat().st_size == artifact["bytes"] and sha256_file(path) == artifact["sha256"],
                f"Convergence artifact differs from its manifest: {artifact['file']}")


def inventory_source(source: Path) -> dict:
    require(source.is_dir(), "Source root does not exist.")
    reject_undeclared_runtime_files(source)
    baseline_tree = git(source, "ls-tree", "-r", "--format=%(objectname) %(path)", BASELINE_COMMIT).decode("utf-8")
    baseline_blobs = dict(line.split(" ", 1)[::-1] for line in baseline_tree.splitlines())
    records = []
    for relative in sorted(PUBLIC_PATHS):
        path = safe_asset(source, relative)
        record = {"path": relative, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
        if relative in PRESERVED_PATHS:
            require(relative in baseline_blobs, f"Protected asset missing from baseline: {relative}")
            baseline_bytes = git(source, "cat-file", "blob", baseline_blobs[relative])
            expected = hashlib.sha256(baseline_bytes).hexdigest()
            text_asset = path.suffix in {".js", ".css", ".html", ".json", ".geojson"} or relative == "_headers"
            # Git's Windows checkout can convert LF to CRLF, notably sw.js.
            # Accept only that conversion, pin the original Git bytes, and hash
            # the actual copied bytes separately in the public inventory.
            eol_only = text_asset and path.read_bytes().replace(b"\r\n", b"\n") == baseline_bytes.replace(b"\r\n", b"\n")
            require(record["sha256"] == expected or eol_only,
                    f"Production asset changed outside interface scope: {relative}")
            record["baselineSha256"] = expected
            record["checkoutLineEndingsOnly"] = record["sha256"] != expected
        records.append(record)
    total = sum(record["bytes"] for record in records)
    require(total < MAX_TOTAL_BYTES, f"Pages candidate exceeds 35 MiB: {total} bytes.")
    validate_runtime_contract(source)
    validate_browser_references(source)
    tree = "".join(f"{item['path']}\t{item['bytes']}\t{item['sha256']}\n" for item in records).encode("utf-8")
    return {
        "schemaVersion": 1, "baselineCommit": BASELINE_COMMIT,
        "baselineDeploymentId": BASELINE_DEPLOYMENT, "sourceRoot": str(source),
        "purpose": "Complete Pages interface candidate using unchanged shared immutable R2 data",
        "retention": "Retain as current validated candidate after release; previous production is the one rollback",
        "rebuild": "Run scripts/prepare_interface_release.py from this Git revision with a fresh .tmp output",
        "fileCount": len(records), "totalBytes": total, "newFilesLargerThan100MiB": [],
        "treeHashAlgorithm": "ordinal path<TAB>bytes<TAB>sha256<LF>",
        "treeSha256": hashlib.sha256(tree).hexdigest(), "files": records,
    }


def verify_candidate(output: Path, plan: dict) -> None:
    actual = {path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()}
    require(actual == PUBLIC_PATHS, "Candidate inventory contains missing or undeclared public files.")
    for record in plan["files"]:
        path = safe_asset(output, record["path"])
        require(path.stat().st_size == record["bytes"] and sha256_file(path) == record["sha256"],
                f"Candidate differs from the approved source: {record['path']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--output", type=Path, default=Path(".tmp/interface-pages-candidate"))
    parser.add_argument("--inventory", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check-only", action="store_true", help="Validate and print the plan without writing files")
    mode.add_argument("--verify-existing", action="store_true", help="Verify the existing candidate without writing files")
    args = parser.parse_args()
    source = args.source_root.resolve()
    output = (args.output if args.output.is_absolute() else source / args.output).resolve()
    receipt = args.inventory or output.with_name(output.name + "-inventory.json")
    receipt = (receipt if receipt.is_absolute() else source / receipt).resolve()
    require(output.is_relative_to(source / ".tmp") and output != source / ".tmp",
            "Candidate must be a dedicated directory beneath this worktree's .tmp directory.")
    require(not receipt.is_relative_to(output), "Hash inventory must remain outside the public candidate.")
    plan = inventory_source(source)
    if args.verify_existing:
        require(output.is_dir(), "Candidate has not been prepared.")
        require(receipt.is_file(), "Candidate hash inventory is missing.")
        recorded = json.loads(receipt.read_text(encoding="utf-8"))
        require(recorded.get("treeSha256") == plan["treeSha256"] and recorded.get("files") == plan["files"],
                "Source or recorded inventory changed after this candidate was frozen.")
        verify_candidate(output, plan)
    elif not args.check_only:
        require(not output.exists(), "Refusing to overwrite an existing candidate; use a fresh .tmp path.")
        require(not receipt.exists(), "Refusing to overwrite an existing release inventory.")
        require(receipt.is_relative_to(source / ".tmp"), "Release inventory must remain beneath this worktree's .tmp directory.")
        output.parent.mkdir(parents=True, exist_ok=True)
        free = shutil.disk_usage(output.parent).free
        require(free > plan["totalBytes"] + 1024 * 1024, "Insufficient disk space for this small candidate.")
        if output.drive.upper() == "C:" and free >= 100 * 1024**3:
            require(free - plan["totalBytes"] - 1024 * 1024 >= 100 * 1024**3, "Candidate would cross the 100 GiB C: reserve.")
        output.mkdir()
        for record in plan["files"]:
            target = output / record["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / record["path"], target)
        verify_candidate(output, plan)
        plan["candidateRoot"] = str(output)
        plan["approximateNetDiskGrowthBytes"] = plan["totalBytes"]
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "ok": True, "mode": "check" if args.check_only else "verify" if args.verify_existing else "stage",
        "fileCount": plan["fileCount"], "totalBytes": plan["totalBytes"],
        "treeSha256": plan["treeSha256"], "candidateRoot": str(output),
        "inventory": str(receipt), "baselineDeploymentId": BASELINE_DEPLOYMENT,
    }, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReleaseError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"Interface release refused: {exc}", file=sys.stderr)
        raise SystemExit(1)
