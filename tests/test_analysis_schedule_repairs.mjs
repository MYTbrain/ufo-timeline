import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const app = fs.readFileSync("app.js", "utf8");
function functionSource(name, followingName) {
  const start = app.indexOf("  function " + name + "(");
  const end = app.indexOf("  function " + followingName + "(",start);
  assert.ok(start >= 0 && end > start);
  return app.slice(start,end);
}
const timers = new Map();
let timerId = 0;
const posted = [];
const listeners = new Set();
const rendered = [];
const artifactLoads = new Map();
let mapRestores = 0;
const worker = {
  addEventListener: (_name,handler) => listeners.add(handler),
  removeEventListener: (_name,handler) => listeners.delete(handler),
  postMessage: message => posted.push(message),
};
const runtime = {catalogFacetWorkerRowsQueued:1,analysisRequestId:0,analysisCancellationGeneration:0,
  analysisComputeScheduleGeneration:0,analysisWorkerFlight:null,analysisCache:new Map(),
  analysisComparisonDirtyComponents:new Set(),analysisComparisonPerformanceSamples:[],analysisComparisonRequestId:0,
  analysisPerformanceSamples:[],analysisV2OverviewManifestRequested:true,discardedWorkerResults:0,
  analysisViewController:{setAnalysisState(){},setComputationPhase(){},setSectionState(){},renderAnalysisResult(result){rendered.push(result);}}};
const state = {activeView:"analysis",filterGeneration:1};
let artifactVersion = 0;
const snapshot = () => ({generation:state.filterGeneration,baselineMode:"full_catalog",
  timeRange:{mode:"full",startOrdinal:null,endOrdinal:null},contextLayers:{},areaFilter:null});
const cacheKey = value => value.generation + ":" + artifactVersion;
const noop = () => {};
const context = vm.createContext({console,Promise,Date,URL,Object,Number,String,Array,Error,Boolean,
  runtime,state,startup:{initialViewReady:true},catalog:[{event_id:1}],performance:{now:()=>0},
  window:{setTimeout(callback,delay){const id=++timerId;timers.set(id,{callback,delay});return id;},
    clearTimeout(id){timers.delete(id);}},
  ensureCatalogFacetWorker:()=>worker,getAnalysisFilterSnapshot:snapshot,analysisComputeCacheKey:cacheKey,
  catalogFacetWorkerFilterPayload:()=>({lowPrecisionValues:[]}),analysisCatalogDatasetHash:()=>"fixture",
  analysisContextReleaseHashes:()=>({}),analysisV2ArtifactHashes:()=>({}),analysisDurationArtifactHashes:()=>({}),
  analysisReportingDelayArtifactHashes:()=>({}),analysisTimeOfDayArtifactHashes:()=>({}),
  analysisWitnessCountArtifactHashes:()=>({}),analysisColorArtifactHashes:()=>({}),analysisCoordinateEvidenceArtifactHashes:()=>({}),
  ensureAnalysisContextProjections:noop,attachAnalysisV2ContextPulseSummary:value=>value,
  analysisContextEvidenceArtifactsReady:()=>false,analysisResultHasContextEvidence:()=>false,
  analysisResponseEnvelopeMatchesCurrentState(pending,message){return Boolean(pending && pending.requestId===message.requestId &&
    pending.signature===cacheKey(snapshot()) && pending.generation===state.filterGeneration &&
    pending.cancellationGeneration===message.cancellationGeneration);},
  setAnalysisMapOnlyControlsAvailable:noop,restoreMapAfterAnalysis:()=>{mapRestores+=1;},pausePlayback:noop});
