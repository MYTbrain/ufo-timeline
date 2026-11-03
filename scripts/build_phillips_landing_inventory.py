"""Build factual landing-trace index metadata from the July 1975 CUFOS scan."""

import argparse
import concurrent.futures
from collections import defaultdict
import csv
import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import re
import statistics
import subprocess


CATALOG_URL = "https://cufos.org/PDFs/books/Physical_Traces.pdf"
CATALOG_SHA256 = "e824270528264c2563df17f79540171dc216fb9be85968a5eb844ecb1b2be17b"
CATALOG_FIRST_PAGE = 19
CATALOG_LAST_PAGE = 129
INSUFFICIENT_FIRST_PAGE = 126
DECLARED_COUNT = 831
DPI = 180
VERIFIED_PAGES = {
    12: 19, 54: 28, 104: 19, 112: 37, 158: 46, 164: 47, 179: 50, 188: 52, 199: 54, 221: 58, 235: 60,
    247: 61, 248: 62, 259: 63, 264: 63, 269: 65, 288: 69, 290: 69, 291: 69,
    293: 69, 381: 82, 386: 83, 476: 95, 494: 97, 496: 97, 535: 104, 537: 104,
    583: 108, 618: 75, 643: 115, 665: 109, 673: 104, 684: 57, 707: 70, 708: 75,
    712: 69, 726: 111, 746: 122, 753: 108, 763: 64, 787: 32,
}
# Independently read from the scan for the linked case dossiers.
REVIEWED_ROWS = {
    12: ("1490", "Ireland", "sighting_trace", [], []),
    54: ("1953-07-02", "Villares del Saz, Spain", "sighting_trace",
         ["impression"], ["rectangular"]),
    104: ("1663-08-15", "Robozero, U.S.S.R.", "sighting_trace", [], []),
    112: ("1956", "Bethel, Connecticut, United States", "trace_discovery",
          ["scorching", "surface"], ["circular"]),
    158: ("1963-01-31", "Tucumán, Argentina", "sighting_trace",
          ["scorching", "surface"], ["circular"]),
    164: ("1963-12-27", "Epping, Essex, England", "sighting_trace",
          ["impression", "deformation"], ["circular", "rectangular"]),
    179: ("1964-09-04", "Glassboro, New Jersey, United States", "sighting_trace",
          ["impression", "scorching", "deformation"], ["circular", "radial"]),
    188: ("1965-01-12", "Custer, Washington, United States", "sighting_trace",
          ["impression", "scorching", "surface"], ["circular", "linear"]),
    199: ("1965-06-28", "Delroy, Ohio, United States", "trace_discovery",
          ["impression", "deformation", "surface"], ["circular", "radial"]),
    221: ("1966-01", "Corndale, New South Wales, Australia", "sighting_trace",
          ["impression"], ["circular"]),
    235: ("1966-05", "Canada, locality unspecified", "sighting_trace",
          ["deformation"], ["circular", "swirl"]),
    247: ("1966-09-13", "Stirum, North Dakota, United States", "sighting_trace",
          ["impression"], ["triangular"]),
    248: ("1966-10-05", "East Connersville, Indiana, United States", "sighting_trace",
          ["impression"], ["triangular"]),
    259: ("1967", "Colorado, United States", "sighting_trace",
          ["impression", "scorching"], ["rectangular"]),
    264: ("1967-01", "McGregor, Iowa, United States", "trace_discovery",
          ["surface"], ["circular"]),
    269: ("1967-04-08", "Banner Elk, North Carolina, United States", "sighting_trace",
          ["impression"], ["triangular"]),
    291: ("1967-09", "Bowden, Alberta, Canada", "trace_discovery",
          ["deformation"], ["circular"]),
    381: ("1969-05-11", "Chapeau, Québec, Canada", "sighting_trace",
          ["impression", "surface"], ["triangular", "circular"]),
    386: ("1969-06-17", "Ibiúna, São Paulo, Brazil", "sighting_trace",
          ["deformation"], ["circular", "swirl"]),
    476: ("1971-05-25", "Lynchford, Tasmania, Australia", "trace_discovery",
          ["impression", "deformation"], ["triangular", "swirl"]),
    496: ("1971-11-13", "Lucerne Valley, California, United States", "sighting_trace",
          ["impression"], ["triangular"]),
    535: ("1972-09-20", "Montauroux, France", "trace_discovery",
          ["deformation"], ["swirl"]),
    537: ("1972-09-14", "Houston, Missouri, United States", "sighting_trace",
          ["impression", "deformation", "surface", "scorching"], ["triangular", "circular"]),
    583: ("1973-06-03", "Junee, New South Wales, Australia", "sighting_trace",
          ["scorching", "impression"], ["circular"]),
    618: ("1968", "Brasília, Brazil", "sighting_trace",
          ["impression"], ["triangular"]),
    643: ("1973-11-16", "Lemon Grove, California, United States", "sighting_trace",
          ["impression", "deformation"], ["triangular", "swirl"]),
    665: ("1973-07-04", "Ponzano Magra Inferiore, La Spezia, Italy", "sighting_trace",
          ["impression"], ["rectangular"]),
    673: ("1972-09-28", "Valea Popiliu, Prahova, Romania", "sighting_trace",
          ["impression", "scorching", "deformation"], ["circular", "radial"]),
    684: ("1965-10-23", "Long Prairie, Minnesota, United States", "sighting_trace",
          ["surface"], ["linear"]),
    707: ("1967-09-20", "Winsted, Connecticut, United States", "sighting_trace",
          ["impression", "scorching", "deformation"], ["triangular"]),
    708: ("1968-08-10", "La Criolla, Argentina", "sighting_trace",
          ["impression"], ["triangular"]),
    726: ("1974-10-06", "St. Matthias, Canada", "sighting_trace",
          ["impression", "deformation", "surface"], ["triangular", "linear"]),
    746: ("1974-09-01", "Langenburg, Saskatchewan, Canada", "sighting_trace",
          ["deformation"], ["circular", "swirl"]),
    753: ("1973-07", "Hinsdale, New Hampshire, United States", "trace_discovery",
          ["deformation"], ["swirl", "circular"]),
    763: ("1967", "Ironton, Missouri, United States", "sighting_trace",
          ["impression"], ["circular"]),
    787: ("1954-09-27", "Prémanon, Jura, France", "sighting_trace",
          ["deformation", "impression"], ["circular", "rectangular", "swirl"]),
}
REVIEWED_MEDIA = {
    179: ["photo"], 188: ["sketch"], 199: ["photo"], 381: ["photo", "sketch"],
    537: ["photo", "sketch"], 665: ["photo", "sketch"], 708: ["sketch"],
    726: ["photo", "sketch"], 753: ["photo"],
}
ID_DIGITS = str.maketrans({"O": "0", "o": "0", "Q": "0", "I": "1", "l": "1", "|": "1",
                          "Z": "2", "z": "2", "S": "5", "G": "6", "B": "8"})
