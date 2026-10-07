"""Prepare a bounded Pages/R2 quality release, without uploading or copying the corpus.

Builder receipts are the delivery allowlist. The old canonical R2 objects keep
their original immutable URLs and hashes; only explicitly declared deltas receive
new keys. --check-only writes nothing. Actual preparation creates one small Pages
candidate and private release metadata. --verify-existing rechecks its frozen
inventory. Optional --verify-public streams the declared new public assets and
candidate assets without writing a hydrated corpus or disabling TLS validation.
--hydrate-contract consumes the small portable contract, verifies shared files,
and downloads only missing compressed objects into an explicit bounded cache.
"""
from __future__ import annotations

import argparse
import copy
from concurrent.futures import ThreadPoolExecutor, as_completed
import fnmatch
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import shutil
import sys
from typing import Any
from urllib.parse import unquote, urlsplit
import urllib.request


REPO_ROOT = Path(__file__).resolve().parent.parent
RELEASE_ID = "quality-20261007"
R2_ORIGIN = "https://pub-e9029ab2f6b448daad03d7cde7e15e64.r2.dev"
NEW_PREFIX = "releases/" + RELEASE_ID
BASE_PREFIX = "releases/coordinated-reliability-v152-20260731"
BASE_URL = R2_ORIGIN + "/" + BASE_PREFIX
RELEASE_CAP = 850 * 1024 * 1024
PAGES_CAP = 40 * 1024 * 1024
PAGES_FILE_CAP = 25 * 1024 * 1024
HARD_CAP = 1024 * 1024 * 1024
MUTABLE_SHELL = frozenset({
    "app.js", "index.html", "styles.css", "_headers", "catalog_filter_worker.js",
    "startup_profile_worker.js", "analysis_view.js", "analysis_stats.js",
    "analysis_spatial.js", "analysis_spatial_worker.js", "trace_neighborhood.js",
    "famous_case_presets.js", "data/app_config.json",
})
PRIVATE_NAMES = frozenset({"upload_manifest.json", "replication_contract.json",
                           "candidate_inventory.json", "delivery_plan.json", "quality_release_contract.json"})
CANONICAL_PAGES_METADATA = frozenset({"canonical_web_manifest.json", "event_chunk_manifest.json",
    "summary_manifest.json", "points_meta.json", "trace_segments_meta.json",
    "trace_event_index_meta.json", "trace_aggregate_bins_meta.json"})
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
PAGES_ANALYTICS_INSERTION = (b"<!-- Cloudflare Pages Analytics --><script defer src='"
    b"https://static.cloudflareinsights.com/beacon.min.js' data-cf-beacon='"
    b'{"token": "df011473b8f34ae9a926359e4a1743e6"}'
    b"'></script><!-- Cloudflare Pages Analytics -->")


class ReleaseError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReleaseError(message)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    require(isinstance(value, dict), "Expected an object: " + str(path))
    return value


def relative(value: str) -> str:
    require(isinstance(value, str) and value and "\\" not in value,
            "Public paths must use nonempty forward-slash relative paths")
    parts = PurePosixPath(value)
    require(not parts.is_absolute() and ".." not in parts.parts and "." not in parts.parts
            and not re.match(r"^[A-Za-z]:", value) and "//" not in value,
            "Unsafe relative path: " + value)
    require(parts.as_posix() == value, "Noncanonical relative path: " + value)
    return value


def checked_file(root: Path, name: str) -> Path:
    name = relative(name)
    root = root.resolve()
    path = root.joinpath(*PurePosixPath(name).parts)
    require(path.resolve().is_relative_to(root), "Input path escapes its root: " + name)
    for candidate in (path, *path.parents):
        if candidate == root:
            break
        require(not candidate.is_symlink() and not
                (hasattr(candidate, "is_junction") and candidate.is_junction()),
                "Linked input is not a frozen file: " + name)
    require(path.is_file(), "Missing declared file: " + str(path))
    return path


def file_pin(path: Path) -> dict:
    return {"bytes": path.stat().st_size, "sha256": sha(path)}


def declared_pin(path: Path, record: dict) -> dict:
    require(isinstance(record.get("bytes"), int) and record["bytes"] >= 0
            and SHA_RE.fullmatch(str(record.get("sha256", ""))) is not None,
            "Missing/invalid bytes or SHA256 declaration: " + str(path))
    require(path.stat().st_size == record["bytes"], "Declared size changed: " + str(path))
    require(sha(path) == record["sha256"], "Declared digest changed: " + str(path))
    return {"bytes": record["bytes"], "sha256": record["sha256"]}


def tree_hash(records: list[dict]) -> str:
    return hashlib.sha256("".join(
        f"{row['path']}\t{row['bytes']}\t{row['sha256']}\n"
        for row in sorted(records, key=lambda row: row["path"])).encode()).hexdigest()


