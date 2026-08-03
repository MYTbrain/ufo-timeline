"""Build, validate, hydrate, and serve the UFO Timeline reproduction contract.

The contract keeps source code in Git while pinning the exact immutable Pages
and R2 artifacts needed to reconstruct a production-equivalent local site.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import gzip
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import ssl
import sys
import time
from typing import Any, Iterable
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

try:
    import truststore
except ImportError:  # The locked environment includes it; retain a stdlib fallback for tooling.
    truststore = None
else:
    truststore.inject_into_ssl()


VERIFIED_SSL_CONTEXT = ssl.create_default_context()
# Python 3.14 enables OpenSSL's strict-X509 mode by default. Some valid public
# Cloudflare chains still omit the strict-only critical marker on an
# intermediate CA. Keep certificate and hostname verification enabled while
# disabling only that extra compatibility-breaking flag.
if hasattr(ssl, "VERIFY_X509_STRICT"):
    VERIFIED_SSL_CONTEXT.verify_flags &= ~ssl.VERIFY_X509_STRICT


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "reproduction" / "release.json"
DEFAULT_SITE_ROOT = REPO_ROOT / ".reproduction" / "site"
DEFAULT_CACHE_ROOT = REPO_ROOT / ".reproduction" / "cache"
SOURCE_ROOT = REPO_ROOT / "webapp" / "static_public"
USER_AGENT = "ufo-timeline-reproducer/1.0"
HASH_CHUNK_BYTES = 1024 * 1024
TREE_HASH_DESCRIPTION = "ordinal path<TAB>bytes<TAB>sha256<LF>"
OPTIONAL_LAYER_SPECS = (
    {
        "name": "crop_circles",
        "root": PurePosixPath("data/crop_circles"),
        "manifest": PurePosixPath("data/crop_circles/manifest.json"),
    },
    {
        "name": "animal_mutilations",
        "root": PurePosixPath("data/animal_mutilations"),
        "manifest": PurePosixPath("data/animal_mutilations/manifest.json"),
    },
)
PAGES_SOURCE_ADDITION_PATHS = frozenset(
    {
        PurePosixPath("404.html"),
        PurePosixPath("crop_circle_bootstrap.js"),
        PurePosixPath("crop_circle_layer.js"),
        PurePosixPath("animal_mutilation_bootstrap.js"),
        PurePosixPath("animal_mutilation_layer.js"),
    }
)
REQUIRED_PAGES_PATHS = (
    PurePosixPath("404.html"),
    PurePosixPath("index.html"),
    PurePosixPath("_headers"),
)
REQUIRED_PAGES_JSON_PATHS = (
    PurePosixPath("canonical_web_static_payload_manifest.json"),
    PurePosixPath("cloudflare_bundle_manifest.json"),
    PurePosixPath("r2_upload_manifest.json"),
    PurePosixPath("data/app_config.json"),
    PurePosixPath("data/event_catalog_manifest.json"),
    PurePosixPath("data/event_chunk_manifest.json"),
    PurePosixPath("data/points_meta.json"),
    PurePosixPath("data/startup_profiles/manifest.json"),
)
CLOUDFLARE_ANALYTICS_PATTERN = re.compile(
    rb"<!-- Cloudflare Pages Analytics --><script defer "
    rb"src='https://static\.cloudflareinsights\.com/beacon\.min\.js' "
    rb"data-cf-beacon='\{\"token\": \"[0-9a-f]{32}\"\}'></script>"
    rb"<!-- Cloudflare Pages Analytics -->"
)


class ContractError(RuntimeError):
    """Raised when a reproduction contract is unsafe, incomplete, or stale."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(HASH_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_sha256(records: Iterable[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for record in sorted(records, key=lambda item: item["path"]):
        row = f"{record['path']}\t{record['bytes']}\t{record['sha256']}\n"
        digest.update(row.encode("utf-8"))
    return digest.hexdigest()


def safe_relative_path(value: str) -> PurePosixPath:
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if (
        not normalized
        or path.is_absolute()
        or ".." in path.parts
        or (path.parts and path.parts[0].endswith(":"))
    ):
        raise ContractError(f"Unsafe relative path in reproduction contract: {value!r}")
    return path


def file_record(path: Path, *, relative_to: Path, url: str | None = None) -> dict[str, Any]:
    relative = path.relative_to(relative_to).as_posix()
    record: dict[str, Any] = {
        "path": relative,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }
    if url is not None:
        record["url"] = url
    return record


def iter_files(root: Path) -> list[Path]:
    return sorted((path for path in root.rglob("*") if path.is_file()), key=lambda path: path.relative_to(root).as_posix())


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ContractError(f"Expected a JSON object: {path}")
    return value


def _payload_declarations(value: Any) -> Iterable[dict[str, Any]]:
    """Yield nested browser payload declarations without assuming field names."""
    if isinstance(value, dict):
        path = value.get("path")
        if isinstance(path, str) and (
            value.get("r2Only") is True
            or "sha256" in value
            or "bytes" in value
            or "sizeBytes" in value
        ):
            yield value
        for item in value.values():
            yield from _payload_declarations(item)
    elif isinstance(value, list):
        for item in value:
            yield from _payload_declarations(item)


def _layer_relative_path(root: PurePosixPath, value: str) -> PurePosixPath:
    relative = safe_relative_path(value)
    if relative.parts[: len(root.parts)] == root.parts:
        resolved = relative
    else:
        resolved = root / relative
    if not resolved.is_relative_to(root):
        raise ContractError(f"Optional-layer path escapes {root.as_posix()}: {value!r}")
    return resolved


