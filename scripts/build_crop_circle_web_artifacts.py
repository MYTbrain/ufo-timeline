"""Build lazy, rights-safe Crop Circle Timeline runtime artifacts.

The full interoperability export is a build input only. The browser receives a
compact point index after the layer is enabled and one small detail chunk after
a marker is opened. No source photograph pixels are packaged.
"""

from __future__ import annotations

import argparse
import calendar
import gzip
import hashlib
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import unquote, urlparse

try:
    from scripts.context_evidence_contract import (
        REPEATABLE_CONTEXT_FIELDS,
        distinct_reviewed_values,
    )
except ImportError:  # Direct script execution resolves sibling modules here.
    from context_evidence_contract import REPEATABLE_CONTEXT_FIELDS, distinct_reviewed_values


SCHEMA_VERSION = 1
DEFAULT_CHUNK_SIZE = 250
DATE_PRECISION_CODES = {
    "exact_day": 0,
    "day": 0,
    "month": 1,
    "year": 2,
    "range": 3,
    "approximate": 4,
    "unknown": 4,
}
COORDINATE_CODES = {"exact": 0, "candidate": 1, "locality": 2}
COORDINATE_EVIDENCE_CODES = {
    "source_exact": 0, "source_bounded": 1, "source_regional": 2,
    "source_uncertainty_unknown": 3, "candidate_field_marker": 4,
    "locality_centroid": 5, "postal_centroid": 6, "approximate_map_pin": 7,
    "unmapped": 8,
}
ENRICHMENT_DISPLAY_POLICY = "short_source_excerpt"
ENRICHMENT_DATE_ROLE = "catalog_unspecified"
ENRICHMENT_DATE_STATUSES = {"matched_all", "matched_available_years"}
ENRICHMENT_FAILURE_CODES = {"source_record_date_mismatch", "source_fetch_or_parse_failed"}
ICCRA_HOSTS = {"iccra.org", "www.iccra.org"}
YEAR_RE = re.compile(r"(?<!\d)((?:18|19|20)\d{2})(?!\d)")
URL_RE = re.compile(r"(?:https?://|www\.)\S+", flags=re.IGNORECASE)
HTML_TAG_RE = re.compile(r"<[^>]+>")
EXCERPT_METADATA_RE = re.compile(
    r"\b(?:crop\s*type|sources?|photos?|photographs?|pictured|diagrams?)\s*:",
    flags=re.IGNORECASE,
)
UNKNOWN_CROPS = {"", "?", "unknown", "unkown", "not known", "n/a", "na", "none"}
SAFE_CREDIT_MAX_WORDS = 12
SAFE_CREDIT_MAX_CHARS = 120
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTEXT_EVIDENCE_ROOT = REPO_ROOT / "campaign" / "context_evidence" / "ledgers"
QUALIFYING_SOURCE_TIERS = {"primary", "official", "contemporaneous"}
INDEPENDENT_SOURCE_STATUSES = {"independent", "independent_primary", "independently_obtained"}
STRICT_REVIEW_STATES = {"source_reviewed", "human_reviewed"}
RESOLVED_DEDUP_STATUSES = {"resolved_cluster", "stable_unique"}
STRICT_CONFLICT_FIELDS = {
    "catalog_date", "coordinate_method", "coordinate_uncertainty_m", "dedup_cluster_id",
    "discovery_date", "duplicate_of_case_id", "formation_date", "investigation_date",
    "latitude", "location_label", "longitude", "occurrence_date", "photography_date",
    "publication_date", "report_date", "source_case_identifier",
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--description-enrichment", type=Path)
    parser.add_argument(
        "--context-evidence-root", type=Path, default=DEFAULT_CONTEXT_EVIDENCE_ROOT,
        help="Optional directory containing the four reviewed context-evidence JSONL ledgers",
    )
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--asset-base-url", default="")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    return parser.parse_args()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


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
        if not assertion_id or assertion_id in assertions or not case_id.startswith("cc_"):
            raise ValueError(f"Invalid crop context assertion identity: {assertion_id!r}")
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
        if str(row.get("caseId") or "") != assertion["caseId"]:
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
                raise ValueError(f"Invalid reviewed crop duplicate decision: {assertion_id}")
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
            raise ValueError(f"Conflicting accepted crop context values: {case_id}:{field_name}")
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
        and str(row.get("caseId") or "").startswith("cc_")
    }
    metadata["caseCount"] = len(cases)
    metadata["acceptedNewCaseCount"] = len(accepted_new)
    return cases, metadata, accepted_new


def normalized_text(value: str) -> str:
    return " ".join(value.replace("\u00a0", " ").split()).strip()


def text_has_control_characters(value: str) -> bool:
    return any(
        ord(character) == 0x7F
        or 0x80 <= ord(character) <= 0x9F
        or (ord(character) < 0x20 and character not in "\t\n\r")
        for character in value
    )


def normalized_crop(value: str | None) -> str | None:
    cleaned = normalized_text(str(value or "")).strip(" .;,:")
    folded = cleaned.casefold()
    if folded in UNKNOWN_CROPS or folded.startswith("no crop type"):
        return None
    return folded or None


def unique_year(value: str | None) -> int | None:
    years = {int(match) for match in YEAR_RE.findall(str(value or ""))}
    return next(iter(years)) if len(years) == 1 else None


def assertion_year(value: str | None) -> int | None:
    match = re.match(r"^((?:18|19|20)\d{2})(?:-|$)", str(value or ""))
    return int(match.group(1)) if match else None


def source_url_year(value: str | None) -> int | None:
    return unique_year(unquote(str(value or "")))


def _context_field(evidence: Mapping[str, Any], name: str) -> Mapping[str, Any] | None:
    value = (evidence.get("fields") or {}).get(name)
    return value if isinstance(value, Mapping) else None


def _context_value(evidence: Mapping[str, Any], name: str) -> Any:
    field = _context_field(evidence, name)
    return field.get("value") if field is not None else None


