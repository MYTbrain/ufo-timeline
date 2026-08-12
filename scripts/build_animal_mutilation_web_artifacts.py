"""Build deterministic, lazy Animal Mutilation Reports web artifacts.

The source GeoJSON remains the scientific handoff. Pages receives only a small
manifest; the compact point index, searchable all-record catalog, and detail
chunks are immutable R2 payloads. The builder accepts either the handoff ZIP or
the GeoJSON directly so a corrected handoff can replace the development input
without changing the browser contract.
"""

from __future__ import annotations

import argparse
import calendar
import gzip
import hashlib
import json
import re
import shutil
import zipfile
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

try:
    from scripts.context_evidence_contract import (
        REPEATABLE_CONTEXT_FIELDS,
        distinct_reviewed_values,
    )
except ImportError:  # Direct script execution resolves sibling modules here.
    from context_evidence_contract import REPEATABLE_CONTEXT_FIELDS, distinct_reviewed_values


SCHEMA_VERSION = 1
DEFAULT_CHUNK_SIZE = 250
MAX_CHUNK_SIZE = 250
HANDOFF_GEOJSON = "data/animal_mutilations.geojson"
HANDOFF_MANIFEST = "handoff_manifest.json"
IMPORT_MANIFEST = "manifest/animal_mutilations_import_manifest.json"
RELEASE_ID_RE = re.compile(r"^animal-mutilations-v1-\d{8}$")
DATE_PRECISION_CODES = {
    "exact_day": 0,
    "month": 1,
    "year": 2,
    "range": 3,
    "approximate": 4,
    "unknown": 5,
}
COORDINATE_EVIDENCE_CODES = {
    "source_exact": 0, "source_bounded": 1, "source_regional": 2,
    "source_uncertainty_unknown": 3, "generalized_public_marker": 4,
    "locality_centroid": 5, "postal_centroid": 6, "approximate_map_pin": 7,
    "unmapped": 8,
}
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTEXT_EVIDENCE_ROOT = REPO_ROOT / "campaign" / "context_evidence" / "ledgers"
QUALIFYING_SOURCE_TIERS = {"primary", "official", "contemporaneous"}
INDEPENDENT_SOURCE_STATUSES = {"independent", "independent_primary", "independently_obtained"}
STRICT_REVIEW_STATES = {"source_reviewed", "human_reviewed"}
RESOLVED_DEDUP_STATUSES = {"resolved_cluster", "stable_unique"}
STRICT_CONFLICT_FIELDS = {
    "catalog_date", "coordinate_method", "coordinate_uncertainty_m", "death_interval",
    "dedup_cluster_id", "discovery_date", "duplicate_of_case_id", "formation_date",
    "investigation_date", "latitude", "location_label", "longitude", "occurrence_date",
    "photography_date", "publication_date", "report_date", "source_case_identifier",
}
NON_SITE_COORDINATE_METHODS = {
    "approximate_map_pin", "candidate_field_marker", "city_centroid", "locality_centroid",
    "postal_centroid", "public_generalization", "regional_centroid",
}
PRIVATE_TEXT_RE = re.compile(
    r"(?:\b(?:owner|contact|phone|email|access instructions?)\s*:|"
    r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b|"
    r"\b\d{1,6}\s+(?:[A-Za-z0-9.'-]+\s+){0,5}"
    r"(?:street|st|road|rd|lane|ln|drive|dr|avenue|ave|boulevard|blvd)\b)",
    flags=re.IGNORECASE,
)
PUBLIC_ROUTE_RE = re.compile(
    r"\b(?:US|U\.S\.|State|County)\s+(?:Route\s+)?\d{1,4}\b",
    flags=re.IGNORECASE,
)
HTML_TAG_RE = re.compile(r"<[^>]+>")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="Animal mutilation GeoJSON")
    source.add_argument("--handoff-zip", type=Path, help="Frozen Timeline handoff ZIP")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--asset-base-url", default="")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument(
        "--context-evidence-root", type=Path, default=DEFAULT_CONTEXT_EVIDENCE_ROOT,
        help="Optional directory containing the four reviewed context-evidence JSONL ledgers",
    )
    return parser.parse_args()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _ledger_path(root: Path, filename: str) -> Path:
    direct = root / filename
    nested = root / "ledgers" / filename
    return direct if direct.is_file() or not nested.is_file() else nested


def _jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            raise ValueError(f"Blank context-evidence JSONL line: {path}:{line_number}")
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid context-evidence JSONL: {path}:{line_number}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"Context-evidence row must be an object: {path}:{line_number}")
        rows.append(value)
    return rows