def _manifest_payload_path_values(manifest: dict[str, Any]) -> list[str]:
    delivery = manifest.get("delivery")
    if isinstance(delivery, dict) and "r2OnlyPaths" in delivery:
        paths = delivery.get("r2OnlyPaths")
        if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
            raise ContractError("Optional-layer delivery.r2OnlyPaths must be a list of paths")
        return list(paths)
    return [str(record["path"]) for record in _payload_declarations(manifest)]


def optional_layer_contracts(
    root: Path,
    *,
    validate_local_payloads: bool = False,
) -> list[dict[str, Any]]:
    """Load known optional-layer manifests and classify Pages versus R2 files."""
    contracts: list[dict[str, Any]] = []
    for spec in OPTIONAL_LAYER_SPECS:
        layer_root = spec["root"]
        manifest_relative = spec["manifest"]
        manifest_path = root.joinpath(*manifest_relative.parts)
        if not manifest_path.is_file():
            continue
        manifest = load_json(manifest_path)
        release_id = str(manifest.get("releaseId") or "").strip()
        asset_base_url = str(manifest.get("assetBaseUrl") or "").strip()
        if not release_id:
            raise ContractError(f"Optional-layer manifest has no releaseId: {manifest_relative.as_posix()}")
        parsed_base = urlparse(asset_base_url)
        prefix = parsed_base.path.strip("/")
        if parsed_base.scheme != "https" or not parsed_base.netloc or not prefix:
            raise ContractError(
                f"Optional-layer assetBaseUrl must be absolute HTTPS: {manifest_relative.as_posix()}"
            )
        if prefix.split("/")[-1] != release_id:
            raise ContractError(
                f"Optional-layer assetBaseUrl must end with releaseId: {manifest_relative.as_posix()}"
            )

        delivery = manifest.get("delivery")
        delivery = delivery if isinstance(delivery, dict) else {}
        immutable_prefix = str(delivery.get("immutablePrefix") or "").strip("/")
        if immutable_prefix and immutable_prefix != prefix:
            raise ContractError(
                f"Optional-layer immutablePrefix disagrees with assetBaseUrl: {manifest_relative.as_posix()}"
            )

        page_values = delivery.get("pagesFiles", ["manifest.json"])
        if not isinstance(page_values, list) or not all(isinstance(path, str) for path in page_values):
            raise ContractError("Optional-layer delivery.pagesFiles must be a list of paths")
        pages_paths = {_layer_relative_path(layer_root, value) for value in page_values}
        pages_paths.add(manifest_relative)

        payload_values = _manifest_payload_path_values(manifest)
        if not payload_values:
            raise ContractError(f"Optional-layer manifest declares no R2 payloads: {manifest_relative.as_posix()}")
        r2_paths = [_layer_relative_path(layer_root, value) for value in payload_values]
        if len(set(r2_paths)) != len(r2_paths):
            raise ContractError(f"Optional-layer manifest has duplicate R2 paths: {manifest_relative.as_posix()}")
        if set(r2_paths) & pages_paths:
            raise ContractError(f"Optional-layer file cannot be both Pages and R2: {manifest_relative.as_posix()}")

        declarations: dict[PurePosixPath, dict[str, Any]] = {}
        for declaration in _payload_declarations(manifest):
            relative = _layer_relative_path(layer_root, str(declaration["path"]))
            if relative in declarations:
                raise ContractError(
                    f"Optional-layer payload integrity is declared twice: {relative.as_posix()}"
                )
            declarations[relative] = declaration

        records: list[dict[str, Any]] = []
        for relative in r2_paths:
            declaration = declarations.get(relative)
            if declaration is None:
                raise ContractError(
                    f"Optional-layer R2 path has no integrity declaration: {relative.as_posix()}"
                )
            expected_bytes = declaration.get("bytes", declaration.get("sizeBytes", -1))
            expected_sha = str(declaration.get("sha256") or "")
            try:
                expected_bytes = int(expected_bytes)
            except (TypeError, ValueError) as exc:
                raise ContractError(f"Invalid optional-layer byte count: {relative.as_posix()}") from exc
            if expected_bytes < 0 or not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
                raise ContractError(f"Invalid optional-layer integrity declaration: {relative.as_posix()}")
            local_path = root.joinpath(*relative.parts)
            if validate_local_payloads:
                if not local_path.is_file():
                    raise ContractError(f"Missing optional-layer R2 payload: {relative.as_posix()}")
                actual_bytes = local_path.stat().st_size
                actual_sha = sha256_file(local_path)
                if actual_bytes != expected_bytes or actual_sha != expected_sha:
                    raise ContractError(
                        f"Optional-layer R2 payload failed local integrity: {relative.as_posix()}"
                    )
            payload_from_root = relative.relative_to(layer_root).as_posix()
            records.append(
                {
                    "path": relative.as_posix(),
                    "bytes": expected_bytes,
                    "sha256": expected_sha,
                    "url": asset_base_url.rstrip("/") + "/" + quote(payload_from_root, safe="/._-"),
                }
            )

        contracts.append(
            {
                "name": spec["name"],
                "root": layer_root,
                "manifest_path": manifest_relative,
                "manifest": manifest,
                "pages_paths": pages_paths,
                "r2_paths": set(r2_paths),
                "r2_records": records,
            }
        )
    return contracts


def optional_layer_undeclared_files(root: Path, contracts: list[dict[str, Any]] | None = None) -> list[str]:
    contracts = optional_layer_contracts(root) if contracts is None else contracts
    by_root = {contract["root"]: contract for contract in contracts}
    undeclared: list[str] = []
    for spec in OPTIONAL_LAYER_SPECS:
        layer_root = spec["root"]
        absolute_root = root.joinpath(*layer_root.parts)
        if not absolute_root.exists():
            continue
        contract = by_root.get(layer_root)
        allowed = set() if contract is None else contract["pages_paths"] | contract["r2_paths"]
        for path in iter_files(absolute_root):
            relative = PurePosixPath(path.relative_to(root).as_posix())
            if relative not in allowed:
                undeclared.append(relative.as_posix())
    return sorted(undeclared)


