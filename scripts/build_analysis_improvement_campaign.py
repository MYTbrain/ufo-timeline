from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DETAIL_ROOT = REPO_ROOT / "static_bundle" / "data" / "canonical_web" / "event_chunks"
DEFAULT_APP_CONFIG = REPO_ROOT / "static_bundle" / "data" / "app_config.json"
DEFAULT_ANALYSIS_ROOT = REPO_ROOT / "webapp" / "static_public" / "data" / "analysis_v2"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "campaign" / "analysis_improvement"

CAMPAIGN_SCHEMA = "ufo-timeline-analysis-improvement-campaign-v1.0.0"
CAMPAIGN_ID = "analysis-improvement-campaign-20260804"
BASELINE_COMMIT = "f64c7ab3b3a5efb297500365d883f0c5a26d2c25"
BASELINE_TAG = "analysis-v2.2.0-production"
PRODUCTION_DEPLOYMENT_ID = "e8008f72-d98e-4f15-86f1-8d3d48ad2054"
PRODUCTION_URL = "https://e8008f72.ufo-timeline.pages.dev"
CANONICAL_URL = "https://ufo-timeline.pages.dev"
PREVIEW_DEPLOYMENT_ID = "ba79a53a-8701-4063-be0b-a2c0a168e948"
ROLLBACK_DEPLOYMENT_ID = "688e156d-1a4e-44d5-8a60-de1d6554ee18"
FROZEN_BUNDLE = "cloudflare_bundle_r2_analysis-v2-2-dashboard-r4-frozen_20260803"
FROZEN_TREE_SHA256 = "a1058d1d108d290a874edac4940aa1e58093adcf702d6be92aeb09f04f5e72b0"
SOURCE_TREE_SHA256 = "c39c540bdbed3e691f63019a570ae5fab4d8493647533a2c9c19319f0f8791d5"
R2_TREE_SHA256 = "5cfd7f9e3158facdfc4d3de42fd388093fb8dfa2d617a9608a1d04127f4563a2"
R2_BASE_URL = (
    "https://pub-e9029ab2f6b448daad03d7cde7e15e64.r2.dev/"
    "releases/coordinated-reliability-v152-20260731"
)

DATE_RE = re.compile(r"(?P<year>\d{4})[-/](?P<month>\d{1,2})[-/](?P<day>\d{1,2})")
KEY_NORMALIZER = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class FieldDefinition:
    field_id: str
    label: str
    coverage_kind: str
    source_path: str
    inference_note: str