def load_context_evidence(root: Path | None, domain: str) -> tuple[dict[str, dict[str, Any]], dict[str, Any], set[str]]:
    """Load only quorum-reviewed assertions; unresolved critical evidence fails closed."""
    metadata: dict[str, Any] = {
        "status": "not_present", "activeAcceptedAssertions": 0, "caseCount": 0,
        "acceptedNewCaseCount": 0, "files": {},
    }
    if root is None:
        return {}, metadata, set()
    filenames = (
        "source_ledger.jsonl", "case_enrichment.jsonl", "case_review_decisions.jsonl",
        "research_queue.jsonl",
    )
    paths = {name: _ledger_path(root, name) for name in filenames}
    present = [name for name, path in paths.items() if path.is_file()]
    if not present:
        return {}, metadata, set()
    if len(present) != len(paths):
        missing = sorted(set(paths) - set(present))
        raise ValueError(f"Incomplete context-evidence ledger set: {missing}")
    metadata["status"] = "loaded"
    metadata["files"] = {
        name: {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        for name, path in sorted(paths.items())
    }

    source_rows = _jsonl_rows(paths["source_ledger.jsonl"])
    assertion_rows = _jsonl_rows(paths["case_enrichment.jsonl"])
    decision_rows = _jsonl_rows(paths["case_review_decisions.jsonl"])
    queue_rows = _jsonl_rows(paths["research_queue.jsonl"])
    sources: dict[str, dict[str, str]] = {}
    for row in source_rows:
        source_id = str(row.get("sourceId") or "")
        if not source_id or source_id in sources:
            raise ValueError(f"Missing or duplicate context source ID: {source_id!r}")
        sources[source_id] = {
            "familyId": str(row.get("sourceFamilyId") or ""),
            "sourceTier": str(row.get("sourceTier") or "lead_only").lower(),
            "independenceStatus": str(row.get("independenceStatus") or "unknown").lower(),
        }
        if not sources[source_id]["familyId"]:
            raise ValueError(f"Context source has no source family: {source_id}")

    assertions: dict[str, dict[str, Any]] = {}
    for row in assertion_rows:
        if row.get("domain") != domain:
            continue
        assertion_id = str(row.get("assertionId") or "")
        case_id = str(row.get("caseId") or "")
        evidence_hashes = [str(value).lower() for value in row.get("evidenceSha256") or []]
        source_ids = sorted({str(value) for value in row.get("sourceIds") or []})
        if not assertion_id or assertion_id in assertions or not case_id.startswith("ami_"):
            raise ValueError(f"Invalid animal context assertion identity: {assertion_id!r}")
        if not evidence_hashes or evidence_hashes != sorted(set(evidence_hashes)) or any(
            re.fullmatch(r"[0-9a-f]{64}", value) is None for value in evidence_hashes
        ):
            raise ValueError(f"Invalid frozen evidence hashes: {assertion_id}")
        if not source_ids or any(source_id not in sources for source_id in source_ids):
            raise ValueError(f"Unresolved context source reference: {assertion_id}")
        assertions[assertion_id] = {
            "assertionId": assertion_id, "caseId": case_id,
            "fieldName": str(row.get("fieldName") or ""), "value": row.get("value"),
            "sourceIds": source_ids, "evidenceSha256": evidence_hashes,
        }

    decisions: dict[str, dict[str, Any]] = {}
    superseded: set[str] = set()
    for row in decision_rows:
        assertion = assertions.get(str(row.get("assertionId") or ""))
        if assertion is None:
            continue
        decision_id = str(row.get("decisionId") or "")
        if not decision_id or decision_id in decisions:
            raise ValueError(f"Missing or duplicate context review decision: {decision_id!r}")
        if row.get("domain") != domain:
            raise ValueError(f"Context review decision domain mismatch: {decision_id}")
        case_id = str(row.get("caseId") or "")
        if case_id.startswith("animal_mutilation:"):
            case_id = case_id.split(":", 1)[1]
        if case_id != assertion["caseId"]:
            raise ValueError(f"Context review decision case mismatch: {decision_id}")
        if [str(value).lower() for value in row.get("frozenEvidenceSha256") or []] != assertion["evidenceSha256"]:
            raise ValueError(f"Context review decision evidence mismatch: {decision_id}")
        decisions[decision_id] = row
        superseded.update(str(value) for value in row.get("supersedesDecisionIds") or [])

    active_by_assertion: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for decision_id, row in decisions.items():
        if decision_id not in superseded:
            active_by_assertion[str(row.get("assertionId") or "")].append(row)
    reviewed_by_field: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    case_conflicts: dict[str, set[str]] = defaultdict(set)
    duplicate_targets: dict[str, set[str]] = defaultdict(set)
    for assertion_id, assertion in assertions.items():
        active = active_by_assertion.get(assertion_id, [])
        positive_outcomes = {"accepted", "duplicate"}
        human_rows = [row for row in active if (row.get("reviewer") or {}).get("reviewerType") == "human"]
        candidate_rows = human_rows or active
        outcomes = {str(row.get("outcome") or "") for row in candidate_rows}
        targets = {
            str(row.get("duplicateOfCaseId") or "") for row in candidate_rows
            if row.get("outcome") == "duplicate"
        } - {""}
        unanimous_positive = len(outcomes) == 1 and outcomes.issubset(positive_outcomes) and len(targets) <= 1
        agent_ids = {
            str((row.get("reviewer") or {}).get("reviewerId") or "") for row in active
            if (row.get("reviewer") or {}).get("reviewerType") == "agent"
        } - {""}
        review_state = (
            "human_reviewed" if human_rows and unanimous_positive
            else "source_reviewed" if not human_rows and len(agent_ids) >= 2 and unanimous_positive
            else None
        )
        if not review_state:
            if outcomes.intersection({"contradictory", "unresolved"}) and assertion["fieldName"] in STRICT_CONFLICT_FIELDS:
                case_conflicts[assertion["caseId"]].add(assertion["fieldName"])
            continue
        if outcomes == {"duplicate"}:
            if assertion["fieldName"] != "duplicate_of_case_id" or targets != {str(assertion["value"])}:
                raise ValueError(f"Invalid reviewed animal duplicate decision: {assertion_id}")
            duplicate_targets[assertion["caseId"]].update(targets)
        if review_state:
            reviewed_by_field[(assertion["caseId"], assertion["fieldName"])].append({
                **assertion, "reviewState": review_state,
            })

    cases: dict[str, dict[str, Any]] = {}
    for (case_id, field_name), values in sorted(reviewed_by_field.items()):
        field_values = distinct_reviewed_values(
            field_name,
            (value["value"] for value in values),
            canonical_json_bytes,
        )
        if field_name not in REPEATABLE_CONTEXT_FIELDS and len(field_values) != 1:
            raise ValueError(f"Conflicting accepted animal context values: {case_id}:{field_name}")
        item = cases.setdefault(case_id, {
            "fields": {}, "sourceIds": set(), "reviewStates": set(),
            "unresolvedConflictFields": set(),
        })
        source_ids = sorted({source_id for value in values for source_id in value["sourceIds"]})
        states = {value["reviewState"] for value in values}
        item["fields"][field_name] = {
            "value": field_values if field_name in REPEATABLE_CONTEXT_FIELDS else field_values[0],
            "sourceIds": source_ids,
            "reviewState": "human_reviewed" if "human_reviewed" in states else "source_reviewed",
        }
        item["sourceIds"].update(source_ids)
        item["reviewStates"].update(states)
        metadata["activeAcceptedAssertions"] += 1
    for case_id in set(case_conflicts) | set(duplicate_targets):
        item = cases.setdefault(case_id, {
            "fields": {}, "sourceIds": set(), "reviewStates": set(),
            "unresolvedConflictFields": set(),
        })
        item["unresolvedConflictFields"].update(case_conflicts[case_id])
        if duplicate_targets[case_id]:
            if len(duplicate_targets[case_id]) != 1:
                item["unresolvedConflictFields"].add("duplicate_of_case_id")
            else:
                item["duplicateOfCaseId"] = next(iter(duplicate_targets[case_id]))
    for item in cases.values():
        source_ids = sorted(item.pop("sourceIds"))
        states = item.pop("reviewStates")
        conflict_fields = sorted(item.pop("unresolvedConflictFields"))
        independent = [
            source_id for source_id in source_ids
            if sources[source_id]["independenceStatus"] in INDEPENDENT_SOURCE_STATUSES
        ]
        independent_families = sorted({sources[source_id]["familyId"] for source_id in independent})
        qualifying = [
            source_id for source_id in source_ids
            if sources[source_id]["sourceTier"] in QUALIFYING_SOURCE_TIERS
        ]
        item.update({
            "sourceIds": source_ids,
            "sourceFamilyIds": sorted({sources[source_id]["familyId"] for source_id in source_ids}),
            "reviewState": "human_reviewed" if "human_reviewed" in states else "source_reviewed" if states else "unreviewed",
            "independenceStatus": (
                "independent_source_families" if len(independent_families) >= 2 else
                "single_independent_source_family" if independent_families else
                "same_source_family" if source_ids and all(
                    sources[source_id]["independenceStatus"] == "same_family"
                    for source_id in source_ids
                ) else
                "unresolved" if source_ids else "no_sources"
            ),
            "sourceGateSatisfied": bool(qualifying) or len(independent_families) >= 2,
            "unresolvedConflict": bool(conflict_fields),
            "unresolvedConflictFields": conflict_fields,
        })

    accepted_new = {
        str(row.get("caseId")) for row in queue_rows
        if row.get("domain") == domain and row.get("caseClass") == "accepted_new_source"
        and row.get("status") in {"materially_upgraded", "strict_ready"}
        and str(row.get("caseId") or "").startswith("ami_")
    }
    metadata["caseCount"] = len(cases)
    metadata["acceptedNewCaseCount"] = len(accepted_new)
    return cases, metadata, accepted_new


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def _context_field(evidence: Mapping[str, Any], name: str) -> Mapping[str, Any] | None:
    value = (evidence.get("fields") or {}).get(name)
    return value if isinstance(value, Mapping) else None


def _context_value(evidence: Mapping[str, Any], name: str) -> Any:
    field = _context_field(evidence, name)
    return field.get("value") if field is not None else None


def _public_context_text(value: Any, *, field: str, case_id: str) -> str | None:
    if value is None:
        return None
    text = normalize_text(value)
    if any(ord(char) == 0 or ord(char) == 0x7F for char in text) or HTML_TAG_RE.search(text):
        raise ValueError(f"Unsafe reviewed public text in {field}: {case_id}")
    privacy_scan_text = PUBLIC_ROUTE_RE.sub("public route", text)
    if PRIVATE_TEXT_RE.search(privacy_scan_text):
        raise ValueError(f"Potential private contact or address text in {field}: {case_id}")
    return text or None


def _date_bounds(value: Any) -> tuple[str | None, str | None, str]:
    if isinstance(value, Mapping):
        start_value = (
            value.get("date") or value.get("dateIso") or value.get("dateStart")
            or value.get("startDate") or value.get("start")
        )
        end_value = value.get("dateEnd") or value.get("endDate") or value.get("end")
    else:
        start_value = value
        end_value = None
    start_text = str(start_value or "")
    end_text = str(end_value or "")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", start_text):
        date.fromisoformat(start_text)
        if end_text:
            date.fromisoformat(end_text)
            return start_text, end_text, "exact_day" if start_text == end_text else "range"
        return start_text, start_text, "exact_day"
    if re.fullmatch(r"\d{4}-\d{2}", start_text):
        year, month = map(int, start_text.split("-"))
        last_day = calendar.monthrange(year, month)[1]
        return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last_day:02d}", "month"
    if re.fullmatch(r"\d{4}", start_text):
        year = int(start_text)
        return f"{year:04d}-01-01", f"{year:04d}-12-31", "year"
    if not start_text:
        return None, None, "unknown"
    raise ValueError(f"Unsupported reviewed date value: {value!r}")


