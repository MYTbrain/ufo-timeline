// Bounded independent audit: read canonical artifacts in place, retain sparse
// encounter rows in memory, and write only a small provenance/count receipt.
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";
import crypto from "node:crypto";
import vm from "node:vm";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");
const require = createRequire(import.meta.url);
const sha = b => crypto.createHash("sha256").update(b).digest("hex");
const read = f => JSON.parse(fs.readFileSync(f, "utf8"));
const pin = f => { const b=fs.readFileSync(f); return {path:f,bytes:b.length,sha256:sha(b)}; };
const millis = performance.now();
const occurrenceGuard = process.argv.includes("--occurrence-guard");
const target = path.join(root, "docs/qa/encounter-complete-20261013/context-real-artifacts.json");
assert.ok(!fs.existsSync(target), "Existing unique receipt is protected; rename deliberately before rerunning.");
const runtimeNames = ["analysis_encounter_context.js","encounter_evidence.js","analysis_lunar.js","analysis_nuclear.js","analysis_planetary.js","analysis_cross_context.js","analysis_astronomy_engine.js","app.js","catalog_filter_worker.js","trace_chronology.js","trace_neighborhood.js"];
const runtimePins = runtimeNames.map(n=>pin(path.join(root,n)));
const Core=require(path.join(root,"analysis_encounter_context.js"));
const Encounter=require(path.join(root,"encounter_evidence.js"));
const Planetary=require(path.join(root,"analysis_planetary.js"));
const Cross=require(path.join(root,"analysis_cross_context.js"));
const comparisonManifestPath=path.join(root,"data/analysis_comparisons/manifest.json");
const comparisons=read(comparisonManifestPath);
const evidenceManifestPath=path.join(root,"data/encounters/manifest.json");
const evidenceManifest=read(evidenceManifestPath);
function jsonGzip(file, expected) {
 const packed=fs.readFileSync(file), decoded=zlib.gunzipSync(packed);
 if(expected.gzipSha256)assert.equal(sha(packed),expected.gzipSha256,file+": gzip pin");
 if(expected.sha256)assert.equal(sha(decoded),expected.sha256,file+": decoded pin");
 return {value:JSON.parse(decoded.toString("utf8")),pin:{...pin(file),decodedBytes:decoded.length,decodedSha256:sha(decoded)}};
}
const ev=jsonGzip(path.join(root,"data/encounters/evidence.json.gz"),{gzipSha256:evidenceManifest.artifact.gzipSha256,sha256:evidenceManifest.artifact.decodedSha256});
const index=Encounter.createIndex(ev.value), records=new Map(ev.value.rows.map(r=>[r.eventId,r]));
const origins=jsonGzip(path.join(root,"data/encounters/label_origins.json.gz"),{...evidenceManifest.labelOrigins,sha256:evidenceManifest.labelOrigins.decodedSha256});
const originIndex=Encounter.createLabelOriginsIndex(origins.value,index,evidenceManifest.artifact.decodedSha256);
const timingManifestPath=path.join(root,"data/trace_chronology/manifest.json"),timingManifest=read(timingManifestPath);
const timing=occurrenceGuard?jsonGzip(path.join(root,"data/trace_chronology/evidence.json.gz"),{gzipSha256:timingManifest.gzipSha256,sha256:timingManifest.decodedSha256}):null;
const chronologyIndex=timing?require(path.join(root,"trace_chronology.js")).createEvidenceIndex(timing.value):null;
const heldSourceRows=[];
const ctx=jsonGzip(path.join(root,"data/analysis_comparisons/context_rows.json.gz"),comparisons.artifacts.context);
const nuc=jsonGzip(path.join(root,"data/analysis_comparisons/nuclear_context_v1.json.gz"),comparisons.artifacts.nuclear);
const extension=jsonGzip(path.join(root,"data/analysis_comparisons/nuclear_extension_v1.json.gz"),comparisons.artifacts.nuclearExtension);
const nuclear={...nuc.value,tests:nuc.value.tests.concat(extension.value.tests),nuclearFacilities:nuc.value.nuclearFacilities.concat(extension.value.nuclearFacilities),
 controlCoverageIntervals:[{startOrdinal:Math.min(...nuc.value.tests.map(row=>row.ordinal)),endOrdinal:Math.max(...nuc.value.tests.map(row=>row.ordinal))}]};
