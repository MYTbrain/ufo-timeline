"""Recover twelve omitted/malformed citation footers from retained original captures.

This is an explicit reviewed metadata delta, not a permissive parser fallback.
Original source accounts, IDs, captures, narratives, dates and earlier pins remain
unchanged. Author-only citations remain author-only, not independent verification.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED = Path("C:/Users/jarod/Desktop/UFO Timeline map tool")
SPEC = importlib.util.spec_from_file_location("review_prepare", ROOT / "scripts/encounter_review_prepare.py")
PREP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREP)

# Explicit manual review of each originally missing citation, not a classifier.
# source span is retained as a tiny factual locator; no source narrative copied.
RECOVERIES = {
    "rosales-original:1910:27:7db8f382c039": ("Joaquim Fernandes", "Joaquim Fernandes", "attributed_person_without_publication_locator", "unlabelled_citation_footer"),
    "rosales-original:1956:47:4863708c0c88": ("Sven Olof Svensson", "Sven Olof Svensson", "attributed_person_without_publication_locator", "unlabelled_citation_footer"),
    "rosales-original:1966:141:f12c71d26b5c": ("Humcat 1966-64", "HUMCAT 1966-64", "catalog_account_locator_only", "unlabelled_catalog_citation"),
    "rosales-original:1967:214:8794aa59c6b9": ("Humcat 1967-43", "HUMCAT 1967-43", "catalog_account_locator_only", "unlabelled_catalog_citation"),
    "rosales-original:1970:23:a3a16d45f04d": ("So0urce: Luis Burgos, Ovniscience, Argentina", "Luis Burgos, Ovniscience, Argentina", "attributed_person_and_outlet_without_publication_locator", "source_label_typo"),
    "rosales-original:1973:30:5dca8297543c": ("Humcat 1973-125", "HUMCAT 1973-125", "catalog_account_locator_only", "unlabelled_catalog_citation"),
    "rosales-original:1973:32:7596e7fc20af": ("Humcat 1973-1", "HUMCAT 1973-1", "catalog_account_locator_only", "unlabelled_catalog_citation"),
    "rosales-original:1973:41:731390dd89ae": ("Preston Dennett, UFO Healing", "Preston Dennett, UFO Healing", "author_and_book_title_without_page", "unlabelled_citation_footer"),
    "rosales-original:1973:204:08439f1e8a86": ("Humcat 1973-62 Webb in 1973 Year of The Humanoids", "HUMCAT 1973-62; Webb in 1973 Year of The Humanoids", "catalog_locator_and_book_title_without_page", "unlabelled_catalog_and_author_footer"),
    "rosales-original:1996:161:f8b57f79e464": ("UFO Roundup Vol. 1 # 22", "UFO Roundup Vol. 1 # 22", "serial_volume_issue_locator", "unlabelled_citation_footer"),
    "rosales-original:1989:112:f85db2851514": ("HC addition # Tom Dongo, Alien Tide", "Tom Dongo, Alien Tide", "author_and_book_title_without_page", "citation_misplaced_in_non_numeric_hc_footer"),
    "rosales-original:1989:370:d25adec99596": ("HC addition # Paul M Makuch, New Jersey Chronicle September/December 1992", "Paul M Makuch, New Jersey Chronicle, September/December 1992", "author_outlet_issue_period", "citation_misplaced_in_non_numeric_hc_footer"),
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def run(output, *, shared=SHARED):
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Protected nonempty output exists")
    base = shared / "data/research/encounter-expansion-20261017/rosales-originals/combined-originals.json.gz"
    payload = base.read_bytes()
    original = json.loads(gzip.decompress(payload))
    rows_by_id = {row["sourceEntryId"]: row for row in original["records"]}
    missing_before = [row["sourceEntryId"] for row in original["records"] if not row.get("sourceCitationRaw")]
    if len(rows_by_id) != len(original["records"]) or len(missing_before) != 18:
        raise ValueError("Expected immutable source account baseline differs")
    grouped = defaultdict(list)
    for entry_id in RECOVERIES:
        row = rows_by_id[entry_id]
        if row.get("sourceCitationRaw"):
            raise ValueError("Recovery may only fill originally absent citation")
        grouped[row["capture"]["path"]].append(row)
    deltas = []
    for path, selected in grouped.items():
        capture = Path(path).read_bytes()
        text = PREP.source_text(capture)
        boundaries = list(PREP.M.NUMBER.finditer(text))
        for row in selected:
            if sha(capture) != row["capture"]["sha256"]:
                raise ValueError("Original capture hash mismatch")
            ordinal = row["sourceEntryOrdinal"] - 1
            block = text[boundaries[ordinal].end():boundaries[ordinal + 1].start() if ordinal + 1 < len(boundaries) else len(text)].strip()
            stop = PREP.M.STOP.search(block)
            if stop:
                block = block[:stop.start()].strip()
            normalized = PREP.M.compact(block)
            if sha(normalized.encode()) != row["sourceBlockSha256"]:
                raise ValueError("Original source block hash mismatch")
            source_span, replacement, specificity, recovery_kind = RECOVERIES[row["sourceEntryId"]]
            position = normalized.find(source_span)
            if position < 0 or normalized.find(source_span, position + 1) >= 0:
                raise ValueError("Reviewed citation span not uniquely located: " + row["sourceEntryId"])
            delta = {"sourceEntryId": row["sourceEntryId"], "field": "sourceCitationRaw", "previousValue": row.get("sourceCitationRaw"), "recoveredValue": replacement, "specificity": specificity, "recoveryKind": recovery_kind, "sourceUrl": row["sourceUrl"], "sourceBlockSha256": row["sourceBlockSha256"], "capture": {key: row["capture"][key] for key in ("path", "bytes", "sha256")}, "locator": {"nativeEntryNumber": row["nativeEntryNumber"], "sourceEntryOrdinal": row["sourceEntryOrdinal"], "normalizedSourceBlockCharacterStart": position, "normalizedSourceBlockCharacterEnd": position + len(source_span), "exactCitationSpan": source_span}, "reviewStatus": "manually_reviewed_original_source_footer", "independentCorroborationEstablished": False, "fullBibliographyRecovered": specificity in {"serial_volume_issue_locator", "author_outlet_issue_period"}}
            deltas.append(delta)
    deltas.sort(key=lambda row: row["sourceEntryId"])
    view = json.loads(json.dumps(original))
    delta_by_id = {row["sourceEntryId"]: row for row in deltas}
    for row in view["records"]:
        if row["sourceEntryId"] not in delta_by_id:
            continue
        delta = delta_by_id[row["sourceEntryId"]]
        row["sourceCitationRaw"] = delta["recoveredValue"]
        row["reviewFlags"] = [flag for flag in row.get("reviewFlags", []) if flag != "missing_source_citation"]
        row["reviewFlags"].append("citation_recovered_from_pinned_source_footer")
        row["sourceCitationRecovery"] = {"deltaEntryId": row["sourceEntryId"], "kind": delta["recoveryKind"], "specificity": delta["specificity"], "previousValue": delta["previousValue"], "sourceBlockSha256": delta["sourceBlockSha256"]}
    # Explicit whitelist: no date, place, time, classification or source identifier
    # may drift when a source label is repaired.
    for before, after in zip(original["records"], view["records"]):
        safe_before = {key: value for key, value in before.items() if key not in {"sourceCitationRaw", "reviewFlags", "sourceCitationRecovery"}}
        safe_after = {key: value for key, value in after.items() if key not in {"sourceCitationRaw", "reviewFlags", "sourceCitationRecovery"}}
        if safe_before != safe_after:
            raise ValueError("Non-citation metadata drift")
        if before["sourceEntryId"] not in delta_by_id and before != after:
            raise ValueError("Unreviewed account changed")
    remaining = [row["sourceEntryId"] for row in view["records"] if not row.get("sourceCitationRaw")]
    report = {"schemaId": "ufo-original-citation-recovery-delta-v1", "generatedAtUtc": datetime.now(timezone.utc).isoformat(), "baseline": {"path": str(base), "gzipSha256": sha(payload), "decodedSha256": sha(gzip.decompress(payload)), "accounts": len(original["records"])}, "producer": {"path": str(Path(__file__).resolve()), "sha256": sha(Path(__file__).read_bytes())}, "counts": {"accounts": len(view["records"]), "missingParsedCitationsBefore": len(missing_before), "recoveredCitationFooters": len(deltas), "missingParsedCitationsAfter": len(remaining)}, "deltas": deltas, "remainingMissingCitationAccountIds": remaining, "knownRemainingGapNotes": [{"sourceEntryId": "rosales-original:2003:95:cf25bcc5d095", "status": "original_retained_capture_entry_truncated_before_source_footer", "noCitationInvented": True}, {"sourceEntryId": "rosales-original:1981:69:692011a573c5", "status": "original_retained_entry_has_no_source_footer", "noCitationInvented": True}, {"yearPage": "2005", "status": "four_entries_have_explicit_blank_Source_field", "noCitationInvented": True}], "policy": {"originalCapturesModified": False, "baselineMetadataModified": False, "sourceEntryIdsChanged": False, "newNarrativesIncluded": False, "datesTimesCoordinatesClassificationsChanged": False, "crossSourceIdentityAccepted": False, "recoveredAuthorOnlyCitationMeansFullPublicationKnown": False, "restrictedHumcat1973SourceAcquired": False}, "rebuild": "python scripts/encounter_original_citation_recovery.py --output <new-empty-directory>"}
    view["metadataRecovery"] = {"schemaId": report["schemaId"], "baselineGzipSha256": report["baseline"]["gzipSha256"], "deltaFilename": "citation-recovery-delta.json", "modifiedAccounts": len(deltas)}
    recovered = gzip.compress(json.dumps(view, ensure_ascii=False, separators=(",", ":")).encode(), mtime=0)
    delta_bytes = json.dumps(report, ensure_ascii=False, indent=2).encode() + b"\n"
    if len(recovered) + len(delta_bytes) > 2 * 1024 * 1024:
        raise ValueError("Recovery artifacts exceed 2 MiB task allocation")
    output.mkdir(parents=True, exist_ok=True)
    (output / "citation-recovery-delta.json").write_bytes(delta_bytes)
    (output / "combined-originals-citation-recovered.json.gz").write_bytes(recovered)
    receipt = {"schemaId": "ufo-source-metadata-recovery-receipt-v1", "canonicalMetadataView": str(output / "combined-originals-citation-recovered.json.gz"), "canonicalCorrectionDelta": str(output / "citation-recovery-delta.json"), "retainedBaseline": report["baseline"], "retention": "Retain unique recovery delta and derived metadata view; old original-metadata hashes remain valid for prior reviews. Full narratives remain only in protected original captures.", "rebuild": report["rebuild"], "files": [{"path": str(output / "citation-recovery-delta.json"), "bytes": len(delta_bytes), "sha256": sha(delta_bytes)}, {"path": str(output / "combined-originals-citation-recovered.json.gz"), "bytes": len(recovered), "sha256": sha(recovered)}], "netGrowthBytesExcludingReceipt": len(delta_bytes) + len(recovered), "newFilesOver100MiB": [], "supersededStaging": [], "rollback": "Original combined-originals.json.gz remains protected; runtime unchanged", "cleanup": "No deletion proposed"}
    (output / "lifecycle.json").write_bytes(json.dumps(receipt, ensure_ascii=False, indent=2).encode() + b"\n")
    print(json.dumps({"output": str(output), "counts": report["counts"], "netBytes": sum(path.stat().st_size for path in output.iterdir())}, indent=2))
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, required=True)
    run(ap.parse_args().output)