def _legacy_source_family_ids(detail: Mapping[str, Any]) -> list[str]:
    output: list[str] = []
    for ref in detail.get("sourceRefs") or []:
        if not isinstance(ref, Mapping):
            continue
        normalized = normalize_text(ref.get("sourceId"))
        if normalized:
            output.append(f"legacy_sf_{hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:16]}")
    return sorted(set(output))


def _selected_animal_date(detail: Mapping[str, Any], evidence: Mapping[str, Any]) -> tuple[str | None, str | None, str, str, bool]:
    for field_name in (
        "occurrence_date", "death_interval", "discovery_date", "report_date",
        "investigation_date", "publication_date",
    ):
        field = _context_field(evidence, field_name)
        if field is not None:
            start, end, precision = _date_bounds(field.get("value"))
            return start, end, precision, field_name, bool(field.get("sourceIds"))
    return (
        detail.get("dateStart"), detail.get("dateEnd") or detail.get("dateStart"),
        str(detail.get("datePrecision") or "unknown"),
        str(detail.get("dateRole") or "reported_unspecified"), False,
    )


def _animal_coordinate_state(detail: Mapping[str, Any], evidence: Mapping[str, Any]) -> dict[str, Any]:
    latitude = _context_field(evidence, "latitude")
    longitude = _context_field(evidence, "longitude")
    uncertainty = _context_field(evidence, "coordinate_uncertainty_m")
    method = _context_field(evidence, "coordinate_method")
    accepted_pair = latitude is not None and longitude is not None
    if (latitude is None) != (longitude is None):
        accepted_pair = False
    coordinates = detail.get("coordinates")
    lat_value = latitude.get("value") if accepted_pair else (
        coordinates[1] if isinstance(coordinates, list) and len(coordinates) >= 2 else None
    )
    lon_value = longitude.get("value") if accepted_pair else (
        coordinates[0] if isinstance(coordinates, list) and len(coordinates) >= 2 else None
    )
    lat = float(lat_value) if isinstance(lat_value, (int, float)) else None
    lon = float(lon_value) if isinstance(lon_value, (int, float)) else None
    if lat is not None and not -90 <= lat <= 90:
        raise ValueError(f"Reviewed animal latitude is out of range: {detail.get('id')}")
    if lon is not None and not -180 <= lon <= 180:
        raise ValueError(f"Reviewed animal longitude is out of range: {detail.get('id')}")
    uncertainty_value = uncertainty.get("value") if uncertainty is not None else detail.get("coordinateUncertaintyM")
    uncertainty_m = float(uncertainty_value) if isinstance(uncertainty_value, (int, float)) else None
    if uncertainty_m is not None and uncertainty_m < 0:
        raise ValueError(f"Reviewed animal coordinate uncertainty is negative: {detail.get('id')}")
    coordinate_method = normalize_text(method.get("value") if method is not None else detail.get("coordinateMethod"))
    has_coordinates = lat is not None and lon is not None
    if not coordinate_method:
        coordinate_method = "public_generalization" if has_coordinates else "unmapped"
    method_code = coordinate_method.casefold().replace(" ", "_")
    if not has_coordinates:
        evidence_class = "unmapped"
    elif method_code in NON_SITE_COORDINATE_METHODS:
        evidence_class = "generalized_public_marker" if method_code == "public_generalization" else method_code
    elif accepted_pair:
        if uncertainty_m is None:
            evidence_class = "source_uncertainty_unknown"
        elif uncertainty_m <= 100:
            evidence_class = "source_exact"
        elif uncertainty_m <= 1000:
            evidence_class = "source_bounded"
        else:
            evidence_class = "source_regional"
    else:
        evidence_class = "generalized_public_marker"
    provenance_complete = bool(
        accepted_pair and uncertainty is not None and method is not None
        and latitude.get("sourceIds") and longitude.get("sourceIds")
        and uncertainty.get("sourceIds") and method.get("sourceIds")
    )
    return {
        "coordinates": [round(lon, 7), round(lat, 7)] if has_coordinates else None,
        "coordinateEvidenceClass": evidence_class,
        "coordinateMethod": coordinate_method,
        "coordinateUncertaintyM": round(uncertainty_m, 3) if uncertainty_m is not None else None,
        "coordinateProvenanceComplete": provenance_complete,
    }


