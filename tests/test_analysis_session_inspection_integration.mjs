import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const day = iso => Date.parse(iso + 'T00:00:00Z') / 86400000;
const output = [], self = { postMessage: value => output.push(value) };
const context = vm.createContext({self, console});
for (const file of ['analysis_stats.js','catalog_filter_worker.js']) vm.runInContext(fs.readFileSync(file,'utf8'),context);
async function ask(data) {
  output.length = 0; self.onmessage({data});
  for (let n=0; n<100 && !output.length; n++) await new Promise(resolve=>setImmediate(resolve));
  assert.ok(output.length,'worker responds'); return output.at(-1);
}
await ask({type:'addCatalogFacetRows',rows:[
  {eventId:'1',sortOrdinal:day('1973-10-01'),source:'one',type:'Disk',craftType:'disc_saucer',country:'United States',adminRegion:'WA',lat:47,lon:-122,mapped:true,precision:'city',datePrecision:'exact_day',craftConfidence:'high'},
  {eventId:'2',sortOrdinal:day('1973-10-02'),source:'two',type:'Triangle',craftType:'triangle',country:'Belgium',mapped:false,precision:'unknown',datePrecision:'exact_day',craftConfidence:'medium'},
  {eventId:'3',sortOrdinal:null,source:'one',type:'Unknown',craftType:'unknown',country:'unknown',mapped:false,precision:'unknown',datePrecision:'unknown'}
]});
const captured = (await ask({type:'captureAnalysisSession',requestedEventIds:['1','2','3']})).result;
assert.equal(captured.summary.reportN,3);
const group = {eventIds:captured.eventIds,reportCount:3,provenance:{encounterEvidenceMode:'all'}};
for (const [domain,distribution] of Object.entries(captured.summary.distributions)) {
  if (!distribution) continue;
  for (const row of [...distribution.rows,{key:'__unknown__',count:distribution.unknownN}]) {
    const held = {...group,inspectionSummary:{distribution}};
    const request = {type:'inspectAnalysisSessionEvidence',section:'craft',domainKey:domain,rowKey:row.key,groups:{A:held,B:held},limit:1,offset:0};
    const response = await ask(request); assert.equal(response.type,'analysisSessionEvidenceInspected',response.error);
    for (const side of Object.values(response.result.groups)) {
      assert.equal(side.matchedN,row.count,domain+':'+row.key); assert.equal(side.totalN,3);
      assert.equal(side.rows.length,Math.min(row.count,1)); assert.equal(side.hasMore,row.count>1);
      if (side.rows.length) assert.deepEqual([...side.rows[0].eventIds],[side.rows[0].id]);
    }
    if (row.count>1) {
      const next=await ask({...request,offset:1}); assert.notEqual(next.result.groups.A.rows[0].id,response.result.groups.A.rows[0].id,'pagination advances membership');
    }
  }
}
const coverage = {...group,inspectionSummary:captured.summary};
for(const key of ['mappedN','unmappedN','datedN','undatedN']) {
  const response=await ask({type:'inspectAnalysisSessionEvidence',section:'overview',domainKey:'coverage',rowKey:key,groups:{A:coverage,B:coverage}});
  assert.equal(response.type,'analysisSessionEvidenceInspected',response.error); assert.equal(response.result.groups.A.matchedN,captured.summary[key]);
}
const unavailable={...group,inspectionSummary:{distribution:null}};
const missing=await ask({type:'inspectAnalysisSessionEvidence',section:'craft',domainKey:'duration',rowKey:'__unknown__',groups:{A:unavailable,B:unavailable}});
assert.equal(missing.result.groups.A.available,false);assert.equal(missing.result.groups.A.matchedN,null);assert.match(missing.result.groups.A.reason,/unavailable when the group was held/);
const mismatched={...group,inspectionSummary:{distribution:{...captured.summary.distributions.craft,rows:[{key:'triangle',count:2}]}}};
assert.match((await ask({type:'inspectAnalysisSessionEvidence',section:'craft',domainKey:'craft',rowKey:'triangle',groups:{A:mismatched,B:mismatched}})).error,/differs from the held summary/);
console.log('A/B inspection integration: all available core bins and unknowns reconcile, exact IDs paginate, coverage reconciles, stale/unavailable fields reject.');