def pages_source_records(
    source_root: Path,
    release_manifest: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Classify the Git source overlay and return only deployable Pages assets."""
    layer_contracts = optional_layer_contracts(source_root, validate_local_payloads=True)
    declared_r2_paths = {
        path for contract in layer_contracts for path in contract["r2_paths"]
    }
    declared_pages_paths = {
        path for contract in layer_contracts for path in contract["pages_paths"]
    }
    undeclared_layer_files = optional_layer_undeclared_files(source_root, layer_contracts)
    if undeclared_layer_files:
        raise ContractError(
            "Optional-layer source contains undeclared files; keep review queues, raw inputs, "
            "caches, images, and provenance-only artifacts out of browser delivery: "
            + ", ".join(undeclared_layer_files[:10])
        )
    allowed_paths: set[PurePosixPath] | None = None
    if release_manifest is not None:
        allowed_paths = {
            safe_relative_path(str(record["path"]))
            for section in (release_manifest["pages"], release_manifest["source_overlay"])
            for record in section["files"]
        }
        allowed_paths.update(PAGES_SOURCE_ADDITION_PATHS)
        allowed_paths.update(declared_pages_paths)

    records: list[dict[str, Any]] = []
    unclassified: list[str] = []
    for source in iter_files(source_root):
        relative = PurePosixPath(source.relative_to(source_root).as_posix())
        if relative in declared_r2_paths:
            continue
        if allowed_paths is not None and relative not in allowed_paths:
            unclassified.append(relative.as_posix())
            continue
        records.append(file_record(source, relative_to=source_root))
    if unclassified:
        preview = ", ".join(unclassified[:10])
        raise ContractError(
            "Source overlay contains unclassified Pages assets; update the release allowlist explicitly: " + preview
        )
    return records


def merge_file_records(*collections: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for collection in collections:
        for record in collection:
            relative = safe_relative_path(str(record["path"])).as_posix()
            merged[relative] = {
                "path": relative,
                "bytes": int(record["bytes"]),
                "sha256": str(record["sha256"]),
            }
    return [merged[path] for path in sorted(merged)]


def expected_pages_records(
    manifest: dict[str, Any],
    source_root: Path,
    *,
    include_r2: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_records = pages_source_records(source_root, manifest)
    collections: list[Iterable[dict[str, Any]]] = [manifest["pages"]["files"]]
    if include_r2:
        collections.append(manifest["r2"]["files"])
        collections.append(optional_layer_r2_records(source_root))
    collections.append(source_records)
    return merge_file_records(*collections), source_records


def verify_exact_file_inventory(
    root: Path,
    expected_records: Iterable[dict[str, Any]],
    *,
    label: str,
) -> dict[str, Any]:
    expected = {str(record["path"]): record for record in expected_records}
    actual_records = [file_record(path, relative_to=root) for path in iter_files(root)]
    actual = {record["path"]: record for record in actual_records}
    missing = sorted(set(expected) - set(actual))
    unexpected = sorted(set(actual) - set(expected))
    changed = sorted(
        path
        for path in set(expected) & set(actual)
        if int(expected[path]["bytes"]) != int(actual[path]["bytes"])
        or str(expected[path]["sha256"]) != str(actual[path]["sha256"])
    )
    if missing or unexpected or changed:
        details = []
        if missing:
            details.append("missing=" + ", ".join(missing[:10]))
        if unexpected:
            details.append("unexpected=" + ", ".join(unexpected[:10]))
        if changed:
            details.append("changed=" + ", ".join(changed[:10]))
        raise ContractError(f"{label} does not match its exact allowed inventory: " + "; ".join(details))
    return {
        "file_count": len(actual_records),
        "total_bytes": sum(int(record["bytes"]) for record in actual_records),
        "tree_sha256": tree_sha256(actual_records),
    }


def verify_required_pages_files(root: Path) -> dict[str, Any]:
    missing = [path.as_posix() for path in REQUIRED_PAGES_PATHS if not root.joinpath(*path.parts).is_file()]
    json_paths = set(REQUIRED_PAGES_JSON_PATHS)
    json_paths.update(contract["manifest_path"] for contract in optional_layer_contracts(root))
    startup_root = root / "data" / "startup_profiles"
    if startup_root.is_dir():
        json_paths.update(
            PurePosixPath(path.relative_to(root).as_posix())
            for path in startup_root.rglob("manifest.json")
            if path.is_file()
        )
    missing.extend(path.as_posix() for path in sorted(json_paths) if not root.joinpath(*path.parts).is_file())
    if missing:
        raise ContractError("Pages release is missing required files: " + ", ".join(sorted(missing)))

    parsed: list[str] = []
    for relative in sorted(json_paths):
        path = root.joinpath(*relative.parts)
        try:
            json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ContractError(f"Required Pages JSON is invalid: {relative.as_posix()}: {exc}") from exc
        parsed.append(relative.as_posix())
    return {"required_file_count": len(REQUIRED_PAGES_PATHS), "parsed_json": parsed}


def optional_layer_r2_records(source_root: Path) -> list[dict[str, Any]]:
    return [
        record
        for contract in optional_layer_contracts(source_root, validate_local_payloads=True)
        for record in contract["r2_records"]
    ]


def find_optional_layer_r2_payloads(root: Path) -> list[str]:
    declared = {
        path
        for contract in optional_layer_contracts(root)
        for path in contract["r2_paths"]
    }
    return sorted(
        path.relative_to(root).as_posix()
        for path in iter_files(root)
        if PurePosixPath(path.relative_to(root).as_posix()) in declared
    )


def find_crop_r2_payloads(root: Path) -> list[str]:
    """Backward-compatible crop-only report for existing tooling and tests."""
    crop_root = PurePosixPath("data/crop_circles")
    return [
        path
        for path in find_optional_layer_r2_payloads(root)
        if PurePosixPath(path).is_relative_to(crop_root)
    ]


def verify_release_pages_bundle(
    root: Path,
    expected_records: Iterable[dict[str, Any]],
    *,
    allow_optional_r2_payloads: bool = False,
) -> dict[str, Any]:
    inventory = verify_exact_file_inventory(root, expected_records, label="Pages release")
    contracts = optional_layer_contracts(root)
    undeclared = optional_layer_undeclared_files(root, contracts)
    if undeclared:
        raise ContractError("Pages release contains undeclared optional-layer files: " + ", ".join(undeclared[:10]))
    optional_payloads = find_optional_layer_r2_payloads(root)
    if optional_payloads and not allow_optional_r2_payloads:
        raise ContractError(
            "Pages release contains R2-only optional-layer payloads: "
            + ", ".join(optional_payloads[:10])
        )
    return {
        "inventory": inventory,
        "required": verify_required_pages_files(root),
        "optional_layer_payloads": optional_payloads,
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def normalize_base_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ContractError(f"Expected an absolute HTTPS URL, got: {value}")
    return value.rstrip("/")


def deterministic_zip(source_root: Path, output_path: Path) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(output_path.suffix + ".part")
    if temp_path.exists():
        temp_path.unlink()
    records = [file_record(path, relative_to=source_root) for path in iter_files(source_root)]
    with ZipFile(temp_path, "w") as archive:
        for record in records:
            source = source_root / Path(record["path"])
            info = ZipInfo(record["path"], date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source.read_bytes(), compress_type=ZIP_DEFLATED, compresslevel=9)
    os.replace(temp_path, output_path)
    return {
        "file_count": len(records),
        "uncompressed_bytes": sum(record["bytes"] for record in records),
        "tree_sha256": tree_sha256(records),
        "tree_hash_algorithm": TREE_HASH_DESCRIPTION,
        "archive_bytes": output_path.stat().st_size,
        "archive_sha256": sha256_file(output_path),
    }


def build_manifest(args: argparse.Namespace) -> dict[str, Any]:
    pages_root = args.pages_root.resolve()
    source_root = args.source_root.resolve()
    if not pages_root.is_dir():
        raise ContractError(f"Pages root does not exist: {pages_root}")
    if not source_root.is_dir():
        raise ContractError(f"Source overlay does not exist: {source_root}")

    pages_base_url = normalize_base_url(args.pages_base_url)
    pages_host_label = urlparse(pages_base_url).hostname.split(".")[0]
    if pages_host_label != args.pages_deployment_id[:8]:
        raise ContractError(
            "Pages URL is not the immutable deployment URL for the supplied deployment ID: "
            f"{pages_base_url} vs {args.pages_deployment_id}"
        )

    r2_manifest_path = pages_root / "r2_upload_manifest.json"
    r2_source = load_json(r2_manifest_path)
    uploads = r2_source.get("uploads")
    if not isinstance(uploads, list) or not uploads:
        raise ContractError(f"R2 upload manifest has no uploads: {r2_manifest_path}")
    r2_base_url = normalize_base_url(str(r2_source.get("r2_base_url", "")))
    r2_key_prefix = str(r2_source.get("r2_key_prefix", "")).strip("/")
    if "/releases/" not in f"/{r2_key_prefix}/":
        raise ContractError(f"R2 key prefix is not immutable/versioned: {r2_key_prefix}")

    archive_summary = deterministic_zip(pages_root, args.archive_output.resolve())
    pages_records = [file_record(path, relative_to=pages_root) for path in iter_files(pages_root)]
    if tree_sha256(pages_records) != archive_summary["tree_sha256"]:
        raise ContractError("Pages tree changed while the deterministic archive was being built")

    r2_records: list[dict[str, Any]] = []
    for upload in uploads:
        if not isinstance(upload, dict):
            raise ContractError("R2 upload manifest contains a non-object entry")
        relative = safe_relative_path(str(upload.get("path", "")))
        # The production upload manifest was generated on Windows. Normalize
        # its separators so future releases can also be built on Linux/macOS.
        source_path_value = str(upload.get("source_path", "")).replace("\\", "/")
        source_path = Path(source_path_value)
        if not source_path.is_absolute():
            source_path = REPO_ROOT / source_path
        if not source_path.is_file():
            raise ContractError(f"Missing local source for R2 object {relative}: {source_path}")
        expected_bytes = int(upload.get("bytes", -1))
        if source_path.stat().st_size != expected_bytes:
            raise ContractError(
                f"R2 source size mismatch for {relative}: {source_path.stat().st_size} != {expected_bytes}"
            )
        url = normalize_base_url(str(upload.get("url", "")))
        record = {
            "path": relative.as_posix(),
            "bytes": expected_bytes,
            "sha256": sha256_file(source_path),
            "url": url,
            "copied_to_pages": bool(upload.get("copied_to_pages", False)),
        }
        r2_records.append(record)

    source_records = pages_source_records(source_root)
    mismatches: list[str] = []
    for record in source_records:
        pages_path = pages_root / Path(record["path"])
        if not pages_path.is_file() or sha256_file(pages_path) != record["sha256"]:
            mismatches.append(record["path"])
    if mismatches:
        preview = ", ".join(mismatches[:10])
        raise ContractError(f"Authoritative source is not synchronized with the frozen Pages tree: {preview}")

    app_config_path = pages_root / "data" / "app_config.json"
    app_config = load_json(app_config_path)
    manifest = {
        "schema_version": 1,
        "release": {
            "id": args.release_id,
            "generated_at_utc": r2_source.get("generated_at_utc"),
            "asset_version": app_config.get("staticAssetVersion"),
            "normalized_count": app_config.get("normalizedCount"),
            "mapped_count": app_config.get("mappedCount"),
            "canonical_production_url": args.canonical_production_url.rstrip("/"),
        },
        "runtime": {
            "python": (REPO_ROOT / ".python-version").read_text(encoding="utf-8").strip(),
            "node": (REPO_ROOT / ".nvmrc").read_text(encoding="utf-8").strip(),
            "python_lockfile": "requirements.lock",
            "node_lockfile": "package-lock.json",
        },
        "source_overlay": {
            "root": source_root.relative_to(REPO_ROOT).as_posix(),
            "file_count": len(source_records),
            "total_bytes": sum(record["bytes"] for record in source_records),
            "tree_sha256": tree_sha256(source_records),
            "tree_hash_algorithm": TREE_HASH_DESCRIPTION,
            "files": source_records,
        },
        "pages": {
            "deployment_id": args.pages_deployment_id,
            "base_url": pages_base_url,
            "file_count": archive_summary["file_count"],
            "uncompressed_bytes": archive_summary["uncompressed_bytes"],
            "tree_sha256": archive_summary["tree_sha256"],
            "tree_hash_algorithm": TREE_HASH_DESCRIPTION,
            "archive": {
                "url": normalize_base_url(args.archive_url),
                "bytes": archive_summary["archive_bytes"],
                "sha256": archive_summary["archive_sha256"],
                "format": "zip",
            },
            "files": pages_records,
        },
        "r2": {
            "base_url": r2_base_url,
            "key_prefix": r2_key_prefix,
            "file_count": len(r2_records),
            "total_bytes": sum(record["bytes"] for record in r2_records),
            "tree_sha256": tree_sha256(r2_records),
            "tree_hash_algorithm": TREE_HASH_DESCRIPTION,
            "source_manifest_path": "r2_upload_manifest.json",
            "source_manifest_sha256": sha256_file(r2_manifest_path),
            "files": r2_records,
        },
        "offline_localization": {
            "app_config_path": "data/app_config.json",
            "replace_url_prefix": r2_base_url,
            "replacement": ".",
        },
    }
    validate_manifest(manifest)
    write_json(args.output.resolve(), manifest)
    return manifest


def validate_file_collection(label: str, collection: dict[str, Any], *, count_key: str, bytes_key: str) -> None:
    files = collection.get("files")
    if not isinstance(files, list) or not files:
        raise ContractError(f"{label} file list is empty")
    seen: set[str] = set()
    for record in files:
        if not isinstance(record, dict):
            raise ContractError(f"{label} contains a non-object file record")
        relative = safe_relative_path(str(record.get("path", ""))).as_posix()
        if relative in seen:
            raise ContractError(f"Duplicate {label} path: {relative}")
        seen.add(relative)
        if int(record.get("bytes", -1)) < 0:
            raise ContractError(f"Invalid byte count for {label} path: {relative}")
        digest = str(record.get("sha256", ""))
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ContractError(f"Invalid SHA-256 for {label} path: {relative}")
    if int(collection.get(count_key, -1)) != len(files):
        raise ContractError(f"{label} file count does not match its records")
    if int(collection.get(bytes_key, -1)) != sum(int(record["bytes"]) for record in files):
        raise ContractError(f"{label} byte total does not match its records")
    if collection.get("tree_sha256") != tree_sha256(files):
        raise ContractError(f"{label} tree SHA-256 does not match its records")


def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema_version") != 1:
        raise ContractError(f"Unsupported reproduction schema: {manifest.get('schema_version')}")
    for required in ("release", "runtime", "source_overlay", "pages", "r2", "offline_localization"):
        if not isinstance(manifest.get(required), dict):
            raise ContractError(f"Missing reproduction manifest section: {required}")
    validate_file_collection("source overlay", manifest["source_overlay"], count_key="file_count", bytes_key="total_bytes")
    validate_file_collection("Pages", manifest["pages"], count_key="file_count", bytes_key="uncompressed_bytes")
    validate_file_collection("R2", manifest["r2"], count_key="file_count", bytes_key="total_bytes")

    archive = manifest["pages"].get("archive")
    if not isinstance(archive, dict):
        raise ContractError("Pages archive record is missing")
    normalize_base_url(str(archive.get("url", "")))
    if int(archive.get("bytes", -1)) <= 0 or len(str(archive.get("sha256", ""))) != 64:
        raise ContractError("Pages archive record is invalid")
    pages_url = normalize_base_url(str(manifest["pages"].get("base_url", "")))
    deployment_id = str(manifest["pages"].get("deployment_id", ""))
    if urlparse(pages_url).hostname.split(".")[0] != deployment_id[:8]:
        raise ContractError("Pages base URL is not tied to the recorded immutable deployment")
    r2_base = normalize_base_url(str(manifest["r2"].get("base_url", "")))
    if "/releases/" not in f"/{manifest['r2'].get('key_prefix', '')}/":
        raise ContractError("R2 contract is not tied to an immutable release prefix")
    for record in manifest["r2"]["files"]:
        if not normalize_base_url(str(record.get("url", ""))).startswith(r2_base + "/"):
            raise ContractError(f"R2 URL is outside the release base: {record.get('url')}")
    for lock_key in ("python_lockfile", "node_lockfile"):
        lock_path = REPO_ROOT / str(manifest["runtime"].get(lock_key, ""))
        if not lock_path.is_file():
            raise ContractError(f"Missing runtime lockfile: {lock_path}")


def request_bytes(url: str, *, timeout: float, retries: int = 3) -> bytes:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(request, timeout=timeout, context=VERIFIED_SSL_CONTEXT) as response:
                return response.read()
        except Exception as exc:  # noqa: BLE001 - report the final transport error with context
            last_error = exc
            if attempt < retries:
                time.sleep(attempt)
    raise ContractError(f"Failed to download after {retries} attempts: {url}: {last_error}")


def download_to_path(record: dict[str, Any], target: Path, *, timeout: float) -> str:
    expected_size = int(record["bytes"])
    expected_sha = str(record["sha256"])
    if target.is_file() and target.stat().st_size == expected_size and sha256_file(target) == expected_sha:
        return "cached"
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".part")
    if temp.exists():
        temp.unlink()
    request = Request(str(record["url"]), headers={"User-Agent": USER_AGENT})
    digest = hashlib.sha256()
    byte_count = 0
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            with urlopen(request, timeout=timeout, context=VERIFIED_SSL_CONTEXT) as response, temp.open("wb") as output:
                for chunk in iter(lambda: response.read(HASH_CHUNK_BYTES), b""):
                    output.write(chunk)
                    digest.update(chunk)
                    byte_count += len(chunk)
            break
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            digest = hashlib.sha256()
            byte_count = 0
            if temp.exists():
                temp.unlink()
            if attempt < 3:
                time.sleep(attempt)
    else:
        raise ContractError(f"Failed to download {record['url']}: {last_error}")
    actual_sha = digest.hexdigest()
    if byte_count != expected_size or actual_sha != expected_sha:
        if temp.exists():
            temp.unlink()
        raise ContractError(
            f"Downloaded artifact failed verification: {record['path']} "
            f"bytes={byte_count}/{expected_size} sha256={actual_sha}/{expected_sha}"
        )
    os.replace(temp, target)
    return "downloaded"


def safe_extract_zip(archive_path: Path, output_root: Path) -> None:
    with ZipFile(archive_path) as archive:
        for info in archive.infolist():
            relative = safe_relative_path(info.filename)
            target = output_root.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output, HASH_CHUNK_BYTES)


def verify_pages_tree(output_root: Path, pages: dict[str, Any]) -> None:
    inventory = verify_exact_file_inventory(output_root, pages["files"], label="Pages archive")
    if inventory["tree_sha256"] != pages["tree_sha256"]:
        raise ContractError("Extracted Pages tree does not match the frozen release")


def download_r2_files(manifest: dict[str, Any], output_root: Path, *, jobs: int, timeout: float) -> dict[str, int]:
    results = {"cached": 0, "downloaded": 0}
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=jobs) as executor:
        futures = {
            executor.submit(
                download_to_path,
                record,
                output_root / Path(record["path"]),
                timeout=timeout,
            ): record["path"]
            for record in manifest["r2"]["files"]
        }
        for index, future in enumerate(as_completed(futures), start=1):
            path = futures[future]
            try:
                results[future.result()] += 1
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{path}: {exc}")
            if index % 50 == 0 or index == len(futures):
                print(f"R2 artifacts verified: {index}/{len(futures)}", flush=True)
    if failures:
        raise ContractError("R2 hydration failed:\n" + "\n".join(failures[:20]))
    return results


def overlay_source(
    source_root: Path,
    output_root: Path,
    *,
    records: list[dict[str, Any]] | None = None,
    release_manifest: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    records = pages_source_records(source_root, release_manifest) if records is None else records
    for record in records:
        relative = Path(record["path"])
        source = source_root / relative
        target = output_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return records


def hydrate_optional_layer_payloads(source_root: Path, output_root: Path) -> dict[str, Any]:
    """Copy locally pinned optional-layer R2 payloads into an offline reproduction."""
    records = optional_layer_r2_records(source_root)
    for record in records:
        source = source_root / Path(record["path"])
        target = output_root / Path(record["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if target.stat().st_size != int(record["bytes"]) or sha256_file(target) != record["sha256"]:
            raise ContractError(f"Optional-layer payload copy failed integrity: {record['path']}")
    return {
        "file_count": len(records),
        "total_bytes": sum(int(record["bytes"]) for record in records),
        "tree_sha256": tree_sha256(records),
    }


def localize_optional_layer_manifests(source_root: Path, output_root: Path) -> list[dict[str, str]]:
    """Point hydrated optional-layer manifests at their local payload directories."""
    localized: list[dict[str, str]] = []
    for contract in optional_layer_contracts(source_root, validate_local_payloads=True):
        relative = contract["manifest_path"]
        target = output_root.joinpath(*relative.parts)
        manifest = load_json(target)
        manifest["assetBaseUrl"] = "./" + contract["root"].as_posix() + "/"
        write_json(target, manifest)
        localized.append({"path": relative.as_posix(), "sha256": sha256_file(target)})
    return localized


def replace_url_prefix(value: Any, old: str, new: str) -> Any:
    if isinstance(value, str):
        if value == old:
            return new
        if value.startswith(old + "/"):
            return new + value[len(old) :]
        return value
    if isinstance(value, list):
        return [replace_url_prefix(item, old, new) for item in value]
    if isinstance(value, dict):
        return {key: replace_url_prefix(item, old, new) for key, item in value.items()}
    return value


def normalize_production_source(path: str, content: bytes) -> bytes:
    """Remove only Cloudflare's deterministic serve-time HTML analytics injection."""
    if not path.lower().endswith(".html"):
        return content
    return CLOUDFLARE_ANALYTICS_PATTERN.sub(b"", content)


def localize_app_config(manifest: dict[str, Any], output_root: Path) -> str:
    localization = manifest["offline_localization"]
    config_path = output_root / Path(localization["app_config_path"])
    config = load_json(config_path)
    localized = replace_url_prefix(
        config,
        str(localization["replace_url_prefix"]),
        str(localization["replacement"]),
    )
    deployment_profile = localized.get("deploymentProfile")
    if isinstance(deployment_profile, dict):
        deployment_profile["target"] = "local_reproduction"
    write_json(config_path, localized)
    return sha256_file(config_path)


def expand_gzip_files(output_root: Path) -> dict[str, int]:
    expanded = 0
    skipped = 0
    for compressed in sorted(output_root.rglob("*.gz")):
        target = compressed.with_suffix("")
        if target.exists():
            skipped += 1
            continue
        temp = target.with_suffix(target.suffix + ".part")
        target.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(compressed, "rb") as source, temp.open("wb") as output:
            shutil.copyfileobj(source, output, HASH_CHUNK_BYTES)
        os.replace(temp, target)
        expanded += 1
    return {"expanded": expanded, "skipped_existing": skipped}


def hydrate(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path = args.manifest.resolve()
    manifest = load_json(manifest_path)
    validate_manifest(manifest)
    output_root = args.output.resolve()
    cache_root = args.cache.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    cache_root.mkdir(parents=True, exist_ok=True)

    archive_record = {
        "path": "pages-bundle.zip",
        **manifest["pages"]["archive"],
    }
    archive_path = cache_root / f"{manifest['release']['id']}-pages.zip"
    archive_status = download_to_path(archive_record, archive_path, timeout=args.timeout)
    safe_extract_zip(archive_path, output_root)
    verify_pages_tree(output_root, manifest["pages"])

    source_root = REPO_ROOT / Path(manifest["source_overlay"]["root"])
    expected_records, source_records = expected_pages_records(
        manifest,
        source_root,
        include_r2=bool(args.offline),
    )
    r2_results = {"cached": 0, "downloaded": 0}
    optional_layer_results = {"file_count": 0, "total_bytes": 0, "tree_sha256": tree_sha256([])}
    if args.offline:
        r2_results = download_r2_files(
            manifest,
            output_root,
            jobs=max(1, args.jobs),
            timeout=args.timeout,
        )
        optional_layer_results = hydrate_optional_layer_payloads(source_root, output_root)

    overlay_source(source_root, output_root, records=source_records)
    for record in source_records:
        output_path = output_root / Path(record["path"])
        if sha256_file(output_path) != record["sha256"]:
            raise ContractError(f"Source overlay verification failed: {record['path']}")
    for record in manifest["r2"]["files"] if args.offline else []:
        output_path = output_root / Path(record["path"])
        if output_path.stat().st_size != int(record["bytes"]) or sha256_file(output_path) != record["sha256"]:
            raise ContractError(f"R2 artifact verification failed after hydration: {record['path']}")

    release_validation = verify_release_pages_bundle(
        output_root,
        expected_records,
        allow_optional_r2_payloads=bool(args.offline),
    )
    localized_config_sha = None
    localized_optional_manifests: list[dict[str, str]] = []
    if args.offline:
        localized_config_sha = localize_app_config(manifest, output_root)
        localized_optional_manifests = localize_optional_layer_manifests(source_root, output_root)
    gzip_results = {"expanded": 0, "skipped_existing": 0}
    if args.expand_gzip:
        gzip_results = expand_gzip_files(output_root)

    receipt = {
        "schema_version": 1,
        "release_id": manifest["release"]["id"],
        "manifest_sha256": sha256_file(manifest_path),
        "source_tree_sha256": tree_sha256(source_records),
        "source_file_count": len(source_records),
        "excluded_r2_source_file_count": len(iter_files(source_root)) - len(source_records),
        "offline": bool(args.offline),
        "expanded_gzip": bool(args.expand_gzip),
        "localized_app_config_sha256": localized_config_sha,
        "localized_optional_layer_manifests": localized_optional_manifests,
        "pages_archive": archive_status,
        "r2": r2_results,
        "optional_layer_r2": optional_layer_results,
        "gzip": gzip_results,
        "pages_validation": release_validation,
    }
    # Keep reproduction metadata outside the deployable directory so Wrangler
    # receives exactly the validated Pages inventory and nothing else.
    receipt_path = cache_root / f"{manifest['release']['id']}-reproduction-receipt.json"
    receipt["receipt_path"] = str(receipt_path)
    write_json(receipt_path, receipt)
    return receipt


def check_production(manifest: dict[str, Any], *, timeout: float) -> dict[str, Any]:
    production_url = normalize_base_url(str(manifest["release"]["canonical_production_url"]))
    app_config_url = production_url + "/data/app_config.json"
    app_config = json.loads(request_bytes(app_config_url, timeout=timeout))
    live_r2 = app_config.get("deploymentProfile", {}).get("largeDataBaseUrl")
    if live_r2 != manifest["r2"]["base_url"]:
        raise ContractError(f"Production R2 release drifted: {live_r2} != {manifest['r2']['base_url']}")
    for key, manifest_key in (("normalizedCount", "normalized_count"), ("mappedCount", "mapped_count")):
        if app_config.get(key) != manifest["release"].get(manifest_key):
            raise ContractError(f"Production {key} drifted from the reproduction contract")
    live_r2_manifest = request_bytes(production_url + "/r2_upload_manifest.json", timeout=timeout)
    live_manifest_sha = hashlib.sha256(live_r2_manifest).hexdigest()
    if live_manifest_sha != manifest["r2"]["source_manifest_sha256"]:
        raise ContractError("Production R2 upload manifest drifted from the reproduction contract")

    source_root = REPO_ROOT / Path(manifest["source_overlay"]["root"])
    source_records = pages_source_records(source_root, manifest)
    for record in source_records:
        live_bytes = request_bytes(
            production_url + "/" + quote(record["path"], safe="/._-"),
            timeout=timeout,
        )
        live_bytes = normalize_production_source(record["path"], live_bytes)
        live_sha = hashlib.sha256(live_bytes).hexdigest()
        if len(live_bytes) != record["bytes"] or live_sha != record["sha256"]:
            raise ContractError(f"Production source asset drifted from Git: {record['path']}")
    optional_records = optional_layer_r2_records(source_root)
    for record in optional_records:
        live_bytes = request_bytes(record["url"], timeout=timeout)
        live_sha = hashlib.sha256(live_bytes).hexdigest()
        if len(live_bytes) != int(record["bytes"]) or live_sha != record["sha256"]:
            raise ContractError(f"Production optional-layer R2 payload drifted: {record['path']}")
    return {
        "production_url": production_url,
        "r2_base_url": live_r2,
        "normalized_count": app_config.get("normalizedCount"),
        "mapped_count": app_config.get("mappedCount"),
        "r2_manifest_sha256": live_manifest_sha,
        "source_file_count": len(source_records),
        "source_tree_sha256": tree_sha256(source_records),
        "optional_layer_r2_file_count": len(optional_records),
        "optional_layer_r2_tree_sha256": tree_sha256(optional_records),
    }


def verify(args: argparse.Namespace) -> dict[str, Any]:
    manifest = load_json(args.manifest.resolve())
    validate_manifest(manifest)
    source_root = REPO_ROOT / Path(manifest["source_overlay"]["root"])
    optional_records = optional_layer_r2_records(source_root)
    result: dict[str, Any] = {
        "ok": True,
        "release_id": manifest["release"]["id"],
        "pages_tree_sha256": manifest["pages"]["tree_sha256"],
        "r2_tree_sha256": manifest["r2"]["tree_sha256"],
        "optional_layer_r2_file_count": len(optional_records),
        "optional_layer_r2_tree_sha256": tree_sha256(optional_records),
    }
    if args.check_baseline_source:
        records = [file_record(path, relative_to=source_root) for path in iter_files(source_root)]
        if tree_sha256(records) != manifest["source_overlay"]["tree_sha256"]:
            raise ContractError("Current source differs from the release baseline; hydrate will overlay the current source")
        result["baseline_source_matches"] = True
    if args.check_production:
        result["production"] = check_production(manifest, timeout=args.timeout)
    return result


def serve(args: argparse.Namespace) -> None:
    site_root = args.site.resolve()
    if not (site_root / "index.html").is_file():
        raise ContractError(
            f"Reproduction site is not hydrated: {site_root}. Run `python scripts/reproduction.py hydrate --offline` first."
        )
    handler = lambda *handler_args, **handler_kwargs: SimpleHTTPRequestHandler(  # noqa: E731
        *handler_args,
        directory=str(site_root),
        **handler_kwargs,
    )
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Serving UFO Timeline reproduction at http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="Build a deterministic Pages archive and reproduction manifest")
    build.add_argument("--pages-root", type=Path, required=True)
    build.add_argument("--source-root", type=Path, default=SOURCE_ROOT)
    build.add_argument("--pages-base-url", required=True)
    build.add_argument("--pages-deployment-id", required=True)
    build.add_argument("--canonical-production-url", default="https://ufo-timeline.pages.dev")
    build.add_argument("--release-id", required=True)
    build.add_argument("--archive-output", type=Path, required=True)
    build.add_argument("--archive-url", required=True)
    build.add_argument("--output", type=Path, default=DEFAULT_MANIFEST)

    hydrate_parser = subparsers.add_parser("hydrate", help="Hydrate a verified local reproduction")
    hydrate_parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    hydrate_parser.add_argument("--output", type=Path, default=DEFAULT_SITE_ROOT)
    hydrate_parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE_ROOT)
    hydrate_parser.add_argument("--offline", action="store_true", help="Download every immutable R2 object and localize app URLs")
    hydrate_parser.add_argument("--expand-gzip", action="store_true", help="Expand gzip siblings for full scientific validation")
    hydrate_parser.add_argument("--jobs", type=int, default=8)
    hydrate_parser.add_argument("--timeout", type=float, default=120.0)

    verify_parser = subparsers.add_parser("verify", help="Validate the committed reproduction contract")
    verify_parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    verify_parser.add_argument("--check-baseline-source", action="store_true")
    verify_parser.add_argument("--check-production", action="store_true")
    verify_parser.add_argument("--timeout", type=float, default=120.0)

    serve_parser = subparsers.add_parser("serve", help="Serve a hydrated local reproduction")
    serve_parser.add_argument("--site", type=Path, default=DEFAULT_SITE_ROOT)
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "build":
            result = build_manifest(args)
            print(json.dumps({"ok": True, "release": result["release"], "pages": result["pages"] | {"files": "omitted"}, "r2": result["r2"] | {"files": "omitted"}}, indent=2, sort_keys=True))
        elif args.command == "hydrate":
            print(json.dumps(hydrate(args), indent=2, sort_keys=True))
        elif args.command == "verify":
            print(json.dumps(verify(args), indent=2, sort_keys=True))
        elif args.command == "serve":
            serve(args)
        else:  # pragma: no cover - argparse enforces the subcommand
            raise ContractError(f"Unknown command: {args.command}")
    except ContractError as exc:
        print(f"reproduction error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