CASE_NUMBER = re.compile(r"([0-9OoQIl|ZzSGB]{3})([ps]{0,2})")
MONTHS = {month.lower(): number for number, month in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}
COUNTRIES = (
    "ARGENTINA", "AUSTRALIA", "AUSTRIA", "BELGIUM", "BOLIVIA", "BRAZIL", "CANADA", "CHILE",
    "COLOMBIA", "CUBA", "CZECHOSLOVAKIA", "DENMARK", "ECUADOR", "ENGLAND", "FINLAND",
    "FRANCE", "GERMANY", "GREECE", "HOLLAND", "HUNGARY", "ICELAND", "INDIA", "INDONESIA",
    "IRELAND", "ITALY", "JAPAN", "KOREA", "MALAYSIA", "MEXICO", "MOROCCO", "NETHERLANDS",
    "NEW GUINEA", "NEW ZEALAND", "NORTHERN IRELAND", "NORWAY", "PARAGUAY", "PERU",
    "PHILIPPINES", "POLAND", "PORTUGAL", "RHODESIA", "ROMANIA", "SCOTLAND", "SOUTH AFRICA",
    "SPAIN", "SWEDEN", "SWITZERLAND", "TAIWAN", "TASMANIA", "THAILAND", "URUGUAY",
    "VENEZUELA", "WALES", "YUGOSLAVIA",
)
COUNTRY = re.compile(r"^(U\s*\.?\s*S\s*\.?\s*S\s*\.?\s*R\s*\.?|U\s*\.\s*S\s*\.?|"
                     + "|".join(COUNTRIES) + r")(?=[\s,.;:]+|$)")