context.document = {baseURI:"http://127.0.0.1:8168/",getElementById:()=>null};
context.resolveAssetPath = value => value;
context.fetch = url => new Promise(resolve=>artifactLoads.set(url,resolve));
context.ensureAnalysisV2Manifest = url => new Promise(resolve=>artifactLoads.set(url,manifest=>resolve(manifest)));
context.ensureWorldReferenceData = ()=>Promise.resolve({});
for(const [setter,flag] of [["setAnalysisDurationArtifactInWorker","analysisDurationWorkerReady"],
  ["setAnalysisTimeOfDayArtifactInWorker","analysisTimeOfDayWorkerReady"],
  ["setAnalysisGeographyArtifactInWorker","analysisGeographyWorkerReady"]]){
  context[setter] = ()=>{artifactVersion+=1;runtime[flag]=true;return Promise.resolve();};
}
for (const [name,next] of [["computeAnalysisViaWorker","setAnalysisComputationPhase"],
  ["setAnalysisComputationPhase","renderAnalysisWorkerResult"],["renderAnalysisWorkerResult","computeAnalysisForCurrentView"],
  ["computeAnalysisForCurrentView","scheduleAnalysisCompute"],["scheduleAnalysisCompute","postCatalogFacetWorkerRows"],
  ["trimAnalysisResultCache","computeAnalysisViaWorker"],["handleAnalysisViewChange","analysisContextLayerConfig"],
  ["ensureAnalysisDurationArtifact","analysisReportingDelayArtifactHashes"],
  ["ensureAnalysisTimeOfDayArtifact","requestAnalysisTimeEvidence"],
  ["ensureAnalysisGeographyArtifact","analysisDurationArtifactHashes"]]) {
  vm.runInContext(functionSource(name,next),context);
}
const flush = async () => {for(let i=0;i<12;i+=1) await Promise.resolve();};
async function runImmediateTimers(){
  for(const [id,timer] of [...timers]) if(timer.delay===0){timers.delete(id);timer.callback();}
  await flush();
}
function complete(message,result={}){
  const response = {...message,type:"analysisComputed",filterGeneration:message.generation,
    result:{summary:{activeCount:1},inferenceDeferred:Boolean(message.quickMode),marker:message.analysisSignature,...result}};
  for(const listener of [...listeners]) listener({data:response});
}
const schedule = reason => context.scheduleAnalysisCompute(reason,{immediate:true});

schedule("initial");await runImmediateTimers();
assert.equal(posted.length,1);assert.equal(posted[0].analysisPhase,"quick");
const loaders = [context.ensureAnalysisTimeOfDayArtifact(),context.ensureAnalysisDurationArtifact(),context.ensureAnalysisGeographyArtifact()];
for(const [index,path] of ["analysis_time_of_day_v1","analysis_duration_v1","analysis_v2"].entries()){
  const manifest = {releaseId:path,artifacts:{}};
  const resolver = artifactLoads.get("http://127.0.0.1:8168/data/"+path+"/manifest.json");
  assert.equal(typeof resolver,"function");
  resolver(path==="analysis_v2"?manifest:{ok:true,json:()=>Promise.resolve(manifest)});
  await loaders[index];await runImmediateTimers();
}
assert.equal(posted.length,1,"Artifact completions must wait instead of queueing worker computations");
complete(posted[0]);await flush();
assert.equal(posted.length,2,"Only the latest artifact generation may run after the prior flight");
assert.equal(posted[1].analysisSignature,"1:3");
assert.equal(rendered.length,0,"Superseded quick result must not render");
complete(posted[1]);await flush();await runImmediateTimers();
assert.equal(posted.length,3);assert.equal(posted[2].analysisPhase,"full");
assert.equal(rendered.length,1);assert.equal(rendered[0].inferenceDeferred,true);

