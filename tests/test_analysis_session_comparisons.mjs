import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const Adapter = require("../analysis_session_comparisons.js");
const Lunar = require("../analysis_lunar.js"), Planetary = require("../analysis_planetary.js");
const day = iso => Date.parse(iso + "T00:00:00Z") / 86400000;
const dateA = day("2024-04-08"), dateB = day("2024-04-24");
const row = (id, ordinal, extra = {}) => ({ eventId: id, sortOrdinal: ordinal, datePrecision: "exact_day", craftType: "disc_saucer", source: "fixture", mapped: true, lat: 36, lon: -80, ...extra });
const verified = row("a1", dateA, { utcTimestamp: "2024-04-08T18:00:00Z", utcTimestampVerified: true, timeZoneProvenance: "UTC fixture", coordinateEvidenceClass: "source_exact" });
const group = rows => ({ cohort: { eventIds: rows.map(item => item.eventId), scope: { timeRange: { mode: "full" } } }, rows });
const input = { ordinalEpoch: "unix_day", groups: {
  A: group([verified, row("a2", null, { datePrecision: "unknown", mapped: false }), row("withheld", dateA, { encounterOccurrenceDateExcluded: true }), row("context", dateA, { type: "Nuclear / atomic event", craftType: "non_ufo_context" })]),
  B: group([row("b1", dateB, { lat: -30, lon: 100 })]),
}, nuclear: { tests: [
  { id: "first", ordinal: day("2024-04-01"), role: "weapons", lat: 0, lon: 0 },
  { id: "test-a", ordinal: dateA, role: "weapons", lat: 36, lon: -80 },
  { id: "test-b", ordinal: dateA, role: "peaceful", lat: 36, lon: -80 },
  { id: "last", ordinal: day("2024-05-01"), role: "weapons", lat: 0, lon: 0 },
], nuclearFacilities: [{ id: "nuclear-site", nuclearRoleSourceVerified: true, nuclearRole: "nuclear_research", lat: 36, lon: -80, activeIntervals: [{ startYear: 2000, endYear: 2024 }] }] },
artifactHashes: { lunar: "fixture-pin", nuclear: "fixture-nuclear-pin" } };
// The production worker already holds this atlas. Build a small in-memory
// fixture to exercise that same path without writing or copying any data.
const atlas = Planetary.buildEphemerisAtlasBuffer(Array.from({ length: 36 }, (_, index) => day("2024-03-31") + index));
Planetary.setEphemerisAtlas(Planetary.decodeEphemerisAtlas(atlas.buffer, atlas.metadata));
const original = JSON.stringify(input), result = Adapter.compute(input);
assert.equal(JSON.stringify(input), original, "Computing comparisons cannot modify held groups or source records");
assert.equal(result.status, "ready"); assert.equal(result.inferenceEligible, false);
assert.deepEqual(result.artifactHashes, input.artifactHashes);
assert.equal(result.settings.planet, "Venus"); assert.equal(result.settings.partner, "Mars");
assert.equal(result.settings.zodiacSystem, "sidereal"); assert.equal(result.settings.ayanamsaId, "lahiri"); assert.equal(result.settings.orb, 3);
assert.equal(result.settings.nuclearWindowDays, 30);
const dimension = key => { const value = result.dimensions.find(item => item.key === key); assert.ok(value, "Missing comparison: " + key); return value; };
const count = (key, side, category) => dimension(key)[side].rows.find(item => item.key === category)?.count || 0;
assert.equal(dimension("lunar_phase").unit, "canonical_reports");
assert.equal(dimension("lunar_phase").a.totalN, 4); assert.equal(dimension("lunar_phase").a.eligibleN, 1); assert.equal(dimension("lunar_phase").a.unknownN, 3);
assert.equal(count("lunar_phase", "a", "new"), 1); assert.equal(count("lunar_phase", "b", "full"), 1);
assert.equal(dimension("lunar_horizon").a.eligibleN, 1); assert.equal(dimension("lunar_horizon").b.eligibleN, 0);
assert.equal(count("lunar_horizon", "a", "above"), 1);
const lunarOracle = Lunar.computeLunarContext({ rows: [verified] }).domains[0];
assert.deepEqual(dimension("lunar_azimuth").a.rows.map(item => item.count), lunarOracle.sky.azimuthBins.map(item => item.count));
const planetaryOracle = Planetary.computePlanetaryContext({ rows: [verified], planet: "Venus", aspectPartner: "Mars", zodiacSystem: "sidereal", ayanamsaId: "lahiri", samplingMode: "common_grid" }).domains[0];
assert.deepEqual(dimension("planetary_sign").a.rows.map(item => item.count), planetaryOracle.signBins.map(item => item.count));
assert.deepEqual(dimension("planetary_motion").a.rows.map(item => item.count), planetaryOracle.motion.bins.map(item => item.count));
assert.deepEqual(dimension("planetary_aspect_mars").a.rows.map(item => item.count), planetaryOracle.aspectPartners[0].bins.concat(planetaryOracle.aspectPartners[0].outsideBand).map(item => item.count));
assert.equal(dimension("planetary_houses").a.calculated, false); assert.equal(count("planetary_houses", "a", "verified_inputs"), 1);
for (const [key, rows, cells] of [["planetary_all_zodiac", 9, 12], ["planetary_all_motion", 9, 3], ["planetary_all_aspects", 36, 6]]) {
  const field = dimension(key); assert.equal(field.multiLabel, true); assert.equal(field.a.rows.length, rows * cells);
  assert.equal(field.a.rows.reduce((sum, item) => sum + item.count, 0), rows * field.a.eligibleN);
  assert.equal(field.heatmap.rows.length, rows); assert.equal(field.heatmap.columns.length, cells);
  for (const item of field.a.rows) assert.ok(item.lowerCount <= item.count && item.count <= item.upperCount);
}
assert.equal(dimension("nuclear_pair_phase").unit, "report_test_pairs");
assert.equal(dimension("nuclear_pair_phase").a.totalN, 2, "One report linked to two tests yields two pairs, not two reports");
assert.equal(count("nuclear_pair_phase", "a", "same_day"), 2);
assert.equal(count("nuclear_spatial_reports", "a", "same_day"), 1);
assert.equal(count("nuclear_temporal_roles", "a", "weapons"), 1); assert.equal(count("nuclear_temporal_roles", "a", "peaceful"), 1);
assert.equal(count("nuclear_facility_activity", "a", "activity_unknown"), 1, "Closing-year uncertainty is not promoted to confirmed daily activity");
assert.ok(dimension("nuclear_temporal").notes.some(note => /global/.test(note)));
for (const field of result.dimensions) for (const slot of ["a", "b"]) {
  const side = field[slot]; assert.equal(side.eligibleN + side.unknownN, side.totalN);
  assert.ok(side.rows.every(item => Number.isInteger(item.count) && item.count >= 0 && item.count <= side.eligibleN));
  if (side.available) assert.ok(field.multiLabel ? side.rows.reduce((sum, item) => sum + item.count, 0) >= side.eligibleN : side.rows.reduce((sum, item) => sum + item.count, 0) === side.eligibleN,
    field.key + " must retain a complete partition or explicitly overlapping labels");
}

