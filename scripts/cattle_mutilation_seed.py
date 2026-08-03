"""Build the Phase 1 global animal-mutilation cross-domain seed catalog.

The command is deliberately non-destructive: authoritative UFO and crop-circle
inputs are opened read-only, raw third-party pages remain in a caller-provided
private cache, and every generated artifact is written below an explicit output
directory.  Classification and relationship scoring are deterministic and
explainable; no relationship asserts causality.
"""

from __future__ import annotations

import argparse
from bisect import bisect_left, bisect_right
from calendar import monthrange
import csv
import hashlib
import html
import json
import math
import os
import re
import shutil
import sys
import unicodedata
import zipfile
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime
from html.parser import HTMLParser
from importlib.metadata import PackageNotFoundError, version as package_version
from itertools import combinations
from pathlib import Path
from functools import lru_cache
from typing import Any, Iterable, Iterator, Mapping, Sequence
from urllib.parse import urlsplit


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.cattle_mutilation_acquire import (  # noqa: E402
    AUDIT_FIELDS as ACQUISITION_AUDIT_FIELDS,
    AUDIT_SCHEMA_VERSION as ACQUISITION_AUDIT_SCHEMA_VERSION,
    CACHE_SCHEMA_VERSION as ACQUISITION_CACHE_SCHEMA_VERSION,
    PINNED_CROP_ZIP_SHA256,
    CropSourceAcquisitionError,
    acquire_crop_sources,
    enumerate_crop_source_targets,
)
from scripts.cattle_mutilation_pdf import (  # noqa: E402
    CATALOG_ADAPTER_VERSION,
    PINNED_COMBINED_PDF_SHA256,
    scan_catalog_pdf,
)
from scripts.animal_mutilation_taxonomy import (  # noqa: E402
    AnimalAssertion,
    GENERIC_ANIMAL_TERMS,
    TAXA,
    analyze_incident_animals,
    assertion_to_public_row,
    has_any_animal_term,
    taxonomy_manifest,
    victim_labels,
)


PIPELINE_VERSION = "animal-mutilation-cross-domain-seed-v1.1.12"
CANONICALIZATION_VERSION = "1.1.12"
VALIDATION_PROVENANCE_SCHEMA_VERSION = "animal-mutilation-validation-provenance-v1.1.12"
PINNED_BASE_COMMIT = "d0c8341c9b4785db40f7da74369c750770b0d21f"
PINNED_STARTER_PACK_SHA256 = (
    "578F9A6E2E6B1EFDC4634EF5421F3079A5E169ADE89EF65F9CA181BC506AE611"
)
PINNED_SOURCE_RECORD_COUNT = 971_115
PINNED_DEDUPED_EVENT_COUNT = 944_578
PINNED_CROP_EVENT_COUNT = 7_745
PINNED_CROP_ASSERTION_COUNT = 8_391
PINNED_CROP_ASSERTION_URL_COUNT = 2_345
PINNED_CROP_ALL_RECORD_URL_COUNT = 2_371
PINNED_CROP_IMAGE_ALT_TEXT_COUNT = 2_858
PINNED_CROP_IMAGE_TITLE_TEXT_COUNT = 78
PINNED_CATALOG_PAGE_COUNT = 309
PINNED_CATALOG_SLOT_COUNT = 5_978

DEFAULT_STARTER_PACK = Path(
    r"C:\Users\jarod\Downloads\cattle_mutilation_mapping_starter_pack.zip"
)
DEFAULT_CROP_ZIP = Path(
    r"C:\Users\jarod\Downloads\Crop_Circle_UFO_Timeline_Export_v1.zip"
)
DEFAULT_CATALOG_PDF = Path(r"C:\Users\jarod\Downloads\COMBINED.pdf")
DEFAULT_SOURCE_RECORDS = REPO_ROOT / "data" / "canonical_full" / "source_records.jsonl"
DEFAULT_DEDUPED_EVENTS = REPO_ROOT / "data" / "canonical_full" / "deduped_events.jsonl"
DEFAULT_OUTPUT_DIR = (
    Path(r"C:\Users\jarod\Documents\Cattle Mutilation Map")
    / "outputs"
    / "phase1_1"
    / "global_animal_seed_v1_1"
)
DEFAULT_PRIVATE_CACHE = (
    Path(r"C:\Users\jarod\Documents\Cattle Mutilation Map")
    / "private_cache"
    / "crop_sources_v1"
)

OUTPUT_NAMES = (
    "candidate_records.jsonl",
    "canonical_incidents.jsonl",
    "related_events.jsonl",
    "extraction_audit.csv",
    "seed_report.md",
    "duplicate_pairs.csv",
    "rejected_or_noise_candidates.jsonl",
    "cross_domain_relationships.jsonl",
    "crop_circle_source_candidates.jsonl",
    "crop_circle_source_access_audit.csv",
    "run_manifest.json",
)

EXTRACTION_AUDIT_FIELDS = (
    "source_index",
    "canonical_input_id",
    "source_name",
    "source_native_id",
    "source_row_hash",
    "record_id",
    "candidate_score",
    "candidate_reasons",
    "record_type",
    "incident_likelihood",
    "disposition",
    "needs_human_review",
    "has_crop_circle_signal",
    "explicit_crop_mutilation_link",
    "duplicate_cluster_id",
)

CROP_AUDIT_FIELDS = (
    "item_kind",
    "item_id",
    "parent_event_id",
    "source_record_url",
    "disposition",
    "coverage_status",
    "http_status",
    "content_sha256",
    "archive_snapshot_url",
    "rights_status",
    "notes",
)

DUPLICATE_PAIR_FIELDS = (
    "duplicate_cluster_id",
    "left_record_id",
    "right_record_id",
    "pair_score",
    "reasons",
    "auto_merge",
    "review_state",
)


ANIMAL_TERMS: Mapping[str, tuple[str, ...]] = {
    **{taxon.normalized_common_name: taxon.terms for taxon in TAXA},
    "animal": GENERIC_ANIMAL_TERMS,
}

MUTILATION_TERMS = (
    "mutilation",
    "mutilations",
    "mutilated",
    "mutilating",
    "mutilacion",
    "mutilaciones",
    "mutilado",
    "mutilados",
    "mutilada",
    "mutiladas",
    "mutilacao",
    "mutilacoes",
    "mutilado",
    "mutile",
    "mutiles",
    "verstummelt",
    "verstummelte",
    "verstummelten",
    "verstummelung",
    "verminkt",
    "verminkte",
    "verminking",
)

HARM_TERMS = (
    "carcass",
    "carcasses",
    "corpse",
    "dead",
    "death",
    "died",
    "killed",
    "slain",
    "gutted",
    "dissected",
    "drained",
    "bloodless",
    "no blood",
    "sin sangre",
    "sem sangue",
    "cadaver",
    "cadaveres",
    "mort",
    "morte",
    "muerto",
    "muertos",
    "dood",
    "tot",
)

DISTINCTIVE_HARM_TERMS = (
    "carcass",
    "carcasses",
    "gutted",
    "dissected",
    "drained",
    "bloodless",
    "no blood",
    "sin sangre",
    "sem sangue",
    "mashed up",
    "crushed and bloodless",
)

ANATOMY_TERMS = (
    "tongue",
    "eye",
    "eyes",
    "ear",
    "ears",
    "jaw",
    "udder",
    "rectum",
    "anus",
    "genital",
    "sexual organ",
    "hide removed",
    "tissue removed",
    "incision",
    "puncture",
    "surgical precision",
    "turned inside out",
)

INCIDENT_TERMS = (
    "found",
    "discovered",
    "reported",
    "occurred",
    "killed",
    "died",
    "investigated",
    "located",
    "recovered",
    "hallado",
    "encontrado",
    "encontrados",
    "encontrada",
    "encontradas",
    "gevonden",
    "gefunden",
)

CROP_TERMS = (
    "crop circle",
    "crop circles",
    "crop formation",
    "crop formations",
    "formation in the field",
    "graancirkel",
    "graancirkels",
    "kornkreis",
    "kornkreise",
    "circulo de cultivo",
    "circulos de cultivo",
    "agroglifo",
    "agroglifos",
)

UFO_ASSOCIATION_TERMS = (
    "ufo",
    "uap",
    "flying saucer",
    "unidentified object",
    "strange light",
    "mystery helicopter",
    "unmarked helicopter",
    "helicopter",
    "aircraft",
)

NOISE_TERMS = (
    "book",
    "article",
    "publication",
    "edition",
    "publisher",
    "conference",
    "researcher",
    "theory",
    "radio appearance",
    "television",
    "movie",
    "film",
    "fiction",
    "review",
    "research biography",
    "biography",
    "skeptic",
    "skeptics",
    "skeptical",
    "debunk",
    "debunked",
    "hoax",
    "fictional",
)

INVESTIGATION_TERMS = (
    "investigation",
    "investigator",
    "sheriff",
    "police",
    "veterinarian",
    "veterinary",
    "necropsy",
    "laboratory",
    "task force",
)

NEGATIVE_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bno\s+(?:evidence\s+of\s+)?(?:cattle\s+|animal\s+|livestock\s+)?mutilat",
        r"\bnot\s+(?:been\s+)?mutilat\w*\b",
        r"\b(?:no|none\s+of\s+the)\s+(?:[a-z0-9-]+\s+){0,5}(?:was|were|had\s+been)?\s*mutilat\w*\b",
        r"\bnot\s+(?:a\s+)?(?:classic\s+)?mutilation\b",
        r"\black(?:ed|s|ing)?\s+(?:the\s+)?(?:classic\s+)?mutilation\s+features\b",
        r"\bdid\s+not\s+(?:have|show)\s+(?:the\s+)?(?:classic\s+)?mutilation\s+features\b",
        r"\bno\s+mutilations?\s+(?:occurred|were\s+found|reported)\b",
        r"\bno\s+mutilation\s+(?:connection|link|association)\b",
        r"\bno\s+(?:obvious\s+)?(?:marks?|injur(?:y|ies)|wounds?)\s+(?:on|at|were|found|visible)\b",
        r"\bno\s+(?:obvious\s+)?(?:marks?|injur(?:y|ies)|wounds?)(?:\s+or\s+(?:marks?|injur(?:y|ies)|wounds?))?.{0,35}\b(?:initial\s+find|visible|observed)\b",
        r"\b(?:likely|possibly|probably)\s+(?:coyotes?|predators?|scavengers?)\b",
        r"\b(?:coyotes?|predators?|scavengers?)\s+(?:likely|possibly|probably)\b",
        r"\bno\s+(?:organs?|tissue|hide|skin|tongue|eyes?|ears?|udder|genitals?|sexual\s+organs?|rectum|anus|jaw|head|neck|torso|limbs?|legs?)\s+(?:(?:was|were|are|is)\s+)?(?:missing|absent|removed|excised|severed|cut\s+out|stripped|cored)\b",
        r"\b(?:organs?|tissue|hide|skin|tongue|eyes?|ears?|udder|genitals?|sexual\s+organs?|rectum|anus|jaw|head|neck|torso|limbs?|legs?)\s+(?:(?:was|were|are|is)\s+)?(?:not|never)\s+(?:missing|absent|removed|excised|severed|cut\s+out|stripped|cored)\b",
    )
)

PRIVATE_LOCATION_RE = re.compile(
    r"\b(?:ranch|farm|homestead|residence|home|private property|\d{1,6}\s+[A-Za-z].*(?:road|rd\.?|street|st\.?|avenue|ave\.?|lane|ln\.?|drive|dr\.?))\b",
    re.IGNORECASE,
)

PUBLIC_EXCERPT_PRIVATE_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "[email withheld]"),
    (
        r"(?<!\d)[+-]?\d{1,2}\.\d{3,}\s*[,/]\s*[+-]?\d{1,3}\.\d{3,}(?!\d)",
        "[coordinates withheld]",
    ),
    (
        r"\b\d{1,6}(?:\s*[-\N{EN DASH}\N{EM DASH}]\s*\d{1,6})?\s+"
        r"(?!(?:mutilated|mutilation|dead|died|injured|year|month|day|animal|animals|"
        r"cattle|cow|calf|steer|bull|horse|dog|dogs|cat|cats|sheep|goat|pig)\b)"
        r"(?:[A-Za-z][A-Za-z0-9.'\N{RIGHT SINGLE QUOTATION MARK}-]*\s+){1,6}"
        r"(?:Road|Rd\.?|Street|St\.?|Avenue|Ave\.?|Lane|Ln\.?|Drive|Dr\.?|Highway|Hwy\.?)\b",
        "[street address withheld]",
    ),
    (
        r"(?<!\d)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}(?!\d)",
        "[phone withheld]",
    ),
)

_PRIVATE_PROPERTY_NONNAME_TOKENS = (
    "at|near|the|on|from|inside|outside|a|an|private|family|local|nearby|working|"
    "small|large|old|new|this|that|his|her|their|our|was|were|is|are|found|"
    "discovered|located|reported|mutilated|mutilation|mutilations|gutted|"
    "eviscerated|bloodless|decapitated|beheaded|drained|skinned|dissected|"
    "excised|severed|removed|missing|killed|dead|died|injured|wounded|"
    "slaughtered|carcass|carcasses|corpse|animal|animals|livestock|pet|pets|"
    "mammal|mammals|cow|cows|cattle|calf|calves|steer|steers|bull|bulls|"
    "ox|oxen|horse|horses|donkey|donkeys|mule|mules|sheep|ewe|ewes|ram|rams|"
    "lamb|lambs|goat|goats|pig|pigs|hog|hogs|boar|boars|bison|buffalo|yak|"
    "yaks|llama|llamas|alpaca|alpacas|cat|cats|dog|dogs|bird|birds|chicken|"
    "chickens|hen|hens|rooster|roosters|turkey|turkeys|duck|ducks|goose|geese|"
    "fish|deer|elk|moose|antelope|pronghorn|rabbit|rabbits|hare|hares|whale|"
    "whales|dolphin|dolphins|reptile|reptiles|lizard|lizards|frog|frogs|"
    "amphibian|amphibians"
)
_CAPITALIZED_PRIVATE_PROPERTY_TOKEN = (
    rf"(?!(?i:(?:{_PRIVATE_PROPERTY_NONNAME_TOKENS}))\b)"
    r"[A-Z][A-Za-z0-9&.'\N{RIGHT SINGLE QUOTATION MARK}-]*"
)
_LOWERCASE_PRIVATE_PROPERTY_TOKEN = (
    rf"(?!(?:{_PRIVATE_PROPERTY_NONNAME_TOKENS})\b)"
    r"[a-z][a-z0-9&.'\N{RIGHT SINGLE QUOTATION MARK}-]*"
)
NAMED_PRIVATE_PROPERTY_LABEL_RE = re.compile(
    rf"(?:\b{_CAPITALIZED_PRIVATE_PROPERTY_TOKEN}"
    rf"(?:\s+(?:(?:and|&)\s+)?{_CAPITALIZED_PRIVATE_PROPERTY_TOKEN}){{0,3}}"
    r"\s+(?i:ranch|farm|homestead)\b|"
    rf"\b{_LOWERCASE_PRIVATE_PROPERTY_TOKEN}"
    rf"(?:\s+(?:(?:and|&)\s+)?{_LOWERCASE_PRIVATE_PROPERTY_TOKEN}){{0,3}}"
    r"\s+(?i:ranch|farm|homestead)\b)",
)

_PUBLIC_URL_START = r"(?:https?:(?:/{0,2})?|www\.)"
_PUBLIC_MARKDOWN_URL_START = r"(?:https?(?::/{0,2})?|www\.)"
PUBLIC_INLINE_MARKDOWN_LINK_START_RE = re.compile(
    rf"\[(?P<label>[^\]\r\n]{{1,240}})\]\(\s*<?(?={_PUBLIC_MARKDOWN_URL_START})",
    re.IGNORECASE,
)
PUBLIC_MARKDOWN_LINK_RE = re.compile(
    rf"\[[^\]\r\n]{{1,240}}\]\s*(?:\(\s*<?{_PUBLIC_MARKDOWN_URL_START}|\[[^\]\r\n]{{0,120}}\])",
    re.IGNORECASE,
)
PUBLIC_REFERENCE_DEFINITION_RE = re.compile(
    rf"^[ \t]{{0,3}}\[(?P<label>[^\]\r\n]{{1,120}})\]:[ \t]*<?{_PUBLIC_URL_START}[^\r\n]*(?:\r?\n|$)",
    re.IGNORECASE | re.MULTILINE,
)
PUBLIC_REFERENCE_LINK_RE = re.compile(
    r"\[([^\]\r\n]{1,240})\]\s*\[[^\]\r\n]{0,120}\]"
)
PUBLIC_AUTOLINK_RE = re.compile(
    rf"<\s*{_PUBLIC_URL_START}[^>\r\n]*(?:>|$)",
    re.IGNORECASE,
)
PUBLIC_ORPHAN_MARKDOWN_DESTINATION_RE = re.compile(
    rf"\]?\(\s*<?{_PUBLIC_MARKDOWN_URL_START}[^\s<>\[\]]*",
    re.IGNORECASE,
)
PUBLIC_BARE_URL_RE = re.compile(
    rf"(?<![\w@]){_PUBLIC_URL_START}[^\s<>\[\]]*",
    re.IGNORECASE,
)

NARRATIVE_KEY_RE = re.compile(
    r"(?:^|[/_ -])(?:description|desc|narrative|notes?|comments?|explanation|hatchdesc|short description|long description)(?:$|[/_ -])",
    re.IGNORECASE,
)

REFERENCE_KEY_RE = re.compile(r"^(?:ref(?:erence)?|url|link)(?:[/_ -]|$)", re.IGNORECASE)
STRUCTURED_KEY_RE = re.compile(r"^(?:attributes?|types?)(?:[/_ -]|$)", re.IGNORECASE)


class SeedPipelineError(RuntimeError):
    """Raised when a locked input or scientific invariant fails."""


