"""Read-only adapter for the pinned Crop Circle Center PDF catalog.

The adapter extracts deterministic page and formation-slot provenance without
copying images or returning complete page text.  The catalog is an index: an
absence of mutilation language in its extracted text is never evidence that a
crop-circle event has no mutilation association.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, Protocol

from pypdf import PdfReader


PINNED_COMBINED_PDF_SHA256 = "f51718f1eeb1c3f06f3a154d02eb7ab24dcefebB201e3ace04c6e8f79dcc65e7".lower()
CATALOG_ADAPTER_VERSION = "1.0.0"
ABSENCE_POLICY = "unknown_not_negative_evidence"
MAX_FACTUAL_TEXT_CHARS = 280

_YEAR_LINE = re.compile(r"^(?P<year>\d{3,4})(?P<remainder>.*)$")
_ADMIN_COUNTRY_LINE = re.compile(r"^(?P<admin>.*?)\s*\|\s*(?P<country>.*)$")
_SPACE = re.compile(r"\s+")
_MONTHS = {
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
}
_DATE_QUALIFIERS = {"early", "mid", "middle", "late", "beginning", "end"}
_INDEX_ANNOTATIONS = {"addition"}


class CatalogPdfError(RuntimeError):
    """Base error raised when the catalog cannot be adapted safely."""


class CatalogPdfIntegrityError(CatalogPdfError):
    """Raised when the source PDF does not match its pinned identity."""


class _PdfPage(Protocol):
    def extract_text(self) -> str | None: ...


class _PdfReader(Protocol):
    pages: list[_PdfPage]


def sha256_file(path: str | Path) -> str:
    """Return a lowercase SHA-256 digest without loading the PDF into memory."""

    source = Path(path)
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_catalog_pdf(
    path: str | Path,
    *,
    expected_sha256: str = PINNED_COMBINED_PDF_SHA256,
) -> str:
    """Fail closed unless *path* is the expected catalog PDF."""

    source = Path(path)
    if not source.is_file():
        raise CatalogPdfError(f"Catalog PDF does not exist or is not a file: {source}")
    expected = expected_sha256.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("expected_sha256 must be a 64-character hexadecimal SHA-256 digest")
    actual = sha256_file(source)
    if actual != expected:
        raise CatalogPdfIntegrityError(
            f"Catalog PDF SHA-256 mismatch for {source}: expected {expected}, got {actual}"
        )
    return actual


def normalize_page_text(text: str) -> str:
    """Normalize extracted text for stable hashing while preserving line order."""

    normalized = unicodedata.normalize("NFC", text).replace("\u200b", "")
    lines = [_SPACE.sub(" ", line).strip() for line in normalized.splitlines()]
    return "\n".join(line for line in lines if line)


def normalize_factual_text(text: str, *, limit: int = MAX_FACTUAL_TEXT_CHARS) -> str:
    """Return a whitespace-normalized, bounded factual extract."""

    normalized = _SPACE.sub(" ", unicodedata.normalize("NFC", text)).strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(0, limit - 3)].rstrip() + "..."


def iter_catalog_pages(
    path: str | Path,
    *,
    expected_sha256: str = PINNED_COMBINED_PDF_SHA256,
    reader_factory: Callable[[str], _PdfReader] = PdfReader,
) -> Iterator[dict[str, Any]]:
    """Yield catalog pages in PDF order with nested deterministic slot records.

    Full extracted page text is used only transiently.  Returned records contain
    hashes and bounded factual extracts, never the raw PDF or its images.
    """

    source = Path(path)
    pdf_sha256 = verify_catalog_pdf(source, expected_sha256=expected_sha256)
    try:
        reader = reader_factory(str(source))
    except Exception as exc:  # pragma: no cover - exercised through pypdf in integration
        raise CatalogPdfError(f"Could not open catalog PDF {source}: {exc}") from exc

    for page_index, page in enumerate(reader.pages):
        page_number = page_index + 1
        try:
            raw_text = page.extract_text() or ""
        except Exception as exc:
            raise CatalogPdfError(
                f"Could not extract text from catalog PDF page {page_number}: {exc}"
            ) from exc
        yield adapt_catalog_page(
            raw_text,
            pdf_sha256=pdf_sha256,
            page_number=page_number,
        )


def scan_catalog_pdf(
    path: str | Path,
    *,
    expected_sha256: str = PINNED_COMBINED_PDF_SHA256,
    reader_factory: Callable[[str], _PdfReader] = PdfReader,
) -> dict[str, Any]:
    """Return a deterministic, parent-CLI-friendly catalog scan."""

    page_records: list[dict[str, Any]] = []
    slot_records: list[dict[str, Any]] = []
    pdf_sha256: str | None = None

    for record in iter_catalog_pages(
        path,
        expected_sha256=expected_sha256,
        reader_factory=reader_factory,
    ):
        pdf_sha256 = record["provenance"]["pdf_sha256"]
        slots = record.pop("slots")
        slot_records.extend(slots)
        page_records.append(record)

    # A zero-page PDF is still identified even though the iterator yielded no page.
    if pdf_sha256 is None:
        pdf_sha256 = verify_catalog_pdf(path, expected_sha256=expected_sha256)

    coverage_counts = {"index_only": 0, "narrative_present": 0}
    for page in page_records:
        coverage_counts[page["narrative_coverage"]] += 1

    return {
        "schema_version": "crop-circle-catalog-adapter-v1.0.0",
        "adapter_version": CATALOG_ADAPTER_VERSION,
        "source": {
            "filename": Path(path).name,
            "sha256": pdf_sha256,
            "rights_handling": "hashes_and_short_factual_extracts_only",
            "images_redistributed": False,
            "raw_pdf_text_redistributed": False,
        },
        "absence_policy": ABSENCE_POLICY,
        "counts": {
            "pages": len(page_records),
            "slots": len(slot_records),
            "index_only_pages": coverage_counts["index_only"],
            "narrative_present_pages": coverage_counts["narrative_present"],
        },
        "pages": page_records,
        "slots": slot_records,
    }


def adapt_catalog_page(
    raw_text: str,
    *,
    pdf_sha256: str,
    page_number: int,
) -> dict[str, Any]:
    """Adapt one extracted page into provenance, coverage, and slot records."""

    normalized_page = normalize_page_text(raw_text)
    page_text_sha256 = _sha256_text(normalized_page)
    lines = normalized_page.splitlines() if normalized_page else []
    slots, consumed_indices = _extract_slots(
        lines,
        pdf_sha256=pdf_sha256,
        page_number=page_number,
    )
    narrative_lines = [
        line
        for index, line in enumerate(lines)
        if index not in consumed_indices and not _is_index_boilerplate(line)
    ]
    narrative_coverage = "narrative_present" if narrative_lines else "index_only"
    narrative_excerpt = (
        normalize_factual_text(" ".join(narrative_lines)) if narrative_lines else None
    )

    return {
        "provenance": {
            "pdf_sha256": pdf_sha256,
            "page_number": page_number,
            "source_locator": f"COMBINED.pdf#page={page_number}",
        },
        "text_sha256": page_text_sha256,
        "text_extraction_status": "text_extracted" if normalized_page else "empty",
        "narrative_coverage": narrative_coverage,
        "narrative_excerpt": narrative_excerpt,
        "absence_interpretation": ABSENCE_POLICY,
        "slots": slots,
    }


def _extract_slots(
    lines: list[str],
    *,
    pdf_sha256: str,
    page_number: int,
) -> tuple[list[dict[str, Any]], set[int]]:
    year_indices = [index for index, line in enumerate(lines) if _YEAR_LINE.match(line)]
    slots: list[dict[str, Any]] = []
    consumed_indices: set[int] = set()

    for year_position, start_index in enumerate(year_indices):
        stop_index = (
            year_indices[year_position + 1]
            if year_position + 1 < len(year_indices)
            else len(lines)
        )
        admin_index = next(
            (
                index
                for index in range(start_index + 1, stop_index)
                if _ADMIN_COUNTRY_LINE.match(lines[index])
            ),
            None,
        )
        if admin_index is None:
            continue

        date_text, first_location = _split_date_and_location(lines[start_index])
        intermediate = [
            line
            for line in lines[start_index + 1 : admin_index]
            if not _is_index_boilerplate(line)
        ]
        location_parts = ([first_location] if first_location else []) + intermediate
        location_text = normalize_factual_text(" ".join(location_parts))
        admin_match = _ADMIN_COUNTRY_LINE.match(lines[admin_index])
        assert admin_match is not None
        admin_region = normalize_factual_text(admin_match.group("admin"))
        country = normalize_factual_text(admin_match.group("country"))

        source_text = normalize_factual_text(
            " ".join(lines[start_index : admin_index + 1]),
            limit=10_000,
        )
        text_sha256 = _sha256_text(source_text)
        slot_number = len(slots) + 1
        factual_text = _format_slot_factual_text(
            date_text=date_text,
            location_text=location_text,
            admin_region=admin_region,
            country=country,
        )
        slots.append(
            {
                "slot_id": f"combined-p{page_number:04d}-s{slot_number:03d}-{text_sha256[:12]}",
                "provenance": {
                    "pdf_sha256": pdf_sha256,
                    "page_number": page_number,
                    "slot_number": slot_number,
                    "source_locator": (
                        f"COMBINED.pdf#page={page_number}&slot={slot_number}"
                    ),
                },
                "date_text": date_text,
                "location_text": location_text or None,
                "admin_region": admin_region or None,
                "country": country or None,
                "text_sha256": text_sha256,
                "factual_text": factual_text,
                "narrative_coverage": "index_only",
                "absence_interpretation": ABSENCE_POLICY,
            }
        )
        consumed_indices.update(range(start_index, admin_index + 1))

    return slots, consumed_indices


def _split_date_and_location(line: str) -> tuple[str, str]:
    match = _YEAR_LINE.match(line)
    if match is None:
        raise ValueError(f"Not a catalog year line: {line!r}")
    year = match.group("year")
    remainder = match.group("remainder").strip()
    if not remainder:
        return year, ""

    tokens = remainder.split()
    date_tokens = [year]
    if tokens and tokens[0].casefold() in _MONTHS:
        date_tokens.append(tokens.pop(0).casefold())
        while tokens and (
            tokens[0].isdigit() or tokens[0].casefold() in _DATE_QUALIFIERS
        ):
            date_tokens.append(tokens.pop(0).casefold())
    return " ".join(date_tokens), " ".join(tokens)


def _format_slot_factual_text(
    *,
    date_text: str,
    location_text: str,
    admin_region: str,
    country: str,
) -> str:
    place = ", ".join(part for part in (location_text, admin_region, country) if part)
    return normalize_factual_text(" - ".join(part for part in (date_text, place) if part))


def _is_index_boilerplate(line: str) -> bool:
    folded = normalize_factual_text(line).casefold()
    if not folded:
        return True
    if folded in _INDEX_ANNOTATIONS:
        return True
    if folded.startswith(("www.", "http://", "https://")):
        return True
    if "cropcirclecenter.com" in folded or "cropcircle-archive.com" in folded:
        return True
    if folded in {"no diagram", "more info needed"}:
        return True
    if folded.startswith("please help us to keep going"):
        return True
    return False


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
