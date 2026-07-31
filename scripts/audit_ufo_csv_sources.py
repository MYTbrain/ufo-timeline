"""Audit local UFO CSV sources for schema, preservation, and exact overlap.

This is a Phase 1 source inventory utility. It does not canonicalize or dedupe
records. It produces enough field-level evidence to write adapters without
silently dropping source-specific columns.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_SOURCE_DIR = Path("UFO Databases")
DEFAULT_REPORT_PATH = Path("data/reports/ufo_csv_audit.json")
DEFAULT_INVENTORY_DIR = Path("data/canonical/source_field_inventories")
DEFAULT_COLUMN_MAPPING_PATH = Path("data/canonical/source_column_mapping.json")
DEFAULT_UNMAPPED_JSON_PATH = Path("data/canonical/unmapped_fields_report.json")
DEFAULT_UNMAPPED_CSV_PATH = Path("data/canonical/unmapped_fields_report.csv")
ROW_JOINER = "\x1f"
DEFAULT_UNIQUE_TRACK_LIMIT = 5000
DEFAULT_SAMPLE_LIMIT = 8


CANONICAL_ROLE_PATTERNS: list[tuple[str, str, str]] = [
    (r"^(case|case[_ -]?id|id|no|number|record[_ -]?id)$", "source_native_id", "canonical"),
    (r"(date|sighted|occurred|reported|posted)", "date_or_reported_date", "canonical"),
    (r"(^time$|time[_ -]?of[_ -]?day|hour)", "time_raw", "canonical"),
    (r"(city|town|locality)", "city", "canonical"),
    (r"(state|province|region|county)", "state_province", "canonical"),
    (r"(country|nation)", "country", "canonical"),
    (r"(^lat$|latitude)", "lat", "canonical"),
    (r"(^lon$|^lng$|longitude)", "lon", "canonical"),
    (r"(location|place|address)", "location_raw", "canonical"),
    (r"(shape|craft|object|vehicle|uap[_ -]?type|ufo[_ -]?type)", "object_shape_claim", "source_claim"),
    (r"(duration|elapsed)", "duration_raw", "source_claim"),
    (r"(description|summary|narrative|comments|text|report)", "description", "canonical"),
    (r"(url|link|href|reference|source)", "source_url_or_reference", "canonical"),
    (r"(movement|maneuver|motion|trajectory|path)", "movement_claim", "source_claim"),
    (r"(direction|bearing|heading|travel)", "direction_claim", "source_claim"),
    (r"(speed|velocity)", "speed_claim", "source_claim"),
    (r"(altitude|elevation|height)", "altitude_claim", "source_claim"),
    (r"(witness|observer)", "witness_claim", "source_claim"),
    (r"(radar|photo|video|image|sketch|evidence|media)", "evidence_claim", "source_claim"),
    (r"(credibility|reliability|strangeness|rating|quality)", "quality_claim", "source_claim"),
    (r"(status|classification|class|hynek|ce[1-5])", "classification_claim", "source_claim"),
    (r"(color|colour|light)", "color_light_claim", "source_claim"),
    (r"(sound|noise)", "sound_claim", "source_claim"),
]


@dataclass
class ColumnStats:
    name: str
    index: int
    non_empty_count: int = 0
    empty_count: int = 0
    numeric_count: int = 0
    integer_count: int = 0
    boolean_count: int = 0
    date_like_count: int = 0
    url_like_count: int = 0
    max_length: int = 0
    sample_values: list[str] = field(default_factory=list)
    unique_values: set[str] = field(default_factory=set, repr=False)
    unique_count_at_least: int = 0
    unique_count_exact: bool = True

    def observe(self, value: str, *, unique_limit: int, sample_limit: int) -> None:
        text = value.strip()
        if not text:
            self.empty_count += 1
            return

        self.non_empty_count += 1
        self.max_length = max(self.max_length, len(text))
        if len(self.sample_values) < sample_limit and text not in self.sample_values:
            self.sample_values.append(text[:240])

        if self.unique_count_exact:
            self.unique_values.add(text)
            if len(self.unique_values) > unique_limit:
                self.unique_count_at_least = len(self.unique_values)
                self.unique_values.clear()
                self.unique_count_exact = False

        if is_number(text):
            self.numeric_count += 1
            if is_integer(text):
                self.integer_count += 1
        if is_boolean(text):
            self.boolean_count += 1
        if is_date_like(text):
            self.date_like_count += 1
        if is_url_like(text):
            self.url_like_count += 1

    def to_inventory(self, total_rows: int) -> dict[str, Any]:
        inferred_type = infer_type(self, total_rows)
        semantic_role, action = classify_column(self.name, inferred_type)
        unique_count = len(self.unique_values) if self.unique_count_exact else None
        unique_at_least = unique_count if self.unique_count_exact else self.unique_count_at_least
        return {
            "name": self.name,
            "index": self.index,
            "non_empty_count": self.non_empty_count,
            "empty_count": self.empty_count,
            "non_empty_ratio": round(self.non_empty_count / total_rows, 6) if total_rows else 0,
            "inferred_type": inferred_type,
            "unique_count": unique_count,
            "unique_count_exact": self.unique_count_exact,
            "unique_count_at_least": unique_at_least,
            "max_length": self.max_length,
            "sample_values": self.sample_values,
            "suspected_semantic_role": semantic_role,
            "mapping_action": action,
        }


@dataclass
class FileAudit:
    file: str
    rows: int
    cols: int
    header: list[str]
    header_sample: list[str]
    schema_signature: str
    rows_with_extra_columns: int = 0
    rows_with_missing_columns: int = 0
    max_extra_columns: int = 0
    sample_extra_values: list[list[str]] = field(default_factory=list)
    inventory_path: str | None = None


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", default=str(DEFAULT_SOURCE_DIR), help="Directory containing CSV source files.")
    parser.add_argument("--output", default=str(DEFAULT_REPORT_PATH), help="Aggregate JSON audit report path.")
    parser.add_argument("--inventory-dir", default=str(DEFAULT_INVENTORY_DIR), help="Per-source inventory output directory.")
    parser.add_argument("--column-mapping", default=str(DEFAULT_COLUMN_MAPPING_PATH), help="Column mapping JSON output path.")
    parser.add_argument("--unmapped-json", default=str(DEFAULT_UNMAPPED_JSON_PATH), help="Unmapped fields JSON report path.")
    parser.add_argument("--unmapped-csv", default=str(DEFAULT_UNMAPPED_CSV_PATH), help="Unmapped fields CSV report path.")
    parser.add_argument("--limit-header-sample", type=int, default=12, help="Header columns to include in aggregate sample.")
    parser.add_argument("--sample-limit", type=int, default=DEFAULT_SAMPLE_LIMIT, help="Sample non-empty values per column.")
    parser.add_argument(
        "--unique-track-limit",
        type=int,
        default=DEFAULT_UNIQUE_TRACK_LIMIT,
        help="Maximum exact unique values to track per column before reporting a lower bound.",
    )
    return parser


def is_number(value: str) -> bool:
    try:
        return math.isfinite(float(value.replace(",", "")))
    except ValueError:
        return False


def is_integer(value: str) -> bool:
    try:
        text = value.replace(",", "")
        number = float(text)
        return math.isfinite(number) and (str(int(number)) == text or re.fullmatch(r"[-+]?\d+", text) is not None)
    except (OverflowError, ValueError):
        return False


def is_boolean(value: str) -> bool:
    return value.strip().lower() in {"true", "false", "yes", "no", "y", "n", "0", "1"}


def is_date_like(value: str) -> bool:
    text = value.strip()
    return bool(
        re.search(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", text)
        or re.search(r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b", text)
        or re.search(r"\b\d{1,2}[/-]\d{4}\b", text)
    )


def is_url_like(value: str) -> bool:
    return value.strip().lower().startswith(("http://", "https://", "www."))


def infer_type(stats: ColumnStats, total_rows: int) -> str:
    non_empty = stats.non_empty_count
    if non_empty == 0:
        return "empty"
    threshold = max(1, int(non_empty * 0.8))
    if stats.boolean_count >= threshold:
        return "boolean"
    if stats.integer_count >= threshold:
        return "integer"
    if stats.numeric_count >= threshold:
        return "number"
    if stats.date_like_count >= threshold:
        return "date_like"
    if stats.url_like_count >= threshold:
        return "url_like"
    if stats.max_length > 500:
        return "long_text"
    return "text"


def classify_column(name: str, inferred_type: str) -> tuple[str, str]:
    normalized = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    for pattern, role, action in CANONICAL_ROLE_PATTERNS:
        if re.search(pattern, normalized):
            return role, action
    if inferred_type == "empty":
        return "empty", "ignore_empty"
    return "source_specific", "source_specific"


def row_digest(row: list[str]) -> str:
    return hashlib.sha1(ROW_JOINER.join(row).encode("utf-8", "replace")).hexdigest()


def schema_signature(header: list[str]) -> str:
    return hashlib.sha1(ROW_JOINER.join(header).encode("utf-8", "replace")).hexdigest()


def safe_inventory_name(file_name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", file_name).removesuffix(".csv") + ".json"


def audit_csv_file(
    path: Path,
    *,
    inventory_dir: Path,
    limit_header_sample: int,
    unique_track_limit: int,
    sample_limit: int,
) -> tuple[FileAudit, set[str], dict[str, Any]]:
    digests: set[str] = set()
    row_count = 0
    header: list[str] = []
    rows_with_extra_columns = 0
    rows_with_missing_columns = 0
    max_extra_columns = 0
    sample_extra_values: list[list[str]] = []

    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, [])
        stats = [ColumnStats(name=name or f"__unnamed_{index + 1}", index=index) for index, name in enumerate(header)]
        extra_stats: list[ColumnStats] = []

        for row in reader:
            row_count += 1
            digests.add(row_digest(row))
            if len(row) > len(header):
                rows_with_extra_columns += 1
                extra_values = row[len(header) :]
                max_extra_columns = max(max_extra_columns, len(extra_values))
                if len(sample_extra_values) < sample_limit:
                    sample_extra_values.append(extra_values[:8])
                while len(extra_stats) < len(extra_values):
                    extra_stats.append(ColumnStats(name=f"__extra_{len(extra_stats) + 1}", index=len(header) + len(extra_stats)))
                for index, value in enumerate(extra_values):
                    extra_stats[index].observe(value, unique_limit=unique_track_limit, sample_limit=sample_limit)
            elif len(row) < len(header):
                rows_with_missing_columns += 1

            for index, column_stats in enumerate(stats):
                value = row[index] if index < len(row) else ""
                column_stats.observe(value, unique_limit=unique_track_limit, sample_limit=sample_limit)

    columns = [column.to_inventory(row_count) for column in stats + extra_stats]
    source_inventory = {
        "source_file": path.name,
        "source_path": str(path.resolve()),
        "row_count": row_count,
        "column_count": len(header),
        "observed_column_count_including_extra": len(columns),
        "schema_signature": schema_signature(header),
        "columns": columns,
        "row_shape_anomalies": {
            "rows_with_extra_columns": rows_with_extra_columns,
            "rows_with_missing_columns": rows_with_missing_columns,
            "max_extra_columns": max_extra_columns,
            "sample_extra_values": sample_extra_values,
        },
    }

    inventory_dir.mkdir(parents=True, exist_ok=True)
    inventory_path = inventory_dir / safe_inventory_name(path.name)
    inventory_path.write_text(json.dumps(source_inventory, ensure_ascii=False, indent=2), encoding="utf-8")

    audit = FileAudit(
        file=path.name,
        rows=row_count,
        cols=len(header),
        header=header,
        header_sample=header[: max(0, limit_header_sample)],
        schema_signature=schema_signature(header),
        rows_with_extra_columns=rows_with_extra_columns,
        rows_with_missing_columns=rows_with_missing_columns,
        max_extra_columns=max_extra_columns,
        sample_extra_values=sample_extra_values,
        inventory_path=str(inventory_path),
    )
    return audit, digests, source_inventory


def compare_exact_overlap(left_name: str, left_digests: set[str], right_name: str, right_digests: set[str]) -> dict[str, Any]:
    overlap = len(left_digests & right_digests)
    left_only = len(left_digests - right_digests)
    right_only = len(right_digests - left_digests)
    relationship = "partial_overlap"
    keep = None
    drop = None
    if left_only == 0 and right_only == 0:
        relationship = "exact_match"
        keep = max((left_name, len(left_digests)), (right_name, len(right_digests)), key=lambda item: item[1])[0]
        drop = right_name if keep == left_name else left_name
    elif left_only == 0:
        relationship = "left_subset_of_right"
        keep = right_name
        drop = left_name
    elif right_only == 0:
        relationship = "right_subset_of_left"
        keep = left_name
        drop = right_name
    return {
        "left": left_name,
        "right": right_name,
        "exact_overlap": overlap,
        "left_only": left_only,
        "right_only": right_only,
        "relationship": relationship,
        "recommended_keep": keep,
        "recommended_drop": drop,
    }


def write_column_mapping_and_unmapped(
    inventories: list[dict[str, Any]],
    *,
    column_mapping_path: Path,
    unmapped_json_path: Path,
    unmapped_csv_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    mapping: dict[str, Any] = {"sources": {}}
    unmapped_rows: list[dict[str, Any]] = []

    for inventory in inventories:
        source_file = inventory["source_file"]
        source_map: dict[str, Any] = {}
        for column in inventory["columns"]:
            entry = {
                "suspected_semantic_role": column["suspected_semantic_role"],
                "mapping_action": column["mapping_action"],
                "inferred_type": column["inferred_type"],
                "non_empty_count": column["non_empty_count"],
                "unique_count": column["unique_count"],
                "unique_count_exact": column["unique_count_exact"],
                "sample_values": column["sample_values"],
            }
            source_map[column["name"]] = entry
            if column["non_empty_count"] and column["mapping_action"] == "source_specific":
                unmapped_rows.append(
                    {
                        "source_file": source_file,
                        "column": column["name"],
                        "non_empty_count": column["non_empty_count"],
                        "inferred_type": column["inferred_type"],
                        "sample_values": column["sample_values"],
                        "required_action": "preserve_source_specific_or_map_before_adapter_release",
                    }
                )
        mapping["sources"][source_file] = source_map

    unmapped_report = {
        "unmapped_non_empty_column_count": len(unmapped_rows),
        "rows": unmapped_rows,
    }

    column_mapping_path.parent.mkdir(parents=True, exist_ok=True)
    unmapped_json_path.parent.mkdir(parents=True, exist_ok=True)
    unmapped_csv_path.parent.mkdir(parents=True, exist_ok=True)
    column_mapping_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    unmapped_json_path.write_text(json.dumps(unmapped_report, ensure_ascii=False, indent=2), encoding="utf-8")

    with unmapped_csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["source_file", "column", "non_empty_count", "inferred_type", "sample_values", "required_action"],
        )
        writer.writeheader()
        for row in unmapped_rows:
            writer.writerow({**row, "sample_values": json.dumps(row["sample_values"], ensure_ascii=False)})

    return mapping, unmapped_report


def build_report(
    source_dir: Path,
    *,
    inventory_dir: Path,
    column_mapping_path: Path,
    unmapped_json_path: Path,
    unmapped_csv_path: Path,
    limit_header_sample: int,
    unique_track_limit: int,
    sample_limit: int,
) -> dict[str, Any]:
    csv_paths = sorted(source_dir.glob("*.csv"))
    audits: list[FileAudit] = []
    inventories: list[dict[str, Any]] = []
    digest_sets: dict[str, set[str]] = {}
    schema_groups: dict[str, list[str]] = {}

    for path in csv_paths:
        audit, digests, inventory = audit_csv_file(
            path,
            inventory_dir=inventory_dir,
            limit_header_sample=limit_header_sample,
            unique_track_limit=unique_track_limit,
            sample_limit=sample_limit,
        )
        audits.append(audit)
        inventories.append(inventory)
        digest_sets[audit.file] = digests
        schema_groups.setdefault(audit.schema_signature, []).append(audit.file)

    exact_overlap_pairs: list[dict[str, Any]] = []
    recommended_drop: set[str] = set()
    for group_files in schema_groups.values():
        if len(group_files) < 2:
            continue
        for index, left_name in enumerate(group_files):
            for right_name in group_files[index + 1 :]:
                comparison = compare_exact_overlap(left_name, digest_sets[left_name], right_name, digest_sets[right_name])
                exact_overlap_pairs.append(comparison)
                if comparison["recommended_drop"]:
                    recommended_drop.add(str(comparison["recommended_drop"]))

    kept_files = [audit.file for audit in audits if audit.file not in recommended_drop]
    kept_rows = sum(audit.rows for audit in audits if audit.file in kept_files)
    _mapping, unmapped_report = write_column_mapping_and_unmapped(
        inventories,
        column_mapping_path=column_mapping_path,
        unmapped_json_path=unmapped_json_path,
        unmapped_csv_path=unmapped_csv_path,
    )

    return {
        "source_dir": str(source_dir.resolve()),
        "file_count": len(audits),
        "raw_row_total": sum(audit.rows for audit in audits),
        "files": [asdict(audit) for audit in audits],
        "schema_groups": [
            {"schema_signature": signature, "files": sorted(files)}
            for signature, files in sorted(schema_groups.items(), key=lambda item: (len(item[1]), item[0]), reverse=True)
        ],
        "exact_overlap_pairs": exact_overlap_pairs,
        "recommended_keep_files_after_exact_subset_pruning": kept_files,
        "recommended_drop_files_after_exact_subset_pruning": sorted(recommended_drop),
        "estimated_rows_after_exact_subset_pruning": kept_rows,
        "inventory_dir": str(inventory_dir),
        "column_mapping_path": str(column_mapping_path),
        "unmapped_json_path": str(unmapped_json_path),
        "unmapped_csv_path": str(unmapped_csv_path),
        "unmapped_non_empty_column_count": unmapped_report["unmapped_non_empty_column_count"],
        "notes": [
            "Exact overlap only compares files with identical header schemas.",
            "High-cardinality unique counts are reported as lower bounds after the tracking cap.",
            "Columns classified as source_specific must still be preserved by adapters.",
        ],
    }


def main() -> int:
    args = build_argument_parser().parse_args()
    source_dir = Path(args.source_dir).resolve()
    output_path = Path(args.output).resolve() if args.output else None
    inventory_dir = Path(args.inventory_dir).resolve()

    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")

    report = build_report(
        source_dir,
        inventory_dir=inventory_dir,
        column_mapping_path=Path(args.column_mapping).resolve(),
        unmapped_json_path=Path(args.unmapped_json).resolve(),
        unmapped_csv_path=Path(args.unmapped_csv).resolve(),
        limit_header_sample=max(0, args.limit_header_sample),
        unique_track_limit=max(100, args.unique_track_limit),
        sample_limit=max(1, args.sample_limit),
    )

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
