"""Profile canonical build artifact sizes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_INPUT_DIRS = [
    Path("data/canonical_full"),
    Path("data/reports/canonical_full"),
]
DEFAULT_OUTPUT_PATH = Path("data/reports/canonical_full/artifact_size_report.json")


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        action="append",
        dest="input_dirs",
        default=None,
        help="Directory to profile. May be passed more than once.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help="Output JSON report path.",
    )
    parser.add_argument(
        "--build-duration-seconds",
        type=float,
        default=None,
        help="Optional measured build duration to include in the report.",
    )
    parser.add_argument(
        "--legacy-duplicate-path",
        default=None,
        help="Optional file path to subtract when estimating future output without a legacy duplicate.",
    )
    return parser


def profile_artifacts(
    *,
    input_dirs: list[Path],
    base_dir: Path,
    build_duration_seconds: float | None = None,
    legacy_duplicate_path: Path | None = None,
    exclude_paths: set[Path] | None = None,
) -> dict[str, Any]:
    resolved_excludes = {path.resolve() for path in exclude_paths or set()}
    files = []
    for input_dir in input_dirs:
        if not input_dir.exists():
            continue
        for path in sorted(input_dir.glob("*")):
            if not path.is_file():
                continue
            if path.resolve() in resolved_excludes:
                continue
            size_bytes = path.stat().st_size
            files.append(
                {
                    "path": relative_path(path, base_dir),
                    "bytes": size_bytes,
                    "mb": round(size_bytes / (1024 * 1024), 2),
                }
            )

    files.sort(key=lambda item: (-item["bytes"], item["path"]))
    total_bytes = sum(item["bytes"] for item in files)
    report: dict[str, Any] = {
        "input_dirs": [relative_path(path, base_dir) for path in input_dirs],
        "total_files": len(files),
        "total_bytes": total_bytes,
        "total_mb": round(total_bytes / (1024 * 1024), 2),
        "files": files,
        "startup_implication": (
            "Raw canonical/provenance JSON is archival/build output only. "
            "It is not suitable for browser startup loading without compact indexes, "
            "shards, compression, and lazy detail fetches."
        ),
    }
    if build_duration_seconds is not None:
        report["build_duration_seconds"] = build_duration_seconds
    if legacy_duplicate_path is not None:
        duplicate_path = legacy_duplicate_path.resolve()
        duplicate_bytes = duplicate_path.stat().st_size if duplicate_path.exists() else 0
        report["legacy_duplicate"] = {
            "path": relative_path(duplicate_path, base_dir),
            "bytes": duplicate_bytes,
            "mb": round(duplicate_bytes / (1024 * 1024), 2),
            "future_default_total_mb_estimate_without_legacy_duplicate": round(
                (total_bytes - duplicate_bytes) / (1024 * 1024),
                2,
            ),
        }
    return report


def relative_path(path: Path, base_dir: Path) -> str:
    resolved_path = path.resolve()
    resolved_base = base_dir.resolve()
    try:
        return str(resolved_path.relative_to(resolved_base)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def main() -> int:
    args = build_argument_parser().parse_args()
    base_dir = Path.cwd()
    input_dirs = [Path(path) for path in args.input_dirs] if args.input_dirs else DEFAULT_INPUT_DIRS
    legacy_duplicate_path = Path(args.legacy_duplicate_path) if args.legacy_duplicate_path else None
    output_path = Path(args.output)
    report = profile_artifacts(
        input_dirs=input_dirs,
        base_dir=base_dir,
        build_duration_seconds=args.build_duration_seconds,
        legacy_duplicate_path=legacy_duplicate_path,
        exclude_paths={output_path},
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