def walk_urls(value: Any):
    if isinstance(value, str) and value.startswith("https://"):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from walk_urls(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_urls(child)


def declared_url(url: str, new_urls: set[str]) -> bool:
    # The product's prefer-gzip loaders request a declared .gz sibling before
    # trying the logical raw URL. This alias does not declare raw data uploaded.
    return url in new_urls or url + ".gz" in new_urls


def declared_directory(url: str, new_urls: set[str]) -> bool:
    return any(value.startswith(url.rstrip("/") + "/") for value in new_urls)


def validate_browser_references(pages: list[dict]) -> None:
    names = {row["path"] for row in pages}
    def check(owner: str, value: str) -> None:
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc or not parsed.path:
            return
        name = unquote(parsed.path)
        name = posixpath.normpath(name.lstrip("/")) if name.startswith("/") else posixpath.normpath(
            posixpath.join(posixpath.dirname(owner), name))
        if parsed.path.endswith("/"):
            name = posixpath.join(name, "index.html").removeprefix("./")
        require(name in names, "Browser asset is absent from candidate: " + owner + " -> " + value)
    class BrowserParser(HTMLParser):
        def __init__(self, owner: str):
            super().__init__()
            self.owner = owner
        def handle_starttag(self, tag: str, attrs: list) -> None:
            for key, value in attrs:
                if value and key in {"href", "src"}:
                    check(self.owner, value)
    js_asset = re.compile(r'''["']((?:\./|/)?[A-Za-z0-9_./-]+\.(?:js|css)(?:\?[^"'\s]*)?)["']''')
    css_asset = re.compile(r'''url\(\s*["']?([^\s"')]+)["']?\s*\)''')
    for row in pages:
        suffix = PurePosixPath(row["path"]).suffix
        if suffix not in {".html", ".js", ".css"}:
            continue
        text = Path(row["source"]).read_text(encoding="utf-8-sig")
        if suffix == ".html":
            BrowserParser(row["path"]).feed(text)
        elif suffix == ".js":
            for match in js_asset.finditer(text):
                check(row["path"], match.group(1))
        else:
            for match in css_asset.finditer(text):
                check(row["path"], match.group(1))
def normalize_receipt(path: Path, lane: str, release_root: Path,
                      quality_sha: str) -> tuple[list[dict], dict]:
    receipt = load(path)
    require(receipt.get("release_id", receipt.get("releaseId", RELEASE_ID)) == RELEASE_ID,
            "Builder receipt belongs to another release")
    reviewed = receipt.get("quality_manifest_sha256", receipt.get("qualityManifestSha256",
                           receipt.get("quality_manifest", {}).get("sha256")))
    require(reviewed == quality_sha, "Builder receipt has a stale/unpinned quality view: " + str(path))
    lane_root = release_root / lane
    require(lane_root.is_dir(), "Missing delta lane root: " + str(lane_root))
    raw_records = receipt.get("files")
    require(isinstance(raw_records, list) and raw_records, "Builder has no declared files: " + str(path))
    records = []
    names = set()
    for record in raw_records:
        require(isinstance(record, dict), "Builder file entry is not an object")
        name = relative(str(record.get("path", "")))
        require(name not in names, "Duplicate builder path: " + name)
        names.add(name)
        source = checked_file(lane_root, name)
        pin = declared_pin(source, record)
        delivery = record.get("delivery")
        require(delivery in {"pages", "r2", "local", "retained_analysis_receipt"},
                "Missing explicit delivery for: " + name)
        item = {"lane": lane, "source": str(source), "path": name, "delivery": delivery, **pin}
        if delivery == "pages":
            item["pages_path"] = relative(str(record.get("pages_path", record.get("publicPath", record.get("public_path", "")))))
            require(item["bytes"] < PAGES_FILE_CAP, "Pages payload exceeds file cap")
        elif delivery == "r2":
            key = relative(str(record.get("key", record.get("immutableKey", record.get("public_key", record.get("r2_key", NEW_PREFIX + "/" + lane + "/" + name))))))
            require(key == NEW_PREFIX + "/" + lane + "/" + name,
                    "R2 key does not match the declared lane/path: " + key)
            url = record.get("url", record.get("public_url", R2_ORIGIN + "/" + key))
            require(url == R2_ORIGIN + "/" + key, "Unexpected immutable R2 URL: " + str(url))
            item.update(key=key, url=url, content_type=record.get("content_type", "application/gzip" if name.endswith(".gz") else "application/json"),
                        cache_control="public, max-age=31536000, immutable")
        if record.get("logical_path"):
            item["logical_path"] = relative(record["logical_path"])
        elif delivery == "r2" and lane == "map_delta":
            item["logical_path"] = "data/canonical_web/" + name
        elif delivery == "r2" and lane == "analysis_delta":
            item["logical_path"] = "data/" + name
        records.append(item)
        # Tiny canonical metadata is also available at the original Pages path.
        # Its R2 URL still names the declared immutable new object. This explicit
        # allowlist cannot put map binaries or source chunks into Pages.
        if lane == "map_delta" and delivery == "r2" and name in CANONICAL_PAGES_METADATA:
            records.append({"lane": lane, "source": str(source), "path": name,
                            "delivery": "pages", "pages_path": "data/canonical_web/" + name,
                            "derived_delivery_role": "canonical_metadata_pages_sibling", **pin})
    return records, {"lane": lane, "path": str(path.resolve()), **file_pin(path),
                     "declared_files": len(records)}


def count_release_tree(root: Path) -> tuple[int, list[dict]]:
    total = 0
    larger = []
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs:
            path = Path(directory) / name
            require(not path.is_symlink() and not (hasattr(path, "is_junction") and path.is_junction()),
                    "Release tree contains a linked directory")
        for name in files:
            path = Path(directory) / name
            require(not path.is_symlink(), "Release tree contains a linked file")
            size = path.stat().st_size
            total += size
            if size > 100 * 1024 * 1024:
                larger.append({"path": str(path), "bytes": size})
    require(total < RELEASE_CAP, "Main release tree exceeds the 850 MiB cap")
    return total, larger


def config_from_map_receipt(existing: dict, receipt: dict, quality: dict,
                            quality_sha: str) -> dict:
    require(receipt["qualityManifestSha256"] == quality_sha,
            "Config builder received a stale map receipt")
    require(receipt["baseManifestSha256"] == quality["base"]["manifest_sha256"],
            "Config builder received another source base")
    result = copy.deepcopy(existing)
    prefix = R2_ORIGIN + "/" + NEW_PREFIX + "/map_delta/"
    counts = receipt["counts"]
    result["normalizedCount"] = counts["events"]
    result["mappedCount"] = counts["mapped_events"]
    result["unresolvedCount"] = counts["unmapped_events"]
    result["precisionBreakdown"] = copy.deepcopy(counts["location_precision_counts"])
    result["staticAssetVersion"] = "quality20261007"
    result["deploymentProfile"]["largeDataBaseUrl"] = BASE_URL
    packed = result["packedPoints"]
    packed.update(enabled=True, rowCount=counts["mapped_events"],
                  binaryUrl=prefix + "points.bin", metadataUrl=prefix + "points_meta.json")
    canonical = result["canonicalWebArtifacts"]
    canonical.update(enabled=True, primaryCatalog=True, fullDetails=True, traceRuntime=True,
        manifestUrl=prefix + "canonical_web_manifest.json",
        chunkManifestUrl=prefix + "event_chunk_manifest.json",
        eventChunksBaseUrl=BASE_URL + "/data/canonical_web/event_chunks/",
        summaryManifestUrl=prefix + "summary_manifest.json",
        summaryShardsBaseUrl=prefix + "summary_shards/")
    overlay = receipt["detailOverlay"]
    result["detailQualityOverlay"] = {"enabled": True, "gzipUrl": "./" + overlay["publicPath"],
        "gzipSha256": overlay["sha256"], "patchCount": overlay["patchCount"],
        "baseManifestSha256": overlay["baseManifestSha256"],
        "qualityManifestSha256": overlay["qualityManifestSha256"]}
    result["dataQualityRelease"] = {"id": RELEASE_ID, "qualityManifestSha256": quality_sha,
        "baseManifestSha256": receipt["baseManifestSha256"],
        "effectiveMappedCount": counts["mapped_events"], "effectiveUnmappedCount": counts["unmapped_events"]}
    return result


def runtime_manifest_objects(pages: list[dict]) -> list[dict]:
    """Read explicit optional-layer pins, including preserved original releases."""
    objects = {}
    def visit(value: Any, base: str, owner: str):
        if isinstance(value, list):
            for child in value:
                visit(child, base, owner)
        elif isinstance(value, dict):
            pairs = (("gzipFile", "gzipBytes", "gzipSha256"),)
            if not all(k in value for k in pairs[0]):
                pairs += (("file", "bytes", "sha256"), ("path", "bytes", "sha256"))
            for file_key, bytes_key, hash_key in pairs:
                if not all(key in value for key in (file_key, bytes_key, hash_key)):
                    continue
                name = value[file_key]
                require(isinstance(name, str), "Optional runtime asset path is not text")
                url = name if name.startswith("https://") else base.rstrip("/") + "/" + relative(name)
                require(url.startswith(R2_ORIGIN + "/releases/") and isinstance(value[bytes_key], int)
                        and value[bytes_key] >= 0 and SHA_RE.fullmatch(str(value[hash_key])),
                        "Optional runtime object lacks an immutable URL/byte/hash pin: " + owner)
                item = {"url": url, "bytes": value[bytes_key], "sha256": value[hash_key],
                        "manifest_path": owner}
                require(url not in objects or all(objects[url][key] == item[key] for key in ("bytes", "sha256")),
                        "Conflicting optional runtime URL pins: " + url)
                objects[url] = item
            for child in value.values():
                if isinstance(child, (dict, list)):
                    visit(child, base, owner)
    for row in pages:
        if PurePosixPath(row["path"]).name != "manifest.json":
            continue
        manifest = load(Path(row["source"]))
        base = manifest.get("assetBaseUrl")
        if not isinstance(base, str) or not base.startswith(R2_ORIGIN + "/releases/"):
            continue
        for key in ("artifacts", "points", "details", "catalog", "payloads"):
            if key in manifest:
                visit(manifest[key], base, row["path"])
    return list(objects.values())


def modern_contract(plan: dict) -> dict:
    registry = {}
    # Original packed points/summaries are superseded. Only source detail chunks
    # remain active on that release; carrying every historical object would make
    # reproduction download unused catalog projections.
    base_details = [row for row in plan["inherited_objects"]
                    if row["path"].startswith("data/canonical_web/event_chunks/")]
    for row in base_details + plan["uploads"] + plan["optional_runtime_objects"]:
        item = {key: row[key] for key in ("url", "bytes", "sha256")}
        require(item["url"] not in registry or registry[item["url"]] == item,
                "Conflicting physical runtime object pins")
        registry[item["url"]] = item
    return {"schema": "ufo-runtime-replication-v1", "release_id": RELEASE_ID,
        "quality_manifest_sha256": plan["quality_manifest"]["sha256"],
        "builder_receipts": [{key: row[key] for key in ("lane", "bytes", "sha256")}
                             for row in plan["builder_receipts"]],
        "pages": [{key: row[key] for key in ("path", "bytes", "sha256")} for row in plan["pages"]],
        "pages_tree_sha256": plan["pages_tree_sha256"],
        "runtime_objects": sorted(registry.values(), key=lambda row: row["url"]),
        "runtime_object_count": len(registry), "runtime_object_bytes": sum(row["bytes"] for row in registry.values()),
        "cache_policy": plan["cache_policy_coverage"], "counts": plan["config"],
        "provider_html_transformation": {"provider": "Cloudflare Pages Analytics", "inserted_bytes": 214,
            "token": "df011473b8f34ae9a926359e4a1743e6", "source_inventory_hashes": "Untransformed Git/Pages source bytes",
            "public_verification": "Allow exactly one fixed script/comment envelope immediately before </body>; strip only that envelope, then require exact source byte count/hash. All other assets require exact physical bytes."},
        "hydration": {"mode": "shared immutable files plus streaming verification",
            "policy": "Reuse locally pinned originals; download only missing declared objects to an explicitly supplied cache. Never expand gzip/copy complete corpus or use legacy campaign paths.",
            "command": "python scripts/prepare_quality_release.py --hydrate-contract <this file> --hydrate-cache <explicit cache directory> --shared-base-root <existing canonical_web root> --shared-release-root <existing quality-20261007 root>",
            "check_command": "python scripts/prepare_quality_release.py --hydrate-contract <this file> --hydrate-cache <explicit cache directory> --shared-base-root <existing canonical_web root> --shared-release-root <existing quality-20261007 root> --verify-cache --verify-pages-root <Git checkout root>",
            "verification": "Each physical object has an explicit immutable URL, byte count and SHA256. Four streams verify new assets at preview; final production Pages-only check reuses that immutable receipt."}}


def immutable_key(url: str) -> str:
    parsed = urlsplit(url)
    require(parsed.scheme == "https" and parsed.netloc == urlsplit(R2_ORIGIN).netloc
            and not parsed.query and not parsed.fragment and not parsed.username
            and not parsed.password and parsed.path.startswith("/releases/"),
            "Runtime object URL is not on the pinned immutable R2 origin")
    key = relative(parsed.path.removeprefix("/"))
    require(unquote(key) == key, "Encoded runtime object keys are prohibited")
    return key


def validate_modern_contract(contract: dict) -> None:
    require(contract.get("schema") == "ufo-runtime-replication-v1"
            and contract.get("release_id") == RELEASE_ID
            and SHA_RE.fullmatch(str(contract.get("quality_manifest_sha256", ""))),
            "Unsupported or unpinned portable release contract")
    pages = contract.get("pages")
    objects = contract.get("runtime_objects")
    require(isinstance(pages, list) and pages and isinstance(objects, list) and objects,
            "Portable contract lacks Pages/runtime inventories")
    for row in pages + objects:
        require(isinstance(row.get("bytes"), int) and not isinstance(row["bytes"], bool)
                and row["bytes"] >= 0 and SHA_RE.fullmatch(str(row.get("sha256", ""))),
                "Portable contract has an invalid object byte/hash pin")
    require(len({relative(row["path"]) for row in pages}) == len(pages)
            and tree_hash(pages) == contract["pages_tree_sha256"],
            "Portable Pages inventory is duplicated or stale")
    require(len({immutable_key(row["url"]) for row in objects}) == len(objects),
            "Portable runtime inventory has duplicate objects")
    require(contract["runtime_object_count"] == len(objects)
            and contract["runtime_object_bytes"] == sum(row["bytes"] for row in objects),
            "Portable runtime census differs from its pins")
    require(sum(row["bytes"] for row in pages) < PAGES_CAP
            and contract["runtime_object_bytes"] + sum(row["bytes"] for row in pages) < HARD_CAP,
            "Portable runtime plus Pages exceeds the bounded 1 GiB layout")
    by_hash = {}
    for row in objects:
        require(row["sha256"] not in by_hash or by_hash[row["sha256"]] == row["bytes"],
                "One cache digest was declared with conflicting lengths")
        by_hash[row["sha256"]] = row["bytes"]


def write_modern_contract(path: Path, plan: dict) -> dict:
    contract = modern_contract(plan)
    validate_modern_contract(contract)
    path = path.resolve()
    candidate = Path(plan["candidate_root"]).resolve()
    require(not path.is_relative_to(candidate), "Portable contract must stay outside Pages")
    require(not path.exists() or load(path) == contract,
            "Refusing to overwrite another portable contract")
    path.parent.mkdir(parents=True, exist_ok=True)
    write(path, contract)
    return {"path": str(path), **file_pin(path), "runtime_objects": contract["runtime_object_count"],
            "runtime_bytes": contract["runtime_object_bytes"], "contains_machine_paths": False}


def hydrate_contract(args: argparse.Namespace) -> dict:
    """No decompression, corpus extraction, overwrite, or cloud mutation."""
    path = args.hydrate_contract.resolve()
    contract = load(path)
    validate_modern_contract(contract)
    require(args.hydrate_cache is not None, "Hydration requires an explicit cache directory")
    cache = args.hydrate_cache.resolve()
    for parent in (args.shared_base_root, args.shared_release_root, args.shared_r2_root,
                   args.verify_pages_root):
        if parent:
            require(not cache.is_relative_to(parent.resolve()) and not parent.resolve().is_relative_to(cache),
                    "Cache must be separate from protected shared/Page roots")
    if args.verify_pages_root:
        for row in contract["pages"]:
            declared_pin(checked_file(args.verify_pages_root, row["path"]), row)
    rows = []
    checked_hashes = {}
    for row in contract["runtime_objects"]:
        key = immutable_key(row["url"])
        locations = []
        if args.shared_r2_root:
            locations.append((args.shared_r2_root, key))
        if args.shared_base_root and key.startswith(BASE_PREFIX + "/data/canonical_web/"):
            locations.append((args.shared_base_root, key.removeprefix(BASE_PREFIX + "/data/canonical_web/")))
        if args.shared_release_root and key.startswith(NEW_PREFIX + "/"):
            locations.append((args.shared_release_root, key.removeprefix(NEW_PREFIX + "/")))
        local = None
        role = None
        for root, name in locations:
            if root.joinpath(*PurePosixPath(name).parts).exists():
                local = checked_file(root, name)
                declared_pin(local, row)
                role = "shared_verified"
                break
        if local is None:
            name = "objects/" + row["sha256"]
            target = cache.joinpath(*PurePosixPath(name).parts)
            if target.exists():
                local = checked_file(cache, name)
                declared_pin(local, row)
                role = "cache_verified"
            else:
                require(not args.verify_cache, "Required runtime object is absent: " + row["url"])
                local = target
                role = "download_required"
        if row["sha256"] in checked_hashes:
            require(checked_hashes[row["sha256"]]["bytes"] == row["bytes"], "Cache digest size conflict")
            if checked_hashes[row["sha256"]]["role"] == "download_required" and role != "download_required":
                checked_hashes[row["sha256"]] = {**row, "local": str(local), "role": role}
        else:
            checked_hashes[row["sha256"]] = {**row, "local": str(local), "role": role}
        rows.append({**row, "local": str(local), "role": role})
    for row in rows:
        if row["role"] == "download_required" and checked_hashes[row["sha256"]]["role"] != "download_required":
            row.update({key: checked_hashes[row["sha256"]][key] for key in ("local", "role")})
    downloads = [row for row in checked_hashes.values() if row["role"] == "download_required"]
    growth = sum(row["bytes"] for row in downloads) + max(65536, len(json.dumps(rows)) * 2)
    require(growth < HARD_CAP, "Hydration exceeds the hard 1 GiB no-copy cap")
    parent = cache
    while not parent.exists():
        parent = parent.parent
    require(not parent.is_symlink() and not (hasattr(parent, "is_junction") and parent.is_junction()),
            "Cache destination traverses a link")
    free = shutil.disk_usage(parent).free
    require(free > growth + 1024 * 1024, "Insufficient hydration storage")
    if parent.drive.upper() == "C:":
        require((free >= 100 * 1024**3 and free - growth >= 100 * 1024**3)
                or (free < 100 * 1024**3 and growth <= 100 * 1024 * 1024),
                "Hydration violates the C: storage reserve")
    if not args.check_only and not args.verify_cache:
        cache.mkdir(parents=True, exist_ok=True)
        objects_dir = cache / "objects"
        objects_dir.mkdir(exist_ok=True)
        require(not objects_dir.is_symlink() and not (hasattr(objects_dir, "is_junction") and objects_dir.is_junction()),
                "Cache objects directory must not be linked")
        def download(row: dict) -> None:
            target = Path(row["local"])
            temporary = target.with_name(target.name + ".part")
            require(not target.exists() and not temporary.exists(), "Refusing to overwrite a cache/partial object")
            digest, actual = hashlib.sha256(), 0
            request = urllib.request.Request(row["url"], headers={"Accept-Encoding": "identity",
                "User-Agent": "UFO-Timeline-pinned-runtime-hydration"})
            try:
                with temporary.open("xb") as output, urllib.request.urlopen(request, timeout=args.timeout) as response:
                    require(response.status == 200 and immutable_key(response.geturl()) == immutable_key(row["url"]),
                            "Hydration response moved outside the declared immutable object")
                    require(response.headers.get("Content-Encoding", "identity") in {"", "identity"},
                            "Hydration requires exact physical bytes")
                    while block := response.read(1024 * 1024):
                        actual += len(block)
                        require(actual <= row["bytes"], "Hydration object exceeds its declared size")
                        digest.update(block)
                        output.write(block)
                require(actual == row["bytes"] and digest.hexdigest() == row["sha256"],
                        "Hydration object differs from its declared bytes/hash")
                # Linking fails if another file already occupies the target;
                # only our temporary download is removed afterward.
                os.link(temporary, target)
            finally:
                if temporary.exists():
                    temporary.unlink()
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(download, row) for row in downloads]
            for index, future in enumerate(as_completed(futures), 1):
                future.result()
                if index % 20 == 0 or index == len(futures):
                    print(f"Hydrated {index}/{len(futures)} missing pinned objects", file=sys.stderr, flush=True)
        for row in rows:
            if row["role"] == "download_required":
                row["role"] = "downloaded_verified"
        write(cache / "runtime_index.json", {"schema": "ufo-runtime-cache-index-v1",
            "contract_sha256": sha(path), "objects": rows,
            "purpose": "Verified compressed runtime objects; shared originals remain at their existing paths",
            "rebuild": "Repeat the portable contract hydration command; --verify-cache is read-only",
            "retention": "Explicit reproduction cache; no archive expansion. Review literal cached-object paths before removal."})
    return {"passed": True, "mode": "hydrate_check_only" if args.check_only else "verify_cache" if args.verify_cache else "hydrated",
            "contract_sha256": sha(path), "runtime_objects": len(rows),
            "shared_objects_verified": sum(row["role"] == "shared_verified" for row in rows),
            "existing_cache_objects_verified": sum(row["role"] == "cache_verified" for row in rows),
            "missing_unique_objects": len(downloads), "download_bytes": sum(row["bytes"] for row in downloads),
            "pages_verified": len(contract["pages"]) if args.verify_pages_root else 0,
            "cache_root": str(cache), "parallel_streams": 4, "gzip_expanded": False,
            "canonical_corpus_copied": False, "cloud_mutations_performed": False}