def apply_animal_context(detail: dict[str, Any], evidence: Mapping[str, Any]) -> dict[str, Any]:
    output = dict(detail)
    public_id = str(output["id"])
    case_id = public_id.split(":", 1)[1] if public_id.startswith("animal_mutilation:") else public_id
    for field_name, output_name in (
        ("public_title", "title"), ("public_summary", "summary"),
        ("location_label", "location"), ("source_case_identifier", "sourceCaseIdentifier"),
    ):
        value = _context_value(evidence, field_name)
        if value is not None:
            output[output_name] = _public_context_text(value, field=field_name, case_id=case_id)
    if _context_field(evidence, "primary_classification") is not None:
        output["primaryClassification"] = _public_context_text(
            _context_value(evidence, "primary_classification"), field="primary_classification", case_id=case_id,
        )
    if _context_field(evidence, "animal_species") is not None:
        species = _context_value(evidence, "animal_species")
        output["animalSpecies"] = species if isinstance(species, list) else [species]
    if _context_field(evidence, "victim_count") is not None:
        output["victimCount"] = _context_value(evidence, "victim_count")
    if _context_field(evidence, "injuries") is not None:
        output["injuries"] = _context_value(evidence, "injuries")

    start, end, precision, date_role, date_provenance = _selected_animal_date(output, evidence)
    coordinate = _animal_coordinate_state(output, evidence)
    output.update(coordinate)
    output["dateStart"] = start
    output["dateEnd"] = end
    output["datePrecision"] = precision
    output["dateRole"] = date_role
    output["locationPrecision"] = coordinate["coordinateEvidenceClass"]
    source_family_ids = list(evidence.get("sourceFamilyIds") or _legacy_source_family_ids(output))
    review_state = str(evidence.get("reviewState") or output.get("reviewState") or output.get("status") or "reported_unreviewed")
    independence_status = str(evidence.get("independenceStatus") or "unreviewed")
    duplicate_of = _context_value(evidence, "duplicate_of_case_id") or evidence.get("duplicateOfCaseId")
    dedup_cluster = _context_value(evidence, "dedup_cluster_id")
    dedup_status = "duplicate" if duplicate_of else "resolved_cluster" if dedup_cluster else "canonical_record_unreviewed"
    legal_restriction = _context_value(evidence, "legal_publication_restriction") is True
    exact_day = bool(start and start == end and precision == "exact_day")
    source_site = coordinate["coordinateEvidenceClass"] in {"source_exact", "source_bounded"}
    # Reviewed source-supported sites are public by policy. The builder still
    # rejects PII-prone ledger fields and suppresses documented legal exceptions.
    if source_site and review_state in STRICT_REVIEW_STATES:
        output["privacyLevel"] = "public_source_supported_site"
    reasons: list[str] = []
    if coordinate["coordinates"] is None:
        reasons.append("coordinates_unavailable")
    if not source_site:
        reasons.append("coordinate_not_source_supported_within_1km")
    if coordinate["coordinateUncertaintyM"] is None:
        reasons.append("coordinate_uncertainty_unavailable")
    elif coordinate["coordinateUncertaintyM"] > 1000:
        reasons.append("coordinate_uncertainty_exceeds_1km")
    if not coordinate["coordinateProvenanceComplete"]:
        reasons.append("coordinate_field_provenance_incomplete")
    if not exact_day:
        reasons.append("date_not_exact_occurrence_day")
    if date_role not in {
        "occurrence", "occurrence_date", "death", "death_date", "death_interval", "incident", "incident_date",
    }:
        reasons.append("date_role_not_occurrence_or_formation")
    if not date_provenance:
        reasons.append("date_field_provenance_incomplete")
    if review_state not in STRICT_REVIEW_STATES:
        reasons.append("record_not_source_or_human_reviewed")
    if not evidence.get("sourceGateSatisfied"):
        reasons.append("qualifying_or_independent_source_gate_not_met")
    if dedup_status not in RESOLVED_DEDUP_STATUSES:
        reasons.append("deduplication_not_resolved")
    if dedup_status == "duplicate":
        reasons.append("duplicate_record_excluded_from_analysis")
    if evidence.get("unresolvedConflict"):
        reasons.append("unresolved_identity_date_or_coordinate_conflict")
    if legal_restriction:
        reasons.append("legal_publication_restriction")
    reasons = sorted(set(reasons))
    if dedup_status == "duplicate":
        analysis_tier = "excluded"
    elif not reasons:
        analysis_tier = "animal_strict"
    elif exact_day and coordinate["coordinates"] is not None:
        analysis_tier = "animal_public_marker"
    else:
        analysis_tier = "excluded"
    output.update({
        "status": review_state,
        "reviewState": review_state,
        "sourceFamilyIds": source_family_ids,
        "independenceStatus": independence_status,
        "dedupStatus": dedup_status,
        "analysisTier": analysis_tier,
        "exclusionReasonCodes": reasons,
        "legalPublicationRestriction": legal_restriction,
        "causality": "not_asserted", "traceEligible": False, "traceRole": "context_only",
    })
    return output


def _validate_new_animal_case(case_id: str, evidence: Mapping[str, Any]) -> None:
    fields = set((evidence.get("fields") or {}).keys())
    missing: list[str] = []
    if "source_case_identifier" not in fields:
        missing.append("source_case_identifier")
    if not fields.intersection({"public_title", "public_summary"}):
        missing.append("public_title_or_summary")
    if "primary_classification" not in fields:
        missing.append("primary_classification")
    if not fields.intersection({
        "occurrence_date", "death_interval", "discovery_date", "report_date", "publication_date",
    }):
        missing.append("date_role")
    if not ("location_label" in fields or {"latitude", "longitude"}.issubset(fields)):
        missing.append("location_role")
    if not fields.intersection({"animal_species", "victim_count"}):
        missing.append("animal_species_or_victim_count")
    if missing:
        raise ValueError(f"Accepted new animal case {case_id} lacks reviewed bootstrap fields: {', '.join(missing)}")


