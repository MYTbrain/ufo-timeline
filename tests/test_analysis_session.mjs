import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFile } from "node:fs/promises";
import vm from "node:vm";
const require = createRequire(import.meta.url);
const Session = require("../analysis_session.js");
const first = {
  eventIds:[0,"0",1,"2"], label:"1954 · France", scope:"Current filtered reports", provenance:{datasetCount:702893,hash:"release-one",filters:{sources:["alpha"]}},
  summary:{reportN:3,mappedN:2,unmappedN:1,datedN:1,undatedN:2,distributions:{
    source:{eligibleN:3,unknownN:0,rows:[{key:"alpha",label:"Alpha",count:2},{key:"beta",label:"Beta",count:1}]},
    craft:{eligibleN:2,unknownN:1,rows:[{key:"disc",label:"Disc",count:2}]},
    being:{eligibleN:1,unknownN:2,multiLabel:true,rows:[{key:"grey",label:"Grey",count:1},{key:"small",label:"Small",count:1}]},
    abduction:{eligibleN:1,unknownN:2,rows:[{key:"source_reported",label:"Source-classified",count:1}]}
  }}
};
const second = {eventIds:[2,3],label:"1973",scope:"All reports",provenance:{hash:"release-one"},summary:{reportN:2,mappedN:1,unmappedN:1,datedN:2,undatedN:0,distributions:{
  source:{eligibleN:2,unknownN:0,rows:[{key:"alpha",label:"Alpha",count:1},{key:"gamma",label:"Gamma",count:1}]},
  being:{eligibleN:2,unknownN:0,multiLabel:true,rows:[{key:"grey",label:"Grey",count:1},{key:"humanoid",label:"Humanoid",count:1}]}
}}};
const store=Session.createStore(); let notices=[];
const unsubscribe=store.subscribe(state=>notices.push(state.version));
assert.equal(store.getState().version,0);
store.setGroup("a",first); const captured=store.getState().groups.A;
assert.deepEqual(captured.eventIds,["0","1","2"],"epoch/index-zero report identity must survive and duplicates count once");
assert.equal(captured.reportCount,3);assert.equal(captured.summary.reportN,3);assert.equal(captured.provenance.datasetCount,702893);
first.eventIds.push(100);first.provenance.filters.sources.push("later-source");first.summary.distributions.source.rows[0].count=0;
assert.equal(captured.reportCount,3);assert.deepEqual(captured.provenance.filters.sources,["alpha"]);assert.equal(captured.summary.distributions.source.rows[0].count,2,"external mutations cannot alter a capture");
assert(Object.isFrozen(captured.eventIds));assert(Object.isFrozen(captured.provenance.filters));assert(Object.isFrozen(captured.summary.distributions.being.rows));
assert.throws(()=>captured.eventIds.push("9"),TypeError);
store.setGroup("B",second); const state=store.getState(),comparison=state.comparison;
assert.equal(comparison.overlap.reportN,1);assert.equal(comparison.overlapCount,1);assert.equal(comparison.overlap.shareA,1/3);assert.equal(comparison.overlap.shareB,1/2);
assert.equal(comparison.overlap.unionN,4);assert.equal(comparison.overlap.onlyAN,2);assert.equal(comparison.overlap.onlyBN,1);
assert.equal(comparison.a.mappedN,2);assert.equal(comparison.b.datedN,2);
const grey=comparison.distributions.being.rows.find(r=>r.key==="grey");
assert.equal(grey.aShare,1);assert.equal(grey.bShare,1/2);assert.equal(grey.aShareOfReports,1/3);assert.equal(grey.bShareOfReports,1/2);
assert.equal(grey.shareDifference,1/2);assert.equal(grey.reportShareDifference,1/3-1/2);
assert.equal(comparison.distributions.being.unknown.aShareOfReports,2/3);assert.equal(comparison.distributions.being.multiLabel,true);
assert(comparison.distributions.being.rows.reduce((sum,r)=>sum+(r.aShare||0),0)>1,"multi-label being counts are allowed to overlap");
const beta=comparison.distributions.source.rows.find(r=>r.key==="beta");assert.equal(beta.bCount,0,"available complete source summary can have a true zero");
const disc=comparison.distributions.craft.rows[0];assert.equal(disc.bCount,null);assert.equal(disc.bShare,null);assert.equal(disc.bShareOfReports,null);assert.equal(comparison.distributions.craft.available,false,"an absent field summary is not a zero distribution");
assert.equal(comparison.distributions.craft.b.unknownN,null);
assert.equal(comparison.inferenceEligible,false);assert.match(comparison.countUnit,/reports/);assert.match(comparison.countUnit,/not independent incidents/);
assert.equal(store.useGroup("A"),true);assert.equal(store.getState().selection,captured);assert.equal(store.getState().activeGroup,"A");
const aReference=store.getState().groups.A,bReference=store.getState().groups.B;
store.useSelection({eventIds:["900"],label:"Chart cell",summary:{reportN:1}});
assert.equal(store.getState().activeGroup,null);assert.equal(store.getState().selection.reportCount,1);
assert.equal(store.getState().groups.A,aReference);assert.equal(store.getState().groups.B,bReference,"drilldowns/live filter changes cannot replace saved A/B cohorts");
store.clearSelection();assert.equal(store.getState().selection,null);assert.equal(store.getState().groups.A,aReference);assert.equal(store.getState().groups.B,bReference);
store.useGroup("A");store.setGroup("A",{eventIds:["7"],label:"Replacement A"});
assert.equal(store.getState().selection,captured,"repinning is not an implicit active-cohort change");assert.equal(store.getState().activeGroup,null,"the old capture must not masquerade as replacement Group A");
store.useGroup("B");const appliedB=store.getState().selection;store.clearGroup("B");assert.equal(store.getState().selection,appliedB);assert.equal(store.getState().activeGroup,null);
store.setGroup("B",{eventIds:[],label:"Empty pinned group",summary:{reportN:0,mappedN:0,unmappedN:0}});
const beforeEmptyApply=store.getState();assert.equal(store.useGroup("B"),false);assert.equal(store.getState(),beforeEmptyApply);
const emptyCompare=Session.compareGroups({eventIds:[],summary:{reportN:0}}, {eventIds:[],summary:{reportN:0}});
assert.equal(emptyCompare.overlap.reportN,0);assert.equal(emptyCompare.overlap.shareA,null,"zero denominator does not produce NaN or a misleading zero share");
assert.equal(Session.compareGroups(null,{eventIds:[]}),null);
const unavailable=Session.compareGroups({eventIds:[1],summary:{reportN:1,distributions:{source:[{key:"alpha",count:1}]}}},{eventIds:[2],summary:{reportN:1}});
assert.equal(unavailable.distributions.source.rows[0].aShare,null,"count-only summaries cannot invent eligible denominators");assert.equal(unavailable.distributions.source.rows[0].aShareOfReports,1);
let stable=store.getState();
assert.throws(()=>store.setGroup("A",{eventIds:[1,1],summary:{reportN:2}}),/unique captured IDs/);assert.equal(store.getState(),stable);
assert.throws(()=>store.setGroup("A",{eventIds:[1],summary:{mappedN:1,unmappedN:1}}),/does not match captured/);
assert.throws(()=>store.setGroup("A",{eventIds:[1],summary:{distributions:{source:{eligibleN:1,unknownN:0,rows:[{key:"x",count:0}]}}}}),/eligible pool/);
assert.throws(()=>store.setGroup("C",{eventIds:[]}),/slot/);assert.throws(()=>store.useSelection({eventIds:[null]}),/identity/);
let cyclic={};cyclic.self=cyclic;assert.throws(()=>store.useSelection({eventIds:[],provenance:cyclic}),/cyclic/);
const noticesBeforeUnsubscribe=notices.length;unsubscribe();store.clearAll();assert.equal(notices.length,noticesBeforeUnsubscribe);assert.equal(store.getState().groups.A,null);assert.equal(store.getState().groups.B,null);assert.equal(store.getState().selection,null);
assert.equal(Session.createStore().getState().groups.A,null,"another page-local store cannot recover prior groups");
const listenerErrors=[];const isolated=Session.createStore({onListenerError:error=>listenerErrors.push(error.message)});let healthyListener=0;
isolated.subscribe(()=>{throw new Error("broken view");});isolated.subscribe(()=>healthyListener++);isolated.setGroup("A",{eventIds:[0]});assert.equal(healthyListener,1);assert.deepEqual(listenerErrors,["broken view"]);
const metadataIds = new Proxy(new Array(1000).fill("external-id"), { get(target,key) { if (/^\d+$/.test(String(key))) throw new Error("Metadata membership must not be recopied"); return Reflect.get(target,key); } });
const compacted=Session.createStore();compacted.setGroup("A",{eventIds:[0],provenance:{activeSnapshot:{eventIds:metadataIds},report_ids:new Set(["1","2"]),sourceIds:["preserve-source-reference"]}});
const compactProvenance=compacted.getState().groups.A.provenance;
assert.deepEqual(compactProvenance.activeSnapshot.eventIds,{reportIdsOmitted:true,providedIdCount:1000,membershipStoredAt:"cohort.eventIds"});
assert.equal(compactProvenance.report_ids.providedIdCount,2);assert.deepEqual(compactProvenance.sourceIds,["preserve-source-reference"],"source-reference identifiers are not report membership");
const source=await readFile(new URL("../analysis_session.js",import.meta.url),"utf8");
const forbidden=()=>{throw new Error("Unexpected persistence/network/timer access");};
const sandbox={};for(const name of ["localStorage","sessionStorage","indexedDB","fetch","XMLHttpRequest","setTimeout","document"]){Object.defineProperty(sandbox,name,{get:forbidden});}
vm.createContext(sandbox);vm.runInContext(source,sandbox);vm.runInContext('var s=UfoAnalysisSession.createStore();s.setGroup("A",{eventIds:[0]});s.useGroup("A");s.clearAll();',sandbox);
console.log("Analysis session: immutable RAM captures, distinct report units, group/selection lifecycle, exact overlap, explicit denominators, unknown coverage and unavailable fields passed.");
