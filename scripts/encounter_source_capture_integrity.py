"""Audit all retained original source endings and every parser-held block offline."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SHARED = Path("C:/Users/jarod/Desktop/UFO Timeline map tool")
SPEC = importlib.util.spec_from_file_location("prepare", ROOT / "scripts/encounter_review_prepare.py")
PREP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREP)
HELD_REVIEWS = {
    ("rosales_1997", 54): "explicit_source_removed_by_request",
    ("rosales_2002", 43): "explicit_source_removed",
    ("rosales_1975", 252): "explicit_source_removed",
    ("rosales_pdf_1940", 33): "appended_index_of_existing_accounts_not_new_account",
    ("rosales_pdf_1957", 1): "cover_year_and_image_caption_not_account",
    ("rosales_pdf_1983", 72): "empty_year_footer_sentinel_not_account",
    ("rosales_pdf_1984", 56): "empty_year_footer_sentinel_not_account",
    ("rosales_pdf_1994", 279): "recoverable_account_letterspaced_pdf_native_labels",
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def run(output, *, shared=SHARED):
    output = Path(output)
    if output.exists() and any(path.name != "stpetersburg1994-p153.png" for path in output.iterdir()):
        raise ValueError("Protected analysis output exists")
    base = shared / "data/research/encounter-expansion-20261017/rosales-originals"
    raw = (base / "combined-originals.json.gz").read_bytes()
    payload = json.loads(gzip.decompress(raw))
    source_audit_path = base / "combined-originals-audit.json"
    audit_raw = source_audit_path.read_bytes()
    source_audits = {row["sourceId"]: row for row in json.loads(audit_raw)["sourceAudits"]}
    groups = defaultdict(list)
    for row in payload["records"]:
        groups[row["capture"]["path"]].append(row)
    sources, held, recovered = [], [], []
    for path, accounts in sorted(groups.items()):
        capture = Path(path).read_bytes()
        sample = accounts[0]
        digest = sha(capture)
        if digest != sample["capture"]["sha256"]:
            raise ValueError("Capture pin mismatch")
        source_id = sample["sourceId"]
        audit = source_audits[source_id]
        pdf = capture.startswith(b"%PDF")
        text = PREP.source_text(capture)
        boundaries = list(PREP.M.NUMBER.finditer(text))
        if len(boundaries) != audit["numberedBlocks"]:
            raise ValueError("Parser boundary parity changed")
        original_body = re.split(br"<!--\s*FILE ARCHIVED ON", capture, flags=re.I)[0] if not pdf else None
        closed_html = bool(re.search(br"</html\s*>", original_body, re.I)) if not pdf else None
        pdf_eof = b"%%EOF" in capture[-4096:] if pdf else None
        source_result = {"sourceId": source_id, "sourceUrl": sample["sourceUrl"], "capture": {"path": path, "bytes": len(capture), "sha256": digest}, "format": "pdf" if pdf else "html", "parsedAccounts": len(accounts), "numberedBlocks": len(boundaries), "declaredTotals": audit["declaredTotals"], "htmlDocumentClosingTagPresentBeforeWaybackFooter": closed_html, "pdfEofMarkerPresent": pdf_eof, "heldBlockCount": len(audit["heldBlocks"]), "tailStatus": "truncated_native_html_account_evidence" if not pdf and not closed_html else "container_has_expected_closing_marker_not_proof_complete_historical_catalog", "lastParsedAccountId": accounts[-1]["sourceEntryId"], "declaredTotalIsAutomaticallyIncidentCount": False}
        if not pdf and not closed_html:
            source_result["incompleteTailEvidence"] = {"lastAccountMissingSourceCitation": not accounts[-1].get("sourceCitationRaw"), "lastAccountMissingClassification": not accounts[-1].get("sourceClassificationRaw"), "lastNativeTextEndsMidWord": original_body.rstrip().endswith(b"The fi"), "shortEnding": "The fi" if original_body.rstrip().endswith(b"The fi") else "review_required"}
        source_held = []
        for old in audit["heldBlocks"]:
            ordinal = old["ordinal"]
            boundary = boundaries[ordinal - 1]
            block = text[boundary.end():boundaries[ordinal].start() if ordinal < len(boundaries) else len(text)].strip()
            stop = PREP.M.STOP.search(block)
            if stop:
                block = block[:stop.start()].strip()
            block_hash = sha(PREP.M.compact(block).encode())
            if block_hash != old["blockSha256"]:
                raise ValueError("Held source block hash mismatch")
            kind = HELD_REVIEWS[(source_id, ordinal)]
            item = {"sourceId": source_id, "sourceUrl": sample["sourceUrl"], "captureSha256": digest, "nativeEntryNumber": old["nativeEntryNumber"], "sourceEntryOrdinal": ordinal, "sourceBlockSha256": block_hash, "previousParserHoldReason": old["reason"], "manualHoldClassification": kind, "recoverRemovedContent": False, "isRecoverableAccount": kind.startswith("recoverable_account")}
            if kind.startswith("explicit_source_removed"):
                item["removedPlaceholderOnly"] = True
                item["restoreDeletedNarrativeAuthorized"] = False
            if item["isRecoverableAccount"]:
                if source_id != "rosales_pdf_1994" or ordinal != 279:
                    raise ValueError("Unexpected manually reviewed recovered account")
                candidate = {"sourceEntryId": "rosales-original:1994:279:" + block_hash[:12], "sourceId": source_id, "sourceUrl": sample["sourceUrl"], "yearPage": "1994", "sourceEntryOrdinal": ordinal, "nativeEntryNumber": "279", "locationRaw": "St. Petersburg, Russia", "dateRaw": "December 1994", "dateIso": None, "dateStartIso": "1994-12", "datePrecision": "month", "timeRaw": "late evening", "sourceCaseIds": [], "sourceClassificationRaw": "D?", "sourceClassificationCodes": ["D"], "sourceCitationRaw": "http://www.kp.ru/daily/", "sourceBlockSha256": block_hash, "capture": {key: sample["capture"][key] for key in ("path", "sha256", "bytes", "captureUtc", "encoding")}, "sourcePageStart": 153, "sourcePageEnd": 153, "latitude": None, "longitude": None, "utcTime": None, "status": "held_manually_recovered_source_metadata_not_identity_reviewed", "reviewFlags": ["manual_pdf_label_spacing_recovery", "uncertain_source_classification", "generic_upstream_url_without_article_locator", "not_an_independently_verified_incident"], "publicRedistribution": "not_authorized_by_acquisition", "reviewedFactualMetadata": {"reportedWitnessCount": 6, "reportedEntityCount": 1, "reportedAppearance": "woman, white hair/clothing, reported luminosity", "craftAssociation": "co_reported_separate_local_reports_not_shared_vehicle_established", "onboardStatus": "not_described", "recallMethod": "unknown"}, "manualVisualCheck": {"page": 153, "image": str(output / "stpetersburg1994-p153.png"), "status": "native_pdf_page_render_inspected", "citationMeansOriginalArticleRecovered": False}, "existingAccountIdsChanged": False, "includedInPrior10853OverlapCounts": False}
                recovered.append(candidate)
                item["recoveredCandidateId"] = candidate["sourceEntryId"]
            held.append(item)
            source_held.append(kind)
        source_result["heldClassifications"] = source_held
        if audit["declaredTotals"] and not pdf:
            source_result["declaredTotalMinusParsedAccounts"] = max(audit["declaredTotals"]) - len(accounts)
            source_result["sourceRemovalPlaceholders"] = sum(kind.startswith("explicit_source_removed") for kind in source_held)
        if source_id == "rosales_pdf_1942":
            source_result["numberingRestartInterpretation"] = "1941_and_1942_sections_number_separately; last_declared_total35_is1942_section_not_whole59_accounts"
        sources.append(source_result)
    if len(sources) != 73 or len(held) != len(HELD_REVIEWS) or len(recovered) != 1:
        raise ValueError("Unexpected source corpus/held review scope")
    report = {"schemaId": "ufo-original-source-capture-integrity-audit-v1", "generatedAtUtc": datetime.now(timezone.utc).isoformat(), "baseline": {"path": str(base / "combined-originals.json.gz"), "gzipSha256": sha(raw), "sourceAuditPath": str(source_audit_path), "sourceAuditSha256": sha(audit_raw)}, "producer": {"path": str(Path(__file__).resolve()), "sha256": sha(Path(__file__).read_bytes())}, "counts": {"capturesHashVerified": len(sources), "html": sum(row["format"] == "html" for row in sources), "pdf": sum(row["format"] == "pdf" for row in sources), "baselineParsedAccounts": len(payload["records"]), "truncatedHtmlCaptures": sum(row["tailStatus"] == "truncated_native_html_account_evidence" for row in sources), "manuallyInspectedParserHeldBlocks": len(held), "sourceRemovedPlaceholders": sum(row["removedPlaceholderOnly"] for row in held if row.get("removedPlaceholderOnly")), "nonAccountIndexCoverOrFooterBlocks": sum(not row["isRecoverableAccount"] and not row.get("removedPlaceholderOnly") for row in held), "recoverableAdditionalSourceAccounts": len(recovered), "runtimePromotions": 0}, "sources": sources, "heldBlockReviews": held, "policy": {"completenessClaim": "audited_acquired_captures_not_complete_historical_Rosales_catalog", "validPdfOrClosingHtmlMeansHistoricalCompleteness": False, "sourceNumberIsIndependentIncidentId": False, "removedContentRestored": False, "existing10853AccountIdsChanged": False, "existingOverlapCountsChanged": False, "newNetworkFetches": False, "sourceNarrativesRepublished": False}, "rebuild": "python scripts/encounter_source_capture_integrity.py --output <new-directory-containing-optional-native-page153-QA-render>"}
    candidate_payload = {"schemaId": "ufo-manual-held-source-metadata-recovery-v1", "records": recovered, "policy": report["policy"], "baselineParsedAccountsRetained": 10853, "additionalHeldAccounts": 1}
    output.mkdir(parents=True, exist_ok=True)
    for name, value in [("audit.json", report), ("held-account-recovery.json", candidate_payload)]:
        (output / name).write_bytes(json.dumps(value, ensure_ascii=False, indent=2).encode() + b"\n")
    files = [{"path": str(path), "bytes": path.stat().st_size, "sha256": sha(path.read_bytes())} for path in output.iterdir()]
    lifecycle = {"purpose": "Canonical offline all-capture tail and held-block audit plus one manually recovered held source metadata candidate and private native page QA render", "canonicalAudit": str(output / "audit.json"), "canonicalHeldRecovery": str(output / "held-account-recovery.json"), "retainedBaseline": report["baseline"], "retention": "Retain unique source-account recovery and integrity decisions. Page153 render is private review evidence and not published. Prior raw captures, metadata, runtime, production and rollback remain protected.", "files": files, "netGrowthBytesExcludingLifecycle": sum(row["bytes"] for row in files), "newFilesOver100MiB": [], "supersededStaging": [], "cleanup": "No duplicated dataset or superseded staging created", "rebuild": report["rebuild"], "qaRenderRebuild": "pdftoppm -f 153 -l 153 -scale-to 1800 -singlefile -png <retained-rosales1994.pdf> <output>/stpetersburg1994-p153"}
    (output / "lifecycle.json").write_bytes(json.dumps(lifecycle, ensure_ascii=False, indent=2).encode() + b"\n")
    print(json.dumps({"output": str(output), "counts": report["counts"], "netBytes": sum(path.stat().st_size for path in output.iterdir())}, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
