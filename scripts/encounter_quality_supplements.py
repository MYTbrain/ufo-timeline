"""Attach reviewed additional-source findings without rewriting catalog evidence.

The six prior enrichment tables remain exact prefixes. Explicit identity revisions
are separate from preserved prior decisions; reviews cannot change classifications,
populate UTC, or invent a mapped site.
Original documents stay in the private research archive; only bounded, attributed
factual metadata and public source links enter the runtime artifact.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path

TABLES = ("sources", "sourceEntries", "cases", "episodes", "entityObservations", "reportLinks")
DISPOSITIONS = {"additional_source_context", "conflicting_version", "identity_conflict", "source_chain_dependency"}
FIELDS = {"date", "time", "place", "recall_method", "recall_stage", "entity_description", "entity_measurement", "episode_identity", "source_chain", "investigation", "context"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def packed(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def load(path):
    raw = Path(path).read_bytes()
    return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw.decode("utf-8-sig"))


def enrich(prior, review, *, verify_captures=True):
    require(review.get("schemaId") == "ufo-encounter-quality-review-v1", "Unknown quality review schema")
    require(sha(packed(prior)) == review.get("priorContentSha256"), "Quality review prior changed")
    require(isinstance(review.get("reviewer"), str) and review["reviewer"].strip(), "Named reviewer required")
    require(isinstance(review.get("reviews"), list) and review["reviews"], "No reviewed findings")
    require(not prior.get("qualityReviews"), "This batch requires the unmodified pinned prior")
    payload = copy.deepcopy(prior)
    source_ids = {row["sourceId"] for row in prior["sources"]}
    source_hashes = {row["sourceId"]: row.get("captureSha256") for row in prior["sources"]}
    entries = {row["entryId"]: row for row in prior["sourceEntries"]}
    episodes = {row["episodeId"]: row for row in prior["episodes"]}
    cases = {row["caseId"] for row in prior["cases"]}
    seen_reviews, capture_pins, new_entries = set(), [], {}
    for source in review.get("sources", []):
        require(set(source) <= {"sourceId", "title", "url", "kind", "capture", "rightsStatus", "privacyStatus", "sourceDate", "dependency"}, "Unexpected source field")
        require(source.get("sourceId") and source["sourceId"] not in source_ids, "Source identity collision")
        require(isinstance(source.get("title"), str) and len(source["title"]) <= 240, "Bounded source title required")
        require(isinstance(source.get("url"), str) and source["url"].startswith(("https://", "http://")), "Public source URL required")
        pin = source.get("capture", {})
        require(set(pin) == {"path", "sha256", "bytes"}, "Exact private capture pin required")
        if verify_captures:
            raw = Path(pin["path"]).read_bytes()
            require(len(raw) == pin["bytes"] and sha(raw) == pin["sha256"], "Additional-source capture changed")
        capture_pins.append(copy.deepcopy(pin))
        item = {key: copy.deepcopy(value) for key, value in source.items() if key != "capture"}
        item.update(captureSha256=pin["sha256"], captureStatus="captured", rightsStatus=source.get("rightsStatus", "bounded_factual_metadata_only_no_fulltext_republication"), privacyStatus=source.get("privacyStatus", "public_historical_material_identity_and_addresses_minimized"))
        payload["sources"].append(item)
        source_ids.add(source["sourceId"])
        source_hashes[source["sourceId"]] = pin["sha256"]
    for entry in review.get("sourceEntries", []):
        require(set(entry) <= {"entryId", "sourceId", "caseId", "episodeId", "title", "locator", "nativeEntryId", "upstreamCitation", "evidenceSha256", "evidenceHashMeaning", "reviewFlags"}, "Unexpected source entry field")
        require(entry.get("entryId") and entry["entryId"] not in entries, "Source entry identity collision")
        require(entry.get("sourceId") in source_ids and entry.get("caseId") in cases, "Unknown additional source/case")
        require(entry.get("episodeId") in episodes and episodes[entry["episodeId"]]["caseId"] == entry["caseId"], "Additional source episode/case mismatch")
        require(isinstance(entry.get("locator"), str) and 1 <= len(entry["locator"]) <= 300, "Source locator required")
        require(isinstance(entry.get("title"), str) and 1 <= len(entry["title"]) <= 240, "Source entry title required")
        require(isinstance(entry.get("evidenceSha256"), str) and len(entry["evidenceSha256"]) == 64, "Source evidence hash required")
        require(entry.get("evidenceHashMeaning") == "captured_source_bytes" and entry["evidenceSha256"] == source_hashes[entry["sourceId"]], "Entry must pin its captured source bytes")
        item = copy.deepcopy(entry)
        item.update(episodeIds=[entry["episodeId"]], reviewStatus="reviewed_additional_source", shortExcerpt="")
        payload["sourceEntries"].append(item)
        entries[entry["entryId"]] = item
        new_entries[entry["entryId"]] = item
    payload["qualityReviews"] = []
    for finding in review["reviews"]:
        require(set(finding) <= {"reviewId", "subjectEntryId", "caseId", "episodeId", "sourceEntryIds", "disposition", "findings", "rationale", "reviewer", "associationRevision"}, "Unexpected finding field; core evidence cannot be changed")
        rid = finding.get("reviewId")
        require(rid and rid not in seen_reviews, "Quality review identity collision")
        seen_reviews.add(rid)
        subject = entries.get(finding.get("subjectEntryId"))
        require(subject and subject["entryId"] not in new_entries, "Review must target a preserved source entry")
        require(finding.get("caseId") == subject["caseId"] and finding.get("episodeId") in subject.get("episodeIds", [subject.get("episodeId")]), "Review target identity mismatch")
        require(finding.get("disposition") in DISPOSITIONS, "Explicit review disposition required")
        refs = finding.get("sourceEntryIds", [])
        require(refs and len(set(refs)) == len(refs) and all(key in new_entries and new_entries[key]["caseId"] == finding["caseId"] and new_entries[key]["episodeId"] == finding["episodeId"] for key in refs), "Review evidence must reference added sources for its exact case/episode")
        require(isinstance(finding.get("findings"), list) and 1 <= len(finding["findings"]) <= 8, "Bounded reviewed facts required")
        for fact in finding["findings"]:
            require(set(fact) == {"field", "text", "sourceEntryId"}, "Each fact needs field, text and source attribution")
            require(fact["field"] in FIELDS and fact["sourceEntryId"] in refs, "Fact evidence reference missing")
            require(isinstance(fact["text"], str) and 1 <= len(fact["text"]) <= 650, "Fact text must be bounded metadata")
        require(isinstance(finding.get("rationale"), str) and 10 <= len(finding["rationale"]) <= 700, "Review rationale required")
        item = copy.deepcopy(finding)
        item["reviewer"] = finding.get("reviewer", review["reviewer"])
        item["classificationEffect"] = "none"
        item["associationEffect"] = "none_prior_status_preserved"
        revision = finding.get("associationRevision")
        if revision:
            require(set(revision) == {"eventId", "previousStatus", "status", "identityBasis"}, "Explicit association revision required")
            require(revision["previousStatus"] == "candidate" and revision["status"] == "linked", "Only explicitly resolved candidate identity can be revised")
            links = [row for row in prior["reportLinks"] if row["eventId"] == revision["eventId"] and row["caseId"] == finding["caseId"] and finding["subjectEntryId"] in row["sourceEntryIds"]]
            require(len(links) == 1 and links[0]["status"] == revision["previousStatus"] and links[0]["acceptedForRuntime"] is False, "Association prior identity/status changed")
            require(finding["disposition"] == "additional_source_context" and any(row["field"] == "episode_identity" for row in finding["findings"]), "Association revision needs explicit source-backed identity resolution")
            require(isinstance(revision["identityBasis"], list) and len(revision["identityBasis"]) >= 2, "Multiple independent identity fields required")
            item["associationEffect"] = "reviewed_identity_resolution_prior_row_retained"
        payload["qualityReviews"].append(item)
    used = {key for item in payload["qualityReviews"] for key in item["sourceEntryIds"]}
    require(used == set(new_entries), "Additional-source entries must all support reviewed findings")
    revisions = [row["associationRevision"] for row in payload["qualityReviews"] if row.get("associationRevision")]
    require(len({row["eventId"] for row in revisions}) == len(revisions), "Multiple revisions for one report are not supported in this batch")
    source_words = {}
    for item in payload["qualityReviews"]:
        for fact in item["findings"]:
            sid = new_entries[fact["sourceEntryId"]]["sourceId"]
            source_words[sid] = source_words.get(sid, 0) + len(fact["text"].split())
    require(all(words <= 200 for words in source_words.values()), "Additional-source factual summaries exceed the per-source budget")
    for key in TABLES:
        require(payload[key][:len(prior[key])] == prior[key], "Preserved enrichment changed: " + key)
    require(payload["reportLinks"] == prior["reportLinks"], "Research cannot rewrite preserved report-link decisions")
    payload["releaseId"] = review.get("releaseId", "encounter-quality-reviewed-20261017-v1")
    payload["qualityReviewPolicy"] = "Additional-source metadata preserves competing versions and source dependence; it does not establish truth, independent incidents, UTC, coordinates, or new classifications."
    audit = dict(schemaId="ufo-encounter-quality-supplement-audit-v1", priorContentSha256=sha(packed(prior)), outputContentSha256=sha(packed(payload)), reviewedAccounts=len({row["subjectEntryId"] for row in payload["qualityReviews"]}), reviews=len(payload["qualityReviews"]), findings=sum(len(row["findings"]) for row in payload["qualityReviews"]), addedSources=len(payload["sources"])-len(prior["sources"]), addedSourceEntries=len(new_entries), associationRevisions=len(revisions), effectiveAcceptedLinks=sum(row["acceptedForRuntime"] is True for row in prior["reportLinks"])+len(revisions), counts={key: len(payload[key]) for key in TABLES}, priorTablesPreserved=True, reportLinksUnchanged=True, baseClassificationsUnchanged=True, capturePins=capture_pins)
    return payload, audit


def build(prior_path, review_path, output):
    output = Path(output)
    require(not output.exists(), "Protected output exists")
    prior_raw, review_raw = Path(prior_path).read_bytes(), Path(review_path).read_bytes()
    prior, review = load(prior_path), load(review_path)
    payload, audit = enrich(prior, review)
    require(Path(prior_path).read_bytes() == prior_raw and Path(review_path).read_bytes() == review_raw, "Review inputs changed while building")
    output.mkdir(parents=True)
    decoded = packed(payload)
    compressed = gzip.compress(decoded, mtime=0)
    (output / "evidence.json.gz").write_bytes(compressed)
    audit.update(priorPath=str(Path(prior_path).resolve()), priorGzipSha256=sha(prior_raw), reviewPath=str(Path(review_path).resolve()), reviewSha256=sha(review_raw), gzipSha256=sha(compressed), decodedSha256=sha(decoded), gzipBytes=len(compressed), decodedBytes=len(decoded))
    (output / "audit.json").write_bytes((json.dumps(audit, indent=2) + "\n").encode())
    return audit


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prior", type=Path, required=True)
    ap.add_argument("--review", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    print(json.dumps(build(args.prior, args.review, args.output), indent=2))
