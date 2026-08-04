"""Build the immutable, event-aligned Analysis reporting-delay v1 sidecar."""

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
    from scripts.analysis_reporting_delay import (
        DELAY_BINS,
        ROLE_CODES,
        STATUS_CODES,
        normalize_reporting_delay,
        parse_explicit_day,
        reporting_delay_bin,
    )
except ModuleNotFoundError:  # Direct ``python scripts/...`` execution.
    from analysis_reporting_delay import (  # type: ignore
        DELAY_BINS,
        ROLE_CODES,
        STATUS_CODES,
        normalize_reporting_delay,
        parse_explicit_day,
        reporting_delay_bin,
    )


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DETAIL_ROOT = REPO_ROOT / "static_bundle" / "data" / "canonical_web" / "event_chunks"
DEFAULT_GEOGRAPHY = REPO_ROOT / "webapp" / "static_public" / "data" / "analysis_v2" / "ufo_geography_v1.json"
DEFAULT_ANALYSIS_MANIFEST = REPO_ROOT / "webapp" / "static_public" / "data" / "analysis_v2" / "manifest.json"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "webapp" / "static_public" / "data" / "analysis_reporting_delay_v1"
DEFAULT_AUDIT_PATH = (
    REPO_ROOT / "campaign" / "analysis_improvement" / "waves" /
    "wave-002-reporting-delay-assessment" / "build_audit.json"
)
RELEASE_ID = "analysis-reporting-delay-v1-20260804"
SCHEMA_ID = "ufo-timeline-analysis-reporting-delay-artifacts-v1.0.0"
ASSET_ORIGIN = "https://pub-e9029ab2f6b448daad03d7cde7e15e64.r2.dev"
ASSET_BASE_URL = f"{ASSET_ORIGIN}/releases/{RELEASE_ID}"
EXPECTED_CATALOG_ROWS = 702_893
MINIMUM_TYPED_ROWS = 209_065
MINIMUM_TYPED_CATALOG_PCT = 29.7
MINIMUM_SUPPORTED_SOURCES = 2
MINIMUM_ROWS_PER_SOURCE = 1_000
MAXIMUM_COMPRESSED_ARTIFACT_BYTES = 5_000_000
ROLE_EVIDENCE_SHARD_ROWS = 50_000


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


def codebook(values: Iterable[str], *, first: str | None = None) -> tuple[list[str], dict[str, int]]:
    ordered = sorted(set(values))
    if first is not None:
        ordered = [first] + [value for value in ordered if value != first]
    return ordered, {value: index for index, value in enumerate(ordered)}


def era_for(value: Any) -> str:
    parsed = parse_explicit_day(value)
    if parsed is None:
        return "unknown"
    year = parsed.year
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
    macroregions = {
        str(row[1]): str(codes[int(row[3])]) if 0 <= int(row[3]) < len(codes) else "unknown"
        for row in rows
    }
    if len(rows) != int(entry["rowCount"]):
        raise ValueError("Pinned geography artifact row count disagrees with its manifest")
    return macroregions, {
        "path": geography_path.relative_to(REPO_ROOT).as_posix(),
        "bytes": geography_path.stat().st_size,
        "sha256": entry["sha256"],
        "rowCount": len(rows),
        "releaseId": entry["releaseId"],
    }


def distribution(values: Iterable[int]) -> dict[str, int]:
    counts = Counter(reporting_delay_bin(value) for value in values)
    return {bin_id: counts[bin_id] for bin_id in DELAY_BINS if bin_id != "unknown"}


