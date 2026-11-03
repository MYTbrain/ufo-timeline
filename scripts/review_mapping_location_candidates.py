"""Admit source-supported locality references from the retained unmapped audit.

Every input receives a decision. This reads immutable source details and current
summary guards; it never edits the corpus. Only native NUFORC/MUFON observation
location fields are admitted automatically. Gazetteer matches identify a named
locality, not an observer, object, landing site, or precise sighting coordinate.
All narrative text is screened for displacement, media, travel, and conflicting
roles. A held decision is an unresolved review task, not evidence of no location.
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
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.recover_mapping_locations import (
    EvidenceWriter, GUARD_FIELDS, SUPPORTED_FEATURES, distance_km,
    json_bytes, name_key, pin, text,
)

SCHEMA = "ufo-qualified-locality-source-review-v1"
NATIVE_LOCATION_FIELDS = {"nuforc": "Location", "mufon": "Location of Event"}
MISSING_ADMIN = "state_or_province_missing_requires_source_review"
COMPOUND_HOLD = "compound_places_require_source_review"
EXACT_SCREEN = "small_primary_name_locality_cluster_requires_source_review"

# These are conservative admission gates, not a claim that every matching word
# invalidates the source. Matches remain in the held ledger for direct review.
RISK_PATTERNS = {
    "observer_travel_or_route": (
        r"\b(?:driving|travell?ing|road trip|en route|on route|roadside|interstate|"
        r"highway|motorway|freeway|hiking|kayaking|canoeing|sailing|camping|"
        r"on vacation|on holiday|on a trip|returning from|headed (?:to|for)|"
        r"heading (?:to|toward|towards)|on (?:a|the) (?:bus|train|boat|ship)|"
        r"aboard|on board|in.flight|on a plane|in an airplane|commercial flight|"
        r"flight from|flying from|on (?:my|our|the) way|got out of (?:my|our|the) car|"
        r"(?:in|from) (?:my|our|the) (?:car|truck|vehicle)|car window|"
        r"(?:captain|pilot) of (?:an? |the )?(?:commercial |private )?(?:airliner|airplane|aircraft)|"
        r"first officer|flight attendant|cockpit|(?:i|we) (?:was|were) flying|"
        r"a bordo|dans un avion|en un avi[oó]n|no avi[aã]o)\b"
    ),
    "distance_or_remote_locality": (
        r"\b(?:\d+(?:\.\d+)?|several|many|few|twenty|thirty|forty|fifty)\s*"
        r"(?:km|mi|miles?|kilomet(?:er|re)s?)\s+(?:north|south|east|west|outside|from|away)\b|"
        r"\b(?:outskirts|remote area|remote location|offshore|border crossing|paso fronterizo)\b"
    ),
    "facility_or_noncity_observer_role": (
        r"\b(?:military base|marine base|air force base|army base|naval base|"
        r"usmc|on guard duty|airbase|offshore platform|oil platform|"
        r"military installation|national park|state park|national forest|campground)\b"
    ),
    "remote_media_or_republication": (
        r"\b(?:live.?feed|web.?cam|google (?:earth|maps)|satellite image|"
        r"news telecast|newspaper article|documentary|tv show|television show|"
        r"youtube|you tube|nasa (?:video|image|photo|feed)|"
        r"international space station|ISS live|not a witness|not an eyewitness|"
        r"did not witness|didn't witness|read about|read this (?:story|report)|"
        r"forwarded (?:an? |the )?(?:email|image|photo|video)|"
        r"photo(?:graph)? of (?:the |a )?(?:moon|mars|sun)|"
        r"(?:watching|viewing) (?:an? |the )?(?:video|film|broadcast|stream)|"
        r"(?:detected|found|noticed|discovered|visible) (?:only )?(?:on|in) (?:the |my |some )?(?:photos?|pictures?|images?)|"
        r"(?:revising|reviewing|examining|editing) (?:some |the |my )?(?:sunset )?(?:pictures?|photos?|images?)|"
        r"(?:did not|didn't|never) (?:actually |physically )?see (?:the |an? )?object)\b"
    ),
    "nonobservational_or_disputed_account": (
        r"\b(?:hoax|fiction|no sighting|not a sighting|not my (?:sighting|report)|"
        r"this is (?:an? |the )?(?:story|article|legend)|"
        r"i (?:heard|read) (?:about|this)|someone (?:told|sent) me|"
        r"i was told|we were told|second.hand account)\b"
    ),
    "explicit_location_qualification_or_conflict": (
        r"\b(?:location (?:is|was) (?:wrong|incorrect|unknown)|"
        r"wrong (?:city|country|state|location)|not (?:in|at) the (?:city|town)|"
        r"could not (?:enter|select|find) (?:the |my |a )?(?:city|town|location)|"
        r"nearest (?:city|town)|closest (?:city|town)|"
        r"(?:i|we) (?:was|were|am|are) (?:near|outside|between)|"
        r"(?:sighting|observed|witnessed|happened|occurred) (?:was |is )?(?:near|outside|between))\b"
    ),
    "multiple_event_or_observer_locations": (
        r"\b(?:on (?:two|three|four|several|multiple|different) occasions|"
        r"(?:several|multiple|different) (?:sightings|locations|cities|towns)|"
        r"(?:another|second|third) sighting|(?:lives|lived) in [\w '-]{2,40} and (?:he|she|they) could see)\b"
    ),
}
COMPILED_RISKS = {key: re.compile(pattern, re.I) for key, pattern in RISK_PATTERNS.items()}

# Explicit observer clauses are additionally checked against retained populated
# place names. This does not use a mapped report as a geographic authority.
OBSERVER_PLACE = re.compile(
    r"\b(?:I|we)\s+(?:(?:was|were|am|are|had been|have been)\s+)?"
    r"(?:located|staying|living|visiting|vacationing|stationed|working|born|residing)?\s*"
    r"(?:in|at|from)\s+(?:the (?:city|town|village) of\s+)?"
    r"([^.;!?\n]{1,90})", re.I,
)
NONPLACE_STARTS = re.compile(
    r"^(?:a |an |the (?!city |town |village )|my |our |his |her |their |home\b|"
    r"front\b|back\b|outside\b|inside\b|work\b|bed\b|school\b|college\b|"
    r"church\b|hospital\b|hospitality\b|army\b|navy\b|air force\b)", re.I,
)


def publisher_text(value):
    return re.sub(r"\s*,\s*", ",", text(value)).casefold()


def digest_value(value):
    return hashlib.sha256(json_bytes(value)).hexdigest()


def iter_jsonl(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def unique_rows(path, key):
    result = {}
    for row in iter_jsonl(path):
        identifier = str(row[key])
        if identifier in result:
            raise ValueError("Duplicate identity in retained evidence: " + identifier)
        result[identifier] = row
    return result


def authority_name_index(queries):
    """Names already backed by an independent GeoNames feature, never reports."""
    names = defaultdict(list)
    seen = set()
    for query in queries.values():
        for feature in query.get("features", []):
            identity = str(feature["geonameId"])
            if identity in seen:
                continue
            seen.add(identity)
            for label in {feature.get("name", ""), feature.get("asciiName", "")}:
                key = name_key(label)
                if len(key) >= 4:
                    names[key].append(feature)
    return dict(names)


def narrative_text(detail):
    fields = detail.get("raw_fields") or {}
    values, seen = [], set()
    for value in (detail.get("description_full"), detail.get("description"),
                  fields.get("Long Description"), fields.get("Description"),
                  detail.get("summary"), detail.get("description_short"),
                  fields.get("Short Description")):
        value = str(value or "").replace("\\n", "\n").replace("\\,", ",")
        cleaned = re.sub(r"^\s*NUFORC\s+UFO\s+Sighting\s+\d+", "", value, flags=re.I).strip()
        key = re.sub(r"\s+", " ", cleaned)
        if key and key not in seen:
            values.append(cleaned)
            seen.add(key)
    return "\n".join(values)


def narrative_risks(narrative, anchors, authority_names=None):
    reasons, examples = [], []
    for reason, pattern in COMPILED_RISKS.items():
        match = pattern.search(narrative)
        if match:
            reasons.append(reason)
            examples.append({"reason": reason,
                             "excerpt": narrative[max(0, match.start()-65):match.end()+100]})
    if authority_names and anchors:
        expected_names = {name_key(f[key]) for f in anchors for key in ("name", "asciiName") if f.get(key)}
        for match in OBSERVER_PLACE.finditer(narrative):
            phrase = match[1].strip(" \"'")
            if NONPLACE_STARTS.match(phrase):
                continue
            words = re.findall(r"[\w'-]+", phrase, re.UNICODE)
            for length in range(min(5, len(words)), 0, -1):
                key = name_key(" ".join(words[:length]))
                if key in expected_names:
                    break
                candidates = authority_names.get(key, [])
                if not candidates:
                    continue
                # Homonyms of the mentioned place keep this gate conservative.
                # Any nearby authority is enough to avoid inventing a conflict;
                # only a separately named, exclusively distant place is held.
                if all(min(distance_km(f, a)
                           for a in anchors) > 100 for f in candidates):
                    reasons.append("different_named_observer_locality")
                    examples.append({"reason":"different_named_observer_locality",
                                     "excerpt":match[0],
                                     "authorityIds":[f["geonameId"] for f in candidates[:8]]})
                break
    return list(dict.fromkeys(reasons)), examples[:8]


def validate_feature(query, country, admin):
    features = query.get("features", [])
    if query.get("screen") != EXACT_SCREEN:
        return None, "authority_match_not_unambiguous_primary_locality"
    if len(features) != 1:
        return None, "multiple_same_name_features_not_resolved_by_population"
    feature = features[0]
    if feature.get("featureCode") not in SUPPORTED_FEATURES or feature.get("featureClass") != "P":
        return None, "unsupported_authority_feature"
    if feature.get("country") != country or (admin and feature.get("admin1") != admin):
        return None, "authority_jurisdiction_conflict"
    if not any(item.get("kind") == "primary_or_ascii" for item in feature.get("nameMatches", [])):
        return None, "alternate_name_requires_independent_identity_review"
    if not feature.get("authorityUrl") or not feature.get("sourceLineSha256"):
        return None, "authority_provenance_missing"
    lat, lon = feature.get("lat"), feature.get("lon")
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None, "invalid_authority_coordinate"
    return feature, None


def geographic_reference(candidate, queries):
    parsed = candidate["parsedLocation"]
    holds = set(parsed.get("holds", []))
    country, admin = parsed.get("country"), parsed.get("admin1")
    whole_refs = [ref for ref in parsed.get("queryRefs", []) if ref["scope"] == "whole_label"]
    whole = queries.get(whole_refs[0]["queryId"], {}) if len(whole_refs) == 1 else {}
    if not country:
        return None, [], "no_explicit_supported_country"
    if holds <= {MISSING_ADMIN} and whole.get("features"):
        feature, reason = validate_feature(whole, country, admin)
        if reason:
            return None, [], reason
        return {"kind":"city_reference", "lat":feature["lat"], "lon":feature["lon"],
                "precision":"city", "queryIds":[whole["queryId"]],
                "country":country, "admin1":feature["admin1"],
                "missingAdminResolvedBy":"unique_primary_named_locality_in_explicit_country" if not admin else None}, [feature], None
    area = candidate.get("approximateAreaCandidate")
    if area and holds <= {COMPOUND_HOLD} and not whole.get("features"):
        if area.get("country") != country or not admin or area.get("admin1") != admin:
            return None, [], "compound_area_requires_consistent_explicit_jurisdiction"
        anchors, query_ids = [], []
        for component in area.get("componentEvidence", []):
            query = queries.get(component["queryId"], {})
            feature, reason = validate_feature(query, country, admin)
            if reason:
                return None, [], "compound_component:" + reason
            anchors.append(feature)
            query_ids.append(query["queryId"])
        if len(anchors) < 2 or len({str(f["geonameId"]) for f in anchors}) < 2:
            return None, [], "compound_area_requires_distinct_resolved_components"
        diameter = max(distance_km(a, b)
                       for a in anchors for b in anchors)
        if diameter > 100:
            return None, [], "compound_component_diameter_above_100km"
        center = area.get("center", {})
        lat, lon, radius = center.get("lat"), center.get("lon"), area.get("radiusKm")
        if not isinstance(lat, (float, int)) or not isinstance(lon, (float, int)) or not isinstance(radius, (float, int)):
            return None, [], "compound_area_geometry_missing"
        if not (-90 <= lat <= 90 and -180 <= lon <= 180 and 10 <= radius <= 111):
            return None, [], "compound_area_geometry_out_of_bounds"
        if any(distance_km(center, f) + 10 > radius + 0.001 for f in anchors):
            return None, [], "compound_area_does_not_cover_named_anchors_and_display_buffer"
        return {"kind":"approximate_area_reference", "lat":lat,"lon":lon,
                "precision":"approximate", "queryIds":query_ids,
                "country":country,"admin1":admin, "radiusKm":radius,
                "anchorDiameterKm":round(diameter,3), "localityReferenceBufferKm":10,
                "label":area["label"],"uncertaintyStatement":area["uncertaintyStatement"]}, anchors, None
    if holds - {MISSING_ADMIN}:
        return None, [], "unresolved_label_qualification"
    return None, [], "no_unambiguous_independent_locality_reference"


def review(candidate, snapshot, queries, authority_names=None):
    summary, detail = snapshot["summary"], snapshot["source_detail"]
    event_id = summary["event_id"]
    reasons, evidence = [], {}
    source = summary.get("source")
    if str(event_id) != str(candidate["eventId"]) or str(detail.get("event_id")) != str(event_id):
        raise ValueError("Snapshot/candidate event identity mismatch")
    if any(summary.get(key) != candidate["guards"].get(key) for key in GUARD_FIELDS):
        reasons.append("current_summary_guard_mismatch")
    if summary.get("has_coordinates"):
        reasons.append("already_mapped_not_admissible")
    if detail.get("has_coordinates"):
        reasons.append("source_detail_coordinate_state_requires_prior_correction_review")
    if detail.get("source") != source or publisher_text(detail.get("location_raw")) != publisher_text(summary.get("location_raw")):
        reasons.append("immutable_source_and_effective_location_disagree")
    if str(snapshot.get("provenance", {}).get("detail_index")) != str(candidate.get("detailIndex")):
        reasons.append("source_detail_index_mismatch")
    previous_hold = candidate.get("previousReview", {}).get("sourceHold")
    if previous_hold:
        reasons.append("prior_source_hold_requires_new_independent_evidence")
        evidence["previousSourceHold"] = previous_hold
    source_field = NATIVE_LOCATION_FIELDS.get(source)
    fields = detail.get("raw_fields") or {}
    if not source_field:
        reasons.append("archive_location_field_semantics_not_independently_confirmed")
    elif not fields.get(source_field) or publisher_text(fields[source_field]) != publisher_text(summary.get("location_raw")):
        reasons.append("native_observation_location_missing_or_disagrees")
    if detail.get("duplicate_record_count") != 1 or detail.get("source_provenance_count") != 1:
        reasons.append("composite_or_duplicate_source_identity_requires_review")
    reference, anchors, geo_reason = geographic_reference(candidate, queries)
    if geo_reason:
        reasons.append(geo_reason)
    narrative = narrative_text(detail)
    if len(re.findall(r"[^\W\d_]{2,}", narrative, re.UNICODE)) < 6 or re.fullmatch(r"[\[\]\s]*(?:missing data|not available|no description)[\[\]\s]*", narrative, re.I):
        reasons.append("substantive_source_narrative_missing")
    # Read every narrative in full. The more expensive geographic-role scan is
    # useful only when a native source and independent geographic candidate exist.
    if source_field and reference:
        risks, examples = narrative_risks(narrative, anchors, authority_names)
        reasons.extend(risks)
        if examples:
            evidence["narrativeRiskEvidence"] = examples
    reasons = list(dict.fromkeys(reasons))
    result = {"event_id":event_id, "accepted":not reasons,
              "status":"accepted_source_supported" if not reasons else "held_for_source_review",
              "source":source,"candidateLane":candidate["reviewLane"],
              "reasons":reasons,"candidateId":str(candidate["eventId"])}
    if evidence:
        result["reviewEvidence"] = evidence
    if reasons:
        return result
    feature_evidence = [{key: feature.get(key) for key in (
        "geonameId","name","asciiName","country","admin1","featureCode","lat","lon",
        "authorityUrl","sourceLineSha256","nameMatches"
    )} for feature in anchors]
    result.update({
        "decision_id":f"qualified-locality-20261103-{event_id}",
        "confidence":"high_for_declared_locality_identity_not_observer_position",
        "guards":dict(candidate["guards"]),
        "set_fields":{"lat":reference["lat"],"lon":reference["lon"],"has_coordinates":True,
                      "coordinate_source":"geocoded","location_precision":reference["precision"]},
        "scope":reference["kind"],
        "location_reference_evidence":{
            **reference,"sourceLocationField":source_field,
            "sourceLocationValue":fields[source_field],"originalLocationLabel":summary.get("location_raw"),
            "authorityFeatures":feature_evidence,
            "locationRole":"declared_native_observation_locality_reference_not_measured_observer_or_object_position",
            "sourceNarrativeReview":"full_retained_narrative_screened_for_conflict_travel_media_and_role_gates",
            "rawSourceFieldsUnchanged":True,
            "narrativeNeedNotRepeatLocation":"Native publisher observation-location field supplies locality; independent authority supplies geographic reference.",
        },
        "provenance":{
            "sourceDetail":snapshot.get("provenance",{}),
            "rawFieldsSha256":digest_value(fields),"reviewedNarrativeSha256":digest_value(narrative),
            "reviewedNarrativeCharacters":len(narrative),
            "queryIds":reference["queryIds"],"canonicalDataMutated":False,
        },
    })
    return result


def run(details_path, candidates_path, queries_path, output, maximum_bytes=100*1024**2):
    details_path, candidates_path, queries_path, output = map(Path, (details_path,candidates_path,queries_path,output))
    if not 0 < maximum_bytes <= 100*1024**2:
        raise ValueError("Source review evidence must fit within 100 MiB")
    names = ("accepted-decisions.jsonl.gz","held-decisions.jsonl.gz","receipt.json")
    if any((output/name).exists() for name in names):
        raise ValueError("Refusing to overwrite retained source-review evidence")
    candidates = unique_rows(candidates_path,"eventId")
    queries = unique_rows(queries_path,"queryId")
    authorities = authority_name_index(queries)
    inputs = {key:pin(path) for key,path in (("sourceDetails",details_path),("recordCandidates",candidates_path),
                                            ("queryEvidence",queries_path),("reviewScript",Path(__file__))) }
    accepted, held, seen = [], [], set()
    counts, reasons, sources, scopes = Counter(), Counter(), Counter(), Counter()
    for snapshot in iter_jsonl(details_path):
        identity = str(snapshot["summary"]["event_id"])
        if identity in seen or identity not in candidates:
            raise ValueError("Duplicate or unexpected source detail identity: " + identity)
        seen.add(identity)
        decision = review(candidates[identity],snapshot,queries,authorities)
        counts["sourceDetailsRead"] += 1
        sources[f'{decision["source"]}:{decision["status"]}'] += 1
        if decision["accepted"]:
            accepted.append(decision)
            scopes[decision["scope"]] += 1
        else:
            held.append(decision)
            reasons.update(decision["reasons"])
        if counts["sourceDetailsRead"] % 20000 == 0:
            print(json.dumps({"stage":"source_review","read":counts["sourceDetailsRead"],"accepted":len(accepted)}),flush=True)
    if seen != set(candidates):
        raise ValueError("Incomplete source snapshot: " + str(len(set(candidates)-seen)) + " candidate records lack details")
    output.mkdir(parents=True,exist_ok=True)
    writer = EvidenceWriter(output,maximum_bytes)
    writer.write_lines(names[0],accepted)
    writer.write_lines(names[1],held)
    counts.update({"candidateRecords":len(candidates),"accepted":len(accepted),"held":len(held)})
    receipt = {"schemaId":SCHEMA,"status":"source_admission_review_complete",
               "completedUtc":datetime.now(timezone.utc).isoformat(),"counts":dict(counts),
               "acceptedScopes":dict(scopes),"sourceOutcomes":dict(sources),"holdReasons":dict(reasons.most_common()),
               "inputs":inputs,"outputs":writer.files,"sourceCorpusMutated":False,
               "mappedCopiesUsedAsEvidence":False,"humanReviewClaimed":False,
               "policy":"Native declared observation locality plus unique independent primary-name authority. All prior source holds, unresolved homonyms, route/media/conflicting roles, and unconfirmed archive semantics remain held. No population ranking selects a feature.",
               "precisionPolicy":"City decisions identify a reported locality, not an exact observer/object position. Approximate compound-area centers require explicit shared jurisdiction and independently resolved components within 100 km, with a declared 10 km display buffer rather than a statistical confidence bound.",
               "limitations":"Rule-based admission of structured native fields is not independent confirmation that the reported event happened, nor exhaustive natural-language fact verification. Direct source contradictions, newly discovered ambiguity, or better locality evidence can supersede a decision using the retained guards and source pins.",
               "storage":{"outputBytes":sum(f["bytes"] for f in writer.files),"uncompressedEvidenceBytes":writer.raw_bytes,
                          "maximumUncompressedEvidenceBytes":maximum_bytes,"newFilesAbove100MiB":[],
                          "retention":"Retain decisions, all holds, and source pins as the incremental admission evidence. Inputs remain canonical read-only audit snapshots; this output is not a runtime dataset or full corpus copy."}}
    (output/names[2]).write_bytes(json_bytes(receipt))
    print(json.dumps({"status":receipt["status"],"counts":dict(counts),"acceptedScopes":dict(scopes),
                      "outputBytes":receipt["storage"]["outputBytes"]}),flush=True)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--details",type=Path,required=True)
    parser.add_argument("--candidates",type=Path,required=True)
    parser.add_argument("--queries",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--max-output-mib",type=int,default=100)
    args = parser.parse_args()
    run(args.details,args.candidates,args.queries,args.output,args.max_output_mib*1024**2)


if __name__ == "__main__":
    main()
