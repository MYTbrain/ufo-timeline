import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const statisticsCode=fs.readFileSync("analysis_stats.js","utf8");
const exportIndex=statisticsCode.lastIndexOf("    computeAnalysis,");
assert.ok(exportIndex>0);
const instrumentedStats=statisticsCode.slice(0,exportIndex)+
  "    __intervalTest: {membershipForRow, baselineDescriptor, createAccumulator, addRow, addQuickCoreRow},\n"+
  statisticsCode.slice(exportIndex);
const messages=[];
const self={postMessage:message=>messages.push(message)};
const workerCode=fs.readFileSync("catalog_filter_worker.js","utf8");
const hookIndex=workerCode.indexOf("  self.onmessage = ");
assert.ok(hookIndex>0);
const workerContext=vm.createContext({self,console});
vm.runInContext(instrumentedStats,workerContext);
vm.runInContext(workerCode.slice(0,hookIndex)+
  "  self.__intervalTest={activeAnalysisIdRows,normalizedFilters};\n"+workerCode.slice(hookIndex),workerContext);
const stats=self.UfoAnalysisStats;
const epoch=stats.ordinalFromCivil(1970,1,1);
const ordinal=(year,month,day)=>stats.ordinalFromCivil(year,month,day)-epoch;
const april1=ordinal(1992,4,1),april14=ordinal(1992,4,14),april15=ordinal(1992,4,15),april30=ordinal(1992,4,30);
const yearStart=ordinal(1992,1,1),yearEnd=ordinal(1992,12,31);
const base={source:"fixture",type:"Triangle",craftType:"triangle",mapped:false,precision:"unknown",craftConfidence:"high"};
const rows=[
  {...base,eventId:"month",datePrecision:"month",sortOrdinal:april15,dateStartOrdinal:april1,dateEndOrdinal:april30},
  {...base,eventId:"year",datePrecision:"year",sortOrdinal:ordinal(1992,7,1),dateStartOrdinal:yearStart,dateEndOrdinal:yearEnd},
  {...base,eventId:"exact-active",datePrecision:"exact_day",sortOrdinal:april15},
  {...base,eventId:"exact-previous",datePrecision:"exact_day",sortOrdinal:april14},
  {...base,eventId:"undated",datePrecision:"unknown",sortOrdinal:null},
];
function send(message){
  messages.length=0;self.onmessage({data:message});
  assert.equal(messages.length,1);assert.notEqual(messages[0].type,"catalogFacetWorkerError",messages[0].error);
  return messages[0];
}
send({type:"addCatalogFacetRows",rows});
const filters={sourceMode:"all",typeMode:"all",precisionMode:"all",hideLowPrecision:false,hideNonExactDates:false};
const request=day=>({filters,timeRangeMode:"window",timeRangeStartOrdinal:day,timeRangeEndOrdinal:day,
  baselineMode:"previous_equal_duration",selectedDomains:["overview","time","sources_quality"],quickMode:true});
for(const [day,count,ids] of [[april1,2,["month","year"]],[april30,2,["month","year"]],
  [ordinal(1992,5,1),1,["year"]],[ordinal(1993,1,1),0,[]]]){
  const query=request(day);
  const result=send({...query,type:"computeAnalysis",requestId:"analysis-"+day}).result;
  assert.equal(result.summary.activeCount,count,"The stored midpoint must not control interval inclusion");
  const facet=send({...query,type:"computeCatalogFacetCounts",requestId:"facets-"+day}).result;
  assert.equal(facet.legendEventCounts.triangle||0,count,"Facet and Analysis date membership must agree");
  const activeIds=self.__intervalTest.activeAnalysisIdRows(query,null,self.__intervalTest.normalizedFilters(query),null,null,null,new Set());
  assert.deepEqual(Array.from(activeIds,item=>item.eventId).sort(),ids.sort(),"Active-query endpoint IDs use interval overlap");
}
const comparison=send({...request(april15),type:"computeAnalysis",requestId:"disjoint-previous"}).result;
assert.equal(comparison.summary.activeCount,3);
assert.equal(comparison.summary.referenceCount,1,"Month/year rows overlapping the active window must be excluded from the disjoint previous reference");
const civilRows=rows.map(row=>({...row,sortOrdinal:row.sortOrdinal==null?null:row.sortOrdinal+epoch,
  dateStartOrdinal:row.dateStartOrdinal==null?null:row.dateStartOrdinal+epoch,
  dateEndOrdinal:row.dateEndOrdinal==null?null:row.dateEndOrdinal+epoch}));