const facilityPath="C:/Users/jarod/Desktop/UFO Timeline map tool/webapp/static_public/data/analysis_v2/facility_analysis_v1.json.gz";
const facilities=jsonGzip(facilityPath,comparisons.artifacts.facilities);
const planPath=path.join(root,"releases/workspace-analysis-20261008/delivery_plan.json");
const plan=read(planPath), shards=plan.uploads.filter(x=>/\/summary_shards\/summary_\d+\.json\.gz$/.test(x.key)).sort((a,b)=>a.key.localeCompare(b.key));
assert.equal(shards.length,71);
const app=fs.readFileSync(path.join(root,"app.js"),"utf8");
const functionCode=name=>{const a=app.indexOf("  function "+name+"("),b=app.indexOf("\n  function ",a+3); assert.ok(a>=0&&b>a);return app.slice(a,b);};
const hydrationPin={name:"hydrateCatalogEvent",sha256:sha(functionCode("hydrateCatalogEvent"))};
const workerSource=fs.readFileSync(path.join(root,"catalog_filter_worker.js"),"utf8");
const visitStart=workerSource.indexOf("    function visitRaw(values, callback) {"),visitEnd=workerSource.indexOf("    function forEachRow(callback)",visitStart);
assert.ok(visitStart>=0&&visitEnd>visitStart);
const visitCode=workerSource.slice(visitStart,visitEnd),workerInputPin={name:"buildComparisonInputs.visitRaw",sha256:sha(visitCode)};
const adapter=vm.createContext({input:{},matched:true});vm.runInContext(visitCode,adapter);
const trace=require(path.join(root,"trace_neighborhood.js"));
const serializer=vm.createContext({TRACE_NEIGHBORHOOD:trace,CRAFT_TYPE_COLORS:trace.CRAFT_TYPE_COLORS,runtime:{craftTypeResolutionByKey:new Map()},state:{colorMode:"craft_type"},DEFAULT_COLOR_MODE:"craft_type"});
const serializerNames=["parseIsoParts","daysFromCivil","isoToOrdinal","getVisualTypeGroup","resolvedCraftTypeForEvent","craftTypeColorKeyForEvent","eventLegendKeyForMode","nullableCatalogNumber","serializeCatalogFacetWorkerRow"];
const serializerPins=serializerNames.map(name=>({name,sha256:sha(functionCode(name))}));
serializerNames.forEach(name=>vm.runInContext(functionCode(name),serializer));
assert.equal(serializer.isoToOrdinal("1970-01-01"),0);
const rows=[], identities=new Set(), shardPins=[];
let corpusCount=0;
for(const shard of shards) {
 const packed=fs.readFileSync(shard.source);assert.equal(packed.length,shard.bytes);assert.equal(sha(packed),shard.sha256);
 shardPins.push({key:shard.key,source:shard.source,bytes:shard.bytes,sha256:shard.sha256});
 for(const summary of JSON.parse(zlib.gunzipSync(packed).toString("utf8"))) {
  corpusCount++;
  const source=records.get(String(summary.event_id));if(!source)continue;
  assert.equal(source.source,summary.source);assert.equal(source.sourceRef.chunk,summary.chunk_id);assert.equal(source.sourceRef.detailIndex,summary.detail_index);
  const decorated=Encounter.decorate({...summary,sort_ordinal:serializer.isoToOrdinal(summary.sort_date_iso)},index,originIndex);
  // Same source-pinned decision as actual hydrateCatalogEvent; no source
  // precision, date value or canonical record is rewritten.
  decorated.encounterOccurrenceDateExcluded=chronologyIndex?Boolean(chronologyIndex.exclusion(summary.event_id)):null;
  const value=JSON.parse(JSON.stringify(serializer.serializeCatalogFacetWorkerRow(decorated)));
  if(occurrenceGuard)assert.equal(value.encounterOccurrenceDateExcluded,Boolean(chronologyIndex.exclusion(summary.event_id)));
  const start=value.dateStartOrdinal==null?value.sortOrdinal:value.dateStartOrdinal;
  let row;
  if(occurrenceGuard){adapter.visitRaw(value,source=>{row=JSON.parse(JSON.stringify(source));});row.id=row.eventId=String(row.eventId);}
  else row={...value,id:String(value.eventId),eventId:String(value.eventId),sortOrdinal:start,startOrdinal:start,endOrdinal:value.dateEndOrdinal==null?start:value.dateEndOrdinal,dateRole:"occurrence"};
  if(value.encounterOccurrenceDateExcluded===true){const exclusion=chronologyIndex.exclusion(summary.event_id);heldSourceRows.push({eventId:String(value.eventId),source:value.source,sourceDatePrecision:value.datePrecision,reason:exclusion.reason,abductionCode:value.encounterAbductionCode,beingMask:value.encounterBeingMask});assert.equal(row.sourceDatePrecision,value.datePrecision);assert.equal(row.datePrecision,"excluded_source_occurrence_date");assert.equal(row.dateRole,"source_date_withheld");}
  assert.ok(!identities.has(row.id));identities.add(row.id);rows.push(row);
 }
}
assert.equal(corpusCount,702893);assert.equal(rows.length,index.rowCount);
console.log(JSON.stringify({stage:"summary_join",corpusCount,encounters:rows.length,elapsedSeconds:(performance.now()-millis)/1000}));
const ordinal=iso=>Date.parse(iso+"T00:00:00Z")/86400000;
const base={rows,encounterEvidenceReady:true,ordinalEpoch:"unix_day",crops:ctx.value.crops,animals:ctx.value.animals,nuclear,
 broaderFacilities:Array.isArray(facilities.value)?facilities.value:facilities.value.rows||facilities.value.facilities||[],
 facilityCodebook:facilities.value.codes||facilities.value.codebook||comparisons.facilityCodebook,
 artifactHashes:{encounterEvidence:ev.pin.decodedSha256,comparisonContext:ctx.pin.decodedSha256,nuclearContext:nuc.pin.decodedSha256,comparisonFacilities:facilities.pin.decodedSha256}};
