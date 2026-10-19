import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url), Inspect = require("../analysis_session_inspection.js"), Context = require("../analysis_session_context.js"), Comparisons = require("../analysis_session_comparisons.js"), Planetary = require("../analysis_planetary.js");
const day = iso => Date.parse(iso + "T00:00:00Z") / 86400000, date = day("2024-04-08"), other = day("2024-04-24");
const report = (id, ordinal = date, extra = {}) => ({ eventId: id, startOrdinal: ordinal, endOrdinal: ordinal, sortOrdinal: ordinal, datePrecision: "exact_day", craftType: "disc_saucer", coordinateSource: "source_exact", coordinateEvidenceClass: "source_exact", craftConfidence: "high", lat: 36, lon: -80, source: "fixture", country: "United States", ...extra });
const group = (rows, first = date, last = date) => ({ cohort: { eventIds: rows.map(row => row.eventId), reportCount: rows.length, scope: { timeRange: { mode: "window", startOrdinal: first, endOrdinal: last } } }, rows });
const verified = report("a1", date, { utcTimestamp: "2024-04-08T18:00:00Z", utcTimestampVerified: true, timeZoneProvenance: "source UTC fixture", sourceUrl: "https://example.org/report" });
const groups = { A: group([verified, report("a2", date, { datePrecision: "year", coordinateSource: "unknown", craftConfidence: "unknown", sourceUrl: "javascript:alert(1)" }),
  report("a3", date, { encounterOccurrenceDateExcluded: true }), report("a4", date, { isContext: true })]), B: group([report("a1"), report("b1", other, { lat: -30, lon: 100 })], date, other) };
const context = { crops: [
  { id: "crop1", startOrdinal: date, endOrdinal: date, datePrecision: "exact_day", dateRole: "catalog_date", country: "France", morphology: ["disc", "ring", "ring"], classification: "geometric", strictEligible: false, sourceFamilyIds: ["family1", "family2"], sourceUrl: "https://example.org/crop1" },
  { id: "crop2", startOrdinal: date, endOrdinal: other, datePrecision: "range", morphology: ["ring"], strictEligible: true },
  { id: "crop3", startOrdinal: other, endOrdinal: other, datePrecision: "exact_day", country: "Belgium" },
], animals: [{ id: "animal1", startOrdinal: date, endOrdinal: date, datePrecision: "exact_day", dateRole: "publication_date", species: ["bovine"], strictEligible: false }, { id: "animal2", startOrdinal: other, endOrdinal: other, datePrecision: "exact_day", species: ["equine", "bovine"] }] };
const pin = (id, lat, lon) => ({ eventId: id, lat, lon, ordinal: date + 719163, year: 2024, coordinateEvidence: "source_coordinates", craft: "disc_saucer" });
context.spatialPoints = [pin("a1", 36, -80), pin("a2", 36, -80.1), pin("b1", -30, 100)];
context.neighbors = [["a1", "a2", 1000, 0, true], ["a2", "a1", 1000, 0, true], ["a1", "b1", 5000, 2, null], ["a1", "missing", 1000, 0, true]];
context.facilities = [{ id: "active", name: "Active fixture", facilityClass: "military", lat: 36, lon: -80.05, coordinateConfidence: "high", temporalConfidence: "high", inferentialEligible: true, activeIntervals: [{ startYear: 2000, endYear: 2030 }] }];
context.relationships = [{ relationshipId: "r1", currentUfoEventId: "a1", relationshipType: "reported_nearby", reviewState: "needs_review", reconciliationStatus: "reconciled_current", associationEligible: false },
  { relationshipId: "r2", currentUfoEventId: "a2" }, { relationshipId: "unjoined", relationshipType: "reported_nearby" }];
context.contextNeighbors = [{ ufoEventId: "a1", contextId: "crop1", lane: "crop_locality", dateRole: "observed_catalog_date" }, { ufoEventId: "a1", contextId: "crop1", lane: "crop_locality", dateRole: "observed_catalog_date" },
  { ufoEventId: "a1", contextId: "crop2", lane: "crop_locality", dateRole: "matched_control_plus_1y" }, { ufoEventId: "a2", contextId: "animal1", lane: "animal_locality", dateRole: "observed_catalog_date", originUfoExcluded: true }];