FIELDS = (
    FieldDefinition(
        "coordinate_evidence",
        "Coordinate evidence class",
        "normalized_field_present",
        "summary.coordinate_source",
        "Presence does not imply exact or source-provided coordinates.",
    ),
    FieldDefinition(
        "source_coordinates",
        "Source-provided coordinates",
        "qualified_value",
        "summary.coordinate_source",
        "Generalized and geocoded coordinates remain excluded from kilometer inference.",
    ),
    FieldDefinition(
        "coordinate_precision",
        "Coordinate precision class",
        "normalized_field_present",
        "summary.location_precision",
        "Precision labels are evidence classes, not error radii.",
    ),
    FieldDefinition(
        "coordinate_pile_review_state",
        "Full-catalog coordinate-pile review state",
        "normalized_field_present",
        "not_available_in_canonical_event",
        "Zero means the role is absent from the full catalog, not that no piles exist.",
    ),
    FieldDefinition(
        "occurrence_date_role",
        "Occurrence-date role",
        "raw_field_present",
        "detail.date_raw",
        "Raw occurrence text is preserved; precision is assessed separately.",
    ),
    FieldDefinition(
        "exact_date",
        "Exact occurrence date",
        "qualified_value",
        "summary.date_precision",
        "Only exact_day is eligible for exact-day inference.",
    ),
    FieldDefinition(
        "time_of_day_raw",
        "Raw time of day",
        "raw_field_present",
        "summary.time_raw",
        "Raw clock text may lack timezone semantics.",
    ),
    FieldDefinition(
        "time_of_day_normalized",
        "Normalized time of day",
        "qualified_value",
        "summary.time_sort_kind,time_sort_confidence",
        "Only non-unknown values with medium/high confidence count.",
    ),
    FieldDefinition(
        "reported_date_role",
        "Reported or posted date role",
        "raw_field_present",
        "detail.reported_date_raw,posted_date_raw",
        "Reported and posted dates remain distinct in detailed records.",
    ),
    FieldDefinition(
        "reporting_delay_estimable",
        "Non-negative reporting delay",
        "qualified_value",
        "detail.sort_date_iso,reported_date_raw,posted_date_raw",
        "Uses reported date first, then posted date; ambiguous/negative intervals fail closed.",
    ),
    FieldDefinition(
        "craft_normalized",
        "Normalized craft/configuration class",
        "normalized_field_present",
        "summary.craft_type_inferred",
        "Configuration and multiple-object classes are not treated as single craft.",
    ),
    FieldDefinition(
        "craft_confidence",
        "Medium/high craft confidence",
        "qualified_value",
        "summary.craft_type_confidence",
        "Low-confidence classifications are descriptive only.",
    ),
    FieldDefinition(
        "craft_classification_source",
        "Craft classification source",
        "normalized_field_present",
        "summary.craft_type_source",
        "The source field records classification provenance, not authenticity.",
    ),
    FieldDefinition(
        "same_day_suitability",
        "Medium/strong same-day suitability",
        "qualified_value",
        "summary.same_day_match_strength",
        "Weak/unknown values are excluded from exact-day association work.",
    ),
    FieldDefinition(
        "duplicate_lineage",
        "Canonical duplicate lineage",
        "normalized_field_present",
        "detail.canonical_input_ids",
        "Lineage presence does not establish source independence.",
    ),
    FieldDefinition(
        "publisher_lineage",
        "Publisher/source-file lineage",
        "normalized_field_present",
        "detail.source_provenance",
        "Publisher identity may still be shared across nominal source names.",
    ),
    FieldDefinition(
        "independent_source_identity",
        "Nominal source identity",
        "normalized_field_present",
        "detail.source",
        "Nominal source identity is not automatically an independent holdout.",
    ),
    FieldDefinition(
        "country_assignment",
        "Country/macroregion assignment",
        "derived_field_present",
        "analysis_v2.ufo_geography_v1",
        "Ocean and ambiguous boundary rows remain unknown.",
    ),
    FieldDefinition(
        "administrative_region",
        "Administrative-region assignment",
        "normalized_field_present",
        "not_available_in_canonical_event",
        "Zero is an explicit readiness gap.",
    ),
    FieldDefinition(
        "boundary_assignment_provenance",
        "Boundary-assignment provenance",
        "derived_field_present",
        "analysis_v2.ufo_geography_v1",
        "Coverage is limited to mapped packed-point rows.",
    ),
    FieldDefinition(
        "duration_raw",
        "Raw duration",
        "raw_field_present",
        "detail.duration_raw",
        "Raw duration text is not yet a normalized numeric interval.",
    ),
    FieldDefinition(
        "witness_count_raw",
        "Raw witness-count value",
        "raw_explicit_value",
        "detail.raw_fields",
        "Blank or absent values are unknown, never zero witnesses.",
    ),
    FieldDefinition(
        "sound_raw",
        "Explicit sound/noise value",
        "raw_explicit_value",
        "detail.raw_fields",
        "Coverage records explicit values only; absence is not evidence of silence.",
    ),
    FieldDefinition(
        "color_raw",
        "Explicit color value",
        "raw_explicit_value",
        "detail.raw_fields",
        "Coverage records explicit values only.",
    ),
    FieldDefinition(
        "light_positive_mention",
        "Explicit positive light/luminosity mention",
        "raw_positive_mention",
        "detail.raw_fields",
        "This is positive-mention coverage and cannot estimate absence.",
    ),
    FieldDefinition(
        "behavior_raw",
        "Explicit motion/maneuver/hover/speed value",
        "raw_explicit_value",
        "detail.raw_fields",
        "Bearing and viewer-direction roles are intentionally excluded.",
    ),
    FieldDefinition(
        "evidence_raw",
        "Explicit evidence/photo/video/radar/trace value",
        "raw_explicit_value",
        "detail.raw_fields",
        "Raw mentions require a typed evidence taxonomy before inference.",
    ),
)

FIELD_IDS = tuple(field.field_id for field in FIELDS)

RAW_KEY_PATTERNS = {
    "witness_count_raw": ("witness", "observer", "numberofpeople", "noofpeople"),
    "sound_raw": ("sound", "noise", "audible"),
    "color_raw": ("color", "colour"),
    "behavior_raw": ("behavior", "behaviour", "maneuver", "manoeuvre", "motion", "movement", "speed", "hover"),
    "evidence_raw": ("evidence", "photo", "photograph", "video", "film", "radar", "physicaltrace"),
}

LIGHT_KEY_PATTERNS = ("light", "luminos", "bright", "glow")
LIGHT_VALUE_RE = re.compile(r"\b(light(?:s|ed|ing)?|luminous|luminosity|bright(?:ness)?|glow(?:ing)?)\b", re.I)


