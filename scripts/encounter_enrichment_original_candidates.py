"""Inspect only bounded pilot candidates in original immutable detail chunks."""
import gzip, hashlib, json
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; SHARED=Path("C:/Users/jarod/Desktop/UFO Timeline map tool")
payload=json.loads((ROOT/"docs/qa/encounter-enrichment-pilot-20261013/candidates.json").read_text())
needed=defaultdict(dict)
for key,rows in payload["candidates"].items():
 for row in rows:
  if row["source"] not in ["ufocat","majestic","phenomenainon_updb"]:continue
  needed[row["chunk_id"]].setdefault(row["detail_index"],{"summary":row,"queries":[]})["queries"].append(key)
# The known Hill canonical crosswalk uses a location alias not caught by the
# place scan; include its already accepted canonical identity explicitly.
for chunk,index,event_id in [("chunk_000042",0,0)]:
 pass
rows=[];pins=[]
for chunk,entries in sorted(needed.items()):
 file=SHARED/"data/canonical_web/event_chunks"/(chunk+".json")
 raw=file.read_bytes();data=json.loads(raw);digest=hashlib.sha256(raw).hexdigest()
 pins.append({"chunk":chunk,"path":str(file),"bytes":len(raw),"sha256":digest})
 for index,entry in entries.items():
  event=data[index]; summary=entry["summary"]
  assert str(event["event_id"])==str(summary["event_id"]) and event["source"]==summary["source"]
  rawfields=event.get("raw_fields") or {}
  if event["source"]=="ufocat":
   # Raw keys are dictionary-preserved source fields, not inferred values.
   wanted=["PRN","IRN","NAMES","NOTES","HYNEK","VALLEE","TYPE","Ufonaut","Height","Uniform","TIME","TZ","DATE","LOC","CITY","OBJS","ENTS"]
   fields={k:v for k,v in rawfields.items() if str(k).upper() in {x.upper() for x in wanted}}
  else:fields={k:v for k,v in rawfields.items() if str(k).lower() in ["name","names","source","reference","location","description","details"]}
  rows.append({"queries":entry["queries"],"eventId":str(event["event_id"]),"source":event["source"],"sourceId":event.get("source_id"),
   "dateRaw":event.get("date_raw"),"dateIso":event.get("date_iso"),"sortIso":event.get("sort_date_iso"),"datePrecision":event.get("date_precision"),
   "timeRaw":event.get("time_raw"),"locationRaw":event.get("location_raw"),"lat":event.get("lat"),"lon":event.get("lon"),"coordinateSource":event.get("coordinate_source"),
   "sourceRef":{"chunk":chunk,"detailIndex":index,"chunkSha256":digest},"descriptionExcerpt":str(event.get("description") or "")[:900],"rawFields":fields})
out=ROOT/"docs/qa/encounter-enrichment-pilot-20261013/original-candidate-evidence.json";assert not out.exists()
bytes=(json.dumps({"schemaId":"ufo-encounter-pilot-candidate-original-evidence-v1","policy":"Private bounded match-review evidence; this discovery subset does not accept or publish incident/entity links.","chunks":pins,"rows":rows},separators=(",",":"),ensure_ascii=False)+"\n").encode()
assert len(bytes)<2*1024*1024
out.write_bytes(bytes); print(json.dumps({"output":str(out),"bytes":len(bytes),"originalChunks":len(pins),"candidateRows":len(rows)},indent=2))

