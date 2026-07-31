"""Create a Cloudflare Pages/R2 friendly static payload.

Pages gets the app shell and small metadata. Large canonical artifacts are
omitted from Pages by default and can be served from an R2 base URL.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


PAGES_FILE_LIMIT_BYTES = 25 * 1024 * 1024
DEFAULT_OUTPUT_ROOT = Path("cloudflare_bundle")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--static-root", type=Path, default=Path("static_bundle"))
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--r2-base-url", default="", help="Optional absolute base URL for large data artifacts.")
    parser.add_argument(
        "--r2-key-prefix",
        default="",
        help="Optional immutable R2 key prefix, for example releases/2026-07-20.",
    )
    parser.add_argument("--include-gzip-data", action="store_true", help="Keep gzip data artifacts under the Pages file limit.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    r2_key_prefix = normalize_r2_key_prefix(args.r2_key_prefix)
    validate_r2_prefix_url(args.r2_base_url, r2_key_prefix)
    if args.output_root.exists():
        shutil.rmtree(args.output_root)
    args.output_root.mkdir(parents=True)

    copied: list[dict[str, Any]] = []
    omitted: list[dict[str, Any]] = []
    for source in args.static_root.rglob("*"):
      if not source.is_file():
          continue
      relative = source.relative_to(args.static_root)
      decision = classify_file(relative, source.stat().st_size, include_gzip_data=args.include_gzip_data)
      if decision["copy"]:
          target = args.output_root / relative
          target.parent.mkdir(parents=True, exist_ok=True)
          shutil.copy2(source, target)
          copied.append({"path": str(relative).replace("\\", "/"), "bytes": source.stat().st_size})
      else:
          omitted.append({
              "path": str(relative).replace("\\", "/"),
              "bytes": source.stat().st_size,
              "reason": decision["reason"],
          })

    config_path = args.output_root / "data" / "app_config.json"
    if config_path.exists():
        config = read_json(config_path)
        rewrite_config_for_cloudflare(config, args.r2_base_url)
        write_json(config_path, config)

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "static_root": str(args.static_root),
        "output_root": str(args.output_root),
        "pages_file_limit_bytes": PAGES_FILE_LIMIT_BYTES,
        "r2_base_url": args.r2_base_url,
        "r2_key_prefix": r2_key_prefix,
        "include_gzip_data": bool(args.include_gzip_data),
        "pages_safe": all(item["bytes"] <= PAGES_FILE_LIMIT_BYTES for item in copied),
        "copied_file_count": len(copied),
        "omitted_file_count": len(omitted),
        "max_copied_file_bytes": max((item["bytes"] for item in copied), default=0),
        "copied": copied,
        "omitted": omitted,
    }
    r2_manifest = build_r2_upload_manifest(
        copied,
        omitted,
        args.r2_base_url,
        args.static_root,
        r2_key_prefix=r2_key_prefix,
    )
    write_cloudflare_headers(args.output_root)
    write_json(args.output_root / "r2_upload_manifest.json", r2_manifest)
    write_r2_upload_script(args.output_root, r2_manifest)
    write_json(args.output_root / "cloudflare_bundle_manifest.json", report)
    print(json.dumps({
        "output": str(args.output_root),
        "pages_safe": report["pages_safe"],
        "copied_file_count": len(copied),
        "omitted_file_count": len(omitted),
        "max_copied_file_bytes": report["max_copied_file_bytes"],
    }, indent=2))


def classify_file(relative: Path, size: int, *, include_gzip_data: bool) -> dict[str, Any]:
    parts = relative.parts
    path_text = str(relative).replace("\\", "/")
    if size > PAGES_FILE_LIMIT_BYTES:
        return {"copy": False, "reason": "exceeds_cloudflare_pages_25_mib_limit"}
    if len(parts) >= 2 and parts[0] == "data" and parts[1] == "canonical_web":
        if include_gzip_data and path_text.endswith(".gz"):
            return {"copy": True, "reason": "gzip_data_under_pages_limit"}
        if path_text.endswith(".gz"):
            return {"copy": False, "reason": "gzip_canonical_dataset_for_r2"}
        if any(token in path_text for token in ("/event_chunks/", "/summary_shards/")):
            return {"copy": False, "reason": "large_canonical_dataset_for_r2"}
        if path_text.endswith(".bin"):
            return {"copy": False, "reason": "raw_binary_excluded_for_r2_or_gzip_variant"}
    return {"copy": True, "reason": "pages_asset"}


def rewrite_config_for_cloudflare(config: dict[str, Any], r2_base_url: str) -> None:
    deployment = {
        "target": "cloudflare_pages_r2",
        "largeDataBaseUrl": r2_base_url,
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "notes": [
            "Cloudflare Pages should host app shell and small manifests.",
            "Large canonical artifacts should live on R2 or be served as gzip artifacts under the Pages file limit.",
        ],
    }
    config["deploymentProfile"] = deployment
    if not r2_base_url:
        return
    base = r2_base_url.rstrip("/") + "/"
    packed = config.get("packedPoints")
    if isinstance(packed, dict):
        packed["metadataUrl"] = base + "data/canonical_web/points_meta.json"
        packed["binaryUrl"] = base + "data/canonical_web/points.bin"
    canonical = config.get("canonicalWebArtifacts")
    if isinstance(canonical, dict):
        canonical["manifestUrl"] = base + "data/canonical_web/canonical_web_manifest.json"
        canonical["chunkManifestUrl"] = base + "data/canonical_web/event_chunk_manifest.json"
        canonical["eventChunksBaseUrl"] = base + "data/canonical_web/event_chunks/"
        canonical["summaryManifestUrl"] = base + "data/canonical_web/summary_manifest.json"
        canonical["summaryShardsBaseUrl"] = base + "data/canonical_web/summary_shards/"
    startup_profile = config.get("startupProfile")
    if isinstance(startup_profile, dict) and startup_profile.get("manifestUrl"):
        # Keep startup profile on Pages unless the caller explicitly moves it.
        startup_profile.setdefault("deployment", "pages")


def build_r2_upload_manifest(
    copied: list[dict[str, Any]],
    omitted: list[dict[str, Any]],
    r2_base_url: str,
    static_root: Path,
    *,
    r2_key_prefix: str = "",
) -> dict[str, Any]:
    by_path: dict[str, dict[str, Any]] = {}
    for item in [*copied, *omitted]:
        path = item["path"]
        if not path.startswith("data/canonical_web/"):
            continue
        by_path[path] = {
            "path": path,
            "bytes": item["bytes"],
            "r2_key": prefixed_r2_key(path, r2_key_prefix),
            "source_path": str(static_root / Path(path)),
            "url": (r2_base_url.rstrip("/") + "/" + path) if r2_base_url else "",
            "content_type": content_type_for_path(path),
            # The runtime explicitly fetches .gz siblings and decompresses them
            # with DecompressionStream. Do not mark R2 objects with
            # Content-Encoding:gzip, or browsers will auto-decompress the body
            # before the app's manual decoder sees it.
            "content_encoding": "",
            "cache_control": "public, max-age=31536000, immutable",
            "copied_to_pages": any(copied_item["path"] == path for copied_item in copied),
        }
    canonical_uploads = [
        by_path[path]
        for path in sorted(by_path)
        if should_upload_canonical_r2_path(path, by_path)
    ]
    return {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "r2_base_url": r2_base_url,
        "r2_key_prefix": r2_key_prefix,
        "upload_count": len(canonical_uploads),
        "upload_bytes": sum(int(item["bytes"]) for item in canonical_uploads),
        "uploads": canonical_uploads,
        "notes": [
            "Upload these omitted canonical data artifacts to R2 using the same relative keys.",
            "The app will prefer .gz siblings for JSON/binary artifacts where supported.",
            "Keep data artifact URLs versioned or immutable; update app_config only when the data version changes.",
        ],
    }


def normalize_r2_key_prefix(value: str) -> str:
    normalized = str(value or "").strip().replace("\\", "/").strip("/")
    if not normalized:
        return ""
    parts = normalized.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"Invalid R2 key prefix: {value!r}")
    return "/".join(parts)


def prefixed_r2_key(path: str, prefix: str) -> str:
    return f"{prefix}/{path}" if prefix else path


def validate_r2_prefix_url(r2_base_url: str, prefix: str) -> None:
    if not prefix or not r2_base_url:
        return
    base_path = urlsplit(r2_base_url).path.strip("/")
    if base_path != prefix and not base_path.endswith("/" + prefix):
        raise ValueError(
            "R2 base URL path must end with the R2 key prefix: "
            f"base={r2_base_url!r}, prefix={prefix!r}"
        )


def should_upload_canonical_r2_path(path: str, all_paths: dict[str, dict[str, Any]]) -> bool:
    if path.endswith(".gz"):
        base_path = path[:-3]
        return (
            "/event_chunks/" in base_path or
            "/summary_shards/" in base_path or
            base_path.endswith(".bin")
        )
    gzip_sibling = path + ".gz"
    if gzip_sibling in all_paths and (
        "/event_chunks/" in path or
        "/summary_shards/" in path or
        path.endswith(".bin")
    ):
        return False
    return True


def content_type_for_path(path: str) -> str:
    path_without_gzip = path[:-3] if path.endswith(".gz") else path
    if path_without_gzip.endswith(".json"):
        return "application/json; charset=utf-8"
    if path_without_gzip.endswith(".bin"):
        return "application/octet-stream"
    if path_without_gzip.endswith(".csv"):
        return "text/csv; charset=utf-8"
    return "application/octet-stream"


def powershell_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def write_r2_upload_script(output_root: Path, r2_manifest: dict[str, Any]) -> None:
    uploads = r2_manifest.get("uploads") if isinstance(r2_manifest, dict) else []
    lines = [
        "# Generated by scripts/build_cloudflare_bundle.py.",
        "# Uploads canonical data artifacts to Cloudflare R2 with the headers the browser expects.",
        "param(",
        "  [Parameter(Mandatory=$true)][string]$BucketName,",
        "  [string]$Wrangler = '',",
        "  [string]$Node = '',",
        "  [string]$WranglerJs = ''",
        ")",
        "$ErrorActionPreference = 'Stop'",
        "$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')",
        "Push-Location $RepoRoot",
        "try {",
        "if (-not $Node) {",
        "  $NodeCandidate = Join-Path $env:ProgramFiles 'nodejs\\node.exe'",
        "  if (Test-Path -LiteralPath $NodeCandidate) { $Node = $NodeCandidate }",
        "}",
        "if (-not $WranglerJs) {",
        "  $WranglerJsCandidate = Join-Path $RepoRoot 'node_modules\\wrangler\\bin\\wrangler.js'",
        "  if (Test-Path -LiteralPath $WranglerJsCandidate) { $WranglerJs = $WranglerJsCandidate }",
        "}",
        "$nodeOptions = [Environment]::GetEnvironmentVariable('NODE_OPTIONS', 'Process')",
        "if (-not $nodeOptions) {",
        "  $env:NODE_OPTIONS = '--use-system-ca'",
        "} elseif ($nodeOptions -notmatch '(^|\\s)--use-system-ca(\\s|$)') {",
        "  $env:NODE_OPTIONS = \"$nodeOptions --use-system-ca\"",
        "}",
        "function Invoke-LocalWrangler {",
        "  param([string[]]$Arguments)",
        "  $maxAttempts = 4",
        "  for ($Attempt = 1; $Attempt -le $maxAttempts; $Attempt++) {",
        "    if ($Wrangler) { & $Wrangler @Arguments }",
        "    elseif ($Node -and $WranglerJs) { & $Node $WranglerJs @Arguments }",
        "    else { & wrangler @Arguments }",
        "    if ($LASTEXITCODE -eq 0) { return }",
        "    if ($Attempt -lt $maxAttempts) {",
        "      $delay = [Math]::Min(10, $Attempt * 2)",
        "      Write-Warning \"Wrangler failed with exit code $LASTEXITCODE on attempt $Attempt/$maxAttempts. Retrying in $delay seconds.\"",
        "      Start-Sleep -Seconds $delay",
        "    }",
        "  }",
        "  throw \"Wrangler failed with exit code $LASTEXITCODE for: $($Arguments -join ' ')\"",
        "}",
        "$Uploads = @(",
    ]
    for item in uploads:
        lines.append(
            "  @{ Source = " + powershell_quote(str(item.get("source_path", ""))) +
            "; Key = " + powershell_quote(str(item.get("r2_key", ""))) +
            "; ContentType = " + powershell_quote(str(item.get("content_type", "application/octet-stream"))) +
            "; ContentEncoding = " + powershell_quote(str(item.get("content_encoding", ""))) +
            "; CacheControl = " + powershell_quote(str(item.get("cache_control", "public, max-age=31536000, immutable"))) + " }"
        )
    lines.extend([
        ")",
        "foreach ($Upload in $Uploads) {",
        "  $Source = $Upload.Source",
        "  $ResolvedSource = Join-Path $RepoRoot $Source",
        "  if (!(Test-Path -LiteralPath $ResolvedSource)) { throw \"Missing R2 source file: $ResolvedSource\" }",
        "  $Args = @('r2', 'object', 'put', \"$BucketName/$($Upload.Key)\", '--remote', '--file', $Source, '--content-type', $Upload.ContentType)",
        "  if ($Upload.ContentEncoding) { $Args += @('--content-encoding', $Upload.ContentEncoding) }",
        "  if ($Upload.CacheControl) { $Args += @('--cache-control', $Upload.CacheControl) }",
        "  Write-Host \"Uploading $($Upload.Key)\"",
        "  Invoke-LocalWrangler -Arguments $Args",
        "  Start-Sleep -Milliseconds 150",
        "}",
        "} finally {",
        "  Pop-Location",
        "}",
        "Write-Host \"Uploaded $($Uploads.Count) canonical artifacts to bucket $BucketName.\"",
        "",
    ])
    (output_root / "upload_r2_assets.ps1").write_text("\n".join(lines), encoding="utf-8")


def write_cloudflare_headers(output_root: Path) -> None:
    headers = """# Cloudflare Pages cache policy for UFO Timeline static deployment.

/index.html
  Cache-Control: public, max-age=0, must-revalidate

/app.js
  Cache-Control: public, max-age=0, must-revalidate

/startup_profile_worker.js
  Cache-Control: public, max-age=0, must-revalidate

/catalog_filter_worker.js
  Cache-Control: public, max-age=0, must-revalidate

/trace_facility_worker.js
  Cache-Control: public, max-age=0, must-revalidate

/styles.css
  Cache-Control: public, max-age=0, must-revalidate

/data/app_config.json
  Cache-Control: public, max-age=0, must-revalidate

/data/startup_profiles/*
  Cache-Control: public, max-age=31536000, immutable

/data/canonical_web/*
  Cache-Control: public, max-age=31536000, immutable

/vendor/*
  Cache-Control: public, max-age=31536000, immutable
"""
    (output_root / "_headers").write_text(headers, encoding="utf-8")


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")


if __name__ == "__main__":
    main()
