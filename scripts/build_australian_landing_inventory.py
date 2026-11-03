"""Extract factual entry metadata from Basterfield's Australian physical trace catalog."""
from __future__ import annotations

import argparse
from datetime import date
from hashlib import sha256
from html import unescape
import json
from pathlib import Path
import re


URL = "https://www.project1947.com/kbcat/kbtrace0505.htm"
STATE = re.compile(r"\b(NSW|QLD|VIC|TAS|SA|WA|NT|ACT)\b", re.I)
DATE = re.compile(r"(?:(\d{1,2})\s+)?([A-Za-z]{3,9})?\s*(\d{4}|\d{2})$")
MONTHS = {month: index for index, month in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}
TAGS = {
    "impression": r"\b(?:indentations?|depressions?|imprints?|holes?|furrows?|footprints?)\b",
    "scorching": r"\b(?:scorch(?:ed|ing)?|burnt|burned|charred)\b",
    "deformation": r"\b(?:flattened|swirl(?:ed|ing)?|bent|twisted|matted|uprooted)\b",
    "surface": r"\b(?:discolou?r(?:ed|ation)?|bare (?:earth|soil)|slime|residue|withered|dry ring)\b",
}
LAYOUTS = {
    "circular": r"\b(?:rings?|circles?|circular|annular|round patch)\b",
    "triangular": r"\b(?:triangle|triangular)\b",
    "linear": r"\b(?:parallel|straight line|row of)\b",
    "rectangular": r"\b(?:rectangular|square (?:of|patch|area))\b",
    "radial": r"\b(?:radial|radiating)\b",
    "swirl": r"\b(?:swirl(?:ed|ing)?|twisted|anti-clockwise|counterclockwise|clockwise)\b",
}
CODES = {
    "R": ("surface", "circular"), "DR": ("surface", "circular"),
    "FSA": ("deformation", "swirl"), "FA": ("deformation", None),
    "BEC": ("surface", "circular"), "SL": ("surface", None),
    "WV": ("surface", None), "BS": ("scorching", "circular"),
}


def plain(fragment: str) -> str:
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def header_fields(heading: str) -> tuple[str | None, str]:
    state = STATE.search(heading)
    if not state:
        return None, heading
    prefix = heading[:state.start()].strip(" ,")
    year = re.search(r"\b(?:19|20)\d{2}(?:/\d{2,4})?\b|(?<=[A-Za-z] )\d{2}\b", prefix)
    if not year:
        return None, f"{prefix}, {state[0].upper()}, Australia"
    date_text = prefix[:year.end()]
    place = prefix[year.end():].strip(" ,")
    location = f"{place}, {state[0].upper()}, Australia"
    if "/" in date_text:
        return None, location
    match = DATE.search(date_text)
    if not match:
        return None, location
    day, month, year_text = match.groups()
    year_value = int(year_text) + (1900 if len(year_text) == 2 else 0)
    month_value = MONTHS.get(month[:3].lower()) if month else None
    if month_value and day and not re.match(r"^(?:ca\.?|early|late|mid|end)\b", date_text, re.I):
        return date(year_value, month_value, int(day)).isoformat(), location
    if month_value:
        return f"{year_value:04d}-{month_value:02d}", location
    return f"{year_value:04d}", location


def build(raw: bytes) -> dict:
    source = raw.decode("cp1252")
    headers = list(re.finditer(r'<div class="sub">(.*?)</div>', source, re.I | re.S))
    if len(headers) != 153:
        raise ValueError("Expected the 153-entry May 2005 edition")
    rows = []
    for index, header in enumerate(headers, 1):
        heading = plain(header[1])
        end = headers[index].start() if index < len(headers) else len(source)
        body = re.search(r'<div class="txt">(.*?)</div>', source[header.end():end], re.I | re.S)
        text = plain(body[1]) if body else ""
        if not text:
            raise ValueError(f"Missing report text for catalog entry {index}")
        trace_hits = [kind for kind, pattern in TAGS.items() if re.search(pattern, text, re.I)]
        layouts = [kind for kind, pattern in LAYOUTS.items() if re.search(pattern, text, re.I)] if trace_hits else []
        reported_date, location = header_fields(heading)
        state = STATE.search(heading)
        codes = heading[state.end():].split("(")[0] if state else ""
        tagged = list(trace_hits)
        for code, (kind, layout) in CODES.items():
            if re.search(r"\b" + code + r"\b", codes):
                if kind not in tagged:
                    tagged.append(kind)
                if layout and layout not in layouts:
                    layouts.append(layout)
        rows.append({
            "id": f"basterfield:{index}", "date": reported_date, "location": location,
            "kind": "unclear", "traces": tagged, "patterns": layouts, "media": [],
            "evidenceBasis": "described_trace" if trace_hits else "classification_only" if tagged else "catalog_only",
            "source": {"key": "basterfield", "label": "Basterfield Australian trace catalog",
                       "url": URL, "locator": heading},
        })
    return {
        "source": {"label": "Basterfield Australian physical trace catalog",
                   "url": URL, "sha256": sha256(raw).hexdigest(),
                   "methods": "Screened from the May 2005 catalog headings, trace codes and descriptions."},
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, default=Path("landing_site_australian_catalog.js"))
    args = parser.parse_args()
    payload = build(args.source.read_bytes())
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    args.output.write_text(
        "// Generated by scripts/build_australian_landing_inventory.py. Factual metadata only.\n"
        "(function (root, catalog) {\n"
        '  if (typeof module === "object" && module.exports) module.exports = catalog;\n'
        "  root.UfoLandingSiteAustralianCatalog = catalog;\n"
        f"}})(globalThis, {data});\n", encoding="utf-8", newline="\n")
    print(f"Indexed {len(payload['rows'])} Australian catalog entries")


if __name__ == "__main__":
    main()
