"""Recover bounded own-occurrence clocks from the entire preserved UFO corpus.

Canonical chunks are streamed once, never copied or changed. Only narrow,
reproducible templates become local-clock evidence. Approximation words have no
invented tolerance; natural day periods, cross-day ranges and ambiguous incident
context remain review candidates. Geographic and UTC acceptance belongs to the
chronology builder, not this extraction pass.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date
import gzip
import hashlib
import json
from pathlib import Path
import re
import time

SHARED = Path(r"C:/Users/jarod/Desktop/UFO Timeline map tool")
DEFAULT_OUTPUT = SHARED / "data/research/trace-chronology-20261008/corpus-recovery"
DAY_MS = 86_400_000
OUTPUT_BUDGET = 5 * 1024 * 1024
MAX_SAFE_ID = 9_007_199_254_740_991

AMPM = r"[ap]\.?\s*m\.?"
TIME = rf"(?:\d{{1,2}}(?::\d{{2}}(?::\d{{2}})?)?\s*{AMPM}|\d{{1,2}}:\d{{2}}(?::\d{{2}})?)"
ZONE = r"(?:UTC|GMT|Z|EST|EDT|CST|CDT|MST|MDT|PST|PDT|AKST|AKDT|HST|LT|local(?:\s+time)?|[+-]\d{2}:?\d{2})(?!\w)"
TOKEN = re.compile(rf"(?<![\w\d:]){TIME}(?!\w)", re.I)
POINT = re.compile(rf"^(\d{{1,2}})(?::(\d{{2}}))?(?::(\d{{2}}))?\s*({AMPM})?$", re.I)
PREFIX = re.compile(r"^\s*(?:(at)\s+)?", re.I)
APPROX = re.compile(r"\b(?:about|around|approximately|approx\.?|roughly|circa|estimated|nearly|almost|shortly|close to)\b|[?~\u00b1]|\+/-", re.I)
DATE_CONTEXT = re.compile(r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|January|February|March|April|May|June|July|August|September|October|November|December)\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b(?:19|20)\d{2}\b", re.I)
PERIOD = re.compile(r"\b(?:morning|afternoon|evening|night(?:time|fall)?|dawn|dusk|daytime|daylight|sunset|sunrise|twilight|noon|midnight)\b", re.I)
EVENT_VERB = re.compile(r"\b(?:saw|sees|seen|observed|observes|sighted|spotted|noticed|witnessed|appeared|appears|hovered|hovering|landed|landing|tracked|tracks)\b", re.I)
OBJECT = re.compile(r"\b(?:ufos?|uaps?|objects?|lights?|craft|discs?|disks?|saucers?|orbs?|spheres?|triangles?|ellipses?|cigars?|boomerangs?|fireballs?|balls?|targets?|phenomen(?:on|a))\b", re.I)
REPORT = re.compile(r"\b(?:reported|reporting|reports?|telephoned|called|interviewed|interviews?|received|submitted|submission|posted|published|publication|press conference|newspaper|article|letter|meeting|lecture|broadcast|announced)\b", re.I)
MULTI_EVENT = re.compile(r"\b(?:another|parallel incident|different incident|separate|second|previous|next|following day|earlier|later|night before|first night|same or a similar|again|subsequently|meanwhile|missing time|nightly|daily|every night|minutes after|hours after|over \d+ days)\b", re.I)
PRIOR_ACTION = re.compile(r"\b(?:driv(?:ing|es|e)|walk(?:ing|ed|s)?|went|goes|going|woke|awoke|awakened|left|depart(?:ed|ing)?|arriv(?:ed|ing)|took|started|begin|began|waiting|waited|returned|returning|stepped|chasing|heard|hears|looked|looking|watching|sat|sitting|stood|standing|when|then|after|before|while)\b", re.I)
TIMEBASE = re.compile(r"\b(?:airliner|aircrew|aboard|on board|ship|offshore|at sea|pilot|flight|aircraft)\b", re.I)
RANGE = re.compile(rf"^\s*(?:(?:between|from)\s+)?(?P<a>{TIME})\s*(?:to|and|[-\u2013\u2014])\s*(?P<b>{TIME})(?:\s+(?P<zone>{ZONE}))?", re.I)
SHARED_SUFFIX_RANGE = re.compile(rf"^\s*(?:(?:between|from)\s+)?(?P<a>\d{{1,2}}(?::\d{{2}}(?::\d{{2}})?)?)\s*(?:to|and|[-\u2013\u2014])\s*(?P<b>\d{{1,2}}(?::\d{{2}}(?::\d{{2}})?)?)\s*(?P<half>{AMPM})(?:\s+(?P<zone>{ZONE}))?", re.I)
LEADING_POINT = re.compile(rf"^\s*(?:at\s+)?(?P<t>{TIME})(?:\s+(?P<zone>{ZONE}))?", re.I)
LEADING_HALF = re.compile(rf"^\s*(?:in|during)\s+the\s+(?P<half>{AMPM})(?!\w)", re.I)
EXACT_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def pin(path: Path) -> dict:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": h.hexdigest()}


def read_json(path: Path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def point_bounds(token: str):
    """Return reported clock-resolution bounds; bare hours require AM/PM."""
    match = POINT.fullmatch(token.strip())
    if not match:
        return None
    hour, minute, second, ampm = match.groups()
    hour = int(hour)
    if ampm:
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if ampm.lower().startswith("p") else 0)
    elif minute is None or not 0 <= hour <= 23:
        return None
    if minute is not None and int(minute) > 59 or second is not None and int(second) > 59:
        return None
    start = (hour * 3600 + int(minute or 0) * 60 + int(second or 0)) * 1000
    width, precision = (1000, "second") if second is not None else (60_000, "minute") if minute is not None else (3_600_000, "hour")
    return {"localStartMs": start, "localEndMs": start + width - 1, "precision": precision}


def explicit_range(text: str, *, full: bool):
    # A trailing AM/PM governs both endpoints in '4:45-7:06 p.m.'.
    # Prefer that grammar before interpreting the first endpoint as 24-hour.
    match = SHARED_SUFFIX_RANGE.match(text)
    shared_suffix = match is not None
    if match is None:
        match = RANGE.match(text)
    if not match or full and text[match.end():].strip(" .,"):
        return None
    if re.search(r"\band\b", match.group(0), re.I) and not re.match(r"\s*between\b", match.group(0), re.I):
        return {"candidateReason": "multiple_clock_values_not_an_explicit_range", "end": match.end()}
    suffix = " " + match.group("half") if shared_suffix else ""
    first, second = point_bounds(match.group("a") + suffix), point_bounds(match.group("b") + suffix)
    if first is None or second is None:
        return None
    if second["localEndMs"] < first["localStartMs"]:
        return {"candidateReason": "cross_midnight_range_requires_explicit_end_date", "end": match.end()}
    result = {"localStartMs": first["localStartMs"], "localEndMs": second["localEndMs"], "precision": "explicit_range", "end": match.end(), "clockExcerpt": match.group(0).strip(), "ruleId": "own_explicit_same_day_clock_range_v1", "clockMentions": len(TOKEN.findall(match.group(0)))}
    if match.group("zone"):
        result["explicitTimezoneToken"] = match.group("zone")
    return result


def parse_source_time(raw: str):
    """Parse only complete own-source field templates, without source sentinels."""
    text = raw.strip()
    if not text or APPROX.search(text):
        return None
    result = explicit_range(text, full=True)
    if result:
        return result
    # Literal AM/PM is a 12-hour period, not a clock at midnight/noon.
    if re.fullmatch(AMPM, text, re.I):
        pm = text.lower().startswith("p")
        return {"localStartMs": DAY_MS // 2 if pm else 0, "localEndMs": DAY_MS - 1 if pm else DAY_MS // 2 - 1, "precision": "explicit_ampm_half", "end": len(raw), "clockExcerpt": text, "ruleId": "own_literal_ampm_half_v1"}
    match = re.fullmatch(rf"(?P<t>{TIME})(?:\s+(?P<zone>{ZONE}))?", text, re.I)
    if not match:
        return None
    result = point_bounds(match.group("t"))
    if result is None:
        return None
    result.update({"end": len(raw), "clockExcerpt": text, "ruleId": "own_complete_source_clock_v1"})
    if match.group("zone"):
        result["explicitTimezoneToken"] = match.group("zone")
    return result


def recover_narrative(text: str):
    """Return a local extraction or a reason why a visible clock needs review."""
    visible = list(TOKEN.finditer(text))
    if not visible and not PERIOD.search(text[:150]) and not LEADING_HALF.match(text):
        return None
    result = explicit_range(text, full=False)
    if result and "candidateReason" in result:
        return result
    is_range = result is not None
    if result is None:
        match = LEADING_POINT.match(text)
        if match:
            result = point_bounds(match.group("t"))
            if result:
                result.update({"end": match.end(), "clockExcerpt": match.group(0).strip(), "ruleId": "leading_direct_own_occurrence_clock_v1"})
                if match.group("zone"):
                    result["explicitTimezoneToken"] = match.group("zone")
        else:
            match = LEADING_HALF.match(text)
            if match:
                pm = match.group("half").lower().startswith("p")
                result = {"localStartMs": DAY_MS // 2 if pm else 0, "localEndMs": DAY_MS - 1 if pm else DAY_MS // 2 - 1, "precision": "explicit_ampm_half", "end": match.end(), "clockExcerpt": match.group(0).strip(), "ruleId": "leading_direct_own_ampm_half_v1"}
    if result is None:
        return {"candidateReason": "nonleading_clock_or_natural_period_requires_context_review"}
    if APPROX.search(text[:result["end"]]):
        return {"candidateReason": "approximation_has_no_source_defined_tolerance"}
    expected_mentions = result.get("clockMentions", 2) if is_range else 0 if result["precision"] == "explicit_ampm_half" else 1
    if len(visible) != expected_mentions:
        return {"candidateReason": "additional_or_unparsed_clock_mentions"}
    if MULTI_EVENT.search(text):
        return {"candidateReason": "multiple_occurrences_relative_day_or_missing_time"}
    # Source bibliography can follow the event. It never supplies a clock.
    tail = text[result["end"]:]
    verb = EVENT_VERB.search(tail[:150])
    if not verb or not OBJECT.search(tail[:250]):
        return {"candidateReason": "no_direct_occurrence_and_object_near_clock"}
    before_verb = tail[:verb.start()]
    if APPROX.search(before_verb):
        return {"candidateReason": "clock_adjacent_qualifier_requires_context_review"}
    if DATE_CONTEXT.search(before_verb):
        return {"candidateReason": "narrative_calendar_date_requires_consistency_review"}
    if REPORT.search(tail[:250]) or PRIOR_ACTION.search(before_verb):
        return {"candidateReason": "reporting_or_preobservation_action_context"}
    token = str(result.get("explicitTimezoneToken") or "")
    explicit_absolute_zone = bool(token) and not re.fullmatch(r"(?:LT|local(?:\s+time)?)", token, re.I)
    if TIMEBASE.search(tail[:250]) and not explicit_absolute_zone:
        return {"candidateReason": "airborne_or_maritime_unstated_clock_timebase"}
    # A 24h token without an AM/PM or a literal 'at' may be a citation/ratio.
    if not is_range and result["precision"] != "explicit_ampm_half" and not re.search(AMPM, result["clockExcerpt"], re.I) and not re.match(r"\s*at\s+", text, re.I):
        return {"candidateReason": "bare_24h_narrative_token_requires_review"}
    result["excerpt"] = text[:min(len(text), result["end"] + verb.end() + 180)]
    return result


def exact_calendar_day(event: dict) -> bool:
    value = event.get("sort_date_iso") or event.get("date_iso")
    if event.get("date_precision") != "exact_day" or not isinstance(value, str) or not EXACT_DATE.fullmatch(value):
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def extraction_row(event, extraction, field, path, index, raw_chunk, chunk_hash, typed_status):
    text = str(event.get(field) or "")
    excerpt = extraction.get("excerpt", text)
    # Description excerpt is a literal prefix; source-field excerpt is the full raw field.
    return {"eventId": event["event_id"], "source": event.get("source"), "sourceId": event.get("source_id"), "sourceRowNumber": event.get("source_row_number"), "date": event.get("sort_date_iso") or event.get("date_iso"), "datePrecision": event.get("date_precision"), "sourceTimeRaw": str(event.get("time_raw") or ""), "sourceTimeStatus": typed_status, "sourceField": field, "sourceChunk": path.stem, "sourceChunkPath": str(path.resolve()), "sourceChunkSha256": chunk_hash, "sourceChunkBytes": len(raw_chunk), "detailIndex": index, "sourceTextSha256": digest(text.encode("utf-8")), "excerpt": excerpt, "excerptStart": 0, "excerptEnd": len(excerpt), "localStartMs": extraction["localStartMs"], "localEndMs": extraction["localEndMs"], "precision": extraction["precision"], "ruleId": extraction["ruleId"], "clockExcerpt": extraction["clockExcerpt"], **({"explicitTimezoneToken": extraction["explicitTimezoneToken"]} if extraction.get("explicitTimezoneToken") else {}), "basis": "source_clock_resolution_interval" if extraction["precision"] not in {"explicit_ampm_half", "explicit_range"} else "source_defined_clock_range_or_literal_half_day", "status": "accepted_local_evidence_pending_geographic_UTC_gate", "measuredPhysicalTimingEstablished": False, "physicalFlightPathEstablished": False}


def validate_recovered_sources(rows, root=SHARED):
    """Fail closed on chunk/identity/date/field/quote drift, and rerun every rule."""
    source_root = (Path(root) / "data/canonical_web/event_chunks").resolve()
    attribute = Path(root) / "data/research/analysis-repairs-20261007/attributes/analysis_time_of_day_v1"
    manifest, dictionary = read_json(attribute / "manifest.json"), read_json(attribute / "time_of_day_value_dictionary_v1.json.gz")
    source_status = {(manifest["codes"]["source"][v[0]], v[2]): manifest["codes"]["status"][v[3]] for v in dictionary}
    groups = defaultdict(list)
    seen = set()
    for row in rows:
        event_id = row.get("eventId")
        if type(event_id) is not int or not 0 < event_id <= MAX_SAFE_ID or event_id in seen:
            raise ValueError("Recovered evidence has an invalid or duplicate event ID")
        seen.add(event_id)
        path = Path(row.get("sourceChunkPath", "")).resolve()
        if path.parent != source_root or path.stem != row.get("sourceChunk") or path.suffix != ".json":
            raise ValueError("Recovered source path is outside shared canonical chunks")
        groups[path].append(row)
    pins = []
    for path, group in sorted(groups.items(), key=lambda item: str(item[0])):
        raw = path.read_bytes()
        h = digest(raw)
        events = json.loads(raw)
        for row in group:
            if row.get("sourceChunkSha256") != h or row.get("sourceChunkBytes") != len(raw):
                raise ValueError("Recovered source chunk hash or size drift")
            index = row.get("detailIndex")
            if type(index) is not int or not 0 <= index < len(events):
                raise ValueError("Recovered source detail locator invalid")
            event = events[index]
            if event.get("event_id") != row["eventId"] or event.get("source") != row.get("source") or event.get("source_id") != row.get("sourceId") or event.get("source_row_number") != row.get("sourceRowNumber"):
                raise ValueError("Recovered source identity drift")
            if not exact_calendar_day(event) or (event.get("sort_date_iso") or event.get("date_iso")) != row.get("date") or str(event.get("time_raw") or "") != row.get("sourceTimeRaw"):
                raise ValueError("Recovered source date or original clock drift")
            actual_status = source_status.get((event.get("source"), str(event.get("time_raw") or "").strip()), "empty_or_unclassified")
            if actual_status != row.get("sourceTimeStatus"):
                raise ValueError("Recovered original typed clock status drift")
            field = row.get("sourceField")
            if field not in {"description", "summary", "time_raw"}:
                raise ValueError("Recovered source field unsupported")
            text = str(event.get(field) or "")
            if digest(text.encode("utf-8")) != row.get("sourceTextSha256") or row.get("excerptStart") != 0 or row.get("excerptEnd") != len(row.get("excerpt", "")) or not text.startswith(row.get("excerpt", "")):
                raise ValueError("Recovered source field hash or exact quotation drift")
            parsed = parse_source_time(text) if field == "time_raw" else recover_narrative(text)
            if not parsed or "candidateReason" in parsed or any(parsed.get(k) != row.get(k) for k in ("localStartMs", "localEndMs", "precision", "ruleId", "clockExcerpt", "explicitTimezoneToken")):
                raise ValueError("Recovered template or interval drift")
            if field != "time_raw" and row.get("sourceTimeStatus") not in {"empty_or_unclassified", "sentinel_ambiguous", "invalid_clock", "qualitative_period"}:
                raise ValueError("Recovered narrative conflicts with an existing exact/approximate source clock")
            if field != "time_raw" and actual_status == "empty_or_unclassified" and str(event.get("time_raw") or "").strip():
                raise ValueError("Recovered narrative would promote an unclassified existing source clock")
            if field == "time_raw" and actual_status in {"exact_clock", "sentinel_ambiguous", "approximate_clock", "qualitative_period"}:
                raise ValueError("Recovered source field would promote an existing typed status or sentinel")
        pins.append({"path": str(path), "bytes": len(raw), "sha256": h, "role": "recovered_own_occurrence_clock_source", "recordsVerified": len(group)})
    return pins


def corpus_recovery(root=SHARED):
    started = time.monotonic()
    root = Path(root)
    attribute = root / "data/research/analysis-repairs-20261007/attributes/analysis_time_of_day_v1"
    manifest_path, dictionary_path = attribute / "manifest.json", attribute / "time_of_day_value_dictionary_v1.json.gz"
    manifest, dictionary = read_json(manifest_path), read_json(dictionary_path)
    codes = manifest["codes"]
    lookup = {(codes["source"][value[0]], value[2]): (codes["status"][value[3]], value) for value in dictionary}
    rows, candidates, counts, sources, chunks = [], [], Counter(), defaultdict(Counter), []
    candidate_codes = {"source": [], "sourceField": [], "sourceTimeStatus": [], "reviewReason": []}
    samples, sample_counts = [], Counter()
    def candidate(event, path, index, field, status, reason, text):
        source = event.get("source", "unknown")
        values = [source, field, status, reason]
        indices = []
        for key, value in zip(candidate_codes, values):
            if value not in candidate_codes[key]:
                candidate_codes[key].append(value)
            indices.append(candidate_codes[key].index(value))
        candidates.append([event["event_id"], path.stem, index, *indices])
        sources[source]["candidates"] += 1
        sample_key = (source, reason)
        if sample_counts[sample_key] < 4:
            match = TOKEN.search(text)
            start = max(0, match.start() - 80) if match else 0
            samples.append({"eventId": event["event_id"], "source": source, "sourceChunk": path.stem, "detailIndex": index, "sourceField": field, "sourceTimeStatus": status, "reviewReason": reason, "excerpt": text[start:start + 350], "sourceTextSha256": digest(text.encode("utf-8"))})
            sample_counts[sample_key] += 1
    typed_inventory = Counter()
    for path in sorted((root / "data/canonical_web/event_chunks").glob("*.json")):
        raw_chunk = path.read_bytes()
        chunk_hash = digest(raw_chunk)
        events = json.loads(raw_chunk)
        chunks.append({"file": path.name, "bytes": len(raw_chunk), "sha256": chunk_hash, "rows": len(events)})
        for index, event in enumerate(events):
            counts["corpus_records_scanned"] += 1
            source, raw = event.get("source", "unknown"), str(event.get("time_raw") or "")
            status, dictionary_row = lookup.get((source, raw.strip()), ("empty_or_unclassified", None))
            counts["source_status_" + status] += 1
            sources[source]["scanned"] += 1
            if status == "exact_clock":
                continue
            if dictionary_row:
                typed_inventory[(source, raw.strip(), status)] += 1
            field = "time_raw"
            extraction = parse_source_time(raw) if status not in {"sentinel_ambiguous", "approximate_clock", "qualitative_period"} else None
            if extraction is None or "candidateReason" in extraction:
                field = "description" if isinstance(event.get("description"), str) and event["description"] else "summary"
                text = str(event.get(field) or "")
                extraction = recover_narrative(text)
            else:
                text = raw
            if extraction is None:
                if status in {"approximate_clock", "qualitative_period"}:
                    candidate(event, path, index, "time_raw", status, "approximation_or_natural_period_has_no_source_defined_clock_bounds", raw)
                    counts["candidate_typed_unbounded_approximation_or_period"] += 1
                continue
            reason = extraction.get("candidateReason")
            if not reason and status == "approximate_clock":
                reason = "existing_source_clock_approximation_must_not_be_promoted"
            if not reason and field != "time_raw" and raw.strip() and status == "empty_or_unclassified":
                reason = "unclassified_existing_source_clock_requires_conflict_review"
            if not reason and not exact_calendar_day(event):
                reason = "partial_or_uncertain_source_date"
            if reason:
                # Exact excerpt/locator permits independent source reopening; no prose copies.
                candidate(event, path, index, field, status, reason, text)
                counts["candidate_" + reason] += 1
                continue
            row = extraction_row(event, extraction, field, path, index, raw_chunk, chunk_hash, status)
            rows.append(row)
            counts["accepted_local_rows"] += 1
            counts["accepted_" + extraction["precision"]] += 1
            counts["accepted_field_" + field] += 1
            sources[source]["accepted_local"] += 1
    inventory = []
    counts["candidate_rows"] = len(candidates)
    counts["accepted_local_pre1970_rows"] = sum(row["date"] < "1970-01-01" for row in rows)
    for (source, raw, status), count in sorted(typed_inventory.items()):
        value = lookup[(source, raw)][1]
        inventory.append({"source": source, "raw": raw, "status": status, "corpusOccurrences": count, "dictionaryLowerMinute": value[5], "dictionaryUpperMinute": value[6], "qualitativePeriod": codes["qualitativePeriod"][value[10]], "note": "dictionary values for approximate clocks are centers without a source-defined tolerance; natural periods have no accepted numeric clock bounds" if status in {"approximate_clock", "qualitative_period"} else "source status retained"})
    policy = {"scope": "entire preserved canonical event corpus, every source and year; no flap-only filter", "sourceMutated": False, "corpusCopied": False, "rawNoonMidnightSentinelsAcceptedAsClocks": False, "clocksBorrowedAcrossRecords": False, "approximationTolerancesInvented": False, "naturalDayPeriodMidpointsUsed": False, "localEvidenceEqualsUTCAcceptance": False, "reportedResolutionEqualsMeasuredTimingAccuracy": False, "automaticAcceptance": "narrow complete own-source fields or leading direct-occurrence grammar only; rerunnable rules with source pins"}
    common = {"schemaId": "trace-occurrence-clock-recovery-v1", "policy": policy}
    evidence = {**common, "rows": rows}
    queue = {"schemaId": "trace-occurrence-clock-recovery-candidates-v1", "policy": policy, "rowSchema": ["eventId", "sourceChunk", "detailIndex", "sourceCode", "sourceFieldCode", "sourceTimeStatusCode", "reviewReasonCode"], "codes": candidate_codes, "rows": candidates, "reviewSamples": samples, "provenance": "Every candidate reopens its own event in the audit-pinned shared canonical chunk; bounded excerpts are samples only, and no candidate is an accepted clock."}
    audit = {**common, "counts": dict(counts), "bySource": {key: dict(value) for key, value in sources.items()}, "inputs": {"canonicalManifest": pin(root / "data/canonical_web/canonical_web_manifest.json"), "clockManifest": pin(manifest_path), "clockDictionary": pin(dictionary_path), "sourceChunksRoot": str((root / "data/canonical_web/event_chunks").resolve()), "sourceChunks": chunks, "extractor": pin(Path(__file__))}, "typedNonexactValueInventory": inventory, "elapsedSeconds": round(time.monotonic() - started, 3), "storage": {"canonicalArtifact": "occurrence_clock_evidence.json.gz and corpus_recovery_audit.json", "rollback": "existing source-pinned accepted_narrative_clocks.json and evidence.json.gz remain retained; no deployment created", "purpose": "sparse local occurrence-clock evidence and whole-corpus review leads", "rebuild": "run this helper with --root pointing to the same shared corpus and --output pointing to this directory", "retention": "retain audit/evidence while consumed by chronology; review queue remains reproducible from immutable source pins", "supersededArtifacts": [], "newFilesLargerThan100MiB": [], "netGrowthBudgetBytes": OUTPUT_BUDGET}}
    return evidence, queue, audit


def output_bytes(evidence, queue, audit):
    encode = lambda value: json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return {"occurrence_clock_evidence.json.gz": gzip.compress(encode(evidence), mtime=0), "occurrence_clock_candidates.json.gz": gzip.compress(encode(queue), mtime=0), "corpus_recovery_audit.json": (json.dumps(audit, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode("utf-8")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=SHARED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify-only", type=Path)
    args = parser.parse_args()
    if args.verify_only:
        rows = read_json(args.verify_only)["rows"]
        pins = validate_recovered_sources(rows, args.root)
        print(json.dumps({"verifiedLocalRows": len(rows), "verifiedSourceChunks": len(pins)}, indent=2))
        return
    evidence, queue, audit = corpus_recovery(args.root)
    payloads = output_bytes(evidence, queue, audit)
    if sum(len(value) for value in payloads.values()) > OUTPUT_BUDGET:
        raise ValueError("Recovery outputs exceed the explicit 5 MiB budget; nothing was written")
    args.output.mkdir(parents=True, exist_ok=True)
    previous = sum((args.output / name).stat().st_size for name in payloads if (args.output / name).exists())
    for name, value in payloads.items():
        (args.output / name).write_bytes(value)
    print(json.dumps({"output": str(args.output.resolve()), "counts": audit["counts"], "bySource": audit["bySource"], "files": {name: len(value) for name, value in payloads.items()}, "netDiskGrowthBytes": sum(len(value) for value in payloads.values()) - previous}, indent=2))


if __name__ == "__main__":
    main()
