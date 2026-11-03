"""Build a supplemental landing-trace lead index from existing local exports.

Read source CSVs in place. Publish only factual metadata, locators and screening
tags. Narratives, names, witness details and precise coordinates stay in the
owning source archives.
"""

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date
import gzip
import hashlib
import json
from pathlib import Path
import re
import unicodedata


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUTS = Path.home() / "Desktop/UFO Timeline map tool/UFO Databases"
UF_CODEBOOK = "https://cufos.org/PDFs/UFOCAT%20Codebook%202023.pdf"
HATCH_URL = "https://rr0.org/udb/index.html"
MAJESTIC_URL = "https://github.com/richgel999/ufo_data"
NARA_URL = "https://www.archives.gov/research/military/air-force/ufos"
SOURCES = {
    "ufocat": ("CUFOS UFOCAT 2023", UF_CODEBOOK),
    "hatch": ("Larry Hatch's *U* Database", HATCH_URL),
    "nuforc": ("National UFO Reporting Center", "https://nuforc.org/databank/"),
    "bluebook": ("Project Blue Book via UPDB", "https://catalog.archives.gov/id/597821"),
    "geipan": ("CNES / GEIPAN case files", "https://www.geipan.fr/fr/recherche/cas"),
    "urecat": ("URECAT via UPDB", "https://ufologie.patrickgross.org/ce3/_full.htm"),
    "specialist": ("Historical trace compilations via UFO Data", MAJESTIC_URL),
}
MAJESTIC_SOURCES = {
    "BerlinerBBUnknowns", "EberhartUFOI", "HallUFOEvidence2", "Johnson", "NICAP_DB",
    "Overmeire", "Trace", "rr0", "ValléeMagonia",
}
SITE = r"(?:ground|soil|earth|grass|vegetation|plants?|crops?|wheat|reeds?|bushes|lawn|field|asphalt|road|snow|sand)"
MARKS = r"(?:imprints?|indentations?|footprints?|depressions?|impressions?|holes?|ruts?|furrows?|tracks?|marks?|traces?|rings?|patch(?:es)?)"
OBJECT = re.compile(r"\b(?:ufo|object|craft|disc|disk|saucer|orb|sphere|light)\b", re.I)
LANDING = re.compile(
    r"\b(?:landed|lands|landing site|landing spot|touch(?:ed|es) down|"
    r"came (?:down|to rest)|rest(?:ed|ing) on (?:the )?ground|"
    r"hover(?:ed|ing) (?:just )?above (?:the )?ground|took off from (?:the )?(?:ground|field))\b",
    re.I,
)
ARRIVAL = re.compile(r"\b(?:found|discovered|left behind|left (?:a|an|the)|showed|examined|investigated)\b", re.I)
NO_SIGHTING = re.compile(r"\b(?:no (?:ufo|object|sighting) (?:was )?(?:seen|reported|observed)|trace discovery)\b", re.I)
NEGATED = re.compile(r"\b(?:no (?:physical |ground |visible )?(?:traces?|marks?|impressions?)|"
                     r"(?:no|not) (?:found|discovered|left|seen)|no damage)\b", re.I)
