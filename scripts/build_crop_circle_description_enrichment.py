"""Build a rights-bounded crop-circle source-description enrichment.

The Crop Circle Timeline interoperability export currently contains generated
catalog summaries, not source narratives. This one-time enrichment reads the
event-specific ICCRA pages already cited by that export and retains only a
short, source-attributed excerpt plus structured crop and credit fields. Raw
HTML and full article text are deliberately not packaged.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import threading
import time
from typing import Any
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen


SCHEMA_VERSION = 1
PARSER_VERSION = "iccra-primary-report-v2"
DEFAULT_MAX_SOURCE_WORDS = 25
ALLOWED_HOSTS = {"iccra.org", "www.iccra.org"}
USER_AGENT = "ufo-timeline-description-enrichment/1.0"
PROGRESS_LOCK = threading.Lock()
YEAR_RE = re.compile(r"(?<!\d)((?:18|19|20)\d{2})(?!\d)")
URL_RE = re.compile(r"(?:https?://|www\.)\S+", flags=re.IGNORECASE)
HTML_TAG_RE = re.compile(r"<[^>]+>")
METADATA_LABEL_RE = re.compile(
    r"\b(?P<label>source\s+and\s+photos?|crop\s*type|sources?|photos?|photographs?|pictured|diagrams?)\s*:",
    flags=re.IGNORECASE,
)
FOOTER_RE = re.compile(
    r"\b(?:city\s*/?\s*county\s*/?\s*date|page\s+last\s+updated|copyright)\b|©",
    flags=re.IGNORECASE,
)
UNKNOWN_CROPS = {"", "?", "unknown", "unkown", "not known", "n/a", "na", "none"}
SAFE_CREDIT_MAX_WORDS = 12
SAFE_CREDIT_MAX_CHARS = 120


class SourceDateMismatchError(ValueError):
    """An event page explicitly names a different year than its assertion."""

    def __init__(self, message: str, evidence: dict[str, Any]) -> None:
        super().__init__(message)
        self.evidence = evidence


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--max-source-words", type=int, default=DEFAULT_MAX_SOURCE_WORDS)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--offline", action="store_true", help="Require every source page to exist in --cache")
    return parser.parse_args()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    """Return a displayable crop value while retaining the raw value separately."""
    cleaned = normalized_text(str(value or "")).strip(" .;,:")
    folded = cleaned.casefold()
    if folded in UNKNOWN_CROPS or folded.startswith("no crop type"):
        return None
    return folded or None


def safe_credit_display(value: str | None) -> str | None:
    """Only short, plain source attributions are eligible for direct UI display."""
    cleaned = normalized_text(str(value or ""))
    if not cleaned or len(cleaned) > SAFE_CREDIT_MAX_CHARS:
        return None
    if len(cleaned.split()) > SAFE_CREDIT_MAX_WORDS:
        return None
    if URL_RE.search(cleaned) or HTML_TAG_RE.search(cleaned) or text_has_control_characters(cleaned):
        return None
    if re.search(r"\b(?:photos?|photographs?|pictured|diagrams?)\s*:", cleaned, flags=re.IGNORECASE):
        return None
    if cleaned.casefold().strip(" .") in {"see report", "unknown", "none"}:
        return None
    return cleaned


def unique_year(value: str | None) -> int | None:
    years = {int(match) for match in YEAR_RE.findall(str(value or ""))}
    return next(iter(years)) if len(years) == 1 else None


def assertion_year(value: str | None) -> int | None:
    match = re.match(r"^((?:18|19|20)\d{2})(?:-|$)", str(value or ""))
    return int(match.group(1)) if match else None


def source_url_year(value: str | None) -> int | None:
    return unique_year(unquote(str(value or "")))


def strip_report_heading(value: str) -> str:
    """Remove only the bounded ICCRA report title, retaining same-node narrative."""
    cleaned = normalized_text(value)
    if not cleaned.casefold().startswith("reported crop circles"):
        return cleaned
    dated_heading = re.match(
        r"^Reported Crop Circles.{0,320}?\([^)]*(?:18|19|20)\d{2}[^)]*\)\s*(.*)$",
        cleaned,
        flags=re.IGNORECASE,
    )
    if dated_heading:
        return normalized_text(dated_heading.group(1))
    if " - " in cleaned:
        remainder = normalized_text(cleaned.split(" - ", 1)[1])
        if len(remainder.split()) <= 5 and not re.search(r"[.!?]$", remainder):
            return ""
        return remainder
    return ""


def split_metadata(value: str) -> tuple[str, dict[str, list[str]]]:
    """Split narrative from inline ICCRA crop/source/media footer fields."""
    cleaned = normalized_text(value)
    footer = FOOTER_RE.search(cleaned)
    if footer:
        cleaned = cleaned[:footer.start()].rstrip(" ,;:-")
    matches = list(METADATA_LABEL_RE.finditer(cleaned))
    if not matches:
        return cleaned, {}
    narrative = normalized_text(cleaned[:matches[0].start()])
    fields: dict[str, list[str]] = {}
    for index, match in enumerate(matches):
        label = re.sub(r"\s+", " ", match.group("label").casefold())
        if label == "crop type":
            key = "crop"
        elif label.startswith("source and"):
            key = "source_media"
        elif label.startswith("source"):
            key = "source"
        else:
            key = "media"
        end = matches[index + 1].start() if index + 1 < len(matches) else len(cleaned)
        metadata_value = normalized_text(cleaned[match.end():end]).strip(" ,;:-")
        if metadata_value:
            fields.setdefault(key, []).append(metadata_value)
    return narrative, fields


def is_preamble(value: str) -> bool:
    cleaned = normalized_text(value)
    if not cleaned:
        return True
    if re.fullmatch(r"[\w .,'’-]{2,80}\s+-\s+\d{1,2}/\d{1,2}/\d{2,4}", cleaned):
        return True
    if re.fullmatch(r"(?:updated\s+)?(?:[A-Z][a-z]{2,9}\.?\s+)?\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}", cleaned):
        return True
    if cleaned.casefold().startswith(("by ", "submitted by ", "reported by ")) and len(cleaned.split()) <= 12:
        return True
    return False


def is_media_preamble(value: str) -> bool:
    cleaned = normalized_text(value).casefold()
    return cleaned.endswith((" photo:", " photos:", " photograph:", " photographs:", " diagram:"))


def bounded_excerpt_words(words: list[str], max_words: int) -> list[str]:
    if len(words) <= max_words:
        return words
    bounded = words[:max_words]
    # Avoid appending a fragment of a later sentence when at least one useful,
    # complete sentence already fits inside the rights-bounded word limit.
    for index in range(len(bounded) - 1, 4, -1):
        if re.search(r"[.!?][\"'’”)]*$", bounded[index]):
            return bounded[:index + 1]
    return bounded


def strip_leading_case_label(value: str, labels: tuple[str, ...]) -> str:
    """Remove ICCRA's place/county heading when it shares a narrative paragraph."""
    cleaned = value
    for label in sorted((normalized_text(item) for item in labels if item), key=len, reverse=True):
        if not cleaned.casefold().startswith(label.casefold()):
            continue
        remainder = cleaned[len(label):].lstrip(" ,;:-")
        if remainder.startswith("(") and ")" in remainder:
            remainder = remainder.split(")", 1)[1].lstrip(" ,;:-")
        cleaned = remainder
        break
    # A few legacy assertion rows have malformed place fields even though the
    # page heading itself is regular: "Place, County (Month, YYYY) Narrative".
    # Remove only that tightly bounded heading shape, never a normal sentence.
    heading_match = re.match(r"^.{1,160}?,.{1,100}?\([^)]*\b\d{4}\b[^)]*\)\s+(.+)$", cleaned)
    if heading_match:
        cleaned = heading_match.group(1)
    return normalized_text(cleaned)


