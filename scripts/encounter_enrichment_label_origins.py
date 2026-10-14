"""Derive per-label evidence origin from actual pinned classifier decisions.
Read immutable original chunks in place; only indexed encounter rows are traced.
No source records, coordinates or existing encounter evidence are modified.
"""
from __future__ import annotations
import argparse,builtins,gzip,hashlib,importlib.util,inspect,json,sys
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; SHARED=Path("C:/Users/jarod/Desktop/UFO Timeline map tool")
SCHEMA="ufo-encounter-being-label-origins-v1"; RELEASE="being-label-origins-20261013-v1"
def digest(b):return hashlib.sha256(b).hexdigest()
def compact(value):return json.dumps(value,ensure_ascii=False,separators=(",",":"),sort_keys=True).encode()
def run(output):
 output=Path(output);output.mkdir(parents=True,exist_ok=True)
 if (output/"manifest.json").exists() or (output/"label_origins.json.gz").exists():raise ValueError("Protected validated origin output already exists.")
 builder=ROOT/"scripts/build_encounter_evidence.py";builder_bytes=builder.read_bytes();extractor_sha=digest(builder_bytes)
 spec=importlib.util.spec_from_file_location("pinned_encounter_classifier",builder);module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
 full=gzip.decompress((ROOT/"data/encounters/evidence.json.gz").read_bytes());base=json.loads(full);base_manifest=json.loads((ROOT/"data/encounters/manifest.json").read_text())
 assert digest(full)==base_manifest["artifact"]["decodedSha256"]
 expected={row["eventId"]:row for row in base["rows"]}
 taxonomy=[row["key"] for row in base["taxonomy"]]; bits={key:1<<i for i,key in enumerate(taxonomy)}
 lines,start=inspect.getsourcelines(module.classify);source_lines={start+i:line.rstrip() for i,line in enumerate(lines)}
 narrative_start=next(n for n,v in source_lines.items() if "narrative_fields = narratives(" in v)
 narrative_end=next(n for n,v in source_lines.items() if "if entity_coded and not keys:" in v)
 key_constructor=next(n for n,v in source_lines.items() if v.strip()=="keys = set()")
 classifier_code=module.classify.__code__; recorder={}; tracked_sets=[]
 class OriginSet(builtins.set):
  def record(self,key,line):
   if key not in bits:return
   origin="narrative" if narrative_start<line<narrative_end else "source"
   recorder.setdefault(key,defaultdict(builtins.set))[origin].add(line)
  def add(self,key):
   self.record(key,inspect.currentframe().f_back.f_lineno);super().add(key)
  def update(self,values):
   values=list(values);line=inspect.currentframe().f_back.f_lineno
   for key in values:self.record(key,line)
   super().update(values)
 def traced_set(*args):
  frame=inspect.currentframe().f_back
  if frame.f_code is classifier_code and frame.f_lineno==key_constructor:
   result=OriginSet(*args);tracked_sets.append(result);return result
  return builtins.set(*args)
 def mask(keys):return sum(bits[key] for key in builtins.set(keys))
 rows=[];pins=[];counts=Counter(); seen=builtins.set()
 indexed_by_chunk=defaultdict(dict)
 for id,row in expected.items():indexed_by_chunk[row["sourceRef"]["chunk"]][row["sourceRef"]["detailIndex"]]=(id,row)
 for chunk,needed in sorted(indexed_by_chunk.items()):
  file=SHARED/"data/canonical_web/event_chunks"/(chunk+".json");raw=file.read_bytes();sha=digest(raw);events=json.loads(raw)
  pins.append({"chunk":chunk,"path":str(file),"bytes":len(raw),"sha256":sha})
  for position,(id,expected_row) in sorted(needed.items()):
   event=events[position];assert str(event["event_id"])==id and event["source"]==expected_row["source"]
   assert sha==expected_row["sourceRef"]["chunkSha256"]
   normal=module.classify(event);recorder.clear();tracked_sets.clear();module.set=traced_set
   try:traced=module.classify(event)
   finally:del module.set
   assert compact(normal)==compact(traced),"Instrumentation changed classifier output."
   assert traced["beingTypes"]==expected_row["beingTypes"],"Pinned current classifier no longer reproduces indexed being labels."
   accepted=builtins.set(traced["beingTypes"]);source_keys=[k for k in accepted if "source" in recorder.get(k,{})];narrative_keys=[k for k in accepted if "narrative" in recorder.get(k,{})]
   source_mask=mask(source_keys);narrative_mask=mask(narrative_keys);full_mask=mask(accepted);unknown=full_mask&~(source_mask|narrative_mask)
   assert unknown==0,"Actual accepted label lacks a traced decision origin."
   assert len(tracked_sets)==1
   decision_rows=[{"key":key,"sourceLines":sorted(recorder[key].get("source",[])),"narrativeLines":sorted(recorder[key].get("narrative",[]))} for key in taxonomy if key in accepted]
   rows.append({"eventId":id,"source":event["source"],"sourceRef":expected_row["sourceRef"],"beingMask":full_mask,"sourceBeingMask":source_mask,"narrativeBeingMask":narrative_mask,"bothBeingMask":source_mask&narrative_mask,"unknownBeingMask":unknown,"decisionLines":decision_rows})
   assert id not in seen;seen.add(id)
   counts["rows"]+=1
   if full_mask:counts["beingRows"]+=1
   if source_mask:counts["sourceOriginRows"]+=1
   if narrative_mask:counts["narrativeOriginRows"]+=1
   if source_mask&narrative_mask:counts["bothOriginRows"]+=1
  if len(pins)%40==0:print(f"Traced {len(pins)} original chunks; {len(rows)} indexed rows.",flush=True)
 assert seen==builtins.set(expected) and len(rows)==16319
 assert digest(builder.read_bytes())==extractor_sha,"Extractor changed during tracing."
 rows.sort(key=lambda r:int(r["eventId"]))
 payload={"schemaId":SCHEMA,"releaseId":RELEASE,"catalogCount":702893,"baseEvidenceDecodedSha256":digest(full),"extractorSha256":extractor_sha,"taxonomyKeys":taxonomy,
  "policy":{"method":"Actual unchanged classifier keys.add/update execution sites traced, with byte-identical normal/traced output required for every indexed original row.","originMeaning":"Decision evidence origin, not a collection proxy, incident truth or firsthand witness verification.","absenceMeans":"Not indexed; not negative.","sourceRecordMutated":False,"classifierRelexed":False,"sourceAndNarrativeMasksMayOverlap":True,"sourceFallbackClassificationsRetained":True},"rows":rows}
 decoded=compact(payload);packed=gzip.compress(decoded,compresslevel=9,mtime=0);assert len(packed)<2*1024*1024
 (output/"label_origins.json.gz").write_bytes(packed)
 manifest={"schemaId":SCHEMA,"releaseId":RELEASE,"catalogCount":702893,"rowCount":len(rows),"taxonomyKeys":taxonomy,"baseEvidenceDecodedSha256":digest(full),"extractorSha256":extractor_sha,
  "artifact":{"file":"label_origins.json.gz","decodedBytes":len(decoded),"decodedSha256":digest(decoded),"gzipBytes":len(packed),"gzipSha256":digest(packed)},"counts":dict(counts),"policy":payload["policy"]}
 (output/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf8")
 audit={"schemaId":"ufo-encounter-label-origin-trace-audit-v1","status":"passed","normalTracedParityRows":len(rows),"zeroUnattributedLabels":True,"sourceRefsExact":True,"sourcePins":pins,"extractor":{"path":str(builder),"bytes":len(builder_bytes),"sha256":extractor_sha},
  "classifierLineRoles":{"keysConstructor":key_constructor,"narrativeBranchStart":narrative_start,"narrativeBranchEnd":narrative_end,"executedLabelDecisionLines":{str(n):source_lines[n] for n in sorted({line for r in rows for d in r["decisionLines"] for line in d["sourceLines"]+d["narrativeLines"]})}},
  "rebuild":f"python scripts/encounter_enrichment_label_origins.py --output <fresh-directory>","retention":"Canonical small source-pinned origin sidecar; original chunks and base encounter evidence remain protected in place.","artifact":manifest["artifact"],"counts":dict(counts)}
 (output/"audit.json").write_text(json.dumps(audit,indent=2)+"\n",encoding="utf8")
 print(json.dumps({"output":str(output),"counts":dict(counts),"artifact":manifest["artifact"]},indent=2))
if __name__=="__main__":
 parser=argparse.ArgumentParser();parser.add_argument("--output",type=Path,default=SHARED/"data/research/encounter-enrichment-pilot-20261013/label_origins");args=parser.parse_args();run(args.output)