def _public_context_text(value: Any, *, field: str, case_id: str) -> str | None:
    if value is None:
        return None
    text = normalized_text(str(value))
    if text_has_control_characters(text) or "\ufffd" in text or HTML_TAG_RE.search(text):
        raise ValueError(f"Unsafe reviewed public text in {field}: {case_id}")
    if PRIVATE_TEXT_RE.search(text):
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
    for value in detail.get("sourceFamilies") or []:
        normalized = normalized_text(str(value))
        if normalized:
            output.append(f"legacy_sf_{hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:16]}")
    return sorted(set(output))


def _selected_crop_date(detail: Mapping[str, Any], evidence: Mapping[str, Any]) -> tuple[str | None, str | None, str, str, bool]:
    for field_name in (
        "formation_date", "occurrence_date", "discovery_date", "photography_date",
        "catalog_date", "publication_date",
    ):
        field = _context_field(evidence, field_name)
        if field is not None:
            start, end, precision = _date_bounds(field.get("value"))
            return start, end, precision, field_name, bool(field.get("sourceIds"))
    return (
        detail.get("dateIso"), detail.get("endDateIso") or detail.get("dateIso"),
        str(detail.get("datePrecision") or "unknown"),
        str(detail.get("dateRole") or "catalog_unspecified"), False,
    )


def _crop_coordinate_state(detail: Mapping[str, Any], evidence: Mapping[str, Any]) -> dict[str, Any]:
    latitude = _context_field(evidence, "latitude")
    longitude = _context_field(evidence, "longitude")
    uncertainty = _context_field(evidence, "coordinate_uncertainty_m")
    method = _context_field(evidence, "coordinate_method")
    accepted_pair = latitude is not None and longitude is not None
    if (latitude is None) != (longitude is None):
        accepted_pair = False
    lat_value = latitude.get("value") if accepted_pair else detail.get("lat")
    lon_value = longitude.get("value") if accepted_pair else detail.get("lon")
    lat = float(lat_value) if isinstance(lat_value, (int, float)) else None
    lon = float(lon_value) if isinstance(lon_value, (int, float)) else None
    if lat is not None and not -90 <= lat <= 90:
        raise ValueError(f"Reviewed crop latitude is out of range: {detail.get('id')}")
    if lon is not None and not -180 <= lon <= 180:
        raise ValueError(f"Reviewed crop longitude is out of range: {detail.get('id')}")
    uncertainty_m_value = uncertainty.get("value") if uncertainty is not None else None
    if not isinstance(uncertainty_m_value, (int, float)):
        legacy_km = detail.get("coordinateUncertaintyKm")
        uncertainty_m_value = float(legacy_km) * 1000 if isinstance(legacy_km, (int, float)) else None
    uncertainty_m = float(uncertainty_m_value) if isinstance(uncertainty_m_value, (int, float)) else None
    if uncertainty_m is not None and uncertainty_m < 0:
        raise ValueError(f"Reviewed crop coordinate uncertainty is negative: {detail.get('id')}")
    coordinate_method = normalized_text(str(method.get("value") if method is not None else ""))
    has_coordinates = lat is not None and lon is not None
    if not coordinate_method:
        if not has_coordinates:
            coordinate_method = "unmapped"
        elif detail.get("markerConfidence") == "provisional":
            coordinate_method = "candidate_field_marker"
        elif detail.get("exactCoordinate") is True:
            coordinate_method = "legacy_source_coordinates"
        else:
            coordinate_method = "locality_centroid"
    method_code = coordinate_method.casefold().replace(" ", "_")
    if not has_coordinates:
        evidence_class = "unmapped"
    elif method_code in NON_SITE_COORDINATE_METHODS:
        evidence_class = method_code
    elif accepted_pair or detail.get("exactCoordinate") is True:
        if uncertainty_m is None:
            evidence_class = "source_uncertainty_unknown"
        elif uncertainty_m <= 100:
            evidence_class = "source_exact"
        elif uncertainty_m <= 1000:
            evidence_class = "source_bounded"
        else:
            evidence_class = "source_regional"
    elif detail.get("markerConfidence") == "provisional":
        evidence_class = "candidate_field_marker"
    else:
        evidence_class = "locality_centroid"
    provenance_complete = bool(
        accepted_pair and uncertainty is not None and method is not None
        and latitude.get("sourceIds") and longitude.get("sourceIds")
        and uncertainty.get("sourceIds") and method.get("sourceIds")
    )
    return {
        "lat": round(lat, 7) if lat is not None else None,
        "lon": round(lon, 7) if lon is not None else None,
        "coordinateEvidenceClass": evidence_class,
        "coordinateMethod": coordinate_method,
        "coordinateUncertaintyM": round(uncertainty_m, 3) if uncertainty_m is not None else None,
        "coordinateProvenanceComplete": provenance_complete,
    }


