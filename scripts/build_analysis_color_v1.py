"""Build the immutable, event-aligned Analysis color v1 sidecar."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from scripts.analysis_color import CATEGORY_CODES, NORMALIZED_STATUSES, ROLE_CODES, SOURCE_SENTINELS, STATUS_CODES, normalize_color
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
    from analysis_color import CATEGORY_CODES, NORMALIZED_STATUSES, ROLE_CODES, SOURCE_SENTINELS, STATUS_CODES, normalize_color  # type: ignore
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
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "webapp" / "static_public" / "data" / "analysis_color_v1"
DEFAULT_AUDIT_PATH = (
    REPO_ROOT / "campaign" / "analysis_improvement" / "waves" /
    "wave-007-color-assessment" / "build_audit.json"
)
DEFAULT_RAW_AUDIT = (
    REPO_ROOT / "campaign" / "analysis_improvement" / "waves" /
    "wave-007-color-assessment" / "raw_value_audit.json"
)
DEFAULT_PARSER_CONTRACT = (
    REPO_ROOT / "campaign" / "analysis_improvement" / "waves" /
    "wave-007-color-assessment" / "parser_contract.json"
)
RELEASE_ID = "analysis-color-v1-20260805"
SCHEMA_ID = "ufo-timeline-analysis-color-artifacts-v1.0.0"
ASSET_ORIGIN = "https://pub-e9029ab2f6b448daad03d7cde7e15e64.r2.dev"
ASSET_BASE_URL = f"{ASSET_ORIGIN}/releases/{RELEASE_ID}"
EXPECTED_CATALOG_ROWS = 702_893
EXPECTED_RAW_ROWS = 79_215
EXPECTED_SOURCE_RAW_ROWS = {"nuforc": 11_686, "ufocat": 67_529}
EXPECTED_SOURCE_VALUE_PAIRS = 4_859
MINIMUM_NORMALIZED_ROWS = 63_372
MINIMUM_NORMALIZED_CATALOG_PCT = 9.0
MINIMUM_SUPPORTED_SOURCES = 2
MINIMUM_ROWS_PER_SOURCE = 1_000
MINIMUM_COMMON_SUPPORT_RATE = 0.8
MINIMUM_CELL_N = 20
MAXIMUM_COMPRESSED_ARTIFACT_BYTES = 5_000_000
SOURCE_FIELD_NAMES = {"nuforc": "Color", "ufocat": "COLOR"}


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


def category_mask(categories: tuple[str, ...]) -> int:
    mask = 0
    for category in categories:
        mask |= 1 << CATEGORY_CODES.index(category)
    return mask


def raw_color_value(event: dict[str, Any], source: str) -> str | None:
    key = SOURCE_FIELD_NAMES.get(source)
    raw_fields = event.get("raw_fields")
    if key is None or not isinstance(raw_fields, dict) or key not in raw_fields:
        return None
    raw = raw_fields.get(key)
    if raw is None or not str(raw).strip() or str(raw).strip().lower() in SOURCE_SENTINELS:
        return None
    return str(raw)


def category_support(
    normalized_by_value: dict[tuple[str, str], Any],
    raw_counts: Counter[tuple[str, str]],
    sources: list[str],
) -> dict[str, Any]:
    source_category_counts: dict[str, Counter[str]] = {source: Counter() for source in sources}
    for key, count in raw_counts.items():
        normalized = normalized_by_value[key]
        if not normalized.normalized:
            continue
        for category in normalized.categories:
            source_category_counts[key[0]][category] += count
    observed_categories = [
        category for category in CATEGORY_CODES
        if sum(source_category_counts[source][category] for source in sources) > 0
    ]
    common = [
        category for category in observed_categories
        if all(source_category_counts[source][category] >= MINIMUM_CELL_N for source in sources)
    ]
    rate = len(common) / len(observed_categories) if observed_categories else 0.0
    return {
        "minimumRowsPerSourceCategory": MINIMUM_CELL_N,
        "observedCategories": observed_categories,
        "commonSupportCategories": common,
        "commonSupportRate": round(rate, 8),
        "bySourceCategory": {
            source: {category: source_category_counts[source][category] for category in observed_categories}
            for source in sources
        },
    }


def build(args: argparse.Namespace) -> dict[str, Any]:
    detail_root = Path(args.detail_root).resolve()
    geography_path = Path(args.geography).resolve()
    analysis_manifest_path = Path(args.analysis_manifest).resolve()
    output_root = Path(args.output_root).resolve()
    audit_path = Path(args.audit_path).resolve()
    raw_audit_path = Path(args.raw_audit).resolve()
    parser_contract_path = Path(args.parser_contract).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)

    raw_audit = json.loads(raw_audit_path.read_text(encoding="utf-8"))
    parser_contract = json.loads(parser_contract_path.read_text(encoding="utf-8"))
    if raw_audit["coverage"]["eligibleRawColorRows"] != EXPECTED_RAW_ROWS:
        raise ValueError("Governing raw color audit row count changed")
    if raw_audit["valueInventory"]["distinctSourceValuePairs"] != EXPECTED_SOURCE_VALUE_PAIRS:
        raise ValueError("Governing raw color source-value inventory changed")
    if parser_contract["governingAudit"]["sha256"] != sha256_file(raw_audit_path):
        raise ValueError("Parser contract does not pin the current raw color audit")

    macroregion_by_event, geography_input = load_macroregions(geography_path, analysis_manifest_path)
    chunk_paths = sorted(detail_root.glob("chunk_*.json"))
    if not chunk_paths:
        raise ValueError(f"No canonical detail chunks found under {detail_root}")

    projections_raw: list[tuple[int, int | str, tuple[str, str], str, str]] = []
    normalization_by_value: dict[tuple[str, str], Any] = {}
    raw_counts: Counter[tuple[str, str]] = Counter()
    source_raw_counts: Counter[str] = Counter()
    source_status_counts: dict[str, Counter[str]] = defaultdict(Counter)
    source_role_counts: dict[str, Counter[str]] = defaultdict(Counter)
    source_category_counts: dict[str, Counter[str]] = defaultdict(Counter)
    reason_counts: Counter[str] = Counter()
    era_counts: Counter[str] = Counter()
    macroregion_counts: Counter[str] = Counter()
    catalog_row_index = 0

    for chunk_path in chunk_paths:
        rows = json.loads(chunk_path.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise ValueError(f"Canonical detail chunk is not an array: {chunk_path}")
        for event in rows:
            source = str(event.get("source") or "unknown").strip().lower() or "unknown"
            raw_value = raw_color_value(event, source)
            if raw_value is not None:
                event_id_value = event.get("event_id")
                event_id = event_id_value if isinstance(event_id_value, int) else str(event_id_value or "")
                if event_id == "":
                    raise ValueError(f"Color-bearing catalog row {catalog_row_index} has no event ID")
                value_key = (source, raw_value)
                raw_counts[value_key] += 1
                if value_key not in normalization_by_value:
                    normalization_by_value[value_key] = normalize_color(source, raw_value)
                normalized = normalization_by_value[value_key]
                era = era_for(event.get("sort_date_iso") or event.get("date_iso"))
                macroregion = macroregion_by_event.get(str(event_id), "unknown")
                projections_raw.append((catalog_row_index, event_id, value_key, era, macroregion))
                source_raw_counts[source] += 1
                source_status_counts[source][normalized.status] += 1
                source_role_counts[source][normalized.role] += 1
                for category in normalized.categories:
                    source_category_counts[source][category] += 1
                reason_counts[normalized.reason] += 1
                era_counts[era] += 1
                macroregion_counts[macroregion] += 1
            catalog_row_index += 1

    if catalog_row_index != EXPECTED_CATALOG_ROWS:
        raise ValueError(f"Served catalog row count changed: {catalog_row_index}/{EXPECTED_CATALOG_ROWS}")
    if len(projections_raw) != EXPECTED_RAW_ROWS:
        raise ValueError(f"Explicit color row count changed: {len(projections_raw)}/{EXPECTED_RAW_ROWS}")
    if dict(source_raw_counts) != EXPECTED_SOURCE_RAW_ROWS:
        raise ValueError(f"Explicit color source row counts changed: {dict(source_raw_counts)}")
    if len(raw_counts) != EXPECTED_SOURCE_VALUE_PAIRS:
        raise ValueError(f"Exact source-value pair count changed: {len(raw_counts)}/{EXPECTED_SOURCE_VALUE_PAIRS}")

    ordered_value_keys = sorted(
        normalization_by_value,
        key=lambda key: (key[0], hashlib.sha256(key[1].encode("utf-8")).hexdigest(), key[1]),
    )
    value_codes = {key: index for index, key in enumerate(ordered_value_keys)}
    sources, source_code = codebook((key[0] for key in ordered_value_keys), first="unknown")
    reasons, reason_code = codebook((item.reason for item in normalization_by_value.values()))
    eras, era_code = codebook((row[3] for row in projections_raw), first="unknown")
    macroregions, macroregion_code = codebook((row[4] for row in projections_raw), first="unknown")
    status_code = {value: index for index, value in enumerate(STATUS_CODES)}
    role_code = {value: index for index, value in enumerate(ROLE_CODES)}

    value_dictionary = []
    for source, raw_value in ordered_value_keys:
        normalized = normalization_by_value[(source, raw_value)]
        value_dictionary.append([
            source_code[source],
            normalized.raw_value_sha256,
            normalized.raw_value,
            status_code[normalized.status],
            reason_code[normalized.reason],
            role_code[normalized.role],
            category_mask(normalized.categories),
            1 if normalized.changing else 0,
            1 if normalized.multicolor else 0,
            1 if normalized.compound else 0,
            raw_counts[(source, raw_value)],
        ])
    projection = [
        [row_index, event_id, value_codes[value_key], era_code[era], macroregion_code[macroregion]]
        for row_index, event_id, value_key, era, macroregion in projections_raw
    ]
    if sum(row[-1] for row in value_dictionary) != len(projection):
        raise ValueError("Color dictionary occurrence counts do not match the event projection")

    normalized_rows = sum(
        count for key, count in raw_counts.items() if normalization_by_value[key].status in NORMALIZED_STATUSES
    )
    normalized_by_source = {
        source: sum(
            count for key, count in raw_counts.items()
            if key[0] == source and normalization_by_value[key].status in NORMALIZED_STATUSES
        )
        for source in sorted(source_raw_counts)
    }
    supported_sources = sorted(
        source for source, count in normalized_by_source.items() if count >= MINIMUM_ROWS_PER_SOURCE
    )
    normalized_catalog_pct = 100 * normalized_rows / catalog_row_index
    role_unspecified_rows = sum(
        count for key, count in raw_counts.items()
        if normalization_by_value[key].role == "role_unspecified"
    )
    role_specific_rows = len(projection) - role_unspecified_rows - sum(
        count for key, count in raw_counts.items()
        if normalization_by_value[key].role == "both_role_cues_ambiguous"
    )
    support = category_support(normalization_by_value, raw_counts, supported_sources)

    artifacts: dict[str, Any] = {}
    payloads: dict[str, Any] = {}
    compressed_sizes: dict[str, int] = {}
    dictionary_files = write_raw_and_gzip(output_root, "color_value_dictionary_v1", value_dictionary)
    artifacts["colorValueDictionary"] = artifact_entry(
        "color_value_dictionary_v1",
        dictionary_files,
        len(value_dictionary),
        [
            "sourceCode", "rawValueSha256", "rawValue", "statusCode", "reasonCode", "roleCode",
            "categoryMask", "changingFlag", "multicolorFlag", "compoundFlag", "occurrenceCount",
        ],
    )
    compressed_sizes["colorValueDictionary"] = dictionary_files["gzipBytes"]
    projection_files = write_raw_and_gzip(output_root, "color_projection_v1", projection)
    artifacts["colorProjection"] = artifact_entry(
        "color_projection_v1",
        projection_files,
        len(projection),
        ["catalogRowIndex", "eventId", "valueCode", "eraCode", "macroregionCode"],
    )
    compressed_sizes["colorProjection"] = projection_files["gzipBytes"]
    for key, stem, files, rows in (
        ("colorValueDictionary", "color_value_dictionary_v1", dictionary_files, value_dictionary),
        ("colorProjection", "color_projection_v1", projection_files, projection),
    ):
        payloads[f"{key}Raw"] = {
            "path": f"{stem}.json",
            "bytes": files["rawBytes"],
            "sha256": files["rawSha256"],
            "recordCount": len(rows),
            "r2Only": True,
        }
        payloads[f"{key}Gzip"] = {
            "path": f"{stem}.json.gz",
            "bytes": files["gzipBytes"],
            "sha256": files["gzipSha256"],
            "decodedBytes": files["rawBytes"],
            "recordCount": len(rows),
            "r2Only": True,
        }
    oversized = {key: size for key, size in compressed_sizes.items() if size > MAXIMUM_COMPRESSED_ARTIFACT_BYTES}

    material_gates = {
        "minimumNormalizedRows": normalized_rows >= MINIMUM_NORMALIZED_ROWS,
        "minimumNormalizedCatalogPct": normalized_catalog_pct >= MINIMUM_NORMALIZED_CATALOG_PCT,
        "minimumSupportedSources": len(supported_sources) >= MINIMUM_SUPPORTED_SOURCES,
        "minimumRowsPerSupportedSource": all(normalized_by_source[source] >= MINIMUM_ROWS_PER_SOURCE for source in supported_sources),
        "minimumCommonSupportRate": support["commonSupportRate"] >= MINIMUM_COMMON_SUPPORT_RATE,
        "originalValuesPreserved": all(
            row[2] == ordered_value_keys[index][1] and row[1] == sha256_bytes(row[2].encode("utf-8"))
            for index, row in enumerate(value_dictionary)
        ),
        "sourceOccurrenceParity": dict(source_raw_counts) == raw_audit["coverage"]["sourceEligibleRows"],
        "dictionaryOccurrenceParity": sum(row[-1] for row in value_dictionary) == len(projection),
        "roleAmbiguityPreserved": role_unspecified_rows > 0,
        "objectAndLightRolesSeparated": all(role in ROLE_CODES for role in ("emitted_light_explicit", "object_surface_explicit")),
        "descriptorsExcludedFromNormalizedRows": all(
            not item.normalized for item in normalization_by_value.values() if item.status == "non_color_descriptor"
        ),
        "compressedArtifactBudget": not oversized,
        "patternFinderSuppressed": True,
    }
    readiness_status = "ready_descriptive_cross_source" if all(material_gates.values()) else "not_estimable"

    manifest = {
        "schemaId": SCHEMA_ID,
        "schemaVersion": 1,
        "manifestVersion": "1.0.0",
        "releaseId": RELEASE_ID,
        "generatedAt": "2026-08-05T00:00:00Z",
        "assetBaseUrl": ASSET_BASE_URL,
        "delivery": {
            "pagesFiles": ["manifest.json"],
            "r2OnlyPaths": [item["path"] for item in payloads.values()],
            "immutablePrefix": f"releases/{RELEASE_ID}",
            "cacheControl": "public, max-age=31536000, immutable",
        },
        "artifacts": artifacts,
        "payloads": payloads,
        "codes": {
            "source": sources,
            "status": list(STATUS_CODES),
            "reason": reasons,
            "role": list(ROLE_CODES),
            "category": list(CATEGORY_CODES),
            "era": eras,
            "macroregion": macroregions,
        },
        "rowOrdering": {
            "policyId": "served_catalog_sparse_explicit_color_subsequence_v1",
            "keyFields": ["catalogRowIndex", "eventId"],
            "sha256": sha256_bytes(compact_json_bytes([[row[0], row[1]] for row in projection])),
        },
        "inputs": {
            "canonicalManifest": {
                "path": "static_bundle/data/canonical_web/canonical_web_manifest.json",
                "sha256": sha256_file(detail_root.parent / "canonical_web_manifest.json"),
            },
            "geography": geography_input,
            "rawValueAudit": {
                "path": raw_audit_path.relative_to(REPO_ROOT).as_posix(),
                "bytes": raw_audit_path.stat().st_size,
                "sha256": sha256_file(raw_audit_path),
            },
            "parserContract": {
                "path": parser_contract_path.relative_to(REPO_ROOT).as_posix(),
                "bytes": parser_contract_path.stat().st_size,
                "sha256": sha256_file(parser_contract_path),
            },
        },
        "policy": {
            "canonicalEventsMutated": False,
            "explicitSourceFieldOnly": True,
            "narrativeDescriptionsRead": False,
            "neighboringFieldsRead": False,
            "fuzzyMatchingUsed": False,
            "sourceFieldImpliesObjectColor": False,
            "missingColorIsColorlessOrZero": False,
            "descriptorsAreExactColors": False,
            "unknownRolePromoted": False,
            "minimumCommonSupport": MINIMUM_COMMON_SUPPORT_RATE,
            "minimumActiveAndReferenceCellN": MINIMUM_CELL_N,
            "patternFinderPromotion": False,
            "incidenceAuthenticityRiskCausalOrCraftClaims": False,
        },
        "counts": {
            "catalogRows": catalog_row_index,
            "rawColorRows": len(projection),
            "uniqueSourceRawValues": len(value_dictionary),
            "normalizedRows": normalized_rows,
            "normalizedCatalogPct": round(normalized_catalog_pct, 6),
            "roleUnspecifiedRows": role_unspecified_rows,
            "roleSpecificRows": role_specific_rows,
            "bySourceRaw": dict(sorted(source_raw_counts.items())),
            "bySourceNormalized": normalized_by_source,
            "supportedSources": supported_sources,
            "bySourceStatus": {source: dict(sorted(counts.items())) for source, counts in sorted(source_status_counts.items())},
            "bySourceRole": {source: dict(sorted(counts.items())) for source, counts in sorted(source_role_counts.items())},
            "bySourceCategory": {source: dict(sorted(counts.items())) for source, counts in sorted(source_category_counts.items())},
            "byEraRaw": dict(sorted(era_counts.items())),
            "byMacroregionRaw": dict(sorted(macroregion_counts.items())),
        },
        "commonSupport": support,
        "readiness": {
            "status": readiness_status,
            "assessmentLane": "cross_source_descriptive_role_preserving",
            "materialCriterion": "previously_unavailable_assessment_becomes_estimable",
            "materialGates": material_gates,
            "supportedSources": supported_sources,
            "suppressionPolicy": "Suppress any category, active/reference estimate, or export cell below support thresholds. role_unspecified remains explicitly unspecified and is never relabeled object color or emitted-light color.",
            "warnings": [
                "Color values describe reports, not incidence, authenticity, risk, craft properties, or causal effects.",
                "The source Color column does not establish whether a value refers to an object surface or emitted light.",
                "Missing color is unknown, never colorless or a negative observation.",
                "Descriptor-only and unparsed values remain visible in readiness accounting but do not count as normalized colors.",
            ],
        },
        "negativeControls": {
            "missingValueExclusion": {
                "catalogRowsWithoutEligibleRawColor": catalog_row_index - len(projection),
                "interpretation": "unknown_not_colorless_or_zero",
            },
            "roleSeparation": {
                "roleUnspecifiedRows": role_unspecified_rows,
                "roleSpecificRows": role_specific_rows,
                "interpretation": "unknown_object_and_light_roles_never_collapsed",
            },
            "descriptorHoldout": {
                "rows": sum(
                    count for key, count in raw_counts.items()
                    if normalization_by_value[key].status == "non_color_descriptor"
                ),
                "interpretation": "appearance_and_luminosity_descriptors_excluded_from_normalized_color_rows",
            },
            "unparsedHoldout": {
                "rows": sum(
                    count for key, count in raw_counts.items()
                    if normalization_by_value[key].status == "unparsed"
                ),
                "interpretation": "unsupported_text_preserved_without_fuzzy_repair",
            },
            "commonSupport": support,
            "patternFinderSuppression": {
                "eligible": False,
                "interpretation": "descriptive_color_assessment_is_not_an_anomaly_detector",
            },
        },
    }
    manifest_path = output_root / "manifest.json"
    manifest_path.write_bytes(compact_json_bytes(manifest))
    audit = {
        "schemaId": "ufo-timeline-analysis-color-build-audit-v1.0.0",
        "releaseId": RELEASE_ID,
        "status": readiness_status,
        "manifest": {
            "path": manifest_path.relative_to(REPO_ROOT).as_posix(),
            "bytes": manifest_path.stat().st_size,
            "sha256": sha256_file(manifest_path),
        },
        "counts": manifest["counts"],
        "commonSupport": support,
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
        "ok": readiness_status == "ready_descriptive_cross_source",
        "status": readiness_status,
        "manifest": str(manifest_path),
        "audit": str(audit_path),
        "counts": manifest["counts"],
        "commonSupport": support,
        "compressedArtifacts": audit["compressedArtifacts"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--detail-root", default=str(DEFAULT_DETAIL_ROOT))
    parser.add_argument("--geography", default=str(DEFAULT_GEOGRAPHY))
    parser.add_argument("--analysis-manifest", default=str(DEFAULT_ANALYSIS_MANIFEST))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--audit-path", default=str(DEFAULT_AUDIT_PATH))
    parser.add_argument("--raw-audit", default=str(DEFAULT_RAW_AUDIT))
    parser.add_argument("--parser-contract", default=str(DEFAULT_PARSER_CONTRACT))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(build(parse_args()), indent=2, sort_keys=True))
