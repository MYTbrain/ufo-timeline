"""Build and validate the Cloudflare Pages/R2 public deployment bundle."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATIC_ROOT = Path("static_bundle")
DEFAULT_OUTPUT_ROOT = Path("cloudflare_bundle_r2")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--static-root", type=Path, default=DEFAULT_STATIC_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument(
        "--r2-base-url",
        required=True,
        help="Production R2 base URL for omitted canonical artifacts, for example https://assets.example.org/ufo.",
    )
    parser.add_argument(
        "--r2-key-prefix",
        default="",
        help="Optional immutable R2 key prefix. The R2 base URL path must end with the same prefix.",
    )
    parser.add_argument(
        "--allow-placeholder-r2",
        action="store_true",
        help="Allow placeholder R2 URLs. Use only for local dry runs.",
    )
    parser.add_argument(
        "--skip-startup-profiles",
        action="store_true",
        help="Do not rebuild curated startup profile artifacts before bundling.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    steps: list[dict[str, Any]] = []

    if not args.skip_startup_profiles:
        steps.append(
            run_step(
                "startup_profiles",
                "scripts/build_startup_profile_artifacts.py",
                "--static-root",
                str(args.static_root),
                "--all-default-profiles",
                "--enable-default-profile",
            )
        )

    cloudflare_args = [
        "--static-root",
        str(args.static_root),
        "--output-root",
        str(args.output_root),
        "--r2-base-url",
        args.r2_base_url,
    ]
    if args.r2_key_prefix:
        cloudflare_args.extend(("--r2-key-prefix", args.r2_key_prefix))
    steps.append(run_step("cloudflare_bundle", "scripts/build_cloudflare_bundle.py", *cloudflare_args))

    validator_args = ["--bundle-root", str(args.output_root)]
    if args.allow_placeholder_r2:
        validator_args.append("--allow-placeholder-r2")
    steps.append(run_step("validate_cloudflare_bundle", "scripts/validate_cloudflare_bundle.py", *validator_args))

    print(json.dumps({"ok": True, "steps": steps}, indent=2, sort_keys=True))


def run_step(name: str, script: str, *args: str) -> dict[str, Any]:
    command = [sys.executable, str(REPO_ROOT / script), *args]
    env = os.environ.copy()
    local_packages = str(REPO_ROOT / ".python_packages")
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        f"{local_packages}{os.pathsep}{existing_pythonpath}"
        if existing_pythonpath
        else local_packages
    )
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        if result.stdout:
            print(result.stdout, file=sys.stdout, end="" if result.stdout.endswith("\n") else "\n")
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="" if result.stderr.endswith("\n") else "\n")
        raise SystemExit(result.returncode)
    parsed_stdout = parse_last_json_object(result.stdout)
    return {
        "name": name,
        "command": command_for_report(command),
        "returncode": result.returncode,
        "summary": parsed_stdout,
    }


def parse_last_json_object(stdout: str) -> Any:
    text = stdout.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text[-1000:]


def command_for_report(command: list[str]) -> list[str]:
    return [str(Path(part).relative_to(REPO_ROOT)) if is_repo_path(part) else part for part in command]


def is_repo_path(value: str) -> bool:
    try:
        path = Path(value)
        return path.is_absolute() and path.is_relative_to(REPO_ROOT)
    except ValueError:
        return False


if __name__ == "__main__":
    main()