OBSERVATION_START = re.compile(
    r"\b(?:A|An|The|Two|Three|Four|Five|Six|Several|Many|One|Mr|Mrs|Miss|While|Object|"
    r"Trace[s]?|Landed|Witness(?:es)?|Not translated|Photograph|No details)\b"
)
SITE_TERMS = r"(?:ground|soil|earth|grass|trees?|plants?|vegetation|crop[s]?|wheat|reeds?|bush(?:es)?|lawn|field|asphalt|road|snow|sand|moss)"
TRACE_TERMS = r"(?:imprint[s]?|indentation[s]?|impression[s]?|depression[s]?|holes?|tracks?|footprints?|marks?|traces?|rings?|patch(?:es)?|scars?)"
EVIDENCE = {
    "impression": (
        rf"\b(?:imprints?|indentations?|footprints?|depressions?|impressions?|craters?)\b",
        rf"\bholes?\b.{{0,45}}\b(?:in|found|discovered|deep|diameter)\b|\b(?:found|discovered)\b.{{0,32}}\bholes?\b",
        rf"\b(?:ruts?|furrows?)\b.{{0,35}}\b(?:{SITE_TERMS}|found|deep)\b",
    ),
    "scorching": (
        rf"\b(?:burn(?:ed|t|ing)|scorch(?:ed|ing)?|charred|singed|blackened|calcined)\b.{{0,35}}\b(?:{SITE_TERMS}|{TRACE_TERMS})\b",
        rf"\b{SITE_TERMS}\b.{{0,40}}\b(?:burn(?:ed|t|ing)|scorch(?:ed|ing)?|charred|singed|blackened|calcined|caught fire)\b",
    ),
    "deformation": (
        rf"\b(?:flattened|bent|twisted|matted|pressed down|blown down|uprooted|knocked down|broken|"
        rf"folded|crushed|swirled|cut down|laid flat|torn out)\b.{{0,40}}\b{SITE_TERMS}\b",
        rf"\b{SITE_TERMS}\b.{{0,45}}\b(?:flattened|bent|twisted|matted|pressed down|blown down|uprooted|"
        rf"knocked down|broken|folded|crushed|swirled|cut down|laid flat|torn out)\b",
    ),
    "surface": (
        rf"\b(?:discolou?r(?:ed|ation)|dried|dehydrated|withered|oily|discolou?ration|deposits?|residue)\b.{{0,42}}\b(?:{SITE_TERMS}|{TRACE_TERMS})\b",
        rf"\b{SITE_TERMS}\b.{{0,42}}\b(?:discolou?r(?:ed|ation)|dried|dehydrated|withered|oily|deposits?|residue)\b",
        rf"\b(?:snow|ice)\b.{{0,35}}\bmelt(?:ed|ing)?\b|\bmelt(?:ed|ing)?\b.{{0,35}}\b(?:snow|ice)\b",
    ),
}
PATTERNS = {
    "circular": r"circular|concentric|rings?|circles?|oval|elliptical",
    "triangular": r"triang(?:le|ular|les)",
    "linear": r"in a line|straight line|parallel|row of",
    "rectangular": r"rectangular|rectangle|square|quadrilateral",
    "radial": r"radiat(?:e|ing)|radial|star-shaped|spokes?",
    "swirl": r"spiral(?:led)?|swirl(?:ed|ing)?|clockwise|counterclockwise|anti-clockwise",
}
SIGHTING = re.compile(r"\b(?:saw|seen|observed|sighted|witnessed|spotted)\b")
OBJECT = re.compile(r"\b(?:ufo|object|craft|disc|disk|saucer|light|sphere|globe)\b")
NO_SIGHTING = re.compile(
    r"\b(?:no (?:ufo|object|sighting) (?:was )?(?:seen|reported|observed)|"
    r"(?:ufo|object) (?:was )?not seen)\b"
)


