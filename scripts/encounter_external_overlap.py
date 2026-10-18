"""Bounded external encounter discovery against the effective catalog.

Reads shared summary shards in place, one at a time. Every discovered link is
held for review: date/place agreement is not accepted incident identity. Optional
detail inspection adds native citation evidence without retaining descriptions.
No canonical input, runtime asset, or source capture is modified.
"""
from __future__ import annotations

import argparse
import calendar
from collections import Counter, defaultdict
from datetime import date
import gzip
import hashlib
import json
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
SHARED = Path("C:/Users/jarod/Desktop/UFO Timeline map tool")
MAX_OUTPUT_BYTES = 5 * 1024 * 1024
MAX_LINKS_PER_ENTRY = 20
SCHEMA = "ufo-external-encounter-overlap-v1"
COUNTRIES = {
    "usa", "us", "united states", "united states of america", "uk", "united kingdom",
    "england", "scotland", "wales", "france", "spain", "italy", "germany", "russia",
    "ussr", "soviet union", "canada", "australia", "brazil", "argentina", "mexico",
    "portugal", "chile", "peru", "bolivia", "sweden", "norway", "finland", "poland",
    "zimbabwe", "south africa", "japan", "china", "india", "new zealand", "belgium",
}
COUNTRIES.update("afghanistan|albania|algeria|andorra|angola|antigua and barbuda|armenia|austria|azerbaijan|bahamas|bahrain|bangladesh|barbados|belarus|belize|benin|bhutan|bosnia and herzegovina|botswana|brunei|bulgaria|burkina faso|burundi|cabo verde|cambodia|cameroon|central african republic|chad|colombia|comoros|congo|costa rica|croatia|cuba|cyprus|czechia|czech republic|czechoslovakia|democratic republic of the congo|denmark|djibouti|dominica|dominican republic|ecuador|egypt|el salvador|equatorial guinea|eritrea|estonia|eswatini|ethiopia|fiji|gabon|gambia|georgia|ghana|greece|grenada|guatemala|guinea|guinea bissau|guyana|haiti|honduras|hungary|iceland|indonesia|iran|iraq|ireland|israel|ivory coast|jamaica|jordan|kazakhstan|kenya|kiribati|kuwait|kyrgyzstan|laos|latvia|lebanon|lesotho|liberia|libya|liechtenstein|lithuania|luxembourg|madagascar|malawi|malaysia|maldives|mali|malta|marshall islands|mauritania|mauritius|micronesia|moldova|monaco|mongolia|montenegro|morocco|mozambique|myanmar|namibia|nauru|nepal|netherlands|nicaragua|niger|nigeria|north korea|north macedonia|oman|pakistan|palau|palestine|panama|papua new guinea|paraguay|philippines|qatar|romania|rwanda|saint kitts and nevis|saint lucia|saint vincent and the grenadines|samoa|san marino|sao tome and principe|saudi arabia|senegal|serbia|seychelles|sierra leone|singapore|slovakia|slovenia|solomon islands|somalia|south korea|south sudan|sri lanka|sudan|suriname|swaziland|switzerland|syria|taiwan|tajikistan|tanzania|thailand|timor leste|togo|tonga|trinidad and tobago|tunisia|turkey|turkmenistan|tuvalu|uganda|ukraine|united arab emirates|uruguay|uzbekistan|vanuatu|vatican city|venezuela|vietnam|yemen|yugoslavia|zambia".split("|"))
UNUSABLE_PLACES = COUNTRIES | {"unknown", "unspecified", "not known", "undisclosed", "earth", "worldwide", "not given"}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def norm(value):
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def date_interval(row):
    """Return inclusive ordinals using declared precision, never midpoint certainty."""
    precision = str(row.get("datePrecision") or row.get("date_precision") or "unknown").lower()
    raw = str(row.get("dateRaw") or row.get("date_raw") or "")
    if re.search(r"\b(?:bc|bce)\b", raw, re.I) or raw.lstrip().startswith("-"):
        return None
    start = row.get("dateStartIso") or row.get("dateIso") or row.get("date_iso") or row.get("sort_date_iso")
    end = row.get("dateEndIso") or row.get("end_date_iso")
    if not start:
        # A raw year is usable as a year interval, never as January 1.
        match = re.fullmatch(r"(?:c(?:irca)?\.?\s*)?(\d{4})\??", raw.strip(), re.I)
        if not match:
            return None
        start = match.group(1)
        precision = "year"
    match = re.fullmatch(r"(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?", str(start))
    if not match:
        return None
    year, month, day = (int(x) if x else None for x in match.groups())
    if not 1 <= year <= 9999:
        return None
    try:
        if precision in {"year", "approximate_year", "year_only"} or month is None:
            lo, hi = date(year, 1, 1), date(year, 12, 31)
        elif precision in {"month", "month_only"} or day is None:
            lo, hi = date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
        elif precision in {"exact_day", "day", "exact", "date_range", "range"}:
            lo = hi = date(year, month, day)
        else:
            # Unknown/seasonal/approximate midpoint dates are not exact evidence.
            return None
        if end:
            parsed_end = date.fromisoformat(str(end))
            if parsed_end < lo:
                return None
            hi = max(hi, parsed_end)
        return lo.toordinal(), hi.toordinal()
    except (ValueError, TypeError):
        return None


