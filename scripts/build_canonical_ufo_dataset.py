"""Build the canonical offline UFO CSV dataset and dedupe artifacts."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from parser.canonical_schema import (
    EXACT_SUBSET_DROP_FILES,
    RETAINED_CSV_SOURCE_FILES,
    clean_text,
    normalize_type_label,
    source_claims_for_record,
    stable_hash,
)
from parser.canonical_export import canonical_events_to_normalized_events
from parser.csv_sources import adapter_for_path
from parser.dedupe import (
    DEFAULT_DUPLICATE_CANDIDATE_LIMIT,
    DEDUPE_STRATEGY_AGGRESSIVE_V1,
    DEDUPE_STRATEGY_EXACT,
    DEDUPE_STRATEGY_MAXIMAL_V1,
    DEDUPE_STRATEGY_MAXIMAL_V2,
    DEDUPE_STRATEGY_MAXIMAL_V3,
    SUPPORTED_DEDUPE_STRATEGIES,
    build_deduped_events,
    build_duplicate_candidates,
)
from parser.taxonomy import normalize_shape_label
from parser.utils import write_json, write_jsonl


DEFAULT_SOURCE_DIR = Path("UFO Databases")
DEFAULT_OUTPUT_DIR = Path("data/canonical")
DEFAULT_REPORTS_DIR = Path("data/reports")
DEFAULT_SOURCE_COLUMN_MAPPING_PATH = Path("data/canonical/source_column_mapping.json")
DEFAULT_AUDIT_REPORT_PATH = Path("data/reports/ufo_csv_audit.json")


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dir",
        default=str(DEFAULT_SOURCE_DIR),
        help="Directory containing local UFO CSV source files.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for canonical JSONL outputs.",
    )
    parser.add_argument(
        "--reports-dir",
        default=str(DEFAULT_REPORTS_DIR),
        help="Directory for import and dedupe reports.",
    )
    parser.add_argument(
        "--limit-per-source",
        type=int,
        default=None,
        help="Optional row limit per retained source for smoke tests.",
    )
    parser.add_argument(
        "--source-column-mapping",
        default=str(DEFAULT_SOURCE_COLUMN_MAPPING_PATH),
        help=(
            "Optional audit-generated source column mapping JSON used to emit "
            "provenance-linked source claims from high-value raw columns."
        ),
    )
    parser.add_argument(
        "--no-source-column-mapping",
        action="store_true",
        help="Disable source-claim generation from source_column_mapping.json.",
    )
    parser.add_argument(
        "--audit-report",
        default=str(DEFAULT_AUDIT_REPORT_PATH),
        help="Optional CSV audit report used to drive verified exact-subset pruning.",
    )
    parser.add_argument(
        "--no-audit-report",
        action="store_true",
        help="Disable audit-driven source file planning and use built-in retained/drop sets.",
    )
    parser.add_argument(
        "--write-legacy-canonical-input-events",
        action="store_true",
        help=(
            "Also write canonical_input_events.jsonl as a legacy duplicate of "
            "source_records.jsonl. Disabled by default to avoid multi-GB duplication."
        ),
    )
    parser.add_argument(
        "--manual-review-decisions",
        default=None,
        help=(
            "Optional JSONL or JSON-array file of manual review decisions keyed by "
            "manual_review_queue review_item_id. Decisions are recorded as "
            "non-destructive annotations in this build."
        ),
    )
    parser.add_argument(
        "--dedupe-strategy",
        choices=sorted(SUPPORTED_DEDUPE_STRATEGIES),
        default=DEDUPE_STRATEGY_EXACT,
        help=(
            "Canonical auto-merge strategy. Use maximal_v3 for the most aggressive "
            "rule-based consolidation currently supported."
        ),
    )
    return parser


def build_canonical_dataset(
    *,
    source_dir: Path,
    output_dir: Path,
    reports_dir: Path,
    limit_per_source: int | None = None,
    source_column_mapping_path: Path | None = None,
    audit_report_path: Path | None = None,
    write_legacy_canonical_input_events: bool = False,
    manual_review_decisions_path: Path | None = None,
    dedupe_strategy: str = DEDUPE_STRATEGY_EXACT,
) -> dict[str, Any]:
    source_dir = source_dir.resolve()
    output_dir = output_dir.resolve()
    reports_dir = reports_dir.resolve()
    source_column_mapping = load_source_column_mapping(source_column_mapping_path)
    audit_report = load_audit_report(audit_report_path)
    source_plan = build_source_file_plan(source_dir, audit_report)

    source_records = []
    source_report: list[dict[str, Any]] = []
    skipped_files: list[dict[str, Any]] = []
    import_failures: list[dict[str, Any]] = []

    for file_name in source_plan["retained_source_files"]:
        path = source_dir / file_name
        if not path.exists():
            skipped_files.append(
                {
                    "file": file_name,
                    "reason": "missing_retained_source",
                }
            )
            continue

        adapter = adapter_for_path(path)
        if adapter is None:
            skipped_files.append(
                {
                    "file": file_name,
                    "reason": "no_adapter",
                }
            )
            continue

        before_count = len(source_records)
        failure_record = None
        try:
            for record in adapter.iter_records(path, limit=limit_per_source):
                source_records.append(record)
        except Exception as exc:  # pragma: no cover - defensive reporting path
            failure_record = {
                "file": file_name,
                "source_name": adapter.source_name,
                "error_type": type(exc).__name__,
                "message": str(exc),
                "imported_records_before_failure": len(source_records) - before_count,
            }
            import_failures.append(failure_record)
        imported_count = len(source_records) - before_count
        source_report.append(
            {
                "file": file_name,
                "source_name": adapter.source_name,
                "imported_records": imported_count,
                "limit_applied": limit_per_source,
                "import_status": "failed" if failure_record else "imported",
            }
        )

    for skip_record in source_plan["exact_subset_pruned_files"]:
        if (source_dir / skip_record["file"]).exists():
            skipped_files.append(skip_record)

    deduped_events, duplicate_groups = build_deduped_events(source_records, strategy=dedupe_strategy)
    duplicate_candidates = build_duplicate_candidates(source_records)
    normalized_events = canonical_events_to_normalized_events(deduped_events)
    map_events = [
        event
        for event in normalized_events
        if event.get("lat") is not None and event.get("lon") is not None
    ]

    source_record_dicts = [record.to_json_dict() for record in source_records]
    source_claims, source_claim_report = build_source_claims(
        source_records,
        source_column_mapping=source_column_mapping,
    )
    column_accounting = build_column_accounting(
        source_records,
        source_column_mapping=source_column_mapping,
    )
    manual_review_queue = build_manual_review_queue(
        source_records=source_records,
        duplicate_candidates=duplicate_candidates,
        column_accounting=column_accounting,
        import_failures=import_failures,
    )
    manual_review_decisions = load_manual_review_decisions(manual_review_decisions_path)
    (
        manual_review_queue,
        applied_manual_review_decisions,
        manual_review_decision_report,
    ) = apply_manual_review_decisions(
        manual_review_queue,
        manual_review_decisions,
        decisions_path=manual_review_decisions_path,
    )
    write_jsonl(output_dir / "source_records.jsonl", source_record_dicts)
    legacy_canonical_input_events_path = output_dir / "canonical_input_events.jsonl"
    if write_legacy_canonical_input_events:
        write_jsonl(legacy_canonical_input_events_path, source_record_dicts)
    elif legacy_canonical_input_events_path.exists():
        legacy_canonical_input_events_path.unlink()
    write_jsonl(output_dir / "source_claims.jsonl", source_claims)
    write_jsonl(output_dir / "deduped_events.jsonl", deduped_events)
    write_jsonl(output_dir / "duplicate_groups.jsonl", duplicate_groups)
    write_jsonl(output_dir / "duplicate_candidates.jsonl", duplicate_candidates)
    write_jsonl(output_dir / "manual_review_queue.jsonl", manual_review_queue)
    write_jsonl(output_dir / "manual_review_applied_decisions.jsonl", applied_manual_review_decisions)
    write_json(output_dir / "normalized_events.json", normalized_events)
    write_json(output_dir / "map_events.json", map_events)
    write_json(output_dir / "manual_review_decision_schema.json", manual_review_decision_schema(), indent=2)
    write_json(reports_dir / "canonical_column_accounting.json", column_accounting, indent=2)
    write_json(reports_dir / "canonical_import_failures.json", import_failures, indent=2)
    write_json(reports_dir / "manual_review_decisions_report.json", manual_review_decision_report, indent=2)

    import_report = {
        "source_dir": str(source_dir),
        "retained_source_files": source_plan["retained_source_files"],
        "exact_subset_drop_files": source_plan["exact_subset_drop_files"],
        "source_file_plan": {
            "source": source_plan["source"],
            "audit_report_path": str(audit_report_path.resolve())
            if audit_report_path is not None and audit_report_path.exists()
            else None,
        },
        "sources": source_report,
        "skipped_files": skipped_files,
        "source_record_count": len(source_records),
        "legacy_canonical_input_events_written": write_legacy_canonical_input_events,
        "source_claim_count": len(source_claims),
        "source_claims": source_claim_report,
        "column_accounting": {
            "report_path": str((reports_dir / "canonical_column_accounting.json").resolve()),
            "files": len(column_accounting.get("sources", {})),
            "unmapped_header_count": column_accounting.get("summary", {}).get("unmapped_header_count", 0),
            "source_specific_non_empty_value_count": column_accounting.get("summary", {}).get(
                "source_specific_non_empty_value_count",
                0,
            ),
            "row_shape_anomaly_count": column_accounting.get("summary", {}).get("row_shape_anomaly_count", 0),
        },
        "import_failures": {
            "report_path": str((reports_dir / "canonical_import_failures.json").resolve()),
            "count": len(import_failures),
        },
        "source_column_mapping_path": str(source_column_mapping_path.resolve())
        if source_column_mapping_path is not None and source_column_mapping_path.exists()
        else None,
        "deduped_event_count": len(deduped_events),
        "normalized_event_count": len(normalized_events),
        "map_event_count": len(map_events),
        "duplicate_group_count": len(duplicate_groups),
        "duplicate_candidate_count": len(duplicate_candidates),
        "duplicate_candidate_limit": DEFAULT_DUPLICATE_CANDIDATE_LIMIT,
        "duplicate_candidate_limit_reached": len(duplicate_candidates) >= DEFAULT_DUPLICATE_CANDIDATE_LIMIT,
        "manual_review_queue_count": len(manual_review_queue),
        "manual_review_queue": {
            "queue_path": str((output_dir / "manual_review_queue.jsonl").resolve()),
            "decision_schema_path": str((output_dir / "manual_review_decision_schema.json").resolve()),
            "type_counts": count_review_item_types(manual_review_queue),
            "status_counts": count_review_item_statuses(manual_review_queue),
        },
        "manual_review_decisions": {
            "decisions_path": str(manual_review_decisions_path.resolve())
            if manual_review_decisions_path is not None
            else None,
            "applied_decisions_path": str((output_dir / "manual_review_applied_decisions.jsonl").resolve()),
            "report_path": str((reports_dir / "manual_review_decisions_report.json").resolve()),
            "provided_decision_count": manual_review_decision_report["provided_decision_count"],
            "applied_decision_count": manual_review_decision_report["applied_decision_count"],
            "invalid_decision_count": len(manual_review_decision_report["invalid_decisions"]),
            "unknown_review_item_id_count": len(manual_review_decision_report["unknown_review_item_ids"]),
            "effect_policy": manual_review_decision_report["effect_policy"],
        },
        "limit_per_source": limit_per_source,
        "dedupe_strategy": dedupe_strategy,
    }
    dedupe_report = {
        "strategy": dedupe_strategy,
        "auto_merge_policy": dedupe_auto_merge_policy(dedupe_strategy),
        "duplicate_candidate_policy": "Fuzzy pairs are emitted for review only and are never auto-merged.",
        "fuzzy_auto_merge_enabled": dedupe_strategy != DEDUPE_STRATEGY_EXACT,
        "source_record_count": len(source_records),
        "deduped_event_count": len(deduped_events),
        "projected_record_reduction": max(0, len(source_records) - len(deduped_events)),
        "duplicate_group_count": len(duplicate_groups),
        "duplicate_candidate_count": len(duplicate_candidates),
        "duplicate_candidate_limit": DEFAULT_DUPLICATE_CANDIDATE_LIMIT,
        "duplicate_candidate_limit_reached": len(duplicate_candidates) >= DEFAULT_DUPLICATE_CANDIDATE_LIMIT,
        "manual_review_queue_count": len(manual_review_queue),
        "manual_review_applied_decision_count": manual_review_decision_report["applied_decision_count"],
        "manual_review_decision_effect_policy": manual_review_decision_report["effect_policy"],
    }
    write_json(reports_dir / "canonical_import_report.json", import_report, indent=2)
    write_json(reports_dir / "dedupe_report.json", dedupe_report, indent=2)

    return {
        **import_report,
        "output_dir": str(output_dir),
        "reports_dir": str(reports_dir),
    }


def dedupe_auto_merge_policy(strategy: str) -> dict[str, Any]:
    if strategy == DEDUPE_STRATEGY_EXACT:
        return {
            "name": DEDUPE_STRATEGY_EXACT,
            "description": (
                "Exact canonical duplicate fingerprints are merged automatically. "
                "Fuzzy candidates remain review-only."
            ),
            "auto_merge_families": ["exact_canonical_fingerprint"],
        }
    if strategy == DEDUPE_STRATEGY_AGGRESSIVE_V1:
        return {
            "name": DEDUPE_STRATEGY_AGGRESSIVE_V1,
            "description": (
                "Auto-merge exact duplicates plus high-yield same-source/native-ID, "
                "exact-day/location/time, trusted-coordinate/time, and same-source "
                "exact-day/location/type families. Fuzzy text candidates remain review-only."
            ),
            "auto_merge_families": [
                "exact_canonical_fingerprint",
                "same_source_native_id_any_date",
                "same_source_native_id_strong_date",
                "strong_date_location_specific_time",
                "same_source_strong_date_location_specific_time",
                "strong_date_coordinate_specific_time",
                "same_source_strong_date_coordinate_cell_specific_time",
                "same_source_strong_date_location_type",
                "same_source_strong_date_coordinate_type",
                "same_source_strong_date_location",
                "same_source_strong_date_coordinate_cell",
            ],
        }
    if strategy == DEDUPE_STRATEGY_MAXIMAL_V1:
        return {
            "name": DEDUPE_STRATEGY_MAXIMAL_V1,
            "description": (
                "Includes aggressive_v1 plus cross-source exact-day/location/type, "
                "exact-day/coordinate/type, and low-confidence cross-source exact-day/location "
                "families. This is intended for aggressive production review runs."
            ),
            "auto_merge_families": [
                *dedupe_auto_merge_policy(DEDUPE_STRATEGY_AGGRESSIVE_V1)["auto_merge_families"],
                "strong_date_location_type",
                "strong_date_coordinate_type",
                "strong_date_location",
                "strong_date_coordinate_cell",
            ],
        }
    if strategy == DEDUPE_STRATEGY_MAXIMAL_V2:
        return {
            "name": DEDUPE_STRATEGY_MAXIMAL_V2,
            "description": (
                "Includes maximal_v1 plus structured city/state/country exact-day "
                "merge keys so county/no-county and inconsistent raw-location variants "
                "can merge without relying on broad city-only matching."
            ),
            "auto_merge_families": [
                *dedupe_auto_merge_policy(DEDUPE_STRATEGY_MAXIMAL_V1)["auto_merge_families"],
                "same_source_strong_date_structured_city_state_country",
                "same_source_strong_date_structured_city_state",
                "same_source_strong_date_structured_city_country_type",
                "strong_date_structured_city_state_country",
                "strong_date_structured_city_state",
                "strong_date_structured_city_country_type",
            ],
        }
    if strategy == DEDUPE_STRATEGY_MAXIMAL_V3:
        return {
            "name": DEDUPE_STRATEGY_MAXIMAL_V3,
            "description": (
                "Uses maximal_v2 state-aware merge families and replaces broad "
                "city/country/type joins with a group-aware exact-day city/country "
                "merge that links state-present and state-missing variants only "
                "when all known states/provinces in the block agree."
            ),
            "auto_merge_families": [
                family
                for family in dedupe_auto_merge_policy(DEDUPE_STRATEGY_MAXIMAL_V2)["auto_merge_families"]
                if family
                not in {
                    "same_source_strong_date_structured_city_country_type",
                    "strong_date_structured_city_country_type",
                }
            ] + [
                "strong_date_structured_city_country_no_state_conflict",
            ],
        }
    return {
        "name": strategy,
        "description": "Unknown strategy.",
        "auto_merge_families": [],
    }


def load_source_column_mapping(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    mapping_path = path.resolve()
    if not mapping_path.exists():
        return {}
    return json.loads(mapping_path.read_text(encoding="utf-8"))


def load_audit_report(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    audit_path = path.resolve()
    if not audit_path.exists():
        return {}
    return json.loads(audit_path.read_text(encoding="utf-8"))


def build_source_file_plan(source_dir: Path, audit_report: dict[str, Any]) -> dict[str, Any]:
    retained_files = sorted(RETAINED_CSV_SOURCE_FILES)
    exact_subset_drop_files = dict(EXACT_SUBSET_DROP_FILES)
    exact_subset_pruned_files = [
        {
            "file": dropped_file,
            "reason": "exact_subset_pruned",
            "retained_file": retained_file,
            "evidence_source": "built_in_exact_subset_map",
        }
        for dropped_file, retained_file in sorted(EXACT_SUBSET_DROP_FILES.items())
    ]
    plan_source = "built_in"

    audit_retained = audit_report.get("recommended_keep_files_after_exact_subset_pruning")
    audit_pairs = audit_report.get("exact_overlap_pairs")
    if isinstance(audit_retained, list) and isinstance(audit_pairs, list):
        verified_pairs = []
        for pair in audit_pairs:
            if not is_verified_exact_subset_pair(pair):
                continue
            retained_file = pair["recommended_keep"]
            dropped_file = pair["recommended_drop"]
            if not (source_dir / retained_file).exists():
                continue
            verified_pairs.append(
                {
                    "file": dropped_file,
                    "reason": "exact_subset_pruned",
                    "retained_file": retained_file,
                    "evidence_source": "ufo_csv_audit",
                    "relationship": pair.get("relationship"),
                    "exact_overlap": pair.get("exact_overlap"),
                    "left_only": pair.get("left_only"),
                    "right_only": pair.get("right_only"),
                }
            )

        if verified_pairs:
            retained_files = sorted(str(file_name) for file_name in audit_retained)
            exact_subset_drop_files = {
                item["file"]: item["retained_file"]
                for item in verified_pairs
            }
            exact_subset_pruned_files = sorted(verified_pairs, key=lambda item: item["file"])
            plan_source = "ufo_csv_audit"

    return {
        "source": plan_source,
        "retained_source_files": retained_files,
        "exact_subset_drop_files": exact_subset_drop_files,
        "exact_subset_pruned_files": exact_subset_pruned_files,
    }


def is_verified_exact_subset_pair(pair: Any) -> bool:
    if not isinstance(pair, dict):
        return False
    return (
        pair.get("relationship") == "left_subset_of_right"
        and pair.get("left_only") == 0
        and bool(pair.get("recommended_keep"))
        and bool(pair.get("recommended_drop"))
    )


def build_source_claims(
    source_records: list[Any],
    *,
    source_column_mapping: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    seen_claim_ids: set[str] = set()
    origin_counts = {
        "adapter_explicit_field": 0,
        "source_column_mapping": 0,
    }

    for record in source_records:
        for claim in source_claims_for_record(record):
            if add_unique_source_claim(claims, seen_claim_ids, claim):
                origin_counts["adapter_explicit_field"] += 1
        for claim in source_claims_from_column_mapping(record, source_column_mapping):
            if add_unique_source_claim(claims, seen_claim_ids, claim):
                origin_counts["source_column_mapping"] += 1

    return claims, {
        "total": len(claims),
        "origin_counts": origin_counts,
        "source_column_mapping_enabled": bool(source_column_mapping),
    }


def build_column_accounting(
    source_records: list[Any],
    *,
    source_column_mapping: dict[str, Any],
) -> dict[str, Any]:
    records_by_file: dict[str, list[Any]] = {}
    for record in source_records:
        records_by_file.setdefault(record.source_file, []).append(record)

    summary = {
        "file_count": len(records_by_file),
        "header_column_count": 0,
        "unmapped_header_count": 0,
        "source_specific_non_empty_value_count": 0,
        "source_claim_non_empty_value_count": 0,
        "row_shape_anomaly_count": 0,
    }
    sources: dict[str, Any] = {}

    for source_file, records in sorted(records_by_file.items()):
        header = first_non_empty_header(records)
        source_mapping = source_column_mapping.get("sources", {}).get(source_file, {})
        mapped_headers = set(source_mapping)
        header_set = set(header)
        unmapped_headers = [column_name for column_name in header if column_name not in mapped_headers]
        mapping_action_counts: dict[str, int] = {
            "canonical": 0,
            "source_claim": 0,
            "source_specific": 0,
            "ignore_empty": 0,
            "unmapped": len(unmapped_headers),
        }
        mapped_columns_by_action: dict[str, list[str]] = {
            "canonical": [],
            "source_claim": [],
            "source_specific": [],
            "ignore_empty": [],
        }
        for column_name in header:
            column_mapping = source_mapping.get(column_name)
            if not column_mapping:
                continue
            action = column_mapping.get("mapping_action") or "unmapped"
            mapping_action_counts[action] = mapping_action_counts.get(action, 0) + 1
            mapped_columns_by_action.setdefault(action, []).append(column_name)

        extra_mapped_columns = sorted(mapped_headers - header_set)
        source_specific_non_empty_values = count_non_empty_mapped_values(
            records,
            source_mapping,
            mapping_action="source_specific",
        )
        source_claim_non_empty_values = count_non_empty_mapped_values(
            records,
            source_mapping,
            mapping_action="source_claim",
        )
        row_shape_anomaly_counts = count_row_shape_anomalies(records)
        row_shape_anomaly_count = sum(row_shape_anomaly_counts.values())

        summary["header_column_count"] += len(header)
        summary["unmapped_header_count"] += len(unmapped_headers)
        summary["source_specific_non_empty_value_count"] += source_specific_non_empty_values
        summary["source_claim_non_empty_value_count"] += source_claim_non_empty_values
        summary["row_shape_anomaly_count"] += row_shape_anomaly_count

        sources[source_file] = {
            "imported_records": len(records),
            "header_column_count": len(header),
            "row_shape_anomaly_counts": row_shape_anomaly_counts,
            "mapping_action_counts": mapping_action_counts,
            "mapped_columns_by_action": mapped_columns_by_action,
            "unmapped_headers": unmapped_headers,
            "extra_mapped_columns_not_in_header": extra_mapped_columns,
            "source_specific_columns": mapped_columns_by_action.get("source_specific", []),
            "source_specific_non_empty_value_count": source_specific_non_empty_values,
            "source_claim_columns": mapped_columns_by_action.get("source_claim", []),
            "source_claim_non_empty_value_count": source_claim_non_empty_values,
        }

    return {
        "source_column_mapping_enabled": bool(source_column_mapping),
        "summary": summary,
        "sources": sources,
    }


def first_non_empty_header(records: list[Any]) -> list[str]:
    for record in records:
        if record.raw_source_header:
            return list(record.raw_source_header)
    return []


def count_non_empty_mapped_values(
    records: list[Any],
    source_mapping: dict[str, Any],
    *,
    mapping_action: str,
) -> int:
    columns = [
        column_name
        for column_name, column_mapping in source_mapping.items()
        if column_mapping.get("mapping_action") == mapping_action
    ]
    count = 0
    for record in records:
        for column_name in columns:
            if clean_text(record.raw_source_row.get(column_name)):
                count += 1
    return count


def count_row_shape_anomalies(records: list[Any]) -> dict[str, int]:
    anomaly_counts: dict[str, int] = {}
    for record in records:
        for anomaly in record.source_row_anomalies:
            anomaly_counts[anomaly] = anomaly_counts.get(anomaly, 0) + 1
    return anomaly_counts


def load_manual_review_decisions(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []

    decision_path = path.resolve()
    if not decision_path.exists():
        raise FileNotFoundError(f"Manual review decisions file not found: {decision_path}")

    raw_text = decision_path.read_text(encoding="utf-8")
    if not raw_text.strip():
        return []

    if raw_text.lstrip().startswith("["):
        payload = json.loads(raw_text)
        if not isinstance(payload, list):
            raise ValueError("Manual review decisions JSON array must contain objects.")
        return payload

    decisions: list[dict[str, Any]] = []
    for line_number, line in enumerate(raw_text.splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"Manual review decision line {line_number} must be a JSON object.")
        decisions.append(payload)
    return decisions


def apply_manual_review_decisions(
    queue: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    *,
    decisions_path: Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    updated_queue = copy.deepcopy(queue)
    queue_by_id = {
        item.get("review_item_id"): item
        for item in updated_queue
        if item.get("review_item_id")
    }
    applied_decisions: list[dict[str, Any]] = []
    applied_review_item_ids: set[str] = set()
    unknown_review_item_ids: list[dict[str, Any]] = []
    invalid_decisions: list[dict[str, Any]] = []

    for decision_index, raw_decision in enumerate(decisions, start=1):
        if not isinstance(raw_decision, dict):
            invalid_decisions.append(
                {
                    "decision_index": decision_index,
                    "reason": "decision_record_must_be_object",
                }
            )
            continue

        review_item_id = clean_text(raw_decision.get("review_item_id"))
        decision = clean_text(raw_decision.get("decision"))
        if not review_item_id:
            invalid_decisions.append(
                {
                    "decision_index": decision_index,
                    "reason": "missing_review_item_id",
                    "decision": decision,
                }
            )
            continue
        if not decision:
            invalid_decisions.append(
                {
                    "decision_index": decision_index,
                    "review_item_id": review_item_id,
                    "reason": "missing_decision",
                }
            )
            continue

        queue_item = queue_by_id.get(review_item_id)
        if queue_item is None:
            unknown_review_item_ids.append(
                {
                    "decision_index": decision_index,
                    "review_item_id": review_item_id,
                    "decision": decision,
                }
            )
            continue

        if review_item_id in applied_review_item_ids:
            invalid_decisions.append(
                {
                    "decision_index": decision_index,
                    "review_item_id": review_item_id,
                    "decision": decision,
                    "reason": "duplicate_decision_for_review_item",
                }
            )
            continue

        suggested_decisions = set(queue_item.get("suggested_decisions") or [])
        if decision not in suggested_decisions:
            invalid_decisions.append(
                {
                    "decision_index": decision_index,
                    "review_item_id": review_item_id,
                    "decision": decision,
                    "reason": "decision_not_allowed_for_review_type",
                    "allowed_decisions": sorted(suggested_decisions),
                }
            )
            continue

        applied_decision = build_applied_manual_review_decision(
            raw_decision,
            queue_item=queue_item,
            decision_index=decision_index,
        )
        queue_item["status"] = "reviewed"
        queue_item["manual_decision"] = applied_decision
        queue_item["decision_effect"] = "record_only"
        applied_decisions.append(applied_decision)
        applied_review_item_ids.add(review_item_id)

    return updated_queue, applied_decisions, build_manual_review_decision_report(
        decisions=decisions,
        applied_decisions=applied_decisions,
        invalid_decisions=invalid_decisions,
        unknown_review_item_ids=unknown_review_item_ids,
        updated_queue=updated_queue,
        decisions_path=decisions_path,
    )


def build_applied_manual_review_decision(
    decision_record: dict[str, Any],
    *,
    queue_item: dict[str, Any],
    decision_index: int,
) -> dict[str, Any]:
    applied = {
        "review_item_id": clean_text(decision_record.get("review_item_id")),
        "review_type": queue_item.get("review_type"),
        "decision": clean_text(decision_record.get("decision")),
        "decision_index": decision_index,
        "apply_effect": "record_only",
        "effect_note": (
            "Decision is recorded on the manual review queue only; fuzzy duplicate "
            "merge/exclusion effects are not applied to canonical event outputs in this pass."
        ),
    }

    for optional_field in ("reviewer", "reviewed_at", "notes", "replacement_canonical_event_id"):
        value = clean_text(decision_record.get(optional_field))
        if value:
            applied[optional_field] = value

    excluded_ids = normalize_decision_id_list(decision_record.get("exclude_canonical_input_ids"))
    if excluded_ids:
        applied["exclude_canonical_input_ids"] = excluded_ids

    return applied


def normalize_decision_id_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = clean_text(value)
        return [text] if text else []
    if not isinstance(value, list):
        return []
    ids: list[str] = []
    for item in value:
        text = clean_text(item)
        if text:
            ids.append(text)
    return ids


def build_manual_review_decision_report(
    *,
    decisions: list[dict[str, Any]],
    applied_decisions: list[dict[str, Any]],
    invalid_decisions: list[dict[str, Any]],
    unknown_review_item_ids: list[dict[str, Any]],
    updated_queue: list[dict[str, Any]],
    decisions_path: Path | None,
) -> dict[str, Any]:
    decision_counts: dict[str, int] = {}
    for applied_decision in applied_decisions:
        decision = applied_decision.get("decision") or "unknown"
        decision_counts[decision] = decision_counts.get(decision, 0) + 1

    return {
        "decisions_path": str(decisions_path.resolve()) if decisions_path is not None else None,
        "provided_decision_count": len(decisions),
        "applied_decision_count": len(applied_decisions),
        "decision_counts": decision_counts,
        "unknown_review_item_ids": unknown_review_item_ids,
        "invalid_decisions": invalid_decisions,
        "queue_status_counts": count_review_item_statuses(updated_queue),
        "effect_policy": "record_only",
        "canonical_outputs_mutated": False,
    }


def build_manual_review_queue(
    *,
    source_records: list[Any],
    duplicate_candidates: list[dict[str, Any]],
    column_accounting: dict[str, Any],
    import_failures: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []

    for candidate in duplicate_candidates:
        review_item = {
            "review_item_id": stable_hash(
                {
                    "type": "duplicate_candidate",
                    "duplicate_candidate_id": candidate.get("duplicate_candidate_id"),
                },
                prefix="rev_",
                length=24,
            ),
            "review_type": "duplicate_candidate",
            "priority": "high" if candidate.get("score", 0) >= 0.9 else "medium",
            "status": "needs_review",
            "reason": "bounded fuzzy duplicate candidate; never auto-merged",
            "candidate": candidate,
            "suggested_decisions": ["same_event", "distinct_events", "needs_more_evidence"],
        }
        queue.append(review_item)

    for record in source_records:
        if not record.source_row_anomalies:
            continue
        queue.append(
            {
                "review_item_id": stable_hash(
                    {
                        "type": "row_shape_anomaly",
                        "canonical_input_id": record.canonical_input_id,
                        "anomalies": record.source_row_anomalies,
                    },
                    prefix="rev_",
                    length=24,
                ),
                "review_type": "row_shape_anomaly",
                "priority": "high" if record.raw_source_extra_columns else "medium",
                "status": "needs_review",
                "reason": "source row column count does not match header",
                "canonical_input_id": record.canonical_input_id,
                "source_file": record.source_file,
                "source_row_number": record.source_row_number,
                "source_native_id": record.source_native_id,
                "source_row_anomalies": list(record.source_row_anomalies),
                "raw_source_extra_columns": list(record.raw_source_extra_columns),
                "raw_source_missing_columns": list(record.raw_source_missing_columns),
                "suggested_decisions": ["accept_preserved_row", "repair_source_row", "exclude_source_row"],
            }
        )

    if column_accounting.get("source_column_mapping_enabled"):
        for source_file, source_accounting in column_accounting.get("sources", {}).items():
            unmapped_headers = source_accounting.get("unmapped_headers") or []
            if not unmapped_headers:
                continue
            queue.append(
                {
                    "review_item_id": stable_hash(
                        {
                            "type": "unmapped_headers",
                            "source_file": source_file,
                            "unmapped_headers": unmapped_headers,
                        },
                        prefix="rev_",
                        length=24,
                    ),
                    "review_type": "unmapped_headers",
                    "priority": "medium",
                    "status": "needs_review",
                    "reason": "imported source has headers absent from source_column_mapping",
                    "source_file": source_file,
                    "unmapped_headers": unmapped_headers,
                    "imported_records": source_accounting.get("imported_records"),
                    "suggested_decisions": ["map_columns", "mark_source_specific", "ignore_if_empty"],
                }
            )

    for failure in import_failures:
        queue.append(
            {
                "review_item_id": stable_hash(
                    {
                        "type": "import_failure",
                        "file": failure.get("file"),
                        "error_type": failure.get("error_type"),
                        "message": failure.get("message"),
                    },
                    prefix="rev_",
                    length=24,
                ),
                "review_type": "import_failure",
                "priority": "high",
                "status": "needs_review",
                "reason": "source adapter raised during canonical import",
                "failure": failure,
                "suggested_decisions": ["fix_adapter", "fix_source_file", "exclude_source_file"],
            }
        )

    return sorted(
        queue,
        key=lambda item: (
            {"high": 0, "medium": 1, "low": 2}.get(item.get("priority"), 9),
            item.get("review_type", ""),
            item.get("review_item_id", ""),
        ),
    )


def count_review_item_types(queue: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in queue:
        review_type = item.get("review_type") or "unknown"
        counts[review_type] = counts.get(review_type, 0) + 1
    return counts


def count_review_item_statuses(queue: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in queue:
        status = item.get("status") or "unknown"
        counts[status] = counts.get(status, 0) + 1
    return counts


def manual_review_decision_schema() -> dict[str, Any]:
    return {
        "description": "Schema for human/manual adjudication decisions keyed by manual_review_queue review_item_id.",
        "input_format": "JSONL with one decision object per line, or one JSON array of decision objects.",
        "fields": {
            "review_item_id": "Required. Matches manual_review_queue.jsonl.",
            "decision": "Required. Example: same_event, distinct_events, accept_preserved_row, repair_source_row.",
            "reviewer": "Optional reviewer identifier.",
            "reviewed_at": "Optional ISO-8601 timestamp.",
            "notes": "Optional free-text rationale.",
            "replacement_canonical_event_id": "Optional event id override for adjudicated duplicate merges.",
            "exclude_canonical_input_ids": "Optional list of source records to exclude after review.",
        },
        "supported_decisions_by_review_type": {
            "duplicate_candidate": ["same_event", "distinct_events", "needs_more_evidence"],
            "row_shape_anomaly": ["accept_preserved_row", "repair_source_row", "exclude_source_row"],
            "unmapped_headers": ["map_columns", "mark_source_specific", "ignore_if_empty"],
            "import_failure": ["fix_adapter", "fix_source_file", "exclude_source_file"],
        },
        "policy": {
            "default_auto_merge": False,
            "manual_decisions_required_for_fuzzy_merges": True,
            "source_rows_are_preserved_until_explicitly_excluded": True,
            "decision_ingestion_effect": "record_only",
            "canonical_outputs_mutated_by_decisions": False,
        },
    }


def add_unique_source_claim(
    claims: list[dict[str, Any]],
    seen_claim_ids: set[str],
    claim: dict[str, Any],
) -> bool:
    claim_id = claim.get("source_claim_id")
    if not claim_id or claim_id in seen_claim_ids:
        return False
    seen_claim_ids.add(claim_id)
    claims.append(claim)
    return True


def source_claims_from_column_mapping(
    record: Any,
    source_column_mapping: dict[str, Any],
) -> list[dict[str, Any]]:
    source_columns = (
        source_column_mapping.get("sources", {})
        .get(record.source_file, {})
    )
    if not source_columns or not record.raw_source_row:
        return []

    claims = []
    for source_field, column_mapping in source_columns.items():
        if column_mapping.get("mapping_action") != "source_claim":
            continue
        raw_value = clean_text(record.raw_source_row.get(source_field))
        if not raw_value:
            continue
        role = clean_text(column_mapping.get("suspected_semantic_role")) or "source_claim"
        claim_type = claim_type_from_mapping_role(role)
        claim_payload = {
            "claim_type": claim_type,
            "canonical_input_id": record.canonical_input_id,
            "source_dataset": record.source_name,
            "source_file": record.source_file,
            "source_row_number": record.source_row_number,
            "source_native_id": record.source_native_id,
            "source_record_hash": record.source_row_hash,
            "source_field": source_field,
            "raw_value": raw_value,
            "normalized_value": normalize_mapped_claim_value(claim_type, raw_value),
            "origin": "source_column_mapping",
            "confidence": "source_explicit",
            "mapping_role": role,
            "inferred_type": column_mapping.get("inferred_type"),
        }
        claim_payload["source_claim_id"] = stable_hash(claim_payload, prefix="scl_", length=24)
        claims.append(claim_payload)
    return claims


def claim_type_from_mapping_role(role: str) -> str:
    claim_type = role.strip().lower()
    for suffix in ("_claim", "_raw"):
        if claim_type.endswith(suffix):
            claim_type = claim_type[: -len(suffix)]
    return claim_type or "source"


def normalize_mapped_claim_value(claim_type: str, raw_value: str) -> str | None:
    if claim_type == "object_shape":
        return normalize_shape_label(raw_value)
    if claim_type in {"classification", "color_light", "direction", "evidence", "movement", "quality", "sound"}:
        return normalize_type_label(raw_value)
    return None


def main() -> int:
    args = build_argument_parser().parse_args()
    source_column_mapping_path = None if args.no_source_column_mapping else Path(args.source_column_mapping)
    audit_report_path = None if args.no_audit_report else Path(args.audit_report)
    summary = build_canonical_dataset(
        source_dir=Path(args.source_dir),
        output_dir=Path(args.output_dir),
        reports_dir=Path(args.reports_dir),
        limit_per_source=args.limit_per_source,
        source_column_mapping_path=source_column_mapping_path,
        audit_report_path=audit_report_path,
        write_legacy_canonical_input_events=args.write_legacy_canonical_input_events,
        manual_review_decisions_path=Path(args.manual_review_decisions)
        if args.manual_review_decisions
        else None,
        dedupe_strategy=args.dedupe_strategy,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
