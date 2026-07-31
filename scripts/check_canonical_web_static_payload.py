"""Validate an opt-in staged canonical web static payload.

This validates packaging/deployment shape only. It does not enable canonical
web artifacts in the checked-in app config and does not exercise browser
runtime behavior.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SUPPORTED_MODES = {
    "trace-runtime",
    "startup-preview",
    "primary-catalog-trace-runtime",
    "primary-catalog-trace-runtime-with-details",
}

BASE_REQUIRED_FILES = {
    "data/canonical_web/canonical_web_manifest.json",
    "data/canonical_web/event_chunk_manifest.json",
    "data/canonical_web/summary_manifest.json",
}

TRACE_RUNTIME_REQUIRED_FILES = {
    "data/canonical_web/trace_event_index.bin",
    "data/canonical_web/trace_event_index_meta.json",
    "data/canonical_web/trace_segments.bin",
    "data/canonical_web/trace_segments_meta.json",
    "data/canonical_web/trace_aggregate_bins.bin",
    "data/canonical_web/trace_aggregate_bins_meta.json",
}

POINT_REQUIRED_FILES = {
    "data/canonical_web/points.bin",
    "data/canonical_web/points_meta.json",
}

CANONICAL_FLAGS = (
    "enabled",
    "primaryCatalog",
    "traceRuntime",
    "filteredTraceAggregation",
)

PROVENANCE_ONLY_PATH_MARKERS = (
    "source_records",
    "source_claims",
    "raw_source",
    "raw_fields",
    "canonical_input_events",
    "duplicate_candidates",
    "duplicate_groups",
)


def check_canonical_web_static_payload(
    payload_root: Path,
    *,
    static_bundle_root: Path | None = Path("static_bundle"),
    expected_canonical_config: str = "disabled",
) -> dict[str, Any]:
    payload_root = payload_root.resolve()
    manifest_path = payload_root / "canonical_web_static_payload_manifest.json"
    target_dir = payload_root / "data" / "canonical_web"
    payload_manifest = _read_json_if_exists(manifest_path)
    files = payload_manifest.get("files", []) if isinstance(payload_manifest, dict) else []
    copied_paths = {str(item.get("path", "")).replace("\\", "/") for item in files if isinstance(item, dict)}
    mode = str(payload_manifest.get("mode", "")) if isinstance(payload_manifest, dict) else ""

    file_size_mismatches = _file_size_mismatches(payload_root, files)
    gzip_entries = sorted(path for path in copied_paths if path.endswith(".gz"))
    gzip_raw_siblings_missing = [
        path for path in gzip_entries if path.removesuffix(".gz") not in copied_paths
    ]
    provenance_only_paths = sorted(
        path for path in copied_paths if any(marker in path for marker in PROVENANCE_ONLY_PATH_MARKERS)
    )
    default_config = _read_static_bundle_app_config(static_bundle_root)

    required_files = set(BASE_REQUIRED_FILES)
    if mode in {"trace-runtime", "startup-preview", "primary-catalog-trace-runtime", "primary-catalog-trace-runtime-with-details"}:
        required_files.update(TRACE_RUNTIME_REQUIRED_FILES)
    if mode in {"startup-preview", "primary-catalog-trace-runtime-with-details"}:
        required_files.update(POINT_REQUIRED_FILES)

    summary_shards = sorted(path for path in copied_paths if path.startswith("data/canonical_web/summary_shards/"))
    detail_chunks = sorted(path for path in copied_paths if path.startswith("data/canonical_web/event_chunks/"))
    mode_required_missing = sorted(required_files - copied_paths)

    config_expectation_met = _canonical_config_matches(default_config, expected_canonical_config)
    checks = {
        "payload_manifest_exists": manifest_path.exists(),
        "target_dir_exists": target_dir.exists(),
        "mode_supported": mode in SUPPORTED_MODES,
        "manifest_file_count_matches": len(files) == int(payload_manifest.get("file_count", -1))
        if isinstance(payload_manifest, dict)
        else False,
        "copied_files_exist": bool(files) and not [path for path in copied_paths if not (payload_root / path).is_file()],
        "copied_file_sizes_match": not file_size_mismatches,
        "base_manifests_present": BASE_REQUIRED_FILES.issubset(copied_paths),
        "mode_required_files_present": not mode_required_missing,
        "primary_payload_has_summary_shards": (
            mode not in {"primary-catalog-trace-runtime", "primary-catalog-trace-runtime-with-details"}
            or bool(summary_shards)
        ),
        "full_detail_payload_has_event_chunks": mode != "primary-catalog-trace-runtime-with-details" or bool(detail_chunks),
        "lean_payload_omits_event_chunks": mode == "primary-catalog-trace-runtime-with-details" or not detail_chunks,
        "gzip_entries_have_raw_siblings": not gzip_raw_siblings_missing,
        "provenance_only_files_excluded": not provenance_only_paths,
        "default_app_config_canonical_config_matches_expected": config_expectation_met,
    }

    return {
        "payload_root": str(payload_root),
        "static_bundle_root": str(static_bundle_root.resolve()) if static_bundle_root else None,
        "mode": mode,
        "status": "ready" if all(checks.values()) else "blocked",
        "checks": checks,
        "counts": {
            "files": len(files),
            "raw_files": len([path for path in copied_paths if not path.endswith(".gz")]),
            "gzip_files": len(gzip_entries),
            "summary_shards": len([path for path in summary_shards if not path.endswith(".gz")]),
            "event_chunks": len([path for path in detail_chunks if not path.endswith(".gz")]),
            "total_bytes": int(payload_manifest.get("total_bytes", 0)) if isinstance(payload_manifest, dict) else 0,
            "raw_bytes": int(payload_manifest.get("raw_bytes", 0)) if isinstance(payload_manifest, dict) else 0,
            "gzip_bytes": int(payload_manifest.get("gzip_bytes", 0)) if isinstance(payload_manifest, dict) else 0,
        },
        "config_state": {
            "default_app_config_canonical_disabled": _canonical_flags_disabled(default_config),
            "default_app_config_canonical_promoted": _canonical_flags_promoted(default_config),
        },
        "expected_canonical_config": expected_canonical_config,
        "problems": {
            "missing_files": sorted(path for path in copied_paths if not (payload_root / path).is_file()),
            "mode_required_missing": mode_required_missing,
            "file_size_mismatches": file_size_mismatches,
            "gzip_raw_siblings_missing": gzip_raw_siblings_missing,
            "provenance_only_paths": provenance_only_paths,
        },
    }


def _read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _file_size_mismatches(payload_root: Path, files: list[Any]) -> list[dict[str, Any]]:
    mismatches = []
    for item in files:
        if not isinstance(item, dict):
            continue
        relative_path = str(item.get("path", "")).replace("\\", "/")
        expected_bytes = item.get("bytes")
        if not relative_path or expected_bytes is None:
            continue
        path = payload_root / relative_path
        if not path.exists() or not path.is_file():
            continue
        actual_bytes = path.stat().st_size
        if int(expected_bytes) != actual_bytes:
            mismatches.append({"path": relative_path, "expected_bytes": int(expected_bytes), "actual_bytes": actual_bytes})
    return mismatches


def _read_static_bundle_app_config(static_bundle_root: Path | None) -> dict[str, Any]:
    if static_bundle_root is None:
        return {}
    config_path = static_bundle_root / "data" / "app_config.json"
    if not config_path.exists():
        return {}
    return json.loads(config_path.read_text(encoding="utf-8"))


def _canonical_flags_disabled(config: dict[str, Any]) -> bool:
    canonical_config = config.get("canonicalWebArtifacts") if isinstance(config, dict) else None
    if not isinstance(canonical_config, dict):
        return False
    return all(canonical_config.get(flag) is False for flag in CANONICAL_FLAGS)


def _canonical_flags_promoted(config: dict[str, Any]) -> bool:
    canonical_config = config.get("canonicalWebArtifacts") if isinstance(config, dict) else None
    if not isinstance(canonical_config, dict):
        return False
    return all(canonical_config.get(flag) is True for flag in CANONICAL_FLAGS)


def _canonical_config_matches(config: dict[str, Any], expected: str) -> bool:
    if expected == "any":
        return True
    if expected == "promoted":
        return _canonical_flags_promoted(config)
    if expected == "disabled":
        return _canonical_flags_disabled(config)
    raise ValueError(f"Unsupported expected canonical config: {expected}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload-root", type=Path, default=Path("data/canonical_web_static_primary_trace_payload"))
    parser.add_argument("--static-bundle-root", type=Path, default=Path("static_bundle"))
    parser.add_argument("--output", type=Path, default=Path("data/reports/canonical_web_static_payload_readiness.json"))
    parser.add_argument(
        "--expected-canonical-config",
        choices=("disabled", "promoted", "any"),
        default="disabled",
        help="Expected static_bundle/data/app_config.json canonicalWebArtifacts flag state.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = check_canonical_web_static_payload(
        args.payload_root,
        static_bundle_root=args.static_bundle_root,
        expected_canonical_config=args.expected_canonical_config,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