def place_terms(row):
    """Use explicit locality phrases; country-only entries cannot imply identity."""
    text = str(row.get("locationRaw") or row.get("location_raw") or "")
    first = re.split(r"[,;]", text)[0]
    first = re.sub(r"^\s*(?:near|outside|vicinity of|area of|environs of)\s+", "", first, flags=re.I)
    first = re.sub(r"\([^)]*\)", " ", first)
    term = norm(first)
    terms = [term] if len(term) >= 3 and term not in UNUSABLE_PLACES else []
    for alias in row.get("locationAliases") or []:
        candidate = norm(alias)
        if len(candidate) >= 3 and candidate not in UNUSABLE_PLACES and candidate not in terms:
            terms.append(candidate)
    return terms


def normalized_location(summary):
    return " " + norm(" ".join(str(summary.get(k) or "") for k in ("location_raw", "city", "state_province", "country"))) + " "


def matching_terms(terms, normalized_text):
    return [term for term in terms if " " + term + " " in normalized_text]


def location_matches(candidate, summary):
    return matching_terms(place_terms(candidate), normalized_location(summary))


def normalized_ids(ids):
    result = set()
    for item in ids or []:
        scheme = str(item.get("scheme") or "").lower()
        value = str(item.get("value") or "").strip()
        if scheme and value:
            result.add((scheme, str(item.get("year") or ""), value.lstrip("0") or "0"))
    return result


def native_ids(event):
    """Conservative native keys; PRN, IRN and URN are deliberately distinct."""
    raw = event.get("raw_source_row") or event.get("raw_fields") or {}
    ids = []
    if event.get("source") == "ufocat":
        for field, scheme in (("URN", "ufocat_urn"), ("PRN", "ufocat_prn"), ("IRN", "ufocat_irn")):
            value = str(raw.get(field) or "").strip()
            if value.isdigit():
                ids.append({"scheme": scheme, "value": value})
        # Website HC IDs use ARosales01. Book PAGEVOL values are different units.
        for source_field, page_field in (("SOURCE", "PAGEVOL"), ("ISOURCE", "IPAGEVOL")):
            page = str(raw.get(page_field) or "").strip()
            if str(raw.get(source_field) or "").strip().lower() == "arosales01" and page.isdigit():
                ids.append({"scheme": "rosales_hc", "value": page})
    return ids


