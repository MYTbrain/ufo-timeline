import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const context = require("../analysis_encounter_context.js");
const evidence = require("../encounter_evidence.js");
const day = Date.parse("2000-07-01T00:00:00Z") / 86400000;
const greyMask = evidence.beingMask(["grey"]);
const rows = [
  { id: "1", eventId: "1", startOrdinal: day, endOrdinal: day, datePrecision: "exact_day", lat: 0, lon: 0, source: "a", craftType: "disc_saucer", encounterBeingMask: evidence.beingMask(["grey", "small_humanoid"]), encounterAbductionCode: 1, encounterEvidenceReady: true },
  { id: "2", startOrdinal: day, endOrdinal: day + 30, datePrecision: "month", lat: 0, lon: 0, source: "a", encounterBeingMask: greyMask, encounterEvidenceReady: true },
  { id: "3", startOrdinal: day, endOrdinal: day, datePrecision: "exact_day", lat: null, lon: null, source: "b", encounterBeingMask: greyMask, encounterAbductionCode: 2, encounterEvidenceReady: true },
  { id: "4", startOrdinal: day, endOrdinal: day, datePrecision: "exact_day", lat: 0, lon: 0, source: "a", craftType: "non_ufo_context", encounterBeingMask: greyMask, encounterEvidenceReady: true },
];
const crop = { id: "crop", startOrdinal: day, endOrdinal: day, datePrecision: "exact_day", dateRole: "discovery_date", lat: 0, lon: 0, sourceFamilyIds: ["independent"] };
const nuclear = { tests: [{ id: "test", ordinal: day, lat: 0, lon: 0, role: "weapons" }], nuclearFacilities: [{ id: "site", lat: 0, lon: 0, nuclearRoleSourceVerified: true, activeIntervals: [[1900, 2100]] }] };
const options = { rows: rows.concat(rows[0]), range: { start: day - 7, end: day + 31 }, encounterEvidenceReady: true, nuclear,
  crops: [crop, { ...crop, id: "duplicate_marker" }, { ...crop, id: "own_report", lat: 1, originUfoEventIds: ["1"] }], animals: [crop], ordinalEpoch: "unix_day" };
const model = context.computeEncounterContext(options);
assert.equal(model.status, "ready");
assert.equal(model.duplicateIdentityN, 1);
assert.equal(model.indexedMatchedN, 4);
const find = (matrix, id) => matrix.rows.find((row) => row.id === id);
assert.equal(model.groups.find((row) => row.id === "grey").activeN, 4);
assert.equal(find(model.lunar.matrix, "grey").eligible, 2, "Nonexact dates and non-report context stay out of lunar estimates");
assert.equal(find(model.lunar.matrix, "small_humanoid").eligible, 1);
assert.equal(find(model.lunar.matrix, "reported_abduction").eligible, 2);
assert.equal(find(model.nuclear.phases, "grey").eligible, 1, "Nuclear comparisons also require usable coordinates");
assert.equal(find(model.nuclear.phases, "grey").cells.find((row) => row.id === "same_day").count, 1);
assert.equal(find(model.crops.calendar, "grey").eligible, 3);
assert.equal(find(model.crops.calendar, "grey").cells[0].count, 3);
assert.equal(find(model.crops.marker, "grey").eligible, 2);
assert.equal(find(model.crops.marker, "grey").cells[0].count, 2);
assert.equal(model.crops.coverage.eligibleContextClusters, 2, "Same-day co-located marker duplicates form one context cluster");
assert.ok(model.crops.coverage.sourceCollisionPairs > 0);
assert.equal(find(model.crops.calendar, "grey").cells[0].pairCount, 5, "Known own-report links are excluded; other candidates remain descriptive");
assert.equal(find(model.crops.calendar, "nordic").cells[0].share, null);
assert.equal(model.crops.strictSiteStatus, "unavailable_source_verified_event_sites_and_times_required");
const disabled = context.computeEncounterContext({ ...options, cropCirclesEnabled: false });
assert.equal(find(disabled.crops.calendar, "grey").cells[0].count, null, "Disabled context is unavailable, not a zero observation");
assert.equal(context.computeEncounterContext({ ...options, encounterEvidenceReady: false }).status, "unavailable_encounter_evidence");
const unlocated = context.computeEncounterContext({ ...options, crops: [{ ...crop, lat: null, lon: null }] });
assert.equal(find(unlocated.crops.marker, "grey").cells[0].count, null, "Missing context coordinates cannot create a zero-proximity observation");
const missingNuclear = context.computeEncounterContext({ ...options, nuclear: {} });
assert.equal(find(missingNuclear.nuclear.phases, "grey").cells[0].count, null, "Missing independent nuclear catalog is unavailable");
assert.equal(find(missingNuclear.nuclear.facilities, "grey").cells[0].count, null, "Missing facility inventory is unavailable");
const originatingPublisher = context.computeEncounterContext({ ...options, crops: [{ ...crop, originPublisherCodes: ["a"] }] });
assert.equal(find(originatingPublisher.crops.calendar, "grey").cells[0].count, 1, "Known originating publishers exclude same-source comparisons even when opaque source-family hashes differ");
assert.throws(() => context.computeEncounterContext({ ...options, ordinalEpoch: "python_day" }), /Unix-day/);
const planets = context.computeEncounterPlanetary({ ...options, planetarySettings: { zodiacSystem: "sidereal", ayanamsaId: "lahiri", aspectOrbDegrees: 3 } });
assert.equal(planets.status, "ready");
assert.equal(Object.keys(planets.matrices.zodiac).length, 9);
assert.equal(Object.keys(planets.matrices.motion).length, 9);
assert.equal(Object.keys(planets.matrices.aspects).length, 36);
for (const matrix of Object.values(planets.matrices.zodiac)) {
  const grey = find(matrix, "grey");
  assert.equal(grey.eligible, 2);
  assert.equal(grey.cells.reduce((sum, cell) => sum + cell.count, 0), 2);
  for (const cell of grey.cells) assert.ok(cell.lowerCount <= cell.count && cell.count <= cell.upperCount);
}
for (const matrix of Object.values(planets.matrices.aspects)) assert.equal(find(matrix, "grey").cells.reduce((sum, cell) => sum + cell.count, 0), 2, "Major aspect plus outside-band cells partition the cohort");
assert.equal(planets.settings.ayanamsaId, "lahiri");
assert.equal(planets.inferenceEligible, false);
assert.match(planets.housesStatus, /unavailable/);
console.log("Encounter lunar, all-body/all-pair planetary, nuclear, context clustering, lineage and unavailable-data checks passed.");
