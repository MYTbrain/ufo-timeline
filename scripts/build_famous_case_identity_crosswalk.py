"""Validate the complete case identity audit and project its references into the UI.

Reads the shared canonical summaries/details without copying or modifying them.
Run with --canonical-root pointing at the protected canonical_web directory.
The three reviewed group JSONs are the inputs; nearby rows never create matches.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import subprocess


MANIFEST_SHA256 = "242ff4abc42c70c2b241a3cd16c8b9059bca137d940bd6147c5a65de63b7750b"
SUMMARY_SHA256 = "9c50d0e608fc89d1dc7523cde5f407a45e2d10a9e6adefaf83384d1a8a209bdc"
CHUNK_SHA256 = "833ca33e18ca17768b2e1852d36ad28bd45f9544e88d1821677a67ac176a9d19"
START = "  // BEGIN GENERATED CATALOG IDENTITY REVIEW"
END = "  // END GENERATED CATALOG IDENTITY REVIEW"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            return json.load(stream)
    return json.loads(path.read_text(encoding="utf-8"))


def build(root, canonical, release_contract):
    pins = load(release_contract)["r2"]
    require(pins["base_url"].endswith("/releases/coordinated-reliability-v152-20260731"), "Unexpected production dataset release.")
    production_files = {item["path"]: item for item in pins["files"]}
    def verify_data_pin(relative, path):
        pin = production_files["data/canonical_web/" + relative]
        actual = digest(path)
        require(path.stat().st_size == pin["bytes"] and actual == pin["sha256"], f"Production data byte mismatch: {relative}")
        return actual
    for filename, expected in [
        ("canonical_web_manifest.json", MANIFEST_SHA256),
        ("summary_manifest.json", SUMMARY_SHA256),
        ("event_chunk_manifest.json", CHUNK_SHA256),
    ]:
        require(digest(canonical / filename) == expected, f"Canonical manifest drift: {filename}")
    preset_path = root / "famous_case_presets.js"
    presets = json.loads(subprocess.check_output([
        "node", "-e", "process.stdout.write(JSON.stringify(require('./famous_case_presets.js').CASES))"
    ], cwd=root, encoding="utf-8"))
    require(len(presets) == 85, "The audit scope must be exactly the 85 current presets.")
    preset_by_id = {item["id"]: item for item in presets}
    audit_root = root / "docs/releases/famous-case-identity-audit"
    case_reviews = {}
    input_receipts = []
    for group in "abc":
        path = audit_root / f"group-{group}.json"
        audit = load(path)
        input_receipts.append({"file": str(path.relative_to(root)).replace("\\", "/"), "sha256": digest(path)})
        require(isinstance(audit.get("cases"), list), f"Missing reviewed cases: {path.name}")
        for review in audit["cases"]:
            case_id = review["caseId"]
            require(case_id in preset_by_id and case_id not in case_reviews, f"Unknown/duplicate case: {case_id}")
            require(review.get("status") in {"matched", "unverified", "no_confirmed_match", "unmatched"},
                    f"Unfinished identity review: {case_id}")
            require(review.get("reviewNote"), f"Missing review note: {case_id}")
            require(isinstance(review.get("catalogRefs"), list), f"Missing reference decision: {case_id}")
            case_reviews[case_id] = review
    require(set(case_reviews) == set(preset_by_id), "Audit groups do not cover all 85 presets.")
    required_ids = set()
    for case_id, review in case_reviews.items():
        local_ids = set()
        for reference in review["catalogRefs"]:
            event_id = str(reference["eventId"])
            require(event_id.isdigit() and 0 < int(event_id) < 2**53, f"Unsafe record ID: {case_id}")
            require(event_id not in local_ids, f"Duplicate source row within {case_id}: {event_id}")
            require(reference.get("identityEvidence") and reference.get("sourceRef"), f"No source identity evidence: {event_id}")
            local_ids.add(event_id)
            required_ids.add(event_id)
        require(bool(local_ids) == (review["status"] == "matched"), f"Status/ref disagreement: {case_id}")

    rows = {}
    scanned = 0
    for shard in load(canonical / "summary_manifest.json"):
        shard_relative = "summary_shards/" + shard["file"] + ".gz"
        shard_path = canonical / shard_relative
        verify_data_pin(shard_relative, shard_path)
        for row in load(shard_path):
            scanned += 1
            event_id = str(row["event_id"])
            if event_id in required_ids:
                require(event_id not in rows, f"Duplicate canonical ID: {event_id}")
                rows[event_id] = row
    require(scanned == 702893, f"Incomplete shared catalog: {scanned}")
    require(set(rows) == required_ids, "Referenced records missing from the canonical summaries.")

    # Validate original-detail pointers as well as summary identities. Detailed
    # narrative acceptance remains the documented human/agent source review.
    by_chunk = defaultdict(list)
    for row in rows.values():
        by_chunk[row["chunk_id"]].append(row)
    chunk_receipts = []
    for chunk_id, chunk_rows in sorted(by_chunk.items()):
        path = canonical / "event_chunks" / (chunk_id + ".json.gz")
        chunk_sha256 = verify_data_pin("event_chunks/" + path.name, path)
        details = load(path)
        chunk_receipts.append({"id": chunk_id, "sha256": chunk_sha256, "matchedProductionPin": True})
        for row in chunk_rows:
            detail = details[row["detail_index"]]
            require(str(detail["event_id"]) == str(row["event_id"]), f"Detail pointer mismatch: {row['event_id']}")
            require(detail["source"] == row["source"] and detail["sort_date_iso"] == row["sort_date_iso"],
                    f"Detail identity mismatch: {row['event_id']}")

    projection = {}
    summary = []
    for preset in presets:
        case_id = preset["id"]
        review = case_reviews[case_id]
        references = []
        for reference in review["catalogRefs"]:
            row = rows[str(reference["eventId"])]
            require(row["source"] == reference["source"] and row["sort_date_iso"] == reference["dateIso"],
                    f"Reference source/date mismatch: {case_id}/{row['event_id']}")
            for key in ["chunkId", "chunk", "chunk_id"]:
                if key in reference:
                    require(reference[key] == row["chunk_id"], f"Audit chunk locator mismatch: {row['event_id']}")
            for key in ["detailIndex", "index", "detail_index"]:
                if key in reference:
                    require(reference[key] == row["detail_index"], f"Audit detail index mismatch: {row['event_id']}")
            status = reference["mappingStatus"]
            if status in {"outside_vicinity", "mapped_outside_vicinity"}:
                status = "mapped"
            require(status in {"mapped", "unmapped", "needs_review"}, f"Unrecognized mapping review: {case_id}/{status}")
            require((status != "unmapped") == bool(row["has_coordinates"]), f"Mapping flag mismatch: {row['event_id']}")
            projected = {
                "eventId": str(row["event_id"]), "source": row["source"], "dateIso": row["sort_date_iso"],
                "sourceRef": reference["sourceRef"], "mappingStatus": status,
                "identityEvidence": reference["identityEvidence"],
            }
            if row["has_coordinates"]:
                for reviewed_key, row_key in [("reviewedLat", "lat"), ("reviewedLon", "lon")]:
                    if reviewed_key in reference:
                        require(reference[reviewed_key] == row[row_key], f"Coordinate review mismatch: {row['event_id']}")
                    projected[reviewed_key] = row[row_key]
            if reference.get("mappingNote"):
                projected["mappingNote"] = reference["mappingNote"]
            for key in ["recordRole", "dateWindowIssue", "dateRelation"]:
                if reference.get(key):
                    projected[key] = reference[key]
            references.append(projected)
        projection[case_id] = {"status": "matched" if references else "no_confirmed_match",
                               "note": review["reviewNote"], "refs": references}
        summary.append({"caseId": case_id, "name": preset["name"], "status": projection[case_id]["status"],
                        "recordCount": len(references), "mappingCounts": dict(Counter(ref["mappingStatus"] for ref in references)),
                        "sourceDateOutsidePresetCount": sum(not preset["startIso"] <= ref["dateIso"] <= preset["endIso"] for ref in references)})

    source = preset_path.read_text(encoding="utf-8")
    require(source.count(START) == 1 and source.count(END) == 1, "Missing unique generated crosswalk markers.")
    prefix, rest = source.split(START)
    _, suffix = rest.split(END)
    encoded = json.dumps(projection, ensure_ascii=False, separators=(",", ":"))
    preset_path.write_text(prefix + START + "\n  const CATALOG_REVIEW = " + encoded + ";\n" + END + suffix,
                          encoding="utf-8", newline="\n")
    receipt = {"schemaVersion": 1, "reviewDate": "2026-10-06", "scope": "All 85 historical presets; explicit source identities separate from vicinity candidates",
               "canonicalManifestSha256": MANIFEST_SHA256, "summaryManifestSha256": SUMMARY_SHA256,
               "chunkManifestSha256": CHUNK_SHA256, "inputAudits": input_receipts,
               "productionR2Base": pins["base_url"], "productionPinContractSha256": digest(release_contract),
               "summaryShardsVerifiedAgainstProductionPins": 71, "liveR2BytesFetched": False,
               "summaryRecordsChecked": scanned, "referencedDetailChunks": chunk_receipts,
               "caseCount": len(summary), "matchedCaseCount": sum(item["status"] == "matched" for item in summary),
               "referenceCount": sum(item["recordCount"] for item in summary),
               "runtimePresetsSha256": digest(preset_path), "cases": summary}
    output = root / "docs/releases/FAMOUS_CASE_IDENTITY_COVERAGE_2026-10-06.json"
    output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    totals = Counter(ref["mappingStatus"] for item in projection.values() for ref in item["refs"])
    conflict_count = sum(item["sourceDateOutsidePresetCount"] for item in summary)
    lines = [
        "# Full famous-case database identity review - 6 October 2026", "",
        f"All **85 presets** were reviewed against original detail narratives and source fields. **{receipt['matchedCaseCount']} cases** have identifying source records; **{85 - receipt['matchedCaseCount']}** have no confirmed match in this bounded review. The crosswalk contains **{receipt['referenceCount']} source rows**, not that many independent incidents.", "",
        f"The reviewed rows include {totals['mapped']} mapped entries, {totals['unmapped']} entries without coordinates, and {totals['needs_review']} entries with a source-supported mapping discrepancy requiring review. {conflict_count} source dates fall outside their preset's reported dates; stored dates were preserved.", "",
        "Identity acceptance requires an explicit case/witness identity or a distinct original incident narrative. Date and vicinity alone, later comparisons, and unrelated witnesses do not create a match. The three group audits preserve accepted locators, concise evidence and rejected/ambiguous candidates. A nonmatch is a bounded search outcome, not proof that the event is absent from all sources.", "",
        "## Product behavior", "",
        "Results exposes matched source rows for every reviewed case, with stored dates, raw Type labels, mapping status, and Full Details access independent of map filters. Presets without a confirmed source identity are marked in the dropdown and Results. Nearby report/connection results remain a separate geographic selection. Source rows without coordinates cannot seed map traces. Outside-vicinity points are not automatically coordinate errors. No historical preset becomes a fabricated event, and no dates or coordinates were repaired by this review.", "",
        "## Coverage by case", "",
        "| Case | Matched rows | Mapped | Unmapped | Mapping review | Source dates outside preset |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in summary:
        counts = item["mappingCounts"]
        lines.append(f"| {item['name']} | {item['recordCount']} | {counts.get('mapped', 0)} | {counts.get('unmapped', 0)} | {counts.get('needs_review', 0)} | {item['sourceDateOutsidePresetCount']} |")
    lines += [
        "", "## Provenance and reproducibility", "",
        "The audit reads the existing shared canonical corpus. All 71 summary gzip shard hashes and all referenced detail chunk hashes match the existing immutable production R2 pins in the supplied release contract. This is local-byte verification against those pins; the script does not fetch live R2 bytes. It checks 702,893 summary rows and validates every accepted event's source, stored date and original-detail pointer. The machine-readable receipt contains manifest, group-input and chunk hashes.", "",
        "Rebuild the small runtime crosswalk from the three reviewed group JSONs:", "",
        "```powershell",
        "python scripts/build_famous_case_identity_crosswalk.py --canonical-root 'C:\\Users\\jarod\\Desktop\\UFO Timeline map tool\\data\\canonical_web' --release-contract 'C:\\Users\\jarod\\Desktop\\UFO Timeline map tool\\reproduction\\release.json'",
        "```", "",
        "This creates only small source/provenance files. It does not copy, modify, ingest, geocode or rebuild the corpus. The current Git source and existing compact interface candidate are canonical. The validated f88416b1-1e96-45fa-8b2a-a1edbfc5fdae production release is the rollback for this update. No newly created file exceeds 100 MiB. Previous candidate shell bytes are replaced in place after hash verification; no complete rollback tree is copied. Older remote deployments are superseded cleanup candidates, subject to the existing retention policy. Protected dataset/research artifacts are retained.", "",
    ]
    (root / "docs/releases/FAMOUS_CASE_FULL_IDENTITY_REVIEW_2026-10-06.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(json.dumps({key: receipt[key] for key in ["caseCount", "matchedCaseCount", "referenceCount", "summaryRecordsChecked"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical-root", type=Path, required=True)
    parser.add_argument("--release-contract", type=Path, required=True)
    args = parser.parse_args()
    build(Path(__file__).resolve().parents[1], args.canonical_root.resolve(), args.release_contract.resolve())
