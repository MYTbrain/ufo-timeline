import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url), Session = require("../analysis_session.js");

const fixture = () => ({ key: "lunar_phase", label: "Moon phase", unit: "canonical_reports", order: "source",
  uncertainty: { kind: "sampled_time_interval", label: "Stable–possible counts", estimate: "utc_noon_with_verified_utc_overrides", note: "Sampled source-time bounds, not confidence intervals." },
  heatmap: { kind: "phase", rows: [{ key: "moon", label: "Moon" }], columns: [{ key: "new", label: "New Moon" }, { key: "full", label: "Full Moon" }] },
  a: { totalN: 4, eligibleN: 3, unknownN: 1, coverage: { eligibleExactDateN: 3, verifiedTimeN: 1, dateOnlyN: 2, stableN: 1, ambiguousN: 2, skyEligibleN: 1 }, rows: [
    { key: "new", label: "New Moon", count: 2, lowerCount: 1, upperCount: 3, matrixRow: "moon", matrixColumn: "new" },
    { key: "full", label: "Full Moon", count: 1, lowerCount: 0, upperCount: 2, matrixRow: "moon", matrixColumn: "full" },
  ] },
  b: { totalN: 2, eligibleN: 2, unknownN: 0, coverage: { verifiedTimeN: 0, dateOnlyN: 2, stableN: 0, ambiguousN: 2 }, rows: [
    { key: "new", label: "New Moon", count: 1, lowerCount: 0, upperCount: 2, matrixRow: "moon", matrixColumn: "new" },
    { key: "full", label: "Full Moon", count: 1, lowerCount: 1, upperCount: 1, matrixRow: "moon", matrixColumn: "full" },
  ] } });
const source = fixture(), sourceCopy = JSON.stringify(source), result = Session.compareExternalDimension(source);
const newMoon = result.rows.find(row => row.key === "new"), fullMoon = result.rows.find(row => row.key === "full");
assert.equal(JSON.stringify(source), sourceCopy, "Normalization must not mutate the calculator output");
assert.deepEqual([newMoon.aCount, newMoon.aLowerCount, newMoon.aUpperCount, newMoon.bCount, newMoon.bLowerCount, newMoon.bUpperCount], [2, 1, 3, 1, 0, 2]);
assert.deepEqual([newMoon.aShareOfReports, newMoon.aLowerShareOfReports, newMoon.aUpperShareOfReports], [0.5, 0.25, 0.75], "Bounds use each side's own full report denominator");
assert.deepEqual([newMoon.bShareOfReports, newMoon.bLowerShareOfReports, newMoon.bUpperShareOfReports], [0.5, 0, 1]);
assert.equal(fullMoon.aLowerCount, 0, "A stable lower bound of zero survives normalization");
assert.equal(newMoon.matrixRow, "moon"); assert.equal(newMoon.matrixColumn, "new");
assert.equal(result.heatmap.rows[0].label, "Moon"); assert.equal(result.heatmap.columns.length, 2);
assert.equal(result.a.coverage.verifiedTimeN, 1); assert.equal(result.a.coverage.dateOnlyN, 2); assert.equal(result.a.coverage.skyEligibleN, 1);
assert.equal(result.uncertainty.kind, "sampled_time_interval"); assert.match(result.uncertainty.note, /not confidence intervals/);
assert.ok(Object.isFrozen(result.heatmap.rows)); assert.ok(Object.isFrozen(result.a.coverage)); assert.ok(Object.isFrozen(result.uncertainty));
source.a.rows[0].upperCount = 2; source.a.coverage.dateOnlyN = 99; source.heatmap.rows[0].label = "changed";
assert.equal(newMoon.aUpperCount, 3); assert.equal(result.a.coverage.dateOnlyN, 2); assert.equal(result.heatmap.rows[0].label, "Moon");

