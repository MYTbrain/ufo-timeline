"""Audit a pinned third-party transcription as private discovery metadata only.

Never executes the downloaded scraper, invents event dates from page years,
deduplicates incidents by HC number, or classifies Type G as abduction.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date
import hashlib
import json
from pathlib import Path
import re

MONTHS = {name.lower(): i for i, name in enumerate(("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"), 1)}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def date_fields(raw):
    """Accept only unqualified complete civil dates or explicit month/year units."""
    text = re.sub(r"\s+", " ", str(raw or "")).strip()
    base = {"dateRaw": text, "dateIso": None, "datePrecision": "unknown"}
    if re.search(r"\b(?:BC|BCE)\b", text, re.I):
        return {**base, "datePrecision": "historical_bce", "dateParseStatus": "held_historical_calendar"}
    clean = re.sub(r"\s+(?:AD|CE)$", "", text, flags=re.I).replace(",", "")
    tokens = clean.split()
    try:
        if re.fullmatch(r"\d{4}", clean):
            y = int(clean)
            date(y, 1, 1)
            return {**base, "dateIso": f"{y:04d}", "datePrecision": "year", "dateParseStatus": "explicit_year_only"}
        if len(tokens) == 2 and tokens[0].lower() in MONTHS and re.fullmatch(r"\d{4}", tokens[1]):
            y, m = int(tokens[1]), MONTHS[tokens[0].lower()]
            date(y, m, 1)
            return {**base, "dateIso": f"{y:04d}-{m:02d}", "datePrecision": "month", "dateParseStatus": "explicit_month_only"}
        if len(tokens) == 3 and re.fullmatch(r"\d{4}", tokens[2]):
            if tokens[0].lower() in MONTHS and re.fullmatch(r"\d{1,2}", tokens[1]):
                y, m, d = int(tokens[2]), MONTHS[tokens[0].lower()], int(tokens[1])
            elif tokens[1].lower() in MONTHS and re.fullmatch(r"\d{1,2}", tokens[0]):
                y, m, d = int(tokens[2]), MONTHS[tokens[1].lower()], int(tokens[0])
            else:
                raise ValueError("unrecognized civil date")
            return {**base, "dateIso": date(y, m, d).isoformat(), "datePrecision": "exact_day", "dateParseStatus": "unqualified_transcribed_civil_date"}
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", clean):
            return {**base, "dateIso": date.fromisoformat(clean).isoformat(), "datePrecision": "exact_day", "dateParseStatus": "unqualified_transcribed_civil_date"}
    except ValueError:
        return {**base, "dateParseStatus": "held_invalid_or_unrecognized_date"}
    return {**base, "dateParseStatus": "held_qualifier_range_season_or_unknown"}


def archive_map(text):
    current, result = {}, {}
    for line in text.splitlines():
        m = re.search(r"Fetching (ancient|\d{4}) from (https://web\.archive\.org/web/\d{14}/http://www\.ufoinfo\.com/humanoid/humanoid(?:ancient|\d{4})\.shtml)", line)
        if m:
            current[m[1]] = m[2]
        m = re.search(r"Parsed (\d+) entries from page (ancient|\d{4})", line)
        if m and int(m[1]) and m[2] in current:
            result[m[2]] = {"url": current[m[2]], "transcriberReportedRows": int(m[1])}
    return result


def normalize(rows, *, csv_sha, archives):
    rows = list(rows)
    key_counts = Counter((r["year_page"], r["entry_number"]) for r in rows)
    hc_groups = defaultdict(list)
    for index, row in enumerate(rows, 1):
        if row["hc_number"].isdigit():
            hc_groups[row["hc_number"]].append(index)
    records = []
    for ordinal, row in enumerate(rows, 1):
        canonical = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        flags = ["third_party_transcription_not_original", "not_approved_for_public_redistribution", "no_accepted_incident_identity"]
        hc = row["hc_number"].strip()
        ids = []
        if hc.isdigit():
            ids.append({"scheme": "rosales_hc", "value": hc})
            if len(hc_groups[hc]) > 1:
                flags.append("nonunique_hc_key_requires_independent_identity")
        else:
            flags.append("no_numeric_hc_key")
        if key_counts[(row["year_page"], row["entry_number"])] > 1:
            flags.append("repeated_page_entry_number_not_incident_identity")
        if row["type_code"]:
            flags.append("type_qualifiers_and_combined_codes_may_be_lost")
        if not row["description"].strip():
            flags.append("blank_transcribed_narrative")
        if not row["source"].strip():
            flags.append("blank_transcribed_citation")
        records.append({
            "sourceEntryId": f"rosales-transcription:{csv_sha[:12]}:{ordinal:05d}",
            "sourceUrl": f"http://www.ufoinfo.com/humanoid/humanoid{row['year_page']}.shtml",
            "archiveSource": archives.get(row["year_page"]),
            "transcriptionRow": ordinal, "transcriptionRowSha256": sha(canonical),
            "yearPageRaw": row["year_page"], "entryNumberRaw": row["entry_number"],
            **date_fields(row["date"]), "locationRaw": row["location"], "timeRaw": row["time"],
            "sourceCaseIds": ids, "hcNumberRaw": row["hc_number"],
            "typeCodeTranscribed": row["type_code"], "sourceCitationTranscribed": row["source"],
            "narrativeSha256": sha(row["description"].encode()),
            "narrativeCharacters": len(row["description"]),
            "qualityFlags": flags, "status": "held_discovery_only",
        })
    counts = {
        "transcriptionRows": len(rows), "distinctYearPages": len({r["year_page"] for r in rows}),
        "uniqueRowHashes": len({r["transcriptionRowSha256"] for r in records}),
        "repeatedPageEntryKeyGroups": sum(n > 1 for n in key_counts.values()),
        "extraRowsWithRepeatedPageEntryKeys": sum(n - 1 for n in key_counts.values()),
        "numericHcRows": sum(len(v) for v in hc_groups.values()), "uniqueNumericHcValues": len(hc_groups),
        "nonuniqueHcGroups": sum(len(v) > 1 for v in hc_groups.values()),
        "extraRowsWithNonuniqueHcKeys": sum(len(v) - 1 for v in hc_groups.values()),
        "datePrecision": dict(Counter(r["datePrecision"] for r in records)),
        "typeCodeTranscribed": dict(Counter(r["type_code"] for r in rows)),
        "blankFields": {field: sum(not r[field].strip() for r in rows) for field in rows[0]},
        "acceptedIdentityLinks": 0, "runtimeAdditions": 0,
    }
    return {"schemaId": "ufo-rosales-transcription-candidates-v1", "records": records, "counts": counts,
            "policy": "Private discovery only. No row is accepted as a new incident or abduction. Type definitions in third-party README are not authoritative. Original/source dates, HC collisions, combined and uncertain codes require review."}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--research", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    if args.output.exists():
        raise SystemExit("Protected normalization output exists; no overwrite")
    manifest = json.loads((args.research / "capture_manifest.json").read_text(encoding="utf-8"))
    sources = {r["sourceId"]: r for r in manifest["sources"]}
    for key in ("ufolio_rosales", "ufolio_scrape_log"):
        row = sources[key]
        if row["status"] != "captured" or sha(Path(row["path"]).read_bytes()) != row["sha256"]:
            raise ValueError("Source pin mismatch: " + key)
    with Path(sources["ufolio_rosales"]["path"]).open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    result = normalize(rows, csv_sha=sources["ufolio_rosales"]["sha256"], archives=archive_map(Path(sources["ufolio_scrape_log"]["path"]).read_text(encoding="utf-8")))
    result["inputs"] = [sources[k] for k in ("ufolio_rosales", "ufolio_scrape_log")]
    result["builderSha256"] = sha(Path(__file__).read_bytes())
    raw = (json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    if len(raw) > 18 * 1024 * 1024:
        raise ValueError("Private normalization cap exceeded")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as f:
        f.write(raw)
    print(json.dumps({"output": str(args.output), "bytes": len(raw), "sha256": sha(raw), "counts": result["counts"]}))


if __name__ == "__main__":
    main()