def compact_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(compact_json_bytes(value))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip()) and value.strip().lower() not in {"unknown", "n/a", "none", "null"}
    if isinstance(value, (list, tuple, dict)):
        return bool(value)
    return True


def normalized_key(value: str) -> str:
    return KEY_NORMALIZER.sub("", str(value).lower())


def raw_value_present(raw_fields: Any, patterns: Iterable[str]) -> bool:
    if not isinstance(raw_fields, dict):
        return False
    patterns = tuple(patterns)
    for key, value in raw_fields.items():
        normalized = normalized_key(key)
        if any(pattern in normalized for pattern in patterns) and is_nonempty(value):
            return True
    return False


def light_positive_mention(raw_fields: Any) -> bool:
    if not isinstance(raw_fields, dict):
        return False
    for key, value in raw_fields.items():
        if not is_nonempty(value):
            continue
        key_normalized = normalized_key(key)
        if any(pattern in key_normalized for pattern in LIGHT_KEY_PATTERNS):
            return True
        if "characteristic" in key_normalized and LIGHT_VALUE_RE.search(str(value)):
            return True
    return False


def parse_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    match = DATE_RE.search(value)
    if not match:
        return None
    try:
        return date(int(match.group("year")), int(match.group("month")), int(match.group("day")))
    except ValueError:
        return None


def reporting_delay_estimable(event: dict[str, Any]) -> bool:
    if event.get("date_precision") != "exact_day":
        return False
    occurred = parse_date(event.get("sort_date_iso"))
    reported = parse_date(event.get("reported_date_raw")) or parse_date(event.get("posted_date_raw"))
    return bool(occurred and reported and reported >= occurred)


def era_for(value: Any) -> str:
    parsed = parse_date(value)
    if not parsed:
        return "unknown"
    year = parsed.year
    if year < 1945:
        return "pre_1945"
    if year <= 1959:
        return "1945_1959"
    if year <= 1979:
        return "1960_1979"
    if year <= 1999:
        return "1980_1999"
    if year <= 2009:
        return "2000_2009"
    if year <= 2019:
        return "2010_2019"
    return "2020_plus"


def load_geography(analysis_root: Path) -> tuple[dict[int, str], dict[str, Any]]:
    manifest_path = analysis_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    codes = manifest["codes"]["ufoGeography"]["macroregion"]
    rows = json.loads((analysis_root / "ufo_geography_v1.json").read_text(encoding="utf-8"))
    geography: dict[int, str] = {}
    for row in rows:
        geography[int(row[1])] = str(codes[int(row[3])])
    return geography, manifest


def field_flags(event: dict[str, Any], region: str, has_geography: bool) -> dict[str, bool]:
    raw_fields = event.get("raw_fields")
    provenance = event.get("source_provenance")
    return {
        "coordinate_evidence": is_nonempty(event.get("coordinate_source")),
        "source_coordinates": event.get("coordinate_source") == "raw_latlong",
        "coordinate_precision": is_nonempty(event.get("location_precision")),
        "coordinate_pile_review_state": False,
        "occurrence_date_role": is_nonempty(event.get("date_raw")),
        "exact_date": event.get("date_precision") == "exact_day",
        "time_of_day_raw": is_nonempty(event.get("time_raw")),
        "time_of_day_normalized": (
            event.get("time_sort_kind") not in {None, "", "unknown"}
            and event.get("time_sort_confidence") in {"medium", "high"}
        ),
        "reported_date_role": is_nonempty(event.get("reported_date_raw")) or is_nonempty(event.get("posted_date_raw")),
        "reporting_delay_estimable": reporting_delay_estimable(event),
        "craft_normalized": is_nonempty(event.get("craft_type_inferred")),
        "craft_confidence": event.get("craft_type_confidence") in {"medium", "high"},
        "craft_classification_source": is_nonempty(event.get("craft_type_source")),
        "same_day_suitability": event.get("same_day_match_strength") in {"medium", "strong"},
        "duplicate_lineage": is_nonempty(event.get("canonical_input_ids")),
        "publisher_lineage": bool(
            isinstance(provenance, list)
            and any(is_nonempty(item.get("source_name")) and is_nonempty(item.get("source_file")) for item in provenance if isinstance(item, dict))
        ),
        "independent_source_identity": is_nonempty(event.get("source")),
        "country_assignment": has_geography and region != "unknown",
        "administrative_region": False,
        "boundary_assignment_provenance": has_geography,
        "duration_raw": is_nonempty(event.get("duration_raw")),
        "witness_count_raw": raw_value_present(raw_fields, RAW_KEY_PATTERNS["witness_count_raw"]),
        "sound_raw": raw_value_present(raw_fields, RAW_KEY_PATTERNS["sound_raw"]),
        "color_raw": raw_value_present(raw_fields, RAW_KEY_PATTERNS["color_raw"]),
        "light_positive_mention": light_positive_mention(raw_fields),
        "behavior_raw": raw_value_present(raw_fields, RAW_KEY_PATTERNS["behavior_raw"]),
        "evidence_raw": raw_value_present(raw_fields, RAW_KEY_PATTERNS["evidence_raw"]),
    }