TAGS = {
    "impression": (
        rf"\b{SITE}\b.{{0,30}}\b{MARKS}\b|\b{MARKS}\b.{{0,26}}\b{SITE}\b|"
        r"\b(?:tripod|landing (?:gear|leg)|support(?: leg| pad))\s+(?:marks?|impressions?|indentations?|holes?)\b"
    ),
    "scorching": (
        rf"\b(?:scorch(?:ed|ing)?|burn(?:ed|t)|charred|singed|blackened)\b.{{0,26}}\b{SITE}\b|"
        rf"\b{SITE}\b.{{0,24}}\b(?:scorch(?:ed|ing)?|burn(?:ed|t)|charred|singed|blackened)\b"
    ),
    "deformation": (
        rf"\b(?:flattened|bent|twisted|matted|uprooted|pressed down|swirled|lay flat)\b.{{0,24}}\b{SITE}\b|"
        rf"\b{SITE}\b.{{0,24}}\b(?:flattened|bent|twisted|matted|uprooted|pressed down|swirled|lay flat)\b"
    ),
    "surface": (
        rf"\b(?:discolou?red|withered|dried|melted|residue|deposits?)\b.{{0,23}}\b{SITE}\b|"
        rf"\b{SITE}\b.{{0,23}}\b(?:discolou?red|withered|dried|melted|residue|deposits?)\b"
    ),
}
# A geometry word must directly modify the trace feature, rather than the object.
LAYOUTS = {
    "circular": "circular|concentric|elliptical|oval|round|rings?|circles?",
    "triangular": "triangular|triangles?",
    "linear": "line of|rows? of|parallel",
    "rectangular": "rectangular|rectangle|square|quadrilateral",
    "radial": "radial|radiating|spokes?",
    "swirl": "spiral|swirl(?:ed|ing)?|clockwise|counterclockwise|anti-clockwise",
}
TRACE_PATTERNS = {key: re.compile(value, re.I) for key, value in TAGS.items()}
LAYOUT_PATTERNS = {
    key: re.compile(rf"\b(?:{value})\s+(?:(?:shaped|ground|burn|scorch|soil|grass|crop|trace|pattern)\s+){{0,2}}"
                    rf"(?:{MARKS}|{SITE}|patterns?)\b|\b{MARKS}\s+(?:(?:in|into|formed|forming|of)\s+){{1,2}}"
                    rf"(?:an?\s+)?(?:{value})\b", re.I)
    for key, value in LAYOUTS.items()
}
KNOWN_UNSUITABLE = re.compile(
    r"\b(?:emergency (?:airplane |aircraft )?landing|rocket landing|crop circles? (?:hoax|artist)|"
    r"aircraft accident|spacecraft recovery|landing lights?)\b", re.I
)
PHILLIPS_REFERENCE = re.compile(r"(?:\bted phillips\b|\btphillips\w*\b|physical traces associated with ufo sightings)", re.I)
TOKENS = re.compile(r"[a-z0-9]+")
REGIONS = {
    "AU": "Australia", "CA": "Canada", "US": "United States",
    "CAN": "Canada", "UK": "United Kingdom", "GB": "United Kingdom", "NZ": "New Zealand",
}
UPDB_COLLECTIONS = {"7": "bluebook", "8": "urecat"}
# NARA file unit identified by title, place and month via the Encounter Atlas
# catalog concordance: https://encounteratlas.com/datasets/
BLUE_BOOK_FILES = {
    "BB-10872": ("Donnybrook, North Dakota, United States", "https://catalog.archives.gov/id/302554913"),
}


def normalize(value):
    return " ".join((value or "").strip().split())


def iso_date(value, month=None, day=None):
    if month is not None:
        parts = [value, month, day]
    else:
        source = value.strip()
        iso = re.match(r"^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?(?:\b|$)", source)
        if iso:
            parts = list(iso.groups())
        else:
            legacy = re.fullmatch(r"(\d{1,2})/(?:(\d{1,2})/)?(\d{4})", source)
            if not legacy:
                return None
            mm, dd, yyyy = legacy.groups()
            parts = [yyyy, mm, dd]
    year, month, day = [(str(part).strip() if part is not None else "") for part in parts]
    if not year.isdigit() or len(year) != 4 or not 1000 <= int(year) <= 2026:
        return None
    if not month.isdigit() or not 1 <= int(month) <= 12:
        return year
    prefix = f"{year}-{int(month):02d}"
    if not day.isdigit() or int(day) == 0:
        return prefix
    try:
        return date(int(year), int(month), int(day)).isoformat()
    except ValueError:
        return prefix


def public_location(*parts):
    cleaned = []
    for value in parts:
        value = normalize(value)
        # Publish locality-level labels only. Exclude source fields containing
        # house numbers, map coordinates, URLs or common private-address cues.
        if (not value or len(value) > 90 or re.search(r"\d|https?[:/]|@|\b(?:street|road|avenue|"
                r"lane|drive|court|highway|intersection|mile marker|route)\b", value, re.I)):
            continue
        value = REGIONS.get(value.upper(), value)
        if value.isupper() and len(value) > 3:
            value = value.title()
        if value.casefold() not in {item.casefold() for item in cleaned}:
            cleaned.append(value)
    return ", ".join(cleaned) or None


