"""Check staged static loadout consistency for the canonical web app.

This report is intentionally read-only. It verifies that the shipped static
bundle points at the staged canonical payload, that critical startup files are
present, and that manifest/config row counts agree.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_PAYLOAD_ROOT = Path("static_bundle")
DEFAULT_ZIP = Path("static_bundle.zip")
DEFAULT_OUTPUT = Path("data/reports/static_loadout_readiness.json")


def check_static_loadout_readiness(*, payload_root: Path, zip_path: Path | None = None) -> dict[str, Any]:
    payload_root = payload_root.resolve()
    app_config_path = payload_root / "data" / "app_config.json"
    payload_manifest_path = payload_root / "canonical_web_static_payload_manifest.json"
    canonical_dir = payload_root / "data" / "canonical_web"
    canonical_manifest_path = canonical_dir / "canonical_web_manifest.json"
    points_meta_path = canonical_dir / "points_meta.json"
    points_bin_path = canonical_dir / "points.bin"
    points_gzip_path = canonical_dir / "points.bin.gz"
    summary_manifest_path = canonical_dir / "summary_manifest.json"
    first_summary_gzip_path = canonical_dir / "summary_shards" / "summary_000000.json.gz"

    app_config = read_json(app_config_path)
    payload_manifest = read_json(payload_manifest_path)
    canonical_manifest = read_json(canonical_manifest_path)
    points_meta = read_json(points_meta_path)
    summary_manifest = read_json_value(summary_manifest_path)

    config_points = app_config.get("packedPoints") if isinstance(app_config.get("packedPoints"), dict) else {}
    manifest_counts = canonical_manifest.get("counts") if isinstance(canonical_manifest.get("counts"), dict) else {}
    payload_counts = payload_manifest.get("app_config_sync") if isinstance(payload_manifest.get("app_config_sync"), dict) else {}

    expected_point_rows = int_or_none(manifest_counts.get("mapped_events"))
    config_point_rows = int_or_none(config_points.get("rowCount"))
    metadata_point_rows = int_or_none(points_meta.get("row_count"))
    payload_point_rows = int_or_none(payload_counts.get("packedPointsRowCount"))

    critical_files = {
        "app_config": app_config_path,
        "payload_manifest": payload_manifest_path,
        "canonical_manifest": canonical_manifest_path,
        "points_meta": points_meta_path,
        "points_bin": points_bin_path,
        "points_bin_gzip": points_gzip_path,
        "summary_manifest": summary_manifest_path,
        "first_summary_gzip": first_summary_gzip_path,
    }
    critical_file_status = {
        name: {"path": str(path), "exists": path.exists(), "bytes": path.stat().st_size if path.exists() else 0}
        for name, path in critical_files.items()
    }

    row_parity_ok = (
        expected_point_rows is not None
        and config_point_rows == expected_point_rows
        and metadata_point_rows == expected_point_rows
        and payload_point_rows == expected_point_rows
    )
    binary_size_ok = (
        metadata_point_rows is not None
        and int_or_none(points_meta.get("bytes_per_row")) is not None
        and points_bin_path.exists()
        and points_bin_path.stat().st_size == metadata_point_rows * int(points_meta["bytes_per_row"])
    )
    canonical_config_promoted = bool((app_config.get("canonicalWebArtifacts") or {}).get("primaryCatalog"))
    packed_points_canonical = (
        config_points.get("metadataUrl") == "./data/canonical_web/points_meta.json"
        and config_points.get("binaryUrl") == "./data/canonical_web/points.bin"
    )
    gzip_present = points_gzip_path.exists() and first_summary_gzip_path.exists()
    all_critical_files_present = all(item["exists"] for item in critical_file_status.values())

    zip_summary = None
    if zip_path is not None:
        zip_path = zip_path.resolve()
        zip_summary = {"path": str(zip_path), "exists": zip_path.exists(), "bytes": zip_path.stat().st_size if zip_path.exists() else 0}

    checks = {
        "all_critical_files_present": all_critical_files_present,
        "canonical_config_promoted": canonical_config_promoted,
        "packed_points_use_canonical_paths": packed_points_canonical,
        "row_parity_ok": row_parity_ok,
        "points_binary_size_ok": binary_size_ok,
        "gzip_startup_assets_present": gzip_present,
        "zip_exists": True if zip_summary is None else bool(zip_summary["exists"]),
    }
    return {
        "schema_version": 1,
        "report_policy": "static_loadout_readiness_report_only",
        "canonical_outputs_mutated": False,
        "payload_root": str(payload_root),
        "status": "ready" if all(checks.values()) else "needs_attention",
        "checks": checks,
        "counts": {
            "manifest_events": int_or_none(manifest_counts.get("events")),
            "manifest_mapped_events": expected_point_rows,
            "app_config_normalized_count": int_or_none(app_config.get("normalizedCount")),
            "app_config_mapped_count": int_or_none(app_config.get("mappedCount")),
            "packed_points_config_rows": config_point_rows,
            "packed_points_metadata_rows": metadata_point_rows,
            "payload_manifest_packed_point_rows": payload_point_rows,
            "summary_shards": summary_shard_count(summary_manifest),
            "payload_files": int_or_none(payload_manifest.get("file_count")),
            "payload_raw_bytes": int_or_none(payload_manifest.get("raw_bytes")),
            "payload_gzip_bytes": int_or_none(payload_manifest.get("gzip_bytes")),
        },
        "critical_files": critical_file_status,
        "zip": zip_summary,
        "notes": [
            "This report verifies the staged static loadout only; it does not mutate data or app config.",
            "Packed points must use canonical_web paths so the map does not fall back to the legacy 34k startup point file.",
        ],
    }


def int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def read_json(path: Path) -> dict[str, Any]:
    payload = read_json_value(path)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def read_json_value(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def summary_shard_count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        return len(value.get("shards") or [])
    return 0


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload-root", type=Path, default=DEFAULT_PAYLOAD_ROOT)
    parser.add_argument("--zip", type=Path, default=DEFAULT_ZIP)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = check_static_loadout_readiness(payload_root=args.payload_root, zip_path=args.zip)
    report["outputs"] = {"json": str(args.output)}
    write_json(args.output, report)
    print(json.dumps({
        "json": str(args.output),
        "status": report["status"],
        "manifest_mapped_events": report["counts"]["manifest_mapped_events"],
        "packed_points_metadata_rows": report["counts"]["packed_points_metadata_rows"],
        "zip_bytes": report["zip"]["bytes"] if report.get("zip") else None,
        "canonical_outputs_mutated": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
