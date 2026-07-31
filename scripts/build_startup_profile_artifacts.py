"""Build small startup-profile artifacts for fast first render.

The profile artifacts intentionally duplicate only lightweight map/trace data.
Full event details stay in the existing canonical_web lazy chunks.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from parser.packed_points import export_packed_points
from parser.trace_scale import trace_gap_bucket_for_days
from parser.trace_segments import export_trace_artifacts


DEFAULT_PROFILE_ID = "france_1954_flap"
DEFAULT_PROFILE_LABEL = "1954 France Sept-Nov"
DEFAULT_START_DATE = "1954-09-01"
DEFAULT_END_DATE = "1954-11-30"
DEFAULT_PROFILES = [
    {
        "profile_id": "france_1954_flap",
        "label": "1954 France Sept-Nov",
        "start_date": "1954-09-01",
        "end_date": "1954-11-30",
    },
    {
        "profile_id": "mystery_airship_wave_1896_1897",
        "label": "1896 Nov–97 Jun · Mystery Airship Wave",
        "start_date": "1896-11-01",
        "end_date": "1897-06-30",
    },
    {
        "profile_id": "belgium_1989_1990_wave",
        "label": "1989-1990 Belgium wave",
        "start_date": "1989-11-01",
        "end_date": "1990-04-30",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--static-root", type=Path, default=Path("static_bundle"))
    parser.add_argument("--profile-id", default=DEFAULT_PROFILE_ID)
    parser.add_argument("--label", default=DEFAULT_PROFILE_LABEL)
    parser.add_argument("--start-date", default=DEFAULT_START_DATE)
    parser.add_argument("--end-date", default=DEFAULT_END_DATE)
    parser.add_argument("--max-preview-segments", type=int, default=12000)
    parser.add_argument(
        "--all-default-profiles",
        action="store_true",
        help="Build every curated scoped startup profile and write a startup_profiles/manifest.json index.",
    )
    parser.add_argument(
        "--enable-default-profile",
        action="store_true",
        help="Enable the first built profile in data/app_config.json for immediate interactive startup.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    static_root = args.static_root
    canonical_root = static_root / "data" / "canonical_web"
    chunk_manifest = read_json(canonical_root / "event_chunk_manifest.json")

    if args.all_default_profiles:
        built_profiles = [
            build_startup_profile(
                static_root=static_root,
                canonical_root=canonical_root,
                chunk_manifest=chunk_manifest,
                profile_id=profile["profile_id"],
                label=profile["label"],
                start_date=profile["start_date"],
                end_date=profile["end_date"],
                max_preview_segments=args.max_preview_segments,
            )
            for profile in DEFAULT_PROFILES
        ]
        write_startup_profiles_index(static_root, built_profiles)
        startup_profile_config = (
            enable_startup_profile_config(static_root, built_profiles[0])
            if args.enable_default_profile and built_profiles
            else None
        )
        print(json.dumps({"profiles": built_profiles, "startup_profile_config": startup_profile_config}, indent=2))
        return

    profile_result = build_startup_profile(
        static_root=static_root,
        canonical_root=canonical_root,
        chunk_manifest=chunk_manifest,
        profile_id=args.profile_id,
        label=args.label,
        start_date=args.start_date,
        end_date=args.end_date,
        max_preview_segments=args.max_preview_segments,
    )
    startup_profile_config = (
        enable_startup_profile_config(static_root, profile_result)
        if args.enable_default_profile
        else None
    )
    print(json.dumps({**profile_result, "startup_profile_config": startup_profile_config}, indent=2))


def build_startup_profile(
    *,
    static_root: Path,
    canonical_root: Path,
    chunk_manifest: list[dict[str, Any]],
    profile_id: str,
    label: str,
    start_date: str,
    end_date: str,
    max_preview_segments: int,
) -> dict[str, Any]:
    output_root = static_root / "data" / "startup_profiles" / profile_id
    output_root.mkdir(parents=True, exist_ok=True)

    scoped_events = load_scoped_summary_events(
        canonical_root=canonical_root,
        start_date=start_date,
        end_date=end_date,
    )
    scoped_events.sort(key=event_sort_key)

    events_path = output_root / "events.json"
    write_json(events_path, scoped_events)
    write_gzip(events_path)

    point_meta = export_packed_points(scoped_events, output_root, chunk_manifest=chunk_manifest)
    trace_meta = export_trace_artifacts(scoped_events, output_root)
    for artifact_name in (
        "points.bin",
        "points_meta.json",
        "trace_event_index.bin",
        "trace_event_index_meta.json",
        "trace_segments.bin",
        "trace_segments_meta.json",
        "trace_aggregate_bins.bin",
        "trace_aggregate_bins_meta.json",
    ):
        artifact_path = output_root / artifact_name
        if artifact_path.exists():
            write_gzip(artifact_path)

    trace_preview_segments = build_trace_preview_segments(scoped_events, max_preview_segments)
    trace_preview_path = output_root / "trace_preview_segments.json"
    write_json(trace_preview_path, trace_preview_segments)
    write_gzip(trace_preview_path)

    manifest = {
        "schema_version": 1,
        "profile_id": profile_id,
        "label": label,
        "date_range": {
            "start": start_date,
            "end": end_date,
        },
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "events": len(scoped_events),
            "mapped_events": int(point_meta.get("row_count") or 0),
            "trace_events": int(trace_meta["trace_events"].get("row_count") or 0),
            "trace_segments": int(trace_meta["trace_segments"].get("row_count") or 0),
            "trace_preview_segments": len(trace_preview_segments),
        },
        "files": {
            "events": "events.json",
            "events_gzip": "events.json.gz",
            "points": "points.bin",
            "points_gzip": "points.bin.gz",
            "points_metadata": "points_meta.json",
            "trace_event_index": "trace_event_index.bin",
            "trace_event_index_gzip": "trace_event_index.bin.gz",
            "trace_event_index_metadata": "trace_event_index_meta.json",
            "trace_aggregate_bins": "trace_aggregate_bins.bin",
            "trace_aggregate_bins_gzip": "trace_aggregate_bins.bin.gz",
            "trace_aggregate_bins_metadata": "trace_aggregate_bins_meta.json",
            "trace_preview_segments": "trace_preview_segments.json",
            "trace_preview_segments_gzip": "trace_preview_segments.json.gz",
        },
        "full_detail_policy": "Use existing canonical_web event chunk/detail references; full details are not duplicated in startup profile artifacts.",
    }
    manifest_path = output_root / "manifest.json"
    write_json(manifest_path, manifest)
    write_gzip(manifest_path)
    return {
        "profile": profile_id,
        "label": label,
        "baseUrl": "./" + str(Path("data") / "startup_profiles" / profile_id).replace("\\", "/") + "/",
        "manifestUrl": "./" + str(Path("data") / "startup_profiles" / profile_id / "manifest.json").replace("\\", "/"),
        "date_range": manifest["date_range"],
        "output": str(output_root),
        "counts": manifest["counts"],
    }


def write_startup_profiles_index(static_root: Path, built_profiles: list[dict[str, Any]]) -> None:
    output_root = static_root / "data" / "startup_profiles"
    output_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "profiles": [
            {
                "id": profile["profile"],
                "label": profile["label"],
                "baseUrl": profile["baseUrl"],
                "manifestUrl": profile["manifestUrl"],
                "date_range": profile["date_range"],
                "counts": profile["counts"],
            }
            for profile in built_profiles
        ],
    }
    manifest_path = output_root / "manifest.json"
    write_json(manifest_path, manifest)
    write_gzip(manifest_path)


def enable_startup_profile_config(static_root: Path, profile: dict[str, Any]) -> dict[str, Any]:
    config_path = static_root / "data" / "app_config.json"
    if not config_path.is_file():
        raise ValueError(f"Cannot enable startup profile because {config_path} does not exist.")
    config = read_json(config_path)
    if not isinstance(config, dict):
        raise ValueError(f"{config_path} must contain a JSON object.")
    existing = config.get("startupProfile") if isinstance(config.get("startupProfile"), dict) else {}
    startup_profile = {
        **existing,
        "enabled": True,
        "id": profile["profile"],
        "label": profile["label"],
        "baseUrl": profile["baseUrl"],
        "manifestUrl": profile["manifestUrl"],
        "renderBeforeGlobalCatalog": True,
        "tracePreview": True,
        "worker": True,
    }
    config["startupProfile"] = startup_profile
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return startup_profile


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, value: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write("\n")


def write_gzip(path: Path) -> None:
    gzip_path = path.with_suffix(path.suffix + ".gz")
    with path.open("rb") as source, gzip.open(gzip_path, "wb", compresslevel=9) as target:
        target.write(source.read())


def load_scoped_summary_events(*, canonical_root: Path, start_date: str, end_date: str) -> list[dict[str, Any]]:
    summary_manifest = read_json(canonical_root / "summary_manifest.json")
    events: list[dict[str, Any]] = []
    for shard in summary_manifest:
        shard_file = shard.get("file")
        if not shard_file:
            continue
        shard_events = read_json(canonical_root / "summary_shards" / str(shard_file))
        for event in shard_events:
            date_iso = str(event.get("sort_date_iso") or "")
            if start_date <= date_iso <= end_date and event.get("has_coordinates") and event.get("lat") is not None and event.get("lon") is not None:
                events.append(compact_startup_event(event))
    return events


def compact_startup_event(event: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "event_id",
        "chunk_id",
        "detail_index",
        "sort_date_iso",
        "date_precision",
        "time_raw",
        "playback_sort_key",
        "location_raw",
        "source",
        "type",
        "shape_normalized",
        "visual_type_group",
        "coordinate_source",
        "location_precision",
        "lat",
        "lon",
    )
    compact = {key: event.get(key) for key in keys if key in event}
    compact["has_coordinates"] = True
    return compact


def event_sort_key(event: dict[str, Any]) -> tuple[Any, ...]:
    playback_key = event.get("playback_sort_key")
    if isinstance(playback_key, list) and playback_key:
        return tuple(playback_key)
    return (event.get("sort_date_iso") or "", str(event.get("event_id") or ""))


def date_key_to_ordinal(date_key: str) -> int | None:
    try:
        return datetime.strptime(date_key[:10], "%Y-%m-%d").date().toordinal()
    except (TypeError, ValueError):
        return None


def build_trace_preview_segments(events: list[dict[str, Any]], max_segments: int) -> list[dict[str, Any]]:
    if len(events) < 2 or max_segments <= 0:
        return []
    raw_segments: list[dict[str, Any]] = []
    previous = events[0]
    previous_ordinal = date_key_to_ordinal(str(previous.get("sort_date_iso") or ""))
    for event in events[1:]:
        current_ordinal = date_key_to_ordinal(str(event.get("sort_date_iso") or ""))
        if previous_ordinal is None or current_ordinal is None:
            previous = event
            previous_ordinal = current_ordinal
            continue
        gap_days = max(0, current_ordinal - previous_ordinal)
        bucket_key = trace_gap_bucket_for_days(gap_days)
        raw_segments.append(
            {
                "from": [previous.get("lat"), previous.get("lon")],
                "to": [event.get("lat"), event.get("lon")],
                "from_event_id": previous.get("event_id"),
                "to_event_id": event.get("event_id"),
                "from_sort_date_key": (previous.get("sort_date_iso") or "").replace("-", "")[:8],
                "to_sort_date_key": (event.get("sort_date_iso") or "").replace("-", "")[:8],
                "gap_days": gap_days,
                "bucket_key": bucket_key,
            }
        )
        previous = event
        previous_ordinal = current_ordinal
    if len(raw_segments) <= max_segments:
        return raw_segments
    step = max(1, len(raw_segments) // max_segments)
    return raw_segments[::step][:max_segments]


if __name__ == "__main__":
    main()