def describe(text, structured=False):
    """Screen trace language in clauses. Preserve ambiguity rather than adjudicating a case."""
    if not text or KNOWN_UNSUITABLE.search(text):
        return None
    # Match the landing context in the full source note but match individual
    # traces within a clause. Clean whitespace without including a republished excerpt.
    landing = bool(LANDING.search(text) and OBJECT.search(text))
    if not (landing or structured):
        return None
    traces = set()
    layouts = set()
    for clause in re.split(r"(?<=[.!?;])\s+|[\r\n]+", text):
        clause = normalize(clause)
        if NEGATED.search(clause):
            continue
        clause_tags = [key for key, pattern in TRACE_PATTERNS.items() if pattern.search(clause)]
        if not clause_tags:
            continue
        if not (landing or ARRIVAL.search(clause) or structured):
            continue
        # Generic marks, ordinary animal tracks and shoe prints do not by
        # themselves support the impressions screening lane.
        if "impression" in clause_tags and re.search(
                r"\b(?:cat|dog|animal|horse|boot|shoe|tire|tyre) (?:tracks?|prints?)\b", clause, re.I):
            clause_tags.remove("impression")
        if ("impression" in clause_tags and not re.search(
                r"\b(?:imprints?|indentations?|footprints?|depressions?|impressions?|holes?|ruts?|furrows?|tripod|"
                r"landing (?:gear|leg)|support (?:pad|leg)|ground marks?|tracks?)\b", clause, re.I)):
            clause_tags.remove("impression")
        if not clause_tags:
            continue
        traces.update(clause_tags)
        layouts.update(key for key, pattern in LAYOUT_PATTERNS.items() if pattern.search(clause))
    if not traces:
        return None
    kind = "trace_discovery" if NO_SIGHTING.search(text) else "sighting_trace" if landing else "unclear"
    return kind, [key for key in TAGS if key in traces], [key for key in LAYOUTS if key in layouts]


def source_ref(key, locator, url=None, label=None):
    name, fallback = SOURCES[key]
    return {"key": key, "label": label or name, "url": url or fallback, "locator": locator}


def row_record(key, ident, date_value, location, source, description, code=None):
    kind, traces, patterns = description or ("unclear", [], [])
    result = {"id": f"{key}:{ident}", "date": date_value, "location": location, "kind": kind,
              "traces": traces, "patterns": patterns, "media": [], "source": source,
              "evidenceBasis": "described_trace" if description else "classification_only",
              "duplicateStatus": "unresolved"}
    if code:
        result["classification"] = code
    return result


def csv_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        yield from enumerate(csv.DictReader(stream), 2)