def coverage_record(covered: int, total: int) -> dict[str, Any]:
    return {
        "coveredRows": covered,
        "missingRows": total - covered,
        "coveragePct": round((100.0 * covered / total), 6) if total else 0.0,
    }


def scan_catalog(detail_root: Path, geography: dict[int, str], expected_rows: int) -> dict[str, Any]:
    overall = Counter()
    overall_total = 0
    group_totals: Counter[tuple[str, str, str]] = Counter()
    group_fields: dict[tuple[str, str, str], Counter[str]] = defaultdict(Counter)
    source_totals: Counter[str] = Counter()
    source_fields: dict[str, Counter[str]] = defaultdict(Counter)

    chunks = sorted(detail_root.glob("chunk_*.json"))
    if not chunks:
        raise FileNotFoundError(f"No canonical detail chunks found under {detail_root}")
    for chunk in chunks:
        events = json.loads(chunk.read_text(encoding="utf-8"))
        for event in events:
            event_id = int(event["event_id"])
            source = str(event.get("source") or "unknown")
            era = era_for(event.get("sort_date_iso"))
            has_geography = event_id in geography
            region = geography.get(event_id, "unknown")
            group = (source, era, region)
            flags = field_flags(event, region, has_geography)
            overall_total += 1
            group_totals[group] += 1
            source_totals[source] += 1
            for field_id, covered in flags.items():
                if covered:
                    overall[field_id] += 1
                    group_fields[group][field_id] += 1
                    source_fields[source][field_id] += 1
    if overall_total != expected_rows:
        raise ValueError(f"Canonical row count drifted: scanned {overall_total}, expected {expected_rows}")

    groups = []
    for source, era, region in sorted(group_totals):
        total = group_totals[(source, era, region)]
        groups.append(
            {
                "source": source,
                "era": era,
                "region": region,
                "rows": total,
                "fields": {
                    field_id: coverage_record(group_fields[(source, era, region)][field_id], total)
                    for field_id in FIELD_IDS
                },
            }
        )
    sources = {
        source: {
            "rows": source_totals[source],
            "fields": {
                field_id: coverage_record(source_fields[source][field_id], source_totals[source])
                for field_id in FIELD_IDS
            },
        }
        for source in sorted(source_totals)
    }
    return {
        "rowCount": overall_total,
        "chunkCount": len(chunks),
        "overall": {field_id: coverage_record(overall[field_id], overall_total) for field_id in FIELD_IDS},
        "sources": sources,
        "groups": groups,
    }


def independence_score(scan: dict[str, Any], field_id: str) -> tuple[int, list[str]]:
    supported = [
        source
        for source, payload in scan["sources"].items()
        if payload["fields"][field_id]["coveredRows"] >= 1000
    ]
    score = min(5, len(supported))
    return score, supported


def coverage_gain_score(coverage_pct: float) -> int:
    if coverage_pct >= 50:
        return 5
    if coverage_pct >= 25:
        return 4
    if coverage_pct >= 10:
        return 3
    if coverage_pct >= 1:
        return 2
    if coverage_pct > 0:
        return 1
    return 0


