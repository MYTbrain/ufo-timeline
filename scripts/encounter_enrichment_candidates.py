"""Find a bounded candidate set for the 24-entry encounter pilot.
Read effective summary shards in place; no corpus copies or source changes.
"""
import gzip, hashlib, json, re, unicodedata
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def norm(x):
 return re.sub(r'[^a-z0-9]+',' ',unicodedata.normalize('NFKD',str(x)).encode('ascii','ignore').decode().lower()).strip()
QUERIES=[
 ("santa_maria_1954",1954,1954,["santa maria"]),
 ("penrose_1954",1954,1954,["derby","burton"]),
 ("mulberry_1954",1954,1954,["mulberry"]),
 ("eagle_river_1961",1961,1961,["eagle river"]),
 ("lake_huron_1961",1961,1961,["huron"]),
 ("hill_1961",1961,1961,["woodstock","lincoln","indian head","white mountains"]),
 ("pinhal_1961",1961,1961,["pinhal"]),
 ("brasilia_1965",1965,1965,["brasilia"]),
 ("brands_flats_1965",1965,1965,["brands","brand s","brand","fishersville"]),
 ("poole_1965",1964,1966,["poole"]),
 ("walton_1975",1975,1975,["heber","snowflake","sitgreaves"]),
 ("wauwatosa_1975",1975,1975,["wauwatosa"]),
 ("mount_vernon_1975",1975,1975,["mt vernon","mount vernon"]),
 ("happy_camp_1975",1975,1975,["happy camp"]),
 ("torphins_1993",1993,1993,["torphins"]),
 ("pinaya_1993",1993,1993,["pinaya"]),
 ("panama_1993",1993,1993,["panama"]),
 ("megrit_1954",1954,1954,["megrit"]),
 ("valensole_1965",1965,1965,["valensole"]),
 ("quarouble_1954",1954,1954,["quarouble"]),
 ("mourieras_1954",1954,1954,["mourieras","mouri eras","bugeat"]),
]
plan=json.loads((ROOT/"releases/workspace-analysis-20261008/delivery_plan.json").read_text())
results=defaultdict(list); total=0; pins=[]
for item in plan["uploads"]:
 if not re.search(r"/summary_shards/summary_\d+\.json\.gz$",item["key"]):continue
 path=Path(item["source"]); data=path.read_bytes()
 assert hashlib.sha256(data).hexdigest()==item["sha256"] and len(data)==item["bytes"]
 pins.append({k:item[k] for k in ["key","source","bytes","sha256"]})
 for row in json.loads(gzip.decompress(data)):
  total+=1
  iso=str(row.get("sort_date_iso") or row.get("date_iso") or "")
  if not re.match(r"^\d{4}",iso):continue
  year=int(iso[:4]); place=norm(" ".join(str(row.get(k) or "") for k in ["location_raw","country","city","state_province"]))
  for key,lo,hi,terms in QUERIES:
   if lo<=year<=hi and any(norm(t) in place for t in terms):
    results[key].append(row)
assert total==702893 and len(pins)==71
output=ROOT/"docs/qa/encounter-enrichment-pilot-20261013/candidates.json"
assert not output.exists()
output.parent.mkdir(parents=True,exist_ok=True)
payload={"schemaId":"ufo-encounter-enrichment-candidates-v1","catalogReports":total,"summaryPins":pins,"queries":[{"key":k,"yearStart":a,"yearEnd":b,"placeTerms":t,"candidateCount":len(results[k])} for k,a,b,t in QUERIES],"candidates":dict(results),"policy":"Location/date candidates only; no incident links are accepted by this discovery script."}
content=(json.dumps(payload,separators=(",",":"),ensure_ascii=False)+"\n").encode()
assert len(content)<2*1024*1024
output.write_bytes(content)
print(json.dumps({"output":str(output),"bytes":len(content),"counts":{k:len(v) for k,v in results.items()}},indent=2))