state.filterGeneration=2;
schedule("filter changed");await runImmediateTimers();
artifactVersion+=1;schedule("coordinate evidence ready");await runImmediateTimers();
assert.equal(posted.length,3,"Filter and artifact updates must not queue behind full inference");
complete(posted[2]);await flush();
assert.equal(posted.length,4);assert.equal(posted[3].analysisSignature,"2:4");
assert.equal(rendered.length,1,"Previous full cohort must not overwrite current filters");
complete(posted[3]);await flush();await runImmediateTimers();
assert.equal(posted.length,5);assert.equal(posted[4].analysisPhase,"full");
complete(posted[4]);await flush();
assert.equal(rendered.at(-1).marker,"2:4");assert.equal(rendered.at(-1).inferenceDeferred,false);
assert.equal(runtime.analysisComputationPhase,"ready");
assert.equal(runtime.analysisCache.has("2:4"),true);

state.filterGeneration=3;schedule("another cohort");await runImmediateTimers();
assert.equal(posted.length,6);
context.handleAnalysisViewChange("map");
assert.equal(mapRestores,1);assert.equal(schedule("artifact finished on map"),false);
complete(posted[5]);await flush();
assert.equal(posted.length,6,"Map view must not launch waiting analysis work");
context.handleAnalysisViewChange("analysis");await runImmediateTimers();
assert.equal(posted.length,7);assert.equal(posted[6].analysisSignature,"3:4");
complete(posted[6]);await flush();await runImmediateTimers();
assert.equal(posted.length,8);complete(posted[7]);await flush();
assert.equal(rendered.at(-1).marker,"3:4");assert.equal(runtime.analysisWorkerFlight,null);
context.handleAnalysisViewChange("map");context.handleAnalysisViewChange("analysis");await runImmediateTimers();
assert.equal(posted.length,8,"Returning to an unchanged cohort must restore the full cached result");
assert.equal(runtime.analysisComputationPhase,"ready");
assert.equal(timers.size,0,"Worker deadlines and inference timers are released");

state.filterGeneration=4;schedule("change before map return");await runImmediateTimers();
assert.equal(posted.length,9);
context.handleAnalysisViewChange("map");context.handleAnalysisViewChange("analysis");await runImmediateTimers();
assert.equal(posted.length,9,"Reopening Analysis before the old flight completes must still wait");
complete(posted[8]);await flush();assert.equal(posted.length,10);
complete(posted[9]);await flush();await runImmediateTimers();assert.equal(posted.length,11);
complete(posted[10]);await flush();assert.equal(rendered.at(-1).marker,"4:4");
assert.equal(runtime.analysisWorkerFlight,null);assert.equal(timers.size,0);

// Exercise the production strict-lane builder against the currently pinned
// manifest without running the full inference engine or weakening its gates.
const workerCode = fs.readFileSync("catalog_filter_worker.js","utf8");
const start = workerCode.indexOf("  function spatialReadinessFromManifest(");
const end = workerCode.indexOf("\n  function ",start+3);
const strictContext = vm.createContext({analysisSpatialArtifacts:{artifactHashes:{}}});
const relationshipStart = workerCode.indexOf("  function relationshipReconciliationReadiness(");
const relationshipEnd = workerCode.indexOf("\n  function ",relationshipStart+3);
vm.runInContext(workerCode.slice(relationshipStart,relationshipEnd),strictContext);
vm.runInContext(workerCode.slice(start,end),strictContext);
const manifest = JSON.parse(fs.readFileSync("data/analysis_v2/manifest.json","utf8"));
const readiness = strictContext.spatialReadinessFromManifest(manifest);
for(const kind of ["crop","animal"]){
  const lane = readiness[kind+"_strict"];
  assert.equal(lane.status,"blocked");
  assert.ok(lane.gates.some(gate=>gate.gateId===kind+"_strict_balanced_cohort"));
  assert.ok(lane.gates.some(gate=>gate.gateId===kind+"_strict_context_clusters"));
  assert.equal(lane.laneKey,kind+"_strict");
}
assert.equal(readiness.crop_strict.eligibleN,1);assert.equal(readiness.animal_strict.eligibleN,0);
console.log("Actual Analysis quick/full scheduling, artifact coalescing, latest filters, map return, and strict-lane assertions passed");
