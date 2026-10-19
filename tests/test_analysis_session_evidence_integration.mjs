import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { createRequire } from "node:module";
import { webcrypto, createHash } from "node:crypto";
const require = createRequire(import.meta.url);
function functionSource(source, name) {
  const start = source.search(new RegExp("^  (?:async )?function " + name + "\\(", "m"));
  assert.ok(start >= 0, name);
  const next = source.slice(start + 1).search(/\n  (?:async )?function \w+\(/);
  return source.slice(start, start + 1 + next);
}
const app = fs.readFileSync("app.js", "utf8");
const decorationContext=vm.createContext({getCatalogEventById:id=>String(id)==='a'?{location_display:'Reviewed place'}:null});
vm.runInContext(functionSource(app,'decorateAnalysisInspectionReports'),decorationContext);
const rawInspection={groups:{A:{totalN:1,matchedN:1,rows:[{id:'a',eventIds:['a'],label:'Triangle',date:'Date withheld'}]},B:{totalN:1,matchedN:1,rows:[{id:'crop-a',label:'Context record',eventIds:[],contextRecord:{kind:'crops',id:'crop-a'}}]}}};
const decorated=decorationContext.decorateAnalysisInspectionReports(rawInspection);
assert.equal(decorated.groups.A.rows[0].label,'Reviewed place · Triangle');assert.equal(decorated.groups.A.rows[0].date,'Date withheld');
assert.equal(rawInspection.groups.A.rows[0].label,'Triangle','Source presentation does not mutate worker counts or rows');
assert.equal(decorated.groups.B.rows[0].label,'Context record','Independent records are never decorated via UFO IDs');
const A = { eventIds: ["a"], reportCount: 1, provenance: { sessionCaptureId: "capture-a" } };
const B = { eventIds: ["b"], reportCount: 1, provenance: { sessionCaptureId: "capture-b" } };
let held = { A, B }, posted = [], comparisonLoads = 0, spatialLoads = 0;
const listeners = new Map(), timers = new Map(); let timerId = 0;
const worker = { postMessage(message) { posted.push(message); },
  addEventListener(type, fn) { if (!listeners.has(type)) listeners.set(type,new Set()); listeners.get(type).add(fn); },
  removeEventListener(type,fn) { listeners.get(type)?.delete(fn); } };
const context = vm.createContext({ console, URL,
  runtime: { analysisSessionStore: { getState() { return { groups: held }; } }, catalogFacetWorkerRequestId: 0 },
  document: { baseURI: "https://preview.invalid/index.html" }, resolveAssetPath: x => x,
  ensureAnalysisComparisonArtifacts: async () => { comparisonLoads++; },
  ensureAnalysisSpatialArtifacts: async () => { spatialLoads++; }, ensureCatalogFacetWorker: () => worker,
  setTimeout(fn,ms) { assert.equal(ms,180000); const id=++timerId; timers.set(id,fn); return id; },
  clearTimeout(id) { timers.delete(id); } });
context.window=context;
vm.runInContext(functionSource(app,"loadAnalysisSessionEvidence"),context);
function respond(result={status:"ready",dimensions:[]}, message=posted.at(-1)) {
  for(const fn of [...listeners.get("message")||[]]) fn({data:{type:"analysisSessionEvidenceComputed",requestId:message.requestId,evidenceSignature:message.evidenceSignature,result}});
}
const next = () => new Promise(resolve => setImmediate(resolve));
const core = context.loadAnalysisSessionEvidence({section:"crops",groups:held});
await next(); assert.equal(comparisonLoads,0); assert.equal(spatialLoads,0);
assert.deepEqual([...posted.at(-1).groups.A.eventIds],["a"]);
respond(); await core; assert.equal(timers.size,0);
const celestial = context.loadAnalysisSessionEvidence({section:"comparisons",groups:held,settings:{planet:"Mars",orb:3}});
await next(); assert.equal(comparisonLoads,1); assert.equal(posted.at(-1).settings.planet,"Mars");respond();await celestial;
const space=context.loadAnalysisSessionEvidence({section:"spatial",groups:held});await next();assert.equal(spatialLoads,1);respond();await space;
const stale=context.loadAnalysisSessionEvidence({section:"animals",groups:held});await next();held={A:{...A},B};respond();await assert.rejects(stale,/held groups changed/);held={A,B};
const error=context.loadAnalysisSessionEvidence({section:"encounters",groups:held});await next();
for(const fn of [...listeners.get("message")||[]]) fn({data:{type:"catalogFacetWorkerError",requestId:posted.at(-1).requestId,error:"integrity mismatch"}});
await assert.rejects(error,/integrity mismatch/);
const timeout=context.loadAnalysisSessionEvidence({section:"animals",groups:held});await next();[...timers.values()].at(-1)();await assert.rejects(timeout,/timed out/);assert.equal(timers.size,0);
await assert.rejects(context.loadAnalysisSessionEvidence({section:"unsupported",groups:held}),/not recognized/);
const inspectA={...A,summary:{distributions:{craft:{rows:[{key:'disc_saucer',count:1}],eligibleN:1,unknownN:0}}}},inspectB={...B,summary:{distributions:{craft:{rows:[],eligibleN:0,unknownN:1}}}};
held={A:inspectA,B:inspectB};
const inspection=context.loadAnalysisSessionEvidence({inspection:true,section:'craft',domainKey:'craft',rowKey:'disc_saucer',offset:25,limit:25,groups:held});
await next();
const inspectionMessage=posted.at(-1);
assert.equal(inspectionMessage.type,'inspectAnalysisSessionEvidence');assert.equal(inspectionMessage.offset,25);assert.equal(inspectionMessage.rowKey,'disc_saucer');
assert.equal(inspectionMessage.groups.A.inspectionSummary.distribution.rows[0].count,1);
for(const fn of [...listeners.get('message')||[]]) fn({data:{type:'analysisSessionEvidenceInspected',requestId:inspectionMessage.requestId,evidenceSignature:inspectionMessage.evidenceSignature,result:{groups:{A:{rows:[]},B:{rows:[]}}}}});
await inspection;assert.equal(timers.size,0);
const staleInspection=context.loadAnalysisSessionEvidence({inspection:true,section:'craft',domainKey:'craft',rowKey:'__unknown__',groups:held});await next();held={A:inspectA,B:{...inspectB}};
for(const fn of [...listeners.get('message')||[]]) fn({data:{type:'analysisSessionEvidenceInspected',requestId:posted.at(-1).requestId,evidenceSignature:posted.at(-1).evidenceSignature,result:{groups:{A:{rows:[]},B:{rows:[]}}}}});
await assert.rejects(staleInspection,/held groups changed/);held={A,B};

// The actual worker verifies exact membership, date epochs and lazy context reuse.
const day=iso=>Date.parse(iso+"T00:00:00Z")/86400000;
const sourceRows=[{eventId:"a",sortOrdinal:day("1973-09-01"),datePrecision:"exact_day",mapped:true,source:"fixture",type:"Disk",craftType:"disc_saucer",country:"United States",lat:40,lon:-75},
 {eventId:"b",sortOrdinal:day("1989-12-01"),datePrecision:"exact_day",mapped:false,source:"fixture",type:"Triangle",craftType:"triangle",lat:null,lon:null}];
const crop={id:"crop-a",startOrdinal:day("1973-09-01"),endOrdinal:day("1973-09-01"),datePrecision:"exact_day",dateRole:"occurrence",country:"United States",lat:40,lon:-75,morphology:["single_circle"],strictEligible:false};
const payload={ordinalEpoch:"unix_day",crops:[crop],animals:[]},bytes=Buffer.from(JSON.stringify(payload));
const hash=createHash("sha256").update(bytes).digest("hex"), manifest={artifacts:{context:{file:"context.json",sha256:hash,bytes:bytes.length}}};
let requests=0;const outputs=[], contextApi=require("../analysis_session_context.js");
const self={crypto:webcrypto,UfoAnalysisSessionContext:contextApi,UfoAnalysisSpatial:require("../analysis_spatial.js"),postMessage:m=>outputs.push(m)};
const workerContext=vm.createContext({self,console,URL,Response,TextDecoder,Uint8Array,ArrayBuffer,
  fetch:async url=>{requests++;return new Response(String(url).endsWith("manifest.json")?JSON.stringify(manifest):bytes);} });
vm.runInContext(fs.readFileSync("analysis_stats.js","utf8"),workerContext);
vm.runInContext(fs.readFileSync("catalog_filter_worker.js","utf8"),workerContext);
self.onmessage({data:{type:"addCatalogFacetRows",rows:sourceRows}});assert.equal(requests,0,"No context download during catalog startup");
function cohort(id,iso){return {eventIds:[id],reportCount:1,scope:{timeRange:{mode:"window",startOrdinal:day(iso),endOrdinal:day(iso)}},provenance:{capturedSnapshot:{timeRange:{mode:"window",startOrdinal:day(iso),endOrdinal:day(iso)},areaFilter:{active:false,shapes:[]}}}};}
const groups={A:cohort("a","1973-09-01"),B:cohort("b","1989-12-01")};
async function ask(message) {outputs.length=0;self.onmessage({data:message});for(let i=0;i<100&&!outputs.length;i++)await next();assert.ok(outputs.length,"worker response");return outputs.at(-1);}
const result=await ask({type:"computeAnalysisSessionEvidence",requestId:"first",evidenceSignature:"same",section:"crops",groups,settings:{},contextManifestUrl:"https://fixture.invalid/manifest.json"});
assert.equal(result.type,"analysisSessionEvidenceComputed",result.error);assert.equal(result.evidenceSignature,"same");
assert.ok(result.result.dimensions.some(d=>d.a?.totalN===1&&d.b?.totalN===0),"Independent catalogs follow each captured window");
const again=await ask({type:"computeAnalysisSessionEvidence",requestId:"second",evidenceSignature:"same",section:"animals",groups,settings:{},contextManifestUrl:"https://fixture.invalid/manifest.json"});
assert.equal(again.type,"analysisSessionEvidenceComputed",again.error);assert.equal(requests,2,"Manifest and artifact reused between categories");
self.UfoAnalysisSessionInspection=require('../analysis_session_inspection.js');
const externalDimension=result.result.dimensions.find(row=>row.key==='crops_morphology');
assert.ok(externalDimension);
const inspectedContext=await ask({type:'inspectAnalysisSessionEvidence',requestId:'context-inspection',section:'crops',domainKey:externalDimension.key,rowKey:externalDimension.a.rows[0].key,groups,settings:{},contextManifestUrl:'https://fixture.invalid/manifest.json'});
assert.equal(inspectedContext.type,'analysisSessionEvidenceInspected',inspectedContext.error);
assert.equal(inspectedContext.result.groups.A.matchedN,1);assert.equal(inspectedContext.result.groups.B.matchedN,0);
assert.equal(inspectedContext.result.groups.A.rows[0].id,'crop-a');assert.ok(!inspectedContext.result.groups.A.rows[0].eventIds?.length,'A context ID never invents a report join');
self.UfoAnalysisSessionContext = { ...contextApi, compute(options) {
  assert.equal(options.groups.A.rows[0].sortOrdinal, day("1973-09-01"), "Raw typed-row dates enter estimators as Unix days");
  assert.equal(options.groups.B.rows[0].startOrdinal, day("1989-12-01"));
  assert.equal(options.groups.B.rows[0].lat, null, "Unmapped rows never acquire zero coordinates");
  return contextApi.compute(options);
} };
const evidence=await ask({type:"computeAnalysisSessionEvidence",requestId:"epoch",section:"context",groups,settings:{},contextManifestUrl:"https://fixture.invalid/manifest.json"});
assert.equal(evidence.type,"analysisSessionEvidenceComputed",evidence.error);
const bad=await ask({type:"computeAnalysisSessionEvidence",requestId:"bad",section:"crops",groups:{A:{...groups.A,eventIds:["missing"]},B:groups.B},contextManifestUrl:"https://fixture.invalid/manifest.json"});
assert.equal(bad.type,"catalogFacetWorkerError");assert.match(bad.error,/absent/);
console.log("A/B evidence app/worker integration: exact IDs, date epochs, independent catalogs, lazy reuse, replacement and failure cleanup passed.");
