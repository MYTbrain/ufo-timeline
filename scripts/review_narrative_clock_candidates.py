"""Prepare a bounded source-row review queue; never auto-accept narrative clocks.

Review scope is the 199 mapped original-detail strong leads from the coverage
audit, plus the specifically requested Ariel School Eberhart record. The queue
records full descriptions and hashes the exact existing detail chunk bytes.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import audit_trace_timing_coverage as coverage


FRONTEND = Path(r"C:/Users/jarod/.codex/worktrees/case-navigation-release/UFO Timeline map tool")


def load_builder(root):
    sys.path.insert(0, str(root / ".python_packages"))
    path = FRONTEND / "scripts/build_trace_chronology_evidence.py"
    spec = importlib.util.spec_from_file_location("trace_chronology_builder", path)
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    return builder


def prepare(root):
    builder = load_builder(root)
    aliases, single_zones, timezone_metadata = builder.country_zone_rules()
    candidates, counts = [], Counter()
    for path in sorted((root / "data/canonical_web/event_chunks").glob("*.json")):
        raw_chunk = path.read_bytes()
        rows = json.loads(raw_chunk)
        chunk_hash = None
        for index, event in enumerate(rows):
            exception = event.get("event_id") == 3478209486003715
            if str(event.get("time_raw") or "").strip() or not (event.get("has_coordinates") or exception):
                continue
            text = str(event.get("description") or event.get("summary") or "")
            lead = coverage.LEADING.match(text)
            if not lead or not 1 <= int(lead.group("hour")) <= 12 or int(lead.group("minute") or 0) > 59:
                continue
            tail = text[lead.end():]
            if len(coverage.clocks(text)) != 1 or coverage.MULTI_EVENT.search(text) or coverage.REPORT_VERBS.search(tail[:150]) or coverage.APPROXIMATE.search(lead.group(0)) or not coverage.EVENT_VERBS.search(tail[:250]):
                continue
            if chunk_hash is None:
                chunk_hash = hashlib.sha256(raw_chunk).hexdigest()
            hour = int(lead.group("hour")) % 12
            if lead.group("ampm").lower() == "p":
                hour += 12
            minute = hour * 60 + int(lead.group("minute") or 0)
            zone, zone_reason = builder.strict_zone(event, aliases, single_zones)
            if exception:
                zone, zone_reason = "Africa/Harare", "manually_reviewed_explicit_Ruwa_Zimbabwe_jurisdiction"
            exact_day = event.get("date_precision") == "exact_day"
            if not exact_day:
                counts["deferred_partial_or_uncertain_date"] += 1
            elif not zone:
                counts["deferred_unresolved_zone"] += 1
            else:
                counts["eligible_for_source_row_manual_review"] += 1
            row = {"eventId": event["event_id"], "source": event.get("source"), "sourceId": event.get("source_id"), "sourceRowNumber": event.get("source_row_number"), "date": event.get("sort_date_iso") or event.get("date_iso"), "datePrecision": event.get("date_precision"), "location": event.get("location_raw"), "lat": event.get("lat"), "lon": event.get("lon"), "mappedOriginalDetail": bool(event.get("has_coordinates")), "zone": zone, "zoneReason": zone_reason, "localLowerMinute": minute, "localUpperMinute": minute, "localStartMs": minute * 60_000, "localEndMs": minute * 60_000 + 59_999, "sourceField": "description", "sourceChunk": str(path.resolve()), "sourceChunkSha256": chunk_hash, "sourceChunkBytes": len(raw_chunk), "detailIndex": index, "sourceProvenance": event.get("source_provenance", []), "sourceUrl": event.get("source_url"), "leadingClockExcerpt": lead.group(0).strip(), "description": text, "exactDay": exact_day, "requestedArielException": exception, "status": "pending_manual_review" if exact_day and zone else "deferred_date_or_zone"}
            candidates.append(row)
    counts["all_mapped_original_detail_strong_leads"] = sum(not row["requestedArielException"] for row in candidates)
    counts["requested_Ariel_exception"] = sum(row["requestedArielException"] for row in candidates)
    return {"schemaId": "trace-narrative-clock-review-queue-v1", "policy": {"sourceMutated": False, "narrativeAutoAccepted": False, "scope": "Mapped original-detail source-clock-empty leading-occurrence-clock review leads plus the specifically requested Ariel Eberhart source record", "minutePrecisionIsReportedClockPrecisionNotPhysicalTimingCertainty": True}, "counts": dict(counts), "timezoneDatabase": timezone_metadata, "rows": candidates}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=coverage.DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    queue = prepare(args.root)
    args.output.write_text(json.dumps(queue, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"path": str(args.output), "bytes": args.output.stat().st_size, "counts": queue["counts"]}, indent=2))


if __name__ == "__main__":
    main()
