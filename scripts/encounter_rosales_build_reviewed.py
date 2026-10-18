"""Build a sparse, additive Rosales identity-review artifact without changing inputs.

Reviewed joins add source-account annotations, not reports, filter labels, UTC,
coordinates, or independently verified incidents. Source narratives stay private.
The existing 24-entry enrichment pilot is retained byte-for-byte at table-row level.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
import re
import time

from encounter_rosales_originals import extract_rows

ROOT = Path(__file__).resolve().parents[1]
SHARED = Path("C:/Users/jarod/Desktop/UFO Timeline map tool")
RESEARCH = SHARED / "data/research/encounter-expansion-20261017"
TABLES = ("sources", "sourceEntries", "cases", "episodes", "entityObservations", "reportLinks")
ID_KEYS = dict(zip(TABLES, ("sourceId", "entryId", "caseId", "episodeId", "entityObservationId", None)))
SCHEMA = "ufo-encounter-enrichment-v1"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def packed(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def read_json(path):
    raw = Path(path).read_bytes()
    return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw.decode("utf-8-sig"))


def file_pin(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=sha(raw))


def keyed(rows, key):
    out = {}
    for row in rows:
        require(row[key] not in out, "Duplicate " + key + ": " + str(row[key]))
        out[row[key]] = row
    return out


def validate_review(review, accounts, queue):
    require(review.get("schemaId") == "ufo-reviewed-rosales-decisions-v1", "Unknown review schema")
    require(isinstance(review.get("reviewer"), str) and review["reviewer"].strip(), "Named reviewer required")
    require(isinstance(review.get("rows"), list) and review["rows"], "No explicit review decisions")
    pairs = set()
    for decision in review["rows"]:
        entry_id, event_id = decision.get("sourceEntryId"), str(decision.get("eventId", ""))
        require(entry_id in accounts and entry_id in queue, "Review entry missing from pinned discovery inputs")
        require(re.fullmatch(r"[1-9]\d*", event_id) and int(event_id) < 2**53, "Invalid native event ID")
        require((entry_id, event_id) not in pairs, "Duplicate reviewed source/report pair")
        pairs.add((entry_id, event_id))
        require(decision.get("status") in {"linked", "candidate", "contradicted"}, "Decision must be explicit linked/candidate/contradicted")
        require(isinstance(decision.get("rationale"), str) and 12 <= len(decision["rationale"].strip()) <= 1200, "Review rationale required, bounded to metadata")
        candidates = [row for row in queue[entry_id].get("nativeCitationLinks", []) if str(row["eventId"]) == event_id]
        require(len(candidates) == 1, "Review must select an existing pinned native citation candidate")
        require(not decision.get("acceptedForRuntime") or decision["status"] == "linked", "Held decision cannot be accepted")
        # Scoped descriptions require explicit entityGroups below. A source Type
        # G or a reviewed identity cannot directly reclassify the filter index.
        forbidden = {"reportedTypes", "entityObservations", "abduction", "abductionCode", "latitude", "longitude", "utcTime"}
        require(not (forbidden & decision.keys()), "Identity review cannot promote encounter classifications or coordinates")
        enums = dict(visibleBeingStatus={"reported_visible", "reported_nonvisual", "uncertain", "not_described"}, contactKind={"forced", "voluntary", "unclear", "none_described"}, onboardStatus={"reported", "not_described", "disputed"}, recallMethod={"conscious", "hypnotic", "retrospective", "mixed", "unknown"}, scope={"dated_episode", "source_account_unsplit"}, craftAssociation={"explicit", "co_reported", "none_reported", "not_established"})
        for field, values in enums.items():
            require(field not in decision or decision[field] in values, "Invalid reviewed " + field)
        require(isinstance(decision.get("identityBasis", []), list), "Identity basis must be a list")
        require(isinstance(decision.get("entityGroups", []), list), "Entity groups must be explicit list")
        if decision.get("entityGroups"):
            require(decision.get("visibleBeingStatus") == "reported_visible", "Nonvisual/uncertain review cannot create visible entity observations")
        for group in decision.get("entityGroups", []):
            require(isinstance(group.get("reportedTypes", []), list), "Reported entity types must be explicit list")
            require(group.get("count") is None or type(group["count"]) is int and group["count"] > 0, "Entity count must be positive integer or unknown")
            require(isinstance(group.get("attributes", []), list), "Entity attributes must be explicit list")
            for attribute in group.get("attributes", []):
                require(attribute.get("attribution") in {"explicit_group", "explicit_individual"}, "Entity attribute attribution required")
                require(isinstance(attribute.get("field"), str) and attribute["field"].strip(), "Entity attribute field required")
                require(isinstance(attribute.get("value"), (str, float, int, bool)) or attribute.get("value") is None, "Entity attribute must be a bounded factual value")
                require(len(str(attribute.get("value", ""))) <= 300, "Entity attributes cannot contain source narratives")
    return True


def verify_sources(decisions, accounts):
    by_capture = defaultdict(list)
    for decision in decisions:
        account = accounts[decision["sourceEntryId"]]
        by_capture[account["capture"]["path"]].append(account)
    pins = []
    for path, selected in sorted(by_capture.items()):
        first = selected[0]
        raw = Path(path).read_bytes()
        require(sha(raw) == first["capture"]["sha256"], "Original capture hash mismatch: " + path)
        require(all(r["capture"]["sha256"] == sha(raw) and r["capture"]["bytes"] == len(raw) for r in selected), "Capture pin disagreement")
        parsed, _ = extract_rows(raw, dict(path=path, sha256=sha(raw), sourceId=first["sourceId"], sourceUrl=first["sourceUrl"], yearPage=first.get("yearPage")))
        parsed = keyed(parsed, "sourceEntryId")
        for account in selected:
            actual = parsed.get(account["sourceEntryId"])
            require(actual is not None, "Original source entry disappeared on replay")
            for field in ("sourceBlockSha256", "narrativeSha256", "nativeEntryNumber", "sourceEntryOrdinal", "sourceUrl", "dateRaw", "dateIso", "datePrecision", "timeRaw", "locationRaw", "sourceCaseIds", "sourceClassificationRaw", "sourceCitationRaw"):
                require(actual.get(field) == account.get(field), "Parsed source pin mismatch: " + field)
        pins.append(dict(path=path, sha256=sha(raw), bytes=len(raw), sourceUrl=first["sourceUrl"]))
    return pins


def verify_native(decisions, queue, chunks):
    by_chunk, selected = defaultdict(list), {}
    for decision in decisions:
        entry_id, event_id = decision["sourceEntryId"], str(decision["eventId"])
        candidate = next(r for r in queue[entry_id]["nativeCitationLinks"] if str(r["eventId"]) == event_id)
        by_chunk[candidate["sourceRef"]["chunk"]].append((entry_id, event_id, candidate))
    pins = []
    for chunk, links in sorted(by_chunk.items()):
        raw = (Path(chunks) / (chunk + ".json")).read_bytes()
        actual_sha = sha(raw)
        rows = json.loads(raw)
        for entry_id, event_id, candidate in links:
            ref = candidate["sourceRef"]
            require(actual_sha == ref["chunkSha256"], "Native chunk hash mismatch: " + chunk)
            index = ref["detailIndex"]
            require(isinstance(index, int) and 0 <= index < len(rows), "Native detail index outside chunk")
            record = rows[index]
            require(str(record["event_id"]) == event_id and record["source"] == candidate["source"] and str(record["source_id"]) == candidate["sourceEventId"], "Native event/source/source_id identity mismatch")
            require(record.get("date_raw") == candidate.get("dateRaw") and record.get("location_raw") == candidate.get("locationRaw"), "Native date/locality changed")
            selected[(entry_id, event_id)] = dict(candidate=candidate, record=record)
        pins.append(dict(chunk=chunk, bytes=len(raw), sha256=actual_sha, path=str(Path(chunks) / (chunk + ".json"))))
    return selected, pins


def append_context(prior, review, accounts, native):
    payload = copy.deepcopy(prior)
    payload["releaseId"] = review.get("releaseId", "encounter-rosales-reviewed-20261017-v1")
    source_ids = {row["sourceId"] for row in payload["sources"]}
    entry_ids = {row["entryId"] for row in payload["sourceEntries"]}
    reviewed_entries = {}
    taxonomy = set(prior["taxonomyKeys"])
    account_annotations = {}
    for decision in review["rows"]:
        external_id = decision["sourceEntryId"]
        account = accounts[external_id]
        suffix = external_id.removeprefix("rosales-original:")
        source_id = "rosales-capture:" + account["capture"]["sha256"][:20]
        entry_id, case_id, episode_id = "entry:rosales:" + suffix, "case:rosales-source:" + suffix, "episode:rosales-account:" + suffix
        annotation_fields = ("visibleBeingStatus", "contactKind", "onboardStatus", "recallMethod", "scope", "craftAssociation", "entityGroups")
        annotation = {field: decision.get(field) for field in annotation_fields}
        if external_id in account_annotations:
            require(account_annotations[external_id] == annotation, "Review has conflicting annotations for one source account")
        else:
            account_annotations[external_id] = annotation
        if external_id not in reviewed_entries:
            require(entry_id not in entry_ids, "Reviewed entry already exists in prior artifact")
            reviewed_entries[external_id] = []
            if source_id not in source_ids:
                source_ids.add(source_id)
                payload["sources"].append(dict(sourceId=source_id, title="Albert Rosales humanoid source catalog · " + str(account.get("yearPage") or "year not established"), url=account["sourceUrl"], kind="archived_original_catalog", captureSha256=account["capture"]["sha256"], captureStatus="captured_and_replayed", rightsStatus="factual_metadata_only_fulltext_reuse_not_established", privacyStatus="source_narratives_and_private_addresses_not_republished"))
            locator = "Entry " + str(account["nativeEntryNumber"]) + "; ordinal " + str(account["sourceEntryOrdinal"])
            if account.get("sourcePageStart"):
                locator += "; page " + str(account["sourcePageStart"])
            if account.get("sourceCaseIds"):
                locator += "; " + ", ".join("HC " + row["value"] for row in account["sourceCaseIds"])
            title = account["locationRaw"] + " · " + account["dateRaw"]
            flags = list(dict.fromkeys(account.get("reviewFlags", []) + decision.get("reviewFlags", []) + ["source_account_not_independent_verified_incident", "review_does_not_reclassify_filter_index"]))
            if decision.get("scope", "source_account_unsplit") == "source_account_unsplit":
                flags.append("source_account_not_split_into_verified_episodes")
            payload["sourceEntries"].append(dict(entryId=entry_id, sourceId=source_id, nativeEntryId=str(account["nativeEntryNumber"]), externalSourceEntryId=external_id, caseId=case_id, episodeId=episode_id, episodeIds=[episode_id], title=title, locator=locator, shortExcerpt="", upstreamCitation=account.get("sourceCitationRaw"), evidenceSha256=account["sourceBlockSha256"], evidenceHashMeaning="compact_original_source_block_text", originalCaptureSha256=account["capture"]["sha256"], narrativeSha256=account["narrativeSha256"], sourceClassificationRaw=account.get("sourceClassificationRaw"), sourceClassificationCodes=account.get("sourceClassificationCodes", []), reviewStatus="reviewed_source_annotations" if decision["status"] == "linked" else "held_identity_review", reviewFlags=flags))
            payload["cases"].append(dict(caseId=case_id, title=title, episodeIds=[episode_id], sourceEntryIds=[entry_id], independentIncidentVerified=False, identityUnit="source_account_not_deduplicated_incident"))
            dated_episode = decision.get("scope", "source_account_unsplit") == "dated_episode"
            payload["episodes"].append(dict(episodeId=episode_id, caseId=case_id, sourceEntryIds=[entry_id], evidenceEntryIds=[entry_id], scope=decision.get("scope", "source_account_unsplit"), contactKind=decision.get("contactKind", "unclear"), onboardStatus=decision.get("onboardStatus", "not_established"), recallMethod=decision.get("recallMethod", "unknown"), visibleBeingStatus=decision.get("visibleBeingStatus", "uncertain"), recallStages=[], reviewFlags=flags, date=dict(raw=account["dateRaw"], precision=account["datePrecision"], startIso=account.get("dateIso") if dated_episode else None, endIso=account.get("dateIso") if dated_episode else None, status="reported_header_not_adjudicated", conflicts=[]), time=dict(raw=account.get("timeRaw"), precision="source_clock_or_period", status="reported_not_verified", utcVerified=False, utcStartMs=None, utcEndMs=None, timezoneProvenance=[], conflicts=[]), site=dict(raw=account["locationRaw"], precision="reported_locality", status="reported_not_verified", sourceVerified=False, lat=None, lon=None)))
            for ordinal, group in enumerate(decision.get("entityGroups", []), 1):
                types = group.get("reportedTypes", [])
                require(set(types) <= taxonomy, "Reviewed entity type outside established taxonomy")
                entity_id = "entity:rosales:" + suffix + ":" + str(ordinal)
                entity_scope = "individual" if group.get("count") == 1 else "group"
                attributes, entity_flags = [], ["reported_source_description_not_verified_species", "source_group_counts_not_independent_incident_totals"]
                for attribute in group.get("attributes", []):
                    result = dict(field=attribute["field"], value=attribute.get("value"), unit=attribute.get("unit"), attribution=attribute["attribution"], entryId=entry_id)
                    if attribute["attribution"] == "explicit_individual" and entity_scope == "group":
                        result["subjectScope"] = "one_unresolved_member"
                        entity_flags.append("individual_attribute_target_not_separately_identified")
                    attributes.append(result)
                payload["entityObservations"].append(dict(entityObservationId=entity_id, episodeId=episode_id, sourceEntryIds=[entry_id], label=group.get("label", "Reviewed source entity group " + str(ordinal)), scope=entity_scope, count=group.get("count"), reportedTypes=types, craftAssociation=decision.get("craftAssociation", "not_established"), attributes=attributes, reviewFlags=list(dict.fromkeys(entity_flags))))
                reviewed_entries[external_id].append(entity_id)
        selected = native[(external_id, str(decision["eventId"]))]
        candidate, original = selected["candidate"], selected["record"]
        flags = list(dict.fromkeys(decision.get("reviewFlags", []) + ["source_review_does_not_reclassify_filter_index"]))
        if candidate.get("dateAgreement") not in {"overlap", "equal", "exact"}:
            flags.append("native_source_date_agreement_requires_separate_review")
        payload["reportLinks"].append(dict(eventId=str(decision["eventId"]), source=candidate["source"], sourceEventId=candidate["sourceEventId"], sourceRef=copy.deepcopy(candidate["sourceRef"]), caseId=case_id, episodeIds=[episode_id], sourceEntryIds=[entry_id], entityObservationIds=reviewed_entries[external_id], status=decision["status"], acceptedForRuntime=decision["status"] == "linked", matchBasis=[dict(field="native_source_id", excerpt=candidate["sourceEventId"]), dict(field="manual_identity_review", excerpt=decision["rationale"])] + [dict(field="reviewed_identity_basis", excerpt=str(value)) for value in decision.get("identityBasis", [])], reviewFlags=flags, originalDateRaw=original.get("date_raw"), originalTimeRaw=original.get("time_raw"), reviewer=decision.get("reviewer", review["reviewer"])))
    policy = payload.setdefault("policy", {})
    require(isinstance(policy, dict), "Prior enrichment policy must remain an object")
    policy.update(reviewedSourceAnnotationsPreserveOriginals=True, encounterFilterClassificationUnchanged=True, newSourceAccountsNotIndependentIncidents=True, newSourceAccountsNotAutomaticallySplitIntoEpisodes=True, newSourceNarrativesNotPublished=True)
    return payload


def validate_payload(payload, prior):
    require(payload.get("schemaId") == SCHEMA and payload.get("catalogCount") == 702893, "Invalid enrichment base contract")
    maps = {}
    for table in TABLES:
        require(payload[table][:len(prior[table])] == prior[table], "Prior pilot table changed: " + table)
        if ID_KEYS[table]:
            maps[table] = keyed(payload[table], ID_KEYS[table])
    pairs = set()
    for link in payload["reportLinks"]:
        pair = (link["eventId"], tuple(link["sourceEntryIds"]))
        require(pair not in pairs, "Duplicate enrichment association")
        pairs.add(pair)
        require(link["status"] in {"linked", "candidate", "contradicted"} and link["acceptedForRuntime"] == (link["status"] == "linked"), "Held association promoted")
        require(link["caseId"] in maps["cases"] and set(link["sourceEntryIds"]) <= maps["sourceEntries"].keys() and set(link["episodeIds"]) <= maps["episodes"].keys(), "Broken association references")
        require(set(link["entityObservationIds"]) <= maps["entityObservations"].keys(), "Broken entity references")
    for episode in payload["episodes"][len(prior["episodes"]):]:
        require(episode["scope"] in {"dated_episode", "source_account_unsplit"}, "Unknown source account scope")
        if episode["scope"] == "source_account_unsplit":
            require(episode["date"]["startIso"] is None and episode["date"]["endIso"] is None, "Unsplit source account cannot imply exact episode dates")
        require(not episode["time"]["utcVerified"] and episode["time"]["utcStartMs"] is None and episode["time"]["utcEndMs"] is None, "Source clock promoted to verified UTC")
        require(not episode["site"]["sourceVerified"] and episode["site"]["lat"] is None and episode["site"]["lon"] is None, "Source locality promoted to exact coordinates")
    taxonomy = set(payload["taxonomyKeys"])
    for entity in payload["entityObservations"][len(prior["entityObservations"]):]:
        require(set(entity["reportedTypes"]) <= taxonomy, "Reviewed entity taxonomy mismatch")
        require(entity["episodeId"] in maps["episodes"] and set(entity["sourceEntryIds"]) <= maps["sourceEntries"].keys(), "Broken entity source references")
        require(maps["episodes"][entity["episodeId"]]["visibleBeingStatus"] == "reported_visible", "Nonvisual review invented visible entities")
        for attribute in entity["attributes"]:
            if attribute["attribution"] == "explicit_individual" and entity["scope"] == "group":
                require(attribute.get("subjectScope") == "one_unresolved_member" and "individual_attribute_target_not_separately_identified" in entity["reviewFlags"], "Individual attribute membership uncertainty was lost")
    return True


def build(review_path, output, originals=RESEARCH / "rosales-originals/combined-originals.json.gz", queue_path=RESEARCH / "review_queue.json.gz", prior_path=ROOT / "data/encounters/enrichment.json.gz", evidence_path=ROOT / "data/encounters/evidence.json.gz", chunks=SHARED / "data/canonical_web/event_chunks"):
    started = time.perf_counter()
    output = Path(output)
    require(not output.exists(), "Output must be a new directory; validated artifacts are protected")
    paths = [Path(review_path), Path(originals), Path(queue_path), Path(prior_path), Path(evidence_path), Path(__file__), Path(__file__).with_name("encounter_rosales_originals.py")]
    inputs = [file_pin(path) for path in paths]
    review = read_json(review_path)
    accounts = keyed(read_json(originals)["records"], "sourceEntryId")
    queue = keyed(read_json(queue_path)["records"], "sourceEntryId")
    prior = read_json(prior_path)
    evidence_bytes = gzip.decompress(Path(evidence_path).read_bytes())
    require(prior.get("baseEvidenceDecodedSha256") == sha(evidence_bytes), "Prior enrichment base evidence hash mismatch")
    validate_review(review, accounts, queue)
    source_pins = verify_sources(review["rows"], accounts)
    native, native_pins = verify_native(review["rows"], queue, chunks)
    payload = append_context(prior, review, accounts, native)
    validate_payload(payload, prior)
    for pin in inputs + source_pins + native_pins:
        require(file_pin(pin["path"]) == {key: pin[key] for key in ("path", "bytes", "sha256")}, "Input changed during build: " + pin["path"])
    decoded = packed(payload)
    compressed = gzip.compress(decoded, mtime=0)
    artifact = dict(file="evidence.json.gz", gzipBytes=len(compressed), gzipSha256=sha(compressed), decodedBytes=len(decoded), decodedSha256=sha(decoded))
    prior_n = len(prior["reportLinks"])
    decisions = payload["reportLinks"][prior_n:]
    counts = dict(prior={table: len(prior[table]) for table in TABLES}, total={table: len(payload[table]) for table in TABLES}, added={table: len(payload[table]) - len(prior[table]) for table in TABLES}, statuses=dict(Counter(row["status"] for row in decisions)), newCanonicalReports=0, changedEncounterClassifications=0, verifiedUtcAdded=0, exactSitesAdded=0)
    manifest = dict(schemaId="ufo-encounter-rosales-reviewed-manifest-v1", releaseId=payload["releaseId"], catalogCount=702893, baseEvidenceDecodedSha256=sha(evidence_bytes), artifact=artifact, counts=counts, inputs=inputs, sourceCapturePins=source_pins, originalChunkPins=native_pins, reviewer=review["reviewer"], policy=payload["policy"], retention=dict(canonical="New additive source identity-review artifact; not automatically promoted", rollback="Existing runtime enrichment and current deployed production/rollback unchanged", superseded=[], newFilesOver100MiB=[], rebuild="Replay this builder with the pinned review, discovery, prior enrichment and shared native inputs into a new empty output", cleanup="No unique source, review or provenance deletion proposed"))
    audit = dict(schemaId="ufo-encounter-rosales-reviewed-audit-v1", status="passed", counts=counts, artifact=artifact, checks=dict(priorPilotRowsPreserved=True, nativeIdentitySourceIdChunkIndexHashPinned=True, originalCaptureAndBlockReplayed=True, heldLinksExcludedFromAccepted=True, identityDoesNotReclassify=True, noNarrativePublication=True, utcAndCoordinatesRemainNull=True, sharedInputsUnchanged=True), elapsedSeconds=round(time.perf_counter() - started, 3))
    output.mkdir(parents=True, exist_ok=False)
    (output / "evidence.json.gz").write_bytes(compressed)
    for name, data in (("manifest.json", manifest), ("audit.json", audit)):
        (output / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    audit["output"] = str(output)
    print(json.dumps(audit, ensure_ascii=False))
    return payload, manifest, audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--originals", type=Path, default=RESEARCH / "rosales-originals/combined-originals.json.gz")
    parser.add_argument("--queue", type=Path, default=RESEARCH / "review_queue.json.gz")
    args = parser.parse_args()
    build(args.review, args.output, originals=args.originals, queue_path=args.queue)
