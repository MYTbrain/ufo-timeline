"""Build the immutable, event-aligned Analysis time-of-day v1 sidecar."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from scripts.analysis_time_of_day import STATUS_CODES, TIME_BINS, normalize_time_of_day
    from scripts.build_analysis_duration_v1 import (
        codebook,
        compact_json_bytes,
        era_for,
        load_macroregions,
        sha256_bytes,
        sha256_file,
        write_raw_and_gzip,
    )
except ModuleNotFoundError:  # Direct ``python scripts/...`` execution.
    from analysis_time_of_day import STATUS_CODES, TIME_BINS, normalize_time_of_day  # type: ignore
    from build_analysis_duration_v1 import (  # type: ignore
        codebook,
        compact_json_bytes,
        era_for,
        load_macroregions,
        sha256_bytes,
        sha256_file,
        write_raw_and_gzip,
    )


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DETAIL_ROOT = REPO_ROOT / "static_bundle" / "data" / "canonical_web" / "event_chunks"
DEFAULT_GEOGRAPHY = REPO_ROOT / "webapp" / "static_public" / "data" / "analysis_v2" / "ufo_geography_v1.json"
DEFAULT_ANALYSIS_MANIFEST = REPO_ROOT / "webapp" / "static_public" / "data" / "analysis_v2" / "manifest.json"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "webapp" / "static_public" / "data" / "analysis_time_of_day_v1"
DEFAULT_AUDIT_PATH = (
    REPO_ROOT / "campaign" / "analysis_improvement" / "waves" /
    "wave-004-time-of-day-assessment" / "build_audit.json"
)
RELEASE_ID = "analysis-time-of-day-v1-20260804"
SCHEMA_ID = "ufo-timeline-analysis-time-of-day-artifacts-v1.0.0"
ASSET_ORIGIN = "https://pub-e9029ab2f6b448daad03d7cde7e15e64.r2.dev"
ASSET_BASE_URL = f"{ASSET_ORIGIN}/releases/{RELEASE_ID}"
EXPECTED_CATALOG_ROWS = 702_893
MINIMUM_TYPED_ROWS = 102_410
MINIMUM_TYPED_CATALOG_PCT = 14.56
MINIMUM_SUPPORTED_SOURCES = 3
MINIMUM_ROWS_PER_SOURCE = 1_000
MAXIMUM_COMPRESSED_ARTIFACT_BYTES = 5_000_000
PROJECTION_SHARD_ROWS = 200_000


TYPED_STATUSES = {"exact_clock", "approximate_clock", "clock_range", "qualitative_period"}


def typed_record(normalization: Any) -> bool:
    return normalization.status in TYPED_STATUSES


def stable_time_share_diagnostics(
    rows: list[tuple[str, str, str, str]], dimension_index: int
) -> dict[str, Any]:
    total = Counter(row[3] for row in rows)
    total_n = len(rows)
    groups = sorted({row[dimension_index] for row in rows if row[dimension_index] != "unknown"})
    holdouts = []
    for group in groups:
        retained = [row for row in rows if row[dimension_index] != group]
        retained_counts = Counter(row[3] for row in retained)
        maximum_shift = max(
            (
                abs(
                    (retained_counts[bin_id] / len(retained) if retained else 0) -
                    (total[bin_id] / total_n if total_n else 0)
                )
                for bin_id in TIME_BINS[1:]
            ),
            default=0,
        )
        holdouts.append({
            "heldOut": group,
            "retainedRows": len(retained),
            "maximumAbsoluteShareShift": round(maximum_shift, 8),
        })
    return {"groups": groups, "holdouts": holdouts, "interpretation": "descriptive_sensitivity_not_release_gate"}


def artifact_entry(stem: str, files: dict[str, Any], row_count: int, row_schema: list[str]) -> dict[str, Any]:
    return {
        "artifactId": stem,
        "releaseId": f"{RELEASE_ID}.{stem}",
        "file": f"{ASSET_BASE_URL}/{stem}.json",
        "gzipFile": f"{ASSET_BASE_URL}/{stem}.json.gz",
        "bytes": files["rawBytes"],
        "gzipBytes": files["gzipBytes"],
        "sha256": files["rawSha256"],
        "gzipSha256": files["gzipSha256"],
        "rowCount": row_count,
        "rowSchema": row_schema,
    }


def build(args: argparse.Namespace) -> dict[str, Any]:
    detail_root = Path(args.detail_root).resolve()
    geography_path = Path(args.geography).resolve()
    analysis_manifest_path = Path(args.analysis_manifest).resolve()
    output_root = Path(args.output_root).resolve()
    audit_path = Path(args.audit_path).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)

    macroregion_by_event, geography_input = load_macroregions(geography_path, analysis_manifest_path)
    chunk_paths = sorted(detail_root.glob("chunk_*.json"))
    if not chunk_paths:
        raise ValueError(f"No canonical detail chunks found under {detail_root}")

    projections_raw: list[tuple[int, int | str, tuple[str, str], str]] = []
    normalization_by_value: dict[tuple[str, str], Any] = {}
    raw_counts: Counter[tuple[str, str]] = Counter()
    source_raw_counts: Counter[str] = Counter()
    source_status_counts: dict[str, Counter[str]] = defaultdict(Counter)
    source_bin_counts: dict[str, Counter[str]] = defaultdict(Counter)
    reason_counts: Counter[str] = Counter()
    timezone_semantics_counts: Counter[str] = Counter()
    qualitative_counts: Counter[str] = Counter()
    diagnostics_rows: list[tuple[str, str, str, str]] = []
    catalog_row_index = 0

    for chunk_path in chunk_paths:
        rows = json.loads(chunk_path.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise ValueError(f"Canonical detail chunk is not an array: {chunk_path}")
        for event in rows:
            source = str(event.get("source") or "unknown").strip().lower() or "unknown"
            raw_value = str(event.get("time_raw") or "").strip()
            if raw_value:
                event_id_value = event.get("event_id")
                event_id = event_id_value if isinstance(event_id_value, int) else str(event_id_value or "")
                if event_id == "":
                    raise ValueError(f"Time-bearing catalog row {catalog_row_index} has no event ID")
                value_key = (source, raw_value)
                raw_counts[value_key] += 1
                if value_key not in normalization_by_value:
                    normalization_by_value[value_key] = normalize_time_of_day(source, raw_value)
                normalized = normalization_by_value[value_key]
                macroregion = macroregion_by_event.get(str(event_id), "unknown")
                projections_raw.append((catalog_row_index, event_id, value_key, macroregion))
                source_raw_counts[source] += 1
                source_status_counts[source][normalized.status] += 1
                source_bin_counts[source][normalized.descriptive_bin] += 1
                reason_counts[normalized.reason] += 1
                timezone_semantics_counts[normalized.timezone_semantics] += 1
                if normalized.qualitative_period:
                    qualitative_counts[normalized.qualitative_period] += 1
                if normalized.inferential_bin != "unknown":
                    diagnostics_rows.append((
                        source,
                        era_for(event.get("sort_date_iso") or event.get("date_iso")),
                        macroregion,
                        normalized.inferential_bin,
                    ))
            catalog_row_index += 1

    if catalog_row_index != EXPECTED_CATALOG_ROWS:
        raise ValueError(f"Served catalog row count changed: {catalog_row_index}/{EXPECTED_CATALOG_ROWS}")

    ordered_value_keys = sorted(
        normalization_by_value,
        key=lambda key: (key[0], hashlib.sha256(key[1].encode("utf-8")).hexdigest(), key[1]),
    )
    value_codes = {key: index for index, key in enumerate(ordered_value_keys)}
    sources, source_code = codebook((key[0] for key in ordered_value_keys), first="unknown")
    reasons, reason_code = codebook((item.reason for item in normalization_by_value.values()))
    precisions, precision_code = codebook((item.precision for item in normalization_by_value.values()), first="unknown")
    qualitative_periods, qualitative_code = codebook(
        (item.qualitative_period for item in normalization_by_value.values()), first=""
    )
    timezone_labels, timezone_label_code = codebook(
        (item.timezone_label for item in normalization_by_value.values()), first=""
    )
    timezone_semantics, timezone_semantics_code = codebook(
        (item.timezone_semantics for item in normalization_by_value.values()), first="unknown"
    )
    macroregions, macroregion_code = codebook((row[3] for row in projections_raw), first="unknown")
    status_code = {value: index for index, value in enumerate(STATUS_CODES)}
    bin_code = {value: index for index, value in enumerate(TIME_BINS)}

    value_dictionary = []
    for source, raw_value in ordered_value_keys:
        normalized = normalization_by_value[(source, raw_value)]
        value_dictionary.append([
            source_code[source],
            hashlib.sha256(raw_value.encode("utf-8")).hexdigest(),
            raw_value,
            status_code[normalized.status],
            reason_code[normalized.reason],
            normalized.lower_minute,
            normalized.upper_minute,
            bin_code[normalized.descriptive_bin],
            bin_code[normalized.inferential_bin],
            precision_code[normalized.precision],
            qualitative_code[normalized.qualitative_period],
            timezone_label_code[normalized.timezone_label],
            timezone_semantics_code[normalized.timezone_semantics],
            raw_counts[(source, raw_value)],
        ])

    projection = [
        [row_index, event_id, value_codes[value_key], macroregion_code[macroregion]]
        for row_index, event_id, value_key, macroregion in projections_raw
    ]
    if sum(row[-1] for row in value_dictionary) != len(projection):
        raise ValueError("Time-of-day dictionary occurrence counts do not match the event projection")

    typed_rows = sum(count for key, count in raw_counts.items() if typed_record(normalization_by_value[key]))
    exact_rows = sum(
        count for key, count in raw_counts.items()
        if normalization_by_value[key].status == "exact_clock" and normalization_by_value[key].inferential_bin != "unknown"
    )
    descriptive_binned_rows = sum(
        count for key, count in raw_counts.items() if normalization_by_value[key].descriptive_bin != "unknown"
    )
    typed_by_source = {
        source: sum(
            count for key, count in raw_counts.items()
            if key[0] == source and typed_record(normalization_by_value[key])
        )
        for source in sorted(source_raw_counts)
    }
    supported_sources = sorted(
        source for source, count in typed_by_source.items() if count >= MINIMUM_ROWS_PER_SOURCE
    )

    artifacts: dict[str, Any] = {}
    payloads: dict[str, Any] = {}
    compressed_sizes: dict[str, int] = {}
    dictionary_files = write_raw_and_gzip(output_root, "time_of_day_value_dictionary_v1", value_dictionary)
    artifacts["timeOfDayValueDictionary"] = artifact_entry(
        "time_of_day_value_dictionary_v1",
        dictionary_files,
        len(value_dictionary),
        [
            "sourceCode", "rawValueSha256", "rawValue", "statusCode", "reasonCode",
            "lowerMinute", "upperMinute", "descriptiveBinCode", "inferentialBinCode",
            "precisionCode", "qualitativePeriodCode", "timezoneLabelCode",
            "timezoneSemanticsCode", "occurrenceCount",
        ],
    )
    compressed_sizes["timeOfDayValueDictionary"] = dictionary_files["gzipBytes"]
    payloads["timeOfDayValueDictionaryRaw"] = {
        "path": "time_of_day_value_dictionary_v1.json", "bytes": dictionary_files["rawBytes"],
        "sha256": dictionary_files["rawSha256"], "recordCount": len(value_dictionary), "r2Only": True,
    }
    payloads["timeOfDayValueDictionaryGzip"] = {
        "path": "time_of_day_value_dictionary_v1.json.gz", "bytes": dictionary_files["gzipBytes"],
        "sha256": dictionary_files["gzipSha256"], "decodedBytes": dictionary_files["rawBytes"],
        "recordCount": len(value_dictionary), "r2Only": True,
    }

    projection_keys = []
    for shard_index, start in enumerate(range(0, len(projection), PROJECTION_SHARD_ROWS)):
        shard = projection[start:start + PROJECTION_SHARD_ROWS]
        stem = f"time_of_day_projection_v1_{shard_index:03d}"
        key = f"timeOfDayProjectionShard{shard_index:03d}"
        files = write_raw_and_gzip(output_root, stem, shard)
        artifacts[key] = artifact_entry(
            stem, files, len(shard), ["catalogRowIndex", "eventId", "valueCode", "macroregionCode"]
        )
        compressed_sizes[key] = files["gzipBytes"]
        projection_keys.append(key)
        payloads[f"{key}Raw"] = {
            "path": f"{stem}.json", "bytes": files["rawBytes"], "sha256": files["rawSha256"],
            "recordCount": len(shard), "r2Only": True,
        }
        payloads[f"{key}Gzip"] = {
            "path": f"{stem}.json.gz", "bytes": files["gzipBytes"], "sha256": files["gzipSha256"],
            "decodedBytes": files["rawBytes"], "recordCount": len(shard), "r2Only": True,
        }

    oversized = {key: value for key, value in compressed_sizes.items() if value > MAXIMUM_COMPRESSED_ARTIFACT_BYTES}
    if oversized:
        raise ValueError(f"Compressed time-of-day artifact budget exceeded: {oversized}")

    typed_catalog_pct = 100 * typed_rows / catalog_row_index
    sentinel_rows = sum(
        count for key, count in raw_counts.items() if normalization_by_value[key].status == "sentinel_ambiguous"
    )
    material_gates = {
        "minimumTypedRows": typed_rows >= MINIMUM_TYPED_ROWS,
        "minimumTypedCatalogPct": typed_catalog_pct >= MINIMUM_TYPED_CATALOG_PCT,
        "minimumSupportedSources": len(supported_sources) >= MINIMUM_SUPPORTED_SOURCES,
        "minimumRowsPerSupportedSource": all(typed_by_source[source] >= MINIMUM_ROWS_PER_SOURCE for source in supported_sources),
        "originalClockTextPreserved": all(bool(row[2]) for row in value_dictionary),
        "projectionParity": len(projection) == sum(source_raw_counts.values()),
        "dictionaryOccurrenceParity": sum(row[-1] for row in value_dictionary) == len(projection),
        "midnightAndNoonFailClosed": sentinel_rows > 0,
        "timezoneSemanticsSeparated": "unknown" in timezone_semantics,
        "compressedArtifactBudget": not oversized,
    }
    readiness_status = "ready_descriptive" if all(material_gates.values()) else "not_estimable"

    inventory_paths = {
        "majestic": REPO_ROOT / "data/canonical/source_field_inventories/majestic.json",
        "mufon": REPO_ROOT / "data/canonical/source_field_inventories/mufon.json",
        "nuforc": REPO_ROOT / "data/canonical/source_field_inventories/nuforc.json",
        "phenomenainon_updb": REPO_ROOT / "data/canonical/source_field_inventories/phenomenAInon_UPDB.json",
        "ufocat": REPO_ROOT / "data/canonical/source_field_inventories/ufocat2023.json",
    }
    manifest = {
        "schemaId": SCHEMA_ID,
        "schemaVersion": 1,
        "manifestVersion": "1.0.0",
        "releaseId": RELEASE_ID,
        "generatedAt": "2026-08-04T00:00:00Z",
        "assetBaseUrl": ASSET_BASE_URL,
        "delivery": {
            "pagesFiles": ["manifest.json"],
            "r2OnlyPaths": [item["path"] for item in payloads.values()],
            "immutablePrefix": f"releases/{RELEASE_ID}",
            "cacheControl": "public, max-age=31536000, immutable",
        },
        "artifacts": artifacts,
        "artifactGroups": {"timeProjectionShards": projection_keys},
        "payloads": payloads,
        "codes": {
            "source": sources,
            "status": list(STATUS_CODES),
            "reason": reasons,
            "timeBin": list(TIME_BINS),
            "precision": precisions,
            "qualitativePeriod": qualitative_periods,
            "timezoneLabel": timezone_labels,
            "timezoneSemantics": timezone_semantics,
            "macroregion": macroregions,
        },
        "rowOrdering": {
            "policyId": "served_catalog_sparse_time_of_day_subsequence_v1",
            "keyFields": ["catalogRowIndex", "eventId"],
            "sha256": sha256_bytes(compact_json_bytes([[row[0], row[1]] for row in projection])),
        },
        "inputs": {
            "canonicalManifest": {
                "path": "static_bundle/data/canonical_web/canonical_web_manifest.json",
                "sha256": sha256_file(detail_root.parent / "canonical_web_manifest.json"),
            },
            "geography": geography_input,
            "sourceFieldInventories": {
                source: {
                    "path": path.relative_to(REPO_ROOT).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
                for source, path in inventory_paths.items()
            },
        },
        "policy": {
            "canonicalEventsMutated": False,
            "narrativeDescriptionsRead": False,
            "missingTimeIsMidnight": False,
            "midnightOrNoonSentinelsExact": False,
            "timezoneInferredFromLocation": False,
            "utcConversionApplied": False,
            "solarOrTwilightStateInferred": False,
            "qualitativePeriodsAssignedMinutes": False,
            "approximateOrRangeValuesInferentiallyEligible": False,
            "patternFinderPromotion": False,
            "runtimeCovariates": ["source", "era", "macroregion"],
            "minimumCommonSupport": 0.8,
            "minimumActiveAndReferenceBinN": 20,
        },
        "counts": {
            "catalogRows": catalog_row_index,
            "rawTimeRows": len(projection),
            "uniqueSourceRawValues": len(value_dictionary),
            "typedRows": typed_rows,
            "typedCatalogPct": round(typed_catalog_pct, 6),
            "exactInferentialRows": exact_rows,
            "descriptiveBinnedRows": descriptive_binned_rows,
            "sentinelAmbiguousRows": sentinel_rows,
            "bySourceRaw": dict(sorted(source_raw_counts.items())),
            "bySourceTyped": typed_by_source,
            "supportedSources": supported_sources,
            "bySourceStatus": {source: dict(sorted(counts.items())) for source, counts in sorted(source_status_counts.items())},
            "bySourceDescriptiveBin": {source: dict(sorted(counts.items())) for source, counts in sorted(source_bin_counts.items())},
            "byTimezoneSemantics": dict(sorted(timezone_semantics_counts.items())),
            "byQualitativePeriod": dict(sorted(qualitative_counts.items())),
        },
        "readiness": {
            "status": readiness_status,
            "assessmentLane": "descriptive_with_exact_clock_runtime_gated_comparisons",
            "materialCriterion": "previously_unavailable_assessment_becomes_estimable",
            "materialGates": material_gates,
            "supportedSources": supported_sources,
            "suppressionPolicy": "Suppress comparisons when integrity, exact-clock support, common support, or holdout stability fails; display sentinel, invalid, qualitative, and timezone-unknown lanes without assigning clock minutes.",
            "warnings": [
                "Clock values retain source-local meaning; no location-based timezone or UTC conversion is applied.",
                "Exact-looking midnight and noon source defaults remain sentinel-ambiguous.",
                "Qualitative periods are descriptive labels and are never assigned clock minutes.",
                "Report time is not event incidence, authenticity, risk, solar state, or inferred travel time.",
            ],
        },
        "negativeControls": {
            "leaveOneSourceOut": stable_time_share_diagnostics(diagnostics_rows, 0),
            "eraHoldout": stable_time_share_diagnostics(diagnostics_rows, 1),
            "macroregionHoldout": stable_time_share_diagnostics(diagnostics_rows, 2),
            "approximateAndRangeHoldout": {
                "excludedRows": sum(
                    count for key, count in raw_counts.items()
                    if normalization_by_value[key].status in {"approximate_clock", "clock_range"}
                ),
                "interpretation": "excluded_from_inferential_clock_bin_comparisons",
            },
            "midnightAndNoonSentinelAudit": {
                "excludedRows": sentinel_rows,
                "interpretation": "never_coerced_to_exact_midnight_or_noon",
            },
            "unknownTimezoneHoldout": {
                "rows": timezone_semantics_counts["unknown"],
                "interpretation": "clock_bins_are_not_solar_or_utc_bins",
            },
        },
    }
    manifest_path = output_root / "manifest.json"
    manifest_path.write_bytes(compact_json_bytes(manifest))

    audit = {
        "schemaId": "ufo-timeline-analysis-time-of-day-build-audit-v1.0.0",
        "releaseId": RELEASE_ID,
        "status": readiness_status,
        "manifest": {
            "path": manifest_path.relative_to(REPO_ROOT).as_posix(),
            "bytes": manifest_path.stat().st_size,
            "sha256": sha256_file(manifest_path),
        },
        "counts": manifest["counts"],
        "materialGates": material_gates,
        "compressedArtifacts": {
            key: value for key, value in sorted(compressed_sizes.items())
        } | {"maximumBytesEach": MAXIMUM_COMPRESSED_ARTIFACT_BYTES},
        "topNormalizationReasons": [
            {"reason": reason, "rows": count} for reason, count in reason_counts.most_common(20)
        ],
        "artifactHashes": {
            key: {"sha256": value["sha256"], "gzipSha256": value["gzipSha256"]}
            for key, value in artifacts.items()
        },
    }
    audit_path.write_bytes(compact_json_bytes(audit))
    return {
        "ok": readiness_status == "ready_descriptive",
        "status": readiness_status,
        "manifest": str(manifest_path),
        "audit": str(audit_path),
        "counts": manifest["counts"],
        "compressedArtifacts": audit["compressedArtifacts"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--detail-root", default=str(DEFAULT_DETAIL_ROOT))
    parser.add_argument("--geography", default=str(DEFAULT_GEOGRAPHY))
    parser.add_argument("--analysis-manifest", default=str(DEFAULT_ANALYSIS_MANIFEST))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--audit-path", default=str(DEFAULT_AUDIT_PATH))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(build(parse_args()), indent=2, sort_keys=True))