def scan_hash(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_page(pdf, renderer, tesseract, page, left_only=False):
    raster_options = ["-x", "0", "-y", "0", "-W", "470", "-H", "2860"] if left_only else []
    dpi = 260 if left_only else DPI
    raster = subprocess.run(
        [renderer, "-f", str(page), "-l", str(page), "-singlefile", "-r", str(dpi), "-gray",
         *raster_options, str(pdf)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout
    env = {**os.environ, "OMP_THREAD_LIMIT": "1"}
    result = subprocess.run(
        [tesseract, "stdin", "stdout", "--psm", "6", "tsv"],
        check=True,
        input=raster,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    lines = {}
    for row in csv.DictReader(io.StringIO(result.stdout.decode("utf-8")), delimiter="\t", quoting=csv.QUOTE_NONE):
        if row["level"] != "5" or not row["text"]:
            continue
        key = row["block_num"], row["par_num"], row["line_num"]
        scale = DPI / dpi
        lines.setdefault(key, []).append([
            *(round(int(row[field]) * scale) for field in ("left", "top", "width", "height")), row["text"],
        ])
    return page, list(lines.values())


def parsed_date(text):
    """Retain date precision. Reject malformed or unrecognised OCR instead of inventing a date."""
    match = re.search(r"\b([1-9][0-9]{3})\b", text)
    if not match or not 1000 <= int(match[1]) <= 1975:
        return None
    year = int(match[1])
    month_text = re.match(r"^\s*([A-Za-z]{3})[A-Za-z]*\b", text)
    if not month_text or (month := MONTHS.get(month_text[1].lower())) is None:
        return str(year)
    day_text = re.search(r"\b([0-9]{1,2})\b", text[month_text.end():match.start()])
    if day_text:
        try:
            return datetime.date(year, month, int(day_text[1])).isoformat()
        except ValueError:
            pass
    return f"{year:04d}-{month:02d}"


def parsed_location(text):
    """Read a geographic heading at the start of an abstract, not names in the narrative."""
    match = COUNTRY.match(text.strip())
    if not match:
        return None
    country = match[1]
    if country.startswith("U."):
        country = "United States" if "R" not in country else "U.S.S.R."
    else:
        country = country.title()
    remainder = text.strip()[match.end():]
    if remainder.startswith("."):
        return country
    remainder = remainder.lstrip(" ,;:")
    separator = re.search(r"\.(?:\s|$)|\s{3,}|[(){}]", remainder)
    if separator:
        remainder = remainder[:separator.start()]
    if (start := OBSERVATION_START.search(remainder)):
        remainder = remainder[:start.start()]
    locality = remainder.strip(" ,;:.-")
    if not locality or len(locality) > 78 or len(locality.split()) > 8 or not re.search(r"[A-Za-z]", locality):
        return country
    locality = re.sub(r",\s*", ", ", locality)
    return f"{locality}, {country}"


def trace_tags(text):
    # Match local site evidence rather than any discussion of the apparent craft.
    clauses = re.split(r"(?<=[.!?;])\s+", text.lower())
    traces = {
        kind for kind, rules in EVIDENCE.items()
        if any(re.search(rule, clause) for rule in rules for clause in clauses)
    }
    patterns = {
        kind for kind, rule in PATTERNS.items()
        if any(re.search(rf"\b(?:{rule})\b.{{0,27}}\b(?:{TRACE_TERMS}|{SITE_TERMS})\b"
                         rf"|\b{TRACE_TERMS}\b.{{0,22}}\b(?:{rule})\b", clause)
               for clause in clauses)
    }
    return sorted(traces), sorted(patterns if traces else ())


def catalog_anchors(lines):
    matches = [(i, CASE_NUMBER.fullmatch(words[0][4].strip(".,:()[]")))
               for i, words in enumerate(lines) if 35 <= words[0][0] < 290]
    return [(i, match) for i, match in matches
            if match and 1 <= int(match[1].translate(ID_DIGITS)) <= DECLARED_COUNT]


def aligned_anchors(lines, left):
    """Match independent reads of the left column by vertical position."""
    initial = catalog_anchors(lines)
    if not left:
        return [(i, match, 1, False) for i, match in initial]
    y_rows = [statistics.median(word[1] for word in words) for words in lines]
    by_index = {i: [(match, 1)] for i, match in initial}
    for j, match in catalog_anchors(left):
        y = statistics.median(word[1] for word in left[j])
        i = min(range(len(y_rows)), key=lambda index: abs(y_rows[index] - y))
        if abs(y_rows[i] - y) < 14:
            by_index.setdefault(i, []).append((match, 2))
    resolved = []
    for i, reads in sorted(by_index.items()):
        numbers = {int(match[1].translate(ID_DIGITS)) for match, _ in reads}
        if len(numbers) > 1:
            exact = {int(match[1]) for match, _ in reads if match[1].isdigit()}
            if len(exact) != 1:
                continue
            number = next(iter(exact))
            reads = [(match, run) for match, run in reads if int(match[1].translate(ID_DIGITS)) == number]
        match, run = max(reads, key=lambda read: (read[0][1].isdigit(), bool(read[0][2])))
        resolved.append((i, match, run, len(reads) > 1))
    return resolved


def extract_candidates(pages, left_pages):
    by_number = {}
    for page_key, raw in sorted(pages.items(), key=lambda item: int(item[0])):
        page = int(page_key)
        lines = sorted((sorted(words) for words in raw if words),
                       key=lambda words: statistics.median(word[1] for word in words))
        left = [sorted(words) for words in left_pages.get(page_key, []) if words]
        number_words = aligned_anchors(lines, left)
        if not number_words:
            continue
        anchor_starts = [lines[i][0][0] for i, _, _, _ in number_words if lines[i][0][0] < 290]
        if not anchor_starts:
            continue
        margin = statistics.median(anchor_starts)
        anchors = [(i, match, run, corroborated) for i, match, run, corroborated in number_words
                   if abs(lines[i][0][0] - margin) < 31 or lines[i][0][0] > margin + 200]
        body_left = margin + 202
        header_rows = []
        for i, _, _, _ in anchors:
            prior = " ".join(word[4] for word in lines[i - 1] if word[0] < body_left) if i else ""
            has_header = bool(prior and not CASE_NUMBER.fullmatch(prior.split()[0])
                              and (re.search(r"\b(?:[1-9][0-9]{3}s?|Unknown)\b", prior, re.I)
                                   or prior.split()[0][:3].lower() in MONTHS))
            header_rows.append(i - 1 if page < INSUFFICIENT_FIRST_PAGE and has_header else i)

        for sequence, (i, match, run, corroborated) in enumerate(anchors):
            number = int(match[1].translate(ID_DIGITS))
            if number in VERIFIED_PAGES and page != VERIFIED_PAGES[number]:
                continue
            start = header_rows[sequence]
            stop = header_rows[sequence + 1] if sequence + 1 < len(anchors) else len(lines)
            left_text = " ".join(word[4] for word in lines[start] if word[0] < body_left)
            if start == i:
                left_text = " ".join(left_text.split()[1:])
            body_lines = [" ".join(word[4] for word in words if word[0] >= body_left)
                          for words in lines[start:stop]]
            abstract = " ".join(part for part in body_lines if part)
            abstract = re.sub(r"-\s+(?=[a-z])", "", abstract)
            date = parsed_date(left_text)
            location = next((place for line in body_lines[:2] if (place := parsed_location(line))), None)
            traces, patterns = trace_tags(abstract)
            lowered = abstract.lower()
            if page >= INSUFFICIENT_FIRST_PAGE:
                kind = "insufficient"
            elif traces and NO_SIGHTING.search(lowered):
                kind = "trace_discovery"
            elif traces and SIGHTING.search(lowered) and OBJECT.search(lowered):
                kind = "sighting_trace"
            else:
                kind = "unclear"
            if not abstract.strip():
                continue
            row = {
                "id": number, "page": page, "date": date, "location": location, "kind": kind,
                "traces": traces, "patterns": patterns,
                "media": [name for code, name in [("p", "photo"), ("s", "sketch")] if code in match[2]],
                "verification": "ocr_agreement" if corroborated else "ocr_candidate",
            }
            score = (
                number in VERIFIED_PAGES,
                corroborated,
                match[1].isdigit(),
                bool(location),
                bool(date),
                start < i or page >= INSUFFICIENT_FIRST_PAGE,
                run == 2,
            )
            by_number.setdefault(number, []).append((score, row))
    return by_number


def direct_references(path):
    """Read exact direct case-number references, never indirect or other Phillips works."""
    refs = defaultdict(list)
    if not path:
        return refs
    source = json.loads(path.read_text(encoding="utf-8-sig"))
    if source["schemaId"] != "ufo-timeline-phillips-source-index-v1":
        raise ValueError("UFOCAT source index has an unexpected schema")
    for row in source["records"]:
        for cite in row["citations"]:
            case = cite.get("catalogCaseId")
            if (cite["sourceCode"] == "TPhillips1" and cite["citationRole"] == "direct"
                    and cite.get("locatorType") == "catalog_case_number" and case and case.isdecimal()
                    and 1 <= int(case) <= DECLARED_COUNT):
                refs[int(case)].append(row)
    return refs


def reference_fields(rows):
    dates = set()
    places = set()
    countries = {"US": "United States", "CN": "Canada"}
    for row in rows:
        date = row["date"]
        year, month, day = (date.get(field) or "" for field in ("yearRaw", "monthRaw", "dayRaw"))
        if year.isdecimal() and 1000 <= int(year) <= 1975:
            pieces = [year]
            if month.isdecimal() and 1 <= int(month) <= 12:
                pieces.append(month.zfill(2))
                if day.isdecimal():
                    try:
                        datetime.date(int(year), int(month), int(day))
                        pieces.append(day.zfill(2))
                    except ValueError:
                        pass
            dates.add("-".join(pieces))
        location = row["location"]
        locality = location.get("locality") or ""
        state = location.get("state") or ""
        country = countries.get(location.get("region"))
        if locality:
            places.add(", ".join(part for part in (locality.title(), state, country) if part))
    return (next(iter(dates)) if len(dates) == 1 else None,
            next(iter(places)) if len(places) == 1 else None)


def reference_agreement(row, refs):
    for ref in refs:
        ref_year = ref["date"].get("yearRaw")
        locality = ref["location"].get("locality")
        if (row["date"] and row["date"][:4] == ref_year and row["location"] and locality
                and row["location"].casefold().startswith(locality.casefold())):
            return True
    return False


def build_inventory(pages, left_pages, digest, references, reference_hash):
    rows = []
    ambiguous = []
    candidates = extract_candidates(pages, left_pages)
    for number in sorted(candidates.keys() | REVIEWED_ROWS.keys() | references.keys()):
        matches = candidates.get(number, [])
        if number in REVIEWED_ROWS:
            date, location, kind, traces, patterns = REVIEWED_ROWS[number]
            rows.append({
                "id": number, "page": VERIFIED_PAGES[number], "date": date, "location": location,
                "kind": kind, "traces": traces, "patterns": patterns, "media": REVIEWED_MEDIA.get(number, []),
                "verification": "scan_reviewed",
            })
            continue
        refs = references.get(number, [])
        scored = [((score[0], reference_agreement(row, refs), *score[1:]), row) for score, row in matches]
        best_score = max((score for score, _ in scored), default=None)
        best = [row for score, row in scored if score == best_score]
        if len(best) == 1:
            rows.append(best[0])
            continue
        if len(best) > 1:
            ambiguous.append(number)
        if refs:
            date, location = reference_fields(refs)
            rows.append({
                "id": number, "page": None, "date": date, "location": location, "kind": "unclear",
                "traces": [], "patterns": [], "media": [], "verification": "ufocat_direct",
            })
    linked = sum(row["page"] is not None for row in rows)
    return {
        "source": {
            "label": "Ted Phillips, Physical Traces Associated with UFO Sightings (CUFOS, 1975)",
            "url": CATALOG_URL,
            "sha256": digest,
            "declaredCount": DECLARED_COUNT,
            "declaredCategories": {"sighting_trace": 561, "trace_discovery": 154, "insufficient": 116},
            "methods": "Page-linked metadata uses scan OCR or visual review. Category, trace and layout tags from OCR are screening cues. Entries linked by UFOCAT alone use only exact direct catalog-number citations, with scan pages and evidence unconfirmed.",
            "ambiguousCount": len(ambiguous),
            "pageLinkedCount": linked,
            "directOnlyCount": len(rows) - linked,
            "referenceIndex": {
                "label": "UFOCAT 2023",
                "url": "https://cufos.org/cufos-publications-databases/ufocat/",
                "sourceCode": "TPhillips1",
                "sourceCodebook": "UFOCAT 2023 Sources.xlsx, Sheet1, row 749",
                "sha256": reference_hash,
            } if reference_hash else None,
        },
        "rows": rows,
    }


def write_asset(path, payload):
    header = "// Generated by scripts/build_phillips_landing_inventory.py. Factual metadata only.\n"
    wrapper = "(function (root, catalog) {\n  \"use strict\";\n  if (typeof module === \"object\" && module.exports) module.exports = catalog;\n  root.UfoLandingSitePhillipsCatalog = catalog;\n})(globalThis, "
    source = json.dumps(payload["source"], ensure_ascii=False, separators=(",", ": "))
    records = ",\n".join("    " + json.dumps(row, ensure_ascii=False, separators=(",", ": "))
                        for row in payload["rows"])
    data = '{\n  "source": ' + source + ',\n  "rows": [\n' + records + "\n  ]\n}"
    path.write_text(header + wrapper + data + ");\n", encoding="utf-8", newline="\n")


def read_pages(source, renderer, tesseract, workers, digest, cache, left_only):
    if cache and cache.exists():
        cached = json.loads(cache.read_text(encoding="utf-8"))
        if cached["sha256"] != digest or cached["dpi"] != DPI or bool(cached.get("leftOnly")) != left_only:
            raise ValueError("OCR cache does not match this source and pass")
        return cached["pages"]
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(read_page, source, renderer, tesseract, page, left_only)
            for page in range(CATALOG_FIRST_PAGE, CATALOG_LAST_PAGE + 1)
        ]
        pages = {}
        for done in concurrent.futures.as_completed(futures):
            page, lines = done.result()
            pages[str(page)] = lines
            if len(pages) % 20 == 0:
                label = "number-column" if left_only else "full-page"
                print(f"OCR {len(pages)} catalog pages ({label})", flush=True)
    if cache:
        cached = {"sha256": digest, "dpi": DPI, "leftOnly": left_only, "pages": pages}
        cache.write_text(json.dumps(cached, ensure_ascii=False), encoding="utf-8")
    return pages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Local copy of the original CUFOS PDF")
    parser.add_argument("--renderer", default="pdftoppm")
    parser.add_argument("--tesseract", default="tesseract")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--ocr-cache", type=Path, help="Optional private full-page OCR cache")
    parser.add_argument("--left-cache", type=Path, help="Optional private number-column OCR cache")
    parser.add_argument("--ufocat-index", type=Path, help="Optional retained Phillips exact-code citation index")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "landing_site_phillips_catalog.js")
    args = parser.parse_args()

    digest = scan_hash(args.source)
    if digest != CATALOG_SHA256:
        parser.error("Source hash differs from the July 1975 CUFOS scan")
    if args.workers < 1:
        parser.error("--workers must be positive")
    ocr_args = args.source, args.renderer, args.tesseract, args.workers, digest
    pages = read_pages(*ocr_args, args.ocr_cache, left_only=False)
    left_pages = read_pages(*ocr_args, args.left_cache, left_only=True)
    references = direct_references(args.ufocat_index)
    reference_hash = scan_hash(args.ufocat_index) if args.ufocat_index else None
    inventory = build_inventory(pages, left_pages, digest, references, reference_hash)
    write_asset(args.output, inventory)
    print(f"Wrote {len(inventory['rows'])} catalog rows from {len(pages)} PDF pages")


if __name__ == "__main__":
    main()