def review_index(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        data = json.load(stream)
    return {
        str(member["source_native_id"])
        for event in data["events"].values() for member in event["sourceRecords"]
    }


def ufocat_rows(path, phillips_members, coverage):
    for number, raw in csv_rows(path):
        coverage["scanned"] += 1
        ident = raw["PRN"].strip()
        if not ident.isdigit():
            continue
        code = raw["TYPE"].strip().upper()
        # The CUFOS codebook defines 6 as landing and carries Type 5 trace
        # subtypes forward. TT is ground marks even under encounter Type 5.
        code_lead = bool(re.fullmatch(r"6(?:T|TT)", code) or code in {"5TT", "7TT", "8TT"})
        text = raw["NOTES"]
        description = describe(text, structured=code_lead)
        if not (description or code_lead):
            continue
        refs = " ".join(raw[name] for name in ("SOURCE", "ISOURCE"))
        if ident in phillips_members or PHILLIPS_REFERENCE.search(refs):
            coverage["excludedPhillipsLineage"] += 1
            continue
        if not description and (NEGATED.search(text) or KNOWN_UNSUITABLE.search(text)):
            coverage["excludedExplicitlyInapplicable"] += 1
            continue
        loc = public_location(raw["LOCATION"], raw["STATE"], raw["REGION"])
        if not loc and not raw["YEAR"].strip():
            coverage["excludedNoDateOrLocation"] += 1
            continue
        base = f"UFOCAT PRN {ident} · CSV row {number}"
        reference = " ".join(normalize(raw[name]) for name in ("SOURCE", "PAGEVOL")).strip()
        locator = base + (f" · {reference}" if reference else "")
        yield row_record("ufocat", ident, iso_date(raw["YEAR"], raw["MO"], raw["DAY"]), loc,
                         source_ref("ufocat", locator, label="CUFOS UFOCAT 2023 codebook"),
                         description, code if code_lead else None)


def majestic_rows(path, coverage):
    for number, raw in csv_rows(path):
        coverage["scanned"] += 1
        family, ident = raw["source"], raw["source_id"]
        if not re.fullmatch(r"[A-Za-z0-9_-]+", ident or ""):
            continue
        if family == "Hatch":
            key = "hatch"
            attrs = {value.split(":", 1)[0] for name, value in raw.items()
                     if name and name.startswith("attributes/") and value}
            has_landing = "LND" in attrs
            has_ground_trace = bool({"TRC", "DRT", "VEG"} & attrs)
            code_lead = has_landing and has_ground_trace
            structured = code_lead or {"TRC", "DRT"} <= attrs
            code = " + ".join(sorted({"LND", "TRC", "DRT", "VEG"} & attrs)) if code_lead else None
        elif family in MAJESTIC_SOURCES:
            key = "specialist"
            code_lead = False
            structured = family == "Trace"
            code = None
        else:
            continue
        text = raw["desc"]
        description = describe(text, structured=structured)
        if not (description or code_lead):
            continue
        refs = " ".join(value for name, value in raw.items() if name and name.startswith("ref/") and value)
        if PHILLIPS_REFERENCE.search(refs):
            coverage["excludedPhillipsLineage"] += 1
            continue
        if not description and (NEGATED.search(text) or KNOWN_UNSUITABLE.search(text)):
            coverage["excludedExplicitlyInapplicable"] += 1
            continue
        loc = public_location(raw["location/0"], raw.get("key_vals/State/Prov"), raw.get("key_vals/Country"))
        date_value = iso_date(raw["date"])
        if not loc and not date_value:
            coverage["excludedNoDateOrLocation"] += 1
            continue
        locator = f"{ident} · UFO Data export row {number}"
        if key == "specialist":
            locator = f"{family} · {locator}"
        yield row_record(key, ident, date_value, loc, source_ref(key, locator), description, code)


def nuforc_rows(path, coverage):
    for number, raw in csv_rows(path):
        coverage["scanned"] += 1
        ident = raw["No"].strip()
        if not ident.isdigit():
            continue
        description = describe(raw["Description"])
        if not description:
            continue
        if PHILLIPS_REFERENCE.search(raw["Description"]):
            coverage["excludedPhillipsLineage"] += 1
            continue
        date_value = iso_date(raw["Occurred"])
        loc = public_location(*raw["Location"].split(","))
        if not loc and not date_value:
            coverage["excludedNoDateOrLocation"] += 1
            continue
        locator = f"NUFORC report {ident} · CSV row {number}"
        yield row_record("nuforc", ident, date_value, loc,
                         source_ref("nuforc", locator, f"https://nuforc.org/sighting/?id={ident}"),
                         description)


def updb_rows(path, coverage):
    for number, raw in csv_rows(path):
        coverage["scanned"] += 1
        key = UPDB_COLLECTIONS.get(raw["source"])
        ident = normalize(raw["source_id"])
        if not key or not re.fullmatch(r"[A-Za-z0-9_-]+", ident):
            continue
        description = describe(raw["description"])
        if not description:
            continue
        if PHILLIPS_REFERENCE.search(raw["description"]):
            coverage["excludedPhillipsLineage"] += 1
            continue
        date_value = iso_date(raw["date"])
        loc = public_location(raw["city"], raw["country"])
        if not loc and not date_value:
            coverage["excludedNoDateOrLocation"] += 1
            continue
        case_file = BLUE_BOOK_FILES.get(ident) if key == "bluebook" else None
        source_url = case_file[1] if case_file else None
        loc = case_file[0] if case_file else loc
        locator = f"{ident} · UPDB export row {number}"
        yield row_record(key, ident, date_value, loc, source_ref(key, locator, source_url), description)


def geipan_rows():
    # The agency's official documents provide the trace wording. Keep locations
    # at community scale and leave conflicting observation dates at month precision.
    rows = [
        ("1978-03-bennecourt", "1978-03", "Bennecourt, Yvelines, France",
         "Re-examination of Bennecourt, pp. 1-3. Header and witness statement differ by one day.",
         "https://www.geipan.fr/sites/default/files/Compte%20rendu%20enquete2.pdf",
         "sighting_trace", ["impression", "deformation"], ["circular"]),
        ("79-06", "1979-11-27", "Porcieu-Amblagnieu, Isère, France",
         "GEPAN 79/06, technical note 8, chap. 4 and §6.1.2",
         "https://www.geipan.fr/sites/default/files/note_tech_8.pdf",
         "sighting_trace", ["deformation"], ["swirl"]),
        ("81-07", "1981-06-12", "France (site anonymized in source)",
         "GEPAN 81/07, technical note 12, §1.2 and §§2.3–2.6",
         "https://www.geipan.fr/sites/default/files/note_tech_12.pdf",
         "trace_discovery", ["deformation", "surface"], ["circular"]),
        ("1982-10-amarante", "1982-10-21", "Nancy area, France",
         "L'Amarante, GEPAN technical note 17, §VII.1",
         "https://www.geipan.fr/sites/default/files/note_tech_17.pdf",
         "sighting_trace", ["deformation", "surface"], []),
    ]
    for ident, when, where, locator, url, kind, traces, layouts in rows:
        yield row_record("geipan", ident, when, where, source_ref("geipan", locator, url),
                         (kind, traces, layouts))


def likely_key(date_value, loc):
    if not (date_value and len(date_value) == 10 and loc):
        return None
    city = unicodedata.normalize("NFKD", loc.split(",")[0]).lower()
    city = "".join(char for char in city if not unicodedata.combining(char))
    return date_value, " ".join(TOKENS.findall(city))


def index_phillips(path):
    text = path.read_text(encoding="utf-8")
    payload = text.split("})(globalThis,", 1)[1].lstrip()
    data, _ = json.JSONDecoder().raw_decode(payload)
    return {key for row in data["rows"] if (key := likely_key(row.get("date"), row.get("location")))}


def build(input_dir, phillips_asset, citation_sidecar):
    records = {}
    coverage = {}
    inputs = {}
    phillips_members = review_index(citation_sidecar)
    streams = [
        ("ufocat2023.csv", lambda path, counts: ufocat_rows(path, phillips_members, counts)),
        ("majestic.csv", majestic_rows),
        ("nuforc.csv", nuforc_rows),
        ("phenomenAInon_UPDB.csv", updb_rows),
    ]
    for name, generator in streams:
        path = input_dir / name
        counts = Counter()
        for row in generator(path, counts):
            ident = row["id"]
            previous = records.get(ident)
            if previous is not None:
                counts["excludedDuplicateNativeId"] += 1
                if previous["evidenceBasis"] == "described_trace":
                    continue
            records[ident] = row
        coverage[name] = dict(counts)
        with path.open("rb") as stream:
            inputs[name] = {"bytes": path.stat().st_size, "sha256": hashlib.file_digest(stream, "sha256").hexdigest()}
    records.update({row["id"]: row for row in geipan_rows()})
    matches = defaultdict(list)
    for row in records.values():
        key = likely_key(row["date"], row["location"])
        if key:
            matches[key].append(row)
    phillips_keys = index_phillips(phillips_asset)
    for key, same_site in matches.items():
        if key in phillips_keys or len(same_site) > 1:
            for row in same_site:
                row["duplicateStatus"] = "possible_overlap"
    rows = sorted(records.values(), key=lambda row: (row["date"] or "9999", row["id"]))
    source_counts = Counter(row["source"]["key"] for row in rows)
    basis_counts = Counter(row["evidenceBasis"] for row in rows)
    methods = (
        "A bounded screening pass over existing UFOCAT, Hatch and historical UFO Data exports, "
        "NUFORC reports and the Blue Book and URECAT subsets in UPDB, plus four GEIPAN source files. Narrative-screened rows are "
        "keyword leads for ground or vegetation traces in a landing context or a trace-classified "
        "record. Classification-only rows retain narrow UFOCAT landing/ground-mark codes or Hatch "
        "landing plus trace flags. The index excludes explicit Phillips citations and repeated "
        "source-native IDs. An exact reported day and matching locality flag possible overlap. "
        "Counts describe source records and include unresolved duplicates and unreviewed reports."
    )
    overlap_inputs = {path.name: {"bytes": path.stat().st_size,
                                 "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                      for path in (phillips_asset, citation_sidecar)}
    return {"source": {"label": "Additional landing-trace leads", "url": NARA_URL, "methods": methods,
                       "declaredCount": len(rows), "counts": {"bySource": dict(source_counts),
                       "byEvidenceBasis": dict(basis_counts),
                       "possibleOverlap": sum(row["duplicateStatus"] == "possible_overlap" for row in rows)},
                       "coverage": coverage, "inputPins": inputs,
                       "overlapInputPins": overlap_inputs}, "rows": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, default=DEFAULT_INPUTS)
    parser.add_argument("--phillips", type=Path, default=ROOT / "landing_site_phillips_catalog.js")
    parser.add_argument("--citations", type=Path, default=ROOT / "data/source_citations/phillips.json.gz")
    parser.add_argument("--output", type=Path, default=ROOT / "landing_site_other_catalog.js")
    args = parser.parse_args()
    payload = build(args.inputs, args.phillips, args.citations)
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    args.output.write_text(
        "// Generated by scripts/build_other_landing_inventory.py.\n"
        "(function (root) {\n"
        '  "use strict";\n'
        f"  const catalog = {encoded};\n"
        '  if (typeof module === "object" && module.exports) module.exports = catalog;\n'
        "  root.UfoLandingSiteOtherCatalog = catalog;\n"
        "})(globalThis);\n",
        encoding="utf-8", newline="\n",
    )
    print(json.dumps(payload["source"], indent=2))


if __name__ == "__main__":
    main()
