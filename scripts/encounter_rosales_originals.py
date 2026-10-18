"""Parse retained public Rosales HTML captures into private discovery candidates.

Offline only. Source rows remain allegations and are never promoted to runtime.
Native numbering and HC numbers are citations, not globally unique event keys.
"""
from __future__ import annotations

import argparse
from bisect import bisect_right
import csv
import gzip
import hashlib
from collections import Counter
from datetime import date
from html.parser import HTMLParser
import json
import io
from pathlib import Path
import re


def compact(text: str) -> str:
    return " ".join(text.split())


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class PlainText(HTMLParser):
    """Retain actual block boundaries; ignore archived navigation scripts."""
    BLOCKS = {"p", "br", "div", "hr", "li", "tr", "td", "h1", "h2", "h3", "h4"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.skip += 1
        if tag in self.BLOCKS and not self.skip:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.skip = max(0, self.skip - 1)
        if tag in self.BLOCKS and tag != "br" and not self.skip:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


MONTHS = {name.lower(): i for i, name in enumerate(
    ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"), 1)}
MONTHS.update({name[:3]: i for name, i in list(MONTHS.items())})


def parse_date(raw: str | None) -> tuple[str | None, str, list[str]]:
    """Only explicit valid calendar days receive an ISO day; no invented dates."""
    value = compact(raw or "")
    if not value:
        return None, "unknown", ["missing_date"]
    if re.search(r"\b(?:Time|Type)\s*[:.]?", value, re.I):
        return None, "unparsed", ["date_header_contamination"]
    m = re.fullmatch(r"([A-Za-z]+)\.?\s+(\d{1,2}),?\s+(\d{4})", value)
    if m and m[1].lower() in MONTHS:
        try:
            return date(int(m[3]), MONTHS[m[1].lower()], int(m[2])).isoformat(), "day", []
        except ValueError:
            return None, "invalid", ["invalid_calendar_date"]
    if re.fullmatch(r"\d{4}", value):
        return None, "year", []
    m = re.fullmatch(r"([A-Za-z]+)\.?\s+\d{4}", value)
    if m and m[1].lower() in MONTHS:
        return None, "month", []
    if re.search(r"\b(?:circa|about|approx|early|late|mid|spring|summer|autumn|fall|winter|before|after)\b|\?", value, re.I):
        return None, "approximate", []
    if re.search(r"\bBC\b|\bAD\b|\d\s*[-–/]\s*\d", value, re.I):
        return None, "historical_or_range", []
    return None, "unparsed", ["unparsed_date"]


NUMBER = re.compile(r"(?m)^[ \t]*(\d{1,4})(?:\.[ \t]*$|,?[ \t]*(?=\n(?:[ \t]*\n)*[ \t]*Location[ .:]))")
LOCATION = re.compile(r"(?mi)^[ \t]*Location\s*[.:]?\s*(.*?)\s*$")
DATE = re.compile(r"(?mi)^[ \t]*Date\s*[:.]\s*(.*?)\s*$")
TIME = re.compile(r"(?mi)^[ \t]*Time\s*[:.]\s*(.*?)\s*$")
FOOTER = re.compile(r"(?mi)^[ \t]*(?:HC\s+(?:addition|addendum)|Source\s*[:.]|Type\s*[:.]|Comments\s*[:.]|High\s+Strangeness\s+Index\s*:|Reliability\s+of\s+Source\s*:|ROS\s*:)")
STOP = re.compile(r"(?mi)^\s*(?:Total\s+Cases\s*:|Addendums\s+will\s+be|Please\s+send\s+all\s+feedback|Please\s+see\s+the\s+Humanoid|All\s+compiled\s+Humanoid)")


def decode_html(payload: bytes) -> tuple[str, str]:
    try:
        return payload.decode("utf-8-sig"), "utf-8"
    except UnicodeDecodeError:
        # Some captures mix UTF-8 and isolated Windows smart-quote bytes.
        # Preserve valid UTF-8 and decode only the otherwise undecodable bytes.
        mixed = payload.decode("utf-8", errors="surrogateescape")
        parts = []
        for character in mixed:
            value = ord(character) - 0xDC00
            if 0x80 <= value <= 0xFF:
                try:
                    character = bytes([value]).decode("cp1252")
                except UnicodeDecodeError:
                    character = chr(value)
            parts.append(character)
        return "".join(parts), "utf8_with_legacy_bytes"


def normalize_layout(text: str) -> str:
    text = text.replace("\xa0", " ").replace("\r", "")
    text = re.sub(r"(?m)(^\s*Location[^\n]*?)(Date\s*:)", r"\1\n\2", text)
    return re.sub(r"\bT\s*y\s*p\s*e(?=\s*:)", "Type", text, flags=re.I)


def extract_rows(payload: bytes, source: dict, include_narratives=False) -> tuple[list[dict], dict]:
    page_starts = []
    pdf_page_count = None
    if payload.startswith(b"%PDF"):
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(payload))
        parts, position = [], 0
        for page_number, page in enumerate(reader.pages, 1):
            page_text = page.extract_text() or ""
            # Remove only the document's leading page number, not narrative numbers.
            page_text = re.sub(rf"\A\s*{page_number}\s*\n", "", page_text)
            page_text = normalize_layout(page_text)
            page_starts.append(position)
            parts.append(page_text + "\n")
            position += len(page_text) + 1
        text = "".join(parts)
        encoding = "pdf_native_text_pypdf"
        pdf_page_count = len(reader.pages)
        if not text.strip():
            raise ValueError(f"No native PDF text; OCR review required: {source.get('path')}")
    else:
        html, encoding = decode_html(payload)
        parser = PlainText()
        parser.feed(html)
        text = normalize_layout("".join(parser.parts))
    boundaries = list(NUMBER.finditer(text))
    capture_sha = hashlib.sha256(payload).hexdigest()
    expected_sha = source.get("sha256")
    if expected_sha and expected_sha != capture_sha:
        raise ValueError(f"Capture hash mismatch: {source.get('path')}")
    url = source.get("url") or source.get("sourceUrl")
    source_id = source.get("sourceId") or "rosales_original"
    page_match = re.search(r"humanoid-?(ancient|\d{4})\.(?:s?html?|pdf)", url or "", re.I)
    page = page_match[1] if page_match else source.get("yearPage")
    declared_range = re.search(r"(?mi)^\s*(\d{4})\s*[-–]+\s*(\d{4})\s+HUMANOID", text[:1500])
    source_year_range = [int(declared_range[1]), int(declared_range[2])] if declared_range else None
    rows = []
    rejected = []
    for ordinal, boundary in enumerate(boundaries, 1):
        raw_block = text[boundary.end():boundaries[ordinal].start() if ordinal < len(boundaries) else len(text)]
        block_start = boundary.end() + len(raw_block) - len(raw_block.lstrip())
        block = raw_block.strip()
        stop = STOP.search(block)
        if stop:
            block = block[:stop.start()].strip()
        loc = LOCATION.search(block)
        dm = DATE.search(block)
        flags = []
        if re.match(r"\s*(?:\[?Removed\s+by\s+request\]?|Entry\s+removed)\b", block, re.I):
            rejected.append({"ordinal": ordinal, "nativeEntryNumber": boundary[1], "blockSha256": sha(compact(block)), "reason": "explicit_source_removal"})
            continue
        if not dm:
            # Preserve an explicit typo in the original header, with a review flag.
            dm = re.search(r'(?mi)^\s*Date[\u201d\u201c"]\s*([^\n]+)', block)
            if dm:
                flags.append("malformed_date_label")
        if not dm and loc:
            unlabelled = re.search(r"\S[^\n]*", block[loc.end():])
            candidate = unlabelled[0] if unlabelled else ""
            misplaced_location = re.match(r"Location\s*[.:]\s*(.*)", candidate, re.I)
            if misplaced_location:
                candidate = misplaced_location[1]
            candidate_date = re.split(r"Time\s*:", candidate, maxsplit=1, flags=re.I)[0].strip()
            if unlabelled and (parse_date(candidate_date)[1] == "day" or (misplaced_location and "Time:" in candidate and re.search(r"\d{4}", candidate_date))):
                # Store its original span so the narrative begins after the header.
                dm = re.search(re.escape(unlabelled[0]), block[loc.end():])
                date_value = candidate
                date_end_override = loc.end() + dm.end()
                flags.append("date_mislabelled_location" if misplaced_location else "unlabelled_date_header")
            else:
                date_value = None
        else:
            date_value = None
        if not loc or not dm:
            rejected.append({"ordinal": ordinal, "nativeEntryNumber": boundary[1], "blockSha256": sha(compact(block)), "reason": "missing_location_or_date_label"})
            continue
        date_raw = compact(date_value if date_value is not None else dm[1])
        date_end = date_end_override if date_value is not None else dm.end()
        inline_time = re.search(r"Time\s*[:.]\s*(.*)$", date_raw, re.I)
        if inline_time:
            time_raw = compact(inline_time[1])
            date_raw = date_raw[:inline_time.start()].strip()
            narrative_start = date_end
        else:
            tm = TIME.search(block, date_end)
            # A clock elsewhere in a narrative is not the report header.
            if tm and len(compact(block[date_end:tm.start()])) == 0:
                time_raw = compact(tm[1])
                narrative_start = tm.end()
            else:
                time_raw = None
                narrative_start = date_end
                flags.append("missing_or_malformed_time_header")
        # Preserve erroneous header classifications separately from footer types.
        header_type = re.match(r"\s*Type\s*:\s*([^\n]+)", block[narrative_start:], re.I)
        header_classification = compact(header_type[1]) if header_type else None
        if header_type:
            narrative_start += header_type.end()
            flags.append("unexpected_header_classification")
        footer = FOOTER.search(block, narrative_start)
        narrative = compact(block[narrative_start:footer.start() if footer else len(block)])
        footer_text = block[footer.start():] if footer else ""
        if not narrative:
            flags.append("missing_narrative")
        type_matches = list(re.finditer(r"(?mi)\bType\s*[:.]\s*([^\n]*)", footer_text))
        # Later comments sometimes reproduce a different comparison case.
        # Its Type must not overwrite the primary report's first footer Type.
        type_raw = compact(type_matches[0][1]) if type_matches else None
        # Only the leading code expression is a classification. A prose article
        # such as 'a humanoid' must never create an additional Type A.
        code_expression = re.match(r"^([A-HX]\b[?#!]*(?:\s*(?:&|/|,|\bor\b|\band\b)\s*[A-HX]\b[?#!]*)*)", type_raw or "", re.I)
        type_codes = re.findall(r"\b[A-HX]\b", code_expression[1].upper()) if code_expression else []
        if not type_raw:
            flags.append("missing_source_classification")
        elif not type_codes:
            flags.append("unrecognized_source_classification")
        if type_raw and re.search(r"[#*!]", type_raw):
            flags.append("source_classification_annotation")
        if type_raw and ("?" in type_raw or re.search(r"\bor\b|\bpossibly\b", type_raw, re.I)):
            flags.append("uncertain_source_classification")
        source_match = re.search(r"(?mis)^\s*Source\s*[:.]\s*(.*?)(?=\bType\s*[:.]|^\s*(?:Comments\s*:|High\s+Strangeness|Reliability\s+of\s+Source|ROS\s*:)|\Z)", footer_text)
        citation = compact(source_match[1]) if source_match else None
        if not citation:
            flags.append("missing_source_citation")
        hc_matches = re.findall(r"(?mi)^\s*HC\s+(?:addition|addendum)\s*#\s*(\d+)\b", footer_text)
        source_ids = [{"scheme": "rosales_hc", "value": x} for x in dict.fromkeys(hc_matches)]
        date_iso, precision, date_flags = parse_date(date_raw)
        date_start_iso = date_iso
        if precision == "year":
            date_start_iso = date_raw
        elif precision == "month":
            month_name, year = date_raw.replace(".", "").split()
            date_start_iso = f"{year}-{MONTHS[month_name.lower()]:02d}"
        flags += date_flags
        occurrence_years = re.findall(r"\b(?:1[0-9]{3}|20\d\d)\b", date_raw)
        if page and not source_year_range and page not in {"ancient", "1910", "1930"} and occurrence_years and page not in occurrence_years:
            flags.append("occurrence_year_differs_from_page")
        location_raw = compact(loc[1])
        if re.search(r"unknown|not given|not specified|not known|unspecified|not stated|undisclosed", location_raw, re.I):
            flags.append("location_not_specific")
        result = {
            "sourceEntryId": f"rosales-original:{page or sha(url or '')[:12]}:{ordinal}:{sha(compact(block))[:12]}",
            "sourceId": source_id, "sourceUrl": url, "yearPage": page,
            "sourceDeclaredYearRange": source_year_range,
            "sourceEntryOrdinal": ordinal, "nativeEntryNumber": boundary[1],
            "locationRaw": location_raw, "dateRaw": date_raw, "dateIso": date_iso,
            "dateStartIso": date_start_iso,
            "datePrecision": precision, "timeRaw": time_raw,
            "sourceCaseIds": source_ids, "sourceClassificationRaw": type_raw,
            "sourceClassificationCodes": list(dict.fromkeys(type_codes)),
            "headerClassificationRaw": header_classification, "sourceCitationRaw": citation,
            "narrativeSha256": sha(narrative), "narrativeCharacters": len(narrative),
            "sourceBlockSha256": sha(compact(block)),
            "capture": {"path": source.get("path"), "sha256": capture_sha, "bytes": len(payload),
                        "captureUtc": source.get("captureUtc"), "encoding": encoding},
            "reviewFlags": flags, "status": "discovery_candidate",
            "publicRedistribution": "not_authorized_by_acquisition",
            "latitude": None, "longitude": None, "utcTime": None,
        }
        if page_starts:
            result["sourcePageStart"] = bisect_right(page_starts, boundary.start())
            result["sourcePageEnd"] = bisect_right(page_starts, block_start + max(0, len(block) - 1))
            result["capture"]["pdfPages"] = pdf_page_count
        if include_narratives:
            result["narrativePrivate"] = narrative
        rows.append(result)
    declared = re.findall(r"Total\s+Cases\s*:\s*(\d+)", text, re.I)
    audit = {"sourceId": source_id, "sourceUrl": url, "yearPage": page,
             "numberedBlocks": len(boundaries), "parsedRows": len(rows), "heldBlocks": rejected,
             "declaredTotals": [int(x) for x in declared], "encoding": encoding,
             "pdfPages": pdf_page_count,
             "sourceDeclaredYearRange": source_year_range,
             "captureSha256": capture_sha,
             "reviewFlags": dict(Counter(f for r in rows for f in r["reviewFlags"]))}
    return rows, audit


def build(manifest: Path | list[Path], output: Path, audit_path: Path, include_narratives=False):
    if output.exists() or audit_path.exists():
        raise FileExistsError("Refusing to replace an existing validated output or audit; choose an explicit new destination")
    manifests = [manifest] if isinstance(manifest, Path) else manifest
    rows, audits = [], []
    seen, skipped, alternate_captures = {}, 0, []
    for manifest_path in manifests:
        data = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        for source in data["sources"]:
            if source.get("status") not in {"captured", "reused"}:
                continue
            path = Path(source["path"])
            if not path.is_absolute():
                path = manifest_path.parent / path
            payload = path.read_bytes()
            actual_sha = hashlib.sha256(payload).hexdigest()
            if source.get("sha256") and source["sha256"] != actual_sha:
                raise ValueError(f"Capture hash mismatch: {path}")
            source_url = source.get("url") or source.get("sourceUrl")
            if source_url in seen:
                skipped += 1
                if seen[source_url] != actual_sha:
                    alternate_captures.append({"sourceUrl": source_url, "retainedSha256": seen[source_url], "alternateSha256": actual_sha, "path": str(path), "decision": "first_capture_retained_alternate_not_promoted"})
                continue
            seen[source_url] = actual_sha
            found, audit = extract_rows(payload, {**source, "path": str(path)}, include_narratives)
            rows += found
            audits.append(audit)
    output.parent.mkdir(parents=True, exist_ok=True)
    ids = [row["sourceEntryId"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate sourceEntryIds; candidates require source identity review")
    document = {"schemaId": "rosales-original-discovery-v1", "records": rows,
                "runtimePromotions": 0, "narrativesIncluded": include_narratives}
    encoded = (json.dumps(document, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    decoded_bytes = len(encoded)
    if decoded_bytes > 32 * 1024 * 1024:
        raise ValueError("Decoded candidate output exceeds the bounded 32 MiB cap")
    if output.suffix == ".gz":
        encoded = gzip.compress(encoded, mtime=0)
        if len(encoded) > 4 * 1024 * 1024:
            raise ValueError("Compressed candidate output exceeds the bounded 4 MiB cap")
    output.write_bytes(encoded)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    summary = {"schemaId": "rosales-original-discovery-audit-v1", "manifests": [str(p) for p in manifests],
               "inputManifestPins": [{"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size} for p in manifests],
               "builderSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "output": str(output), "sourcesParsed": len(audits), "candidateRows": len(rows),
               "outputSha256": hashlib.sha256(encoded).hexdigest(), "outputBytes": len(encoded), "decodedBytes": decoded_bytes,
               "duplicateCapturesSkipped": skipped, "alternateCapturesHeld": alternate_captures,
               "datePrecision": dict(Counter(r["datePrecision"] for r in rows)),
               "reviewFlags": dict(Counter(f for r in rows for f in r["reviewFlags"])),
               "sourceAudits": audits, "runtimePromotions": 0,
               "policy": "Private discovery candidates; no source account is a verified incident, and acquisition conveys no public redistribution permission."}
    audit_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True, action="append", help="Repeat to combine a base capture manifest and bounded retry manifests")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--include-narratives", action="store_true", help="Private output only; never publish or commit full narratives")
    args = parser.parse_args()
    summary = build(args.manifest, args.output, args.audit, args.include_narratives)
    print(json.dumps({k: summary[k] for k in ("sourcesParsed", "candidateRows", "datePrecision", "reviewFlags", "runtimePromotions")}))


if __name__ == "__main__":
    main()
