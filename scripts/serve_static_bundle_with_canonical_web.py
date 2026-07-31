"""Serve the static app with optional canonical web artifacts for local preview.

This helper serves the deployable ``static_bundle`` by default, including the
promoted canonical web artifacts staged under ``static_bundle/data/canonical_web``.
It can also point at an external canonical artifact directory when explicitly
requested with ``--canonical-web-dir``.
It can also serve precompressed ``.gz`` siblings with the correct
``Content-Encoding`` header, matching how a production static host should serve
those files.
"""

from __future__ import annotations

import argparse
from functools import partial
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import posixpath
import sys
from typing import Any
from urllib.parse import unquote, urlparse


DEFAULT_STATIC_ROOT = Path("static_bundle")
DEFAULT_CANONICAL_WEB_DIR = DEFAULT_STATIC_ROOT / "data" / "canonical_web"


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--static-root", type=Path, default=DEFAULT_STATIC_ROOT)
    parser.add_argument("--canonical-web-dir", type=Path, default=DEFAULT_CANONICAL_WEB_DIR)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8130)
    parser.add_argument("--enable-canonical-web", action="store_true")
    parser.add_argument("--enable-primary-catalog", action="store_true")
    parser.add_argument("--enable-trace-runtime", action="store_true")
    parser.add_argument("--enable-filtered-trace-aggregation", action="store_true")
    parser.add_argument(
        "--use-canonical-packed-points",
        action="store_true",
        help="Point packedPoints metadata/binary URLs at /data/canonical_web. Implied by --enable-primary-catalog.",
    )
    parser.add_argument("--no-gzip", action="store_true", help="Do not serve .gz siblings.")
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-request logs for detached local browser QA.",
    )
    return parser


def build_preview_app_config(
    base_config: dict[str, Any],
    *,
    enable_canonical_web: bool = False,
    enable_primary_catalog: bool = False,
    enable_trace_runtime: bool = False,
    enable_filtered_trace_aggregation: bool = False,
    use_canonical_packed_points: bool = False,
) -> dict[str, Any]:
    config = dict(base_config)
    if enable_primary_catalog or use_canonical_packed_points:
        packed_points_config = dict(config.get("packedPoints") or {})
        packed_points_config.update(
            {
                "enabled": True,
                "metadataUrl": "/data/canonical_web/points_meta.json",
                "binaryUrl": "/data/canonical_web/points.bin",
                "mapLayerMode": "all",
            }
        )
        config["packedPoints"] = packed_points_config

    canonical_config = dict(config.get("canonicalWebArtifacts") or {})
    canonical_config.setdefault("filteredTraceAggregation", False)
    if enable_canonical_web or enable_primary_catalog or enable_trace_runtime or enable_filtered_trace_aggregation:
        canonical_config.update(
            {
                "enabled": True,
                "manifestUrl": "/data/canonical_web/canonical_web_manifest.json",
                "chunkManifestUrl": "/data/canonical_web/event_chunk_manifest.json",
                "eventChunksBaseUrl": "/data/canonical_web/event_chunks/",
                "summaryManifestUrl": "/data/canonical_web/summary_manifest.json",
                "summaryShardsBaseUrl": "/data/canonical_web/summary_shards/",
                "primaryCatalog": bool(enable_primary_catalog),
                "traceRuntime": bool(enable_trace_runtime),
                "filteredTraceAggregation": bool(enable_filtered_trace_aggregation),
            }
        )
    config["canonicalWebArtifacts"] = canonical_config
    return config


