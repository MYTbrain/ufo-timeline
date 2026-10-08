import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { gunzipSync } from "node:zlib";

const source=fs.readFileSync("animal_mutilation_layer.js","utf8");
function functionSource(name){
  const start=source.indexOf("  function "+name+"(");
  const end=source.indexOf("\n  function ",start+3);
  assert.ok(start>=0&&end>start);return source.slice(start,end);
}
let focusCount=0;
const panel={hidden:true,attributes:new Map(),setAttribute(name,value){this.attributes.set(name,value);}};
const body={innerHTML:""};
const context=vm.createContext({console,URL,Map,detailPanel:panel,detailBody:body,detailClose:{focus(){focusCount+=1;}},ROW:{id:0}});
for(const name of ["escapeHtml","safePublicHttpUrl","readableCode","formatDate","formatLocation",
  "reviewPresentation","coordinateEvidenceLabel","uncertaintyLabel","listLabel","identifierListLabel",
  "sourceReferenceHtml","publicEvidenceValue","acceptedFieldProvenanceHtml","renderDetail"]){
  vm.runInContext(functionSource(name),context);
}
const summary="A contemporary source described the animal report; its cause remains a source assessment.";
const record={id:"animal_mutilation:ami_fixture",title:"Reviewed case",reviewState:"source_reviewed",status:"source_reviewed",
  summary,dateStart:"1975-02-27",dateEnd:"1975-02-27",datePrecision:"exact_day",dateRole:"publication_date",
  coordinates:null,sourceIncidentId:"ptx:fixture",sourceIncidentSha256:null,analysisTier:"excluded",
  traceEligible:false,causality:"not_asserted",evidenceExcerptKind:"reviewed_field_paraphrase",
  evidenceExcerpts:["Reviewed field summary (paraphrase): "+summary],
  sourceRefs:[{sourceId:"src_fixture",title:"Newspaper & archived issue",url:"https://texashistory.unt.edu/ark:/67531/test/",
    locator:"page 1",sourceHash:"a".repeat(64),hashRole:"frozen_source_capture"}],
  fieldProvenance:{publication_date:{value:"1975-02-27",reviewState:"source_reviewed",assertionIds:["cea_fixture"],
    evidenceSha256:["a".repeat(64)],sourceIds:["src_fixture"],sourceLocators:[{sourceId:"src_fixture",locator:"publication header"}]}}};
const before=JSON.stringify(record);
context.renderDetail(record,[]);
assert.equal(JSON.stringify(record),before,"Presentation must preserve the original scientific state and identifiers");
assert.match(body.innerHTML,/<h4>Reviewed source summary<\/h4>/);
assert.doesNotMatch(body.innerHTML,/<h4>Public report excerpts<\/h4>/);
assert.equal(body.innerHTML.split(summary).length-1,1,"The public summary must not repeat as an excerpt");
assert.match(body.innerHTML,/Newspaper &amp; archived issue<\/a>/);
assert.match(body.innerHTML,/Source capture SHA-256/);
assert.match(body.innerHTML,/<details class="animal-field-provenance"><summary>Reviewed field evidence · 1 field<\/summary>/);
assert.match(body.innerHTML,/Publication Date/);assert.match(body.innerHTML,/publication header/);
assert.match(body.innerHTML,/Evidence identifiers/);assert.match(body.innerHTML,/cea_fixture/);
assert.match(body.innerHTML,/Source incident SHA-256<\/dt><dd><code class="animal-hash">Not supplied/);
assert.equal(panel.hidden,false);assert.equal(panel.attributes.get("aria-hidden"),"false");assert.equal(focusCount,1);

context.renderDetail({...record,evidenceExcerptKind:undefined,evidenceExcerpts:["Original legacy public excerpt."],sourceRefs:[{sourceId:"old-id",sourceHash:"b".repeat(64)}],fieldProvenance:undefined},[]);
assert.match(body.innerHTML,/<h4>Public report excerpts<\/h4>/);assert.match(body.innerHTML,/Original legacy public excerpt/);
assert.match(body.innerHTML,/old-id/);assert.match(body.innerHTML,/Source SHA-256/);
assert.doesNotMatch(body.innerHTML,/animal-field-provenance/);

const unsafe={...record,sourceRefs:[{sourceId:"src_bad",title:"<script>source</script>",url:"javascript:alert(1)",sourceHash:"<bad>"}],
  fieldProvenance:{public_title:{value:"<img src=x onerror=alert(1)>",reviewState:"source_reviewed",assertionIds:["<identifier>"],
    evidenceSha256:["<hash>"],sourceLocators:[{sourceId:"src_bad",locator:"<script>locator</script>"}]}}};
context.renderDetail(unsafe,[]);
assert.doesNotMatch(body.innerHTML,/<script>|<img|href="javascript:/);
assert.match(body.innerHTML,/&lt;script&gt;source/);assert.match(body.innerHTML,/&lt;img src=x onerror=alert\(1\)&gt;/);
assert.match(body.innerHTML,/&lt;identifier&gt;/);assert.match(body.innerHTML,/&lt;script&gt;locator/);

if(process.argv[2]){
  const root=path.resolve(process.argv[2]);
  const receipt=JSON.parse(fs.readFileSync(path.join(root,"validation.json")));
  const manifest=JSON.parse(fs.readFileSync(path.join(root,"animal_mutilations/manifest.json")));
  const ids=new Set(receipt.changedAnimalCaseIds);
  let renderedCases=0;
  for(const declaration of manifest.details.files){
    const chunk=path.join(root,"animal_mutilations",declaration.path);
    if(!fs.existsSync(chunk))continue;
    const records=JSON.parse(gunzipSync(fs.readFileSync(chunk)));
    for(const detail of Object.values(records))if(ids.has(detail.id)){
      const immutable=JSON.stringify(detail);context.renderDetail(detail,[]);
      assert.equal(JSON.stringify(detail),immutable);
      assert.match(body.innerHTML,/<h4>Reviewed source summary<\/h4>/);
      assert.match(body.innerHTML,/Source capture SHA-256/);
      assert.match(body.innerHTML,/Reviewed field evidence/);
      assert.doesNotMatch(body.innerHTML,/Reviewed field summary \(paraphrase\):/);
      assert.doesNotMatch(body.innerHTML,/Public report excerpts|No public source link was supplied/);
      assert.ok(detail.sourceRefs.every(ref=>body.innerHTML.includes(context.escapeHtml(ref.title))));
      renderedCases+=1;
    }
  }
  assert.equal(renderedCases,7,"Every repaired animal detail card must render its reviewed source evidence");
}
console.log("Animal reviewed-source headings, duplicate suppression, field provenance, capture hash roles, legacy compatibility and escaped output assertions passed");