const collectionReport = (id, extra = {}) => ({ eventId: id, canonicalJoinStatus: "validated_id_source_chunk_index", disposition: "direct_report", scope: "occupant_soil_plant", materials: ["soil"], actions: ["taking"], beingTypes: [], source: "fixture", sourceFamily: "family1", provisionalGroup: "provisional1", startOrdinal: date, endOrdinal: date, ...extra });
const collectionEvidence = { schemaId: "ufo-collection-evidence-v1", schemaVersion: 1, taxonomy: { materials: [{ key: "soil", label: "Soil" }], actions: [{ key: "taking", label: "Taking" }] },
  reports: [collectionReport("a1"), collectionReport("a2", { disposition: "ambiguous" }), collectionReport("a3", { canonicalPrimaryDiffers: true }), collectionReport("outside")], cases: [], policy: {} };
const descriptor = (dimension, key) => ({ key: dimension.key, label: dimension.label, unit: dimension.unit, a: dimension.a, b: dimension.b,
  row: { key, label: key, aCount: dimension.a.rows.find(row => row.key === key)?.count || 0, bCount: dimension.b.rows.find(row => row.key === key)?.count || 0 } });
let checked = 0;
function checkDimensions(input, aggregate) {
  for (const dimension of aggregate.dimensions) {
    const keys = new Set([...dimension.a.rows, ...dimension.b.rows].filter(row => row.count).map(row => row.key)); keys.add("__unknown__");
    // Include a zero cell where the renderer provides one, without running all
    // several hundred known-empty astronomical matrix cells unnecessarily.
    const zero = dimension.a.rows.find(row => !row.count && !dimension.b.rows.find(other => other.key === row.key)?.count); if (zero) keys.add(zero.key);
    for (const rowKey of keys) {
      const output = Inspect.inspect({ ...input, domainKey: dimension.key, rowKey, dimension: descriptor(dimension, rowKey), limit: 100 });
      assert.equal(output.unit, dimension.unit);
      for (const slot of ["A", "B"]) {
        const expected = dimension[slot.toLowerCase()], actual = output.groups[slot];
        assert.equal(actual.available, expected.available !== false, dimension.key + " availability " + slot);
        if (expected.available === false) { assert.equal(actual.matchedN, null); continue; }
        assert.equal(actual.totalN, expected.totalN, dimension.key + " denominator " + slot);
        assert.equal(actual.matchedN, rowKey === "__unknown__" ? expected.unknownN : expected.rows.find(row => row.key === rowKey)?.count || 0, dimension.key + " exact count " + rowKey + " " + slot);
        for (const row of actual.rows) assert.ok(row.eventIds.every(id => input.groups[slot].cohort.eventIds.includes(id)), dimension.key + " never invents report joins");
      } checked++;
    }
  }
}
const original = JSON.stringify({ groups, context, collectionEvidence });
for (const section of ["crops", "animals", "facilities", "spatial", "context", "collections"]) {
  const input = { section, groups, context, collectionEvidence, settings: { spatialRadiusKm: 100 } }; checkDimensions(input, Context.compute(input));
}
const ring = Inspect.inspect({ section: "crops", groups, context, domainKey: "crops_morphology", rowKey: "ring", limit: 1 });
assert.equal(ring.groups.A.matchedN, 2); assert.equal(ring.groups.A.rows.length, 1); assert.equal(ring.groups.A.hasMore, true); assert.equal(ring.groups.A.rows[0].id, "crop1"); assert.deepEqual(ring.groups.A.rows[0].eventIds, []);
const page2 = Inspect.inspect({ section: "crops", groups, context, domainKey: "crops_morphology", rowKey: "ring", offset: 1, limit: 1 });
assert.equal(page2.groups.A.rows[0].id, "crop2"); assert.equal(page2.groups.A.hasMore, false); assert.equal(page2.groups.A.matchedN, 2);
const arbitrary = { A: { ...groups.A, cohort: { eventIds: groups.A.cohort.eventIds } }, B: groups.B };
const scoped = Inspect.inspect({ section: "crops", groups: arbitrary, context, domainKey: "crops_country", rowKey: "France" });
assert.equal(scoped.groups.A.available, false); assert.equal(scoped.groups.A.matchedN, null); assert.equal(scoped.groups.B.matchedN, 1);
const unknownSources = Inspect.inspect({ section: "context", groups, context, domainKey: "report_coordinate_source", rowKey: "__unknown__" });
assert.deepEqual(unknownSources.groups.A.rows[0].eventIds, ["a2"]); assert.equal(unknownSources.groups.A.rows[0].sourceUrl, "");
const allCollection = { section: "collections", groups, collectionEvidence, settings: { collectionEvidence: "all", includeMemberVariants: true } }; checkDimensions(allCollection, Context.compute(allCollection));
assert.equal(JSON.stringify({ groups, context, collectionEvidence }), original, "Inspection does not mutate held populations, source context or review evidence");

