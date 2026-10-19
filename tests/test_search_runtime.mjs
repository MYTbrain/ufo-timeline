import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import crypto from "node:crypto";
import zlib from "node:zlib";
import vm from "node:vm";
import { createRequire } from "node:module";
import { buildSearchIndex } from "../scripts/build_search_index.mjs";
const require=createRequire(import.meta.url), Query=require("../search_query.js"), Runtime=require("../search_runtime.js");
const directory=fs.mkdtempSync(path.join(os.tmpdir(),"ufo-search-runtime-"));
const source=path.join(directory,"source");fs.mkdirSync(source);
const rows=[
  {event_id:0,description:"Topsoil and plants collected by grey beings.",source:"archive",has_coordinates:false},
  {event_id:"001",description:"SOIL samples, red craft, no beings noted.",source:"archive"},
  {event_id:"9007199254740993",description:"A plantation — échantillon 🌱; İSTANBUL.",source:"archive"},
  {event_id:9,description:"Plants only. No soil sample phrase.",source:"archive"},
  {event_id:10,description:"Unrelated original report.",source:"archive"},
];
function write(file,value){const bytes=zlib.gzipSync(Buffer.from(JSON.stringify(value))),filename=path.join(source,file);fs.writeFileSync(filename,bytes);return{path:filename,sha256:crypto.createHash("sha256").update(bytes).digest("hex")};}
const summaries=write("summaries.json.gz",rows.map(row=>({event_id:row.event_id}))),details=write("details.json.gz",rows);
const pins=path.join(source,"pins.json");fs.writeFileSync(pins,JSON.stringify({summary_shards:[summaries],detail_chunks:[{...details,id:"fixture"}]}));
const output=path.join(directory,"index");
const built=await buildSearchIndex({pinsPath:pins,outputDir:output,pageSize:2,maxPackBytes:1024,expectedRecordCount:5});
// Optional hot fragments are exact unions, using the same ordinal varints as
// ordinary vocabulary postings. A zero-hit fragment never needs a byte request.
const hotBytes=Buffer.from([0,1,2]);fs.writeFileSync(path.join(output,"fragments_000.pack"),hotBytes);
built.manifest.fragments=[["missing_fragment",3,0,0],["soil",0,3,3]];
built.manifest.fragmentPacks=[{file:"fragments_000.pack",start:0,bytes:3,sha256:crypto.createHash("sha256").update(hotBytes).digest("hex")}];
fs.writeFileSync(path.join(output,"manifest.json"),JSON.stringify(built.manifest));
const requests=[];let rangeMode="normal",metadataFailures=0,cancelledBody=0,delays=0,inFlight=0,maxInFlight=0;
async function fixtureFetch(url,options={}){
  const file=path.basename(new URL(url).pathname),range=options.headers&&options.headers.Range;
  requests.push({file,range});
  if(file==="manifest.json"&&metadataFailures-->0)return new Response("unavailable",{status:503});
  if(options.signal?.aborted)throw new DOMException("cancelled","AbortError");
  if(range&&delays){
    inFlight+=1;maxInFlight=Math.max(maxInFlight,inFlight);
    try{await new Promise((resolve,reject)=>{const timer=setTimeout(resolve,delays);options.signal?.addEventListener("abort",()=>{clearTimeout(timer);reject(new DOMException("cancelled","AbortError"));},{once:true});});}
    finally{inFlight-=1;}
  }
  const data=fs.readFileSync(path.join(output,file));
  if(!range)return new Response(data,{status:200,headers:{"Content-Type":file.endsWith(".json")?"application/json":"application/gzip"}});
  if(rangeMode==="ignore")return new Response(new ReadableStream({start(controller){controller.enqueue(data);},cancel(){cancelledBody+=1;}}),{status:200});
  const [,startText,endText]=/^bytes=(\d+)-(\d+)$/.exec(range),start=Number(startText),end=Number(endText);
  const contentRange=rangeMode==="wrong"?`bytes ${start+1}-${end}/${data.length}`:`bytes ${start}-${end}/${data.length}`;
  const body=rangeMode==="short"?data.subarray(start,end):data.subarray(start,end+1);
  return new Response(body,{status:206,headers:{"Content-Range":contentRange}});
}
const manifestSha256=crypto.createHash("sha256").update(fs.readFileSync(path.join(output,"manifest.json"))).digest("hex");
const config={manifestUrl:"https://fixture.test/index/manifest.json",manifestSha256,fetch:fixtureFetch,concurrency:2};
const runtime=Runtime.create(config);
assert.equal(requests.length,0,"creating the runtime must not fetch metadata or start search work");
function options(plan,extra={}){return{expectedRecordCount:rows.length,metadataComplete:true,
  supplementalMatches:Object.fromEntries(plan.terms.map(term=>[term,[]])),...extra};}
