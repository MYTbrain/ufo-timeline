"""Capture only the eight/nine explicitly reviewed primary pilot sources.
No bulk crawl. HEAD byte checks and streaming caps bound all retained inputs.
"""
import hashlib,json,urllib.request,urllib.error
from datetime import datetime,timezone
from pathlib import Path
SHARED=Path("C:/Users/jarod/Desktop/UFO Timeline map tool")
DEST=SHARED/"data/research/encounter-enrichment-pilot-20261013/primary"
SOURCES=[
 ("humcat1954","https://cufos.org/PDFs/HUMCAT/HUMCAT_Index_1954.pdf"),
 ("humcat1961","https://cufos.org/PDFs/HUMCAT/HUMCAT_Index_1961.pdf"),
 ("humcat1965","https://cufos.org/PDFs/HUMCAT/HUMCAT_Index_1965.pdf"),
 ("humcat1975","https://cufos.org/PDFs/HUMCAT/HUMCAT_Index_1975.pdf"),
 ("rosales1993","https://www.iraap.org/rosales/1993.htm"),
 ("urecat_megrit","https://ufologie.patrickgross.org/ce3/1954-10-04-france-megritf.htm"),
 ("gross_quarouble_sep","https://ufologie.patrickgross.org/1954/10sep1954quaroublef.htm"),
 ("gross_mourieras","https://ufologie.patrickgross.org/1954/10sep1954mourierasf.htm"),
 ("gross_quarouble_oct","https://ufologie.patrickgross.org/1954/10oct1954quaroublef.htm"),
]
MAX_TOTAL=12*1024*1024
if (DEST.parent/"primary_manifest.json").exists():
 raise ValueError("Protected source-capture manifest already exists. Replay the pilot from those pinned inputs; do not recapture or replace them.")
DEST.mkdir(parents=True,exist_ok=True); rows=[]; total=0
for key,url in SOURCES:
 suffix=".pdf" if url.endswith(".pdf") else ".html"; file=DEST/(key+suffix)
 cap=4*1024*1024 if suffix==".pdf" else 1024*1024
 try:head=urllib.request.urlopen(urllib.request.Request(url,method="HEAD"),timeout=20);headers=dict(head.headers)
 except urllib.error.HTTPError as error:
  if suffix==".pdf":raise
  headers={"headStatus":error.code}
 expected=int(headers.get("Content-Length") or 0);assert not expected or expected<=cap
 if file.exists():
  data=file.read_bytes();assert len(data)<=cap
 else:
  # The normal urllib client identifies itself accurately as Python-urllib.
  # A custom research UA was rejected; no browser/credential identity is spoofed.
  request=urllib.request.Request(url)
  try:response=urllib.request.urlopen(request,timeout=30)
  except urllib.error.HTTPError as error:
   rows.append({"sourceId":key,"url":url,"captureStatus":"web_review_only_local_capture_unavailable","httpStatus":error.code,"captureUtc":datetime.now(timezone.utc).isoformat(),"sha256":None,"bytes":0,"publicRedistribution":"not_authorized_by_this_capture"});continue
  incoming=int(response.headers.get("Content-Length") or 0);assert not incoming or incoming<=cap
  blocks=[];n=0
  while True:
   block=response.read(min(65536,cap+1-n))
   if not block:break
   blocks.append(block);n+=len(block)
   if n>cap:raise ValueError("Explicit source capture cap exceeded: "+url)
  data=b"".join(blocks)
  assert total+len(data)<=MAX_TOTAL
  if suffix==".pdf":assert data.startswith(b"%PDF")
  file.write_bytes(data)
 total+=len(data);assert total<=MAX_TOTAL
 rows.append({"sourceId":key,"url":url,"path":str(file),"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest(),
  "captureUtc":datetime.now(timezone.utc).isoformat(),"captureStatus":"captured","contentType":headers.get("Content-Type"),"advertisedBytes":expected,
  "etag":headers.get("ETag"),"lastModified":headers.get("Last-Modified"),"publicRedistribution":"not_authorized_by_this_capture","retention":"Unique bounded original-source research input, not part of runtime/public deployment."})
out=DEST.parent/"primary_manifest.json"
payload={"schemaId":"ufo-encounter-pilot-primary-captures-v1","sources":rows,"totalBytes":total,"streamPerFileCapBytes":{"pdf":4*1024*1024,"html":1024*1024},"totalCapBytes":MAX_TOTAL,"policy":"Protected original inputs captured once from explicit primary URLs. No corpus archive copy or NUFORC collection retrieval."}
out.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"sourceCount":len(rows),"totalBytes":total,"manifest":str(out)},indent=2))