def _new_animal_feature(case_id: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
    _validate_new_animal_case(case_id, evidence)
    title = _context_value(evidence, "public_title") or "Reviewed animal mutilation report"
    summary = _context_value(evidence, "public_summary") or "Reviewed animal mutilation incident."
    species = _context_value(evidence, "animal_species")
    common_names = species if isinstance(species, list) else [species] if species else []
    props = {
        "causality": "not_asserted", "claim_label": "Reported animal mutilation",
        "content_warning": "Animal-death descriptions may be disturbing.",
        "date_end": None, "date_precision": "unknown", "date_start": None,
        "evidence_excerpts": [], "evidence_status": "reported_unreviewed",
        "location_label": _context_value(evidence, "location_label"), "location_precision": "unknown",
        "normalized_common_names": common_names, "privacy_level": "public_generalized",
        "reported_taxon_keys": [], "source_incident_id": _context_value(evidence, "source_case_identifier"),
        "source_incident_sha256": None, "source_refs": [], "source_status": "reviewed_context_evidence",
        "species_groups": [], "status": "reported_unreviewed", "summary": summary, "title": title,
        "trace_eligible": False, "trace_role": "context_only",
        "uncertainty": {
            "coordinates_available": False, "date_precision": "unknown",
            "location_precision": "unknown", "privacy_generalized": True,
        },
    }
    return {
        "type": "Feature", "id": f"animal_mutilation:{case_id}", "geometry": None,
        "properties": props,
    }


def _leading_exclusions(records: list[Mapping[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    counts = Counter(
        reason for record in records for reason in record.get("exclusionReasonCodes") or []
    )
    return [{"reasonCode": reason, "count": count} for reason, count in sorted(
        counts.items(), key=lambda item: (-item[1], item[0])
    )[:limit]]


def validate_text(value: Any, *, field: str, record_id: str) -> str:
    text = str(value or "")
    if any(ord(char) == 0 or ord(char) == 0x7F for char in text):
        raise ValueError(f"Unsafe text in {field}: {record_id}")
    # The accepted v1 handoff contains a few legacy Windows-1252 punctuation
    # code points represented as C1 controls. Normalize those for safe display
    # without changing the source artifact or its lineage hash.
    return "".join(
        bytes([ord(char)]).decode("windows-1252") if 0x80 <= ord(char) <= 0x9F else char
        for char in text
    )


def iso_ordinal(value: Any) -> int | None:
    if not value:
        return None
    try:
        parsed = date.fromisoformat(str(value))
    except ValueError as error:
        raise ValueError(f"Invalid ISO date: {value}") from error
    return (parsed - date(1970, 1, 1)).days


def safe_source_url(value: Any, *, record_id: str) -> str | None:
    if not value:
        return None
    url = str(value)
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError(f"Invalid public source URL: {record_id}")
    host = parsed.hostname.casefold().strip(".")
    if host in {"localhost", "0.0.0.0", "::1"} or host.endswith(".local") or host.startswith("127."):
        raise ValueError(f"Non-public source URL: {record_id}")
    return url


def load_source(input_path: Path | None, handoff_zip: Path | None) -> tuple[dict[str, Any], dict[str, Any]]:
    if handoff_zip:
        handoff_zip_bytes = handoff_zip.read_bytes()
        with zipfile.ZipFile(handoff_zip) as archive:
            handoff_manifest_bytes = archive.read(HANDOFF_MANIFEST)
            handoff = json.loads(handoff_manifest_bytes)
            for path, expected in handoff.get("files", {}).items():
                payload = archive.read(path)
                if len(payload) != int(expected["size_bytes"]) or sha256_bytes(payload) != expected["sha256"]:
                    raise ValueError(f"Handoff payload failed integrity validation: {path}")
            geojson_bytes = archive.read(HANDOFF_GEOJSON)
            source_meta = {
                "handoffSchema": handoff.get("schema_version"),
                "handoffZipSha256": sha256_bytes(handoff_zip_bytes),
                "handoffManifestSha256": sha256_bytes(handoff_manifest_bytes),
                "releaseCommit": handoff.get("release_commit"),
                "seedSourceCommit": handoff.get("seed_source_commit"),
                "sourceGeojsonSha256": sha256_bytes(geojson_bytes),
                "coordinateAudit": {"available": False, "requiredForRelease": True},
            }
            audit_entries = [
                (path, metadata) for path, metadata in handoff.get("files", {}).items()
                if path.startswith("data/")
                if "coordinate" in str(metadata.get("role") or "").casefold()
                and "audit" in str(metadata.get("role") or "").casefold()
            ]
            if len(audit_entries) > 1:
                raise ValueError("Handoff declares multiple coordinate-audit artifacts")
            if audit_entries:
                audit_path, audit_metadata = audit_entries[0]
                audit_bytes = archive.read(audit_path)
                if audit_path.endswith(".jsonl"):
                    rows = [json.loads(line) for line in audit_bytes.splitlines() if line.strip()]
                else:
                    audit_payload = json.loads(audit_bytes)
                    rows = audit_payload.get("records", audit_payload.get("rows", audit_payload))
                    if not isinstance(rows, list):
                        raise ValueError("Coordinate audit does not expose a deterministic record array")
                source_meta["coordinateAudit"] = {
                    "available": True,
                    "requiredForRelease": True,
                    "path": audit_path,
                    "sha256": audit_metadata["sha256"],
                    "recordCount": len(rows),
                }
            if IMPORT_MANIFEST in archive.namelist():
                import_manifest = json.loads(archive.read(IMPORT_MANIFEST))
                source_meta["adapterVersion"] = import_manifest.get("adapter_version")
                if source_meta["coordinateAudit"]["available"]:
                    coordinate_normalization = import_manifest.get("coordinate_normalization") or {}
                    coordinate_audit_identity = coordinate_normalization.get("audit") or {}
                    audit_path = str(source_meta["coordinateAudit"]["path"])
                    audit_name = Path(audit_path).name
                    output = (import_manifest.get("outputs") or {}).get(audit_name)
                    expected_records = (import_manifest.get("counts") or {}).get("coordinate_audit_records")
                    if not output or output.get("sha256") != source_meta["coordinateAudit"]["sha256"]:
                        raise ValueError("Coordinate audit identity is not reconciled in the import manifest")
                    if int(output.get("records", -1)) != int(source_meta["coordinateAudit"]["recordCount"]):
                        raise ValueError("Coordinate audit output count is inconsistent")
                    if expected_records is None or int(expected_records) != int(source_meta["coordinateAudit"]["recordCount"]):
                        raise ValueError("Coordinate audit aggregate count is inconsistent")
                    import_audit_path = str(coordinate_audit_identity.get("path") or "")
                    if not import_audit_path or Path(import_audit_path).name != audit_name:
                        raise ValueError("Coordinate audit path is not authoritative in the import manifest")
                    if coordinate_audit_identity.get("sha256") != source_meta["coordinateAudit"]["sha256"]:
                        raise ValueError("Coordinate audit hash is not authoritative in the import manifest")
                    if int(coordinate_audit_identity.get("record_count", -1)) != int(
                        source_meta["coordinateAudit"]["recordCount"]
                    ):
                        raise ValueError("Coordinate audit record count is not authoritative in the import manifest")
                    correction_count = coordinate_normalization.get("correction_count")
                    semantic_validation_passed = coordinate_normalization.get("semantic_validation_passed")
                    if int(correction_count if correction_count is not None else -1) != 479:
                        raise ValueError("Coordinate audit correction_count must be exactly 479")
                    if semantic_validation_passed is not True:
                        raise ValueError("Coordinate audit semantic validation must pass")
                    handoff_coordinate_normalization = handoff.get("coordinate_normalization") or {}
                    handoff_audit_identity = handoff_coordinate_normalization.get("audit") or {}
                    if (
                        handoff_coordinate_normalization.get("correction_count") != correction_count
                        or handoff_coordinate_normalization.get("semantic_validation_passed") is not True
                        or handoff_audit_identity.get("path") != audit_path
                        or handoff_audit_identity.get("sha256") != source_meta["coordinateAudit"]["sha256"]
                        or int(handoff_audit_identity.get("record_count", -1))
                        != int(source_meta["coordinateAudit"]["recordCount"])
                    ):
                        raise ValueError("Coordinate audit identity is not mirrored by the handoff manifest")
                    source_meta["coordinateAudit"].update({
                        "correctionCount": int(correction_count),
                        "semanticValidationPassed": True,
                        "semanticGeographyValidation": coordinate_normalization.get(
                            "semantic_geography_validation"
                        ),
                        "schemaVersion": (import_manifest.get("schema_versions") or {}).get(
                            "coordinate_normalization_audit"
                        ),
                        "schemaSha256": (import_manifest.get("schema_sha256") or {}).get(
                            "coordinate_normalization_audit"
                        ),
                        "longitudeSignCorrected": int(
                            (import_manifest.get("counts") or {}).get("longitude_sign_corrected", -1)
                        ),
                        "coordinatesUnchanged": int(
                            (import_manifest.get("counts") or {}).get("coordinates_unchanged", -1)
                        ),
                        "coordinatesSuppressedAmbiguous": int(
                            (import_manifest.get("counts") or {}).get("coordinates_suppressed_ambiguous", -1)
                        ),
                        "noPublicGeometry": int(
                            (import_manifest.get("counts") or {}).get("no_public_geometry", -1)
                        ),
                    })
                    if not source_meta["coordinateAudit"]["schemaVersion"] or not source_meta["coordinateAudit"]["schemaSha256"]:
                        raise ValueError("Coordinate audit schema identity is missing")
            return json.loads(geojson_bytes), source_meta
    assert input_path is not None
    raw = input_path.read_bytes()
    return json.loads(raw), {"sourceGeojsonSha256": sha256_bytes(raw)}


def validate_collection(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("type") != "FeatureCollection" or payload.get("name") != "Animal Mutilation Reports":
        raise ValueError("Input is not the Animal Mutilation Reports FeatureCollection")
    if payload.get("trace_eligible") is not False or payload.get("trace_role") != "context_only":
        raise ValueError("Animal records must remain context-only and trace-ineligible")
    if payload.get("causality") != "not_asserted":
        raise ValueError("Animal causality must remain not_asserted")
    if payload.get("relationships") not in (None, []):
        raise ValueError("Animal context layer must not contain relationships")
    features = payload.get("features")
    if not isinstance(features, list):
        raise ValueError("FeatureCollection.features must be an array")
    ids = [str(feature.get("id") or "") for feature in features]
    if any(not record_id.startswith("animal_mutilation:") for record_id in ids):
        raise ValueError("Every feature requires a stable animal_mutilation ID")
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate animal mutilation IDs")
    if any((feature.get("properties") or {}).get("location_precision") != "unknown" for feature in features):
        raise ValueError("Every animal report must retain location_precision=unknown")
    return sorted(features, key=lambda feature: str(feature["id"]))


def write_json_gzip(path: Path, value: Any) -> dict[str, Any]:
    raw = canonical_json_bytes(value)
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(compressed)
    return {
        "path": path.as_posix(),
        "bytes": len(compressed),
        "decodedBytes": len(raw),
        "sha256": sha256_bytes(compressed),
        "r2Only": True,
    }


def write_json(path: Path, value: Any) -> dict[str, Any]:
    raw = canonical_json_bytes(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {"bytes": len(raw), "sha256": sha256_bytes(raw)}


def compact_source_ref(ref: dict[str, Any], record_id: str) -> dict[str, Any]:
    return {
        "sourceId": validate_text(ref.get("source_id"), field="source_id", record_id=record_id),
        "sourceHash": validate_text(ref.get("source_hash"), field="source_hash", record_id=record_id),
        "locator": validate_text(ref.get("locator"), field="locator", record_id=record_id),
        "url": safe_source_url(ref.get("url"), record_id=record_id),
    }


def compact_detail(feature: dict[str, Any]) -> dict[str, Any]:
    record_id = str(feature["id"])
    props = feature.get("properties") or {}
    geometry = feature.get("geometry")
    coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
    if coordinates is not None and (
        geometry.get("type") != "Point" or len(coordinates) != 2 or
        not all(isinstance(value, (int, float)) for value in coordinates)
    ):
        raise ValueError(f"Invalid public geometry: {record_id}")
    for field, expected in {
        "status": "reported_unreviewed",
        "evidence_status": "reported_unreviewed",
        "causality": "not_asserted",
        "trace_role": "context_only",
    }.items():
        if props.get(field) != expected:
            raise ValueError(f"Invalid {field}: {record_id}")
    if props.get("trace_eligible") is not False:
        raise ValueError(f"Trace eligibility is forbidden: {record_id}")
    uncertainty = props.get("uncertainty") or {}
    if bool(uncertainty.get("coordinates_available")) != bool(coordinates is not None):
        raise ValueError(f"Coordinate uncertainty mismatch: {record_id}")
    excerpts = [
        validate_text(item, field="evidence_excerpts", record_id=record_id)
        for item in props.get("evidence_excerpts") or []
    ]
    return {
        "id": record_id,
        "title": validate_text(props.get("title"), field="title", record_id=record_id),
        "claimLabel": validate_text(props.get("claim_label"), field="claim_label", record_id=record_id),
        "summary": validate_text(props.get("summary"), field="summary", record_id=record_id),
        "contentWarning": validate_text(props.get("content_warning"), field="content_warning", record_id=record_id),
        "dateStart": props.get("date_start"),
        "dateEnd": props.get("date_end"),
        "datePrecision": props.get("date_precision"),
        "location": validate_text(props.get("location_label"), field="location_label", record_id=record_id) or None,
        "locationPrecision": props.get("location_precision"),
        "coordinates": [round(float(coordinates[0]), 6), round(float(coordinates[1]), 6)] if coordinates else None,
        "commonNames": list(props.get("normalized_common_names") or []),
        "taxonKeys": list(props.get("reported_taxon_keys") or []),
        "speciesGroups": list(props.get("species_groups") or []),
        "evidenceExcerpts": excerpts,
        "status": props.get("status"),
        "evidenceStatus": props.get("evidence_status"),
        "sourceStatus": props.get("source_status"),
        "privacyLevel": props.get("privacy_level"),
        "uncertainty": uncertainty,
        "sourceIncidentId": props.get("source_incident_id"),
        "sourceIncidentSha256": props.get("source_incident_sha256"),
        "sourceRefs": [compact_source_ref(ref, record_id) for ref in props.get("source_refs") or []],
        "causality": "not_asserted",
        "traceEligible": False,
        "traceRole": "context_only",
    }


def search_text(detail: dict[str, Any]) -> str:
    pieces: list[str] = [
        detail["id"], detail.get("title") or "", detail.get("summary") or "", detail.get("location") or "",
        detail.get("sourceIncidentId") or "",
    ]
    # The catalog is a bounded discovery index, not a second copy of full
    # report excerpts. Detailed public excerpts remain lazy in detail chunks.
    for key in ("commonNames", "taxonKeys", "speciesGroups"):
        pieces.extend(str(item) for item in detail.get(key) or [])
    pieces.extend(str(ref.get("sourceId") or "") for ref in detail.get("sourceRefs") or [])
    return normalize_text(" ".join(pieces)).casefold()


def build(
    *, input_path: Path | None, handoff_zip: Path | None, output_root: Path,
    release_id: str, asset_base_url: str, chunk_size: int,
    context_evidence_root: Path | None = DEFAULT_CONTEXT_EVIDENCE_ROOT,
) -> dict[str, Any]:
    if not RELEASE_ID_RE.fullmatch(release_id):
        raise ValueError("release-id must match animal-mutilations-v1-YYYYMMDD")
    if chunk_size < 1 or chunk_size > MAX_CHUNK_SIZE:
        raise ValueError("detail chunk size must be between 1 and 250")
    immutable_prefix = f"releases/{release_id}/"
    normalized_base = asset_base_url.rstrip("/") + "/" if asset_base_url else ""
    if normalized_base and not urlparse(normalized_base).scheme in {"http", "https"}:
        raise ValueError("asset-base-url must be an HTTP(S) URL")
    if normalized_base and not urlparse(normalized_base).path.endswith("/" + immutable_prefix):
        raise ValueError("asset-base-url must end with the immutable release prefix")

    payload, source_meta = load_source(input_path, handoff_zip)
    features = validate_collection(payload)
    source_details = [compact_detail(feature) for feature in features]
    source_contract_counts = {
        "records": len(source_details),
        "mapped": sum(detail["coordinates"] is not None for detail in source_details),
        "unmapped": sum(detail["coordinates"] is None for detail in source_details),
        "mappedPositions": len({tuple(detail["coordinates"]) for detail in source_details if detail["coordinates"]}),
        "exactCoordinates": sum(detail["locationPrecision"] != "unknown" for detail in source_details),
        "dated": sum(detail["dateStart"] is not None for detail in source_details),
        "undated": sum(detail["dateStart"] is None for detail in source_details),
        "exactDay": sum(detail["datePrecision"] == "exact_day" for detail in source_details),
        "mappedExactDay": sum(
            detail["coordinates"] is not None and detail["datePrecision"] == "exact_day"
            for detail in source_details
        ),
        "reportedUnreviewed": sum(detail["status"] == "reported_unreviewed" for detail in source_details),
        "detailChunks": (len(source_details) + chunk_size - 1) // chunk_size,
    }
    if handoff_zip is not None:
        locked_counts = {
            "records": 1177,
            "mapped": 518,
            "unmapped": 659,
            "mappedPositions": 400,
            "exactCoordinates": 0,
            "dated": 1149,
            "undated": 28,
            "exactDay": 921,
            "mappedExactDay": 339,
            "reportedUnreviewed": 1177,
            "detailChunks": 5,
        }
        if chunk_size != 250 or source_contract_counts != locked_counts:
            raise ValueError(
                "Frozen Animal Mutilation Reports contract mismatch: "
                f"expected {locked_counts}, observed {source_contract_counts} with chunk_size={chunk_size}"
            )

    context_evidence, context_metadata, accepted_new_cases = load_context_evidence(
        context_evidence_root, "animal_mutilation"
    )
    source_case_ids = {
        detail["id"].split(":", 1)[1] if detail["id"].startswith("animal_mutilation:") else detail["id"]
        for detail in source_details
    }
    unknown_context_cases = sorted(set(context_evidence) - source_case_ids - accepted_new_cases)
    if unknown_context_cases:
        raise ValueError(
            "Reviewed animal assertions target cases absent from the source export and not accepted_new_source: "
            + ", ".join(unknown_context_cases[:5])
        )
    missing_new_evidence = sorted(accepted_new_cases - set(context_evidence))
    if missing_new_evidence:
        raise ValueError("Accepted new animal cases have no reviewed evidence: " + ", ".join(missing_new_evidence[:5]))
    all_details = source_details + [
        compact_detail(_new_animal_feature(case_id, context_evidence[case_id]))
        for case_id in sorted(accepted_new_cases - source_case_ids)
    ]
    details: list[dict[str, Any]] = []
    legally_restricted_suppressed = 0
    for detail in all_details:
        case_id = detail["id"].split(":", 1)[1] if detail["id"].startswith("animal_mutilation:") else detail["id"]
        reviewed = apply_animal_context(detail, context_evidence.get(case_id, {}))
        if reviewed["legalPublicationRestriction"]:
            legally_restricted_suppressed += 1
            continue
        details.append(reviewed)
    details.sort(key=lambda detail: detail["id"])
    species_groups = sorted({group for detail in details for group in detail["speciesGroups"]})
    species_codes = {name: index for index, name in enumerate(species_groups)}
    detail_chunk_by_id = {detail["id"]: index // chunk_size for index, detail in enumerate(details)}

    computed_counts = {
        "records": len(details),
        "sourceRecords": len(source_details),
        "acceptedNewCases": len(accepted_new_cases - source_case_ids),
        "legallyRestrictedSuppressed": legally_restricted_suppressed,
        "mapped": sum(detail["coordinates"] is not None for detail in details),
        "unmapped": sum(detail["coordinates"] is None for detail in details),
        "mappedPositions": len({tuple(detail["coordinates"]) for detail in details if detail["coordinates"]}),
        "exactCoordinates": sum(detail["coordinateEvidenceClass"] == "source_exact" for detail in details),
        "boundedCoordinates": sum(detail["coordinateEvidenceClass"] == "source_bounded" for detail in details),
        "dated": sum(detail["dateStart"] is not None for detail in details),
        "undated": sum(detail["dateStart"] is None for detail in details),
        "exactDay": sum(detail["datePrecision"] == "exact_day" for detail in details),
        "mappedExactDay": sum(
            detail["coordinates"] is not None and detail["datePrecision"] == "exact_day"
            for detail in details
        ),
        "reportedUnreviewed": sum(detail["status"] == "reported_unreviewed" for detail in details),
        "detailChunks": (len(details) + chunk_size - 1) // chunk_size,
    }

    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    detail_files: list[dict[str, Any]] = []
    for start in range(0, len(details), chunk_size):
        chunk = details[start:start + chunk_size]
        relative = Path("details") / f"chunk_{start // chunk_size:03d}.json.gz"
        info = write_json_gzip(output_root / relative, {item["id"]: item for item in chunk})
        info["path"] = relative.as_posix()
        info["recordCount"] = len(chunk)
        detail_files.append(info)

    point_rows: list[list[Any]] = []
    catalog_rows: list[list[Any]] = []
    for detail in details:
        start_ordinal = iso_ordinal(detail["dateStart"])
        end_ordinal = iso_ordinal(detail["dateEnd"])
        precision_code = DATE_PRECISION_CODES.get(str(detail["datePrecision"]), DATE_PRECISION_CODES["unknown"])
        group_codes = [species_codes[name] for name in detail["speciesGroups"]]
        chunk_number = detail_chunk_by_id[detail["id"]]
        coordinates = detail["coordinates"]
        if coordinates:
            point_rows.append([
                detail["id"], coordinates[1], coordinates[0], start_ordinal, end_ordinal,
                precision_code, group_codes, chunk_number,
                COORDINATE_EVIDENCE_CODES.get(
                    detail["coordinateEvidenceClass"], COORDINATE_EVIDENCE_CODES["unmapped"]
                ),
                detail["coordinateUncertaintyM"],
            ])
        catalog_rows.append([
            detail["id"], detail["title"], detail["summary"], detail["location"],
            detail["dateStart"], detail["dateEnd"], precision_code, group_codes,
            bool(coordinates), chunk_number, detail["status"], detail["commonNames"], search_text(detail),
            detail["analysisTier"], detail["reviewState"], detail["coordinateEvidenceClass"],
            detail["coordinateUncertaintyM"],
        ])

    points_info = write_json_gzip(output_root / "points.json.gz", point_rows)
    points_info["path"] = "points.json.gz"
    points_info["recordCount"] = len(point_rows)
    points_info["rowSchema"] = [
        "id", "lat", "lon", "startOrdinal", "endOrdinal", "datePrecisionCode",
        "speciesGroupCodes", "detailChunk", "coordinateEvidenceClassCode", "coordinateUncertaintyM",
    ]
    catalog_info = write_json_gzip(output_root / "catalog.json.gz", catalog_rows)
    catalog_info["path"] = "catalog.json.gz"
    catalog_info["recordCount"] = len(catalog_rows)
    catalog_info["rowSchema"] = [
        "id", "title", "summary", "location", "dateStart", "dateEnd", "datePrecisionCode",
        "speciesGroupCodes", "mapped", "detailChunk", "status", "commonNames", "searchText",
        "analysisTier", "reviewState", "coordinateEvidenceClass", "coordinateUncertaintyM",
    ]
    r2_paths = sorted([points_info["path"], catalog_info["path"], *(item["path"] for item in detail_files)])
    manifest = {
        "schemaVersion": SCHEMA_VERSION,
        "releaseId": release_id,
        "assetBaseUrl": normalized_base,
        "layerName": "Animal Mutilation Reports",
        "sourceSchema": payload.get("schema_version"),
        "source": source_meta,
        "contextEvidence": context_metadata,
        "counts": computed_counts,
        "points": points_info,
        "catalog": catalog_info,
        "details": {
            "basePath": "details/",
            "chunkPattern": "chunk_{chunk:03d}.json.gz",
            "chunkSize": chunk_size,
            "files": detail_files,
        },
        "codes": {
            "datePrecision": DATE_PRECISION_CODES, "speciesGroup": species_codes,
            "coordinateEvidenceClass": COORDINATE_EVIDENCE_CODES,
        },
        "readiness": {
            "activeInventory": len(details),
            "mapped": computed_counts["mapped"],
            "sensitivityReady": sum(detail["analysisTier"] == "animal_public_marker" for detail in details),
            "strictReady": sum(detail["analysisTier"] == "animal_strict" for detail in details),
            "leadingExclusionReasons": _leading_exclusions(details),
        },
        "delivery": {
            "pagesFiles": ["manifest.json"],
            "immutablePrefix": immutable_prefix,
            "r2OnlyPaths": r2_paths,
        },
        "policy": {
            "causality": "not_asserted",
            "traceEligible": False,
            "traceRole": "context_only",
            "relationshipsEligible": False,
            "craftColorEligible": False,
            "playbackEligible": False,
            "status": "mixed" if any(detail["reviewState"] in STRICT_REVIEW_STATES for detail in details) else "reported_unreviewed",
            "exactCoordinateEligible": any(
                detail["coordinateEvidenceClass"] == "source_exact" for detail in details
            ),
            "contentWarningRequired": True,
            "legalRestrictionSuppressesPublicRecord": True,
            "sourceSupportedPrivatePropertyCoordinatesPublished": True,
            "privateOwnerAndAccessDetailsPublished": False,
        },
    }
    write_json(output_root / "manifest.json", manifest)
    return manifest


def main() -> None:
    args = parse_args()
    manifest = build(
        input_path=args.input,
        handoff_zip=args.handoff_zip,
        output_root=args.output,
        release_id=args.release_id,
        asset_base_url=args.asset_base_url,
        chunk_size=args.chunk_size,
        context_evidence_root=args.context_evidence_root,
    )
    print(json.dumps({"output": str(args.output), "releaseId": manifest["releaseId"], "counts": manifest["counts"]}, indent=2))


if __name__ == "__main__":
    main()
