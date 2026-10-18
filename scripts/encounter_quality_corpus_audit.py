"""Audit encounter metadata without inventing observations or copying the corpus.

Units remain separate: native indexed reports, archived source accounts and reviewed
source-context objects. Missing sparse-index fields do not prove missing source text.
Reads the existing effective summary shards and timing overlay in place; full native
detail chunks are deliberately not scanned or copied by this metadata pass.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SHARED = Path("C:/Users/jarod/Desktop/UFO Timeline map tool")
UNKNOWN = {"", "unknown", "not known", "not given", "n/a", "na", "none", "?", "unspecified", "not reported"}
COUNTRY_ONLY = {"usa", "us", "united states", "united states of america", "uk", "united kingdom", "england", "scotland", "wales", "france", "spain", "italy", "germany", "russia", "ussr", "canada", "australia", "brazil", "argentina", "mexico", "portugal", "chile", "peru", "sweden", "norway", "finland", "poland", "zimbabwe", "south africa", "japan", "china", "india", "new zealand", "belgium", "malaysia"}
POSITIVE_ABDUCTION = {"source_reported", "narrative_reported"}
MAX_TOTAL_OUTPUT = 10 * 1024 * 1024


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def compact(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def load_pinned(path, expected_hash=None):
    path = Path(path)
    raw = path.read_bytes()
    digest = sha(raw)
    if expected_hash and digest != expected_hash:
        raise ValueError("Input hash mismatch: " + str(path))
    decoded = gzip.decompress(raw) if path.name.endswith(".gz") else raw
    return json.loads(decoded), {"path": str(path.resolve()), "bytes": len(raw), "sha256": digest, "decodedSha256": sha(decoded)}


def present(value):
    return value is not None and str(value).strip().casefold() not in UNKNOWN


def raw_clock_kind(value):
    """Classify header availability only; never treat a clock-like string as verified UTC."""
    text = str(value or "").strip()
    if not present(text):
        return "missing_or_unknown"
    if re.search(r"\b(?:midnight|noon)\b", text, re.I):
        return "named_clock_boundary_unvalidated"
    if re.search(r"\b\d{1,2}\s*:\s*\d{2}\b|\b\d{1,2}\s*(?:a\.?m\.?|p\.?m\.?)\b|\b\d{4}\b", text, re.I):
        return "clock_like_raw_unvalidated"
    return "period_or_other_raw"


def citation_signals(value):
    """Signals for research triage, not a source authenticity or credibility score."""
    text = str(value or "").strip()
    return {
        "citationPresent": present(text),
        "urlMentioned": bool(re.search(r"https?://|www\.", text, re.I)),
        "pageOrIssueLocatorMentioned": bool(re.search(r"\b(?:p{1,2}\.\s*\d|pages?\s+\d|vol(?:ume)?\.?\s*\d|no\.?\s*\d|issue\s*\d)|#\s*\d", text, re.I)),
        "personalCommunicationMentioned": bool(re.search(r"personal\s+(?:communication|investigation|interview)|letter\s+(?:to|from)|e-?mail|private\s+communication", text, re.I)),
        "anonymousMentioned": bool(re.search(r"\banonym(?:ous|ity)\b", text, re.I)),
        "quotationOrRetellingMentioned": bool(re.search(r"\bquoting\b|\bquoted\b|\bciting\b|\bcited\b|\bvia\b|\bretold\b", text, re.I)),
        "bareNamedCustodian": text.casefold() in {"nuforc", "mufon", "cufos", "nicap", "cau s", "caus", "cun"},
        "placeholderOrCrossReferenceOnly": bool(text and (re.fullmatch(r"[?.\-\s]+", text) or re.fullmatch(r"(?:see\s+)?(?:above|previous|same(?:\s+as\s+above)?|ibid\.?|op\.?\s*cit\.?)", text, re.I))),
    }


def count_fields(rows, fields):
    return {key: sum(present(row.get(key)) for row in rows) for key in fields}


def summarize_registry(rows):
    return {
        "rows": len(rows),
        "withAnyGap": sum(bool(row["gaps"]) for row in rows),
        "gapCounts": dict(sorted(Counter(gap for row in rows for gap in row["gaps"]).items())),
        "priorityCounts": dict(sorted(Counter(row["priority"] for row in rows).items())),
    }


def effective_report_links(enrichment):
    """Apply only the explicitly reviewed identity revision accepted by runtime.

    Source rows remain immutable. Supplemental findings do not establish a new
    association merely because they share an event, case, or source URL.
    """
    reviews = enrichment.get("qualityReviews") or []
    if not isinstance(reviews, list):
        raise ValueError("Invalid quality review collection")
    entries = {row["entryId"]: row for row in enrichment.get("sourceEntries", [])}
    episodes = {row["episodeId"]: row for row in enrichment.get("episodes", [])}
    sources = {row["sourceId"] for row in enrichment.get("sources", [])}
    review_ids, revisions, by_subject = set(), {}, defaultdict(list)
    links = enrichment["reportLinks"]
    for review in reviews:
        subject = entries.get(review.get("subjectEntryId"))
        episode = episodes.get(review.get("episodeId"))
        if not review.get("reviewId") or review["reviewId"] in review_ids or not subject or not episode or subject.get("caseId") != review.get("caseId") or episode.get("caseId") != review.get("caseId") or review["episodeId"] not in (subject.get("episodeIds") or [subject.get("episodeId")]):
            raise ValueError("Quality review target identity mismatch")
        if review.get("classificationEffect") != "none" or review.get("disposition") not in {"additional_source_context", "conflicting_version", "identity_conflict", "source_chain_dependency"}:
            raise ValueError("Unsupported quality review effect")
        ids = review.get("sourceEntryIds")
        if not isinstance(ids, list) or not ids or any(entry_id not in entries or entries[entry_id].get("caseId") != review["caseId"] or entries[entry_id].get("episodeId") != review["episodeId"] or entries[entry_id].get("sourceId") not in sources for entry_id in ids):
            raise ValueError("Quality review supplemental source identity mismatch")
        findings = review.get("findings")
        if not isinstance(findings, list) or not findings or any(not fact.get("field") or not fact.get("text") or fact.get("sourceEntryId") not in ids for fact in findings):
            raise ValueError("Quality review finding attribution missing")
        revision = review.get("associationRevision")
        if revision:
            matched = [(i, link) for i, link in enumerate(links) if str(link["eventId"]) == str(revision.get("eventId")) and link.get("caseId") == review["caseId"] and review["subjectEntryId"] in link.get("sourceEntryIds", [])]
            if len(matched) != 1:
                raise ValueError("Quality identity revision has no unique prior association")
            position, prior = matched[0]
            if revision.get("previousStatus") != "candidate" or prior.get("status") != revision["previousStatus"] or prior.get("acceptedForRuntime") is not False or revision.get("status") != "linked" or review.get("disposition") != "additional_source_context" or review.get("associationEffect") != "reviewed_identity_resolution_prior_row_retained" or len(revision.get("identityBasis") or []) < 2 or not any(fact.get("field") == "episode_identity" for fact in findings) or position in revisions:
                raise ValueError("Unreviewed or conflicting quality identity revision")
            revisions[position] = review
        review_ids.add(review["reviewId"])
        by_subject[review["subjectEntryId"]].append(review["reviewId"])
    result = []
    for position, link in enumerate(links):
        current = dict(link)
        current["originalStatus"] = link["status"]
        current["originalAcceptedForRuntime"] = link.get("acceptedForRuntime") is True
        current["qualityReviewIds"] = [review_id for entry_id in link.get("sourceEntryIds", []) for review_id in by_subject.get(entry_id, [])]
        if position in revisions:
            current["status"] = "linked"
            current["acceptedForRuntime"] = True
            current["associationRevisionReviewId"] = revisions[position]["reviewId"]
        result.append(current)
    return result


def height_guard_index(evidence, attribute_reviews=None, expected_hash=None):
    if attribute_reviews is None:
        return {}
    if attribute_reviews.get("schemaId") != "ufo-encounter-attribute-reviews-v1" or not expected_hash or attribute_reviews.get("baseEvidenceDecodedSha256") != expected_hash:
        raise ValueError("Height-review base evidence pin mismatch")
    indexed = {str(row["eventId"]): row for row in evidence["rows"]}
    guards = {}
    for review in attribute_reviews.get("rows", []):
        event_id = str(review.get("eventId"))
        row = indexed.get(event_id)
        if event_id in guards or not row or review.get("action") != "withhold_height_feet" or row.get("source") != review.get("source") or row.get("sourceEventId") != review.get("sourceEventId") or row.get("sourceRef") != review.get("sourceRef") or row.get("heightFeet") != review.get("originalHeightFeet") or not review.get("reason") or not review.get("reportedMetricText"):
            raise ValueError("Height-review native source identity or measurement mismatch")
        guards[event_id] = review
    return guards


def native_registry(evidence, summaries, origins, enrichment, timing, attribute_reviews=None, base_hash=None):
    accepted_links = defaultdict(list)
    held_links = defaultdict(list)
    for link in effective_report_links(enrichment):
        (accepted_links if link.get("acceptedForRuntime") else held_links)[str(link["eventId"])].append(link)
    # Freeze sparse maps before any lookup: defaultdict reads must not create
    # apparent reviewed coverage for records that have never been reviewed.
    accepted_links, held_links = dict(accepted_links), dict(held_links)
    timing_schema = {name: i for i, name in enumerate(timing["rowSchema"])}
    timing_rows = {str(row[timing_schema["eventId"]]): row for row in timing["rows"] if str(row[timing_schema["eventId"]]) in summaries}
    excluded = {str(row["eventId"]): row for row in timing.get("excludedDates", [])}
    codes = timing["codes"]["evidence"]
    origin_by_id = {str(row["eventId"]): row for row in origins["rows"]}
    height_guards = height_guard_index(evidence, attribute_reviews, base_hash)
    rows, source_stats = [], defaultdict(lambda: defaultdict(Counter))
    categories = {"datePrecision": Counter(), "locationPrecision": Counter(), "coordinateSource": Counter(), "rawTimeAvailability": Counter(), "runtimeTimingKind": Counter(), "runtimeTimingPrecision": Counter(), "runtimeTimingIntervalWidth": Counter(), "reviewFlags": Counter(), "beingType": Counter(), "craftAssociation": Counter(), "abductionStatus": Counter()}
    base_fields = Counter()
    for row in evidence["rows"]:
        event_id = str(row["eventId"])
        summary = summaries[event_id]
        if summary["chunk_id"] != row["sourceRef"]["chunk"] or summary["detail_index"] != row["sourceRef"]["detailIndex"] or summary["source"] != row["source"]:
            raise ValueError("Summary identity differs from encounter pin: " + event_id)
        origin = origin_by_id[event_id]
        if origin["sourceRef"] != row["sourceRef"]:
            raise ValueError("Label origin native pin differs: " + event_id)
        positive = bool(row["beingTypes"]) or row["abductionStatus"] in POSITIVE_ABDUCTION
        mapped = bool(summary.get("has_coordinates"))
        clock_kind = raw_clock_kind(summary.get("time_raw"))
        timing_row = timing_rows.get(event_id)
        timing_code = codes[timing_row[timing_schema["evidenceCode"]]] if timing_row is not None else None
        clock_supported = bool(timing_code and timing_code.get("timePrecision") != "whole_source_calendar_day")
        gaps = []
        if not mapped:
            gaps.append("unmapped")
        if summary.get("location_precision") in {"country", "state", "province", "unknown", "approximate"}:
            gaps.append("location_coarser_than_city")
        if not present(summary.get("location_raw")):
            gaps.append("missing_location_raw")
        if summary.get("date_precision") != "exact_day":
            gaps.append("date_not_exact_day")
        if clock_kind == "missing_or_unknown":
            gaps.append("raw_time_missing_or_unknown")
        if not clock_supported:
            gaps.append("no_clock_supported_runtime_interval")
        if event_id in excluded:
            gaps.append("occurrence_date_excluded_by_source_timing_policy")
        if row["beingTypes"] == ["unspecified"]:
            gaps.append("being_type_unspecified")
        if row["abductionStatus"] in POSITIVE_ABDUCTION and not row["beingTypes"]:
            gaps.append("reported_abduction_without_indexed_being_description")
        if row["abductionStatus"] == "ambiguous":
            gaps.append("abduction_classification_ambiguous")
        if event_id not in accepted_links:
            gaps.append("no_accepted_reviewed_source_context")
        if event_id in held_links:
            gaps.append("held_source_identity_or_episode_link")
        if event_id in height_guards:
            gaps.append("height_withheld_due_to_source_unit_or_subject_conflict")
        if any(link.get("status") == "contradicted" for link in held_links.get(event_id, [])):
            priority = "resolve_explicit_source_identity_conflict"
        elif event_id in height_guards:
            priority = "resolve_reported_height_unit_or_subject_conflict"
        elif event_id in held_links:
            priority = "resolve_held_source_identity"
        elif not positive:
            priority = "review_ambiguous_only_report_not_positive_encounter"
        elif not mapped and present(summary.get("location_raw")):
            priority = "research_unmapped_report_with_reported_locality"
        elif row["beingTypes"] == ["unspecified"]:
            priority = "recover_unspecified_being_description"
        elif "reported_abduction_without_indexed_being_description" in gaps:
            priority = "review_abduction_source_and_being_description"
        elif not clock_supported:
            priority = "recover_source_occurrence_time"
        elif event_id not in accepted_links:
            priority = "review_upstream_source_chain"
        else:
            priority = "reviewed_context_available_remaining_fields_unresolved"
        state = {"eventId": event_id, "source": row["source"], "sourceEventId": row["sourceEventId"], "sourceRef": row["sourceRef"], "positiveEncounterClassification": positive,
                 "dateRaw": summary.get("date_raw"), "datePrecision": summary.get("date_precision"), "locationRaw": summary.get("location_raw"), "locationPrecision": summary.get("location_precision"), "mapped": mapped,
                 "timeRaw": summary.get("time_raw"), "rawTimeAvailability": clock_kind, "clockSupportedRuntimeInterval": clock_supported, "runtimeTimingKind": timing_code.get("kind") if timing_code else None,
                 "beingTypes": row["beingTypes"], "abductionStatus": row["abductionStatus"], "craftAssociation": row["craftAssociation"], "rawIndexedHeightFeet": row.get("heightFeet"), "effectiveIndexedHeightFeet": row.get("heightFeet") if event_id not in height_guards else None, "heightReview": {key: height_guards[event_id][key] for key in ("action", "reason", "reportedMetricText")} if event_id in height_guards else None, "acceptedSourceContextLinks": len(accepted_links.get(event_id, [])), "heldSourceContextLinks": len(held_links.get(event_id, [])), "qualityReviewIds": sorted({review_id for link in accepted_links.get(event_id, []) + held_links.get(event_id, []) for review_id in link.get("qualityReviewIds", [])}), "gaps": gaps, "priority": priority}
        rows.append(state)
        values = {"datePrecision": summary.get("date_precision") or "missing", "locationPrecision": summary.get("location_precision") or "missing", "coordinateSource": summary.get("coordinate_source") or "missing", "rawTimeAvailability": clock_kind, "runtimeTimingKind": timing_code.get("kind") if timing_code else "no_interval", "runtimeTimingPrecision": timing_code.get("timePrecision") if timing_code else "no_interval", "craftAssociation": row["craftAssociation"] or "no_indexed_being_association", "abductionStatus": row["abductionStatus"] or "not_indexed"}
        for key, value in values.items():
            categories[key][value] += 1
            source_stats[row["source"]][key][value] += 1
        categories["reviewFlags"].update(row.get("reviewFlags") or [])
        categories["beingType"].update(row["beingTypes"])
        if timing_row is not None:
            width = timing_row[timing_schema["utcEndMs"]] - timing_row[timing_schema["utcStartMs"]] + 1
            bucket = next((label for limit, label in [(60_000, "up_to_1_minute"), (3_600_000, "up_to_1_hour"), (8 * 3_600_000, "up_to_8_hours"), (24 * 3_600_000, "up_to_24_hours")] if width <= limit), "over_24_hours")
            categories["runtimeTimingIntervalWidth"][bucket] += 1
        for key, condition in {"mapped": mapped, "unmapped": not mapped, "positiveEncounterUnion": positive, "ambiguousOnlyNoBeing": not positive, "hasIndexedHeightFeet": present(row.get("heightFeet")), "hasIndexedUniform": present(row.get("uniform")), "acceptedReviewedSourceContext": event_id in accepted_links, "heldReviewedSourceContext": event_id in held_links, "clockSupportedRuntimeInterval": clock_supported, "wholeCalendarDayRuntimeInterval": bool(timing_code and timing_code.get("timePrecision") == "whole_source_calendar_day"), "sourceCodedBeingLabel": bool(origin.get("sourceBeingMask")), "narrativeBeingLabel": bool(origin.get("narrativeBeingMask")), "unattributedBeingLabel": bool(origin.get("unknownBeingMask")), "sourceAndNarrativeOverlapBeingLabel": bool(origin.get("bothBeingMask")), "nativeSourceRefPresent": bool(row.get("sourceRef")), "indexedEvidenceExcerptPresent": any(present(item.get("excerpt")) for item in row["evidence"])}.items():
            base_fields[key] += bool(condition)
        base_fields["rawIndexedHeightFeetAvailable"] += row.get("heightFeet") is not None
        base_fields["effectiveIndexedHeightFeetAvailable"] += row.get("heightFeet") is not None and event_id not in height_guards
        base_fields["heightWithheldByReviewedSourceConflict"] += event_id in height_guards
        base_fields["indexedUniformFieldPresentIncludingExplicitNegativesOrUnknowns"] += "uniform" in row
    return rows, {"unit": "native_source_report_row", "rows": len(rows), "fieldCoverage": dict(base_fields), "categories": {key: dict(value) for key, value in categories.items()}, "bySource": {source: {key: dict(value) for key, value in data.items()} for source, data in source_stats.items()}, **summarize_registry(rows)}


def original_registry(originals, enrichment, source_queue):
    entries = originals["records"]
    review_status = {}
    for entry in enrichment["sourceEntries"]:
        external_id = entry.get("externalSourceEntryId")
        if external_id:
            links = [link for link in effective_report_links(enrichment) if entry["entryId"] in link.get("sourceEntryIds", [])]
            review_status[external_id] = [link["status"] for link in links]
    old_queue = {row["sourceEntryId"]: row for row in source_queue["records"]}
    hc_groups, narrative_groups = defaultdict(list), defaultdict(list)
    for row in entries:
        for item in row.get("sourceCaseIds", []):
            if item.get("scheme") == "rosales_hc" and str(item.get("value", "")).isdigit():
                hc_groups[str(int(item["value"]))].append(row["sourceEntryId"])
        if row.get("narrativeSha256"):
            narrative_groups[row["narrativeSha256"]].append(row["sourceEntryId"])
    colliding_hc = {key: ids for key, ids in hc_groups.items() if len(ids) > 1}
    collision_ids = {entry_id for ids in colliding_hc.values() for entry_id in ids}
    categories = {key: Counter() for key in ["datePrecision", "rawTimeAvailability", "reviewFlag", "sourceClassification", "reviewStatus", "discoveryPriority"]}
    coverage, citation_coverage, rows, captures = Counter(), Counter(), [], {}
    for row in entries:
        entry_id = row["sourceEntryId"]
        citation = citation_signals(row.get("sourceCitationRaw"))
        citation_coverage.update(key for key, available in citation.items() if available)
        flags = row.get("reviewFlags") or []
        clock_kind = raw_clock_kind(row.get("timeRaw"))
        queue = old_queue.get(entry_id, {})
        reviewed = review_status.get(entry_id, [])
        gaps = []
        if row.get("datePrecision") != "day":
            gaps.append("date_not_exact_day")
        if row.get("datePrecision") in {"invalid", "unparsed", "historical_or_range"}:
            gaps.append("date_requires_source_review")
        if clock_kind == "missing_or_unknown":
            gaps.append("reported_time_missing_or_unknown")
        elif clock_kind == "period_or_other_raw":
            gaps.append("reported_time_period_or_unparsed")
        if "location_not_specific" in flags or not present(row.get("locationRaw")) or str(row.get("locationRaw") or "").strip().casefold() in COUNTRY_ONLY:
            gaps.append("location_not_specific_or_unknown")
        if not citation["citationPresent"]:
            gaps.append("missing_upstream_citation")
        if citation["placeholderOrCrossReferenceOnly"]:
            gaps.append("upstream_citation_placeholder_or_cross_reference_only")
        if citation["bareNamedCustodian"]:
            gaps.append("upstream_custodian_citation_without_report_locator")
        if "missing_source_classification" in flags:
            gaps.append("missing_source_classification")
        if "uncertain_source_classification" in flags:
            gaps.append("source_classification_explicitly_uncertain")
        if entry_id in collision_ids:
            gaps.append("nonunique_numeric_hc_identifier")
        if (row.get("narrativeCharacters") or 0) < 120:
            gaps.append("short_source_narrative_requires_context_review")
        if "linked" not in reviewed:
            gaps.append("not_identity_linked_to_native_report")
        if "contradicted" in reviewed:
            gaps.append("explicit_native_source_identity_conflict")
            priority = "resolve_explicit_source_identity_conflict"
        elif entry_id in collision_ids:
            priority = "resolve_source_identifier_collision"
        elif reviewed and "linked" not in reviewed:
            priority = "resolve_held_source_identity"
        elif "missing_upstream_citation" in gaps:
            priority = "recover_missing_upstream_source"
        elif "date_requires_source_review" in gaps:
            priority = "review_unparsed_invalid_or_historical_date"
        elif "location_not_specific_or_unknown" in gaps:
            priority = "research_source_locality"
        elif citation["bareNamedCustodian"]:
            priority = "recover_original_custodian_report_locator"
        elif queue.get("nativeCitationLinks") and "linked" not in reviewed:
            priority = "review_existing_native_citation_candidate"
        elif "linked" in reviewed:
            priority = "reviewed_identity_available_source_details_remain_unverified"
        else:
            priority = "review_upstream_source_and_episode_identity"
        capture = row.get("capture") or {}
        if capture.get("path"):
            captures[capture["path"]] = {key: capture[key] for key in ("path", "bytes", "sha256")}
        categories["datePrecision"][row.get("datePrecision") or "missing"] += 1
        categories["rawTimeAvailability"][clock_kind] += 1
        categories["reviewFlag"].update(flags)
        categories["sourceClassification"].update(row.get("sourceClassificationCodes") or ["missing_or_unrecognized"])
        categories["reviewStatus"]["linked" if "linked" in reviewed else "contradicted" if "contradicted" in reviewed else "held" if reviewed else "not_yet_identity_reviewed"] += 1
        categories["discoveryPriority"][queue.get("priority") or "not_in_previous_discovery_queue"] += 1
        for key, available in {"dateRawPresent": present(row.get("dateRaw")), "locationRawPresent": present(row.get("locationRaw")), "timeRawPresent": present(row.get("timeRaw")), "capturePinPresent": bool(capture.get("sha256")), "sourceBlockPinPresent": bool(row.get("sourceBlockSha256")), "narrativeHashPresent": bool(row.get("narrativeSha256")), "numericHcPresent": bool(row.get("sourceCaseIds")), "identityReviewed": bool(reviewed), "acceptedIdentityLink": "linked" in reviewed, "verifiedSiteCoordinate": row.get("latitude") is not None and row.get("longitude") is not None, "verifiedUtc": row.get("utcTime") is not None, "sourceCitationPresent": citation["citationPresent"]}.items():
            coverage[key] += bool(available)
        rows.append({"sourceEntryId": entry_id, "sourceId": row["sourceId"], "sourceUrl": row["sourceUrl"], "sourceCaseIds": row.get("sourceCaseIds", []), "dateRaw": row.get("dateRaw"), "datePrecision": row.get("datePrecision"), "locationRaw": row.get("locationRaw"), "timeRaw": row.get("timeRaw"), "sourceCitationRaw": row.get("sourceCitationRaw"), "citationSignals": citation, "narrativeCharacters": row.get("narrativeCharacters"), "captureSha256": capture.get("sha256"), "sourceBlockSha256": row.get("sourceBlockSha256"), "identityReviewStatuses": reviewed, "nativeCitationCandidateEventIds": [link["eventId"] for link in queue.get("nativeCitationLinks", [])], "existingDiscoveryPriority": queue.get("priority"), "gaps": gaps, "priority": priority})
    return rows, {"unit": "archived_original_source_account_not_deduplicated_incident", "rows": len(rows), "fieldCoverage": dict(coverage), "citationSignals": dict(citation_coverage), "categories": {key: dict(value) for key, value in categories.items()}, "numericHcCollisionGroups": len(colliding_hc), "accountsInNumericHcCollisionGroups": len(collision_ids), "extraNumericHcRowsBeyondFirst": sum(len(ids) - 1 for ids in colliding_hc.values()), "exactNarrativeHashRepeatGroups": sum(len(ids) > 1 for ids in narrative_groups.values()), "captures": sorted(captures.values(), key=lambda item: item["path"]), **summarize_registry(rows)}


def reviewed_context_summary(enrichment, evidence_ids):
    raw_links = enrichment["reportLinks"]
    links = effective_report_links(enrichment)
    accepted = [row for row in links if row.get("acceptedForRuntime")]
    accepted_ids = {str(row["eventId"]) for row in accepted}
    accepted_episode_ids = {value for link in accepted for value in link.get("episodeIds", [])}
    accepted_entity_ids = {value for link in accepted for value in link.get("entityObservationIds", [])}
    episodes = enrichment["episodes"]
    entities = enrichment["entityObservations"]
    def episode_stats(rows):
        return {"rows": len(rows), "recallMethod": dict(Counter(row.get("recallMethod") or "missing" for row in rows)), "scope": dict(Counter(row.get("scope") or "missing" for row in rows)), "contactKind": dict(Counter(row.get("contactKind") or "missing" for row in rows)), "onboardStatus": dict(Counter(row.get("onboardStatus") or "missing" for row in rows)), "datePrecision": dict(Counter((row.get("date") or {}).get("precision") or "missing" for row in rows)), "dateConflictObjects": sum(bool((row.get("date") or {}).get("conflicts")) for row in rows), "siteSourceVerified": sum(bool((row.get("site") or {}).get("sourceVerified")) for row in rows), "siteLatLonPresent": sum((row.get("site") or {}).get("lat") is not None and (row.get("site") or {}).get("lon") is not None for row in rows), "utcVerified": sum(bool((row.get("time") or {}).get("utcVerified")) for row in rows), "rawTimeAvailable": sum(present((row.get("time") or {}).get("raw")) for row in rows), "visibleBeingStatus": dict(Counter(row.get("visibleBeingStatus") or "not_in_earlier_schema" for row in rows))}
    def entity_stats(rows):
        fields = Counter()
        for row in rows:
            fields.update(set(attribute["field"] for attribute in row.get("attributes", [])))
        return {"rows": len(rows), "withReportedCount": sum(row.get("count") is not None for row in rows), "withAnyAttributes": sum(bool(row.get("attributes")) for row in rows), "attributes": sum(len(row.get("attributes", [])) for row in rows), "observationsWithAttributeField": dict(fields), "attributeAttribution": dict(Counter(attribute.get("attribution") or "missing" for row in rows for attribute in row.get("attributes", []))), "craftAssociation": dict(Counter(row.get("craftAssociation") or "missing" for row in rows))}
    return {"unit": "reviewed_source_context_objects_not_independent_incidents", "tableCounts": {key: len(enrichment[key]) for key in ["sources", "sourceEntries", "cases", "episodes", "entityObservations", "reportLinks"]}, "rawReportLinkStatus": dict(Counter(row["status"] for row in raw_links)), "rawAcceptedReportLinks": sum(row.get("acceptedForRuntime") is True for row in raw_links), "rawHeldReportLinks": sum(row.get("acceptedForRuntime") is not True for row in raw_links), "effectiveReportLinkStatus": dict(Counter(row["status"] for row in links)), "reportLinkStatus": dict(Counter(row["status"] for row in links)), "acceptedReportLinks": len(accepted), "acceptedUniqueNativeReports": len(accepted_ids), "acceptedNativeReportsInEncounterIndex": len(accepted_ids & evidence_ids), "heldReportLinks": len(links) - len(accepted), "qualityReviewCount": len(enrichment.get("qualityReviews") or []), "qualityFindings": sum(len(row.get("findings") or []) for row in enrichment.get("qualityReviews") or []), "identityAssociationRevisions": sum(bool(row.get("associationRevision")) for row in enrichment.get("qualityReviews") or []), "sourceKind": dict(Counter(row.get("kind") or "missing" for row in enrichment["sources"])), "allEpisodes": episode_stats(episodes), "acceptedLinkedEpisodes": episode_stats([row for row in episodes if row["episodeId"] in accepted_episode_ids]), "allEntityObservations": entity_stats(entities), "acceptedLinkedEntityObservations": entity_stats([row for row in entities if row["entityObservationId"] in accepted_entity_ids]), "sourceEntriesWithUpstreamCitation": sum(present(row.get("upstreamCitation")) for row in enrichment["sourceEntries"]), "sourceEntriesWithEvidenceHash": sum(bool(row.get("evidenceSha256")) for row in enrichment["sourceEntries"])}


def balanced_queue(rows, group_key, limit=240):
    """Round robin through priority and source strata rather than famous-case bias."""
    groups = defaultdict(list)
    for row in rows:
        groups[(row["priority"], row.get(group_key, "unknown"))].append(row)
    result = []
    for index in range(max((len(group) for group in groups.values()), default=0)):
        for key in sorted(groups):
            if index < len(groups[key]):
                result.append(groups[key][index])
                if len(result) >= limit:
                    return result
    return result


def run(output, *, root=ROOT, shared=SHARED, originals_path=None):
    output, root, shared = Path(output), Path(root), Path(shared)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Refusing to overwrite a nonempty analysis directory")
    inputs = []
    def read(path, expected=None):
        value, pin = load_pinned(path, expected)
        inputs.append(pin)
        return value
    manifest = read(root / "data/encounters/manifest.json")
    evidence = read(root / "data/encounters/evidence.json.gz", manifest["artifact"]["gzipSha256"])
    origins = read(root / "data/encounters/label_origins.json.gz", manifest["labelOrigins"]["gzipSha256"])
    enrichment = read(root / "data/encounters/enrichment.json.gz", manifest["enrichment"]["gzipSha256"])
    if origins["baseEvidenceDecodedSha256"] != manifest["artifact"]["decodedSha256"] or enrichment["baseEvidenceDecodedSha256"] != manifest["artifact"]["decodedSha256"]:
        raise ValueError("Enrichment/label origins do not pin the current base evidence")
    config = read(root / "data/app_config.json")
    timing = read(root / "data/trace_chronology/evidence.json.gz", config["traceChronologyEvidenceGzipSha256"])
    originals_path = Path(originals_path) if originals_path else shared / "data/research/encounter-expansion-20261017/rosales-originals/combined-originals.json.gz"
    originals = read(originals_path)
    if originals.get("metadataRecovery"):
        recovery = originals["metadataRecovery"]
        delta_name = recovery.get("deltaFilename") or ""
        if Path(delta_name).name != delta_name:
            raise ValueError("Citation delta must be a sibling filename")
        delta = read(originals_path.parent / delta_name)
        if delta["baseline"]["gzipSha256"] != recovery.get("baselineGzipSha256"):
            raise ValueError("Citation recovery baseline hash mismatch")
        by_id = {row["sourceEntryId"]: row for row in originals["records"]}
        for change in delta["deltas"]:
            row = by_id.get(change["sourceEntryId"])
            if not row or row.get("sourceCitationRaw") != change.get("recoveredValue") or row.get("sourceBlockSha256") != change.get("sourceBlockSha256"):
                raise ValueError("Citation recovery metadata/locator mismatch")
    source_queue = read(shared / "data/research/encounter-expansion-20261017/review_queue.json.gz")
    plan = read(root / "releases/workspace-analysis-20261008/delivery_plan.json")
    ids = {str(row["eventId"]) for row in evidence["rows"]}
    if len(ids) != len(evidence["rows"]):
        raise ValueError("Duplicate base encounter event IDs")
    summaries, total_summary_rows = {}, 0
    all_summary_ids, duplicate_summary_ids = set(), set()
    shard_pins = []
    for item in plan["uploads"]:
        if not re.search(r"/summary_shards/summary_\d+\.json\.gz$", item["key"]):
            continue
        rows, pin = load_pinned(item["source"], item["sha256"])
        if pin["bytes"] != item["bytes"]:
            raise ValueError("Summary shard byte count mismatch")
        shard_pins.append(pin)
        total_summary_rows += len(rows)
        for row in rows:
            event_id = str(row["event_id"])
            numeric_id = int(event_id)
            if numeric_id in all_summary_ids:
                duplicate_summary_ids.add(numeric_id)
            all_summary_ids.add(numeric_id)
            if event_id in ids:
                if event_id in summaries:
                    raise ValueError("Duplicate target encounter summary row")
                summaries[event_id] = row
    if set(summaries) != ids or total_summary_rows != evidence["catalogCount"]:
        raise ValueError("Incomplete effective summary coverage")
    native_rows, native_summary = native_registry(evidence, summaries, origins, enrichment, timing, manifest.get("attributeReviews"), manifest["artifact"]["decodedSha256"])
    original_rows, original_summary = original_registry(originals, enrichment, source_queue)
    reviewed_summary = reviewed_context_summary(enrichment, ids)
    if manifest["enrichment"].get("counts", {}).get("acceptedReportLinks") != reviewed_summary["acceptedReportLinks"] or manifest["enrichment"].get("counts", {}).get("heldReportLinks") != reviewed_summary["heldReportLinks"]:
        raise ValueError("Effective enrichment association counts disagree with runtime manifest")
    for pin in original_summary["captures"]:
        path = Path(pin["path"])
        raw = path.read_bytes()
        if len(raw) != pin["bytes"] or sha(raw) != pin["sha256"]:
            raise ValueError("Original source capture no longer matches pin: " + str(path))
    native_ref_groups = Counter((row["sourceRef"]["chunk"], row["sourceRef"]["detailIndex"]) for row in evidence["rows"])
    native_id_groups = Counter((row["source"], row["sourceEventId"]) for row in evidence["rows"])
    integrity = {"catalogSummaryUniqueIds": len(all_summary_ids), "catalogSummaryDuplicateIds": len(duplicate_summary_ids), "nativeEncounterUniqueIds": len(ids), "nativeEncounterDuplicateIds": len(evidence["rows"]) - len(ids), "nativeEncounterRepeatedDetailRefGroups": sum(count > 1 for count in native_ref_groups.values()), "nativeEncounterRepeatedSourceEventIdGroups": sum(count > 1 for count in native_id_groups.values()), "originalSourceUniqueEntryIds": len({row["sourceEntryId"] for row in originals["records"]}), "originalSourceRepeatedBlockHashGroups": sum(count > 1 for count in Counter(row["sourceBlockSha256"] for row in originals["records"]).values()), "allBaseIndexRowsHaveMatchingSummaryIdentity": True, "allBaseIndexRowsHaveMatchingLabelOriginNativePin": True, "nativeDetailsNotReopenedThisMetadataPass": True}
    report = {"schemaId": "ufo-encounter-quality-corpus-audit-v1", "generatedAtUtc": datetime.now(timezone.utc).isoformat(), "scope": {"nativeEncounterRows": len(native_rows), "archivedRosalesSourceAccounts": len(original_rows), "fullCatalogSummaryRowsRead": total_summary_rows, "effectiveSummaryShardsRead": len(shard_pins), "nativeDetailChunksRead": 0, "sourceCapturesHashVerified": len(original_summary["captures"])}, "integrity": integrity, "nativeEncounterIndex": native_summary, "archivedOriginalAccounts": original_summary, "reviewedContext": reviewed_summary, "inputPins": inputs, "effectiveSummaryPins": shard_pins,
              "policy": {"missingMeans": "not_available_in_audited_metadata_layer_not_a_negative_observation", "sourceCountsAreIndependent": False, "sourceAccountEqualsIndependentIncident": False, "mappedMeansVerifiedSite": False, "chronologyMeansMeasuredCraftMovement": False, "calendarDayUtcEnvelopeMeansKnownClock": False, "sparseLabelAbsenceMeansNoBeing": False, "baseEvidenceLabelsModified": False, "runtimeModified": False, "privateNarrativesRepublished": False, "sourceBibliographyAuthenticityNotAutomated": True, "citationSignalsAreResearchTriageNotCredibilityScores": True, "nativeCitationPinsRevalidatedAgainstFullDetailsThisRun": False, "existingSourceCapturesHashVerified": True, "currentTimingOverlayApplied": True},
              "limits": ["The base encounter index retains classification evidence, not complete witnesses, episode narratives or bibliographies. Index missingness is not asserted to be source missingness.", "All 10,853 Rosales accounts are parsed source accounts; their quantities cannot be added to the native encounter rows or interpreted as independently corroborated incidents.", "Original capture and block hashes establish retrieval/provenance, not historical truth or source independence.", "Clock-like raw strings are availability signals only. Runtime clock-supported UTC envelopes are separated from whole-calendar-day envelopes and verified UTC is not asserted.", "Summary coordinate availability is kept separate from reviewed source-verified sites; neither city centroids nor source-provided points are independently validated by this audit.", "Source witness counts, photographic/physical evidence custody, hypnosis status and exact entity traits are not guessed where the source has not received a manual episode-level review.", "Research queue ordering balances source and issue strata, rather than ranking plausibility or evidential credibility."],
              "rebuild": {"producer": str(Path(__file__).resolve()), "producerSha256": sha(Path(__file__).read_bytes()), "command": "python scripts/encounter_quality_corpus_audit.py --output <new-empty-directory> --originals \"" + str(originals_path) + "\"", "inputsSharedInPlace": True}, "originalSourceMetadataRecovery": originals.get("metadataRecovery"), "runtimeAttributeReviewCount": len((manifest.get("attributeReviews") or {}).get("rows") or []), "currentEffectiveQualityReviewsApplied": True}
    registry = {"schemaId": "ufo-encounter-quality-gap-registry-v1", "nativeSourceReports": native_rows, "archivedOriginalSourceAccounts": original_rows, "unitSeparationRequired": True, "narrativesIncluded": False}
    queue = {"schemaId": "ufo-encounter-quality-research-queue-v1", "selection": "round_robin_priority_by_source_strata_not_confidence_rank", "nativeSourceReportSample": balanced_queue(native_rows, "source"), "archivedOriginalAccountSample": balanced_queue(original_rows, "sourceId"), "completeQueueIsGapRegistry": True, "sourceAbsenceIsNotEventAbsence": True}
    files = {"audit.json": json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8") + b"\n", "gap-registry.json.gz": gzip.compress(compact(registry), mtime=0), "research-queue.json.gz": gzip.compress(compact(queue), mtime=0)}
    if sum(map(len, files.values())) > MAX_TOTAL_OUTPUT:
        raise ValueError("Output exceeds the declared 10 MiB task budget")
    output.mkdir(parents=True, exist_ok=True)
    for name, raw in files.items():
        (output / name).write_bytes(raw)
    lifecycle = {"schemaId": "ufo-research-storage-lifecycle-v1", "purpose": "Canonical encounter corpus metadata missingness and source-research triage audit", "canonical": str(output.resolve()), "retention": "Retain unique derived audit, gap registry, research queue and input pins; originals and previous enrichment remain protected in place", "rollback": {"runtime": "No runtime mutation; current runtime enrichment remains canonical for the site", "priorEnrichment": str(shared / "data/research/encounter-enrichment-pilot-20261013/validated/reviewed/evidence.json.gz")}, "supersededStaging": [], "newFilesLargerThan100MiB": [], "cleanup": "No superseded generated artifacts were created; no deletion proposed", "rebuild": report["rebuild"], "files": [{"path": str((output / name).resolve()), "bytes": len(raw), "sha256": sha(raw)} for name, raw in files.items()], "netDiskGrowthBytesExcludingLifecycle": sum(map(len, files.values())), "nativeInputsCopied": False}
    (output / "lifecycle.json").write_bytes(json.dumps(lifecycle, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")
    print(json.dumps({"output": str(output), "scope": report["scope"], "nativeFieldCoverage": native_summary["fieldCoverage"], "originalFieldCoverage": original_summary["fieldCoverage"], "netBytes": sum(path.stat().st_size for path in output.iterdir())}, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--originals", type=Path, help="Optional source-metadata view, e.g. the source-pinned citation-recovered 10,853-account artifact")
    args = parser.parse_args()
    run(args.output, originals_path=args.originals)


if __name__ == "__main__":
    main()
