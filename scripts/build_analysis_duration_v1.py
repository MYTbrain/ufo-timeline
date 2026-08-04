"""Build the immutable, event-aligned Analysis duration v1 sidecar."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

try:
    from scripts.analysis_duration import DURATION_BINS, STATUS_CODES, normalize_duration
except ModuleNotFoundError:  # Direct ``python scripts/...`` execution.
    from analysis_duration import DURATION_BINS, STATUS_CODES, normalize_duration


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DETAIL_ROOT = REPO_ROOT / "static_bundle" / "data" / "canonical_web" / "event_chunks"
DEFAULT_GEOGRAPHY = REPO_ROOT / "webapp" / "static_public" / "data" / "analysis_v2" / "ufo_geography_v1.json"
DEFAULT_ANALYSIS_MANIFEST = REPO_ROOT / "webapp" / "static_public" / "data" / "analysis_v2" / "manifest.json"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "webapp" / "static_public" / "data" / "analysis_duration_v1"
DEFAULT_AUDIT_PATH = (
    REPO_ROOT / "campaign" / "analysis_improvement" / "waves" /
    "wave-001-duration-assessment" / "build_audit.json"
)
RELEASE_ID = "analysis-duration-v1-20260804"
SCHEMA_ID = "ufo-timeline-analysis-duration-artifacts-v1.0.0"
ASSET_ORIGIN = "https://pub-e9029ab2f6b448daad03d7cde7e15e64.r2.dev"
ASSET_BASE_URL = f"{ASSET_ORIGIN}/releases/{RELEASE_ID}"
EXPECTED_CATALOG_ROWS = 702_893
MINIMUM_NORMALIZED_ROWS = 232_065
MINIMUM_NORMALIZED_CATALOG_PCT = 33.0
MINIMUM_SUPPORTED_SOURCES = 2
MINIMUM_ROWS_PER_SOURCE = 1_000
MAXIMUM_COMPRESSED_ARTIFACT_BYTES = 5_000_000


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def compact_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def write_raw_and_gzip(output_root: Path, stem: str, value: Any) -> dict[str, Any]:
    raw_path = output_root / f"{stem}.json"
    gzip_path = output_root / f"{stem}.json.gz"
    raw_bytes = compact_json_bytes(value)
    raw_path.write_bytes(raw_bytes)
    with gzip_path.open("wb") as output_handle:
        with gzip.GzipFile(filename="", mode="wb", fileobj=output_handle, mtime=0, compresslevel=9) as gzip_handle:
            gzip_handle.write(raw_bytes)
    return {
        "rawPath": raw_path,
        "gzipPath": gzip_path,
        "rawBytes": len(raw_bytes),
        "gzipBytes": gzip_path.stat().st_size,
        "rawSha256": sha256_bytes(raw_bytes),
        "gzipSha256": sha256_file(gzip_path),
    }


def era_for(value: Any) -> str:
    text = str(value or "").strip()
    try:
        year = date.fromisoformat(text[:10]).year
    except (TypeError, ValueError):
        try:
            year = int(text[:4])
        except (TypeError, ValueError):
            return "unknown"
    if year < 1945:
        return "pre_1945"
    if year < 1960:
        return "1945_1959"
    if year < 1980:
        return "1960_1979"
    if year < 2000:
        return "1980_1999"
    if year < 2020:
        return "2000_2019"
    return "2020_plus"


def load_macroregions(geography_path: Path, manifest_path: Path) -> tuple[dict[str, str], dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entry = manifest["artifacts"]["ufoGeography"]
    if sha256_file(geography_path) != entry["sha256"]:
        raise ValueError("Pinned geography artifact failed its manifest SHA-256")
    rows = json.loads(geography_path.read_text(encoding="utf-8"))
    codes = manifest["codes"]["ufoGeography"]["macroregion"]
    macroregions: dict[str, str] = {}
    for row in rows:
        event_id = str(row[1])
        code = int(row[3])
        macroregions[event_id] = str(codes[code]) if 0 <= code < len(codes) else "unknown"
    if len(rows) != int(entry["rowCount"]):
        raise ValueError("Pinned geography artifact row count disagrees with its manifest")
    return macroregions, {
        "path": geography_path.relative_to(REPO_ROOT).as_posix(),
        "bytes": geography_path.stat().st_size,
        "sha256": entry["sha256"],
        "rowCount": len(rows),
        "releaseId": entry["releaseId"],
    }


def codebook(values: Iterable[str], *, first: str | None = None) -> tuple[list[str], dict[str, int]]:
    ordered = sorted(set(values))
    if first is not None:
        ordered = [first] + [value for value in ordered if value != first]
    return ordered, {value: index for index, value in enumerate(ordered)}


def normalized_record(normalization: Any) -> bool:
    return (
        normalization.status not in {"unparsed", "ambiguous"}
        and (normalization.lower_seconds is not None or normalization.upper_seconds is not None)
    )


def stable_share_diagnostics(rows: list[tuple[str, str, str, str]], dimension_index: int) -> dict[str, Any]:
    """Report descriptive leave-one-group shifts without making them a release gate."""

    eligible = [row for row in rows if row[3] != "unknown"]
    total = Counter(row[3] for row in eligible)
    total_n = sum(total.values())
    groups = sorted({row[dimension_index] for row in eligible if row[dimension_index] != "unknown"})
    holdouts = []
    for group in groups:
        retained = [row for row in eligible if row[dimension_index] != group]
        retained_counts = Counter(row[3] for row in retained)
        retained_n = sum(retained_counts.values())
        maximum_shift = max(
            (
                abs((retained_counts[bin_id] / retained_n if retained_n else 0) - (total[bin_id] / total_n if total_n else 0))
                for bin_id in DURATION_BINS[1:]
            ),
            default=0,
        )
        holdouts.append({
            "heldOut": group,
            "retainedRows": retained_n,
            "maximumAbsoluteShareShift": round(maximum_shift, 8),
        })
    return {"groups": groups, "holdouts": holdouts, "interpretation": "descriptive_sensitivity_not_release_gate"}


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
    raw_counts: Counter[tuple[str, str]] = Counter()
    normalization_by_value: dict[tuple[str, str], Any] = {}
    source_counts: Counter[str] = Counter()
    source_status_counts: dict[str, Counter[str]] = defaultdict(Counter)
    source_bin_counts: dict[str, Counter[str]] = defaultdict(Counter)
    reason_counts: Counter[str] = Counter()
    diagnostics_rows: list[tuple[str, str, str, str]] = []
    catalog_row_index = 0

    for chunk_path in chunk_paths:
        rows = json.loads(chunk_path.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise ValueError(f"Canonical detail chunk is not an array: {chunk_path}")
        for event in rows:
            source = str(event.get("source") or "unknown").strip().lower() or "unknown"
            raw_value = str(event.get("duration_raw") or "").strip()
            if raw_value:
                event_id_value = event.get("event_id")
                event_id = event_id_value if isinstance(event_id_value, int) else str(event_id_value or "")
                if event_id == "":
                    raise ValueError(f"Duration-bearing catalog row {catalog_row_index} has no event ID")
                value_key = (source, raw_value)
                raw_counts[value_key] += 1
                if value_key not in normalization_by_value:
                    normalization_by_value[value_key] = normalize_duration(source, raw_value)
                normalization = normalization_by_value[value_key]
                macroregion = macroregion_by_event.get(str(event_id), "unknown")
                projections_raw.append((catalog_row_index, event_id, value_key, macroregion))
                source_counts[source] += 1
                source_status_counts[source][normalization.status] += 1
                source_bin_counts[source][normalization.descriptive_bin] += 1
                reason_counts[normalization.reason] += 1
                if normalized_record(normalization):
                    diagnostics_rows.append((source, era_for(event.get("sort_date_iso") or event.get("date_iso")), macroregion, normalization.descriptive_bin))
            catalog_row_index += 1

    if catalog_row_index != EXPECTED_CATALOG_ROWS:
        raise ValueError(f"Served catalog row count changed: {catalog_row_index}/{EXPECTED_CATALOG_ROWS}")

    ordered_value_keys = sorted(normalization_by_value, key=lambda key: (key[0], hashlib.sha256(key[1].encode("utf-8")).hexdigest(), key[1]))
    value_codes = {key: index for index, key in enumerate(ordered_value_keys)}
    reasons, reason_code = codebook((item.reason for item in normalization_by_value.values()), first="empty")
    source_contracts, source_contract_code = codebook((item.source_contract for item in normalization_by_value.values()), first="none")
    sources, source_code = codebook((key[0] for key in ordered_value_keys), first="unknown")
    statuses = list(STATUS_CODES)
    status_code = {value: index for index, value in enumerate(statuses)}
    bins = list(DURATION_BINS)
    bin_code = {value: index for index, value in enumerate(bins)}
    macroregions, macroregion_code = codebook((row[3] for row in projections_raw), first="unknown")

    value_dictionary = []
    for source, raw_value in ordered_value_keys:
        normalized = normalization_by_value[(source, raw_value)]
        value_dictionary.append([
            source_code[source],
            hashlib.sha256(raw_value.encode("utf-8")).hexdigest(),
            raw_value,
            status_code[normalized.status],
            reason_code[normalized.reason],
            normalized.lower_seconds,
            normalized.upper_seconds,
            bin_code[normalized.descriptive_bin],
            bin_code[normalized.inferential_bin],
            source_contract_code[normalized.source_contract],
            raw_counts[(source, raw_value)],
        ])

    projection = [
        [row_index, event_id, value_codes[value_key], macroregion_code[macroregion]]
        for row_index, event_id, value_key, macroregion in projections_raw
    ]
    if sum(row[-1] for row in value_dictionary) != len(projection):
        raise ValueError("Duration dictionary occurrence counts do not match the event projection")

    normalized_rows = sum(
        count for key, count in raw_counts.items() if normalized_record(normalization_by_value[key])
    )
    inferential_rows = sum(
        count for key, count in raw_counts.items() if normalization_by_value[key].inferential_bin != "unknown"
    )
    descriptive_binned_rows = sum(
        count for key, count in raw_counts.items() if normalization_by_value[key].descriptive_bin != "unknown"
    )
    normalized_by_source = {
        source: sum(
            count for key, count in raw_counts.items()
            if key[0] == source and normalized_record(normalization_by_value[key])
        )
        for source in sorted(source_counts)
    }
    supported_sources = sorted(
        source for source, count in normalized_by_source.items() if count >= MINIMUM_ROWS_PER_SOURCE
    )

    dictionary_files = write_raw_and_gzip(output_root, "duration_value_dictionary_v1", value_dictionary)
    projection_files = write_raw_and_gzip(output_root, "duration_projection_v1", projection)
    if dictionary_files["gzipBytes"] > MAXIMUM_COMPRESSED_ARTIFACT_BYTES:
        raise ValueError("Compressed duration dictionary exceeds the preregistered artifact budget")
    if projection_files["gzipBytes"] > MAXIMUM_COMPRESSED_ARTIFACT_BYTES:
        raise ValueError("Compressed duration projection exceeds the preregistered artifact budget")

    codebook_path = REPO_ROOT / "data" / "reports" / "ufocat_codebook_extract" / "UFOCAT Codebook 2023.txt"
    source_inventory_paths = {
        "majestic": REPO_ROOT / "data" / "canonical" / "source_field_inventories" / "majestic.json",
        "nuforc": REPO_ROOT / "data" / "canonical" / "source_field_inventories" / "nuforc.json",
        "ufocat": REPO_ROOT / "data" / "canonical" / "source_field_inventories" / "ufocat2023.json",
    }
    source_contract_evidence = {
        "ufocatCodebook": {
            "path": codebook_path.relative_to(REPO_ROOT).as_posix(),
            "bytes": codebook_path.stat().st_size,
            "sha256": sha256_file(codebook_path),
            "durationSection": "FIELD NAME: DUR WIDTH: 3 characters",
        },
        "sourceFieldInventories": {
            source: {
                "path": path.relative_to(REPO_ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for source, path in source_inventory_paths.items()
        },
    }
    normalized_catalog_pct = 100 * normalized_rows / catalog_row_index
    material_gates = {
        "minimumNormalizedRows": normalized_rows >= MINIMUM_NORMALIZED_ROWS,
        "minimumNormalizedCatalogPct": normalized_catalog_pct >= MINIMUM_NORMALIZED_CATALOG_PCT,
        "minimumSupportedSources": len(supported_sources) >= MINIMUM_SUPPORTED_SOURCES,
        "originalValuesPreserved": True,
        "projectionParity": len(projection) == sum(source_counts.values()),
        "compressedArtifactBudget": True,
    }
    readiness_status = "ready_descriptive" if all(material_gates.values()) else "not_estimable"

    artifacts = {}
    payloads = {}
    for key, stem, files, rows, row_schema in (
        (
            "durationValueDictionary", "duration_value_dictionary_v1", dictionary_files, len(value_dictionary),
            ["sourceCode", "rawValueSha256", "rawValue", "statusCode", "reasonCode", "lowerSeconds", "upperSeconds", "descriptiveBinCode", "inferentialBinCode", "sourceContractCode", "occurrenceCount"],
        ),
        (
            "durationProjection", "duration_projection_v1", projection_files, len(projection),
            ["catalogRowIndex", "eventId", "valueCode", "macroregionCode"],
        ),
    ):
        raw_name = f"{stem}.json"
        gzip_name = f"{stem}.json.gz"
        artifacts[key] = {
            "artifactId": stem,
            "releaseId": f"{RELEASE_ID}.{stem}",
            "file": f"{ASSET_BASE_URL}/{raw_name}",
            "gzipFile": f"{ASSET_BASE_URL}/{gzip_name}",
            "bytes": files["rawBytes"],
            "gzipBytes": files["gzipBytes"],
            "sha256": files["rawSha256"],
            "gzipSha256": files["gzipSha256"],
            "rowCount": rows,
            "rowSchema": row_schema,
        }
        payloads[f"{key}Raw"] = {
            "path": raw_name,
            "bytes": files["rawBytes"],
            "sha256": files["rawSha256"],
            "recordCount": rows,
            "r2Only": True,
        }
        payloads[f"{key}Gzip"] = {
            "path": gzip_name,
            "bytes": files["gzipBytes"],
            "sha256": files["gzipSha256"],
            "decodedBytes": files["rawBytes"],
            "recordCount": rows,
            "r2Only": True,
        }

    projection_order_bytes = compact_json_bytes([[row[0], row[1]] for row in projection])
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
        "payloads": payloads,
        "codes": {
            "source": sources,
            "status": statuses,
            "reason": reasons,
            "durationBin": bins,
            "sourceContract": source_contracts,
            "macroregion": macroregions,
        },
        "rowOrdering": {
            "policyId": "served_catalog_sparse_duration_subsequence_v1",
            "keyFields": ["catalogRowIndex", "eventId"],
            "sha256": sha256_bytes(projection_order_bytes),
        },
        "inputs": {
            "canonicalManifest": {
                "path": "static_bundle/data/canonical_web/canonical_web_manifest.json",
                "sha256": sha256_file(detail_root.parent / "canonical_web_manifest.json"),
            },
            "geography": geography_input,
            "sourceContracts": source_contract_evidence,
        },
        "policy": {
            "canonicalEventsMutated": False,
            "narrativeDescriptionsRead": False,
            "missingDurationIsZero": False,
            "majesticBareNumericUnitAssigned": False,
            "ufocatApproximateCodesInferentiallyEligible": False,
            "binSpanningIntervalsInferentiallyEligible": False,
            "patternFinderPromotion": False,
            "runtimeCovariates": ["source", "era", "macroregion"],
            "minimumCommonSupport": 0.8,
            "minimumActiveAndReferenceBinN": 20,
        },
        "counts": {
            "catalogRows": catalog_row_index,
            "rawDurationRows": len(projection),
            "uniqueSourceRawValues": len(value_dictionary),
            "normalizedRows": normalized_rows,
            "normalizedCatalogPct": round(normalized_catalog_pct, 6),
            "descriptiveBinnedRows": descriptive_binned_rows,
            "inferentialBinnedRows": inferential_rows,
            "bySourceRaw": dict(sorted(source_counts.items())),
            "bySourceNormalized": normalized_by_source,
            "supportedSources": supported_sources,
            "bySourceStatus": {source: dict(sorted(counts.items())) for source, counts in sorted(source_status_counts.items())},
            "bySourceDescriptiveBin": {source: dict(sorted(counts.items())) for source, counts in sorted(source_bin_counts.items())},
        },
        "readiness": {
            "status": readiness_status,
            "assessmentLane": "descriptive_with_runtime_gated_comparisons",
            "materialCriterion": "previously_unavailable_assessment_becomes_estimable",
            "materialGates": material_gates,
            "supportedSources": supported_sources,
            "suppressionPolicy": "Suppress charts and comparisons when artifact integrity, typed coverage, source support, active/reference bin N, common support, or holdout stability fails.",
            "warnings": [
                "UFOCAT DUR values are approximate under the pinned source codebook.",
                "Majestic bare numeric duration units remain unresolved and are not normalized.",
                "Duration is reported observation time, not event authenticity, incidence, risk, or inferred travel time.",
            ],
        },
        "negativeControls": {
            "leaveOneSourceOut": stable_share_diagnostics(diagnostics_rows, 0),
            "eraHoldout": stable_share_diagnostics(diagnostics_rows, 1),
            "macroregionHoldout": stable_share_diagnostics(diagnostics_rows, 2),
        },
    }
    manifest_path = output_root / "manifest.json"
    manifest_path.write_bytes(compact_json_bytes(manifest))

    audit = {
        "schemaId": "ufo-timeline-analysis-duration-build-audit-v1.0.0",
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
            "dictionaryBytes": dictionary_files["gzipBytes"],
            "projectionBytes": projection_files["gzipBytes"],
            "maximumBytesEach": MAXIMUM_COMPRESSED_ARTIFACT_BYTES,
        },
        "topNormalizationReasons": [
            {"reason": reason, "rows": count}
            for reason, count in reason_counts.most_common(20)
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