def overlap(candidates, shards, encounter_ids, *, inspect_details=False, native_citations_all=False, shared=SHARED, expected_count=None):
    candidates = list(candidates)
    seen = [r.get("sourceEntryId") for r in candidates]
    if len(set(seen)) != len(seen) or any(not x for x in seen):
        raise ValueError("Each external entry needs a unique sourceEntryId")
    intervals = [date_interval(r) for r in candidates]
    candidate_place_terms = [place_terms(r) for r in candidates]
    by_year = defaultdict(list)
    for i, interval in enumerate(intervals):
        if interval:
            a, b = (date.fromordinal(x).year for x in interval)
            if b - a > 10:
                continue  # A decades-wide account requires explicit episode review.
            for year in range(a, b + 1):
                by_year[year].append(i)
    results = [{"sourceEntryId": r["sourceEntryId"], "sourceUrl": r.get("sourceUrl"),
                "status": "held_discovery_only", "temporalCandidateCount": 0,
                "locationCandidateCount": 0, "indexedCandidateCount": 0,
                "outsideEncounterIndexCandidateCount": 0, "candidateLinks": [],
                "nativeCitationCandidateCount": 0, "nativeCitationLinks": []} for r in candidates]
    hc_candidates = defaultdict(set)
    for i, candidate in enumerate(candidates):
        for scheme, _, value in normalized_ids(candidate.get("sourceCaseIds")):
            if scheme == "rosales_hc":
                hc_candidates[value].add(i)
    pins = []
    report_ids = set()
    total = 0
    for item in shards:
        path = Path(item["source"])
        raw = path.read_bytes()
        actual_sha = sha(raw)
        if actual_sha != item["sha256"] or len(raw) != item["bytes"]:
            raise ValueError("Summary input pin mismatch: " + str(path))
        pins.append({k: item[k] for k in ("key", "source", "bytes", "sha256")})
        rows = json.loads(gzip.decompress(raw))
        for row in rows:
            total += 1
            interval = date_interval(row)
            if not interval:
                continue
            a, b = (date.fromordinal(x).year for x in interval)
            possible = set()
            for year in range(a, min(b, a + 10) + 1):
                possible.update(by_year.get(year, ()))
            normalized_row_location = None
            for i in possible:
                other = intervals[i]
                if interval[0] > other[1] or other[0] > interval[1]:
                    continue
                result = results[i]
                result["temporalCandidateCount"] += 1
                if not candidate_place_terms[i]:
                    continue
                if normalized_row_location is None:
                    normalized_row_location = normalized_location(row)
                terms = matching_terms(candidate_place_terms[i], normalized_row_location)
                if not terms:
                    continue
                event_id = str(row["event_id"])
                indexed = event_id in encounter_ids
                result["locationCandidateCount"] += 1
                result["indexedCandidateCount"] += int(indexed)
                result["outsideEncounterIndexCandidateCount"] += int(not indexed)
                report_ids.add(event_id)
                link = {"eventId": event_id, "source": row["source"],
                        "dateRaw": row.get("date_raw"), "datePrecision": row.get("date_precision"),
                        "locationRaw": row.get("location_raw"), "inEncounterIndex": indexed,
                        "sourceRef": {"chunk": row["chunk_id"], "detailIndex": row["detail_index"]},
                        "basis": ["date_interval_overlap", "explicit_locality_phrase"],
                        "locationTerms": terms, "status": "held_discovery_only"}
                if len(result["candidateLinks"]) < MAX_LINKS_PER_ENTRY:
                    result["candidateLinks"].append(link)
        del rows, raw
    if expected_count is not None and total != expected_count:
        raise ValueError(f"Catalog count mismatch: {total} != {expected_count}")
    detail_pins = []
    native_report_ids = set()
    native_rows_scanned = 0
    rosales_citation_audit = {"reportsWithRosalesCitation": 0, "reportsWithNativeWebsiteHc": 0,
                              "primarySourceCodes": Counter(), "intermediateSourceCodes": Counter()}
    if inspect_details or native_citations_all:
        needed = defaultdict(list)
        for i, result in enumerate(results):
            for link in result["candidateLinks"]:
                needed[link["sourceRef"]["chunk"]].append((i, link))
        if native_citations_all:
            for path in (Path(shared) / "data/canonical_web/event_chunks").glob("chunk_*.json"):
                needed.setdefault(path.stem, [])
        for chunk, links in sorted(needed.items()):
            path = Path(shared) / "data/canonical_web/event_chunks" / (chunk + ".json")
            raw = path.read_bytes()
            digest = sha(raw)
            rows = json.loads(raw)
            detail_pins.append({"chunk": chunk, "source": str(path), "bytes": len(raw), "sha256": digest})
            for i, link in links:
                row = rows[link["sourceRef"]["detailIndex"]]
                if str(row["event_id"]) != link["eventId"] or row["source"] != link["source"]:
                    raise ValueError("Original identity pin mismatch")
                link["sourceRef"]["chunkSha256"] = digest
                keys = native_ids(row)
                common = normalized_ids(keys) & normalized_ids(candidates[i].get("sourceCaseIds"))
                if common:
                    link["basis"].append("native_citation_key_agreement")
                    link["matchingCitationKeys"] = [{"scheme": s, "year": y or None, "value": v} for s, y, v in sorted(common)]
                link["sourceEventId"] = str(row.get("source_id") or "")
            if native_citations_all:
                for index, row in enumerate(rows):
                    native_rows_scanned += 1
                    keys = native_ids(row)
                    native_hcs = {value for scheme, _, value in normalized_ids(keys) if scheme == "rosales_hc"}
                    raw_fields = row.get("raw_source_row") or row.get("raw_fields") or {}
                    has_rosales_citation = False
                    if row.get("source") == "ufocat":
                        for field, counter in (("SOURCE", "primarySourceCodes"), ("ISOURCE", "intermediateSourceCodes")):
                            source_code = str(raw_fields.get(field) or "").strip()
                            if re.fullmatch(r"ARosales\d+", source_code, re.I):
                                rosales_citation_audit[counter][source_code] += 1
                                has_rosales_citation = True
                    rosales_citation_audit["reportsWithRosalesCitation"] += int(has_rosales_citation)
                    rosales_citation_audit["reportsWithNativeWebsiteHc"] += int(bool(native_hcs))
                    candidate_indexes = set()
                    for value in native_hcs:
                        candidate_indexes.update(hc_candidates.get(value, ()))
                    normalized_row_location = None
                    for i in sorted(candidate_indexes):
                        common = normalized_ids(keys) & normalized_ids(candidates[i].get("sourceCaseIds"))
                        event_id = str(row["event_id"])
                        native_report_ids.add(event_id)
                        result = results[i]
                        result["nativeCitationCandidateCount"] += 1
                        if len(result["nativeCitationLinks"]) >= MAX_LINKS_PER_ENTRY:
                            continue
                        row_interval = date_interval(row)
                        candidate_interval = intervals[i]
                        date_status = "unknown"
                        if row_interval and candidate_interval:
                            date_status = "overlap" if row_interval[0] <= candidate_interval[1] and candidate_interval[0] <= row_interval[1] else "conflict"
                        if normalized_row_location is None:
                            normalized_row_location = normalized_location(row)
                        terms = matching_terms(candidate_place_terms[i], normalized_row_location)
                        result["nativeCitationLinks"].append({
                            "eventId": event_id, "source": row["source"], "sourceEventId": str(row.get("source_id") or ""),
                            "sourceRef": {"chunk": chunk, "detailIndex": index, "chunkSha256": digest},
                            "dateRaw": row.get("date_raw"), "datePrecision": row.get("date_precision"),
                            "locationRaw": row.get("location_raw"), "inEncounterIndex": event_id in encounter_ids,
                            "matchingCitationKeys": [{"scheme": s, "year": y or None, "value": v} for s, y, v in sorted(common)],
                            "dateAgreement": date_status,
                            "locationAgreement": "explicit_locality_phrase" if terms else "not_established",
                            "status": "held_native_citation_review",
                        })
            del rows, raw
        if native_citations_all and expected_count is not None and native_rows_scanned != expected_count:
            raise ValueError(f"Native-scan catalog count mismatch: {native_rows_scanned} != {expected_count}")
    for result, interval in zip(results, intervals):
        result["dateIntervalUsable"] = interval is not None
        result["ambiguous"] = result["locationCandidateCount"] > 1
        result["linksTruncated"] = result["locationCandidateCount"] > len(result["candidateLinks"])
        result["nativeLinksTruncated"] = result["nativeCitationCandidateCount"] > len(result["nativeCitationLinks"])
        result["reviewReason"] = "date_and_place_are_discovery_not_incident_identity" if result["locationCandidateCount"] else "no_location_supported_summary_candidate_is_not_proof_of_novelty"
    counts = {"externalSourceEntries": len(candidates), "catalogReportsScanned": total,
              "entriesWithSummaryCandidates": sum(r["locationCandidateCount"] > 0 for r in results),
              "entriesWithExistingEncounterCandidates": sum(r["indexedCandidateCount"] > 0 for r in results),
              "entriesWithOutsideEncounterIndexCandidates": sum(r["outsideEncounterIndexCandidateCount"] > 0 for r in results),
              "entriesWithoutSummaryCandidate": sum(r["locationCandidateCount"] == 0 for r in results),
              "entriesWithoutUsableDate": sum(x is None for x in intervals),
              "ambiguousEntries": sum(r["ambiguous"] for r in results),
              "candidateReportLinks": sum(r["locationCandidateCount"] for r in results),
              "uniqueCandidateReports": len(report_ids),
              "entriesWithNativeCitationCandidates": sum(r["nativeCitationCandidateCount"] > 0 for r in results),
              "nativeCitationReportLinks": sum(r["nativeCitationCandidateCount"] for r in results),
              "uniqueNativeCitationReports": len(native_report_ids),
              "nativeCatalogReportsScanned": native_rows_scanned,
              "retainedNativeDateConflicts": sum(l["dateAgreement"] == "conflict" for r in results for l in r["nativeCitationLinks"]),
              "truncatedEntries": sum(r["linksTruncated"] for r in results),
              "acceptedIdentityLinks": 0}
    return {"schemaId": SCHEMA, "counts": counts, "summaryPins": pins, "detailPins": detail_pins,
            "rosalesCitationAudit": rosales_citation_audit,
            "maxRetainedLinksPerEntry": MAX_LINKS_PER_ENTRY, "entries": results,
            "policy": {"allLinksHeld": True, "noNewCanonicalReports": True, "runtimeChanged": False,
                       "noNarrativeFulltextRetained": True, "missingMatchDoesNotEstablishNovelty": True,
                       "countsAreSourceEntriesAndCatalogReportsNotVerifiedIncidents": True,
                       "nativeCitationInspectionScope": "entire_corpus_hc_keys_plus_retained_date_place_candidates" if native_citations_all else "retained_date_place_candidates_only" if inspect_details else "not_requested"}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--candidates-gzip", action="store_true", help="Read gzipped candidate JSON; .gz suffix or gzip magic is also detected")
    parser.add_argument("--output", required=True)
    parser.add_argument("--worktree", default=str(ROOT))
    parser.add_argument("--shared", default=str(SHARED))
    parser.add_argument("--inspect-details", action="store_true")
    parser.add_argument("--native-citations-all", action="store_true", help="Read original chunks once for exact candidate HC keys; retain conflict states")
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError("Output already exists; preserve reviewed research artifacts")
    candidate_path = Path(args.candidates)
    candidate_bytes = candidate_path.read_bytes()
    decoded_candidates = gzip.decompress(candidate_bytes) if args.candidates_gzip or candidate_path.suffix == ".gz" or candidate_bytes.startswith(b"\x1f\x8b") else candidate_bytes
    if len(decoded_candidates) > 30 * 1024 * 1024:
        raise ValueError("Decoded candidate input exceeds explicit 30 MiB cap")
    payload = json.loads(decoded_candidates)
    candidates = payload if isinstance(payload, list) else payload.get("records", payload.get("entries", payload.get("candidates")))
    if not isinstance(candidates, list):
        raise ValueError("Candidates must be a list or an object containing records/entries/candidates")
    root = Path(args.worktree)
    plan_path = root / "releases/workspace-analysis-20261008/delivery_plan.json"
    plan_bytes = plan_path.read_bytes()
    plan = json.loads(plan_bytes)
    shards = [r for r in plan["uploads"] if re.search(r"/summary_shards/summary_\d+\.json\.gz$", r["key"])]
    encounter_path = root / "data/encounters/evidence.json.gz"
    encounter_bytes = encounter_path.read_bytes()
    encounters = json.loads(gzip.decompress(encounter_bytes))
    ids = {str(r["eventId"]) for r in encounters["rows"]}
    result = overlap(candidates, shards, ids, inspect_details=args.inspect_details,
                     native_citations_all=args.native_citations_all, shared=Path(args.shared), expected_count=encounters["catalogCount"])
    result["inputs"] = [{"path": str(p), "bytes": len(raw), "sha256": sha(raw)} for p, raw in
                        ((candidate_path, candidate_bytes), (plan_path, plan_bytes), (encounter_path, encounter_bytes))]
    script_path = Path(__file__).resolve()
    script_bytes = script_path.read_bytes()
    result["builder"] = {"path": str(script_path), "bytes": len(script_bytes), "sha256": sha(script_bytes)}
    encoded = (json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    if len(encoded) > 30 * 1024 * 1024:
        raise ValueError("Decoded overlap artifact exceeds explicit 30 MiB cap")
    decoded_bytes = len(encoded)
    if output.suffix == ".gz":
        encoded = gzip.compress(encoded, mtime=0)
    if len(encoded) > MAX_OUTPUT_BYTES:
        raise ValueError("Overlap artifact exceeds explicit 5 MiB cap")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(encoded)
    print(json.dumps({"output": str(output), "bytes": len(encoded), "decodedBytes": decoded_bytes, "sha256": sha(encoded), "counts": result["counts"]}, indent=2))


if __name__ == "__main__":
    main()
