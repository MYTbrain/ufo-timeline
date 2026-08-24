"""Audit rendered canonical location labels without mutating source data.

The canonical catalog intentionally preserves source wording.  This report
finds strings that are likely poor *display* labels: source classifications
mixed into places, duplicated administrative components, internal state
contradictions, placeholder components, coordinate literals, markup, and
structurally malformed comma-separated values.

The audit is report-only.  Findings must be repaired with a reviewed display
projection or a source-specific normalization; ``location_raw`` and the source
row remain provenance.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from scripts.check_static_country_coordinate_anomalies import (
    US_STATE_NAME_TO_ABBREVIATION,
)
from scripts.apply_jurisdiction_coordinate_repair_preview import US_STATE_BOUNDS


DEFAULT_PAYLOAD_ROOT = Path("static_bundle")
DEFAULT_JSON_OUTPUT = Path("data/reports/static_location_label_audit.json")
DEFAULT_CSV_OUTPUT = Path("data/reports/static_location_label_audit.csv")

MAJESTIC_ENVIRONMENT_CATEGORIES = {
    "coastlands",
    "desert",
    "farmlands",
    "forest",
    "high seas",
    "islands",
    "metropolis",
    "mountains",
    "offshore",
    "oil coal",
    "pasture",
    "rainforest",
    "residential",
    "town city",
    "tundra",
    "wetlands",
}

PLACEHOLDER_COMPONENTS = {
    "n a",
    "na",
    "none",
    "null",
    "tbd",
    "unknown",
    "unknown city",
    "unknown location",
    "unspecified",
}

US_COUNTRY_TOKENS = {"us", "usa", "united states", "united states of america"}
COORDINATE_LITERAL_RE = re.compile(
    r"^[+-]?\d{1,3}(?:\.\d+)?\s*[,;/ ]\s*[+-]?\d{1,3}(?:\.\d+)?$"
)
MARKUP_OR_URL_RE = re.compile(r"https?://|<[^>]+>|&(?:nbsp|amp|lt|gt);", re.I)


def audit_static_location_labels(
    *,
    payload_root: Path,
    json_output: Path | None = None,
    csv_output: Path | None = None,
    max_examples_per_reason: int = 250,
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    scanned_events = 0
    events_with_findings = 0

    for event in iter_static_summary_events(payload_root):
        scanned_events += 1
        event_findings = classify_location_label(event)
        if not event_findings:
            continue
        events_with_findings += 1
        source = str(event.get("source") or "unknown")
        for reason, severity in event_findings:
            reason_counts[reason] += 1
            source_counts[source] += 1
            findings.append(
                {
                    "reason": reason,
                    "severity": severity,
                    "event_id": event.get("event_id"),
                    "date": event.get("sort_date_iso") or event.get("date_raw"),
                    "source": source,
                    "location_rendered": event.get("location_display")
                    or event.get("location_raw"),
                    "location_raw": event.get("location_raw"),
                    "location_display": event.get("location_display"),
                    "lat": event.get("lat"),
                    "lon": event.get("lon"),
                    "coordinate_source": event.get("coordinate_source"),
                }
            )

    findings.sort(key=finding_sort_key)
    examples = limited_examples(findings, max_examples_per_reason)
    report = {
        "schema_version": 1,
        "report_policy": "static_location_label_audit_report_only",
        "canonical_outputs_mutated": False,
        "payload_root": str(payload_root.resolve()),
        "status": "ready" if not findings else "needs_attention",
        "counts": {
            "scanned_events": scanned_events,
            "events_with_findings": events_with_findings,
            "finding_rows": len(findings),
        },
        "reason_counts": dict(sorted(reason_counts.items())),
        "source_finding_counts": dict(
            sorted(source_counts.items(), key=lambda item: (-item[1], item[0]))
        ),
        "examples": examples,
        "notes": [
            "Findings describe rendered-label risk, not proof that coordinates are wrong.",
            "Majestic Locale values are environment classifications, not place components.",
            "Raw source labels and rows must remain preserved when display labels are repaired.",
            "Review-severity findings require source or geographic evidence before mutation.",
        ],
    }
    if json_output:
        write_json(json_output, report)
    if csv_output:
        write_csv(csv_output, findings)
    return report


def classify_location_label(event: dict[str, Any]) -> list[tuple[str, str]]:
    source = normalize_component(event.get("source"))
    rendered_value = event.get("location_display") or event.get("location_raw")
    rendered = str(rendered_value or "").strip()
    if not rendered:
        return [("missing_location_label", "review")]

    findings: list[tuple[str, str]] = []
    raw_parts = rendered.split(",")
    parts = [part.strip() for part in raw_parts]
    normalized = [normalize_component(part) for part in parts]

    if any(not part for part in parts):
        findings.append(("empty_comma_component", "safe_display_fix"))
    if MARKUP_OR_URL_RE.search(rendered):
        findings.append(("markup_or_url_in_location", "safe_display_fix"))
    # U+FFFD means the source decoder already lost the original character.
    # Embedded control bytes also occur in the corpus alongside mojibake, where
    # removing only the control byte would leave a misleadingly "fixed" place
    # name.  Both belong in the evidence-backed review lane.
    if "\ufffd" in rendered or any(ord(char) < 32 for char in rendered):
        findings.append(("invalid_character_in_location", "review"))
    if len(rendered) > 180:
        findings.append(("overlong_location_label", "review"))
    if len(parts) > 7:
        findings.append(("excessive_location_components", "review"))

    nonempty_normalized = [part for part in normalized if part]
    if not nonempty_normalized:
        return [("missing_location_label", "review")]
    if any(
        left == right
        for left, right in zip(nonempty_normalized, nonempty_normalized[1:])
    ):
        findings.append(("adjacent_duplicate_component", "safe_display_fix"))
    elif len(set(nonempty_normalized)) < len(nonempty_normalized):
        findings.append(("repeated_component", "safe_display_fix"))

    if all(part in PLACEHOLDER_COMPONENTS for part in nonempty_normalized):
        findings.append(("missing_location_label", "review"))
    elif len(nonempty_normalized) > 1 and any(
        part in PLACEHOLDER_COMPONENTS for part in nonempty_normalized
    ):
        findings.append(("placeholder_component_with_context", "safe_display_fix"))

    place_index = 0
    if (
        source == "majestic"
        and nonempty_normalized
        and nonempty_normalized[0] in MAJESTIC_ENVIRONMENT_CATEGORIES
    ):
        if len(nonempty_normalized) == 1:
            findings.append(("missing_location_label", "review"))
        else:
            findings.append(("majestic_environment_category_prefix", "safe_display_fix"))
        place_index = 1

    if place_index < len(parts) and COORDINATE_LITERAL_RE.match(parts[place_index]):
        findings.append(("coordinate_literal_as_place", "review"))

    us_state_findings = classify_us_state_components(
        parts,
        place_index=place_index,
    )
    findings.extend(us_state_findings)
    return dedupe_findings(findings)


def classify_us_state_components(
    parts: list[str],
    *,
    place_index: int,
) -> list[tuple[str, str]]:
    normalized = [normalize_component(part) for part in parts]
    if not normalized or normalized[-1] not in US_COUNTRY_TOKENS:
        return []

    admin_parts = parts[place_index + 1 : -1]
    state_parts = [
        (part, state)
        for part in admin_parts
        if (state := us_state_code(part))
    ]
    states = [state for _part, state in state_parts]
    unique_states = sorted(set(states))
    if len(unique_states) > 1:
        # A token such as ``MD)`` or ``SD?`` is often part of a parenthetical
        # route description or an uncertainty-qualified source claim.  The
        # robust audit recognizer should still surface it, but the generic
        # display normalizer deliberately accepts only exact administrative
        # components.  Mark the non-exact cases for review instead of claiming
        # they are automatically repairable.
        severity = (
            "uncertainty_display_fix"
            if all(is_exact_us_state_component(part) for part, _state in state_parts)
            else "review"
        )
        return [("contradictory_us_state_components", severity)]
    if len(states) > 1:
        severity = (
            "safe_display_fix"
            if all(is_exact_us_state_component(part) for part, _state in state_parts)
            else "review"
        )
        return [("redundant_us_state_components", severity)]
    return []


def us_state_code(value: Any) -> str | None:
    text = str(value or "").strip().upper().replace(".", "")
    text = re.sub(r"^[^A-Z0-9]+|[^A-Z0-9]+$", "", text)
    if text in US_STATE_BOUNDS:
        return text
    return US_STATE_NAME_TO_ABBREVIATION.get(text)


def is_exact_us_state_component(value: Any) -> bool:
    """Return whether the generic display normalizer can consume the token."""

    text = str(value or "").strip().upper().strip(".")
    return text in US_STATE_BOUNDS or text in US_STATE_NAME_TO_ABBREVIATION


def normalize_component(value: Any) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").lower()))


def dedupe_findings(findings: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    seen: set[str] = set()
    deduped: list[tuple[str, str]] = []
    for reason, severity in findings:
        if reason in seen:
            continue
        seen.add(reason)
        deduped.append((reason, severity))
    return deduped


def iter_static_summary_events(payload_root: Path) -> Iterable[dict[str, Any]]:
    summary_dir = (
        payload_root.resolve() / "data" / "canonical_web" / "summary_shards"
    )
    if not summary_dir.exists():
        raise FileNotFoundError(f"Missing static summary shard directory: {summary_dir}")
    for shard_path in sorted(summary_dir.glob("summary_*.json")):
        payload = json.loads(shard_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"{shard_path} must contain a JSON array.")
        yield from (event for event in payload if isinstance(event, dict))


def finding_sort_key(row: dict[str, Any]) -> tuple[int, str, str, str]:
    severity_rank = {"safe_display_fix": 0, "review": 1}
    return (
        severity_rank.get(str(row.get("severity")), 9),
        str(row.get("reason") or ""),
        str(row.get("source") or ""),
        str(row.get("location_rendered") or ""),
    )


def limited_examples(
    rows: Iterable[dict[str, Any]], max_examples_per_reason: int
) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    selected: list[dict[str, Any]] = []
    for row in rows:
        reason = str(row.get("reason") or "unknown")
        if counts[reason] >= max_examples_per_reason:
            continue
        counts[reason] += 1
        selected.append(row)
    return selected


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "reason",
        "severity",
        "event_id",
        "date",
        "source",
        "location_rendered",
        "location_raw",
        "location_display",
        "lat",
        "lon",
        "coordinate_source",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload-root", type=Path, default=DEFAULT_PAYLOAD_ROOT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--max-examples-per-reason", type=int, default=250)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = audit_static_location_labels(
        payload_root=args.payload_root,
        json_output=args.json_output,
        csv_output=args.csv_output,
        max_examples_per_reason=args.max_examples_per_reason,
    )
    print(
        json.dumps(
            {
                "json": str(args.json_output),
                "csv": str(args.csv_output),
                "status": report["status"],
                **report["counts"],
                "canonical_outputs_mutated": report["canonical_outputs_mutated"],
            },
            indent=2,
        )
    )
    return 0 if report["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
