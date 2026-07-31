"""Validate a Cloudflare Pages/R2 bundle before public upload."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PLACEHOLDER_R2_HOSTS = (
    "example-r2.invalid",
    "example.r2.dev",
    "example.com",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", type=Path, default=Path("cloudflare_bundle_r2"))
    parser.add_argument(
        "--allow-placeholder-r2",
        action="store_true",
        help="Allow placeholder R2 URLs. Use only for local tests, never for public deployment.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = validate_bundle(args.bundle_root, allow_placeholder_r2=args.allow_placeholder_r2)
    print(json.dumps(report, indent=2, sort_keys=True))
    if not report["ok"]:
        raise SystemExit(1)


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_bundle(bundle_root: Path, *, allow_placeholder_r2: bool = False) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    errors: list[str] = []

    bundle_manifest_path = bundle_root / "cloudflare_bundle_manifest.json"
    r2_manifest_path = bundle_root / "r2_upload_manifest.json"
    app_config_path = bundle_root / "data" / "app_config.json"
    headers_path = bundle_root / "_headers"

    checks["bundle_manifest_exists"] = bundle_manifest_path.exists()
    checks["r2_manifest_exists"] = r2_manifest_path.exists()
    checks["app_config_exists"] = app_config_path.exists()
    checks["headers_exists"] = headers_path.exists()

    for name, passed in checks.items():
        if not passed:
            errors.append(f"Missing required Cloudflare bundle file: {name}")

    bundle_manifest = read_json(bundle_manifest_path) if bundle_manifest_path.exists() else {}
    r2_manifest = read_json(r2_manifest_path) if r2_manifest_path.exists() else {}
    app_config = read_json(app_config_path) if app_config_path.exists() else {}
    headers = headers_path.read_text(encoding="utf-8") if headers_path.exists() else ""

    checks["pages_safe"] = bool(bundle_manifest.get("pages_safe"))
    if not checks["pages_safe"]:
        errors.append("Cloudflare bundle manifest is not Pages-safe.")

    checks["startup_profiles_cached"] = "/data/startup_profiles/*" in headers and "immutable" in headers
    if not checks["startup_profiles_cached"]:
        errors.append("Cloudflare _headers is missing immutable startup profile cache rules.")

    deployment_profile = app_config.get("deploymentProfile") if isinstance(app_config, dict) else {}
    large_data_url = str(deployment_profile.get("largeDataBaseUrl") or "")
    r2_base_url = str(r2_manifest.get("r2_base_url") or "")
    r2_key_prefix = str(r2_manifest.get("r2_key_prefix") or "").strip("/")
    upload_count = int(r2_manifest.get("upload_count") or 0)
    uploads = r2_manifest.get("uploads") if isinstance(r2_manifest.get("uploads"), list) else []

    checks["r2_upload_manifest_has_uploads"] = upload_count > 0
    if not checks["r2_upload_manifest_has_uploads"]:
        errors.append("R2 upload manifest has no canonical data uploads.")

    checks["r2_base_url_present"] = bool(r2_base_url)
    if not checks["r2_base_url_present"]:
        errors.append("R2 base URL is empty; large canonical artifacts will not resolve from public Pages.")

    placeholder_hits = [
        host
        for host in PLACEHOLDER_R2_HOSTS
        if host in r2_base_url or host in large_data_url
    ]
    checks["r2_base_url_not_placeholder"] = allow_placeholder_r2 or not placeholder_hits
    if not checks["r2_base_url_not_placeholder"]:
        errors.append("R2 base URL still uses placeholder host(s): " + ", ".join(placeholder_hits))

    expected_keys = [
        f"{r2_key_prefix}/{item.get('path')}" if r2_key_prefix else str(item.get("path") or "")
        for item in uploads
        if isinstance(item, dict)
    ]
    actual_keys = [str(item.get("r2_key") or "") for item in uploads if isinstance(item, dict)]
    checks["r2_keys_match_prefix"] = actual_keys == expected_keys
    if not checks["r2_keys_match_prefix"]:
        errors.append("R2 upload keys do not match the declared immutable key prefix.")

    base_path = r2_base_url.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    checks["r2_base_url_matches_prefix"] = not r2_key_prefix or base_path.endswith("/" + r2_key_prefix)
    if not checks["r2_base_url_matches_prefix"]:
        errors.append("R2 base URL path does not end with the declared immutable key prefix.")

    return {
        "ok": not errors,
        "bundle_root": str(bundle_root),
        "checks": checks,
        "r2_base_url": r2_base_url,
        "r2_key_prefix": r2_key_prefix,
        "upload_count": upload_count,
        "errors": errors,
    }


if __name__ == "__main__":
    main()