for(const text of ["soil","plant","soil AND grey","soil OR échant","(red OR grey) AND soil",'"soil sample"',"🌱","—","i̇","i","SOIL samples",'"no beings" OR 🌱',"zzzz",'"sample phrase" AND plants']){
  const plan=Query.compile(text),result=await runtime.search(plan,options(plan));
  const expected=rows.filter(row=>Query.matchEvent(plan,row)).map(row=>String(row.event_id));
  assert.deepEqual(result.ids,expected,"exact indexed-vs-direct parity: "+text);
  assert.equal(result.complete,true,text+JSON.stringify(result.errors));
  assert.equal(result.planKey,plan.cacheKey);
  assert.equal(result.coverage.includesUnmapped,true);
}
assert(requests.some(request=>request.file==="fragments_000.pack"),"common substring terms use the exact direct posting accelerator");
const noHitPlan=Query.compile("missing_fragment"),noHitBefore=requests.length;
assert.deepEqual((await runtime.search(noHitPlan,options(noHitPlan))).ids,[]);
assert.equal(requests.length,noHitBefore,"known empty fragment requires no range fetch");
const before=requests.length,soil=Query.compile("soil");
await runtime.search(soil,options(soil));await runtime.search(soil,options(soil));
assert.equal(requests.length,before,"validated byte cache prevents repeated fetches; search result claims are recomputed");
const plan=Query.compile("original AND corrected");
const supplemental={original:[],corrected:["10"]};
const mixed=await runtime.search(plan,options(plan,{supplementalMatches:supplemental}));
assert.deepEqual(mixed.ids,["10"],"AND may match preserved text in one leaf and corrected metadata in another");
const missingOverlay=await runtime.search(soil,{expectedRecordCount:5});
assert.equal(missingOverlay.complete,false);assert.equal(missingOverlay.coverage.metadataOverlay,false);
assert.match(missingOverlay.errors[0].message,/metadata/);
const unknown=await runtime.search(soil,options(soil,{supplementalMatches:{soil:["not-a-current-ID"]}}));
assert.equal(unknown.complete,false);assert.equal(unknown.errors[0].unindexedReports,1);
const wrongCount=await runtime.search(soil,options(soil,{expectedRecordCount:6}));
assert.equal(wrongCount.complete,false);assert.deepEqual(wrongCount.ids,[]);
const wrongSet=await runtime.search(soil,options(soil,{expectedIdSetSha256:"a-different-release"}));
assert.equal(wrongSet.complete,false);
const excerpt=await runtime.getExcerpt("0",Query.compile("soil"),{maxLength:100});
assert.equal(excerpt.recordId,"0");assert(excerpt.matched);assert(excerpt.segments.some(segment=>segment.match&&segment.text==="soil"));
assert.equal(await runtime.getExcerpt("not-found",soil),null);
runtime.destroy();await assert.rejects(()=>runtime.search(soil,options(soil)),{name:"AbortError"});
const unpinned=Runtime.create({...config,manifestSha256:"0".repeat(64)});
const rejectedPin=await unpinned.search(soil,options(soil));
assert.equal(rejectedPin.complete,false);assert.match(rejectedPin.errors[0].message,/manifest does not match/);unpinned.destroy();

