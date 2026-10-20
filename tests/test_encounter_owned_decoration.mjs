import assert from "node:assert/strict";
import fs from "node:fs";
import zlib from "node:zlib";
import vm from "node:vm";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url), api = require("../encounter_evidence.js");
const manifest = JSON.parse(fs.readFileSync("data/encounters/manifest.json", "utf8"));
const payload = JSON.parse(zlib.gunzipSync(fs.readFileSync("data/encounters/evidence.json.gz")));
const originPayload = JSON.parse(zlib.gunzipSync(fs.readFileSync("data/encounters/label_origins.json.gz")));
const index = api.createIndex(payload, manifest.attributeReviews, manifest.artifact.decodedSha256);
const origins = api.createLabelOriginsIndex(originPayload, index, manifest.artifact.decodedSha256);
assert.equal(index.rowCount, 16319);

const keys = ["encounterAbductionCode", "encounterBeingMask", "encounterSourceBeingMask", "encounterNarrativeBeingMask",
  "encounterEvidenceProvenanceReady", "encounterCraftAssociationCode", "encounterHeightFeet", "encounterUniform",
  "encounterEvidenceReady", "encounterIdentityMismatch"];
let heightCount = 0, withheldCount = 0;
for (const row of payload.rows) {
  const record = index.get(row.eventId), origin = origins.get(row.eventId);
  const raw = { event_id: Number(row.eventId), source: row.source, location_raw: "Retained locality",
    type: "Retained source classification", lat: null, lon: null, raw_source_row: { field: "retained" } };
  const original = structuredClone(raw), owned = { ...raw };
  assert.equal(api.decorateInPlace(owned, index, origins), owned, "Owned decoration allocates no replacement catalog record");
  const pure = api.decorate(raw, index, origins);
  assert.notEqual(pure, raw, "The public pure decorator still returns an independent record");
  assert.deepEqual(raw, original, "Pure decoration never mutates source records");
  assert.equal(pure.raw_source_row, raw.raw_source_row, "Existing shallow-copy contract is retained");
  assert.deepEqual(owned, pure);
  assert.deepEqual(Object.keys(owned).filter(key => key.startsWith("encounter")), keys);
  assert.equal(owned.encounterAbductionCode, api.ABDUCTION_CODES[row.abductionStatus]);
  assert.equal(owned.encounterBeingMask, api.beingMask(row.beingTypes));
  assert.equal(owned.encounterSourceBeingMask, origin.sourceBeingMask);
  assert.equal(owned.encounterNarrativeBeingMask, origin.narrativeBeingMask);
  assert.equal(owned.encounterCraftAssociationCode, api.ASSOCIATION_CODES[row.craftAssociation]);
  assert.equal(owned.encounterEvidenceReady, true);
  assert.equal(owned.encounterEvidenceProvenanceReady, true);
  assert.equal(owned.encounterIdentityMismatch, false);
  assert.equal(owned.encounterHeightFeet, record.heightFeet ?? null);
  assert.equal(owned.encounterUniform, record.uniform == null ? null : typeof record.uniform === "boolean"
    ? record.uniform ? "Reported" : "Not reported in source field" : record.uniform);
  if (owned.encounterHeightFeet !== null) heightCount += 1;
  if (record.measurementReview) {
    withheldCount += 1;
    assert.equal(owned.encounterHeightFeet, null, "Disputed measurements stay outside Analysis height comparisons");
    assert.equal(record.reportedHeightFeet, row.heightFeet, "The disputed original stays inspectable");
  }
  const mismatched = api.decorateInPlace({ ...raw, source: "unrelated_collection" }, index, origins);
  assert.equal(mismatched.encounterEvidenceReady, false);
  assert.equal(mismatched.encounterEvidenceProvenanceReady, false);
  assert.equal(mismatched.encounterIdentityMismatch, true);
  for (const key of ["encounterAbductionCode", "encounterBeingMask", "encounterSourceBeingMask", "encounterNarrativeBeingMask", "encounterCraftAssociationCode"]) assert.equal(mismatched[key], 0);
  assert.equal(mismatched.encounterHeightFeet, null);
  assert.equal(mismatched.encounterUniform, null);
}
assert.equal(withheldCount, 5);
assert.equal(heightCount, 2436);

// An unindexed report is known not to have an indexed classification only when
// its evidence index is ready; unavailable evidence must retain unknown status.
const unknown = { event_id: 1, source: "nuforc", lat: null, lon: null };
assert.equal(index.has(unknown.event_id), false);
for (const [evidenceIndex, originIndex, ready, provenance] of [
  [index, origins, true, true], [index, null, true, false], [null, null, false, false],
]) {
  const owned = { ...unknown }, pure = api.decorate(unknown, evidenceIndex, originIndex);
  assert.equal(api.decorateInPlace(owned, evidenceIndex, originIndex), owned);
  assert.deepEqual(owned, pure);
  assert.deepEqual(Object.fromEntries(keys.map(key => [key, owned[key]])), {
    encounterAbductionCode: 0, encounterBeingMask: 0, encounterSourceBeingMask: 0, encounterNarrativeBeingMask: 0,
    encounterEvidenceProvenanceReady: provenance, encounterCraftAssociationCode: 0, encounterHeightFeet: null,
    encounterUniform: null, encounterEvidenceReady: ready, encounterIdentityMismatch: false,
  });
}
for (const value of [null, undefined, false, 0, "report"]) {
  assert.equal(api.decorate(value, index, origins), value);
  assert.equal(api.decorateInPlace(value, index, origins), value);
}
const first = payload.rows[0];
assert.deepEqual(api.decorateInPlace({ eventId: first.eventId, source: first.source }, index, origins),
  api.decorate({ eventId: first.eventId, source: first.source }, index, origins), "Alternate eventId input remains supported");

