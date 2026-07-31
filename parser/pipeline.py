"""End-to-end parsing, normalization, geocoding, and report generation."""

from __future__ import annotations

import csv
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from .config import AppConfig
from .dates import normalize_event_dates
from .event_parser import parse_events_from_text
from .geocode_cache import GeocodeCache
from .geocoders import create_geocoder
from .geocoders.base import GeocoderError, GeocoderLimitReached
from .locations import (
    LocationCandidate,
    build_location_candidates,
    classify_geocode_precision,
    extract_decimal_coordinates,
    extract_dms_coordinates,
    infer_text_precision,
)
from .static_bundle import build_static_bundle
from .utils import coerce_float, ensure_parent_dir, safe_read_json, write_json, write_jsonl


ORIGINAL_TIMELINE_BASE_URL = "https://www.subquantumtech.com/timeline"
SOURCE_FILE_TO_TIMELINE_DESTINATION = {
    "ufos up to 1949.txt": "timeline.html",
    "ufos 1950_1959.txt": "timeline_part2.html",
    "ufos 1960_1969.txt": "timeline_part3.html",
    "ufos 1970_1979.txt": "timeline_part4.html",
    "ufos 1980_present.txt": "timeline_part5.html",
}


def _original_entry_url(event: dict[str, Any]) -> str | None:
    event_hash = (event.get("event_hash") or "").strip()
    source_file = (event.get("source_file") or "").strip().lower()
    destination = SOURCE_FILE_TO_TIMELINE_DESTINATION.get(source_file)
    if not event_hash or destination is None:
        return None
    return f"{ORIGINAL_TIMELINE_BASE_URL}/{destination}#{event_hash}"


def _ensure_manual_overrides_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        ensure_parent_dir(path)
        path.write_text("{}", encoding="utf-8")
    return safe_read_json(path, {})


def _event_warning_record(event: dict[str, Any], warning_type: str) -> dict[str, Any]:
    return {
        "event_id": event.get("event_id"),
        "event_hash": event.get("event_hash"),
        "source_file": event.get("source_file"),
        "warning_type": warning_type,
        "parse_warnings": event.get("parse_warnings", []),
        "raw_event_block": event.get("raw_event_block"),
    }


