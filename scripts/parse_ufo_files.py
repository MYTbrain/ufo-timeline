"""CLI entry point for parsing UFO chronology files into JSON outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from parser import load_config, run_pipeline


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default="config.example.yaml",
        help="Path to the YAML configuration file.",
    )
    parser.add_argument(
        "--disable-geocoding",
        action="store_true",
        help="Skip external geocoder lookups and only use raw/manual coordinates.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional maximum number of events to process for a quick dry run.",
    )
    parser.add_argument(
        "--input-file",
        action="append",
        default=None,
        help="Optional specific input file(s) to process instead of the full configured list.",
    )
    parser.add_argument(
        "--max-geocode-queries",
        type=int,
        default=None,
        help="Optional override for geocoder.query_limit_per_run so large live geocoding runs can be resumed in batches.",
    )
    parser.add_argument(
        "--repeat-batches",
        type=int,
        default=1,
        help="Repeat the full pipeline multiple times so resumable geocoding can continue automatically across batches.",
    )
    return parser


def main() -> int:
    parser = build_argument_parser()
    args = parser.parse_args()
    config = load_config(args.config)
    if args.max_geocode_queries is not None:
        config.geocoder.query_limit_per_run = args.max_geocode_queries
    selected_files = [Path(item).resolve() for item in args.input_file] if args.input_file else None
    run_count = max(args.repeat_batches, 1)
    summaries: list[dict[str, object]] = []
    for batch_index in range(run_count):
        summary = run_pipeline(
            config,
            disable_geocoding=args.disable_geocoding,
            event_limit=args.limit,
            input_files=selected_files,
        )
        summary["batch_number"] = batch_index + 1
        summaries.append(summary)

    if run_count == 1:
        print(json.dumps(summaries[0], indent=2))
    else:
        print(
            json.dumps(
                {
                    "repeat_batches": run_count,
                    "runs": summaries,
                    "final": summaries[-1],
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