def safe_iccra_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError(f"Refusing non-ICCRA source URL: {value}")
    return value


def cache_path(cache_root: Path, url: str) -> Path:
    return cache_root / f"{hashlib.sha256(url.encode('utf-8')).hexdigest()}.html"


def decode_source_html(payload: bytes) -> str:
    head = payload[:2048].lower()
    charset_match = re.search(rb"charset\s*=\s*['\"]?([a-z0-9._-]+)", head)
    encodings = []
    if charset_match:
        declared = charset_match.group(1).decode("ascii", "ignore").lower()
        # Web browsers interpret ISO-8859-1 labels as Windows-1252. ICCRA's
        # older pages use that label while containing Windows smart quotes;
        # decoding them as strict Latin-1 would leak C1 control characters.
        if declared in {"iso-8859-1", "iso8859-1", "latin-1", "latin1"}:
            declared = "windows-1252"
        encodings.append(declared)
    encodings.extend(["windows-1252", "utf-8", "latin-1"])
    for encoding in dict.fromkeys(encodings):
        try:
            return payload.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return payload.decode("utf-8", "replace")


@dataclass
class _CellCapture:
    active: bool = False
    td_depth: int = 0
    paragraph_depth: int = 0
    paragraph_buffer: list[str] = field(default_factory=list)
    paragraphs: list[str] = field(default_factory=list)
    cell_text: list[str] = field(default_factory=list)