// A range host returning a whole pack must be rejected before downloading its body.
for(const mode of ["ignore","wrong","short"]){
  rangeMode=mode;const failedRuntime=Runtime.create(config),partial=await failedRuntime.search(soil,options(soil));
  assert.equal(partial.complete,false,mode);assert(partial.errors.length);
  rangeMode="normal";const retry=await failedRuntime.search(soil,options(soil));
  assert.equal(retry.complete,true,"range failure must not poison a later retry");
  assert.deepEqual(retry.ids,["0","001","9"]);failedRuntime.destroy();
}
assert(cancelledBody>0,"HTTP200 full-pack body was explicitly cancelled");
metadataFailures=1;const retryRuntime=Runtime.create(config);
assert.equal((await retryRuntime.search(soil,options(soil))).complete,false);
assert.equal((await retryRuntime.search(soil,options(soil))).complete,true,"metadata failure must be retryable");retryRuntime.destroy();

delays=40;const cancellable=Runtime.create(config),controller=new AbortController();
const pending=cancellable.search(Query.compile("🌱"),options(Query.compile("🌱"),{signal:controller.signal}));
setTimeout(()=>controller.abort(),10);
await assert.rejects(()=>pending,{name:"AbortError"});
assert.equal((await cancellable.search(soil,options(soil))).complete,true,"cancellation is separate from incomplete coverage and does not poison the index");
const older=cancellable.search(Query.compile("🌱"),options(Query.compile("🌱")));older.catch(()=>{});
const newer=cancellable.search(soil,options(soil));
await assert.rejects(()=>older,{name:"AbortError"});assert.equal((await newer).complete,true);
assert(maxInFlight<=2,"range requests obey the shared concurrency bound");
cancellable.destroy();

// The browser bridge itself creates a worker only on demand, forwards compact
// options, ignores stale completions and terminates all requests on destruction.
const workers=[];
class FakeWorker{
  constructor(url){this.url=url;this.listeners={};this.messages=[];workers.push(this);}
  addEventListener(type,callback){this.listeners[type]=callback;}
  postMessage(data){this.messages.push(data);}
  emit(data){this.listeners.message({data});}
  terminate(){this.terminated=true;}
}
const context={URL,AbortController,Map,Promise,Error,Object,globalThis:null,Worker:FakeWorker,location:{href:"https://fixture.test/index.html"},
  document:{currentScript:{src:"https://fixture.test/search_runtime.js?v=one"}}};context.globalThis=context;
vm.runInNewContext(fs.readFileSync(new URL("../search_runtime.js",import.meta.url),"utf8"),context);
const bridge=context.UfoSearchRuntime.create({manifestUrl:config.manifestUrl,manifestSha256});assert.equal(workers.length,0);
const first=bridge.search(soil,{onProgress:()=>{}});first.catch(()=>{});
assert.equal(workers.length,1);assert.equal(workers[0].url,"https://fixture.test/search_worker.js?v=one");
const firstRequest=workers[0].messages[0];assert.equal(firstRequest.type,"search");assert(!("onProgress" in firstRequest.options));
assert.equal(firstRequest.config.manifestSha256,manifestSha256,"the worker bridge retains the pinned manifest checksum");
const second=bridge.search(soil,{});await assert.rejects(()=>first,{name:"AbortError"});
const secondRequest=workers[0].messages.findLast(message=>message.type==="search");
workers[0].emit({type:"result",requestId:firstRequest.requestId,result:{ids:["stale"]}});
workers[0].emit({type:"result",requestId:secondRequest.requestId,result:{ids:["fresh"],complete:true}});
assert.deepEqual((await second).ids,["fresh"]);
const held=bridge.getExcerpt("0",soil);bridge.destroy();await assert.rejects(()=>held,{name:"AbortError"});assert(workers[0].terminated);
console.log("Search runtime: exact range parity, split metadata AND, coverage, retry, cancellation, bounded caches and lazy worker bridge passed.");
// Explicitly retained counterpart is the reproducible five-report fixture above;
// these unique small test-only paths contain no project source or canonical data.
fs.rmSync(directory,{recursive:true});
