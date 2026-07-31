"""Apply high-confidence mapping candidates to a preview-only corpus sidecar.

This streams a canonical deduped_events JSONL file and fills missing
coordinates for rows whose normalized location text has a high/medium offline
GeoNames match. It never overwrites canonical_full.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("data/canonical_preview_remaining_lower_time_format_apply/deduped_events.jsonl")
DEFAULT_CANDIDATES = Path("data/reports/offline_geonames_mapping_candidates.csv")
DEFAULT_OUTPUT_DIR = Path("data/canonical_preview_mapping_enrichment_geonames_high_medium")
DEFAULT_REPORT = Path("data/reports/mapping_enrichment_geonames_high_medium_preview_apply_report.json")
ALLOWED_CONFIDENCE = {"high", "medium"}
NUMERIC_HIGH_CONFIDENCE = 0.8
NUMERIC_MEDIUM_CONFIDENCE = 0.65


def apply_mapping_enrichment_preview(
    *,
    input_path: Path,
    candidates_path: Path,
    output_dir: Path,
    report_output: Path,
) -> dict[str, Any]:
    candidates = load_candidates(candidates_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "deduped_events.jsonl"
    tmp_output_path = output_path.with_suffix(".jsonl.tmp")

    input_event_count = 0
    mapped_before_count = 0
    enriched_event_count = 0
    query_candidates = {key: candidate for key, candidate in candidates.items() if not key.startswith("event:")}
    event_candidates = {key.removeprefix("event:"): candidate for key, candidate in candidates.items() if key.startswith("event:")}
    candidate_hit_counts = {query: 0 for query in candidates}
    source_counts: dict[str, int] = {}

    with input_path.open("r", encoding="utf-8") as source, tmp_output_path.open("w", encoding="utf-8", newline="\n") as output:
        for line in source:
            if not line.strip():
                continue
            event = json.loads(line)
            input_event_count += 1
            if has_usable_coordinates(event):
                mapped_before_count += 1
                output.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
                continue

            event_id = clean_text(event.get("canonical_event_id"))
            query = normalize_query(best_location_text(event))
            candidate_key = f"event:{event_id}" if event_id in event_candidates else query
            candidate = event_candidates.get(event_id) or query_candidates.get(query)
            if candidate:
                event = enrich_event(event, candidate)
                enriched_event_count += 1
                candidate_hit_counts[candidate_key] = candidate_hit_counts.get(candidate_key, 0) + 1
                source = clean_text(event.get("source_name")) or "unknown"
                source_counts[source] = source_counts.get(source, 0) + 1
            output.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")

    tmp_output_path.replace(output_path)
    report = {
        "schema_version": 1,
        "mode": "preview",
        "apply_policy": "mapping_enrichment_geonames_high_medium_preview_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": True,
        "geocoding_performed": False,
        "inputs": {
            "deduped_events": str(input_path),
            "mapping_candidates": str(candidates_path),
        },
        "outputs": {
            "deduped_events": str(output_path),
            "report": str(report_output),
        },
        "input_event_count": input_event_count,
        "preview_event_count": input_event_count,
        "mapped_before_count": mapped_before_count,
        "enriched_event_count": enriched_event_count,
        "projected_mapped_after_count": mapped_before_count + enriched_event_count,
        "candidate_query_count": len(candidates),
        "candidate_queries_used": sum(1 for count in candidate_hit_counts.values() if count > 0),
        "enriched_by_source": dict(sorted(source_counts.items())),
        "top_candidate_hits": [
            {"query": query, "enriched_event_count": count}
            for query, count in sorted(candidate_hit_counts.items(), key=lambda item: (-item[1], item[0]))
            if count > 0
        ][:100],
        "safety_notes": [
            "Preview writes only a sidecar deduped_events.jsonl.",
            "Only high/medium offline GeoNames candidates are applied.",
            "No network geocoding is performed.",
            "Canonical source artifacts are not overwritten.",
        ],
    }
    write_json(report_output, report)
    return report


def load_candidates(path: Path) -> dict[str, dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            confidence, numeric_confidence = normalize_candidate_confidence(row.get("confidence"))
            if confidence not in ALLOWED_CONFIDENCE:
                continue
            event_id = clean_text(row.get("canonical_event_id"))
            query = normalize_query(row.get("query") or "")
            candidate_key = f"event:{event_id}" if event_id else query
            if not candidate_key:
                continue
            lat = parse_float(row.get("lat"))
            lon = parse_float(row.get("lon"))
            if lat is None or lon is None:
                continue
            candidates[candidate_key] = {
                "query": query,
                "canonical_event_id": event_id,
                "confidence": confidence,
                "numeric_confidence": numeric_confidence,
                "lat": lat,
                "lon": lon,
                "name": clean_text(row.get("name") or row.get("display_name")),
                "country_code": clean_text(row.get("country_code")),
                "admin1": clean_text(row.get("admin1")),
                "timezone": clean_text(row.get("timezone")),
                "location_precision": clean_text(row.get("location_precision")) or "city",
                "candidate_count": int(row.get("candidate_count") or 0),
                "source": (
                    "body_text_city_state"
                    if event_id
                    else "cached_geocode" if clean_text(row.get("provider_id")) else "offline_geonames"
                ),
            }
    return candidates


def enrich_event(event: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    next_event = dict(event)
    next_event["lat"] = candidate["lat"]
    next_event["lon"] = candidate["lon"]
    next_event["coordinate_source"] = "geocoded"
    next_event["location_precision"] = candidate.get("location_precision") or "city"
    next_event["geocode_query_used"] = candidate["query"]
    next_event["geocode_display_name"] = display_name(candidate)
    next_event["geocode_confidence"] = candidate.get("numeric_confidence") or (0.85 if candidate["confidence"] == "high" else 0.65)
    next_event["mapping_enrichment_source"] = candidate.get("source") or "offline_geonames"
    next_event["mapping_enrichment_confidence"] = candidate["confidence"]
    next_event["mapping_enrichment_timezone"] = candidate["timezone"]
    existing_notes = clean_text(next_event.get("mapping_notes"))
    enrichment_note = (
        "Preview mapping enrichment from offline GeoNames "
        f"({candidate['confidence']} confidence; query '{candidate['query']}')."
    )
    next_event["mapping_notes"] = f"{existing_notes} {enrichment_note}".strip()
    return next_event


def normalize_candidate_confidence(value: Any) -> tuple[str, float | None]:
    text = clean_text(value).lower()
    if text in ALLOWED_CONFIDENCE:
        return text, None
    numeric = parse_float(text)
    if numeric is None:
        return "", None
    if numeric >= NUMERIC_HIGH_CONFIDENCE:
        return "high", numeric
    if numeric >= NUMERIC_MEDIUM_CONFIDENCE:
        return "medium", numeric
    return "", numeric


def display_name(candidate: dict[str, Any]) -> str:
    parts = [candidate.get("name"), candidate.get("admin1"), candidate.get("country_code")]
    return ", ".join(clean_text(part) for part in parts if clean_text(part))


def has_usable_coordinates(event: dict[str, Any]) -> bool:
    lat = parse_float(event.get("lat"))
    lon = parse_float(event.get("lon"))
    return lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180


def best_location_text(event: dict[str, Any]) -> str:
    candidates = [
        event.get("location_raw"),
        event.get("primary_location_text"),
        ", ".join(str(event.get(key) or "") for key in ("city", "state_province", "country")),
    ]
    for candidate in candidates:
        text = clean_text(candidate)
        if text and re.search(r"[A-Za-z0-9]", text):
            return text
    return ""


def normalize_query(value: Any) -> str:
    text = clean_text(value).lower()
    text = text.replace("\\,", ",")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*,\s*", ", ", text)
    return text.strip(" ,")


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def parse_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result else None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = apply_mapping_enrichment_preview(
        input_path=args.input,
        candidates_path=args.candidates,
        output_dir=args.output_dir,
        report_output=args.report_output,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
