"""Launch the local FastAPI + Leaflet web app."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

import uvicorn

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from parser import load_config


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default="config.example.yaml",
        help="Path to the YAML configuration file.",
    )
    parser.add_argument("--host", default=None, help="Override the configured host.")
    parser.add_argument("--port", type=int, default=None, help="Override the configured port.")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload during local development.",
    )
    return parser


def main() -> int:
    args = build_argument_parser().parse_args()
    config = load_config(args.config)
    os.environ["UFO_TIMELINE_CONFIG"] = str(config.config_path)

    uvicorn.run(
        "webapp.app:create_app",
        host=args.host or config.web.host,
        port=args.port or config.web.port,
        factory=True,
        reload=args.reload,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
