import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import {createRequire} from "node:module";
const require = createRequire(import.meta.url);
const review = require("../mufon_date_review.js");
const app = fs.readFileSync(new URL("../app.js", import.meta.url), "utf8");
const fixtures = JSON.parse(fs.readFileSync(new URL("../docs/qa/mufon-date-review-20261019/fixtures.json", import.meta.url), "utf8"));
function actual(name) {
  const start = app.indexOf("  function " + name + "(");
  const match = /\n  (?:async )?function |\n  const /g;
  match.lastIndex = start + 10;
  const next = match.exec(app);
  assert.ok(start >= 0 && next && next.index > start, name);
  return app.slice(start, next.index);
}
const byId = new Map(), panel = {innerHTML:""}, title = {textContent:""};
const context = vm.createContext({console, MUFON_DATE_REVIEW:review, ENCOUNTERS:null, UFOCAT_REFERENCES:null,
  runtime:{catalogSummaryMemory:{fallbackPlaybackKeysReleased:0,compactPlaybackKeys:0,unusedPropertiesReleased:0,prunedEvents:0}},
  activeCatalogUsesCanonicalWebArtifacts:()=>true, canonicalPlaybackSortKeyIsDefaultFallback:()=>false,
  DEFAULT_CANONICAL_PLAYBACK_SORT_KEY:[3,null,null,3,0],internCanonicalSummaryString:v=>v,
  applyLocationLabelOverlay:e=>e,getVisualTypeGroup:()=>"UFO/UAP sighting",eventLegendKeyForMode:()=>"light",
  getCatalogEventById:id=>byId.get(id),
  els:{detailPanel:panel,detailStageTitle:title}, displayLocationForEvent:e=>e.location_raw,
  escapeHtml:v=>String(v??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll('"',"&quot;"),
  locationPrecisionDisplayLabel:v=>v,formatList:()=>"",renderLinkList:()=>""});
for (const name of ["parseIsoParts","daysFromCivil","isoToOrdinal","finiteChronologyNumber",
  "applyMufonDateReview","eventDateLabel","compactCanonicalSummaryEventForRuntime","hydrateCatalogEvent",
  "sortDateIsoFromPackedKey","sortTimeMsFromPackedValue","projectPackedPointRowToEvent","augmentPackedMapEventDisplayFields",
  "nullableCatalogNumber","serializeCatalogFacetWorkerRow","decodePackedTraceEventIndexRowForRender","renderDetail"]) {
  vm.runInContext(actual(name),context,{filename:"actual-app:"+name});
}
const serialized=[];
for (const fixture of fixtures) {
  const original=JSON.stringify(fixture), hydrated=context.hydrateCatalogEvent(fixture.summary);
  byId.set(fixture.event_id,hydrated);
  assert.equal(hydrated.sort_ordinal,null);
  assert.equal(hydrated.date_precision,"unknown");
  assert.equal(hydrated.date_review.status,"unverified_source_date","Compaction retains the review flag");
  assert.equal(context.eventDateLabel(hydrated),"Date unverified");
  const workerRow=context.serializeCatalogFacetWorkerRow(hydrated);
  assert.equal(workerRow.sortOrdinal,null); assert.equal(workerRow.datePrecision,"unknown");
  assert.equal(workerRow.occurrenceDateWithheld,true);
  serialized.push(workerRow);
  const packed=context.projectPackedPointRowToEvent({event_id:fixture.event_id,lat:fixture.summary.lat,lon:fixture.summary.lon,
    source_id:"mufon",sort_date_key:18900401,sort_time_ms:0,date_precision_id:"exact_day",chunk_id:fixture.chunk_id,detail_index:fixture.detail_index});
  assert.equal(packed.sort_date_iso,null); assert.equal(packed.sort_date_key,null); assert.equal(packed.sort_time_ms,null);
  assert.equal(context.eventDateLabel(packed),"Date unverified");
  const rebuiltPacked={event_id:fixture.event_id,source:"mufon",sort_date_iso:null,date_precision:"unknown",chunk_id:"chunk_000999",detail_index:9};
  context.augmentPackedMapEventDisplayFields(rebuiltPacked,hydrated);
  assert.equal(context.eventDateLabel(rebuiltPacked),"Date unverified","Future packed points inherit reviewed labels from the canonical summary");
  context.decodePackedTraceField=(_metadata,_view,field)=>field==="event_id"?fixture.event_id:0;
  assert.equal(context.decodePackedTraceEventIndexRowForRender({metadata:{},view:{}},0),null,
    "The old packed trace index cannot resurrect a withheld date, including All Time with undated reports visible");
  const detail=context.applyMufonDateReview(fixture.detail);
  context.renderDetail(detail);
  assert.match(title.textContent,/^Date unverified \|/);
  assert.match(panel.innerHTML,/<h4>Occurrence date unverified<\/h4>/);
  assert.match(panel.innerHTML,/Imported Date \(unverified\)/);
  assert.match(panel.innerHTML,/Date Submitted/);
  assert.ok(panel.innerHTML.includes(fixture.detail.reported_date_raw));
  assert.match(panel.innerHTML,/1890-04-01/,"Original source date remains inspectable");
  assert.doesNotMatch(panel.innerHTML,/<h3 class="detail-title">1890-04-01/);
  assert.equal(JSON.stringify(fixture),original,"No layer rewrites original records");
}
// Exercise the real core Analysis/facet worker using the actual corrected app serializer.
const messages=[], self={postMessage:message=>messages.push(message)};
const workerContext=vm.createContext({self,console});
vm.runInContext(fs.readFileSync("analysis_stats.js","utf8"),workerContext);
vm.runInContext(fs.readFileSync("catalog_filter_worker.js","utf8"),workerContext);
const ordinal=context.isoToOrdinal("1890-04-01");
function send(message){messages.length=0;self.onmessage({data:message});assert.equal(messages.length,1);assert.notEqual(messages[0].type,"catalogFacetWorkerError",messages[0].error);return messages[0];}
send({type:"addCatalogFacetRows",rows:[...serialized,{eventId:1,source:"mufon",type:"Light",craftType:"light",datePrecision:"exact_day",sortOrdinal:ordinal,mapped:false}]});
const filters={sourceMode:"all",typeMode:"all",precisionMode:"all",hideLowPrecision:false,hideNonExactDates:false};
const query={filters,baselineMode:"full_catalog",selectedDomains:["overview","time","craft"],quickMode:true};
const windowed=send({...query,type:"computeAnalysis",requestId:"1890-window",timeRangeMode:"window",timeRangeStartOrdinal:ordinal,timeRangeEndOrdinal:ordinal}).result;
assert.equal(windowed.summary.activeCount,1,"Only the unrelated, valid historical control belongs in the 1890 window");
const all=send({...query,type:"computeAnalysis",requestId:"all",timeRangeMode:"all"}).result;
assert.equal(all.summary.activeCount,6,"Undated reports remain available in All Time");
const html=fs.readFileSync("index.html","utf8");
assert.ok(html.indexOf('src="./mufon_date_review.js?')<html.indexOf('src="./app.js?'));
assert.match(app,/applyMufonDateReview\(applyLocationLabelOverlay\(applyAnalysisRepairDetailOverlay/);
assert.match(app,/applyMufonDateReview\(applyLocationLabelOverlay\(event, \{ detail: true \}\)\)/);
console.log("Actual map/summary/detail/trace and core Analysis paths withhold all five unsupported dates, preserve raw/submission fields and retain valid historical records.");
