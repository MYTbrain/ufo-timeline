import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { createRequire } from "node:module";
import { createHash, webcrypto } from "node:crypto";
import { gzipSync } from "node:zlib";

const require = createRequire(import.meta.url);
const evidence = require("../encounter_evidence.js");
const hash = (bytes) => createHash("sha256").update(bytes).digest("hex");
const fixtureRow = (eventId = "1", fields = {}) => ({
  eventId, source: "fixture", sourceEventId: "native-" + eventId,
  abductionStatus: "source_reported", beingTypes: ["grey", "small_humanoid"], craftAssociation: "explicit",
  evidence: [{ field: "description", excerpt: "Witness reported being taken into a craft by a small humanoid.", ruleId: "own_incident_explicit" }],
  sourceRef: { chunk: "chunk_000001.json.gz", detailIndex: 3, chunkSha256: "a".repeat(64) }, ...fields,
});
const fixture = () => ({ schemaId: evidence.SCHEMA_ID, releaseId: evidence.RELEASE_ID,
  catalogCount: evidence.CATALOG_COUNT, taxonomy: evidence.TAXONOMY.map(({ key, label, group }) => ({ key, label, group })),
  rows: [fixtureRow(), fixtureRow("2", { abductionStatus: "narrative_reported", beingTypes: ["nordic"], craftAssociation: "co_reported" }),
    fixtureRow("3", { abductionStatus: "ambiguous", beingTypes: [], craftAssociation: "not_established" }),
    fixtureRow("4", { abductionStatus: "", beingTypes: ["unspecified"], craftAssociation: "none_reported", heightFeet: 3.5, uniform: "silver", reviewFlags: ["Source type retained"] })] });
const payload = fixture();
const index = evidence.createIndex(payload);
assert.equal(index.ready, true);
assert.equal(index.rowCount, 4);
assert.equal(index.get(1).encounterAbductionCode, 1);
assert.equal(index.get("2").encounterCraftAssociationCode, 2);
assert.equal(index.get("4").encounterBeingMask, 1 << 18);
assert.equal(index.get("5"), null);
assert.equal(index.get("01"), null);
assert.equal(index.get(Number.MAX_SAFE_INTEGER + 1), null);
assert.ok(Object.isFrozen(index.get("1")) && Object.isFrozen(index.get("1").evidence[0]));

// Retained evidence cannot be changed by the builder after installation or by consumers.
payload.rows[0].evidence[0].excerpt = "mutated";
payload.rows[0].beingTypes.push("reptilian");
assert.match(index.get("1").evidence[0].excerpt, /Witness reported/);
assert.deepEqual(index.get("1").beingTypes, ["grey", "small_humanoid"]);
const snapshot = index.snapshot();
snapshot.beingTypeCounts.grey = 999;
snapshot.taxonomy[0].label = "mutated";
assert.equal(index.snapshot().beingTypeCounts.grey, 1);
assert.equal(index.taxonomy[0].label, "Grey");
assert.equal(index.snapshot().abductionReportedCount, 2);
assert.equal(index.snapshot().ambiguousAbductionCount, 1);
assert.equal(index.snapshot().beingReportCount, 3);
assert.equal(index.snapshot().notIndexedCount, 702889);

const original = { event_id: 1, type: "Disk", craft_type_inferred: "disc_saucer", raw_source_row: { description: "untouched" } };
const annotated = evidence.decorate(original, index);
assert.notEqual(annotated, original);
assert.equal(original.encounterBeingMask, undefined);
assert.equal(annotated.type, "Disk");
assert.equal(annotated.craft_type_inferred, "disc_saucer");
assert.equal(annotated.raw_source_row, original.raw_source_row);
assert.equal(evidence.decorate({ event_id: "5" }, index).encounterAbductionCode, 0);
assert.equal(evidence.decorate({ event_id: "5" }, index).encounterEvidenceReady, true);
const staleSource = evidence.decorate({ event_id: 1, source: "another_collection" }, index);
assert.equal(staleSource.encounterIdentityMismatch, true);
assert.equal(staleSource.encounterEvidenceReady, false);
assert.equal(staleSource.encounterBeingMask, 0);
assert.equal(evidence.matches(staleSource, { abduction: "reported" }), false);
assert.equal(evidence.matches(staleSource, { abduction: "not_indexed" }), false);
assert.equal(evidence.matches(staleSource, {}), true);
assert.equal(evidence.renderBadges(staleSource, index), "");
assert.equal(evidence.renderEvidence(staleSource, index), "");
assert.equal(evidence.decorate({ event_id: 1, source: "fixture" }, index).encounterIdentityMismatch, false);