def _serialize(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    return value


def _apply_manual_override(event: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    lat = coerce_float(override.get("lat"))
    lon = coerce_float(override.get("lon"))
    return {
        "lat": lat,
        "lon": lon,
        "primary_location_text": override.get("primary_location_text") or event.get("location_raw"),
        "coordinate_source": "manual_fallback" if lat is not None and lon is not None else "unresolved",
        "location_precision": override.get("location_precision", "approximate"),
        "geocode_query_used": override.get("geocode_query_used"),
        "geocode_display_name": override.get("geocode_display_name") or "Manual override",
        "geocode_confidence": coerce_float(override.get("geocode_confidence")),
        "mapping_notes": override.get("mapping_notes", "Resolved from manual_location_overrides.json."),
    }


def _event_has_direct_coordinates(event: dict[str, Any]) -> bool:
    extra_latlong = event.get("extra_data", {}).get("LatLong")
    if extract_decimal_coordinates(extra_latlong):
        return True
    location_raw = event.get("location_raw")
    return bool(
        extract_decimal_coordinates(location_raw) or extract_dms_coordinates(location_raw)
    )


def _candidate_priority_score(candidate: LocationCandidate) -> float:
    precision = infer_text_precision(
        candidate.query,
        approximate=candidate.approximate,
        multi_location=candidate.source_kind == "explicit_multi_location",
    )
    precision_weight = {
        "address": 12.0,
        "city": 10.0,
        "county": 7.0,
        "multi_location": 8.0,
        "state_province": 4.0,
        "approximate": 3.0,
        "country": 1.0,
        "unknown": 0.5,
    }.get(precision, 1.0)
    source_weight = {
        "explicit_location": 3.0,
        "explicit_multi_location": 2.5,
        "description_fallback": 1.0,
    }.get(candidate.source_kind, 1.0)
    structure_bonus = 1.5 if "," in candidate.query else 0.0
    return (precision_weight * source_weight) + structure_bonus


def _build_geocode_plan(
    events: list[dict[str, Any]],
    candidate_lookup: dict[int, list[LocationCandidate]],
    *,
    manual_overrides: dict[str, Any],
    geocoder,
) -> list[dict[str, Any]]:
    aggregated: dict[str, dict[str, Any]] = {}
    geocoder_cache = getattr(geocoder, "cache", None)
    provider_id = getattr(geocoder, "provider_id", None)

    for event in events:
        if str(event["event_id"]) in manual_overrides:
            continue
        if _event_has_direct_coordinates(event):
            continue

        for candidate in candidate_lookup.get(event["event_id"], []):
            cached = geocoder_cache.get(provider_id, candidate.query) if geocoder_cache is not None and provider_id is not None else None
            if cached is not None:
                continue

            normalized_query = (
                geocoder_cache.normalize_query(candidate.query)
                if geocoder_cache is not None
                else candidate.query.strip().lower()
            )
            score = _candidate_priority_score(candidate)
            precision = infer_text_precision(
                candidate.query,
                approximate=candidate.approximate,
                multi_location=candidate.source_kind == "explicit_multi_location",
            )
            group = aggregated.setdefault(
                normalized_query,
                {
                    "query": candidate.query,
                    "score": 0.0,
                    "count": 0,
                    "precision": precision,
                    "source_kind": candidate.source_kind,
                    "sample_event_ids": [],
                },
            )
            group["score"] += score
            group["count"] += 1
            if len(group["sample_event_ids"]) < 10:
                group["sample_event_ids"].append(event["event_id"])
            if len(candidate.query) > len(group["query"]):
                group["query"] = candidate.query

    planned_queries = list(aggregated.values())
    planned_queries.sort(
        key=lambda item: (
            -item["score"],
            -item["count"],
            item["query"],
        )
    )
    return planned_queries


def _warm_geocode_cache(
    geocoder,
    geocoding_state: dict[str, Any],
    geocode_failures: list[dict[str, Any]],
    planned_queries: list[dict[str, Any]],
) -> None:
    if not geocoding_state.get("enabled", True):
        return

    for planned in planned_queries:
        if not geocoding_state.get("enabled", True):
            return
        try:
            geocoder.geocode(planned["query"])
        except GeocoderLimitReached:
            geocoding_state["enabled"] = False
            geocoding_state["reason"] = "query_limit_reached"
            geocoding_state["deferred_count"] = geocoding_state.get("deferred_count", 0) + 1
            return
        except GeocoderError as exc:
            geocode_failures.append(
                {
                    "event_id": None,
                    "event_hash": None,
                    "source_file": None,
                    "query": planned["query"],
                    "raw_location": planned["query"],
                    "error": f"Cache warm geocoder request failed: {exc}",
                    "priority_score": planned["score"],
                    "priority_count": planned["count"],
                }
            )


def _resolve_location(
    event: dict[str, Any],
    *,
    geocoder,
    geocoding_state: dict[str, Any],
    location_candidates: list[LocationCandidate] | None = None,
    manual_overrides: dict[str, Any],
    geocode_failures: list[dict[str, Any]],
    geocoding_enabled: bool,
    description_fallback_enabled: bool,
) -> dict[str, Any]:
    event_id_key = str(event["event_id"])
    if event_id_key in manual_overrides:
        return _apply_manual_override(event, manual_overrides[event_id_key])

    mapping_notes: list[str] = []
    primary_location_text = None

    extra_latlong = event.get("extra_data", {}).get("LatLong")
    coords = extract_decimal_coordinates(extra_latlong)
    if coords:
        lat, lon = coords
        return {
            "lat": lat,
            "lon": lon,
            "primary_location_text": event.get("location_raw"),
            "coordinate_source": "raw_latlong",
            "location_precision": "exact_coords",
            "geocode_query_used": None,
            "geocode_display_name": event.get("location_raw"),
            "geocode_confidence": 1.0,
            "mapping_notes": "Used coordinates from Extra Data.LatLong.",
        }

    location_raw = event.get("location_raw")
    coords = extract_decimal_coordinates(location_raw) or extract_dms_coordinates(location_raw)
    if coords:
        lat, lon = coords
        return {
            "lat": lat,
            "lon": lon,
            "primary_location_text": location_raw,
            "coordinate_source": "location_coordinates",
            "location_precision": "exact_coords",
            "geocode_query_used": location_raw,
            "geocode_display_name": location_raw,
            "geocode_confidence": 1.0,
            "mapping_notes": "Extracted coordinates directly from the location field.",
        }

    candidates = location_candidates
    if candidates is None:
        candidates = build_location_candidates(
            event,
            description_fallback_enabled=description_fallback_enabled,
        )
    primary_location_text = candidates[0].query if candidates else None
    multiple_locations = len(event.get("all_locations_raw") or []) > 1

    if not candidates:
        return {
            "lat": None,
            "lon": None,
            "primary_location_text": None,
            "coordinate_source": "unresolved",
            "location_precision": infer_text_precision(None),
            "geocode_query_used": None,
            "geocode_display_name": None,
            "geocode_confidence": None,
            "mapping_notes": "No usable location field or conservative description fallback could be extracted.",
        }

    can_use_cache_only = (
        geocoder is not None
        and geocoding_enabled
        and not geocoding_state.get("enabled", True)
        and geocoding_state.get("reason") == "query_limit_reached"
    )
    if not geocoding_enabled or geocoder is None or (
        not geocoding_state.get("enabled", True) and not can_use_cache_only
    ):
        inferred_precision = infer_text_precision(
            primary_location_text,
            approximate=any(candidate.approximate for candidate in candidates),
            multi_location=multiple_locations,
        )
        if geocoding_state.get("reason") == "query_limit_reached":
            note = "Live geocoding was deferred after reaching the configured query limit for this run; rerun to continue from the local cache."
        else:
            note = "Textual location candidate exists but external geocoding was disabled or unavailable."
        return {
            "lat": None,
            "lon": None,
            "primary_location_text": primary_location_text,
            "coordinate_source": "unresolved",
            "location_precision": inferred_precision,
            "geocode_query_used": primary_location_text,
            "geocode_display_name": None,
            "geocode_confidence": None,
            "mapping_notes": note,
        }

    for candidate in candidates:
        try:
            geocode_result = geocoder.geocode(candidate.query)
        except GeocoderLimitReached:
            geocoding_state["enabled"] = False
            geocoding_state["reason"] = "query_limit_reached"
            geocoding_state["deferred_count"] = geocoding_state.get("deferred_count", 0) + 1
            inferred_precision = infer_text_precision(
                primary_location_text,
                approximate=any(item.approximate for item in candidates),
                multi_location=multiple_locations,
            )
            return {
                "lat": None,
                "lon": None,
                "primary_location_text": primary_location_text,
                "coordinate_source": "unresolved",
                "location_precision": inferred_precision,
                "geocode_query_used": primary_location_text,
                "geocode_display_name": None,
                "geocode_confidence": None,
                "mapping_notes": "Deferred after reaching the configured live geocoding query limit for this run.",
            }
        except GeocoderError as exc:
            geocode_failures.append(
                {
                    "event_id": event["event_id"],
                    "event_hash": event.get("event_hash"),
                    "source_file": event.get("source_file"),
                    "query": candidate.query,
                    "raw_location": candidate.raw_text,
                    "error": str(exc),
                }
            )
            mapping_notes.append(f"Geocoder request failed for '{candidate.query}': {exc}")
            continue

        if not geocode_result:
            geocode_failures.append(
                {
                    "event_id": event["event_id"],
                    "event_hash": event.get("event_hash"),
                    "source_file": event.get("source_file"),
                    "query": candidate.query,
                    "raw_location": candidate.raw_text,
                    "error": "No result returned",
                }
            )
            continue

        precision = classify_geocode_precision(
            geocode_result,
            approximate=candidate.approximate,
            multi_location=multiple_locations,
        )
        confidence = coerce_float(geocode_result.get("confidence"))
        note_parts = candidate.notes or []
        note_parts.append(f"Geocoded from {candidate.source_kind}.")
        return {
            "lat": coerce_float(geocode_result.get("lat")),
            "lon": coerce_float(geocode_result.get("lon")),
            "primary_location_text": candidate.query,
            "coordinate_source": "geocoded",
            "location_precision": precision,
            "geocode_query_used": candidate.query,
            "geocode_display_name": geocode_result.get("display_name"),
            "geocode_confidence": confidence,
            "mapping_notes": " ".join(note_parts),
        }

    return {
        "lat": None,
        "lon": None,
        "primary_location_text": primary_location_text,
        "coordinate_source": "unresolved",
        "location_precision": infer_text_precision(
            primary_location_text,
            approximate=any(candidate.approximate for candidate in candidates),
            multi_location=multiple_locations,
        ),
        "geocode_query_used": primary_location_text,
        "geocode_display_name": None,
        "geocode_confidence": None,
        "mapping_notes": "Unable to resolve any location candidate via the configured geocoder.",
    }


def _build_map_event(event: dict[str, Any]) -> dict[str, Any]:
    search_parts = [
        event.get("raw_event_block") or "",
        event.get("mapping_notes") or "",
        " ".join(event.get("parse_warnings") or []),
    ]
    if event.get("geocode_display_name"):
        search_parts.append(event["geocode_display_name"])
    if event.get("extra_data"):
        search_parts.append(str(event["extra_data"]))

    payload = dict(event)
    payload["search_text"] = " ".join(search_parts).lower()
    return payload


def _write_unresolved_csv(path: Path, records: list[dict[str, Any]]) -> None:
    ensure_parent_dir(path)
    fieldnames = [
        "event_id",
        "source_file",
        "date_raw",
        "sort_date_iso",
        "location_raw",
        "primary_location_text",
        "coordinate_source",
        "location_precision",
        "geocode_query_used",
        "geocode_confidence",
        "mapping_notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow({name: record.get(name) for name in fieldnames})


def _rank_unresolved_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    priority_weights = {
        "city": 5,
        "multi_location": 4,
        "approximate": 3,
        "country": 2,
        "unknown": 1,
        "state_province": 2,
        "county": 3,
        "address": 4,
    }
    grouped: dict[str, dict[str, Any]] = {}

    for record in records:
        key = (
            record.get("geocode_query_used")
            or record.get("primary_location_text")
            or record.get("location_raw")
            or "<<no_location_text>>"
        )
        group = grouped.setdefault(
            key,
            {
                "query": key,
                "count": 0,
                "event_ids": [],
                "source_files": set(),
                "sample_location_raw": record.get("location_raw"),
                "sample_primary_location_text": record.get("primary_location_text"),
                "precision_counts": {},
                "earliest_sort_date": None,
                "latest_sort_date": None,
            },
        )
        group["count"] += 1
        if len(group["event_ids"]) < 10:
            group["event_ids"].append(record.get("event_id"))
        source_file = record.get("source_file")
        if source_file:
            group["source_files"].add(source_file)
        precision = record.get("location_precision") or "unknown"
        group["precision_counts"][precision] = group["precision_counts"].get(precision, 0) + 1
        sort_date = record.get("sort_date_iso")
        if sort_date:
            if not group["earliest_sort_date"] or sort_date < group["earliest_sort_date"]:
                group["earliest_sort_date"] = sort_date
            if not group["latest_sort_date"] or sort_date > group["latest_sort_date"]:
                group["latest_sort_date"] = sort_date

    ranked: list[dict[str, Any]] = []
    for query, group in grouped.items():
        top_precision = max(
            group["precision_counts"].items(),
            key=lambda item: (item[1], priority_weights.get(item[0], 0)),
        )[0]
        priority_score = group["count"] * priority_weights.get(top_precision, 1)
        ranked.append(
            {
                "query": query,
                "count": group["count"],
                "top_precision": top_precision,
                "precision_counts": group["precision_counts"],
                "priority_score": priority_score,
                "source_files": sorted(group["source_files"]),
                "source_file_count": len(group["source_files"]),
                "sample_event_ids": group["event_ids"],
                "sample_location_raw": group["sample_location_raw"],
                "sample_primary_location_text": group["sample_primary_location_text"],
                "earliest_sort_date": group["earliest_sort_date"],
                "latest_sort_date": group["latest_sort_date"],
                "ranking_reason": "Higher scores indicate location texts that appear often and look more actionable for future geocoding passes.",
            }
        )

    ranked.sort(
        key=lambda item: (
            -item["priority_score"],
            -item["count"],
            item["query"],
        )
    )

    for index, item in enumerate(ranked, start=1):
        item["rank"] = index
    return ranked


def _write_ranked_unresolved_csv(path: Path, records: list[dict[str, Any]]) -> None:
    ensure_parent_dir(path)
    fieldnames = [
        "rank",
        "query",
        "count",
        "top_precision",
        "priority_score",
        "source_file_count",
        "earliest_sort_date",
        "latest_sort_date",
        "sample_location_raw",
        "sample_primary_location_text",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow({name: record.get(name) for name in fieldnames})


def run_pipeline(
    config: AppConfig,
    *,
    disable_geocoding: bool = False,
    event_limit: int | None = None,
    input_files: list[Path] | None = None,
) -> dict[str, Any]:
    manual_overrides = _ensure_manual_overrides_file(config.manual_overrides_path)
    geocode_cache = GeocodeCache(config.geocode_cache_path)
    geocoder = None
    geocoding_state = {"enabled": bool(config.geocoder.enabled and not disable_geocoding), "reason": None, "deferred_count": 0}
    if config.geocoder.enabled and not disable_geocoding:
        geocoder = create_geocoder(config.geocoder, geocode_cache)

    normalized_events: list[dict[str, Any]] = []
    location_candidate_lookup: dict[int, list[LocationCandidate]] = {}
    parse_failure_records: list[dict[str, Any]] = []
    geocode_failures: list[dict[str, Any]] = []
    unresolved_records: list[dict[str, Any]] = []

    selected_files = input_files or config.input_files

    for input_file in selected_files:
        text = input_file.read_text(encoding="utf-8")
        parsed_events, hard_failures = parse_events_from_text(text, source_file=input_file.name)
        parse_failure_records.extend(hard_failures)

        for event in parsed_events:
            date_data = normalize_event_dates(
                event.get("date_raw"),
                end_date_raw=event.get("end_date_raw"),
                alternate_date_raw=event.get("extra_data", {}).get("event_fields", {}).get("Alternate date")
                if isinstance(event.get("extra_data", {}).get("event_fields", {}), dict)
                else None,
                context_year_heading=event.get("extra_data", {}).get("timeline_year_heading"),
                source_file=event.get("source_file"),
            )
            event["date_iso"] = date_data["date_iso"]
            event["end_date_iso"] = date_data["end_date_iso"]
            event["sort_date_iso"] = date_data["sort_date_iso"]
            event["date_precision"] = date_data["date_precision"]
            event["original_entry_url"] = _original_entry_url(event)
            event["parse_warnings"].extend(date_data["date_warnings"] or [])
            location_candidate_lookup[event["event_id"]] = build_location_candidates(
                event,
                description_fallback_enabled=config.geocoder.description_fallback_enabled,
            )
            normalized_events.append(event)
            if event_limit and len(normalized_events) >= event_limit:
                break

        if event_limit and len(normalized_events) >= event_limit:
            break

    if geocoder is not None and geocoding_state.get("enabled", True):
        planned_queries = _build_geocode_plan(
            normalized_events,
            location_candidate_lookup,
            manual_overrides=manual_overrides,
            geocoder=geocoder,
        )
        _warm_geocode_cache(
            geocoder,
            geocoding_state,
            geocode_failures,
            planned_queries,
        )

    for event in normalized_events:
        location_data = _resolve_location(
            event,
            geocoder=geocoder,
            geocoding_state=geocoding_state,
            location_candidates=location_candidate_lookup.get(event["event_id"]),
            manual_overrides=manual_overrides,
            geocode_failures=geocode_failures,
            geocoding_enabled=bool(config.geocoder.enabled and not disable_geocoding),
            description_fallback_enabled=config.geocoder.description_fallback_enabled,
        )
        event.update(location_data)

        if event["parse_warnings"]:
            parse_failure_records.append(_event_warning_record(event, "parse_warning"))

        if (
            event.get("coordinate_source") == "unresolved"
            or event.get("location_precision") in {"country", "state_province", "approximate", "multi_location", "unknown"}
        ):
            unresolved_records.append(
                {
                    "event_id": event["event_id"],
                    "source_file": event.get("source_file"),
                    "date_raw": event.get("date_raw"),
                    "sort_date_iso": event.get("sort_date_iso"),
                    "location_raw": event.get("location_raw"),
                    "primary_location_text": event.get("primary_location_text"),
                    "coordinate_source": event.get("coordinate_source"),
                    "location_precision": event.get("location_precision"),
                    "geocode_query_used": event.get("geocode_query_used"),
                    "geocode_display_name": event.get("geocode_display_name"),
                    "geocode_confidence": event.get("geocode_confidence"),
                    "mapping_notes": event.get("mapping_notes"),
                    "parse_warnings": event.get("parse_warnings") or [],
                }
            )

    map_events = [
        _build_map_event(event)
        for event in normalized_events
        if event.get("lat") is not None and event.get("lon") is not None and event.get("coordinate_source") != "unresolved"
    ]
    ranked_unresolved_records = _rank_unresolved_records(unresolved_records)

    write_json(config.normalized_events_path, [_serialize(event) for event in normalized_events])
    write_json(config.map_events_path, [_serialize(event) for event in map_events])
    write_json(config.unresolved_locations_json_path, unresolved_records, indent=2)
    _write_unresolved_csv(config.unresolved_locations_csv_path, unresolved_records)
    write_json(config.ranked_unresolved_locations_json_path, ranked_unresolved_records, indent=2)
    _write_ranked_unresolved_csv(config.ranked_unresolved_locations_csv_path, ranked_unresolved_records)
    write_jsonl(config.parse_failures_path, parse_failure_records)
    write_jsonl(config.geocode_failures_path, geocode_failures)
    static_bundle_dir = build_static_bundle(
        config,
        normalized_events=normalized_events,
        map_events=map_events,
        unresolved_records=unresolved_records,
        ranked_unresolved_records=ranked_unresolved_records,
        summary={
            "normalized_events": len(normalized_events),
            "map_events": len(map_events),
            "unresolved_locations": len(unresolved_records),
            "geocoding_enabled": bool(config.geocoder.enabled and not disable_geocoding),
            "geocoder_live_requests": getattr(geocoder, "query_count", 0),
        },
    )

    return {
        "normalized_events": len(normalized_events),
        "map_events": len(map_events),
        "parse_failures": len(parse_failure_records),
        "geocode_failures": len(geocode_failures),
        "unresolved_locations": len(unresolved_records),
        "geocoding_enabled": bool(config.geocoder.enabled and not disable_geocoding),
        "geocoder_live_requests": getattr(geocoder, "query_count", 0),
        "geocoder_cache_hits": getattr(geocoder, "cache_hit_count", 0),
        "geocoder_query_limit": config.geocoder.query_limit_per_run,
        "geocoding_stop_reason": geocoding_state.get("reason"),
        "deferred_after_query_limit": geocoding_state.get("deferred_count", 0),
        "static_bundle_dir": str(static_bundle_dir),
    }