def make_backlog(scan: dict[str, Any]) -> dict[str, Any]:
    definitions = [
        ("duration_assessment", "duration_raw", 5, 4, 2, 2, "Makes the priority duration assessment estimable."),
        ("reporting_delay_assessment", "reporting_delay_estimable", 5, 4, 3, 2, "Makes reporting-delay analysis estimable with explicit date roles."),
        ("witness_count_assessment", "witness_count_raw", 4, 3, 3, 2, "Adds a typed witness-count lane without treating missing as zero."),
        ("time_of_day_assessment", "time_of_day_normalized", 4, 4, 3, 3, "Adds local-time readiness before solar or twilight context."),
        ("country_admin_provenance", "administrative_region", 4, 5, 3, 2, "Adds pinned administrative-region and boundary provenance."),
        ("coordinate_evidence_repair", "source_coordinates", 5, 5, 5, 4, "Repairs coordinate evidence while preserving generalized markers."),
        ("typed_observation_assessments", "light_positive_mention", 4, 2, 4, 3, "Separates sound, color, light, behavior, and evidence roles."),
    ]
    candidates = []
    for candidate_id, field_id, severity, confidence, effort, risk, outcome in definitions:
        coverage = scan["overall"][field_id]
        data_gain = coverage_gain_score(float(coverage["coveragePct"]))
        independence, supported_sources = independence_score(scan, field_id)
        score = 3 * severity + 3 * data_gain + 2 * confidence + independence - effort - 2 * risk
        blockers = []
        if field_id in {"duration_raw", "witness_count_raw", "light_positive_mention"}:
            blockers.append("typed_normalization_and_original_value_preservation_required")
        if field_id == "reporting_delay_estimable":
            blockers.append("reported_vs_posted_date_roles_must_remain_separate")
        if field_id == "administrative_region":
            blockers.append("pinned_boundary_release_and_assignment_provenance_required")
        candidates.append(
            {
                "candidateId": candidate_id,
                "primaryField": field_id,
                "score": score,
                "scoreComponents": {
                    "userFacingSeverity": severity,
                    "dataOrInferenceGain": data_gain,
                    "scientificConfidence": confidence,
                    "sourceIndependence": independence,
                    "performanceGain": 0,
                    "effort": effort,
                    "regressionRisk": risk,
                    "formula": "3*severity+3*gain+2*confidence+independence+performance-effort-2*risk",
                },
                "baselineCoverage": coverage,
                "independentlySupportedSources": supported_sources,
                "expectedOutcome": outcome,
                "materialCriterion": "previously_unavailable_assessment_becomes_estimable",
                "blockingIssues": blockers,
                "status": "candidate",
            }
        )
    candidates.extend(
        [
            {
                "candidateId": "analysis_projection_encoding",
                "primaryField": None,
                "score": 20,
                "scoreComponents": {
                    "userFacingSeverity": 3,
                    "dataOrInferenceGain": 0,
                    "scientificConfidence": 5,
                    "sourceIndependence": 0,
                    "performanceGain": 5,
                    "effort": 3,
                    "regressionRisk": 3,
                    "formula": "3*severity+3*gain+2*confidence+independence+performance-effort-2*risk",
                },
                "baselineCoverage": None,
                "independentlySupportedSources": [],
                "expectedOutcome": "Reduce analysis startup transfer or cold spatial latency by at least 10%.",
                "materialCriterion": "performance_metric_improves_at_least_10_percent",
                "blockingIssues": ["fresh_constrained_profile_baseline_required"],
                "status": "candidate",
            },
            {
                "candidateId": "dashboard_density_refinement",
                "primaryField": None,
                "score": 14,
                "scoreComponents": {
                    "userFacingSeverity": 3,
                    "dataOrInferenceGain": 0,
                    "scientificConfidence": 5,
                    "sourceIndependence": 0,
                    "performanceGain": 2,
                    "effort": 2,
                    "regressionRisk": 2,
                    "formula": "3*severity+3*gain+2*confidence+independence+performance-effort-2*risk",
                },
                "baselineCoverage": None,
                "independentlySupportedSources": [],
                "expectedOutcome": "Reduce a measured dashboard height or task-completion burden by at least 10%.",
                "materialCriterion": "dashboard_height_or_core_task_improves_at_least_10_percent",
                "blockingIssues": ["fresh_visual_density_and_task_baseline_required"],
                "status": "candidate",
            },
        ]
    )
    candidates.sort(key=lambda item: (-int(item["score"]), str(item["candidateId"])))
    for rank, candidate in enumerate(candidates, start=1):
        candidate["rank"] = rank
    return {
        "schemaId": "ufo-timeline-analysis-ranked-backlog-v1.0.0",
        "campaignId": CAMPAIGN_ID,
        "rankingPolicy": {
            "componentRange": [0, 5],
            "higherIsBetter": [
                "userFacingSeverity",
                "dataOrInferenceGain",
                "scientificConfidence",
                "sourceIndependence",
                "performanceGain",
            ],
            "lowerIsBetter": ["effort", "regressionRisk"],
            "onePrimaryObjectivePerWave": True,
        },
        "candidates": candidates,
    }


def module_status(field: dict[str, Any], supported_sources: list[str]) -> str:
    if field["coveredRows"] >= 1000 and len(supported_sources) >= 2:
        return "candidate_audit_ready"
    return "not_ready"


