"""Audit stable record identity from imported sources through the web map payload."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable


DEFAULT_CANONICAL_FULL = Path("data/canonical_full")
DEFAULT_CANONICAL_WEB = Path("data/canonical_web")
DEFAULT_IMPORT_REPORT = Path("data/reports/canonical_import_report.json")
DEFAULT_IMPORT_FAILURES = Path("data/reports/canonical_import_failures.json")
DEFAULT_APP_CONFIG = Path("static_bundle/data/app_config.json")
DEFAULT_JSON_OUTPUT = Path("data/reports/canonical_pipeline_completeness_audit_v152.json")
DEFAULT_MARKDOWN_OUTPUT = Path("data/reports/canonical_pipeline_completeness_audit_v152.md")
SAMPLE_LIMIT = 25


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical-full-dir", type=Path, default=DEFAULT_CANONICAL_FULL)
    parser.add_argument("--canonical-web-dir", type=Path, default=DEFAULT_CANONICAL_WEB)
    parser.add_argument(
        "--expected-events",
        type=Path,
        default=None,
        help="Expected deduped event JSONL. Defaults to canonical-web manifest source.input_path.",
    )
    parser.add_argument("--import-report", type=Path, default=DEFAULT_IMPORT_REPORT)
    parser.add_argument("--import-failures", type=Path, default=DEFAULT_IMPORT_FAILURES)
    parser.add_argument("--app-config", type=Path, default=DEFAULT_APP_CONFIG)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser


def audit_canonical_pipeline_completeness(
    *,
    canonical_full_dir: Path,
    canonical_web_dir: Path,
    expected_events_path: Path | None,
    import_report_path: Path,
    import_failures_path: Path,
    app_config_path: Path | None,
) -> dict[str, Any]:
    canonical_full_dir = canonical_full_dir.resolve()
    canonical_web_dir = canonical_web_dir.resolve()
    import_report_path = import_report_path.resolve()
    import_failures_path = import_failures_path.resolve()
    resolved_app_config = (
        app_config_path.resolve()
        if app_config_path is not None and app_config_path.exists()
        else None
    )

    import_report = _read_json(import_report_path)
    import_failures = _read_json(import_failures_path)
    web_manifest_path = canonical_web_dir / "canonical_web_manifest.json"
    web_manifest = _read_json(web_manifest_path)
    manifest_input_path = str(
        ((web_manifest.get("source") or {}).get("input_path") or "")
    ).strip()
    if expected_events_path is not None:
        resolved_expected_events = expected_events_path.resolve()
    elif manifest_input_path and Path(manifest_input_path).exists():
        resolved_expected_events = Path(manifest_input_path).resolve()
    else:
        resolved_expected_events = (canonical_full_dir / "deduped_events.jsonl").resolve()
    if not resolved_expected_events.exists():
        raise FileNotFoundError(
            "Expected deduped event source is unavailable: "
            f"{resolved_expected_events}"
        )

    expected_input_ids: set[str] = set()
    input_rows = 0
    for row in _read_jsonl(canonical_full_dir / "input_event_lookup.jsonl"):
        input_rows += 1
        input_id = str(row.get("canonical_input_id") or "").strip()
        if input_id:
            expected_input_ids.add(input_id)

    expected_canonical_ids: set[str] = set()
    expected_event_rows = 0
    for row in _read_jsonl(resolved_expected_events):
        expected_event_rows += 1
        canonical_id = str(row.get("canonical_event_id") or "").strip()
        if canonical_id:
            expected_canonical_ids.add(canonical_id)

    web_canonical_ids: set[str] = set()
    web_input_ids: set[str] = set()
    reviewed_removed_ids: set[str] = set()
    reviewed_keeper_ids: set[str] = set()
    reviewed_clusters = 0
    reviewed_preserved_source_records = 0
    for path in sorted((canonical_web_dir / "event_chunks").glob("chunk_*.json")):
        rows = _read_json(path)
        for row in rows:
            canonical_id = str(row.get("canonical_event_id") or "").strip()
            if canonical_id:
                web_canonical_ids.add(canonical_id)
            web_input_ids.update(_string_values(row.get("canonical_input_ids")))
            merge = row.get("reviewed_duplicate_merge")
            if not isinstance(merge, dict):
                continue
            reviewed_clusters += 1
            preferred = str(merge.get("preferred_canonical_event_id") or "").strip()
            if preferred:
                reviewed_keeper_ids.add(preferred)
            member_ids = set(_string_values(merge.get("merged_canonical_event_ids")))
            reviewed_removed_ids.update(member_ids.difference({preferred}))
            reviewed_preserved_source_records += int(
                merge.get("preserved_source_record_count") or 0
            )

    web_event_ids: set[str] = set()
    mapped_web_event_ids: set[str] = set()
    invalid_coordinate_event_ids: set[str] = set()
    unmapped_reason_counts: Counter[str] = Counter()
    for path in sorted((canonical_web_dir / "summary_shards").glob("summary_*.json")):
        rows = _read_json(path)
        for row in rows:
            event_id = str(row.get("event_id") or "").strip()
            if event_id:
                web_event_ids.add(event_id)
            mapped = bool(row.get("has_coordinates"))
            lat = _finite_number(row.get("lat"))
            lon = _finite_number(row.get("lon"))
            coordinates_valid = (
                lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180
            )
            if mapped and coordinates_valid:
                mapped_web_event_ids.add(event_id)
            elif mapped or lat is not None or lon is not None:
                invalid_coordinate_event_ids.add(event_id)
            else:
                unmapped_reason_counts[
                    f"{row.get('coordinate_source') or 'unknown'}"
                    f"|{row.get('location_precision') or 'unknown'}"
                ] += 1

    missing_canonical_ids = expected_canonical_ids.difference(web_canonical_ids)
    undocumented_missing_ids = missing_canonical_ids.difference(reviewed_removed_ids)
    documented_missing_not_expected = reviewed_removed_ids.difference(expected_canonical_ids)
    web_extra_ids = web_canonical_ids.difference(expected_canonical_ids)
    missing_input_ids = expected_input_ids.difference(web_input_ids)
    web_extra_input_ids = web_input_ids.difference(expected_input_ids)

    manifest_counts = web_manifest.get("counts") or {}
    app_config = _read_json(resolved_app_config) if resolved_app_config else {}
    app_normalized = _optional_int(app_config.get("normalizedCount"))
    app_mapped = _optional_int(app_config.get("mappedCount"))
    import_failure_rows = import_failures if isinstance(import_failures, list) else []
    source_record_count = int(import_report.get("source_record_count") or input_rows)
    normalized_event_count = int(
        import_report.get("normalized_event_count") or len(expected_canonical_ids)
    )
    automatic_merge_reduction = source_record_count - len(expected_canonical_ids)

    checks = {
        "source_lookup_rows_match_import_report": input_rows == source_record_count,
        "source_input_ids_are_unique": len(expected_input_ids) == input_rows,
        "expected_event_rows_match_import_report": (
            expected_event_rows == normalized_event_count
        ),
        "expected_canonical_event_ids_are_unique": (
            len(expected_canonical_ids) == expected_event_rows
        ),
        "all_source_inputs_preserved_in_web_provenance": not missing_input_ids,
        "no_unexpected_web_source_inputs": not web_extra_input_ids,
        "all_missing_canonical_shells_are_documented_reviewed_merges": (
            not undocumented_missing_ids and not documented_missing_not_expected
        ),
        "no_unexpected_web_canonical_events": not web_extra_ids,
        "web_event_count_matches_manifest": (
            len(web_event_ids) == int(manifest_counts.get("events") or -1)
        ),
        "mapped_event_count_matches_manifest": (
            len(mapped_web_event_ids) == int(manifest_counts.get("mapped_events") or -1)
        ),
        "no_invalid_serialized_coordinates": not invalid_coordinate_event_ids,
        "import_failures_are_empty": not import_failure_rows,
        "app_config_normalized_count_matches": (
            app_normalized is None or app_normalized == len(web_event_ids)
        ),
        "app_config_mapped_count_matches": (
            app_mapped is None or app_mapped == len(mapped_web_event_ids)
        ),
    }

    return {
        "schema_version": 1,
        "mode": "stable_identity_canonical_pipeline_completeness_audit",
        "status": "passed" if all(checks.values()) else "failed",
        "inputs": {
            "canonical_full_dir": str(canonical_full_dir),
            "canonical_web_dir": str(canonical_web_dir),
            "expected_events": str(resolved_expected_events),
            "import_report": str(import_report_path),
            "import_failures": str(import_failures_path),
            "app_config": str(resolved_app_config) if resolved_app_config else None,
            "canonical_web_manifest_sha256": _sha256(web_manifest_path),
        },
        "source_import": {
            "retained_source_files": import_report.get("retained_source_files") or [],
            "source_record_count": source_record_count,
            "source_lookup_row_count": input_rows,
            "unique_canonical_input_id_count": len(expected_input_ids),
            "import_failure_count": len(import_failure_rows),
            "import_failure_samples": import_failure_rows[:SAMPLE_LIMIT],
            "skipped_files": import_report.get("skipped_files") or [],
        },
        "normalization_and_deduplication": {
            "successfully_normalized_canonical_event_count": normalized_event_count,
            "expected_deduped_event_row_count": expected_event_rows,
            "unique_expected_canonical_event_id_count": len(expected_canonical_ids),
            "automatic_duplicate_record_reduction": automatic_merge_reduction,
            "reviewed_web_merge_cluster_count": reviewed_clusters,
            "reviewed_web_removed_event_shell_count": len(reviewed_removed_ids),
            "reviewed_web_preserved_source_record_sum": reviewed_preserved_source_records,
        },
        "canonical_web": {
            "event_count": len(web_event_ids),
            "mapped_event_count": len(mapped_web_event_ids),
            "without_coordinates_count": len(web_event_ids) - len(mapped_web_event_ids),
            "invalid_coordinate_count": len(invalid_coordinate_event_ids),
            "invalid_coordinate_event_id_samples": _sample(invalid_coordinate_event_ids),
            "unmapped_reason_counts": dict(sorted(unmapped_reason_counts.items())),
            "manifest_event_count": manifest_counts.get("events"),
            "manifest_mapped_event_count": manifest_counts.get("mapped_events"),
        },
        "identity_reconciliation": {
            "expected_canonical_event_count": len(expected_canonical_ids),
            "current_web_canonical_event_count": len(web_canonical_ids),
            "expected_not_current_web_count": len(missing_canonical_ids),
            "documented_reviewed_removed_count": len(reviewed_removed_ids),
            "undocumented_expected_not_current_web_count": len(undocumented_missing_ids),
            "undocumented_expected_not_current_web_samples": _sample(undocumented_missing_ids),
            "documented_removed_not_expected_count": len(documented_missing_not_expected),
            "web_not_expected_count": len(web_extra_ids),
            "web_not_expected_samples": _sample(web_extra_ids),
            "source_input_ids_missing_from_web_provenance_count": len(missing_input_ids),
            "source_input_ids_missing_from_web_provenance_samples": _sample(missing_input_ids),
            "web_provenance_input_ids_not_in_source_lookup_count": len(web_extra_input_ids),
            "web_provenance_input_ids_not_in_source_lookup_samples": _sample(
                web_extra_input_ids
            ),
        },
        "production_count_contract": {
            "app_config_normalized_count": app_normalized,
            "app_config_mapped_count": app_mapped,
        },
        "checks": checks,
    }


def render_markdown(report: dict[str, Any]) -> str:
    source = report["source_import"]
    normalized = report["normalization_and_deduplication"]
    web = report["canonical_web"]
    identity = report["identity_reconciliation"]
    failed = [name for name, passed in report["checks"].items() if not passed]
    lines = [
        "# Canonical Pipeline Completeness Audit",
        "",
        f"Status: **{report['status'].upper()}**",
        "",
        "## Stage counts",
        "",
        "| Stage | Count |",
        "| --- | ---: |",
        f"| Imported source records | {source['source_record_count']:,} |",
        f"| Successfully normalized canonical events | {normalized['successfully_normalized_canonical_event_count']:,} |",
        f"| Automatic duplicate-record reduction | {normalized['automatic_duplicate_record_reduction']:,} |",
        f"| Reviewed web-only duplicate shells removed | {normalized['reviewed_web_removed_event_shell_count']:,} |",
        f"| Current canonical-web events | {web['event_count']:,} |",
        f"| Current mapped events | {web['mapped_event_count']:,} |",
        f"| Events retained without coordinates | {web['without_coordinates_count']:,} |",
        f"| Invalid serialized coordinates | {web['invalid_coordinate_count']:,} |",
        "",
        "## Stable-identity reconciliation",
        "",
        f"- Import failures: **{source['import_failure_count']:,}**",
        f"- Source input IDs missing from web provenance: **{identity['source_input_ids_missing_from_web_provenance_count']:,}**",
        f"- Expected canonical shells absent without a reviewed-merge record: **{identity['undocumented_expected_not_current_web_count']:,}**",
        f"- Web canonical events absent from the expected source output: **{identity['web_not_expected_count']:,}**",
        "",
        "Records without coordinates remain in the catalog and results; they are omitted only from map-point rendering.",
        "",
        "## Checks",
        "",
    ]
    lines.extend(
        f"- {'PASS' if passed else 'FAIL'} — `{name}`"
        for name, passed in report["checks"].items()
    )
    if failed:
        lines.extend(["", "Failed checks: " + ", ".join(failed)])
    return "\n".join(lines) + "\n"


def _read_json(path: Path | None) -> Any:
    if path is None:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            value = json.loads(text)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} is not a JSON object")
            yield value


def _string_values(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _sample(values: Iterable[str]) -> list[str]:
    return sorted(set(values))[:SAMPLE_LIMIT]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    args = build_argument_parser().parse_args()
    report = audit_canonical_pipeline_completeness(
        canonical_full_dir=args.canonical_full_dir,
        canonical_web_dir=args.canonical_web_dir,
        expected_events_path=args.expected_events,
        import_report_path=args.import_report,
        import_failures_path=args.import_failures,
        app_config_path=args.app_config,
    )
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"status": report["status"], "checks": report["checks"]}))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