def load_json_with_optional_bom(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def safe_resolve_under(root: Path, relative_url_path: str) -> Path:
    root = root.resolve()
    raw_path = unquote(relative_url_path).replace("\\", "/")
    raw_parts = [part for part in raw_path.split("/") if part not in ("", ".")]
    if any(part == ".." for part in raw_parts):
        raise ValueError(f"Requested path escapes static root: {relative_url_path}")
    clean_path = posixpath.normpath("/".join(raw_parts)).lstrip("/")
    if clean_path in ("", "."):
        clean_path = "index.html"
    candidate = (root / Path(*clean_path.split("/"))).resolve()
    if root != candidate and root not in candidate.parents:
        raise ValueError(f"Requested path escapes static root: {relative_url_path}")
    return candidate


def select_served_file(file_path: Path, accept_encoding: str, *, prefer_gzip: bool = True) -> tuple[Path, str | None]:
    if prefer_gzip and "gzip" in accept_encoding.lower():
        gzip_path = file_path.with_name(f"{file_path.name}.gz")
        if gzip_path.exists() and gzip_path.is_file():
            return gzip_path, "gzip"
    return file_path, None


class CanonicalPreviewHandler(BaseHTTPRequestHandler):
    server_version = "UfoTimelineCanonicalPreview/1.0"
    protocol_version = "HTTP/1.1"
    file_copy_chunk_size = 1024 * 256

    def __init__(
        self,
        *args: Any,
        static_root: Path,
        canonical_web_dir: Path,
        enable_canonical_web: bool,
        enable_primary_catalog: bool,
        enable_trace_runtime: bool,
        enable_filtered_trace_aggregation: bool,
        use_canonical_packed_points: bool,
        prefer_gzip: bool,
        quiet: bool = False,
        **kwargs: Any,
    ) -> None:
        self.static_root = static_root.resolve()
        self.canonical_web_dir = canonical_web_dir.resolve()
        self.enable_canonical_web = enable_canonical_web
        self.enable_primary_catalog = enable_primary_catalog
        self.enable_trace_runtime = enable_trace_runtime
        self.enable_filtered_trace_aggregation = enable_filtered_trace_aggregation
        self.use_canonical_packed_points = use_canonical_packed_points
        self.prefer_gzip = prefer_gzip
        self.quiet = quiet
        super().__init__(*args, **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        if self.quiet:
            return
        super().log_message(format, *args)

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlparse(self.path)
        request_path = parsed.path or "/"
        try:
            if request_path == "/":
                request_path = "/index.html"
            if request_path == "/data/app_config.json":
                self._serve_app_config()
                return
            if request_path.startswith("/data/canonical_web/"):
                relative = request_path.removeprefix("/data/canonical_web/")
                self._serve_file(safe_resolve_under(self.canonical_web_dir, relative))
                return
            self._serve_file(safe_resolve_under(self.static_root, request_path))
        except ValueError as exc:
            self.send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _serve_app_config(self) -> None:
        config_path = self.static_root / "data" / "app_config.json"
        if not config_path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "Missing static_bundle/data/app_config.json")
            return
        base_config = load_json_with_optional_bom(config_path)
        config = build_preview_app_config(
            base_config,
            enable_canonical_web=self.enable_canonical_web,
            enable_primary_catalog=self.enable_primary_catalog,
            enable_trace_runtime=self.enable_trace_runtime,
            enable_filtered_trace_aggregation=self.enable_filtered_trace_aggregation,
            use_canonical_packed_points=self.use_canonical_packed_points,
        )
        payload = json.dumps(config, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _serve_file(self, file_path: Path) -> None:
        if file_path.is_dir():
            file_path = file_path / "index.html"
        if not file_path.exists() or not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return
        served_path, content_encoding = select_served_file(
            file_path,
            self.headers.get("Accept-Encoding", ""),
            prefer_gzip=self.prefer_gzip,
        )
        content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(served_path.stat().st_size))
        self.send_header("Cache-Control", "no-store")
        if content_encoding:
            self.send_header("Content-Encoding", content_encoding)
            self.send_header("Vary", "Accept-Encoding")
        self.end_headers()
        try:
            with served_path.open("rb") as handle:
                while True:
                    chunk = handle.read(self.file_copy_chunk_size)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            # Browsers can cancel speculative or superseded requests. Treat that as
            # a client-side abort, not a preview-server failure.
            return


class CanonicalPreviewServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def serve(
    *,
    static_root: Path,
    canonical_web_dir: Path,
    host: str,
    port: int,
    enable_canonical_web: bool,
    enable_primary_catalog: bool,
    enable_trace_runtime: bool,
    enable_filtered_trace_aggregation: bool,
    use_canonical_packed_points: bool,
    prefer_gzip: bool,
    quiet: bool = False,
) -> None:
    if not static_root.exists():
        raise FileNotFoundError(f"Static root does not exist: {static_root}")
    if not canonical_web_dir.exists() and (
        enable_canonical_web or enable_primary_catalog or enable_trace_runtime or enable_filtered_trace_aggregation
    ):
        raise FileNotFoundError(f"Canonical web artifact directory does not exist: {canonical_web_dir}")
    handler = partial(
        CanonicalPreviewHandler,
        static_root=static_root,
        canonical_web_dir=canonical_web_dir,
        enable_canonical_web=enable_canonical_web,
        enable_primary_catalog=enable_primary_catalog,
        enable_trace_runtime=enable_trace_runtime,
        enable_filtered_trace_aggregation=enable_filtered_trace_aggregation,
        use_canonical_packed_points=use_canonical_packed_points or enable_primary_catalog,
        prefer_gzip=prefer_gzip,
        quiet=quiet,
    )
    server = CanonicalPreviewServer((host, port), handler)
    url = f"http://{host}:{port}/index.html"
    print(f"Serving UFO Timeline preview at {url}")
    print(f"static_root={static_root.resolve()}")
    print(f"canonical_web_dir={canonical_web_dir.resolve()}")
    if enable_canonical_web or enable_primary_catalog or enable_trace_runtime or enable_filtered_trace_aggregation:
        print(
            "canonicalWebArtifacts overrides: "
            f"enabled={enable_canonical_web or enable_primary_catalog or enable_trace_runtime or enable_filtered_trace_aggregation}, "
            f"primaryCatalog={enable_primary_catalog}, "
            f"traceRuntime={enable_trace_runtime}, "
            f"filteredTraceAggregation={enable_filtered_trace_aggregation}"
        )
    if enable_primary_catalog or use_canonical_packed_points:
        print("packedPoints override: /data/canonical_web/points_meta.json + /data/canonical_web/points.bin")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping preview server.")
    finally:
        server.server_close()


def main() -> int:
    args = build_argument_parser().parse_args()
    serve(
        static_root=args.static_root,
        canonical_web_dir=args.canonical_web_dir,
        host=args.host,
        port=args.port,
        enable_canonical_web=args.enable_canonical_web,
        enable_primary_catalog=args.enable_primary_catalog,
        enable_trace_runtime=args.enable_trace_runtime,
        enable_filtered_trace_aggregation=args.enable_filtered_trace_aggregation,
        use_canonical_packed_points=args.use_canonical_packed_points,
        prefer_gzip=not args.no_gzip,
        quiet=args.quiet,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