def make_module_registry(scan: dict[str, Any]) -> dict[str, Any]:
    candidates = []
    for module_id, field_id, minimum_pct in (
        ("duration", "duration_raw", 5.0),
        ("witness_count", "witness_count_raw", 5.0),
        ("reporting_delay", "reporting_delay_estimable", 5.0),
        ("time_of_day", "time_of_day_normalized", 5.0),
        ("sound", "sound_raw", 5.0),
        ("color", "color_raw", 5.0),
        ("light", "light_positive_mention", 5.0),
        ("behavior", "behavior_raw", 5.0),
        ("evidence", "evidence_raw", 5.0),
    ):
        supported_score, supported_sources = independence_score(scan, field_id)
        coverage = scan["overall"][field_id]
        candidates.append(
            {
                "moduleId": module_id,
                "version": "0.1.0-candidate",
                "status": module_status(coverage, supported_sources),
                "requiredFields": [field_id, "exact_date", "independent_source_identity"],
                "minimumCoveragePct": minimum_pct,
                "baselineCoverage": coverage,
                "supportedSources": supported_sources,
                "sourceIndependenceScore": supported_score,
                "estimators": ["descriptive_distribution", "source_era_region_standardized_comparison"],
                "negativeControls": ["source_composition_holdout", "era_holdout", "region_holdout"],
                "uncertaintyTreatment": "typed_parser_uncertainty_and_bootstrap_interval_required",
                "suppressionPolicy": "suppress_inference_until_common_support_and_typed_normalization_pass",
            }
        )
    return {
        "schemaId": "ufo-timeline-analysis-module-readiness-v1.0.0",
        "campaignId": CAMPAIGN_ID,
        "productionModules": [
            {"moduleId": "overview", "version": "2.2.0", "status": "production_ready"},
            {"moduleId": "time", "version": "2.2.0", "status": "production_ready"},
            {"moduleId": "craft", "version": "2.2.0", "status": "production_ready"},
            {"moduleId": "geography", "version": "2.2.0", "status": "production_ready"},
            {"moduleId": "spatial_evidence", "version": "2.2.0", "status": "production_ready"},
            {"moduleId": "sources_quality", "version": "2.2.0", "status": "production_ready"},
            {"moduleId": "context", "version": "2.2.0", "status": "production_ready"},
        ],
        "candidateModules": candidates,
        "forbiddenClaims": [
            "chronology_connector_relationship",
            "trace_styling_inference",
            "inferred_travel",
            "authenticity",
            "incidence",
            "risk",
            "causal_facility_interpretation",
        ],
    }


def make_provenance_ledger(scan: dict[str, Any], input_hashes: dict[str, str]) -> dict[str, Any]:
    fields = []
    for definition in FIELDS:
        fields.append(
            {
                "fieldId": definition.field_id,
                "coverageKind": definition.coverage_kind,
                "sourcePath": definition.source_path,
                "coverage": scan["overall"][definition.field_id],
                "originalValuePreserved": True,
                "externalAcquisitionUsed": False,
                "rightsStatus": "derived_from_existing_private_canonical_corpus_no_new_redistribution",
                "inferenceNote": definition.inference_note,
            }
        )
    return {
        "schemaId": "ufo-timeline-analysis-field-provenance-ledger-v1.0.0",
        "campaignId": CAMPAIGN_ID,
        "inputHashes": input_hashes,
        "fields": fields,
        "unresolvedIssues": [
            {
                "issueId": "publisher_independence_not_fully_adjudicated",
                "kind": "scientific",
                "status": "open_fail_closed",
                "effect": "nominal sources cannot automatically be promoted to independent holdouts",
            },
            {
                "issueId": "external_bulk_dataset_rights_not_reviewed",
                "kind": "rights",
                "status": "not_authorized",
                "effect": "no whole-dataset external ingestion is allowed",
            },
            {
                "issueId": "raw_pages_are_private_inputs",
                "kind": "rights",
                "status": "enforced",
                "effect": "raw fetched pages must remain outside deployed artifacts",
            },
        ],
    }