// Each context catalog retains its own captured records and date roles. It
// cannot borrow either the report count or the other group's context records.
const contextInput = { ...input, settings: { sourceDomain: "crops", planetaryHeatmaps: false }, groups: {
  A: { ...input.groups.A, context: { crops: [{ id: "crop-a", startOrdinal: dateA, endOrdinal: dateA, datePrecision: "exact_day", dateRole: "discovery", lat: 36, lon: -80 }] } },
  B: { ...input.groups.B, context: { crops: [{ id: "crop-b", startOrdinal: dateB, endOrdinal: dateB, datePrecision: "exact_day", dateRole: "catalog", lat: 0, lon: 100 }, { id: "crop-unknown", datePrecision: "unknown" }] } },
} };
const contexts = Adapter.compute(contextInput), cropPhase = contexts.dimensions.find(item => item.key === "lunar_phase");
assert.equal(cropPhase.unit, "crop_catalog_records"); assert.equal(cropPhase.a.totalN, 1); assert.equal(cropPhase.b.totalN, 2); assert.equal(cropPhase.b.unknownN, 1);
assert.ok(contexts.notes.some(note => /not promoted/.test(note)));
const noCatalog = Adapter.compute({ ...input, nuclear: {}, settings: { planetaryHeatmaps: false } });
assert.equal(noCatalog.dimensions.find(item => item.key === "nuclear_spatial_reports").a.available, false);
assert.equal(noCatalog.dimensions.find(item => item.key === "nuclear_facility_role").a.available, false);
assert.throws(() => Adapter.compute({ ...input, groups: { ...input.groups, A: { ...input.groups.A, rows: input.groups.A.rows.slice(1) } } }), /missing captured/);
assert.throws(() => Adapter.compute({ ...input, groups: { ...input.groups, A: { ...input.groups.A, rows: input.groups.A.rows.concat(row("outside", dateA)) } } }), /outside its captured/);
assert.throws(() => Adapter.compute({ ...input, ordinalEpoch: "guessed" }), /ordinalEpoch/);
const inheritedWindow = Adapter.compute({ ...input, settings: { planetaryHeatmaps: false }, groups: { ...input.groups,
  B: { ...input.groups.B, cohort: { ...input.groups.B.cohort, scope: { timeRange: { startIso: "2024-04-08", endIso: "2024-04-08" } } } } } });