const checks=[],timings={};
const timed=(key,fn)=>{const a=performance.now(),value=fn();timings[key]=Math.round(performance.now()-a);console.log(JSON.stringify({stage:key,milliseconds:timings[key]}));return value;};
function summarize(model) {
 assert.equal(model.status,"ready");assert.equal(model.inferenceEligible,false);
 assert.equal(model.indexedMatchedN,rows.length);assert.equal(model.duplicateIdentityN,0);
 const groups=model.groups;
 const source=groups.find(r=>r.id==="source_abduction"), narrative=groups.find(r=>r.id==="narrative_abduction"), reported=groups.find(r=>r.id==="reported_abduction");
 assert.equal(reported.allMatchedN,source.allMatchedN+narrative.allMatchedN);
 const results=[];
 for(const group of groups) {
  const moon=model.lunar.matrix.rows.find(r=>r.id===group.id),nuclear=model.nuclear.phases.rows.find(r=>r.id===group.id),facility=model.nuclear.facilities.rows.find(r=>r.id===group.id);
  assert.equal(moon.cells.reduce((n,c)=>n+c.count,0),moon.eligible);
  assert.equal(moon.stableN+moon.ambiguousN,moon.eligible);
  for(const cell of moon.cells)assert.ok(cell.lowerCount<=cell.count&&cell.count<=cell.upperCount);
  assert.equal(facility.cells.reduce((n,c)=>n+c.count,0),facility.eligible);
  for(const cell of nuclear.cells)assert.ok(cell.count<=nuclear.eligible);
  const lanes={};
  for(const domain of ["crops","animals"]) {
   const calendar=model[domain].calendar.rows.find(r=>r.id===group.id), marker=model[domain].marker.rows.find(r=>r.id===group.id);
   assert.ok(marker.eligible<=calendar.eligible);
   for(let i=0;i<3;i++){
    assert.ok(calendar.cells[i].count==null||calendar.cells[i].count<=calendar.eligible);
    assert.ok(marker.cells[i].count==null||marker.cells[i].count<=marker.eligible);
    if(calendar.cells[i].count!=null&&marker.cells[i].count!=null)assert.ok(marker.cells[i].count<=calendar.cells[i].count);
    if(i>0&&calendar.cells[i].count!=null)assert.ok(calendar.cells[i].count>=calendar.cells[i-1].count);
   }
   assert.match(model[domain].strictSiteStatus,/unavailable/);
   lanes[domain]={calendarEligible:calendar.eligible,markerEligible:marker.eligible,
    calendarCounts:calendar.cells.map(c=>c.count),calendarPairs:calendar.cells.map(c=>c.pairCount),
    markerCounts:marker.cells.map(c=>c.count),markerPairs:marker.cells.map(c=>c.pairCount)};
  }
  results.push({id:group.id,allMatchedN:group.allMatchedN,activeN:group.activeN,lunarEligible:moon.eligible,lunarStable:moon.stableN,lunarAmbiguous:moon.ambiguousN,verifiedMoonSkyEligible:moon.sky.eligible,lunarExclusions:moon.excluded,
   nuclearEligible:nuclear.eligible,nuclearLinked:nuclear.linkedReportsN,nuclearPhaseCounts:nuclear.cells.map(c=>({id:c.id,count:c.count,pairCount:c.pairCount})),nuclearExclusions:nuclear.excluded,
   facilityEligible:facility.eligible,facilityCounts:facility.cells.map(c=>({id:c.id,count:c.count})),unknownFacilityActivity:facility.unknownActivityN,...lanes});
 }
 return {status:model.status,range:model.range,indexedMatchedN:model.indexedMatchedN,duplicateIdentityN:model.duplicateIdentityN,groups:results,
  cropsCoverage:model.crops.coverage,animalsCoverage:model.animals.coverage,nuclearCoverage:model.nuclear.coverage,nuclearSettings:model.nuclear.settings};
}
const full=timed("context_all_time",()=>Core.computeEncounterContext(base));
const fullSummary=summarize(full);
const inspectionChecks=[];
for(const groupId of ["grey","reported_abduction"]) {
 for(const [topic,axis,matrix] of [["lunar","phase",full.lunar.matrix],["nuclear","phases",full.nuclear.phases],["nuclear","distances",full.nuclear.distances],["nuclear","facilities",full.nuclear.facilities],["crops","calendar",full.crops.calendar],["crops","marker",full.crops.marker],["animals","calendar",full.animals.calendar],["animals","marker",full.animals.marker]]) {
  const nativeRow=matrix.rows.find(row=>row.id===groupId), cell=nativeRow.cells.find(cell=>cell.count>0)||nativeRow.cells.find(cell=>cell.count===0);
  if(!cell)continue;
  const result=Core.inspectReports(base,{contextTopic:topic,contextAxis:axis,rowKey:groupId,columnKey:cell.id,bucket:"cell",allIds:true});
  assert.equal(result.total,cell.count,topic+"/"+axis+" exact report count");assert.equal(result.eventIds.length,result.total);assert.equal(new Set(result.eventIds).size,result.total);
  inspectionChecks.push({topic,axis,groupId,column:cell.id,reports:result.total,allIdsComplete:true});
 }
}
const franceRange={start:ordinal("1954-09-01"),end:ordinal("1954-11-30")};
const france=timed("context_france_wave_dates",()=>Core.computeEncounterContext({...base,range:franceRange}));
const franceSummary=summarize(france);
// Independent day-bucket accumulation uses source fields and set membership;
// it does not read the core's internal links, counts, clusters or group rows.
function referenceContext(values,model,range,domain){
 const dayOf=r=>typeof r.startOrdinal==="number"?r.startOrdinal:r.sortOrdinal;
 const exact=r=>Number.isFinite(dayOf(r))&&(r.endOrdinal==null||r.endOrdinal===dayOf(r))&&["exact_day","day"].includes(r.datePrecision);
 const active=r=>!range||(Number.isFinite(dayOf(r))&&(r.endOrdinal??dayOf(r))>=range.start&&dayOf(r)<=range.end);
 const located=r=>r.mapped!==false&&Number.isFinite(r.lat)&&Number.isFinite(r.lon)&&Math.abs(r.lat)<=90&&Math.abs(r.lon)<=180;
 const list=v=>Array.isArray(v)?v.map(String):v==null?[]:[String(v)];
 const clusters=new Map;
 for(const row of values){
  if(row.legalPublicationRestriction===true||row.dedupStatus==="duplicate"||list(row.exclusionReasons).some(v=>["legal_publication_restriction","duplicate_record_excluded_from_analysis","unresolved_identity_date_or_coordinate_conflict"].includes(v))||!exact(row)||!active(row))continue;
  const key=String(row.clusterId||"").trim()||(located(row)?[domain,row.lat.toFixed(6),row.lon.toFixed(6),dayOf(row)].join("|"):domain+"|"+String(row.id||"").trim());
  if(!clusters.has(key))clusters.set(key,{row,members:[]});clusters.get(key).members.push(row);
 }
 const days=new Map;
 for(const cluster of clusters.values()){const day=dayOf(cluster.row);if(!days.has(day))days.set(day,[]);days.get(day).push(cluster);}
 const groups=Encounter.TAXONOMY.map((v,i)=>({id:v.key,select:r=>Boolean(r.encounterBeingMask&(1<<i))})).concat([
  {id:"reported_abduction",select:r=>[1,2].includes(r.encounterAbductionCode)},
  {id:"source_abduction",select:r=>r.encounterAbductionCode===1},
  {id:"narrative_abduction",select:r=>r.encounterAbductionCode===2},
  {id:"ambiguous_abduction",select:r=>r.encounterAbductionCode===3}]);
 const accum=new Map(groups.map(g=>[g.id,{eligible:0,located:0,calendarCounts:[0,0,0],calendarPairs:[0,0,0],markerCounts:[0,0,0],markerPairs:[0,0,0]}]));
 let collisions=0;
 for(const report of rows.filter(r=>exact(r)&&active(r))){
  const all=[0,0,0],near=[0,0,0],point=located(report),source=String(report.source||"").trim().toLowerCase();
  for(let lag=-30;lag<=30;lag++)for(const cluster of days.get(dayOf(report)+lag)||[]){
   const collision=cluster.members.some(c=>list(c.originUfoEventIds).includes(report.id)||list(c.originInputIds).includes(report.id)||(report.duplicateLineage&&c.lineageHash&&report.duplicateLineage===c.lineageHash)||(source&&list(c.sourceFamilyIds).concat(list(c.originPublisherCodes)).some(v=>v.toLowerCase()===source)));
   if(collision){collisions++;continue;}
   const spatial=point&&located(cluster.row)&&Cross.distanceKm(report,cluster.row)<=100;
   [0,7,30].forEach((window,i)=>{if(Math.abs(lag)<=window){all[i]++;if(spatial)near[i]++;}});
  }
  for(const g of groups.filter(g=>g.select(report))){const a=accum.get(g.id);a.eligible++;if(point)a.located++;for(let i=0;i<3;i++){a.calendarPairs[i]+=all[i];a.calendarCounts[i]+=all[i]>0?1:0;if(point){a.markerPairs[i]+=near[i];a.markerCounts[i]+=near[i]>0?1:0;}}}
 }
 assert.equal(collisions,model[domain].coverage.sourceCollisionPairs);
 let cells=0;
 for(const g of groups){const a=accum.get(g.id),calendar=model[domain].calendar.rows.find(r=>r.id===g.id),marker=model[domain].marker.rows.find(r=>r.id===g.id);
  assert.equal(calendar.eligible,a.eligible);assert.equal(marker.eligible,a.located);
  for(let i=0;i<3;i++){assert.equal(calendar.cells[i].pairCount,a.calendarPairs[i]);assert.equal(marker.cells[i].pairCount,a.markerPairs[i]);assert.equal(calendar.cells[i].count,clusters.size?a.calendarCounts[i]:null);assert.equal(marker.cells[i].count,[...clusters.values()].some(c=>located(c.row))?a.markerCounts[i]:null);cells+=2;}
 }
 return {domain,validatedCountAndPairCells:cells,eligibleContextClusters:clusters.size,knownSourceCollisionPairs:collisions};
}
const independent=timed("independent_context_reference",()=>({allTime:[referenceContext(ctx.value.crops,full,null,"crops"),referenceContext(ctx.value.animals,full,null,"animals")],franceWaveDates:[referenceContext(ctx.value.crops,france,franceRange,"crops"),referenceContext(ctx.value.animals,france,franceRange,"animals")]}));
checks.push("All 23 categories partition lunar phase estimates and preserve stable/possible bounds; nuclear phase counts use unique report sets; facility groups partition eligible reports; marker counts are bounded by calendar counts.");
checks.push("All calendar/marker count and report-context-pair cells, eligible denominators and known source-collision totals match independent day-bucket accumulation for both cohorts.");
let fixtureReview;
{
const testDay=ordinal("2000-07-01");
const fixture={id:"fixture",eventId:"fixture",source:"ufocat",datePrecision:"exact_day",startOrdinal:testDay,endOrdinal:testDay,lat:0,lon:0,mapped:true,encounterEvidenceReady:true,encounterBeingMask:Encounter.beingMask(["grey","small_humanoid"]),encounterAbductionCode:1};
const fixtureContext={id:"fixture_context",datePrecision:"exact_day",startOrdinal:testDay,endOrdinal:testDay,lat:0,lon:0,sourceFamilyIds:["independent"]};
const fixtureBase={...base,rows:[fixture,fixture],range:{start:testDay-1,end:testDay+1},crops:[fixtureContext],animals:[],nuclear:{tests:[],nuclearFacilities:[]},broaderFacilities:[]};
const dedup=Core.computeEncounterContext(fixtureBase);
assert.equal(dedup.indexedMatchedN,1);assert.equal(dedup.duplicateIdentityN,1);
const group=(model,domain,lane,id="grey")=>model[domain][lane].rows.find(r=>r.id===id);
const unknownLocation=Core.computeEncounterContext({...fixtureBase,crops:[{...fixtureContext,lat:null,lon:null}]});
const unavailableMarker=group(unknownLocation,"crops","marker").cells[0];
const own=Core.computeEncounterContext({...fixtureBase,crops:[{...fixtureContext,originUfoEventIds:["fixture"]}]});
assert.equal(group(own,"crops","calendar").cells[0].count,0);
const publisher=Core.computeEncounterContext({...fixtureBase,crops:[{...fixtureContext,originPublisherCodes:["ufocat"],sourceFamilyIds:["opaque_sf_hash"]}]});
const publisherCell=group(publisher,"crops","calendar").cells[0];
const disabled=Core.computeEncounterContext({...fixtureBase,cropCirclesEnabled:false});
assert.equal(group(disabled,"crops","calendar").cells[0].count,null);
const unknown=Core.computeEncounterContext({...fixtureBase,rows:[{...fixture,startOrdinal:null,endOrdinal:null,sortOrdinal:null,datePrecision:"unknown"}]});
assert.equal(group(unknown,"crops","calendar").eligible,0);
const span=Core.computeEncounterContext({...fixtureBase,rows:[{...fixture,endOrdinal:testDay+29,datePrecision:"month"}]});
assert.equal(group(span,"crops","calendar").eligible,0);
const boundary=Core.computeEncounterContext({...fixtureBase,range:{start:testDay,end:testDay},crops:[{...fixtureContext,startOrdinal:testDay+1,endOrdinal:testDay+1}]});
assert.equal(group(boundary,"crops","calendar").cells[2].count,null);
fixtureReview={duplicateIdentityCount:dedup.duplicateIdentityN,unmappedContextMarkerCell:unavailableMarker,ownReportCalendarCell:group(own,"crops","calendar").cells[0],originPublisherCalendarCell:publisherCell,
 unknownDateEligible:group(unknown,"crops","calendar").eligible,monthSpanEligible:group(span,"crops","calendar").eligible,rangeBoundaryOutsideContext:boundary.crops.coverage,
 missingNuclearCatalogCount:dedup.nuclear.phases.rows.find(r=>r.id==="grey").cells[0].count,
 missingFacilityInventoryCount:dedup.nuclear.facilities.rows.find(r=>r.id==="grey").cells[0].count};
assert.equal(fixtureReview.missingNuclearCatalogCount,null);
assert.equal(fixtureReview.missingFacilityInventoryCount,null);
checks.push("Exact own-report ID exclusion, duplicate encounter-ID removal, disabled-layer nulls, unknown-date exclusion and selected-range boundary clipping exercised with real core.");
}
if(occurrenceGuard){
 checks.push("Occurrence guard uses the SHA-verified chronology exclusion index, actual app serializer and actual worker input adapter. Known held source dates retain original source precision but cannot enter exact-date comparison lanes.");
}
const atlasManifestPath=path.join(root,"data/analysis_comparisons/ephemeris_atlas_manifest.json");
const atlasManifest=read(atlasManifestPath),atlasPackedPath=path.join(root,"data/analysis_comparisons/ephemeris_atlas_v1.bin.gz"),atlasPacked=fs.readFileSync(atlasPackedPath);
assert.equal(sha(atlasPacked),atlasManifest.gzipSha256);
const atlasDecoded=zlib.gunzipSync(atlasPacked);assert.equal(sha(atlasDecoded),atlasManifest.sha256);assert.equal(atlasDecoded.length,atlasManifest.byteLength);
Planetary.setEphemerisAtlas(Planetary.decodeEphemerisAtlas(atlasDecoded,atlasManifest));
const planetary=timed("planetary_france_wave_dates",()=>Core.computeEncounterPlanetary({...base,range:franceRange,planetarySettings:{zodiacSystem:"sidereal",ayanamsaId:"lahiri",aspectOrbDegrees:3}}));
for(const kind of ["zodiac","motion","aspects"]) {
 const matrix=Object.values(planetary.matrices[kind])[0], nativeRow=matrix.rows.find(row=>row.id==="grey"), cell=nativeRow.cells.find(cell=>cell.count>0)||nativeRow.cells[0];
 const result=Core.inspectReports({...base,range:franceRange,planetarySettings:{zodiacSystem:"sidereal",ayanamsaId:"lahiri",aspectOrbDegrees:3}},
 {contextTopic:"planetary",contextAxis:matrix.axisId,planetKind:kind,rowKey:"grey",columnKey:cell.id,bucket:"cell",allIds:true});
 assert.equal(result.total,cell.count);inspectionChecks.push({topic:"planetary",axis:kind,column:cell.id,reports:result.total,allIdsComplete:true});
}
assert.equal(Object.keys(planetary.matrices.zodiac).length,9);assert.equal(Object.keys(planetary.matrices.motion).length,9);assert.equal(Object.keys(planetary.matrices.aspects).length,36);
const planetGroups=[];
for(const kind of ["zodiac","motion","aspects"])for(const [axis,matrix]of Object.entries(planetary.matrices[kind]))for(const row of matrix.rows){
 assert.equal(row.cells.reduce((n,c)=>n+c.count,0),row.eligible);
 for(const cell of row.cells)assert.ok(cell.lowerCount<=cell.count&&cell.count<=cell.upperCount);
 if(kind==="zodiac"&&String(matrix.planet).toLowerCase()==="sun")planetGroups.push({id:row.id,eligible:row.eligible,excluded:row.excluded});
}
assert.equal(planetary.inferenceEligible,false);assert.match(planetary.housesStatus,/unavailable/);
checks.push("Real atlas SHA/decoded contract checked; France-wave dates exercised all 9 bodies and 36 unordered pairs. Every category/axis partitions estimates and retains interval bounds; houses remain unavailable.");
const changes=runtimePins.filter(x=>path.basename(x.path)!=="app.js"&&pin(x.path).sha256!==x.sha256).map(x=>x.path);
const appEnd=fs.readFileSync(path.join(root,"app.js"),"utf8");
for(const value of serializerPins){const start=appEnd.indexOf("  function "+value.name+"("),end=appEnd.indexOf("\n  function ",start+3);if(start<0||end<=start||sha(appEnd.slice(start,end))!==value.sha256)changes.push("app.js:"+value.name);}
const hydrationStart=appEnd.indexOf("  function hydrateCatalogEvent("),hydrationEnd=appEnd.indexOf("\n  function ",hydrationStart+3);if(sha(appEnd.slice(hydrationStart,hydrationEnd))!==hydrationPin.sha256)changes.push("app.js:hydrateCatalogEvent");
const concerns=[];
const checkedFixtures=fixtureReview;
if(checkedFixtures.unmappedContextMarkerCell.count!==null)concerns.push({id:"marker_catalog_without_coordinates",behavior:checkedFixtures.unmappedContextMarkerCell,expected:"Unavailable/null when there are no located eligible context clusters."});
if(checkedFixtures.originPublisherCalendarCell.count!==0)concerns.push({id:"known_originating_publisher_overlap",behavior:checkedFixtures.originPublisherCalendarCell,expected:"Known originating publisher codes exclude the same report collection; native cross-context engine already uses these codes."});
const sourceDateGuard=occurrenceGuard?{status:"source_pinned_occurrence_date_exclusions_applied",chronologyRelease:timingManifest.releaseId,indexExcludedDates:timing.value.excludedDates.length,encounterExcludedDates:heldSourceRows.length,
 bySource:heldSourceRows.reduce((a,r)=>(a[r.source]=(a[r.source]||0)+1,a),{}),byReason:heldSourceRows.reduce((a,r)=>(a[r.reason]=(a[r.reason]||0)+1,a),{}),bySourcePrecision:heldSourceRows.reduce((a,r)=>(a[r.sourceDatePrecision]=(a[r.sourceDatePrecision]||0)+1,a),{}),
 sourceAbductionHeld:heldSourceRows.filter(r=>r.abductionCode===1).length,narrativeAbductionHeld:heldSourceRows.filter(r=>r.abductionCode===2).length,ambiguousAbductionHeld:heldSourceRows.filter(r=>r.abductionCode===3).length,beingReportsHeld:heldSourceRows.filter(r=>r.beingMask).length,
 examples:heldSourceRows.slice(0,5),allExcludedEncounterIdsSha256:sha(heldSourceRows.map(r=>r.eventId).sort().join("\n")),preservation:"Classification badges, original source dates, precisions and canonical records unchanged; only occurrence-date comparison eligibility is withheld."}:{status:"not_applied_pre_guard_quality_intermediate"};
