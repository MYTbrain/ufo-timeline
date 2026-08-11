"""Shared integrity and immutable-upload plumbing for optional Timeline layers."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import ssl
import subprocess
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen


DEFAULT_CACHE_CONTROL = "public, max-age=31536000, immutable"
USER_AGENT = "ufo-timeline-optional-layer-r2-publisher/1.0"
VERIFIED_SSL_CONTEXT = ssl.create_default_context()
if hasattr(ssl, "VERIFY_X509_STRICT"):
    VERIFIED_SSL_CONTEXT.verify_flags &= ~ssl.VERIFY_X509_STRICT


class ReleaseError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_payload_path(value: str) -> PurePosixPath:
    normalized = str(value or "").replace("\\", "/")
    path = PurePosixPath(normalized)
    if (
        not normalized
        or path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
        or path.parts[0].endswith(":")
    ):
        raise ReleaseError(f"Unsafe optional-layer payload path: {value!r}")
    return path


def release_prefix(manifest: dict[str, Any]) -> str:
    release_id = str(manifest.get("releaseId") or "").strip()
    base_url = str(manifest.get("assetBaseUrl") or "").strip()
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ReleaseError("assetBaseUrl must be an absolute HTTPS URL")
    prefix = parsed.path.strip("/")
    if not release_id or not prefix or prefix.split("/")[-1] != release_id:
        raise ReleaseError("assetBaseUrl path must end with the manifest releaseId")
    delivery = manifest.get("delivery")
    if isinstance(delivery, dict) and delivery.get("immutablePrefix"):
        declared_prefix = str(delivery["immutablePrefix"]).strip("/")
        if declared_prefix != prefix:
            raise ReleaseError("delivery.immutablePrefix must match the assetBaseUrl path")
    return prefix


def _nested_payload_declarations(value: Any) -> list[dict[str, Any]]:
    declarations: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if isinstance(value.get("path"), str) and (
            value.get("r2Only") is True
            or "sha256" in value
            or "bytes" in value
            or "sizeBytes" in value
        ):
            declarations.append(value)
        for item in value.values():
            declarations.extend(_nested_payload_declarations(item))
    elif isinstance(value, list):
        for item in value:
            declarations.extend(_nested_payload_declarations(item))
    return declarations


def _record_count(value: Any) -> int | None:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        for key in ("records", "rows", "features"):
            if isinstance(value.get(key), list):
                return len(value[key])
        return len(value)
    return None


def _validate_decoded_payload(path: Path, declaration: Mapping[str, Any]) -> None:
    if path.suffix != ".gz":
        return
    try:
        decoded = gzip.decompress(path.read_bytes())
    except (OSError, EOFError) as exc:
        raise ReleaseError(f"Invalid gzip payload: {path}") from exc
    expected_decoded = declaration.get("decodedBytes", declaration.get("decoded_bytes"))
    if expected_decoded is not None and len(decoded) != int(expected_decoded):
        raise ReleaseError(
            f"Decoded byte count does not match manifest for {path.name}: "
            f"{len(decoded)}/{expected_decoded}"
        )
    expected_decoded_sha = declaration.get("decodedSha256", declaration.get("decoded_sha256"))
    if expected_decoded_sha is not None:
        actual_decoded_sha = hashlib.sha256(decoded).hexdigest()
        if actual_decoded_sha != str(expected_decoded_sha):
            raise ReleaseError(
                f"Decoded SHA-256 does not match manifest for {path.name}: "
                f"{actual_decoded_sha}/{expected_decoded_sha}"
            )
    content_type = str(declaration.get("contentType") or "application/json").lower()
    if not content_type.startswith("application/json"):
        return
    try:
        value = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseError(f"Compressed payload is not valid JSON: {path}") from exc
    expected_records = declaration.get("recordCount", declaration.get("record_count"))
    actual_records = _record_count(value)
    if expected_records is not None and actual_records != int(expected_records):
        raise ReleaseError(
            f"Record count does not match manifest for {path.name}: "
            f"{actual_records}/{expected_records}"
        )


def declared_payloads(manifest: dict[str, Any], manifest_path: Path) -> list[dict[str, Any]]:
    delivery = manifest.get("delivery")
    delivery = delivery if isinstance(delivery, dict) else {}
    declared_delivery_paths = delivery.get("r2OnlyPaths")
    payload_order: list[str] | None = None
    payload_allowlist: set[str] | None = None
    if declared_delivery_paths is not None:
        if not isinstance(declared_delivery_paths, list) or not all(
            isinstance(path, str) for path in declared_delivery_paths
        ):
            raise ReleaseError("delivery.r2OnlyPaths must be a list of paths")
        payload_order = [safe_payload_path(path).as_posix() for path in declared_delivery_paths]
        if len(set(payload_order)) != len(payload_order):
            raise ReleaseError("delivery.r2OnlyPaths contains duplicate paths")
        payload_allowlist = set(payload_order)

    declarations: dict[str, dict[str, Any]] = {}
    declaration_order: list[str] = []
    unlisted_r2: list[str] = []
    for declaration in _nested_payload_declarations(manifest):
        relative = safe_payload_path(str(declaration["path"])).as_posix()
        if payload_allowlist is not None and relative not in payload_allowlist:
            if declaration.get("r2Only") is True:
                unlisted_r2.append(relative)
            continue
        if relative in declarations:
            raise ReleaseError(f"Duplicate optional-layer payload declaration: {relative}")
        declarations[relative] = declaration
        declaration_order.append(relative)

    if payload_order is not None:
        missing = sorted(set(payload_order) - set(declarations))
        if missing or unlisted_r2:
            raise ReleaseError(
                "delivery.r2OnlyPaths disagrees with payload declarations"
                + (f"; missing integrity={', '.join(missing)}" if missing else "")
                + (f"; unlisted r2Only={', '.join(sorted(set(unlisted_r2)))}" if unlisted_r2 else "")
            )
    else:
        payload_order = declaration_order
    if not payload_order:
        raise ReleaseError("Optional-layer manifest declares no R2 payloads")

    root = manifest_path.parent
    prefix = release_prefix(manifest)
    payloads: list[dict[str, Any]] = []
    for relative_text in payload_order:
        declaration = declarations[relative_text]
        relative = safe_payload_path(relative_text)
        local_path = root.joinpath(*relative.parts)
        if not local_path.is_file():
            raise ReleaseError(f"Missing optional-layer payload: {local_path}")
        expected_bytes = declaration.get("bytes", declaration.get("sizeBytes", -1))
        try:
            expected_bytes = int(expected_bytes)
        except (TypeError, ValueError) as exc:
            raise ReleaseError(f"Invalid byte count for optional-layer payload: {relative_text}") from exc
        expected_sha = str(declaration.get("sha256") or "")
        if expected_bytes < 0 or not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
            raise ReleaseError(f"Invalid integrity declaration for optional-layer payload: {relative_text}")
        actual_bytes = local_path.stat().st_size
        actual_sha = sha256_file(local_path)
        if actual_bytes != expected_bytes or actual_sha != expected_sha:
            raise ReleaseError(
                f"Optional-layer payload does not match manifest: {relative_text} "
                f"(bytes {actual_bytes}/{expected_bytes}, sha256 {actual_sha}/{expected_sha})"
            )
        _validate_decoded_payload(local_path, declaration)
        public_url = str(manifest["assetBaseUrl"]).rstrip("/") + "/" + quote(
            relative_text, safe="/._-"
        )
        payloads.append(
            {
                "path": relative_text,
                "localPath": local_path,
                "bytes": actual_bytes,
                "sha256": actual_sha,
                "r2Key": prefix + "/" + relative_text,
                "publicUrl": public_url,
                "contentType": str(declaration.get("contentType") or "application/json; charset=utf-8"),
            }
        )

    pages_files = delivery.get("pagesFiles", [manifest_path.name])
    if not isinstance(pages_files, list) or not all(isinstance(path, str) for path in pages_files):
        raise ReleaseError("delivery.pagesFiles must be a list of paths")
    allowed = {safe_payload_path(path).as_posix() for path in pages_files} | set(payload_order)
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }
    undeclared = sorted(actual - allowed)
    if undeclared:
        raise ReleaseError(
            "Optional-layer directory contains undeclared release files; raw inputs, review queues, "
            "audits, caches, and images are not publishable: " + ", ".join(undeclared[:10])
        )
    return payloads


def request_http(url: str, *, method: str, timeout: float) -> tuple[int, Mapping[str, str], bytes]:
    request = Request(
        url,
        method=method,
        headers={"User-Agent": USER_AGENT, "Cache-Control": "no-cache"},
    )
    try:
        with urlopen(request, timeout=timeout, context=VERIFIED_SSL_CONTEXT) as response:
            body = b"" if method == "HEAD" else response.read()
            return int(response.status), dict(response.headers.items()), body
    except HTTPError as exc:
        body = b"" if method == "HEAD" else exc.read()
        return int(exc.code), dict(exc.headers.items()), body
    except URLError as exc:
        raise ReleaseError(f"Unable to verify public R2 URL {url}: {exc}") from exc


def _readback(payload: dict[str, Any], *, timeout: float, query: str) -> None:
    status, _, body = request_http(payload["publicUrl"] + query, method="GET", timeout=timeout)
    if status != 200:
        raise ReleaseError(f"R2 readback returned HTTP {status}: {payload['publicUrl']}")
    actual_sha = hashlib.sha256(body).hexdigest()
    if len(body) != payload["bytes"] or actual_sha != payload["sha256"]:
        raise ReleaseError(
            "Refusing to overwrite a mismatched object at immutable key " + payload["r2Key"]
        )


def classify_remote(payload: dict[str, Any], *, timeout: float) -> str:
    url = payload["publicUrl"] + "?release-integrity=head"
    status, headers, _ = request_http(url, method="HEAD", timeout=timeout)
    if status == 404:
        return "missing"
    if status in {403, 405, 501}:
        get_status, _, _ = request_http(url, method="GET", timeout=timeout)
        if get_status == 404:
            return "missing"
        if get_status != 200:
            raise ReleaseError(f"Unexpected R2 preflight status {get_status}: {payload['publicUrl']}")
    elif status != 200:
        raise ReleaseError(f"Unexpected R2 HEAD status {status}: {payload['publicUrl']}")
    content_length = headers.get("Content-Length") or headers.get("content-length")
    if content_length is not None and int(content_length) != payload["bytes"]:
        raise ReleaseError(
            "Refusing to overwrite a mismatched object at immutable key " + payload["r2Key"]
        )
    _readback(payload, timeout=timeout, query="?release-integrity=preflight")
    return "matching"


def resolve_wrangler_command(
    wrangler: Path,
    *,
    platform_name: str | None = None,
    node_executable: Path | None = None,
) -> list[str]:
    """Return a CreateProcess-safe Wrangler launcher on Windows and POSIX."""
    platform_name = os.name if platform_name is None else platform_name
    wrangler = wrangler.resolve()
    node_modules = wrangler.parent.parent if wrangler.parent.name == ".bin" else None
    wrangler_js = (
        node_modules / "wrangler" / "bin" / "wrangler.js"
        if node_modules is not None
        else wrangler
    )
    if platform_name == "nt" or wrangler.suffix.lower() == ".js":
        if not wrangler_js.is_file():
            raise ReleaseError(f"Wrangler JavaScript entrypoint is missing: {wrangler_js}")
        if node_executable is None:
            program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
            program_node = program_files / "nodejs" / "node.exe"
            located_node = shutil.which("node")
            node_executable = program_node if program_node.is_file() else Path(located_node or "")
        if not node_executable or not node_executable.is_file():
            raise ReleaseError("Node.js executable is unavailable for the pinned Wrangler launcher")
        return [str(node_executable.resolve()), str(wrangler_js.resolve())]
    if not wrangler.is_file():
        raise ReleaseError(f"Wrangler is not installed at {wrangler}; run npm ci first")
    return [str(wrangler)]


def upload_payload(wrangler_command: list[str], bucket: str, payload: dict[str, Any]) -> None:
    subprocess.run(
        [
            *wrangler_command,
            "r2",
            "object",
            "put",
            f"{bucket}/{payload['r2Key']}",
            "--file",
            str(payload["localPath"]),
            "--content-type",
            payload["contentType"],
            "--cache-control",
            DEFAULT_CACHE_CONTROL,
            "--remote",
        ],
        check=True,
    )


def verify_remote(payload: dict[str, Any], *, timeout: float) -> None:
    _readback(payload, timeout=timeout, query="?release-integrity=post-upload")


def publish_release(
    *,
    manifest_path: Path,
    bucket: str,
    wrangler: Path,
    timeout: float,
    validate_only: bool,
    validate_manifest: Callable[[dict[str, Any], list[dict[str, Any]]], None],
    upload_label: str,
) -> dict[str, Any]:
    resolved_manifest = manifest_path.resolve()
    manifest = json.loads(resolved_manifest.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ReleaseError("Optional-layer manifest must be a JSON object")
    payloads = declared_payloads(manifest, resolved_manifest)
    validate_manifest(manifest, payloads)
    plan = {
        "releaseId": manifest.get("releaseId"),
        "bucket": bucket,
        "payloadCount": len(payloads),
        "payloadBytes": sum(item["bytes"] for item in payloads),
        "r2Prefix": release_prefix(manifest),
        "assetBaseUrl": manifest.get("assetBaseUrl"),
    }
    if validate_only:
        return {**plan, "validated": True}
    wrangler_command = resolve_wrangler_command(wrangler)

    remote_states = {item["path"]: classify_remote(item, timeout=timeout) for item in payloads}
    uploads = [item for item in payloads if remote_states[item["path"]] == "missing"]
    for index, payload in enumerate(uploads, start=1):
        print(f"Uploading {upload_label} R2 payload {index}/{len(uploads)}: {payload['r2Key']}", flush=True)
        upload_payload(wrangler_command, bucket, payload)
    for payload in payloads:
        verify_remote(payload, timeout=timeout)
    return {
        **plan,
        "alreadyPresent": len(payloads) - len(uploads),
        "uploaded": len(uploads),
        "verified": len(payloads),
    }