assert.deepEqual(evidence.beingTypes(evidence.beingMask(["grey", "unspecified", "mantis_like"])), ["grey", "mantis_like", "unspecified"]);
assert.equal(evidence.beingMask(evidence.TAXONOMY.map((row) => row.key)), 524287);
assert.throws(() => evidence.beingMask(["unknown"]), /being type/);
assert.throws(() => evidence.beingMask(["grey", "grey"]), /being type/);
assert.throws(() => evidence.beingTypes(1 << 25), /mask/);

// OR within selected being types, AND between the independent encounter facets.
assert.equal(evidence.matches(annotated, { abduction: "reported", beingTypes: ["nordic", "grey"] }), true);
assert.equal(evidence.matches(annotated, { abduction: "reported", beingTypes: ["nordic"] }), false);
assert.equal(evidence.matches(annotated, { abduction: "source_reported", being: "reported" }), true);
assert.equal(evidence.matches(index.get("2"), { abduction: "source_reported" }), false);
assert.equal(evidence.matches(index.get("2"), { abduction: "reported" }), true);
assert.equal(evidence.matches(index.get("3"), { abduction: "reported" }), false);
assert.equal(evidence.matches(index.get("3"), { abduction: "ambiguous", being: "not_indexed" }), true);
assert.equal(evidence.matches(index.get("4"), { abduction: "not_indexed", being: "reported" }), true);
assert.equal(evidence.matches(evidence.decorate({ event_id: "5" }, index), { abduction: "not_indexed", being: "not_indexed" }), true);
assert.equal(evidence.matches(annotated, { being: "not_indexed", beingTypes: ["grey"] }), false);
assert.equal(evidence.matches(annotated, { abduction: "misspelled" }), false);
assert.equal(evidence.matches(annotated, { beingTypes: ["unregistered"] }), false);
assert.equal(evidence.matches({ encounterEvidenceReady: true, encounterAbductionCode: 1, encounterBeingMask: -1 }, { being: "reported" }), false);

// Unavailable evidence is not an empty valid index, including the not-indexed option.
const unavailable = evidence.decorate(annotated, null);
assert.equal(unavailable.encounterEvidenceReady, false);
assert.equal(evidence.matches(unavailable, {}), true);
assert.equal(evidence.matches(unavailable, { abduction: "reported" }), false);
assert.equal(evidence.matches(unavailable, { abduction: "not_indexed" }), false);
assert.equal(evidence.matches(null, { being: "not_indexed" }), false);
assert.equal(evidence.matches(null, {}), true);
const unusedTypes = [];
unusedTypes.forEach = () => { throw new Error("Inactive facets must not iterate the taxonomy or selected types"); };
assert.equal(evidence.matches(null, { abduction: "any", being: "any", beingTypes: unusedTypes }), true);
assert.equal(evidence.matches(null, { abduction: "unknown_filter", being: "any", beingTypes: unusedTypes }), false);

for (const mutate of [
  (p) => { p.schemaId = "wrong"; }, (p) => { p.releaseId = "wrong"; }, (p) => { p.catalogCount = 1; },
  (p) => { p.taxonomy.pop(); }, (p) => { p.taxonomy[0].key = "unknown"; }, (p) => { p.taxonomy.reverse(); },
  (p) => { p.rows.push(fixtureRow()); }, (p) => { p.rows[0].eventId = 1; }, (p) => { p.rows[0].eventId = "01"; },
  (p) => { p.rows[0].eventId = "9007199254740992"; }, (p) => { p.rows[0].beingTypes = ["species_claim"]; },
  (p) => { p.rows[0].source = ""; }, (p) => { delete p.rows[0].sourceEventId; }, (p) => { p.rows[0].evidence = []; },
  (p) => { p.rows[0].evidence[0].excerpt = ""; }, (p) => { p.rows[0].evidence[0].ruleId = ""; },
  (p) => { p.rows[0].abductionStatus = "confirmed"; }, (p) => { p.rows[0].craftAssociation = "flight_path"; },
  (p) => { p.rows[0].sourceRef.chunk = "../../private.json"; }, (p) => { p.rows[0].sourceRef.detailIndex = -1; },
  (p) => { p.rows[0].sourceRef.detailIndex = 0.5; }, (p) => { p.rows[0].sourceRef.chunkSha256 = "invalid"; },
  (p) => { p.rows[0].heightFeet = Infinity; }, (p) => { p.rows[0].uniform = {}; }, (p) => { p.rows[0].reviewFlags = [""]; },
  (p) => { p.rowCount = p.rows.length + 1; },
]) {
  const invalid = fixture(); mutate(invalid);
  assert.throws(() => evidence.createIndex(invalid), /Encounter evidence refused/);
}