def apply_crop_context(detail: dict[str, Any], evidence: Mapping[str, Any]) -> dict[str, Any]:
    output = dict(detail)
    case_id = str(output["id"])
    for field_name, output_name in (
        ("public_title", "title"), ("public_summary", "catalogSummary"),
        ("location_label", "location"), ("source_case_identifier", "sourceCaseIdentifier"),
    ):
        value = _context_value(evidence, field_name)
        if value is not None:
            output[output_name] = _public_context_text(value, field=field_name, case_id=case_id)
    if _context_field(evidence, "crop_type") is not None:
        output["crop"] = normalized_crop(str(_context_value(evidence, "crop_type")))
    if _context_field(evidence, "primary_classification") is not None:
        output["classification"] = _public_context_text(
            _context_value(evidence, "primary_classification"), field="primary_classification", case_id=case_id,
        )

    start, end, precision, date_role, date_provenance = _selected_crop_date(output, evidence)
    coordinate = _crop_coordinate_state(output, evidence)
    output.update(coordinate)
    output["dateIso"] = start
    output["endDateIso"] = end
    output["datePrecision"] = precision
    output["dateRole"] = date_role
    output["formationDateKnown"] = bool(date_role == "formation_date" and precision == "exact_day")
    output["coordinateUncertaintyKm"] = (
        coordinate["coordinateUncertaintyM"] / 1000 if coordinate["coordinateUncertaintyM"] is not None else None
    )

    source_family_ids = list(evidence.get("sourceFamilyIds") or _legacy_source_family_ids(output))
    review_state = str(evidence.get("reviewState") or output.get("reviewState") or output.get("classification") or "unreviewed")
    independence_status = str(evidence.get("independenceStatus") or "unreviewed")
    duplicate_of = _context_value(evidence, "duplicate_of_case_id") or evidence.get("duplicateOfCaseId")
    dedup_cluster = _context_value(evidence, "dedup_cluster_id")
    dedup_status = "duplicate" if duplicate_of else "resolved_cluster" if dedup_cluster else "canonical_record_unreviewed"
    legal_restriction = _context_value(evidence, "legal_publication_restriction") is True
    exact_day = bool(start and start == end and precision in {"day", "exact_day"})
    source_site = coordinate["coordinateEvidenceClass"] in {"source_exact", "source_bounded"}
    reasons: list[str] = []
    if coordinate["lat"] is None or coordinate["lon"] is None:
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
    if date_role not in {"formation", "formation_date", "occurrence", "occurrence_date"}:
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
        analysis_tier = "crop_strict"
    elif exact_day and coordinate["coordinateEvidenceClass"] in {
        "source_exact", "source_bounded", "candidate_field_marker",
    }:
        analysis_tier = "crop_bounded"
    elif exact_day and coordinate["lat"] is not None and coordinate["lon"] is not None:
        analysis_tier = "crop_locality"
    else:
        analysis_tier = "excluded"
    output.update({
        "reviewState": review_state,
        "sourceFamilyIds": source_family_ids,
        "independenceStatus": independence_status,
        "dedupStatus": dedup_status,
        "analysisTier": analysis_tier,
        "exclusionReasonCodes": reasons,
        "legalPublicationRestriction": legal_restriction,
        "cropChronologyEligible": bool(
            coordinate["lat"] is not None and exact_day and dedup_status != "duplicate"
        ),
        "causality": "not_asserted",
        "traceEligible": False,
        "traceRole": "context_only",
    })
    return output


def _validate_new_crop_case(case_id: str, evidence: Mapping[str, Any]) -> None:
    fields = set((evidence.get("fields") or {}).keys())
    missing: list[str] = []
    if "source_case_identifier" not in fields:
        missing.append("source_case_identifier")
    if not fields.intersection({"public_title", "public_summary"}):
        missing.append("public_title_or_summary")
    if "primary_classification" not in fields:
        missing.append("primary_classification")
    if not fields.intersection({
        "occurrence_date", "formation_date", "discovery_date", "catalog_date", "publication_date",
    }):
        missing.append("date_role")
    if not ("location_label" in fields or {"latitude", "longitude"}.issubset(fields)):
        missing.append("location_role")
    if "crop_type" not in fields:
        missing.append("crop_type")
    if missing:
        raise ValueError(f"Accepted new crop case {case_id} lacks reviewed bootstrap fields: {', '.join(missing)}")