def make_baseline_metrics(scan: dict[str, Any], manifest: dict[str, Any], app_config: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaId": "ufo-timeline-analysis-before-after-metrics-v1.0.0",
        "campaignId": CAMPAIGN_ID,
        "measurementId": "production-v2.2-baseline",
        "catalog": {
            "normalizedRows": int(app_config["normalizedCount"]),
            "mappedRows": int(app_config["mappedCount"]),
            "detailChunks": scan["chunkCount"],
            "fieldCoverageMatrixGroups": len(scan["groups"]),
        },
        "statisticalReadiness": {
            "estimatorVersion": manifest["estimatorVersion"],
            "analysisReleaseId": manifest["releaseId"],
            "productionModules": 7,
            "candidateFieldCoverage": {field_id: scan["overall"][field_id] for field_id in FIELD_IDS},
        },
        "performance": {
            "measurementStatus": "fresh_campaign_browser_baseline_required",
            "inheritedReceipt": "docs/releases/UFO_TIMELINE_ANALYSIS_V2_EVIDENCE_LAB_RELEASE_2026-08-03.md",
            "firstUsefulRenderMs": {"min": 385.0, "max": 483.0, "freshness": "pre_v2.2_dashboard_revision"},
            "warmQuickCoreMs": {"value": 21.9, "freshness": "pre_v2.2_dashboard_revision"},
            "warmFullInferenceMs": {"value": 142.3, "freshness": "pre_v2.2_dashboard_revision"},
            "coldSpatialMs": {"value": 3066.5, "freshness": "pre_v2.2_dashboard_revision"},
            "switchingReloads": {"value": 0, "freshness": "pre_v2.2_dashboard_revision"},
        },
        "accessibility": {
            "measurementStatus": "fresh_campaign_browser_baseline_required",
            "requiredChecks": ["keyboard", "themes", "reduced_motion", "mobile_overflow", "direct_hashes", "exports"],
        },
        "visualDensity": {
            "dashboardCount": 7,
            "maximumOrdinaryDashboardViewports": 1.25,
            "measurementStatus": "fresh_campaign_browser_baseline_required",
        },
    }


def write_matrix_csv(path: Path, matrix: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["source", "era", "region", "rows", "field_id", "coverage_kind", "covered_rows", "missing_rows", "coverage_pct"])
        kinds = {field.field_id: field.coverage_kind for field in FIELDS}
        for group in matrix["groups"]:
            for field_id in FIELD_IDS:
                coverage = group["fields"][field_id]
                writer.writerow(
                    [
                        group["source"],
                        group["era"],
                        group["region"],
                        group["rows"],
                        field_id,
                        kinds[field_id],
                        coverage["coveredRows"],
                        coverage["missingRows"],
                        f"{coverage['coveragePct']:.6f}",
                    ]
                )