@dataclass(frozen=True)
class Analysis:
    candidate_score: float
    incident_likelihood: float
    candidate_reasons: tuple[str, ...]
    record_type: str
    disposition: str
    needs_human_review: bool
    animal_terms: tuple[str, ...]
    animal_assertions: tuple[AnimalAssertion, ...]
    context_animal_assertions: tuple[AnimalAssertion, ...]
    incident_evidence_mode: str
    incident_evidence_sentences: tuple[str, ...]
    finding_terms: tuple[str, ...]
    association_terms: tuple[str, ...]
    explicit_aerial_association_terms: tuple[str, ...]
    noise_terms: tuple[str, ...]
    explicit_negative: bool
    negative_only: bool
    crop_signal: bool
    explicit_crop_mutilation_link: bool
    crop_relationship_type: str | None
    narrative_text: str
    reference_text: str
    structured_codes: tuple[str, ...]


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._suppressed = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self._suppressed += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"} and self._suppressed:
            self._suppressed -= 1

    def handle_data(self, data: str) -> None:
        if not self._suppressed and data.strip():
            self.parts.append(data)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(4 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def verify_file_hash(path: Path, expected: str, label: str) -> str:
    if not path.is_file():
        raise SeedPipelineError(f"{label} not found: {path}")
    actual = sha256_file(path)
    if actual.lower() != expected.lower():
        raise SeedPipelineError(
            f"{label} SHA-256 mismatch: expected {expected.upper()}, got {actual.upper()}"
        )
    return actual


def stable_id(prefix: str, *parts: object, length: int = 24) -> str:
    payload = "\x1f".join("" if part is None else str(part) for part in parts)
    return f"{prefix}_{sha256_bytes(payload.encode('utf-8'))[:length]}"


def canonical_json(record: Mapping[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def normalize_space(value: object) -> str:
    return re.sub(r"\s+", " ", "" if value is None else str(value)).strip()


def _strip_balanced_inline_markdown_urls(value: str) -> str:
    """Keep link labels while removing complete or truncated URL destinations."""

    output: list[str] = []
    cursor = 0
    while match := PUBLIC_INLINE_MARKDOWN_LINK_START_RE.search(value, cursor):
        output.append(value[cursor : match.start()])
        output.append(match.group("label"))
        destination_start = match.end()
        depth = 1
        position = destination_start
        while position < len(value):
            char = value[position]
            if char == "(" and (position == 0 or value[position - 1] != "\\"):
                depth += 1
            elif char == ")" and (position == 0 or value[position - 1] != "\\"):
                depth -= 1
                if depth == 0:
                    cursor = position + 1
                    break
            position += 1
        else:
            # The source or an upstream evidence window may already have cut
            # the Markdown link. Drop the URL-shaped token but retain later
            # prose so an animal/harm assertion is not lost with the locator.
            whitespace = re.search(r"\s", value[destination_start:])
            cursor = (
                destination_start + whitespace.start()
                if whitespace is not None
                else len(value)
            )
    output.append(value[cursor:])
    return "".join(output)


def strip_public_link_locators(value: object) -> str:
    """Remove Web locators from evidence without removing factual link labels."""

    text = html.unescape("" if value is None else str(value))
    reference_labels: set[str] = set()

    def remove_definition(match: re.Match[str]) -> str:
        reference_labels.add(normalize_space(match.group("label")).casefold())
        return " "

    text = PUBLIC_REFERENCE_DEFINITION_RE.sub(remove_definition, text)
    text = _strip_balanced_inline_markdown_urls(text)
    text = PUBLIC_REFERENCE_LINK_RE.sub(r"\1", text)
    if reference_labels:
        shortcut_reference_re = re.compile(r"\[([^\]\r\n]{1,120})\]")

        def replace_shortcut_reference(match: re.Match[str]) -> str:
            label = normalize_space(match.group(1))
            return label if label.casefold() in reference_labels else match.group(0)

        text = shortcut_reference_re.sub(replace_shortcut_reference, text)
    text = PUBLIC_AUTOLINK_RE.sub("", text)
    text = PUBLIC_ORPHAN_MARKDOWN_DESTINATION_RE.sub("", text)
    text = PUBLIC_BARE_URL_RE.sub("", text)
    return normalize_space(text)


def contains_public_link_locator(value: object) -> bool:
    """Detect complete and truncated link forms forbidden in public evidence."""

    text = "" if value is None else str(value)
    return any(
        pattern.search(text) is not None
        for pattern in (
            PUBLIC_MARKDOWN_LINK_RE,
            PUBLIC_REFERENCE_DEFINITION_RE,
            PUBLIC_REFERENCE_LINK_RE,
            PUBLIC_AUTOLINK_RE,
            PUBLIC_ORPHAN_MARKDOWN_DESTINATION_RE,
            PUBLIC_BARE_URL_RE,
        )
    )


def normalize_for_match(value: object) -> str:
    text = unicodedata.normalize("NFKD", normalize_space(value).casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def unique_strings(values: Iterable[object]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = normalize_space(value)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


@lru_cache(maxsize=None)
def _compiled_term_pattern(terms: tuple[str, ...]) -> re.Pattern[str]:
    normalized_terms = sorted(
        {normalize_for_match(term) for term in terms if normalize_for_match(term)},
        key=lambda term: (-len(term), term),
    )
    if not normalized_terms:
        return re.compile(r"(?!x)x")
    return re.compile(
        r"(?<![a-z0-9])(?:" + "|".join(re.escape(term) for term in normalized_terms) + r")(?![a-z0-9])"
    )


def _contains_terms(normalized_text: str, terms: Iterable[str]) -> bool:
    return _compiled_term_pattern(tuple(terms)).search(normalized_text) is not None


def matched_terms(text: str, terms: Iterable[str]) -> tuple[str, ...]:
    normalized = normalize_for_match(text)
    return tuple(sorted({match.group(0) for match in _compiled_term_pattern(tuple(terms)).finditer(normalized)}))


def animal_matches(text: str) -> tuple[str, ...]:
    normalized = normalize_for_match(text)
    species: set[str] = set()
    for label, terms in ANIMAL_TERMS.items():
        if _contains_terms(normalized, terms):
            species.add(label)
    return tuple(sorted(species))


def terms_within(text: str, left_terms: Iterable[str], right_terms: Iterable[str], max_chars: int) -> bool:
    normalized = normalize_for_match(text)
    left_positions = [match.start() for match in _compiled_term_pattern(tuple(left_terms)).finditer(normalized)]
    right_positions = [match.start() for match in _compiled_term_pattern(tuple(right_terms)).finditer(normalized)]
    return any(abs(left - right) <= max_chars for left in left_positions for right in right_positions)


def extract_text_lanes(record: Mapping[str, Any]) -> tuple[str, str, tuple[str, ...]]:
    narrative: list[object] = [record.get("description"), record.get("summary")]
    references: list[object] = [record.get("source_url")]
    structured: list[str] = [normalize_space(record.get("type_raw")), normalize_space(record.get("type_normalized"))]
    raw_fields = record.get("raw_fields")
    if isinstance(raw_fields, Mapping):
        for key, value in raw_fields.items():
            if not isinstance(value, (str, int, float)) or not normalize_space(value):
                continue
            key_text = normalize_space(key)
            if STRUCTURED_KEY_RE.search(key_text):
                structured.append(normalize_space(value))
            elif REFERENCE_KEY_RE.search(key_text):
                references.append(value)
            elif NARRATIVE_KEY_RE.search(key_text):
                narrative.append(value)
    narrative_text = "\n".join(unique_strings(narrative))
    reference_text = "\n".join(unique_strings(references))
    codes: set[str] = set()
    for value in structured:
        for token in re.findall(r"(?<![A-Z0-9])[A-Z]{2,5}(?![A-Z0-9])", value):
            codes.add(token)
    return narrative_text, reference_text, tuple(sorted(codes))


def public_http_url(value: object) -> str | None:
    """Return a usable public HTTP(S) URL without promoting legacy HTML links.

    Some legacy source rows store an HTML anchor such as
    ``<a href="timeline.html#...">`` in ``source_url``.  That value is useful
    to the narrative scanner, but it is neither an absolute source URL nor a
    valid public citation for the case schema.  Absolute links embedded in an
    anchor are retained; relative and malformed values remain available via
    the raw-record locator instead of being rewritten into invented URLs.
    """

    text = normalize_space(value)
    if not text:
        return None
    href = re.search(r"\bhref\s*=\s*(['\"])(.*?)\1", text, flags=re.IGNORECASE)
    if href:
        text = html.unescape(href.group(2)).strip()
    try:
        parsed = urlsplit(text)
    except ValueError:
        return None
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None
    return text


def analyze_source_record(record: Mapping[str, Any]) -> Analysis:
    narrative, references, structured_codes = extract_text_lanes(record)
    narrative_match = normalize_for_match(narrative)
    type_text = normalize_for_match(" ".join(unique_strings([record.get("type_raw"), record.get("type_normalized")])))
    structured_type_signal = "mutilation related" in type_text or "mutilation_related" in type_text
    structured_code_signal = {"ANI", "INJ"}.issubset(set(structured_codes))
    animal_analysis = analyze_incident_animals(narrative)
    animal_lexicon = tuple(term for terms in ANIMAL_TERMS.values() for term in terms)
    animals = victim_labels(animal_analysis)
    all_animals = animal_analysis.all_animal_terms
    broad_relevant = (
        _contains_terms(narrative_match, MUTILATION_TERMS)
        or animal_analysis.evidence_mode != "none"
        or (has_any_animal_term(narrative) and animal_analysis.nonclassic_harm_only)
        or structured_type_signal
        or structured_code_signal
    )
    if not broad_relevant:
        return Analysis(
            candidate_score=0.0,
            incident_likelihood=0.0,
            candidate_reasons=(),
            record_type="related_ground_event",
            disposition="not_candidate",
            needs_human_review=False,
            animal_terms=(),
            animal_assertions=(),
            context_animal_assertions=(),
            incident_evidence_mode="none",
            incident_evidence_sentences=(),
            finding_terms=(),
            association_terms=(),
            explicit_aerial_association_terms=(),
            noise_terms=(),
            explicit_negative=False,
            negative_only=False,
            crop_signal=False,
            explicit_crop_mutilation_link=False,
            crop_relationship_type=None,
            narrative_text=narrative,
            reference_text=references,
            structured_codes=structured_codes,
        )
    mutilation = matched_terms(narrative, MUTILATION_TERMS)
    harm = matched_terms(narrative, HARM_TERMS)
    incidents = matched_terms(narrative, INCIDENT_TERMS)
    crops = matched_terms(narrative, CROP_TERMS)
    associations = matched_terms(narrative, UFO_ASSOCIATION_TERMS)
    noise = matched_terms(narrative, NOISE_TERMS)
    investigation = matched_terms(narrative, INVESTIGATION_TERMS)
    explicit_negative = any(pattern.search(narrative) for pattern in NEGATIVE_PATTERNS)
    explicit_phrase = bool(animals and animal_analysis.evidence_mode == "explicit_mutilation")
    distinctive_injury = bool(animals and animal_analysis.evidence_mode == "distinctive_injury")
    sentence_local_incident = bool(explicit_phrase or distinctive_injury)
    record_year_match = re.match(r"^(\d{4})", normalize_space(record.get("date_iso")))
    record_year = int(record_year_match.group(1)) if record_year_match else None

    def is_current_positive_evidence(sentence: str) -> bool:
        normalized = normalize_for_match(sentence)
        relative_unit = r"(?:day|week|month|year)(?:s|\s+s)?"
        relative_quantity = (
            r"(?:(?:a|the)\s+)?"
            r"(?:(?:\d+(?:\s+to\s+\d+)?|one|two|three|four|five|six|seven|"
            r"eight|nine|ten|few|several|many|multiple|couple\s+of|number\s+of)\s+)?"
        )
        # The outer record date belongs to the UFO/source record.  A separate
        # animal report described only as earlier, later, historical, or
        # recalled from news cannot inherit that date and enter deterministic
        # cross-domain matching as an exact animal event. Scope the temporal
        # cue to the animal/harm clause: in "helicopters flew the day before a
        # mutilated cow was discovered", the cow discovery is the reference
        # event and remains current rather than inheriting the helicopter cue.
        relative_marker = re.compile(
            rf"\b{relative_quantity}{relative_unit}\s+"
            r"(?:before|after|later|earlier|prior\s+to|following)\b|"
            rf"\b(?:in|during)\s+(?:the\s+)?{relative_quantity}{relative_unit}\s+"
            r"(?:before|after|prior\s+to|following)\b|"
            r"\b(?:the\s+)?next\s+(?:morning|day|night|afternoon|evening)\b|"
            r"\bback\s+in\s+the\s+day\b|"
            r"\bpreviously\b|"
            rf"\b(?:in|during|over)\s+(?:the\s+)?past\s+{relative_quantity}{relative_unit}\b"
        )
        harm_anchor = re.compile(
            r"\b(?:mutilat\w*|gutted|dissected|drained|bloodless|decapitated|"
            r"skinned|carcasses?|deaths?|dead|missing\s+(?:parts?|organs?|eyes?|"
            r"ears?|tongue|udder|head|limbs?))\b"
        )
        introductory_only = re.compile(
            r"(?:(?:about|roughly|approximately|around|some|in|during|over|the|past)\s*)*"
        )
        for relative_match in relative_marker.finditer(normalized):
            prefix = normalized[: relative_match.start()].strip()
            suffix = normalized[relative_match.end() :]
            marker_text = relative_match.group(0)
            shifts_following_animal_clause = bool(
                re.search(r"\b(?:later|after|following|next)\b", marker_text)
                and harm_anchor.search(suffix)
            )
            if (
                introductory_only.fullmatch(prefix)
                or harm_anchor.search(prefix)
                or shifts_following_animal_clause
            ):
                return False
        if re.search(
            r"\b(?:prior|previous|historical(?:ly)?)\b.{0,60}\bmutilat\w*\b|"
            r"\bmutilat\w*\b.{0,60}\b(?:in\s+the\s+past|years?\s+ago|decades?\s+ago)\b",
            normalized,
        ):
            return False
        if re.search(
            r"\bmutilat\w*\b.{0,140}\b(?:(?:were|was|have\s+been|had\s+been|being)?\s*"
            r"consistently\s+reported|reported\s+consistently|"
            r"for\s+(?:well\s+)?over\s+(?:a\s+)?decade|"
            r"throughout\s+(?:the\s+)?(?:area|region))\b",
            normalized,
        ):
            return False
        mentioned_decade = re.search(r"\bin\s+(?:the\s+)?((?:18|19|20)\d0)s\b", normalized)
        if mentioned_decade and record_year is not None:
            decade_start = int(mentioned_decade.group(1))
            if not decade_start <= record_year <= decade_start + 9:
                return False
        return True

    current_positive_evidence = any(
        is_current_positive_evidence(sentence)
        for sentence in animal_analysis.evidence_sentences
    )
    background_without_incident = bool(
        not sentence_local_incident
        and re.search(
            r"\b(?:historical(?:ly)?|prior|previous)\b.{0,80}\bmutilat\w*\b|"
            r"\bmutilat\w*\b.{0,80}\b(?:in\s+the\s+past|years?\s+ago|decades?\s+ago)\b",
            narrative_match,
        )
    )
    background_only = bool(
        sentence_local_incident and not current_positive_evidence
        or background_without_incident
    )
    negative_only = bool(explicit_negative and not current_positive_evidence)

    score = 0.0
    reasons: list[str] = []
    if explicit_phrase:
        score += 0.78
        reasons.append("sentence_local_animal_mutilation")
    elif distinctive_injury:
        score += 0.62
        reasons.append("sentence_local_distinctive_animal_injury")
    elif all_animals and mutilation:
        score += 0.24
        reasons.append("animal_and_mutilation_context_without_victim_binding")
    elif animal_analysis.nonclassic_harm_only:
        score += 0.12
        reasons.append("nonclassic_animal_harm_context")
    if structured_type_signal:
        score += 0.22
        reasons.append("mutilation_related_source_type")
    if structured_code_signal:
        score += 0.12
        reasons.append("structured_animal_injury_codes_review_only")
    if incidents and sentence_local_incident:
        score += 0.12
        reasons.append("incident_verb_in_sentence_local_animal_context")
    if crops:
        reasons.append("crop_circle_narrative_signal")
    if associations:
        reasons.append("ufo_or_aerial_narrative_signal")
    if explicit_negative:
        reasons.append("explicit_negative_or_nonclassic_statement")
        if negative_only:
            score -= 0.30
    if background_only:
        reasons.append("historical_or_background_context_only")
    if noise and not incidents:
        score -= 0.18
        reasons.append("research_or_publication_context")
    score = round(max(0.0, min(1.0, score)), 4)

    plausible_signal = bool(
        score >= 0.20
        or structured_type_signal
        or structured_code_signal
        or explicit_negative and (all_animals or mutilation)
    )
    publication_or_biography_context = bool(
        noise
        and (
            re.search(
                r"\b(?:researcher|author|writer|skeptic|biograph\w*|book|article|"
                r"edition|publisher|film|conference)\b.{0,180}\b(?:mutilat\w*|claims?|theor\w*)\b",
                narrative_match,
            )
            or re.search(
                r"\b(?:mutilat\w*|claims?|theor\w*)\b.{0,180}\b(?:researcher|author|"
                r"writer|skeptic|biograph\w*|book|article|edition|publisher|film|conference|hoax)\b",
                narrative_match,
            )
        )
    )
    has_incident_sentence = any(
        re.search(
            r"\b(?:found|discovered|located|recovered|killed|died|hallado|hallada|encontrado|encontrada|gevonden|gefunden)\b",
            normalize_for_match(sentence),
        )
        for sentence in animal_analysis.evidence_sentences
    )
    if has_incident_sentence:
        publication_or_biography_context = False
    aggregate_match_text = (
        normalize_for_match(" ".join(animal_analysis.evidence_sentences))
        or narrative_match
    )
    has_individual_incident_anchor = bool(
        has_incident_sentence
        or re.search(
            r"\b(?:one|a|an|the)\b.{0,80}\b(?:was|were)?\s*(?:found|discovered|located|recovered)\b",
            aggregate_match_text,
        )
    )
    quantified_case_pattern = re.compile(
        r"\b(?:there\s+(?:were|are|have\s+been)\s+|a\s+total\s+of\s+)?"
        r"(?:about\s+|approximately\s+|more\s+than\s+|at\s+least\s+)?"
        r"(?:\d[\d,.]*|dozens?|scores?|hundreds?|thousands?|many|multiple|numerous)\s+"
        r"[^.!?;]{0,90}\b(?:mutilation\s+)?(?:cases?|incidents?|reports?|mutilations)\b"
    )
    aggregate_scope_signal = re.search(
        r"\b(?:series|wave|overview|across|throughout|nationwide|regionwide|"
        r"cases?\s+(?:were|have|reported)|total\s+(?:number|count|of\s+cases?))\b",
        aggregate_match_text,
    )
    aggregate_context = bool(
        (quantified_case_pattern.search(aggregate_match_text) or aggregate_scope_signal)
        and not has_individual_incident_anchor
    )
    direct_incident = bool(
        animals
        and sentence_local_incident
        and not negative_only
        and not background_only
        and not aggregate_context
        and not publication_or_biography_context
    )
    if direct_incident and not aggregate_context:
        record_type = "mutilation_case"
    elif aggregate_context and (all_animals or mutilation):
        record_type = "aggregate_report"
    elif noise and not incidents:
        record_type = "publication_event"
    elif investigation and not direct_incident:
        record_type = "investigative_event"
    elif associations and not direct_incident:
        record_type = "related_aerial_event"
    else:
        record_type = "related_ground_event"

    if not plausible_signal:
        disposition = "not_candidate"
    elif structured_code_signal and not (animals or mutilation or distinctive_injury):
        disposition = "structured_code_review"
    elif negative_only:
        disposition = "explicit_negative_context"
    elif background_only:
        disposition = "context_or_noise_candidate"
    elif noise and not direct_incident:
        disposition = "context_or_noise_candidate"
    else:
        disposition = "candidate"

    incident_likelihood = score
    if record_type != "mutilation_case":
        incident_likelihood = min(incident_likelihood, 0.49)
    if negative_only:
        incident_likelihood = min(incident_likelihood, 0.20)
    incident_likelihood = round(incident_likelihood, 4)
    crop_relationship_type = classify_explicit_crop_relationship(
        narrative,
        direct_incident=direct_incident,
        has_crop_signal=bool(crops),
    )
    explicit_crop_link = crop_relationship_type is not None
    explicit_aerial_terms = locally_linked_aerial_terms(
        narrative,
        direct_incident=direct_incident,
    )
    return Analysis(
        candidate_score=score,
        incident_likelihood=incident_likelihood,
        candidate_reasons=tuple(sorted(set(reasons))),
        record_type=record_type,
        disposition=disposition,
        needs_human_review=plausible_signal,
        animal_terms=animals,
        animal_assertions=animal_analysis.victim_assertions,
        context_animal_assertions=animal_analysis.context_assertions,
        incident_evidence_mode=animal_analysis.evidence_mode,
        incident_evidence_sentences=animal_analysis.evidence_sentences,
        finding_terms=tuple(sorted(set((*mutilation, *animal_analysis.evidence_terms)))),
        association_terms=tuple(sorted(set((*crops, *associations)))),
        explicit_aerial_association_terms=explicit_aerial_terms,
        noise_terms=tuple(sorted(set(noise))),
        explicit_negative=explicit_negative,
        negative_only=negative_only,
        crop_signal=bool(crops),
        explicit_crop_mutilation_link=explicit_crop_link,
        crop_relationship_type=crop_relationship_type,
        narrative_text=narrative,
        reference_text=references,
        structured_codes=structured_codes,
    )


def classify_explicit_crop_relationship(
    text: str,
    *,
    direct_incident: bool,
    has_crop_signal: bool,
) -> str | None:
    """Classify only source-stated crop/animal relationships.

    A page-wide co-occurrence is not enough.  The animal incident and crop
    formation must occur in the same sentence (topical context) and explicit
    spatial language is required for the stronger same-scene/nearby labels.
    """

    if not direct_incident or not has_crop_signal:
        return None
    animal_lexicon = tuple(term for terms in ANIMAL_TERMS.values() for term in terms)
    for sentence in re.split(r"(?<=[.!?])\s+|[\r\n]+", normalize_space(text)):
        normalized = normalize_for_match(sentence)
        if not normalized:
            continue
        if not _contains_terms(normalized, CROP_TERMS):
            continue
        if re.search(
            r"\b(?:found|discovered|located)\b.{0,50}(?:/\s*|\b(?:inside|within|in|at)\b\s*)?(?:a\s+)?\b(?:crop circle|crop formation|circulo de cultivo|graancirkel|kornkreis|agroglifo)\b",
            normalized,
        ):
            return "same_scene"
        if not _contains_terms(normalized, animal_lexicon):
            continue
        if not (
            _contains_terms(normalized, MUTILATION_TERMS)
            or _contains_terms(normalized, DISTINCTIVE_HARM_TERMS)
            or _contains_terms(normalized, ANATOMY_TERMS)
        ):
            continue
        if re.search(
            r"\b(?:cattle|cow|cows|calf|bull|steer|heifer|sheep|dog|animal|livestock|vaca|gado|rund|kuh|koe|mutilat\w*|verstummelt\w*|verminkt\w*)\b.{0,100}\b(?:inside|within|in|at|under|amid|among|surrounded by|dentro de|en el|na)\b.{0,80}\b(?:crop circle|crop formation|circulo de cultivo|graancirkel|kornkreis|agroglifo)",
            normalized,
        ) or re.search(
            r"\b(?:crop circle|crop formation|circulo de cultivo|graancirkel|kornkreis|agroglifo)\b.{0,80}\b(?:contained|held|with|inside|within)\b.{0,80}\b(?:cattle|cow|calf|sheep|dog|animal|livestock|vaca|rund|kuh|koe)\b",
            normalized,
        ) or re.search(
            r"\b(?:found|discovered|located)\b.{0,35}(?:/\s*)?\b(?:crop circle|crop formation|circulo de cultivo|graancirkel|kornkreis|agroglifo)\b",
            normalized,
        ):
            return "same_scene"
        if re.search(
            r"\b(?:beside|near|nearby|adjacent|alongside|next to|close to|junto|cerca de)\b.{0,100}\b(?:crop circle|crop formation|graancirkel|kornkreis|agroglifo)",
            normalized,
        ) or re.search(
            r"\b(?:crop circle|crop formation|graancirkel|kornkreis|agroglifo)\b.{0,100}\b(?:beside|near|nearby|adjacent|alongside|next to|close to)\b",
            normalized,
        ):
            return "reported_nearby"
        return "topical_context"
    normalized_text = normalize_for_match(text)
    if (
        terms_within(normalized_text, CROP_TERMS, animal_lexicon, 500)
        and (
            _contains_terms(normalized_text, MUTILATION_TERMS)
            or _contains_terms(normalized_text, DISTINCTIVE_HARM_TERMS)
            or _contains_terms(normalized_text, ANATOMY_TERMS)
        )
        and re.search(r"\b(?:also|even|same (?:area|region|place)|not only|along with|as well as)\b", normalized_text)
        and not re.search(r"\b(?:decades? later|years? later|elsewhere|unrelated|different (?:country|state|region)|book discusses)\b", normalized_text)
    ):
        return "topical_context"
    return None


def locally_linked_aerial_terms(text: str, *, direct_incident: bool) -> tuple[str, ...]:
    """Return aerial terms only when a sentence locally links them to the animal incident.

    Page-wide co-occurrence is contextual retrieval evidence, not a source-stated
    animal/UFO relationship.  The strict same-sentence and linking-language rule
    intentionally leaves looser narratives for human review without promoting
    them to ``reported_nearby``.
    """

    if not direct_incident:
        return ()
    animal_lexicon = tuple(term for terms in ANIMAL_TERMS.values() for term in terms)
    linked_terms: set[str] = set()
    for sentence in re.split(r"(?<=[.!?])\s+|[\r\n]+", normalize_space(text)):
        normalized = normalize_for_match(sentence)
        aerial_terms = matched_terms(normalized, UFO_ASSOCIATION_TERMS)
        if not aerial_terms or not _contains_terms(normalized, animal_lexicon):
            continue
        if not (
            _contains_terms(normalized, MUTILATION_TERMS)
            or _contains_terms(normalized, DISTINCTIVE_HARM_TERMS)
            or _contains_terms(normalized, ANATOMY_TERMS)
        ):
            continue
        if not re.search(
            r"\b(?:near|nearby|beside|alongside|over|above|at\s+the\s+scene|at\s+the\s+site|"
            r"same\s+(?:scene|site|field|area|time|night)|while|when|during|before|after|following)\b",
            normalized,
        ):
            continue
        linked_terms.update(aerial_terms)
    return tuple(sorted(linked_terms))


def short_evidence_excerpt(
    text: str,
    terms: Sequence[str],
    *,
    max_words: int = 24,
    max_chars: int = 240,
    withhold_named_private_property: bool = False,
) -> str | None:
    # Strip locators from the complete source string before selecting and
    # truncating the evidence window. This prevents a long URL from becoming a
    # leaking fragment or displacing the animal/harm words the excerpt needs.
    cleaned = strip_public_link_locators(text)
    if not cleaned:
        return None
    normalized = normalize_for_match(cleaned)
    position = min(
        (normalized.find(normalize_for_match(term)) for term in terms if normalize_for_match(term) in normalized),
        default=0,
    )
    approximate_ratio = position / max(1, len(normalized))
    words = cleaned.split()
    center = int(approximate_ratio * len(words))
    start = max(0, center - max_words // 3)
    excerpt = " ".join(words[start : start + max_words])
    if start:
        excerpt = "... " + excerpt
    if start + max_words < len(words):
        excerpt += " ..."
    return sanitize_public_excerpt(
        excerpt[:max_chars].rstrip(),
        withhold_named_private_property=withhold_named_private_property,
    )


def source_explicit_human_staging(text: object) -> bool:
    """Identify a narrow source statement that people deliberately staged a carcass."""

    normalized = normalize_for_match(text)
    return bool(
        re.search(
            r"\b(?:they|we|he|she|people|hoaxers?|pranksters?)\b"
            r"(?:\s+[a-z0-9-]+){0,3}\s+"
            r"(?:planted|placed|staged)\b.{0,45}\bmutilat\w*\b",
            normalized,
        )
    )


def _private_property_evidence_redaction_required(
    location: Mapping[str, Any] | None,
    *evidence_values: object,
) -> bool:
    if isinstance(location, Mapping):
        if location.get("privacy_level") == "internal_only":
            return True
        for value in location.values():
            text = normalize_space(value)
            if text and (
                PRIVATE_LOCATION_RE.search(text)
                or NAMED_PRIVATE_PROPERTY_LABEL_RE.search(text)
            ):
                return True
    return any(
        NAMED_PRIVATE_PROPERTY_LABEL_RE.search(normalize_space(value))
        for value in evidence_values
        if normalize_space(value)
    )


def _public_crop_candidate_location(
    location: Mapping[str, Any] | None,
    *,
    withhold_named_private_property: bool,
) -> dict[str, Any]:
    public_location = dict(location or {})
    if not withhold_named_private_property:
        return public_location
    for key in ("raw_text", "place", "locality", "county", "region", "admin1", "admin2"):
        value = normalize_space(public_location.get(key))
        if value and NAMED_PRIVATE_PROPERTY_LABEL_RE.search(value):
            public_location[key] = None
    return public_location


def sanitize_public_excerpt(
    value: object,
    *,
    withhold_named_private_property: bool = False,
) -> str | None:
    """Remove common private locators from short public evidence text."""

    text = strip_public_link_locators(value)
    if not text:
        return None
    if withhold_named_private_property:
        text = NAMED_PRIVATE_PROPERTY_LABEL_RE.sub(
            "[private property withheld]",
            text,
        )
    for pattern, replacement in PUBLIC_EXCERPT_PRIVATE_PATTERNS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return normalize_space(text) or None


def contains_public_private_locator(value: object) -> bool:
    """Return true for a private property, address, or Web locator."""

    text = normalize_space(value)
    return bool(
        text
        and (
            NAMED_PRIVATE_PROPERTY_LABEL_RE.search(text)
            or contains_public_link_locator(text)
            or any(
                re.search(pattern, text, flags=re.IGNORECASE)
                for pattern, _replacement in PUBLIC_EXCERPT_PRIVATE_PATTERNS
            )
        )
    )


def finding_claims(analysis: Analysis, source_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Materialize conservative, source-attributed finding claims.

    These are claims *reported by the source*, not verified observations.  The
    deliberately modest confidence and ``retelling`` basis prevent extracted
    vocabulary from being promoted to veterinary or laboratory evidence.
    """

    if analysis.negative_only:
        return [], [
            {
                "claim_type": "reported_classic_mutilation_features",
                "anatomical_site": None,
                "asserted_value": False,
                "asserted_by": None,
                "observation_basis": "retelling",
                "source_ids": [source_id],
                "confidence": 0.55,
                "contradicted_by_source_ids": [],
                "notes": "Source-explicit negative; this is not negative evidence for other incidents.",
            }
        ]
    anatomy_normalized = {normalize_for_match(term) for term in ANATOMY_TERMS}
    anatomical: list[dict[str, Any]] = []
    scene: list[dict[str, Any]] = []
    for term in analysis.finding_terms:
        normalized = normalize_for_match(term)
        if normalized in anatomy_normalized:
            anatomical.append(
                {
                    "claim_type": "reported_anatomical_finding",
                    "anatomical_site": term,
                    "asserted_value": True,
                    "asserted_by": None,
                    "observation_basis": "retelling",
                    "source_ids": [source_id],
                    "confidence": 0.5,
                    "contradicted_by_source_ids": [],
                    "notes": "Lexically extracted source claim; requires review.",
                }
            )
        else:
            scene.append(
                {
                    "claim_type": "reported_carcass_or_harm_finding",
                    "anatomical_site": None,
                    "asserted_value": term,
                    "asserted_by": None,
                    "observation_basis": "retelling",
                    "source_ids": [source_id],
                    "confidence": 0.5,
                    "contradicted_by_source_ids": [],
                    "notes": "Lexically extracted source claim; requires review.",
                }
            )
    return anatomical, scene


def map_date_precision(value: object) -> str:
    normalized = normalize_for_match(value).replace(" ", "_")
    mapping = {
        "exact_time": "exact_time",
        "datetime": "exact_time",
        "exact_day": "exact_day",
        "day": "exact_day",
        "date": "exact_day",
        "month": "month",
        "season": "season",
        "year": "year",
        "range": "range",
        "decade": "range",
        "approximate": "approximate",
    }
    return mapping.get(normalized, "unknown")


def map_location_precision(value: object) -> str:
    normalized = normalize_for_match(value)
    if "exact" in normalized or "site" in normalized:
        return "exact_site"
    if "parcel" in normalized:
        return "parcel"
    if "road" in normalized:
        return "road_segment"
    if any(term in normalized for term in ("city", "locality", "town", "village")):
        return "locality"
    if "county" in normalized:
        return "county"
    if any(term in normalized for term in ("state", "province", "admin1")):
        return "state"
    if "country" in normalized:
        return "country"
    if "approx" in normalized or "centroid" in normalized:
        return "approximate"
    return "unknown"


def normalized_date(value: object) -> str | None:
    text = normalize_space(value)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return None
    try:
        parsed = date.fromisoformat(text)
    except ValueError:
        return None
    return parsed.isoformat()


def normalized_date_interval(
    start_value: object,
    end_value: object,
    precision_value: object,
) -> dict[str, Any]:
    """Normalize without converting an uncertain start-only date into an exact day.

    Month/year precision has a deterministic calendar boundary.  Open-ended
    approximate, range, season, and unknown values retain a null end because the
    source does not establish one; this prevents false temporal matches.
    """

    precision = normalize_space(precision_value)
    if precision == "exact_time":
        precision = "exact_day"
    allowed = {"exact_day", "month", "season", "year", "range", "approximate", "unknown"}
    if precision not in allowed:
        precision = map_date_precision(precision_value)
        if precision == "exact_time":
            precision = "exact_day"
        if precision not in allowed:
            precision = "unknown"

    start = normalized_date(start_value)
    supplied_end = normalized_date(end_value)
    if start is None:
        return {"start": None, "end": None, "precision": precision}

    # A non-exact singleton is normally an upstream placeholder, not an actual
    # closed range.  Treat it as start-only and preserve the stated uncertainty.
    if supplied_end == start and precision != "exact_day":
        supplied_end = None
    if supplied_end is not None:
        if supplied_end < start:
            supplied_end = None
        else:
            return {"start": start, "end": supplied_end, "precision": precision}

    if precision == "exact_day":
        end = start
    elif precision == "month":
        parsed = date.fromisoformat(start)
        end = parsed.replace(day=monthrange(parsed.year, parsed.month)[1]).isoformat()
    elif precision == "year":
        end = f"{start[:4]}-12-31"
    else:
        end = None
    return {"start": start, "end": end, "precision": precision}


def project_location(record: Mapping[str, Any]) -> dict[str, Any]:
    raw = normalize_space(record.get("location_raw")) or None
    city = normalize_space(record.get("city")) or None
    precision = map_location_precision(record.get("location_precision"))
    lat = record.get("lat") if isinstance(record.get("lat"), (int, float)) else None
    lon = record.get("lon") if isinstance(record.get("lon"), (int, float)) else None
    year_text = normalize_space(record.get("date_iso"))[:4]
    modern = year_text.isdigit() and int(year_text) >= 1990
    private_signal = bool(raw and PRIVATE_LOCATION_RE.search(raw))
    named_private_signal = any(
        NAMED_PRIVATE_PROPERTY_LABEL_RE.search(value)
        for value in (raw, city)
        if value
    )
    precise_signal = precision in {"exact_site", "parcel", "road_segment"}
    suppress_public = named_private_signal or (
        private_signal and (modern or precise_signal)
    )
    # Some upstream records put a ranch/farm name in the city field. A
    # generalized public projection must not reintroduce the private property
    # label through that nominal locality after suppressing the raw location.
    public_city = (
        None
        if suppress_public
        and city
        and (
            PRIVATE_LOCATION_RE.search(city)
            or NAMED_PRIVATE_PROPERTY_LABEL_RE.search(city)
        )
        else city
    )
    public_lat = None if suppress_public else lat
    public_lon = None if suppress_public else lon
    public_precision = "locality" if suppress_public and public_city else ("unknown" if suppress_public else precision)
    public_raw = (
        ", ".join(
            unique_strings(
                [public_city, record.get("state_province"), record.get("country")]
            )
        )
        or None
        if suppress_public
        else raw
    )
    return {
        "raw_text": public_raw,
        "country_code": normalize_space(record.get("country")) or None,
        "admin1": normalize_space(record.get("state_province")) or None,
        "admin2": None,
        "locality": public_city if suppress_public else city,
        "latitude_internal": lat,
        "longitude_internal": lon,
        "latitude_public": public_lat,
        "longitude_public": public_lon,
        "precision": public_precision,
        "coordinate_source": normalize_space(record.get("coordinate_source")) or None,
        "geocode_query": None,
        "geocode_confidence": None,
        "privacy_level": "internal_only" if suppress_public else "public_generalized",
        "mapping_notes": (
            "Public coordinates suppressed because the source may identify a named or modern private property."
            if suppress_public
            else "Coordinates retain the upstream precision label; centroids are not exact sites."
        ),
    }


def _enforce_private_public_location(record: Mapping[str, Any]) -> None:
    """Apply the private-location projection again after checkpoint resume."""

    location = record.get("location")
    if not isinstance(location, dict) or location.get("privacy_level") != "internal_only":
        return
    location["latitude_public"] = None
    location["longitude_public"] = None

    def safe_component(value: object) -> str | None:
        text = normalize_space(value) or None
        if text and (
            PRIVATE_LOCATION_RE.search(text)
            or NAMED_PRIVATE_PROPERTY_LABEL_RE.search(text)
        ):
            return None
        return text

    locality = safe_component(location.get("locality"))
    admin2 = safe_component(location.get("admin2"))
    admin1 = safe_component(location.get("admin1"))
    country = safe_component(location.get("country_code"))
    location["locality"] = locality
    location["raw_text"] = ", ".join(
        unique_strings([locality, admin2, admin1, country])
    ) or None
    location["precision"] = "locality" if locality else "unknown"


def build_candidate_record(record: Mapping[str, Any], analysis: Analysis, source_index: int) -> dict[str, Any]:
    canonical_input_id = normalize_space(record.get("canonical_input_id"))
    source_native_id = normalize_space(record.get("source_native_id")) or None
    source_row_hash = normalize_space(record.get("source_row_hash"))
    raw_hash = sha256_bytes(canonical_json(dict(record)).encode("utf-8"))
    record_id = stable_id(
        "cmr",
        normalize_space(record.get("source_name")),
        source_native_id,
        raw_hash,
        "primary_mutilation_claim",
    )
    source_id = f"ufo:{canonical_input_id or source_native_id or record_id}"
    anatomical_findings, scene_findings = finding_claims(analysis, source_id)
    interval = normalized_date_interval(
        record.get("date_iso"),
        record.get("end_date_iso"),
        map_date_precision(record.get("date_precision")),
    )
    precision = interval["precision"]
    start = interval["start"]
    end = interval["end"]
    location = project_location(record)
    withhold_named_private_property = _private_property_evidence_redaction_required(
        location,
        analysis.narrative_text,
    )
    animal_rows = [
        assertion_to_public_row(assertion, source_id)
        for assertion in analysis.animal_assertions
    ]
    animal_context_rows = [
        assertion_to_public_row(assertion, source_id)
        for assertion in analysis.context_animal_assertions
    ]
    for animal in [*animal_rows, *animal_context_rows]:
        animal["evidence_excerpt"] = sanitize_public_excerpt(
            animal.get("evidence_excerpt"),
            withhold_named_private_property=withhold_named_private_property,
        )
    public_incident_evidence = unique_strings(
        animal.get("evidence_excerpt")
        for animal in animal_rows
        if animal.get("evidence_excerpt")
    )
    associated_events: list[dict[str, Any]] = []
    if analysis.crop_signal:
        associated_events.append(
            {
                "association_type": "crop_circle",
                "claim": {
                    "claim_type": "source_mentions_crop_formation_context",
                    "asserted_value": True,
                    "asserted_by": None,
                    "observation_basis": "retelling",
                    "source_ids": [source_id],
                    "confidence": 0.65 if analysis.explicit_crop_mutilation_link else 0.35,
                    "contradicted_by_source_ids": [],
                    "notes": "Source-stated context only; authenticity and causality are not asserted.",
                },
                "linked_record_id": None,
                "temporal_offset_hours": None,
                "distance_km": None,
            }
        )
    if analysis.explicit_aerial_association_terms:
        associated_events.append(
            {
                "association_type": (
                    "helicopter"
                    if any("helicopter" in term for term in analysis.explicit_aerial_association_terms)
                    else "uap_or_light"
                ),
                "claim": {
                    "claim_type": "source_mentions_aerial_context",
                    "asserted_value": True,
                    "asserted_by": None,
                    "observation_basis": "retelling",
                    "source_ids": [source_id],
                    "confidence": 0.45,
                    "contradicted_by_source_ids": [],
                    "notes": "Association is source-stated and does not establish a causal connection.",
                },
                "linked_record_id": None,
                "temporal_offset_hours": None,
                "distance_km": None,
            }
        )
    excerpt = short_evidence_excerpt(
        analysis.narrative_text,
        (*analysis.animal_terms, *analysis.finding_terms, *analysis.association_terms),
        withhold_named_private_property=withhold_named_private_property,
    )
    victim_excerpts = [
        normalize_space(animal.get("evidence_excerpt"))
        for animal in animal_rows
        if normalize_space(animal.get("evidence_excerpt"))
    ]
    if victim_excerpts:
        excerpt = sanitize_public_excerpt(
            min(victim_excerpts, key=lambda value: (len(value), value)),
            withhold_named_private_property=withhold_named_private_property,
        )
    elif analysis.incident_evidence_sentences:
        excerpt = sanitize_public_excerpt(
            min(
                analysis.incident_evidence_sentences,
                key=lambda sentence: (len(sentence), sentence),
            ),
            withhold_named_private_property=withhold_named_private_property,
        )
    human_staging = source_explicit_human_staging(analysis.narrative_text)
    source_title = f"{normalize_space(record.get('source_name')) or 'UFO Timeline'} record {source_native_id or canonical_input_id}"
    return {
        "event_domain": "animal_mutilation",
        "record_id": record_id,
        "canonical_incident_id": None,
        "record_type": analysis.record_type,
        "status": (
            "contested"
            if analysis.explicit_negative or human_staging
            else "lead"
        ),
        "title": source_title,
        "summary": excerpt,
        "dates": {
            "event_start": start,
            "event_end": end,
            "discovery_start": None,
            "discovery_end": None,
            "report_date": None,
            "estimated_death_start": None,
            "estimated_death_end": None,
            "precision": precision,
            "raw_text": normalize_space(record.get("date_raw")) or None,
        },
        "location": location,
        "animals": animal_rows,
        "animal_context": animal_context_rows,
        "anatomical_findings": anatomical_findings,
        "scene_findings": scene_findings,
        "laboratory_findings": [],
        "associated_events": associated_events,
        "investigation": {
            "agencies": [],
            "case_numbers": [],
            "investigators": [],
            "necropsy_performed": None,
            "veterinary_review": None,
            "official_conclusion": None,
            "disposition": (
                "source_explicit_deliberate_placement_of_mutilated_animal"
                if human_staging
                else None
            ),
            "contradictions": [],
        },
        "sources": [
            {
                "source_id": source_id,
                "tier": "C",
                "source_type": "dataset",
                "title": source_title,
                "agency_or_publisher": normalize_space(record.get("source_name")) or None,
                "publication_date": None,
                "url": public_http_url(record.get("source_url")),
                "page_or_container": f"source_records.jsonl line {source_index}",
                "archival_citation": None,
                "rights_status": "copyrighted_metadata_only",
                "raw_text_retention": "internal_only",
                "source_hash": raw_hash,
            }
        ],
        "extraction": {
            "candidate_score": analysis.candidate_score,
            "candidate_reasons": list(analysis.candidate_reasons),
            "incident_likelihood": analysis.incident_likelihood,
            "needs_human_review": analysis.needs_human_review,
            "incident_evidence_mode": analysis.incident_evidence_mode,
            "incident_evidence_sentences": public_incident_evidence,
        },
        "provenance": {
            "ingestion_adapter": "ufo_timeline_source_records_v1",
            "source_native_id": source_native_id,
            "raw_record_hash": raw_hash,
            "duplicate_cluster_id": None,
            "canonicalization_version": CANONICALIZATION_VERSION,
            "ingested_at": None,
            "review_state": "unreviewed",
            "review_notes": None,
        },
        "public_content_warning": "Animal-death and anatomical descriptions may be disturbing.",
        "related_ufo_timeline_event_ids": [],
        "external_event_refs": [],
        "direct_animal_terms": list(analysis.animal_terms),
        "finding_terms": list(analysis.finding_terms),
        "association_terms": list(analysis.association_terms),
        "explicit_aerial_association_terms": list(analysis.explicit_aerial_association_terms),
        "noise_terms": list(analysis.noise_terms),
        "structured_codes": list(analysis.structured_codes),
        "explicit_negative": analysis.explicit_negative,
        "negative_only": analysis.negative_only,
        "explicit_crop_mutilation_link": analysis.explicit_crop_mutilation_link,
        "crop_relationship_type": analysis.crop_relationship_type,
        "raw_record_pointer": {
            "dataset": "data/canonical_full/source_records.jsonl",
            "line": source_index,
            "canonical_input_id": canonical_input_id or None,
            "source_row_hash": raw_hash,
            "source_native_row_hash": source_row_hash or None,
        },
    }


def _audit_row(
    source_index: int,
    record: Mapping[str, Any] | None,
    analysis: Analysis | None,
    candidate: Mapping[str, Any] | None,
    *,
    disposition: str | None = None,
) -> dict[str, Any]:
    record = record or {}
    analysis_disposition = analysis.disposition if analysis else "malformed"
    return {
        "source_index": source_index,
        "canonical_input_id": normalize_space(record.get("canonical_input_id")),
        "source_name": normalize_space(record.get("source_name")),
        "source_native_id": normalize_space(record.get("source_native_id")),
        "source_row_hash": normalize_space(record.get("source_row_hash")),
        "record_id": normalize_space(candidate.get("record_id")) if candidate else "",
        "candidate_score": f"{analysis.candidate_score:.4f}" if analysis else "",
        "candidate_reasons": "|".join(analysis.candidate_reasons) if analysis else "",
        "record_type": analysis.record_type if analysis else "",
        "incident_likelihood": f"{analysis.incident_likelihood:.4f}" if analysis else "",
        "disposition": disposition or analysis_disposition,
        "needs_human_review": str(bool(analysis and analysis.needs_human_review)).lower(),
        "has_crop_circle_signal": str(bool(analysis and analysis.crop_signal)).lower(),
        "explicit_crop_mutilation_link": str(bool(analysis and analysis.explicit_crop_mutilation_link)).lower(),
        "duplicate_cluster_id": "",
    }


def _case_date_projection(case: Mapping[str, Any]) -> dict[str, Any]:
    dates = case.get("dates") if isinstance(case.get("dates"), Mapping) else {}
    return {
        "event_start": dates.get("event_start"),
        "event_end": dates.get("event_end"),
        "precision": normalize_space(dates.get("precision")) or "unknown",
    }


def _case_public_location_projection(case: Mapping[str, Any]) -> dict[str, Any]:
    location = case.get("location") if isinstance(case.get("location"), Mapping) else {}
    return {
        "raw_text": location.get("raw_text"),
        "country_code": location.get("country_code"),
        "admin1": location.get("admin1"),
        "admin2": location.get("admin2"),
        "locality": location.get("locality"),
        "latitude_public": location.get("latitude_public"),
        "longitude_public": location.get("longitude_public"),
        "precision": normalize_space(location.get("precision")) or "unknown",
        "privacy_level": normalize_space(location.get("privacy_level")) or "unknown",
    }


def _expected_case_projection(case: Mapping[str, Any]) -> dict[str, Any]:
    animal_fields = (
        "reported_text",
        "reported_taxon_key",
        "normalized_common_name",
        "species_group",
        "domestic_context",
        "incident_role",
        "identification_basis",
        "identification_confidence",
        "source_ids",
    )

    def animal_projection(field: str) -> list[dict[str, Any]]:
        rows = case.get(field, []) if isinstance(case.get(field), list) else []
        return sorted(
            [
                {key: row.get(key) for key in animal_fields}
                for row in rows
                if isinstance(row, Mapping)
            ],
            key=canonical_json,
        )

    return {
        "event_domain": case.get("event_domain"),
        "explicit_negative": bool(case.get("explicit_negative")),
        "negative_only": bool(case.get("negative_only")),
        "dates": _case_date_projection(case),
        "public_location": _case_public_location_projection(case),
        "animals": animal_projection("animals"),
        "animal_context": animal_projection("animal_context"),
    }


def _finish_validation_decision(
    decision: Mapping[str, Any], case: Mapping[str, Any]
) -> dict[str, Any]:
    result = json.loads(canonical_json(dict(decision)))
    expected = _expected_case_projection(case)
    result["expected"] = expected
    result["expected_projection_sha256"] = sha256_bytes(
        canonical_json(expected).encode("utf-8")
    )
    return result


def _build_ufo_validation_decision(
    record: Mapping[str, Any], case: Mapping[str, Any]
) -> dict[str, Any]:
    raw_location = normalize_space(record.get("location_raw"))
    source_city = normalize_space(record.get("city"))
    source_precision = map_location_precision(record.get("location_precision"))
    year_text = normalize_space(record.get("date_iso"))[:4]
    modern = year_text.isdigit() and int(year_text) >= 1990
    private_signal = bool(raw_location and PRIVATE_LOCATION_RE.search(raw_location))
    named_private_signal = any(
        NAMED_PRIVATE_PROPERTY_LABEL_RE.search(value)
        for value in (raw_location, source_city)
        if value
    )
    precise_signal = source_precision in {"exact_site", "parcel", "road_segment"}
    return _finish_validation_decision(
        {
            "basis": "ufo_source_record",
            "source_record_hash": normalize_space(
                case.get("provenance", {}).get("raw_record_hash")
            ),
            "source_date": {
                "start": normalized_date(record.get("date_iso")),
                "end": normalized_date(record.get("end_date_iso")),
                "precision": map_date_precision(record.get("date_precision")),
            },
            "source_location": {
                "raw_text_sha256": (
                    sha256_bytes(raw_location.encode("utf-8")) if raw_location else None
                ),
                "precision": source_precision,
                "private_signal": private_signal,
                "named_private_signal": named_private_signal,
                "public_suppression_required": bool(
                    named_private_signal
                    or (private_signal and (modern or precise_signal))
                ),
            },
        },
        case,
    )


def _build_crop_validation_decision(
    source_candidate: Mapping[str, Any], case: Mapping[str, Any]
) -> dict[str, Any]:
    source_dates = (
        source_candidate.get("dates")
        if isinstance(source_candidate.get("dates"), Mapping)
        else {}
    )
    source_location = (
        source_candidate.get("location")
        if isinstance(source_candidate.get("location"), Mapping)
        else {}
    )
    return _finish_validation_decision(
        {
            "basis": "crop_source_context",
            "source_record_hash": normalize_space(source_candidate.get("source_hash")),
            "source_date": {
                "start": normalized_date(source_dates.get("start")),
                "end": normalized_date(source_dates.get("end")),
                "precision": map_date_precision(source_dates.get("precision")),
            },
            "source_location": {
                "raw_text_sha256": None,
                "precision": map_location_precision(source_location.get("precision")),
                "private_signal": False,
                "public_suppression_required": False,
            },
        },
        case,
    )


def scan_ufo_source_records(
    source_records_path: Path,
    work_dir: Path,
    *,
    resume: bool,
    limit: int | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Stream every UFO source row into an auditable candidate spool.

    Checkpointing uses a verified source identity plus durable byte boundaries
    for both temporary spools.  Resume truncates any writes beyond the last
    committed checkpoint before appending, so an interruption cannot duplicate
    or silently skip source rows.
    """

    if not source_records_path.is_file():
        raise SeedPipelineError(f"UFO source corpus not found: {source_records_path}")
    work_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = work_dir / "ufo_scan_checkpoint.json"
    candidate_spool = work_dir / "ufo_candidates.spool.jsonl"
    audit_spool = work_dir / "extraction_audit.spool.csv"
    source_identity = _ufo_source_identity(source_records_path)
    source_size = int(source_identity["size_bytes"])
    offset = 0
    scanned = 0
    malformed = 0
    candidates_written = 0
    restored_checkpoint = False
    source_prefix_hasher = hashlib.sha256()

    resume_paths = (checkpoint_path, candidate_spool, audit_spool)
    existing_resume_paths = tuple(path.exists() for path in resume_paths)
    if resume and any(existing_resume_paths):
        if not all(existing_resume_paths):
            raise SeedPipelineError(
                "Cannot resume: checkpoint and both UFO scan spools must all exist"
            )
        try:
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SeedPipelineError("Cannot resume: UFO scan checkpoint is unreadable") from exc
        if checkpoint.get("checkpoint_schema_version") != 2:
            raise SeedPipelineError("Cannot resume: UFO scan checkpoint format changed")
        if checkpoint.get("pipeline_version") != PIPELINE_VERSION:
            raise SeedPipelineError("Cannot resume: animal-mutilation pipeline version changed")
        if checkpoint.get("source_identity") != source_identity:
            raise SeedPipelineError("Cannot resume: UFO source corpus identity changed")
        try:
            offset = int(checkpoint["byte_offset"])
            scanned = int(checkpoint["scanned"])
            malformed = int(checkpoint["malformed"])
            candidates_written = int(checkpoint["candidates_written"])
            candidate_spool_size = int(checkpoint["candidate_spool_size"])
            audit_spool_size = int(checkpoint["audit_spool_size"])
        except (KeyError, TypeError, ValueError) as exc:
            raise SeedPipelineError("Cannot resume: UFO scan checkpoint is incomplete") from exc
        if (
            offset < 0
            or offset > source_size
            or scanned < 0
            or malformed < 0
            or malformed > scanned
            or candidates_written < 0
            or candidates_written > scanned
            or candidate_spool_size < 0
            or audit_spool_size < 0
        ):
            raise SeedPipelineError("Cannot resume: UFO scan checkpoint values are invalid")
        if limit is not None and scanned > limit:
            raise SeedPipelineError("Cannot resume: --limit is below the checkpoint row count")
        if offset < source_size and offset:
            with source_records_path.open("rb") as source_boundary:
                source_boundary.seek(offset - 1)
                if source_boundary.read(1) != b"\n":
                    raise SeedPipelineError(
                        "Cannot resume: checkpoint byte offset is not a JSONL row boundary"
                    )
        _restore_spool_boundary(
            candidate_spool,
            candidate_spool_size,
            expected_lines=candidates_written,
            label="candidate",
        )
        _restore_spool_boundary(
            audit_spool,
            audit_spool_size,
            expected_lines=scanned + 1,
            label="audit",
        )
        with audit_spool.open(encoding="utf-8", newline="") as audit_check:
            if next(csv.reader(audit_check), None) != list(EXTRACTION_AUDIT_FIELDS):
                raise SeedPipelineError("Cannot resume: UFO audit spool header changed")
        source_prefix_hasher = _hash_ufo_source_prefix(source_records_path, offset)
        expected_prefix_hash = normalize_space(checkpoint.get("source_prefix_sha256"))
        if (
            not re.fullmatch(r"[a-f0-9]{64}", expected_prefix_hash)
            or source_prefix_hasher.hexdigest() != expected_prefix_hash
        ):
            raise SeedPipelineError("Cannot resume: scanned UFO source prefix changed")
        restored_checkpoint = True
    else:
        for path in resume_paths:
            path.unlink(missing_ok=True)

    candidate_mode = "a" if restored_checkpoint else "w"
    audit_mode = "a" if restored_checkpoint else "w"
    with (
        source_records_path.open("rb") as source,
        candidate_spool.open(candidate_mode, encoding="utf-8", newline="\n") as candidate_handle,
        audit_spool.open(audit_mode, encoding="utf-8", newline="") as audit_handle,
    ):
        source.seek(offset)
        audit_writer = csv.DictWriter(audit_handle, fieldnames=EXTRACTION_AUDIT_FIELDS, lineterminator="\n")
        if not restored_checkpoint:
            audit_writer.writeheader()

        def persist_checkpoint(*, complete: bool) -> None:
            candidate_handle.flush()
            audit_handle.flush()
            os.fsync(candidate_handle.fileno())
            os.fsync(audit_handle.fileno())
            if _ufo_source_identity(source_records_path) != source_identity:
                raise SeedPipelineError("UFO source corpus changed during extraction")
            _write_checkpoint(
                checkpoint_path,
                source_identity=source_identity,
                source_size=source_size,
                source_prefix_sha256=source_prefix_hasher.hexdigest(),
                byte_offset=source.tell(),
                scanned=scanned,
                malformed=malformed,
                candidates_written=candidates_written,
                candidate_spool_size=os.fstat(candidate_handle.fileno()).st_size,
                audit_spool_size=os.fstat(audit_handle.fileno()).st_size,
                complete=complete,
            )

        while limit is None or scanned < limit:
            raw_line = source.readline()
            if not raw_line:
                break
            source_prefix_hasher.update(raw_line)
            source_index = scanned + 1
            try:
                record = json.loads(raw_line)
                if not isinstance(record, dict):
                    raise ValueError("source row must be an object")
                analysis = analyze_source_record(record)
                candidate = None
                if analysis.disposition != "not_candidate":
                    candidate = build_candidate_record(record, analysis, source_index)
                    spool_record = {
                        "candidate": candidate,
                        "analysis": {
                            "disposition": analysis.disposition,
                            "crop_signal": analysis.crop_signal,
                            "explicit_crop_mutilation_link": analysis.explicit_crop_mutilation_link,
                            "crop_relationship_type": analysis.crop_relationship_type,
                            "narrative_hash": sha256_bytes(analysis.narrative_text.encode("utf-8")),
                        },
                        "validation_decision": _build_ufo_validation_decision(
                            record, candidate
                        ),
                    }
                    candidate_handle.write(canonical_json(spool_record) + "\n")
                    candidates_written += 1
                audit_writer.writerow(_audit_row(source_index, record, analysis, candidate))
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
                malformed += 1
                audit_writer.writerow(_audit_row(source_index, None, None, None))
            scanned += 1
            if scanned % 10_000 == 0:
                persist_checkpoint(complete=False)
        persist_checkpoint(complete=source.tell() >= source_size)

    candidates = [
        json.loads(line)
        for line in candidate_spool.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return candidates, {
        "scanned": scanned,
        "malformed": malformed,
        "candidate_spool": str(candidate_spool),
        "audit_spool": str(audit_spool),
        "checkpoint": str(checkpoint_path),
        "source_size_bytes": source_size,
        "candidates_written": candidates_written,
    }


def _ufo_source_identity(path: Path) -> dict[str, Any]:
    """Return a cheap, stable identity that detects ordinary source replacement.

    The rolling prefix digest in each checkpoint verifies every byte already
    consumed.  This identity additionally samples the entire file (including
    its tail) and retains the file modification time so unconsumed changes fail
    closed without adding another multi-gigabyte full-file read to every run.
    """

    stat = path.stat()
    sample_size = 1024 * 1024
    positions = {
        0,
        max(0, stat.st_size // 4 - sample_size // 2),
        max(0, stat.st_size // 2 - sample_size // 2),
        max(0, stat.st_size * 3 // 4 - sample_size // 2),
        max(0, stat.st_size - sample_size),
    }
    digest = hashlib.sha256()
    digest.update(str(stat.st_size).encode("ascii"))
    with path.open("rb") as handle:
        for position in sorted(positions):
            handle.seek(position)
            sample = handle.read(sample_size)
            digest.update(position.to_bytes(8, "big", signed=False))
            digest.update(len(sample).to_bytes(8, "big", signed=False))
            digest.update(sample)
    return {
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sampled_content_sha256": digest.hexdigest(),
    }


def _hash_ufo_source_prefix(path: Path, byte_count: int) -> Any:
    digest = hashlib.sha256()
    remaining = byte_count
    with path.open("rb") as handle:
        while remaining:
            chunk = handle.read(min(4 * 1024 * 1024, remaining))
            if not chunk:
                raise SeedPipelineError("Cannot resume: UFO source prefix is truncated")
            digest.update(chunk)
            remaining -= len(chunk)
    return digest


def _restore_spool_boundary(
    path: Path,
    saved_size: int,
    *,
    expected_lines: int,
    label: str,
) -> None:
    actual_size = path.stat().st_size
    if actual_size < saved_size:
        raise SeedPipelineError(
            f"Cannot resume: {label} spool is shorter than its checkpoint boundary"
        )
    with path.open("r+b") as handle:
        if actual_size != saved_size:
            handle.truncate(saved_size)
        handle.flush()
        os.fsync(handle.fileno())
    with path.open("rb") as handle:
        actual_lines = sum(chunk.count(b"\n") for chunk in iter(lambda: handle.read(1024 * 1024), b""))
    if actual_lines != expected_lines:
        raise SeedPipelineError(
            f"Cannot resume: {label} spool row count does not match checkpoint"
        )


def _write_checkpoint(
    path: Path,
    *,
    source_identity: Mapping[str, Any],
    source_size: int,
    source_prefix_sha256: str,
    byte_offset: int,
    scanned: int,
    malformed: int,
    candidates_written: int,
    candidate_spool_size: int,
    audit_spool_size: int,
    complete: bool,
) -> None:
    payload = {
        "checkpoint_schema_version": 2,
        "pipeline_version": PIPELINE_VERSION,
        "source_identity": dict(source_identity),
        "source_size": source_size,
        "source_prefix_sha256": source_prefix_sha256,
        "byte_offset": byte_offset,
        "scanned": scanned,
        "malformed": malformed,
        "candidates_written": candidates_written,
        "candidate_spool_size": candidate_spool_size,
        "audit_spool_size": audit_spool_size,
        "complete": complete,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SeedPipelineError(f"Malformed JSONL at {path}:{line_number}") from exc
            if not isinstance(row, dict):
                raise SeedPipelineError(f"JSONL row is not an object at {path}:{line_number}")
            yield row


def attach_ufo_lineage(
    candidate_wrappers: list[dict[str, Any]],
    deduped_events_path: Path,
    *,
    allow_partial: bool,
) -> dict[str, Any]:
    """Attach existing canonical event lineage without mutating UFO data."""

    wanted: set[str] = set()
    by_input: dict[str, dict[str, Any]] = {}
    for wrapper in candidate_wrappers:
        candidate = wrapper["candidate"]
        input_id = normalize_space(candidate.get("raw_record_pointer", {}).get("canonical_input_id"))
        if input_id:
            wanted.add(input_id)
            by_input[input_id] = wrapper

    found: set[str] = set()
    scanned = 0
    for event in read_jsonl(deduped_events_path):
        scanned += 1
        event_id = normalize_space(event.get("canonical_event_id"))
        input_ids = {
            normalize_space(item)
            for item in event.get("canonical_input_ids", [])
            if normalize_space(item)
        }
        if not input_ids:
            for provenance in event.get("source_provenance", []):
                if isinstance(provenance, Mapping) and normalize_space(provenance.get("canonical_input_id")):
                    input_ids.add(normalize_space(provenance.get("canonical_input_id")))
        for input_id in sorted(wanted.intersection(input_ids)):
            wrapper = by_input[input_id]
            candidate = wrapper["candidate"]
            if event_id:
                candidate["related_ufo_timeline_event_ids"] = [event_id]
                candidate["external_event_refs"].append(
                    {
                        "domain": "ufo",
                        "dataset": "MYTbrain/ufo-timeline",
                        "external_id": event_id,
                        "native_event_id": event.get("event_id") or event_id,
                        "relationship_id": None,
                    }
                )
                wrapper["ufo_event_id"] = event_id
                wrapper["ufo_event_native_id"] = event.get("event_id") or event_id
                wrapper["ufo_endpoint_provenance"] = {
                    "dataset": "MYTbrain/ufo-timeline",
                    "external_id": event_id,
                    "native_event_id": event.get("event_id") or event_id,
                    "deduped_event_sha256": sha256_bytes(
                        canonical_json(event).encode("utf-8")
                    ),
                    "canonical_input_id": input_id,
                }
                found.add(input_id)
    if not allow_partial and scanned != PINNED_DEDUPED_EVENT_COUNT:
        raise SeedPipelineError(
            f"Deduplicated corpus count changed: expected {PINNED_DEDUPED_EVENT_COUNT:,}, scanned {scanned:,}"
        )
    return {
        "deduped_events_scanned": scanned,
        "candidate_input_ids": len(wanted),
        "candidate_input_ids_with_lineage": len(found),
        "candidate_input_ids_without_lineage": len(wanted - found),
    }


def _fallback_cluster_key(candidate: Mapping[str, Any]) -> str:
    # Date/place similarity is a review signal, never an automatic merge key.
    # Only authoritative upstream lineage can group records in Phase 1.
    return stable_id("block-unique", candidate.get("record_id"), length=20)


def _merge_animal_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Merge source-local animal assertions without losing role provenance."""

    merged: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    for raw_row in sorted((dict(row) for row in rows), key=canonical_json):
        key = (
            normalize_space(raw_row.get("normalized_common_name") or raw_row.get("species")),
            normalize_space(raw_row.get("reported_taxon_key")),
            normalize_space(raw_row.get("species_group")),
            normalize_space(raw_row.get("domestic_context")),
            normalize_space(raw_row.get("incident_role")),
        )
        if key not in merged:
            merged[key] = raw_row
            merged[key]["source_ids"] = sorted(
                {normalize_space(value) for value in raw_row.get("source_ids", []) if normalize_space(value)}
            )
            continue
        current = merged[key]
        current["source_ids"] = sorted(
            {
                *current.get("source_ids", []),
                *(
                    normalize_space(value)
                    for value in raw_row.get("source_ids", [])
                    if normalize_space(value)
                ),
            }
        )
        current["identification_confidence"] = max(
            float(current.get("identification_confidence") or 0),
            float(raw_row.get("identification_confidence") or 0),
        )
        for field in ("reported_text", "evidence_excerpt", "identification_basis"):
            values = sorted(
                {
                    normalize_space(current.get(field)),
                    normalize_space(raw_row.get(field)),
                }
                - {""}
            )
            current[field] = values[0] if values else None
    return [merged[key] for key in sorted(merged)]


def cluster_candidates(
    candidate_wrappers: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str]]:
    case_wrappers = [
        wrapper
        for wrapper in candidate_wrappers
        if wrapper["candidate"].get("record_type") == "mutilation_case"
    ]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for wrapper in case_wrappers:
        key = normalize_space(wrapper.get("ufo_event_id")) or _fallback_cluster_key(wrapper["candidate"])
        groups[key].append(wrapper)

    canonical_incidents: list[dict[str, Any]] = []
    duplicate_pairs: list[dict[str, Any]] = []
    record_to_cluster: dict[str, str] = {}
    for key in sorted(groups):
        members = sorted(groups[key], key=lambda item: item["candidate"]["record_id"])
        incident_id = stable_id("cmi", key, *[item["candidate"]["record_id"] for item in members], length=24)
        primary = max(
            members,
            key=lambda item: (
                float(item["candidate"].get("extraction", {}).get("candidate_score") or 0),
                item["candidate"]["record_id"],
            ),
        )["candidate"]
        for wrapper in members:
            candidate = wrapper["candidate"]
            candidate["canonical_incident_id"] = incident_id
            candidate["provenance"]["duplicate_cluster_id"] = incident_id
            record_to_cluster[candidate["record_id"]] = incident_id

        incident = json.loads(canonical_json(primary))
        incident["record_id"] = incident_id
        incident["canonical_incident_id"] = incident_id
        incident["title"] = primary.get("title")
        incident["sources"] = sorted(
            [source for item in members for source in item["candidate"].get("sources", [])],
            key=lambda source: source.get("source_id", ""),
        )
        incident["animals"] = _merge_animal_rows(
            animal
            for item in members
            for animal in item["candidate"].get("animals", [])
        )
        incident["animal_context"] = _merge_animal_rows(
            animal
            for item in members
            for animal in item["candidate"].get("animal_context", [])
        )
        for field in (
            "direct_animal_terms",
            "finding_terms",
            "association_terms",
            "explicit_aerial_association_terms",
            "noise_terms",
            "structured_codes",
        ):
            incident[field] = sorted(
                {
                    normalize_space(value)
                    for item in members
                    for value in item["candidate"].get(field, [])
                    if normalize_space(value)
                }
            )
        incident["related_ufo_timeline_event_ids"] = sorted(
            {
                str(event_id)
                for item in members
                for event_id in item["candidate"].get("related_ufo_timeline_event_ids", [])
            }
        )
        incident["external_event_refs"] = _dedupe_dicts(
            [ref for item in members for ref in item["candidate"].get("external_event_refs", [])],
            key_fields=("domain", "dataset", "external_id"),
        )
        incident["constituent_record_ids"] = [item["candidate"]["record_id"] for item in members]
        incident["provenance"]["raw_record_hash"] = sha256_bytes(
            "\n".join(sorted(source["source_hash"] for source in incident["sources"] if source.get("source_hash"))).encode("utf-8")
        )
        incident["provenance"]["source_native_id"] = None
        canonical_incidents.append(incident)

        for left, right in combinations(members, 2):
            left_id = left["candidate"]["record_id"]
            right_id = right["candidate"]["record_id"]
            same_event = bool(left.get("ufo_event_id") and left.get("ufo_event_id") == right.get("ufo_event_id"))
            reasons = ["same_existing_ufo_canonical_event"] if same_event else ["same_date_location_species_block"]
            duplicate_pairs.append(
                {
                    "duplicate_cluster_id": incident_id,
                    "left_record_id": left_id,
                    "right_record_id": right_id,
                    "pair_score": "1.0000" if same_event else "0.7500",
                    "reasons": "|".join(reasons),
                    "auto_merge": "false",
                    "review_state": "provisional_cluster",
                }
            )
    canonical_incidents.sort(key=lambda row: row["record_id"])
    duplicate_pairs.sort(key=lambda row: (row["duplicate_cluster_id"], row["left_record_id"], row["right_record_id"]))
    return canonical_incidents, duplicate_pairs, record_to_cluster


def _dedupe_dicts(rows: Iterable[dict[str, Any]], *, key_fields: Sequence[str]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    for row in sorted(rows, key=canonical_json):
        key = tuple(str(row.get(field)) for field in key_fields)
        if key not in seen:
            seen.add(key)
            output.append(row)
    return output


def finalize_extraction_audit(
    audit_spool: Path,
    output_path: Path,
    record_to_cluster: Mapping[str, str],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp = output_path.with_suffix(output_path.suffix + ".tmp")
    with (
        audit_spool.open(encoding="utf-8", newline="") as source,
        temp.open("w", encoding="utf-8", newline="") as destination,
    ):
        reader = csv.DictReader(source)
        writer = csv.DictWriter(destination, fieldnames=EXTRACTION_AUDIT_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in reader:
            row["duplicate_cluster_id"] = record_to_cluster.get(row.get("record_id", ""), "")
            writer.writerow({field: row.get(field, "") for field in EXTRACTION_AUDIT_FIELDS})
    os.replace(temp, output_path)


def load_crop_package(crop_zip_path: Path, *, allow_partial: bool) -> dict[str, Any]:
    package_hash = verify_file_hash(
        crop_zip_path, PINNED_CROP_ZIP_SHA256, "Crop Circle Atlas export"
    )
    try:
        with zipfile.ZipFile(crop_zip_path) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            validation = json.loads(archive.read("validation_report.json"))
            for entry in manifest.get("files", []):
                member = archive.read(entry["name"])
                if len(member) != int(entry["size_bytes"]):
                    raise SeedPipelineError(f"Crop ZIP member size mismatch: {entry['name']}")
                if sha256_bytes(member).lower() != str(entry["sha256"]).lower():
                    raise SeedPipelineError(f"Crop ZIP member SHA-256 mismatch: {entry['name']}")
            export = json.loads(archive.read("crop_circle_timeline_export_v1.json"))
    except (zipfile.BadZipFile, KeyError, json.JSONDecodeError) as exc:
        raise SeedPipelineError(f"Invalid Crop Circle Atlas package: {type(exc).__name__}") from exc

    if validation.get("status") != "passed" or validation.get("errors"):
        raise SeedPipelineError("Crop Circle Atlas packaged validation did not pass")
    events = export.get("events")
    assertions = export.get("source_assertions")
    image_links = export.get("image_links")
    if not isinstance(events, list) or not isinstance(assertions, list) or not isinstance(image_links, list):
        raise SeedPipelineError("Crop export is missing event, assertion, or image-link arrays")
    if not allow_partial:
        if len(events) != PINNED_CROP_EVENT_COUNT:
            raise SeedPipelineError(
                f"Crop event count changed: expected {PINNED_CROP_EVENT_COUNT:,}, got {len(events):,}"
            )
        if len(assertions) != PINNED_CROP_ASSERTION_COUNT:
            raise SeedPipelineError(
                f"Crop assertion count changed: expected {PINNED_CROP_ASSERTION_COUNT:,}, got {len(assertions):,}"
            )
    event_ids = [normalize_space(event.get("external_id")) for event in events]
    assertion_ids = [normalize_space(item.get("assertion_id")) for item in assertions]
    if len(set(event_ids)) != len(event_ids) or "" in event_ids:
        raise SeedPipelineError("Crop external IDs are not unique and non-empty")
    if len(set(assertion_ids)) != len(assertion_ids) or "" in assertion_ids:
        raise SeedPipelineError("Crop assertion IDs are not unique and non-empty")
    if any(event.get("trace_eligible") is not False or event.get("trace_role") != "context_only" for event in events):
        raise SeedPipelineError("Crop events must remain context_only and trace_eligible=false")
    event_id_set = set(event_ids)
    for assertion in assertions:
        if normalize_space(assertion.get("formation_id")) not in event_id_set:
            raise SeedPipelineError(
                f"Crop assertion endpoint missing: {assertion.get('assertion_id')}"
            )
    image_alt_text_count = sum(1 for row in image_links if normalize_space(row.get("alt_text")))
    image_title_text_count = sum(1 for row in image_links if normalize_space(row.get("title_text")))
    if not allow_partial:
        if image_alt_text_count != PINNED_CROP_IMAGE_ALT_TEXT_COUNT:
            raise SeedPipelineError(
                "Crop image alt-text count changed: "
                f"expected {PINNED_CROP_IMAGE_ALT_TEXT_COUNT:,}, got {image_alt_text_count:,}"
            )
        if image_title_text_count != PINNED_CROP_IMAGE_TITLE_TEXT_COUNT:
            raise SeedPipelineError(
                "Crop image title-text count changed: "
                f"expected {PINNED_CROP_IMAGE_TITLE_TEXT_COUNT:,}, got {image_title_text_count:,}"
            )
    for image_link in image_links:
        formation_id = normalize_space(image_link.get("formation_id"))
        if formation_id and formation_id not in event_id_set:
            raise SeedPipelineError(
                f"Crop image narrative endpoint missing: {image_link.get('image_link_id')}"
            )
    assertion_urls = {
        normalize_space(item.get("source_record_url"))
        for item in assertions
        if normalize_space(item.get("source_record_url"))
    }
    if not allow_partial and len(assertion_urls) != PINNED_CROP_ASSERTION_URL_COUNT:
        raise SeedPipelineError(
            f"Crop assertion URL count changed: expected {PINNED_CROP_ASSERTION_URL_COUNT:,}, got {len(assertion_urls):,}"
        )
    targets, enumerated_hash = enumerate_crop_source_targets(crop_zip_path)
    if enumerated_hash.lower() != package_hash.lower():
        raise SeedPipelineError("Crop acquisition enumeration read a different package identity")
    if not allow_partial and len(targets) != PINNED_CROP_ALL_RECORD_URL_COUNT:
        raise SeedPipelineError(
            f"Crop all-record URL count changed: expected {PINNED_CROP_ALL_RECORD_URL_COUNT:,}, got {len(targets):,}"
        )
    listing_source_urls: set[str] = set()

    def collect_listing_urls(value: Any) -> None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                if key == "source_url" and public_http_url(item):
                    listing_source_urls.add(public_http_url(item) or "")
                collect_listing_urls(item)
        elif isinstance(value, list):
            for item in value:
                collect_listing_urls(item)

    collect_listing_urls(export)
    acquired_urls = {target.url for target in targets}
    listing_source_urls.difference_update(acquired_urls)
    listing_source_urls.discard("")
    return {
        "package_sha256": package_hash,
        "manifest": manifest,
        "validation": validation,
        "export": export,
        "events": events,
        "assertions": assertions,
        "image_links": image_links,
        "image_alt_text_count": image_alt_text_count,
        "image_title_text_count": image_title_text_count,
        "targets": targets,
        "assertion_url_count": len(assertion_urls),
        "listing_source_urls": sorted(listing_source_urls),
    }


def _crop_text_analysis(text: str) -> Analysis:
    return analyze_source_record(
        {
            "description": text,
            "summary": "",
            "type_raw": "crop_circle_source_narrative",
            "type_normalized": "crop_circle_source_narrative",
            "raw_fields": {},
        }
    )


def crop_image_narrative_entries(
    image_links: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Enumerate every nonempty packaged image narrative with stable unique IDs."""

    ordered: list[tuple[str, Mapping[str, Any]]] = sorted(
        ((canonical_json(dict(row)), row) for row in image_links),
        key=lambda item: item[0],
    )
    duplicate_occurrences: Counter[str] = Counter()
    entries: list[dict[str, Any]] = []
    for row_json, row in ordered:
        duplicate_occurrences[row_json] += 1
        occurrence = duplicate_occurrences[row_json]
        record_id = stable_id(
            "crop-image",
            row_json,
            occurrence,
            length=24,
        )
        for field, item_kind in (
            ("alt_text", "crop_image_alt_text"),
            ("title_text", "crop_image_title_text"),
        ):
            narrative = normalize_space(row.get(field))
            if not narrative:
                continue
            entries.append(
                {
                    "record_id": record_id,
                    "item_kind": item_kind,
                    "item_id": f"{record_id}:{field}",
                    "field": field,
                    "text": narrative,
                    "row": row,
                }
            )
    return entries


def crop_image_narrative_expected_sets(
    image_links: Sequence[Mapping[str, Any]],
) -> dict[str, set[str]]:
    expected: dict[str, set[str]] = {
        "crop_image_alt_text": set(),
        "crop_image_title_text": set(),
    }
    for entry in crop_image_narrative_entries(image_links):
        expected[entry["item_kind"]].add(entry["item_id"])
    return expected


def _crop_source_candidate(
    *,
    source_kind: str,
    source_id: str,
    formation_ids: Sequence[str],
    source_url: str | None,
    source_hash: str,
    text: str,
    analysis: Analysis,
    provenance_locator: str,
    dates: Mapping[str, Any] | None = None,
    location: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    candidate_id = stable_id("ccsc", source_kind, source_id, source_hash, "crop_mutilation_claim")
    human_staging = source_explicit_human_staging(text)
    withhold_named_private_property = _private_property_evidence_redaction_required(
        location,
        text,
    )
    public_location = _public_crop_candidate_location(
        location,
        withhold_named_private_property=withhold_named_private_property,
    )
    candidate_reasons = set(analysis.candidate_reasons)
    if human_staging:
        candidate_reasons.add("source_explicit_deliberate_human_staging")

    def public_assertion(assertion: AnimalAssertion) -> dict[str, Any]:
        row = asdict(assertion)
        row["evidence_excerpt"] = sanitize_public_excerpt(
            row.get("evidence_excerpt"),
            withhold_named_private_property=withhold_named_private_property,
        )
        return row

    public_animal_assertions = [
        public_assertion(assertion) for assertion in analysis.animal_assertions
    ]
    public_context_animal_assertions = [
        public_assertion(assertion)
        for assertion in analysis.context_animal_assertions
    ]
    public_incident_evidence = unique_strings(
        assertion.get("evidence_excerpt")
        for assertion in public_animal_assertions
        if assertion.get("evidence_excerpt")
    )

    return {
        "crop_source_candidate_id": candidate_id,
        "event_domain": "crop_circle",
        "trace_eligible": False,
        "trace_role": "context_only",
        "source_kind": source_kind,
        "source_id": source_id,
        "formation_ids": sorted(set(formation_ids)),
        "source_url": source_url,
        "source_hash": source_hash,
        "provenance_locator": provenance_locator,
        "dates": dict(dates or {}),
        "location": public_location,
        "classification": analysis.disposition,
        "record_type": analysis.record_type,
        "crop_relationship_type": analysis.crop_relationship_type,
        "candidate_score": analysis.candidate_score,
        "candidate_reasons": sorted(candidate_reasons),
        "direct_animal_terms": list(analysis.animal_terms),
        "animal_assertions": public_animal_assertions,
        "context_animal_assertions": public_context_animal_assertions,
        "incident_evidence_mode": analysis.incident_evidence_mode,
        "incident_evidence_sentences": public_incident_evidence,
        "finding_terms": list(analysis.finding_terms),
        "explicit_aerial_association_terms": list(analysis.explicit_aerial_association_terms),
        "explicit_negative": analysis.explicit_negative,
        "negative_only": analysis.negative_only,
        "source_explicit_human_staging": human_staging,
        "evidence_excerpt": short_evidence_excerpt(
            text,
            (*analysis.animal_terms, *analysis.finding_terms, *analysis.association_terms),
            withhold_named_private_property=withhold_named_private_property,
        ),
        "review_state": "needs_human_review",
        "causality": "not_asserted",
    }


def _claims_from_crop_source_candidate(
    row: Mapping[str, Any], source_id: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    anatomy_normalized = {normalize_for_match(term) for term in ANATOMY_TERMS}
    anatomical: list[dict[str, Any]] = []
    scene: list[dict[str, Any]] = []
    for term in row.get("finding_terms", []):
        claim = {
            "claim_type": (
                "reported_anatomical_finding"
                if normalize_for_match(term) in anatomy_normalized
                else "reported_carcass_or_harm_finding"
            ),
            "anatomical_site": term if normalize_for_match(term) in anatomy_normalized else None,
            "asserted_value": True if normalize_for_match(term) in anatomy_normalized else term,
            "asserted_by": None,
            "observation_basis": "retelling",
            "source_ids": [source_id],
            "confidence": 0.5,
            "contradicted_by_source_ids": [],
            "notes": "Lexically extracted linked-source claim; requires review.",
        }
        (anatomical if claim["anatomical_site"] else scene).append(claim)
    return anatomical, scene


def build_crop_cattle_candidate(
    source_candidate: Mapping[str, Any],
    crop_events_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Promote an actual animal incident found in a crop source to a case lead."""

    source_candidate_id = normalize_space(source_candidate.get("crop_source_candidate_id"))
    record_id = stable_id("cmr", "crop_source", source_candidate_id, length=24)
    source_id = f"crop-source:{source_candidate_id}"
    relationship_type = normalize_space(source_candidate.get("crop_relationship_type")) or "topical_context"
    formation_ids = [
        normalize_space(item)
        for item in source_candidate.get("formation_ids", [])
        if normalize_space(item) in crop_events_by_id
    ]
    event = crop_events_by_id.get(formation_ids[0]) if len(formation_ids) == 1 else None

    dates = {"start": None, "end": None, "precision": "unknown"}
    if relationship_type in {"same_scene", "reported_nearby"}:
        supplied_dates = source_candidate.get("dates", {})
        if supplied_dates.get("start") or event is not None:
            dates = (
                normalized_date_interval(
                    supplied_dates.get("start"),
                    supplied_dates.get("end"),
                    supplied_dates.get("precision") or "unknown",
                )
                if supplied_dates.get("start")
                else _date_interval_from_crop(event or {})
            )

    raw_crop_details = event.get("crop_circle", {}) if event else {}
    if not isinstance(raw_crop_details, Mapping):
        raw_crop_details = {}
    raw_supplied_location = source_candidate.get("location", {})
    if not isinstance(raw_supplied_location, Mapping):
        raw_supplied_location = {}
    evidence_values = [
        source_candidate.get("evidence_excerpt"),
        *source_candidate.get("incident_evidence_sentences", []),
        *[
            assertion.get("evidence_excerpt")
            for field in ("animal_assertions", "context_animal_assertions")
            for assertion in source_candidate.get(field, [])
            if isinstance(assertion, Mapping)
        ],
    ]
    withhold_named_private_property = _private_property_evidence_redaction_required(
        raw_supplied_location,
        *raw_crop_details.values(),
        *evidence_values,
    )
    supplied_location = _public_crop_candidate_location(
        raw_supplied_location,
        withhold_named_private_property=withhold_named_private_property,
    )
    crop_details = _public_crop_candidate_location(
        raw_crop_details,
        withhold_named_private_property=withhold_named_private_property,
    )
    place = supplied_location.get("place") or crop_details.get("place")
    region = supplied_location.get("region") or crop_details.get("region")
    country = (
        supplied_location.get("country_code")
        or supplied_location.get("country")
        or crop_details.get("country_code")
        or crop_details.get("country")
    )
    has_context_location = relationship_type in {"same_scene", "reported_nearby"} and bool(
        place or region or country
    )
    location_precision = "approximate" if has_context_location else "unknown"
    location = {
        "raw_text": ", ".join(unique_strings([place, region, country])) or None,
        "country_code": normalize_space(country) or None,
        "admin1": normalize_space(region) or None,
        "admin2": normalize_space(supplied_location.get("county") or crop_details.get("county")) or None,
        "locality": normalize_space(place) or None,
        "latitude_internal": None,
        "longitude_internal": None,
        "latitude_public": None,
        "longitude_public": None,
        "precision": location_precision,
        "coordinate_source": None,
        "geocode_query": None,
        "geocode_confidence": None,
        "privacy_level": "public_generalized",
        "mapping_notes": (
            "Place is generalized from linked crop-formation context; no animal-site coordinate is asserted."
            if has_context_location
            else "Animal incident location is not established by the linked crop source."
        ),
    }
    anatomical, scene = _claims_from_crop_source_candidate(source_candidate, source_id)
    source_hash = normalize_space(source_candidate.get("source_hash"))
    if not re.fullmatch(r"[a-fA-F0-9]{64}", source_hash):
        source_hash = sha256_bytes(canonical_json(dict(source_candidate)).encode("utf-8"))
    source_kind = normalize_space(source_candidate.get("source_kind"))
    source_type = "website" if source_candidate.get("source_url") else "dataset"
    human_staging = source_candidate.get("source_explicit_human_staging") is True
    animal_rows = []
    for assertion in source_candidate.get("animal_assertions", []):
        animal_rows.append(
            {
                "species": assertion.get("normalized_common_name"),
                "reported_text": assertion.get("reported_text"),
                "reported_taxon_key": assertion.get("reported_taxon_key"),
                "normalized_common_name": assertion.get("normalized_common_name"),
                "species_group": assertion.get("species_group"),
                "domestic_context": assertion.get("domestic_context"),
                "incident_role": assertion.get("incident_role"),
                "identification_basis": assertion.get("identification_basis"),
                "identification_confidence": assertion.get("identification_confidence"),
                "source_ids": [source_id],
                "evidence_excerpt": assertion.get("evidence_excerpt"),
                "breed": None,
                "sex": None,
                "age_class": None,
                "count": None,
                "condition_before_death": None,
                "ownership_public": None,
            }
        )
    animal_context_rows = [
        {
            **dict(assertion),
            "species": assertion.get("normalized_common_name"),
            "source_ids": [source_id],
            "breed": None,
            "sex": None,
            "age_class": None,
            "count": None,
            "condition_before_death": None,
            "ownership_public": None,
        }
        for assertion in source_candidate.get("context_animal_assertions", [])
    ]
    for animal in [*animal_rows, *animal_context_rows]:
        animal["evidence_excerpt"] = sanitize_public_excerpt(
            animal.get("evidence_excerpt"),
            withhold_named_private_property=withhold_named_private_property,
        )
    return {
        "event_domain": "animal_mutilation",
        "record_id": record_id,
        "canonical_incident_id": None,
        "record_type": "mutilation_case",
        "status": "contested" if human_staging else "lead",
        "title": f"Crop-linked source animal incident {source_candidate_id}",
        "summary": sanitize_public_excerpt(
            source_candidate.get("evidence_excerpt"),
            withhold_named_private_property=withhold_named_private_property,
        ),
        "dates": {
            "event_start": dates.get("start"),
            "event_end": dates.get("end"),
            "discovery_start": None,
            "discovery_end": None,
            "report_date": None,
            "estimated_death_start": None,
            "estimated_death_end": None,
            "precision": dates.get("precision") or "unknown",
            "raw_text": None,
        },
        "location": location,
        "animals": animal_rows,
        "animal_context": animal_context_rows,
        "anatomical_findings": anatomical,
        "scene_findings": scene,
        "laboratory_findings": [],
        "associated_events": [
            {
                "association_type": "crop_circle",
                "claim": {
                    "claim_type": "source_or_citation_links_crop_context",
                    "asserted_value": relationship_type,
                    "asserted_by": None,
                    "observation_basis": "retelling",
                    "source_ids": [source_id],
                    "confidence": 0.65 if relationship_type in {"same_scene", "reported_nearby"} else 0.35,
                    "contradicted_by_source_ids": [],
                    "notes": "Context only; crop authenticity and causality are not asserted.",
                },
                "linked_record_id": None,
                "temporal_offset_hours": None,
                "distance_km": None,
            }
        ],
        "investigation": {
            "agencies": [],
            "case_numbers": [],
            "investigators": [],
            "necropsy_performed": None,
            "veterinary_review": None,
            "official_conclusion": None,
            "disposition": (
                "source_explicit_deliberate_placement_of_mutilated_animal"
                if human_staging
                else None
            ),
            "contradictions": [],
        },
        "sources": [
            {
                "source_id": source_id,
                "tier": "C",
                "source_type": source_type,
                "title": f"Crop Circle Atlas linked source ({source_kind})",
                "agency_or_publisher": "Crop Circle Atlas linked source",
                "publication_date": None,
                "url": public_http_url(source_candidate.get("source_url")),
                "page_or_container": normalize_space(source_candidate.get("provenance_locator")) or None,
                "archival_citation": None,
                "rights_status": "copyrighted_metadata_only",
                "raw_text_retention": "internal_only",
                "source_hash": source_hash,
            }
        ],
        "extraction": {
            "candidate_score": source_candidate.get("candidate_score"),
            "candidate_reasons": list(source_candidate.get("candidate_reasons", [])),
            "incident_likelihood": min(0.79, float(source_candidate.get("candidate_score") or 0.5)),
            "needs_human_review": True,
            "incident_evidence_mode": source_candidate.get("incident_evidence_mode"),
            "incident_evidence_sentences": [
                sanitized
                for sentence in source_candidate.get("incident_evidence_sentences", [])
                if (
                    sanitized := sanitize_public_excerpt(
                        sentence,
                        withhold_named_private_property=withhold_named_private_property,
                    )
                )
            ],
        },
        "provenance": {
            "ingestion_adapter": "crop_circle_source_narrative_v1",
            "source_native_id": source_candidate_id,
            "raw_record_hash": source_hash,
            "duplicate_cluster_id": None,
            "canonicalization_version": CANONICALIZATION_VERSION,
            "ingested_at": None,
            "review_state": "unreviewed",
            "review_notes": None,
        },
        "public_content_warning": "Animal-death and anatomical descriptions may be disturbing.",
        "related_ufo_timeline_event_ids": [],
        "external_event_refs": [],
        "direct_animal_terms": list(source_candidate.get("direct_animal_terms", [])),
        "finding_terms": list(source_candidate.get("finding_terms", [])),
        "association_terms": ["crop_source_lineage"],
        "explicit_aerial_association_terms": list(
            source_candidate.get("explicit_aerial_association_terms", [])
        ),
        "noise_terms": [],
        "structured_codes": [],
        "explicit_negative": bool(source_candidate.get("explicit_negative")),
        "negative_only": bool(source_candidate.get("negative_only")),
        "explicit_crop_mutilation_link": relationship_type in {"same_scene", "reported_nearby", "topical_context"},
        "crop_relationship_type": relationship_type,
        "raw_record_pointer": {
            "dataset": "crop_circle_source_candidates",
            "line": None,
            "canonical_input_id": source_candidate_id,
            "source_row_hash": source_hash,
        },
    }


def promote_crop_source_cases(
    crop_source_candidates: Sequence[Mapping[str, Any]],
    crop_events: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    crop_events_by_id = {
        normalize_space(event.get("external_id")): event
        for event in crop_events
        if normalize_space(event.get("external_id"))
    }
    wrappers: list[dict[str, Any]] = []
    for row in crop_source_candidates:
        formation_ids = sorted(
            {
                normalize_space(item)
                for item in row.get("formation_ids", [])
                if normalize_space(item) in crop_events_by_id
            }
        )
        if row.get("record_type") != "mutilation_case" or row.get("negative_only") or not formation_ids:
            continue
        candidate = build_crop_cattle_candidate(row, crop_events_by_id)
        wrappers.append(
            {
                "candidate": candidate,
                "analysis": {
                    "disposition": row.get("classification"),
                    "crop_signal": True,
                    "explicit_crop_mutilation_link": bool(row.get("crop_relationship_type")),
                    "crop_relationship_type": row.get("crop_relationship_type") or "topical_context",
                },
                "crop_source_candidate_id": row["crop_source_candidate_id"],
                "crop_formation_ids": formation_ids,
                "crop_relationship_type": row.get("crop_relationship_type") or "topical_context",
                "validation_decision": _build_crop_validation_decision(row, candidate),
            }
        )
    return sorted(wrappers, key=lambda item: item["candidate"]["record_id"])


def _read_acquisition_audit(path: Path | None) -> dict[str, dict[str, str]]:
    if path is None or not path.is_file():
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        return {
            normalize_space(row.get("source_record_url")): row
            for row in csv.DictReader(handle)
            if normalize_space(row.get("source_record_url"))
        }


def _decode_page_bytes(data: bytes, charset_hint: str = "") -> str:
    if not data:
        return ""
    if data.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF87a", b"GIF89a", b"RIFF")):
        return ""
    header = data[:8192].decode("ascii", "ignore")
    embedded = re.search(
        r"charset\s*=\s*['\"]?\s*([A-Za-z0-9._-]+)",
        header,
        flags=re.IGNORECASE,
    )
    codecs_to_try = unique_strings(
        [charset_hint, embedded.group(1) if embedded else None, "utf-8-sig", "cp1252", "iso-8859-1"]
    )
    for codec in codecs_to_try:
        try:
            return data.decode(codec, "strict")
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode("utf-8", "replace")


def _extract_visible_text(
    data: bytes,
    *,
    content_type: str = "",
    charset_hint: str = "",
) -> str:
    normalized_type = normalize_for_match(content_type)
    if normalized_type.startswith(("image/", "audio/", "video/", "font/")):
        return ""
    if data.startswith(b"%PDF"):
        try:
            from io import BytesIO
            from pypdf import PdfReader

            reader = PdfReader(BytesIO(data))
            return "\n".join(normalize_space(page.extract_text() or "") for page in reader.pages)[:2_000_000]
        except Exception:
            return ""
    decoded = _decode_page_bytes(data, charset_hint)
    if not decoded:
        return ""
    parser = _VisibleTextParser()
    try:
        parser.feed(decoded)
    except Exception:
        return ""
    unique_lines: list[str] = []
    seen: set[str] = set()
    for part in parser.parts:
        line = normalize_space(part)
        normalized = normalize_for_match(line)
        if len(normalized) < 3 or normalized in seen:
            continue
        seen.add(normalized)
        unique_lines.append(line)
    return "\n".join(unique_lines)[:2_000_000]


def scan_crop_sources(
    crop_data: Mapping[str, Any],
    *,
    catalog_pdf_path: Path,
    acquisition_audit_path: Path | None,
    private_cache_dir: Path | None,
    allow_partial: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    events = crop_data["events"]
    assertions = crop_data["assertions"]
    image_links = crop_data.get("image_links", [])
    targets = crop_data["targets"]
    acquisition_rows = _read_acquisition_audit(acquisition_audit_path)
    candidates: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    crop_events_by_id = {
        normalize_space(event.get("external_id")): event
        for event in events
        if normalize_space(event.get("external_id"))
    }

    event_narrative_fields = (
        "description",
        "raw_event_block",
        "search_text",
        "source_raw",
        "mapping_notes",
        "parse_warnings",
        "date_qualifiers",
    )
    event_candidate_count = 0
    for event in sorted(events, key=lambda row: normalize_space(row.get("external_id"))):
        event_id = normalize_space(event.get("external_id"))
        event_values: list[object] = []
        scanned_fields: list[str] = []
        for field in event_narrative_fields:
            value = event.get(field)
            if isinstance(value, list):
                populated = [item for item in value if normalize_space(item)]
                event_values.extend(populated)
                if populated:
                    scanned_fields.append(field)
            elif normalize_space(value):
                event_values.append(value)
                scanned_fields.append(field)
        text = "\n".join(unique_strings(event_values))
        analysis = _crop_text_analysis(text)
        if text and analysis.disposition != "not_candidate":
            crop_details = event.get("crop_circle") if isinstance(event.get("crop_circle"), Mapping) else {}
            candidate = _crop_source_candidate(
                source_kind="crop_event_packaged_narrative",
                source_id=event_id,
                formation_ids=[event_id],
                source_url=public_http_url(event.get("original_entry_url")),
                source_hash=sha256_bytes(text.encode("utf-8")),
                text=text,
                analysis=analysis,
                provenance_locator=f"crop export event {event_id}",
                dates=_date_interval_from_crop(event),
                location={
                    "place": crop_details.get("place"),
                    "region": crop_details.get("region"),
                    "country": crop_details.get("country"),
                    "country_code": crop_details.get("country_code"),
                    "county": crop_details.get("county"),
                    "precision": map_location_precision(event.get("location_precision")),
                    "latitude": event.get("lat"),
                    "longitude": event.get("lon"),
                    "coordinate_uncertainty_km": event.get("coordinate_uncertainty_km"),
                },
            )
            candidates.append(candidate)
            event_candidate_count += 1
            disposition = "packaged_narrative_candidate"
        elif text:
            disposition = "packaged_narrative_no_signal"
        else:
            disposition = "no_packaged_narrative"
        audit_rows.append(
            {
                "item_kind": "crop_event",
                "item_id": event_id,
                "parent_event_id": "",
                "source_record_url": "",
                "disposition": disposition,
                "coverage_status": "packaged_narrative_scanned" if text else "coverage_gap",
                "http_status": "",
                "content_sha256": sha256_bytes(text.encode("utf-8")) if text else "",
                "archive_snapshot_url": "",
                "rights_status": "metadata_only",
                "notes": (
                    "trace_eligible=false; scanned_fields=" + "|".join(scanned_fields)
                    if text
                    else "trace_eligible=false; missing narrative remains unknown, not negative evidence"
                ),
            }
        )

    assertions_by_url: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for assertion in sorted(assertions, key=lambda row: normalize_space(row.get("assertion_id"))):
        assertion_id = normalize_space(assertion.get("assertion_id"))
        formation_id = normalize_space(assertion.get("formation_id"))
        url = normalize_space(assertion.get("source_record_url"))
        if url:
            assertions_by_url[url].append(assertion)
        assertion_fields = ("source_listing_text", "notes")
        text = "\n".join(unique_strings([assertion.get(field) for field in assertion_fields]))
        analysis = _crop_text_analysis(text)
        if text and analysis.disposition != "not_candidate":
            candidate = _crop_source_candidate(
                source_kind="crop_assertion_packaged_narrative",
                source_id=assertion_id,
                formation_ids=[formation_id],
                source_url=url or None,
                source_hash=sha256_bytes(text.encode("utf-8")),
                text=text,
                analysis=analysis,
                provenance_locator=f"crop export assertion {assertion_id}",
                dates=normalized_date_interval(
                    assertion.get("date_iso"),
                    assertion.get("end_date_iso"),
                    map_date_precision(assertion.get("date_precision")),
                ),
                location={
                    "place": assertion.get("place"),
                    "region": assertion.get("region"),
                    "country": assertion.get("country"),
                },
            )
            candidates.append(candidate)
            disposition = "narrative_candidate"
        elif text:
            disposition = "packaged_narrative_no_signal"
        else:
            disposition = "no_packaged_narrative"
        audit_rows.append(
            {
                "item_kind": "crop_assertion",
                "item_id": assertion_id,
                "parent_event_id": formation_id,
                "source_record_url": url,
                "disposition": disposition,
                "coverage_status": "packaged_narrative_scanned" if text else "coverage_gap",
                "http_status": "",
                "content_sha256": sha256_bytes(text.encode("utf-8")) if text else "",
                "archive_snapshot_url": "",
                "rights_status": normalize_space(assertion.get("rights_scope")) or "unknown",
                "notes": (
                    "missing packaged narrative remains unknown, not negative evidence"
                    if not text
                    else "scanned_fields=" + "|".join(field for field in assertion_fields if normalize_space(assertion.get(field)))
                ),
            }
        )

    image_entries = crop_image_narrative_entries(image_links)
    image_entries_by_record: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in image_entries:
        image_entries_by_record[entry["record_id"]].append(entry)
        row = entry["row"]
        analysis = _crop_text_analysis(entry["text"])
        audit_rows.append(
            {
                "item_kind": entry["item_kind"],
                "item_id": entry["item_id"],
                "parent_event_id": normalize_space(row.get("formation_id")),
                "source_record_url": (
                    public_http_url(row.get("source_record_url"))
                    or public_http_url(row.get("source_page_url"))
                    or ""
                ),
                "disposition": (
                    "packaged_narrative_candidate"
                    if analysis.disposition != "not_candidate"
                    else "packaged_narrative_no_signal"
                ),
                "coverage_status": "packaged_narrative_scanned",
                "http_status": "",
                "content_sha256": sha256_bytes(entry["text"].encode("utf-8")),
                "archive_snapshot_url": "",
                "rights_status": normalize_space(row.get("rights_status")) or "unknown",
                "notes": f"scanned_field={entry['field']}; image URL and taxonomy fields excluded from prose scan",
            }
        )

    image_candidate_count = 0
    for record_id in sorted(image_entries_by_record):
        record_entries = image_entries_by_record[record_id]
        row = record_entries[0]["row"]
        text = "\n".join(unique_strings(entry["text"] for entry in record_entries))
        analysis = _crop_text_analysis(text)
        if analysis.disposition == "not_candidate":
            continue
        formation_id = normalize_space(row.get("formation_id"))
        event = crop_events_by_id.get(formation_id)
        crop_details = (
            event.get("crop_circle", {})
            if event is not None and isinstance(event.get("crop_circle"), Mapping)
            else {}
        )
        source_url = (
            public_http_url(row.get("source_record_url"))
            or public_http_url(row.get("source_page_url"))
        )
        candidates.append(
            _crop_source_candidate(
                source_kind="crop_image_packaged_narrative",
                source_id=record_id,
                formation_ids=[formation_id] if formation_id else [],
                source_url=source_url,
                source_hash=sha256_bytes(text.encode("utf-8")),
                text=text,
                analysis=analysis,
                provenance_locator=(
                    "crop export image_links "
                    f"{normalize_space(row.get('image_link_id')) or record_id} "
                    f"fields={','.join(entry['field'] for entry in record_entries)}"
                ),
                dates=_date_interval_from_crop(event or {}),
                location={
                    "place": crop_details.get("place"),
                    "region": crop_details.get("region"),
                    "country": crop_details.get("country"),
                    "country_code": crop_details.get("country_code"),
                    "county": crop_details.get("county"),
                    "precision": map_location_precision(
                        event.get("location_precision") if event is not None else None
                    ),
                },
            )
        )
        image_candidate_count += 1

    for url in crop_data.get("listing_source_urls", []):
        audit_rows.append(
            {
                "item_kind": "crop_listing_source_url",
                "item_id": stable_id("listing-url", url, length=16),
                "parent_event_id": "",
                "source_record_url": url,
                "disposition": "packaged_listing_locator_not_narrative_page",
                "coverage_status": "packaged_locator_scanned",
                "http_status": "",
                "content_sha256": sha256_bytes(url.encode("utf-8")),
                "archive_snapshot_url": "",
                "rights_status": "metadata_only",
                "notes": "Listing/root locator audited separately from source_record_url narrative pages.",
            }
        )

    page_candidate_count = 0
    for target in targets:
        row = acquisition_rows.get(target.url, {})
        status = row.get("acquisition_status", "not_attempted_offline")
        coverage = row.get("coverage_status", "coverage_gap")
        object_relative = normalize_space(row.get("cache_object_path"))
        content_hash = normalize_space(row.get("content_sha256"))
        visible_text = ""
        object_problem = ""
        if (
            private_cache_dir is not None
            and object_relative
            and content_hash
            and status in {"live_success", "archive_success"}
        ):
            object_path = private_cache_dir.joinpath(*Path(object_relative).parts)
            if not object_path.is_file():
                object_problem = "cache_object_missing"
            elif sha256_file(object_path).lower() != content_hash.lower():
                object_problem = "cache_object_hash_mismatch"
            else:
                visible_text = _extract_visible_text(
                    object_path.read_bytes(),
                    content_type=row.get("content_type", ""),
                    charset_hint=row.get("content_charset", ""),
                )
        if visible_text:
            analysis = _crop_text_analysis(visible_text)
            if analysis.disposition != "not_candidate":
                candidate = _crop_source_candidate(
                    source_kind="crop_linked_source_page",
                    source_id=target.url,
                    formation_ids=target.formation_ids,
                    source_url=target.url,
                    source_hash=content_hash,
                    text=visible_text,
                    analysis=analysis,
                    provenance_locator=row.get("retrieval_url") or target.url,
                )
                candidates.append(candidate)
                page_candidate_count += 1
                disposition = "source_page_narrative_candidate"
            else:
                disposition = "source_page_scanned_no_signal"
            coverage = "narrative_scanned"
        elif status in {"live_success", "archive_success"}:
            disposition = object_problem or "narrative_unavailable"
            coverage = "coverage_gap"
        else:
            disposition = status
        audit_rows.append(
            {
                "item_kind": "crop_source_url",
                "item_id": stable_id("url", target.url, length=16),
                "parent_event_id": "|".join(target.formation_ids),
                "source_record_url": target.url,
                "disposition": disposition,
                "coverage_status": coverage,
                "http_status": row.get("live_http_status", ""),
                "content_sha256": content_hash,
                "archive_snapshot_url": row.get("archive_snapshot_url", ""),
                "rights_status": "|".join(target.rights_scopes) or "unknown",
                "notes": object_problem or row.get("error_code", "") or (
                    "acquired bytes contained no extractable narrative; absence remains unknown"
                    if status in {"live_success", "archive_success"}
                    else "unavailable content remains a coverage gap"
                ),
            }
        )

    catalog = scan_catalog_pdf(catalog_pdf_path)
    if not allow_partial:
        if catalog["counts"]["pages"] != PINNED_CATALOG_PAGE_COUNT:
            raise SeedPipelineError("Pinned catalog page count changed")
        if catalog["counts"]["slots"] != PINNED_CATALOG_SLOT_COUNT:
            raise SeedPipelineError("Pinned catalog slot count changed")
    for page in catalog["pages"]:
        audit_rows.append(
            {
                "item_kind": "catalog_pdf_page",
                "item_id": f"page_{int(page['provenance']['page_number']):03d}",
                "parent_event_id": "",
                "source_record_url": "",
                "disposition": page["narrative_coverage"],
                "coverage_status": "catalog_text_scanned",
                "http_status": "",
                "content_sha256": page["text_sha256"],
                "archive_snapshot_url": "",
                "rights_status": "private_input_metadata_output_only",
                "notes": page["absence_interpretation"],
            }
        )

    slot_candidate_count = 0
    slot_formations: dict[tuple[str, str], set[str]] = defaultdict(set)
    for assertion in assertions:
        page_key = normalize_space(assertion.get("source_page"))
        slot_key = normalize_space(assertion.get("source_slot"))
        formation_id = normalize_space(assertion.get("formation_id"))
        if page_key and slot_key and formation_id:
            slot_formations[(page_key, slot_key)].add(formation_id)
    for slot in catalog["slots"]:
        factual_text = normalize_space(slot.get("factual_text"))
        analysis = _crop_text_analysis(factual_text)
        provenance = slot.get("provenance", {})
        key = (
            normalize_space(provenance.get("page_number")),
            normalize_space(provenance.get("slot_number")),
        )
        formation_ids = sorted(slot_formations.get(key, set()))
        if factual_text and analysis.disposition != "not_candidate":
            candidates.append(
                _crop_source_candidate(
                    source_kind="catalog_pdf_slot",
                    source_id=slot["slot_id"],
                    formation_ids=formation_ids,
                    source_url=None,
                    source_hash=slot["text_sha256"],
                    text=factual_text,
                    analysis=analysis,
                    provenance_locator=provenance["source_locator"],
                    dates={"start": None, "end": None, "precision": "unknown", "raw": slot.get("date_text")},
                    location={
                        "place": slot.get("location_text"),
                        "region": slot.get("admin_region"),
                        "country": slot.get("country"),
                        "precision": "locality" if slot.get("location_text") else "unknown",
                    },
                )
            )
            slot_candidate_count += 1
            disposition = "index_slot_candidate"
        else:
            disposition = "index_only_scanned_no_signal" if factual_text else "index_slot_without_text"
        audit_rows.append(
            {
                "item_kind": "catalog_pdf_slot",
                "item_id": slot["slot_id"],
                "parent_event_id": "|".join(formation_ids),
                "source_record_url": "",
                "disposition": disposition,
                "coverage_status": "catalog_slot_text_scanned" if factual_text else "coverage_gap",
                "http_status": "",
                "content_sha256": slot["text_sha256"],
                "archive_snapshot_url": "",
                "rights_status": "private_input_metadata_output_only",
                "notes": slot["absence_interpretation"],
            }
        )

    expected_sets = {
        "crop_event": {normalize_space(row.get("external_id")) for row in events},
        "crop_assertion": {normalize_space(row.get("assertion_id")) for row in assertions},
        "crop_source_url": {target.url for target in targets},
        "crop_listing_source_url": {
            stable_id("listing-url", url, length=16)
            for url in crop_data.get("listing_source_urls", [])
        },
        "catalog_pdf_page": {f"page_{index:03d}" for index in range(1, catalog["counts"]["pages"] + 1)},
        "catalog_pdf_slot": {normalize_space(row.get("slot_id")) for row in catalog["slots"]},
    }
    expected_sets.update(crop_image_narrative_expected_sets(image_links))
    for item_kind, expected in expected_sets.items():
        actual = [row["item_id"] if item_kind != "crop_source_url" else row["source_record_url"] for row in audit_rows if row["item_kind"] == item_kind]
        if len(actual) != len(set(actual)) or set(actual) != expected:
            raise SeedPipelineError(f"Crop audit disposition coverage mismatch for {item_kind}")

    candidates.sort(key=lambda row: row["crop_source_candidate_id"])
    audit_rows.sort(key=lambda row: (row["item_kind"], row["item_id"], row["source_record_url"]))
    return candidates, audit_rows, {
        "crop_events_scanned": len(events),
        "crop_assertions_scanned": len(assertions),
        "crop_unique_source_urls_scanned": len(targets),
        "crop_assertion_unique_source_urls": crop_data["assertion_url_count"],
        "crop_listing_source_urls_scanned": len(crop_data.get("listing_source_urls", [])),
        "crop_event_narrative_candidates": event_candidate_count,
        "crop_packaged_narrative_candidates": sum(1 for row in candidates if row["source_kind"] == "crop_assertion_packaged_narrative"),
        "crop_image_alt_text_narratives_scanned": sum(
            1 for row in audit_rows if row["item_kind"] == "crop_image_alt_text"
        ),
        "crop_image_title_text_narratives_scanned": sum(
            1 for row in audit_rows if row["item_kind"] == "crop_image_title_text"
        ),
        "crop_image_narrative_candidates": image_candidate_count,
        "crop_source_page_narrative_candidates": page_candidate_count,
        "catalog_pages_scanned": catalog["counts"]["pages"],
        "catalog_slots_scanned": catalog["counts"]["slots"],
        "catalog_index_only_pages": catalog["counts"]["index_only_pages"],
        "catalog_narrative_pages": catalog["counts"]["narrative_present_pages"],
        "catalog_slot_narrative_candidates": slot_candidate_count,
        "crop_source_access_gaps": sum(
            1
            for row in audit_rows
            if row["item_kind"] == "crop_source_url" and row["coverage_status"] == "coverage_gap"
        ),
    }


US_STATE_NAMES = {
    "AL": "alabama", "AK": "alaska", "AZ": "arizona", "AR": "arkansas", "CA": "california",
    "CO": "colorado", "CT": "connecticut", "DE": "delaware", "FL": "florida", "GA": "georgia",
    "HI": "hawaii", "ID": "idaho", "IL": "illinois", "IN": "indiana", "IA": "iowa",
    "KS": "kansas", "KY": "kentucky", "LA": "louisiana", "ME": "maine", "MD": "maryland",
    "MA": "massachusetts", "MI": "michigan", "MN": "minnesota", "MS": "mississippi", "MO": "missouri",
    "MT": "montana", "NE": "nebraska", "NV": "nevada", "NH": "new hampshire", "NJ": "new jersey",
    "NM": "new mexico", "NY": "new york", "NC": "north carolina", "ND": "north dakota", "OH": "ohio",
    "OK": "oklahoma", "OR": "oregon", "PA": "pennsylvania", "RI": "rhode island", "SC": "south carolina",
    "SD": "south dakota", "TN": "tennessee", "TX": "texas", "UT": "utah", "VT": "vermont",
    "VA": "virginia", "WA": "washington", "WV": "west virginia", "WI": "wisconsin", "WY": "wyoming",
}

COUNTRY_ALIASES = {
    "us": "US", "usa": "US", "united states": "US", "united states of america": "US",
    "uk": "GB", "gb": "GB", "united kingdom": "GB", "england": "GB",
    "br": "BR", "brazil": "BR", "brasil": "BR",
    "nl": "NL", "netherlands": "NL", "the netherlands": "NL", "nederland": "NL",
    "de": "DE", "germany": "DE", "fr": "FR", "france": "FR",
    "ca": "CA", "canada": "CA", "au": "AU", "australia": "AU",
    "af": "AF", "afghanistan": "AF", "ar": "AR", "argentina": "AR",
    "at": "AT", "austria": "AT", "be": "BE", "belgium": "BE",
    "ba": "BA", "bosnia": "BA", "bosnia and herzegovina": "BA",
    "bw": "BW", "botswana": "BW", "bg": "BG", "bulgaria": "BG",
    "cl": "CL", "chile": "CL", "cn": "CN", "china": "CN",
    "co": "CO", "colombia": "CO", "hr": "HR", "croatia": "HR",
    "cy": "CY", "cyprus": "CY", "cz": "CZ", "czechia": "CZ",
    "czech republic": "CZ", "czech republik": "CZ", "dk": "DK", "denmark": "DK",
    "eg": "EG", "egypt": "EG", "ee": "EE", "estonia": "EE",
    "fi": "FI", "finland": "FI", "ge": "GE", "georgia": "GE",
    "hu": "HU", "hungary": "HU", "in": "IN", "india": "IN",
    "id": "ID", "indonesia": "ID", "ir": "IR", "iran": "IR",
    "ie": "IE", "ireland": "IE", "il": "IL", "israel": "IL",
    "it": "IT", "italy": "IT", "jp": "JP", "japan": "JP",
    "kz": "KZ", "kazakhstan": "KZ", "ke": "KE", "kenya": "KE",
    "lv": "LV", "latvia": "LV", "lt": "LT", "lithuania": "LT",
    "lu": "LU", "luxembourg": "LU", "mk": "MK", "macedonia": "MK",
    "my": "MY", "malaysia": "MY", "mx": "MX", "mexico": "MX",
    "nz": "NZ", "new zealand": "NZ", "ng": "NG", "nigeria": "NG",
    "no": "NO", "norway": "NO", "pe": "PE", "peru": "PE",
    "ph": "PH", "philippines": "PH", "pl": "PL", "poland": "PL",
    "pt": "PT", "portugal": "PT", "pr": "PR", "puerto rico": "PR",
    "by": "BY", "belarus": "BY", "republic of belarus": "BY",
    "ro": "RO", "romania": "RO", "ru": "RU", "russia": "RU",
    "rs": "RS", "serbia": "RS", "sk": "SK", "slovakia": "SK",
    "si": "SI", "slovenia": "SI", "za": "ZA", "south africa": "ZA",
    "kr": "KR", "south korea": "KR", "es": "ES", "spain": "ES",
    "se": "SE", "sweden": "SE", "ch": "CH", "switzerland": "CH",
    "tr": "TR", "turkey": "TR", "ua": "UA", "ukraine": "UA",
    "uy": "UY", "uruguay": "UY", "scotland": "GB", "wales": "GB",
    "the netherland": "NL", "unites states": "US",
}

KNOWN_MISLABELED_US_REGIONS = {
    "cambridgeshire": "GB", "hampshire": "GB", "leicestershire": "GB", "lincolnshire": "GB",
    "noord brabant": "NL",
}


def normalize_country(value: object, *, region: object = None, place: object = None) -> tuple[str | None, str | None]:
    normalized = normalize_for_match(value)
    raw = normalize_space(value)
    code = COUNTRY_ALIASES.get(
        normalized,
        raw.upper() if len(raw) == 2 else (f"NAME:{normalized}" if normalized else None),
    )
    warning = None
    context = f"{normalize_for_match(region)} {normalize_for_match(place)}"
    if code == "US":
        for token, corrected in KNOWN_MISLABELED_US_REGIONS.items():
            if token in context:
                code = corrected
                warning = f"country_assignment_corrected_from_US_to_{corrected}"
                break
    return code, warning


def normalize_admin1(value: object) -> str:
    text = normalize_space(value)
    if text.upper() in US_STATE_NAMES:
        return US_STATE_NAMES[text.upper()]
    return normalize_for_match(text)


def _date_interval_from_case(case: Mapping[str, Any]) -> dict[str, Any]:
    dates = case.get("dates", {})
    return normalized_date_interval(
        dates.get("event_start"),
        dates.get("event_end"),
        dates.get("precision", "unknown"),
    )


def _date_interval_from_crop(event: Mapping[str, Any]) -> dict[str, Any]:
    return normalized_date_interval(
        event.get("date_iso"),
        event.get("end_date_iso"),
        map_date_precision(event.get("date_precision")),
    )


def compare_intervals(left: Mapping[str, Any], right: Mapping[str, Any]) -> tuple[str, float, float | None]:
    try:
        left_start = date.fromisoformat(str(left.get("start")))
        left_end = date.fromisoformat(str(left.get("end")))
        right_start = date.fromisoformat(str(right.get("start")))
        right_end = date.fromisoformat(str(right.get("end")))
    except (TypeError, ValueError):
        return "unknown", 0.0, None
    left_precision = str(left.get("precision") or "unknown")
    right_precision = str(right.get("precision") or "unknown")
    if (
        left_start == left_end == right_start == right_end
        and left_precision == right_precision == "exact_day"
    ):
        return "exact_day", 1.0, 0.0
    if max(left_start, right_start) <= min(left_end, right_end):
        if (
            (left_start == left_end and left_precision != "exact_day")
            or (right_start == right_end and right_precision != "exact_day")
        ):
            return "precision_limited_overlap", 0.4, 0.0
        return "overlapping_interval", 0.7, 0.0
    left_mid = left_start + (left_end - left_start) / 2
    right_mid = right_start + (right_end - right_start) / 2
    offset = abs((left_mid - right_mid).total_seconds()) / 86400
    if offset <= 31:
        return "within_window", 0.4, round(offset, 3)
    return "incompatible", 0.0, round(offset, 3)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    value = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(max(0.0, 1 - value)))


def _precision_uncertainty(precision: str) -> float | None:
    return {
        "exact_site": 1.0, "parcel": 2.0, "road_segment": 5.0, "locality": 15.0,
        "county": 80.0, "state": 250.0, "country": 700.0, "approximate": 100.0,
    }.get(precision)


def compare_locations(case: Mapping[str, Any], crop: Mapping[str, Any]) -> tuple[str, float, float | None, float | None, list[str]]:
    left = case.get("location", {})
    circle = crop.get("crop_circle", {})
    left_country, _ = normalize_country(left.get("country_code"))
    right_country, warning = normalize_country(
        circle.get("country_code") or circle.get("country"),
        region=circle.get("region"),
        place=circle.get("place"),
    )
    warnings = [warning] if warning else []
    if left_country and right_country and left_country != right_country:
        return "incompatible", 0.0, None, None, warnings
    left_admin = normalize_admin1(left.get("admin1"))
    right_admin = normalize_admin1(circle.get("region"))
    left_locality = normalize_for_match(left.get("locality"))
    left_raw = normalize_for_match(left.get("raw_text"))
    right_locality = normalize_for_match(circle.get("place"))
    left_county = normalize_for_match(left.get("admin2"))
    right_county = normalize_for_match(circle.get("county"))
    if left_admin and right_admin and left_admin != right_admin:
        return "incompatible", 0.0, None, None, warnings + ["admin1_conflict"]

    # Cross-domain candidates and their public distance components may use
    # only the public projection. Internal/private coordinates are retained
    # for custody but can neither select a match nor triangulate its scene.
    left_lat = left.get("latitude_public")
    left_lon = left.get("longitude_public")
    right_lat = crop.get("lat")
    right_lon = crop.get("lon")
    distance = None
    if all(isinstance(value, (int, float)) for value in (left_lat, left_lon, right_lat, right_lon)):
        distance = round(haversine_km(float(left_lat), float(left_lon), float(right_lat), float(right_lon)), 3)
    left_precision = str(left.get("precision") or "unknown")
    right_precision = map_location_precision(crop.get("location_precision"))
    uncertainty = (_precision_uncertainty(left_precision) or 0.0) + float(crop.get("coordinate_uncertainty_km") or _precision_uncertainty(right_precision) or 0.0)
    uncertainty_value = round(uncertainty, 3) if uncertainty else None
    locality_matches = bool(
        left_locality
        and right_locality
        and (left_locality == right_locality or right_locality in left_raw)
    )
    if locality_matches and distance is not None and uncertainty and distance > uncertainty + 25:
        return "incompatible", 0.0, distance, uncertainty_value, warnings + ["coordinate_locality_conflict"]
    if locality_matches:
        return "same_locality", 1.0, distance, uncertainty_value, warnings
    if left_county and right_county and left_county == right_county:
        return "same_county", 0.82, distance, uncertainty_value, warnings
    if distance is not None and uncertainty and distance <= uncertainty + 5:
        return "within_uncertainty", 0.78, distance, uncertainty_value, warnings
    if left_admin and right_admin and left_admin == right_admin:
        return "same_admin1", 0.62, distance, uncertainty_value, warnings
    if left_country and right_country and left_country == right_country:
        return "same_country", 0.20, distance, uncertainty_value, warnings
    return "unknown", 0.0, distance, uncertainty_value, warnings


def _source_ref(source: Mapping[str, Any], supports: str) -> dict[str, Any]:
    raw_hash = normalize_space(source.get("source_hash"))
    source_hash = raw_hash if re.fullmatch(r"[a-fA-F0-9]{64}", raw_hash) else None
    return {
        "source_id": normalize_space(source.get("source_id")) or "unknown_source",
        "supports": supports,
        "locator": normalize_space(source.get("page_or_container")) or normalize_space(source.get("url")) or "source locator unavailable",
        "source_hash": source_hash,
    }


def make_relationship(
    *,
    subject: Mapping[str, Any],
    object_ref: Mapping[str, Any],
    relationship_type: str,
    assertion_mode: str,
    match_tier: int,
    temporal: Mapping[str, Any],
    spatial: Mapping[str, Any],
    source_refs: Sequence[Mapping[str, Any]],
    reasons: Sequence[str],
    source_component: float,
    review_state: str,
    provenance_locator: str,
) -> dict[str, Any]:
    compatibility = round(
        min(1.0, 0.42 * float(temporal["score"]) + 0.42 * float(spatial["score"]) + 0.16 * source_component),
        4,
    )
    identity = canonical_json(
        {
            "subject": subject,
            "object": object_ref,
            "type": relationship_type,
            "mode": assertion_mode,
            "tier": match_tier,
            "reasons": sorted(set(reasons)),
        }
    )
    relationship_id = stable_id("rel", identity, length=24)
    return {
        "relationship_id": relationship_id,
        "subject": dict(subject),
        "object": dict(object_ref),
        "relationship_type": relationship_type,
        "assertion_mode": assertion_mode,
        "match_tier": match_tier,
        "temporal": dict(temporal),
        "spatial": dict(spatial),
        "scores": {
            "relationship_compatibility": compatibility,
            "temporal_component": round(float(temporal["score"]), 4),
            "spatial_component": round(float(spatial["score"]), 4),
            "source_component": round(source_component, 4),
        },
        "reasons": sorted(set(reasons)),
        "source_refs": [dict(row) for row in source_refs],
        "review_state": review_state,
        "review_notes": None,
        "provenance": {
            "ingestion_adapter": "cross_domain_relationship_v1",
            "provenance_locator": provenance_locator,
            "raw_record_hash": sha256_bytes(identity.encode("utf-8")),
            "canonicalization_version": CANONICALIZATION_VERSION,
            "generated_at": None,
        },
        "causality": "not_asserted",
    }


def _same_event_temporal(case: Mapping[str, Any]) -> dict[str, Any]:
    interval = _date_interval_from_case(case)
    exact = interval["precision"] == "exact_day" and interval["start"] == interval["end"] and interval["start"] is not None
    return {
        "subject_interval": interval,
        "object_interval": dict(interval),
        "comparison": "exact_day" if exact else ("overlapping_interval" if interval["start"] else "unknown"),
        "offset_days": 0.0 if interval["start"] else None,
        "score": 1.0 if exact else (0.7 if interval["start"] else 0.0),
    }


def _same_event_spatial(case: Mapping[str, Any]) -> dict[str, Any]:
    precision = str(case.get("location", {}).get("precision") or "unknown")
    comparison, score = {
        "exact_site": ("exact_site", 1.0),
        "parcel": ("same_locality", 0.95),
        "road_segment": ("same_locality", 0.9),
        "locality": ("same_locality", 0.8),
        "county": ("same_county", 0.7),
        "state": ("same_admin1", 0.55),
        "country": ("same_country", 0.2),
        "approximate": ("within_uncertainty", 0.4),
    }.get(precision, ("unknown", 0.0))
    return {
        "subject_precision": precision,
        "object_precision": precision,
        "comparison": comparison,
        "distance_km": None,
        "uncertainty_km": _precision_uncertainty(precision),
        "score": score,
    }


def _case_endpoint(case: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "domain": "animal_mutilation",
        "dataset": "animal_mutilation_phase1_global_seed_v1_1",
        "external_id": case["record_id"],
        "native_event_id": case.get("canonical_incident_id") or case["record_id"],
    }


def _crop_endpoint(event: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "domain": "crop_circle",
        "dataset": "crop_circle_atlas_export_v1",
        "external_id": event["external_id"],
        "native_event_id": event.get("event_id"),
    }


def _relationship_source_refs(case: Mapping[str, Any], supports: str) -> list[dict[str, Any]]:
    return [_source_ref(source, supports) for source in case.get("sources", [])]


def _merge_relationship_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["relationship_id"]].append(row)

    merged: list[dict[str, Any]] = []
    for relationship_id in sorted(grouped):
        group = grouped[relationship_id]
        best = max(
            group,
            key=lambda item: (
                float(item.get("scores", {}).get("relationship_compatibility") or 0.0),
                float(item.get("scores", {}).get("temporal_component") or 0.0),
                float(item.get("scores", {}).get("spatial_component") or 0.0),
                float(item.get("scores", {}).get("source_component") or 0.0),
                canonical_json(item),
            ),
        )
        current = json.loads(canonical_json(best))
        current["reasons"] = sorted(
            {
                normalize_space(reason)
                for item in group
                for reason in item.get("reasons", [])
                if normalize_space(reason)
            }
        )
        current["source_refs"] = _dedupe_dicts(
            [
                source_ref
                for item in group
                for source_ref in item.get("source_refs", [])
            ],
            key_fields=("source_id", "supports", "locator"),
        )
        source_component = max(
            float(item.get("scores", {}).get("source_component") or 0.0)
            for item in group
        )
        temporal_component = float(current["temporal"]["score"])
        spatial_component = float(current["spatial"]["score"])
        current["scores"] = {
            "relationship_compatibility": round(
                min(
                    1.0,
                    0.42 * temporal_component
                    + 0.42 * spatial_component
                    + 0.16 * source_component,
                ),
                4,
            ),
            "temporal_component": round(temporal_component, 4),
            "spatial_component": round(spatial_component, 4),
            "source_component": round(source_component, 4),
        }
        merged.append(current)
    return merged


def build_relationships(
    candidate_wrappers: list[dict[str, Any]],
    canonical_incidents: list[dict[str, Any]],
    crop_events: Sequence[dict[str, Any]],
    crop_source_candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    incidents_by_id = {row["record_id"]: row for row in canonical_incidents}
    relationships: list[dict[str, Any]] = []
    wrappers_by_incident: dict[str, list[dict[str, Any]]] = defaultdict(list)
    crop_events_by_id = {
        normalize_space(event.get("external_id")): event
        for event in crop_events
        if normalize_space(event.get("external_id"))
    }
    for wrapper in candidate_wrappers:
        case = wrapper["candidate"]
        incident_id = normalize_space(case.get("canonical_incident_id"))
        if incident_id:
            wrappers_by_incident[incident_id].append(wrapper)

    # Existing UFO canonical identity is lineage, not proof of an aerial event.
    for incident_id in sorted(wrappers_by_incident):
        incident = incidents_by_id[incident_id]
        subject = _case_endpoint(incident)
        for wrapper in sorted(wrappers_by_incident[incident_id], key=lambda item: item["candidate"]["record_id"]):
            candidate = wrapper["candidate"]
            event_id = normalize_space(wrapper.get("ufo_event_id"))
            if event_id:
                object_ref = {
                    "domain": "ufo",
                    "dataset": "MYTbrain/ufo-timeline",
                    "external_id": event_id,
                    "native_event_id": wrapper.get("ufo_event_native_id") or event_id,
                }
                lineage = make_relationship(
                    subject=subject,
                    object_ref=object_ref,
                    relationship_type="duplicate_lineage",
                    assertion_mode="deterministic_match",
                    match_tier=2,
                    temporal=_same_event_temporal(candidate),
                    spatial=_same_event_spatial(candidate),
                    source_refs=_relationship_source_refs(candidate, "duplicate_lineage"),
                    reasons=["cattle_record_extracted_from_ufo_timeline_source_record"],
                    source_component=1.0,
                    review_state="machine_reviewed",
                    provenance_locator=f"source_records:{candidate['record_id']}->{event_id}",
                )
                relationships.append(lineage)
                for owner in (incident, candidate):
                    for ref in owner.get("external_event_refs", []):
                        if ref.get("domain") == "ufo" and str(ref.get("external_id")) == event_id:
                            ref["relationship_id"] = lineage["relationship_id"]

                aerial_terms = set(candidate.get("explicit_aerial_association_terms", []))
                if aerial_terms:
                    explicit_aerial = make_relationship(
                        subject=subject,
                        object_ref=object_ref,
                        relationship_type="reported_nearby",
                        assertion_mode="explicit_source",
                        match_tier=1,
                        temporal=_same_event_temporal(candidate),
                        spatial=_same_event_spatial(candidate),
                        source_refs=_relationship_source_refs(candidate, "explicit_relationship"),
                        reasons=["source_explicit_ufo_or_aerial_association", *[f"term:{term}" for term in sorted(aerial_terms)]],
                        source_component=0.9,
                        review_state="needs_human_review",
                        provenance_locator=f"source_records:{candidate['record_id']}#aerial-context",
                    )
                    relationships.append(explicit_aerial)

            if candidate.get("explicit_crop_mutilation_link") and not wrapper.get("crop_formation_ids"):
                source = candidate["sources"][0]
                raw_hash = normalize_space(source.get("source_hash"))
                source_hash = raw_hash if len(raw_hash) == 64 else sha256_bytes(raw_hash.encode("utf-8"))
                crop_candidate_id = stable_id(
                    "ccsc", "ufo_source_explicit", candidate["record_id"], source_hash, length=24
                )
                crop_candidate = {
                    "crop_source_candidate_id": crop_candidate_id,
                    "event_domain": "crop_circle",
                    "trace_eligible": False,
                    "trace_role": "context_only",
                    "source_kind": "ufo_timeline_source_explicit_crop_occurrence",
                    "source_id": source["source_id"],
                    "formation_ids": [],
                    "source_url": source.get("url"),
                    "source_hash": source_hash,
                    "provenance_locator": source.get("page_or_container"),
                    "dates": _date_interval_from_case(candidate),
                    "location": {
                        "place": candidate.get("location", {}).get("locality"),
                        "region": candidate.get("location", {}).get("admin1"),
                        "country": candidate.get("location", {}).get("country_code"),
                    },
                    "classification": f"explicit_source_{candidate.get('crop_relationship_type') or 'topical_context'}",
                    "record_type": "related_ground_event",
                    "crop_relationship_type": candidate.get("crop_relationship_type") or "topical_context",
                    "candidate_score": candidate.get("extraction", {}).get("candidate_score"),
                    "candidate_reasons": ["source_explicit_crop_circle_and_animal_mutilation"],
                    "direct_animal_terms": candidate.get("direct_animal_terms", []),
                    "finding_terms": candidate.get("finding_terms", []),
                    "explicit_negative": candidate.get("explicit_negative", False),
                    "evidence_excerpt": candidate.get("summary"),
                    "review_state": "needs_human_review",
                    "causality": "not_asserted",
                }
                crop_source_candidates.append(crop_candidate)
                object_ref = {
                    "domain": "crop_circle",
                    "dataset": "phase1_source_stated_crop_occurrences",
                    "external_id": crop_candidate_id,
                    "native_event_id": source["source_id"],
                }
                crop_relationship_type = candidate.get("crop_relationship_type") or "topical_context"
                explicit_crop = make_relationship(
                    subject=subject,
                    object_ref=object_ref,
                    relationship_type=crop_relationship_type,
                    assertion_mode="explicit_source",
                    match_tier=1,
                    temporal=_same_event_temporal(candidate),
                    spatial=_same_event_spatial(candidate),
                    source_refs=_relationship_source_refs(candidate, "explicit_relationship"),
                    reasons=[f"source_explicit_crop_circle_and_animal_mutilation_{crop_relationship_type}"],
                    source_component=1.0 if crop_relationship_type == "same_scene" else 0.8,
                    review_state="needs_human_review",
                    provenance_locator=f"source_records:{candidate['record_id']}#crop-context",
                )
                relationships.append(explicit_crop)
                explicit_ref = {
                    "domain": "crop_circle",
                    "dataset": "phase1_source_stated_crop_occurrences",
                    "external_id": crop_candidate_id,
                    "native_event_id": source["source_id"],
                    "relationship_id": explicit_crop["relationship_id"],
                }
                incident["external_event_refs"].append(dict(explicit_ref))
                candidate["external_event_refs"].append(dict(explicit_ref))

            crop_formation_ids = wrapper.get("crop_formation_ids", [])
            if crop_formation_ids:
                relationship_type = wrapper.get("crop_relationship_type") or "topical_context"
                for formation_id in sorted(set(crop_formation_ids)):
                    crop_event = crop_events_by_id.get(formation_id)
                    if crop_event is None:
                        continue
                    case_interval = _date_interval_from_case(candidate)
                    crop_interval = _date_interval_from_crop(crop_event)
                    comparison, temporal_score, offset_days = compare_intervals(case_interval, crop_interval)
                    temporal = {
                        "subject_interval": case_interval,
                        "object_interval": crop_interval,
                        "comparison": comparison,
                        "offset_days": offset_days,
                        "score": temporal_score,
                    }
                    spatial_comparison, spatial_score, distance, uncertainty, warnings = compare_locations(
                        candidate, crop_event
                    )
                    spatial = {
                        "subject_precision": candidate.get("location", {}).get("precision", "unknown"),
                        "object_precision": map_location_precision(crop_event.get("location_precision")),
                        "comparison": spatial_comparison,
                        "distance_km": distance,
                        "uncertainty_km": uncertainty,
                        "score": spatial_score,
                    }
                    crop_source_ref = {
                        "source_id": f"crop:{formation_id}",
                        "supports": "endpoint_identity",
                        "locator": normalize_space(crop_event.get("original_entry_url")) or "Crop Circle Atlas export",
                        "source_hash": sha256_bytes(canonical_json(crop_event).encode("utf-8")),
                    }
                    relationship = make_relationship(
                        subject=subject,
                        object_ref=_crop_endpoint(crop_event),
                        relationship_type=relationship_type,
                        assertion_mode="explicit_source",
                        match_tier=1 if relationship_type in {"same_scene", "reported_nearby"} else 2,
                        temporal=temporal,
                        spatial=spatial,
                        source_refs=[
                            *_relationship_source_refs(candidate, "explicit_relationship"),
                            crop_source_ref,
                        ],
                        reasons=[
                            (
                                f"source_explicit_{relationship_type}"
                                if wrapper.get("analysis", {}).get("crop_relationship_type")
                                else "native_crop_source_citation_lineage"
                            ),
                            *warnings,
                        ],
                        source_component=1.0 if relationship_type == "same_scene" else (0.85 if relationship_type == "reported_nearby" else 0.65),
                        review_state="needs_human_review",
                        provenance_locator=f"crop-source:{wrapper.get('crop_source_candidate_id')}->{formation_id}",
                    )
                    relationships.append(relationship)
                    external_ref = {
                        "domain": "crop_circle",
                        "dataset": "crop_circle_atlas_export_v1",
                        "external_id": formation_id,
                        "native_event_id": crop_event.get("event_id"),
                        "relationship_id": relationship["relationship_id"],
                    }
                    candidate["external_event_refs"].append(dict(external_ref))
                    incident["external_event_refs"].append(dict(external_ref))

    # Context/non-case rows still need a resolvable record-to-UFO lineage edge.
    # The candidate itself is the subject; this does not turn it into a
    # mutilation incident or assert an aerial association.
    for wrapper in sorted(
        candidate_wrappers, key=lambda item: item["candidate"]["record_id"]
    ):
        candidate = wrapper["candidate"]
        if normalize_space(candidate.get("canonical_incident_id")):
            continue
        event_id = normalize_space(wrapper.get("ufo_event_id"))
        if not event_id:
            continue
        object_ref = {
            "domain": "ufo",
            "dataset": "MYTbrain/ufo-timeline",
            "external_id": event_id,
            "native_event_id": wrapper.get("ufo_event_native_id") or event_id,
        }
        lineage = make_relationship(
            subject=_case_endpoint(candidate),
            object_ref=object_ref,
            relationship_type="duplicate_lineage",
            assertion_mode="deterministic_match",
            match_tier=2,
            temporal=_same_event_temporal(candidate),
            spatial=_same_event_spatial(candidate),
            source_refs=_relationship_source_refs(candidate, "duplicate_lineage"),
            reasons=["context_record_extracted_from_ufo_timeline_source_record"],
            source_component=1.0,
            review_state="machine_reviewed",
            provenance_locator=f"source_records:{candidate['record_id']}->{event_id}",
        )
        relationships.append(lineage)
        for ref in candidate.get("external_event_refs", []):
            if ref.get("domain") == "ufo" and str(ref.get("external_id")) == event_id:
                ref["relationship_id"] = lineage["relationship_id"]

    crop_by_year: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for event in crop_events:
        interval = _date_interval_from_crop(event)
        if interval["start"] and interval["start"][:4].isdigit():
            crop_by_year[int(interval["start"][:4])].append(event)
    crop_years = sorted(crop_by_year)

    # Computed candidates use only uncertainty-aware temporal/spatial evidence.
    for incident in canonical_incidents:
        interval = _date_interval_from_case(incident)
        if not interval["start"] or not interval["end"]:
            continue
        start_year = int(interval["start"][:4])
        end_year = int(interval["end"][:4])
        first_year_index = bisect_left(crop_years, start_year)
        last_year_index = bisect_right(crop_years, end_year)
        scored: list[tuple[float, int, dict[str, Any], dict[str, Any], dict[str, Any], list[str]]] = []
        for year in crop_years[first_year_index:last_year_index]:
            for crop in crop_by_year[year]:
                crop_interval = _date_interval_from_crop(crop)
                temporal_comparison, temporal_score, offset_days = compare_intervals(interval, crop_interval)
                spatial_comparison, spatial_score, distance, uncertainty, warnings = compare_locations(incident, crop)
                if temporal_comparison == "exact_day" and spatial_comparison in {"exact_site", "same_locality", "within_uncertainty"}:
                    tier = 3
                elif temporal_score >= 0.7 and spatial_comparison in {"same_locality", "same_county", "same_admin1", "within_uncertainty"}:
                    tier = 4
                elif temporal_score >= 0.4 and spatial_comparison in {"same_locality", "same_county", "same_admin1", "within_uncertainty"}:
                    tier = 5
                else:
                    continue
                score = 0.5 * temporal_score + 0.5 * spatial_score
                reasons = [
                    f"temporal:{temporal_comparison}",
                    f"spatial:{spatial_comparison}",
                    *warnings,
                ]
                scored.append(
                    (
                        score,
                        tier,
                        crop,
                        {
                            "subject_interval": interval,
                            "object_interval": crop_interval,
                            "comparison": temporal_comparison,
                            "offset_days": offset_days,
                            "score": temporal_score,
                        },
                        {
                            "subject_precision": incident["location"]["precision"],
                            "object_precision": map_location_precision(crop.get("location_precision")),
                            "comparison": spatial_comparison,
                            "distance_km": distance,
                            "uncertainty_km": uncertainty,
                            "score": spatial_score,
                        },
                        reasons,
                    )
                )
        for _, tier, crop, temporal, spatial, reasons in sorted(
            scored,
            key=lambda item: (-item[0], item[1], item[2]["external_id"]),
        ):
            crop_source_ref = {
                "source_id": f"crop:{crop['external_id']}",
                "supports": "endpoint_identity",
                "locator": normalize_space(crop.get("original_entry_url")) or "Crop Circle Atlas export",
                "source_hash": sha256_bytes(canonical_json(crop).encode("utf-8")),
            }
            relationship = make_relationship(
                subject=_case_endpoint(incident),
                object_ref=_crop_endpoint(crop),
                relationship_type="reported_nearby" if tier == 3 else "regional_context",
                assertion_mode="deterministic_match",
                match_tier=tier,
                temporal=temporal,
                spatial=spatial,
                source_refs=[*_relationship_source_refs(incident, "temporal_component"), crop_source_ref],
                reasons=[*reasons, "computed_candidate_not_source_assertion"],
                source_component=0.55,
                review_state="needs_human_review",
                provenance_locator=f"computed:{incident['record_id']}->{crop['external_id']}",
            )
            relationships.append(relationship)
            computed_ref = {
                "domain": "crop_circle",
                "dataset": "crop_circle_atlas_export_v1",
                "external_id": crop["external_id"],
                "native_event_id": crop.get("event_id"),
                "relationship_id": relationship["relationship_id"],
            }
            incident["external_event_refs"].append(dict(computed_ref))
            for wrapper in wrappers_by_incident.get(incident["record_id"], []):
                wrapper["candidate"]["external_event_refs"].append(dict(computed_ref))

    for incident in canonical_incidents:
        incident["external_event_refs"] = _dedupe_dicts(
            incident.get("external_event_refs", []),
            key_fields=("domain", "dataset", "external_id", "relationship_id"),
        )
    for wrapper in candidate_wrappers:
        candidate = wrapper["candidate"]
        candidate["external_event_refs"] = _dedupe_dicts(
            candidate.get("external_event_refs", []),
            key_fields=("domain", "dataset", "external_id", "relationship_id"),
        )
    crop_source_candidates.sort(key=lambda row: row["crop_source_candidate_id"])
    return _merge_relationship_rows(relationships), crop_source_candidates


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(canonical_json(row) + "\n")
    os.replace(temp, path)


def write_csv(path: Path, rows: Iterable[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    os.replace(temp, path)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temp, path)


def _count_by(rows: Iterable[Mapping[str, Any]], getter: Any) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        value = getter(row)
        counts[str(value or "unknown")] += 1
    return dict(sorted(counts.items()))


def build_seed_report(
    *,
    scan_summary: Mapping[str, Any],
    lineage_summary: Mapping[str, Any],
    crop_summary: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    canonical_incidents: Sequence[Mapping[str, Any]],
    related_events: Sequence[Mapping[str, Any]],
    rejected: Sequence[Mapping[str, Any]],
    duplicate_pairs: Sequence[Mapping[str, Any]],
    relationships: Sequence[Mapping[str, Any]],
    crop_source_candidates: Sequence[Mapping[str, Any]],
) -> str:
    def _display_summary_count(summary: Mapping[str, Any], key: str) -> str:
        value = summary.get(key)
        try:
            return f"{int(value):,}"
        except (TypeError, ValueError):
            return "unknown"

    def _distribution_lines(counts: Mapping[str, int]) -> list[str]:
        if not counts:
            return ["- None."]
        return [f"- `{key}`: {value:,}" for key, value in counts.items()]

    def _score_band(row: Mapping[str, Any]) -> str:
        try:
            score = float(row.get("extraction", {}).get("candidate_score"))
        except (TypeError, ValueError):
            return "unknown"
        if score < 0.20:
            return "0.00-0.19"
        if score < 0.40:
            return "0.20-0.39"
        if score < 0.60:
            return "0.40-0.59"
        if score < 0.80:
            return "0.60-0.79"
        return "0.80-1.00"

    def _has_coordinates(row: Mapping[str, Any], projection: str) -> bool:
        location = row.get("location", {})
        latitude = location.get(f"latitude_{projection}")
        longitude = location.get(f"longitude_{projection}")
        return (
            isinstance(latitude, (int, float))
            and not isinstance(latitude, bool)
            and math.isfinite(latitude)
            and isinstance(longitude, (int, float))
            and not isinstance(longitude, bool)
            and math.isfinite(longitude)
        )

    def _false_positive_lane(row: Mapping[str, Any]) -> str:
        if row.get("explicit_negative"):
            return "explicit_negative_or_nonclassic"
        if row.get("record_type") == "publication_event":
            return "research_or_publication_context"
        if row.get("record_type") == "aggregate_report":
            return "aggregate_claim"
        if row.get("structured_codes") and not row.get("direct_animal_terms") and not row.get("finding_terms"):
            return "taxonomy_or_glossary_only"
        return "other_context_or_noise"

    explicit_relationships = [
        row for row in relationships if row.get("assertion_mode") == "explicit_source"
    ]
    computed_relationships = [
        row for row in relationships if row.get("assertion_mode") == "deterministic_match"
    ]
    analyst_confirmed_relationships = [
        row for row in relationships if row.get("assertion_mode") == "analyst_confirmed"
    ]
    reviewed_relationship_rejections = [
        row for row in relationships if row.get("review_state") == "rejected"
    ]
    reviewed_record_rejections = [
        row
        for row in rejected
        if row.get("provenance", {}).get("review_state") == "rejected_as_noise"
    ]
    pending_context_review = max(0, len(rejected) - len(reviewed_record_rejections))

    relationship_modes = _count_by(relationships, lambda row: row.get("assertion_mode"))
    relationship_types = _count_by(relationships, lambda row: row.get("relationship_type"))
    explicit_relationship_types = _count_by(
        explicit_relationships, lambda row: row.get("relationship_type")
    )
    computed_match_tiers = _count_by(
        computed_relationships,
        lambda row: f"tier_{row.get('match_tier')}" if row.get("match_tier") is not None else "unknown",
    )
    computed_review_states = _count_by(
        computed_relationships, lambda row: row.get("review_state")
    )
    case_types = _count_by(candidates, lambda row: row.get("record_type"))
    sources = _count_by(
        candidates,
        lambda row: row.get("sources", [{}])[0].get("agency_or_publisher") if row.get("sources") else None,
    )
    countries = _count_by(candidates, lambda row: row.get("location", {}).get("country_code"))
    admin1_regions = _count_by(candidates, lambda row: row.get("location", {}).get("admin1"))
    decades = _count_by(
        candidates,
        lambda row: (
            f"{int(row['dates']['event_start'][:4]) // 10 * 10}s"
            if row.get("dates", {}).get("event_start")
            else "unknown"
        ),
    )
    date_precisions = _count_by(candidates, lambda row: row.get("dates", {}).get("precision"))
    coordinate_sources = _count_by(
        candidates, lambda row: row.get("location", {}).get("coordinate_source")
    )
    location_precisions = _count_by(
        candidates, lambda row: row.get("location", {}).get("precision")
    )
    score_bands = _count_by(candidates, _score_band)
    privacy_levels = _count_by(
        candidates, lambda row: row.get("location", {}).get("privacy_level")
    )
    false_positive_lanes = _count_by(rejected, _false_positive_lane)
    victim_species: Counter[str] = Counter()
    victim_groups: Counter[str] = Counter()
    for incident in canonical_incidents:
        for animal in incident.get("animals", []):
            victim_species[
                normalize_space(animal.get("reported_taxon_key"))
                or normalize_space(animal.get("normalized_common_name"))
                or "unknown"
            ] += 1
            victim_groups[normalize_space(animal.get("species_group")) or "unknown"] += 1
    incident_evidence_modes = _count_by(
        canonical_incidents,
        lambda row: row.get("extraction", {}).get("incident_evidence_mode"),
    )
    bovine_incidents = sum(
        1
        for row in canonical_incidents
        if any(animal.get("species_group") == "bovine" for animal in row.get("animals", []))
    )
    non_bovine_incidents = sum(
        1
        for row in canonical_incidents
        if any(animal.get("species_group") not in {"bovine", "unknown"} for animal in row.get("animals", []))
    )
    mixed_species_incidents = sum(
        1
        for row in canonical_incidents
        if len(
            {
                animal.get("reported_taxon_key")
                or animal.get("normalized_common_name")
                for animal in row.get("animals", [])
            }
        )
        > 1
    )

    internal_mapped = sum(1 for row in candidates if _has_coordinates(row, "internal"))
    public_mapped = sum(1 for row in candidates if _has_coordinates(row, "public"))
    generalized_locations = sum(
        1
        for row in candidates
        if row.get("location", {}).get("privacy_level") == "internal_only"
    )
    duplicate_cluster_sizes: Counter[int] = Counter()
    for incident in canonical_incidents:
        members = incident.get("constituent_record_ids")
        size = len(members) if isinstance(members, list) else 1
        duplicate_cluster_sizes[max(1, size)] += 1

    unresolved_access_keys = (
        "crop_source_access_gaps",
        "crop_source_url_rows_without_content",
        "crop_source_urls_without_content",
        "crop_source_access_unresolved",
        "crop_source_coverage_gaps",
        "coverage_gap_count",
    )
    unresolved_source_access: int | None = None
    unresolved_source_access_key: str | None = None
    for key in unresolved_access_keys:
        if key not in crop_summary:
            continue
        try:
            unresolved_source_access = int(crop_summary[key])
            unresolved_source_access_key = key
            break
        except (TypeError, ValueError):
            continue

    missing_lineage = lineage_summary.get("candidate_input_ids_without_lineage")
    malformed_count = scan_summary.get("malformed")
    lines = [
        "# Phase 1.1 Global Animal-Mutilation Cross-Domain Seed Report",
        "",
        "This report is a deterministic, species-inclusive discovery and correlation artifact. It does not establish that a reported incident occurred, the authenticity of crop formations, an anomalous cause, or causation between event domains.",
        "",
        "## Coverage",
        "",
        f"- UFO source records scanned: {_display_summary_count(scan_summary, 'scanned')}",
        f"- Malformed UFO source records: {_display_summary_count(scan_summary, 'malformed')}",
        f"- Deduplicated UFO events scanned for lineage: {_display_summary_count(lineage_summary, 'deduped_events_scanned')}",
        f"- Crop events scanned as context: {_display_summary_count(crop_summary, 'crop_events_scanned')}",
        f"- Crop assertions scanned: {_display_summary_count(crop_summary, 'crop_assertions_scanned')}",
        f"- Assertion-linked source URLs: {_display_summary_count(crop_summary, 'crop_assertion_unique_source_urls')}",
        f"- All record-level source URLs audited: {_display_summary_count(crop_summary, 'crop_unique_source_urls_scanned')}",
        f"- Catalog pages / formation slots scanned: {_display_summary_count(crop_summary, 'catalog_pages_scanned')} / {_display_summary_count(crop_summary, 'catalog_slots_scanned')}",
        "",
        "## Seed outputs",
        "",
        f"- Plausible candidate records: {len(candidates):,}",
        f"- Provisional canonical mutilation incidents: {len(canonical_incidents):,}",
        f"- Related/context records: {len(related_events):,}",
        f"- Context/noise candidates retained separately: {len(rejected):,}",
        f"- Provisional duplicate pairs: {len(duplicate_pairs):,}",
        f"- Crop-source narrative candidates: {len(crop_source_candidates):,}",
        f"- Cross-domain relationships: {len(relationships):,}",
        "",
        "## Inclusive animal coverage",
        "",
        "Species never determines eligibility. A source-local victim or possible-victim assertion is required; pets, predators, scavengers, and other contextual animals remain separately labeled.",
        "",
        f"- Incidents with a bovine victim assertion: {bovine_incidents:,}",
        f"- Incidents with a non-bovine victim assertion: {non_bovine_incidents:,}",
        f"- Mixed-species incidents: {mixed_species_incidents:,}",
        "",
        "### Victim species",
        "",
        *_distribution_lines(dict(sorted(victim_species.items()))),
        "",
        "### Victim animal group",
        "",
        *_distribution_lines(dict(sorted(victim_groups.items()))),
        "",
        "### Incident evidence mode",
        "",
        *_distribution_lines(incident_evidence_modes),
        "",
        "## Explicit source relationships",
        "",
        f"- Total explicit-source relationships: {len(explicit_relationships):,}",
        *_distribution_lines(explicit_relationship_types),
        "",
        "These rows preserve a relationship stated by a source. They do not verify either event's cause or authenticity.",
        "",
        "## Computed review candidates",
        "",
        f"- Total deterministic-match candidates: {len(computed_relationships):,}",
        f"- Analyst-confirmed relationships retained in a separate lane: {len(analyst_confirmed_relationships):,}",
        "",
        "### Match tier",
        "",
        *_distribution_lines(computed_match_tiers),
        "",
        "### Review state",
        "",
        *_distribution_lines(computed_review_states),
        "",
        "Computed matches are review candidates only. Country/state conflicts are rejected before locality matching, date intervals remain intervals, and locality centroids are never treated as formation sites.",
        "",
        "## Reviewed rejections",
        "",
        f"- Cross-domain relationships explicitly rejected during review: {len(reviewed_relationship_rejections):,}",
        f"- Candidate records explicitly marked `rejected_as_noise`: {len(reviewed_record_rejections):,}",
        f"- Context/noise candidates still awaiting recorded review: {pending_context_review:,}",
        "",
        "Machine-retained context is not described as a reviewed rejection unless its review state explicitly says so.",
        "",
        "## Unresolved source access",
        "",
        (
            f"- Crop source URLs without usable content: {unresolved_source_access:,} "
            f"(summary field `{unresolved_source_access_key}`)."
            if unresolved_source_access is not None
            else "- Crop source URLs without usable content: unknown in the current aggregate; inspect `crop_circle_source_access_audit.csv` for the authoritative dispositions."
        ),
        "- Missing, blocked, rights-limited, and narrative-free pages remain coverage gaps, never negative evidence.",
        "",
        "## Privacy generalization",
        "",
        f"- Candidate records with generalized/suppressed private locations: {generalized_locations:,}",
        f"- Candidate records with public coordinates: {public_mapped:,}",
        f"- Candidate records without public coordinates: {len(candidates) - public_mapped:,}",
        *_distribution_lines(privacy_levels),
        "",
        "## Extraction false-positive and control queue",
        "",
        f"- Total retained context/noise candidates: {len(rejected):,}",
        *_distribution_lines(false_positive_lanes),
        "",
        "These are deterministic extraction-control lanes, not analyst-confirmed false positives unless listed under Reviewed rejections.",
        "",
        "## Relationship overview",
        "",
        *_distribution_lines(relationship_modes),
        *_distribution_lines(relationship_types),
        "",
        "## Candidate distributions",
        "",
        "### Record type",
        "",
        *[f"- `{key}`: {value:,}" for key, value in case_types.items()],
        "",
        "### Source family",
        "",
        *[f"- `{key}`: {value:,}" for key, value in sources.items()],
        "",
        "### Country",
        "",
        *_distribution_lines(countries),
        "",
        "### Admin1 / state-province",
        "",
        *_distribution_lines(admin1_regions),
        "",
        "### Decade",
        "",
        *_distribution_lines(decades),
        "",
        "### Date precision",
        "",
        *_distribution_lines(date_precisions),
        "",
        "### Coordinate source",
        "",
        *_distribution_lines(coordinate_sources),
        "",
        "### Location precision",
        "",
        *_distribution_lines(location_precisions),
        "",
        "### Mapped / unmapped",
        "",
        f"- Internal coordinates available: {internal_mapped:,}",
        f"- Internal coordinates unavailable: {len(candidates) - internal_mapped:,}",
        f"- Public coordinates available: {public_mapped:,}",
        f"- Public coordinates suppressed or unavailable: {len(candidates) - public_mapped:,}",
        "",
        "### Candidate-score band",
        "",
        *_distribution_lines(score_bands),
        "",
        "### Provisional duplicate-cluster size",
        "",
        *(
            [
                f"- `{size}` constituent source record{'s' if size != 1 else ''}: {count:,} cluster{'s' if count != 1 else ''}"
                for size, count in sorted(duplicate_cluster_sizes.items())
            ]
            or ["- None."]
        ),
        "",
        "## Known controls and gaps",
        "",
        "- Structured taxonomy/glossary text is isolated from narrative evidence and cannot independently establish a case.",
        "- Species labels are sentence-local victim assertions; page-wide animal co-occurrence is retained only as context.",
        "- Non-bovine animals are fully eligible and are never rejected for species.",
        "- Ambiguous human or technical words such as `kids` and `RAM` are not species aliases.",
        "- Animal place names such as Cow Down and Fort Keogh Livestock Laboratory remain false-positive controls.",
        "- Missing, blocked, or rights-limited source pages remain coverage gaps, never negative evidence.",
        "- The catalog PDF is index/diagram-only; its absence of mutilation prose is not evidence of no relationship.",
        "- Official government and contemporary newspaper acquisition remains U.S.-first and is outside this existing-corpus seed run.",
        "- Every relationship fixes `causality` to `not_asserted`; crop records remain `context_only` and non-traceable.",
        "",
        "## Warnings and unresolved questions",
        "",
        f"- Malformed UFO rows requiring source repair: {malformed_count if malformed_count is not None else 'unknown'}.",
        f"- Candidate input IDs without deduplicated-UFO lineage: {missing_lineage if missing_lineage is not None else 'unknown'}.",
        f"- Context/noise candidates awaiting recorded review: {pending_context_review:,}.",
        f"- Computed relationships awaiting review or rejection: {sum(1 for row in computed_relationships if row.get('review_state') not in {'rejected', 'analyst_confirmed'}):,}.",
        "- Source-access coverage must be interpreted from the access audit when an aggregate unresolved count is unavailable.",
        "- Automated scores prioritize review; they do not make canonical scientific decisions or assert causality.",
        "",
    ]
    return "\n".join(lines)


def _jsonl_count(path: Path) -> int:
    with path.open("rb") as handle:
        return sum(1 for line in handle if line.strip())


def _csv_count(path: Path) -> int:
    with path.open(encoding="utf-8", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def _case_source_evidence_identity(source: Mapping[str, Any]) -> dict[str, str]:
    source_ref = _source_ref(source, "validation_identity")
    source_hash = normalize_space(source_ref.get("source_hash")).lower()
    if not re.fullmatch(r"[a-f0-9]{64}", source_hash):
        raise SeedPipelineError(
            f"Case source lacks authoritative SHA-256 provenance: {source_ref.get('source_id')}"
        )
    return {
        "source_id": normalize_space(source_ref.get("source_id")),
        "source_hash": source_hash,
        "locator": normalize_space(source_ref.get("locator")),
    }


def _crop_candidate_source_evidence_identity(
    source_candidate: Mapping[str, Any],
) -> dict[str, str] | None:
    source_id = normalize_space(source_candidate.get("source_id"))
    source_hash = normalize_space(source_candidate.get("source_hash")).lower()
    if not source_id or not re.fullmatch(r"[a-f0-9]{64}", source_hash):
        return None
    return {
        "source_id": source_id,
        "source_hash": source_hash,
        "locator": normalize_space(source_candidate.get("provenance_locator"))
        or normalize_space(source_candidate.get("source_url"))
        or "source locator unavailable",
    }


def build_validation_provenance(
    candidate_wrappers: Sequence[Mapping[str, Any]],
    candidates: Sequence[Mapping[str, Any]],
    canonical_incidents: Sequence[Mapping[str, Any]],
    crop_source_candidates: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Persist independent evidence for practical deterministic offline validation."""

    wrappers_by_id = {
        normalize_space(wrapper.get("candidate", {}).get("record_id")): wrapper
        for wrapper in candidate_wrappers
        if normalize_space(wrapper.get("candidate", {}).get("record_id"))
    }
    decisions: list[dict[str, Any]] = []
    for candidate in sorted(candidates, key=lambda row: row["record_id"]):
        record_id = normalize_space(candidate.get("record_id"))
        wrapper = wrappers_by_id.get(record_id)
        decision = wrapper.get("validation_decision") if wrapper else None
        if not isinstance(decision, Mapping):
            raise SeedPipelineError(
                "Candidate validation provenance is missing; restart extraction without an older resume spool: "
                + record_id
            )
        expected = _expected_case_projection(candidate)
        if decision.get("expected") != expected:
            raise SeedPipelineError(
                f"Candidate validation projection changed during extraction: {record_id}"
            )
        row = json.loads(canonical_json(dict(decision)))
        row["record_id"] = record_id
        row["derived_from_record_id"] = record_id
        decisions.append(row)

    for incident in sorted(canonical_incidents, key=lambda row: row["record_id"]):
        member_wrappers = [
            wrappers_by_id[normalize_space(record_id)]
            for record_id in incident.get("constituent_record_ids", [])
            if normalize_space(record_id) in wrappers_by_id
        ]
        if not member_wrappers:
            raise SeedPipelineError(
                f"Canonical incident validation provenance is missing: {incident.get('record_id')}"
            )
        primary_wrapper = max(
            member_wrappers,
            key=lambda wrapper: (
                float(
                    wrapper.get("candidate", {})
                    .get("extraction", {})
                    .get("candidate_score")
                    or 0
                ),
                normalize_space(wrapper.get("candidate", {}).get("record_id")),
            ),
        )
        base_decision = primary_wrapper.get("validation_decision")
        if not isinstance(base_decision, Mapping):
            raise SeedPipelineError(
                f"Canonical incident source decision is missing: {incident.get('record_id')}"
            )
        base = dict(base_decision)
        base.pop("expected", None)
        base.pop("expected_projection_sha256", None)
        row = _finish_validation_decision(base, incident)
        row["record_id"] = normalize_space(incident.get("record_id"))
        row["derived_from_record_id"] = normalize_space(
            primary_wrapper.get("candidate", {}).get("record_id")
        )
        decisions.append(row)

    source_evidence_by_key: dict[str, dict[str, str]] = {}
    for case in [*candidates, *canonical_incidents]:
        for source in case.get("sources", []):
            identity = _case_source_evidence_identity(source)
            source_evidence_by_key[canonical_json(identity)] = identity
    for source_candidate in crop_source_candidates:
        identity = _crop_candidate_source_evidence_identity(source_candidate)
        if identity is not None:
            source_evidence_by_key[canonical_json(identity)] = identity

    ufo_endpoint_by_key: dict[str, dict[str, Any]] = {}
    for wrapper in candidate_wrappers:
        endpoint = wrapper.get("ufo_endpoint_provenance")
        if not isinstance(endpoint, Mapping):
            continue
        endpoint_row = {
            "dataset": normalize_space(endpoint.get("dataset")),
            "external_id": normalize_space(endpoint.get("external_id")),
            "native_event_id": endpoint.get("native_event_id"),
            "deduped_event_sha256": normalize_space(
                endpoint.get("deduped_event_sha256")
            ).lower(),
            "canonical_input_id": normalize_space(
                endpoint.get("canonical_input_id")
            ),
        }
        if not endpoint_row["external_id"] or not re.fullmatch(
            r"[a-f0-9]{64}", endpoint_row["deduped_event_sha256"]
        ):
            raise SeedPipelineError("UFO endpoint validation provenance is incomplete")
        ufo_endpoint_by_key[canonical_json(endpoint_row)] = endpoint_row

    payload: dict[str, Any] = {
        "schema_version": VALIDATION_PROVENANCE_SCHEMA_VERSION,
        "authority": (
            "captured_from_pinned_source_and_deduplicated_inputs_before_relationship_generation"
        ),
        "ufo_endpoints": [ufo_endpoint_by_key[key] for key in sorted(ufo_endpoint_by_key)],
        "source_evidence": [
            source_evidence_by_key[key] for key in sorted(source_evidence_by_key)
        ],
        "case_decisions": sorted(decisions, key=lambda row: row["record_id"]),
    }
    payload["registry_sha256"] = sha256_bytes(canonical_json(payload).encode("utf-8"))
    return payload


def run_extract(args: argparse.Namespace) -> dict[str, Any]:
    starter_pack = Path(args.starter_pack).resolve()
    crop_zip = Path(args.crop_zip).resolve()
    catalog_pdf = Path(args.catalog_pdf).resolve()
    source_records = Path(args.source_records).resolve()
    deduped_events = Path(args.deduped_events).resolve()
    output_dir = Path(args.output_dir).resolve()
    work_dir = output_dir / ".work"
    allow_partial = bool(args.allow_partial)
    if args.limit is not None and not allow_partial:
        raise SeedPipelineError("--limit requires --allow-partial")

    starter_hash = verify_file_hash(
        starter_pack, PINNED_STARTER_PACK_SHA256, "Cattle mutilation starter pack"
    )
    crop_hash = verify_file_hash(crop_zip, PINNED_CROP_ZIP_SHA256, "Crop Circle Atlas export")
    pdf_hash = verify_file_hash(catalog_pdf, PINNED_COMBINED_PDF_SHA256, "Crop Circle catalog PDF")
    crop_data = load_crop_package(crop_zip, allow_partial=allow_partial)

    candidate_wrappers, scan_summary = scan_ufo_source_records(
        source_records,
        work_dir,
        resume=bool(args.resume),
        limit=args.limit,
    )
    if not allow_partial and scan_summary["scanned"] != PINNED_SOURCE_RECORD_COUNT:
        raise SeedPipelineError(
            f"UFO source count changed: expected {PINNED_SOURCE_RECORD_COUNT:,}, scanned {scan_summary['scanned']:,}"
        )
    lineage_summary = attach_ufo_lineage(
        candidate_wrappers,
        deduped_events,
        allow_partial=allow_partial,
    )
    crop_source_candidates, crop_audit_rows, crop_summary = scan_crop_sources(
        crop_data,
        catalog_pdf_path=catalog_pdf,
        acquisition_audit_path=(Path(args.acquisition_audit).resolve() if args.acquisition_audit else None),
        private_cache_dir=(Path(args.private_cache_dir).resolve() if args.private_cache_dir else None),
        allow_partial=allow_partial,
    )
    crop_case_wrappers = promote_crop_source_cases(
        crop_source_candidates,
        crop_data["events"],
    )
    candidate_wrappers.extend(crop_case_wrappers)
    # Defense in depth: enforce the public privacy projection again before
    # clustering and output generation, including after a same-version resume.
    for wrapper in candidate_wrappers:
        _enforce_private_public_location(wrapper["candidate"])
    canonical_incidents, duplicate_pairs, record_to_cluster = cluster_candidates(candidate_wrappers)
    crop_summary["crop_source_cases_promoted"] = len(crop_case_wrappers)
    relationships, crop_source_candidates = build_relationships(
        candidate_wrappers,
        canonical_incidents,
        crop_data["events"],
        crop_source_candidates,
    )

    candidates = sorted(
        [wrapper["candidate"] for wrapper in candidate_wrappers],
        key=lambda row: row["record_id"],
    )
    related_events = [row for row in candidates if row["record_type"] != "mutilation_case"]
    rejected_ids = {
        wrapper["candidate"]["record_id"]
        for wrapper in candidate_wrappers
        if wrapper.get("analysis", {}).get("disposition")
        in {"structured_code_review", "explicit_negative_context", "context_or_noise_candidate"}
    }
    rejected = [row for row in candidates if row["record_id"] in rejected_ids]

    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "candidate_records.jsonl", candidates)
    write_jsonl(output_dir / "canonical_incidents.jsonl", canonical_incidents)
    write_jsonl(output_dir / "related_events.jsonl", related_events)
    write_jsonl(output_dir / "rejected_or_noise_candidates.jsonl", rejected)
    write_jsonl(output_dir / "cross_domain_relationships.jsonl", relationships)
    write_jsonl(output_dir / "crop_circle_source_candidates.jsonl", crop_source_candidates)
    write_csv(output_dir / "duplicate_pairs.csv", duplicate_pairs, DUPLICATE_PAIR_FIELDS)
    write_csv(output_dir / "crop_circle_source_access_audit.csv", crop_audit_rows, CROP_AUDIT_FIELDS)
    finalize_extraction_audit(
        Path(scan_summary["audit_spool"]),
        output_dir / "extraction_audit.csv",
        record_to_cluster,
    )
    report = build_seed_report(
        scan_summary=scan_summary,
        lineage_summary=lineage_summary,
        crop_summary=crop_summary,
        candidates=candidates,
        canonical_incidents=canonical_incidents,
        related_events=related_events,
        rejected=rejected,
        duplicate_pairs=duplicate_pairs,
        relationships=relationships,
        crop_source_candidates=crop_source_candidates,
    )
    _atomic_write_text(output_dir / "seed_report.md", report)

    input_identities = {
        "starter_pack": {
            "file_name": starter_pack.name,
            "size_bytes": starter_pack.stat().st_size,
            "sha256": starter_hash,
        },
        "crop_circle_export": {
            "file_name": crop_zip.name,
            "size_bytes": crop_zip.stat().st_size,
            "sha256": crop_hash,
            "source_commit": crop_data["manifest"].get("source_commit"),
        },
        "catalog_pdf": {
            "file_name": catalog_pdf.name,
            "size_bytes": catalog_pdf.stat().st_size,
            "sha256": pdf_hash,
        },
        "ufo_source_records": {
            "file_name": source_records.name,
            "size_bytes": source_records.stat().st_size,
            "sha256": sha256_file(source_records),
        },
        "ufo_deduped_events": {
            "file_name": deduped_events.name,
            "size_bytes": deduped_events.stat().st_size,
            "sha256": sha256_file(deduped_events),
        },
    }
    acquisition_audit_path = (
        Path(args.acquisition_audit).resolve() if args.acquisition_audit else None
    )
    cache_inventory_hashes: list[str] = []
    if acquisition_audit_path is not None and acquisition_audit_path.is_file():
        with acquisition_audit_path.open(encoding="utf-8", newline="") as handle:
            acquisition_rows = list(csv.DictReader(handle))
        cache_inventory_hashes = sorted(
            {
                normalize_space(row.get("content_sha256"))
                for row in acquisition_rows
                if re.fullmatch(
                    r"[a-fA-F0-9]{64}", normalize_space(row.get("content_sha256"))
                )
            }
        )
        input_identities["crop_source_acquisition_audit"] = {
            "file_name": acquisition_audit_path.name,
            "size_bytes": acquisition_audit_path.stat().st_size,
            "sha256": sha256_file(acquisition_audit_path),
            "rows": len(acquisition_rows),
            "content_object_count": len(cache_inventory_hashes),
            "content_inventory_sha256": sha256_bytes(
                canonical_json(cache_inventory_hashes).encode("utf-8")
            ),
        }
    else:
        input_identities["crop_source_acquisition_audit"] = {
            "status": "not_supplied",
            "rows": 0,
            "content_object_count": 0,
            "content_inventory_sha256": sha256_bytes(b"[]"),
        }
    counts = {
        **{key: value for key, value in scan_summary.items() if isinstance(value, int)},
        **lineage_summary,
        **crop_summary,
        "candidate_records": len(candidates),
        "canonical_incidents": len(canonical_incidents),
        "related_events": len(related_events),
        "rejected_or_noise_candidates": len(rejected),
        "duplicate_pairs": len(duplicate_pairs),
        "cross_domain_relationships": len(relationships),
        "explicit_source_relationships": sum(1 for row in relationships if row["assertion_mode"] == "explicit_source"),
        "computed_relationships": sum(1 for row in relationships if row["assertion_mode"] == "deterministic_match"),
        "crop_circle_source_candidates": len(crop_source_candidates),
        "crop_access_audit_rows": len(crop_audit_rows),
        "public_locations_generalized": sum(1 for row in candidates if row["location"]["privacy_level"] == "internal_only"),
        "canonical_incidents_with_bovine_victim": sum(
            1
            for row in canonical_incidents
            if any(animal.get("species_group") == "bovine" for animal in row.get("animals", []))
        ),
        "canonical_incidents_with_non_bovine_victim": sum(
            1
            for row in canonical_incidents
            if any(animal.get("species_group") not in {"bovine", "unknown"} for animal in row.get("animals", []))
        ),
        "canonical_incidents_with_unknown_animal_victim": sum(
            1
            for row in canonical_incidents
            if any(animal.get("species_group") == "unknown" for animal in row.get("animals", []))
        ),
        "canonical_mixed_species_incidents": sum(
            1
            for row in canonical_incidents
            if len(
                {
                    animal.get("reported_taxon_key")
                    or animal.get("normalized_common_name")
                    for animal in row.get("animals", [])
                }
            )
            > 1
        ),
    }
    output_hashes = {
        name: {
            "size_bytes": (output_dir / name).stat().st_size,
            "sha256": sha256_file(output_dir / name),
        }
        for name in OUTPUT_NAMES
        if name != "run_manifest.json"
    }
    scoring_configuration = {
        "animal_taxonomy": taxonomy_manifest(),
        "generic_animal_terms": list(GENERIC_ANIMAL_TERMS),
        "mutilation_terms": MUTILATION_TERMS,
        "harm_terms": HARM_TERMS,
        "distinctive_harm_terms": DISTINCTIVE_HARM_TERMS,
        "anatomy_terms": ANATOMY_TERMS,
        "crop_terms": CROP_TERMS,
        "relationship_tiers": [1, 2, 3, 4, 5],
        "computed_match_limit": None,
        "causality": "not_asserted",
    }
    try:
        pypdf_version = package_version("pypdf")
    except PackageNotFoundError:
        pypdf_version = "unavailable"
    validation_provenance = build_validation_provenance(
        candidate_wrappers,
        candidates,
        canonical_incidents,
        crop_source_candidates,
    )
    manifest = {
        "schema_version": "animal-mutilation-seed-run-manifest-v1.1.12",
        "pipeline_version": PIPELINE_VERSION,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "base_commit": PINNED_BASE_COMMIT,
        "run_mode": "partial_fixture" if allow_partial else "full_global_existing_corpora",
        "timestamp_policy": "no_wall_clock_timestamp_in_deterministic_outputs",
        "network_acquisition_policy": "separate_explicit_acquire_stage_private_cache_only",
        "tool_versions": {
            "python": ".".join(str(item) for item in sys.version_info[:3]),
            "pypdf": pypdf_version,
            "crop_source_acquisition_audit_schema": ACQUISITION_AUDIT_SCHEMA_VERSION,
            "crop_source_cache_schema": ACQUISITION_CACHE_SCHEMA_VERSION,
            "catalog_pdf_adapter": CATALOG_ADAPTER_VERSION,
        },
        "configuration": {
            "scoring_sha256": sha256_bytes(
                canonical_json(scoring_configuration).encode("utf-8")
            ),
            "source_scan_checkpoint_version": PIPELINE_VERSION,
            "privacy_policy": (
                "redact_all_named_private_properties_and_generalize_"
                "modern_or_precise_unnamed_private_locations"
            ),
            "computed_relationship_policy": "retain_all_tier_3_to_5_review_leads",
        },
        "causality": "not_asserted",
        "crop_trace_policy": "context_only_trace_eligible_false",
        "inputs": input_identities,
        "counts": dict(sorted(counts.items())),
        "outputs": output_hashes,
        "validation_provenance": validation_provenance,
        "coverage_gaps": {
            "crop_source_url_rows_without_content": sum(
                1
                for row in crop_audit_rows
                if row["item_kind"] == "crop_source_url" and row["coverage_status"] == "coverage_gap"
            ),
            "crop_assertions_without_packaged_narrative": sum(
                1
                for row in crop_audit_rows
                if row["item_kind"] == "crop_assertion" and row["disposition"] == "no_packaged_narrative"
            ),
            "catalog_index_only_pages": crop_summary["catalog_index_only_pages"],
        },
    }
    _atomic_write_text(
        output_dir / "run_manifest.json",
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    validation = validate_outputs(output_dir, crop_zip_path=crop_zip)
    return {"output_dir": str(output_dir), "manifest": manifest, "validation": validation}


def _evidence_identity_tuple(value: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        normalize_space(value.get("source_id")),
        normalize_space(value.get("source_hash")).lower(),
        normalize_space(value.get("locator")),
    )


def _validate_case_decision(
    case: Mapping[str, Any], decision: Mapping[str, Any]
) -> None:
    record_id = normalize_space(case.get("record_id"))
    expected = decision.get("expected")
    if not isinstance(expected, Mapping):
        raise SeedPipelineError(f"Case validation decision is incomplete: {record_id}")
    expected_hash = normalize_space(decision.get("expected_projection_sha256")).lower()
    if not re.fullmatch(r"[a-f0-9]{64}", expected_hash) or expected_hash != sha256_bytes(
        canonical_json(dict(expected)).encode("utf-8")
    ):
        raise SeedPipelineError(f"Case validation decision hash mismatch: {record_id}")

    actual_dates = _case_date_projection(case)
    if actual_dates != expected.get("dates"):
        raise SeedPipelineError(f"Case date decision mismatch: {record_id}")
    actual_location = _case_public_location_projection(case)
    if actual_location != expected.get("public_location"):
        raise SeedPipelineError(f"Case public-location decision mismatch: {record_id}")
    actual_projection = _expected_case_projection(case)
    for field in (
        "event_domain",
        "explicit_negative",
        "negative_only",
        "animals",
        "animal_context",
    ):
        if actual_projection.get(field) != expected.get(field):
            raise SeedPipelineError(
                f"Case {field.replace('_', '-')} decision mismatch: {record_id}"
            )

    basis = normalize_space(decision.get("basis"))
    source_date = (
        decision.get("source_date")
        if isinstance(decision.get("source_date"), Mapping)
        else {}
    )
    source_location = (
        decision.get("source_location")
        if isinstance(decision.get("source_location"), Mapping)
        else {}
    )
    if basis == "ufo_source_record":
        source_precision = normalize_space(source_date.get("precision")) or "unknown"
        if actual_dates["precision"] != source_precision:
            raise SeedPipelineError(f"Case date precision was changed from source: {record_id}")
        if actual_dates["event_start"] != source_date.get("start"):
            raise SeedPipelineError(f"Case date start was changed from source: {record_id}")
        source_end = source_date.get("end")
        if source_end is not None and actual_dates["event_end"] != source_end:
            raise SeedPipelineError(f"Case date end was changed from source: {record_id}")
        if source_end is None and source_precision in {"exact_day", "exact_time"}:
            if actual_dates["event_end"] != actual_dates["event_start"]:
                raise SeedPipelineError(f"Exact case date did not remain a singleton: {record_id}")
        if (
            source_end is None
            and source_precision not in {"exact_day", "exact_time", "unknown"}
            and actual_dates["event_start"] is not None
            and actual_dates["event_end"] == actual_dates["event_start"]
        ):
            raise SeedPipelineError(f"Approximate case date collapsed to a day: {record_id}")

        source_location_precision = (
            normalize_space(source_location.get("precision")) or "unknown"
        )
        suppression_required = bool(
            source_location.get("public_suppression_required")
        )
        if suppression_required:
            if (
                actual_location["privacy_level"] != "internal_only"
                or actual_location["latitude_public"] is not None
                or actual_location["longitude_public"] is not None
                or actual_location["precision"] not in {"locality", "unknown"}
            ):
                raise SeedPipelineError(
                    f"Private source location was not safely generalized: {record_id}"
                )
            raw_source_hash = normalize_space(source_location.get("raw_text_sha256"))
            public_raw = normalize_space(actual_location.get("raw_text"))
            if raw_source_hash and public_raw and sha256_bytes(
                public_raw.encode("utf-8")
            ) == raw_source_hash:
                raise SeedPipelineError(f"Private raw address leaked publicly: {record_id}")
        elif actual_location["precision"] != source_location_precision:
            raise SeedPipelineError(
                f"Case location precision was changed from source: {record_id}"
            )
    elif basis == "crop_source_context":
        if actual_location["precision"] not in {"approximate", "unknown"}:
            raise SeedPipelineError(
                f"Crop-context animal location became too precise: {record_id}"
            )
    else:
        raise SeedPipelineError(f"Unknown case validation decision basis: {record_id}")


def validate_outputs(output_dir: Path, *, crop_zip_path: Path | None = None) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    missing = [name for name in OUTPUT_NAMES if not (output_dir / name).is_file()]
    if missing:
        raise SeedPipelineError(f"Missing output artifacts: {', '.join(missing)}")
    manifest = json.loads((output_dir / "run_manifest.json").read_text(encoding="utf-8"))
    for name, identity in manifest.get("outputs", {}).items():
        path = output_dir / name
        if path.stat().st_size != identity["size_bytes"] or sha256_file(path) != identity["sha256"]:
            raise SeedPipelineError(f"Output integrity mismatch: {name}")

    candidates = list(read_jsonl(output_dir / "candidate_records.jsonl"))
    incidents = list(read_jsonl(output_dir / "canonical_incidents.jsonl"))
    related = list(read_jsonl(output_dir / "related_events.jsonl"))
    rejected = list(read_jsonl(output_dir / "rejected_or_noise_candidates.jsonl"))
    relationships = list(read_jsonl(output_dir / "cross_domain_relationships.jsonl"))
    crop_candidates = list(read_jsonl(output_dir / "crop_circle_source_candidates.jsonl"))
    with (output_dir / "crop_circle_source_access_audit.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        crop_audit = list(csv.DictReader(handle))
    expected_counts = manifest["counts"]
    actual_counts = {
        "candidate_records": len(candidates),
        "canonical_incidents": len(incidents),
        "related_events": len(related),
        "rejected_or_noise_candidates": len(rejected),
        "cross_domain_relationships": len(relationships),
        "crop_circle_source_candidates": len(crop_candidates),
        "duplicate_pairs": _csv_count(output_dir / "duplicate_pairs.csv"),
        "crop_access_audit_rows": _csv_count(output_dir / "crop_circle_source_access_audit.csv"),
        "scanned": _csv_count(output_dir / "extraction_audit.csv"),
    }
    for key, actual in actual_counts.items():
        if int(expected_counts[key]) != actual:
            raise SeedPipelineError(
                f"Output count mismatch for {key}: manifest={expected_counts[key]}, actual={actual}"
            )

    candidate_ids = {row["record_id"] for row in candidates}
    incident_ids = {row["record_id"] for row in incidents}
    crop_candidate_ids = {row["crop_source_candidate_id"] for row in crop_candidates}
    cases_by_id = {row["record_id"]: row for row in [*candidates, *incidents]}
    crop_candidates_by_id = {
        row["crop_source_candidate_id"]: row for row in crop_candidates
    }
    validation_provenance = manifest.get("validation_provenance")
    if not isinstance(validation_provenance, Mapping):
        raise SeedPipelineError("Run manifest lacks authoritative validation provenance")
    if validation_provenance.get("schema_version") != VALIDATION_PROVENANCE_SCHEMA_VERSION:
        raise SeedPipelineError("Run manifest validation provenance schema changed")
    registry_hash = normalize_space(
        validation_provenance.get("registry_sha256")
    ).lower()
    registry_payload = dict(validation_provenance)
    registry_payload.pop("registry_sha256", None)
    if not re.fullmatch(r"[a-f0-9]{64}", registry_hash) or registry_hash != sha256_bytes(
        canonical_json(registry_payload).encode("utf-8")
    ):
        raise SeedPipelineError("Run manifest validation provenance hash mismatch")

    decision_rows = validation_provenance.get("case_decisions")
    if not isinstance(decision_rows, list):
        raise SeedPipelineError("Run manifest case validation decisions are missing")
    decisions_by_id = {
        normalize_space(row.get("record_id")): row
        for row in decision_rows
        if isinstance(row, Mapping) and normalize_space(row.get("record_id"))
    }
    expected_case_ids = candidate_ids | incident_ids
    if len(decisions_by_id) != len(decision_rows) or set(decisions_by_id) != expected_case_ids:
        raise SeedPipelineError(
            "Run manifest must contain one authoritative decision per emitted case record"
        )

    source_evidence_rows = validation_provenance.get("source_evidence")
    if not isinstance(source_evidence_rows, list):
        raise SeedPipelineError("Run manifest source-evidence registry is missing")
    authoritative_source_evidence = {
        _evidence_identity_tuple(row)
        for row in source_evidence_rows
        if isinstance(row, Mapping)
    }
    if len(authoritative_source_evidence) != len(source_evidence_rows) or any(
        not source_id
        or not re.fullmatch(r"[a-f0-9]{64}", source_hash)
        or not locator
        for source_id, source_hash, locator in authoritative_source_evidence
    ):
        raise SeedPipelineError("Run manifest source-evidence registry is malformed")
    emitted_source_evidence: set[tuple[str, str, str]] = set()
    for case in [*candidates, *incidents]:
        for source in case.get("sources", []):
            emitted_source_evidence.add(
                _evidence_identity_tuple(_case_source_evidence_identity(source))
            )
    for source_candidate in crop_candidates:
        identity = _crop_candidate_source_evidence_identity(source_candidate)
        if identity is not None:
            emitted_source_evidence.add(_evidence_identity_tuple(identity))
    if emitted_source_evidence != authoritative_source_evidence:
        raise SeedPipelineError(
            "Emitted source provenance does not match the authoritative manifest registry"
        )

    ufo_endpoint_rows = validation_provenance.get("ufo_endpoints")
    if not isinstance(ufo_endpoint_rows, list):
        raise SeedPipelineError("Run manifest UFO endpoint registry is missing")
    authoritative_ufo_endpoints: set[tuple[str, str]] = set()
    for endpoint in ufo_endpoint_rows:
        if not isinstance(endpoint, Mapping) or not re.fullmatch(
            r"[a-f0-9]{64}", normalize_space(endpoint.get("deduped_event_sha256")).lower()
        ):
            raise SeedPipelineError("Run manifest UFO endpoint provenance is malformed")
        external_id = normalize_space(endpoint.get("external_id"))
        native_id = normalize_space(endpoint.get("native_event_id"))
        if not external_id or not native_id:
            raise SeedPipelineError("Run manifest UFO endpoint identity is incomplete")
        authoritative_ufo_endpoints.add((external_id, native_id))

    crop_event_ids: set[str] = set()
    crop_events_by_id: dict[str, Mapping[str, Any]] = {}
    crop_event_source_evidence: set[tuple[str, str, str]] = set()
    crop_data: dict[str, Any] | None = None
    if crop_zip_path is not None:
        crop_data = load_crop_package(crop_zip_path, allow_partial=manifest.get("run_mode") == "partial_fixture")
        crop_events_by_id = {
            normalize_space(row.get("external_id")): row for row in crop_data["events"]
        }
        crop_event_ids = set(crop_events_by_id)
        crop_event_source_evidence = {
            (
                f"crop:{normalize_space(row.get('external_id'))}",
                sha256_bytes(canonical_json(row).encode("utf-8")),
                normalize_space(row.get("original_entry_url"))
                or "Crop Circle Atlas export",
            )
            for row in crop_data["events"]
        }
        expected_audit_sets = {
            "crop_event": crop_event_ids,
            "crop_assertion": {
                normalize_space(row.get("assertion_id")) for row in crop_data["assertions"]
            },
            "crop_source_url": {target.url for target in crop_data["targets"]},
            "crop_listing_source_url": {
                stable_id("listing-url", url, length=16)
                for url in crop_data.get("listing_source_urls", [])
            },
            **crop_image_narrative_expected_sets(crop_data.get("image_links", [])),
        }
        for item_kind, expected in expected_audit_sets.items():
            actual = [
                row["source_record_url"] if item_kind == "crop_source_url" else row["item_id"]
                for row in crop_audit
                if row.get("item_kind") == item_kind
            ]
            if len(actual) != len(set(actual)) or set(actual) != expected:
                raise SeedPipelineError(
                    f"Crop audit does not provide one exact disposition per {item_kind}"
                )
    for item_kind, expected_count in (
        ("catalog_pdf_page", int(expected_counts["catalog_pages_scanned"])),
        ("catalog_pdf_slot", int(expected_counts["catalog_slots_scanned"])),
    ):
        actual_ids = [row["item_id"] for row in crop_audit if row.get("item_kind") == item_kind]
        if len(actual_ids) != expected_count or len(set(actual_ids)) != expected_count:
            raise SeedPipelineError(
                f"Crop audit does not provide one exact disposition per {item_kind}"
            )
    if any(not normalize_space(row.get("disposition")) for row in crop_audit):
        raise SeedPipelineError("Crop audit contains an item without a deterministic disposition")
    relationship_ids: set[str] = set()
    for relationship in relationships:
        relationship_id = relationship.get("relationship_id")
        if not re.fullmatch(r"rel_[a-f0-9]{16,64}", str(relationship_id)):
            raise SeedPipelineError(f"Invalid relationship ID: {relationship_id}")
        if relationship_id in relationship_ids:
            raise SeedPipelineError(f"Duplicate relationship ID: {relationship_id}")
        relationship_ids.add(str(relationship_id))
        if relationship.get("causality") != "not_asserted":
            raise SeedPipelineError(f"Causality invariant failed: {relationship_id}")
        if relationship.get("assertion_mode") == "deterministic_match" and relationship.get("review_state") == "analyst_confirmed":
            raise SeedPipelineError(f"Computed relationship was auto-confirmed: {relationship_id}")
        subject_id = str(relationship["subject"]["external_id"])
        if subject_id not in incident_ids and subject_id not in candidate_ids:
            raise SeedPipelineError(f"Relationship subject does not resolve: {relationship_id}")
        if relationship["subject"] != _case_endpoint(cases_by_id[subject_id]):
            raise SeedPipelineError(
                f"Relationship subject identity does not match emitted case: {relationship_id}"
            )
        object_domain = relationship["object"]["domain"]
        object_id = str(relationship["object"]["external_id"])
        if object_domain == "crop_circle" and object_id not in crop_candidate_ids and crop_event_ids and object_id not in crop_event_ids:
            raise SeedPipelineError(f"Crop relationship object does not resolve: {relationship_id}")
        if object_domain == "crop_circle" and object_id in crop_event_ids and crop_data is not None:
            crop_event = crop_events_by_id[object_id]
            if relationship["object"] != _crop_endpoint(crop_event):
                raise SeedPipelineError(
                    f"Crop relationship object identity does not match pinned event: {relationship_id}"
                )
        elif object_domain == "crop_circle" and object_id in crop_candidates_by_id:
            crop_candidate = crop_candidates_by_id[object_id]
            expected_crop_candidate_endpoint = {
                "domain": "crop_circle",
                "dataset": "phase1_source_stated_crop_occurrences",
                "external_id": object_id,
                "native_event_id": crop_candidate.get("source_id"),
            }
            if relationship["object"] != expected_crop_candidate_endpoint:
                raise SeedPipelineError(
                    f"Crop relationship object identity does not match source occurrence: {relationship_id}"
                )
        if object_domain == "ufo":
            ufo_identity = (
                object_id,
                normalize_space(relationship["object"].get("native_event_id")),
            )
            if (
                relationship["object"].get("dataset") != "MYTbrain/ufo-timeline"
                or ufo_identity not in authoritative_ufo_endpoints
            ):
                raise SeedPipelineError(
                    f"UFO relationship object does not resolve against authoritative lineage: {relationship_id}"
                )
        if not relationship.get("source_refs"):
            raise SeedPipelineError(f"Relationship lacks source evidence: {relationship_id}")
        for source_ref in relationship.get("source_refs", []):
            source_identity = _evidence_identity_tuple(source_ref)
            source_id, source_hash, locator = source_identity
            if not re.fullmatch(r"[a-f0-9]{64}", source_hash):
                raise SeedPipelineError(
                    f"Relationship supporting source lacks a SHA-256 hash: {relationship_id}:{source_id}"
                )
            if (
                source_identity not in authoritative_source_evidence
                and source_identity not in crop_event_source_evidence
            ):
                raise SeedPipelineError(
                    "Relationship supporting source hash/locator does not match authoritative provenance: "
                    f"{relationship_id}:{source_id}:{locator}"
                )

    relationships_by_id = {row["relationship_id"]: row for row in relationships}
    for row in [*candidates, *incidents]:
        if not row.get("sources"):
            raise SeedPipelineError(f"Case record lacks sources: {row.get('record_id')}")
        if row.get("event_domain") != "animal_mutilation":
            raise SeedPipelineError(
                f"Case record has the wrong event domain: {row.get('record_id')}"
            )
        if row.get("negative_only") is True and row.get("explicit_negative") is not True:
            raise SeedPipelineError(
                f"Case negative-only invariant failed: {row.get('record_id')}"
            )
        source_ids = {
            normalize_space(source.get("source_id"))
            for source in row.get("sources", [])
            if normalize_space(source.get("source_id"))
        }
        if row.get("record_type") == "mutilation_case" and not row.get("animals"):
            raise SeedPipelineError(
                f"Mutilation case lacks a source-local victim assertion: {row.get('record_id')}"
            )
        for field, permitted_roles in (
            ("animals", {"reported_victim", "possible_victim"}),
            (
                "animal_context",
                {
                    "predator_or_scavenger",
                    "witness_companion",
                    "nearby_unaffected",
                    "context_only",
                },
            ),
        ):
            for animal in row.get(field, []):
                animal_source_ids = {
                    normalize_space(value)
                    for value in animal.get("source_ids", [])
                    if normalize_space(value)
                }
                if not animal_source_ids or not animal_source_ids <= source_ids:
                    raise SeedPipelineError(
                        f"Animal assertion source does not resolve: {row.get('record_id')}"
                    )
                if animal.get("incident_role") not in permitted_roles:
                    raise SeedPipelineError(
                        f"Animal assertion is in the wrong role lane: {row.get('record_id')}"
                    )
        public_evidence_values = [row.get("title"), row.get("summary")]
        public_evidence_values.extend(
            source.get(field)
            for source in row.get("sources", [])
            for field in ("title", "agency_or_publisher")
            if isinstance(source, Mapping)
        )
        public_evidence_values.extend(
            animal.get("evidence_excerpt")
            for field in ("animals", "animal_context")
            for animal in row.get(field, [])
        )
        public_evidence_values.extend(
            row.get("extraction", {}).get("incident_evidence_sentences", [])
        )
        for value in public_evidence_values:
            if contains_public_private_locator(value):
                raise SeedPipelineError(
                    f"Public evidence excerpt contains a private locator: {row.get('record_id')}"
                )
        _validate_case_decision(row, decisions_by_id[row["record_id"]])
        if row.get("location", {}).get("privacy_level") == "internal_only" and (
            row["location"].get("latitude_public") is not None
            or row["location"].get("longitude_public") is not None
        ):
            raise SeedPipelineError(f"Private public-coordinate suppression failed: {row['record_id']}")
        for external_ref in row.get("external_event_refs", []):
            if external_ref.get("domain") == "ufo" and (
                normalize_space(external_ref.get("external_id")),
                normalize_space(external_ref.get("native_event_id")),
            ) not in authoritative_ufo_endpoints:
                raise SeedPipelineError(
                    f"External UFO event reference lacks authoritative lineage: {row['record_id']}"
                )
            relationship_id = normalize_space(external_ref.get("relationship_id"))
            if relationship_id not in relationship_ids:
                raise SeedPipelineError(
                    f"External event reference has a dangling relationship: {row['record_id']}"
                )
            relationship = relationships_by_id[relationship_id]
            object_ref = relationship["object"]
            if (
                external_ref.get("domain") != object_ref.get("domain")
                or external_ref.get("dataset") != object_ref.get("dataset")
                or str(external_ref.get("external_id")) != str(object_ref.get("external_id"))
            ):
                raise SeedPipelineError(
                    f"External event reference does not match relationship object: {row['record_id']}"
                )
    for row in crop_candidates:
        if row.get("trace_eligible") is not False or row.get("trace_role") != "context_only":
            raise SeedPipelineError(f"Crop trace invariant failed: {row.get('crop_source_candidate_id')}")
        public_evidence_values = [row.get("evidence_excerpt")]
        public_evidence_values.extend(
            row.get("incident_evidence_sentences", [])
        )
        public_evidence_values.extend(
            animal.get("evidence_excerpt")
            for field in ("animal_assertions", "context_animal_assertions")
            for animal in row.get(field, [])
            if isinstance(animal, Mapping)
        )
        public_evidence_values.extend(
            row.get("location", {}).get(field)
            for field in (
                "raw_text",
                "place",
                "locality",
                "county",
                "region",
                "admin2",
                "admin1",
            )
        )
        for value in public_evidence_values:
            if contains_public_private_locator(value):
                raise SeedPipelineError(
                    "Crop source candidate public evidence contains a private locator: "
                    f"{row.get('crop_source_candidate_id')}"
                )

    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:
        raise SeedPipelineError("jsonschema is required for output schema validation") from exc
    case_validator = Draft202012Validator(
        json.loads((REPO_ROOT / "docs" / "cattle_mutilation" / "case.schema.json").read_text(encoding="utf-8"))
    )
    relationship_validator = Draft202012Validator(
        json.loads(
            (REPO_ROOT / "docs" / "cattle_mutilation" / "cross_domain_relationship.schema.json").read_text(
                encoding="utf-8"
            )
        )
    )
    for row in [*candidates, *incidents]:
        errors = sorted(case_validator.iter_errors(row), key=lambda error: list(error.path))
        if errors:
            raise SeedPipelineError(
                f"Case schema validation failed for {row.get('record_id')}: {errors[0].message}"
            )
    for row in relationships:
        errors = sorted(
            relationship_validator.iter_errors(row), key=lambda error: list(error.path)
        )
        if errors:
            raise SeedPipelineError(
                f"Relationship schema validation failed for {row.get('relationship_id')}: {errors[0].message}"
            )

    return {
        "status": "passed",
        "output_dir": str(output_dir),
        "artifacts_verified": len(OUTPUT_NAMES),
        "counts_verified": actual_counts,
        "relationship_endpoints_verified": len(relationships),
        "authoritative_ufo_endpoints_verified": len(authoritative_ufo_endpoints),
        "authoritative_source_identities_verified": len(authoritative_source_evidence),
        "case_decisions_verified": len(decisions_by_id),
        "privacy_invariants_verified": len(candidates) + len(incidents),
        "crop_dispositions_verified": len(crop_audit),
        "case_schema_rows_verified": len(candidates) + len(incidents),
        "relationship_schema_rows_verified": len(relationships),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    acquire = subparsers.add_parser("acquire", help="Discover or privately cache every crop source page.")
    acquire.add_argument("--crop-zip", default=str(DEFAULT_CROP_ZIP))
    acquire.add_argument("--audit-output", default=str(DEFAULT_PRIVATE_CACHE / "source_access_audit.csv"))
    acquire.add_argument("--private-cache-dir", default=str(DEFAULT_PRIVATE_CACHE))
    acquire.add_argument("--network", action="store_true", help="Explicitly enable live network requests.")
    acquire.add_argument("--archive-fallback", action="store_true", help="Explicitly enable Wayback after live failure.")
    acquire.add_argument("--rate-limit-seconds", type=float, default=0.5)
    acquire.add_argument("--timeout-seconds", type=float, default=20.0)
    acquire.add_argument(
        "--retry-failures",
        action="store_true",
        help="Retry prior completed failures; by default they are reused for resumability.",
    )
    acquire.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Maximum concurrent source targets; request starts remain globally rate-limited.",
    )
    acquire.add_argument("--progress-every", type=int, default=100)

    extract = subparsers.add_parser("extract", help="Build all deterministic Phase 1 outputs.")
    extract.add_argument("--starter-pack", default=str(DEFAULT_STARTER_PACK))
    extract.add_argument("--crop-zip", default=str(DEFAULT_CROP_ZIP))
    extract.add_argument("--catalog-pdf", default=str(DEFAULT_CATALOG_PDF))
    extract.add_argument("--source-records", default=str(DEFAULT_SOURCE_RECORDS))
    extract.add_argument("--deduped-events", default=str(DEFAULT_DEDUPED_EVENTS))
    extract.add_argument("--acquisition-audit", default=str(DEFAULT_PRIVATE_CACHE / "source_access_audit.csv"))
    extract.add_argument("--private-cache-dir", default=str(DEFAULT_PRIVATE_CACHE))
    extract.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    extract.add_argument("--resume", action="store_true")
    extract.add_argument("--allow-partial", action="store_true", help="Fixture/test mode only; disables pinned corpus counts.")
    extract.add_argument("--limit", type=int, default=None, help="Fixture/test mode source-row limit.")

    validate = subparsers.add_parser("validate", help="Validate output integrity and scientific invariants.")
    validate.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    validate.add_argument("--crop-zip", default=str(DEFAULT_CROP_ZIP))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "acquire":
            if args.archive_fallback and not args.network:
                raise SeedPipelineError("--archive-fallback requires --network")
            result = acquire_crop_sources(
                args.crop_zip,
                args.audit_output,
                args.private_cache_dir,
                network=args.network,
                archive_fallback=args.archive_fallback,
                rate_limit_seconds=args.rate_limit_seconds,
                timeout_seconds=args.timeout_seconds,
                retry_failures=args.retry_failures,
                workers=args.workers,
                progress_every=args.progress_every,
                progress_fn=lambda done, total, target, status: print(
                    f"crop-source acquisition {done:,}/{total:,}: {status} ({target.url})",
                    file=sys.stderr,
                    flush=True,
                ),
            )
        elif args.command == "extract":
            result = run_extract(args)
        else:
            result = validate_outputs(Path(args.output_dir), crop_zip_path=Path(args.crop_zip))
    except (SeedPipelineError, CropSourceAcquisitionError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    display_result = result
    if args.command == "extract" and isinstance(result, Mapping):
        manifest = result.get("manifest")
        if isinstance(manifest, Mapping):
            output_path = Path(str(result.get("output_dir", args.output_dir)))
            display_result = {
                "output_dir": str(output_path),
                "manifest_path": str(output_path / "run_manifest.json"),
                "pipeline_version": manifest.get("pipeline_version"),
                "counts": manifest.get("counts", {}),
                "validation": result.get("validation", {}),
            }
    # Escaping non-ASCII keeps CLI completion reliable on legacy Windows
    # consoles without changing any UTF-8 artifact written by the pipeline.
    print(json.dumps(display_result, ensure_ascii=True, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
