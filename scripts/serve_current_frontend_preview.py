"""Preview reviewed frontend deltas over the retained Pages stage, without copies.

Only the explicitly listed public files may come from the source checkout.
All other assets come from the existing stage. Public R2 URLs in JSON responses
are rewritten in memory to a restricted same-origin relay; files on disk remain
unchanged. The relay streams published assets without storing copies. The server
listens on loopback only.
"""

from __future__ import annotations

import argparse
from functools import partial
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import mimetypes
from pathlib import Path
from shutil import copyfileobj
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_OVERLAYS = frozenset({
    "index.html", "app.js", "famous_case_presets.js",
    "famous_case_availability.js", "flap_preset_labels.js", "trace_direction_summary.js", "share_view.js", "analysis_view.js",
    "styles.css", "ui/accepted-workspace/site-workflow-preview.js",
    "ui/accepted-workspace/chronology-preview.css",
})
PUBLISHED_ORIGIN = "https://pub-e9029ab2f6b448daad03d7cde7e15e64.r2.dev"
PUBLISHED_PREFIX = "/__published_assets/"
REMOTE_TIMEOUT_SECONDS = 30
MAX_JSON_BYTES = 32 * 1024 * 1024


def public_path_parts(request_target: str) -> list[str]:
    """Reject traversal, hidden paths and Windows path aliases before routing."""
    parsed = urlsplit(request_target)
    if parsed.scheme or parsed.netloc:
        raise ValueError("Only local request paths are accepted")
    request_path = unquote(parsed.path, errors="strict")
    if request_path == "/":
        request_path = "/index.html"
    if not request_path.startswith("/"):
        raise ValueError("An absolute request path is required")
    parts = request_path[1:].split("/")
    if any(
        not part or part.startswith(".") or part.endswith((".", " "))
        or any(character in '<>:"\\|?*%' or ord(character) < 32 for character in part)
        for part in parts
    ):
        raise ValueError("Invalid public asset path")
    return parts


def resolve_public_file(request_target: str, source_root: Path, stage_root: Path) -> Path:
    """Select one public file; reject traversal, hidden paths and directories."""
    parts = public_path_parts(request_target)
    relative = "/".join(parts)
    root = source_root if relative in SOURCE_OVERLAYS and (source_root / relative).is_file() else stage_root
    resolved_root = root.resolve()
    candidate = (resolved_root / relative).resolve()
    if not candidate.is_relative_to(resolved_root):
        raise ValueError("Asset must stay within its public root")
    if not candidate.is_file():
        raise FileNotFoundError(relative)
    return candidate


def published_asset_url(request_target: str) -> str | None:
    parts = public_path_parts(request_target)
    if parts[0] != PUBLISHED_PREFIX.strip("/"):
        return None
    if len(parts) < 4 or parts[1] != "releases":
        raise ValueError("Only immutable published release assets are available")
    # Neither the request query nor a caller-supplied host participates in the
    # destination. Only this pinned public origin and /releases/ may be read.
    return PUBLISHED_ORIGIN + "/" + quote("/".join(parts[1:]), safe="/-._~")


def rewrite_published_urls(payload: bytes) -> bytes:
    original = (PUBLISHED_ORIGIN + "/releases/").encode("ascii")
    replacement = (PUBLISHED_PREFIX + "releases/").encode("ascii")
    return payload.replace(original, replacement).replace(
        original.replace(b"/", b"\\/"), replacement.replace(b"/", b"\\/")
    )


class NoPublishedRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        # Immutable objects need no redirects. Refusing all redirects prevents
        # either a new host or an unexpected mutable path from entering scope.
        return None


def public_content_type(path: Path) -> str:
    # .gz files are fetched as compressed bytes and explicitly decoded by the
    # application. They must never receive an automatic Content-Encoding header.
    overrides = {
        ".js": "application/javascript; charset=utf-8",
        ".mjs": "application/javascript; charset=utf-8",
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".svg": "image/svg+xml",
        ".wasm": "application/wasm",
        ".gz": "application/gzip",
    }
    return overrides.get(path.suffix.lower()) or mimetypes.guess_type(str(path))[0] or "application/octet-stream"


class PreviewHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def __init__(self, *args, source_root: Path, stage_root: Path, quiet: bool = False, **kwargs):
        self.source_root = source_root
        self.stage_root = stage_root
        self.quiet = quiet
        super().__init__(*args, **kwargs)

    def log_message(self, format: str, *args) -> None:
        if not self.quiet:
            super().log_message(format, *args)

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
        self.serve_asset(head_only=False)

    def do_HEAD(self) -> None:  # noqa: N802 - stdlib handler contract
        self.serve_asset(head_only=True)

    def serve_asset(self, *, head_only: bool) -> None:
        try:
            remote_url = published_asset_url(self.path)
        except (ValueError, UnicodeError):
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid public asset path")
            return
        if remote_url is not None:
            self.serve_published_asset(remote_url, head_only=head_only)
            return
        try:
            path = resolve_public_file(self.path, self.source_root, self.stage_root)
            stream = path.open("rb")
        except (ValueError, UnicodeError):
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid public asset path")
            return
        except (OSError, RuntimeError):
            self.send_error(HTTPStatus.NOT_FOUND, "Public asset not found")
            return
        with stream:
            if path.suffix.lower() == ".json":
                payload = rewrite_published_urls(stream.read())
                self.send_payload(payload, public_content_type(path), head_only=head_only)
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", public_content_type(path))
            self.send_header("Content-Length", str(path.stat().st_size))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            if not head_only:
                try:
                    copyfileobj(stream, self.wfile, length=256 * 1024)
                except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                    pass  # Browser navigation may cancel an in-flight asset.

    def send_payload(self, payload: bytes, content_type: str, *, head_only: bool) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if not head_only:
            try:
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                pass

    def serve_published_asset(self, remote_url: str, *, head_only: bool) -> None:
        remote_path = Path(urlsplit(remote_url).path)
        is_json = remote_path.suffix.lower() == ".json"
        method = "HEAD" if head_only and not is_json else "GET"
        request = Request(remote_url, method=method, headers={
            "Accept-Encoding": "identity", "User-Agent": "UFO-Timeline-Local-Preview/1.0",
        })
        try:
            upstream = build_opener(NoPublishedRedirects()).open(request, timeout=REMOTE_TIMEOUT_SECONDS)
        except HTTPError as error:
            status = error.code if error.code in (403, 404, 410, 429) else HTTPStatus.BAD_GATEWAY
            error.close()
            self.send_error(status, "Published asset request failed")
            return
        except (TimeoutError, URLError, OSError) as error:
            timed_out = isinstance(error, TimeoutError) or isinstance(getattr(error, "reason", None), TimeoutError)
            self.send_error(HTTPStatus.GATEWAY_TIMEOUT if timed_out else HTTPStatus.BAD_GATEWAY, "Published asset unavailable")
            return
        with upstream:
            if upstream.headers.get("Content-Encoding", "identity").lower() not in ("", "identity"):
                self.send_error(HTTPStatus.BAD_GATEWAY, "Unexpected published transport encoding")
                return
            if is_json:
                try:
                    payload = upstream.read(MAX_JSON_BYTES + 1)
                except (TimeoutError, OSError):
                    self.send_error(HTTPStatus.GATEWAY_TIMEOUT, "Published JSON response interrupted")
                    return
                if len(payload) > MAX_JSON_BYTES:
                    self.send_error(HTTPStatus.BAD_GATEWAY, "Published JSON exceeds preview response limit")
                    return
                self.send_payload(rewrite_published_urls(payload), public_content_type(remote_path), head_only=head_only)
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", public_content_type(remote_path))
            content_length = upstream.headers.get("Content-Length")
            if content_length and content_length.isdigit():
                self.send_header("Content-Length", content_length)
            else:
                self.send_header("Connection", "close")
                self.close_connection = True
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            # Never set Content-Encoding: .gz/binary assets remain original bytes.
            self.end_headers()
            if not head_only:
                try:
                    copyfileobj(upstream, self.wfile, length=256 * 1024)
                except (TimeoutError, OSError):
                    self.close_connection = True


class PreviewServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 128


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--stage-root", type=Path, default=None)
    parser.add_argument("--port", type=int, default=8136)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    source_root = args.source_root.resolve()
    stage_root = (args.stage_root or source_root / ".tmp" / "workspace-analysis-20261008-pages").resolve()
    if not source_root.is_dir() or not stage_root.is_dir():
        parser.error("The source checkout and retained Pages stage must already exist")
    if not (stage_root / "data" / "app_config.json").is_file():
        parser.error("The retained stage is missing data/app_config.json")
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535")
    handler = partial(PreviewHandler, source_root=source_root, stage_root=stage_root, quiet=args.quiet)
    server = PreviewServer(("127.0.0.1", args.port), handler)
    print(f"Current frontend preview: http://127.0.0.1:{args.port}/", flush=True)
    print(f"Source overlays: {source_root} ({', '.join(sorted(SOURCE_OVERLAYS))})", flush=True)
    print(f"Retained runtime assets: {stage_root}", flush=True)
    print("Public R2 assets: read-only same-origin relay; JSON URL substitutions stay in memory.", flush=True)
    print("Storage: no copied data, staging tree, on-disk configuration rewrite or deployment.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