for (const change of [
  row => { delete row.lowerCount; }, row => { delete row.upperCount; }, row => { row.lowerCount = 3; }, row => { row.upperCount = 1; },
  row => { row.upperCount = 4; }, row => { row.lowerCount = -1; }, row => { row.lowerCount = 0.5; }, row => { row.upperCount = NaN; },
  row => { row.upperCount = Infinity; }, row => { row.upperCount = "3"; }, row => { row.upperCount = Number.MAX_SAFE_INTEGER + 1; },
]) {
  const value = fixture(); change(value.a.rows[0]); assert.throws(() => Session.compareExternalDimension(value), /sampled/);
}
for (const change of [
  value => { delete value.a.rows[0].matrixColumn; }, value => { value.a.rows[0].matrixRow = 1; }, value => { value.a.rows[0].matrixRow = ""; },
  value => { value.b.rows[0].matrixRow = "sun"; }, value => { value.heatmap.columns[0].key = "unrelated"; },
  value => { value.heatmap.rows.push({ key: "moon", label: "Duplicate" }); },
  value => { value.a.rows.push({ key: "alias", label: "Alias", count: 0, matrixRow: "moon", matrixColumn: "new" }); },
]) {
  const value = fixture(); change(value); assert.throws(() => Session.compareExternalDimension(value), /matrix/);
}
for (const change of [
  value => { value.a.coverage.verifiedTimeN = 5; }, value => { value.a.coverage.dateOnlyN = 1; }, value => { value.a.coverage.ambiguousN = 1; },
  value => { value.a.coverage.skyEligibleN = -1; }, value => { value.a.coverage.verifiedInputN = 2; value.a.coverage.missingInputN = 1; },
]) {
  const value = fixture(); change(value); assert.throws(() => Session.compareExternalDimension(value), /coverage/);
}
for (const change of [
  value => { value.uncertainty.kind = "confidence_interval"; }, value => { value.uncertainty.estimate = "exact_measured"; },
]) {
  const value = fixture(); change(value); assert.throws(() => Session.compareExternalDimension(value), /uncertainty|estimate/);
}
const unavailable = fixture(); unavailable.b = { available: false, totalN: 7, reason: "Source data unavailable" };
const unavailableRow = Session.compareExternalDimension(unavailable).rows[0];
assert.equal(unavailableRow.bCount, null); assert.equal(unavailableRow.bLowerCount, null); assert.equal(unavailableRow.bUpperCount, null); assert.equal(unavailableRow.bLowerShareOfReports, null);
const omitted = fixture(); delete omitted.heatmap; omitted.a.rows = [{ key: "full", count: 3 }];
const omittedRow = Session.compareExternalDimension(omitted).rows.find(row => row.key === "new");
assert.equal(omittedRow.aCount, 0, "A complete available distribution retains true category zeros");
assert.equal(omittedRow.aLowerCount, null, "An omitted uncertainty estimate is not invented as a zero range");
const exactZero = fixture(); delete exactZero.heatmap; exactZero.a = { totalN: 0, eligibleN: 0, unknownN: 0, rows: [{ key: "new", count: 0, lowerCount: 0, upperCount: 0 }] };
const emptyRow = Session.compareExternalDimension(exactZero).rows.find(row => row.key === "new");
assert.equal(emptyRow.aLowerCount, 0); assert.equal(emptyRow.aUpperCount, 0); assert.equal(emptyRow.aLowerShareOfReports, null, "Zero denominators never yield an apparent zero share or NaN");

const stored = Session.createStore();
stored.setGroup("A", { eventIds: ["1", "2"], summary: { distributions: { craft: { eligibleN: 2, unknownN: 0, rows: [{ key: "disc", count: 2, lowerCount: 1, upperCount: 2 }] } } } });
stored.setGroup("B", { eventIds: ["3"], summary: { distributions: { craft: { eligibleN: 1, unknownN: 0, rows: [{ key: "disc", count: 1 }] } } } });
assert.equal(stored.getState().groups.A.summary.distributions.craft.rows[0].lowerCount, 1, "The generic stored distribution also retains optional ranges");
assert.equal(stored.getState().comparison.distributions.craft.rows[0].aLowerCount, 1);
assert.equal(stored.getState().comparison.distributions.craft.rows[0].bLowerCount, null);
console.log("Temporary comparison uncertainty: sampled bound validation and retention, own-denominator shares, matrix alignment, source-time/sky coverage, immutable metadata, unavailable fields and legacy populations passed.");
