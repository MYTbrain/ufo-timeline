"""Reconcile prior accepted intervals with a source-backed corpus candidate.

No corpus copy or source mutation. A changed/withdrawn old interval must join
an original nonblank UFOCAT time/date flag; all other old numeric bounds must
remain exactly preserved. The small result is an audit receipt, not a release.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path


def load(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def pin(path):
    raw = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def check(baseline_path, candidate_path, ledger_path):
    baseline, candidate, ledger = [load(path) for path in (baseline_path, candidate_path, ledger_path)]
    old = {row[0]: row for row in baseline["rows"]}
    new = {row[0]: row for row in candidate["rows"]}
    fields = {row["eventId"]: row for row in ledger["rows"]}
    excluded = {row["eventId"]: row for row in candidate.get("excludedDates", [])}
    if set(new).intersection(excluded):
        raise ValueError("Source date is both accepted and excluded")
    counts, changes, examples = Counter(), Counter(), []
    for event_id, row in old.items():
        next_row = new.get(event_id)
        if next_row and row[1:3] == next_row[1:3]:
            counts["prior_numeric_intervals_unchanged"] += 1
            continue
        source = fields.get(event_id)
        if source is None:
            raise ValueError(f"Unexplained prior interval change/withdrawal: {event_id}")
        outcome = "source_flag_corrected_interval" if next_row else "source_flag_withheld_interval"
        counts[outcome] += 1
        changes[source["fields"]["TZ"] + " / " + outcome] += 1
        if len(examples) < 20:
            examples.append({"eventId": event_id, "sourceFlag": source["fields"]["TZ"],
                             "sourceZoneCode": source["fields"]["TZONE"],
                             "oldUTC": row[1:3], "newUTC": next_row[1:3] if next_row else None,
                             "exclusion": excluded.get(event_id)})
    counts["newly_supported_intervals"] = len(set(new) - set(old))
    counts["baseline_accepted_intervals"] = len(old)
    counts["candidate_accepted_intervals"] = len(new)
    counts["source_date_exclusions"] = len(excluded)
    return {"schemaId": "corpus-timing-transition-check-v1", "baseline": pin(baseline_path),
            "candidate": pin(candidate_path), "sourceFieldLedger": pin(ledger_path),
            "counts": dict(counts), "sourceFlagChangeCounts": dict(changes), "examples": examples,
            "unexplainedPriorChanges": 0, "allOtherPriorNumericBoundsPreserved": True,
            "sourceRecordsMutated": False, "storagePurpose": "Retain small source-correction reconciliation receipt with final corpus timing audit; rebuild using pinned arguments, no corpus or backup copy."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("baseline", "candidate", "ledger", "output"):
        parser.add_argument("--" + key, required=True, type=Path)
    args = parser.parse_args()
    result = check(args.baseline, args.candidate, args.ledger)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["counts"]))
