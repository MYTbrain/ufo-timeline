"""Report static bundle coordinate regressions for explicit U.S. rows.

This check is intentionally narrow. It catches the failure mode where rows
labelled like ``FARGO, Cass, ND, US`` have correct source labels but impossible
positive longitudes in the shipped static summaries.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from scripts.apply_jurisdiction_coordinate_repair_preview import US_STATE_BOUNDS


DEFAULT_PAYLOAD_ROOT = Path("static_bundle")
DEFAULT_OUTPUT = Path("data/reports/static_coordinate_regressions.json")

US_LAT_MIN = 18.0
US_LAT_MAX = 72.0
US_LON_MIN = -180.0
US_LON_MAX = -52.0

US_STATES = set(US_STATE_BOUNDS)

NAMED_US_REGRESSIONS = [
    {"label": "FARGO, Cass, ND, US", "contains": "FARGO", "state": "ND"},
    {"label": "BUTLER, Bates, MO, US", "contains": "BUTLER", "state": "MO"},
    {"label": "MONETT, Barry, MO, US", "contains": "MONETT", "state": "MO"},
    {"label": "MARION, Smyth, VA, US", "contains": "MARION", "state": "VA"},
    {"label": "KINSTON, Lenoir, NC, US", "contains": "KINSTON", "state": "NC"},
    {"label": "PASCO, Franklin, WA, US", "contains": "PASCO", "state": "WA"},
    {"label": "SANTA MONICA, Los Angeles, CA, US", "contains": "SANTA MONICA", "state": "CA"},
    {"label": "PATRICK AFB, Brevard, FL, US", "contains": "PATRICK AFB", "state": "FL"},
]

NAMED_COUNTRY_REGRESSIONS = [
    {
        "label": "WEST BERLIN, TEMPELHOF APT, Berlin, GER, EU",
        "contains": "WEST BERLIN",
        "country_tokens": {"GER", "DEU", "GERMANY"},
        "bounds": {"lat_min": 47.0, "lat_max": 56.0, "lon_min": 5.0, "lon_max": 16.0},
    },
    {
        "label": "WIEN (VIENNA), Vienna, AUT, EU",
        "contains": "WIEN",
        "country_tokens": {"AUT", "AUSTRIA"},
        "bounds": {"lat_min": 46.0, "lat_max": 50.0, "lon_min": 9.0, "lon_max": 18.0},
    },
    {
        "label": "JUNGFRAU, Bern, SUI, EU",
        "contains": "JUNGFRAU",
        "country_tokens": {"SUI", "CHE", "SWITZERLAND"},
        "bounds": {"lat_min": 45.0, "lat_max": 48.5, "lon_min": 5.0, "lon_max": 11.0},
    },
    {
        "label": "RONGERES, FRA",
        "contains": "RONGERES",
        "country_tokens": {"FRA", "FRANCE"},
        "bounds": {"lat_min": 41.0, "lat_max": 52.0, "lon_min": -6.0, "lon_max": 10.0},
    },
]


def check_static_coordinate_regressions(
    *,
    payload_root: Path,
    named_regressions: list[dict[str, str]] | None = None,
    named_country_regressions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload_root = payload_root.resolve()
    if named_regressions is None:
        named_regressions = NAMED_US_REGRESSIONS
    if named_country_regressions is None:
        named_country_regressions = NAMED_COUNTRY_REGRESSIONS
    scanned_events = 0
    explicit_us_rows = 0
    explicit_us_outside_bounds = 0
    explicit_us_outside_state_bounds = 0
    outside_examples: list[dict[str, Any]] = []
    outside_state_examples: list[dict[str, Any]] = []
    named_results = {
        item["label"]: {"label": item["label"], "found": 0, "outside_bounds": 0, "examples": []}
        for item in named_regressions
    }
    named_country_results = {
        item["label"]: {"label": item["label"], "found": 0, "outside_bounds": 0, "examples": []}
        for item in named_country_regressions
    }

    for event in iter_static_summary_events(payload_root):
        scanned_events += 1
        location_raw = str(event.get("location_raw") or "")
        lat = float_or_none(event.get("lat"))
        lon = float_or_none(event.get("lon"))
        if lat is None or lon is None:
            continue

        location_upper = location_raw.upper()
        for item in named_country_regressions:
            if item["contains"].upper() not in location_upper:
                continue
            if not location_has_country_token(location_raw, item["country_tokens"]):
                continue
            named_country = named_country_results[item["label"]]
            named_country["found"] += 1
            if len(named_country["examples"]) < 5:
                named_country["examples"].append(summarize_event(event, state=explicit_us_state(location_raw) or ""))
            if not is_inside_named_country_bounds(item, lat, lon):
                named_country["outside_bounds"] += 1

        state = explicit_us_state(location_raw)
        if state is None:
            continue

        explicit_us_rows += 1
        inside = is_inside_us_wide_bounds(lat, lon)
        inside_state = is_inside_us_state_bounds(state, lat, lon)
        if not inside:
            explicit_us_outside_bounds += 1
            if len(outside_examples) < 100:
                outside_examples.append(summarize_event(event, state=state))
        if not inside_state:
            explicit_us_outside_state_bounds += 1
            if len(outside_state_examples) < 100:
                outside_state_examples.append(summarize_event(event, state=state))

        for item in named_regressions:
            if item["contains"].upper() in location_upper and state == item["state"]:
                named = named_results[item["label"]]
                named["found"] += 1
                if len(named["examples"]) < 5:
                    named["examples"].append(summarize_event(event, state=state))
                if not inside or not inside_state:
                    named["outside_bounds"] += 1

    named_failures = [
        item
        for item in named_results.values()
        if item["found"] == 0 or item["outside_bounds"] > 0
    ]
    named_country_failures = [
        item
        for item in named_country_results.values()
        if item["found"] == 0 or item["outside_bounds"] > 0
    ]
    checks = {
        "explicit_us_rows_inside_wide_us_bounds": explicit_us_outside_bounds == 0,
        "explicit_us_rows_inside_state_bounds": explicit_us_outside_state_bounds == 0,
        "named_regressions_found": all(item["found"] > 0 for item in named_results.values()),
        "named_regressions_inside_wide_and_state_bounds": all(item["outside_bounds"] == 0 for item in named_results.values()),
        "named_country_regressions_found": all(item["found"] > 0 for item in named_country_results.values()),
        "named_country_regressions_inside_country_bounds": all(item["outside_bounds"] == 0 for item in named_country_results.values()),
    }

    return {
        "schema_version": 1,
        "report_policy": "static_coordinate_regression_report_only",
        "canonical_outputs_mutated": False,
        "payload_root": str(payload_root),
        "status": "ready" if all(checks.values()) else "needs_attention",
        "checks": checks,
        "bounds": {
            "explicit_us_wide_lat_min": US_LAT_MIN,
            "explicit_us_wide_lat_max": US_LAT_MAX,
            "explicit_us_wide_lon_min": US_LON_MIN,
            "explicit_us_wide_lon_max": US_LON_MAX,
        },
        "counts": {
            "scanned_events": scanned_events,
            "explicit_us_rows": explicit_us_rows,
            "explicit_us_outside_bounds": explicit_us_outside_bounds,
            "explicit_us_outside_state_bounds": explicit_us_outside_state_bounds,
            "named_regressions_checked": len(named_regressions),
            "named_regression_failures": len(named_failures),
            "named_country_regressions_checked": len(named_country_regressions),
            "named_country_regression_failures": len(named_country_failures),
        },
        "named_regressions": list(named_results.values()),
        "named_country_regressions": list(named_country_results.values()),
        "outside_examples": outside_examples,
        "outside_state_examples": outside_state_examples,
        "notes": [
            "This check only treats rows ending in an explicit U.S. state plus US/USA as U.S. rows.",
            "Rows ending in CA without US/USA are intentionally not treated as California because CA is also used for Canada/Central America.",
        ],
    }


def iter_static_summary_events(payload_root: Path) -> Iterable[dict[str, Any]]:
    summary_dir = payload_root / "data" / "canonical_web" / "summary_shards"
    if not summary_dir.exists():
        raise FileNotFoundError(f"Missing static summary shard directory: {summary_dir}")
    for shard_path in sorted(summary_dir.glob("summary_*.json")):
        payload = json.loads(shard_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"{shard_path} must contain a JSON array.")
        for event in payload:
            if isinstance(event, dict):
                yield event


def explicit_us_state(location_raw: str) -> str | None:
    parts = [part.strip().upper().strip(".") for part in location_raw.split(",")]
    parts = [part for part in parts if part]
    if len(parts) < 2:
        return None
    if parts[-1] not in {"US", "USA", "UNITED STATES"}:
        return None
    state = parts[-2]
    return state if state in US_STATES else None


def is_inside_us_wide_bounds(lat: float, lon: float) -> bool:
    return US_LAT_MIN <= lat <= US_LAT_MAX and US_LON_MIN <= lon <= US_LON_MAX


def is_inside_us_state_bounds(state: str, lat: float, lon: float) -> bool:
    min_lat, max_lat, min_lon, max_lon = US_STATE_BOUNDS[state]
    return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon


def location_has_country_token(location_raw: str, country_tokens: set[str]) -> bool:
    parts = [part.strip().upper().strip(".") for part in location_raw.split(",")]
    return any(part in country_tokens for part in parts)


def is_inside_named_country_bounds(item: dict[str, Any], lat: float, lon: float) -> bool:
    bounds = item["bounds"]
    return (
        bounds["lat_min"] <= lat <= bounds["lat_max"]
        and bounds["lon_min"] <= lon <= bounds["lon_max"]
    )


def float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def summarize_event(event: dict[str, Any], *, state: str) -> dict[str, Any]:
    return {
        "event_id": event.get("event_id"),
        "date": event.get("sort_date_iso") or event.get("date_raw"),
        "location_raw": event.get("location_raw"),
        "source": event.get("source"),
        "state": state,
        "lat": event.get("lat"),
        "lon": event.get("lon"),
        "coordinate_source": event.get("coordinate_source"),
        "location_precision": event.get("location_precision"),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload-root", type=Path, default=DEFAULT_PAYLOAD_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = check_static_coordinate_regressions(payload_root=args.payload_root)
    report["outputs"] = {"json": str(args.output)}
    write_json(args.output, report)
    print(
        json.dumps(
            {
                "json": str(args.output),
                "status": report["status"],
                "explicit_us_rows": report["counts"]["explicit_us_rows"],
                "explicit_us_outside_bounds": report["counts"]["explicit_us_outside_bounds"],
                "explicit_us_outside_state_bounds": report["counts"]["explicit_us_outside_state_bounds"],
                "named_regression_failures": report["counts"]["named_regression_failures"],
                "named_country_regression_failures": report["counts"]["named_country_regression_failures"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
        )
    )
    return 0 if report["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