def configure_source(args: argparse.Namespace, dry_run: bool) -> dict:
    source = args.source_root.resolve()
    root = args.release_root.resolve()
    quality = load(args.quality_manifest.resolve())
    quality_sha = sha(args.quality_manifest.resolve())
    map_path = (args.map_receipt or root / "map_delta/map_release_receipt.json").resolve()
    analysis_path = (args.analysis_receipt or root / "analysis_delta/analysis_release_receipt.json").resolve()
    records = []
    for path, lane in ((map_path, "map_delta"), (analysis_path, "analysis_delta")):
        rows, _ = normalize_receipt(path, lane, root, quality_sha)
        records.extend(rows)
    pages = [row for row in records if row["delivery"] == "pages"]
    require(len({row["pages_path"] for row in pages}) == len(pages), "Conflicting source metadata paths")
    config_path = checked_file(source, "data/app_config.json")
    result = config_from_map_receipt(load(config_path), load(map_path), quality, quality_sha)
    edits = [{"path": "data/app_config.json", "purpose": "Reviewed count/URL/detail guard config"}]
    for row in pages:
        name = relative(row["pages_path"])
        target = source.joinpath(*PurePosixPath(name).parts)
        require(target.resolve().is_relative_to(source), "Source metadata destination escapes product checkout")
        for parent in (target.parent, *target.parents):
            if parent == source:
                break
            require(not parent.is_symlink() and not (hasattr(parent, "is_junction") and parent.is_junction()),
                    "Source metadata destination traverses a link")
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(row["source"], target)
        edits.append({"path": name, "bytes": row["bytes"], "sha256": row["sha256"]})
    if not dry_run:
        write(config_path, result)
    return {"passed": True, "mode": "configure_source_dry_run" if dry_run else "source_configured",
            "quality_manifest_sha256": quality_sha, "normalized_count": result["normalizedCount"],
            "mapped_count": result["mappedCount"], "detail_patch_count": result["detailQualityOverlay"]["patchCount"],
            "updated_pages_source_files": edits, "runtime_config": result,
            "cloud_mutations_performed": False, "corpus_copied": False}