class IccraReportParser(HTMLParser):
    """Extract paragraph text from ICCRA's primary report column."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.capture = _CellCapture()
        self._capture_stack: list[tuple[bool, int]] = []
        self._all_paragraph_depth = 0
        self._all_paragraph_buffer: list[str] = []
        self.all_paragraphs: list[str] = []

    @staticmethod
    def _is_primary_cell(attributes: dict[str, str | None]) -> bool:
        if str(attributes.get("valign") or "").lower() != "top":
            return False
        width = str(attributes.get("width") or "").strip().lower()
        match = re.search(r"\d+(?:\.\d+)?", width)
        return bool(match and float(match.group(0)) >= 400)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "td":
            self._capture_stack.append((self.capture.active, self.capture.td_depth))
            if self.capture.active:
                self.capture.td_depth += 1
            elif self._is_primary_cell(attributes):
                self.capture.active = True
                self.capture.td_depth = 1
                self.capture.cell_text = []
        if tag == "p":
            self._all_paragraph_depth += 1
            if self._all_paragraph_depth == 1:
                self._all_paragraph_buffer = []
            if self.capture.active:
                self.capture.paragraph_depth += 1
                if self.capture.paragraph_depth == 1:
                    self.capture.paragraph_buffer = []
        elif tag == "br":
            if self._all_paragraph_depth:
                self._all_paragraph_buffer.append(" ")
            if self.capture.active and self.capture.paragraph_depth:
                self.capture.paragraph_buffer.append(" ")
        if self.capture.active and tag in {"br", "div", "h1", "h2", "h3", "li", "p", "tr"}:
            self.capture.cell_text.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag == "p":
            if self._all_paragraph_depth:
                if self._all_paragraph_depth == 1:
                    value = normalized_text("".join(self._all_paragraph_buffer))
                    if value:
                        self.all_paragraphs.append(value)
                self._all_paragraph_depth -= 1
            if self.capture.active and self.capture.paragraph_depth:
                if self.capture.paragraph_depth == 1:
                    value = normalized_text("".join(self.capture.paragraph_buffer))
                    if value:
                        self.capture.paragraphs.append(value)
                self.capture.paragraph_depth -= 1
        elif tag == "td" and self._capture_stack:
            was_active, previous_depth = self._capture_stack.pop()
            self.capture.active = was_active
            self.capture.td_depth = previous_depth
        elif self.capture.active and tag in {"br", "div", "h1", "h2", "h3", "li", "p", "tr"}:
            self.capture.cell_text.append(" ")

    def handle_data(self, data: str) -> None:
        if self._all_paragraph_depth:
            self._all_paragraph_buffer.append(data)
        if self.capture.active and self.capture.paragraph_depth:
            self.capture.paragraph_buffer.append(data)
        if self.capture.active:
            self.capture.cell_text.append(data)


def extract_page_heading(parser: IccraReportParser) -> str | None:
    paragraph_candidates = parser.capture.paragraphs or parser.all_paragraphs
    heading_candidate = next(
        (
            normalized_text(value)
            for value in paragraph_candidates
            if normalized_text(value).casefold().startswith("reported crop circles")
        ),
        None,
    )
    cell_text = normalized_text("".join(parser.capture.cell_text))
    candidates = [value for value in (heading_candidate, cell_text) if value]
    for candidate in candidates:
        dated_heading = re.match(
            r"^(Reported Crop Circles.{0,320}?\([^)]*(?:18|19|20)\d{2}[^)]*\))",
            candidate,
            flags=re.IGNORECASE,
        )
        if dated_heading:
            return normalized_text(dated_heading.group(1))
    if heading_candidate:
        if " - " in heading_candidate:
            return normalized_text(heading_candidate.split(" - ", 1)[0] + " -")
        return heading_candidate
    return None


def parse_report(
    payload: bytes,
    *,
    max_source_words: int,
    leading_case_labels: tuple[str, ...] = (),
) -> dict[str, Any]:
    parser = IccraReportParser()
    parser.feed(decode_source_html(payload))
    primary_cell_text = normalized_text("".join(parser.capture.cell_text))
    paragraphs = parser.capture.paragraphs if primary_cell_text else parser.all_paragraphs
    candidates = [strip_report_heading(value) for value in paragraphs]
    # A handful of legacy pages begin with a report notice, then a raw URL and
    # byline before the actual narrative. Do not mistake that navigation-like
    # preamble for the formation description.
    early_url_index = next(
        (index for index, value in enumerate(candidates[:5]) if URL_RE.search(value)),
        None,
    )
    if early_url_index is not None:
        candidates = candidates[early_url_index + 1:]
    narrative: list[str] = []
    metadata: dict[str, list[str]] = {}
    for paragraph in candidates:
        value = normalized_text(paragraph)
        lower = value.casefold()
        if (
            lower.startswith("reported crop circles")
            or lower.startswith("city / county / date")
            or lower.startswith("city/county/date")
            or lower.startswith("page last updated")
            or lower.startswith("©")
            or lower.startswith("copyright")
        ):
            break
        if lower in {"about iccra", "usa formations", "reports", "home"}:
            continue
        if not narrative and is_media_preamble(value):
            # A caption lead-in such as "...in a caption with three photos:"
            # is context for omitted images, not the formation description.
            continue
        value, paragraph_metadata = split_metadata(value)
        for key, values in paragraph_metadata.items():
            metadata.setdefault(key, []).extend(values)
        value = normalized_text(URL_RE.sub("", value)).strip(" ,;:-")
        if not narrative:
            value = strip_leading_case_label(value, leading_case_labels)
            if is_preamble(value) or is_media_preamble(value):
                continue
        if value:
            narrative.append(value)

    # Primary-cell text is used for metadata on every page, and as a tightly
    # bounded narrative fallback only when paragraph markup contains no body.
    cell_body = strip_report_heading(primary_cell_text)
    cell_narrative, cell_metadata = split_metadata(cell_body)
    for key, values in cell_metadata.items():
        if not metadata.get(key):
            metadata[key] = values
    if not narrative and primary_cell_text.casefold().startswith("reported crop circles"):
        fallback = normalized_text(URL_RE.sub("", cell_narrative)).strip(" ,;:-")
        fallback = strip_leading_case_label(fallback, leading_case_labels)
        if not is_preamble(fallback) and not is_media_preamble(fallback) and len(fallback.split()) >= 3:
            narrative.append(fallback)

    crop_raw = next(iter(metadata.get("crop", [])), None)
    source_values = metadata.get("source", [])
    source_media_values = metadata.get("source_media", [])
    source_credit_raw = next(iter(source_values), None)
    bounded_media_attribution = [
        value
        for value in [*source_media_values, *metadata.get("media", [])]
        if len(value) <= 240 and len(value.split()) <= 30 and not URL_RE.search(value)
    ]
    source_attribution_raw = [*source_values, *bounded_media_attribution]
    source_credit_display = safe_credit_display(source_credit_raw)

    full_narrative = normalized_text(" ".join(narrative))
    words = full_narrative.split()
    excerpt_words = bounded_excerpt_words(words, max_source_words)
    return {
        "sourceExcerpt": " ".join(excerpt_words) or None,
        "sourceExcerptWordCount": len(excerpt_words),
        "sourceExcerptTruncated": len(words) > len(excerpt_words),
        "crop": normalized_crop(crop_raw),
        "cropRaw": crop_raw,
        "sourceCredit": source_credit_display,
        "sourceCreditDisplay": source_credit_display,
        "sourceCreditRaw": source_credit_raw,
        "sourceAttributionRaw": source_attribution_raw,
        "sourceAttributionAvailable": bool(
            source_values or source_media_values or metadata.get("media", [])
        ),
        "sourceNarrativeDetected": bool(words),
        "sourceNarrativeWordCount": len(words),
        "pageHeading": extract_page_heading(parser),
    }


def fetch_source(
    url: str,
    *,
    cache_root: Path | None,
    refresh: bool,
    offline: bool,
    timeout: float,
) -> tuple[bytes, str]:
    url = safe_iccra_url(url)
    cached = cache_path(cache_root, url) if cache_root else None
    if cached and cached.is_file() and not refresh:
        return cached.read_bytes(), "cache"
    if offline:
        raise FileNotFoundError(f"Source page not present in cache: {url}")
    request = Request(url, headers={"User-Agent": USER_AGENT})
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = response.read()
            if cached:
                cached.parent.mkdir(parents=True, exist_ok=True)
                cached.write_bytes(payload)
            return payload, "network"
        except Exception as exc:  # noqa: BLE001 - final error is recorded in the enrichment report
            last_error = exc
            if attempt < 3:
                time.sleep(attempt)
    raise RuntimeError(f"Source request failed after 3 attempts: {last_error}")


def enrich_assertion(
    assertion: dict[str, Any],
    *,
    cache_root: Path | None,
    refresh: bool,
    offline: bool,
    timeout: float,
    max_source_words: int,
) -> dict[str, Any]:
    url = safe_iccra_url(str(assertion.get("source_record_url") or ""))
    payload, retrieval = fetch_source(
        url,
        cache_root=cache_root,
        refresh=refresh,
        offline=offline,
        timeout=timeout,
    )
    place = normalized_text(str(assertion.get("place") or ""))
    county = normalized_text(str(assertion.get("county") or ""))
    parsed = parse_report(
        payload,
        max_source_words=max_source_words,
        leading_case_labels=tuple(filter(None, (f"{place}, {county}" if place and county else "", place))),
    )
    assertion_date_year = assertion_year(assertion.get("date_iso"))
    record_url_year = source_url_year(url)
    heading_year = unique_year(parsed.get("pageHeading"))
    explicit_years = {
        "assertionYear": assertion_date_year,
        "sourceRecordUrlYear": record_url_year,
        "pageHeadingYear": heading_year,
    }
    comparable_years = {year for year in explicit_years.values() if year is not None}
    if len(comparable_years) > 1:
        raise SourceDateMismatchError(
            "Assertion date, source-record URL, and page heading do not identify the same year",
            explicit_years,
        )
    date_validation_status = (
        "matched_all"
        if all(year is not None for year in explicit_years.values())
        else "matched_available_years"
    )
    return {
        "formationId": str(assertion.get("formation_id") or ""),
        "assertionId": str(assertion.get("assertion_id") or ""),
        "sourceName": str(assertion.get("source_name") or "ICCRA"),
        "sourceRecordUrl": url,
        "sourceCollectionUrl": assertion.get("source_url"),
        "sourceDate": assertion.get("date_iso"),
        "sourceDatePrecision": assertion.get("date_precision"),
        "dateRole": "catalog_unspecified",
        "displayPolicy": "short_source_excerpt",
        "parserVersion": PARSER_VERSION,
        "pageSha256": sha256_bytes(payload),
        "retrieval": retrieval,
        "dateValidation": {"status": date_validation_status, **explicit_years},
        **parsed,
    }


def primary_record(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        raise ValueError("Cannot select a primary description from an empty record list")
    return max(
        records,
        key=lambda record: (
            bool(record.get("sourceExcerpt")),
            int(record.get("sourceNarrativeWordCount") or 0),
            str(record.get("assertionId") or ""),
        ),
    )


def main() -> None:
    args = parse_args()
    if args.max_source_words < 1 or args.max_source_words > DEFAULT_MAX_SOURCE_WORDS:
        raise ValueError(f"--max-source-words must be between 1 and {DEFAULT_MAX_SOURCE_WORDS}")
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "crop-circle-timeline-export-v1.0.0":
        raise ValueError("Unsupported crop-circle export schema")
    all_iccra_assertions = [
        assertion
        for assertion in payload.get("source_assertions", [])
        if assertion.get("source_name") == "ICCRA" and assertion.get("source_record_url")
    ]
    assertions = [
        assertion
        for assertion in all_iccra_assertions
        if assertion.get("source_record_url") != assertion.get("source_url")
    ]
    assertions.sort(key=lambda item: (str(item.get("formation_id")), str(item.get("assertion_id"))))

    records_by_formation: dict[str, list[dict[str, Any]]] = {}
    failures: list[dict[str, Any]] = []
    workers = max(1, min(8, int(args.workers)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                enrich_assertion,
                assertion,
                cache_root=args.cache,
                refresh=bool(args.refresh),
                offline=bool(args.offline),
                timeout=float(args.timeout),
                max_source_words=int(args.max_source_words),
            ): assertion
            for assertion in assertions
        }
        for index, future in enumerate(as_completed(futures), start=1):
            assertion = futures[future]
            try:
                record = future.result()
                formation_id = record["formationId"]
                records_by_formation.setdefault(formation_id, []).append(record)
            except Exception as exc:  # noqa: BLE001 - failures remain visible and machine-readable
                failure: dict[str, Any] = {
                    "formationId": str(assertion.get("formation_id") or ""),
                    "assertionId": str(assertion.get("assertion_id") or ""),
                    "url": str(assertion.get("source_record_url") or ""),
                    "errorCode": (
                        "source_record_date_mismatch"
                        if isinstance(exc, SourceDateMismatchError)
                        else "source_fetch_or_parse_failed"
                    ),
                    "error": str(exc),
                }
                if isinstance(exc, SourceDateMismatchError):
                    failure["dateValidation"] = exc.evidence
                failures.append(failure)
            if index % 25 == 0 or index == len(futures):
                with PROGRESS_LOCK:
                    print(f"ICCRA description pages processed: {index}/{len(futures)}", flush=True)

    ordered_records: dict[str, dict[str, Any]] = {}
    for formation_id in sorted(records_by_formation):
        descriptions = sorted(
            records_by_formation[formation_id],
            key=lambda record: str(record.get("assertionId") or ""),
        )
        primary = primary_record(descriptions)
        ordered_records[formation_id] = {
            **primary,
            "primaryAssertionId": primary.get("assertionId"),
            "sourceDescriptions": descriptions,
        }
    description_assertions = [
        description
        for record in ordered_records.values()
        for description in record.get("sourceDescriptions", [])
    ]
    output = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "sourceExportSha256": sha256_file(args.input),
        "sourceExportSchema": payload.get("schema_version"),
        "sourceCommit": (payload.get("source") or {}).get("source_commit"),
        "policy": {
            "maxSourceWords": int(args.max_source_words),
            "rawHtmlPackaged": False,
            "fullArticleTextPackaged": False,
            "displayPolicy": "short_source_excerpt",
            "dateRole": "catalog_unspecified",
        },
        "counts": {
            "candidateAssertions": len(assertions),
            "indexOnlyAssertionsSkipped": len(all_iccra_assertions) - len(assertions),
            "records": len(ordered_records),
            "withSourceExcerpt": sum(bool(record.get("sourceExcerpt")) for record in ordered_records.values()),
            "withCrop": sum(bool(record.get("crop")) for record in ordered_records.values()),
            "withSourceCredit": sum(bool(record.get("sourceCreditDisplay")) for record in ordered_records.values()),
            "withSourceAttribution": sum(
                bool(record.get("sourceAttributionAvailable")) for record in ordered_records.values()
            ),
            "descriptionAssertions": len(description_assertions),
            "sourceExcerptAssertions": sum(
                bool(record.get("sourceExcerpt")) for record in description_assertions
            ),
            "duplicateFormationRecords": sum(
                len(record.get("sourceDescriptions", [])) > 1 for record in ordered_records.values()
            ),
            "quarantinedDateMismatches": sum(
                failure.get("errorCode") == "source_record_date_mismatch" for failure in failures
            ),
            "failures": len(failures),
        },
        "records": ordered_records,
        "failures": sorted(failures, key=lambda item: (item["formationId"], item["assertionId"])),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), **output["counts"]}, indent=2))


if __name__ == "__main__":
    main()