def _new_crop_event(case_id: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
    _validate_new_crop_case(case_id, evidence)
    return {
        "event_id": None, "event_hash": case_id, "external_id": case_id,
        "date_raw": None, "date_iso": None, "end_date_iso": None, "date_precision": "unknown",
        "location_raw": _context_value(evidence, "location_label"),
        "lat": None, "lon": None, "has_coordinates": False,
        "marker_confidence": "locality_only", "exact_coordinate_eligible": False,
        "coordinate_uncertainty_km": None, "mapping_notes": "Reviewed context-evidence sidecar case.",
        "description": _context_value(evidence, "public_summary"), "title": _context_value(evidence, "public_title"),
        "links": [],
        "crop_circle": {
            "formation_id": case_id, "place": _context_value(evidence, "location_label"),
            "region": None, "country": None, "crop": _context_value(evidence, "crop_type"),
            "crop_normalized": _context_value(evidence, "crop_type"),
            "classification": _context_value(evidence, "primary_classification"),
            "origin_status": "reviewed_context_evidence", "source_family_names": [],
            "assertion_count": len(evidence.get("fields") or {}), "multi_archive_coverage": False,
            "possible_multiple_formations_same_entity": False, "modal_morphology_family": None,
        },
    }


def _leading_exclusions(records: list[Mapping[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    counts = Counter(
        reason for record in records for reason in record.get("exclusionReasonCodes") or []
    )
    return [{"reasonCode": reason, "count": count} for reason, count in sorted(
        counts.items(), key=lambda item: (-item[1], item[0])
    )[:limit]]


def validate_plain_text(
    value: Any,
    *,
    field: str,
    formation_id: str,
    allow_url: bool = False,
) -> str:
    text = str(value or "")
    if text_has_control_characters(text) or "\ufffd" in text:
        raise ValueError(f"Unsafe control text in {field}: {formation_id}")
    if HTML_TAG_RE.search(text):
        raise ValueError(f"HTML is not allowed in {field}: {formation_id}")
    if not allow_url and URL_RE.search(text):
        raise ValueError(f"URLs are not allowed in {field}: {formation_id}")
    return text


def safe_iccra_url(value: Any, *, field: str, formation_id: str) -> str:
    url = str(value or "")
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ICCRA_HOSTS:
        raise ValueError(f"Invalid ICCRA URL in {field}: {formation_id}")
    return url


def write_json_gzip(path: Path, value: Any) -> dict[str, Any]:
    raw = canonical_json_bytes(value)
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(compressed)
    return {
        "path": path.name,
        "bytes": len(compressed),
        "decoded_bytes": len(raw),
        "sha256": hashlib.sha256(compressed).hexdigest(),
    }


def write_json(path: Path, value: Any) -> dict[str, Any]:
    raw = canonical_json_bytes(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {
        "path": path.name,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def iso_ordinal(value: str | None) -> int | None:
    if not value:
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return (parsed - date(1970, 1, 1)).days


def coordinate_code(event: dict[str, Any]) -> int:
    if event.get("exact_coordinate_eligible"):
        return COORDINATE_CODES["exact"]
    if event.get("marker_confidence") == "provisional":
        return COORDINATE_CODES["candidate"]
    return COORDINATE_CODES["locality"]


def compact_morphology(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record.get("diagram_occurrence_id"),
        "family": record.get("morphology_family"),
        "confidence": record.get("morphology_confidence"),
        "complexity": record.get("complexity_score"),
        "complexityTier": record.get("complexity_tier"),
        "components": record.get("significant_component_count"),
        "holes": record.get("hole_count"),
        "circles": record.get("circle_like_component_count"),
        "discs": record.get("filled_disc_component_count"),
        "rings": record.get("ring_component_count"),
        "concentric": record.get("concentric_components"),
        "alignment": record.get("component_alignment_score"),
        "symmetryOrder": record.get("rotational_symmetry_order"),
        "symmetryScore": record.get("rotational_symmetry_score"),
        "boundaryComplexity": record.get("boundary_complexity"),
        "straightTier": record.get("straight_component_tier"),
        "rank": record.get("diagram_rank_within_entity"),
    }


def compact_source(assertion: dict[str, Any]) -> dict[str, Any]:
    source_page = assertion.get("source_page")
    page_number = source_page if str(source_page or "").strip().isdigit() else None
    page_url = source_page if str(source_page or "").startswith(("https://", "http://")) else None
    return {
        "assertionId": assertion.get("assertion_id"),
        "name": assertion.get("source_name"),
        "recordUrl": assertion.get("source_record_url") or page_url,
        "collectionUrl": assertion.get("source_url"),
        "pageNumber": page_number,
        "listingText": assertion.get("source_listing_text"),
        "date": assertion.get("date_iso"),
        "datePrecision": assertion.get("date_precision"),
    }


def compact_image(image: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": image.get("source_name"),
        "pageUrl": image.get("source_page_url") or image.get("source_record_url"),
        "imageUrl": image.get("image_url") if image.get("embedding_allowed") else None,
        "kind": image.get("image_kind"),
        "rights": image.get("rights_status"),
        "displayPolicy": image.get("pixel_display_policy"),
        "embeddingAllowed": bool(image.get("embedding_allowed")),
    }


def compact_source_description(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "assertionId": record.get("assertionId"),
        "text": record.get("sourceExcerpt"),
        "truncated": bool(record.get("sourceExcerptTruncated")),
        "url": record.get("sourceRecordUrl"),
        "sourceName": record.get("sourceName") or "ICCRA",
        "creditDisplay": record.get("sourceCreditDisplay"),
        "attributionAvailable": bool(record.get("sourceAttributionAvailable")),
    }


def compact_detail(
    event: dict[str, Any],
    morphology: list[dict[str, Any]],
    assertions: list[dict[str, Any]],
    images: list[dict[str, Any]],
    description_enrichment: dict[str, Any] | None,
) -> dict[str, Any]:
    crop = event.get("crop_circle") or {}
    enrichment = description_enrichment or {}
    source_excerpt = enrichment.get("sourceExcerpt")
    source_descriptions = [
        compact_source_description(record)
        for record in enrichment.get("sourceDescriptions", [])
        if record.get("sourceExcerpt")
    ]
    if source_excerpt and not source_descriptions:
        source_descriptions = [compact_source_description(enrichment)]
    source_credit_display = enrichment.get("sourceCreditDisplay")
    crop_value = (
        normalized_crop(crop.get("crop"))
        or normalized_crop(enrichment.get("crop"))
        or normalized_crop(crop.get("crop_normalized"))
    )
    return {
        "id": event.get("event_hash") or event.get("external_id"),
        "eventId": event.get("event_id"),
        "title": event.get("title"),
        "dateRaw": event.get("date_raw"),
        "dateIso": event.get("date_iso"),
        "endDateIso": event.get("end_date_iso"),
        "datePrecision": event.get("date_precision"),
        "location": event.get("location_raw"),
        "lat": event.get("lat"),
        "lon": event.get("lon"),
        "markerConfidence": event.get("marker_confidence"),
        "exactCoordinate": bool(event.get("exact_coordinate_eligible")),
        "coordinateUncertaintyKm": event.get("coordinate_uncertainty_km"),
        "mappingNotes": event.get("mapping_notes"),
        "catalogSummary": event.get("description"),
        "sourceDescription": source_excerpt,
        "sourceDescriptions": source_descriptions,
        "sourceDescriptionStatus": "source_excerpt" if source_excerpt else "not_captured",
        "sourceDescriptionTruncated": bool(enrichment.get("sourceExcerptTruncated")),
        "sourceDescriptionUrl": enrichment.get("sourceRecordUrl"),
        "sourceDescriptionLabel": "ICCRA — source narrative",
        "sourceDescriptionCredit": source_credit_display,
        "sourceDescriptionCreditDisplay": source_credit_display,
        "sourceDescriptionAttributionAvailable": bool(enrichment.get("sourceAttributionAvailable")),
        "dateRole": enrichment.get("dateRole") or "catalog_unspecified",
        "formationDateKnown": False,
        "place": crop.get("place"),
        "region": crop.get("region"),
        "country": crop.get("country"),
        "crop": crop_value,
        "sourceCropRaw": enrichment.get("cropRaw"),
        "sizeText": crop.get("size_text"),
        "reportedSizeM": crop.get("reported_size_m"),
        "classification": crop.get("classification"),
        "originStatus": crop.get("origin_status"),
        "sourceFamilies": crop.get("source_family_names") or [],
        "assertionCount": crop.get("assertion_count"),
        "multiArchive": bool(crop.get("multi_archive_coverage")),
        "multipleDiagrams": bool(crop.get("possible_multiple_formations_same_entity")) or len(morphology) > 1,
        "morphology": [compact_morphology(item) for item in morphology],
        "sources": [compact_source(item) for item in assertions],
        "images": [compact_image(item) for item in images],
        "links": list(dict.fromkeys([link for link in event.get("links", []) if link])),
        "causality": "not_asserted",
        "traceEligible": False,
        "traceRole": "context_only",
        "cropChronologyEligible": bool(
            event.get("has_coordinates")
            and event.get("date_precision") in {"exact_day", "day"}
        ),
        "cropChronologyRole": "catalog_date_adjacency_only",
    }


def _validate_description_record(
    record: dict[str, Any],
    *,
    formation_id: str,
    assertion: dict[str, Any],
    max_words: int,
) -> None:
    if record.get("formationId") != formation_id:
        raise ValueError(f"Description formation key mismatch: {formation_id}")
    assertion_id = str(record.get("assertionId") or "")
    if assertion_id != str(assertion.get("assertion_id") or ""):
        raise ValueError(f"Description assertion key mismatch: {formation_id}")
    if record.get("displayPolicy") != ENRICHMENT_DISPLAY_POLICY:
        raise ValueError(f"Invalid source-description display policy: {formation_id}")
    if record.get("dateRole") != ENRICHMENT_DATE_ROLE:
        raise ValueError(f"Invalid source-description date role: {formation_id}")
    if record.get("parserVersion") != "iccra-primary-report-v2":
        raise ValueError(f"Unsupported source-description parser version: {formation_id}")
    if record.get("retrieval") not in {"cache", "network"}:
        raise ValueError(f"Invalid source-description retrieval status: {formation_id}")

    excerpt = validate_plain_text(
        record.get("sourceExcerpt"),
        field="sourceExcerpt",
        formation_id=formation_id,
    ).strip()
    if not excerpt:
        raise ValueError(f"Captured source-description record has no excerpt: {formation_id}")
    if EXCERPT_METADATA_RE.search(excerpt):
        raise ValueError(f"Source excerpt contains footer metadata: {formation_id}")
    word_count = len(excerpt.split())
    if word_count > max_words:
        raise ValueError(f"Source excerpt exceeds the publication word limit: {formation_id}")
    if record.get("sourceExcerptWordCount") != word_count:
        raise ValueError(f"Source excerpt word count mismatch: {formation_id}")
    narrative_word_count = record.get("sourceNarrativeWordCount")
    if not isinstance(narrative_word_count, int) or narrative_word_count < word_count:
        raise ValueError(f"Invalid source narrative word count: {formation_id}")
    if record.get("sourceNarrativeDetected") is not True:
        raise ValueError(f"Source narrative detection flag mismatch: {formation_id}")
    if record.get("sourceExcerptTruncated") is not (narrative_word_count > word_count):
        raise ValueError(f"Source excerpt truncation flag mismatch: {formation_id}")

    source_url = safe_iccra_url(
        record.get("sourceRecordUrl"),
        field="sourceRecordUrl",
        formation_id=formation_id,
    )
    if source_url != assertion.get("source_record_url"):
        raise ValueError(f"Source record URL does not match its assertion: {formation_id}")
    collection_url = safe_iccra_url(
        record.get("sourceCollectionUrl"),
        field="sourceCollectionUrl",
        formation_id=formation_id,
    )
    if collection_url != assertion.get("source_url"):
        raise ValueError(f"Source collection URL does not match its assertion: {formation_id}")
    if record.get("sourceName") != assertion.get("source_name"):
        raise ValueError(f"Source name does not match its assertion: {formation_id}")
    if record.get("sourceDate") != assertion.get("date_iso"):
        raise ValueError(f"Source date does not match its assertion: {formation_id}")
    if record.get("sourceDatePrecision") != assertion.get("date_precision"):
        raise ValueError(f"Source date precision does not match its assertion: {formation_id}")

    page_heading = validate_plain_text(
        record.get("pageHeading"),
        field="pageHeading",
        formation_id=formation_id,
    )
    if not page_heading.casefold().startswith("reported crop circles"):
        raise ValueError(f"Missing ICCRA page heading: {formation_id}")
    expected_years = {
        "assertionYear": assertion_year(record.get("sourceDate")),
        "sourceRecordUrlYear": source_url_year(source_url),
        "pageHeadingYear": unique_year(page_heading),
    }
    comparable_years = {year for year in expected_years.values() if year is not None}
    if len(comparable_years) > 1:
        raise ValueError(f"Source date provenance mismatch escaped quarantine: {formation_id}")
    expected_date_status = (
        "matched_all"
        if all(year is not None for year in expected_years.values())
        else "matched_available_years"
    )
    date_validation = record.get("dateValidation")
    if not isinstance(date_validation, dict):
        raise ValueError(f"Missing source date validation: {formation_id}")
    if date_validation.get("status") not in ENRICHMENT_DATE_STATUSES:
        raise ValueError(f"Invalid source date validation status: {formation_id}")
    if date_validation != {"status": expected_date_status, **expected_years}:
        raise ValueError(f"Stored source date evidence mismatch: {formation_id}")

    page_sha = str(record.get("pageSha256") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", page_sha):
        raise ValueError(f"Invalid source page hash: {formation_id}")
    crop_raw = record.get("cropRaw")
    validate_plain_text(crop_raw, field="cropRaw", formation_id=formation_id)
    if record.get("crop") != normalized_crop(crop_raw):
        raise ValueError(f"Source crop normalization mismatch: {formation_id}")

    credit_raw = record.get("sourceCreditRaw")
    validate_plain_text(credit_raw, field="sourceCreditRaw", formation_id=formation_id, allow_url=True)
    credit_display = record.get("sourceCreditDisplay")
    if record.get("sourceCredit") != credit_display:
        raise ValueError(f"Legacy source credit is not the safe display value: {formation_id}")
    if credit_display is not None:
        clean_credit = validate_plain_text(
            credit_display,
            field="sourceCreditDisplay",
            formation_id=formation_id,
        )
        if len(clean_credit) > SAFE_CREDIT_MAX_CHARS or len(clean_credit.split()) > SAFE_CREDIT_MAX_WORDS:
            raise ValueError(f"Source credit display is not concise: {formation_id}")
        if EXCERPT_METADATA_RE.search(clean_credit):
            raise ValueError(f"Source credit display contains media metadata: {formation_id}")
    attributions = record.get("sourceAttributionRaw")
    if not isinstance(attributions, list):
        raise ValueError(f"Invalid source attribution list: {formation_id}")
    for attribution in attributions:
        validate_plain_text(
            attribution,
            field="sourceAttributionRaw",
            formation_id=formation_id,
            allow_url=True,
        )
    if attributions and record.get("sourceAttributionAvailable") is not True:
        raise ValueError(f"Source attribution availability mismatch: {formation_id}")


def load_description_enrichment(path: Path | None, input_path: Path) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    raw_input = input_path.read_bytes()
    source_payload = json.loads(raw_input)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schemaVersion") != 1 or not isinstance(payload.get("records"), dict):
        raise ValueError("Unsupported crop-circle description enrichment schema")
    if payload.get("sourceExportSha256") != hashlib.sha256(raw_input).hexdigest():
        raise ValueError("Description enrichment does not match the crop-circle source export")
    if payload.get("sourceExportSchema") != source_payload.get("schema_version"):
        raise ValueError("Description enrichment source schema mismatch")
    if payload.get("sourceCommit") != (source_payload.get("source") or {}).get("source_commit"):
        raise ValueError("Description enrichment source commit mismatch")

    policy = payload.get("policy") or {}
    if policy.get("rawHtmlPackaged") or policy.get("fullArticleTextPackaged"):
        raise ValueError("Description enrichment violates the short-excerpt publication policy")
    if policy.get("displayPolicy") != ENRICHMENT_DISPLAY_POLICY:
        raise ValueError("Invalid description enrichment display policy")
    if policy.get("dateRole") != ENRICHMENT_DATE_ROLE:
        raise ValueError("Invalid description enrichment date role")
    max_words = int(policy.get("maxSourceWords") or 0)
    if max_words < 1 or max_words > 25:
        raise ValueError("Description enrichment must cap source excerpts at 25 words")

    all_iccra_assertions = [
        assertion
        for assertion in source_payload.get("source_assertions", [])
        if assertion.get("source_name") == "ICCRA" and assertion.get("source_record_url")
    ]
    candidate_assertions = [
        assertion
        for assertion in all_iccra_assertions
        if assertion.get("source_record_url") != assertion.get("source_url")
    ]
    assertions_by_id = {
        str(assertion.get("assertion_id") or ""): assertion
        for assertion in candidate_assertions
    }
    if len(assertions_by_id) != len(candidate_assertions) or "" in assertions_by_id:
        raise ValueError("Crop-circle source assertions must have unique IDs")

    records: dict[str, dict[str, Any]] = {}
    seen_assertion_ids: set[str] = set()
    for formation_key, envelope in payload["records"].items():
        formation_id = str(formation_key)
        if not isinstance(envelope, dict) or envelope.get("formationId") != formation_id:
            raise ValueError(f"Invalid description enrichment record: {formation_id}")
        descriptions = envelope.get("sourceDescriptions")
        if not isinstance(descriptions, list) or not descriptions:
            raise ValueError(f"Source descriptions were not preserved by assertion: {formation_id}")
        for description in descriptions:
            if not isinstance(description, dict):
                raise ValueError(f"Invalid source description item: {formation_id}")
            assertion_id = str(description.get("assertionId") or "")
            if assertion_id in seen_assertion_ids:
                raise ValueError(f"Duplicate source description assertion: {assertion_id}")
            assertion = assertions_by_id.get(assertion_id)
            if assertion is None:
                raise ValueError(f"Unknown source description assertion: {assertion_id}")
            if str(assertion.get("formation_id") or "") != formation_id:
                raise ValueError(f"Source description assertion belongs to another formation: {assertion_id}")
            _validate_description_record(
                description,
                formation_id=formation_id,
                assertion=assertion,
                max_words=max_words,
            )
            seen_assertion_ids.add(assertion_id)
        ordered_descriptions = sorted(descriptions, key=lambda item: str(item.get("assertionId") or ""))
        if descriptions != ordered_descriptions:
            raise ValueError(f"Source descriptions are not deterministically ordered: {formation_id}")
        primary = max(
            descriptions,
            key=lambda item: (
                bool(item.get("sourceExcerpt")),
                int(item.get("sourceNarrativeWordCount") or 0),
                str(item.get("assertionId") or ""),
            ),
        )
        if envelope.get("primaryAssertionId") != primary.get("assertionId"):
            raise ValueError(f"Primary source description is not deterministic: {formation_id}")
        for key, value in primary.items():
            if envelope.get(key) != value:
                raise ValueError(f"Primary compatibility field mismatch ({key}): {formation_id}")
        records[formation_id] = envelope

    failures = payload.get("failures")
    if not isinstance(failures, list):
        raise ValueError("Description enrichment failures must be a list")
    failed_assertion_ids: set[str] = set()
    for failure in failures:
        if not isinstance(failure, dict):
            raise ValueError("Invalid description enrichment failure")
        assertion_id = str(failure.get("assertionId") or "")
        assertion = assertions_by_id.get(assertion_id)
        if assertion is None or assertion_id in failed_assertion_ids or assertion_id in seen_assertion_ids:
            raise ValueError(f"Invalid failed description assertion: {assertion_id}")
        formation_id = str(assertion.get("formation_id") or "")
        if failure.get("formationId") != formation_id or failure.get("url") != assertion.get("source_record_url"):
            raise ValueError(f"Failed source assertion provenance mismatch: {assertion_id}")
        error_code = failure.get("errorCode")
        if error_code not in ENRICHMENT_FAILURE_CODES:
            raise ValueError(f"Invalid source-description failure code: {assertion_id}")
        if error_code == "source_record_date_mismatch":
            evidence = failure.get("dateValidation")
            if not isinstance(evidence, dict):
                raise ValueError(f"Missing date-mismatch evidence: {assertion_id}")
            expected_assertion_year = assertion_year(assertion.get("date_iso"))
            expected_url_year = source_url_year(assertion.get("source_record_url"))
            if evidence.get("assertionYear") != expected_assertion_year:
                raise ValueError(f"Invalid assertion-year mismatch evidence: {assertion_id}")
            if evidence.get("sourceRecordUrlYear") != expected_url_year:
                raise ValueError(f"Invalid URL-year mismatch evidence: {assertion_id}")
            if len({year for year in evidence.values() if isinstance(year, int)}) < 2:
                raise ValueError(f"Date mismatch failure contains no mismatch: {assertion_id}")
        failed_assertion_ids.add(assertion_id)

    if seen_assertion_ids | failed_assertion_ids != set(assertions_by_id):
        missing = sorted(set(assertions_by_id) - seen_assertion_ids - failed_assertion_ids)
        raise ValueError(f"Description assertions are unaccounted for: {missing[:3]}")

    descriptions = [
        description
        for record in records.values()
        for description in record.get("sourceDescriptions", [])
    ]
    expected_counts = {
        "candidateAssertions": len(candidate_assertions),
        "indexOnlyAssertionsSkipped": len(all_iccra_assertions) - len(candidate_assertions),
        "records": len(records),
        "withSourceExcerpt": sum(bool(record.get("sourceExcerpt")) for record in records.values()),
        "withCrop": sum(bool(record.get("crop")) for record in records.values()),
        "withSourceCredit": sum(bool(record.get("sourceCreditDisplay")) for record in records.values()),
        "withSourceAttribution": sum(
            bool(record.get("sourceAttributionAvailable")) for record in records.values()
        ),
        "descriptionAssertions": len(descriptions),
        "sourceExcerptAssertions": sum(bool(record.get("sourceExcerpt")) for record in descriptions),
        "duplicateFormationRecords": sum(
            len(record.get("sourceDescriptions", [])) > 1 for record in records.values()
        ),
        "quarantinedDateMismatches": sum(
            failure.get("errorCode") == "source_record_date_mismatch" for failure in failures
        ),
        "failures": len(failures),
    }
    if payload.get("counts") != expected_counts:
        raise ValueError("Description enrichment counts do not match its records and source export")
    return records


def build(
    input_path: Path,
    output_root: Path,
    release_id: str,
    chunk_size: int,
    asset_base_url: str = "",
    description_enrichment_path: Path | None = None,
    context_evidence_root: Path | None = DEFAULT_CONTEXT_EVIDENCE_ROOT,
) -> dict[str, Any]:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "crop-circle-timeline-export-v1.0.0":
        raise ValueError("Unsupported crop-circle export schema")
    if chunk_size < 50:
        raise ValueError("chunk-size must be at least 50")
    description_enrichment = load_description_enrichment(description_enrichment_path, input_path)
    context_evidence, context_metadata, accepted_new_cases = load_context_evidence(
        context_evidence_root, "crop_circle"
    )

    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    morphology_by_formation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in payload.get("morphology_occurrences", []):
        morphology_by_formation[str(record.get("formation_id"))].append(record)
    for records in morphology_by_formation.values():
        records.sort(key=lambda item: (item.get("diagram_rank_within_entity") or 999, item.get("diagram_occurrence_id") or ""))

    assertions_by_formation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in payload.get("source_assertions", []):
        assertions_by_formation[str(record.get("formation_id"))].append(record)

    images_by_formation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in payload.get("image_links", []):
        images_by_formation[str(record.get("formation_id"))].append(record)

    source_events = list(payload.get("events", []))
    source_ids = {str(item.get("event_hash") or item.get("external_id")) for item in source_events}
    unknown_context_cases = sorted(set(context_evidence) - source_ids - accepted_new_cases)
    if unknown_context_cases:
        raise ValueError(
            "Reviewed crop assertions target cases absent from the source export and not accepted_new_source: "
            + ", ".join(unknown_context_cases[:5])
        )
    missing_new_evidence = sorted(accepted_new_cases - set(context_evidence))
    if missing_new_evidence:
        raise ValueError("Accepted new crop cases have no reviewed evidence: " + ", ".join(missing_new_evidence[:5]))
    events = source_events + [
        _new_crop_event(case_id, context_evidence[case_id])
        for case_id in sorted(accepted_new_cases - source_ids)
    ]
    events.sort(key=lambda item: str(item.get("event_hash") or item.get("external_id")))
    detail_records: list[dict[str, Any]] = []
    detail_chunk_by_id: dict[str, int] = {}
    morphology_families = sorted({
        str(record.get("morphology_family"))
        for record in payload.get("morphology_occurrences", [])
        if record.get("morphology_family")
    })
    morphology_codes = {name: index for index, name in enumerate(morphology_families)}

    legally_restricted_suppressed = 0
    for event in events:
        formation_id = str(event.get("event_hash") or event.get("external_id"))
        detail = apply_crop_context(compact_detail(
            event,
            morphology_by_formation.get(formation_id, []),
            assertions_by_formation.get(formation_id, []),
            images_by_formation.get(formation_id, []),
            description_enrichment.get(formation_id),
        ), context_evidence.get(formation_id, {}))
        if detail["legalPublicationRestriction"]:
            legally_restricted_suppressed += 1
            continue
        detail_records.append(detail)
    detail_chunk_by_id = {
        detail["id"]: index // chunk_size for index, detail in enumerate(detail_records)
    }

    detail_files: list[dict[str, Any]] = []
    for start in range(0, len(detail_records), chunk_size):
        chunk_number = start // chunk_size
        chunk_records = detail_records[start:start + chunk_size]
        relative = Path("details") / f"chunk_{chunk_number:03d}.json.gz"
        info = write_json_gzip(output_root / relative, {record["id"]: record for record in chunk_records})
        info["path"] = str(relative).replace("\\", "/")
        info["record_count"] = len(chunk_records)
        detail_files.append(info)

    point_rows: list[list[Any]] = []
    event_by_id = {
        str(event.get("event_hash") or event.get("external_id")): event for event in events
    }
    for detail in detail_records:
        lat = detail.get("lat")
        lon = detail.get("lon")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            continue
        formation_id = str(detail["id"])
        event = event_by_id[formation_id]
        crop = event.get("crop_circle") or {}
        primary_family = crop.get("modal_morphology_family") or "no_diagram"
        evidence_class = str(detail.get("coordinateEvidenceClass") or "unmapped")
        if evidence_class == "source_exact":
            public_coordinate_code = COORDINATE_CODES["exact"]
        elif evidence_class in {"source_bounded", "candidate_field_marker"}:
            public_coordinate_code = COORDINATE_CODES["candidate"]
        else:
            public_coordinate_code = COORDINATE_CODES["locality"]
        point_rows.append([
            formation_id,
            round(float(lat), 6),
            round(float(lon), 6),
            iso_ordinal(detail.get("dateIso")),
            iso_ordinal(detail.get("endDateIso") or detail.get("dateIso")),
            DATE_PRECISION_CODES.get(str(detail.get("datePrecision") or "unknown"), DATE_PRECISION_CODES["unknown"]),
            public_coordinate_code,
            morphology_codes.get(str(primary_family), morphology_codes.get("no_diagram", 0)),
            detail_chunk_by_id[formation_id],
            COORDINATE_EVIDENCE_CODES.get(evidence_class, COORDINATE_EVIDENCE_CODES["unmapped"]),
            detail.get("coordinateUncertaintyM"),
        ])

    points_info = write_json_gzip(output_root / "points.json.gz", point_rows)
    mapped_positions = len({(row[1], row[2]) for row in point_rows})
    manifest = {
        "schemaVersion": SCHEMA_VERSION,
        "releaseId": release_id,
        "assetBaseUrl": asset_base_url.rstrip("/") + "/" if asset_base_url else "",
        # A live wall-clock timestamp would make milestone double-builds differ.
        # Preserve a frozen upstream timestamp when one exists; otherwise null is
        # the honest deterministic value and the immutable release ID supplies
        # release chronology.
        "generatedAtUtc": payload.get("generated_at_utc") or payload.get("generatedAtUtc"),
        "sourceSchema": payload.get("schema_version"),
        "sourceCommit": (payload.get("source") or {}).get("source_commit"),
        "counts": {
            "events": len(detail_records),
            "sourceEvents": len(source_events),
            "acceptedNewCases": len(accepted_new_cases - source_ids),
            "legallyRestrictedSuppressed": legally_restricted_suppressed,
            "mapped": len(point_rows),
            "mappedPositions": mapped_positions,
            "exactCoordinates": sum(
                record["coordinateEvidenceClass"] == "source_exact" for record in detail_records
            ),
            "boundedCoordinates": sum(
                record["coordinateEvidenceClass"] == "source_bounded" for record in detail_records
            ),
            "candidateFields": sum(
                record["coordinateEvidenceClass"] == "candidate_field_marker" for record in detail_records
            ),
            "localityCentroids": sum(
                record["coordinateEvidenceClass"] in {
                    "locality_centroid", "postal_centroid", "approximate_map_pin"
                } for record in detail_records
            ),
            "detailChunks": len(detail_files),
            "sourceDescriptions": sum(bool(record.get("sourceDescriptions")) for record in detail_records),
            "recordsWithSourceDescriptions": sum(
                bool(record.get("sourceDescriptions")) for record in detail_records
            ),
            "sourceDescriptionAssertions": sum(
                len(record.get("sourceDescriptions") or []) for record in detail_records
            ),
            "catalogDateTraceEligible": sum(bool(record.get("cropChronologyEligible")) for record in detail_records),
            "openLicenseImageLinks": sum(
                1 for record in payload.get("image_links", []) if record.get("embedding_allowed")
            ),
        },
        "points": {
            **points_info,
            "path": "points.json.gz",
            "rowSchema": [
                "id", "lat", "lon", "startOrdinal", "endOrdinal", "datePrecisionCode",
                "coordinateCode", "morphologyCode", "detailChunk",
                "coordinateEvidenceClassCode", "coordinateUncertaintyM",
            ],
        },
        "details": {
            "basePath": "details/",
            "chunkPattern": "chunk_{chunk:03d}.json.gz",
            "chunkSize": chunk_size,
            "files": detail_files,
        },
        "codes": {
            "datePrecision": DATE_PRECISION_CODES,
            "coordinate": COORDINATE_CODES,
            "coordinateEvidenceClass": COORDINATE_EVIDENCE_CODES,
            "morphology": morphology_codes,
        },
        "contextEvidence": context_metadata,
        "readiness": {
            "activeInventory": len(detail_records),
            "mapped": len(point_rows),
            "sensitivityReady": sum(
                record["analysisTier"] in {"crop_bounded", "crop_locality"} for record in detail_records
            ),
            "strictReady": sum(record["analysisTier"] == "crop_strict" for record in detail_records),
            "leadingExclusionReasons": _leading_exclusions(detail_records),
        },
        "policy": {
            "causality": "not_asserted",
            "traceEligible": False,
            "traceRole": "context_only",
            "cropChronologyEnabledByDefault": False,
            "cropChronologyRole": "catalog_date_adjacency_only",
            "cropChronologyCrossDomain": False,
            "cropChronologyDefaultRelation": "same_day",
            "cropChronologyDefaultMaximumDistanceKm": 250,
            "cropChronologyDefaultCoordinates": "exact_and_candidate",
            "photographsPreloaded": False,
            "schematicsAreApproximate": True,
            "dateRole": "catalog_unspecified",
            "formationTimeInferred": False,
            "legalRestrictionSuppressesPublicRecord": True,
            "privateOwnerAndAccessDetailsPublished": False,
        },
    }
    manifest_info = write_json(output_root / "manifest.json", manifest)
    manifest["manifestBytes"] = manifest_info["bytes"]
    return manifest


def main() -> None:
    args = parse_args()
    manifest = build(
        args.input,
        args.output,
        args.release_id,
        args.chunk_size,
        args.asset_base_url,
        args.description_enrichment,
        args.context_evidence_root,
    )
    print(json.dumps({
        "output": str(args.output),
        "releaseId": manifest["releaseId"],
        "counts": manifest["counts"],
        "pointsGzipBytes": manifest["points"]["bytes"],
        "largestDetailGzipBytes": max(item["bytes"] for item in manifest["details"]["files"]),
    }, indent=2))


if __name__ == "__main__":
    main()
