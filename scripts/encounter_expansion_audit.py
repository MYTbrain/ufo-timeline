"""Summarize pinned encounter intake and prepare a held review queue, offline."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--research", type=Path, required=True)
    ap.add_argument("--summary", type=Path, required=True)
    ap.add_argument("--queue-output", type=Path, help="Use a new empty output path for a replay without copying source data")
    args = ap.parse_args()
    root = args.research.resolve()
    queue_path = args.queue_output or root / "review_queue.json.gz"
    if args.summary.exists() or queue_path.exists():
        raise SystemExit("Protected audit output exists; no overwrite")
    native_path = root / "rosales-originals/combined-originals.json.gz"
    native = load(native_path)
    overlap = load(root / "rosales_overlap.json.gz")
    urecat = load(root / "urecat_candidates.json")
    urecat_overlap = load(root / "urecat_overlap.json.gz")
    parse = load(root / "rosales-originals/combined-originals-audit.json")
    receipt = load(root / "rosales-originals/combined-originals-receipt.json")
    if sha(native_path.read_bytes()) != receipt["output"]["sha256"]:
        raise ValueError("Combined source pin mismatch")
    records = {r["sourceEntryId"]: r for r in native["records"]}
    hcs = defaultdict(set)
    for row in records.values():
        for key in row["sourceCaseIds"]:
            if key["scheme"] == "rosales_hc":
                hcs[key["value"].lstrip("0") or "0"].add(row["sourceEntryId"])
    queue = []
    for found in overlap["entries"]:
        row = records[found["sourceEntryId"]]
        collision = any(len(hcs[k["value"].lstrip("0") or "0"]) > 1 for k in row["sourceCaseIds"] if k["scheme"] == "rosales_hc")
        links = found["nativeCitationLinks"]
        contextual = [k for k in links if k["dateAgreement"] == "overlap" and k["locationAgreement"] == "explicit_locality_phrase"]
        exact = len(contextual) == 1 and row["datePrecision"] == "day" and contextual[0]["datePrecision"] in {"exact_day", "day", "exact"}
        if len(links) == 1 and len(contextual) == 1 and not collision:
            tier = "native_context_review"
            if exact and found["locationCandidateCount"] == 1:
                tier = "precise_unambiguous_native_review"
        elif links:
            tier = "native_conflict_or_insufficient_context"
        elif found["locationCandidateCount"]:
            tier = "date_locality_discovery_review"
        else:
            tier = "no_candidate_found_not_proof_of_novelty"
        queue.append({"sourceEntryId": row["sourceEntryId"], "priority": tier,
                      "sourceUrl": row["sourceUrl"], "dateRaw": row["dateRaw"], "datePrecision": row["datePrecision"],
                      "locationRaw": row["locationRaw"], "timeRaw": row["timeRaw"],
                      "sourceClassificationRaw": row["sourceClassificationRaw"], "sourceCaseIds": row["sourceCaseIds"],
                      "reviewFlags": row["reviewFlags"], "nonuniqueHcKey": collision,
                      "capture": row["capture"], "nativeCitationLinks": links,
                      "summaryCandidateReportIds": [x["eventId"] for x in found["candidateLinks"]],
                      "outsideEncounterIndexCandidateCount": found["outsideEncounterIndexCandidateCount"],
                      "status": "held_not_admitted"})
    order = {s: i for i, s in enumerate(("precise_unambiguous_native_review", "native_context_review", "native_conflict_or_insufficient_context", "date_locality_discovery_review", "no_candidate_found_not_proof_of_novelty"))}
    queue.sort(key=lambda r: (order[r["priority"]], r["sourceEntryId"]))
    encoded = gzip.compress((json.dumps({"schemaId": "encounter-source-review-queue-v1", "records": queue, "acceptedIdentityLinks": 0, "policy": "Priority is a review order, never identity acceptance. No absent match establishes a new case. Source classification and reuse eligibility require separate review."}, ensure_ascii=False, separators=(",", ":")) + "\n").encode(), mtime=0)
    if len(encoded) > 4 * 1024 * 1024:
        raise ValueError("Review queue cap exceeded")
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    queue_path.write_bytes(encoded)
    pins = []
    for name in ("capture_manifest.json", "transcription_candidates.json", "urecat_candidates.json", "urecat_overlap.json.gz", "rosales-originals/combined-originals.json.gz", "rosales-originals/combined-originals-audit.json", "rosales-originals/combined-originals-receipt.json", "rosales_overlap.json.gz", "owned_duplicate_capture_cleanup.json"):
        path = root / name
        raw = path.read_bytes()
        pins.append({"path": str(path), "bytes": len(raw), "sha256": sha(raw)})
    pins.append({"path": str(queue_path), "bytes": len(encoded), "sha256": sha(encoded)})
    summary = {
        "schemaId": "encounter-source-expansion-audit-v1", "date": "2026-10-17",
        "result": "Recovered 10853 original-source candidate accounts and completed corpus-wide overlap discovery; no runtime ingestion or deployment.",
        "units": "Source accounts and catalog report rows, not independently verified or deduplicated incidents, abductions, persons, or beings.",
        "canonicalResearch": str(root), "canonicalCandidateMetadata": str(native_path),
        "sources": {"nativeRosalesCaptures": parse["sourcesParsed"], "nativeFormats": receipt["nativeSourceFormats"],
                    "transcriptionRows": 8666, "nativeCandidateAccounts": len(records), "urecatIndexCandidates": urecat["counts"]["candidateRecords"],
                    "urecatNotAdditiveToRosales": True},
        "sourceRecovery": {"transcriberMissingGroupsRecovered": 18, "additionalFailedHtmlYearsRecoveredAsPdf": [1994, 1995],
                           "method": "Public archived original-host HTML and native PDF filenames; direct live 403s were not bypassed.",
                           "fullHeraExportFound": False, "hera18000FigureDate": "2020-09-30", "outreachSent": False},
        "rosalesOverlap": overlap["counts"], "rosalesAlreadyCitedInCorpus": overlap["rosalesCitationAudit"],
        "urecatOverlap": urecat_overlap["counts"],
        "reviewPriorities": dict(Counter(r["priority"] for r in queue)),
        "hcKeyCollisions": {"groups": sum(len(v) > 1 for v in hcs.values()), "extraAccounts": sum(len(v) - 1 for v in hcs.values())},
        "datePrecision": parse["datePrecision"], "uncertainSourceClassifications": parse["reviewFlags"].get("uncertain_source_classification", 0),
        "classificationLimits": ["Type G includes voluntary interaction and cannot establish abduction.", "Nonvisual/voice/psychic contact is separate from reported visible beings.", "Source codes D and F use the author's original definitions, not the incorrect third-party README descriptions.", "Date, location, clock, citation, and hypothesis remain separate; no coordinates or UTC were invented."],
        "manualChecks": [
            {"case": "Teterboro 1998 HC3930", "finding": "Perceived message alongside a craft account; no explicit visible being in reviewed account."},
            {"case": "Northford 1995 HC2803", "finding": "Perceived voice and landed object; not automatically a visible-being or abduction record."},
            {"case": "Seattle 1997 HC3365", "finding": "Prior-night light and a human-looking airport encounter; witness-inferred relationship and uncertain classification retained."},
        ],
        "publication": {"runtimeAdditions": 0, "acceptedIdentityLinks": 0, "deploymentChanged": False, "fullNarrativesIncluded": False,
                        "eligibility": "Acquisition does not confer public redistribution rights; original pages and PDFs remain private research inputs."},
        "sourceLinks": ["https://6degreesofjohnkeel.com/blog/announcing-the-humanoid-encounters-project", "https://6degreesofjohnkeel.com/episodes/e055-introducin-project-hera-with-taylor-bell", "https://github.com/ebrinz/ufolio/tree/de7df473ddbd7849f7905522158dd3b43e65ab75/rosales", "https://www.iraap.org/rosales/", "https://ufologie.patrickgross.org/ce3/_full.htm", "https://www.nicap.org/cat7.htm"],
        "pins": pins,
        "replay": ["Run original parser against the three pinned manifests to a new empty destination.", "Run encounter_external_overlap.py --native-citations-all against pinned candidates and shared corpus in place.", "Run this script with the protected captures and pinned overlap outputs; choose new empty output destinations."],
    }
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"summary": str(args.summary), "queueBytes": len(encoded), "reviewPriorities": summary["reviewPriorities"]}))


if __name__ == "__main__":
    main()
