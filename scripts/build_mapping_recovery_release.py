"""Build a bounded geographic-only release delta from CURRENT pinned summaries.

Original detail chunks remain in place. Existing quality and analysis date
overlays are applied in that order before new mapping guards are evaluated.
No chronology is inferred or recomputed. This emits a candidate, never publishes
it, changes runtime configuration, or copies a canonical corpus.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import copy
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from scripts.build_quality_map_release import (
    BIN_NAMES, META_NAMES, COUNT_FIELDS, GUARD_FIELDS, build_profiles,
    ensure_new_output, export_packed_points, export_trace_artifacts,
    gzip_file, point_projection_from_summary, read_json, sha256,
    verify_storage, write_gzip_json, write_json,
)
from scripts.review_mapping_location_candidates import iter_jsonl

SHARED = Path(r"C:/Users/jarod/Desktop/UFO Timeline map tool")
SCHEMA = "ufo-mapping-recovery-release-v1"
DETAIL_SCHEMA = "ufo-mapping-recovery-detail-overlay-v1"
GEO_FIELDS = frozenset(("lat","lon","has_coordinates","coordinate_source","location_precision","location_reference"))
IDENTITY_FIELDS = ("event_id","canonical_event_id","source_id","chunk_id","detail_index","date_precision")
REFERENCE_FIELDS = frozenset(("kind","label","note","authority_ids","bounds","radius_km","evidence_id"))
GENERATED_ARTIFACTS = {
    "event_chunk_manifest":"event_chunk_manifest.json",
    "summary_manifest":"summary_manifest.json",
    "summary_shards_dir":"summary_shards/",
    "points":"points.bin","points_metadata":"points_meta.json",
    "trace_event_index":"trace_event_index.bin","trace_event_index_metadata":"trace_event_index_meta.json",
    "trace_segments":"trace_segments.bin","trace_segments_metadata":"trace_segments_meta.json",
    "trace_aggregate_bins":"trace_aggregate_bins.bin","trace_aggregate_bins_metadata":"trace_aggregate_bins_meta.json",
}


def pin(path):
    path=Path(path)
    return {"path":str(path.resolve()),"bytes":path.stat().st_size,"sha256":sha256(path)}


def verify_pin(path, expected):
    path=Path(path)
    actual=pin(path)
    if actual["bytes"] != expected["bytes"] or actual["sha256"] != expected["sha256"]:
        raise ValueError("Pinned input changed: " + str(path))
    return actual


def delivery_input(plan, suffix):
    found=[item for item in plan["uploads"] if item["key"].endswith("/"+suffix)]
    if len(found) != 1:
        raise ValueError("Expected exactly one current delivery input: " + suffix)
    item=found[0]
    path=Path(item["source"])
    return path,verify_pin(path,item)


def scalar_guard(row, path):
    value=row
    for part in path:
        if isinstance(value,dict) and part in value:
            value=value[part]
        elif isinstance(value,list) and isinstance(part,int) and 0 <= part < len(value):
            value=value[part]
        else:
            return False,None
    return True,value


def apply_overlay(row, patch):
    if patch is None:
        return row
    if str(row.get("event_id")) != str(patch["eventId"]):
        raise ValueError("Prior overlay event identity mismatch")
    guards=patch["guards"]
    if isinstance(guards,dict):
        valid=all(row.get(key) == value for key,value in guards.items())
    elif isinstance(guards,list):
        valid=all(scalar_guard(row,guard["path"]) == (guard["exists"],guard["value"]) for guard in guards)
    else:
        raise ValueError("Unsupported prior overlay guard contract")
    if not valid:
        raise ValueError("Prior overlay guard failed: " + str(row.get("event_id")))
    result=dict(row)
    result.update(copy.deepcopy(patch["setFields"]))
    return result


def overlay_index(payload):
    if payload.get("schemaVersion") != 1:
        raise ValueError("Unsupported prior detail overlay schema")
    patches={}
    for patch in payload["patches"]:
        identity=str(patch["eventId"])
        if identity in patches:
            raise ValueError("Duplicate prior overlay patch identity")
        patches[identity]=patch
    if payload.get("patchCount",len(patches)) != len(patches):
        raise ValueError("Prior overlay patch count mismatch")
    return patches


def validate_decision(decision):
    if decision.get("status") != "accepted_source_supported" or decision.get("accepted") is False:
        raise ValueError("Only accepted source-supported decisions can build a release")
    fields=decision.get("set_fields") or {}
    if set(fields)-GEO_FIELDS or not {"lat","lon","has_coordinates","coordinate_source","location_precision"} <= set(fields):
        raise ValueError("Decision attempts a non-geographic edit or lacks required geographic fields")
    if fields["has_coordinates"] is not True:
        raise ValueError("This recovery lane only adds reviewed mapping references")
    for key,bound in (("lat",90),("lon",180)):
        value=fields[key]
        if type(value) not in (int,float) or not math.isfinite(value) or not -bound <= value <= bound:
            raise ValueError("Invalid approved coordinate")
    if fields["location_precision"] not in {"city","approximate","state","province","country","exact_coords"}:
        raise ValueError("Unsupported approved location precision")
    if not isinstance(fields["coordinate_source"],str) or not fields["coordinate_source"]:
        raise ValueError("Coordinate authority method is missing")
    reference=fields.get("location_reference")
    if not isinstance(reference,dict) or set(reference)-REFERENCE_FIELDS:
        raise ValueError("A compact approved location_reference is required")
    if not all(reference.get(key) for key in ("kind","label","note","evidence_id")):
        raise ValueError("Location reference identity, label, note, and evidence ID are required")
    if not isinstance(reference.get("authority_ids"),list) or not reference["authority_ids"]:
        raise ValueError("Location reference independent authority identifiers are required")
    if len(json.dumps(reference,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode("utf8")) > 1024:
        raise ValueError("Compact location reference exceeds 1 KiB")
    if fields["location_precision"] == "approximate" and "radius_km" in reference:
        if type(reference["radius_km"]) not in (int,float) or not 0 < reference["radius_km"] <= 20050:
            raise ValueError("Invalid reference envelope radius")
    guards=decision.get("guards") or {}
    if not set(GUARD_FIELDS) <= set(guards):
        raise ValueError("Current geographic/source guards are incomplete")
    if type(guards["has_coordinates"]) is not bool:
        raise ValueError("Current mapped/unmapped guard must be explicit")
    return decision


def load_decisions(path):
    decisions={}
    for decision in iter_jsonl(path):
        validate_decision(decision)
        identity=str(decision["event_id"])
        if identity in decisions:
            raise ValueError("Duplicate accepted event ID: " + identity)
        decisions[identity]=decision
    if not decisions:
        raise ValueError("No accepted mapping decisions supplied")
    return decisions


def apply_summary_decision(row,decision):
    # Full source-only identity guards are deliberately checked later against
    # the pinned effective detail. A compact summary need not contain source_id.
    for key,value in decision["guards"].items():
        if key in row and row[key] != value:
            raise ValueError(f"Current summary guard failed: {row['event_id']}:{key}")
        if key in GUARD_FIELDS and row.get(key) != value:
            raise ValueError(f"Current summary geographic guard failed: {row['event_id']}:{key}")
    result=dict(row)
    result.update(copy.deepcopy(decision["set_fields"]))
    if {key:value for key,value in row.items() if key not in GEO_FIELDS} != {key:value for key,value in result.items() if key not in GEO_FIELDS}:
        raise ValueError("A non-geographic summary field changed")
    return result


def detail_patch(original,effective,summary,decision):
    identity=str(original["event_id"])
    if identity != str(decision["event_id"]) or identity != str(summary["event_id"]):
        raise ValueError("Mapping detail event identity mismatch")
    for key,value in decision["guards"].items():
        if effective.get(key) != value:
            raise ValueError(f"Current effective detail guard failed: {identity}:{key}")
    for key in GUARD_FIELDS:
        if effective.get(key) != summary.get(key):
            raise ValueError(f"Current detail/summary disagree before mapping: {identity}:{key}")
    fields=copy.deepcopy(decision["set_fields"])
    result=dict(effective)
    result.update(fields)
    if {k:v for k,v in effective.items() if k not in GEO_FIELDS} != {k:v for k,v in result.items() if k not in GEO_FIELDS}:
        raise ValueError("Mapping detail changed source identity, evidence, or chronology")
    guard_keys=set(GUARD_FIELDS)|set(IDENTITY_FIELDS)|set(decision["guards"])
    guards={key:copy.deepcopy(effective.get(key)) for key in sorted(guard_keys)}
    return {"eventId":original["event_id"],"chunkId":summary["chunk_id"],"detailIndex":summary["detail_index"],
            "guards":guards,"setFields":fields,"evidenceId":decision.get("decision_id")}


def source_detail_patches(declared, selected, decisions, quality, analysis):
    base=Path(declared["base"]["path"])
    jobs=defaultdict(list)
    for identity,row in selected.items():
        jobs[row["chunk_id"]].append((row["detail_index"],identity))
    patches,receipts=[],[]
    for chunk,items in sorted(jobs.items()):
        relative=f"event_chunks/{chunk}.json.gz"
        if Path(chunk).name != chunk or relative not in declared["base"]["files"]:
            raise ValueError("Unknown protected detail chunk")
        path=base/relative
        receipt=verify_pin(path,declared["base"]["files"][relative])
        rows=read_json(path)
        for index,identity in items:
            raw=rows[index]
            if str(raw.get("event_id")) != identity or raw.get("chunk_id") != chunk or raw.get("detail_index") != index:
                raise ValueError("Original detail locator differs from current summary")
            effective=apply_overlay(apply_overlay(raw,quality.get(identity)),analysis.get(identity))
            patches.append(detail_patch(raw,effective,selected[identity],decisions[identity]))
        receipts.append({**receipt,"matchedPatches":len(items)})
        if len(receipts)%25 == 0 or len(receipts)==len(jobs):
            print(json.dumps({"stage":"detail_guards","chunks":len(receipts),"patches":len(patches)}),flush=True)
    if {str(p["eventId"]) for p in patches} != set(decisions):
        raise ValueError("Incomplete guarded mapping detail overlay")
    return sorted(patches,key=lambda p:p["eventId"]),receipts


def files_receipts(output,prefix):
    files=[]
    for path in sorted(output.rglob("*")):
        if not path.is_file() or path.name == "map_release_receipt.json":
            continue
        relative=path.relative_to(output).as_posix()
        if relative.startswith("mapping_recovery_detail/"):
            delivery,public,key="pages","data/"+relative,None
        elif relative.startswith("startup_profiles/"):
            delivery,public,key="pages","data/"+relative,None
        elif relative in BIN_NAMES:
            delivery,public,key="local",None,None
        else:
            delivery,public,key="r2",prefix+"/"+relative,prefix+"/"+relative
        files.append({"path":relative,**{k:v for k,v in pin(path).items() if k!="path"},
                      "delivery":delivery,"publicPath":public,"immutableKey":key})
    return files


def size_gate(output,maximum):
    total=sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
    if total > maximum:
        raise ValueError("Bounded map-delta byte cap exceeded; partial output is not validated")
    return total


def write_mapping_overlay(output,packet,base_sha,decision_sha):
    """Use the runtime's existing schema-1 envelope with the new decision pin.

    qualityManifestSha256 is the legacy loader's correction-packet identity slot;
    for this independent mapping layer it pins the accepted mapping decisions.
    The actual prior quality manifest remains separately pinned in sourcePins.
    """
    packet={**packet,"baseManifestSha256":base_sha,"qualityManifestSha256":decision_sha}
    overlay_path=Path(output)/"mapping_recovery_detail/patches.json.gz"
    write_gzip_json(overlay_path,packet)
    with gzip.open(overlay_path,"rb") as handle:
        raw=handle.read()
    manifest={"schemaId":DETAIL_SCHEMA,"schemaVersion":1,"file":"patches.json.gz","bytes":len(raw),
              "sha256":hashlib.sha256(raw).hexdigest(),"gzipBytes":overlay_path.stat().st_size,
              "gzipSha256":sha256(overlay_path),"patchCount":len(packet["patches"]),"sourcePins":packet["sourcePins"],
              "baseManifestSha256":base_sha,"qualityManifestSha256":decision_sha,
              "mappingDecisionsSha256":decision_sha}
    write_json(Path(output)/"mapping_recovery_detail/manifest.json",manifest)
    return manifest


def rebase_generated_artifacts(canonical):
    """Relative generated paths follow the new manifest in preview/production.

    Inherited absolute pointers would silently load old packed traces even when
    app_config selects the new manifest. Original full-detail chunks remain at
    their unchanged shared event_chunks_dir authority URL.
    """
    canonical.setdefault("artifacts",{}).update(GENERATED_ARTIFACTS)
    return canonical


def build(delivery_plan,decisions_path,quality_manifest,quality_overlay,analysis_manifest,output,
          prefix="releases/mapping-recovery-20261103/map_delta",maximum_bytes=450*1024**2):
    delivery_plan,decisions_path,quality_manifest,quality_overlay,analysis_manifest,output=map(
        lambda p:Path(p).resolve(),(delivery_plan,decisions_path,quality_manifest,quality_overlay,analysis_manifest,output))
    if not 0 < maximum_bytes <= 450*1024**2:
        raise ValueError("Map recovery delta must fit within 450 MiB")
    prefix=prefix.strip("/")
    if not prefix or ".." in prefix.split("/") or "\\" in prefix:
        raise ValueError("Invalid immutable release prefix")
    declared,plan=read_json(quality_manifest),read_json(delivery_plan)
    base=Path(declared["base"]["path"]).resolve()
    ensure_new_output(output,base)
    decisions=load_decisions(decisions_path)
    inputs={key:pin(path) for key,path in (("deliveryPlan",delivery_plan),("acceptedDecisions",decisions_path),
           ("qualityManifest",quality_manifest),("qualityOverlay",quality_overlay),("analysisOverlayManifest",analysis_manifest),
           ("builder",Path(__file__)))}
    canonical_path,inputs["currentCanonicalManifest"]=delivery_input(plan,"data/canonical_web/canonical_web_manifest.json")
    summaries_path,inputs["currentSummaryManifest"]=delivery_input(plan,"data/canonical_web/summary_manifest.json")
    analysis_path,inputs["analysisOverlay"]=delivery_input(plan,"data/analysis_repair_detail/patches.json.gz")
    current,shards=read_json(canonical_path),read_json(summaries_path)
    analysis_declared=read_json(analysis_manifest)
    if (inputs["analysisOverlay"]["sha256"] != analysis_declared["gzipSha256"] or
            inputs["analysisOverlay"]["bytes"] != analysis_declared["gzipBytes"] or
            inputs["qualityOverlay"]["sha256"] != analysis_declared["sourcePins"]["existingQualityOverlayGzipSha256"]):
        raise ValueError("Existing detail overlay chain pins changed")
    quality_payload,analysis_payload=read_json(quality_overlay),read_json(analysis_path)
    if (quality_payload["baseManifestSha256"] != declared["base"]["manifest_sha256"] or
            quality_payload["qualityManifestSha256"] != inputs["qualityManifest"]["sha256"]):
        raise ValueError("Quality detail overlay and base manifest differ")
    quality,analysis=overlay_index(quality_payload),overlay_index(analysis_payload)
    base_manifest=base/"canonical_web_manifest.json"
    inputs["originalCanonicalManifest"]=verify_pin(base_manifest,declared["base"]["files"]["canonical_web_manifest.json"])
    chunk_path=base/"event_chunk_manifest.json"
    inputs["originalChunkManifest"]=verify_pin(chunk_path,declared["base"]["files"]["event_chunk_manifest.json"])
    chunks=read_json(chunk_path)
    source_shards=[]
    for shard in shards:
        path,receipt=delivery_input(plan,f'data/canonical_web/summary_shards/{shard["id"]}.json.gz')
        source_shards.append((shard,path,receipt))
    estimate=int((current["counts"]["mapped_events"]+len(decisions))*208*1.7+
                 sum(item[2]["bytes"] for item in source_shards)*1.4+20*1024**2+len(decisions)*1200)
    free_before=verify_storage(output,estimate,maximum_bytes)
    print(json.dumps({"stage":"planned","estimatedBytes":estimate,"decisions":len(decisions),"summaryShards":len(shards)}),flush=True)
    output.mkdir(parents=True,exist_ok=True)
    counters={name:Counter() for name in COUNT_FIELDS}
    total,mapped,before_mapped=0,0,0
    bounds=None
    point_rows,selected=[],{}
    unchanged_digest=hashlib.sha256()
    for shard,path,receipt in source_shards:
        old_rows=read_json(path)
        if len(old_rows)!=shard["event_count"] or old_rows[0]["event_id"]!=shard["start_event_id"] or old_rows[-1]["event_id"]!=shard["end_event_id"]:
            raise ValueError("Current summary shard identity/order changed")
        rows=[]
        for before in old_rows:
            identity=str(before["event_id"])
            before_mapped+=bool(before.get("has_coordinates"))
            if identity in decisions:
                if identity in selected:
                    raise ValueError("Duplicate selected identity in summary shards")
                selected[identity]=before
                row=apply_summary_decision(before,decisions[identity])
            else:
                row=before
            nongeo={key:value for key,value in before.items() if key not in GEO_FIELDS}
            unchanged_digest.update(json.dumps(nongeo,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode("utf8"))
            unchanged_digest.update(b"\n")
            rows.append(row)
            total+=1
            for name,(field,default) in COUNT_FIELDS.items():
                counters[name][row.get(field) or default]+=1
            if row.get("has_coordinates"):
                mapped+=1
                point_rows.append(point_projection_from_summary(row))
                if bounds is None:
                    bounds={"west":row["lon"],"east":row["lon"],"south":row["lat"],"north":row["lat"]}
                else:
                    bounds["west"]=min(bounds["west"],row["lon"])
                    bounds["east"]=max(bounds["east"],row["lon"])
                    bounds["south"]=min(bounds["south"],row["lat"])
                    bounds["north"]=max(bounds["north"],row["lat"])
        write_gzip_json(output/"summary_shards"/(shard["id"]+".json.gz"),rows)
        if len(selected) and total%100000==0:
            print(json.dumps({"stage":"summaries","events":total,"mappingDecisionsApplied":len(selected)}),flush=True)
    newly_mapped=sum(not decision["guards"]["has_coordinates"] for decision in decisions.values())
    if set(selected)!=set(decisions) or total!=current["counts"]["events"] or before_mapped!=current["counts"]["mapped_events"] or mapped!=before_mapped+newly_mapped:
        raise ValueError("Current catalog census or approved decision coverage failed")
    size_gate(output,maximum_bytes)
    patches,detail_receipts=source_detail_patches(declared,selected,decisions,quality,analysis)
    chain={key:inputs[key]["sha256"] for key in ("acceptedDecisions","deliveryPlan","qualityManifest","qualityOverlay","analysisOverlay","currentCanonicalManifest")}
    packet={"schemaId":DETAIL_SCHEMA,"schemaVersion":1,"sourcePins":chain,"patchCount":len(patches),"patches":patches}
    overlay_manifest=write_mapping_overlay(output,packet,declared["base"]["manifest_sha256"],inputs["acceptedDecisions"]["sha256"])
    write_json(output/"summary_manifest.json",shards)
    write_json(output/"event_chunk_manifest.json",chunks)
    points=export_packed_points(point_rows,output,chunk_manifest=chunks)
    if points["row_count"]!=mapped:
        raise ValueError("Packed points census disagrees with corrected summaries")
    traces=export_trace_artifacts(point_rows,output)
    for name in BIN_NAMES+META_NAMES:
        if name in META_NAMES:
            metadata=read_json(output/name)
            metadata["mappingRecoverySourcePins"]=chain
            write_json(output/name,metadata)
        gzip_file(output/name)
        size_gate(output,maximum_bytes)
    profiles=build_profiles(point_rows,chunks,output,inputs["qualityManifest"]["sha256"])
    # The existing startup exporter is reused; correct its old detail-policy text
    # and retain the complete chain pins without changing event chronology.
    for path in (output/"startup_profiles").rglob("manifest.json"):
        manifest=read_json(path)
        manifest["mappingRecoverySourcePins"]=chain
        if "full_detail_policy" in manifest:
            manifest["full_detail_policy"]="Shared immutable details; quality, analysis repair, then mapping recovery guarded overlays."
        write_json(path,manifest)
        gzip_file(path)
    counts={"events":total,"mapped_events":mapped,"unmapped_events":total-mapped,"event_chunks":len(chunks),
            "summary_shards":len(shards),"mapped_bounds":bounds,"trace_events":traces["trace_events"]["row_count"],
            "trace_segments":traces["trace_segments"]["row_count"],"trace_aggregate_bins":traces["trace_aggregate_bins"]["row_count"],
            **{name:dict(sorted(counter.items())) for name,counter in counters.items()}}
    canonical=copy.deepcopy(current)
    rebase_generated_artifacts(canonical)
    canonical["counts"]=counts
    canonical["mapping_recovery"]={"schemaId":SCHEMA,"sourcePins":chain,"changedRecords":len(decisions),
                                   "chronologyRecomputedRecords":0,"nonGeographicSummaryFieldsPreserved":True,
                                   "originalDetailsShared":True,"detailOverlayRequired":True}
    canonical.setdefault("policy",{})["mapping_recovery_detail_overlay_required"]=True
    for key,metadata in (("packed_points",points),("packed_trace_events",traces["trace_events"]),
                         ("packed_trace_segments",traces["trace_segments"]),("packed_trace_aggregate_bins",traces["trace_aggregate_bins"])):
        canonical.setdefault(key,{}).update({name:metadata[name] for name in ("schema_version","row_count","bytes_per_row")})
    write_json(output/"canonical_web_manifest.json",canonical)
    for name in ("canonical_web_manifest.json","event_chunk_manifest.json","summary_manifest.json"):
        gzip_file(output/name)
    for key in ("deliveryPlan","acceptedDecisions","qualityManifest","qualityOverlay","analysisOverlayManifest","builder"):
        verify_pin(Path(inputs[key]["path"]),inputs[key])
    files=files_receipts(output,prefix)
    total_bytes=size_gate(output,maximum_bytes)
    receipt={"schemaVersion":1,"schemaId":SCHEMA,"status":"validated_local_mapping_candidate",
             "generatedAtUtc":datetime.now(timezone.utc).isoformat(),"output":str(output),"immutablePrefix":prefix,
             "inputs":inputs,"summarySourcePins":[item[2] for item in source_shards],"sourceChunkReads":detail_receipts,
             "counts":counts,"beforeCounts":current["counts"],"changedRecords":len(decisions),
             "newlyMappedRecords":newly_mapped,"existingMappedCorrections":len(decisions)-newly_mapped,
             "chronologyRecomputedRecords":0,"nonGeographicSummarySha256":unchanged_digest.hexdigest(),
             "nonGeographicFieldsPreserved":True,"allSummaryDecisionsGuarded":True,"allEffectiveDetailDecisionsGuarded":True,
             "detailOverlay":overlay_manifest,"detailOverlayOrder":["quality","analysis_repair","mapping_recovery"],
             "files":files,"profiles":profiles,"productionPublished":False,
             "storage":{"estimatedBytes":estimate,"totalOutputBytes":total_bytes,"maximumOutputBytes":maximum_bytes,
                        "freeBytesBefore":free_before,"freeBytesAfter":shutil.disk_usage(output).free,
                        "sourceCorpusCopied":False,"filesLargerThan100MiB":[item["path"] for item in files if item["bytes"]>100*1024**2]},
             "retention":{"purpose":"Incremental validated mapping release candidate, with prior current date/quality corrections preserved.",
                          "canonicalArtifact":"This candidate delta plus pinned original chunks and prior overlays; current production remains canonical until release approval.",
                          "rollback":plan.get("retained_rollback"),"supersededStaging":[],
                          "rebuild":"python scripts/build_mapping_recovery_release.py --delivery-plan "+str(delivery_plan)+" --decisions "+str(decisions_path)+" --output "+str(output)}}
    write_json(output/"map_release_receipt.json",receipt)
    size_gate(output,maximum_bytes)
    print(json.dumps({"status":receipt["status"],"changedRecords":len(decisions),"mapped":mapped,"unmapped":total-mapped,
                      "outputBytes":total_bytes,"chronologyRecomputedRecords":0}),flush=True)
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delivery-plan",type=Path,default=ROOT/"releases/workspace-analysis-20261008/delivery_plan.json")
    parser.add_argument("--decisions",type=Path,required=True)
    parser.add_argument("--quality-manifest",type=Path,default=SHARED/"data/research/database_quality_20261007/quality_view_manifest.json")
    parser.add_argument("--quality-overlay",type=Path,default=ROOT/"data/quality_detail_patches.json.gz")
    parser.add_argument("--analysis-manifest",type=Path,default=ROOT/"data/analysis_repair_detail/manifest.json")
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--immutable-prefix",default="releases/mapping-recovery-20261103/map_delta")
    parser.add_argument("--max-output-mib",type=int,default=450)
    args=parser.parse_args()
    build(args.delivery_plan,args.decisions,args.quality_manifest,args.quality_overlay,args.analysis_manifest,args.output,
          args.immutable_prefix,args.max_output_mib*1024**2)


if __name__ == "__main__":
    main()