def cache_coverage(pages: list[dict], changed: list[str]) -> dict:
    record = next((row for row in pages if row["path"] == "_headers"), None)
    require(record is not None, "Pages cache policy missing")
    rules = []
    pattern = None
    for raw in Path(record["source"]).read_text(encoding="utf8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if not raw[0].isspace():
            pattern = raw.strip()
        elif pattern and raw.strip().casefold().startswith("cache-control:"):
            rules.append((pattern, raw.strip().split(":", 1)[1].strip()))
    coverage = {}
    for name in changed:
        if name == "_headers":
            continue
        controls = [value for pattern, value in rules if fnmatch.fnmatchcase("/" + name, pattern)]
        require(controls, "Changed Pages asset has no cache policy: " + name)
        require(any(re.search(r"(?:^|,)\s*(?:no-store|no-cache|max-age=0)(?:\s*,|$)", value)
                    for value in controls), "Changed Pages asset is not revalidated: " + name)
        coverage[name] = controls
    return {"changed_pages_assets": coverage,
            "new_r2_assets": "Every upload uses public,max-age=31536000,immutable at a new versioned key"}


def validate_config(config: dict, quality: dict, new_urls: set[str],
                    map_receipt: dict, pages: list[dict], deltas: list[dict]) -> None:
    require(config.get("deploymentProfile", {}).get("largeDataBaseUrl") == BASE_URL,
            "Base canonical R2 pointer must remain immutable and unchanged")
    require(config.get("normalizedCount") == 702893, "Record count changed")
    # Quality census may be pinned in a separate receipt; builder config counts
    # are still independently checked against the release metadata below.
    require(isinstance(config.get("mappedCount"), int) and 580783 <= config["mappedCount"] <= 702893,
            "Invalid effective mapped count")
    canonical = config.get("canonicalWebArtifacts", {})
    require(canonical.get("enabled") and canonical.get("primaryCatalog") and canonical.get("fullDetails"),
            "Canonical catalog/full details disabled")
    require(canonical.get("eventChunksBaseUrl") == BASE_URL + "/data/canonical_web/event_chunks/",
            "Full source detail chunk base must be inherited unchanged")
    require(config.get("locationLabelOverlay", {}).get("entryCount") == 68654,
            "Existing location-label overlay lost")
    for url in walk_urls(config):
        if url.startswith(R2_ORIGIN + "/" + NEW_PREFIX + "/"):
            require(declared_url(url, new_urls) or declared_directory(url, new_urls),
                    "Config references undeclared new R2 data: " + url)
    require(quality.get("base_catalog_mutated") is False,
            "Expected an immutable-base sparse quality view")
    map_canonical = next((row for row in deltas if row["lane"] == "map_delta"
                          and row["path"] == "canonical_web_manifest.json"), None)
    require(map_canonical is not None, "Missing corrected canonical metadata")
    counts = load(Path(map_canonical["source"]))["counts"]
    require(counts["events"] == config["normalizedCount"] and counts["mapped_events"] == config["mappedCount"],
            "Config does not agree with corrected canonical census")
    packed = config.get("packedPoints", {})
    require(packed.get("rowCount") == config["mappedCount"], "Packed point count does not match effective catalog")
    for value in (packed.get("binaryUrl"), packed.get("metadataUrl"), canonical.get("manifestUrl"),
                  canonical.get("summaryManifestUrl")):
        require(isinstance(value, str) and declared_url(value, new_urls),
                "Corrected runtime points/summary metadata still names undeclared or old data")
    summary_base = canonical.get("summaryShardsBaseUrl", "")
    require(summary_base.startswith(R2_ORIGIN + "/" + NEW_PREFIX + "/map_delta/")
            and summary_base.endswith("/") and any(url.startswith(summary_base) for url in new_urls),
            "Corrected summary shard base missing")
    overlay = map_receipt.get("detailOverlay")
    require(isinstance(overlay, dict), "Map builder must pin the detail overlay")
    overlay_config = config.get("detailQualityOverlay", {})
    require(overlay_config.get("enabled") is True, "Corrected source detail overlay disabled")
    require(overlay_config.get("gzipSha256") == overlay["sha256"]
            and overlay_config.get("patchCount") == overlay["patchCount"]
            and overlay_config.get("baseManifestSha256") == overlay["baseManifestSha256"]
            and overlay_config.get("qualityManifestSha256") == overlay["qualityManifestSha256"],
            "Detail overlay config differs from its reviewed compressed payload")
    require(overlay_config["baseManifestSha256"] == quality["base"]["manifest_sha256"],
            "Detail overlay names another canonical base")
    require(overlay_config["qualityManifestSha256"] == map_receipt.get("quality_manifest_sha256", map_receipt.get("qualityManifestSha256")),
            "Detail overlay quality contract is stale")
    expected_path = relative(overlay["publicPath"])
    require(overlay_config.get("gzipUrl") in {"./" + expected_path, "/" + expected_path, expected_path},
            "Detail overlay config path differs from its declared Pages path")
    payload = next((row for row in pages if row["path"] == expected_path), None)
    require(payload and payload["sha256"] == overlay["sha256"] and payload["bytes"] == overlay["bytes"],
            "Detail overlay is absent from the actual Pages inventory")


def make_plan(args: argparse.Namespace) -> dict:
    source = args.source_root.resolve()
    baseline_path = (args.baseline_inventory or source / ".tmp/interface-pages-inventory.json").resolve()
    baseline = load(baseline_path)
    quality_path = args.quality_manifest.resolve()
    quality = load(quality_path)
    quality_sha = sha(quality_path)
    release_root = args.release_root.resolve()
    require(release_root.name == RELEASE_ID and release_root.parent.name == "releases",
            "Use the dedicated releases/quality-20261007 tree")
    require(release_root.is_dir(), "Release tree does not exist")
    release_bytes, larger = count_release_tree(release_root)
    output = (args.output or source / ".tmp/quality-20261007-pages").resolve()
    metadata = (args.metadata_root or release_root / "release_metadata").resolve()
    require(output.is_relative_to(source / ".tmp") and output != source / ".tmp",
            "Pages candidate must be beneath the product worktree .tmp")
    require(metadata.is_relative_to(release_root) and metadata != release_root
            and not metadata.is_relative_to(output), "Metadata must stay private beneath release root")
    inherited_path = args.base_contract.resolve()
    inherited = load(inherited_path)
    require(inherited["r2"]["base_url"] == BASE_URL and inherited["r2"]["key_prefix"] == BASE_PREFIX,
            "Inherited canonical contract does not identify the original R2 release")
    base_files = inherited["r2"]["files"]
    require(len(base_files) == inherited["r2"]["file_count"] and base_files,
            "Inherited R2 contract has missing objects")
    require(sum(x["bytes"] for x in base_files) == inherited["r2"]["total_bytes"]
            and tree_hash(base_files) == inherited["r2"]["tree_sha256"],
            "Inherited R2 pin census/tree digest does not agree")
    require(all(row["url"].startswith(BASE_URL + "/") and SHA_RE.fullmatch(row["sha256"])
                for row in base_files), "Inherited R2 objects are not pinned to the base release")
    receipts = [(args.map_receipt or release_root / "map_delta/map_release_receipt.json", "map_delta"),
                (args.analysis_receipt or release_root / "analysis_delta/analysis_release_receipt.json", "analysis_delta")]
    if args.detail_receipt:
        receipts.append((args.detail_receipt, "detail_overlay"))
    deltas = []
    receipt_pins = []
    for path, lane in receipts:
        require(path is not None, "A declared builder receipt is required for: " + lane)
        rows, pin = normalize_receipt(path.resolve(), lane, release_root, quality_sha)
        deltas.extend(rows)
        receipt_pins.append(pin)
    uploads = [row for row in deltas if row["delivery"] == "r2"]
    require(len({row["key"] for row in uploads}) == len(uploads), "Conflicting upload keys")
    pages_delta = [row for row in deltas if row["delivery"] == "pages"]
    require(len({row["pages_path"] for row in pages_delta}) == len(pages_delta), "Conflicting Pages delta paths")
    overrides = {row["pages_path"]: row for row in pages_delta}
    extras = {relative(name) for name in args.extra_pages_path}
    require(not extras & PRIVATE_NAMES, "Private release metadata cannot be a browser asset")
    baseline_files = baseline.get("files")
    require(isinstance(baseline_files, list) and len(baseline_files) == baseline["fileCount"],
            "Baseline candidate inventory count is inconsistent")
    require(tree_hash(baseline_files) == baseline["treeSha256"], "Baseline inventory digest is inconsistent")
    old_files = {row["path"]: row for row in baseline_files}
    require(len(old_files) == len(baseline_files), "Duplicate baseline Pages paths")
    pages = []
    for name in sorted(set(old_files) | set(overrides) | extras):
        relative(name)
        require(PurePosixPath(name).name not in PRIVATE_NAMES, "Private manifest leaked to Pages")
        if name in overrides:
            row = overrides[name]
            path = Path(row["source"])
            pin = {k: row[k] for k in ("bytes", "sha256")}
            kind = "declared_delta_metadata"
        else:
            path = checked_file(source, name)
            pin = file_pin(path)
            kind = "explicit_extra_browser_asset" if name in extras else "inherited_product_asset"
            if name in old_files and name not in MUTABLE_SHELL:
                expected = old_files[name]
                require(pin == {k: expected[k] for k in ("bytes", "sha256")},
                        "Preserved Pages asset changed outside declared scope: " + name)
        require(pin["bytes"] < PAGES_FILE_CAP, "Pages file exceeds the 25 MiB cap: " + name)
        pages.append({"path": name, "source": str(path), "kind": kind, **pin})
    require(sum(row["bytes"] for row in pages) < PAGES_CAP, "Pages candidate exceeds the 40 MiB cap")
    config_row = next(row for row in pages if row["path"] == "data/app_config.json")
    config = load(Path(config_row["source"]))
    new_urls = {row["url"] for row in uploads}
    validate_config(config, quality, new_urls, load(receipts[0][0].resolve()), pages, deltas)
    validate_browser_references(pages)
    # Pin every manifest URL that names a new quality asset, while allowing
    # unchanged explicitly inherited URLs to remain on their historical prefix.
    for row in pages:
        if PurePosixPath(row["path"]).name != "manifest.json":
            continue
        data = load(Path(row["source"]))
        for url in walk_urls(data):
            if url.startswith(R2_ORIGIN + "/" + NEW_PREFIX + "/"):
                require(declared_url(url, new_urls) or declared_directory(url, new_urls),
                        "Pages manifest references undeclared new R2 object: " + url)
    changed = [row["path"] for row in pages if row["path"] not in old_files
               or row["sha256"] != old_files[row["path"]]["sha256"]]
    caches = cache_coverage(pages, changed)
    base_by_logical = {row["path"]: dict(row, inherited=True) for row in base_files}
    for row in uploads:
        logical = row.get("logical_path")
        if logical:
            base_by_logical[logical] = {k: row[k] for k in ("bytes", "sha256", "url")} | {"path": logical, "inherited": False}
    plan = {"schema_version": 1, "release_id": RELEASE_ID, "source_root": str(source),
            "candidate_root": str(output), "metadata_root": str(metadata), "release_root": str(release_root),
            "purpose": "Bounded reviewed quality delta plus existing product assets; canonical source corpus remains shared and immutable",
            "quality_manifest": {"path": str(quality_path), **file_pin(quality_path)},
            "baseline_pages_inventory": {"path": str(baseline_path), **file_pin(baseline_path)},
            "inherited_r2_contract": {"path": str(inherited_path), **file_pin(inherited_path),
                                      "objects": len(base_files), "total_bytes": inherited["r2"]["total_bytes"],
                                      "tree_sha256": inherited["r2"]["tree_sha256"], "source_bytes_rehashed": False},
            "builder_receipts": receipt_pins, "pages": pages, "pages_tree_sha256": tree_hash(pages),
            "optional_runtime_objects": runtime_manifest_objects(pages),
            "pages_total_bytes": sum(row["bytes"] for row in pages), "changed_pages_paths": changed,
            "uploads": uploads, "local_verification_only_files": [row for row in deltas if row["delivery"] in {"local", "retained_analysis_receipt"}],
            "upload_total_bytes": sum(row["bytes"] for row in uploads),
            "upload_key_prefix": NEW_PREFIX, "new_immutable_urls": sorted(new_urls),
            "effective_delivery": sorted(base_by_logical.values(), key=lambda row: row["path"]),
            "inherited_objects": base_files,
            "config": {"normalized_count": config["normalizedCount"], "mapped_count": config["mappedCount"],
                       "sha256": config_row["sha256"]},
            "cache_policy_coverage": caches,
            "release_tree_bytes_before_preparation": release_bytes,
            "release_tree_cap_bytes": RELEASE_CAP, "pages_cap_bytes": PAGES_CAP,
            "files_larger_than_100MiB": larger, "canonical_corpus_copied": False,
            "cloud_mutations_performed": False, "retention": {"new_canonical_candidate": str(output),
                 "new_canonical_release_metadata": str(metadata),
                 "retained_rollback_deployment": "78cc3660-5750-4685-a095-fee6dce37fbf",
                 "superseded_candidate": baseline.get("candidateRoot"),
                 "superseded_cleanup": "No automatic deletion; obsolete staging requires explicit reviewed literal allowlist after successful deployment."}}
    return plan


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf8")


def verify_candidate(plan: dict) -> None:
    root = Path(plan["candidate_root"])
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    require(actual == {row["path"] for row in plan["pages"]}, "Candidate has missing or undeclared files")
    for row in plan["pages"]:
        declared_pin(checked_file(root, row["path"]), row)


def prepare(plan: dict) -> None:
    root = Path(plan["candidate_root"])
    metadata = Path(plan["metadata_root"])
    require(not root.exists(), "Refusing to replace an existing Pages candidate")
    require(not metadata.exists(), "Refusing to replace frozen release metadata")
    serialized = json.dumps(plan, ensure_ascii=False, indent=2).encode()
    metadata_budget = max(len(serialized) * 4 + 65536, 1024 * 1024)
    require(plan["release_tree_bytes_before_preparation"] + metadata_budget < RELEASE_CAP,
            "Release metadata would exceed the 850 MiB release cap")
    expected_growth = plan["pages_total_bytes"] + metadata_budget
    require(expected_growth < HARD_CAP, "Preparation exceeds the hard 1 GiB no-copy cap")
    for parent in (root.parent, metadata.parent):
        parent.mkdir(parents=True, exist_ok=True)
        free = shutil.disk_usage(parent).free
        require(free >= expected_growth + 1024 * 1024, "Insufficient free storage")
        if parent.drive.upper() == "C:":
            if free < 100 * 1024**3:
                require(expected_growth <= 100 * 1024 * 1024,
                        "Below C: reserve, preparation would add more than 100 MiB")
            else:
                require(free - expected_growth >= 100 * 1024**3, "Preparation would cross the C: reserve")
    root.mkdir()
    for row in plan["pages"]:
        source = Path(row["source"])
        declared_pin(source, row)
        target = root.joinpath(*PurePosixPath(row["path"]).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    verify_candidate(plan)
    metadata.mkdir()
    write(metadata / "delivery_plan.json", plan)
    write(metadata / "candidate_inventory.json", {"schema_version": 1,
          "release_id": RELEASE_ID, "candidate_root": str(root), "files": plan["pages"],
          "file_count": len(plan["pages"]), "total_bytes": plan["pages_total_bytes"],
          "tree_sha256": plan["pages_tree_sha256"]})
    write(metadata / "upload_manifest.json", {"schema_version": 1, "release_id": RELEASE_ID,
          "bucket": "ufo-timeline-data", "key_prefix": NEW_PREFIX, "uploads": plan["uploads"],
          "existing_object_policy": "Reuse only exact bytes/hash match; fail closed on any different existing immutable key. Upload through the root coordinator after review.",
          "upload_total_bytes": plan["upload_total_bytes"], "cloud_mutations_performed": False})
    write(metadata / "replication_contract.json", {"schema_version": 1, "release_id": RELEASE_ID,
          "quality_manifest": plan["quality_manifest"], "builder_receipts": plan["builder_receipts"],
          "pages": {"files": plan["pages"], "tree_sha256": plan["pages_tree_sha256"],
                    "total_bytes": plan["pages_total_bytes"]},
          "unchanged_canonical_r2": plan["inherited_objects"],
          "new_r2_delta": plan["uploads"], "effective_delivery": plan["effective_delivery"],
          "config": plan["config"], "retention": plan["retention"],
          "local_replication": "Reuse pinned shared original R2 source objects; stage this small Pages inventory and its declared quality deltas. Never hydrate an obsolete campaign tree or expand the complete corpus for this release.",
          "production_verification": "Verify mutable and immutable Pages files, then stream/hash every new delta URL. Inherited canonical pins remain unchanged; no original source byte is silently replaced."})
    write(metadata / "quality_release_contract.json", modern_contract(plan))


def normalize_provider_html(payload: bytes) -> tuple[bytes, dict | None]:
    if PAGES_ANALYTICS_INSERTION not in payload:
        return payload, None
    require(payload.count(PAGES_ANALYTICS_INSERTION) == 1
            and payload.count(PAGES_ANALYTICS_INSERTION + b"</body>") == 1,
            "Provider Analytics insertion is duplicated or misplaced")
    return payload.replace(PAGES_ANALYTICS_INSERTION, b"", 1), {
        "provider": "Cloudflare Pages Analytics", "inserted_bytes": len(PAGES_ANALYTICS_INSERTION),
        "envelope_sha256": hashlib.sha256(PAGES_ANALYTICS_INSERTION).hexdigest(),
        "token": "df011473b8f34ae9a926359e4a1743e6", "source_byte_hash_verified_after_exact_removal": True}


def verify_remote_record(url: str, record: dict, timeout: float) -> dict | None:
    request = urllib.request.Request(url, headers={"User-Agent": "UFO-Timeline-release-verification", "Accept-Encoding": "identity"})
    digest = hashlib.sha256()
    actual = 0
    html = record.get("allow_pages_analytics") is True
    payload = bytearray() if html else None
    transformed = None
    with urllib.request.urlopen(request, timeout=timeout) as response:
        require(response.status == 200, "Public asset is unavailable: " + url)
        require(response.headers.get("Content-Encoding", "identity") in {"", "identity"},
                "Unexpected transport encoding prevents immutable-byte check: " + url)
        if record.get("requires_revalidation"):
            cache = response.headers.get("Cache-Control", "")
            require(bool(re.search(r"(?:^|,)\s*(?:no-store|no-cache|max-age=0)(?:\s*,|$)", cache)),
                    "Deployed Cache-Control does not revalidate changed asset: " + url)
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            actual += len(block)
            require(actual <= record["bytes"] + (214 if html else 0), "Public asset exceeds declared length: " + url)
            if html:
                payload.extend(block)
            else:
                digest.update(block)
    if html:
        source, transformed = normalize_provider_html(bytes(payload))
        actual = len(source)
        digest.update(source)
    require(actual == record["bytes"] and digest.hexdigest() == record["sha256"],
            "Public asset differs from its frozen declaration: " + url)
    return dict(transformed, path=record["path"]) if transformed else None


def public_verification(plan: dict, base: str, timeout: float, pages_only: bool = False) -> dict:
    parsed = urlsplit(base)
    require(parsed.scheme == "https" and not parsed.username and not parsed.password
            and parsed.port in {None, 443} and parsed.path in {"", "/"} and not parsed.query and not parsed.fragment
            and (parsed.hostname == "ufo-timeline.pages.dev" or
                 bool(re.fullmatch(r"[0-9a-f]{8}\.ufo-timeline\.pages\.dev", parsed.hostname or ""))),
            "Public candidate verification requires an exact UFO Timeline Pages URL")
    revalidated = set(plan["cache_policy_coverage"]["changed_pages_assets"])
    jobs = [(base.rstrip("/") + "/" + row["path"],
             dict(row, requires_revalidation=row["path"] in revalidated,
                  allow_pages_analytics=row["path"].endswith(".html")))
            for row in plan["pages"] if row["path"] != "_headers"]
    public_pages_count = len(jobs)
    if not pages_only:
        jobs.extend((row["url"], row) for row in plan["uploads"])
    transformations = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(verify_remote_record, url, row, timeout) for url, row in jobs]
        for index, future in enumerate(as_completed(futures), 1):
            transformation = future.result()
            if isinstance(transformation, dict):
                transformations.append(transformation)
            if index % 20 == 0 or index == len(futures):
                print(f"Verified {index}/{len(futures)} declared public objects", file=sys.stderr, flush=True)
    return {"passed": True, "pages_url": base.rstrip("/"), "pages_files_verified": public_pages_count,
            "headers_control_file_pinned_locally_not_requested": True,
            "provider_html_transformations": sorted(transformations, key=lambda row: row["path"]),
            "changed_asset_cache_policies_verified": len(revalidated),
            "new_r2_objects_verified": 0 if pages_only else len(plan["uploads"]),
            "r2_verification_reused_from_immutable_preview": pages_only,
            "parallel_streams": 4, "inherited_original_objects": len(plan["inherited_objects"]),
            "inherited_objects_reused_from_original_pinned_contract": True, "full_corpus_downloaded_or_copied": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--baseline-inventory", type=Path)
    parser.add_argument("--quality-manifest", type=Path, default=REPO_ROOT / "data/research/database_quality_20261007/quality_view_manifest.json")
    parser.add_argument("--base-contract", type=Path, default=REPO_ROOT / "reproduction/release.json")
    parser.add_argument("--release-root", type=Path, default=REPO_ROOT / "data/releases/quality-20261007")
    parser.add_argument("--map-receipt", type=Path)
    parser.add_argument("--analysis-receipt", type=Path)
    parser.add_argument("--detail-receipt", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--metadata-root", type=Path)
    parser.add_argument("--extra-pages-path", action="append", default=[])
    parser.add_argument("--configure-source", action="store_true",
                        help="Derive config/counts/URLs and copy only receipt-declared Pages metadata/startup/overlay files into product source before its Git commit; combine with --check-only to preview")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check-only", action="store_true")
    mode.add_argument("--verify-existing", action="store_true")
    parser.add_argument("--verify-public", help="Read-only, stream/hash changed R2 and all declared Pages assets at this HTTPS URL")
    parser.add_argument("--pages-only", action="store_true", help="For final production check, verify only Pages; retain the immutable-preview R2 verification receipt")
    parser.add_argument("--write-modern-contract", type=Path, help="Export small portable runtime pins outside Pages; no corpus copy")
    parser.add_argument("--export-frozen-plan", type=Path, help="Export portable pins from an already-frozen private delivery plan, without rebuilding data")
    parser.add_argument("--verification-receipt", type=Path, help="Save the successful bounded verification result outside Pages")
    parser.add_argument("--hydrate-contract", type=Path, help="Hydrate only missing pinned physical objects from the portable contract")
    parser.add_argument("--hydrate-cache", type=Path, help="Explicit content-addressed reproduction cache; never expanded")
    parser.add_argument("--shared-base-root", type=Path, help="Existing shared original canonical_web directory")
    parser.add_argument("--shared-release-root", type=Path, help="Existing shared quality-20261007 delta directory")
    parser.add_argument("--shared-r2-root", type=Path, help="Optional existing R2-key mirror whose children include releases/")
    parser.add_argument("--verify-pages-root", type=Path, help="Verify exact source Pages inventory in a Git checkout/candidate during hydration")
    parser.add_argument("--verify-cache", action="store_true", help="Read-only check; reject missing runtime objects and write nothing")
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args(argv)
    try:
        if args.hydrate_contract:
            require(not args.export_frozen_plan and not args.configure_source and not args.verify_public
                    and not args.verify_existing and not args.write_modern_contract,
                    "Hydration must run separately from release preparation")
            print(json.dumps(hydrate_contract(args), indent=2))
            return 0
        if args.export_frozen_plan:
            require(args.write_modern_contract is not None and not args.configure_source and not args.verify_public,
                    "Frozen export requires only its explicit portable contract destination")
            frozen = load(args.export_frozen_plan.resolve())
            verify_candidate(frozen)
            print(json.dumps({"passed": True, "mode": "portable_contract_exported",
                              **write_modern_contract(args.write_modern_contract, frozen)}, indent=2))
            return 0
        require(args.source_root is not None, "Release preparation requires --source-root")
        if args.configure_source:
            require(not args.verify_existing and not args.verify_public,
                    "Source configuration precedes freezing/public verification")
            print(json.dumps(configure_source(args, args.check_only), indent=2))
            return 0
        plan = make_plan(args)
        if args.verify_existing:
            frozen = load(Path(plan["metadata_root"]) / "delivery_plan.json")
            for key in ("quality_manifest", "builder_receipts", "pages", "uploads", "config", "pages_tree_sha256"):
                require(frozen[key] == plan[key], "Source/contract changed after release freeze: " + key)
            verify_candidate(frozen)
            plan = frozen
        elif not args.check_only:
            require(not args.verify_public, "Public verification requires --verify-existing or --check-only")
            prepare(plan)
        result = {"passed": True, "mode": "check_only" if args.check_only else "verify_existing" if args.verify_existing else "prepared",
                  "release_id": RELEASE_ID, "pages_files": len(plan["pages"]), "pages_total_bytes": plan["pages_total_bytes"],
                  "changed_pages_paths": plan["changed_pages_paths"], "new_r2_objects": len(plan["uploads"]),
                  "new_r2_total_bytes": plan["upload_total_bytes"], "release_tree_bytes": plan["release_tree_bytes_before_preparation"],
                  "release_tree_cap_bytes": RELEASE_CAP, "pages_cap_bytes": PAGES_CAP,
                  "pages_tree_sha256": plan["pages_tree_sha256"], "inherited_r2_objects": len(plan["inherited_objects"]),
                  "inherited_corpus_rehashed_or_copied": False, "cloud_mutations_performed": False,
                  "candidate_root": plan["candidate_root"], "metadata_root": plan["metadata_root"],
                  "files_larger_than_100MiB": plan["files_larger_than_100MiB"]}
        if args.verify_public:
            result["public_verification"] = public_verification(plan, args.verify_public, args.timeout, args.pages_only)
        if args.write_modern_contract:
            result["portable_contract"] = write_modern_contract(args.write_modern_contract, plan)
        if args.verification_receipt:
            require(args.verify_public is not None, "A public verification must pass before writing its receipt")
            receipt = args.verification_receipt.resolve()
            require(not receipt.is_relative_to(Path(plan["candidate_root"]).resolve()),
                    "Verification receipts must remain outside Pages")
            require(not receipt.exists(), "Refusing to overwrite a verification receipt")
            receipt.parent.mkdir(parents=True, exist_ok=True)
            write(receipt, result)
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("Quality release rejected: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
