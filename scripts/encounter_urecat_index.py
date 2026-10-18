"""Parse a pinned URECAT index capture offline, without fetching case narratives.

The resulting records are private research candidates, not new verified incidents.
Dates come from the visible index cell, never the filename. Repeated index rows
and supported English/French aliases retain their source row references.
"""
import argparse
from collections import Counter
from datetime import date
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import urljoin, urlsplit, urlunsplit


SOURCE_URL = "https://ufologie.patrickgross.org/ce3/_full.htm"
HOSTS = {"ufologie.patrickgross.org", "ufology.patrickgross.org"}
MONTHS = {
    name: number
    for number, names in enumerate([
        ("january", "jan", "janvier"), ("february", "feb", "fevrier"),
        ("march", "mar", "mars"), ("april", "apr", "avril"),
        ("may", "mai"), ("june", "jun", "juin"),
        ("july", "jul", "juillet"), ("august", "aug", "aout"),
        ("september", "sep", "sept", "septembre"),
        ("october", "oct", "octobre"), ("november", "nov", "novembre"),
        ("december", "dec", "decembre"),
    ], 1)
    for name in names
}


def clean(value):
    return re.sub(r"\s+", " ", value).strip()


def folded(value):
    value = unicodedata.normalize("NFKD", value.casefold())
    return "".join(c for c in value if not unicodedata.combining(c))


def parse_date(raw):
    """Return only fully stated, valid, unqualified dates as exact dates."""
    value = folded(clean(raw)).strip()
    result = {"dateIso": None, "datePrecision": "unknown"}
    if not value or value in {"unknown", "not known", "?", "date unknown", "inconnue"}:
        return result
    if re.search(r"\b(?:bc|bce|av\.?)\b", value):
        return dict(result, datePrecision="historical")
    if re.search(r"\b(?:or|ou|between|from|to|and|entre|au)\b", value) or (re.search(r"\d\s*[-/]\s*\d", value) and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)):
        return dict(result, datePrecision="range")
    if len([word for word in re.findall(r"[a-z]+", value) if word in MONTHS]) > 1 or len(re.findall(r"\d+", value)) > 3:
        return dict(result, datePrecision="range")
    if re.search(r"\b(?:before|after|since|avant|apres|depuis)\b", value):
        return dict(result, datePrecision="bounded")
    if re.fullmatch(r"(?:the )?\d{3}0['’]?s", value):
        return dict(result, datePrecision="decade")
    if "?" in value or re.search(r"\b(?:about|circa|ca|maybe|probably|possible|early|late|mid|beg|beginning|end|debut|fin|environ)\b", value):
        return dict(result, datePrecision="approximate")
    if re.search(r"\b(?:spring|summer|autumn|fall|winter|printemps|ete|automne|hiver)\b", value):
        return dict(result, datePrecision="season")
    value = re.sub(r"(?<=\d)(?:st|nd|rd|th)\b", "", value)
    value = clean(value.replace(",", " "))
    if re.fullmatch(r"\d{3,4}", value):
        return dict(result, datePrecision="year")
    match = re.fullmatch(r"([a-z]+)\.? (\d{3,4})", value)
    if match and match[1] in MONTHS:
        return dict(result, datePrecision="month")
    parts = None
    match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", value)
    if match:
        parts = tuple(map(int, match.groups()))
    else:
        match = re.fullmatch(r"([a-z]+)\.? (\d{1,2}) (\d{3,4})", value)
        if match and match[1] in MONTHS:
            parts = (int(match[3]), MONTHS[match[1]], int(match[2]))
        match = re.fullmatch(r"(\d{1,2}) ([a-z]+)\.? (\d{3,4})", value)
        if match and match[2] in MONTHS:
            parts = (int(match[3]), MONTHS[match[2]], int(match[1]))
    if parts:
        try:
            return {"dateIso": date(*parts).isoformat(), "datePrecision": "day"}
        except ValueError:
            return dict(result, datePrecision="invalid")
    return dict(result, datePrecision="unparsed")