// Exercise the actual hydration call site: only a fresh compact canonical
// summary belongs to this path. Legacy/borrowed records retain pure decoration.
const app = fs.readFileSync("app.js", "utf8");
const hydrateStart = app.indexOf("  function hydrateCatalogEvent(");
const hydrateEnd = app.indexOf("  function ingestCatalogShard(", hydrateStart);
assert.ok(hydrateStart >= 0 && hydrateEnd > hydrateStart);
for (const [ownsCompact, helperPresent] of [[true, true], [false, true], [true, false]]) {
  let ownedCalls = 0, pureCalls = 0, compact;
  const original = Object.freeze({ event_id: Number(first.eventId), source: first.source,
    date_precision: "exact_day", sort_date_iso: "1954-10-01", has_coordinates: false,
    visual_type_group: "disc_saucer", location_precision: "unknown", lat: null, lon: null });
  const hooks = {
    decorate(...args) { pureCalls += 1; return api.decorate(...args); },
    ...(helperPresent ? { decorateInPlace(...args) { ownedCalls += 1; return api.decorateInPlace(...args); } } : {}),
  };
  const context = vm.createContext({ ENCOUNTERS: hooks, runtime: { encounterEvidence: index, encounterLabelOrigins: origins,
    traceChronologyEvidence: { exclusion: () => false } },
    applyLocationLabelOverlay: event => event, applyMufonDateReview: event => event,
    compactCanonicalSummaryEventForRuntime: event => { compact = ownsCompact ? { ...event } : event; return compact; },
    isoToOrdinal: () => 42, getVisualTypeGroup: () => "disc_saucer", finiteChronologyNumber: Number,
  });
  vm.runInContext(app.slice(hydrateStart, hydrateEnd), context);
  const hydrated = context.hydrateCatalogEvent(original);
  assert.equal(ownedCalls, ownsCompact && helperPresent ? 1 : 0);
  assert.equal(pureCalls, ownsCompact && helperPresent ? 0 : 1);
  assert.equal(hydrated === compact, ownsCompact && helperPresent, "Owned fast path retains the fresh compact object");
  assert.equal(original.encounterEvidenceReady, undefined, "Borrowed/source input is never annotated in place");
  assert.equal(hydrated.encounterEvidenceReady, true);
  assert.equal(hydrated.encounterBeingMask, index.get(first.eventId).encounterBeingMask);
  assert.equal(hydrated.encounterOccurrenceDateExcluded, false);
}

// Time the same owned compact objects with and without the extra full-record
// copy. Timing is reported, not used as a machine-dependent pass threshold.
const prototype = { ...unknown, chunk_id: "chunk_000001", detail_index: 0, date_raw: "1954-10-01",
  sort_date_iso: "1954-10-01", date_precision: "exact_day", time_raw: "", time_display: "",
  playback_sort_key: [1954, 10, 1], location_raw: "Retained locality", location_display: "Retained locality",
  type: "Disk", coordinate_source: "unresolved", location_precision: "unknown", has_coordinates: false,
  shape_normalized: "disk", visual_type_group: "disc_saucer", craft_type_inferred: "disc_saucer",
  craft_type_confidence: "source", craft_type_source: "source", same_day_match_strength: "none",
  country: "unknown", state_province: "unknown", duplicate_lineage_id: "", sort_ordinal: 0 };
const sampleCount = 100000;
let checksum = 0;
function measure(decorator) {
  const started = performance.now();
  for (let n = 0; n < sampleCount; n += 1) {
    const result = decorator({ ...prototype, event_id: n % 2 ? Number(first.eventId) : 1,
      source: n % 2 ? first.source : "nuforc" }, index, origins);
    checksum += result.encounterBeingMask;
  }
  return performance.now() - started;
}
measure(api.decorate); measure(api.decorateInPlace);
const copiedMs = measure(api.decorate), ownedMs = measure(api.decorateInPlace);
assert.ok(Number.isFinite(checksum));
console.log(JSON.stringify({ check: "Owned encounter decoration matches all 16,319 indexed reports, unindexed/unknown/mismatched records and five measurement holds",
  indexed: index.rowCount, usableHeights: heightCount, heldHeights: withheldCount,
  benchmark: { sampleCount, copiedMs: Math.round(copiedMs), ownedMs: Math.round(ownedMs),
    eliminatedReplacementRecords: sampleCount } }));