const descriptor=stats.__intervalTest.baselineDescriptor(stats.BASELINE_MODES.PREVIOUS_EQUAL_DURATION,
  {start:april15+epoch,end:april15+epoch},false);
for(const row of civilRows.filter(row=>["month","year"].includes(row.eventId))){
  const membership=stats.__intervalTest.membershipForRow(row,{},descriptor);
  assert.equal(membership.active,true);assert.equal(membership.reference,false);
}
const other=stats.computeAnalysis({rows:civilRows,timeRangeStartOrdinal:april15+epoch,timeRangeEndOrdinal:april15+epoch,
  baselineMode:"other_dates_balanced",quickMode:true});
assert.equal(other.summary.activeCount,3);assert.equal(other.summary.referenceCount,1);
for(const accumulatorFunction of ["addRow","addQuickCoreRow"]){
  const accumulator=stats.__intervalTest.createAccumulator("year-only");
  stats.__intervalTest[accumulatorFunction](accumulator,civilRows[1]);
  assert.equal(accumulator.months.get("unknown"),1,"A year-precision date has no observed month");
  assert.equal(accumulator.months.has("07"),false);assert.equal(accumulator.monthYears.size,0);
}

const appCode=fs.readFileSync("app.js","utf8");
function appFunction(name,next){
  const start=appCode.indexOf("  function "+name+"(");
  const end=appCode.indexOf("  function "+next+"(",start);
  assert.ok(start>=0&&end>start);return appCode.slice(start,end);
}
const appEvents=rows.map(row=>({event_id:row.eventId,source:"fixture",type:"Triangle",has_coordinates:false,
  date_precision:row.datePrecision,sort_ordinal:row.sortOrdinal,
  date_iso:row.eventId==="month"?"1992-04-01":row.eventId==="year"?"1992-01-01":null,
  end_date_iso:row.eventId==="month"?"1992-04-30":row.eventId==="year"?"1992-12-31":null,
  date_recovery_contract:["month","year"].includes(row.eventId)?"mufon_zero_component_interval_v1":null}));
const state={timeRangeMode:"window",timeRangeStartOrdinal:april1,timeRangeEndOrdinal:april1,
  timelineCatalog:appEvents,timelinePlaybackEvents:appEvents.filter(event=>event.sort_ordinal!=null),
  timelineCatalogDisplayOrder:appEvents,keywordActive:false};
let binarySearchCalls=0;
const appContext=vm.createContext({state,runtime:{},daysFromCivil:(year,month,day)=>ordinal(year,month,day),
  parseIsoParts:()=>null,eventLegendKeyForMode:()=>"triangle",invalidateTraceSequenceCache(){},
  lowerBoundTimelineEventIndex(){binarySearchCalls+=1;return 0;},upperBoundTimelineEventIndex(){binarySearchCalls+=1;return 0;},
  sortFilteredCatalog:events=>events});
vm.runInContext(appFunction("isoToOrdinal","ordinalToIso"),appContext);
const serializerStart=appCode.indexOf("  function nullableCatalogNumber(");
const serializerEnd=appCode.indexOf("  const ANALYSIS_BASELINE_MODES",serializerStart);
vm.runInContext(appCode.slice(serializerStart,serializerEnd),appContext);
const evidenceStart=appCode.indexOf("  function eventHasExactDateEvidence(");
const evidenceEnd=appCode.indexOf("\n  function ",evidenceStart+3);
vm.runInContext(appCode.slice(evidenceStart,evidenceEnd),appContext);
vm.runInContext(appFunction("eventMatchesTimeRange","rebuildTimeFilteredCatalog"),appContext);
vm.runInContext(appFunction("rebuildTimeFilteredCatalog","sortFilteredCatalog"),appContext);
for(const event of appEvents.slice(0,2)){
  assert.equal(appContext.eventMatchesTimeRange(event),true);
  const packed=appContext.serializeCatalogFacetWorkerRow(event);
  assert.equal(packed.dateStartOrdinal,event.event_id==="month"?april1:yearStart);
  assert.equal(packed.dateEndOrdinal,event.event_id==="month"?april30:yearEnd);
  assert.equal(appContext.eventHasExactDateEvidence(event),false);
}
appContext.rebuildTimeFilteredCatalog();
assert.equal(binarySearchCalls,0,"Recovered intervals must bypass single-ordinal index slicing");
assert.deepEqual(Array.from(state.filteredCatalog,event=>event.event_id),["month","year"]);
assert.equal(state.filteredExactDateEventCount,0);
console.log("Actual app/worker/statistics month and year interval, arbitrary-day filtering, unknown month, and disjoint-cohort assertions passed");