// All source-derived strings are escaped, never evaluated or used as markup/URLs.
const malicious = fixture();
malicious.taxonomy[0].label = '<img src=x onerror="bad()">';
malicious.rows[0].source = '<script>source()</script>';
malicious.rows[0].sourceEventId = '<b>native</b>';
malicious.rows[0].evidence[0] = { field: '<svg onload="bad()">', excerpt: "<script>bad()</script> & 'quoted'", ruleId: '<img src=x>' };
malicious.rows[0].uniform = '<a href="javascript:bad()">silver</a>';
malicious.rows[0].reviewFlags = ['<input autofocus onfocus="bad()">'];
const unsafeIndex = evidence.createIndex(malicious);
const markup = evidence.renderEvidence(1, unsafeIndex) + evidence.renderBadges(1, unsafeIndex);
assert.ok(!markup.includes("<script>") && !markup.includes("<img ") && !markup.includes("<svg ") && !markup.includes('<a href="javascript:'));
assert.ok(markup.includes("&lt;script&gt;") && markup.includes("&lt;img") && markup.includes("&#39;quoted&#39;"));
for (const item of ["Original chunk SHA-256", "chunk_000001.json.gz", "own_incident_explicit", "Source event ID"]) {
  assert.ok(evidence.renderEvidence(1, index).includes(item));
}
assert.match(evidence.renderEvidence(1, index), /^<section class="detail-block encounter-evidence">/);
assert.equal(evidence.renderEvidence({ event_id: "5" }, index), "");
assert.equal(evidence.renderBadges({ event_id: "5" }, index), "");

// Both browser spellings refer to the same immutable API, without a Node module.
const browser = vm.createContext({});
vm.runInContext(fs.readFileSync(new URL("../encounter_evidence.js", import.meta.url), "utf8"), browser);
assert.equal(browser.UFOEncounterEvidence, browser.UfoEncounterEvidence);
assert.equal(browser.UFOEncounterEvidence.SCHEMA_ID, evidence.SCHEMA_ID);

if (!globalThis.crypto) globalThis.crypto = webcrypto;
const decoded = Buffer.from(JSON.stringify(fixture()));
const compressed = gzipSync(decoded);
const pins = { gzipSha256: hash(compressed), sha256: hash(decoded), gzipBytes: compressed.length, bytes: decoded.length, rowCount: 4 };
assert.equal((await evidence.decodeEvidenceResponse(new Response(compressed), pins)).rows.length, 4);
assert.equal((await evidence.decodeEvidenceResponse(new Response(decoded), pins)).rows.length, 4, "already decompressed response must not be decoded twice");
await assert.rejects(evidence.decodeEvidenceResponse(new Response(compressed), { ...pins, gzipSha256: "0".repeat(64) }), /hash mismatch/);
await assert.rejects(evidence.decodeEvidenceResponse(new Response(decoded), { ...pins, sha256: "0".repeat(64) }), /hash mismatch/);
await assert.rejects(evidence.decodeEvidenceResponse(new Response(decoded), { ...pins, rowCount: 5 }), /row count/);
await assert.rejects(evidence.decodeEvidenceResponse(new Response(decoded), {}), /integrity pin/);
await assert.rejects(evidence.decodeEvidenceResponse(new Response("no", { status: 404 }), pins), /response failed/);
console.log("Encounter evidence validation, filter semantics, provenance, escaping, and delivery tests passed.");
