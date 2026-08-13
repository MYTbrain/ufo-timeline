"""Validate and publish one immutable crop-circle runtime release to Cloudflare R2.

The manifest remains on Pages. Its point index and detail chunks are uploaded
under the versioned R2 prefix encoded by ``assetBaseUrl``. Existing objects are
never overwritten: a matching object is skipped, while a hash mismatch aborts
the release before any upload begins.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import ssl
import subprocess
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen


DEFAULT_MANIFEST = Path("webapp/static_public/data/crop_circles/manifest.json")
DEFAULT_BUCKET = "ufo-timeline-data"
DEFAULT_CACHE_CONTROL = "public, max-age=31536000, immutable"
USER_AGENT = "ufo-timeline-crop-r2-publisher/1.0"
VERIFIED_SSL_CONTEXT = ssl.create_default_context()
if hasattr(ssl, "VERIFY_X509_STRICT"):
    VERIFIED_SSL_CONTEXT.verify_flags &= ~ssl.VERIFY_X509_STRICT


class ReleaseError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--wrangler", type=Path, default=Path("node_modules/.bin/wrangler"))
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate local payloads and print the immutable upload plan without network access.",
    )
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_payload_path(value: str) -> PurePosixPath:
    path = PurePosixPath(str(value or ""))
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ReleaseError(f"Unsafe crop-circle payload path: {value!r}")
    return path


def release_prefix(manifest: dict[str, Any]) -> str:
    release_id = str(manifest.get("releaseId") or "").strip()
    base_url = str(manifest.get("assetBaseUrl") or "").strip()
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ReleaseError("assetBaseUrl must be an absolute HTTPS URL")
    prefix = parsed.path.strip("/")
    if not prefix or prefix.split("/")[-1] != release_id:
        raise ReleaseError("assetBaseUrl path must end with the manifest releaseId")
    return prefix


def declared_payloads(manifest: dict[str, Any], manifest_path: Path) -> list[dict[str, Any]]:
    points = manifest.get("points")
    details = manifest.get("details")
    if not isinstance(points, dict) or not isinstance(details, dict) or not isinstance(details.get("files"), list):
        raise ReleaseError("Crop-circle manifest is missing point/detail payload declarations")
    declarations = [points, *details["files"]]
    root = manifest_path.parent
    prefix = release_prefix(manifest)
    payloads: list[dict[str, Any]] = []
    seen: set[str] = set()
    for declaration in declarations:
        if not isinstance(declaration, dict):
            raise ReleaseError("Invalid crop-circle payload declaration")
        relative = safe_payload_path(str(declaration.get("path") or ""))
        relative_text = relative.as_posix()
        if relative_text in seen:
            raise ReleaseError(f"Duplicate crop-circle payload declaration: {relative_text}")
        seen.add(relative_text)
        local_path = root.joinpath(*relative.parts)
        if not local_path.is_file():
            raise ReleaseError(f"Missing crop-circle payload: {local_path}")
        expected_bytes = int(declaration.get("bytes") or -1)
        expected_sha = str(declaration.get("sha256") or "")
        actual_bytes = local_path.stat().st_size
        actual_sha = sha256_file(local_path)
        if actual_bytes != expected_bytes or actual_sha != expected_sha:
            raise ReleaseError(
                f"Crop-circle payload does not match manifest: {relative_text} "
                f"(bytes {actual_bytes}/{expected_bytes}, sha256 {actual_sha}/{expected_sha})"
            )
        public_url = str(manifest["assetBaseUrl"]).rstrip("/") + "/" + quote(relative_text, safe="/._-")
        payloads.append({
            "path": relative_text,
            "localPath": local_path,
            "bytes": actual_bytes,
            "sha256": actual_sha,
            "r2Key": prefix + "/" + relative_text,
            "publicUrl": public_url,
        })
    expected_count = int((manifest.get("counts") or {}).get("detailChunks") or -1) + 1
    if len(payloads) != expected_count:
        raise ReleaseError(f"Manifest declares {len(payloads)} payloads, expected {expected_count}")
    return payloads


def request_bytes(url: str, *, timeout: float) -> tuple[int, bytes]:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Cache-Control": "no-cache"})
    try:
        with urlopen(request, timeout=timeout, context=VERIFIED_SSL_CONTEXT) as response:
            return int(response.status), response.read()
    except HTTPError as exc:
        return int(exc.code), exc.read()
    except URLError as exc:
        raise ReleaseError(f"Unable to verify public R2 URL {url}: {exc}") from exc


def classify_remote(payload: dict[str, Any], *, timeout: float) -> str:
    status, body = request_bytes(payload["publicUrl"] + "?release-integrity=1", timeout=timeout)
    if status == 404:
        return "missing"
    if status != 200:
        raise ReleaseError(f"Unexpected R2 preflight status {status}: {payload['publicUrl']}")
    actual_sha = hashlib.sha256(body).hexdigest()
    if len(body) != payload["bytes"] or actual_sha != payload["sha256"]:
        raise ReleaseError(
            "Refusing to overwrite a mismatched object at immutable key " + payload["r2Key"]
        )
    return "matching"


def resolve_wrangler_command(wrangler: Path) -> list[str]:
    """Return a CreateProcess-safe Wrangler launcher on Windows and POSIX."""
    wrangler = wrangler.resolve()
    if os.name != "nt":
        return [str(wrangler)]
    node_modules = wrangler.parent.parent if wrangler.parent.name == ".bin" else None
    wrangler_js = node_modules / "wrangler" / "bin" / "wrangler.js" if node_modules else wrangler
    if not wrangler_js.is_file():
        raise ReleaseError(f"Wrangler JavaScript entrypoint is missing: {wrangler_js}")
    located_node = shutil.which("node")
    if not located_node:
        raise ReleaseError("Node.js executable is unavailable for the pinned Wrangler launcher")
    return [str(Path(located_node).resolve()), str(wrangler_js.resolve())]


def upload_payload(wrangler_command: list[str], bucket: str, payload: dict[str, Any]) -> None:
    command = [
        *wrangler_command,
        "r2",
        "object",
        "put",
        f"{bucket}/{payload['r2Key']}",
        "--file",
        str(payload["localPath"]),
        "--content-type",
        "application/json; charset=utf-8",
        "--cache-control",
        DEFAULT_CACHE_CONTROL,
        "--remote",
    ]
    subprocess.run(command, check=True)


def verify_remote(payload: dict[str, Any], *, timeout: float) -> None:
    status, body = request_bytes(payload["publicUrl"] + "?release-integrity=post-upload", timeout=timeout)
    if status != 200:
        raise ReleaseError(f"Published R2 object returned HTTP {status}: {payload['publicUrl']}")
    if len(body) != payload["bytes"] or hashlib.sha256(body).hexdigest() != payload["sha256"]:
        raise ReleaseError(f"Published R2 object failed its hash check: {payload['r2Key']}")


def main() -> None:
    args = parse_args()
    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payloads = declared_payloads(manifest, manifest_path)
    plan = {
        "releaseId": manifest.get("releaseId"),
        "bucket": args.bucket,
        "payloadCount": len(payloads),
        "payloadBytes": sum(item["bytes"] for item in payloads),
        "r2Prefix": release_prefix(manifest),
        "assetBaseUrl": manifest.get("assetBaseUrl"),
    }
    if args.validate_only:
        print(json.dumps({**plan, "validated": True}, indent=2))
        return
    if not args.wrangler.is_file():
        raise ReleaseError(f"Wrangler is not installed at {args.wrangler}; run npm ci first")

    remote_states = {item["path"]: classify_remote(item, timeout=args.timeout) for item in payloads}
    uploads = [item for item in payloads if remote_states[item["path"]] == "missing"]
    wrangler_command = resolve_wrangler_command(args.wrangler)
    for index, payload in enumerate(uploads, start=1):
        print(f"Uploading crop-circle R2 payload {index}/{len(uploads)}: {payload['r2Key']}", flush=True)
        upload_payload(wrangler_command, args.bucket, payload)
    for payload in payloads:
        verify_remote(payload, timeout=args.timeout)
    print(json.dumps({
        **plan,
        "alreadyPresent": len(payloads) - len(uploads),
        "uploaded": len(uploads),
        "verified": len(payloads),
    }, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError, ReleaseError) as exc:
        print(f"Crop-circle R2 release failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