// Use the real ephemeris API with a small memory-only atlas, just as the worker
// does, and reconcile every nonempty displayed cell against the real adapter.
const atlas = Planetary.buildEphemerisAtlasBuffer(Array.from({ length: 36 }, (_, index) => day("2024-03-31") + index));
Planetary.setEphemerisAtlas(Planetary.decodeEphemerisAtlas(atlas.buffer, atlas.metadata));
const nuclear = { tests: [{ id: "start", ordinal: day("2024-04-01"), role: "weapons", lat: 0, lon: 0 }, { id: "near", name: "Near test", ordinal: date, role: "weapons", lat: 36, lon: -80 },
  { id: "farther", ordinal: date, role: "peaceful", lat: 38, lon: -80 }, { id: "finish", ordinal: day("2024-05-01"), role: "weapons", lat: 0, lon: 0 }],
  nuclearFacilities: [{ id: "nuclear1", nuclearRoleSourceVerified: true, nuclearRole: "nuclear_research", lat: 36, lon: -80, activeIntervals: [{ startYear: 2000, endYear: 2024 }] }] };
let input = { section: "comparisons", groups, nuclear, settings: { nuclearRadiusKm: 100 } }; checkDimensions(input, Comparisons.compute(input));
const pair = Inspect.inspect({ ...input, domainKey: "nuclear_pair_phase", rowKey: "same_day" });
assert.equal(pair.groups.A.totalN, 1, "100km radius excludes the farther test"); assert.deepEqual(pair.groups.A.rows[0].eventIds, ["a1"]);
input = { ...input, settings: { nuclearRadiusKm: 500 } }; checkDimensions(input, Comparisons.compute(input));
assert.equal(Inspect.inspect({ ...input, domainKey: "nuclear_pair_phase", rowKey: "same_day" }).groups.A.totalN, 2, "500km radius gives two actual report/test pairs");
const contextInput = { ...input, settings: { sourceDomain: "crops", planetaryHeatmaps: false }, groups: { A: { ...groups.A, context: { crops: [{ id: "crop-a", startOrdinal: date, endOrdinal: date, datePrecision: "exact_day", lat: 36, lon: -80, dateRole: "discovery" }] } },
  B: { ...groups.B, context: { crops: [{ id: "crop-b", startOrdinal: other, endOrdinal: other, datePrecision: "exact_day", lat: 0, lon: 100 }, { id: "unknown", datePrecision: "unknown" }] } } } };
checkDimensions(contextInput, Comparisons.compute(contextInput));
const contextPairs = Inspect.inspect({ ...contextInput, domainKey: "nuclear_pair_phase", rowKey: "same_day" });
assert.ok(contextPairs.groups.A.rows.every(row => row.eventIds.length === 0), "Independent crop/test pairs cannot open unrelated UFO reports");
const noChronology = { ...input, nuclear: { nuclearFacilities: nuclear.nuclearFacilities } }; checkDimensions(noChronology, Comparisons.compute(noChronology));
const descriptorMismatch = descriptor(Context.compute({ section: "crops", groups, context }).dimensions[0], "ring"); descriptorMismatch.row.aCount = 999;
assert.throws(() => Inspect.inspect({ section: "crops", groups, context, domainKey: "crops_morphology", rowKey: "ring", dimension: descriptorMismatch }), /disagrees with the displayed/);
const unsupported = Inspect.inspect({ groups, domainKey: "unsupported", rowKey: "anything" }); assert.equal(unsupported.groups.A.available, false);
const browser = vm.createContext({}); vm.runInContext(fs.readFileSync("analysis_session_inspection.js", "utf8"), browser);
const injected = browser.UfoAnalysisSessionInspection.inspect({ section: "crops", groups, context, contextApi: Context, domainKey: "crops_country", rowKey: "France" });
assert.equal(injected.groups.A.matchedN, 1, "Browser factory accepts lazy API injection after it loads");
Planetary.clearEphemerisAtlas();
console.log(`Exact A/B row inspection: ${checked} aggregate-cell checks passed across source records, held reports, qualified spatial pairs, provenance joins, collection versions, lunar states, planetary matrices and nuclear pairs; pagination, unknowns, unavailable sides and immutable inputs passed.`);