def case_url(href, source_url=SOURCE_URL):
    """Identify native case pages; ignore countries, year indexes and navigation."""
    absolute = urlsplit(urljoin(source_url, href))
    host = (absolute.hostname or "").lower().removeprefix("www.")
    name = absolute.path.rsplit("/", 1)[-1]
    if absolute.scheme not in {"http", "https"} or host not in HOSTS:
        return None
    if not absolute.path.startswith("/ce3/") or not re.fullmatch(r"\d{3,4}s?(?:-.+)?\.html?", name):
        return None
    return urlunsplit(("https", "ufologie.patrickgross.org", absolute.path, "", ""))


class IndexRows(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.row = None
        self.cell = None
        self.link = None
        self.row_number = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "tr":
            self._finish_row()
            self.row_number += 1
            self.row = {"rowNumber": self.row_number, "htmlLine": self.getpos()[0], "cells": []}
        elif tag in {"td", "th"} and self.row is not None:
            self.cell = {"text": [], "links": []}
            self.row["cells"].append(self.cell)
        elif tag == "a" and self.cell is not None and attrs.get("href"):
            self.link = {"href": attrs["href"], "text": []}
            self.cell["links"].append(self.link)
        elif tag == "br" and self.cell is not None:
            self.cell["text"].append(" ")

    def handle_data(self, data):
        if self.cell is not None:
            self.cell["text"].append(data)
        if self.link is not None:
            self.link["text"].append(data)

    def handle_endtag(self, tag):
        if tag == "a":
            self.link = None
        elif tag in {"td", "th"}:
            self.cell = self.link = None
        elif tag == "tr":
            self._finish_row()

    def _finish_row(self):
        if self.row is not None:
            self.rows.append(self.row)
        self.row = self.cell = self.link = None

    def close(self):
        super().close()
        self._finish_row()


def _native_ids(text):
    return sorted(set("URECAT-" + number.zfill(6)
                      for number in re.findall(r"\bURECAT[-\s]+(\d{1,6})\b", text, re.I)))


def _row_signature(row):
    parsed = parse_date(row["dateRaw"])
    return (parsed["dateIso"] or folded(row["dateRaw"]), folded(row["locationRaw"]))


def parse_index(data, source_url=SOURCE_URL, input_path=None):
    """Produce deterministic source-pinned metadata, preserving identity holds."""
    charset = re.search(rb"charset\s*=\s*['\"]?([\w-]+)", data[:4096], re.I)
    encoding = charset[1].decode("ascii") if charset else "utf-8"
    html = data.decode(encoding, errors="strict")
    parser = IndexRows()
    parser.feed(html)
    parser.close()
    groups = {}
    case_rows = 0
    for row in parser.rows:
        cells = row["cells"]
        if len(cells) < 2:
            continue
        values = [clean("".join(cell["text"])) for cell in cells]
        for cell in cells:
            for link in cell["links"]:
                url = case_url(link["href"], source_url)
                if not url:
                    continue
                case_rows += 1
                reference = {
                    "rowNumber": row["rowNumber"], "htmlLine": row["htmlLine"],
                    "href": link["href"], "sourceUrl": url,
                    "dateRaw": values[0], "locationRaw": clean("".join(link["text"])) or values[1],
                    "reportedNamesRaw": values[2] if len(values) > 2 else "",
                    "sourceCaseIds": _native_ids(" ".join(values)),
                }
                groups.setdefault(url, []).append(reference)
    distinct_urls = len(groups)
    bilingual_groups = 0
    # A terminal f is not enough: Tindouf is a real place name. Merge only if
    # the counterpart exists and visible date/place, place or native IDs agree.
    # Contradictory dates stay held, including aliases for a multi-episode page.
    for french_url in sorted(list(groups)):
        if french_url not in groups:
            continue
        match = re.fullmatch(r"(.+)f(\.html?)", french_url)
        if not match:
            continue
        english_url = match[1] + match[2]
        if english_url not in groups:
            continue
        left, right = groups[french_url], groups[english_url]
        same_metadata = bool({_row_signature(r) for r in left} & {_row_signature(r) for r in right})
        same_place = bool({folded(r["locationRaw"]) for r in left if r["locationRaw"]}
                          & {folded(r["locationRaw"]) for r in right if r["locationRaw"]})
        left_ids = {i for r in left for i in r["sourceCaseIds"]}
        right_ids = {i for r in right for i in r["sourceCaseIds"]}
        if (same_metadata or same_place or left_ids & right_ids) and not (left_ids and right_ids and left_ids != right_ids):
            groups[english_url].extend(groups.pop(french_url))
            bilingual_groups += 1
    records = []
    for url, references in sorted(groups.items()):
        references.sort(key=lambda r: (r["rowNumber"], r["href"]))
        first = references[0]
        date_variants = sorted({r["dateRaw"] for r in references})
        dates = [parse_date(value) for value in date_variants]
        exact = {d["dateIso"] for d in dates if d["dateIso"]}
        date_iso = next(iter(exact)) if len(exact) == 1 and all(d["dateIso"] for d in dates) else None
        precisions = {d["datePrecision"] for d in dates}
        precision = ("conflicting" if len(exact) > 1 else
                     next(iter(precisions)) if len(precisions) == 1 else "mixed")
        ids = sorted({i for r in references for i in r["sourceCaseIds"]})
        flags = []
        if date_iso is None:
            flags.append("date_not_exact")
        if len(exact) > 1:
            flags.append("index_date_conflict")
        if len(ids) > 1:
            flags.append("native_id_conflict")
        if len({r["sourceUrl"] for r in references}) > 1:
            flags.append("bilingual_alias_unreviewed")
        if re.fullmatch(r"\d{3,4}s?\.html?", url.rsplit("/", 1)[-1]):
            flags.append("year_only_link_target_unreviewed")
        entry_id = (ids[0].lower() if len(ids) == 1 else
                    "urecat-index:" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:20])
        records.append({
            "sourceEntryId": entry_id, "sourceUrl": url, "sourceCaseIds": ids,
            "dateRaw": first["dateRaw"], "dateIso": date_iso, "datePrecision": precision,
            "dateVariants": date_variants,
            "locationRaw": first["locationRaw"],
            "locationVariants": sorted({r["locationRaw"] for r in references}),
            "sourceUrlAliases": sorted({r["sourceUrl"] for r in references}),
            "rowReferences": references, "reviewFlags": flags,
            "status": "index_candidate_unreviewed", "acceptedForRuntime": False,
        })
    pin = {"sourceUrl": source_url, "sha256": hashlib.sha256(data).hexdigest(),
           "bytes": len(data), "encoding": encoding}
    if input_path is not None:
        pin["inputPath"] = str(Path(input_path).resolve())
    return {
        "schemaId": "ufo-encounter-urecat-index-candidates-v1", "sourcePin": pin,
        "policy": "Private offline index metadata only. No case narratives fetched; no incident verification, runtime promotion, or public redistribution authorization.",
        "counts": {
            "tableRows": len(parser.rows), "caseRowReferences": case_rows,
            "distinctCaseUrls": distinct_urls, "candidateRecords": len(records),
            "duplicateUrlRowReferences": case_rows - distinct_urls,
            "bilingualAliasGroups": bilingual_groups,
            "datePrecision": dict(sorted(Counter(r["datePrecision"] for r in records).items())),
            "exactDateRecords": sum(r["dateIso"] is not None for r in records),
            "nativeIdRecords": sum(bool(r["sourceCaseIds"]) for r in records),
            "dateConflictRecords": sum("index_date_conflict" in r["reviewFlags"] for r in records),
            "runtimePromotions": 0,
        },
        "records": records,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-url", default=SOURCE_URL)
    parser.add_argument("--expected-sha256", help="Refuse a capture that differs from its manifest pin.")
    parser.add_argument("--overwrite", action="store_true", help="Replace a reproducible candidate output, never the input.")
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error("The protected source input cannot be the output.")
    if args.output.exists() and not args.overwrite:
        parser.error("Candidate output already exists; pass --overwrite only for deliberate regeneration.")
    data = args.input.read_bytes()
    if args.expected_sha256 and hashlib.sha256(data).hexdigest() != args.expected_sha256.lower():
        parser.error("Input SHA-256 differs from the expected capture pin.")
    result = parse_index(data, args.source_url, args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output.resolve()), "sourcePin": result["sourcePin"], "counts": result["counts"]}, indent=2))


if __name__ == "__main__":
    main()
