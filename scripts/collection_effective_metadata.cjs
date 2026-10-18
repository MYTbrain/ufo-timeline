"use strict";
// Project only guarded runtime metadata needed by the sparse collection sidecar.
// Canonical files are read, never changed. Date/quality validation uses the same
// modules as the browser rather than a second implementation of their guards.
const fs = require("node:fs"), path = require("node:path"), zlib = require("node:zlib"), crypto = require("node:crypto");
const Quality = require("../quality_detail_overlay.js"), Repair = require("../analysis_repair_detail_overlay.js");
const root = path.resolve(__dirname, ".."), shared = process.argv[2];
function assert(value, label) { if (!value) throw new Error("Collection runtime metadata: " + label); }
function digest(bytes) { return crypto.createHash("sha256").update(bytes).digest("hex"); }
function pin(file, role) { const raw = fs.readFileSync(file); return { file:path.basename(file), sha256:digest(raw), bytes:raw.length, role }; }
function read(relative) { return fs.readFileSync(path.join(root, relative)); }
const configBytes = read("data/app_config.json"), config = JSON.parse(configBytes);
function compressed(relative, contract) { const bytes = read(relative); assert(digest(bytes)===contract.gzipSha256, "stale compressed " + relative); if (contract.gzipBytes!=null) assert(bytes.length===contract.gzipBytes,"stale compressed size"); const decoded=zlib.gunzipSync(bytes); if(contract.sha256) assert(digest(decoded)===contract.sha256,"stale decoded "+relative); if(contract.bytes!=null) assert(decoded.length===contract.bytes,"stale decoded size"); return JSON.parse(decoded); }
const q = Quality.createIndex(compressed("data/quality_detail_patches.json.gz",config.detailQualityOverlay),config.detailQualityOverlay);
const a = Repair.createIndex(compressed("data/analysis_repair_detail/patches.json.gz",config.analysisRepairDetailOverlay),config.analysisRepairDetailOverlay);
const loc = compressed("data/location_label_overlay.json.gz",config.locationLabelOverlay);
assert(loc.schema_version===1 && Array.isArray(loc.labels) && Array.isArray(loc.reviewed),"location schema");
assert(loc.labels.length===config.locationLabelOverlay.entryCount && loc.reviewed.length===config.locationLabelOverlay.reviewedCount && loc.labels.length-loc.reviewed.length===config.locationLabelOverlay.genericDisplayCount && loc.source_inventory_sha256===config.locationLabelOverlay.sourceInventorySha256,"location inventory/count contract");
const labels=new Map(), reviewed=new Map(); loc.labels.forEach(row=>{assert(Array.isArray(row)&&row.length===2&&!labels.has(String(row[0]))&&String(row[1]).trim(),"location identity");labels.set(String(row[0]),String(row[1]));});
loc.reviewed.forEach(row=>{assert(labels.has(String(row[0]))&&!reviewed.has(String(row[0])),"reviewed location identity");reviewed.set(String(row[0]),row[1]);});
let input=""; process.stdin.setEncoding("utf8"); process.stdin.on("data",part=>input+=part); process.stdin.on("end",()=>{
 const reports=JSON.parse(input), metadata=[], chunks=new Map(); let qualityN=0,repairN=0,labelN=0,labelSkippedN=0;
 reports.forEach(report=>{
  const id=String(report.eventId), hasQ=q.hasPatch(id),hasA=a.hasPatch(id),hasL=labels.has(id); if(!hasQ&&!hasA&&!hasL)return;
  const result={eventId:id,applied:[]}; let effective=null;
  if(hasQ||hasA){
   const file=path.join(shared,"data/canonical_web/event_chunks",report.chunkId+".json.gz");
   if(!chunks.has(file))chunks.set(file,JSON.parse(zlib.gunzipSync(fs.readFileSync(file))));
   const original=chunks.get(file)[report.detailIndex]; assert(original&&String(original.event_id)===id&&original.source===report.source&&String(original.source_id)===String(report.sourceId),"baseline identity/locator mismatch");
   effective=Quality.apply(q,original); if(hasQ){qualityN++;result.applied.push("quality_detail");}
   effective=Repair.apply(a,effective); if(hasA){repairN++;result.applied.push("analysis_repair_detail");}
   result.effective={};["date_iso","end_date_iso","sort_date_iso","date_precision","date_interval_semantics","exact_day_eligible","date_recovery_contract","country","location_raw","location_display","coordinate_source","location_precision","has_coordinates"].forEach(key=>{if(Object.hasOwn(effective,key))result.effective[key]=effective[key];});
  }
  // Browser applyLocationLabelOverlay deliberately lets quality corrections win.
  if(hasL&&!hasQ&&!(effective&&effective.quality_view_changes)){
   result.locationDisplay=labels.get(id);result.reviewedLocation=reviewed.get(id)||null;labelN++;result.applied.push("location_label_display");
  }else if(hasL)labelSkippedN++;
  metadata.push(result);
 });
 const pins=[pin(path.join(root,"data/app_config.json"),"runtime metadata contracts"),pin(path.join(root,"data/quality_detail_patches.json.gz"),"guarded current report metadata"),pin(path.join(root,"data/analysis_repair_detail/patches.json.gz"),"guarded current partial-date intervals"),pin(path.join(root,"data/location_label_overlay.json.gz"),"current location display labels"),pin(path.join(root,"quality_detail_overlay.js"),"browser quality guard implementation"),pin(path.join(root,"analysis_repair_detail_overlay.js"),"browser date guard implementation"),pin(__filename,"sparse runtime metadata projector")];
 process.stdout.write(JSON.stringify({metadata,inputPins:pins,receipt:{qualityPatchN:qualityN,dateRepairPatchN:repairN,locationDisplayN:labelN,locationSkippedForQualityN:labelSkippedN,detailChunksRead:chunks.size,canonicalDataMutated:false,guardImplementation:"same JavaScript modules used by browser"}}));
});
