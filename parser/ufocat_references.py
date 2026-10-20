"""Decode UFOCAT citation codes without changing report or evidence identities.

The four Phillips work titles are pinned to UFOCAT 2023 Sources.xlsx, rows
748-751. Direct TPhillips1 locators are catalog case numbers; indirect
locators mix case numbers and printed pages and must remain unverified.
"""
from __future__ import annotations

from collections.abc import Mapping
import math
import re
from typing import Any

CATALOG_URL = "https://cufos.org/PDFs/books/Physical_Traces.pdf"
CATALOG_PDF_SHA256 = "e824270528264c2563df17f79540171dc216fb9be85968a5eb844ecb1b2be17b"
# Original scan visually checked by independent reviewers; no OCR inference.
VERIFIED_CATALOG_PAGES = {253: (44, 62), 537: (86, 104), 585: (90, 108)}
FAMILY_ID = "ted_phillips_physical_trace_lineage"
WORKS = {
    "TPhillips": ("investigation_files", "Ted Phillips - investigation files"),
    "TPhillips1": ("physical_traces_1975", "Ted Phillips - Physical Traces Associated with UFO Sightings (CUFOS, 1975)"),
    "TPhillips2": ("trace_cases", "Ted Phillips - Trace Cases"),
    "TPhillips3": ("missouri_and_newspaper_reports", "Ted Phillips - Missouri Cases and other newspaper reports"),
}


def _text(value: Any) -> str:
    if isinstance(value, str):
        return " ".join(value.split())
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return ""
    return str(int(value)) if isinstance(value, float) and value.is_integer() else str(value)


def _ufocat_owner(value: Mapping[str, Any]) -> bool:
    # A merged event's list of source names does not establish raw-field ownership.
    names = [_text(value.get(key)).lower() for key in ("source_name", "source") if _text(value.get(key))]
    allowed = {"ufocat", "ufocat2023", "ufocat2023.csv"}
    if names:
        return all(name in allowed for name in names)
    filename = _text(value.get("source_file")).replace("\\", "/").rsplit("/", 1)[-1].lower()
    return filename == "ufocat2023.csv"


def _raw_rows(event: Mapping[str, Any]):
    canonical = event.get("extra_data", {})
    canonical = canonical.get("canonical", {}) if isinstance(canonical, Mapping) else {}
    if not isinstance(canonical, Mapping):
        canonical = {}
    if _ufocat_owner(event):
        for raw in (event.get("raw_fields"), canonical.get("raw_fields"), event.get("raw_source_row")):
            if isinstance(raw, Mapping):
                yield raw
    for owner in (event, canonical):
        for key in ("source_records", "source_provenance"):
            values = owner.get(key)
            if not isinstance(values, list):
                continue
            for member in values:
                if not isinstance(member, Mapping) or not _ufocat_owner(member):
                    continue
                for raw in (member.get("raw_fields"), member.get("raw_source_row")):
                    if isinstance(raw, Mapping):
                        yield raw


def reference_entries(event: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """Return existing references and source-owned UFOCAT citations as plain text."""
    if not isinstance(event, Mapping):
        return []
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    originals = event.get("references")
    if isinstance(originals, str):
        originals = [originals]
    if isinstance(originals, list):
        for original in originals:
            text = _text(original) if isinstance(original, str) else ""
            if text and text not in seen:
                entries.append({"text": text, "citationRole": "existing"})
                seen.add(text)
    for raw in _raw_rows(event):
        for role, code_field, locator_field in (("direct", "SOURCE", "PAGEVOL"), ("indirect", "ISOURCE", "IPAGEVOL")):
            code = _text(raw.get(code_field))
            if not code:
                continue
            locator = _text(raw.get(locator_field))
            work = WORKS.get(code)
            entry: dict[str, Any] = {"sourceCode": code, "citationRole": role,
                "locatorRaw": locator or None, "locatorType": "source_locator_unresolved",
                "catalogCaseNumber": None, "flags": []}
            title = f"UFOCAT source code {code}" if not work else f"{work[1]} [{code}]"
            suffix = f", locator {locator}" if locator else ""
            legacy_text = None
            if work:
                entry.update({"sourceWorkId": work[0], "familyId": FAMILY_ID})
            if code == "TPhillips1":
                entry["url"] = CATALOG_URL
                if role == "direct":
                    if re.fullmatch(r"[0-9]+", locator) and 1 <= int(locator) <= 831:
                        entry["catalogCaseNumber"] = int(locator)
                        entry["locatorType"] = "catalog_case_number"
                        suffix = f", case {locator}"
                        pages = VERIFIED_CATALOG_PAGES.get(entry["catalogCaseNumber"])
                        if pages:
                            legacy_text = f"{title}{suffix} ({role} citation)"
                            entry["catalogPrintedPage"], entry["catalogPdfPage"] = pages
                            entry["catalogPdfSha256"] = CATALOG_PDF_SHA256
                            entry["url"] = f"{CATALOG_URL}#page={entry['catalogPdfPage']}"
                            suffix += f", printed p. {entry['catalogPrintedPage']}, PDF page {entry['catalogPdfPage']}"
                    else:
                        entry["flags"].append("missing_or_invalid_catalog_case_number")
                        suffix = f", unverified locator {locator}" if locator else ", case number unavailable"
                else:
                    entry["locatorType"] = "ambiguous_catalog_case_number_or_printed_page"
                    suffix = f", locator {locator} (page or case number unverified)" if locator else ", locator unavailable"
            text = f"{title}{suffix} ({role} citation)"
            entry["text"] = text
            # Upgrade only this owned row's exact former helper string. Do not
            # relabel arbitrary existing references or citations without raw rows.
            if legacy_text and legacy_text != text:
                for i, existing in enumerate(entries):
                    if existing["text"] == legacy_text and existing["citationRole"] == "existing":
                        seen.discard(legacy_text)
                        if text in seen:
                            entries.pop(i)
                        else:
                            existing.update(entry)
                            seen.add(text)
                        break
            if text not in seen:
                entries.append(entry)
                seen.add(text)
            else:
                # An already exported display string still gets its typed link
                # and source ownership back when the browser reads raw fields.
                for existing in entries:
                    if existing["text"] == text and existing["citationRole"] == "existing":
                        existing.update(entry)
                        break
    return entries


def references(event: Mapping[str, Any] | None) -> list[str]:
    return [entry["text"] for entry in reference_entries(event)]
