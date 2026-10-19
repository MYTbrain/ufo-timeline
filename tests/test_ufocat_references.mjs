import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import {createHash} from "node:crypto";
import {gunzipSync} from "node:zlib";
import {createRequire} from "node:module";
import {fileURLToPath} from "node:url";
import {spawnSync} from "node:child_process";
const require = createRequire(import.meta.url), References = require("../ufocat_references.js");
const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const fixtures = JSON.parse(fs.readFileSync(path.join(root, "tests/fixtures/ufocat_references.json"), "utf8"));
for (const fixture of fixtures) {
  const before = JSON.stringify(fixture.event), entries = References.referenceEntries(fixture.event);
  assert.deepEqual(entries.filter(entry => entry.sourceCode).map(entry => entry.sourceCode), fixture.expectedCodes, fixture.name);
  assert.deepEqual(References.references(fixture.event), entries.map(entry => entry.text));
  assert.equal(JSON.stringify(fixture.event), before, "Citation display never mutates report data");
}
const direct = References.referenceEntries(fixtures[0].event)[0], indirect = References.referenceEntries(fixtures[1].event)[1];
assert.equal(direct.catalogCaseNumber, 293);
assert.equal(direct.locatorType, "catalog_case_number");
assert.equal(indirect.catalogCaseNumber, null);
assert.equal(indirect.locatorRaw, "079");
assert.equal(indirect.locatorType, "ambiguous_catalog_case_number_or_printed_page");
assert.equal(direct.url, "https://cufos.org/PDFs/books/Physical_Traces.pdf");
assert.equal(References.referenceEntries(fixtures[3].event)[0].url, undefined);
assert.equal(References.referenceEntries(fixtures[7].event)[0].flags[0], "missing_or_invalid_catalog_case_number");
const reexported = {...fixtures[0].event, references: References.references(fixtures[0].event)};
assert.deepEqual(References.referenceEntries(reexported), References.referenceEntries(fixtures[0].event), "Re-export does not lose typed source links or duplicate strings");
// Real Majestic-primary Huey event whose Phillips citation survives only in a
// merged UFOCAT source member, not in the primary event's raw fields.
const member = {source_name:"ufocat", source_file:"ufocat2023.csv", source_native_id:"64419", source_row_number:21,
  source_row_hash:"c1f91dc24b122570bade1ffe31fa3cfd30ca8a22", canonical_input_id:"cin_e0a87523012682f7306acbcd",
  raw_fields:{SOURCE:"TPhillips", PAGEVOL:"290"}};
const merged = {event_id:889027367562998, canonical_event_id:"evt_04b9763b9f6e02939a8ca22d", source:"majestic",
  canonical_input_ids:[member.canonical_input_id], source_provenance:[{...member,raw_fields:undefined}],
  raw_fields:{SOURCE:"TPhillips3", PAGEVOL:"unrelated primary fields"}};
const payload = {schemaId:"ufo-timeline-phillips-detail-citations-v1", counts:{eventN:1,sourceRecordN:1},
  events:{[merged.event_id]:{eventId:merged.event_id,canonicalEventId:merged.canonical_event_id,sourceRecords:[member]}}};
const index = References.createIndex(payload), snapshot = JSON.stringify(merged);
assert.equal(index.eventN, 1);
assert.equal(References.referenceEntries(merged).length, 0, "Merged provenance without owned raw fields is insufficient");
const enriched = References.withIndexedCitations(merged,index);
assert.notEqual(enriched, merged);
assert.equal(JSON.stringify(merged), snapshot, "The original event and primary raw fields stay unchanged");
assert.equal(enriched.raw_fields, merged.raw_fields);
assert.deepEqual(References.referenceEntries(enriched).map(entry => entry.sourceCode), ["TPhillips"]);
assert.equal(References.withIndexedCitations(enriched,index), enriched, "Member attachment is idempotent");
for (const change of [{event_id:123}, {event_id:"889027367562998.0"}, {event_id:Number.MAX_SAFE_INTEGER+1},
  {canonical_event_id:"evt_ffffffffffffffffffffffff"}, {canonical_input_ids:[]}, {source_provenance:[]},
  {source_provenance:[{...member,source_row_hash:"f".repeat(40)}]},
  {source_provenance:[{...member,canonical_input_id:"cin_ffffffffffffffffffffffff"}]},
  {source_provenance:[{...member,source_name:"nuforc"}]}]) {
  const changed = {...merged,...change};
  assert.equal(References.withIndexedCitations(changed,index),changed,"Unknown or mismatched identities fail closed");
}
assert.equal(References.withIndexedCitations(merged,{...index}),merged,"Only fully validated index objects are accepted");
for (const mutate of [p=>p.counts.eventN=2, p=>p.counts.sourceRecordN=2,
  p=>p.events[merged.event_id].sourceRecords.push(member),
  p=>p.events[merged.event_id].sourceRecords[0].source_row_hash="not-a-hash",
  p=>p.events[merged.event_id].sourceRecords[0].raw_fields.description="Never import narrative",
  p=>p.events[merged.event_id].sourceRecords[0].raw_fields={SOURCE:"TPhillips10"}]) {
  const invalid = JSON.parse(JSON.stringify(payload)); mutate(invalid);
  assert.throws(()=>References.createIndex(invalid), /Invalid Phillips citation index/);
}
const manifest = JSON.parse(fs.readFileSync(path.join(root,"data/source_citations/manifest.json"),"utf8"));
const compressed = fs.readFileSync(path.join(root,"data/source_citations",manifest.artifact.file));
const decoded = gunzipSync(compressed);
assert.equal(compressed.length,manifest.artifact.gzipBytes);
assert.equal(createHash("sha256").update(compressed).digest("hex"),manifest.artifact.gzipSha256);
assert.equal(decoded.length,manifest.artifact.decodedBytes);
assert.equal(createHash("sha256").update(decoded).digest("hex"),manifest.artifact.decodedSha256);
const fullPayload = JSON.parse(decoded), fullIndex = References.createIndex(fullPayload,manifest);
assert.equal(fullIndex.eventN,1953);
assert.equal(fullIndex.sourceRecordN,2882);
assert.equal(References.referenceEntries(References.withIndexedCitations(merged,fullIndex))[0].sourceCode,"TPhillips");
assert.throws(()=>References.createIndex(fullPayload,{...manifest,counts:{...manifest.counts,eventN:1954}}), /Invalid Phillips citation index/);
assert.throws(()=>References.createIndex(fullPayload,{...manifest,inputPins:{...manifest.inputPins,sourceIndex:{sha256:"f".repeat(64)}}}), /Invalid Phillips citation index/);
const browser = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(root, "ufocat_references.js"), "utf8"), browser);
assert.deepEqual(JSON.parse(JSON.stringify(browser.UfoUfocatReferences.referenceEntries(fixtures[0].event))), References.referenceEntries(fixtures[0].event));
const python = process.env.UFO_TEST_PYTHON || process.env.PYTHON || (process.platform === "win32" ? "python" : "python3");
const parity = spawnSync(python, ["-c", "import json,sys; from parser.ufocat_references import reference_entries; print(json.dumps([reference_entries(x['event']) for x in json.load(sys.stdin)]))"],
  {cwd: root, input: JSON.stringify(fixtures), encoding:"utf8"});
assert.equal(parity.status, 0, parity.stderr || "Python parity process did not finish");
assert.deepEqual(JSON.parse(parity.stdout), fixtures.map(fixture => References.referenceEntries(fixture.event)), "Python export and browser display agree on provenance and locator semantics");
console.log("UFOCAT references: ownership, direct/indirect locators, unknowns, browser export, and Python parity passed");