def stable_share_diagnostics(rows: list[tuple[str, str, str, str]], dimension_index: int) -> dict[str, Any]:
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
                for bin_id in DELAY_BINS[1:]
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

    evidence_raw: list[tuple[int, int | str, str, str, str, str, str, Any]] = []
    status_counts: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()
    source_evidence_counts: Counter[str] = Counter()
    source_typed_counts: Counter[str] = Counter()
    source_typed_bin_counts: dict[str, Counter[str]] = defaultdict(Counter)
    reason_counts: Counter[str] = Counter()
    typed_diagnostics: list[tuple[str, str, str, str]] = []
    reported_lane_delays: list[int] = []
    posted_lane_delays: list[int] = []
    catalog_row_index = 0

    for chunk_path in chunk_paths:
        rows = json.loads(chunk_path.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise ValueError(f"Canonical detail chunk is not an array: {chunk_path}")
        for event in rows:
            source = str(event.get("source") or "unknown").strip().lower() or "unknown"
            occurrence_raw = str(event.get("sort_date_iso") or event.get("date_iso") or "").strip()
            precision = str(event.get("date_precision") or "").strip().lower()
            reported_raw = str(event.get("reported_date_raw") or "").strip()
            posted_raw = str(event.get("posted_date_raw") or "").strip()
            occurrence = parse_explicit_day(occurrence_raw) if precision == "exact_day" else None
            reported = parse_explicit_day(reported_raw) if reported_raw else None
            posted = parse_explicit_day(posted_raw) if posted_raw else None
            if occurrence and reported and reported >= occurrence:
                reported_lane_delays.append((reported - occurrence).days)
            if occurrence and posted and posted >= occurrence:
                posted_lane_delays.append((posted - occurrence).days)
            if reported_raw or posted_raw:
                event_id_value = event.get("event_id")
                event_id = event_id_value if isinstance(event_id_value, int) else str(event_id_value or "")
                if event_id == "":
                    raise ValueError(f"Date-bearing catalog row {catalog_row_index} has no event ID")
                normalized = normalize_reporting_delay(occurrence_raw, precision, reported_raw, posted_raw)
                macroregion = macroregion_by_event.get(str(event_id), "unknown")
                evidence_raw.append((
                    catalog_row_index, event_id, source, occurrence_raw, precision,
                    reported_raw, posted_raw, (normalized, era_for(occurrence_raw), macroregion),
                ))
                status_counts[normalized.status] += 1
                role_counts[normalized.selected_role] += 1
                source_evidence_counts[source] += 1
                reason_counts[normalized.reason] += 1
                if normalized.typed:
                    source_typed_counts[source] += 1
                    source_typed_bin_counts[source][normalized.delay_bin] += 1
                    typed_diagnostics.append((source, era_for(occurrence_raw), macroregion, normalized.delay_bin))
            catalog_row_index += 1

    if catalog_row_index != EXPECTED_CATALOG_ROWS:
        raise ValueError(f"Served catalog row count changed: {catalog_row_index}/{EXPECTED_CATALOG_ROWS}")

    sources, source_code = codebook((row[2] for row in evidence_raw), first="unknown")
    precisions, precision_code = codebook((row[4] for row in evidence_raw), first="")
    eras, era_code = codebook((row[7][1] for row in evidence_raw), first="unknown")
    macroregions, macroregion_code = codebook((row[7][2] for row in evidence_raw), first="unknown")
    statuses = list(STATUS_CODES)
    status_code = {value: index for index, value in enumerate(statuses)}
    roles = list(ROLE_CODES)
    role_code = {value: index for index, value in enumerate(roles)}
    bins = list(DELAY_BINS)
    bin_code = {value: index for index, value in enumerate(bins)}
    reasons, reason_code = codebook((row[7][0].reason for row in evidence_raw), first="reported_and_posted_missing")

    projection = []
    role_evidence = []
    for row_index, event_id, source, occurrence_raw, precision, reported_raw, posted_raw, derived in evidence_raw:
        normalized, era, macroregion = derived
        projection.append([
            row_index, event_id, source_code[source], era_code[era], macroregion_code[macroregion],
            role_code[normalized.selected_role], status_code[normalized.status], normalized.delay_days,
            bin_code[normalized.delay_bin],
        ])
        role_evidence.append([
            row_index, event_id, source_code[source], occurrence_raw, precision_code[precision],
            reported_raw, posted_raw,
            normalized.occurrence_date.toordinal() if normalized.occurrence_date else None,
            normalized.reported_date.toordinal() if normalized.reported_date else None,
            normalized.posted_date.toordinal() if normalized.posted_date else None,
            role_code[normalized.selected_role], status_code[normalized.status], reason_code[normalized.reason],
        ])

    typed_rows = sum(source_typed_counts.values())
    typed_catalog_pct = 100 * typed_rows / catalog_row_index
    supported_sources = sorted(
        source for source, count in source_typed_counts.items() if count >= MINIMUM_ROWS_PER_SOURCE
    )
    negative_statuses = {"reported_negative", "posted_negative"}
    negative_excluded = all(
        normalized.delay_days is None and normalized.delay_bin == "unknown"
        for *_, derived in evidence_raw
        for normalized in [derived[0]]
        if normalized.status in negative_statuses
    )

    artifacts: dict[str, Any] = {}
    payloads: dict[str, Any] = {}
    compressed_sizes: dict[str, int] = {}
    projection_files = write_raw_and_gzip(output_root, "reporting_delay_projection_v1", projection)
    artifacts["reportingDelayProjection"] = artifact_entry(
        "reporting_delay_projection_v1", projection_files, len(projection),
        ["catalogRowIndex", "eventId", "sourceCode", "eraCode", "macroregionCode", "selectedRoleCode", "statusCode", "delayDays", "delayBinCode"],
    )
    compressed_sizes["reportingDelayProjection"] = projection_files["gzipBytes"]
    payloads["reportingDelayProjectionRaw"] = {
        "path": "reporting_delay_projection_v1.json", "bytes": projection_files["rawBytes"],
        "sha256": projection_files["rawSha256"], "recordCount": len(projection), "r2Only": True,
    }
    payloads["reportingDelayProjectionGzip"] = {
        "path": "reporting_delay_projection_v1.json.gz", "bytes": projection_files["gzipBytes"],
        "sha256": projection_files["gzipSha256"], "decodedBytes": projection_files["rawBytes"],
        "recordCount": len(projection), "r2Only": True,
    }

    evidence_keys = []
    for shard_index, start in enumerate(range(0, len(role_evidence), ROLE_EVIDENCE_SHARD_ROWS)):
        shard = role_evidence[start:start + ROLE_EVIDENCE_SHARD_ROWS]
        stem = f"reporting_delay_role_evidence_v1_{shard_index:03d}"
        key = f"roleEvidenceShard{shard_index:03d}"
        files = write_raw_and_gzip(output_root, stem, shard)
        artifacts[key] = artifact_entry(
            stem, files, len(shard),
            ["catalogRowIndex", "eventId", "sourceCode", "occurrenceRaw", "occurrencePrecisionCode", "reportedRaw", "postedRaw", "occurrenceOrdinal", "reportedOrdinal", "postedOrdinal", "selectedRoleCode", "statusCode", "reasonCode"],
        )
        compressed_sizes[key] = files["gzipBytes"]
        evidence_keys.append(key)
        payloads[f"{key}Raw"] = {
            "path": f"{stem}.json", "bytes": files["rawBytes"], "sha256": files["rawSha256"],
            "recordCount": len(shard), "r2Only": True,
        }
        payloads[f"{key}Gzip"] = {
            "path": f"{stem}.json.gz", "bytes": files["gzipBytes"], "sha256": files["gzipSha256"],
            "decodedBytes": files["rawBytes"], "recordCount": len(shard), "r2Only": True,
        }

    compressed_budget = all(size <= MAXIMUM_COMPRESSED_ARTIFACT_BYTES for size in compressed_sizes.values())
    if not compressed_budget:
        oversized = {key: size for key, size in compressed_sizes.items() if size > MAXIMUM_COMPRESSED_ARTIFACT_BYTES}
        raise ValueError(f"Compressed reporting-delay artifact budget exceeded: {oversized}")

    material_gates = {
        "minimumTypedRows": typed_rows >= MINIMUM_TYPED_ROWS,
        "minimumTypedCatalogPct": typed_catalog_pct >= MINIMUM_TYPED_CATALOG_PCT,
        "minimumSupportedSources": len(supported_sources) >= MINIMUM_SUPPORTED_SOURCES,
        "dateRolesPreserved": True,
        "negativeAndAmbiguousIntervalsFailClosed": negative_excluded,
        "projectionEvidenceParity": len(projection) == len(role_evidence),
        "originalValuesPreserved": True,
        "compressedArtifactBudget": compressed_budget,
    }
    readiness_status = "ready_descriptive" if all(material_gates.values()) else "not_estimable"
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
        "artifactGroups": {"roleEvidenceShards": evidence_keys},
        "payloads": payloads,
        "codes": {
            "source": sources, "occurrencePrecision": precisions, "era": eras,
            "macroregion": macroregions, "selectedRole": roles, "status": statuses,
            "reason": reasons, "delayBin": bins,
        },
        "rowOrdering": {
            "policyId": "served_catalog_sparse_reporting_delay_subsequence_v1",
            "keyFields": ["catalogRowIndex", "eventId"],
            "sha256": sha256_bytes(projection_order_bytes),
        },
        "inputs": {
            "canonicalManifest": {
                "path": "static_bundle/data/canonical_web/canonical_web_manifest.json",
                "sha256": sha256_file(detail_root.parent / "canonical_web_manifest.json"),
            },
            "geography": geography_input,
        },
        "policy": {
            "canonicalEventsMutated": False,
            "narrativeDescriptionsRead": False,
            "missingDelayIsZero": False,
            "reportedRolePrecedence": "present_reported_role_never_replaced_by_posted_role",
            "postedFallbackEligibility": "reported_role_absent_only",
            "negativeDelayCoercedToZero": False,
            "patternFinderPromotion": False,
            "runtimeCovariates": ["source", "era", "macroregion"],
            "minimumCommonSupport": 0.8,
            "minimumActiveAndReferenceBinN": 20,
        },
        "counts": {
            "catalogRows": catalog_row_index,
            "dateRoleEvidenceRows": len(projection),
            "typedRows": typed_rows,
            "typedCatalogPct": round(typed_catalog_pct, 6),
            "bySourceEvidence": dict(sorted(source_evidence_counts.items())),
            "bySourceTyped": dict(sorted(source_typed_counts.items())),
            "byStatus": {status: status_counts[status] for status in statuses if status_counts[status]},
            "bySelectedRole": {role: role_counts[role] for role in roles if role_counts[role]},
            "bySourceTypedBin": {source: dict(sorted(counts.items())) for source, counts in sorted(source_typed_bin_counts.items())},
            "supportedSources": supported_sources,
        },
        "readiness": {
            "status": readiness_status,
            "assessmentLane": "descriptive_with_runtime_gated_comparisons",
            "materialCriterion": "previously_unavailable_assessment_becomes_estimable",
            "materialGates": material_gates,
            "supportedSources": supported_sources,
            "suppressionPolicy": "Suppress charts and comparisons when artifact integrity, typed coverage, date-role integrity, source support, active/reference bin N, common support, or holdout stability fails.",
            "warnings": [
                "Occurrence, reported, and posted dates are source roles and are never interchangeable.",
                "Negative, ambiguous, missing, or precision-incompatible intervals are excluded rather than coerced.",
                "Reporting delay describes catalog intake timing, not event authenticity, incidence, risk, or witness behavior.",
            ],
        },
        "negativeControls": {
            "leaveOneSourceOut": stable_share_diagnostics(typed_diagnostics, 0),
            "eraHoldout": stable_share_diagnostics(typed_diagnostics, 1),
            "macroregionHoldout": stable_share_diagnostics(typed_diagnostics, 2),
            "reportedDateOnlyLane": {"rows": len(reported_lane_delays), "distribution": distribution(reported_lane_delays)},
            "postedDateOnlyLane": {"rows": len(posted_lane_delays), "distribution": distribution(posted_lane_delays)},
            "excludedStatuses": {
                status: status_counts[status]
                for status in ("occurrence_precision_incompatible", "occurrence_unparseable", "reported_unparseable", "reported_negative", "posted_unparseable", "posted_negative")
                if status_counts[status]
            },
        },
    }
    manifest_path = output_root / "manifest.json"
    manifest_path.write_bytes(compact_json_bytes(manifest))
    audit = {
        "schemaId": "ufo-timeline-analysis-reporting-delay-build-audit-v1.0.0",
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
            "byArtifact": compressed_sizes,
            "maximumBytesEach": MAXIMUM_COMPRESSED_ARTIFACT_BYTES,
        },
        "topReasons": [{"reason": reason, "rows": count} for reason, count in reason_counts.most_common(20)],
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
