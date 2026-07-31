"""Configuration loading and path resolution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class GeocoderConfig:
    enabled: bool
    provider: str
    endpoint: str
    user_agent: str
    email: str | None
    language: str
    country_codes: list[str]
    rate_limit_seconds: float
    timeout_seconds: float
    query_limit_per_run: int | None
    confidence_threshold: float | None
    description_fallback_enabled: bool


@dataclass(slots=True)
class WebConfig:
    host: str
    port: int
    tile_url: str
    tile_attribution: str
    initial_center: list[float]
    initial_zoom: int


@dataclass(slots=True)
class AppConfig:
    config_path: Path
    input_files: list[Path]
    normalized_events_path: Path
    map_events_path: Path
    unresolved_locations_json_path: Path
    unresolved_locations_csv_path: Path
    ranked_unresolved_locations_json_path: Path
    ranked_unresolved_locations_csv_path: Path
    parse_failures_path: Path
    geocode_failures_path: Path
    manual_overrides_path: Path
    static_bundle_dir: Path
    geocode_cache_path: Path
    geocoder: GeocoderConfig
    web: WebConfig


def _resolve_path(base_dir: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()


def load_config(config_path: str | Path) -> AppConfig:
    path = Path(config_path).resolve()
    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    base_dir = path.parent
    inputs = raw.get("inputs", {})
    outputs = raw.get("outputs", {})
    cache = raw.get("cache", {})
    geocoder = raw.get("geocoder", {})
    web = raw.get("web", {})

    input_files = [
        _resolve_path(base_dir, item)
        for item in inputs.get("files", [])
    ]

    return AppConfig(
        config_path=path,
        input_files=input_files,
        normalized_events_path=_resolve_path(
            base_dir,
            outputs.get("normalized_events", "data/normalized_events.json"),
        ),
        map_events_path=_resolve_path(
            base_dir,
            outputs.get("map_events", "data/map_events.json"),
        ),
        unresolved_locations_json_path=_resolve_path(
            base_dir,
            outputs.get(
                "unresolved_locations_json",
                "data/reports/unresolved_locations.json",
            ),
        ),
        unresolved_locations_csv_path=_resolve_path(
            base_dir,
            outputs.get(
                "unresolved_locations_csv",
                "data/reports/unresolved_locations.csv",
            ),
        ),
        ranked_unresolved_locations_json_path=_resolve_path(
            base_dir,
            outputs.get(
                "ranked_unresolved_locations_json",
                "data/reports/ranked_unresolved_locations.json",
            ),
        ),
        ranked_unresolved_locations_csv_path=_resolve_path(
            base_dir,
            outputs.get(
                "ranked_unresolved_locations_csv",
                "data/reports/ranked_unresolved_locations.csv",
            ),
        ),
        parse_failures_path=_resolve_path(
            base_dir,
            outputs.get("parse_failures", "data/reports/parse_failures.jsonl"),
        ),
        geocode_failures_path=_resolve_path(
            base_dir,
            outputs.get("geocode_failures", "data/reports/geocode_failures.jsonl"),
        ),
        manual_overrides_path=_resolve_path(
            base_dir,
            outputs.get(
                "manual_overrides",
                "data/manual_location_overrides.json",
            ),
        ),
        static_bundle_dir=_resolve_path(
            base_dir,
            outputs.get("static_bundle_dir", "static_bundle"),
        ),
        geocode_cache_path=_resolve_path(
            base_dir,
            cache.get("geocode_cache", "cache/geocode_cache.jsonl"),
        ),
        geocoder=GeocoderConfig(
            enabled=bool(geocoder.get("enabled", True)),
            provider=str(geocoder.get("provider", "nominatim")),
            endpoint=str(
                geocoder.get("endpoint", "https://nominatim.openstreetmap.org/search")
            ),
            user_agent=str(
                geocoder.get("user_agent", "ufo-timeline-map-tool/1.0")
            ),
            email=geocoder.get("email"),
            language=str(geocoder.get("language", "en")),
            country_codes=list(geocoder.get("country_codes", []) or []),
            rate_limit_seconds=float(geocoder.get("rate_limit_seconds", 1.1)),
            timeout_seconds=float(geocoder.get("timeout_seconds", 25)),
            query_limit_per_run=(
                int(geocoder["query_limit_per_run"])
                if geocoder.get("query_limit_per_run") is not None
                else None
            ),
            confidence_threshold=(
                float(geocoder["confidence_threshold"])
                if geocoder.get("confidence_threshold") is not None
                else None
            ),
            description_fallback_enabled=bool(
                geocoder.get("description_fallback_enabled", True)
            ),
        ),
        web=WebConfig(
            host=str(web.get("host", "127.0.0.1")),
            port=int(web.get("port", 8000)),
            tile_url=str(
                web.get(
                    "tile_url",
                    "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
                )
            ),
            tile_attribution=str(
                web.get(
                    "tile_attribution",
                    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
                )
            ),
            initial_center=[float(v) for v in web.get("initial_center", [20, 0])],
            initial_zoom=int(web.get("initial_zoom", 2)),
        ),
    )