def build(args: argparse.Namespace) -> dict[str, Any]:
    detail_root = args.detail_root.resolve()
    analysis_root = args.analysis_root.resolve()
    output_root = args.output_root.resolve()
    completed_path = output_root / "state" / "completed_waves.json"
    if completed_path.exists() and not getattr(args, "force_reinitialize", False):
        completed_state = json.loads(completed_path.read_text(encoding="utf-8"))
        if completed_state.get("waves"):
            raise RuntimeError(
                "Refusing to reinitialize an active campaign with completed waves. "
                "Advance it through preregistrations and wave receipts, or pass "
                "--force-reinitialize only when intentionally rebuilding the campaign baseline."
            )
    app_config_path = args.app_config.resolve()
    app_config = json.loads(app_config_path.read_text(encoding="utf-8"))
    geography, manifest = load_geography(analysis_root)
    scan = scan_catalog(detail_root, geography, int(app_config["normalizedCount"]))

    input_hashes = {
        "appConfigSha256": sha256_file(app_config_path),
        "eventChunkManifestSha256": sha256_file(detail_root.parent / "event_chunk_manifest.json"),
        "analysisManifestSha256": sha256_file(analysis_root / "manifest.json"),
        "geographyArtifactSha256": sha256_file(analysis_root / "ufo_geography_v1.json"),
    }
    matrix = {
        "schemaId": "ufo-timeline-analysis-field-coverage-matrix-v1.0.0",
        "campaignId": CAMPAIGN_ID,
        "dimensions": ["source", "era", "region", "field"],
        "eraPolicy": ["pre_1945", "1945_1959", "1960_1979", "1980_1999", "2000_2009", "2010_2019", "2020_plus", "unknown"],
        "regionPolicy": "analysis_v2_pinned_macroregion_or_unknown",
        "fieldDefinitions": [definition.__dict__ for definition in FIELDS],
        **scan,
        "inputHashes": input_hashes,
    }
    metrics_dir = output_root / "metrics"
    state_dir = output_root / "state"
    preregistration_paths = sorted((output_root / "waves").glob("*/preregistration.json"))
    active_registration = (
        json.loads(preregistration_paths[-1].read_text(encoding="utf-8"))
        if preregistration_paths
        else None
    )
    write_json(metrics_dir / "field_coverage_matrix.json", matrix)
    write_matrix_csv(metrics_dir / "field_coverage_matrix.csv", matrix)

    backlog = make_backlog(scan)
    if active_registration:
        active_candidate_id = str(active_registration.get("candidateId") or "")
        for candidate in backlog["candidates"]:
            if candidate["candidateId"] == active_candidate_id:
                candidate["status"] = "in_progress"
    modules = make_module_registry(scan)
    provenance = make_provenance_ledger(scan, input_hashes)
    baseline_metrics = make_baseline_metrics(scan, manifest, app_config)
    completed = {
        "schemaId": "ufo-timeline-analysis-completed-wave-ledger-v1.0.0",
        "campaignId": CAMPAIGN_ID,
        "baselineSeal": {
            "commit": BASELINE_COMMIT,
            "tag": BASELINE_TAG,
            "productionDeploymentId": PRODUCTION_DEPLOYMENT_ID,
            "frozenTreeSha256": FROZEN_TREE_SHA256,
        },
        "waves": [],
    }
    write_json(state_dir / "ranked_backlog.json", backlog)
    write_json(state_dir / "module_readiness.json", modules)
    write_json(state_dir / "source_provenance_ledger.json", provenance)
    write_json(metrics_dir / "baseline_metrics.json", baseline_metrics)
    write_json(state_dir / "completed_waves.json", completed)

    tracked = [
        metrics_dir / "field_coverage_matrix.json",
        metrics_dir / "field_coverage_matrix.csv",
        metrics_dir / "baseline_metrics.json",
        state_dir / "ranked_backlog.json",
        state_dir / "module_readiness.json",
        state_dir / "source_provenance_ledger.json",
        state_dir / "completed_waves.json",
    ]
    tracked.extend(sorted((output_root / "contracts" / "v1").glob("*.json")))
    tracked.extend(sorted((output_root / "waves").glob("*/*.json")))
    active_wave = None
    if active_registration:
        active_wave = {
            "waveId": active_registration["waveId"],
            "candidateId": active_registration["candidateId"],
            "primaryObjective": active_registration["primaryObjective"],
            "status": "in_progress",
            "preregistration": preregistration_paths[-1].relative_to(REPO_ROOT).as_posix(),
        }
    current = {
        "schemaId": CAMPAIGN_SCHEMA,
        "campaignId": CAMPAIGN_ID,
        "status": "active" if active_wave else "initializing",
        "objective": "continuously_improve_analysis_data_first_with_evidence_gated_auto_deployments",
        "stopRule": "close_after_two_consecutive_bounded_frontier_passes_find_no_safe_material_gain",
        "currentProduction": {
            "analysisReleaseId": manifest["releaseId"],
            "estimatorVersion": manifest["estimatorVersion"],
            "baselineCommit": BASELINE_COMMIT,
            "baselineTag": BASELINE_TAG,
            "deploymentId": PRODUCTION_DEPLOYMENT_ID,
            "immutableUrl": PRODUCTION_URL,
            "canonicalUrl": CANONICAL_URL,
            "deploymentSourceLabel": "990dc33",
            "previewDeploymentId": PREVIEW_DEPLOYMENT_ID,
            "frozenBundle": FROZEN_BUNDLE,
            "frozenTreeSha256": FROZEN_TREE_SHA256,
            "sourceTreeSha256": SOURCE_TREE_SHA256,
            "r2TreeSha256": R2_TREE_SHA256,
            "r2BaseUrl": R2_BASE_URL,
        },
        "rollbackTarget": {
            "deploymentId": ROLLBACK_DEPLOYMENT_ID,
            "immutableUrl": f"https://{ROLLBACK_DEPLOYMENT_ID[:8]}.ufo-timeline.pages.dev",
            "releaseId": "context-layer-quick-toggles-v1-20260803",
            "reconstructionManifest": "reproduction/release.json",
            "rollbackInstruction": "redeploy the verified reproduction Pages package to branch main",
        },
        "activeWave": active_wave,
        "consecutiveNoGainFrontierPasses": 0,
        "nextCandidate": active_wave["candidateId"] if active_wave else backlog["candidates"][0]["candidateId"],
        "packageArtifacts": {
            path.relative_to(REPO_ROOT).as_posix(): {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
            for path in tracked
        },
    }
    write_json(state_dir / "current.json", current)
    return {
        "ok": True,
        "rowCount": scan["rowCount"],
        "groupCount": len(scan["groups"]),
        "sourceCount": len(scan["sources"]),
        "nextCandidate": current["nextCandidate"],
        "outputRoot": str(output_root),
        "currentStateSha256": sha256_file(state_dir / "current.json"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build deterministic state for the UFO Analysis improvement campaign.")
    parser.add_argument("--detail-root", type=Path, default=DEFAULT_DETAIL_ROOT)
    parser.add_argument("--app-config", type=Path, default=DEFAULT_APP_CONFIG)
    parser.add_argument("--analysis-root", type=Path, default=DEFAULT_ANALYSIS_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument(
        "--force-reinitialize",
        action="store_true",
        help="Intentionally replace completed-wave state while rebuilding the campaign baseline.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(build(parse_args()), indent=2, sort_keys=True))
