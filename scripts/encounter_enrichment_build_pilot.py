"""Identity-checked sparse enrichment pilot; original inputs remain untouched.

Replay: python scripts/encounter_enrichment_build_pilot.py --output <new-empty-dir>
Requires pypdf. Installed tzdata 2026c is optional; conditional offsets are never
verified witness UTC and omitted when that pinned rules version is unavailable.
"""
from __future__ import annotations
import argparse, copy, gzip, hashlib, json, re, time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
SHARED=Path("C:/Users/jarod/Desktop/UFO Timeline map tool")
RESEARCH=SHARED/"data/research/encounter-enrichment-pilot-20261013"
SCHEMA="ufo-encounter-enrichment-v1"
RELEASE="encounter-enrichment-pilot-20261013-v1"
REVIEW=ROOT/"docs/qa/encounter-enrichment-pilot-20261013/reviewed_entries.json"
ORIGINAL=ROOT/"docs/qa/encounter-enrichment-pilot-20261013/original-candidate-evidence.json"
SOURCE_MANIFEST=RESEARCH/"primary_manifest.json"

def sha(b):return hashlib.sha256(b).hexdigest()
def packed(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
def unique(rows,key):
    values=[r[key] for r in rows]
    assert len(set(values))==len(values),(key,"duplicate")
    return set(values)

def validate_payload(p):
    assert p["schemaId"]==SCHEMA and p["catalogCount"]==702893
    sources=unique(p["sources"],"sourceId"); entries=unique(p["sourceEntries"],"entryId")
    cases=unique(p["cases"],"caseId");episodes=unique(p["episodes"],"episodeId")
    entities=unique(p["entityObservations"],"entityObservationId")
    unique(p["reportLinks"],"eventId")
    assert len(entries)==24 and len(cases)==20 and len(episodes)==25
    taxonomy=set(p["taxonomyKeys"])
    for e in p["sourceEntries"]:
        assert e["sourceId"] in sources and e["caseId"] in cases
        assert set(e["episodeIds"])<=episodes and e["episodeId"] in episodes
        assert re.fullmatch("[0-9a-f]{64}",e["evidenceSha256"])
    for e in p["episodes"]:
        assert e["caseId"] in cases and set(e["sourceEntryIds"])<=entries
        assert e["contactKind"] in {"forced","voluntary","unclear","none_described"}
        assert e["recallMethod"] in {"conscious","hypnotic","retrospective","mixed","unknown"}
        assert e["scope"] in {"dated_episode","undated_episode","relative_episode","repeated_history"}
        assert e["onboardStatus"] in {"reported","not_described","disputed"}
        assert not e["time"]["utcVerified"] and e["time"]["utcStartMs"] is None and e["time"]["utcEndMs"] is None
        assert not e["site"]["sourceVerified"] and e["site"]["lat"] is None and e["site"]["lon"] is None
        if e["scope"]=="relative_episode": assert e["date"]["startIso"] is None and e["date"]["endIso"] is None
    for ent in p["entityObservations"]:
        assert ent["episodeId"] in episodes and set(ent["sourceEntryIds"])<=entries
        assert set(ent["reportedTypes"])<=taxonomy and ent["scope"] in {"individual","group"}
        assert ent["count"] is None or isinstance(ent["count"],int) and ent["count"]>0
        for a in ent["attributes"]:
            assert a["entryId"] in entries and a["attribution"] in {"explicit_individual","explicit_group","unknown"}
            if a["field"]=="height": assert a["unit"]=="ft" and a["value"]>0
    for r in p["reportLinks"]:
        assert r["eventId"].isdigit() and 0<int(r["eventId"])<2**53
        assert r["source"]=="ufocat" and r["sourceRef"]["detailIndex"]>=0
        assert r["caseId"] in cases and set(r["episodeIds"])<=episodes
        assert set(r["entityObservationIds"])<=entities and set(r["sourceEntryIds"])<=entries
        assert r["status"] in {"linked","candidate","contradicted"}
        assert r["acceptedForRuntime"]==(r["status"]=="linked")
        assert len(r["matchBasis"])>=2
    return True

def case_guards(p):
    ep={r["episodeId"].removeprefix("episode:"):r for r in p["episodes"]}
    ent={r["entityObservationId"]:r for r in p["entityObservations"]}
    link={r["eventId"]:r for r in p["reportLinks"]}
    assert ep["penrose"]["time"]["raw"]=="2330" and ep["penrose"]["recallMethod"]!="hypnotic"
    assert ep["pinhal"]["time"]["raw"]=="2130" and ep["pinhal"]["onboardStatus"]=="disputed"
    assert ep["pinhal"]["recallMethod"]!="hypnotic"
    assert ep["walton"]["time"]["raw"]=="1830" and ep["walton"]["time"]["status"]=="conflicted"
    assert ep["hill"]["recallMethod"]=="mixed" and len(ep["hill"]["recallStages"])==3
    assert ep["stalnaker"]["onboardStatus"]=="not_described"
    assert ep["panama"]["contactKind"]=="unclear"
    assert ep["lake-huron"]["scope"]=="repeated_history"
    assert ep["hellwig-second"]["onboardStatus"]=="not_described"
    assert ep["torphins-first"]["episodeId"] not in {x for r in p["reportLinks"] for x in r["episodeIds"]}
    assert all(not link[k]["acceptedForRuntime"] for k in ["3356684600748588","1555818683808798","1958215277055445"])
    w=[r for r in ent.values() if r["episodeId"]=="episode:wauwatosa"]
    assert not any(a["field"]=="height" for e in w for a in e["attributes"])
    assert any(a["field"]=="carried_object_length" for e in w for a in e["attributes"])
    walton=[r for r in ent.values() if r["episodeId"]=="episode:walton"]
    assert len(walton)==3 and not any(a["field"]=="height" for e in walton if "human_like" in e["reportedTypes"] for a in e["attributes"])
    bf=[r for r in ent.values() if r["episodeId"]=="episode:brands-flats"]
    assert any(a["field"]=="hand" and e["scope"]=="individual" for e in bf for a in e["attributes"])
    assert not any(a["field"]=="forehead" for e in bf for a in e["attributes"])
    assert len({r["episodeIds"][0] for r in p["reportLinks"] if r["eventId"] in {"1554093889853441","140747894653055"}})==1
    return True

def run(output):
    output=Path(output);started=time.perf_counter()
    output.mkdir(parents=True,exist_ok=True)
    assert not any(output.iterdir()),"Output must be new and empty; reviewed provenance is protected."
    inputs={str(p):sha(p.read_bytes()) for p in [Path(__file__),REVIEW,ORIGINAL,SOURCE_MANIFEST]}
    review=json.loads(REVIEW.read_text(encoding="utf-8")); candidates=json.loads(ORIGINAL.read_text(encoding="utf-8"))
    captures=json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))["sources"]
    caps={r["sourceId"]:r for r in captures};source_pins=[];source_text={}
    for sid in review["sources"]:
        row=caps[sid]
        if "path" not in row:
            assert sid=="rosales1993" and row["captureStatus"]=="web_review_only_local_capture_unavailable"
            source_pins.append(dict(sourceId=sid,bytes=None,sha256=None,path=None,captureStatus=row["captureStatus"],reviewUrl=review["sources"][sid]["url"]))
            source_text[sid]=None
            continue
        raw=Path(row["path"]).read_bytes();assert sha(raw)==row["sha256"]
        source_pins.append(dict(sourceId=sid,bytes=len(raw),sha256=sha(raw),path=row["path"]))
        source_text[sid]=PdfReader(Path(row["path"])) if row["path"].endswith(".pdf") else raw
    base_bytes=gzip.decompress((ROOT/"data/encounters/evidence.json.gz").read_bytes());base=json.loads(base_bytes)
    base_manifest=json.loads((ROOT/"data/encounters/manifest.json").read_text(encoding="utf-8"))
    assert sha(base_bytes)==base_manifest["artifact"]["decodedSha256"]
    candidate_rows={r["eventId"]:r for r in candidates["rows"]}
    # Hill's route marker is held in the existing famous-case crosswalk rather than
    # the narrow discovery locality query. Its original chunk/index were reviewed.
    candidate_rows["2951042600193666"]=dict(eventId="2951042600193666",source="ufocat",sourceId="34717",dateRaw="9/19/1961",timeRaw="2200",sourceRef=dict(chunk="chunk_000000",detailIndex=967,chunkSha256="3a35d0472b5f136984a56ce66c0395461a7540ce4c48409014008c2ffad527ea"))
    selected={l["eventId"] for e in review["entries"] for l in e["links"]}
    by_chunk=defaultdict(list)
    for eid in selected:by_chunk[candidate_rows[eid]["sourceRef"]["chunk"]].append(eid)
    original_pins=[]; originals={}
    for chunk,ids in sorted(by_chunk.items()):
        path=SHARED/"data/canonical_web/event_chunks"/(chunk+".json");raw=path.read_bytes();h=sha(raw);data=json.loads(raw)
        original_pins.append(dict(chunk=chunk,bytes=len(raw),sha256=h,path=str(path)))
        for eid in ids:
            c=candidate_rows[eid];ref=c["sourceRef"];r=data[ref["detailIndex"]]
            assert h==ref["chunkSha256"] and str(r["event_id"])==eid and r["source"]==c["source"] and str(r["source_id"])==c["sourceId"]
            assert r.get("date_raw")==c["dateRaw"] and r.get("time_raw")==c["timeRaw"]
            originals[eid]=dict(source=r["source"],sourceEventId=str(r["source_id"]),sourceRef=ref,names=r.get("raw_fields",{}).get("NAMES"),location=r.get("location_raw"),date=r.get("date_raw"),clock=r.get("time_raw"))
        del data,raw
    p=dict(schemaId=SCHEMA,releaseId=RELEASE,catalogCount=702893,baseEvidenceDecodedSha256=sha(base_bytes),taxonomyKeys=[r["key"] for r in base["taxonomy"]],sources=[],sourceEntries=[],cases=[],episodes=[],entityObservations=[],reportLinks=[])
    for sid,s in review["sources"].items():
        p["sources"].append(dict(sourceId=sid,**s,captureSha256=caps[sid].get("sha256"),captureStatus=caps[sid]["captureStatus"],rightsStatus="factual_metadata_and_limited_excerpts_only_fulltext_reuse_not_established",privacyStatus="public_historical_material_identity_and_addresses_minimized"))
    case_map={};quote_words=Counter();conditional_zone_n=0
    for e in review["entries"]:
        entry_id="entry:"+e["key"];case_id="case:"+e["caseKey"]
        episode_ids=["episode:"+ep["key"] for ep in e["episodes"]]
        evidence=source_text[e["sourceId"]]
        hash_meaning="captured_html_bytes"
        if evidence is None:
            evidence=packed(dict(sourceUrl=review["sources"][e["sourceId"]]["url"],locator=e["locator"],shortExcerpt=e["shortExcerpt"]))
            hash_meaning="reviewed_locator_and_excerpt_not_source_capture"
        if isinstance(evidence,PdfReader):
            pages=[e["locator"]["pageIndex"]]
            if e["key"] in {"stalnaker","walton","happy-camp"}:pages.append(pages[0]+1)
            evidence="\n".join(evidence.pages[i].extract_text() for i in pages).encode()
            hash_meaning="pypdf_text_of_located_pages"
        quote_words[e["sourceId"]]+=len(e["shortExcerpt"].split())
        p["sourceEntries"].append(dict(entryId=entry_id,sourceId=e["sourceId"],nativeEntryId=e["nativeEntryId"],caseId=case_id,episodeId=episode_ids[0],episodeIds=episode_ids,title=e["title"],locator=e["locator"],shortExcerpt=e["shortExcerpt"],upstreamCitation=e["upstreamCitation"],evidenceSha256=sha(evidence),evidenceHashMeaning=hash_meaning,reviewStatus="reviewed_factual_metadata",reviewFlags=e["reviewFlags"]+(["local_source_capture_unavailable"] if source_text[e["sourceId"]] is None else [])))
        c=case_map.setdefault(case_id,dict(caseId=case_id,title=e["caseKey"].replace("-"," ").title(),episodeIds=[],sourceEntryIds=[],independentIncidentVerified=False))
        c["episodeIds"].extend(episode_ids);c["sourceEntryIds"].append(entry_id)
        entry_entities=[]
        for ep in e["episodes"]:
            ep=copy.deepcopy(ep);key=ep.pop("key");entities=ep.pop("entities");relationship=ep.pop("relationship")
            ep_id="episode:"+key
            ep.update(episodeId=ep_id,caseId=case_id,sourceEntryIds=[entry_id],evidenceEntryIds=[entry_id])
            if relationship:
                relationship["otherEpisodeId"]="episode:"+relationship.pop("otherEpisodeKey");ep["relationship"]=relationship
            if ep["time"]["conflicts"]:ep["time"]["status"]="conflicted"
            # These are conditional civil-rule calculations, not witness-zone
            # verification or UTC measurements; the scientific UTC gates stay off.
            for z in ep["time"]["timezoneProvenance"]:
                z["sourceUrl"]="https://www.iana.org/time-zones";z["rulesVersion"]=None;z["conditionalOffsetMinutes"]=None
                if ep["date"]["precision"] in {"exact_day","date_range"} and re.fullmatch(r"\d{4}",ep["time"]["raw"] or ""):
                    try:
                        import tzdata
                        from zoneinfo import ZoneInfo
                        if tzdata.IANA_VERSION=="2026c":
                            clock=ep["time"]["raw"];d=datetime.fromisoformat(ep["date"]["startIso"]+"T"+clock[:2]+":"+clock[2:]).replace(tzinfo=ZoneInfo(z["ianaCandidate"]))
                            z["conditionalOffsetMinutes"]=int(d.utcoffset().total_seconds()/60);z["rulesVersion"]="2026c";conditional_zone_n+=1
                    except ImportError:pass
            p["episodes"].append(ep)
            for n,ent in enumerate(entities,1):
                entity_id="entity:"+key+":"+str(n);ent=copy.deepcopy(ent)
                ent.update(entityObservationId=entity_id,episodeId=ep_id,sourceEntryIds=[entry_id])
                for a in ent["attributes"]:
                    a["entryId"]=entry_id;a["attribution"]=a["attribution"] or ("explicit_individual" if ent["scope"]=="individual" else "explicit_group")
                p["entityObservations"].append(ent);entry_entities.append(ent)
        for l in e["links"]:
            native=originals[l["eventId"]];ep_ids=["episode:"+k for k in l["episodeKeys"]]
            basis=[dict(field="native_source_id",excerpt=native["sourceEventId"]),dict(field="reviewed_identity",excerpt=l["basis"])]
            if native["names"]:basis.append(dict(field="native_names",excerpt=str(native["names"])))
            p["reportLinks"].append(dict(eventId=l["eventId"],source=native["source"],sourceEventId=native["sourceEventId"],sourceRef=native["sourceRef"],caseId=case_id,episodeIds=ep_ids,sourceEntryIds=[entry_id],entityObservationIds=[r["entityObservationId"] for r in entry_entities if r["episodeId"] in ep_ids],status=l["status"],acceptedForRuntime=l["status"]=="linked",matchBasis=basis,reviewFlags=e["reviewFlags"]+l["reviewFlags"]))
    assert all(n<=25 for n in quote_words.values()),quote_words
    p["cases"]=list(case_map.values())
    p["policy"]=dict(additiveOnly=True,originalRecordsChanged=False,classificationUnit="reported_source_episode_not_verified_incident",acceptedLinkMeaning="reviewed_identity_join_not_occurrence_verification",candidateLinksExcludedFromRuntime=True,absenceMeaning="not_reviewed_not_negative",entityCountsMustNotBeSummedAcrossOverlappingGroups=True,sourcePhenotypesNotVerifiedSpecies=True,sourceDateHoldsNotOverridden=True,noNewCanonicalReports=True,noNarrativeFulltext=True,noNewPrivateAddresses=True,utcAndExactSiteUnknownsRemainNull=True,contactKindIsNotAbductionClassification=True)
    validate_payload(p);case_guards(p)
    for path,h in inputs.items():assert sha(Path(path).read_bytes())==h,(path,"input changed during build")
    decoded=packed(p);compressed=gzip.compress(decoded,mtime=0)
    counts=dict(sourceEntries=len(p["sourceEntries"]),sources=len(p["sources"]),caseFamilies=len(p["cases"]),episodes=len(p["episodes"]),entityObservations=len(p["entityObservations"]),entityAttributes=sum(len(e["attributes"]) for e in p["entityObservations"]),reportLinks=len(p["reportLinks"]),acceptedReportLinks=sum(r["acceptedForRuntime"] for r in p["reportLinks"]),heldReportLinks=sum(not r["acceptedForRuntime"] for r in p["reportLinks"]),unlinkedSourceEntries=sum(not any(e["entryId"] in l["sourceEntryIds"] for l in p["reportLinks"]) for e in p["sourceEntries"]),verifiedUtcEpisodes=0,verifiedExactSiteEpisodes=0,conditionalHistoricalZoneOffsets=conditional_zone_n,contactKinds=dict(Counter(e["contactKind"] for e in p["episodes"])),recallMethods=dict(Counter(e["recallMethod"] for e in p["episodes"])),scopes=dict(Counter(e["scope"] for e in p["episodes"])))
    artifact=dict(path="evidence.json.gz",gzipBytes=len(compressed),gzipSha256=sha(compressed),decodedBytes=len(decoded),decodedSha256=sha(decoded))
    manifest=dict(schemaId="ufo-encounter-enrichment-manifest-v1",releaseId=RELEASE,catalogCount=702893,baseEvidenceDecodedSha256=sha(base_bytes),artifact=artifact,counts=counts,inputs=inputs,sourcePins=source_pins,originalChunkPins=original_pins,retention=dict(canonical="This validated sparse pilot",researchInputs="Unique bounded primary captures retained in shared research; not deployed",rollback="Current deployed site and known-good rollback unchanged",superseded="None: discovery QA remains evidence, not a release",newFilesOver100MiB=[],netNewBuildBytes=len(compressed),rebuild="Run review generator then builder to a new empty directory; inspect and promote after source-pin QA"))
    audit=dict(schemaId="ufo-encounter-enrichment-qa-v1",releaseId=RELEASE,status="passed",counts=counts,artifact=artifact,checks=dict(sourceCapturePinsMatch=True,originalReportIdentitySourceChunkIndexPinsMatch=True,reviewInputAndBuilderStable=True,schemaAndReferencesMatch=True,focusedScientificGuardsPass=True,reportedTimesNotUtc=True,noExactSiteInvented=True,quoteWordsWithin25PerSource=dict(quote_words),wholeCorpusRewrite=False),heldReportIds=[r["eventId"] for r in p["reportLinks"] if not r["acceptedForRuntime"]],sourceEntryCoverageGaps=[e["entryId"] for e in p["sourceEntries"] if not any(e["entryId"] in l["sourceEntryIds"] for l in p["reportLinks"])],elapsedSeconds=round(time.perf_counter()-started,3))
    (output/"evidence.json.gz").write_bytes(compressed)
    (output/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (output/"audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(dict(output=str(output),counts=counts,artifact=artifact,elapsedSeconds=audit["elapsedSeconds"])))

if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--output",default=str(RESEARCH/"validated/reviewed"));args=ap.parse_args();run(args.output)