assert.equal(inheritedWindow.dimensions.find(item => item.key === "lunar_phase").b.totalN, 1, "Exact captured report membership cannot be clipped by an inherited map date window");
assert.equal(inheritedWindow.dimensions.find(item => item.key === "lunar_phase").b.rows.find(item => item.key === "full").count, 1);
const classification = Adapter.compute({ ...input, settings: { planetaryHeatmaps: false }, groups: {
  A: group([row("explicit-context", dateA, { visualTypeGroup: "non_ufo_context", craftType: "unknown", type: "Unknown" })]),
  B: group([row("appearance-fireball", dateA, { craftType: "fireball_meteor_like", type: "Fireball" })]),
} });
assert.equal(classification.dimensions.find(item => item.key === "lunar_phase").a.eligibleN, 0);
assert.equal(classification.dimensions.find(item => item.key === "planetary_sign").a.eligibleN, 0);
assert.equal(classification.dimensions.find(item => item.key === "nuclear_temporal").a.eligibleN, 0);
assert.equal(classification.dimensions.find(item => item.key === "nuclear_temporal").b.eligibleN, 1, "An appearance category alone is not an identified explanation");
const pythonInput = { ...input, ordinalEpoch: "python_day", settings: { planetaryHeatmaps: false }, groups: Object.fromEntries(Object.entries(input.groups).map(([slot, value]) => [slot, { ...value, rows: value.rows.map(item => ({ ...item, sortOrdinal: item.sortOrdinal == null ? null : item.sortOrdinal + 719163 })) }])) };
assert.deepEqual(Adapter.compute(pythonInput).dimensions.find(item => item.key === "lunar_phase").a.rows.map(item => item.count), dimension("lunar_phase").a.rows.map(item => item.count));

// Browser/worker UMD boundary uses the already loaded, pinned calculators.
const self = { UfoAnalysisLunar: Lunar, UfoAnalysisPlanetary: Planetary, UfoAnalysisNuclear: require("../analysis_nuclear.js") };
vm.runInNewContext(fs.readFileSync("analysis_session_comparisons.js", "utf8"), { self });
assert.equal(typeof self.UfoAnalysisSessionComparisons.compute, "function");
console.log("Temporary celestial/nuclear comparisons: exact membership, retained unknowns, Moon sky eligibility, precomputed planetary grid, shared settings, report/pair denominators, nuclear activity uncertainty and context units passed.");
