"""Build the immutable, event-aligned Analysis witness-count v1 sidecar."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from scripts.analysis_witness_count import STATUS_CODES, WITNESS_COUNT_BINS, normalize_witness_count
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
    from analysis_witness_count import STATUS_CODES, WITNESS_COUNT_BINS, normalize_witness_count  # type: ignore
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
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "webapp" / "static_public" / "data" / "analysis_witness_count_v1"
DEFAULT_AUDIT_PATH = (
    REPO_ROOT / "campaign" / "analysis_improvement" / "waves" /
    "wave-005-witness-count-assessment" / "build_audit.json"
)
RELEASE_ID = "analysis-witness-count-v1-20260804"
SCHEMA_ID = "ufo-timeline-analysis-witness-count-artifacts-v1.0.0"
ASSET_ORIGIN = "https://pub-e9029ab2f6b448daad03d7cde7e15e64.r2.dev"
ASSET_BASE_URL = f"{ASSET_ORIGIN}/releases/{RELEASE_ID}"
EXPECTED_CATALOG_ROWS = 702_893
EXPECTED_RAW_ROWS = 145_289
MINIMUM_TYPED_ROWS = 116_231
MINIMUM_TYPED_CATALOG_PCT = 16.53
MINIMUM_SUPPORTED_SOURCES = 1
MINIMUM_ROWS_PER_SOURCE = 1_000
MAXIMUM_COMPRESSED_ARTIFACT_BYTES = 5_000_000
PROJECTION_SHARD_ROWS = 200_000
RAW_FIELD_NAME = "No of observers"
TYPED_STATUSES = {"exact_count", "approximate_count", "bounded_range", "lower_bound", "qualitative_plural"}


def typed_record(normalization: Any) -> bool:
    return normalization.status in TYPED_STATUSES


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
    credential_profile_counts: Counter[str] = Counter()
    exact_count_frequency: Counter[int] = Counter()
    duplicate_exact_bins: Counter[str] = Counter()
    unique_lineage_exact_bins: Counter[str] = Counter()
    catalog_row_index = 0

    for chunk_path in chunk_paths:
        rows = json.loads(chunk_path.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise ValueError(f"Canonical detail chunk is not an array: {chunk_path}")
        for event in rows:
            source = str(event.get("source") or "unknown").strip().lower() or "unknown"
            raw_fields = event.get("raw_fields") if isinstance(event.get("raw_fields"), dict) else {}
            raw_value = str(raw_fields.get(RAW_FIELD_NAME) or "").strip() if source == "nuforc" else ""
            if raw_value:
                event_id_value = event.get("event_id")
                event_id = event_id_value if isinstance(event_id_value, int) else str(event_id_value or "")
                if event_id == "":
                    raise ValueError(f"Witness-count-bearing catalog row {catalog_row_index} has no event ID")
                value_key = (source, raw_value)
                raw_counts[value_key] += 1
                if value_key not in normalization_by_value:
                    normalization_by_value[value_key] = normalize_witness_count(source, raw_value)
                normalized = normalization_by_value[value_key]
                macroregion = macroregion_by_event.get(str(event_id), "unknown")
                projections_raw.append((catalog_row_index, event_id, value_key, macroregion))
                source_raw_counts[source] += 1
                source_status_counts[source][normalized.status] += 1
                source_bin_counts[source][normalized.descriptive_bin] += 1
                reason_counts[normalized.reason] += 1
                if normalized.credential_profile:
                    credential_profile_counts[normalized.credential_profile] += 1
                if normalized.status == "exact_count" and normalized.exact_count is not None:
                    exact_count_frequency[normalized.exact_count] += 1
                    if int(event.get("duplicate_record_count") or 1) > 1:
                        duplicate_exact_bins[normalized.descriptive_bin] += 1
                    else:
                        unique_lineage_exact_bins[normalized.descriptive_bin] += 1
            catalog_row_index += 1

    if catalog_row_index != EXPECTED_CATALOG_ROWS:
        raise ValueError(f"Served catalog row count changed: {catalog_row_index}/{EXPECTED_CATALOG_ROWS}")
    if len(projections_raw) != EXPECTED_RAW_ROWS:
        raise ValueError(f"Explicit NUFORC witness-count row count changed: {len(projections_raw)}/{EXPECTED_RAW_ROWS}")

    ordered_value_keys = sorted(
        normalization_by_value,
        key=lambda key: (key[0], hashlib.sha256(key[1].encode("utf-8")).hexdigest(), key[1]),
    )
    value_codes = {key: index for index, key in enumerate(ordered_value_keys)}
    sources, source_code = codebook((key[0] for key in ordered_value_keys), first="unknown")
    reasons, reason_code = codebook((item.reason for item in normalization_by_value.values()))
    precisions, precision_code = codebook((item.precision for item in normalization_by_value.values()), first="unknown")
    credential_profiles, credential_code = codebook(
        (item.credential_profile for item in normalization_by_value.values()), first=""
    )
    macroregions, macroregion_code = codebook((row[3] for row in projections_raw), first="unknown")
    status_code = {value: index for index, value in enumerate(STATUS_CODES)}
    bin_code = {value: index for index, value in enumerate(WITNESS_COUNT_BINS)}

    value_dictionary = []
    for source, raw_value in ordered_value_keys:
        normalized = normalization_by_value[(source, raw_value)]
        value_dictionary.append([
            source_code[source],
            hashlib.sha256(raw_value.encode("utf-8")).hexdigest(),
            raw_value,
            status_code[normalized.status],
            reason_code[normalized.reason],
            normalized.exact_count,
            normalized.lower_count,
            normalized.upper_count,
            bin_code[normalized.descriptive_bin],
            precision_code[normalized.precision],
            credential_code[normalized.credential_profile],
            1 if normalized.extreme_audit else 0,
            raw_counts[(source, raw_value)],
        ])

    projection = [
        [row_index, event_id, value_codes[value_key], macroregion_code[macroregion]]
        for row_index, event_id, value_key, macroregion in projections_raw
    ]
    if sum(row[-1] for row in value_dictionary) != len(projection):
        raise ValueError("Witness-count dictionary occurrence counts do not match the event projection")

    typed_rows = sum(count for key, count in raw_counts.items() if typed_record(normalization_by_value[key]))
    exact_rows = sum(
        count for key, count in raw_counts.items() if normalization_by_value[key].status == "exact_count"
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
    dictionary_files = write_raw_and_gzip(output_root, "witness_count_value_dictionary_v1", value_dictionary)
    artifacts["witnessCountValueDictionary"] = artifact_entry(
        "witness_count_value_dictionary_v1",
        dictionary_files,
        len(value_dictionary),
        [
            "sourceCode", "rawValueSha256", "rawValue", "statusCode", "reasonCode",
            "exactCount", "lowerCount", "upperCount", "descriptiveBinCode", "precisionCode",
            "credentialProfileCode", "extremeAuditFlag", "occurrenceCount",
        ],
    )
    compressed_sizes["witnessCountValueDictionary"] = dictionary_files["gzipBytes"]
    payloads["witnessCountValueDictionaryRaw"] = {
        "path": "witness_count_value_dictionary_v1.json", "bytes": dictionary_files["rawBytes"],
        "sha256": dictionary_files["rawSha256"], "recordCount": len(value_dictionary), "r2Only": True,
    }
    payloads["witnessCountValueDictionaryGzip"] = {
        "path": "witness_count_value_dictionary_v1.json.gz", "bytes": dictionary_files["gzipBytes"],
        "sha256": dictionary_files["gzipSha256"], "decodedBytes": dictionary_files["rawBytes"],
        "recordCount": len(value_dictionary), "r2Only": True,
    }

    projection_keys: list[str] = []
    for shard_index, start in enumerate(range(0, len(projection), PROJECTION_SHARD_ROWS)):
        shard = projection[start:start + PROJECTION_SHARD_ROWS]
        stem = f"witness_count_projection_v1_{shard_index:03d}"
        key = f"witnessCountProjectionShard{shard_index:03d}"
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
        raise ValueError(f"Compressed witness-count artifact budget exceeded: {oversized}")

    typed_catalog_pct = 100 * typed_rows / catalog_row_index
    zero_rows = sum(count for key, count in raw_counts.items() if normalization_by_value[key].reason == "zero_source_sentinel")
    negative_rows = sum(count for key, count in raw_counts.items() if normalization_by_value[key].reason == "negative_source_sentinel")
    extreme_rows = sum(count for count_value, count in exact_count_frequency.items() if count_value >= 1000)
    high_rows = sum(count for count_value, count in exact_count_frequency.items() if count_value >= 100)
    credential_rows = sum(credential_profile_counts.values())
    material_gates = {
        "minimumTypedRows": typed_rows >= MINIMUM_TYPED_ROWS,
        "minimumTypedCatalogPct": typed_catalog_pct >= MINIMUM_TYPED_CATALOG_PCT,
        "minimumSupportedSources": len(supported_sources) >= MINIMUM_SUPPORTED_SOURCES,
        "minimumRowsPerSupportedSource": all(typed_by_source[source] >= MINIMUM_ROWS_PER_SOURCE for source in supported_sources),
        "singleSourceEnforced": supported_sources == ["nuforc"] and set(source_raw_counts) == {"nuforc"},
        "originalWitnessTextPreserved": all(bool(row[2]) for row in value_dictionary),
        "projectionParity": len(projection) == sum(source_raw_counts.values()),
        "dictionaryOccurrenceParity": sum(row[-1] for row in value_dictionary) == len(projection),
        "nonpositiveSentinelsFailClosed": zero_rows > 0 and negative_rows > 0,
        "typedUncertaintyClassesDeclared": all(
            status in STATUS_CODES
            for status in ("exact_count", "approximate_count", "bounded_range", "lower_bound", "qualitative_plural")
        ),
        "extremeCountsAudited": extreme_rows > 0,
        "credentialMetadataSeparated": credential_rows > 0,
        "compressedArtifactBudget": not oversized,
    }
    readiness_status = "ready_descriptive" if all(material_gates.values()) else "not_estimable"

    all_exact_bins = duplicate_exact_bins + unique_lineage_exact_bins
    exact_total = sum(all_exact_bins.values())
    unique_total = sum(unique_lineage_exact_bins.values())
    maximum_duplicate_holdout_shift = max(
        (
            abs(
                (unique_lineage_exact_bins[bin_id] / unique_total if unique_total else 0) -
                (all_exact_bins[bin_id] / exact_total if exact_total else 0)
            )
            for bin_id in WITNESS_COUNT_BINS[1:]
        ),
        default=0,
    )

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
        "artifactGroups": {"witnessCountProjectionShards": projection_keys},
        "payloads": payloads,
        "codes": {
            "source": sources,
            "status": list(STATUS_CODES),
            "reason": reasons,
            "witnessCountBin": list(WITNESS_COUNT_BINS),
            "precision": precisions,
            "credentialProfile": credential_profiles,
            "macroregion": macroregions,
        },
        "rowOrdering": {
            "policyId": "served_catalog_sparse_explicit_witness_count_subsequence_v1",
            "keyFields": ["catalogRowIndex", "eventId"],
            "sha256": sha256_bytes(compact_json_bytes([[row[0], row[1]] for row in projection])),
        },
        "inputs": {
            "canonicalManifest": {
                "path": "static_bundle/data/canonical_web/canonical_web_manifest.json",
                "sha256": sha256_file(detail_root.parent / "canonical_web_manifest.json"),
            },
            "geography": geography_input,
            "sourceFieldInventory": {
                "path": "data/canonical/source_field_inventories/nuforc.json",
                "bytes": (REPO_ROOT / "data/canonical/source_field_inventories/nuforc.json").stat().st_size,
                "sha256": sha256_file(REPO_ROOT / "data/canonical/source_field_inventories/nuforc.json"),
            },
        },
        "policy": {
            "canonicalEventsMutated": False,
            "explicitSourceFieldOnly": True,
            "sourceFieldName": RAW_FIELD_NAME,
            "narrativeDescriptionsRead": False,
            "missingCountIsZeroOrOne": False,
            "qualitativePartySizeIsExact": False,
            "approximateRangeOrLowerBoundIsExact": False,
            "credentialMetadataIsCredibilityEvidence": False,
            "extremeCountsDiscarded": False,
            "crossSourceComparison": False,
            "activeReferenceInference": False,
            "patternFinderPromotion": False,
            "credibilityIncidenceAuthenticityRiskOrCausalClaims": False,
        },
        "counts": {
            "catalogRows": catalog_row_index,
            "rawWitnessCountRows": len(projection),
            "uniqueSourceRawValues": len(value_dictionary),
            "typedRows": typed_rows,
            "typedCatalogPct": round(typed_catalog_pct, 6),
            "exactCountRows": exact_rows,
            "descriptiveBinnedRows": exact_rows,
            "zeroSentinelRows": zero_rows,
            "negativeSentinelRows": negative_rows,
            "highCountRows100Plus": high_rows,
            "extremeCountRows1000Plus": extreme_rows,
            "credentialTaggedRows": credential_rows,
            "maximumExactCount": max(exact_count_frequency, default=0),
            "bySourceRaw": dict(sorted(source_raw_counts.items())),
            "bySourceTyped": typed_by_source,
            "supportedSources": supported_sources,
            "bySourceStatus": {source: dict(sorted(counts.items())) for source, counts in sorted(source_status_counts.items())},
            "bySourceDescriptiveBin": {source: dict(sorted(counts.items())) for source, counts in sorted(source_bin_counts.items())},
            "byCredentialProfile": dict(sorted(credential_profile_counts.items())),
        },
        "readiness": {
            "status": readiness_status,
            "assessmentLane": "single_source_descriptive_only",
            "materialCriterion": "previously_unavailable_assessment_becomes_estimable",
            "materialGates": material_gates,
            "supportedSources": supported_sources,
            "suppressionPolicy": "Publish explicit-field descriptive counts only. Suppress active/reference inference, cross-source holdouts, Pattern Finder, and credibility or incidence interpretations while evidence remains NUFORC-only.",
            "warnings": [
                "Witness-count evidence is available from NUFORC only and cannot support cross-source comparison.",
                "Missing values are unknown, never zero or one witness.",
                "Credential suffixes describe source metadata and are not credibility evidence.",
                "Counts describe reports, not incidence, authenticity, risk, independent corroboration, or causal effects.",
            ],
        },
        "negativeControls": {
            "missingValueExclusion": {
                "catalogRowsWithoutExplicitWitnessCount": catalog_row_index - len(projection),
                "interpretation": "never_coerced_to_zero_or_one",
            },
            "nonpositiveSentinelAudit": {
                "zeroRows": zero_rows,
                "negativeRows": negative_rows,
                "interpretation": "invalid_source_codes_excluded_from_descriptive_count_bins",
            },
            "approximateRangeLowerBoundAndQualitativeHoldout": {
                "excludedRows": sum(
                    count for key, count in raw_counts.items()
                    if normalization_by_value[key].status in {
                        "approximate_count", "bounded_range", "lower_bound", "qualitative_plural"
                    }
                ),
                "interpretation": "typed_but_never_coerced_to_exact_count",
            },
            "extremeCountAudit": {
                "rows100Plus": high_rows,
                "rows1000Plus": extreme_rows,
                "maximumExactCount": max(exact_count_frequency, default=0),
                "interpretation": "retained_with_explicit_extreme_lane_not_silently_trimmed",
            },
            "duplicateLineageHoldout": {
                "duplicateLineageRows": sum(duplicate_exact_bins.values()),
                "retainedSingleRecordRows": unique_total,
                "maximumAbsoluteShareShift": round(maximum_duplicate_holdout_shift, 8),
                "interpretation": "descriptive_sensitivity_not_cross_source_independence",
            },
            "singleSourceComparisonSuppression": {
                "supportedSources": supported_sources,
                "activeReferenceInference": False,
                "patternFinderPromotion": False,
                "interpretation": "one_source_cannot_supply_an_independent_source_holdout",
            },
        },
    }
    manifest_path = output_root / "manifest.json"
    manifest_path.write_bytes(compact_json_bytes(manifest))

    audit = {
        "schemaId": "ufo-timeline-analysis-witness-count-build-audit-v1.0.0",
        "releaseId": RELEASE_ID,
        "status": readiness_status,
        "manifest": {
            "path": manifest_path.relative_to(REPO_ROOT).as_posix(),
            "bytes": manifest_path.stat().st_size,
            "sha256": sha256_file(manifest_path),
        },
        "counts": manifest["counts"],
        "materialGates": material_gates,
        "compressedArtifacts": dict(sorted(compressed_sizes.items())) | {
            "maximumBytesEach": MAXIMUM_COMPRESSED_ARTIFACT_BYTES
        },
        "normalizationReasons": [
            {"reason": reason, "rows": count} for reason, count in reason_counts.most_common()
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
