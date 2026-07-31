"""Rebuild static_bundle from existing generated JSON data without reparsing/geocoding."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from parser import load_config
from parser.static_bundle import build_static_bundle
from parser.utils import safe_read_json


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default="config.example.yaml",
        help="Path to the YAML configuration file.",
    )
    parser.add_argument(
        "--allow-canonical-regression",
        action="store_true",
        help=(
            "Allow a legacy JSON rebuild to replace an existing canonical-web bundle "
            "with fewer events. This is destructive and is blocked by default."
        ),
    )
    return parser


def _existing_canonical_event_count(static_bundle_dir: Path) -> int | None:
    manifest_path = static_bundle_dir / "data" / "canonical_web" / "canonical_web_manifest.json"
    manifest = safe_read_json(manifest_path, None)
    if not isinstance(manifest, dict):
        return None
    counts = manifest.get("counts")
    if not isinstance(counts, dict):
        return None
    event_count = counts.get("events")
    if isinstance(event_count, bool) or not isinstance(event_count, int):
        return None
    return event_count


def rebuild_static_bundle_from_existing_data(
    config_path: str | Path,
    *,
    allow_canonical_regression: bool = False,
) -> dict[str, Any]:
    config = load_config(config_path)
    normalized_events = safe_read_json(config.normalized_events_path, [])
    map_events = safe_read_json(config.map_events_path, [])
    unresolved_records = safe_read_json(config.unresolved_locations_json_path, [])
    ranked_unresolved_records = safe_read_json(config.ranked_unresolved_locations_json_path, [])

    if not isinstance(normalized_events, list):
        raise ValueError(f"Expected a list in {config.normalized_events_path}")
    if not isinstance(map_events, list):
        raise ValueError(f"Expected a list in {config.map_events_path}")

    existing_canonical_events = _existing_canonical_event_count(Path(config.static_bundle_dir))
    if (
        not allow_canonical_regression
        and existing_canonical_events is not None
        and len(normalized_events) < existing_canonical_events
    ):
        raise RuntimeError(
            "Refusing to replace the existing canonical-web static bundle "
            f"({existing_canonical_events:,} events) with the smaller legacy JSON input "
            f"({len(normalized_events):,} events). Use stage_canonical_web_static_payload.py "
            "for canonical rebuilds, or pass --allow-canonical-regression only when the "
            "event-count reduction is intentional."
        )

    summary = {
        "normalized_events": len(normalized_events),
        "map_events": len(map_events),
        "unresolved_locations": len(unresolved_records) if isinstance(unresolved_records, list) else 0,
        "geocoder_live_requests": 0,
    }
    bundle_dir = build_static_bundle(
        config,
        normalized_events=normalized_events,
        map_events=map_events,
        unresolved_records=unresolved_records if isinstance(unresolved_records, list) else [],
        ranked_unresolved_records=ranked_unresolved_records if isinstance(ranked_unresolved_records, list) else [],
        summary=summary,
    )
    return {
        **summary,
        "static_bundle_dir": str(bundle_dir),
    }


def main() -> int:
    args = build_argument_parser().parse_args()
    summary = rebuild_static_bundle_from_existing_data(
        args.config,
        allow_canonical_regression=args.allow_canonical_regression,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
