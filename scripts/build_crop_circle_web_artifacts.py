"""Build lazy, rights-safe Crop Circle Timeline runtime artifacts.

The full interoperability export is a build input only. The browser receives a
compact point index after the layer is enabled and one small detail chunk after
a marker is opened. No source photograph pixels are packaged.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import shutil
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--description-enrichment", type=Path)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--asset-base-url", default="")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    return parser.parse_args()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


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
) -> dict[str, Any]:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "crop-circle-timeline-export-v1.0.0":
        raise ValueError("Unsupported crop-circle export schema")
    if chunk_size < 50:
        raise ValueError("chunk-size must be at least 50")
    description_enrichment = load_description_enrichment(description_enrichment_path, input_path)

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

    events = sorted(payload.get("events", []), key=lambda item: str(item.get("event_hash") or item.get("external_id")))
    detail_records: list[dict[str, Any]] = []
    detail_chunk_by_id: dict[str, int] = {}
    morphology_families = sorted({
        str(record.get("morphology_family"))
        for record in payload.get("morphology_occurrences", [])
        if record.get("morphology_family")
    })
    morphology_codes = {name: index for index, name in enumerate(morphology_families)}

    for index, event in enumerate(events):
        formation_id = str(event.get("event_hash") or event.get("external_id"))
        detail_chunk_by_id[formation_id] = index // chunk_size
        detail_records.append(compact_detail(
            event,
            morphology_by_formation.get(formation_id, []),
            assertions_by_formation.get(formation_id, []),
            images_by_formation.get(formation_id, []),
            description_enrichment.get(formation_id),
        ))

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
    for event in events:
        if not event.get("has_coordinates"):
            continue
        lat = event.get("lat")
        lon = event.get("lon")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            continue
        formation_id = str(event.get("event_hash") or event.get("external_id"))
        crop = event.get("crop_circle") or {}
        primary_family = crop.get("modal_morphology_family") or "no_diagram"
        point_rows.append([
            formation_id,
            round(float(lat), 6),
            round(float(lon), 6),
            iso_ordinal(event.get("date_iso")),
            iso_ordinal(event.get("end_date_iso") or event.get("date_iso")),
            DATE_PRECISION_CODES.get(str(event.get("date_precision") or "unknown"), DATE_PRECISION_CODES["unknown"]),
            coordinate_code(event),
            morphology_codes.get(str(primary_family), morphology_codes.get("no_diagram", 0)),
            detail_chunk_by_id[formation_id],
        ])

    points_info = write_json_gzip(output_root / "points.json.gz", point_rows)
    mapped_positions = len({(row[1], row[2]) for row in point_rows})
    manifest = {
        "schemaVersion": SCHEMA_VERSION,
        "releaseId": release_id,
        "assetBaseUrl": asset_base_url.rstrip("/") + "/" if asset_base_url else "",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "sourceSchema": payload.get("schema_version"),
        "sourceCommit": (payload.get("source") or {}).get("source_commit"),
        "counts": {
            "events": len(events),
            "mapped": len(point_rows),
            "mappedPositions": mapped_positions,
            "exactCoordinates": sum(1 for row in point_rows if row[6] == COORDINATE_CODES["exact"]),
            "candidateFields": sum(1 for row in point_rows if row[6] == COORDINATE_CODES["candidate"]),
            "localityCentroids": sum(1 for row in point_rows if row[6] == COORDINATE_CODES["locality"]),
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
            "morphology": morphology_codes,
        },
        "policy": {
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