const receipt={schemaId:"ufo-encounter-context-real-artifact-audit-v1",generatedAtUtc:new Date().toISOString(),status:changes.length?"executed_runtime_changed":concerns.length?"review_issues_found":"passed",elapsedSeconds:Math.round((performance.now()-millis)/1000),timingsMilliseconds:timings,
 method:"All 71 frozen summary shards read in place. Only source-joined sparse encounter rows retained in memory; actual app serializer and comparison-worker input semantics used. Actual lunar/nuclear/context/planetary core executed.",
 corpusReports:corpusCount,encounterReports:rows.length,sourceJoinMismatches:0,inputArtifacts:[ev.pin,ctx.pin,nuc.pin,facilities.pin,...(timing?[timing.pin]:[]),{...pin(atlasPackedPath),decodedBytes:atlasDecoded.length,decodedSha256:sha(atlasDecoded)}],
 runtimePins,serializerPins,hydrationPin,workerInputPin,sourceDateGuard,runtimeChangesDuringAudit:changes,summaryPins:shardPins,fullTime:fullSummary,franceWaveDates:franceSummary,planetaryFrance:{status:planetary.status,bodies:Object.keys(planetary.matrices.zodiac).length,motionAxes:Object.keys(planetary.matrices.motion).length,pairAxes:Object.keys(planetary.matrices.aspects).length,groups:planetGroups,precomputation:planetary.precomputation,housesStatus:planetary.housesStatus},
 fixtureReview,independentReference:independent,checks,concerns,limitations:["Descriptive report associations, not independent incidents or event truth.","Crop/animal lanes use recorded dates and generalized public markers; strict verified site/time lane remains unavailable.","France-wave date window is worldwide for the comparison audit, matching the time preset; no France-only geography is inferred.","Nuclear source coverage ends in 1998 and reviewed nuclear institutions are a partial four-site inventory.","No visual/browser acceptance is established by this core audit."],
 reproduction:{command:"node docs/qa/encounter-atlas-20261013/audit-context-real-artifacts.mjs"+(occurrenceGuard?" --occurrence-guard":""),script:pin(fileURLToPath(import.meta.url)),outputProtection:"Existing receipt cannot be overwritten."},
 storage:{canonicalReceipt:target,corpusCopiesCreated:0,binaryDownloadsCreated:0,largeArtifactsCreated:0,retention:"Keep as unique source-pinned QA receipt and reproduction script; canonical datasets and deployment rollback remain in place."}};
receipt.inspectionChecks=inspectionChecks;
receipt.inputArtifacts.push(origins.pin,extension.pin);
receipt.limitations=receipt.limitations.map(value=>value.startsWith("Nuclear source coverage")?"FOA/SIPRI base through1998 plus six reviewed DPRK tests2006–2017; reviewed institutions remain a partial five-marker inventory. Control-date eligibility remains confined to base chronology coverage.":value);
receipt.reproduction.command="node docs/qa/encounter-complete-20261013/audit-context-real-artifacts.mjs --occurrence-guard";
const bytes=Buffer.from(JSON.stringify(receipt)+"\n");assert.ok(bytes.length<160*1024,"Small QA receipt cap");
fs.mkdirSync(path.dirname(target),{recursive:true});fs.writeFileSync(target,bytes);
console.log(JSON.stringify({status:receipt.status,receipt:target,receiptBytes:bytes.length,timings,concerns,runtimeChanges:changes},null,2));

